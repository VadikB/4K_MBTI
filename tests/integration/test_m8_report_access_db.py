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

from Api import m8_report_access, m8_report_corrections, m8_results, routes

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
        connection.execute('CREATE TABLE organizations(id bigint PRIMARY KEY,name text,is_active boolean)')
        connection.execute('CREATE TABLE organization_memberships(organization_id bigint,user_id bigint,role text)')
        connection.execute('CREATE TABLE assessment_configurations(id bigint PRIMARY KEY,name text)')
        connection.execute('CREATE TABLE assessment_personalized_profiles(id bigint PRIMARY KEY,assessment_configuration_id bigint)')
        connection.execute('''CREATE TABLE m5_cycles(id bigint PRIMARY KEY,cycle_id uuid,owner_user_id bigint,
            organization_id bigint,personalized_profile_id bigint,usage_scope text,status text,
            display_snapshot_json jsonb,created_at timestamptz DEFAULT now(),started_at timestamptz,
            collection_closed_at timestamptz)''')
        connection.execute('CREATE TABLE m10_pipeline_runs(cycle_db_id bigint,status text,stage text,error_code text)')
        connection.execute('CREATE TABLE m8_results(id uuid PRIMARY KEY,cycle_db_id bigint)')
        connection.execute('CREATE TABLE m8_result_revisions(id uuid PRIMARY KEY,results_id uuid,revision_no integer,payload_json jsonb)')
        connection.execute('CREATE TABLE m7_cycle_plans(id bigint,cycle_db_id bigint)')
        connection.execute('CREATE TABLE m7_plan_revisions(plan_id bigint,revision_no integer,content_json jsonb)')
        connection.execute('''CREATE TABLE m8_reports(id uuid PRIMARY KEY,result_revision_id uuid,revision_no integer,
            audience text,status text DEFAULT 'ready',created_at timestamptz DEFAULT now(),c67_json jsonb)''')
        m8_report_access.ensure_schema(connection)
        m8_report_corrections.ensure_schema(connection)
        connection.execute("INSERT INTO users VALUES(10,'Участник','owner@example.test'),(11,'Другой','other@example.test'),"
                           "(20,'Админ','admin@example.test'),(21,'Новый','new@example.test'),"
                           "(22,'Снятый','removed@example.test'),(23,'Чужой','foreign@example.test')")
        connection.execute("INSERT INTO organizations VALUES(1,'Организация A',true),(2,'Организация B',true)")
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
        # A newer technical revision, even with an older creation timestamp, stays
        # on the same Cycle card. Closure time, not report creation, orders cards.
        correction_id, correction_report_id = uuid4(), uuid4()
        connection.execute('UPDATE m5_cycles SET collection_closed_at=now()-interval \'2 days\' WHERE id=1')
        connection.execute('UPDATE m5_cycles SET collection_closed_at=now()-interval \'1 day\' WHERE id=2')
        connection.execute('UPDATE m5_cycles SET collection_closed_at=now()-interval \'3 days\' WHERE id=3')
        connection.execute('INSERT INTO m8_result_revisions VALUES(%s,%s,2)', (correction_id, result_id))
        connection.execute("""INSERT INTO m8_reports
            (id,result_revision_id,revision_no,audience,created_at,c67_json)
            VALUES(%s,%s,1,'assessee',now()-interval '10 days','{}')""",
            (correction_report_id, correction_id))
        history = m8_results.list_owned_cycles(connection, 10)
        assert [item['cycle_id'] for item in history] == [str(previous_cycle), str(cycle_id), str(foreign_cycle)]
        corrected = history[1]
        assert corrected['program_name'] == 'Программа A'
        assert corrected['report_id'] == str(correction_report_id)
        assert len(corrected['versions']) == 2
        # The comparison endpoint orders by completion, even if a correction
        # makes its report revision appear at another creation time.
        previous_correction_revision, previous_correction_report = uuid4(), uuid4()
        connection.execute('INSERT INTO m8_result_revisions VALUES(%s,%s,2)',
                           (previous_correction_revision, previous_result))
        connection.execute("""INSERT INTO m8_reports
            (id,result_revision_id,revision_no,audience,created_at,c67_json)
            VALUES(%s,%s,1,'assessee',now()-interval '10 days','{}')""",
            (previous_correction_report, previous_correction_revision))
        connection.execute("UPDATE m5_cycles SET collection_closed_at=now() WHERE id=1")
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=22)
        assert not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=23)
        assert m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=21)
        pending_cycle, failed_cycle = uuid4(), uuid4()
        connection.execute("""INSERT INTO m5_cycles(id,cycle_id,owner_user_id,organization_id,
            personalized_profile_id,usage_scope,status,display_snapshot_json,collection_closed_at)
            VALUES(4,%s,11,1,500,'assessment','calculation_pending',
              '{"program_name":"Программа B"}'::jsonb,now()-interval '4 days'),
              (5,%s,11,1,500,'assessment','failed',
              '{"program_name":"Программа B"}'::jsonb,now()-interval '5 days')""",
            (pending_cycle, failed_cycle))
        page = m8_report_access.page_customer_reports(connection, user_id=21)
        assert page['total'] == 4 and page['items'][0]['program_name'] == 'Программа A'
        assert page['items'][0]['report_id'] == str(correction_report_id)
        assert len(page['items']) == 4 and page['organization_id'] == 1
        assert m8_report_access.page_customer_reports(connection, user_id=21, page_size=1, page=2)['items'][0]['cycle_id'] == str(previous_cycle)
        assert m8_report_access.page_customer_reports(connection, user_id=21, program='Программа B')['total'] == 3
        assert m8_report_access.page_customer_reports(connection, user_id=21, status='preparing')['items'][0]['report_id'] is None
        assert m8_report_access.page_customer_reports(connection, user_id=21, status='failed')['items'][0]['cycle_id'] == str(failed_cycle)
        assert m8_report_access.page_customer_reports(connection, user_id=21, query='Другой')['total'] == 2
        assert m8_report_access.page_customer_reports(connection, user_id=21, query='несуществующий')['total'] == 0
        with pytest.raises(PermissionError):
            m8_report_access.page_customer_reports(connection, user_id=21, organization_id=2)
        connection.execute('INSERT INTO m7_cycle_plans VALUES(1,1),(2,2),(3,3)')
        connection.execute("""INSERT INTO m7_plan_revisions VALUES
            (1,1,'{"pilot_plan_binding":{"contract":"m7_pilot_plan_binding/1","program_ref":{"id":701}}}'),
            (1,2,'{}'),
            (2,1,'{"pilot_plan_binding":{"contract":"m7_pilot_plan_binding/1","program_ref":{"id":702}}}'),
            (3,1,'{"pilot_plan_binding":{"contract":"m7_pilot_plan_binding/1","program_ref":{"id":701}}}')""")
        for version, expected in ((701, cycle_id), (702, previous_cycle)):
            exact = m8_report_access.page_customer_reports(connection, user_id=21, program_definition_id=version)
            assert [item['cycle_id'] for item in exact['items']] == [str(expected)]
        assert m8_report_access.page_customer_reports(connection, user_id=21, program_definition_id=999)['total'] == 0
        assert m8_report_access.page_customer_reports(connection, user_id=21)['total'] == 4

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
                         str(previous_correction_report): previous_cycle,
                         str(foreign_report): foreign_cycle}
        monkeypatch.setattr(routes.m8_results, 'read_report',
                            lambda _, rid: _report(rid, report_cycles[str(rid)]))
        monkeypatch.setattr(routes.m8_results, 'render_pdf', lambda *_: b'%PDF-synthetic')
        monkeypatch.setattr(routes.m8_report_comparison, 'render_comparison_pdf', lambda *_: b'%PDF-synthetic')
        app = FastAPI(); app.include_router(routes.router)
        with TestClient(app) as client:
            own = f'/users/assessment/m8/reports/{report_id}'
            admin = f'/users/admin/m8-access/reports/{report_id}'
            counts_before = tuple(connection.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                                  for table in ('m8_results', 'm8_result_revisions', 'm8_reports'))
            assert client.get(own).status_code == client.get(admin).status_code == 401
            client.cookies.set(routes.SESSION_COOKIE_NAME, 'owner')
            assert client.get('/users/assessment/m8/history').json()['reports_total'] == 3
            detail = client.get(own)
            assert detail.status_code == 200 and detail.json()['c67']['skills'][0]['score']['value'] == 0
            assert 'validator_trace' not in detail.text and 'profile_ref' not in detail.text
            assert detail.json()['c67']['contract'] == 'C-67'
            assert client.get(own + '/pdf').status_code == 200
            from Api.typst_pdf_renderer import TypstRenderError
            monkeypatch.setattr(routes.m8_results, 'render_pdf',
                                lambda *_: (_ for _ in ()).throw(TypstRenderError('PDF_RENDER_TIMEOUT')))
            failed_pdf = client.get(own + '/pdf')
            assert failed_pdf.status_code == 503
            assert 'Повторите скачивание' in failed_pdf.json()['detail']
            monkeypatch.setattr(routes.m8_results, 'render_pdf', lambda *_: b'%PDF-synthetic')
            assert client.get(own + '/pdf').status_code == 200
            comparison = own + '/comparison'
            assert client.get(comparison, params={'previous_report_id': str(previous_report)}).status_code == 200
            auto = client.get(comparison)
            assert auto.status_code == 200
            assert auto.json()['previous']['report_id'] == str(previous_correction_report)
            connection.execute('INSERT INTO m8_published_reports(cycle_db_id,report_id) VALUES(2,%s)',
                               (previous_report,))
            published = client.get(comparison)
            assert published.status_code == 200
            assert published.json()['previous']['report_id'] == str(previous_report)
            assert client.get(comparison, params={'previous_report_id': str(correction_report_id)}).status_code == 403
            assert client.get(own + '/comparison.pdf', params={'previous_report_id': str(previous_report)}).status_code == 200
            assert client.get(comparison, params={'previous_report_id': str(foreign_report)}).status_code == 403
            assert tuple(connection.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']
                         for table in ('m8_results', 'm8_result_revisions', 'm8_reports')) == counts_before
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


