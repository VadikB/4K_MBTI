"""Реальная PERS-06 матрица DeepSeek с возобновляемыми обезличенными артефактами.

Скрипт не публикует пакет и не присваивает методологический допуск. Каждый профиль
явно синтетический; секреты провайдера в артефакты не записываются.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Api.llm.deepseek_gateway import DeepSeekGateway
from Api import m5_functional_generation_service as functional_service
from Api.m5_passport_generation import load_bank_case


PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.2"
SOURCE = PACKAGE / "sources/functional-v0.2"
DEFAULT_OUTPUT = ROOT / "docs/evc/evidence/pers-functional-personalization"
PASSPORT_OUTPUT = ROOT / "docs/evc/evidence/m5-passport-qa"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    data = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def case_number(case_id: str) -> str:
    return case_id.rsplit(".", 1)[-1]


def build_synthetic_profile(row: dict[str, Any]) -> dict[str, Any]:
    """Полная проекция M4 без личности реального пользователя."""
    profile = {
        "schema_version": 1,
        "status": "ready",
        "synthetic_test_data": True,
        "base_role": "specialist_expert",
        "organization_context": {
            "name": "Синтетическая организация PERS-06",
            "activity_description": "Изолированный продуктовый тест функциональной персонализации",
            "general_rules": ["Не приписывать учебные факты реальной организации"],
        },
        "role_profile": {
            "code": "specialist_expert",
            "position_or_status": row["Профессиональный контекст"],
            "description": {"name": row["Профессиональный контекст"]},
            "card": {
                "responsibility_object": row["Подтверждённая для учебного теста деятельность"],
                "independent_authority": "Анализировать сведения и готовить решение.",
                "approval_required": "Согласовывать распоряжение чужими ресурсами.",
            },
        },
        "user_context": {
            "position_or_status": row["Профессиональный контекст"],
            "regular_tasks": row["Подтверждённая для учебного теста деятельность"],
            "additional_information": row["Возможное отображение"],
            "constraints_and_interactions": "Рабочие решения принимаются в пределах подтверждённого мандата и требуют взаимодействия с коллегами или заказчиками.",
        },
        "source": {"test_id": row["TestID"], "marker": row["Данные"]},
    }
    profile["checksum"] = digest(profile)
    return profile


def _as_source(case_id: str) -> Path:
    paths = sorted((SOURCE / "04_as").glob(f"AS_SPEC_{case_number(case_id)}_FUNCTIONAL_*.json"))
    if len(paths) != 1:
        raise ValueError(f"PERS_AS_SOURCE_NOT_UNIQUE:{case_id}")
    return paths[0]


def _case_source(case_id: str) -> Path:
    paths = sorted((SOURCE / "02_cases").glob(f"Case_SPEC_{case_number(case_id)}_*.json"))
    if len(paths) != 1:
        raise ValueError(f"PERS_CASE_SOURCE_NOT_UNIQUE:{case_id}")
    return paths[0]


def load_inputs(row: dict[str, Any]) -> dict[str, Any]:
    """Read PERS-06 v0.2 evidence for historical report reproduction."""
    case_path, as_path = _case_source(row["CaseID"]), _as_source(row["CaseID"])
    profile = build_synthetic_profile(row)
    return {
        "case": read_json(case_path),
        "author_as_example": read_json(as_path),
        "profile": profile,
        "refs": {
            "case": {"path": str(case_path.relative_to(ROOT)), "sha256": digest(case_path.read_bytes())},
            "author_as_example": {"path": str(as_path.relative_to(ROOT)), "sha256": digest(as_path.read_bytes())},
            "profile": {"test_id": row["TestID"], "sha256": profile["checksum"]},
        },
    }


def deterministic_checks(inputs: dict[str, Any], candidate: Any) -> dict[str, Any]:
    expected = inputs["author_as_example"]
    checks: list[dict[str, Any]] = []

    def check(code: str, passed: bool, actual: Any = None) -> None:
        checks.append({"code": code, "result": "PASS" if passed else "FAIL", "actual": actual})

    check("json_object", isinstance(candidate, dict))
    if not isinstance(candidate, dict):
        return {"status": "FAIL", "checks": checks}
    required = set(expected)
    check("top_level_contract", required <= set(candidate), sorted(required - set(candidate)))
    check("case_identity", candidate.get("CaseID") == expected.get("CaseID") and candidate.get("CaseVersion") == expected.get("CaseVersion"))
    check("base_role", candidate.get("BaseRole") == expected.get("BaseRole"), candidate.get("BaseRole"))
    check("indicator_targets", candidate.get("IndicatorIDs") == expected.get("IndicatorIDs"), candidate.get("IndicatorIDs"))
    check("m2_versions", candidate.get("Версии M2") == expected.get("Версии M2"))
    characters = candidate.get("Активные персонажи")
    check("character_count", isinstance(characters, list) and len(characters) == len(expected.get("Активные персонажи", [])), len(characters) if isinstance(characters, list) else None)
    materials = candidate.get("Материалы")
    material_ids = {item.get("MaterialID") for item in materials if isinstance(item, dict)} if isinstance(materials, list) else set()
    starts = candidate.get("Стартовые MaterialIDs")
    check("start_material_refs", isinstance(starts, list) and set(starts) <= material_ids, starts)
    events = candidate.get("События")
    check("events_present", isinstance(events, list) and len(events) == len(expected.get("События", [])), len(events) if isinstance(events, list) else None)
    forbidden_keys = {"Evidence", "IA", "participant_score", "participant_level"}
    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()), set())
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value), set())
        return set()
    check("no_premature_assessment", not (keys(candidate) & forbidden_keys), sorted(keys(candidate) & forbidden_keys))
    return {"status": "PASS" if all(c["result"] == "PASS" for c in checks) else "FAIL", "checks": checks}


def _provider_record(response: Any, *, operation_id: str, kind: str, input_checksum: str) -> dict[str, Any]:
    sent = response.sent
    provider = response.provider
    return {
        "operation_id": operation_id,
        "kind": kind,
        "provider": sent.get("provider"),
        "requested_model": sent.get("model"),
        "actual_model": provider.get("model"),
        "endpoint": sent.get("endpoint"),
        "parameters": sent.get("parameters"),
        "gateway_version": sent.get("gateway_version"),
        "provider_contract": sent.get("contract"),
        "provider_request_id": provider.get("request_id"),
        "provider_revision": provider.get("revision"),
        "finish_reason": provider.get("finish_reason"),
        "usage": provider.get("usage"),
        "transport_attempts": provider.get("transport_attempts"),
        "input_checksum": input_checksum,
    }


def _passport_snapshot(case_id: str, profile: dict, test_id: str) -> dict:
    case, package = load_bank_case(case_id)
    return functional_service.build_passport_snapshot(
        case_version=case, package_ref=package, profile=profile, operation_id=test_id, synthetic=True,
        profile_checksum=profile["checksum"],
    )


def generate_one(row: dict[str, Any], gateway: DeepSeekGateway) -> dict[str, Any]:
    profile = build_synthetic_profile(row)
    snapshot = _passport_snapshot(row["CaseID"], profile, row["TestID"])
    generated = functional_service.generate(snapshot, gateway)
    return {
        "schema_version": 1,
        "test_id": row["TestID"],
        "case_id": row["CaseID"],
        "synthetic_test_data": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_refs": snapshot["refs"],
        "profile": profile,
        "candidate_as": generated["candidate_as"],
        "candidate_checksum": generated["candidate_checksum"],
        "response_envelope_depth": generated["response_envelope_depth"],
        "deterministic_validation": generated["deterministic_validation"],
        "provider_operation": generated["provider_operation"],
    }


def test_one(generation: dict[str, Any], gateway: DeepSeekGateway) -> dict[str, Any]:
    snapshot = _passport_snapshot(generation["case_id"], generation["profile"], generation["test_id"])
    if generation["input_refs"] != snapshot["refs"]:
        raise ValueError("M5_QA_SNAPSHOT_MISMATCH")
    tested = functional_service.test_candidate(snapshot, generation, gateway)
    aggregation = tested["aggregation"]
    conclusion = {"status": aggregation["status"], "checks": tested["checks"],
                  "defects": aggregation["blocking_failures"] + aggregation["review_required"],
                  "admitted_for_participant": aggregation["admitted_for_participant"]}
    return {
        "schema_version": 2,
        "test_id": generation["test_id"],
        "case_id": generation["case_id"],
        "candidate_checksum": generation["candidate_checksum"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "structurally_valid": aggregation["status"] not in {"INCOMPLETE"},
        "conclusion": conclusion,
        "aggregation": aggregation,
        "provider_operation": tested["provider_operation"],
    }


def repair_one(generation: dict[str, Any], tested: dict[str, Any], gateway: DeepSeekGateway, attempt_no: int) -> dict[str, Any]:
    snapshot = _passport_snapshot(generation["case_id"], generation["profile"], generation["test_id"])
    if generation["input_refs"] != snapshot["refs"]:
        raise ValueError("M5_QA_SNAPSHOT_MISMATCH")
    repaired = functional_service.repair_candidate(snapshot, generation, tested, gateway)
    history = list(generation.get("repair_history", []))
    history.append({
        "attempt_no": attempt_no,
        "previous_candidate_checksum": generation["candidate_checksum"],
        "tester_status": tested["conclusion"].get("status"),
        "defects": tested["conclusion"].get("defects", []),
        "tester_operation": tested["provider_operation"],
    })
    return {
        **generation,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **repaired,
        "repair_history": history,
    }
def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def report_path(path: Path) -> str:
    """Keep repository evidence relative and external smoke evidence explicit."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def summarize_existing(rows: list[dict[str, Any]], output: Path, errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    results = []
    known_errors = {item["test_id"]: item for item in (errors or [])}
    previous = output / "matrix-summary.json"
    if previous.exists():
        for item in read_json(previous).get("errors", []):
            known_errors.setdefault(item["test_id"], item)
    for row in rows:
        stem = row["TestID"].lower().replace(".", "-")
        generated_path, tested_path = output / "generations" / f"{stem}.json", output / "tester" / f"{stem}.json"
        if not generated_path.exists() or not tested_path.exists():
            known_errors.setdefault(row["TestID"], {
                "test_id": row["TestID"], "case_id": row["CaseID"],
                "error_type": "NOT_COMPLETED", "error": "No complete generation/tester artifact",
            })
            continue
        generation, tested = read_json(generated_path), read_json(tested_path)
        results.append({
            "test_id": row["TestID"], "case_id": row["CaseID"],
            "generation": generation["deterministic_validation"]["status"],
            "tester": tested["conclusion"].get("status", "INDETERMINATE"),
            "admitted_for_participant": bool(tested["structurally_valid"] and tested["conclusion"].get("status") == "PASS" and tested["conclusion"].get("admitted_for_participant") is True),
            "repair_attempts": len(generation.get("repair_history", [])),
            "generation_path": report_path(generated_path),
            "tester_path": report_path(tested_path),
            "candidate_checksum": generation["candidate_checksum"],
        })
        known_errors.pop(row["TestID"], None)
    return {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "package": {"id": "m5-functional-personalization-cases", "version": "0.2", "status": "draft"},
        "selected": len(rows), "completed": len(results), "failed": len(known_errors),
        "results": sorted(results, key=lambda item: item["test_id"]),
        "errors": sorted(known_errors.values(), key=lambda item: item["test_id"]),
        "methodology_admission": "NOT_RUN",
    }


