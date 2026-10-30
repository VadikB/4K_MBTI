from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi import HTTPException

from Api import routes
from Api.schemas import AdminOrganizationsResponse, AdminOrganizationTransferRequest


pytestmark = pytest.mark.integration


@pytest.fixture
def transfer_db(test_database_url, monkeypatch):
    schema = "arch30_transfer_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url) as setup:
        setup.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        setup.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
        setup.execute("CREATE TABLE users(id BIGINT PRIMARY KEY,email TEXT NOT NULL)")
        setup.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY,name TEXT NOT NULL,is_active BOOLEAN NOT NULL)")
        setup.execute("""CREATE TABLE organization_memberships(
            organization_id BIGINT NOT NULL REFERENCES organizations(id),user_id BIGINT NOT NULL REFERENCES users(id),
            role TEXT NOT NULL,admission_source TEXT NOT NULL,admitted_by_user_id BIGINT,admitted_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_id))""")
        setup.execute("""CREATE TABLE configured_organization_membership_suppressions(
            user_id BIGINT NOT NULL,organization_id BIGINT NOT NULL,reason TEXT NOT NULL,
            created_by_user_id BIGINT,created_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(user_id,organization_id))""")
        setup.execute("""CREATE TABLE organization_assessment_assignments(
            organization_id BIGINT,recipient_user_id BIGINT,status TEXT,revoked_at TIMESTAMP)""")
        setup.execute("""CREATE TABLE organization_invitations(
            organization_id BIGINT,recipient_email TEXT,revoked_at TIMESTAMP)""")
        setup.execute("""CREATE TABLE participant_acquaintance_states(
            user_id BIGINT,organization_id BIGINT,status TEXT)""")
        setup.execute("CREATE TABLE web_user_sessions(token TEXT,user_id BIGINT)")
        setup.execute("""CREATE TABLE m5_cycles(
            cycle_id UUID,owner_user_id BIGINT,organization_id BIGINT,status TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        setup.execute("INSERT INTO users VALUES(7,'person@example.test'),(99,'actor@example.test'),(8,'other-admin@example.test')")
        setup.execute("INSERT INTO organizations VALUES(3,'Организация А',TRUE),(4,'Организация Б',TRUE),(5,'Неактивная',FALSE)")
        setup.commit()
    connection = psycopg.connect(test_database_url, row_factory=dict_row)
    connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
    connection.commit()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=99))
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)
    monkeypatch.setattr(
        routes,
        "_build_admin_organizations",
        lambda *_args: AdminOrganizationsResponse(title="Организации", subtitle="", items=[]),
    )
    try:
        yield connection
    finally:
        connection.close()
        with psycopg.connect(test_database_url) as cleanup:
            cleanup.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


def _request():
    return SimpleNamespace(cookies={routes.SESSION_COOKIE_NAME: "session"})


def _payload(target=4, role="member"):
    return AdminOrganizationTransferRequest(
        expected_source_organization_id=3,
        target_organization_id=target,
        target_role=role,
        operation_id="transfer-operation-1",
    )


def test_transfer_is_atomic_revokes_old_scope_and_suppresses_configured_admin(transfer_db):
    transfer_db.execute("INSERT INTO organization_memberships VALUES(3,7,'admin','configured_admin',99,NOW(),NOW())")
    transfer_db.execute("INSERT INTO organization_memberships VALUES(3,8,'admin','admin_add',99,NOW(),NOW())")
    transfer_db.execute("INSERT INTO organization_assessment_assignments VALUES(3,7,'active',NULL)")
    transfer_db.execute("INSERT INTO organization_invitations VALUES(3,'person@example.test',NULL)")
    transfer_db.execute("INSERT INTO participant_acquaintance_states VALUES(7,3,'completed')")
    transfer_db.execute("INSERT INTO web_user_sessions VALUES('old-session',7)")
    transfer_db.commit()

    routes.transfer_admin_organization_user(7, _payload(role="member"), _request())

    membership = transfer_db.execute("SELECT * FROM organization_memberships WHERE user_id=7").fetchone()
    assert membership["organization_id"] == 4
    assert membership["role"] == "member"
    assert membership["admission_source"] == "superadmin_transfer"
    assert transfer_db.execute("SELECT status FROM organization_assessment_assignments").fetchone()["status"] == "revoked"
    assert transfer_db.execute("SELECT revoked_at IS NOT NULL AS revoked FROM organization_invitations").fetchone()["revoked"]
    assert transfer_db.execute("SELECT 1 FROM participant_acquaintance_states WHERE user_id=7").fetchone() is None
    assert transfer_db.execute("SELECT 1 FROM web_user_sessions WHERE user_id=7").fetchone() is None
    suppression = transfer_db.execute(
        "SELECT reason FROM configured_organization_membership_suppressions WHERE user_id=7 AND organization_id=3"
    ).fetchone()
    assert suppression["reason"] == "superadmin_transfer"

    # Repeat the exact request after a lost response: no duplicate scope and no conflict.
    routes.transfer_admin_organization_user(7, _payload(role="member"), _request())
    repeated = transfer_db.execute(
        "SELECT organization_id, role, admission_source FROM organization_memberships WHERE user_id=7"
    ).fetchone()
    assert repeated == {"organization_id": 4, "role": "member", "admission_source": "superadmin_transfer"}
    assert transfer_db.execute(
        "SELECT COUNT(*) AS count FROM configured_organization_membership_suppressions WHERE user_id=7"
    ).fetchone()["count"] == 1


def test_transfer_rejects_last_admin_without_partial_changes(transfer_db):
    transfer_db.execute("INSERT INTO organization_memberships VALUES(3,7,'admin','admin_add',99,NOW(),NOW())")
    transfer_db.commit()

    with pytest.raises(HTTPException) as raised:
        routes.transfer_admin_organization_user(7, _payload(), _request())

    assert raised.value.status_code == 409
    assert raised.value.detail == "ORGANIZATION_TRANSFER_LAST_ADMIN"
    transfer_db.rollback()
    assert transfer_db.execute("SELECT organization_id FROM organization_memberships WHERE user_id=7").fetchone()["organization_id"] == 3


def test_transfer_closes_active_cycle_via_m7_and_rejects_inactive_target(transfer_db, monkeypatch):
    transfer_db.execute("INSERT INTO organization_memberships VALUES(3,7,'member','admin_add',99,NOW(),NOW())")
    transfer_db.execute(
        "INSERT INTO m5_cycles VALUES(%s,7,3,'active',NOW())",
        (uuid4(),),
    )
    transfer_db.commit()

    closed = {}
    def complete(connection, **kwargs):
        closed.update(kwargs)
        connection.execute("UPDATE m5_cycles SET status='collection_closed' WHERE cycle_id=%s", (kwargs["cycle_id"],))
        return {"states": {"cycle": "collection_closed"}}
    monkeypatch.setattr(routes.m7_completion, "complete", complete)
    routes.transfer_admin_organization_user(7, _payload(), _request())
    assert closed["reason"] == "organization_transfer"
    assert transfer_db.execute("SELECT status FROM m5_cycles").fetchone()["status"] == "collection_closed"
    assert transfer_db.execute("SELECT organization_id FROM organization_memberships WHERE user_id=7").fetchone()["organization_id"] == 4

    transfer_db.execute("UPDATE organization_memberships SET organization_id=3 WHERE user_id=7")
    transfer_db.commit()

    with pytest.raises(HTTPException) as inactive:
        routes.transfer_admin_organization_user(7, _payload(target=5), _request())
    assert inactive.value.detail == "ORGANIZATION_TRANSFER_TARGET_INACTIVE"
