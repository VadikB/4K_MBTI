from copy import deepcopy

import pytest

from Api import m8_report_comparison
from Api.m8_report_comparison import compare_reports


def report(cycle, report_id, score=2.25, *, role="role-1", outcome="full_score",
           budget=7200, calendar=259200, return_policy="return-v1"):
    skill = {
        "skill_id": "K1.S1", "skill_code": "K1.S1", "skill_name": "Навык",
        "skill_description": "Описание", "competency_id": "K1",
        "components": ["C1"], "indicators": ["I1"], "outcome": outcome,
        "presentation": {"required_indicator_ids": ["I1"], "included_indicator_ids": ["I1"]},
        "score": None if score is None else {"value": score, "numerator": score, "denominator": 1},
    }
    return {
        "id": report_id, "revision_no": 1, "cycle_id": cycle,
        "results_revision_id": f"results-{cycle}", "created_at": "2026-10-17T00:00:00Z",
        "c67": {
            "role_ref": {"id": role, "checksum": "role-checksum"},
            "profile_ref": {"id": "profile", "checksum": "profile-checksum"},
            "target_profile": {"requirements": [{"skill_id": "K1.S1", "value": 2}]},
            "provenance": {"composition_checksum": f"integrity-{cycle}", "sources": {"M2": "v1", "M6": "v1"}, "algorithm": {"version": "v1", "rules_hash": "rules-v1"},
                           "comparison_evidence": {
                               "contract_version": "m8-comparison-evidence/1.0.0",
                               "semantic_composition": {"full_target_set_checksum": "semantic-m2"},
                               "assessment_conditions": {"time_budget_seconds": budget,
                                   "calendar_window_seconds": calendar, "return_policy_checksum": return_policy},
                           }},
            "partial_result": {"is_incomplete": False}, "skills": [skill],
            "time": {"started_at": "2026-10-01T00:00:00Z"},
            "collection": {"closed_at": "2026-10-02T00:00:00Z"},
        },
    }


def test_proven_pair_returns_exact_delta_and_preserves_zero():
    value = compare_reports(report("current", "r2", 2.25), report("previous", "r1", 1.75))
    assert value["mode"] == "numeric"
    assert value["skills"][0]["difference"] == 0.5
    zero = compare_reports(report("current", "r2", 0), report("previous", "r1", 0))
    assert zero["skills"][0] == {**zero["skills"][0], "previous": 0.0, "current": 0.0, "difference": 0.0}


@pytest.mark.parametrize(
    ("mutate", "status", "reason"),
    [
        (lambda value: value["c67"].update(role_ref={"id": "role-2", "checksum": "other"}), "not_allowed", "different_role"),
        (lambda value: value["c67"].update(role_ref={"id": "role-2", "name": "Та же роль"}), "not_confirmed", "role_snapshot_missing"),
        (lambda value: value["c67"]["skills"][0]["presentation"].update(required_indicator_ids=["I2"]), "not_confirmed", "skill_composition_changed"),
        (lambda value: value["c67"]["provenance"].update(algorithm={"version": "v2", "rules_hash": "rules-v2"}), "not_confirmed", "m6_rules_not_confirmed"),
        (lambda value: value["c67"].update(profile_ref={"id": "profile-2", "checksum": "other"}), "not_confirmed", "assessment_context_not_confirmed"),
        (lambda value: value["c67"]["skills"][0].update(outcome="partial_score"), "not_allowed", "score_completeness_changed"),
        (lambda value: value["c67"]["skills"][0].update(score=None), "not_allowed", "numeric_score_missing"),
    ],
)
def test_missing_or_conflicting_evidence_never_returns_delta(mutate, status, reason):
    current = report("current", "r2")
    previous = deepcopy(report("previous", "r1"))
    mutate(previous)
    row = compare_reports(current, previous)["skills"][0]
    assert row["difference"] is None
    assert row["comparability"] == {"status": status, "reason": reason}


def test_same_cycle_different_report_revision_is_not_a_previous_assessment():
    with pytest.raises(ValueError, match="DISTINCT_CYCLES"):
        compare_reports(report("cycle", "r2"), report("cycle", "r1"))


@pytest.mark.parametrize("field,value", [
    ("time_budget_seconds", 3600),
    ("calendar_window_seconds", 172800),
    ("return_policy_checksum", "return-v2"),
])
def test_different_saved_assessment_conditions_never_return_delta(field, value):
    current = report("current", "r2")
    previous = report("previous", "r1")
    previous["c67"]["provenance"]["comparison_evidence"]["assessment_conditions"][field] = value
    row = compare_reports(current, previous)["skills"][0]
    assert row["difference"] is None
    assert row["comparability"] == {"status": "not_confirmed", "reason": "assessment_conditions_not_confirmed"}


def test_historical_report_without_comparison_evidence_is_not_confirmed():
    previous = report("previous", "r1")
    previous["c67"]["provenance"].pop("comparison_evidence")
    row = compare_reports(report("current", "r2"), previous)["skills"][0]
    assert row["comparability"] == {"status": "not_confirmed", "reason": "assessment_conditions_not_confirmed"}


def test_missing_saved_condition_is_not_equal_to_another_missing_condition():
    current = report("current", "r2", return_policy=None)
    previous = report("previous", "r1", return_policy=None)
    row = compare_reports(current, previous)["skills"][0]
    assert row["difference"] is None
    assert row["comparability"] == {"status": "not_confirmed", "reason": "assessment_conditions_not_confirmed"}


