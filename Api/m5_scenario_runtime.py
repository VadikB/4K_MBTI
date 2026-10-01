"""Минимальный событийный исполнитель пяти M5 Case для assessment/QA scope."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4


def model_check_case03(scheme: dict, *, rules: dict, initiated_by: str, scheme_authored_by: str) -> dict:
    rules_version = str(rules["version"])
    routes = scheme.get("routes") if isinstance(scheme, dict) else None
    if not isinstance(routes, dict) or any(key not in routes for key in "ABCDEF"):
        return {"status": "INDETERMINATE", "reason": "ROUTE_OR_CONDITION_NOT_SPECIFIED",
                "initiated_by": initiated_by, "scheme_authored_by": scheme_authored_by, "rules_version": rules_version}
    inputs = {key: (value.get("start"), value.get("duration_minutes"), value.get("deadline"))
              for key, value in rules["inputs"].items()}
    durations = rules["route_duration_minutes"]
    results = {}
    for key in "ABCDEF":
        route = routes[key]
        if route not in {"catalog", "unique", "defer", "reject_for_input"}:
            return {"status": "INDETERMINATE", "reason": f"UNKNOWN_ROUTE:{key}",
                    "initiated_by": initiated_by, "scheme_authored_by": scheme_authored_by, "rules_version": rules_version}
        start, duration, deadline = inputs[key]
        if start is None or route in {"defer", "reject_for_input"}:
            results[key] = {"route": route, "computable": route in {"defer", "reject_for_input"}, "finish": None}
            continue
        expected_duration = int(durations[route])
        if duration != expected_duration:
            duration = expected_duration
        finish = datetime.fromisoformat(start) + timedelta(minutes=duration)
        day_end = int(rules["workday"]["end_hour"])
        if finish.hour > day_end or (finish.hour == day_end and finish.minute):
            overflow = finish - finish.replace(hour=day_end, minute=0)
            finish = (finish + timedelta(days=1)).replace(hour=int(rules["workday"]["start_hour"]), minute=0) + overflow
        results[key] = {"route": route, "computable": True, "finish": finish.isoformat(timespec="minutes"),
                        "meets_deadline": finish <= datetime.fromisoformat(deadline)}
    return {"status": "COMPLETED", "results": results, "initiated_by": initiated_by,
            "scheme_authored_by": scheme_authored_by, "rules_version": rules_version}


def _as_row(connection, assessment_situation_id: str, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    row = connection.execute("SELECT * FROM m5_assessment_situations WHERE assessment_situation_id=%s" + suffix,
                             (UUID(assessment_situation_id),)).fetchone()
    if not row:
        raise ValueError("M5_AS_NOT_FOUND")
    return row


def _next_sequence(connection, as_db_id: int) -> int:
    row = connection.execute("""
        SELECT GREATEST(COALESCE((SELECT max(sequence_no) FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s),0),
                        COALESCE((SELECT max(sequence_no) FROM m5_scenario_events WHERE assessment_situation_db_id=%s),0))+1 AS n
    """, (as_db_id, as_db_id)).fetchone()
    return int(row["n"])


def append_event(connection, *, as_db_id: int, event_type: str, event_key: str, cause: dict,
                 payload: dict | None = None, material_id: str | None = None) -> dict:
    existing = connection.execute("SELECT * FROM m5_scenario_events WHERE assessment_situation_db_id=%s AND event_key=%s",
                                  (as_db_id, event_key)).fetchone()
    if existing:
        return dict(existing)
    row = connection.execute("""
        INSERT INTO m5_scenario_events (assessment_situation_db_id,event_id,event_type,event_key,cause_json,material_id,payload_json,sequence_no)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s) RETURNING *
    """, (as_db_id, uuid4(), event_type, event_key, json.dumps(cause, ensure_ascii=False), material_id,
          json.dumps(payload or {}, ensure_ascii=False), _next_sequence(connection, as_db_id))).fetchone()
    return dict(row)


def start(connection, assessment_situation_id: str) -> dict:
    row = _as_row(connection, assessment_situation_id, lock=True)
    if row["status"] == "rejected" and row["usage_scope"] != "qa":
        raise ValueError("AS_NOT_ADMITTED")
    if row["status"] not in {"admitted", "rejected", "active"}:
        raise ValueError("M5_AS_CANNOT_START")
    connection.execute("UPDATE m5_assessment_situations SET status='active', started_at=COALESCE(started_at,NOW()) WHERE id=%s", (row["id"],))
    event = append_event(connection, as_db_id=int(row["id"]), event_type="scenario_started", event_key="scenario_started",
                         cause={"type": "explicit_start", "scope": row["usage_scope"]})
    return {"status": "active", "participant_payload": row["snapshot_json"]["participant_payload"], "event": event}


def submit_turn(connection, *, assessment_situation_id: str, request_id: str, turn_id: str, content: str) -> dict:
    row = _as_row(connection, assessment_situation_id, lock=True)
    if row["status"] != "active":
        raise ValueError("M5_AS_NOT_ACTIVE")
    existing = connection.execute("SELECT * FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s AND request_id=%s",
                                  (row["id"], request_id)).fetchone()
    if existing:
        return {"turn": dict(existing), "events": [], "idempotent": True}
    turn = connection.execute("""
        INSERT INTO m5_dialogue_turns (assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES (%s,%s,%s,'assessee','assessee',%s,%s) RETURNING *
    """, (row["id"], UUID(turn_id), _next_sequence(connection, int(row["id"])), content, request_id)).fetchone()
    events = []
    payload = row["execution_payload_json"]
    lower = content.lower()
    for material in payload["materials"]:
        condition = material["disclosure_condition"]
        event_condition = material["event_condition"]
        disclose = condition.get("type") == "semantic_request" and any(topic.lower() in lower for topic in condition.get("topics", []))
        mandatory = event_condition.get("type", "").startswith("after_first_")
        if disclose or mandatory:
            if material.get("participant_payload") is None or condition.get("type") in {"never", "method_owner_unresolved"}:
                continue
            events.append(append_event(connection, as_db_id=int(row["id"]), event_type="material_disclosed",
                                       event_key=f"material:{material['material_id']}", cause={"turn_id": str(turn["turn_id"]), "condition": condition if disclose else event_condition},
                                       material_id=material["material_id"], payload={"content": material["participant_payload"]}))
    return {"turn": dict(turn), "events": events, "idempotent": False}


def transition(connection, *, assessment_situation_id: str, action: str, reason: str, request_id: str) -> dict:
    row = _as_row(connection, assessment_situation_id, lock=True)
    existing = connection.execute(
        "SELECT * FROM m5_scenario_events WHERE assessment_situation_db_id=%s AND event_key=%s",
        (row["id"], f"transition:{request_id}"),
    ).fetchone()
    if existing:
        return {"status": existing["payload_json"]["status"], "event": dict(existing), "idempotent": True}
    transitions = {
        ("active", "pause"): "paused", ("paused", "resume"): "active",
        ("active", "scenario_end"): "scenario_ended", ("active", "terminate"): "scenario_ended",
        ("scenario_ended", "close"): "closed", ("paused", "terminate"): "scenario_ended",
    }
    target = transitions.get((row["status"], action))
    if not target:
        raise ValueError("M5_INVALID_STATE_TRANSITION")
    timestamps = ", scenario_ended_at=NOW()" if target == "scenario_ended" else ", closed_at=NOW()" if target == "closed" else ""
    connection.execute(f"UPDATE m5_assessment_situations SET status=%s{timestamps} WHERE id=%s", (target, row["id"]))
    event = append_event(connection, as_db_id=int(row["id"]), event_type=action, event_key=f"transition:{request_id}",
                         cause={"reason": reason, "from": row["status"], "to": target}, payload={"status": target})
    return {"status": target, "event": event, "idempotent": False}


def trace(connection, assessment_situation_id: str) -> dict:
    row = _as_row(connection, assessment_situation_id)
    turns = [dict(x) for x in connection.execute("SELECT * FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s ORDER BY sequence_no", (row["id"],)).fetchall()]
    events = [dict(x) for x in connection.execute("SELECT * FROM m5_scenario_events WHERE assessment_situation_db_id=%s ORDER BY sequence_no", (row["id"],)).fetchall()]
    return {"assessment_situation_id": assessment_situation_id, "status": row["status"], "turns": turns, "events": events}
