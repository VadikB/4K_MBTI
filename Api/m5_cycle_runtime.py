from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum
from Api.cycle_execution_manifest import build_manifest


def _profile_row(connection, personalized_profile_id: int) -> dict[str, Any]:
    row = connection.execute(
        "SELECT to_jsonb(p) AS value FROM assessment_personalized_profiles p WHERE p.id=%s",
        (personalized_profile_id,),
    ).fetchone()
    if not row or row["value"].get("status") != "ready":
        raise ValueError("M4_PROFILE_NOT_READY")
    return dict(row["value"])


def _assignment_for_profile(connection, profile: dict[str, Any], personalized_profile_id: int) -> int | None:
    """Resolve the exact immutable assignment generation that produced this M4 profile."""
    relations = connection.execute("""SELECT
        to_regclass(current_schema()||'.organization_assessment_assignments') AS assignments,
        to_regclass(current_schema()||'.organization_assessment_source_bindings') AS bindings,
        to_regclass(current_schema()||'.participant_acquaintance_confirmations') AS confirmations""").fetchone()
    if not relations or not all(relations.get(name) for name in ("assignments", "bindings", "confirmations")):
        return None
    rows = connection.execute(
        """SELECT assignment.id,assignment.status,assignment.revoked_at
           FROM participant_acquaintance_confirmations confirmation
           JOIN organization_assessment_assignments assignment
             ON assignment.recipient_user_id=confirmation.user_id
            AND assignment.organization_id=confirmation.organization_id
            AND assignment.assignment_ref=confirmation.assignment_ref
           JOIN organization_assessment_source_bindings binding
             ON binding.assignment_id=assignment.id
            AND binding.questionnaire_revision_id=confirmation.questionnaire_revision_id
           WHERE confirmation.personalized_profile_id=%s
             AND assignment.recipient_user_id=%s
             AND assignment.organization_id=%s
             AND binding.assessment_configuration_id=%s
             AND binding.role_profile_version_id=%s
           ORDER BY assignment.id DESC""",
        (
            personalized_profile_id,
            profile.get("user_id"),
            profile.get("organization_id"),
            profile.get("assessment_configuration_id"),
            profile.get("role_profile_version_id"),
        ),
    ).fetchall()
    if not rows:
        return None
    assignment = rows[0]
    if assignment["status"] != "active" or assignment.get("revoked_at") is not None:
        raise ValueError("ASSIGNMENT_CANCELLED")
    return int(assignment["id"])


