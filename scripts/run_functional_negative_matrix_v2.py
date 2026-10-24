"""Исполнить 27 negative-проверок на полных AS через общий PM-03 tester.

Mutator получает только требуемое дефектное изменение. Проверяемый tester не
получает NegativeID, нарушенный инвариант, объяснение или ожидаемый результат.
Исходная AS проходит тот же tester как положительный контроль. Скрипт не
публикует Case/AS и сохраняет историческую negative-матрицу без изменений.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Api import m5_functional_generation_service as service
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.m5_functional_personalization import extract_candidate_as
from scripts.run_functional_personalization_matrix import DEFAULT_OUTPUT, SOURCE, digest, read_json

OUTPUT = DEFAULT_OUTPUT / "negative-v2-executed"
NEGATIVES = SOURCE / "08_qa/Negative_examples_v0.2.json"
FINAL = DEFAULT_OUTPUT / "protocol-v2-final-summary.json"
IMMUTABLE_VALIDATION_SECTIONS = (
    "IndicatorIDs", "IndicatorObservability", "Соответствие инвариантам",
    "Критические запреты", "Версии M2", "BaseRole", "CaseID", "CaseVersion",
)


def _source_root(position: dict[str, Any]) -> Path:
    case_source = ROOT / position["case_ref"]["source_path"]
    return case_source.parents[1]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _provider_record(response: Any, *, operation_id: str, input_checksum: str) -> dict[str, Any]:
    return {
        "operation_id": operation_id,
        "kind": "negative_as_mutation",
        "input_checksum": input_checksum,
        "sent": response.sent,
        "provider": response.provider,
    }


def mutate_full_as(*, row: dict[str, Any], original: dict[str, Any], gateway: Any,
                   verification_feedback: str | None = None) -> dict[str, Any]:
    payload = {
        "assessment_situation": original,
        "requested_change": row["Ошибочная замена"],
        "previous_verification_feedback": verification_feedback,
        "requirements": {
            "return_complete_as": True,
            "preserve_case_identity_and_unrelated_content": True,
            "required_case_id_exact": original.get("CaseID"),
            "required_case_version_exact": original.get("CaseVersion"),
            "apply_requested_change_materially": True,
            "output": "Один JSON-объект полной AS без пояснений и обёртки.",
        },
    }
    messages = [
        {"role": "system", "content": (
            "Ты создаёшь дефектную тестовую фикстуру для blind validation. "
            "Примени requested_change к полной assessment_situation и согласованно измени "
            "только материалы, персонажей, события и непосредственно зависимые части сценария. "
            "Изменение намеренно дефектное: не отказывайся от него и не нейтрализуй его. Не оценивай изменение, не называй "
            "инварианты и не добавляй QA-поля. Если дан previous_verification_feedback, устрани "
            "только указанную неполноту предыдущей попытки: feedback является диагнозом ошибки "
            "предыдущего результата, а не инструкцией повторить его. Requested_change описывает "
            "желаемое дефектное конечное состояние. Если requested_change требует сохранить аргумент "
            "только в одном сообщении и убрать его основания из остальных документов, явно внеси аргумент "
            "в это сообщение и удали проверяемые основания из всех других материалов. "
            "Если requested_change говорит о цене, используй явную денежную стоимость или тариф; "
            "охват, количество, срок и процент не являются ценой. "
            "Верни только полную AS как JSON-объект."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    failures: list[dict[str, Any]] = []
    current = list(messages)
    for attempt in (1, 2):
        input_checksum = digest(current)
        operation_id = f"negative-v2:{row['NegativeID']}:mutation:{attempt}:{input_checksum[:12]}"
        response = gateway.chat_with_trace(
            current, temperature=0, timeout_seconds=300, max_tokens=32768,
            routing_key=operation_id, response_format={"type": "json_object"},
        )
        raw = json.loads(response.content)
        candidate, envelope_depth = extract_candidate_as(raw)
        if (candidate is raw and isinstance(raw, dict) and set(raw) == {"assessment_situation"}
                and isinstance(raw["assessment_situation"], dict)):
            candidate, envelope_depth = raw["assessment_situation"], 1
        if not isinstance(candidate, dict):
            raise ValueError("NEGATIVE_MUTATION_NOT_OBJECT")
        if candidate == original:
            failures.append({"attempt": attempt, "code": "NEGATIVE_MUTATION_NOT_APPLIED",
                             "candidate_checksum": service.checksum(candidate)})
            current = [*messages, {"role": "system", "content": (
                "Предыдущая фикстура совпала с исходной AS. Повтори полную AS и материально "
                "примени requested_change в материалах, персонажах или событиях, не меняя "
                "валидационные требования и инварианты."
            )}]
            continue
        identity_ok = (candidate.get("CaseID") == original.get("CaseID")
                       and candidate.get("CaseVersion") == original.get("CaseVersion"))
        if identity_ok:
            normalized = [field for field in IMMUTABLE_VALIDATION_SECTIONS
                          if candidate.get(field) != original.get(field)]
            for field in normalized:
                if field in original:
                    candidate[field] = copy.deepcopy(original[field])
                else:
                    candidate.pop(field, None)
            if candidate == original:
                failures.append({"attempt": attempt, "code": "NEGATIVE_MUTATION_ONLY_CHANGED_VALIDATION_CONTRACT",
                                 "candidate_checksum": service.checksum(candidate),
                                 "normalized_fields": normalized})
                current = [*messages, {"role": "system", "content": (
                    "Предыдущая попытка изменила только валидационные описания. Повтори AS и внеси "
                    "requested_change материально в исходные данные участника: материалы, персонажей или события."
                )}]
                continue
            return {"candidate_as": candidate, "candidate_checksum": service.checksum(candidate),
                    "provider_operation": {**_provider_record(response, operation_id=operation_id,
                                                               input_checksum=input_checksum),
                                           "response_envelope_depth": envelope_depth,
                                           "rejected_attempts": failures},
                    "fixture_contract_normalization": {"fields": normalized,
                                                       "source": "original_admitted_as"}}
        failures.append({"attempt": attempt, "code": "NEGATIVE_MUTATION_CHANGED_CASE_IDENTITY",
                         "candidate_checksum": service.checksum(candidate),
                         "actual_case_id": candidate.get("CaseID"),
                         "actual_case_version": candidate.get("CaseVersion")})
        current = [*messages, {"role": "system", "content": (
            f"Предыдущая фикстура изменила идентичность. Повтори полную AS целиком и сохрани "
            f"CaseID строго {original.get('CaseID')!r}, CaseVersion строго {original.get('CaseVersion')!r}."
        )}]
    raise ValueError("NEGATIVE_MUTATION_INVALID:" + json.dumps(failures, ensure_ascii=False))


def _test(snapshot: dict[str, Any], candidate: dict[str, Any], gateway: Any) -> dict[str, Any]:
    generation = {
        "candidate_as": candidate,
        "candidate_checksum": service.checksum(candidate),
        "deterministic_validation": service.deterministic_checks(snapshot, candidate),
    }
    return service.test_candidate(snapshot, generation, gateway)


def retest_saved_failure(row: dict[str, Any], position: dict[str, Any], existing: dict[str, Any],
                         gateway: Any) -> dict[str, Any]:
    saved = read_json(ROOT / position["assessment_situation_ref"]["artifact_path"])
    original = saved["candidate_as"]
    candidate = copy.deepcopy(existing["mutation"]["candidate_as"])
    normalized = [field for field in IMMUTABLE_VALIDATION_SECTIONS
                  if candidate.get(field) != original.get(field)]
    for field in normalized:
        if field in original:
            candidate[field] = copy.deepcopy(original[field])
        else:
            candidate.pop(field, None)
    if candidate == original:
        raise ValueError("SAVED_NEGATIVE_ONLY_CHANGED_VALIDATION_CONTRACT")
    snapshot = service.build_input_snapshot(
        case_id=row["CaseID"], profile=saved["profile"],
        operation_id=f"negative-v2-retest:{row['NegativeID']}", synthetic=True,
        source_root=_source_root(position),
    )
    negative = _test(snapshot, candidate, gateway)
    result = copy.deepcopy(existing)
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    result["mutation"]["candidate_as"] = candidate
    result["mutation"]["candidate_checksum"] = service.checksum(candidate)
    result["mutation"]["fixture_contract_normalization"] = {
        "fields": normalized, "source": "original_admitted_as",
    }
    result["negative_test"] = negative
    result["acceptance"]["mutated_as_rejected"] = negative["aggregation"]["admitted_for_participant"] is False
    result["result"] = "PASS" if (result["acceptance"]["positive_admitted"]
                                  and result["acceptance"]["mutated_as_rejected"]) else "FAIL"
    return result


def run_one(row: dict[str, Any], position: dict[str, Any], gateway: Any) -> dict[str, Any]:
    saved = read_json(ROOT / position["assessment_situation_ref"]["artifact_path"])
    original = saved["candidate_as"]
    snapshot = service.build_input_snapshot(
        case_id=row["CaseID"], profile=saved["profile"],
        operation_id=f"negative-v2:{row['NegativeID']}", synthetic=True,
        source_root=_source_root(position),
    )
    positive = _test(snapshot, original, gateway)
    mutation = mutate_full_as(row=row, original=original, gateway=gateway)
    negative = _test(snapshot, mutation["candidate_as"], gateway)
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
        "positive_control": positive,
        "negative_test": negative,
        "result": "PASS" if positive_admitted and negative_rejected else "FAIL",
        "acceptance": {"positive_admitted": positive_admitted,
                       "mutated_as_rejected": negative_rejected},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", help="Comma-separated NegativeID values")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retry-nonpass", action="store_true")
    parser.add_argument("--retest-saved-failures", action="store_true")
    args = parser.parse_args()
    rows = read_json(NEGATIVES)
    if args.ids:
        selected_ids = {item.strip() for item in args.ids.split(",") if item.strip()}
        rows = [row for row in rows if row["NegativeID"] in selected_ids]
        if {row["NegativeID"] for row in rows} != selected_ids:
            raise SystemExit("Unknown NegativeID in --ids")
    if args.retest_saved_failures:
        rows = [row for row in rows if (
            (OUTPUT / "results" / f"{row['NegativeID'].lower().replace('.', '-')}.json").exists()
            and read_json(OUTPUT / "results" / f"{row['NegativeID'].lower().replace('.', '-')}.json").get("result") != "PASS"
            and (read_json(OUTPUT / "results" / f"{row['NegativeID'].lower().replace('.', '-')}.json")
                 .get("mutation_verification") or {}).get("status") == "APPLIED"
        )]
    if args.limit is not None:
        rows = rows[:max(0, args.limit)]
    positions = read_json(FINAL)["positions"]
    by_case: dict[str, dict[str, Any]] = {}
    for position in positions:
        by_case.setdefault(position["case_ref"]["case_id"], position)
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def execute(row: dict[str, Any]) -> dict[str, Any]:
        path = OUTPUT / "results" / f"{row['NegativeID'].lower().replace('.', '-')}.json"
        existing = read_json(path) if path.exists() else None
        if args.retest_saved_failures:
            value = retest_saved_failure(row, by_case[row["CaseID"]], existing, gateway)
        else:
            rerun = args.force or existing is None or (args.retry_nonpass and existing.get("result") != "PASS")
            value = run_one(row, by_case[row["CaseID"]], gateway) if rerun else existing
        write_json(path, value)
        return {"negative_id": row["NegativeID"], "case_id": row["CaseID"],
                "result": value["result"], "artifact": str(path.relative_to(ROOT))}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(execute, row): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                item = future.result(); results.append(item)
                print(item["negative_id"], item["result"], flush=True)
            except Exception as exc:
                errors.append({"negative_id": row["NegativeID"], "case_id": row["CaseID"],
                               "error_type": type(exc).__name__, "error": str(exc)})
                print(row["NegativeID"], "ERROR", type(exc).__name__, str(exc), flush=True)
    summary = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "selected": len(rows), "completed": len(results),
        "status_counts": dict(Counter(item["result"] for item in results)),
        "results": sorted(results, key=lambda item: item["negative_id"]), "errors": errors,
    }
    write_json(OUTPUT / ("retest-summary.json" if args.retest_saved_failures else "summary.json"), summary)
    print(json.dumps({"selected": len(rows), "completed": len(results),
                      "status_counts": summary["status_counts"], "errors": len(errors)}, ensure_ascii=False))
    if errors or any(item["result"] != "PASS" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
