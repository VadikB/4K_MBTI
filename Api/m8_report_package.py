from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "assessment_definitions/reports/m8_basic_report/v1_3"


def load_package() -> dict:
    manifest = json.loads((PACKAGE / "manifest.json").read_bytes())
    raw = (PACKAGE / "template.json").read_bytes()
    expected = (1, "m8_basic_report", "1.3.0", "draft", "m8_individual_report", "PM-06")
    if tuple(manifest.get(k) for k in ("schema_version", "id", "version", "status", "scope", "owner")) != expected:
        raise ValueError("M8_REPORT_PACKAGE_INVALID")
    if manifest.get("artifacts") != [{"name": "template.json", "sha256": hashlib.sha256(raw).hexdigest()}]:
        raise ValueError("CHECKSUM_MISMATCH")
    source_manifest = json.loads((ROOT / "docs/methodology/source-sets/2026-10-01/manifest.json").read_bytes())
    source = next((x for x in source_manifest["entries"] if x["id"] == manifest["source"]["id"] and x["version"] == manifest["source"]["version"]), None)
    if not source or source["sha256"] != manifest["source"]["sha256"]:
        raise ValueError("SOURCE_CHECKSUM_MISMATCH")
    if hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("SOURCE_CHECKSUM_MISMATCH")
    template = json.loads(raw)
    if template.get("invariants") != {"show_recommendations": True, "derive_skill_level": False,
                                      "derive_competency_score": False, "preserve_exact_fraction": True}:
        raise ValueError("M8_REPORT_INVARIANTS_INVALID")
    return {"manifest": manifest, "template": template, "template_hash": hashlib.sha256(raw).hexdigest()}