def run_profile(row: dict[str, Any], output: Path, gateway: DeepSeekGateway, force: bool, max_repairs: int) -> dict[str, Any]:
    stem = row["TestID"].lower().replace(".", "-")
    generated_path, tested_path = output / "generations" / f"{stem}.json", output / "tester" / f"{stem}.json"
    generation = read_json(generated_path) if generated_path.exists() and not force else generate_one(row, gateway)
    if not generated_path.exists() or force:
        write_json(generated_path, generation)
    tested = read_json(tested_path) if tested_path.exists() and not force else test_one(generation, gateway)
    attempt_no = len(generation.get("repair_history", []))
    while (attempt_no < max_repairs and
           (tested["aggregation"]["blocking_failures"] or tested["aggregation"]["deterministic_failures"])):
        audit = output / "attempts" / stem
        write_json(audit / f"{attempt_no + 1:02d}-generation.json", generation)
        write_json(audit / f"{attempt_no + 1:02d}-tester.json", tested)
        attempt_no += 1
        generation = repair_one(generation, tested, gateway, attempt_no)
        tested = test_one(generation, gateway)
    write_json(generated_path, generation)
    write_json(tested_path, tested)
    return {
        "test_id": row["TestID"], "case_id": row["CaseID"],
        "generation": generation["deterministic_validation"]["status"],
        "tester": tested["conclusion"].get("status", "INDETERMINATE"),
        "admitted_for_participant": bool(tested["structurally_valid"] and tested["conclusion"].get("status") == "PASS" and tested["conclusion"].get("admitted_for_participant") is True),
        "generation_path": report_path(generated_path),
        "tester_path": report_path(tested_path),
        "candidate_checksum": generation["candidate_checksum"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PASSPORT_OUTPUT)
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-repairs", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args()
    rows = read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")
    if args.profile:
        rows = [row for row in rows if row["TestID"] in set(args.profile)]
    if not rows:
        raise SystemExit("No selected profiles")
    if args.summarize_only:
        summary = summarize_existing(rows, args.output)
        write_json(args.output / "matrix-summary.json", summary)
        print(json.dumps({k: summary[k] for k in ("selected", "completed", "failed")}, ensure_ascii=False))
        return
    gateway = DeepSeekGateway()
    if not gateway.enabled:
        raise SystemExit("DeepSeek is not configured")
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(run_profile, row, args.output, gateway, args.force, max(0, args.max_repairs)): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"{result['test_id']} generation={result['generation']} tester={result['tester']}", flush=True)
            except Exception as exc:  # matrix must preserve failures and continue
                errors.append({"test_id": row["TestID"], "case_id": row["CaseID"], "error_type": type(exc).__name__, "error": str(exc)})
                print(f"{row['TestID']} ERROR {type(exc).__name__}: {exc}", flush=True)
    summary = summarize_existing(rows, args.output, errors)
    write_json(args.output / "matrix-summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("selected", "completed", "failed")}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
