import hashlib
import json

import pytest

from tests.assessment_completion_evidence import validate_completion


def write(path, value):
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence(tmp_path):
    run = {"run_id": "run-1", "database": "product4k_pytest_run1",
           "profile": "assessment-execution-contour/2", "code": {"sha": "a" * 40,
           "branch": "codex/exec-contour-fix-01", "files": {
               "tests/assessment_completion_evidence.py": "a" * 64,
               "tests/assessment_execution_export.py": "b" * 64}}}
    first = {"cycle": {"cycle_id": "cycle-1"},
             "sessions": [{"session_id": "session-1"}],
             "assessment_situation": {"assessment_situation_id": "as-1"},
             "assessment_answers": 0}
    screenshot = tmp_path / "available-report.png"
    screenshot.write_bytes(b"synthetic png evidence")
    first_hash = write(tmp_path / "first-case-receipt.json", first)
    export = {"run_id": "run-1", "cycle_id": "cycle-1", "owner_user_id": 1,
              "collection_status": "calculated", "close_reason": "route_completed",
              "collection_closed_at": "2026-11-10T10:00:00Z", "c46": {"id": "c46-1"},
              "situations": [{"assessment_situation_id": "as-1", "session_id": "session-1", "status": "closed",
                              "final_handoff_id": "handoff-1", "assessee_turns": 1,
                              "finalization_status": "queued", "interim_handoffs": 1, "c54_receipts": 1}],
              "pipeline": {"status": "ready", "latest_report_id": "report-1",
                           "latest_results_revision_id": "results-1"},
              "results": {"id": "results-1", "c46_revision_id": "c46-1"},
              "report": {"id": "report-1", "status": "ready", "audience": "assessee",
                         "revision_no": 1, "created_by": 1, "result_revision_id": "results-1"}}
    export_hash = write(tmp_path / "terminal-execution-export.json", export)
    receipt = {
        "contract": "assessment-execution-contour/2", "run_id": "run-1",
        "cycle_id": "cycle-1", "initial_assessment_situation_id": "as-1",
        "report_id": "report-1", "results_revision_id": "results-1", "report_opened": True,
        "situation_count": 1,
        "first_case_receipt": {"file": "first-case-receipt.json", "sha256": first_hash,
                               "assessment_answers": 0},
        "terminal_export": {"file": "terminal-execution-export.json", "sha256": export_hash},
        "stages": [
            {"stage": "first_case_started", "status": "milestone", "cycle_id": "cycle-1",
             "assessment_situation_id": "as-1"},
            {"stage": "assessment_situation_closed", "status": "completed", "position": 1,
             "cycle_id": "cycle-1", "session_id": "session-1", "assessment_situation_id": "as-1", "close_status": "closed",
             "final_handoff_id": "handoff-1", "finalization_status": "queued",
             "assessee_turns_before": 0, "assessee_turns": 1,
             "interim_handoffs": 1, "c54_receipts": 1},
            {"stage": "collection_closed", "status": "completed", "cycle_id": "cycle-1",
             "close_reason": "route_completed", "closed_at": "2026-11-10T10:00:00Z",
             "c46_revision_id": "c46-1"},
            {"stage": "report_opened", "status": "completed", "cycle_id": "cycle-1",
             "report_id": "report-1", "results_revision_id": "results-1", "report_revision_no": 1,
             "owner_user_id": 1, "screenshot": screenshot.name,
             "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest()},
        ],
    }
    digest = write(tmp_path / "execution-contour-receipt.json", receipt)
    completion = {"run_id": "run-1", "status": "completed", "exit_code": 0,
                  "receipt_file": "execution-contour-receipt.json", "receipt_sha256": digest}
    cleanup = {"run_id": "run-1", "owner_verified": True,
               "database_absent": True, "state_absent": True}
    return run, first, completion, cleanup, receipt


def test_completion_evidence_accepts_terminal_chain(tmp_path):
    run, first, completion, cleanup, _ = evidence(tmp_path)
    assert validate_completion(tmp_path, run=run, first_case=first,
                               completion=completion, cleanup=cleanup, process_exit=0) == []


@pytest.mark.parametrize("mutation,expected", [
    ("foreign_run", "COMPOSITE_RUN_MISMATCH"),
    ("foreign_cycle", "COMPOSITE_CONTEXT_MISMATCH"),
    ("missing_stage", "COMPOSITE_STAGE_CHAIN_INVALID"),
    ("report_not_opened", "REPORT_OPEN_NOT_PROVEN"),
    ("cleanup_failed", "CLEANUP_NOT_VERIFIED"),
    ("process_failed", "PROCESS_EXIT_NOT_ZERO"),
    ("report_before_close", "COMPOSITE_STAGE_CHAIN_INVALID"),
    ("failed_close", "AS_CLOSE_STAGE_INVALID"),
    ("foreign_as", "TERMINAL_AS_READBACK_MISMATCH"),
    ("missing_as", "AS_CLOSE_STAGE_INVALID"),
    ("wrong_first_case_hash", "FIRST_CASE_LINK_INVALID"),
    ("zero_situations", "COMPOSITE_STAGE_CHAIN_INVALID"),
    ("foreign_export", "TERMINAL_COLLECTION_MISMATCH"),
    ("non_object_stage", "COMPOSITE_STAGE_CHAIN_INVALID"),
])
def test_completion_evidence_fails_closed(tmp_path, mutation, expected):
    run, first, completion, cleanup, receipt = evidence(tmp_path)
    process_exit = 0
    if mutation == "foreign_run": receipt["run_id"] = "other"
    elif mutation == "foreign_cycle": receipt["cycle_id"] = "other"
    elif mutation == "missing_stage": receipt["stages"] = receipt["stages"][:1]
    elif mutation == "report_not_opened": receipt["report_opened"] = False
    elif mutation == "cleanup_failed": cleanup["database_absent"] = False
    elif mutation == "process_failed": process_exit = 1
    elif mutation == "report_before_close": receipt["stages"][1], receipt["stages"][-1] = receipt["stages"][-1], receipt["stages"][1]
    elif mutation == "failed_close": receipt["stages"][1]["status"] = "failed"
    elif mutation == "foreign_as": receipt["stages"][1]["assessment_situation_id"] = "foreign-as"
    elif mutation == "missing_as": receipt["stages"][1].pop("assessment_situation_id")
    elif mutation == "wrong_first_case_hash": receipt["first_case_receipt"]["sha256"] = "0" * 64
    elif mutation == "zero_situations": receipt["situation_count"] = 0
    elif mutation == "foreign_export":
        exported = json.loads((tmp_path / "terminal-execution-export.json").read_text())
        exported["cycle_id"] = "foreign-cycle"
        receipt["terminal_export"]["sha256"] = write(tmp_path / "terminal-execution-export.json", exported)
    elif mutation == "non_object_stage": receipt["stages"][0] = "first_case_started"
    if mutation not in {"cleanup_failed", "process_failed"}:
        completion["receipt_sha256"] = write(tmp_path / "execution-contour-receipt.json", receipt)
    errors = validate_completion(tmp_path, run=run, first_case=first,
                                 completion=completion, cleanup=cleanup, process_exit=process_exit)
    assert expected in errors


def test_completion_evidence_rejects_tampered_receipt_and_failure_artifact(tmp_path):
    run, first, completion, cleanup, receipt = evidence(tmp_path)
    receipt["report_id"] = "tampered"
    write(tmp_path / "execution-contour-receipt.json", receipt)
    (tmp_path / "cleanup-deferred.json").write_text("{}")
    errors = validate_completion(tmp_path, run=run, first_case=first,
                                 completion=completion, cleanup=cleanup, process_exit=0)
    assert "COMPLETION_RECEIPT_INVALID" not in errors
    assert "COMPOSITE_COMPLETION_INVALID" in errors
    assert "FAILURE_ARTIFACT:cleanup-deferred" in errors
