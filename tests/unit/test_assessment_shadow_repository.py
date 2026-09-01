import pytest

from Api.assessment_evaluator_contracts import CompetencyEvaluationOutput
from Api.assessment_shadow_repository import AssessmentShadowRepository


def output(*, level: str, skill_id: int = 11) -> CompetencyEvaluationOutput:
    return CompetencyEvaluationOutput(
        competency_code="communication",
        component_code="evaluation.communication",
        component_version=1,
        status="evaluated",
        assessments=[
            {
                "skill_id": skill_id,
                "competency_skill_id": 21,
                "skill_code": "active_listening",
                "skill_name": "Активное слушание",
                "competency_name": "Коммуникация",
                "level_code": level,
                "level_name": level,
                "rubric_match_scores": {"L1": 1, "L2": 0, "L3": 0},
                "structural_elements": {},
                "red_flags": ["flag"],
                "found_evidence": [{"reference": "case:31", "observation": "signal"}],
                "detected_required_blocks": [],
                "missing_required_blocks": [],
                "block_coverage_percent": None,
                "rationale": "Must not be persisted in shadow summary.",
                "evidence_excerpt": "Must not be persisted in shadow summary.",
                "source_session_case_ids": [31],
            }
        ],
        case_analyses=[],
    )


@pytest.mark.unit
def test_shadow_summary_is_sanitized_and_comparison_is_deterministic() -> None:
    repository = AssessmentShadowRepository()
    official = repository._summary(output(level="L1"))
    shadow = repository._summary(output(level="L2"))
    comparison = repository._compare(official, shadow)

    assert "rationale" not in str(official)
    assert "evidence_excerpt" not in str(official)
    assert official["skills"][0]["evidence_count"] == 1
    assert comparison["compared_skill_count"] == 1
    assert comparison["exact_level_match_percent"] == 0.0


@pytest.mark.unit
def test_shadow_aggregate_percentage_is_weighted_by_compared_skills() -> None:
    result = AssessmentShadowRepository()._aggregate_metrics(
        {
            "run_count": 2,
            "completed_count": 2,
            "failed_count": 0,
            "compared_skill_count": 3,
            "exact_level_match_count": 2,
        }
    )

    assert result["exact_level_match_percent"] == 66.67
