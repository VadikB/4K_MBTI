from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.rows import dict_row

from Api import m8_report_access, m8_results, routes

pytestmark = pytest.mark.integration
MIGRATIONS = Path('scripts/migrations')


def _schema(connection):
    name = 'm8_access_pytest_' + uuid4().hex
    connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
    connection.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(name)))
    return name


def _report(report_id, cycle_id):
    return {'id': str(report_id), 'revision_no': 1, 'status': 'ready', 'owner_user_id': 10,
            'cycle_id': str(cycle_id), 'results_revision_id': str(uuid4()),
            'program_name': 'Программа A', 'participant_name': 'Участник',
            'c67': {'contract': 'C-67', 'skills': [{'skill_id': 'S1', 'outcome': 'full_score',
                                'score': {'value': 0, 'numerator': 0, 'denominator': 1},
                                'components': [{'private': 'hidden'}], 'validator_trace': {'private': True}}],
                    'limitations': ['Ограничение'], 'coverage': {},
                    'competencies': [{'competency_id': 'C1', 'skill_ids': ['S1'],
                                      'score': {'value': 0, 'validator_trace': 'hidden'}}],
                    'descriptive': {'status': 'ready', 'summary': ['Факт'], 'validator_trace': {'secret': 'hidden'},
                                    'claims': [{'kind': 'quote', 'skill_ids': ['S1'], 'text': 'Допустимая цитата',
                                                'basis_refs': ['internal'], 'limitations': []}]},
                    'profile_ref': {'private': 'hidden'}, 'assessment_situations': [{'dialogue': 'hidden'}],
                    'provenance': {'prompt': 'hidden'},
                    'report_mechanism': {'id': 'm8', 'version': '1', 'checksum': 'hidden'}}}


