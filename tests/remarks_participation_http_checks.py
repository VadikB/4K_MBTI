"""Actual F01/F02 HTTP handlers; only synthetic inputs in a marker-owned stand.

The server has no background workers or provider credentials. Assignment sources
are the existing explicitly synthetic seed, not a new methodology approval.
No cookies, passwords, or state.json contents are exported as evidence.
"""
from __future__ import annotations

import hashlib
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import owned

if os.getenv('AGENT4K_ISOLATED_STAND') != '1':
    raise RuntimeError('OWNED_ISOLATED_STAND_REQUIRED')
state = json.loads(Path(os.environ['STAND_STATE']).read_text())
with owned(state):
    pass

from Api import assessment_assignment_sources
from Api.config import settings
from Api.database import close_connection_pool, get_connection
from Api.routes import SESSION_COOKIE_NAME
from Api.web_session_service import web_session_service

EVENTS = []
SNAPSHOTS = []


class Client:
    def __init__(self, base, token=None):
        self.base = base
        self.token = token

    def request(self, method, path, *, payload=None, params=None, expected=200, code=None):
        url = self.base + path + ('?' + urlencode(params) if params else '')
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Cookie'] = SESSION_COOKIE_NAME + '=' + self.token
        request = Request(url, method=method, headers=headers,
            data=json.dumps(payload).encode() if payload is not None else None)
        try:
            reply = urlopen(request, timeout=30)
        except HTTPError as failure:
            reply = failure
        with reply:
            status = reply.status
            data = json.loads(reply.read())
            for value in reply.headers.get_all('Set-Cookie', []):
                cookie = SimpleCookie(value)
                if SESSION_COOKIE_NAME in cookie:
                    self.token = cookie[SESSION_COOKIE_NAME].value
        detail_code = str(data.get('detail', '')).split(':', 1)[0]
        detail_code = detail_code if re.fullmatch('[A-Z][A-Z0-9_]+', detail_code) else None
        EVENTS.append({'method': method, 'path': path, 'status': status,
            'expected_status': expected, 'expected_code': code, 'detail_code': detail_code})
        assert status == expected, f'{method} {path}: expected {expected}, got {status}, code={detail_code}'
        if code:
            assert str(data.get('detail', '')).startswith(code), f'{method} {path}: wrong refusal code'
        return data


