from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes
from Api.auth_service import AuthAccessDeniedError, MagicLinkRequestResult
from Api.organization_invitation_service import OrganizationInvitationError
from Api.schemas import OrganizationInvitationPublicResponse


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


@pytest.mark.e2e
def test_public_invitation_returns_only_allowed_organization_copy(admission_client) -> None:
    client, monkeypatch = admission_client
    expires_at = datetime.now() + timedelta(days=30)
    monkeypatch.setattr(
        routes,
        "_public_invitation_by_token",
        lambda token: OrganizationInvitationPublicResponse(
            organization_id=3,
            organization_name="Организация A",
            invitation_intro="Добро пожаловать",
            expires_at=expires_at,
        ) if token == "valid" else (_ for _ in ()).throw(OrganizationInvitationError("Приглашение недействительно.")),
    )

    response = client.get("/users/organization-invitations/valid")
    assert response.status_code == 200
    assert response.json()["organization_name"] == "Организация A"
    assert set(response.json()) == {"organization_id", "organization_name", "invitation_intro", "expires_at"}
    assert client.get("/users/organization-invitations/tampered").status_code == 404


@pytest.mark.e2e
def test_auth_request_preserves_invitation_server_context(admission_client) -> None:
    client, monkeypatch = admission_client
    captured = {}
    expires_at = datetime.now() + timedelta(minutes=15)
    monkeypatch.setattr(routes.settings, "auth_magic_link_dev_mode", True)
    monkeypatch.setattr(
        routes.auth_service,
        "create_magic_link_request",
        lambda **kwargs: captured.update(kwargs) or MagicLinkRequestResult(
            email="owner@example.test",
            expires_at=expires_at,
            dev_magic_token="dev-token",
            organization_invitation_id=17,
        ),
    )
    monkeypatch.setattr(
        routes,
        "_public_invitation_by_id",
        lambda invitation_id: OrganizationInvitationPublicResponse(
            organization_id=3,
            organization_name="Организация A",
            invitation_intro=None,
            expires_at=expires_at,
        ) if invitation_id == 17 else None,
    )

    response = client.post(
        "/users/auth/email/request-link",
        json={"email": "owner@example.test", "organization_invitation_token": "shared-token"},
    )

    assert response.status_code == 200
    assert captured["organization_invitation_token"] == "shared-token"
    assert response.json()["organization"]["organization_id"] == 3
