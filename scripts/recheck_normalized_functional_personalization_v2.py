"""Повторно проверить отклонённые AS после снятия известного response envelope.

Исходные generation/tester-v2 артефакты не изменяются.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.m5_functional_personalization import extract_candidate_as
from scripts.retest_functional_personalization_v2 import retest_one, write_json
from scripts.run_functional_personalization_matrix import (
    DEFAULT_OUTPUT, SOURCE, deterministic_checks, digest,
    load_inputs, read_json,
)

OUTPUT = DEFAULT_OUTPUT / "normalized-v2"


def main() -> None:
    old_summary = read_json(DEFAULT_OUTPUT / "tester-v2/summary.json")
    failed = {item["test_id"] for item in old_summary["comparison"] if item["new_status"] == "FAIL"}
    rows = {row["TestID"]: row for row in read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")}
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")

    def execute(test_id: str) -> dict:
        stem = test_id.lower().replace(".", "-")
        original = read_json(DEFAULT_OUTPUT / "generations" / f"{stem}.json")
        candidate, depth = extract_candidate_as(original["candidate_as"])
        normalized = {
            **original,
            "schema_version": 2,
            "candidate_as": candidate,
            "candidate_checksum": digest(candidate),
            "deterministic_validation": deterministic_checks(load_inputs(rows[test_id]), candidate),
            "normalization": {
                "kind": "known_response_envelope",
                "depth": depth,
                "source_candidate_checksum": original["candidate_checksum"],
            },
        }
        write_json(OUTPUT / "generations" / f"{stem}.json", normalized)
        tested = retest_one(normalized, gateway)
        write_json(OUTPUT / "tester" / f"{stem}.json", tested)
        return tested

    results, errors = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(execute, test_id): test_id for test_id in sorted(failed)}
        for future in as_completed(futures):
            test_id = futures[future]
            try:
                result = future.result(); results.append(result)
                print(test_id, result["aggregation"]["status"], flush=True)
            except Exception as exc:
                errors.append({"test_id": test_id, "error_type": type(exc).__name__, "error": str(exc)})
                print(test_id, "ERROR", type(exc).__name__, str(exc), flush=True)
    summary = {
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_protocol_summary": str((DEFAULT_OUTPUT / "tester-v2/summary.json").relative_to(ROOT)),
        "selected": len(failed), "completed": len(results), "errors": errors,
        "status_counts": dict(Counter(item["aggregation"]["status"] for item in results)),
        "results": sorted([{
            "test_id": item["test_id"], "case_id": item["case_id"],
            "status": item["aggregation"]["status"],
            "admitted": item["aggregation"]["admitted_for_participant"],
            "candidate_checksum": item["candidate_checksum"],
        } for item in results], key=lambda item: item["test_id"]),
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps({"completed": len(results), "errors": len(errors), "status_counts": summary["status_counts"]}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
