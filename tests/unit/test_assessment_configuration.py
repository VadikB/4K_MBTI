import pytest

from Api.assessment_configuration import (
    LEGACY_LEVELS,
    LEGACY_METHODOLOGY_DEFINITION,
    LEGACY_ROLES,
    complete_legacy_methodology_definition,
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
def test_legacy_methodology_freezes_roles_and_levels() -> None:
    assert [item["code"] for item in LEGACY_ROLES] == ["linear_employee", "manager", "leader"]
    assert [item["code"] for item in LEGACY_LEVELS] == ["L1", "L2", "L3"]
    assert LEGACY_METHODOLOGY_DEFINITION["methodology_version"] == "1.0"


@pytest.mark.unit
def test_pre_baseline_legacy_definition_is_completed_without_mutating_source() -> None:
    source = {"code": "competencies_4k", "competencies": [{"code": "communication"}]}

    completed = complete_legacy_methodology_definition(source)

    assert "roles" not in source
    assert [item["code"] for item in completed["roles"]] == ["linear_employee", "manager", "leader"]
    assert [item["code"] for item in completed["levels"]] == ["L1", "L2", "L3"]


@pytest.mark.unit
def test_legacy_scenario_is_valid() -> None:
    validate_scenario_definition(LEGACY_SCENARIO_DEFINITION)
