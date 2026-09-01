from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import Api.routes as routes


class ShadowAggregateRepository:
    def aggregate_comparisons(self, *, connection):
        assert connection is not None
        return {
            "totals": {
                "run_count": 2,
                "completed_count": 1,
                "failed_count": 1,
                "compared_skill_count": 2,
                "exact_level_match_count": 1,
                "exact_level_match_percent": 50.0,
            },
            "groups": [],
        }


class ShadowBatchService:
    def preview(self, **kwargs):
        assert kwargs["max_competency_runs"] == 1
        return {
            "dry_run": True, "planned_competency_runs": 1, "maximum_llm_attempts": 2,
            "completed_runs": 0, "failed_runs": 0,
            "targets": [{"session_id": 42, "competency_code": "communication"}],
        }

    def execute(self, **_kwargs):
        raise RuntimeError("Universal LLM and shadow feature flags must both be enabled.")


@contextmanager
def _connection():
    yield object()


@pytest.fixture
def shadow_admin_client(monkeypatch):
    monkeypatch.setattr(routes, "assessment_shadow_repository", ShadowAggregateRepository())
    monkeypatch.setattr(routes, "assessment_shadow_batch_service", ShadowBatchService())
    monkeypatch.setattr(routes, "get_connection", _connection)
    monkeypatch.setattr(
        routes.web_session_service,
        "get_user_by_token",
        lambda token: (
            SimpleNamespace(
                id=7,
                email="admin@example.test",
                created_at=datetime.now(timezone.utc),
            )
            if token in {"superadmin", "org-admin"}
            else None
        ),
    )

    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client, monkeypatch


@pytest.mark.e2e
def test_shadow_comparison_requires_session(shadow_admin_client) -> None:
    client, _monkeypatch = shadow_admin_client
    response = client.get("/users/admin/assessment-shadow-comparisons")
    assert response.status_code == 401


@pytest.mark.e2e
def test_shadow_comparison_rejects_non_superadmin(shadow_admin_client) -> None:
    client, monkeypatch = shadow_admin_client
    monkeypatch.setattr(
        routes,
        "_require_superadmin",
        lambda *_args: (_ for _ in ()).throw(HTTPException(status_code=403, detail="Superadmin access required")),
    )
    client.cookies.set(routes.SESSION_COOKIE_NAME, "org-admin")

    response = client.get("/users/admin/assessment-shadow-comparisons")

    assert response.status_code == 403
    assert response.json()["detail"] == "Superadmin access required"


@pytest.mark.e2e
def test_shadow_comparison_returns_sanitized_aggregate(shadow_admin_client) -> None:
    client, monkeypatch = shadow_admin_client
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)
    client.cookies.set(routes.SESSION_COOKIE_NAME, "superadmin")

    response = client.get("/users/admin/assessment-shadow-comparisons")

    assert response.status_code == 200
    assert response.json()["totals"]["exact_level_match_percent"] == 50.0
    assert "session_id" not in response.text
    assert "official_summary_json" not in response.text


@pytest.mark.e2e
def test_shadow_batch_dry_run_returns_bounded_plan(shadow_admin_client) -> None:
    client, monkeypatch = shadow_admin_client
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)
    client.cookies.set(routes.SESSION_COOKIE_NAME, "superadmin")

    response = client.post("/users/admin/assessment-shadow-batches", json={"dry_run": True})

    assert response.status_code == 200
    assert response.json()["planned_competency_runs"] == 1
    assert response.json()["maximum_llm_attempts"] == 2


@pytest.mark.e2e
def test_shadow_batch_execute_reports_disabled_flags_as_conflict(shadow_admin_client) -> None:
    client, monkeypatch = shadow_admin_client
    monkeypatch.setattr(routes, "_require_superadmin", lambda *_args: None)
    client.cookies.set(routes.SESSION_COOKIE_NAME, "superadmin")

    response = client.post(
        "/users/admin/assessment-shadow-batches",
        json={"dry_run": False, "confirm_paid_calls": True},
    )

    assert response.status_code == 409
    assert "feature flags" in response.json()["detail"]
