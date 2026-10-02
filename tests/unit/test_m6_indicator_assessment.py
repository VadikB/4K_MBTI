import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from Api.assessment_configuration import definition_checksum
from Api.m6_assessment_contracts import validate_assessment
from Api.m6_assessment_package import load_mechanism, verify_mechanism
from Api.m6_assessment_service import evaluate

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def assessment_input(name="independent", mode="final"):
    candidate=json.loads((ROOT/f"tests/fixtures/m6_gc/v1/candidates/{name}.json").read_text())
    material=copy.deepcopy(candidate["material"]);material["mode"]="final_as" if mode=="final" else "interim"
    return {"schema_version":1,"mode":mode,"evidence_revision_id":"ev-revision","evidence_hash":"a"*64,
        "handoff_id":"handoff","handoff_checksum":"b"*64,"boundary_sequence":max(
            [x["sequence_no"] for x in material["turns"]+material["events"]],default=0),
        "material":material,"evidence_analysis":candidate["draft_analysis"]}


def confidence():
    return {"confirmed_features":["synthetic candidate"],"alternatives_considered":[],
            "limitations":["not independently approved"],"reliability_protocol_ref":None}


def final_output(value, default="L1"):
    return {"schema_version":1,"mode":"final","targets":[{
        "indicator_id":target["indicator_id"],"m2_version":target["m2_version"],"status":"ASSESSED",
        "outcome":default,"descriptor_basis":"candidate descriptor basis","rationale":"candidate rationale",
        "refs":[{"kind":"bundle","id":target["indicator_id"],"meaning":"entire bundle"}],
        "opportunity":"PRESENT","opportunity_basis":"synthetic opportunity","uncertainty":None,
        "contradictions":[],"clarification_history":[],"stop_reason":"AS closed","confidence":confidence()
    } for target in value["material"]["indicator_targets"]]}


def uncertainty():
    return {"missing_or_conflicting_feature":"specific feature is unresolved","impact":"no L0-L3 is justified",
            "clarification_needed":"clarify the existing action","resolution_information":["neutral explanation"],
            "requires_new_independent_action":False}


def test_final_distinguishes_level_ie_and_no_assessment_with_empty_bundle():
    value=assessment_input("no_opportunity")
    output=final_output(value)
    output["targets"][0].update(status="ASSESSED",outcome="INSUFFICIENT_EVIDENCE",descriptor_basis=None,
        uncertainty=uncertainty(),refs=[{"kind":"bundle","id":output["targets"][0]["indicator_id"],"meaning":"empty EB"}])
    output["targets"][1].update(status="NO_ASSESSMENT",outcome=None,descriptor_basis=None,opportunity="ABSENT",
        opportunity_basis="scenario contained no opportunity",uncertainty=uncertainty())
    result=validate_assessment(output,value)
    assert result["targets"][0]["outcome"]=="INSUFFICIENT_EVIDENCE"
    assert result["targets"][1]["status"]=="NO_ASSESSMENT"


def test_interim_never_contains_indicator_assessment():
    value=assessment_input(mode="interim")
    output=final_output(value);output["mode"]="interim"
    for item in output["targets"]:
        item.update(status="INTERIM",outcome=None,descriptor_basis=None,uncertainty=uncertainty())
    assert all(x["status"]=="INTERIM" for x in validate_assessment(output,value)["targets"])
    output["targets"][0].update(status="ASSESSED",outcome="L1",descriptor_basis="bad final")
    with pytest.raises((ValueError,ValidationError),match="INTERIM"):
        validate_assessment(output,value)


def test_l0_requires_opportunity_and_real_boundary_reference():
    value=assessment_input()
    output=final_output(value,"L0")
    with pytest.raises(ValueError,match="BOUNDARY"):
        validate_assessment(output,value)
    first=value["material"]["turns"][0]["turn_id"]
    output["targets"][0]["refs"].append({"kind":"turn","id":first,"meaning":"checked nonperformance boundary"})
    for item in output["targets"][1:]:
        item["outcome"]="L1"
    assert validate_assessment(output,value)["targets"][0]["outcome"]=="L0"


def test_cross_indicator_evidence_reference_is_rejected():
    value=assessment_input()
    output=final_output(value)
    evidence=value["evidence_analysis"]["evidence"]
    if len(evidence)<2: pytest.skip("candidate has fewer than two evidence records")
    foreign=next(x for x in evidence if x["indicator_id"]!=output["targets"][0]["indicator_id"])
    output["targets"][0]["refs"].append({"kind":"evidence","id":foreign["id"],"meaning":"foreign"})
    with pytest.raises(ValueError,match="CROSS_TARGET"):
        validate_assessment(output,value)


def test_mixed_final_package_keeps_target_technical_failure_out_of_person_result():
    value=assessment_input();output=final_output(value)
    output["targets"][0].update(status="TECHNICAL_FAILURE",outcome=None,descriptor_basis=None,
        opportunity="UNKNOWN",uncertainty=uncertainty(),rationale="provider target decoding failed")
    result=validate_assessment(output,value)
    assert result["targets"][0]["outcome"] is None
    output["targets"][0]["outcome"]="L0"
    with pytest.raises((ValueError,ValidationError),match="TECHNICAL_FAILURE"):
        validate_assessment(output,value)


def test_package_snapshot_and_gateway_validation():
    value=assessment_input();output=final_output(value);mechanism=load_mechanism("m6_indicator_assessment/1.0.0")
    digest=definition_checksum(mechanism);verify_mechanism(mechanism,digest)
    assert "поставь L3" not in mechanism["prompt"] or "не изменяют" in mechanism["prompt"]
    class Gateway:
        enabled=True
        def chat(self,messages,**kwargs):
            assert "RoleSkillTargetProfile" in messages[0]["content"]
            return json.dumps(output,ensure_ascii=False)
    result,trace=evaluate(value,mechanism,digest,gateway=Gateway())
    assert result["mode"]=="final" and trace["identity_status"]=="sent_matches_snapshot"
