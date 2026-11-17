from Api import m8_results
from Api.m8_results import _comparison, _coverage_context, _partial_result_projection, _report_content
from Api.m8_report_package import load_package
from Api.m8_report_access import public_projection


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


def test_description_failure_keeps_base_c67_available():
    report = _report_content(results(), "assessee", None)
    assert report["skills"]
    assert report["recommendations"] == []
    assert report["descriptive"]["status"] == "failed"
    assert report["descriptive"]["failure_reason"] == "DESCRIPTION_GENERATION_FAILED"


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
        "plan_scope","collection_incomplete","observation_missing"}
    assert "technical_failure" not in {x["code"] for x in result["limitation_reasons"]}
    assert result["plan_completed"] is False


def test_technical_failure_is_not_collection_incomplete():
    cut = {"numerator":1,"denominator":1,"ratio":1.0}
    c46 = {"payload_json":{"collection":{"reason":"plan_finished"},"plan":{
        "revision_id":"plan","untraversed_route":[{"case_id":"c1"}]}}}
    c56 = {"cycle_context":{"assessment_situations":[{"status":"closed","handoff_id":"h1"}]},
           "coverage":{"full_m2":{"indicator_assessments":cut},"cycle_plan":{"indicator_assessments":cut}},
           "limitations":[]}
    result = _partial_result_projection(c46, c56, {"status":"failed"}, load_package()["template"])
    assert [x["code"] for x in result["limitation_reasons"]] == ["technical_failure"]
    assert result["plan_completed"] is True
    assert result["is_incomplete"] is False


def test_completed_short_program_keeps_scope_limitation_without_false_incompletion():
    cut = lambda numerator, denominator: {"numerator": numerator, "denominator": denominator}
    c46 = {"payload_json": {"collection": {"reason": "plan_finished"}, "plan": {
        "revision_id": "frozen-plan", "untraversed_route": [{"case_id": str(i)} for i in range(3)]}}}
    c56 = {"cycle_context": {"assessment_situations": [
        {"status": "closed", "handoff_id": str(i)} for i in range(3)]},
        "coverage": {"full_m2": {"indicator_assessments": cut(2, 4)},
                     "cycle_plan": {"indicator_assessments": cut(2, 2)}},
        "limitations": []}
    projected = _partial_result_projection(c46, c56, {"status": "completed"}, load_package()["template"])
    assert projected["plan_completed"] is True
    assert projected["is_incomplete"] is False
    assert projected["messages"]["title"] == "Оценка завершена"
    assert [value["code"] for value in projected["limitation_reasons"]] == ["plan_scope"]
    assert projected["plan_revision_id"] == "frozen-plan"


def test_remaining_plan_relevance_uses_frozen_route_positions():
    from Api.m8_results import _skill_presentation
    c46 = {"payload_json": {"plan": {"untraversed_route": [
        {"purpose_target_ids": ["I1"]}, {"purpose_target_ids": ["I2"]},
        {"purpose_target_ids": ["I3"]}]},
        "route": {"positions": [{"position_no": 1, "state": "completed"},
                                {"position_no": 2, "state": "completed"}]}}}
    c56 = {"planned_target_set": [{"indicator_id": value} for value in ("I1", "I2", "I3")]}
    template = load_package()["template"]
    skill = {"outcome": "full_score", "components": [{"required_indicator_ids": ["I1"],
        "included_indicator_ids": ["I1"]}]}
    assert _skill_presentation(skill, c56, c46, {}, template)["remaining_plan_relevant"] is False
    skill["components"][0]["required_indicator_ids"] = ["I1", "I3"]
    assert _skill_presentation(skill, c56, c46, {}, template)["remaining_plan_relevant"] is True


