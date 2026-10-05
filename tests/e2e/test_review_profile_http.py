from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from Api import routes

pytestmark = pytest.mark.e2e
USER = dict(id=91, full_name='Synthetic participant', email='participant@example.test',
            created_at=datetime.now(timezone.utc), role_id=None, job_description=None, raw_duties=None)


@pytest.fixture
def profile_client(monkeypatch):
    class Connection:
        def __init__(self): self.queries = []; self.updates = 0; self.row = None
        def execute(self, sql, params=None):
            self.queries.append(sql)
            if 'UPDATE users' in sql:
                self.updates += 1
                self.row = None
            elif 'FROM users u' in sql: self.row = USER
            elif 'FROM m8_reports p' in sql and hasattr(self, 'report_scope'): self.row = self.report_scope
            else: self.row = None
            return self
        def fetchone(self): return self.row
        def fetchall(self): return []
        def commit(self): pass
    db = Connection()
    @contextmanager
    def factory(): yield db
    monkeypatch.setattr(routes, 'get_connection', factory)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
        lambda token: SimpleNamespace(id={'owner':91, 'same-org':92, 'other-org':93}[token],email='participant@example.test') if token in {'owner','same-org','other-org'} else None)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client: yield client, db


@pytest.mark.parametrize('token,status', [(None,401),('same-org',403),('other-org',403)])
def test_profile_owner_boundary_precedes_sql(profile_client, token, status):
    client, db = profile_client
    if token: client.cookies.set(routes.SESSION_COOKIE_NAME, token)
    assert client.get('/users/91').status_code == status
    assert client.get('/users/91/profile-summary').status_code == status
    assert client.patch('/users/91/profile', json={'email':'new@example.test'}).status_code == status
    assert db.queries == [] and db.updates == 0


def test_owner_can_read_and_update_profile(profile_client):
    client, db = profile_client
    client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    assert client.get('/users/91').status_code == 200
    assert client.get('/users/91/profile-summary').status_code == 200
    assert client.patch('/users/91/profile', json={'telegram':'@updated'}).status_code == 200
    assert db.updates == 1


def test_saved_report_owner_and_audience(profile_client, monkeypatch):
    client, db = profile_client
    report = {'owner_user_id':91, 'audience':'assessee', 'id':str(uuid4())}
    db.report_scope = {'cycle_id':str(uuid4()),'audience':'assessee'}
    monkeypatch.setattr(routes.m8_results,'owner_can_read_cycle',lambda connection,cycle,user:user==91)
    monkeypatch.setattr(routes.m8_results, 'read_report', lambda *_: report)
    url = '/users/assessment/m8/reports/' + report['id']
    assert client.get(url).status_code == 401
    client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    assert client.get(url).json() == report
    report['audience'] = 'organization'
    db.report_scope['audience'] = 'organization'
    assert client.get(url).status_code == 403
    report['audience'] = 'assessee'
    db.report_scope['audience'] = 'assessee'
    for token in ('same-org','other-org'):
        client.cookies.set(routes.SESSION_COOKIE_NAME, token)
        assert client.get(url).status_code == 403


def test_user_listing_requires_scoped_admin(profile_client, monkeypatch):
    from fastapi import HTTPException
    from Api.org_access import AdminScope
    client, db = profile_client
    assert client.get('/users').status_code == 401
    assert db.queries == []
    client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    def denied(*_): raise HTTPException(403, detail='Admin access required')
    monkeypatch.setattr(routes, '_get_admin_scope_or_403', denied)
    assert client.get('/users').status_code == 403
    assert db.queries == []
    monkeypatch.setattr(routes, '_get_admin_scope_or_403', lambda *_: AdminScope(organization_ids=(10,)))
    assert client.get('/users').status_code == 200
    assert 'organization_id' in db.queries[-1] and 'ANY' in db.queries[-1]


def test_t104_profile_email_change_is_not_an_identity_change(profile_client):
    client, db = profile_client
    client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    response=client.patch('/users/91/profile',json={'email':'another@example.test','telegram':'changed'})
    assert response.status_code==409
    assert db.updates==0


def test_t104_anonymous_dialogue_message_never_reaches_agent(profile_client,monkeypatch):
    client,_=profile_client
    def forbidden(**_): raise AssertionError('Unauthenticated request reached profile agent')
    monkeypatch.setattr(routes.interviewer_agent,'reply',forbidden)
    assert client.post('/users/agent/message',json={'session_id':'synthetic-session','message':'synthetic'}).status_code==401


@pytest.mark.parametrize('offset_hours', [0, 3])
def test_history_and_profile_summary_share_datetime_encoding(profile_client, monkeypatch, offset_hours):
    from datetime import timedelta
    client, _ = profile_client
    stamp = datetime(2026, 10, 5, 12, 34, 56, tzinfo=timezone(timedelta(hours=offset_hours)))
    cycle = {'cycle_id':str(uuid4()), 'report_id':str(uuid4()),
             'cycle_created_at':stamp, 'collection_closed_at':stamp,
             'versions':[{'created_at':stamp}]}
    monkeypatch.setattr(routes.m8_results, 'list_owned_cycles', lambda *_: [cycle])
    client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    history = client.get('/users/assessment/m8/history')
    summary = client.get('/users/91/profile-summary')
    assert history.status_code == summary.status_code == 200
    assert history.json()['cycles'] == summary.json()['cycle_history']