def test_owner_and_admin_http_scope_ignores_legacy_recipient_list(test_database_url, monkeypatch):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema_name = _schema(connection)
        connection.execute('CREATE TABLE users(id bigint PRIMARY KEY,full_name text,email text)')
        connection.execute('CREATE TABLE organizations(id bigint PRIMARY KEY,is_active boolean)')
        connection.execute('CREATE TABLE organization_memberships(organization_id bigint,user_id bigint,role text)')
        connection.execute('CREATE TABLE assessment_configurations(id bigint PRIMARY KEY,name text)')
        connection.execute('CREATE TABLE assessment_personalized_profiles(id bigint PRIMARY KEY,assessment_configuration_id bigint)')
        connection.execute('''CREATE TABLE m5_cycles(id bigint PRIMARY KEY,cycle_id uuid,owner_user_id bigint,
            organization_id bigint,personalized_profile_id bigint,usage_scope text,status text,
            display_snapshot_json jsonb,created_at timestamptz DEFAULT now(),started_at timestamptz,
            collection_closed_at timestamptz)''')
        connection.execute('CREATE TABLE m10_pipeline_runs(cycle_db_id bigint,status text,stage text,error_code text)')
        connection.execute('CREATE TABLE m8_results(id uuid PRIMARY KEY,cycle_db_id bigint)')
        connection.execute('CREATE TABLE m8_result_revisions(id uuid PRIMARY KEY,results_id uuid,revision_no integer)')
        connection.execute('''CREATE TABLE m8_reports(id uuid PRIMARY KEY,result_revision_id uuid,revision_no integer,
            audience text,created_at timestamptz DEFAULT now(),c67_json jsonb)''')
        m8_report_access.ensure_schema(connection)
        connection.execute("INSERT INTO users VALUES(10,'Участник','owner@example.test'),(11,'Другой','other@example.test'),"
                           "(20,'Админ','admin@example.test'),(21,'Новый','new@example.test'),"
                           "(22,'Снятый','removed@example.test'),(23,'Чужой','foreign@example.test')")
        connection.execute('INSERT INTO organizations VALUES(1,true),(2,true)')
        connection.execute("INSERT INTO organization_memberships VALUES(1,10,'member'),(1,20,'admin'),"
                           "(1,22,'admin'),(2,23,'admin')")
        connection.execute("INSERT INTO assessment_configurations VALUES(1,'Программа A')")
        connection.execute('INSERT INTO assessment_personalized_profiles VALUES(500,1)')
        cycle_id, result_id, revision_id, report_id = uuid4(), uuid4(), uuid4(), uuid4()
        previous_cycle, previous_result, previous_revision, previous_report = uuid4(), uuid4(), uuid4(), uuid4()
        foreign_cycle, foreign_result, foreign_revision, foreign_report = uuid4(), uuid4(), uuid4(), uuid4()
        connection.execute("INSERT INTO m5_cycles(id,cycle_id,owner_user_id,organization_id,personalized_profile_id,"
                           "usage_scope,status,display_snapshot_json,started_at,collection_closed_at) VALUES(1,%s,10,1,500,'assessment',"
                           "'calculated','{\"program_name\":\"Программа A\"}'::jsonb,now(),now())", (cycle_id,))
        connection.execute('INSERT INTO m8_results VALUES(%s,1)', (result_id,))
        connection.execute('INSERT INTO m8_result_revisions VALUES(%s,%s,1)', (revision_id, result_id))
        connection.execute("INSERT INTO m8_reports(id,result_revision_id,revision_no,audience,c67_json) "
                           "VALUES(%s,%s,1,'assessee','{}')", (report_id, revision_id))
        for db_id, cid, org_id, result, revision, report in (
            (2, previous_cycle, 1, previous_result, previous_revision, previous_report),
            (3, foreign_cycle, 2, foreign_result, foreign_revision, foreign_report),
        ):
            connection.execute("""INSERT INTO m5_cycles(id,cycle_id,owner_user_id,organization_id,
                personalized_profile_id,usage_scope,status,display_snapshot_json,created_at,started_at,collection_closed_at)
                VALUES(%s,%s,10,%s,500,'assessment','calculated',%s::jsonb,now()-interval '1 day',
                now()-interval '1 day',now()-interval '1 day')""", (db_id, cid, org_id,
                    '{"program_name":"Программа B"}' if db_id == 2 else None))
            connection.execute('INSERT INTO m8_results VALUES(%s,%s)', (result, db_id))
            connection.execute('INSERT INTO m8_result_revisions VALUES(%s,%s,1)', (revision, result))
            connection.execute("INSERT INTO m8_reports(id,result_revision_id,revision_no,audience,c67_json) "
                               "VALUES(%s,%s,1,'assessee','{}')", (report, revision))
        connection.execute('CREATE TABLE m8_cycle_report_recipients(cycle_db_id bigint,user_id bigint)')
        connection.execute('INSERT INTO m8_cycle_report_recipients VALUES(1,22),(1,23)')
        connection.execute('DELETE FROM organization_memberships WHERE organization_id=1 AND user_id IN (10,22)')
        connection.execute("INSERT INTO organization_memberships VALUES(1,21,'admin')")
        connection.execute("UPDATE assessment_configurations SET name='Новое название' WHERE id=1")
        assert m8_results.owner_can_read_cycle(connection, str(cycle_id), 10)
        assert not m8_results.owner_can_read_cycle(connection, str(cycle_id), 11)
        history = m8_results.list_owned_cycles(connection, 10)
        assert len(history) == 3 and history[0]['program_name'] == 'Программа A'
        assert next(item for item in history if item['cycle_id'] == str(previous_cycle))['program_name'] == 'Программа B'
        assert history[0]['collection_closed_at'] is not None
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=22)
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=23)
        assert m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=21)
        assert m8_report_access.list_customer_reports(connection, user_id=21)[0]['program_name'] == 'Программа A'

        @contextmanager
        def get_connection():
            connection.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema_name)))
            yield connection
        monkeypatch.setattr(routes, 'get_connection', get_connection)
        monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
            lambda token: SimpleNamespace(id={'owner': 10, 'other': 11, 'admin': 20, 'new': 21,
                                              'removed': 22, 'foreign': 23}[token])
            if token in {'owner', 'other', 'admin', 'new', 'removed', 'foreign'} else None)
        report_cycles = {str(report_id): cycle_id, str(previous_report): previous_cycle,
                         str(foreign_report): foreign_cycle}
        monkeypatch.setattr(routes.m8_results, 'read_report',
                            lambda _, rid: _report(rid, report_cycles[str(rid)]))
        monkeypatch.setattr(routes.m8_results, 'render_pdf', lambda *_: b'%PDF-synthetic')
        monkeypatch.setattr(routes.m8_report_comparison, 'render_comparison_pdf', lambda *_: b'%PDF-synthetic')
        app = FastAPI(); app.include_router(routes.router)
        with TestClient(app) as client:
            own = f'/users/assessment/m8/reports/{report_id}'
            admin = f'/users/admin/m8-access/reports/{report_id}'
            assert client.get(own).status_code == client.get(admin).status_code == 401
            client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
            assert client.get('/users/assessment/m8/history').json()['reports_total'] == 3
            detail = client.get(own)
            assert detail.status_code == 200 and detail.json()['c67']['skills'][0]['score']['value'] == 0
            assert 'validator_trace' not in detail.text and 'profile_ref' not in detail.text
            assert detail.json()['c67']['contract'] == 'C-67'
            assert client.get(own + '/pdf').status_code == 200
            comparison = own + '/comparison'
            assert client.get(comparison, params={'previous_report_id': str(previous_report)}).status_code == 200
            assert client.get(own + '/comparison.pdf', params={'previous_report_id': str(previous_report)}).status_code == 200
            assert client.get(comparison, params={'previous_report_id': str(foreign_report)}).status_code == 403
            client.cookies.set(routes.SESSION_COOKIE_NAME, 'other')
            assert client.get(own).status_code == client.get(own + '/pdf').status_code == 403
            assert client.get(comparison, params={'previous_report_id': str(previous_report)}).status_code == 403
            for token in ('admin', 'new'):
                client.cookies.set(routes.SESSION_COOKIE_NAME, token)
                assert client.get('/users/admin/m8-access/reports').json()['items'][0]['program_name'] == 'Программа A'
                detail = client.get(admin)
                assert detail.status_code == 200 and detail.json()['participant_name'] == 'Участник'
                assert 'validator_trace' not in detail.text and 'dialogue' not in detail.text
                assert client.get(admin + '/pdf').status_code == 200
            for token in ('removed', 'foreign'):
                client.cookies.set(routes.SESSION_COOKIE_NAME, token)
                items = client.get('/users/admin/m8-access/reports').json()['items']
                if token == 'removed':
                    assert items == []
                else:
                    assert [item['report_id'] for item in items] == [str(foreign_report)]
                assert client.get(admin).status_code == client.get(admin + '/pdf').status_code == 403
        connection.rollback()


