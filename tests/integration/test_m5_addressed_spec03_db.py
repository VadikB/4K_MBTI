from __future__ import annotations

import json
import os
from collections import defaultdict, deque
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
from Api.m5_rule_engine import CharacterReply, ControlledSemanticAdapter, Decision, DeepSeekSemanticAdapter
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
        self.inputs[character["character_id"]].append({"text": text, "facts": character["known_facts"], "context": context})
        return CharacterReply("COMPLETED", "Заказчик ждёт статус к 16:00.", "controlled", controlled_test=True)


def _owner(http):
    http.cookies.set(routes.SESSION_COOKIE_NAME, "m5-02-owner")


def _rules(semantics, *, update="NO_MATCH", transfer="NO_MATCH", reply=None, intent="CONTINUE"):
    semantics.outcomes = {"SCENARIO_CONTROL": intent, "E01_UPDATE": update, "E02_TRANSFER": transfer,
                          "E03_REPLY": "MATCH" if reply else "NO_MATCH"}
    semantics.details = {"E03_REPLY": {"speaker_ids": reply, "recipient_ids": reply}} if reply else {}


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
        direct_events = _effect(direct, "E02_TRANSFER")
        assert len(direct_events) == 1
        assert direct_events[0]["payload_json"]["message_turn_id"] == direct["turn"]["turn_id"]
        assert FACT in characters.inputs["COLLEAGUE_2"][-1]["facts"]
        assert DETAIL not in json.dumps(characters.inputs["COLLEAGUE_2"], ensure_ascii=False)

        _rules(semantics, reply=["COLLEAGUE_3"])
        _post(http, as_id, _command("ask-nonrecipient", "Рита, когда вам удобно сверить журнал?"))
        assert FACT not in json.dumps(characters.inputs["COLLEAGUE_3"], ensure_ascii=False)
        _rules(semantics, transfer="DELEGATE")
        semantics.details["E02_TRANSFER"] = {"text": DETAIL, "recipient_ids": ["COLLEAGUE_3"]}
        delegated = _post(http, as_id, _command("send-in-chat", "Ирина, передайте Рите здесь время закрытия окна."))
        delegate_events = _effect(delegated, "E02_TRANSFER")
        assert len(delegate_events) == 1
        forwarded = delegate_events[0]["payload_json"]
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
        transfers = [event for event in handoff["envelope_json"]["dialogue"]["events"]
                     if event["event_type"] == "information_transferred"]
        assert [(
            event["material_id"], event["cause"]["turn_id"], event["payload"]["sender_id"],
            event["payload"]["recipient_ids"], event["payload"]["text"],
        ) for event in transfers] == [
            ("M04", direct["turn"]["turn_id"], "assessee", ["COLLEAGUE_2"], FACT),
            ("M04", delegated["turn"]["turn_id"], "COLLEAGUE_1", ["COLLEAGUE_3"], DETAIL),
        ]
        _, material = resolve(connection, str(handoff["handoff_id"]))
        assert material["conditional_opportunities"][0]["occurred_event_refs"] == ["E01_UPDATE", "E02_TRANSFER"]
        assert [e["material_id"] for e in material["materials"] if e["material_id"].startswith(("M", "P"))] == [
            "P00", "M01", "M02", "M03", "M04",
        ]
    _record("ac2-ac3-readback", {"public_start": before, "public_reopened": after, "internal": internal,
                                "c45": handoff["envelope_json"], "recipient_contexts": characters.inputs})


class SemanticGateway:
    enabled = True

    def __init__(self):
        self.responses = deque()
        self.inputs = []

    def feed(self, *responses):
        assert not self.responses
        self.responses.extend(responses)

    def chat(self, messages, **kwargs):
        self.inputs.append(json.loads(messages[1]["content"]))
        response = self.responses.popleft()
        return json.dumps({"basis": "synthetic acceptance", **response}, ensure_ascii=False)


@pytest.fixture
def semantic_gateway(monkeypatch):
    gateway, characters = SemanticGateway(), Characters()
    monkeypatch.setattr(runtime, "DeepSeekSemanticAdapter",
                        lambda *, operation: DeepSeekSemanticAdapter(gateway=gateway, operation=operation))
    monkeypatch.setattr(runtime, "DeepSeekCharacterAdapter", lambda **_: characters)
    return gateway, characters


def _choice(code, **details):
    return {"code": code, **({"details": details} if details else {})}


