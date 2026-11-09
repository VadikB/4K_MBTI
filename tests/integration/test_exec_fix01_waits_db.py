"""B5 regression drafts: real product pipeline + PG, recorded providers only."""
from datetime import datetime, timedelta, timezone
import json
import time
from uuid import uuid4

import pytest

from Api import m10_orchestration as orchestration
from Api import m6_repository, m7_clarification, m7_completion
from Api import m7_return_integration as presence
from Api.m5_cycle_runtime import read_cycle
from Api.m6_worker import run_request as run_evidence
from Api.m6_assessment_worker import run_request as run_assessment
from tests.integration.test_exec_fix01_clarification_db import current, database, http
from tests.integration.test_exec_fix01_clarification_db import RecordedEvidence, RecordedAssessment, _request

pytestmark = pytest.mark.integration


def _queue(current, handoff=None):
    with current['factory']() as c:
        orchestration.ensure_schema(c)
        request = orchestration.enqueue_handoff(c, handoff_id=handoff or current['handoff_id'], created_by=99)
        c.commit(); return request


def _open(c, current):
    return c.execute('SELECT * FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND ended_at IS NULL',
                     (current['cycle_db'],)).fetchone()


def _resolve_product(current, request, status='ASK'):
    factory = current['factory']
    run_evidence(request['id'], connection_factory=factory, gateway=RecordedEvidence())
    with factory() as c:
        assert m6_repository.read_request(c, request['id'])['status'] == 'succeeded'
        assert orchestration._queue_assessment(c); c.commit()
        assessment = c.execute("SELECT id FROM m6_assessment_requests WHERE status='queued' ORDER BY created_at DESC LIMIT 1").fetchone()
    run_assessment(assessment['id'], connection_factory=factory,
                   gateway=RecordedAssessment(uncertain=status != 'NO_QUESTION'))
    class Question:
        enabled = True
        def chat(self, messages, **_kwargs):
            if status == 'WAIT_TECHNICAL': raise TimeoutError('synthetic M7 failure')
            value = json.loads(messages[1]['content'])
            return json.dumps({'schema_version': 1, 'admissible': True,
                'text': 'Что вы имели в виду, когда назвали этот довод основным?',
                'purpose': 'clarify_meaning', 'indicator_ids': [value['indicator_ids'][0]],
                'resolving_information': ['смысл данного ответа'], 'refusal_reason': None}, ensure_ascii=False)
    with factory() as c:
        assert orchestration._clarify_interim(c, gateway=Question(), connection_factory=factory); c.commit()
        decision_id = c.execute('SELECT id FROM m7_clarification_decisions ORDER BY created_at DESC LIMIT 1').fetchone()['id']
        result = m7_clarification.read(c, str(decision_id)); assert result['status'] == status
        return result


def test_b5_interim_queue_stops_budget_but_not_calendar_and_replay_never_restarts_wait(current, http):
    queued = _queue(current)
    with current['factory']() as c:
        first = _open(c, current)
        assert first['interval_type'] == 'blocking_system_wait'
        before = read_cycle(c, current['cycle_id']); c.commit()
    time.sleep(1.1)  # real elapsed SQL NOW; no fake clock/result mock
    with current['factory']() as c:
        after = read_cycle(c, current['cycle_id'])
        assert after['consumed_seconds'] == before['consumed_seconds']
        assert after['calendar_deadline'] == before['calendar_deadline']
    decision = _resolve_product(current, queued)
    assert decision['question_turn_id']
    with current['factory']() as c:
        assert _open(c, current)['interval_type'] == 'collecting'
        count = c.execute("SELECT count(*) AS n FROM m5_cycle_time_intervals WHERE interval_type='blocking_system_wait'").fetchone()['n']
    assert _queue(current)['id'] == queued['id']
    with current['factory']() as c:
        assert _open(c, current)['interval_type'] == 'collecting'
        assert c.execute("SELECT count(*) AS n FROM m5_cycle_time_intervals WHERE interval_type='blocking_system_wait'").fetchone()['n'] == count


@pytest.mark.parametrize('status', ['NO_QUESTION', 'WAIT_TECHNICAL'])
def test_b5_pipeline_resolution_or_technical_failure_preserves_expected_wait(current, http, status):
    request = _queue(current); _resolve_product(current, request, status=status)
    with current['factory']() as c:
        assert _open(c, current)['interval_type'] == ('blocking_system_wait' if status == 'WAIT_TECHNICAL' else 'collecting')
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()


def test_b5_next_interim_after_accepted_answer_gets_a_new_wait(current, http):
    first = _resolve_product(current, _queue(current))
    with current['factory']() as c:
        answer = m7_clarification.answer(c, **_request(first)); c.commit()
    next_request = _queue(current, str(answer['handoff_id']))
    with current['factory']() as c:
        assert _open(c, current)['interval_type'] == 'blocking_system_wait'
        assert c.execute("SELECT count(*) AS n FROM m5_cycle_time_intervals WHERE interval_type='blocking_system_wait'").fetchone()['n'] == 2
    _resolve_product(current, next_request, status='NO_QUESTION')
    with current['factory']() as c:
        assert _open(c, current)['interval_type'] == 'collecting'
        assert m7_completion.finish_current_situation(c, cycle_id=current['cycle_id'], key='after-second-interim', initiated_by=99)['handoff_id']


