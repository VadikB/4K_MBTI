import pytest

from Api.assessment_configuration import definition_checksum
from Api.assessment_indicator_material_repository import (
    AssessmentIndicatorMaterialRepository,
    CompetencyIndicatorEvaluationInputBuilder,
)


def competency() -> dict:
    return {
        "id": "K1",
        "skills": [{"id": "K1.1", "name": "Ориентация", "components": [{
            "id": "K1.C01", "name": "Ситуация", "indicators": [{
                "id": "K1.I01", "name": "Цели", "function": "Выявлять цели.",
                "product": "Карта целей.", "levels": {key: key for key in ("L0", "L1", "L2", "L3")},
                "boundary": "Граница.", "evidence_pattern": "Работа с целями.",
                "red_flags": [{"code": "RF-K1.I01-01", "description": "Подмена цели."}],
            }],
        }]}],
    }


class MaterialConnection:
    def __init__(self):
        self.scope = None

    def execute(self, statement, params):
        normalized = " ".join(statement.split())
        if "FROM session_case_indicators" in normalized:
            self.scope = params
            rows = [{
                "indicator_code": "K1.I01", "session_case_id": 31, "case_registry_id": 41,
                "expected_artifact_code": "map", "expected_artifact": "Карта",
                "answer_structure_hint": "Структура", "constraints_text": "Ограничения",
                "required_blocks_version": 1, "red_flags_version": 1,
            }]
        elif "FROM session_case_messages" in normalized:
            rows = [{"message_text": "Сначала уточню цели."}]
        elif "FROM cases_registry cr" in normalized:
            rows = [{
                "block_code": "goals", "block_name": "Цели", "flag_code": None,
                "flag_name": None, "flag_description": None,
                "related_response_block_code": "goals", "evidence_description": "Уточняет цели",
                "expected_signal": "задаёт вопрос",
            }]
        else:
            raise AssertionError(normalized)

        class Result:
            def fetchall(self):
                return rows

        return Result()


@pytest.mark.unit
def test_indicator_material_loader_combines_frozen_definition_with_session_cases() -> None:
    connection = MaterialConnection()
    result = AssessmentIndicatorMaterialRepository().load(
        connection, session_id=42, methodology_version_id=2, competency=competency(),
    )

    indicator = result[0]["components"][0]["indicators"][0]
    assert connection.scope == (42, 2, ["K1.I01"])
    assert indicator["levels"]["L0"] == {"descriptor": "L0"}
    assert indicator["cases"][0]["indicator_evidence"][0]["expected_signal"] == "задаёт вопрос"


@pytest.mark.unit
def test_indicator_material_loader_rejects_empty_frozen_scope_before_sql() -> None:
    with pytest.raises(ValueError, match="non-empty unique"):
        AssessmentIndicatorMaterialRepository().load(
            MaterialConnection(), session_id=42, methodology_version_id=2,
            competency={"id": "K1", "skills": []},
        )


@pytest.mark.unit
def test_v2_builder_uses_frozen_methodology_identity() -> None:
    class Repository:
        def load(self, _connection, **kwargs):
            assert kwargs["methodology_version_id"] == 2
            return AssessmentIndicatorMaterialRepository()._normalize_competency(competency())[0]

    snapshot = {"methodology": {
        "id": 2, "code": "competencies_4k", "version": 2,
        "definition": {"methodology_version": "1.1", "competencies": [competency()]},
    }}
    result = CompetencyIndicatorEvaluationInputBuilder(Repository()).build(
        connection=object(), snapshot=snapshot, session_id=42, user_id=7,
        competency_code="K1", component_code="evaluation.communication", component_version=2,
        agent_definition={
            "code": "communication_1_1", "name": "Communication", "version": 2,
            "checksum": "checksum", "instruction_markdown": "Evaluate.",
            "input_contract": {"code": "competency_evaluation_input", "version": 2},
            "output_contract": {"code": "competency_evaluation_output", "version": 2},
            "executor": {"code": "evaluation.communication", "version": 2},
            "runtime": {
                "mode": "universal_llm", "model_profile": "assessment_strict",
                "temperature": 0, "max_attempts": 1, "timeout_seconds": 30,
                "max_output_tokens": 1200, "fallback": "fail",
            },
        },
    )

    assert result.contract_version == 2
    assert result.methodology_version_id == 2
    assert result.methodology_version == "1.1"


@pytest.mark.unit
def test_v2_builder_resolves_only_matching_frozen_agent() -> None:
    definition = {
        "instruction_markdown": "Evaluate indicators.",
        "input_contract": {"code": "competency_evaluation_input", "version": 2},
        "output_contract": {"code": "competency_evaluation_output", "version": 2},
        "executor": {"code": "evaluation.communication", "version": 2},
        "runtime": {
            "mode": "universal_llm", "model_profile": "assessment_strict", "temperature": 0,
            "max_attempts": 1, "timeout_seconds": 30, "max_output_tokens": 1200, "fallback": "fail",
        },
    }
    snapshot = {"prompts": {"agent_definitions": {"indicator_communication": {
        "id": 9, "code": "indicator_communication", "name": "Communication", "version": 1,
        "checksum": definition_checksum(definition), "definition": definition,
    }}}}
    resolved = CompetencyIndicatorEvaluationInputBuilder().resolve_agent_definition(
        snapshot=snapshot,
        competency={"agent_definition": {"code": "indicator_communication", "version": 1}},
        component_code="evaluation.communication",
        component_version=2,
    )
    assert resolved["input_contract"]["version"] == 2
    assert resolved["executor"] == {"code": "evaluation.communication", "version": 2}

    snapshot["prompts"]["agent_definitions"]["indicator_communication"]["checksum"] = "changed"
    with pytest.raises(ValueError, match="checksum mismatch"):
        CompetencyIndicatorEvaluationInputBuilder().resolve_agent_definition(
            snapshot=snapshot,
            competency={"agent_definition": {"code": "indicator_communication", "version": 1}},
            component_code="evaluation.communication",
            component_version=2,
        )
