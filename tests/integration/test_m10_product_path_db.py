from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from tests.preparation_assertions import assert_queued_operation
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema, ensure_role_profile_schema, ensure_assessment_context_schema
from Api.assessment_role_profiles import publish_base_roles
from Api import assessment_contexts as contexts, participant_profile
from Api.schemas import PersonalizedProfileSelection
from Api.m5_case_runtime import checksum
from Api.m5_functional_generation_service import checksum as functional_checksum
from Api.m5_scenario_runtime import submit_turn, transition
from Api.m5_rule_engine import CharacterReply, Decision, RuleOutcome
from Api.m5_storage import import_package
from Api.m7_completion import complete, finish_current_situation
from Api.m7_completion import create_additional_session
from Api.m5_cycle_runtime import read_cycle
from Api.m10_product_flow import prepare, start_prepared, start_or_resume, read_runtime
from Api.m10_product_flow import next_situation
from Api.product_cycle_preparation_queue import ProductCyclePreparationQueue
from Api.m7_cycle_planner import create_plan
from tests.passport_as_fixture import synthetic_as
from tests.m6_admission_fixture import RecordedAdmissionGateway as AdmissionOnlyGateway
from Api.m10_test_gateway import BrowserAcceptanceGateway
from Api import m10_orchestration
from Api import m6_repository
from Api.m6_worker import run_request as run_evidence
from Api.m6_assessment_worker import run_request as run_assessment
from Api.m8_results import read_latest_report, render_pdf
from Api import m6_cycle_aggregation_repository
from Api.m8_results import create_results, create_report, read_report
from Api.m7_completion import read_c46
from scripts.build_m5_case_package import OUTPUT
from scripts.build_m5_functional_package import OUTPUT as FUNCTIONAL_OUTPUT
from scripts.build_m5_sales_package import build_execution_rules
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
from Api.m5_catalog_integrity import publication_plan, publish_catalog

pytestmark = pytest.mark.integration


class RecordedAdmissionGateway(AdmissionOnlyGateway):
    """Isolated transport for both M6 admission and publishable M8 content."""

    def chat(self, messages, **kwargs):
        value = json.loads(messages[1]["content"])
        if value.get("contract_version") == "m8-descriptive-report/1.2.0":
            return BrowserAcceptanceGateway().chat(messages, **kwargs)
        return super().chat(messages, **kwargs)


