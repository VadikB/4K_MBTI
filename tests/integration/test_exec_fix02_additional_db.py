"""EXEC-FIX-02: frozen first preparation, live guards, legacy and lock order.

Real owned-PG fixture; deterministic local transport and synthetic upstream admission.
"""
import json
import hashlib
from uuid import uuid4

import pytest
from Api.llm import deepseek_gateway as gateway_module
from Api import m10_product_flow, m7_cycle_planner
from Api.product_cycle_preparation_queue import _canonical
from tests.integration.test_exec_fix02_retry_db import test_database_url, configured_database_url, product_db, retry_env, _post, _process, _first, _close

pytestmark = pytest.mark.integration


def test_first_retry_uses_frozen_cycle_when_mutable_configuration_changes(retry_env):
    env = retry_env
    env.transport.slots.acquire()
    assert _post(env, 'first-frozen-overload').status_code == 202
    _, failed = _process(env)
    assert failed['error_code'] == 'LlmCapacityError'
    env.transport.slots.release()
    with env.db() as c:
        before = c.execute('SELECT cycle_id,catalog_ref_json,execution_manifest_checksum FROM m5_cycles').fetchone()
        c.execute('UPDATE assessment_configurations SET catalog_version_id=NULL WHERE id=1')
    assert _post(env, 'first-frozen-retry').status_code == 202
    _, completed = _process(env)
    assert completed['status'] == 'completed', completed
    assert completed['result_json']['plan']['cycle_id'] == str(before['cycle_id'])
    assert completed['result_json']['decision']['assessment_situation_id']
    with env.db() as c:
        after = c.execute('SELECT cycle_id,catalog_ref_json,execution_manifest_checksum FROM m5_cycles').fetchone()
        assert after == before
        assert c.execute('SELECT COUNT(*) AS n FROM m7_route_assignments').fetchone()['n'] == 1
        assert c.execute('SELECT COUNT(*) AS n FROM m5_assessment_situations').fetchone()['n'] == 1


@pytest.mark.parametrize('guard', ['terminal', 'membership', 'case_admission', 'revision'])
def test_guard_change_during_provider_cannot_attach_or_present_next(retry_env, monkeypatch, guard):
    env = retry_env
    cycle, first_as = _first(env)
    _close(env, cycle, first_as)
    original = env.transport.urlopen
    changed = False

    def changing_transport(req, **kwargs):
        nonlocal changed
        response = original(req, **kwargs)
        if not changed:
            changed = True
            with env.db() as c:
                if guard == 'terminal':
                    c.execute("UPDATE m5_cycles SET status='collection_closed' WHERE cycle_id=%s", (cycle,))
                elif guard == 'membership':
                    c.execute('DELETE FROM organization_memberships WHERE user_id=99')
                elif guard == 'case_admission':
                    selected = c.execute('''SELECT cv.id FROM m7_route_decisions d
                        JOIN m5_cycles c ON c.id=d.cycle_db_id
                        JOIN m5_case_versions cv ON cv.case_id=d.selected_case_id AND cv.case_version=d.selected_case_version
                        WHERE c.cycle_id=%s ORDER BY d.created_at DESC LIMIT 1''', (cycle,)).fetchone()
                    c.execute("INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum) VALUES(%s,'assessment_situation','FAIL','{}','synthetic-provider-drift')", (selected['id'],))
                else:
                    plan = m7_cycle_planner.read_plan(c, cycle)
                    c.execute("INSERT INTO m7_plan_revisions SELECT %s,plan_id,cycle_db_id,revision_no+1,content_json,content_checksum,'synthetic provider revision drift',NOW() FROM m7_plan_revisions WHERE id=%s", (uuid4(), plan['revision_id']))
        return response

    monkeypatch.setattr(gateway_module.request, 'urlopen', changing_transport)
    assert _post(env, 'provider-drift', cycle).status_code == 201
    _, failed = _process(env)
    assert changed and failed['status'] == 'failed', failed
    assert env.http.get('/users/assessment/cycles/preparation/provider-drift').json()['retry_allowed'] is False
    assert _post(env, 'provider-drift-again', cycle).status_code == 409
    with env.db() as c:
        assert c.execute('SELECT COUNT(*) AS n FROM m5_assessment_situations').fetchone()['n'] == 1
        assert c.execute('SELECT COUNT(*) AS n FROM m7_route_assignments').fetchone()['n'] == 1
        assert c.execute('SELECT status FROM m5_assessment_situations WHERE assessment_situation_id=%s', (first_as,)).fetchone()['status'] == 'closed'


