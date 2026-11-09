"""L1–L8: real queue, gateway and owner HTTP on an isolated owned PG.

Only identity lookup and upstream human permission/admission are synthetic.
Provider transport is local and deterministic; production queue/domain code runs.
"""
from __future__ import annotations
import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from Api import routes, m10_product_flow
from Api.llm import deepseek_gateway as gateway_module
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.m5_case_runtime import checksum
from Api.m5_functional_generation_service import checksum as functional_checksum
from Api.m5_catalog_integrity import publication_plan, publish_catalog
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
from Api.m5_storage import import_package
from Api.schemas import PersonalizedProfileSelection
from Api import participant_profile
from Api.product_cycle_preparation_queue import ProductCyclePreparationQueue, public_operation
from scripts.build_m5_functional_package import OUTPUT as FUNCTIONAL_OUTPUT
from scripts.build_m5_sales_package import build_execution_rules
from tests.integration.test_m10_product_path_db import product_db, _add_turn
from tests.conftest import test_database_url as configured_database_url
from Api.m5_scenario_runtime import transition
from Api.m7_completion import finish_current_situation

pytestmark = pytest.mark.integration


@pytest.fixture
def test_database_url(configured_database_url, tmp_path):
    """CI and local runs both obtain marker-owned resources without shared writes."""
    import os
    import subprocess
    import sys
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from scripts.test_stand import admin_params
    with psycopg.connect(configured_database_url) as c:
        marker = c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
    if str(marker or "").startswith("stand-10.2:"):
        yield configured_database_url
        return
    admin_params(configured_database_url)
    root = Path(__file__).resolve().parents[2]
    state_path = tmp_path / "exec02-owned-state.json"
    env = dict(os.environ, STAND_ADMIN_URL=configured_database_url, PYTHON_DOTENV_DISABLED="1", DB_POOL_MIN_SIZE="0")
    command = [sys.executable, str(root / "scripts/test_stand.py")]
    subprocess.run([*command, "create", "--state", str(state_path), "--provider", "disabled"],
                   env=env, cwd=root, check=True, capture_output=True, text=True)
    state = json.loads(state_path.read_text())
    try:
        yield make_conninfo(**{**conninfo_to_dict(configured_database_url), "dbname": state["database"]})
    finally:
        subprocess.run([*command, "destroy", "--state", str(state_path)],
                       env=env, cwd=root, check=True, capture_output=True, text=True)


