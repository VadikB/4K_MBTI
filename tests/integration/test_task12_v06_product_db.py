"""Read a v0.6 specialist assignment through the ordinary product API on local TEST."""
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import (
    assessment_programs, auth_service, m10_orchestration, m5_scenario_runtime, m6_repository, routes,
    product_cycle_preparation_queue as preparation, web_session_service as sessions,
)
from Api.llm import deepseek_gateway
from Api.m5_rule_engine import DeepSeekSemanticAdapter
from Api.m6_assessment_worker_v2 import run_request as run_assessment
from Api.m6_worker_v2 import run_request as run_evidence
from scripts.release_specialist_pilot import RELEASE_DIR, ROOT, publish_v06_program, release
from tests.integration.test_m5_battery_scenario_db import TurnGateway
from tests.integration.test_m5_battery_v06_scenarios_db import ANSWER, AUTHORITY, DECISIONS, TASKS, ControlledV06Gateway
from tests.integration.test_m10_product_path_db import AssessmentGateway, EvidenceGateway, RecordedAdmissionGateway
from tests.integration.test_specialist_pilot_release_db import publish_v06_fixture, release_db, seed_baseline  # noqa: F401
from tests.integration.test_task6_processing_status_db import payload


QUOTE = "Часы специалиста сами по себе не подтверждают срок."


class AttributionGateway(EvidenceGateway):
    def chat(self, messages, **kwargs):
        material = json.loads(messages[1]["content"])
        result = json.loads(super().chat(messages, **kwargs))
        turn = next(row for row in material["turns"] if QUOTE in row["content"])
        criterion = next(item for item in material["criteria"] if item["id"] == "K4.I13")
        result["fragments"] = [{"id": "fragment", "turn_id": turn["turn_id"], "quote": QUOTE}]
        result["signals"] = [{"id": "signal", "fragment_id": "fragment", "observation": "Проверил переход от трудозатрат к сроку",
                              "form_description": "письменное обоснование", "context_refs": []}]
        result["evidence"] = [{
            "id": "evidence", "indicator_id": criterion["id"], "m2_version": criterion["m2_version"],
            "type": "Simple", "interpretation": "Различил трудозатраты и срок", "bs_ids": ["signal"],
            "fragment_ids": ["fragment"], "ordered_turn_ids": [turn["turn_id"]], "context_refs": [], "limitations": [],
            "attribution": {"function": criterion["function"], "product": criterion["product"],
                            "evidence_pattern": criterion["evidence_pattern"], "boundaries": criterion["boundary"]},
        }]
        next(bundle for bundle in result["bundles"] if bundle["indicator_id"] == criterion["id"])["evidence_ids"] = ["evidence"]
        return json.dumps(result, ensure_ascii=False)


class ModeAssessment(AssessmentGateway):
    def chat(self, messages, **kwargs):
        result = json.loads(super().chat(messages, **kwargs))
        mode = json.loads(messages[1]["content"])["material"]["mode"]
        if mode == "interim":
            result["mode"] = "interim"
        for target in result["targets"]:
            target["confidence"]["limitations"] = ["Синтетический контроль обработки"]
            target["rationale"] = "Для этого показателя свидетельство в контрольном прогоне не выделялось."
            if mode == "interim":
                target.update(status="INTERIM", outcome=None, descriptor_basis=None)
            elif target["indicator_id"] == "K4.I13":
                target.update(outcome="L1", descriptor_basis="В тексте отделены ресурсы от срока.",
                              rationale="Участник указал, что трудозатраты сами по себе не подтверждают срок.")
                target["refs"].append({"kind": "evidence", "id": "evidence", "meaning": "Закреплённая цитата ответа"})
            else:
                target.update(outcome="INSUFFICIENT_EVIDENCE", descriptor_basis=None,
                              uncertainty={
                                  "missing_or_conflicting_feature": "По цели не выделен отдельный фрагмент.",
                                  "impact": "Уровень по этой цели не устанавливался.",
                                  "clarification_needed": "Уточнение не требуется для контрольного прогона.",
                                  "resolution_information": [],
                                  "requires_new_independent_action": True,
                              })
        return json.dumps(result, ensure_ascii=False)


