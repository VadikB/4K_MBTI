"""EXEC-FIX-01: real isolated PG + HTTP, deterministic recorded providers only.

Reuses the frozen M6 synthetic fixture; creates a single route position around
that fixture's AS so that presence/Continue/finish exercise production services.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from threading import Barrier, local
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from Api import m6_repository as evidence_repo, m6_assessment_repository as assessments
from Api import m7_clarification, m7_completion, m7_return_integration as presence
from Api.m5_case_runtime import checksum
from Api.m5_scenario_runtime import build_c45
from Api.m6_assessment_package import load_mechanism as load_assessment_mechanism
from Api.m6_assessment_worker import run_request as run_assessment
from Api.m6_worker import run_request as run_evidence
from tests.integration.test_m6_evidence_db import database, empty_output, enqueue, _assessment_output

pytestmark = pytest.mark.integration


@pytest.fixture
def current(database):
    factory, _ = database
    with factory() as c:
        row = c.execute('SELECT * FROM m5_assessment_situations').fetchone()
        cycle = c.execute('SELECT * FROM m5_cycles WHERE id=%s', (row['cycle_db_id'],)).fetchone()
        c.execute("UPDATE m5_assessment_situations SET status='scenario_ended',closed_at=NULL WHERE id=%s", (row['id'],))
        c.execute("UPDATE m5_cycles SET status='active',time_budget_seconds=7200,calendar_window_seconds=259200 WHERE id=%s", (cycle['id'],))
        c.execute("UPDATE m5_cycle_sessions SET status='active',ended_at=NULL WHERE id=%s", (row['session_db_id'],))
        # The frozen M6 fixture is a legacy one-AS cycle. Attach a saved, synthetic
        # one-position plan so tests use actual return ownership, never mocks.
        plan_id, revision_id, position_id = uuid4(), uuid4(), uuid4()
        policy = presence.policy_snapshot_for_plan(usage_scope='qa')
        content = {'goal': None, 'route': [{'position_no': 1}], 'return_policy_snapshot': policy}
        c.execute('''INSERT INTO m7_cycle_plans
            (id,cycle_db_id,profile_ref_json,full_target_set_json,planned_target_set_json,
             observation_requirements_json,rules_json,rules_checksum,status,created_by)
            VALUES(%s,%s,'{}','[]','[]','[]','{}',%s,'READY',99)''',
            (plan_id, cycle['id'], checksum({})))
        c.execute('''INSERT INTO m7_plan_revisions
            (id,plan_id,cycle_db_id,revision_no,content_json,content_checksum,reason)
            VALUES(%s,%s,%s,1,%s::jsonb,%s,'synthetic_exec_fix01')''',
            (revision_id, plan_id, cycle['id'], json.dumps(content), checksum(content)))
        case = row['snapshot_json']['case_ref']
        c.execute('''INSERT INTO m7_route_positions
            (id,cycle_db_id,plan_revision_id,position_no,case_id,case_version,
             expected_targets_json,state,current_as_db_id)
            VALUES(%s,%s,%s,1,%s,%s,'[]','in_progress',%s)''',
            (position_id, cycle['id'], revision_id, case['id'], case['version'], row['id']))
        c.execute('''INSERT INTO m7_route_position_as_history
            (position_id,assessment_situation_db_id,ordinal,disposition) VALUES(%s,%s,1,'current')''',
            (position_id, row['id']))
        # Reopen a collecting interval if the fixture's synthetic final handoff
        # closed it. No wall-clock sleeps are needed for temporal regressions.
        c.execute('UPDATE m5_cycle_time_intervals SET ended_at=COALESCE(ended_at,NOW()) WHERE cycle_db_id=%s', (cycle['id'],))
        c.execute("INSERT INTO m5_cycle_time_intervals(cycle_db_id,session_db_id,interval_type,started_at,reason) VALUES(%s,%s,'collecting',NOW(),'synthetic_exec_fix01')", (cycle['id'], row['session_db_id']))
        interim = build_c45(c, str(row['assessment_situation_id']), mode='interim')
        c.commit()
    return {'factory': factory, 'as_id': str(row['assessment_situation_id']), 'as_db': row['id'],
            'cycle_id': str(cycle['cycle_id']), 'cycle_db': cycle['id'],
            'session_db': row['session_db_id'], 'handoff_id': str(interim['handoff_id'])}


class RecordedEvidence:
    enabled = True
    def chat(self, messages, **_kwargs):
        return json.dumps(empty_output(json.loads(messages[1]['content'])))


class RecordedAssessment:
    enabled = True
    def __init__(self, uncertain=True): self.uncertain = uncertain
    def chat(self, messages, **_kwargs):
        value = _assessment_output(json.loads(messages[1]['content']))
        if not self.uncertain:
            for target in value['targets']: target['uncertainty'] = None
        return json.dumps(value, ensure_ascii=False)


def _resolve(current, *, handoff_id=None, status='ASK', key=None):
    """Persist real Evidence/IA/C54/Decision chains with controlled providers."""
    factory = current['factory']; key = key or uuid4().hex
    with factory() as c:
        request = enqueue(c, handoff_id or current['handoff_id'], 'e-' + key); c.commit()
    run_evidence(request['id'], connection_factory=factory, gateway=RecordedEvidence())
    with factory() as c:
        request = evidence_repo.read_request(c, request['id'])
        assert request['status'] == 'succeeded'
        assessment = assessments.enqueue(c, evidence_revision_id=str(request['analysis_revision_id']),
            key='a-' + key, mechanism=load_assessment_mechanism('m6_indicator_assessment/1.0.0'), created_by=99)
        c.commit()
    run_assessment(assessment['id'], connection_factory=factory,
                   gateway=RecordedAssessment(uncertain=status != 'NO_QUESTION'))
    with factory() as c:
        saved = assessments.read_request(c, assessment['id'])
        assert saved['status'] == 'succeeded'
        indicator = assessment['input_json']['material']['indicator_targets'][0]['indicator_id']
    class Question:
        enabled = True
        def chat(self, *_args, **_kwargs):
            if status == 'WAIT_TECHNICAL': raise TimeoutError('synthetic technical wait')
            return json.dumps({'schema_version': 1, 'admissible': True,
                'text': 'Что вы имели в виду, когда назвали этот довод основным?',
                'purpose': 'clarify_meaning', 'indicator_ids': [indicator],
                'resolving_information': ['смысл данного ответа'], 'refusal_reason': None}, ensure_ascii=False)
    decision = m7_clarification.decide_detached(c54_revision_id=str(saved['c54_revision_id']),
        key='d-' + key, created_by=99, gateway=Question(), connection_factory=factory)
    assert decision['status'] == status
    if status == 'ASK':
        with factory() as c:
            decision = m7_clarification.present(c, decision_id=str(decision['id']),
                expected_c54_revision_id=str(saved['c54_revision_id'])); c.commit()
    return decision


def _request(decision):
    return {'decision_id': str(decision['id']), 'request_id': 'answer-' + uuid4().hex,
            'turn_id': str(uuid4()), 'content': 'Этот довод связывает обе части моего решения.'}


def _counts(c):
    return c.execute('''SELECT
        (SELECT count(*) FROM m5_dialogue_turns) AS turns,
        (SELECT count(*) FROM m7_clarification_responses) AS responses,
        (SELECT count(*) FROM m5_c45_handoffs) AS handoffs,
        (SELECT count(*) FROM m6_processing_requests) AS jobs,
        (SELECT count(*) FROM m7_finalization_outbox) AS outbox''').fetchone()


def _finish(c, current, key='finish'):
    return m7_completion.finish_current_situation(c, cycle_id=current['cycle_id'], key=key, initiated_by=99)


def _expire(c, current, kind, offset=0):
    if kind == 'budget':
        c.execute("UPDATE m5_cycle_time_intervals SET ended_at=started_at WHERE cycle_db_id=%s AND interval_type='collecting'", (current['cycle_db'],))
        c.execute('''UPDATE m5_cycle_time_intervals SET started_at=NOW()-(%s*INTERVAL '1 second'),
            ended_at=NOW() WHERE id=(SELECT max(id) FROM m5_cycle_time_intervals
                WHERE cycle_db_id=%s AND interval_type='collecting')''',
            (7200 + offset, current['cycle_db']))
    else:
        c.execute('''UPDATE m5_cycles SET started_at=NOW()-(calendar_window_seconds+%s)*INTERVAL '1 second'
            WHERE id=%s''', (offset, current['cycle_db']))


@pytest.mark.parametrize('kind,offset', [('budget', 0), ('budget', 1), ('calendar', 0), ('calendar', 1)])
def test_b1_new_clarification_rejected_at_and_after_time_boundary(current, kind, offset):
    decision = _resolve(current); request = _request(decision)
    with current['factory']() as c:
        _expire(c, current, kind, offset); c.commit()
        before = _counts(c)
        with pytest.raises(ValueError, match='TIME|CLOSED|UNAVAILABLE'):
            m7_clarification.answer(c, **request)
        c.rollback()
        assert _counts(c) == before


@pytest.mark.parametrize('blocked', ['session_paused', 'cycle_paused', 'blocking_wait', 'recognized_absence', 'expired_presence'])
def test_b2_new_answer_cannot_bypass_collection_or_explicit_continue(current, blocked):
    decision = _resolve(current); request = _request(decision)
    with current['factory']() as c:
        if blocked == 'session_paused': c.execute("UPDATE m5_cycle_sessions SET status='paused' WHERE id=%s", (current['session_db'],))
        elif blocked == 'cycle_paused': c.execute("UPDATE m5_cycles SET status='paused' WHERE id=%s", (current['cycle_db'],))
        else:
            c.execute("UPDATE m5_cycle_time_intervals SET started_at=NOW()-INTERVAL '120 seconds' WHERE ended_at IS NULL AND interval_type='collecting'")
            if blocked == 'blocking_wait':
                from Api.m5_cycle_runtime import begin_blocking_wait
                begin_blocking_wait(c, cycle_db_id=current['cycle_db'], session_db_id=current['session_db'], operation_ref='synthetic-block', reason='synthetic')
            elif blocked == 'recognized_absence':
                # Controlled event records actual DB intervals, not monkeypatches.
                c.execute('''INSERT INTO m7_return_absence_events
                    (id,cycle_db_id,session_db_id,position_id,assessment_situation_db_id,source_kind,source_ref,recognized_at,policy_ref_json,status)
                    SELECT %s,%s,%s,p.id,%s,'controlled_fixture','synthetic-absence',NOW()-INTERVAL '1 second','{}','recognized'
                    FROM m7_route_positions p WHERE p.cycle_db_id=%s''',
                    (uuid4(), current['cycle_db'], current['session_db'], current['as_db'], current['cycle_db']))
            else:
                c.execute('''INSERT INTO m7_return_presence_clients
                    (cycle_db_id,client_id,owner_user_id,assessment_situation_db_id,last_seen_at,lease_expires_at)
                    VALUES(%s,%s,99,%s,NOW()-INTERVAL '61 seconds',NOW()-INTERVAL '1 second')''',
                    (current['cycle_db'], uuid4(), current['as_db']))
        c.commit(); before = _counts(c)
        with pytest.raises(ValueError, match='RETURN|WAIT|CLOSED|UNAVAILABLE'):
            m7_clarification.answer(c, **request)
        c.rollback(); assert _counts(c) == before


def test_b3_replay_after_final_closure_and_every_payload_field_conflicts(current):
    decision = _resolve(current); request = _request(decision)
    with current['factory']() as c:
        accepted = m7_clarification.answer(c, **request); c.commit()
        m7_completion.complete(c, cycle_id=current['cycle_id'], key='final-refusal',
            action='final_refusal', reason='synthetic_refusal', initiated_by=99); c.commit()
        before = _counts(c)
        assert m7_clarification.answer(c, **request) == accepted
        for change in ({'content': 'Изменённый ответ'}, {'turn_id': str(uuid4())}, {'request_id': 'changed-request'}):
            with pytest.raises(ValueError, match='IDEMPOTENCY'):
                m7_clarification.answer(c, **{**request, **change})
            c.rollback()
        assert _counts(c) == before


def test_b4_same_answer_two_transactions_waiting_for_cycle_replays_once(current, monkeypatch):
    decision = _resolve(current); request = _request(decision)
    gate = Barrier(2); seen = local(); read = m7_clarification.repo.read
    def first_read(c, decision_id):
        result = read(c, decision_id)
        if not getattr(seen, 'done', False):
            seen.done = True; assert result['response_outcome'] is None; gate.wait(timeout=10)
        return result
    def answer():
        with current['factory']() as c:
            c.execute("SET LOCAL lock_timeout='10s'")
            result = m7_clarification.answer(c, **request); c.commit(); return result
    with current['factory']() as c: before = _counts(c)
    with monkeypatch.context() as patch:
        patch.setattr(m7_clarification.repo, 'read', first_read)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: answer(), range(2)))
    assert results[0]['answer_turn_id'] == results[1]['answer_turn_id']
    with current['factory']() as c:
        after = _counts(c)
        assert after['turns'] == before['turns'] + 1
        assert after['responses'] == before['responses'] + 1
        assert after['handoffs'] == before['handoffs'] + 1
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()


@pytest.mark.parametrize('stage', ['first_pending', 'WAIT_TECHNICAL', 'open_ASK', 'answered_pending'])
def test_c1_normal_finish_blocks_pending_technical_failure_and_unanswered_question(current, stage):
    if stage != 'first_pending':
        decision = _resolve(current, status='WAIT_TECHNICAL' if stage == 'WAIT_TECHNICAL' else 'ASK')
        if stage == 'answered_pending':
            with current['factory']() as c: m7_clarification.answer(c, **_request(decision)); c.commit()
    with current['factory']() as c:
        before = _counts(c)
        with pytest.raises(ValueError, match='CLARIFICATION|INTERIM|PENDING|WAIT|TECHNICAL'):
            _finish(c, current)
        c.rollback(); assert _counts(c) == before
        assert c.execute('SELECT status FROM m5_assessment_situations WHERE id=%s', (current['as_db'],)).fetchone()['status'] == 'scenario_ended'


def test_c2_c4_c6_fresh_resolution_closes_once_and_pauses_budget_between_situations(current):
    _resolve(current, status='NO_QUESTION')
    with current['factory']() as c:
        before = _counts(c)
        first = _finish(c, current); c.commit()
        replay = _finish(c, current); c.commit()
        assert first['handoff_id'] == replay['handoff_id'] and replay['idempotent']
        after = _counts(c)
        assert after['handoffs'] == before['handoffs'] + 1
        assert after['outbox'] == before['outbox'] + 1
        assert c.execute('SELECT status FROM m5_cycles WHERE id=%s', (current['cycle_db'],)).fetchone()['status'] == 'paused'
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE cycle_db_id=%s AND interval_type=\'collecting\' AND ended_at IS NULL', (current['cycle_db'],)).fetchone()
        assert c.execute('SELECT current_as_db_id FROM m7_route_positions WHERE cycle_db_id=%s', (current['cycle_db'],)).fetchone()['current_as_db_id'] == current['as_db']
        final = c.execute('SELECT envelope_json FROM m5_c45_handoffs WHERE handoff_id=%s', (first['handoff_id'],)).fetchone()['envelope_json']
        assert {x['turn_id'] for x in final['dialogue']['turns']} == {str(x['turn_id']) for x in c.execute('SELECT turn_id FROM m5_dialogue_turns WHERE assessment_situation_db_id=%s', (current['as_db'],)).fetchall()}


def test_c3_answered_old_decision_does_not_authorize_new_material(current):
    decision = _resolve(current)
    with current['factory']() as c:
        answer = m7_clarification.answer(c, **_request(decision)); c.commit()
        with pytest.raises(ValueError, match='CLARIFICATION|INTERIM|PENDING|WAIT'):
            _finish(c, current)
        c.rollback()
    _resolve(current, handoff_id=str(answer['handoff_id']), status='NO_QUESTION')
    with current['factory']() as c:
        assert _finish(c, current)['handoff_id']


@pytest.mark.parametrize('action', ['final_refusal', 'time_limit'])
@pytest.mark.parametrize('stage', ['first_pending', 'WAIT_TECHNICAL', 'open_ASK'])
def test_c5_independent_closure_never_waits_for_normal_finish_resolution(current, action, stage):
    if stage != 'first_pending': _resolve(current, status='WAIT_TECHNICAL' if stage == 'WAIT_TECHNICAL' else 'ASK')
    with current['factory']() as c:
        if action == 'time_limit': _expire(c, current, 'budget')
        result = m7_completion.complete(c, cycle_id=current['cycle_id'], key='independent-closure',
            action=action, reason='synthetic_explicit_reason', initiated_by=99)
        assert result['states']['cycle'] == 'collection_closed'
        assert c.execute('SELECT status FROM m5_assessment_situations WHERE id=%s', (current['as_db'],)).fetchone()['status'] == 'closed'


@pytest.fixture
def http(current, monkeypatch):
    import Api.routes as routes
    # Authentication is a synthetic cookie; ownership and every mutation use PG.
    monkeypatch.setattr(routes, 'get_connection', current['factory'])
    monkeypatch.setattr(routes.web_session_service, 'get_user_by_token',
        lambda token: SimpleNamespace(id=99) if token == 'synthetic-owner' else None)
    monkeypatch.setenv('AGENT4K_ISOLATED_STAND', '1')
    monkeypatch.setenv('AGENT4K_BROWSER_TEST_GATEWAY', '1')
    monkeypatch.setenv('AGENT4K_QA_ORCHESTRATION', '1')
    monkeypatch.setenv('AGENT4K_BROWSER_SCENARIO', 'acceptance-v1')
    monkeypatch.setenv('AGENT4K_STAND_MARKER', 'stand-10.2:exec-fix01-synthetic')
    monkeypatch.setenv('DB_NAME', 'product4k_pytest_exec_fix01_http')
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        client.cookies.set(routes.SESSION_COOKIE_NAME, 'synthetic-owner')
        yield client


def test_http_pg_budget_rejects_without_turn_response_handoff_or_job(current, http):
    decision = _resolve(current); request = _request(decision)
    with current['factory']() as c:
        _expire(c, current, 'budget'); c.commit(); before = _counts(c)
    response = http.post('/users/assessment/m7/clarifications/' + str(decision['id']) + '/answers',
                         json={k: v for k, v in request.items() if k != 'decision_id'})
    assert response.status_code == 409, response.text
    with current['factory']() as c: assert _counts(c) == before


def test_http_pg_first_pending_finish_rejected_and_scenario_ended_heartbeat_dto_accepted(current, http):
    response = http.post('/users/assessment/m7/cycles/' + current['cycle_id'] + '/finish-situation',
                         json={'idempotency_key': 'first-pending'})
    assert response.status_code == 409, response.text
    decision = _resolve(current)
    response = http.post('/users/assessment/m7/cycles/' + current['cycle_id'] + '/presence', json={
        'client_id': str(uuid4()), 'expected_assessment_situation_id': current['as_id']})
    assert response.status_code == 200, response.text
    # Actual browser-shaped request must pass validation and fail because there
    # is no absence, rather than 422 for expected_state=scenario_ended.
    response = http.post('/users/assessment/m7/cycles/' + current['cycle_id'] + '/return-continue', json={
        'position_no': 1, 'expected_assessment_situation_id': current['as_id'],
        'expected_state': 'scenario_ended', 'idempotency_key': 'browser-shaped-return'})
    assert response.status_code == 409, response.text


def test_b1_answer_before_budget_and_calendar_boundaries_is_accepted(current):
    decision = _resolve(current); request = _request(decision)
    with current['factory']() as c:
        _expire(c, current, 'budget', offset=-1)
        c.execute("UPDATE m5_cycles SET started_at=NOW()-(calendar_window_seconds-1)*INTERVAL '1 second' WHERE id=%s", (current['cycle_db'],))
        before = _counts(c)
        result = m7_clarification.answer(c, **request)
        assert result['response_outcome'] == 'answered'
        after = _counts(c)
        assert after['turns'] == before['turns'] + 1 and after['responses'] == before['responses'] + 1


@pytest.mark.parametrize('outcome', ['no_answer', 'refused'])
def test_c2_current_explicit_no_answer_or_refusal_allows_normal_close(current, outcome):
    decision = _resolve(current)
    with current['factory']() as c:
        m7_clarification.record_outcome(c, decision_id=str(decision['id']), request_id=outcome, outcome=outcome)
        assert _finish(c, current)['handoff_id']


def test_c4_two_tabs_finish_at_once_create_one_final_handoff_and_outbox(current):
    _resolve(current, status='NO_QUESTION')
    gate = Barrier(2)
    def finish():
        with current['factory']() as c:
            c.execute("SET LOCAL lock_timeout='10s'"); gate.wait(timeout=10)
            result = _finish(c, current, key='same-key-two-tabs'); c.commit(); return result
    with current['factory']() as c: before = _counts(c)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: finish(), range(2)))
    assert results[0]['handoff_id'] == results[1]['handoff_id']
    with current['factory']() as c:
        after = _counts(c)
        assert after['handoffs'] == before['handoffs'] + 1 and after['outbox'] == before['outbox'] + 1


def test_b4_cycle_closure_winning_lock_fences_answer_and_heartbeat(current):
    from threading import Event
    decision = _resolve(current); request = _request(decision)
    locked, release, contenders = Event(), Event(), Barrier(2)
    def close_first():
        with current['factory']() as c:
            c.execute('SELECT id FROM m5_cycles WHERE id=%s FOR UPDATE', (current['cycle_db'],)).fetchone()
            locked.set(); assert release.wait(timeout=10)
            result = m7_completion.complete(c, cycle_id=current['cycle_id'], key='worker-wins',
                action='final_refusal', reason='synthetic-worker-first', initiated_by=99)
            c.commit(); return result
    def late_write(kind):
        assert locked.wait(timeout=10)
        with current['factory']() as c:
            c.execute("SET LOCAL lock_timeout='10s'")
            contenders.wait(timeout=10)
            try:
                if kind == 'answer': m7_clarification.answer(c, **request)
                else: presence.heartbeat(c, cycle_id=current['cycle_id'], owner_user_id=99,
                    client_id=str(uuid4()), expected_as_id=current['as_id'])
            except ValueError as error:
                c.rollback(); return str(error)
            raise AssertionError('late write accepted after closure won the Cycle lock')
    with current['factory']() as c: before = _counts(c)
    with ThreadPoolExecutor(max_workers=3) as pool:
        closer = pool.submit(close_first); assert locked.wait(timeout=10)
        writes = [pool.submit(late_write, kind) for kind in ('answer', 'heartbeat')]
        # The close holds the actual PG Cycle lock until contenders are launched.
        release.set()
        assert closer.result(timeout=15)['states']['cycle'] == 'collection_closed'
        assert all(future.result(timeout=15) for future in writes)
    with current['factory']() as c:
        after = _counts(c)
        assert after['turns'] == before['turns'] and after['responses'] == before['responses']
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()


def test_c4_second_tab_receipt_is_bound_to_original_as_after_route_moves(current):
    _resolve(current,status='NO_QUESTION')
    with current['factory']() as c:
        first=_finish(c,current,key='first-tab');c.commit()
        second=_finish(c,current,key='second-tab');c.commit()
        assert second['handoff_id']==first['handoff_id']
        # Another tab progressed the route; the lost receipt must still resolve
        # to the original AS without inspecting/closing whatever is current now.
        c.execute("UPDATE m7_route_positions SET state='completed' WHERE cycle_db_id=%s",(current['cycle_db'],));c.commit()
        replay=_finish(c,current,key='second-tab')
        assert replay['assessment_situation_id']==current['as_id']
        assert replay['handoff_id']==first['handoff_id']


def test_c2_current_stop_for_insufficient_question_time_still_allows_finish(current):
    with current['factory']() as c:
        _expire(c,current,'budget',offset=-50);c.commit()
    _resolve(current,status='STOP')
    with current['factory']() as c:
        assert _finish(c,current)['handoff_id']


def test_new_write_to_old_ask_is_rejected_when_latest_question_changes(current):
    old=_resolve(current)
    with current['factory']() as c:
        newer=build_c45(c,current['as_id'],mode='interim');c.commit()
    latest=_resolve(current,handoff_id=str(newer['handoff_id']),status='ASK')
    assert latest['id']!=old['id']
    with current['factory']() as c:
        before=_counts(c)
        with pytest.raises(ValueError,match='STATE_CHANGED'):
            m7_clarification.answer(c,**_request(old))
        c.rollback();assert _counts(c)==before
