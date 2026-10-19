from copy import deepcopy

import pytest

from Api import m8_report_comparison
from Api.m8_report_comparison import compare_reports


def report(cycle, report_id, score=2.25, *, role="role-1", outcome="full_score"):
    skill = {
        "skill_id": "K1.S1", "skill_code": "K1.S1", "skill_name": "Навык",
        "skill_description": "Описание", "competency_id": "K1",
        "components": ["C1"], "indicators": ["I1"], "outcome": outcome,
        "score": None if score is None else {"value": score, "numerator": score, "denominator": 1},
    }
    return {
        "id": report_id, "revision_no": 1, "cycle_id": cycle,
        "results_revision_id": f"results-{cycle}", "created_at": "2026-10-17T00:00:00Z",
        "c67": {
            "role_ref": {"id": role, "checksum": "role-checksum"},
            "profile_ref": {"id": "profile", "checksum": "profile-checksum"},
            "target_profile": {"requirements": [{"skill_id": "K1.S1", "value": 2}]},
            "provenance": {"composition_checksum": "m2", "sources": {"m2": "v1"}, "algorithm": {"m6": "v1"}},
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
        (lambda value: value["c67"]["provenance"].update(composition_checksum="other"), "not_confirmed", "m2_composition_not_confirmed"),
        (lambda value: value["c67"]["provenance"].update(algorithm={"m6": "v2"}), "not_confirmed", "m6_rules_not_confirmed"),
        (lambda value: value["c67"].update(profile_ref={"id": "profile-2", "checksum": "other"}), "not_confirmed", "assessment_context_not_confirmed"),
        (lambda value: value["c67"]["skills"][0].update(outcome="partial_score"), "not_allowed", "full_score_required"),
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


def test_comparison_pdf_uses_exact_projection_and_server_renderer(monkeypatch):
    captured = []
    monkeypatch.setattr("Api.typst_pdf_renderer.render_typst_report", lambda payload, template: captured.append((payload, template)) or b"%PDF")
    comparison = compare_reports(report("current", "r2", 2.25), report("previous", "r1", 1.75))
    assert m8_report_comparison.render_comparison_pdf(comparison) == b"%PDF"
    assert captured[0][1] == "m8_report_comparison_v1.typ"
    assert captured[0][0]["comparable"][0]["difference"] == 0.5