def _deliver_update(http, as_id, gateway):
    gateway.feed(_choice("CONTINUE"), _choice("MATCH"))
    receipt = _post(http, as_id, _command("proposal", PROPOSAL))
    assert len(_effect(receipt, "E01_UPDATE")) == 1


@pytest.mark.parametrize("legacy", [False, True], ids=["saved_audience", "missing_legacy_audience"])
def test_private_question_does_not_reach_other_colleagues_on_later_turn(
    product_db, product_path, semantic_gateway, legacy,
):
    app, _, cycle_id, as_id, _ = product_path(["CASE.SPEC.03"])
    gateway, characters = semantic_gateway
    roster = ["COLLEAGUE_1", "COLLEAGUE_2", "COLLEAGUE_3"]
    shared_text = "Коллеги, когда ждут общий статус?"
    private_text = f"Ирина, уточню лично: {FACT}. Я правильно прочитал?"
    with TestClient(app) as http:
        _owner(http)
        _deliver_update(http, as_id, gateway)
        gateway.feed(_choice("CONTINUE"), _choice("UNKNOWN"))
        assert not _post(http, as_id, _command("uncertain", "Попробуем уточнить позже."))["events"]

        gateway.feed(_choice("CONTINUE"), _choice("NO_MATCH"),
                     _choice("MATCH", speaker_ids=["COLLEAGUE_2"], recipient_ids=roster))
        shared = _command("public-question", shared_text)
        _post(http, as_id, shared)
        gateway.feed(_choice("CONTINUE"), _choice("NO_MATCH"),
                     _choice("MATCH", speaker_ids=roster[:2], recipient_ids=roster[:1]))
        private = _command("private-question", private_text)
        receipt = _post(http, as_id, private)
        assert not _effect(receipt, "E02_TRANSFER")
        assert [event["payload_json"]["speaker_id"] for event in _effect(receipt, "E03_REPLY")] == roster[:1]
        assert characters.inputs["COLLEAGUE_1"][-1]["text"] == private_text
        assert f"{FACT}. {DETAIL}" in characters.inputs["COLLEAGUE_1"][-1]["facts"]
        assert len(characters.inputs["COLLEAGUE_2"]) == 1

    with product_db() as connection:
        saved = runtime.trace(connection, as_id)
        audiences = saved["state"]["state_json"]["turn_audiences"]
        assert audiences[private["turn_id"]] == roster[:1]
        assert audiences[shared["turn_id"]] == roster
        if legacy:
            # Simulate the pre-fix snapshot, with the original Turn still present.
            connection.execute(
                """UPDATE m5_scenario_states SET state_json=state_json #- %s::text[]
                   WHERE assessment_situation_db_id=%s""",
                (["turn_audiences", private["turn_id"]], saved["state"]["assessment_situation_db_id"]),
            )
        control(connection, cycle_id=cycle_id, key="privacy-pause", action="pause",
                reason="operator_pause", initiated_by=99)
    with product_db() as connection:
        control(connection, cycle_id=cycle_id, key="privacy-resume", action="resume",
                reason="operator_resume", initiated_by=99)

    with TestClient(app) as reopened:
        _owner(reopened)
        trace = reopened.get(_public_path(cycle_id)).json()["trace"]
        assert any(turn["turn_id"] == private["turn_id"] and turn["content_text"] == private_text
                   for turn in trace["turns"])
        gateway.feed(_choice("CONTINUE"), _choice("NO_MATCH"),
                     _choice("MATCH", speaker_ids=roster[1:], recipient_ids=roster[1:]))
        _post(reopened, as_id, _command("another-colleague", "Артур и Рита, когда вы свободны?"))
        for colleague in roster[1:]:
            inputs = characters.inputs[colleague][-1]
            history = inputs["context"]["dialogue_history"]
            assert any(item["turn_id"] == shared["turn_id"] and item["content_text"] == shared_text for item in history)
            assert all(item["turn_id"] != private["turn_id"] for item in history)
            assert FACT not in json.dumps(inputs, ensure_ascii=False)
        gateway.feed(_choice("CONTINUE"), _choice("NO_MATCH"),
                     _choice("MATCH", speaker_ids=roster[:1], recipient_ids=roster[:1]))
        _post(reopened, as_id, _command("sender-again", "Ирина, уточните границы своего вклада."))
        sender_history = characters.inputs["COLLEAGUE_1"][-1]["context"]["dialogue_history"]
        assert any(item["turn_id"] == private["turn_id"] for item in sender_history) is (not legacy)

    with product_db() as connection:
        runtime.transition(connection, assessment_situation_id=as_id, action="scenario_end",
                           reason="completed", request_id="privacy-end")
        envelope = runtime.build_c45(connection, as_id, mode="interim")["envelope_json"]
        assert any(turn["turn_id"] == private["turn_id"] and turn["content"] == private_text
                   for turn in envelope["dialogue"]["turns"])
        assert not any(event["event_type"] == "information_transferred" for event in envelope["dialogue"]["events"])
        assert envelope["runtime_state"]["turn_audiences"].get(private["turn_id"]) == (None if legacy else roster[:1])


