"""Cycle-manifest-bound adapter for saved C-45 inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from Api.cycle_execution_manifest import resolve_cycle_dependency
from Api.m6_input_resolver import normalize


def load_criteria(snapshot: dict, directory: Path, sources_path: Path) -> list[dict]:
    data = (directory / "methodology.json").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if digest != manifest["artifact"]["sha256"] or not any(
        item["checksum"] == digest for item in snapshot["methodology_refs"]
    ):
        raise ValueError("CHECKSUM_MISMATCH")
    sources = json.loads(sources_path.read_bytes())["entries"]
    criteria = {}
    for competency in json.loads(data)["competencies"]:
        source = next(item for item in sources if item["id"] == f"M2.{competency['id']}.matrix")
        if not any(item["sha256"] == source["sha256"] for item in manifest["sources"]):
            raise ValueError("SOURCE_UNRESOLVED")
        for skill in competency["skills"]:
            for component in skill["components"]:
                for indicator in component["indicators"]:
                    criteria[indicator["id"]] = {
                        **indicator,
                        "skill_id": skill["id"],
                        "component_id": component["id"],
                        "m2_version": "v" + source["version"],
                        "source_ref": source,
                        "package_sha256": digest,
                    }
    result = []
    for target in snapshot["indicator_targets"]:
        criterion = criteria.get(target["indicator_id"])
        if not criterion or any(
            criterion[key] != target[key] for key in ("m2_version", "component_id", "skill_id")
        ):
            raise ValueError("TARGET_SET_MISMATCH")
        if not all(criterion.get(key) for key in ("function", "product", "evidence_pattern", "boundary")) \
                or set(criterion["levels"]) != {"L0", "L1", "L2", "L3"}:
            raise ValueError("SOURCE_UNRESOLVED")
        result.append(criterion)
    return result


def resolve(connection, handoff_id: str) -> tuple[int, dict]:
    handoff = connection.execute(
        "SELECT * FROM m5_c45_handoffs WHERE handoff_id=%s", (UUID(handoff_id),)
    ).fetchone()
    if not handoff:
        raise ValueError("M6_HANDOFF_NOT_FOUND")
    row = connection.execute(
        "SELECT * FROM m5_assessment_situations WHERE id=%s", (handoff["assessment_situation_db_id"],)
    ).fetchone()
    cycle = connection.execute("SELECT * FROM m5_cycles WHERE id=%s", (row["cycle_db_id"],)).fetchone()
    session = connection.execute(
        "SELECT * FROM m5_cycle_sessions WHERE id=%s", (row["session_db_id"],)
    ).fetchone()
    if not cycle or not session:
        raise ValueError("M6_OWNER_MISMATCH")
    cycle = dict(cycle)
    methodology = resolve_cycle_dependency(cycle, "m2_methodology")
    source_set = resolve_cycle_dependency(cycle, "source_set")
    criteria = load_criteria(row["snapshot_json"], methodology, source_set / "manifest.json")
    return row["id"], normalize(dict(handoff), dict(row), cycle, dict(session), criteria)