@pytest.mark.parametrize("outcome", ["partial_score", "result_without_score", "no_result"])
def test_non_full_outcomes_remain_separate(outcome):
    row = compare_reports(report("current", "r2", outcome=outcome), report("previous", "r1"))["skills"][0]
    assert row["difference"] is None
    assert row["comparability"] == {"status": "not_allowed", "reason":
                                   "score_completeness_changed" if outcome == "partial_score" else "full_score_required"}


def test_incomplete_cycle_uses_saved_skill_relevance_not_global_prohibition():
    current = report("current", "r2", 2.0)
    previous = report("previous", "r1", 1.0)
    current["c67"]["partial_result"] = {"is_incomplete": True}
    current["c67"]["skills"][0]["presentation"]["remaining_plan_relevant"] = False
    allowed = compare_reports(current, previous)["skills"][0]
    assert allowed["comparability"]["status"] == "allowed"
    current["c67"]["skills"][0]["presentation"]["remaining_plan_relevant"] = None
    unknown = compare_reports(current, previous)["skills"][0]
    assert unknown["comparability"] == {"status": "allowed", "reason": None}


def test_optional_target_and_different_technical_profile_ids_do_not_block_actual_scores():
    current = report("current", "r2", 2.25)
    previous = report("previous", "r1", 1.75)
    current["c67"]["target_profile"] = previous["c67"]["target_profile"] = None
    previous["c67"]["profile_ref"]["id"] = "other-db-row"
    previous["c67"]["role_ref"]["id"] = "other-role-row"
    assert compare_reports(current, previous)["skills"][0]["difference"] == 0.5


def test_partial_scores_require_same_confirmed_included_composition():
    current = report("current", "r2", 2.0, outcome="partial_score")
    previous = report("previous", "r1", 1.0, outcome="partial_score")
    for value in (current, previous):
        value["c67"]["skills"][0]["presentation"].update(
            required_indicator_ids=["I1", "I2", "I3"], included_indicator_ids=["I1", "I2"])
    assert compare_reports(current, previous)["skills"][0]["difference"] == 1.0
    previous["c67"]["skills"][0]["presentation"]["included_indicator_ids"] = ["I1", "I3"]
    row = compare_reports(current, previous)["skills"][0]
    assert row["difference"] is None
    assert row["comparability"]["reason"] == "skill_composition_changed"


def test_incomplete_two_of_three_cycle_keeps_a_complete_skill_comparable():
    current = report("current", "r2", 2.0)
    previous = report("previous", "r1", 1.0)
    for value in (current, previous):
        other = deepcopy(value["c67"]["skills"][0])
        other.update(skill_id="K1.S2", skill_code="K1.S2", skill_name="Второй навык",
                     outcome="partial_score", score={"value": 2, "numerator": 2, "denominator": 1},
                     presentation={"required_indicator_ids": ["I2", "I3", "I4"],
                                   "included_indicator_ids": ["I2", "I3"]})
        value["c67"]["skills"].append(other)
    current["c67"]["partial_result"] = {"is_incomplete": True, "progress": {"completed": 2, "planned": 3}}
    previous["c67"]["skills"][1]["presentation"]["included_indicator_ids"] = ["I2", "I4"]
    rows = compare_reports(current, previous)["skills"]
    assert rows[0]["difference"] == 1.0
    assert rows[1]["difference"] is None
    assert rows[1]["comparability"]["reason"] == "skill_composition_changed"


def test_missing_mandatory_context_and_equal_numbers_do_not_confirm_comparability():
    current = report("current", "r2", 0)
    previous = report("previous", "r1", 0)
    current["c67"]["profile_ref"] = previous["c67"]["profile_ref"] = {"id": "same"}
    row = compare_reports(current, previous)["skills"][0]
    assert row["previous"] == row["current"] == 0.0
    assert row["difference"] is None
    assert row["comparability"]["reason"] == "assessment_context_not_confirmed"
    current["c67"]["profile_ref"] = previous["c67"]["profile_ref"] = {"checksum": "known"}
    current["c67"]["provenance"]["algorithm"] = previous["c67"]["provenance"]["algorithm"] = {}
    row = compare_reports(current, previous)["skills"][0]
    assert row["difference"] is None
    assert row["comparability"]["reason"] == "m6_rules_not_confirmed"


def test_new_m2_version_with_same_name_is_not_semantically_mapped():
    current = report("current", "r2", 2.0)
    previous = report("previous", "r1", 2.0)
    previous["c67"]["provenance"]["sources"] = {"M2": "v2", "M6": "v1"}
    row = compare_reports(current, previous)["skills"][0]
    assert row["difference"] is None
    assert row["comparability"]["reason"] == "m2_sources_not_confirmed"


def test_skill_only_in_previous_cycle_remains_visible_without_delta():
    current = report("current", "r2", 2.0)
    previous = report("previous", "r1", 1.0)
    previous["c67"]["skills"][0].update(skill_id="K1.old", skill_code="K1.old", skill_name="Старый навык")
    rows = compare_reports(current, previous)["skills"]
    assert len(rows) == 2
    assert rows[1]["previous"] == 1.0 and rows[1]["current"] is None
    assert rows[1]["comparability"]["reason"] == "skill_absent_in_current_cycle"


def test_comparison_pdf_uses_exact_projection_and_server_renderer(monkeypatch):
    captured = []
    monkeypatch.setattr("Api.typst_pdf_renderer.render_typst_report", lambda payload, template: captured.append((payload, template)) or b"%PDF")
    comparison = compare_reports(report("current", "r2", 2.25), report("previous", "r1", 1.75))
    assert m8_report_comparison.render_comparison_pdf(comparison) == b"%PDF"
    assert captured[0][1] == "m8_report_comparison_v2.typ"
    assert captured[0][0]["comparable"][0]["difference"] == 0.5
