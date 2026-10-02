from __future__ import annotations

import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_case_runtime import checksum
from Api.m5_storage import import_package
from Api.m5_scenario_runtime import build_c45,transition
from Api.m7_cycle_planner import choose_next,create_plan,present,read_plan
from scripts.build_m5_case_package import OUTPUT

pytestmark=pytest.mark.integration


def setup(connection, admitted=False):
    package=json.loads((OUTPUT/'case-package.json').read_text());manifest=json.loads((OUTPUT/'manifest.json').read_text())
    rules=json.loads((OUTPUT/'execution-rules.json').read_text());case=package['cases'][0]
    if admitted:
        case['status']='FROZEN'
    connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)');connection.execute('INSERT INTO users VALUES(99)')
    connection.execute('''CREATE TABLE assessment_personalized_profiles(id BIGINT PRIMARY KEY,status TEXT,
        content_json JSONB,provenance_json JSONB,checksum TEXT)''')
    ensure_m5_runtime_schema(connection);import_package(connection,package=package,manifest=manifest,execution_rules=rules)
    connection.execute("INSERT INTO assessment_personalized_profiles VALUES(7,'ready',%s::jsonb,'{}',%s)",
        (json.dumps({'role_profile':{'code':case['base_role']}}),'c'*64))
    return case


def admit_case(connection,case):
    row=connection.execute("SELECT id FROM m5_case_versions WHERE case_id=%s",(case['case_id'],)).fetchone()
    for scope in ('case_format','case_dialogue','assessment_situation'):
        evidence={'eligibility':'user_admission','scope':scope,'synthetic':True}
        connection.execute("INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum) VALUES(%s,%s,'PASS',%s::jsonb,%s)",
            (row['id'],scope,json.dumps(evidence),checksum(evidence)))


@pytest.fixture
def db(test_database_url):
    schema='m7_plan_pytest_'+uuid4().hex
    with psycopg.connect(test_database_url,row_factory=dict_row) as c:
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
    def connect():
        c=psycopg.connect(test_database_url,row_factory=dict_row)
        c.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)));c.commit();return c
    try:yield connect
    finally:
        with psycopg.connect(test_database_url) as c:c.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def test_plan_keeps_full_goal_and_explains_unadmitted_pool(db):
    with db() as c:
        setup(c);result=create_plan(c,personalized_profile_id=7,selected_skills=['K1','K2','K3','K4'],created_by=99,key='plan');c.commit()
        assert result['plan']['status']=='NO_ROUTE'
        assert result['plan']['uncovered_target_ids']
        assert all(not x['eligible'] for x in result['plan']['catalog'])
        assert result['cycle_status']=='prepared'


def test_selected_case_is_prepared_presented_once_and_low_level_does_not_drive_repeat(db):
    with db() as c:
        case=setup(c,admitted=True);admit_case(c,case)
        plan=create_plan(c,personalized_profile_id=7,selected_skills=['K1','K2','K3','K4'],created_by=99,key='plan');c.commit()
    policy=json.loads((OUTPUT/'admission-policy.json').read_text())
    with db() as c:
        decision=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='next',created_by=99,policy=policy)
        replay=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='next',created_by=99,policy=policy)
        assert decision['id']==replay['id'] and decision['status']=='SELECTED', (decision['considered_json'],plan['plan']['route'],plan['plan']['catalog'][0])
        assert decision['assessment_situation_status']=='admitted';c.commit()
    with db() as c:
        result=present(c,decision_id=str(decision['id']),expected_revision=1);c.commit()
        assert result['presentation']['status']=='active'
        saved=read_plan(c,str(plan['cycle_id']))
        assert saved['cycle_status']=='active' and len(saved['decisions'])==1
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n']==1
        waiting=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='while-active',created_by=99,policy=policy)
        assert waiting['status']=='WAITING_CURRENT_AS'
        as_id=str(result['decision']['assessment_situation_id'])
        transition(c,assessment_situation_id=as_id,action='scenario_end',reason='synthetic',request_id='end')
        transition(c,assessment_situation_id=as_id,action='close',reason='synthetic',request_id='close')
        handoff=build_c45(c,as_id,mode='final')
        as_db=c.execute('SELECT id FROM m5_assessment_situations WHERE assessment_situation_id=%s',(as_id,)).fetchone()['id']
        for target in case['indicator_targets']:
            payload={'target':{'indicator_id':target['indicator_id'],'status':'ASSESSED','outcome':'L0','opportunity':'PRESENT'}}
            c.execute('''INSERT INTO m5_c54_receipts(assessment_situation_db_id,handoff_id,receipt_id,mode,indicator_id,m2_version,
                boundary_sequence,status,payload_json,validation_json,controlled_test) VALUES(%s,%s,%s,'final',%s,%s,%s,'accepted',%s::jsonb,'{}',TRUE)''',
                (as_db,handoff['handoff_id'],uuid4(),target['indicator_id'],target['m2_version'],handoff['boundary_sequence'],json.dumps(payload)))
        after_l0=choose_next(c,cycle_id=str(plan['cycle_id']),expected_plan_revision_id=str(plan['revision_id']),key='after-l0',created_by=99,policy=policy)
        assert after_l0['status']=='NO_ADMISSIBLE_CASE'
        assert set(after_l0['facts_json']['final_ia_target_ids'])=={x['indicator_id'] for x in case['indicator_targets']}
