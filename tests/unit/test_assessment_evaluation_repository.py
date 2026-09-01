import pytest

from Api.assessment_evaluation_repository import AssessmentEvaluationResultRepository
from Api.assessment_evaluator_contracts import (
    CaseSkillAnalysisOutput,
    CompetencyEvaluationInput,
    CompetencyEvaluationOutput,
    SkillEvaluationOutput,
)


def input_data() -> CompetencyEvaluationInput:
    return CompetencyEvaluationInput(
        session_id=42,
        user_id=7,
        methodology_code="competencies_4k",
        methodology_version=1,
        competency_code="communication",
        component_code="evaluation.communication",
        component_version=1,
        agent_definition={
            "code": "communication",
            "name": "Коммуникация",
            "version": 1,
            "checksum": "test-checksum",
            "instruction_markdown": "Оцени коммуникацию.",
            "input_contract": {"code": "competency_evaluation_input", "version": 1},
            "output_contract": {"code": "competency_evaluation_output", "version": 1},
            "executor": {"code": "evaluation.communication", "version": 1},
            "runtime": {"mode": "legacy_adapter"},
        },
        agent_prompt_config={"profile": {}, "rules": []},
        skills=[
            {
                "skill_id": 11,
                "competency_skill_id": 21,
                "skill_code": "active_listening",
                "skill_name": "Активное слушание",
                "competency_name": "Коммуникация",
                "rubric": {},
                "cases": [
                    {
                        "session_case_id": 31,
                        "case_registry_id": 41,
                        "user_text": "Уточню ожидания.",
                        "expected_artifact_code": "questions_summary",
                        "expected_artifact": "Список вопросов",
                        "answer_structure_hint": "",
                        "constraints_text": "",
                        "clarifying_questions": "",
                        "required_response_blocks": [],
                        "methodical_red_flags": [],
                        "skill_evidence": [],
                        "is_refusal_case": False,
                    }
                ],
            }
        ],
    )


def assessment(*, source_case_id: int = 31) -> SkillEvaluationOutput:
    return SkillEvaluationOutput(
        skill_id=11,
        competency_skill_id=21,
        skill_code="active_listening",
        skill_name="Активное слушание",
        competency_name="Коммуникация",
        level_code="L2",
        level_name="Продвинутый",
        rubric_match_scores={"L1": 1, "L2": 1, "L3": 0},
        structural_elements={"has_questions": True},
        red_flags=[],
        found_evidence=[],
        detected_required_blocks=[],
        missing_required_blocks=[],
        block_coverage_percent=100,
        rationale="Есть уточнение.",
        evidence_excerpt="Уточню ожидания.",
        source_session_case_ids=[source_case_id],
    )


def case_analysis() -> CaseSkillAnalysisOutput:
    return CaseSkillAnalysisOutput(
        session_case_id=31,
        case_registry_id=41,
        skill_id=11,
        competency_name="Коммуникация",
        expected_artifact_code="questions_summary",
        expected_artifact_name="Список вопросов",
        detected_artifact_parts=["Уточняющие вопросы"],
        missing_artifact_parts=[],
        artifact_compliance_percent=100,
        structural_elements={"has_questions": True},
        detected_required_blocks=["Уточняющие вопросы"],
        missing_required_blocks=[],
        block_coverage_percent=100,
        red_flags=[],
        found_evidence=[],
        detected_signals=["has_questions"],
        evidence_excerpt="Уточню ожидания.",
        source_message_count=1,
    )


def output(*, source_case_id: int = 31) -> CompetencyEvaluationOutput:
    return CompetencyEvaluationOutput(
        competency_code="communication",
        component_code="evaluation.communication",
        component_version=1,
        status="evaluated",
        assessments=[assessment(source_case_id=source_case_id)],
        case_analyses=[case_analysis()],
    )


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, statement: str, params: tuple) -> None:
        self.calls.append((" ".join(statement.split()), params))


@pytest.mark.unit
def test_repository_persists_both_validated_output_collections() -> None:
    connection = RecordingConnection()

    AssessmentEvaluationResultRepository().save(
        connection=connection,
        input_data=input_data(),
        output=output(),
    )

    assert len(connection.calls) == 2
    case_statement, case_params = connection.calls[0]
    assessment_statement, assessment_params = connection.calls[1]
    assert "INSERT INTO session_case_skill_analysis" in case_statement
    assert "ON CONFLICT (session_case_id, skill_id)" in case_statement
    assert case_params[:6] == (42, 7, 31, 41, 11, "Коммуникация")
    assert "INSERT INTO session_skill_assessments" in assessment_statement
    assert "ON CONFLICT (session_id, skill_id)" in assessment_statement
    assert assessment_params[:5] == (42, 7, 11, 21, "Коммуникация")


@pytest.mark.unit
def test_repository_rejects_references_outside_input_before_writing() -> None:
    connection = RecordingConnection()

    with pytest.raises(ValueError, match="case outside"):
        AssessmentEvaluationResultRepository().save(
            connection=connection,
            input_data=input_data(),
            output=output(source_case_id=999),
        )

    assert connection.calls == []
