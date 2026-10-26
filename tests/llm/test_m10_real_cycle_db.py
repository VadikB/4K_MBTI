from __future__ import annotations

import copy
import json
import os
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import m10_orchestration, participant_profile
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.m10_product_flow import read_runtime, start_or_resume
from Api.m5_cycle_runtime import transition_session
from Api.m5_case_runtime import checksum as runtime_checksum
from Api.m5_storage import import_package
from Api.m5_catalog_integrity import publication_plan, publish_catalog
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
from Api.m6_worker_v2 import run_request as run_evidence
from Api.m6_assessment_worker_v2 import run_request as run_assessment
from Api.m8_results import read_latest_report
from tests.integration.test_m10_product_path_db import product_db
from Api import routes
from scripts.build_m5_functional_package import OUTPUT as FUNCTIONAL_OUTPUT
from scripts.build_m5_sales_package import build_execution_rules
from Api.product_cycle_preparation_queue import ProductCyclePreparationQueue
from Api.schemas import PersonalizedProfileSelection


pytestmark = [pytest.mark.integration, pytest.mark.llm]


def _jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _saved_a06_row(row_id: str) -> dict:
    root = Path(__file__).resolve().parents[2]
    archive = root / "docs/evc/evidence/r10-matrix-9f6d958-checkpoint-2026-10-26.tar.gz"
    member = f"p4k-r10-9f6d958-pilot/rows/{row_id.lower()}.json"
    with tarfile.open(archive, "r:gz") as bundle:
        extracted = bundle.extractfile(member)
        assert extracted is not None
        return json.load(extracted)


def _install_functional_catalog(connection) -> dict:
    package = json.loads((FUNCTIONAL_OUTPUT / "case-package.json").read_text())
    manifest = json.loads((FUNCTIONAL_OUTPUT / "manifest.json").read_text())
    legacy_rules = json.loads((FUNCTIONAL_OUTPUT / "execution-rules.json").read_text())
    runtime_package = FUNCTIONAL_OUTPUT.parent.parent / "functional-personalization-runtime/1.2.0"
    bindings = load_runtime_rule_package(
        runtime_package, package["cases"], expected_case_package_version="0.5"
    )
    fixture_package = copy.deepcopy(package)
    fixture_bindings = copy.deepcopy(bindings)
    for case in fixture_package["cases"]:
        case["status"] = "FROZEN"
        case["author_case"]["Status"] = "FROZEN"
        fixture_bindings["bindings"]["case_bindings"][case["case_id"]]["case_checksum"] = \
            runtime_checksum(case)
    imported = import_package(
        connection, package=fixture_package, manifest=manifest, execution_rules=legacy_rules,
    )
    runtime = import_runtime_rule_version(
        connection, fixture_bindings,
        build_execution_rules(fixture_package["cases"], fixture_bindings["bindings"]),
    )
    cases = connection.execute(
        "SELECT * FROM m5_case_versions WHERE package_id=%s ORDER BY case_id",
        (imported["package_db_id"],),
    ).fetchall()
    for case in cases:
        for scope in ("case_format", "case_dialogue", "assessment_situation"):
            evidence = {
                "schema_version": 1, "eligibility": "user_admission", "scope": scope,
                "result": "PASS", "case_ref": {"id": case["case_id"],
                "version": case["case_version"], "checksum": case["content_checksum"]},
                "base_role": case["base_role"], "usage_scopes": ["assessment"],
                "origin": {"type": "human_review", "actor_ref": "review:r10-isolated-fixture"},
            }
            connection.execute(
                """INSERT INTO m5_qa_evidence
                   (case_version_id,scope,result,evidence_json,evidence_checksum)
                   VALUES(%s,%s,'PASS',%s::jsonb,%s)""",
                (case["id"], scope, json.dumps(evidence, ensure_ascii=False), runtime_checksum(evidence)),
            )
    plan = publication_plan(
        connection, package_db_id=imported["package_db_id"],
        case_version_ids=[int(case["id"]) for case in cases], usage_scope="assessment",
        organization_id=10, runtime_rule_version_id=runtime["id"],
    )
    assert plan["publishable"] is True, plan["decisions"]
    catalog = publish_catalog(
        connection, catalog_id="r10-functional-cycle-fixture", catalog_version="1.0",
        package_db_id=imported["package_db_id"],
        case_version_ids=[int(case["id"]) for case in cases], usage_scope="assessment",
        organization_id=10, published_by=99,
        decision_basis="isolated R10 replay of an unchanged real-provider admitted AS",
        idempotency_key="r10-functional-cycle-catalog", runtime_rule_version_id=runtime["id"],
    )
    connection.execute(
        "ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT REFERENCES m5_catalogs(id)"
    )
    connection.execute(
        "ALTER TABLE assessment_configurations ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT TRUE"
    )
    connection.execute(
        "UPDATE assessment_configurations SET catalog_version_id=%s WHERE id=1",
        (catalog["catalog_db_id"],),
    )
    specialist_role = connection.execute(
        """SELECT v.id FROM assessment_role_profile_versions v
           JOIN assessment_role_profiles r ON r.id=v.role_profile_id
           WHERE r.code='specialist_expert' AND v.status='published'"""
    ).fetchone()["id"]
    organization_context = connection.execute(
        """SELECT v.id FROM assessment_organization_context_versions v
           JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
           WHERE c.organization_id=10 AND v.status='published'"""
    ).fetchone()["id"]
    profile = participant_profile.confirm(
        connection, user_id=99,
        selection=PersonalizedProfileSelection(
            organization_context_version_id=organization_context,
            role_profile_version_id=specialist_role, assessment_configuration_id=1,
        ),
        full_name="Synthetic R10 specialist", position="", duties="",
    )
    connection.execute("""CREATE TABLE product_cycle_preparation_operations (
        id BIGSERIAL PRIMARY KEY,operation_id TEXT UNIQUE,user_id BIGINT,request_json JSONB,
        request_checksum TEXT,status TEXT DEFAULT 'queued',attempts INTEGER DEFAULT 0,
        result_json JSONB,error_code TEXT,error_message TEXT,worker_id TEXT,attempt_token UUID,
        locked_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW(),updated_at TIMESTAMP DEFAULT NOW(),
        completed_at TIMESTAMP)""")
    return {"profile": dict(profile["content"]), "profile_id": int(profile["id"]),
            "profile_checksum": profile["checksum"], "runtime_package": runtime_package}


