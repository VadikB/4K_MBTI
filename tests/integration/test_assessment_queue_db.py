from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg.rows import dict_row

from Api import assessment_preparation_queue as queue_module
from Api.assessment_preparation_queue import AssessmentPreparationQueue
from Api.schemas import AssessmentStartResponse, UserResponse


@pytest.fixture
def queue_database(test_database_url, monkeypatch):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_preparation_jobs")
        connection.execute(
            """
            CREATE TABLE assessment_preparation_jobs (
                id BIGSERIAL PRIMARY KEY,
                operation_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                user_payload_json JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                result_json JSONB,
                error_message TEXT,
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
            CREATE UNIQUE INDEX idx_assessment_preparation_jobs_active_user
            ON assessment_preparation_jobs(user_id)
            WHERE status IN ('queued', 'running')
            """
        )

    @contextmanager
    def test_connection():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            yield connection

    monkeypatch.setattr(queue_module, "get_connection", test_connection)
    yield

    with psycopg.connect(test_database_url) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_preparation_jobs")


def make_test_user() -> UserResponse:
    return UserResponse(
        id=101,
        created_at=datetime.now(UTC),
        role_id=1,
        job_description="Менеджер",
        raw_duties="Управляет задачами",
        normalized_duties="Управляет задачами",
        active_profile_id=1,
        company_industry="ИТ",
    )


@pytest.mark.integration
def test_enqueue_claim_complete_and_read_result(queue_database, monkeypatch) -> None:
    queue = AssessmentPreparationQueue()
    monkeypatch.setattr(queue_module.operation_progress_service, "complete", lambda *_args, **_kwargs: None)

    queued = queue.enqueue(operation_id="integration-operation", user=make_test_user())
    claimed = queue._claim_next("integration-worker")

    assert queued["status"] == "queued"
    assert claimed is not None
    assert claimed.operation_id == "integration-operation"
    assert claimed.worker_id == "integration-worker"

    queue._complete(
        claimed,
        AssessmentStartResponse(
            session_code="integration-session",
            session_id=501,
            case_number=1,
            total_cases=1,
            message="ready",
            assessment_completed=False,
            case_completed=False,
        ),
    )
    status = queue.get_status("integration-operation")

    assert status["status"] == "completed"
    assert status["attempts"] == 1
    assert status["result_json"]["session_code"] == "integration-session"


@pytest.mark.integration
def test_active_job_is_deduplicated_per_user(queue_database) -> None:
    queue = AssessmentPreparationQueue()

    first = queue.enqueue(operation_id="first-operation", user=make_test_user())
    second = queue.enqueue(operation_id="second-operation", user=make_test_user())

    assert first["operation_id"] == "first-operation"
    assert second["operation_id"] == "first-operation"


@pytest.mark.integration
def test_expired_lease_is_returned_to_queue(queue_database, monkeypatch) -> None:
    queue = AssessmentPreparationQueue()
    monkeypatch.setattr(queue_module.settings, "assessment_queue_lease_timeout_seconds", 30)
    queue.enqueue(operation_id="expired-operation", user=make_test_user())
    claimed = queue._claim_next("dead-worker")
    assert claimed is not None

    with queue_module.get_connection() as connection:
        connection.execute(
            """
            UPDATE assessment_preparation_jobs
            SET locked_at = NOW() - INTERVAL '2 minutes'
            WHERE operation_id = 'expired-operation'
            """
        )

    queue._last_maintenance_monotonic = 0
    queue._run_maintenance_if_due()
    reclaimed = queue._claim_next("replacement-worker")

    assert reclaimed is not None
    assert reclaimed.operation_id == "expired-operation"
    assert reclaimed.worker_id == "replacement-worker"


@pytest.mark.integration
def test_worker_with_expired_lease_cannot_overwrite_result(queue_database, monkeypatch) -> None:
    queue = AssessmentPreparationQueue()
    monkeypatch.setattr(queue_module.operation_progress_service, "complete", lambda *_args, **_kwargs: None)
    queue.enqueue(operation_id="lease-owner-operation", user=make_test_user())
    expired_claim = queue._claim_next("expired-worker")
    assert expired_claim is not None

    with queue_module.get_connection() as connection:
        connection.execute(
            """
            UPDATE assessment_preparation_jobs
            SET worker_id = 'replacement-worker',
                locked_at = NOW()
            WHERE operation_id = 'lease-owner-operation'
            """
        )

    queue._complete(
        expired_claim,
        AssessmentStartResponse(
            session_code="stale-result",
            session_id=999,
            case_number=1,
            total_cases=1,
            message="stale",
            assessment_completed=False,
            case_completed=False,
        ),
    )
    status = queue.get_status("lease-owner-operation")

    assert status["status"] == "running"
    assert status["result_json"] is None
    assert status["error_message"] is None
