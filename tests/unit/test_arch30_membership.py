from __future__ import annotations

import psycopg
import pytest
from fastapi import HTTPException

from Api.routes import _execute_membership_write, _lock_membership_by_email, _reject_foreign_membership


class _Result:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((" ".join(query.split()), params))
        if "FROM users u" in query:
            return _Result(self.row)
        return _Result()


class _UniqueViolationConnection(_Connection):
    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        self.calls.append((normalized, params))
        if normalized.startswith("INSERT INTO organization_memberships"):
            raise psycopg.errors.UniqueViolation("synthetic membership race")
        if "FROM users u" in query:
            return _Result(self.row)
        return _Result()


def test_membership_lookup_locks_normalized_email_before_reading_scope():
    connection = _Connection({
        "user_id": 7,
        "organization_id": 3,
        "role": "admin",
        "organization_name": "Организация А",
    })

    result = _lock_membership_by_email(connection, email=" Person@Example.TEST ")

    assert result["organization_id"] == 3
    assert "pg_advisory_xact_lock" in connection.calls[0][0]
    assert connection.calls[0][1] == ("person@example.test",)
    assert connection.calls[1][1] == ("person@example.test",)


def test_foreign_membership_hides_tenant_from_organization_admin():
    with pytest.raises(HTTPException) as raised:
        _reject_foreign_membership(
            {"organization_id": 3, "organization_name": "Скрытая организация"},
            organization_id=4,
            expose_organization=False,
        )

    assert raised.value.status_code == 409
    assert "ORGANIZATION_MEMBERSHIP_CONFLICT" in raised.value.detail
    assert "Скрытая организация" not in raised.value.detail
    assert "с другой организацией" in raised.value.detail


def test_foreign_membership_gives_superadmin_transfer_action():
    with pytest.raises(HTTPException) as raised:
        _reject_foreign_membership(
            {"organization_id": 3, "organization_name": "Организация А"},
            organization_id=4,
            expose_organization=True,
        )

    assert raised.value.status_code == 409
    assert "Организация А" in raised.value.detail
    assert "перенесите пользователя" in raised.value.detail


def test_unique_violation_rolls_back_savepoint_and_returns_business_conflict():
    connection = _UniqueViolationConnection({
        "user_id": 7,
        "organization_id": 3,
        "role": "member",
        "organization_name": "Организация А",
    })

    with pytest.raises(HTTPException) as raised:
        _execute_membership_write(
            connection,
            email="person@example.test",
            organization_id=4,
            expose_existing_organization=False,
            query="INSERT INTO organization_memberships VALUES (%s, %s)",
            params=(4, 7),
        )

    assert raised.value.status_code == 409
    commands = [call[0] for call in connection.calls]
    assert commands[0] == "SAVEPOINT organization_membership_write"
    assert "ROLLBACK TO SAVEPOINT organization_membership_write" in commands
    assert "RELEASE SAVEPOINT organization_membership_write" in commands


@pytest.mark.parametrize("membership", [None, {"organization_id": None}, {"organization_id": 4}])
def test_empty_or_same_membership_is_idempotently_allowed(membership):
    _reject_foreign_membership(
        membership,
        organization_id=4,
        expose_organization=False,
    )
