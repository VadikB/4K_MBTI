"""REMAIN_04 actual SQL + owned HTTP; display-only downstream projections stubbed.
No AS, Cycle, provider or mail. Synthetic sources, not methodological approval.
"""
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
import pytest

from Api import acquaintance, assessment_contexts as contexts, routes, org_access
from Api import assessment_assignment_sources as sources
from Api.assessment_role_profiles import publish_base_roles
from Api.database import ensure_role_profile_schema, ensure_assessment_context_schema, ensure_acquaintance_confirmation_schema
from Api.questionnaire_sources import assignment_readiness, PARTICIPANT_QUESTION_SCHEMA

pytestmark = pytest.mark.integration


@pytest.fixture
def stand(test_database_url, monkeypatch):
    schema = 'remain04_pytest_' + uuid4().hex
    with psycopg.connect(test_database_url) as c:
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))

    @contextmanager
    def factory():
        with psycopg.connect(test_database_url, row_factory=dict_row) as c:
            c.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
            c.commit()
            yield c

    try:
        with factory() as c:
            c.execute('CREATE TABLE users(id BIGINT PRIMARY KEY,full_name TEXT,email TEXT,job_description TEXT,active_profile_id BIGINT)')
            c.execute("INSERT INTO users VALUES(1,'Иван Синтетический','p@example.test',NULL,NULL),(2,'Петр Синтетический','b@example.test',NULL,NULL),(3,'Админ Синтетический','admin@example.test',NULL,NULL),(4,'Второй Синтетический','second@example.test',NULL,NULL)")
            c.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,name TEXT,is_active BOOLEAN)')
            c.execute("INSERT INTO organizations VALUES(10,'Org A',TRUE),(20,'Org B',TRUE)")
            c.execute('CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT,UNIQUE(organization_id,user_id))')
            c.execute("INSERT INTO organization_memberships VALUES(10,1,'member'),(20,2,'member'),(10,3,'admin'),(10,4,'member')")
            c.execute('CREATE TABLE assessment_methodologies(id BIGINT PRIMARY KEY)')
            c.execute('INSERT INTO assessment_methodologies VALUES(1)')
            c.execute('CREATE TABLE assessment_methodology_versions(id BIGINT PRIMARY KEY,methodology_id BIGINT,status TEXT,definition_json JSONB)')
            c.execute('''INSERT INTO assessment_methodology_versions VALUES(1,1,'published','{"methodology_version":"1.1"}')''')
            c.execute('CREATE TABLE assessment_configurations(id BIGINT PRIMARY KEY,methodology_version_id BIGINT,status TEXT,code TEXT,name TEXT)')
            c.execute("INSERT INTO assessment_configurations VALUES(1,1,'published','one','One'),(2,1,'published','two','Two')")
            c.execute('CREATE TABLE user_sessions(id BIGINT PRIMARY KEY,user_id BIGINT,execution_snapshot_json JSONB,execution_checksum TEXT)')
            c.execute('CREATE TABLE assessment_preparation_jobs(id BIGINT PRIMARY KEY)')
            ensure_role_profile_schema(c)
            ensure_assessment_context_schema(c)
            ensure_acquaintance_confirmation_schema(c)
            root = Path('assessment_definitions/role_profiles/competencies_4k/1.1')
            roles = publish_base_roles(c, package=json.loads((root/'base_roles.json').read_text()),
                manifest=json.loads((root/'manifest.json').read_text()),published_by_user_id=3,decision_basis='synthetic isolated REMAIN04')
            role = roles['version_ids'][0]
            definition = dict(name='Synthetic',organization_type='компания',industry='образование',
                activity_description='Программы',case_reality_level='обобщённый',organization_name_usage_rules='не использовать')
            versions = []
            for org in (10,10,20):
                v = contexts.create_organization_context_draft(c,organization_id=org,definition=definition)
                contexts.publish_organization_context(c,version_id=v,confirmed_by_user_id=3)
                versions.append(v)
            c.execute('''CREATE TABLE organization_assessment_assignments(id BIGINT PRIMARY KEY,organization_id BIGINT,
                recipient_user_id BIGINT,assignment_ref TEXT,status TEXT,revoked_at TIMESTAMP)''')
            c.execute("INSERT INTO organization_assessment_assignments VALUES(11,10,1,'A','active',NULL),(12,20,2,'B','active',NULL),(14,10,4,'A','active',NULL)")
            c.execute('''CREATE TABLE organization_invitations(organization_id BIGINT,recipient_email TEXT,purpose TEXT,
                assignment_ref TEXT,revoked_at TIMESTAMP,created_by_user_id BIGINT)''')
            c.execute('''CREATE TABLE questionnaire_response_revisions(id BIGINT PRIMARY KEY,organization_id BIGINT,
                assignment_ref TEXT,status TEXT,briefing_json JSONB,organization_context_version_id BIGINT,confirmed_at TIMESTAMP)''')
            for rev,org,ref,version in ((41,10,'A',versions[0]),(42,10,'A',versions[1]),(43,20,'B',versions[2])):
                briefing = dict(purpose=f'Purpose {rev}',organizer=f'Organizer {rev}',results_usage=f'Usage {rev}',
                    participant_questions=[q['text'] for q in PARTICIPANT_QUESTION_SCHEMA['questions']],
                    participant_question_schema=PARTICIPANT_QUESTION_SCHEMA,consent_version=1,consent_text='Synthetic consent',
                    responsible_contact='historical@invalid.test',result_recipients='historical recipient')
                c.execute("INSERT INTO questionnaire_response_revisions VALUES(%s,%s,%s,'confirmed',%s::jsonb,%s,NOW())",(rev,org,ref,json.dumps(briefing),version))
            c.execute('''CREATE TABLE organization_assessment_source_bindings(id BIGINT PRIMARY KEY,assignment_id BIGINT,
                questionnaire_revision_id BIGINT,assessment_configuration_id BIGINT,role_profile_version_id BIGINT)''')
            c.execute('INSERT INTO organization_assessment_source_bindings VALUES(1,11,41,1,%s),(2,12,43,1,%s),(4,14,42,1,%s)',(role,role,role))
            c.execute('''CREATE TABLE participant_acquaintance_states(user_id BIGINT PRIMARY KEY,organization_id BIGINT,
                organization_context_version_id BIGINT,assignment_ref TEXT,questionnaire_revision_id BIGINT,status TEXT,current_step INTEGER,
                answers_json JSONB,answers_confirmed_at TIMESTAMP,briefing_checksum TEXT,consent_version INTEGER,
                consent_accepted_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW(),updated_at TIMESTAMP DEFAULT NOW())''')
        monkeypatch.setattr(routes, 'get_connection', factory)
        monkeypatch.setattr(routes.web_session_service, 'get_user_by_token', lambda token: SimpleNamespace(id=1,email='p@example.test') if token=='synthetic-owner' else None)
        monkeypatch.setattr(org_access, 'is_platform_protected_account', lambda *a, **k: False)
        monkeypatch.setattr(org_access, 'assign_user_organization_from_email', lambda *a, **k: None)
        # Unrelated read-only display consumers need runtime tables outside this boundary.
        monkeypatch.setattr(acquaintance, '_competency_explanation',lambda *a,**k: {})
        monkeypatch.setattr(acquaintance, '_onboarding_progress',lambda *a,**k: {})
        monkeypatch.setattr(acquaintance, 'resolve_display_timing',lambda *a,**k: {})
        monkeypatch.setattr(acquaintance, '_prepared_plan_snapshot',lambda *a,**k: None)
        app=FastAPI();app.include_router(routes.router)
        with TestClient(app,raise_server_exceptions=False) as http:
            http.cookies.set(routes.SESSION_COOKIE_NAME,'synthetic-owner')
            yield factory,http
    finally:
        with psycopg.connect(test_database_url) as c:
            c.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def test_exact_briefing_optional_profile_rollback_replay_and_next_snapshot(stand,monkeypatch):
    factory,http=stand
    assert http.get('/users/2/acquaintance').status_code==403
    assert http.put('/users/2/acquaintance/answers',json={'answers':{'answer_1':'foreign'},'confirm':False}).status_code==403
    assert http.post('/users/admin/organizations/10/questionnaire/41/confirm',json={}).status_code==403
    with factory() as c:
        a=acquaintance.early_readiness(c,user_id=1)
        b=acquaintance.early_readiness(c,user_id=2)
        second=acquaintance.early_readiness(c,user_id=4)
        assert (a['questionnaire_revision_id'],b['questionnaire_revision_id'])==(41,43)
        assert second['questionnaire_revision_id']==42
        assert second['briefing']['purpose']=='Purpose 42'
        assert assignment_readiness(c,organization_id=10,assignment_ref='A')['questionnaire_revision_id']==42
        assert acquaintance.early_readiness(c,user_id=3)['status']=='waiting_for_assignment'
        assert a['briefing']['purpose']=='Purpose 41'
        assert 'responsible_contact' not in a['briefing']
        assert 'historical' not in json.dumps(a['briefing'])
        assert a['briefing']['provided_participant_fields'][2]['value'] is None
    for _ in range(2):
        assert http.get('/users/1/acquaintance').json()['readiness']['questionnaire_revision_id']==41
    assert http.post('/users/1/acquaintance/resolve-profile').status_code==409
    assert http.post('/users/1/acquaintance/consent',json={'version':1}).status_code==200
    answers={f'answer_{i}':f'  Synthetic work {i}  ' for i in (1,2,3)}
    for key,value in answers.items():
        assert http.put('/users/1/acquaintance/answers',json={'answers':{key:value},'confirm':False}).status_code==200
    assert http.get('/users/1/acquaintance').json()['mandatory_complete'] is False
    assert http.put('/users/1/acquaintance/answers',json={'answers':answers,'confirm':True}).status_code==200
    real=contexts.create_personalized_profile
    def fail_after_insert(*a,**k):
        real(*a,**k)
        raise ValueError('synthetic injected rollback')
    monkeypatch.setattr(contexts,'create_personalized_profile',fail_after_insert)
    assert http.post('/users/1/acquaintance/resolve-profile').status_code==409
    with factory() as c:
        assert c.execute('SELECT count(*) n FROM assessment_personalized_profiles').fetchone()['n']==0
        assert c.execute('SELECT count(*) n FROM assessment_user_context_versions').fetchone()['n']==0
    monkeypatch.setattr(contexts,'create_personalized_profile',real)
    result=http.post('/users/1/acquaintance/resolve-profile')
    assert result.status_code==200,result.text
    pid=result.json()['late_readiness']['personalized_profile_id']
    for _ in range(2):
        assert http.post('/users/1/acquaintance/resolve-profile').json()['late_readiness']['personalized_profile_id']==pid
    with factory() as c:
        old=c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s',(pid,)).fetchone()
        assert c.execute('SELECT count(*) n FROM assessment_personalized_profiles').fetchone()['n']==1
        assert 'Иван' not in json.dumps(old['content_json']) and 'p@example.test' not in json.dumps(old['content_json'])
        user=c.execute('SELECT * FROM assessment_user_context_versions WHERE id=%s',(old['user_context_version_id'],)).fetchone()
        items=user['professional_context_json']['acquaintance_answers']['items']
        assert items[0]['raw_answer']==items[0]['normalized']==answers['answer_1']
        assert old['content_json']['user_context']['position_or_status']==''
        other_context=c.execute('SELECT organization_context_version_id FROM questionnaire_response_revisions WHERE id=42').fetchone()['organization_context_version_id']
        wrong=contexts.create_personalized_profile(c,user_id=1,assessment_configuration_id=1,
            organization_context_version_id=other_context,
            role_profile_version_id=old['role_profile_version_id'],user_context_version_id=old['user_context_version_id'])
        c.execute('UPDATE participant_acquaintance_confirmations SET personalized_profile_id=%s WHERE user_id=1',(wrong['id'],))
        assert acquaintance.late_readiness(c,user_id=1)['reason']=='W02_PROFILE_ASSIGNMENT_SCOPE_MISMATCH'
        c.execute('UPDATE participant_acquaintance_confirmations SET personalized_profile_id=%s WHERE user_id=1',(pid,))
        c.execute("UPDATE organization_assessment_assignments SET status='revoked' WHERE id=11")
        c.execute("INSERT INTO organization_assessment_assignments VALUES(13,10,1,'Next','active',NULL)")
        c.execute("INSERT INTO questionnaire_response_revisions SELECT 44,10,'Next',status,briefing_json,organization_context_version_id,NOW() FROM questionnaire_response_revisions WHERE id=42")
        c.execute('INSERT INTO organization_assessment_source_bindings SELECT 3,13,44,assessment_configuration_id,role_profile_version_id FROM organization_assessment_source_bindings WHERE id=1')
        c.execute("UPDATE users SET job_description='Optional position' WHERE id=1")
    assert http.get('/users/1/acquaintance').json()['mandatory_complete'] is False
    assert http.post('/users/1/acquaintance/consent',json={'version':1}).status_code==200
    assert http.put('/users/1/acquaintance/answers',json={'answers':answers,'confirm':True}).status_code==200
    newer=http.post('/users/1/acquaintance/resolve-profile')
    assert newer.status_code==200,newer.text
    assert newer.json()['late_readiness']['personalized_profile_id']!=pid
    with factory() as c:
        assert c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s',(pid,)).fetchone()==old


