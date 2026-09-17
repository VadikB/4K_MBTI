from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes


ROLE = {
    "id": 31,
    "code": "student",
    "version": 1,
    "scope": "base",
    "organization_id": None,
    "definition": {
        "description": {"name": "Студент", "short_description": "Учебная деятельность"},
    },
}


@contextmanager
def _connection():
    yield object()


@pytest.fixture
def role_client(monkeypatch):
    monkeypatch.setattr(routes, "get_connection", _connection)
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda token: SimpleNamespace(id=7) if token == "valid" else None,
    )
    monkeypatch.setattr(routes, "list_available_role_profiles", lambda _connection, *, user_id: [ROLE] if user_id == 7 else [])
    monkeypatch.setattr(routes, "get_selected_role_profile", lambda _connection, *, user_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, monkeypatch


@pytest.mark.e2e
def test_m3_role_selection_requires_authentication(role_client) -> None:
    client, _ = role_client
    assert client.get("/users/role-profiles/available").status_code == 401
    assert client.put("/users/role-profiles/selection", json={"version_id": 31}).status_code == 401


@pytest.mark.e2e
def test_m3_role_selection_returns_dynamic_options_and_selected_role(role_client) -> None:
    client, monkeypatch = role_client
    client.cookies.set(routes.SESSION_COOKIE_NAME, "valid")
    assert client.get("/users/role-profiles/available").json() == {
        "roles": [{
            "version_id": 31, "code": "student", "version": 1, "name": "Студент",
            "short_description": "Учебная деятельность", "scope": "base", "organization_id": None,
        }],
        "selected_version_id": None,
    }
    monkeypatch.setattr(
        routes,
        "select_role_profile_for_user",
        lambda _connection, *, user_id, version_id: ROLE if (user_id, version_id) == (7, 31) else None,
    )
    response = client.put("/users/role-profiles/selection", json={"version_id": 31})
    assert response.status_code == 200
    assert response.json()["code"] == "student"


@pytest.mark.e2e
def test_m3_role_selection_rejects_inaccessible_role(role_client) -> None:
    client, monkeypatch = role_client
    client.cookies.set(routes.SESSION_COOKIE_NAME, "valid")
    monkeypatch.setattr(
        routes,
        "select_role_profile_for_user",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("RoleProfile is not available to this organization member.")),
    )
    response = client.put("/users/role-profiles/selection", json={"version_id": 99})
    assert response.status_code == 400


@pytest.mark.e2e
def test_organization_draft_creation_is_scoped_to_its_admin(role_client) -> None:
    client, monkeypatch = role_client
    client.cookies.set(routes.SESSION_COOKIE_NAME, "valid")

    class Connection:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return {"id": 10}

        def commit(self):
            pass

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(
        routes,
        "_get_admin_scope_or_403",
        lambda _connection, _user: SimpleNamespace(is_superadmin=False, organization_ids=(10,)),
    )
    monkeypatch.setattr(
        routes,
        "create_organization_role_profile_draft",
        lambda _connection, *, organization_id, **_kwargs: 41 if organization_id == 10 else None,
    )
    payload = {"definition": {"code": "research_coordinator"}, "provenance": {"formation_method": "documents"}}
    assert client.post("/users/admin/organizations/20/role-profiles/drafts", json=payload).status_code == 403
    response = client.post("/users/admin/organizations/10/role-profiles/drafts", json=payload)
    assert response.status_code == 201
    assert response.json() == {"version_id": 41, "organization_id": 10, "status": "draft"}
