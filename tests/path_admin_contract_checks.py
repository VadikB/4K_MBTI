"""Explicit child suite; real DB bootstrap required, no fake connection/resolver.

TestClient runs the actual ASGI router and real cookie-backed sessions. SQL seeds
are synthetic upstream inputs, NOT methodological approval or real AS admission.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.test_stand import owned

if os.getenv('AGENT4K_ISOLATED_STAND') != '1':
    raise RuntimeError('OWNED_ISOLATED_STAND_REQUIRED')
with owned(json.loads(Path(os.environ['STAND_STATE']).read_text())):
    pass

from Api import routes, assessment_programs
from Api.database import get_connection, close_connection_pool
from Api.web_session_service import web_session_service

pytestmark = pytest.mark.integration
app = FastAPI()
app.include_router(routes.router)
EVENTS = []
TABLES = (
    'organizations', 'users', 'organization_memberships', 'organization_email_domains',
    'organization_invitations', 'assessment_role_profiles', 'assessment_role_profile_versions',
    'organization_assessment_program_connections', 'assessment_program_definitions',
    'assessment_program_allowed_roles', 'organization_assessment_assignments',
    'organization_assessment_assignment_operations', 'organization_assessment_source_bindings',
    'questionnaire_response_revisions', 'assessment_organization_contexts',
    'assessment_organization_context_versions', 'm8_report_access_revisions',
    'm8_report_access_recipients',
    'assessment_personalized_profiles', 'participant_acquaintance_confirmations',
    'assessment_preparation_jobs', 'product_cycle_preparation_operations', 'm5_cycles',
)


@pytest.fixture(scope='session', autouse=True)
def persist_evidence():
    yield
    from Api.config import settings
    with get_connection() as c:
        activity = {table: c.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in (
            'm5_cycles', 'm5_assessment_situations', 'product_cycle_preparation_operations',
            'assessment_preparation_jobs', 'm5_generation_lab_runs', 'm5_equivalent_generation_operations')}
        pg_version = c.execute('SELECT version() AS value').fetchone()['value']
        isolation = c.execute('SHOW default_transaction_isolation').fetchone()['default_transaction_isolation']
    credentials_absent = not settings.deepseek_api_keys and not settings.email_provider
    Path(os.environ['PATH_ADMIN_EVIDENCE']).write_text(json.dumps({
        'contract': 'path_admin_http_pg/1', 'synthetic_only': True,
        'real_sessions': True, 'real_resolvers': True, 'real_postgresql': True,
        'database': os.environ['DB_NAME'], 'events': EVENTS,
        'runtime_activity': activity, 'external_credentials_absent': credentials_absent,
        'postgresql': pg_version, 'default_transaction_isolation': isolation,
    }, ensure_ascii=False, indent=2, default=str) + '\n')
    close_connection_pool()
    assert credentials_absent and all(n == 0 for n in activity.values())


def snapshot():
    with get_connection() as c:
        tables = {}
        for table in TABLES:
            if c.execute('SELECT to_regclass(%s) AS relation', (table,)).fetchone()['relation']:
                values = c.execute(f'SELECT to_jsonb(t) AS row FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
                raw = json.dumps([r['row'] for r in values], sort_keys=True, default=str).encode()
                tables[table] = {'count': len(values), 'sha256': hashlib.sha256(raw).hexdigest()}
        return tables


@contextmanager
def session(uid):
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set(routes.SESSION_COOKIE_NAME, web_session_service.create_session(uid))
        yield client


def no_write(client, method, path, *, status, detail=None, **kwargs):
    before = snapshot()
    reply = client.request(method, path, **kwargs)
    after = snapshot()
    EVENTS.append({'method': method, 'path': path, 'expected_status': status,
                   'status': reply.status_code, 'detail': reply.json().get('detail') if reply.status_code != 500 else 'Internal Server Error',
                   'before': before, 'after': after, 'unchanged': before == after})
    assert reply.status_code == status, reply.text
    if detail:
        assert reply.json()['detail'] == detail, reply.text
    assert after == before, 'denied command persisted domain changes'
    return reply


def create_scope():
    suffix = uuid4().hex[:12]
    with get_connection() as c:
        super_id = c.execute("SELECT id FROM users WHERE email='superadmin@example.test'").fetchone()['id']
        # The seeded catalog is tenant-scoped; use that tenant for positive bindings.
        org = c.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()['id']
        foreign = c.execute("INSERT INTO organizations(code,name) VALUES(%s,'Synthetic foreign') RETURNING id", ('foreign_' + suffix,)).fetchone()['id']
        ids = []
        for label, oid, role in [('admin', org, 'admin'), ('member', org, 'member'),
                                 ('second', org, 'member'), ('foreign', foreign, 'admin')]:
            uid = c.execute("INSERT INTO users(email,full_name) VALUES(%s,'Synthetic contract subject') RETURNING id",
                            (label + suffix + '@example.test',)).fetchone()['id']
            c.execute("INSERT INTO organization_memberships(organization_id,user_id,role,admission_source,admitted_at) VALUES(%s,%s,%s,'admin_add',NOW())", (oid, uid, role))
            ids.append(uid)
        config = dict(c.execute("SELECT * FROM assessment_configurations WHERE code='e102_controlled_catalog'").fetchone())
        role = c.execute("SELECT v.id FROM assessment_role_profile_versions v JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code='specialist_expert' AND v.status='published'").fetchone()['id']
        student = c.execute("SELECT v.id FROM assessment_role_profile_versions v JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code='student' AND v.status='published'").fetchone()['id']
        assignment_ref = 'ac0610-' + suffix
        code = 'synthetic-' + suffix
        sources = {'synthetic_test': 'AC06/07/09/10; not human review or pilot admission'}
        checksum = assessment_programs.definition_checksum(code=code, version='test.1', name='Synthetic test program',
            assignment_ref=assignment_ref, mode='dialogue', configuration_id=config['id'],
            catalog_version_id=config['catalog_version_id'], role_version_ids=[role], source_refs=sources)
        program = c.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,catalog_version_id,
             source_refs_json,definition_checksum,published_by_user_id,published_at)
            VALUES(%s,'test.1','Synthetic test program',%s,'dialogue','draft',%s,%s,%s::jsonb,%s,%s,NOW()) RETURNING id""",
            (code, assignment_ref, config['id'], config['catalog_version_id'], json.dumps(sources), checksum, super_id)).fetchone()['id']
        c.execute('INSERT INTO assessment_program_allowed_roles VALUES(%s,%s,0)', (program, role))
        c.execute("UPDATE assessment_program_definitions SET status='published' WHERE id=%s", (program,))
        c.commit()
    with session(super_id) as client:
        response = client.put(f'/users/admin/organizations/{org}/assessment-program', json={
            'program_definition_id': program, 'operation_id': 'connect-' + suffix})
        assert response.status_code == 200, response.text
    return dict(org=org, foreign=foreign, admin=ids[0], member=ids[1], second=ids[2],
                foreign_admin=ids[3], super=super_id, role=role, student=student,
                program=program, ref=assignment_ref, config=config)


