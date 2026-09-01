from __future__ import annotations

import pytest

from Api.assessment_competency_executor import CompetencyEvaluatorExecutor
from Api.assessment_evaluator_contracts import CompetencyEvaluationInput
from Api.config import settings
from Api.llm.deepseek_gateway import DeepSeekGateway


@pytest.mark.llm
def test_universal_competency_evaluator_real_provider_smoke(monkeypatch) -> None:
    """One synthetic case; at most two calls and 1200 output tokens per call."""

    if not settings.deepseek_api_keys:
        pytest.skip("DeepSeek credentials are not configured in the local environment.")
    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", True)
    input_data = CompetencyEvaluationInput(
        session_id=900001,
        user_id=900001,
        methodology_code="synthetic_universal_smoke",
        methodology_version=1,
        competency_code="communication",
        component_code="evaluation.communication",
        component_version=1,
        agent_definition={
            "code": "communication_smoke",
            "name": "Synthetic communication smoke",
            "version": 1,
            "checksum": "synthetic-smoke-only",
            "instruction_markdown": (
                "Оцени навык только по наблюдаемым свидетельствам. "
                "L1 означает наличие базового уточнения ожиданий; не завышай уровень."
            ),
            "input_contract": {"code": "competency_evaluation_input", "version": 1},
            "output_contract": {"code": "competency_evaluation_output", "version": 1},
            "executor": {"code": "evaluation.communication", "version": 1},
            "runtime": {
                "mode": "universal_llm",
                "model_profile": "assessment_strict",
                "temperature": 0,
                "max_attempts": 2,
                "timeout_seconds": 45,
                "max_output_tokens": 1200,
                "fallback": "fail",
            },
        },
        agent_prompt_config={"profile": {}, "rules": []},
        skills=[
            {
                "skill_id": 900011,
                "competency_skill_id": 900021,
                "skill_code": "expectation_clarification",
                "skill_name": "Уточнение ожиданий",
                "competency_name": "Коммуникация",
                "rubric": {
                    "L1": {
                        "level_name": "Базовый",
                        "knowledge_text": "Понимает необходимость уточнить ожидания.",
                        "skill_text": "Задает один релевантный уточняющий вопрос.",
                        "behavior_text": "Не делает вывод до уточнения.",
                    },
                    "L2": {
                        "level_name": "Продвинутый",
                        "knowledge_text": "Различает ожидания нескольких сторон.",
                        "skill_text": "Системно проверяет понимание и ограничения.",
                        "behavior_text": "Фиксирует согласованное понимание.",
                    },
                    "L3": {
                        "level_name": "Системный",
                        "knowledge_text": "Выстраивает систему коммуникации.",
                        "skill_text": "Проектирует устойчивый контур согласования.",
                        "behavior_text": "Предотвращает повторные разрывы ожиданий.",
                    },
                },
                "cases": [
                    {
                        "session_case_id": 900031,
                        "case_registry_id": None,
                        "user_text": "Сначала уточню у заказчика, какой результат он ожидает и к какому сроку.",
                        "expected_artifact_code": "clarifying_question",
                        "expected_artifact": "Релевантный уточняющий вопрос",
                        "answer_structure_hint": "Вопрос об ожидаемом результате и сроке",
                        "constraints_text": "Не придумывать отсутствующий контекст",
                        "clarifying_questions": "Какой результат ожидается? К какому сроку?",
                        "required_response_blocks": [
                            {"block_code": "questions", "block_name": "Уточняющие вопросы"}
                        ],
                        "methodical_red_flags": [],
                        "skill_evidence": [
                            {
                                "related_response_block_code": "questions",
                                "evidence_description": "Уточняет результат и срок",
                                "expected_signal": "задает конкретные вопросы",
                            }
                        ],
                        "is_refusal_case": False,
                    }
                ],
            }
        ],
    )

    output = CompetencyEvaluatorExecutor([], llm_gateway=DeepSeekGateway()).execute(
        connection=object(),
        input_data=input_data,
    )

    assert output.status == "evaluated"
    assert output.assessments[0].skill_id == 900011
    assert output.assessments[0].source_session_case_ids == [900031]
    assert output.assessments[0].level_code in {"L1", "L2"}
