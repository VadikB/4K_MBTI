from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from Api.m5_case_runtime import checksum

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "assessment_definitions/aggregation/m6_admission/v1/rules.json"


def load_rules() -> dict:
    rules = json.loads(RULES.read_bytes())
    expected = (1, "m6_admission", "1.0.0", "draft", "m6_product_technical_acceptance", "PM-05")
    if tuple(rules.get(k) for k in ("schema_version", "id", "version", "status", "scope", "owner")) != expected:
        raise ValueError("M6_ADMISSION_PACKAGE_INVALID")
    entries = json.loads((ROOT / "docs/methodology/source-sets/2026-10-01/manifest.json").read_bytes())["entries"]
    source = next((x for x in entries if x["id"] == rules["source"]["id"] and x["version"] == rules["source"]["version"]), None)
    if not source or source["sha256"] != rules["source"]["sha256"]:
        raise ValueError("SOURCE_UNRESOLVED")
    if hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("SOURCE_UNRESOLVED")
    return rules


def decide(connection, *, cycle_id: str, observations: list[dict]) -> tuple[str, list[dict], list[str]]:
    rules = load_rules()
    by_indicator: dict[str, list[dict]] = defaultdict(list)
    for item in observations:
        by_indicator[item["indicator_id"]].append(item)
    requirements = connection.execute(
        """SELECT p.observation_requirements_json FROM m7_cycle_plans p
           JOIN m5_cycles c ON c.id=p.cycle_db_id WHERE c.cycle_id=%s""", (cycle_id,),
    ).fetchone()
    requirement_map = {x["indicator_id"]: x for x in (requirements["observation_requirements_json"] if requirements else [])}
    decisions, limitations = [], list(rules["limitations"])
    for indicator_id, rows in sorted(by_indicator.items()):
        numeric = [x for x in rows if x.get("outcome") in rules["numeric_outcomes"]]
        revision_ids = sorted(x["revision_id"] for x in numeric)
        as_ids = {x["assessment_situation_id"] for x in numeric}
        contexts = []
        for as_id in sorted(as_ids):
            row = connection.execute(
                "SELECT snapshot_json FROM m5_assessment_situations WHERE assessment_situation_id=%s", (as_id,),
            ).fetchone()
            if row:
                contexts.append({"assessment_situation_id": as_id, "base_role": row["snapshot_json"].get("base_role"),
                                 "case_ref": row["snapshot_json"].get("case_ref")})
        required = int(requirement_map.get(indicator_id, {}).get("distinct_as_required", 1))
        checks = {
            "numeric_ia_present": bool(numeric),
            "all_opportunities_present": bool(numeric) and all(x.get("opportunity") == rules["required_opportunity"] for x in numeric),
            "all_refs_resolved": bool(numeric) and all(x.get("refs") for x in numeric),
            "same_m2_version": len({x.get("m2_version") for x in numeric}) <= 1,
            "same_base_role": len({x.get("base_role") for x in contexts}) <= 1 and len(contexts) == len(as_ids),
            "no_reported_contradiction": all(not x.get("contradictions") for x in numeric),
            "distinct_as_sufficient": len(as_ids) >= required,
        }
        admissible = all(checks.values())
        failed = sorted(key for key, value in checks.items() if not value)
        decisions.append({
            "indicator_id": indicator_id,
            "included_revision_ids": revision_ids,
            "interpretation_admissible": bool(numeric),
            "numeric_admissible": admissible,
            "reason_code": "ADMITTED_ALL_CHECKS" if admissible else "ADMISSION_CHECK_FAILED:" + ",".join(failed),
            "mechanism": {"id": rules["id"], "version": rules["version"], "rules_checksum": checksum(rules)},
            "checks": checks,
            "contexts": contexts,
        })
    return f"{rules['id']}/{rules['version']}", decisions, limitations
