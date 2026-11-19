from __future__ import annotations

import json
from shutil import copytree

import pytest

from Api.assessment_case_contracts import validate_case_version
from Api import m5_case_type_catalog
from Api.m5_package import digest, verify_package_directory
from Api.m5_storage import import_package_directory
from scripts.build_m5_case_package import OUTPUT as CASE_V2_PACKAGE
from scripts.build_m5_functional_package import OUTPUT as CASE_V3_PACKAGE


@pytest.mark.unit
def test_case_type_catalog_matches_the_frozen_source():
    catalog = m5_case_type_catalog.load_case_type_catalog()
    assert catalog.ids == {f"CT{index:02d}" for index in range(1, 21)}
    assert catalog.ref.model_dump() == {
        "id": "m5-case-type-catalog", "version": "1.0",
        "checksum": "d748e390933a45eabca44f305027f757c7568a6c4ef343ee5bc7f104c210b7c0",
    }


@pytest.mark.unit
def test_rehashing_a_replacement_cannot_reuse_the_frozen_catalog_version(tmp_path, monkeypatch):
    directory = copytree(m5_case_type_catalog.CATALOG_DIR, tmp_path / "catalog")
    monkeypatch.setattr(m5_case_type_catalog, "CATALOG_DIR", directory)
    source = directory / m5_case_type_catalog.SOURCE_NAME
    source.write_bytes(b"replacement")
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["artifacts"][0]["sha256"] = digest(source.read_bytes())
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="M5_CASE_TYPE_CATALOG_MANIFEST_INVALID: m5-case-type-catalog@1.0"):
        m5_case_type_catalog.load_case_type_catalog()


@pytest.mark.unit
@pytest.mark.parametrize("source", [CASE_V2_PACKAGE, CASE_V3_PACKAGE], ids=["v2", "v3"])
def test_bank_rejects_syntactically_valid_unknown_case_type(source, tmp_path):
    directory = copytree(source, tmp_path / "bank")
    package_path = directory / "case-package.json"
    manifest_path = directory / "manifest.json"
    package = json.loads(package_path.read_bytes())
    manifest = json.loads(manifest_path.read_bytes())
    case = package["cases"][0]
    case["case_type_ids"][0] = "CT99"
    assert validate_case_version(case).case_type_ids[0] == "CT99"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    next(item for item in manifest["artifacts"] if item["name"] == package_path.name)["sha256"] = digest(
        package_path.read_bytes()
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    class NoDatabaseAccess:
        def execute(self, *_args):
            pytest.fail("CaseTypeID must be checked before accessing the database")

    pattern = rf"M5_CASE_TYPE_UNKNOWN: CT99 at /cases/0/case_type_ids/0.*{case['case_id']}.*m5-case-type-catalog@1.0"
    with pytest.raises(ValueError, match=pattern):
        verify_package_directory(directory)
    with pytest.raises(ValueError, match=pattern):
        import_package_directory(NoDatabaseAccess(), directory)
