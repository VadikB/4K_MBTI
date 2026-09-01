from __future__ import annotations

import json

from Api.assessment_evaluator_contracts import CompetencyEvaluationInput, CompetencyEvaluationOutput


class AssessmentShadowRepository:
    def aggregate_comparisons(self, *, connection) -> dict:
        totals = connection.execute(
            """
            SELECT
                COUNT(*)::integer AS run_count,
                COUNT(*) FILTER (WHERE status = 'completed')::integer AS completed_count,
                COUNT(*) FILTER (WHERE status = 'failed')::integer AS failed_count,
                COALESCE(SUM((comparison_json ->> 'compared_skill_count')::integer)
                    FILTER (WHERE status = 'completed'), 0)::integer AS compared_skill_count,
                COALESCE(SUM((comparison_json ->> 'exact_level_match_count')::integer)
                    FILTER (WHERE status = 'completed'), 0)::integer AS exact_level_match_count
            FROM assessment_shadow_evaluation_runs
            """
        ).fetchone()
        groups = connection.execute(
            """
            SELECT
                competency_code,
                official_agent_code,
                official_agent_version,
                shadow_agent_code,
                shadow_agent_version,
                COUNT(*)::integer AS run_count,
                COUNT(*) FILTER (WHERE status = 'completed')::integer AS completed_count,
                COUNT(*) FILTER (WHERE status = 'failed')::integer AS failed_count,
                COALESCE(SUM((comparison_json ->> 'compared_skill_count')::integer)
                    FILTER (WHERE status = 'completed'), 0)::integer AS compared_skill_count,
                COALESCE(SUM((comparison_json ->> 'exact_level_match_count')::integer)
                    FILTER (WHERE status = 'completed'), 0)::integer AS exact_level_match_count,
                MIN(completed_at) AS first_completed_at,
                MAX(completed_at) AS last_completed_at
            FROM assessment_shadow_evaluation_runs
            GROUP BY
                competency_code,
                official_agent_code,
                official_agent_version,
                shadow_agent_code,
                shadow_agent_version
            ORDER BY competency_code, shadow_agent_code, shadow_agent_version
            """
        ).fetchall()
        return {
            "totals": self._aggregate_metrics(dict(totals)),
            "groups": [self._aggregate_metrics(dict(row)) for row in groups],
        }

    def _aggregate_metrics(self, row: dict) -> dict:
        compared = int(row.get("compared_skill_count") or 0)
        matches = int(row.get("exact_level_match_count") or 0)
        return {
            **row,
            "exact_level_match_percent": round(matches * 100 / compared, 2) if compared else None,
        }

    def save_success(
        self,
        *,
        connection,
        official_input: CompetencyEvaluationInput,
        official_output: CompetencyEvaluationOutput,
        shadow_input: CompetencyEvaluationInput,
        shadow_output: CompetencyEvaluationOutput,
    ) -> None:
        official_summary = self._summary(official_output)
        self.save_success_with_summary(
            connection=connection,
            official_input=official_input,
            official_summary=official_summary,
            shadow_input=shadow_input,
            shadow_output=shadow_output,
        )

    def save_success_with_summary(
        self,
        *,
        connection,
        official_input: CompetencyEvaluationInput,
        official_summary: dict,
        shadow_input: CompetencyEvaluationInput,
        shadow_output: CompetencyEvaluationOutput,
    ) -> None:
        shadow_summary = self._summary(shadow_output)
        comparison = self._compare(official_summary, shadow_summary)
        self._upsert(
            connection=connection,
            official_input=official_input,
            shadow_input=shadow_input,
            status="completed",
            official_summary=official_summary,
            shadow_summary=shadow_summary,
            comparison=comparison,
            error_code=None,
        )

    def save_failure(
        self,
        *,
        connection,
        official_input: CompetencyEvaluationInput,
        official_output: CompetencyEvaluationOutput,
        shadow_input: CompetencyEvaluationInput,
        error: Exception,
    ) -> None:
        self.save_failure_with_summary(
            connection=connection,
            official_input=official_input,
            official_summary=self._summary(official_output),
            shadow_input=shadow_input,
            error=error,
        )

    def save_failure_with_summary(
        self,
        *,
        connection,
        official_input: CompetencyEvaluationInput,
        official_summary: dict,
        shadow_input: CompetencyEvaluationInput,
        error: Exception,
    ) -> None:
        self._upsert(
            connection=connection, official_input=official_input, shadow_input=shadow_input,
            status="failed", official_summary=official_summary, shadow_summary=None,
            comparison=None, error_code=error.__class__.__name__,
        )

    def _summary(self, output: CompetencyEvaluationOutput) -> dict:
        return {
            "status": output.status,
            "skills": [
                {
                    "skill_id": item.skill_id,
                    "level_code": item.level_code,
                    "red_flag_count": len(item.red_flags),
                    "evidence_count": len(item.found_evidence),
                    "source_session_case_ids": sorted(set(item.source_session_case_ids)),
                }
                for item in sorted(output.assessments, key=lambda value: value.skill_id)
            ],
        }

    def _compare(self, official: dict, shadow: dict) -> dict:
        official_by_skill = {item["skill_id"]: item for item in official["skills"]}
        shadow_by_skill = {item["skill_id"]: item for item in shadow["skills"]}
        shared_ids = sorted(set(official_by_skill) & set(shadow_by_skill))
        exact_level_matches = sum(
            official_by_skill[skill_id]["level_code"] == shadow_by_skill[skill_id]["level_code"]
            for skill_id in shared_ids
        )
        return {
            "official_skill_count": len(official_by_skill),
            "shadow_skill_count": len(shadow_by_skill),
            "compared_skill_count": len(shared_ids),
            "exact_level_match_count": exact_level_matches,
            "exact_level_match_percent": (
                round(exact_level_matches * 100 / len(shared_ids), 2) if shared_ids else None
            ),
            "missing_in_shadow_skill_ids": sorted(set(official_by_skill) - set(shadow_by_skill)),
            "extra_in_shadow_skill_ids": sorted(set(shadow_by_skill) - set(official_by_skill)),
        }

    def _upsert(
        self,
        *,
        connection,
        official_input: CompetencyEvaluationInput,
        shadow_input: CompetencyEvaluationInput,
        status: str,
        official_summary: dict,
        shadow_summary: dict | None,
        comparison: dict | None,
        error_code: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO assessment_shadow_evaluation_runs (
                session_id, competency_code,
                official_agent_code, official_agent_version, official_agent_checksum,
                shadow_agent_code, shadow_agent_version, shadow_agent_checksum,
                status, official_summary_json, shadow_summary_json, comparison_json,
                error_code, completed_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, NOW(), NOW()
            )
            ON CONFLICT (session_id, competency_code, shadow_agent_code, shadow_agent_version)
            DO UPDATE SET
                official_agent_code = EXCLUDED.official_agent_code,
                official_agent_version = EXCLUDED.official_agent_version,
                official_agent_checksum = EXCLUDED.official_agent_checksum,
                shadow_agent_checksum = EXCLUDED.shadow_agent_checksum,
                status = EXCLUDED.status,
                official_summary_json = EXCLUDED.official_summary_json,
                shadow_summary_json = EXCLUDED.shadow_summary_json,
                comparison_json = EXCLUDED.comparison_json,
                error_code = EXCLUDED.error_code,
                completed_at = NOW(),
                updated_at = NOW()
            """,
            (
                official_input.session_id,
                official_input.competency_code,
                official_input.agent_definition.code,
                official_input.agent_definition.version,
                official_input.agent_definition.checksum,
                shadow_input.agent_definition.code,
                shadow_input.agent_definition.version,
                shadow_input.agent_definition.checksum,
                status,
                json.dumps(official_summary, ensure_ascii=False),
                json.dumps(shadow_summary, ensure_ascii=False) if shadow_summary is not None else None,
                json.dumps(comparison, ensure_ascii=False) if comparison is not None else None,
                error_code,
            ),
        )


assessment_shadow_repository = AssessmentShadowRepository()