@pytest.fixture
def scope():
    return create_scope()


def preview(client, s, *, ref=None, text=None, org=None):
    response = client.post(f"/users/admin/organizations/{org or s['org']}/questionnaire/preview", json={
        'assignment_ref': ref or s['ref'], 'source_author': 'Synthetic test customer — not human review',
        'idempotency_key': uuid4().hex, 'channel': 'csv',
        'csv_text': text or Path('assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv').read_text(),
    })
    assert response.status_code == 201, response.text
    return response.json()['id']


def confirm(client, s, revision):
    reply = client.post(f"/users/admin/organizations/{s['org']}/questionnaire/{revision}/confirm",
                        json={'recipients': ['participant']})
    assert reply.status_code == 200, reply.text
    assert reply.json()['status'] == 'confirmed'
    return reply.json()


def ready(client, s):
    return confirm(client, s, preview(client, s))


def payload(s, **changes):
    return {'user_ids': [s['member']], 'assignment_ref': s['ref'],
            'operation_id': 'assign-' + uuid4().hex, **changes}


def assignment_counts(s):
    with get_connection() as c:
        assignments = c.execute('SELECT id FROM organization_assessment_assignments WHERE organization_id=%s AND assignment_ref=%s', (s['org'], s['ref'])).fetchall()
        bindings = c.execute('''SELECT b.id,b.assignment_id FROM organization_assessment_source_bindings b
            JOIN organization_assessment_assignments a ON a.id=b.assignment_id WHERE a.organization_id=%s AND a.assignment_ref=%s''', (s['org'], s['ref'])).fetchall()
        cycles = c.execute('SELECT count(*) AS n FROM m5_cycles').fetchone()['n']
        return {'assignments': assignments, 'bindings': bindings, 'cycles': cycles}


