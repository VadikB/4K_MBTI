"""Локально исправить подтверждённые blocker-дефекты и повторить tester v2."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.m5_functional_personalization import extract_candidate_as
from Api.m5_functional_tester import build_applicability_plan
from scripts.retest_functional_personalization_v2 import retest_one, write_json
from scripts.run_functional_personalization_matrix import (
    DEFAULT_OUTPUT, SOURCE, _case_source, deterministic_checks, digest,
    load_inputs, read_json,
)

OUTPUT = DEFAULT_OUTPUT / "remediation-v2"


def repair_v2(generation: dict, tested: dict, row: dict, gateway: DeepSeekGateway, attempt: int) -> dict:
    inputs = load_inputs(row)
    plan = build_applicability_plan(inputs["case"])
    aggregation = tested["aggregation"]
    localized = aggregation["blocking_failures"] + aggregation["review_required"]
    payload = {
        "profile": generation["profile"],
        "case": inputs["case"],
        "author_as_example": inputs["author_as_example"],
        "candidate_as": generation["candidate_as"],
        "applicability_plan": plan,
        "localized_failed_checks": localized,
        "repair_constraints": {
            "repair_every_localized_path_and_all_dependent_references": True,
            "keep_professional_subject_consistent_in_intro_materials_dictionary_characters_rules_observability_and_qa": True,
            "copy_locked_fields_exactly_from_author_as_example": [
                "CaseID", "CaseVersion", "BaseRole", "IndicatorIDs", "Версии M2"
            ],
            "preserve_case_invariants_uncertainty_character_count_event_count_and_information_load": True,
            "do_not_create_consent_authority_resources_evidence_scores_or_participant_answers": True,
            "do_not_weaken_or_delete_a_requirement_to_make_a_check_pass": True,
            "output": "Верни только исправленный полный JSON-объект AS, не входной конверт."
        },
    }
    instruction = (SOURCE / "07_generation/Generator_instruction_v0.2.txt").read_text(encoding="utf-8")
    messages = [
        {"role": "system", "content": instruction},
        {"role": "system", "content": "Это локальное исправление. Не меняй Case, цели, инварианты и серьёзность находок. Устрани причину во всех зависимых местах."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    operation_id = f"repair-v2:{generation['test_id']}:{attempt}:{digest(messages)[:12]}"
    response = gateway.chat_with_trace(
        messages, temperature=0.1, timeout_seconds=300, max_tokens=32768,
        routing_key=operation_id, response_format={"type": "json_object"},
    )
    candidate, envelope_depth = extract_candidate_as(json.loads(response.content))
    repaired = {
        **generation,
        "schema_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_as": candidate,
        "candidate_checksum": digest(candidate),
        "deterministic_validation": deterministic_checks(inputs, candidate),
        "response_envelope_depth": envelope_depth,
        "remediation": {
            "attempt": attempt,
            "source_candidate_checksum": generation["candidate_checksum"],
            "source_tester_status": aggregation["status"],
            "failed_check_ids": [item["check_id"] for item in localized],
            "provider_operation_id": operation_id,
        },
    }
    return repaired


def main() -> None:
    summary = read_json(DEFAULT_OUTPUT / "normalized-v2/summary.json")
    targets = [item for item in summary["results"] if item["status"] in {"FAIL", "REVIEW_REQUIRED"}]
    rows = {row["TestID"]: row for row in read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")}
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results = []
    for target in targets:
        test_id = target["test_id"]; stem = test_id.lower().replace(".", "-")
        generation = read_json(DEFAULT_OUTPUT / "normalized-v2/generations" / f"{stem}.json")
        tested = read_json(DEFAULT_OUTPUT / "normalized-v2/tester" / f"{stem}.json")
        history = []
        for attempt in range(1, 3):
            write_json(OUTPUT / "attempts" / stem / f"{attempt:02d}-input-generation.json", generation)
            write_json(OUTPUT / "attempts" / stem / f"{attempt:02d}-input-tester.json", tested)
            generation = repair_v2(generation, tested, rows[test_id], gateway, attempt)
            tested = retest_one(generation, gateway)
            history.append({"attempt": attempt, "status": tested["aggregation"]["status"], "candidate_checksum": generation["candidate_checksum"]})
            print(test_id, "attempt", attempt, tested["aggregation"]["status"], flush=True)
            if tested["aggregation"]["status"] in {"PASS", "PASS_WITH_WARNINGS"}:
                break
        write_json(OUTPUT / "generations" / f"{stem}.json", generation)
        write_json(OUTPUT / "tester" / f"{stem}.json", tested)
        results.append({"test_id": test_id, "case_id": target["case_id"], "history": history,
                        "final_status": tested["aggregation"]["status"],
                        "admitted": tested["aggregation"]["admitted_for_participant"]})
    write_json(OUTPUT / "summary.json", {"schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
                                         "selected": len(targets), "results": results})


if __name__ == "__main__":
    main()
