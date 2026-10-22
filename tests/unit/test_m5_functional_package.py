from __future__ import annotations

import copy
import json

import pytest

from Api.assessment_case_contracts import CaseVersionV3
from Api.m5_package import verify_package_directory
from scripts.build_m5_functional_package import OUTPUT, build

pytestmark = pytest.mark.unit


def _package() -> dict:
    return json.loads((OUTPUT / "case-package.json").read_text(encoding="utf-8"))


def test_functional_package_keeps_all_nine_current_passports_and_full_fields():
    report = verify_package_directory(OUTPUT)
    package = _package()
    assert report["case_count"] == 9
    assert report["indicator_target_count"] == 55
    assert package["runtime_enabled"] is False
    assert [case["version"] for case in package["cases"]] == [
        "v0.5", "v0.6", "v0.4", "v0.5", "v0.5", "v0.4", "v0.4", "v0.4", "v0.4",
    ]
    required = {f"{number} " for number in (16, 17, 18, 19, 22)}
    for case in package["cases"]:
        CaseVersionV3.model_validate(case)
        keys = set(case["passport"])
        assert all(any(key.startswith(prefix) for key in keys) for prefix in required)


def test_functional_character_counts_and_actorless_cases_are_exact():
    package = _package()
    assert [len(case["characters"]) for case in package["cases"]] == [1, 0, 3, 1, 1, 3, 0, 2, 1]
    assert not package["cases"][1]["characters"]
    assert not package["cases"][6]["characters"]


def test_functional_sources_and_author_event_references_are_resolvable():
    package = _package()
    root = OUTPUT
    for case in package["cases"]:
        for ref in (case["author_case_source"], case["author_as_source"]):
            assert (root / ref["file"]).is_file()
        author_event_ids = {item["EventID"] for item in case["author_assessment_situation"]["События"]}
        assert author_event_ids == {item["step_id"] for item in case["scenario"]}


def test_functional_qa_plans_are_executable_inventory_not_synthetic_pass():
    source = OUTPUT / "sources/functional-v0.2"
    profiles = json.loads((source / "07_generation/Professional_profile_test_matrix_v0.2.json").read_text())
    negatives = json.loads((source / "08_qa/Negative_examples_v0.2.json").read_text())
    scenarios = json.loads((source / "08_qa/Scenario_regression_plan_v0.2.json").read_text())
    assert len(profiles) == len(negatives) == 27
    assert len(scenarios) == 34
    assert {item["Фактическая генерация"] for item in profiles} == {"NOT_RUN"}
    assert {item["Запуск валидатора продукта"] for item in negatives} == {"NOT_RUN"}
    assert {item["Результат"] for item in scenarios} == {"NOT_RUN"}


def test_builder_rejects_missing_significant_events_field(tmp_path):
    source = OUTPUT / "sources/functional-v0.2"
    copied = tmp_path / "source"
    for path in source.rglob("*"):
        if path.is_file():
            target = copied / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    case_path = copied / "04_as/AS_SPEC_01_FUNCTIONAL_v0.2_TEST_DRAFT.json"
    value = json.loads(case_path.read_text())
    del value["События"]
    case_path.write_text(json.dumps(value, ensure_ascii=False))
    index = json.loads((copied / "Package_index_v0.2.json").read_text())
    changed = next(item for item in index["Cases"] if item["CaseID"] == "CASE.SPEC.01")
    from Api.m5_package import digest
    changed["AS"]["SHA256"] = digest(case_path.read_bytes())
    (copied / "Package_index_v0.2.json").write_text(json.dumps(index, ensure_ascii=False))
    with pytest.raises(ValueError, match="scenario/events field is absent"):
        build(copied)


def test_case02_keeps_non_monetary_advantage_and_no_forced_correct_option():
    case = copy.deepcopy(_package()["cases"][1])
    text = json.dumps(case["author_assessment_situation"], ensure_ascii=False).lower()
    assert "отклик" in text
    assert "цена" not in json.dumps(case["passport"]["16 Инвариантное ядро"], ensure_ascii=False).lower()
    assert "не доказывает" in text
