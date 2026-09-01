from __future__ import annotations

import psycopg
import pytest

from scripts.cleanup_removed_personality_schema import cleanup_removed_schema, verify_removed_schema


@pytest.mark.integration
def test_cleanup_removes_retired_schema_and_is_idempotent(test_database_url: str) -> None:
    with psycopg.connect(test_database_url) as connection:
        connection.execute("DROP TABLE IF EXISTS session_mbti_refinements CASCADE")
        connection.execute("DROP TABLE IF EXISTS session_case_results CASCADE")
        connection.execute("DROP TABLE IF EXISTS user_sessions CASCADE")
        connection.execute("DROP TABLE IF EXISTS llm_prompts CASCADE")
        connection.execute(
            "CREATE TABLE user_sessions (id BIGSERIAL PRIMARY KEY, mbti_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb)"
        )
        connection.execute(
            """
            CREATE TABLE session_case_results (
                id BIGSERIAL PRIMARY KEY,
                mbti_case_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                mbti_followup_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
                mbti_followup_answers JSONB NOT NULL DEFAULT '[]'::jsonb
            )
            """
        )
        connection.execute("CREATE TABLE session_mbti_refinements (id BIGSERIAL PRIMARY KEY)")
        connection.execute("CREATE TABLE llm_prompts (prompt_code TEXT PRIMARY KEY)")
        connection.execute(
            "INSERT INTO llm_prompts (prompt_code) VALUES ('mbti.system'), ('assessment.system')"
        )

        first_result = cleanup_removed_schema(connection)
        verify_removed_schema(connection)
        second_result = cleanup_removed_schema(connection)
        verify_removed_schema(connection)

        remaining_prompts = connection.execute("SELECT prompt_code FROM llm_prompts ORDER BY prompt_code").fetchall()
        assert first_result == {"prompts_deleted": 1, "tables_dropped": 1, "columns_dropped": 4}
        assert second_result == {"prompts_deleted": 0, "tables_dropped": 0, "columns_dropped": 0}
        assert remaining_prompts == [("assessment.system",)]

        connection.execute("DROP TABLE IF EXISTS session_case_results CASCADE")
        connection.execute("DROP TABLE IF EXISTS user_sessions CASCADE")
        connection.execute("DROP TABLE IF EXISTS llm_prompts CASCADE")
        connection.commit()
