from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from Api.m5_case_runtime import checksum


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/recommendations/m8/v1_2"
CONTRACT_VERSION = "m8-recommendations/1.2.0"
VERIFIED_CONTRACT_VERSIONS = {"m8-recommendations/1.1.0", CONTRACT_VERSION}
# Canonical M4 content only: identity and arbitrary nested metadata never cross this boundary.
PROFILE_ALLOWLIST = {
    "organization_context": ("activity_description", "activities", "products", "employee_context"),
    "role_profile": ("mission", "typical_tasks", "work_objects", "independent_authority", "approval_required", "escalation", "role_constraints"),
    "user_context": ("position_or_status", "unit_or_program", "specialization", "regular_tasks", "systems_and_tools", "irrelevant_areas"),
}


def load_package() -> dict[str, Any]:
    manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
    raw = (PACKAGE / "templates.json").read_bytes()
    expected = (1, "m8_recommendations", "1.2.0", "draft", "individual_report", "PM-06")
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
    if snapshot is not None and not isinstance(snapshot, dict):
        raise ValueError("M8_PROFILE_INVALID")
    if (snapshot or {}).get("schema_version", 1) != 1 or (snapshot or {}).get("status") == "blocked":
        raise ValueError("M8_PROFILE_INVALID")
    content = (snapshot or {}).get("content", snapshot or {})
    if not isinstance(content, dict):
        raise ValueError("M8_PROFILE_INVALID")
    projection: dict[str, Any] = {}
    for section, allowed in PROFILE_ALLOWLIST.items():
        source = content.get(section)
        if source is None:
            continue
        if not isinstance(source, dict):
            raise ValueError("M8_PROFILE_INVALID")
        if section == "role_profile":
            source = source.get("card", {})
        if not isinstance(source, dict):
            raise ValueError("M8_PROFILE_INVALID")
        # Professional text or lists of text, never unbounded dictionaries containing contacts.
        selected = {}
        for key in allowed:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                selected[key] = value
            elif isinstance(value, list):
                if any(not isinstance(item, str) for item in value):
                    raise ValueError("M8_PROFILE_INVALID")
                texts = [item for item in value if isinstance(item, str) and item.strip()]
                if texts:
                    selected[key] = texts
            elif value is not None and not isinstance(value, str):
                raise ValueError("M8_PROFILE_INVALID")
        if selected:
            projection[section] = selected
    return projection


def _select_context(profile: dict[str, Any], policy: dict) -> dict:
    boundaries = []
    for section in ("role_profile", "user_context"):
        for key, label in policy["boundary_labels"].items():
            value = profile.get(section, {}).get(key)
            if value:
                boundaries.append({"path": f"{section}.{key}", "label": label, "value": value})
    selection = {"policy_version": policy["version"], "status": "missing",
                 "selected_path": None, "selected_index": None, "value": None, "boundaries": boundaries}
    for path in policy["selection_order"]:
        section, key = path.split(".")
        value = profile.get(section, {}).get(key)
        if value:
            selection.update(status="available", selected_path=path,
                             selected_index=0 if isinstance(value, list) else None,
                             value=value[0] if isinstance(value, list) else value)
            break
    return selection


def _skill_indicators(skill: dict[str, Any]) -> set[str]:
    return {indicator for component in skill.get("components", []) for indicator in component.get("required_indicator_ids", [])}


def _validate_basis(skill: dict, basis: dict, observations: list[dict]) -> None:
    if basis.get("skill_id") != skill.get("skill_id") or basis.get("indicator_id") not in _skill_indicators(skill):
        raise ValueError("RECOMMENDATION_BASIS_SCOPE_MISMATCH")
    matches = [x for x in observations if x.get("indicator_id") == basis["indicator_id"]
               and x.get("revision_id") == basis.get("ia_revision_id")]
    if len(matches) != 1:
        raise ValueError("RECOMMENDATION_BASIS_UNRESOLVED")


def _candidate(skill, observation, projection, admissions, rules):
    target = projection["target"]
    decisions = [x for x in admissions if x.get("indicator_id") == observation["indicator_id"]]
    if len(decisions) != 1 or decisions[0].get("interpretation_admissible") is not True:
        return None, "INTERPRETATION_NOT_ADMITTED"
    admission = decisions[0]
    if observation["revision_id"] not in admission.get("interpretable_revision_ids", []):
        return None, "INTERPRETATION_REVISION_NOT_ADMITTED"
    if target.get("status") != rules["status"] or target.get("outcome") not in rules["outcomes"]:
        return None, "NO_JUSTIFIED_RESULT"
    if target.get("opportunity") != rules["opportunity"] or not target.get("opportunity_basis", "").strip():
        return None, "OPPORTUNITY_NOT_CONFIRMED"
    if target.get("uncertainty") or target.get("contradictions") or projection["bundle"].get("contradictions"):
        return None, "UNRESOLVED_LIMITATION"
    if not target.get("refs") or not projection.get("traces") or not target.get("rationale", "").strip():
        return None, "MATERIAL_BASIS_MISSING"
    criterion = projection["criterion"]
    if criterion.get("skill_id") != skill["skill_id"] or criterion.get("id") != observation["indicator_id"]:
        raise ValueError("RECOMMENDATION_BASIS_SCOPE_MISMATCH")
    if not any(c["component_id"] == criterion["component_id"] and criterion["id"] in c.get("required_indicator_ids", [])
               for c in skill.get("components", [])):
        raise ValueError("RECOMMENDATION_COMPONENT_MISMATCH")
    if not all(criterion.get(k) for k in ("function", "product", "name")):
        return None, "CONTENT_NOT_AVAILABLE"
    return {"kind":"indicator_assessment", "skill_id":skill["skill_id"], "indicator_id":observation["indicator_id"],
        "ia_revision_id":observation["revision_id"], **{k:observation[k] for k in
        ("assessment_revision_id","evidence_revision_id","assessment_situation_id")},
        "outcome":target["outcome"], "manifestation":target["rationale"],
        "refs":target["refs"], "material_ref":projection["material_ref"],
        "material_excerpts":[{"turn_id":fragment["turn_id"], "fragment_id":fragment["id"], "quote":fragment["quote"]}
            for trace in projection["traces"] for fragment in trace.get("fragments", [])],
        "ia_checksum":projection["ia_checksum"], "evidence_checksum":projection["evidence_checksum"]}, None


