import pytest
from pydantic import ValidationError

from Api.assessment_evaluator_contracts import (
    CompetencyIndicatorEvaluationInput,
    CompetencyIndicatorEvaluationOutput,
    IndicatorAssessmentOutput,
)
from Api.assessment_indicator_repository import AssessmentIndicatorResultRepository


def input_data() -> CompetencyIndicatorEvaluationInput:
    return CompetencyIndicatorEvaluationInput(
        session_id=42,
        user_id=7,
        methodology_code="competencies_4k",
        methodology_version_id=2,
        methodology_version="1.1",
        competency_code="K1",
        component_code="evaluation.communication",
        component_version=2,
        agent_definition={
            "code": "communication_1_1",
            "name": "Коммуникация 1.1",
            "version": 2,
            "checksum": "checksum",
            "instruction_markdown": "Оценить индикаторы.",
            "input_contract": {"code": "competency_evaluation_input", "version": 2},
            "output_contract": {"code": "competency_evaluation_output", "version": 2},
            "executor": {"code": "evaluation.communication", "version": 2},
            "runtime": {
                "mode": "universal_llm", "model_profile": "assessment_strict",
                "temperature": 0, "max_attempts": 1, "timeout_seconds": 30,
                "max_output_tokens": 1200, "fallback": "fail",
            },
        },
        skills=[{
            "skill_code": "K1.1",
            "skill_name": "Ориентация",
            "components": [{
                "component_code": "K1.C01",
                "component_name": "Ситуация",
                "indicators": [{
                    "indicator_code": "K1.I01",
                    "indicator_name": "Цели и позиции",
                    "function": "Выявлять цели.",
                    "product": "Рабочая карта.",
                    "levels": {code: {"descriptor": code} for code in ("L0", "L1", "L2", "L3")},
                    "boundary": "Граница с K1.I02.",
                    "evidence_pattern": "Наблюдаемая работа с целями.",
                    "red_flags": [{"code": "RF-K1.I01-01", "description": "Критичный паттерн."}],
                    "cases": [{
                        "session_case_id": 31,
                        "case_registry_id": 41,
                        "user_text": "Уточню цели.",
                        "expected_artifact_code": "map",
                        "expected_artifact": "Карта",
                        "answer_structure_hint": "",
                        "constraints_text": "",
                        "required_response_blocks": [],
                        "methodical_red_flags": [],
                        "indicator_evidence": [],
                        "is_refusal_case": False,
                    }],
                }],
            }],
        }],
    )


def output(*, case_id: int = 31, indicator_code: str = "K1.I01") -> CompetencyIndicatorEvaluationOutput:
    return CompetencyIndicatorEvaluationOutput(
        competency_code="K1",
        component_code="evaluation.communication",
        component_version=2,
        status="evaluated",
        indicator_assessments=[{
            "indicator_code": indicator_code,
            "evidence_state": "observed",
            "level_code": "L0",
            "evidence": [{"session_case_id": case_id, "observation": "Цели смешаны.", "excerpt": "Наша цель одна."}],
            "red_flag_codes": [],
            "rationale": "Наблюдаемое действие неработоспособно.",
            "confidence": 0.8,
        }],
    )


class Result:
    def fetchone(self):
        return {"id": 101}


class RecordingConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((" ".join(statement.split()), params))
        return Result()


@pytest.mark.unit
def test_contract_distinguishes_l0_from_missing_evidence() -> None:
    assert output().indicator_assessments[0].level_code == "L0"
    missing = IndicatorAssessmentOutput(
        indicator_code="K1.I01",
        evidence_state="insufficient_evidence",
        level_code=None,
        evidence=[],
        red_flag_codes=[],
        rationale="Недостаточно наблюдений.",
    )
    assert missing.level_code is None
    with pytest.raises(ValidationError, match="Observed indicator requires"):
        IndicatorAssessmentOutput(
            indicator_code="K1.I01", evidence_state="observed", level_code="L0",
            evidence=[], red_flag_codes=[], rationale="Нет evidence.",
        )


@pytest.mark.unit
def test_contract_rejects_cross_competency_hierarchy() -> None:
    payload = input_data().model_dump()
    payload["skills"][0]["components"][0]["indicators"][0]["indicator_code"] = "K2.I01"
    with pytest.raises(ValidationError, match="does not belong"):
        CompetencyIndicatorEvaluationInput.model_validate(payload)


@pytest.mark.unit
def test_contract_rejects_output_status_without_assessments() -> None:
    with pytest.raises(ValidationError, match="status does not match"):
        CompetencyIndicatorEvaluationOutput(
            competency_code="K1",
            component_code="evaluation.communication",
            component_version=2,
            status="evaluated",
            indicator_assessments=[],
        )


@pytest.mark.unit
def test_repository_upserts_assessment_and_replaces_evidence() -> None:
    connection = RecordingConnection()
    AssessmentIndicatorResultRepository().save(connection=connection, input_data=input_data(), output=output())

    assert len(connection.calls) == 3
    assert "INSERT INTO session_indicator_assessments" in connection.calls[0][0]
    assert "ON CONFLICT (session_id, methodology_version_id, indicator_code)" in connection.calls[0][0]
    assert "DELETE FROM session_case_indicator_evidence" in connection.calls[1][0]
    assert "INSERT INTO session_case_indicator_evidence" in connection.calls[2][0]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("invalid_output", "message"),
    [(output(case_id=999), "case outside"), (output(indicator_code="K1.I99"), "indicator outside")],
)
def test_repository_rejects_references_outside_input(invalid_output, message) -> None:
    connection = RecordingConnection()
    with pytest.raises(ValueError, match=message):
        AssessmentIndicatorResultRepository().save(
            connection=connection, input_data=input_data(), output=invalid_output,
        )
    assert connection.calls == []
