from __future__ import annotations

from datetime import datetime, timedelta
from contextlib import contextmanager

import pytest

from Api import auth_service as auth_module
from Api.organization_invitation_service import (
    OrganizationInvitationError,
    ensure_email_admitted_to_invitation,
    hash_invitation_token,
    resolve_invitation,
)


class _Result:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _Connection:
    def __init__(self, invitation=None, memberships=None):
        self.invitation = invitation
        self.memberships = memberships or []
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))
        if "FROM organization_invitations" in query:
            return _Result(one=self.invitation)
        return _Result(many=self.memberships)


def _invitation(**overrides):
    value = {
        "id": 9,
        "organization_id": 3,
        "expires_at": datetime.now() + timedelta(days=30),
        "revoked_at": None,
        "name": "Организация A",
        "invitation_intro": "Добро пожаловать",
        "is_active": True,
    }
    value.update(overrides)
    return value


def test_resolve_invitation_uses_hash_and_returns_only_public_context() -> None:
    connection = _Connection(invitation=_invitation())

    context = resolve_invitation(connection, token="shared-secret")

    assert context.organization_id == 3
    assert context.organization_name == "Организация A"
    assert connection.calls[0][1] == (hash_invitation_token("shared-secret"),)
    assert "shared-secret" not in str(connection.calls[0])


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (None, "недействительно"),
        (_invitation(revoked_at=datetime.now()), "отозвано"),
        (_invitation(expires_at=datetime.now() - timedelta(seconds=1)), "истёк"),
    ],
)
def test_invalid_revoked_and_expired_invitations_fail_closed(row, message) -> None:
    with pytest.raises(OrganizationInvitationError, match=message):
        resolve_invitation(_Connection(invitation=row), token="shared-secret")


def test_email_must_be_admitted_to_the_invited_organization() -> None:
    invitation = resolve_invitation(_Connection(invitation=_invitation()), token="shared-secret")
    allowed = _Connection(memberships=[{"role": "member", "admission_source": "admin_add"}])
    ensure_email_admitted_to_invitation(allowed, email="person@example.test", invitation=invitation)
    assert allowed.calls[0][1] == (3, "person@example.test", "person@example.test")

    with pytest.raises(OrganizationInvitationError, match="выбранной организации"):
        ensure_email_admitted_to_invitation(
            _Connection(memberships=[]),
            email="member-of-b@example.test",
            invitation=invitation,
        )


def test_same_domain_is_not_an_invitation_admission_rule() -> None:
    invitation = resolve_invitation(_Connection(invitation=_invitation()), token="shared-secret")
    with pytest.raises(OrganizationInvitationError):
        ensure_email_admitted_to_invitation(
            _Connection(memberships=[]),
            email="outside@example.test",
            invitation=invitation,
        )


def test_verification_action_is_bound_to_the_server_invitation(monkeypatch) -> None:
    calls = []

    class _AuthConnection:
        def execute(self, query, params=None):
            calls.append((query, params))
            if "FROM organization_invitations" in query:
                return _Result(one=_invitation())
            if "FROM organization_memberships" in query:
                return _Result(many=[{"role": "member", "admission_source": "csv_import"}])
            if "SELECT created_at FROM auth_action_tokens" in query:
                return _Result(one=None)
            if "SELECT COUNT(*) AS request_count" in query:
                return _Result(one={"request_count": 0})
            return _Result(one=None)

        def commit(self):
            pass

    @contextmanager
    def _connection():
        yield _AuthConnection()

    service = auth_module.AuthService()
    monkeypatch.setattr(service, "ensure_schema", lambda: None)
    monkeypatch.setattr(auth_module, "get_connection", _connection)
    monkeypatch.setattr(auth_module.settings, "auth_magic_link_dev_mode", True)

    result = service.create_auth_action_request(
        email="person@example.test",
        purpose="email_verification",
        organization_invitation_token="shared-secret",
    )

    insert = next(item for item in calls if "INSERT INTO auth_action_tokens" in item[0])
    assert insert[1][-1] == 9
    assert result.organization_invitation_id == 9
