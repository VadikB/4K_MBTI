"""Owner status GET only; same safe projection reaches the exact admin assignment."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from Api import routes
from Api.preparation_observation import project

pytestmark=pytest.mark.e2e


def test_status_read_is_owned_read_only_and_matches_admin_projection(monkeypatch):
    now=datetime(2026,11,16,12,tzinfo=timezone.utc)
    operation={'operation_id':'safe-operation','status':'running','user_id':99,'created_at':now-timedelta(minutes=30),
        'error_message':'SQL PROMPT SECRET', 'request_json':{}}
    operation['preparation']=project(operation,{'kind':'assessment','stage':'checking',
        'stage_started_at':now-timedelta(minutes=27),'heartbeat_at':now},now=now)
    reads=[]
    monkeypatch.setattr(routes.web_session_service,'get_user_by_token',lambda token:SimpleNamespace(id=99) if token=='owner' else None)
    def owned(operation_id,user_id):
        reads.append((operation_id,user_id))
        return operation if operation_id=='safe-operation' and user_id==99 else None
    monkeypatch.setattr(routes.product_cycle_preparation_queue,'get_owned_status',owned)
    def command(**_kwargs):
        pytest.fail('Status GET must not enqueue preparation')
    monkeypatch.setattr(routes.product_cycle_preparation_queue,'enqueue',command)
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as client:
        client.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
        one=client.get('/users/assessment/cycles/preparation/safe-operation')
        two=client.get('/users/assessment/cycles/preparation/safe-operation')
        assert one.status_code==two.status_code==200
        assert one.json()==two.json()
        assert 'SQL PROMPT SECRET' not in one.text and 'user_id' not in one.text
        assert client.get('/users/assessment/cycles/preparation/foreign-operation').status_code==404
        client.cookies.clear()
        assert client.get('/users/assessment/cycles/preparation/safe-operation').status_code==401
    admin=routes._project_admin_assessment_stage({'assignment_id':1,'preparation_status':'running',
        'preparation_operation_id':'safe-operation','preparation':operation['preparation']})
    assert admin['preparation']==one.json()['preparation']
    assert admin['preparation']['stage_code'] == 'checking'
    assert project({**operation, 'status': 'failed'}, now=now)['stage_code'] is None
    assert reads==[('safe-operation',99),('safe-operation',99),('foreign-operation',99)]


def test_platform_preparation_endpoints_use_exact_reference_and_reject_other_roles(monkeypatch):
    from contextlib import nullcontext
    from Api import org_access

    reference = 'P4K-1234567890ABCDEF12345678'
    accounts = {
        'platform': SimpleNamespace(id=1, email=routes.ADMIN_EMAIL),
        'org-admin': SimpleNamespace(id=2, email='synthetic-admin@example.invalid'),
        'participant': SimpleNamespace(id=3, email='synthetic-participant@example.invalid'),
        'revoked': SimpleNamespace(id=4, email='synthetic-revoked@example.invalid'),
    }
    reads = []
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token', accounts.get)
    monkeypatch.setattr(routes, 'get_connection', lambda: nullcontext(object()))
    monkeypatch.setattr(org_access, 'configured_superadmin_emails', lambda: {accounts['revoked'].email})
    monkeypatch.setattr(org_access, 'configured_access_suppressed', lambda *args, **kwargs: True)

    def find(_connection, code):
        reads.append(code)
        if code != reference:
            return None
        return {'reference': code, 'assignment_id': 41, 'organization_id': 10,
                'stage_label': 'Проверяем материалы ситуации', 'last_confirmed_at': '2026-11-21T12:00:00Z',
                'failure_class': 'ASSESSMENT_AS_NOT_ADMITTED'}

    def listed(_connection, *, before, organization_id):
        reads.append((before, organization_id))
        return {'items': [], 'next_before': None}

    monkeypatch.setattr(routes.support_preparation, 'read', find)
    monkeypatch.setattr(routes.support_preparation, 'list_failures', listed)
    app = FastAPI()
    app.include_router(routes.router)
    path = '/users/admin/support/preparation'
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        assert client.get(f'{path}/{reference}').status_code == 401
        for role in ('org-admin', 'participant', 'revoked'):
            client.cookies.set(routes.SESSION_COOKIE_NAME, role)
            assert client.get(path).status_code == 403
            assert client.get(f'{path}/{reference}').status_code == 403
        assert reads == []
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'platform')
        listed_response = client.get(path, params={'before': 20, 'organization_id': 10})
        assert listed_response.status_code == 200
        assert listed_response.headers['Cache-Control'] == 'no-store'
        assert client.get(path, params={'before': 2**63}).status_code == 422
        assert client.get(f'{path}/wrong-format').status_code == 404
        absent = 'P4K-' + '0' * 24
        assert client.get(f'{path}/{absent}').status_code == 404
        for _ in range(2):
            response = client.get(f'{path}/{reference}')
            assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
            body = response.json()
            assert body['reference'] == reference and body['assignment_id'] == 41
            assert f'Номер подготовки: {reference}' in body['handoff_text']
            assert 'Поколение назначения: #41' in body['handoff_text']
            assert '/?screen=admin-organizations&org=10' in body['handoff_text']
            assert body['environment'] == {'mode': routes.settings.app_origin_mode,
                'origin': routes.settings.public_app_origin, 'version': routes.get_app_version()}
        assert client.post(f'{path}/{reference}').status_code == 405
    assert reads == [(20, 10), absent, reference, reference]
