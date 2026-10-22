"""Запустить 27 реальных отрицательных PERS-проверок независимым DeepSeek-тестером."""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from scripts.run_functional_personalization_matrix import SOURCE, _case_source, digest, read_json

OUTPUT = ROOT / "docs/evc/evidence/pers-functional-personalization/negative"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_one(row: dict, gateway: DeepSeekGateway) -> dict:
    instruction = (SOURCE / "07_generation/Tester_instruction_v0.2.txt").read_text(encoding="utf-8")
    case = read_json(_case_source(row["CaseID"]))
    required = {
        "status": "FAIL|INDETERMINATE; PASS запрещён, если описанное изменение действительно нарушает правило",
        "negative_id": row["NegativeID"],
        "violated_invariant": row["Нарушенный инвариант"],
        "finding": {"result": "FAIL|INDETERMINATE", "evidence": "конкретная связь дефекта с функцией", "repair_scope": ["зависимые части AS"]},
    }
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json.dumps({"case": case, "proposed_defective_change": row, "required_output": required}, ensure_ascii=False)},
    ]
    input_checksum = digest(messages)
    operation_id = f"negative:{row['NegativeID']}:{input_checksum[:12]}"
    response = gateway.chat_with_trace(
        messages, temperature=0, timeout_seconds=180, max_tokens=4096,
        routing_key=operation_id, response_format={"type": "json_object"},
    )
    conclusion = json.loads(response.content)
    result = conclusion.get("status")
    finding = conclusion.get("finding") if isinstance(conclusion.get("finding"), dict) else {}
    invariant_present = conclusion.get("violated_invariant") == row["Нарушенный инвариант"] or row["Нарушенный инвариант"] in json.dumps(conclusion, ensure_ascii=False)
    executable_result = "PASS" if result == "FAIL" and finding.get("result") == "FAIL" and invariant_present else "FAIL"
    return {
        "schema_version": 1, "negative_id": row["NegativeID"], "case_id": row["CaseID"],
        "created_at": datetime.now(timezone.utc).isoformat(), "expected": "FAIL",
        "product_test_result": executable_result, "conclusion": conclusion,
        "provider_operation": {
            "operation_id": operation_id, "provider": response.sent.get("provider"),
            "requested_model": response.sent.get("model"), "actual_model": response.provider.get("model"),
            "finish_reason": response.provider.get("finish_reason"), "usage": response.provider.get("usage"),
            "provider_request_id": response.provider.get("request_id"), "input_checksum": input_checksum,
            "gateway_version": response.sent.get("gateway_version"), "provider_contract": response.sent.get("contract"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    rows = read_json(SOURCE / "08_qa/Negative_examples_v0.2.json")
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results, errors = [], []
    def execute(row: dict) -> dict:
        path = OUTPUT / f"{row['NegativeID'].lower().replace('.', '-')}.json"
        value = run_one(row, gateway) if args.force or not path.exists() else read_json(path)
        write_json(path, value)
        return {"negative_id": row["NegativeID"], "case_id": row["CaseID"],
                "result": value["product_test_result"], "path": str(path.relative_to(ROOT))}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(execute, row): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                item = future.result(); results.append(item)
                print(f"{item['negative_id']} result={item['result']}", flush=True)
            except Exception as exc:
                errors.append({"negative_id": row["NegativeID"], "case_id": row["CaseID"],
                               "error_type": type(exc).__name__, "error": str(exc)})
                print(f"{row['NegativeID']} ERROR {type(exc).__name__}: {exc}", flush=True)
    summary = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
               "selected": len(rows), "completed": len(results), "failed": len(errors),
               "results": sorted(results, key=lambda x: x["negative_id"]), "errors": errors}
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("selected", "completed", "failed")}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
