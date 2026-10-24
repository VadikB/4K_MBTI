import hashlib
import json
from pathlib import Path

import pytest

from Api.cycle_execution_manifest import (
    CHECKSUM_KIND,
    build_manifest,
    resolve_dependency,
    validate_manifest,
)


def _root(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "9.8.7"\n', encoding="utf-8")
    return tmp_path


def _build(root: Path, relative_path: str):
    return build_manifest(
        profile_ref={"id": "profile:1", "version": "1", "checksum": "p"},
        selected_role_ref={"id": "role:1", "version": "1", "checksum": "r"},
        target_set_checksum="targets",
        parameter_sources={"time_budget": {"version": "1"}},
        catalog_ref={"id": "catalog", "version": "1", "checksum": "c"},
        root=root,
        dependencies={"package": relative_path},
    )


def test_manifest_separates_application_version_and_resolves_frozen_content(tmp_path: Path):
    root = _root(tmp_path)
    v1 = root / "packages/v1"
    v2 = root / "packages/v2"
    v1.mkdir(parents=True)
    v2.mkdir(parents=True)
    (v1 / "manifest.json").write_text('{"version":"1"}\n', encoding="utf-8")
    (v2 / "manifest.json").write_text('{"version":"2"}\n', encoding="utf-8")

    manifest_v1, checksum_v1 = _build(root, "packages/v1")
    manifest_v2, checksum_v2 = _build(root, "packages/v2")

    assert manifest_v1["application_version"] == "9.8.7"
    assert manifest_v1["application_version_role"] == "deployment_trace_only"
    assert manifest_v1["canonicalization"] == CHECKSUM_KIND
    assert checksum_v1 != checksum_v2
    assert resolve_dependency(manifest_v1, checksum_v1, "package", root=root) == v1
    assert resolve_dependency(manifest_v2, checksum_v2, "package", root=root) == v2


def test_same_ref_cannot_change_after_cycle_snapshot(tmp_path: Path):
    root = _root(tmp_path)
    package = root / "packages/v1"
    package.mkdir(parents=True)
    artifact = package / "rules.json"
    artifact.write_text('{"threshold":1}\n', encoding="utf-8")
    manifest, manifest_checksum = _build(root, "packages/v1")

    artifact.write_text('{"threshold":2}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="CYCLE_DEPENDENCY_CHECKSUM_MISMATCH:package"):
        resolve_dependency(manifest, manifest_checksum, "package", root=root)


def test_deleted_publication_and_unknown_dependency_are_explicit(tmp_path: Path):
    root = _root(tmp_path)
    package = root / "packages/v1"
    package.mkdir(parents=True)
    (package / "rules.json").write_text("{}\n", encoding="utf-8")
    manifest, manifest_checksum = _build(root, "packages/v1")

    (package / "rules.json").unlink()
    package.rmdir()

    with pytest.raises(ValueError, match="CYCLE_DEPENDENCY_UNAVAILABLE:package"):
        resolve_dependency(manifest, manifest_checksum, "package", root=root)
    with pytest.raises(ValueError, match="CYCLE_DEPENDENCY_NOT_FROZEN:other"):
        resolve_dependency(manifest, manifest_checksum, "other", root=root)


def test_manifest_checksum_rejects_runtime_ref_mutation(tmp_path: Path):
    root = _root(tmp_path)
    package = root / "packages/v1"
    package.mkdir(parents=True)
    (package / "rules.json").write_text("{}\n", encoding="utf-8")
    manifest, manifest_checksum = _build(root, "packages/v1")
    manifest["runtime_refs"]["target_set_checksum"] = "changed"

    with pytest.raises(ValueError, match="CYCLE_EXECUTION_MANIFEST_CHECKSUM_MISMATCH"):
        validate_manifest(manifest, manifest_checksum)


def test_functional_protocol_prompt_package_is_complete():
    package = Path(__file__).resolve().parents[2] / "assessment_definitions/prompts/m5_functional_protocol/v1"
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert (manifest["id"], manifest["version"], manifest["owner"]) == (
        "m5_functional_protocol", "1.0.0", "PM-03",
    )
    assert manifest["artifacts"] == [
        {"name": name, "sha256": hashlib.sha256((package / name).read_bytes()).hexdigest()}
        for name in ("challenger.md", "json-retry.md", "tester-addendum.md")
    ]
