"""REPORT-09 authorization and public projection over HTTP."""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from Api import routes

pytestmark = pytest.mark.e2e


def test_correction_commands_require_superadmin_before_storage(monkeypatch):
    @contextmanager
    def connection():
        yield SimpleNamespace(commit=lambda: None)
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                        lambda token: SimpleNamespace(id=7 if token == 'service' else 8) if token else None)
    def authorize(_connection, user):
        if user is None:
            raise HTTPException(401)
        if user.id != 7:
            raise HTTPException(403)
    monkeypatch.setattr(routes, '_require_superadmin', authorize)
    calls = []
    monkeypatch.setattr(routes.m8_report_corrections, 'prepare',
                        lambda *_args, **kwargs: calls.append(('prepare', kwargs)) or {'candidate_id': 'saved'})
    monkeypatch.setattr(routes.m8_report_corrections, 'publish',
                        lambda *_args, **kwargs: calls.append(('publish', kwargs)) or {'id': 'saved'})
    app = FastAPI(); app.include_router(routes.router)
    prepare = {'expected_report_id': str(uuid4()), 'result_revision_id': str(uuid4()),
               'kind': 'explanation', 'incident_ref': 'INC-SYNTHETIC',
               'participant_reason': 'Уточнение формулировки.', 'descriptive': {'summary': [], 'claims': []}}
    publish = {'candidate_id': str(uuid4()), 'expected_report_id': prepare['expected_report_id'],
               'idempotency_key': 'synthetic-key'}
    with TestClient(app) as client:
        for token, status in ((None, 401), ('owner', 403), ('org-admin', 403)):
            if token:
                client.cookies.set(routes.SESSION_COOKIE_NAME, token)
            else:
                client.cookies.clear()
            assert client.post('/users/admin/m8-report-corrections/candidates', json=prepare).status_code == status
            assert client.post('/users/admin/m8-report-corrections', json=publish).status_code == status
        assert calls == []
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'service')
        assert client.post('/users/admin/m8-report-corrections/candidates', json=prepare).status_code == 201
        assert client.post('/users/admin/m8-report-corrections', json=publish).status_code == 201
        assert [name for name, _ in calls] == ['prepare', 'publish']


def test_public_correction_notice_excludes_incident_and_internal_fields(monkeypatch):
    report_id = uuid4()
    cycle_id = uuid4()
    report = {'id': str(report_id), 'cycle_id': str(cycle_id), 'owner_user_id': 7,
              'c67': {'contract': 'C-67', 'skills': [], 'competencies': [], 'coverage': {},
                      'descriptive': {'status': 'ready', 'summary': ['Исправленный вывод'], 'claims': []},
                      'limitations': [], 'provenance': {'secret': 'private'},
                      'report_mechanism': {'id': 'm8', 'version': '1', 'checksum': 'private'}}}
    @contextmanager
    def connection():
        yield SimpleNamespace()
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token', lambda _token: SimpleNamespace(id=7))
    monkeypatch.setattr(routes, '_owned_saved_report',
                        lambda *_args, **_kwargs: {**report, 'correction': {
                            'created_at': '2026-11-17T10:00:00Z', 'reason': 'Уточнение вывода.',
                            'changes': [{'skill_id': None, 'skill_name': None, 'field': 'summary',
                                         'before': ['Ранее'], 'after': ['Исправлено']}]}})
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        result = client.get(f'/users/assessment/m8/reports/{report_id}')
    assert result.status_code == 200
    data = result.json()
    assert data['correction']['reason'] == 'Уточнение вывода.'
    assert 'incident' not in str(data).lower()
    assert 'secret' not in str(data)


def test_customer_freshness_checks_current_membership(monkeypatch):
    cycle_id = uuid4()
    report_id = str(uuid4())
    class Result:
        def fetchone(self):
            return {'id': 5}
    class Connection:
        def execute(self, *_args):
            return Result()
    @contextmanager
    def connection():
        yield Connection()
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                        lambda token: SimpleNamespace(id=20 if token == 'selected' else 21) if token else None)
    monkeypatch.setattr(routes.m8_report_corrections, 'current_report_id', lambda *_args: report_id)
    monkeypatch.setattr(routes.m8_report_access, 'customer_can_read_report',
                        lambda _connection, report_id, user_id: user_id == 20)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        url = f'/users/admin/m8-access/cycles/{cycle_id}/reports/latest'
        assert client.get(url).status_code == 401
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'other')
        assert client.get(url).status_code == 403
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'selected')
        assert client.get(url).json() == {'id': report_id}
