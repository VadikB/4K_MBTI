"""Scoped answers/consent recovery; isolated transaction, never shared application data."""
from datetime import datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from Api import acquaintance_state_store as store


@pytest.mark.integration
def test_scoped_history_does_not_transfer_answers_or_consent(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = 'path29_scope_' + uuid4().hex
        connection.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL('SET LOCAL search_path TO {}').format(psycopg.sql.Identifier(schema)))
        connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)')
        connection.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY)')
        connection.execute('INSERT INTO users VALUES(1),(2)')
        connection.execute('INSERT INTO organizations VALUES(10),(20)')
        connection.execute('''CREATE TABLE participant_acquaintance_states(
            user_id BIGINT PRIMARY KEY,organization_id BIGINT,organization_context_version_id BIGINT,
            assignment_ref TEXT,questionnaire_revision_id BIGINT,status TEXT,current_step INTEGER,
            answers_json JSONB,answers_confirmed_at TIMESTAMP,briefing_checksum TEXT,
            consent_version INTEGER,consent_accepted_at TIMESTAMP,created_at TIMESTAMP,updated_at TIMESTAMP DEFAULT NOW())''')
        store.ensure_schema(connection)
        a = dict(organization_id=10, assignment_ref='A', questionnaire_revision_id=101,
                 organization_context_version_id=1001, briefing_checksum='synthetic-a')
        b = {**a, 'assignment_ref': 'B', 'questionnaire_revision_id': 102}
        revision = {**a, 'questionnaire_revision_id': 103}
        tenant = {**a, 'organization_id': 20}
        saved = dict(status='in_progress', current_step=3, answers_json={'answer_1': 'Synthetic own answer'},
                     consent_version=1, consent_accepted_at=datetime(2026, 10, 29, 10),
                     answers_confirmed_at=None, created_at=datetime(2026, 10, 29, 9))
        assert store.activate(connection, user_id=1, readiness=a) is None
        original = store.write(connection, user_id=1, readiness=a, state=saved)
        for scope in (b, revision, tenant):
            assert store.read(connection, user_id=1, readiness=scope) is None
        assert connection.execute('SELECT COUNT(*) AS n FROM participant_acquaintance_scope_states').fetchone()['n'] == 0
        assert store.activate(connection, user_id=1, readiness=b) is None
        store.write(connection, user_id=1, readiness=b, state={
            'status': 'not_started', 'current_step': 0, 'answers_json': {}})
        assert store.read(connection, user_id=1, readiness=b)['consent_accepted_at'] is None
        assert store.read(connection, user_id=2, readiness=a) is None
        recovered = store.read(connection, user_id=1, readiness=a)
        assert recovered['answers_json'] == saved['answers_json']
        assert recovered['consent_accepted_at'] == saved['consent_accepted_at'].isoformat()
        restored = store.activate(connection, user_id=1, readiness=a)
        again = store.write(connection, user_id=1, readiness=a, state=restored)
        assert again['created_at'] == original['created_at']
        assert again['consent_accepted_at'] == original['consent_accepted_at']
        assert again['answers_json'] == original['answers_json']
        connection.execute('SAVEPOINT scope_switch')
        store.activate(connection, user_id=1, readiness=tenant)
        store.write(connection, user_id=1, readiness=tenant, state={'status': 'not_started', 'current_step': 0})
        connection.execute('ROLLBACK TO SAVEPOINT scope_switch')
        assert store.read(connection, user_id=1, readiness=a)['answers_json'] == saved['answers_json']
        assert store.read(connection, user_id=1, readiness=tenant) is None
        connection.rollback()
