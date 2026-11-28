from time import perf_counter

import pytest

from Api import m10_orchestration, m6_assessment_worker_v2, m6_repository, m6_worker_v2
from Api.assessment_configuration import definition_checksum
from Api.m5_case_runtime import checksum
from Api.m6_candidate_v3 import attach_criterion_attribution
from tests.integration.test_m10_product_path_db import AssessmentGateway
from tests.integration.test_specialist_pilot_release_db import opened_specialist_pilot, pin_evidence_mechanism, release_db
from tests.integration.test_task5_m6_interim_retry_db import InterimAssessmentGateway, _answer, _request, _submit_to_interim
from tests.m6_bundle_repair_fixture import RecordedEvidenceGateway


pytestmark = pytest.mark.integration
TARGET = "K4.I05"
PARTS = (
    ("dates", "Сверил даты: 10 и 12 мая.", "Сопоставил сроки по двум конкретным датам."),
    ("prices", "Сопоставил цены: 400 и 500 тысяч.", "Сопоставил предложения по цене в одной единице."),
    ("letter", "Завтра отправлю письмо.", "Сообщил о запланированной отправке письма."),
)
ANSWER = " ".join(quote for _, quote, _ in PARTS)


def reply(material, variant):
    turn, = [row["turn_id"] for row in material["turns"] if row["speaker_type"] == "assessee"]
    version = material["schema_version"]
    criterion = next(row for row in material["criteria"] if row["id"] == TARGET)
    fragments, signals, evidence = [], [], []
    for key, quote, explanation in PARTS:
        fragments.append({"id": f"f-{key}", "turn_id": turn, "quote": quote})
        signals.append({"id": f"s-{key}", "fragment_id": f"f-{key}", "observation": explanation,
                        "form_description": "Письменный ответ", "context_refs": []})
        if key == "letter":
            continue
        evidence.append({
            "id": f"e-{key}", "indicator_id": TARGET, "m2_version": criterion["m2_version"], "type": "Simple",
            "interpretation": explanation, "bs_ids": [f"s-{key}"], "fragment_ids": [f"f-{key}"],
            "context_refs": [], "limitations": [], "ordered_turn_ids": [turn],
        })
    reviews = []
    if variant == "too-many":
        evidence[0]["bs_ids"].append("s-letter")
        evidence[0]["fragment_ids"].append("f-letter")
    if variant in {"repaired", "unclear", "unclear-missing", "removed-verified", "substituted", "invented",
                   "foreign-turn", "foreign-indicator"}:
        reviews.append({
            "evidence_id": "e-dates", "signal_id": "s-letter", "fragment_id": "f-letter", "indicator_id": TARGET,
            "turn_id": turn, "reason": "unclear" if variant.startswith("unclear") else "irrelevant",
            "explanation": ("Из обещания отправить письмо нельзя установить, какие данные сопоставлены."
                            if variant.startswith("unclear") else
                            "Обещание отправить письмо описывает передачу информации и не обосновывает сопоставление дат."),
        })
    if variant == "removed-verified":
        evidence.pop()
    if variant == "substituted":
        fragments[1]["quote"] = PARTS[2][1]
    if variant == "invented":
        fragments[1]["quote"] = "Сопоставил цены: 800 и 900 тысяч."
    if variant == "foreign-turn":
        reviews[0]["turn_id"] = "another-situation-turn"
    if variant == "foreign-indicator":
        evidence[0]["indicator_id"] = "K9.I99"
    if variant == "unclear-missing":
        fragments.pop()
        signals.pop()
    if variant == "schema-missing-interpretation":
        del evidence[0]["interpretation"]
    bundles = [{"indicator_id": t["indicator_id"], "context_refs": [], "limitations": [], "contradictions": [],
                "opportunity_basis": "Письменная ситуация давала возможность сопоставить предложения.",
                "evidence_ids": [e["id"] for e in evidence if e["indicator_id"] == t["indicator_id"]]}
               for t in material["indicator_targets"]]
    result = {"schema_version": version, "fragments": fragments, "signals": signals, "evidence": evidence,
              "bundles": bundles, "attribution_notes": []}
    if version == 3:
        result["repair_notes"] = reviews
    return result


