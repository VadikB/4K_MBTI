"""Owned SQL contract test, NOT a paid PATH or new human/methodology admission.

The nine unchanged Cases reuse published source QA. Program/plan approval and
generation/tester/challenger are explicitly SYNTHETIC boundary substitutions.
The actual planner, snapshots, SQL lineage, start/time and AS presentation execute.
"""
import json
from types import SimpleNamespace

import pytest

from Api import assessment_programs, participant_profile
from Api.assessment_start_readiness import read as start_readiness
from Api.assessment_start_readiness import require as real_start_requirement
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import publish_catalog
from Api.m5_cycle_runtime import read_cycle
from Api.m5_runtime_rules import import_runtime_rule_version
from Api.m5_storage import import_package, prepare_assessment_situation
from Api.m7_cycle_planner import read_plan
from Api.m7_planning_repository import attach_prepared_as
from Api.m10_product_flow import prepare, start_prepared
from Api.pilot_plan_admission import ROOT, validate_snapshot
from Api.schemas import PersonalizedProfileSelection
from scripts.build_m5_sales_package import build_execution_rules
from scripts.plan_specialist_program_release import build_admitted_materials, PACKAGE_DIR
from tests.integration.test_m10_product_path_db import product_db  # noqa: F401; reused isolated fixture
from tests.unit.test_assessment_start_readiness import functional_trace
from tests.unit.test_pilot_plan_admission import snapshot, seal

pytestmark = pytest.mark.integration