def test_ac06_ordinary_admin_cannot_connect_or_mutate_foreign(scope):
    s = scope
    with session(s['admin']) as client:
        base = f"/users/admin/organizations/{s['foreign']}"
        no_write(client, 'PUT', f"/users/admin/organizations/{s['org']}/assessment-program", status=403,
                 detail='Superadmin access required', json={'program_definition_id': s['program'], 'operation_id': 'forbidden-connect'})
        no_write(client, 'PUT', base + '/assessment-program', status=403,
                 json={'program_definition_id': s['program'], 'operation_id': 'foreign-connect'})
        no_write(client, 'PATCH', base, status=403, json={'name': 'Forbidden overwrite'})
        no_write(client, 'POST', base + '/members', status=403, json={'email': 'forbidden@example.test',
                 'full_name': 'Synthetic forbidden', 'role_description': 'Synthetic position'})
        no_write(client, 'DELETE', base + '/members', status=403, params={'email': 'absent@example.test'})
        no_write(client, 'POST', base + '/admins', status=403, json={'email': 'forbidden-admin@example.test', 'full_name': 'Synthetic forbidden'})
        no_write(client, 'POST', base + '/domains', status=403, json={'domain': 'foreign.example.test'})
        no_write(client, 'DELETE', base + '/domains', status=403, params={'domain': 'foreign.example.test'})
        no_write(client, 'POST', base + '/assessment-assignments', status=403, json=payload(s))
        no_write(client, 'POST', base + '/questionnaire/preview', status=403, json={
            'assignment_ref': s['ref'], 'source_author': 'Synthetic', 'idempotency_key': 'foreign-preview',
            'channel': 'csv', 'csv_text': Path('assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv').read_text()})


def test_ac07_confirm_foreign_stale_and_exact_revision(scope):
    s = scope
    with session(s['admin']) as client:
        stale = preview(client, s)
        text = Path('assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv').read_text()
        current = preview(client, s, text=text.replace('Познакомиться с форматом оценки', 'Проверить текущую версию'))
        assert current != stale
        confirm(client, s, current)
        with get_connection() as c:
            confirmed = dict(c.execute('SELECT id,status,organization_context_version_id FROM questionnaire_response_revisions WHERE id=%s', (current,)).fetchone())
        no_write(client, 'POST', f"/users/admin/organizations/{s['org']}/questionnaire/{stale}/confirm",
                 status=409, detail='QUESTIONNAIRE_REVISION_CONFLICT', json={'recipients': ['participant']})
        # A real foreign revision, not an invented absent id.
        with session(s['foreign_admin']) as foreign:
            foreign_revision = preview(foreign, s, org=s['foreign'])
        no_write(client, 'POST', f"/users/admin/organizations/{s['org']}/questionnaire/{foreign_revision}/confirm",
                 status=409, detail='QUESTIONNAIRE_REVISION_NOT_FOUND', json={'recipients': ['participant']})
        no_write(client, 'POST', f"/users/admin/organizations/{s['foreign']}/questionnaire/{foreign_revision}/confirm",
                 status=403, json={'recipients': ['participant']})
        before = snapshot()
        confirm(client, s, current)
        with get_connection() as c:
            replay = dict(c.execute('SELECT id,status,organization_context_version_id FROM questionnaire_response_revisions WHERE id=%s', (current,)).fetchone())
        assert replay == confirmed
        assert snapshot() == before
        EVENTS.append({'criterion': 'AC07', 'exact_revision': current, 'stale_revision': stale,
                       'foreign_revision': foreign_revision, 'context_version': confirmed['organization_context_version_id'],
                       'positive_and_replay': 'PASS'})