def worker_receipt(factory, request, gateway):
    m6_worker_v2.run_request(request["id"], connection_factory=factory, gateway=gateway)
    with factory() as db:
        state = m6_repository.read_request(db, request["id"])
        attempt, = db.execute("""SELECT attempt_no,status,error_code,trace_json FROM m6_processing_attempts
            WHERE request_id=%s""", (request["id"],)).fetchall()
        revisions = db.execute("SELECT count(*) AS n FROM m6_analysis_revisions WHERE request_id=%s",
                               (request["id"],)).fetchone()["n"]
        assert revisions == (state["status"] == "succeeded")
        assert attempt["attempt_no"] == 1
        return state, attempt


def assess(factory, request, gateway):
    for _ in range(3):
        assert m10_orchestration.advance_once(connection_factory=factory)
        with factory() as db:
            assessment = db.execute("""SELECT q.id FROM m6_assessment_requests q
                JOIN m6_analysis_revisions v ON v.id=q.evidence_revision_id WHERE v.request_id=%s""",
                                    (request["id"],)).fetchone()
        if assessment:
            break
    assert assessment
    m6_assessment_worker_v2.run_request(assessment["id"], connection_factory=factory, gateway=gateway)


@pytest.mark.parametrize("mode", ["interim", "final_as"])
@pytest.mark.parametrize(("variant", "outcome", "failing_fragment"), [
    ("valid-first", None, None),
    ("repaired", None, None),
    ("unclear", None, None),
    ("silent", "M6_FRAGMENT_REPAIR_EVIDENCE_MISSING", "f-letter"),
    ("removed-verified", "M6_FRAGMENT_REPAIR_EVIDENCE_MISSING", "f-prices"),
    ("substituted", "M6_FRAGMENT_REPAIR_QUOTE", "f-prices"),
    ("invented", "M6_FRAGMENT_QUOTE_NOT_FOUND", "f-prices"),
    ("foreign-turn", "M6_FRAGMENT_TURN_UNKNOWN", "f-letter"),
    ("foreign-indicator", "TARGET_SET_MISMATCH", "f-dates"),
    ("unclear-missing", "M6_FRAGMENT_REPAIR_MISSING", "f-letter"),
])
def test_scoped_m6_retry_on_published_program(release_db, opened_specialist_pilot, monkeypatch,
                                             mode, variant, outcome, failing_fragment):
    pilot = opened_specialist_pilot
    as_id = pilot.first["assessment_situation_id"]
    runtime_path = f"/users/assessment/cycles/{pilot.cycle_id}/runtime"
    m7_path = f"/users/assessment/m7/cycles/{pilot.cycle_id}"

    started = perf_counter()
    _submit_to_interim(pilot.client, as_id, monkeypatch, answer=ANSWER)
    with release_db() as db:
        interim = _request(db, as_id)
        original, = _answer(db, interim["as_db_id"])
    request = interim
    if mode == "final_as":
        ready, _ = worker_receipt(release_db, interim, RecordedEvidenceGateway(lambda m: reply(m, "valid-first")))
        assert ready["status"] == "succeeded"
        assess(release_db, interim, InterimAssessmentGateway())
        assert m10_orchestration.advance_once(connection_factory=release_db)
        finished = pilot.client.post(m7_path + "/finish-situation", json={"idempotency_key": "task13-finish"})
        assert finished.status_code == 200, finished.text
        with release_db() as db:
            request, = db.execute("""SELECT id,as_db_id,handoff_id FROM m6_processing_requests
                WHERE as_db_id=%s AND mode='final_as'""", (interim["as_db_id"],)).fetchall()

    with release_db() as db:
        frozen = db.execute("""SELECT r.input_json,r.input_hash,r.mechanism_json,r.mechanism_hash,
                                      h.boundary_sequence,h.envelope_json,h.envelope_checksum
            FROM m6_processing_requests r JOIN m5_c45_handoffs h ON h.handoff_id=r.handoff_id
            WHERE r.id=%s""", (request["id"],)).fetchone()
    assert frozen["input_json"]["mode"] == mode
    assert frozen["mechanism_json"]["ref"] == "m6_evidence/1.0.3"
    assert frozen["input_hash"] == definition_checksum(frozen["input_json"])
    assert frozen["mechanism_hash"] == definition_checksum(frozen["mechanism_json"])
    assert frozen["envelope_checksum"] == checksum(frozen["envelope_json"])
    assert frozen["boundary_sequence"] == frozen["envelope_json"]["boundary"]["inclusive_sequence"]
    assert frozen["input_json"]["last_included_turn_id"] == str(original["turn_id"])

    gateway = (RecordedEvidenceGateway(lambda m: reply(m, variant)) if variant == "valid-first" else
               RecordedEvidenceGateway(lambda m: reply(m, "too-many"), lambda m: reply(m, variant)))
    saved, attempt = worker_receipt(release_db, request, gateway)
    assert len(gateway.calls) == (1 if variant == "valid-first" else 2)
    assert attempt["error_code"] == outcome
    trace = attempt["trace_json"]
    if variant != "valid-first":
        feedback = gateway.calls[1][-1]["content"]
        assert '"verified_links":[{"evidence_id":"e-prices"' in feedback
        assert '"readable_links":[{"evidence_id":"e-dates"' in feedback
        assert '"fragment_id":"f-letter","signal_id":"s-letter"' in feedback
        assert '"code":"M6_SIMPLE_BASIS","path":"evidence.0.bs_ids"' in feedback
        assert "дословной копией" not in feedback

    if outcome:
        issue = next(row for row in trace["validation_attempts"][-1]["validation_errors"] if row["code"] == outcome)
        if failing_fragment:
            assert (issue["fragment_id"], issue["indicator_id"]) == (
                failing_fragment, "K9.I99" if variant == "foreign-indicator" else TARGET,
            )
        assert saved["analysis_revision_id"] is None
        return

    with release_db() as db:
        output = m6_repository.read_analysis(db, saved["analysis_revision_id"])
        replay = m10_orchestration.enqueue_handoff(db, handoff_id=str(request["handoff_id"]),
                                                   created_by=pilot.participant_id)
        assert replay["id"] == saved["id"]
        assert replay["mechanism_hash"] == frozen["mechanism_hash"]
        assert _answer(db, request["as_db_id"]) == [original]
    m6_worker_v2.run_request(replay["id"], connection_factory=release_db, gateway=gateway)
    assert len(gateway.calls) == (1 if variant == "valid-first" else 2)
    analysis = output["analysis"]
    assert analysis["schema_version"] == 1
    assert trace["repair_notes"] == gateway.responses[-1]["repair_notes"]
    assert trace["assembled_analysis"]["contract"] == "M6.EvidenceAnalysis/1"
    raw = gateway.responses[-1]
    assert analysis["signals"] == raw["signals"]
    assert [f["quote"] for f in analysis["fragments"]] == [q for _, q, _ in PARTS]
    assert [e["fragment_ids"] for e in analysis["evidence"]] == [["f-dates"], ["f-prices"]]
    criterion = next(row for row in frozen["input_json"]["criteria"] if row["id"] == TARGET)
    for stored, sent in zip(analysis["evidence"], raw["evidence"], strict=True):
        assert stored["interpretation"] == sent["interpretation"]
        assert stored["indicator_id"] == sent["indicator_id"]
        assert [stored["attribution"][k] for k in ("function", "product", "evidence_pattern", "boundaries")] == [
            criterion[k] for k in ("function", "product", "evidence_pattern", "boundary")
        ]

    assess(release_db, request, InterimAssessmentGateway() if mode == "interim" else AssessmentGateway())
    if mode == "interim":
        assert m10_orchestration.advance_once(connection_factory=release_db)
        timing_ms = (perf_counter() - started) * 1000
        print(f"{mode} {variant}: {len(gateway.calls)} Evidence, {timing_ms:.1f} ms до решения M7")
        assert pilot.client.get(runtime_path).json()["finish_availability"] == {"allowed": True, "reason": "CURRENT_DECISION"}
    else:
        operation = pilot.worker._claim()
        assert operation["operation_id"] == "next:" + as_id
        pilot.worker._process(operation)
        ready = pilot.client.get(runtime_path).json()["next_presentation"]
        for _ in range(2):
            opened = pilot.client.post(m7_path + "/present-next", json=ready)
            assert opened.status_code == 201, opened.text
            assert opened.json()["runtime"]["current_situation"]["assessment_situation_id"] == ready["assessment_situation_id"]

    with release_db() as db:
        c54, = db.execute("""SELECT c.payload_json,d.status FROM m6_c54_revisions c
            LEFT JOIN m7_clarification_decisions d ON d.c54_revision_id=c.id
            WHERE c.handoff_id=%s""", (request["handoff_id"],)).fetchall()
        assert c54["payload_json"]["evidence_revision_id"] == str(saved["analysis_revision_id"])
        assert c54["status"] == ("NO_QUESTION" if mode == "interim" else None)
        assert m6_repository.read_request(db, request["id"]) == saved


