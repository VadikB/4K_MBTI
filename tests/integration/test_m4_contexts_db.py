from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.assessment_contexts import (
    confirm_user_context,
    create_organization_context_draft,
    create_user_context_draft,
    publish_organization_context,
)
from Api.database import ensure_assessment_context_schema, ensure_role_profile_schema


@pytest.mark.integration
def test_m4_context_schema_enforces_one_organization_and_frozen_versions(test_database_url) -> None:
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m4_test_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations (id BIGINT PRIMARY KEY, is_active BOOLEAN NOT NULL)")
        connection.execute(
            "CREATE TABLE organization_memberships ("
            "organization_id BIGINT REFERENCES organizations(id), user_id BIGINT REFERENCES users(id), "
            "UNIQUE (organization_id, user_id))"
        )
        connection.execute(
            "CREATE TABLE user_sessions (id BIGINT PRIMARY KEY, user_id BIGINT REFERENCES users(id), "
            "execution_snapshot_json JSONB, execution_checksum TEXT)"
        )
        connection.execute("CREATE TABLE assessment_methodologies (id BIGINT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE assessment_methodology_versions ("
            "id BIGINT PRIMARY KEY, methodology_id BIGINT REFERENCES assessment_methodologies(id), "
            "status TEXT, definition_json JSONB)"
        )
        connection.execute(
            "CREATE TABLE assessment_configurations ("
            "id BIGINT PRIMARY KEY, methodology_version_id BIGINT REFERENCES assessment_methodology_versions(id), status TEXT)"
        )
        connection.execute("CREATE TABLE assessment_preparation_jobs (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (1), (2)")
        connection.execute("INSERT INTO organizations VALUES (10, TRUE), (20, TRUE)")

        ensure_role_profile_schema(connection)
        ensure_assessment_context_schema(connection)

        connection.execute("INSERT INTO organization_memberships VALUES (10, 1)")
        with pytest.raises(psycopg.errors.UniqueViolation):
            with connection.transaction():
                connection.execute("INSERT INTO organization_memberships VALUES (20, 1)")

        organization_definition = {
            "name": "Организация", "organization_type": "компания", "industry": "образование",
            "activity_description": "Образовательные программы", "case_reality_level": "обобщённый",
            "organization_name_usage_rules": "не использовать название",
        }
        version_id = create_organization_context_draft(
            connection, organization_id=10, definition=organization_definition,
        )
        publish_organization_context(connection, version_id=version_id, confirmed_by_user_id=2)
        with pytest.raises(psycopg.Error, match="immutable"):
            with connection.transaction():
                connection.execute(
                    "UPDATE assessment_organization_context_versions SET definition_json = '{\"changed\": true}'::jsonb WHERE id = %s",
                    (version_id,),
                )

        user_version_id = create_user_context_draft(
            connection,
            user_id=1,
            identity={"full_name": "Иван Иванов", "contacts": "private@example.test"},
            professional={"position_or_status": "Эксперт"},
        )
        confirm_user_context(connection, version_id=user_version_id, user_id=1)
        stored = connection.execute(
            "SELECT status, identity_json, professional_context_json FROM assessment_user_context_versions WHERE id = %s",
            (user_version_id,),
        ).fetchone()
        assert stored["status"] == "confirmed"
        assert stored["identity_json"]["contacts"] == "private@example.test"
        assert "contacts" not in stored["professional_context_json"]
        connection.rollback()
