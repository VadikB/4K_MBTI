from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from Api import routes

pytestmark = pytest.mark.e2e


@pytest.fixture
def confirmation_client(monkeypatch):
    revision = {"id": 71, "assignment_ref": "synthetic", "status": "confirmed", "channel": "product_form",
                "recipient_mapping_json": ["participant", "organization_admin"],
                "briefing_json": {"authorized_recipients": [{"user_id": 18}]}}
    class Connection:
        committed = False
        def execute(self, _sql, _params=()):
            return SimpleNamespace(fetchone=lambda: revision)
        def commit(self): self.committed = True
        def rollback(self): pass
    connection = Connection()
    @contextmanager
    def get_connection(): yield connection
    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=18))
    def require(_connection, _user, organization_id):
        if organization_id != 3: raise HTTPException(403, "Forbidden")
    monkeypatch.setattr(routes, "_require_organization_admin", require)
    monkeypatch.setattr(routes, "get_admin_scope", lambda *_args: SimpleNamespace(is_superadmin=False))
    monkeypatch.setattr(routes.assessment_programs, "validate_questionnaire_assignment", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes.questionnaire_sources, "confirm", lambda *_args, **_kwargs: revision)
    def failed_readiness(*_args, **_kwargs):
        assert connection.committed
        raise RuntimeError("synthetic readiness failure")
    monkeypatch.setattr(routes.questionnaire_sources, "admin_assignment_readiness", failed_readiness)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app), connection


def test_commit_survives_supplementary_readiness_failure(confirmation_client):
    client, connection = confirmation_client
    response = client.post('/users/admin/organizations/3/questionnaire/71/confirm', json={
        'recipients': ['participant', 'organization_admin'], 'recipient_user_ids': [18],
    })
    assert response.status_code == 200
    assert connection.committed
    assert response.json()['status'] == 'confirmed'
    assert response.json()['readiness_refresh_required'] is True
    assert response.json()['recipient_user_ids'] == [18]


def test_exact_revision_check_reads_effective_recipients_and_checks_scope(confirmation_client):
    client, _ = confirmation_client
    saved = client.get('/users/admin/organizations/3/questionnaire/71')
    assert saved.status_code == 200
    assert saved.json()['id'] == 71
    assert saved.json()['recipient_mapping'] == ['participant', 'organization_admin']
    assert saved.json()['recipient_user_ids'] == [18]
    assert client.get('/users/admin/organizations/4/questionnaire/71').status_code == 403


def test_connected_program_rejects_tampered_questionnaire_preview_and_stale_confirm(
        confirmation_client, monkeypatch):
    client, _ = confirmation_client

    def reject_mismatch(_connection, *, organization_id, assignment_ref):
        assert organization_id == 3
        assert assignment_ref == 'synthetic'
        raise ValueError('PROGRAM_ASSIGNMENT_REF_MISMATCH')

    monkeypatch.setattr(
        routes.assessment_programs, 'validate_questionnaire_assignment', reject_mismatch,
    )
    preview = client.post('/users/admin/organizations/3/questionnaire/preview', json={
        'assignment_ref': 'synthetic', 'source_author': 'Synthetic customer',
        'idempotency_key': 'program01-r02-preview', 'channel': 'product_form',
        'answers': {},
    })
    assert preview.status_code == 400
    assert preview.json()['detail'] == 'PROGRAM_ASSIGNMENT_REF_MISMATCH'

    confirm = client.post('/users/admin/organizations/3/questionnaire/71/confirm', json={
        'recipients': ['participant'],
    })
    assert confirm.status_code == 409
    assert confirm.json()['detail'] == 'PROGRAM_ASSIGNMENT_REF_MISMATCH'
