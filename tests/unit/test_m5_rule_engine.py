import pytest

from Api.m5_rule_engine import ControlledSemanticAdapter, DeepSeekSemanticAdapter, RuleOutcome, evaluate_rule

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
