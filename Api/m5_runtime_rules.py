"""Versioned runtime-rule artifacts bound to immutable M5 CaseVersion content."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from Api.m5_case_runtime import checksum


ALLOWED_FUNCTIONS = {"character_reaction", "material_update", "facilitator_action"}


def load_runtime_rule_package(directory: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    expected = (1, "m5-functional-personalization-runtime", "1.0.0", "draft", "PM-04")
    if tuple(manifest.get(key) for key in ("schema_version", "id", "version", "status", "owner")) != expected:
        raise ValueError("M5_RUNTIME_RULE_MANIFEST_INVALID")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1 or artifacts[0].get("name") != "event-bindings.json":
        raise ValueError("M5_RUNTIME_RULE_MANIFEST_INVALID")
    artifact_path = directory / artifacts[0]["name"]
    if hashlib.sha256(artifact_path.read_bytes()).hexdigest() != artifacts[0].get("sha256"):
        raise ValueError("M5_RUNTIME_RULE_ARTIFACT_CHECKSUM_MISMATCH")
    bindings = load_event_bindings(artifact_path, cases)
    return {
        "manifest": manifest,
        "manifest_checksum": hashlib.sha256(manifest_raw).hexdigest(),
        "bindings": bindings,
    }


def load_event_bindings(path: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if tuple(value.get(key) for key in ("schema_version", "id", "version", "status", "owner")) != (
        1, "m5-functional-personalization-runtime", "1.0.0", "draft", "PM-04"
    ):
        raise ValueError("M5_RUNTIME_RULE_ARTIFACT_INVALID")
    expected = {case["case_id"]: case for case in cases}
    bindings = value.get("case_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(expected):
        raise ValueError("M5_RUNTIME_RULE_CASE_SET_MISMATCH")
    for case_id, case in expected.items():
        binding = bindings[case_id]
        if binding.get("case_version") != case["version"] or binding.get("case_checksum") != checksum(case):
            raise ValueError(f"M5_RUNTIME_RULE_CASE_REF_MISMATCH:{case_id}")
        events = binding.get("events")
        expected_events = {item["step_id"] for item in case["scenario"]}
        if not isinstance(events, dict) or set(events) != expected_events:
            raise ValueError(f"M5_RUNTIME_RULE_EVENT_SET_MISMATCH:{case_id}")
        speakers = {item["character_id"] for item in case["characters"]}
        materials = {item["material_id"] for item in case["materials"]}
        for event_id, event in events.items():
            if event.get("function") not in ALLOWED_FUNCTIONS:
                raise ValueError(f"M5_RUNTIME_RULE_FUNCTION_INVALID:{case_id}:{event_id}")
            if not set(event.get("speaker_ids") or []).issubset(speakers):
                raise ValueError(f"M5_RUNTIME_RULE_SPEAKER_INVALID:{case_id}:{event_id}")
            if not set(event.get("material_ids") or []).issubset(materials):
                raise ValueError(f"M5_RUNTIME_RULE_MATERIAL_INVALID:{case_id}:{event_id}")
            if event["function"] == "character_reaction" and not event.get("speaker_ids"):
                raise ValueError(f"M5_RUNTIME_RULE_SPEAKER_REQUIRED:{case_id}:{event_id}")
    value["artifact_checksum"] = hashlib.sha256(raw).hexdigest()
    return value


def import_runtime_rule_version(connection, loaded: dict[str, Any], compiled_rules: dict[str, Any]) -> dict[str, Any]:
    manifest = loaded["manifest"]
    bindings = loaded["bindings"]
    rules_checksum = checksum(compiled_rules)
    existing = connection.execute(
        "SELECT id,manifest_checksum,rules_checksum FROM m5_runtime_rule_versions "
        "WHERE artifact_id=%s AND artifact_version=%s FOR UPDATE",
        (manifest["id"], manifest["version"]),
    ).fetchone()
    if existing:
        if existing["manifest_checksum"] != loaded["manifest_checksum"] or existing["rules_checksum"] != rules_checksum:
            raise ValueError("M5_RUNTIME_RULE_VERSION_CONFLICT")
        return {"id": int(existing["id"]), "created": False, "rules_checksum": rules_checksum}
    row = connection.execute("""
        INSERT INTO m5_runtime_rule_versions
        (artifact_id,artifact_version,schema_version,status,owner,manifest_json,manifest_checksum,rules_json,rules_checksum)
        VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s) RETURNING id
    """, (manifest["id"], manifest["version"], manifest["schema_version"], manifest["status"], manifest["owner"],
          json.dumps(manifest, ensure_ascii=False), loaded["manifest_checksum"],
          json.dumps(compiled_rules, ensure_ascii=False), rules_checksum)).fetchone()
    rule_id = int(row["id"])
    for case_id, binding in bindings["case_bindings"].items():
        case = connection.execute(
            "SELECT id,content_checksum FROM m5_case_versions WHERE case_id=%s AND case_version=%s",
            (case_id, binding["case_version"]),
        ).fetchone()
        if case is None or case["content_checksum"] != binding["case_checksum"]:
            raise ValueError(f"M5_RUNTIME_RULE_CASE_NOT_IMPORTED:{case_id}")
        connection.execute("""
            INSERT INTO m5_runtime_rule_case_bindings
            (runtime_rule_version_id,case_version_id,binding_json,binding_checksum)
            VALUES (%s,%s,%s::jsonb,%s)
        """, (rule_id, case["id"], json.dumps(binding, ensure_ascii=False), checksum(binding)))
    return {"id": rule_id, "created": True, "rules_checksum": rules_checksum}


def resolve_runtime_rules(connection, *, case_version_id: int, case_id: str,
                          legacy_rules: dict[str, Any], catalog_db_id: int | None = None,
                          runtime_rule_version_id: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = runtime_rule_version_id
    if catalog_db_id is not None:
        member = connection.execute(
            "SELECT runtime_rule_version_id FROM m5_catalog_case_versions "
            "WHERE catalog_db_id=%s AND case_version_id=%s",
            (catalog_db_id, case_version_id),
        ).fetchone()
        if member and member["runtime_rule_version_id"] is not None:
            if selected is not None and int(member["runtime_rule_version_id"]) != int(selected):
                raise ValueError("M5_RUNTIME_RULE_CATALOG_MISMATCH")
            selected = int(member["runtime_rule_version_id"])
    if selected is None:
        return legacy_rules, {"source": "package_legacy"}
    row = connection.execute("""
        SELECT version.artifact_id,version.artifact_version,version.manifest_checksum,
               version.rules_json,version.rules_checksum
        FROM m5_runtime_rule_versions version
        JOIN m5_runtime_rule_case_bindings binding ON binding.runtime_rule_version_id=version.id
        WHERE version.id=%s AND binding.case_version_id=%s
    """, (selected, case_version_id)).fetchone()
    if row is None or checksum(row["rules_json"]) != row["rules_checksum"]:
        raise ValueError("M5_RUNTIME_RULE_BINDING_UNAVAILABLE")
    return dict(row["rules_json"]), {
        "source": "versioned_runtime_rules", "id": row["artifact_id"],
        "version": row["artifact_version"], "manifest_checksum": row["manifest_checksum"],
        "rules_checksum": row["rules_checksum"],
    }
