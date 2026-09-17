from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_m3_base_roles import (
    CARD_FIELDS, DESCRIPTION_FIELDS, ROLE_CODES, VALIDITY_CHECKS,
    validate_package, validate_role_profile_contract,
)


PACKAGE_DIR = Path(__file__).resolve().parents[2] / "assessment_definitions/role_profiles/competencies_4k/1.1"


def test_m3_package_contains_all_six_complete_base_roles() -> None:
    package = json.loads((PACKAGE_DIR / "base_roles.json").read_text(encoding="utf-8"))
    validate_package(package)
    assert tuple(role["code"] for role in package["base_roles"]) == ROLE_CODES
    assert all(len(role["description"]) == len(DESCRIPTION_FIELDS) and len(role["card"]) == len(CARD_FIELDS) for role in package["base_roles"])
    assert all("\n" in role["card"]["typical_tasks"] for role in package["base_roles"])


def test_m3_manifest_matches_package_and_declares_two_sources() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    content = (PACKAGE_DIR / "base_roles.json").read_bytes()
    assert manifest["artifact"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert {item["name"] for item in manifest["normative_artifacts"]} == {
        "base_roles_source.md", "role_profile_source.md", "role_profile_contract.json",
    }
    for item in manifest["normative_artifacts"]:
        assert hashlib.sha256((PACKAGE_DIR / item["name"]).read_bytes()).hexdigest() == item["sha256"]
    assert len(manifest["sources"]) == 2
    assert all(len(source["sha256"]) == 64 for source in manifest["sources"])


def test_m3_package_rejects_missing_normative_field() -> None:
    package = json.loads((PACKAGE_DIR / "base_roles.json").read_text(encoding="utf-8"))
    del package["base_roles"][0]["card"]["independent_authority"]
    with pytest.raises(ValueError, match="Incomplete card"):
        validate_package(package)


def test_m3_role_profile_contract_covers_fields_and_validity_rules() -> None:
    contract = json.loads((PACKAGE_DIR / "role_profile_contract.json").read_text(encoding="utf-8"))
    validate_role_profile_contract(contract)
    assert [item["key"] for item in contract["description_fields"]] == [key for _, key in DESCRIPTION_FIELDS]
    assert [item["key"] for item in contract["card_fields"]] == [key for _, key in CARD_FIELDS]
    assert tuple(item["name"] for item in contract["role_validity_checks"]) == VALIDITY_CHECKS
    source = (PACKAGE_DIR / "role_profile_source.md").read_text(encoding="utf-8")
    assert all(f"## M3.{number}." in source for number in range(1, 10))
    assert "## Appendix A. Зафиксированный baseline M3" in source
    base_source = (PACKAGE_DIR / "base_roles_source.md").read_text(encoding="utf-8")
    assert all(role["description"]["name"] in base_source for role in json.loads((PACKAGE_DIR / "base_roles.json").read_text(encoding="utf-8"))["base_roles"])


def test_m3_contract_rejects_missing_role_validity_check() -> None:
    contract = json.loads((PACKAGE_DIR / "role_profile_contract.json").read_text(encoding="utf-8"))
    contract["role_validity_checks"].pop()
    with pytest.raises(ValueError, match="nine role-validity checks"):
        validate_role_profile_contract(contract)
