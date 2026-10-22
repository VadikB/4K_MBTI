"""Собрать итоговую судьбу 27 позиций без изменения исходных артефактов."""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.retest_functional_personalization_v2 import write_json
from scripts.run_functional_personalization_matrix import DEFAULT_OUTPUT, SOURCE, read_json


def main() -> None:
    matrix = read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")
    original = read_json(DEFAULT_OUTPUT / "matrix-summary.json")
    first = read_json(DEFAULT_OUTPUT / "tester-v2/summary.json")
    normalized = read_json(DEFAULT_OUTPUT / "normalized-v2/summary.json")
    remediated = read_json(DEFAULT_OUTPUT / "remediation-v2/summary.json")
    original_results = {item["test_id"]: item for item in original["results"]}
    original_errors = {item["test_id"]: item for item in original["errors"]}
    first_results = {item["test_id"]: item for item in first["comparison"]}
    normalized_results = {item["test_id"]: item for item in normalized["results"]}
    remediation_results = {item["test_id"]: item for item in remediated["results"]}
    positions = []
    for row in matrix:
        test_id = row["TestID"]
        if test_id in original_errors:
            error = original_errors[test_id]
            positions.append({
                "test_id": test_id, "case_id": row["CaseID"],
                "original_status": "TECHNICAL_ERROR", "protocol_v2_initial_status": "NOT_RUN",
                "final_status": "TECHNICAL_ERROR", "admitted": False,
                "fate": "generation_or_tester_chain_not_completed",
                "reason": error["error"], "error_type": error["error_type"],
            })
            continue
        initial = first_results[test_id]
        final_status = initial["new_status"]
        final_path = f"docs/evc/evidence/pers-functional-personalization/tester-v2/{test_id.lower().replace('.', '-')}.json"
        transformation = "none"
        if test_id in normalized_results:
            final_status = normalized_results[test_id]["status"]
            final_path = f"docs/evc/evidence/pers-functional-personalization/normalized-v2/tester/{test_id.lower().replace('.', '-')}.json"
            transformation = "known_response_envelope_removed"
        if test_id in remediation_results:
            final_status = remediation_results[test_id]["final_status"]
            final_path = f"docs/evc/evidence/pers-functional-personalization/remediation-v2/tester/{test_id.lower().replace('.', '-')}.json"
            transformation = "localized_blocker_repair"
        positions.append({
            "test_id": test_id, "case_id": row["CaseID"],
            "original_status": original_results[test_id]["tester"],
            "protocol_v2_initial_status": initial["new_status"],
            "final_status": final_status,
            "admitted": final_status in {"PASS", "PASS_WITH_WARNINGS"},
            "transformation": transformation, "final_tester_path": final_path,
        })
    report = {
        "schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": first["protocol"], "matrix_total": len(positions),
        "final_status_counts": dict(Counter(item["final_status"] for item in positions)),
        "admitted": sum(item["admitted"] for item in positions),
        "positions": positions,
        "resolved_cause_groups": [
            {"code": "INVALID_NOT_APPLICABLE_AGGREGATION", "affected": 22,
             "resolution": "Системно неприменимая conditional-проверка больше не считается невыполненной."},
            {"code": "KNOWN_RESPONSE_ENVELOPE", "affected": 14,
             "resolution": "Строго опознанный response envelope снят; AS не изменялась; tester v2 повторён."},
            {"code": "PROFESSIONAL_SUBJECT_MISMATCH", "affected": 1, "test_ids": ["PROFILE.02.2"],
             "paths": ["Материалы[0..6].Текст", "Словарь", "IndicatorObservability", "Числовые связи для QA"],
             "requirement_refs": ["common.professional_consistency", "common.scenario_executability", "invariant:CASE.SPEC.02.I01"],
             "resolution": "Все зависимые фрагменты приведены к одному предмету; повторный tester v2 = PASS."},
        ],
        "remaining_blockers": [item for item in positions if item["final_status"] != "PASS"],
    }
    write_json(DEFAULT_OUTPUT / "protocol-v2-final-summary.json", report)


if __name__ == "__main__":
    main()
