"""Owner-only ASGI draft contract, R1 guards and independent acceptance clear."""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import Api.routes as routes
from Api import assessment_drafts

pytestmark = pytest.mark.e2e

@pytest.fixture
def client(monkeypatch):
    calls = []
    class Connection:
        def execute(self, query, params):
            assert 'FROM m5_assessment_situations' in query
            return SimpleNamespace(fetchone=lambda: {'user_id': 7, 'usage_scope': 'assessment'})
    @contextmanager
    def connection(): yield Connection()
    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
        lambda token: SimpleNamespace(id=7 if token == 'owner' else 8) if token else None)
    def guard(*_args, **_kwargs): calls.append('r1')
    monkeypatch.setattr(routes, '_m7_require_explicit_return', guard)
    for method in ['read', 'save', 'consume']:
        def service(_connection, _method=method, **data):
            calls.append((_method, data)); return {'version': 1, 'text': data.get('text', '')}
        monkeypatch.setattr(assessment_drafts, method, service)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as http: yield http, calls, monkeypatch


def path(): return f'/users/assessment/m5/situations/{uuid4()}/draft'

def body(**extra): return {'slot_id': 'dialogue:q', 'expected_version': 0, 'revision': 'r1', 'text': '  raw\ntext  ', **extra}


def test_owner_only_even_for_an_organization_administrator(client):
    http, calls, _ = client
    assert http.get(path()).status_code == 401
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'administrator')
    assert http.put(path(), json=body()).status_code == 403
    assert calls == []


def test_read_write_and_empty_delete_are_no_store_and_guarded_by_r1(client):
    http, calls, _ = client; http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    for response in [http.get(path()), http.put(path(), json=body()), http.put(path(), json=body(text=''))]:
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert calls[0] == 'r1' and calls[2] == 'r1'
    assert calls[3][1]['text'] == '  raw\ntext  '
    assert calls[3][1]['owner_user_id'] == 7
    assert calls[5][1]['text'] == ''


@pytest.mark.parametrize('changes', [{'text': 'x' * 10001}, {'expected_version': -1}, {'revision': ''}])
def test_invalid_payload_cannot_write(client, changes):
    http, calls, _ = client; http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    assert http.put(path(), json=body(**changes)).status_code == 422
    assert calls == []


def test_r1_get_and_autosave_never_act_as_continue(client):
    http, calls, patch = client; http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    def guard(*_args, **_kwargs): raise ValueError('M7_EXPLICIT_RETURN_REQUIRED')
    patch.setattr(routes, '_m7_require_explicit_return', guard)
    assert http.get(path()).status_code == 409
    assert http.put(path(), json=body()).status_code == 409
    assert calls == []


def test_cas_conflict_safe_code_and_clear_only_after_readback_no_presence(client):
    http, calls, patch = client; http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    def conflict(*_args, **_kwargs): raise ValueError('DRAFT_VERSION_CONFLICT')
    patch.setattr(assessment_drafts, 'save', conflict)
    assert http.put(path(), json=body()).json() == {'detail': 'DRAFT_VERSION_CONFLICT'}
    calls.clear()
    response = http.post(path() + '/accepted', json={'accepted': True, 'slot_id': 'dialogue:q',
        'revision': 'sent', 'request_id': 'original', 'turn_id': str(uuid4())})
    assert response.status_code == 200
    assert calls[0][0] == 'consume' and 'r1' not in calls
