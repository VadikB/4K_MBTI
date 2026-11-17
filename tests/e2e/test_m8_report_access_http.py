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
    monkeypatch.setattr(routes.m8_report_corrections, "public_notice", lambda *_args: None)
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


def test_customer_list_parameters_and_retired_routes(monkeypatch):
    calls = []
    @contextmanager
    def connection():
        yield object()
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                        lambda token: SimpleNamespace(id=20) if token == 'admin' else None)
    def page(_connection, **kwargs):
        calls.append(kwargs)
        if kwargs['organization_id'] == 99:
            raise PermissionError('forbidden')
        return {'items': [], 'total': 0, 'page': kwargs['page'], 'page_size': kwargs['page_size'],
                'organization_id': 1, 'organizations': [{'id': 1, 'name': 'Организация'}], 'programs': []}
    monkeypatch.setattr(routes.m8_report_access, 'page_customer_reports', page)
    monkeypatch.setattr(routes, '_require_matching_session_user', lambda *_args: None)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        url = '/users/admin/m8-access/reports'
        assert client.get(url).status_code == 401
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'admin')
        response = client.get(url, params={'organization_id': 1, 'query': 'Иван',
                                           'program': 'Пилот', 'status': 'ready', 'page': 2, 'page_size': 10})
        assert response.status_code == 200 and response.json()['total'] == 0
        assert calls[-1] == {'user_id': 20, 'organization_id': 1, 'query': 'Иван',
                             'program': 'Пилот', 'status': 'ready', 'page': 2, 'page_size': 10}
        assert client.get(url, params={'organization_id': 99}).status_code == 403
        assert client.get(url, params={'page': 0}).status_code == 422
        for path in ('/users/admin/reports', '/users/admin/reports.pdf',
                     '/users/admin/reports/123', '/users/admin/reports/123/expert.pdf'):
            assert client.get(path).status_code == 410
        assert client.post('/users/admin/reports/expert-group.zip').status_code == 410
        assert client.get('/users/20/assessment/123/report.pdf').status_code == 410


def test_public_api_and_pdf_share_compatible_copy_without_rewriting_c67(monkeypatch):
    from copy import deepcopy
    from io import BytesIO
    from pypdf import PdfReader

    report_id = uuid4()
    report = {"id": str(report_id), "cycle_id": str(uuid4()), "owner_user_id": 10,
              "program_name": "Контрольная HTTP программа", "collection_closed_at": "2026-11-17",
              "c67": {"template_version": "m8-basic-report/1.5.0", "skills": [
                  {"skill_id": "S", "skill_name": "HTTP навык", "outcome": "full_score",
                   "completeness": "full", "score": {"value": 0, "numerator": 0, "denominator": 1}}],
                  "limitations": ["Skill Level is not derived from numeric Score", "Сохранённое ограничение"],
                  "descriptive": {"status": "ready", "summary": [], "claims": []}}}
    original = deepcopy(report)
    @contextmanager
    def connection():
        yield SimpleNamespace(commit=lambda: None)
    monkeypatch.setattr(routes, "get_connection", connection)
    monkeypatch.setattr(routes, "_owned_saved_report", lambda *_args, **_kwargs: report)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=20))
    monkeypatch.setattr(routes.m8_report_access, "customer_can_read_report", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(routes.m8_results, "read_report", lambda *_args: report)
    monkeypatch.setattr(routes.m8_report_corrections, "public_notice", lambda *_args: None)
    monkeypatch.setattr(routes.m8_report_access, "record_access", lambda *_args, **_kwargs: None)
    report["correction"] = None
    original["correction"] = None
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        for prefix in ("/users/assessment/m8", "/users/admin/m8-access"):
            url = f"{prefix}/reports/{report_id}"
            response = client.get(url)
            assert response.status_code == 200
            view = response.json()["c67"]
            assert view["skills"][0]["score"]["value"] == 0
            assert "Skill Level" not in response.text
            pdf = client.get(url + "/pdf")
            assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
            assert pdf.headers["content-disposition"] == f'attachment; filename="4k-report-{report_id}.pdf"'
            text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
            for message in view["limitations"] + ["Контрольная HTTP программа", "2026-11-17"]:
                assert message in text
    assert report == original
