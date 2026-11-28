"""Durable asynchronous preparation of the product M7 Cycle.

This queue owns only orchestration state. The admitted Cycle/AS remains owned by
the M4/M5/M7 product services and is returned only after their transaction commits.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import threading
from contextlib import contextmanager
from time import perf_counter
from uuid import uuid4

from fastapi.encoders import jsonable_encoder

from Api.database import get_connection
from Api import preparation_observation as observation

logger = logging.getLogger("agent4k.product_cycle_preparation")
HEARTBEAT_INTERVAL_SECONDS = 30.0


def _canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_request(request: dict) -> dict:
    """Client retry UUID is transport identity, not a new assessment/profile scope."""
    return {key: value for key, value in request.items()
            if key not in {"idempotency_key", "preparation_key"}}


def _command_request(request: dict) -> dict:
    # These fields are derived by the server, never transport payload identity.
    return {key: value for key, value in request.items()
            if key not in {"preparation_key", "next_preparation_scope"}}


def _owned_profile_snapshot(connection, *, profile_id: int, user_id: int) -> dict | None:
    return connection.execute(
        """SELECT content_json,assessment_configuration_id,checksum,organization_id,
                  organization_context_version_id,role_profile_version_id,user_context_version_id
           FROM assessment_personalized_profiles WHERE id=%s AND user_id=%s""",
        (profile_id, user_id),
    ).fetchone()


def latest_scope_operation(connection, *, user_id: int, profile_id: int, assignment_ref: str,
                           questionnaire_revision_id: int | None,
                           assignment_id: int | None = None) -> dict | None:
    table = connection.execute("SELECT to_regclass(current_schema()||'.product_cycle_preparation_operations') AS relation").fetchone()
    if not table or not table.get('relation'):
        return None
    row = connection.execute('''SELECT operation_id,status,attempt_token,error_code,error_message,request_json,created_at,updated_at,completed_at FROM product_cycle_preparation_operations
        WHERE user_id=%s AND request_json->>'personalized_profile_id'=%s
          AND request_json->>'assignment_ref'=%s
          AND request_json->>'questionnaire_revision_id' IS NOT DISTINCT FROM %s
          AND request_json->>'assignment_id' IS NOT DISTINCT FROM %s
        ORDER BY created_at DESC,id DESC LIMIT 1''',
        (user_id, str(profile_id), assignment_ref,
         str(questionnaire_revision_id) if questionnaire_revision_id is not None else None,
         str(assignment_id) if assignment_id is not None else None)).fetchone()
    if not row:
        return None
    operation = dict(row)
    ProductCyclePreparationQueue._project_retry_guard(connection, operation, user_id=user_id)
    return public_operation(observation.attach(connection, operation))


def latest_next_operation(connection, *, cycle_id: str, user_id: int) -> dict | None:
    from Api import m10_product_flow
    table = connection.execute("SELECT to_regclass(current_schema()||'.product_cycle_preparation_operations') AS relation").fetchone()
    if not table or not table.get("relation"):
        return None
    scope = m10_product_flow.next_preparation_scope(connection, cycle_id=cycle_id, user_id=user_id, check_current=False)
    row = connection.execute(
        """SELECT operation_id,status,attempt_token,error_code,error_message,request_json,created_at,updated_at,completed_at,
                  result_json#>>'{decision,status}' AS decision_status
           FROM product_cycle_preparation_operations op WHERE user_id=%s
             AND request_json->>'kind'='next' AND request_json->>'cycle_id'=%s
             AND (((request_json->'next_preparation_scope') - 'plan_revision_id')=(%s::jsonb - 'plan_revision_id')
                  OR (NOT request_json ? 'next_preparation_scope' AND NOT EXISTS (
                      SELECT 1 FROM m7_route_positions p
                      JOIN m5_cycles c ON c.id=p.cycle_db_id
                      JOIN m5_assessment_situations a ON a.id=p.current_as_db_id
                      WHERE c.cycle_id::text=%s AND a.status='closed' AND a.closed_at>op.created_at)))
           ORDER BY created_at DESC,id DESC LIMIT 1""", (user_id, cycle_id, _canonical(scope), cycle_id),
    ).fetchone()
    if not row:
        synchronous = observation.sync_for_cycle(connection, cycle_id, user_id)
        return public_operation(synchronous) if synchronous else None
    operation = dict(row)
    ProductCyclePreparationQueue._project_retry_guard(connection, operation, user_id=user_id)
    return public_operation(observation.attach(connection, operation))


def _operation_lock_key(operation_id: str) -> int:
    return int.from_bytes(hashlib.sha256(operation_id.encode()).digest()[:8], "big", signed=True)


PUBLIC_FAILURE = {
    "code": "ASSESSMENT_CYCLE_PREPARATION_FAILED",
    "message": "Подготовка завершилась с ошибкой. Обратитесь к ответственному за оценку.",
}
PUBLIC_TECHNICAL_FAILURE = {
    "code": "ASSESSMENT_CYCLE_PREPARATION_TECHNICAL_FAILURE",
    "message": "Не удалось завершить подготовку. Можно повторить её.",
}
PROGRAM_COVERAGE_UNAVAILABLE = "PILOT_PLAN_PROGRAM_COVERAGE_UNAVAILABLE"
PUBLIC_FAILURES_BY_PREFIX = {
    PROGRAM_COVERAGE_UNAVAILABLE: {
        "code": "ASSESSMENT_PROGRAM_COVERAGE_UNAVAILABLE",
        "message": "Подтверждённый профиль не позволяет составить маршрут с охватом назначенной программы.",
    },
    "M5_FUNCTIONAL_VERIFICATION_INCOMPLETE": {
        "code": "ASSESSMENT_VERIFICATION_INCOMPLETE",
        "message": "Не удалось завершить обязательную проверку материалов. Обратитесь к организатору оценки.",
    },
    "M7_NO_ADMISSIBLE_CASE": {
        "code": "ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE",
        "message": "Для роли «Специалист» в назначенной конфигурации пока нет допущенной ситуации. Обратитесь к ответственному за настройку оценки.",
    },
    "M5_FUNCTIONAL_AS_NOT_ADMITTED": {
        "code": "ASSESSMENT_AS_NOT_ADMITTED",
        "message": "Материалы ситуации не прошли обязательную проверку. Обратитесь к организатору оценки.",
    },
}
RETRYABLE_TECHNICAL_ERRORS = frozenset({"TimeoutError", "ConnectionError", "LlmGatewayError", "LlmCapacityError"})


def retry_allowed(operation: dict) -> bool:
    """Only explicitly classified technical failures permit a new preparation command."""
    return (operation.get("status") == "failed"
            and not operation.get("retry_blocked")
            and operation.get("error_code") in RETRYABLE_TECHNICAL_ERRORS
            and not any(str(operation.get("error_message") or "").startswith(prefix)
                        for prefix in PUBLIC_FAILURES_BY_PREFIX))


def public_operation(operation: dict) -> dict:
    """Return the participant-safe projection of an orchestration operation."""
    payload = {
        "operation_id": str(operation["operation_id"]),
        "status": str(operation["status"]),
    }
    if operation["status"] == "completed" and operation.get("result_json") is not None:
        payload["result"] = operation["result_json"]
    elif operation["status"] == "failed":
        internal_message = str(operation.get("error_message") or "")
        payload["retry_allowed"] = retry_allowed(operation)
        payload["error"] = dict(next((value for prefix, value in PUBLIC_FAILURES_BY_PREFIX.items()
                                      if internal_message.startswith(prefix)),
                                     PUBLIC_TECHNICAL_FAILURE if payload["retry_allowed"] else PUBLIC_FAILURE))
        if internal_message.startswith(PROGRAM_COVERAGE_UNAVAILABLE + ":"):
            try:
                covered = json.loads(internal_message.split(":", 1)[1])
                available, minimum = covered["available_target_count"], covered["minimum_target_count"]
                payload["error"]["message"] += f" Доступно целей: {available}. Требуется не менее {minimum}."
                if question := covered.get("clarification_question"):
                    payload["error"]["message"] += " " + question
                elif reasons := [reason["message"] for reason in covered.get("excluded_cases", [])
                                 if reason.get("status") == "incompatible"]:
                    payload["error"]["message"] += " " + " ".join(reasons)
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
    if operation.get("decision_status"):
        payload["decision_status"] = operation["decision_status"]
    if operation.get('preparation'):
        payload['preparation'] = {**operation['preparation'], 'allowed_actions':
            ['check'] if operation['status'] in {'queued','running'} else ['retry'] if payload.get('retry_allowed') else []}
    return payload


def needs_functional_generation(*, functional: bool, decision: dict | None) -> bool:
    """Generate only for a newly selected Case that has no persisted assignment."""
    return bool(
        functional
        and decision
        and decision.get("status") == "SELECTED"
        and not decision.get("assigned_as_db_id")
    )


class ProductCyclePreparationQueue:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="product-cycle-preparation", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            self._wake.set()
            thread, self._thread = self._thread, None
        if thread:
            thread.join(timeout=5)

    def enqueue(self, *, operation_id: str, user_id: int, request: dict) -> dict:
        from Api import m10_product_flow
        request = _command_request(request)
        with get_connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (_operation_lock_key(operation_id),))
            connection.execute("SELECT pg_advisory_xact_lock(%s, %s)", (771105, user_id))
            operation_row = connection.execute(
                """SELECT operation_id,user_id,status,result_json,error_code,error_message,
                          request_json,request_checksum,created_at,updated_at,completed_at
                   FROM product_cycle_preparation_operations
                   WHERE operation_id=%s""",
                (operation_id,),
            ).fetchone()
            if operation_row:
                result = dict(operation_row)
                if int(result["user_id"]) != int(user_id):
                    raise PermissionError("PRODUCT_CYCLE_PREPARATION_OPERATION_NOT_OWNED")
                if _command_request(result["request_json"]) != request:
                    raise ValueError("PRODUCT_CYCLE_PREPARATION_IDEMPOTENCY_CONFLICT")
                self._project_retry_guard(connection, result)
                result.pop("request_json", None)
                result.pop("request_checksum", None)
                result.pop("user_id", None)
                return observation.attach(connection, result)
            if request.get("kind") == "next":
                request["next_preparation_scope"] = m10_product_flow.next_preparation_scope(
                    connection, cycle_id=str(request["cycle_id"]), user_id=user_id,
                )
                after_as = request.get("after_assessment_situation_id")
                if after_as and after_as != request["next_preparation_scope"]["after_assessment_situation_id"]:
                    raise ValueError("PRODUCT_CYCLE_PREPARATION_POSITION_CHANGED")
            existing = connection.execute(
                """SELECT operation_id,status,result_json,error_code,error_message,request_json,
                          request_checksum,created_at,updated_at,completed_at
                   FROM product_cycle_preparation_operations op
                   WHERE user_id=%s AND status IN ('queued','running','completed','failed')
                     AND ((request_json - 'idempotency_key' - 'preparation_key')=%s::jsonb
                          OR (request_json->>'kind'='next' AND %s='next'
                              AND request_json->>'cycle_id'=%s
                              AND ((request_json->'next_preparation_scope') - 'plan_revision_id')
                                  =(%s::jsonb - 'plan_revision_id'))
                          OR (request_json->>'kind'='next' AND %s='next'
                              AND request_json->>'cycle_id'=%s
                              AND NOT request_json ? 'next_preparation_scope'
                              AND NOT EXISTS (
                                  SELECT 1 FROM m7_route_positions p
                                  JOIN m5_cycles c ON c.id=p.cycle_db_id
                                  JOIN m5_assessment_situations a ON a.id=p.current_as_db_id
                                  WHERE c.cycle_id::text=%s AND a.status='closed'
                                    AND a.closed_at>op.created_at)))
                   ORDER BY created_at DESC,id DESC LIMIT 1""",
                (user_id, _canonical(semantic_request(request)), request.get("kind"), request.get("cycle_id"),
                 _canonical(request.get("next_preparation_scope") or {}), request.get("kind"),
                 request.get("cycle_id"), request.get("cycle_id")),
            ).fetchone()
            if existing:
                result = dict(existing)
                if result["status"] == "failed":
                    self._project_retry_guard(connection, result, user_id=user_id)
                    if not retry_allowed(result):
                        raise ValueError("PRODUCT_CYCLE_PREPARATION_RETRY_NOT_ALLOWED")
                else:
                    result.pop("request_checksum", None)
                    result.pop("request_json", None)
                    return observation.attach(connection, result)
            request["preparation_key"] = ((existing["request_json"].get("preparation_key")
                or existing["request_json"]["idempotency_key"]) if existing else request["idempotency_key"])
            self._guard_request(connection, request, user_id=user_id)
            request_text = _canonical(request)
            request_checksum = hashlib.sha256(request_text.encode()).hexdigest()
            active = connection.execute("""SELECT id,request_json,created_at
                FROM product_cycle_preparation_operations
                WHERE user_id=%s AND status IN ('queued','running')
                FOR UPDATE""", (user_id,)).fetchall()
            for pending in active:
                try:
                    self._guard_request(connection, pending['request_json'], user_id=user_id,
                                        created_at=pending['created_at'], lock=False)
                except ValueError:
                    # The persisted one-active-user index is retained. A revoked
                    # generation's queued/running command cannot block its successor.
                    connection.execute("""UPDATE product_cycle_preparation_operations
                        SET status='failed',error_code='ValueError',
                            error_message='PRODUCT_CYCLE_PREPARATION_ASSIGNMENT_SCOPE_CHANGED',
                            completed_at=NOW(),updated_at=NOW(),locked_at=NULL,attempt_token=NULL
                        WHERE id=%s AND status IN ('queued','running')""", (pending['id'],))
                else:
                    raise ValueError('PRODUCT_CYCLE_PREPARATION_SCOPE_BUSY')
            row = connection.execute(
                """INSERT INTO product_cycle_preparation_operations
                   (operation_id,user_id,request_json,request_checksum)
                   VALUES (%s,%s,%s::jsonb,%s)
                   RETURNING operation_id,status,result_json,error_code,error_message,created_at,updated_at,completed_at""",
                (operation_id, user_id, request_text, request_checksum),
            ).fetchone()
            connection.execute('''INSERT INTO preparation_observations
                (source,operation_id,attempt_token,kind,stage,history_json) VALUES
                ('cycle',%s,'queued',%s,'queued',jsonb_build_array(jsonb_build_object('stage','queued','at',NOW())))
                ON CONFLICT(source,operation_id,attempt_token) DO NOTHING''',
                (operation_id, 'next' if request.get('kind') == 'next' else 'assessment'))
        self._wake.set()
        with get_connection() as connection:
            return observation.attach(connection, dict(row))

    def get_status(self, operation_id: str) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT operation_id,user_id,status,attempt_token,attempts,result_json,error_code,error_message,
                          created_at,updated_at,completed_at
                   FROM product_cycle_preparation_operations WHERE operation_id=%s""",
                (operation_id,),
            ).fetchone()
            return observation.attach(connection, dict(row)) if row else None

    def get_owned_status(self, operation_id: str, user_id: int) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(
                """SELECT operation_id,user_id,status,attempt_token,attempts,result_json,error_code,error_message,request_json,
                          created_at,updated_at,completed_at
                   FROM product_cycle_preparation_operations
                   WHERE operation_id=%s AND user_id=%s""",
                (operation_id, user_id),
            ).fetchone()
            if row:
                result = dict(row)
                self._project_retry_guard(connection, result, user_id=user_id)
                return observation.attach(connection, result)
            return observation.sync_owned(connection, operation_id, user_id)

    @staticmethod
    def _guard_request(connection, request: dict, *, user_id: int, created_at=None, lock: bool = True) -> None:
        from Api import m10_product_flow
        if request.get("kind") == "next":
            current = m10_product_flow.next_preparation_scope(
                connection, cycle_id=str(request["cycle_id"]), user_id=user_id, lock=lock,
            )
            if not request.get("next_preparation_scope") and created_at is not None and connection.execute(
                """SELECT 1 FROM m7_route_positions p JOIN m5_cycles c ON c.id=p.cycle_db_id
                   JOIN m5_assessment_situations s ON s.id=p.current_as_db_id
                   WHERE c.cycle_id=%s AND s.status='closed' AND s.closed_at>%s LIMIT 1""",
                (request["cycle_id"], created_at),
            ).fetchone():
                raise ValueError("PRODUCT_CYCLE_PREPARATION_POSITION_CHANGED")
            if request.get("next_preparation_scope") and current != request["next_preparation_scope"]:
                raise ValueError("PRODUCT_CYCLE_PREPARATION_POSITION_CHANGED")
        else:
            if request.get('assignment_ref'):
                from Api import acquaintance
                current_scope = acquaintance.preparation_scope(connection, user_id=user_id,
                    profile_id=request.get('personalized_profile_id'))
                if current_scope is None or any(request.get(name) != current_scope.get(name)
                        for name in ('organization_id', 'assignment_ref', 'questionnaire_revision_id',
                                     'personalized_profile_id', 'profile_checksum', 'assignment_id')):
                    raise ValueError('PRODUCT_CYCLE_PREPARATION_ASSIGNMENT_SCOPE_CHANGED')
            # Stable domain key also finds a terminal first Cycle, which must not
            # be replaced by a new Cycle when a technical failure is retried.
            key = request.get("preparation_key", request["idempotency_key"])
            cycle = connection.execute(
                """SELECT c.cycle_id FROM m7_plan_request_keys k
                   JOIN m7_cycle_plans p ON p.id=k.plan_id JOIN m5_cycles c ON c.id=p.cycle_db_id
                   WHERE k.created_by=%s AND k.key=%s""", (user_id, f"product-prepare:{key}"),
            ).fetchone()
            if cycle:
                m10_product_flow.require_preparation_cycle(
                    connection, cycle_id=str(cycle["cycle_id"]), user_id=user_id, lock=lock,
                )
        key = request.get("preparation_key", request["idempotency_key"])
        selection_key = f"product-next:{key}" if request.get("kind") == "next" else f"product-prepared:{key}"
        selected = connection.execute(
            """SELECT cv.id,c.usage_scope,c.catalog_ref_json,d.plan_revision_id,c.cycle_id
               FROM m7_next_as_requests k JOIN m7_route_decisions d ON d.id=k.decision_id
               JOIN m5_cycles c ON c.id=d.cycle_db_id
               JOIN m5_case_versions cv ON cv.case_id=d.selected_case_id AND cv.case_version=d.selected_case_version
               JOIN m5_catalog_case_versions member ON member.case_version_id=cv.id
                 AND member.catalog_db_id=(c.catalog_ref_json->>'db_id')::bigint
               WHERE c.owner_user_id=%s AND k.key=%s""", (user_id, selection_key),
        ).fetchone()
        if selected:
            from Api.m5_catalog_integrity import case_admission
            from Api import m7_cycle_planner
            plan = m7_cycle_planner.read_plan(connection, str(selected["cycle_id"]))
            if str(plan["revision_id"]) != str(selected["plan_revision_id"]):
                raise ValueError("M7_STALE_PLAN_REVISION")
            admitted = case_admission(connection, case_version_id=int(selected["id"]),
                usage_scope=selected["usage_scope"], catalog_db_id=selected["catalog_ref_json"]["db_id"])
            if not admitted["admitted"]:
                raise ValueError("AS_NOT_ADMITTED")

    @classmethod
    def _project_retry_guard(cls, connection, operation: dict, *, user_id: int | None = None) -> None:
        if not retry_allowed(operation):
            return
        try:
            cls._guard_request(connection, operation["request_json"],
                               user_id=user_id if user_id is not None else int(operation["user_id"]),
                               created_at=operation.get("created_at"), lock=False)
        except ValueError:
            operation["retry_blocked"] = True

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._claim()
                if job is None:
                    self._wake.wait(timeout=1.0)
                    self._wake.clear()
                    continue
                self._process(job)
            except Exception:
                logger.exception("Product Cycle preparation worker loop failed")
                self._stop.wait(timeout=1.0)

    def _claim(self) -> dict | None:
        with get_connection() as connection:
            observation.notice_delays(connection)
            connection.execute(
                """UPDATE product_cycle_preparation_operations
                   SET status='queued',worker_id=NULL,attempt_token=NULL,locked_at=NULL,updated_at=NOW()
                   WHERE status='running' AND locked_at < NOW() - INTERVAL '10 minutes'"""
            )
            connection.execute('''UPDATE preparation_observations p SET status='lease_expired',error_category='lease_expired'
                WHERE p.source='cycle' AND p.status='running' AND p.attempt_token<>'queued'
                  AND EXISTS(SELECT 1 FROM product_cycle_preparation_operations op
                    WHERE op.operation_id=p.operation_id AND op.status='queued' AND op.attempts>0)''')
            row = connection.execute(
                """SELECT id,operation_id,user_id,request_json,request_checksum
                   FROM product_cycle_preparation_operations WHERE status='queued'
                   ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"""
            ).fetchone()
            if not row:
                return None
            attempt_token = uuid4()
            claimed = connection.execute(
                """UPDATE product_cycle_preparation_operations
                   SET status='running',attempts=attempts+1,worker_id=%s,attempt_token=%s,
                       locked_at=NOW(),updated_at=NOW()
                   WHERE id=%s
                   RETURNING id,operation_id,user_id,request_json,request_checksum,attempt_token,created_at""",
                (self._worker_id, attempt_token, row["id"]),
            ).fetchone()
        return dict(claimed)

    @staticmethod
    def _assert_current_attempt(connection, job: dict, *, lock: bool = False) -> None:
        suffix = " FOR UPDATE" if lock else ""
        row = connection.execute(
            "SELECT status,attempt_token FROM product_cycle_preparation_operations "
            f"WHERE id=%s{suffix}",
            (job["id"],),
        ).fetchone()
        if not row or row["status"] != "running" or row["attempt_token"] != job["attempt_token"]:
            raise RuntimeError("PRODUCT_CYCLE_PREPARATION_ATTEMPT_STALE")

    @contextmanager
    def _lease_heartbeat(self, job: dict):
        stop = threading.Event()

        def heartbeat() -> None:
            while not stop.wait(HEARTBEAT_INTERVAL_SECONDS):
                try:
                    with get_connection() as connection:
                        connection.execute(
                            """UPDATE product_cycle_preparation_operations
                               SET locked_at=NOW(),updated_at=NOW()
                               WHERE id=%s AND status='running' AND attempt_token=%s""",
                            (job["id"], job["attempt_token"]),
                        )
                    observation.record(('cycle', str(job['operation_id']), str(job['attempt_token']), get_connection,
                        'next' if job['request_json'].get('kind') == 'next' else 'assessment'), heartbeat=True)
                except Exception:
                    logger.exception(
                        "Product Cycle preparation heartbeat failed operation_id=%s",
                        job["operation_id"],
                    )

        thread = threading.Thread(
            target=heartbeat,
            name=f"product-cycle-preparation-heartbeat-{job['id']}",
            daemon=True,
        )
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=1.0)

    def _process(self, job: dict) -> None:
        try:
            with self._lease_heartbeat(job):
                observer = observation.begin('cycle', job['operation_id'], job['attempt_token'],
                    'next' if job['request_json'].get('kind') == 'next' else 'assessment',
                    'unknown', factory=get_connection)
                with observation.observing(observer):
                    self._process_current_attempt(job)
            return
        except Exception as exc:
            if str(exc) == "PRODUCT_CYCLE_PREPARATION_ATTEMPT_STALE":
                logger.info("Discarded stale Product Cycle preparation attempt operation_id=%s", job["operation_id"])
                return
            logger.exception("Product Cycle preparation failed operation_id=%s", job["operation_id"])
            with get_connection() as connection:
                connection.execute(
                    """UPDATE product_cycle_preparation_operations
                       SET status='failed',result_json=%s::jsonb,error_code=%s,error_message=%s,
                           completed_at=NOW(),updated_at=NOW(),locked_at=NULL,attempt_token=NULL
                       WHERE id=%s AND status='running' AND attempt_token=%s""",
                    (json.dumps(jsonable_encoder(getattr(exc, "failure_result", None)), ensure_ascii=False)
                     if getattr(exc, "failure_result", None) else None,
                     type(exc).__name__, str(exc)[:2000], job["id"], job["attempt_token"]),
                )
                connection.execute('''UPDATE preparation_observations SET
                    status=CASE WHEN status='lease_expired' THEN status ELSE 'failed' END,
                    error_category=COALESCE(error_category,%s)
                    WHERE source='cycle' AND operation_id=%s AND attempt_token=%s''',
                    (type(exc).__name__,str(job['operation_id']),str(job['attempt_token'])))

    def _process_current_attempt(self, job: dict) -> None:
        from Api import m10_product_flow, m7_cycle_planner, m5_battery_profile
        from Api.llm.deepseek_gateway import DeepSeekGateway
        from Api.llm.provider_contract import load_provider_contract
        from Api import m5_functional_generation_service
        from Api.m5_passport_generation import AS_PACKAGE
        from Api.m5_runtime_rules import resolve_preparation_binding
        from Api.m5_storage import resolve_cycle_base_role
        from Api.cycle_execution_manifest import resolve_cycle_dependency, resolve_review_response

        failure_result = None
        try:
            request = dict(job["request_json"])
            preparation_key = str(request.get("preparation_key", request["idempotency_key"]))
            if hashlib.sha256(_canonical(request).encode()).hexdigest() != job["request_checksum"]:
                raise ValueError("PRODUCT_CYCLE_PREPARATION_SNAPSHOT_MISMATCH")
            with get_connection() as connection:
                self._assert_current_attempt(connection, job, lock=True)
                self._guard_request(connection, request, user_id=int(job["user_id"]), created_at=job.get("created_at"))
                next_cycle_id = request.get("cycle_id") if request.get("kind") == "next" else None
                if next_cycle_id:
                    existing_cycle = connection.execute(
                        """SELECT cycle_id,personalized_profile_id FROM m5_cycles
                           WHERE cycle_id=%s AND owner_user_id=%s""",
                        (next_cycle_id, job["user_id"]),
                    ).fetchone()
                    if not existing_cycle:
                        raise ValueError("M7_CYCLE_NOT_FOUND")
                else:
                    existing_cycle = connection.execute(
                        """SELECT c.cycle_id,c.personalized_profile_id FROM m7_plan_request_keys k
                           JOIN m7_cycle_plans p ON p.id=k.plan_id JOIN m5_cycles c ON c.id=p.cycle_db_id
                           WHERE k.created_by=%s AND k.key=%s""",
                        (job["user_id"], f"product-prepare:{preparation_key}"),
                    ).fetchone()
                profile_id = (existing_cycle["personalized_profile_id"] if existing_cycle else
                              m10_product_flow._owned_profile(
                                  connection, int(job["user_id"]), request.get("personalized_profile_id"),
                              ))
                profile = _owned_profile_snapshot(connection, profile_id=profile_id, user_id=job["user_id"])
                if request.get('profile_checksum') and (not profile or profile['checksum'] != request['profile_checksum']
                        or profile['organization_id'] != request.get('organization_id')):
                    raise ValueError('PRODUCT_CYCLE_PREPARATION_PROFILE_SCOPE_CHANGED')
                if existing_cycle:
                    functional = m10_product_flow.uses_functional_generation(
                        connection, cycle_id=str(existing_cycle["cycle_id"]),
                    )
                else:
                    catalog_column = connection.execute("""SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema=current_schema() AND table_name='assessment_configurations'
                          AND column_name='catalog_version_id') AS available""").fetchone()["available"]
                    functional = bool(profile and catalog_column and connection.execute("""SELECT 1 FROM assessment_configurations c
                        JOIN m5_catalogs catalog ON catalog.id=c.catalog_version_id
                        JOIN m5_catalog_case_versions member ON member.catalog_db_id=catalog.id
                        JOIN m5_case_versions cv ON cv.id=member.case_version_id
                        WHERE c.id=%s AND (cv.case_id LIKE 'CASE.SPEC.%%'
                            OR cv.content_json->>'schema_version'='4') LIMIT 1""",
                        (profile["assessment_configuration_id"],)).fetchone())
                fit_review = {}
                if functional and not existing_cycle and profile:
                    designs = m5_battery_profile.configuration_designs(
                        connection, configuration_id=profile["assessment_configuration_id"],
                    )
                    if designs:
                        provider = load_provider_contract()
                        connection.rollback()
                        observation.progress("plan")
                        fit_review = m5_battery_profile.review(
                            profile["content_json"], designs, DeepSeekGateway(
                                base_url=provider["endpoint"].removesuffix("/chat/completions"), model=provider["model"],
                            ), operation_id=str(job["operation_id"]),
                        )
                        self._assert_current_attempt(connection, job, lock=True)
                        self._guard_request(connection, request, user_id=int(job["user_id"]), created_at=job.get("created_at"))
                        current_profile = _owned_profile_snapshot(connection, profile_id=profile_id, user_id=job["user_id"])
                        if current_profile != profile:
                            raise ValueError("PRODUCT_CYCLE_PREPARATION_PROFILE_SCOPE_CHANGED")
                if next_cycle_id:
                    result = m10_product_flow.prepare_next_situation(
                        connection, cycle_id=str(next_cycle_id), user_id=int(job["user_id"]),
                        key=preparation_key, defer_as=functional,
                    )
                else:
                    result = m10_product_flow.prepare(
                        connection, user_id=int(job["user_id"]), key=preparation_key,
                        selected_skills=list(request["selected_skills"]), profile_id=profile_id,
                        defer_as=functional, exact_profile=bool(request.get('assignment_ref')),
                        profile_fit=fit_review,
                    )
                decision = result["decision"]
                needs_generation = needs_functional_generation(
                    functional=functional,
                    decision=decision,
                )
                if needs_generation:
                    frozen_cycle = connection.execute(
                        "SELECT * FROM m5_cycles WHERE cycle_id=%s", (str(result["plan"]["cycle_id"]),)
                    ).fetchone()
                    if frozen_cycle["personalized_profile_id"] != profile_id:
                        profile = _owned_profile_snapshot(
                            connection, profile_id=frozen_cycle["personalized_profile_id"], user_id=job["user_id"],
                        )
                    if not profile or profile["checksum"] != frozen_cycle["profile_ref_json"]["checksum"]:
                        raise ValueError("PRODUCT_CYCLE_PREPARATION_PROFILE_SCOPE_CHANGED")
                    frozen_profile = dict(profile["content_json"])
                    catalog_db_id = (frozen_cycle["catalog_ref_json"] or {}).get("db_id")
                    frozen_case_row = connection.execute(
                        "SELECT cv.id,cv.content_json,cv.content_checksum,member.runtime_rule_version_id,"
                        "p.package_id,p.package_version FROM m5_case_versions cv "
                        "JOIN m5_packages p ON p.id=cv.package_id "
                        "JOIN m5_catalog_case_versions member ON member.case_version_id=cv.id "
                        "WHERE member.catalog_db_id=%s AND cv.case_id=%s AND cv.case_version=%s",
                        (catalog_db_id, decision["selected_case_id"], decision["selected_case_version"]),
                    ).fetchone()
                    if not frozen_case_row:
                        raise ValueError("M5_FUNCTIONAL_CASE_VERSION_NOT_FOUND")
                    frozen_case = dict(frozen_case_row["content_json"])
                    frozen_case_checksum = frozen_case_row["content_checksum"]
                    generation_package_ref = {
                        "id": frozen_case_row["package_id"], "version": frozen_case_row["package_version"],
                        "compiler": {"source_schema_profile": "functional-passport-v1"},
                    }
                    selected_base_role = resolve_cycle_base_role(connection, frozen_cycle, frozen_profile)
                    execution_manifest = frozen_cycle["execution_manifest_json"] or {}
                    dependencies = execution_manifest.get("dependencies", {})
                    as_package = (resolve_cycle_dependency(dict(frozen_cycle), "m5_functional_as")
                                  if "m5_functional_as" in dependencies else AS_PACKAGE)
                    project_role = execution_manifest.get("runtime_refs", {}).get("project_role")
                    project_role_prompt = (
                        resolve_cycle_dependency(dict(frozen_cycle), "m5_educational_role_interactions")
                        if project_role is not None else None
                    )
                    m2_path = resolve_cycle_dependency(dict(frozen_cycle), "m2_methodology") / "methodology.json"
                    m3_path = resolve_cycle_dependency(dict(frozen_cycle), "m3_role_profiles") / "base_roles.json"
                    runtime_rule_ref = resolve_preparation_binding(connection, frozen_case_row)
                    provider_path = resolve_cycle_dependency(dict(frozen_cycle), "provider_contract") / "manifest.json"
                    profile_fit = next((row["profile_fit"] for row in result["plan"]["plan"]["route"]
                                        if row["case_id"] == decision["selected_case_id"] and "profile_fit" in row), None)
            saving_started = perf_counter()
            if needs_generation:
                with get_connection() as connection:
                    self._assert_current_attempt(connection, job)
                snapshot = m5_functional_generation_service.build_passport_snapshot(
                    case_version=frozen_case, profile=frozen_profile,
                    operation_id=str(job["operation_id"]), synthetic=False,
                    profile_checksum=profile["checksum"], case_version_checksum=frozen_case_checksum,
                    profile_sources={key: profile[key + "_version_id"] for key in (
                        "organization_context", "role_profile", "user_context",
                    )},
                    selected_base_role=selected_base_role, as_package=as_package,
                    review_response_package=resolve_review_response(frozen_cycle),
                    m2_path=m2_path, m3_path=m3_path, runtime_rule_ref=runtime_rule_ref,
                    package_ref=generation_package_ref, battery_profile_fit=profile_fit,
                    provider_contract=load_provider_contract(provider_path),
                    project_role=project_role, project_role_prompt=project_role_prompt,
                    battery_pilot=(frozen_cycle.get("catalog_ref_json") or {}).get("battery_pilot") is True,
                    battery_scenario_package=(resolve_cycle_dependency(dict(frozen_cycle), "m5_battery_scenario")
                                              if "m5_battery_scenario" in dependencies else None),
                )
                provider = snapshot["refs"]["provider_contract"]
                try:
                    generation_gateway = DeepSeekGateway(
                        base_url=provider["endpoint"].removesuffix("/chat/completions"),
                        model=provider["model"],
                    )
                except TypeError:
                    # Test/injected transports may intentionally expose no constructor options;
                    # their sent identity remains captured in the immutable operation trace.
                    generation_gateway = DeepSeekGateway()
                generated = m5_functional_generation_service.prepare(snapshot, generation_gateway)
                if not generated["admitted_for_participant"]:
                    failure_result = {
                        "stage": "functional_tester_admission",
                        "plan": {"cycle_id": str(result["plan"]["cycle_id"])},
                        "generated": generated,
                    }
                    outcome = generated["tester"]["aggregation"]["status"]
                    failure_code = ("M5_FUNCTIONAL_VERIFICATION_INCOMPLETE" if outcome == "INCOMPLETE"
                                    else "M5_FUNCTIONAL_AS_NOT_ADMITTED")
                    raise ValueError(failure_code + ":" + outcome)
                saving_started = perf_counter()
                trace = m5_functional_generation_service.build_persistence_trace(snapshot, generated)
                if "review_response" in snapshot["refs"]:
                    from Api.assessment_start_readiness import functional_gate

                    functional_gate(trace, operation_id=str(job["operation_id"]), cycle=frozen_cycle,
                                    case_version=frozen_case)
                with get_connection() as connection:
                    self._assert_current_attempt(connection, job, lock=True)
                    self._guard_request(connection, request, user_id=int(job["user_id"]), created_at=job.get("created_at"))
                    m10_product_flow.require_preparation_cycle(connection,
                        cycle_id=str(result["plan"]["cycle_id"]), user_id=int(job["user_id"]))
                    attached = m7_cycle_planner.attach_functional_generated_as(
                        connection, decision_id=str(decision["id"]), prepared_result=generated,
                        generation_trace=trace, created_by=int(job["user_id"]),
                        policy=m10_product_flow._policy(connection, cycle_id=str(result["plan"]["cycle_id"])),
                    )
                    result["decision"] = attached
                    result["plan"] = m7_cycle_planner.read_plan(connection, str(result["plan"]["cycle_id"]))
            with get_connection() as connection:
                self._assert_current_attempt(connection, job, lock=True)
                self._guard_request(connection, request, user_id=int(job["user_id"]), created_at=job.get("created_at"))
                runtime = m10_product_flow.read_runtime(connection, cycle_id=str(result["plan"]["cycle_id"]))
                participant_result = {**m10_product_flow.participant_presentation(result), "runtime": runtime}
                connection.execute(
                    """UPDATE product_cycle_preparation_operations
                       SET status='completed',result_json=%s::jsonb,completed_at=clock_timestamp(),updated_at=clock_timestamp(),
                           locked_at=NULL,attempt_token=NULL
                       WHERE id=%s AND status='running' AND attempt_token=%s""",
                    (json.dumps(jsonable_encoder(participant_result), ensure_ascii=False),
                     job["id"], job["attempt_token"]),
                )
                connection.execute("""UPDATE preparation_observations SET status='completed',
                    scope_json=scope_json || jsonb_build_object('ready_persistence_ms',%s::double precision)
                    WHERE source='cycle' AND operation_id=%s AND attempt_token=%s""",
                    (round((perf_counter() - saving_started) * 1000, 3),
                     str(job['operation_id']), str(job['attempt_token'])))
        except Exception as exc:
            if failure_result is not None:
                setattr(exc, "failure_result", failure_result)
            raise


product_cycle_preparation_queue = ProductCyclePreparationQueue()
