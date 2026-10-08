"""10.4 HTTP + PostgreSQL against a newly bootstrapped, owned 10.2 database."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

pytestmark=pytest.mark.integration


def test_profile_access_on_owned_stand(tmp_path, monkeypatch):
    from scripts.test_stand import environment
    env={**os.environ,'STAND_ADMIN_URL':os.environ.get('STAND_ADMIN_URL') or os.environ.get('TEST_DATABASE_URL','')}
    state_path=tmp_path/'state.json'
    def cli(action):
        result=subprocess.run([sys.executable,'scripts/test_stand.py',action,'--state',str(state_path),'--gateway','1'],
            env=env,capture_output=True,text=True,timeout=150)
        assert result.returncode==0,action+' failed (details kept only in disposable test environment)'
    cli('create')
    try:
        cli('bootstrap');cli('seed')
        state=json.loads(state_path.read_text())
        monkeypatch.setenv('STAND_ADMIN_URL',env['STAND_ADMIN_URL'])
        isolated=environment(state)
        destination=Path(os.getenv('PROFILE_ACCESS_ARTIFACT_DIR',tmp_path))/'matrix.json'
        destination.parent.mkdir(parents=True,exist_ok=True)
        result=subprocess.run([sys.executable,__file__,'--internal',str(destination)],env=isolated,
                              capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stdout+result.stderr
        assert json.loads(destination.read_text())['status']=='PASS'
    finally:cli('destroy')


def internal(destination):
    assert os.environ.get('AGENT4K_ISOLATED_STAND')=='1'
    from scripts.test_stand import owned
    with owned(json.loads(Path(os.environ['STAND_STATE']).read_text())):pass
    from Api import routes
    from Api.database import get_connection,close_connection_pool
    from Api.agent import interviewer_agent
    from Api.web_session_service import web_session_service
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    records=[]
    def snapshot():
        # Only the owned synthetic DB; credentials/values never appear in artifacts.
        with get_connection() as c:
            return {table:c.execute('SELECT to_jsonb(t) AS row FROM '+table+' t ORDER BY id').fetchall()
                for table in ['users','user_role_profiles','user_identities','auth_password_credentials',
                    'organization_memberships','assessment_user_context_versions','assessment_personalized_profiles','m5_cycles','m8_reports']}
    with get_connection() as c:
        people=c.execute('SELECT id,email FROM users ORDER BY id').fetchall()
        owner,same=[p['id'] for p in people]
        org=c.execute('SELECT organization_id FROM organization_memberships WHERE user_id=%s',(owner,)).fetchone()['organization_id']
        otherorg=c.execute("INSERT INTO organizations(code,name) VALUES('t104_other','Synthetic other tenant') RETURNING id").fetchone()['id']
        other=c.execute("INSERT INTO users(full_name,email) VALUES('Synthetic other tenant','tenant@example.test') RETURNING id").fetchone()['id']
        admin=c.execute("INSERT INTO users(full_name,email) VALUES('Synthetic org admin','orgadmin@example.test') RETURNING id").fetchone()['id']
        c.execute("""INSERT INTO organization_memberships(
            organization_id,user_id,role,admission_source,admitted_at
        ) VALUES(%s,%s,'member','admin_add',NOW()),(%s,%s,'admin','admin_add',NOW())""",
            (otherorg,other,org,admin));c.commit()
    tokens={actor:web_session_service.create_session(uid) for actor,uid in [('owner',owner),('same_org',same),('other_tenant',other),('org_admin',admin),('expired',owner)]}
    with get_connection() as c:
        c.execute("UPDATE web_user_sessions SET expires_at=NOW()-INTERVAL '1 minute' WHERE token=%s",(tokens['expired'],));c.commit()
    valid_user=web_session_service.get_user_by_token(tokens['owner'])
    dialogue=interviewer_agent.start(valid_user.email,valid_user)
    def history():
        with get_connection() as c:return c.execute('SELECT history_json FROM agent_conversation_sessions WHERE session_id=%s',(dialogue.session_id,)).fetchone()['history_json']
    app=FastAPI();app.include_router(routes.router)
    with TestClient(app) as http:
        def actor(name):
            http.cookies.clear()
            if name in tokens:http.cookies.set(routes.SESSION_COOKIE_NAME,tokens[name])
            elif name=='forged':http.cookies.set(routes.SESSION_COOKIE_NAME,'synthetic-invalid-token')
        def verify(name,method,url,status,payload=None,unchanged=True):
            actor(name);before=snapshot();before_history=history()
            response=http.request(method,url,json=payload) if payload is not None else http.request(method,url)
            assert response.status_code==status,(name,method,url,response.status_code,status)
            same_state=snapshot()==before and history()==before_history
            if unchanged:assert same_state,(name,method,url,'unexpected write')
            records.append({'actor':name,'method':method,'route':url.replace(str(owner),'{owner}'),
                'expected':status,'actual':response.status_code,'no_profile_identity_membership_history_write':same_state})
            return response
        for who,status in [('anonymous',401),('forged',401),('expired',401),('same_org',403),('other_tenant',403),('org_admin',403)]:
            verify(who,'GET',f'/users/{owner}/profile-summary',status)
            verify(who,'GET',f'/users/{owner}',status)
            verify(who,'PATCH',f'/users/{owner}/profile',status,{'telegram':'@forbidden'})
            verify(who,'POST','/users/agent/message',status,{'session_id':dialogue.session_id,'message':'synthetic message'})
            verify(who,'POST','/users/agent/profile/confirm',status,{'session_id':dialogue.session_id,
                'full_name':'Synthetic','email':valid_user.email,'position':'Synthetic','duties':'Synthetic tasks',
                'role_id':valid_user.role_id,'company_industry':'Synthetic','consent_accepted':True})
        verify('owner','GET',f'/users/{owner}/profile-summary',200)
        before=snapshot()
        verify('owner','PATCH',f'/users/{owner}/profile',200,{'telegram':'@permitted'},unchanged=False)
        after=snapshot()
        for table in before:
            if table!='users':assert before[table]==after[table],table
        expected=before['users'];next(row['row'] for row in expected if row['row']['id']==owner)['telegram']='@permitted'
        assert expected==after['users']
        avatar='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='
        before=snapshot()
        verify('owner','PATCH',f'/users/{owner}/profile',200,{'avatar_data_url':avatar},unchanged=False)
        next(row['row'] for row in before['users'] if row['row']['id']==owner)['avatar_data_url']=avatar
        assert snapshot()==before  # Omitted email and telegram are preserved.
        verify('owner','PATCH',f'/users/{owner}/profile',200,{'email':valid_user.email})
        verify('owner','PATCH',f'/users/{owner}/profile',400,{'avatar_data_url':'invalid'})
        for email in ['orgadmin@example.test','tenant@example.test',None]:
            verify('owner','PATCH',f'/users/{owner}/profile',409,{'email':email,'telegram':'@forbidden'})
        verify('owner','PATCH',f'/users/{owner}/profile',422,{'user_id':same,'telegram':'@forbidden'})
        verify('owner','POST','/users/agent/profile/confirm',409,{'session_id':dialogue.session_id,
                'full_name':'Synthetic','email':'orgadmin@example.test','position':'Synthetic','duties':'Synthetic tasks',
                'role_id':valid_user.role_id,'company_industry':'Synthetic','consent_accepted':True})
        verify('owner','POST','/users/agent/message',403,{'session_id':'missing-or-foreign','message':'synthetic'})
        verify('owner','GET','/users',403)
        listing=verify('org_admin','GET','/users',200).json()
        assert {r['id'] for r in listing}=={owner,same,admin}
        verify('org_admin','GET',f'/users/{other}/profile-summary',403)
        # Real owner confirmation/message work without a fabricated new identity.
        response=verify('owner','POST','/users/agent/profile/confirm',200,{'session_id':dialogue.session_id,
                'full_name':valid_user.full_name,'email':valid_user.email,'position':'Synthetic position',
                'duties':'Synthetic tasks','role_id':valid_user.role_id,'company_industry':'Synthetic',
                'consent_accepted':True},unchanged=False)
        with get_connection() as c:
            assert c.execute('SELECT email FROM users WHERE id=%s',(owner,)).fetchone()['email']==valid_user.email
        verify('owner','POST','/users/agent/message',200,{'session_id':dialogue.session_id,'message':'synthetic finished conversation'},unchanged=False)
        actor('owner');http.post('/users/session/logout')
        verify('owner','GET',f'/users/{owner}/profile-summary',401)
        verify('owner','PATCH',f'/users/{owner}/profile',401,{'telegram':'@forbidden'})
        verify('owner','POST','/users/agent/message',401,{'session_id':dialogue.session_id,'message':'synthetic'})
    destination.write_text(json.dumps({'status':'PASS','boundary':'real FastAPI router, real sessions, owned 10.2 PostgreSQL, new transaction verification','cases':records},ensure_ascii=False,indent=2)+'\n')
    close_connection_pool()


if __name__=='__main__':
    internal(Path(sys.argv[2]))
