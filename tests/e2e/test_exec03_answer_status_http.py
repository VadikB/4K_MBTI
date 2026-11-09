"""ASGI route/auth/query validation for the owner answer-status endpoint."""
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import Api.routes as routes
from Api import assessment_answer_status

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class OwnershipConnection:
    def __init__(self):
        self.row = {'user_id': 7, 'usage_scope': 'assessment'}

    def execute(self, query, _params):
        assert 'FROM m5_assessment_situations' in query
        return Result(self.row)


@pytest.fixture
def client(monkeypatch):
    ownership = OwnershipConnection()
    reads = []

    @contextmanager
    def connection():
        yield ownership

    monkeypatch.setattr(routes, 'get_connection', connection)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                        lambda token: SimpleNamespace(id=7 if token == 'owner' else 8) if token else None)

    def read(_connection, **identity):
        reads.append(identity)
        return {**identity, 'cycle_id': str(uuid4()), 'status': 'accepted',
                'processing_status': 'applied',
                'turn': {'turn_id': identity['turn_id'], 'request_id': identity['request_id'],
                         'speaker_type': 'assessee', 'content_text': 'Принятый ответ'}}

    monkeypatch.setattr(assessment_answer_status, 'read', read)
    # An accepted readback after expiry/close must not invoke new-write guards.
    def guard(*_args, **_kwargs):
        raise AssertionError('Readback invoked write/return admission')
    monkeypatch.setattr(routes, '_m7_require_explicit_return', guard)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as http:
        yield http, ownership, reads, monkeypatch


def url():
    return f'/users/assessment/m5/situations/{uuid4()}/answer-status'


def params(**extra):
    return {'request_id': 'lost-before-response', 'turn_id': str(uuid4()), **extra}


def test_authentication_and_owner_checked_before_any_answer_lookup(client):
    http, ownership, reads, _ = client
    path, query = url(), params()
    assert http.get(path, params=query).status_code == 401
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'other')
    assert http.get(path, params=query).status_code == 403
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    ownership.row = None
    assert http.get(path, params=query).status_code == 404
    assert reads == []


def test_qa_situation_cannot_be_read_through_participant_endpoint(client):
    http, ownership, reads, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    ownership.row['usage_scope'] = 'qa'
    value = http.get(url(), params=params())
    assert value.status_code == 403
    assert value.json() == {'detail': 'QA_AS_NOT_AVAILABLE_IN_PRODUCT_ROUTE'}
    assert reads == []


@pytest.mark.parametrize('query', [
    {'request_id': '', 'turn_id': str(uuid4())},
    {'request_id': '   ', 'turn_id': str(uuid4())},
    {'request_id': 'x' * 201, 'turn_id': str(uuid4())},
    {'request_id': 'valid', 'turn_id': 'not-a-uuid'},
    {'request_id': 'valid', 'turn_id': str(uuid4()), 'clarification_id': 'not-a-uuid'},
    {'request_id': 'valid'},
    {'turn_id': str(uuid4())},
])
def test_invalid_identity_has_422_and_never_reads_status(client, query):
    http, _ownership, reads, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    assert http.get(url(), params=query).status_code == 422
    assert reads == []


def test_closed_accepted_result_is_read_without_resume_or_write_admission(client):
    http, _ownership, reads, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
    path, query = url(), params(clarification_id=str(uuid4()))
    value = http.get(path, params=query)
    assert value.status_code == 200
    assert reads == [{'assessment_situation_id': path.split('/')[-2], **query}]
    assert value.json()['turn']['turn_id'] == query['turn_id']
    assert value.json()['status'] == 'accepted'
    assert 'snapshot' not in value.text
    assert 'mechanism' not in value.text


@pytest.mark.parametrize('code', ['ANSWER_STATUS_IDENTITY_CONFLICT',
                                 'ANSWER_STATUS_CLARIFICATION_NOT_FOUND'])
def test_identity_conflict_is_409_without_history(client, code):
    http, _ownership, _reads, monkeypatch = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')

    def conflict(*_args, **_kwargs):
        raise ValueError(code)

    monkeypatch.setattr(assessment_answer_status, 'read', conflict)
    value = http.get(url(), params=params())
    assert value.status_code == 409
    assert value.json() == {'detail': code}
    assert 'Принятый ответ' not in value.text
