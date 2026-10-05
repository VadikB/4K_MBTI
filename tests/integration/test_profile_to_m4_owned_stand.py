"""10.5 participant API acceptance on an owned, clean-bootstrap PostgreSQL database."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import pytest

pytestmark = pytest.mark.integration


def test_profile_to_m4_on_owned_stand(tmp_path, monkeypatch):
    from scripts.test_stand import environment
    env = {**os.environ, 'STAND_ADMIN_URL': os.getenv('STAND_ADMIN_URL') or os.getenv('TEST_DATABASE_URL', '')}
    state_path = tmp_path / 'state.json'
    def cli(action):
        result = subprocess.run([sys.executable, 'scripts/test_stand.py', action, '--state', str(state_path), '--gateway', '1'],
            env=env, capture_output=True, text=True, timeout=150)
        assert result.returncode == 0, action + ' failed in disposable test environment'
    cli('create')
    try:
        state = json.loads(state_path.read_text()); state['browser_profile'] = 'unprepared'
        state_path.write_text(json.dumps(state))
        cli('bootstrap'); cli('seed')
        monkeypatch.setenv('STAND_ADMIN_URL', env['STAND_ADMIN_URL'])
        isolated = environment(state)
        if os.getenv('R112_ARTIFACT_DIR'):
            isolated['R112_ARTIFACT_DIR'] = os.environ['R112_ARTIFACT_DIR']
        if os.getenv('H106_ARTIFACT_DIR'):
            isolated['H106_ARTIFACT_DIR'] = os.environ['H106_ARTIFACT_DIR']
        destination = Path(os.getenv('PROFILE_M4_ARTIFACT_DIR', tmp_path)) / 'acceptance.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([sys.executable, __file__, '--internal', str(destination)], env=isolated,
            capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(destination.read_text())['status'] == 'PASS'
    finally:
        cli('destroy')


def internal(destination):
    from scripts.test_stand import owned
    with owned(json.loads(Path(os.environ['STAND_STATE']).read_text())):
        pass
    from Api import routes
    from Api.database import get_connection, close_connection_pool
    from Api.web_session_service import web_session_service
    from Api.agent import interviewer_agent
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    with get_connection() as c:
        owner = c.execute('SELECT id FROM users ORDER BY id LIMIT 1').fetchone()['id']
        assert c.execute('SELECT count(*) AS n FROM assessment_personalized_profiles WHERE user_id=%s', (owner,)).fetchone()['n'] == 0
    token = web_session_service.create_session(owner)
    user = web_session_service.get_user_by_token(token)
    dialogue = interviewer_agent.start(user.email, user)
    app = FastAPI(); app.include_router(routes.router)
    def snapshot():
        with get_connection() as c:
            return {table: c.execute('SELECT to_jsonb(t) AS row FROM '+table+' t ORDER BY id').fetchall()
                for table in ('users', 'user_role_profiles', 'assessment_user_context_versions', 'assessment_personalized_profiles')}
    with TestClient(app, raise_server_exceptions=False) as http:
        http.cookies.set(routes.SESSION_COOKIE_NAME, token)
        options = http.get('/users/assessment/profile/options').json()
        selection = {'role_profile_version_id': next(r['version_id'] for r in options['roles'] if r['name'] == 'Менеджер проекта, продукта или процесса'),
            'organization_context_version_id': options['organization_contexts'][0]['version_id'],
            'assessment_configuration_id': options['configurations'][0]['id']}
        payload = {'session_id': dialogue.session_id, 'full_name': 'Synthetic changed participant', 'email': user.email,
            'position': 'Synthetic changed position', 'duties': 'Synthetic changed duties', 'role_id': user.role_id,
            'company_industry': 'Synthetic', 'consent_accepted': True, 'personalized_profile': selection}
        before = snapshot()
        rejected = http.post('/users/agent/profile/confirm', json={**payload, 'personalized_profile': {**selection, 'role_profile_version_id': 999999}})
        assert rejected.status_code in (400, 409)
        unchanged = snapshot() == before
        assert unchanged, 'Rejected M4 confirmation must not partially commit the participant profile'
        from Api import assessment_contexts as contexts
        with get_connection() as c:
            draft = contexts.create_user_context_draft(c, user_id=owner,
                identity={'full_name':'Synthetic draft'}, professional={})
            with pytest.raises(ValueError, match='confirmed UserContext'):
                contexts.create_personalized_profile(c,user_id=owner,**selection,user_context_version_id=draft)
            c.execute("UPDATE assessment_user_context_versions SET checksum=%s WHERE id=%s",('0'*64,draft))
            contexts.confirm_user_context(c,version_id=draft,user_id=owner)
            with pytest.raises(ValueError, match='checksum mismatch'):
                contexts.create_personalized_profile(c,user_id=owner,**selection,user_context_version_id=draft)
            c.rollback()  # Adversarial draft fixture never becomes the participant's actual input.
        for field in ('assessment_configuration_id','organization_context_version_id'):
            rejected = http.post('/users/agent/profile/confirm',json={**payload,'personalized_profile':{**selection,field:999999}})
            assert rejected.status_code == 400
            assert snapshot() == before
        blank = http.post('/users/agent/profile/confirm',json={**payload,'full_name':' '})
        assert blank.status_code == 422 and snapshot() == before
        from unittest.mock import patch
        from concurrent.futures import ThreadPoolExecutor
        from Api.assessment_authoring_service import assessment_authoring_service
        from Api.m7_completion import complete
        from Api import m10_orchestration
        from Api.m6_worker import run_request as run_evidence
        from Api.m6_assessment_worker import run_request as run_assessment
        from test_m10_product_path_db import EvidenceGateway, AssessmentGateway
        def finish_pipeline(cycle_id):
            for _ in range(40):
                m10_orchestration.advance_once(connection_factory=get_connection)
                with get_connection() as c:
                    status = c.execute('SELECT status FROM m5_cycles WHERE cycle_id=%s',(cycle_id,)).fetchone()['status']
                    evidence = c.execute("SELECT id FROM m6_processing_requests WHERE status='queued' LIMIT 1").fetchone()
                    assessment = c.execute("SELECT id FROM m6_assessment_requests WHERE status='queued' LIMIT 1").fetchone()
                if status == 'calculated': return
                if evidence: run_evidence(evidence['id'],connection_factory=get_connection,gateway=EvidenceGateway())
                if assessment: run_assessment(assessment['id'],connection_factory=get_connection,gateway=AssessmentGateway())
            with get_connection() as c:
                diagnostics = {table: c.execute('SELECT status FROM '+table).fetchall() for table in ('m6_processing_requests','m6_assessment_requests')}
            raise AssertionError('Synthetic pipeline did not finish: '+str(diagnostics))
        def confirmed(body):
            response = http.post('/users/agent/profile/confirm', json=body)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['dashboard']['profile_readiness'] == 'ready'
            return result['dashboard']['personalized_profile_id']
        # Failure after canonical M4 INSERT still rolls back user, consent, history and all M4 writes.
        with patch.object(interviewer_agent, '_persist_session', side_effect=RuntimeError('synthetic interruption')):
            failed = http.post('/users/agent/profile/confirm', json=payload)
        assert failed.status_code == 500
        assert snapshot() == before
        # Concurrent submits and replay after a lost response converge on one immutable snapshot.
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(confirmed, [payload, payload]))
        profile_id = ids[0]
        assert snapshot()['user_role_profiles'] == before['user_role_profiles']
        assert ids[0] == ids[1] == confirmed(payload)
        with get_connection() as c:
            original = c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s', (profile_id,)).fetchone()
            assert original['role_profile_version_id'] == selection['role_profile_version_id']
            assert original['assessment_configuration_id'] == selection['assessment_configuration_id']
            contexts_snapshot = contexts.build_from_confirmed_sources(c, user_id=owner, **selection,
                user_context_version_id=original['user_context_version_id'])
            assert original['checksum'] == contexts_snapshot['checksum']
            assert payload['full_name'] not in json.dumps(original['content_json'])
            foreign_id = c.execute('SELECT id FROM assessment_personalized_profiles WHERE user_id<>%s LIMIT 1',(owner,)).fetchone()['id']
        foreign = http.post('/users/assessment/cycles/start',json={'idempotency_key':'foreign','personalized_profile_id':foreign_id})
        assert foreign.status_code == 409 and 'SCOPE_MISMATCH' in foreign.text
        started = http.post('/users/assessment/cycles/start',json={'idempotency_key':'start','personalized_profile_id':profile_id})
        assert started.status_code == 201, started.text
        cycle_id = started.json()['plan']['cycle_id']
        history = http.get('/users/assessment/m8/history')
        assert history.status_code == 200, history.text
        assert history.json()['assessments_total'] == 1
        assert history.json()['reports_total'] == 0
        assert history.json()['cycles'][0]['status'] == 'collecting'
        as_id = started.json()['runtime']['current_situation']['assessment_situation_id']
        turn = http.post(f'/users/assessment/m5/situations/{as_id}/turns',json={'request_id':'technical-answer','turn_id':str(uuid4()),'content':'Synthetic participant answer'})
        assert turn.status_code == 200, turn.text
        assert started.json()['runtime']['current_situation']
        replay = http.post('/users/assessment/cycles/start',json={'idempotency_key':'lost-start-response','personalized_profile_id':profile_id})
        assert replay.json()['plan']['cycle_id'] == cycle_id
        with get_connection() as c:
            frozen_cycle = c.execute('SELECT profile_ref_json FROM m5_cycles WHERE cycle_id=%s',(cycle_id,)).fetchone()
        # Optional professional fields use the M4 contract, not legacy completeness gates.
        revised = {**payload, 'position':'', 'duties':'', 'company_industry':''}
        new_id = confirmed(revised)
        journey = http.get(f'/users/{owner}/journey-state').json()
        assert journey['profile'] == {'status':'complete','missing_fields':[]}
        assert journey['next_action'] == 'show_dashboard'
        assert http.get('/users/session/restore').json()['user']['personal_data_consent_accepted_at']
        assert new_id != profile_id
        assert confirmed(revised) == new_id
        resumed = http.post('/users/assessment/cycles/start',json={'idempotency_key':'resume','personalized_profile_id':new_id})
        assert resumed.json()['plan']['cycle_id'] == cycle_id
        with get_connection() as c:
            assert c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s',(profile_id,)).fetchone() == original
            assert c.execute('SELECT profile_ref_json FROM m5_cycles WHERE cycle_id=%s',(cycle_id,)).fetchone() == frozen_cycle
            # Finish collection through the existing domain operation; no output material is fabricated.
            complete(c,cycle_id=cycle_id,key='close-fixture',action='complete',reason='synthetic acceptance',initiated_by=owner)
            c.commit()
        assert http.get('/users/assessment/m8/history').json()['cycles'][0]['status'] == 'processing'
        with get_connection() as c:
            db_cycle = c.execute('SELECT id FROM m5_cycles WHERE cycle_id=%s',(cycle_id,)).fetchone()['id']
            m10_orchestration._set_state(c,db_cycle,status='failed',stage='synthetic_failure',error='SYNTHETIC')
            c.commit()
        assert http.get('/users/assessment/m8/history').json()['cycles'][0]['status'] == 'failed'
        with get_connection() as c:
            m10_orchestration._set_state(c,db_cycle,status='processing',stage='synthetic_recovery')
            c.commit()
        finish_pipeline(cycle_id)
        with get_connection() as c:
            historical_reports = c.execute('SELECT to_jsonb(r) AS value FROM m8_reports r ORDER BY id').fetchall()
        final_id = confirmed({**revised, 'position':'Synthetic after completion'})
        with get_connection() as c:
            assert c.execute('SELECT to_jsonb(r) AS value FROM m8_reports r ORDER BY id').fetchall() == historical_reports
            assert c.execute('SELECT profile_ref_json FROM m5_cycles WHERE cycle_id=%s',(cycle_id,)).fetchone() == frozen_cycle
        # R11.2: the real 10.5 confirmation builder feeds saved Results, never the live profile.
        results = http.get(f'/users/assessment/m8/cycles/{cycle_id}/results').json()
        saved_report = http.get(f'/users/assessment/m8/cycles/{cycle_id}/reports/latest').json()
        generation = saved_report['c67']['recommendation_generation']
        assert generation['input']['profile_projection']['user_context']['regular_tasks'] == payload['duties']
        assert generation['input']['context_selection']['selected_path'] == 'user_context.regular_tasks'
        assert results['results']['personalized_profile_snapshot']['content'] == original['content_json']
        regenerated = http.post(f'/users/assessment/m8/cycles/{cycle_id}/reports/regenerate',
            json={'idempotency_key':'task112-historical-context'})
        assert regenerated.status_code == 201, regenerated.text
        assert regenerated.json()['c67']['recommendation_generation']['input'] == generation['input']
        assert http.get(f"/users/assessment/m8/reports/{saved_report['id']}").json() == saved_report
        assert 'Synthetic after completion' not in json.dumps(generation)
        assert payload['full_name'] not in json.dumps(generation)
        assert user.email not in json.dumps(generation)
        if os.getenv('R112_ARTIFACT_DIR'):
            evidence = Path(os.environ['R112_ARTIFACT_DIR']); evidence.mkdir(parents=True, exist_ok=True)
            (evidence/'saved-context.json').write_text(json.dumps({
                'm4_content_excerpt':{'user_context':original['content_json']['user_context'],
                    'role_profile':{'card':{k:v for k,v in original['content_json']['role_profile']['card'].items()
                        if k in generation['input']['profile_projection'].get('role_profile', {})}},
                    'organization_context':{k:v for k,v in original['content_json']['organization_context'].items()
                        if k in generation['input']['profile_projection'].get('organization_context', {})}},
                'projection':generation['input']['profile_projection'],
                'selection':generation['input']['context_selection'], 'recommendations':saved_report['c67']['recommendations'],
                'same_historical_input_after_live_change':True},ensure_ascii=False,indent=2)+'\n')
        new_id = final_id
        next_cycle = http.post('/users/assessment/cycles/start',json={'idempotency_key':'new-cycle','personalized_profile_id':new_id})
        assert next_cycle.status_code == 201, next_cycle.text
        assert next_cycle.json()['plan']['cycle_id'] != cycle_id
        as_id = next_cycle.json()['runtime']['current_situation']['assessment_situation_id']
        turn = http.post(f'/users/assessment/m5/situations/{as_id}/turns',json={'request_id':'technical-answer-next','turn_id':str(uuid4()),'content':'Synthetic participant answer'})
        assert turn.status_code == 200, turn.text
        with get_connection() as c:
            next_id = next_cycle.json()['plan']['cycle_id']
            assert c.execute('SELECT personalized_profile_id FROM m5_cycles WHERE cycle_id=%s',(next_id,)).fetchone()['personalized_profile_id'] == new_id
            complete(c,cycle_id=next_id,key='close-next',action='complete',reason='synthetic acceptance',initiated_by=owner)
            c.commit()
        finish_pipeline(next_id)
        history = http.get('/users/assessment/m8/history').json()
        assert history['assessments_total'] == history['reports_total'] == history['completed_assessments'] == 2
        assert {row['cycle_id'] for row in history['cycles']} == {cycle_id,next_id}
        first = next(row for row in history['cycles'] if row['cycle_id'] == cycle_id)
        assert len(first['versions']) == 2
        summary = http.get(f'/users/{owner}/profile-summary').json()
        assert summary['cycle_history'] == history['cycles']
        assert summary['legacy_assessments_total'] == 0
        assert http.get('/users/session/restore').json()['dashboard']['reports_total'] == 2
        from Api import m8_results
        with get_connection() as c:
            customer = m8_results.create_report(c,results_revision_id=results['revision_id'],audience='customer',
                key='h106-customer',target_profile=None,created_by=owner)
            qa_report = m8_results.create_report(c,results_revision_id=results['revision_id'],audience='methodology_qa',
                key='h106-qa',target_profile=None,created_by=owner)
            with patch.object(m8_results,'generate_recommendations',side_effect=ValueError('synthetic generator failure')):
                base_report = m8_results.create_report(c,results_revision_id=results['revision_id'],audience='assessee',
                    key='h106-failed-recommendations',target_profile=None,created_by=owner)
            c.commit()
        assert base_report['c67']['skills'] and base_report['c67']['recommendation_generation']['status'] == 'failed'
        history = http.get('/users/assessment/m8/history').json()
        assert history['reports_total'] == 2
        first = next(row for row in history['cycles'] if row['cycle_id'] == cycle_id)
        assert first['status'] == 'report_ready' and first['report_id'] == base_report['id']
        assert len(first['versions']) == 3
        for hidden in (customer, qa_report):
            assert hidden['id'] not in json.dumps(history)
            for suffix in ('','/pdf'):
                assert http.get(f"/users/assessment/m8/reports/{hidden['id']}"+suffix).status_code == 403
        def history_fingerprints():
            with get_connection() as c:
                return {table:c.execute('SELECT to_jsonb(t) AS value FROM '+table+' t ORDER BY id').fetchall()
                    for table in ('m6_indicator_assessment_revisions','m8_result_revisions','m8_reports')}
        unchanged = history_fingerprints()
        for _ in range(2):
            assert http.get('/users/assessment/m8/history').json() == history
            for row in history['cycles']:
                for version in row['versions']:
                    report = http.get(f"/users/assessment/m8/reports/{version['report_id']}")
                    assert report.status_code == 200 and report.json()['cycle_id'] == row['cycle_id']
                    assert report.json()['results_revision_id'] == version['results_revision_id']
                    assert http.get(f"/users/assessment/m8/reports/{version['report_id']}/pdf").status_code == 200
        assert history_fingerprints() == unchanged
        with get_connection() as c:
            legacy_id = c.execute("""INSERT INTO user_sessions(user_id,session_code,assessment_code,status)
                VALUES(%s,'synthetic-h106-archive','competencies_4k','completed') RETURNING id""", (owner,)).fetchone()['id']
            c.commit()
        mixed = http.get(f'/users/{owner}/profile-summary').json()
        assert mixed['legacy_assessments_total'] == 1 and mixed['history'][0]['session_id'] == legacy_id
        assert mixed['cycle_history'] == history['cycles']
        assert http.get('/users/session/restore').json()['dashboard']['reports_total'] == 2
        if os.getenv('H106_ARTIFACT_DIR'):
            import hashlib
            evidence = Path(os.environ['H106_ARTIFACT_DIR']); evidence.mkdir(parents=True,exist_ok=True)
            (evidence/'history-receipt.json').write_text(json.dumps({'history':history,
                'legacy_assessments_total':mixed['legacy_assessments_total'],
                'read_fingerprints':{table:{'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()}
                    for table,rows in unchanged.items()},'unchanged_after_get_and_pdf':history_fingerprints()==unchanged},
                ensure_ascii=False,indent=2,default=str)+'\n')
        http.cookies.clear()
        assert http.get('/users/assessment/m8/history').status_code == 401
        assert http.get(f"/users/assessment/m8/reports/{saved_report['id']}").status_code == 401
        with get_connection() as c:
            other = c.execute('SELECT id FROM users WHERE id<>%s ORDER BY id LIMIT 1',(owner,)).fetchone()['id']
        http.cookies.set(routes.SESSION_COOKIE_NAME, web_session_service.create_session(other))
        assert http.get('/users/assessment/m8/history').json()['cycles'] == []
        for suffix in ('','/pdf'):
            assert http.get(f"/users/assessment/m8/reports/{saved_report['id']}"+suffix).status_code == 403
        http.cookies.set(routes.SESSION_COOKIE_NAME, token)
        with get_connection() as c:
            c.execute("UPDATE m5_cycles SET usage_scope='qa' WHERE cycle_id=%s",(cycle_id,));c.commit()
        assert http.get('/users/assessment/m8/history').json()['reports_total'] == 1
        assert http.get(f"/users/assessment/m8/reports/{saved_report['id']}").status_code == 403
        with get_connection() as c:
            c.execute("UPDATE m5_cycles SET usage_scope='assessment' WHERE cycle_id=%s",(cycle_id,));c.commit()
        with get_connection() as c:
            # A second published configuration is an admin input, not an SQL-prepared user M4.
            config = c.execute('SELECT * FROM assessment_configurations WHERE id=%s',(selection['assessment_configuration_id'],)).fetchone()
            cfg2 = assessment_authoring_service.create_configuration(c,code='synthetic_105_second',name='Synthetic second',
                methodology_version_id=config['methodology_version_id'],scenario_version_id=config['scenario_version_id'],actor_user_id=owner,comment='Synthetic 10.5')
            assessment_authoring_service.publish_configuration(c,configuration_id=cfg2['id'],make_default=False,actor_user_id=owner,comment='Synthetic 10.5')
            c.commit()
        second_selection = {**selection,'assessment_configuration_id':cfg2['id']}
        second_config_id = confirmed({**revised,'personalized_profile':second_selection})
        restored = http.get('/users/session/restore',params={'personalized_profile_id':second_config_id}).json()
        assert restored['dashboard']['personalized_profile_id'] == second_config_id
        assert http.get(f'/users/{owner}/journey-state',params={'personalized_profile_id':second_config_id}).json()['next_action'] == 'show_dashboard'
        ambiguous = http.post('/users/assessment/cycles/start',json={'idempotency_key':'ambiguous'})
        assert ambiguous.status_code == 409 and 'SELECTION_REQUIRED' in ambiguous.text
        # Remove only synthetic admission evidence from the owned stand: ready profile, no allowed route.
        with get_connection() as c:
            c.execute('DELETE FROM m5_qa_evidence')
            before_reports = c.execute('SELECT count(*) AS n FROM m8_reports').fetchone()['n']
            before_cycles = c.execute('SELECT count(*) AS n FROM m5_cycles').fetchone()['n']
            c.commit()
        no_route = http.post('/users/assessment/cycles/start',json={'idempotency_key':'no-route','personalized_profile_id':second_config_id})
        assert no_route.status_code == 409 and 'M7_NO_ADMISSIBLE_CASE' in no_route.text, no_route.text
        with get_connection() as c:
            assert c.execute('SELECT count(*) AS n FROM m5_cycles').fetchone()['n'] == before_cycles
            assert c.execute('SELECT count(*) AS n FROM m8_reports').fetchone()['n'] == before_reports
            # Active organization changes cannot select a profile from the old organization.
            org2 = c.execute("INSERT INTO organizations(code,name) VALUES('synthetic_105_other','Synthetic other') RETURNING id").fetchone()['id']
            # The real bootstrap enforces one membership per user; do not weaken that constraint.
            c.execute('UPDATE organization_memberships SET organization_id=%s WHERE user_id=%s',(org2,owner))
            c.commit()
        wrong_org = http.post('/users/assessment/cycles/start',json={'idempotency_key':'wrong-org','personalized_profile_id':new_id})
        assert wrong_org.status_code == 409 and 'SCOPE_MISMATCH' in wrong_org.text
        assert http.get('/users/assessment/m8/history').json()['cycles'] == []
        assert http.get(f'/users/assessment/m8/cycles/{cycle_id}/results').status_code == 403
        for suffix in ('','/pdf'):
            assert http.get(f"/users/assessment/m8/reports/{saved_report['id']}"+suffix).status_code == 403
    destination.write_text(json.dumps({'status':'PASS','zero_M4_before_confirmation':True,
        'unconfirmed_and_bad_checksum_rejected':True,'missing_sources_rejected':True,
        'atomic_rejection':True,'rollback_after_M4_write':True,'concurrent_repeat':True,
        'ready_profile_id':profile_id,'new_profile_id':new_id,'source_checksums':contexts_snapshot['sources'],
        'old_cycle_snapshot_unchanged':True,'optional_professional_fields':True,
        'configuration_ambiguity':True,'foreign_profile_and_organization_rejected':True,
        'no_catalog_no_empty_cycle':True},indent=2)+'\n')
    close_connection_pool()


if __name__ == '__main__':
    internal(Path(sys.argv[2]))
