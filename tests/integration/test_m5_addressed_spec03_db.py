from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import m5_scenario_runtime as runtime, participant_profile, routes
from Api.m10_input_resolver import resolve
from Api.m10_product_flow import start_prepared
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import publish_catalog
from Api.m5_passport_generation import ADDRESSED_RUNTIME, BANK_PACKAGE
from Api.m5_rule_engine import CharacterReply, ControlledSemanticAdapter, Decision
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
from Api.m5_storage import import_package
from Api.m7_completion import complete, control
from Api.product_cycle_preparation_queue import ProductCyclePreparationQueue
from Api.schemas import PersonalizedProfileSelection
from scripts.plan_specialist_program_release import build_release_artifacts
from tests.integration.test_m10_product_path_db import _resolve_interim_for_finish, product_db
from tests.passport_as_fixture import synthetic_as
from tests.spec03_fixture import DETAIL, FACT, PROPOSAL
from tests.unit.test_m5_passport_bank import CaptureGateway

pytestmark = pytest.mark.integration


def _record(name, value):
    directory = os.getenv("M5_02_EVIDENCE")
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)
        Path(directory, name + ".json").write_text(json.dumps(value, ensure_ascii=False, default=str, indent=2) + "\n")


@pytest.fixture
def product_path(product_db, monkeypatch):
    def setup(case_ids, variant=0):
        package = json.loads((BANK_PACKAGE / "case-package.json").read_bytes())
        bindings = load_runtime_rule_package(ADDRESSED_RUNTIME, package["cases"], expected_case_package_version="0.6")
        for case in package["cases"]:
            case["status"] = "FROZEN"
        manifest, rules = build_release_artifacts(package, bindings, usage_scope="assessment", package_dir=BANK_PACKAGE)
        with product_db() as connection:
            imported = import_package(connection, package=package, manifest=manifest, execution_rules=rules)
            installed = import_runtime_rule_version(connection, bindings, rules, package_db_id=imported["package_db_id"])
            cases = connection.execute("""
                SELECT * FROM m5_case_versions WHERE package_id=%s AND case_id=ANY(%s) ORDER BY case_id
            """, (imported["package_db_id"], case_ids)).fetchall()
            assert [row["case_id"] for row in cases] == case_ids
            # Synthetic authority for this isolated catalog. The normal
            # CaseVersion, publication, preparation and M7 gates still run.
            for case in cases:
                for scope in ("case_format", "case_dialogue", "assessment_situation"):
                    evidence = {"schema_version": 1, "eligibility": "user_admission", "scope": scope,
                                "result": "PASS", "case_ref": {"id": case["case_id"], "version": case["case_version"],
                                "checksum": case["content_checksum"]}, "base_role": case["base_role"],
                                "usage_scopes": ["assessment"],
                                "origin": {"type": "human_review", "actor_ref": "review:synthetic-m5-02"}}
                    connection.execute("""
                        INSERT INTO m5_qa_evidence (case_version_id,scope,result,evidence_json,evidence_checksum)
                        VALUES (%s,%s,'PASS',%s::jsonb,%s)
                    """, (case["id"], scope, json.dumps(evidence), checksum(evidence)))
            catalog = publish_catalog(
                connection, catalog_id="m5-02", catalog_version="1", package_db_id=imported["package_db_id"],
                case_version_ids=[case["id"] for case in cases], runtime_rule_version_id=installed["id"],
                usage_scope="assessment", organization_id=10, published_by=99,
                decision_basis="isolated SPEC.03 fixture", idempotency_key="m5-02-catalog",
            )
            connection.execute("ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT REFERENCES m5_catalogs(id)")
            connection.execute("ALTER TABLE assessment_configurations ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT TRUE")
            connection.execute("UPDATE assessment_configurations SET catalog_version_id=%s", (catalog["catalog_db_id"],))
            role = connection.execute("""
                SELECT v.id FROM assessment_role_profile_versions v JOIN assessment_role_profiles r ON r.id=v.role_profile_id
                WHERE r.code='specialist_expert' AND v.status='published'
            """).fetchone()["id"]
            org = connection.execute("""
                SELECT v.id FROM assessment_organization_context_versions v
                JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
                WHERE c.organization_id=10 AND v.status='published'
            """).fetchone()["id"]
            profile = participant_profile.confirm(
                connection, user_id=99, selection=PersonalizedProfileSelection(
                    organization_context_version_id=org, role_profile_version_id=role, assessment_configuration_id=1,
                ), full_name="Synthetic specialist", position="", duties="",
            )
            connection.execute("""CREATE TABLE product_cycle_preparation_operations (
                id BIGSERIAL PRIMARY KEY,operation_id TEXT UNIQUE,user_id BIGINT,request_json JSONB,request_checksum TEXT,
                status TEXT DEFAULT 'queued',attempts INTEGER DEFAULT 0,result_json JSONB,error_code TEXT,error_message TEXT,
                worker_id TEXT,attempt_token UUID,locked_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),completed_at TIMESTAMP)""")

        class Gateway(CaptureGateway):
            enabled = True

            def chat_with_trace(self, messages, **kwargs):
                result = super().chat_with_trace(messages, **kwargs)
                if ":generation:" in kwargs["routing_key"]:
                    result.content = json.dumps(synthetic_as(self.calls[-1][2], variant=variant), ensure_ascii=False)
                return result

        gateway = Gateway("pass")
        queue = ProductCyclePreparationQueue()
        monkeypatch.setattr("Api.llm.deepseek_gateway.DeepSeekGateway", lambda **_: gateway)
        monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", product_db)
        monkeypatch.setattr(routes, "get_connection", product_db)
        monkeypatch.setattr(routes, "product_cycle_preparation_queue", queue)
        monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                            lambda token: SimpleNamespace(id=99) if token == "m5-02-owner" else None)
        queue.enqueue(operation_id="m5-02-first", user_id=99, request={
            "idempotency_key": "m5-02-first", "selected_skills": ["K1", "K2", "K4"],
            "personalized_profile_id": profile["id"],
        })
        queue._process(queue._claim())
        operation = queue.get_status("m5-02-first")
        assert operation["status"] == "completed", operation
        prepared = operation["result_json"]
        cycle_id = str(prepared["plan"]["cycle_id"])
        as_id = str(prepared["decision"]["assessment_situation_id"])
        with product_db() as connection:
            start_prepared(connection, user_id=99, cycle_id=cycle_id, key="m5-02-start")
        app = FastAPI()
        app.include_router(routes.router)
        return app, queue, cycle_id, as_id, prepared["decision"]["selected_case_id"]
    return setup


