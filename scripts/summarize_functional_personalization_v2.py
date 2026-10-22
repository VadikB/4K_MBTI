"""Собрать итоговую судьбу 27 позиций без изменения исходных артефактов."""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.retest_functional_personalization_v2 import write_json
from scripts.run_functional_personalization_matrix import (
    DEFAULT_OUTPUT, SOURCE, deterministic_checks, digest, load_inputs, read_json,
)


def main() -> None:
    matrix = read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")
    original = read_json(DEFAULT_OUTPUT / "matrix-summary.json")
    first = read_json(DEFAULT_OUTPUT / "tester-v2/summary.json")
    normalized = read_json(DEFAULT_OUTPUT / "normalized-v2/summary.json")
    remediated = read_json(DEFAULT_OUTPUT / "remediation-v2/summary.json")
    recovery = read_json(DEFAULT_OUTPUT / "technical-recovery-v2/summary.json")
    original_results = {item["test_id"]: item for item in original["results"]}
    original_errors = {item["test_id"]: item for item in original["errors"]}
    first_results = {item["test_id"]: item for item in first["comparison"]}
    normalized_results = {item["test_id"]: item for item in normalized["results"]}
    remediation_results = {item["test_id"]: item for item in remediated["results"]}
    recovery_results = {item["test_id"]: item for item in recovery["results"]}
    positions = []
    consistency_errors = []
    for row in matrix:
        test_id = row["TestID"]
        if test_id in original_errors and test_id not in recovery_results:
            error = original_errors[test_id]
            positions.append({
                "test_id": test_id, "case_id": row["CaseID"],
                "original_status": "TECHNICAL_ERROR", "protocol_v2_initial_status": "NOT_RUN",
                "final_status": "TECHNICAL_ERROR", "admitted": False,
                "fate": "generation_or_tester_chain_not_completed",
                "reason": error["error"], "error_type": error["error_type"],
            })
            continue
        stem = test_id.lower().replace('.', '-')
        if test_id in recovery_results:
            initial = {"new_status": "NOT_RUN"}
            final_status = recovery_results[test_id]["status"]
            final_path = f"docs/evc/evidence/pers-functional-personalization/technical-recovery-v2/tester/{stem}.json"
            generation_path = f"docs/evc/evidence/pers-functional-personalization/generations/{stem}.json"
            transformation = "tester_technical_recovery"
        else:
            initial = first_results[test_id]
            final_status = initial["new_status"]
            final_path = f"docs/evc/evidence/pers-functional-personalization/tester-v2/{stem}.json"
            generation_path = original_results[test_id]["generation_path"]
            transformation = "none"
            if test_id in normalized_results:
                final_status = normalized_results[test_id]["status"]
                final_path = f"docs/evc/evidence/pers-functional-personalization/normalized-v2/tester/{stem}.json"
                generation_path = f"docs/evc/evidence/pers-functional-personalization/normalized-v2/generations/{stem}.json"
                transformation = "known_response_envelope_removed"
            if test_id in remediation_results:
                final_status = remediation_results[test_id]["final_status"]
                final_path = f"docs/evc/evidence/pers-functional-personalization/remediation-v2/tester/{stem}.json"
                generation_path = f"docs/evc/evidence/pers-functional-personalization/remediation-v2/generations/{stem}.json"
                transformation = "localized_blocker_repair"
        generation = read_json(ROOT / generation_path)
        tested = read_json(ROOT / final_path)
        inputs = load_inputs(row)
        final_deterministic = deterministic_checks(inputs, generation["candidate_as"])
        candidate_checksum = digest(generation["candidate_as"])
        if generation.get("candidate_checksum") != candidate_checksum:
            consistency_errors.append({"test_id": test_id, "code": "GENERATION_CHECKSUM_MISMATCH"})
        if tested.get("candidate_checksum") != candidate_checksum:
            consistency_errors.append({"test_id": test_id, "code": "TESTER_CANDIDATE_MISMATCH"})
        if final_deterministic["status"] != "PASS" and final_status in {"PASS", "PASS_WITH_WARNINGS"}:
            consistency_errors.append({"test_id": test_id, "code": "ADMISSION_WITH_DETERMINISTIC_FAILURE"})
        candidate = generation["candidate_as"]
        positions.append({
            "test_id": test_id,
            "case_ref": {"case_id": row["CaseID"], "case_version": candidate.get("CaseVersion"),
                         "source_path": generation["input_refs"]["case"]["path"],
                         "source_sha256": generation["input_refs"]["case"]["sha256"]},
            "profile_ref": {"schema_version": generation["profile"].get("schema_version"),
                            "snapshot_checksum": generation["profile"]["checksum"],
                            "test_id": generation["profile"]["source"]["test_id"]},
            "assessment_situation_ref": {"id": candidate.get("AssessmentSituationID"),
                                         "version": candidate.get("Version"),
                                         "sha256": candidate_checksum,
                                         "artifact_path": generation_path},
            "original_status": original_results[test_id]["tester"] if test_id in original_results else "TECHNICAL_ERROR",
            "original_deterministic_status": original_results[test_id]["generation"] if test_id in original_results else generation["deterministic_validation"]["status"],
            "protocol_v2_initial_status": initial["new_status"],
            "final_deterministic_status": final_deterministic["status"],
            "final_semantic_status": tested["aggregation"]["status"],
            "final_status": final_status,
            "admitted": final_status in {"PASS", "PASS_WITH_WARNINGS"},
            "transformation": transformation, "final_tester_path": final_path,
        })
    report = {
        "schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": first["protocol"], "matrix_total": len(positions),
        "historical_deterministic_counts": dict(Counter(
            item.get("generation", "NOT_RUN") for item in original["results"]
        )),
        "final_deterministic_counts": dict(Counter(
            item.get("final_deterministic_status", "NOT_RUN") for item in positions
        )),
        "final_status_counts": dict(Counter(item["final_status"] for item in positions)),
        "admitted": sum(item["admitted"] for item in positions),
        "consistency_errors": consistency_errors,
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
    if consistency_errors:
        raise ValueError(f"FINAL_AS_LINKAGE_INVALID:{consistency_errors}")
    write_json(DEFAULT_OUTPUT / "protocol-v2-final-summary.json", report)


if __name__ == "__main__":
    main()
