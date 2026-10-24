from __future__ import annotations

import hashlib
import json
import tomllib
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
CHECKSUM_KIND = "sha256-canonical-json-v1"
CONTENT_CHECKSUM_KIND = "sha256-raw-bytes-v1"

# Logical names are part of the persisted contract. Paths always identify an
# immutable, versioned publication; callers must never replace them with latest/current.
DEFAULT_DEPENDENCIES: dict[str, str] = {
    "source_set": "docs/methodology/source-sets/2026-10-01",
    "m2_methodology": "assessment_definitions/methodologies/competencies_4k/1.1",
    "m3_role_profiles": "assessment_definitions/role_profiles/competencies_4k/1.1",
    "m4_context": "assessment_definitions/contexts/competencies_4k/1.1",
    "m5_case_catalog": "assessment_definitions/cases/competencies_4k/1.1",
    "m5_functional_package": "assessment_definitions/cases/competencies_4k/functional-personalization/0.3",
    "m5_functional_runtime": "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.1.0",
    "m5_functional_repair": "assessment_definitions/prompts/m5_functional_repair/v1",
    "m5_functional_protocol": "assessment_definitions/prompts/m5_functional_protocol/v1",
    "m6_evidence": "assessment_definitions/prompts/m6_evidence/v1.0.1",
    "m6_indicator_assessment": "assessment_definitions/prompts/m6_indicator_assessment/v1.0.1",
    "m6_substantive_admission": "assessment_definitions/prompts/m6_substantive_admission/v2",
    "m6_cycle_aggregation": "assessment_definitions/aggregation/m6_cycle_aggregation/v1",
    "m7_cycle_plan": "assessment_definitions/planning/m7_cycle_plan/v1",
    "m7_return_integration": "assessment_definitions/planning/m7_return_integration/v2",
    "m8_descriptive_report": "assessment_definitions/prompts/m8_descriptive_report/v1",
    "m8_report_projection": "assessment_definitions/reports/m8_basic_report/v1_4",
    "m8_recommendations": "assessment_definitions/recommendations/m8/v1_2",
    "provider_contract": "assessment_definitions/providers/deepseek/v1",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def checksum(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _content_snapshot(path: Path, *, root: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"CYCLE_DEPENDENCY_UNAVAILABLE:{path.relative_to(root).as_posix()}")
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    entries = [
        {
            "path": item.relative_to(root).as_posix(),
            "checksum": hashlib.sha256(item.read_bytes()).hexdigest(),
            "checksum_kind": CONTENT_CHECKSUM_KIND,
        }
        for item in files
    ]
    return {
        "path": path.relative_to(root).as_posix(),
        "kind": "file" if path.is_file() else "directory",
        "content_checksum": checksum(entries),
        "content_checksum_kind": CHECKSUM_KIND,
        "files": entries,
    }


def application_version(*, root: Path = ROOT) -> str:
    with (root / "pyproject.toml").open("rb") as source:
        return str(tomllib.load(source)["project"]["version"])


@lru_cache(maxsize=4)
def _dependency_snapshot(root: Path, dependency_items: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    return {
        name: _content_snapshot(root / relative_path, root=root)
        for name, relative_path in dependency_items
    }


def build_manifest(
    *,
    profile_ref: Mapping[str, Any],
    selected_role_ref: Mapping[str, Any],
    target_set_checksum: str,
    parameter_sources: Mapping[str, Any],
    catalog_ref: Mapping[str, Any] | None,
    root: Path = ROOT,
    dependencies: Mapping[str, str] = DEFAULT_DEPENDENCIES,
) -> tuple[dict[str, Any], str]:
    snapshot = deepcopy(_dependency_snapshot(root, tuple(sorted(dependencies.items()))))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "application_version": application_version(root=root),
        "application_version_role": "deployment_trace_only",
        "canonicalization": CHECKSUM_KIND,
        "dependencies": snapshot,
        "runtime_refs": {
            "profile_ref": dict(profile_ref),
            "selected_role_ref": dict(selected_role_ref),
            "target_set_checksum": target_set_checksum,
            "parameter_sources": dict(parameter_sources),
            "catalog_ref": dict(catalog_ref) if catalog_ref else None,
        },
    }
    return manifest, checksum(manifest)


def validate_manifest(manifest: Mapping[str, Any], expected_checksum: str) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("canonicalization") != CHECKSUM_KIND:
        raise ValueError("CYCLE_EXECUTION_MANIFEST_UNSUPPORTED")
    if checksum(manifest) != expected_checksum:
        raise ValueError("CYCLE_EXECUTION_MANIFEST_CHECKSUM_MISMATCH")


def resolve_dependency(
    manifest: Mapping[str, Any],
    expected_checksum: str,
    name: str,
    *,
    root: Path = ROOT,
) -> Path:
    validate_manifest(manifest, expected_checksum)
    dependency = manifest.get("dependencies", {}).get(name)
    if not isinstance(dependency, dict):
        raise ValueError(f"CYCLE_DEPENDENCY_NOT_FROZEN:{name}")
    path = root / str(dependency.get("path", ""))
    if not path.exists():
        raise ValueError(f"CYCLE_DEPENDENCY_UNAVAILABLE:{name}")
    actual = _content_snapshot(path, root=root)
    if actual["content_checksum"] != dependency.get("content_checksum"):
        raise ValueError(f"CYCLE_DEPENDENCY_CHECKSUM_MISMATCH:{name}")
    return path


def resolve_cycle_dependency(cycle: Mapping[str, Any], name: str, *, root: Path = ROOT) -> Path:
    manifest = cycle.get("execution_manifest_json")
    manifest_checksum = cycle.get("execution_manifest_checksum")
    if not isinstance(manifest, dict) or not manifest_checksum:
        raise ValueError("CYCLE_EXECUTION_MANIFEST_MISSING")
    return resolve_dependency(manifest, str(manifest_checksum), name, root=root)
