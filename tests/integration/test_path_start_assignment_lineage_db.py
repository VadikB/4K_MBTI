"""Actual admin projection SQL on PostgreSQL; narrow synthetic schema, no LLM.

These are negative lineage fixtures, not pre-created data for the primary PATH.
"""
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from Api.acquaintance import _prepared_plan_snapshot

pytestmark = pytest.mark.integration


def stage_sql():
    from Api.admin_assignment_projection import ADMIN_ASSIGNMENT_STAGES_SQL
    return ADMIN_ASSIGNMENT_STAGES_SQL


@pytest.fixture
def lineage_db(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as c:
        schema = 'path_start_lineage_pytest_' + uuid4().hex
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        c.execute(psycopg.sql.SQL('SET LOCAL search_path TO {}').format(psycopg.sql.Identifier(schema)))
        tables = {
            'organization_assessment_assignments': 'id bigint,organization_id bigint,recipient_user_id bigint,assignment_ref text,status text,created_at timestamp,revoked_at timestamp',
            'organization_assessment_source_bindings': 'id bigint,assignment_id bigint,assessment_configuration_id bigint,role_profile_version_id bigint,questionnaire_revision_id bigint,created_at timestamp',
            'questionnaire_response_revisions': 'id bigint,organization_context_version_id bigint',
            'assessment_personalized_profiles': 'id bigint,user_id bigint,organization_id bigint,assessment_configuration_id bigint,role_profile_version_id bigint,organization_context_version_id bigint,status text,frozen_at timestamp',
            'participant_acquaintance_confirmations': 'id bigint,user_id bigint,organization_id bigint,assignment_ref text,questionnaire_revision_id bigint,personalized_profile_id bigint,confirmed_at timestamp',
            'assessment_preparation_jobs': 'id bigint,operation_id text,status text,user_id bigint,personalized_profile_id bigint,created_at timestamp',
            'product_cycle_preparation_operations': 'id bigint,operation_id text,status text,user_id bigint,request_json jsonb,created_at timestamp,result_json jsonb',
            'm5_cycles': 'id bigint,cycle_id text,status text,owner_user_id bigint,organization_id bigint,assignment_id bigint,usage_scope text,personalized_profile_id bigint,created_at timestamp,collection_closed_at timestamp,started_at timestamp',
            'm8_results': 'id bigint,cycle_db_id bigint',
            'm8_result_revisions': 'id bigint,results_id bigint,revision_no int,payload_json jsonb',
            'm8_reports': 'id bigint,result_revision_id bigint,audience text,revision_no int,status text,c67_json jsonb',
            'm8_published_reports': 'cycle_db_id bigint,report_id bigint',
            'm7_cycle_plans': 'id bigint,cycle_db_id bigint,status text',
            'm7_plan_revisions': 'plan_id bigint,revision_no int,content_json jsonb',
            'm5_assessment_situations': 'id bigint,cycle_db_id bigint,status text',
            'm7_route_position_as_history': 'assessment_situation_db_id bigint,disposition text',
            'm10_pipeline_runs': 'cycle_db_id bigint,status text,updated_at timestamp',
            'participant_acquaintance_states': 'user_id bigint,organization_id bigint,assignment_ref text,status text',
        }
        for name, columns in tables.items():
            c.execute('CREATE TABLE ' + name + '(' + columns + ')')
        c.execute("""INSERT INTO organization_assessment_assignments
            (id,organization_id,recipient_user_id,assignment_ref,status,created_at,revoked_at)
            VALUES(41,10,1,'A','active',NOW()-INTERVAL '2 hours',NULL),
                  (42,10,1,'B','active',NOW()-INTERVAL '1 hour',NULL)""")
        c.execute("INSERT INTO organization_assessment_source_bindings VALUES(1,41,11,2,21,NOW()-INTERVAL '2 hours'),(2,42,11,2,22,NOW()-INTERVAL '1 hour')")
        c.execute('INSERT INTO questionnaire_response_revisions VALUES(21,31),(22,32)')
        c.execute("INSERT INTO assessment_personalized_profiles VALUES(101,1,10,11,2,31,'ready',NOW()-INTERVAL '2 hours'),(102,1,10,11,2,32,'ready',NOW()-INTERVAL '1 hour'),(999,1,99,11,2,99,'ready',NOW())")
        c.execute("INSERT INTO participant_acquaintance_confirmations VALUES(1,1,10,'A',21,101,NOW()-INTERVAL '2 hours'),(2,1,10,'B',22,102,NOW()-INTERVAL '1 hour')")
        c.execute("INSERT INTO assessment_preparation_jobs VALUES(1,'job-A','completed',1,101,NOW()-INTERVAL '2 hours'),(2,'job-B','failed',1,102,NOW()-INTERVAL '1 hour'),(3,'foreign-later-job','running',1,999,NOW())")
        yield c
        c.rollback()  # Including this fixture's schema, never application data.


def project(c):
    return {row['assignment_ref']: row for row in c.execute(stage_sql(), ([10],)).fetchall()}


def test_two_assignments_same_configuration_keep_their_exact_profile_job(lineage_db):
    rows = project(lineage_db)
    assert (rows['A']['preparation_operation_id'], rows['A']['preparation_status']) == ('job-A', 'completed')
    assert (rows['B']['preparation_operation_id'], rows['B']['preparation_status']) == ('job-B', 'failed')


def test_cancellation_availability_uses_the_exact_cycle_and_rejects_unbound_legacy(lineage_db):
    assert {ref: row['can_cancel'] for ref, row in project(lineage_db).items()} == {'A': True, 'B': True}
    lineage_db.execute("""INSERT INTO m5_cycles(id,cycle_id,status,owner_user_id,organization_id,assignment_id,
        usage_scope,personalized_profile_id,created_at,started_at) VALUES
        (1,'started-A','prepared',1,10,41,'assessment',101,NOW(),NOW()),
        (2,'legacy-B','prepared',1,10,NULL,'assessment',102,NOW(),NULL)""")
    assert {ref: row['can_cancel'] for ref, row in project(lineage_db).items()} == {'A': False, 'B': False}
    lineage_db.execute('UPDATE m5_cycles SET assignment_id=42 WHERE id=2')
    assert project(lineage_db)['B']['can_cancel'] is True


def test_exact_product_operation_overrides_legacy_job_not_foreign_scope(lineage_db):
    lineage_db.execute('''INSERT INTO product_cycle_preparation_operations
        (id,operation_id,status,user_id,request_json,created_at) VALUES
        (1,'product-B','queued',1,'{"personalized_profile_id":102,"organization_id":10,"assignment_ref":"B","questionnaire_revision_id":22,"assignment_id":42}',NOW()),
        (2,'foreign-product','failed',1,'{"personalized_profile_id":102,"organization_id":99,"assignment_ref":"A","questionnaire_revision_id":21,"assignment_id":41}',NOW()+INTERVAL '1 minute')''')
    rows = project(lineage_db)
    assert rows['A']['preparation_operation_id'] == 'job-A'
    assert (rows['B']['preparation_operation_id'], rows['B']['preparation_status']) == ('product-B', 'queued')


def test_old_completed_operation_requires_exact_cycle_pointer_without_assignment_id(lineage_db):
    lineage_db.execute("INSERT INTO m5_cycles(id,cycle_id,status,owner_user_id,organization_id,assignment_id,usage_scope,personalized_profile_id,created_at) VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW())")
    lineage_db.execute('''INSERT INTO product_cycle_preparation_operations
        (id,operation_id,status,user_id,request_json,created_at,result_json) VALUES
        (1,'old-A','completed',1,'{"personalized_profile_id":101,"organization_id":10,"assignment_ref":"A","questionnaire_revision_id":21}',NOW(),'{"plan":{"cycle_id":"cycle-A"}}'),
        (2,'new-B','queued',1,'{"personalized_profile_id":102,"organization_id":10,"assignment_ref":"B","questionnaire_revision_id":22,"assignment_id":42}',NOW(),NULL)''')
    rows = project(lineage_db)
    assert rows['A']['preparation_operation_id'] == 'old-A'
    assert rows['B']['preparation_operation_id'] == 'new-B'


def test_new_generation_never_projects_old_prepared_cycle(lineage_db):
    lineage_db.execute("INSERT INTO m5_cycles(id,cycle_id,status,owner_user_id,organization_id,assignment_id,usage_scope,personalized_profile_id,created_at) VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW())")
    lineage_db.execute("INSERT INTO m5_assessment_situations VALUES(1,1,'admitted')")
    assert _prepared_plan_snapshot(lineage_db, personalized_profile_id=101, assignment_id=42) is None


def test_unproven_legacy_profile_is_unknown_but_exact_cycle_pointer_is_valid(lineage_db):
    lineage_db.execute('DELETE FROM participant_acquaintance_confirmations')
    assert all(row['preparation_operation_id'] is None for row in project(lineage_db).values())
    lineage_db.execute("INSERT INTO m5_cycles(id,cycle_id,status,owner_user_id,organization_id,assignment_id,usage_scope,personalized_profile_id,created_at) VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW())")
    rows = project(lineage_db)
    assert rows['A']['preparation_operation_id'] == 'job-A'
    assert rows['B']['preparation_operation_id'] is None


def test_profile_readiness_is_bound_to_selected_assignment_and_independent_of_start(lineage_db):
    from Api.routes import _project_admin_assessment_stage

    lineage_db.execute("INSERT INTO m5_cycles VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW(),NULL)")
    lineage_db.execute("INSERT INTO m7_cycle_plans VALUES(1,1,'READY')")
    lineage_db.execute("""INSERT INTO m7_plan_revisions VALUES(1,1,'{"route":[{}]}')""")
    lineage_db.execute("INSERT INTO m5_assessment_situations VALUES(1,1,'admitted')")
    lineage_db.execute("UPDATE assessment_personalized_profiles SET status='blocked' WHERE id=102")
    rows = project(lineage_db)
    a = _project_admin_assessment_stage({
        **rows['A'], 'assessment_profile_ready': False,
        'start_readiness': {'contract': 'm7_start_readiness/1', 'can_start': True, 'cycle_id': 'cycle-A', 'reasons': []},
    })
    assert a['assignment_id'] == 41 and a['code'] == 'ready_to_start'
    assert a['profile_readiness'] == {'personalized_profile_id': 101, 'status': 'ready'}
    b = _project_admin_assessment_stage({**rows['B'], 'assessment_profile_ready': True})
    assert b['assignment_id'] == 42 and b['start_readiness'] is None
    assert b['profile_readiness'] == {'personalized_profile_id': 102, 'status': 'blocked'}
    assert b['preparation_status'] is None
    lineage_db.execute("DELETE FROM participant_acquaintance_confirmations WHERE assignment_ref='B'")
    pending = _project_admin_assessment_stage({**project(lineage_db)['B'], 'assessment_profile_ready': True})
    assert pending['assignment_id'] == 42 and pending['profile_readiness'] is None


def test_admin_row_opens_same_admissible_publication_as_report_registry(lineage_db):
    from Api.routes import _project_admin_assessment_stage

    lineage_db.execute("INSERT INTO m5_cycles VALUES(1,'cycle-A','calculated',1,10,41,'assessment',101,NOW(),NOW())")
    lineage_db.execute("INSERT INTO m8_results VALUES(1,1)")
    lineage_db.execute("""INSERT INTO m8_result_revisions VALUES
        (1,1,1,'{"assessed_skill_profile":[{"outcome":"full_score"}]}'),
        (2,1,2,'{"assessed_skill_profile":[{"outcome":"result_without_score"}]}')""")
    lineage_db.execute("INSERT INTO m8_reports VALUES(101,1,'assessee',1,'ready','{}'),"
                       "(102,2,'assessee',1,'limited','{}'),(103,2,'customer',1,'ready','{}')")
    lineage_db.execute("INSERT INTO m8_published_reports VALUES(1,101)")
    a = _project_admin_assessment_stage(project(lineage_db)['A'])
    assert a['report_id'] == '101' and a['result_summary']['kind'] == 'full'
    lineage_db.execute("UPDATE m8_published_reports SET report_id=102 WHERE cycle_db_id=1")
    b = _project_admin_assessment_stage(project(lineage_db)['A'])
    assert b['report_id'] == '102' and b['result_summary']['kind'] == 'without_score'
    lineage_db.execute("UPDATE m8_published_reports SET report_id=101 WHERE cycle_db_id=1")
    lineage_db.execute("UPDATE m8_reports SET status='failed' WHERE id=101")
    unavailable = _project_admin_assessment_stage(project(lineage_db)['A'])
    assert unavailable['report_id'] is None and unavailable['result_summary'] is None
    lineage_db.execute("DELETE FROM m8_published_reports WHERE cycle_db_id=1")
    assert project(lineage_db)['A']['report_id'] == 102
    lineage_db.execute("UPDATE m8_reports SET c67_json=%s WHERE id=102",
                       ('{"processing":{"status":"failed"}}',))
    assert project(lineage_db)['A']['report_id'] is None


@pytest.mark.parametrize('status', ['queued', 'running'])
def test_shared_summary_fact_matches_admin_row(lineage_db, status):
    from Api.admin_assignment_projection import preparation_for_assignment
    lineage_db.execute('''INSERT INTO product_cycle_preparation_operations
        (id,operation_id,status,user_id,request_json,created_at) VALUES
        (1,'exact-B',%s,1,'{"personalized_profile_id":102,"organization_id":10,"assignment_ref":"B","questionnaire_revision_id":22,"assignment_id":42}',NOW())''', (status,))
    row = project(lineage_db)['B']
    assert preparation_for_assignment(lineage_db, assignment_id=42) == {
        'operation_id': row['preparation_operation_id'], 'status': row['preparation_status']}
    assert row['preparation_status'] == status


def test_completed_preparation_without_first_situation_does_not_allow_start(lineage_db):
    from Api.routes import _project_admin_assessment_stage
    lineage_db.execute("INSERT INTO m5_cycles(id,cycle_id,status,owner_user_id,organization_id,assignment_id,usage_scope,personalized_profile_id,created_at) VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW())")
    lineage_db.execute("INSERT INTO m7_cycle_plans VALUES(1,1,'READY')")
    lineage_db.execute('''INSERT INTO m7_plan_revisions VALUES(1,1,'{"route":[{}]}')''')
    row = project(lineage_db)['A']
    assert row['preparation_status'] == 'completed'
    assert row['admitted_situation'] is False
    # Even a declared positive decision cannot substitute for an admitted AS.
    row['start_readiness'] = {'contract':'m7_start_readiness/1','can_start':True,'cycle_id':'cycle-A','reasons':[]}
    result = _project_admin_assessment_stage(row)
    assert result['code'] == 'start_blocked'
    assert result['action'] is None


def test_latest_unbound_confirmation_never_reuses_old_legacy_profile(lineage_db):
    lineage_db.execute("INSERT INTO participant_acquaintance_confirmations VALUES(3,1,10,'B',22,NULL,NOW()+INTERVAL '1 minute')")
    b = project(lineage_db)['B']
    assert b['preparation_operation_id'] is None and b['personalized_profile_id'] is None


def test_legacy_job_with_shared_sources_cannot_choose_assignment_generation(lineage_db):
    from Api.admin_assignment_projection import preparation_for_assignment
    lineage_db.execute("UPDATE organization_assessment_assignments SET status='revoked',revoked_at=NOW() WHERE id=41")
    lineage_db.execute("INSERT INTO organization_assessment_assignments VALUES(43,10,1,'A','active',NOW(),NULL)")
    lineage_db.execute('INSERT INTO organization_assessment_source_bindings VALUES(3,43,11,2,21,NOW())')
    assert preparation_for_assignment(lineage_db, assignment_id=43) == {'operation_id':None,'status':None}
    rows = lineage_db.execute(stage_sql(), ([10],)).fetchall()
    assert next(row for row in rows if row['assignment_id'] == 43)['preparation_operation_id'] is None
    # A new generation first needs its own confirmed profile. Merely naming its
    # assignment in an operation cannot recycle the old generation's profile.
    lineage_db.execute('''INSERT INTO assessment_personalized_profiles
        SELECT 103,user_id,organization_id,assessment_configuration_id,role_profile_version_id,
               organization_context_version_id,status,NOW()
        FROM assessment_personalized_profiles WHERE id=101''')
    lineage_db.execute('''INSERT INTO product_cycle_preparation_operations
        (id,operation_id,status,user_id,request_json,created_at) VALUES
        (1,'new-generation','queued',1,'{"personalized_profile_id":103,"organization_id":10,"assignment_ref":"A","questionnaire_revision_id":21,"assignment_id":43}',NOW())''')
    assert preparation_for_assignment(lineage_db, assignment_id=43) == {'operation_id':None,'status':None}
    lineage_db.execute("INSERT INTO participant_acquaintance_confirmations VALUES(4,1,10,'A',21,103,NOW()+INTERVAL '1 minute')")
    assert preparation_for_assignment(lineage_db, assignment_id=43) == {'operation_id':'new-generation','status':'queued'}
    assert lineage_db.execute("SELECT status FROM assessment_preparation_jobs WHERE operation_id='job-A'").fetchone()['status'] == 'completed'
