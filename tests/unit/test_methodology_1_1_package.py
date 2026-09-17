import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_methodology_1_1_package import LEVELS, validate_package, write_package


def _package() -> dict:
    return {
        "schema_version": 2,
        "status": "draft",
        "levels": copy.deepcopy(LEVELS),
        "competencies": [{
            "id": "K1",
            "skills": [{
                "id": "K1.1",
                "components": [{
                    "id": "K1.C01",
                    "indicators": [{
                        "id": "K1.I01",
                        "levels": {"L0": "a", "L1": "b", "L2": "c", "L3": "d"},
                        "evidence_pattern": "observable",
                    }],
                }],
            }],
        }],
    }


@pytest.mark.unit
def test_validator_accepts_indicator_hierarchy_without_release_count_gate() -> None:
    validate_package(_package(), enforce_release_counts=False)


@pytest.mark.unit
def test_validator_rejects_missing_l0() -> None:
    package = _package()
    del package["competencies"][0]["skills"][0]["components"][0]["indicators"][0]["levels"]["L0"]
    with pytest.raises(ValueError, match="L0-L3"):
        validate_package(package, enforce_release_counts=False)


@pytest.mark.unit
def test_validator_rejects_duplicate_methodology_ids() -> None:
    package = _package()
    duplicate = copy.deepcopy(package["competencies"][0]["skills"][0]["components"][0]["indicators"][0])
    package["competencies"][0]["skills"][0]["components"][0]["indicators"].append(duplicate)
    with pytest.raises(ValueError, match="Duplicate methodology ID"):
        validate_package(package, enforce_release_counts=False)


@pytest.mark.unit
def test_package_writer_is_deterministic(tmp_path) -> None:
    package = _package()
    package.update({"code": "competencies_4k", "methodology_version": "1.1"})
    sources = [{"name": "source.xlsx", "sha256": "abc"}]

    first = tmp_path / "first"
    second = tmp_path / "second"
    write_package(package, sources, first)
    write_package(package, sources, second)

    assert (first / "methodology.json").read_bytes() == (second / "methodology.json").read_bytes()
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "draft"


@pytest.mark.unit
def test_repository_manifest_covers_every_agent_artifact() -> None:
    package_dir = Path("assessment_definitions/methodologies/competencies_4k/1.1")
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    declared = {item["name"]: item["sha256"] for item in manifest["agent_artifacts"]}
    actual = {
        path.relative_to(package_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (package_dir / "agents").rglob("*")
        if path.is_file()
    }
    assert declared == actual
