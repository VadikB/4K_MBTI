import pytest

from Api.m8_recommendations import _validate_basis, generate, profile_projection


def _skill(outcome="full_score"):
    value = {"skill_id": "K1.1", "outcome": outcome, "components": [{
        "component_id": "K1.1.C1", "required_indicator_ids": ["K1.1.I1", "K1.1.I2"],
        "included_indicator_ids": ["K1.1.I1"], "missing_indicator_ids": ["K1.1.I2"],
        "completeness": "partial" if outcome == "partial_score" else "full",
    }], "comparison": {"status": "NOT_COMPARABLE", "reason": "NORMATIVE_SKILL_LEVEL_NOT_AVAILABLE"}}
    if outcome in {"full_score", "partial_score"}:
        value["score"] = {"value": 2.4, "numerator": 12, "denominator": 5}
    return value


def _results(outcome="full_score"):
    return {"results_revision_id": "results-revision-1", "results_version": "m8-results/1.0.0",
        "profile_ref": {"id": "profile:7", "version": "1", "checksum": "a" * 64},
        "assessed_skill_profile": [_skill(outcome)],
        "observations": [{"indicator_id": "K1.1.I1", "revision_id": "ia-1",
            "assessment_revision_id": "assessment-1", "evidence_revision_id": "evidence-1",
            "assessment_situation_id": "as-1", "outcome": "L2", "refs": [],
            "confidence": {"confirmed_features": ["участник явно сформулировал критерий решения"]}}]}


def _profile():
    return {"content": {"organization_context": {}, "role_profile": {"typical_tasks": ["согласование решения с командой"]},
        "user_context": {"regular_tasks": ["личная задача"], "email": "forbidden@example.test"}}}


@pytest.mark.parametrize("outcome", ["full_score", "partial_score", "result_without_score"])
def test_t11_supported_skill_outcomes_create_three_grounded_types(outcome):
    generated = generate(_results(outcome), _profile())
    assert generated["status"] == "ready"
    assert {item["type"] for item in generated["recommendations"]} == {
        "Development", "Consolidation / Maintenance", "Application / Transfer"}
    assert all(item["basis_refs"][0]["ia_revision_id"] == "ia-1" for item in generated["recommendations"])
    assert all("устойчив" not in item["goal"].lower() for item in generated["recommendations"])
    assert all(item["practice"] and item["application_context"] and item["progress_signal"]
               for item in generated["recommendations"])


def test_t11_no_result_is_notice_not_deficit_recommendation():
    generated = generate(_results("no_result"), _profile())
    assert generated["recommendations"] == []
    assert generated["notices"][0]["kind"] == "INSUFFICIENT_BASIS"
    assert "дефицит" in generated["notices"][0]["text"]


def test_t11_partial_and_not_comparable_do_not_claim_missing_elements_or_target_gap():
    generated = generate(_results("partial_score"), _profile())
    text = str(generated["recommendations"])
    assert "K1.1.I2" not in text
    assert "не достиг" not in text.lower()
    assert all(item["gap_ref"] is None for item in generated["recommendations"])


def test_t11_profile_projection_is_minimal_and_snapshot_based():
    projection = profile_projection(_profile())
    assert projection["role_profile"]["typical_tasks"] == ["согласование решения с командой"]
    assert "email" not in projection["user_context"]
    generated = generate(_results(), _profile())
    assert generated["input"]["profile_projection"] == projection
    assert "forbidden@example.test" not in str(generated)


def test_t11_foreign_or_unresolved_basis_is_rejected():
    skill = _skill()
    observations = _results()["observations"]
    with pytest.raises(ValueError, match="SCOPE_MISMATCH"):
        _validate_basis(skill, {"skill_id": "K2.1", "indicator_id": "K1.1.I1", "ia_revision_id": "ia-1"}, observations)
    with pytest.raises(ValueError, match="UNRESOLVED"):
        _validate_basis(skill, {"skill_id": "K1.1", "indicator_id": "K1.1.I1", "ia_revision_id": "missing"}, observations)


def test_t11_output_is_deterministic_and_input_is_versioned():
    first = generate(_results(), _profile())
    second = generate(_results(), _profile())
    assert first == second
    assert first["contract_version"] == "m8-recommendations/1.0.0"
    assert first["mechanism"]["kind"] == "deterministic_template"
    assert len(first["input_checksum"]) == 64
    assert first["input"]["observation_refs"][0]["confirmed_features"] == [
        "участник явно сформулировал критерий решения"]
