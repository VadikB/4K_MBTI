"""Run authorized ARCH-A06 PM-03 rows with real provider and external evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("A06_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Api import m5_functional_generation_service as functional_service
from Api.llm.deepseek_gateway import DeepSeekGateway
from scripts.run_functional_personalization_matrix import build_synthetic_profile

MATRIX = ROOT / "tests/fixtures/arch_a06/acceptance-matrix-v1.json"
SAFE_ERROR = re.compile(r"^[A-Z0-9_.:-]{1,160}$")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def require_external_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError("A06_OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")
    return resolved


def safe_error_code(exc: Exception) -> str:
    value = str(exc).strip()
    return value if SAFE_ERROR.fullmatch(value) else "DETAILS_REDACTED"


def source_row(matrix: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    function = matrix["functions"][row["function"]]
    return {
        "TestID": row["id"],
        "CaseID": row["case_id"],
        "BaseRole": "specialist_expert",
        "Профессиональный контекст": function["label"],
        "Подтверждённая для учебного теста деятельность": function["activity"],
        "Возможное отображение": function["authority"],
        "Данные": "SYNTHETIC_TEST_PROFILE; ARCH-A06; не реальный пользователь",
    }


def run_row(matrix: dict[str, Any], row: dict[str, Any], gateway: Any) -> dict[str, Any]:
    profile = build_synthetic_profile(source_row(matrix, row))
    snapshot = functional_service.build_input_snapshot(
        case_id=row["case_id"], profile=profile, operation_id=row["id"],
        synthetic=True, profile_checksum=profile["checksum"],
    )
    prepared = functional_service.prepare(snapshot, gateway)
    trace = None
    if prepared["admitted_for_participant"]:
        trace = functional_service.build_persistence_trace(snapshot, prepared)
    aggregation = prepared["tester"]["aggregation"]
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "matrix_id": matrix["matrix_id"],
        "row": row,
        "synthetic_test_data": True,
        "package": snapshot["refs"]["package"],
        "input_snapshot_checksum": prepared["input_snapshot_checksum"],
        "generation": prepared["deterministic_validation"],
        "generation_operation": prepared["generation_operation"],
        "repair": prepared["repair"],
        "tester": prepared["tester"],
        "admission": {
            "status": "PASS" if prepared["admitted_for_participant"] else "FAIL",
            "admitted_for_participant": prepared["admitted_for_participant"],
            "aggregation_status": aggregation["status"],
        },
        "candidate_checksum": prepared["candidate_checksum"],
        "persistence_trace": trace,
        "http_runtime": "NOT_RUN",
        "m6": "NOT_RUN",
        "m8": "NOT_RUN",
        "methodology_status": "NOT_RUN",
        "reliability_status": "NOT_RUN",
    }


def select_rows(matrix: dict[str, Any], ids: list[str], run_all: bool) -> list[dict[str, Any]]:
    rows = matrix["rows"]
    if run_all and ids:
        raise ValueError("A06_SELECT_ALL_OR_ROWS")
    if run_all:
        return rows
    selected = ids or [rows[0]["id"]]
    unknown = sorted(set(selected) - {row["id"] for row in rows})
    if unknown:
        raise ValueError(f"A06_UNKNOWN_ROWS:{','.join(unknown)}")
    return [row for row in rows if row["id"] in set(selected)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--row", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = require_external_output(args.output)
    matrix = read_json(MATRIX)
    rows = select_rows(matrix, args.row, args.all)
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    outcomes = []
    for row in rows:
        target = output / "rows" / f"{row['id'].lower()}.json"
        if target.exists() and not args.force:
            existing = read_json(target)
            outcomes.append({"id": row["id"], "status": existing["admission"]["status"], "resumed": True})
            continue
        try:
            result = run_row(matrix, row, gateway)
            write_json(target, result)
            status = result["admission"]["status"]
            outcomes.append({"id": row["id"], "status": status, "resumed": False})
            print(f"{row['id']} admission={status}", flush=True)
        except Exception as exc:
            failure = {
                "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "matrix_id": matrix["matrix_id"], "row": row,
                "synthetic_test_data": True, "status": "TECHNICAL_ERROR",
                "error_type": type(exc).__name__, "error_code": safe_error_code(exc),
            }
            write_json(output / "failures" / f"{row['id'].lower()}.json", failure)
            outcomes.append({"id": row["id"], "status": "TECHNICAL_ERROR", "resumed": False})
            print(f"{row['id']} TECHNICAL_ERROR {type(exc).__name__}: {safe_error_code(exc)}", flush=True)
            break
    summary = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "matrix_id": matrix["matrix_id"], "selected": len(rows), "outcomes": outcomes,
        "http_runtime": "NOT_RUN", "m6": "NOT_RUN", "m8": "NOT_RUN",
        "methodology_status": "NOT_RUN", "reliability_status": "NOT_RUN",
    }
    write_json(output / "summary.json", summary)
    if any(item["status"] == "TECHNICAL_ERROR" for item in outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
