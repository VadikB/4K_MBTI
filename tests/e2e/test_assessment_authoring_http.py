from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes
from Api.assessment_configuration import LEGACY_METHODOLOGY_DEFINITION


class AuthoringContractService:
    def __init__(self) -> None:
        self.row = {
            "id": 41,
            "code": "baseline_http_4k",
            "name": "Baseline HTTP 4K",
            "version": 1,
            "status": "draft",
            "description": "HTTP contract smoke",
            "definition_json": {**LEGACY_METHODOLOGY_DEFINITION, "code": "baseline_http_4k"},
            "checksum": "a" * 64,
            "created_at": datetime.now(timezone.utc),
            "published_at": None,
        }
        self.transitions: list[tuple[str, int, int]] = []

    def create_definition(self, _connection, **kwargs):
        assert kwargs["entity_type"] == "methodology"
        assert kwargs["actor_user_id"] == 7
        assert kwargs["code"] == "baseline_http_4k"
        return dict(self.row)

    def submit_for_review(self, _connection, **kwargs):
        self.transitions.append(("submit", kwargs["version_id"], kwargs["actor_user_id"]))
        self.row["status"] = "ready_for_review"
        return dict(self.row)

    def publish(self, _connection, **kwargs):
        self.transitions.append(("publish", kwargs["version_id"], kwargs["actor_user_id"]))
        self.row["status"] = "published"
        self.row["published_at"] = datetime.now(timezone.utc)
        return dict(self.row)


@contextmanager
def _connection():
    yield object()


@pytest.fixture
def authoring_http_client(monkeypatch):
    service = AuthoringContractService()
    monkeypatch.setattr(routes, "assessment_authoring_service", service)
    monkeypatch.setattr(routes, "get_connection", _connection)
    monkeypatch.setattr(routes, "require_platform_permission", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda token: SimpleNamespace(id=7, email="methodologist@example.test") if token == "valid" else None,
    )
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, service


@pytest.mark.e2e
def test_methodology_http_contract_create_submit_publish(authoring_http_client) -> None:
    client, service = authoring_http_client
    client.cookies.set(routes.SESSION_COOKIE_NAME, "valid")

    created = client.post(
        "/users/admin/assessment-definitions/methodology",
        json={
            "code": "baseline_http_4k",
            "name": "Baseline HTTP 4K",
            "description": "HTTP contract smoke",
            "definition": LEGACY_METHODOLOGY_DEFINITION,
            "comment": "create baseline contract",
        },
    )
    assert created.status_code == 200
    assert created.json()["status"] == "draft"

    submitted = client.post(
        "/users/admin/assessment-definitions/methodology/41/submit",
        json={"comment": "ready for review"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "ready_for_review"

    published = client.post(
        "/users/admin/assessment-definitions/methodology/41/publish",
        json={"comment": "approved"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert service.transitions == [("submit", 41, 7), ("publish", 41, 7)]


@pytest.mark.e2e
def test_methodology_authoring_requires_session(authoring_http_client) -> None:
    client, _service = authoring_http_client
    response = client.post(
        "/users/admin/assessment-definitions/methodology",
        json={
            "code": "baseline_http_4k",
            "name": "Baseline HTTP 4K",
            "definition": LEGACY_METHODOLOGY_DEFINITION,
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Admin session not found"
