from __future__ import annotations

import copy

import pytest

from scripts.run_functional_personalization_matrix import (
    build_synthetic_profile,
    deterministic_checks,
    load_inputs,
    read_json,
    SOURCE,
)

pytestmark = pytest.mark.unit


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
