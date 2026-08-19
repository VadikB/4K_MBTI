import pytest

from Api.assessment_configuration import (
    LEGACY_METHODOLOGY_DEFINITION,
    LEGACY_SCENARIO_DEFINITION,
    definition_checksum,
)
from Api.assessment_runtime import validate_scenario_definition


@pytest.mark.unit
def test_definition_checksum_is_stable_for_key_order() -> None:
    assert definition_checksum({"b": 2, "a": 1}) == definition_checksum({"a": 1, "b": 2})


@pytest.mark.unit
def test_legacy_methodology_has_exactly_four_evaluators() -> None:
    evaluator_codes = [item["evaluator"] for item in LEGACY_METHODOLOGY_DEFINITION["competencies"]]
    assert evaluator_codes == [
        "evaluation.communication",
        "evaluation.teamwork",
        "evaluation.creativity",
        "evaluation.critical_thinking",
    ]


@pytest.mark.unit
def test_legacy_scenario_is_valid_and_contains_no_mbti() -> None:
    validate_scenario_definition(LEGACY_SCENARIO_DEFINITION)
    assert "mbti" not in str(LEGACY_SCENARIO_DEFINITION).lower()


@pytest.mark.unit
def test_scenario_rejects_mbti_component() -> None:
    invalid = {
        "initial_stage": "evaluate",
        "stages": [
            {
                "id": "evaluate",
                "component": "evaluation.mbti",
                "component_version": 1,
                "on_success": "complete_session",
            }
        ],
    }
    with pytest.raises(ValueError, match="MBTI"):
        validate_scenario_definition(invalid)
