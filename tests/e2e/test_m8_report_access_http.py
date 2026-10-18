from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import routes


pytestmark = pytest.mark.e2e


def test_customer_direct_report_and_pdf_recheck_access(monkeypatch):
    report_id = uuid4()
    report = {"id": str(report_id), "owner_user_id": 10, "cycle_id": str(uuid4()),
              "audience": "assessee", "c67": {"skills": [], "limitations": [], "coverage": {},
              "reliability": {}, "descriptive": {"status": "ready", "summary": []}}}
    @contextmanager
    def connection():
        yield SimpleNamespace(commit=lambda: None)
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id={"selected": 20, "other": 21}[token]) if token in {"selected", "other"} else None)
    monkeypatch.setattr(routes.m8_report_access, "customer_can_read_report",
                        lambda _connection, report_id, user_id: user_id == 20)
    monkeypatch.setattr(routes.m8_results, "read_report", lambda *_: report)
    monkeypatch.setattr(routes.m8_report_access, "customer_projection",
                        lambda value: {**value, "audience": "customer"})
    monkeypatch.setattr(routes.m8_report_access, "record_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes.m8_results, "render_pdf", lambda value: b"%PDF-synthetic")
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        url = f"/users/admin/m8-access/reports/{report_id}"
        assert client.get(url).status_code == 401
        client.cookies.set(routes.SESSION_COOKIE_NAME, "other")
        denied = client.get(url)
        assert denied.status_code == 403 and "skills" not in denied.text
        assert client.get(url + "/pdf").status_code == 403
        client.cookies.set(routes.SESSION_COOKIE_NAME, "selected")
        assert client.get(url).json()["audience"] == "customer"
        pdf = client.get(url + "/pdf")
        assert pdf.status_code == 200 and pdf.content == b"%PDF-synthetic"
