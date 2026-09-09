import pytest

from scripts.repair_incomplete_frozen_agent_bundle import _missing_agent_codes


@pytest.mark.unit
def test_missing_agent_codes_supports_legacy_evaluator_references() -> None:
    snapshot = {
        "methodology": {
            "definition": {
                "competencies": [
                    {"evaluator": "evaluation.communication"},
                    {"evaluator": "evaluation.teamwork"},
                ]
            }
        },
        "prompts": {"agent_definitions": {"teamwork": {"version": 1}}},
    }

    assert _missing_agent_codes(snapshot) == ["communication"]


@pytest.mark.unit
def test_complete_agent_bundle_has_no_missing_codes() -> None:
    snapshot = {
        "methodology": {
            "definition": {
                "competencies": [
                    {
                        "evaluator": "evaluation.communication",
                        "agent_definition": {"code": "communication_v2", "version": 2},
                    }
                ]
            }
        },
        "prompts": {"agent_definitions": {"communication_v2": {"version": 2}}},
    }

    assert _missing_agent_codes(snapshot) == []
