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
        receipt_path = base + '/operations/qa02-mixed-real-db'
        with routes.get_connection() as db:
            before = db.execute('SELECT * FROM organization_invitations ORDER BY id').fetchall()
        read = client.get(receipt_path, params={'assignment_ref': 'competencies_4k', 'email': 'unknown@example.test'})
        assert read.status_code == 200
        saved={v['email']:v for v in read.json()['items']}
        assert {email: (v['operation_id'], v['invitation_id']) for email, v in saved.items()} == {
            email: (payload['operation_id'], item['invitation_id']) for email, item in items.items()}
        assert client.get(receipt_path, params={'assignment_ref': 'new-program', 'email': 'unknown@example.test'}).status_code == 404
        with routes.get_connection() as db:
            assert db.execute('SELECT * FROM organization_invitations ORDER BY id').fetchall() == before
        assert len(sent) == 3
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


@pytest.mark.parametrize("already_revoked", [False, True])
def test_recovery_of_proven_pre_transport_crash(invitation_database, monkeypatch, already_revoked):
    from Api import invitation_outcomes

    _, _, org, app = invitation_database
    base = f"/users/admin/organizations/{org}/personal-invitations"
    email = "person@example.test"
    old = {"emails": [email], "operation_id": "qa02-pre-transport-crash"}
    other = {"emails": ["admin@example.test"], "operation_id": "qa02-neighbor"}
    calls = []

    def transport(**payload):
        calls.append(payload["email"])

    monkeypatch.setattr(routes, "send_auth_action_email", transport)
    with TestClient(app) as client:
        assert client.post(base, json=other).json()["items"][0]["outcome"] == "accepted"

        def crash_before_transport(**payload):
            raise TypeError("send_auth_action_email() got an unexpected keyword argument 'created_at'")

        monkeypatch.setattr(routes, "send_auth_action_email", crash_before_transport)
        with pytest.raises(TypeError, match="unexpected keyword argument"):
            client.post(base, json=old)
        monkeypatch.setattr(routes, "send_auth_action_email", transport)

        receipt = f"{base}/operations/{old['operation_id']}"
        params = {"assignment_ref": "competencies_4k", "email": email}
        unresolved = client.get(receipt, params=params).json()["items"][0]
        assert unresolved["outcome"] == "unknown"
        assert calls == ["admin@example.test"]

        with routes.get_connection() as db:
            if already_revoked:
                db.execute("UPDATE organization_invitations SET revoked_at=NOW() WHERE id=%s",
                           (unresolved["invitation_id"],))
            attempt = db.execute(
                "SELECT * FROM organization_invitations WHERE id=%s",
                (unresolved["invitation_id"],),
            ).fetchone()
            neighbor = db.execute(
                "SELECT * FROM organization_invitations WHERE request_id=%s", (other["operation_id"],),
            ).fetchone()
            recovery_params = (
                invitation_outcomes.encode_reason("error", "failed_unclassified", recipients=[email]),
                attempt["id"], org, attempt["created_by_user_id"], email, old["operation_id"],
                attempt["assignment_ref"], attempt["delivery_started_at"], attempt["delivery_error"],
                attempt["revoked_at"],
            )
            recovery = """
                UPDATE organization_invitations SET delivery_status='error', delivery_error=%s
                WHERE id=%s AND organization_id=%s AND created_by_user_id=%s
                  AND lower(recipient_email)=%s AND request_id=%s AND assignment_ref=%s
                  AND purpose='personal_registration' AND delivery_status='sending'
                  AND delivery_started_at=%s AND delivery_error IS NOT DISTINCT FROM %s
                  AND sent_at IS NULL AND used_at IS NULL AND revoked_at IS NOT DISTINCT FROM %s
                RETURNING id
            """
            assert db.execute(recovery, recovery_params).fetchone() == {"id": attempt["id"]}
            assert db.execute(recovery, recovery_params).fetchone() is None
            db.commit()

        resolved = client.get(receipt, params=params).json()["items"][0]
        assert resolved["outcome"] == "failed"
        assert resolved["invitation_id"] == unresolved["invitation_id"]
        assert resolved["link_status"] == ("revoked" if already_revoked else "active")
        assert client.post(base, json=old).json()["items"][0]["outcome"] == "failed"
        assert calls == ["admin@example.test"]
        retry = {**old, "operation_id": "qa02-explicit-retry"}
        accepted = client.post(base, json=retry).json()["items"][0]
        assert accepted["outcome"] == "accepted"
        assert accepted["invitation_id"] != attempt["id"]
        assert calls == ["admin@example.test", email]
        with routes.get_connection() as db:
            assert db.execute("SELECT * FROM organization_invitations WHERE id=%s",
                              (neighbor["id"],)).fetchone() == neighbor
            recovered = db.execute("SELECT * FROM organization_invitations WHERE id=%s",
                                   (attempt["id"],)).fetchone()
            assert recovered["sent_at"] is None
            assert recovered["delivery_status"] == "error"
            assert recovered["delivery_started_at"] == attempt["delivery_started_at"]
            assert recovered["revoked_at"] is not None
            if already_revoked:
                assert recovered["revoked_at"] == attempt["revoked_at"]
