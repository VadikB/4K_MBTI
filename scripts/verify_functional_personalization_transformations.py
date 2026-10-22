"""Доказать байтовую нейтральность envelope normalization и локализовать repair."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Api.m5_functional_personalization import extract_candidate_as
from scripts.retest_functional_personalization_v2 import write_json
from scripts.run_functional_personalization_matrix import DEFAULT_OUTPUT, digest, read_json


def changed_paths(before: Any, after: Any, prefix: str = "$") -> list[str]:
    if type(before) is not type(after):
        return [prefix]
    if isinstance(before, dict):
        paths = []
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after:
                paths.append(f"{prefix}.{key}")
            else:
                paths.extend(changed_paths(before[key], after[key], f"{prefix}.{key}"))
        return paths
    if isinstance(before, list):
        paths = []
        if len(before) != len(after):
            paths.append(prefix + ".length")
        for index, (left, right) in enumerate(zip(before, after)):
            paths.extend(changed_paths(left, right, f"{prefix}[{index}]"))
        return paths
    return [] if before == after else [prefix]


def main() -> None:
    normalized_summary = read_json(DEFAULT_OUTPUT / "normalized-v2/summary.json")
    envelopes = []
    for item in normalized_summary["results"]:
        test_id = item["test_id"]; stem = test_id.lower().replace(".", "-")
        source = read_json(DEFAULT_OUTPUT / "generations" / f"{stem}.json")
        normalized = read_json(DEFAULT_OUTPUT / "normalized-v2/generations" / f"{stem}.json")
        extracted, depth = extract_candidate_as(source["candidate_as"])
        if depth == 0:
            continue
        identical = digest(extracted) == digest(normalized["candidate_as"])
        envelopes.append({"test_id": test_id, "depth": depth,
                          "extracted_sha256": digest(extracted),
                          "normalized_sha256": digest(normalized["candidate_as"]),
                          "content_identical": identical})
        if not identical:
            raise ValueError(f"ENVELOPE_NORMALIZATION_CHANGED_CONTENT:{test_id}")
    if len(envelopes) != 14:
        raise ValueError(f"EXPECTED_14_KNOWN_ENVELOPES:{len(envelopes)}")
    before = read_json(DEFAULT_OUTPUT / "normalized-v2/generations/profile-02-2.json")
    after = read_json(DEFAULT_OUTPUT / "remediation-v2/generations/profile-02-2.json")
    repair_paths = changed_paths(before["candidate_as"], after["candidate_as"])
    required_prefixes = ("$.Материалы", "$.Словарь", "$.IndicatorObservability", "$.Числовые связи для QA")
    coverage = {prefix: any(path.startswith(prefix) for path in repair_paths) for prefix in required_prefixes}
    if not all(coverage.values()):
        raise ValueError(f"PROFILE_02_2_DEPENDENCY_NOT_REPAIRED:{coverage}")
    tester = read_json(DEFAULT_OUTPUT / "remediation-v2/tester/profile-02-2.json")
    write_json(DEFAULT_OUTPUT / "transformation-verification.json", {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "known_response_envelopes": envelopes,
        "unknown_structure_policy": "preserve_and_fail_downstream_validation",
        "profile_02_2": {
            "before_sha256": before["candidate_checksum"], "after_sha256": after["candidate_checksum"],
            "changed_paths": repair_paths, "dependent_area_coverage": coverage,
            "repair_attempt_limit": 2, "attempts_used": 1,
            "final_deterministic_status": after["deterministic_validation"]["status"],
            "final_semantic_status": tester["aggregation"]["status"],
        },
    })


if __name__ == "__main__":
    main()
