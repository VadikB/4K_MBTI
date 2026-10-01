import pytest

from Api.llm.contracts import LlmResponse
from Api.m5_rule_engine import (ControlledSemanticAdapter, DeepSeekCharacterAdapter,
                                DeepSeekSemanticAdapter, RuleOutcome,
                                build_m5_ai_operations_snapshot, evaluate_rule)

pytestmark = pytest.mark.unit


def decide(rule, outcomes):
    return evaluate_rule(rule, state={"status": "active"}, data={}, text="Любой смысловой текст",
                         turn_id="turn-1", semantic_adapter=ControlledSemanticAdapter(outcomes))


def test_semantic_decision_does_not_depend_on_keyword_presence():
    rule = {"rule_id": "r1", "type": "semantic_decision", "decision_code": "REQUEST", "condition": "asked for data"}
    assert decide(rule, {"r1": "TRUE"}).outcome == RuleOutcome.TRUE
    assert decide(rule, {"r1": "FALSE"}).outcome == RuleOutcome.FALSE


@pytest.mark.parametrize("value", ["UNKNOWN", "ERROR"])
def test_not_does_not_turn_unknown_or_error_into_permission(value):
    rule = {"type": "not", "rules": [{"rule_id": "r1", "type": "semantic_decision"}]}
    assert decide(rule, {"r1": value}).outcome.value == value


def test_all_any_propagate_uncertainty_safely():
    yes = {"rule_id": "yes", "type": "semantic_decision"}
    unknown = {"rule_id": "unknown", "type": "semantic_decision"}
    adapter = {"yes": "TRUE", "unknown": "UNKNOWN"}
    assert decide({"type": "all", "rules": [yes, unknown]}, adapter).outcome == RuleOutcome.UNKNOWN
    assert decide({"type": "any", "rules": [yes, unknown]}, adapter).outcome == RuleOutcome.TRUE


def test_unknown_operator_is_rejected():
    with pytest.raises(ValueError, match="RULE_OPERATOR_UNSUPPORTED"):
        decide({"type": "python", "code": "open('/tmp/x')"}, {})


def test_real_adapter_keeps_versioned_prompt_ref_when_gateway_is_unavailable():
    gateway = type("Gateway", (), {"enabled": False, "model": "test-model"})()
    decision = DeepSeekSemanticAdapter(gateway).decide(
        rule={"rule_id": "r", "condition": {}, "allowed_codes": ["MATCH", "NO_MATCH", "UNKNOWN"]},
        text="text", turn_id="turn", context={})
    assert decision.outcome == RuleOutcome.UNKNOWN
    assert decision.prompt_ref["id"] == "m5_semantic_decision"


def test_character_adapter_keeps_versioned_prompt_ref_when_gateway_is_unavailable():
    gateway = type("Gateway", (), {"enabled": False, "model": "test-model"})()
    reply = DeepSeekCharacterAdapter(gateway).respond(
        material={"material_id": "m", "reaction_rule": "constraint"},
        character={"character_id": "c", "public_position": "position"},
        text="turn", turn_id="turn", context={})
    assert reply.status == "UNKNOWN"
    assert reply.prompt_ref["id"] == "m5_character_response"


def test_semantic_adapter_sends_frozen_model_endpoint_parameters_and_keeps_provider_trace():
    operation = build_m5_ai_operations_snapshot()["semantic_decision"]

    class Gateway:
        enabled = True
        model = operation["model"]
        base_url = operation["endpoint"].removesuffix("/chat/completions")

        def chat_with_trace(self, messages, **kwargs):
            assert kwargs["temperature"] == operation["parameters"]["temperature"]
            assert kwargs["max_tokens"] == operation["parameters"]["max_tokens"]
            return LlmResponse(
                '{"code":"MATCH","basis":"ok"}',
                {"request_id": "provider-1", "model": operation["model"], "revision": None},
                {"provider": "deepseek", "endpoint": operation["endpoint"], "model": operation["model"],
                 "parameters": operation["parameters"], "messages": messages},
            )

    result = DeepSeekSemanticAdapter(Gateway(), operation=operation).decide(
        rule={"rule_id": "r", "condition": {}, "allowed_codes": ["MATCH", "NO_MATCH", "UNKNOWN"]},
        text="text", turn_id="turn", context={},
    )
    assert result.outcome == RuleOutcome.TRUE
    assert result.ai_trace["sent"]["model"] == operation["model"]
    assert result.ai_trace["provider"]["request_id"] == "provider-1"
    assert result.ai_trace["provider"]["revision"] is None


def test_semantic_adapter_rejects_provider_model_mismatch():
    operation = build_m5_ai_operations_snapshot()["semantic_decision"]

    class Gateway:
        enabled = True
        model = operation["model"]
        base_url = operation["endpoint"].removesuffix("/chat/completions")

        def chat_with_trace(self, messages, **kwargs):
            return LlmResponse(
                '{"code":"MATCH","basis":"ok"}', {"model": "unexpected-model"},
                {"endpoint": operation["endpoint"], "model": operation["model"], "messages": messages},
            )

    result = DeepSeekSemanticAdapter(Gateway(), operation=operation).decide(
        rule={"rule_id": "r", "condition": {}, "allowed_codes": ["MATCH", "NO_MATCH", "UNKNOWN"]},
        text="text", turn_id="turn", context={},
    )
    assert result.outcome == RuleOutcome.ERROR
    assert result.code == "AI_PROVIDER_IDENTITY_MISMATCH"
