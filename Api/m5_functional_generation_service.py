"""Shared PM-03 functional AS generation and independent admission service.

The service is pure with respect to persistence: callers build an immutable input
snapshot in a short DB transaction, run this service without a DB connection, and
persist its complete trace atomically only after programmatic admission.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Api.m5_functional_personalization import extract_candidate_as
from Api.m5_functional_tester import aggregate, build_applicability_plan, normalize_results
from Api.m5_case_runtime import checksum as runtime_checksum
from scripts.build_m5_sales_package import build_execution_rules, compile_case_values

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.3"
SOURCE = PACKAGE / "sources/functional-v0.2"
REPAIR_PACKAGE = ROOT / "assessment_definitions/prompts/m5_functional_repair/v1"
PROTOCOL_PACKAGE = ROOT / "assessment_definitions/prompts/m5_functional_protocol/v1"

AUTHOR_INDICATOR_FIELDS = (
    "IndicatorID", "SkillID", "ComponentID", "Название", "Версия M2",
    "Нормативный источник", "Материалы и факты", "Конкретное условие",
    "Что сохранить при адаптации", "Дефект потери", "Форма проявления",
    "Проектная возможность", "Фактическое возникновение", "Evidence и IA",
    "Связанные инварианты",
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def checksum(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _unique(pattern: str, code: str, *, source_root: Path = SOURCE) -> Path:
    paths = sorted(source_root.glob(pattern))
    if len(paths) != 1:
        raise ValueError(code)
    return paths[0]


def _load_repair_instruction(repair_package: Path = REPAIR_PACKAGE) -> tuple[str, dict[str, str]]:
    manifest = _read(repair_package / "manifest.json")
    artifacts = manifest.get("artifacts") or []
    registered = next((item for item in artifacts if item.get("name") == "prompt.md"), None)
    prompt = (repair_package / "prompt.md").read_bytes()
    if (manifest.get("id") != "m5_functional_repair" or manifest.get("version") != "1.0.0"
            or manifest.get("status") != "draft" or not registered
            or registered.get("sha256") != checksum(prompt)):
        raise ValueError("M5_FUNCTIONAL_REPAIR_PACKAGE_INVALID")
    return prompt.decode("utf-8"), {
        "id": manifest["id"], "version": manifest["version"], "checksum": checksum(prompt),
    }


def build_input_snapshot(*, case_id: str, profile: dict[str, Any], operation_id: str,
                         synthetic: bool = False, case_value: dict[str, Any] | None = None,
                         author_as_example: dict[str, Any] | None = None,
                         profile_checksum: str | None = None,
                         case_version_checksum: str | None = None,
                         source_root: Path = SOURCE,
                         repair_package: Path = REPAIR_PACKAGE,
                         protocol_package: Path = PROTOCOL_PACKAGE) -> dict[str, Any]:
    number = case_id.rsplit(".", 1)[-1]
    case_path = _unique(f"02_cases/Case_SPEC_{number}_*.json", f"PERS_CASE_SOURCE_NOT_UNIQUE:{case_id}", source_root=source_root)
    example_path = _unique(f"04_as/AS_SPEC_{number}_FUNCTIONAL_*.json", f"PERS_AS_SOURCE_NOT_UNIQUE:{case_id}", source_root=source_root)
    package_manifest = _read(source_root.parents[1] / "manifest.json")
    source_case, source_example = _read(case_path), _read(example_path)
    case = json.loads(json.dumps(case_value if case_value is not None else source_case, ensure_ascii=False))
    example = json.loads(json.dumps(author_as_example if author_as_example is not None else source_example, ensure_ascii=False))
    if case.get("CaseID") != case_id or example.get("CaseID") != case_id:
        raise ValueError("M5_FUNCTIONAL_SOURCE_IDENTITY_MISMATCH")
    clean_profile = json.loads(json.dumps(profile, ensure_ascii=False))
    profile_checksum = profile_checksum or checksum(clean_profile)
    return {
        "schema_version": 1,
        "operation_id": operation_id,
        "synthetic": synthetic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": case,
        "author_as_example": example,
        "profile": clean_profile,
        "refs": {
            "package": {"id": package_manifest["id"], "version": package_manifest["version"],
                        "compiler": package_manifest.get("compiler")},
            "case": {"path": str(case_path.relative_to(ROOT)), "sha256": checksum(case_path.read_bytes()),
                     "case_version_checksum": case_version_checksum or checksum(case)},
            "author_as_example": {"path": str(example_path.relative_to(ROOT)), "sha256": checksum(example_path.read_bytes())},
            "profile": {"sha256": profile_checksum},
            "generator_prompt": {"path": str((source_root / "07_generation/Generator_instruction_v0.2.txt").relative_to(ROOT)),
                                 "sha256": checksum((source_root / "07_generation/Generator_instruction_v0.2.txt").read_bytes())},
            "tester_prompt": {"path": str((source_root / "07_generation/Tester_instruction_v0.2.txt").relative_to(ROOT)),
                              "sha256": checksum((source_root / "07_generation/Tester_instruction_v0.2.txt").read_bytes())},
            "generation_contract": {"path": str((source_root / "07_generation/Generation_contract_v0.2.json").relative_to(ROOT)),
                                    "sha256": checksum((source_root / "07_generation/Generation_contract_v0.2.json").read_bytes())},
            "repair_package": {"path": str(repair_package.relative_to(ROOT))},
            **{
                f"protocol_{name.replace('-', '_')}": {
                    "path": str((protocol_package / f"{name}.md").relative_to(ROOT)),
                    "sha256": checksum((protocol_package / f"{name}.md").read_bytes()),
                }
                for name in ("json-retry", "tester-addendum", "challenger")
            },
        },
    }


def _frozen_file(snapshot: dict[str, Any], ref_name: str) -> Path:
    ref = snapshot["refs"][ref_name]
    path = ROOT / ref["path"]
    if not path.is_file():
        raise ValueError(f"CYCLE_DEPENDENCY_UNAVAILABLE:{ref_name}")
    if checksum(path.read_bytes()) != ref["sha256"]:
        raise ValueError(f"CYCLE_DEPENDENCY_CHECKSUM_MISMATCH:{ref_name}")
    return path


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
    package_ref = (snapshot.get("refs") or {}).get("package") or {}
    compiler = package_ref.get("compiler") or {}
    if compiler.get("source_schema_profile") == "functional-personalization-indicator-v1":
        expected_targets = expected.get("IndicatorObservability")
        candidate_targets = candidate.get("IndicatorObservability")
        expected_by_id = ({item.get("IndicatorID"): item for item in expected_targets}
                          if isinstance(expected_targets, list) else {})
        candidate_by_id = ({item.get("IndicatorID"): item for item in candidate_targets}
                           if isinstance(candidate_targets, list) else {})
        check("indicator_content_target_set", bool(expected_by_id)
              and set(candidate_by_id) == set(expected_by_id), sorted(candidate_by_id))
        differences = []
        if set(candidate_by_id) == set(expected_by_id):
            for indicator_id, source_target in expected_by_id.items():
                candidate_target = candidate_by_id[indicator_id]
                for field in AUTHOR_INDICATOR_FIELDS:
                    if candidate_target.get(field) != source_target.get(field):
                        differences.append({"indicator_id": indicator_id, "field": field})
        check("indicator_author_content_preserved", not differences, differences)
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


def bind_frozen_author_indicator_content(snapshot: dict[str, Any], candidate: Any) -> Any:
    """Bind source-owned IndicatorObservability fields without repairing LLM content."""
    package_ref = (snapshot.get("refs") or {}).get("package") or {}
    compiler = package_ref.get("compiler") or {}
    if (compiler.get("source_schema_profile") != "functional-personalization-indicator-v1"
            or not isinstance(candidate, dict)):
        return candidate
    source_targets = snapshot["author_as_example"].get("IndicatorObservability")
    candidate_targets = candidate.get("IndicatorObservability")
    if not isinstance(source_targets, list) or not isinstance(candidate_targets, list):
        return candidate
    source_by_id = {item.get("IndicatorID"): item for item in source_targets if isinstance(item, dict)}
    bound = deepcopy(candidate)
    for target in bound["IndicatorObservability"]:
        if not isinstance(target, dict):
            continue
        source = source_by_id.get(target.get("IndicatorID"))
        if source is None:
            continue
        for field in AUTHOR_INDICATOR_FIELDS:
            if field in source:
                target[field] = deepcopy(source[field])
            else:
                target.pop(field, None)
    return bound


def _trace(response: Any, *, operation_id: str, kind: str, input_checksum: str) -> dict[str, Any]:
    return {"operation_id": operation_id, "kind": kind, "input_checksum": input_checksum,
            "sent": response.sent, "provider": response.provider}


def _strict_json_call(gateway: Any, messages: list[dict[str, str]], *, operation_id: str,
                      max_tokens: int, temperature: float,
                      retry_instruction: str) -> tuple[Any, Any, list[dict[str, Any]]]:
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
            current = [*messages, {"role": "system", "content": retry_instruction}]
    raise AssertionError("unreachable")


def generate(snapshot: dict[str, Any], gateway: Any) -> dict[str, Any]:
    instruction = _frozen_file(snapshot, "generator_prompt").read_text(encoding="utf-8")
    contract = _frozen_file(snapshot, "generation_contract").read_text(encoding="utf-8")
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
        retry_instruction=_frozen_file(snapshot, "protocol_json_retry").read_text(encoding="utf-8"),
    )
    provider_candidate, depth = extract_candidate_as(raw)
    candidate = bind_frozen_author_indicator_content(snapshot, provider_candidate)
    provider_candidate_checksum = checksum(provider_candidate)
    candidate_checksum = checksum(candidate)
    return {"candidate_as": candidate, "candidate_checksum": candidate_checksum,
            "author_content_binding": {
                "source": "frozen_input_snapshot.author_as_example",
                "provider_candidate_checksum": provider_candidate_checksum,
                "bound_candidate_checksum": candidate_checksum,
                "changed": provider_candidate_checksum != candidate_checksum,
            },
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
                   "adversarial_review": {"candidate_conflicts": ["JSON path потенциального противоречия"],
                                          "resolution": "Почему каждый конфликт не нарушает требование; для FAIL — пустая строка допустима"},
                   "findings": [{"code": "string", "severity": "blocking|non_blocking",
                                 "paths": ["JSON path"], "reason": "string",
                                 "requirement_ref": "check_id/source_ref"}],
               }]}}
    messages = [{"role": "system", "content": _frozen_file(snapshot, "tester_prompt").read_text(encoding="utf-8")},
                {"role": "system", "content": _frozen_file(snapshot, "protocol_tester_addendum").read_text(encoding="utf-8")},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    input_checksum = checksum(messages)
    operation_id = f"{snapshot['operation_id']}:tester:{input_checksum[:12]}"
    raw, response, parse_failures = _strict_json_call(
        gateway, messages, operation_id=operation_id, max_tokens=16384, temperature=0,
        retry_instruction=_frozen_file(snapshot, "protocol_json_retry").read_text(encoding="utf-8"),
    )
    checks = normalize_results(plan, raw.get("checks"))
    protected = [item for item in plan["required_checks"] if item.get("protected")]
    challenge_payload = {
        "case": snapshot["case"], "author_as_example": snapshot["author_as_example"],
        "candidate_as": generation["candidate_as"],
        "protected_checks": protected,
        "required_output": payload["required_output"],
        "rules": {
            "purpose": "Ищи опровержение PASS, не подтверждение.",
            "inspect_entire_candidate": True,
            "direct_statement_is_not_uncertain_merely_because_it_has_a_source": True,
            "different_labels_require_different_substance": True,
            "inspect_new_assertions_and_removed_constraints_against_author_example": True,
            "return_each_protected_check_once": True,
        },
    }
    challenge_messages = [
        {"role": "system", "content": _frozen_file(snapshot, "protocol_challenger").read_text(encoding="utf-8")},
        {"role": "user", "content": json.dumps(challenge_payload, ensure_ascii=False)},
    ]
    challenge_checksum = checksum(challenge_messages)
    challenge_operation_id = f"{snapshot['operation_id']}:challenger:{challenge_checksum[:12]}"
    challenge_raw, challenge_response, challenge_failures = _strict_json_call(
        gateway, challenge_messages, operation_id=challenge_operation_id, max_tokens=16384, temperature=0,
        retry_instruction=_frozen_file(snapshot, "protocol_json_retry").read_text(encoding="utf-8"),
    )
    challenge_checks = normalize_results(plan, challenge_raw.get("checks"))
    challenge_by_id = {item["check_id"]: item for item in challenge_checks
                       if item.get("status") != "NOT_APPLICABLE"}
    merged_checks = []
    for item in checks:
        challenged = challenge_by_id.get(item["check_id"])
        if challenged is not None and item.get("protected") and challenged.get("status") != "PASS":
            merged_checks.append(challenged)
        else:
            merged_checks.append(item)
    checks = merged_checks
    aggregation = aggregate(generation["deterministic_validation"], checks)
    return {"protocol": plan["protocol"], "checks": checks, "aggregation": aggregation,
            "provider_operation": {**_trace(response, operation_id=operation_id, kind="independent_tester_v2", input_checksum=input_checksum),
                                   "parse_failures": parse_failures},
            "challenger_operation": {**_trace(challenge_response, operation_id=challenge_operation_id,
                                                kind="independent_tester_v2_challenger",
                                                input_checksum=challenge_checksum),
                                     "parse_failures": challenge_failures}}


def repair_candidate(snapshot: dict[str, Any], generation: dict[str, Any], tested: dict[str, Any],
                     gateway: Any) -> dict[str, Any]:
    """Ask PM-03 for one complete corrected AS; never patch or admit it server-side."""
    instruction = _frozen_file(snapshot, "generator_prompt").read_text(encoding="utf-8")
    repair_instruction, repair_prompt_ref = _load_repair_instruction(ROOT / snapshot["refs"]["repair_package"]["path"])
    payload = {
        "profile": snapshot["profile"], "case": snapshot["case"],
        "author_as_example": snapshot["author_as_example"],
        "rejected_candidate_as": generation["candidate_as"],
        "blocking_failures": tested["aggregation"]["blocking_failures"],
        "deterministic_failures": tested["aggregation"]["deterministic_failures"],
        "requirements": {
            "output_contract": "full_as_json",
            "preserve_case_identity_and_indicator_targets": True,
            "fix_every_listed_failure_in_all_dependent_fields": True,
            "do_not_weaken_or_remove_observation_conditions": True,
            "must_not_create_evidence_or_scores": True,
            "status": "TEST_DRAFT", "current": False,
        },
    }
    messages = [
        {"role": "system", "content": instruction},
        {"role": "system", "content": repair_instruction},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    input_checksum = checksum(messages)
    operation_id = f"{snapshot['operation_id']}:generation:repair:{input_checksum[:12]}"
    raw, response, parse_failures = _strict_json_call(
        gateway, messages, operation_id=operation_id, max_tokens=32768, temperature=0.1,
        retry_instruction=_frozen_file(snapshot, "protocol_json_retry").read_text(encoding="utf-8"),
    )
    provider_candidate, depth = extract_candidate_as(raw)
    candidate = bind_frozen_author_indicator_content(snapshot, provider_candidate)
    provider_candidate_checksum = checksum(provider_candidate)
    candidate_checksum = checksum(candidate)
    return {"candidate_as": candidate, "candidate_checksum": candidate_checksum,
            "author_content_binding": {
                "source": "frozen_input_snapshot.author_as_example",
                "provider_candidate_checksum": provider_candidate_checksum,
                "bound_candidate_checksum": candidate_checksum,
                "changed": provider_candidate_checksum != candidate_checksum,
            },
            "response_envelope_depth": depth,
            "deterministic_validation": deterministic_checks(snapshot, candidate),
            "provider_operation": {**_trace(response, operation_id=operation_id, kind="generation_repair",
                                              input_checksum=input_checksum),
                                   "prompt_ref": repair_prompt_ref,
                                   "parse_failures": parse_failures}}


def prepare(snapshot: dict[str, Any], gateway: Any) -> dict[str, Any]:
    generation = generate(snapshot, gateway)
    tested = test_candidate(snapshot, generation, gateway)
    repair = None
    if (not tested["aggregation"]["admitted_for_participant"]
            and (tested["aggregation"]["blocking_failures"]
                 or tested["aggregation"]["deterministic_failures"])):
        repaired = repair_candidate(snapshot, generation, tested, gateway)
        retested = test_candidate(snapshot, repaired, gateway)
        repair = {
            "original_candidate_checksum": generation["candidate_checksum"],
            "original_author_content_binding": generation["author_content_binding"],
            "original_deterministic_validation": generation["deterministic_validation"],
            "original_generation_operation": generation["provider_operation"],
            "original_tester": tested,
            "repair_generation_operation": repaired["provider_operation"],
        }
        generation, tested = repaired, retested
    compiled_case = None
    execution_rules = None
    if tested["aggregation"]["admitted_for_participant"]:
        compiled_case = compile_case_values(
            case=snapshot["case"], situation=generation["candidate_as"],
            case_source_name=Path(snapshot["refs"]["case"]["path"]).name,
            case_source_checksum=snapshot["refs"]["case"]["sha256"],
            as_source_name=f"generated-{generation['candidate_checksum']}.json",
            as_source_checksum=generation["candidate_checksum"],
            source_schema_profile="functional-personalization-indicator-v1",
        )
        execution_rules = build_execution_rules([compiled_case])
    return {"schema_version": 1, "input_snapshot_checksum": checksum(snapshot),
            "candidate_as": generation["candidate_as"], "candidate_checksum": generation["candidate_checksum"],
            "author_content_binding": generation["author_content_binding"],
            "deterministic_validation": generation["deterministic_validation"],
            "generation_operation": generation["provider_operation"], "tester": tested,
            "repair": repair,
            "admitted_for_participant": tested["aggregation"]["admitted_for_participant"],
            "compiled_case": compiled_case, "execution_rules": execution_rules}


def build_persistence_trace(snapshot: dict[str, Any], prepared: dict[str, Any]) -> dict[str, Any]:
    """Build the immutable PM-03 -> PM-04 hand-off kept in the AS snapshot."""
    if checksum(snapshot) != prepared.get("input_snapshot_checksum"):
        raise ValueError("M5_FUNCTIONAL_INPUT_SNAPSHOT_MISMATCH")
    candidate = prepared.get("candidate_as")
    if not isinstance(candidate, dict) or checksum(candidate) != prepared.get("candidate_checksum"):
        raise ValueError("M5_FUNCTIONAL_CANDIDATE_SNAPSHOT_MISMATCH")
    tester = prepared.get("tester") or {}
    if not isinstance(tester.get("provider_operation", {}).get("input_checksum"), str):
        raise ValueError("M5_FUNCTIONAL_TESTER_INPUT_TRACE_REQUIRED")
    return {
        "schema_version": 2,
        "input_snapshot_checksum": prepared["input_snapshot_checksum"],
        "source_snapshot": {
            "case": snapshot["case"],
            "author_as_example": snapshot["author_as_example"],
            "refs": snapshot["refs"],
            "profile_checksum": snapshot["refs"]["profile"]["sha256"],
        },
        "accepted_as": candidate,
        "candidate_checksum": prepared["candidate_checksum"],
        "author_content_binding": prepared["author_content_binding"],
        "compiled_case_checksum": runtime_checksum(prepared["compiled_case"]),
        "execution_rules_checksum": runtime_checksum(prepared["execution_rules"]),
        "deterministic_validation": prepared["deterministic_validation"],
        "generation_operation": prepared["generation_operation"],
        "repair": prepared.get("repair"),
        "tester": tester,
        "tester_input_checksum": tester["provider_operation"]["input_checksum"],
        "admitted_for_participant": prepared["admitted_for_participant"],
    }
