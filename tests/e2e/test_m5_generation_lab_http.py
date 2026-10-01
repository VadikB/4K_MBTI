from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import Api.routes as routes

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, row=None): self.row = row
    def fetchone(self): return self.row


@pytest.fixture
def client(monkeypatch):
    class Connection:
        def __init__(self): self.run = None
        def execute(self, sql, params=()):
            if "FROM m5_runtime_lab_runs" in sql: return Result(self.run)
            if "INSERT INTO m5_runtime_lab_runs" in sql:
                self.run = {"run_id": str(params[0]), "created_by": params[1], "assessment_situation_db_id": params[2],
                            "request_checksum": params[3], "status": "active"}
                return Result(self.run)
            return Result()
        def commit(self): pass

    connection = Connection()
    @contextmanager
    def get_connection(): yield connection
    def authorize(_connection, user):
        if user is None: raise HTTPException(401)
        if user.id != 7: raise HTTPException(403)
    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes, "_require_superadmin", authorize)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id=7 if token == "admin" else 8) if token else None)
    monkeypatch.setattr(routes.m5_storage, "qa_lab_catalog", lambda *_: {
        "source_status": "WORKING", "qa_scope": True,
        "profiles": [{"id": 17, "base_role": "team_lead", "full_name": "QA profile"}],
        "cases": [{"case_id": "CASE-TDISC-04", "case_version": "v0.1", "title": "Case 4",
                   "base_role": "team_lead", "indicator_ids": ["K1.I01"], "admitted_for_assessment": False}],
    })
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as value: yield value, monkeypatch, connection


def payload():
    return {"run_id": str(uuid4()), "case_id": "CASE-TDISC-04", "case_version": "v0.1",
            "personalized_profile_id": 17}


def test_lab_requires_superadmin_before_runtime_access(client):
    http, _, _ = client
    for expected, token in ((401, None), (403, "member")):
        if token: http.cookies.set(routes.SESSION_COOKIE_NAME, token)
        assert http.get("/users/admin/m5-lab").status_code == expected
        assert http.post("/users/admin/m5-lab/runs", json=payload()).status_code == expected


def test_lab_catalog_uses_real_profiles_and_marks_working_cases(client):
    http, _, _ = client; http.cookies.set(routes.SESSION_COOKIE_NAME, "admin")
    catalog = http.get("/users/admin/m5-lab").json()
    assert catalog["qa_scope"] is True and catalog["profiles"][0]["id"] == 17
    assert catalog["cases"][0]["admitted_for_assessment"] is False


def test_lab_creates_qa_as_through_common_storage_and_runtime(client):
    http, monkeypatch, _ = client; http.cookies.set(routes.SESSION_COOKIE_NAME, "admin")
    calls = {}
    monkeypatch.setattr(routes.m5_storage, "import_package_directory", lambda *_: {"created": False})
    def prepare(_connection, **kwargs):
        calls.update(kwargs)
        return {"id": 51, "assessment_situation_id": "11111111-1111-4111-8111-111111111111",
                "snapshot": {"case_ref": {"id": "CASE-TDISC-04"}, "base_role": "team_lead",
                             "participant_payload": {}, "indicator_targets": [],
                             "admission": {"code": "CASE_NOT_ADMITTED"}}}
    monkeypatch.setattr(routes.m5_storage, "prepare_assessment_situation", prepare)
    monkeypatch.setattr(routes.m5_scenario_runtime, "start", lambda *_: {"participant_payload": {"initial_situation": "QA"}})
    monkeypatch.setattr(routes.m5_scenario_runtime, "trace", lambda *_: {"turns": [], "events": []})
    response = http.post("/users/admin/m5-lab/runs", json=payload())
    assert response.status_code == 200
    assert calls["usage_scope"] == "qa" and calls["qa_authorized_by"] == 7
    assert response.json()["snapshot_json"]["admission"]["code"] == "CASE_NOT_ADMITTED"


def test_client_cannot_supply_usage_scope(client):
    http, _, _ = client; http.cookies.set(routes.SESSION_COOKIE_NAME, "admin")
    assert http.post("/users/admin/m5-lab/runs", json=payload() | {"usage_scope": "assessment"}).status_code == 422
