from __future__ import annotations

import pytest

from Api.assessment_evaluation_material_repository import AssessmentEvaluationMaterialRepository
from Api.assessment_evaluator_contracts import SkillEvaluationInput


class MaterialConnection:
    def __init__(self) -> None:
        self.skill_params = None

    def execute(self, statement: str, params=None):
        normalized = " ".join(statement.split())
        if "FROM session_case_skills" in normalized and "s.skill_code = ANY" in normalized:
            self.skill_params = params
            rows = [
                {
                    "skill_id": 11,
                    "skill_code": "active_listening",
                    "skill_name": "Активное слушание",
                    "competency_name": "Коммуникация",
                    "competency_skill_id": 21,
                }
            ]
        elif "FROM competency_skill_criteria" in normalized:
            rows = [
                {
                    "level_code": "L1", "level_name": "Базовый",
                    "knowledge_text": "Понимает ожидания", "skill_text": "Уточняет",
                    "behavior_text": "Не предполагает",
                }
            ]
        elif "FROM session_cases sc" in normalized:
            rows = [
                {
                    "session_case_id": 31, "case_registry_id": 41,
                    "expected_artifact_code": "questions", "expected_artifact": "Вопросы",
                    "answer_structure_hint": "Уточнить", "constraints_text": "",
                    "clarifying_questions": "",
                }
            ]
        elif "FROM session_case_messages" in normalized:
            rows = [{"message_text": "Сначала уточню ожидаемый результат."}]
        elif "FROM cases_registry cr" in normalized:
            rows = [
                {
                    "block_code": "questions", "block_name": "Вопросы",
                    "flag_code": None, "flag_name": None, "flag_description": None,
                    "evidence_description": "Уточняет ожидания", "expected_signal": "задает вопрос",
                }
            ]
        else:  # pragma: no cover - makes an unexpected query explicit
            raise AssertionError(normalized)

        class Result:
            def fetchall(self):
                return rows

        return Result()


@pytest.mark.unit
def test_material_repository_restricts_query_and_builds_contract_input() -> None:
    connection = MaterialConnection()

    materials = AssessmentEvaluationMaterialRepository().load(
        connection,
        session_id=42,
        skill_codes=["active_listening", "active_listening", ""],
    )

    validated = SkillEvaluationInput.model_validate(materials[0])
    assert connection.skill_params == (42, ["active_listening"])
    assert validated.skill_code == "active_listening"
    assert validated.rubric["L1"].level_name == "Базовый"
    assert validated.cases[0].required_response_blocks[0].block_code == "questions"


@pytest.mark.unit
def test_material_repository_rejects_empty_skill_scope_before_sql() -> None:
    with pytest.raises(ValueError, match="skill_codes"):
        AssessmentEvaluationMaterialRepository().load(
            MaterialConnection(),
            session_id=42,
            skill_codes=[],
        )
