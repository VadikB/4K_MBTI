from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import hmac
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

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
                "token_hash": params[1],
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
        if "WHERE id = %s FOR UPDATE" in query:
            return _Result(one=next(row for row in self.rows if row["id"] == params[0]))
        if "SET delivery_status = 'accepted'" in query:
            row = next(row for row in self.rows if row["id"] == params[0])
            if row["used_at"] is not None or row["revoked_at"] is not None or row["expires_at"] <= datetime.now():
                return _Result(one=None)
            row["delivery_status"] = "accepted"
            return _Result(one=row)
        if "SET delivery_status = 'sending'" in query:
            row = next(row for row in self.rows if row["id"] == params[0])
            row["delivery_status"] = "sending"
            return _Result(one=row)
        if "SET delivery_status = 'error'" in query:
            row = next(row for row in self.rows if row["id"] == params[1])
            if row["delivery_status"] in {"queued", "sending"} and row["used_at"] is None and row["revoked_at"] is None:
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
    monkeypatch.setattr(routes.settings, "auth_invitation_token_secret", "r03-test-secret-that-is-at-least-32-characters")
    monkeypatch.setattr(routes, "send_auth_action_email", lambda **payload: sent.append(payload))
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _operation_token_hash(operation: str, email: str = "person@example.test") -> str:
    secret = "r03-test-secret-that-is-at-least-32-characters"
    material = f"3:{email}:{operation}".encode("utf-8")
    raw_token = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), material, hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return routes.hash_invitation_token(raw_token)


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


def test_personal_invitation_retry_does_not_duplicate_uncertain_delivery(monkeypatch) -> None:
    connection = _InvitationConnection()
    sent = []
    client = _client(monkeypatch, connection, sent)
    operation = "r03-interrupted-operation"
    monkeypatch.setattr(routes, "send_auth_action_email", lambda **_payload: (_ for _ in ()).throw(RuntimeError("controlled stop")))

    with pytest.raises(RuntimeError, match="controlled stop"):
        client.post(
            "/users/admin/organizations/3/personal-invitations",
            json={"emails": ["person@example.test"], "operation_id": operation},
            headers={"Idempotency-Key": operation},
        )

    monkeypatch.setattr(routes, "send_auth_action_email", lambda **payload: sent.append(payload))
    response = client.post(
        "/users/admin/organizations/3/personal-invitations",
        json={"emails": ["PERSON@EXAMPLE.TEST"], "operation_id": operation},
        headers={"Idempotency-Key": operation},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "uncertain"
    assert len(connection.rows) == 1
    assert len(sent) == 0


@pytest.mark.parametrize(
    ("used_at", "revoked_at", "expires_at"),
    [
        (datetime.now(), None, datetime.now() + timedelta(hours=70)),
        (None, datetime.now(), datetime.now() + timedelta(hours=70)),
        (None, None, datetime.now() - timedelta(seconds=1)),
    ],
)
def test_personal_invitation_does_not_recover_inactive_accepted_operation(
    monkeypatch, used_at, revoked_at, expires_at
) -> None:
    operation = "r03-inactive-accepted"
    connection = _InvitationConnection()
    connection.rows.append({
        "id": 1, "organization_id": 3, "token_hash": _operation_token_hash(operation),
        "expires_at": expires_at, "recipient_email": "person@example.test",
        "request_id": operation, "delivery_status": "accepted", "delivery_error": None,
        "used_at": used_at, "revoked_at": revoked_at, "name": "Organization A",
        "invitation_intro": "Welcome", "is_active": True, "purpose": "personal_registration",
    })
    sent = []
    client = _client(monkeypatch, connection, sent)

    response = client.post(
        "/users/admin/organizations/3/personal-invitations",
        json={"emails": ["person@example.test"], "operation_id": operation},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "error"
    assert connection.rows[0]["delivery_status"] == "accepted"
    assert sent == []


def test_personal_invitation_rejects_legacy_operation_without_reconstructable_token(monkeypatch) -> None:
    operation = "r03-legacy-operation"
    connection = _InvitationConnection()
    connection.rows.append({
        "id": 1, "organization_id": 3, "token_hash": "legacy-random-token-hash",
        "expires_at": datetime.now() + timedelta(hours=70), "recipient_email": "person@example.test",
        "request_id": operation, "delivery_status": "queued", "delivery_error": None,
        "used_at": None, "revoked_at": None, "name": "Organization A",
        "invitation_intro": "Welcome", "is_active": True, "purpose": "personal_registration",
    })
    sent = []
    client = _client(monkeypatch, connection, sent)

    response = client.post(
        "/users/admin/organizations/3/personal-invitations",
        json={"emails": ["person@example.test"], "operation_id": operation},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "error"
    assert "безопасно восстановлена" in response.json()["items"][0]["error"]
    assert sent == []


def test_personal_invitation_requires_operation_identifier(monkeypatch) -> None:
    client = _client(monkeypatch, _InvitationConnection(), [])
    response = client.post(
        "/users/admin/organizations/3/personal-invitations",
        json={"emails": ["person@example.test"]},
    )
    assert response.status_code == 400


def test_consumed_invitation_context_survives_expiry_boundary(monkeypatch) -> None:
    connection = _InvitationConnection()
    connection.rows.append({
        "id": 8, "organization_id": 3, "expires_at": datetime.now() - timedelta(seconds=1),
        "recipient_email": "person@example.test", "request_id": "r03-consumed-expired",
        "delivery_status": "accepted", "used_at": datetime.now(), "revoked_at": None,
        "name": "Organization A", "invitation_intro": "Welcome", "is_active": True,
        "purpose": "personal_registration",
    })

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    assert routes._public_invitation_by_id(8).organization_id == 3
