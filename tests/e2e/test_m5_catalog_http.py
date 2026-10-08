from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes


pytestmark = pytest.mark.e2e


@contextmanager
def connection():
    yield object()


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id=7, email="publisher@example.test") if token == "publisher" else None)
    monkeypatch.setattr(routes, "require_platform_permission",
                        lambda _connection, user, _permission: None if user else (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(routes, "_get_admin_scope_or_403",
                        lambda *_args: SimpleNamespace(is_superadmin=False, organization_ids=[11]))
    monkeypatch.setattr(routes.m5_catalog_integrity, "publication_plan", lambda _connection, **kwargs: {
        "publishable": True, "case_version_ids": kwargs["case_version_ids"],
    })
    captured = {}
    def publish(_connection, **kwargs):
        captured.update(kwargs)
        return {"catalog_db_id": 31, "idempotent": False, "manifest_checksum": "a" * 64}
    monkeypatch.setattr(routes.m5_catalog_integrity, "publish_catalog", publish)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, captured


def payload():
    return {
        "catalog_id": "controlled-4k",
        "catalog_version": "1.0",
        "package_db_id": 3,
        "case_version_ids": [7],
        "usage_scope": "assessment",
        "organization_id": 11,
        "decision_basis": "approved review packet",
        "idempotency_key": "catalog-1",
    }


def test_catalog_publication_requires_authenticated_authority_and_uses_server_actor(http):
    client, captured = http
    assert client.post("/users/admin/m5-catalogs/publish", json=payload()).status_code == 401
    client.cookies.set(routes.SESSION_COOKIE_NAME, "publisher")
    response = client.post("/users/admin/m5-catalogs/publish", json=payload())
    assert response.status_code == 200
    assert captured["published_by"] == 7
    assert captured["organization_id"] == 11


def test_foreign_organization_is_rejected_before_publication(http):
    client, captured = http
    client.cookies.set(routes.SESSION_COOKIE_NAME, "publisher")
    response = client.post("/users/admin/m5-catalogs/publish", json=payload() | {"organization_id": 12})
    assert response.status_code == 403
    assert captured == {}