@pytest.mark.parametrize("failure", ["E02_TRANSFER", "E03_REPLY"])
def test_failed_semantic_output_retries_original_http_turn_once(
    product_db, product_path, semantic_gateway, failure,
):
    app, _, cycle_id, as_id, _ = product_path(["CASE.SPEC.03"])
    gateway, characters = semantic_gateway
    command = _command("provider-retry", f"Артур, {FACT}.")
    valid_transfer = _choice("DIRECT", recipient_ids=["COLLEAGUE_2"], text=FACT)
    with TestClient(app) as http:
        _owner(http)
        _deliver_update(http, as_id, gateway)
        with product_db() as connection:
            before = runtime.trace(connection, as_id)
        if failure == "E02_TRANSFER":
            gateway.feed(_choice("CONTINUE"), _choice("DIRECT"))
        else:
            gateway.feed(_choice("CONTINUE"), valid_transfer, _choice("MATCH"))
        response = http.post(_turn_path(as_id), json=command)
        assert response.status_code == 502
        assert response.json()["detail"] == "SEMANTIC_OUTPUT_INVALID"
        readback_url = f"/users/assessment/m5/situations/{as_id}/answer-status"
        identity = {key: command[key] for key in ("request_id", "turn_id")}
        readback = http.get(readback_url, params=identity).json()
        assert readback["status"] == "accepted" and readback["processing_status"] == "failed"
        assert readback["turn"]["content_text"] == command["content"]
        assert http.get(_public_path(cycle_id)).json()["blocking_system_wait"] is False
        assert not characters.inputs

        with product_db() as connection:
            state = runtime.trace(connection, as_id)
            operation = connection.execute("""
                SELECT status, error_code, attempt_no, result_json
                FROM m5_turn_operations WHERE request_id=%s
            """, (command["request_id"],)).fetchone()
            assert operation == {"status": "failed", "error_code": "SEMANTIC_OUTPUT_INVALID",
                                 "attempt_no": 1, "result_json": None}
            assert len(state["turns"]) == len(before["turns"]) + 1
            assert str(state["turns"][-1]["turn_id"]) == command["turn_id"]
            assert state["events"] == before["events"]
            assert state["decisions"] == before["decisions"]
            assert state["state"]["revision"] == before["state"]["revision"]

        gateway.feed(_choice("CONTINUE"), valid_transfer, _choice("MATCH", speaker_ids=["COLLEAGUE_2"]))
        applied = _post(http, as_id, command)
        events = _effect(applied, "E02_TRANSFER")
        assert len(events) == 1 and len(_effect(applied, "E03_REPLY")) == 1
        transfer = events[0]
        assert transfer["cause_json"]["turn_id"] == command["turn_id"]
        assert transfer["payload_json"]["sender_id"] == "assessee"
        assert transfer["payload_json"]["recipient_ids"] == ["COLLEAGUE_2"]
        assert transfer["payload_json"]["text"] == FACT
        assert FACT in characters.inputs["COLLEAGUE_2"][-1]["facts"]

        requests = len(gateway.inputs)
        assert _post(http, as_id, command) == {**applied, "idempotent": True}
        assert len(gateway.inputs) == requests

    with product_db() as connection:
        operation = connection.execute("SELECT status, attempt_no FROM m5_turn_operations WHERE request_id=%s",
                                       (command["request_id"],)).fetchone()
        assert operation == {"status": "applied", "attempt_no": 2}
        final = runtime.trace(connection, as_id)
        assert sum(str(turn["turn_id"]) == command["turn_id"] for turn in final["turns"]) == 1
        assert sum(event["event_type"] == "information_transferred" for event in final["events"]) == 1


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
