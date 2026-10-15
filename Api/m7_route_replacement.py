from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum


TERMINAL_CYCLE = {"collection_closed", "calculation_pending", "calculated", "failed"}
runtime_provider = None


class ReplacementProvider(Protocol):
    """PM-03 boundary. Production has no implicit or synthetic implementation."""

    def prepare(self, connection, *, context: dict) -> dict: ...


@dataclass(frozen=True)
class FixedCaseReplacementProvider:
    """Controlled provider for isolated acceptance tests only."""

    policy: dict
    substitutions: tuple[dict, ...] = ()

    def prepare(self, connection, *, context: dict) -> dict:
        from Api.m5_storage import prepare_assessment_situation

        return prepare_assessment_situation(
            connection,
            assessment_situation_id=str(uuid4()),
            case_id=context["case_id"],
            case_version=context["case_version"],
            personalized_profile_id=context["personalized_profile_id"],
            cycle_db_id=context["cycle_db_id"],
            session_db_id=context["session_db_id"],
            substitutions=list(self.substitutions),
            policy=self.policy,
            usage_scope=context["usage_scope"],
            qa_authorized_by=context["requested_by"] if context["usage_scope"] == "qa" else None,
        )


@dataclass(frozen=True)
class GeneratedCandidateReplacementProvider:
    """Передаёт P01 только уже сохранённый и допущенный candidate UX-P02."""

    operation_id: str

    def prepare(self, connection, *, context: dict) -> dict:
        row = connection.execute("""SELECT o.status,o.candidate_as_db_id,s.assessment_situation_id,
            s.cycle_db_id,s.session_db_id,s.personalized_profile_id,s.usage_scope
            FROM m5_equivalent_generation_operations o
            LEFT JOIN m5_assessment_situations s ON s.id=o.candidate_as_db_id
            WHERE o.id=%s""", (UUID(self.operation_id),)).fetchone()
        if not row or row["status"] != "completed" or not row["candidate_as_db_id"]:
            raise ValueError("M5_EQUIVALENT_CANDIDATE_NOT_READY")
        if (row["cycle_db_id"], row["session_db_id"], row["personalized_profile_id"], row["usage_scope"]) != (
            context["cycle_db_id"], context["session_db_id"], context["personalized_profile_id"], context["usage_scope"]
        ):
            raise ValueError("M5_EQUIVALENT_CANDIDATE_CONTEXT_MISMATCH")
        return {"id": int(row["candidate_as_db_id"]),
                "assessment_situation_id": str(row["assessment_situation_id"]), "status": "admitted"}


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_route_positions (
        id UUID PRIMARY KEY,
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        plan_revision_id UUID NOT NULL,
        position_no INTEGER NOT NULL CHECK(position_no > 0),
        case_id TEXT NOT NULL,
        case_version TEXT NOT NULL,
        expected_targets_json JSONB NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('not_presented','in_progress','awaiting_replacement','completed')),
        current_as_db_id BIGINT REFERENCES m5_assessment_situations(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY(plan_revision_id,cycle_db_id) REFERENCES m7_plan_revisions(id,cycle_db_id),
        UNIQUE(cycle_db_id,position_no), UNIQUE(current_as_db_id), UNIQUE(id,cycle_db_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_route_position_as_history (
        position_id UUID NOT NULL REFERENCES m7_route_positions(id),
        assessment_situation_db_id BIGINT NOT NULL UNIQUE REFERENCES m5_assessment_situations(id),
        ordinal INTEGER NOT NULL CHECK(ordinal > 0),
        disposition TEXT NOT NULL CHECK(disposition IN ('current','replaced')),
        replacement_operation_id UUID,
        exclusion_reason TEXT,
        attached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        replaced_at TIMESTAMPTZ,
        PRIMARY KEY(position_id,ordinal))""")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_m7_position_one_current
        ON m7_route_position_as_history(position_id) WHERE disposition='current'""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_as_replacement_operations (
        id UUID PRIMARY KEY,
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        position_id UUID NOT NULL,
        request_key TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        expected_as_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        expected_state TEXT NOT NULL,
        reason TEXT NOT NULL,
        policy_ref_json JSONB NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('preparing','preparation_failed','completed')),
        candidate_as_db_id BIGINT REFERENCES m5_assessment_situations(id),
        result_json JSONB,
        error_code TEXT,
        created_by BIGINT NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        FOREIGN KEY(position_id,cycle_db_id) REFERENCES m7_route_positions(id,cycle_db_id),
        UNIQUE(cycle_db_id,request_key))""")
    connection.execute("""DO $$ BEGIN
        ALTER TABLE m7_route_position_as_history ADD CONSTRAINT fk_m7_position_replacement
            FOREIGN KEY(replacement_operation_id) REFERENCES m7_as_replacement_operations(id);
        EXCEPTION WHEN duplicate_object THEN NULL; END $$""")


def attach_initial(connection, *, decision_id, as_db_id: int) -> dict:
    decision = connection.execute(
        "SELECT cycle_db_id,plan_revision_id,selected_case_id,selected_case_version,expected_targets_json "
        "FROM m7_route_decisions WHERE id=%s", (decision_id,),
    ).fetchone()
    existing = connection.execute(
        "SELECT * FROM m7_route_positions WHERE current_as_db_id=%s", (as_db_id,),
    ).fetchone()
    if existing:
        return dict(existing)
    position_no = int(connection.execute(
        "SELECT COALESCE(MAX(position_no),0)+1 AS value FROM m7_route_positions WHERE cycle_db_id=%s",
        (decision["cycle_db_id"],),
    ).fetchone()["value"])
    position_id = uuid4()
    row = connection.execute("""INSERT INTO m7_route_positions
        (id,cycle_db_id,plan_revision_id,position_no,case_id,case_version,expected_targets_json,state,current_as_db_id)
        VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,'not_presented',%s) RETURNING *""",
        (position_id, decision["cycle_db_id"], decision["plan_revision_id"], position_no,
         decision["selected_case_id"], decision["selected_case_version"],
         json.dumps(decision["expected_targets_json"]), as_db_id)).fetchone()
    connection.execute("""INSERT INTO m7_route_position_as_history
        (position_id,assessment_situation_db_id,ordinal,disposition)
        VALUES(%s,%s,1,'current')""", (position_id, as_db_id))
    return dict(row)


def mark_presented(connection, as_db_id: int) -> None:
    connection.execute("""UPDATE m7_route_positions SET state='in_progress',updated_at=NOW()
        WHERE current_as_db_id=%s AND state='not_presented'""", (as_db_id,))


def is_excluded(connection, as_db_id: int) -> bool:
    return connection.execute("""SELECT 1 FROM m7_route_position_as_history
        WHERE assessment_situation_db_id=%s AND disposition='replaced'""", (as_db_id,)).fetchone() is not None


def replacement_metadata(connection, cycle_db_id: int) -> dict:
    positions = connection.execute("""SELECT p.*,s.assessment_situation_id AS current_as_id,s.status AS current_as_status
        FROM m7_route_positions p LEFT JOIN m5_assessment_situations s ON s.id=p.current_as_db_id
        WHERE p.cycle_db_id=%s ORDER BY p.position_no""", (cycle_db_id,)).fetchall()
    history = connection.execute("""SELECT h.position_id,h.ordinal,h.disposition,h.exclusion_reason,
        h.replacement_operation_id,s.assessment_situation_id
        FROM m7_route_position_as_history h JOIN m7_route_positions p ON p.id=h.position_id
        JOIN m5_assessment_situations s ON s.id=h.assessment_situation_db_id
        WHERE p.cycle_db_id=%s ORDER BY p.position_no,h.ordinal""", (cycle_db_id,)).fetchall()
    by_position: dict[str, list] = {}
    for item in history:
        by_position.setdefault(str(item["position_id"]), []).append({
            "ordinal": item["ordinal"], "assessment_situation_id": str(item["assessment_situation_id"]),
            "disposition": item["disposition"], "exclusion_reason": item["exclusion_reason"],
            "replacement_operation_id": str(item["replacement_operation_id"]) if item["replacement_operation_id"] else None,
        })
    values = [{
        "position_id": str(p["id"]), "position_no": p["position_no"], "case_id": p["case_id"],
        "case_version": p["case_version"],
        "state": "completed" if p["current_as_status"] == "closed" else p["state"],
        "current_assessment_situation_id": str(p["current_as_id"]) if p["current_as_id"] else None,
        "expected_targets": p["expected_targets_json"], "history": by_position.get(str(p["id"]), []),
    } for p in positions]
    return {"schema_version": 1, "positions": values,
            "progress": {"total_positions": len(values),
                         "completed_positions": sum(1 for value in values if value["state"] == "completed")}}


def replace_current(connection, *, cycle_id: str, position_no: int,
                    expected_assessment_situation_id: str, expected_state: str,
                    key: str, reason: str, policy_ref: dict, requested_by: int,
                    provider: ReplacementProvider | None) -> dict:
    cycle = connection.execute(
        "SELECT * FROM m5_cycles WHERE cycle_id=%s FOR UPDATE", (UUID(cycle_id),),
    ).fetchone()
    if not cycle:
        raise ValueError("M7_CYCLE_NOT_FOUND")
    if int(cycle["owner_user_id"]) != int(requested_by):
        raise ValueError("M7_CYCLE_NOT_FOUND")
    if not all(policy_ref.get(field) for field in ("id", "version", "checksum")):
        raise ValueError("M7_REPLACEMENT_POLICY_REF_INVALID")
    request = {"position_no": position_no, "expected_assessment_situation_id": expected_assessment_situation_id,
               "expected_state": expected_state, "reason": reason, "policy_ref": policy_ref}
    request_hash = checksum(request)
    prior = connection.execute(
        "SELECT * FROM m7_as_replacement_operations WHERE cycle_db_id=%s AND request_key=%s",
        (cycle["id"], key),
    ).fetchone()
    if prior:
        if prior["request_hash"] != request_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        if prior["result_json"]:
            return dict(prior["result_json"])
        raise ValueError(prior["error_code"] or "M7_REPLACEMENT_PREPARATION_PENDING")
    position = connection.execute(
        "SELECT * FROM m7_route_positions WHERE cycle_db_id=%s AND position_no=%s FOR UPDATE",
        (cycle["id"], position_no),
    ).fetchone()
    if not position:
        raise ValueError("M7_ROUTE_POSITION_NOT_FOUND")
    old = connection.execute(
        "SELECT * FROM m5_assessment_situations WHERE id=%s FOR UPDATE", (position["current_as_db_id"],),
    ).fetchone()
    if str(old["assessment_situation_id"]) != expected_assessment_situation_id or old["status"] != expected_state:
        raise ValueError("M7_REPLACEMENT_STALE_CURRENT_AS")
    if position["state"] not in {"in_progress", "awaiting_replacement"} or old["status"] not in {"active", "paused"}:
        raise ValueError("M7_REPLACEMENT_NOT_APPLICABLE")
    if cycle["status"] in TERMINAL_CYCLE:
        raise ValueError("M7_COLLECTION_CLOSED")
    from Api.m7_completion import _effective_limit
    if _effective_limit(connection, dict(cycle)) != (None, None):
        raise ValueError("M7_TIME_LIMIT_REACHED")
    operation_id = uuid4()
    connection.execute("""INSERT INTO m7_as_replacement_operations
        (id,cycle_db_id,position_id,request_key,request_hash,expected_as_db_id,expected_state,
         reason,policy_ref_json,status,created_by)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'preparing',%s)""",
        (operation_id, cycle["id"], position["id"], key, request_hash, old["id"], expected_state,
         reason, json.dumps(policy_ref), requested_by))
    connection.execute("UPDATE m7_route_positions SET state='awaiting_replacement',updated_at=NOW() WHERE id=%s", (position["id"],))
    if provider is None:
        failed = {"operation_id": str(operation_id), "cycle_id": cycle_id, "position_no": position_no,
                  "old_assessment_situation_id": str(old["assessment_situation_id"]),
                  "new_assessment_situation_id": None, "status": "preparation_failed",
                  "error_code": "M7_REPLACEMENT_PROVIDER_UNAVAILABLE"}
        connection.execute("""UPDATE m7_as_replacement_operations SET status='preparation_failed',
            error_code='M7_REPLACEMENT_PROVIDER_UNAVAILABLE',result_json=%s::jsonb WHERE id=%s""",
            (json.dumps(failed), operation_id))
        return failed
    context = {"cycle_db_id": cycle["id"], "session_db_id": old["session_db_id"],
               "personalized_profile_id": cycle["personalized_profile_id"], "usage_scope": cycle["usage_scope"],
               "case_id": position["case_id"], "case_version": position["case_version"],
               "expected_targets": position["expected_targets_json"], "requested_by": requested_by}
    try:
        candidate = provider.prepare(connection, context=context)
    except Exception as exc:
        code = f"M7_REPLACEMENT_PREPARATION_FAILED:{type(exc).__name__}"
        failed = {"operation_id": str(operation_id), "cycle_id": cycle_id, "position_no": position_no,
                  "old_assessment_situation_id": str(old["assessment_situation_id"]),
                  "new_assessment_situation_id": None, "status": "preparation_failed", "error_code": code}
        connection.execute("""UPDATE m7_as_replacement_operations SET status='preparation_failed',
            error_code=%s,result_json=%s::jsonb WHERE id=%s""", (code, json.dumps(failed), operation_id))
        return failed
    new = connection.execute(
        "SELECT * FROM m5_assessment_situations WHERE id=%s FOR UPDATE", (candidate["id"],),
    ).fetchone()
    if not new or new["status"] != "admitted" or new["cycle_db_id"] != cycle["id"] or new["session_db_id"] != old["session_db_id"]:
        raise ValueError("M7_REPLACEMENT_CANDIDATE_INVALID")
    if new["snapshot_json"]["case_ref"] != old["snapshot_json"]["case_ref"]:
        raise ValueError("M7_REPLACEMENT_CASE_MISMATCH")
    if new["snapshot_json"]["profile_ref"] != old["snapshot_json"]["profile_ref"]:
        raise ValueError("M7_REPLACEMENT_PROFILE_MISMATCH")
    # One transaction: archive old, attach new, and persist replayable result.
    connection.execute("UPDATE m5_assessment_situations SET status='terminated' WHERE id=%s", (old["id"],))
    connection.execute("""UPDATE m7_route_position_as_history SET disposition='replaced',
        replacement_operation_id=%s,exclusion_reason=%s,replaced_at=NOW()
        WHERE position_id=%s AND assessment_situation_db_id=%s AND disposition='current'""",
        (operation_id, reason, position["id"], old["id"]))
    ordinal = int(connection.execute(
        "SELECT COALESCE(MAX(ordinal),0)+1 AS value FROM m7_route_position_as_history WHERE position_id=%s",
        (position["id"],),
    ).fetchone()["value"])
    connection.execute("""INSERT INTO m7_route_position_as_history
        (position_id,assessment_situation_db_id,ordinal,disposition,replacement_operation_id)
        VALUES(%s,%s,%s,'current',%s)""", (position["id"], new["id"], ordinal, operation_id))
    connection.execute("""UPDATE m7_route_positions SET current_as_db_id=%s,state='not_presented',updated_at=NOW()
        WHERE id=%s""", (new["id"], position["id"]))
    result = {"operation_id": str(operation_id), "cycle_id": cycle_id, "position_no": position_no,
              "old_assessment_situation_id": str(old["assessment_situation_id"]),
              "new_assessment_situation_id": str(new["assessment_situation_id"]),
              "status": "completed", "new_state": "not_presented", "reason": reason,
              "policy_ref": policy_ref, "completed_at": datetime.now(timezone.utc).isoformat()}
    connection.execute("""UPDATE m7_as_replacement_operations SET status='completed',candidate_as_db_id=%s,
        result_json=%s::jsonb,completed_at=NOW() WHERE id=%s""",
        (new["id"], json.dumps(result), operation_id))
    return result
