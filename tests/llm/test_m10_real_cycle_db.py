from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import m10_orchestration
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.m10_product_flow import read_runtime, start_or_resume
from Api.m5_cycle_runtime import transition_session
from Api.m6_worker_v2 import run_request as run_evidence
from Api.m6_assessment_worker_v2 import run_request as run_assessment
from Api.m8_results import read_latest_report
from tests.integration.test_m10_product_path_db import product_db
from Api import routes


pytestmark = [pytest.mark.integration, pytest.mark.llm]


def _jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


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
