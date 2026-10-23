"""Отремонтировать неподтверждённые negative-фикстуры до запуска blind tester.

Скрипт передаёт mutator только требуемое изменение и отзыв независимого verifier.
Нарушенный инвариант, ожидаемый вердикт и объяснение отклонения tester не получает.
Неподтверждённые попытки сохраняются отдельно и не заменяют основной артефакт.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Api.llm.deepseek_gateway import DeepSeekGateway
from scripts.run_functional_negative_matrix_v2 import (
    FINAL, NEGATIVES, OUTPUT, ROOT, _test, mutate_full_as, write_json,
)
from scripts.run_functional_personalization_matrix import read_json
from scripts.verify_functional_negative_mutations import verify
from Api import m5_functional_generation_service as service


def artifact_path(negative_id: str) -> Path:
    return OUTPUT / "results" / f"{negative_id.lower().replace('.', '-')}.json"


def verification_feedback(existing: dict[str, Any] | None) -> str | None:
    if not existing:
        return None
    conclusion = (existing.get("mutation_verification") or {}).get("conclusion") or {}
    reason = conclusion.get("reason")
    return reason if isinstance(reason, str) and reason.strip() else None


def latest_verification_feedback(negative_id: str, existing: dict[str, Any] | None) -> str | None:
    directory = OUTPUT / "repair-attempts" / negative_id.lower().replace(".", "-")
    if directory.exists():
        for path in sorted(directory.glob("round-*.json"), reverse=True):
            attempt = read_json(path)
            if (attempt.get("mutation_verification") or {}).get("status") == "APPLIED":
                continue
            feedback = verification_feedback(attempt)
            if feedback:
                return feedback
    return verification_feedback(existing)


def latest_attempt(negative_id: str) -> dict[str, Any] | None:
    directory = OUTPUT / "repair-attempts" / negative_id.lower().replace(".", "-")
    paths = sorted(directory.glob("round-*.json"), reverse=True) if directory.exists() else []
    return read_json(paths[0]) if paths else None


def build_artifact(*, row: dict[str, Any], position: dict[str, Any], saved: dict[str, Any],
                   mutation: dict[str, Any], positive: dict[str, Any],
                   negative: dict[str, Any], mutation_verification: dict[str, Any]) -> dict[str, Any]:
    positive_admitted = positive["aggregation"]["admitted_for_participant"] is True
    negative_rejected = negative["aggregation"]["admitted_for_participant"] is False
    return {
        "schema_version": 1,
        "negative_id": row["NegativeID"],
        "case_id": row["CaseID"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_as": position["assessment_situation_ref"],
        "profile_ref": position["profile_ref"],
        "blind_boundary": {
            "tester_received_negative_id": False,
            "tester_received_violated_invariant": False,
            "tester_received_rejection_explanation": False,
            "tester_received_expected_result": False,
        },
        "requested_mutation": row["Ошибочная замена"],
        "expected_violated_invariant": row["Нарушенный инвариант"],
        "mutation": mutation,
        "mutation_verification": mutation_verification,
        "positive_control": positive,
        "negative_test": negative,
        "blind_tester_result": "PASS" if positive_admitted and negative_rejected else "FAIL",
        "result": "PASS" if positive_admitted and negative_rejected else "FAIL",
        "acceptance": {
            "positive_admitted": positive_admitted,
            "mutated_as_rejected": negative_rejected,
        },
    }


def repair_one(*, row: dict[str, Any], position: dict[str, Any], gateway: Any,
               max_rounds: int = 2, reuse_latest: bool = False) -> dict[str, Any]:
    path = artifact_path(row["NegativeID"])
    existing = read_json(path) if path.exists() else None
    feedback = latest_verification_feedback(row["NegativeID"], existing)
    saved = read_json(ROOT / position["assessment_situation_ref"]["artifact_path"])
    original = saved["candidate_as"]
    attempts: list[dict[str, Any]] = []
    reusable = latest_attempt(row["NegativeID"]) if reuse_latest else None
    for repair_round in range(1, max_rounds + 1):
        if repair_round == 1 and reusable and isinstance(reusable.get("mutation"), dict):
            mutation = copy.deepcopy(reusable["mutation"])
        else:
            mutation = mutate_full_as(
                row=row, original=original, gateway=gateway,
                verification_feedback=feedback,
            )
        provisional = {
            "source_as": position["assessment_situation_ref"],
            "mutation": mutation,
        }
        checked = verify(row, provisional, gateway)
        attempt = {
            "repair_round": repair_round,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "negative_id": row["NegativeID"],
            "requested_mutation": row["Ошибочная замена"],
            "feedback_used": feedback,
            "mutation": mutation,
            "mutation_verification": checked,
        }
        attempts.append(attempt)
        write_json(
            OUTPUT / "repair-attempts" / row["NegativeID"].lower().replace(".", "-")
            / f"round-{repair_round}.json",
            attempt,
        )
        if checked["status"] != "APPLIED":
            reason = checked.get("conclusion", {}).get("reason")
            feedback = reason if isinstance(reason, str) and reason.strip() else feedback
            continue
        snapshot = service.build_input_snapshot(
            case_id=row["CaseID"], profile=saved["profile"],
            operation_id=f"negative-v2-repair:{row['NegativeID']}", synthetic=True,
        )
        positive = (copy.deepcopy(existing["positive_control"])
                    if existing and existing.get("positive_control") else _test(snapshot, original, gateway))
        negative = _test(snapshot, mutation["candidate_as"], gateway)
        artifact = build_artifact(
            row=row, position=position, saved=saved, mutation=mutation,
            positive=positive, negative=negative, mutation_verification=checked,
        )
        write_json(path, artifact)
        return {"negative_id": row["NegativeID"], "status": "APPLIED",
                "result": artifact["result"], "round": repair_round}
    return {"negative_id": row["NegativeID"], "status": "NOT_APPLIED",
            "result": "TECHNICAL_ERROR", "round": max_rounds}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", help="Comma-separated NegativeID values")
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--reuse-latest", action="store_true")
    args = parser.parse_args()
    rows = read_json(NEGATIVES)
    summary = read_json(OUTPUT / "mutation-verification-summary.json")
    unresolved = {item["negative_id"] for item in summary["results"]
                  if item["mutation_status"] != "APPLIED"}
    unresolved.update(summary["missing_negative_ids"])
    if args.ids:
        requested = {item.strip() for item in args.ids.split(",") if item.strip()}
        unknown = requested - {row["NegativeID"] for row in rows}
        if unknown:
            raise SystemExit(f"Unknown NegativeID: {sorted(unknown)}")
        unresolved &= requested
    rows = [row for row in rows if row["NegativeID"] in unresolved]
    positions = read_json(FINAL)["positions"]
    by_case: dict[str, dict[str, Any]] = {}
    for position in positions:
        by_case.setdefault(position["case_ref"]["case_id"], position)
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results = []
    errors = []
    for row in rows:
        try:
            result = repair_one(row=row, position=by_case[row["CaseID"]], gateway=gateway,
                                max_rounds=max(1, args.max_rounds), reuse_latest=args.reuse_latest)
            results.append(result)
            print(result["negative_id"], result["status"], result["result"], flush=True)
        except Exception as exc:
            error = {"negative_id": row["NegativeID"], "error_type": type(exc).__name__,
                     "error": str(exc)}
            errors.append(error)
            print(row["NegativeID"], "ERROR", type(exc).__name__, str(exc), flush=True)
    run_summary = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected": len(rows),
        "results": results,
        "errors": errors,
    }
    write_json(OUTPUT / "repair-summary.json", run_summary)
    print(json.dumps(run_summary, ensure_ascii=False))
    if errors or any(item["status"] != "APPLIED" or item["result"] != "PASS" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
