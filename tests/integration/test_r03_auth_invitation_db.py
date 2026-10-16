from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
import threading
import time
import uuid
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes
from Api import web_session_service as session_module
from Api.org_access import AdminScope
from Api.organization_invitation_service import hash_invitation_token


pytestmark = pytest.mark.integration


@pytest.fixture(params=["UTC", "Europe/Moscow"])
def invitation_database(test_database_url, monkeypatch, request):
    schema = "r03_fix2_" + uuid.uuid4().hex
    with psycopg.connect(test_database_url) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGSERIAL PRIMARY KEY, email TEXT NOT NULL)")
        connection.execute("CREATE TABLE auth_password_credentials(email TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE organizations(id BIGSERIAL PRIMARY KEY, code TEXT UNIQUE, name TEXT, invitation_intro TEXT, is_active BOOLEAN NOT NULL DEFAULT TRUE)")
        connection.execute("""CREATE TABLE organization_memberships(
            organization_id BIGINT NOT NULL REFERENCES organizations(id), user_id BIGINT NOT NULL REFERENCES users(id),
            role TEXT NOT NULL, admission_source TEXT NOT NULL, PRIMARY KEY(organization_id,user_id))""")
        connection.execute("""CREATE TABLE organization_invitations(
            id BIGSERIAL PRIMARY KEY, organization_id BIGINT NOT NULL REFERENCES organizations(id), token_hash TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL, revoked_at TIMESTAMP, created_by_user_id BIGINT REFERENCES users(id), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            recipient_email TEXT, purpose TEXT NOT NULL DEFAULT 'shared_access', used_at TIMESTAMP,
            delivery_status TEXT NOT NULL DEFAULT 'not_sent', delivery_error TEXT, sent_at TIMESTAMP,
            delivery_started_at TIMESTAMP, request_id TEXT, assignment_ref TEXT)""")
        connection.execute("""CREATE UNIQUE INDEX uq_r03_operation ON organization_invitations(
            organization_id,LOWER(recipient_email),request_id) WHERE purpose='personal_registration' AND request_id IS NOT NULL""")
        admin = connection.execute("INSERT INTO users(email) VALUES('admin@example.test') RETURNING id").fetchone()[0]
        member = connection.execute("INSERT INTO users(email) VALUES('person@example.test') RETURNING id").fetchone()[0]
        organization = connection.execute("INSERT INTO organizations(code,name) VALUES('r03','R03') RETURNING id").fetchone()[0]
        connection.execute("INSERT INTO organization_memberships VALUES(%s,%s,'admin','configured_admin')", (organization, admin))
        connection.execute("INSERT INTO organization_memberships VALUES(%s,%s,'member','admin_add')", (organization, member))
        connection.commit()

    @contextmanager
    def connection_factory():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
            connection.execute("SELECT set_config('TimeZone', %s, false)", (request.param,))
            yield connection

    monkeypatch.setattr(routes, "get_connection", connection_factory)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=admin, email="admin@example.test"))
    monkeypatch.setattr(routes, "get_admin_scope", lambda _connection, _user: AdminScope(organization_ids=(organization,)))
    monkeypatch.setattr(routes.settings, "auth_magic_link_dev_mode", False)
    monkeypatch.setattr(routes.settings, "email_provider", "controlled-sink")
    monkeypatch.setattr(routes.settings, "auth_invitation_token_secret", "integration-secret-that-is-at-least-32-characters")
    monkeypatch.setattr(
        routes.questionnaire_sources, "assignment_readiness",
        lambda *_args, **_kwargs: {"status": "ready"},
    )
    app = FastAPI()
    app.include_router(routes.router)
    yield test_database_url, schema, organization, app
    with psycopg.connect(test_database_url) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()


def _send(app, organization_id, operation_id, email="person@example.test"):
    with TestClient(app) as client:
        return client.post(
            f"/users/admin/organizations/{organization_id}/personal-invitations",
            json={"emails": [email], "operation_id": operation_id},
            headers={"Idempotency-Key": operation_id},
        )


