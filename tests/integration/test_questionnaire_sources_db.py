from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_questionnaire_source_schema
from Api.questionnaire_sources import (
    admin_assignment_readiness, assignment_readiness, confirm, public_revision, save_preview,
)
from Api.m8_report_access import ensure_schema as ensure_report_access_schema


pytestmark = pytest.mark.integration
EXAMPLE = Path("assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv")


def test_csv_preview_confirmation_is_idempotent_and_publishes_provenance(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "questionnaire_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY,full_name TEXT,email TEXT)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN DEFAULT TRUE)")
        connection.execute("CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)")
        connection.execute("""CREATE TABLE organization_invitations(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT,recipient_email TEXT,purpose TEXT,
            assignment_ref TEXT,created_by_user_id BIGINT,revoked_at TIMESTAMP)""")
        connection.execute("""CREATE TABLE participant_acquaintance_confirmations(
            id BIGSERIAL PRIMARY KEY,user_id BIGINT,organization_id BIGINT,assignment_ref TEXT,
            personalized_profile_id BIGINT,confirmed_at TIMESTAMP DEFAULT NOW())""")
        connection.execute("""CREATE TABLE assessment_preparation_jobs(
            id BIGSERIAL PRIMARY KEY,user_id BIGINT,status TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        connection.execute("CREATE TABLE m5_cycles(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE m8_reports(id UUID PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES(1,'Участник','participant@example.test'),(2,'Администратор','admin@example.test')")
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
        ensure_report_access_schema(connection)
        connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin')")
        connection.execute("""INSERT INTO organization_invitations(
            organization_id,recipient_email,purpose,assignment_ref,created_by_user_id,revoked_at)
            VALUES
              (10,'participant@example.test','personal_registration','synthetic-assignment',2,NULL),
              (10,'admin@example.test','personal_registration','synthetic-assignment',1,NULL),
              (10,'participant@example.test','personal_registration','second-assignment',2,NULL),
              (10,'admin@example.test','personal_registration','second-assignment',1,NOW())""")

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
            confirmed_by=2, recipients=["participant", "organization_admin"], recipient_user_ids=[2],
        )
        assert confirmed["status"] == "confirmed"
        version = connection.execute(
            "SELECT * FROM assessment_organization_context_versions WHERE id=%s",
            (confirmed["organization_context_version_id"],),
        ).fetchone()
        assert version["status"] == "published"
        assert "participant_briefing" not in version["definition_json"]
        assert confirmed["briefing_json"]["purpose"]
        assert confirmed["briefing_json"]["result_recipients"] == (
            "Результаты доступны участнику и выбранным представителям заказчика."
        )
        assert confirmed["briefing_json"]["recipient_mapping"] == ["organization_admin", "participant"]
        assert confirmed["briefing_json"]["authorized_recipients"] == [{
            "user_id": 2, "name": "Администратор", "email": "admin@example.test",
        }]
        assert confirmed["briefing_json"]["assignment_ref"] == "synthetic-assignment"
        assert version["source_manifest_json"]["questionnaire_revision_id"] == preview["id"]
        assert confirm(
            connection, revision_id=preview["id"], organization_id=10,
            confirmed_by=2, recipients=["participant"],
        )["organization_context_version_id"] == confirmed["organization_context_version_id"]

        stale = save_preview(connection, **{
            **kwargs, "idempotency_key": "preview-stale",
            "raw_text": EXAMPLE.read_text().replace(
                "Познакомиться с форматом оценки и получить развивающую обратную связь",
                "Устаревшая цель",
            ),
        })
        fresh = save_preview(connection, **{
            **kwargs, "idempotency_key": "preview-fresh",
            "raw_text": EXAMPLE.read_text().replace(
                "Познакомиться с форматом оценки и получить развивающую обратную связь",
                "Новая опубликованная цель",
            ),
        })
        projection = public_revision(fresh, confirmed_row=confirmed)
        assert projection["participant_preview"]["purpose"] == "Новая опубликованная цель"
        assert projection["is_first_publication"] is False
        assert {item["field"] for item in projection["changes"]} == {
            "purpose", "result_recipients",
        }
        assert "questionnaire_revision_id" not in projection["participant_preview"]
        confirm(connection, revision_id=fresh["id"], organization_id=10,
                confirmed_by=2, recipients=["participant"])
        with pytest.raises(ValueError, match="QUESTIONNAIRE_REVISION_CONFLICT"):
            confirm(connection, revision_id=stale["id"], organization_id=10,
                    confirmed_by=2, recipients=["participant"])

        second_kwargs = {
            **kwargs, "assignment_ref": "second-assignment", "idempotency_key": "preview-2",
            "raw_text": EXAMPLE.read_text().replace(
                "Познакомиться с форматом оценки и получить развивающую обратную связь",
                "Отдельная цель второй оценки",
            ),
        }
        second = save_preview(connection, **second_kwargs)
        confirm(connection, revision_id=second["id"], organization_id=10,
                confirmed_by=2, recipients=["participant"])
        first_ready = assignment_readiness(
            connection, organization_id=10, assignment_ref="synthetic-assignment",
        )
        second_ready = assignment_readiness(
            connection, organization_id=10, assignment_ref="second-assignment",
        )
        assert first_ready["briefing"]["purpose"] != second_ready["briefing"]["purpose"]
        first_admin = admin_assignment_readiness(
            connection, organization_id=10, assignment_ref="synthetic-assignment",
        )
        second_admin = admin_assignment_readiness(
            connection, organization_id=10, assignment_ref="second-assignment",
        )
        missing_admin = admin_assignment_readiness(
            connection, organization_id=10, assignment_ref="missing-assignment",
        )
        assert first_admin["assignment_ref"] == "synthetic-assignment"
        assert second_admin["assignment_ref"] == "second-assignment"
        assert first_admin["roles"]["total"] == 2
        assert second_admin["roles"]["total"] == 1
        assert missing_admin["roles"]["total"] == 0
        assert first_admin["early"]["status"] == second_admin["early"]["status"] == "ready"
        assert missing_admin["early"]["status"] == "data_missing"

        with pytest.raises(ValueError, match="QUESTIONNAIRE_REVISION_NOT_FOUND"):
            confirm(
                connection, revision_id=preview["id"], organization_id=20,
                confirmed_by=2, recipients=["participant"],
            )
        connection.rollback()
