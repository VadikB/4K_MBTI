import json
from contextlib import nullcontext
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from Api import m10_orchestration, m5_scenario_runtime, m6_assessment_worker_v2, m6_worker_v2, routes, web_session_service
from Api.config import settings
from Api.m5_cycle_runtime import read_cycle
from Api.m5_rule_engine import ControlledSemanticAdapter
from Api.m6_interim_retry import RetryRefused, RetryTarget, retry
from scripts.retry_m6_interim_evidence import main
from tests.integration.test_m10_product_path_db import AssessmentGateway, EvidenceGateway
from tests.integration.test_specialist_pilot_release_db import opened_specialist_pilot, release_db

pytestmark = pytest.mark.integration
ANSWER = "🧪 Сверил сроки и записал порядок действий."


class SpanGateway(EvidenceGateway):
    def __init__(self, *, correct_on_retry=False, on_claim=None):
        self.correct_on_retry = correct_on_retry
        self.on_claim = on_claim
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1 and self.on_claim:
            self.on_claim()
        if self.calls == 2:
            assert "fragments[0]: start=2, end=14" in messages[-1]["content"]
            assert '["fragments", 0, "end"]' in messages[-1]["content"]
        value = json.loads(super().chat(messages, **kwargs))
        material = json.loads(messages[1]["content"])
        turn, = [item for item in material["turns"] if item["speaker_type"] == "assessee"]
        assert turn["content"] == ANSWER
        end = len(ANSWER) + 1
        if self.calls == 1:
            end = 0
        elif self.correct_on_retry:
            end = 14
        value["fragments"] = [{
            "id": "synthetic-span", "turn_id": turn["turn_id"], "start": 2, "end": end, "quote": "Сверил сроки",
        }]
        return json.dumps(value, ensure_ascii=False)


class InterimAssessmentGateway(AssessmentGateway):
    def chat(self, messages, **kwargs):
        result = json.loads(super().chat(messages, **kwargs))
        result["mode"] = "interim"
        for target in result["targets"]:
            target.update(status="INTERIM", outcome=None, descriptor_basis=None)
        return json.dumps(result)


def _answer(db, as_db_id):
    return db.execute("""SELECT turn_id,sequence_no,created_at,content_text
        FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s AND speaker_type='assessee'""",
        (as_db_id,)).fetchall()


def _request(db, as_id):
    value, = db.execute("""SELECT r.id,r.as_db_id,r.handoff_id,r.input_hash,r.mechanism_hash
        FROM m6_processing_requests r JOIN m5_assessment_situations s ON s.id=r.as_db_id
        WHERE s.assessment_situation_id=%s AND r.mode='interim'""", (as_id,)).fetchall()
    return value


def _submit_to_interim(client, as_id, monkeypatch):
    monkeypatch.setattr(m5_scenario_runtime, "DeepSeekSemanticAdapter",
                        lambda **_: ControlledSemanticAdapter({"SCENARIO_CONTROL": "FINAL"}))
    turn_id = str(uuid4())
    receipt = client.post(f"/users/assessment/m5/situations/{as_id}/turns", json={
        "request_id": "task5-turn", "turn_id": turn_id, "content": ANSWER,
    })
    assert receipt.status_code == 200, receipt.text
    readback = client.get(f"/users/assessment/m5/situations/{as_id}/answer-status",
                          params={"request_id": "task5-turn", "turn_id": turn_id})
    assert readback.status_code == 200 and readback.json()["status"] == "accepted"


