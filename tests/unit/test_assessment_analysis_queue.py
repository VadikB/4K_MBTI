from contextlib import contextmanager

import pytest

from Api import assessment_analysis_queue as queue_module
from Api.assessment_analysis_queue import AssessmentAnalysisJob, AssessmentAnalysisQueue
from Api.assessment_configuration import LEGACY_METHODOLOGY_DEFINITION, LEGACY_SCENARIO_DEFINITION, definition_checksum
from Api.assessment_evaluator_contracts import CompetencyEvaluationOutput
from Api.assessment_runtime import ScenarioExecutionContext


def frozen_agent_definitions() -> dict:
    result = {}
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
            "executor": {"code": competency["evaluator"], "version": 1},
            "runtime": {"mode": "legacy_adapter"},
        }
        result[code] = {
            "id": len(result) + 1, "code": code, "name": code, "version": 1,
            "checksum": definition_checksum(definition), "definition": definition,
        }
    return result


class Cursor:
    rowcount = 1

    def __init__(self, statement: str = "") -> None:
        self.statement = statement

    def fetchone(self):
        if "execution_snapshot_json" in self.statement:
            return {
                "execution_snapshot_json": {
                    "methodology": {
                        "code": "competencies_4k",
                        "version": 1,
                        "definition": LEGACY_METHODOLOGY_DEFINITION,
                    },
                    "scenario": {"definition": LEGACY_SCENARIO_DEFINITION},
                    "prompts": {"agent_definitions": frozen_agent_definitions()},
                }
            }
        return {"id": 77}


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.commits = 0

    def execute(self, statement: str, _params=None):
        self.statements.append(" ".join(statement.split()))
        return Cursor(statement)

    def commit(self) -> None:
        self.commits += 1


def analysis_job(*, attempts: int = 1, max_attempts: int = 3) -> AssessmentAnalysisJob:
    return AssessmentAnalysisJob(
        id=9,
        operation_id="analysis-9",
        session_id=42,
        user_id=7,
        attempts=attempts,
        max_attempts=max_attempts,
        worker_id="worker",
    )


@pytest.mark.unit
def test_analysis_job_completes_report(monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    connection = RecordingConnection()
    evaluated: list[tuple[int, int]] = []

    class Agent:
        def __init__(self, agent_code: str):
            self.agent_code = agent_code

        def evaluate_session(self, *, connection, session_id: int, user_id: int):
            evaluated.append((session_id, user_id))
            return []

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(queue_module, "get_connection", fake_connection)
    monkeypatch.setattr(
        queue_module,
        "competency_assessment_agents",
        [Agent(item["code"]) for item in LEGACY_METHODOLOGY_DEFINITION["competencies"]],
    )
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)

    queue._process(analysis_job())

    assert evaluated == [(42, 7)] * 4
    assert any("SET status = 'completed'" in statement for statement in connection.statements)
    assert any("progress_percent = 100" in statement for statement in connection.statements)


@pytest.mark.unit
def test_transient_analysis_failure_is_retried(monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    connection = RecordingConnection()
    failures: list[tuple[str, bool]] = []

    class FailingAgent:
        agent_code = "communication"

        def evaluate_session(self, **_kwargs):
            raise RuntimeError("temporary analysis failure")

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(queue_module, "get_connection", fake_connection)
    monkeypatch.setattr(queue_module, "competency_assessment_agents", [FailingAgent()])
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)
    monkeypatch.setattr(queue, "_fail", lambda _job, message, retry: failures.append((message, retry)))

    queue._process(analysis_job())

    assert failures == [("temporary analysis failure", True)]


@pytest.mark.unit
def test_last_analysis_attempt_becomes_terminal_failure(monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    connection = RecordingConnection()
    failures: list[tuple[str, bool]] = []

    class FailingAgent:
        agent_code = "communication"

        def evaluate_session(self, **_kwargs):
            raise RuntimeError("permanent analysis failure")

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(queue_module, "get_connection", fake_connection)
    monkeypatch.setattr(queue_module, "competency_assessment_agents", [FailingAgent()])
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)
    monkeypatch.setattr(queue, "_fail", lambda _job, message, retry: failures.append((message, retry)))

    queue._process(analysis_job(attempts=3, max_attempts=3))

    assert failures == [("permanent analysis failure", False)]


@pytest.mark.unit
def test_universal_queue_path_does_not_resolve_legacy_strategy(monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    connection = RecordingConnection()
    frozen = frozen_agent_definitions()["communication"]
    frozen["definition"]["runtime"] = {
        "mode": "universal_llm",
        "model_profile": "assessment_strict",
        "temperature": 0,
        "max_attempts": 1,
        "timeout_seconds": 30,
        "max_output_tokens": 1200,
        "fallback": "fail",
    }
    frozen["checksum"] = definition_checksum(frozen["definition"])
    competency = dict(LEGACY_METHODOLOGY_DEFINITION["competencies"][0])
    competency["skill_codes"] = ["active_listening"]
    snapshot = {
        "methodology": {
            "code": "universal_test",
            "version": 1,
            "definition": {"competencies": [competency]},
        },
        "prompts": {"agent_definitions": {"communication": frozen}},
    }

    class Provider:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, []

    monkeypatch.setattr(queue_module, "competency_assessment_agents", [])
    monkeypatch.setattr(queue_module, "UniversalEvaluationMaterialProvider", lambda **_kwargs: Provider())
    monkeypatch.setattr(
        queue_module.CompetencyEvaluatorExecutor,
        "execute",
        lambda _self, *, connection, input_data: CompetencyEvaluationOutput(
            competency_code=input_data.competency_code,
            component_code=input_data.component_code,
            component_version=input_data.component_version,
            status="no_assessments",
            assessments=[],
            case_analyses=[],
        ),
    )
    context = ScenarioExecutionContext(
        connection=connection,
        session_id=42,
        user_id=7,
        snapshot=snapshot,
        stage={},
    )

    result = queue._execute_methodology_evaluators(context, analysis_job())

    assert result == {"evaluators_completed": ["evaluation.communication"]}


@pytest.mark.unit
def test_shadow_path_requires_both_kill_switches(monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    monkeypatch.setattr(queue_module.settings, "assessment_universal_llm_enabled", True)
    monkeypatch.setattr(queue_module.settings, "assessment_universal_llm_shadow_enabled", False)

    class NeverExecutor:
        def execute(self, **_kwargs):
            raise AssertionError("disabled shadow must not execute")

    queue._execute_shadow_evaluation(
        context=ScenarioExecutionContext(
            connection=object(), session_id=42, user_id=7, snapshot={}, stage={}
        ),
        competency={"shadow_evaluation": {"agent_definition": {"code": "shadow", "version": 1}}},
        executor=NeverExecutor(),
        official_input=None,
        official_output=None,
    )
