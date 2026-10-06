from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes
from Api.auth_service import AuthAccessDeniedError


@pytest.fixture
def admission_client(monkeypatch):
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda token: SimpleNamespace(id=8, email="owner@example.test") if token == "admitted" else None,
    )
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, monkeypatch


@pytest.mark.e2e
def test_session_bootstrap_requires_an_admitted_owner_session(admission_client) -> None:
    client, _monkeypatch = admission_client

    assert client.get("/users/8/session-bootstrap").status_code == 401
    client.cookies.set(routes.SESSION_COOKIE_NAME, "admitted")
    assert client.get("/users/7/session-bootstrap").status_code == 403


@pytest.mark.e2e
def test_participant_profile_urls_require_the_same_session_owner(admission_client) -> None:
    client, _monkeypatch = admission_client

    assert client.get("/users/8/profile-summary").status_code == 401
    client.cookies.set(routes.SESSION_COOKIE_NAME, "admitted")
    assert client.get("/users/7/profile-summary").status_code == 403


@pytest.mark.e2e
def test_same_domain_outside_allowlist_is_rejected_by_auth_http(admission_client) -> None:
    client, monkeypatch = admission_client
    monkeypatch.setattr(
        routes.auth_service,
        "create_magic_link_request",
        lambda **_kwargs: (_ for _ in ()).throw(
            AuthAccessDeniedError("Пользователь с таким email не найден в активных организациях.")
        ),
    )

    response = client.post("/users/auth/email/request-link", json={"email": "outside@example.test"})

    assert response.status_code == 403
    assert "не найден" in response.json()["detail"]
