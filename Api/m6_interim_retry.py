"""Operator retry for a failed product M6 Evidence request at the current C-45."""
import json
from dataclasses import dataclass
from uuid import UUID

from Api import m6_repository, m6_worker_v2
from Api.m5_cycle_runtime import _remaining_collecting_seconds
from Api.m5_scenario_runtime import latest_material_sequence


@dataclass(frozen=True)
class RetryTarget:
    assignment_id: int
    cycle_id: UUID
    situation_id: UUID
    handoff_id: UUID
    request_id: UUID
    failed_attempt: int


class RetryRefused(ValueError):
    pass


def _inspect(db, target: RetryTarget, *, lock: bool) -> dict:
    # Product mutations take locks in Cycle -> AS -> M6 request order.
    cycle = db.execute("""SELECT c.id,c.status,c.collection_closed_at,c.time_budget_seconds,
          c.started_at + make_interval(secs=>c.calendar_window_seconds) AS deadline,
          a.status='active' AND a.revoked_at IS NULL AS assignment_active
        FROM m5_cycles c JOIN organization_assessment_assignments a ON a.id=c.assignment_id
          AND a.organization_id=c.organization_id AND a.recipient_user_id=c.owner_user_id
        WHERE c.cycle_id=%s AND c.assignment_id=%s AND c.usage_scope='assessment'"""
        + (" FOR UPDATE OF c" if lock else ""), (target.cycle_id, target.assignment_id)).fetchone()
    if cycle is None:
        raise RetryRefused("M6_RETRY_ASSIGNMENT_CYCLE_MISMATCH")
    situation = db.execute("""SELECT id,status FROM m5_assessment_situations
        WHERE cycle_db_id=%s AND assessment_situation_id=%s AND usage_scope='assessment'"""
        + (" FOR UPDATE" if lock else ""), (cycle["id"], target.situation_id)).fetchone()
    if situation is None:
        raise RetryRefused("M6_RETRY_SITUATION_MISMATCH")
    request = db.execute("""SELECT r.status,r.lease_token,r.lease_expires_at,
          h.boundary_sequence,h.receiver_status,
          r.input_json#>>'{material_revision,boundary_sequence}' AS input_boundary,
          r.input_json->>'as_id' AS input_as_id,r.input_json->>'cycle_id' AS input_cycle_id,
          r.input_json#>>'{handoff_ref,id}' AS input_handoff_id,
          r.input_json#>>'{handoff_ref,checksum}' AS input_handoff_hash,h.envelope_checksum
        FROM m6_processing_requests r JOIN m5_c45_handoffs h ON h.handoff_id=r.handoff_id
          AND h.assessment_situation_db_id=r.as_db_id
        WHERE r.id=%s AND r.as_db_id=%s AND r.handoff_id=%s AND r.mode='interim' AND h.mode='interim'
          AND r.mechanism_json->>'ref'='m6_evidence/1.0.1' AND NOT r.synthetic_confirmed"""
        + (" FOR UPDATE OF r" if lock else ""), (target.request_id, situation["id"], target.handoff_id)).fetchone()
    if request is None:
        raise RetryRefused("M6_RETRY_REQUEST_HANDOFF_MISMATCH")

    attempt = db.execute("""SELECT a.attempt_no,a.status,a.error_code,
          EXISTS (SELECT 1 FROM m6_processing_attempts source
                  WHERE source.request_id=a.request_id AND source.attempt_no=%s AND source.status='failed') AS source_failed,
          (SELECT id FROM m6_analysis_revisions revision WHERE revision.request_id=a.request_id) AS analysis_revision_id
        FROM m6_processing_attempts a WHERE a.request_id=%s ORDER BY a.attempt_no DESC LIMIT 1""",
        (target.failed_attempt, target.request_id)).fetchone()
    if not attempt or not attempt["source_failed"]:
        raise RetryRefused("M6_RETRY_EXPECTED_FAILED_ATTEMPT_NOT_FOUND")
    summary = {
        "assignment_id": target.assignment_id, "cycle_id": target.cycle_id,
        "assessment_situation_id": target.situation_id, "handoff_id": target.handoff_id,
        "request_id": target.request_id, "boundary_sequence": request["boundary_sequence"],
        "calendar_deadline": cycle["deadline"], "request_status": request["status"],
        "attempt_no": attempt["attempt_no"], "attempt_status": attempt["status"],
        "error_code": attempt["error_code"], "analysis_revision_id": attempt["analysis_revision_id"],
        "eligible": False, "started": False,
    }
    # A replay still reads the same request after later attempts or route progress.
    if attempt["attempt_no"] > target.failed_attempt or request["status"] in {"running", "succeeded"}:
        return summary
    if request["status"] != "failed" or request["lease_token"] or request["lease_expires_at"]:
        raise RetryRefused("M6_RETRY_REQUEST_NOT_FAILED")
    current = db.execute("""SELECT EXISTS (SELECT 1 FROM m7_route_positions p
          WHERE p.cycle_db_id=%s AND p.current_as_db_id=%s AND p.state='in_progress') AS current_as,
          clock_timestamp() AS checked_at""", (cycle["id"], situation["id"])).fetchone()
    if (not cycle["assignment_active"] or cycle["status"] != "active" or cycle["collection_closed_at"]
            or not cycle["deadline"] or current["checked_at"] >= cycle["deadline"]
            or _remaining_collecting_seconds(db, cycle) <= 0):
        raise RetryRefused("M6_RETRY_CYCLE_NOT_OPEN")
    if not current["current_as"] or situation["status"] != "scenario_ended":
        raise RetryRefused("M6_RETRY_SITUATION_NOT_CURRENT")
    latest = db.execute("""SELECT handoff_id FROM m5_c45_handoffs
        WHERE assessment_situation_db_id=%s AND mode='interim'
        ORDER BY boundary_sequence DESC LIMIT 1""", (situation["id"],)).fetchone()
    if (not latest or latest["handoff_id"] != target.handoff_id or request["receiver_status"] != "accepted"
            or request["boundary_sequence"] != latest_material_sequence(db, situation["id"])
            or request["input_boundary"] != str(request["boundary_sequence"])
            or request["input_as_id"] != str(target.situation_id)
            or request["input_cycle_id"] != str(target.cycle_id)
            or request["input_handoff_id"] != str(target.handoff_id)
            or request["input_handoff_hash"] != request["envelope_checksum"]):
        raise RetryRefused("M6_RETRY_STALE_C45")
    return {**summary, "eligible": True}


def retry(target: RetryTarget, *, connection_factory, apply: bool = False, operator: str = "", gateway=None) -> dict:
    if apply and not operator:
        raise RetryRefused("M6_RETRY_OPERATOR_REQUIRED")
    with connection_factory() as db:
        if not apply:
            db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        result = _inspect(db, target, lock=apply)
        if not apply or not result["eligible"]:
            return result
        job = m6_repository.claim(db, target.request_id)
        audit = {"operator_retry": {"principal": operator, "source_attempt_no": target.failed_attempt}}
        db.execute("UPDATE m6_processing_attempts SET trace_json=%s::jsonb WHERE id=%s",
                   (json.dumps(audit), job["attempt_id"]))
        db.commit()
    m6_worker_v2.process_claimed_request(job, connection_factory=connection_factory, gateway=gateway,
                                         claim_trace=audit)
    with connection_factory() as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        return {**_inspect(db, target, lock=False), "started": True}
