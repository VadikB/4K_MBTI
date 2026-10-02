from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from Api.assessment_case_contracts import CaseVersionV2
from Api.m5_case_runtime import build_assessment_situation, build_c34_envelope, checksum
from scripts.build_m5_case_package import OUTPUT, build_package, verify_directory, write_package

pytestmark = pytest.mark.unit
SOURCE = OUTPUT / "sources/M5_Командное_обсуждение_5_комплексных_кейсов_v0_1_WORKING.xlsx"


def package():
    return json.loads((OUTPUT / "case-package.json").read_text())


def refs():
    return {"id": "fixture", "version": "1", "checksum": "a" * 64}


def evidence(result="PASS"):
    return [{"scope": scope, "result": result, "artifact_ref": f"qa/{scope}.json", "checksum": "b" * 64}
            for scope in ("case_format", "case_dialogue", "assessment_situation")]


def test_repository_package_has_five_cases_and_exact_multi_indicator_targets():
    report = verify_directory(OUTPUT)
    value = package()
    assert report["case_count"] == len(value["cases"]) == 5
    assert report["indicator_target_count"] == 43
    assert all(len(CaseVersionV2.model_validate(x).indicator_targets) > 1 for x in value["cases"])
    assert {x["case_id"] for x in value["cases"]} == {f"CASE-TDISC-0{i}" for i in range(1, 6)}
    assert all(x["status"] == "WORKING" for x in value["cases"])
    assert value["runtime_enabled"] is False


def test_proposals_are_not_imported_as_cases():
    value = package()
    assert len(value["excluded_proposals"]) == 10
    assert all(x["Status"] == "PROPOSAL" for x in value["excluded_proposals"])
    assert not ({x["IdeaID"] for x in value["excluded_proposals"]} & {x["case_id"] for x in value["cases"]})


def test_source_import_is_deterministic(tmp_path):
    imported, source = build_package(SOURCE)
    assert imported == package()
    assert source["source_sha256"] == "06f528d9c9e34c4748979e4d787ce0e069990e9f4051953e395ecb3f454e53fa"
    first, second = tmp_path / "a", tmp_path / "b"
    write_package(SOURCE, first)
    write_package(SOURCE, second)
    assert {str(p.relative_to(first)): p.read_bytes() for p in first.rglob("*") if p.is_file()} == {
        str(p.relative_to(second)): p.read_bytes() for p in second.rglob("*") if p.is_file()}


def test_contract_rejects_changed_target_set_and_duplicate_indicator():
    case = copy.deepcopy(package()["cases"][0])
    case["indicator_targets"].pop()
    with pytest.raises(ValidationError, match="Passport IndicatorIDs"):
        CaseVersionV2.model_validate(case)
    case = copy.deepcopy(package()["cases"][0])
    case["indicator_targets"].append(copy.deepcopy(case["indicator_targets"][0]))
    with pytest.raises(ValidationError, match="Duplicate Case IndicatorID"):
        CaseVersionV2.model_validate(case)


def test_working_case_is_visible_for_qa_but_not_admitted():
    case = package()["cases"][0]
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    situation, execution = build_assessment_situation(
        assessment_situation_id="AS.QA.001", cycle_ref=refs(), session_ref=refs(), case_value=case, profile_ref=refs(),
        profile_snapshot={"base_role": case["base_role"]}, methodology_refs=[refs()],
        substitutions=[], qa_evidence=evidence(), policy=policy,
    )
    assert situation["indicator_targets"] == case["indicator_targets"]
    assert execution["indicator_targets"] == case["indicator_targets"]
    assert situation["admission"]["code"] == "CASE_NOT_ADMITTED"
    with pytest.raises(ValueError, match="AS_NOT_ADMITTED"):
        build_c34_envelope(situation)


def test_c34_contains_same_exact_targets_after_admission():
    case = copy.deepcopy(package()["cases"][0])
    case["status"] = "FROZEN"
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    situation, _ = build_assessment_situation(
        assessment_situation_id="AS.FROZEN.001", cycle_ref=refs(), session_ref=refs(), case_value=case, profile_ref=refs(),
        profile_snapshot={"base_role": case["base_role"]}, methodology_refs=[refs()],
        substitutions=[], qa_evidence=evidence(), policy=policy,
    )
    envelope = build_c34_envelope(situation)
    assert envelope["indicator_ids"] == [x["indicator_id"] for x in case["indicator_targets"]]
    assert envelope["participant_payload_checksum"] == checksum(situation["participant_payload"])


def test_case04_unresolved_decision_blocks_even_a_frozen_case():
    case = copy.deepcopy(next(x for x in package()["cases"] if x["case_id"] == "CASE-TDISC-04"))
    case["status"] = "FROZEN"
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    situation, _ = build_assessment_situation(
        assessment_situation_id="AS.CASE04", cycle_ref=refs(), session_ref=refs(), case_value=case, profile_ref=refs(),
        profile_snapshot={"base_role": case["base_role"]}, methodology_refs=[refs()],
        substitutions=[], qa_evidence=evidence(), policy=policy,
    )
    assert situation["admission"]["code"] == "CASE_NOT_ADMITTED"
    assert any(x.startswith("unresolved:") for x in situation["admission"]["reasons"])