@pytest.mark.parametrize('error_code', ['LlmCapacityError', 'RuntimeError'])
def test_legacy_unscoped_next_failure_keeps_its_retry_classification(retry_env, error_code):
    env = retry_env
    cycle, first_as = _first(env)
    _close(env, cycle, first_as)
    # Historical persisted request shape predates next_preparation_scope and
    # preparation_key. Insert via fixture SQL because normal enqueue now adds them.
    legacy = {'kind': 'next', 'cycle_id': cycle, 'idempotency_key': 'legacy-next'}
    import hashlib
    with env.db() as c:
        c.execute('''INSERT INTO product_cycle_preparation_operations
            (operation_id,user_id,request_json,request_checksum,status,error_code,error_message,completed_at)
            VALUES('legacy-next',99,%s::jsonb,%s,'failed',%s,'synthetic historical failure',NOW())''',
            (json.dumps(legacy), hashlib.sha256(_canonical(legacy).encode()).hexdigest(), error_code))
    old = _post(env, 'legacy-next', cycle)
    assert old.status_code == 201
    assert old.json()['retry_allowed'] is (error_code == 'LlmCapacityError')
    replay = _post(env, 'legacy-next-new-key', cycle)
    if error_code == 'RuntimeError':
        assert replay.status_code == 409
    else:
        assert replay.status_code == 201 and replay.json()['status'] == 'queued'
        job, result = _process(env)
        assert job['request_json']['preparation_key'] == 'legacy-next'
        assert result['status'] == 'completed', result
        second_as = result['result_json']['decision']['assessment_situation_id']
        _close(env, cycle, second_as)
        third = _post(env, 'post-legacy-next-position', cycle)
        assert third.status_code == 201 and third.json()['status'] == 'queued'
        assert third.json()['operation_id'] != replay.json()['operation_id']


def test_failed_next_from_another_cycle_is_not_a_semantic_duplicate(retry_env):
    env = retry_env
    cycle, first_as = _first(env)
    _close(env, cycle, first_as)
    env.transport.mode = 'credentials'
    assert _post(env, 'cycle-one-credential-failure', cycle).status_code == 201
    _, failed = _process(env)
    assert failed['status'] == 'failed'
    with env.db() as c:
        another = m7_cycle_planner.create_plan(c, personalized_profile_id=env.profile,
            selected_skills=['K1','K2','K3','K4'], created_by=99, key='independent-cycle', usage_scope='assessment')
    other_cycle = str(another['cycle_id'])
    assert other_cycle != cycle
    response = _post(env, 'cycle-two-new-command', other_cycle)
    assert response.status_code == 201 and response.json()['status'] == 'queued', response.text
    assert response.json()['operation_id'] != 'cycle-one-credential-failure'


