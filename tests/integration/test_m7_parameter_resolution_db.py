import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_cycle_runtime import create_cycle, create_session, start_session
from Api.m7_cycle_planner import read_plan, revise_prepared_parameters
from Api.m7_parameter_resolution import resolve, save_revision
from Api.acquaintance import _prepared_plan_snapshot, resolve_display_timing
from Api.m7_planning_package import load_rules
from Api import m7_planning_repository as repo

pytestmark = pytest.mark.integration


@pytest.fixture
def db(test_database_url):
    schema = 'm7_parameters_pytest_' + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
    connection = psycopg.connect(test_database_url, row_factory=dict_row)
    connection.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
    connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)')
    connection.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN NOT NULL)')
    connection.execute("CREATE TABLE assessment_configurations(id BIGINT PRIMARY KEY,status TEXT NOT NULL)")
    connection.execute('''CREATE TABLE assessment_personalized_profiles(
        id BIGINT PRIMARY KEY,user_id BIGINT,organization_id BIGINT,assessment_configuration_id BIGINT,
        status TEXT,content_json JSONB,provenance_json JSONB,checksum TEXT)''')
    connection.execute("INSERT INTO users VALUES(7),(99)")
    connection.execute("INSERT INTO organizations VALUES(10,TRUE),(20,TRUE)")
    connection.execute("INSERT INTO assessment_configurations VALUES(100,'published'),(200,'published')")
    connection.execute("""INSERT INTO assessment_personalized_profiles VALUES
        (1,7,10,100,'ready','{}','{}',%s)""", ('p'*64,))
    ensure_m5_runtime_schema(connection)
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()
        with psycopg.connect(test_database_url) as cleanup:
            cleanup.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def test_sources_resolve_independently_and_started_cycle_keeps_snapshot(db):
    save_revision(db,source_scope='organization',organization_id=10,assessment_configuration_id=None,
                  values={'time_budget_seconds':4200},created_by=99)
    save_revision(db,source_scope='program',organization_id=10,assessment_configuration_id=100,
                  values={'calendar_window_seconds':172800},created_by=99)
    resolved=resolve(db,personalized_profile_id=1,usage_scope='assessment')
    assert resolved['values']=={'time_budget_seconds':4200,'calendar_window_seconds':172800}
    assert resolved['sources']['time_budget_seconds']['kind']=='organization'
    assert resolved['sources']['calendar_window_seconds']['kind']=='program'
    display=resolve_display_timing(db,personalized_profile_id=1)
    assert display['status']=='resolved'
    assert display['time_budget_seconds']==4200
    assert display['calendar_window_seconds']==172800
    assert display['resolved_checksum']==resolved['resolved_checksum']
    cycle=create_cycle(db,personalized_profile_id=1,selected_role_ref={'id':'r','version':'1','checksum':'x'},
        target_set=[{'indicator_id':'K1.I1','m2_version':'1'}],created_by=7,usage_scope='assessment')
    save_revision(db,source_scope='organization',organization_id=10,assessment_configuration_id=None,
                  values={'time_budget_seconds':4800},created_by=99)
    assert db.execute('SELECT time_budget_seconds FROM m5_cycles WHERE id=%s',(cycle['id'],)).fetchone()['time_budget_seconds']==4200
    assert resolve(db,personalized_profile_id=1,usage_scope='assessment')['values']['time_budget_seconds']==4800
    with pytest.raises(ValueError,match='M7_PARAMETER_CONFIGURATION_NOT_ALLOWED'):
        save_revision(db,source_scope='program',organization_id=10,assessment_configuration_id=999,
                      values={'calendar_window_seconds':100},created_by=99)
    save_revision(db,source_scope='program',organization_id=20,assessment_configuration_id=100,
                  values={'calendar_window_seconds':99},created_by=99)
    assert resolve(db,personalized_profile_id=1,usage_scope='assessment')['values']['calendar_window_seconds']==172800


def test_identical_published_program_revision_is_idempotent(db):
    first=save_revision(db,source_scope='program',organization_id=10,assessment_configuration_id=100,
                        values={'time_budget_seconds':7200,'calendar_window_seconds':259200},created_by=99)
    second=save_revision(db,source_scope='program',organization_id=10,assessment_configuration_id=100,
                         values={'time_budget_seconds':7200,'calendar_window_seconds':259200},created_by=99)
    assert second['id']==first['id']
    assert db.execute("SELECT count(*) AS n FROM m7_parameter_revisions WHERE source_scope='program'").fetchone()['n']==1


