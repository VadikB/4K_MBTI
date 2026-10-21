"""Read-only UX-CMP01 projection for two immutable assessee reports."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


CONTRACT_VERSION = "m8-report-comparison/1.0.0"
REASON_LABELS = {
    "different_role": "Роли в оценках различаются.",
    "role_snapshot_missing": "Не сохранено достаточное подтверждение роли.",
    "m2_composition_not_confirmed": "Совпадение состава навыков не подтверждено.",
    "m2_sources_not_confirmed": "Совпадение версий методологии не подтверждено.",
    "m6_rules_not_confirmed": "Совпадение правил расчёта не подтверждено.",
    "assessment_context_not_confirmed": "Сопоставимость условий оценки не подтверждена.",
    "assessment_conditions_not_confirmed": "Сопоставимость бюджета, календарного окна и правил возврата не подтверждена.",
    "role_requirements_not_confirmed": "Сопоставимость требований роли не подтверждена.",
    "partial_cycle": "Одна из оценок завершена не полностью.",
    "full_score_required": "Для одного из срезов нет полного результата по навыку.",
    "numeric_score_missing": "В одном из срезов нет числового результата.",
    "skill_definition_not_confirmed": "Совпадение определения навыка не подтверждено.",
    "skill_absent_in_previous_cycle": "В предыдущей оценке навык отсутствует.",
}


def _score(skill: dict[str, Any]) -> Decimal | None:
    score = skill.get("score")
    if not isinstance(score, dict) or score.get("value") is None:
        return None
    return Decimal(str(score["value"]))


def _same(left: Any, right: Any) -> bool:
    return left is not None and right is not None and left == right


def _skill_definition(skill: dict[str, Any]) -> dict[str, Any]:
    return {key: skill.get(key) for key in (
        "skill_id", "skill_code", "skill_name", "skill_description",
        "competency_id", "components", "indicators",
    )}


def _complete_comparison_evidence(value: dict[str, Any]) -> bool:
    semantic = value.get("semantic_composition") or {}
    conditions = value.get("assessment_conditions") or {}
    return (
        value.get("contract_version") == "m8-comparison-evidence/1.0.0"
        and bool(semantic.get("full_target_set_checksum"))
        and type(conditions.get("time_budget_seconds")) is int
        and conditions["time_budget_seconds"] > 0
        and type(conditions.get("calendar_window_seconds")) is int
        and conditions["calendar_window_seconds"] > 0
        and bool(conditions.get("return_policy_checksum"))
    )


def _global_evidence(current: dict[str, Any], previous: dict[str, Any]) -> tuple[str | None, str | None]:
    if not _same(current.get("role_ref"), previous.get("role_ref")):
        if current.get("role_ref") is not None and previous.get("role_ref") is not None:
            return "not_allowed", "different_role"
        return "not_confirmed", "role_snapshot_missing"
    current_provenance = current.get("provenance") or {}
    previous_provenance = previous.get("provenance") or {}
    evidence = current_provenance.get("comparison_evidence") or {}
    previous_evidence = previous_provenance.get("comparison_evidence") or {}
    if not _complete_comparison_evidence(evidence) or not _complete_comparison_evidence(previous_evidence):
        return "not_confirmed", "assessment_conditions_not_confirmed"
    if not _same(evidence.get("semantic_composition"), previous_evidence.get("semantic_composition")):
        return "not_confirmed", "m2_composition_not_confirmed"
    if not _same(evidence.get("assessment_conditions"), previous_evidence.get("assessment_conditions")):
        return "not_confirmed", "assessment_conditions_not_confirmed"
    for key, reason in (
        ("sources", "m2_sources_not_confirmed"),
        ("algorithm", "m6_rules_not_confirmed"),
    ):
        if not _same(current_provenance.get(key), previous_provenance.get(key)):
            return "not_confirmed", reason
    if not _same(current.get("profile_ref"), previous.get("profile_ref")):
        return "not_confirmed", "assessment_context_not_confirmed"
    if not _same(current.get("target_profile"), previous.get("target_profile")):
        return "not_confirmed", "role_requirements_not_confirmed"
    if (current.get("partial_result") or {}).get("is_incomplete") or (previous.get("partial_result") or {}).get("is_incomplete"):
        return "not_allowed", "partial_cycle"
    return None, None


def compare_reports(current_report: dict[str, Any], previous_report: dict[str, Any]) -> dict[str, Any]:
    """Build a conservative per-skill comparison without recalculation or inference."""
    if str(current_report.get("cycle_id")) == str(previous_report.get("cycle_id")):
        raise ValueError("COMPARISON_REQUIRES_DISTINCT_CYCLES")
    current = current_report["c67"]
    previous = previous_report["c67"]
    global_status, global_reason = _global_evidence(current, previous)
    previous_by_id = {str(item.get("skill_id")): item for item in previous.get("skills", [])}
    rows = []
    for current_skill in current.get("skills", []):
        skill_id = str(current_skill.get("skill_id"))
        previous_skill = previous_by_id.get(skill_id)
        status, reason = global_status, global_reason
        current_score = _score(current_skill)
        previous_score = _score(previous_skill or {})
        if previous_skill is None:
            status, reason = "not_allowed", "skill_absent_in_previous_cycle"
        elif status is None and not _same(_skill_definition(current_skill), _skill_definition(previous_skill)):
            status, reason = "not_confirmed", "skill_definition_not_confirmed"
        elif status is None and (current_skill.get("outcome") != "full_score" or previous_skill.get("outcome") != "full_score"):
            status, reason = "not_allowed", "full_score_required"
        elif status is None and (current_score is None or previous_score is None):
            status, reason = "not_allowed", "numeric_score_missing"
        if status is None:
            status, reason = "allowed", None
        delta = current_score - previous_score if status == "allowed" else None
        rows.append({
            "skill_id": skill_id,
            "skill_name": current_skill.get("skill_name") or skill_id,
            "competency_id": current_skill.get("competency_id"),
            "previous": None if previous_score is None else float(previous_score),
            "current": None if current_score is None else float(current_score),
            "difference": None if delta is None else float(delta),
            "comparability": {"status": status, "reason": reason},
        })
    statuses = {row["comparability"]["status"] for row in rows}
    mode = "numeric" if statuses == {"allowed"} else "mixed" if "allowed" in statuses else "separate"
    return {
        "contract_version": CONTRACT_VERSION,
        "mode": mode,
        "current": _report_ref(current_report),
        "previous": _report_ref(previous_report),
        "skills": rows,
    }


def _report_ref(report: dict[str, Any]) -> dict[str, Any]:
    c67 = report["c67"]
    return {
        "cycle_id": str(report["cycle_id"]),
        "report_id": str(report["id"]),
        "report_revision_no": report["revision_no"],
        "results_revision_id": str(report["results_revision_id"]),
        "created_at": report.get("created_at"),
        "role_ref": c67.get("role_ref"),
        "started_at": (c67.get("time") or {}).get("started_at"),
        "closed_at": (c67.get("collection") or {}).get("closed_at"),
    }


def render_comparison_pdf(comparison: dict[str, Any]) -> bytes:
    """Render the exact selected pair with the existing server PDF pipeline."""
    from Api.typst_pdf_renderer import render_typst_report

    payload = {
        "title": "Сравнение оценок 4К",
        "mode": comparison["mode"],
        "current": comparison["current"],
        "previous": comparison["previous"],
        "comparable": [row for row in comparison["skills"] if row["comparability"]["status"] == "allowed"],
        "separate": [{**row, "reason_text": REASON_LABELS.get(
            row["comparability"]["reason"], "Сопоставимость не подтверждена."
        )} for row in comparison["skills"] if row["comparability"]["status"] != "allowed"],
    }
    return render_typst_report(payload, "m8_report_comparison_v1.typ")
