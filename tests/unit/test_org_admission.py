from __future__ import annotations

from contextlib import contextmanager

from Api import org_access
from Api import web_session_service as web_sessions


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _MembershipConnection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, params=None):
        assert "FROM organization_memberships" in query
        assert params == ("person@example.com", "person@example.com")
        return _Rows(self.rows)


def _disable_configured_access(monkeypatch):
    monkeypatch.setattr(org_access, "configured_superadmin_emails", lambda: set())
    monkeypatch.setattr(org_access, "configured_org_admin_emails", lambda: {})
    monkeypatch.setattr(org_access, "ensure_configured_organizations", lambda _connection: None)


def test_same_domain_without_explicit_membership_is_denied(monkeypatch) -> None:
    _disable_configured_access(monkeypatch)

    assert not org_access.email_has_organization_access(
        _MembershipConnection([]),
        email="Person@Example.com",
    )


def test_explicit_admin_add_and_csv_import_are_admitted(monkeypatch) -> None:
    _disable_configured_access(monkeypatch)

    for source in ("admin_add", "csv_import"):
        assert org_access.email_has_organization_access(
            _MembershipConnection([{"organization_id": 7, "role": "member", "admission_source": source}]),
            email="person@example.com",
        )


def test_legacy_membership_requires_reapproval(monkeypatch) -> None:
    _disable_configured_access(monkeypatch)

    assert not org_access.email_has_organization_access(
        _MembershipConnection(
            [{"organization_id": 7, "role": "member", "admission_source": "legacy_unclassified"}]
        ),
        email="person@example.com",
    )


def test_multiple_explicit_participant_memberships_fail_closed(monkeypatch) -> None:
    _disable_configured_access(monkeypatch)

    assert not org_access.email_has_organization_access(
        _MembershipConnection(
            [
                {"organization_id": 7, "role": "member", "admission_source": "admin_add"},
                {"organization_id": 8, "role": "member", "admission_source": "csv_import"},
            ]
        ),
        email="person@example.com",
    )


def test_service_admin_membership_remains_admitted(monkeypatch) -> None:
    _disable_configured_access(monkeypatch)

    assert org_access.email_has_organization_access(
        _MembershipConnection(
            [{"organization_id": 7, "role": "admin", "admission_source": "legacy_unclassified"}]
        ),
        email="person@example.com",
    )


def test_assignment_does_not_create_member_from_domain(monkeypatch) -> None:
    _disable_configured_access(monkeypatch)

    class _NoQueryConnection:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("domain membership lookup must not run")

    org_access.assign_user_organization_from_email(
        _NoQueryConnection(),
        user_id=42,
        email="person@example.com",
    )


def test_configured_bootstrap_never_reactivates_or_renames_existing_organization(monkeypatch) -> None:
    statements = []

    class _Connection:
        def execute(self, query, params=None):
            statements.append((" ".join(query.split()), params))
            return _Rows([])

    monkeypatch.setattr(org_access, "configured_org_names", lambda: {"pilot": "Configured name"})
    monkeypatch.setattr(org_access, "configured_org_admin_emails", lambda: {})
    monkeypatch.setattr(org_access, "configured_org_domains", lambda: {})

    org_access.ensure_configured_organizations(_Connection())

    query, params = next(item for item in statements if "INSERT INTO organizations" in item[0])
    assert params == ("pilot", "Configured name")
    assert "ON CONFLICT (code) DO NOTHING" in query
    assert "is_active = TRUE" not in query
    assert "DO UPDATE" not in query


def test_configured_bootstrap_skips_a_fully_deleted_organization(monkeypatch) -> None:
    statements = []

    class _Connection:
        def execute(self, query, params=None):
            normalized = " ".join(query.split())
            statements.append((normalized, params))
            if "organization_deletion_tombstones" in normalized:
                return _Rows([{"exists": 1}])
            return _Rows([])

    monkeypatch.setattr(org_access, "configured_org_names", lambda: {"pilot": "Configured name"})
    monkeypatch.setattr(org_access, "configured_org_admin_emails", lambda: {})
    monkeypatch.setattr(org_access, "configured_org_domains", lambda: {})

    org_access.ensure_configured_organizations(_Connection())

    assert not any("INSERT INTO organizations" in query for query, _params in statements)


def test_suppressed_configured_admin_is_not_recreated_or_admitted(monkeypatch) -> None:
    calls = []

    class _Result:
        def __init__(self, row=None, rows=None):
            self.row = row
            self.rows = rows or []

        def fetchone(self):
            return self.row

        def fetchall(self):
            return self.rows

    class _Connection:
        def execute(self, query, params=None):
            normalized = " ".join(query.split())
            calls.append((normalized, params))
            if "SELECT id FROM organizations" in normalized:
                return _Result({"id": 7})
            if "FROM configured_organization_membership_suppressions" in normalized:
                return _Result({"?column?": 1})
            if "LEFT JOIN configured_organization_membership_suppressions" in normalized:
                return _Result(None)
            if "FROM organization_memberships" in normalized:
                return _Result(rows=[])
            return _Result()

    monkeypatch.setattr(org_access, "ensure_configured_organizations", lambda _connection: None)
    monkeypatch.setattr(org_access, "configured_superadmin_emails", lambda: set())
    monkeypatch.setattr(org_access, "configured_org_admin_emails", lambda: {"pilot": ["admin@example.com"]})

    connection = _Connection()
    org_access.assign_user_organization_from_email(connection, user_id=42, email="admin@example.com")
    assert not any("INSERT INTO organization_memberships" in query for query, _params in calls)
    assert not org_access.email_has_organization_access(connection, email="admin@example.com")


def test_legacy_web_session_is_deleted_when_used(monkeypatch) -> None:
    executed = []

    class _Result:
        def fetchone(self):
            return {"email": "legacy@example.com"}

    class _Connection:
        def execute(self, query, params=None):
            executed.append((query, params))
            return _Result()

        def commit(self):
            executed.append(("COMMIT", None))

    connection = _Connection()

    @contextmanager
    def _connection_context():
        yield connection

    service = web_sessions.WebSessionService()
    monkeypatch.setattr(service, "ensure_schema", lambda: None)
    monkeypatch.setattr(web_sessions, "get_connection", _connection_context)
    monkeypatch.setattr(org_access, "email_has_organization_access", lambda *_args, **_kwargs: False)

    assert service.get_user_by_token("legacy-token") is None
    assert any("DELETE FROM web_user_sessions" in query for query, _params in executed)
    assert ("COMMIT", None) in executed
