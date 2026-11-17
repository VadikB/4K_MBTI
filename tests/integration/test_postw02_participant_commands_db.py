"""Persisted compatibility and atomic refusal on the existing isolated DB fixture."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from Api import m5_scenario_runtime as scenario, m7_completion as completion
from Api.m5_cycle_runtime import read_cycle
from Api.m7_return_integration import heartbeat
from tests.integration.test_m7_cycle_planner_db import active_cycle, db  # noqa: F401

pytestmark = pytest.mark.integration

TABLES = ('m5_cycles', 'm5_cycle_sessions', 'm5_assessment_situations',
          'm5_cycle_time_intervals', 'm5_scenario_events', 'm5_scenario_states',
          'm5_dialogue_turns', 'm5_c45_handoffs', 'm7_completion_commands',
          'm7_transition_events', 'm7_continuation_intents', 'm7_finalization_outbox')


def persisted(c):
    return {table: c.execute(f'SELECT to_jsonb(t) AS row FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
            for table in TABLES}


@pytest.mark.parametrize('entry', ['control', 'completion', 'transitions'])
@pytest.mark.parametrize('reason', ['user_pause', 'between_situations'])
def test_public_refusal_is_atomic_and_old_receipt_still_replays(db, entry, reason):
    with db() as c:
        plan, shown = active_cycle(c)
        cycle_id, as_id = str(plan['cycle_id']), str(shown['decision']['assessment_situation_id'])
        action = 'interrupt_for_continuation' if entry=='completion' else 'pause'
        def invoke(participant, key='manual'):
            if entry=='transitions':
                return scenario.transition(c, assessment_situation_id=as_id, action=action,
                                           reason=reason, request_id=key, participant_command=participant)
            function = completion.complete if entry=='completion' else completion.control
            return function(c, cycle_id=cycle_id, key=key, action=action, reason=reason,
                            initiated_by=99, participant_command=participant)
        before = persisted(c)
        with pytest.raises(ValueError, match='M7_PARTICIPANT_MANUAL_CONTROL_NOT_ALLOWED'):
            invoke(True)
        assert persisted(c) == before
        # Simulate a receipt produced by an earlier deployment/internal caller.
        old = invoke(False)
        after = persisted(c)
        repeated = invoke(True)
        assert repeated == ({**old, 'idempotent': True} if entry=='transitions' else old)
        assert persisted(c) == after


@pytest.mark.parametrize('entry', ['control', 'transitions'])
def test_saved_pause_recovers_same_as_once_without_new_time_budget(db, entry):
    with db() as c:
        plan, shown = active_cycle(c)
        cycle_id, as_id = str(plan['cycle_id']), str(shown['decision']['assessment_situation_id'])
        before = read_cycle(c, cycle_id)
        if entry=='control':
            completion.control(c, cycle_id=cycle_id, key='old-pause', action='pause', reason='old_user_pause', initiated_by=99)
            def resume(key='recover', reason='resume'):
                return completion.control(c, cycle_id=cycle_id, key=key, action='resume', reason=reason,
                                          initiated_by=99, participant_command=True)
        else:
            scenario.transition(c, assessment_situation_id=as_id, action='pause', reason='old_user_pause', request_id='old-pause')
            def resume(key='recover', reason='resume'):
                return scenario.transition(c, assessment_situation_id=as_id, action='resume', reason=reason,
                                           request_id=key, participant_command=True)
        snapshot = c.execute('SELECT snapshot_json,snapshot_checksum,execution_payload_json FROM m5_assessment_situations').fetchone()
        first = resume()
        after = persisted(c)
        second = resume()
        assert second == ({**first, 'idempotent': True} if entry=='transitions' else first)
        assert persisted(c) == after
        with pytest.raises(ValueError, match='IDEMPOTENCY_CONFLICT'):
            resume(reason='different')
        timing = read_cycle(c, cycle_id)
        assert timing['time_budget_seconds'] == before['time_budget_seconds']
        assert timing['calendar_deadline'] == before['calendar_deadline']
        assert timing['remaining_seconds'] <= before['remaining_seconds']
        assert c.execute('SELECT snapshot_json,snapshot_checksum,execution_payload_json FROM m5_assessment_situations').fetchone() == snapshot
        assert c.execute('SELECT status FROM m5_assessment_situations').fetchone()['status']=='active'


@pytest.mark.parametrize('defect', ['between', 'closed_as', 'recognized_absence', 'expired_lease', 'deadline', 'budget', 'blocking_wait'])
def test_public_cycle_resume_cannot_bypass_saved_recovery_constraints(db, defect):
    with db() as c:
        plan, shown = active_cycle(c)
        cycle_id, as_id = str(plan['cycle_id']), str(shown['decision']['assessment_situation_id'])
        base = datetime.now(timezone.utc)-timedelta(seconds=240)
        if defect in {'expired_lease', 'recognized_absence'}:
            c.execute('UPDATE m5_cycle_time_intervals SET started_at=%s', (base-timedelta(seconds=10),))
            heartbeat(c, cycle_id=cycle_id, owner_user_id=99, client_id=str(uuid4()), expected_as_id=as_id, received_at=base)
        completion.control(c, cycle_id=cycle_id, key='old-pause', action='pause', reason='old_user_pause', initiated_by=99)
        if defect=='between': c.execute("UPDATE m7_route_positions SET state='completed'")
        if defect=='closed_as': c.execute("UPDATE m5_assessment_situations SET status='closed'")
        if defect=='deadline': c.execute("UPDATE m5_cycles SET started_at=NOW()-INTERVAL '100 hours'")
        if defect=='budget':
            c.execute("UPDATE m5_cycle_time_intervals SET started_at=ended_at-INTERVAL '100 hours' WHERE interval_type='collecting'")
        if defect=='blocking_wait':
            # The schema permits one open interval per Cycle: represent the
            # persisted blocking state without inserting a second open interval.
            c.execute("""UPDATE m5_cycle_time_intervals SET interval_type='blocking_system_wait',
                reason='system',operation_ref='pending-operation' WHERE ended_at IS NULL""")
        if defect=='recognized_absence':
            from Api.m7_return_integration import reconcile_presence
            reconcile_presence(c, cycle_id=cycle_id, owner_user_id=99)
        if defect in {'deadline','budget'}:
            result=completion.control(c,cycle_id=cycle_id,key='expired-resume',action='resume',
                                      reason='continue',initiated_by=99,participant_command=True)
            assert result['reason']==('calendar_deadline' if defect=='deadline' else 'time_budget')
            assert result['states']['cycle']=='collection_closed'
            assert c.execute('SELECT status FROM m5_assessment_situations').fetchone()['status']=='closed'
            assert c.execute('SELECT count(*) AS n FROM m5_cycle_time_intervals WHERE ended_at IS NULL').fetchone()['n']==0
            after=persisted(c)
            assert completion.control(c,cycle_id=cycle_id,key='expired-resume',action='resume',
                                      reason='continue',initiated_by=99,participant_command=True)==result
            assert persisted(c)==after
            return
        expected = ('M7_RETURN_EXPLICIT_CONTINUE_REQUIRED' if defect in {'recognized_absence','expired_lease'} else
                    'M7_TIME_LIMIT_REACHED' if defect in {'deadline','budget'} else 'M7_PARTICIPANT_RESUME_NOT_ALLOWED')
        before = persisted(c)
        # A rejected HTTP transaction rolls back a newly recognized presence event too.
        with pytest.raises(ValueError, match=expected):
            with c.transaction():
                completion.control(c, cycle_id=cycle_id, key='unsafe-resume', action='resume',
                                   reason='between_situations', initiated_by=99, participant_command=True)
        assert persisted(c) == before