@pytest.mark.parametrize('mode', ['lost_reply', 'same_key_concurrent', 'different_key_concurrent'])
def test_ac09_assignment_repeats_double_click_lost_reply_and_readback(scope, mode):
    s = scope
    concurrent = mode != 'lost_reply'
    with session(s['admin']) as client:
        ready(client, s)
    command = payload(s, user_ids=[s['member'], s['member']])
    url = f"/users/admin/organizations/{s['org']}/assessment-assignments"
    barrier = threading.Barrier(2)

    def click():
        with session(s['admin']) as client:
            if concurrent:
                barrier.wait(timeout=10)
            sent = {**command}
            if mode == 'different_key_concurrent':
                sent['operation_id'] = uuid4().hex
            reply = client.post(url, json=sent)
            assert reply.status_code == 200, reply.text
            return reply.json()['items'][0]

    if concurrent:
        with ThreadPoolExecutor(max_workers=2) as pool:
            answers = list(pool.map(lambda _: click(), range(2)))
    else:
        click()  # Deliberately discard the committed response (lost delivery).
        answers = [click()]
    assert len({r['assignment_id'] for r in answers}) == 1
    before = assignment_counts(s)
    assert len(before['assignments']) == len(before['bindings']) == 1 and before['cycles'] == 0
    # New session (reload), same operation and a new operation key for same intent.
    with session(s['admin']) as reloaded:
        for changed in ({}, {'operation_id': 'new-intent-' + uuid4().hex}):
            response = reloaded.post(url, json={**command, **changed})
            assert response.status_code == 200, response.text
            assert response.json()['items'][0]['assignment_id'] == before['assignments'][0]['id']
        for _ in range(2):
            response = reloaded.get('/users/admin/organizations')
            assert response.status_code == 200, response.text
    after = assignment_counts(s)
    assert after == before
    EVENTS.append({'criterion': 'AC09', 'mode': mode, 'concurrent': concurrent, 'lost_response': not concurrent,
                   'reload_and_repeat_readback': True, 'before': before, 'after': after})


