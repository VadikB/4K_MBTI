"""EXEC-FIX-05: actual owned PG, HTTP, persisted boundaries and repeat fencing."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from time import monotonic, sleep
from uuid import uuid4

import pytest

from Api import m10_orchestration, m7_completion
from tests.integration.test_exec_fix01_clarification_db import (
    _counts, _request, _resolve, current, http,
)
from tests.integration.test_m6_evidence_db import database

pytestmark = pytest.mark.integration

CASES = [
    (-5, -1, 'time_budget'),
    (-1, -5, 'calendar_deadline'),
    (-5, 60, 'time_budget'),
    (None, -5, 'calendar_deadline'),
    (None, 60, None),
    (-5, -5, 'calendar_deadline'),
]


def _limits(c, state, budget_offset, calendar_offset):
    """Controlled closed fractional intervals; no HTTP timing assumptions."""
    now = c.execute('SELECT clock_timestamp() AS value').fetchone()['value']
    calendar_at = now + timedelta(seconds=calendar_offset)
    c.execute('UPDATE m5_cycles SET started_at=%s WHERE id=%s',
              (calendar_at - timedelta(seconds=259200), state['cycle_db']))
    c.execute('UPDATE m5_cycle_time_intervals SET ended_at=started_at WHERE cycle_db_id=%s',
              (state['cycle_db'],))
    budget_at = now + timedelta(seconds=budget_offset) if budget_offset is not None else None
    second_start = (budget_at - timedelta(seconds=3600.2) if budget_at
                    else now - timedelta(seconds=3601.1))
    first_start = second_start - timedelta(seconds=3609.8)
    first_end = first_start + timedelta(seconds=3599.8)
    intervals = [
        ('collecting', first_start, first_end),
        ('authorized_pause', first_end, first_end + timedelta(seconds=5)),
        ('blocking_system_wait', first_end + timedelta(seconds=5), second_start),
        ('collecting', second_start, second_start + timedelta(seconds=3600.3 if budget_at else 3600.1)),
    ]
    for kind, start, end in intervals:
        c.execute('''INSERT INTO m5_cycle_time_intervals
            (cycle_db_id,session_db_id,interval_type,started_at,ended_at,reason)
            VALUES(%s,%s,%s,%s,%s,'exec_fix05_controlled')''',
            (state['cycle_db'], state['session_db'], kind, start, end))
    return budget_at, calendar_at


def _effects(c):
    return {**_counts(c), **c.execute('''SELECT
        (SELECT count(*) FROM m7_transition_events) AS events,
        (SELECT count(*) FROM m7_c46_revisions) AS c46,
        (SELECT count(*) FROM m7_completion_commands) AS commands''').fetchone()}


def _assert_saved(c, state, result, reason, effective_at):
    assert result['reason'] == reason
    cycle = c.execute('SELECT * FROM m5_cycles WHERE id=%s', (state['cycle_db'],)).fetchone()
    session = c.execute('SELECT * FROM m5_cycle_sessions WHERE id=%s', (state['session_db'],)).fetchone()
    event = c.execute('SELECT * FROM m7_transition_events WHERE id=%s', (result['event_id'],)).fetchone()
    assert cycle['status'] == 'collection_closed' and cycle['close_reason'] == reason
    assert session['status'] == 'completed' and session['close_reason'] == reason
    assert event['reason'] == reason and event['effective_at'] == effective_at
    assert event['boundary_json']['limit_kind'] == reason
    assert event['effective_at'] < event['processed_at']
    saved = m7_completion.read_c46(c, state['cycle_id'])
    assert str(saved['id']) == result['c46_revision_id']
    assert saved['payload_json']['collection']['reason'] == reason
    assert saved['payload_json']['collection']['closed_at'] == cycle['collection_closed_at'].isoformat()
    assert cycle['collection_closed_at'] > effective_at
    assert len(result['final_handoff_ids']) == 1
    assert c.execute('SELECT count(*) AS n FROM m7_finalization_outbox').fetchone()['n'] == 1
    assert c.execute('SELECT count(*) AS n FROM m7_c46_revisions').fetchone()['n'] == 1
    assert c.execute('SELECT count(*) AS n FROM m7_transition_events').fetchone()['n'] == 1


@pytest.mark.parametrize('budget_offset,calendar_offset,reason', CASES)
@pytest.mark.parametrize('worker', [False, True], ids=['complete', 'late-worker'])
def test_first_deadline_persisted_once(current, budget_offset, calendar_offset, reason, worker):
    with current['factory']() as c:
        budget_at, calendar_at = _limits(c, current, budget_offset, calendar_offset)
        before = _effects(c)
        request = dict(cycle_id=current['cycle_id'], key='automatic-expiry' if worker else 'exec05',
                       action='time_limit', reason='automatic' if worker else 'probe', initiated_by=99)
        if reason is None:
            if worker:
                assert m7_completion.expire_due_cycles(c) == []
            else:
                with pytest.raises(ValueError, match='M7_TIME_LIMIT_NOT_REACHED'):
                    m7_completion.complete(c, **request)
            assert _effects(c) == before
            return
        result = m7_completion.expire_due_cycles(c)[0] if worker else m7_completion.complete(c, **request)
        c.commit()
        effective_at = budget_at if reason == 'time_budget' else calendar_at
        _assert_saved(c, current, result, reason, effective_at)
        after = _effects(c)
        assert m7_completion.complete(c, **request) == result
        with pytest.raises(ValueError, match='IDEMPOTENCY_CONFLICT'):
            m7_completion.complete(c, **{**request, 'reason': 'changed'})
        with pytest.raises(ValueError, match='M7_COLLECTION_CLOSED'):
            m7_completion.complete(c, **{**request, 'key': 'new-command'})
        assert m7_completion.expire_due_cycles(c) == []
        assert _effects(c) == after
        _assert_saved(c, current, result, reason, effective_at)


@pytest.mark.parametrize('budget_offset,calendar_offset,reason', CASES)
def test_http_resume_reports_and_persists_first_deadline(current, http, budget_offset, calendar_offset, reason):
    with current['factory']() as c:
        m7_completion.control(c, cycle_id=current['cycle_id'], key='pause', action='pause',
                              reason='authorized', initiated_by=99)
        budget_at, calendar_at = _limits(c, current, budget_offset, calendar_offset)
        c.commit()
        before = _effects(c)
    response = http.post('/users/assessment/m7/cycles/' + current['cycle_id'] + '/control',
                         json={'action': 'resume', 'reason': 'continue', 'idempotency_key': 'resume'})
    assert response.status_code == 200, response.text
    status = http.get('/users/assessment/m7/cycles/' + current['cycle_id'])
    assert status.status_code == 200, status.text
    with current['factory']() as c:
        if reason is None:
            assert response.json()['cycle_status'] == 'active'
            assert _effects(c)['c46'] == before['c46']
            assert _effects(c)['outbox'] == before['outbox']
        else:
            result = response.json()
            # The earlier pause has no transition event/C46; expiry creates one.
            _assert_saved(c, current, result, reason, budget_at if reason == 'time_budget' else calendar_at)
            assert status.json()['close_reason'] == reason
            effects = _effects(c)
            assert m7_completion.expire_due_cycles(c) == []
            assert _effects(c) == effects


def test_http_accepted_answer_replays_after_both_limits_and_new_answer_is_blocked(current, http):
    decision = _resolve(current)
    request = _request(decision)
    endpoint = '/users/assessment/m7/clarifications/' + str(decision['id']) + '/answers'
    body = {k: v for k, v in request.items() if k != 'decision_id'}
    with current['factory']() as c:
        m10_orchestration.ensure_schema(c)
        _limits(c, current, None, 60)
        c.commit()
    accepted = http.post(endpoint, json=body)
    assert accepted.status_code == 200, accepted.text
    with current['factory']() as c:
        _limits(c, current, -5, -1)
        c.commit()
    # Replay is allowed already after expiry, before a worker has processed it.
    replay = http.post(endpoint, json=body)
    assert replay.status_code == 200 and replay.json()['answer_turn_id'] == accepted.json()['answer_turn_id']
    closure = http.post('/users/assessment/m7/cycles/' + current['cycle_id'] + '/control',
                        json={'action': 'resume', 'reason': 'continue', 'idempotency_key': 'expired-resume'})
    assert closure.status_code == 200 and closure.json()['reason'] == 'time_budget', closure.text
    with current['factory']() as c:
        effects = _effects(c)
    replay = http.post(endpoint, json=body)
    assert replay.status_code == 200 and replay.json()['answer_turn_id'] == accepted.json()['answer_turn_id']
    changed = http.post(endpoint, json={**body, 'content': 'changed'})
    assert changed.status_code == 409, changed.text
    new = http.post(endpoint, json={**body, 'request_id': 'new', 'turn_id': str(uuid4())})
    assert new.status_code == 409, new.text
    with current['factory']() as c:
        assert _effects(c) == effects


@pytest.mark.parametrize('budget_offset,calendar_offset,reason', CASES[:2])
def test_open_collecting_interval_uses_same_observation_as_calendar(current, budget_offset, calendar_offset, reason):
    with current['factory']() as c:
        budget_at, calendar_at = _limits(c, current, budget_offset, calendar_offset)
        c.execute("""UPDATE m5_cycle_time_intervals SET ended_at=NULL WHERE id=(
            SELECT max(id) FROM m5_cycle_time_intervals WHERE cycle_db_id=%s
            AND interval_type='collecting' AND reason='exec_fix05_controlled')""", (current['cycle_db'],))
        result = m7_completion.complete(c, cycle_id=current['cycle_id'], key='open-interval',
                                         action='time_limit', reason='probe', initiated_by=99)
        c.commit()
        _assert_saved(c, current, result, reason, budget_at if reason == 'time_budget' else calendar_at)


def test_http_new_answer_after_both_limits_is_rejected_without_effects(current, http):
    decision = _resolve(current)
    request = _request(decision)
    with current['factory']() as c:
        _limits(c, current, -5, -1)
        c.commit()
        before = _effects(c)
    response = http.post('/users/assessment/m7/clarifications/' + str(decision['id']) + '/answers',
                         json={k: v for k, v in request.items() if k != 'decision_id'})
    assert response.status_code == 409, response.text
    with current['factory']() as c:
        assert _effects(c) == before


def test_complete_observes_both_limits_after_actual_cycle_lock_wait(current):
    with current['factory']() as c:
        _limits(c, current, None, 60)
        c.commit()

    def complete_after_lock():
        with current['factory']() as c:
            c.execute("SET application_name='exec05_complete_waiter'")
            c.execute("SET lock_timeout='10s'")
            result = m7_completion.complete(c, cycle_id=current['cycle_id'], key='lock-wait',
                                             action='time_limit', reason='probe', initiated_by=99)
            c.commit()
            return result

    with current['factory']() as holder:
        holder.execute('SELECT id FROM m5_cycles WHERE id=%s FOR UPDATE', (current['cycle_db'],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(complete_after_lock)
            timeout = monotonic() + 5
            waiting = None
            while monotonic() < timeout:
                with current['factory']() as observer:
                    waiting = observer.execute("SELECT 1 FROM pg_stat_activity WHERE application_name='exec05_complete_waiter' AND wait_event_type='Lock'").fetchone()
                if waiting: break
                sleep(.05)
            assert waiting, 'complete did not wait on the actual Cycle lock'
            budget_at, _ = _limits(holder, current, -5, -1)
            holder.commit()
            result = future.result(timeout=10)
    with current['factory']() as c:
        _assert_saved(c, current, result, 'time_budget', budget_at)