def _setup(product_db):
    with product_db() as connection:
        package = json.loads((FUNCTIONAL_OUTPUT / "case-package.json").read_text())
        manifest = json.loads((FUNCTIONAL_OUTPUT / "manifest.json").read_text())
        legacy_rules = json.loads((FUNCTIONAL_OUTPUT / "execution-rules.json").read_text())
        runtime_package = FUNCTIONAL_OUTPUT.parent.parent / "functional-personalization-runtime/1.2.0"
        loaded = load_runtime_rule_package(
            runtime_package, package["cases"], expected_case_package_version="0.5"
        )
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
            worker_id TEXT,attempt_token UUID,locked_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW(),updated_at TIMESTAMP DEFAULT NOW(),completed_at TIMESTAMP)""")
        connection.commit()
    return specialist_profile["id"]


class TechnicalTransport:
    def __init__(self):
        self.slots = threading.BoundedSemaphore(1)
        self.sent = 0
        self.mode = "success"
        self.tester_outcome = None

    def urlopen(self, req, **_kwargs):
        self.sent += 1
        messages = json.loads(req.data)["messages"]
        payload = json.loads(next(x["content"] for x in reversed(messages) if x["role"] == "user"))
        if "author_as_example" in payload and "protected_checks" not in payload and "applicability_plan" not in payload:
            candidate = copy.deepcopy(payload["author_as_example"])
            materials = [x["MaterialID"] for x in candidate["Материалы"]]
            events = [x["EventID"] for x in candidate["События"]]
            characters = [x["CharacterID"] for x in candidate["Активные персонажи"]]
            for index, target in enumerate(candidate["IndicatorObservability"]):
                target.update(material_refs=materials[:1], event_refs=events[:1], character_refs=characters[:1],
                    authority_refs=["participant"], author_mapping={"source_pointer": f"/IndicatorObservability/{index}",
                    "source_checksum": functional_checksum(payload["author_as_example"]["IndicatorObservability"][index])})
            content = candidate
        else:
            required = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
            content = {"candidate_checksum": payload.get("candidate_checksum"), "checks": [
                {"check_id": x["check_id"], "status": self.tester_outcome or "PASS", "reason": "synthetic provider",
                 "evidence_paths": [], "findings": [],
                 "adversarial_review": {"candidate_conflicts": [], "resolution": "fixture"}} for x in required]}
        body = {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}, "finish_reason": "stop"}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return json.dumps(body).encode()
        return Response()


@pytest.fixture
def retry_env(product_db, monkeypatch):
    # A random schema alone does not prove database ownership.
    with product_db() as c:
        marker = c.execute("SELECT shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()").fetchone()["marker"]
        assert marker.startswith("stand-10.2:")
    profile = _setup(product_db)
    transport = TechnicalTransport()
    def gateway(**kwargs):
        client = DeepSeekGateway(api_keys=[] if transport.mode == "credentials" else ["synthetic-key"], **kwargs)
        client.request_slots = transport.slots
        return client
    monkeypatch.setattr(gateway_module, "DeepSeekGateway", gateway)
    monkeypatch.setattr(gateway_module.settings, "deepseek_queue_timeout_seconds", 0.001)
    monkeypatch.setattr(gateway_module, "pause_thread_connections_for_external_io", lambda: 0)
    monkeypatch.setattr(gateway_module.request, "urlopen", transport.urlopen)
    monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", product_db)
    monkeypatch.setattr(routes, "get_connection", product_db)
    monkeypatch.setattr(routes.acquaintance, "preparation_scope", lambda *a, **k: None)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
        lambda token: SimpleNamespace(id=99) if token == "exec02-owner" else SimpleNamespace(id=100) if token else None)
    queue = ProductCyclePreparationQueue()
    monkeypatch.setattr(routes, "product_cycle_preparation_queue", queue)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME, "exec02-owner")
        yield SimpleNamespace(db=product_db, profile=profile, transport=transport, queue=queue, http=http, app=app)


def _post(env, key, cycle=None):
    url = f"/users/assessment/m7/cycles/{cycle}/next" if cycle else "/users/assessment/cycles/prepare"
    body = {"idempotency_key": key}
    if not cycle: body.update(personalized_profile_id=env.profile, selected_skills=["K1", "K2", "K3", "K4"])
    return env.http.post(url, json=body)


def _process(env):
    job = env.queue._claim(); assert job
    env.queue._process(job)
    return job, env.queue.get_status(job["operation_id"])


def _close(env, cycle, as_id):
    with env.db() as c:
        _add_turn(c, as_id, "Сохранённый синтетический ответ", "answer-"+as_id)
        transition(c, assessment_situation_id=as_id, action="scenario_end", reason="synthetic lifecycle", request_id="end-"+as_id)
        finish_current_situation(c, cycle_id=cycle, key="close-"+as_id, initiated_by=99)


def _first(env):
    assert _post(env, "first").status_code == 202
    _, result = _process(env)
    assert result["status"] == "completed", result
    cycle = result["result_json"]["plan"]["cycle_id"]
    first_as = result["result_json"]["decision"]["assessment_situation_id"]
    with env.db() as c:
        m10_product_flow.start_prepared(c, user_id=99, cycle_id=cycle, key="start")
    return cycle, first_as


def test_first_next_capacity_recovery_and_concurrent_retry_fencing(retry_env, tmp_path):
    env = retry_env
    evidence = []
    cycle = None
    for kind in ("first", "next"):
        if kind == "next":
            _close(env, cycle, first_as)
            with env.db() as c:
                frozen_plan = c.execute("SELECT content_checksum FROM m7_plan_revisions WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)", (cycle,)).fetchone()["content_checksum"]
                c.execute("UPDATE assessment_configurations SET catalog_version_id=NULL WHERE id=1")
        env.transport.slots.acquire()
        sent_before = env.transport.sent
        response = _post(env, kind+"-overload", cycle)
        assert response.status_code in (201,202), response.text
        old_job, failed = _process(env)
        assert failed["error_code"] == "LlmCapacityError", failed
        assert env.transport.sent == sent_before
        public = env.http.get("/users/assessment/cycles/preparation/"+old_job["operation_id"]).json()
        assert public["retry_allowed"] is True
        assert "synthetic-key" not in str(public)
        if cycle:
            runtime = env.http.get(f"/users/assessment/cycles/{cycle}/runtime").json()
            assert runtime["preparation_operation"] == public
        env.transport.slots.release()
        if kind == "first":
            with env.db() as c:
                c.execute("UPDATE assessment_configurations SET catalog_version_id=NULL WHERE id=1")
        # Two genuinely concurrent commands, not sequential duplicate calls.
        with ThreadPoolExecutor(2) as workers:
            retried = list(workers.map(lambda key: _post(env, key, cycle), [kind+"-retry-a", kind+"-retry-b"]))
        assert all(x.status_code in (201,202) for x in retried), [x.text for x in retried]
        assert retried[0].json()["operation_id"] == retried[1].json()["operation_id"]
        new_job = env.queue._claim(); assert new_job
        # Real lease reclaim: old worker must not apply even after replacement completes.
        with env.db() as c:
            c.execute("UPDATE product_cycle_preparation_operations SET locked_at=NOW()-INTERVAL '11 minutes' WHERE id=%s", (new_job["id"],))
        reclaimed = env.queue._claim(); assert reclaimed["attempt_token"] != new_job["attempt_token"]
        env.queue._process(reclaimed)
        completed = env.queue.get_status(reclaimed["operation_id"])
        assert completed["status"] == "completed", completed
        sent_completed = env.transport.sent
        env.queue._process(old_job); env.queue._process(new_job)
        assert env.queue.get_status(reclaimed["operation_id"]) == completed
        assert env.transport.sent == sent_completed
        assert env.queue._claim() is None
        result = completed["result_json"]
        if cycle is None:
            cycle = result["plan"]["cycle_id"]
            first_as = result["decision"]["assessment_situation_id"]
            with env.db() as c: m10_product_flow.start_prepared(c, user_id=99, cycle_id=cycle, key="start-first")
        else:
            second_as = result["decision"]["assessment_situation_id"]
            assert second_as != first_as
            with env.db() as c:
                assert c.execute("SELECT content_checksum FROM m7_plan_revisions WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)", (cycle,)).fetchone()["content_checksum"] == frozen_plan
                assert c.execute("SELECT status FROM m5_assessment_situations WHERE assessment_situation_id=%s", (first_as,)).fetchone()["status"] == "closed"
                assert c.execute("SELECT count(*) AS n FROM m5_dialogue_turns WHERE speaker_type='assessee'").fetchone()["n"] == 1
            assert _post(env, "next-replay-new-key", cycle).json()["operation_id"] == reclaimed["operation_id"]
        with env.db() as c:
            assert c.execute("SELECT count(*) AS n FROM m5_cycles").fetchone()["n"] == 1
            assert c.execute("SELECT count(*) AS n FROM m7_route_assignments").fetchone()["n"] == (1 if kind == "first" else 2)
            assert c.execute("SELECT count(*) AS n FROM m7_route_decisions WHERE status='SELECTED'").fetchone()["n"] == (1 if kind == "first" else 2)
        evidence.append({"kind": kind, "failed_projection": public, "slot_failure_sent": 0,
            "operation_id": reclaimed["operation_id"], "cycle_id": cycle,
            "as_id": result["decision"]["assessment_situation_id"], "concurrent_retry_deduplicated": True,
            "reclaimed_token_changed": True, "late_workers_no_effect": True})
    _close(env, cycle, second_as)
    third = _post(env, "third-position", cycle)
    assert third.status_code == 201 and third.json()["status"] == "queued"
    _, result = _process(env)
    assert result["status"] == "completed", result
    assert result["result_json"]["decision"]["assessment_situation_id"] not in {first_as, second_as}
    # An old key remains a historical replay, never a new position command.
    assert _post(env, "next-overload", cycle).json()["status"] == "failed"
    # Different owner cannot read/replay an operation or use this Cycle.
    env.http.cookies.set(routes.SESSION_COOKIE_NAME, "other")
    assert env.http.get("/users/assessment/cycles/preparation/first-overload").status_code == 404
    assert _post(env, "foreign-next", cycle).status_code == 403
    out = Path(__import__('os').environ.get('EXEC_FIX02_EVIDENCE', str(tmp_path))); out.mkdir(parents=True, exist_ok=True)
    (out/'pg-http-recovery.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')


@pytest.mark.parametrize("failure", ["credentials", "FAIL", "TECHNICAL_ERROR"])
def test_next_configuration_and_admission_failures_cannot_change_transport_key(retry_env, failure):
    env = retry_env; cycle, first_as = _first(env); _close(env, cycle, first_as)
    if failure == "credentials": env.transport.mode = failure
    else: env.transport.tester_outcome = failure
    initial = _post(env, "blocked-next", cycle); assert initial.status_code == 201
    _, failed = _process(env); assert failed["status"] == "failed", failed
    read = env.http.get("/users/assessment/cycles/preparation/blocked-next").json()
    assert read["retry_allowed"] is False
    assert _post(env, "blocked-next", cycle).json() == read
    assert _post(env, "new-blocked-next", cycle).status_code == 409
    with env.db() as c:
        assert c.execute("SELECT count(*) AS n FROM m5_assessment_situations").fetchone()["n"] == 1


@pytest.mark.parametrize("guard", ["terminal", "time", "membership", "assignment", "revision", "case_admission"])
def test_next_retry_rechecks_live_guards_before_provider(retry_env, guard):
    env = retry_env; cycle, first_as = _first(env); _close(env, cycle, first_as)
    env.transport.slots.acquire()
    assert _post(env, "transient-next", cycle).status_code == 201
    _, failed = _process(env); assert failed["error_code"] == "LlmCapacityError"
    env.transport.slots.release(); sent_before = env.transport.sent
    with env.db() as c:
        if guard == "terminal": c.execute("UPDATE m5_cycles SET status='collection_closed' WHERE cycle_id=%s", (cycle,))
        elif guard == "time": c.execute("UPDATE m5_cycles SET started_at=NOW()-(calendar_window_seconds+60)*INTERVAL '1 second' WHERE cycle_id=%s", (cycle,))
        elif guard == "membership": c.execute("DELETE FROM organization_memberships WHERE user_id=99")
        elif guard == "assignment":
            c.execute("CREATE TABLE organization_assessment_assignments(id BIGINT PRIMARY KEY,recipient_user_id BIGINT,status TEXT,revoked_at TIMESTAMPTZ)")
            c.execute("INSERT INTO organization_assessment_assignments VALUES(12,99,'cancelled',NOW())")
            c.execute("UPDATE m5_cycles SET assignment_id=12 WHERE cycle_id=%s", (cycle,))
        elif guard == "revision":
            # Append a real immutable plan revision, without rewriting old history.
            plan = m10_product_flow.m7_cycle_planner.read_plan(c, cycle)
            c.execute("INSERT INTO m7_plan_revisions SELECT %s,plan_id,cycle_db_id,revision_no+1,content_json,content_checksum,'synthetic revision drift',NOW() FROM m7_plan_revisions WHERE id=%s", (uuid4(),plan['revision_id']))
        else:
            selected = c.execute("SELECT cv.id FROM m7_route_decisions d JOIN m5_cycles c ON c.id=d.cycle_db_id JOIN m5_case_versions cv ON cv.case_id=d.selected_case_id AND cv.case_version=d.selected_case_version WHERE c.cycle_id=%s ORDER BY d.created_at DESC LIMIT 1", (cycle,)).fetchone()
            c.execute("INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum) VALUES(%s,'assessment_situation','FAIL','{}','synthetic-revocation')", (selected['id'],))
    read = env.http.get("/users/assessment/cycles/preparation/transient-next").json()
    assert read["retry_allowed"] is False, read
    if guard != "terminal":
        with env.db() as c:
            runtime = m10_product_flow.read_runtime(c, cycle_id=cycle)
        assert runtime["preparation_operation"] == read
    assert _post(env, "transient-next", cycle).json() == read
    assert _post(env, "new-next-after-guard", cycle).status_code == 409
    assert env.transport.sent == sent_before
    with env.db() as c:
        assert c.execute("SELECT count(*) AS n FROM m5_assessment_situations").fetchone()["n"] == 1