def test_same_operation_is_serialized_and_lost_response_is_replayed(invitation_database, monkeypatch):
    database_url, schema, organization_id, app = invitation_database
    sent = []
    lock = threading.Lock()

    def sink(**payload):
        time.sleep(0.05)
        with lock:
            sent.append(payload)

    monkeypatch.setattr(routes, "send_auth_action_email", sink)
    operation = "r03-parallel-operation"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: _send(app, organization_id, operation), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    assert {response.json()["items"][0]["status"] for response in responses} == {"accepted"}
    assert len(sent) == 1
    token = parse_qs(urlparse(sent[0]["action_url"]).query)["invite"][0]
    with TestClient(app) as client:
        resolved = client.get(f"/users/organization-invitations/{token}")
    assert resolved.status_code == 200
    assert resolved.json()["organization_id"] == organization_id
    replay = _send(app, organization_id, operation, "PERSON@EXAMPLE.TEST")
    assert replay.json()["items"][0]["invitation_id"] == responses[0].json()["items"][0]["invitation_id"]
    assert len(sent) == 1
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        row = connection.execute("SELECT delivery_status,expires_at-created_at AS ttl FROM organization_invitations").fetchone()
        assert row["delivery_status"] == "accepted"
        assert 71.99 <= row["ttl"].total_seconds() / 3600 <= 72.01


def test_personal_invitation_ttl_is_snapshotted_per_created_invitation(invitation_database, monkeypatch):
    database_url, schema, organization_id, app = invitation_database
    monkeypatch.setattr(routes, "send_auth_action_email", lambda **_payload: None)
    monkeypatch.setattr(routes.settings, "auth_personal_invitation_ttl_hours", 5)
    first = _send(app, organization_id, "ttl-five-hours")
    assert first.status_code == 200
    first_id = first.json()["items"][0]["invitation_id"]

    monkeypatch.setattr(routes.settings, "auth_personal_invitation_ttl_hours", 9)
    replay = _send(app, organization_id, "ttl-five-hours")
    second = _send(app, organization_id, "ttl-nine-hours", "admin@example.test")
    assert second.status_code == 200
    assert replay.json()["items"][0]["invitation_id"] == first_id

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        rows = connection.execute(
            "SELECT id,expires_at-created_at AS ttl FROM organization_invitations ORDER BY id"
        ).fetchall()
    assert len(rows) == 2
    assert 4.99 <= rows[0]["ttl"].total_seconds() / 3600 <= 5.01
    assert 8.99 <= rows[1]["ttl"].total_seconds() / 3600 <= 9.01


def test_inactive_organization_neither_creates_nor_sends(invitation_database, monkeypatch):
    database_url, schema, organization_id, app = invitation_database
    with psycopg.connect(database_url) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        connection.execute("UPDATE organizations SET is_active=FALSE WHERE id=%s", (organization_id,))
        connection.commit()
    sent = []
    monkeypatch.setattr(routes, "send_auth_action_email", lambda **payload: sent.append(payload))
    response = _send(app, organization_id, "inactive-before-request")
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "error"
    assert sent == []
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        assert connection.execute("SELECT count(*) AS n FROM organization_invitations").fetchone()["n"] == 0


def test_deactivation_after_provider_acceptance_is_uncertain_and_link_is_not_resolved(invitation_database, monkeypatch):
    database_url, schema, organization_id, app = invitation_database
    sent = []

    def sink(**payload):
        sent.append(payload)
        with psycopg.connect(database_url) as connection:
            connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
            connection.execute("UPDATE organizations SET is_active=FALSE WHERE id=%s", (organization_id,))
            connection.commit()

    monkeypatch.setattr(routes, "send_auth_action_email", sink)
    response = _send(app, organization_id, "inactive-after-provider")
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "uncertain"
    assert len(sent) == 1
    token = parse_qs(urlparse(sent[0]["action_url"]).query)["invite"][0]
    with TestClient(app) as client:
        assert client.get(f"/users/organization-invitations/{token}").status_code == 404
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        assert connection.execute("SELECT delivery_status FROM organization_invitations").fetchone()["delivery_status"] == "sending"


