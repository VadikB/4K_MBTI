"""Independent branch/identity tests for the narrow answer readback.

No provider/DB calls; owner route is tested separately.
The foreign-AS collision case intentionally fails against an unscoped M7 lookup.
"""
from uuid import UUID, uuid4

import pytest

from Api import assessment_answer_status as status


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    """Small relational fake; foreign M7 answers are visible to unscoped SQL."""
    def __init__(self, *, situation_id, cycle_id, turns=(), responses=(),
                 decision=None, operation=None):
        self.situation_id = situation_id
        self.cycle_id = cycle_id
        self.turns = list(turns)
        self.responses = list(responses)
        self.decision = decision
        self.operation = operation
        self.queries = []

    def execute(self, sql, params=()):
        query = ' '.join(sql.split())
        self.queries.append((query, params))
        assert query.startswith('SELECT '), query  # Readback has no writes/DDL.
        if 'SELECT cycle_id FROM m5_cycles' in query:
            return Result([{'cycle_id': UUID(self.cycle_id)}])
        if 'LEFT JOIN m7_clarification_responses' in query:
            if self.decision is None:
                return Result([])
            did, aid = params
            if str(did) != str(self.decision['id']) or aid != self.situation_id:
                return Result([])
            return Result([self.decision])
        if 'FROM m5_dialogue_turns' in query:
            aid, request_id, turn_id = params
            return Result([{key: t[key] for key in ('turn_id', 'request_id', 'speaker_type', 'content_text')}
                           for t in self.turns if t['assessment_situation_db_id'] == aid
                           and (t['request_id'] == request_id or t['turn_id'] == turn_id)])
        if 'FROM m7_clarification_responses' in query:
            # Model the actual global UNIQUE answer_turn_id and decision AS.
            turn_id = params[0]
            rows = [r for r in self.responses if r['answer_turn_id'] == turn_id]
            if 'assessment_situation_db_id' in query:
                rows = [r for r in rows if r['assessment_situation_db_id'] == params[-1]]
            return Result(rows)
        if 'FROM m5_turn_operations' in query:
            return Result([self.operation] if self.operation else [])
        raise AssertionError(f'Unexpected SQL: {query}')


@pytest.fixture
def setup_status(monkeypatch):
    aid, cid, tid = str(uuid4()), str(uuid4()), str(uuid4())
    situation = {'id': 31, 'cycle_db_id': 41, 'assessment_situation_id': aid,
                 'status': 'closed', 'session_db_id': 51}
    locks = []

    def load(connection, actual_id, *, lock=False):
        assert actual_id == aid
        locks.append(lock)
        return situation

    monkeypatch.setattr(status, '_as_row', load)
    turn = {'assessment_situation_db_id': 31, 'turn_id': UUID(tid),
            'request_id': 'lost-response-key', 'speaker_type': 'assessee',
            'content_text': 'Сохранённый ответ'}

    def make(*, turns=(turn,), responses=(), decision=None, operation=None):
        c = Connection(situation_id=31, cycle_id=cid, turns=turns,
                       responses=responses, decision=decision, operation=operation)
        return c

    return make, aid, cid, tid, turn, locks


def call(c, aid, tid, clarification_id=None):
    return status.read(c, assessment_situation_id=aid,
                       request_id='lost-response-key', turn_id=tid,
                       clarification_id=clarification_id)


@pytest.mark.parametrize('processing', ['pending', 'applied', 'failed', 'rejected_late'])
def test_committed_turn_remains_accepted_in_every_processing_state(setup_status, processing):
    make, aid, cid, tid, turn, locks = setup_status
    c = make(operation={'status': processing, 'turn_id': UUID(tid)})
    value = call(c, aid, tid)
    assert value['status'] == 'accepted'
    assert value['processing_status'] == processing
    assert value['cycle_id'] == cid
    assert value['assessment_situation_id'] == aid
    assert value['turn'] == {'turn_id': tid, 'request_id': 'lost-response-key',
                             'speaker_type': 'assessee', 'content_text': turn['content_text']}
    assert locks == [True]


def test_legacy_committed_turn_without_detached_operation_is_accepted(setup_status):
    make, aid, _cid, tid, _turn, _locks = setup_status
    assert call(make(), aid, tid)['processing_status'] == 'applied'


def test_absent_has_no_turn_and_no_processing_success(setup_status):
    make, aid, _cid, tid, _turn, locks = setup_status
    value = call(make(turns=()), aid, tid)
    assert value['status'] == 'absent'
    assert value['turn'] is None
    assert value['processing_status'] is None
    assert locks == [True]


