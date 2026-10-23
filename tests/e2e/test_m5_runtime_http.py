from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import Api.routes as routes

pytestmark = pytest.mark.e2e


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, owner_id=7, scope="assessment"):
        self.owner_id = owner_id
        self.scope = scope

    def execute(self, *args, **_kwargs):
        if args and 'owner_user_id' in args[0]:
            return Result({'owner_user_id':self.owner_id,'usage_scope':self.scope})
        return Result({"user_id": self.owner_id, "usage_scope": self.scope})

    def commit(self):
        pass


@pytest.fixture
def client(monkeypatch):
    connection = Connection()

    @contextmanager
    def get_connection():
        yield connection

    monkeypatch.setattr(routes, "get_connection", get_connection)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token",
                        lambda token: SimpleNamespace(id=7) if token == "owner" else SimpleNamespace(id=8) if token else None)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as value:
        yield value, monkeypatch, connection


def test_product_route_checks_owner_and_admission_gate(client):
    http, monkeypatch, connection = client
    situation_id = str(uuid4())
    monkeypatch.setattr(routes.m5_scenario_runtime, "start",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("AS_NOT_ADMITTED")))
    assert http.post(f"/users/assessment/m5/situations/{situation_id}/start").status_code == 401
    http.cookies.set(routes.SESSION_COOKIE_NAME, "other")
    assert http.post(f"/users/assessment/m5/situations/{situation_id}/start").status_code == 403
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
    response = http.post(f"/users/assessment/m5/situations/{situation_id}/start")
    assert response.status_code == 409
    assert response.json() == {"detail": "AS_NOT_ADMITTED"}
    connection.scope = "qa"
    assert http.post(f"/users/assessment/m5/situations/{situation_id}/start").json() == {
        "detail": "QA_AS_NOT_AVAILABLE_IN_PRODUCT_ROUTE"
    }


def test_cycle_preparation_api_exposes_only_participant_safe_projection(client):
    http, monkeypatch, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
    marker = "CLOSED-CANDIDATE-MARKER"
    internal = {
        "operation_id": "safe-projection-01",
        "user_id": 7,
        "status": "failed",
        "attempts": 3,
        "result_json": {
            "stage": "functional_tester_admission",
            "generated": {
                "candidate_as": {"hidden_facts": marker},
                "tester": {"messages": [marker], "criteria": [marker]},
            },
        },
        "error_code": "ProviderRejected",
        "error_message": f"raw provider failure {marker}",
    }
    monkeypatch.setattr(
        routes.product_cycle_preparation_queue,
        "get_owned_status",
        lambda operation_id, user_id: internal if operation_id == "safe-projection-01" and user_id == 7 else None,
    )
    response = http.get("/users/assessment/cycles/preparation/safe-projection-01")
    assert response.status_code == 200
    assert response.json() == {
        "operation_id": "safe-projection-01",
        "status": "failed",
        "error": {
            "code": "ASSESSMENT_CYCLE_PREPARATION_FAILED",
            "message": "Не удалось подготовить оценочный цикл. Повторите попытку.",
        },
    }
    assert marker not in response.text
    assert "error_message" not in response.text
    assert "result_json" not in response.text

    completed = {
        "operation_id": "safe-projection-02",
        "status": "completed",
        "result_json": {"plan": {"cycle_id": "cycle-01"}, "runtime": {"status": "prepared"}},
    }
    monkeypatch.setattr(routes.product_cycle_preparation_queue, "enqueue", lambda **_kwargs: completed)
    prepared = http.post("/users/assessment/cycles/prepare", json={
        "idempotency_key": "safe-projection-02",
        "selected_skills": ["K1", "K2", "K3", "K4"],
    })
    assert prepared.status_code == 202
    assert prepared.json() == {
        "operation_id": "safe-projection-02",
        "status": "completed",
        "result": completed["result_json"],
    }


def test_cycle_preparation_api_rejects_foreign_or_reused_operation_key(client):
    http, monkeypatch, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")

    monkeypatch.setattr(
        routes.product_cycle_preparation_queue,
        "enqueue",
        lambda **_kwargs: (_ for _ in ()).throw(
            PermissionError("PRODUCT_CYCLE_PREPARATION_OPERATION_NOT_OWNED")
        ),
    )
    foreign = http.post("/users/assessment/cycles/prepare", json={
        "idempotency_key": "known-foreign-key",
        "selected_skills": ["K1"],
    })
    assert foreign.status_code == 403
    assert foreign.json() == {"detail": "Нет доступа к операции подготовки Cycle."}

    monkeypatch.setattr(
        routes.product_cycle_preparation_queue,
        "enqueue",
        lambda **_kwargs: (_ for _ in ()).throw(
            ValueError("PRODUCT_CYCLE_PREPARATION_IDEMPOTENCY_CONFLICT")
        ),
    )
    conflict = http.post("/users/assessment/cycles/prepare", json={
        "idempotency_key": "reused-own-key",
        "selected_skills": ["K2"],
    })
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "Ключ операции уже использован для другого запроса."}


