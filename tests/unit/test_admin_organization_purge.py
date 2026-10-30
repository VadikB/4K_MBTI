from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from Api import routes
from Api.schemas import AdminOrganizationPurgeRequest, AdminOrganizationsResponse


class FakeConnection:
    def __init__(self, organization=None, protected_accounts=None):
        self.organization = organization
        self.protected_accounts = protected_accounts or []
        self.committed = False
        self.rolled_back = False
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=()):
        self.statements.append((str(query), _params))
        if "SELECT id, code, is_active FROM organizations" in str(query):
            return SimpleNamespace(fetchone=lambda: self.organization)
        if "FROM organization_memberships membership JOIN users" in str(query):
            return SimpleNamespace(fetchall=lambda: self.protected_accounts)
        if "INSERT INTO configured_access_suppressions" in str(query):
            return SimpleNamespace(rowcount=1)
        raise AssertionError(str(query))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def payload(**overrides):
    return AdminOrganizationPurgeRequest(
        confirmation_code=overrides.get("confirmation_code", "test-org"),
        preview_fingerprint=overrides.get("preview_fingerprint", "a" * 64),
        operation_id=overrides.get("operation_id", "purge-operation-1"),
        acknowledge_irreversible=overrides.get("acknowledge_irreversible", True),
    )


def setup_route(monkeypatch, connection):
    user = SimpleNamespace(id=99)
    monkeypatch.setattr(routes, "_physical_organization_purge_available", lambda: True)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: user)
    monkeypatch.setattr(routes, "_require_superadmin", lambda _connection, _user: None)
    monkeypatch.setattr(routes, "get_connection", lambda: connection)
    monkeypatch.setattr(routes, "purge_plan_fingerprint", lambda _connection: "a" * 64)
    monkeypatch.setattr(routes, "record_receipt", lambda *_args: None)
    monkeypatch.setattr(routes, "read_receipt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes, "append_intent", lambda _path, **kwargs: {
        "operation_id": kwargs["operation_id"], "target_type": kwargs["target_type"],
        "target_id": kwargs["target_id"], "preview_fingerprint": kwargs["fingerprint"]})
    monkeypatch.setattr(
        routes,
        "_build_admin_organizations",
        lambda _connection: AdminOrganizationsResponse(
            title="Организации", subtitle="", is_superadmin=True,
            physical_purge_available=True, items=[],
        ),
    )
    return SimpleNamespace(cookies={routes.SESSION_COOKIE_NAME: "session"})


def test_purge_is_hidden_outside_test_database(monkeypatch):
    monkeypatch.setattr(routes, "_physical_organization_purge_available", lambda: False)
    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_organization(1, payload(), SimpleNamespace(cookies={}))
    assert failure.value.status_code == 404


@pytest.mark.parametrize(
    ("organization", "request_payload", "detail"),
    [
        ({"id": 1, "code": "test-org", "is_active": False}, payload(confirmation_code="wrong"), "does not match"),
        ({"id": 1, "code": "test-org", "is_active": False}, payload(acknowledge_irreversible=False), "acknowledgement"),
    ],
)
def test_purge_rejects_missing_preconditions(monkeypatch, organization, request_payload, detail):
    connection = FakeConnection(organization)
    request = setup_route(monkeypatch, connection)
    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_organization(1, request_payload, request)
    assert failure.value.status_code in {400, 409}
    assert detail.lower() in str(failure.value.detail).lower()
    assert not connection.committed


def test_purge_commits_only_after_exact_confirmation(monkeypatch):
    connection = FakeConnection({"id": 1, "code": "test-org", "is_active": False})
    request = setup_route(monkeypatch, connection)
    captured = {}

    def purge(_connection, *, organization_id, confirm_code, expected_fingerprint, on_validated):
        captured.update(organization_id=organization_id, confirm_code=confirm_code)
        assert expected_fingerprint == "a" * 64
        on_validated(expected_fingerprint)
        return {"public.organizations": 1, "public.organization_memberships": 2}

    monkeypatch.setattr(routes, "purge_organization", purge)
    response = routes.purge_admin_organization(1, payload(), request)
    assert captured == {"organization_id": 1, "confirm_code": "test-org"}
    assert connection.committed and not connection.rolled_back
    assert response.items == []


def test_purge_lost_response_replays_receipt_without_target_lookup(monkeypatch):
    connection = FakeConnection(None)
    request = setup_route(monkeypatch, connection)
    monkeypatch.setattr(routes, "read_receipt", lambda *_args, **_kwargs: {"operation_id": "purge-operation-1"})

    response = routes.purge_admin_organization(1, payload(), request)

    assert response.items == []
    assert not connection.rolled_back


def test_purge_rejects_organization_that_would_delete_current_account(monkeypatch):
    connection = FakeConnection(
        {"id": 1, "code": "test-org", "is_active": False},
        [{"id": 99, "email": "admin@example.test"}],
    )
    request = setup_route(monkeypatch, connection)

    with pytest.raises(HTTPException) as failure:
        routes.purge_admin_organization(1, payload(), request)

    assert failure.value.status_code == 409
    assert failure.value.detail == "CANNOT_PURGE_ORGANIZATION_WITH_CURRENT_ACCOUNT"


def test_purge_revokes_configured_access_before_deleting_orphan_account(monkeypatch):
    connection = FakeConnection(
        {"id": 1, "code": "test-org", "is_active": False},
        [{"id": 12, "email": "configured@example.test"}],
    )
    request = setup_route(monkeypatch, connection)
    monkeypatch.setattr(routes, "configured_superadmin_emails", lambda: {"configured@example.test"})
    monkeypatch.setattr(routes, "configured_org_admin_emails", lambda: {})

    monkeypatch.setattr(routes, "purge_organization", lambda *_args, **_kwargs: {"public.organizations": 1})
    invalidated = []
    monkeypatch.setattr(routes.interviewer_agent, "invalidate_user", invalidated.append)

    routes.purge_admin_organization(1, payload(), request)

    suppression = [statement for statement in connection.statements
        if "INSERT INTO configured_access_suppressions" in statement[0]]
    assert len(suppression) == 1
    assert suppression[0][1] == ("configured@example.test", 99)
    assert invalidated == [12]
    assert connection.committed