def test_skill_presentation_preserves_m6_outcomes_and_explains_missing_values():
    from Api.m8_results import _skill_presentation
    template = load_package()["template"]
    c46 = {"payload_json": {"plan": {"untraversed_route": []}}}
    c56 = {"planned_target_set": [{"indicator_id": "I1"}], "coverage": {"full_m2": {
        "admissible_contributions": {"missing_reasons": {"I2": "NO_JUSTIFIED_FINAL_IA"}}}}}
    component = {"required_indicator_ids": ["I1", "I2"], "included_indicator_ids": ["I1"]}
    for outcome in ("full_score", "partial_score", "result_without_score", "no_result"):
        skill = {"outcome": outcome, "components": [component]}
        projected = _skill_presentation(skill, c56, c46, {"affected_indicator_ids": []}, template)
        assert projected["outcome"] == outcome
        assert projected["included_indicator_ids"] == ["I1"]
        assert projected["missing_indicator_ids"] == ["I2"]
        assert projected["reasons"][0]["code"] == "plan_scope"
        assert projected["source_reason_codes"] == ["NO_JUSTIFIED_FINAL_IA"]
        assert "нет обоснованной" in projected["reasons"][-1]["message"]
        assert all(value["message"] and value["message"] != value["code"] for value in projected["reasons"])
    assert _skill_presentation({"outcome": "no_result", "components": [component]}, c56, c46,
        {"affected_indicator_ids": ["I2"]}, template)["reasons"][-2]["code"] == "technical_failure"
    c56["coverage"]["full_m2"]["admissible_contributions"]["missing_reasons"]["I2"] = "NEW_UNKNOWN_REASON"
    unknown = _skill_presentation({"outcome": "no_result", "components": [component]}, c56, c46,
        {"affected_indicator_ids": []}, template)
    assert unknown["source_reason_codes"] == ["NEW_UNKNOWN_REASON"]
    assert unknown["reasons"][-1]["message"] == template["skill_result"]["unknown_reason"]


def test_public_projection_keeps_human_reasons_and_hides_comparison_ids():
    report = {"id": "r", "revision_no": 2, "created_at": "2026-11-16T12:00:00Z",
        "results_revision_id": "internal-revision", "c67": {"contract": "C-67", "template_version": "internal-template",
        "report_mechanism": {"version": "internal-version"}, "skills": [{"skill_id": "S", "outcome": "full_score",
        "score": {"value": 0, "numerator": 0, "denominator": 1},
        "presentation": {"label": "Полный показатель по навыку", "reasons": [
            {"code": "plan_scope", "message": "Программа охватывала часть навыка."}],
            "included_indicator_ids": ["I1"], "missing_indicator_ids": ["I2"]}}],
        "partial_result": {"plan_completed": True, "is_incomplete": False, "plan_scope_limited": True,
            "progress": {"completed": 3, "planned": 3}, "messages": {"title": "Оценка завершена"},
            "limitation_reasons": [{"code": "plan_scope", "message": "Часть состава."}]}}}
    value = public_projection(report)["c67"]
    assert value["skills"][0]["score"]["value"] == 0
    assert value["skills"][0]["presentation"]["reasons"][0]["message"] == "Программа охватывала часть навыка."
    assert "included_indicator_ids" not in value["skills"][0]["presentation"]
    assert value["partial_result"]["plan_completed"] is True
    projected = public_projection(report)
    assert value["contract"] == "C-67"
    assert projected["revision_no"] == 2
    assert projected["results_revision_id"] == "internal-revision"
    assert value["template_version"] == "internal-template"


