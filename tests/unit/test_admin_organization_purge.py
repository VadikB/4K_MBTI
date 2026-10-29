from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from Api import routes
from Api.schemas import AdminOrganizationPurgeRequest, AdminOrganizationsResponse


class FakeConnection:
    def __init__(self, organization=None):
        self.organization = organization
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, _params=()):
        if "SELECT id, code, is_active FROM organizations" in str(query):
            return SimpleNamespace(fetchone=lambda: self.organization)
        raise AssertionError(str(query))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def payload(**overrides):
    return AdminOrganizationPurgeRequest(
        confirmation_code=overrides.get("confirmation_code", "test-org"),
        backup_reference=overrides.get("backup_reference", "backup-20261029"),
        acknowledge_irreversible=overrides.get("acknowledge_irreversible", True),
    )


def setup_route(monkeypatch, connection):
    user = SimpleNamespace(id=99)
    monkeypatch.setattr(routes, "_physical_organization_purge_available", lambda: True)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: user)
    monkeypatch.setattr(routes, "_require_superadmin", lambda _connection, _user: None)
    monkeypatch.setattr(routes, "get_connection", lambda: connection)
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
        ({"id": 1, "code": "test-org", "is_active": True}, payload(), "Deactivate organization"),
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

    def purge(_connection, *, organization_id, confirm_code):
        captured.update(organization_id=organization_id, confirm_code=confirm_code)
        return {"public.organizations": 1, "public.organization_memberships": 2}

    monkeypatch.setattr(routes, "purge_organization", purge)
    response = routes.purge_admin_organization(1, payload(), request)
    assert captured == {"organization_id": 1, "confirm_code": "test-org"}
    assert connection.committed and not connection.rolled_back
    assert response.items == []
