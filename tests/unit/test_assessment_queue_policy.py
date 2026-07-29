from __future__ import annotations

from datetime import UTC, datetime

import pytest

from Api import assessment_preparation_queue as queue_module
from Api.assessment_preparation_queue import AssessmentPreparationJob, AssessmentPreparationQueue
from Api.schemas import AssessmentStartResponse


def user_payload() -> dict:
    return {
        "id": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "role_id": 1,
        "job_description": "Менеджер",
        "raw_duties": "Управляет задачами",
        "normalized_duties": "Управляет задачами",
        "active_profile_id": 1,
        "company_industry": "ИТ",
    }


def job(*, attempts: int = 1, max_attempts: int = 3) -> AssessmentPreparationJob:
    return AssessmentPreparationJob(
        id=10,
        operation_id="operation",
        user_id=1,
        user_payload=user_payload(),
        attempts=attempts,
        max_attempts=max_attempts,
        worker_id="worker",
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
