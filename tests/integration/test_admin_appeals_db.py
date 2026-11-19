from uuid import uuid4
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import psycopg
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from Api import acquaintance, appeals, routes
from Api.database import ensure_appeals_schema
from Api.org_access import AdminScope


@pytest.mark.integration
def test_report_retry_and_same_text_in_new_assignment(test_database_url, monkeypatch) -> None:
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "appeals_scope_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)")
        connection.execute("INSERT INTO users VALUES(1),(2)")
        connection.execute("INSERT INTO organizations VALUES(10)")
        connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin')")
        ensure_appeals_schema(connection)
        assignment = {"id": 11}
        monkeypatch.setattr(acquaintance, "early_readiness", lambda *_args, **_kwargs: {
            "status": "ready", "organization_id": 10, "assignment_ref": "program-a",
            "assignment_id": assignment["id"], "questionnaire_revision_id": 3})
        first = acquaintance.report_issue(connection, user_id=1, message="Неточная роль")
        assert acquaintance.report_issue(connection, user_id=1, message="Неточная роль")["id"] == first["id"]
        assignment["id"] = 12
        second = acquaintance.report_issue(connection, user_id=1, message="Неточная роль")
        assert second["id"] != first["id"]
        assert connection.execute("SELECT COUNT(*) AS n FROM participant_data_issue_reports").fetchone()["n"] == 2
        connection.rollback()


@pytest.mark.integration
def test_concurrent_claims_have_one_owner(test_database_url) -> None:
    schema = "appeals_race_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)")
        connection.execute("INSERT INTO users VALUES(1),(2),(3)")
        connection.execute("INSERT INTO organizations VALUES(10)")
        connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin'),(10,3,'admin')")
        ensure_appeals_schema(connection)
        issue_id = connection.execute("""INSERT INTO participant_data_issue_reports(user_id,organization_id,message)
            VALUES(1,10,'Ошибка') RETURNING id""").fetchone()["id"]
        connection.commit()
    gate = Barrier(2)

    def attempt(actor_id):
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            gate.wait(timeout=5)
            claimed = appeals.claim_issue(connection, organization_id=10, user_id=1,
                                          issue_id=issue_id, actor_id=actor_id)
            connection.commit()
            return claimed

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, (2, 3)))
        assert sum(value is not None for value in outcomes) == 1
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            owner = connection.execute("SELECT claimed_by_user_id FROM participant_data_issue_reports WHERE id=%s",
                                       (issue_id,)).fetchone()["claimed_by_user_id"]
            assert owner == next(value["claimed_by_user_id"] for value in outcomes if value)
    finally:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


@pytest.mark.integration
def test_http_owner_tenant_claim_reply_and_readback(test_database_url, monkeypatch) -> None:
    schema = "appeals_http_" + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)")
        connection.execute("INSERT INTO users VALUES(1),(2),(3),(4)")
        connection.execute("INSERT INTO organizations VALUES(10),(20)")
        connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin'),(20,3,'admin'),(20,4,'member')")
        ensure_appeals_schema(connection)
        issue_id = connection.execute("""INSERT INTO participant_data_issue_reports
            (user_id,organization_id,scope_key,assignment_ref,assignment_id,questionnaire_revision_id,message)
            VALUES(1,10,'[\"a\",1,11]','a',11,1,'Неточная роль') RETURNING id""").fetchone()["id"]
        connection.commit()

    @contextmanager
    def get_connection():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            yield connection

    users = {"participant": 1, "admin": 2, "other-admin": 3, "other-member": 4}
    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id=users[token], email=f"{token}@example.test") if token in users else None)

    def scope(_connection, user, **_kwargs):
        if user is None:
            raise HTTPException(401)
        if user.id == 2:
            return AdminScope(organization_ids=(10,), actor_user_id=2)
        if user.id == 3:
            return AdminScope(organization_ids=(20,), actor_user_id=3)
        raise HTTPException(403)

    monkeypatch.setattr(routes, "_get_admin_scope_or_403", scope)
    app = FastAPI(); app.include_router(routes.router)
    base = f"/users/admin/organizations/10/members/1/issues"
    try:
        with TestClient(app) as http:
            assert http.get("/users/1/acquaintance/issues").status_code == 401
            http.cookies.set(routes.SESSION_COOKIE_NAME, "other-member")
            assert http.get("/users/1/acquaintance/issues").status_code == 403
            assert http.get(base).status_code == 403
            http.cookies.set(routes.SESSION_COOKIE_NAME, "other-admin")
            assert http.get(base).status_code == 403
            http.cookies.set(routes.SESSION_COOKIE_NAME, "admin")
            assert http.get(base.replace("members/1/", "members/4/")).status_code == 404
            assert http.get(base).json()["items"][0]["message"] == "Неточная роль"
            assert http.post(f"{base}/{issue_id}/claim").status_code == 200
            sent = http.post(f"{base}/{issue_id}/reply", json={"message": "Исправим запись"})
            assert sent.status_code == 200
            assert http.post(f"{base}/{issue_id}/reply", json={"message": "Исправим запись"}).json()["created_at"] == sent.json()["created_at"]
            with get_connection() as connection:
                connection.execute("DELETE FROM organization_memberships WHERE organization_id=10 AND user_id=1")
                connection.commit()
            http.cookies.set(routes.SESSION_COOKIE_NAME, "participant")
            own = http.get("/users/1/acquaintance/issues")
            assert own.status_code == 200
            assert own.json()["items"][0]["reply_message"] == "Исправим запись"
            assert own.json()["items"][0]["assignment_id"] == 11
    finally:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


