"""Fail-closed validation for the EXEC-CONTOUR composite terminal receipt."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def _read_object(directory: Path, name: str, errors: list[str]) -> tuple[dict, Path]:
    path = directory / f"{name}.json"
    try:
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise ValueError("UNSAFE_RECEIPT_PATH")
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("JSON_OBJECT_REQUIRED")
        return value, path
    except (OSError, ValueError, TypeError):
        errors.append(f"MISSING_OR_INVALID:{name}")
        return {}, path


def validate_completion(directory: Path, *, run: dict, first_case: dict,
                        completion: dict, cleanup: dict, process_exit: int) -> list[str]:
    errors: list[str] = []
    receipt, receipt_path = _read_object(directory, "execution-contour-receipt", errors)
    if receipt.get("contract") != "assessment-execution-contour/2" or run.get("profile") != "assessment-execution-contour/2":
        errors.append("COMPOSITE_CONTRACT_INVALID")
    run_id = run.get("run_id")
    code = run.get('code') or {}
    if (not isinstance(code, dict) or not re.fullmatch(r'[a-f0-9]{40}', str(code.get('sha', '')))
            or not code.get('branch')
            or not isinstance(code.get('files'), dict)
            or any(not re.fullmatch(r'[a-f0-9]{64}', str(code['files'].get(name, '')))
                   for name in ('tests/assessment_completion_evidence.py',
                                'tests/assessment_execution_export.py'))):
        errors.append('CODE_IDENTITY_MISSING')
    if not run_id or any(value.get("run_id") != run_id for value in (receipt, completion, cleanup)):
        errors.append("COMPOSITE_RUN_MISMATCH")
    cycle = first_case.get("cycle", {}).get("cycle_id")
    initial_as = first_case.get("assessment_situation", {}).get("assessment_situation_id")
    if (not isinstance(cycle, str) or not cycle or not isinstance(initial_as, str) or not initial_as
            or receipt.get("cycle_id") != cycle or receipt.get("initial_assessment_situation_id") != initial_as):
        errors.append("COMPOSITE_CONTEXT_MISMATCH")
    first_path = directory / 'first-case-receipt.json'
    first_link = receipt.get('first_case_receipt') or {}
    try:
        first_hash = hashlib.sha256(first_path.read_bytes()).hexdigest()
    except OSError:
        first_hash = None
    if (first_path.is_symlink() or first_path.resolve().parent != directory.resolve()
            or first_link.get('file') != first_path.name or first_link.get('sha256') != first_hash
            or first_link.get('assessment_answers') != 0 or first_case.get('assessment_answers') != 0):
        errors.append('FIRST_CASE_LINK_INVALID')
    stages = receipt.get("stages")
    if not isinstance(stages, list) or not stages:
        errors.append("COMPOSITE_STAGES_MISSING")
        stages = []
    names = [stage.get("stage") for stage in stages if isinstance(stage, dict)]
    closings = [stage for stage in stages if isinstance(stage, dict) and stage.get('stage') == 'assessment_situation_closed']
    expected = ['first_case_started'] + ['assessment_situation_closed'] * len(closings) + ['collection_closed', 'report_opened']
    if (names != expected or len(names) != len(stages) or not closings
            or type(receipt.get('situation_count')) is not int
            or receipt.get('situation_count') != len(closings)):
        errors.append("COMPOSITE_STAGE_CHAIN_INVALID")
    first_stage = stages[0] if stages and isinstance(stages[0], dict) else {}
    if (first_stage.get('status') != 'milestone' or first_stage.get('cycle_id') != cycle
            or first_stage.get('assessment_situation_id') != initial_as):
        errors.append('FIRST_CASE_STAGE_INVALID')
    seen = set()
    initial_session = ((first_case.get('sessions') or [{}])[0] or {}).get('session_id')
    for position, stage in enumerate(closings, 1):
        as_id = stage.get('assessment_situation_id')
        if (stage.get('status') != 'completed' or stage.get('cycle_id') != cycle
                or type(stage.get('position')) is not int or stage.get('position') != position
                or not isinstance(as_id, str) or not as_id
                or (position == 1 and as_id != initial_as) or as_id in seen
                or not stage.get('session_id') or (position == 1 and initial_session
                    and stage.get('session_id') != initial_session)
                or stage.get('close_status') not in ('closed', 'terminated')
                or not stage.get('final_handoff_id')
                or stage.get('finalization_status') not in ('pending', 'queued')
                or type(stage.get('assessee_turns_before')) is not int
                or stage['assessee_turns_before'] < 0
                or any(type(stage.get(key)) is not int or stage[key] < 0
                       for key in ('assessee_turns', 'interim_handoffs', 'c54_receipts'))):
            errors.append('AS_CLOSE_STAGE_INVALID')
        if type(stage.get('assessee_turns')) is int and type(stage.get('assessee_turns_before')) is int \
                and stage['assessee_turns'] < stage['assessee_turns_before']:
            errors.append('AS_TURN_COUNT_REGRESSED')
        seen.add(as_id)
    close_stage = stages[-2] if len(stages) >= 2 and isinstance(stages[-2], dict) else {}
    if (close_stage.get('stage') != 'collection_closed' or close_stage.get('status') != 'completed'
            or close_stage.get('cycle_id') != cycle or not close_stage.get('close_reason')
            or not close_stage.get('closed_at') or not close_stage.get('c46_revision_id')):
        errors.append('COLLECTION_CLOSE_STAGE_INVALID')
    report_stage = stages[-1] if stages and isinstance(stages[-1], dict) else {}
    if (receipt.get("report_opened") is not True or report_stage.get("status") != "completed"
            or report_stage.get("cycle_id") != cycle or not report_stage.get("report_id")
            or report_stage.get("report_id") != receipt.get("report_id")
            or not report_stage.get('results_revision_id')
            or report_stage.get('results_revision_id') != receipt.get('results_revision_id')
            or type(report_stage.get('report_revision_no')) is not int
            or not report_stage.get('owner_user_id')):
        errors.append("REPORT_OPEN_NOT_PROVEN")
    screenshot = directory / str(report_stage.get("screenshot", ""))
    try:
        if (not screenshot.is_file() or screenshot.is_symlink()
                or screenshot.resolve().parent != directory.resolve()
                or hashlib.sha256(screenshot.read_bytes()).hexdigest() != report_stage.get("screenshot_sha256")):
            raise ValueError
    except (OSError, ValueError):
        errors.append("REPORT_SCREENSHOT_INVALID")
    export_link = receipt.get('terminal_export') or {}
    exported, export_path = _read_object(directory, 'terminal-execution-export', errors)
    try:
        export_hash = hashlib.sha256(export_path.read_bytes()).hexdigest()
    except OSError:
        export_hash = None
    if export_link.get('file') != export_path.name or export_link.get('sha256') != export_hash:
        errors.append('TERMINAL_EXPORT_HASH_INVALID')
    if (exported.get('run_id') != run_id or exported.get('cycle_id') != cycle
            or exported.get('collection_status') not in ('collection_closed', 'calculation_pending', 'calculated')
            or exported.get('close_reason') != close_stage.get('close_reason')
            or exported.get('collection_closed_at') != close_stage.get('closed_at')
            or (exported.get('c46') or {}).get('id') != close_stage.get('c46_revision_id')):
        errors.append('TERMINAL_COLLECTION_MISMATCH')
    situations = exported.get('situations')
    if not isinstance(situations, list):
        situations = []
    closed = [item for item in situations if isinstance(item, dict)
              and item.get('status') in ('closed', 'terminated')]
    if len(closed) != len(closings):
        errors.append('TERMINAL_AS_COUNT_MISMATCH')
    for stage in closings:
        item = next((item for item in closed
                     if item.get('assessment_situation_id') == stage.get('assessment_situation_id')), None)
        if (item is None or item.get('status') != stage.get('close_status')
                or item.get('session_id') != stage.get('session_id')
                or item.get('final_handoff_id') != stage.get('final_handoff_id')
                or item.get('finalization_status') != stage.get('finalization_status')
                or any(item.get(key) != stage.get(key)
                       for key in ('assessee_turns', 'interim_handoffs', 'c54_receipts'))):
            errors.append('TERMINAL_AS_READBACK_MISMATCH')
    report = exported.get('report') or {}
    results = exported.get('results') or {}
    pipeline = exported.get('pipeline') or {}
    if (report.get('id') != report_stage.get('report_id')
            or report.get('result_revision_id') != results.get('id')
            or results.get('id') != report_stage.get('results_revision_id')
            or results.get('c46_revision_id') != (exported.get('c46') or {}).get('id')
            or report.get('revision_no') != report_stage.get('report_revision_no')
            or report.get('created_by') != report_stage.get('owner_user_id')
            or report_stage.get('owner_user_id') != exported.get('owner_user_id')
            or report.get('status') != 'ready' or report.get('audience') != 'assessee'
            or pipeline.get('status') != 'ready'
            or pipeline.get('latest_report_id') != report.get('id')
            or pipeline.get('latest_results_revision_id') != results.get('id')):
        errors.append('TERMINAL_REPORT_MISMATCH')
    try:
        digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    except OSError:
        digest = None
    if (completion.get("status") != "completed" or completion.get("exit_code") != 0
            or completion.get("receipt_file") != receipt_path.name
            or completion.get("receipt_sha256") != digest):
        errors.append("COMPOSITE_COMPLETION_INVALID")
    if process_exit != 0:
        errors.append("PROCESS_EXIT_NOT_ZERO")
    if not all(cleanup.get(key) is True for key in ("owner_verified", "database_absent", "state_absent")):
        errors.append("CLEANUP_NOT_VERIFIED")
    for name in ("failure.json", "failure-receipt.json", "cleanup-deferred.json", "cleanup-error.json"):
        if (directory / name).exists():
            errors.append(f"FAILURE_ARTIFACT:{name[:-5]}")
    return errors
