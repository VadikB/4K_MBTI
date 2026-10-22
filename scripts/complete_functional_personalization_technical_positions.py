"""Завершить tester v2 для двух AS, чья генерация была успешно сохранена."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from scripts.retest_functional_personalization_v2 import retest_one, write_json
from scripts.run_functional_personalization_matrix import DEFAULT_OUTPUT, read_json

OUTPUT = DEFAULT_OUTPUT / "technical-recovery-v2"
TARGETS = ("PROFILE.06.1", "PROFILE.09.1")


def main() -> None:
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results, errors = [], []
    for attempt, test_id in enumerate(TARGETS, start=1):
        stem = test_id.lower().replace(".", "-")
        generation_path = DEFAULT_OUTPUT / "generations" / f"{stem}.json"
        generation = read_json(generation_path)
        try:
            tested = retest_one(generation, gateway)
            tested["technical_recovery"] = {
                "attempt": 1,
                "stage": "tester_v2",
                "generation_artifact": str(generation_path.relative_to(ROOT)),
                "generation_candidate_checksum": generation["candidate_checksum"],
                "historical_failure": "truncated" if test_id == "PROFILE.06.1" else "timeout",
            }
            write_json(OUTPUT / "tester" / f"{stem}.json", tested)
            results.append({
                "test_id": test_id, "status": tested["aggregation"]["status"],
                "admitted": tested["aggregation"]["admitted_for_participant"],
                "candidate_checksum": tested["candidate_checksum"],
                "provider_operation": tested["provider_operation"],
            })
            print(test_id, tested["aggregation"]["status"], flush=True)
        except Exception as exc:
            errors.append({"test_id": test_id, "attempt": 1, "stage": "tester_v2",
                           "error_type": type(exc).__name__, "error": str(exc)})
            print(test_id, "ERROR", type(exc).__name__, str(exc), flush=True)
    write_json(OUTPUT / "summary.json", {
        "schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
        "requested_model": gateway.model, "targets": len(TARGETS),
        "completed": len(results), "results": results, "errors": errors,
    })
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
