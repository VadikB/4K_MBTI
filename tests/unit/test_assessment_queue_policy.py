from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from Api import assessment_preparation_queue as queue_module
from Api.assessment_preparation_queue import AssessmentPreparationJob, AssessmentPreparationQueue
from Api.schemas import AssessmentStartResponse
from Api.snapshot_integrity import bind_execution_snapshot, snapshot_checksum


def user_payload() -> dict:
    return {
        "id": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "role_id": 1,
        "job_description": "Менеджер",
        "raw_position": "Менеджер",
        "raw_duties": "Управляет задачами",
        "normalized_duties": "Управляет задачами",
        "active_profile_id": 1,
        "company_industry": "ИТ",
        "personal_data_consent_accepted_at": datetime.now(UTC).isoformat(),
    }


@pytest.fixture(autouse=True)
def verified_stage(monkeypatch):
    @contextmanager
    def fake_connection():
        yield SimpleNamespace()

    monkeypatch.setattr(queue_module, "get_connection", fake_connection)
    monkeypatch.setattr(
        queue_module.scenario_runner,
        "run_stage",
        lambda *_args, **kwargs: kwargs["executor"](SimpleNamespace()),
    )


def job(*, attempts: int = 1, max_attempts: int = 3) -> AssessmentPreparationJob:
    snapshot = bind_execution_snapshot({
        "schema_version": 1,
        "scenario": {
            "definition": {
                "schema_version": 1,
                "initial_stage": "prepare_profile",
                "stages": [{"id": "prepare_profile", "component": "profile.prepare", "component_version": 1}],
            }
        },
    }, user_id=1)
    return AssessmentPreparationJob(
        id=10,
        operation_id="operation",
        user_id=1,
        user_payload=user_payload(),
        attempts=attempts,
        max_attempts=max_attempts,
        worker_id="worker",
        execution_snapshot=snapshot,
        execution_checksum=snapshot_checksum(snapshot),
    )


@pytest.mark.unit
def test_transient_failure_is_retried(monkeypatch) -> None:
    queue = AssessmentPreparationQueue()
    failures: list[tuple[str, bool]] = []

    class FailingAgent:
        def start_case_interview(self, **_kwargs):
            raise RuntimeError("temporary")

    monkeypatch.setattr(queue_module, "_get_interviewer_agent", lambda: FailingAgent())
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)
    monkeypatch.setattr(queue, "_fail", lambda _job, message, retry: failures.append((message, retry)))

    queue._process(job())
    assert failures == [("temporary", True)]


@pytest.mark.unit
def test_validation_failure_is_not_retried(monkeypatch) -> None:
    queue = AssessmentPreparationQueue()
    failures: list[tuple[str, bool]] = []

    class InvalidAgent:
        def start_case_interview(self, **_kwargs):
            raise ValueError("profile is invalid")

    monkeypatch.setattr(queue_module, "_get_interviewer_agent", lambda: InvalidAgent())
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)
    monkeypatch.setattr(queue, "_fail", lambda _job, message, retry: failures.append((message, retry)))

    queue._process(job())
    assert failures == [("profile is invalid", False)]


@pytest.mark.unit
def test_successful_job_is_completed(monkeypatch) -> None:
    queue = AssessmentPreparationQueue()
    completed: list[AssessmentStartResponse] = []

    class SuccessfulAgent:
        def start_case_interview(self, **_kwargs):
            return AssessmentStartResponse(
                session_code="session",
                session_id=2,
                case_number=1,
                total_cases=1,
                message="ready",
                assessment_completed=False,
                case_completed=False,
            )

    monkeypatch.setattr(queue_module, "_get_interviewer_agent", lambda: SuccessfulAgent())
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)
    monkeypatch.setattr(queue, "_complete", lambda _job, result: completed.append(result))

    queue._process(job())
    assert completed[0].session_code == "session"


@pytest.mark.unit
def test_corrupt_snapshot_is_terminal_machine_failure(monkeypatch) -> None:
    queue = AssessmentPreparationQueue()
    failures: list[tuple[str, bool, str]] = []
    corrupted = job()
    corrupted.execution_snapshot["tampered"] = True
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)
    monkeypatch.setattr(
        queue,
        "_fail",
        lambda _job, message, retry, error_code="": failures.append((message, retry, error_code)),
    )

    queue._process(corrupted)

    assert failures == [("SNAPSHOT_INTEGRITY_FAILED", False, "SNAPSHOT_INTEGRITY_FAILED")]