def test_support_report_readback_and_exact_access(test_database_url, monkeypatch):
    from Api import support_reports
    from Api.typst_pdf_renderer import TypstRenderError

    with psycopg.connect(test_database_url, row_factory=dict_row) as setup:
        schema = _schema(setup)
        setup.execute('CREATE TABLE users(id bigint PRIMARY KEY)')
        setup.execute('CREATE TABLE organizations(id bigint PRIMARY KEY,is_active boolean)')
        setup.execute('CREATE TABLE organization_memberships(organization_id bigint,user_id bigint,role text)')
        setup.execute('''CREATE TABLE m5_cycles(id bigint PRIMARY KEY,cycle_id uuid,organization_id bigint,
            usage_scope text,collection_closed_at timestamptz)''')
        setup.execute('''CREATE TABLE m10_pipeline_runs(cycle_db_id bigint,status text,stage text,
            updated_at timestamptz)''')
        setup.execute('CREATE TABLE m10_pipeline_revisions(cycle_db_id bigint,revision_no integer)')
        setup.execute('''CREATE TABLE preparation_observations(id bigint,source text,operation_id text,stage text,
            stage_started_at timestamptz)''')
        setup.execute('CREATE TABLE m8_results(id uuid PRIMARY KEY,cycle_db_id bigint)')
        setup.execute('''CREATE TABLE m8_result_revisions(id uuid PRIMARY KEY,results_id uuid,revision_no integer,
            payload_json jsonb,created_at timestamptz DEFAULT now())''')
        setup.execute('''CREATE TABLE m8_reports(id uuid PRIMARY KEY,result_revision_id uuid,revision_no integer,
            audience text,status text,created_at timestamptz DEFAULT now(),c67_json jsonb)''')
        setup.execute('CREATE TABLE m8_published_reports(cycle_db_id bigint,report_id uuid)')
        m8_report_access.ensure_schema(setup)
        setup.execute('INSERT INTO users VALUES(20),(21),(22),(23),(24)')
        setup.execute('INSERT INTO organizations VALUES(1,true),(2,true)')
        setup.execute("INSERT INTO organization_memberships VALUES(1,20,'admin'),(2,21,'admin')")
        ready, failed, delayed, no_result, foreign = [uuid4() for _ in range(5)]
        for db_id, cycle, org in ((1, ready, 1), (2, failed, 1), (3, delayed, 1),
                                  (4, no_result, 1), (5, foreign, 2)):
            setup.execute("""INSERT INTO m5_cycles VALUES
                (%s,%s,%s,'assessment',now()-interval '1 day')""", (db_id, cycle, org))
        setup.execute("""INSERT INTO m10_pipeline_runs VALUES
            (2,'failed','report_failed',now()),(3,'processing','assessment_queued',now()-interval '1 day')""")
        setup.execute('INSERT INTO m10_pipeline_revisions VALUES(2,7),(3,2)')
        old_report, current_report, no_result_report, foreign_report = [uuid4() for _ in range(4)]
        revisions = {}
        for db_id in (1, 2, 4, 5):
            result_id, revisions[db_id] = uuid4(), uuid4()
            setup.execute('INSERT INTO m8_results VALUES(%s,%s)', (result_id, db_id))
            setup.execute('INSERT INTO m8_result_revisions VALUES(%s,%s,1)', (revisions[db_id], result_id))
        for db_id, report_id, revision, c67 in (
            (1, old_report, 1, '{"skills":[{"outcome":"full_score"}]}'),
            (1, current_report, 2, '{"partial_result":{"is_incomplete":true},"skills":[{"outcome":"partial_score"}]}'),
            (4, no_result_report, 1, '{"skills":[{"outcome":"no_result"}],"partial_result":{"is_incomplete":true}}'),
            (5, foreign_report, 1, '{"skills":[{"outcome":"full_score"}]}'),
        ):
            setup.execute("""INSERT INTO m8_reports(id,result_revision_id,revision_no,audience,status,c67_json)
                VALUES(%s,%s,%s,'assessee','ready',%s::jsonb)""", (report_id, revisions[db_id], revision, c67))
        setup.execute('INSERT INTO m8_published_reports VALUES(1,%s)', (current_report,))
        setup.commit()

        @contextmanager
        def connect(*, read_only=False):
            with psycopg.connect(test_database_url, row_factory=dict_row, autocommit=True) as db:
                db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
                db.autocommit = False
                if read_only:
                    db.execute('SET TRANSACTION READ ONLY')
                yield db

        with connect(read_only=True) as db:
            queue = support_reports.list_problems(db, organization_id=1)
            assert [item['state'] for item in queue['items']] == ['delayed', 'failed']
            failure = support_reports.read(db, failed, report_id=None, user_id=23, can_recover=True)
            assert failure['results_revision_id'] == revisions[2] and failure['results_status'] == 'saved'
            assert failure['report_status'] == 'not_created' and failure['recovery_revision'] == 7

        monkeypatch.setattr(routes, 'get_connection', connect)
        monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
                            lambda token: SimpleNamespace(id=int(token)) if token else None)
        monkeypatch.setattr(routes, 'has_superadmin_access', lambda _db, user: user.id in {23, 24})
        monkeypatch.setattr(routes, 'has_platform_permission', lambda _db, user, _permission: user.id == 24)
        monkeypatch.setattr(routes, 'require_platform_permission',
                            lambda *_args: (_ for _ in ()).throw(PermissionError('configuration.publish')))
        monkeypatch.setattr(routes.m8_results, 'read_report', lambda _, rid: _report(rid, ready))
        monkeypatch.setattr(routes.m8_report_corrections, 'public_notice', lambda *_args: None)
        attempts = []

        def render(report):
            attempts.append(report['id'])
            if len(attempts) == 1:
                raise TypstRenderError('PDF_RENDER_TIMEOUT')
            return b'%PDF-synthetic'

        monkeypatch.setattr(routes.m8_results, 'render_pdf', render)
        app = FastAPI()
        app.include_router(routes.router)
        with TestClient(app) as client:
            support = '/users/admin/support/reports'
            ready_path = f'{support}/{ready}'
            exact_url = f'/users/admin/m8-access/reports/{old_report}'
            assert client.get(ready_path).status_code == 401
            for role in ('20', '21'):
                client.cookies.set(routes.SESSION_COOKIE_NAME, role)
                assert client.get(ready_path).status_code == 403
            client.cookies.set(routes.SESSION_COOKIE_NAME, '23')
            opened = client.get(ready_path)
            assert opened.headers['cache-control'] == 'no-store'
            assert opened.json()['report_id'] == str(current_report) and opened.json()['state'] == 'limited'
            assert opened.json()['report_revision'] == 2 and opened.json()['report_access'] == 'denied'
            assert 'skills' not in opened.text
            normal = client.get(f'{support}/{no_result}').json()
            assert normal['state'] == 'no_result' and normal['recovery_revision'] is None
            exact = client.get(ready_path, params={'report_id': str(old_report)}).json()
            assert exact['report_id'] == str(old_report) and exact['state'] == 'ready'
            mismatch = client.get(ready_path, params={'report_id': str(foreign_report)}).json()
            assert mismatch['report_id'] is None and mismatch['report_status'] == 'not_found'
            assert mismatch['requested_report_id'] == str(foreign_report)
            assert client.get(f'{support}/{uuid4()}').status_code == 404
            assert client.get(f'{support}/{failed}').json()['recovery_revision'] is None
            assert client.post(f'/users/admin/assessment/m8/cycles/{failed}/processing-recovery',
                               json={'idempotency_key': 'denied', 'expected_pipeline_revision': 7}).status_code == 403
            for denied in ('21', '23'):
                client.cookies.set(routes.SESSION_COOKIE_NAME, denied)
                assert client.get(exact_url).status_code == client.get(exact_url + '/pdf').status_code == 403
            client.cookies.set(routes.SESSION_COOKIE_NAME, '24')
            assert client.get(f'{support}/{failed}').json()['recovery_revision'] == 7
            client.cookies.set(routes.SESSION_COOKIE_NAME, '20')
            assert client.get(exact_url).json()['id'] == str(old_report)
            assert client.get(exact_url + '/pdf').status_code == 503
            assert client.get(exact_url + '/pdf').content == b'%PDF-synthetic'
            assert attempts == [str(old_report), str(old_report)]
            with connect() as db:
                db.execute('DELETE FROM organization_memberships WHERE organization_id=1 AND user_id=20')
            assert client.get(exact_url).status_code == client.get(exact_url + '/pdf').status_code == 403

        with connect(read_only=True) as db:
            assert db.execute('SELECT count(*) AS n FROM m8_reports').fetchone()['n'] == 4
            assert db.execute('SELECT count(*) AS n FROM m8_result_revisions').fetchone()['n'] == 4
            assert db.execute('SELECT count(*) AS n FROM m10_pipeline_revisions').fetchone()['n'] == 2
        setup.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        setup.commit()
