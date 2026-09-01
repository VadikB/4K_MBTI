from dataclasses import replace

import pytest
from pydantic import ValidationError

from Api.assessment_configuration import LEGACY_METHODOLOGY_DEFINITION, definition_checksum
from Api.assessment_evaluation_repository import assessment_evaluation_result_repository
from Api.assessment_competency_executor import CompetencyEvaluatorExecutor
from Api.assessment_evaluator_contracts import (
    CompetencyEvaluationInputBuilder,
    LegacyCompetencyEvaluatorAdapter,
)
from Api.communication_agent import (
    BaseCompetencyAgent,
    CommunicationAgent,
    CompetencyCalculation,
    SkillEvaluation,
)
from Api.deepseek_client import deepseek_client
from Api.config import settings
from Api.universal_competency_evaluator import UniversalCompetencyEvaluationError


def snapshot() -> dict:
    agent_definitions = {}
    for competency in LEGACY_METHODOLOGY_DEFINITION["competencies"]:
        code = competency["code"]
        definition = {
            "schema_version": 1,
            "code": code,
            "version": 1,
            "competency_code": code,
            "instruction_markdown": f"Оцени компетенцию {code}.",
            "input_contract": {"code": "competency_evaluation_input", "version": 1},
            "output_contract": {"code": "competency_evaluation_output", "version": 1},
            "executor": {"code": competency["evaluator"], "version": competency["evaluator_version"]},
            "runtime": {"mode": "legacy_adapter"},
        }
        agent_definitions[code] = {
            "id": len(agent_definitions) + 1,
            "code": code,
            "name": code,
            "version": 1,
            "checksum": definition_checksum(definition),
            "definition": definition,
        }
    return {
        "methodology": {
            "code": "competencies_4k",
            "version": 1,
            "definition": LEGACY_METHODOLOGY_DEFINITION,
        },
        "prompts": {"agent_definitions": agent_definitions},
    }


def evaluation() -> SkillEvaluation:
    return SkillEvaluation(
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
        found_evidence=[{"reference": "message:5", "observation": "Уточняет ожидания"}],
        detected_required_blocks=["question"],
        missing_required_blocks=[],
        block_coverage_percent=100,
        rationale="Ответ содержит уточняющий вопрос.",
        evidence_excerpt="Сначала уточню ожидания.",
        source_session_case_ids=[31],
    )


def skill_material(*, session_case_id: int = 31) -> dict:
    return {
        "skill_id": 11,
        "competency_skill_id": 21,
        "skill_code": "active_listening",
        "skill_name": "Активное слушание",
        "competency_name": "Коммуникация",
        "rubric": {
            "L2": {
                "level_name": "Продвинутый",
                "knowledge_text": "Понимает ожидания сторон",
                "skill_text": "Задает уточняющие вопросы",
                "behavior_text": "Проверяет понимание",
            }
        },
        "cases": [
            {
                "session_case_id": session_case_id,
                "case_registry_id": 41,
                "user_text": "Сначала уточню ожидания.",
                "expected_artifact_code": "questions_summary",
                "expected_artifact": "Список вопросов",
                "answer_structure_hint": "Вопросы и резюме",
                "constraints_text": "",
                "clarifying_questions": "",
                "required_response_blocks": [
                    {"block_code": "questions", "block_name": "Уточняющие вопросы"}
                ],
                "methodical_red_flags": [],
                "skill_evidence": [
                    {
                        "related_response_block_code": "questions",
                        "evidence_description": "Уточняет ожидания",
                        "expected_signal": "задает вопросы",
                    }
                ],
                "is_refusal_case": False,
            }
        ],
    }


def universal_input():
    frozen_snapshot = snapshot()
    bundle = frozen_snapshot["prompts"]["agent_definitions"]["communication"]
    definition = bundle["definition"]
    definition["runtime"] = {
        "mode": "universal_llm",
        "model_profile": "assessment_strict",
        "temperature": 0,
        "max_attempts": 2,
        "timeout_seconds": 30,
        "max_output_tokens": 1200,
        "fallback": "fail",
    }
    bundle["checksum"] = definition_checksum(definition)

    class MaterialProvider:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, [skill_material()]

    return CompetencyEvaluationInputBuilder().build(
        snapshot=frozen_snapshot,
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
        connection=object(),
        agent=MaterialProvider(),
    )