def test_b5_pause_resume_while_interim_pending_remains_blocked_until_question(current, http):
    request = _queue(current)
    with current['factory']() as c:
        m7_completion.control(c, cycle_id=current['cycle_id'], key='pause-waiting', action='pause', reason='synthetic', initiated_by=99)
        m7_completion.control(c, cycle_id=current['cycle_id'], key='resume-waiting', action='resume', reason='synthetic', initiated_by=99)
        assert _open(c, current)['interval_type'] == 'blocking_system_wait'; c.commit()
    _resolve_product(current, request)
    with current['factory']() as c: assert _open(c, current)['interval_type'] == 'collecting'


def test_b5_real_absence_overlapping_analysis_retains_explicit_continue(current, http):
    request = _queue(current)
    with current['factory']() as c:
        # Existing real lease expires while only the system can make progress.
        c.execute('''INSERT INTO m7_return_presence_clients
            (cycle_db_id,client_id,owner_user_id,assessment_situation_db_id,last_seen_at,lease_expires_at)
            VALUES(%s,%s,99,%s,NOW()-INTERVAL '61 seconds',NOW()-INTERVAL '1 second')''',
            (current['cycle_db'], uuid4(), current['as_db']))
        assert presence.reconcile_presence(c, cycle_id=current['cycle_id'], owner_user_id=99)
        assert _open(c, current)['interval_type'] == 'blocking_system_wait'; c.commit()
    _resolve_product(current, request)
    with current['factory']() as c:
        assert _open(c, current)['interval_type'] == 'blocking_system_wait'
        result = presence.continue_return(c, cycle_id=current['cycle_id'], position_no=1,
            expected_as_id=current['as_id'], expected_state='scenario_ended', key='continue-after-analysis', owner_user_id=99)
        assert result['assessment_situation_id'] == current['as_id']
        assert _open(c, current)['interval_type'] == 'collecting'
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()


def test_b5_calendar_expiry_still_closes_cycle_while_analysis_is_blocking(current, http):
    _queue(current)
    with current['factory']() as c:
        c.execute("UPDATE m5_cycles SET started_at=NOW()-(calendar_window_seconds+1)*INTERVAL '1 second' WHERE id=%s", (current['cycle_db'],))
        result = m7_completion.complete(c, cycle_id=current['cycle_id'], key='calendar-wait-expiry',
            action='time_limit', reason='synthetic', initiated_by=99)
        assert result['reason'] == 'calendar_deadline' and result['states']['cycle'] == 'collection_closed'
        assert not _open(c, current)


def test_b5_continue_before_question_readiness_keeps_analysis_wait_until_ask(current, http):
    request = _queue(current)
    with current['factory']() as c:
        # evaluated_at advances only recognition; consumed budget is already
        # frozen by the persisted technical wait interval.
        at = datetime.now(timezone.utc)
        c.execute('''INSERT INTO m7_return_presence_clients
            (cycle_db_id,client_id,owner_user_id,assessment_situation_db_id,last_seen_at,lease_expires_at)
            VALUES(%s,%s,99,%s,%s,%s)''',
            (current['cycle_db'], uuid4(), current['as_db'], at, at + timedelta(seconds=1)))
        evaluated = at + timedelta(seconds=2)
        assert presence.reconcile_presence(c, cycle_id=current['cycle_id'], owner_user_id=99, evaluated_at=evaluated)
        result = presence.continue_return(c, cycle_id=current['cycle_id'], position_no=1,
            expected_as_id=current['as_id'], expected_state='scenario_ended', key='continue-during-analysis',
            owner_user_id=99, evaluated_at=evaluated)
        assert result['assessment_situation_id'] == current['as_id']
        assert _open(c, current)['interval_type'] == 'blocking_system_wait'
        assert not c.execute("SELECT 1 FROM m7_return_absence_events WHERE status='recognized'").fetchone()
        c.commit()
    _resolve_product(current, request)
    with current['factory']() as c:
        assert _open(c, current)['interval_type'] == 'collecting'
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()


def test_b5_absence_then_pause_resume_retains_return_wait_after_analysis(current,http):
    request=_queue(current)
    with current['factory']() as c:
        c.execute('''INSERT INTO m7_return_presence_clients
            (cycle_db_id,client_id,owner_user_id,assessment_situation_db_id,last_seen_at,lease_expires_at)
            VALUES(%s,%s,99,%s,NOW()-INTERVAL '61 seconds',NOW()-INTERVAL '1 second')''',
            (current['cycle_db'],uuid4(),current['as_db']))
        assert presence.reconcile_presence(c,cycle_id=current['cycle_id'],owner_user_id=99)
        m7_completion.control(c,cycle_id=current['cycle_id'],key='absence-pause',action='pause',reason='synthetic',initiated_by=99)
        m7_completion.control(c,cycle_id=current['cycle_id'],key='absence-resume',action='resume',reason='synthetic',initiated_by=99)
        assert _open(c,current)['interval_type']=='blocking_system_wait';c.commit()
    _resolve_product(current,request)
    with current['factory']() as c:
        assert _open(c,current)['interval_type']=='blocking_system_wait'
        presence.continue_return(c,cycle_id=current['cycle_id'],position_no=1,expected_as_id=current['as_id'],
            expected_state='scenario_ended',key='absence-explicit-continue',owner_user_id=99)
        assert _open(c,current)['interval_type']=='collecting'
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()
