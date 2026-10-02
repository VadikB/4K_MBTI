from __future__ import annotations

import hashlib
import json
from pathlib import Path

from Api.assessment_configuration import definition_checksum
from Api.config import settings
from Api.m6_assessment_contracts import AssessmentOutput

PACKAGE = Path(__file__).resolve().parents[1] / "assessment_definitions/prompts/m6_indicator_assessment/v1"


def load_mechanism(ref: str, directory: Path = PACKAGE) -> dict:
    if ref != "m6_indicator_assessment/1.0.0":
        raise ValueError("M6_ASSESSMENT_MECHANISM_UNSUPPORTED")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    prompt = (directory / "prompt.md").read_bytes()
    expected = (1, "m6_indicator_assessment", "1.0.0", "draft", "m6_indicator_assessment_qa")
    actual = tuple(manifest[k] for k in ("schema_version", "id", "version", "status", "scope"))
    if actual != expected or manifest.get("owner") != "PM-05":
        raise ValueError("M6_ASSESSMENT_PACKAGE_INVALID")
    if manifest["artifacts"] != [{"name": "prompt.md", "sha256": hashlib.sha256(prompt).hexdigest()}]:
        raise ValueError("CHECKSUM_MISMATCH")
    source = manifest["source"]
    root = Path(__file__).resolve().parents[1]
    entries = json.loads((root / "docs/methodology/source-sets/2026-10-01/manifest.json").read_bytes())["entries"]
    registered = next((x for x in entries if x["id"] == source["id"] and x["version"] == source["version"]), None)
    if not registered or registered["sha256"] != source["sha256"]:
        raise ValueError("SOURCE_UNRESOLVED")
    if hashlib.sha256((root / registered["path"]).read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("SOURCE_UNRESOLVED")
    config = manifest["execution"]
    for key in ("timeout_seconds", "max_tokens", "max_input_bytes", "lease_seconds"):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError("M6_ASSESSMENT_PACKAGE_INVALID")
    if config.get("temperature") != 0 or config["lease_seconds"] <= config["timeout_seconds"]:
        raise ValueError("M6_ASSESSMENT_PACKAGE_INVALID")
    return {
        "ref": ref, "manifest": manifest, "prompt": prompt.decode(),
        "schema": AssessmentOutput.model_json_schema(), "handler": "m6-indicator-assessment/1",
        "operation": {"provider": "deepseek", "endpoint": str(settings.deepseek_base_url).rstrip("/") + "/chat/completions",
            "model": str(settings.deepseek_model),
            "parameters": {k: config[k] for k in ("temperature", "timeout_seconds", "max_tokens")},
            "prompt_ref": {"id": manifest["id"], "version": manifest["version"], "checksum": hashlib.sha256(prompt).hexdigest()},
            "response_format": "json_object"},
        "max_input_bytes": config["max_input_bytes"], "lease_seconds": config["lease_seconds"],
    }


def verify_mechanism(value: dict, expected_hash: str) -> None:
    if definition_checksum(value) != expected_hash or value.get("handler") != "m6-indicator-assessment/1":
        raise ValueError("CHECKSUM_MISMATCH")
    if value["schema"] != AssessmentOutput.model_json_schema():
        raise ValueError("M6_SCHEMA_UNSUPPORTED")
    if hashlib.sha256(value["prompt"].encode()).hexdigest() != value["operation"]["prompt_ref"]["checksum"]:
        raise ValueError("CHECKSUM_MISMATCH")
