"""Real PostgreSQL ordinary receipt replay across admission boundaries."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event
from uuid import uuid4

import pytest

from Api import m5_scenario_runtime as runtime
from Api.m5_rule_engine import ControlledCharacterAdapter, ControlledSemanticAdapter
from tests.integration.test_m7_cycle_planner_db import active_cycle, db

pytestmark = pytest.mark.integration


def send(factory, identity, semantic=None):
    return runtime.submit_turn_detached(**identity, semantic_adapter=semantic or ControlledSemanticAdapter({}),
        character_adapter=ControlledCharacterAdapter({}), connection_factory=factory)


def setup(factory):
    with factory() as c:
        _plan, shown = active_cycle(c)
        as_id = str(shown['decision']['assessment_situation_id'])
        c.commit()
    return {'assessment_situation_id': as_id, 'request_id': 'exec03-applied-' + uuid4().hex,
            'turn_id': str(uuid4()), 'content': 'Synthetic exact receipt with a real saved Turn'}


def counts(factory):
    with factory() as c:
        return tuple(c.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in (
            'm5_dialogue_turns', 'm5_scenario_events', 'm5_rule_decisions', 'm5_ai_attempts',
            'm5_c54_receipts', 'm5_turn_operations', 'm5_c45_handoffs'))


@pytest.mark.parametrize('boundary', ['scenario_ended', 'closed', 'cycle_closed', 'budget', 'calendar', 'paused'])
def test_applied_receipt_replays_before_new_write_guards_without_any_material_or_provider(db, boundary):
    identity = setup(db)
    original = send(db, identity)
    with db() as c:
        if boundary in {'scenario_ended', 'closed', 'paused'}:
            runtime.transition(c, assessment_situation_id=identity['assessment_situation_id'],
                action='pause' if boundary == 'paused' else 'scenario_end', reason='exec03 boundary', request_id='boundary')
            if boundary == 'closed':
                runtime.transition(c, assessment_situation_id=identity['assessment_situation_id'],
                    action='close', reason='exec03 boundary', request_id='close')
        elif boundary == 'cycle_closed':
            c.execute("UPDATE m5_cycles SET status='collection_closed'")
        elif boundary == 'budget':
            c.execute("""UPDATE m5_cycle_time_intervals SET started_at=NOW()-(
                (SELECT time_budget_seconds+1 FROM m5_cycles)*INTERVAL '1 second')
                WHERE interval_type='collecting' AND ended_at IS NULL""")
        else:
            c.execute("UPDATE m5_cycles SET started_at=NOW()-((calendar_window_seconds+1)*INTERVAL '1 second')")
        c.commit()
    before = counts(db)

    class NoProvider(ControlledSemanticAdapter):
        def decide(self, **_kwargs):
            raise AssertionError('Applied replay called a provider')

    with ThreadPoolExecutor(max_workers=2) as pool:
        replays = list(pool.map(lambda _: send(db, identity, NoProvider({})), range(2)))
    expected = json.loads(json.dumps({**original, 'idempotent': True}, default=str))
    assert replays == [expected, expected]
    with pytest.raises(ValueError, match='M5_IDEMPOTENCY_PAYLOAD_MISMATCH'):
        send(db, {**identity, 'content': identity['content'] + ' changed'})
    with pytest.raises(ValueError, match='M5_IDEMPOTENCY_PAYLOAD_MISMATCH'):
        send(db, {**identity, 'turn_id': str(uuid4())})
    with pytest.raises(ValueError, match='M5_AS_NOT_ACTIVE|M7_COLLECTION_CLOSED|M7_TIME_LIMIT_REACHED'):
        send(db, {**identity, 'request_id': uuid4().hex, 'turn_id': str(uuid4())})
    assert counts(db) == before


def test_pending_commit_retry_then_late_original_finalization_has_one_turn_and_one_attempt(db):
    identity = setup(db)
    entered, release = Event(), Event()

    class HeldProvider(ControlledSemanticAdapter):
        def decide(self, **kwargs):
            entered.set()
            assert release.wait(timeout=10)
            return super().decide(**kwargs)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(send, db, identity, HeldProvider({}))
        assert entered.wait(timeout=10)
        try:
            with db() as c:
                assert c.execute("SELECT count(*) AS n FROM m5_dialogue_turns WHERE request_id=%s",
                                 (identity['request_id'],)).fetchone()['n'] == 1
            with pytest.raises(ValueError, match='M7_BLOCKING_SYSTEM_WAIT|M5_TURN_OPERATION_IN_PROGRESS'):
                send(db, identity)
        finally:
            release.set()
        result = first.result(timeout=10)
    before = counts(db)
    assert send(db, identity)['turn'] == json.loads(json.dumps(result['turn'], default=str))
    assert counts(db) == before
    with db() as c:
        saved = c.execute('SELECT status,attempt_no FROM m5_turn_operations WHERE request_id=%s',
                          (identity['request_id'],)).fetchone()
        assert saved == {'status': 'applied', 'attempt_no': 1}