@pytest.fixture
def product_db(test_database_url, monkeypatch):
    # This older component fixture has two static Cases and intentionally does
    # not model a human-accepted complete/limited program. Its upstream start
    # permission is a SYNTHETIC substitution, not evidence of product admission.
    # Actual fail-closed readiness + SQL/HTTP start are exercised independently
    # by test_pilot_start_admission_db with the real predicate restored.
    monkeypatch.setattr("Api.assessment_start_readiness.require", lambda *args, **kwargs: {
        "contract": "m7_start_readiness/1", "can_start": True,
        "basis": "SYNTHETIC_UPSTREAM_START_PERMISSION_NOT_HUMAN_ADMISSION"})
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
            connection.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN NOT NULL)')
            connection.execute('CREATE TABLE organization_memberships(organization_id BIGINT REFERENCES organizations(id),user_id BIGINT REFERENCES users(id),UNIQUE(organization_id,user_id))')
            connection.execute('CREATE TABLE user_sessions(id BIGINT PRIMARY KEY,user_id BIGINT REFERENCES users(id),execution_snapshot_json JSONB,execution_checksum TEXT)')
            connection.execute('CREATE TABLE assessment_methodologies(id BIGINT PRIMARY KEY)')
            connection.execute('CREATE TABLE assessment_methodology_versions(id BIGINT PRIMARY KEY,methodology_id BIGINT REFERENCES assessment_methodologies(id),status TEXT,definition_json JSONB)')
            connection.execute('CREATE TABLE assessment_configurations(id BIGINT PRIMARY KEY,methodology_version_id BIGINT REFERENCES assessment_methodology_versions(id),status TEXT,code TEXT,name TEXT)')
            connection.execute('CREATE TABLE assessment_preparation_jobs(id BIGINT PRIMARY KEY)')
            connection.execute('INSERT INTO organizations VALUES(10,TRUE),(20,TRUE)')
            ensure_role_profile_schema(connection); ensure_assessment_context_schema(connection)
            connection.execute('INSERT INTO organization_memberships VALUES(10,99)')
            connection.execute('INSERT INTO assessment_methodologies VALUES(1)')
            connection.execute("INSERT INTO assessment_methodology_versions VALUES(1,1,'published','{\"methodology_version\":\"1.1\"}')")
            connection.execute("INSERT INTO assessment_configurations VALUES(1,1,'published','synthetic','Synthetic configuration')")
            root = Path(__file__).resolve().parents[2]
            package = root/'assessment_definitions/role_profiles/competencies_4k/1.1'
            roles = publish_base_roles(connection, package=json.loads((package/'base_roles.json').read_text()),
                manifest=json.loads((package/'manifest.json').read_text()),published_by_user_id=99,decision_basis='synthetic isolated regression')
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
            organization = {'name':'Synthetic','organization_type':'компания','industry':'образование',
                'activity_description':'Разработка программ','case_reality_level':'обобщённый','organization_name_usage_rules':'не использовать'}
            org = contexts.create_organization_context_draft(connection,organization_id=10,definition=organization)
            contexts.publish_organization_context(connection,version_id=org,confirmed_by_user_id=99)
            acquaintance_answers = {
                'schema_variant': 'corporate', 'schema_version': '1.0', 'assignment_ref': 'ctx01-synthetic',
                'items': [
                    {'key': 'work_situations', 'raw_answer': 'CTX01: разбираю неоднозначные рабочие задачи'},
                    {'key': 'decision_situations', 'raw_answer': 'CTX01: принимаю решения при неполных данных'},
                    {'key': 'constraints_interactions', 'raw_answer': 'CTX01: согласую ограничения с командами'},
                ],
            }
            connection.execute('''CREATE TABLE participant_acquaintance_confirmations(
                id BIGSERIAL PRIMARY KEY,user_id BIGINT,organization_id BIGINT,assignment_ref TEXT,answers_json JSONB,
                user_context_version_id BIGINT,personalized_profile_id BIGINT,
                confirmed_at TIMESTAMP NOT NULL DEFAULT NOW())''')
            connection.execute('''INSERT INTO participant_acquaintance_confirmations(
                user_id,organization_id,assignment_ref,answers_json) VALUES(99,10,'ctx01-synthetic',%s::jsonb)''',
                (json.dumps(acquaintance_answers, ensure_ascii=False),))
            role = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
                JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code=%s""",(case['base_role'],)).fetchone()['id']
            profile = participant_profile.confirm(connection,user_id=99,
                selection=PersonalizedProfileSelection(organization_context_version_id=org,
                    role_profile_version_id=role,assessment_configuration_id=1),
                full_name='Synthetic participant',position='',duties='')
            assert profile['content']['user_context']['regular_tasks'] == acquaintance_answers['items'][0]['raw_answer']
            assert profile['content']['user_context']['decision_situations'] == acquaintance_answers['items'][1]['raw_answer']
            assert profile['content']['user_context']['constraints_and_interactions'] == acquaintance_answers['items'][2]['raw_answer']
            assert profile['content']['user_context']['acquaintance_answers'] == acquaintance_answers
            factory.profile_id = profile['id']
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


def _resolve_interim_for_finish(connection, factory, as_id):
    """Inter-case tests now require the same actual M6/M7 authorization as HTTP."""
    from Api import m7_clarification, m6_assessment_repository
    from Api.m5_scenario_runtime import build_c45
    interim=build_c45(connection,as_id,mode='interim')
    evidence=m10_orchestration.enqueue_handoff(connection,handoff_id=str(interim['handoff_id']),created_by=99)
    connection.commit()
    run_evidence(evidence['id'],connection_factory=factory,gateway=EvidenceGateway())
    m10_orchestration._queue_assessment(connection)
    request=connection.execute("SELECT id FROM m6_assessment_requests WHERE status='queued' ORDER BY created_at DESC LIMIT 1").fetchone()
    connection.commit()
    class InterimAssessment(AssessmentGateway):
        def chat(self,messages,**kwargs):
            value=json.loads(super().chat(messages,**kwargs));value['mode']='interim'
            for target in value['targets']:
                target.update(status='INTERIM',outcome=None,descriptor_basis=None)
            return json.dumps(value)
    run_assessment(request['id'],connection_factory=factory,gateway=InterimAssessment())
    saved=m6_assessment_repository.read_request(connection,request['id'])
    assert saved['status']=='succeeded'
    connection.commit()
    decision=m7_clarification.decide_detached(c54_revision_id=str(saved['c54_revision_id']),
        key='inter-case-resolution:'+str(interim['handoff_id']),created_by=99,connection_factory=factory)
    assert decision['status']=='NO_QUESTION'


def _add_turn(connection, as_id, text, key):
    as_db=connection.execute("SELECT id FROM m5_assessment_situations WHERE assessment_situation_id=%s",(as_id,)).fetchone()["id"]
    connection.execute("""INSERT INTO m5_dialogue_turns
        (assessment_situation_db_id,turn_id,sequence_no,speaker_type,speaker_id,content_text,request_id)
        VALUES(%s,%s,2,'assessee','assessee',%s,%s)""",(as_db,uuid4(),text,key))


def test_prepare_does_not_start_time_and_explicit_start_presents_same_situation(product_db):
    with product_db() as connection:
        prepared = prepare(connection, user_id=99, key="w02-prepare")
        cycle_id = str(prepared["plan"]["cycle_id"])
        decision = prepared["decision"]
        assert decision["status"] == "SELECTED"
        assert prepared["presentation"] is None
        before = read_cycle(connection, cycle_id)
        assert before["status"] == "prepared"
        assert before["started_at"] is None
        assert before["calendar_deadline"] is None
        assert before["consumed_seconds"] == 0
        assert before["sessions"][-1]["status"] == "prepared"
        situation_id = str(decision["assessment_situation_id"])
        prepared_runtime = read_runtime(connection, cycle_id=cycle_id)
        assert prepared_runtime["current_situation"] == {
            "assessment_situation_id": situation_id, "status": "admitted"}
        assert prepared_runtime["trace"] is None

        started = start_prepared(
            connection, user_id=99, cycle_id=cycle_id, key="w02-start",
        )
        assert str(started["decision"]["assessment_situation_id"]) == situation_id
        after = read_cycle(connection, cycle_id)
        assert after["status"] == "active"
        assert after["started_at"] is not None
        assert after["calendar_deadline"] is not None
        assert after["sessions"][-1]["status"] == "active"
        original = connection.execute(
            "SELECT * FROM m5_assessment_situations WHERE assessment_situation_id=%s", (situation_id,)
        ).fetchone()
        candidate_id = uuid4()
        candidate_snapshot = dict(original["snapshot_json"])
        candidate_snapshot["assessment_situation_id"] = str(candidate_id)
        connection.execute("""INSERT INTO m5_assessment_situations
            (assessment_situation_id,case_version_id,personalized_profile_id,cycle_db_id,session_db_id,
             usage_scope,status,snapshot_json,execution_payload_json,snapshot_checksum)
            VALUES(%s,%s,%s,%s,%s,%s,'admitted',%s::jsonb,%s::jsonb,%s)""",
            (candidate_id,original["case_version_id"],original["personalized_profile_id"],original["cycle_db_id"],
             original["session_db_id"],original["usage_scope"],json.dumps(candidate_snapshot),
             json.dumps(original["execution_payload_json"]),checksum(candidate_snapshot)))
        started_runtime = read_runtime(connection, cycle_id=cycle_id)
        assert started_runtime["current_situation"]["assessment_situation_id"] == situation_id
        assert started_runtime["current_situation"]["participant_payload"]
        assert str(candidate_id) not in {x["assessment_situation_id"] for x in started_runtime["situations"]}
        _add_turn(connection, situation_id, "Ответ для проверки состава A01", "a01-composition-turn")
        complete(connection, cycle_id=cycle_id, key="a01-composition-close", action="complete",
                 reason="plan_finished", initiated_by=99)
        c46 = read_c46(connection, cycle_id)["payload_json"]
        dispositions = {x["assessment_situation_id"]: x["route_disposition"]
                        for x in c46["assessment_situations"]}
        assert dispositions[situation_id] == "current"
        assert dispositions[str(candidate_id)] == "unattached_candidate"
        candidate_status = connection.execute(
            "SELECT status FROM m5_assessment_situations WHERE assessment_situation_id=%s", (candidate_id,)
        ).fetchone()["status"]
        assert candidate_status == "admitted"


def test_product_cycle_preparation_operation_returns_only_committed_admitted_cycle(product_db, monkeypatch):
    factory = product_db
    with factory() as connection:
        connection.execute("INSERT INTO users VALUES(100)")
        connection.execute("""CREATE TABLE product_cycle_preparation_operations (
            id BIGSERIAL PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE,
            user_id BIGINT NOT NULL REFERENCES users(id), request_json JSONB NOT NULL,
            request_checksum TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0, result_json JSONB, error_code TEXT,
            error_message TEXT, worker_id TEXT, attempt_token UUID, locked_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP)
        """)
        connection.commit()
    monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", factory)
    queue = ProductCyclePreparationQueue()
    request = {"personalized_profile_id": factory.profile_id, "idempotency_key": "async-product-01",
               "selected_skills": ["K1", "K2", "K3", "K4"]}
    accepted = queue.enqueue(operation_id="async-product-01", user_id=99, request=request)
    assert accepted["status"] == "queued"
    job = queue._claim()
    assert job is not None
    assert queue.get_status("async-product-01")["result_json"] is None
    queue._process(job)
    completed = queue.get_status("async-product-01")
    assert completed["status"] == "completed"
    assert completed["result_json"]["plan"]["cycle_id"]
    assert completed["result_json"]["runtime"]["current_situation"]["status"] == "admitted"
    replay = queue.enqueue(operation_id="async-product-01", user_id=99, request=request)
    assert replay["status"] == "completed"
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        queue.enqueue(operation_id="async-product-01", user_id=99,
                      request={**request, "selected_skills": ["K1"]})
    with pytest.raises(PermissionError, match="OPERATION_NOT_OWNED"):
        queue.enqueue(operation_id="async-product-01", user_id=100, request=request)
    assert queue.get_owned_status("async-product-01", 100) is None


@pytest.mark.integration
def test_http_preparation_retry_requires_server_classified_technical_failure(product_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from Api import routes

    factory = product_db
    with factory() as connection:
        connection.execute("""CREATE TABLE product_cycle_preparation_operations (
            id BIGSERIAL PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE,
            user_id BIGINT NOT NULL REFERENCES users(id), request_json JSONB NOT NULL,
            request_checksum TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0, result_json JSONB, error_code TEXT,
            error_message TEXT, worker_id TEXT, attempt_token UUID, locked_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP)
        """)
    monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", factory)
    monkeypatch.setattr(routes, "get_connection", factory)
    monkeypatch.setattr(routes.acquaintance, "preparation_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id=99) if token == "synthetic-owner" else None)
    queue = ProductCyclePreparationQueue()
    monkeypatch.setattr(routes, "product_cycle_preparation_queue", queue)
    app = FastAPI()
    app.include_router(routes.router)
    request = {"personalized_profile_id": factory.profile_id,
               "idempotency_key": "synthetic-initial", "selected_skills": ["K1", "K2", "K3", "K4"]}
    queue.enqueue(operation_id=request["idempotency_key"], user_id=99, request=request)
    with factory() as connection:
        connection.execute("""UPDATE product_cycle_preparation_operations SET status='failed',
            error_code='ValueError',error_message='M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE'
            WHERE operation_id=%s""", (request["idempotency_key"],))

    with TestClient(app) as client:
        client.cookies.set(routes.SESSION_COOKIE_NAME, "synthetic-owner")
        saved = client.get("/users/assessment/cycles/preparation/synthetic-initial")
        assert saved.status_code == 200
        assert saved.json()["retry_allowed"] is False
        assert saved.json()["error"]["code"] == "ASSESSMENT_AS_NOT_ADMITTED"
        same_key = client.post("/users/assessment/cycles/prepare", json=request)
        assert same_key.status_code == 202 and same_key.json()["operation_id"] == "synthetic-initial"
        blocked = client.post("/users/assessment/cycles/prepare",
                              json={**request, "idempotency_key": "synthetic-forbidden"})
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "PRODUCT_CYCLE_PREPARATION_RETRY_NOT_ALLOWED"
        with factory() as connection:
            assert connection.execute("SELECT COUNT(*) AS n FROM product_cycle_preparation_operations").fetchone()["n"] == 1
            connection.execute("""UPDATE product_cycle_preparation_operations SET
                error_code='TimeoutError',error_message='synthetic private timeout'
                WHERE operation_id='synthetic-initial'""")
        technical = client.get("/users/assessment/cycles/preparation/synthetic-initial")
        assert technical.json()["retry_allowed"] is True
        assert "synthetic private timeout" not in technical.text
        allowed = client.post("/users/assessment/cycles/prepare",
                              json={**request, "idempotency_key": "synthetic-allowed"})
        assert allowed.status_code == 202 and allowed.json()["status"] == "queued"
        concurrent = client.post("/users/assessment/cycles/prepare",
                                 json={**request, "idempotency_key": "synthetic-concurrent"})
        assert concurrent.status_code == 202 and concurrent.json()["operation_id"] == "synthetic-allowed"
    with factory() as connection:
        assert connection.execute("SELECT COUNT(*) AS n FROM product_cycle_preparation_operations").fetchone()["n"] == 2


@pytest.mark.integration
def test_product_cycle_preparation_reclaim_fences_late_worker(product_db, monkeypatch):
    factory = product_db
    with factory() as connection:
        connection.execute("INSERT INTO users VALUES(100)")
        connection.execute("""CREATE TABLE product_cycle_preparation_operations (
            id BIGSERIAL PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE,
            user_id BIGINT NOT NULL REFERENCES users(id), request_json JSONB NOT NULL,
            request_checksum TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0, result_json JSONB, error_code TEXT,
            error_message TEXT, worker_id TEXT, attempt_token UUID, locked_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMP)
        """)
        connection.commit()
    monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", factory)
    queue = ProductCyclePreparationQueue()
    request = {
        "personalized_profile_id": factory.profile_id,
        "idempotency_key": "fenced-product-01",
        "selected_skills": ["K1", "K2", "K3", "K4"],
    }
    queue.enqueue(operation_id="fenced-product-01", user_id=99, request=request)
    first = queue._claim()
    assert first is not None

    with factory() as connection:
        connection.execute(
            """UPDATE product_cycle_preparation_operations
               SET status='queued',worker_id=NULL,attempt_token=NULL,locked_at=NULL
               WHERE id=%s""",
            (first["id"],),
        )
    second = queue._claim()
    assert second is not None
    assert second["attempt_token"] != first["attempt_token"]

    monkeypatch.setattr(
        "Api.product_cycle_preparation_queue.HEARTBEAT_INTERVAL_SECONDS",
        0.02,
    )
    with queue._lease_heartbeat(second):
        with factory() as connection:
            connection.execute(
                """UPDATE product_cycle_preparation_operations
                   SET locked_at=NOW() - INTERVAL '11 minutes' WHERE id=%s""",
                (second["id"],),
            )
        time.sleep(0.08)
        assert queue._claim() is None

    with factory() as connection:
        with pytest.raises(RuntimeError, match="ATTEMPT_STALE"):
            queue._assert_current_attempt(connection, first, lock=True)
        queue._assert_current_attempt(connection, second, lock=True)
        stale_update = connection.execute(
            """UPDATE product_cycle_preparation_operations
               SET status='completed',result_json='{}'::jsonb
               WHERE id=%s AND status='running' AND attempt_token=%s""",
            (first["id"], first["attempt_token"]),
        )
        assert stale_update.rowcount == 0
        current = connection.execute(
            "SELECT status,attempt_token,result_json FROM product_cycle_preparation_operations WHERE id=%s",
            (second["id"],),
        ).fetchone()
        assert current["status"] == "running"
        assert current["attempt_token"] == second["attempt_token"]
        assert current["result_json"] is None

    active = queue.enqueue(operation_id="async-product-02", user_id=99,
                           request={**request, "idempotency_key": "async-product-02"})
    with pytest.raises(ValueError, match='PREPARATION_SCOPE_BUSY'):
        queue.enqueue(operation_id="async-product-03", user_id=99,
                      request={**request, "idempotency_key": "async-product-03", "selected_skills": ["K1"]})
    duplicate_scope = queue.enqueue(operation_id="async-product-04", user_id=99,
                                    request={**request, "idempotency_key": "async-product-02"})
    assert active["operation_id"] == "fenced-product-01"
    assert duplicate_scope["operation_id"] == "fenced-product-01"


@pytest.mark.parametrize(
    ("explicit_profile", "close_during_provider", "crash_phase", "tester_outcome"),
    [
        (True, False, None, None),
        (False, False, None, None),
        (True, True, None, None),
        (True, False, "before_provider", None),
        (True, False, "after_provider", None),
        (True, False, "after_attach", None),
        (True, False, None, "INCOMPLETE"),
        (True, False, None, "FAIL"),
    ],
)
def test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases(
        product_db, monkeypatch, tmp_path, explicit_profile, close_during_provider, crash_phase,
        tester_outcome, *, first_case_only=False, next_failure=None, next_expiry=False, passport_bank=False,
        refresh_profile_before_recovery=False):
    if not passport_bank:
        from Api.cycle_execution_manifest import DEFAULT_DEPENDENCIES
        monkeypatch.delitem(DEFAULT_DEPENDENCIES, "m5_functional_as")
    with product_db() as connection:
        if passport_bank:
            from Api.m5_passport_generation import BANK_PACKAGE
            from scripts.build_m5_passport_bank import RUNTIME_PACKAGE as passport_rules
            from scripts.plan_specialist_program_release import build_release_artifacts
            fixture_package = json.loads((BANK_PACKAGE / "case-package.json").read_bytes())
            fixture_bindings = load_runtime_rule_package(passport_rules, fixture_package["cases"],
                                                         expected_case_package_version="0.6")
            for case in fixture_package["cases"]:
                case["status"] = "FROZEN"
            manifest, rules = build_release_artifacts(fixture_package, fixture_bindings, usage_scope="assessment",
                                                      package_dir=BANK_PACKAGE)
            source_rules = rules
        else:
            fixture_package = json.loads((FUNCTIONAL_OUTPUT / "case-package.json").read_bytes())
            manifest = json.loads((FUNCTIONAL_OUTPUT / "manifest.json").read_bytes())
            source_rules = json.loads((FUNCTIONAL_OUTPUT / "execution-rules.json").read_bytes())
            runtime_package = FUNCTIONAL_OUTPUT.parent.parent / "functional-personalization-runtime/1.2.0"
            fixture_bindings = load_runtime_rule_package(
                runtime_package, fixture_package["cases"], expected_case_package_version="0.5"
            )
            for case in fixture_package["cases"]:
                case["status"] = "FROZEN"
                case["author_case"]["Status"] = "FROZEN"
                fixture_bindings["bindings"]["case_bindings"][case["case_id"]]["case_checksum"] = checksum(case)
            rules = build_execution_rules(fixture_package["cases"], fixture_bindings["bindings"])
        # Only the isolated fixture simulates completed human admission.
        imported = import_package(connection, package=fixture_package, manifest=manifest, execution_rules=source_rules)
        runtime = import_runtime_rule_version(connection, fixture_bindings, rules, package_db_id=imported["package_db_id"])
        cases = connection.execute(
            "SELECT * FROM m5_case_versions WHERE package_id=%s ORDER BY case_id", (imported["package_db_id"],)
        ).fetchall()
        assert len(cases) == 9 and {row["status"] for row in cases} == {"FROZEN"}
        for case in cases:
            for scope in ("case_format", "case_dialogue", "assessment_situation"):
                evidence = {"schema_version": 1, "eligibility": "user_admission", "scope": scope,
                    "result": "PASS", "case_ref": {"id": case["case_id"], "version": case["case_version"],
                    "checksum": case["content_checksum"]}, "base_role": case["base_role"],
                    "usage_scopes": ["assessment"],
                    "origin": {"type": "human_review", "actor_ref": "review:functional-cycle-fixture"}}
                connection.execute("""INSERT INTO m5_qa_evidence
                    (case_version_id,scope,result,evidence_json,evidence_checksum)
                    VALUES(%s,%s,'PASS',%s::jsonb,%s)""",
                    (case["id"], scope, json.dumps(evidence, ensure_ascii=False), checksum(evidence)))
        catalog_plan = publication_plan(connection, package_db_id=imported["package_db_id"],
            case_version_ids=[int(case["id"]) for case in cases], usage_scope="assessment",
            organization_id=10, runtime_rule_version_id=runtime["id"])
        assert catalog_plan["publishable"] is True, catalog_plan["decisions"]
        catalog = publish_catalog(connection, catalog_id="functional-cycle-fixture", catalog_version="1.0",
            package_db_id=imported["package_db_id"], case_version_ids=[int(case["id"]) for case in cases],
            usage_scope="assessment", organization_id=10, published_by=99,
            decision_basis="isolated regression of functional Cycle wiring",
            idempotency_key="functional-cycle-catalog", runtime_rule_version_id=runtime["id"])
        connection.execute("ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT REFERENCES m5_catalogs(id)")
        connection.execute("ALTER TABLE assessment_configurations ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT TRUE")
        connection.execute("UPDATE assessment_configurations SET catalog_version_id=%s WHERE id=1",
                           (catalog["catalog_db_id"],))
        specialist_role = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id
            WHERE r.code='specialist_expert' AND v.status='published'""").fetchone()["id"]
        organization_context = connection.execute("""SELECT v.id FROM assessment_organization_context_versions v
            JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
            WHERE c.organization_id=10 AND v.status='published'""").fetchone()["id"]
        specialist_profile = participant_profile.confirm(connection, user_id=99,
            selection=PersonalizedProfileSelection(organization_context_version_id=organization_context,
                role_profile_version_id=specialist_role, assessment_configuration_id=1),
            full_name='Synthetic specialist', position='', duties='')
        connection.execute("""CREATE TABLE product_cycle_preparation_operations (
            id BIGSERIAL PRIMARY KEY,operation_id TEXT UNIQUE,user_id BIGINT,request_json JSONB,request_checksum TEXT,
            status TEXT DEFAULT 'queued',attempts INTEGER DEFAULT 0,result_json JSONB,error_code TEXT,error_message TEXT,
            worker_id TEXT,attempt_token UUID,locked_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW(),updated_at TIMESTAMP DEFAULT NOW(),completed_at TIMESTAMP)""")
        with pytest.raises(ValueError, match="M5_FUNCTIONAL_PREPARATION_REQUIRED"):
            start_or_resume(
                connection,
                user_id=99,
                key="functional-compatibility-start",
                profile_id=specialist_profile["id"] if explicit_profile else None,
            )
        assert connection.execute(
            "SELECT 1 FROM m5_cycles WHERE owner_user_id=99"
        ).fetchone() is None
        connection.commit()

    class FunctionalGateway:
        enabled = True
        call_count = 0
        transaction_probes = []
        cycle_closed = False
        crash_injected = False
        def chat_with_trace(self, messages, **kwargs):
            type(self).call_count += 1
            with product_db() as probe:
                probe_pid = probe.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
                observed_at = probe.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
                # The provider boundary must not inherit a transaction or a row lock
                # from PM-03. NOWAIT turns a leaked lock into a deterministic failure.
                probe.execute(
                    """SELECT id FROM product_cycle_preparation_operations
                       WHERE operation_id='functional-cycle' FOR UPDATE NOWAIT"""
                ).fetchone()
                idle_in_transaction = probe.execute(
                    """SELECT count(*) AS value FROM pg_stat_activity
                       WHERE datname=current_database() AND pid<>%s
                         AND state='idle in transaction'""",
                    (probe_pid,),
                ).fetchone()["value"]
                type(self).transaction_probes.append({
                    "observed_at": observed_at,
                    "idle_in_transaction": idle_in_transaction,
                })
            if crash_phase == "before_provider" and not type(self).crash_injected:
                type(self).crash_injected = True
                raise SystemExit("controlled crash before provider response")
            payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
            if ":generation:" in kwargs["routing_key"]:
                if close_during_provider and not type(self).cycle_closed:
                    with product_db() as closer:
                        closer.execute(
                            """UPDATE m5_cycles SET status='collection_closed',updated_at=NOW()
                               WHERE id=(SELECT id FROM m5_cycles WHERE owner_user_id=99
                                         ORDER BY created_at DESC LIMIT 1)"""
                        )
                    type(self).cycle_closed = True
                content = json.dumps(synthetic_as(payload), ensure_ascii=False)
            else:
                required = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
                content = json.dumps({"candidate_checksum": payload.get("candidate_checksum"),
                                      "checks": [{"check_id": item["check_id"],
                        "status": ("TECHNICAL_ERROR" if tester_outcome == "INCOMPLETE" else "FAIL")
                                  if tester_outcome and ":tester:" in kwargs["routing_key"]
                                  and item["check_id"] == "common.confidentiality" else "PASS",
                        "reason": "synthetic mandatory failure" if tester_outcome else "isolated functional Cycle fixture",
                        "evidence_paths": [],
                        "findings": ([{"code": "SYNTHETIC_BLOCK", "severity": "blocking",
                                      "paths": ["candidate_as"], "reason": "synthetic mandatory failure",
                                      "requirement_ref": item["check_id"]}]
                                     if tester_outcome == "FAIL" and ":tester:" in kwargs["routing_key"]
                                     and item["check_id"] == "common.confidentiality" else []),
                        "adversarial_review": {"candidate_conflicts": [], "resolution": "fixture"}}
                        for item in required]}, ensure_ascii=False)
            return SimpleNamespace(content=content, sent={}, provider={"finish_reason": "stop"})

    monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", product_db)
    monkeypatch.setattr("Api.llm.deepseek_gateway.DeepSeekGateway", FunctionalGateway)
    crash_state = {"after_provider": False, "after_attach": False}
    if crash_phase == "after_provider":
        from Api import m5_functional_generation_service as generation_service
        original_prepare = generation_service.prepare

        def crash_after_provider(*args, **kwargs):
            result = original_prepare(*args, **kwargs)
            if not crash_state["after_provider"]:
                crash_state["after_provider"] = True
                raise SystemExit("controlled crash after provider response")
            return result

        monkeypatch.setattr(generation_service, "prepare", crash_after_provider)
    if crash_phase == "after_attach":
        from Api import m7_cycle_planner as cycle_planner
        original_attach = cycle_planner.attach_functional_generated_as

        def crash_after_attach(connection, **kwargs):
            result = original_attach(connection, **kwargs)
            if not crash_state["after_attach"]:
                connection.commit()
                crash_state["after_attach"] = True
                raise SystemExit("controlled crash after committed attach")
            return result

        monkeypatch.setattr(cycle_planner, "attach_functional_generated_as", crash_after_attach)
    queue = ProductCyclePreparationQueue()
    request = {"idempotency_key": "functional-cycle",
               "selected_skills": ["K1", "K2", "K3", "K4"]}
    if explicit_profile:
        request["personalized_profile_id"] = specialist_profile["id"]
    queue.enqueue(operation_id="functional-cycle", user_id=99, request=request)
    first_claim = queue._claim()
    if crash_phase:
        with pytest.raises(SystemExit, match="controlled crash"):
            queue._process(first_claim)
        crashed = queue.get_status("functional-cycle")
        assert crashed["status"] == "running"
        with product_db() as connection:
            if refresh_profile_before_recovery:
                later_profile = participant_profile.confirm(
                    connection, user_id=99,
                    selection=PersonalizedProfileSelection(
                        organization_context_version_id=organization_context,
                        role_profile_version_id=specialist_role, assessment_configuration_id=1,
                    ),
                    full_name="Synthetic specialist", position="Новая должность", duties="Новые задачи",
                )
                assert later_profile["id"] != specialist_profile["id"]
            connection.execute(
                """UPDATE product_cycle_preparation_operations
                   SET locked_at=NOW() - INTERVAL '11 minutes' WHERE id=%s""",
                (first_claim["id"],),
            )
        recovered_claim = queue._claim()
        assert recovered_claim is not None
        assert recovered_claim["attempt_token"] != first_claim["attempt_token"]
        # A previously claimed operation cannot attach or overwrite the new attempt.
        queue._process(first_claim)
        assert queue.get_status("functional-cycle")["status"] == "running"
        queue._process(recovered_claim)
    else:
        queue._process(first_claim)
    operation = queue.get_status("functional-cycle")
    assert FunctionalGateway.transaction_probes
    assert all(item["observed_at"] for item in FunctionalGateway.transaction_probes)
    assert all(item["idle_in_transaction"] == 0 for item in FunctionalGateway.transaction_probes)
    if tester_outcome:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from Api import routes

        assert operation["status"] == "failed", operation
        code = ('M5_FUNCTIONAL_VERIFICATION_INCOMPLETE' if tester_outcome == 'INCOMPLETE'
                else 'M5_FUNCTIONAL_AS_NOT_ADMITTED')
        assert operation["error_message"] == f"{code}:{tester_outcome}"
        diagnostic = operation["result_json"]["generated"]["tester"]
        assert diagnostic["aggregation"]["status"] == tester_outcome
        assert diagnostic["aggregation"]["admitted_for_participant"] is False
        assert any(item["check_id"] == "common.confidentiality"
                   for item in diagnostic["checks"])
        with product_db() as connection:
            saved_profile = connection.execute(
                "SELECT content_json FROM assessment_personalized_profiles WHERE id=%s",
                (specialist_profile["id"],),
            ).fetchone()["content_json"]
            assert saved_profile
            assert connection.execute("SELECT COUNT(*) AS n FROM m5_assessment_situations").fetchone()["n"] == 0
            assert connection.execute(
                "SELECT COUNT(*) AS n FROM m5_cycles WHERE owner_user_id=99 AND started_at IS NOT NULL"
            ).fetchone()["n"] == 0
            assert connection.execute("SELECT COUNT(*) AS n FROM m5_dialogue_turns").fetchone()["n"] == 0
        monkeypatch.setattr(routes, "get_connection", product_db)
        monkeypatch.setattr(routes.acquaintance, "preparation_scope", lambda *args, **kwargs: None)
        monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                            lambda token: SimpleNamespace(id=99) if token == "synthetic-owner" else None)
        monkeypatch.setattr(routes, "product_cycle_preparation_queue", queue)
        app = FastAPI()
        app.include_router(routes.router)
        calls_before_readback = FunctionalGateway.call_count
        with TestClient(app) as client:
            client.cookies.set(routes.SESSION_COOKIE_NAME, "synthetic-owner")
            for _ in range(2):
                response = client.get("/users/assessment/cycles/preparation/functional-cycle")
                assert response.status_code == 200
                assert response.json()["status"] == "failed"
        assert FunctionalGateway.call_count == calls_before_readback
        assert queue.get_status("functional-cycle")["result_json"] == operation["result_json"]
        return
    if close_during_provider:
        assert operation["status"] == "failed", operation
        assert operation["error_message"] == "M7_COLLECTION_CLOSED"
        with product_db() as connection:
            assignment = connection.execute(
                """SELECT a.assessment_situation_db_id FROM m7_route_decisions d
                   JOIN m5_cycles c ON c.id=d.cycle_db_id
                   LEFT JOIN m7_route_assignments a ON a.decision_id=d.id
                   WHERE c.owner_user_id=99 ORDER BY d.created_at DESC LIMIT 1"""
            ).fetchone()
            assert assignment["assessment_situation_db_id"] is None
        return
    assert operation["status"] == "completed", operation
    prepared = operation["result_json"]
    with product_db() as connection:
        route_ids = [item["case_id"] for item in prepared["plan"]["plan"]["route"]]
        assert route_ids
        assert all(case_id.startswith("CASE.SPEC.") for case_id in route_ids)
        assert not any(case_id.startswith("CASE-TDISC-") for case_id in route_ids)
        decision = connection.execute("""SELECT d.* FROM m7_route_decisions d
            JOIN m5_cycles c ON c.id=d.cycle_db_id WHERE c.cycle_id=%s ORDER BY d.created_at DESC LIMIT 1""",
            (prepared["plan"]["cycle_id"],)).fetchone()
        assert decision["selected_case_id"].startswith("CASE.SPEC.")
        situation = connection.execute("""SELECT s.snapshot_json,s.snapshot_checksum,s.execution_payload_json
            FROM m5_assessment_situations s JOIN m7_route_assignments a ON a.assessment_situation_db_id=s.id
            WHERE a.decision_id=%s""", (decision["id"],)).fetchone()
        assignment_count = connection.execute(
            "SELECT count(*) AS value FROM m7_route_assignments WHERE decision_id=%s",
            (decision["id"],),
        ).fetchone()["value"]
        assert assignment_count == 1
        assert situation["snapshot_json"]["case_ref"]["id"].startswith("CASE.SPEC.")
        generated_ref = situation["execution_payload_json"]["runtime_rule_ref"]
        generated_trace = situation["execution_payload_json"]["ai_operations"]["functional_personalization"]
        assert generated_ref == {"source": "functional_generation",
                                 "candidate_checksum": generated_trace["candidate_checksum"]}
        assert generated_trace["admitted_for_participant"] is True
        assert generated_trace["schema_version"] == 2
        assert functional_checksum(generated_trace["accepted_as"]) == generated_trace["candidate_checksum"]
        assert generated_trace["tester_input_checksum"] == generated_trace["tester"]["provider_operation"]["input_checksum"]
        assert generated_trace["source_snapshot"]["case"]["CaseID"] == decision["selected_case_id"]
        assert generated_trace["accepted_as"]["CaseVersion"] == decision["selected_case_version"]
        assert not set(generated_trace["source_snapshot"]) & {"author_as_example"}
        if passport_bank:
            refs = generated_trace["source_snapshot"]["refs"]
            assert refs["runtime_rule"]["version"] == "1.3.1"
            assert decision["selected_case_id"] == "CASE.SPEC.02"
            assert refs["protocol_package"]["version"] == "3.0.0"
            assert refs["as_contract"]["version"] == "2.0.0"
            assert generated_trace["tester"]["protocol"]["checksum"] == refs["tester_protocol"]["sha256"]
            for reviews in generated_trace["tester"]["independent_checks"].values():
                by_id = {item["check_id"]: item for item in reviews}
                for check_id in ("common.professional_consistency", "case02.attractive_feature", "indicator:K1.I09"):
                    assert by_id[check_id]["requirement"]["case_content"]
            k1_i09 = next(row for row in generated_trace["accepted_as"]["IndicatorObservability"]
                          if row["IndicatorID"] == "K1.I09")
            assert k1_i09["Что сохранить при адаптации"]
        assert generated_trace["source_snapshot"]["profile_checksum"] == situation["snapshot_json"]["profile_ref"]["checksum"]
        if refresh_profile_before_recovery:
            assert generated_trace["source_snapshot"]["profile_checksum"] == specialist_profile["checksum"]
        # AS-PRESENTATION-DIAG-01: real persisted snapshot from the existing
        # controlled-provider pipeline, not an injected successful resolver.
        public = situation["snapshot_json"]["participant_payload"]
        accepted = generated_trace["accepted_as"]
        public_p00 = next(item for item in accepted["Материалы"] if item["MaterialID"] == "P00")
        assert public["introduction"] == public_p00["Текст"]
        assert [item["material_id"] for item in public["initial_materials"]] == [
            item for item in accepted["Стартовые MaterialIDs"] if item != "P00"]
        assert not set(public) & {"initial_situation", "trigger", "assessee_position",
            "participants_and_positions", "assessee_task", "conditions_and_constraints"}
        assert "определяются в AS" not in json.dumps(public, ensure_ascii=False)
        frozen_public = copy.deepcopy(public)
        assert checksum(situation['snapshot_json']) == situation['snapshot_checksum']
        assert checksum(situation['execution_payload_json']) == situation['snapshot_json']['execution_payload_ref']['checksum']
        assert "planned case durations do not constrain selection" in prepared["plan"]["plan"]["duration_semantics"]
        selected_case = connection.execute("SELECT case_version_id FROM m5_assessment_situations WHERE id=%s",
            (connection.execute("SELECT assessment_situation_db_id FROM m7_route_assignments WHERE decision_id=%s",
                                (decision["id"],)).fetchone()["assessment_situation_db_id"],)).fetchone()
        with pytest.raises(psycopg.Error, match="Referenced M5 CaseVersion content is immutable"):
            with connection.transaction():
                connection.execute("UPDATE m5_case_versions SET status='WORKING' WHERE id=%s",
                                   (selected_case["case_version_id"],))

    class Semantic:
        def decide(self, *, rule, text, turn_id, context):
            return Decision(RuleOutcome.UNKNOWN, "REGRESSION", "controlled regression", (turn_id,),
                            adapter="controlled", controlled_test=True)

    class Character:
        def respond(self, *, material, character, text, turn_id, context):
            return CharacterReply("UNKNOWN", None, "controlled", controlled_test=True)

    cycle_id = str(prepared["plan"]["cycle_id"])
    first_as = str(prepared["decision"]["assessment_situation_id"])
    generation_calls = FunctionalGateway.call_count

    # Refresh/retry and an explicit next while the current AS is still open reuse
    # persisted state. Neither path may call generator/tester again.
    replay_operation = "functional-cycle-replay"
    accepted_replay = queue.enqueue(operation_id=replay_operation, user_id=99, request={
        **request, "idempotency_key": replay_operation,
    })
    assert accepted_replay['operation_id'] == 'functional-cycle'
    assert queue._claim() is None
    replay = queue.get_status(accepted_replay['operation_id'])
    assert replay["status"] == "completed"
    assert replay["result_json"]["decision"]["assessment_situation_id"] == first_as
    assert FunctionalGateway.call_count == generation_calls

    if not first_case_only:
        waiting_operation = "functional-cycle-waiting"
        queue.enqueue(operation_id=waiting_operation, user_id=99, request={
            "kind": "next", "cycle_id": cycle_id, "idempotency_key": waiting_operation,
        })
        queue._process(queue._claim())
        waiting = queue.get_status(waiting_operation)
        assert waiting["status"] == "completed", waiting
        assert waiting["result_json"]["decision"]["status"] == "WAITING_CURRENT_AS"
        assert FunctionalGateway.call_count == generation_calls

    with product_db() as connection:
        start_prepared(connection, user_id=99, cycle_id=cycle_id, key="functional-cycle-start")
        assert read_runtime(connection, cycle_id=cycle_id)["current_situation"]["participant_payload"] == frozen_public
        # HTTP is a separate real transaction: publish the explicit start first,
        # exactly as the product request does before a subsequent runtime GET.
        connection.commit()
        # A separate HTTP read uses the actual owner SQL guard/runtime resolver
        # and PostgreSQL connection; only the authentication token lookup is a
        # controlled identity fixture. This is NOT an auth acceptance test.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from Api import routes
        monkeypatch.setattr(routes, "get_connection", product_db)
        monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                            lambda token: SimpleNamespace(id=99) if token == "projection-fixture" else None)
        app = FastAPI()
        app.include_router(routes.router)
        with TestClient(app) as http:
            http.cookies.set(routes.SESSION_COOKIE_NAME, "projection-fixture")
            response = http.get(f"/users/assessment/cycles/{cycle_id}/runtime")
            assert response.status_code == 200, response.text
            assert response.json()["current_situation"]["participant_payload"] == frozen_public
            assert response.json()["current_situation"]["response_format"] == (
                "dialogue" if situation["execution_payload_json"]["characters"] else "written"
            )
            assert not [turn for turn in response.json()['trace']['turns'] if turn['speaker_type'] == 'assessee']
            # Allowlisted primary readback saved before fixture DROP SCHEMA.
            # Source QA/provider/start permission are synthetic substitutions;
            # persistence, owner SQL guard and HTTP runtime are real PostgreSQL.
            (tmp_path / 'as-presentation-persistence.json').write_text(json.dumps({
                'scope': 'SYNTHETIC_PROVIDER_AND_UPSTREAM_ADMISSION_REAL_POSTGRESQL_HTTP',
                'parameters': {'explicit_profile': explicit_profile, 'crash_phase': crash_phase},
                'cycle_id': cycle_id, 'assessment_situation_id': first_as,
                'assignment_count': assignment_count, 'snapshot_checksum': situation['snapshot_checksum'],
                'candidate_checksum': generated_trace['candidate_checksum'],
                'accepted_as_checksum': functional_checksum(accepted),
                'case_ref': situation['snapshot_json']['case_ref'],
                'case_route': route_ids,
                'profile_ref': situation['snapshot_json']['profile_ref'],
                'execution_payload_ref': situation['snapshot_json']['execution_payload_ref'],
                'compiler': generated_trace['source_snapshot']['refs']['package']['compiler'],
                **({'as_preparation_refs': {name: refs[name] for name in (
                    'protocol_package', 'case_content_contract', 'tester_protocol', 'm2')},
                    'tester_protocol': generated_trace['tester']['protocol']} if passport_bank else {}),
                'persisted_public': frozen_public, 'http_public': response.json()['current_situation']['participant_payload'],
                'http_status': response.status_code, 'assessment_answers_at_readback': 0,
                'snapshot_checksum_verified': True, 'execution_checksum_verified': True,
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        if first_case_only:
            assert FunctionalGateway.call_count == generation_calls
            return  # REMAIN_05: first AS, zero assessment answers, no Next/Report.
        submit_turn(connection, assessment_situation_id=first_as,
                    request_id="functional-cycle-turn", turn_id=str(uuid4()),
                    content="Контролируемый ответ для перехода ко второй ситуации.",
                    semantic_adapter=Semantic(), character_adapter=Character())
        transition(connection, assessment_situation_id=first_as, action="scenario_end",
                   reason="regression", request_id="functional-cycle-end")
        _resolve_interim_for_finish(connection,product_db,first_as)
        # The started Cycle keeps its frozen CASE.SPEC route even when the mutable
        # configuration pointer changes before the next position is prepared.
        connection.execute("UPDATE assessment_configurations SET catalog_version_id=NULL WHERE id=1")
        connection.commit()

    # The actual participant HTTP handler must expose the same durable operation
    # through queued/running/completed, with no second Next command on readback.
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from Api import routes
    with product_db() as connection:
        connection.execute("INSERT INTO users VALUES(100)")
    monkeypatch.setattr(routes, "get_connection", product_db)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id={"functional-owner": 99,
                            "functional-other": 100}[token]) if token in
                        {"functional-owner", "functional-other"} else None)
    monkeypatch.setattr(routes, "product_cycle_preparation_queue", queue)
    app = FastAPI()
    app.include_router(routes.router)
    second_operation = 'next:' + first_as
    support_case = next_failure in {'FAIL', 'TECHNICAL'}
    if support_case:
        from Api import preparation_observation, support_preparation
        support_reference = preparation_observation.reference('cycle', second_operation)
        support_path = '/users/admin/support/preparation'
        with product_db() as connection:
            connection.execute("""CREATE TABLE organization_assessment_assignments (
                id BIGINT PRIMARY KEY,organization_id BIGINT NOT NULL,recipient_user_id BIGINT NOT NULL,
                assignment_ref TEXT NOT NULL,status TEXT NOT NULL,revoked_at TIMESTAMP)""")
            connection.execute("""INSERT INTO organization_assessment_assignments
                VALUES (41,10,99,'synthetic-next','active',NULL)""")
            connection.execute('UPDATE m5_cycles SET assignment_id=41 WHERE cycle_id=%s', (cycle_id,))

        def support_setup_user(token):
            if token == 'support-platform':
                return SimpleNamespace(id=100, email=routes.ADMIN_EMAIL)
            return {'functional-owner': SimpleNamespace(id=99), 'functional-other': SimpleNamespace(id=100)}.get(token)

        monkeypatch.setattr(routes.web_session_service, 'get_user_by_token', support_setup_user)
    if next_failure and next_failure != 'TECHNICAL':
        original_chat = FunctionalGateway.chat_with_trace
        review_calls = []
        def rejected_next(self, messages, **kwargs):
            review_calls.append(kwargs['routing_key'])
            response = original_chat(self, messages, **kwargs)
            if ':tester:' in kwargs['routing_key']:
                raw = json.loads(response.content)
                check = next((x for x in raw['checks'] if x['check_id'] == 'common.authority'), None)
                if check:
                    if next_failure == 'FAIL':
                        check.update(status='FAIL', findings=[{
                            'code': 'SYNTHETIC_NEXT_DEFECT', 'severity': 'blocking',
                            'reason': 'synthetic localized defect', 'paths': ['candidate_as'],
                            'requirement_ref': check['check_id']}])
                    elif next_failure == 'JSON_EXHAUSTED':
                        response.content = '{"checks":'
                        return response
                    else:
                        raw['checks'].remove(check)
                    response.content = json.dumps(raw)
            return response
        monkeypatch.setattr(FunctionalGateway, 'chat_with_trace', rejected_next)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME, "functional-owner")
        cycle_path = f'/users/assessment/m7/cycles/{cycle_id}'
        finished_first = http.post(cycle_path + '/finish-situation', json={'idempotency_key': 'functional-cycle-finish'})
        assert finished_first.status_code == 200, finished_first.text
        with product_db() as connection:
            paused = read_cycle(connection, cycle_id)
            if next_failure and next_failure != 'TECHNICAL':
                before_cycle = paused
                before_plan = connection.execute('SELECT content_checksum FROM m7_plan_revisions ORDER BY revision_no').fetchall()
                before_as = connection.execute('SELECT snapshot_json,execution_payload_json,status FROM m5_assessment_situations').fetchall()
                before_turns = connection.execute('SELECT * FROM m5_dialogue_turns ORDER BY id').fetchall()
        next_path = cycle_path + '/next'
        status_path = f"/users/assessment/cycles/preparation/{second_operation}"
        assert http.get(status_path).json()['status'] == 'queued', 'Finish schedules the original Next command'
        original_request = {'idempotency_key': second_operation, 'after_assessment_situation_id': first_as}
        accepted = http.post(next_path, json=original_request)
        assert accepted.status_code == 201, accepted.text
        assert_queued_operation(accepted.json(), second_operation, "next")
        if next_failure:
            def concurrent_next(index):
                return queue.enqueue(operation_id=f'parallel-next-{index}', user_id=99,
                    request={'kind': 'next', 'cycle_id': cycle_id, 'idempotency_key': f'parallel-next-{index}'})
            with ThreadPoolExecutor(max_workers=2) as workers:
                assert [op['operation_id'] for op in workers.map(concurrent_next, range(2))] == [second_operation] * 2
        assert http.get(status_path).json()["status"] == "queued"
        if support_case:
            with product_db() as connection:
                connection.execute('SET TRANSACTION READ ONLY')
                pending = support_preparation.read(connection, support_reference)
                assert pending['state'] == 'waiting' and pending['stage'] == 'queued'
                assert pending['assignment_id'] == 41
                assert support_preparation.list_failures(connection)['items'] == []
        claimed = queue._claim()
        assert claimed and claimed["operation_id"] == second_operation
        assert http.get(status_path).json()["status"] == "running"
        if support_case:
            preparation_observation.begin('cycle', second_operation, claimed['attempt_token'],
                                          'next', 'next', factory=product_db)
            with product_db() as connection:
                assert support_preparation.read(connection, support_reference)['state'] == 'waiting'
                connection.execute("""UPDATE preparation_observations
                    SET stage_started_at=NOW()-INTERVAL '3 minutes', heartbeat_at=NOW()-INTERVAL '2 minutes'
                    WHERE source='cycle' AND operation_id=%s AND attempt_token=%s""",
                    (second_operation, str(claimed['attempt_token'])))
                stale = support_preparation.read(connection, support_reference)
                assert stale['state'] == 'unconfirmed' and stale['stage'] == 'next'
                stage_at, last_known, read_at = (
                    datetime.fromisoformat(stale[key]) for key in ('stage_at', 'last_confirmed_at', 'read_at')
                )
                assert stage_at < last_known < read_at
        assert http.post(next_path, json=original_request).json()["operation_id"] == second_operation
        http.cookies.set(routes.SESSION_COOKIE_NAME, "functional-other")
        assert http.get(status_path).status_code == 404
        assert http.post(next_path, json={"idempotency_key": "foreign-next"}).status_code == 403
        http.cookies.set(routes.SESSION_COOKIE_NAME, "functional-owner")
        if next_failure == 'TECHNICAL':
            def lose_provider(*args, **kwargs):
                raise ConnectionError('synthetic transport')
            with monkeypatch.context() as retry_patch:
                retry_patch.setattr('Api.m5_functional_generation_service.prepare', lose_provider)
                queue._process(claimed)
            failure = http.get(status_path).json()
            assert failure['status'] == 'failed' and failure['retry_allowed'] is True
            assert http.get(status_path).json()['operation_id'] == second_operation
            retry_key = 'functional-cycle-next-retry'
            retry = http.post(next_path, json={'idempotency_key': retry_key})
            assert retry.status_code == 201
            assert http.post(next_path, json={'idempotency_key': retry_key}).json()['operation_id'] == retry_key
            claimed = queue._claim()
            assert claimed['request_json']['preparation_key'] == second_operation
            second_operation = retry_key
            status_path = f'/users/assessment/cycles/preparation/{second_operation}'
        queue._process(claimed)
        finished = http.get(status_path)
        assert finished.status_code == 200
        if next_failure and next_failure != 'TECHNICAL':
            from scripts.preparation_diagnostics import lookup
            from Api.preparation_observation import reference
            assert finished.json()['status'] == 'failed'
            assert finished.json()['retry_allowed'] is False
            expected_code = ('ASSESSMENT_AS_NOT_ADMITTED' if next_failure == 'FAIL'
                             else 'ASSESSMENT_VERIFICATION_INCOMPLETE')
            assert finished.json()['error']['code'] == expected_code
            calls_at_failure = list(review_calls)
            repeated_reads = []
            for _ in range(2):
                operation_read = http.get(status_path)
                runtime_read = http.get(f'/users/assessment/cycles/{cycle_id}/runtime')
                assert operation_read.status_code == runtime_read.status_code == 200
                runtime_operation = runtime_read.json()['preparation_operation']
                operation_body = operation_read.json()
                # read_at belongs to each GET, while the saved terminal outcome is identical.
                assert {**runtime_operation, 'preparation': {k: v for k, v in runtime_operation['preparation'].items() if k != 'read_at'}} == {
                    **operation_body, 'preparation': {k: v for k, v in operation_body['preparation'].items() if k != 'read_at'}}
                assert runtime_read.json()['between_situations'] is True
                assert runtime_read.json()['current_situation'] is None
                assert runtime_read.json()['situations'] == [{'assessment_situation_id': first_as, 'status': 'closed'}]
                repeated_reads.append({'operation': operation_read.json(), 'runtime_operation': runtime_operation})
            # Lost response, same command and another tab never create another AS/Turn.
            assert http.post(next_path, json=original_request).json()['operation_id'] == second_operation
            assert http.post(next_path, json={'idempotency_key': 'forbidden-next-retry'}).status_code == 409
            assert review_calls == calls_at_failure
            with product_db() as connection:
                after_cycle = read_cycle(connection, cycle_id)
                assert connection.execute('SELECT content_checksum FROM m7_plan_revisions ORDER BY revision_no').fetchall() == before_plan
                assert connection.execute('SELECT snapshot_json,execution_payload_json,status FROM m5_assessment_situations').fetchall() == before_as
                assert connection.execute('SELECT * FROM m5_dialogue_turns ORDER BY id').fetchall() == before_turns
                for field in ('cycle_id', 'time_budget_seconds', 'calendar_window_seconds', 'calendar_deadline', 'remaining_seconds'):
                    assert after_cycle[field] == before_cycle[field]
                diagnostic = lookup(connection, reference('cycle', second_operation))[-1]['operation']
                assert diagnostic['candidate_checksum']
                assert diagnostic['admission_checks']
                assert diagnostic['admission_aggregation']['admitted_for_participant'] is False
                if support_case:
                    participant = finished.json()['preparation']
                    admin = routes._project_admin_assessment_stage({
                        'assignment_id': 41, 'cycle_status': 'paused', 'cycle_id': cycle_id,
                        'preparation': participant,
                    })
                    assert admin['preparation']['reference'] == participant['reference'] == support_reference
                    assert diagnostic['operation_id'] == second_operation
                    connection.execute("""UPDATE organization_assessment_assignments
                        SET status='revoked',revoked_at=NOW() WHERE id=41""")
                    connection.execute("""INSERT INTO organization_assessment_assignments
                        VALUES (42,10,99,'synthetic-next','active',NULL)""")
            if support_case:
                http.cookies.set(routes.SESSION_COOKIE_NAME, 'support-platform')
                listed = http.get(support_path)
                first_read = http.get(f'{support_path}/{support_reference}')
                second_read = http.get(f'{support_path}/{support_reference}')
                assert listed.status_code == first_read.status_code == second_read.status_code == 200
                one, two = first_read.json(), second_read.json()
                assert one.pop('read_at') <= two.pop('read_at')
                assert one == two
                assert [item['reference'] for item in listed.json()['items']] == [support_reference]
                assert (one['assignment_id'], one['organization_id'], one['state']) == (41, 10, 'admission_denied')
                assert one['failure_class'] == expected_code and one['last_confirmed_at']
                assert one['previous_position'] == 1
                assert one['result_confirmed_at'] is None
                for forbidden in ('answers', 'result_json', 'error_message', 'candidate_checksum',
                                  'synthetic localized defect', 'attempt_token', second_operation):
                    assert forbidden not in first_read.text
                assert review_calls == calls_at_failure
            assert sum(':generation:repair:' in key for key in review_calls) == (1 if next_failure == 'FAIL' else 0)
            assert sum(':generation:' in key for key in review_calls) == (2 if next_failure == 'FAIL' else 1)
            evidence = {'synthetic': True, 'outcome': next_failure, 'cycle_id': cycle_id,
                        'closed_as': first_as, 'reads': repeated_reads,
                        'generation_calls': sum(':generation:' in key for key in review_calls),
                        'repair_calls': sum(':generation:repair:' in key for key in review_calls),
                        'unchanged_plan_as_turns_budget': True,
                        'candidate_checksum': diagnostic['candidate_checksum'],
                        'aggregation': diagnostic['admission_aggregation']}
            import os
            evidence_dir = os.getenv('CASE_ADMISSION_EVIDENCE')
            if evidence_dir:
                (Path(evidence_dir) / f'http-{next_failure.lower()}.json').write_text(
                    json.dumps(evidence, ensure_ascii=False, indent=2))
            return
        prepared = finished.json()
        assert prepared["status"] == "completed"
        assert prepared["result"]["decision"]["status"] == "SELECTED"
        assert prepared["result"]["presentation"] is None
        if support_case:
            with product_db() as connection:
                connection.execute('SET TRANSACTION READ ONLY')
                resolved = support_preparation.read(connection, support_reference)
                assert resolved['state'] == 'result_confirmed' and resolved['result_confirmed_at']
                assert resolved['last_confirmed_at'] == resolved['result_confirmed_at']
                assert resolved['operation_status'] == 'failed' and resolved['assignment_id'] == 41
                assert support_preparation.list_failures(connection)['items'] == []
        prepared_as = prepared["result"]["decision"]["assessment_situation_id"]
        runtime_path = f'/users/assessment/cycles/{cycle_id}/runtime'
        for _ in range(2):
            runtime = http.get(runtime_path).json()
            assert runtime["between_situations"] is True
            assert runtime["current_situation"] is runtime["trace"] is None
            assert runtime["preparation_operation"]["operation_id"] == second_operation
            assert runtime["status"]["remaining_seconds"] == paused["remaining_seconds"]
            assert datetime.fromisoformat(runtime["status"]["calendar_deadline"]) == paused["calendar_deadline"]
        target = runtime["next_presentation"]
        assert target["assessment_situation_id"] == prepared_as
        present_path = f'/users/assessment/m7/cycles/{cycle_id}/present-next'
        http.cookies.set(routes.SESSION_COOKIE_NAME, "functional-other")
        assert http.post(present_path, json=target).status_code == 403
        http.cookies.set(routes.SESSION_COOKIE_NAME, "functional-owner")
        assert http.post(present_path, json={**target, 'expected_plan_revision_id': str(uuid4())}).status_code == 409

        def read_next_facts(connection):
            return connection.execute("""SELECT s.status,s.started_at,a.presented_at,
                (SELECT COUNT(*) FROM product_cycle_preparation_operations
                 WHERE request_json->>'kind'='next' AND request_json->>'cycle_id'=%s
                   AND request_json->'next_preparation_scope'->>'after_assessment_situation_id'=%s) AS operations,
                (SELECT COUNT(*) FROM m7_route_decisions WHERE cycle_db_id=s.cycle_db_id
                   AND status='SELECTED') AS selected,
                (SELECT COUNT(*) FROM m5_scenario_events WHERE assessment_situation_db_id=s.id
                   AND event_type='scenario_started') AS presentations
                FROM m5_assessment_situations s JOIN m7_route_assignments a ON a.assessment_situation_db_id=s.id
                WHERE s.assessment_situation_id=%s""", (cycle_id, first_as, prepared_as)).fetchone()

        with product_db() as connection:
            before = read_next_facts(connection)
            assert before == {'status': 'admitted', 'started_at': None, 'presented_at': None,
                              'operations': 2 if next_failure == 'TECHNICAL' else 1, 'selected': 2,
                              'presentations': 0}
            if next_expiry:
                connection.execute("""UPDATE m5_cycles SET
                    started_at=clock_timestamp()-make_interval(secs=>calendar_window_seconds)-interval '1 second'
                    WHERE cycle_id=%s""", (cycle_id,))
        if next_expiry:
            response = http.post(present_path, json=target)
            assert response.status_code == 201, response.text
            runtime = response.json()['runtime']
            assert runtime['cycle_id'] == cycle_id
            assert runtime['status']['collection_status'] == 'collection_closed'
            assert runtime['status']['close_reason'] == 'calendar_deadline'
            assert http.post(present_path, json=target).status_code == 409
            with product_db() as connection:
                after = read_next_facts(connection)
                assert after == {**before, 'status': 'closed'}
        else:
            def click_next(_):
                with TestClient(app) as tab:
                    tab.cookies.set(routes.SESSION_COOKIE_NAME, 'functional-owner')
                    return tab.post(present_path, json=target)
            with ThreadPoolExecutor(max_workers=2) as pool:
                presentations = list(pool.map(click_next, range(2)))
            assert [r.status_code for r in presentations] == [201, 201]
            receipts = [r.json()['presentation'] for r in presentations]
            assert all(receipt['assessment_situation_id'] == prepared_as for receipt in receipts)
            assert sum(bool(receipt.get('idempotent')) for receipt in receipts) == 1
            with product_db() as connection:
                after = read_next_facts(connection)
                assert after['status'] == 'active' and after['started_at'] and after['presented_at']
                assert after['presentations'] == 1
                assert after['operations'] == before['operations'] and after['selected'] == before['selected']
                assert read_cycle(connection, cycle_id)['calendar_deadline'] == paused['calendar_deadline']
                connection.execute("""UPDATE m5_cycle_time_intervals
                    SET started_at=started_at-interval '7 seconds'
                    WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)
                    AND ended_at IS NULL AND interval_type='collecting'""", (cycle_id,))
                assert read_cycle(connection, cycle_id)['remaining_seconds'] <= paused['remaining_seconds'] - 7
        import os
        if evidence_dir := os.getenv('ASUX04_EVIDENCE'):
            flavor = 'expiry' if next_expiry else 'retry' if next_failure else 'ready'
            (Path(evidence_dir) / f'http-{flavor}.json').write_text(json.dumps({
                'synthetic': True, 'cycle_id': cycle_id, 'previous_as': first_as, 'next_as': prepared_as,
                'before': before, 'after': after, 'calendar_deadline_at_pause': paused['calendar_deadline'],
                'remaining_seconds_at_pause': paused['remaining_seconds'], 'expiry': next_expiry,
                'technical_retry': next_failure == 'TECHNICAL',
                'closed_reason': runtime['status']['close_reason'],
            }, ensure_ascii=False, indent=2, default=str))
    second = queue.get_status(second_operation)
    assert second["status"] == "completed", second
    assert FunctionalGateway.call_count > generation_calls
    assert second["result_json"]["decision"]["assessment_situation_id"] != first_as
    with product_db() as connection:
        second_payload = connection.execute(
            "SELECT execution_payload_json FROM m5_assessment_situations WHERE assessment_situation_id=%s",
            (second["result_json"]["decision"]["assessment_situation_id"],),
        ).fetchone()["execution_payload_json"]
        second_trace = second_payload["ai_operations"]["functional_personalization"]
        assert second_trace["schema_version"] == 2
        assert functional_checksum(second_trace["accepted_as"]) == second_trace["candidate_checksum"]
        assert second_trace["source_snapshot"]["case"]["CaseID"] == \
            second["result_json"]["decision"]["selected_case_id"]


