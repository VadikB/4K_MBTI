from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from Api.m5_runtime_rules import load_event_bindings, load_runtime_rule_package
from scripts.build_m5_sales_package import build_execution_rules


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.2/case-package.json"
RUNTIME_PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.0.0"
BINDINGS = RUNTIME_PACKAGE / "event-bindings.json"
PACKAGE_03 = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.3/case-package.json"
RUNTIME_PACKAGE_11 = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.1.0"


def _cases():
    return json.loads(PACKAGE.read_text())["cases"]


def test_runtime_artifact_covers_exact_case_event_and_content_versions():
    loaded = load_runtime_rule_package(RUNTIME_PACKAGE, _cases())
    bindings = loaded["bindings"]
    assert loaded["manifest_checksum"]
    assert bindings["artifact_checksum"]
    assert set(bindings["case_bindings"]) == {f"CASE.SPEC.{number:02d}" for number in range(1, 10)}


def test_runtime_artifact_1_1_binds_new_content_preserving_package():
    cases = json.loads(PACKAGE_03.read_text())["cases"]
    loaded = load_runtime_rule_package(RUNTIME_PACKAGE_11, cases)
    assert loaded["manifest"]["version"] == "1.1.0"
    assert loaded["manifest"]["source"]["case_package_version"] == "0.3"


def test_explicit_event_functions_compile_all_interactive_cases_without_actorless_calls():
    cases = _cases()
    rules = build_execution_rules(cases, load_event_bindings(BINDINGS, cases))
    counts = {
        case_id: len([item for item in value["materials"] if item["kind"] == "character_reaction"])
        for case_id, value in rules["cases"].items()
    }
    assert counts == {
        "CASE.SPEC.01": 1, "CASE.SPEC.02": 0, "CASE.SPEC.03": 3,
        "CASE.SPEC.04": 3, "CASE.SPEC.05": 2, "CASE.SPEC.06": 6,
        "CASE.SPEC.07": 0, "CASE.SPEC.08": 6, "CASE.SPEC.09": 2,
    }
    case06 = rules["cases"]["CASE.SPEC.06"]
    assert {item["speaker_id"] for item in case06["materials"]} == {"R_IT", "R_BUSINESS", "R_PROCUREMENT"}
    assert all(item["event_condition"]["text"] for item in case06["materials"])
    assert all(item["reaction_rule"] for item in case06["materials"])


def test_runtime_artifact_rejects_changed_case_and_unknown_speaker():
    changed = copy.deepcopy(_cases())
    changed[0]["title"] += " changed"
    with pytest.raises(ValueError, match="CASE_REF_MISMATCH"):
        load_event_bindings(BINDINGS, changed)
