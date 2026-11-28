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


@pytest.mark.parametrize(("scenario_version", "review_version"), [
    ("1.10.0", "2.1.0"), ("1.10.1", "2.1.1"), ("1.10.2", "2.1.2"), ("1.10.3", "2.1.3"), ("1.10.4", "2.1.4"),
])
def test_v06_readback_binds_all_passports_and_review_conditions(scenario_version, review_version):
    from Api.cycle_execution_manifest import BATTERY_V06_SCENARIO_REFS, M5_BATTERY_PILOT_REVIEW_PACKAGES, ROOT
    from Api.m5_battery_contract import load_scenario
    from Api.m5_battery_review import build_plan
    from Api.m5_case_runtime import checksum
    from Api.m5_functional_tester import load_protocol
    from Api.m5_passport_v12 import SCENARIO_FIELDS

    bank, _, _ = BATTERY_RELEASES["v0.6"]
    cases = json.loads((bank / "case-package.json").read_bytes())["cases"]
    scenario = ROOT / BATTERY_V06_SCENARIO_REFS[scenario_version]
    review_path = ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"]
    protocol = load_protocol(review_path / "tester-protocol.json")
    m2, _ = load_m2(M2, SOURCE_MANIFEST)
    assert len(cases) == 9
    for case in cases:
        passport = json.loads((bank / case["passport_source"]["file"]).read_bytes())["Паспорт"]
        design = load_scenario(case, scenario)
        start, materials, events, finish = (passport["17 Сценарий Dialogue"][field] for field in SCENARIO_FIELDS)
        assert design["applicability"] == passport["18 Правила персонализации и ролевой адаптации"]
        assert design["start_ids"] == start["Последовательность предъявления"]
        assert [row["content"] for row in case["materials"]][:len(design["start_ids"])] == [
            next(row for row in materials if row["ID"] == item) for item in design["start_ids"]
        ]
        assert {row["id"]: row["passport"] for row in design["events"]} == {row["ID"]: row for row in events}
        assert design["finish"] == finish

        plan = build_plan(
            {"case_version": case, "battery_scenario": design,
             "refs": {"case": {"case_version_checksum": checksum(case)}}},
            protocol, review_path / "case-content-contract.json", m2,
        )
        assert plan["content_contract"]["version"] == review_version
        observed = {check["check_id"]: check for check in plan["required_checks"]
                    if check["check_id"].startswith("indicator:")}
        conditions = passport["22 IndicatorIDs"]["Проектные условия"]
        assert set(observed) == {f"indicator:{row['IndicatorID']}" for row in conditions}
        for condition in conditions:
            check = observed[f"indicator:{condition['IndicatorID']}"]
            requirement = check["requirement"].get("passport_or_protocol", check["requirement"])
            assert requirement["opportunity"] == condition["Условие возникновения"]
            assert requirement["observable_form"] == condition["Доступная форма проявления"]
            assert requirement["validity_risk"] == condition["Риск потери"]
            assert requirement["locations"] == condition["Место в сценарии"]
