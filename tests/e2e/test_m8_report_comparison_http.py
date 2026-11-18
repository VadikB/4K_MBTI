from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import routes


pytestmark = pytest.mark.e2e


def test_comparison_rechecks_both_cycles_and_binds_exact_reports(monkeypatch):
    now = datetime.now(timezone.utc)
    current_id, previous_id = uuid4(), uuid4()
    current_cycle, previous_cycle = uuid4(), uuid4()
    current_scope = {
        "id": current_id, "cycle_db_id": 20, "cycle_id": current_cycle,
        "organization_id": 7, "owner_user_id": 91, "cycle_created_at": now,
        "collection_closed_at": now,
    }
    previous_scope = {
        "id": previous_id, "cycle_id": previous_cycle, "organization_id": 7,
        "owner_user_id": 91, "cycle_created_at": now - timedelta(days=30),
        "collection_closed_at": now - timedelta(days=29),
    }

    class Connection:
        def execute(self, sql, params=None):
            self.row = current_scope if "WHERE p.id=%s" in sql and params[0] == current_id else previous_scope
            return self
        def fetchone(self):
            return self.row

    @contextmanager
    def connection():
        yield Connection()

    reports = {
        current_id: {"id": str(current_id), "cycle_id": str(current_cycle)},
        previous_id: {"id": str(previous_id), "cycle_id": str(previous_cycle)},
    }
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda token: SimpleNamespace(id=91) if token == "owner" else None)
    checked = []
    monkeypatch.setattr(routes.m8_results, "owner_can_read_cycle", lambda _c, cycle, user: checked.append((cycle, user)) or True)
    monkeypatch.setattr(routes.m8_results, "read_report", lambda _c, report_id: reports[report_id])
    monkeypatch.setattr(routes.m8_report_comparison, "compare_reports", lambda current, previous: {
        "current": current["id"], "previous": previous["id"], "mode": "numeric",
    })
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        url = f"/users/assessment/m8/reports/{current_id}/comparison?previous_report_id={previous_id}"
        assert client.get(url).status_code == 401
        client.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
        response = client.get(url)
        assert response.status_code == 200
        assert response.json() == {"current": str(current_id), "previous": str(previous_id), "mode": "numeric"}
        assert checked == [(str(current_cycle), 91), (str(previous_cycle), 91)]


def test_comparison_rejects_foreign_previous_report(monkeypatch):
    now = datetime.now(timezone.utc)
    current_id, previous_id = uuid4(), uuid4()
    current_scope = {"id": current_id, "cycle_db_id": 20, "cycle_id": uuid4(), "organization_id": 7,
                     "owner_user_id": 91, "cycle_created_at": now, "collection_closed_at": now}
    previous_scope = {"id": previous_id, "cycle_id": uuid4(), "organization_id": 8,
                      "owner_user_id": 92, "cycle_created_at": now - timedelta(days=1), "collection_closed_at": now}

    class Connection:
        def execute(self, sql, params=None):
            self.row = current_scope if params[0] == current_id else previous_scope
            return self
        def fetchone(self): return self.row

    @contextmanager
    def connection(): yield Connection()
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=91))
    monkeypatch.setattr(routes.m8_results, "owner_can_read_cycle", lambda *_: True)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        response = client.get(f"/users/assessment/m8/reports/{current_id}/comparison?previous_report_id={previous_id}")
        assert response.status_code == 403
        assert "skills" not in response.text


def test_fix02_http_projects_both_partial_outcomes_and_real_pdf_with_unchanged_acl(monkeypatch):
    from scripts.report_preview_fixture import saved_reports
    from pypdf import PdfReader
    from io import BytesIO
    from copy import deepcopy

    reports = saved_reports()
    current, previous = reports["partial-current"], reports["partial-previous"]
    before = deepcopy((current, previous))
    class Connection:
        def execute(self, _sql, params=None):
            report = current if str(params[0]) == current["id"] else previous
            self.row = {"id": report["id"], "cycle_db_id": 1, "cycle_id": report["cycle_id"],
                "owner_user_id": 18, "organization_id": 1,
                "collection_closed_at": datetime.fromisoformat(report["collection_closed_at"].replace("Z", "+00:00"))}
            return self
        def fetchone(self): return self.row
    @contextmanager
    def connection(): yield Connection()
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda token: SimpleNamespace(id=18) if token == "owner" else None)
    monkeypatch.setattr(routes.m8_results, "owner_can_read_cycle", lambda *_: True)
    monkeypatch.setattr(routes.m8_results, "read_report", lambda _c, report_id: current if str(report_id) == current["id"] else previous)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        base = f"/users/assessment/m8/reports/{current['id']}/comparison"
        suffix = f"?previous_report_id={previous['id']}"
        assert client.get(base + suffix).status_code == 401
        client.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
        response = client.get(base + suffix)
        assert response.status_code == 200
        first = response.json()["skills"][0]
        assert first["difference"] == .25
        assert first["previous_result"]["outcome"] == first["current_result"]["outcome"] == "partial_score"
        pdf = client.get(base + ".pdf" + suffix)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
        text = " ".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        assert "+0,25" in text and text.count("Результат по части навыка") == 2
    assert (current, previous) == before
