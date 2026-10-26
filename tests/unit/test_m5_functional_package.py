from __future__ import annotations

import copy
import json

import pytest

from Api.assessment_case_contracts import CaseVersionV3
from Api.m5_case_runtime import build_assessment_situation, checksum
from Api.m5_package import verify_package_directory
from Api.m5_functional_generation_service import build_input_snapshot, deterministic_checks
from Api.m5_runtime_rules import load_runtime_rule_package
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


def test_package_04_keeps_published_case_versions_and_runtime_bindings_immutable():
    previous = json.loads((OUTPUT.parent / "0.3/case-package.json").read_text(encoding="utf-8"))
    current = _package()
    assert {
        (case["case_id"], case["version"]): checksum(case) for case in current["cases"]
    } == {
        (case["case_id"], case["version"]): checksum(case) for case in previous["cases"]
    }
    runtime = OUTPUT.parent.parent / "functional-personalization-runtime/1.1.0"
    assert load_runtime_rule_package(runtime, current["cases"])["manifest"]["version"] == "1.1.0"
    for case in current["cases"]:
        stored = CaseVersionV3.model_validate(case).model_dump(exclude_unset=True)
        assert checksum(stored) == checksum(case)


def test_static_case_as_ref_uses_immutable_imported_content_checksum():
    case = copy.deepcopy(_package()["cases"][0])
    case["status"] = "FROZEN"
    case["author_case"]["Status"] = "FROZEN"
    ref = {"id": "fixture", "version": "1", "checksum": "a" * 64}
    situation, _ = build_assessment_situation(
        assessment_situation_id="AS.CASE.SPEC.01", case_value=case,
        cycle_ref=ref, session_ref=ref, profile_ref=ref,
        profile_snapshot={"base_role": case["base_role"]},
        methodology_refs=[ref], substitutions=[], qa_evidence=[],
        policy={"allowed_case_statuses": ["FROZEN"], "required_evidence_scopes": []},
    )
    assert situation["case_ref"]["checksum"] == checksum(case)
    assert checksum(CaseVersionV3.model_validate(case).model_dump()) != checksum(case)


def test_all_55_indicator_targets_preserve_author_content_exactly():
    package = _package()
    rows = 0
    for case in package["cases"]:
        compiled = {item["indicator_id"]: item for item in case["indicator_targets"]}
        for source in case["author_assessment_situation"]["IndicatorObservability"]:
            target = compiled[source["IndicatorID"]]
            assert target["author_title"] == source["Название"]
            assert target["normative_source"] == source["Нормативный источник"]
            assert target["material_refs"] == source["Материалы и факты"]
            assert target["observation_condition"] == source["Конкретное условие"]
            assert target["adaptation_constraints"] == source["Что сохранить при адаптации"]
            assert target["validity_risk"] == source["Дефект потери"]
            assert target["observable_action"] == source["Форма проявления"]
            assert target["design_opportunity"] == source["Проектная возможность"]
            assert target["actual_occurrence"] == source["Фактическое возникновение"]
            assert target["evidence_status"] == source["Evidence и IA"]
            assert target["invariant_refs"] == source["Связанные инварианты"]
            assert target["branch_condition"] is None
            assert target["event_condition"] is None
            assert target["condition_absence_reason"] == "SOURCE_HAS_NO_SEPARATE_BRANCH_OR_EVENT_PREDICATE"
            rows += 1
    assert rows == 55
    report = json.loads((OUTPUT / "content-preservation-report.json").read_text())
    assert report["result"] == "PASS"
    assert report["target_count"] == len(report["targets"]) == 55


@pytest.mark.parametrize("field", ["Конкретное условие", "Материалы и факты", "Что сохранить при адаптации"])
def test_builder_rejects_corrupted_required_indicator_content(tmp_path, field):
    source = OUTPUT.parent / "0.2/sources/functional-v0.2"
    copied = tmp_path / "source"
    for path in source.rglob("*"):
        if path.is_file():
            target = copied / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    as_path = copied / "04_as/AS_SPEC_01_FUNCTIONAL_v0.2_TEST_DRAFT.json"
    value = json.loads(as_path.read_text())
    del value["IndicatorObservability"][0][field]
    as_path.write_text(json.dumps(value, ensure_ascii=False))
    index = json.loads((copied / "Package_index_v0.2.json").read_text())
    changed = next(item for item in index["Cases"] if item["CaseID"] == "CASE.SPEC.01")
    from Api.m5_package import digest
    changed["AS"]["SHA256"] = digest(as_path.read_bytes())
    (copied / "Package_index_v0.2.json").write_text(json.dumps(index, ensure_ascii=False))
    with pytest.raises(ValueError, match="Unsupported functional IndicatorObservability schema"):
        build(copied)


@pytest.mark.parametrize("field", ["Конкретное условие", "Материалы и факты", "Что сохранить при адаптации"])
def test_pre_admission_check_rejects_changed_author_indicator_content(field):
    case = _package()["cases"][0]
    snapshot = build_input_snapshot(
        case_id=case["case_id"], profile={"base_role": "specialist_expert"},
        operation_id="a01-negative", case_value=case["author_case"],
        author_as_example=case["author_assessment_situation"],
    )
    candidate = copy.deepcopy(snapshot["author_as_example"])
    candidate["IndicatorObservability"][0][field] = [] if field == "Материалы и факты" else "искажено"
    result = deterministic_checks(snapshot, candidate)
    assert result["status"] == "FAIL"
    failed = {item["code"] for item in result["checks"] if item["result"] == "FAIL"}
    assert "indicator_author_content_preserved" in failed


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
