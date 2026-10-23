"""Применимость и программная агрегация tester protocol v2 для PERS."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "docs/evc/protocols/m5-functional-personalization-tester-v2.json"
RESULT_STATUSES = {"PASS", "FAIL", "NOT_APPLICABLE", "NOT_RUN", "INDETERMINATE", "TECHNICAL_ERROR"}
PROTECTED_CATEGORIES = {"invariant", "indicator_observability", "authority", "confidentiality", "scenario_executability", "target_integrity"}


def checksum(value: Any) -> str:
    data = value if isinstance(value, bytes) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(data).hexdigest()


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if (value.get("schema_version"), value.get("id"), value.get("version"), value.get("status")) != (
        2, "m5-functional-personalization-tester", "2.0.0", "draft"
    ):
        raise ValueError("M5_FUNCTIONAL_TESTER_PROTOCOL_INVALID")
    if set(value.get("result_statuses", [])) != RESULT_STATUSES:
        raise ValueError("M5_FUNCTIONAL_TESTER_PROTOCOL_INVALID")
    value["checksum"] = hashlib.sha256(raw).hexdigest()
    return value


def build_applicability_plan(case: dict[str, Any], protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    protocol = deepcopy(protocol or load_protocol())
    passport = case.get("Паспорт")
    if not isinstance(passport, dict):
        raise ValueError("M5_FUNCTIONAL_CASE_PASSPORT_REQUIRED")
    case_id = str(case.get("CaseID") or "")
    version = str(case.get("Version") or "")
    invariants = passport.get("16 Инвариантное ядро")
    indicators = passport.get("22 IndicatorIDs", {}).get("Проектные условия")
    if not case_id or not version or not isinstance(invariants, list) or not isinstance(indicators, list):
        raise ValueError("M5_FUNCTIONAL_CASE_CHECK_SOURCES_REQUIRED")
    checks = [deepcopy(item) for item in protocol["common_checks"]]
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
        },
        "source_ref": {"case_id": case_id, "case_version": version, "field": "22", "indicator_id": item["IndicatorID"]},
    } for item in indicators)
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
    return {
        "protocol": {"id": protocol["id"], "version": protocol["version"], "checksum": protocol["checksum"]},
        "case_ref": {"case_id": case_id, "case_version": version, "checksum": checksum(case)},
        "required_checks": checks,
        "not_applicable_checks": not_applicable,
    }


def normalize_results(plan: dict[str, Any], raw_checks: Any) -> list[dict[str, Any]]:
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
    normalized = []
    for definition in plan["required_checks"]:
        item = deepcopy(provided.get(definition["check_id"], {}))
        status = item.get("status")
        reason = str(item.get("reason") or "").strip()
        if definition["check_id"] in duplicates:
            status, reason = "TECHNICAL_ERROR", "Tester вернул повторяющийся check_id."
        elif status not in RESULT_STATUSES:
            status, reason = "NOT_RUN", "Tester не вернул обязательный результат."
        elif status == "NOT_APPLICABLE":
            status, reason = "TECHNICAL_ERROR", "LLM не может исключить проверку, которую план применимости пометил обязательной."
        findings = item.get("findings") if isinstance(item.get("findings"), list) else []
        if status == "FAIL" and not findings:
            status, reason = "TECHNICAL_ERROR", "FAIL без локализованной находки и серьёзности не может быть агрегирован."
        protected = bool(definition.get("protected") or definition.get("category") in PROTECTED_CATEGORIES)
        adversarial = item.get("adversarial_review") if isinstance(item.get("adversarial_review"), dict) else None
        if status == "PASS" and definition.get("mandatory") and protected and (
            adversarial is None
            or not isinstance(adversarial.get("candidate_conflicts"), list)
            or not str(adversarial.get("resolution") or "").strip()
        ):
            status, reason = "TECHNICAL_ERROR", "PASS защищённой проверки без adversarial review не допускается."
        normalized.append({
            **deepcopy(definition), "status": status, "reason": reason,
            "evidence_paths": item.get("evidence_paths") if isinstance(item.get("evidence_paths"), list) else [],
            "findings": [finding for finding in findings if isinstance(finding, dict)],
            "adversarial_review": adversarial,
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
        "review_required": review,
        "warnings": warnings,
    }