@pytest.mark.parametrize('fault', ['late_domain_rejection', 'postgres_exception'])
def test_ac09_late_batch_failure_is_atomic(scope, fault):
    s = scope
    with session(s['admin']) as client:
        ready(client, s)
    # Real PostgreSQL exception in the SECOND binding, after first assignment+binding
    # have been inserted. This is an infrastructure fault, not fake Connection.
    with get_connection() as c:
        if fault == 'postgres_exception':
            c.execute('CREATE SEQUENCE ac09_fault_reached')
            c.execute("""CREATE FUNCTION ac09_fail_second_binding() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF EXISTS(SELECT 1 FROM organization_assessment_assignments a
                    WHERE a.id=NEW.assignment_id AND a.recipient_user_id=""" + str(s['second']) + """ )
                AND EXISTS(SELECT 1 FROM organization_assessment_source_bindings b
                    JOIN organization_assessment_assignments a ON a.id=b.assignment_id
                    WHERE a.recipient_user_id=""" + str(s['member']) + """ )
                THEN PERFORM nextval('ac09_fault_reached');
                  RAISE EXCEPTION 'AC09_SYNTHETIC_LATE_FAILURE'; END IF; RETURN NEW; END $$""")
            c.execute('CREATE TRIGGER ac09_late_failure BEFORE INSERT ON organization_assessment_source_bindings FOR EACH ROW EXECUTE FUNCTION ac09_fail_second_binding()')
        else:
            # Same published sources; frozen profile ownership triggers the real
            # bind() domain refusal for the second recipient, not a mocked error.
            from Api.assessment_contexts import (create_user_context_draft, confirm_user_context,
                                                 create_personalized_profile)
            user_context = create_user_context_draft(c, user_id=s['second'],
                identity={'full_name': 'Synthetic second subject'},
                professional={'position_or_status': 'Synthetic position'})
            confirm_user_context(c, version_id=user_context, user_id=s['second'])
            revision = c.execute('SELECT id,organization_context_version_id FROM questionnaire_response_revisions WHERE organization_id=%s AND assignment_ref=%s AND status=\'confirmed\'', (s['org'], s['ref'])).fetchone()
            profile = create_personalized_profile(c, user_id=s['second'],
                assessment_configuration_id=s['config']['id'], role_profile_version_id=s['role'],
                organization_context_version_id=revision['organization_context_version_id'],
                user_context_version_id=user_context)
            c.execute('''INSERT INTO participant_acquaintance_confirmations
                (user_id,organization_id,assignment_ref,questionnaire_revision_id,
                 question_schema_json,answers_json,answers_checksum,user_context_version_id,personalized_profile_id)
                SELECT %s,%s,%s,%s,question_schema_json,answers_json,answers_checksum,%s,%s
                FROM participant_acquaintance_confirmations ORDER BY id LIMIT 1''',
                (s['second'], s['org'], s['ref'], revision['id'], user_context, profile['id']))
        c.commit()
    try:
        with session(s['admin']) as client:
            response = no_write(client, 'POST', f"/users/admin/organizations/{s['org']}/assessment-assignments",
                status=500 if fault == 'postgres_exception' else 409,
                json=payload(s, user_ids=[s['member'], s['second']]))
            if fault == 'late_domain_rejection':
                assert response.json()['detail'].startswith('ASSIGNMENT_SOURCES_FROZEN:')
            else:
                with get_connection() as c:
                    reached = dict(c.execute('SELECT last_value,is_called FROM ac09_fault_reached').fetchone())
                EVENTS.append({'criterion': 'AC09', 'late_postgresql_fault_after_first_binding': reached})
                assert reached == {'last_value': 1, 'is_called': True}
    finally:
        if fault == 'postgres_exception':
            with get_connection() as c:
                c.execute('DROP TRIGGER ac09_late_failure ON organization_assessment_source_bindings')
                c.execute('DROP FUNCTION ac09_fail_second_binding()')
                c.execute('DROP SEQUENCE ac09_fault_reached')
                c.commit()


@pytest.mark.parametrize('invalid', ['retired_program', 'role', 'catalog_scope', 'assignment_scope',
    'questionnaire_missing', 'questionnaire_incomplete', 'source_selection', 'recipient_scope'])
