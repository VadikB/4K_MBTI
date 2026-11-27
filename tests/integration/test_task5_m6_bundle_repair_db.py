import json

import pytest

from Api import m10_orchestration, m6_assessment_worker_v2, m6_repository, m6_worker_v2
from Api.assessment_configuration import definition_checksum
from Api.m6_package_v2 import load_mechanism
from tests.integration.test_specialist_pilot_release_db import (
    opened_specialist_pilot, pin_original_evidence_mechanism, release_db,
)
from tests.integration.test_task5_m6_interim_retry_db import InterimAssessmentGateway, _answer, _request, _submit_to_interim
from tests.m6_bundle_repair_fixture import (
    ANSWER, LEGACY_HASH, TARGETS, RecordedEvidenceGateway, complete_reply, double_defect_reply, retry_reply,
)

pytestmark = pytest.mark.integration


@pytest.fixture(params=["1.0.1", "1.0.2"])
def pinned_pilot(request):
    version = request.param
    if version == "1.0.1":
        request.getfixturevalue("pin_original_evidence_mechanism")
    return version, request.getfixturevalue("opened_specialist_pilot")


@pytest.mark.parametrize("defect", ["repaired", "valid-first", "empty", "missing", "foreign", "duplicate", "invented"])
def test_spec02_m6_bundle_repair(release_db, pinned_pilot, monkeypatch, defect):
    version, pilot = pinned_pilot
    as_id = pilot.first["assessment_situation_id"]
    _submit_to_interim(pilot.client, as_id, monkeypatch, answer=ANSWER)
    with release_db() as db:
        request = _request(db, as_id)
        original, = _answer(db, request["as_db_id"])
        frozen = db.execute("SELECT mechanism_json,input_json FROM m6_processing_requests WHERE id=%s",
                            (request["id"],)).fetchone()
        assert db.execute("""SELECT snapshot_json#>>'{case_ref,id}' AS case_id
            FROM m5_assessment_situations WHERE id=%s""", (request["as_db_id"],)).fetchone()["case_id"] == "CASE.SPEC.02"
    assert frozen["mechanism_json"]["ref"] == f"m6_evidence/{version}"
    assert frozen["mechanism_json"] == load_mechanism(f"m6_evidence/{version}")
    assert request["mechanism_hash"] == definition_checksum(frozen["mechanism_json"])
    if version == "1.0.1":
        assert request["mechanism_hash"] == LEGACY_HASH
    expected = [target["indicator_id"] for target in frozen["input_json"]["indicator_targets"]]
    assert set(expected) == set(TARGETS) and len(expected) == len(TARGETS)

    gateway = (RecordedEvidenceGateway(complete_reply) if defect == "valid-first" else
               RecordedEvidenceGateway(double_defect_reply, lambda material: retry_reply(material, defect)))
    m6_worker_v2.run_request(request["id"], connection_factory=release_db, gateway=gateway)
    accepted = defect in {"repaired", "valid-first"}
    with release_db() as db:
        saved = m6_repository.read_request(db, request["id"])
        assert _answer(db, request["as_db_id"]) == [original]
        assert _request(db, as_id) == request
        attempt, = db.execute("""SELECT status,error_code,trace_json FROM m6_processing_attempts
            WHERE request_id=%s""", (request["id"],)).fetchall()
        revisions = db.execute("SELECT count(*) AS n FROM m6_analysis_revisions WHERE request_id=%s",
                               (request["id"],)).fetchone()["n"]
        assert revisions == int(accepted)
        assert saved["status"] == attempt["status"] == ("succeeded" if accepted else "failed")
        if accepted:
            analysis = m6_repository.read_analysis(db, saved["analysis_revision_id"])
    assert len(gateway.calls) == (1 if defect == "valid-first" else 2)
    for messages in gateway.calls:
        assert json.loads(messages[1]["content"]) == (frozen["input_json"] if version == "1.0.1" else
                                                     {**frozen["input_json"], "schema_version": 2})
    validations = attempt["trace_json"]["validation_attempts"]
    if defect != "valid-first":
        feedback = gateway.calls[1][-1]["content"]
        assert gateway.calls[1][-2]["role"] == "assistant"
        assert json.loads(gateway.calls[1][-2]["content"]) == gateway.responses[0]
        assert f"Недостающие indicator_id в bundles: {', '.join(expected)}." in feedback
        assert "fragments.1.quote" in feedback and "Для пустой цитаты" in feedback
        assert str(original["turn_id"]) in feedback
        if version == "1.0.1":
            assert "fragments.1.end" in feedback and "M6_FRAGMENT_RANGE_MISMATCH" in feedback
            assert "fragments[0]: start=0, end=11" in feedback
        else:
            assert "M6_FRAGMENT_QUOTE_NOT_FOUND" in feedback and "start=" not in feedback
        assert validations[0]["missing_indicator_ids"] == expected
    assert validations[-1]["status"] == ("accepted" if accepted else "rejected")

    if not accepted:
        code = {
            "empty": "TARGET_SET_MISMATCH", "missing": "TARGET_SET_MISMATCH", "foreign": "TARGET_SET_MISMATCH",
            "duplicate": "M6_DUPLICATE_ID", "invented": "M6_FRAGMENT_SPAN" if version == "1.0.1" else "M6_FRAGMENT_QUOTE_NOT_FOUND",
        }[defect]
        assert attempt["error_code"] == code
        assert saved["analysis_revision_id"] is None
        return

    bundles = {row["content_json"]["indicator_id"]: row["content_json"] for row in analysis["bundles"]}
    assert set(bundles) == set(TARGETS)
    assert sum(not bundle["evidence_ids"] for bundle in bundles.values()) == 7
    output = analysis["analysis"]
    assert len(output["fragments"]) == len(output["signals"]) == len(output["evidence"]) == 2
    for fragment, signal, evidence in zip(output["fragments"], output["signals"], output["evidence"], strict=True):
        assert fragment["turn_id"] == str(original["turn_id"])
        assert fragment["quote"] == original["content_text"][fragment["start"]:fragment["end"]]
        assert signal["fragment_id"] == fragment["id"] == evidence["fragment_ids"][0]
        assert signal["id"] == evidence["bs_ids"][0]
        assert bundles[evidence["indicator_id"]]["evidence_ids"] == [evidence["id"]]

    assert m10_orchestration.advance_once(connection_factory=release_db)
    with release_db() as db:
        assessment, = db.execute("""SELECT id FROM m6_assessment_requests
            WHERE as_db_id=%s AND mode='interim'""", (request["as_db_id"],)).fetchall()
    m6_assessment_worker_v2.run_request(assessment["id"], connection_factory=release_db, gateway=InterimAssessmentGateway())
    assert m10_orchestration.advance_once(connection_factory=release_db)
    with release_db() as db:
        decision, = db.execute("""SELECT d.status,c.payload_json FROM m7_clarification_decisions d
            JOIN m6_c54_revisions c ON c.id=d.c54_revision_id
            WHERE c.as_db_id=%s AND c.handoff_id=%s AND c.mode='interim'""",
                               (request["as_db_id"], request["handoff_id"])).fetchall()
        assert decision["status"] == "NO_QUESTION"
        assert decision["payload_json"]["evidence_revision_id"] == str(analysis["id"])
