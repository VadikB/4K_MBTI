"""REV-02: actual M4 lifecycle in an isolated PostgreSQL schema, synthetic participants only."""
import json
from pathlib import Path
from uuid import uuid4
import psycopg
import pytest
from psycopg.rows import dict_row
from Api.database import ensure_role_profile_schema, ensure_assessment_context_schema
from Api.assessment_role_profiles import publish_base_roles
from Api import assessment_contexts as contexts, participant_profile
from Api.schemas import PersonalizedProfileSelection
from Api.m10_product_flow import _owned_profile

pytestmark = pytest.mark.integration


def test_confirmed_profile_lifecycle_and_boundaries(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as c:
        schema = 'review_m4_pytest_' + uuid4().hex
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        c.execute(psycopg.sql.SQL('SET LOCAL search_path TO {}').format(psycopg.sql.Identifier(schema)))
        c.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)')
        c.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN NOT NULL)')
        c.execute('CREATE TABLE organization_memberships(organization_id BIGINT REFERENCES organizations(id),user_id BIGINT REFERENCES users(id),UNIQUE(organization_id,user_id))')
        c.execute('CREATE TABLE user_sessions(id BIGINT PRIMARY KEY,user_id BIGINT REFERENCES users(id),execution_snapshot_json JSONB,execution_checksum TEXT)')
        c.execute('CREATE TABLE assessment_methodologies(id BIGINT PRIMARY KEY)')
        c.execute('CREATE TABLE assessment_methodology_versions(id BIGINT PRIMARY KEY,methodology_id BIGINT REFERENCES assessment_methodologies(id),status TEXT,definition_json JSONB)')
        c.execute('CREATE TABLE assessment_configurations(id BIGINT PRIMARY KEY,methodology_version_id BIGINT REFERENCES assessment_methodology_versions(id),status TEXT,code TEXT,name TEXT)')
        c.execute('CREATE TABLE assessment_preparation_jobs(id BIGINT PRIMARY KEY)')
        c.execute('INSERT INTO users VALUES(1),(2)')
        c.execute('INSERT INTO organizations VALUES(10,TRUE),(20,TRUE)')
        ensure_role_profile_schema(c); ensure_assessment_context_schema(c)
        c.execute('INSERT INTO organization_memberships VALUES(10,1),(20,2)')
        c.execute('INSERT INTO assessment_methodologies VALUES(1)')
        c.execute("INSERT INTO assessment_methodology_versions VALUES(1,1,'published','{\"methodology_version\":\"1.1\"}')")
        c.execute("INSERT INTO assessment_configurations VALUES(1,1,'published','synthetic','Synthetic configuration')")
        root = Path(__file__).resolve().parents[2]
        package = root/'assessment_definitions/role_profiles/competencies_4k/1.1'
        roles = publish_base_roles(c, package=json.loads((package/'base_roles.json').read_text()),
            manifest=json.loads((package/'manifest.json').read_text()),published_by_user_id=1,decision_basis='synthetic isolated regression')
        organization = {'name':'Synthetic','organization_type':'компания','industry':'образование',
            'activity_description':'Разработка программ','case_reality_level':'обобщённый','organization_name_usage_rules':'не использовать'}
        org = contexts.create_organization_context_draft(c,organization_id=10,definition=organization)
        foreign = contexts.create_organization_context_draft(c,organization_id=20,definition=organization)
        for version in (org,foreign):contexts.publish_organization_context(c,version_id=version,confirmed_by_user_id=1)
        assert participant_profile.options(c,user_id=1)['current_profile'] is None
        selection = PersonalizedProfileSelection(organization_context_version_id=org,
            role_profile_version_id=roles['version_ids'][0],assessment_configuration_id=1)
        arguments = dict(user_id=1,selection=selection,full_name='Synthetic participant',position='Эксперт',duties='Анализ программ')
        first = participant_profile.confirm(c,**arguments)
        assert first['status']=='ready' and _owned_profile(c,1)==first['id']
        assert first['content']['user_context']=={'position_or_status':'Эксперт','regular_tasks':'Анализ программ'}
        assert 'Synthetic participant' not in str(first)
        assert participant_profile.confirm(c,**arguments)['id']==first['id']
        renamed = participant_profile.confirm(c,**{**arguments,'full_name':'Synthetic renamed participant'})
        assert renamed['id'] != first['id']
        second = participant_profile.confirm(c,**{**arguments,'position':'Менеджер'})
        assert second['id'] != first['id']
        assert c.execute('SELECT content_json FROM assessment_personalized_profiles WHERE id=%s',(first['id'],)).fetchone()['content_json']==first['content']
        with pytest.raises(ValueError,match='контекст вашей организации'):
            participant_profile.confirm(c,**{**arguments,'selection':selection.model_copy(update={'organization_context_version_id':foreign})})
        with pytest.raises(ValueError,match='опубликованная конфигурация'):
            participant_profile.confirm(c,**{**arguments,'selection':selection.model_copy(update={'assessment_configuration_id':999})})
        blocked = contexts.create_personalized_profile(c,user_id=1,assessment_configuration_id=1,
            organization_context_version_id=org,role_profile_version_id=selection.role_profile_version_id,
            user_context_version_id=second['sources']['user_context']['version_id'],
            conflicts=[{'type':'authority','resolved':False}])
        assert blocked['status']=='blocked'
        with pytest.raises(ValueError,match='существенные противоречия'): participant_profile.confirm(c,**arguments)
        with pytest.raises(ValueError,match='M4_PROFILE_NOT_READY'): _owned_profile(c,1)
        c.rollback()
