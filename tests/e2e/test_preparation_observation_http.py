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
    assert reads==[('safe-operation',99),('safe-operation',99),('foreign-operation',99)]