def test_pilot_120_program_revision_is_resolved_and_frozen_in_new_cycle(db):
    revision=save_revision(db,source_scope='program',organization_id=10,assessment_configuration_id=100,
        values={'time_budget_seconds':7200,'calendar_window_seconds':259200},created_by=99)
    resolved=resolve(db,personalized_profile_id=1,usage_scope='assessment')
    assert resolved['values']=={'time_budget_seconds':7200,'calendar_window_seconds':259200}
    assert resolved['sources']['time_budget_seconds']['kind']=='program'
    assert resolved['sources']['time_budget_seconds']['revision_id']==str(revision['id'])
    display=resolve_display_timing(db,personalized_profile_id=1)
    assert display['time_budget_seconds']==7200
    assert display['calendar_window_seconds']==259200

    cycle=create_cycle(db,personalized_profile_id=1,selected_role_ref={'id':'r','version':'1','checksum':'x'},
        target_set=[{'indicator_id':'K1.I1','m2_version':'1'}],created_by=7,usage_scope='assessment')
    row=db.execute("SELECT time_budget_seconds,calendar_window_seconds,parameter_sources_json "
        "FROM m5_cycles WHERE id=%s",(cycle['id'],)).fetchone()
    assert row['time_budget_seconds']==7200
    assert row['calendar_window_seconds']==259200
    assert row['parameter_sources_json']['time_budget']['kind']=='program'

    save_revision(db,source_scope='program',organization_id=10,assessment_configuration_id=100,
        values={'time_budget_seconds':7300,'calendar_window_seconds':259200},created_by=99)
    frozen=db.execute("SELECT time_budget_seconds,calendar_window_seconds,parameter_sources_json "
        "FROM m5_cycles WHERE id=%s",(cycle['id'],)).fetchone()
    assert frozen==row


def test_invalid_values_and_client_override_are_not_defaults(db):
    assert resolve(db,personalized_profile_id=1,usage_scope='assessment')['values']['time_budget_seconds']==3600
    for value in (0,-1,'3600',True):
        with pytest.raises(ValueError,match='M7_PARAMETER_VALUE_INVALID'):
            save_revision(db,source_scope='organization',organization_id=10,assessment_configuration_id=None,
                          values={'time_budget_seconds':value},created_by=99)
    with pytest.raises(ValueError,match='M7_PARAMETER_OVERRIDE_NOT_ALLOWED'):
        resolve(db,personalized_profile_id=1,usage_scope='assessment',qa_overrides={'time_budget_seconds':10})
    qa=resolve(db,personalized_profile_id=1,usage_scope='qa',qa_overrides={'time_budget_seconds':10})
    assert qa['values']['time_budget_seconds']==10
    assert qa['sources']['time_budget_seconds']['kind']=='qa_explicit_override'
    db.execute("""INSERT INTO m7_parameter_revisions VALUES
        (%s,'organization',10,NULL,1,'published',%s::jsonb,%s,99,NOW(),NOW())""",
        (uuid4(),json.dumps({'time_budget_seconds':3700}),'broken'))
    with pytest.raises(ValueError,match='M7_PARAMETER_CONFIGURATION_CHECKSUM_MISMATCH'):
        resolve(db,personalized_profile_id=1,usage_scope='assessment')


def test_prepared_plan_revision_is_historical_and_freezes_at_first_start(db):
    cycle=create_cycle(db,personalized_profile_id=1,selected_role_ref={'id':'r','version':'1','checksum':'x'},
        target_set=[{'indicator_id':'K1.I1','m2_version':'1'}],created_by=7,usage_scope='qa')
    session=create_session(db,cycle_id=str(cycle['cycle_id']),created_by=7)
    rules=load_rules();content={'status':'READY','route':[{'planned_max_minutes':1}],
        'planned_max_seconds':60,'uncovered_target_ids':[],'time_budget_seconds':3600,
        'calendar_window_seconds':259200}
    repo.save_plan(db,cycle=cycle,profile_ref=cycle['profile_ref_json'],full_targets=cycle['target_set_json'],
        planned_targets=cycle['target_set_json'],requirements=[],rules=rules,content=content,
        created_by=7,key='initial',request_hash='h')
    revised=revise_prepared_parameters(db,cycle_id=str(cycle['cycle_id']),created_by=99,
        reason='approved_qa_adjustment',time_budget_seconds=4000)
    assert revised['revision_no']==2 and revised['plan']['time_budget_seconds']==4000
    assert db.execute('SELECT count(*) AS n FROM m7_plan_revisions').fetchone()['n']==2
    assert read_plan(db,str(cycle['cycle_id']))['revision_no']==2
    assert db.execute('SELECT count(*) AS n FROM m7_plan_revisions').fetchone()['n']==2
    start_session(db,session_id=str(session['session_id']))
    with pytest.raises(ValueError,match='M7_PLAN_PARAMETERS_ALREADY_FROZEN'):
        revise_prepared_parameters(db,cycle_id=str(cycle['cycle_id']),created_by=99,
            reason='late',time_budget_seconds=5000)


def test_w02_reloads_the_saved_assessment_plan_snapshot(db):
    cycle=create_cycle(db,personalized_profile_id=1,selected_role_ref={'id':'r','version':'1','checksum':'x'},
        target_set=[{'indicator_id':'K1.I1','m2_version':'1'}],created_by=7,usage_scope='assessment')
    rules=load_rules();content={'status':'READY','route':[{'planned_max_minutes':12}],
        'planned_max_seconds':720,'uncovered_target_ids':[],'time_budget_seconds':3600,
        'calendar_window_seconds':259200}
    repo.save_plan(db,cycle=cycle,profile_ref=cycle['profile_ref_json'],full_targets=cycle['target_set_json'],
        planned_targets=cycle['target_set_json'],requirements=[],rules=rules,content=content,
        created_by=7,key='w02-display',request_hash='w02-display-hash')
    snapshot=_prepared_plan_snapshot(db,personalized_profile_id=1)
    assert snapshot['cycle_id']==str(cycle['cycle_id'])
    assert snapshot['revision_no']==1
    assert snapshot['revision_id']
    assert snapshot['plan']['planned_max_seconds']==720