def test_absent_unconfirmed_ambiguous_and_new_binding_never_fall_back(stand):
    factory,http=stand
    with factory() as c:
        c.execute('INSERT INTO organization_assessment_source_bindings SELECT 3,11,42,assessment_configuration_id,role_profile_version_id FROM organization_assessment_source_bindings WHERE id=1')
        assert sources.current_binding(c,user_id=1,organization_id=10,assignment_ref='A',questionnaire_revision_id=41) is None
        c.execute("UPDATE questionnaire_response_revisions SET status='draft' WHERE id=42")
    result=http.get('/users/1/acquaintance').json()
    assert result['readiness']['briefing'] is None
    assert result['readiness']['reason']=='confirmed_questionnaire'
    with factory() as c:
        c.execute('DELETE FROM organization_assessment_source_bindings WHERE assignment_id=11')
    assert http.get('/users/1/acquaintance').json()['readiness']['reason']=='assignment_sources'
    with factory() as c:
        c.execute("INSERT INTO organization_assessment_assignments VALUES(13,10,1,'Other','active',NULL)")
    assert http.get('/users/1/acquaintance').json()['readiness']['reason']=='assessment_assignment'
    with factory() as c:
        c.execute("UPDATE organization_assessment_assignments SET status='revoked' WHERE recipient_user_id=1")
    assert http.get('/users/1/acquaintance').json()['readiness']['status']=='waiting_for_assignment'
