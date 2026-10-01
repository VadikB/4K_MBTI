"""Ограниченный вычислитель правил M5; не исполняет код из артефактов."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

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

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome.value, "code": self.code, "basis": self.basis,
            "turn_ids": list(self.turn_ids), "handler_version": self.handler_version,
            "adapter": self.adapter, "model": self.model, "controlled_test": self.controlled_test,
            "prompt_ref": self.prompt_ref,
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


class CharacterResponseAdapter(Protocol):
    def respond(self, *, material: dict, character: dict, text: str, turn_id: str, context: dict) -> CharacterReply: ...


class ControlledCharacterAdapter:
    def __init__(self, responses: dict[str, str]): self.responses = responses
    def respond(self, *, material: dict, character: dict, text: str, turn_id: str, context: dict) -> CharacterReply:
        value = self.responses.get(material["material_id"])
        return CharacterReply("COMPLETED" if value else "UNKNOWN", value, "controlled", controlled_test=True)


class DeepSeekCharacterAdapter:
    def __init__(self, gateway: DeepSeekGateway | None = None):
        self.gateway = gateway or DeepSeekGateway()
        root = Path(__file__).resolve().parents[1] / "assessment_definitions/prompts/m5_character_response/v1"
        manifest = json.loads((root / "manifest.json").read_text())
        prompt_bytes = (root / "prompt.md").read_bytes()
        prompt_checksum = hashlib.sha256(prompt_bytes).hexdigest()
        if prompt_checksum != manifest["artifacts"][0]["sha256"]:
            raise RuntimeError("M5_CHARACTER_PROMPT_CHECKSUM_MISMATCH")
        self.prompt = prompt_bytes.decode()
        self.prompt_ref = {"id": manifest["id"], "version": manifest["version"], "checksum": prompt_checksum}

    def respond(self, *, material: dict, character: dict, text: str, turn_id: str, context: dict) -> CharacterReply:
        if not self.gateway.enabled:
            return CharacterReply("UNKNOWN", None, "deepseek", self.gateway.model, prompt_ref=self.prompt_ref)
        request = {"character": {"id": character["character_id"], "public_position": character["public_position"]},
                   "reaction_constraint": material["reaction_rule"], "assessee_turn": text, "context": context}
        try:
            raw = self.gateway.chat(
                [{"role": "system", "content": self.prompt},
                 {"role": "user", "content": json.dumps(request, ensure_ascii=False)}],
                temperature=0.2, max_tokens=500, timeout_seconds=60,
                routing_key="m5-character:" + hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest())
            content = str(json.loads(raw).get("response") or "").strip()
            if not content:
                return CharacterReply("ERROR", None, "deepseek", self.gateway.model, prompt_ref=self.prompt_ref)
            return CharacterReply("COMPLETED", content, "deepseek", self.gateway.model, prompt_ref=self.prompt_ref)
        except Exception:
            return CharacterReply("ERROR", None, "deepseek", self.gateway.model, prompt_ref=self.prompt_ref)


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
    def __init__(self, gateway: DeepSeekGateway | None = None):
        self.gateway = gateway or DeepSeekGateway()
        root = Path(__file__).resolve().parents[1] / "assessment_definitions/prompts/m5_semantic_decision/v1"
        manifest = json.loads((root / "manifest.json").read_text())
        prompt_bytes = (root / "prompt.md").read_bytes()
        prompt_checksum = hashlib.sha256(prompt_bytes).hexdigest()
        if prompt_checksum != manifest["artifacts"][0]["sha256"]:
            raise RuntimeError("M5_SEMANTIC_PROMPT_CHECKSUM_MISMATCH")
        self.prompt = prompt_bytes.decode()
        self.prompt_ref = {"id": manifest["id"], "version": manifest["version"], "checksum": prompt_checksum}

    def decide(self, *, rule: dict, text: str, turn_id: str, context: dict) -> Decision:
        if not self.gateway.enabled:
            return Decision(RuleOutcome.UNKNOWN, "SEMANTIC_ADAPTER_UNAVAILABLE", "AI gateway unavailable",
                            (turn_id,), adapter="deepseek", model=self.gateway.model, prompt_ref=self.prompt_ref)
        allowed = rule.get("allowed_codes", ["MATCH", "NO_MATCH", "UNKNOWN"])
        prompt = {
            "condition": rule.get("condition"), "allowed_codes": allowed,
            "message": text, "factual_context": context,
        }
        try:
            raw = self.gateway.chat(
                [{"role": "system", "content": self.prompt},
                 {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                temperature=0, max_tokens=300, timeout_seconds=60,
                routing_key="m5-semantic:" + hashlib.sha256(json.dumps(prompt, sort_keys=True).encode()).hexdigest(),
            )
            value = json.loads(raw)
            code = str(value.get("code", "UNKNOWN"))
            if code not in allowed:
                return Decision(RuleOutcome.ERROR, "SEMANTIC_OUTPUT_INVALID", "code outside enum",
                                (turn_id,), adapter="deepseek", model=self.gateway.model, prompt_ref=self.prompt_ref)
            outcome = RuleOutcome.TRUE if code == rule.get("true_code", "MATCH") else (
                RuleOutcome.UNKNOWN if code == "UNKNOWN" else RuleOutcome.FALSE)
            return Decision(outcome, code, str(value.get("basis") or ""), (turn_id,),
                            adapter="deepseek", model=self.gateway.model, prompt_ref=self.prompt_ref)
        except Exception as exc:
            return Decision(RuleOutcome.ERROR, "SEMANTIC_ADAPTER_ERROR", type(exc).__name__,
                            (turn_id,), adapter="deepseek", model=self.gateway.model, prompt_ref=self.prompt_ref)


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
