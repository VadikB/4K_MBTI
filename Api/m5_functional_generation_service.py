"""Shared PM-03 functional AS generation and independent admission service.

The service is pure with respect to persistence: callers build an immutable input
snapshot in a short DB transaction, run this service without a DB connection, and
persist its complete trace atomically only after programmatic admission.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Api.m5_functional_personalization import extract_candidate_as
from Api.m5_functional_tester import aggregate, build_applicability_plan, normalize_results
from scripts.build_m5_sales_package import build_execution_rules, compile_case_values

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.2"
SOURCE = PACKAGE / "sources/functional-v0.2"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def checksum(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _unique(pattern: str, code: str) -> Path:
    paths = sorted(SOURCE.glob(pattern))
    if len(paths) != 1:
        raise ValueError(code)
    return paths[0]


def build_input_snapshot(*, case_id: str, profile: dict[str, Any], operation_id: str,
                         synthetic: bool = False, case_value: dict[str, Any] | None = None,
                         author_as_example: dict[str, Any] | None = None) -> dict[str, Any]:
    number = case_id.rsplit(".", 1)[-1]
    case_path = _unique(f"02_cases/Case_SPEC_{number}_*.json", f"PERS_CASE_SOURCE_NOT_UNIQUE:{case_id}")
    example_path = _unique(f"04_as/AS_SPEC_{number}_FUNCTIONAL_*.json", f"PERS_AS_SOURCE_NOT_UNIQUE:{case_id}")
    source_case, source_example = _read(case_path), _read(example_path)
    case = json.loads(json.dumps(case_value if case_value is not None else source_case, ensure_ascii=False))
    example = json.loads(json.dumps(author_as_example if author_as_example is not None else source_example, ensure_ascii=False))
    if case.get("CaseID") != case_id or example.get("CaseID") != case_id:
        raise ValueError("M5_FUNCTIONAL_SOURCE_IDENTITY_MISMATCH")
    clean_profile = json.loads(json.dumps(profile, ensure_ascii=False))
    profile_checksum = checksum(clean_profile)
    return {
        "schema_version": 1,
        "operation_id": operation_id,
        "synthetic": synthetic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": case,
        "author_as_example": example,
        "profile": clean_profile,
        "refs": {
            "case": {"path": str(case_path.relative_to(ROOT)), "sha256": checksum(case_path.read_bytes())},
            "author_as_example": {"path": str(example_path.relative_to(ROOT)), "sha256": checksum(example_path.read_bytes())},
            "profile": {"sha256": profile_checksum},
        },
    }


def deterministic_checks(snapshot: dict[str, Any], candidate: Any) -> dict[str, Any]:
    expected = snapshot["author_as_example"]
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
    check("character_count", isinstance(characters, list) and len(characters) == len(expected.get("Активные персонажи", [])))
    materials = candidate.get("Материалы")
    material_ids = {x.get("MaterialID") for x in materials if isinstance(x, dict)} if isinstance(materials, list) else set()
    starts = candidate.get("Стартовые MaterialIDs")
    check("start_material_refs", isinstance(starts, list) and set(starts) <= material_ids, starts)
    events = candidate.get("События")
    check("events_present", isinstance(events, list) and len(events) == len(expected.get("События", [])))
    forbidden = {"Evidence", "IA", "participant_score", "participant_level"}
    def keys(value: Any) -> set[str]:
        if isinstance(value, dict): return set(value) | set().union(*(keys(x) for x in value.values()), set())
        if isinstance(value, list): return set().union(*(keys(x) for x in value), set())
        return set()
    check("no_premature_assessment", not (keys(candidate) & forbidden), sorted(keys(candidate) & forbidden))
    return {"status": "PASS" if all(x["result"] == "PASS" for x in checks) else "FAIL", "checks": checks}


def _trace(response: Any, *, operation_id: str, kind: str, input_checksum: str) -> dict[str, Any]:
    return {"operation_id": operation_id, "kind": kind, "input_checksum": input_checksum,
            "sent": response.sent, "provider": response.provider}


def _strict_json_call(gateway: Any, messages: list[dict[str, str]], *, operation_id: str,
                      max_tokens: int, temperature: float) -> tuple[Any, Any, list[dict[str, Any]]]:
    """Retry one malformed provider envelope; never salvage or merge partial JSON."""
    failures: list[dict[str, Any]] = []
    current = list(messages)
    for attempt in (1, 2):
        response = gateway.chat_with_trace(
            current, temperature=temperature, timeout_seconds=300, max_tokens=max_tokens,
            routing_key=operation_id if attempt == 1 else f"{operation_id}:json-retry",
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(response.content), response, failures
        except json.JSONDecodeError as exc:
            failures.append({"attempt": attempt, "code": "PROVIDER_JSON_INVALID",
                             "position": exc.pos, "response_characters": len(response.content),
                             "finish_reason": response.provider.get("finish_reason")})
            if attempt == 2:
                raise ValueError("M5_FUNCTIONAL_PROVIDER_JSON_INVALID") from exc
            current = [*messages, {"role": "system", "content":
                "Предыдущий ответ не был одним корректным JSON-объектом. Повтори ответ целиком: ровно один JSON-объект, без второго объекта, пояснений и Markdown."}]
    raise AssertionError("unreachable")


def generate(snapshot: dict[str, Any], gateway: Any) -> dict[str, Any]:
    instruction = (SOURCE / "07_generation/Generator_instruction_v0.2.txt").read_text(encoding="utf-8")
    contract = (SOURCE / "07_generation/Generation_contract_v0.2.json").read_text(encoding="utf-8")
    payload = {"profile": snapshot["profile"], "case": snapshot["case"],
               "author_as_example": snapshot["author_as_example"], "requirements": {
                   "output": "Верни только один JSON-объект полной AS с теми же верхнеуровневыми полями, что у author_as_example.",
                   "required_top_level_fields_exact": list(snapshot["author_as_example"].keys()),
                   "omit_empty_required_fields": False,
                   "status": "TEST_DRAFT", "current": False, "synthetic": snapshot["synthetic"],
                   "must_adapt_all_dependent_parts": True, "must_not_create_evidence_or_scores": True,
                   "compact_json": True, "do_not_expand_or_duplicate_author_content": True,
                   "maximum_output_characters": int(len(canonical(snapshot["author_as_example"])) * 1.15)}}
    messages = [{"role": "system", "content": instruction},
                {"role": "system", "content": "Содержательный контракт:\n" + contract},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    input_checksum = checksum(messages)
    operation_id = f"{snapshot['operation_id']}:generation:{input_checksum[:12]}"
    raw, response, parse_failures = _strict_json_call(
        gateway, messages, operation_id=operation_id, max_tokens=32768, temperature=0.2,
    )
    candidate, depth = extract_candidate_as(raw)
    return {"candidate_as": candidate, "candidate_checksum": checksum(candidate),
            "response_envelope_depth": depth, "deterministic_validation": deterministic_checks(snapshot, candidate),
            "provider_operation": {**_trace(response, operation_id=operation_id, kind="generation", input_checksum=input_checksum),
                                   "parse_failures": parse_failures}}


def test_candidate(snapshot: dict[str, Any], generation: dict[str, Any], gateway: Any) -> dict[str, Any]:
    plan = build_applicability_plan(snapshot["case"])
    payload = {"case": snapshot["case"], "profile": snapshot["profile"],
               "candidate_as": generation["candidate_as"],
               "deterministic_validation": generation["deterministic_validation"],
               "applicability_plan": plan,
               "protocol_rules": {"evaluate_every_required_check_exactly_once": True,
                 "llm_must_not_change_applicability": True,
                 "missing_required_material_or_condition_is_fail_not_not_applicable": True,
                 "allowed_statuses": ["PASS", "FAIL", "NOT_RUN", "INDETERMINATE", "TECHNICAL_ERROR"],
                 "do_not_return_overall_status": True},
               "required_output": {"checks": [{
                   "check_id": "exact id from applicability_plan.required_checks",
                   "status": "PASS|FAIL|NOT_RUN|INDETERMINATE|TECHNICAL_ERROR",
                   "evidence_paths": ["JSON path"], "reason": "string",
                   "findings": [{"code": "string", "severity": "blocking|non_blocking",
                                 "paths": ["JSON path"], "reason": "string",
                                 "requirement_ref": "check_id/source_ref"}],
               }]}}
    messages = [{"role": "system", "content": (SOURCE / "07_generation/Tester_instruction_v0.2.txt").read_text(encoding="utf-8")},
                {"role": "system", "content": "Верни один JSON-объект с единственным верхнеуровневым полем checks. Следуй applicability_plan, используй точные check_id каждого required_checks ровно один раз. Не добавляй проверки и не вычисляй общий статус."},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    input_checksum = checksum(messages)
    operation_id = f"{snapshot['operation_id']}:tester:{input_checksum[:12]}"
    raw, response, parse_failures = _strict_json_call(
        gateway, messages, operation_id=operation_id, max_tokens=16384, temperature=0,
    )
    checks = normalize_results(plan, raw.get("checks"))
    aggregation = aggregate(generation["deterministic_validation"], checks)
    return {"protocol": plan["protocol"], "checks": checks, "aggregation": aggregation,
            "provider_operation": {**_trace(response, operation_id=operation_id, kind="independent_tester_v2", input_checksum=input_checksum),
                                   "parse_failures": parse_failures}}


def prepare(snapshot: dict[str, Any], gateway: Any) -> dict[str, Any]:
    generation = generate(snapshot, gateway)
    tested = test_candidate(snapshot, generation, gateway)
    compiled_case = None
    execution_rules = None
    if tested["aggregation"]["admitted_for_participant"]:
        compiled_case = compile_case_values(
            case=snapshot["case"], situation=generation["candidate_as"],
            case_source_name=Path(snapshot["refs"]["case"]["path"]).name,
            case_source_checksum=snapshot["refs"]["case"]["sha256"],
            as_source_name=f"generated-{generation['candidate_checksum']}.json",
            as_source_checksum=generation["candidate_checksum"],
        )
        execution_rules = build_execution_rules([compiled_case])
    return {"schema_version": 1, "input_snapshot_checksum": checksum(snapshot),
            "candidate_as": generation["candidate_as"], "candidate_checksum": generation["candidate_checksum"],
            "deterministic_validation": generation["deterministic_validation"],
            "generation_operation": generation["provider_operation"], "tester": tested,
            "admitted_for_participant": tested["aggregation"]["admitted_for_participant"],
            "compiled_case": compiled_case, "execution_rules": execution_rules}