@pytest.mark.parametrize('guard', ['terminal', 'membership', 'assignment', 'revision', 'case_admission'])
def test_first_retry_rechecks_live_guard_without_sending_provider(retry_env, guard):
    env = retry_env
    sent_before = env.transport.sent
    assert env.transport.slots.acquire(blocking=False)
    try:
        initial = _post(env, 'first-capacity-before-guard')
        assert initial.status_code == 202, initial.text
        old_job, failed = _process(env)
        assert failed['status'] == 'failed' and failed['error_code'] == 'LlmCapacityError', failed
        assert env.transport.sent == sent_before
    finally:
        env.transport.slots.release()
    initial_read = env.http.get('/users/assessment/cycles/preparation/first-capacity-before-guard')
    assert initial_read.status_code == 200 and initial_read.json()['retry_allowed'] is True

    with env.db() as c:
        cycle = c.execute('SELECT cycle_id,catalog_ref_json,execution_manifest_checksum FROM m5_cycles').fetchone()
        assert cycle
        cycle_id = str(cycle['cycle_id'])
        if guard == 'terminal':
            c.execute("UPDATE m5_cycles SET status='collection_closed' WHERE cycle_id=%s", (cycle_id,))
        elif guard == 'membership':
            c.execute('DELETE FROM organization_memberships WHERE user_id=99')
        elif guard == 'assignment':
            c.execute('''CREATE TABLE organization_assessment_assignments(
                id BIGINT PRIMARY KEY,recipient_user_id BIGINT,status TEXT,revoked_at TIMESTAMPTZ)''')
            c.execute("INSERT INTO organization_assessment_assignments VALUES(12,99,'cancelled',NOW())")
            c.execute('UPDATE m5_cycles SET assignment_id=12 WHERE cycle_id=%s', (cycle_id,))
        elif guard == 'revision':
            plan = m7_cycle_planner.read_plan(c, cycle_id)
            c.execute('''INSERT INTO m7_plan_revisions
                SELECT %s,plan_id,cycle_db_id,revision_no+1,content_json,content_checksum,
                       'synthetic first preparation revision drift',NOW()
                FROM m7_plan_revisions WHERE id=%s''', (uuid4(), plan['revision_id']))
        else:
            selected = c.execute('''SELECT cv.id FROM m7_route_decisions d
                JOIN m5_cycles c ON c.id=d.cycle_db_id
                JOIN m5_case_versions cv ON cv.case_id=d.selected_case_id AND cv.case_version=d.selected_case_version
                WHERE c.cycle_id=%s ORDER BY d.created_at DESC LIMIT 1''', (cycle_id,)).fetchone()
            assert selected
            c.execute('''INSERT INTO m5_qa_evidence(case_version_id,scope,result,evidence_json,evidence_checksum)
                VALUES(%s,'assessment_situation','FAIL','{}','synthetic-first-admission-revocation')''', (selected['id'],))

    read = env.http.get('/users/assessment/cycles/preparation/first-capacity-before-guard')
    assert read.status_code == 200 and read.json()['retry_allowed'] is False, read.text
    same_key = _post(env, 'first-capacity-before-guard')
    assert same_key.status_code == 202 and same_key.json() == read.json(), same_key.text
    new_key = _post(env, 'first-capacity-after-guard')
    assert new_key.status_code == 409, new_key.text
    assert env.transport.sent == sent_before
    assert env.queue._claim() is None
    # Reinvoking the old attempt is not a way around either guard/fence.
    env.queue._process(old_job)
    assert env.transport.sent == sent_before
    with env.db() as c:
        assert c.execute('SELECT COUNT(*) AS n FROM m5_cycles').fetchone()['n'] == 1
        assert c.execute('SELECT COUNT(*) AS n FROM m5_assessment_situations').fetchone()['n'] == 0
        assert c.execute('SELECT COUNT(*) AS n FROM m7_route_assignments').fetchone()['n'] == 0
        assert c.execute('SELECT COUNT(*) AS n FROM product_cycle_preparation_operations').fetchone()['n'] == 1
        after = c.execute('SELECT cycle_id,catalog_ref_json,execution_manifest_checksum FROM m5_cycles').fetchone()
        assert after == cycle


