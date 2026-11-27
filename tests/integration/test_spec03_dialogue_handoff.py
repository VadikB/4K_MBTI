"""Регрессия C-45 для двух ходов с явным завершением через HTTP.

Поместить в tests/integration/ в рабочей копии 4K. Запуск:
python -m pytest --run-integration -q tests/integration/test_spec03_dialogue_handoff.py

Только изолированная тестовая PostgreSQL. P4K_SOURCE_PROBE_OUTPUT задаёт
необязательный каталог для кратких технических квитанций по каждой ветви.
"""
from __future__ import annotations

import json
import os
import traceback
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from Api import m5_scenario_runtime as runtime
from Api import m6_assessment_worker_v2, m6_worker_v2, m10_orchestration, routes, web_session_service
from Api.assessment_configuration import definition_checksum
from Api.m5_case_runtime import checksum
from Api.m5_rule_engine import DeepSeekCharacterAdapter, DeepSeekSemanticAdapter
from Api.m6_input_resolver_v2 import normalize
from tests.integration.test_m5_battery_scenario_db import TurnGateway, matched
from tests.integration.test_m10_product_path_db import EvidenceGateway, RecordedAdmissionGateway
from tests.integration.test_specialist_pilot_release_db import opened_specialist_pilot, release_db
from tests.integration.test_task5_m6_interim_retry_db import (
    InterimAssessmentGateway, _request, _submit_to_interim,
)


pytestmark = pytest.mark.integration


def advance_interim(factory, situation_id):
    with factory() as db:
        job = _request(db, situation_id)
    m6_worker_v2.run_request(job["id"], connection_factory=factory, gateway=EvidenceGateway())
    for _ in range(40):
        changed = m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
        with factory() as db:
            queued = db.execute(
                "SELECT id FROM m6_assessment_requests WHERE mode='interim' AND as_db_id=%s AND status='queued'",
                (job["as_db_id"],),
            ).fetchone()
            decision = db.execute("""SELECT d.status FROM m7_clarification_decisions d
                JOIN m6_c54_revisions c ON d.c54_revision_id=c.id
                WHERE c.handoff_id=%s AND c.mode='interim'""", (job["handoff_id"],)).fetchone()
        if decision:
            assert decision["status"] == "NO_QUESTION"
            return decision["status"]
        if queued:
            m6_assessment_worker_v2.run_request(queued["id"], connection_factory=factory, gateway=InterimAssessmentGateway())
        else:
            assert changed, "Очередь не продвинулась"
    pytest.fail("Решение M7 не получено")


def present_next(pilot, current_id):
    http = pilot.client
    m7 = f"/users/assessment/m7/cycles/{pilot.cycle_id}"
    finished = http.post(m7 + "/finish-situation", json={"idempotency_key":"finish-" + current_id})
    assert finished.status_code == 200, finished.text
    job = pilot.worker._claim()
    assert job and job["operation_id"] == "next:" + current_id
    pilot.worker._process(job)
    operation = pilot.worker.get_status(job["operation_id"])
    assert operation["status"] == "completed", operation.get("error_code")
    state = http.get(f"/users/assessment/cycles/{pilot.cycle_id}/runtime").json()
    presented = http.post(m7 + "/present-next", json=state["next_presentation"])
    assert presented.status_code == 201, presented.text
    body = presented.json()["runtime"]
    assert body["cycle_id"] == pilot.cycle_id
    return body["current_situation"]["assessment_situation_id"]


def send_turn(http, monkeypatch, situation_id, text, rules, recipients, responses, *, control="CONTINUE", fragments=None):
    # Шлюз задаёт ответы модели. Все переходы, C-45 и очередь исполняет продукт.
    gateway = TurnGateway(rules, control=control, recipients=recipients, responses=responses, fragments=fragments)
    command = {"turn_id": str(uuid4()), "request_id": str(uuid4()), "content": text}
    with monkeypatch.context() as patch:
        patch.setattr(runtime, "DeepSeekSemanticAdapter", lambda **kw: DeepSeekSemanticAdapter(gateway, **kw))
        patch.setattr(runtime, "DeepSeekCharacterAdapter", lambda **kw: DeepSeekCharacterAdapter(gateway, **kw))
        receipt = http.post(f"/users/assessment/m5/situations/{situation_id}/turns", json=command)
    return receipt, command, gateway.character_calls