def universal_output_payload(*, source_case_id: int = 31) -> dict:
    return {
        "contract_version": 1,
        "competency_code": "communication",
        "component_code": "evaluation.communication",
        "component_version": 1,
        "status": "evaluated",
        "assessments": [
            {
                "skill_id": 11,
                "competency_skill_id": 21,
                "skill_code": "active_listening",
                "skill_name": "Активное слушание",
                "competency_name": "Коммуникация",
                "level_code": "L1",
                "level_name": "Базовый",
                "rubric_match_scores": {"L1": 1, "L2": 0, "L3": 0},
                "structural_elements": {"has_questions": True},
                "red_flags": [],
                "found_evidence": [{"reference": "case:31", "observation": "Уточняет ожидания"}],
                "detected_required_blocks": ["questions"],
                "missing_required_blocks": [],
                "block_coverage_percent": 100,
                "rationale": "Есть базовое проявление навыка.",
                "evidence_excerpt": "Сначала уточню ожидания.",
                "source_session_case_ids": [source_case_id],
            }
        ],
        "case_analyses": [],
    }


@pytest.mark.unit
def test_input_builder_uses_frozen_methodology_identity() -> None:
    competency = LEGACY_METHODOLOGY_DEFINITION["competencies"][0]

    result = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=competency,
    )

    assert result.contract_version == 1
    assert result.methodology_code == "competencies_4k"
    assert result.methodology_version == 1
    assert result.competency_code == "communication"
    assert result.component_code == "evaluation.communication"
    assert result.component_version == 1
    assert result.agent_definition.code == "communication"
    assert result.agent_definition.instruction_markdown == "Оцени компетенцию communication."


@pytest.mark.unit
def test_input_builder_rejects_tampered_frozen_agent_definition() -> None:
    invalid_snapshot = snapshot()
    invalid_snapshot["prompts"]["agent_definitions"]["communication"]["definition"][
        "instruction_markdown"
    ] = "Подменённая инструкция"

    with pytest.raises(ValueError, match="checksum mismatch"):
        CompetencyEvaluationInputBuilder().build(
            snapshot=invalid_snapshot,
            session_id=42,
            user_id=7,
            competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
        )


@pytest.mark.unit
def test_executor_routes_only_by_exact_component_identity() -> None:
    class Strategy:
        agent_code = "communication"

    executor = CompetencyEvaluatorExecutor([Strategy()])

    assert executor.resolve_component("evaluation.communication", 1).agent_code == "communication"
    with pytest.raises(RuntimeError, match="evaluation.teamwork v1"):
        executor.resolve_component("evaluation.teamwork", 1)


@pytest.mark.unit
def test_universal_executor_is_blocked_by_kill_switch(monkeypatch) -> None:
    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", False)

    with pytest.raises(RuntimeError, match="disabled"):
        CompetencyEvaluatorExecutor([]).execute(connection=object(), input_data=universal_input())


@pytest.mark.unit
def test_universal_executor_uses_frozen_markdown_and_validates_output(monkeypatch) -> None:
    calls: list[tuple[list[dict[str, str]], float, int]] = []

    class Gateway:
        def chat(self, messages, *, temperature, timeout_seconds, max_tokens=None, routing_key=None):
            calls.append((messages, temperature, timeout_seconds))
            return __import__("json").dumps(universal_output_payload(), ensure_ascii=False)

    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", True)
    input_data = universal_input()
    output = CompetencyEvaluatorExecutor([], llm_gateway=Gateway()).execute(
        connection=object(),
        input_data=input_data,
    )

    assert output.assessments[0].skill_id == 11
    assert input_data.agent_definition.instruction_markdown in calls[0][0][0]["content"]
    assert calls[0][1:] == (0.0, 30)