@pytest.mark.integration
def test_v06_assignment_to_report_and_pdf_in_local_test(release_db, monkeypatch, tmp_path):
    with release_db() as connection:
        publisher, _, organization, _, _ = seed_baseline(connection)
        participant = connection.execute("""INSERT INTO users(email,full_name)
            VALUES('task12-participant@example.test','Синтетический участник') RETURNING id""").fetchone()["id"]
        connection.execute("""INSERT INTO organization_memberships(organization_id,user_id,role,admission_source)
            VALUES(%s,%s,'member','admin_add')""", (organization, participant))
        release(connection, directory=RELEASE_DIR, publisher=publisher, principal="synthetic-local-test")
        admin = connection.execute("INSERT INTO users(email) VALUES('task12-admin@example.test') RETURNING id").fetchone()["id"]
        connection.execute("""INSERT INTO organization_memberships
            (organization_id,user_id,role,admission_source,is_participant)
            VALUES(%s,%s,'admin','admin_add',FALSE)""", (organization, admin))
    publish_v06_fixture(publisher, tmp_path)
    with release_db() as connection:
        candidate = publish_v06_program(connection, publisher=publisher, principal="synthetic-local-test")
        assessment_programs.connect(connection, organization_id=organization, program_definition_id=candidate["program_id"],
                                    actor_user_id=publisher, operation_id="local-v06-test-connect")
    for module in (routes, preparation, sessions, auth_service):
        monkeypatch.setattr(module, "get_connection", release_db)
    auth_service.auth_service.ensure_schema()
    sessions.web_session_service.ensure_schema()
    gateway = ControlledV06Gateway()
    monkeypatch.setattr(deepseek_gateway, "DeepSeekGateway", lambda **_: gateway)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as administrator, TestClient(app) as participant_client:
        administrator.cookies.set(routes.SESSION_COOKIE_NAME, sessions.web_session_service.create_session(admin))
        participant_client.cookies.set(routes.SESSION_COOKIE_NAME, sessions.web_session_service.create_session(participant))
        admin_path = f"/users/admin/organizations/{organization}"
        form = payload(administrator.post(admin_path + "/questionnaire/preview", json={
            "assignment_ref": "specialist-pilot", "source_author": "Синтетическая организация",
            "idempotency_key": "v06-form", "channel": "csv",
            "csv_text": (ROOT / "assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv").read_text(),
        }), 201)
        payload(administrator.post(admin_path + f"/questionnaire/{form['id']}/confirm", json={"recipients": ["participant"]}))
        assignments = payload(administrator.post(admin_path + "/assessment-assignments", json={
            "user_ids": [participant], "assignment_ref": "specialist-pilot", "operation_id": "v06-assignment",
        }))
        assignment = assignments["items"][0]["assignment_id"]
        acquaintance = f"/users/{participant}/acquaintance"
        initial = payload(participant_client.get(acquaintance))
        payload(participant_client.post(acquaintance + "/consent", json={
            "version": initial["readiness"]["briefing"]["consent_version"],
        }))
        payload(participant_client.put(acquaintance + "/answers", json={"confirm": True, "answers": {
            "answer_1": TASKS, "answer_2": DECISIONS, "answer_3": AUTHORITY,
        }}))
        payload(participant_client.post(acquaintance + "/resolve-profile"))
        payload(participant_client.post("/users/assessment/cycles/prepare", json={
            "idempotency_key": "v06-prepare", "selected_skills": ["K1", "K2", "K3", "K4"],
        }), 202)
        worker = preparation.product_cycle_preparation_queue
        job = worker._claim()
        assert job["operation_id"] == "v06-prepare"
        started = perf_counter()
        worker._process(job)
        server_ms = round((perf_counter() - started) * 1000, 2)
        operation = payload(participant_client.get("/users/assessment/cycles/preparation/v06-prepare"))
        assert operation["status"] == "completed", operation
        cycle = payload(participant_client.get(acquaintance))["prepared_plan"]["cycle_id"]
        started = perf_counter()
        opened = payload(participant_client.post("/users/assessment/cycles/start", json={
            "cycle_id": cycle, "idempotency_key": "v06-start",
        }), 201)
        card_http_ms = round((perf_counter() - started) * 1000, 2)
        current = opened["runtime"]["current_situation"]
        situation = current["assessment_situation_id"]
        material_ids = [item["material_id"] for item in current["participant_payload"]["initial_materials"]]
        assert material_ids == [f"M{i:02}" for i in range(1, 7)]
        assert current["participant_payload"]["number_initial_materials"] is True
        again = payload(participant_client.get(f"/users/assessment/cycles/{cycle}/runtime"))["current_situation"]
        assert current["participant_payload"] == again["participant_payload"]

        submit = m5_scenario_runtime.submit_turn_detached
        with release_db() as connection:
            saved = connection.execute("""SELECT cv.case_id,cv.case_version,s.execution_payload_json
                FROM m5_assessment_situations s JOIN m5_case_versions cv ON cv.id=s.case_version_id
                WHERE s.assessment_situation_id=%s""", (situation,)).fetchone()
            selected = connection.execute("""SELECT assignment_id,catalog_ref_json,execution_manifest_json
                FROM m5_cycles WHERE cycle_id=%s""", (cycle,)).fetchone()
        assert (saved["case_id"], saved["case_version"]) == ("CASE.SPEC.02", "v0.9-pilot.1")
        assert selected["assignment_id"] == assignment and selected["catalog_ref_json"]["version"] == "1.4.5"
        semantic = DeepSeekSemanticAdapter(TurnGateway({}, control="FINAL"),
            operation=saved["execution_payload_json"]["ai_operations"]["semantic_decision"])
        def submit_controlled(**kwargs):
            return submit(**{**kwargs, "semantic_adapter": semantic})
        monkeypatch.setattr(m5_scenario_runtime, "submit_turn_detached", submit_controlled)
        answer_id = str(uuid4())
        payload(participant_client.post(f"/users/assessment/m5/situations/{situation}/turns", json={
            "request_id": "v06-answer", "turn_id": answer_id, "content": ANSWER,
        }))
        completion = payload(participant_client.post(f"/users/assessment/m7/cycles/{cycle}/completion", json={
            "action": "complete", "reason": "controlled_partial_completion", "idempotency_key": "v06-close",
        }))
        assert completion["states"]["cycle"] == "collection_closed"
        with release_db() as connection:
            cycle_db_id = connection.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s", (cycle,)).fetchone()["id"]
        for _ in range(14):
            m10_orchestration.advance_once(connection_factory=release_db, gateway=RecordedAdmissionGateway())
            with release_db() as connection:
                requests = connection.execute("SELECT id FROM m6_processing_requests WHERE status='queued'").fetchall()
                assessments = connection.execute("SELECT id FROM m6_assessment_requests WHERE status='queued'").fetchall()
                pipeline = connection.execute("SELECT stage FROM m10_pipeline_runs WHERE cycle_db_id=%s", (cycle_db_id,)).fetchone()
            if pipeline and pipeline["stage"] == "report_ready":
                break
            for request in requests:
                run_evidence(request["id"], connection_factory=release_db, gateway=AttributionGateway())
            for request in assessments:
                run_assessment(request["id"], connection_factory=release_db, gateway=ModeAssessment())
        result = payload(participant_client.get(f"/users/assessment/m8/cycles/{cycle}/status"))
        assert result["pipeline_stage"] == "report_ready", result
        report = payload(participant_client.get(f"/users/assessment/m8/reports/{result['report_id']}"))
        pdf = participant_client.get(f"/users/assessment/m8/reports/{result['report_id']}/pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        with release_db() as connection:
            evidence_states = connection.execute("""SELECT r.mode,r.status,a.error_code
                FROM m6_processing_requests r LEFT JOIN m6_processing_attempts a ON a.request_id=r.id
                ORDER BY r.mode,a.attempt_no""").fetchall()
            assert evidence_states == [
                {"mode": "final_as", "status": "succeeded", "error_code": None},
                {"mode": "interim", "status": "succeeded", "error_code": None},
            ]
            request = connection.execute("""SELECT id FROM m6_processing_requests
                WHERE status='succeeded' AND mode='final_as'""").fetchone()
            stored = m6_repository.read_request(connection, request["id"])
            analysis = m6_repository.read_analysis(connection, stored["analysis_revision_id"])["analysis"]
        fragment, = analysis["fragments"]
        assert fragment["turn_id"] == answer_id and ANSWER[fragment["start"]:fragment["end"]] == QUOTE
        if directory := os.getenv("M5_V06_LOCAL_PRODUCT_EVIDENCE"):
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            (path / "report.pdf").write_bytes(pdf.content)
            (path / "result.json").write_text(json.dumps({
                "scope": "local isolated PostgreSQL with controlled gateways and explicit partial completion",
                "application_version": selected["execution_manifest_json"]["application_version"],
                "assignment_id": assignment, "program_version": candidate["program_version"],
                "catalog": selected["catalog_ref_json"], "case_id": saved["case_id"], "case_version": saved["case_version"],
                "server_preparation_ms": server_ms, "card_http_ms": card_http_ms, "material_ids": material_ids,
                "resume_same_payload": True, "evidence_fragment": fragment, "evidence_states": evidence_states,
                "report_id": report["id"], "pipeline_stage": result["pipeline_stage"],
                "pdf_size": len(pdf.content), "pdf_sha256": hashlib.sha256(pdf.content).hexdigest(),
            }, default=str, ensure_ascii=False, indent=2) + "\n")