def observe_boundary(db, handoff_id):
    row = db.execute("""SELECT h.envelope_json AS envelope, s.execution_payload_json AS execution
                        FROM m5_c45_handoffs h JOIN m5_assessment_situations s ON s.id=h.assessment_situation_db_id
                        WHERE h.handoff_id=%s""", (handoff_id,)).fetchone()
    envelope, execution = row["envelope"], row["execution"]
    materials = {m["material_id"] for m in execution["materials"]}
    presented = [m["material_id"] for m in envelope["presented_materials"]]
    return {"handed_as_materials": presented, "top_level_materials": sorted(materials),
            "missing_from_top_level_materials": [m for m in presented if m not in materials]}


def check_document_references(db, as_id, criteria):
    """Изменения копий C-45 с действительным хешем каждой тестовой копии."""
    row = dict(db.execute(
        "SELECT * FROM m5_assessment_situations WHERE id=%s", (as_id,)
    ).fetchone())
    cycle = dict(db.execute("SELECT * FROM m5_cycles WHERE id=%s", (row["cycle_db_id"],)).fetchone())
    session = dict(db.execute(
        "SELECT * FROM m5_cycle_sessions WHERE id=%s", (row["session_db_id"],)
    ).fetchone())
    handoff = dict(db.execute(
        "SELECT * FROM m5_c45_handoffs WHERE assessment_situation_db_id=%s AND mode='interim'",
        (as_id,),
    ).fetchone())
    # Так общий нормализатор вызывается после проверки области в продуктовом адаптере M10.
    row["usage_scope"] = "qa"
    normalized = normalize(handoff, row, cycle, session, criteria)
    changes = {
        "unknown_material": "material_id",
        "foreign_event": "event_id",
        "wrong_event": "event_id",
        "wrong_sequence": "sequence_no",
        "wrong_scenario_rule": "payload.scenario_event_id",
        "wrong_content": "payload.content",
        "wrong_recipient": "payload.recipient_ids",
        "wrong_reply_recipient": "payload.recipient_ids",
        "missing_delivery": "presented_materials.event_id",
    }
    for changed, field in changes.items():
        copy = deepcopy(handoff)
        envelope = copy["envelope_json"]
        item = next(m for m in envelope["presented_materials"] if m["material_id"] == "M04")
        event = next(e for e in envelope["dialogue"]["events"] if e["event_id"] == item["event_id"])
        if changed == "unknown_material":
            item["material_id"] = "MISSING-DOCUMENT"
        elif changed == "foreign_event":
            item["event_id"] = str(uuid4())
        elif changed == "wrong_event":
            item["event_id"] = next(e["event_id"] for e in envelope["dialogue"]["events"]
                                    if e["event_type"] == "scenario_started")
        elif changed == "wrong_sequence":
            item["sequence_no"] += 1
        elif changed == "wrong_scenario_rule":
            event["payload"]["scenario_event_id"] = "E04_BOUNDARY"
        elif changed == "wrong_content":
            event["payload"]["content"]["text"] = "Иное содержание"
        elif changed == "wrong_recipient":
            event["payload"]["recipient_ids"] = ["assessee", "C1"]
        elif changed == "wrong_reply_recipient":
            reply = next(entry for entry in envelope["dialogue"]["events"]
                         if entry["event_type"] == "character_response" and entry["payload"]["speaker_id"] == "C1")
            turn_id = reply["cause"]["character_turn_id"]
            assert envelope["runtime_state"]["battery_audiences"][turn_id] == ["assessee"]
            assert reply["payload"]["recipient_ids"] == ["assessee"]
            reply["payload"]["recipient_ids"] = ["assessee", "C2"]
        else:
            envelope["presented_materials"].remove(item)
        # Изолируем проверку источника от более ранней проверки контрольной суммы.
        copy["envelope_checksum"] = checksum(envelope)
        with pytest.raises(ValueError, match=rf"SOURCE_UNRESOLVED:.*{field}$"):
            normalize(copy, row, cycle, session, criteria)

    historical = deepcopy(handoff)
    envelope = historical["envelope_json"]
    for event in envelope["dialogue"]["events"]:
        if event["event_type"] == "character_response":
            envelope["presented_materials"].append({
                **{key: event[key] for key in ("event_id", "material_id", "sequence_no", "event_type")},
                "available_at": event["created_at"],
            })
    envelope["presented_materials"].sort(key=lambda item: item["sequence_no"])
    with pytest.raises(ValueError, match="CHECKSUM_MISMATCH"):
        normalize(historical, row, cycle, session, criteria)
    historical["envelope_checksum"] = checksum(envelope)
    projected = normalize(historical, row, cycle, session, criteria)
    for key in ("turns", "events", "materials", "as_snapshot_ref", "execution_payload_ref"):
        assert projected[key] == normalized[key]
    assert projected["handoff_ref"]["checksum"] == historical["envelope_checksum"]
    assert checksum(envelope) == historical["envelope_checksum"]
    assert checksum(handoff["envelope_json"]) == handoff["envelope_checksum"]
    return list(changes)


