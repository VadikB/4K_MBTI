"""Применимость и программная агрегация tester protocol v2 для PERS."""
from __future__ import annotations

from ast import literal_eval
from collections.abc import Collection, Iterable
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/evc/protocols/m5-functional-personalization-tester-v2.json"
RESULT_STATUSES = {"PASS", "FAIL", "NOT_APPLICABLE", "NOT_RUN", "INDETERMINATE", "TECHNICAL_ERROR"}
PROTECTED_CATEGORIES = {"invariant", "indicator_observability", "authority", "confidentiality", "scenario_executability", "target_integrity"}
PATH_STEP = re.compile(r"""\.([^.[\]]+)|\[("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\[\]'"]+)\]""")
CANDIDATE_COLLECTION_IDS = {
    "Материалы": "MaterialID", "События": "EventID", "Активные персонажи": "CharacterID",
    "IndicatorObservability": "IndicatorID",
}


def checksum(value: Any) -> str:
    data = value if isinstance(value, bytes) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(data).hexdigest()


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if (value.get("schema_version"), value.get("id"), value.get("status")) != (
        2, "m5-functional-personalization-tester", "draft"
    ) or value.get("version") not in {"2.0.0", "2.1.0"}:
        raise ValueError("M5_FUNCTIONAL_TESTER_PROTOCOL_INVALID")
    if set(value.get("result_statuses", [])) != RESULT_STATUSES:
        raise ValueError("M5_FUNCTIONAL_TESTER_PROTOCOL_INVALID")
    content_checks = value.get("case_content_checks")
    if value["version"] == "2.1.0" and not (isinstance(content_checks, dict) and content_checks):
        raise ValueError("M5_FUNCTIONAL_TESTER_CASE_CONTENT_CHECKS_REQUIRED")
    value["checksum"] = hashlib.sha256(raw).hexdigest()
    return value


def build_applicability_plan(case: dict[str, Any], protocol: dict[str, Any] | None = None, *,
                             case_content_contract: dict[str, Any] | None = None,
                             scenario_qa: bool = False) -> dict[str, Any]:
    protocol = deepcopy(protocol or load_protocol())
    passport = case.get("Паспорт")
    if not isinstance(passport, dict):
        raise ValueError("M5_FUNCTIONAL_CASE_PASSPORT_REQUIRED")
    case_id = str(case.get("CaseID") or "")
    version = str(case.get("Version") or "")
    invariants = passport.get("16 Инвариантное ядро")
    indicators = passport.get("22 IndicatorIDs", {}).get("Проектные условия")
    personalization = passport.get("18 Правила персонализации и ролевой адаптации")
    prohibitions = personalization.get("Критические запреты") if isinstance(personalization, dict) else None
    if scenario_qa:
        # Temporary technical protocol for 02. The passport-specific review
        # plan for v1.2 is owned by 03; v1.1 case-specific checks stay pinned.
        prohibitions = []
        protocol["conditional_checks"] = []
        protocol["case_content_checks"] = {}
    if (not case_id or not version or not isinstance(invariants, list)
            or not isinstance(indicators, list) or not isinstance(prohibitions, list)
            or (not scenario_qa and not prohibitions)
            or (scenario_qa and not isinstance(personalization, dict))
            or not all(isinstance(item, str) and item.strip() for item in prohibitions)):
        raise ValueError("M5_FUNCTIONAL_CASE_CHECK_SOURCES_REQUIRED")
    checks = [deepcopy(item) for item in protocol["common_checks"]]
    if scenario_qa:
        checks.append({
            "check_id": "passport:adaptation", "category": "authority", "mandatory": True, "protected": True,
            "requirement": personalization,
            "source_ref": {"case_id": case_id, "case_version": version, "field": "18"},
        })
    checks.extend({
        "check_id": "invariant:" + item["InvariantID"], "category": "invariant",
        "mandatory": True, "protected": True, "requirement": item["Условие"],
        "source_ref": {"case_id": case_id, "case_version": version, "field": "16", "invariant_id": item["InvariantID"]},
    } for item in invariants)
    checks.extend({
        "check_id": "indicator:" + item["IndicatorID"], "category": "indicator_observability",
        "mandatory": True, "protected": True,
        "requirement": {
            "functional_conditions": item.get("Функциональные условия", []),
            "designed_condition": item.get("Проектное условие", []),
            "materials": item.get("Материалы и факты по функции", []),
            "opportunity": item.get("Условие возникновения"),
            **({"locations": item["Место в сценарии"], "observable_form": item["Доступная форма проявления"],
                "validity_risk": item["Риск потери"]} if scenario_qa else {}),
        },
        "source_ref": {"case_id": case_id, "case_version": version, "field": "22", "indicator_id": item["IndicatorID"]},
    } for item in indicators)
    checks.extend({
        "check_id": f"critical_prohibition:{index:02d}",
        "category": "invariant", "mandatory": True, "protected": True,
        "requirement": "AS не реализует критически запрещённую конструкцию: " + prohibition,
        "source_ref": {"case_id": case_id, "case_version": version, "field": "18",
                       "critical_prohibition_index": index},
    } for index, prohibition in enumerate(prohibitions, start=1))
    not_applicable = []
    for item in protocol["conditional_checks"]:
        if case_id in item["applicable_case_ids"]:
            checks.append(deepcopy(item))
        else:
            not_applicable.append({
                **deepcopy(item), "mandatory": False, "status": "NOT_APPLICABLE",
                "basis": f"Протокол {protocol['version']}: проверка применима только к {item['applicable_case_ids']}; текущий Case={case_id}.",
            })
    identifiers = [item["check_id"] for item in checks]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("M5_FUNCTIONAL_TESTER_CHECK_ID_CONFLICT")
    content_contract = case_content_contract or {}
    requirements = content_contract.get("requirements", {})
    evidence_sections = content_contract.get("finding_evidence_sections", {})
    content_check_ids = protocol.get("case_content_checks", {}).get(case_id, [])
    protected_ids = {item["check_id"] for item in checks if item.get("mandatory") and item.get("protected")}
    if set(content_check_ids) != set(requirements) or not set(requirements) <= protected_ids:
        raise ValueError("M5_FUNCTIONAL_TESTER_CASE_CONTENT_CHECKS_MISMATCH")
    for item in checks:
        if item["check_id"] in requirements:
            item["requirement"] = {"passport_or_protocol": item["requirement"],
                                   "case_content": requirements[item["check_id"]],
                                   "finding_evidence_sections": evidence_sections[item["check_id"]]}
    return {
        "protocol": {"id": protocol["id"], "version": protocol["version"], "checksum": protocol["checksum"]},
        "case_ref": {"case_id": case_id, "case_version": version, "checksum": checksum(case)},
        "required_checks": checks,
        "not_applicable_checks": not_applicable,
    }