def test_product_turn_and_transition_use_runtime_without_exposing_execution_snapshot(client):
    http, monkeypatch, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
    situation_id = str(uuid4())
    monkeypatch.setattr(routes.m5_scenario_runtime, "submit_turn",
                        lambda *_args, **kwargs: {"turn": {"content_text": kwargs["content"]}, "events": []})
    turn = http.post(f"/users/assessment/m5/situations/{situation_id}/turns", json={
        "request_id": "turn-1", "turn_id": str(uuid4()), "content": "Ответ",
    })
    assert turn.status_code == 200
    assert "execution_payload" not in turn.text
    monkeypatch.setattr(routes.m5_scenario_runtime, "transition",
                        lambda *_args, **kwargs: {"status": kwargs["action"], "idempotent": False})
    transition = http.post(f"/users/assessment/m5/situations/{situation_id}/transitions", json={
        "request_id": "pause-1", "action": "pause", "reason": "Пауза участника",
    })
    assert transition.status_code == 200
    assert transition.json()["status"] == "pause"


def test_admin_c45_and_technical_qa_evidence_use_common_runtime(client):
    http, monkeypatch, _ = client
    http.cookies.set(routes.SESSION_COOKIE_NAME, "owner")
    situation_id = str(uuid4())
    monkeypatch.setattr(routes, "_require_superadmin", lambda _connection, _user: SimpleNamespace(is_superadmin=True))
    monkeypatch.setattr(
        routes.m5_scenario_runtime,
        "build_c45",
        lambda *_args, **kwargs: {
            "assessment_situation_id": situation_id,
            "mode": kwargs["mode"],
            "envelope_json": {"boundary_sequence": 12, "contains_evidence": False},
        },
    )
    c45 = http.post(f"/users/admin/m5-runtime/situations/{situation_id}/c45?mode=interim")
    assert c45.status_code == 200
    assert c45.json()["mode"] == "interim"
    assert c45.json()["envelope_json"]["contains_evidence"] is False

    monkeypatch.setattr(
        routes.m5_storage,
        "record_technical_qa_evidence",
        lambda *_args, **kwargs: {
            "assessment_situation_id": situation_id,
            "evidence_json": {
                "eligibility": "technical_qa",
                "empirical_pilot": "NOT_RUN",
                "trajectory": kwargs["trajectory"],
            },
        },
    )
    evidence = http.post(f"/users/admin/m5-runtime/situations/{situation_id}/qa-evidence", json={
        "trajectory": "content_progress",
        "expected": {"runtime": "trace_saved"},
        "actual": {"events": 12},
        "defects": [],
    })
    assert evidence.status_code == 200
    assert evidence.json()["evidence_json"] == {
        "eligibility": "technical_qa",
        "empirical_pilot": "NOT_RUN",
        "trajectory": "content_progress",
    }


def test_product_m7_completion_routes_enforce_owner_and_keep_processing_distinct(client):
    http,monkeypatch,connection=client;cycle_id=str(uuid4())
    monkeypatch.setattr(routes.m7_completion,'read_status',lambda *_args,**_kwargs:{'collection_status':'collection_closed','processing_status':'processing','remaining_seconds':0})
    monkeypatch.setattr(routes.m7_completion,'complete',lambda *_args,**kwargs:{'action':kwargs['action'],'processing_status':'pending'})
    assert http.get(f'/users/assessment/m7/cycles/{cycle_id}').status_code==401
    http.cookies.set(routes.SESSION_COOKIE_NAME,'other')
    assert http.get(f'/users/assessment/m7/cycles/{cycle_id}').status_code==403
    http.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
    status=http.get(f'/users/assessment/m7/cycles/{cycle_id}')
    assert status.status_code==200 and status.json()['processing_status']=='processing'
    result=http.post(f'/users/assessment/m7/cycles/{cycle_id}/completion',json={
        'action':'complete','reason':'plan_finished','idempotency_key':'finish-1'})
    assert result.status_code==200 and result.json()['processing_status']=='pending'
    connection.scope='qa'
    assert http.get(f'/users/assessment/m7/cycles/{cycle_id}').status_code==403