@pytest.mark.unit
def test_universal_executor_retries_invalid_json_without_legacy_fallback(monkeypatch) -> None:
    responses = iter(["not-json", __import__("json").dumps(universal_output_payload())])

    class Gateway:
        calls = 0

        def chat(self, *_args, **_kwargs):
            self.calls += 1
            return next(responses)

    gateway = Gateway()
    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", True)
    output = CompetencyEvaluatorExecutor([], llm_gateway=gateway).execute(
        connection=object(),
        input_data=universal_input(),
    )

    assert output.status == "evaluated"
    assert gateway.calls == 2


@pytest.mark.unit
def test_universal_executor_rejects_case_reference_outside_input(monkeypatch) -> None:
    class Gateway:
        def chat(self, *_args, **_kwargs):
            return __import__("json").dumps(universal_output_payload(source_case_id=999))

    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", True)
    with pytest.raises(UniversalCompetencyEvaluationError, match="2 attempt"):
        CompetencyEvaluatorExecutor([], llm_gateway=Gateway()).execute(
            connection=object(),
            input_data=universal_input(),
        )


@pytest.mark.unit
def test_frozen_markdown_is_consumed_by_semantic_prompt(monkeypatch) -> None:
    input_data = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
    )
    captured: list[list[dict[str, str]]] = []
    monkeypatch.setattr(deepseek_client, "api_keys", ["test-key"])
    monkeypatch.setattr(
        deepseek_client,
        "chat",
        lambda messages, **_kwargs: captured.append(messages) or '{"scores":{"L1":1,"L2":0,"L3":0}}',
    )
    agent = CommunicationAgent()
    prompt_config = input_data.agent_prompt_config.model_dump()
    prompt_config["definition_instruction_markdown"] = input_data.agent_definition.instruction_markdown

    scores = agent._score_against_rubric(
        "Я уточняю ожидания сторон.",
        skill_material()["rubric"],
        skill_name="Активное слушание",
        agent_prompt_config=prompt_config,
    )

    assert scores == {"L1": 1, "L2": 0, "L3": 0}
    assert "Оцени компетенцию communication." in captured[0][0]["content"]


@pytest.mark.unit
def test_legacy_adapter_normalizes_existing_skill_evaluation() -> None:
    recorded: list[tuple[int, int]] = []

    class Agent:
        def evaluate_session(self, *, connection, session_id: int, user_id: int):
            recorded.append((session_id, user_id))
            return [evaluation()]

    input_data = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
    )
    output = LegacyCompetencyEvaluatorAdapter(Agent()).evaluate(
        connection=object(),
        input_data=input_data,
    )

    assert recorded == [(42, 7)]
    assert output.status == "evaluated"
    assert output.assessments[0].skill_code == "active_listening"
    assert output.assessments[0].level_code == "L2"


@pytest.mark.unit
def test_legacy_adapter_rejects_result_outside_contract() -> None:
    class Agent:
        def evaluate_session(self, **_kwargs):
            return [replace(evaluation(), level_code="unexpected")]

    input_data = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
    )

    with pytest.raises(ValidationError):
        LegacyCompetencyEvaluatorAdapter(Agent()).evaluate(
            connection=object(),
            input_data=input_data,
        )


@pytest.mark.unit
def test_input_builder_rejects_unversioned_methodology_snapshot() -> None:
    invalid_snapshot = snapshot()
    invalid_snapshot["methodology"]["version"] = 0

    with pytest.raises(ValidationError):
        CompetencyEvaluationInputBuilder().build(
            snapshot=invalid_snapshot,
            session_id=42,
            user_id=7,
            competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
        )


@pytest.mark.unit
def test_input_builder_loads_and_validates_self_contained_material() -> None:
    class Agent:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, [skill_material()]

    result = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
        connection=object(),
        agent=Agent(),
    )

    assert result.skills[0].skill_code == "active_listening"
    assert result.skills[0].rubric["L2"].level_name == "Продвинутый"
    assert result.skills[0].cases[0].user_text == "Сначала уточню ожидания."