@pytest.mark.parametrize("retry_succeeds", [True, False], ids=["succeeded", "failed"])
def test_operator_retries_current_interim_without_replaying_participant_turn(
        release_db, opened_specialist_pilot, retry_succeeds, monkeypatch, capsys):
    pilot = opened_specialist_pilot
    http, cycle_id = pilot.client, pilot.cycle_id
    as_id = pilot.first["assessment_situation_id"]
    runtime_path = f"/users/assessment/cycles/{cycle_id}/runtime"
    m7_path = f"/users/assessment/m7/cycles/{cycle_id}"
    _submit_to_interim(http, as_id, monkeypatch)
    with release_db() as db:
        request = _request(db, as_id)
        as_db_id = request["as_db_id"]
        original, = _answer(db, as_db_id)
        assert db.execute("""SELECT snapshot_json#>>'{case_ref,id}' AS case_id
            FROM m5_assessment_situations WHERE id=%s""", (as_db_id,)).fetchone()["case_id"] == "CASE.SPEC.02"
    target = RetryTarget(pilot.assignment_id, UUID(cycle_id), UUID(as_id), request["handoff_id"], request["id"], 1)
    m6_worker_v2.run_request(target.request_id, connection_factory=release_db, gateway=SpanGateway())
    assert m10_orchestration.advance_once(connection_factory=release_db)
    assert m6_worker_v2.recover_pending(connection_factory=release_db) is False
    blocked = http.get(runtime_path).json()
    assert blocked["pipeline"]["error_code"] == "M6_EVIDENCE_FAILED"
    assert blocked["finish_availability"] == {"allowed": False, "reason": "INTERIM_PENDING"}

    args = [
        "--expected-origin", settings.public_app_origin,
        "--assignment-id", str(target.assignment_id), "--cycle-id", cycle_id, "--situation-id", as_id,
        "--handoff-id", str(target.handoff_id), "--request-id", str(target.request_id), "--failed-attempt", "1",
    ]
    capsys.readouterr()
    assert main([args[0], "https://wrong-origin.example", *args[2:]], connection_factory=release_db) == 2
    assert json.loads(capsys.readouterr().out) == {"error_code": "M6_RETRY_ORIGIN_MISMATCH"}
    assert main(args, connection_factory=release_db) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["eligible"] and not preview["started"]
    assert preview["attempt_no"] == 1 and preview["error_code"] == "M6_FRAGMENT_SPAN"
    assert preview["boundary_sequence"] == original["sequence_no"] + 1

    with pytest.raises(RetryRefused, match="M6_RETRY_ASSIGNMENT_CYCLE_MISMATCH"):
        retry(replace(target, assignment_id=target.assignment_id + 1), connection_factory=release_db)
    with pytest.raises(RetryRefused, match="M6_RETRY_EXPECTED_FAILED_ATTEMPT_NOT_FOUND"):
        retry(replace(target, failed_attempt=2), connection_factory=release_db)

    blocked_gateway = SpanGateway()
    with release_db() as db:
        db.execute("""UPDATE m5_cycles SET started_at=clock_timestamp()-interval '1 day' * 4
            WHERE cycle_id=%s""", (target.cycle_id,))
        with pytest.raises(RetryRefused, match="M6_RETRY_CYCLE_NOT_OPEN"):
            retry(target, connection_factory=lambda: nullcontext(db), apply=True, operator="synthetic",
                  gateway=blocked_gateway)
        db.rollback()
    assert blocked_gateway.calls == 0

    with release_db() as db:
        m5_scenario_runtime.append_event(db, as_db_id=as_db_id, event_type="clarification_answered",
                                         event_key="synthetic-stale-boundary", cause={}, payload={})
        with pytest.raises(RetryRefused, match="M6_RETRY_STALE_C45"):
            retry(target, connection_factory=lambda: nullcontext(db), apply=True, operator="synthetic",
                  gateway=blocked_gateway)
        db.rollback()
    assert blocked_gateway.calls == 0

    def read_concurrent_attempt():
        observed = retry(target, connection_factory=release_db, apply=True, operator="concurrent")
        assert not observed["eligible"] and not observed["started"]
        assert observed["request_status"] == "running" and observed["attempt_no"] == 2

    gateway = SpanGateway(correct_on_retry=retry_succeeds, on_claim=read_concurrent_attempt)
    assert main([*args, "--apply"], connection_factory=release_db, gateway=gateway) == (0 if retry_succeeds else 1)
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["started"] and resumed["attempt_no"] == 2
    assert resumed["request_status"] == ("succeeded" if retry_succeeds else "failed")
    assert main([*args, "--apply"], connection_factory=release_db, gateway=gateway) == (0 if retry_succeeds else 1)
    replayed = json.loads(capsys.readouterr().out)
    assert replayed == {**resumed, "started": False}
    assert gateway.calls == 2

    with release_db() as db:
        assert _request(db, as_id) == request
        assert _answer(db, as_db_id) == [original]
        first, second = db.execute("""SELECT attempt_no,status,error_code,trace_json->'validation_attempts' AS checks,
            trace_json->'operator_retry' AS audit FROM m6_processing_attempts WHERE request_id=%s ORDER BY attempt_no""",
            (target.request_id,)).fetchall()
        assert (first["attempt_no"], second["attempt_no"]) == (1, 2)
        assert first["status"] == "failed" and first["error_code"] == "M6_FRAGMENT_SPAN"
        assert first["checks"][0]["issues"] == [{"path": ["fragments", 0, "end"], "rule": "greater_than"}]
        assert first["checks"][1]["issues"] == [{"path": ["fragments", 0, "end"], "rule": "span_end_exceeds_turn"}]
        assert second["audit"]["source_attempt_no"] == 1 and second["audit"]["principal"]
        assert second["checks"][1]["status"] == ("accepted" if retry_succeeds else "rejected")
        revisions = db.execute("SELECT count(*) AS n FROM m6_analysis_revisions WHERE request_id=%s",
                               (target.request_id,)).fetchone()["n"]
        assert revisions == int(retry_succeeds)
    if not retry_succeeds:
        assert http.get(runtime_path).json()["finish_availability"]["allowed"] is False
        return

    assert m10_orchestration.advance_once(connection_factory=release_db)
    with release_db() as db:
        assessment, = db.execute("""SELECT id FROM m6_assessment_requests
            WHERE as_db_id=%s AND mode='interim'""", (as_db_id,)).fetchall()
    m6_assessment_worker_v2.run_request(
        assessment["id"], connection_factory=release_db, gateway=InterimAssessmentGateway(),
    )
    assert m10_orchestration.advance_once(connection_factory=release_db)
    assert http.get(runtime_path).json()["finish_availability"] == {"allowed": True, "reason": "CURRENT_DECISION"}
    with release_db() as db:
        c54, = db.execute("""SELECT d.status FROM m6_c54_revisions c
            JOIN m7_clarification_decisions d ON d.c54_revision_id=c.id
            WHERE c.as_db_id=%s AND c.handoff_id=%s AND c.mode='interim'""",
            (as_db_id, target.handoff_id)).fetchall()
        assert c54["status"] == "NO_QUESTION"

    finish = {"idempotency_key": "task5-finish"}
    closed = http.post(m7_path + "/finish-situation", json=finish)
    assert closed.status_code == 200, closed.text
    replay = http.post(m7_path + "/finish-situation", json=finish)
    assert replay.json() == {**closed.json(), "idempotent": True}
    job = pilot.worker._claim()
    assert job["operation_id"] == "next:" + as_id
    pilot.worker._process(job)
    assert pilot.worker._claim() is None
    operation = pilot.worker.get_status("next:" + as_id)
    assert operation["status"] == "completed" and operation["attempts"] == 1
    next_as = operation["result_json"]["decision"]["assessment_situation_id"]
    present = http.get(runtime_path).json()["next_presentation"]
    for _ in range(2):
        response = http.post(m7_path + "/present-next", json=present)
        assert response.status_code == 201, response.text
        runtime = response.json()["runtime"]
        assert runtime["cycle_id"] == cycle_id and runtime["current_situation"]["assessment_situation_id"] == next_as
    http.cookies.set(routes.SESSION_COOKIE_NAME, web_session_service.web_session_service.create_session(pilot.participant_id))
    assert http.get(runtime_path).json()["current_situation"] == runtime["current_situation"]
    assert not retry(target, connection_factory=release_db, apply=True, operator="synthetic")["started"]

    with release_db() as db:
        assert _answer(db, as_db_id) == [original]
        cycle = read_cycle(db, cycle_id)
        assert cycle["status"] == "active" and cycle["started_at"] == pilot.started_at
        assert cycle["collection_closed_at"] is None
        cases = db.execute("""SELECT s.snapshot_json#>>'{case_ref,id}' AS case_id,s.status,
             (SELECT count(*) FROM m5_scenario_events e WHERE e.assessment_situation_db_id=s.id
                 AND e.event_type='scenario_started') AS presentations
             FROM m5_assessment_situations s WHERE s.cycle_db_id=%s ORDER BY s.id""", (cycle["id"],)).fetchall()
        assert cases == [
            {"case_id": "CASE.SPEC.02", "status": "closed", "presentations": 1},
            {"case_id": "CASE.SPEC.03", "status": "active", "presentations": 1},
        ]
