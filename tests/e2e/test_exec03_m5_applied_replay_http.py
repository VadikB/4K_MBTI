"""Concrete ASGI tests for ordinary M5 applied replay and owner-first guard order.

Real route + real new receipt reader. Only persistence/AS snapshot lookup are
synthetic boundaries; no provider, queue, running service, or database is used.
"""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

import Api.routes as routes
from Api import m5_scenario_runtime as runtime
from Api.m5_case_runtime import checksum

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, *, operation, request_id):
        self.owner = {'user_id': 7, 'usage_scope': 'assessment'}
        self.operation = operation
        self.request_id = request_id
        self.status_lookups = 0
        self.commits = 0

    def execute(self, sql, params=()):
        query = ' '.join(sql.split())
        assert query.startswith('SELECT '), query
        if 'FROM m5_assessment_situations s' in query:
            return Result(self.owner)
        assert 'FROM m5_turn_operations' in query
        assert 'FOR UPDATE' not in query
        self.status_lookups += 1
        return Result(self.operation if params == (31, self.request_id) else None)

    def commit(self):
        self.commits += 1


@pytest.fixture
def client(monkeypatch):
    aid, tid = str(uuid4()), str(uuid4())
    payload = {'request_id': 'lost-response', 'turn_id': tid, 'content': 'Принятый ответ'}
    cached = {'assessment_situation_id': aid, 'turn': {'turn_id': tid,
              'content_text': payload['content'], 'speaker_type': 'assessee'},
              'events': [{'event_id': str(uuid4()), 'sequence_no': 5}], 'revision': 9}
    operation = {'turn_id': UUID(tid), 'request_checksum': checksum({
                 'turn_id': tid, 'content': payload['content']}),
                 'status': 'applied', 'result_json': cached}
    c = Connection(operation=operation, request_id=payload['request_id'])
    calls = {'locks': 0, 'guard': 0, 'submit': 0}

    @contextmanager
    def connection():
        yield c

    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                        lambda token: SimpleNamespace(id=7 if token == 'owner' else 8) if token else None)

    def source(_connection, actual_id, *, lock=False):
        assert actual_id == aid
        assert lock is True
        calls['locks'] += 1
        return {'id': 31, 'cycle_db_id': 41, 'session_db_id': 51, 'status': 'closed'}

    monkeypatch.setattr(runtime, '_as_row', source)

    def guard(*_args, **_kwargs):
        calls['guard'] += 1
        raise ValueError('M7_COLLECTION_CLOSED')

    def submit(**_kwargs):
        calls['submit'] += 1
        raise AssertionError('Cached replay attempted new provider processing')

    monkeypatch.setattr(routes, '_m7_require_explicit_return', guard)
    monkeypatch.setattr(runtime, 'submit_turn_detached', submit)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        yield http, c, calls, payload, cached, aid, monkeypatch


def path(aid):
    return f'/users/assessment/m5/situations/{aid}/turns'


def test_applied_owned_post_returns_exact_receipt_before_guard_or_provider(client):
    http, c, calls, payload, cached, aid, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    before = deepcopy(cached)
    response = http.post(path(aid), json=payload)
    assert response.status_code == 200
    assert response.json() == {**before, 'idempotent': True}
    assert cached == before
    assert calls == {'locks': 1, 'guard': 0, 'submit': 0}
    assert c.status_lookups == 1
    assert c.commits == 1


@pytest.mark.parametrize('cookie,owner,code', [
    (None, {'user_id': 7, 'usage_scope': 'assessment'}, 401),
    ('other', {'user_id': 7, 'usage_scope': 'assessment'}, 403),
    ('owner', None, 404),
    ('owner', {'user_id': 7, 'usage_scope': 'qa'}, 403),
])
def test_ordinary_cached_receipt_remains_behind_auth_owner_and_scope(client, cookie, owner, code):
    http, c, calls, payload, _cached, aid, _ = client
    if cookie:
        http.cookies.set(routes.SESSION_COOKIE_NAME, cookie)
    c.owner = owner
    response = http.post(path(aid), json=payload)
    assert response.status_code == code
    assert c.status_lookups == 0
    assert calls == {'locks': 0, 'guard': 0, 'submit': 0}


@pytest.mark.parametrize('change', [
    {'content': 'Изменённый ответ'},
    {'turn_id': str(uuid4())},
])
def test_post_changed_payload_conflicts_before_terminal_guard(client, change):
    http, c, calls, payload, _cached, aid, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    response = http.post(path(aid), json={**payload, **change})
    assert response.status_code == 409
    assert response.json() == {'detail': 'M5_IDEMPOTENCY_PAYLOAD_MISMATCH'}
    assert calls == {'locks': 1, 'guard': 0, 'submit': 0}
    assert c.commits == 0


@pytest.mark.parametrize('processing', [None, 'pending', 'failed', 'rejected_late'])
@pytest.mark.parametrize('guard_code', ['M7_COLLECTION_CLOSED', 'M7_RETURN_EXPLICIT_CONTINUE_REQUIRED',
                                      'M7_BLOCKING_SYSTEM_WAIT'])
def test_new_or_nonapplied_post_still_hits_current_write_guards(client, processing, guard_code):
    http, c, calls, payload, _cached, aid, monkeypatch = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    if processing is None:
        c.operation = None
    else:
        c.operation['status'] = processing

    def guard(*_args, **_kwargs):
        calls['guard'] += 1
        if guard_code == 'M7_RETURN_EXPLICIT_CONTINUE_REQUIRED':
            raise HTTPException(status_code=409, detail=guard_code)
        raise ValueError(guard_code)

    monkeypatch.setattr(routes, '_m7_require_explicit_return', guard)
    response = http.post(path(aid), json=payload)
    assert response.status_code == 409
    assert response.json() == {'detail': guard_code}
    assert calls == {'locks': 1, 'guard': 1, 'submit': 0}
    assert c.commits == 0


def test_new_request_id_is_not_deduplicated_by_same_content(client):
    http, c, calls, payload, _cached, aid, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    response = http.post(path(aid), json={**payload, 'request_id': 'intentional-new-request'})
    assert response.status_code == 409
    assert response.json() == {'detail': 'M7_COLLECTION_CLOSED'}
    assert calls == {'locks': 1, 'guard': 1, 'submit': 0}
