import pytest

from Api.m6_cycle_aggregation import calculate


def obs(indicator, level, n, opportunity="PRESENT"):
    return {"indicator_id": indicator, "outcome": level, "revision_id": f"r{n}",
            "assessment_situation_id": f"as{n}", "opportunity": opportunity}


def decision(indicator, *revisions, admissible=True):
    return {"indicator_id": indicator, "included_revision_ids": list(revisions),
            "numeric_admissible": admissible, "interpretation_admissible": True,
            "reason_code": "COMPARABLE" if admissible else "CONDITIONS_INCOMPARABLE",
            "rationale": "synthetic technical fixture", "conditions_refs": ["fixture"]}


def test_e8_a_uses_equal_component_weights_and_full_coverage():
    hierarchy = [{"skill_id":"TEST.S1","components":[
        {"component_id":"A","indicator_ids":["I1","I2"]}, {"component_id":"B","indicator_ids":["I3"]}]}]
    observations = [obs("I1","L1",1),obs("I1","L3",2),obs("I1","L2",3),obs("I2","L0",4),obs("I3","L3",5)]
    decisions = [decision("I1","r1","r2","r3"),decision("I2","r4"),decision("I3","r5")]
    result = calculate(hierarchy=hierarchy, observations=observations, decisions=decisions,
        planned_indicator_ids=["I1","I2","I3"], composition_version="v")
    skill = result["skill_outcomes"][0]
    assert skill["outcome"] == "full_score" and skill["score"] == {"value":2.0,"numerator":2,"denominator":1}
    coverage = result["coverage"]["full_m2"]
    assert [(coverage[x]["numerator"],coverage[x]["denominator"]) for x in coverage if x != "scope"] == [(3,3),(3,3),(3,3),(2,2),(2,2)]


def test_e8_b_preserves_zero_ie_and_incomparable_ia_as_partial():
    hierarchy=[{"skill_id":"TEST.S2","components":[{"component_id":"A","indicator_ids":["I1","I2"]},
        {"component_id":"B","indicator_ids":["I3","I4"]},{"component_id":"C","indicator_ids":["I5"]}]}]
    observations=[obs("I1","L1",1),obs("I1","L3",2),obs("I2","INSUFFICIENT_EVIDENCE",3),
        obs("I3",None,4,"ABSENT"),obs("I4","L0",5),obs("I5","L1",6),obs("I5","L3",7)]
    decisions=[decision("I1","r1","r2"),decision("I4","r5"),decision("I5","r6","r7",admissible=False)]
    result=calculate(hierarchy=hierarchy,observations=observations,decisions=decisions,
        planned_indicator_ids=["I1","I2","I3","I4","I5"],composition_version="v")
    skill=result["skill_outcomes"][0]
    assert skill["outcome"]=="partial_score" and skill["score"]=={"value":1.0,"numerator":1,"denominator":1}
    assert skill["components"][1]["score"]["value"]==0
    c=result["coverage"]["full_m2"]
    assert [(c[x]["numerator"],c[x]["denominator"]) for x in c if x!="scope"]==[(4,5),(3,5),(2,5),(2,3),(0,3)]


@pytest.mark.parametrize(("observations","decisions","outcome"), [
    ([obs("I1","L1",1),obs("I1","L3",2)],[decision("I1","r1","r2",admissible=False)],"result_without_score"),
    ([obs("I1","INSUFFICIENT_EVIDENCE",1)],[],"no_result"),
])
def test_e8_c_d_distinguish_result_without_score_from_no_result(observations,decisions,outcome):
    result=calculate(hierarchy=[{"skill_id":"S","components":[{"component_id":"C","indicator_ids":["I1"]}]}],
        observations=observations,decisions=decisions,planned_indicator_ids=["I1"],composition_version="v")
    assert result["skill_outcomes"][0]["outcome"]==outcome


def test_e8_e_full_zero_is_a_real_score():
    result=calculate(hierarchy=[{"skill_id":"S","components":[{"component_id":"C","indicator_ids":["I1","I2"]}]}],
        observations=[obs("I1","L0",1),obs("I2","L0",2)], decisions=[decision("I1","r1"),decision("I2","r2")],
        planned_indicator_ids=["I1","I2"],composition_version="v")
    assert result["skill_outcomes"][0]["outcome"]=="full_score"
    assert result["skill_outcomes"][0]["score"]["value"]==0


def test_e8_f_corrected_i5_admission_creates_new_four_thirds_result():
    hierarchy=[{"skill_id":"TEST.S2","components":[{"component_id":"A","indicator_ids":["I1","I2"]},
        {"component_id":"B","indicator_ids":["I3","I4"]},{"component_id":"C","indicator_ids":["I5"]}]}]
    observations=[obs("I1","L1",1),obs("I1","L3",2),obs("I2","INSUFFICIENT_EVIDENCE",3),
        obs("I3",None,4,"ABSENT"),obs("I4","L0",5),obs("I5","L1",6),obs("I5","L3",7)]
    result=calculate(hierarchy=hierarchy,observations=observations,
        decisions=[decision("I1","r1","r2"),decision("I4","r5"),decision("I5","r6","r7")],
        planned_indicator_ids=["I1","I2","I3","I4","I5"],composition_version="e8-f")
    skill=result["skill_outcomes"][0]
    assert skill["outcome"]=="partial_score"
    assert skill["score"]=={"value":4/3,"numerator":4,"denominator":3}
    c=result["coverage"]["full_m2"]
    assert [(c[x]["numerator"],c[x]["denominator"]) for x in c if x!="scope"]==[(4,5),(3,5),(3,5),(3,3),(1,3)]


def test_rejects_convenient_subset_of_assessments():
    with pytest.raises(ValueError,match="M6_CONVENIENT_SUBSET_FORBIDDEN"):
        calculate(hierarchy=[{"skill_id":"S","components":[{"component_id":"C","indicator_ids":["I1"]}]}],
            observations=[obs("I1","L1",1),obs("I1","L3",2)], decisions=[decision("I1","r2")],
            planned_indicator_ids=["I1"],composition_version="v")
