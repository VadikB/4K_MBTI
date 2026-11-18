import pytest
from fastapi import HTTPException
from Api import routes, invitation_outcomes
from Api.email_service import EmailDeliveryError, EmailDeliveryUncertainError
from tests.e2e.test_r03_invitation_http import _InvitationConnection, _Result, _client

pytestmark = pytest.mark.e2e

BASE='/users/admin/organizations/3/personal-invitations'

@pytest.mark.parametrize('condition,expected', [
    ('invalid','invalid_email'), ('unconfirmed','questionnaire_unconfirmed'),
    ('minimum','questionnaire_incomplete'), ('university','organization_unsupported'), ('member','member_unavailable'),
    ('console','mail_not_configured'), ('provider','provider_rejected'), ('unknown_reason','failed_unclassified'),
])
def test_real_handler_refusal_branches_and_get(monkeypatch,condition,expected):
    db=_InvitationConnection(); sent=[]; client=_client(monkeypatch,db,sent)
    email='broken' if condition=='invalid' else 'person@example.test'
    if condition in {'unconfirmed','minimum','university'}:
        monkeypatch.setattr(routes.questionnaire_sources,'assignment_readiness',lambda *a,**k: {'status':'draft','reason':'early_minimum' if condition=='minimum' else 'university_admission_not_supported' if condition=='university' else 'confirmed_questionnaire','missing':['purpose','organizer','PRIVATE_FIELD']})
    if condition=='member': monkeypatch.setattr(routes,'is_platform_protected_account',lambda *a,**k:True)
    if condition=='console': monkeypatch.setattr(routes.settings,'email_provider','console')
    if condition in {'provider','unknown_reason'}:
        def reject(**k):
            if condition=='provider': raise EmailDeliveryError('SECRET_RAW_RESPONSE')
            raise EmailDeliveryError('SECRET_UNKNOWN_FAILURE',reason_code='future_provider_code')
        monkeypatch.setattr(routes,'send_auth_action_email',reject)
    response=client.post(BASE,json={'emails':[email],'operation_id':'qa02-'+condition})
    assert response.status_code==200
    item=response.json()['items'][0]
    assert item['outcome']=='failed' and item['reason_code']==expected
    assert 'SECRET' not in response.text
    if item['invitation_id']:
        get=client.get(BASE+'/operations/qa02-'+condition,params={'assignment_ref':'competencies_4k','email':email})
        assert get.json()['items'][0]['reason_code']==expected
        replay=client.post(BASE,json={'emails':[email],'operation_id':'qa02-'+condition})
        assert replay.json()['items'][0]['reason_code']==expected
    else:
        assert db.rows==[]
        assert client.get(BASE+'/operations/qa02-'+condition,params={'assignment_ref':'competencies_4k'}).status_code==404


def test_exact_normalized_batch_identity_and_no_repeated_effect(monkeypatch):
    db=_InvitationConnection();sent=[];client=_client(monkeypatch,db,sent)
    payload={'emails':[' PERSON@EXAMPLE.TEST ','person@example.test'],'operation_id':'qa02-exact-batch'}
    assert len(client.post(BASE,json=payload).json()['items'])==1
    assert client.post(BASE,json=payload).json()['items'][0]['outcome']=='accepted'
    changed=client.post(BASE,json={**payload,'emails':['other@example.test']})
    assert changed.json()['items'][0]['reason_code']=='operation_mismatch'
    assert len(sent)==1


def test_initial_acl_is_checked_before_configuration_and_effect(monkeypatch):
    db=_InvitationConnection();sent=[];client=_client(monkeypatch,db,sent)
    def denied(*a,**k): raise HTTPException(403,'private access reason')
    monkeypatch.setattr(routes,'_require_organization_admin',denied)
    assert client.post(BASE,json={'emails':['person@example.test'],'operation_id':'qa02-denied'}).status_code==403
    assert not db.rows and not sent


def test_untyped_adapter_failure_after_dispatch_cannot_prove_refusal(monkeypatch):
    db=_InvitationConnection();sent=[];client=_client(monkeypatch,db,sent)
    def broken(**payload):
        sent.append(payload)
        raise ValueError('broken provider JSON after acceptance')
    monkeypatch.setattr(routes,'send_auth_action_email',broken)
    response=client.post(BASE,json={'emails':['person@example.test'],'operation_id':'qa02-broken-adapter'})
    assert response.json()['items'][0]['outcome']=='unknown'
    read=client.get(BASE+'/operations/qa02-broken-adapter',params={'assignment_ref':'competencies_4k'})
    assert read.json()['items'][0]['outcome']=='unknown'
    assert len(sent)==1


@pytest.mark.parametrize('condition,reason', [('changed','organization_changed'),('rights','permission_changed'),('membership','access_changed')])
def test_second_guard_failure_is_saved_before_transport(monkeypatch,condition,reason):
    class Connection(_InvitationConnection):
        member_reads=0
        def execute(self,query,params=()):
            if condition=='membership' and 'FROM organization_memberships om' in query:
                self.member_reads+=1
                if self.member_reads==2:return _Result(one=None)
            return super().execute(query,params)
    db=Connection();sent=[];client=_client(monkeypatch,db,sent)
    calls=[]
    if condition=='changed':
        def ready(*a,**k):
            calls.append(1);return {'status':'ready' if len(calls)==1 else 'draft'}
        monkeypatch.setattr(routes.questionnaire_sources,'assignment_readiness',ready)
    if condition=='rights':
        original=routes._require_organization_admin
        def guard(*a,**k):
            calls.append(1)
            if len(calls)==4:raise HTTPException(403,'private')
            return original(*a,**k)
        monkeypatch.setattr(routes,'_require_organization_admin',guard)
    result=client.post(BASE,json={'emails':['person@example.test'],'operation_id':'qa02-second-'+condition})
    assert result.json()['items'][0]['reason_code']==reason
    assert result.json()['items'][0]['outcome']=='failed' and not sent
    read=client.get(BASE+'/operations/qa02-second-'+condition,params={'assignment_ref':'competencies_4k'})
    assert read.json()['items'][0]['reason_code']==reason


def test_post_transport_change_is_unknown_and_link_is_separate(monkeypatch):
    from datetime import datetime
    db=_InvitationConnection();sent=[];client=_client(monkeypatch,db,sent)
    def sink(**payload):
        sent.append(payload);db.rows[0]['revoked_at']=datetime(2026,11,17)
    monkeypatch.setattr(routes,'send_auth_action_email',sink)
    result=client.post(BASE,json={'emails':['person@example.test'],'operation_id':'qa02-after-transport'})
    assert result.json()['items'][0]['reason_code']=='context_changed'
    read=client.get(BASE+'/operations/qa02-after-transport',params={'assignment_ref':'competencies_4k'}).json()['items'][0]
    assert read['outcome']=='unknown' and read['link_status']=='revoked'
    assert len(sent)==1
