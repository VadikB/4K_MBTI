from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes
from Api.org_access import AdminScope


class _Result:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _InvitationConnection:
    def __init__(self):
        self.rows: list[dict] = []

    def execute(self, query, params=()):
        if "FROM organization_memberships om" in query:
            return _Result(one={"id": 18})
        if "INSERT INTO organization_invitations" in query:
            request_id = params[5]
            duplicate = next(
                (
                    row
                    for row in self.rows
                    if row["organization_id"] == params[0]
                    and row["recipient_email"] == params[4]
                    and row["request_id"] == request_id
                    and request_id is not None
                ),
                None,
            )
            if duplicate is not None:
                return _Result(one=None)
            row = {
                "id": len(self.rows) + 1,
                "organization_id": params[0],
                "expires_at": params[2],
                "recipient_email": params[4],
                "request_id": request_id,
                "delivery_status": "queued",
                "delivery_error": None,
                "used_at": None,
                "revoked_at": None,
                "name": "Organization A",
                "invitation_intro": "Welcome",
                "is_active": True,
                "purpose": "personal_registration",
            }
            self.rows.append(row)
            return _Result(one=row)
        if "AND request_id = %s" in query:
            organization_id, email, request_id = params
            row = next(
                row
                for row in self.rows
                if row["organization_id"] == organization_id
                and row["recipient_email"] == email
                and row["request_id"] == request_id
            )
            return _Result(one=row)
        if "SET delivery_status = 'accepted'" in query:
            row = next(row for row in self.rows if row["id"] == params[0])
            row["delivery_status"] = "accepted"
            return _Result(one=row)
        if "SET delivery_status = 'error'" in query:
            row = next(row for row in self.rows if row["id"] == params[1])
            row["delivery_status"] = "error"
            row["delivery_error"] = params[0]
            return _Result(one=row)
        if "FROM organization_invitations" in query:
            invitation_id = params[0]
            return _Result(one=next(row for row in self.rows if row["id"] == invitation_id))
        return _Result(one={"id": 18})

    def commit(self):
        return None

    def rollback(self):
        return None


def _client(monkeypatch, connection, sent):
    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda _token: SimpleNamespace(id=18, email="admin@example.test"),
    )
    monkeypatch.setattr(
        routes,
        "get_admin_scope",
        lambda _connection, _user: AdminScope(organization_ids=(3,)),
    )
    monkeypatch.setattr(routes.settings, "auth_magic_link_dev_mode", False)
    monkeypatch.setattr(routes.settings, "email_provider", "postmark")
    monkeypatch.setattr(routes, "send_auth_action_email", lambda **payload: sent.append(payload))
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_personal_invitation_repeated_operation_has_one_effect(monkeypatch) -> None:
    connection = _InvitationConnection()
    sent = []
    client = _client(monkeypatch, connection, sent)
    headers = {"Idempotency-Key": "r03-same-operation"}
    payload = {"emails": [" Person@Example.Test "], "operation_id": "r03-same-operation"}

    first = client.post("/users/admin/organizations/3/personal-invitations", json=payload, headers=headers)
    second = client.post("/users/admin/organizations/3/personal-invitations", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["items"][0]["invitation_id"] == second.json()["items"][0]["invitation_id"]
    assert len(connection.rows) == 1
    assert len(sent) == 1
    expires_at = datetime.fromisoformat(first.json()["items"][0]["expires_at"])
    assert timedelta(hours=71, minutes=59) < expires_at - datetime.now() <= timedelta(hours=72)


def test_personal_invitation_without_provider_is_not_accepted(monkeypatch) -> None:
    connection = _InvitationConnection()
    sent = []
    client = _client(monkeypatch, connection, sent)
    monkeypatch.setattr(routes.settings, "email_provider", "")

    response = client.post(
        "/users/admin/organizations/3/personal-invitations",
        json={"emails": ["person@example.test"], "operation_id": "r03-no-provider"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "error"
    assert "не настроен" in response.json()["items"][0]["error"]
    assert sent == []
    assert connection.rows == []


def test_consumed_personal_invitation_keeps_public_organization_context(monkeypatch) -> None:
    connection = _InvitationConnection()
    connection.rows.append(
        {
            "id": 7,
            "organization_id": 3,
            "expires_at": datetime.now() + timedelta(hours=70),
            "recipient_email": "person@example.test",
            "request_id": "r03-consumed",
            "delivery_status": "accepted",
            "used_at": datetime.now(),
            "revoked_at": None,
            "name": "Organization A",
            "invitation_intro": "Welcome",
            "is_active": True,
            "purpose": "personal_registration",
        }
    )

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)

    result = routes._public_invitation_by_id(7)

    assert result is not None
    assert result.organization_id == 3
    assert result.recipient_email == "person@example.test"
