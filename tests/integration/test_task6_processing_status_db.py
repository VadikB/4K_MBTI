"""Assignment-scoped failure presentation on the published 2.0 program."""
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from Api import (
    assessment_programs, auth_service, m10_orchestration, m10_product_flow, m5_scenario_runtime,
    m6_assessment_worker_v2, m6_worker_v2, m7_completion, m8_results, routes,
    product_cycle_preparation_queue as preparation, web_session_service as sessions,
)
from Api.llm import deepseek_gateway
from Api.m5_rule_engine import ControlledSemanticAdapter
from Api.m6_interim_retry import RetryTarget, retry
from Api.m7_cycle_planner import create_plan
from scripts.release_specialist_pilot import RELEASE_DIR, ROOT, release
from tests.integration.test_m5_battery_v04_db import V04Gateway
from tests.integration.test_m10_product_path_db import AssessmentGateway, EvidenceGateway, RecordedAdmissionGateway
from tests.integration.test_specialist_pilot_release_db import release_db, seed_baseline  # noqa: F401

pytestmark = pytest.mark.integration
ASSIGNMENT = "specialist-pilot"
ASSIGNMENT_ID = 33
ANSWER = "Сверил сроки и записал порядок действий."


class InvalidGateway:
    def chat(self, *_args, **_kwargs):
        return "{}"


class InterimAssessmentGateway(AssessmentGateway):
    def chat(self, messages, **kwargs):
        result = json.loads(super().chat(messages, **kwargs))
        result["mode"] = "interim"
        for target in result["targets"]:
            target.update(status="INTERIM", outcome=None, descriptor_basis=None)
        return json.dumps(result)


