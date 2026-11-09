"""Concrete unit draft: applied M5 receipt + direct detached replay fencing."""
from contextlib import contextmanager
from copy import deepcopy
from uuid import UUID, uuid4

import pytest

from Api import m5_scenario_runtime as runtime
from Api.m5_case_runtime import checksum


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute(self, sql, params=()):
        query = ' '.join(sql.split())
        self.queries.append((query, params))
        assert query.startswith('SELECT '), query
        assert 'FROM m5_turn_operations' in query
        # Reader must not create the Cycle/AS -> operation row-lock dependency.
        assert 'FOR UPDATE' not in query
        return Result(self.rows.get(tuple(params)))


@pytest.fixture
def applied(monkeypatch):
    aid, tid = str(uuid4()), str(uuid4())
    key, content = 'lost-response', 'Ранее принятый ответ'
    source = {'id': 31, 'cycle_db_id': 41, 'session_db_id': 51,
              'assessment_situation_id': UUID(aid), 'status': 'closed'}
    locks = []

    def locked_source(_connection, actual_id, *, lock=False):
        assert actual_id == aid
        assert lock is True
        locks.append(actual_id)
        return source

    monkeypatch.setattr(runtime, '_as_row', locked_source)
    original = {'assessment_situation_id': aid, 'turn': {'turn_id': tid,
                'speaker_type': 'assessee', 'content_text': content},
                'events': [{'event_id': str(uuid4()), 'sequence_no': 7}],
                'idempotent': False, 'revision': 8}
    operation = {'turn_id': UUID(tid),
                 'request_checksum': checksum({'turn_id': tid, 'content': content}),
                 'status': 'applied', 'result_json': original}
    connection = Connection({(31, key): operation})
    identity = {'assessment_situation_id': aid, 'request_id': key,
                'turn_id': tid, 'content': content}
    return connection, identity, original, operation, locks, source


def test_public_applied_reader_returns_exact_cached_result_without_modifying_it(applied):
    connection, identity, original, _op, locks, _source = applied
    before = deepcopy(original)
    value = runtime.read_applied_turn_receipt(connection, **identity)
    assert value == {**before, 'idempotent': True}
    assert original == before
    assert locks == [identity['assessment_situation_id']]
    assert connection.queries[0][1] == (31, identity['request_id'])


@pytest.mark.parametrize('change', [
    {'content': 'Изменённое содержание'},
    {'turn_id': str(uuid4())},
])
@pytest.mark.parametrize('processing', ['applied', 'pending', 'failed', 'rejected_late'])
def test_changed_content_or_turn_under_original_key_conflicts_for_all_states(applied, change, processing):
    connection, identity, _original, operation, _locks, _source = applied
    operation['status'] = processing
    with pytest.raises(ValueError, match='^M5_IDEMPOTENCY_PAYLOAD_MISMATCH$'):
        runtime.read_applied_turn_receipt(connection, **{**identity, **change})


@pytest.mark.parametrize('processing', ['pending', 'failed', 'rejected_late'])
def test_nonapplied_receipt_never_grants_replay_bypass(applied, processing):
    connection, identity, _original, operation, _locks, _source = applied
    operation['status'] = processing
    assert runtime.read_applied_turn_receipt(connection, **identity) is None


def test_absent_request_does_not_use_other_as_or_other_request_receipt(applied):
    connection, identity, _original, operation, _locks, _source = applied
    connection.rows = {(999, identity['request_id']): operation,
                       (31, 'some-other-request'): operation}
    assert runtime.read_applied_turn_receipt(connection, **identity) is None


def test_snapshot_validation_failure_is_not_bypassed(applied, monkeypatch):
    connection, identity, _original, _operation, _locks, _source = applied

    def corrupt(*_args, **_kwargs):
        raise ValueError('SNAPSHOT_INTEGRITY_FAILED')

    monkeypatch.setattr(runtime, '_as_row', corrupt)
    with pytest.raises(ValueError, match='^SNAPSHOT_INTEGRITY_FAILED$'):
        runtime.read_applied_turn_receipt(connection, **identity)
    assert connection.queries == []


@pytest.mark.parametrize('source_status', ['active', 'scenario_ended', 'closed'])
def test_detached_applied_replay_returns_before_admission_state_or_provider(applied, monkeypatch, source_status):
    connection, identity, original, _operation, locks, source = applied
    source['status'] = source_status

    def forbidden(*_args, **_kwargs):
        raise AssertionError('Applied replay attempted new admission/processing')

    monkeypatch.setattr(runtime.m5_cycle_runtime, 'assert_collecting', forbidden)
    monkeypatch.setattr(runtime, '_state', forbidden)
    monkeypatch.setattr(runtime, '_evaluate', forbidden)

    @contextmanager
    def factory():
        yield connection

    value = runtime.submit_turn_detached(**identity, semantic_adapter=forbidden,
                                        character_adapter=forbidden, connection_factory=factory)
    assert value == {**original, 'idempotent': True}
    # Works with public-helper/private-alreadylocked-row refactor.
    assert locks == [identity['assessment_situation_id']]
    assert len(connection.queries) == 1


@pytest.mark.parametrize('processing', [None, 'pending', 'failed', 'rejected_late'])
def test_detached_new_or_nonapplied_request_still_runs_collection_guard(applied, monkeypatch, processing):
    connection, identity, _original, operation, _locks, _source = applied
    if processing is None:
        connection.rows.clear()
    else:
        operation['status'] = processing
    guards = []

    def closed(_connection, **scope):
        guards.append(scope)
        raise ValueError('M7_COLLECTION_CLOSED')

    monkeypatch.setattr(runtime.m5_cycle_runtime, 'assert_collecting', closed)

    @contextmanager
    def factory():
        yield connection

    with pytest.raises(ValueError, match='^M7_COLLECTION_CLOSED$'):
        runtime.submit_turn_detached(**identity, connection_factory=factory)
    assert guards == [{'cycle_db_id': 41, 'session_db_id': 51}]
    assert len(connection.queries) == 1  # No provider/operation mutation after guard.
