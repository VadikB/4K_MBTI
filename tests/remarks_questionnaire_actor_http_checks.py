"""F06 real HTTP/PG; manual/CSV actor provenance and old-revision privacy.

Upstream questionnaire answers and accounts are disposable synthetic inputs.
No questionnaire author is supplied by the product; a legacy spoofed payload
field is deliberately ignored by the actual HTTP handler.
"""
import csv
import hashlib
import io
import json

from tests.remarks_participation_http_checks import (
    ROOT, SNAPSHOTS, Client, get_connection, run_http_checks, settings, state,
    web_session_service,
)


def revision_snapshot(revision_id):
    with get_connection() as connection:
        row = connection.execute('SELECT to_jsonb(q) AS row FROM questionnaire_response_revisions q WHERE id=%s',
            (revision_id,)).fetchone()['row']
    return hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()


def main(base):
    assert not settings.deepseek_api_keys and not settings.email_provider
    with get_connection() as connection:
        users = {row['email']: row['id'] for row in connection.execute('SELECT id,email FROM users').fetchall()}
        organization = connection.execute("SELECT id FROM organizations WHERE code='e102_synthetic'").fetchone()['id']
    actor_a = users['participant@example.test']
    actor_b = users['other@example.test']
    superadmin = Client(base, web_session_service.create_session(users['superadmin@example.test']))
    org_path = f'/users/admin/organizations/{organization}'
    for email, name in [('participant@example.test', 'Synthetic uploader A'), ('other@example.test', 'Synthetic confirmer B')]:
        superadmin.request('POST', org_path + '/admins', payload={'email': email, 'full_name': name})
    created = superadmin.request('POST', '/users/admin/organizations', payload={
        'code': 'actor_foreign', 'name': 'Synthetic actor foreign control'})
    foreign_org = next(item['id'] for item in created['items'] if item['code'] == 'actor_foreign')
    superadmin.request('POST', f'/users/admin/organizations/{foreign_org}/admins', payload={
        'email': 'foreign-actor@example.test', 'full_name': 'Synthetic foreign actor'})
    with get_connection() as connection:
        foreign_id = connection.execute("SELECT id FROM users WHERE email='foreign-actor@example.test'").fetchone()['id']
    foreign = Client(base, web_session_service.create_session(foreign_id))
    a, b = Client(base), Client(base)

    def login(client, email):
        client.request('POST', '/users/auth/email/password-login', payload={'email': email, 'password': state['password']})

    login(a, 'participant@example.test')
    login(b, 'other@example.test')
    csv_text = (ROOT / 'assessment_definitions/questionnaires/corporate/0.2/example.synthetic.csv').read_text()
    answers = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        answers.setdefault(row['question_id'], {})[row['field']] = row['value']
    legacy_recipients = {'recipients': ['participant', 'organization_admin'], 'recipient_user_ids': [actor_b]}
    with get_connection() as connection:
        expected_names = {row['id']: row['full_name'] for row in connection.execute(
            'SELECT id,full_name FROM users WHERE id=ANY(%s)', ([actor_a, actor_b],)).fetchall()}
    expected_emails = {actor_a: 'participant@example.test', actor_b: 'other@example.test'}

    def assert_actor(revision, uploader, *, revision_id, confirmed=False, joined=True):
        assert revision['id'] == revision_id and revision['uploaded_by_user_id'] == uploader
        assert revision['source_author'] == ''
        if joined:
            assert revision['uploaded_by_name'] == expected_names[uploader]
            assert revision['uploaded_by_email'] == expected_emails[uploader]
        if confirmed:
            assert revision['status'] == 'confirmed'
            assert revision['recipient_mapping'] == ['participant', 'organization_admin']
            assert revision['recipient_user_ids'] == []
        assert 'C04' not in revision['answers_json']
        assert 'responsible_contact' not in revision['answers_json']['C21']
        assert 'responsible_contact' not in revision['participant_preview']

    for channel in ['product_form', 'csv']:
        ref = 'remarks-actor-' + channel
        revision_ids = []
        first_history = None
        for index, (uploader, confirmer, uploader_id, confirmer_id) in enumerate([
            (a, b, actor_a, actor_b), (b, a, actor_b, actor_a),
        ]):
            payload = {'assignment_ref': ref, 'channel': channel,
                'idempotency_key': ref + '-' + str(index),
                'source_author': 'Spoofed legacy author must not be trusted'}
            if channel == 'csv':
                payload['csv_text'] = (csv_text + '\nC04,answer,"Только участник"\nC21,responsible_contact,"old@example.test"\n').replace(
                    'Техническая проверка изолированного тестового контура', 'Synthetic actor revision ' + str(index))
            else:
                payload['answers'] = {**answers, 'C01': {**answers['C01'],
                    'activity_description': 'Synthetic actor revision ' + str(index)}}
            preview = uploader.request('POST', org_path + '/questionnaire/preview', expected=201, payload=payload)
            revision_id = preview['id']
            revision_ids.append(revision_id)
            assert_actor(preview, uploader_id, revision_id=revision_id)
            confirmed = confirmer.request('POST', org_path + f'/questionnaire/{revision_id}/confirm', payload=legacy_recipients)
            # Confirmation returns the authoritative uploader ID even before the joined read.
            assert_actor(confirmed, uploader_id, revision_id=revision_id, confirmed=True, joined=False)
            replay = confirmer.request('POST', org_path + f'/questionnaire/{revision_id}/confirm', payload={})
            assert replay['id'] == confirmed['id'] and replay['status'] == 'confirmed'
            with get_connection() as connection:
                stored = connection.execute('''SELECT uploaded_by_user_id,confirmed_by_user_id,source_author,status
                    FROM questionnaire_response_revisions WHERE id=%s''', (revision_id,)).fetchone()
                assert stored == {'uploaded_by_user_id': uploader_id, 'confirmed_by_user_id': confirmer_id,
                    'source_author': '', 'status': 'confirmed'}
                assert connection.execute('''SELECT COUNT(*) AS n FROM assessment_organization_context_versions
                    WHERE source_manifest_json->>'questionnaire_revision_id'=%s''', (str(revision_id),)).fetchone()['n'] == 1
            immutable = revision_snapshot(revision_id)
            if index == 0:
                first_history = immutable
            for client in [a, b]:
                current = client.request('GET', org_path + f'/questionnaire/{revision_id}')
                assert_actor(current, uploader_id, revision_id=revision_id, confirmed=True)
                listed = client.request('GET', org_path + '/questionnaire')['items']
                selected = next(item for item in listed if item['assignment_ref'] == ref)
                assert_actor(selected, uploader_id, revision_id=revision_id, confirmed=True)
            # A fresh cookie-backed login and subsequent reads model reload/re-entry.
            login(b, 'other@example.test')
            reread = b.request('GET', org_path + f'/questionnaire/{revision_id}')
            assert_actor(reread, uploader_id, revision_id=revision_id, confirmed=True)
            before_privacy = revision_snapshot(revision_id)
            denied = foreign.request('GET', org_path + f'/questionnaire/{revision_id}', expected=403)
            assert 'uploaded_by_email' not in denied and 'answers_json' not in denied
            foreign.request('GET', org_path + '/questionnaire', expected=403)
            foreign.request('GET', f'/users/admin/organizations/{foreign_org}/questionnaire/{revision_id}', expected=404)
            assert revision_snapshot(revision_id) == before_privacy == immutable
            assert revision_snapshot(revision_ids[0]) == first_history, 'a later revision rewrote historical provenance'
            historical = b.request('GET', org_path + f'/questionnaire/{revision_ids[0]}')
            assert_actor(historical, actor_a, revision_id=revision_ids[0], confirmed=True)
            SNAPSHOTS.append({'context': 'questionnaire_actor', 'channel': channel, 'revision_id': revision_id,
                'uploader_user_id': uploader_id, 'confirmer_user_id': confirmer_id,
                'before': immutable, 'after': revision_snapshot(revision_id), 'unchanged': True,
                'historical_revision_unchanged': True, 'foreign_scope_denied': True,
                'removed_fields_not_active': True, 'legacy_manual_author_ignored': True})
    with get_connection() as connection:
        assert connection.execute('SELECT COUNT(*) AS n FROM m5_cycles').fetchone()['n'] == 0
        assert connection.execute('SELECT COUNT(*) AS n FROM m5_assessment_situations').fetchone()['n'] == 0


if __name__ == '__main__':
    run_http_checks(main, evidence_file_env='REMARKS_QUESTIONNAIRE_ACTOR_EVIDENCE',
        contract='remarks-questionnaire-actor-http-pg/1')
