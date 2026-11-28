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
from time import perf_counter
from typing import Any

from Api import m5_passport_generation as passport_generation
from Api import m5_review_clarification as review_clarification
from Api.llm.contracts import LlmGatewayError
from Api.m5_addressed_contract import validate_scenario_contract
from Api.m5_passport import allowed_profile, missing
from Api.m5_functional_personalization import extract_candidate_as
from Api.m5_functional_tester import (
    BATTERY_REVIEW_SCOPES, EXPLICIT_REVIEW_BATCH_PROTOCOLS, SERVER_BOUND_REVIEW_PACKAGES,
    aggregate, aggregate_reviews, build_applicability_plan, load_protocol, normalize_results, reviewer_checks,
)
from Api.m5_case_runtime import checksum as runtime_checksum
from scripts.build_m5_sales_package import build_execution_rules, compile_case_values
from Api.m5_runtime_rules import load_runtime_rule_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.5"
SOURCE = PACKAGE / "sources/functional-v0.2"
REPAIR_PACKAGE = ROOT / "assessment_definitions/prompts/m5_functional_repair/v1"
PROTOCOL_PACKAGE = ROOT / "assessment_definitions/prompts/m5_functional_protocol/v2"
RUNTIME_PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.2.0"

AUTHOR_INDICATOR_FIELDS = (
    "IndicatorID", "SkillID", "ComponentID", "Название", "Версия M2",
    "Нормативный источник", "Материалы и факты", "Конкретное условие",
    "Что сохранить при адаптации", "Дефект потери", "Форма проявления",
    "Проектная возможность", "Фактическое возникновение", "Evidence и IA",
    "Связанные инварианты",
)
INDICATOR_LAYER_FIELD = "IndicatorTargetLayers"
INDICATOR_LAYER_CONTRACT_VERSION = "1.0.0"
ADAPTED_TARGET_FIELDS = (
    "IndicatorID", "Конкретное условие", "Форма проявления", "Дефект потери",
    "Материалы и факты", "Что сохранить при адаптации", "Связанные инварианты",
    "material_refs", "event_refs", "character_refs", "authority_refs", "author_mapping",
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


def _protocol_package_ref(protocol_package: Path) -> dict[str, str]:
    raw = (protocol_package / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    expected_version = {"v1": "1.0.0", "v2": "2.0.0"}.get(protocol_package.name)
    artifacts = manifest.get("artifacts")
    expected_names = {"json-retry.md", "tester-addendum.md", "challenger.md"}
    if (not expected_version or manifest.get("schema_version") != 1
            or manifest.get("id") != "m5_functional_protocol"
            or manifest.get("version") != expected_version
            or manifest.get("status") != "draft"
            or not isinstance(artifacts, list)
            or {item.get("name") for item in artifacts if isinstance(item, dict)} != expected_names
            or len(artifacts) != len(expected_names)):
        raise ValueError("M5_FUNCTIONAL_PROTOCOL_PACKAGE_INVALID")
    for item in artifacts:
        if item.get("sha256") != checksum((protocol_package / item["name"]).read_bytes()):
            raise ValueError("M5_FUNCTIONAL_PROTOCOL_PACKAGE_INVALID")
    return {"id": manifest["id"], "version": manifest["version"],
            "checksum": checksum(raw), "path": str(protocol_package.relative_to(ROOT))}


def build_historical_input_snapshot(*, case_id: str, profile: dict[str, Any], operation_id: str,
                         synthetic: bool = False, case_value: dict[str, Any] | None = None,
                         author_as_example: dict[str, Any] | None = None,
                         profile_checksum: str | None = None,
                         case_version_checksum: str | None = None,
                         source_root: Path = SOURCE,
                         repair_package: Path = REPAIR_PACKAGE,
                         protocol_package: Path = PROTOCOL_PACKAGE,
                         provider_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reproduce the input contract of archived 0.2–0.5 laboratory runs."""
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
    refs = {
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
        "protocol_package": _protocol_package_ref(protocol_package),
        **{
            f"protocol_{name.replace('-', '_')}": {
                "path": str((protocol_package / f"{name}.md").relative_to(ROOT)),
                "sha256": checksum((protocol_package / f"{name}.md").read_bytes()),
            }
            for name in ("json-retry", "tester-addendum", "challenger")
        },
    }
    if provider_contract is not None:
        refs["provider_contract"] = {key: provider_contract[key] for key in (
            "version", "checksum", "provider", "endpoint", "model", "thinking", "supported_response_formats"
        )}
    if (package_manifest.get("compiler") or {}).get("source_schema_profile") == "functional-personalization-indicator-v2":
        adaptation_contract = source_root.parents[1] / "indicator-adaptation-contract.json"
        refs["indicator_adaptation_contract"] = {
            "path": str(adaptation_contract.relative_to(ROOT)),
            "sha256": checksum(adaptation_contract.read_bytes()),
        }
    return {
        "schema_version": 1,
        "operation_id": operation_id,
        "synthetic": synthetic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": case,
        "author_as_example": example,
        "profile": clean_profile,
        "refs": refs,
    }


def build_passport_snapshot(*, case_version: dict, profile: dict, operation_id: str, synthetic: bool = False,
                            profile_checksum: str | None = None, case_version_checksum: str | None = None,
                            as_package: Path = passport_generation.CURRENT_AS_PACKAGE,
                            review_response_package: Path | None = None,
                            m2_path: Path = passport_generation.M2, m3_path: Path = passport_generation.M3,
                            provider_contract: dict[str, Any] | None = None,
                            profile_sources: dict | None = None,
                            selected_base_role: str | None = None,
                            runtime_rule_ref: dict | None = None, package_ref: dict | None = None,
                            project_role: dict | None = None,
                            project_role_prompt: Path | None = None,
                            battery_scenario_package: Path | None = None, battery_pilot: bool = False,
                            battery_profile_fit: dict | None = None) -> dict:
    from Api import m5_battery_contract

    contract, contract_ref, refs = passport_generation.read_as_package(as_package)
    if review_response_package is not None:
        if refs["protocol_package"]["version"] != "7.0.0":
            raise ValueError("M5_REVIEW_RESPONSE_CONTRACT_PROTOCOL_MISMATCH")
        refs["review_response"] = review_clarification.load_response_contract(review_response_package)
    case_contract_ref = contract.pop("case_as_contract_ref", contract_ref)
    event_material_rules = contract.pop("event_material_rules", None)
    actual = runtime_checksum(case_version)
    battery = case_version.get("passport_version") == "1.2"
    if battery:
        if (not (synthetic or battery_pilot) or battery_scenario_package is None
                or (battery_pilot and refs["protocol_package"]["version"] not in SERVER_BOUND_REVIEW_PACKAGES.values())):
            raise ValueError("M5_BATTERY_PREPARATION_NOT_ENABLED")
    if battery_pilot and not battery:
        raise ValueError("M5_BATTERY_PILOT_CASE_VERSION_INVALID")
    if battery:
        case_contract_ref = contract.pop("battery_case_as_contract_ref", contract_ref)
    if case_version_checksum and case_version_checksum != actual:
        raise missing(case_version["case_id"], case_version["version"], "content_checksum")
    projected, m2_ref, m2 = passport_generation.normalize_case(
        case_version, case_contract_ref, m2_path=m2_path, m3_path=m3_path,
    )
    if selected_base_role is not None and selected_base_role != projected["base_role"]:
        raise missing(projected["case_id"], projected["version"], "BaseRole→profile")
    case = {"CaseID": projected["case_id"], "Version": projected["version"], "Паспорт": projected["passport"]}
    design = (runtime_rule_ref or {}).get("scenario_contract")
    battery_design = None
    fit = None
    if battery:
        battery_design = m5_battery_contract.load_scenario(projected, battery_scenario_package, pilot=battery_pilot)
        fit = m5_battery_contract.validate_profile(profile, battery_design, battery_profile_fit)
        if fit is not None:
            if fit["status"] != "applicable":
                raise ValueError(f"M5_BATTERY_PROFILE_{fit['status'].upper()}:18/{fit['criterion']}: {fit['message']}")
            refs["battery_profile_fit_checksum"] = runtime_checksum(fit)
        contract = m5_battery_contract.candidate_contract(contract)
        refs["battery_scenario"] = battery_design["ref"]
        package_ref = {**(package_ref or {}), "compiler": {"source_schema_profile": "functional-passport-v1.2"}}
    if design is not None:
        validate_scenario_contract(projected, design)
        contract = passport_generation.addressed_candidate_contract(contract, design)
    delivery = (passport_generation.build_event_material_delivery(projected, event_material_rules)
                if event_material_rules is not None and design is None and not battery else None)
    refs.update({
        "package": package_ref or {"compiler": {"source_schema_profile": "functional-passport-v1"}},
        "case": {"passport": projected["passport_source"], "case_version_checksum": actual},
        "m2": m2_ref, "as_contract": contract_ref,
        "runtime_rule": runtime_rule_ref,
        "profile": {"sha256": profile_checksum or checksum(profile), "sources": profile_sources or {}},
    })
    if provider_contract is not None:
        refs["provider_contract"] = {key: provider_contract[key] for key in (
            "version", "checksum", "provider", "endpoint", "model", "thinking", "supported_response_formats",
        )}
    if project_role is not None:
        if project_role_prompt is None:
            raise ValueError("M5_EDUCATIONAL_ROLE_PROMPT_NOT_FROZEN")
        refs["project_role_prompt"] = {
            "path": str(project_role_prompt.relative_to(ROOT)),
            "sha256": checksum(project_role_prompt.read_bytes()),
        }
        refs["project_role"] = {key: project_role[key] for key in ("code", "version", "checksum", "snapshot_checksum")}
    profile_input = allowed_profile(profile)
    if fit is not None:
        from Api.m5_battery_profile import FIELDS

        profile_input["user_context"].update({key: profile["user_context"][key] for key in FIELDS
                                              if key in profile["user_context"]})
    snapshot = {
        "schema_version": 2, "operation_id": operation_id, "synthetic": synthetic,
        "created_at": datetime.now(timezone.utc).isoformat(), "case": case, "case_version": projected,
        "as_contract": contract, "profile": profile_input, "refs": refs,
        **({"project_role": {**project_role, "interactions": list(project_role["interactions"])}}
           if project_role is not None else {}),
        **({"scenario_contract": design} if design is not None else {}),
        **({"battery_scenario": battery_design} if battery_design is not None else {}),
        **({"battery_pilot": True} if battery_pilot else {}),
        **({"event_material_delivery": delivery} if delivery is not None else {}),
    }
    # Resolve all mandatory checks before entering the provider.
    try:
        if "tester_protocol" in refs:
            protocol = load_protocol(_frozen_file(snapshot, "tester_protocol"))
            if protocol["version"] in SERVER_BOUND_REVIEW_PACKAGES and (
                SERVER_BOUND_REVIEW_PACKAGES[protocol["version"]] != refs["protocol_package"]["version"]
            ):
                raise ValueError("M5_FUNCTIONAL_REVIEW_PROTOCOL_MISMATCH")
            if protocol.get("scope") in BATTERY_REVIEW_SCOPES:
                from Api.m5_battery_review import build_plan

                if not battery:
                    raise ValueError("M5_BATTERY_REVIEW_REQUIRES_DIAGNOSTIC_PASSPORT")
                snapshot["applicability_plan"] = build_plan(
                    snapshot, protocol, _frozen_file(snapshot, "case_content_contract"), m2,
                )
                return snapshot
            content = None if battery else passport_generation.read_case_content_contract(
                _frozen_file(snapshot, "case_content_contract"), projected["case_id"],
            )
            snapshot["applicability_plan"] = build_applicability_plan(
                case, protocol, case_content_contract=content, scenario_qa=battery,
            )
            if content:
                indicator_ids = content["indicator_fields"].keys() | set(content["initial_material_refs_required"])
                if not indicator_ids <= {target["indicator_id"] for target in projected["indicator_targets"]}:
                    raise ValueError("M5_AS_CASE_CONTENT_INDICATOR_NOT_IN_PASSPORT")
                snapshot["case_content_contract"] = content
                snapshot["m2_indicator_descriptors"] = {key: m2[key]["descriptor"] for key in sorted(indicator_ids)}
        else:
            build_applicability_plan(case)
    except (KeyError, TypeError, ValueError) as exc:
        raise missing(projected["case_id"], projected["version"], "16–18,21–22→Tester") from exc
    return snapshot


def _frozen_file(snapshot: dict[str, Any], ref_name: str) -> Path:
    ref = snapshot["refs"][ref_name]
    path = ROOT / ref["path"]
    if not path.is_file():
        raise ValueError(f"CYCLE_DEPENDENCY_UNAVAILABLE:{ref_name}")
    if checksum(path.read_bytes()) != ref["sha256"]:
        raise ValueError(f"CYCLE_DEPENDENCY_CHECKSUM_MISMATCH:{ref_name}")
    return path


def deterministic_checks(snapshot: dict[str, Any], candidate: Any) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors = []
    battery_review = snapshot.get("applicability_plan", {}).get("protocol", {}).get("scope") in BATTERY_REVIEW_SCOPES

    def check(code: str, passed: bool, actual: Any = None, *, path: str = "candidate_as", **diagnostic: Any) -> None:
        row = {"code": code, "result": "PASS" if passed else "FAIL", "actual": actual}
        if not passed and (diagnostic or battery_review):
            row.update(path=path, **diagnostic)
        checks.append(row)
        if not passed:
            errors.append({"error_class": "candidate_validation", "check": code, "path": path})
    check("json_object", isinstance(candidate, dict), **(
        {"actual": type(candidate).__name__, "expected": "object", "reason": "Подготовка принимает объект AS."}
        if battery_review else {}
    ))
    if not isinstance(candidate, dict):
        return {"status": "FAIL", "checks": checks, "errors": errors}
    if "as_contract" in snapshot:
        serialized = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
        check("response_size", len(serialized) <= snapshot["as_contract"]["maximum_output_characters"],
              len(serialized), **(
                  {"expected": {"maximum": snapshot["as_contract"]["maximum_output_characters"]},
                   "reason": "Размер AS должен укладываться в контракт генерации."}
                  if battery_review else {}
              ))
        forbidden = {"Evidence", "IA", "participant_score", "participant_level", "author_assessment_situation", "author_as_example"}
        def forbidden_keys(value):
            if isinstance(value, dict):
                return (set(value) & forbidden) | set().union(*(forbidden_keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(forbidden_keys(item) for item in value))
            return set()
        violations = sorted(forbidden_keys(candidate))
        check("no_premature_assessment", not violations, violations, **(
            {"expected": [], "reason": "В AS отсутствуют поля оценки, Evidence и авторские AS."}
            if battery_review else {}
        ))
        if "battery_scenario" in snapshot:
            from Api.m5_battery_contract import validate_candidate

            missing_paths = validate_candidate(snapshot, candidate, check, detailed=battery_review)
        else:
            missing_paths = passport_generation.validate_candidate(snapshot, candidate, check)
        return {"status": "FAIL" if errors else "PASS", "checks": checks, "errors": errors,
                **({"missing_required_paths": missing_paths} if missing_paths else {})}
    expected = snapshot["author_as_example"]
    package_ref = (snapshot.get("refs") or {}).get("package") or {}
    compiler = package_ref.get("compiler") or {}
    required = set(expected)
    if compiler.get("source_schema_profile") == "functional-personalization-indicator-v2":
        required.add(INDICATOR_LAYER_FIELD)
    check("top_level_contract", required <= set(candidate), sorted(required - set(candidate)))
    check("case_identity", candidate.get("CaseID") == expected.get("CaseID") and candidate.get("CaseVersion") == expected.get("CaseVersion"))
    check("base_role", candidate.get("BaseRole") == expected.get("BaseRole"), candidate.get("BaseRole"))
    check("indicator_targets", candidate.get("IndicatorIDs") == expected.get("IndicatorIDs"), candidate.get("IndicatorIDs"))
    check("m2_versions", candidate.get("Версии M2") == expected.get("Версии M2"))
    def indexed(values: Any, field: str) -> tuple[dict[str, dict[str, Any]], list[Any]]:
        if not isinstance(values, list):
            return {}, ["NOT_A_LIST"]
        invalid = [index for index, item in enumerate(values)
                   if not isinstance(item, dict) or not isinstance(item.get(field), str)
                   or not item.get(field).strip()]
        ids = [item[field] for item in values if isinstance(item, dict)
               and isinstance(item.get(field), str) and item.get(field).strip()]
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        return ({item[field]: item for item in values if isinstance(item, dict)
                 and isinstance(item.get(field), str) and item.get(field).strip()},
                [{"invalid_indexes": invalid}, {"duplicate_ids": duplicates}]
                if invalid or duplicates else [])
    if compiler.get("source_schema_profile") == "functional-personalization-indicator-v1":
        expected_targets = expected.get("IndicatorObservability")
        candidate_targets = candidate.get("IndicatorObservability")
        expected_by_id, expected_shape_errors = indexed(expected_targets, "IndicatorID")
        candidate_by_id, candidate_shape_errors = indexed(candidate_targets, "IndicatorID")
        check("indicator_content_target_set", bool(expected_by_id)
              and not expected_shape_errors and not candidate_shape_errors
              and len(candidate_targets) == len(expected_targets)
              and set(candidate_by_id) == set(expected_by_id),
              candidate_shape_errors or sorted(candidate_by_id))
        differences = []
        if set(candidate_by_id) == set(expected_by_id):
            for indicator_id, source_target in expected_by_id.items():
                candidate_target = candidate_by_id[indicator_id]
                for field in AUTHOR_INDICATOR_FIELDS:
                    if candidate_target.get(field) != source_target.get(field):
                        differences.append({"indicator_id": indicator_id, "field": field})
        check("indicator_author_content_preserved", not differences, differences)
    if compiler.get("source_schema_profile") == "functional-personalization-indicator-v2":
        expected_targets = expected.get("IndicatorObservability")
        candidate_targets = candidate.get("IndicatorObservability")
        expected_by_id, expected_shape_errors = indexed(expected_targets, "IndicatorID")
        candidate_by_id, candidate_shape_errors = indexed(candidate_targets, "IndicatorID")
        check("indicator_content_target_set", bool(expected_by_id)
              and not expected_shape_errors and not candidate_shape_errors
              and len(candidate_targets) == len(expected_targets)
              and set(candidate_by_id) == set(expected_by_id),
              candidate_shape_errors or sorted(candidate_by_id))
        differences = []
        if set(candidate_by_id) == set(expected_by_id):
            for indicator_id, source_target in expected_by_id.items():
                candidate_target = candidate_by_id[indicator_id]
                for field in AUTHOR_INDICATOR_FIELDS:
                    if candidate_target.get(field) != source_target.get(field):
                        differences.append({"indicator_id": indicator_id, "field": field})
        check("indicator_author_content_preserved", not differences, differences)
        layers = candidate.get(INDICATOR_LAYER_FIELD)
        author_layer = layers.get("author") if isinstance(layers, dict) else None
        adapted_layer = layers.get("adapted") if isinstance(layers, dict) else None
        check("indicator_layer_contract", isinstance(layers, dict)
              and layers.get("contract_version") == INDICATOR_LAYER_CONTRACT_VERSION)
        author_targets = author_layer.get("targets") if isinstance(author_layer, dict) else None
        check("indicator_author_layer_checksum", isinstance(author_layer, dict)
              and author_layer.get("version") == "functional-indicator-author/1.0.0"
              and author_layer.get("source_ref") == snapshot["refs"]["author_as_example"]
              and author_targets == expected_targets
              and author_layer.get("checksum") == checksum(expected_targets))
        adapted_targets = adapted_layer.get("targets") if isinstance(adapted_layer, dict) else None
        adapted_by_id, adapted_shape_errors = indexed(adapted_targets, "IndicatorID")
        check("indicator_adapted_target_set", bool(expected_by_id)
              and not adapted_shape_errors and len(adapted_targets) == len(expected_targets)
              and set(adapted_by_id) == set(expected_by_id),
              adapted_shape_errors or sorted(adapted_by_id))
        materials_by_id, material_shape_errors = indexed(candidate.get("Материалы"), "MaterialID")
        events_by_id, event_shape_errors = indexed(candidate.get("События"), "EventID")
        characters_by_id, character_shape_errors = indexed(candidate.get("Активные персонажи"), "CharacterID")
        check("indicator_reference_namespaces_unambiguous",
              not material_shape_errors and not event_shape_errors and not character_shape_errors,
              {"materials": material_shape_errors, "events": event_shape_errors,
               "characters": character_shape_errors})
        material_ids = set(materials_by_id)
        event_ids = set(events_by_id)
        character_ids = set(characters_by_id)
        authority_ids = {f"character:{character_id}" for character_id in characters_by_id}
        authority_ids.add("participant")
        adapted_failures = []
        for indicator_id, target in adapted_by_id.items():
            if indicator_id not in expected_by_id:
                continue  # The target-set check owns this error, not mapping lookup.
            missing = [field for field in ADAPTED_TARGET_FIELDS if field not in target]
            mapping = target.get("author_mapping")
            expected_pointer = f"/IndicatorObservability/{list(expected_by_id).index(indicator_id)}"
            ref_type_errors = {}
            for field in ("material_refs", "event_refs", "character_refs", "authority_refs"):
                values = target.get(field)
                if (not isinstance(values, list) or any(not isinstance(value, str) or not value.strip()
                                                        for value in values)
                        or (isinstance(values, list) and len(values) != len(set(values)))):
                    ref_type_errors[field] = values
            def refs(field: str) -> set[str]:
                values = target.get(field)
                return set(values) if isinstance(values, list) and all(
                    isinstance(value, str) for value in values
                ) else set()
            invalid = {
                "missing_fields": missing,
                "empty_condition": not str(target.get("Конкретное условие") or "").strip(),
                "material_refs": sorted(refs("material_refs") - material_ids),
                "event_refs": sorted(refs("event_refs") - event_ids),
                "character_refs": sorted(refs("character_refs") - character_ids),
                "authority_refs": sorted(refs("authority_refs") - authority_ids),
                "reference_types": ref_type_errors,
                "author_mapping": mapping != {
                    "source_pointer": expected_pointer,
                    "source_checksum": checksum(expected_by_id[indicator_id]),
                },
            }
            if (missing or invalid["empty_condition"] or invalid["material_refs"]
                    or invalid["event_refs"] or invalid["character_refs"]
                    or invalid["authority_refs"] or invalid["reference_types"]
                    or invalid["author_mapping"]):
                adapted_failures.append({"indicator_id": indicator_id, **invalid})
        check("indicator_adaptation_references", not adapted_failures, adapted_failures)
        for failure in adapted_failures:
            for field in ("material_refs", "event_refs", "character_refs", "authority_refs", "author_mapping"):
                if failure.get(field) or field in failure["reference_types"]:
                    errors.append({"error_class": "candidate_validation", "check": "indicator_adaptation_references",
                                   "path": f"candidate_as/{INDICATOR_LAYER_FIELD}/adapted/targets/{failure['indicator_id']}/{field}"})
        check("indicator_adapted_layer_checksum", isinstance(adapted_layer, dict)
              and adapted_layer.get("version") == "functional-indicator-adaptation/1.0.0"
              and adapted_layer.get("checksum") == checksum(adapted_targets))
    # Only validated namespaces may feed dependent reference checks, including
    # legacy compiler profiles. Empty lists remain valid when the passport allows.
    namespaces = {}
    for field, id_field in (("Активные персонажи", "CharacterID"),
                            ("Материалы", "MaterialID"), ("События", "EventID")):
        namespace, shape_errors = indexed(candidate.get(field), id_field)
        namespaces[field] = namespace
        check("namespace_shape:" + id_field, not shape_errors, shape_errors,
              path="candidate_as/" + field)
    characters = candidate.get("Активные персонажи")
    check("character_count", isinstance(characters, list) and len(characters) == len(expected.get("Активные персонажи", [])))
    material_ids = set(namespaces["Материалы"])
    starts = candidate.get("Стартовые MaterialIDs")
    check("start_material_refs", isinstance(starts, list)
          and all(isinstance(value, str) and value.strip() for value in starts)
          and set(starts) <= material_ids, starts, path="candidate_as/Стартовые MaterialIDs")
    events = candidate.get("События")
    check("events_present", isinstance(events, list) and len(events) == len(expected.get("События", [])))
    forbidden = {"Evidence", "IA", "participant_score", "participant_level"}
    def keys(value: Any) -> set[str]:
        if isinstance(value, dict): return set(value) | set().union(*(keys(x) for x in value.values()), set())
        if isinstance(value, list): return set().union(*(keys(x) for x in value), set())
        return set()
    check("no_premature_assessment", not (keys(candidate) & forbidden), sorted(keys(candidate) & forbidden))
    return {"status": "PASS" if all(x["result"] == "PASS" for x in checks) else "FAIL",
            "checks": checks, "errors": errors}


def bind_indicator_target_layers(snapshot: dict[str, Any], candidate: Any) -> Any:
    """Freeze the author layer and retain the provider projection as a distinct layer."""
    package_ref = (snapshot.get("refs") or {}).get("package") or {}
    compiler = package_ref.get("compiler") or {}
    if (compiler.get("source_schema_profile") != "functional-personalization-indicator-v2"
            or not isinstance(candidate, dict)):
        return candidate
    source_targets = snapshot["author_as_example"].get("IndicatorObservability")
    candidate_targets = candidate.get("IndicatorObservability")
    if not isinstance(source_targets, list) or not isinstance(candidate_targets, list):
        return candidate
    bound = deepcopy(candidate)
    adapted_targets = deepcopy(candidate_targets)
    source_indexes = {item.get("IndicatorID"): index for index, item in enumerate(source_targets)
                      if isinstance(item, dict)}
    for target in adapted_targets:
        if not isinstance(target, dict):
            continue
        indicator_id = target.get("IndicatorID")
        source_index = source_indexes.get(indicator_id) if isinstance(indicator_id, str) else None
        mapping = target.get("author_mapping")
        expected_pointer = (f"/IndicatorObservability/{source_index}"
                            if source_index is not None else None)
        if source_index is not None and isinstance(mapping, dict) and mapping.get("source_pointer") == expected_pointer:
            mapping["source_checksum"] = checksum(source_targets[source_index])
    bound["IndicatorObservability"] = deepcopy(source_targets)
    bound[INDICATOR_LAYER_FIELD] = {
        "contract_version": INDICATOR_LAYER_CONTRACT_VERSION,
        "author": {
            "version": "functional-indicator-author/1.0.0",
            "source_ref": deepcopy(snapshot["refs"]["author_as_example"]),
            "checksum": checksum(source_targets),
            "targets": deepcopy(source_targets),
        },
        "adapted": {
            "version": "functional-indicator-adaptation/1.0.0",
            "checksum": checksum(adapted_targets),
            "targets": adapted_targets,
        },
    }
    return bound


# Compatibility alias for callers/tests created for package 0.3.
bind_frozen_author_indicator_content = bind_indicator_target_layers


def concrete_adapted_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return the concrete AS view while keeping the frozen author layer separate."""
    concrete = deepcopy(candidate)
    layers = candidate.get(INDICATOR_LAYER_FIELD)
    adapted = layers.get("adapted") if isinstance(layers, dict) else None
    targets = adapted.get("targets") if isinstance(adapted, dict) else None
    if isinstance(targets, list):
        concrete["IndicatorObservability"] = deepcopy(targets)
        concrete.pop(INDICATOR_LAYER_FIELD, None)
    return concrete


def _trace(response: Any, *, operation_id: str, kind: str, input_checksum: str) -> dict[str, Any]:
    return {"operation_id": operation_id, "kind": kind, "input_checksum": input_checksum,
            "sent": response.sent, "provider": response.provider}


def _review_message(payload: dict, batch_checks: list[dict], *, passport: bool) -> dict[str, str]:
    if payload.get("protocol", {}).get("version") in EXPLICIT_REVIEW_BATCH_PROTOCOLS:
        required_output = deepcopy(payload["required_output"])
        required_output["checks"][0]["check_id"] = "Copy each id from review_dispatch.check_ids exactly once"
        dispatch = {**payload["review_dispatch"], "check_ids": [item["check_id"] for item in batch_checks]}
        payload = {**payload, "required_output": required_output, "review_dispatch": dispatch}
    if passport:
        payload = passport_generation.compact_review_payload(payload, batch_checks)
    return {"role": "user", "content": json.dumps(
        payload, ensure_ascii=False, separators=(",", ":") if passport else None,
    )}


def _message_fingerprint(messages: list[dict[str, str]]) -> tuple[str, int]:
    encoded = canonical(messages)
    return checksum(encoded), len(encoded)


def _strict_json_call(gateway: Any, messages: list[dict[str, str]], *, operation_id: str,
                      max_tokens: int, temperature: float,
                      retry_instruction: str, review_checks: list[dict[str, Any]] | None = None,
                      candidate_checksum: str | None = None,
                      calls: list[dict[str, Any]] | None = None,
                      initial_fingerprint: tuple[str, int] | None = None,
                      record_response: bool = False, allow_invalid_repair: bool = False,
                      review_context: dict[str, Any] | None = None,
                      budget: dict[str, Any] | None = None, clarification: bool = False,
                      ) -> tuple[Any, Any, list[dict[str, Any]]]:
    """Retry one malformed envelope, or use the remaining attempt for a scoped clarification."""
    failures: list[dict[str, Any]] = []
    current = list(messages)
    if budget is None:
        budget = _operation_budget(gateway, operation_id)
    suffix = review_clarification.CLARIFICATION_SUFFIX if clarification else ":json-retry"
    for attempt in ((2,) if clarification else (1, 2)):
        routing_key = operation_id if attempt == 1 else operation_id + suffix
        fingerprint = (initial_fingerprint if attempt == 1 and initial_fingerprint is not None
                       else _message_fingerprint(current))
        input_checksum, messages_size = fingerprint
        # The trusted synchronous gateway returns the trace of the request it actually sent.
        # Bind the receipt before yielding to the gateway, independently of model output.
        dispatch = ({
            **review_context, "request_sha256": input_checksum, "request_id": routing_key, "attempt": attempt,
        } if review_context is not None else None)
        started_at = perf_counter()
        response = gateway.chat_with_trace(
            current, temperature=temperature, timeout_seconds=300, max_tokens=max_tokens,
            routing_key=routing_key,
            response_format={"type": "json_object"}, **budget,
        )
        binding_matches = True
        if dispatch is not None:
            sent_messages = response.sent.get("messages")
            binding_matches = isinstance(sent_messages, list) and _message_fingerprint(sent_messages) == fingerprint
        if calls is not None:
            elapsed_ms = (perf_counter() - started_at) * 1000
            calls.append({
                "attempt": attempt, "input_checksum": input_checksum, "message_count": len(current),
                "messages_utf8_bytes": messages_size, "elapsed_ms": round(elapsed_ms, 3),
                **({"response_content": response.content} if record_response else {}),
                **({"review_dispatch": dispatch, "review_binding_matches": binding_matches,
                    "response_sha256": checksum(response.content.encode("utf-8"))} if dispatch is not None else {}),
                "model": response.sent.get("model"), "parameters": response.sent.get("parameters"),
                "provider": {key: response.provider.get(key) for key in (
                    "model", "revision", "finish_reason", "usage", "queue_wait_ms", "transport_attempts",
                )},
            })
        if not binding_matches:
            return {"checks": [{
                "check_id": item["check_id"], "status": "TECHNICAL_ERROR",
                "reason": "Отправка рецензенту не подтверждена трассой шлюза.",
                "protocol_error_code": "REVIEW_DISPATCH_MISMATCH",
            } for item in review_checks]}, response, failures
        try:
            return json.loads(response.content), response, failures
        except json.JSONDecodeError as exc:
            failures.append({"attempt": attempt, "code": "PROVIDER_JSON_INVALID",
                             "position": exc.pos, "response_characters": len(response.content),
                             "finish_reason": response.provider.get("finish_reason")})
            if attempt == 2:
                if review_checks is not None:
                    return {"candidate_checksum": candidate_checksum, "checks": [{
                        "check_id": item["check_id"], "status": "TECHNICAL_ERROR",
                        "reason": "Исчерпан технический повтор JSON-ответа проверки.",
                        "protocol_error_code": "PROVIDER_JSON_INVALID_RETRY_EXHAUSTED",
                    } for item in review_checks]}, response, failures
                if allow_invalid_repair:
                    return None, response, failures
                raise ValueError("M5_FUNCTIONAL_PROVIDER_JSON_INVALID") from exc
            current = [*messages, {"role": "system", "content": retry_instruction}]
    raise AssertionError("unreachable")


def _operation_budget(gateway: Any, operation_id: str) -> dict:
    return ({"operation_budget": gateway.operation_budget(operation_id)}
            if hasattr(gateway, "operation_budget") else {})


def _bound_batch_checks(raw: Any, batch_checks: list[dict[str, Any]],
                        expected_candidate_checksum: str | None = None, *, reviewer: str = "Tester") -> list[dict[str, Any]]:
    """Only check IDs requested in this batch may satisfy it."""
    ids = {item["check_id"] for item in batch_checks}
    if expected_candidate_checksum is not None:
        actual = raw.get("candidate_checksum") if isinstance(raw, dict) else None
        if actual != expected_candidate_checksum:
            reason = (f"Ответ {reviewer} не содержит привязки к кандидату."
                      if actual is None else f"Ответ {reviewer} относится к другому кандидату.")
            return [{"check_id": check_id, "status": "TECHNICAL_ERROR", "reason": reason,
                     "protocol_error_code": ("CANDIDATE_CHECKSUM_REQUIRED" if actual is None
                                             else "CANDIDATE_CHECKSUM_MISMATCH")}
                    for check_id in (item["check_id"] for item in batch_checks)]
    checks = raw.get("checks") if isinstance(raw, dict) else None
    return [item for item in checks if isinstance(item, dict)
            and isinstance(item.get("check_id"), str) and item["check_id"] in ids] \
        if isinstance(checks, list) else []


def _review_batch(gateway: Any, messages: list[dict], *, plan: dict, review_basis: dict,
                  snapshot: dict, reviewer: str, batch_no: int, context: dict | None,
                  review_ref: dict, candidate_checksum: str | None, echo_checksum: bool,
                  instruction: str | None) -> tuple[list[dict], dict]:
    definitions = plan["required_checks"]
    fingerprint = _message_fingerprint(messages)
    operation_id = f"{snapshot['operation_id']}:{reviewer}:{batch_no:02d}:{fingerprint[0][:12]}"
    budget = _operation_budget(gateway, operation_id)
    retry_instruction = _frozen_file(snapshot, "protocol_json_retry").read_text(encoding="utf-8")
    calls = []
    raw, response, parse_failures = _strict_json_call(
        gateway, messages, operation_id=operation_id, max_tokens=16384, temperature=0,
        retry_instruction=retry_instruction, review_checks=definitions, candidate_checksum=candidate_checksum,
        calls=calls, initial_fingerprint=fingerprint, record_response=bool(review_ref),
        review_context=context, budget=budget,
    )
    checks = _bound_batch_checks(
        raw, definitions, candidate_checksum if echo_checksum else None, reviewer=reviewer.capitalize(),
    )
    batch = {
        **_trace(response, operation_id=operation_id, input_checksum=fingerprint[0],
                 kind="independent_tester_v2_batch" if reviewer == "tester" else "independent_tester_v2_challenger_batch"),
        "batch_no": batch_no, "required_check_ids": [item["check_id"] for item in definitions],
        "parse_failures": parse_failures, "calls": calls,
        **({**review_ref, "reviewer": reviewer} if review_ref else {}),
    }
    if instruction is None or len(calls) != 1 or calls[0]["review_binding_matches"] is not True:
        return checks, batch
    scoped_messages, scope = review_clarification.clarification_messages(
        plan, checks, call=calls[0], initial_messages=messages, review_basis=review_basis, instruction=instruction,
    )
    if not scope:
        return checks, batch
    scoped_context = {**context, "check_ids": [item["check_id"] for item in scope]}
    started = perf_counter()
    try:
        corrected, correction_response, failures = _strict_json_call(
            gateway, scoped_messages, operation_id=operation_id, max_tokens=16384, temperature=0,
            retry_instruction=retry_instruction, review_checks=scope, calls=calls, record_response=True,
            review_context=scoped_context, budget=budget, clarification=True,
        )
    except (LlmGatewayError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc) not in {"OPERATION_DEADLINE_EXCEEDED", "OPERATION_ATTEMPT_LIMIT"}:
            raise
        batch["clarification"] = {
            "sent": getattr(exc, "sent", {}), "accepted_check_ids": [], "error": "REVIEW_CLARIFICATION_UNAVAILABLE",
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
        }
        return checks, batch
    checks, accepted = review_clarification.apply_clarification(
        checks, corrected, scoped_messages, plan, scope, review_basis=review_basis, reviewer=reviewer,
    )
    batch["parse_failures"].extend(failures)
    batch["clarification"] = {"sent": correction_response.sent, "accepted_check_ids": accepted}
    return checks, batch


def _generation_instructions(snapshot: dict) -> tuple[str, str]:
    design = snapshot.get("scenario_contract")
    if "battery_scenario" in snapshot:
        battery = snapshot["battery_scenario"]
        instruction = battery["instructions"]["generation"]
        if addendum := battery.get("generation_addendum"):
            instruction = f"{instruction}\n\n{addendum}"
        contract = json.dumps(snapshot["as_contract"], ensure_ascii=False)
    elif design:
        instruction = design["candidate_contract"]["instruction"]
        contract = json.dumps(snapshot["as_contract"], ensure_ascii=False)
    else:
        instruction = _frozen_file(snapshot, "generator_prompt").read_text(encoding="utf-8")
        contract = _frozen_file(snapshot, "generation_contract").read_text(encoding="utf-8")
        if "event_material_delivery" in snapshot:
            contract = json.dumps(snapshot["as_contract"], ensure_ascii=False)
    if "project_role" in snapshot:
        addendum = _frozen_file(snapshot, "project_role_prompt").read_text(encoding="utf-8")
        instruction = f"{instruction}\n\n{addendum}"
    return instruction, contract


def _assemble_candidate(snapshot: dict, raw: Any) -> dict:
    proposed, depth = extract_candidate_as(raw)
    condition_changes = []
    if "battery_scenario" in snapshot:
        from Api.m5_battery_contract import bind

        candidate, changes = bind(snapshot, proposed), []
        source = "frozen_input_snapshot.battery_scenario"
    elif "as_contract" in snapshot:
        candidate, changes = passport_generation.bind_event_materials(snapshot, proposed)
        candidate, condition_changes = passport_generation.bind_event_conditions(snapshot, candidate)
        source = "frozen_input_snapshot.case_version.passport"
    else:
        candidate, changes = bind_indicator_target_layers(snapshot, proposed), []
        source = "frozen_input_snapshot.author_as_example"
    provider_checksum, candidate_checksum = checksum(proposed), checksum(candidate)
    return {
        "candidate_as": candidate,
        "candidate_checksum": candidate_checksum,
        "author_content_binding": {
            "source": source,
            "provider_candidate_checksum": provider_checksum,
            "bound_candidate_checksum": candidate_checksum,
            "changed": provider_checksum != candidate_checksum,
            **({"event_material_changes": changes} if changes else {}),
            **({"event_condition_changes": condition_changes} if condition_changes else {}),
        },
        "response_envelope_depth": depth,
        "deterministic_validation": deterministic_checks(snapshot, candidate),
    }


def generate(snapshot: dict[str, Any], gateway: Any) -> dict[str, Any]:
    instruction, contract = _generation_instructions(snapshot)
    if "as_contract" in snapshot:
        payload = passport_generation.provider_basis(snapshot)
    else:
        compiler_profile = (((snapshot.get("refs") or {}).get("package") or {}).get("compiler") or {}).get(
            "source_schema_profile"
        )
        two_layer = compiler_profile == "functional-personalization-indicator-v2"
        required_fields = list(snapshot["author_as_example"].keys())
        if two_layer:
            required_fields.append(INDICATOR_LAYER_FIELD)
        payload = {"profile": snapshot["profile"], "case": snapshot["case"],
                   "author_as_example": snapshot["author_as_example"], "requirements": {
                       "output": "Верни только один JSON-объект полной AS с теми же верхнеуровневыми полями, что у author_as_example.",
                       "required_top_level_fields_exact": required_fields,
                       "omit_empty_required_fields": False,
                       "status": "TEST_DRAFT", "current": False, "synthetic": snapshot["synthetic"],
                       "must_adapt_all_dependent_parts": True, "must_not_create_evidence_or_scores": True,
                       "compact_json": True, "do_not_expand_or_duplicate_author_content": True,
                       **({"indicator_target_layers": {
                           "author_layer": "server binds immutable author source after generation",
                           "adapted_projection_location": "IndicatorObservability",
                           "required_fields_per_adapted_target": list(ADAPTED_TARGET_FIELDS),
                           "author_mapping": {"source_pointer": "/IndicatorObservability/{source_index}",
                                              "source_checksum": "server-bound; provider must not calculate it"},
                           "reference_namespaces": {
                               "material_refs": "Материалы[].MaterialID",
                               "event_refs": "События[].EventID",
                               "character_refs": "Активные персонажи[].CharacterID",
                               "authority_refs": "participant or character:<CharacterID>",
                           },
                           "preserve_author_meaning_observability_and_constraints": True,
                       }} if two_layer else {}),
                       "maximum_output_characters": int(len(canonical(snapshot["author_as_example"])) * 1.35)}}
    messages = [{"role": "system", "content": instruction},
                {"role": "system", "content": "Содержательный контракт:\n" + contract},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    fingerprint = _message_fingerprint(messages)
    input_checksum = fingerprint[0]
    operation_id = f"{snapshot['operation_id']}:generation:{input_checksum[:12]}"
    calls = []
    raw, response, parse_failures = _strict_json_call(
        gateway, messages, operation_id=operation_id, max_tokens=32768, temperature=0.2,
        retry_instruction=_frozen_file(snapshot, "protocol_json_retry").read_text(encoding="utf-8"),
        calls=calls, initial_fingerprint=fingerprint,
    )
    return {**_assemble_candidate(snapshot, raw),
            "provider_operation": {**_trace(response, operation_id=operation_id, kind="generation", input_checksum=input_checksum),
                                   "parse_failures": parse_failures, "calls": calls}}


def test_candidate(snapshot: dict[str, Any], generation: dict[str, Any], gateway: Any, *,
                   review_round: int = 1) -> dict[str, Any]:
    plan = snapshot.get("applicability_plan") or build_applicability_plan(snapshot["case"])
    batch_size = 8
    battery_review = plan["protocol"].get("scope") in BATTERY_REVIEW_SCOPES
    server_bound = plan["protocol"].get("version") in SERVER_BOUND_REVIEW_PACKAGES
    concrete_candidate = (generation["candidate_as"] if battery_review
                          else concrete_adapted_candidate(generation["candidate_as"]))
    layers = ({} if battery_review else generation["candidate_as"].get(INDICATOR_LAYER_FIELD, {}))
    review_basis = {
        "candidate_as": concrete_candidate if isinstance(concrete_candidate, dict) else None,
        "missing_required_paths": generation["deterministic_validation"].get("missing_required_paths", ()),
    }
    protocol_ref = (snapshot.get("refs") or {}).get("protocol_package") or {}
    response_contract = (snapshot.get("refs") or {}).get("review_response")
    instruction = None
    if response_contract is not None:
        instruction = _frozen_file({"refs": response_contract}, "instruction").read_text(encoding="utf-8")
    passport_basis = passport_generation.provider_basis(snapshot) if "as_contract" in snapshot else None
    candidate_binding = passport_basis is not None or protocol_ref.get("version") == "2.0.0"
    candidate_checksum = checksum(concrete_candidate) if candidate_binding else None
    echo_checksum = candidate_binding and not server_bound
    payload_base = {"case": snapshot["case"], "profile": snapshot["profile"],
               "candidate_as": concrete_candidate,
               **({"candidate_checksum": candidate_checksum} if echo_checksum else {}),
               "author_indicator_layer": layers.get("author"),
               "adapted_indicator_layer": layers.get("adapted"),
               "deterministic_validation": generation["deterministic_validation"],
               "protocol_rules": {"evaluate_every_required_check_exactly_once": True,
                 "llm_must_not_change_applicability": True,
                 "candidate_as_is_concrete_adapted_view": True,
                 "author_indicator_layer_is_provenance_not_professional_content": True,
                 "author_only_names_are_not_adapted_defects": True,
                 "never_require_mutating_immutable_author_layer": True,
                 "reference_namespaces_are_closed": {
                     "material_refs": "Материалы[].MaterialID only; hidden fact IDs are forbidden",
                     "event_refs": "События[].EventID only",
                     "character_refs": "Активные персонажи[].CharacterID only",
                 },
                 "hidden_fact_semantics_are_checked_in_conditions_and_events_not_material_refs": True,
                 "missing_required_material_or_condition_is_fail_not_not_applicable": True,
                 "allowed_statuses": ["PASS", "FAIL", "NOT_RUN", "INDETERMINATE", "TECHNICAL_ERROR"],
                 "do_not_return_overall_status": True},
               "required_output": {**({"candidate_checksum": "exact candidate_checksum from input"}
                                     if echo_checksum else {}), "checks": [{
                   "check_id": "exact id from applicability_plan.required_checks",
                   "status": "PASS|FAIL|NOT_RUN|INDETERMINATE|TECHNICAL_ERROR",
                   "evidence_paths": ["JSON path"], "reason": "string",
                   "adversarial_review": {"candidate_conflicts": ["JSON path потенциального противоречия"],
                                          "resolution": "Почему каждый конфликт не нарушает требование; для FAIL — пустая строка допустима"},
                   "findings": [{"code": "string", "severity": "blocking|non_blocking",
                                 "paths": ["JSON path"], "reason": "string",
                                 "requirement_ref": "check_id/source_ref"}],
               }]}}
    if passport_basis is not None:
        payload_base = {
            **passport_basis, "candidate_as": concrete_candidate,
            **({"candidate_checksum": candidate_checksum} if echo_checksum else {}),
            "required_output": payload_base["required_output"],
            "deterministic_validation": generation["deterministic_validation"],
        }
    review_ref = {}
    if battery_review:
        review_ref = {
            "source_ref": plan["case_ref"], "protocol": plan["protocol"],
            "review_package": snapshot["refs"]["protocol_package"],
            **({"response_contract": response_contract} if response_contract is not None else {}),
            "scenario_source": snapshot["refs"]["battery_scenario"], "m2_source": snapshot["refs"]["m2"],
            "candidate_checksum": candidate_checksum,
            "assessment_situation_id": concrete_candidate.get("AssessmentSituationID") if isinstance(concrete_candidate, dict) else None,
            "as_version": concrete_candidate.get("Version") if isinstance(concrete_candidate, dict) else None,
        }
        payload_base.update({key: value for key, value in review_ref.items()
                             if echo_checksum or key != "candidate_checksum"},
                            risk_context=plan["risk_context"], m2_indicator_descriptors=plan["indicator_descriptors"])
        required_check_output = payload_base["required_output"]["checks"][0]
        required_check_output["adversarial_review"]["resolution"] = (
            "Для PASS по обязательному защищённому критерию заполни содержательную строку со ссылками "
            "на материалы и поля из evidence_paths, даже если вывод уже есть в reason. "
            "При пустом candidate_conflicts укажи, какие материалы сопоставил и почему критерий выполнен. "
            "При непустом candidate_conflicts объясни, как разрешён каждый указанный конфликт. "
            "Пустая строка даёт TECHNICAL_ERROR. Для FAIL она допустима."
        )
        required_check_output["findings"][0].update(
            requirement_ref="exact check_id", expected="known requirement, if available",
            actual="observed value, if available",
        )
    if instruction is not None:
        payload_base["required_output"] = review_clarification.response_forms(payload_base["required_output"])
    if server_bound and generation["deterministic_validation"]["status"] != "PASS":
        return {
            "protocol": plan["protocol"], "checks": [], "review_skipped": "INVALID_CANDIDATE_STRUCTURE",
            "aggregation": aggregate(generation["deterministic_validation"], [], scoped_findings=True),
            "candidate_checksum": generation["candidate_checksum"], "reviewed_candidate_checksum": None,
            "review_source": review_ref, "independent_checks": {"tester": [], "challenger": []},
            "provider_operation": {"batches": []}, "challenger_operation": {"batches": []},
        }

    def review_context(reviewer, batch_no, batch_checks):
        if not server_bound:
            return None
        return {
            "operation_id": snapshot["operation_id"], "round": review_round, "reviewer": reviewer,
            "batch_no": batch_no, "candidate_sha256": candidate_checksum, "package": protocol_ref,
            "check_ids": [item["check_id"] for item in batch_checks],
        }

    adaptation_contract = (_frozen_file(snapshot, "indicator_adaptation_contract").read_text(encoding="utf-8")
                           if "indicator_adaptation_contract" in snapshot["refs"] else None)
    response_instructions = [{"role": "system", "content": instruction}] if instruction is not None else []
    tester_operations = []
    tester_raw_checks = []
    required_checks = reviewer_checks(plan, "tester")
    for batch_no, offset in enumerate(range(0, len(required_checks), batch_size), start=1):
        batch_checks = required_checks[offset:offset + batch_size]
        batch_plan = {**plan, "required_checks": batch_checks, "not_applicable_checks": []}
        if battery_review:
            batch_plan.pop("indicator_descriptors")
            batch_plan.pop("risk_context")
        payload = {**payload_base, "applicability_plan": batch_plan}
        context = review_context("tester", batch_no, batch_checks)
        if context is not None:
            payload["review_dispatch"] = {key: context[key] for key in ("operation_id", "round", "reviewer", "batch_no")}
        messages = [{"role": "system", "content": _frozen_file(snapshot, "tester_prompt").read_text(encoding="utf-8")},
                    {"role": "system", "content": _frozen_file(snapshot, "protocol_tester_addendum").read_text(encoding="utf-8")},
                    *([{"role": "system", "content": "Контракт двух слоёв IndicatorTarget:\n" + adaptation_contract}]
                      if adaptation_contract else []),
                    *response_instructions,
                    _review_message(payload, batch_checks, passport=passport_basis is not None)]
        rows, batch = _review_batch(
            gateway, messages, plan=batch_plan, review_basis=review_basis, snapshot=snapshot,
            reviewer="tester", batch_no=batch_no, context=context, review_ref=review_ref,
            candidate_checksum=candidate_checksum, echo_checksum=echo_checksum, instruction=instruction,
        )
        tester_raw_checks.extend(rows)
        tester_operations.append(batch)
    checks = [{**item, "reviewer": "tester", "candidate_checksum": generation["candidate_checksum"]}
              for item in normalize_results(plan, tester_raw_checks, **review_basis)]
    challenge_definitions = reviewer_checks(plan, "challenger")
    challenge_payload = {
        **(passport_basis if passport_basis is not None else {
            "case": snapshot["case"], "author_as_example": snapshot["author_as_example"],
        }),
        "candidate_as": concrete_candidate,
        **({"candidate_checksum": candidate_checksum} if echo_checksum else {}),
        "author_indicator_layer": layers.get("author"),
        "adapted_indicator_layer": layers.get("adapted"),
        "protected_checks": challenge_definitions,
        "required_output": payload_base["required_output"],
        "rules": {
            "purpose": "Ищи опровержение PASS, не подтверждение.",
            "inspect_entire_candidate": True,
            "direct_statement_is_not_uncertain_merely_because_it_has_a_source": True,
            "different_labels_require_different_substance": True,
            "inspect_new_assertions_and_removed_constraints_against_author_example": True,
            "verify_author_layer_unchanged": True,
            "candidate_as_is_concrete_adapted_view": True,
            "source_only_names_are_not_concrete_as_defects": True,
            "author_only_names_are_expected_provenance_and_must_not_be_changed": True,
            "verify_adaptation_preserves_meaning_observability_and_constraints": True,
            "verify_material_event_character_and_authority_mappings": True,
            "reference_namespaces_are_closed": {
                "material_refs": "Материалы[].MaterialID only; never require Fxx hidden fact IDs",
                "event_refs": "События[].EventID only",
                "character_refs": "Активные персонажи[].CharacterID only",
            },
            "hidden_facts_are_verified_semantically_via_conditions_and_events": True,
            "return_each_protected_check_once": True,
        },
    }
    if passport_basis is not None:
        challenge_payload = {
            **passport_basis, "candidate_as": concrete_candidate,
            **({"candidate_checksum": candidate_checksum} if echo_checksum else {}),
            "protected_checks": challenge_definitions, "required_output": payload_base["required_output"],
        }
    if battery_review:
        challenge_payload = {**payload_base, "protected_checks": challenge_definitions}
    challenger_operations = []
    challenger_raw_checks = []
    for batch_no, offset in enumerate(range(0, len(challenge_definitions), batch_size), start=1):
        batch_checks = challenge_definitions[offset:offset + batch_size]
        batch_payload = {**challenge_payload, "protected_checks": batch_checks}
        context = review_context("challenger", batch_no, batch_checks)
        if context is not None:
            batch_payload["review_dispatch"] = {key: context[key] for key in (
                "operation_id", "round", "reviewer", "batch_no",
            )}
        challenge_messages = [
            {"role": "system", "content": _frozen_file(snapshot, "protocol_challenger").read_text(encoding="utf-8")},
            *([{"role": "system", "content": _frozen_file(snapshot, "protocol_tester_addendum").read_text(encoding="utf-8")}]
              if battery_review else []),
            *([{"role": "system", "content": "Контракт двух слоёв IndicatorTarget:\n" + adaptation_contract}]
              if adaptation_contract else []),
            *response_instructions,
            _review_message(batch_payload, batch_checks, passport=passport_basis is not None),
        ]
        rows, batch = _review_batch(
            gateway, challenge_messages, plan={**plan, "required_checks": batch_checks, "not_applicable_checks": []},
            review_basis=review_basis, snapshot=snapshot, reviewer="challenger", batch_no=batch_no,
            context=context, review_ref=review_ref, candidate_checksum=candidate_checksum,
            echo_checksum=echo_checksum, instruction=instruction,
        )
        challenger_raw_checks.extend(rows)
        challenger_operations.append(batch)
    challenge_plan = {**plan, "required_checks": challenge_definitions, "not_applicable_checks": []}
    challenge_checks = [{**item, "reviewer": "challenger", "candidate_checksum": generation["candidate_checksum"]}
                        for item in normalize_results(challenge_plan, challenger_raw_checks, reviewer="challenger", **review_basis)]
    if battery_review:
        for records, batches in ((checks, tester_operations), (challenge_checks, challenger_operations)):
            batch_by_id = {check_id: batch for batch in batches for check_id in batch["required_check_ids"]}
            for record in records:
                batch = batch_by_id[record["check_id"]]
                record.update(review_package=review_ref["review_package"], batch_no=batch["batch_no"],
                              operation_id=batch["operation_id"], as_version=review_ref["as_version"])
    challenge_by_id = {item["check_id"]: item for item in challenge_checks
                       if item.get("status") != "NOT_APPLICABLE"}
    merged_checks = []
    for item in checks:
        challenged = challenge_by_id.get(item["check_id"])
        # Keep a localized Tester defect even when Challenger could not check it.
        if (challenged is not None and item.get("protected") and challenged.get("status") != "PASS"
                and not (item.get("status") == "FAIL" and not item.get("protocol_errors"))):
            merged_checks.append(challenged)
        else:
            merged_checks.append(item)
    # Aggregate both independent records: neither can overwrite the other.
    independent_checks = {"tester": checks, "challenger": challenge_checks}
    aggregation = aggregate_reviews(generation["deterministic_validation"], independent_checks, plan["protocol"])
    tester_input_checksum = checksum([item["input_checksum"] for item in tester_operations])
    challenger_input_checksum = checksum([item["input_checksum"] for item in challenger_operations])
    return {"protocol": plan["protocol"], "checks": merged_checks, "aggregation": aggregation,
            "candidate_checksum": generation["candidate_checksum"],
            "reviewed_candidate_checksum": candidate_checksum,
            **({"review_source": review_ref} if battery_review else {}),
            "independent_checks": independent_checks,
            "provider_operation": {"kind": "independent_tester_v2_batched",
                                   "operation_id": f"{snapshot['operation_id']}:tester:batched",
                                   "input_checksum": tester_input_checksum,
                                   "batch_size": batch_size, "batches": tester_operations},
            "challenger_operation": {"kind": "independent_tester_v2_challenger_batched",
                                     "operation_id": f"{snapshot['operation_id']}:challenger:batched",
                                     "input_checksum": challenger_input_checksum,
                                     "batch_size": batch_size, "batches": challenger_operations}}


def repair_candidate(snapshot: dict[str, Any], generation: dict[str, Any], tested: dict[str, Any],
                     gateway: Any) -> dict[str, Any]:
    """Request one corrected AS and assemble the same server-bound fields as in generation."""
    instruction, contract = _generation_instructions(snapshot)
    battery_review = "review_source" in tested
    if "as_contract" in snapshot:
        repair_instruction = _frozen_file(snapshot, "repair_prompt").read_text(encoding="utf-8")
        repair_prompt_ref = snapshot["refs"]["repair_prompt"]
        blocking = tested["aggregation"]["blocking_failures"]
        if battery_review:
            blocking = [{
                **{key: item[key] for key in ("check_id", "reviewer", "operation_id", "source_ref")},
                "findings": [{key: finding[key] for key in ("code", "paths", "reason", "expected", "actual")
                              if key in finding} for finding in item["findings"]],
            } for item in blocking]
        payload = {
            **passport_generation.provider_basis(snapshot),
            "rejected_candidate_as": generation["candidate_as"],
            "blocking_failures": blocking,
            "deterministic_failures": tested["aggregation"]["deterministic_failures"],
            **({"validation_errors": generation["deterministic_validation"]["errors"]} if not battery_review else {
                "source_ref": tested["review_source"]["source_ref"],
                "rejected_candidate_checksum": generation["candidate_checksum"],
            }),
        }
    else:
        repair_instruction, repair_prompt_ref = _load_repair_instruction(ROOT / snapshot["refs"]["repair_package"]["path"])
        payload = {
            "profile": snapshot["profile"], "case": snapshot["case"],
            "author_as_example": snapshot["author_as_example"],
            "rejected_candidate_as": concrete_adapted_candidate(generation["candidate_as"]),
            "author_indicator_layer": generation["candidate_as"].get(INDICATOR_LAYER_FIELD, {}).get("author"),
            "adapted_indicator_layer": generation["candidate_as"].get(INDICATOR_LAYER_FIELD, {}).get("adapted"),
            "blocking_failures": tested["aggregation"]["blocking_failures"],
            "deterministic_failures": tested["aggregation"]["deterministic_failures"],
            "requirements": {
                "output_contract": "full_as_json",
                "preserve_case_identity_and_indicator_targets": True,
                "fix_every_listed_failure_in_all_dependent_fields": True,
                "do_not_weaken_or_remove_observation_conditions": True,
                "must_not_create_evidence_or_scores": True,
                "indicator_target_layers": {
                    "author_layer": "server binds immutable author source after repair",
                    "adapted_projection_location": "IndicatorObservability",
                    "required_fields_per_adapted_target": list(ADAPTED_TARGET_FIELDS),
                    "author_mapping": {
                        "source_pointer": "/IndicatorObservability/{source_index}",
                        "source_checksum": "server-bound; provider must not calculate it",
                    },
                    "preserve_existing_valid_references": True,
                },
                "status": "TEST_DRAFT", "current": False,
            },
        }
    adaptation_contract = (_frozen_file(snapshot, "indicator_adaptation_contract").read_text(encoding="utf-8")
                           if "indicator_adaptation_contract" in snapshot["refs"] else None)
    messages = [
        {"role": "system", "content": instruction},
        {"role": "system", "content": "Содержательный контракт:\n" + contract},
        {"role": "system", "content": repair_instruction},
        *([{"role": "system", "content": "Контракт двух слоёв IndicatorTarget:\n" + adaptation_contract}]
          if adaptation_contract else []),
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    fingerprint = _message_fingerprint(messages)
    input_checksum = fingerprint[0]
    operation_id = f"{snapshot['operation_id']}:generation:repair:{input_checksum[:12]}"
    calls = []
    raw, response, parse_failures = _strict_json_call(
        gateway, messages, operation_id=operation_id, max_tokens=32768, temperature=0.1,
        retry_instruction=_frozen_file(snapshot, "protocol_json_retry").read_text(encoding="utf-8"),
        calls=calls, initial_fingerprint=fingerprint, record_response=battery_review, allow_invalid_repair=battery_review,
    )
    return {**_assemble_candidate(snapshot, raw),
            **({"invalid_repair_response": True} if battery_review and len(parse_failures) == 2 else {}),
            "provider_operation": {**_trace(response, operation_id=operation_id, kind="generation_repair",
                                              input_checksum=input_checksum),
                                   "prompt_ref": repair_prompt_ref,
                                   "parse_failures": parse_failures, "calls": calls}}


def prepare(snapshot: dict[str, Any], gateway: Any, *, functional_package: Path = PACKAGE,
            runtime_package: Path = RUNTIME_PACKAGE) -> dict[str, Any]:
    provider = (snapshot.get("refs") or {}).get("provider_contract")
    if provider and hasattr(gateway, "model") and hasattr(gateway, "base_url"):
        actual_endpoint = f"{str(getattr(gateway, 'base_url', '')).rstrip('/')}/chat/completions"
        if str(getattr(gateway, "model", "")) != provider["model"] or actual_endpoint != provider["endpoint"]:
            raise ValueError("M5_FUNCTIONAL_PROVIDER_IDENTITY_MISMATCH")
    from Api import preparation_observation as observation
    observation.materials()
    generation = generate(snapshot, gateway)
    observation.progress('checking')
    tested = test_candidate(snapshot, generation, gateway)
    repair = None
    if (not tested["aggregation"]["admitted_for_participant"]
            and (tested["aggregation"]["blocking_failures"]
                 or tested["aggregation"]["deterministic_failures"])):
        observation.materials()
        repaired = repair_candidate(snapshot, generation, tested, gateway)
        repair = {
            "original_candidate_checksum": generation["candidate_checksum"],
            "original_author_content_binding": generation["author_content_binding"],
            "original_deterministic_validation": generation["deterministic_validation"],
            "original_generation_operation": generation["provider_operation"],
            "original_tester": tested,
            "repair_generation_operation": repaired["provider_operation"],
        }
        battery_review = "review_source" in tested
        if battery_review:
            repair["original_candidate_as"] = generation["candidate_as"]
        if repaired.get("invalid_repair_response"):
            repair["outcome"] = "INVALID_REPAIR_RESPONSE"
        elif ((snapshot.get("case_content_contract") or battery_review)
              and repaired["candidate_checksum"] == generation["candidate_checksum"]):
            repair["outcome"] = "UNCHANGED_CANDIDATE"
        else:
            observation.progress('checking')
            generation, tested = repaired, test_candidate(snapshot, repaired, gateway, review_round=2)
            if battery_review:
                repair["outcome"] = tested["aggregation"]["status"]
    compiled_case = None
    execution_rules = None
    if tested["aggregation"]["admitted_for_participant"]:
        if "battery_scenario" in snapshot:
            from Api.m5_battery_contract import compile_candidate

            compiled_case, execution_rules = compile_candidate(
                snapshot, generation["candidate_as"], generation["candidate_checksum"],
            )
        elif "as_contract" in snapshot:
            compiled_case, execution_rules = passport_generation.compile_candidate(
                snapshot, generation["candidate_as"], generation["candidate_checksum"],
            )
        else:
            compiler_profile = ((((snapshot.get("refs") or {}).get("package") or {}).get("compiler") or {})
                                .get("source_schema_profile") or "functional-personalization-indicator-v1")
            compiled_case = compile_case_values(
                case=snapshot["case"], situation=generation["candidate_as"],
                case_source_name=Path(snapshot["refs"]["case"]["path"]).name,
                case_source_checksum=snapshot["refs"]["case"]["sha256"],
                as_source_name=f"generated-{generation['candidate_checksum']}.json",
                as_source_checksum=generation["candidate_checksum"],
                source_schema_profile=compiler_profile,
            )
            package_cases = json.loads((functional_package / "case-package.json").read_text(encoding="utf-8"))["cases"]
            package_version = json.loads((functional_package / "manifest.json").read_text(encoding="utf-8"))["version"]
            runtime_bindings = load_runtime_rule_package(
                runtime_package, package_cases, expected_case_package_version=package_version
            )["bindings"]
            execution_rules = build_execution_rules([compiled_case], runtime_bindings)
    return {"schema_version": 1, "input_snapshot_checksum": checksum(snapshot),
            "candidate_as": generation["candidate_as"], "candidate_checksum": generation["candidate_checksum"],
            "author_content_binding": generation["author_content_binding"],
            "deterministic_validation": generation["deterministic_validation"],
            "generation_operation": generation["provider_operation"], "tester": tested,
            "repair": repair,
            "admitted_for_participant": tested["aggregation"]["admitted_for_participant"],
            "compiled_case": compiled_case, "execution_rules": execution_rules}


def review_dispatches_match(tester: dict, *, candidate_sha256: str, review_round: int,
                            operation_id: str | None = None) -> bool:
    protocol_version = tester.get("protocol", {}).get("version")
    package_version = SERVER_BOUND_REVIEW_PACKAGES.get(protocol_version)
    if package_version is None:
        return True
    package = tester.get("review_source", {}).get("review_package")
    if not isinstance(package, dict) or package.get("version") != package_version:
        return False
    for reviewer, trace_key in (("tester", "provider_operation"), ("challenger", "challenger_operation")):
        batches = tester.get(trace_key, {}).get("batches") or []
        if not batches:
            return False
        for batch in batches:
            calls = batch.get("calls") or []
            if len(calls) not in {1, 2}:
                return False
            dispatch = {
                "operation_id": operation_id or batch["operation_id"].split(":" + reviewer + ":", 1)[0],
                "reviewer": reviewer, "round": review_round, "batch_no": batch["batch_no"],
                "candidate_sha256": candidate_sha256, "package": package,
            }
            check_ids = batch["required_check_ids"]
            request_id = batch["operation_id"]
            clarification = batch.get("clarification")
            sent = batch.get("sent", {}).get("messages")
            if clarification is not None:
                if (len(calls) != 2 or not tester["review_source"].get("response_contract")
                        or batch["input_checksum"] != calls[0].get("input_checksum")
                        or not _review_call_matches(calls[0], sent, dispatch, check_ids, request_id, 1)):
                    return False
                scoped_ids = (calls[1].get("review_dispatch") or {}).get("check_ids")
                if (not isinstance(scoped_ids, list) or not scoped_ids
                        or scoped_ids != [key for key in check_ids if key in scoped_ids]
                        or not _review_call_matches(
                            calls[1], clarification.get("sent", {}).get("messages"), dispatch, scoped_ids,
                            request_id + review_clarification.CLARIFICATION_SUFFIX, 2,
                        )):
                    return False
            elif not _review_call_matches(calls[-1], sent, dispatch, check_ids,
                                          request_id + (":json-retry" if len(calls) == 2 else ""), len(calls)):
                return False
    return True


def _review_call_matches(call: dict, sent: list | None, dispatch: dict, check_ids: list[str],
                         request_id: str, attempt: int) -> bool:
    response = call.get("response_content")
    return (isinstance(sent, list) and isinstance(response, str)
            and call.get("review_binding_matches") is True
            and call.get("response_sha256") == checksum(response.encode("utf-8"))
            and _message_fingerprint(sent)[0] == call.get("input_checksum")
            and call.get("review_dispatch") == {
                **dispatch, "check_ids": check_ids, "request_id": request_id,
                "attempt": attempt, "request_sha256": call["input_checksum"],
            })


def archived_diagnostic_review_matches(refs: dict, protocol: dict) -> bool:
    """The v3 QA hand-off froze the scenario but used the general review format."""
    directory = passport_generation.AS_PACKAGE.with_name("v3")
    _, _, package_refs = passport_generation.read_as_package(directory)
    if any(refs.get(key) != ref for key, ref in package_refs.items()):
        return False
    expected = load_protocol(directory / "tester-protocol.json")
    return protocol == {key: expected[key] for key in ("id", "version", "checksum")}


def frozen_battery_review_plan(source: dict, *, cycle: dict | None = None,
                               case_version: dict | None = None) -> dict:
    """Rebuild applicability for pre-existing traces using only pinned server inputs."""
    from Api import m5_battery_contract, m5_battery_review
    from Api.cycle_execution_manifest import (
        BATTERY_V04_SCENARIO_REFS, M5_BATTERY_REVIEW_PACKAGE, M5_REVIEW_RESPONSE_PACKAGE,
        battery_pilot_review_path,
        battery_scenario_path, resolve_cycle_dependency, resolve_review_response,
    )

    refs = source["refs"]
    package = refs["protocol_package"]
    projected = source["case_version"]
    if cycle is None:
        # Standalone checks of saved traces have the same immutable package references.
        as_path = ROOT / (M5_BATTERY_REVIEW_PACKAGE if package["version"] == "4.0.0"
                          else battery_pilot_review_path(package))
        scenario_ref = refs["battery_scenario"]
        scenario_path = ROOT / battery_scenario_path(
            refs["package"]["version"],
            scenario_ref if scenario_ref["version"] in BATTERY_V04_SCENARIO_REFS
            or refs["package"]["version"].removesuffix(m5_battery_contract.PILOT_CASE_SUFFIX) == "0.9" else None,
        )
        m2_path = passport_generation.M2
        pilot = projected["version"].endswith(m5_battery_contract.PILOT_CASE_SUFFIX)
        response_path = ROOT / M5_REVIEW_RESPONSE_PACKAGE if "review_response" in refs else None
    else:
        as_path = resolve_cycle_dependency(cycle, "m5_functional_as")
        scenario_path = resolve_cycle_dependency(cycle, "m5_battery_scenario")
        m2_path = resolve_cycle_dependency(cycle, "m2_methodology") / "methodology.json"
        response_path = resolve_review_response(cycle)
        pilot = cycle["catalog_ref_json"].get("battery_pilot") is True
        if case_version != projected or runtime_checksum(case_version) != refs["case"]["case_version_checksum"]:
            raise ValueError("PILOT_PLAN_REVIEW_CASE_MISMATCH")

    _, _, package_refs = passport_generation.read_as_package(as_path)
    if any(refs.get(key) != value for key, value in package_refs.items()):
        raise ValueError("PILOT_PLAN_REVIEW_PROTOCOL_MISMATCH")
    protocol = load_protocol(as_path / "tester-protocol.json")
    if (protocol.get("scope") not in BATTERY_REVIEW_SCOPES
            or SERVER_BOUND_REVIEW_PACKAGES.get(protocol["version"], "4.0.0") != package["version"]):
        raise ValueError("PILOT_PLAN_REVIEW_PROTOCOL_MISMATCH")
    scenario = m5_battery_contract.load_scenario(projected, scenario_path, pilot=pilot)
    m2, m2_ref = passport_generation.load_m2(m2_path, passport_generation.SOURCE_MANIFEST)
    if scenario["ref"] != refs["battery_scenario"] or m2_ref != refs["m2"]:
        raise ValueError("PILOT_PLAN_REVIEW_SOURCE_MISMATCH")
    response_contract = review_clarification.load_response_contract(response_path) if response_path else None
    if refs.get("review_response") != response_contract or (response_contract and package["version"] != "7.0.0"):
        raise ValueError("PILOT_PLAN_REVIEW_RESPONSE_CONTRACT_MISMATCH")
    plan = m5_battery_review.build_plan(
        {**source, "battery_scenario": scenario, "battery_pilot": pilot},
        protocol, as_path / "case-content-contract.json", m2,
    )
    if response_contract:
        plan["review_instruction"] = _frozen_file({"refs": response_contract}, "instruction").read_text(encoding="utf-8")
    return plan


def bound_review_results_match(plan: dict, definitions: list[dict], records: list[dict],
                               batches: list[dict], *, reviewer: str, candidate: dict,
                               candidate_sha256: str, package: dict, deterministic: dict) -> bool:
    """Check that normalized role results belong to the terminal candidate and receipts."""
    by_id = {item["check_id"]: item for item in definitions}
    record_by_id = {item["check_id"]: item for item in records}
    if len(records) != len(by_id) or record_by_id.keys() != by_id.keys():
        return False
    review_basis = {"candidate_as": candidate, "missing_required_paths": deterministic.get("missing_required_paths", ())}
    raw_checks = []
    for batch in batches:
        for check_id in batch["required_check_ids"]:
            result = record_by_id[check_id]
            if (result.get("status") == "NOT_APPLICABLE"
                    or any(result.get(key) != value for key, value in by_id[check_id].items())
                    or any(result.get(key) != value for key, value in {
                        "reviewer": reviewer, "candidate_checksum": candidate_sha256,
                        "as_version": candidate["Version"], "review_package": package,
                        "operation_id": batch["operation_id"], "batch_no": batch["batch_no"],
                    }.items())):
                return False
        if plan["protocol"]["version"] in SERVER_BOUND_REVIEW_PACKAGES:
            batch_definitions = [by_id[key] for key in batch["required_check_ids"]]
            calls = batch["calls"]
            clarification = batch.get("clarification")
            try:
                instruction = plan.get("review_instruction")
                initial_messages = batch["sent"]["messages"]
                if instruction is not None and {"role": "system", "content": instruction} not in initial_messages:
                    return False
                raw = json.loads(calls[0 if clarification else -1]["response_content"])
                rows = _bound_batch_checks(raw, batch_definitions)
                if clarification:
                    batch_plan = {**plan, "required_checks": batch_definitions, "not_applicable_checks": []}
                    messages, scope = review_clarification.clarification_messages(
                        batch_plan, rows, call=calls[0], initial_messages=initial_messages,
                        review_basis=review_basis, instruction=plan["review_instruction"],
                    )
                    scope_ids = [item["check_id"] for item in scope]
                    if (not scope_ids or scope_ids != calls[1]["review_dispatch"]["check_ids"]
                            or messages != clarification["sent"]["messages"]):
                        return False
                    rows, accepted = review_clarification.apply_clarification(
                        rows, json.loads(calls[1]["response_content"]), messages, batch_plan, scope,
                        review_basis=review_basis, reviewer=reviewer,
                    )
                    if accepted != scope_ids or accepted != clarification.get("accepted_check_ids"):
                        return False
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                return False
            raw_checks.extend(rows)

    if plan["protocol"]["version"] not in SERVER_BOUND_REVIEW_PACKAGES:
        return True
    normalized = normalize_results(
        {**plan, "required_checks": definitions, "not_applicable_checks": []}, raw_checks,
        **review_basis, reviewer=reviewer,
    )
    receipt_fields = {"reviewer", "candidate_checksum", "as_version", "review_package", "operation_id", "batch_no"}
    return all(item == {key: value for key, value in record_by_id[item["check_id"]].items() if key not in receipt_fields}
               for item in normalized)


def build_persistence_trace(snapshot: dict[str, Any], prepared: dict[str, Any]) -> dict[str, Any]:
    """Build the immutable PM-03 -> PM-04 hand-off kept in the AS snapshot."""
    if checksum(snapshot) != prepared.get("input_snapshot_checksum"):
        raise ValueError("M5_FUNCTIONAL_INPUT_SNAPSHOT_MISMATCH")
    candidate = prepared.get("candidate_as")
    if not isinstance(candidate, dict) or checksum(candidate) != prepared.get("candidate_checksum"):
        raise ValueError("M5_FUNCTIONAL_CANDIDATE_SNAPSHOT_MISMATCH")
    tester = prepared.get("tester") or {}
    if "as_contract" in snapshot and (
        tester.get("candidate_checksum") != prepared["candidate_checksum"]
        or tester.get("reviewed_candidate_checksum") != prepared["candidate_checksum"]
    ):
        raise ValueError("M5_FUNCTIONAL_REVIEWED_CANDIDATE_MISMATCH")
    if not isinstance(tester.get("provider_operation", {}).get("input_checksum"), str):
        raise ValueError("M5_FUNCTIONAL_TESTER_INPUT_TRACE_REQUIRED")
    if (snapshot.get("applicability_plan", {}).get("protocol", {}).get("version") in SERVER_BOUND_REVIEW_PACKAGES
            and tester.get("protocol") != snapshot["applicability_plan"]["protocol"]):
        raise ValueError("M5_FUNCTIONAL_REVIEW_PROTOCOL_MISMATCH")
    if not review_dispatches_match(tester, candidate_sha256=prepared["candidate_checksum"],
                                   review_round=2 if prepared.get("repair") else 1,
                                   operation_id=snapshot["operation_id"]):
        raise ValueError("M5_FUNCTIONAL_REVIEW_DISPATCH_MISMATCH")
    layers = candidate.get(INDICATOR_LAYER_FIELD)
    trace = {
        "schema_version": 3 if isinstance(layers, dict) else 2,
        "input_snapshot_checksum": prepared["input_snapshot_checksum"],
        "source_snapshot": {
            "case": snapshot["case"],
            **({"case_version": snapshot["case_version"]} if "as_contract" in snapshot
               else {"author_as_example": snapshot["author_as_example"]}),
            **({"event_material_delivery": snapshot["event_material_delivery"]}
               if "event_material_delivery" in snapshot else {}),
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
    if isinstance(layers, dict):
        trace["indicator_target_layers"] = layers
        trace["indicator_target_layers_checksum"] = checksum(layers)
    return trace
