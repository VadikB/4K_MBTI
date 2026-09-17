from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_m4_context_package import (
    ORGANIZATION_REQUIRED_FIELDS,
    USER_CONTEXT_FIELDS,
    validate_contract,
)


PACKAGE_DIR = Path("assessment_definitions/contexts/competencies_4k/1.1")


@pytest.mark.unit
def test_m4_manifest_covers_every_generated_artifact() -> None:
    manifest = json.loads((PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    declared = {item["name"]: item["sha256"] for item in manifest["artifacts"]}
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in PACKAGE_DIR.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }
    assert declared == actual
    assert manifest["methodology_version"] == "1.1"
    assert manifest["status"] == "draft"
    assert manifest["source_status"] == "FROZEN"
    assert len(manifest["sources"]) == 1
    assert len(manifest["sources"][0]["sha256"]) == 64


@pytest.mark.unit
def test_m4_source_contains_all_normative_sections_and_tables() -> None:
    source = (PACKAGE_DIR / "m4_context_source.md").read_text(encoding="utf-8")
    assert all(f"## M4.{number} " in source for number in range(1, 7))
    assert "## Приложение Результаты QA" in source
    assert sum(
        line.startswith("| ") and set(line.replace("|", "").replace(" ", "")) == {"-"}
        for line in source.splitlines()
    ) == 9


@pytest.mark.unit
def test_m4_contract_preserves_context_and_privacy_rules() -> None:
    contract = json.loads((PACKAGE_DIR / "context_contract.json").read_text(encoding="utf-8"))
    validate_contract(contract)
    assert tuple(contract["organization_context"]["required_fields"]) == ORGANIZATION_REQUIRED_FIELDS
    fields = contract["user_context"]["fields"]
    assert [item["key"] for item in fields] == [key for _, key, _ in USER_CONTEXT_FIELDS]
    assert [item["key"] for item in fields if item["required"]] == ["full_name"]
    assert not any(item["allowed_for_case_generation"] for item in fields if item["category"] == "identity")
    assert contract["personalized_profile"]["role_profile_count"] == 1
    assert contract["conflict_policy"]["block_on"] == [
        "role_selection", "authority", "mandatory_organization_constraint",
    ]


@pytest.mark.unit
def test_m4_contract_rejects_identity_in_case_generation() -> None:
    contract = json.loads((PACKAGE_DIR / "context_contract.json").read_text(encoding="utf-8"))
    contract["user_context"]["fields"][0]["allowed_for_case_generation"] = True
    with pytest.raises(ValueError, match="identity data"):
        validate_contract(contract)


@pytest.mark.unit
def test_personalized_profile_schema_requires_three_versioned_sources_and_excludes_pii() -> None:
    schema = json.loads((PACKAGE_DIR / "personalized_profile.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["sources"]["required"] == [
        "organization_context", "role_profile", "user_context",
    ]
    exclusions = schema["properties"]["content"]["properties"]["user_context"]["not"]["anyOf"]
    assert {tuple(item["required"]) for item in exclusions} == {("full_name",), ("contacts",)}