def create_cycle(
    connection,
    *,
    personalized_profile_id: int,
    selected_role_ref: dict[str, Any],
    target_set: list[dict[str, str]],
    created_by: int,
    time_budget_seconds: int | None = None,
    calendar_window_seconds: int | None = None,
    parameter_sources: dict[str, Any] | None = None,
    usage_scope: str = "assessment",
    catalog_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _profile_row(connection, personalized_profile_id)
    assignment_id = None
    if usage_scope == "assessment" and profile.get("organization_id") is not None:
        assignment_id = _assignment_for_profile(connection, profile, personalized_profile_id)
    if parameter_sources is None:
        from Api.m7_parameter_resolution import resolve
        overrides={name:value for name,value in {
            "time_budget_seconds":time_budget_seconds,
            "calendar_window_seconds":calendar_window_seconds}.items() if value is not None}
        resolved = resolve(connection, personalized_profile_id=personalized_profile_id,
                           usage_scope=usage_scope,qa_overrides=overrides or None)
        time_budget_seconds = resolved["values"]["time_budget_seconds"]
        calendar_window_seconds = resolved["values"]["calendar_window_seconds"]
        parameter_sources = {"time_budget": resolved["sources"]["time_budget_seconds"],
                             "calendar_window": resolved["sources"]["calendar_window_seconds"],
                             "resolution_checksum": resolved["resolved_checksum"]}
    if type(time_budget_seconds) is not int or type(calendar_window_seconds) is not int or time_budget_seconds <= 0 or calendar_window_seconds <= 0:
        raise ValueError("M7_TIME_LIMIT_INVALID")
    if usage_scope not in {"assessment", "qa"}:
        raise ValueError("M7_USAGE_SCOPE_INVALID")
    normalized_targets = sorted(
        ({"indicator_id": str(x["indicator_id"]), "m2_version": str(x["m2_version"])} for x in target_set),
        key=lambda x: (x["indicator_id"], x["m2_version"]),
    )
    if not normalized_targets or len({(x["indicator_id"], x["m2_version"]) for x in normalized_targets}) != len(normalized_targets):
        raise ValueError("TARGET_SET_MISMATCH")
    cycle_id = uuid4()
    profile_ref = {
        "id": f"assessment_personalized_profiles:{personalized_profile_id}",
        "version": "1",
        "checksum": profile["checksum"],
    }
    if parameter_sources is None:
        raise ValueError("M7_PARAMETER_PROVENANCE_REQUIRED")
    sources = parameter_sources
    target_set_checksum = checksum(normalized_targets)
    execution_manifest, execution_manifest_checksum = build_manifest(
        profile_ref=profile_ref,
        selected_role_ref=selected_role_ref,
        target_set_checksum=target_set_checksum,
        parameter_sources=sources,
        catalog_ref=catalog_ref,
    )
    value = {
        "cycle_id": str(cycle_id),
        "profile_ref": profile_ref,
        "selected_role_ref": selected_role_ref,
        "target_set": normalized_targets,
        "time_budget_seconds": time_budget_seconds,
        "calendar_window_seconds": calendar_window_seconds,
        "parameter_sources": sources,
        "usage_scope": usage_scope,
        "catalog_ref": catalog_ref,
    }
    row = connection.execute(
        """
        INSERT INTO m5_cycles
            (cycle_id,owner_user_id,organization_id,assignment_id,personalized_profile_id,profile_ref_json,
             selected_role_ref_json,target_set_json,target_set_checksum,time_budget_seconds,
             calendar_window_seconds,parameter_sources_json,execution_manifest_json,
             execution_manifest_checksum,usage_scope,catalog_ref_json,status,created_by)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,'prepared',%s)
        RETURNING *
        """,
        (
            cycle_id,
            profile.get("user_id") or created_by,
            profile.get("organization_id"),
            assignment_id,
            personalized_profile_id,
            json.dumps(profile_ref),
            json.dumps(selected_role_ref),
            json.dumps(normalized_targets),
            target_set_checksum,
            time_budget_seconds,
            calendar_window_seconds,
            json.dumps(sources),
            json.dumps(execution_manifest),
            execution_manifest_checksum,
            usage_scope,
            json.dumps(catalog_ref) if catalog_ref else None,
            created_by,
        ),
    ).fetchone()
    if usage_scope == "assessment" and profile.get("organization_id") is not None:
        from Api import m8_report_access
        m8_report_access.freeze_for_cycle(
            connection,
            cycle_db_id=int(row["id"]),
            personalized_profile_id=personalized_profile_id,
            participant_user_id=int(profile.get("user_id") or created_by),
            organization_id=int(profile["organization_id"]),
        )
    return dict(row)


def create_session(connection, *, cycle_id: str, created_by: int) -> dict[str, Any]:
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE cycle_id=%s FOR UPDATE", (UUID(cycle_id),)).fetchone()
    if not cycle:
        raise ValueError("M7_CYCLE_NOT_FOUND")
    if cycle["status"] not in {"prepared", "interrupted"}:
        raise ValueError("M7_SESSION_NOT_ALLOWED")
    if cycle["status"] == "interrupted" and not _can_continue(connection, dict(cycle)):
        raise ValueError("M7_ADDITIONAL_SESSION_NOT_ALLOWED")
    ordinal = connection.execute(
        "SELECT COALESCE(MAX(ordinal),0)+1 AS value FROM m5_cycle_sessions WHERE cycle_db_id=%s",
        (cycle["id"],),
    ).fetchone()["value"]
    row = connection.execute(
        """
        INSERT INTO m5_cycle_sessions (session_id,cycle_db_id,ordinal,status,created_by)
        VALUES (%s,%s,%s,'prepared',%s) RETURNING *
        """,
        (uuid4(), cycle["id"], ordinal, created_by),
    ).fetchone()
    return dict(row)


def create_cycle_session_for_case(
    connection,
    *,
    personalized_profile_id: int,
    case_id: str,
    case_version: str,
    created_by: int,
    usage_scope: str,
    time_budget_seconds: int | None = None,
    calendar_window_seconds: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = _profile_row(connection, personalized_profile_id)
    targets = connection.execute(
        """
        SELECT t.indicator_id,t.m2_version
        FROM m5_case_versions cv JOIN m5_case_targets t ON t.case_version_id=cv.id
        WHERE cv.id=(SELECT id FROM m5_case_versions WHERE case_id=%s AND case_version=%s
                     ORDER BY package_id DESC LIMIT 1)
        ORDER BY t.display_order
        """,
        (case_id, case_version),
    ).fetchall()
    if not targets:
        raise ValueError("M5_CASE_VERSION_NOT_IMPORTED")
    content = profile.get("content_json") or {}
    role = content.get("role_profile") if isinstance(content.get("role_profile"), dict) else {}
    role_ref = {
        "id": str(profile.get("role_profile_version_id") or role.get("code") or content.get("base_role") or "qa-role"),
        "version": str(role.get("version") or "1"),
        "checksum": str(role.get("checksum") or profile["checksum"]),
    }
    cycle = create_cycle(
        connection,
        personalized_profile_id=personalized_profile_id,
        selected_role_ref=role_ref,
        target_set=[dict(x) for x in targets],
        created_by=created_by,
        time_budget_seconds=time_budget_seconds,
        calendar_window_seconds=calendar_window_seconds,
        usage_scope=usage_scope,
    )
    session = create_session(connection, cycle_id=str(cycle["cycle_id"]), created_by=created_by)
    session = start_session(connection, session_id=str(session["session_id"]))
    return cycle, session


def start_session(connection, *, session_id: str) -> dict[str, Any]:
    owner = connection.execute(
        """SELECT c.owner_user_id FROM m5_cycle_sessions s
           JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE s.session_id=%s""",
        (UUID(session_id),),
    ).fetchone()
    if not owner:
        raise ValueError("M7_SESSION_CANNOT_START")
    connection.execute("SELECT pg_advisory_xact_lock(%s)", (int(owner["owner_user_id"]),))
    session = connection.execute(
        "SELECT s.*, c.status AS cycle_status,c.assignment_id,c.owner_user_id FROM m5_cycle_sessions s JOIN m5_cycles c ON c.id=s.cycle_db_id "
        "WHERE s.session_id=%s FOR UPDATE OF s,c",
        (UUID(session_id),),
    ).fetchone()
    if not session or session["status"] not in {"prepared", "paused"}:
        raise ValueError("M7_SESSION_CANNOT_START")
    if session["cycle_status"] not in {"prepared", "interrupted", "active", "paused"}:
        raise ValueError("M7_CYCLE_COLLECTION_CLOSED")
    if session.get("assignment_id") is not None and not connection.execute(
        """SELECT 1 FROM organization_assessment_assignments
           WHERE id=%s AND recipient_user_id=%s AND status='active' AND revoked_at IS NULL FOR UPDATE""",
        (session["assignment_id"], session["owner_user_id"]),
    ).fetchone():
        raise ValueError("ASSIGNMENT_CANCELLED")
    connection.execute(
        "UPDATE m5_cycles SET status='active', started_at=COALESCE(started_at,NOW()), updated_at=NOW() WHERE id=%s",
        (session["cycle_db_id"],),
    )
    row = connection.execute(
        "UPDATE m5_cycle_sessions SET status='active',started_at=COALESCE(started_at,NOW()),updated_at=NOW() "
        "WHERE id=%s RETURNING *",
        (session["id"],),
    ).fetchone()
    connection.execute(
        """
        INSERT INTO m5_cycle_time_intervals
            (cycle_db_id,session_db_id,interval_type,started_at,reason)
        VALUES (%s,%s,'collecting',NOW(),'session_started')
        """,
        (session["cycle_db_id"], session["id"]),
    )
    return dict(row)


def transition_session(connection, *, session_id: str, action: str, reason: str) -> dict[str, Any]:
    session = connection.execute(
        "SELECT s.*, c.status AS cycle_status FROM m5_cycle_sessions s JOIN m5_cycles c ON c.id=s.cycle_db_id "
        "WHERE s.session_id=%s FOR UPDATE OF s,c",
        (UUID(session_id),),
    ).fetchone()
    if not session:
        raise ValueError("M7_SESSION_NOT_FOUND")
    transitions = {
        ("active", "pause"): ("paused", "paused"),
        ("paused", "resume"): ("active", "active"),
        ("active", "interrupt"): ("interrupted", "interrupted"),
        ("paused", "interrupt"): ("interrupted", "interrupted"),
        ("active", "complete"): ("completed", "collection_closed"),
        ("paused", "complete"): ("completed", "collection_closed"),
    }
    target = transitions.get((session["status"], action))
    if not target:
        raise ValueError("M7_INVALID_SESSION_TRANSITION")
    session_status, cycle_status = target
    ended = action in {"interrupt", "complete"}
    connection.execute(
        "UPDATE m5_cycle_time_intervals SET ended_at=NOW() WHERE cycle_db_id=%s AND ended_at IS NULL",
        (session["cycle_db_id"],),
    )
    if action == "pause":
        connection.execute(
            "INSERT INTO m5_cycle_time_intervals (cycle_db_id,session_db_id,interval_type,started_at,reason) "
            "VALUES (%s,%s,'authorized_pause',NOW(),%s)",
            (session["cycle_db_id"], session["id"], reason),
        )
    elif action == "resume":
        connection.execute(
            "INSERT INTO m5_cycle_time_intervals (cycle_db_id,session_db_id,interval_type,started_at,reason) "
            "VALUES (%s,%s,'collecting',NOW(),%s)",
            (session["cycle_db_id"], session["id"], reason),
        )
    row = connection.execute(
        "UPDATE m5_cycle_sessions SET status=%s,ended_at=CASE WHEN %s THEN NOW() ELSE ended_at END,"
        "close_reason=%s,updated_at=NOW() WHERE id=%s RETURNING *",
        (session_status, ended, reason, session["id"]),
    ).fetchone()
    connection.execute(
        "UPDATE m5_cycles SET status=%s,collection_closed_at=CASE WHEN %s='collection_closed' THEN NOW() ELSE collection_closed_at END,"
        "close_reason=%s,updated_at=NOW() WHERE id=%s",
        (cycle_status, cycle_status, reason, session["cycle_db_id"]),
    )
    return dict(row)


def _can_continue(connection, cycle: dict[str, Any]) -> bool:
    started_at = cycle.get("started_at")
    if not started_at:
        return True
    now = datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    calendar_elapsed = max(0, int((now - started_at).total_seconds()))
    consumed = connection.execute(
        """
        SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at,NOW())-started_at))),0)::BIGINT AS value
        FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND interval_type='collecting'
        """,
        (cycle["id"],),
    ).fetchone()["value"]
    return calendar_elapsed < int(cycle["calendar_window_seconds"]) and int(consumed) < int(cycle["time_budget_seconds"])


def assert_collecting(connection, *, cycle_db_id: int, session_db_id: int) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT c.*, s.status AS session_status, s.id AS checked_session_id
        FROM m5_cycles c JOIN m5_cycle_sessions s ON s.cycle_db_id=c.id
        WHERE c.id=%s AND s.id=%s FOR UPDATE OF c,s
        """,
        (cycle_db_id, session_db_id),
    ).fetchone()
    if not row or row["status"] != "active" or row["session_status"] != "active":
        raise ValueError("M7_COLLECTION_CLOSED")
    if connection.execute("""SELECT 1 FROM m5_cycle_time_intervals
        WHERE cycle_db_id=%s AND interval_type='blocking_system_wait' AND ended_at IS NULL""",
        (cycle_db_id,)).fetchone():
        raise ValueError("M7_BLOCKING_SYSTEM_WAIT")
    if not _can_continue(connection, dict(row)):
        connection.execute(
            "UPDATE m5_cycle_time_intervals SET ended_at=NOW() WHERE cycle_db_id=%s AND ended_at IS NULL",
            (cycle_db_id,),
        )
        connection.execute(
            "UPDATE m5_cycles SET status='collection_closed',collection_closed_at=NOW(),close_reason='time_limit',updated_at=NOW() WHERE id=%s",
            (cycle_db_id,),
        )
        connection.execute(
            "UPDATE m5_cycle_sessions SET status='completed',ended_at=NOW(),close_reason='time_limit',updated_at=NOW() WHERE id=%s",
            (session_db_id,),
        )
        raise ValueError("M7_TIME_LIMIT_REACHED")
    return dict(row)


def begin_blocking_wait(connection, *, cycle_db_id: int, session_db_id: int, operation_ref: str, reason: str) -> dict[str, Any]:
    existing=connection.execute("SELECT * FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND operation_ref=%s",
        (cycle_db_id,operation_ref)).fetchone()
    if existing:return dict(existing)
    assert_collecting(connection,cycle_db_id=cycle_db_id,session_db_id=session_db_id)
    connection.execute("UPDATE m5_cycle_time_intervals SET ended_at=NOW() WHERE cycle_db_id=%s AND ended_at IS NULL",(cycle_db_id,))
    return dict(connection.execute("""INSERT INTO m5_cycle_time_intervals
        (cycle_db_id,session_db_id,interval_type,started_at,reason,operation_ref)
        VALUES(%s,%s,'blocking_system_wait',NOW(),%s,%s) RETURNING *""",(cycle_db_id,session_db_id,reason,operation_ref)).fetchone())


def end_blocking_wait(connection, *, cycle_db_id: int, session_db_id: int, operation_ref: str, reason: str) -> dict[str, Any]:
    interval=connection.execute("SELECT * FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND operation_ref=%s FOR UPDATE",
        (cycle_db_id,operation_ref)).fetchone()
    if not interval:raise ValueError('M7_BLOCKING_WAIT_NOT_FOUND')
    if interval['ended_at']:return dict(interval)
    connection.execute("UPDATE m5_cycle_time_intervals SET ended_at=NOW() WHERE id=%s",(interval['id'],))
    state=connection.execute("SELECT c.status,s.status AS session_status FROM m5_cycles c JOIN m5_cycle_sessions s ON s.id=%s WHERE c.id=%s FOR UPDATE OF c,s",
        (session_db_id,cycle_db_id)).fetchone()
    another_wait=connection.execute("""SELECT 1 FROM m5_cycle_time_intervals
        WHERE cycle_db_id=%s AND ended_at IS NULL AND interval_type<>'collecting' LIMIT 1""",
        (cycle_db_id,)).fetchone()
    if state and state['status']=='active' and state['session_status']=='active' and not another_wait:
        connection.execute("""INSERT INTO m5_cycle_time_intervals(cycle_db_id,session_db_id,interval_type,started_at,reason)
            VALUES(%s,%s,'collecting',NOW(),%s)""",(cycle_db_id,session_db_id,reason))
    return dict(connection.execute('SELECT * FROM m5_cycle_time_intervals WHERE id=%s',(interval['id'],)).fetchone())


def read_cycle(connection, cycle_id: str) -> dict[str, Any]:
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE cycle_id=%s", (UUID(cycle_id),)).fetchone()
    if not cycle:
        raise ValueError("M7_CYCLE_NOT_FOUND")
    sessions = connection.execute(
        "SELECT * FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal", (cycle["id"],)
    ).fetchall()
    result = dict(cycle)
    result["sessions"] = [dict(x) for x in sessions]
    consumed = connection.execute(
        """
        SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at,NOW())-started_at))),0)::BIGINT AS value
        FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND interval_type='collecting'
        """,
        (cycle["id"],),
    ).fetchone()["value"]
    result["consumed_seconds"] = int(consumed)
    result["remaining_seconds"] = max(0, int(cycle["time_budget_seconds"]) - int(consumed))
    result["calendar_deadline"] = (
        cycle["started_at"] + timedelta(seconds=int(cycle["calendar_window_seconds"]))
        if cycle["started_at"] else None
    )
    return result
