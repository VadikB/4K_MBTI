from contextlib import contextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import telegram_channel_routes as routes
from Api.config import _parse_additional_telegram_subject_projects

pytestmark = pytest.mark.e2e
TOKEN = "synthetic-service-token-at-least-32-characters"
SUBJECT = str(uuid4())
ADDITIONAL_SUBJECT = str(uuid4())


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes.settings, "tg_bot_integration_token", TOKEN)
    monkeypatch.setattr(routes.settings, "tg_student_channel_enabled", True)
    monkeypatch.setattr(routes.settings, "tg_student_organization_id", 17)
    monkeypatch.setattr(
        routes.settings, "tg_student_allowed_subjects", frozenset({SUBJECT})
    )
    monkeypatch.setattr(routes.settings, "tg_student_allowed_project_code", "SYNTH-1")
    monkeypatch.setattr(routes.settings, "tg_student_additional_subject_projects", {})
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


def test_published_role_route_uses_validated_definition(client, monkeypatch):
    @contextmanager
    def connection():
        yield object()

    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes, "load_published_role_profile", lambda c, version_id: {
        "id": version_id, "code": "specialist_expert", "version": 1,
        "definition": {"methodology_version": "1.1"}, "checksum": "a" * 64,
    })
    response = client.get(
        "/integration/v1/role-profile-versions/2",
        headers={"Authorization": "Bearer " + TOKEN},
    )
    assert response.status_code == 200
    assert response.json() == {
        "id": 2, "code": "specialist_expert", "version": 1,
        "methodology_version": "1.1", "checksum": "a" * 64,
    }


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


@pytest.mark.parametrize("raw_value", ["[]", "{", '{"invalid":"SYNTH-2"}', "{}{}"])
def test_additional_subject_config_rejects_invalid_values(raw_value):
    with pytest.raises(ValueError, match="INVALID_TG_STUDENT_ADDITIONAL_SUBJECT_PROJECTS"):
        _parse_additional_telegram_subject_projects(raw_value)


def test_additional_subject_config_rejects_duplicate_keys():
    with pytest.raises(ValueError, match="INVALID_TG_STUDENT_ADDITIONAL_SUBJECT_PROJECTS"):
        _parse_additional_telegram_subject_projects(
            f'{{"{SUBJECT}":"SYNTH-1","{SUBJECT}":"SYNTH-2"}}'
        )


@pytest.mark.parametrize(
    ("subject", "project", "status"),
    [
        (SUBJECT, "SYNTH-1", 200),
        (ADDITIONAL_SUBJECT, "SYNTH-2", 200),
        (SUBJECT, "SYNTH-2", 404),
        (ADDITIONAL_SUBJECT, "SYNTH-1", 404),
        (ADDITIONAL_SUBJECT, "OTHER", 404),
    ],
)
def test_additional_scope_isolated_at_prepare_and_readback(
    client, monkeypatch, subject, project, status,
):
    monkeypatch.setattr(
        routes.settings,
        "tg_student_additional_subject_projects",
        _parse_additional_telegram_subject_projects(
            f'{{"{ADDITIONAL_SUBJECT}":"SYNTH-2","{SUBJECT}":"OTHER"}}'
        ),
    )

    class Connection:
        def commit(self):
            pass

    @contextmanager
    def connection():
        yield Connection()

    snapshot = {"participant": {"external_subject_ref": subject}, "project": {"code": project}}
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.channel, "prepare", lambda *args, **kwargs: {"assignment_ref": "synthetic"})
    monkeypatch.setattr(routes.channel, "refresh", lambda *args: {"status": "preparing"})
    monkeypatch.setattr(routes.channel, "context", lambda *args: {
        "organization_id": 17,
        "external_subject_ref": subject,
        "snapshot_json": snapshot,
    })
    monkeypatch.setattr(routes.channel, "program_options", lambda *args: [])
    headers = {"Authorization": "Bearer " + TOKEN}
    assert client.post(
        "/integration/v1/educational-contexts/prepare",
        headers=headers,
        json={"snapshot": snapshot, "checksum": "a" * 64},
    ).status_code == status
    assert client.post(
        "/integration/v1/educational-contexts/program-options",
        headers=headers,
        json={"assignment_ref": "synthetic"},
    ).status_code == status


def test_additional_subject_resolve_uses_configured_organization(client, monkeypatch):
    monkeypatch.setattr(
        routes.settings, "tg_student_additional_subject_projects", {ADDITIONAL_SUBJECT: "SYNTH-2"}
    )

    class Connection:
        def commit(self):
            pass

    @contextmanager
    def connection():
        yield Connection()

    def resolve(_connection, *, external_subject_ref, organization_id):
        assert external_subject_ref == ADDITIONAL_SUBJECT
        assert organization_id == 17
        return {"external_subject_ref": external_subject_ref, "status": "provisioned"}

    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.subjects, "resolve", resolve)
    headers = {"Authorization": "Bearer " + TOKEN}
    assert client.post(
        "/integration/v1/subjects/resolve", headers=headers, json=request(ADDITIONAL_SUBJECT)
    ).status_code == 200
    assert client.post(
        "/integration/v1/subjects/resolve", headers=headers,
        json={**request(ADDITIONAL_SUBJECT), "organization_ref": "organization:18"},
    ).status_code == 409
