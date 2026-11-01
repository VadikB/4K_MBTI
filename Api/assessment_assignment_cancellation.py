"""Atomic cancellation of one exact organization assessment assignment generation."""
from __future__ import annotations

import hashlib
import json


class CancellationError(ValueError):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS organization_assessment_cancellation_operations (
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        actor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        operation_id TEXT NOT NULL,
        assignment_id BIGINT NOT NULL REFERENCES organization_assessment_assignments(id) ON DELETE RESTRICT,
        request_fingerprint TEXT NOT NULL,
        result_status TEXT NOT NULL,
        cancelled_at TIMESTAMP WITHOUT TIME ZONE,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
        PRIMARY KEY(organization_id,actor_user_id,operation_id)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS organization_assessment_assignment_audit (
        id BIGSERIAL PRIMARY KEY,
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        assignment_id BIGINT NOT NULL REFERENCES organization_assessment_assignments(id) ON DELETE RESTRICT,
        recipient_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        actor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        operation_id TEXT NOT NULL,
        previous_status TEXT NOT NULL,
        new_status TEXT NOT NULL,
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
        UNIQUE(organization_id,actor_user_id,operation_id)
    )""")


def _fingerprint(organization_id: int, assignment_id: int) -> str:
    value = {"organization_id": int(organization_id), "assignment_id": int(assignment_id)}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def cancel(connection, *, organization_id: int, assignment_id: int,
           actor_user_id: int, operation_id: str) -> dict:
    fingerprint = _fingerprint(organization_id, assignment_id)
    scope = connection.execute("""SELECT id,recipient_user_id FROM organization_assessment_assignments
        WHERE id=%s AND organization_id=%s""", (assignment_id, organization_id)).fetchone()
    if not scope:
        raise CancellationError("ASSIGNMENT_NOT_FOUND", 404)
    recipient_user_id = int(scope["recipient_user_id"])
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (recipient_user_id,))
    assignment = connection.execute("""SELECT * FROM organization_assessment_assignments
        WHERE id=%s AND organization_id=%s FOR UPDATE""", (assignment_id, organization_id)).fetchone()
    if not assignment:
        raise CancellationError("ASSIGNMENT_NOT_FOUND", 404)
    prior = connection.execute("""SELECT * FROM organization_assessment_cancellation_operations
        WHERE organization_id=%s AND actor_user_id=%s AND operation_id=%s""",
        (organization_id, actor_user_id, operation_id)).fetchone()
    if prior:
        if prior["request_fingerprint"] != fingerprint:
            raise CancellationError("ASSIGNMENT_CANCEL_IDEMPOTENCY_CONFLICT")
        return _result(assignment, operation_id, prior.get("cancelled_at"))
    if assignment["status"] == "revoked" and assignment.get("revoked_at") is not None:
        connection.execute("""INSERT INTO organization_assessment_cancellation_operations
            (organization_id,actor_user_id,operation_id,assignment_id,request_fingerprint,result_status,cancelled_at)
            VALUES(%s,%s,%s,%s,%s,'revoked',%s)""",
            (organization_id, actor_user_id, operation_id, assignment_id, fingerprint, assignment["revoked_at"]))
        return _result(assignment, operation_id, assignment["revoked_at"])
    cycles = connection.execute("""SELECT status,started_at FROM m5_cycles
        WHERE assignment_id=%s FOR UPDATE""", (assignment_id,)).fetchall()
    if any(row.get("started_at") is not None or row.get("status") != "prepared" for row in cycles):
        raise CancellationError("ASSIGNMENT_ALREADY_STARTED")
    if not cycles and connection.execute("""SELECT 1 FROM m5_cycles cycle
        JOIN participant_acquaintance_confirmations confirmation
          ON confirmation.personalized_profile_id=cycle.personalized_profile_id
         AND confirmation.user_id=cycle.owner_user_id
         AND confirmation.organization_id=cycle.organization_id
        JOIN organization_assessment_source_bindings binding
          ON binding.assignment_id=%s
         AND binding.questionnaire_revision_id=confirmation.questionnaire_revision_id
        WHERE cycle.assignment_id IS NULL AND cycle.owner_user_id=%s AND cycle.organization_id=%s
          AND confirmation.assignment_ref=%s AND cycle.usage_scope='assessment'
        LIMIT 1 FOR UPDATE OF cycle""",
        (assignment_id, recipient_user_id, organization_id, assignment["assignment_ref"])).fetchone():
        raise CancellationError("ASSIGNMENT_LINK_UNKNOWN")
    if assignment["status"] == "active" and assignment.get("revoked_at") is None:
        changed = connection.execute("""UPDATE organization_assessment_assignments
            SET status='revoked',revoked_at=(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
            WHERE id=%s AND status='active' AND revoked_at IS NULL RETURNING *""", (assignment_id,)).fetchone()
        if not changed:
            raise CancellationError("ASSIGNMENT_STATE_STALE")
        assignment = changed
        connection.execute("""INSERT INTO organization_assessment_assignment_audit
            (organization_id,assignment_id,recipient_user_id,actor_user_id,operation_id,previous_status,new_status)
            VALUES(%s,%s,%s,%s,%s,'active','revoked')""",
            (organization_id, assignment_id, recipient_user_id, actor_user_id, operation_id))
    else:
        raise CancellationError("ASSIGNMENT_STATE_STALE")
    connection.execute("""INSERT INTO organization_assessment_cancellation_operations
        (organization_id,actor_user_id,operation_id,assignment_id,request_fingerprint,result_status,cancelled_at)
        VALUES(%s,%s,%s,%s,%s,'revoked',%s)""",
        (organization_id, actor_user_id, operation_id, assignment_id, fingerprint, assignment["revoked_at"]))
    return _result(assignment, operation_id, assignment["revoked_at"])


def _result(assignment: dict, operation_id: str, cancelled_at) -> dict:
    return {
        "assignment_id": int(assignment["id"]), "organization_id": int(assignment["organization_id"]),
        "recipient_user_id": int(assignment["recipient_user_id"]),
        "assignment_ref": str(assignment["assignment_ref"]), "status": "revoked",
        "operation_id": operation_id, "cancelled_at": cancelled_at or assignment["revoked_at"],
    }
