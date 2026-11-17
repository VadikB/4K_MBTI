"""Existing continuation consumption remains a separate, replayable command."""
from copy import deepcopy
from uuid import uuid4

import pytest
from Api import m5_cycle_runtime, m7_completion
from Api.m5_case_runtime import checksum

pytestmark = pytest.mark.unit


class Row:
    def __init__(self, value): self.value = value
    def fetchone(self): return deepcopy(self.value)


class SavedIntent:
    def __init__(self):
        self.intent_id = str(uuid4())
        self.cycle = {'id': 1, 'cycle_id': str(uuid4()), 'status': 'interrupted',
                      'profile_ref_json': {'checksum': 'fixed'}, 'target_set_checksum': 'targets'}
        snapshot = {'profile_ref': self.cycle['profile_ref_json'], 'target_set_checksum': 'targets'}
        self.intent = {'id': self.intent_id, 'status': 'pending',
                       'snapshot_json': snapshot, 'snapshot_checksum': checksum(snapshot)}
        self.keys = {}
        self.session = {'id': 22, 'session_id': str(uuid4()), 'status': 'prepared', 'ordinal': 2}
        self.created = 0
        self.old_as = {'status': 'closed', 'materials': ['saved'], 'evidence': ['original']}

    def execute(self, sql, params):
        if 'SELECT * FROM m7_additional_session_keys' in sql: return Row(self.keys.get(params[1]))
        if 'SELECT * FROM m5_cycle_sessions' in sql: return Row(self.session)
        if 'SELECT * FROM m7_continuation_intents' in sql: return Row(self.intent)
        if 'UPDATE m7_continuation_intents' in sql:
            self.intent['status']='consumed'
            return Row(None)
        if 'INSERT INTO m7_additional_session_keys' in sql:
            self.keys[params[1]]={'request_checksum': params[2], 'session_db_id': params[3]}
            return Row(None)
        raise AssertionError(sql)

    def create_session(self, *a, **k):
        self.created += 1
        self.cycle['status']='active'
        return deepcopy(self.session)

    def consume(self, key='additional', intent_id=None):
        return m7_completion.create_additional_session(self, cycle_id=self.cycle['cycle_id'],
            intent_id=intent_id or self.intent_id, key=key, created_by=7)


@pytest.fixture
def saved(monkeypatch):
    c = SavedIntent()
    monkeypatch.setattr(m7_completion, '_cycle', lambda *a, **k: deepcopy(c.cycle))
    monkeypatch.setattr(m7_completion, '_effective_limit', lambda *a: (None, None))
    monkeypatch.setattr(m5_cycle_runtime, 'create_session', c.create_session)
    return c


def test_saved_pending_intent_is_consumed_once_even_after_lost_response(saved):
    old_as = deepcopy(saved.old_as)
    first = saved.consume()
    assert saved.consume() == first
    assert saved.created == 1
    assert saved.intent['status'] == 'consumed'
    assert saved.old_as == old_as
    with pytest.raises(ValueError, match='M7_ADDITIONAL_SESSION_NOT_ALLOWED'):
        saved.consume(key='second-independent-command')
    with pytest.raises(ValueError, match='IDEMPOTENCY_CONFLICT'):
        saved.consume(intent_id=str(uuid4()))
    assert saved.created == 1


@pytest.mark.parametrize('defect', ['no_intent', 'checksum', 'profile', 'target', 'closed_cycle', 'deadline'])
def test_invalid_saved_intent_does_not_create_a_session(saved, monkeypatch, defect):
    if defect=='no_intent': saved.intent=None
    if defect=='checksum': saved.intent['snapshot_checksum']='corrupt'
    if defect=='profile': saved.cycle['profile_ref_json']={'checksum': 'changed'}
    if defect=='target': saved.cycle['target_set_checksum']='changed'
    if defect=='closed_cycle': saved.cycle['status']='collection_closed'
    if defect=='deadline': monkeypatch.setattr(m7_completion, '_effective_limit', lambda *a: ('calendar_deadline', 'boundary'))
    with pytest.raises(ValueError, match='M7_ADDITIONAL_SESSION_NOT_ALLOWED|COMPOSITION_MISMATCH'):
        saved.consume()
    assert saved.created == 0