def test_inter_case_break_closes_only_current_as_and_resumes_on_explicit_next(product_db, monkeypatch):
    with product_db() as connection:
        started = start_or_resume(connection, user_id=99, key="w02-inter-case")
        cycle_id = str(started["plan"]["cycle_id"])
        first_as = str(started["decision"]["assessment_situation_id"])
        _add_turn(connection, first_as, "Синтетический ответ первой ситуации", "w02-inter-case-turn")
        transition(
            connection, assessment_situation_id=first_as, action="scenario_end",
            reason="participant_completed", request_id="w02-inter-case-scenario-end",
        )

        _resolve_interim_for_finish(connection,product_db,first_as)
        closed = finish_current_situation(
            connection, cycle_id=cycle_id, key="w02-inter-case-close", initiated_by=99,
        )
        assert closed["status"] == "between_situations"
        paused = read_cycle(connection, cycle_id)
        assert paused["status"] == "paused"
        assert paused["sessions"][-1]["status"] == "paused"
        assert read_runtime(connection, cycle_id=cycle_id)["between_situations"] is True
        replay = finish_current_situation(
            connection, cycle_id=cycle_id, key="w02-inter-case-close", initiated_by=99,
        )
        assert replay["idempotent"] is True

        selected = next_situation(
            connection, cycle_id=cycle_id, user_id=99, key="w02-inter-case-next",
        )
        assert selected["decision"]["status"] == "SELECTED"
        second_as = str(selected["decision"]["assessment_situation_id"])
        assert second_as != first_as
        resumed = read_cycle(connection, cycle_id)
        assert resumed["status"] == "active"
        assert resumed["sessions"][-1]["status"] == "active"
        assert read_runtime(connection, cycle_id=cycle_id)["current_situation"]["assessment_situation_id"] == second_as
        assert len(selected["plan"]["plan"]["route"]) == 2
        _add_turn(connection, second_as, "Синтетический ответ последней ситуации", "last-as-turn")
        transition(connection, assessment_situation_id=second_as, action="scenario_end",
                   reason="participant_completed", request_id="last-as-end")
        _resolve_interim_for_finish(connection, product_db, second_as)

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from Api import routes
    monkeypatch.setattr(routes, "get_connection", product_db)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _: SimpleNamespace(id=99))
    def unexpected_next(**_kwargs):
        pytest.fail('last position must never enqueue Next')
    monkeypatch.setattr(routes.product_cycle_preparation_queue, 'enqueue', unexpected_next)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME, "synthetic")
        path = f'/users/assessment/m7/cycles/{cycle_id}'
        finished = http.post(path + '/finish-situation', json={'idempotency_key': 'last-as-finish'})
        assert finished.status_code == 200, finished.text
        runtime = http.get(f'/users/assessment/cycles/{cycle_id}/runtime').json()
        assert runtime['cycle_id'] == cycle_id
        assert runtime['status']['collection_status'] == 'collection_closed'
        assert runtime['between_situations'] is False
        assert 'next_presentation' not in runtime
        assert [s['status'] for s in runtime['situations']] == ['closed', 'closed']
        assert runtime['status']['close_reason'] == 'user_completed_scenario'



