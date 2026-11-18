from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from Api import routes
from Api.email_service import EmailDeliveryError, EmailDeliveryUncertainError
from Api.org_access import AdminScope
from tests.integration.test_r03_auth_invitation_db import invitation_database

pytestmark=pytest.mark.integration

@pytest.mark.parametrize('superadmin',[False,True])
def test_roles_persist_mixed_facts_and_replay_only_one_effect(invitation_database,monkeypatch,superadmin):
    _,_,org,app=invitation_database
    monkeypatch.setattr(routes,'get_admin_scope',lambda *a:AdminScope(is_superadmin=superadmin,organization_ids=(org,)))
    with routes.get_connection() as db:
        person=db.execute("INSERT INTO users(email) VALUES('unknown@example.test') RETURNING id").fetchone()['id']
        db.execute("INSERT INTO organization_memberships VALUES(%s,%s,'member','admin_add')",(org,person));db.commit()
    sent=[]
    def sink(**payload):
        sent.append(payload['email'])
        if payload['email']=='admin@example.test': raise EmailDeliveryError('RAW secret',reason_code='provider_limit',reason_params={'retry_after_seconds':120,'secret':'bad'})
        if payload['email']=='unknown@example.test': raise EmailDeliveryUncertainError('response lost after dispatch')
    monkeypatch.setattr(routes,'send_auth_action_email',sink)
    emails=[' Person@Example.Test ','person@example.test','admin@example.test','unknown@example.test']
    payload={'emails':emails,'operation_id':'qa02-mixed-real-db'}
    base=f'/users/admin/organizations/{org}/personal-invitations'
    with TestClient(app) as client:
        first=client.post(base,json=payload)
        assert first.status_code==200
        items={v['email']:v for v in first.json()['items']}
        assert [items[e]['outcome'] for e in ['person@example.test','admin@example.test','unknown@example.test']]==['accepted','failed','unknown']
        read=client.get(base+'/operations/qa02-mixed-real-db',params={'assignment_ref':'competencies_4k'})
        saved={v['email']:v for v in read.json()['items']}
        assert saved['admin@example.test']['reason_code']=='provider_limit'
        assert saved['admin@example.test']['reason_params']=={'retry_after_seconds':120}
        assert saved['unknown@example.test']['outcome']=='unknown'
        assert 'RAW' not in read.text and 'secret' not in read.text
        replay=client.post(base,json=payload)
        assert replay.status_code==200
        assert len(sent)==3
        changed=client.post(base,json={'emails':['other@example.test'],'operation_id':payload['operation_id']})
        assert changed.json()['items'][0]['reason_code']=='operation_mismatch'
        assert len(sent)==3
        # Registration/link state cannot rewrite accepted mail outcome.
        with routes.get_connection() as db:
            db.execute('UPDATE organization_invitations SET used_at=NOW() WHERE id=%s',(items['person@example.test']['invitation_id'],));db.commit()
        used=client.get(base+'/operations/qa02-mixed-real-db',params={'assignment_ref':'competencies_4k'}).json()
        accepted=next(v for v in used['items'] if v['email']=='person@example.test')
        assert accepted['link_status']=='used' and accepted['outcome']=='accepted'
        monkeypatch.setattr(routes.web_session_service,'get_user_by_token',lambda *a:SimpleNamespace(id=person,email='unknown@example.test'))
        assert client.get(base+'/operations/qa02-mixed-real-db',params={'assignment_ref':'competencies_4k'}).status_code==404


def test_known_refusal_survives_readiness_change_and_get(invitation_database,monkeypatch):
    _,_,org,app=invitation_database
    def reject(**k):raise EmailDeliveryError('private',reason_code='provider_access')
    monkeypatch.setattr(routes,'send_auth_action_email',reject)
    base=f'/users/admin/organizations/{org}/personal-invitations'
    payload={'emails':['person@example.test'],'operation_id':'qa02-retained-error'}
    with TestClient(app) as client:
        assert client.post(base,json=payload).json()['items'][0]['reason_code']=='provider_access'
        monkeypatch.setattr(routes.questionnaire_sources,'assignment_readiness',lambda *a,**k:{'status':'draft'})
        assert client.post(base,json=payload).json()['items'][0]['reason_code']=='provider_access'
        assert client.get(base+'/operations/qa02-retained-error',params={'assignment_ref':'competencies_4k'}).json()['items'][0]['reason_code']=='provider_access'


def test_concurrent_different_recipient_set_never_adds_a_second_effect(invitation_database,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    _,_,org,app=invitation_database
    entered=threading.Event();release=threading.Event();sent=[]
    def sink(**payload):
        sent.append(payload['email']);entered.set();assert release.wait(5)
    monkeypatch.setattr(routes,'send_auth_action_email',sink)
    def send(email):
        with TestClient(app) as client:
            return client.post(f'/users/admin/organizations/{org}/personal-invitations',json={'emails':[email],'operation_id':'qa02-concurrent-set'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(send,'person@example.test');assert entered.wait(5)
        second=pool.submit(send,'admin@example.test');release.set()
        assert first.result(timeout=5).json()['items'][0]['outcome']=='accepted'
        assert second.result(timeout=5).json()['items'][0]['reason_code']=='operation_mismatch'
    assert sent==['person@example.test']