def test_functional_c01_owner_api_reaches_m8(product_db, monkeypatch):
    """Prepare a product-valid M4 functional AS through owner HTTP and reach real M6/M8."""
    if os.getenv("RUN_REAL_CYCLE_LLM") != "1":
        pytest.skip("explicit real-provider acceptance run")
    factory = product_db
    gateway = DeepSeekGateway()
    assert gateway.enabled
    saved = _saved_a06_row("A06.C01.SALES")

    with factory() as connection:
        installed = _install_functional_catalog(connection)
        # N01 used a matrix-only synthetic projection. It is evidence for PM-03,
        # but cannot be rebound to a different immutable M4 snapshot in N02.
        assert installed["profile_checksum"] != \
            saved["persistence_trace"]["source_snapshot"]["profile_checksum"]
        connection.commit()

    from Api import product_cycle_preparation_queue as queue_module
    queue = ProductCyclePreparationQueue()
    monkeypatch.setattr(queue_module, "get_connection", factory)
    monkeypatch.setattr(routes, "product_cycle_preparation_queue", queue)
    monkeypatch.setattr(routes, "get_connection", factory)
    monkeypatch.setattr(
        routes.web_session_service, "get_user_by_token",
        lambda token: type("SyntheticUser", (), {"id": 99})() if token == "r10-functional-owner" else None,
    )
    app = FastAPI()
    app.include_router(routes.router)
    participant_turn_id = uuid4()
    participant_text = (
        "Предлагаю сначала согласовать с клиентом критерии результата и границы пилота. "
        "Я соберу исходные данные, проверю ограничения и варианты, затем оформлю сравнение "
        "с рисками и ответственными. После обратной связи зафиксируем решение, способ проверки "
        "и следующий шаг; ресурсы других команд без их подтверждения не обещаю."
    )
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME, "r10-functional-owner")
        enqueued = http.post(
            "/users/assessment/cycles/prepare",
            json={"personalized_profile_id": installed["profile_id"],
                  "idempotency_key": "r10-c01-sales-prepare",
                  "selected_skills": ["K1", "K2", "K3", "K4"]},
        )
        assert enqueued.status_code == 202, enqueued.text
        job = queue._claim()
        assert job is not None
        queue._process(job)
        preparation = http.get(
            "/users/assessment/cycles/preparation/r10-c01-sales-prepare"
        )
        assert preparation.status_code == 200, preparation.text
        operation = preparation.json()
        if operation["status"] != "completed":
            diagnostic = queue.get_status("r10-c01-sales-prepare")
            output = os.getenv("P4K_FUNCTIONAL_CYCLE_EVIDENCE_PATH")
            if output:
                path = Path(output).with_suffix(".preparation-failure.json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(_jsonable(diagnostic), ensure_ascii=False, indent=2) + "\n")
            pytest.fail(f"functional preparation failed: {diagnostic['error_code']}:{diagnostic['error_message']}")
        prepared = operation["result"]
        assert prepared["decision"]["selected_case_id"] == "CASE.SPEC.01"
        cycle_id = str(prepared["plan"]["cycle_id"])
        as_id = str(prepared["decision"]["assessment_situation_id"])
        started = http.post(
            "/users/assessment/cycles/start",
            json={"cycle_id": cycle_id, "idempotency_key": "r10-c01-sales-start"},
        )
        assert started.status_code == 201, started.text
        assert started.json()["presentation"]["assessment_situation_id"] == as_id
        turn = http.post(
            f"/users/assessment/m5/situations/{as_id}/turns",
            json={"request_id": "r10-c01-sales-turn", "turn_id": str(participant_turn_id),
                  "content": participant_text},
        )
        assert turn.status_code == 200, turn.text
        completed = http.post(
            f"/users/assessment/m7/cycles/{cycle_id}/completion",
            json={"idempotency_key": "r10-c01-sales-complete", "action": "complete",
                  "reason": "isolated_r10_functional_path"},
        )
        assert completed.status_code == 200, completed.text

    assert m10_orchestration.advance_once(connection_factory=factory, gateway=gateway)
    with factory() as connection:
        evidence_request = connection.execute(
            "SELECT id FROM m6_processing_requests ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    assert evidence_request is not None
    run_evidence(evidence_request["id"], connection_factory=factory, gateway=gateway)
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=gateway)
    with factory() as connection:
        assessment_request = connection.execute(
            "SELECT id FROM m6_assessment_requests ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        evidence_status = connection.execute(
            "SELECT status FROM m6_processing_requests WHERE id=%s", (evidence_request["id"],)
        ).fetchone()["status"]
    assert assessment_request is not None, {"evidence_status": evidence_status}
    run_assessment(assessment_request["id"], connection_factory=factory, gateway=gateway)
    assert m10_orchestration.advance_once(connection_factory=factory, gateway=gateway)

    with factory() as connection:
        report = read_latest_report(connection, cycle_id, "assessee")
        pipeline = connection.execute(
            "SELECT status,stage,error_code FROM m10_pipeline_runs"
        ).fetchone()
        evidence = connection.execute(
            """SELECT r.status,rev.output_json,a.trace_json FROM m6_processing_requests r
               LEFT JOIN m6_processing_attempts a ON a.request_id=r.id
               LEFT JOIN m6_analysis_revisions rev ON rev.request_id=r.id
               WHERE r.id=%s ORDER BY a.attempt_no DESC LIMIT 1""",
            (evidence_request["id"],),
        ).fetchone()
        assessment = connection.execute(
            """SELECT r.status,rev.output_json,a.trace_json FROM m6_assessment_requests r
               LEFT JOIN m6_assessment_attempts a ON a.request_id=r.id
               LEFT JOIN m6_assessment_revisions rev ON rev.request_id=r.id
               WHERE r.id=%s ORDER BY a.attempt_no DESC LIMIT 1""",
            (assessment_request["id"],),
        ).fetchone()
        persisted = connection.execute(
            """SELECT s.snapshot_checksum,s.execution_payload_json,cv.content_checksum
               FROM m5_assessment_situations s JOIN m5_case_versions cv ON cv.id=s.case_version_id
               WHERE s.assessment_situation_id=%s""", (as_id,),
        ).fetchone()
    assert pipeline == {"status": "ready", "stage": "report_ready", "error_code": None}
    assert evidence["status"] == "succeeded"
    assert assessment["status"] == "succeeded"
    assert report["c67"]["contract"] == "C-67"
    assert persisted["execution_payload_json"]["ai_operations"]["functional_personalization"] \
        ["admitted_for_participant"] is True

    output = os.getenv("P4K_FUNCTIONAL_CYCLE_EVIDENCE_PATH")
    if output:
        artifact = {
            "schema_version": 1,
            "scope": "product_m4_real_provider_functional_as_owner_http_to_m8",
            "n01_reference_row": saved["row"],
            "candidate_commit": os.getenv("P4K_CANDIDATE_COMMIT"),
            "synthetic_test_data": True,
            "profile_checksum": installed["profile_checksum"],
            "candidate_checksum": persisted["execution_payload_json"]["ai_operations"]
                ["functional_personalization"]["candidate_checksum"],
            "case_version_checksum": persisted["content_checksum"],
            "assessment_situation": {"id": as_id, "snapshot_checksum": persisted["snapshot_checksum"]},
            "participant_turn": {"id": str(participant_turn_id), "request_id": "r10-c01-sales-turn"},
            "m6_evidence": _jsonable(evidence),
            "m6_indicator_assessment": _jsonable(assessment),
            "m7_pipeline": _jsonable(pipeline),
            "m8_report": _jsonable(report),
            "methodological_acceptance": "NOT_RUN",
            "reliability": report["c67"]["reliability"]["status"],
        }
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")


def test_real_cycle_reaches_m8_and_preserves_return_state(product_db, monkeypatch):
    """Explicit real-provider acceptance run; excluded from the standard suite by marker."""
    if os.getenv("RUN_REAL_CYCLE_LLM") != "1":
        pytest.skip("explicit real-provider acceptance run")
    factory = product_db
    gateway = DeepSeekGateway()
    assert gateway.enabled

    with factory() as connection:
        started = start_or_resume(connection, user_id=99, key="pers-real-cycle")
        cycle_id = str(started["plan"]["cycle_id"])
        as_id = str(started["decision"]["assessment_situation_id"])
        before_pause = read_runtime(connection, cycle_id=cycle_id)
        session_id = str(connection.execute(
            """SELECT s.session_id FROM m5_cycle_sessions s
               JOIN m5_cycles c ON c.id=s.cycle_db_id
               WHERE c.cycle_id=%s ORDER BY s.ordinal DESC LIMIT 1""",
            (cycle_id,),
        ).fetchone()["session_id"])
        transition_session(
            connection, session_id=session_id, action="pause", reason="real_cycle_return_check"
        )
        paused = read_runtime(connection, cycle_id=cycle_id)
        transition_session(
            connection, session_id=session_id, action="resume", reason="real_cycle_return_check"
        )
        resumed = read_runtime(connection, cycle_id=cycle_id)
        assert paused["current_situation"]["assessment_situation_id"] == as_id
        assert resumed["current_situation"]["assessment_situation_id"] == as_id

        as_db_id = connection.execute(
            "SELECT id FROM m5_assessment_situations WHERE assessment_situation_id=%s", (as_id,)
        ).fetchone()["id"]
        participant_turn_id = uuid4()
        participant_text = "Нет."
        connection.commit()

    monkeypatch.setattr(routes, "get_connection", factory)
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda token: type("SyntheticUser", (), {"id": 99})() if token == "r10-owner" else None,
    )
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME, "r10-owner")
        turn_response = http.post(
            f"/users/assessment/m5/situations/{as_id}/turns",
            json={
                "request_id": "pers-real-cycle-turn",
                "turn_id": str(participant_turn_id),
                "content": participant_text,
            },
        )
        assert turn_response.status_code == 200, turn_response.text
        completion_response = http.post(
            f"/users/assessment/m7/cycles/{cycle_id}/completion",
            json={
                "idempotency_key": "pers-real-cycle-close",
                "action": "complete",
                "reason": "plan_finished",
            },
        )
        assert completion_response.status_code == 200, completion_response.text

    with factory() as connection:
        stored_turn = connection.execute(
            """SELECT speaker_type,content_text,request_id FROM m5_dialogue_turns
               WHERE assessment_situation_db_id=%s AND turn_id=%s""",
            (as_db_id, participant_turn_id),
        ).fetchone()
        assert stored_turn == {
            "speaker_type": "assessee",
            "content_text": participant_text,
            "request_id": "pers-real-cycle-turn",
        }
        frozen = connection.execute(
            """SELECT s.snapshot_json,s.snapshot_checksum,cv.content_checksum,cv.case_id,cv.case_version,
                      p.checksum AS profile_checksum
               FROM m5_assessment_situations s
               JOIN m5_case_versions cv ON cv.id=s.case_version_id
               JOIN assessment_personalized_profiles p ON p.id=s.personalized_profile_id
               WHERE s.id=%s""",
            (as_db_id,),
        ).fetchone()
        connection.commit()

    assert m10_orchestration.advance_once(connection_factory=factory, gateway=gateway)
    with factory() as connection:
        evidence_request = connection.execute(
            "SELECT id FROM m6_processing_requests ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    run_evidence(evidence_request["id"], connection_factory=factory, gateway=gateway)

    assert m10_orchestration.advance_once(connection_factory=factory, gateway=gateway)
    with factory() as connection:
        evidence_diagnostics = connection.execute(
            """SELECT r.status,a.status AS attempt_status,a.error_code,a.trace_json
               FROM m6_processing_requests r
               LEFT JOIN m6_processing_attempts a ON a.request_id=r.id
               ORDER BY a.attempt_no DESC LIMIT 1"""
        ).fetchone()
        assessment_request = connection.execute(
            "SELECT id FROM m6_assessment_requests ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if assessment_request is None and os.getenv("P4K_FULL_CYCLE_EVIDENCE_PATH"):
        diagnostic_path = Path(os.environ["P4K_FULL_CYCLE_EVIDENCE_PATH"]).with_suffix(".failure.json")
        diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostic_path.write_text(
            json.dumps(_jsonable(evidence_diagnostics), ensure_ascii=False, indent=2) + "\n"
        )
    assert assessment_request is not None, _jsonable(evidence_diagnostics)
    run_assessment(assessment_request["id"], connection_factory=factory, gateway=gateway)

    assert m10_orchestration.advance_once(connection_factory=factory, gateway=gateway)
    with factory() as connection:
        assessment_diagnostics = connection.execute(
            """SELECT r.status,a.status AS attempt_status,a.error_code,a.trace_json
               FROM m6_assessment_requests r
               LEFT JOIN m6_assessment_attempts a ON a.request_id=r.id
               ORDER BY a.attempt_no DESC LIMIT 1"""
        ).fetchone()
        if assessment_diagnostics["status"] != "succeeded":
            diagnostic_path = Path(os.environ["P4K_FULL_CYCLE_EVIDENCE_PATH"]).with_name(
                "full-cycle-real-assessment.failure.json"
            )
            diagnostic_path.write_text(
                json.dumps(_jsonable(assessment_diagnostics), ensure_ascii=False, indent=2) + "\n"
            )
        assert assessment_diagnostics["status"] == "succeeded", _jsonable(assessment_diagnostics)
        report = read_latest_report(connection, cycle_id, "assessee")
        pipeline = connection.execute(
            "SELECT status,stage,error_code FROM m10_pipeline_runs"
        ).fetchone()
        evidence = connection.execute(
            """SELECT r.status,rev.output_json,a.trace_json
               FROM m6_processing_requests r
               LEFT JOIN m6_processing_attempts a ON a.request_id=r.id
               LEFT JOIN m6_analysis_revisions rev ON rev.request_id=r.id
               ORDER BY a.attempt_no DESC LIMIT 1"""
        ).fetchone()
        assessment = connection.execute(
            """SELECT r.status,rev.output_json,a.trace_json
               FROM m6_assessment_requests r
               LEFT JOIN m6_assessment_attempts a ON a.request_id=r.id
               LEFT JOIN m6_assessment_revisions rev ON rev.request_id=r.id
               ORDER BY a.attempt_no DESC LIMIT 1"""
        ).fetchone()
        turns = connection.execute(
            """SELECT turn_id,sequence_no,speaker_type,speaker_id,content_text
               FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s ORDER BY sequence_no""",
            (as_db_id,),
        ).fetchall()

    assert pipeline == {"status": "ready", "stage": "report_ready", "error_code": None}
    assert evidence["status"] == "succeeded"
    assert assessment["status"] == "succeeded"
    assert report["c67"]["contract"] == "C-67"

    artifact = {
        "schema_version": 1,
        "scope": "isolated_real_provider_full_cycle",
        "empirical_pilot": "NOT_RUN",
        "human_methodological_approval": "NOT_RUN",
        "cycle_id": cycle_id,
        "profile_ref": frozen["snapshot_json"]["profile_ref"],
        "profile_checksum": frozen["profile_checksum"],
        "case_ref": {
            "id": frozen["case_id"], "version": frozen["case_version"],
            "checksum": frozen["content_checksum"],
        },
        "assessment_situation_ref": {"id": as_id, "checksum": frozen["snapshot_checksum"]},
        "return_state": {
            "before_pause_as_id": before_pause["current_situation"]["assessment_situation_id"],
            "paused_as_id": paused["current_situation"]["assessment_situation_id"],
            "resumed_as_id": resumed["current_situation"]["assessment_situation_id"],
        },
        "actual_trajectory": _jsonable(turns),
        "m6_evidence": _jsonable(evidence),
        "m6_indicator_assessment": _jsonable(assessment),
        "m7_pipeline": _jsonable(pipeline),
        "m8_report": _jsonable(report),
    }
    output = os.getenv("P4K_FULL_CYCLE_EVIDENCE_PATH")
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
