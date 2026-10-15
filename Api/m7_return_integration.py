"""QA-only adapter для UX-P03 поверх контролируемого события отсутствия."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum
from Api.m5_cycle_runtime import end_blocking_wait, read_cycle
from Api.m5_scenario_runtime import start as start_situation
from Api.m7_route_replacement import GeneratedCandidateReplacementProvider, mark_presented, replacement_metadata, replace_current


POLICY_PATH = Path(__file__).resolve().parents[1] / "assessment_definitions/planning/m7_return_integration/v1/policy.json"
TERMINAL_CYCLE = {"collection_closed", "calculation_pending", "calculated", "failed"}


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads(path.with_name("manifest.json").read_text(encoding="utf-8"))
    if manifest["artifacts"][0]["path"] != path.name or manifest["artifacts"][0]["checksum"] != checksum(policy):
        raise ValueError("M7_RETURN_POLICY_CHECKSUM_MISMATCH")
    if (manifest["id"], manifest["version"], manifest["status"], manifest["usage_scope"]) != (
        policy["id"], policy["version"], policy["status"], policy["usage_scope"]
    ):
        raise ValueError("M7_RETURN_POLICY_REF_MISMATCH")
    if policy.get("status") != "draft" or policy.get("usage_scope") != "qa":
        raise ValueError("M7_RETURN_POLICY_NOT_QA_DRAFT")
    if int(policy.get("replacement_threshold_seconds", 0)) != 180:
        raise ValueError("M7_RETURN_POLICY_INVALID")
    return policy


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_return_absence_events (
        id UUID PRIMARY KEY,cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        session_db_id BIGINT NOT NULL REFERENCES m5_cycle_sessions(id),
        position_id UUID NOT NULL REFERENCES m7_route_positions(id),
        assessment_situation_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        source_kind TEXT NOT NULL CHECK(source_kind='controlled_fixture'),source_ref TEXT NOT NULL,
        recognized_at TIMESTAMPTZ NOT NULL,policy_ref_json JSONB NOT NULL,
        status TEXT NOT NULL CHECK(status IN('recognized','consumed')),consumed_at TIMESTAMPTZ,
        result_json JSONB,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(cycle_db_id,source_ref))""")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_m7_one_open_return_event
        ON m7_return_absence_events(cycle_db_id) WHERE status='recognized'""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_return_commands (
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),request_key TEXT NOT NULL,
        request_checksum TEXT NOT NULL,result_json JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(cycle_db_id,request_key))""")


def _context(connection, cycle_id: str, *, lock: bool = False) -> tuple[dict, dict, dict, dict]:
    suffix = " FOR UPDATE" if lock else ""
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE cycle_id=%s" + suffix, (UUID(cycle_id),)).fetchone()
    if not cycle:
        raise ValueError("M7_CYCLE_NOT_FOUND")
    session = connection.execute("SELECT * FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal DESC LIMIT 1" + suffix,
                                 (cycle["id"],)).fetchone()
    position = connection.execute("SELECT * FROM m7_route_positions WHERE cycle_db_id=%s AND state IN('in_progress','awaiting_replacement') ORDER BY position_no LIMIT 1" + suffix,
                                  (cycle["id"],)).fetchone()
    if not session or not position or not position["current_as_db_id"]:
        raise ValueError("M7_RETURN_CURRENT_POSITION_NOT_FOUND")
    situation = connection.execute("SELECT * FROM m5_assessment_situations WHERE id=%s" + suffix,
                                   (position["current_as_db_id"],)).fetchone()
    return dict(cycle), dict(session), dict(position), dict(situation)


def record_controlled_absence(connection, *, cycle_id: str, expected_as_id: str,
                              source_ref: str, recognized_at: datetime) -> dict:
    """Test seam: production D08 event source intentionally does not exist yet."""
    cycle, session, position, situation = _context(connection, cycle_id, lock=True)
    if cycle["usage_scope"] != "qa":
        raise ValueError("M7_RETURN_CONTROLLED_EVENT_QA_ONLY")
    if cycle["status"] in TERMINAL_CYCLE or situation["status"] not in {"active", "paused"}:
        raise ValueError("M7_RETURN_NOT_APPLICABLE")
    if str(situation["assessment_situation_id"]) != expected_as_id:
        raise ValueError("M7_RETURN_STALE_CURRENT_AS")
    if recognized_at.tzinfo is None:
        raise ValueError("M7_RETURN_RECOGNIZED_AT_TZ_REQUIRED")
    recognized_at = recognized_at.astimezone(timezone.utc)
    open_interval = connection.execute(
        "SELECT started_at FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND ended_at IS NULL FOR UPDATE",
        (cycle["id"],),
    ).fetchone()
    if not open_interval or recognized_at < open_interval["started_at"]:
        raise ValueError("M7_RETURN_RECOGNIZED_AT_OUTSIDE_ACTIVE_INTERVAL")
    if recognized_at > datetime.now(timezone.utc):
        raise ValueError("M7_RETURN_RECOGNIZED_AT_IN_FUTURE")
    policy = load_policy()
    policy_ref = {"id": policy["id"], "version": policy["version"], "checksum": checksum(policy)}
    prior = connection.execute("SELECT * FROM m7_return_absence_events WHERE cycle_db_id=%s AND source_ref=%s",
                               (cycle["id"], source_ref)).fetchone()
    if prior:
        return dict(prior)
    if connection.execute("SELECT 1 FROM m7_return_absence_events WHERE cycle_db_id=%s AND status='recognized'",
                          (cycle["id"],)).fetchone():
        raise ValueError("M7_RETURN_EVENT_ALREADY_OPEN")
    connection.execute("UPDATE m5_cycle_time_intervals SET ended_at=%s WHERE cycle_db_id=%s AND ended_at IS NULL",
                       (recognized_at, cycle["id"]))
    operation_ref = f"return:{source_ref}"
    connection.execute("""INSERT INTO m5_cycle_time_intervals
        (cycle_db_id,session_db_id,interval_type,started_at,reason,operation_ref)
        VALUES(%s,%s,'blocking_system_wait',%s,'controlled_return_absence',%s)""",
        (cycle["id"], session["id"], recognized_at, operation_ref))
    return dict(connection.execute("""INSERT INTO m7_return_absence_events
        (id,cycle_db_id,session_db_id,position_id,assessment_situation_db_id,source_kind,source_ref,
         recognized_at,policy_ref_json,status)
        VALUES(%s,%s,%s,%s,%s,'controlled_fixture',%s,%s,%s::jsonb,'recognized') RETURNING *""",
        (uuid4(), cycle["id"], session["id"], position["id"], situation["id"], source_ref,
         recognized_at, json.dumps(policy_ref))).fetchone())


def read_return_state(connection, *, cycle_id: str, owner_user_id: int,
                      evaluated_at: datetime | None = None) -> dict:
    cycle, _session, position, situation = _context(connection, cycle_id)
    if int(cycle["owner_user_id"]) != int(owner_user_id):
        raise ValueError("M7_CYCLE_NOT_FOUND")
    timing = read_cycle(connection, cycle_id)
    route = replacement_metadata(connection, cycle["id"])
    event = connection.execute("SELECT * FROM m7_return_absence_events WHERE cycle_db_id=%s AND status='recognized' ORDER BY created_at DESC LIMIT 1",
                               (cycle["id"],)).fetchone()
    now = evaluated_at or datetime.now(timezone.utc)
    if not event:
        action, absence_seconds, event_id = "dependency_unavailable", None, None
    else:
        absence_seconds = max(0, int((now - event["recognized_at"]).total_seconds()))
        action = "continue_current" if absence_seconds < load_policy()["replacement_threshold_seconds"] else "replace_current"
        event_id = str(event["id"])
    return {"cycle_id": cycle_id, "collection_status": cycle["status"],
            "position_no": position["position_no"],
            "current_assessment_situation_id": str(situation["assessment_situation_id"]),
            "current_assessment_situation_status": situation["status"],
            "absence_event_id": event_id, "recognized_absence_seconds": absence_seconds,
            "allowed_action": action, "remaining_seconds": timing["remaining_seconds"],
            "calendar_deadline": timing["calendar_deadline"], "progress": route["progress"],
            "planned_total": True}


def continue_return(connection, *, cycle_id: str, position_no: int, expected_as_id: str,
                    expected_state: str, key: str, owner_user_id: int,
                    generation_operation_id: str | None = None,
                    evaluated_at: datetime | None = None) -> dict:
    cycle, session, position, situation = _context(connection, cycle_id, lock=True)
    if int(cycle["owner_user_id"]) != int(owner_user_id):
        raise ValueError("M7_CYCLE_NOT_FOUND")
    request = {"position_no": position_no, "expected_as_id": expected_as_id,
               "expected_state": expected_state, "generation_operation_id": generation_operation_id}
    digest = checksum(request)
    prior = connection.execute("SELECT * FROM m7_return_commands WHERE cycle_db_id=%s AND request_key=%s",
                               (cycle["id"], key)).fetchone()
    if prior:
        if prior["request_checksum"] != digest:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return dict(prior["result_json"])
    if cycle["status"] in TERMINAL_CYCLE:
        raise ValueError("M7_COLLECTION_CLOSED")
    if position["position_no"] != position_no or str(situation["assessment_situation_id"]) != expected_as_id or situation["status"] != expected_state:
        raise ValueError("M7_RETURN_STALE_CURRENT_AS")
    event = connection.execute("SELECT * FROM m7_return_absence_events WHERE cycle_db_id=%s AND status='recognized' FOR UPDATE",
                               (cycle["id"],)).fetchone()
    if not event:
        raise ValueError("M7_RETURN_D08_EVENT_REQUIRED")
    from Api.m7_completion import _effective_limit
    if _effective_limit(connection, cycle) != (None, None):
        raise ValueError("M7_TIME_LIMIT_REACHED")
    now = evaluated_at or datetime.now(timezone.utc)
    elapsed = max(0, int((now - event["recognized_at"]).total_seconds()))
    if elapsed < int(load_policy()["replacement_threshold_seconds"]):
        current_id, branch = expected_as_id, "continued_current"
        end_blocking_wait(connection, cycle_db_id=cycle["id"], session_db_id=session["id"],
                          operation_ref=f"return:{event['source_ref']}", reason="explicit_return_continue")
    else:
        if not generation_operation_id:
            raise ValueError("M7_RETURN_P02_CANDIDATE_REQUIRED")
        replaced = replace_current(connection, cycle_id=cycle_id, position_no=position_no,
            expected_assessment_situation_id=expected_as_id, expected_state=expected_state,
            key=f"{key}:replace", reason="recognized_return_threshold", policy_ref=event["policy_ref_json"],
            requested_by=owner_user_id, provider=GeneratedCandidateReplacementProvider(generation_operation_id))
        current_id = replaced["new_assessment_situation_id"]
        end_blocking_wait(connection, cycle_db_id=cycle["id"], session_db_id=session["id"],
                          operation_ref=f"return:{event['source_ref']}", reason="explicit_return_continue")
        started = start_situation(connection, current_id)
        current_row = connection.execute("SELECT id FROM m5_assessment_situations WHERE assessment_situation_id=%s",
                                         (UUID(current_id),)).fetchone()
        mark_presented(connection, int(current_row["id"]))
        branch = "replaced_current"
        if started["status"] != "active":
            raise ValueError("M7_RETURN_PRESENTATION_FAILED")
    timing = read_cycle(connection, cycle_id)
    result = {"cycle_id": cycle_id, "position_no": position_no, "status": "active", "branch": branch,
              "assessment_situation_id": current_id, "recognized_absence_seconds": elapsed,
              "remaining_seconds": timing["remaining_seconds"],
              "calendar_deadline": timing["calendar_deadline"].isoformat()}
    connection.execute("UPDATE m7_return_absence_events SET status='consumed',consumed_at=NOW(),result_json=%s::jsonb WHERE id=%s",
                       (json.dumps(result), event["id"]))
    connection.execute("INSERT INTO m7_return_commands VALUES(%s,%s,%s,%s::jsonb,NOW())",
                       (cycle["id"], key, digest, json.dumps(result)))
    return result
