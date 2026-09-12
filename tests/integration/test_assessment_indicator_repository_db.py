from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.assessment_indicator_repository import AssessmentIndicatorResultRepository
from Api.assessment_service import freeze_session_case_indicators
from tests.unit.test_assessment_indicator_repository import input_data, output


TABLES = (
    "session_case_indicator_evidence",
    "session_indicator_assessments",
    "session_case_indicators",
    "case_registry_indicators",
    "session_cases",
    "user_sessions",
    "assessment_methodology_versions",
    "users",
)


@pytest.fixture
def indicator_connection(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        for table in TABLES:
            connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE user_sessions (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))")
        connection.execute("CREATE TABLE session_cases (id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES user_sessions(id))")
        connection.execute("CREATE TABLE assessment_methodology_versions (id BIGINT PRIMARY KEY)")
        connection.execute(
            """CREATE TABLE case_registry_indicators (
                cases_registry_id INTEGER, methodology_version_id BIGINT,
                indicator_code TEXT, signal_priority TEXT, is_required BOOLEAN, display_order INTEGER
            )"""
        )
        connection.execute(
            """CREATE TABLE session_case_indicators (
                session_case_id INTEGER, methodology_version_id BIGINT, indicator_code TEXT,
                signal_priority TEXT, is_required BOOLEAN, display_order INTEGER,
                UNIQUE (session_case_id, methodology_version_id, indicator_code)
            )"""
        )
        connection.execute(
            """
            CREATE TABLE session_indicator_assessments (
                id BIGSERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                methodology_version_id BIGINT NOT NULL REFERENCES assessment_methodology_versions(id),
                competency_code TEXT NOT NULL, skill_code TEXT NOT NULL,
                component_code TEXT NOT NULL, indicator_code TEXT NOT NULL,
                evidence_state TEXT NOT NULL CHECK (evidence_state IN ('observed', 'insufficient_evidence', 'not_assessed')),
                assessed_level_code TEXT CHECK (assessed_level_code IN ('L0', 'L1', 'L2', 'L3')),
                red_flag_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
                rationale TEXT NOT NULL,
                confidence DOUBLE PRECISION CHECK (confidence >= 0 AND confidence <= 1),
                source_session_case_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                evaluated_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (session_id, methodology_version_id, indicator_code),
                CHECK ((evidence_state = 'observed' AND assessed_level_code IS NOT NULL)
                    OR (evidence_state <> 'observed' AND assessed_level_code IS NULL))
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE session_case_indicator_evidence (
                id BIGSERIAL PRIMARY KEY,
                session_indicator_assessment_id BIGINT NOT NULL REFERENCES session_indicator_assessments(id) ON DELETE CASCADE,
                session_case_id INTEGER NOT NULL REFERENCES session_cases(id) ON DELETE CASCADE,
                observation TEXT NOT NULL, evidence_excerpt TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (session_indicator_assessment_id, session_case_id, observation, evidence_excerpt)
            )
            """
        )
        connection.execute("INSERT INTO users VALUES (7)")
        connection.execute("INSERT INTO user_sessions VALUES (42, 7)")
        connection.execute("INSERT INTO session_cases VALUES (31, 42)")
        connection.execute("INSERT INTO assessment_methodology_versions VALUES (2)")
        connection.execute(
            "INSERT INTO case_registry_indicators VALUES (41, 2, 'K1.I01', 'leading', TRUE, 1)"
        )
        yield connection
    with psycopg.connect(test_database_url) as connection:
        for table in TABLES:
            connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


@pytest.mark.integration
def test_indicator_repository_is_idempotent(indicator_connection) -> None:
    repository = AssessmentIndicatorResultRepository()
    repository.save(connection=indicator_connection, input_data=input_data(), output=output())
    repository.save(connection=indicator_connection, input_data=input_data(), output=output())

    assessment_count = indicator_connection.execute(
        "SELECT COUNT(*) AS count FROM session_indicator_assessments"
    ).fetchone()["count"]
    evidence_count = indicator_connection.execute(
        "SELECT COUNT(*) AS count FROM session_case_indicator_evidence"
    ).fetchone()["count"]
    row = indicator_connection.execute(
        "SELECT evidence_state, assessed_level_code FROM session_indicator_assessments"
    ).fetchone()

    assert assessment_count == 1
    assert evidence_count == 1
    assert row == {"evidence_state": "observed", "assessed_level_code": "L0"}


@pytest.mark.integration
def test_case_indicator_snapshot_is_idempotent(indicator_connection) -> None:
    for _ in range(2):
        assert freeze_session_case_indicators(
            indicator_connection,
            session_case_id=31,
            case_registry_id=41,
            methodology_version_id=2,
            indicator_codes=["K1.I01"],
        ) == 1
    count = indicator_connection.execute(
        "SELECT COUNT(*) AS count FROM session_case_indicators"
    ).fetchone()["count"]
    assert count == 1
