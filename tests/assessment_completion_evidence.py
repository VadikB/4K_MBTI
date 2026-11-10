"""Fail-closed validation for the EXEC-CONTOUR composite terminal receipt."""
from __future__ import annotations

import hashlib
import json
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
    if receipt.get("contract") != "assessment-execution-contour/1":
        errors.append("COMPOSITE_CONTRACT_INVALID")
    run_id = run.get("run_id")
    if not run_id or any(value.get("run_id") != run_id for value in (receipt, completion, cleanup)):
        errors.append("COMPOSITE_RUN_MISMATCH")
    cycle = first_case.get("cycle", {}).get("cycle_id")
    initial_as = first_case.get("assessment_situation", {}).get("assessment_situation_id")
    if receipt.get("cycle_id") != cycle or receipt.get("initial_assessment_situation_id") != initial_as:
        errors.append("COMPOSITE_CONTEXT_MISMATCH")
    stages = receipt.get("stages")
    if not isinstance(stages, list) or not stages:
        errors.append("COMPOSITE_STAGES_MISSING")
        stages = []
    names = [stage.get("stage") for stage in stages if isinstance(stage, dict)]
    required = ("first_case_started", "assessment_situation_closed", "report_opened")
    if any(name not in names for name in required) or names[:1] != ["first_case_started"]:
        errors.append("COMPOSITE_STAGE_CHAIN_INVALID")
    report_stage = next((stage for stage in stages if isinstance(stage, dict)
                         and stage.get("stage") == "report_opened"), {})
    if (receipt.get("report_opened") is not True or report_stage.get("status") != "completed"
            or report_stage.get("cycle_id") != cycle or not report_stage.get("report_id")
            or report_stage.get("report_id") != receipt.get("report_id")):
        errors.append("REPORT_OPEN_NOT_PROVEN")
    screenshot = directory / str(report_stage.get("screenshot", ""))
    try:
        if (not screenshot.is_file() or screenshot.is_symlink()
                or screenshot.resolve().parent != directory.resolve()
                or hashlib.sha256(screenshot.read_bytes()).hexdigest() != report_stage.get("screenshot_sha256")):
            raise ValueError
    except (OSError, ValueError):
        errors.append("REPORT_SCREENSHOT_INVALID")
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
    for name in ("failure.json", "failure-receipt.json", "cleanup-deferred.json"):
        if (directory / name).exists():
            errors.append(f"FAILURE_ARTIFACT:{name[:-5]}")
    return errors
