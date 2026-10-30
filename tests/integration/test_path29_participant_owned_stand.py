"""Real questionnaire/assignment API → new participant → canonical M4, synthetic only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration


def test_path29_participant_on_owned_clean_database(tmp_path):
    env = {**os.environ, 'STAND_ADMIN_URL': os.getenv('STAND_ADMIN_URL') or os.getenv('TEST_DATABASE_URL', '')}
    state_path = tmp_path / 'state.json'

    def cli(action):
        result = subprocess.run([sys.executable, 'scripts/test_stand.py', action, '--state', str(state_path), '--gateway', '1'],
            env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr

    cli('create')
    try:
        cli('bootstrap')
        cli('seed')  # Sources and OTHER participants only; target is added below through HTTP.
        from scripts.test_stand import environment
        previous = os.environ.get('STAND_ADMIN_URL')
        os.environ['STAND_ADMIN_URL'] = env['STAND_ADMIN_URL']
        try:
            isolated = environment(json.loads(state_path.read_text()))
        finally:
            if previous is None:
                os.environ.pop('STAND_ADMIN_URL', None)
            else:
                os.environ['STAND_ADMIN_URL'] = previous
        result = subprocess.run([sys.executable, __file__, '--internal'], env=isolated,
                                capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        cli('destroy')


def internal():
    from Api import routes
    from Api.database import get_connection, close_connection_pool
    from Api.web_session_service import web_session_service
    from Api.assessment_authoring_service import assessment_authoring_service
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from urllib.parse import urlsplit, parse_qs
    from Api import auth_service as auth_module
    mailbox = []
    auth_module.send_auth_action_email = lambda **payload: mailbox.append(payload)
    auth_module.settings.email_provider = 'postmark'
    auth_module.settings.app_base_url = 'https://test.example.com'
    auth_module.settings.app_origin_mode = 'public'

    app = FastAPI()
    app.include_router(routes.router)
    with get_connection() as c:
        superadmin = c.execute("SELECT id FROM users WHERE email='superadmin@example.test'").fetchone()['id']
        org = c.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()['id']
        runtime = c.execute("SELECT * FROM assessment_configurations WHERE code='e102_controlled_catalog'").fetchone()
        other = assessment_authoring_service.create_configuration(c, code='path29_explicit_second',
            name='Synthetic second explicit configuration', methodology_version_id=runtime['methodology_version_id'],
            scenario_version_id=runtime['scenario_version_id'], catalog_version_id=runtime['catalog_version_id'],
            actor_user_id=superadmin, comment='Synthetic isolated source assignment regression')
        other = assessment_authoring_service.publish_configuration(c, configuration_id=other['id'], make_default=False,
            actor_user_id=superadmin, comment='Synthetic isolated source assignment regression')
        role_code = 'specialist_expert'
        role_id = c.execute('''SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code=%s AND v.status='published' ''', (role_code,)).fetchone()['id']
        student_id = c.execute("SELECT v.id FROM assessment_role_profile_versions v JOIN assessment_role_profiles r ON r.id=v.role_profile_id WHERE r.code='student'").fetchone()['id']
        c.commit()

    with TestClient(app) as admin, TestClient(app) as participant:
        admin.cookies.set(routes.SESSION_COOKIE_NAME, web_session_service.create_session(superadmin))
        assert admin.post(f'/users/admin/organizations/{org}/admins', json={
            'email': 'path29-admin@example.test', 'full_name': 'Synthetic scoped admin'}).status_code == 200
        assert admin.post(f'/users/admin/organizations/{org}/members', json={
            'email': 'path29-participant@example.test', 'full_name': 'Synthetic new participant',
            'role_description': 'Synthetic actual position'}).status_code == 200
        with get_connection() as c:
            uid = c.execute("SELECT id FROM users WHERE email='path29-participant@example.test'").fetchone()['id']
            actor = c.execute("SELECT id FROM users WHERE email='path29-admin@example.test'").fetchone()['id']
            assert c.execute('SELECT COUNT(*) AS n FROM assessment_personalized_profiles WHERE user_id=%s', (uid,)).fetchone()['n'] == 0
        admin.cookies.set(routes.SESSION_COOKIE_NAME, web_session_service.create_session(actor))
        base = f'/users/admin/organizations/{org}'
        preview = admin.post(base + '/questionnaire/preview', json={
            'assignment_ref': 'path29-flow', 'source_author': 'Synthetic customer',
            'idempotency_key': 'path29-questionnaire', 'channel': 'csv',
            'csv_text': Path('assessment_definitions/questionnaires/corporate/0.1/example.synthetic.csv').read_text(),
        })
        assert preview.status_code == 201, preview.text
        revision = preview.json()['id']
        response = admin.post(base + f'/questionnaire/{revision}/confirm', json={'recipients': ['participant']})
        assert response.status_code == 200, response.text
        with get_connection() as c:
            c.execute('''INSERT INTO organization_assessment_pilot_bindings
                (organization_id,assignment_ref,binding_version,assessment_configuration_id,
                 role_profile_version_id,configured_by_user_id)
                VALUES(%s,%s,'specialist-pilot/1',%s,%s,%s)''',
                (org, 'path29-flow', other['id'], role_id, actor))
            c.commit()
        payload = {'user_ids': [uid], 'assignment_ref': 'path29-flow', 'operation_id': 'path29-without-sources'}
        assigned = admin.post(base + '/assessment-assignments', json=payload)
        assert assigned.status_code == 200, assigned.text
        email = 'path29-participant@example.test'
        sent = participant.post('/users/auth/email/request-link', json={'email': email})
        assert sent.status_code == 200 and sent.json()['auth_mode'] == 'verification_pending', sent.text
        delivered = urlsplit(mailbox[-1]['action_url'])
        assert delivered.scheme == 'https' and delivered.netloc == 'test.example.com'
        verification = parse_qs(delivered.query)['token'][0]
        assert participant.post('/users/auth/email/confirm', json={'token': verification}).status_code == 200
        registered = participant.post('/users/auth/email/password-register', json={
            'email': email, 'password': 'SyntheticPass1!', 'password_confirm': 'SyntheticPass1!',
            'verification_token': verification,
        })
        assert registered.status_code == 200, registered.text
        assert registered.json()['agent']['stage'] == 'acquaintance'
        assert participant.get('/users/assessment/profile/options').status_code == 409
        assert participant.put('/users/role-profiles/selection', json={'version_id': student_id}).status_code == 409
        assert participant.post('/users/session/reopen-profile').status_code == 409
        assert participant.post(f'/users/{uid}/assessment/start').status_code == 409
        path = f'/users/{uid}/acquaintance'
        current = participant.get(path).json()
        assert current['readiness']['status'] == 'ready'
        fields = {item['key']: item for item in current['readiness']['briefing']['provided_participant_fields']}
        assert fields['position']['value'] == 'Synthetic actual position'
        assert fields['full_name']['value'] == 'Synthetic new participant'
        assert fields['role']['value'] == 'Специалист / эксперт'
        assert all(item['readonly'] and item['source'] and item['label'] for item in fields.values())
        assert participant.put(path + '/answers', json={'answers': {'answer_1': 'Synthetic'}}).status_code == 409
        assert participant.post('/users/assessment/cycles/prepare', json={
            'idempotency_key': 'path29-no-consent', 'selected_skills': ['K1', 'K2', 'K3', 'K4'],
        }).status_code == 409
        for status in ('completed', 'skipped'):
            assert participant.put(f'/users/{uid}/onboarding', json={'status': status, 'current_step': 99}).status_code == 400
        assert participant.post(path + '/consent', json={'version': 1}).status_code == 200
        answers = {'answer_1': 'Synthetic work situations', 'answer_2': 'Не знаю', 'answer_3': 'Synthetic constraints'}
        for key, value in answers.items():
            assert participant.put(path + '/answers', json={'answers': {key: value}}).status_code == 200
            assert participant.get(path).json()['state']['answers_json'][key] == value
        answers['answer_2'] = 'Synthetic deliberately edited decision answer'
        assert participant.put(path + '/answers', json={'answers': {'answer_2': answers['answer_2']}}).status_code == 200
        response = participant.put(path + '/answers', json={'answers': answers, 'confirm': True})
        assert response.status_code == 200, response.text
        resolved = participant.post(path + '/resolve-profile')
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()['late_readiness']['status'] == 'ready_to_prepare'
        assert resolved.json()['state']['answers_json'] == answers
        assert participant.put(path + '/answers', json={'answers': {'answer_2': 'Changed after confirmation'}}).status_code == 409
        assert participant.put(path + '/answers', json={'answers': answers, 'confirm': False}).json()['answers_confirmed_at']
        assert participant.get(f'/users/{uid}/journey-state').json()['next_action'] == 'show_onboarding'
        assert participant.get(base + '/assessment-source-options').status_code in {401, 403, 404}
        assert admin.post(base + '/assessment-assignments', json={**payload, 'operation_id': 'path29-deny-student',
            'assessment_configuration_id': other['id'], 'role_profile_version_id': student_id}).status_code == 409
        selected = {**payload, 'operation_id': 'path29-complete-specialist'}
        for _ in range(2):
            response = admin.post(base + '/assessment-assignments', json=selected)
            assert response.status_code == 200, response.text
        assert admin.post(base + '/assessment-assignments', json={**selected, 'user_ids': [uid, actor]}).status_code == 409
        assert admin.post(base + '/assessment-assignments', json={**selected,
            'assessment_configuration_id': runtime['id'], 'role_profile_version_id': role_id}).status_code == 409
        for _ in range(2):
            response = participant.post(path + '/resolve-profile')
            assert response.status_code == 200, response.text
            assert response.json()['late_readiness']['status'] == 'ready_to_prepare'
        current = participant.get(path).json()
        assert current['mandatory_complete'] is True
        profile_id = current['late_readiness']['personalized_profile_id']
        assert participant.put(path + '/answers', json={'answers': {'answer_2': 'Changed after bound M4'}}).status_code == 409
        replay = participant.put(path + '/answers', json={'answers': answers, 'confirm': False})
        assert replay.status_code == 200 and replay.json()['answers_confirmed_at']
        assert participant.get(path).json()['late_readiness']['personalized_profile_id'] == profile_id
        with get_connection() as c:
            assert c.execute('SELECT COUNT(*) AS n FROM assessment_personalized_profiles WHERE user_id=%s', (uid,)).fetchone()['n'] == 1
            profile = c.execute('SELECT * FROM assessment_personalized_profiles WHERE id=%s', (profile_id,)).fetchone()
            assert profile['assessment_configuration_id'] == other['id']
            professional = profile['content_json']['user_context']
            assert professional['position_or_status'] == 'Synthetic actual position'
            assert [item['raw_answer'] for item in professional['acquaintance_answers']['items']] == list(answers.values())
            assert professional['acquaintance_answers']['schema_version'] == '1.0'
            assert c.execute('SELECT selected_role_profile_version_id,personal_data_consent_accepted_at FROM users WHERE id=%s', (uid,)).fetchone() == {
                'selected_role_profile_version_id': None, 'personal_data_consent_accepted_at': None}
        assert participant.get(f'/users/{uid}/journey-state').json()['profile']['status'] == 'complete'
        changed = admin.post(base + '/assessment-assignments', json={**selected,
            'operation_id': 'path29-deny-frozen-change', 'assessment_configuration_id': runtime['id'],
            'role_profile_version_id': role_id})
        assert changed.status_code == 409, changed.text
        assert 'Выбранная роль или версия программы не относится к текущей оценке' in changed.text
        assert 'PROGRAM_SOURCE_OVERRIDE_NOT_ALLOWED' not in changed.text
        participant.cookies.clear()
        logged_in = participant.post('/users/auth/email/password-login', json={'email': email, 'password': 'SyntheticPass1!'})
        assert logged_in.status_code == 200, logged_in.text
        assert participant.get(path).json()['state']['answers_json'] == answers
        assert participant.get(f'/users/{uid + 999}/acquaintance').status_code == 403
        from Api.product_cycle_preparation_queue import product_cycle_preparation_queue as queue
        accepted = participant.post('/users/assessment/cycles/prepare', json={
            'idempotency_key': 'path29-prepare-first', 'selected_skills': ['K1', 'K2', 'K3', 'K4'],
        })
        assert accepted.status_code == 202, accepted.text
        operation_id = accepted.json()['operation_id']
        repeated = participant.post('/users/assessment/cycles/prepare', json={
            'idempotency_key': 'path29-new-tab-key', 'selected_skills': ['K1', 'K2', 'K3', 'K4'],
        })
        assert repeated.status_code == 202 and repeated.json()['operation_id'] == operation_id
        assert participant.get(path).json()['preparation_operation']['operation_id'] == operation_id
        job = queue._claim()
        assert job['operation_id'] == operation_id
        queue._process(job)  # The fixture catalog intentionally has no admitted specialist_expert case.
        completed = participant.get('/users/assessment/cycles/preparation/' + operation_id)
        assert completed.status_code == 200 and completed.json()['status'] == 'failed', completed.text
        assert completed.json()['error']['code'] == 'ASSESSMENT_CATALOG_NO_ADMISSIBLE_SPECIALIST_CASE'
        with get_connection() as c:
            assert c.execute('SELECT COUNT(*) AS n FROM m5_cycles WHERE owner_user_id=%s', (uid,)).fetchone()['n'] == 0
            invitations_before = c.execute('SELECT COUNT(*) AS n FROM organization_invitations WHERE organization_id=%s AND LOWER(recipient_email)=%s',
                (org, email)).fetchone()['n']
        removed = admin.delete(base + '/members', params={'email': email})
        assert removed.status_code == 200, removed.text
        with get_connection() as c:
            assert c.execute("SELECT 1 FROM organization_memberships WHERE organization_id=%s AND user_id=%s AND role='member'", (org, uid)).fetchone() is None
        # The removed membership cannot grant organization administration; the user's own saved
        # assessment state remains stored under the existing owner contract.
        assert participant.get(base + '/assessment-source-options').status_code in {401, 403, 404}
        with get_connection() as c:
            assert c.execute('SELECT COUNT(*) AS n FROM assessment_personalized_profiles WHERE user_id=%s', (uid,)).fetchone()['n'] == 1
        restored = admin.post(base + '/members', json={'email': email,
            'full_name': 'Synthetic new participant', 'role_description': 'Synthetic actual position'})
        assert restored.status_code == 200, restored.text
        with get_connection() as c:
            assert c.execute("SELECT 1 FROM organization_memberships WHERE organization_id=%s AND user_id=%s AND role='member'", (org, uid)).fetchone()
            assert c.execute('SELECT id FROM users WHERE email=%s', (email,)).fetchone()['id'] == uid
            assert c.execute('SELECT COUNT(*) AS n FROM organization_invitations WHERE organization_id=%s AND LOWER(recipient_email)=%s',
                (org, email)).fetchone()['n'] == invitations_before
        participant.cookies.clear()
        assert participant.post('/users/auth/email/password-login', json={
            'email': email, 'password': 'SyntheticPass1!'}).status_code == 200
    close_connection_pool()
    print('PATH29 canonical participant API regression PASS')


if __name__ == '__main__':
    internal()
