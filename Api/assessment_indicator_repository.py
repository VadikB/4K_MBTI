from __future__ import annotations

import json

from Api.assessment_evaluator_contracts import (
    CompetencyIndicatorEvaluationInput,
    CompetencyIndicatorEvaluationOutput,
)


class AssessmentIndicatorResultRepository:
    """Persist contract-v2 indicator results without modifying legacy skill results."""

    def save(self, *, connection, input_data: CompetencyIndicatorEvaluationInput, output: CompetencyIndicatorEvaluationOutput) -> None:
        hierarchy, case_scope = self._validate_references(input_data=input_data, output=output)
        for assessment in output.indicator_assessments:
            skill_code, component_code = hierarchy[assessment.indicator_code]
            case_ids = sorted({item.session_case_id for item in assessment.evidence})
            row = connection.execute(
                """
                INSERT INTO session_indicator_assessments (
                    session_id, user_id, methodology_version_id, competency_code,
                    skill_code, component_code, indicator_code, evidence_state,
                    assessed_level_code, red_flag_codes, rationale, confidence,
                    source_session_case_ids, evaluated_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
                    %s, %s, %s::jsonb, NOW(), NOW()
                )
                ON CONFLICT (session_id, methodology_version_id, indicator_code)
                DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    competency_code = EXCLUDED.competency_code,
                    skill_code = EXCLUDED.skill_code,
                    component_code = EXCLUDED.component_code,
                    evidence_state = EXCLUDED.evidence_state,
                    assessed_level_code = EXCLUDED.assessed_level_code,
                    red_flag_codes = EXCLUDED.red_flag_codes,
                    rationale = EXCLUDED.rationale,
                    confidence = EXCLUDED.confidence,
                    source_session_case_ids = EXCLUDED.source_session_case_ids,
                    evaluated_at = EXCLUDED.evaluated_at,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
                """,
                (
                    input_data.session_id, input_data.user_id, input_data.methodology_version_id,
                    output.competency_code, skill_code, component_code, assessment.indicator_code,
                    assessment.evidence_state, assessment.level_code,
                    json.dumps(assessment.red_flag_codes, ensure_ascii=False), assessment.rationale,
                    assessment.confidence, json.dumps(case_ids),
                ),
            ).fetchone()
            assessment_id = int(row["id"])
            connection.execute(
                "DELETE FROM session_case_indicator_evidence WHERE session_indicator_assessment_id = %s",
                (assessment_id,),
            )
            for evidence in assessment.evidence:
                connection.execute(
                    """
                    INSERT INTO session_case_indicator_evidence (
                        session_indicator_assessment_id, session_case_id, observation, evidence_excerpt
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (assessment_id, evidence.session_case_id, evidence.observation, evidence.excerpt),
                )

    def _validate_references(self, *, input_data, output) -> tuple[dict[str, tuple[str, str]], set[int]]:
        if output.competency_code != input_data.competency_code:
            raise ValueError("Evaluator output competency does not match its input.")
        if (output.component_code, output.component_version) != (input_data.component_code, input_data.component_version):
            raise ValueError("Evaluator output component does not match its input.")
        hierarchy: dict[str, tuple[str, str]] = {}
        case_scope: dict[str, set[int]] = {}
        red_flags: dict[str, set[str]] = {}
        for skill in input_data.skills:
            for component in skill.components:
                for indicator in component.indicators:
                    hierarchy[indicator.indicator_code] = (skill.skill_code, component.component_code)
                    red_flags[indicator.indicator_code] = {item.code for item in indicator.red_flags}
                    case_scope[indicator.indicator_code] = {case.session_case_id for case in indicator.cases}
        seen: set[str] = set()
        for assessment in output.indicator_assessments:
            if assessment.indicator_code not in hierarchy:
                raise ValueError("Evaluator assessment references an indicator outside its input.")
            if assessment.indicator_code in seen:
                raise ValueError("Evaluator output contains a duplicate indicator assessment.")
            seen.add(assessment.indicator_code)
            if not {item.session_case_id for item in assessment.evidence}.issubset(case_scope[assessment.indicator_code]):
                raise ValueError("Evaluator assessment references a case outside its input.")
            if not set(assessment.red_flag_codes).issubset(red_flags[assessment.indicator_code]):
                raise ValueError("Evaluator assessment references a red flag outside its input.")
        return hierarchy, set().union(*case_scope.values()) if case_scope else set()


assessment_indicator_result_repository = AssessmentIndicatorResultRepository()