class Semantics(ControlledSemanticAdapter):
    def __init__(self):
        super().__init__({})
        self.call_log = []
        self.details = {}
        self.on_update = None

    def decide(self, *, rule, text, turn_id, context):
        key = rule["rule_id"]
        self.call_log.append((key, text, context))
        if key == "E01_UPDATE" and self.on_update:
            self.on_update()
        parsed = super().decide(rule=rule, text=text, turn_id=turn_id, context=context)
        return Decision(parsed.outcome, parsed.code, parsed.basis, parsed.turn_ids, adapter="controlled",
                        controlled_test=True, details=self.details.get(key))


class Characters:
    def __init__(self):
        self.inputs = defaultdict(list)

    def respond(self, *, material, character, text, turn_id, context):
        self.inputs[character["character_id"]].append({"facts": character["known_facts"], "context": context})
        return CharacterReply("COMPLETED", "Заказчик ждёт статус к 16:00.", "controlled", controlled_test=True)


def _owner(http):
    http.cookies.set(routes.SESSION_COOKIE_NAME, "m5-02-owner")


def _rules(semantics, *, update="NO_MATCH", transfer="NO_MATCH", reply=None, intent="CONTINUE"):
    semantics.outcomes = {"SCENARIO_CONTROL": intent, "E01_UPDATE": update, "E02_TRANSFER": transfer,
                          "E03_REPLY": "MATCH" if reply else "NO_MATCH"}
    semantics.details = {"E03_REPLY": {"speaker_ids": reply}}


def _public_path(cycle_id):
    return f"/users/assessment/cycles/{cycle_id}/runtime"


def _turn_path(as_id):
    return f"/users/assessment/m5/situations/{as_id}/turns"


def _command(request_id, content):
    return {"request_id": request_id, "turn_id": str(uuid4()), "content": content}


def _post(http, as_id, command):
    response = http.post(_turn_path(as_id), json=command)
    assert response.status_code == 200, response.text
    return response.json()


def _effect(receipt, event_id):
    return [event for event in receipt["events"] if event["payload_json"].get("scenario_event_id") == event_id]


