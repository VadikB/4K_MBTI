from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
from dataclasses import dataclass
from uuid import uuid4

from Api.config import settings
from Api.database import get_connection
from Api.progress_service import operation_progress_service
from Api.schemas import AssessmentStartResponse, UserResponse
from Api.user_journey import evaluate_profile_state

logger = logging.getLogger("agent4k.assessment_queue")


def _get_interviewer_agent():
    from Api.agent import interviewer_agent

    return interviewer_agent


def _get_assessment_service():
    from Api.assessment_service import assessment_service

    return assessment_service


@dataclass(slots=True)
class AssessmentPreparationJob:
    id: int
    operation_id: str
    user_id: int
    user_payload: dict
    attempts: int
    max_attempts: int
    worker_id: str
    prepare_only: bool = False


class AssessmentPreparationQueue:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._lifecycle_lock = threading.Lock()
        self._maintenance_lock = threading.Lock()
        self._last_maintenance_monotonic = 0.0
        self._worker_prefix = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"

    def start(self) -> None:
        with self._lifecycle_lock:
            if any(thread.is_alive() for thread in self._threads):
                return
            self._stop_event.clear()
            worker_count = max(1, settings.assessment_queue_worker_threads)
            self._threads = []
            for index in range(worker_count):
                thread = threading.Thread(
                    target=self._run_worker,
                    args=(f"{self._worker_prefix}:{index + 1}",),
                    name=f"assessment-preparation-{index + 1}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)
            logger.info("Assessment preparation queue started workers=%s", worker_count)

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop_event.set()
            self._wake_event.set()
            threads = list(self._threads)
            self._threads = []
        for thread in threads:
            thread.join(timeout=5)
        logger.info("Assessment preparation queue stopped")

    def enqueue(self, *, operation_id: str, user: UserResponse, prepare_only: bool = False) -> dict:
        payload = user.model_dump(mode="json")
        payload["_prepare_only"] = prepare_only
        with get_connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s, %s)", (424242, int(user.id)))
            existing = connection.execute(
                """
                SELECT operation_id, status, attempts, created_at
                FROM assessment_preparation_jobs
                WHERE user_id = %s
                  AND status IN ('queued', 'running')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user.id,),
            ).fetchone()
            if existing is not None:
                result = dict(existing)
            else:
                row = connection.execute(
                    """
                    INSERT INTO assessment_preparation_jobs (
                        operation_id, user_id, user_payload_json, status, max_attempts
                    )
                    VALUES (%s, %s, %s::jsonb, 'queued', %s)
                    RETURNING operation_id, status, attempts, created_at
                    """,
                    (
                        operation_id,
                        user.id,
                        json.dumps(payload, ensure_ascii=False),
                        max(1, settings.assessment_queue_max_attempts),
                    ),
                ).fetchone()
                result = dict(row)
        self._wake_event.set()
        return result

    def get_status(self, operation_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT operation_id, user_id, status, attempts, max_attempts,
                       result_json, error_message, created_at, updated_at, completed_at
                FROM assessment_preparation_jobs
                WHERE operation_id = %s
                """,
                (operation_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def stats(self) -> dict[str, int]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*)::int AS count
                FROM assessment_preparation_jobs
                WHERE status IN ('queued', 'running', 'failed')
                GROUP BY status
                """
            ).fetchall()
        counts = {"queued": 0, "running": 0, "failed": 0}
        counts.update({str(row["status"]): int(row["count"]) for row in rows})
        return counts

    def _run_worker(self, worker_id: str) -> None:
        poll_interval = max(0.2, settings.assessment_queue_poll_interval_seconds)
        while not self._stop_event.is_set():
            try:
                job = self._claim_next(worker_id)
                if job is None:
                    self._wake_event.wait(timeout=poll_interval)
                    self._wake_event.clear()
                    continue
                self._process(job)
            except Exception:
                logger.exception("Assessment queue worker loop failed worker_id=%s", worker_id)
                self._stop_event.wait(timeout=poll_interval)

    def _claim_next(self, worker_id: str) -> AssessmentPreparationJob | None:
        self._run_maintenance_if_due()
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id, operation_id, user_id, user_payload_json, attempts, max_attempts
                FROM assessment_preparation_jobs
                WHERE status = 'queued'
                  AND next_attempt_at <= NOW()
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            claimed = connection.execute(
                """
                UPDATE assessment_preparation_jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    worker_id = %s,
                    locked_at = NOW(),
                    updated_at = NOW(),
                    error_message = NULL
                WHERE id = %s
                RETURNING id, operation_id, user_id, user_payload_json, attempts, max_attempts
                """,
                (worker_id, row["id"]),
            ).fetchone()
        payload = claimed["user_payload_json"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        prepare_only = bool(payload.pop("_prepare_only", False))
        return AssessmentPreparationJob(
            id=int(claimed["id"]),
            operation_id=str(claimed["operation_id"]),
            user_id=int(claimed["user_id"]),
            user_payload=dict(payload or {}),
            attempts=int(claimed["attempts"]),
            max_attempts=int(claimed["max_attempts"]),
            worker_id=worker_id,
            prepare_only=prepare_only,
        )

    def _run_maintenance_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_maintenance_monotonic < 60:
            return
        with self._maintenance_lock:
            now = time.monotonic()
            if now - self._last_maintenance_monotonic < 60:
                return
            lease_seconds = max(30, settings.assessment_queue_lease_timeout_seconds)
            retention_hours = max(1, settings.assessment_queue_retention_hours)
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE assessment_preparation_jobs
                    SET status = 'queued',
                        worker_id = NULL,
                        locked_at = NULL,
                        next_attempt_at = NOW(),
                        updated_at = NOW(),
                        error_message = COALESCE(error_message, 'Worker lease expired; job returned to queue.')
                    WHERE status = 'running'
                      AND locked_at < NOW() - %s::interval
                    """,
                    (f"{lease_seconds} seconds",),
                )
                connection.execute(
                    """
                    DELETE FROM assessment_preparation_jobs
                    WHERE status IN ('completed', 'failed')
                      AND updated_at < NOW() - %s::interval
                    """,
                    (f"{retention_hours} hours",),
                )
            self._last_maintenance_monotonic = now

    def _process(self, job: AssessmentPreparationJob) -> None:
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._run_job_heartbeat,
            args=(job, heartbeat_stop),
            name=f"assessment-heartbeat-{job.id}",
            daemon=True,
        )
        heartbeat.start()
        try:
            interviewer_agent = _get_interviewer_agent()
            user = UserResponse.model_validate(job.user_payload)
            profile_state = evaluate_profile_state(user)
            user_fixable_fields = {"duties", "role", "company_industry", "active_profile"}
            non_repairable_fields = set(profile_state.missing_fields) - user_fixable_fields
            if non_repairable_fields:
                raise ValueError(
                    "Завершите настройку профиля перед оценкой. "
                    "Не заполнены поля: " + ", ".join(sorted(non_repairable_fields)) + "."
                )
            if not profile_state.is_complete:
                repaired_user = interviewer_agent.backfill_user_profile(user.id)
                if repaired_user is not None:
                    user = repaired_user
                repaired_state = evaluate_profile_state(user)
                if not repaired_state.is_complete:
                    raise ValueError(
                        "Завершите настройку профиля перед оценкой. "
                        "Не заполнены поля: " + ", ".join(repaired_state.missing_fields) + "."
                    )
            if job.prepare_only:
                plan = _get_assessment_service().ensure_assessment_session(
                    user,
                    progress_operation_id=job.operation_id,
                )
                if plan is None:
                    raise ValueError("Не удалось предварительно подготовить assessment-сессию.")
                result = None
            else:
                result = interviewer_agent.start_case_interview(
                    user=user,
                    progress_operation_id=job.operation_id,
                )
            self._complete(job, result)
        except ValueError as exc:
            message = str(exc)
            self._fail(
                job,
                message,
                retry="одновременно подготавливается много ассессментов" in message.lower()
                and job.attempts < job.max_attempts,
            )
        except Exception as exc:
            logger.exception(
                "Assessment preparation failed operation_id=%s attempt=%s/%s",
                job.operation_id,
                job.attempts,
                job.max_attempts,
            )
            self._fail(job, str(exc), retry=job.attempts < job.max_attempts)
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=2)

    def _run_job_heartbeat(self, job: AssessmentPreparationJob, stop_event: threading.Event) -> None:
        interval = max(10, min(60, settings.assessment_queue_lease_timeout_seconds // 3))
        while not stop_event.wait(timeout=interval):
            try:
                with get_connection() as connection:
                    connection.execute(
                        """
                        UPDATE assessment_preparation_jobs
                        SET locked_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                          AND status = 'running'
                          AND worker_id = %s
                        """,
                        (job.id, job.worker_id),
                    )
            except Exception:
                logger.exception("Assessment queue heartbeat failed operation_id=%s", job.operation_id)

    def _complete(self, job: AssessmentPreparationJob, result: AssessmentStartResponse | None) -> None:
        result_json = json.dumps(result.model_dump(mode="json"), ensure_ascii=False) if result is not None else None
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE assessment_preparation_jobs
                SET status = 'completed',
                    result_json = %s::jsonb,
                    error_message = NULL,
                    worker_id = NULL,
                    locked_at = NULL,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                  AND status = 'running'
                  AND worker_id = %s
                """,
                (result_json, job.id, job.worker_id),
            )
            updated = cursor.rowcount
        if updated != 1:
            logger.warning("Ignoring completion from expired lease operation_id=%s", job.operation_id)
            return
        operation_progress_service.complete(
            job.operation_id,
            title="Кейсы подготовлены" if job.prepare_only else "Ассессмент готов",
            message=(
                "Персонализированные кейсы подготовлены заранее. Пользователь сможет начать без повторной генерации."
                if job.prepare_only
                else "Первый кейс подготовлен. Можно начинать интервью."
            ),
        )
        logger.info("Assessment preparation completed operation_id=%s user_id=%s", job.operation_id, job.user_id)

    def _fail(self, job: AssessmentPreparationJob, message: str, *, retry: bool) -> None:
        if retry:
            delay_seconds = min(60, 5 * (2 ** max(0, job.attempts - 1)))
            with get_connection() as connection:
                cursor = connection.execute(
                    """
                    UPDATE assessment_preparation_jobs
                    SET status = 'queued',
                        error_message = %s,
                        worker_id = NULL,
                        locked_at = NULL,
                        next_attempt_at = NOW() + %s::interval,
                        updated_at = NOW()
                    WHERE id = %s
                      AND status = 'running'
                      AND worker_id = %s
                    """,
                    (message[:2000], f"{delay_seconds} seconds", job.id, job.worker_id),
                )
                updated = cursor.rowcount
            if updated != 1:
                logger.warning("Ignoring retry from expired lease operation_id=%s", job.operation_id)
                return
            operation_progress_service.advance(
                job.operation_id,
                0,
                title="Повторяем подготовку",
                message=f"Временная ошибка. Повторная попытка {job.attempts + 1} из {job.max_attempts}.",
            )
            self._wake_event.set()
            return
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE assessment_preparation_jobs
                SET status = 'failed',
                    error_message = %s,
                    worker_id = NULL,
                    locked_at = NULL,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                  AND status = 'running'
                  AND worker_id = %s
                """,
                (message[:2000], job.id, job.worker_id),
            )
            updated = cursor.rowcount
        if updated != 1:
            logger.warning("Ignoring failure from expired lease operation_id=%s", job.operation_id)
            return
        operation_progress_service.fail(job.operation_id, message=message)
        logger.warning("Assessment preparation permanently failed operation_id=%s error=%s", job.operation_id, message)


assessment_preparation_queue = AssessmentPreparationQueue()