def _drain_product_pipeline(factory):
    for _ in range(30):
        changed=m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
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
        assert connection.execute("SELECT display_snapshot_json->>'program_name' AS name FROM m5_cycles WHERE cycle_id=%s",
            (cycle_id,)).fetchone()["name"] == "Synthetic configuration"
        connection.execute("UPDATE assessment_configurations SET name='Название после старта' WHERE id=1")
        assert started["presentation"] is not None, {
            "status":started["decision"]["status"],"explanation":started["decision"].get("explanation_json"),
            "considered":started["decision"].get("considered_json"),"catalog0":started["plan"]["plan"]["catalog"][0]}
        as_id=str(started["decision"]["assessment_situation_id"])
        runtime=read_runtime(connection,cycle_id=cycle_id)
        assert runtime["runtime_kind"]=="cycle"
        assert runtime["return_policy_enabled"] is True
        assert runtime["current_situation"]["assessment_situation_id"]==as_id
        assert runtime["current_situation"]["participant_payload"]
        _add_turn(connection,as_id,"Синтетический ответ S10-A","s10-a-turn")
        complete(connection,cycle_id=cycle_id,key="s10-a-close",action="complete",reason="plan_finished",initiated_by=99)
        handoff = connection.execute(
            "SELECT envelope_json FROM m5_c45_handoffs WHERE assessment_situation_db_id="
            "(SELECT id FROM m5_assessment_situations WHERE assessment_situation_id=%s) AND mode='final'",
            (as_id,),
        ).fetchone()['envelope_json']
        assert handoff['profile_snapshot']['user_context']['regular_tasks'].startswith('CTX01:')
        assert handoff['profile_snapshot']['user_context']['decision_situations'].startswith('CTX01:')
        assert handoff['profile_snapshot']['user_context']['constraints_and_interactions'].startswith('CTX01:')
        connection.commit()

    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        evidence=connection.execute("SELECT id,synthetic_confirmed FROM m6_processing_requests").fetchone()
        assert evidence["synthetic_confirmed"] is False
    run_evidence(evidence["id"],connection_factory=factory,gateway=EvidenceGateway())
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        assessment=connection.execute("SELECT id,synthetic_confirmed FROM m6_assessment_requests").fetchone()
        diagnostics = {
            'processing': connection.execute("SELECT status FROM m6_processing_requests").fetchall(),
            'attempts': connection.execute("SELECT status,error_code,trace_json FROM m6_processing_attempts").fetchall(),
            'pipeline': connection.execute("SELECT status,stage,error_code FROM m10_pipeline_runs").fetchall(),
        }
        assert assessment is not None, diagnostics
        assert assessment["synthetic_confirmed"] is False
    run_assessment(assessment["id"],connection_factory=factory,gateway=AssessmentGateway())
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())

    with factory() as connection:
        report=read_latest_report(connection,cycle_id,"assessee")
        assert report["program_name"] == "Synthetic configuration"
        assert report["c67"]["display"]["program_name"] == "Synthetic configuration"
        connection.execute("UPDATE assessment_configurations SET name='Название после оценки' WHERE id=1")
        assert read_report(connection, report["id"])["program_name"] == "Synthetic configuration"
        assert report["c67"]["contract"]=="C-67"
        assert report["c67"]["recommendations"] == []
        assert report["c67"]["descriptive"]["status"] in {"ready", "failed"}
        result = connection.execute('''SELECT r.payload_json FROM m8_result_revisions r
            JOIN m8_results logical ON logical.id=r.results_id
            JOIN m5_cycles cycle ON cycle.id=logical.cycle_db_id
            WHERE cycle.cycle_id=%s ORDER BY r.revision_no DESC LIMIT 1''', (cycle_id,)).fetchone()['payload_json']
        frozen = result['personalized_profile_snapshot']['content']['user_context']
        assert frozen['regular_tasks'].startswith('CTX01:')
        assert frozen['decision_situations'].startswith('CTX01:')
        assert frozen['constraints_and_interactions'].startswith('CTX01:')
        assert any(skill.get("score",{}).get("value")==0 for skill in report["c67"]["skills"]), report["c67"]["skills"]
        assert report["c67"]["reliability"]["status"]=="not_verified"
        assert render_pdf(report).startswith(b"%PDF")
        state=connection.execute("SELECT status,stage FROM m10_pipeline_runs").fetchone()
        assert state=={"status":"ready","stage":"report_ready"}
        assert connection.execute("SELECT count(*) AS n FROM m8_results").fetchone()["n"]==1