def payload(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def open_assessment(client, administrator, org, participant, factory):
    admin_path = f"/users/admin/organizations/{org}"
    form = payload(administrator.post(admin_path + "/questionnaire/preview", json={
        "assignment_ref": ASSIGNMENT, "source_author": "Синтетическая организация",
        "idempotency_key": "task6-form", "channel": "csv",
        "csv_text": (ROOT / "assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv").read_text(),
    }), 201)
    payload(administrator.post(admin_path + f"/questionnaire/{form['id']}/confirm", json={"recipients": ["participant"]}))
    assignments = payload(administrator.post(admin_path + "/assessment-assignments", json={
        "user_ids": [participant], "assignment_ref": ASSIGNMENT, "operation_id": "task6-assignment",
    }))
    assignment = assignments["items"][0]["assignment_id"]
    acquaintance = f"/users/{participant}/acquaintance"
    initial = payload(client.get(acquaintance))
    payload(client.post(acquaintance + "/consent", json={"version": initial["readiness"]["briefing"]["consent_version"]}))
    payload(client.put(acquaintance + "/answers", json={"confirm": True, "answers": {
        "answer_1": "Сверяю рабочие предложения с требованиями и обсуждаю решения с коллегами.",
        "answer_2": "Готовлю рекомендации, решение согласовывает руководитель.",
        "answer_3": "Использую карточки задач и материалы проверок.",
    }}))
    payload(client.post(acquaintance + "/resolve-profile"))
    payload(client.post("/users/assessment/cycles/prepare", json={
        "idempotency_key": "task6-prepare", "selected_skills": ["K1", "K2", "K3", "K4"],
    }), 202)
    worker = preparation.product_cycle_preparation_queue
    job = worker._claim()
    assert job["operation_id"] == "task6-prepare"
    worker._process(job)
    cycle = payload(client.get(acquaintance))["prepared_plan"]["cycle_id"]
    opened = payload(client.post("/users/assessment/cycles/start", json={
        "cycle_id": cycle, "idempotency_key": "task6-start",
    }), 201)
    with factory() as db:
        saved = db.execute("SELECT catalog_ref_json FROM m5_cycles WHERE cycle_id=%s", (cycle,)).fetchone()
        assert saved["catalog_ref_json"]["version"] == "1.4.4"
    return cycle, opened["runtime"]["current_situation"]["assessment_situation_id"], assignment


def add_second_assignment(db, assignment, cycle, participant):
    new_id = db.execute("""
        INSERT INTO organization_assessment_assignments (organization_id,recipient_user_id,assignment_ref,
            created_by_user_id,questionnaire_revision_id,status,operation_id,request_fingerprint)
        SELECT organization_id,recipient_user_id,'task6-second',created_by_user_id,questionnaire_revision_id,
            status,'task6-closed-assignment','task6-closed-fixture'
        FROM organization_assessment_assignments WHERE id=%s RETURNING id
    """, (assignment,)).fetchone()["id"]
    db.execute("""
        INSERT INTO organization_assessment_source_bindings
            (assignment_id,questionnaire_revision_id,assessment_configuration_id,role_profile_version_id,assigned_by_user_id,operation_id)
        SELECT %s,questionnaire_revision_id,assessment_configuration_id,role_profile_version_id,assigned_by_user_id,'task6-second'
        FROM organization_assessment_source_bindings WHERE assignment_id=%s
    """, (new_id, assignment))
    profile = db.execute("SELECT personalized_profile_id FROM m5_cycles WHERE cycle_id=%s", (cycle,)).fetchone()
    plan = create_plan(db, personalized_profile_id=profile["personalized_profile_id"],
        selected_skills=["K1", "K2", "K3", "K4"], created_by=participant, key="task6-second-plan",
        usage_scope="assessment")
    closed_cycle = str(plan["cycle_id"])
    db.execute("UPDATE m5_cycles SET assignment_id=%s WHERE cycle_id=%s", (new_id, closed_cycle))
    m7_completion.complete(db, cycle_id=closed_cycle, key="task6-close", action="complete",
        reason="no_presented_material", initiated_by=participant)
    return new_id, closed_cycle


@pytest.mark.parametrize("broken", ["evidence", "assessment"])
def test_interim_and_report_failures_are_attributed_to_the_exact_assignment(release_db, monkeypatch, broken):
    with release_db() as db:
        publisher, _, org, _, _ = seed_baseline(db)
        participant = db.execute(
            "INSERT INTO users(email,full_name) VALUES('task6-participant@example.test','Синтетический участник') RETURNING id"
        ).fetchone()["id"]
        db.execute('''INSERT INTO organization_memberships(organization_id,user_id,role,admission_source)
            VALUES(%s,%s,'member','admin_add')''', (org, participant))
        administrator_id = db.execute(
            "INSERT INTO users(email) VALUES('task6-admin@example.test') RETURNING id"
        ).fetchone()["id"]
        db.execute("""INSERT INTO organization_memberships
            (organization_id,user_id,role,admission_source,is_participant)
            VALUES(%s,%s,'admin','admin_add',FALSE)""", (org, administrator_id))
        published = release(db, directory=RELEASE_DIR, publisher=publisher, principal="fixture-deployer")
        assessment_programs.connect(db, organization_id=org, program_definition_id=published["program_id"],
                                    actor_user_id=publisher, operation_id="task6-connect")
        db.execute("SELECT setval(pg_get_serial_sequence('organization_assessment_assignments', 'id'), %s, false)",
                   (ASSIGNMENT_ID,))
    for module in (routes, preparation, sessions, auth_service):
        monkeypatch.setattr(module, "get_connection", release_db)
    auth_service.auth_service.ensure_schema()
    sessions.web_session_service.ensure_schema()
    monkeypatch.setattr(deepseek_gateway, "DeepSeekGateway", lambda **_: V04Gateway())
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as administrator, TestClient(app) as client:
        for http, user in ((administrator, administrator_id), (client, participant)):
            http.cookies.set(routes.SESSION_COOKIE_NAME, sessions.web_session_service.create_session(user))

        cycle, situation, assignment = open_assessment(client, administrator, org, participant, release_db)
        assert assignment == ASSIGNMENT_ID
        runtime_url = f"/users/assessment/cycles/{cycle}/runtime"
        result_url = lambda cid: f"/users/assessment/m8/cycles/{cid}/status"
        admin_url = "/users/admin/organizations"
        turn_id = str(uuid4())
        monkeypatch.setattr(m5_scenario_runtime, "DeepSeekSemanticAdapter",
                            lambda **_: ControlledSemanticAdapter({"SCENARIO_CONTROL": "FINAL"}))
        turn_endpoint = f"/users/assessment/m5/situations/{situation}"
        turn = payload(client.post(turn_endpoint + "/turns", json={
            "request_id": "task6-answer", "turn_id": turn_id, "content": ANSWER,
        }))
        assert turn["turn"]["turn_id"] == turn_id
        waiting = payload(client.get(runtime_url))
        assert waiting["failure_stage"] is None
        assert waiting["finish_availability"] == {"allowed": False, "reason": "INTERIM_PENDING"}

        def count(db):
            return db.execute("""SELECT
                (SELECT count(*) FROM m5_dialogue_turns WHERE speaker_type='assessee') AS turns,
                (SELECT count(*) FROM product_cycle_preparation_operations) AS preparations""").fetchone()

        def saved_answers(db):
            return db.execute("""SELECT t.turn_id::text AS turn_id,t.request_id,t.sequence_no,t.content_text
                FROM m5_dialogue_turns t JOIN m5_assessment_situations s ON s.id=t.assessment_situation_db_id
                WHERE s.assessment_situation_id=%s AND t.speaker_type='assessee'
                ORDER BY t.sequence_no""", (situation,)).fetchall()

        def processing_rows(db):
            return db.execute("""SELECT (SELECT count(*) FROM m10_pipeline_revisions) AS pipeline_revisions,
                (SELECT count(*) FROM m6_processing_requests) AS evidence_requests,
                (SELECT count(*) FROM m6_assessment_requests) AS assessment_requests,
                (SELECT count(*) FROM m6_processing_attempts) AS evidence_attempts,
                (SELECT count(*) FROM m6_assessment_attempts) AS assessment_attempts,
                (SELECT count(*) FROM m7_clarification_decisions) AS clarification_decisions""").fetchone()

        def m6_request(table):
            with release_db() as db:
                return db.execute(f"""SELECT request.id FROM {table} request JOIN m5_assessment_situations s
                    ON s.id=request.as_db_id WHERE s.assessment_situation_id=%s AND request.mode='interim'""",
                    (situation,)).fetchone()["id"]

        evidence_id = m6_request("m6_processing_requests")
        m6_worker_v2.run_request(evidence_id, connection_factory=release_db,
            gateway=InvalidGateway() if broken == "evidence" else EvidenceGateway())
        assert m10_orchestration.advance_once(connection_factory=release_db)
        if broken == "assessment":
            m6_assessment_worker_v2.run_request(m6_request("m6_assessment_requests"),
                connection_factory=release_db, gateway=InvalidGateway())
            assert m10_orchestration.advance_once(connection_factory=release_db)

        with release_db() as db:
            second_assignment, closed_cycle = add_second_assignment(db, assignment, cycle, participant)
            saved = saved_answers(db)
            assert len(saved) == 1 and saved[0]["turn_id"] == turn_id and saved[0]["content_text"] == ANSWER

        def fail(*_args, **_kwargs):
            raise RuntimeError("synthetic failure")

        def stages():
            registry = payload(administrator.get(admin_url))
            organization = next(item for item in registry["items"] if item["id"] == org)
            member = next(item for item in organization["members"] if item["user_id"] == participant)
            return registry, member["assessment_stages"]

        with monkeypatch.context() as patch:
            patch.setattr(m10_orchestration.m6_cycle_aggregation_repository, "create_substantive_detached", fail)
            assert m10_orchestration.advance_once(connection_factory=release_db, gateway=RecordedAdmissionGateway())
            calculation = payload(client.get(result_url(closed_cycle)))
            assert calculation["failure_stage"] == "calculation"
            assert calculation["processing"]["message"] == "Не удалось рассчитать итоговый результат"
        with release_db() as db:
            # Requeue only the second scenario in the fixture to exercise both final-worker boundaries.
            closed_db_id = db.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s", (closed_cycle,)).fetchone()["id"]
            m10_orchestration._set_state(db, closed_db_id, status="processing", stage="results_queued")
        with monkeypatch.context() as patch:
            patch.setattr(m8_results, "_report_content", fail)
            assert m10_orchestration.advance_once(connection_factory=release_db, gateway=RecordedAdmissionGateway())

        with release_db() as db:
            before = count(db)
            attempts_before_read = processing_rows(db)
        for _ in range(2):
            runtime = payload(client.get(runtime_url))
            interim = payload(client.get(result_url(cycle)))
            report = payload(client.get(result_url(closed_cycle)))
            registry, admin = stages()
            assert runtime["pipeline"]["error_code"] == f"M6_{broken.upper()}_FAILED"
            assert runtime["failure_stage"] == interim["failure_stage"] == "answer"
            assert runtime["failed_answer_turn_id"] == turn_id
            assert interim["collection_status"] == "active"
            assert interim["route_progress"] == {"completed": 0, "total": 8}
            assert report["collection_status"] == "calculated"
            assert report["pipeline_stage"] == "report_failed"
            assert report["failure_stage"] == "report"
            assert report["processing"]["message"] == "Прохождение завершено. Не удалось сформировать итоговый отчёт."
            for item in (interim, report):
                assert (item["results_status"], item["report_status"], item["report_id"]) == ("failed", "not_created", None)
                assert item["processing"]["allowed_actions"] == []
            assert admin[ASSIGNMENT]["assignment_id"] == assignment
            assert admin["task6-second"]["assignment_id"] == second_assignment
            assert admin[ASSIGNMENT]["progress"] == {"completed": 0, "planned": 8}
            assert admin[ASSIGNMENT]["failure_stage"] == "answer"
            assert admin["task6-second"]["failure_stage"] == "report"
            assert all(admin[ref]["action"] == "open_processing" for ref in (ASSIGNMENT, "task6-second"))
            assert "failed_answer_turn_id" not in str(admin)
        with release_db() as db:
            assert count(db) == before == {"turns": 1, "preparations": 1}
            assert processing_rows(db) == attempts_before_read
            assert saved_answers(db) == saved
            assert db.execute("""SELECT latest_results_revision_id FROM m10_pipeline_runs WHERE cycle_db_id=%s""",
                              (closed_db_id,)).fetchone()["latest_results_revision_id"]

        assert payload(client.get(turn_endpoint + "/answer-status",
            params={"request_id": "task6-other", "turn_id": str(uuid4())}))["status"] == "absent"
        for http in (client, administrator):
            assert http.post(f"/users/admin/assessment/m8/cycles/{closed_cycle}/processing-recovery",
                json={"idempotency_key": "task6-forbidden-retry"}).status_code == 403

        with release_db() as db, db.transaction(force_rollback=True):
            open_db_id = db.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s", (cycle,)).fetchone()["id"]
            m10_orchestration._set_state(db, open_db_id, status="failed", stage="processing_failed", error="UNKNOWN")
            unknown = m10_product_flow.read_runtime(db, cycle_id=cycle)
            assert unknown["failure_stage"] == "unknown" and unknown["failed_answer_turn_id"] is None
        assert payload(client.get(runtime_url))["failure_stage"] == "answer"

        if broken == "evidence":
            with release_db() as db:
                handoff = db.execute("SELECT handoff_id FROM m6_processing_requests WHERE id=%s",
                                     (evidence_id,)).fetchone()["handoff_id"]
            target = RetryTarget(assignment, UUID(cycle), UUID(situation), handoff, evidence_id, failed_attempt=1)
            recovery = retry(target, connection_factory=release_db, apply=True,
                             operator="task6-synthetic", gateway=EvidenceGateway())
            assert recovery["started"] and recovery["request_status"] == "succeeded"
            assert recovery["request_id"] == evidence_id and recovery["attempt_no"] == 2
            assert m10_orchestration.advance_once(connection_factory=release_db)
        m6_assessment_worker_v2.run_request(m6_request("m6_assessment_requests"),
            connection_factory=release_db, gateway=InterimAssessmentGateway())
        assert m10_orchestration.advance_once(connection_factory=release_db)
        success = payload(client.get(runtime_url))
        assert success["finish_availability"] == {"allowed": True, "reason": "CURRENT_DECISION"}
        assert success["failure_stage"] is None and success["failed_answer_turn_id"] is None
        assert success["clarification"]["status"] == "NO_QUESTION"
        assert payload(client.get(result_url(cycle)))["failure_stage"] is None
        recovered_registry, recovered = stages()
        assert recovered[ASSIGNMENT]["assignment_id"] == ASSIGNMENT_ID
        assert recovered[ASSIGNMENT]["code"] == "active" and recovered[ASSIGNMENT]["failure_stage"] is None
        assert recovered[ASSIGNMENT]["progress"] == {"completed": 0, "planned": 8}
        assert recovered["task6-second"]["failure_stage"] == "report"
        receipt = payload(client.get(turn_endpoint + "/answer-status",
            params={"request_id": "task6-answer", "turn_id": turn_id}))
        assert receipt["status"] == "accepted" and receipt["turn"]["turn_id"] == turn_id

        with release_db() as db:
            assert count(db) == before
            assert saved_answers(db) == saved
            m10_orchestration.request_processing_recovery(db, cycle_id=closed_cycle,
                idempotency_key="task6-report-recovery", created_by=publisher)
        assert m10_orchestration.advance_once(connection_factory=release_db, gateway=RecordedAdmissionGateway())
        ready = payload(client.get(result_url(closed_cycle)))
        report_id = ready["report_id"]
        assert report_id and ready["results_status"] == "ready"
        with release_db() as db:
            m10_orchestration._set_state(db, closed_db_id, status="failed", stage="report_failed", error="LATER_ATTEMPT")
        prior = payload(client.get(result_url(closed_cycle)))
        assert prior["report_id"] == report_id and prior["failure_stage"] == "report"
        assert payload(client.get(f"/users/assessment/m8/reports/{report_id}"))["id"] == report_id
        assert payload(administrator.get(f"/users/admin/m8-access/reports/{report_id}"))["id"] == report_id
        assert client.get(f"/users/admin/m8-access/reports/{report_id}").status_code == 403
        assert stages()[1]["task6-second"]["action"] == "open_report"

        # Optional Playwright handoff contains role projections and a synthetic runtime, without sessions.
        if directory := os.getenv("TASK6_BROWSER_INPUTS"):
            Path(directory, f"{broken}.json").write_text(json.dumps({
                "runtime": runtime, "waiting": waiting, "unknown": jsonable_encoder(unknown), "success": success,
                "assignmentId": assignment, "reportAssignmentId": second_assignment, "turnId": turn_id,
                "status": interim, "report": report, "calculation": calculation, "ready": prior,
                "registry": registry, "recoveredRegistry": recovered_registry, "participant": participant, "org": org,
                "assessment": ASSIGNMENT, "secondAssessment": "task6-second",
            }, ensure_ascii=False), encoding="utf-8")
