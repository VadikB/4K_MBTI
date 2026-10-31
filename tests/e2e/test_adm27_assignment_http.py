from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes


pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Connection:
    def __init__(self, members=(18, 19)):
        self.members = set(members)
        self.rows = []
        self.next_id = 1
        self.operations = {}
        self.bound_assignment_ids = []

    def execute(self, sql, params=()):
        if 'INSERT INTO organization_assessment_assignment_operations' in sql:
            self.operations.setdefault(tuple(params[:3]), params[3])
            return Result()
        if 'SELECT request_fingerprint FROM organization_assessment_assignment_operations' in sql:
            return Result(one={'request_fingerprint': self.operations[tuple(params)]})
        if "SELECT DISTINCT request_fingerprint" in sql:
            return Result(many=[{"request_fingerprint": row["fingerprint"]} for row in self.rows
                                if row["organization_id"] == params[0]
                                and row["actor_id"] == params[1] and row["operation_id"] == params[2]])
        if "FROM organization_memberships om" in sql:
            return Result(one={"user_id": params[1]} if params[1] in self.members else None)
        if "INSERT INTO organization_assessment_assignments" in sql:
            organization_id, user_id, assignment_ref, actor_id, revision_id, operation_id, fingerprint = params
            existing = next((row for row in self.rows if row["organization_id"] == organization_id
                             and row["user_id"] == user_id and row["assignment_ref"] == assignment_ref), None)
            if existing:
                return Result(one=None)
            row = {"id": self.next_id, "organization_id": organization_id, "user_id": user_id,
                   "assignment_ref": assignment_ref, "actor_id": actor_id, "revision_id": revision_id,
                   "operation_id": operation_id, "fingerprint": fingerprint}
            self.next_id += 1
            self.rows.append(row)
            return Result(one={"id": row["id"]})
        if "SELECT id FROM organization_assessment_assignments" in sql:
            row = next((row for row in self.rows if row["organization_id"] == params[0]
                        and row["user_id"] == params[1] and row["assignment_ref"] == params[2]), None)
            return Result(one={"id": row["id"]} if row else None)
        return Result()

    def commit(self):
        return None


@pytest.fixture
def client(monkeypatch):
    connection = Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes, "_require_organization_admin", lambda *_args: None)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=18))
    monkeypatch.setattr(routes.questionnaire_sources, "assignment_readiness", lambda *_args, **_kwargs: {
        "status": "ready", "questionnaire_revision_id": 71,
    })
    monkeypatch.setattr(routes.assessment_assignment_sources, "resolve_pilot_binding", lambda *_args, **_kwargs: {
        "assessment_configuration_id": 81, "role_profile_version_id": 91,
    })
    def bind(_connection, **kwargs):
        connection.bound_assignment_ids.append(kwargs["assignment_id"])
        return {"id": 1}

    monkeypatch.setattr(routes.assessment_assignment_sources, "bind", bind)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        yield http, connection


def test_org_admin_assigns_self_and_colleague_idempotently(client):
    http, connection = client
    payload = {"user_ids": [18, 19], "assignment_ref": "assessment-a", "operation_id": "adm27-operation-a"}
    first = http.post("/users/admin/organizations/3/assessment-assignments", json=payload)
    second = http.post("/users/admin/organizations/3/assessment-assignments", json=payload)
    assert first.status_code == 200
    assert [item["status"] for item in first.json()["items"]] == ["assigned", "assigned"]
    assert [item["status"] for item in second.json()["items"]] == ["already_assigned", "already_assigned"]
    assert {(row["user_id"], row["assignment_ref"]) for row in connection.rows} == {(18, "assessment-a"), (19, "assessment-a")}
    assert connection.bound_assignment_ids == [1, 2, 1, 2]


def test_assignment_rejects_operation_payload_substitution(client):
    http, _connection = client
    operation = "adm27-operation-conflict"
    assert http.post("/users/admin/organizations/3/assessment-assignments", json={
        "user_ids": [18], "assignment_ref": "assessment-a", "operation_id": operation,
    }).status_code == 200
    response = http.post("/users/admin/organizations/3/assessment-assignments", json={
        "user_ids": [19], "assignment_ref": "assessment-a", "operation_id": operation,
    })
    assert response.status_code == 409


def test_assignment_reports_foreign_recipient_without_side_effect(client):
    http, connection = client
    response = http.post("/users/admin/organizations/3/assessment-assignments", json={
        "user_ids": [999], "assignment_ref": "assessment-a", "operation_id": "adm27-foreign-user",
    })
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "not_assigned"
    assert connection.rows == []


def test_assignment_rejects_attempt_to_override_pilot_sources(client):
    http, connection = client
    response = http.post("/users/admin/organizations/3/assessment-assignments", json={
        "user_ids": [18], "assignment_ref": "assessment-a", "operation_id": "adm29-source-override",
        "assessment_configuration_id": 82, "role_profile_version_id": 92,
    })
    assert response.status_code == 409
    assert "Выбранная роль или версия программы не относится к текущей оценке" in response.text
    assert "PROGRAM_SOURCE_OVERRIDE_NOT_ALLOWED" not in response.text
    assert connection.rows == []


def test_connected_program_without_selected_role_returns_exact_action_code(client, monkeypatch):
    http, connection = client

    def require_role(*_args, **_kwargs):
        raise ValueError("PROGRAM_ROLE_SELECTION_REQUIRED")

    monkeypatch.setattr(routes.assessment_programs, "resolve", require_role)
    response = http.post("/users/admin/organizations/3/assessment-assignments", json={
        "user_ids": [18], "assignment_ref": "assessment-a", "operation_id": "adm42-role-required",
    })

    assert response.status_code == 409
    assert response.json()["detail"] == "PROGRAM_ROLE_SELECTION_REQUIRED"
    assert connection.rows == []
