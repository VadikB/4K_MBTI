from __future__ import annotations

import hashlib
import json
from pathlib import Path

from Api.m5_case_runtime import checksum

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/planning/m7_cycle_plan/v1"
METHODOLOGY = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"


def load_rules() -> dict:
    manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
    rules_bytes = (PACKAGE / "rules.json").read_bytes()
    expected = (1, "m7_cycle_plan", "1.0.0", "draft", "m7_cycle_plan_qa", "PM-04")
    if tuple(manifest.get(k) for k in ("schema_version", "id", "version", "status", "scope", "owner")) != expected:
        raise ValueError("M7_PLANNING_PACKAGE_INVALID")
    if manifest["artifacts"] != [{"name": "rules.json", "sha256": hashlib.sha256(rules_bytes).hexdigest()}]:
        raise ValueError("CHECKSUM_MISMATCH")
    rules = json.loads(rules_bytes)
    source = rules["source"]
    entries = json.loads((ROOT / "docs/methodology/source-sets/2026-10-01/manifest.json").read_bytes())["entries"]
    registered = next((x for x in entries if x["id"] == source["id"] and x["version"] == source["version"]), None)
    if not registered or registered["sha256"] != source["sha256"]:
        raise ValueError("SOURCE_UNRESOLVED")
    if hashlib.sha256((ROOT / registered["path"]).read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("SOURCE_UNRESOLVED")
    if rules.get("duration_estimate") != "planned_max_minutes":
        raise ValueError("M7_PLANNING_ALGORITHM_CONFIGURATION_UNSUPPORTED")
    if rules.get("tie_break") != ["uncovered_indicator_count_desc", "skill_spread_desc",
                                  "planned_max_minutes_asc", "case_id_asc", "case_version_asc"]:
        raise ValueError("M7_PLANNING_ALGORITHM_CONFIGURATION_UNSUPPORTED")
    if rules.get("required_case_statuses") != ["FROZEN"] or rules.get("required_qa_scopes") != [
        "case_format", "case_dialogue", "assessment_situation"
    ]:
        raise ValueError("M7_PLANNING_ALGORITHM_CONFIGURATION_UNSUPPORTED")
    for name in ("default_time_budget_seconds", "default_calendar_window_seconds"):
        if type(rules.get(name)) is not int or rules[name] <= 0:
            raise ValueError("M7_PLANNING_PARAMETER_INVALID")
    rules["snapshot_checksum"] = checksum(rules)
    return rules


def methodology_targets(selected_skills: list[str]) -> list[dict]:
    value = json.loads(METHODOLOGY.read_bytes())
    result = []
    versions = {"K1": "v1.1", "K2": "v1.0", "K3": "v1.1", "K4": "v1.0"}
    for competency in value["competencies"]:
        if competency["id"] not in selected_skills:
            continue
        for skill in competency["skills"]:
            for component in skill["components"]:
                for indicator in component["indicators"]:
                    result.append({"indicator_id": indicator["id"], "m2_version": versions[competency["id"]],
                                   "skill_id": skill["id"], "component_id": component["id"]})
    if not result:
        raise ValueError("TARGET_SET_MISMATCH")
    return result