def test_unknown_outcome_is_not_sent_twice(invitation_database, monkeypatch):
    database_url, schema, organization_id, app = invitation_database
    operation = "r03-recover-queued"
    monkeypatch.setattr(routes, "send_auth_action_email", lambda **_payload: (_ for _ in ()).throw(RuntimeError("controlled stop before acceptance")))
    with pytest.raises(RuntimeError, match="controlled stop"):
        _send(app, organization_id, operation)
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        assert connection.execute("SELECT delivery_status FROM organization_invitations").fetchone()["delivery_status"] == "sending"

    sent = []
    monkeypatch.setattr(routes, "send_auth_action_email", lambda **payload: sent.append(payload))
    response = _send(app, organization_id, operation)
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "uncertain"
    assert len(sent) == 0


def test_selected_organization_survives_session_restore_and_access_recheck(invitation_database, monkeypatch):
    database_url, schema, organization_id, _app = invitation_database
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        user_id = connection.execute("SELECT id FROM users WHERE email='person@example.test'").fetchone()["id"]
        second_id = connection.execute("INSERT INTO organizations(code,name) VALUES('r03-second','Second') RETURNING id").fetchone()["id"]
        connection.execute("INSERT INTO organization_memberships VALUES(%s,%s,'member','admin_add')", (second_id, user_id))
        connection.commit()

    @contextmanager
    def session_connection():
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
            yield connection

    monkeypatch.setattr(session_module, "get_connection", session_connection)
    token = session_module.web_session_service.create_session(user_id, selected_organization_id=second_id)
    assert session_module.web_session_service.selected_organization_id(token) == second_id
    with session_connection() as connection:
        context = routes._organization_context_for_user(connection, user_id, second_id)
        assert context.organization_id == second_id
        connection.execute("DELETE FROM organization_memberships WHERE organization_id=%s AND user_id=%s", (second_id, user_id))
        connection.commit()
    with session_connection() as connection:
        assert routes._organization_context_for_user(connection, user_id, second_id) is None


def test_invitation_expiry_boundary_and_consumed_history_are_timezone_stable(invitation_database):
    database_url, schema, organization_id, app = invitation_database
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        connection.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        exact_token = "r04-exact-boundary"
        active_token = "r04-before-boundary"
        consumed_token = "r04-consumed-history"
        exact_id = connection.execute("""INSERT INTO organization_invitations(
            organization_id,token_hash,expires_at,recipient_email,purpose,delivery_status,sent_at)
            VALUES(%s,%s,CURRENT_TIMESTAMP AT TIME ZONE 'UTC','person@example.test','personal_registration','accepted',NOW()) RETURNING id""",
            (organization_id, hash_invitation_token(exact_token))).fetchone()["id"]
        connection.execute("""INSERT INTO organization_invitations(
            organization_id,token_hash,expires_at,recipient_email,purpose,delivery_status,sent_at)
            VALUES(%s,%s,(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')+INTERVAL '1 minute','person@example.test','personal_registration','accepted',NOW())""",
            (organization_id, hash_invitation_token(active_token)))
        consumed_id = connection.execute("""INSERT INTO organization_invitations(
            organization_id,token_hash,expires_at,recipient_email,purpose,delivery_status,sent_at,used_at)
            VALUES(%s,%s,(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')-INTERVAL '1 minute','person@example.test','personal_registration','accepted',NOW(),NOW()) RETURNING id""",
            (organization_id, hash_invitation_token(consumed_token))).fetchone()["id"]
        connection.commit()
    with TestClient(app) as client:
        assert client.get(f"/users/organization-invitations/{exact_token}").status_code == 410
        assert client.get(f"/users/organization-invitations/{active_token}").status_code == 200
    assert routes._public_invitation_by_id(consumed_id).organization_id == organization_id
    assert routes._public_invitation_by_id(exact_id) is None