@pytest.mark.unit
def test_input_builder_rejects_invalid_nested_evidence() -> None:
    class Agent:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, [skill_material(session_case_id=0)]

    with pytest.raises(ValidationError):
        CompetencyEvaluationInputBuilder().build(
            snapshot=snapshot(),
            session_id=42,
            user_id=7,
            competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
            connection=object(),
            agent=Agent(),
        )


@pytest.mark.unit
def test_legacy_adapter_prefers_contract_aware_evaluator() -> None:
    calls: list[str] = []

    class Agent:
        def evaluate_contract(self, *, connection, input_data):
            calls.append(input_data.skills[0].skill_code)
            return CompetencyCalculation(assessments=[], case_analyses=[])

        def evaluate_session(self, **_kwargs):
            raise AssertionError("contract-aware evaluator must not use the legacy facade")

    class MaterialAgent(Agent):
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, [skill_material()]

    agent = MaterialAgent()
    input_data = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
        connection=object(),
        agent=agent,
    )
    output = LegacyCompetencyEvaluatorAdapter(agent).evaluate(
        connection=object(),
        input_data=input_data,
    )

    assert calls == ["active_listening"]
    assert output.status == "no_assessments"


@pytest.mark.unit
def test_real_agent_contract_path_calculates_from_supplied_material() -> None:
    received: list[tuple[int, str]] = []

    class Agent(BaseCompetencyAgent):
        def __init__(self) -> None:
            super().__init__("Коммуникация", "communication")

        def _evaluate_materials(self, **kwargs):
            received.append((kwargs["session_id"], kwargs["skills"][0]["skill_code"]))
            return CompetencyCalculation(assessments=[], case_analyses=[])

        def _load_session_skills(self, *_args, **_kwargs):
            raise AssertionError("contract calculation must not reload skills")

    class MaterialProvider:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, [skill_material()]

    agent = Agent()
    input_data = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
        connection=object(),
        agent=MaterialProvider(),
    )

    agent.evaluate_contract(connection=object(), input_data=input_data)

    assert received == [(42, "active_listening")]


@pytest.mark.unit
def test_legacy_facade_keeps_empty_session_short_circuit() -> None:
    class Agent(BaseCompetencyAgent):
        def __init__(self) -> None:
            super().__init__("Коммуникация", "communication")

        def _load_session_skills(self, *_args, **_kwargs):
            return []

    class Connection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("empty session must not load snapshot or prompts")

    assert Agent().evaluate_session(connection=Connection(), session_id=42, user_id=7) == []


@pytest.mark.unit
def test_real_contract_calculation_does_not_write_to_database() -> None:
    material = skill_material()
    material["cases"] = []

    class MaterialProvider:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, [material]

    class NoWritesConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("contract calculation must not execute SQL")

    input_data = CompetencyEvaluationInputBuilder().build(
        snapshot=snapshot(),
        session_id=42,
        user_id=7,
        competency=LEGACY_METHODOLOGY_DEFINITION["competencies"][0],
        connection=object(),
        agent=MaterialProvider(),
    )

    calculation = CommunicationAgent().evaluate_contract(
        connection=NoWritesConnection(),
        input_data=input_data,
    )

    assert calculation.assessments[0].level_code == "N/A"
    assert calculation.case_analyses == []


@pytest.mark.unit
def test_legacy_facade_delegates_persistence_to_repository(monkeypatch) -> None:
    material = skill_material()
    material["cases"] = []
    saved: list[tuple[int, str]] = []

    class Agent(CommunicationAgent):
        def _load_session_skills(self, *_args, **_kwargs):
            return [material]

        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, [material]

    class Cursor:
        def fetchone(self):
            return {"execution_snapshot_json": snapshot()}

    class Connection:
        def execute(self, *_args, **_kwargs):
            return Cursor()

    monkeypatch.setattr(
        assessment_evaluation_result_repository,
        "save",
        lambda *, connection, input_data, output: saved.append(
            (input_data.session_id, output.assessments[0].level_code)
        ),
    )

    evaluations = Agent().evaluate_session(connection=Connection(), session_id=42, user_id=7)

    assert evaluations[0].level_code == "N/A"
    assert saved == [(42, "N/A")]
