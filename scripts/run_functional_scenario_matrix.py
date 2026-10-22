"""34 изолированных semantic scenario-прогона по конечным AS."""
from __future__ import annotations

import json
import argparse
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from scripts.retest_functional_personalization_v2 import write_json
from scripts.run_functional_personalization_matrix import DEFAULT_OUTPUT, SOURCE, _provider_record, digest, read_json

OUTPUT = DEFAULT_OUTPUT / "scenario-v2-executed"
PLAN = SOURCE / "08_qa/Scenario_regression_plan_v0.2.json"
GLOBAL_CASES = [f"CASE.SPEC.{number:02d}" for number in range(1, 9)]
SCOPE_CASES = {
    "R_SCOPE_PRICE": "CASE.SPEC.02", "R_SCOPE_NEW_PROFESSION": "CASE.SPEC.04",
    "R_SCOPE_NO_REAL_EVENT": "CASE.SPEC.05", "R_SCOPE_NO_ROLE": "CASE.SPEC.06",
    "R_SCOPE_LINKS": "CASE.SPEC.02", "R_SCOPE_PAUSE": "CASE.SPEC.08",
    "R_SCOPE_BUDGET": "CASE.SPEC.01", "R_SCOPE_INVARIANT": "CASE.SPEC.02",
}
EXPECTED_REJECTION_TESTS = {"R_SCOPE_LINKS", "R_SCOPE_INVARIANT"}


def scenario_status(test_id: str, result: dict) -> str:
    status = result.get("status")
    if status not in {"PASS", "FAIL", "INDETERMINATE"} or not isinstance(result.get("trace"), list) or not result["trace"]:
        return "TECHNICAL_ERROR"
    defects = result.get("defects") or []
    if test_id in EXPECTED_REJECTION_TESTS:
        rejection_proved = any(
            item.get("status") == "PASS" and (
                "not_presented" in str(item.get("code", "")).lower()
                or "no_pass_by_style" in str(item.get("code", "")).lower()
            ) for item in result.get("checks", [])
        )
        return "PASS" if defects and rejection_proved else "FAIL"
    return "FAIL" if defects else status


def run_one(item: dict, index: int, final_by_case: dict[str, dict], gateway: DeepSeekGateway) -> dict:
    case_id = item.get("CaseID") or SCOPE_CASES.get(item["TestID"]) or GLOBAL_CASES[index % len(GLOBAL_CASES)]
    final = final_by_case[case_id]
    generation = read_json(ROOT / final["assessment_situation_ref"]["artifact_path"])
    candidate = generation["candidate_as"]
    payload = {
        "mode": "isolated_draft_scenario_qa",
        "scenario_test": item,
        "synthetic_trigger": {
            "assessee_turn": "Тестовая реплика, реализующая условие: " + item["Условие теста"],
            "precondition": "Создай минимально достаточное состояние до реплики, затем фактически исполни реплику и переходы.",
        },
        "case_ref": final["case_ref"],
        "profile_ref": final["profile_ref"],
        "assessment_situation_ref": final["assessment_situation_ref"],
        "candidate_as": candidate,
        "required_output": {
            "status": "PASS|FAIL|INDETERMINATE",
            "trace": [{"sequence": "integer", "kind": "assessee_turn|system_decision|material|character_turn|transition", "content": "string", "audience": ["string"]}],
            "checks": [{"code": "string", "status": "PASS|FAIL|INDETERMINATE", "paths": ["JSON path"], "reason": "string"}],
            "defects": [{"code": "string", "severity": "blocking|non_blocking", "paths": ["JSON path"], "reason": "string"}],
        },
        "constraints": {
            "execute_exact_test_condition": True,
            "do_not_invent_materials_or_external_actions": True,
            "preserve_closed_information_and_character_knowledge": True,
            "scenario_end_is_not_as_close": True,
            "planned_story_is_not_evidence": True,
        },
    }
    messages = [
        {"role": "system", "content": "Ты независимый QA-исполнитель draft AS. Создай минимально достаточную синтетическую тестовую реплику из scenario_test.Условие теста и фактически исполни её по правилам AS. Исходная метка candidate_as.Исполнение.Status=NOT_RUN ожидаема: ты создаёшь новую QA-трассу и не должен отказываться из-за отсутствия старой трассы. Для негативного условия PASS означает, что дефектный вход отклонён и не предъявлен. Верни только JSON. PASS допустим, если новая трасса доказывает ожидаемое поведение без подсказки, нового факта или оценки участника."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    input_checksum = digest(messages)
    operation_id = f"scenario-v2:{item['TestID']}:{input_checksum[:12]}"
    response = gateway.chat_with_trace(messages, temperature=0, timeout_seconds=300, max_tokens=4096,
                                       routing_key=operation_id, response_format={"type": "json_object"})
    result = json.loads(response.content)
    status = scenario_status(item["TestID"], result)
    return {
        "schema_version": 1, "test_id": item["TestID"], "plan_version": item.get("Версия плана", "v0.2"),
        "case_ref": final["case_ref"], "profile_ref": final["profile_ref"],
        "assessment_situation_ref": final["assessment_situation_ref"],
        "scenario_test": item, "status": status, "result": result,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider_operation": _provider_record(response, operation_id=operation_id,
                                               kind="isolated_scenario_qa", input_checksum=input_checksum),
        "limitations": ["isolated semantic scenario QA; DB runtime mechanics are verified separately"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    plan = read_json(PLAN)
    final = read_json(DEFAULT_OUTPUT / "protocol-v2-final-summary.json")
    final_by_case = {}
    for item in final["positions"]:
        case_id = item["case_ref"]["case_id"]
        final_by_case.setdefault(case_id, item)
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        def execute(item: dict, index: int) -> dict:
            path = OUTPUT / "results" / f"{item['TestID'].lower()}.json"
            if path.exists() and not args.force:
                result = read_json(path)
                result["status"] = scenario_status(item["TestID"], result["result"])
                return result
            return run_one(item, index, final_by_case, gateway)
        futures = {pool.submit(execute, item, index): item for index, item in enumerate(plan)}
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result(); results.append(result)
                write_json(OUTPUT / "results" / f"{item['TestID'].lower()}.json", result)
                print(item["TestID"], result["status"], flush=True)
            except Exception as exc:
                errors.append({"test_id": item["TestID"], "error_type": type(exc).__name__, "error": str(exc)})
                print(item["TestID"], "ERROR", type(exc).__name__, str(exc), flush=True)
    summary = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "planned": len(plan), "completed": len(results), "errors": errors,
        "status_counts": dict(Counter(item["status"] for item in results)),
        "results": sorted([{"test_id": item["test_id"], "case_id": item["case_ref"]["case_id"],
                            "as_sha256": item["assessment_situation_ref"]["sha256"],
                            "status": item["status"],
                            "artifact": f"docs/evc/evidence/pers-functional-personalization/scenario-v2-executed/results/{item['test_id'].lower()}.json"}
                           for item in results], key=lambda item: item["test_id"]),
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps({"completed": len(results), "status_counts": summary["status_counts"], "errors": len(errors)}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
