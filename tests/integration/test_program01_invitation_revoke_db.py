from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi import HTTPException

from Api import routes


pytestmark = pytest.mark.integration


@pytest.fixture
def invitation_db(test_database_url, monkeypatch):
    schema = "program01_r08_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url) as setup:
        setup.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        setup.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
        setup.execute("CREATE TABLE users(id BIGINT PRIMARY KEY,email TEXT NOT NULL)")
        setup.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY)")
        setup.execute("""CREATE TABLE organization_invitations(
            id BIGINT PRIMARY KEY,organization_id BIGINT NOT NULL,recipient_email TEXT,
            purpose TEXT NOT NULL,used_at TIMESTAMP,revoked_at TIMESTAMP)""")
        setup.execute("""CREATE TABLE participant_acquaintance_states(
            user_id BIGINT PRIMARY KEY,organization_id BIGINT NOT NULL,
            status TEXT NOT NULL,current_step INTEGER NOT NULL)""")
        setup.execute("INSERT INTO users VALUES(42,'participant@example.test')")
        setup.execute("INSERT INTO organizations VALUES(3),(4)")
        setup.execute("""INSERT INTO organization_invitations
            VALUES(7,3,'participant@example.test','personal_registration',NULL,NULL)""")
        setup.commit()

    @contextmanager
    def get_connection():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes, "_require_organization_admin", lambda *_args: None)
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda _token: SimpleNamespace(id=99),
    )
    try:
        yield schema, get_connection
    finally:
        with psycopg.connect(test_database_url) as cleanup:
            cleanup.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


def _request():
    return SimpleNamespace(cookies={routes.SESSION_COOKIE_NAME: "session"})


def _revoke(organization_id=3):
    return routes.revoke_personal_organization_invitation(organization_id, 7, _request())


def test_revoke_contract_covers_unused_replay_used_started_and_foreign_scope(invitation_db):
    _schema, get_connection = invitation_db

    assert _revoke() == {"ok": True}
    assert _revoke() == {"ok": True}
    with get_connection() as connection:
        connection.execute("UPDATE organization_invitations SET revoked_at=NULL,used_at=NOW() WHERE id=7")
        connection.commit()
    with pytest.raises(HTTPException) as used:
        _revoke()
    assert (used.value.status_code, used.value.detail) == (409, "INVITATION_ALREADY_USED")

    with get_connection() as connection:
        connection.execute("UPDATE organization_invitations SET used_at=NULL,revoked_at=NULL WHERE id=7")
        connection.execute("INSERT INTO participant_acquaintance_states VALUES(42,3,'in_progress',1)")
        connection.commit()
    with pytest.raises(HTTPException) as started:
        _revoke()
    assert (started.value.status_code, started.value.detail) == (409, "INVITATION_STATE_CHANGED")
    with get_connection() as connection:
        assert connection.execute("SELECT revoked_at FROM organization_invitations WHERE id=7").fetchone()["revoked_at"] is None

    with pytest.raises(HTTPException) as foreign:
        _revoke(4)
    assert (foreign.value.status_code, foreign.value.detail) == (404, "INVITATION_NOT_FOUND")


def test_concurrent_accept_wins_on_the_same_invitation_row(invitation_db, test_database_url):
    schema, _get_connection = invitation_db
    accepted = Event()
    release = Event()

    def accept_invitation():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            connection.execute("UPDATE organization_invitations SET used_at=NOW() WHERE id=7")
            accepted.set()
            assert release.wait(timeout=5)
            connection.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        accept_future = pool.submit(accept_invitation)
        assert accepted.wait(timeout=5)
        revoke_future = pool.submit(_revoke)
        release.set()
        accept_future.result(timeout=5)
        with pytest.raises(HTTPException) as changed:
            revoke_future.result(timeout=5)

    assert (changed.value.status_code, changed.value.detail) == (409, "INVITATION_ALREADY_USED")
    with _get_connection() as connection:
        row = connection.execute("SELECT used_at,revoked_at FROM organization_invitations WHERE id=7").fetchone()
    assert row["used_at"] is not None
    assert row["revoked_at"] is None