def capture(record):
    if directory := os.getenv("P4K_SOURCE_PROBE_OUTPUT"):
        path = Path(directory)
        path.mkdir(exist_ok=True, parents=True)
        (path / (record["branch"] + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n")


@pytest.mark.parametrize("branch", [
    "03_without_reply", "03_one_reply", "03_boundary_three_replies",
    "03_update_and_replies", "03_update_then_final", "02_facilitator",
])
def test_dialogue_can_be_closed_after_two_saved_messages(opened_specialist_pilot, release_db, monkeypatch, branch):
    pilot = opened_specialist_pilot
    http = pilot.client
    situation_id = pilot.first["assessment_situation_id"]
    is_spec03 = branch.startswith("03_")
    if is_spec03:
        with monkeypatch.context() as patch:
            _submit_to_interim(http, situation_id, patch)
        advance_interim(release_db, situation_id)
        situation_id = present_next(pilot, situation_id)

    automatic = branch == "03_update_then_final"
    group = automatic or branch == "03_update_and_replies"
    boundary = branch == "03_boundary_three_replies"
    recipients = ["C1", "C2", "C3"] if group or boundary else ["C1"]
    first = "C1, какая версия у вашей части?"
    fragments = None
    rules = {}
    replies = {"C1":"Сверяю версию первой части.", "C2":"Ожидаю обе части.", "C3":"Уточняю свой вклад."}
    if branch == "03_one_reply":
        rules["E03_REPLY"] = matched(speaker_ids=recipients)
    if group or boundary:
        fragments = [
            {"text": "C1, подтвердите версию критериев.", "recipient_ids": ["C1"]},
            {"text": "C2, какие ограничения войдут в свод?", "recipient_ids": ["C2"]},
            {"text": "C3, какой срок вы можете подтвердить?", "recipient_ids": ["C3"]},
        ]
        first = " ".join(fragment["text"] for fragment in fragments)
        rules = {"E04_BOUNDARY": matched(speaker_ids=recipients)}
    if group:
        rules["E01_UPDATE"] = matched(speaker_ids=recipients)
    if not is_spec03:
        first = "Где указан предел проверки варианта B?"
        rules = {"E01_FACT":matched(speaker_ids=["FACILITATOR"])}
        recipients, replies = [], {"FACILITATOR":"Предел описан в M05."}
    with release_db() as db:
        snapshot_before = db.execute("""SELECT snapshot_json, snapshot_checksum, execution_payload_json
            FROM m5_assessment_situations WHERE assessment_situation_id=%s""", (situation_id,)).fetchone()
    first_response, _, _ = send_turn(http, monkeypatch, situation_id, first, rules, recipients, replies,
                                    fragments=fragments)
    assert first_response.status_code == 200, first_response.text
    situation_path = f"/users/assessment/m5/situations/{situation_id}"
    record = {"branch":branch}
    original = m10_orchestration.resolve

    def observing_resolver(db, handoff_id):
        record.update(observe_boundary(db, handoff_id))
        try:
            return original(db, handoff_id)
        except ValueError as exc:
            frame = traceback.extract_tb(exc.__traceback__)[-1]
            record["source_decision"] = {"file":Path(frame.filename).name, "function":frame.name,
                                          "line":frame.lineno,"code":str(exc)}
            raise

    if automatic:
        with monkeypatch.context() as patch:
            patch.setattr(m10_orchestration, "resolve", observing_resolver)
            response, post, _ = send_turn(http, monkeypatch, situation_id, "Сдаю итог и завершаю сценарий.",
                                          {}, recipients, {}, control="FINAL")
        path = situation_path + "/turns"
    else:
        second_rules = {"E03_REPLY": matched(speaker_ids=["C1"])} if group else {}
        second_recipients = ["C1"] if group else recipients
        second_response, _, calls = send_turn(
            http, monkeypatch, situation_id, "Сверю подтверждённые условия перед итогом.",
            second_rules, second_recipients, replies if group else {},
        )
        assert second_response.status_code == 200, second_response.text
        if group:
            assert [call["character"]["character_id"] for call in calls] == ["C1"]
            m04 = snapshot_before["execution_payload_json"]["runtime_rules"]["battery_scenario"]["concrete_materials"]["M04"]
            assert m04 not in calls[0]["character"]["known_facts"]
            assert json.dumps(m04["Текст"], ensure_ascii=False)[1:-1] not in json.dumps(calls, ensure_ascii=False)
        path = situation_path + "/transitions"
        post = {"action":"scenario_end", "reason":"user_finished_case", "request_id":str(uuid4())}
        with monkeypatch.context() as patch:
            patch.setattr(m10_orchestration, "resolve", observing_resolver)
            response = http.post(path, json=post)
    record["http_status"] = response.status_code
    if response.status_code != 200:
        record["detail"] = response.json().get("detail")
    with release_db() as db:
        as_row = db.execute("""SELECT id,status,snapshot_json#>>'{case_ref,id}' AS case_id
                               FROM m5_assessment_situations WHERE assessment_situation_id=%s""", (situation_id,)).fetchone()
        trace = runtime.trace(db,situation_id)
        record.update(case=as_row["case_id"], as_status=as_row["status"],
                      participant_turns=sum(t["speaker_type"]=="assessee" for t in trace["turns"]),
                      reply_events=[e["payload_json"].get("speaker_id") for e in trace["events"] if e["event_type"]=="character_response"],
                      m04_deliveries=sum(e["event_type"]=="mandatory_update" and e["material_id"]=="M04" for e in trace["events"]))
        record["interim_requests"] = db.execute(
            "SELECT count(*) AS n FROM m6_processing_requests WHERE as_db_id=%s AND mode='interim'",
            (as_row["id"],)).fetchone()["n"]
        record["interim_handoffs"] = db.execute(
            "SELECT count(*) AS n FROM m5_c45_handoffs WHERE assessment_situation_db_id=%s AND mode='interim'",
            (as_row["id"],)).fetchone()["n"]
    if boundary:
        events = [e for e in trace["events"] if e["event_type"] == "character_response"]
        assert len(events) == 3
        assert {e["payload_json"]["scenario_event_id"] for e in events} == {"E04_BOUNDARY"}
        record["dialogue_rule"] = "E04_BOUNDARY"
    capture(record)
    assert record["case"] == ("CASE.SPEC.03" if is_spec03 else "CASE.SPEC.02")
    assert record["participant_turns"] == 2
    expected_roles = list(recipients) if rules else []
    if group and not automatic:
        expected_roles.append("C1")
    if not is_spec03:
        expected_roles = ["FACILITATOR"]
    assert sorted(record["reply_events"]) == sorted(expected_roles)
    assert record["m04_deliveries"] == int(group)
    assert response.status_code == 200, record
    assert record["as_status"] == "scenario_ended"
    assert record["interim_requests"] == record["interim_handoffs"] == 1
    repeated = http.post(path, json=post)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["idempotent"] is True
    with release_db() as db:
        rows = db.execute("SELECT input_json FROM m6_processing_requests WHERE as_db_id=%s AND mode='interim'",
                          (as_row["id"],)).fetchall()
        assert len(rows) == 1
        value = rows[0]["input_json"]
        snapshot_after = db.execute("""SELECT snapshot_json, snapshot_checksum, execution_payload_json
            FROM m5_assessment_situations WHERE id=%s""", (as_row["id"],)).fetchone()
        assert snapshot_after == snapshot_before
        assert checksum(snapshot_after["snapshot_json"]) == snapshot_after["snapshot_checksum"]
        assert checksum(snapshot_after["execution_payload_json"]) == value["execution_payload_ref"]["checksum"]
        body = {key: item for key, item in value.items() if key != "material_revision"}
        assert definition_checksum(body) == value["material_revision"]["material_sha256"]
        ids = {m["material_id"] for m in value["materials"]}
        record["m6_materials"] = sorted(ids)
        assert not {key for key in ids if key.startswith("CHARACTER.")}
        if is_spec03:
            assert ("M04" in ids) == group
        if group:
            issued = next(m for m in value["materials"] if m["material_id"] == "M04")
            delivery = next(e for e in value["events"] if e["event_id"] == issued["event_id"])
            assert issued["available_sequence"] == delivery["sequence_no"]
            assert delivery["payload"]["recipient_ids"] == ["assessee"]
            assert delivery["payload"]["scenario_event_id"] == "E01_UPDATE"
            assert delivery["payload"]["speaker_id"] == "C2" and delivery["payload"]["author_id"] == "CUSTOMER"
            content = issued["content"]
            assert (content.get("Текст") or content.get("text")) == delivery["payload"]["content"]["text"]
            record["rejected_document_changes"] = check_document_references(db, as_row["id"], value["criteria"])
        dialogue = {turn["turn_id"]: turn for turn in value["turns"]}
        reply_events = [event for event in value["events"] if event["event_type"]=="character_response"]
        stored_replies = {str(event["event_id"]): event for event in trace["events"]
                          if event["event_type"] == "character_response"}
        assert {event["event_id"] for event in reply_events} == stored_replies.keys()
        for event in reply_events:
            reply = dialogue[event["cause"]["character_turn_id"]]
            assert reply["speaker_type"]=="character"
            assert reply["speaker_id"]==event["payload"]["speaker_id"]
            assert reply["content"]==event["payload"]["response"]
            trigger = dialogue[event["cause"]["trigger_turn_id"]]
            assert trigger["speaker_type"] == "assessee"
            assert trigger["sequence_no"] < reply["sequence_no"] < event["sequence_no"]
            stored = stored_replies[event["event_id"]]
            assert event["payload"]["recipient_ids"] == stored["payload_json"]["recipient_ids"]
            if boundary:
                assert event["payload"]["recipient_ids"] == ["assessee"]
    record["m7_decision"] = advance_interim(release_db, situation_id)
    if boundary:
        url = f"/users/assessment/cycles/{pilot.cycle_id}/runtime"
        saved_runtime = http.get(url).json()
        assert http.post("/users/session/logout").status_code == 200
        http.cookies.set(routes.SESSION_COOKIE_NAME, web_session_service.web_session_service.create_session(pilot.participant_id))
        restored = http.get(url).json()
        assert restored["cycle_id"] == pilot.cycle_id
        assert restored["current_situation"]["assessment_situation_id"] == situation_id
        assert restored["trace"]["turns"] == saved_runtime["trace"]["turns"]
        assert http.post(path, json=post).json()["interim_processing_request_id"] == response.json()["interim_processing_request_id"]
        with release_db() as db:
            assert db.execute("""SELECT count(*) AS n FROM m5_c45_handoffs
                WHERE assessment_situation_db_id=%s AND mode='interim'""", (as_row["id"],)).fetchone()["n"] == 1
            assert db.execute("""SELECT count(*) AS n FROM m6_processing_requests
                WHERE as_db_id=%s AND mode='interim'""", (as_row["id"],)).fetchone()["n"] == 1
        record["same_dialogue_after_relogin"] = True
    next_id = present_next(pilot, situation_id)
    with release_db() as db:
        next_as = db.execute("""SELECT snapshot_json#>>'{case_ref,id}' AS code FROM m5_assessment_situations
            WHERE assessment_situation_id=%s AND cycle_db_id=%s""", (next_id, pilot.cycle_db_id)).fetchone()
    assert next_as["code"] == ("CASE.SPEC.04" if is_spec03 else "CASE.SPEC.03")
    record["next_case"] = next_as["code"]
    capture(record)