def test_archive_migration_empty_filled_and_rollback(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        _schema(connection)
        up = (MIGRATIONS / 'p4k_report_02_archive_access.sql').read_text()
        connection.execute(up)
        assert connection.execute("SELECT to_regclass('m8_cycle_report_recipients') AS value").fetchone()['value'] is None
        connection.execute('CREATE TABLE m8_report_access_revisions(id bigint PRIMARY KEY,customer_enabled boolean)')
        connection.execute('CREATE TABLE m8_report_access_recipients(access_revision_id bigint,user_id bigint)')
        connection.execute('CREATE TABLE m8_cycle_report_access(cycle_db_id bigint,access_revision_id bigint)')
        connection.execute('CREATE TABLE m8_cycle_report_recipients(cycle_db_id bigint,user_id bigint)')
        connection.execute('INSERT INTO m8_report_access_revisions VALUES(7,true)')
        connection.execute('INSERT INTO m8_report_access_recipients VALUES(7,20)')
        connection.execute('INSERT INTO m8_cycle_report_access VALUES(1,7)')
        connection.execute('INSERT INTO m8_cycle_report_recipients VALUES(1,20)')
        connection.execute(up)
        assert connection.execute("SELECT to_regclass('m8_cycle_report_recipients') AS value").fetchone()['value'] is None
        assert connection.execute('SELECT user_id FROM m8_cycle_report_recipients_legacy_audit').fetchone()['user_id'] == 20
        connection.execute(up)
        connection.execute((MIGRATIONS / 'p4k_report_02_restore_access.sql').read_text())
        assert connection.execute('SELECT user_id FROM m8_cycle_report_recipients').fetchone()['user_id'] == 20
        connection.rollback()


def test_public_projection_excludes_nested_private_data():
    report = _report(uuid4(), uuid4())
    for audience in ('assessee', 'customer'):
        projected = m8_report_access.public_projection(report, audience=audience)
        assert projected['c67']['skills'][0]['score']['value'] == 0
        assert projected['c67']['competencies'][0]['score']['value'] == 0
        assert projected['c67']['descriptive']['claims'][0]['text'] == 'Допустимая цитата'
        for forbidden in ('validator_trace', 'profile_ref', 'assessment_situations', 'provenance',
                          'components', 'basis_refs', 'checksum'):
            assert forbidden not in str(projected)
