from copy import deepcopy
import json
import re

import pytest

from Api.m5_passport import compile_passport, load_m2
from Api.m5_passport_generation import M2, M3, SOURCE_MANIFEST
from scripts.build_m5_passport_bank import BATTERY_PACKAGE, BATTERY_RELEASES, BATTERY_V04_PACKAGE, build_bank


@pytest.mark.parametrize("version", BATTERY_RELEASES)
def test_battery_build_is_reproducible(tmp_path, version):
    bank, rules, _ = BATTERY_RELEASES[version]
    report = build_bank(bank / "sources", tmp_path / "cases", tmp_path / "rules", battery=True, battery_version=version)
    assert report == json.loads((bank / "verification-report.json").read_bytes())
    for output, artifact in ((tmp_path / "cases", bank), (tmp_path / "rules", rules)):
        for path in output.rglob("*"):
            if path.is_file():
                assert path.read_bytes() == (artifact / path.relative_to(output)).read_bytes()


def test_v04_rejects_the_previous_manifest(tmp_path):
    with pytest.raises(ValueError, match="M5_BATTERY_MANIFEST_CHECKSUM_MISMATCH"):
        build_bank(BATTERY_PACKAGE / "sources", tmp_path / "cases", tmp_path / "rules",
                   battery=True, battery_version="v0.4")
    old = (BATTERY_PACKAGE / "sources/manifest.json").read_bytes()
    assert old != (BATTERY_V04_PACKAGE / "sources/manifest.json").read_bytes()


@pytest.mark.parametrize(("damage", "field"), [
    ("missing", "18 Правила персонализации и ролевой адаптации"),
    ("reference", "22/Проектные условия/0/Место в сценарии→17.2/M99: ссылка не найдена"),
])
def test_battery_import_projection_reports_exact_bad_requirement(damage, field):
    package = json.loads((BATTERY_PACKAGE / "case-package.json").read_bytes())
    case = package["cases"][0]
    raw = deepcopy(case["passport"])
    if damage == "missing":
        del raw[field]
    else:
        raw["22 IndicatorIDs"]["Проектные условия"][0]["Место в сценарии"][0] = "17.2/M99"
    m2, _ = load_m2(M2, SOURCE_MANIFEST)
    with pytest.raises(ValueError, match=re.escape(f"M5_PASSPORT_REQUIREMENT_INVALID:CASE.SPEC.01:v0.6:{field}")):
        compile_passport(
            raw=raw, case_id=case["case_id"], version=case["version"], status=case["status"],
            source=case["passport_source"], m2=m2, m3=json.loads(M3.read_bytes()),
            as_contract_ref=case["as_contract_ref"], selected_base_role=case["base_role"], passport_version="1.2",
        )
