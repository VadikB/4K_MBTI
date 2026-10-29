"""Scoped recovery around the historical single-active-row W02 projection."""
from __future__ import annotations

import json
from fastapi.encoders import jsonable_encoder


def ensure_schema(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS participant_acquaintance_scope_states (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
        assignment_ref TEXT NOT NULL,
        questionnaire_revision_key BIGINT NOT NULL,
        state_json JSONB NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        PRIMARY KEY(user_id,organization_id,assignment_ref,questionnaire_revision_key)
    )''')


def same_scope(row, readiness):
    return bool(row and row.get('organization_id') == readiness.get('organization_id')
        and str(row.get('assignment_ref') or '') == str(readiness.get('assignment_ref') or '')
        and row.get('questionnaire_revision_id') == readiness.get('questionnaire_revision_id'))


def available(connection):
    row = connection.execute("SELECT to_regclass(current_schema()||'.participant_acquaintance_scope_states') AS relation").fetchone()
    return bool(row and row.get('relation'))


def read(connection, *, user_id, readiness):
    current = connection.execute('SELECT * FROM participant_acquaintance_states WHERE user_id=%s', (user_id,)).fetchone()
    if same_scope(current, readiness):
        return dict(current)
    if not readiness.get('assignment_ref') or not available(connection):
        return None
    row = connection.execute('''SELECT state_json FROM participant_acquaintance_scope_states
        WHERE user_id=%s AND organization_id=%s AND assignment_ref=%s AND questionnaire_revision_key=%s''',
        (user_id, readiness['organization_id'], readiness['assignment_ref'],
         readiness.get('questionnaire_revision_id') or 0)).fetchone()
    return dict(row['state_json']) if row else None


def activate(connection, *, user_id, readiness):
    """Command-only switch; preserve previous scope before updating active projection."""
    connection.execute('SELECT id FROM users WHERE id=%s FOR UPDATE', (user_id,))
    current = connection.execute('SELECT * FROM participant_acquaintance_states WHERE user_id=%s FOR UPDATE', (user_id,)).fetchone()
    if same_scope(current, readiness):
        return dict(current)
    restored = read(connection, user_id=user_id, readiness=readiness)
    if current and available(connection):
        connection.execute('''INSERT INTO participant_acquaintance_scope_states
            (user_id,organization_id,assignment_ref,questionnaire_revision_key,state_json)
            VALUES(%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT(user_id,organization_id,assignment_ref,questionnaire_revision_key)
            DO UPDATE SET state_json=EXCLUDED.state_json,updated_at=NOW()''',
            (user_id, current['organization_id'], str(current.get('assignment_ref') or ''),
             current.get('questionnaire_revision_id') or 0,
             json.dumps(jsonable_encoder(dict(current)), ensure_ascii=False)))
    # Do not create an empty consent/answer row merely by entering a scope.
    # A following accepted command writes all fields in the existing transaction.
    return restored


def write(connection, *, user_id, readiness, state):
    return dict(connection.execute('''INSERT INTO participant_acquaintance_states
        (user_id,organization_id,organization_context_version_id,assignment_ref,questionnaire_revision_id,
         status,current_step,answers_json,answers_confirmed_at,briefing_checksum,consent_version,consent_accepted_at,created_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,COALESCE(%s::timestamp,NOW()))
        ON CONFLICT(user_id) DO UPDATE SET
          organization_id=EXCLUDED.organization_id,organization_context_version_id=EXCLUDED.organization_context_version_id,
          assignment_ref=EXCLUDED.assignment_ref,questionnaire_revision_id=EXCLUDED.questionnaire_revision_id,
          status=EXCLUDED.status,current_step=EXCLUDED.current_step,answers_json=EXCLUDED.answers_json,
          answers_confirmed_at=EXCLUDED.answers_confirmed_at,briefing_checksum=EXCLUDED.briefing_checksum,
          consent_version=EXCLUDED.consent_version,consent_accepted_at=EXCLUDED.consent_accepted_at,
          created_at=EXCLUDED.created_at,updated_at=NOW()
        RETURNING *''', (user_id, readiness['organization_id'], readiness['organization_context_version_id'],
        readiness['assignment_ref'], readiness.get('questionnaire_revision_id'), state['status'], state['current_step'],
        json.dumps(state.get('answers_json') or {}, ensure_ascii=False), state.get('answers_confirmed_at'),
        readiness['briefing_checksum'], state.get('consent_version'), state.get('consent_accepted_at'),
        state.get('created_at'))).fetchone())
