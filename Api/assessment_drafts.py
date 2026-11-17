"""Private mutable input, outside Dialogue/material/evaluation and presence.

Cycle -> AS locks serialize CAS with Turn acceptance. A slot is anchored to a
persisted Turn, never to a polling/time revision. No typing history is retained.
"""
from datetime import datetime, timezone

from Api.m5_cycle_runtime import read_cycle
from Api.m5_scenario_runtime import _as_row


def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS assessment_answer_drafts (
        assessment_situation_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id) ON DELETE CASCADE,
        owner_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        slot_id TEXT NOT NULL,
        version BIGINT NOT NULL DEFAULT 0 CHECK(version >= 0),
        revision TEXT NOT NULL DEFAULT '',
        content_text TEXT NOT NULL DEFAULT '' CHECK(char_length(content_text) <= 10000),
        consumed BOOLEAN NOT NULL DEFAULT FALSE,
        expires_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY(assessment_situation_db_id,owner_user_id,slot_id)
    )""")
    connection.execute("CREATE INDEX IF NOT EXISTS ix_answer_drafts_expiry ON assessment_answer_drafts(expires_at)")


def scope(connection, *, assessment_situation_id, owner_user_id, now=None):
    situation = _as_row(connection, assessment_situation_id, lock=True)
    cycle = connection.execute('SELECT cycle_id,owner_user_id,assignment_id FROM m5_cycles WHERE id=%s',
                               (situation['cycle_db_id'],)).fetchone()
    if int(cycle['owner_user_id']) != int(owner_user_id):
        raise ValueError('DRAFT_OWNER_MISMATCH')
    runtime = read_cycle(connection, str(cycle['cycle_id']))
    deadline = runtime['calendar_deadline']
    if (runtime['status'] != 'active' or deadline is None
            or (now or datetime.now(timezone.utc)) >= deadline or runtime['remaining_seconds'] <= 0):
        raise ValueError('DRAFT_UNAVAILABLE')
    if cycle['assignment_id'] is not None:
        assignment = connection.execute('SELECT status,revoked_at FROM organization_assessment_assignments WHERE id=%s',
                                         (cycle['assignment_id'],)).fetchone()
        if not assignment or assignment['status'] != 'active' or assignment['revoked_at'] is not None:
            raise ValueError('DRAFT_UNAVAILABLE')
    if situation['status'] == 'active':
        turn = connection.execute('SELECT turn_id FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s ORDER BY sequence_no DESC LIMIT 1',
                                  (situation['id'],)).fetchone()
        slot_id = 'dialogue:' + (str(turn['turn_id']) if turn else 'start')
    elif situation['status'] == 'scenario_ended':
        question = connection.execute("""SELECT d.id,q.question_turn_id FROM m7_clarification_decisions d
            JOIN m7_clarification_deliveries q ON q.decision_id=d.id
            WHERE assessment_situation_db_id=%s AND status='ASK'
            AND d.c54_revision_id=(SELECT id FROM m6_c54_revisions WHERE as_db_id=%s AND mode='interim'
                ORDER BY created_at DESC,id DESC LIMIT 1)
            AND NOT EXISTS(SELECT 1 FROM m7_clarification_responses r WHERE r.decision_id=d.id)
            ORDER BY d.created_at DESC LIMIT 1""", (situation['id'], situation['id'])).fetchone()
        if not question:
            raise ValueError('DRAFT_UNAVAILABLE')
        slot_id = f"clarification:{question['id']}:{question['question_turn_id']}"
    else:
        raise ValueError('DRAFT_UNAVAILABLE')
    return {'owner_id': str(owner_user_id), 'cycle_id': str(cycle['cycle_id']),
            'assessment_situation_id': assessment_situation_id, 'slot_id': slot_id,
            'as_db_id': situation['id'], 'expires_at': deadline}


def _projection(identity, row):
    return {key: value for key, value in identity.items() if key != 'as_db_id'} | {
        'version': row['version'] if row else 0, 'revision': row['revision'] if row else '',
        'text': row['content_text'] if row else ''}


def read(connection, **identity):
    current = scope(connection, **identity)
    # The regular queue maintenance deletes expired rows. Admission above never
    # returns expired input and does not mutate Cycle/time/presence.
    row = connection.execute('SELECT * FROM assessment_answer_drafts WHERE assessment_situation_db_id=%s AND owner_user_id=%s AND slot_id=%s',
                             (current['as_db_id'], identity['owner_user_id'], current['slot_id'])).fetchone()
    return _projection(current, row)


def save(connection, *, slot_id, expected_version, revision, text, **identity):
    current = scope(connection, **identity)
    if slot_id != current['slot_id']:
        raise ValueError('DRAFT_SLOT_CHANGED')
    if len(text) > 10000 or expected_version < 0 or not revision or len(revision) > 200:
        raise ValueError('DRAFT_INVALID')
    params = (current['as_db_id'], identity['owner_user_id'], slot_id)
    connection.execute('''INSERT INTO assessment_answer_drafts(assessment_situation_db_id,owner_user_id,slot_id,expires_at)
        VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING''', (*params, current['expires_at']))
    row = connection.execute('SELECT * FROM assessment_answer_drafts WHERE assessment_situation_db_id=%s AND owner_user_id=%s AND slot_id=%s FOR UPDATE', params).fetchone()
    if row['consumed']:
        raise ValueError('DRAFT_SLOT_CHANGED')
    # A lost acknowledgement can be retried with exactly the same revision.
    if row['revision'] == revision:
        if row['content_text'] == text:
            return _projection(current, row)
        raise ValueError('DRAFT_REVISION_CONFLICT')
    if row['version'] != expected_version:
        raise ValueError('DRAFT_VERSION_CONFLICT')
    row = connection.execute('''UPDATE assessment_answer_drafts SET content_text=%s,revision=%s,version=version+1
        WHERE assessment_situation_db_id=%s AND owner_user_id=%s AND slot_id=%s RETURNING *''',
        (text, revision, *params)).fetchone()
    return _projection(current, row)


def consume(connection, *, assessment_situation_id, owner_user_id, slot_id, revision,
            request_id, turn_id, clarification_id=None, **_ignored):
    """Clear only the sent revision after an independent committed receipt read."""
    from Api.assessment_answer_status import read as read_answer
    receipt = read_answer(connection, assessment_situation_id=assessment_situation_id,
                          request_id=request_id, turn_id=turn_id, clarification_id=clarification_id)
    if receipt['status'] != 'accepted':
        raise ValueError('DRAFT_ANSWER_NOT_ACCEPTED')
    situation = _as_row(connection, assessment_situation_id, lock=True)
    if clarification_id:
        question = connection.execute('SELECT question_turn_id FROM m7_clarification_deliveries WHERE decision_id=%s',
                                      (clarification_id,)).fetchone()
        accepted_slot = f"clarification:{clarification_id}:{question['question_turn_id']}" if question else None
    else:
        preceding = connection.execute('''SELECT turn_id FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s
            AND sequence_no < (SELECT sequence_no FROM m5_dialogue_turns WHERE turn_id=%s)
            ORDER BY sequence_no DESC LIMIT 1''', (situation['id'], turn_id)).fetchone()
        accepted_slot = 'dialogue:' + (str(preceding['turn_id']) if preceding else 'start')
    if slot_id != accepted_slot:
        raise ValueError('DRAFT_SLOT_CHANGED')
    connection.execute('''UPDATE assessment_answer_drafts SET content_text='',revision='',version=version+1,consumed=TRUE
        WHERE assessment_situation_db_id=%s AND owner_user_id=%s AND slot_id=%s AND revision=%s AND NOT consumed''',
        (situation['id'], owner_user_id, slot_id, revision))
    return {'status': 'accepted'}