def test_admission_processing_failure_is_limited_and_recovery_is_new_revision(product_db):
    from Api import support_reports
    from Api.m8_results import list_owned_cycles
    factory=product_db
    with factory() as connection:
        started=start_or_resume(connection,user_id=99,key="processing-failure")
        cycle_id=str(started["plan"]["cycle_id"])
        as_id=str(started["decision"]["assessment_situation_id"])
        frozen_catalog=dict(connection.execute("SELECT catalog_ref_json FROM m5_cycles WHERE cycle_id=%s",
                                               (cycle_id,)).fetchone()["catalog_ref_json"] or {})
        _add_turn(connection,as_id,"Сохранённый ответ до технического сбоя","processing-failure-turn")
        complete(connection,cycle_id=cycle_id,key="processing-failure-close",action="complete",
                 reason="plan_finished",initiated_by=99)
        connection.commit()
    assert m10_orchestration.advance_once(connection_factory=factory,gateway=RecordedAdmissionGateway())
    with factory() as connection:
        evidence=connection.execute("SELECT id FROM m6_processing_requests").fetchone()
    run_evidence(evidence["id"],connection_factory=factory,gateway=EvidenceGateway())
    assert m10_orchestration.advance_once(connection_factory=factory,gateway=RecordedAdmissionGateway())
    with factory() as connection:
        assessment=connection.execute("SELECT id FROM m6_assessment_requests").fetchone()
    run_assessment(assessment["id"],connection_factory=factory,gateway=AssessmentGateway())
    assert m10_orchestration.advance_once(connection_factory=factory,
        gateway=RecordedAdmissionGateway(fail='joint'))
    with factory() as connection:
        failed=connection.execute("SELECT * FROM m10_pipeline_runs").fetchone()
        assert (failed["status"],failed["stage"],failed["error_code"]) == (
            "failed","admission_processing_failed","M6_ADMISSION_PROCESSING_FAILED")
        old_report=read_latest_report(connection,cycle_id,"assessee")
        assert old_report["c67"]["processing"]["status"] == "failed"
        facts = support_reports.read(connection, UUID(cycle_id), report_id=None, user_id=99, can_recover=True)
        assert (facts["state"], facts["stage_label"]) == ("failed", "Обработка результатов оценивания")
        assert facts["results_status"] == "saved" and not facts["report_openable"]
        assert str(facts["report_id"]) == old_report["id"] and facts["recovery_revision"]
        assert {x["code"] for x in old_report["c67"]["partial_result"]["limitation_reasons"]} >= {
            "technical_failure"}
        assert any("не L0" in item for item in old_report["c67"]["limitations"])
        assert render_pdf(old_report).startswith(b"%PDF")
        card=list_owned_cycles(connection,99)[0]
        assert card["status"] == "failed" and card["report_id"] == old_report["id"]
        saved_turns=connection.execute("SELECT count(*) AS n FROM m5_dialogue_turns").fetchone()["n"]
        assert saved_turns == 1
        retry=m10_orchestration.request_processing_recovery(
            connection,cycle_id=cycle_id,idempotency_key="owned-recovery",created_by=99)
        replay=m10_orchestration.request_processing_recovery(
            connection,cycle_id=cycle_id,idempotency_key="owned-recovery",created_by=99)
        assert retry["id"] == replay["id"]
        connection.commit()
    assert m10_orchestration.advance_once(connection_factory=factory,gateway=RecordedAdmissionGateway())
    with factory() as connection:
        recovered=connection.execute("SELECT * FROM m10_pipeline_runs").fetchone()
        assert (recovered["status"],recovered["stage"]) == ("ready","recovered_report_ready")
        latest=read_latest_report(connection,cycle_id,"assessee")
        assert latest["id"] != old_report["id"] and latest["c67"]["processing"]["status"] == "completed"
        assert read_report(connection,old_report["id"]) == old_report
        assert connection.execute("SELECT count(*) AS n FROM m6_cycle_calculations").fetchone()["n"] == 2
        assert connection.execute("SELECT count(*) AS n FROM m8_result_revisions").fetchone()["n"] == 2
        assert connection.execute("SELECT count(*) AS n FROM m10_processing_recoveries WHERE status='succeeded'").fetchone()["n"] == 1
        assert connection.execute("SELECT count(*) AS n FROM m5_dialogue_turns").fetchone()["n"] == saved_turns
        assert dict(connection.execute("SELECT catalog_ref_json FROM m5_cycles WHERE cycle_id=%s",
                                      (cycle_id,)).fetchone()["catalog_ref_json"] or {}) == frozen_catalog
        assert connection.execute("SELECT count(*) AS n FROM m5_cycle_sessions").fetchone()["n"] == 1
        connection.commit()


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
        plan=create_plan(connection,personalized_profile_id=factory.profile_id,selected_skills=["K1","K2","K3","K4"],
            created_by=99,key="s10-d-plan",usage_scope="assessment")
        cycle_id=str(plan["cycle_id"])
        result=complete(connection,cycle_id=cycle_id,key="s10-d-close",action="complete",
            reason="no_presented_material",initiated_by=99)
        assert result["final_handoff_ids"] == []
        connection.commit()

    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        report=read_latest_report(connection,cycle_id,"assessee")
        assert report["c67"]["contract"] == "C-67"
        assert all(skill["outcome"] == "no_result" for skill in report["c67"]["skills"])
        assert report["c67"]["coverage"]["cycle_plan"]["admissible_contributions"]["numerator"] == 0
        partial=report["c67"]["partial_result"]
        assert partial["is_incomplete"] is True
        assert partial["progress"]["completed"] == 0
        assert partial["progress"]["planned"] >= 1
        assert partial["progress"]["not_presented"] == partial["progress"]["planned"]
        assert {x["code"] for x in partial["limitation_reasons"]} >= {
            "collection_incomplete","observation_missing"}
        assert render_pdf(report).startswith(b"%PDF")
        assert connection.execute("SELECT status FROM m10_pipeline_runs").fetchone()["status"] == "ready"
        from Api.m8_results import list_owned_cycles
        cycle_db_id = connection.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s", (cycle_id,)).fetchone()["id"]
        m10_orchestration._set_state(connection, cycle_db_id, status="failed",
            stage="recovery_failed", error="synthetic_late_service_failure")
        card = list_owned_cycles(connection, 99)[0]
        assert card["status"] == "report_ready" and card["report_id"] == report["id"]
        assert card["processing_message"] is None


