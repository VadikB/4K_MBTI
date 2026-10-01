"""Ограниченный вычислитель правил M5; не исполняет код из артефактов."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from Api.config import settings
from Api.llm.contracts import LlmGatewayError
from Api.llm.deepseek_gateway import DeepSeekGateway


class RuleOutcome(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Decision:
    outcome: RuleOutcome
    code: str
    basis: str
    turn_ids: tuple[str, ...] = ()
    handler_version: str = "m5-rule-engine/1"
    adapter: str = "server"
    model: str | None = None
    controlled_test: bool = False
    prompt_ref: dict | None = None
    ai_trace: dict | None = None

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome.value, "code": self.code, "basis": self.basis,
            "turn_ids": list(self.turn_ids), "handler_version": self.handler_version,
            "adapter": self.adapter, "model": self.model, "controlled_test": self.controlled_test,
            "prompt_ref": self.prompt_ref,
            "ai_trace": self.ai_trace,
        }


class SemanticDecisionAdapter(Protocol):
    def decide(self, *, rule: dict, text: str, turn_id: str, context: dict) -> Decision: ...


@dataclass(frozen=True)
class CharacterReply:
    status: str
    content: str | None
    adapter: str
    model: str | None = None
    controlled_test: bool = False
    prompt_ref: dict | None = None
    ai_trace: dict | None = None


class CharacterResponseAdapter(Protocol):
    def respond(self, *, material: dict, character: dict, text: str, turn_id: str, context: dict) -> CharacterReply: ...


class ControlledCharacterAdapter:
    def __init__(self, responses: dict[str, str]): self.responses = responses
    def respond(self, *, material: dict, character: dict, text: str, turn_id: str, context: dict) -> CharacterReply:
        value = self.responses.get(material["material_id"])
        return CharacterReply("COMPLETED" if value else "UNKNOWN", value, "controlled", controlled_test=True)


def _prompt_bundle(name: str) -> tuple[str, dict]:
    root = Path(__file__).resolve().parents[1] / f"assessment_definitions/prompts/{name}/v1"
    manifest = json.loads((root / "manifest.json").read_text())
    prompt_bytes = (root / "prompt.md").read_bytes()
    prompt_checksum = hashlib.sha256(prompt_bytes).hexdigest()
    if prompt_checksum != manifest["artifacts"][0]["sha256"]:
        raise RuntimeError(f"{name.upper()}_PROMPT_CHECKSUM_MISMATCH")
    return prompt_bytes.decode(), {"id": manifest["id"], "version": manifest["version"], "checksum": prompt_checksum}


def build_m5_ai_operations_snapshot() -> dict[str, dict[str, Any]]:
    """Фиксирует исполнимые настройки; секреты в snapshot не входят."""
    operations = {}
    for code, bundle, parameters in (
        ("semantic_decision", "m5_semantic_decision", {"temperature": 0, "max_tokens": 300, "timeout_seconds": 60}),
        ("character_response", "m5_character_response", {"temperature": 0.2, "max_tokens": 500, "timeout_seconds": 60}),
        ("technical_c45", "m5_technical_c45", {"temperature": 0, "max_tokens": 300, "timeout_seconds": 30}),
    ):
        _, prompt_ref = _prompt_bundle(bundle)
        operations[code] = {
            "schema_version": 1, "provider": "deepseek",
            "endpoint": f"{str(settings.deepseek_base_url).rstrip('/')}/chat/completions",
            "model": str(settings.deepseek_model), "parameters": parameters,
            "prompt_ref": prompt_ref, "response_format": "json_object",
            "limits": {"max_input_bytes": 200000},
            "identity_policy": {"provider_model_must_match": True, "provider_revision": "observe_if_available"},
        }
    return operations


def _gateway_for(operation: dict | None, gateway: Any | None) -> Any:
    if not operation:
        return gateway or DeepSeekGateway()
    expected_endpoint = str(operation["endpoint"])
    base_url = expected_endpoint.removesuffix("/chat/completions")
    resolved = gateway or DeepSeekGateway(base_url=base_url, model=str(operation["model"]))
    actual_endpoint = f"{str(getattr(resolved, 'base_url', base_url)).rstrip('/')}/chat/completions"
    actual_model = str(getattr(resolved, "model", operation["model"]))
    if getattr(resolved, "enabled", True) and (
        actual_endpoint != expected_endpoint or actual_model != str(operation["model"])
    ):
        raise RuntimeError("M5_AI_CONFIG_IDENTITY_MISMATCH")
    return resolved


def _call_with_trace(gateway: Any, messages: list[dict], *, operation: dict, routing_key: str) -> tuple[str, dict]:
    params = dict(operation["parameters"])
    intended = {key: operation[key] for key in ("provider", "endpoint", "model", "parameters", "prompt_ref", "response_format")}
    try:
        if hasattr(gateway, "chat_with_trace"):
            response = gateway.chat_with_trace(messages, routing_key=routing_key, **params)
            sent = dict(response.sent)
            provider = dict(response.provider)
            content = response.content
        else:
            content = gateway.chat(messages, routing_key=routing_key, **params)
            sent = {"provider": operation["provider"], "endpoint": operation["endpoint"],
                    "model": operation["model"], "parameters": params, "messages": messages}
            provider = {"request_id": None, "model": None, "revision": None, "finish_reason": None, "usage": None}
        mismatch = provider.get("model") not in (None, "", operation["model"])
        content = str(content)
        return content, {"intended": intended, "sent": sent, "provider": provider,
                              "response": {"content": content,
                                           "checksum": hashlib.sha256(content.encode("utf-8")).hexdigest()},
                              "identity_status": "mismatch" if mismatch else "matched_or_unreported"}
    except LlmGatewayError as exc:
        exc.ai_trace = {"intended": intended, "sent": exc.sent, "provider": exc.provider,
                        "identity_status": "technical_failure"}
        raise


def execute_frozen_ai_json(*, operation: dict, prompt_bundle: str, input_value: dict,
                           gateway: Any | None = None, routing_key: str) -> tuple[dict, dict]:
    resolved = _gateway_for(operation, gateway)
    if not resolved.enabled:
        raise RuntimeError("M5_AI_GATEWAY_UNAVAILABLE")
    prompt, prompt_ref = _prompt_bundle(prompt_bundle)
    if prompt_ref != operation["prompt_ref"]:
        raise RuntimeError("M5_AI_PROMPT_IDENTITY_MISMATCH")
    input_bytes = json.dumps(input_value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    max_input_bytes = int((operation.get("limits") or {}).get("max_input_bytes") or 0)
    if max_input_bytes and len(input_bytes) > max_input_bytes:
        exc = ValueError("M5_AI_CONTEXT_LIMIT_EXCEEDED")
        exc.ai_trace = {
            "intended": {key: operation.get(key) for key in
                         ("provider", "endpoint", "model", "parameters", "prompt_ref", "response_format")},
            "sent": {}, "provider": {}, "response": {}, "identity_status": "technical_failure",
        }
        raise exc
    raw, ai_trace = _call_with_trace(
        resolved,
        [{"role": "system", "content": prompt},
         {"role": "user", "content": json.dumps(input_value, ensure_ascii=False)}],
        operation=operation, routing_key=routing_key,
    )
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        exc.ai_trace = ai_trace
        raise
    if not isinstance(value, dict):
        exc = ValueError("M5_AI_RESPONSE_NOT_OBJECT")
        exc.ai_trace = ai_trace
        raise exc
    return value, ai_trace


class DeepSeekCharacterAdapter:
    def __init__(self, gateway: DeepSeekGateway | None = None, *, operation: dict | None = None):
        self.operation = operation or build_m5_ai_operations_snapshot()["character_response"]
        self.gateway = _gateway_for(self.operation, gateway)
        self.prompt, self.prompt_ref = _prompt_bundle("m5_character_response")
        if self.prompt_ref != self.operation["prompt_ref"]:
            raise RuntimeError("M5_AI_PROMPT_IDENTITY_MISMATCH")

    def respond(self, *, material: dict, character: dict, text: str, turn_id: str, context: dict) -> CharacterReply:
        if not self.gateway.enabled:
            return CharacterReply("UNKNOWN", None, "deepseek", self.operation["model"], prompt_ref=self.prompt_ref)
        request = {"character": {"id": character["character_id"], "public_position": character["public_position"]},
                   "reaction_constraint": material["reaction_rule"], "assessee_turn": text, "context": context}
        ai_trace = None
        try:
            raw, ai_trace = _call_with_trace(
                self.gateway, [{"role": "system", "content": self.prompt},
                               {"role": "user", "content": json.dumps(request, ensure_ascii=False)}],
                operation=self.operation,
                routing_key="m5-character:" + hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest())
            content = str(json.loads(raw).get("response") or "").strip()
            if not content:
                return CharacterReply("ERROR", None, "deepseek", self.operation["model"], prompt_ref=self.prompt_ref, ai_trace=ai_trace)
            if ai_trace["identity_status"] == "mismatch":
                return CharacterReply("ERROR", None, "deepseek", self.operation["model"], prompt_ref=self.prompt_ref, ai_trace=ai_trace)
            return CharacterReply("COMPLETED", content, "deepseek", self.operation["model"], prompt_ref=self.prompt_ref, ai_trace=ai_trace)
        except Exception as exc:
            return CharacterReply("ERROR", None, "deepseek", self.operation["model"], prompt_ref=self.prompt_ref,
                                  ai_trace=getattr(exc, "ai_trace", None) or ai_trace)


class ControlledSemanticAdapter:
    """Детерминированный адаптер только для проверок механизма."""

    def __init__(self, outcomes: dict[str, str]):
        self.outcomes = outcomes

    def decide(self, *, rule: dict, text: str, turn_id: str, context: dict) -> Decision:
        value = self.outcomes.get(rule["rule_id"], "UNKNOWN")
        outcome = RuleOutcome(value)
        return Decision(outcome, rule.get("decision_code", "CONTROLLED"), "controlled fixture",
                        (turn_id,), adapter="controlled", controlled_test=True)


class DeepSeekSemanticAdapter:
    def __init__(self, gateway: DeepSeekGateway | None = None, *, operation: dict | None = None):
        self.operation = operation or build_m5_ai_operations_snapshot()["semantic_decision"]
        self.gateway = _gateway_for(self.operation, gateway)
        self.prompt, self.prompt_ref = _prompt_bundle("m5_semantic_decision")
        if self.prompt_ref != self.operation["prompt_ref"]:
            raise RuntimeError("M5_AI_PROMPT_IDENTITY_MISMATCH")

    def decide(self, *, rule: dict, text: str, turn_id: str, context: dict) -> Decision:
        if not self.gateway.enabled:
            return Decision(RuleOutcome.UNKNOWN, "SEMANTIC_ADAPTER_UNAVAILABLE", "AI gateway unavailable",
                            (turn_id,), adapter="deepseek", model=self.operation["model"], prompt_ref=self.prompt_ref)
        allowed = rule.get("allowed_codes", ["MATCH", "NO_MATCH", "UNKNOWN"])
        prompt = {
            "condition": rule.get("condition"), "allowed_codes": allowed,
            "message": text, "factual_context": context,
        }
        ai_trace = None
        try:
            raw, ai_trace = _call_with_trace(
                self.gateway, [{"role": "system", "content": self.prompt},
                               {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                operation=self.operation,
                routing_key="m5-semantic:" + hashlib.sha256(json.dumps(prompt, sort_keys=True).encode()).hexdigest(),
            )
            if ai_trace["identity_status"] == "mismatch":
                return Decision(RuleOutcome.ERROR, "AI_PROVIDER_IDENTITY_MISMATCH", "provider model mismatch",
                                (turn_id,), adapter="deepseek", model=self.operation["model"],
                                prompt_ref=self.prompt_ref, ai_trace=ai_trace)
            value = json.loads(raw)
            code = str(value.get("code", "UNKNOWN"))
            if code not in allowed:
                return Decision(RuleOutcome.ERROR, "SEMANTIC_OUTPUT_INVALID", "code outside enum",
                                (turn_id,), adapter="deepseek", model=self.operation["model"], prompt_ref=self.prompt_ref,
                                ai_trace=ai_trace)
            outcome = RuleOutcome.TRUE if code == rule.get("true_code", "MATCH") else (
                RuleOutcome.UNKNOWN if code == "UNKNOWN" else RuleOutcome.FALSE)
            return Decision(outcome, code, str(value.get("basis") or ""), (turn_id,),
                            adapter="deepseek", model=self.operation["model"], prompt_ref=self.prompt_ref, ai_trace=ai_trace)
        except Exception as exc:
            return Decision(RuleOutcome.ERROR, "SEMANTIC_ADAPTER_ERROR", type(exc).__name__,
                            (turn_id,), adapter="deepseek", model=self.operation["model"], prompt_ref=self.prompt_ref,
                            ai_trace=getattr(exc, "ai_trace", None) or ai_trace)


def _combine(kind: str, children: list[Decision]) -> Decision:
    outcomes = [x.outcome for x in children]
    if kind == "not":
        if len(children) != 1:
            raise ValueError("RULE_NOT_ARITY")
        value = children[0].outcome
        mapped = RuleOutcome.FALSE if value == RuleOutcome.TRUE else RuleOutcome.TRUE if value == RuleOutcome.FALSE else value
        return Decision(mapped, "NOT", f"not {value.value}", children[0].turn_ids)
    if RuleOutcome.ERROR in outcomes:
        return Decision(RuleOutcome.ERROR, kind.upper(), "child error")
    if kind == "all":
        if RuleOutcome.FALSE in outcomes:
            return Decision(RuleOutcome.FALSE, "ALL", "at least one false")
        return Decision(RuleOutcome.UNKNOWN if RuleOutcome.UNKNOWN in outcomes else RuleOutcome.TRUE, "ALL", "all children")
    if kind == "any":
        if RuleOutcome.TRUE in outcomes:
            return Decision(RuleOutcome.TRUE, "ANY", "at least one true")
        return Decision(RuleOutcome.UNKNOWN if RuleOutcome.UNKNOWN in outcomes else RuleOutcome.FALSE, "ANY", "all children")
    raise ValueError("RULE_OPERATOR_UNSUPPORTED")


def evaluate_rule(rule: dict, *, state: dict, data: dict, text: str, turn_id: str,
                  semantic_adapter: SemanticDecisionAdapter) -> Decision:
    kind = rule.get("type")
    if kind in {"all", "any", "not"}:
        return _combine(kind, [evaluate_rule(x, state=state, data=data, text=text, turn_id=turn_id,
                                             semantic_adapter=semantic_adapter) for x in rule.get("rules", [])])
    if kind == "state_predicate":
        actual = state.get(rule.get("field"))
        expected = rule.get("equals")
        return Decision(RuleOutcome.TRUE if actual == expected else RuleOutcome.FALSE,
                        "STATE_EQUALS", f"{rule.get('field')}={actual!r}")
    if kind == "data_predicate":
        actual = data.get(rule.get("field"))
        if actual is None:
            return Decision(RuleOutcome.UNKNOWN, "DATA_MISSING", str(rule.get("field")))
        expected = rule.get("equals")
        return Decision(RuleOutcome.TRUE if actual == expected else RuleOutcome.FALSE,
                        "DATA_EQUALS", f"{rule.get('field')}={actual!r}")
    if kind == "semantic_decision":
        return semantic_adapter.decide(rule=rule, text=text, turn_id=turn_id, context={"state": state, "data": data})
    raise ValueError("RULE_OPERATOR_UNSUPPORTED")