def test_spec03_update_transfer_and_saved_public_readback(product_db, product_path, monkeypatch):
    app, _, cycle_id, as_id, case_id = product_path(["CASE.SPEC.03"])
    assert case_id == "CASE.SPEC.03"
    semantics, characters = Semantics(), Characters()
    monkeypatch.setattr(runtime, "DeepSeekSemanticAdapter", lambda **_: semantics)
    monkeypatch.setattr(runtime, "DeepSeekCharacterAdapter", lambda **_: characters)
    with TestClient(app) as http:
        _owner(http)
        before = http.get(_public_path(cycle_id)).json()
        assert before["current_situation"]["response_format"] == "dialogue"
        assert [x["material_id"] for x in before["current_situation"]["participant_payload"]["initial_materials"]] == [
            "M01", "M02", "M03"
        ]
        assert "M04" not in json.dumps(before, ensure_ascii=False)
        assert FACT not in json.dumps(before, ensure_ascii=False)
        assert [turn["speaker_id"] for turn in before["trace"]["turns"]] == ["COLLEAGUE_2"]

        _rules(semantics, reply=["COLLEAGUE_2"])
        ordinary = _post(http, as_id, _command("ordinary", "Когда срок?"))
        assert len(_effect(ordinary, "E03_REPLY")) == 1 and not _effect(ordinary, "E01_UPDATE")
        _rules(semantics, update="UNKNOWN")
        uncertain = _post(http, as_id, _command("unknown", "Как будем поступать?"))
        assert not uncertain["events"]

        _rules(semantics, update="MATCH")
        proposal = _command("proposal", PROPOSAL)
        receipt = _post(http, as_id, proposal)
        assert [x["event_type"] for x in receipt["events"]] == ["character_response", "mandatory_update"]
        update = _effect(receipt, "E01_UPDATE")[0]
        assert update["material_id"] == "M04"
        assert update["payload_json"]["recipient_ids"] == ["assessee"]
        assert update["payload_json"]["speaker_id"] == "COLLEAGUE_1"
        assert update["payload_json"]["speaker_name"] == "Ирина / Инженер измерений"
        assert update["payload_json"]["content"]["text"] == f"{FACT}. {DETAIL}"
        history = next(line[2]["state"]["dialogue_history"] for line in semantics.call_log
                       if line[:2] == ("E01_UPDATE", PROPOSAL))
        assert "Когда срок?" in [entry["content_text"] for entry in history]
        calls = len(semantics.call_log)
        duplicate = _post(http, as_id, proposal)
        assert duplicate["idempotent"] and duplicate["events"] == receipt["events"]
        assert len(semantics.call_log) == calls
        with product_db() as connection:
            control(connection, cycle_id=cycle_id, key="pause-after-update", action="pause",
                    reason="operator_pause", initiated_by=99)
        with product_db() as connection:
            control(connection, cycle_id=cycle_id, key="resume-after-update", action="resume",
                    reason="operator_resume", initiated_by=99)
        assert _post(http, as_id, proposal)["events"] == receipt["events"]
        assert not _effect(_post(http, as_id, _command("proposal-after-resume", PROPOSAL)), "E01_UPDATE")
        assert len([call for call in semantics.call_log if call[0] == "E01_UPDATE"]) == 3

        _rules(semantics)
        assert not _post(http, as_id, _command("promise", "Позже перешлю"))["events"]
        _rules(semantics, transfer="DIRECT", reply=["COLLEAGUE_2"])
        semantics.details["E02_TRANSFER"] = {"text": FACT, "recipient_ids": ["COLLEAGUE_2"]}
        direct = _post(http, as_id, _command("actual-share", f"Артур, {FACT}."))
        assert _effect(direct, "E02_TRANSFER")[0]["payload_json"]["message_turn_id"] == direct["turn"]["turn_id"]
        assert FACT in characters.inputs["COLLEAGUE_2"][-1]["facts"]
        assert DETAIL not in json.dumps(characters.inputs["COLLEAGUE_2"], ensure_ascii=False)

        _rules(semantics, reply=["COLLEAGUE_3"])
        _post(http, as_id, _command("ask-nonrecipient", "Рита, когда вам удобно сверить журнал?"))
        assert FACT not in json.dumps(characters.inputs["COLLEAGUE_3"], ensure_ascii=False)
        _rules(semantics, transfer="DELEGATE")
        semantics.details["E02_TRANSFER"] = {"text": DETAIL, "recipient_ids": ["COLLEAGUE_3"]}
        delegated = _post(http, as_id, _command("send-in-chat", "Ирина, передайте Рите здесь время закрытия окна."))
        forwarded = _effect(delegated, "E02_TRANSFER")[0]["payload_json"]
        assert forwarded["recipient_ids"] == ["COLLEAGUE_3"]
        assert forwarded["sender_id"] == "COLLEAGUE_1" and forwarded["text"] == DETAIL
        assert forwarded["message_turn_id"] != delegated["turn"]["turn_id"]

        _rules(semantics, transfer="DIRECT")
        semantics.details["E02_TRANSFER"] = {"text": FACT, "recipient_ids": ["NOT_IN_THIS_AS"]}
        assert not _post(http, as_id, _command("wrong-recipient", FACT))["events"]
        _rules(semantics, reply=["COLLEAGUE_2", "COLLEAGUE_3"])
        _post(http, as_id, _command("after-share", "Уточните свои ограничения."))
        assert FACT in characters.inputs["COLLEAGUE_2"][-1]["facts"]
        assert DETAIL in characters.inputs["COLLEAGUE_3"][-1]["facts"]
        assert FACT not in json.dumps(characters.inputs["COLLEAGUE_3"][-1], ensure_ascii=False)
        assert DETAIL not in json.dumps(characters.inputs["COLLEAGUE_2"][-1], ensure_ascii=False)

    with TestClient(app) as restarted_read:
        _owner(restarted_read)
        after = restarted_read.get(_public_path(cycle_id)).json()
        assert restarted_read.get(_public_path(cycle_id)).json()["trace"] == after["trace"]
        assert [x["event_id"] for x in after["trace"]["events"] if x["material_id"] == "M04"] == [update["event_id"]]
        assert [turn["content_text"] for turn in after["trace"]["turns"]
                if turn["turn_id"] == forwarded["message_turn_id"]] == [DETAIL]
    with product_db() as connection:
        internal = runtime.trace(connection, as_id)
        assert internal["state"]["state_json"]["disclosed_materials"] == ["P00", "M01", "M02", "M03", "M04"]
        runtime.transition(connection, assessment_situation_id=as_id, action="scenario_end", reason="completed", request_id="end")
        handoff = runtime.build_c45(connection, as_id, mode="interim")
        _, material = resolve(connection, str(handoff["handoff_id"]))
        assert material["conditional_opportunities"][0]["occurred_event_refs"] == ["E01_UPDATE", "E02_TRANSFER"]
        assert [e["material_id"] for e in material["materials"] if e["material_id"].startswith(("M", "P"))] == [
            "P00", "M01", "M02", "M03", "M04",
        ]
    _record("ac2-ac3-readback", {"public_start": before, "public_reopened": after, "internal": internal,
                                "c45": handoff["envelope_json"], "recipient_contexts": characters.inputs})


