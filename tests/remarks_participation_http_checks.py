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
CONFIGURED_EMAIL = 'configured-only@example.test'
CONFIGURED_ORGANIZATION = 'remarks_configured'


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


def table_snapshot(connection, tables):
    result = {}
    for table in tables:
        rows = connection.execute(f'SELECT to_jsonb(t) AS row FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
        raw = json.dumps([row['row'] for row in rows], sort_keys=True, default=str).encode()
        result[table] = {'count': len(rows), 'sha256': hashlib.sha256(raw).hexdigest()}
    return result


def snapshot():
    tables = ('organization_assessment_assignments', 'organization_assessment_source_bindings',
        'questionnaire_response_revisions', 'assessment_personalized_profiles', 'm5_cycles',
        'assessment_preparation_jobs', 'product_cycle_preparation_operations')
    with get_connection() as connection:
        result = table_snapshot(connection, tables)
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


def assert_configured_admin_login_after_revoke(base, superadmin):
    from Api.auth_service import _hash_password

    with get_connection() as connection:
        user_id = connection.execute('INSERT INTO users(email,full_name) VALUES(%s,%s) RETURNING id',
            (CONFIGURED_EMAIL, 'Synthetic configured admin')).fetchone()['id']
        salt, digest = _hash_password(state['password'])
        connection.execute("""INSERT INTO auth_password_credentials(user_id,email,password_hash,password_salt)
            VALUES(%s,%s,%s,%s)""", (user_id, CONFIGURED_EMAIL, digest, salt))
        connection.commit()
    login = '/users/auth/email/password-login'
    credentials = {'email': CONFIGURED_EMAIL, 'password': state['password']}
    configured = Client(base)
    configured.request('POST', login, payload=credentials)
    listed = configured.request('GET', '/users/admin/organizations')
    (org,) = listed['items']
    assert org['code'] == CONFIGURED_ORGANIZATION
    assert [item['is_participant'] for item in org['admins']] == [False]
    admins = f"/users/admin/organizations/{org['id']}/admins"
    changed = superadmin.request('DELETE', admins, params={'email': CONFIGURED_EMAIL})
    assert next(item for item in changed['items'] if item['id'] == org['id'])['admins'] == []
    Client(base).request('POST', login, payload=credentials, expected=403)
    with get_connection() as connection:
        assert connection.execute('SELECT role FROM organization_memberships WHERE user_id=%s',
            (user_id,)).fetchone() is None
        assert connection.execute('SELECT email FROM auth_password_credentials WHERE user_id=%s',
            (user_id,)).fetchone()['email'] == CONFIGURED_EMAIL
        assert connection.execute("""SELECT reason FROM configured_access_suppressions
            WHERE email=%s AND access_kind='organization_admin' AND organization_code=%s""",
            (CONFIGURED_EMAIL, CONFIGURED_ORGANIZATION)).fetchone()['reason'] == 'superadmin_revoke'
    superadmin.request('POST', admins, payload={'email': CONFIGURED_EMAIL})
    restored = Client(base)
    restored.request('POST', login, payload=credentials)
    assert [item['id'] for item in restored.request('GET', '/users/admin/organizations')['items']] == [org['id']]


def assert_superadmin_self_grant_refused(superadmin, actor_id, organization_id):
    alias = 'superadmin-verified-alias@example.test'
    tables = ('users', 'user_identities', 'organization_memberships', 'user_platform_roles',
        'platform_role_permissions', 'configured_access_suppressions', 'configured_organization_membership_suppressions')
    url = f'/users/admin/organizations/{organization_id}/admins'
    with get_connection() as connection:
        email = connection.execute('SELECT email FROM users WHERE id=%s', (actor_id,)).fetchone()['email']
        org_code = connection.execute('SELECT code FROM organizations WHERE id=%s', (organization_id,)).fetchone()['code']
        connection.execute("""INSERT INTO user_identities
            (user_id,provider,provider_subject,email,is_primary,is_verified,verified_at)
            VALUES(%s,'email_magic_link',%s,%s,FALSE,TRUE,NOW())""", (actor_id, alias, alias))
        for address in (email, alias):
            connection.execute("""INSERT INTO configured_access_suppressions
                (email,access_kind,organization_code,reason,created_by_user_id)
                VALUES(%s,'organization_admin',%s,'superadmin_revoke',%s)""", (address, org_code, actor_id))
        connection.execute("""INSERT INTO configured_organization_membership_suppressions
            (user_id,organization_id,reason,created_by_user_id)
            VALUES(%s,%s,'superadmin_revoke',%s)""", (actor_id, organization_id, actor_id))
        connection.commit()
        before = table_snapshot(connection, tables)

    for case, address, code in (
        ('session_email', email, None),
        ('normalized_session_email', f'  {email.upper()}  ', None),
        ('linked_email', alias, 'ADMIN_EMAIL_ALREADY_LINKED'),
    ):
        superadmin.request('POST', url, payload={'email': address, 'full_name': 'Synthetic AC6 attempt'},
            expected=409, code=code)
        with get_connection() as connection:
            after = table_snapshot(connection, tables)
        SNAPSHOTS.append({'context': 'ac6_superadmin_self_grant_refused', 'case': case,
            'before': before, 'after': after, 'unchanged': before == after})
        assert after == before, f'AC6 {case} changed account, roles, memberships or suppressions'

    colleague = 'ac6-colleague@example.test'
    granted = superadmin.request('POST', url, payload={'email': colleague, 'full_name': 'Synthetic AC6 colleague'})
    assert granted['is_superadmin'] is True
    org = next(item for item in granted['items'] if item['id'] == organization_id)
    assert [(item['email'], item['is_participant']) for item in org['admins']] == [(colleague, False)]
    with get_connection() as connection:
        assert connection.execute("""SELECT m.role,m.is_participant FROM organization_memberships m
            JOIN users u ON u.id=m.user_id WHERE m.organization_id=%s AND u.email=%s""",
            (organization_id, colleague)).fetchone() == {'role': 'admin', 'is_participant': False}


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
        superadmin.request('DELETE', org_path + '/members', params={'email': email},
            expected=410, code='MEMBER_EXCLUSION_REMOVED_USE_ACCOUNT_PURGE')
        with get_connection() as connection:
            membership = connection.execute('''SELECT role,is_participant FROM organization_memberships
                WHERE user_id=%s AND organization_id=%s''', (user_id, org)).fetchone()
            assert membership == {'role': 'member' if user_id == member_id else 'admin', 'is_participant': True}
            assert assessment_assignment_sources.has_managed_assignment(connection, user_id=user_id)
    assert snapshot() == frozen, 'removed exclusion endpoint mutated frozen assessment sources'
    SNAPSHOTS.append({'context': 'removed_exclusion_preserves_managed_sources', 'before': frozen,
        'after': snapshot(), 'unchanged': True})
    listed = superadmin.request('GET', '/users/admin/organizations')
    assert 'excluded_accounts' not in listed and 'detached_accounts' not in listed
    organization = next(item for item in listed['items'] if item['id'] == org)
    assert organization['members_count'] == 3
    assert admin_id in [item['user_id'] for item in organization['admins']]
    scoped = admin.request('GET', '/users/admin/organizations')
    assert [item['id'] for item in scoped['items']] == [org]
    assert scoped['purge_preview_available'] is True
    assert 'excluded_accounts' not in scoped and 'detached_accounts' not in scoped
    admin.request('GET', org_path + '/assessment-source-options')
    admin.request('POST', f'/users/admin/organizations/{foreign_org}/members', expected=403, payload={
        'email': 'forbidden@example.test', 'full_name': 'Synthetic forbidden', 'role_description': 'Synthetic position'})
    superadmin.request('POST', f'/users/admin/users/{candidate_id}/transfer-organization', expected=410,
        code='ORGANIZATION_TRANSFER_REMOVED', payload={'expected_source_organization_id': org,
            'target_organization_id': foreign_org, 'target_role': 'member', 'operation_id': 'removed-transfer-test'})
    # The platform can revoke the only administrator without removing participation.
    admin.request('DELETE', org_path + '/admins', params={'email': 'other@example.test'}, expected=403)
    member.request('DELETE', org_path + '/admins', params={'email': 'other@example.test'}, expected=403)
    for _ in range(2):
        changed = superadmin.request('DELETE', org_path + '/admins', params={'email': 'other@example.test'})
        current = next(item for item in changed['items'] if item['id'] == org)
        assert current['admins'] == [] and current['members_count'] == 3
    admin.request('GET', org_path + '/assessment-source-options', expected=403)
    admin.request('GET', org_path + '/questionnaire', expected=403)
    assert snapshot() == frozen
    replacement_email = 'replacement-admin@example.test'
    changed = superadmin.request('POST', org_path + '/admins', payload={
        'email': replacement_email, 'full_name': 'Synthetic replacement admin'})
    current = next(item for item in changed['items'] if item['id'] == org)
    assert current['members_count'] == 3
    assert {item['email']: item['is_participant'] for item in current['admins']} == {replacement_email: False}
    with get_connection() as connection:
        assert connection.execute('''SELECT role,is_participant FROM organization_memberships
            WHERE user_id=%s''', (admin_id,)).fetchone() == {'role': 'member', 'is_participant': True}
        assert connection.execute('SELECT COUNT(*) AS n FROM organizations WHERE id=%s', (foreign_org,)).fetchone()['n'] == 1
        assert connection.execute("SELECT COUNT(*) AS n FROM users WHERE email='foreign-control@example.test'").fetchone()['n'] == 1
        assert connection.execute('SELECT id FROM users WHERE id=%s', (detached_id,)).fetchone()['id'] == detached_id
    assert_configured_admin_login_after_revoke(base, superadmin)
    assert_superadmin_self_grant_refused(superadmin, users['superadmin@example.test'], foreign_org)


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
    os.environ['ORG_ADMIN_EMAILS'] = CONFIGURED_ORGANIZATION + ':' + CONFIGURED_EMAIL
    run_http_checks(main)
