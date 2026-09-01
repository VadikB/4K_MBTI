from __future__ import annotations

import json

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.assessment_shadow_repository import AssessmentShadowRepository
from Api.assessment_shadow_batch_service import AssessmentShadowBatchService


@pytest.mark.integration
def test_shadow_comparison_aggregate_uses_sanitized_counts(test_database_url) -> None:
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_shadow_evaluation_runs")
        connection.execute(
            """
            CREATE TABLE assessment_shadow_evaluation_runs (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL,
                competency_code TEXT NOT NULL,
                official_agent_code TEXT NOT NULL,
                official_agent_version INTEGER NOT NULL,
                official_agent_checksum TEXT NOT NULL,
                shadow_agent_code TEXT NOT NULL,
                shadow_agent_version INTEGER NOT NULL,
                shadow_agent_checksum TEXT NOT NULL,
                status TEXT NOT NULL,
                official_summary_json JSONB NOT NULL,
                shadow_summary_json JSONB,
                comparison_json JSONB,
                error_code TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO assessment_shadow_evaluation_runs (
                session_id, competency_code,
                official_agent_code, official_agent_version, official_agent_checksum,
                shadow_agent_code, shadow_agent_version, shadow_agent_checksum,
                status, official_summary_json, shadow_summary_json, comparison_json, completed_at
            ) VALUES
                (1, 'communication', 'communication', 1, 'official',
                 'communication_shadow', 2, 'shadow', 'completed', '{}', '{}',
                 '{"compared_skill_count": 2, "exact_level_match_count": 1}', NOW()),
                (2, 'communication', 'communication', 1, 'official',
                 'communication_shadow', 2, 'shadow', 'completed', '{}', '{}',
                 '{"compared_skill_count": 1, "exact_level_match_count": 1}', NOW()),
                (3, 'communication', 'communication', 1, 'official',
                 'communication_shadow', 2, 'shadow', 'failed', '{}', NULL, NULL, NOW())
            """
        )

        result = AssessmentShadowRepository().aggregate_comparisons(connection=connection)

        assert result["totals"]["run_count"] == 3
        assert result["totals"]["completed_count"] == 2
        assert result["totals"]["failed_count"] == 1
        assert result["totals"]["exact_level_match_percent"] == 66.67
        assert len(result["groups"]) == 1
        assert result["groups"][0]["shadow_agent_version"] == 2

        connection.execute("DROP TABLE assessment_shadow_evaluation_runs")


@pytest.mark.integration
def test_shadow_batch_selection_skips_existing_agent_version(test_database_url) -> None:
    snapshot = {
        "methodology": {"definition": {"competencies": [{
            "code": "communication",
            "shadow_evaluation": {
                "agent_definition": {"code": "communication_shadow", "version": 2},
                "skill_codes": ["active_listening"],
            },
        }]}},
    }
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_shadow_evaluation_runs")
        connection.execute("DROP TABLE IF EXISTS user_sessions")
        connection.execute(
            """
            CREATE TABLE user_sessions (
                id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL, status TEXT NOT NULL,
                analysis_completed_at TIMESTAMP, execution_snapshot_json JSONB
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_shadow_evaluation_runs (
                session_id BIGINT NOT NULL, competency_code TEXT NOT NULL,
                shadow_agent_code TEXT NOT NULL, shadow_agent_version INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO user_sessions (id, user_id, status, analysis_completed_at, execution_snapshot_json)
            VALUES (1, 11, 'completed', NOW() - INTERVAL '1 minute', %s::jsonb),
                   (2, 22, 'completed', NOW(), %s::jsonb)
            """,
            (json.dumps(snapshot), json.dumps(snapshot)),
        )
        connection.execute(
            """
            INSERT INTO assessment_shadow_evaluation_runs
                (session_id, competency_code, shadow_agent_code, shadow_agent_version)
            VALUES (2, 'communication', 'communication_shadow', 2)
            """
        )

        targets = AssessmentShadowBatchService()._select_targets(connection=connection, limit=4)

        assert [(item["session_id"], item["competency"]["code"]) for item in targets] == [
            (1, "communication")
        ]
        connection.execute("DROP TABLE assessment_shadow_evaluation_runs")
        connection.execute("DROP TABLE user_sessions")
