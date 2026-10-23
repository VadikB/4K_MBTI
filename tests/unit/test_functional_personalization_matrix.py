from __future__ import annotations

import copy

import pytest

from Api.m5_functional_personalization import extract_candidate_as

from scripts.run_functional_personalization_matrix import (
    build_synthetic_profile,
    deterministic_checks,
    load_inputs,
    read_json,
    report_path,
    SOURCE,
)
from Api.m5_functional_tester import aggregate, build_applicability_plan, normalize_results

pytestmark = pytest.mark.unit


def test_external_smoke_evidence_path_does_not_break_summary(tmp_path):
    external = tmp_path / "generation.json"
    assert report_path(external) == str(external)


def _row():
    return read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")[3]


def test_synthetic_profile_is_product_shaped_and_traceable():
    profile = build_synthetic_profile(_row())
    assert profile["synthetic_test_data"] is True
    assert profile["base_role"] == "specialist_expert"
    assert set(profile) >= {"organization_context", "role_profile", "user_context", "checksum"}
    assert profile["source"]["test_id"] == "PROFILE.02.1"


def test_deterministic_checks_accept_author_example_contract():
    inputs = load_inputs(_row())
    result = deterministic_checks(inputs, inputs["author_as_example"])
    assert result["status"] == "PASS"


def test_deterministic_checks_reject_changed_targets_and_broken_material_reference():
    inputs = load_inputs(_row())
    candidate = copy.deepcopy(inputs["author_as_example"])
    candidate["IndicatorIDs"] = ["K9.INVALID"]
    candidate["Стартовые MaterialIDs"].append("MISSING")
    result = deterministic_checks(inputs, candidate)
    assert result["status"] == "FAIL"
    failed = {item["code"] for item in result["checks"] if item["result"] == "FAIL"}
    assert {"indicator_targets", "start_material_refs"} <= failed


def _deterministic(passed=True):
    return {"status": "PASS" if passed else "FAIL", "checks": [
        {"code": "contract", "result": "PASS" if passed else "FAIL"}
    ]}


def _check(status="PASS", *, protected=True, mandatory=True, severity=None):
    findings = [] if severity is None else [{"code": "KNOWN", "severity": severity, "reason": "known"}]
    return {"check_id": "known", "category": "invariant" if protected else "presentation_quality",
            "mandatory": mandatory, "protected": protected, "status": status, "findings": findings}


@pytest.mark.parametrize(("checks", "expected", "admitted"), [
    ([_check("FAIL", severity="blocking")], "FAIL", False),
    ([_check("FAIL", protected=False, severity="non_blocking")], "PASS_WITH_WARNINGS", True),
    ([_check("NOT_APPLICABLE", mandatory=False) | {"basis": "not this Case"}], "PASS", True),
    ([_check("NOT_RUN")], "INCOMPLETE", False),
    ([_check("TECHNICAL_ERROR")], "INCOMPLETE", False),
    ([_check("FAIL", protected=True, severity="non_blocking")], "REVIEW_REQUIRED", False),
])
def test_tester_v2_aggregation_known_combinations(checks, expected, admitted):
    result = aggregate(_deterministic(), checks)
    assert result["status"] == expected
    assert result["admitted_for_participant"] is admitted


def test_deterministic_failure_always_blocks_admission():
    result = aggregate(_deterministic(False), [_check("PASS")])
    assert result["status"] == "FAIL"
    assert result["admitted_for_participant"] is False


def test_declared_deterministic_failure_without_checks_blocks_admission():
    result = aggregate({"status": "FAIL", "checks": []}, [_check("PASS")])
    assert result["status"] == "FAIL"
    assert result["admitted_for_participant"] is False


def test_empty_deterministic_protocol_is_incomplete_and_not_admitted():
    result = aggregate({"status": "PASS", "checks": []}, [_check("PASS")])
    assert result["status"] == "INCOMPLETE"
    assert result["admitted_for_participant"] is False
    assert result["deterministic_protocol_errors"][0]["code"] == "DETERMINISTIC_PROTOCOL_EMPTY"


def test_blocking_finding_cannot_hide_under_declared_pass():
    result = aggregate(_deterministic(), [_check("PASS", severity="blocking")])
    assert result["status"] == "FAIL"
    assert result["admitted_for_participant"] is False


def test_unknown_finding_severity_is_incomplete_and_not_admitted():
    result = aggregate(_deterministic(), [_check("PASS", severity="unknown")])
    assert result["status"] == "INCOMPLETE"
    assert result["admitted_for_participant"] is False


def test_known_response_envelope_is_removed_without_changing_as():
    candidate = {"CaseID": "CASE.SPEC.01", "Материалы": []}
    extracted, depth = extract_candidate_as({"profile": {}, "candidate_as": {"candidate_as": candidate}})
    assert extracted == candidate
    assert depth == 2
    untouched, depth = extract_candidate_as({"candidate_as": candidate, "unexpected": True})
    assert untouched == {"candidate_as": candidate, "unexpected": True}
    assert depth == 0


def test_case_specific_applicability_is_derived_and_llm_cannot_override_it():
    row = _row()
    case02 = load_inputs(row)["case"]
    plan02 = build_applicability_plan(case02)
    assert "case02.attractive_feature" in {item["check_id"] for item in plan02["required_checks"]}
    case03_row = read_json(SOURCE / "07_generation/Professional_profile_test_matrix_v0.2.json")[6]
    plan03 = build_applicability_plan(load_inputs(case03_row)["case"])
    assert "case02.attractive_feature" not in {item["check_id"] for item in plan03["required_checks"]}
    excluded = next(item for item in plan03["not_applicable_checks"] if item["check_id"] == "case02.attractive_feature")
    assert excluded["status"] == "NOT_APPLICABLE" and excluded["basis"]
    assert excluded["mandatory"] is False
    all_pass = [{"check_id": item["check_id"], "status": "PASS", "reason": "ok", "findings": []}
                for item in plan03["required_checks"]]
    assert aggregate(_deterministic(), normalize_results(plan03, all_pass))["status"] == "PASS"
    raw = [{"check_id": item["check_id"], "status": "PASS", "reason": "ok", "findings": []}
           for item in plan02["required_checks"]]
    raw[-1]["status"] = "NOT_APPLICABLE"
    normalized = normalize_results(plan02, raw)
    forced = next(item for item in normalized if item["check_id"] == "case02.attractive_feature")
    assert forced["status"] == "TECHNICAL_ERROR"
