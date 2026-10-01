from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, owner_id=7, scope="assessment"):
        self.owner_id = owner_id
        self.scope = scope

    def execute(self, *_args, **_kwargs):
        return Result({"user_id": self.owner_id, "usage_scope": self.scope})

    def commit(self):
        pass


@pytest.fixture
def client(monkeypatch):
    connection = Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id=7) if token == "owner" else SimpleNamespace(id=8) if token else None)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as value:
        yield value, monkeypatch, connection


def test_product_route_checks_owner_and_admission_gate(client):
    http, monkeypatch, connection = client
    situation_id = str(uuid4())
    monkeypatch.setattr(routes.m5_scenario_runtime, "start",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("AS_NOT_ADMITTED")))
    assert http.post(f"/users/assessment/m5/situations/{situation_id}/start").status_code == 401
    http.cookies.set(routes.SESSION_COOKIE_NAME, "other")
    assert http.post(f"/users/assessment/m5/situations/{situation_id}/start").status_code == 403
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
    response = http.post(f"/users/assessment/m5/situations/{situation_id}/start")
    assert response.status_code == 409
    assert response.json() == {"detail": "AS_NOT_ADMITTED"}
    connection.scope = "qa"
    assert http.post(f"/users/assessment/m5/situations/{situation_id}/start").json() == {
        "detail": "QA_AS_NOT_AVAILABLE_IN_PRODUCT_ROUTE"
    }


def test_product_turn_and_transition_use_runtime_without_exposing_execution_snapshot(client):
    http, monkeypatch, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
    situation_id = str(uuid4())
    monkeypatch.setattr(routes.m5_scenario_runtime, "submit_turn",
                        lambda *_args, **kwargs: {"turn": {"content_text": kwargs["content"]}, "events": []})
    turn = http.post(f"/users/assessment/m5/situations/{situation_id}/turns", json={
        "request_id": "turn-1", "turn_id": str(uuid4()), "content": "Ответ",
    })
    assert turn.status_code == 200
    assert "execution_payload" not in turn.text
    monkeypatch.setattr(routes.m5_scenario_runtime, "transition",
                        lambda *_args, **kwargs: {"status": kwargs["action"], "idempotent": False})
    transition = http.post(f"/users/assessment/m5/situations/{situation_id}/transitions", json={
        "request_id": "pause-1", "action": "pause", "reason": "Пауза участника",
    })
    assert transition.status_code == 200
    assert transition.json()["status"] == "pause"


def test_admin_c45_and_technical_qa_evidence_use_common_runtime(client):
    http, monkeypatch, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
    situation_id = str(uuid4())
    monkeypatch.setattr(routes, "_require_superadmin", lambda _connection, _user: SimpleNamespace(is_superadmin=True))
    monkeypatch.setattr(
        routes.m5_scenario_runtime,
        "build_c45",
        lambda *_args, **kwargs: {
            "assessment_situation_id": situation_id,
            "mode": kwargs["mode"],
            "envelope_json": {"boundary_sequence": 12, "contains_evidence": False},
        },
    )
    c45 = http.post(f"/users/admin/m5-runtime/situations/{situation_id}/c45?mode=interim")
    assert c45.status_code == 200
    assert c45.json()["mode"] == "interim"
    assert c45.json()["envelope_json"]["contains_evidence"] is False

    monkeypatch.setattr(
        routes.m5_storage,
        "record_technical_qa_evidence",
        lambda *_args, **kwargs: {
            "assessment_situation_id": situation_id,
            "evidence_json": {
                "eligibility": "technical_qa",
                "empirical_pilot": "NOT_RUN",
                "trajectory": kwargs["trajectory"],
            },
        },
    )
    evidence = http.post(f"/users/admin/m5-runtime/situations/{situation_id}/qa-evidence", json={
        "trajectory": "content_progress",
        "expected": {"runtime": "trace_saved"},
        "actual": {"events": 12},
        "defects": [],
    })
    assert evidence.status_code == 200
    assert evidence.json()["evidence_json"] == {
        "eligibility": "technical_qa",
        "empirical_pilot": "NOT_RUN",
        "trajectory": "content_progress",
    }