@pytest.mark.integration
def test_legacy_report_migration_preserves_data_and_allows_scoped_duplicate(test_database_url) -> None:
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "appeals_legacy_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES(1)")
        connection.execute("INSERT INTO organizations VALUES(10)")
        connection.execute("""CREATE TABLE participant_data_issue_reports(
            id BIGSERIAL PRIMARY KEY,user_id BIGINT REFERENCES users(id),organization_id BIGINT REFERENCES organizations(id),
            message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),resolved_at TIMESTAMP,
            UNIQUE(user_id,organization_id,message))""")
        old = connection.execute("""INSERT INTO participant_data_issue_reports(user_id,organization_id,message,status)
            VALUES(1,10,'Неточная роль','resolved') RETURNING id,message,status,created_at""").fetchone()
        ensure_appeals_schema(connection)
        ensure_appeals_schema(connection)
        migrated = connection.execute("SELECT * FROM participant_data_issue_reports WHERE id=%s", (old["id"],)).fetchone()
        assert (migrated["message"], migrated["status"], migrated["created_at"], migrated["scope_key"]) == (
            old["message"], old["status"], old["created_at"], "legacy")
        assert migrated["assignment_ref"] is None
        connection.execute("""INSERT INTO participant_data_issue_reports
            (user_id,organization_id,scope_key,assignment_ref,questionnaire_revision_id,message)
            VALUES(1,10,'[\"a\",1]','a',1,'Неточная роль')""")
        assert connection.execute("SELECT COUNT(*) AS n FROM participant_data_issue_reports").fetchone()["n"] == 2
        connection.rollback()


@pytest.mark.integration
def test_claim_reply_retry_and_revoked_owner(test_database_url) -> None:
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "appeals_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        connection.execute("CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT)")
        connection.execute("""CREATE TABLE participant_data_issue_reports(
            id BIGSERIAL PRIMARY KEY,user_id BIGINT,organization_id BIGINT,scope_key TEXT NOT NULL,
            assignment_ref TEXT,questionnaire_revision_id BIGINT,assignment_id BIGINT,message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            claimed_by_user_id BIGINT,claimed_at TIMESTAMP,resolved_at TIMESTAMP,
            UNIQUE(user_id,organization_id,scope_key,message))""")
        connection.execute("""CREATE TABLE participant_data_issue_replies(
            issue_id BIGINT PRIMARY KEY,author_user_id BIGINT,message TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        connection.execute("INSERT INTO users VALUES(1),(2),(3)")
        connection.execute("INSERT INTO organizations VALUES(10),(20)")
        connection.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(10,2,'admin'),(10,3,'admin')")
        first = connection.execute("""INSERT INTO participant_data_issue_reports
            (user_id,organization_id,scope_key,assignment_ref,questionnaire_revision_id,message)
            VALUES(1,10,'[\"a\",1]','a',1,'Ошибка') RETURNING id""").fetchone()["id"]
        second = connection.execute("""INSERT INTO participant_data_issue_reports
            (user_id,organization_id,scope_key,assignment_ref,questionnaire_revision_id,message)
            VALUES(1,10,'[\"b\",2]','b',2,'Ошибка') RETURNING id""").fetchone()["id"]
        assert first != second
        assert len(appeals.list_issues(connection, organization_id=10, user_id=1)) == 2
        assert appeals.list_issues(connection, organization_id=20, user_id=1) == []
        assert appeals.claim_issue(connection, organization_id=10, user_id=1, issue_id=first, actor_id=2)
        assert appeals.claim_issue(connection, organization_id=10, user_id=1, issue_id=first, actor_id=3) is None
        assert appeals.claim_issue(connection, organization_id=20, user_id=1, issue_id=first, actor_id=3) is None
        connection.execute("UPDATE organization_memberships SET role='member' WHERE organization_id=10 AND user_id=2")
        assert appeals.claim_issue(connection, organization_id=10, user_id=1, issue_id=first, actor_id=3)
        receipt = appeals.reply_to_issue(connection, organization_id=10, user_id=1, issue_id=first,
                                          actor_id=3, message="Исправим запись")
        assert receipt["author_user_id"] == 3
        retry = appeals.reply_to_issue(connection, organization_id=10, user_id=1, issue_id=first,
                                        actor_id=3, message="Исправим запись")
        assert retry["created_at"] == receipt["created_at"]
        assert connection.execute("SELECT COUNT(*) AS n FROM participant_data_issue_replies").fetchone()["n"] == 1
        assert appeals.list_issues(connection, organization_id=10, user_id=1)[1]["reply_message"] == "Исправим запись"
        connection.rollback()