def test_report_failure_recovers_saved_results_without_recalculation(product_db, monkeypatch):
    factory = product_db
    with factory() as connection:
        plan = create_plan(connection, personalized_profile_id=factory.profile_id,
            selected_skills=["K1", "K2", "K3", "K4"], created_by=99,
            key="report01-fault-plan", usage_scope="assessment")
        cycle_id = str(plan["cycle_id"])
        complete(connection, cycle_id=cycle_id, key="report01-fault-close",
            action="complete", reason="no_presented_material", initiated_by=99)
        connection.commit()
    original = m10_orchestration.m8_results.create_report_detached
    def fail_report_once(**_kwargs):
        raise RuntimeError("synthetic_report_storage_failure")
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached", fail_report_once)
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        state = connection.execute("SELECT status,stage FROM m10_pipeline_runs").fetchone()
        assert state == {"status": "failed", "stage": "report_failed"}
        results_before = connection.execute("SELECT id,payload_checksum FROM m8_result_revisions").fetchone()
        calculation_before = connection.execute("SELECT id,c56_hash FROM m6_cycle_calculations").fetchone()
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 0
        revision = connection.execute("SELECT max(revision_no) AS n FROM m10_pipeline_revisions").fetchone()["n"]
        with pytest.raises(ValueError, match="M10_PROCESSING_RECOVERY_STALE"):
            m10_orchestration.request_processing_recovery(connection, cycle_id=cycle_id,
                idempotency_key="stale", created_by=99, expected_pipeline_revision=revision + 1)
        request = m10_orchestration.request_processing_recovery(connection, cycle_id=cycle_id,
            idempotency_key="report01-service-recovery", created_by=99, expected_pipeline_revision=revision)
        replay = m10_orchestration.request_processing_recovery(connection, cycle_id=cycle_id,
            idempotency_key="report01-service-recovery", created_by=99, expected_pipeline_revision=revision)
        assert replay["id"] == request["id"]
        assert request["source_pipeline_revision_no"] == revision
        connection.commit()
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached", original)
    def forbidden_recalculation(**_kwargs):
        raise AssertionError("valid C-56 must not be recalculated")
    monkeypatch.setattr(m10_orchestration.m6_cycle_aggregation_repository,
        "create_substantive_detached", forbidden_recalculation)
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        assert connection.execute("SELECT id,payload_checksum FROM m8_result_revisions").fetchone() == results_before
        assert connection.execute("SELECT id,c56_hash FROM m6_cycle_calculations").fetchone() == calculation_before
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 1
        assert connection.execute("SELECT status FROM m10_pipeline_runs").fetchone()["status"] == "ready"
    with pytest.raises(ValueError, match="M8_REPORT_ALREADY_PUBLISHED"):
        original(results_revision_id=str(results_before["id"]), audience="assessee",
            key="report01-unjustified-second-publication", target_profile=None,
            created_by=99, gateway=RecordedAdmissionGateway(), connection_factory=factory)


