from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from Api.m5_case_runtime import checksum


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/recommendations/m8/v1"
CONTRACT_VERSION = "m8-recommendations/1.0.0"
PROFILE_ALLOWLIST = {
    "organization_context": ("description", "activities", "products", "employee_context"),
    "role_profile": ("name", "short_description", "mission", "typical_tasks", "objects_of_work"),
    "user_context": ("position", "department", "specialization", "regular_tasks", "systems", "tools"),
}
FORBIDDEN_PROFILE_KEYS = {"full_name", "contacts", "email", "phone", "name"}


def load_package() -> dict[str, Any]:
    manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
    raw = (PACKAGE / "templates.json").read_bytes()
    expected = (1, "m8_recommendations", "1.0.0", "draft", "individual_report", "PM-06")
    if tuple(manifest.get(key) for key in ("schema_version", "id", "version", "status", "scope", "owner")) != expected:
        raise ValueError("M8_RECOMMENDATION_PACKAGE_INVALID")
    if manifest.get("artifacts") != [{"name": "templates.json", "sha256": hashlib.sha256(raw).hexdigest()}]:
        raise ValueError("CHECKSUM_MISMATCH")
    source_manifest = json.loads((ROOT / "docs/methodology/source-sets/2026-10-01/manifest.json").read_bytes())
    source_ref = manifest.get("source") or {}
    source = next((item for item in source_manifest["entries"]
                   if item["id"] == source_ref.get("id") and item["version"] == source_ref.get("version")), None)
    if not source or source["sha256"] != source_ref.get("sha256"):
        raise ValueError("SOURCE_CHECKSUM_MISMATCH")
    if hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("SOURCE_CHECKSUM_MISMATCH")
    templates = json.loads(raw)
    if templates.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("M8_RECOMMENDATION_PACKAGE_INVALID")
    return {"manifest": manifest, "templates": templates, "template_hash": hashlib.sha256(raw).hexdigest()}


