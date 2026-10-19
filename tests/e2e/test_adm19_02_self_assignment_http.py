from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes


pytestmark = pytest.mark.e2e


class _Result:
    def __init__(self, *, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self):
        self.queries = []

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if "SELECT id FROM organizations" in sql:
            return _Result(row={"id": 3})
        if "JOIN organization_memberships om" in sql:
            assert "AND u.id <> %s" in sql
            assert params == (3, 18)
            return _Result(rows=[])
        return _Result()


@pytest.fixture
def client(monkeypatch):
    connection = _Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)
    monkeypatch.setattr(
        routes.web_session_service, "get_user_by_token",
        lambda token: SimpleNamespace(id=18) if token == "admin" else None,
    )
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME, "admin")
        yield http, connection


def test_single_prepare_refuses_self_assignment_before_query(client):
    http, connection = client
    response = http.post("/users/admin/organizations/3/members/18/prepare-assessment")
    assert response.status_code == 403
    assert connection.queries == []


def test_bulk_prepare_excludes_the_acting_user(client):
    http, connection = client
    response = http.post("/users/admin/organizations/3/prepare-assessments")
    assert response.status_code == 202
    assert response.json()["total_participants"] == 0
    assert any("AND u.id <> %s" in sql for sql, _params in connection.queries)
