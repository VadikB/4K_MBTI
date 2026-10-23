"""Независимо подтвердить, что сохранённые negative-мутации материально применены."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from scripts.run_functional_negative_matrix_v2 import NEGATIVES, OUTPUT, write_json
from scripts.run_functional_personalization_matrix import digest, read_json


def verify(row: dict, artifact: dict, gateway: DeepSeekGateway) -> dict:
    original = read_json(ROOT / artifact["source_as"]["artifact_path"])["candidate_as"]
    mutated = artifact["mutation"]["candidate_as"]
    payload = {
        "requested_change": row["Ошибочная замена"],
        "original_assessment_situation": original,
        "mutated_assessment_situation": mutated,
        "required_output": {
            "status": "APPLIED|NOT_APPLIED|INDETERMINATE",
            "evidence_paths": ["JSON path in mutated_assessment_situation"],
            "reason": "Как именно все смысловые части requested_change представлены или чего не хватает.",
        },
    }
    messages = [
        {"role": "system", "content": (
            "Ты проверяешь только качество тестовой мутации, не допустимость AS. Сравни два полных JSON. "
            "APPLIED разрешён, только если все смысловые части requested_change материально реализованы "
            "в данных/материалах/персонажах/событиях, а evidence_paths точно указывают изменения. "
            "Проверяй только смысловые части requested_change. Противоречия в зависимых полях могут быть "
            "дополнительным дефектом AS, но не делают внесённую запрошенную мутацию неприменённой, если "
            "сам requested_change не требует согласованного обновления этих полей. "
            "Если requested_change прямо говорит, что одинаковые элементы только переименованы, их функция, "
            "предметная граница и содержание должны остаться одинаковыми; содержательное разведение "
            "таких элементов означает NOT_APPLIED. Разные названия сами по себе не доказывают "
            "содержательного разведения: сравни описания, действия, границы и состав, исключив label/name. "
            "Пересчёт суммы из-за появления четырёх строк не меняет функцию самих элементов. "
            "Фраза «Переименовать четыре одинаковые консультации в разные ресурсы» означает APPLIED, "
            "когда созданы четыре разных названия или строки, но описания, функции и границы консультаций "
            "остались одинаковыми: именно ложное различие является запрошенной мутацией. "
            "Фраза «Документ только переименован и не содержит двух смысловых искажений» означает APPLIED, "
            "когда в изменённом документе устранены оба исходных искажения и тем самым исчезла задача их "
            "распознавания; устранение искажений здесь является запрошенной мутацией, а не её нейтрализацией. "
            "В requested_change «ценовой аргумент» означает явную денежную стоимость, цену или тариф. "
            "Число откликов, охват, срок или процент без денежной стоимости не являются ценовым аргументом. "
            "Если requested_change вводит требование что-либо "
            "проверять или оценивать, одного упоминания предмета недостаточно: AS должна фактически "
            "требовать эту проверку от участника или оценщика. Явный запрет такой оценки означает "
            "NOT_APPLIED, даже если предмет присутствует в материалах. "
            "Не используй известный нарушенный инвариант и не выноси итог допуска AS. Верни только JSON."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    input_checksum = digest(messages)
    operation_id = f"negative-v2:{row['NegativeID']}:mutation-verification:{input_checksum[:12]}"
    response = gateway.chat_with_trace(
        messages, temperature=0, timeout_seconds=300, max_tokens=4096,
        routing_key=operation_id, response_format={"type": "json_object"},
    )
    conclusion = json.loads(response.content)
    status = conclusion.get("status")
    paths = conclusion.get("evidence_paths")
    if status not in {"APPLIED", "NOT_APPLIED", "INDETERMINATE"} or not isinstance(paths, list):
        status = "TECHNICAL_ERROR"
    return {
        "status": status, "conclusion": conclusion,
        "provider_operation": {
            "operation_id": operation_id, "kind": "negative_mutation_verification",
            "input_checksum": input_checksum, "sent": response.sent, "provider": response.provider,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--ids", help="Comma-separated NegativeID values")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    rows = {row["NegativeID"]: row for row in read_json(NEGATIVES)}
    paths = sorted((OUTPUT / "results").glob("*.json"))
    if args.ids:
        selected_ids = {item.strip() for item in args.ids.split(",") if item.strip()}
        paths = [path for path in paths if read_json(path)["negative_id"] in selected_ids]
    if args.summarize_only:
        results = []
        for path in paths:
            artifact = read_json(path)
            verification = artifact.get("mutation_verification") or {"status": "NOT_RUN"}
            results.append({"negative_id": artifact["negative_id"], "case_id": artifact["case_id"],
                            "mutation_status": verification["status"], "result": artifact["result"],
                            "artifact": str(path.relative_to(ROOT))})
        summary = {
            "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "selected": len(read_json(NEGATIVES)), "completed": len(results),
            "mutation_status_counts": dict(Counter(item["mutation_status"] for item in results)),
            "result_counts": dict(Counter(item["result"] for item in results)),
            "results": sorted(results, key=lambda item: item["negative_id"]), "errors": [],
            "missing_negative_ids": sorted(set(rows) - {item["negative_id"] for item in results}),
        }
        write_json(OUTPUT / "mutation-verification-summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False))
        return
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results, errors = [], []

    def execute(path: Path) -> dict:
        artifact = read_json(path)
        verification = artifact.get("mutation_verification")
        if args.force or not isinstance(verification, dict):
            verification = verify(rows[artifact["negative_id"]], artifact, gateway)
            artifact["mutation_verification"] = verification
            artifact["blind_tester_result"] = artifact["result"]
            artifact["result"] = (artifact["result"] if verification["status"] == "APPLIED"
                                  else "TECHNICAL_ERROR")
            write_json(path, artifact)
        return {"negative_id": artifact["negative_id"], "case_id": artifact["case_id"],
                "mutation_status": verification["status"], "result": artifact["result"],
                "artifact": str(path.relative_to(ROOT))}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(execute, path): path for path in paths}
        for future in as_completed(futures):
            try:
                item = future.result(); results.append(item)
                print(item["negative_id"], item["mutation_status"], item["result"], flush=True)
            except Exception as exc:
                errors.append({"artifact": str(futures[future].relative_to(ROOT)),
                               "error_type": type(exc).__name__, "error": str(exc)})
    summary = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "selected": len(paths), "completed": len(results),
        "mutation_status_counts": dict(Counter(item["mutation_status"] for item in results)),
        "result_counts": dict(Counter(item["result"] for item in results)),
        "results": sorted(results, key=lambda item: item["negative_id"]), "errors": errors,
        "missing_negative_ids": sorted(set(rows) - {item["negative_id"] for item in results}),
    }
    write_json(OUTPUT / "mutation-verification-summary.json", summary)
    print(json.dumps({key: summary[key] for key in (
        "selected", "completed", "mutation_status_counts", "result_counts", "missing_negative_ids"
    )}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
