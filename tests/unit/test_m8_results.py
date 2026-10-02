from Api import m8_results
from Api.m8_results import _comparison, _report_content


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