def test_late_legacy_next_cannot_advance_after_its_predecessor_closes(retry_env):
    env = retry_env
    cycle_id, first_as = _first(env)
    sent_before = env.transport.sent
    legacy_request = {'kind': 'next', 'cycle_id': cycle_id, 'idempotency_key': 'legacy-before-close'}
    with env.db() as c:
        c.execute('''INSERT INTO product_cycle_preparation_operations
            (operation_id,user_id,request_json,request_checksum,status)
            VALUES('legacy-before-close',99,%s::jsonb,%s,'queued')''',
            (json.dumps(legacy_request), hashlib.sha256(_canonical(legacy_request).encode()).hexdigest()))
    old_job = env.queue._claim()
    assert old_job and old_job['operation_id'] == 'legacy-before-close'
    assert 'next_preparation_scope' not in old_job['request_json']
    assert old_job['created_at']

    # Real AS close after the legacy command/claim changes the route boundary.
    _close(env, cycle_id, first_as)
    with env.db() as c:
        closed = c.execute('SELECT status,closed_at,closed_at>%s AS advanced FROM m5_assessment_situations WHERE assessment_situation_id=%s', (old_job['created_at'], first_as)).fetchone()
        assert closed['status'] == 'closed' and closed['advanced']
    env.queue._process(old_job)
    failed = env.queue.get_status('legacy-before-close')
    assert failed['status'] == 'failed', failed
    assert failed['error_message'] == 'PRODUCT_CYCLE_PREPARATION_POSITION_CHANGED'
    assert env.transport.sent == sent_before
    read = env.http.get('/users/assessment/cycles/preparation/legacy-before-close')
    assert read.status_code == 200 and read.json()['retry_allowed'] is False, read.text
    same_key = _post(env, 'legacy-before-close', cycle_id)
    assert same_key.status_code == 201 and same_key.json() == read.json(), same_key.text

    new_boundary = _post(env, 'new-next-after-real-close', cycle_id)
    assert new_boundary.status_code == 201 and new_boundary.json()['status'] == 'queued', new_boundary.text
    assert new_boundary.json()['operation_id'] != old_job['operation_id']
    new_job, completed = _process(env)
    assert new_job['request_json']['next_preparation_scope']['after_assessment_situation_id'] == first_as
    assert new_job['request_json']['next_preparation_scope']['after_position_no'] == 1
    assert completed['status'] == 'completed', completed
    assert completed['result_json']['plan']['cycle_id'] == cycle_id
    assert completed['result_json']['decision']['assessment_situation_id'] != first_as
    with env.db() as c:
        assert c.execute('SELECT COUNT(*) AS n FROM m5_cycles').fetchone()['n'] == 1
        assert c.execute('SELECT COUNT(*) AS n FROM m5_assessment_situations').fetchone()['n'] == 2
        assert c.execute('SELECT COUNT(*) AS n FROM m7_route_assignments').fetchone()['n'] == 2
        assert c.execute('SELECT COUNT(*) AS n FROM m5_dialogue_turns WHERE speaker_type=\'assessee\'').fetchone()['n'] == 1


def test_runtime_retry_readback_does_not_invert_worker_owner_cycle_locks(retry_env):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    env = retry_env
    cycle_id, first_as = _first(env)
    _close(env, cycle_id, first_as)
    env.transport.slots.acquire()
    assert _post(env, "lock-order-overload", cycle_id).status_code == 201
    _, failed = _process(env)
    assert failed["error_code"] == "LlmCapacityError"
    env.transport.slots.release()
    owner_locked = threading.Event()

    def worker_lock_order():
        with env.db() as c:
            c.execute("SET LOCAL lock_timeout='2s'")
            c.execute("SELECT pg_advisory_xact_lock(99)")
            owner_locked.set()
            c.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s FOR UPDATE", (cycle_id,))

    with ThreadPoolExecutor(1) as workers:
        with env.db() as runtime_connection:
            # The runtime return guard may already own this lock before readback.
            runtime_connection.execute("SET LOCAL lock_timeout='500ms'")
            runtime_connection.execute("SELECT id FROM m5_cycles WHERE cycle_id=%s FOR UPDATE", (cycle_id,))
            future = workers.submit(worker_lock_order)
            assert owner_locked.wait(1)
            runtime = m10_product_flow.read_runtime(runtime_connection, cycle_id=cycle_id)
            assert runtime["preparation_operation"]["retry_allowed"] is True
        future.result(timeout=3)
