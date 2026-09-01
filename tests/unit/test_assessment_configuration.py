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
def test_legacy_scenario_is_valid() -> None:
    validate_scenario_definition(LEGACY_SCENARIO_DEFINITION)
