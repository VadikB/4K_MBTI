from __future__ import annotations

import json

from Api.assessment_evaluator_contracts import (
    CompetencyEvaluationInput,
    CompetencyEvaluationOutput,
)


class AssessmentEvaluationResultRepository:
    """Persist validated evaluator output using the legacy idempotent schema."""

    def save(
        self,
        *,
        connection,
        input_data: CompetencyEvaluationInput,
        output: CompetencyEvaluationOutput,
    ) -> None:
        self._validate_references(input_data=input_data, output=output)
        for analysis in output.case_analyses:
            connection.execute(
                """
                INSERT INTO session_case_skill_analysis (
                    session_id, user_id, session_case_id, case_registry_id, skill_id, competency_name,
                    expected_artifact_code, expected_artifact_name, detected_artifact_parts,
                    missing_artifact_parts, artifact_compliance_percent,
                    structural_elements, detected_required_blocks, missing_required_blocks,
                    block_coverage_percent, red_flags, found_evidence, detected_signals,
                    evidence_excerpt, source_message_count, analyzed_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    NOW(), NOW()
                )
                ON CONFLICT (session_case_id, skill_id)
                DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    user_id = EXCLUDED.user_id,
                    case_registry_id = EXCLUDED.case_registry_id,
                    competency_name = EXCLUDED.competency_name,
                    expected_artifact_code = EXCLUDED.expected_artifact_code,
                    expected_artifact_name = EXCLUDED.expected_artifact_name,
                    detected_artifact_parts = EXCLUDED.detected_artifact_parts,
                    missing_artifact_parts = EXCLUDED.missing_artifact_parts,
                    artifact_compliance_percent = EXCLUDED.artifact_compliance_percent,
                    structural_elements = EXCLUDED.structural_elements,
                    detected_required_blocks = EXCLUDED.detected_required_blocks,
                    missing_required_blocks = EXCLUDED.missing_required_blocks,
                    block_coverage_percent = EXCLUDED.block_coverage_percent,
                    red_flags = EXCLUDED.red_flags,
                    found_evidence = EXCLUDED.found_evidence,
                    detected_signals = EXCLUDED.detected_signals,
                    evidence_excerpt = EXCLUDED.evidence_excerpt,
                    source_message_count = EXCLUDED.source_message_count,
                    analyzed_at = EXCLUDED.analyzed_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    input_data.session_id,
                    input_data.user_id,
                    analysis.session_case_id,
                    analysis.case_registry_id,
                    analysis.skill_id,
                    analysis.competency_name,
                    analysis.expected_artifact_code,
                    analysis.expected_artifact_name,
                    json.dumps(analysis.detected_artifact_parts, ensure_ascii=False),
                    json.dumps(analysis.missing_artifact_parts, ensure_ascii=False),
                    analysis.artifact_compliance_percent,
                    json.dumps(analysis.structural_elements, ensure_ascii=False),
                    json.dumps(analysis.detected_required_blocks, ensure_ascii=False),
                    json.dumps(analysis.missing_required_blocks, ensure_ascii=False),
                    analysis.block_coverage_percent,
                    json.dumps(analysis.red_flags, ensure_ascii=False),
                    json.dumps(analysis.found_evidence, ensure_ascii=False),
                    json.dumps(analysis.detected_signals, ensure_ascii=False),
                    analysis.evidence_excerpt,
                    analysis.source_message_count,
                ),
            )

        for assessment in output.assessments:
            connection.execute(
                """
                INSERT INTO session_skill_assessments (
                    session_id, user_id, skill_id, competency_skill_id, competency_name, skill_code, skill_name,
                    assessed_level_code, assessed_level_name, rubric_match_scores, structural_elements,
                    red_flags, found_evidence, detected_required_blocks, missing_required_blocks,
                    block_coverage_percent, rationale, evidence_excerpt, source_session_case_ids
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, skill_id)
                DO UPDATE SET
                    competency_skill_id = EXCLUDED.competency_skill_id,
                    competency_name = EXCLUDED.competency_name,
                    skill_code = EXCLUDED.skill_code,
                    skill_name = EXCLUDED.skill_name,
                    assessed_level_code = EXCLUDED.assessed_level_code,
                    assessed_level_name = EXCLUDED.assessed_level_name,
                    rubric_match_scores = EXCLUDED.rubric_match_scores,
                    structural_elements = EXCLUDED.structural_elements,
                    red_flags = EXCLUDED.red_flags,
                    found_evidence = EXCLUDED.found_evidence,
                    detected_required_blocks = EXCLUDED.detected_required_blocks,
                    missing_required_blocks = EXCLUDED.missing_required_blocks,
                    block_coverage_percent = EXCLUDED.block_coverage_percent,
                    rationale = EXCLUDED.rationale,
                    evidence_excerpt = EXCLUDED.evidence_excerpt,
                    source_session_case_ids = EXCLUDED.source_session_case_ids,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    input_data.session_id,
                    input_data.user_id,
                    assessment.skill_id,
                    assessment.competency_skill_id,
                    assessment.competency_name,
                    assessment.skill_code,
                    assessment.skill_name,
                    assessment.level_code,
                    assessment.level_name,
                    json.dumps(assessment.rubric_match_scores, ensure_ascii=False),
                    json.dumps(assessment.structural_elements, ensure_ascii=False),
                    json.dumps(assessment.red_flags, ensure_ascii=False),
                    json.dumps(assessment.found_evidence, ensure_ascii=False),
                    json.dumps(assessment.detected_required_blocks, ensure_ascii=False),
                    json.dumps(assessment.missing_required_blocks, ensure_ascii=False),
                    assessment.block_coverage_percent,
                    assessment.rationale,
                    assessment.evidence_excerpt,
                    json.dumps(assessment.source_session_case_ids, ensure_ascii=False),
                ),
            )

    def _validate_references(
        self,
        *,
        input_data: CompetencyEvaluationInput,
        output: CompetencyEvaluationOutput,
    ) -> None:
        if output.competency_code != input_data.competency_code:
            raise ValueError("Evaluator output competency does not match its input.")
        if (output.component_code, output.component_version) != (
            input_data.component_code,
            input_data.component_version,
        ):
            raise ValueError("Evaluator output component does not match its input.")

        input_skill_ids = {skill.skill_id for skill in input_data.skills}
        input_case_ids = {case.session_case_id for skill in input_data.skills for case in skill.cases}
        for assessment in output.assessments:
            if assessment.skill_id not in input_skill_ids:
                raise ValueError("Evaluator assessment references a skill outside its input.")
            if not set(assessment.source_session_case_ids).issubset(input_case_ids):
                raise ValueError("Evaluator assessment references a case outside its input.")
        for analysis in output.case_analyses:
            if analysis.skill_id not in input_skill_ids or analysis.session_case_id not in input_case_ids:
                raise ValueError("Evaluator case analysis references material outside its input.")


assessment_evaluation_result_repository = AssessmentEvaluationResultRepository()
