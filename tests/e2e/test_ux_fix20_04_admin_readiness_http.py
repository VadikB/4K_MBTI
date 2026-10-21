from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes
from Api.org_access import AdminScope
from Api.schemas import AdminOrganizationItem, AdminOrganizationsResponse


pytestmark = pytest.mark.e2e


class _Result:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _Connection:
    def __init__(self):
        self.statements = []

    def execute(self, query, params=()):
        self.statements.append((query, params))
        if "FROM questionnaire_response_revisions" in query:
            return _Result(many=[{
                "id": 8, "assignment_ref": "assessment-a", "status": "confirmed",
                "channel": "product_form", "validation_json": {}, "answers_json": {},
                "confirmed_at": None,
            }])
        return _Result()

    def commit(self):
        return None

    def rollback(self):
        return None


def _client(monkeypatch, connection, scope):
    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=18))
    monkeypatch.setattr(routes, "_get_admin_scope_or_403", lambda *_args: scope)
    monkeypatch.setattr(routes, "get_admin_scope", lambda *_args: scope)
    monkeypatch.setattr(routes, "ensure_configured_organizations", lambda *_args: None)
    monkeypatch.setattr(routes, "_build_admin_organizations", lambda *_args: AdminOrganizationsResponse(
        title="Организация и участники", subtitle="", is_superadmin=False,
        items=[AdminOrganizationItem(id=3, code="new-code", name="Новое название")],
    ))
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_org_admin_initial_setup_updates_only_the_single_attached_card(monkeypatch):
    connection = _Connection()
    response = _client(monkeypatch, connection, AdminScope(organization_ids=(3,))).post(
        "/users/admin/organizations", json={"code": "new-code", "name": "Новое название"},
    )
    assert response.status_code == 200
    writes = [(query, params) for query, params in connection.statements if query.lstrip().startswith(("UPDATE", "INSERT"))]
    assert len(writes) == 1
    assert writes[0][0].lstrip().startswith("UPDATE organizations")
    assert writes[0][1] == ("new-code", "Новое название", 3)


@pytest.mark.parametrize("organization_ids", [(), (3, 4)])
def test_org_admin_initial_setup_rejects_missing_or_ambiguous_scope(monkeypatch, organization_ids):
    connection = _Connection()
    response = _client(monkeypatch, connection, AdminScope(organization_ids=organization_ids)).post(
        "/users/admin/organizations", json={"code": "new-code", "name": "Новое название"},
    )
    assert response.status_code == 403
    assert not any(query.lstrip().startswith(("UPDATE", "INSERT")) for query, _params in connection.statements)


def test_org_admin_cannot_substitute_foreign_organization_id(monkeypatch):
    connection = _Connection()
    response = _client(monkeypatch, connection, AdminScope(organization_ids=(3,))).patch(
        "/users/admin/organizations/4", json={"name": "Чужая организация"},
    )
    assert response.status_code == 403
    assert not any(query.lstrip().startswith(("UPDATE", "INSERT")) for query, _params in connection.statements)


def test_questionnaire_list_returns_server_readiness_for_the_same_assignment(monkeypatch):
    connection = _Connection()
    client = _client(monkeypatch, connection, AdminScope(organization_ids=(3,)))
    monkeypatch.setattr(routes.questionnaire_sources, "admin_assignment_readiness", lambda *_args, **kwargs: {
        "status": "ready", "assignment_ref": kwargs["assignment_ref"],
        "early": {"status": "ready", "message": "Готово", "missing": []},
        "context": {"status": "ready", "message": "Готово"},
        "roles": {"status": "ready", "message": "Готово", "ready": 1, "total": 1},
        "preparation": {"status": "idle", "message": "Не запущено"},
    })
    response = client.get("/users/admin/organizations/3/questionnaire")
    assert response.status_code == 200
    assert response.json()["items"][0]["assignment_ref"] == "assessment-a"
    assert response.json()["items"][0]["readiness"]["assignment_ref"] == "assessment-a"
