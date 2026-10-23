from contextlib import contextmanager
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
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
from tests.m6_admission_fixture import RecordedAdmissionGateway
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
        connection.execute("""CREATE TABLE product_cycle_preparation_operations (
            id BIGSERIAL PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE,
            user_id BIGINT NOT NULL REFERENCES users(id), request_json JSONB NOT NULL,
            request_checksum TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0, result_json JSONB, error_code TEXT,
            error_message TEXT, worker_id TEXT, locked_at TIMESTAMP,
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


def test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases(product_db, monkeypatch):
    with product_db() as connection:
        package = json.loads((FUNCTIONAL_OUTPUT / "case-package.json").read_text())
        manifest = json.loads((FUNCTIONAL_OUTPUT / "manifest.json").read_text())
        legacy_rules = json.loads((FUNCTIONAL_OUTPUT / "execution-rules.json").read_text())
        runtime_package = FUNCTIONAL_OUTPUT.parent.parent / "functional-personalization-runtime/1.0.0"
        loaded = load_runtime_rule_package(runtime_package, package["cases"])
        fixture_package = copy.deepcopy(package)
        fixture_bindings = copy.deepcopy(loaded)
        for case in fixture_package["cases"]:
            case["status"] = "FROZEN"
            case["author_case"]["Status"] = "FROZEN"
            fixture_bindings["bindings"]["case_bindings"][case["case_id"]]["case_checksum"] = checksum(case)
        # Only the isolated fixture simulates completed human admission. Repository
        # package/runtime artifacts remain unchanged WORKING/draft sources.
        imported = import_package(connection, package=fixture_package, manifest=manifest, execution_rules=legacy_rules)
        runtime = import_runtime_rule_version(connection, fixture_bindings,
            build_execution_rules(fixture_package["cases"], fixture_bindings["bindings"]))
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
            worker_id TEXT,locked_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW(),updated_at TIMESTAMP DEFAULT NOW(),completed_at TIMESTAMP)""")
        connection.commit()

    class FunctionalGateway:
        enabled = True
        def chat_with_trace(self, messages, **kwargs):
            payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
            if ":generation:" in kwargs["routing_key"]:
                content = json.dumps(payload["author_as_example"], ensure_ascii=False)
            else:
                required = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
                content = json.dumps({"checks": [{"check_id": item["check_id"], "status": "PASS",
                        "reason": "isolated functional Cycle fixture", "evidence_paths": [], "findings": [],
                        "adversarial_review": {"candidate_conflicts": [], "resolution": "fixture"}}
                        for item in required]}, ensure_ascii=False)
            return SimpleNamespace(content=content, sent={}, provider={"finish_reason": "stop"})

    monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", product_db)
    monkeypatch.setattr("Api.llm.deepseek_gateway.DeepSeekGateway", FunctionalGateway)
    queue = ProductCyclePreparationQueue()
    request = {"personalized_profile_id": specialist_profile["id"], "idempotency_key": "functional-cycle",
               "selected_skills": ["K1", "K2", "K3", "K4"]}
    queue.enqueue(operation_id="functional-cycle", user_id=99, request=request)
    queue._process(queue._claim())
    operation = queue.get_status("functional-cycle")
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
        situation = connection.execute("""SELECT s.snapshot_json,s.execution_payload_json
            FROM m5_assessment_situations s JOIN m7_route_assignments a ON a.assessment_situation_db_id=s.id
            WHERE a.decision_id=%s""", (decision["id"],)).fetchone()
        assert situation["snapshot_json"]["case_ref"]["id"].startswith("CASE.SPEC.")
        generated_ref = situation["execution_payload_json"]["runtime_rule_ref"]
        generated_trace = situation["execution_payload_json"]["ai_operations"]["functional_personalization"]
        assert generated_ref == {"source": "functional_generation",
                                 "candidate_checksum": generated_trace["candidate_checksum"]}
        assert generated_trace["admitted_for_participant"] is True
        assert generated_trace["schema_version"] == 2
        assert functional_checksum(generated_trace["accepted_as"]) == generated_trace["candidate_checksum"]
        assert generated_trace["tester_input_checksum"] == generated_trace["tester"]["provider_operation"]["input_checksum"]
        assert generated_trace["source_snapshot"]["author_as_example"]["CaseID"] == decision["selected_case_id"]
        assert generated_trace["source_snapshot"]["profile_checksum"] == situation["snapshot_json"]["profile_ref"]["checksum"]
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
    with product_db() as connection:
        start_prepared(connection, user_id=99, cycle_id=cycle_id, key="functional-cycle-start")
        submit_turn(connection, assessment_situation_id=first_as,
                    request_id="functional-cycle-turn", turn_id=str(uuid4()),
                    content="Контролируемый ответ для перехода ко второй ситуации.",
                    semantic_adapter=Semantic(), character_adapter=Character())
        transition(connection, assessment_situation_id=first_as, action="scenario_end",
                   reason="regression", request_id="functional-cycle-end")
        finish_current_situation(connection, cycle_id=cycle_id, key="functional-cycle-finish", initiated_by=99)
        connection.commit()

    second_operation = "functional-cycle-next"
    queue.enqueue(operation_id=second_operation, user_id=99, request={
        "kind": "next", "cycle_id": cycle_id, "idempotency_key": second_operation,
    })
    queue._process(queue._claim())
    second = queue.get_status(second_operation)
    assert second["status"] == "completed", second
    assert second["result_json"]["decision"]["assessment_situation_id"] != first_as
    with product_db() as connection:
        second_payload = connection.execute(
            "SELECT execution_payload_json FROM m5_assessment_situations WHERE assessment_situation_id=%s",
            (second["result_json"]["decision"]["assessment_situation_id"],),
        ).fetchone()["execution_payload_json"]
        second_trace = second_payload["ai_operations"]["functional_personalization"]
        assert second_trace["schema_version"] == 2
        assert functional_checksum(second_trace["accepted_as"]) == second_trace["candidate_checksum"]
        assert second_trace["source_snapshot"]["author_as_example"]["CaseID"] == \
            second["result_json"]["decision"]["selected_case_id"]


def test_inter_case_break_closes_only_current_as_and_resumes_on_explicit_next(product_db):
    with product_db() as connection:
        started = start_or_resume(connection, user_id=99, key="w02-inter-case")
        cycle_id = str(started["plan"]["cycle_id"])
        first_as = str(started["decision"]["assessment_situation_id"])
        _add_turn(connection, first_as, "Синтетический ответ первой ситуации", "w02-inter-case-turn")
        transition(
            connection, assessment_situation_id=first_as, action="scenario_end",
            reason="participant_completed", request_id="w02-inter-case-scenario-end",
        )

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