@pytest.fixture
def pilot_db(product_db, monkeypatch):
    # Undo the old component fixture's explicitly synthetic upstream permission:
    # all new SQL/HTTP tests below execute the actual product admission gate.
    monkeypatch.setattr("Api.assessment_start_readiness.require", real_start_requirement)
    def no_provider(*args, **kwargs):
        raise AssertionError("SYNTHETIC_SQL_CONTRACT_MUST_NOT_CALL_PROVIDER")
    monkeypatch.setattr("Api.llm.deepseek_gateway.DeepSeekGateway.chat", no_provider)
    with product_db() as c:
        source = json.loads((ROOT / "tests/browser/fixtures/path-start-release.json").read_bytes())
        package, runtime, _ = build_admitted_materials(source["catalog"]["decision_basis"])
        imported = import_package(c, package=package,
            manifest=json.loads((PACKAGE_DIR / "manifest.json").read_bytes()),
            execution_rules=json.loads((PACKAGE_DIR / "execution-rules.json").read_bytes()))
        runtime_row = import_runtime_rule_version(c, runtime, build_execution_rules(package["cases"], runtime["bindings"]))
        cases = c.execute("SELECT * FROM m5_case_versions WHERE package_id=%s ORDER BY case_id",
                          (imported["package_db_id"],)).fetchall()
        for row, original in zip(cases, source["cases"], strict=True):
            assert row["content_checksum"] == original["content_checksum"]
            for evidence in original["qa_evidence"]:
                c.execute("""INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
                    VALUES(%s,%s,%s,%s::jsonb,%s)""", (row["id"], evidence["scope"], evidence["result"],
                        json.dumps(evidence["evidence_json"]), evidence["evidence_checksum"]))
        catalog = publish_catalog(c, catalog_id="synthetic-pilot-start-contract", catalog_version="1.0",
            package_db_id=imported["package_db_id"], case_version_ids=[row["id"] for row in cases],
            usage_scope="assessment", organization_id=10, published_by=99,
            decision_basis="SYNTHETIC SQL contract only; not a publication outside owned test DB",
            idempotency_key="synthetic-pilot-start", runtime_rule_version_id=runtime_row["id"])
        c.execute("ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT")
        c.execute("ALTER TABLE assessment_configurations ADD COLUMN is_default BOOLEAN DEFAULT TRUE")
        c.execute("ALTER TABLE assessment_configurations ADD COLUMN scenario_version_id BIGINT DEFAULT 1")
        c.execute("ALTER TABLE assessment_configurations ADD COLUMN prompt_bundle_checksum TEXT DEFAULT 'synthetic-prompt'")
        c.execute("UPDATE assessment_configurations SET catalog_version_id=%s WHERE id=1", (catalog["catalog_db_id"],))
        role = c.execute("""SELECT v.* FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code='specialist_expert'""").fetchone()
        org = c.execute("SELECT organization_context_version_id FROM assessment_personalized_profiles LIMIT 1").fetchone()
        profile = participant_profile.confirm(c, user_id=99,
            selection=PersonalizedProfileSelection(organization_context_version_id=org["organization_context_version_id"],
                role_profile_version_id=role["id"], assessment_configuration_id=1),
            full_name="Synthetic SQL participant", position="", duties="")
        profile_id = profile["id"]
        c.execute("""CREATE TABLE organization_assessment_assignments(id BIGINT PRIMARY KEY,organization_id BIGINT,
            recipient_user_id BIGINT,assignment_ref TEXT,status TEXT,revoked_at TIMESTAMP,created_by_user_id BIGINT)""")
        c.execute("INSERT INTO organization_assessment_assignments VALUES(41,10,99,'ctx01-synthetic','active',NULL,99)")
        c.execute("""CREATE TABLE questionnaire_response_revisions(id BIGINT PRIMARY KEY,organization_id BIGINT,
            assignment_ref TEXT,status TEXT,organization_context_version_id BIGINT)""")
        c.execute("INSERT INTO questionnaire_response_revisions VALUES(21,10,'ctx01-synthetic','confirmed',%s)",
                  (org["organization_context_version_id"],))
        c.execute("""CREATE TABLE organization_assessment_source_bindings(id BIGINT PRIMARY KEY,assignment_id BIGINT,
            questionnaire_revision_id BIGINT,assessment_configuration_id BIGINT,role_profile_version_id BIGINT,
            assigned_by_user_id BIGINT)""")
        c.execute("INSERT INTO organization_assessment_source_bindings VALUES(31,41,21,1,%s,99)", (role["id"],))
        c.execute("ALTER TABLE participant_acquaintance_confirmations ADD COLUMN questionnaire_revision_id BIGINT")
        c.execute("UPDATE participant_acquaintance_confirmations SET personalized_profile_id=%s,questionnaire_revision_id=21",
                  (profile_id,))
        c.execute("""CREATE TABLE product_cycle_preparation_operations(id BIGSERIAL PRIMARY KEY,operation_id TEXT,
            user_id BIGINT,status TEXT,request_json JSONB,result_json JSONB,created_at TIMESTAMP DEFAULT NOW())""")
        assessment_programs.ensure_schema(c)
        s = snapshot()
        p = s["review"]["payload"]
        p.update(proposal_id="SYNTHETIC-SQL-PILOT-NOT-HUMAN-ADMISSION")
        p["configuration"].update(id=1, code="synthetic", methodology_version_id=1, scenario_version_id=1,
                                    catalog_version_id=catalog["catalog_db_id"], prompt_bundle_checksum="synthetic-prompt")
        p["catalog_ref"].update(id=catalog["catalog_db_id"], catalog_id="synthetic-pilot-start-contract",
                              manifest_checksum=catalog["manifest_checksum"])
        p["role_refs"][0].update(id=role["id"], version=role["version"], checksum=role["checksum"])
        baseline = p["program"]
        baseline.update(id=0, code="synthetic-pilot", version="1.0", name="Synthetic SQL pilot",
                        assignment_ref="ctx01-synthetic", assessment_configuration_id=1,
                        catalog_version_id=catalog["catalog_db_id"], source_refs_json={
                            "methodology_version_id": 1, "scenario_version_id": 1, "prompt_bundle_checksum": "synthetic-prompt"})
        review_checksum = checksum(p)
        s["review"]["proposal_payload_checksum"] = review_checksum
        owner = s["owner_decision"]
        owner.update(kind="SYNTHETIC_PLAN_ACCEPTANCE_FIXTURE_NOT_HUMAN_REVIEW",
                     decision_id="SYNTHETIC-SQL-PM", human_owner="Synthetic accepting-role boundary fixture",
                     proposal_id=p["proposal_id"], proposal_payload_checksum=review_checksum,
                     reviewed_files_sha256={"synthetic:review": review_checksum})
        owner["origin"]["user_reply_verbatim"] = "SYNTHETIC ONLY; NOT USER APPROVAL"
        s["source_files"] = {"synthetic:review": review_checksum}
        s["artifact_id"] = "synthetic-sql-pilot"
        s["source_manifest_sha256"] = checksum({"kind": "SYNTHETIC_SQL_SOURCE_NOT_RELEASE"})
        s["owner_decision_ref"] = {"path": "synthetic:owner-decision", "sha256": checksum(owner),
                                   "content_checksum": checksum(owner)}
        seal(s)
        validate_snapshot(s)
        sources = {**baseline["source_refs_json"], "pilot_plan_admission": s}
        value = {**baseline, "version": "1.1", "source_refs_json": sources}
        program_checksum = assessment_programs.definition_checksum(code=value["code"], version=value["version"],
            name=value["name"], assignment_ref=value["assignment_ref"], mode=value["mode"], configuration_id=1,
            role_version_ids=[role["id"]], catalog_version_id=catalog["catalog_db_id"], source_refs=sources)
        program_id = c.execute("""INSERT INTO assessment_program_definitions(code,version,name,assignment_ref,mode,
            status,assessment_configuration_id,catalog_version_id,source_refs_json,definition_checksum)
            VALUES(%s,%s,%s,%s,%s,'draft',1,%s,%s::jsonb,%s) RETURNING id""",
            (value["code"], value["version"], value["name"], value["assignment_ref"], value["mode"],
             catalog["catalog_db_id"], json.dumps(sources), program_checksum)).fetchone()["id"]
        c.execute("INSERT INTO assessment_program_allowed_roles VALUES(%s,%s,0)", (program_id, role["id"]))
        c.execute("UPDATE assessment_program_definitions SET status='published' WHERE id=%s", (program_id,))
        assessment_programs.connect(c, organization_id=10, program_definition_id=program_id,
                                    actor_user_id=99, operation_id="synthetic-connect")
        # Same operation and a second operation selecting the current program
        # must not reset published timing or create redundant revisions.
        revision_count = c.execute("SELECT count(*) AS n FROM m7_parameter_revisions").fetchone()['n']
        for operation_id in ('synthetic-connect', 'synthetic-connect-again'):
            assessment_programs.connect(c, organization_id=10, program_definition_id=program_id,
                                        actor_user_id=99, operation_id=operation_id)
            assert c.execute("SELECT count(*) AS n FROM m7_parameter_revisions").fetchone()['n'] == revision_count
        revision = c.execute("SELECT * FROM m7_parameter_revisions WHERE source_scope='program' AND status='published'").fetchone()
        assert revision['organization_id'] == 10 and revision['assessment_configuration_id'] == 1
        assert revision['created_by'] == 99
        assert revision['values_json'] == {'time_budget_seconds': 7200, 'calendar_window_seconds': 259200}
        c.commit()
        row = dict(c.execute("SELECT * FROM assessment_personalized_profiles WHERE id=%s", (profile_id,)).fetchone())
        scope = {"personalized_profile_id": profile_id, "profile_checksum": row["checksum"],
                 "organization_id": 10, "assignment_ref": "ctx01-synthetic", "questionnaire_revision_id": 21}
        monkeypatch.setattr("Api.acquaintance.preparation_scope", lambda *a, **kw: dict(scope))
        prepared = prepare(c, user_id=99, key="synthetic-prepare", profile_id=profile_id, exact_profile=True, defer_as=True)
        cid = str(prepared["plan"]["cycle_id"])
        decision = prepared["decision"]
        case = next(row for row in cases if row["case_id"] == decision["selected_case_id"])
        case_value = case["content_json"]
        from uuid import uuid4
        trace = functional_trace(warning=True)
        trace["accepted_as"] = {"CaseID": case["case_id"], "CaseVersion": case["case_version"]}
        from Api.m5_functional_generation_service import checksum as candidate_checksum
        trace.update(schema_version=2, candidate_checksum=candidate_checksum(trace["accepted_as"]),
                     compiled_case_checksum=case["content_checksum"], source_snapshot={
                         "profile_checksum": row["checksum"], "refs": {"case": {"case_version_checksum": case["content_checksum"]}}})
        trace["generation_operation"]["operation_id"] = "synthetic:generation"
        as_value = prepare_assessment_situation(c, assessment_situation_id=str(uuid4()),
            case_id=case["case_id"], case_version=case["case_version"], personalized_profile_id=profile_id,
            cycle_db_id=decision["cycle_db_id"], session_db_id=decision["session_db_id"], substitutions=[],
            policy=json.loads((ROOT / "assessment_definitions/cases/competencies_4k/1.1/admission-policy.json").read_bytes()), usage_scope="assessment",
            case_value_override=case_value, runtime_rules_override=build_execution_rules(package["cases"], runtime["bindings"]),
            generation_trace=trace)
        attach_prepared_as(c, decision["id"], as_value["id"])
        c.execute("""INSERT INTO product_cycle_preparation_operations(operation_id,user_id,status,request_json,result_json)
            VALUES('synthetic',99,'completed',%s::jsonb,%s::jsonb)""",
            (json.dumps(scope), json.dumps({"plan": {"cycle_id": cid}})))
        c.commit()
    yield product_db, cid, profile_id, int(program_id)