@pytest.mark.parametrize('change', [
    {'request_id': 'another-key'},
    {'turn_id': uuid4()},
    {'speaker_type': 'character'},
    {'speaker_type': 'assessment'},
])
def test_partial_identity_match_is_conflict(setup_status, change):
    make, aid, _cid, tid, turn, _locks = setup_status
    with pytest.raises(ValueError, match='ANSWER_STATUS_IDENTITY_CONFLICT'):
        call(make(turns=({**turn, **change},)), aid, tid)


def test_request_and_turn_matching_different_rows_is_conflict(setup_status):
    make, aid, _cid, tid, turn, _locks = setup_status
    rows = [{**turn, 'turn_id': uuid4()}, {**turn, 'request_id': 'second-key'}]
    with pytest.raises(ValueError, match='ANSWER_STATUS_IDENTITY_CONFLICT'):
        call(make(turns=rows), aid, tid)


def test_detached_operation_cannot_reference_another_turn(setup_status):
    make, aid, _cid, tid, _turn, _locks = setup_status
    with pytest.raises(ValueError, match='ANSWER_STATUS_IDENTITY_CONFLICT'):
        call(make(operation={'status': 'applied', 'turn_id': uuid4()}), aid, tid)


def test_m7_answer_requires_exact_original_decision(setup_status):
    make, aid, _cid, tid, _turn, _locks = setup_status
    did = uuid4()
    decision = {'id': did, 'request_id': 'lost-response-key',
                'answer_turn_id': UUID(tid), 'outcome': 'answered'}
    response = {'decision_id': did, 'answer_turn_id': UUID(tid),
                'assessment_situation_db_id': 31}
    value = call(make(decision=decision, responses=[response]), aid, tid, str(did))
    assert value['status'] == 'accepted'
    assert value['processing_status'] == 'answered'
    # Replaying the M7 identity through the normal Turn endpoint is invalid.
    with pytest.raises(ValueError, match='ANSWER_STATUS_IDENTITY_CONFLICT'):
        call(make(responses=[response]), aid, tid)


@pytest.mark.parametrize('change', [
    {'request_id': 'changed-key'},
    {'answer_turn_id': uuid4()},
    {'outcome': 'refused'},
])
def test_m7_receipt_identity_mismatch_is_conflict(setup_status, change):
    make, aid, _cid, tid, _turn, _locks = setup_status
    did = uuid4()
    decision = {'id': did, 'request_id': 'lost-response-key',
                'answer_turn_id': UUID(tid), 'outcome': 'answered', **change}
    response = {'decision_id': did, 'answer_turn_id': UUID(tid),
                'assessment_situation_db_id': 31}
    with pytest.raises(ValueError, match='ANSWER_STATUS_IDENTITY_CONFLICT'):
        call(make(decision=decision, responses=[response]), aid, tid, str(did))


def test_foreign_clarification_is_not_found_even_for_own_turn(setup_status):
    make, aid, _cid, tid, _turn, _locks = setup_status
    with pytest.raises(ValueError, match='ANSWER_STATUS_CLARIFICATION_NOT_FOUND'):
        call(make(), aid, tid, str(uuid4()))


def test_unanswered_m7_with_missing_turn_is_absent_not_accepted(setup_status):
    make, aid, _cid, tid, _turn, _locks = setup_status
    did = uuid4()
    decision = {'id': did, 'request_id': None, 'answer_turn_id': None, 'outcome': None}
    value = call(make(turns=(), decision=decision), aid, tid, str(did))
    assert value['status'] == 'absent'


def test_m7_receipt_without_its_turn_is_conflict(setup_status):
    make, aid, _cid, tid, _turn, _locks = setup_status
    did = uuid4()
    decision = {'id': did, 'request_id': 'lost-response-key',
                'answer_turn_id': UUID(tid), 'outcome': 'answered'}
    with pytest.raises(ValueError, match='ANSWER_STATUS_IDENTITY_CONFLICT'):
        call(make(turns=(), decision=decision), aid, tid, str(did))


def test_foreign_as_m7_answer_with_same_turn_uuid_does_not_poison_normal_readback(setup_status):
    make, aid, _cid, tid, _turn, _locks = setup_status
    # m5_dialogue_turns only has UNIQUE(as_db_id, turn_id). A distinct AS may
    # legitimately use the same UUID; its M7 row must not affect this owner.
    foreign_response = {'decision_id': uuid4(), 'answer_turn_id': UUID(tid),
                        'assessment_situation_db_id': 999}
    value = call(make(responses=[foreign_response]), aid, tid)
    assert value['status'] == 'accepted'
