"""Повторная tester-only проверка сохранённых PERS AS по protocol v2, без регенерации."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.m5_functional_tester import aggregate, build_applicability_plan, normalize_results
from scripts.run_functional_personalization_matrix import (
    DEFAULT_OUTPUT, SOURCE, _case_source, _provider_record, digest, read_json,
)

OUTPUT = DEFAULT_OUTPUT / "tester-v2"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def retest_one(generation: dict, gateway: DeepSeekGateway) -> dict:
    case = read_json(_case_source(generation["case_id"]))
    plan = build_applicability_plan(case)
    instruction = (SOURCE / "07_generation/Tester_instruction_v0.2.txt").read_text(encoding="utf-8")
    payload = {
        "case": case,
        "profile": generation["profile"],
        "candidate_as": generation["candidate_as"],
        "deterministic_validation": generation["deterministic_validation"],
        "applicability_plan": plan,
        "protocol_rules": {
            "evaluate_every_required_check_exactly_once": True,
            "llm_must_not_change_applicability": True,
            "missing_required_material_or_condition_is_fail_not_not_applicable": True,
            "allowed_statuses": ["PASS", "FAIL", "NOT_RUN", "INDETERMINATE", "TECHNICAL_ERROR"],
            "fail_requires_findings": True,
            "finding": {"code": "string", "severity": "blocking|non_blocking", "paths": ["JSON path"], "reason": "string", "requirement_ref": "check_id/source_ref"},
            "output": {"checks": [{"check_id": "exact id from required_checks", "status": "allowed status", "evidence_paths": ["JSON path"], "reason": "string", "findings": ["finding"]}]},
            "do_not_return_overall_status": True
        },
    }
    messages = [
        {"role": "system", "content": instruction},
        {"role": "system", "content": "Следуй applicability_plan. CASE02-проверка отсутствует в required_checks других Case и уже записана системой как NOT_APPLICABLE. Не добавляй собственные проверки и не вычисляй общий статус."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    input_checksum = digest(messages)
    operation_id = f"tester-v2:{generation['test_id']}:{input_checksum[:12]}"
    response = gateway.chat_with_trace(
        messages, temperature=0, timeout_seconds=300, max_tokens=16384,
        routing_key=operation_id, response_format={"type": "json_object"},
    )
    raw = json.loads(response.content)
    checks = normalize_results(plan, raw.get("checks"))
    aggregation = aggregate(generation["deterministic_validation"], checks)
    return {
        "schema_version": 2,
        "test_id": generation["test_id"], "case_id": generation["case_id"],
        "candidate_checksum": generation["candidate_checksum"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": plan["protocol"], "applicability_plan": plan,
        "checks": checks, "aggregation": aggregation,
        "provider_operation": _provider_record(response, operation_id=operation_id, kind="independent_tester_v2", input_checksum=input_checksum),
    }


def old_status(stem: str) -> str:
    path = DEFAULT_OUTPUT / "tester" / f"{stem}.json"
    return str(read_json(path)["conclusion"].get("status", "INDETERMINATE")) if path.exists() else "NOT_RUN"


def blocker_report(results: list[dict]) -> dict:
    groups: dict[str, dict] = {}
    for result in results:
        aggregation = result["aggregation"]
        for bucket in ("deterministic_failures", "blocking_failures", "incomplete_checks", "review_required"):
            for item in aggregation.get(bucket, []):
                findings = item.get("findings") or [{"code": item.get("code") or item.get("check_id"),
                                                       "paths": [], "reason": item.get("reason") or ""}]
                for finding in findings:
                    code = str(finding.get("code") or item.get("check_id") or "UNCLASSIFIED")
                    key = f"{bucket}:{code}"
                    group = groups.setdefault(key, {"bucket": bucket, "code": code, "count": 0, "examples": []})
                    group["count"] += 1
                    if len(group["examples"]) < 5:
                        group["examples"].append({
                            "test_id": result["test_id"], "case_id": result["case_id"],
                            "check_id": item.get("check_id") or item.get("code"),
                            "requirement": item.get("requirement"), "source_ref": item.get("source_ref"),
                            "paths": finding.get("paths") or item.get("evidence_paths") or [],
                            "reason": finding.get("reason") or item.get("reason"),
                        })
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "groups": sorted(groups.values(), key=lambda x: (-x["count"], x["code"]))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    prior_summary = read_json(DEFAULT_OUTPUT / "matrix-summary.json")
    generation_paths = sorted(ROOT / item["generation_path"] for item in prior_summary["results"])
    pending_llm = args.force or any(not (OUTPUT / path.name).exists() for path in generation_paths)
    gateway = DeepSeekGateway() if pending_llm else None
    if gateway is not None and not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results, errors = [], []
    def execute(path: Path) -> dict:
        generation = read_json(path)
        destination = OUTPUT / path.name
        if args.force or not destination.exists():
            assert gateway is not None
            value = retest_one(generation, gateway)
        else:
            value = read_json(destination)
            # Агрегация — детерминированный слой: её можно пересчитать без повторного LLM-вызова.
            plan = build_applicability_plan(read_json(_case_source(generation["case_id"])))
            checks = normalize_results(plan, value.get("checks"))
            value["applicability_plan"] = plan
            value["checks"] = checks
            value["aggregation"] = aggregate(generation["deterministic_validation"], checks)
        write_json(destination, value)
        return value
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(execute, path): path for path in generation_paths}
        for future in as_completed(futures):
            path = futures[future]
            try:
                value = future.result(); results.append(value)
                print(f"{value['test_id']} {old_status(path.stem)} -> {value['aggregation']['status']}", flush=True)
            except Exception as exc:
                errors.append({"artifact": path.name, "error_type": type(exc).__name__, "error": str(exc)})
                print(f"{path.stem} ERROR {type(exc).__name__}: {exc}", flush=True)
    source_rows = read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")
    complete_ids = {item["test_id"] for item in results}
    matrix_missing = [{"test_id": row["TestID"], "case_id": row["CaseID"], "status": "TECHNICAL_ERROR",
                       "reason": "Полная сохранённая AS/tester-v2 отсутствует."}
                      for row in source_rows if row["TestID"] not in complete_ids]
    comparison = [{
        "test_id": item["test_id"], "case_id": item["case_id"],
        "candidate_checksum": item["candidate_checksum"],
        "old_status": old_status(item["test_id"].lower().replace(".", "-")),
        "new_status": item["aggregation"]["status"],
        "new_admitted": item["aggregation"]["admitted_for_participant"],
    } for item in results]
    summary = {
        "schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": results[0]["protocol"] if results else None,
        "matrix_total": 27, "saved_as_retested": len(results), "matrix_missing": matrix_missing,
        "technical_errors": errors,
        "status_counts": dict(Counter(item["aggregation"]["status"] for item in results)),
        "admitted": sum(item["aggregation"]["admitted_for_participant"] for item in results),
        "comparison": sorted(comparison, key=lambda x: x["test_id"]),
    }
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "blocker-report.json", blocker_report(results))
    print(json.dumps({"retested": len(results), "errors": len(errors), "status_counts": summary["status_counts"],
                      "matrix_missing": len(matrix_missing)}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