def profile_projection(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Return the minimum M4 content used for action context, never identity/contact data."""
    content = dict((snapshot or {}).get("content") or snapshot or {})
    projection: dict[str, Any] = {}
    for section, allowed in PROFILE_ALLOWLIST.items():
        source = content.get(section)
        if not isinstance(source, dict):
            continue
        selected = {key: source[key] for key in allowed if key in source and source[key] not in (None, "", [], {})}
        if selected:
            projection[section] = selected
    return projection


def _flatten_strings(value: Any):
    if isinstance(value, str) and value.strip():
        yield value.strip()
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() not in FORBIDDEN_PROFILE_KEYS:
                yield from _flatten_strings(item)


def _action_context(profile: dict[str, Any], fallback: str) -> str:
    values = list(_flatten_strings(profile))
    return values[0][:240] if values else fallback


def _skill_indicators(skill: dict[str, Any]) -> set[str]:
    return {indicator for component in skill.get("components", []) for indicator in component.get("required_indicator_ids", [])}


def _basis_for(skill: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any] | None:
    indicators = _skill_indicators(skill)
    candidates = [item for item in observations if item.get("indicator_id") in indicators and item.get("revision_id")]
    if not candidates:
        return None
    item = sorted(candidates, key=lambda value: (value.get("indicator_id", ""), value.get("revision_id", "")))[0]
    confirmed = list((item.get("confidence") or {}).get("confirmed_features") or [])
    refs = list(item.get("refs") or [])
    manifestation = confirmed[0] if confirmed else (refs[0].get("meaning") if refs else None)
    return {
        "kind": "indicator_assessment",
        "skill_id": skill["skill_id"],
        "indicator_id": item["indicator_id"],
        "ia_revision_id": item["revision_id"],
        "assessment_revision_id": item.get("assessment_revision_id"),
        "evidence_revision_id": item.get("evidence_revision_id"),
        "assessment_situation_id": item.get("assessment_situation_id"),
        "outcome": item.get("outcome"),
        "manifestation": manifestation or "зафиксированное проявление в завершённой Assessment Situation",
    }


def _validate_basis(skill: dict[str, Any], basis: dict[str, Any], observations: list[dict[str, Any]]) -> None:
    if basis.get("skill_id") != skill.get("skill_id") or basis.get("indicator_id") not in _skill_indicators(skill):
        raise ValueError("RECOMMENDATION_BASIS_SCOPE_MISMATCH")
    matches = [item for item in observations if item.get("indicator_id") == basis["indicator_id"]
               and str(item.get("revision_id")) == str(basis["ia_revision_id"])]
    if len(matches) != 1:
        raise ValueError("RECOMMENDATION_BASIS_UNRESOLVED")


def generate(results: dict[str, Any], profile_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    package = load_package()
    content = package["templates"]
    templates = content["types"]
    profile = profile_projection(profile_snapshot)
    context = _action_context(profile, content["fallback_context"])
    observations = list(results.get("observations") or [])
    recommendations, notices = [], []
    for skill in results.get("assessed_skill_profile", []):
        if skill.get("outcome") == "no_result":
            notice = content["no_result_notice"]
            notices.append({
                "skill_id": skill["skill_id"],
                "kind": "INSUFFICIENT_BASIS",
                "text": notice["text"], "limitations": list(notice["limitations"]),
            })
            continue
        basis = _basis_for(skill, observations)
        if basis is None:
            notice = content["unresolved_basis_notice"]
            notices.append({"skill_id": skill["skill_id"], "kind": "BASIS_UNRESOLVED",
                            "text": notice["text"], "limitations": list(notice["limitations"])})
            continue
        _validate_basis(skill, basis, observations)
        for recommendation_type in ("Development", "Consolidation / Maintenance", "Application / Transfer"):
            template = templates[recommendation_type]
            recommendation = {
                "recommendation_id": f"{skill['skill_id']}:{recommendation_type.split()[0].lower()}",
                "skill_id": skill["skill_id"],
                "type": recommendation_type,
                "basis_refs": [basis],
                "goal": template["goal"].format(manifestation=basis["manifestation"]),
                "practice": template["practice"].format(manifestation=basis["manifestation"]),
                "application_context": context,
                "progress_signal": template["progress_signal"],
                "limitations": list(content["common_limitations"]),
                "component_ids": [component["component_id"] for component in skill.get("components", [])
                                  if basis["indicator_id"] in component.get("required_indicator_ids", [])],
                "indicator_ids": [basis["indicator_id"]],
                "gap_ref": None,
            }
            recommendations.append(recommendation)
    generation_input = {
        "results_revision_id": results.get("results_revision_id"),
        "results_version": results.get("results_version"),
        "profile_ref": results.get("profile_ref"),
        "profile_projection": profile,
        "target_profile": results.get("target_profile"),
        "skill_inputs": [{"skill_id": skill.get("skill_id"), "outcome": skill.get("outcome"),
                          "score": skill.get("score"), "components": skill.get("components"),
                          "comparison": skill.get("comparison")} for skill in results.get("assessed_skill_profile", [])],
        "observation_refs": [{**{key: item.get(key) for key in ("indicator_id", "revision_id", "assessment_revision_id",
                              "evidence_revision_id", "assessment_situation_id", "outcome")},
                              "confirmed_features": list((item.get("confidence") or {}).get("confirmed_features") or []),
                              "refs": list(item.get("refs") or [])} for item in observations],
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "mechanism": {"kind": "deterministic_template", "id": package["manifest"]["id"],
                      "version": package["manifest"]["version"], "template_checksum": package["template_hash"]},
        "input": generation_input,
        "input_checksum": checksum(generation_input),
        "recommendations": recommendations,
        "notices": notices,
        "status": "ready" if recommendations else "unavailable",
        "failure_reason": None if recommendations else "NO_RESOLVABLE_SKILL_BASIS",
    }
