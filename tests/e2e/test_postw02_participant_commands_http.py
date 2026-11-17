"""Public commands reach the real runtime guard; no database/provider calls."""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Api import routes
from Api.m5_case_runtime import checksum

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, row): self.row = row
    def fetchone(self): return deepcopy(self.row)


class ReadOnlyConnection:
    def __init__(self):
        self.command = None
        self.event = None
        self.commits = 0
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append(sql)
        assert sql.lstrip().startswith('SELECT'), 'rejected/replayed commands must not write'
        if 'm7_completion_commands' in sql: return Result(self.command)
        if 'm5_scenario_events' in sql: return Result(self.event)
        if 'owner_user_id,usage_scope' in sql:
            return Result({'owner_user_id': 7, 'usage_scope': 'assessment'})
        if 'p.user_id, s.usage_scope' in sql:
            return Result({'user_id': 7, 'usage_scope': 'assessment'})
        raise AssertionError(sql)

    def commit(self): self.commits += 1


@pytest.fixture
def public_client(monkeypatch):
    c = ReadOnlyConnection()
    cycle_id, as_id = str(uuid4()), str(uuid4())
    # The persisted state includes material that no rejected command may change.
    cycle = {'id': 1, 'cycle_id': cycle_id, 'status': 'active', 'owner_user_id': 7}
    situation = {'id': 3, 'assessment_situation_id': as_id, 'cycle_db_id': 1,
                 'session_db_id': 2, 'status': 'active', 'materials': ['frozen'], 'evidence': []}
    monkeypatch.setattr(routes.m7_completion, '_cycle', lambda *a, **k: deepcopy(cycle))
    monkeypatch.setattr(routes.m5_scenario_runtime, '_as_row', lambda *a, **k: deepcopy(situation))
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                        lambda token: SimpleNamespace(id=7 if token=='owner' else 8))
    @contextmanager
    def connect(): yield c
    monkeypatch.setattr(routes, 'get_connection', connect)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        yield http, c, cycle_id, as_id, cycle, situation


def command_request(cycle_id, as_id, endpoint, reason):
    action = 'interrupt_for_continuation' if endpoint=='completion' else 'pause'
    if endpoint=='transitions':
        return f'/users/assessment/m5/situations/{as_id}/transitions', {
            'action': action, 'reason': reason, 'request_id': 'old-or-new-key'}
    return f'/users/assessment/m7/cycles/{cycle_id}/{endpoint}', {
        'action': action, 'reason': reason, 'idempotency_key': 'old-or-new-key'}


@pytest.mark.parametrize('endpoint', ['control', 'completion', 'transitions'])
@pytest.mark.parametrize('reason', ['user_pause', 'between_situations'])
def test_new_public_manual_commands_are_rejected_without_writes(public_client, endpoint, reason):
    http, c, cycle_id, as_id, cycle, situation = public_client
    url, payload = command_request(cycle_id, as_id, endpoint, reason)
    before = deepcopy((cycle, situation))
    assert http.post(url, json=payload).status_code == 401
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'other')
    assert http.post(url, json=payload).status_code == 403
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    result = http.post(url, json=payload)
    assert result.status_code == 409
    assert result.json() == {'detail': 'M7_PARTICIPANT_MANUAL_CONTROL_NOT_ALLOWED'}
    assert (cycle, situation) == before
    assert c.commits == 0
    assert not any('m7_return_' in sql for sql in c.statements)


@pytest.mark.parametrize('endpoint', ['control', 'completion', 'transitions'])
def test_successful_old_commands_replay_before_new_prohibition(public_client, endpoint):
    http, c, cycle_id, as_id, cycle, situation = public_client
    url, payload = command_request(cycle_id, as_id, endpoint, 'old_reason')
    cycle['status'] = 'collection_closed'
    situation['status'] = 'closed'
    saved = {'action': payload['action'], 'cycle_id': cycle_id, 'saved_result': 'unchanged'}
    if endpoint=='transitions':
        c.event = {'event_type': 'interaction_paused', 'cause_json': {'reason': 'old_reason'},
                   'payload_json': {'status': 'paused'}}
        expected = {'status': 'paused', 'event': c.event, 'idempotent': True}
    else:
        c.command = {'request_checksum': checksum({'action': payload['action'], 'reason': 'old_reason'}),
                     'result_json': saved}
        expected = saved
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    for _ in range(2):
        result = http.post(url, json=payload)
        assert result.status_code == 200
        assert result.json() == expected
    conflict = http.post(url, json={**payload, 'reason': 'different'})
    assert conflict.status_code == 409
    assert conflict.json() == {'detail': 'IDEMPOTENCY_CONFLICT'}
    # Reusing the AS key for another action is a conflict too.
    if endpoint=='transitions':
        assert http.post(url, json={**payload, 'action': 'resume'}).json() == {'detail': 'IDEMPOTENCY_CONFLICT'}


def test_legacy_pause_cannot_address_a_cycle_uuid(public_client, monkeypatch):
    http, c, cycle_id, *_ = public_client
    original_execute = c.execute
    def execute(sql, params=None):
        if 'FROM user_sessions WHERE session_code' in sql:
            assert params == (cycle_id,)
            return Result(None)
        return original_execute(sql, params)
    c.execute = execute
    def forbidden(*a, **k): raise AssertionError('legacy service must not receive a Cycle')
    monkeypatch.setattr(routes.assessment_service, 'pause_assessment_dialogue', forbidden)
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    response = http.post('/users/assessment/pause', json={'session_code': cycle_id})
    assert response.status_code == 404
    assert c.commits == 0
