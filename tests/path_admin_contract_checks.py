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
from psycopg.errors import RaiseException
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
    'organization_assessment_assignment_operation_results',
    'questionnaire_response_revisions', 'assessment_organization_contexts',
    'assessment_organization_context_versions',
    'assessment_personalized_profiles', 'participant_acquaintance_confirmations',
    'assessment_preparation_jobs', 'product_cycle_preparation_operations', 'm5_cycles',
    'participant_data_issue_reports', 'participant_data_issue_replies', 'participant_data_issue_operations',
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


def create_scope(*, include_second_role=False):
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
        second_role = c.execute("""SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id
            WHERE r.code NOT IN ('student','specialist_expert') AND v.status='published'
              AND v.methodology_version='1.1' AND r.scope='base' ORDER BY v.id LIMIT 1""").fetchone()['id'] if include_second_role else None
        roles = [role, second_role] if second_role else [role]
        assignment_ref = 'ac0610-' + suffix
        code = 'synthetic-' + suffix
        sources = {'synthetic_test': 'AC06/07/09/10; not human review or pilot admission'}
        checksum = assessment_programs.definition_checksum(code=code, version='test.1', name='Synthetic test program',
            assignment_ref=assignment_ref, mode='dialogue', configuration_id=config['id'],
            catalog_version_id=config['catalog_version_id'], role_version_ids=roles, source_refs=sources)
        program = c.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,catalog_version_id,
             source_refs_json,definition_checksum,published_by_user_id,published_at)
            VALUES(%s,'test.1','Synthetic test program',%s,'dialogue','draft',%s,%s,%s::jsonb,%s,%s,NOW()) RETURNING id""",
            (code, assignment_ref, config['id'], config['catalog_version_id'], json.dumps(sources), checksum, super_id)).fetchone()['id']
        for ordinal, role_id in enumerate(roles):
            c.execute('INSERT INTO assessment_program_allowed_roles VALUES(%s,%s,%s)', (program, role_id, ordinal))
        c.execute("UPDATE assessment_program_definitions SET status='published' WHERE id=%s", (program,))
        c.commit()
    with session(super_id) as client:
        response = client.put(f'/users/admin/organizations/{org}/assessment-program', json={
            'program_definition_id': program, 'operation_id': 'connect-' + suffix})
        assert response.status_code == 200, response.text
    return dict(org=org, foreign=foreign, admin=ids[0], member=ids[1], second=ids[2],
                foreign_admin=ids[3], super=super_id, role=role, student=student,
                program=program, ref=assignment_ref, config=config, second_role=second_role)


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


def confirm_participant_profile(s, suffix=''):
    prefix = f"/users/{s['member']}/acquaintance"
    with session(s['member']) as client:
        current = client.get(prefix)
        assert current.status_code == 200, current.text
        consent = current.json()['readiness']['briefing']['consent_version']
        assert client.post(prefix + '/consent', json={'version': consent}).status_code == 200
        answers = client.put(prefix + '/answers', json={'confirm': True, 'answers': {
            'answer_1': 'Синтетические задачи' + suffix, 'answer_2': 'Синтетические решения',
            'answer_3': 'Синтетические ограничения'}})
        assert answers.status_code == 200, answers.text
        resolved = client.post(prefix + '/resolve-profile')
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()['late_readiness']['status'] == 'ready_to_prepare', resolved.text
        return resolved.json()['late_readiness']['personalized_profile_id']


@pytest.mark.parametrize('sources', ['same', 'revision', 'role'])
def test_adm_fix02_reassignment_keeps_command_and_profile_history(sources):
    s = create_scope(include_second_role=sources == 'role')
    base = f"/users/admin/organizations/{s['org']}/assessment-assignments"
    command_a = payload(s, role_profile_version_id=s['role'])
    with session(s['admin']) as client:
        ready(client, s)
        response_a = client.post(base, json=command_a)
        assert response_a.status_code == 200, response_a.text
        result_a = response_a.json()
        a_id = result_a['items'][0]['assignment_id']
    profile_a = confirm_participant_profile(s)
    with get_connection() as c:
        frozen_profile = dict(c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s', (profile_a,)).fetchone())
        frozen_confirmations = c.execute('SELECT * FROM participant_acquaintance_confirmations WHERE personalized_profile_id=%s ORDER BY id', (profile_a,)).fetchall()
        frozen_binding = c.execute('SELECT * FROM organization_assessment_source_bindings WHERE assignment_id=%s', (a_id,)).fetchall()
    with session(s['admin']) as client:
        cancelled = client.post(base + f'/{a_id}/cancel', json={'operation_id': uuid4().hex})
        assert cancelled.status_code == 200, cancelled.text
        if sources == 'revision':
            text = Path('assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv').read_text()
            confirm(client, s, preview(client, s, text=text.replace('Познакомиться с форматом оценки', 'Повторная синтетическая оценка')))
        command_b = payload(s, role_profile_version_id=s['second_role'] if sources == 'role' else s['role'])
        response_b = client.post(base, json=command_b)
        assert response_b.status_code == 200, response_b.text
        result_b = response_b.json()
        b_id = result_b['items'][0]['assignment_id']
        assert b_id != a_id
        for command, expected in ((command_a, result_a), (command_b, result_b)):
            assert client.post(base, json=command).json() == expected
            recovered = client.get(base + '/operations/' + command['operation_id'], params={
                'assignment_ref': s['ref'], 'user_ids': str(s['member']),
                'role_profile_version_id': command['role_profile_version_id']})
            assert recovered.status_code == 200, recovered.text
            assert recovered.json() == expected
    with session(s['member']) as client:
        waiting = client.get(f"/users/{s['member']}/acquaintance")
        assert waiting.status_code == 200
        assert waiting.json()['late_readiness']['status'] != 'ready_to_prepare'
        assert waiting.json()['late_readiness']['personalized_profile_id'] is None
        assert waiting.json()['mandatory_complete'] is False
        assert waiting.json()['state']['answers_confirmed_at'] is None
    from Api.acquaintance import preparation_scope
    with get_connection() as c, pytest.raises(ValueError, match='W02_'):
        preparation_scope(c, user_id=s['member'], profile_id=profile_a)
    profile_b = confirm_participant_profile(s, ' для Б')
    assert profile_b != profile_a
    with get_connection() as c:
        assert dict(c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s', (profile_a,)).fetchone()) == frozen_profile
        assert c.execute('SELECT * FROM participant_acquaintance_confirmations WHERE personalized_profile_id=%s ORDER BY id', (profile_a,)).fetchall() == frozen_confirmations
        assert c.execute('SELECT * FROM organization_assessment_source_bindings WHERE assignment_id=%s', (a_id,)).fetchall() == frozen_binding
        bound = c.execute('SELECT * FROM organization_assessment_source_bindings WHERE assignment_id=%s', (b_id,)).fetchone()
        assert (bound['questionnaire_revision_id'] != frozen_binding[0]['questionnaire_revision_id']) == (sources == 'revision')
        assert bound['role_profile_version_id'] == command_b['role_profile_version_id']
    EVENTS.append({'criterion':'ADM-FIX-02', 'sources': sources, 'assignment_a':a_id,
                   'assignment_b':b_id, 'immutable_history':True, 'exact_receipts':True})


def test_adm_fix02_partial_receipt_is_immutable_and_actor_scoped(scope):
    s = scope
    base = f"/users/admin/organizations/{s['org']}/assessment-assignments"
    command = payload(s, user_ids=[s['member'],s['foreign_admin']], role_profile_version_id=s['role'])
    params = {'assignment_ref':s['ref'], 'user_ids':','.join(map(str, command['user_ids'])),
              'role_profile_version_id':s['role']}
    with session(s['admin']) as client:
        ready(client, s)
        first = client.post(base, json=command)
        assert first.status_code == 200, first.text
        items = {item['user_id']:item for item in first.json()['items']}
        assert items[s['member']]['status'] == 'assigned'
        assert items[s['foreign_admin']]['status'] == 'not_assigned'
        assert items[s['foreign_admin']]['reason_code'] == 'ASSIGNMENT_RECIPIENT_NOT_ELIGIBLE'
        with get_connection() as c:
            c.execute('UPDATE organization_memberships SET is_participant=FALSE WHERE organization_id=%s AND user_id=%s', (s['org'],s['member']))
            c.commit()
        assert client.post(base, json=command).json() == first.json()
        assert client.get(base+'/operations/'+command['operation_id'], params=params).json() == first.json()
        for changed in ({'user_ids':str(s['member'])}, {'role_profile_version_id':s['student']},
                        {'assessment_configuration_id':s['config']['id']}):
            assert client.get(base+'/operations/'+command['operation_id'], params={**params,**changed}).status_code == 409
        assert client.post(base, json={**command, 'user_ids':[s['member']]}).status_code == 409
        with get_connection() as c:
            c.execute("UPDATE organization_memberships SET role='member' WHERE organization_id=%s AND user_id=%s", (s['org'],s['admin']))
            c.commit()
        assert client.get(base+'/operations/'+command['operation_id'], params=params).status_code == 403
        assert client.post(base, json=command).status_code == 403
    for actor, expected in ((s['super'],404),(s['foreign_admin'],403)):
        with session(actor) as client:
            assert client.get(base+'/operations/'+command['operation_id'], params=params).status_code == expected
    with get_connection() as c:
        assert c.execute('SELECT COUNT(*) AS n FROM organization_assessment_assignment_operation_results WHERE organization_id=%s AND actor_user_id=%s AND operation_id=%s',
                         (s['org'],s['admin'],command['operation_id'])).fetchone()['n'] == 1
        with pytest.raises(RaiseException, match='immutable'), c.transaction():
            c.execute("UPDATE organization_assessment_assignment_operation_results SET result_json='{}' WHERE operation_id=%s", (command['operation_id'],))
        with pytest.raises(RaiseException, match='immutable'), c.transaction():
            c.execute('DELETE FROM organization_assessment_assignment_operation_results WHERE operation_id=%s', (command['operation_id'],))


def test_adm_fix02_legacy_confirmation_preserves_exact_frozen_profile(scope):
    from Api import acquaintance, assessment_contexts as contexts
    s = scope
    with session(s['admin']) as client:
        ready(client, s)
        assigned = client.post(f"/users/admin/organizations/{s['org']}/assessment-assignments", json=payload(s))
        assert assigned.status_code == 200, assigned.text
    # Synthetic pre-upgrade confirmation with the former JSON shape, produced
    # through the real M4 lifecycle. No existing snapshot/checksum is rewritten.
    with get_connection() as c:
        readiness = acquaintance.early_readiness(c, user_id=s['member'])
        acquaintance.accept_consent(c, user_id=s['member'], version=readiness['briefing']['consent_version'])
        answers = {'answer_1':'Синтетические задачи', 'answer_2':'Синтетические решения',
                   'answer_3':'Синтетические ограничения'}
        acquaintance.save_answers(c, user_id=s['member'], answers=answers, confirm=True)
        saved = c.execute('SELECT * FROM participant_acquaintance_confirmations WHERE user_id=%s ORDER BY id DESC LIMIT 1', (s['member'],)).fetchone()
        legacy_answers = {key:value for key,value in saved['answers_json'].items() if key != 'assignment_id'}
        context_id = contexts.create_user_context_draft(c, user_id=s['member'],
            identity={'full_name':'Synthetic contract subject'}, professional={
                'regular_tasks':answers['answer_1'], 'decision_situations':answers['answer_2'],
                'constraints_and_interactions':answers['answer_3'], 'acquaintance_answers':legacy_answers})
        contexts.confirm_user_context(c, version_id=context_id, user_id=s['member'])
        profile = contexts.create_personalized_profile(c, user_id=s['member'],
            assessment_configuration_id=s['config']['id'], role_profile_version_id=s['role'],
            organization_context_version_id=readiness['organization_context_version_id'], user_context_version_id=context_id)
        legacy = c.execute('''INSERT INTO participant_acquaintance_confirmations
            (user_id,organization_id,assignment_ref,questionnaire_revision_id,question_schema_json,
             answers_json,answers_checksum,user_context_version_id,personalized_profile_id)
            VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING *''',
            (s['member'],s['org'],s['ref'],readiness['questionnaire_revision_id'],json.dumps(saved['question_schema_json']),
             json.dumps(legacy_answers),acquaintance._checksum(legacy_answers),context_id,profile['id'])).fetchone()
        frozen = dict(c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s', (profile['id'],)).fetchone())
        c.commit()
    with session(s['member']) as client:
        reply = client.post(f"/users/{s['member']}/acquaintance/resolve-profile")
        assert reply.status_code == 200, reply.text
        assert reply.json()['late_readiness']['personalized_profile_id'] == profile['id'], reply.text
    with get_connection() as c:
        assert dict(c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s', (profile['id'],)).fetchone()) == frozen
        assert dict(c.execute('SELECT * FROM participant_acquaintance_confirmations WHERE id=%s', (legacy['id'],)).fetchone()) == dict(legacy)


def test_adm_fix02_receipt_failure_rolls_back_all_effects(scope):
    s = scope
    base = f"/users/admin/organizations/{s['org']}/assessment-assignments"
    with session(s['admin']) as client:
        ready(client, s)
    with get_connection() as c:
        c.execute('''CREATE FUNCTION adm_fix02_fail_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'ADM_FIX02_SYNTHETIC_RECEIPT_FAILURE'; END $$''')
        c.execute('''CREATE TRIGGER adm_fix02_fail_receipt BEFORE INSERT
            ON organization_assessment_assignment_operation_results
            FOR EACH ROW EXECUTE FUNCTION adm_fix02_fail_receipt()''')
        c.commit()
    try:
        with session(s['admin']) as client:
            no_write(client, 'POST', base, status=500, json=payload(s))
    finally:
        with get_connection() as c:
            c.execute('DROP TRIGGER adm_fix02_fail_receipt ON organization_assessment_assignment_operation_results')
            c.execute('DROP FUNCTION adm_fix02_fail_receipt()')
            c.commit()


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
    if mode == 'same_key_concurrent':
        assert answers[0] == answers[1]
    with get_connection() as c:
        assert c.execute('SELECT COUNT(*) AS n FROM organization_assessment_assignment_operation_results WHERE organization_id=%s AND actor_user_id=%s',
            (s['org'],s['admin'])).fetchone()['n'] == (2 if mode == 'different_key_concurrent' else 1)
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
            # A profile freezes its exact existing assignment. A confirmation of
            # an older generation alone must not reject a new assignment.
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
            assignment_id = c.execute('''INSERT INTO organization_assessment_assignments
                (organization_id,recipient_user_id,assignment_ref,created_by_user_id,
                 questionnaire_revision_id,status,operation_id,request_fingerprint)
                VALUES(%s,%s,%s,%s,%s,'active',%s,'synthetic-frozen-assignment') RETURNING id''',
                (s['org'], s['second'], s['ref'], s['admin'], revision['id'], uuid4().hex)).fetchone()['id']
            from Api.assessment_assignment_sources import bind
            bind(c, assignment_id=assignment_id, organization_id=s['org'],
                configuration_id=s['config']['id'], role_version_id=s['role'],
                questionnaire_revision_id=revision['id'], actor_user_id=s['admin'], operation_id=uuid4().hex)
            c.execute('''INSERT INTO participant_acquaintance_confirmations
                (user_id,organization_id,assignment_ref,questionnaire_revision_id,
                 question_schema_json,answers_json,answers_checksum,user_context_version_id,personalized_profile_id)
                SELECT %s,%s,%s,%s,question_schema_json,answers_json,answers_checksum,%s,%s
                FROM participant_acquaintance_confirmations ORDER BY id LIMIT 1''',
                (s['second'], s['org'], s['ref'], revision['id'], user_context, profile['id']))
        c.commit()
    if fault == 'late_domain_rejection':
        with session(s['admin']) as client:
            text = Path('assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv').read_text()
            fresh = preview(client, s, text=text.replace('Познакомиться с форматом оценки', 'Новая редакция для проверки атомарности'))
            confirm(client, s, fresh)
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


def test_adm_fix03_stale_screen_cannot_retarget_appeal():
    s = create_scope()
    base = f"/users/admin/organizations/{s['org']}/assessment-assignments"
    prefix = f"/users/{s['member']}/acquaintance"
    with session(s['admin']) as admin:
        ready(admin, s)
        first = admin.post(base, json=payload(s, role_profile_version_id=s['role']))
        assert first.status_code == 200, first.text
        a_id = first.json()['items'][0]['assignment_id']
    with session(s['member']) as member:
        shown = member.get(prefix).json()['readiness']
        command = {'message': 'Synthetic appeal', 'operation_id': str(uuid4()),
                   'assignment_id': shown['assignment_id'],
                   'questionnaire_revision_id': shown['questionnaire_revision_id']}
        accepted = member.post(prefix + '/issues', json=command)
        assert accepted.status_code == 201, accepted.text
        receipt = accepted.json()
        assert member.get(prefix).json()['late_readiness']['personalized_profile_id'] is None
        assert member.get(prefix + '/issues').json()['items'][0]['assessment_display_name'] == s['config']['name']
        assert member.post(prefix + '/issues', json={**command, 'operation_id': str(uuid4()),
            'questionnaire_revision_id': shown['questionnaire_revision_id'] + 100000}).status_code == 409
        assert member.post(prefix + '/issues', json={**command, 'operation_id': str(uuid4()),
            'assignment_id': a_id + 100000}).status_code == 409
    with session(s['admin']) as admin:
        assert admin.post(base + f'/{a_id}/cancel', json={'operation_id': uuid4().hex}).status_code == 200
        second = admin.post(base, json=payload(s, role_profile_version_id=s['role']))
        assert second.status_code == 200, second.text
        b_id = second.json()['items'][0]['assignment_id']
        assert b_id != a_id
    with session(s['member']) as member:
        response = member.post(prefix + '/issues', json={
            'message': 'Synthetic stale screen', 'operation_id': str(uuid4()),
            'assignment_id': shown['assignment_id'],
            'questionnaire_revision_id': shown['questionnaire_revision_id'],
        })
    with get_connection() as c:
        rows = c.execute('SELECT assignment_id,questionnaire_revision_id FROM participant_data_issue_reports WHERE user_id=%s', (s['member'],)).fetchall()
    assert response.status_code == 409, (response.text, rows, {'shown': a_id, 'current': b_id})
    assert len(rows) == 1 and rows[0]['assignment_id'] == a_id
    with session(s['member']) as member:
        assert member.post(prefix + '/issues', json=command).json() == receipt
        lookup = prefix + '/issues/operations/' + command['operation_id']
        pair = {key: command[key] for key in ('assignment_id', 'questionnaire_revision_id')}
        assert member.get(lookup, params=pair).json() == receipt
        assert member.get(lookup, params={**pair, 'assignment_id': b_id}).status_code == 409
        assert member.get(prefix + '/issues/operations/' + str(uuid4()), params=pair).status_code == 404
        assert member.post(prefix + '/issues', json={**command, 'message': 'changed'}).status_code == 409
        assert member.post(prefix + '/issues', json={'message': command['message']}).status_code == 409
        current = member.get(prefix).json()['readiness']
        second_command = {**command, 'operation_id': str(uuid4()),
            'assignment_id': current['assignment_id'],
            'questionnaire_revision_id': current['questionnaire_revision_id']}
        second_receipt = member.post(prefix + '/issues', json=second_command)
        assert second_receipt.status_code == 201, second_receipt.text
        assert second_receipt.json()['id'] != receipt['id']
        assert second_receipt.json()['assignment_id'] == b_id
    with session(s['second']) as member:
        assert member.get(lookup, params=pair).status_code == 403
        assert member.get(lookup.replace(str(s['member']) + '/acquaintance', str(s['second']) + '/acquaintance'), params=pair).status_code == 404
        assert member.get(prefix + '/issues').status_code == 403
    issue_list = f"/users/admin/organizations/{s['org']}/members/{s['member']}/issues"
    issue_base = f"{issue_list}/{receipt['id']}"
    with session(s['foreign_admin']) as foreign:
        assert foreign.get(lookup, params=pair).status_code == 403
        assert foreign.get(issue_list).status_code == 403
        assert foreign.post(issue_base + '/claim').status_code == 403
        assert foreign.post(issue_base + '/reply', json={'message': 'Foreign reply'}).status_code == 403
    with session(s['admin']) as admin:
        roster = admin.get('/users/admin/organizations')
        assert roster.status_code == 200, roster.text
        organization = next(item for item in roster.json()['items'] if item['id'] == s['org'])
        counts = {member['user_id']: member['issue_count'] for member in organization['members']}
        assert counts[s['member']] == 2 and counts[s['second']] == 0
        assert admin.post(issue_base + '/claim').status_code == 200
        reply = admin.post(issue_base + '/reply', json={'message': 'Synthetic reply'})
        assert reply.status_code == 200, reply.text
        assert admin.post(issue_base + '/reply', json={'message': 'Synthetic reply'}).json() == reply.json()
    with session(s['member']) as member:
        items = member.get(prefix + '/issues').json()['items']
        item = next(item for item in items if item['id'] == receipt['id'])
        assert item['reply_author_display_name'] == 'Synthetic contract subject'
        assert item['replied_at'] == reply.json()['created_at']
        assert item['reply_message'] == 'Synthetic reply'
        assert item['assessment_display_name'] == s['config']['name']
        assert 'reply_author_user_id' not in item
        assert member.get(lookup, params=pair).json() == receipt
    with get_connection() as c:
        assert c.execute('SELECT count(*) AS n FROM participant_data_issue_operations WHERE user_id=%s', (s['member'],)).fetchone()['n'] == 2
        assert c.execute('SELECT count(*) AS n FROM participant_data_issue_reports WHERE user_id=%s', (s['member'],)).fetchone()['n'] == 2