def _candidate_path_parts(path: str) -> list[str] | None:
    """Accept slash pointers and the dotted/bracket addresses used by reviewers."""
    path = path.strip()
    if path.startswith(("/", "candidate_as/")):
        if re.search(r"~(?![01])", path):
            return None
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path.removeprefix("/").split("/")]
    else:
        remaining = path.removeprefix("$")
        if not remaining.startswith((".", "[")):
            remaining = "." + remaining
        parts = []
        offset = 0
        while offset < len(remaining):
            match = PATH_STEP.match(remaining, offset)
            if match is None:
                return None
            key, selector = match.groups()
            if selector is not None:
                key = selector.strip()
                if key.startswith(('"', "'")):
                    try:
                        key = literal_eval(key)
                    except (SyntaxError, ValueError):
                        return None
            parts.append(key)
            offset = match.end()
    return parts[1:] if parts[:1] == ["candidate_as"] else parts


def _locate_candidate_path(candidate: dict, path: str, *,
                           allow_missing_parent: bool = False) -> tuple[tuple[str, ...], bool] | None:
    """Normalize ID selectors to indexes, reporting the first absent element when requested."""
    parts = _candidate_path_parts(path)
    if parts is None:
        return None
    node = candidate
    address = []
    for depth, part in enumerate(parts):
        if isinstance(node, dict):
            key = part
            exists = key in node
        elif isinstance(node, list):
            if part.isascii() and part.isdigit() and len(part) <= len(str(len(node))):
                key = int(part)
                exists = key < len(node)
            else:
                id_key = CANDIDATE_COLLECTION_IDS.get(address[-1])
                matches = [index for index, row in enumerate(node)
                           if id_key is not None and isinstance(row, dict) and row.get(id_key) == part]
                if len(matches) > 1:
                    return None
                key = matches[0] if matches else part
                exists = bool(matches)
        else:
            return None
        address.append(str(key))
        if not exists:
            return (tuple(address), False) if allow_missing_parent or depth == len(parts) - 1 else None
        node = node[key]
    return tuple(address), True


def _supports_finding(locations: list[tuple[str, ...]], sections: set[tuple[str, ...]],
                      missing_containers: set[tuple[str, ...]]) -> bool:
    for address in locations:
        if address in missing_containers:
            return True
        if len(address) == 3 and CANDIDATE_COLLECTION_IDS.get(address[0]) == address[2]:
            continue
        if any(address[:len(section)] == section for section in sections):
            return True
    return False


