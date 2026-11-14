"""Actual admin projection SQL on PostgreSQL; narrow synthetic schema, no LLM.

These are negative lineage fixtures, not pre-created data for the primary PATH.
"""
import ast
import inspect
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from Api.routes import _build_admin_organizations
from Api.acquaintance import _prepared_plan_snapshot

pytestmark = pytest.mark.integration


def stage_sql():
    tree = ast.parse(inspect.getsource(_build_admin_organizations))
    return next(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
        and isinstance(node.value, str) and 'FROM organization_assessment_assignments assignment' in node.value)


@pytest.fixture
def lineage_db(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as c:
        schema = 'path_start_lineage_pytest_' + uuid4().hex
        c.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        c.execute(psycopg.sql.SQL('SET LOCAL search_path TO {}').format(psycopg.sql.Identifier(schema)))
        tables = {
            'organization_assessment_assignments': 'id bigint,organization_id bigint,recipient_user_id bigint,assignment_ref text,status text,created_at timestamp,revoked_at timestamp',
            'organization_assessment_source_bindings': 'id bigint,assignment_id bigint,assessment_configuration_id bigint,role_profile_version_id bigint,questionnaire_revision_id bigint',
            'questionnaire_response_revisions': 'id bigint,organization_context_version_id bigint',
            'assessment_personalized_profiles': 'id bigint,user_id bigint,organization_id bigint,assessment_configuration_id bigint,role_profile_version_id bigint,organization_context_version_id bigint,status text,frozen_at timestamp',
            'participant_acquaintance_confirmations': 'id bigint,user_id bigint,organization_id bigint,assignment_ref text,questionnaire_revision_id bigint,personalized_profile_id bigint,confirmed_at timestamp',
            'assessment_preparation_jobs': 'id bigint,operation_id text,status text,user_id bigint,personalized_profile_id bigint,created_at timestamp',
            'product_cycle_preparation_operations': 'id bigint,operation_id text,status text,user_id bigint,request_json jsonb,created_at timestamp,result_json jsonb',
            'm5_cycles': 'id bigint,cycle_id text,status text,owner_user_id bigint,organization_id bigint,assignment_id bigint,usage_scope text,personalized_profile_id bigint,created_at timestamp',
            'm8_results': 'id bigint,cycle_db_id bigint',
            'm8_result_revisions': 'id bigint,results_id bigint,revision_no int,payload_json jsonb',
            'm8_reports': 'id bigint,result_revision_id bigint,audience text,revision_no int',
            'm8_cycle_report_recipients': 'cycle_db_id bigint,user_id bigint',
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
        c.execute('INSERT INTO organization_assessment_source_bindings VALUES(1,41,11,2,21),(2,42,11,2,22)')
        c.execute('INSERT INTO questionnaire_response_revisions VALUES(21,31),(22,32)')
        c.execute("INSERT INTO assessment_personalized_profiles VALUES(101,1,10,11,2,31,'ready',NOW()-INTERVAL '2 hours'),(102,1,10,11,2,32,'ready',NOW()-INTERVAL '1 hour'),(999,1,99,11,2,99,'ready',NOW())")
        c.execute("INSERT INTO participant_acquaintance_confirmations VALUES(1,1,10,'A',21,101,NOW()-INTERVAL '2 hours'),(2,1,10,'B',22,102,NOW()-INTERVAL '1 hour')")
        c.execute("INSERT INTO assessment_preparation_jobs VALUES(1,'job-A','completed',1,101,NOW()-INTERVAL '2 hours'),(2,'job-B','failed',1,102,NOW()-INTERVAL '1 hour'),(3,'foreign-later-job','running',1,999,NOW())")
        yield c
        c.rollback()  # Including this fixture's schema, never application data.


def project(c):
    return {row['assignment_ref']: row for row in c.execute(stage_sql(), (1, [10])).fetchall()}


def test_two_assignments_same_configuration_keep_their_exact_profile_job(lineage_db):
    rows = project(lineage_db)
    assert (rows['A']['preparation_operation_id'], rows['A']['preparation_status']) == ('job-A', 'completed')
    assert (rows['B']['preparation_operation_id'], rows['B']['preparation_status']) == ('job-B', 'failed')


def test_exact_product_operation_overrides_legacy_job_not_foreign_scope(lineage_db):
    lineage_db.execute('''INSERT INTO product_cycle_preparation_operations
        (id,operation_id,status,user_id,request_json,created_at) VALUES
        (1,'product-B','queued',1,'{"personalized_profile_id":102,"organization_id":10,"assignment_ref":"B","questionnaire_revision_id":22,"assignment_id":42}',NOW()),
        (2,'foreign-product','failed',1,'{"personalized_profile_id":102,"organization_id":99,"assignment_ref":"A","questionnaire_revision_id":21,"assignment_id":41}',NOW()+INTERVAL '1 minute')''')
    rows = project(lineage_db)
    assert rows['A']['preparation_operation_id'] == 'job-A'
    assert (rows['B']['preparation_operation_id'], rows['B']['preparation_status']) == ('product-B', 'queued')


def test_old_completed_operation_requires_exact_cycle_pointer_without_assignment_id(lineage_db):
    lineage_db.execute("INSERT INTO m5_cycles VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW())")
    lineage_db.execute('''INSERT INTO product_cycle_preparation_operations
        (id,operation_id,status,user_id,request_json,created_at,result_json) VALUES
        (1,'old-A','completed',1,'{"personalized_profile_id":101,"organization_id":10,"assignment_ref":"A","questionnaire_revision_id":21}',NOW(),'{"plan":{"cycle_id":"cycle-A"}}'),
        (2,'new-B','queued',1,'{"personalized_profile_id":102,"organization_id":10,"assignment_ref":"B","questionnaire_revision_id":22,"assignment_id":42}',NOW(),NULL)''')
    rows = project(lineage_db)
    assert rows['A']['preparation_operation_id'] == 'old-A'
    assert rows['B']['preparation_operation_id'] == 'new-B'


def test_new_generation_never_projects_old_prepared_cycle(lineage_db):
    lineage_db.execute("INSERT INTO m5_cycles VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW())")
    lineage_db.execute("INSERT INTO m5_assessment_situations VALUES(1,1,'admitted')")
    assert _prepared_plan_snapshot(lineage_db, personalized_profile_id=101, assignment_id=42) is None


def test_unproven_legacy_profile_is_unknown_but_exact_cycle_pointer_is_valid(lineage_db):
    lineage_db.execute('DELETE FROM participant_acquaintance_confirmations')
    assert all(row['preparation_operation_id'] is None for row in project(lineage_db).values())
    lineage_db.execute("INSERT INTO m5_cycles VALUES(1,'cycle-A','prepared',1,10,41,'assessment',101,NOW())")
    rows = project(lineage_db)
    assert rows['A']['preparation_operation_id'] == 'job-A'
    assert rows['B']['preparation_operation_id'] is None
