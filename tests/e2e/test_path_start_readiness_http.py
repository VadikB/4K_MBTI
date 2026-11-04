"""Owned HTTP boundary and real readiness projection; synthetic SQL/source stubs."""
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import acquaintance, routes
from tests.unit.test_path_start_readiness import Connection

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize('missing', ['position', 'questionnaire'])
def test_owned_acquaintance_keeps_exact_reason_over_http(monkeypatch, missing):
    @contextmanager
    def factory():
        yield Connection()
    monkeypatch.setattr(routes, 'get_connection', factory)
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
        lambda token: SimpleNamespace(id=1) if token == 'synthetic-owner' else None)
    monkeypatch.setattr(acquaintance, 'assignment_readiness', lambda *a, **kw:
        {'status': 'draft', 'reason': 'confirmed_questionnaire', 'missing': ['confirmation']}
        if missing == 'questionnaire' else {
            'status': 'ready', 'assignment_ref': 'specialist-pilot', 'questionnaire_revision_id': 11,
            'briefing': {'participant_question_schema': acquaintance.PARTICIPANT_QUESTION_SCHEMA}})
    monkeypatch.setattr(acquaintance, '_participant_fields', lambda *a, **kw: [
        {'key': key, 'value': None if key == 'position' else 'Synthetic'} for key in ('full_name', 'email', 'position')])
    monkeypatch.setattr(acquaintance, '_onboarding_progress', lambda *a, **kw: {})
    monkeypatch.setattr(acquaintance, '_competency_explanation', lambda *a, **kw: {})
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        assert client.get('/users/1/acquaintance').status_code == 401
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'synthetic-owner')
        assert client.get('/users/2/acquaintance').status_code == 403
        response = client.get('/users/1/acquaintance')
        assert response.status_code == 200
        result = response.json()
        expected = 'participant_fields:position' if missing == 'position' else 'confirmed_questionnaire'
        assert result['readiness']['reason'] == result['late_readiness']['reason'] == expected
        assert 'ещё готовит данные' not in result['readiness']['message']
        assert result['readiness']['title']
        assert result['mandatory_complete'] is False
