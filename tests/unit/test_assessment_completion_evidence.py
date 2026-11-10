import hashlib
import json

import pytest

from tests.assessment_completion_evidence import validate_completion


def write(path, value):
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence(tmp_path):
    run = {"run_id": "run-1", "database": "product4k_pytest_run1"}
    first = {"cycle": {"cycle_id": "cycle-1"},
             "assessment_situation": {"assessment_situation_id": "as-1"},
             "assessment_answers": 0}
    screenshot = tmp_path / "available-report.png"
    screenshot.write_bytes(b"synthetic png evidence")
    receipt = {
        "contract": "assessment-execution-contour/1", "run_id": "run-1",
        "cycle_id": "cycle-1", "initial_assessment_situation_id": "as-1",
        "report_id": "report-1", "report_opened": True,
        "stages": [
            {"stage": "first_case_started", "status": "milestone"},
            {"stage": "assessment_situation_closed", "status": "completed"},
            {"stage": "report_opened", "status": "completed", "cycle_id": "cycle-1",
             "report_id": "report-1", "screenshot": screenshot.name,
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
    if mutation in {"foreign_run", "foreign_cycle", "missing_stage", "report_not_opened"}:
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