@pytest.mark.parametrize("intent", ["FINAL", "STOP"])
def test_final_turn_has_priority_over_update(product_db, product_path, monkeypatch, intent):
    app, _, cycle_id, as_id, _ = product_path(["CASE.SPEC.03"], variant=1)
    semantics = Semantics()
    _rules(semantics, update="MATCH", intent=intent)
    monkeypatch.setattr(runtime, "DeepSeekSemanticAdapter", lambda **_: semantics)
    monkeypatch.setattr(runtime, "DeepSeekCharacterAdapter", lambda **_: Characters())
    with TestClient(app) as http:
        _owner(http)
        before = http.get(_public_path(cycle_id)).json()
        assert "тираж" in before["current_situation"]["participant_payload"]["introduction"]
        assert "480 листов" not in json.dumps(before, ensure_ascii=False)
        command = _command("last", PROPOSAL + (" Это мой окончательный ответ." if intent == "FINAL"
                                                else " Я прекращаю эту сцену."))
        done = _post(http, as_id, command)
        assert [item["event_type"] for item in done["events"]] == ["scenario_completed"]
        assert _post(http, as_id, command)["idempotent"]
        assert all(rule != "E01_UPDATE" for rule, _, _ in semantics.call_log)
        after = http.get(_public_path(cycle_id)).json()
        assert after["current_situation"]["status"] == "scenario_ended"
        assert "480 листов" not in json.dumps(after, ensure_ascii=False)
    with product_db() as connection:
        handoff = runtime.build_c45(connection, as_id, mode="interim")
        _, material = resolve(connection, str(handoff["handoff_id"]))
        assert material["conditional_opportunities"] == [{
            "indicator_id": "K2.I08", "material_refs": ["M04"], "event_refs": ["E01_UPDATE", "E02_TRANSFER"],
            "status": "NOT_ARISEN", "occurred_event_refs": [],
        }]
        assert connection.execute("SELECT count(*) AS n FROM m6_processing_requests").fetchone()["n"] == 1
    _record("ac3-" + intent.lower(), {"public_start": before, "public_end": after,
                                      "conditional_opportunities": material["conditional_opportunities"]})


