from contextlib import contextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import telegram_channel_routes as routes

pytestmark = pytest.mark.e2e
TOKEN = "synthetic-service-token-at-least-32-characters"
SUBJECT = str(uuid4())


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes.settings, "tg_bot_integration_token", TOKEN)
    monkeypatch.setattr(routes.settings, "tg_student_channel_enabled", True)
    monkeypatch.setattr(routes.settings, "tg_student_organization_id", 17)
    monkeypatch.setattr(
        routes.settings, "tg_student_allowed_subjects", frozenset({SUBJECT})
    )
    monkeypatch.setattr(routes.settings, "tg_student_allowed_project_code", "SYNTH-1")
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def request(subject=SUBJECT):
    return dict(
        source_system="telegram_student_bot",
        external_subject_ref=subject,
        organization_ref="organization:17",
    )


def test_subject_route_fails_closed_before_database(client, monkeypatch):
    def forbidden():
        raise AssertionError("Database must not be opened")

    monkeypatch.setattr(routes, "get_connection", forbidden)
    assert (
        client.post("/integration/v1/subjects/resolve", json=request()).status_code
        == 401
    )
    headers = {"Authorization": "Bearer " + TOKEN}
    assert (
        client.post(
            "/integration/v1/subjects/resolve",
            json=request(str(uuid4())),
            headers=headers,
        ).status_code
        == 404
    )
    monkeypatch.setattr(routes.settings, "tg_student_channel_enabled", False)
    assert (
        client.post(
            "/integration/v1/subjects/resolve", json=request(), headers=headers
        ).status_code
        == 503
    )


def test_subject_contract_has_no_identity_or_login_fields(client, monkeypatch):
    class Connection:
        def commit(self):
            pass

    @contextmanager
    def connection():
        yield Connection()

    monkeypatch.setattr(routes, "get_connection", connection)
    seen = []

    def resolve(c, **kwargs):
        seen.append(kwargs)
        return {
            "external_subject_ref": SUBJECT,
            "status": "provisioned",
            "runtime_owner_id": 999,
        }

    monkeypatch.setattr(routes.subjects, "resolve", resolve)
    response = client.post(
        "/integration/v1/subjects/resolve",
        json=request(),
        headers={"Authorization": "Bearer " + TOKEN},
    )
    assert response.status_code == 200
    assert response.json() == {"external_subject_ref": SUBJECT, "status": "provisioned"}
    assert seen == [{"external_subject_ref": SUBJECT, "organization_id": 17}]
    assert (
        client.post(
            "/integration/v1/subjects/resolve",
            json={**request(), "email": "synthetic@example.test"},
            headers={"Authorization": "Bearer " + TOKEN},
        ).status_code
        == 422
    )


def test_context_rejects_other_project_before_database(client, monkeypatch):
    def forbidden():
        raise AssertionError("Database must not be opened")

    monkeypatch.setattr(routes, "get_connection", forbidden)
    response = client.post(
        "/integration/v1/educational-contexts/prepare",
        headers={"Authorization": "Bearer " + TOKEN},
        json={
            "snapshot": {
                "participant": {"external_subject_ref": SUBJECT},
                "project": {"code": "OTHER"},
            },
            "checksum": "a" * 64,
        },
    )
    assert response.status_code == 404
