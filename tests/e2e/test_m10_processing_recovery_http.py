from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes


pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, row): self.row = row
    def fetchone(self): return self.row


class Connection:
    def __init__(self, organization_id=11): self.organization_id = organization_id
    def execute(self, sql, _params):
        if "SELECT organization_id FROM m5_cycles" in sql:
            return Result({"organization_id": self.organization_id})
        raise AssertionError(sql)
    def commit(self): pass


@pytest.fixture
def http(monkeypatch):
    db = Connection()
    @contextmanager
    def connection(): yield db
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
        lambda token: SimpleNamespace(id=7, email="operator@example.test") if token == "operator" else None)
    monkeypatch.setattr(routes, "require_platform_permission",
        lambda _c, user, _p: None if user else (_ for _ in ()).throw(PermissionError("auth required")))
    monkeypatch.setattr(routes, "_get_admin_scope_or_403",
        lambda *_args: SimpleNamespace(is_superadmin=False, organization_ids=[11]))
    captured = {}
    def request_recovery(_connection, **kwargs):
        captured.update(kwargs)
        return {"id": uuid4(), "status": "queued"}
    monkeypatch.setattr(routes.m10_orchestration, "request_processing_recovery", request_recovery)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, db, captured


def test_recovery_requires_responsible_authority_and_server_actor(http):
    client, _db, captured = http
    cycle = uuid4()
    path = f"/users/admin/assessment/m8/cycles/{cycle}/processing-recovery"
    assert client.post(path, json={"idempotency_key":"retry-1"}).status_code == 401
    client.cookies.set(routes.SESSION_COOKIE_NAME, "operator")
    response = client.post(path, json={"idempotency_key":"retry-1"})
    assert response.status_code == 202
    assert captured == {"cycle_id":str(cycle), "idempotency_key":"retry-1", "created_by":7}


def test_recovery_rejects_foreign_organization(http):
    client, db, captured = http
    db.organization_id = 12
    client.cookies.set(routes.SESSION_COOKIE_NAME, "operator")
    response = client.post(f"/users/admin/assessment/m8/cycles/{uuid4()}/processing-recovery",
                           json={"idempotency_key":"retry-foreign"})
    assert response.status_code == 403
    assert captured == {}


def test_owner_status_has_stable_failure_projection_without_retry_button(monkeypatch):
    cycle=uuid4()
    class StatusConnection:
        def execute(self, sql, _params):
            if "SELECT owner_user_id,usage_scope FROM m5_cycles" in sql:
                return Result({"owner_user_id":17,"usage_scope":"assessment"})
            if "FROM m10_pipeline_runs" in sql:
                return Result({"status":"failed","stage":"admission_processing_failed",
                               "error_code":"M6_ADMISSION_PROCESSING_FAILED"})
            raise AssertionError(sql)
    @contextmanager
    def connection(): yield StatusConnection()
    monkeypatch.setattr(routes,"get_connection",connection)
    monkeypatch.setattr(routes.web_session_service,"get_user_by_token",lambda _token:SimpleNamespace(id=17))
    monkeypatch.setattr(routes.m8_results,"owner_can_read_cycle",lambda *_args:True)
    monkeypatch.setattr(routes.m7_completion,"read_status",lambda *_args:{"cycle_id":str(cycle),"collection_status":"calculated"})
    monkeypatch.setattr(routes.m8_results,"read_latest_report",lambda *_args:{"id":"report-1","status":"ready"})
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as client:
        client.cookies.set(routes.SESSION_COOKIE_NAME,"owner")
        response=client.get(f"/users/assessment/m8/cycles/{cycle}/status")
    assert response.status_code==200
    value=response.json()
    assert value["results_status"]=="failed" and value["report_status"]=="limited"
    assert value["report_id"]=="report-1"
    assert value["processing"]["allowed_actions"]==[]
    assert "Traceback" not in str(value)
