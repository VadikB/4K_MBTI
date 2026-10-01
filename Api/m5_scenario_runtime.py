"""Минимальный событийный исполнитель пяти M5 Case для assessment/QA scope."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from Api.m5_case_runtime import checksum
from Api.m5_rule_engine import (
    CharacterResponseAdapter,
    CharacterReply,
    ControlledCharacterAdapter,
    ControlledSemanticAdapter,
    DeepSeekCharacterAdapter,
    DeepSeekSemanticAdapter,
    RuleOutcome,
    SemanticDecisionAdapter,
    evaluate_rule,
    execute_frozen_ai_json,
)
from Api.snapshot_integrity import (
    SNAPSHOT_COMPOSITION_MISMATCH,
    SNAPSHOT_DEPENDENCY_UNAVAILABLE,
    SNAPSHOT_INTEGRITY_FAILED,
    SNAPSHOT_OWNER_MISMATCH,
    SnapshotIntegrityError,
)


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


def run_model_check_case03(connection, *, assessment_situation_id: str, scheme: dict, rules: dict,
                           initiated_by: str, scheme_authored_by: str, turn_id: str | None = None) -> dict:
    row = _as_row(connection, assessment_situation_id, lock=True)
    if row["status"] != "active" or row["snapshot_json"]["case_ref"]["id"] != "CASE-TDISC-03":
        raise ValueError("MODEL_CHECK_NOT_APPLICABLE")
    if initiated_by == "assessee":
        if turn_id is None or not connection.execute(
            "SELECT 1 AS ok FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s AND turn_id=%s AND speaker_type='assessee'",
            (row["id"], UUID(turn_id)),
        ).fetchone():
            raise ValueError("MODEL_CHECK_REQUIRES_REAL_ASSESSEE_TURN")
    key = checksum({"scheme": scheme, "initiated_by": initiated_by, "scheme_authored_by": scheme_authored_by,
                    "turn_id": turn_id, "rules_version": rules["version"]})
    requested = append_event(connection, as_db_id=int(row["id"]), event_type="model_check_requested",
                             event_key=f"model-check-requested:{key}",
                             cause={"initiated_by": initiated_by, "scheme_authored_by": scheme_authored_by,
                                    "turn_id": turn_id}, payload={"scheme": scheme, "rules_version": rules["version"]})
    result = model_check_case03(scheme, rules=rules, initiated_by=initiated_by, scheme_authored_by=scheme_authored_by)
    event_type = "model_check_indeterminate" if result["status"] == "INDETERMINATE" else "model_check_completed"
    completed = append_event(connection, as_db_id=int(row["id"]), event_type=event_type,
                             event_key=f"model-check-result:{key}",
                             cause={"requested_event_id": str(requested["event_id"]), "turn_id": turn_id}, payload=result)
    return {"result": result, "requested_event": requested, "result_event": completed}


def _as_row(connection, assessment_situation_id: str, *, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    row = connection.execute("SELECT * FROM m5_assessment_situations WHERE assessment_situation_id=%s" + suffix,
                             (UUID(assessment_situation_id),)).fetchone()
    if not row:
        raise ValueError("M5_AS_NOT_FOUND")
    snapshot = row.get("snapshot_json")
    if not isinstance(snapshot, dict) or checksum(snapshot) != row.get("snapshot_checksum"):
        raise SnapshotIntegrityError(SNAPSHOT_INTEGRITY_FAILED, "M5 AS checksum does not match payload.")
    if str(snapshot.get("assessment_situation_id")) != str(row["assessment_situation_id"]):
        raise SnapshotIntegrityError(SNAPSHOT_OWNER_MISMATCH, "M5 AS snapshot belongs to another AS.")
    execution_payload = row.get("execution_payload_json")
    execution_ref = snapshot.get("execution_payload_ref") or {}
    if not isinstance(execution_payload, dict) or checksum(execution_payload) != execution_ref.get("checksum"):
        raise SnapshotIntegrityError(
            SNAPSHOT_INTEGRITY_FAILED,
            "M5 execution payload checksum does not match its frozen reference.",
        )
    dependencies = connection.execute(
        """
        SELECT cv.case_id, cv.case_version, cv.content_checksum, pp.checksum AS profile_checksum
        FROM m5_case_versions cv
        JOIN assessment_personalized_profiles pp ON pp.id = %s
        WHERE cv.id = %s
        """,
        (row["personalized_profile_id"], row["case_version_id"]),
    ).fetchone()
    if not dependencies:
        raise SnapshotIntegrityError(SNAPSHOT_DEPENDENCY_UNAVAILABLE, "M5 AS dependency is unavailable.")
    case_ref = snapshot.get("case_ref") or {}
    profile_ref = snapshot.get("profile_ref") or {}
    if (
        case_ref.get("id") != dependencies["case_id"]
        or str(case_ref.get("version")) != str(dependencies["case_version"])
        or case_ref.get("checksum") != dependencies["content_checksum"]
        or profile_ref.get("checksum") != dependencies["profile_checksum"]
        or profile_ref.get("id") != f"assessment_personalized_profiles:{row['personalized_profile_id']}"
    ):
        raise SnapshotIntegrityError(
            SNAPSHOT_COMPOSITION_MISMATCH,
            "M5 AS references do not match its frozen CaseVersion or PersonalizedProfile.",
        )
    return row


def _next_sequence(connection, as_db_id: int) -> int:
    row = connection.execute("""
        SELECT GREATEST(COALESCE((SELECT max(sequence_no) FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s),0),
                        COALESCE((SELECT max(sequence_no) FROM m5_scenario_events WHERE assessment_situation_db_id=%s),0))+1 AS n
    """, (as_db_id, as_db_id)).fetchone()
    return int(row["n"])


def build_execution_envelope(connection, row: dict) -> dict:
    snapshot = row["snapshot_json"]
    if checksum(snapshot) != row["snapshot_checksum"]:
        raise SnapshotIntegrityError(SNAPSHOT_INTEGRITY_FAILED, "M5 AS checksum does not match payload.")
    admitted = bool(snapshot["admission"]["admitted"])
    qa_override = connection.execute(
        "SELECT id, authorized_by, reason, admission_unchanged FROM m5_qa_overrides WHERE assessment_situation_db_id=%s",
        (row["id"],),
    ).fetchone()
    if not admitted and not (row["usage_scope"] == "qa" and qa_override):
        raise ValueError("AS_NOT_ADMITTED")
    return {
        "schema_version": 1, "contract": "C-34", "assessment_situation_ref": {
            "id": str(row["assessment_situation_id"]), "version": "1", "checksum": row["snapshot_checksum"]},
        "execution_payload_ref": snapshot["execution_payload_ref"],
        "participant_payload_checksum": checksum(snapshot["participant_payload"]),
        "indicator_ids": [x["indicator_id"] for x in snapshot["indicator_targets"]],
        "admitted": admitted, "usage_scope": row["usage_scope"],
        "qa_override_ref": f"m5_qa_overrides:{qa_override['id']}" if qa_override else None,
        "admission_unchanged": bool(qa_override["admission_unchanged"]) if qa_override else True,
    }


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


def _state(connection, row: dict, *, lock: bool = False) -> dict:
    suffix = " FOR UPDATE" if lock else ""
    saved = connection.execute(
        "SELECT * FROM m5_scenario_states WHERE assessment_situation_db_id=%s" + suffix, (row["id"],)
    ).fetchone()
    if saved:
        return dict(saved)
    rules = row["execution_payload_json"].get("runtime_rules", {})
    stages = sorted(row["execution_payload_json"].get("scenario", []), key=lambda x: x["order"])
    initial_stage = stages[0]["step_id"] if stages else "S1"
    initial = {
        "status": row["status"], "current_stage": initial_stage, "disclosed_materials": [],
        "opened_branches": [], "not_opened_branches": [], "applied_effects": [],
    }
    return dict(connection.execute("""
        INSERT INTO m5_scenario_states
            (assessment_situation_db_id, revision, current_stage, state_json, rules_checksum)
        VALUES (%s,0,%s,%s::jsonb,%s) RETURNING *
    """, (row["id"], initial_stage, json.dumps(initial, ensure_ascii=False), checksum(rules))).fetchone())


def _save_state(connection, saved: dict, value: dict) -> dict:
    updated = connection.execute("""
        UPDATE m5_scenario_states SET revision=revision+1, current_stage=%s, state_json=%s::jsonb, updated_at=NOW()
        WHERE assessment_situation_db_id=%s AND revision=%s RETURNING *
    """, (value["current_stage"], json.dumps(value, ensure_ascii=False), saved["assessment_situation_db_id"],
          saved["revision"])).fetchone()
    if not updated:
        raise ValueError("M5_STATE_REVISION_CONFLICT")
    return dict(updated)


def _record_decision(connection, *, row: dict, saved: dict, key: str, rule: dict, decision) -> dict:
    existing = connection.execute(
        "SELECT * FROM m5_rule_decisions WHERE assessment_situation_db_id=%s AND decision_key=%s",
        (row["id"], key),
    ).fetchone()
    if existing:
        return dict(existing)
    recorded = dict(connection.execute("""
        INSERT INTO m5_rule_decisions
            (assessment_situation_db_id,decision_id,decision_key,rule_id,rule_version,input_revision,outcome,decision_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *
    """, (row["id"], uuid4(), key, rule["rule_id"], rule.get("version", "1"), saved["revision"],
          decision.outcome.value, json.dumps(decision.as_dict(), ensure_ascii=False))).fetchone())
    connection.execute("""
        UPDATE m5_ai_attempts SET accepted_result_ref=%s
        WHERE assessment_situation_db_id=%s AND action_key=%s AND outcome='accepted'
    """, (f"m5_rule_decisions:{recorded['decision_id']}", row["id"], key))
    return recorded


def _record_ai_attempt(connection, *, row: dict, action_key: str, action_type: str,
                       boundary_sequence: int, input_value: dict, result: object) -> dict | None:
    ai_trace = getattr(result, "ai_trace", None)
    if not isinstance(ai_trace, dict):
        return None
    outcome_value = getattr(getattr(result, "outcome", None), "value", None)
    result_status = getattr(result, "status", None)
    accepted = outcome_value in {"TRUE", "FALSE", "UNKNOWN"} or result_status == "COMPLETED"
    identity_status = ai_trace.get("identity_status")
    if identity_status == "technical_failure":
        outcome = "technical_failure"
        code = "PROVIDER_CALL_FAILED"
    elif identity_status == "sent_mismatch":
        outcome = "rejected"
        code = "M5_AI_SENT_CONFIG_MISMATCH"
    elif accepted:
        outcome = "accepted"
        code = "VALIDATED"
    else:
        outcome = "rejected"
        code = getattr(result, "code", None) or "OUTPUT_REJECTED"
    existing = connection.execute(
        "SELECT * FROM m5_ai_attempts WHERE assessment_situation_db_id=%s AND action_key=%s",
        (row["id"], action_key),
    ).fetchone()
    if existing:
        return dict(existing)
    return dict(connection.execute("""
        INSERT INTO m5_ai_attempts
            (assessment_situation_db_id,action_key,action_type,request_id,attempt_id,boundary_sequence,
             input_checksum,intended_json,sent_json,provider_json,response_json,outcome,validation_json)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb) RETURNING *
    """, (row["id"], action_key, action_type, uuid4(), uuid4(), boundary_sequence,
          checksum(input_value), json.dumps(ai_trace.get("intended") or {}, ensure_ascii=False),
          json.dumps(ai_trace.get("sent") or {}, ensure_ascii=False),
          json.dumps(ai_trace.get("provider") or {}, ensure_ascii=False),
          json.dumps(ai_trace.get("response") or {}, ensure_ascii=False), outcome,
          json.dumps({"code": code, "identity_status": identity_status}, ensure_ascii=False))).fetchone())


def _evaluate(connection, *, row: dict, saved: dict, operation_key: str, rule: dict, state: dict,
              text: str, turn_id: str, adapter: SemanticDecisionAdapter):
    request_value = {"rule": rule, "text": text, "turn_id": turn_id, "state_revision": saved["revision"]}
    operation = None
    if rule["type"] == "semantic_decision":
        operation = connection.execute("""
            INSERT INTO m5_semantic_operations
                (assessment_situation_db_id,operation_id,operation_key,input_revision,input_checksum,status,request_json)
            VALUES (%s,%s,%s,%s,%s,'pending',%s::jsonb)
            ON CONFLICT (assessment_situation_db_id,operation_key) DO UPDATE SET operation_key=EXCLUDED.operation_key
            RETURNING *
        """, (row["id"], uuid4(), operation_key, saved["revision"], checksum(request_value),
              json.dumps(request_value, ensure_ascii=False))).fetchone()
        if operation["status"] == "completed":
            from Api.m5_rule_engine import Decision
            value = operation["result_json"]
            return Decision(RuleOutcome(value["outcome"]), value["code"], value["basis"], tuple(value["turn_ids"]),
                            value["handler_version"], value["adapter"], value.get("model"), value["controlled_test"],
                            value.get("prompt_ref"))
    decision = evaluate_rule(rule, state=state, data={}, text=text, turn_id=turn_id, semantic_adapter=adapter)
    _record_ai_attempt(connection, row=row, action_key=operation_key, action_type="semantic_decision",
                       boundary_sequence=_next_sequence(connection, int(row["id"])) - 1,
                       input_value=request_value, result=decision)
    if operation:
        current = connection.execute("SELECT status FROM m5_assessment_situations WHERE id=%s", (row["id"],)).fetchone()
        current_state = connection.execute("SELECT revision FROM m5_scenario_states WHERE assessment_situation_db_id=%s", (row["id"],)).fetchone()
        late = current["status"] not in {"active", "paused"} or int(current_state["revision"]) != int(saved["revision"])
        connection.execute("""
            UPDATE m5_semantic_operations SET status=%s, result_json=%s::jsonb, completed_at=NOW() WHERE id=%s
        """, ("rejected_late" if late else "completed", json.dumps(decision.as_dict(), ensure_ascii=False), operation["id"]))
        if late:
            append_event(connection, as_db_id=int(row["id"]), event_type="late_result_rejected",
                         event_key=f"late:{operation['operation_id']}", cause={"operation_id": str(operation["operation_id"])})
            from Api.m5_rule_engine import Decision
            return Decision(RuleOutcome.ERROR, "LATE_RESULT_REJECTED", "AS state changed", (turn_id,))
    return decision


def _apply_material(connection, *, row: dict, saved: dict, state: dict, material: dict, decision_row: dict,
                    turn_id: str, event_type: str) -> dict | None:
    material_id = material["material_id"]
    effect_key = f"material:{material_id}"
    if effect_key in state["applied_effects"]:
        return None
    if material["disclosure_condition"].get("type") in {"semantic_request", "method_owner_unresolved"}:
        append_event(connection, as_db_id=int(row["id"]), event_type="conditional_branch_opened",
                     event_key=f"branch-opened:{material_id}",
                     cause={"turn_id": turn_id, "decision_id": str(decision_row["decision_id"])},
                     material_id=material_id, payload={"condition_confirmed": True})
        state["opened_branches"].append(material_id)
    event = append_event(
        connection, as_db_id=int(row["id"]), event_type=event_type, event_key=effect_key,
        cause={"turn_id": turn_id, "decision_id": str(decision_row["decision_id"]),
               "rule_id": decision_row["rule_id"], "rule_version": decision_row["rule_version"]},
        material_id=material_id, payload={"content": material["participant_payload"], "recipient": "assessee"},
    )
    state["applied_effects"].append(effect_key)
    state["disclosed_materials"].append(material_id)
    connection.execute("""
        INSERT INTO m5_effect_applications
            (assessment_situation_db_id,effect_key,effect_type,rule_decision_id,event_id,state_revision)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
    """, (row["id"], effect_key, event_type, decision_row["id"], event["id"], saved["revision"] + 1))
    return event


def _apply_character_response(connection, *, row: dict, saved: dict, state: dict, material: dict,
                              decision_row: dict, trigger_turn: dict, adapter: CharacterResponseAdapter) -> dict | None:
    effect_key = f"character-response:{material['material_id']}"
    if effect_key in state["applied_effects"]:
        return None
    character = next((x for x in row["execution_payload_json"]["characters"]
                      if x["character_id"] == material.get("speaker_id")), None)
    if not character:
        raise ValueError("CHARACTER_RESPONSE_SPEAKER_UNRESOLVED")
    reply = adapter.respond(material=material, character=character, text=trigger_turn["content_text"],
                            turn_id=str(trigger_turn["turn_id"]),
                            context={"disclosed_materials": state["disclosed_materials"], "stage": state["current_stage"]})
    _record_ai_attempt(
        connection, row=row, action_key=effect_key, action_type="character_response",
        boundary_sequence=int(trigger_turn["sequence_no"]),
        input_value={"material_id": material["material_id"], "character_id": character["character_id"],
                     "turn_id": str(trigger_turn["turn_id"]), "state_revision": saved["revision"]},
        result=reply,
    )
    if reply.status != "COMPLETED" or not reply.content:
        return None
    character_turn = connection.execute("""
        INSERT INTO m5_dialogue_turns
            (assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES (%s,%s,%s,'character',%s,%s,%s) RETURNING *
    """, (row["id"], uuid4(), _next_sequence(connection, int(row["id"])), character["character_id"], reply.content,
          f"character:{trigger_turn['request_id']}:{material['material_id']}")).fetchone()
    connection.execute("""
        UPDATE m5_ai_attempts SET accepted_result_ref=%s
        WHERE assessment_situation_db_id=%s AND action_key=%s AND outcome='accepted'
    """, (f"m5_dialogue_turns:{character_turn['turn_id']}", row["id"], effect_key))
    event = append_event(
        connection, as_db_id=int(row["id"]), event_type="character_response", event_key=effect_key,
        cause={"trigger_turn_id": str(trigger_turn["turn_id"]), "character_turn_id": str(character_turn["turn_id"]),
               "decision_id": str(decision_row["decision_id"]), "rule_id": decision_row["rule_id"]},
        material_id=material["material_id"],
        payload={"speaker_id": character["character_id"], "response": reply.content, "adapter": reply.adapter,
                 "model": reply.model, "controlled_test": reply.controlled_test, "prompt_ref": reply.prompt_ref})
    state["applied_effects"].append(effect_key)
    connection.execute("""
        INSERT INTO m5_effect_applications
            (assessment_situation_db_id,effect_key,effect_type,rule_decision_id,event_id,state_revision)
        VALUES (%s,%s,'character_response',%s,%s,%s) ON CONFLICT DO NOTHING
    """, (row["id"], effect_key, decision_row["id"], event["id"], saved["revision"] + 1))
    return event


def start(connection, assessment_situation_id: str) -> dict:
    row = _as_row(connection, assessment_situation_id, lock=True)
    if row["status"] == "rejected" and row["usage_scope"] != "qa":
        raise ValueError("AS_NOT_ADMITTED")
    if row["status"] == "rejected" and row["usage_scope"] == "qa" and not connection.execute(
        "SELECT 1 AS ok FROM m5_qa_overrides WHERE assessment_situation_db_id=%s AND admission_unchanged",
        (row["id"],),
    ).fetchone():
        raise ValueError("QA_SERVER_AUTHORIZATION_REQUIRED")
    if row["status"] not in {"admitted", "rejected", "active"}:
        raise ValueError("M5_AS_CANNOT_START")
    envelope = build_execution_envelope(connection, row)
    connection.execute("UPDATE m5_assessment_situations SET status='active', started_at=COALESCE(started_at,NOW()) WHERE id=%s", (row["id"],))
    saved = _state(connection, row, lock=True)
    state = dict(saved["state_json"])
    state["status"] = "active"
    if saved["state_json"].get("status") != "active":
        _save_state(connection, saved, state)
    event = append_event(connection, as_db_id=int(row["id"]), event_type="scenario_started", event_key="scenario_started",
                         cause={"type": "C-34", "scope": row["usage_scope"]}, payload={"execution_envelope": envelope})
    return {"status": "active", "participant_payload": row["snapshot_json"]["participant_payload"],
            "execution_envelope": envelope, "event": event}


def submit_turn(connection, *, assessment_situation_id: str, request_id: str, turn_id: str, content: str,
                semantic_adapter: SemanticDecisionAdapter | None = None,
                character_adapter: CharacterResponseAdapter | None = None) -> dict:
    row = _as_row(connection, assessment_situation_id, lock=True)
    if row["status"] != "active":
        raise ValueError("M5_AS_NOT_ACTIVE")
    existing = connection.execute("SELECT * FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s AND request_id=%s",
                                  (row["id"], request_id)).fetchone()
    if existing:
        events = [dict(x) for x in connection.execute(
            "SELECT * FROM m5_scenario_events WHERE assessment_situation_db_id=%s AND cause_json->>'turn_id'=%s ORDER BY sequence_no",
            (row["id"], str(existing["turn_id"]))).fetchall()]
        return {"turn": dict(existing), "events": events, "idempotent": True}
    saved = _state(connection, row, lock=True)
    state = dict(saved["state_json"])
    turn = connection.execute("""
        INSERT INTO m5_dialogue_turns (assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES (%s,%s,%s,'assessee','assessee',%s,%s) RETURNING *
    """, (row["id"], UUID(turn_id), _next_sequence(connection, int(row["id"])), content, request_id)).fetchone()
    events = []
    payload = row["execution_payload_json"]
    operations = row["execution_payload_json"].get("ai_operations") or {}
    if semantic_adapter is None and not operations.get("semantic_decision"):
        raise SnapshotIntegrityError(SNAPSHOT_DEPENDENCY_UNAVAILABLE, "Frozen semantic AI configuration is missing.")
    if character_adapter is None and not operations.get("character_response"):
        raise SnapshotIntegrityError(SNAPSHOT_DEPENDENCY_UNAVAILABLE, "Frozen character AI configuration is missing.")
    adapter = semantic_adapter or DeepSeekSemanticAdapter(operation=operations["semantic_decision"])
    responder = character_adapter or DeepSeekCharacterAdapter(operation=operations["character_response"])
    for material in payload["materials"]:
        condition = material["disclosure_condition"]
        event_condition = material["event_condition"]
        is_character_reaction = material.get("kind") == "character_reaction"
        if not is_character_reaction and (material.get("participant_payload") is None or condition.get("type") == "never"):
            continue
        candidates = []
        if condition.get("type") == "semantic_request":
            candidates.append(("disclosure", condition, "material_disclosed"))
        elif condition.get("type") == "method_owner_unresolved" and isinstance(adapter, ControlledSemanticAdapter):
            candidates.append(("qa_unresolved_branch", condition, "material_disclosed"))
        event_kind = event_condition.get("type", "")
        if event_kind == "after_first_substantive_turn":
            candidates.append(("mandatory", event_condition, "mandatory_update"))
        elif event_kind.startswith("after_first_"):
            candidates.append(("mandatory", event_condition, "mandatory_update"))
        elif is_character_reaction and event_kind.startswith("on_"):
            candidates.append(("character_reaction", event_condition, "character_response"))
        for purpose, specification, event_type in candidates:
            rule_id = f"{material['material_id']}:{purpose}"
            if event_kind == "after_first_substantive_turn" and purpose == "mandatory":
                rule = {"rule_id": rule_id, "version": "1", "type": "state_predicate", "field": "status", "equals": "active"}
            else:
                rule = {"rule_id": rule_id, "version": "1", "type": "semantic_decision",
                        "decision_code": specification.get("type", "semantic"), "condition": specification,
                        "allowed_codes": ["MATCH", "NO_MATCH", "UNKNOWN"], "true_code": "MATCH"}
            decision = _evaluate(connection, row=row, saved=saved, operation_key=f"{request_id}:{rule_id}",
                                 rule=rule, state=state, text=content, turn_id=str(turn["turn_id"]), adapter=adapter)
            decision_row = _record_decision(connection, row=row, saved=saved,
                                            key=f"{request_id}:{rule_id}", rule=rule, decision=decision)
            if decision.outcome == RuleOutcome.TRUE:
                event = (_apply_character_response(connection, row=row, saved=saved, state=state, material=material,
                                                   decision_row=decision_row, trigger_turn=turn, adapter=responder)
                         if purpose == "character_reaction" else
                         _apply_material(connection, row=row, saved=saved, state=state, material=material,
                                         decision_row=decision_row, turn_id=str(turn["turn_id"]), event_type=event_type))
                if event:
                    events.append(event)
    stages = sorted(payload.get("scenario", []), key=lambda x: x["order"])
    current_index = next((i for i, item in enumerate(stages) if item["step_id"] == state["current_stage"]), None)
    if current_index is not None:
        stage = stages[current_index]
        rule = {"rule_id": f"{payload['case_id']}:{stage['step_id']}:completion", "version": "1",
                "type": "semantic_decision", "decision_code": "STAGE_COMPLETION",
                "condition": {"stage": stage["title"], "rules": stage["rules"]},
                "allowed_codes": ["MATCH", "NO_MATCH", "UNKNOWN"], "true_code": "MATCH"}
        decision = _evaluate(connection, row=row, saved=saved, operation_key=f"{request_id}:{rule['rule_id']}",
                             rule=rule, state=state, text=content, turn_id=str(turn["turn_id"]), adapter=adapter)
        decision_row = _record_decision(connection, row=row, saved=saved, key=f"{request_id}:{rule['rule_id']}",
                                        rule=rule, decision=decision)
        if decision.outcome == RuleOutcome.TRUE:
            target = stages[current_index + 1]["step_id"] if current_index + 1 < len(stages) else "ready_for_scenario_end"
            event = append_event(connection, as_db_id=int(row["id"]), event_type="stage_transitioned",
                                 event_key=f"stage:{stage['step_id']}:{target}",
                                 cause={"turn_id": str(turn["turn_id"]), "decision_id": str(decision_row["decision_id"]),
                                        "rule_id": rule["rule_id"]}, payload={"from": stage["step_id"], "to": target})
            state["current_stage"] = target
            events.append(event)
    _save_state(connection, saved, state)
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
        ("active", "scenario_end"): "scenario_ended", ("active", "terminate"): "terminated",
        ("scenario_ended", "close"): "closed", ("paused", "terminate"): "terminated",
    }
    target = transitions.get((row["status"], action))
    if not target:
        raise ValueError("M5_INVALID_STATE_TRANSITION")
    if action == "scenario_end":
        disclosed = set((_state(connection, row, lock=True)["state_json"] or {}).get("disclosed_materials", []))
        for material in row["execution_payload_json"].get("materials", []):
            if material["disclosure_condition"].get("type") in {"semantic_request", "method_owner_unresolved"} and material["material_id"] not in disclosed:
                append_event(connection, as_db_id=int(row["id"]), event_type="conditional_branch_not_opened",
                             event_key=f"branch-not-opened:{material['material_id']}",
                             cause={"transition_request_id": request_id, "reason": "condition_not_confirmed"},
                             material_id=material["material_id"], payload={"condition_available": True})
    timestamps = ", scenario_ended_at=NOW()" if target in {"scenario_ended", "terminated"} else ", closed_at=NOW()" if target == "closed" else ""
    connection.execute(f"UPDATE m5_assessment_situations SET status=%s{timestamps} WHERE id=%s", (target, row["id"]))
    event_types = {"pause": "interaction_paused", "resume": "interaction_resumed", "scenario_end": "scenario_completed",
                   "terminate": "interaction_terminated", "close": "assessment_situation_closed"}
    event = append_event(connection, as_db_id=int(row["id"]), event_type=event_types[action], event_key=f"transition:{request_id}",
                         cause={"reason": reason, "from": row["status"], "to": target}, payload={"status": target})
    saved = _state(connection, row, lock=True)
    state = dict(saved["state_json"])
    state["status"] = target
    if target == "scenario_ended":
        state["current_stage"] = "scenario_end"
    _save_state(connection, saved, state)
    return {"status": target, "event": event, "idempotent": False}


def trace(connection, assessment_situation_id: str) -> dict:
    row = _as_row(connection, assessment_situation_id)
    turns = [dict(x) for x in connection.execute("SELECT * FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s ORDER BY sequence_no", (row["id"],)).fetchall()]
    events = [dict(x) for x in connection.execute("SELECT * FROM m5_scenario_events WHERE assessment_situation_db_id=%s ORDER BY sequence_no", (row["id"],)).fetchall()]
    state = connection.execute("SELECT * FROM m5_scenario_states WHERE assessment_situation_db_id=%s", (row["id"],)).fetchone()
    decisions = [dict(x) for x in connection.execute(
        "SELECT * FROM m5_rule_decisions WHERE assessment_situation_db_id=%s ORDER BY id", (row["id"],)).fetchall()]
    ai_attempts = [dict(x) for x in connection.execute(
        "SELECT * FROM m5_ai_attempts WHERE assessment_situation_db_id=%s ORDER BY id", (row["id"],)).fetchall()]
    c54_receipts = [dict(x) for x in connection.execute(
        "SELECT * FROM m5_c54_receipts WHERE assessment_situation_db_id=%s ORDER BY id", (row["id"],)).fetchall()]
    return {"assessment_situation_id": assessment_situation_id, "status": row["status"], "turns": turns,
            "events": events, "state": dict(state) if state else None, "decisions": decisions,
            "ai_attempts": ai_attempts, "c54_receipts": c54_receipts}


def build_c45(connection, assessment_situation_id: str, *, mode: str = "final") -> dict:
    row = _as_row(connection, assessment_situation_id, lock=True)
    if mode == "interim" and row["status"] != "scenario_ended":
        raise ValueError("C45_INTERIM_REQUIRES_SCENARIO_END_AND_OPEN_AS")
    if mode == "final" and row["status"] != "closed":
        raise ValueError("C45_FINAL_REQUIRES_CLOSED_AS")
    saved = trace(connection, assessment_situation_id)
    sequences = [int(x["sequence_no"]) for x in saved["turns"] + saved["events"]]
    boundary = max(sequences, default=0)
    existing = connection.execute("""
        SELECT * FROM m5_c45_handoffs
        WHERE assessment_situation_db_id=%s AND mode=%s AND boundary_sequence=%s
    """, (row["id"], mode, boundary)).fetchone()
    if existing:
        return dict(existing)
    snapshot = row["snapshot_json"]
    profile_row = connection.execute(
        "SELECT content_json, checksum FROM assessment_personalized_profiles WHERE id=%s",
        (row["personalized_profile_id"],),
    ).fetchone()
    if not profile_row or profile_row["checksum"] != snapshot["profile_ref"]["checksum"]:
        raise SnapshotIntegrityError(SNAPSHOT_DEPENDENCY_UNAVAILABLE, "Frozen PersonalizedProfile is unavailable.")
    presented_materials = [
        {"material_id": x["material_id"], "event_id": str(x["event_id"]),
         "sequence_no": x["sequence_no"], "available_at": x["created_at"].isoformat(),
         "event_type": x["event_type"]}
        for x in saved["events"]
        if x["material_id"] and x["event_type"] in {"material_disclosed", "mandatory_update", "character_response"}
    ]
    envelope = {
        "schema_version": 1, "contract": "C-45", "mode": mode,
        "assessment_situation_ref": {"id": assessment_situation_id, "checksum": row["snapshot_checksum"]},
        "case_ref": snapshot["case_ref"], "profile_ref": snapshot["profile_ref"],
        "profile_snapshot": profile_row["content_json"], "base_role": snapshot["base_role"],
        "cycle_ref": snapshot.get("cycle_ref"), "session_ref": snapshot.get("session_ref"),
        "methodology_refs": snapshot["methodology_refs"], "indicator_targets": snapshot["indicator_targets"],
        "dialogue": {
            "turns": [{"turn_id": str(x["turn_id"]), "sequence_no": x["sequence_no"],
                       "speaker_type": x["speaker_type"], "speaker_id": x["speaker_id"],
                       "content": x["content_text"], "created_at": x["created_at"].isoformat()} for x in saved["turns"]],
            "events": [{"event_id": str(x["event_id"]), "sequence_no": x["sequence_no"],
                         "event_type": x["event_type"], "material_id": x["material_id"],
                         "cause": x["cause_json"], "payload": x["payload_json"],
                         "created_at": x["created_at"].isoformat()} for x in saved["events"]],
        },
        "presented_materials": presented_materials,
        "rule_decisions": [{"decision_id": str(x["decision_id"]), "rule_id": x["rule_id"],
                            "outcome": x["outcome"], "decision": x["decision_json"]} for x in saved["decisions"]],
        "runtime_state": saved["state"]["state_json"] if saved["state"] else None,
        "boundary_sequence": boundary, "boundary": {"inclusive_sequence": boundary,
            "turn_ids": [str(x["turn_id"]) for x in saved["turns"]],
            "event_ids": [str(x["event_id"]) for x in saved["events"]]},
        "assessment_situation_status": row["status"],
        "execution_payload_ref": snapshot["execution_payload_ref"],
        "sender_version": "m5-runtime/2",
        "receiver_mode": "technical_adapter", "evaluation_created": False,
        "evaluation_request": {
            "status": "not_created",
            "evaluator_ref": None,
            "rules_ref": None,
            "reason": "PM-05 evaluator is outside the implemented M5 runtime",
        },
    }
    digest = checksum(envelope)
    return dict(connection.execute("""
        INSERT INTO m5_c45_handoffs
            (assessment_situation_db_id,handoff_id,mode,boundary_sequence,envelope_json,envelope_checksum,receiver_status,receiver_ref)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s,'accepted','technical-pm05-adapter/1') RETURNING *
    """, (row["id"], uuid4(), mode, boundary, json.dumps(envelope, ensure_ascii=False), digest)).fetchone())


def _validate_technical_c54(*, row: dict, handoff: dict, payload: dict, indicator_id: str) -> list[str]:
    envelope = handoff["envelope_json"]
    errors = []
    expected = {
        "contract": "C-54", "assessment_situation_id": str(row["assessment_situation_id"]),
        "handoff_id": str(handoff["handoff_id"]), "mode": handoff["mode"],
        "indicator_id": indicator_id, "boundary_sequence": handoff["boundary_sequence"],
        "status": "technical_received",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append(f"{key}:mismatch")
    target = next((x for x in envelope["indicator_targets"] if x["indicator_id"] == indicator_id), None)
    if not target:
        errors.append("indicator_id:unknown")
    elif payload.get("m2_version") != target["m2_version"]:
        errors.append("m2_version:mismatch")
    if handoff["mode"] == "final" and row["status"] != "closed":
        errors.append("assessment_situation:not_final")
    return errors


def execute_technical_c45(connection, *, assessment_situation_id: str, indicator_id: str,
                          mode: str = "final", gateway=None) -> dict:
    """QA-only transport proof. It never creates Evidence, IA or an assessment result."""
    row = _as_row(connection, assessment_situation_id, lock=True)
    if row["usage_scope"] != "qa":
        raise ValueError("M5_TECHNICAL_C45_QA_ONLY")
    handoff = build_c45(connection, assessment_situation_id, mode=mode)
    existing = connection.execute(
        "SELECT * FROM m5_c54_receipts WHERE handoff_id=%s AND indicator_id=%s",
        (handoff["handoff_id"], indicator_id),
    ).fetchone()
    if existing:
        return dict(existing)
    target = next((x for x in handoff["envelope_json"]["indicator_targets"] if x["indicator_id"] == indicator_id), None)
    if not target:
        raise ValueError("C54_INDICATOR_OUTSIDE_C45")
    operation = (row["execution_payload_json"].get("ai_operations") or {}).get("technical_c45")
    if not operation:
        raise ValueError("M5_TECHNICAL_C45_CONFIG_MISSING")
    input_value = {"handoff_id": str(handoff["handoff_id"]), "indicator_id": indicator_id,
                   "m2_version": target["m2_version"], "c45": handoff["envelope_json"]}
    action_key = f"technical-c45:{handoff['handoff_id']}:{indicator_id}"
    try:
        payload, ai_trace = execute_frozen_ai_json(
            operation=operation, prompt_bundle="m5_technical_c45", input_value=input_value, gateway=gateway,
            routing_key=action_key,
        )
        errors = _validate_technical_c54(row=row, handoff=handoff, payload=payload, indicator_id=indicator_id)
        if ai_trace.get("identity_status") == "sent_mismatch":
            errors.append("sent_config:mismatch")
        result = CharacterReply("COMPLETED" if not errors else "ERROR", None, "deepseek",
                                operation["model"], prompt_ref=operation["prompt_ref"], ai_trace=ai_trace)
        _record_ai_attempt(connection, row=row, action_key=action_key, action_type="technical_c45",
                           boundary_sequence=int(handoff["boundary_sequence"]), input_value=input_value, result=result)
        status = "accepted" if not errors else "rejected"
    except Exception as exc:
        payload = {"technical_error": type(exc).__name__}
        errors = [str(exc)]
        ai_trace = getattr(exc, "ai_trace", None) or {
            "intended": {key: operation.get(key) for key in
                         ("provider", "endpoint", "model", "parameters", "prompt_ref", "response_format")},
            "sent": {}, "provider": {}, "response": {}, "identity_status": "technical_failure",
        }
        result = CharacterReply("ERROR", None, "deepseek", operation["model"],
                                prompt_ref=operation["prompt_ref"], ai_trace=ai_trace)
        _record_ai_attempt(connection, row=row, action_key=action_key, action_type="technical_c45",
                           boundary_sequence=int(handoff["boundary_sequence"]), input_value=input_value, result=result)
        status = "technical_failure"
    receipt = connection.execute("""
        INSERT INTO m5_c54_receipts
            (assessment_situation_db_id,handoff_id,receipt_id,mode,indicator_id,m2_version,
             boundary_sequence,status,payload_json,validation_json,controlled_test)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE) RETURNING *
    """, (row["id"], handoff["handoff_id"], uuid4(), handoff["mode"], indicator_id,
          target["m2_version"], handoff["boundary_sequence"], status,
          json.dumps(payload, ensure_ascii=False), json.dumps({"errors": errors, "methodological_result": False}, ensure_ascii=False))).fetchone()
    if status == "accepted":
        connection.execute("""
            UPDATE m5_ai_attempts SET accepted_result_ref=%s
            WHERE assessment_situation_db_id=%s AND action_key=%s AND outcome='accepted'
        """, (f"m5_c54_receipts:{receipt['receipt_id']}", row["id"], action_key))
    return dict(receipt)
