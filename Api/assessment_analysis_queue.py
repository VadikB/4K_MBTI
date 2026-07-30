from __future__ import annotations

import logging
import os
import socket
import threading
import time
from dataclasses import dataclass
from uuid import uuid4

from Api.communication_agent import competency_assessment_agents
from Api.config import settings
from Api.database import get_connection
from Api.mbti.service import mbti_assessment_service

logger = logging.getLogger("agent4k.analysis_queue")


@dataclass(slots=True)
class AssessmentAnalysisJob:
    id: int
    operation_id: str
    session_id: int
    user_id: int
    attempts: int
    max_attempts: int
    worker_id: str


class AssessmentAnalysisQueue:
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
            self._threads = []
            for index in range(max(1, settings.assessment_analysis_worker_threads)):
                thread = threading.Thread(
                    target=self._run_worker,
                    args=(f"{self._worker_prefix}:{index + 1}",),
                    name=f"assessment-analysis-{index + 1}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)
        logger.info("Assessment analysis queue started workers=%s", len(self._threads))

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop_event.set()
            self._wake_event.set()
            threads = list(self._threads)
            self._threads = []
        for thread in threads:
            thread.join(timeout=5)
        logger.info("Assessment analysis queue stopped")

    def notify(self) -> None:
        self._wake_event.set()

    def enqueue_retry(self, *, session_id: int, user_id: int) -> dict:
        operation_id = f"analysis-{session_id}-{uuid4().hex}"
        with get_connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s, %s)", (434343, session_id))
            active = connection.execute(
                """
                SELECT operation_id, status
                FROM assessment_analysis_jobs
                WHERE session_id = %s
                  AND status IN ('queued', 'running')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if active is not None:
                result = dict(active)
            else:
                row = connection.execute(
                    """
                    INSERT INTO assessment_analysis_jobs (
                        operation_id, session_id, user_id, status, max_attempts
                    )
                    VALUES (%s, %s, %s, 'queued', %s)
                    RETURNING operation_id, status
                    """,
                    (operation_id, session_id, user_id, max(1, settings.assessment_queue_max_attempts)),
                ).fetchone()
                connection.execute(
                    """
                    UPDATE user_sessions
                    SET status = 'cases_completed',
                        error_stage = NULL,
                        error_code = NULL,
                        error_message = NULL,
                        error_retryable = FALSE
                    WHERE id = %s
                      AND user_id = %s
                    """,
                    (session_id, user_id),
                )
                result = dict(row)
        self.notify()
        return result

    def get_status(self, *, session_id: int, user_id: int) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    job.operation_id,
                    job.session_id,
                    job.status,
                    job.progress_percent,
                    job.current_step,
                    job.attempts,
                    job.max_attempts,
                    job.error_code,
                    job.error_message,
                    job.retryable,
                    job.created_at,
                    job.updated_at,
                    job.completed_at,
                    session.status AS session_status
                FROM assessment_analysis_jobs job
                JOIN user_sessions session ON session.id = job.session_id
                WHERE job.session_id = %s
                  AND job.user_id = %s
                ORDER BY job.created_at DESC
                LIMIT 1
                """,
                (session_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def stats(self) -> dict[str, int]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*)::int AS count
                FROM assessment_analysis_jobs
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
                logger.exception("Analysis queue worker loop failed worker_id=%s", worker_id)
                self._stop_event.wait(timeout=poll_interval)

    def _claim_next(self, worker_id: str) -> AssessmentAnalysisJob | None:
        self._run_maintenance_if_due()
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM assessment_analysis_jobs
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
                UPDATE assessment_analysis_jobs
                SET status = 'running',
                    progress_percent = GREATEST(progress_percent, 5),
                    current_step = 'starting',
                    attempts = attempts + 1,
                    worker_id = %s,
                    locked_at = NOW(),
                    updated_at = NOW(),
                    error_code = NULL,
                    error_message = NULL
                WHERE id = %s
                RETURNING id, operation_id, session_id, user_id, attempts, max_attempts
                """,
                (worker_id, row["id"]),
            ).fetchone()
            connection.execute(
                """
                UPDATE user_sessions
                SET status = 'analyzing',
                    analysis_started_at = COALESCE(analysis_started_at, NOW()),
                    error_stage = NULL,
                    error_code = NULL,
                    error_message = NULL,
                    error_retryable = FALSE
                WHERE id = %s
                """,
                (claimed["session_id"],),
            )
        return AssessmentAnalysisJob(
            id=int(claimed["id"]),
            operation_id=str(claimed["operation_id"]),
            session_id=int(claimed["session_id"]),
            user_id=int(claimed["user_id"]),
            attempts=int(claimed["attempts"]),
            max_attempts=int(claimed["max_attempts"]),
            worker_id=worker_id,
        )

    def _process(self, job: AssessmentAnalysisJob) -> None:
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._run_job_heartbeat,
            args=(job, heartbeat_stop),
            name=f"assessment-analysis-heartbeat-{job.id}",
            daemon=True,
        )
        heartbeat.start()
        try:
            with get_connection() as connection:
                step_progress = [15, 35, 55, 75]
                for index, agent in enumerate(competency_assessment_agents):
                    self._update_progress(
                        connection,
                        job,
                        progress=step_progress[min(index, len(step_progress) - 1)],
                        current_step=f"competency_{index + 1}",
                    )
                    agent.evaluate_session(
                        connection=connection,
                        session_id=job.session_id,
                        user_id=job.user_id,
                    )
                self._update_progress(
                    connection,
                    job,
                    progress=90,
                    current_step="mbti_summary",
                )
                mbti_assessment_service.summarize_session(connection, session_id=job.session_id)
                cursor = connection.execute(
                    """
                    UPDATE assessment_analysis_jobs
                    SET status = 'completed',
                        progress_percent = 100,
                        current_step = 'report_ready',
                        retryable = FALSE,
                        worker_id = NULL,
                        locked_at = NULL,
                        completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                      AND status = 'running'
                      AND worker_id = %s
                    """,
                    (job.id, job.worker_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Analysis job lease expired before completion.")
                connection.execute(
                    """
                    UPDATE user_sessions
                    SET status = 'completed',
                        analysis_completed_at = NOW(),
                        finished_at = COALESCE(finished_at, NOW()),
                        error_stage = NULL,
                        error_code = NULL,
                        error_message = NULL,
                        error_retryable = FALSE
                    WHERE id = %s
                    """,
                    (job.session_id,),
                )
            logger.info("Assessment analysis completed session_id=%s", job.session_id)
        except Exception as exc:
            logger.exception(
                "Assessment analysis failed session_id=%s attempt=%s/%s",
                job.session_id,
                job.attempts,
                job.max_attempts,
            )
            self._fail(job, str(exc), retry=job.attempts < job.max_attempts)
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=2)

    def _update_progress(
        self,
        connection,
        job: AssessmentAnalysisJob,
        *,
        progress: int,
        current_step: str,
    ) -> None:
        connection.execute(
            """
            UPDATE assessment_analysis_jobs
            SET progress_percent = %s,
                current_step = %s,
                locked_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
              AND status = 'running'
              AND worker_id = %s
            """,
            (progress, current_step, job.id, job.worker_id),
        )
        connection.commit()

    def _fail(self, job: AssessmentAnalysisJob, message: str, *, retry: bool) -> None:
        if retry:
            delay_seconds = min(60, 5 * (2 ** max(0, job.attempts - 1)))
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE assessment_analysis_jobs
                    SET status = 'queued',
                        current_step = 'retry_wait',
                        error_code = 'analysis_failed',
                        error_message = %s,
                        retryable = TRUE,
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
                connection.execute(
                    """
                    UPDATE user_sessions
                    SET status = 'analyzing',
                        error_stage = 'analysis',
                        error_code = 'analysis_retry',
                        error_message = %s,
                        error_retryable = TRUE
                    WHERE id = %s
                    """,
                    (message[:2000], job.session_id),
                )
            self.notify()
            return

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE assessment_analysis_jobs
                SET status = 'failed',
                    current_step = 'failed',
                    error_code = 'analysis_failed',
                    error_message = %s,
                    retryable = TRUE,
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
            connection.execute(
                """
                UPDATE user_sessions
                SET status = 'failed',
                    error_stage = 'analysis',
                    error_code = 'analysis_failed',
                    error_message = %s,
                    error_retryable = TRUE
                WHERE id = %s
                """,
                (message[:2000], job.session_id),
            )

    def _run_job_heartbeat(self, job: AssessmentAnalysisJob, stop_event: threading.Event) -> None:
        interval = max(10, min(60, settings.assessment_queue_lease_timeout_seconds // 3))
        while not stop_event.wait(timeout=interval):
            try:
                with get_connection() as connection:
                    connection.execute(
                        """
                        UPDATE assessment_analysis_jobs
                        SET locked_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                          AND status = 'running'
                          AND worker_id = %s
                        """,
                        (job.id, job.worker_id),
                    )
            except Exception:
                logger.exception("Analysis queue heartbeat failed session_id=%s", job.session_id)

    def _run_maintenance_if_due(self) -> None:
        now = time.monotonic()
        if now - self._last_maintenance_monotonic < 60:
            return
        with self._maintenance_lock:
            now = time.monotonic()
            if now - self._last_maintenance_monotonic < 60:
                return
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE assessment_analysis_jobs
                    SET status = 'queued',
                        current_step = 'lease_recovered',
                        worker_id = NULL,
                        locked_at = NULL,
                        next_attempt_at = NOW(),
                        updated_at = NOW(),
                        error_message = COALESCE(error_message, 'Worker lease expired; job returned to queue.')
                    WHERE status = 'running'
                      AND locked_at < NOW() - %s::interval
                    """,
                    (f"{max(30, settings.assessment_queue_lease_timeout_seconds)} seconds",),
                )
            self._last_maintenance_monotonic = now


assessment_analysis_queue = AssessmentAnalysisQueue()
