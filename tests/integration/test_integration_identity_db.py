from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.integration_identity_service import resolve_or_provision_participant


pytestmark = pytest.mark.integration


def test_resolve_or_provision_is_idempotent_without_assessment_side_effects(
    test_database_url: str,
) -> None:
    schema = "tgbot_identity_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(
            psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
        )
        connection.execute(
            psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema))
        )
        connection.execute(
            """
            CREATE TABLE users(
                id BIGSERIAL PRIMARY KEY,
                full_name TEXT,
                email TEXT UNIQUE,
                role_id BIGINT,
                job_description TEXT,
                phone TEXT,
                company_industry TEXT
            )
            """
        )
        first = resolve_or_provision_participant(
            connection,
            email=" Student@Example.EDU ",
            display_name="Студент",
        )
        repeated = resolve_or_provision_participant(
            connection,
            email="student@example.edu",
            display_name="Другое имя",
        )

        assert first.created is True
        assert repeated.created is False
        assert repeated.agent4k_user_id == first.agent4k_user_id
        stored = connection.execute("SELECT * FROM users").fetchone()
        assert stored["full_name"] == "Студент"
        assert stored["email"] == "student@example.edu"
        assert stored["role_id"] is None
        assert stored["job_description"] is None
        connection.rollback()
