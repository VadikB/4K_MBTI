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
    if int(policy.get("presence_lease_seconds", 0)) != 120:
        raise ValueError("M7_RETURN_POLICY_INVALID")
    if int(policy.get("max_successful_replacements_per_position", 0)) != 3:
        raise ValueError("M7_RETURN_POLICY_INVALID")
    return policy


def ensure_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_return_absence_events (
        id UUID PRIMARY KEY,cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),
        session_db_id BIGINT NOT NULL REFERENCES m5_cycle_sessions(id),
        position_id UUID NOT NULL REFERENCES m7_route_positions(id),
        assessment_situation_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        source_kind TEXT NOT NULL CHECK(source_kind IN('controlled_fixture','presence_lease')),source_ref TEXT NOT NULL,
        recognized_at TIMESTAMPTZ NOT NULL,policy_ref_json JSONB NOT NULL,
        status TEXT NOT NULL CHECK(status IN('recognized','consumed')),consumed_at TIMESTAMPTZ,
        result_json JSONB,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(cycle_db_id,source_ref))""")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_m7_one_open_return_event
        ON m7_return_absence_events(cycle_db_id) WHERE status='recognized'""")
    connection.execute("ALTER TABLE m7_return_absence_events DROP CONSTRAINT IF EXISTS m7_return_absence_events_source_kind_check")
    connection.execute("""ALTER TABLE m7_return_absence_events ADD CONSTRAINT m7_return_absence_events_source_kind_check
        CHECK(source_kind IN('controlled_fixture','presence_lease'))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_return_commands (
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),request_key TEXT NOT NULL,
        request_checksum TEXT NOT NULL,result_json JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(cycle_db_id,request_key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_return_presence_clients (
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),client_id UUID NOT NULL,
        owner_user_id BIGINT NOT NULL,assessment_situation_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        last_seen_at TIMESTAMPTZ NOT NULL,lease_expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(cycle_db_id,client_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_return_infrastructure_incidents (
        id UUID PRIMARY KEY,started_at TIMESTAMPTZ NOT NULL,recovered_at TIMESTAMPTZ,
        reason TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


def heartbeat(connection, *, cycle_id: str, owner_user_id: int, client_id: str,
              expected_as_id: str, received_at: datetime | None = None) -> dict:
    cycle, _session, _position, situation = _context(connection, cycle_id, lock=True)
    if int(cycle["owner_user_id"]) != int(owner_user_id):
        raise ValueError("M7_CYCLE_NOT_FOUND")
    if cycle["status"] in TERMINAL_CYCLE or situation["status"] not in {"active", "paused"}:
        raise ValueError("M7_RETURN_NOT_APPLICABLE")
    if str(situation["assessment_situation_id"]) != expected_as_id:
        raise ValueError("M7_RETURN_STALE_CURRENT_AS")
    now = (received_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    # A late heartbeat cannot move the already elapsed server boundary forward.
    reconcile_presence(connection, cycle_id=cycle_id, owner_user_id=owner_user_id, evaluated_at=now)
    lease = now.timestamp() + int(load_policy()["presence_lease_seconds"])
    expires_at = datetime.fromtimestamp(lease, timezone.utc)
    row = connection.execute("""INSERT INTO m7_return_presence_clients(
        cycle_db_id,client_id,owner_user_id,assessment_situation_db_id,last_seen_at,lease_expires_at)
        VALUES(%s,%s,%s,%s,%s,%s)
        ON CONFLICT(cycle_db_id,client_id) DO UPDATE SET
          owner_user_id=EXCLUDED.owner_user_id,assessment_situation_db_id=EXCLUDED.assessment_situation_db_id,
          last_seen_at=EXCLUDED.last_seen_at,lease_expires_at=EXCLUDED.lease_expires_at
        RETURNING client_id,last_seen_at,lease_expires_at""",
        (cycle["id"], UUID(client_id), owner_user_id, situation["id"], now, expires_at),
    ).fetchone()
    return {**dict(row), "client_id": str(row["client_id"]), "cycle_id": cycle_id,
            "assessment_situation_id": expected_as_id}


def _open_incident_overlaps(connection, at: datetime) -> bool:
    return bool(connection.execute("""SELECT 1 FROM m7_return_infrastructure_incidents
        WHERE started_at<=%s AND (recovered_at IS NULL OR recovered_at>=%s) LIMIT 1""", (at, at)).fetchone())


def _recognize_presence_absence(connection, *, cycle: dict, session: dict, position: dict,
                                situation: dict, recognized_at: datetime, source_ref: str) -> dict:
    policy = load_policy();policy_ref={"id":policy["id"],"version":policy["version"],"checksum":checksum(policy)}
    connection.execute("UPDATE m5_cycle_time_intervals SET ended_at=%s WHERE cycle_db_id=%s AND ended_at IS NULL AND interval_type='collecting'",
                       (recognized_at, cycle["id"]))
    operation_ref=f"return:{source_ref}"
    connection.execute("""INSERT INTO m5_cycle_time_intervals
        (cycle_db_id,session_db_id,interval_type,started_at,reason,operation_ref)
        VALUES(%s,%s,'blocking_system_wait',%s,'recognized_presence_absence',%s)
        ON CONFLICT DO NOTHING""", (cycle["id"],session["id"],recognized_at,operation_ref))
    return dict(connection.execute("""INSERT INTO m7_return_absence_events
        (id,cycle_db_id,session_db_id,position_id,assessment_situation_db_id,source_kind,source_ref,
         recognized_at,policy_ref_json,status)
        VALUES(%s,%s,%s,%s,%s,'presence_lease',%s,%s,%s::jsonb,'recognized') RETURNING *""",
        (uuid4(),cycle["id"],session["id"],position["id"],situation["id"],source_ref,recognized_at,json.dumps(policy_ref))).fetchone())


def reconcile_presence(connection, *, cycle_id: str, owner_user_id: int,
                       evaluated_at: datetime | None = None) -> dict | None:
    cycle, session, position, situation = _context(connection, cycle_id, lock=True)
    if int(cycle["owner_user_id"]) != int(owner_user_id): raise ValueError("M7_CYCLE_NOT_FOUND")
    existing=connection.execute("SELECT * FROM m7_return_absence_events WHERE cycle_db_id=%s AND status='recognized' FOR UPDATE",(cycle["id"],)).fetchone()
    if existing:return dict(existing)
    latest=connection.execute("""SELECT MAX(lease_expires_at) AS value FROM m7_return_presence_clients
        WHERE cycle_db_id=%s AND assessment_situation_db_id=%s""",(cycle["id"],situation["id"])).fetchone()["value"]
    now=(evaluated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if latest is None or latest>now:return None
    if _open_incident_overlaps(connection,latest):return None
    return _recognize_presence_absence(connection,cycle=cycle,session=session,position=position,
        situation=situation,recognized_at=latest,source_ref=f"lease:{position['id']}:{latest.isoformat()}")


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
    plan = connection.execute("""SELECT r.content_json FROM m7_cycle_plans p
        JOIN LATERAL(SELECT content_json FROM m7_plan_revisions
            WHERE plan_id=p.id ORDER BY revision_no DESC LIMIT 1) r ON TRUE
        WHERE p.cycle_db_id=%s""", (cycle["id"],)).fetchone()
    planned_positions = len((plan["content_json"] or {}).get("route", [])) if plan else None
    event = connection.execute("SELECT * FROM m7_return_absence_events WHERE cycle_db_id=%s AND status='recognized' ORDER BY created_at DESC LIMIT 1",
                               (cycle["id"],)).fetchone()
    now = evaluated_at or datetime.now(timezone.utc)
    limit_reached = (cycle["status"] in TERMINAL_CYCLE or timing["remaining_seconds"] <= 0 or
                     bool(timing["calendar_deadline"] and now >= timing["calendar_deadline"]))
    if limit_reached:
        action, absence_seconds, event_id = "time_limit_reached", None, str(event["id"]) if event else None
    elif not event:
        latest=connection.execute("""SELECT MAX(lease_expires_at) AS value FROM m7_return_presence_clients
            WHERE cycle_db_id=%s AND assessment_situation_db_id=%s""",(cycle["id"],situation["id"])).fetchone()["value"]
        if latest and latest<=now and not _open_incident_overlaps(connection,latest):
            absence_seconds=max(0,int((now-latest).total_seconds()))
            if absence_seconds < load_policy()["replacement_threshold_seconds"]:
                action = "continue_current"
            else:
                ready = connection.execute("""SELECT 1 FROM m5_equivalent_generation_operations
                    WHERE cycle_db_id=%s AND position_id=%s AND expected_as_db_id=%s
                      AND status='completed' ORDER BY completed_at DESC LIMIT 1""",
                    (cycle["id"], position["id"], situation["id"])).fetchone()
                action = "replace_current" if ready else "replacement_candidate_required"
        else:
            action,absence_seconds=("connected",0) if latest and latest>now else ("dependency_unavailable",None)
        event_id = None
    else:
        absence_seconds = max(0, int((now - event["recognized_at"]).total_seconds()))
        if absence_seconds < load_policy()["replacement_threshold_seconds"]:
            action = "continue_current"
        else:
            ready = connection.execute("""SELECT 1 FROM m5_equivalent_generation_operations
                WHERE cycle_db_id=%s AND position_id=%s AND expected_as_db_id=%s
                  AND status='completed' ORDER BY completed_at DESC LIMIT 1""",
                (cycle["id"], position["id"], situation["id"])).fetchone()
            action = "replace_current" if ready else "replacement_candidate_required"
        event_id = str(event["id"])
    return {"cycle_id": cycle_id, "collection_status": cycle["status"],
            "position_no": position["position_no"],
            "current_assessment_situation_id": str(situation["assessment_situation_id"]),
            "current_assessment_situation_status": situation["status"],
            "absence_event_id": event_id, "recognized_absence_seconds": absence_seconds,
            "allowed_action": action, "remaining_seconds": timing["remaining_seconds"],
            "calendar_deadline": timing["calendar_deadline"], "progress": route["progress"],
            "planned_positions": planned_positions,
            "planned_total": planned_positions is not None,
            "presence_lease_seconds": int(load_policy()["presence_lease_seconds"]),
            "replacement_count": sum(1 for item in next(x for x in route["positions"] if x["position_no"]==position["position_no"])["history"] if item["disposition"]=="replaced"),
            "replacement_limit": int(load_policy()["max_successful_replacements_per_position"])}


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
        event = reconcile_presence(connection,cycle_id=cycle_id,owner_user_id=owner_user_id,evaluated_at=evaluated_at)
    if not event:raise ValueError("M7_RETURN_ACTIVE_CONNECTION")
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
        route=replacement_metadata(connection,cycle["id"])
        current_route=next(x for x in route["positions"] if x["position_no"]==position_no)
        replacement_count=sum(1 for item in current_route["history"] if item["disposition"]=="replaced")
        if replacement_count>=int(load_policy()["max_successful_replacements_per_position"]):
            from Api.m7_completion import complete
            closed=complete(connection,cycle_id=cycle_id,key=f"{key}:replacement-limit",action="complete",
                reason="return_replacement_limit_reached",initiated_by=owner_user_id)
            result={"cycle_id":cycle_id,"position_no":position_no,"status":"collection_closed",
                "branch":"replacement_limit_closed","assessment_situation_id":expected_as_id,
                "recognized_absence_seconds":elapsed,"remaining_seconds":read_cycle(connection,cycle_id)["remaining_seconds"],
                "calendar_deadline":read_cycle(connection,cycle_id)["calendar_deadline"].isoformat(),
                "completion":closed}
            connection.execute("UPDATE m7_return_absence_events SET status='consumed',consumed_at=NOW(),result_json=%s::jsonb WHERE id=%s",
                (json.dumps(result),event["id"]))
            connection.execute("INSERT INTO m7_return_commands VALUES(%s,%s,%s,%s::jsonb,NOW())",
                (cycle["id"],key,digest,json.dumps(result)))
            return result
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
