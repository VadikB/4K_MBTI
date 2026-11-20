from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import integration_assessment_configuration_routes as integration_routes


pytestmark = pytest.mark.e2e
TOKEN = "synthetic-integration-token-at-least-32"


@contextmanager
def connection():
    yield object()


def test_configuration_options_require_service_token(monkeypatch) -> None:
    monkeypatch.setattr(integration_routes.settings, "tg_bot_integration_token", TOKEN)
    monkeypatch.setattr(integration_routes, "get_connection", connection)
    monkeypatch.setattr(
        integration_routes, "list_published_configurations", lambda _: []
    )
    app = FastAPI()
    app.include_router(integration_routes.router)
    client = TestClient(app)

    assert client.get("/integration/v1/assessment-configurations").status_code == 401
    assert client.get(
        "/integration/v1/assessment-configurations",
        headers={"Authorization": f"Bearer {TOKEN}"},
    ).json() == []


def test_configuration_options_return_references_only(monkeypatch) -> None:
    monkeypatch.setattr(integration_routes.settings, "tg_bot_integration_token", TOKEN)
    monkeypatch.setattr(integration_routes, "get_connection", connection)
    monkeypatch.setattr(
        integration_routes,
        "list_published_configurations",
        lambda _: [{
            "id": 17,
            "ref": "agent4k:configuration:17",
            "code": "standard",
            "name": "Стандартная",
            "methodology_ref": "agent4k:methodology:m1:v2",
            "reference_checksum": "a" * 64,
            "is_default": True,
        }],
    )
    app = FastAPI()
    app.include_router(integration_routes.router)
    response = TestClient(app).get(
        "/integration/v1/assessment-configurations",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json() == [{
        "id": 17,
        "ref": "agent4k:configuration:17",
        "code": "standard",
        "name": "Стандартная",
        "methodology_ref": "agent4k:methodology:m1:v2",
        "reference_checksum": "a" * 64,
        "is_default": True,
    }]