def test_p01_replacement_http_is_owner_scoped_and_forwards_optimistic_state(client):
    http,monkeypatch,_=client;cycle_id=str(uuid4());old_as=str(uuid4())
    captured={}
    def replace(*_args,**kwargs):
        captured.update(kwargs)
        return {'status':'completed','old_assessment_situation_id':old_as,
                'new_assessment_situation_id':str(uuid4()),'position_no':kwargs['position_no']}
    monkeypatch.setattr(routes.m7_route_replacement,'replace_current',replace)
    payload={'expected_assessment_situation_id':old_as,'expected_state':'active',
        'idempotency_key':'replace-1','reason':'authorized_return',
        'policy_ref':{'id':'P01','version':'2.0','checksum':'a'*64}}
    url=f'/users/assessment/m7/cycles/{cycle_id}/positions/3/replacement'
    assert http.post(url,json=payload).status_code==401
    http.cookies.set(routes.SESSION_COOKIE_NAME,'other')
    assert http.post(url,json=payload).status_code==403
    http.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
    response=http.post(url,json=payload)
    assert response.status_code==201 and response.json()['position_no']==3
    assert captured['requested_by']==7 and captured['expected_assessment_situation_id']==old_as
    assert captured['expected_state']=='active' and captured['key']=='replace-1'


def test_p02_equivalent_candidate_http_runs_controlled_provider(client):
    http,monkeypatch,_=client;cycle_id=str(uuid4());operation_id=str(uuid4());lease=str(uuid4())
    calls=[]
    monkeypatch.setattr(routes.m5_equivalent_generation,'load_variability_package',lambda:{'contract':{}})
    monkeypatch.setattr(routes.m5_equivalent_generation,'begin_generation',
        lambda connection,**kwargs:{'id':operation_id,'status':'pending'})
    monkeypatch.setattr(routes.m5_equivalent_generation,'claim_generation',
        lambda connection,_id:{'id':operation_id,'status':'leased','lease_token':lease,'input_json':{'safe':True}})
    class Provider:
        def generate(self,*,input_snapshot):
            calls.append(input_snapshot);return {'candidate':'ok'}
    monkeypatch.setattr(routes.m5_equivalent_generation,'runtime_provider',Provider())
    monkeypatch.setattr(routes.m5_equivalent_generation,'complete_generation',
        lambda connection,**kwargs:{'status':'completed','operation_id':operation_id,
            'assessment_situation_id':str(uuid4()),'candidate_as_db_id':42})
    http.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
    response=http.post(f'/users/assessment/m7/cycles/{cycle_id}/positions/1/equivalent-candidate',json={
        'expected_assessment_situation_id':str(uuid4()),'idempotency_key':'p02-http-1',
        'provider_config_ref':{'id':'controlled','version':'1','checksum':'a'*64}})
    assert response.status_code==201 and response.json()['candidate_as_db_id']==42
    assert calls==[{'safe':True}]


def test_p03_return_state_is_read_only_and_continue_is_explicit(client):
    http,monkeypatch,_=client;cycle_id=str(uuid4());as_id=str(uuid4());calls=[]
    state={'cycle_id':cycle_id,'position_no':1,'current_assessment_situation_id':as_id,
        'allowed_action':'continue_current','recognized_absence_seconds':179}
    monkeypatch.setattr(routes.m7_return_integration,'read_return_state',
        lambda connection,**kwargs:{**state,'owner_user_id':kwargs['owner_user_id']})
    def proceed(connection,**kwargs):
        calls.append(kwargs);return {'status':'active','branch':'continued_current','assessment_situation_id':as_id}
    monkeypatch.setattr(routes.m7_return_integration,'continue_return',proceed)
    http.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
    loaded=http.get(f'/users/assessment/m7/cycles/{cycle_id}/return-state')
    assert loaded.status_code==200 and loaded.json()['allowed_action']=='continue_current'
    assert calls==[]
    continued=http.post(f'/users/assessment/m7/cycles/{cycle_id}/return-continue',json={
        'position_no':1,'expected_assessment_situation_id':as_id,'expected_state':'active',
        'idempotency_key':'p03-continue-1'})
    assert continued.status_code==200 and continued.json()['branch']=='continued_current'
    assert calls[0]['owner_user_id']==7 and calls[0]['generation_operation_id'] is None


def test_p03_presence_heartbeat_is_owned_and_server_scoped(client):
    http,monkeypatch,_=client;cycle_id=str(uuid4());as_id=str(uuid4());client_id=str(uuid4());calls=[]
    def beat(connection,**kwargs):
        calls.append(kwargs);return {'cycle_id':cycle_id,'assessment_situation_id':as_id,
            'client_id':kwargs['client_id'],'lease_expires_at':'2026-10-16T12:02:00Z'}
    monkeypatch.setattr(routes.m7_return_integration,'heartbeat',beat)
    http.cookies.set(routes.SESSION_COOKIE_NAME,'owner')
    response=http.post(f'/users/assessment/m7/cycles/{cycle_id}/presence',json={
        'client_id':client_id,'expected_assessment_situation_id':as_id})
    assert response.status_code==200 and response.json()['client_id']==client_id
    assert calls==[{'cycle_id':cycle_id,'owner_user_id':7,'client_id':client_id,'expected_as_id':as_id}]