def finding_errors(item: dict[str, Any], *, candidate_as: dict | None = None,
                   missing_paths: Collection[tuple[str, ...]] = (),
                   evidence_sections: Collection[str] = ()) -> list[dict[str, Any]]:
    """Validate evidence before it can be interpreted as a candidate defect."""
    findings = item.get("findings", [])
    errors = []
    def error(code: str, path: str, **basis) -> None:
        errors.append({"error_class": "verification_protocol", "code": code,
                       "check_id": item.get("check_id"), "path": path, **basis})
    if not isinstance(findings, list):
        error("FINDINGS_NOT_A_LIST", "findings")
        return errors
    if item.get("status") == "FAIL" and not findings:
        error("FAIL_WITHOUT_BASIS", "findings")
    if item.get("status") != "FAIL" and findings:
        error("STATUS_FINDINGS_CONFLICT", "findings")
    top_level_field_missing = any(len(path) == 1 for path in missing_paths)
    sections = set()
    if candidate_as is not None and findings:
        for section in evidence_sections:
            located = _locate_candidate_path(candidate_as, section, allow_missing_parent=True)
            if located is not None and (located[1] or located[0] in missing_paths):
                sections.add(located[0])
    missing_containers = {path[:-1] for path in missing_paths
                          if any(path[:len(section)] == section for section in sections)}
    for index, finding in enumerate(findings):
        path = f"findings/{index}"
        if not isinstance(finding, dict):
            error("FINDING_NOT_AN_OBJECT", path)
            continue
        for field in ("code", "reason", "requirement_ref"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                error("FINDING_BASIS_REQUIRED", f"{path}/{field}")
        requirement_ref = finding.get("requirement_ref")
        if (candidate_as is not None and isinstance(requirement_ref, str) and requirement_ref.strip()
                and requirement_ref != item.get("check_id")):
            error("FINDING_REQUIREMENT_REF_MISMATCH", f"{path}/requirement_ref",
                  actual=requirement_ref, expected=item["check_id"])
        if not isinstance(finding.get("severity"), str) or finding["severity"] not in {"blocking", "non_blocking"}:
            error("UNKNOWN_FINDING_SEVERITY", f"{path}/severity")
        paths = finding.get("paths")
        if not isinstance(paths, list) or not paths or any(
                not isinstance(value, str) or not value.strip() for value in paths):
            error("FINDING_LOCATION_REQUIRED", f"{path}/paths")
        elif candidate_as is not None:
            locations = []
            for path_index, value in enumerate(paths):
                located = _locate_candidate_path(candidate_as, value)
                if located is not None:
                    address, exists = located
                    if (exists and (address or top_level_field_missing)) or address in missing_paths:
                        locations.append(address)
                        continue
                error("FINDING_PATH_UNRESOLVABLE", f"{path}/paths/{path_index}", actual=value)
            if (evidence_sections and len(locations) == len(paths)
                    and not _supports_finding(locations, sections, missing_containers)):
                error("FINDING_EVIDENCE_UNRELATED", f"{path}/paths", actual=paths, expected=list(evidence_sections))
    return errors


def normalize_results(plan: dict[str, Any], raw_checks: Any, *, candidate_as: dict | None = None,
                      missing_required_paths: Iterable[str] = ()) -> list[dict[str, Any]]:
    provided = {}
    duplicates = set()
    if isinstance(raw_checks, list):
        for item in raw_checks:
            if not isinstance(item, dict) or not isinstance(item.get("check_id"), str):
                continue
            check_id = item["check_id"]
            if check_id in provided:
                duplicates.add(check_id)
            provided[check_id] = item
    missing_paths = set()
    if candidate_as is not None:
        for path in missing_required_paths:
            located = _locate_candidate_path(candidate_as, path)
            if located is not None and not located[1]:
                missing_paths.add(located[0])
    normalized = []
    for definition in plan["required_checks"]:
        item = deepcopy(provided.get(definition["check_id"], {}))
        status = item.get("status")
        reason = str(item.get("reason") or "").strip()
        if definition["check_id"] in duplicates:
            status, reason = "TECHNICAL_ERROR", "Tester вернул повторяющийся check_id."
        elif not isinstance(status, str) or status not in RESULT_STATUSES:
            status, reason = "NOT_RUN", "Tester не вернул обязательный результат."
        elif status == "NOT_APPLICABLE":
            status, reason = "TECHNICAL_ERROR", "LLM не может исключить проверку, которую план применимости пометил обязательной."
        findings = item.get("findings") if isinstance(item.get("findings"), list) else []
        requirement = definition.get("requirement")
        localized = isinstance(requirement, dict) and "case_content" in requirement
        protocol_errors = finding_errors(
            item, candidate_as=candidate_as if localized else None, missing_paths=missing_paths,
            evidence_sections=requirement.get("finding_evidence_sections", ()) if localized else (),
        )
        if localized and candidate_as is None and findings:
            protocol_errors.append({"error_class": "verification_protocol", "code": "FINDING_CANDIDATE_REQUIRED",
                                    "check_id": definition["check_id"], "path": "candidate_as"})
        if protocol_errors:
            status, reason = "TECHNICAL_ERROR", "Ответ проверки содержит противоречивую или нелокализованную находку."
        protected = bool(definition.get("protected") or definition.get("category") in PROTECTED_CATEGORIES)
        adversarial = item.get("adversarial_review") if isinstance(item.get("adversarial_review"), dict) else None
        if status == "PASS" and definition.get("mandatory") and protected:
            if adversarial is None:
                status, reason = "TECHNICAL_ERROR", "PASS защищённой проверки без adversarial review не допускается."
            elif (not isinstance(adversarial.get("candidate_conflicts"), list)
                  or not str(adversarial.get("resolution") or "").strip()):
                status, reason = "TECHNICAL_ERROR", "PASS защищённой проверки с неполным adversarial review не допускается."
        normalized.append({
            **deepcopy(definition), "status": status, "reason": reason,
            "evidence_paths": item.get("evidence_paths") if isinstance(item.get("evidence_paths"), list) else [],
            "findings": [finding for finding in findings if isinstance(finding, dict)],
            "adversarial_review": adversarial,
            "protocol_errors": protocol_errors or ([{
                "error_class": "verification_protocol", "code": item.get("protocol_error_code") or "REQUIRED_CHECK_" + status,
                "check_id": definition["check_id"], "path": "checks/" + definition["check_id"],
                "reason": reason,
            }] if status in {"NOT_RUN", "INDETERMINATE", "TECHNICAL_ERROR"} else []),
        })
    normalized.extend(deepcopy(plan["not_applicable_checks"]))
    return normalized


def aggregate(deterministic_validation: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    deterministic_checks = deterministic_validation.get("checks")
    deterministic_protocol_errors = []
    if not isinstance(deterministic_checks, list) or not deterministic_checks:
        deterministic_protocol_errors.append({
            "code": "DETERMINISTIC_PROTOCOL_EMPTY",
            "reason": "Обязательный детерминированный протокол отсутствует или пуст.",
        })
        deterministic_checks = []
    deterministic_failures = [item for item in deterministic_checks if item.get("result") != "PASS"]
    if deterministic_validation.get("status") == "FAIL" and not deterministic_failures:
        deterministic_failures.append({
            "code": "DETERMINISTIC_STATUS_FAIL",
            "result": "FAIL",
            "reason": "Детерминированная валидация объявила FAIL без локализованной проверки.",
        })
    blocking_failures, incomplete, review, warnings = [], [], [], []
    for item in checks:
        status = item.get("status")
        if status == "NOT_APPLICABLE":
            if item.get("mandatory") or not str(item.get("basis") or "").strip():
                incomplete.append(item)
            continue
        errors = item.get("protocol_errors") or finding_errors(item)
        if errors:
            incomplete.append({**item, "protocol_errors": errors})
            continue
        findings = item.get("findings") or []
        severities = {finding.get("severity") for finding in findings}
        if severities - {"blocking", "non_blocking"}:
            incomplete.append({**item, "aggregation_error": "UNKNOWN_FINDING_SEVERITY"})
            continue
        has_blocking = "blocking" in severities
        if has_blocking:
            blocking_failures.append(item)
            continue
        if item.get("mandatory") and status in {"NOT_RUN", "INDETERMINATE", "TECHNICAL_ERROR"}:
            incomplete.append(item)
            continue
        if status != "FAIL":
            continue
        protected = bool(item.get("protected") or item.get("category") in PROTECTED_CATEGORIES)
        if protected:
            review.append(item)
        else:
            warnings.append(item)
    if deterministic_failures or blocking_failures:
        status = "FAIL"
    elif deterministic_protocol_errors or incomplete:
        status = "INCOMPLETE"
    elif review:
        status = "REVIEW_REQUIRED"
    elif warnings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    return {
        "status": status,
        "admitted_for_participant": status in {"PASS", "PASS_WITH_WARNINGS"},
        "deterministic_failures": deterministic_failures,
        "deterministic_protocol_errors": deterministic_protocol_errors,
        "blocking_failures": blocking_failures,
        "incomplete_checks": incomplete,
        "verification_errors": [{**error, **{key: item[key] for key in ("reviewer", "candidate_checksum") if key in item}}
                                for item in incomplete for error in item.get("protocol_errors", [])],
        "review_required": review,
        "warnings": warnings,
    }