def test_unapproved_legacy_limited_cannot_bypass_start_via_compatibility(product_db, monkeypatch):
    monkeypatch.setattr("Api.assessment_start_readiness.require", real_start_requirement)
    with product_db() as c:
        prepared = prepare(c, user_id=99, key="unapproved-legacy")
        cid = str(prepared["plan"]["cycle_id"])
        assert prepared["plan"]["plan"]["status"] == "LIMITED"
        with pytest.raises(ValueError, match="M7_START_NOT_ADMITTED:PILOT_PLAN_"):
            start_prepared(c, user_id=99, cycle_id=cid, key="no-legacy-bypass")
        assert read_cycle(c, cid)["started_at"] is None


def test_exact_limited_plan_reaches_explicit_start_same_as_and_zero_answers(pilot_db, tmp_path):
    factory, cid, _, _ = pilot_db
    with factory() as c:
        plan = read_plan(c, cid)
        assert plan["plan"]["status"] == "LIMITED"
        assert len(plan["plan"]["full_target_set"]) == 61
        assert len(plan["plan"]["planned_target_set"]) == 39
        assert len(plan["plan"]["outside_plan_target_ids"]) == 22
        ready = start_readiness(c, cycle_id=cid, user_id=99)
        assert ready["can_start"] is True, ready
        before = read_cycle(c, cid)
        assert before["started_at"] is None and before["consumed_seconds"] == 0
        started = start_prepared(c, user_id=99, cycle_id=cid, key="synthetic-start")
        assert str(started["decision"]["assessment_situation_id"]) == ready["assessment_situation_id"]
        assert started["presentation"]["status"] == "active"
        assert read_cycle(c, cid)["started_at"] is not None
        assert start_readiness(c, cycle_id=cid, user_id=99)["can_start"] is False
        assert c.execute("""SELECT count(*) AS n FROM m5_dialogue_turns turn JOIN m5_assessment_situations s
            ON s.id=turn.assessment_situation_db_id WHERE s.cycle_db_id=%s AND turn.speaker_type='assessee'""",
            (before["id"],)).fetchone()["n"] == 0
        proof = {"result": "PASS_SYNTHETIC_SQL_NOT_PATH_NOT_LLM_ADMISSION",
                 "scope": "owned test/pytest database; synthetic plan acceptance and LLM stage records",
                 "new_provider_calls": 0, "full_m2": 61, "planned_targets": 39, "outside_plan": 22,
                 "before_start": ready, "before_started_at": before["started_at"],
                 "after_started_at": str(read_cycle(c, cid)["started_at"]),
                 "presented_as": str(started["decision"]["assessment_situation_id"]),
                 "assessment_answers": 0}
        (tmp_path / "server-readback.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
        c.commit()


def test_readiness_has_no_bootstrap_or_schema_writes(pilot_db):
    factory, cid, _, _ = pilot_db
    with factory() as c:
        c.execute("SET TRANSACTION READ ONLY")
        ready = start_readiness(c, cycle_id=cid, user_id=99)
        assert ready["can_start"] is True, ready


def test_two_concurrent_explicit_starts_present_once_without_resetting_time(pilot_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    factory, cid, _, _ = pilot_db
    barrier = Barrier(2)

    def start(key):
        with factory() as c:
            barrier.wait(timeout=10)
            result = start_prepared(c, user_id=99, cycle_id=cid, key=key)
            current = c.execute("SELECT started_at FROM m5_cycles WHERE cycle_id=%s", (cid,)).fetchone()
            c.commit()
            as_id = ((result.get("decision") or {}).get("assessment_situation_id")
                     or result["presentation"]["assessment_situation_id"])
            return str(as_id), current["started_at"]

    with ThreadPoolExecutor(max_workers=2) as workers:
        left = workers.submit(start, "synthetic-tab-a")
        right = workers.submit(start, "synthetic-tab-b")
        assert left.result(timeout=30) == right.result(timeout=30)
    with factory() as c:
        assert c.execute("""SELECT count(*) AS n FROM m5_cycle_time_intervals
            WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s) AND interval_type='collecting'""",
            (cid,)).fetchone()["n"] == 1


def test_real_sql_revocation_scope_and_publication_fail_closed_before_start(pilot_db):
    factory, cid, _, program_id = pilot_db
    with factory() as c:
        assert start_readiness(c, cycle_id=cid, user_id=99)["can_start"] is True
        for sql, params in [
            ("UPDATE organization_assessment_assignments SET status='revoked',revoked_at=NOW() WHERE id=41", ()),
            ("UPDATE organization_assessment_program_connections SET is_current=FALSE WHERE program_definition_id=%s", (program_id,)),
            ("UPDATE assessment_program_definitions SET status='retired' WHERE id=%s", (program_id,)),
            ("UPDATE questionnaire_response_revisions SET status='draft' WHERE id=21", ()),
            ("UPDATE product_cycle_preparation_operations SET status='failed'", ()),
            ("UPDATE m7_parameter_revisions SET status='retired' WHERE source_scope='program'", ()),
        ]:
            c.execute("SAVEPOINT negative")
            c.execute(sql, params)
            ready = start_readiness(c, cycle_id=cid, user_id=99)
            assert ready["can_start"] is False and ready["reasons"], (sql, ready)
            with pytest.raises(ValueError):
                start_prepared(c, user_id=99, cycle_id=cid, key="synthetic-denied")
            assert read_cycle(c, cid)["started_at"] is None
            c.execute("ROLLBACK TO SAVEPOINT negative")
        assert start_readiness(c, cycle_id=cid, user_id=99)["can_start"] is True


def test_http_start_uses_same_sql_decision_and_does_not_expose_review_material(pilot_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from Api import routes
    factory, cid, _, _ = pilot_db
    monkeypatch.setattr(routes, "get_connection", factory)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id=99) if token == "synthetic-owner" else None)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        request = {"cycle_id": cid, "idempotency_key": "synthetic-http-start"}
        assert client.post("/users/assessment/cycles/start", json=request).status_code == 401
        client.cookies.set(routes.SESSION_COOKIE_NAME, "synthetic-owner")
        with factory() as c:
            ready = start_readiness(c, cycle_id=cid, user_id=99)
            assert ready["can_start"] is True
            c.execute("UPDATE organization_assessment_assignments SET status='revoked' WHERE id=41")
            c.commit()
        refused = client.post("/users/assessment/cycles/start", json=request)
        assert refused.status_code == 409
        with factory() as c:
            assert read_cycle(c, cid)["started_at"] is None
            c.execute("UPDATE organization_assessment_assignments SET status='active' WHERE id=41")
            c.commit()
        started = client.post("/users/assessment/cycles/start", json=request)
        assert started.status_code == 201, started.text
        assert started.json()["runtime"]["current_situation"]["assessment_situation_id"] == ready["assessment_situation_id"]
        assert "pilot_plan_binding" not in started.text
        assert "observation_occurrences" not in started.text
        assert "SYNTHETIC ONLY; NOT USER APPROVAL" not in started.text
        repeated = client.post("/users/assessment/cycles/start", json=request)
        assert repeated.status_code == 201
        assert repeated.json()["runtime"]["current_situation"]["assessment_situation_id"] == ready["assessment_situation_id"]
