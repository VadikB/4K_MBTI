from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import Api.routes as routes

pytestmark=pytest.mark.e2e


@pytest.fixture
def client(monkeypatch):
    @contextmanager
    def connection():
        yield SimpleNamespace(commit=lambda:None)
    def authorize(c,user):
        if user is None:raise HTTPException(401)
        if user.id!=7:raise HTTPException(403)
    monkeypatch.setattr(routes,'get_connection',connection)
    monkeypatch.setattr(routes,'_require_superadmin',authorize)
    monkeypatch.setattr(routes.web_session_service,'get_user_by_token',lambda token:SimpleNamespace(id=7 if token=='admin' else 8))
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as client:yield client,monkeypatch


def test_all_m6_endpoints_require_admin(client):
    http,monkeypatch=client
    def forbidden(*a,**k):raise AssertionError('storage accessed before authorization')
    monkeypatch.setattr(routes.m6_repository,'read_request',forbidden)
    monkeypatch.setattr(routes.m6_repository,'read_analysis',forbidden)
    monkeypatch.setattr(routes.m6_repository,'existing_key',forbidden)
    monkeypatch.setattr(routes.m6_assessment_repository,'read_request',forbidden)
    monkeypatch.setattr(routes.m6_assessment_repository,'read_result',forbidden)
    monkeypatch.setattr(routes.m6_assessment_repository,'existing_key',forbidden)
    monkeypatch.setattr(routes.m7_cycle_planner,'read_plan',forbidden)
    monkeypatch.setattr(routes.m7_clarification,'read',forbidden)
    payload={'handoff_id':str(uuid4()),'mechanism_ref':'m6_evidence/1.0.0','idempotency_key':'test','synthetic_material_confirmed':True}
    for token,expected in [(None,401),('member',403)]:
        if token:http.cookies.set(routes.SESSION_COOKIE_NAME,token)
        assert http.post('/users/admin/m6-evidence/requests',json=payload).status_code==expected
        assert http.get('/users/admin/m6-evidence/requests/'+str(uuid4())).status_code==expected
        assert http.get('/users/admin/m6-evidence/analyses/'+str(uuid4())).status_code==expected
        assessment={'evidence_revision_id':str(uuid4()),'mechanism_ref':'m6_indicator_assessment/1.0.0',
            'idempotency_key':'test','synthetic_material_confirmed':True}
        assert http.post('/users/admin/m6-assessments/requests',json=assessment).status_code==expected
        assert http.get('/users/admin/m6-assessments/requests/'+str(uuid4())).status_code==expected
        assert http.get('/users/admin/m6-assessments/results/'+str(uuid4())).status_code==expected
        plan={'personalized_profile_id':7,'selected_skills':['K1','K2','K3','K4'],'idempotency_key':'test','synthetic_material_confirmed':True}
        cycle=str(uuid4());decision=str(uuid4())
        assert http.post('/users/admin/m7-plans',json=plan).status_code==expected
        assert http.get('/users/admin/m7-plans/'+cycle).status_code==expected
        assert http.post('/users/admin/m7-plans/'+cycle+'/next',json={'idempotency_key':'next','expected_plan_revision_id':str(uuid4()),'synthetic_material_confirmed':True}).status_code==expected
        assert http.post('/users/admin/m7-decisions/'+decision+'/present',json={'expected_decision_revision':1}).status_code==expected
        clarification=str(uuid4());c54=str(uuid4())
        assert http.post('/users/admin/m7-clarifications',json={'c54_revision_id':c54,'idempotency_key':'c','synthetic_material_confirmed':True}).status_code==expected
        assert http.get('/users/admin/m7-clarifications/'+clarification).status_code==expected
        assert http.post('/users/admin/m7-clarifications/'+clarification+'/present',json={'expected_c54_revision_id':c54}).status_code==expected
        assert http.post('/users/admin/m7-clarifications/'+clarification+'/answers',json={'request_id':'a','turn_id':str(uuid4()),'content':'answer'}).status_code==expected
        assert http.post('/users/admin/m7-clarifications/'+clarification+'/outcomes',json={'request_id':'o','outcome':'no_answer'}).status_code==expected
        assert http.get('/users/admin/m7-cycles/'+cycle+'/c46').status_code==expected
        assert http.post('/users/admin/m7-cycles/'+cycle+'/blocking-waits',json={'operation_ref':'m6:test','reason':'blocked'}).status_code==expected


def test_repeat_uses_saved_request_without_current_package(client):
    http,monkeypatch=client;http.cookies.set(routes.SESSION_COOKIE_NAME,'admin')
    rid=str(uuid4())
    monkeypatch.setattr(routes.m6_repository,'existing_key',lambda *a:{'id':rid})
    monkeypatch.setattr(routes.m6_repository,'read_request',lambda *a:{'id':rid,'status':'succeeded','analysis_revision_id':'revision'})
    monkeypatch.setattr(routes.m6_worker,'run_request',lambda *a:None)
    def forbidden(*a):raise AssertionError('must not read current package on replay')
    monkeypatch.setattr(routes.m6_package,'load_mechanism',forbidden)
    payload={'handoff_id':str(uuid4()),'mechanism_ref':'m6_evidence/1.0.0','idempotency_key':'test','synthetic_material_confirmed':True}
    r=http.post('/users/admin/m6-evidence/requests',json=payload)
    assert r.status_code==202 and 'trace' not in r.text
    payload['synthetic_material_confirmed']=False
    assert http.post('/users/admin/m6-evidence/requests',json=payload).status_code==422


def test_m6_assessment_repeat_uses_saved_request(client):
    http,monkeypatch=client;http.cookies.set(routes.SESSION_COOKIE_NAME,'admin')
    rid=str(uuid4());revision=str(uuid4())
    monkeypatch.setattr(routes.m6_assessment_repository,'existing_key',lambda *a:{'id':rid})
    monkeypatch.setattr(routes.m6_assessment_repository,'read_request',lambda *a:{'id':rid,'status':'succeeded','assessment_revision_id':revision})
    monkeypatch.setattr(routes.m6_assessment_worker,'run_request',lambda *a:None)
    monkeypatch.setattr(routes.m6_assessment_package,'load_mechanism',lambda *a:(_ for _ in ()).throw(AssertionError('current package read')))
    payload={'evidence_revision_id':str(uuid4()),'mechanism_ref':'m6_indicator_assessment/1.0.0',
        'idempotency_key':'test','synthetic_material_confirmed':True}
    response=http.post('/users/admin/m6-assessments/requests',json=payload)
    assert response.status_code==202 and response.json()['assessment_revision_id']==revision
