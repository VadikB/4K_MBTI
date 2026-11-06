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


def test_role_profile_endpoint_returns_only_published_reference(monkeypatch) -> None:
    monkeypatch.setattr(
        integration_routes,
        "load_published_role_profile",
        lambda _connection, version_id: {
            "id": version_id,
            "code": "specialist_expert",
            "version": 3,
            "definition": {"methodology_version": "1.1"},
            "checksum": "a" * 64,
        },
    )
    http = client(monkeypatch)
    response = http.get(
        "/integration/v1/role-profile-versions/17",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 17,
        "code": "specialist_expert",
        "version": 3,
        "methodology_version": "1.1",
        "checksum": "a" * 64,
    }
    assert "definition" not in response.text


def test_role_profile_endpoint_hides_draft_or_missing_version(monkeypatch) -> None:
    def missing(_connection, _version_id):
        raise ValueError("A published RoleProfile version is required.")

    monkeypatch.setattr(integration_routes, "load_published_role_profile", missing)
    http = client(monkeypatch)
    response = http.get(
        "/integration/v1/role-profile-versions/17",
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 404


def test_educational_context_prepare_returns_admission_reasons(monkeypatch) -> None:
    captured = {}

    def prepare(_connection, **kwargs):
        captured.update(kwargs)
        return {
            "operation_id": "educational-context:9",
            "status": "awaiting_admission",
            "organization_id": 4,
            "assignment_id": 12,
            "assignment_ref": "edu:4k-tg-bot:p1:a2",
            "reasons": ["PROGRAM_NOT_CONNECTED", "QUESTIONNAIRE_NOT_CONFIRMED"],
            "cycle_id": None,
        }

    monkeypatch.setattr(integration_routes.educational_contexts, "prepare", prepare)
    http = client(monkeypatch)
    snapshot = {
        "schema_version": 1,
        "kind": "educational_project_assessment_context",
        "assignment_ref": "edu:4k-tg-bot:p1:a2",
    }
    response = http.post(
        "/integration/v1/educational-contexts/prepare",
        json={"snapshot": snapshot, "checksum": "a" * 64},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_admission"
    assert response.json()["cycle_id"] is None
    assert captured == {"snapshot": snapshot, "snapshot_checksum": "a" * 64}


def test_educational_context_prepare_maps_contract_conflict(monkeypatch) -> None:
    def reject(_connection, **_kwargs):
        raise ValueError("EDUCATIONAL_CONTEXT_CHECKSUM_MISMATCH")

    monkeypatch.setattr(integration_routes.educational_contexts, "prepare", reject)
    response = client(monkeypatch).post(
        "/integration/v1/educational-contexts/prepare",
        json={"snapshot": {}, "checksum": "a" * 64},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "EDUCATIONAL_CONTEXT_CHECKSUM_MISMATCH"
