"""Build the ARCH-A06 evidence manifest without promoting historical evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "tests/fixtures/arch_a06/acceptance-matrix-v1.json"
HISTORICAL = ROOT / "docs/evc/evidence/pers-functional-personalization/protocol-v2-final-summary.json"
DEFAULT_OUTPUT = ROOT / "docs/evc/evidence/arch-a06/acceptance-manifest.json"


def build_manifest(*, commit: str, application_version: str) -> dict:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    historical_by_case: dict[str, list[dict]] = {}
    for item in historical["positions"]:
        historical_by_case.setdefault(item["case_ref"]["case_id"], []).append({
            "test_id": item["test_id"],
            "as_sha256": item["assessment_situation_ref"]["sha256"],
            "final_status": item["final_status"],
            "scope": "historical_profile_matrix_only",
        })

    required = matrix["required_evidence"]
    rows = []
    for row in matrix["rows"]:
        rows.append({
            **row,
            "function_profile": matrix["functions"][row["function"]],
            "status": "NOT_RUN",
            "evidence": {name: None for name in required},
            "contract_checks": {
                "http_preparation_safe_projection": {
                    "status": "PASS",
                    "test": "tests/e2e/test_m5_runtime_http.py::test_a06_case_function_matrix_uses_public_safe_preparation_contract",
                    "scope": "request/ownership/idempotency input and participant-safe response shape; runtime execution NOT_RUN",
                },
            },
            "historical_comparison": historical_by_case.get(row["case_id"], []),
            "methodology_status": "NOT_RUN",
            "reliability_status": "NOT_RUN",
        })
    return {
        "schema_version": 1,
        "matrix_id": matrix["matrix_id"],
        "commit": commit,
        "application_version": application_version,
        "synthetic_test_data": True,
        "required_evidence": required,
        "rows": rows,
        "counts": {"total": len(rows), "PASS": 0, "NOT_RUN": len(rows)},
        "limitations": [
            "Historical 27-profile evidence is comparison-only and is not the Sales/HR/IT Cartesian product.",
            "Controlled adapters do not prove real-provider behavior or methodological acceptance.",
            "A row remains NOT_RUN until every required evidence reference is recorded.",
            "HTTP preparation contract PASS is not HTTP runtime, M6, or M8 acceptance.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--application-version", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = build_manifest(commit=args.commit, application_version=args.application_version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
