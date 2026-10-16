from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_questionnaire_source_schema
from Api.questionnaire_sources import confirm, save_preview


pytestmark = pytest.mark.integration
EXAMPLE = Path("assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv")


def test_csv_preview_confirmation_is_idempotent_and_publishes_provenance(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "questionnaire_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES(1),(2)")
        connection.execute("INSERT INTO organizations VALUES(10),(20)")
        connection.execute("""CREATE TABLE assessment_organization_contexts(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT NOT NULL REFERENCES organizations(id),
            code TEXT NOT NULL,created_at TIMESTAMP NOT NULL DEFAULT NOW(),UNIQUE(organization_id,code))""")
        connection.execute("""CREATE TABLE assessment_organization_context_versions(
            id BIGSERIAL PRIMARY KEY,organization_context_id BIGINT NOT NULL REFERENCES assessment_organization_contexts(id),
            version INTEGER NOT NULL,status TEXT NOT NULL,definition_json JSONB NOT NULL,
            source_manifest_json JSONB NOT NULL DEFAULT '{}'::jsonb,checksum TEXT NOT NULL,
            confirmed_by_user_id BIGINT REFERENCES users(id),confirmed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),UNIQUE(organization_context_id,version))""")
        ensure_questionnaire_source_schema(connection)

        kwargs = dict(
            organization_id=10, assignment_ref="synthetic-assignment", channel="csv",
            template_variant="corporate", template_version="0.1", answers={},
            raw_text=EXAMPLE.read_text(), uploaded_by=1,
            source_author="Синтетический заказчик", idempotency_key="preview-1",
        )
        preview = save_preview(connection, **kwargs)
        replay = save_preview(connection, **kwargs)
        assert preview["id"] == replay["id"]
        assert preview["status"] == "ready_for_confirmation"

        confirmed = confirm(
            connection, revision_id=preview["id"], organization_id=10,
            confirmed_by=2, recipients=["participant", "organization_admin"],
        )
        assert confirmed["status"] == "confirmed"
        version = connection.execute(
            "SELECT * FROM assessment_organization_context_versions WHERE id=%s",
            (confirmed["organization_context_version_id"],),
        ).fetchone()
        assert version["status"] == "published"
        assert version["definition_json"]["participant_briefing"]["purpose"]
        assert version["source_manifest_json"]["questionnaire_revision_id"] == preview["id"]
        assert confirm(
            connection, revision_id=preview["id"], organization_id=10,
            confirmed_by=2, recipients=["participant"],
        )["organization_context_version_id"] == confirmed["organization_context_version_id"]

        with pytest.raises(ValueError, match="QUESTIONNAIRE_REVISION_NOT_FOUND"):
            confirm(
                connection, revision_id=preview["id"], organization_id=20,
                confirmed_by=2, recipients=["participant"],
            )
        connection.rollback()
