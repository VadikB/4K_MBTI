from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import Api.routes as routes

pytestmark = pytest.mark.e2e


@pytest.fixture
def client(monkeypatch):
    class Connection:
        def commit(self):
            pass

    @contextmanager
    def connection():
        yield Connection()

    def authorize(_connection, user):
        if user is None:
            raise HTTPException(401)
        if user.id != 7:
            raise HTTPException(403)

    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes, "_require_superadmin", authorize)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda t: SimpleNamespace(id=7 if t == "admin" else 8))
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as c:
        yield c, monkeypatch


def test_lab_requires_superadmin_for_reads_and_generation(client):
    c, _ = client
    payload = {"run_id": str(uuid4()), "case_id": "SCR.A01", "base_role": "team_lead"}
    for expected, token in ((401, None), (403, "member")):
        if token:
            c.cookies.set(routes.SESSION_COOKIE_NAME, token)
        assert c.get("/users/admin/m5-lab").status_code == expected
        assert c.post("/users/admin/m5-lab/runs", json=payload).status_code == expected
        assert c.get("/users/admin/m5-lab/runs/" + payload["run_id"]).status_code == expected


def test_lab_generates_and_returns_reread_artifacts(client):
    c, monkeypatch = client
    c.cookies.set(routes.SESSION_COOKIE_NAME, "admin")
    payload = {"run_id": str(uuid4()), "case_id": "SCR.A01", "base_role": "team_lead"}
    row = {}

    def begin(_connection, *, request, user_id):
        if row:
            return row, False
        row.update(run_id=str(request.run_id), input_json=routes.m5_generation_lab.build_generation_input(request), status="running")
        return row, True

    def finish(_connection, *, run_id, output, error_code):
        row.update(status="failed" if error_code else "completed", output_json=output, error_code=error_code)

    monkeypatch.setattr(routes.m5_generation_lab, "begin_run", begin)
    monkeypatch.setattr(routes.m5_generation_lab, "finish_run", finish)
    monkeypatch.setattr(routes.m5_generation_lab, "get_run", lambda *_: row)
    response = c.post("/users/admin/m5-lab/runs", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert len(response.json()["output_json"]["observability"]) == 2
    assert c.get("/users/admin/m5-lab/runs/" + payload["run_id"]).json() == response.json()
    monkeypatch.setattr(routes.m5_generation_lab, "generate", lambda *_: pytest.fail("Duplicate generation"))
    assert c.post("/users/admin/m5-lab/runs", json=payload).json() == response.json()


def test_lab_catalog_exposes_only_two_supported_roles(client):
    c, _ = client
    c.cookies.set(routes.SESSION_COOKIE_NAME, "admin")
    catalog = c.get("/users/admin/m5-lab").json()
    assert len(catalog["cases"]) == 20
    assert {r["code"] for r in catalog["roles"]} == {"team_lead", "project_product_process_manager"}
    response = c.post("/users/admin/m5-lab/runs", json={"run_id": str(uuid4()), "case_id": "SCR.A01", "base_role": "student"})
    assert response.status_code == 422
