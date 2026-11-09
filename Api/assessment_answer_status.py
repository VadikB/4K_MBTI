"""Owner-route readback for one uncertain M5/M7 answer, including closed AS.

No write admission is performed: this reads a committed receipt and never creates
or replays a Turn. The route verifies ownership before calling this helper.
"""
from uuid import UUID

from Api.m5_scenario_runtime import _as_row


def read(connection, *, assessment_situation_id: str, request_id: str,
         turn_id: str, clarification_id: str | None = None) -> dict:
    # Share the writers' Cycle -> AS lock order. An in-flight transactional M7
    # answer finishes before absence is reported. M5's committed provider phase
    # is visible as pending/failed/applied, never as an absent answer.
    situation = _as_row(connection, assessment_situation_id, lock=True)
    result = {
        'cycle_id': str(connection.execute('SELECT cycle_id FROM m5_cycles WHERE id=%s',
                                           (situation['cycle_db_id'],)).fetchone()['cycle_id']),
        'assessment_situation_id': assessment_situation_id,
        'request_id': request_id, 'turn_id': turn_id, 'clarification_id': clarification_id,
        'status': 'absent', 'processing_status': None, 'turn': None,
    }
    decision = None
    if clarification_id:
        decision = connection.execute('''SELECT d.id,r.request_id,r.answer_turn_id,r.outcome
            FROM m7_clarification_decisions d LEFT JOIN m7_clarification_responses r ON r.decision_id=d.id
            WHERE d.id=%s AND d.assessment_situation_db_id=%s''',
            (UUID(clarification_id), situation['id'])).fetchone()
        if not decision:
            raise ValueError('ANSWER_STATUS_CLARIFICATION_NOT_FOUND')
    turns = connection.execute('''SELECT turn_id,request_id,speaker_type,content_text
        FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s AND (request_id=%s OR turn_id=%s)''',
        (situation['id'], request_id, UUID(turn_id))).fetchall()
    if not turns:
        if decision and decision['request_id'] == request_id:
            raise ValueError('ANSWER_STATUS_IDENTITY_CONFLICT')
        return result
    if len(turns) != 1:
        raise ValueError('ANSWER_STATUS_IDENTITY_CONFLICT')
    turn = turns[0]
    if (turn['request_id'] != request_id or str(turn['turn_id']) != turn_id
            or turn['speaker_type'] != 'assessee'):
        raise ValueError('ANSWER_STATUS_IDENTITY_CONFLICT')
    response = connection.execute('''SELECT r.decision_id FROM m7_clarification_responses r
        JOIN m7_clarification_decisions d ON d.id=r.decision_id
        WHERE r.answer_turn_id=%s AND d.assessment_situation_db_id=%s''',
        (UUID(turn_id), situation['id'])).fetchone()
    if clarification_id:
        if (not response or str(response['decision_id']) != clarification_id
                or decision['outcome'] != 'answered' or decision['request_id'] != request_id
                or str(decision['answer_turn_id']) != turn_id):
            raise ValueError('ANSWER_STATUS_IDENTITY_CONFLICT')
        processing = 'answered'
    else:
        if response:
            raise ValueError('ANSWER_STATUS_IDENTITY_CONFLICT')
        operation = connection.execute('''SELECT status,turn_id FROM m5_turn_operations
            WHERE assessment_situation_db_id=%s AND request_id=%s''',
            (situation['id'], request_id)).fetchone()
        if operation and str(operation['turn_id']) != turn_id:
            raise ValueError('ANSWER_STATUS_IDENTITY_CONFLICT')
        processing = operation['status'] if operation else 'applied'
    return {**result, 'status': 'accepted', 'processing_status': processing,
            'turn': {**dict(turn), 'turn_id': str(turn['turn_id'])}}
