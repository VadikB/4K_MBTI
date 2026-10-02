from contextlib import contextmanager
import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_case_runtime import checksum
from Api.m5_scenario_runtime import transition
from Api.m5_storage import import_package
from Api.m7_completion import complete
from Api.m7_completion import create_additional_session
from Api.m5_cycle_runtime import read_cycle
from Api.m10_product_flow import start_or_resume, read_runtime
from Api.m10_product_flow import next_situation
from Api.m7_cycle_planner import create_plan
from Api import m10_orchestration
from Api import m6_repository
from Api.m6_worker import run_request as run_evidence
from Api.m6_assessment_worker import run_request as run_assessment
from Api.m8_results import read_latest_report, render_pdf
from Api import m6_cycle_aggregation_repository
from Api.m8_results import create_results, create_report, read_report
from Api.m7_completion import read_c46
from scripts.build_m5_case_package import OUTPUT

pytestmark = pytest.mark.integration


@pytest.fixture
def product_db(test_database_url, monkeypatch):
    schema = "m10_product_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))

    @contextmanager
    def factory():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            connection.commit()
            yield connection

    try:
        with factory() as connection:
            connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
            connection.execute("INSERT INTO users VALUES(99)")
            connection.execute("""CREATE TABLE assessment_personalized_profiles(
                id BIGINT PRIMARY KEY,user_id BIGINT NOT NULL,organization_id BIGINT,status TEXT,
                content_json JSONB,provenance_json JSONB,checksum TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
            ensure_m5_runtime_schema(connection)
            m6_repository.ensure_schema(connection)
            m10_orchestration.ensure_schema(connection)
            package=json.loads((OUTPUT/"case-package.json").read_text())
            case=package["cases"][0]
            admitted_cases=[case,package["cases"][2]]
            for admitted_case in admitted_cases:
                admitted_case["status"]="FROZEN"  # isolated S10 fixture; repository package remains WORKING
            import_package(connection,package=package,manifest=json.loads((OUTPUT/"manifest.json").read_text()),
                execution_rules=json.loads((OUTPUT/"execution-rules.json").read_text()))
            connection.execute("INSERT INTO assessment_personalized_profiles VALUES(7,99,NULL,'ready',%s::jsonb,'{}',%s,NOW())",
                (json.dumps({"role_profile":{"code":case["base_role"]}}),"c"*64))
            for admitted_case in admitted_cases:
                case_row=connection.execute("SELECT id FROM m5_case_versions WHERE case_id=%s",(admitted_case["case_id"],)).fetchone()
                assert connection.execute("SELECT status FROM m5_case_versions WHERE id=%s",(case_row["id"],)).fetchone()["status"]=="FROZEN"
                for scope in ("case_format","case_dialogue","assessment_situation"):
                    evidence={"eligibility":"user_admission","scope":scope,"fixture":"S10",
                              "case_id":admitted_case["case_id"]}
                    connection.execute("""INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
                        VALUES(%s,%s,'PASS',%s::jsonb,%s)""",(case_row["id"],scope,json.dumps(evidence),checksum(evidence)))
            connection.commit()
        yield factory
    finally:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


class EvidenceGateway:
    enabled=True
    def chat(self,messages,**_kwargs):
        material=json.loads(messages[1]["content"])
        return json.dumps({"schema_version":1,"fragments":[],"signals":[],"evidence":[],"attribution_notes":[],
            "bundles":[{"indicator_id":x["indicator_id"],"evidence_ids":[],"opportunity_basis":"whole closed dialogue",
                "context_refs":[],"limitations":[],"contradictions":[]} for x in material["indicator_targets"]]})


class AssessmentGateway:
    enabled=True
    def chat(self,messages,**_kwargs):
        value=json.loads(messages[1]["content"]);turn=value["material"]["turns"][-1]
        return json.dumps({"schema_version":1,"mode":"final","targets":[{
            "indicator_id":x["indicator_id"],"m2_version":x["m2_version"],"status":"ASSESSED","outcome":"L0",
            "descriptor_basis":"Synthetic S10 boundary fixture","rationale":"Observed nonperformance in the accepted closed turn",
            "refs":[{"kind":"turn","id":turn["turn_id"],"meaning":"accepted participant action"}],
            "opportunity":"PRESENT","opportunity_basis":"Case requested the action","uncertainty":None,
            "contradictions":[],"clarification_history":[],"stop_reason":None,
            "confidence":{"confirmed_features":["closed turn"],"alternatives_considered":[],
                "limitations":["technical fixture; not GC"],"reliability_protocol_ref":None}}
            for x in value["material"]["indicator_targets"]]})


def _add_turn(connection, as_id, text, key):
    as_db=connection.execute("SELECT id FROM m5_assessment_situations WHERE assessment_situation_id=%s",(as_id,)).fetchone()["id"]
    connection.execute("""INSERT INTO m5_dialogue_turns
        (assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES(%s,%s,2,'assessee','assessee',%s,%s)""",(as_db,uuid4(),text,key))


def _drain_product_pipeline(factory):
    for _ in range(30):
        changed=m10_orchestration.advance_once(connection_factory=factory)
        with factory() as connection:
            evidence=connection.execute("SELECT id FROM m6_processing_requests WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            assessment=connection.execute("SELECT id FROM m6_assessment_requests WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            ready=connection.execute("SELECT count(*) AS n FROM m10_pipeline_runs WHERE status='ready'").fetchone()["n"]
        if evidence:
            run_evidence(evidence["id"],connection_factory=factory,gateway=EvidenceGateway())
            continue
        if assessment:
            run_assessment(assessment["id"],connection_factory=factory,gateway=AssessmentGateway())
            continue
        if ready:
            return
        if not changed:
            break
    raise AssertionError("product pipeline did not reach report_ready")


def test_s10_a_owner_path_reaches_versioned_report_without_admin_finalization(product_db):
    factory=product_db
    with factory() as connection:
        assert connection.execute("SELECT status FROM m5_case_versions WHERE case_id='CASE-TDISC-01'").fetchone()["status"]=="FROZEN"
        started=start_or_resume(connection,user_id=99,key="s10-a")
        cycle_id=str(started["plan"]["cycle_id"])
        assert started["presentation"] is not None, {
            "status":started["decision"]["status"],"explanation":started["decision"].get("explanation_json"),
            "considered":started["decision"].get("considered_json"),"catalog0":started["plan"]["plan"]["catalog"][0]}
        as_id=str(started["decision"]["assessment_situation_id"])
        runtime=read_runtime(connection,cycle_id=cycle_id)
        assert runtime["runtime_kind"]=="cycle"
        assert runtime["current_situation"]["assessment_situation_id"]==as_id
        assert runtime["current_situation"]["participant_payload"]
        _add_turn(connection,as_id,"Синтетический ответ S10-A","s10-a-turn")
        complete(connection,cycle_id=cycle_id,key="s10-a-close",action="complete",reason="plan_finished",initiated_by=99)
        connection.commit()

    assert m10_orchestration.advance_once(connection_factory=factory)
    with factory() as connection:
        evidence=connection.execute("SELECT id,synthetic_confirmed FROM m6_processing_requests").fetchone()
        assert evidence["synthetic_confirmed"] is False
    run_evidence(evidence["id"],connection_factory=factory,gateway=EvidenceGateway())
    assert m10_orchestration.advance_once(connection_factory=factory)
    with factory() as connection:
        assessment=connection.execute("SELECT id,synthetic_confirmed FROM m6_assessment_requests").fetchone()
        assert assessment["synthetic_confirmed"] is False
    run_assessment(assessment["id"],connection_factory=factory,gateway=AssessmentGateway())
    assert m10_orchestration.advance_once(connection_factory=factory)

    with factory() as connection:
        report=read_latest_report(connection,cycle_id,"assessee")
        assert report["c67"]["contract"]=="C-67"
        assert report["c67"]["recommendations"]
        assert {item["type"] for item in report["c67"]["recommendations"]} == {
            "Development", "Consolidation / Maintenance", "Application / Transfer"}
        assert any(skill.get("score",{}).get("value")==0 for skill in report["c67"]["skills"]), report["c67"]["skills"]
        assert report["c67"]["reliability"]["status"]=="not_verified"
        assert render_pdf(report).startswith(b"%PDF")
        state=connection.execute("SELECT status,stage FROM m10_pipeline_runs").fetchone()
        assert state=={"status":"ready","stage":"report_ready"}
        assert connection.execute("SELECT count(*) AS n FROM m8_results").fetchone()["n"]==1


def test_s10_b_additional_session_preserves_boundary_and_reaches_report(product_db):
    factory=product_db
    with factory() as connection:
        started=start_or_resume(connection,user_id=99,key="s10-b")
        cycle_id=str(started["plan"]["cycle_id"])
        first_as=str(started["decision"]["assessment_situation_id"])
        before=read_cycle(connection,cycle_id)
        _add_turn(connection,first_as,"Материал первой AS","s10-b-turn-1")
        interrupted=complete(connection,cycle_id=cycle_id,key="s10-b-interrupt",
            action="interrupt_for_continuation",reason="authorized_return",initiated_by=99)
        session=create_additional_session(connection,cycle_id=cycle_id,
            intent_id=interrupted["continuation_intent_id"],key="s10-b-additional",created_by=99)
        selected=next_situation(connection,cycle_id=cycle_id,user_id=99,key="s10-b-next")
        second_as=str(selected["decision"]["assessment_situation_id"])
        assert second_as != first_as and session["ordinal"] == 2
        _add_turn(connection,second_as,"Материал дополнительной AS","s10-b-turn-2")
        complete(connection,cycle_id=cycle_id,key="s10-b-close",action="complete",reason="plan_finished",initiated_by=99)
        after=read_cycle(connection,cycle_id)
        assert after["calendar_deadline"] == before["calendar_deadline"]
        assert connection.execute("SELECT count(*) AS n FROM m5_cycle_sessions").fetchone()["n"] == 2
        assert connection.execute("SELECT count(*) AS n FROM m5_dialogue_turns WHERE speaker_type='assessee'").fetchone()["n"] == 2
        assert connection.execute("SELECT count(*) AS n FROM m7_continuation_intents WHERE status='consumed'").fetchone()["n"] == 1
        connection.commit()

    _drain_product_pipeline(factory)
    with factory() as connection:
        report=read_latest_report(connection,cycle_id,"assessee")
        assert report["c67"]["contract"] == "C-67"
        assert len(report["c67"]["sessions"]) == 2
        assert len(report["c67"]["assessment_situations"]) == 2
        assert connection.execute("SELECT count(*) AS n FROM m6_analysis_revisions").fetchone()["n"] == 2
        assert connection.execute("SELECT count(*) AS n FROM m6_c54_revisions WHERE mode='final'").fetchone()["n"] == 2
        assert render_pdf(report).startswith(b"%PDF")


def test_s10_d_closed_cycle_without_presented_material_has_no_result_report(product_db):
    factory=product_db
    with factory() as connection:
        plan=create_plan(connection,personalized_profile_id=7,selected_skills=["K1","K2","K3","K4"],
            created_by=99,key="s10-d-plan",usage_scope="assessment")
        cycle_id=str(plan["cycle_id"])
        result=complete(connection,cycle_id=cycle_id,key="s10-d-close",action="complete",
            reason="no_presented_material",initiated_by=99)
        assert result["final_handoff_ids"] == []
        connection.commit()

    assert m10_orchestration.advance_once(connection_factory=factory)
    with factory() as connection:
        report=read_latest_report(connection,cycle_id,"assessee")
        assert report["c67"]["contract"] == "C-67"
        assert all(skill["outcome"] == "no_result" for skill in report["c67"]["skills"])
        assert report["c67"]["coverage"]["cycle_plan"]["admissible_contributions"]["numerator"] == 0
        assert connection.execute("SELECT status FROM m10_pipeline_runs").fetchone()["status"] == "ready"


def test_s10_e_recalculation_preserves_old_results_and_report(product_db):
    factory=product_db
    with factory() as connection:
        plan=create_plan(connection,personalized_profile_id=7,selected_skills=["K1","K2","K3","K4"],
            created_by=99,key="s10-e-plan",usage_scope="assessment")
        cycle_id=str(plan["cycle_id"])
        complete(connection,cycle_id=cycle_id,key="s10-e-close",action="complete",
            reason="history_fixture",initiated_by=99)
        connection.commit()
    assert m10_orchestration.advance_once(connection_factory=factory)

    with factory() as connection:
        old_report=read_latest_report(connection,cycle_id,"assessee")
        old_report_snapshot=json.loads(json.dumps(old_report["c67"]))
        c46=read_c46(connection,cycle_id)
        calculation=m6_cycle_aggregation_repository.create(connection,cycle_id=cycle_id,key="s10-e-calculation-v2",
            expected_composition_checksum=c46["composition_checksum"],
            admission_mechanism_version="m6_admission/1.0.1-history-fixture",decisions=[],created_by=99,
            limitations=["history fixture; normative reliability not verified"])
        results=create_results(connection,cycle_id=cycle_id,calculation_id=calculation["id"],
            key="s10-e-results-v2",target_profile=None,created_by=99)
        new_report=create_report(connection,results_revision_id=results["revision_id"],audience="assessee",
            key="s10-e-report-v2",target_profile=None,created_by=99)
        assert results["revision_no"] == 2
        assert new_report["c67"]["results_revision_no"] == 2
        assert read_report(connection,old_report["id"])["c67"] == old_report_snapshot
        assert read_latest_report(connection,cycle_id,"assessee")["id"] == new_report["id"]
        assert connection.execute("SELECT count(*) AS n FROM m6_analysis_revisions").fetchone()["n"] == 0
        connection.commit()
