import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_methodology_1_1_package import (
    _parse_red_flags,
    _red_flag_transformation_evidence,
    validate_package,
    write_package,
)


PACKAGE_DIR = Path("assessment_definitions/methodologies/competencies_4k/1.1")
NORMATIVE_CONTROL = json.loads((PACKAGE_DIR / "normative-control.json").read_text(encoding="utf-8"))


def _package() -> dict:
    return {
        "schema_version": 2,
        "status": "draft",
        "levels": copy.deepcopy(NORMATIVE_CONTROL["levels"]),
        "competencies": [{
            "id": "K1",
            "skills": [{
                "id": "K1.1",
                "components": [{
                    "id": "K1.C01",
                    "indicators": [{
                        "id": "K1.I01",
                        "levels": {"L0": "a", "L1": "b", "L2": "c", "L3": "d"},
                        "evidence_pattern": "observable", "red_flags": [],
                    }],
                }],
            }],
        }],
    }


@pytest.mark.unit
def test_validator_accepts_indicator_hierarchy_without_release_count_gate() -> None:
    validate_package(_package(), normative_control=NORMATIVE_CONTROL, enforce_release_counts=False)


@pytest.mark.unit
def test_validator_rejects_missing_l0() -> None:
    package = _package()
    del package["competencies"][0]["skills"][0]["components"][0]["indicators"][0]["levels"]["L0"]
    with pytest.raises(ValueError, match="L0-L3"):
        validate_package(package, normative_control=NORMATIVE_CONTROL, enforce_release_counts=False)


@pytest.mark.unit
def test_validator_rejects_duplicate_methodology_ids() -> None:
    package = _package()
    duplicate = copy.deepcopy(package["competencies"][0]["skills"][0]["components"][0]["indicators"][0])
    package["competencies"][0]["skills"][0]["components"][0]["indicators"].append(duplicate)
    with pytest.raises(ValueError, match="Duplicate methodology ID"):
        validate_package(package, normative_control=NORMATIVE_CONTROL, enforce_release_counts=False)


@pytest.mark.unit
def test_explicit_red_flag_code_is_not_split_inside_number() -> None:
    result = _parse_red_flags(
        "RF-K2.I01-01. Подмена общего результата локальным.",
        indicator_id="K2.I01", rule={"format": "explicit_codes"},
    )
    assert result == [{
        "code": "RF-K2.I01-01",
        "description": "Подмена общего результата локальным.",
    }]


@pytest.mark.unit
def test_transformation_fidelity_rejects_changed_normative_content() -> None:
    source = "RF-K2.I01-01. Подмена общего результата локальным."
    corrupted = [
        {"code": "RF-K2.I01-01", "description": "RF-K2.I01-"},
        {"code": "RF-K2.I01-02", "description": "0"},
        {"code": "RF-K2.I01-03", "description": "Подмена общего результата локальным."},
    ]
    with pytest.raises(ValueError, match="changed normative content"):
        _red_flag_transformation_evidence(
            source,
            indicator_id="K2.I01",
            rule={"format": "explicit_codes"},
            red_flags=corrupted,
        )


@pytest.mark.unit
def test_numbered_and_single_red_flag_formats_are_explicitly_configured() -> None:
    numbered = _parse_red_flags(
        "1. Первый риск. 2. Второй риск.", indicator_id="K3.I01",
        rule={"format": "numbered_list", "generated_code_template": "RF-{indicator_id}-{number:02d}"},
    )
    single = _parse_red_flags(
        "Единственный риск.", indicator_id="K4.I10",
        rule={"format": "single_text", "generated_code_template": "RF-{indicator_id}-{number:02d}"},
    )
    assert [item["code"] for item in numbered] == ["RF-K3.I01-01", "RF-K3.I01-02"]
    assert single == [{"code": "RF-K4.I10-01", "description": "Единственный риск."}]


@pytest.mark.unit
def test_validator_rejects_red_flag_fragments() -> None:
    package = _package()
    indicator = package["competencies"][0]["skills"][0]["components"][0]["indicators"][0]
    indicator["red_flags"] = [{"code": "RF-K1.I01-01", "description": "0"}]
    with pytest.raises(ValueError, match="invalid description"):
        validate_package(package, normative_control=NORMATIVE_CONTROL, enforce_release_counts=False)


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
    package_dir = PACKAGE_DIR
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    declared = {item["name"]: item["sha256"] for item in manifest["agent_artifacts"]}
    actual = {
        path.relative_to(package_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (package_dir / "agents").rglob("*")
        if path.is_file()
    }
    assert declared == actual


@pytest.mark.unit
def test_repository_manifest_covers_external_control_artifacts() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    declared = {item["name"]: item["sha256"] for item in manifest["control_artifacts"]}
    actual = {
        "import-profile.json": hashlib.sha256((PACKAGE_DIR / "import-profile.json").read_bytes()).hexdigest(),
        "normative-control.json": hashlib.sha256((PACKAGE_DIR / "normative-control.json").read_bytes()).hexdigest(),
        "methodology-package-v2.schema.json": hashlib.sha256(
            Path("assessment_definitions/schemas/methodology-package-v2.schema.json").read_bytes()
        ).hexdigest(),
    }
    assert declared == actual


@pytest.mark.unit
def test_repository_contains_passing_transformation_fidelity_report() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    report_path = PACKAGE_DIR / "transformation-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    artifact = manifest["transformation_validation"]
    assert artifact == {
        "name": "transformation-report.json",
        "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "status": "PASS",
    }
    assert report["status"] == "PASS"
    assert report["indicator_count"] == 61
    assert report["red_flag_count"] == 50
    assert all(
        item["status"] == "PASS" and item["source_sha256"] == item["reconstructed_sha256"]
        for item in report["indicators"]
    )


@pytest.mark.unit
def test_repository_package_matches_normative_red_flag_counts() -> None:
    package = json.loads((PACKAGE_DIR / "methodology.json").read_text(encoding="utf-8"))
    validate_package(package, normative_control=NORMATIVE_CONTROL)


@pytest.mark.unit
def test_json_schema_exposes_red_flag_semantic_guards() -> None:
    schema = json.loads(Path("assessment_definitions/schemas/methodology-package-v2.schema.json").read_text())
    red_flag = schema["$defs"]["redFlag"]
    assert red_flag["properties"]["code"]["pattern"] == "^RF-K[1-4]\\.I[0-9]{2}-[0-9]{2}$"
    forbidden = red_flag["properties"]["description"]["not"]["anyOf"]
    assert {item["pattern"] for item in forbidden} == {"^[0-9]+$", "^RF-[A-Z0-9.]+-$"}
