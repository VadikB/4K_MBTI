"""F02 AC02: actual HTTP token refusals and independent owned PostgreSQL readback.

Secrets exist only in process memory. No mail, provider, or working database is used.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import urlopen
from uuid import uuid4

import psycopg

from tests.remarks_participation_http_checks import (
    Client, EVENTS, SNAPSHOTS, get_connection, run_http_checks, settings,
    web_session_service,
)


def assert_invitation_denied(base, token):
    try:
        reply = urlopen(base + '/users/organization-invitations/' + token, timeout=15)
    except HTTPError as failure:
        reply = failure
    with reply:
        status = reply.status
        reply.read()
    # The URL contains a credential; export only a fixed route label.
    EVENTS.append({'method': 'GET', 'path': '/users/organization-invitations/{redacted}',
                   'status': status, 'expected_status': 404})
    assert status == 404, 'deleted personal invitation remained usable'


def assert_no_account_rows(connection, user_id, email):
    remaining = []
    for row in connection.execute("""SELECT table_name,column_name FROM information_schema.columns
        WHERE table_schema=current_schema() AND column_name IN
        ('user_id','owner_user_id','recipient_user_id','subject_user_id')""").fetchall():
        count = connection.execute(psycopg.sql.SQL('SELECT COUNT(*) AS n FROM {} WHERE {}=%s').format(
            psycopg.sql.Identifier(row['table_name']), psycopg.sql.Identifier(row['column_name'])),
            (user_id,)).fetchone()['n']
        if count:
            remaining.append(row['table_name'] + '.' + row['column_name'])
    assert not remaining, 'owned account references remain: ' + ','.join(remaining)
    assert not connection.execute('SELECT 1 FROM users WHERE id=%s', (user_id,)).fetchone()
    for table in ('auth_magic_links', 'auth_action_tokens', 'auth_password_credentials'):
        assert connection.execute(psycopg.sql.SQL('SELECT COUNT(*) AS n FROM {} WHERE LOWER(email)=%s')
                                  .format(psycopg.sql.Identifier(table)), (email,)).fetchone()['n'] == 0
    assert connection.execute('SELECT COUNT(*) AS n FROM organization_invitations WHERE LOWER(recipient_email)=%s',
                              (email,)).fetchone()['n'] == 0


def assert_auth_purge_races(actor, org_id):
    """Pause real auth after admission, then purge while the request is in flight."""
    from Api.auth_service import AuthService
    from scripts.purge_test_organization import purge_account

    previous_dev_mode = settings.auth_magic_link_dev_mode
    settings.auth_magic_link_dev_mode = True  # Return a synthetic token; never send mail.
    try:
        for kind in ('magic_issue', 'action_issue', 'magic_verify'):
            email = 'f02-race-' + kind.replace('_', '-') + '@example.test'
            actor.request('POST', f'/users/admin/organizations/{org_id}/members', payload={
                'email': email, 'full_name': 'Synthetic concurrent auth', 'role_description': 'Synthetic role'})
            with get_connection() as connection:
                user_id = connection.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()['id']
                token = secrets.token_urlsafe(32)
                if kind == 'magic_verify':
                    connection.execute("""INSERT INTO auth_magic_links(email,token_hash,expires_at)
                        VALUES(%s,%s,NOW()+INTERVAL '1 hour')""",
                        (email, hashlib.sha256(token.encode()).hexdigest()))
                connection.commit()
            service = AuthService()
            admitted = threading.Event()
            resume = threading.Event()
            original_admission = service._ensure_email_can_authenticate

            def pause_after_admission(connection, **kwargs):
                result = original_admission(connection, **kwargs)
                admitted.set()
                if not resume.wait(15):
                    raise AssertionError('concurrent auth was not released')
                return result

            service._ensure_email_can_authenticate = pause_after_admission

            def authenticate():
                if kind == 'magic_issue':
                    return service.create_magic_link_request(email=email)
                if kind == 'action_issue':
                    return service.create_auth_action_request(email=email, purpose='email_verification')
                return service.verify_magic_link(token=token)

            def delete():
                with get_connection() as connection:
                    purge_account(connection, user_id=user_id)
                    connection.commit()

            with ThreadPoolExecutor(max_workers=2) as pool:
                auth = pool.submit(authenticate)
                try:
                    assert admitted.wait(15), 'auth did not reach the controlled admission boundary'
                    with get_connection() as connection:
                        acquired = connection.execute('SELECT pg_try_advisory_xact_lock(%s) AS acquired',
                            (8_044_001,)).fetchone()['acquired']
                    assert not acquired, 'purge could cross an admitted in-flight auth request'
                    deletion = pool.submit(delete)
                finally:
                    resume.set()
                auth.result(timeout=20)
                deletion.result(timeout=20)
            with get_connection() as connection:
                assert_no_account_rows(connection, user_id, email)
            SNAPSHOTS.append({'context': 'f02-concurrent-' + kind,
                'purge_waited_for_admitted_auth': True, 'account_and_email_tokens_absent_after_delete': True})
    finally:
        settings.auth_magic_link_dev_mode = previous_dev_mode


def assert_preverified_registration_cannot_cross_readd(actor, org_id):
    from Api.auth_service import AuthService

    email = 'f02-registration-race@example.test'
    actor.request('POST', f'/users/admin/organizations/{org_id}/members', payload={
        'email': email, 'full_name': 'Synthetic registration race', 'role_description': 'Synthetic role'})
    token = secrets.token_urlsafe(32)
    with get_connection() as connection:
        user_id = connection.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()['id']
        connection.execute("""INSERT INTO auth_action_tokens(email,purpose,token_hash,expires_at)
            VALUES(%s,'email_verification',%s,NOW()+INTERVAL '1 hour')""",
            (email, hashlib.sha256(token.encode()).hexdigest()))
        connection.commit()
    service = AuthService()
    verified = threading.Event()
    resume = threading.Event()
    original_verify = service.verify_auth_action_token_details

    def pause_after_preverification(**kwargs):
        result = original_verify(**kwargs)
        verified.set()
        if not resume.wait(15):
            raise AssertionError('registration preverification was not released')
        return result

    service.verify_auth_action_token_details = pause_after_preverification
    password = 'Synthetic!42Aa' + secrets.token_urlsafe(16)
    with ThreadPoolExecutor(max_workers=1) as pool:
        registration = pool.submit(service.register_password, email=email, password=password,
            password_confirm=password, verification_token=token)
        try:
            assert verified.wait(15), 'initial registration token was not valid'
            preview = actor.request('GET', f'/users/admin/users/{user_id}/purge-preview')
            actor.request('POST', f'/users/admin/users/{user_id}/purge', payload={
                'confirmation_email': email, 'acknowledge_irreversible': True,
                'preview_fingerprint': preview['fingerprint'], 'operation_id': 'f02-registration-race-delete'})
            actor.request('POST', f'/users/admin/organizations/{org_id}/members', payload={
                'email': email, 'full_name': 'Synthetic fresh registration', 'role_description': 'Synthetic role'})
        finally:
            resume.set()
        try:
            registration.result(timeout=20)
        except ValueError:
            pass
        else:
            raise AssertionError('old preverified token registered the new account')
    with get_connection() as connection:
        new_id = connection.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()['id']
        assert new_id != user_id
        assert connection.execute('SELECT COUNT(*) AS n FROM auth_password_credentials WHERE user_id=%s',
                                  (new_id,)).fetchone()['n'] == 0
        assert connection.execute('SELECT COUNT(*) AS n FROM user_identities WHERE user_id=%s AND is_verified=TRUE',
                                  (new_id,)).fetchone()['n'] == 0
    SNAPSHOTS.append({'context': 'f02-registration-token-preverified-before-delete',
        'same_email_readded_with_new_id': True, 'old_registration_failed': True,
        'new_account_has_no_credentials_or_verified_identities': True})


def assert_password_actions_still_work(actor, org_id, base):
    """Positive regression for the token transaction used by registration/reset."""
    from Api.auth_service import _verify_password

    email = 'f02-password-control@example.test'
    actor.request('POST', f'/users/admin/organizations/{org_id}/members', payload={
        'email': email, 'full_name': 'Synthetic password control', 'role_description': 'Synthetic role'})
    tokens = {name: secrets.token_urlsafe(32) for name in ('register', 'reset')}
    with get_connection() as connection:
        user_id = connection.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()['id']
        for name, purpose in [('register', 'email_verification'), ('reset', 'password_reset')]:
            connection.execute("""INSERT INTO auth_action_tokens(email,purpose,token_hash,expires_at)
                VALUES(%s,%s,%s,NOW()+INTERVAL '1 hour')""",
                (email, purpose, hashlib.sha256(tokens[name].encode()).hexdigest()))
        connection.commit()
    first = 'Synthetic!42Aa' + secrets.token_urlsafe(16)
    second = 'Changed!42Aa' + secrets.token_urlsafe(16)
    registered = Client(base)
    registered.request('POST', '/users/auth/email/password-register', payload={
        'email': email, 'password': first, 'password_confirm': first,
        'verification_token': tokens['register']})
    registered.request('GET', f'/users/{user_id}/session-bootstrap')
    anonymous = Client(base)
    anonymous.request('POST', '/users/auth/password/reset', payload={
        'token': tokens['reset'], 'password': second, 'password_confirm': second})
    registered.request('GET', f'/users/{user_id}/session-bootstrap', expected=401)
    anonymous.request('POST', '/users/auth/password/reset', payload={
        'token': tokens['reset'], 'password': second, 'password_confirm': second}, expected=400)
    with get_connection() as connection:
        credential = connection.execute('''SELECT password_hash,password_salt FROM auth_password_credentials
            WHERE user_id=%s''', (user_id,)).fetchone()
        assert _verify_password(second, salt=credential['password_salt'], password_hash=credential['password_hash'])
        assert not _verify_password(first, salt=credential['password_salt'], password_hash=credential['password_hash'])
    SNAPSHOTS.append({'context': 'f02-password-actions-positive-regression',
        'registration_and_reset_work': True, 'reset_is_single_use': True,
        'old_password_replaced': True, 'old_sessions_revoked': True})


def main(base):
    assert not settings.deepseek_api_keys and not settings.email_provider
    email = 'f02-token-person@example.test'
    raw = {name: secrets.token_urlsafe(32) for name in ('magic', 'verify', 'reset', 'invitation')}
    with get_connection() as connection:
        actor_id = connection.execute("SELECT id FROM users WHERE email='superadmin@example.test'").fetchone()['id']
        org_id = connection.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()['id']
    actor = Client(base, web_session_service.create_session(actor_id))
    actor.request('POST', f'/users/admin/organizations/{org_id}/members', payload={
        'email': email, 'full_name': 'Synthetic F02 token person', 'role_description': 'Synthetic role'})
    with get_connection() as connection:
        old_id = connection.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()['id']
        from Api.auth_service import _hash_password
        salt, password_hash = _hash_password(secrets.token_urlsafe(24))
        connection.execute('''INSERT INTO auth_password_credentials(user_id,email,password_salt,password_hash)
            VALUES(%s,%s,%s,%s)''', (old_id, email, salt, password_hash))
        invitation_id = connection.execute("""INSERT INTO organization_invitations
            (organization_id,token_hash,expires_at,recipient_email,purpose,created_by_user_id)
            VALUES(%s,%s,NOW()+INTERVAL '1 hour',%s,'personal_registration',%s) RETURNING id""",
            (org_id, hashlib.sha256(raw['invitation'].encode()).hexdigest(), email, actor_id)).fetchone()['id']
        connection.execute("""INSERT INTO auth_magic_links(email,token_hash,expires_at,organization_invitation_id)
            VALUES(%s,%s,NOW()+INTERVAL '1 hour',%s)""",
            (email, hashlib.sha256(raw['magic'].encode()).hexdigest(), invitation_id))
        for name, purpose in [('verify', 'email_verification'), ('reset', 'password_reset')]:
            connection.execute("""INSERT INTO auth_action_tokens
                (email,purpose,token_hash,expires_at,organization_invitation_id)
                VALUES(%s,%s,%s,NOW()+INTERVAL '1 hour',%s)""",
                (email, purpose, hashlib.sha256(raw[name].encode()).hexdigest(), invitation_id))
        request = {'idempotency_key': 'f02-late-owned-preparation'}
        request_text = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        attempt = uuid4()
        job = dict(connection.execute("""INSERT INTO product_cycle_preparation_operations
            (operation_id,user_id,request_json,request_checksum,status,attempt_token)
            VALUES('f02-late-owned-preparation',%s,%s::jsonb,%s,'running',%s)
            RETURNING id,operation_id,user_id,request_json,request_checksum,attempt_token,created_at""",
            (old_id, request_text, hashlib.sha256(request_text.encode()).hexdigest(), attempt)).fetchone())
        connection.commit()
    stale_cookie = web_session_service.create_session(old_id)
    target = Client(base, stale_cookie)
    target.request('GET', f'/users/{old_id}/session-bootstrap')
    preview = actor.request('GET', f'/users/admin/users/{old_id}/purge-preview')
    command = {'confirmation_email': email, 'acknowledge_irreversible': True,
               'preview_fingerprint': preview['fingerprint'], 'operation_id': 'f02-token-owned-deletion'}
    actor.request('POST', f'/users/admin/users/{old_id}/purge', payload=command)
    with get_connection() as connection:
        assert_no_account_rows(connection, old_id, email)
    target.request('GET', f'/users/{old_id}/session-bootstrap', expected=401)
    anonymous = Client(base)
    anonymous.request('POST', '/users/auth/email/verify', payload={'token': raw['magic']}, expected=400)
    anonymous.request('POST', '/users/auth/email/confirm', payload={'token': raw['verify']}, expected=400)
    anonymous.request('POST', '/users/auth/password/reset/validate', payload={'token': raw['reset']}, expected=400)
    assert_invitation_denied(base, raw['invitation'])

    # Replay the captured, already claimed real worker job after its row was deleted.
    # The real lease guard must stop before any generation or account recreation.
    from Api.product_cycle_preparation_queue import ProductCyclePreparationQueue
    ProductCyclePreparationQueue()._process(job)
    with get_connection() as connection:
        assert_no_account_rows(connection, old_id, email)
        with connection.transaction():
            try:
                with connection.transaction():
                    connection.execute("""INSERT INTO assessment_preparation_jobs
                        (operation_id,user_id,user_payload_json) VALUES('f02-stale-fk',%s,'{}'::jsonb)""", (old_id,))
            except psycopg.errors.ForeignKeyViolation:
                pass
            else:
                raise AssertionError('late queue insertion accepted a deleted account')
    actor.request('POST', f'/users/admin/organizations/{org_id}/members', payload={
        'email': email, 'full_name': 'Synthetic new F02 account', 'role_description': 'Synthetic role'})
    with get_connection() as connection:
        new_id = connection.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()['id']
        assert new_id != old_id
        assert connection.execute('''SELECT role,is_participant FROM organization_memberships
            WHERE user_id=%s AND organization_id=%s''', (new_id, org_id)).fetchone() == {
                'role': 'member', 'is_participant': True}
        for table, column in [('auth_password_credentials', 'user_id'),
                              ('assessment_personalized_profiles', 'user_id'), ('m5_cycles', 'owner_user_id'),
                              ('product_cycle_preparation_operations', 'user_id')]:
            assert connection.execute(psycopg.sql.SQL('SELECT COUNT(*) AS n FROM {} WHERE {}=%s').format(
                psycopg.sql.Identifier(table), psycopg.sql.Identifier(column)), (new_id,)).fetchone()['n'] == 0, table
        assert not connection.execute('SELECT 1 FROM users WHERE id=%s', (old_id,)).fetchone()
    # Old credentials must remain invalid even after the same email is admitted again.
    target.request('GET', f'/users/{old_id}/session-bootstrap', expected=401)
    anonymous.request('POST', '/users/auth/email/verify', payload={'token': raw['magic']}, expected=400)
    anonymous.request('POST', '/users/auth/email/confirm', payload={'token': raw['verify']}, expected=400)
    anonymous.request('POST', '/users/auth/password/reset/validate', payload={'token': raw['reset']}, expected=400)
    password = 'Synthetic!42Aa' + secrets.token_urlsafe(16)
    anonymous.request('POST', '/users/auth/email/password-register', payload={
        'email': email, 'password': password, 'password_confirm': password,
        'verification_token': raw['verify']}, expected=400)
    anonymous.request('POST', '/users/auth/password/reset', payload={
        'token': raw['reset'], 'password': password, 'password_confirm': password}, expected=400)
    assert_invitation_denied(base, raw['invitation'])
    assert_auth_purge_races(actor, org_id)
    assert_preverified_registration_cannot_cross_readd(actor, org_id)
    assert_password_actions_still_work(actor, org_id, base)
    SNAPSHOTS.append({'context': 'f02-ac02', 'old_account_absent': True,
        'old_tokens_invalid_before_and_after_readd': True, 'captured_worker_stopped': True,
        'late_fk_write_rejected': True, 'new_account_id_differs': True,
        'new_account_has_no_credentials_assessed_profiles_cycles_or_queued_history': True})


if __name__ == '__main__':
    run_http_checks(main, evidence_file_env='F02_TOKEN_EVIDENCE', contract='f02-tokens-http-pg/1')
