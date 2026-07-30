from __future__ import annotations

from contextlib import contextmanager

import psycopg
import pytest
from psycopg.rows import dict_row

from Api import assessment_analysis_queue as queue_module
from Api.assessment_analysis_queue import AssessmentAnalysisQueue


@pytest.fixture
def analysis_database(test_database_url, monkeypatch):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_analysis_jobs")
        connection.execute("DROP TABLE IF EXISTS user_sessions")
        connection.execute(
            """
            CREATE TABLE user_sessions (
                id SERIAL PRIMARY KEY,
                session_code TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                started_at TIMESTAMP DEFAULT NOW(),
                finished_at TIMESTAMP,
                analysis_started_at TIMESTAMP,
                analysis_completed_at TIMESTAMP,
                error_stage TEXT,
                error_code TEXT,
                error_message TEXT,
                error_retryable BOOLEAN NOT NULL DEFAULT FALSE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_analysis_jobs (
                id BIGSERIAL PRIMARY KEY,
                operation_id TEXT NOT NULL UNIQUE,
                session_id INTEGER NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                current_step TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                error_code TEXT,
                error_message TEXT,
                retryable BOOLEAN NOT NULL DEFAULT TRUE,
                worker_id TEXT,
                locked_at TIMESTAMP,
                next_attempt_at TIMESTAMP NOT NULL DEFAULT NOW(),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX idx_assessment_analysis_jobs_active_session
            ON assessment_analysis_jobs(session_id)
            WHERE status IN ('queued', 'running')
            """
        )
        connection.execute(
            """
            INSERT INTO user_sessions (id, session_code, user_id, status)
            VALUES (501, 'analysis-integration-session', 101, 'active')
            """
        )

    @contextmanager
    def test_connection():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            yield connection

    monkeypatch.setattr(queue_module, "get_connection", test_connection)
    yield test_connection

    with psycopg.connect(test_database_url) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_analysis_jobs")
        connection.execute("DROP TABLE IF EXISTS user_sessions")


def enqueue_analysis(queue: AssessmentAnalysisQueue) -> dict:
    return queue.enqueue_retry(session_id=501, user_id=101)


@pytest.mark.integration
def test_analysis_enqueue_is_deduplicated_and_persistent(analysis_database) -> None:
    first_queue = AssessmentAnalysisQueue()
    second_queue = AssessmentAnalysisQueue()

    first = enqueue_analysis(first_queue)
    second = enqueue_analysis(second_queue)
    restored = second_queue.get_status(session_id=501, user_id=101)

    assert first["operation_id"] == second["operation_id"]
    assert restored is not None
    assert restored["status"] == "queued"
    assert restored["session_status"] == "cases_completed"


@pytest.mark.integration
def test_analysis_claim_process_and_report_ready_transition(analysis_database, monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    evaluated: list[tuple[int, int]] = []

    class Agent:
        def evaluate_session(self, *, connection, session_id: int, user_id: int):
            evaluated.append((session_id, user_id))
            connection.execute(
                "UPDATE user_sessions SET error_message = COALESCE(error_message, '') WHERE id = %s",
                (session_id,),
            )
            return []

    monkeypatch.setattr(queue_module, "competency_assessment_agents", [Agent(), Agent(), Agent(), Agent()])
    monkeypatch.setattr(queue_module.mbti_assessment_service, "summarize_session", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)

    enqueue_analysis(queue)
    claimed = queue._claim_next("analysis-worker")
    assert claimed is not None

    running = queue.get_status(session_id=501, user_id=101)
    assert running is not None
    assert running["status"] == "running"
    assert running["session_status"] == "analyzing"

    queue._process(claimed)
    completed = queue.get_status(session_id=501, user_id=101)

    assert evaluated == [(501, 101)] * 4
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["session_status"] == "completed"
    assert completed["progress_percent"] == 100
    assert completed["current_step"] == "report_ready"
    assert completed["completed_at"] is not None


@pytest.mark.integration
def test_terminal_failure_can_be_retried_without_duplicate_active_job(analysis_database, monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()

    class FailingAgent:
        def evaluate_session(self, **_kwargs):
            raise RuntimeError("integration analysis failure")

    monkeypatch.setattr(queue_module.settings, "assessment_queue_max_attempts", 1)
    monkeypatch.setattr(queue_module, "competency_assessment_agents", [FailingAgent()])
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)

    first = enqueue_analysis(queue)
    claimed = queue._claim_next("failing-worker")
    assert claimed is not None
    queue._process(claimed)

    failed = queue.get_status(session_id=501, user_id=101)
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["session_status"] == "failed"
    assert failed["retryable"] is True
    assert "integration analysis failure" in failed["error_message"]

    retried = enqueue_analysis(queue)
    duplicate = enqueue_analysis(queue)
    restored = queue.get_status(session_id=501, user_id=101)

    assert retried["operation_id"] != first["operation_id"]
    assert duplicate["operation_id"] == retried["operation_id"]
    assert restored is not None
    assert restored["status"] == "queued"
    assert restored["session_status"] == "cases_completed"


@pytest.mark.integration
def test_expired_analysis_lease_is_recovered(analysis_database, monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    monkeypatch.setattr(queue_module.settings, "assessment_queue_lease_timeout_seconds", 30)
    enqueue_analysis(queue)
    first_claim = queue._claim_next("dead-analysis-worker")
    assert first_claim is not None

    with analysis_database() as connection:
        connection.execute(
            """
            UPDATE assessment_analysis_jobs
            SET locked_at = NOW() - INTERVAL '2 minutes'
            WHERE session_id = 501
            """
        )

    queue._last_maintenance_monotonic = 0
    queue._run_maintenance_if_due()
    replacement_claim = queue._claim_next("replacement-analysis-worker")

    assert replacement_claim is not None
    assert replacement_claim.operation_id == first_claim.operation_id
    assert replacement_claim.worker_id == "replacement-analysis-worker"