def test_ac10_real_source_denials_leave_no_partial_rows(scope, invalid):
    s = scope
    with session(s['admin']) as client:
        if invalid != 'questionnaire_missing':
            if invalid == 'questionnaire_incomplete':
                preview(client, s, text='question_id,field,value\nC01,organization_type,company\n')
            else:
                ready(client, s)
        command = payload(s)
        expected = {
            'retired_program': 'PROGRAM_NOT_AVAILABLE_FOR_NEW_ASSIGNMENTS',
            'role': 'PROGRAM_ROLE_NOT_AVAILABLE', 'catalog_scope': 'PROGRAM_CATALOG_SCOPE_MISMATCH',
            'assignment_scope': 'PROGRAM_ASSIGNMENT_REF_MISMATCH',
            'questionnaire_missing': 'ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED',
            'questionnaire_incomplete': 'ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED',
            'source_selection': 'PROGRAM_SOURCE_SELECTION_STALE',
        }
        if invalid == 'retired_program':
            with get_connection() as c:
                c.execute("UPDATE assessment_program_definitions SET status='retired' WHERE id=%s", (s['program'],))
                c.commit()
        elif invalid == 'role':
            command['role_profile_version_id'] = s['student']
        elif invalid == 'catalog_scope':
            # Connect the SAME published program to a foreign tenant via actual
            # superadmin route. Its tenant-scoped catalog must not be assignable.
            with session(s['super']) as su:
                connected = su.put(f"/users/admin/organizations/{s['foreign']}/assessment-program", json={
                    'program_definition_id': s['program'], 'operation_id': uuid4().hex})
                assert connected.status_code == 200, connected.text
            with session(s['foreign_admin']) as foreign:
                foreign_scope = {**s, 'org': s['foreign']}
                ready(foreign, foreign_scope)
                no_write(foreign, 'POST', f"/users/admin/organizations/{s['foreign']}/assessment-assignments",
                         status=409, detail=expected[invalid], json=payload(s, user_ids=[s['foreign_admin']]))
            return
        elif invalid == 'assignment_scope':
            # Existing valid confirmed questionnaire, then connect a different
            # exact scope; assignment readiness must not bypass program scope.
            with get_connection() as c:
                row = c.execute('SELECT * FROM assessment_program_definitions WHERE id=%s', (s['program'],)).fetchone()
                checksum = assessment_programs.definition_checksum(code=row['code'], version='test.2',
                    name=row['name'], assignment_ref='other-scope', mode='dialogue',
                    configuration_id=row['assessment_configuration_id'], catalog_version_id=row['catalog_version_id'],
                    role_version_ids=[s['role']], source_refs={})
                c.execute("""INSERT INTO assessment_program_definitions
                    (code,version,name,assignment_ref,mode,status,assessment_configuration_id,catalog_version_id,
                     source_refs_json,definition_checksum) VALUES(%s,'test.2',%s,'other-scope','dialogue','draft',%s,%s,'{}',%s) RETURNING id""",
                    (row['code'], row['name'], row['assessment_configuration_id'], row['catalog_version_id'], checksum))
                other = c.execute('SELECT max(id) AS id FROM assessment_program_definitions').fetchone()['id']
                c.execute('INSERT INTO assessment_program_allowed_roles VALUES(%s,%s,0)', (other, s['role']))
                c.execute("UPDATE assessment_program_definitions SET status='published' WHERE id=%s", (other,))
                c.commit()
            with session(s['super']) as su:
                assert su.put(f"/users/admin/organizations/{s['org']}/assessment-program", json={
                    'program_definition_id': other, 'operation_id': uuid4().hex}).status_code == 200
        elif invalid == 'source_selection':
            command.update(assessment_configuration_id=s['config']['id'] + 100000,
                           role_profile_version_id=s['role'])
        elif invalid == 'recipient_scope':
            command['user_ids'] = [s['foreign_admin']]
            before = assignment_counts(s)
            response = client.post(f"/users/admin/organizations/{s['org']}/assessment-assignments", json=command)
            assert response.status_code == 200, response.text
            assert response.json()['items'][0]['status'] == 'not_assigned'
            assert assignment_counts(s) == before
            EVENTS.append({'criterion': 'AC10', 'invalid': invalid, 'status': 200,
                           'item_status': 'not_assigned', 'before': before, 'after': assignment_counts(s)})
            return
        no_write(client, 'POST', f"/users/admin/organizations/{s['org']}/assessment-assignments",
                 status=409, detail=expected[invalid], json=command)


@pytest.mark.parametrize('invalid', ['absent', 'draft', 'retired'])
def test_ac10_invalid_program_connection_is_atomic(scope, invalid):
    s = scope
    target = s['program']
    with get_connection() as c:
        if invalid == 'absent':
            target = 100000000
        elif invalid == 'retired':
            c.execute("UPDATE assessment_program_definitions SET status='retired' WHERE id=%s", (target,))
        else:
            target = c.execute("""INSERT INTO assessment_program_definitions
                (code,version,name,assignment_ref,mode,status,assessment_configuration_id,catalog_version_id,
                 source_refs_json,definition_checksum) VALUES(%s,'draft','Synthetic draft',%s,'dialogue','draft',%s,%s,'{}','synthetic-unpublished') RETURNING id""",
                ('draft-' + uuid4().hex, s['ref'], s['config']['id'], s['config']['catalog_version_id'])).fetchone()['id']
        c.commit()
    with session(s['super']) as client:
        no_write(client, 'PUT', f"/users/admin/organizations/{s['org']}/assessment-program", status=409,
                 detail='PROGRAM_NOT_AVAILABLE', json={'program_definition_id': target, 'operation_id': uuid4().hex})
