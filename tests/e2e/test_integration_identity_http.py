from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import integration_routes
from Api.integration_identity_service import ParticipantIdentityResolution


pytestmark = pytest.mark.e2e


@contextmanager
def connection():
    class Connection:
        def commit(self):
            return None

    yield Connection()


VALID_TOKEN = "test-integration-token-at-least-32"


def client(monkeypatch, *, token: str = VALID_TOKEN) -> TestClient:
    monkeypatch.setattr(integration_routes.settings, "tg_bot_integration_token", token)
    monkeypatch.setattr(integration_routes, "get_connection", connection)
    app = FastAPI()
    app.include_router(integration_routes.router)
    return TestClient(app)


def test_identity_link_requires_service_token(monkeypatch) -> None:
    http = client(monkeypatch)
    payload = {"email": "student@example.edu", "display_name": "Студент"}

    assert http.post("/integration/v1/participants/resolve", json=payload).status_code == 401
    assert http.post(
        "/integration/v1/participants/resolve",
        json=payload,
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401


def test_identity_link_is_disabled_without_configured_token(monkeypatch) -> None:
    http = client(monkeypatch, token="")
    response = http.post(
        "/integration/v1/participants/resolve",
        json={"email": "student@example.edu", "display_name": "Студент"},
        headers={"Authorization": "Bearer any"},
    )
    assert response.status_code == 503


def test_identity_link_rejects_unsafe_configured_token(monkeypatch) -> None:
    http = client(monkeypatch, token="too-short")
    response = http.post(
        "/integration/v1/participants/resolve",
        json={"email": "student@example.edu", "display_name": "Студент"},
        headers={"Authorization": "Bearer too-short"},
    )
    assert response.status_code == 503


def test_identity_link_returns_only_internal_id_and_status(monkeypatch) -> None:
    captured = {}

    def resolve(_connection, **kwargs):
        captured.update(kwargs)
        return ParticipantIdentityResolution(agent4k_user_id=42, created=True)

    monkeypatch.setattr(integration_routes, "resolve_or_provision_participant", resolve)
    http = client(monkeypatch)
    response = http.post(
        "/integration/v1/participants/resolve",
        json={"email": " Student@Example.EDU ", "display_name": " Студент "},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json() == {"agent4k_user_id": 42, "status": "provisioned"}
    assert captured == {"email": "student@example.edu", "display_name": "Студент"}