@pytest.mark.parametrize(("legacy", "variant", "path", "first_pass"), [
    (True, "valid-first", "evidence.0.attribution", False),
    (False, "valid-first", None, True),
    (False, "schema-missing-interpretation", "evidence.0.interpretation", False),
])
def test_final_as_schema_controls(release_db, request, monkeypatch, pin_evidence_mechanism, legacy, variant, path, first_pass):
    if legacy:
        pin_evidence_mechanism("1.0.2")
    pilot = request.getfixturevalue("opened_specialist_pilot")
    as_id = pilot.first["assessment_situation_id"]
    _submit_to_interim(pilot.client, as_id, monkeypatch, answer=ANSWER)
    response = pilot.client.post(f"/users/assessment/m7/cycles/{pilot.cycle_id}/completion", json={
        "action": "complete", "reason": "synthetic final_as schema control", "idempotency_key": "task13-final",
    })
    assert response.status_code == 200, response.text
    assert m10_orchestration.advance_once(connection_factory=release_db)
    with release_db() as db:
        final, = db.execute("SELECT id FROM m6_processing_requests WHERE mode='final_as'").fetchall()
    gateway = RecordedEvidenceGateway(lambda m: reply(m, variant), lambda m: reply(m, variant))
    result, attempt = worker_receipt(release_db, final, gateway)
    assert len(gateway.calls) == (1 if first_pass else 2)
    assert result["status"] == ("succeeded" if first_pass else "failed")
    if path:
        assert attempt["error_code"] == "ValidationError"
        for attempt_row in attempt["trace_json"]["validation_attempts"]:
            assert attempt_row["error_code"] == "M6_SCHEMA_VALIDATION"
            assert any(issue["path"] == path and issue["code"] == "missing"
                       for issue in attempt_row["validation_errors"])