def test_coverage_context_keeps_catalog_plan_facts_and_result_separate():
    cut = lambda numerator, denominator: {
        "numerator": numerator, "denominator": denominator,
        "ratio": numerator / denominator if denominator else None,
    }
    c46 = {"payload_json": {"plan": {"untraversed_route": [
        {"purpose_target_ids": ["I1", "I2"]},
        {"purpose_target_ids": ["I2", "I3", "OUTSIDE"]},
    ]}}}
    c56 = {
        "full_target_set": [{"indicator_id": value} for value in ("I1", "I2", "I3", "I4")],
        "planned_target_set": [{"indicator_id": value} for value in ("I1", "I2")],
        "coverage": {"full_m2": {
            "opportunities": cut(2, 4),
            "indicator_assessments": cut(1, 4),
            "admissible_contributions": cut(1, 4),
        }},
        "skill_outcomes": [{"skill_id": "K1.S1", "outcome": "partial_score", "score": {"value": 1}}],
    }
    result = _coverage_context(c46, c56)
    assert result["not_a_score"] is True
    assert result["catalog_possibility"] == {
        "numerator": 3, "denominator": 4, "ratio": .75,
        "meaning": "IndicatorID addressable by the immutable accepted Cycle route",
    }
    assert result["cycle_plan"]["numerator"] == 2
    assert result["actual_trajectory"]["opportunities"]["numerator"] == 2
    assert result["actual_trajectory"]["indicator_assessments"]["numerator"] == 1
    assert result["result_sufficiency"]["skill_outcomes"] == [
        {"skill_id": "K1.S1", "outcome": "partial_score"}
    ]


def test_pdf_renderer_is_bound_to_saved_report_template(monkeypatch):
    captured = []
    monkeypatch.setattr(m8_results, "render_typst_report", lambda payload, template: captured.append((payload, template)) or b"pdf")
    base = _report_content(results("no_result"), "assessee", None)
    base.update({"results_revision_no": 1, "report_id": "report", "test_result": False})
    report = {"revision_no": 2, "created_at": "2026-10-17T10:00:00Z", "c67": base}

    report["c67"]["template_version"] = "m8-basic-report/1.2.0"
    from Api.typst_pdf_renderer import TypstRenderError
    import pytest
    with pytest.raises(TypstRenderError, match="PDF_REPORT_VERSION_UNSUPPORTED"):
        m8_results.render_pdf(report)

    report["c67"]["template_version"] = "m8-basic-report/1.4.1"
    monkeypatch.setattr(m8_results, "REPORT_TEMPLATE_VERSION", "m8-basic-report/9.9.9")
    assert m8_results.render_pdf(report) == b"pdf"
    payload, template = captured[-1]
    assert template == "m8_participant_report_v2.typ"
    assert payload["skills"][0]["outcome"] == "Недостаточно оснований для результата"
    assert payload["skills"][0]["score"] == "—"
    assert payload["descriptive"]["status"] == "failed"
    assert payload["radars"][0]["axes"][0]["current"] is None


def test_pdf_projection_pins_selected_c67_during_render(monkeypatch):
    base = _report_content(results(score={"value": 0.0, "numerator": 0, "denominator": 1}), "assessee", None)
    base.update({"results_revision_no": 1, "report_id": "selected", "test_result": False,
                 "template_version": "m8-basic-report/1.5.0"})
    report = {"id": "selected", "revision_no": 1, "c67": base,
              "correction": {"created_at": "2026-11-17", "reason": "Уточнено объяснение"}}
    seen = []

    def render(payload, template):
        base["skills"][0]["score"]["value"] = 3.0
        report["correction"]["reason"] = "Позднее изменение"
        seen.append(payload)
        return b"%PDF"

    monkeypatch.setattr(m8_results, "render_typst_report", render)
    assert m8_results.render_pdf(report) == b"%PDF"
    assert seen[0]["radars"][0]["axes"][0]["current"] == 0
    assert seen[0]["correction"]["reason"] == "Уточнено объяснение"


def test_pdf_reader_rejects_incompatible_saved_model():
    from Api.typst_pdf_renderer import TypstRenderError
    import pytest
    report = {"revision_no": 1, "c67": {"template_version": "m8-basic-report/1.4.1",
                                      "skills": [{"skill_id": "S1", "outcome": "full_score", "score": {}}],
                                      "limitations": []}}
    with pytest.raises(TypstRenderError, match="PDF_REPORT_MODEL_UNSUPPORTED"):
        m8_results.render_pdf(report)
