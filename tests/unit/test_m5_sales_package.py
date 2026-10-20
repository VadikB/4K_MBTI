from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from Api.assessment_case_contracts import CaseVersionV3
from Api.m5_case_runtime import build_assessment_situation
from Api.m5_package import verify_package_directory
from scripts.build_m5_sales_package import OUTPUT, build_package, write_package

pytestmark = pytest.mark.unit
SOURCE_ROOT = OUTPUT / "sources"


def package() -> dict:
    return json.loads((OUTPUT / "case-package.json").read_text())


def test_repository_sales_package_has_exact_nine_pairs_and_targets():
    report = verify_package_directory(OUTPUT)
    value = package()
    assert report["case_count"] == report["assessment_situation_count"] == len(value["cases"]) == 9
    assert report["indicator_target_count"] == 55
    assert [case["case_id"] for case in value["cases"]] == [f"CASE.SPEC.{number:02d}" for number in range(1, 10)]
    assert {case["base_role"] for case in value["cases"]} == {"specialist_expert"}
    assert value["scope"]["excluded"] == ["HR", "mini_cases"]
    assert value["runtime_enabled"] is False


def test_json_native_build_is_deterministic(tmp_path):
    source_manifest = SOURCE_ROOT / "source-selection-manifest.json"
    reconstructed = tmp_path / "input" / "sources"
    reconstructed.mkdir(parents=True)
    for path in SOURCE_ROOT.glob("*.json"):
        target = reconstructed / ("manifest.json" if path == source_manifest else path.name)
        target.write_bytes(path.read_bytes())
    first, second = tmp_path / "a", tmp_path / "b"
    write_package(reconstructed, first)
    write_package(reconstructed, second)
    assert {str(path.relative_to(first)): path.read_bytes() for path in first.rglob("*") if path.is_file()} == {
        str(path.relative_to(second)): path.read_bytes() for path in second.rglob("*") if path.is_file()
    }


def test_cases_02_and_07_are_valid_without_fake_characters():
    selected = {case["case_id"]: CaseVersionV3.model_validate(case) for case in package()["cases"]}
    assert selected["CASE.SPEC.02"].characters == []
    assert selected["CASE.SPEC.07"].characters == []


def test_closed_material_is_not_in_participant_preview():
    previews = json.loads((OUTPUT / "participant-preview.json").read_text())
    package_by_id = {case["case_id"]: case for case in package()["cases"]}
    for preview in previews:
        visible = {item["material_id"] for item in preview["initial_materials"]}
        expected = {item["material_id"] for item in
                    package_by_id[preview["case_id"]]["participant_presentation"]["initial_materials"]}
        assert visible == expected


def test_participant_presentations_keep_sales_as_provenance_and_exact_start_materials():
    expected = {
        "CASE.SPEC.01": ["M01"],
        "CASE.SPEC.02": ["M01", "M06", "M02", "M03", "M04", "M05"],
        "CASE.SPEC.03": ["M01", "M02", "M03"],
        "CASE.SPEC.04": ["M01", "M02", "M03", "M04"],
        "CASE.SPEC.05": ["M01", "M02", "M03", "M04", "M05"],
        "CASE.SPEC.06": ["M01", "M02", "M03"],
        "CASE.SPEC.07": ["M01", "M02", "M03", "M04"],
        "CASE.SPEC.08": ["M01", "M02", "M03"],
        "CASE.SPEC.09": ["M01", "M02", "M03"],
    }
    assessment_ids = set()
    for case in package()["cases"]:
        presentation = case["participant_presentation"]
        assessment_ids.add(presentation["assessment_situation_id"])
        assert presentation["source"] == case["author_as_source"]
        assert all(presentation[key] for key in (
            "introduction", "initial_situation", "trigger", "assessee_position",
            "participants_and_positions", "assessee_task", "conditions_and_constraints",
        ))
        assert [item["material_id"] for item in presentation["initial_materials"]] == expected[case["case_id"]]
    assert len(assessment_ids) == 9
    assert "M04" not in expected["CASE.SPEC.03"]


def test_runtime_materializes_sales_as_and_only_declared_organization_substitution():
    case = copy.deepcopy(next(item for item in package()["cases"] if item["case_id"] == "CASE.SPEC.02"))
    policy = {
        "allowed_case_statuses": ["WORKING"],
        "required_evidence_scopes": ["case_format", "case_dialogue", "assessment_situation"],
    }
    evidence = [
        {"scope": scope, "result": "PASS", "artifact_ref": f"qa/{scope}", "checksum": "b" * 64}
        for scope in policy["required_evidence_scopes"]
    ]
    ref = {"id": "fixture", "version": "1", "checksum": "a" * 64}
    substitution = {
        "slot": "organization_name", "value": "Компания заказчика",
        "source_path": "organization_context.name", "source_checksum": "a" * 64,
    }
    situation, _ = build_assessment_situation(
        assessment_situation_id="AS.SALES.QA.02", cycle_ref=ref, session_ref=ref,
        case_value=case, profile_ref=ref,
        profile_snapshot={"base_role": case["base_role"], "organization_context": {
            "name": "Компания заказчика", "organization_name_usage_rules": "можно использовать",
        }},
        methodology_refs=[ref], substitutions=[substitution], qa_evidence=evidence, policy=policy,
    )
    payload = situation["participant_payload"]
    assert payload["assessment_situation_id"] == case["participant_presentation"]["assessment_situation_id"]
    assert "Компания заказчика" in payload["introduction"]
    assert "author_case" not in payload
    with pytest.raises(ValueError, match="ORGANIZATION_NAME_SUBSTITUTION_FORBIDDEN"):
        build_assessment_situation(
            assessment_situation_id="AS.SALES.QA.02.BLOCKED", cycle_ref=ref, session_ref=ref,
            case_value=case, profile_ref=ref,
            profile_snapshot={"base_role": case["base_role"], "organization_context": {
                "name": "Компания заказчика", "organization_name_usage_rules": "не использовать название",
            }},
            methodology_refs=[ref], substitutions=[substitution], qa_evidence=evidence, policy=policy,
        )


def test_contract_rejects_foreign_indicator_hierarchy_and_fake_source_checksum():
    case = copy.deepcopy(package()["cases"][0])
    case["indicator_targets"][0]["component_id"] = "K4.C01"
    with pytest.raises(ValidationError, match="outside Applicability"):
        CaseVersionV3.model_validate(case)
    case = copy.deepcopy(package()["cases"][0])
    case["author_case_source"]["sha256"] = "not-a-checksum"
    with pytest.raises(ValidationError):
        CaseVersionV3.model_validate(case)


def test_source_selection_rejects_changed_bytes(tmp_path):
    reconstructed = tmp_path / "input" / "sources"
    reconstructed.mkdir(parents=True)
    for path in SOURCE_ROOT.glob("*.json"):
        target = reconstructed / ("manifest.json" if path.name == "source-selection-manifest.json" else path.name)
        target.write_bytes(path.read_bytes())
    changed = reconstructed / "Case_SPEC_01_v0.3_WORKING.json"
    changed.write_bytes(changed.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum mismatch"):
        build_package(reconstructed)