def generate(results: dict, profile_snapshot: dict | None, *, resolved: dict | None = None) -> dict:
    package = load_package()
    content = package["templates"]
    profile = profile_projection(profile_snapshot)
    context = _select_context(profile, content["context_policy"])
    observations = results.get("observations", [])
    if resolved is not None and (resolved.get("cycle_id") != results.get("cycle_id")
            or resolved.get("results_revision_id") != results.get("results_revision_id")
            or resolved.get("results_checksum") != checksum({k:v for k,v in results.items() if k != "results_revision_id"})):
        raise ValueError("RECOMMENDATION_RESULTS_MISMATCH")
    projections = {x["revision_id"]: x for x in (resolved or {}).get("projections", [])}
    if len(projections) != len((resolved or {}).get("projections", [])):
        raise ValueError("RECOMMENDATION_AMBIGUOUS_IA")
    recommendations, notices, diagnostics = [], [], []
    for skill in results.get("assessed_skill_profile", []):
        if skill.get("outcome") == "no_result":
            notices.append({"skill_id":skill["skill_id"], "kind":"INSUFFICIENT_BASIS", **content["no_result_notice"]})
            continue
        before = len(recommendations)
        for obs in sorted(observations, key=lambda x:(x.get("indicator_id", ""), x.get("revision_id", ""))):
            if obs.get("indicator_id") not in _skill_indicators(skill):
                continue
            projection = projections.get(obs.get("revision_id"))
            basis, reason = (None, "SOURCE_NOT_VERIFIED") if projection is None else _candidate(
                skill, obs, projection, results.get("admissions", []), content["admissibility"])
            if reason:
                diagnostics.append({"skill_id":skill["skill_id"], "ia_revision_id":obs.get("revision_id"), "reason":reason})
                continue
            _validate_basis(skill, basis, observations)
            criterion, target = projection["criterion"], projection["target"]
            basis.update({"cycle_id":results["cycle_id"], "results_revision_id":results["results_revision_id"]})
            types = {"Development":None}
            for action in content["supported_actions"]:
                phrase = action["confirmed_action"]
                # Exact supported action + accepted evidence, never a score/level lookup.
                if (action["indicator_id"] == obs["indicator_id"] and action["m2_version"] == target["m2_version"]
                    and phrase in target["confidence"]["confirmed_features"]
                    and phrase in (target.get("descriptor_basis") or "")
                    and phrase in criterion.get("levels", {}).get(target["outcome"], "")
                    and any(t["ref"]["meaning"] == phrase and t.get("fragments") for t in projection["traces"])):
                    types.update({kind:phrase for kind in action["types"]})
            for kind, action in types.items():
                template = content["types"][kind]
                values = {"manifestation":basis["manifestation"], "indicator_name":criterion["name"],
                          "function":criterion["function"], "product":criterion["product"], "action":action}
                limitations = list(content["common_limitations"]) + list(results.get("limitations", []))
                limitations += [content["context_policy"]["boundary_template"].format(
                    label=boundary["label"], value="; ".join(boundary["value"]) if isinstance(boundary["value"], list) else boundary["value"])
                    for boundary in context["boundaries"]]
                limitations += target["confidence"].get("limitations", []) + projection["bundle"].get("limitations", [])
                for trace in projection["traces"]:
                    limitations += trace.get("limitations", [])
                recommendations.append({"recommendation_id":f"{skill['skill_id']}:{obs['revision_id']}:{kind.split()[0].lower()}",
                    "skill_id":skill["skill_id"], "type":kind, "basis_refs":[basis],
                    **{key:template[key].format(**values) for key in ("goal","practice","progress_signal")},
                    "practice":content["context_policy"]["practice_guard"] + template["practice"].format(**values),
                    "application_context":content["context_policy"]["application_template"].format(
                        context=context["value"], function=criterion["function"]) if context["status"] == "available" else content["fallback_context"],
                    "limitations":list(dict.fromkeys(limitations)), "component_ids":[criterion["component_id"]],
                    "indicator_ids":[obs["indicator_id"]], "gap_ref":None})
        if len(recommendations) == before:
            notices.append({"skill_id":skill["skill_id"], "kind":"BASIS_UNAVAILABLE", **content["unresolved_basis_notice"]})
    generation_input = {"results_revision_id":results.get("results_revision_id"), "results_version":results.get("results_version"),
        "cycle_id":results.get("cycle_id"), "profile_ref":results.get("profile_ref"), "profile_projection":profile,
        "context_selection":context,
        "target_profile":results.get("target_profile"), "skill_inputs":results.get("assessed_skill_profile", []),
        "observation_refs":observations, "admissions":results.get("admissions", []), "resolved":resolved}
    return {"contract_version":CONTRACT_VERSION, "mechanism":{"kind":"deterministic_template", "id":package["manifest"]["id"],
        "version":package["manifest"]["version"], "template_checksum":package["template_hash"]},
        "input":generation_input, "input_checksum":checksum(generation_input), "recommendations":recommendations,
        "notices":notices, "diagnostics":diagnostics, "status":"ready" if recommendations else "unavailable", "failure_reason":None}
