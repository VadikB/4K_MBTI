from copy import deepcopy

import pytest

from Api.m5_passport_generation import compact_review_payload


@pytest.fixture
def review():
    case_id = "CASE.SPEC.02"
    check = {"check_id": "common.professional_consistency", "requirement": {
        "passport_or_protocol": "Требование паспорта", "case_content": "Условие профессиональной согласованности",
    }}
    payload = {
        "case": {"CaseID": case_id, "Version": "v0.6"},
        "candidate_as": {"CaseID": case_id, "Материалы": [{"MaterialID": "P00", "Текст": "Условие AS"}]},
        "case_content_contract": {
            "case_id": case_id, "version": "1.0.0", "id": "m5-functional-passport-content",
            "requirements": {
                check["check_id"]: check["requirement"]["case_content"],
                "another": check["requirement"]["case_content"],
                "third": "Требование другого пакета проверок",
            },
        },
        "applicability_plan": {"required_checks": [check]},
    }
    return payload, check


def test_exact_inline_requirement_replaces_only_duplicate_for_this_id(review):
    payload, check = review
    original = deepcopy(payload)
    compact = compact_review_payload(payload, [check])
    assert payload == original
    assert compact["candidate_as"] is payload["candidate_as"]
    assert compact["applicability_plan"]["required_checks"] == original["applicability_plan"]["required_checks"]
    expected = original["case_content_contract"]
    expected["requirements"].pop(check["check_id"])
    assert compact["case_content_contract"] == expected
    assert list(compact["case_content_contract"]["requirements"]) == ["another", "third"]


@pytest.mark.parametrize("shape", [
    "no_contract", "other_case", "version_missing", "no_copy", "similar_text",
    "different_id", "incomplete_requirement", "incomplete_check",
])
def test_inexact_or_incomplete_review_preserves_the_original_payload(review, shape):
    payload, check = review
    if shape == "no_contract":
        payload.pop("case_content_contract")
    elif shape == "other_case":
        payload["case_content_contract"]["case_id"] = "CASE.SPEC.01"
    elif shape == "version_missing":
        payload["case_content_contract"].pop("version")
    elif shape == "no_copy":
        payload["case_content_contract"]["requirements"].pop(check["check_id"])
    elif shape == "similar_text":
        check["requirement"]["case_content"] += "."
    elif shape == "different_id":
        check["check_id"] = "different"
    elif shape == "incomplete_requirement":
        check["requirement"].pop("passport_or_protocol")
    elif shape == "incomplete_check":
        check.pop("check_id")
    assert compact_review_payload(payload, [check]) is payload