def snapshot():
    tables = ('organization_assessment_assignments', 'organization_assessment_source_bindings',
        'questionnaire_response_revisions', 'assessment_personalized_profiles', 'm5_cycles',
        'assessment_preparation_jobs', 'product_cycle_preparation_operations')
    with get_connection() as connection:
        result = {}
        for table in tables:
            rows = connection.execute(f'SELECT to_jsonb(t) AS row FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
            raw = json.dumps([row['row'] for row in rows], sort_keys=True, default=str).encode()
            result[table] = {'count': len(rows), 'sha256': hashlib.sha256(raw).hexdigest()}
        result['user_profile_selection'] = [dict(row) for row in connection.execute('''
            SELECT id,active_profile_id,selected_role_profile_version_id FROM users ORDER BY id''').fetchall()]
    return result


def assert_managed_guards(client, user_id, role_id):
    before = snapshot()
    paths = [
        ('GET', '/users/assessment/profile/options', None),
        ('PUT', '/users/role-profiles/selection', {'version_id': role_id}),
        ('POST', '/users/session/reopen-profile', None),
        ('POST', f'/users/{user_id}/assessment/start', None),
    ]
    for method, path, payload in paths:
        client.request(method, path, payload=payload, expected=409, code='W02_MANAGED_ASSIGNMENT:')
    after = snapshot()
    SNAPSHOTS.append({'context': 'managed_guards', 'user_id': user_id,
        'before': before, 'after': after, 'unchanged': before == after})
    assert before == after, 'managed refusal changed sources, profiles, assignments or Cycle'


def main(base):
    assert not settings.deepseek_api_keys and not settings.email_provider
    with get_connection() as connection:
        users = {row['email']: row['id'] for row in connection.execute('SELECT id,email FROM users').fetchall()}
        org = connection.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()['id']
        config = connection.execute("SELECT id FROM assessment_configurations WHERE code='e102_controlled_catalog'").fetchone()['id']
        role = connection.execute('''SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id
            WHERE r.code='specialist_expert' AND v.status='published' ''').fetchone()['id']
        student = connection.execute('''SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code='student' ''').fetchone()['id']
    member_id = users['participant@example.test']
    admin_id = users['other@example.test']
    superadmin = Client(base, web_session_service.create_session(users['superadmin@example.test']))
    member = Client(base)
    admin = Client(base)
    org_path = f'/users/admin/organizations/{org}'
    superadmin.request('POST', org_path + '/admins', payload={
        'email': 'other@example.test', 'full_name': 'Synthetic organization admin'})
    created = superadmin.request('POST', '/users/admin/organizations', payload={
        'code': 'remarks_control', 'name': 'Synthetic foreign control'})
    foreign_org = next(item['id'] for item in created['items'] if item['code'] == 'remarks_control')
    superadmin.request('POST', f'/users/admin/organizations/{foreign_org}/members', payload={
        'email': 'foreign-control@example.test', 'full_name': 'Synthetic control',
        'role_description': 'Synthetic position'})
    superadmin.request('POST', org_path + '/members', payload={
        'email': 'excluded-candidate@example.test', 'full_name': 'Synthetic excluded candidate',
        'role_description': 'Synthetic position'})
    with get_connection() as connection:
        candidate_id = connection.execute("SELECT id FROM users WHERE email='excluded-candidate@example.test'").fetchone()['id']
        detached_id = connection.execute('''INSERT INTO users(full_name,email)
            VALUES('Synthetic detached','detached-control@example.test') RETURNING id''').fetchone()['id']
        connection.commit()
    ref = 'remarks-participation-synthetic'
    preview = superadmin.request('POST', org_path + '/questionnaire/preview', expected=201, payload={
        'assignment_ref': ref, 'idempotency_key': 'remarks-questionnaire-synthetic', 'channel': 'csv',
        'csv_text': (ROOT / 'assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv').read_text()})
    superadmin.request('POST', org_path + f"/questionnaire/{preview['id']}/confirm", payload={'recipients': ['participant']})
    with get_connection() as connection:
        connection.execute('''INSERT INTO organization_assessment_pilot_bindings
            (organization_id,assignment_ref,binding_version,assessment_configuration_id,
             role_profile_version_id,configured_by_user_id)
            VALUES(%s,%s,'specialist-pilot/1',%s,%s,%s)''',
            (org, ref, config, role, users['superadmin@example.test']))
        connection.commit()
    assigned = superadmin.request('POST', org_path + '/assessment-assignments', payload={
        'user_ids': [member_id, admin_id], 'assignment_ref': ref, 'operation_id': 'remarks-initial-assign'})
    assert len(assigned['items']) == 2 and all(item['status'] == 'assigned' for item in assigned['items'])
    frozen = snapshot()
    for client, email, user_id in [(member, 'participant@example.test', member_id),
                                   (admin, 'other@example.test', admin_id)]:
        client.request('POST', '/users/auth/email/password-login', payload={'email': email, 'password': state['password']})
        assert_managed_guards(client, user_id, student)
        superadmin.request('DELETE', org_path + '/members', params={'email': email})
        assert_managed_guards(client, user_id, student)
        denied = superadmin.request('POST', org_path + '/assessment-assignments', payload={
            'user_ids': [user_id], 'assignment_ref': ref, 'operation_id': 'remarks-excluded-' + str(user_id)})
        assert denied['items'] == [{'user_id': user_id, 'status': 'not_assigned',
            'assignment_id': None, 'error': 'Участник не связан с этой активной организацией.'}]
        client.request('POST', '/users/auth/email/password-login', payload={'email': email, 'password': state['password']})
        client.request('GET', f'/users/{user_id}/session-bootstrap')
        client.request('GET', '/users/session/restore')
        with get_connection() as connection:
            membership = connection.execute('''SELECT role,is_participant FROM organization_memberships
                WHERE user_id=%s AND organization_id=%s''', (user_id, org)).fetchone()
            assert membership == {'role': 'member' if user_id == member_id else 'admin', 'is_participant': False}
            assert assessment_assignment_sources.has_managed_assignment(connection, user_id=user_id)
    superadmin.request('DELETE', org_path + '/members', params={'email': 'excluded-candidate@example.test'})
    excluded_frozen = snapshot()
    assert frozen == excluded_frozen, 'exclusion, login or denied assignment changed frozen assessment sources'
    SNAPSHOTS.append({'context': 'exclude_login_assign', 'before': frozen,
        'after': excluded_frozen, 'unchanged': True})
    listed = superadmin.request('GET', '/users/admin/organizations')
    organization = next(item for item in listed['items'] if item['id'] == org)
    assert organization['members_count'] == 0 and organization['members'] == []
    assert admin_id in [item['user_id'] for item in organization['admins']]
    assert {item['user_id'] for item in listed['excluded_accounts']} == {member_id, candidate_id}
    assert detached_id in [item['user_id'] for item in listed['detached_accounts']]
    assert admin_id not in [item['user_id'] for item in listed['detached_accounts']]
    assert member_id not in [item['user_id'] for item in listed['detached_accounts']]
    scoped = admin.request('GET', '/users/admin/organizations')
    assert [item['id'] for item in scoped['items']] == [org]
    assert scoped['excluded_accounts'] == [] and scoped['detached_accounts'] == []
    admin.request('GET', org_path + '/assessment-source-options')
    admin.request('POST', f'/users/admin/organizations/{foreign_org}/members', expected=403, payload={
        'email': 'forbidden@example.test', 'full_name': 'Synthetic forbidden', 'role_description': 'Synthetic position'})
    admin.request('GET', f'/users/admin/users/{candidate_id}/purge-preview', expected=403)
    superadmin.request('GET', f'/users/admin/users/{candidate_id}/purge-preview')
    for email, user_id in [('participant@example.test', member_id), ('other@example.test', admin_id),
                           ('excluded-candidate@example.test', candidate_id)]:
        superadmin.request('POST', org_path + '/members', payload={
            'email': email, 'full_name': 'Synthetic restored account', 'role_description': 'Synthetic position'})
        with get_connection() as connection:
            membership = connection.execute('''SELECT user_id,role,is_participant FROM organization_memberships
                WHERE user_id=%s AND organization_id=%s''', (user_id, org)).fetchone()
            assert membership == {'user_id': user_id,
                'role': 'admin' if user_id == admin_id else 'member', 'is_participant': True}
    restored = superadmin.request('GET', '/users/admin/organizations')
    assert restored['excluded_accounts'] == []
    assert next(item for item in restored['items'] if item['id'] == org)['members_count'] == 3
    assert snapshot() == frozen, 'reinclude changed immutable assignment/questionnaire/profile/Cycle state'
    # Removing authority from a participating admin keeps their participation.
    superadmin.request('DELETE', org_path + '/admins', params={'email': 'other@example.test'})
    with get_connection() as connection:
        assert connection.execute('''SELECT role,is_participant FROM organization_memberships
            WHERE user_id=%s''', (admin_id,)).fetchone() == {'role': 'member', 'is_participant': True}
        assert connection.execute('SELECT COUNT(*) AS n FROM organizations WHERE id=%s', (foreign_org,)).fetchone()['n'] == 1
        assert connection.execute("SELECT COUNT(*) AS n FROM users WHERE email='foreign-control@example.test'").fetchone()['n'] == 1


def run_http_checks(checker, *, evidence_file_env='REMARKS_PARTICIPATION_EVIDENCE',
                    contract='remarks-participation-http-pg/1'):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    result = 'FAIL'
    with tempfile.TemporaryFile() as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1',
            '--port', str(port), '--no-access-log', '--lifespan', 'off'], cwd=ROOT, stdout=log, stderr=log)
        try:
            base = f'http://127.0.0.1:{port}'
            deadline = time.monotonic() + 30
            while True:
                if server.poll() is not None:
                    raise RuntimeError('ISOLATED_HTTP_SERVER_EXITED')
                try:
                    with urlopen(base + '/health/ready', timeout=1) as health:
                        if health.status == 200:
                            break
                except (URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('ISOLATED_HTTP_SERVER_NOT_READY')
                time.sleep(.1)
            checker(base)
            result = 'PASS'
            print(contract + ' actual localhost HTTP/PostgreSQL PASS')
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            with get_connection() as connection:
                version = connection.execute('SELECT version() AS value').fetchone()['value']
            Path(os.environ[evidence_file_env]).write_text(json.dumps({
                'contract': contract, 'result': result,
                'synthetic_only': True, 'actual_http_socket': True, 'actual_postgresql': True,
                'database': os.environ['DB_NAME'], 'owner_verified': True,
                'postgresql': version, 'external_credentials_absent': not settings.deepseek_api_keys and not settings.email_provider,
                'events': EVENTS, 'snapshots': SNAPSHOTS,
            }, ensure_ascii=False, indent=2) + '\n')
            close_connection_pool()


if __name__ == '__main__':
    run_http_checks(main)
