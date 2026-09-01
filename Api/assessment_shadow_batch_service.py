from __future__ import annotations

from Api.assessment_competency_executor import CompetencyEvaluatorExecutor
from Api.assessment_evaluation_material_repository import UniversalEvaluationMaterialProvider
from Api.assessment_evaluator_contracts import competency_evaluation_input_builder
from Api.assessment_shadow_repository import assessment_shadow_repository
from Api.communication_agent import competency_assessment_agents
from Api.config import settings


MAX_SHADOW_COMPETENCY_RUNS = 4


class AssessmentShadowBatchService:
    def preview(self, *, connection, max_competency_runs: int) -> dict:
        limit = self._validate_limit(max_competency_runs)
        targets = self._select_targets(connection=connection, limit=limit)
        return self._result(targets=targets, dry_run=True, completed=0, failed=0)

    def execute(self, *, connection, max_competency_runs: int, confirm_paid_calls: bool) -> dict:
        limit = self._validate_limit(max_competency_runs)
        if not confirm_paid_calls:
            raise ValueError("Paid shadow calls require confirm_paid_calls=true.")
        if not settings.assessment_universal_llm_enabled or not settings.assessment_universal_llm_shadow_enabled:
            raise RuntimeError("Universal LLM and shadow feature flags must both be enabled.")
        targets = self._select_targets(connection=connection, limit=limit)
        executor = CompetencyEvaluatorExecutor(competency_assessment_agents)
        completed = 0
        failed = 0
        for target in targets:
            official_input = self._build_input(connection=connection, target=target, shadow=False)
            shadow_input = self._build_input(connection=connection, target=target, shadow=True)
            official_summary = self._load_official_summary(connection=connection, shadow_input=shadow_input)
            try:
                shadow_output = executor.execute(connection=connection, input_data=shadow_input)
                assessment_shadow_repository.save_success_with_summary(
                    connection=connection,
                    official_input=official_input,
                    official_summary=official_summary,
                    shadow_input=shadow_input,
                    shadow_output=shadow_output,
                )
                completed += 1
            except Exception as exc:
                assessment_shadow_repository.save_failure_with_summary(
                    connection=connection,
                    official_input=official_input,
                    official_summary=official_summary,
                    shadow_input=shadow_input,
                    error=exc,
                )
                failed += 1
        return self._result(targets=targets, dry_run=False, completed=completed, failed=failed)

    def _validate_limit(self, value: int) -> int:
        limit = int(value)
        if not 1 <= limit <= MAX_SHADOW_COMPETENCY_RUNS:
            raise ValueError(f"max_competency_runs must be between 1 and {MAX_SHADOW_COMPETENCY_RUNS}.")
        return limit

    def _select_targets(self, *, connection, limit: int) -> list[dict]:
        rows = connection.execute(
            """
            SELECT id, user_id, execution_snapshot_json
            FROM user_sessions
            WHERE status = 'completed' AND execution_snapshot_json IS NOT NULL
            ORDER BY analysis_completed_at DESC NULLS LAST, id DESC
            LIMIT 100
            """
        ).fetchall()
        targets: list[dict] = []
        for row in rows:
            snapshot = row["execution_snapshot_json"]
            methodology = dict((snapshot.get("methodology") or {}).get("definition") or {})
            for competency in methodology.get("competencies") or []:
                shadow = competency.get("shadow_evaluation")
                if not isinstance(shadow, dict):
                    continue
                reference = dict(shadow.get("agent_definition") or {})
                exists = connection.execute(
                    """
                    SELECT 1 FROM assessment_shadow_evaluation_runs
                    WHERE session_id = %s AND competency_code = %s
                      AND shadow_agent_code = %s AND shadow_agent_version = %s
                    """,
                    (row["id"], competency.get("code"), reference.get("code"), reference.get("version")),
                ).fetchone()
                if exists:
                    continue
                targets.append({
                    "session_id": int(row["id"]), "user_id": int(row["user_id"]),
                    "snapshot": snapshot, "competency": dict(competency),
                })
                if len(targets) >= limit:
                    return targets
        return targets

    def _build_input(self, *, connection, target: dict, shadow: bool):
        competency = dict(target["competency"])
        provider = None
        if shadow:
            shadow_definition = dict(competency.pop("shadow_evaluation"))
            competency["agent_definition"] = dict(shadow_definition.get("agent_definition") or {})
            competency["skill_codes"] = list(shadow_definition.get("skill_codes") or [])
            provider = UniversalEvaluationMaterialProvider(skill_codes=competency["skill_codes"])
        return competency_evaluation_input_builder.build(
            snapshot=target["snapshot"], session_id=target["session_id"], user_id=target["user_id"],
            competency=competency, connection=connection, agent=provider,
        )

    def _load_official_summary(self, *, connection, shadow_input) -> dict:
        skill_ids = [skill.skill_id for skill in shadow_input.skills]
        rows = connection.execute(
            """
            SELECT skill_id, assessed_level_code, red_flags, found_evidence, source_session_case_ids
            FROM session_skill_assessments
            WHERE session_id = %s AND skill_id = ANY(%s)
            ORDER BY skill_id
            """,
            (shadow_input.session_id, skill_ids),
        ).fetchall()
        if len(rows) != len(skill_ids):
            raise ValueError("Stored official assessments are incomplete for the shadow skill scope.")
        return {"status": "evaluated", "skills": [{
            "skill_id": int(row["skill_id"]), "level_code": row["assessed_level_code"],
            "red_flag_count": len(row["red_flags"] or []),
            "evidence_count": len(row["found_evidence"] or []),
            "source_session_case_ids": sorted(set(row["source_session_case_ids"] or [])),
        } for row in rows]}

    def _result(self, *, targets: list[dict], dry_run: bool, completed: int, failed: int) -> dict:
        max_attempts = 0
        for target in targets:
            reference = dict((target["competency"].get("shadow_evaluation") or {}).get("agent_definition") or {})
            frozen = dict(((target["snapshot"].get("prompts") or {}).get("agent_definitions") or {}).get(reference.get("code")) or {})
            runtime = dict((frozen.get("definition") or {}).get("runtime") or {})
            max_attempts += int(runtime.get("max_attempts") or 1)
        return {
            "dry_run": dry_run,
            "planned_competency_runs": len(targets),
            "maximum_llm_attempts": max_attempts,
            "completed_runs": completed,
            "failed_runs": failed,
            "targets": [{
                "session_id": target["session_id"],
                "competency_code": target["competency"].get("code"),
            } for target in targets],
        }


assessment_shadow_batch_service = AssessmentShadowBatchService()
