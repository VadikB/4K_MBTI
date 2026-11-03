from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes


pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one


class InvitationConnection:
    def __init__(self, *, used=False, revoked=False, acquaintance_started=False):
        self.invitation = {"id": 7, "used_at": "used" if used else None,
                           "revoked_at": "revoked" if revoked else None,
                           "recipient_email": "participant@example.test"}
        self.acquaintance_started = acquaintance_started
        self.committed = False

    def execute(self, sql, _params=()):
        if "SELECT id,used_at,revoked_at" in sql:
            return Result(dict(self.invitation))
        if "SELECT id FROM users" in sql:
            return Result({"id": 42})
        if "SELECT 1 FROM participant_acquaintance_states" in sql:
            return Result({"?column?": 1} if self.acquaintance_started else None)
        if "UPDATE organization_invitations SET revoked_at" in sql:
            if self.invitation["used_at"] or self.invitation["revoked_at"]:
                return Result()
            self.invitation["revoked_at"] = "now"
            return Result({"id": 7})
        return Result()

    def commit(self):
        self.committed = True


def make_client(monkeypatch, connection):
    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes, "_require_organization_admin", lambda *_args: None)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda _token: SimpleNamespace(id=18))
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_unused_invitation_can_be_revoked(monkeypatch):
    connection = InvitationConnection()
    with make_client(monkeypatch, connection) as client:
        response = client.delete("/users/admin/organizations/3/personal-invitations/7")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert connection.committed is True


def test_used_invitation_cannot_be_revoked(monkeypatch):
    connection = InvitationConnection(used=True)
    with make_client(monkeypatch, connection) as client:
        response = client.delete("/users/admin/organizations/3/personal-invitations/7")
    assert response.status_code == 409
    assert response.json()["detail"] == "INVITATION_ALREADY_USED"
    assert connection.committed is False


def test_repeated_revoke_is_idempotent(monkeypatch):
    connection = InvitationConnection(revoked=True)
    with make_client(monkeypatch, connection) as client:
        response = client.delete("/users/admin/organizations/3/personal-invitations/7")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_started_acquaintance_blocks_unused_invitation_revoke(monkeypatch):
    connection = InvitationConnection(acquaintance_started=True)
    with make_client(monkeypatch, connection) as client:
        response = client.delete("/users/admin/organizations/3/personal-invitations/7")
    assert response.status_code == 409
    assert response.json()["detail"] == "INVITATION_STATE_CHANGED"
    assert connection.invitation["revoked_at"] is None
    assert connection.committed is False
