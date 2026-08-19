from contextlib import contextmanager

import pytest

from Api import assessment_analysis_queue as queue_module
from Api.assessment_analysis_queue import AssessmentAnalysisJob, AssessmentAnalysisQueue
from Api.assessment_configuration import LEGACY_METHODOLOGY_DEFINITION, LEGACY_SCENARIO_DEFINITION


class Cursor:
    rowcount = 1

    def __init__(self, statement: str = "") -> None:
        self.statement = statement

    def fetchone(self):
        if "execution_snapshot_json" in self.statement:
            return {
                "execution_snapshot_json": {
                    "methodology": {"definition": LEGACY_METHODOLOGY_DEFINITION},
                    "scenario": {"definition": LEGACY_SCENARIO_DEFINITION},
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
        def evaluate_session(self, *, connection, session_id: int, user_id: int):
            evaluated.append((session_id, user_id))
            return []

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(queue_module, "get_connection", fake_connection)
    monkeypatch.setattr(queue_module, "competency_assessment_agents", [Agent(), Agent(), Agent(), Agent()])
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
