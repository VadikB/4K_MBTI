import pytest

from Api.assessment_configuration import (
    LEGACY_LEVELS,
    LEGACY_METHODOLOGY_DEFINITION,
    LEGACY_ROLES,
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
def test_legacy_scenario_is_valid() -> None:
    validate_scenario_definition(LEGACY_SCENARIO_DEFINITION)


class ReadOnlyConfiguration:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def execute(self, query):
        self.queries.append(query)
        assert query.lstrip().startswith("SELECT")
        assert "FROM assessment_configurations" in query
        return self

    def fetchone(self):
        return self.row


@pytest.fixture
def execution_row():
    from copy import deepcopy
    from tests.unit.test_assessment_authoring import valid_agent_definition

    agents = {}
    profiles = {}
    for item in LEGACY_METHODOLOGY_DEFINITION["competencies"]:
        code = item["code"]
        definition = {**valid_agent_definition(executor_code=item["evaluator"]),
                      "code": code, "version": 1, "competency_code": code}
        agents[code] = {"code": code, "version": 1, "definition": definition,
                        "checksum": definition_checksum(definition)}
        profiles[code] = {"profile": {"agent_code": code, "prompt_version": 1}, "rules": []}
    bundle = {
        "schema_version": 1,
        "interviewer": {code: {"text": "Synthetic fixture", "version": 1}
                        for code in ("case_follow_up", "manual_finish", "timeout_finish")},
        "assessment_agents": profiles, "agent_definitions": agents,
        "case_generation_instructions": [],
    }
    return {"configuration_id": 1, "configuration_code": "fixture",
            "methodology_version_id": 2, "methodology_code": "competencies_4k",
            "methodology_version": 1, "methodology_definition": deepcopy(LEGACY_METHODOLOGY_DEFINITION),
            "scenario_version_id": 3, "scenario_code": "fixture", "scenario_version": 1,
            "scenario_definition": deepcopy(LEGACY_SCENARIO_DEFINITION),
            "prompt_bundle_json": bundle, "prompt_bundle_checksum": definition_checksum(bundle)}


@pytest.mark.unit
def test_complete_configuration_is_read_only_and_preserves_payload(execution_row):
    from Api.assessment_configuration import load_default_execution_configuration
    connection = ReadOnlyConfiguration(execution_row)
    snapshot = load_default_execution_configuration(connection)["snapshot"]
    assert snapshot["prompts"] == execution_row["prompt_bundle_json"]
    assert snapshot["methodology"]["definition"] == execution_row["methodology_definition"]
    assert len(connection.queries) == 1


@pytest.mark.unit
@pytest.mark.parametrize("fault", ["missing", "checksum", "empty", "interviewer", "agent", "agent_checksum"])
def test_incomplete_bundle_rejected_without_active_reads_or_updates(execution_row, fault):
    from Api.assessment_configuration import load_default_execution_configuration
    bundle = execution_row["prompt_bundle_json"]
    if fault == "missing":
        execution_row["prompt_bundle_json"] = None
    elif fault == "checksum":
        execution_row["prompt_bundle_checksum"] = "0" * 64
    else:
        if fault == "empty":
            bundle.clear()
        elif fault == "interviewer":
            del bundle["interviewer"]["manual_finish"]
        elif fault == "agent":
            bundle["agent_definitions"].clear()
        else:
            bundle["agent_definitions"]["communication"]["definition"]["instruction_markdown"] = "Changed"
        execution_row["prompt_bundle_checksum"] = definition_checksum(bundle)
    connection = ReadOnlyConfiguration(execution_row)
    with pytest.raises(ValueError):
        load_default_execution_configuration(connection)
    assert len(connection.queries) == 1


@pytest.mark.unit
@pytest.mark.parametrize("field", ["roles", "levels", "methodology_version"])
def test_missing_methodology_fields_are_not_completed(execution_row, field):
    from Api.assessment_configuration import load_default_execution_configuration, load_default_methodology_roles
    definition = execution_row["methodology_definition"]
    del definition[field]
    with pytest.raises(ValueError, match=field):
        load_default_execution_configuration(ReadOnlyConfiguration(execution_row))
    with pytest.raises(ValueError, match=field):
        load_default_methodology_roles(ReadOnlyConfiguration({"definition_json": definition}))
    assert field not in definition
