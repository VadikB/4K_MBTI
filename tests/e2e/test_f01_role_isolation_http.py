from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import routes
from Api.org_access import AdminScope, configured_superadmin_emails
from Api.schemas import AdminOrganizationsResponse


pytestmark = pytest.mark.e2e


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []


class _Connection:
    def __init__(self, *, existing: bool, platform_role: bool = False):
        self.existing = existing
        self.platform_role = platform_role
        self.queries: list[str] = []
        self.committed = False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.queries.append(normalized)
        if "SELECT id FROM organizations" in normalized or "SELECT id,code FROM organizations" in normalized:
            return _Result({"id": 4, "code": "synthetic"})
        if "LEFT JOIN organization_memberships membership" in normalized:
            return _Result({"user_id": 72, "organization_id": None} if self.existing else None)
        if "JOIN user_platform_roles assignment" in normalized:
            return _Result({"exists": 1} if self.platform_role else None)
        return _Result()

    def commit(self):
        self.committed = True


@pytest.fixture
def http_client(monkeypatch):
    def make(*, existing: bool, platform_role: bool = False, superadmin_actor: bool = False):
        connection = _Connection(existing=existing, platform_role=platform_role)

        @contextmanager
        def get_connection():
            yield connection

        monkeypatch.setattr(routes, "get_connection", get_connection)
        monkeypatch.setattr(
            routes.web_session_service,
            "get_user_by_token",
            lambda _token: SimpleNamespace(id=18, email="actor@example.test"),
        )
        monkeypatch.setattr(
            routes,
            "_require_organization_admin",
            lambda *_args: AdminScope(organization_ids=(4,)),
        )
        monkeypatch.setattr(
            routes,
            "_require_superadmin",
            lambda *_args: AdminScope(is_superadmin=True) if superadmin_actor else (
                pytest.fail("unexpected superadmin access")
            ),
        )
        monkeypatch.setattr(
            routes,
            "_build_admin_organizations",
            lambda *_args, **_kwargs: AdminOrganizationsResponse(
                title="Организации", subtitle="", is_superadmin=superadmin_actor, items=[]
            ),
        )
        app = FastAPI()
        app.include_router(routes.router)
        return TestClient(app), connection

    return make


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("entry", ["form", "csv", "admin"])
def test_protected_email_is_rejected_before_any_account_write(
    monkeypatch, http_client, existing, entry
):
    monkeypatch.setattr(routes.settings, "superadmin_emails_raw", "OTHER@example.test; Protected@Example.Test ")
    http, connection = http_client(existing=existing, superadmin_actor=entry == "admin")
    if entry == "form":
        response = http.post(
            "/users/admin/organizations/4/members",
            json={"email": "protected@example.test", "full_name": "Changed", "role_description": "Position"},
        )
        assert response.status_code == 409
        message = response.json()["detail"]
    elif entry == "csv":
        response = http.post(
            "/users/admin/organizations/4/members/import",
            json={"csv_text": "email,full_name,role_description\nprotected@example.test,Changed,Position"},
        )
        assert response.status_code == 200
        assert response.json()["imported_count"] == 0
        assert response.json()["skipped_count"] == 1
        message = response.json()["errors"][0]
    else:
        response = http.post(
            "/users/admin/organizations/4/admins",
            json={"email": "protected@example.test", "full_name": "Changed"},
        )
        assert response.status_code == 409
        message = response.json()["detail"]
    assert "супер" not in message.lower()
    assert "платформ" not in message.lower()
    assert not any(
        query.startswith(("INSERT INTO users", "UPDATE users", "INSERT INTO organization_memberships",
                          "DELETE FROM configured_access_suppressions", "INSERT INTO organization_invitations"))
        for query in connection.queries
    )


def test_platform_role_account_is_also_rejected(http_client, monkeypatch):
    monkeypatch.setattr(routes.settings, "superadmin_emails_raw", "")
    http, connection = http_client(existing=True, platform_role=True)
    response = http.post(
        "/users/admin/organizations/4/members",
        json={"email": "author@example.test", "full_name": "Changed", "role_description": "Position"},
    )
    assert response.status_code == 409
    assert "платформ" not in response.text.lower()
    assert not any(query.startswith("UPDATE users") for query in connection.queries)


def test_configured_superadmin_parser_accepts_comma_and_semicolon(monkeypatch):
    monkeypatch.setattr(routes.settings, "superadmin_emails_raw", " A@Example.Test ; B@Example.Test, C@Example.Test ")
    assert configured_superadmin_emails() == {
        "a@example.test", "b@example.test", "c@example.test"
    }
