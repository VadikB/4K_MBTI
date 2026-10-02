from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/aggregation/m6_cycle_aggregation/v1"
M2 = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"


def load_package() -> dict:
    manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
    raw = (PACKAGE / "rules.json").read_bytes()
    expected = (1, "m6_cycle_aggregation", "1.0.0", "draft", "m6_cycle_aggregation_qa", "PM-05")
    if tuple(manifest.get(k) for k in ("schema_version", "id", "version", "status", "scope", "owner")) != expected:
        raise ValueError("M6_AGGREGATION_PACKAGE_INVALID")
    if manifest.get("artifacts") != [{"name": "rules.json", "sha256": hashlib.sha256(raw).hexdigest()}]:
        raise ValueError("CHECKSUM_MISMATCH")
    rules = json.loads(raw)
    source_manifest = json.loads((ROOT / "docs/methodology/source-sets/2026-10-01/manifest.json").read_bytes())
    source = next((x for x in source_manifest["entries"] if x["id"] == rules["source"]["id"] and x["version"] == rules["source"]["version"]), None)
    if not source or source["sha256"] != rules["source"]["sha256"]:
        raise ValueError("SOURCE_CHECKSUM_MISMATCH")
    if hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("SOURCE_CHECKSUM_MISMATCH")
    return {"manifest": manifest, "rules": rules, "rules_hash": hashlib.sha256(raw).hexdigest()}


def hierarchy_for(indicator_ids: set[str]) -> list[dict]:
    data = json.loads(M2.read_bytes())
    result = []
    seen = set()
    for competency in data["competencies"]:
        for skill in competency["skills"]:
            components = []
            for component in skill["components"]:
                ids = [x["id"] for x in component["indicators"]]
                selected = [x for x in ids if x in indicator_ids]
                if selected:
                    components.append({"component_id": component["id"], "indicator_ids": selected})
                    seen.update(selected)
            if components:
                components_all = [{"component_id": c["id"], "indicator_ids": [x["id"] for x in c["indicators"]]} for c in skill["components"]]
                result.append({"skill_id": skill["id"], "components": components_all})
    if seen != indicator_ids:
        raise ValueError("M2_TARGET_NOT_FOUND")
    return result