def test_restart_after_results_commit_finishes_one_report(product_db, monkeypatch):
    factory = product_db
    with factory() as connection:
        plan = create_plan(connection, personalized_profile_id=factory.profile_id,
            selected_skills=["K1", "K2", "K3", "K4"], created_by=99,
            key="report01-restart-plan", usage_scope="assessment")
        cycle_id = str(plan["cycle_id"])
        complete(connection, cycle_id=cycle_id, key="report01-restart-close",
            action="complete", reason="no_presented_material", initiated_by=99)
        connection.commit()
    original = m10_orchestration.m8_results.create_report_detached
    class WorkerStopped(BaseException):
        pass
    def stop_after_results(**_kwargs):
        raise WorkerStopped()
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached", stop_after_results)
    with pytest.raises(WorkerStopped):
        m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        result = connection.execute("SELECT id,payload_checksum FROM m8_result_revisions").fetchone()
        calculation = connection.execute("SELECT id,c56_hash FROM m6_cycle_calculations").fetchone()
        assert connection.execute("SELECT status FROM m5_cycles WHERE cycle_id=%s", (cycle_id,)).fetchone()["status"] == "calculated"
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 0
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached", original)
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    assert not m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        assert connection.execute("SELECT id,payload_checksum FROM m8_result_revisions").fetchone() == result
        assert connection.execute("SELECT id,c56_hash FROM m6_cycle_calculations").fetchone() == calculation
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 1


