from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api import assessment_preparation_queue as queue_module
from Api.assessment_configuration import definition_checksum
from Api.database import ensure_execution_snapshot_guards
from Api.snapshot_integrity import bind_execution_snapshot, execution_snapshot_integrity, snapshot_checksum
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
                execution_snapshot_json JSONB,
                execution_checksum TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                result_json JSONB,
                error_code TEXT,
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
        ensure_execution_snapshot_guards(connection, tables=("assessment_preparation_jobs",))

    @contextmanager
    def test_connection():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            yield connection

    monkeypatch.setattr(queue_module, "get_connection", test_connection)
    snapshot = {
        "schema_version": 1,
        "_integrity": execution_snapshot_integrity(),
        "configuration": {"id": 1, "code": "queue_test"},
        "methodology": {"id": 1, "code": "queue_test", "version": 1, "definition": {}},
        "scenario": {"id": 1, "code": "queue_test", "version": 1, "definition": {}},
        "prompts": {},
    }
    monkeypatch.setattr(
        queue_module,
        "load_default_execution_configuration",
        lambda _connection: {
            "configuration_id": 1,
            "methodology_version_id": 1,
            "scenario_version_id": 1,
            "snapshot": snapshot,
            "checksum": definition_checksum(snapshot),
        },
    )
    yield

    with psycopg.connect(test_database_url) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_preparation_jobs")


def make_test_user() -> UserResponse:
    return UserResponse(
        id=101,
        created_at=datetime.now(UTC),
        role_id=1,
        job_description="Менеджер",
        raw_position="Менеджер",
        raw_duties="Управляет задачами",
        normalized_duties="Управляет задачами",
        active_profile_id=1,
        company_industry="ИТ",
        personal_data_consent_accepted_at=datetime.now(UTC),
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
    assert claimed.execution_checksum == definition_checksum(claimed.execution_snapshot)

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
def test_queued_execution_snapshot_is_immutable(queue_database) -> None:
    queue = AssessmentPreparationQueue()
    queue.enqueue(operation_id="immutable-operation", user=make_test_user())

    with pytest.raises(psycopg.Error, match="Execution snapshot is immutable"):
        with queue_module.get_connection() as connection:
            connection.execute(
                "UPDATE assessment_preparation_jobs SET execution_snapshot_json = '{}'::jsonb "
                "WHERE operation_id = 'immutable-operation'"
            )


@pytest.mark.integration
def test_started_session_execution_snapshot_is_immutable(test_database_url) -> None:
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "session_snapshot_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(
            "CREATE TABLE user_sessions (id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL, status TEXT NOT NULL, "
            "execution_snapshot_json JSONB, execution_checksum TEXT)"
        )
        ensure_execution_snapshot_guards(connection, tables=("user_sessions",))
        frozen = bind_execution_snapshot({"schema_version": 1}, user_id=101)
        connection.execute(
            "INSERT INTO user_sessions VALUES (1,101,'active',%s::jsonb,%s)",
            (json.dumps(frozen), snapshot_checksum(frozen)),
        )

        with pytest.raises(psycopg.Error, match="Execution snapshot is immutable"):
            with connection.transaction():
                connection.execute("UPDATE user_sessions SET execution_snapshot_json='{}'::jsonb WHERE id=1")
        connection.rollback()


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

    queue._last_maintenance_monotonic = float("-inf")
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