def test_legacy_worker_reproduces_interim_link_loss(release_db, request, monkeypatch, pin_evidence_mechanism):
    pin_evidence_mechanism("1.0.2")
    pilot = request.getfixturevalue("opened_specialist_pilot")
    as_id = pilot.first["assessment_situation_id"]
    _submit_to_interim(pilot.client, as_id, monkeypatch, answer=ANSWER)
    with release_db() as db:
        interim = _request(db, as_id)

    def rejected(material):
        candidate = attach_criterion_attribution(reply(material, "too-many"), material)
        candidate["evidence"][0]["attribution"]["function"] = "Пересказ сравнения"
        return candidate

    gateway = RecordedEvidenceGateway(rejected, lambda m: attach_criterion_attribution(reply(m, "valid-first"), m))
    result, attempt = worker_receipt(release_db, interim, gateway)
    assert len(gateway.calls) == 2
    assert result["status"] == "failed"
    first, second = attempt["trace_json"]["validation_attempts"]
    assert {issue["code"] for issue in first["validation_errors"]} == {"M6_ATTRIBUTION_MISMATCH", "M6_SIMPLE_BASIS"}
    assert second["validation_errors"] == [{"code": "M6_FRAGMENT_REPAIR_EVIDENCE_MISSING", "path": "evidence"}]
