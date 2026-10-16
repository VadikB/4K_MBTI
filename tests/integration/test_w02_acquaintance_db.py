from __future__ import annotations

import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.acquaintance import accept_consent, early_readiness, report_issue, save_answers


@pytest.mark.integration
def test_w02_readiness_answers_consent_and_tenant_issue_are_independent_from_m4(test_database_url) -> None:
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "w02_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY,email TEXT)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY,name TEXT,is_active BOOLEAN)")
        connection.execute("""CREATE TABLE organization_memberships(
            organization_id BIGINT,user_id BIGINT,role TEXT,UNIQUE(organization_id,user_id))""")
        connection.execute("""CREATE TABLE organization_invitations(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT,recipient_email TEXT,purpose TEXT,
            assignment_ref TEXT,revoked_at TIMESTAMP)""")
        connection.execute("""CREATE TABLE questionnaire_response_revisions(
            id BIGSERIAL PRIMARY KEY,organization_id BIGINT,assignment_ref TEXT,status TEXT,
            briefing_json JSONB,organization_context_version_id BIGINT,confirmed_at TIMESTAMP)""")
        connection.execute("""CREATE TABLE assessment_organization_contexts(
            id BIGINT PRIMARY KEY,organization_id BIGINT,code TEXT)""")
        connection.execute("""CREATE TABLE assessment_organization_context_versions(
            id BIGINT PRIMARY KEY,organization_context_id BIGINT,version INTEGER,status TEXT,definition_json JSONB)""")
        connection.execute("""CREATE TABLE participant_acquaintance_states(
            user_id BIGINT PRIMARY KEY,organization_id BIGINT NOT NULL,organization_context_version_id BIGINT,
            status TEXT NOT NULL DEFAULT 'not_started',current_step INTEGER NOT NULL DEFAULT 0,
            answers_json JSONB NOT NULL DEFAULT '{}'::jsonb,answers_confirmed_at TIMESTAMP,
            briefing_checksum TEXT,consent_version INTEGER,consent_accepted_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),updated_at TIMESTAMP NOT NULL DEFAULT NOW())""")
        connection.execute("""CREATE TABLE participant_data_issue_reports(
            id BIGSERIAL PRIMARY KEY,user_id BIGINT,organization_id BIGINT,message TEXT,status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP,UNIQUE(user_id,organization_id,message))""")
        connection.execute("""INSERT INTO users VALUES
            (1,'participant@example.test'),(2,'admin-a@example.test'),(3,'admin-b@example.test')""")
        connection.execute("INSERT INTO organizations VALUES(10,'Организация А',TRUE),(20,'Организация Б',TRUE)")
        connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin'),(20,3,'admin')")
        connection.execute("INSERT INTO assessment_organization_contexts VALUES(100,10,'default')")
        connection.execute("""INSERT INTO assessment_organization_context_versions
            VALUES(1000,100,1,'published',%s::jsonb)""", (json.dumps({
                "name": "Организация А", "organization_type": "компания",
            }),))

        waiting = early_readiness(connection, user_id=1)
        assert waiting["status"] == "waiting_for_organization"
        assert "participant_briefing" in waiting["reason"]

        briefing = {
            "purpose": "Развитие компетенций", "organizer": "Организация А",
            "results_usage": "Для персонального плана развития",
            "result_recipients": "Участник и назначенный администратор",
            "provided_participant_fields": [{"label": "Подразделение", "value": "Продукт"}],
            "participant_questions": ["Ваша роль?", "Типичные задачи?", "С кем взаимодействуете?"],
            "consent_version": 2, "consent_text": "Согласие v2",
        }
        connection.execute(
            "UPDATE assessment_organization_context_versions SET definition_json=%s::jsonb WHERE id=1000",
            (json.dumps({"name": "Организация А", "organization_type": "компания", "participant_briefing": briefing}),),
        )
        assert early_readiness(connection, user_id=1)["status"] == "ready"

        accept_consent(connection, user_id=1, version=2)
        save_answers(connection, user_id=1, answers={"answer_1": "Ответ 1"})
        save_answers(connection, user_id=1, answers={"answer_2": "Не знаю"})
        confirmed = save_answers(connection, user_id=1, answers={"answer_3": "Ответ 3"}, confirm=True)
        assert confirmed["answers_json"] == {
            "answer_1": "Ответ 1", "answer_2": "Не знаю", "answer_3": "Ответ 3",
        }
        assert confirmed["answers_confirmed_at"] is not None
        issue = report_issue(connection, user_id=1, message="Неточно указано подразделение")
        stored = connection.execute(
            "SELECT organization_id FROM participant_data_issue_reports WHERE id=%s", (issue["id"],),
        ).fetchone()
        assert stored["organization_id"] == 10
        connection.rollback()