def test_concurrent_workers_do_not_generate_second_report(product_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    factory = product_db
    with factory() as connection:
        plan = create_plan(connection, personalized_profile_id=factory.profile_id,
            selected_skills=["K1", "K2", "K3", "K4"], created_by=99,
            key="report01-concurrent-plan", usage_scope="assessment")
        cycle_id = str(plan["cycle_id"])
        complete(connection, cycle_id=cycle_id, key="report01-concurrent-close",
            action="complete", reason="no_presented_material", initiated_by=99)
        connection.commit()
    entered, release = Event(), Event()
    original = m10_orchestration.m8_results.create_report_detached
    calls = []
    def slow_report(**kwargs):
        calls.append(kwargs["results_revision_id"])
        entered.set()
        assert release.wait(10)
        return original(**kwargs)
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached", slow_report)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(m10_orchestration.advance_once,
            connection_factory=factory, gateway=RecordedAdmissionGateway())
        assert entered.wait(10)
        try:
            assert not m10_orchestration.advance_once(connection_factory=factory,
                gateway=RecordedAdmissionGateway())
        finally:
            release.set()
        assert first.result(timeout=10)
    assert len(calls) == 1
    with factory() as connection:
        assert connection.execute("SELECT count(*) AS n FROM m8_result_revisions").fetchone()["n"] == 1
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 1


def test_restart_after_report_commit_reconciles_pipeline_without_generation(product_db, monkeypatch):
    factory = product_db
    with factory() as connection:
        plan = create_plan(connection, personalized_profile_id=factory.profile_id,
            selected_skills=["K1", "K2", "K3", "K4"], created_by=99,
            key="report01-committed-plan", usage_scope="assessment")
        cycle_id = str(plan["cycle_id"])
        complete(connection, cycle_id=cycle_id, key="report01-committed-close",
            action="complete", reason="no_presented_material", initiated_by=99)
        connection.commit()
    original = m10_orchestration._set_state
    class WorkerStopped(BaseException):
        pass
    def stop_before_pipeline_ready(connection, cycle_db_id, **kwargs):
        if kwargs.get("stage") == "report_ready":
            raise WorkerStopped()
        return original(connection, cycle_db_id, **kwargs)
    monkeypatch.setattr(m10_orchestration, "_set_state", stop_before_pipeline_ready)
    with pytest.raises(WorkerStopped):
        m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 1
        pipeline = connection.execute("SELECT status FROM m10_pipeline_runs").fetchone()
        assert pipeline is None or pipeline["status"] != "ready"
    monkeypatch.setattr(m10_orchestration, "_set_state", original)
    def forbidden_generation(**_kwargs):
        raise AssertionError("committed report must not be generated again")
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached", forbidden_generation)
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    with factory() as connection:
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 1
        pipeline = connection.execute("SELECT stage,error_code FROM m10_pipeline_runs").fetchone()
        assert pipeline == {"stage": "report_ready", "error_code": None}


def test_concurrent_direct_report_publication_keeps_one_assessee_report(product_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from Api import m8_descriptive_report
    factory = product_db
    with factory() as connection:
        plan = create_plan(connection, personalized_profile_id=factory.profile_id,
            selected_skills=["K1", "K2", "K3", "K4"], created_by=99,
            key="report01-direct-plan", usage_scope="assessment")
        cycle_id = str(plan["cycle_id"])
        complete(connection, cycle_id=cycle_id, key="report01-direct-close",
            action="complete", reason="no_presented_material", initiated_by=99)
        connection.commit()
    original_report = m10_orchestration.m8_results.create_report_detached
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached",
                        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("synthetic_report_failure")))
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())
    monkeypatch.setattr(m10_orchestration.m8_results, "create_report_detached", original_report)
    with factory() as connection:
        revision_id = str(connection.execute("SELECT id FROM m8_result_revisions").fetchone()["id"])
    barrier = Barrier(2)
    original_generate = m8_descriptive_report.generate
    def concurrent_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(m8_descriptive_report, "generate", concurrent_generate)
    def publish(key):
        try:
            return original_report(results_revision_id=revision_id, audience="assessee", key=key,
                target_profile=None, created_by=99, gateway=RecordedAdmissionGateway(),
                connection_factory=factory)
        except ValueError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, ("report01-direct-a", "report01-direct-b")))
    assert sum(isinstance(item, dict) for item in outcomes) == 1
    assert "M8_REPORT_ALREADY_PUBLISHED" in outcomes
    with factory() as connection:
        assert connection.execute("SELECT count(*) AS n FROM m8_reports").fetchone()["n"] == 1


def test_s10_e_recalculation_preserves_old_results_and_report(product_db):
    factory=product_db
    with factory() as connection:
        plan=create_plan(connection,personalized_profile_id=factory.profile_id,selected_skills=["K1","K2","K3","K4"],
            created_by=99,key="s10-e-plan",usage_scope="assessment")
        cycle_id=str(plan["cycle_id"])
        complete(connection,cycle_id=cycle_id,key="s10-e-close",action="complete",
            reason="history_fixture",initiated_by=99)
        connection.commit()
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=RecordedAdmissionGateway())

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


def test_browser_turn_close_lock_order_and_late_turn(product_db):
    """Real competing connections: expiry owns Cycle while the turn waits for it."""
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    import time
    from Api.m5_scenario_runtime import submit_turn
    from Api.m5_rule_engine import ControlledSemanticAdapter, ControlledCharacterAdapter
    factory=product_db
    with factory() as c:
        started=start_or_resume(c,user_id=99,key='race-start')
        cycle=str(started['plan']['cycle_id']);as_id=str(started['decision']['assessment_situation_id']);c.commit()
    pids=Queue()
    def submit():
        with factory() as c:
            pids.put(c.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'])
            try:
                submit_turn(c,assessment_situation_id=as_id,request_id='racing-turn',turn_id=str(uuid4()),content='synthetic',
                            semantic_adapter=ControlledSemanticAdapter({}),character_adapter=ControlledCharacterAdapter({}))
                c.commit();return 'accepted'
            except ValueError as exc:
                c.rollback();return str(exc)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with factory() as closer:
            closer.execute('SELECT id FROM m5_cycles WHERE cycle_id=%s FOR UPDATE',(cycle,))
            future=pool.submit(submit);pid=pids.get(timeout=5)
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                waiting=closer.execute('SELECT cardinality(pg_blocking_pids(%s)) AS n',(pid,)).fetchone()['n']
                if waiting:break
                time.sleep(.01)
            assert waiting, 'Turn did not reach the held Cycle lock'
            complete(closer,cycle_id=cycle,key='race-close',action='complete',reason='synthetic race',initiated_by=99)
            closer.commit()
        assert future.result(timeout=5)=='M7_COLLECTION_CLOSED'
    with factory() as c:
        assert c.execute('SELECT count(*) AS n FROM m5_dialogue_turns').fetchone()['n']==0
        assert c.execute("SELECT count(*) AS n FROM m5_c45_handoffs WHERE mode='final'").fetchone()['n']==1
