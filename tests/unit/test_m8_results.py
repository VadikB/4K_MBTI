from Api import m8_results
from Api.m8_results import _comparison, _partial_result_projection, _report_content
from Api.m8_report_package import load_package


def skill(outcome="full_score", score=None):
    value = {"skill_id": "K1", "skill_name": "Очень длинное название навыка", "competency_id": "K1",
             "competency_name": "Коммуникация", "outcome": outcome, "components": [],
             "comparison": {"status": "NO_TARGET_REQUIREMENT"}}
    if score is not None:
        value["score"] = score
    return value


def results(outcome="full_score", score=None):
    return {"id": "results", "revision_id": "revision", "revision_no": 1, "cycle_id": "cycle",
            "results": {"profile_ref": {}, "role_ref": {}, "goal": None, "time": {}, "collection": {},
                "sessions": [], "assessment_situations": [], "assessed_skill_profile": [skill(outcome, score)],
                "competencies": [{"competency_id": "K1", "competency_name": "Коммуникация", "skill_ids": ["K1"], "score": None}],
                "coverage": {"full_m2": {}, "cycle_plan": {}}, "confidence": {"kind": "qualitative"},
                "reliability": {"status": "not_verified"}, "limitations": ["Ограничение"], "target_profile": None,
                "composition_checksum": "a" * 64, "c46_ref": {}, "c56_ref": {}, "sources": {}, "algorithm": {}}}


def test_target_comparison_never_derives_level_from_score():
    assert _comparison(skill(score={"value": 2.4}), {"skill_id": "K1", "target_level": "L2"}) == {
        "status": "NOT_COMPARABLE", "target_level": "L2", "reason": "NORMATIVE_SKILL_LEVEL_NOT_AVAILABLE"}
    assert _comparison(skill("no_result"), {"skill_id": "K1", "target_level": "L2"})["status"] == "NO_SKILL_RESULT"
    assert _comparison(skill(), None)["status"] == "NO_TARGET_REQUIREMENT"


def test_c67_preserves_zero_and_no_result_without_recommendations():
    zero = _report_content(results(score={"value": 0.0, "numerator": 0, "denominator": 1}), "assessee", None)
    missing = _report_content(results("no_result"), "methodology_qa", None)
    assert zero["skills"][0]["score"]["value"] == 0.0
    assert missing["skills"][0]["outcome"] == "no_result" and "score" not in missing["skills"][0]
    assert zero["recommendations"] == [] and missing["recommendations"] == []
    assert zero["competencies"][0]["score"] is None


def test_three_audiences_share_facts_and_differ_only_in_disclosure():
    values = [_report_content(results("partial_score", {"value": 1.0, "numerator": 1, "denominator": 1}), audience, None)
              for audience in ("assessee", "customer", "methodology_qa")]
    assert {x["skills"][0]["score"]["value"] for x in values} == {1.0}
    assert {x["coverage"].__repr__() for x in values} == {values[0]["coverage"].__repr__()}
    assert [x["disclosure"] for x in values] == ["personal", "summary_with_coverage", "full"]


def test_recommendation_failure_keeps_base_c67_available(monkeypatch):
    monkeypatch.setattr(m8_results, "generate_recommendations", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("broken")))
    report = _report_content(results(), "assessee", None)
    assert report["skills"]
    assert report["recommendations"] == []
    assert report["recommendation_generation"]["status"] == "failed"
    assert report["recommendation_notices"][0]["kind"] == "GENERATION_FAILURE"


def test_partial_result_uses_as_lifecycle_not_message_count_and_keeps_reasons_separate():
    cut = lambda numerator, denominator: {"numerator":numerator,"denominator":denominator,"ratio":numerator/denominator}
    c46 = {"payload_json":{"collection":{"reason":"time_budget"},"plan":{
        "revision_id":"plan-a","untraversed_route":[{"case_id":f"c{i}"} for i in range(5)]}}}
    c56 = {"cycle_context":{"assessment_situations":[
        {"status":"closed","handoff_id":"h1"}, {"status":"closed","handoff_id":"h2"},
        {"status":"closed","handoff_id":None}]},
        "coverage":{"full_m2":{"indicator_assessments":cut(2,4)},
                    "cycle_plan":{"indicator_assessments":cut(2,3)}},
        "limitations":["context fixture"]}
    result = _partial_result_projection(c46, c56, {"status":"completed"}, load_package()["template"])
    assert result["progress"] == {"completed":2,"planned":5,"presented":3,"interrupted":1,
        "not_presented":2,"formula":"completed AS with final handoff / immutable accepted plan route"}
    assert {x["code"] for x in result["limitation_reasons"]} == {
        "plan_scope","collection_incomplete","observation_missing","context_limited"}
    assert "technical_failure" not in {x["code"] for x in result["limitation_reasons"]}


def test_technical_failure_is_not_collection_incomplete():
    cut = {"numerator":1,"denominator":1,"ratio":1.0}
    c46 = {"payload_json":{"collection":{"reason":"plan_finished"},"plan":{
        "revision_id":"plan","untraversed_route":[{"case_id":"c1"}]}}}
    c56 = {"cycle_context":{"assessment_situations":[{"status":"closed","handoff_id":"h1"}]},
           "coverage":{"full_m2":{"indicator_assessments":cut},"cycle_plan":{"indicator_assessments":cut}},
           "limitations":[]}
    result = _partial_result_projection(c46, c56, {"status":"failed"}, load_package()["template"])
    assert [x["code"] for x in result["limitation_reasons"]] == ["technical_failure"]