@pytest.mark.parametrize("boundary", ["pause", "scenario_end", "terminate", "close", "m7_stop"])
def test_committed_transition_fences_simultaneous_match(product_db, product_path, boundary):
    _, _, cycle_id, as_id, _ = product_path(["CASE.SPEC.03"])
    semantics, characters = Semantics(), Characters()
    _rules(semantics, update="MATCH")

    def change_state():
        with product_db() as connection:
            if boundary == "m7_stop":
                complete(connection, cycle_id=cycle_id, key="close", action="final_refusal",
                         reason="participant_refusal", initiated_by=99)
            elif boundary == "pause":
                control(connection, cycle_id=cycle_id, key="pause", action="pause",
                        reason="operator_pause", initiated_by=99)
            else:
                action = "scenario_end" if boundary == "close" else boundary
                runtime.transition(connection, assessment_situation_id=as_id, action=action,
                                   reason="during_provider", request_id=action)
                if boundary == "close":
                    runtime.transition(connection, assessment_situation_id=as_id, action="close",
                                       reason="during_provider", request_id="closed")

    semantics.on_update = change_state
    command = _command("racing", PROPOSAL)
    kwargs = {"assessment_situation_id": as_id, "semantic_adapter": semantics,
              "character_adapter": characters, "connection_factory": product_db}
    with pytest.raises(ValueError, match="M5_AS_NOT_ACTIVE|M7_COLLECTION_CLOSED"):
        runtime.submit_turn_detached(**kwargs, **command)
    with product_db() as connection:
        saved = runtime.trace(connection, as_id)
        assert not any(e["material_id"] == "M04" for e in saved["events"])
        assert saved["state"]["state_json"]["disclosed_materials"] == ["P00", "M01", "M02", "M03"]
        if boundary == "pause":
            control(connection, cycle_id=cycle_id, key="resume", action="resume",
                    reason="operator_resume", initiated_by=99)
    if boundary == "pause":
        semantics.on_update = None
        with pytest.raises(ValueError, match="M5_AS_NOT_ACTIVE|M7_COLLECTION_CLOSED"):
            runtime.submit_turn_detached(**kwargs, **command)
        new = runtime.submit_turn_detached(**kwargs, **_command("after-resume", PROPOSAL))
        assert len(_effect(new, "E01_UPDATE")) == 1
    _record("ac3-race-" + boundary, {"saved_status": saved["status"], "events": saved["events"]})


def test_written_spec02_prepares_submits_and_next_presents_spec03_in_same_cycle(product_db, product_path, monkeypatch):
    app, queue, cycle_id, written_id, case_id = product_path(["CASE.SPEC.02", "CASE.SPEC.03"])
    assert case_id == "CASE.SPEC.02"
    semantics, characters = Semantics(), Characters()
    monkeypatch.setattr(runtime, "DeepSeekSemanticAdapter", lambda **_: semantics)
    monkeypatch.setattr(runtime, "DeepSeekCharacterAdapter", lambda **_: characters)
    with TestClient(app) as http:
        _owner(http)
        written = http.get(_public_path(cycle_id)).json()
        assert written["current_situation"]["response_format"] == "written"
        _post(http, written_id, _command("written-final", "Проверил вводные. Мой письменный ответ сохранён."))
        assert not characters.inputs
        transition = http.post(f"/users/assessment/m5/situations/{written_id}/transitions", json={
            "action": "scenario_end", "reason": "user_finished_case", "request_id": "written-end",
        })
        assert transition.status_code == 200, transition.text
        with product_db() as connection:
            _resolve_interim_for_finish(connection, product_db, written_id)
        cycle_path = f"/users/assessment/m7/cycles/{cycle_id}"
        finish = http.post(cycle_path + "/finish-situation", json={"idempotency_key": "finish-written"})
        assert finish.status_code == 200, finish.text
        queue._process(queue._claim())
        queued = queue.get_status("next:" + written_id)
        assert queued["status"] == "completed", queued
        selected = queued["result_json"]["decision"]
        assert selected["selected_case_id"] == "CASE.SPEC.03"
        assert queued["result_json"]["plan"]["cycle_id"] == cycle_id
        public = http.get(_public_path(cycle_id)).json()
        target = public["next_presentation"]
        present = http.post(cycle_path + "/present-next", json=target)
        assert present.status_code == 201, present.text
        resulting = present.json()["runtime"]
        assert resulting["cycle_id"] == cycle_id
        assert resulting["current_situation"]["assessment_situation_id"] == selected["assessment_situation_id"]
        assert resulting["current_situation"]["response_format"] == "dialogue"
    _record("ac4-spec02-to-spec03", {"written_start": written, "written_receipt": transition.json(), "next": resulting})
