from __future__ import annotations

import hashlib
import json
from pathlib import Path

from Api.llm.provider_contract import load_provider_contract
from Api.m6_candidate_v3 import EvidenceCandidateV3
from Api.m6_contracts import EvidenceAnalysis, EvidenceCandidate

PREVIOUS_REF = "m6_evidence/1.0.1"
QUOTE_REF = "m6_evidence/1.0.2"
REPAIR_REF = "m6_evidence/1.0.3"
QUOTE_HANDLER = "m6-evidence/2"
QUOTE_INPUT_CONTRACT = "M6.EvidenceInput/2"
QUOTE_OUTPUT_CONTRACT = "M6.EvidenceCandidate/2"
REPAIR_HANDLER = "m6-evidence/3"
REPAIR_INPUT_CONTRACT = "M6.EvidenceInput/3"
REPAIR_OUTPUT_CONTRACT = "M6.EvidenceCandidate/3"
PACKAGE = Path(__file__).resolve().parents[1] / "assessment_definitions/prompts/m6_evidence/v1.0.1"
PACKAGES = {PREVIOUS_REF: PACKAGE, QUOTE_REF: PACKAGE.with_name("v1.0.2"),
            REPAIR_REF: PACKAGE.with_name("v1.0.3")}


def load_mechanism(ref: str | None = None, directory: Path | None = None,
                   source_set: Path | None = None, provider_contract: Path | None = None) -> dict:
    if ref is not None and ref not in PACKAGES:
        raise ValueError("M6_MECHANISM_UNSUPPORTED")
    if directory is None:
        directory = PACKAGES[ref or PREVIOUS_REF]
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest_ref = f"{manifest.get('id')}/{manifest.get('version')}"
    if ref is None:
        ref = manifest_ref
    if ref not in PACKAGES:
        raise ValueError("M6_MECHANISM_UNSUPPORTED")
    expected = (1, ref, "draft", "m6_evidence_qa", "PM-05")
    actual = (manifest.get("schema_version"), manifest_ref, manifest.get("status"),
              manifest.get("scope"), manifest.get("owner"))
    supersedes = {PREVIOUS_REF: "m6_evidence/1.0.0", QUOTE_REF: PREVIOUS_REF, REPAIR_REF: QUOTE_REF}[ref]
    if actual != expected or manifest.get("supersedes") != supersedes:
        raise ValueError("M6_PACKAGE_INVALID")
    contracts = {
        QUOTE_REF: (QUOTE_INPUT_CONTRACT, QUOTE_OUTPUT_CONTRACT, "M6.EvidenceAnalysis/1"),
        REPAIR_REF: (REPAIR_INPUT_CONTRACT, REPAIR_OUTPUT_CONTRACT, "M6.EvidenceAnalysis/1"),
    }
    if ref in contracts:
        actual_contracts = tuple(manifest.get(key) for key in ("input_contract", "output_contract", "analysis_contract"))
        if actual_contracts != contracts[ref]:
            raise ValueError("M6_PACKAGE_INVALID")
    prompt = (directory / "prompt.md").read_bytes()
    if manifest.get("artifacts") != [{"name": "prompt.md", "sha256": hashlib.sha256(prompt).hexdigest()}]:
        raise ValueError("CHECKSUM_MISMATCH")
    root = Path(__file__).resolve().parents[1]
    source = manifest.get("source") or {}
    entries = json.loads((source_set or root / "docs/methodology/source-sets/2026-10-01/manifest.json").read_bytes())["entries"]
    registered = next((x for x in entries if x["id"] == source.get("id") and x["version"] == source.get("version")), None)
    if not registered or registered["sha256"] != source.get("sha256") or hashlib.sha256((root / registered["path"]).read_bytes()).hexdigest() != source.get("sha256"):
        raise ValueError("SOURCE_UNRESOLVED")
    config = manifest.get("execution") or {}
    provider = load_provider_contract((provider_contract / "manifest.json") if provider_contract else None)
    for key in ("timeout_seconds", "max_tokens", "max_input_bytes", "lease_seconds", "validation_attempts"):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError("M6_PACKAGE_INVALID")
    if config["validation_attempts"] > 2 or config["lease_seconds"] <= config["timeout_seconds"]:
        raise ValueError("M6_PACKAGE_INVALID")
    handler, model = {
        PREVIOUS_REF: ("m6-evidence/1", EvidenceAnalysis),
        QUOTE_REF: (QUOTE_HANDLER, EvidenceCandidate),
        REPAIR_REF: (REPAIR_HANDLER, EvidenceCandidateV3),
    }[ref]
    return {
        "ref": ref, "manifest": manifest, "prompt": prompt.decode(),
        "schema": model.model_json_schema(),
        "handler": handler,
        "operation": {"provider": provider["provider"], "endpoint": provider["endpoint"],
            "model": provider["model"],
            "parameters": {key: config[key] for key in ("temperature", "timeout_seconds", "max_tokens")},
            "prompt_ref": {"id": manifest["id"], "version": manifest["version"], "checksum": hashlib.sha256(prompt).hexdigest()},
            "response_format": "json_object", "thinking": provider["thinking"],
            "provider_contract": {"version": provider["version"], "checksum": provider["checksum"]}},
        "max_input_bytes": config["max_input_bytes"], "lease_seconds": config["lease_seconds"],
        "validation_attempts": config["validation_attempts"],
    }
