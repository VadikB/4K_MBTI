"""EXEC01 A: реальные PG locks/интервалы; synthetic QA plan не human admission."""
import json
from copy import deepcopy
from Api.m5_case_runtime import checksum
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from Api import m7_return_integration as returns
from Api.m7_completion_contracts import ReturnContinueRequest
from Api.m5_cycle_runtime import read_cycle
from tests.integration.test_m7_cycle_planner_db import db, active_cycle

pytestmark = pytest.mark.integration


def test_scenario_ended_presence_and_explicit_continue_keep_as(db):
    with db() as c:
        plan, shown = active_cycle(c)
        cycle_id, as_id = str(plan['cycle_id']), str(shown['decision']['assessment_situation_id'])
        c.execute("UPDATE m5_assessment_situations SET status='scenario_ended'")
        revision=c.execute('SELECT * FROM m7_plan_revisions ORDER BY revision_no DESC LIMIT 1').fetchone()
        content=deepcopy(revision['content_json']);policy=returns.load_policy(usage_scope='assessment')
        content['return_policy_snapshot']={'content':policy,'checksum':checksum(policy)}
        c.execute("""INSERT INTO m7_plan_revisions(id,plan_id,cycle_db_id,revision_no,content_json,content_checksum,reason)
            VALUES(%s,%s,%s,%s,%s::jsonb,%s,'synthetic_exec01_r1')""",
            (uuid4(),revision['plan_id'],revision['cycle_db_id'],revision['revision_no']+1,json.dumps(content),checksum(content)))
        c.execute("UPDATE m5_cycles SET usage_scope='assessment'")
        before = read_cycle(c, cycle_id)
        client = str(uuid4())
        c.execute("UPDATE m5_cycle_time_intervals SET started_at=NOW()-INTERVAL '2000 seconds' WHERE ended_at IS NULL")
        now = datetime.now(timezone.utc) - timedelta(seconds=1000)
        first = returns.heartbeat(c, cycle_id=cycle_id, owner_user_id=99, client_id=client, expected_as_id=as_id, received_at=now)
        # Active reading over several lease lengths refreshes the same client.
        for seconds in (60, 120, 180, 240):
            returns.heartbeat(c, cycle_id=cycle_id, owner_user_id=99, client_id=client, expected_as_id=as_id, received_at=now+timedelta(seconds=seconds))
            assert returns.reconcile_presence(c, cycle_id=cycle_id, owner_user_id=99, evaluated_at=now+timedelta(seconds=seconds)) is None
        expired = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert returns.reconcile_presence(c, cycle_id=cycle_id, owner_user_id=99, evaluated_at=expired)
        payload = ReturnContinueRequest(position_no=1, expected_assessment_situation_id=as_id, expected_state='scenario_ended', idempotency_key='exec01-continue')
        result = returns.continue_return(c, cycle_id=cycle_id, position_no=payload.position_no, expected_as_id=as_id, expected_state=payload.expected_state, key=payload.idempotency_key, owner_user_id=99, evaluated_at=expired)
        assert result['branch'] == 'continued_current'
        assert result['recognized_absence_seconds'] > 180
        assert result['assessment_situation_id'] == as_id
        assert result['remaining_seconds'] <= before['remaining_seconds']
        # FIX-RETURN-01: Continue removes stale clients; immediate/reloaded/two-tab heartbeats stay valid.
        for other in (client, str(uuid4()), client):
            returns.heartbeat(c, cycle_id=cycle_id, owner_user_id=99, client_id=other, expected_as_id=as_id)
        assert not c.execute('SELECT 1 FROM m5_cycle_time_intervals WHERE ended_at<started_at').fetchone()
        assert c.execute('SELECT count(*) AS n FROM m5_assessment_situations').fetchone()['n'] == 1


@pytest.mark.parametrize('invalid', ['foreign', 'stale', 'closed', 'terminated', 'closed_cycle'])
def test_scenario_ended_presence_rejects_invalid_scope(db, invalid):
    with db() as c:
        plan, shown = active_cycle(c)
        cycle_id, as_id = str(plan['cycle_id']), str(shown['decision']['assessment_situation_id'])
        c.execute("UPDATE m5_assessment_situations SET status='scenario_ended'")
        if invalid in {'closed', 'terminated'}:
            c.execute('UPDATE m5_assessment_situations SET status=%s', (invalid,))
        if invalid == 'closed_cycle':
            c.execute("UPDATE m5_cycles SET status='collection_closed'")
        with pytest.raises(ValueError):
            returns.heartbeat(c, cycle_id=cycle_id, owner_user_id=98 if invalid=='foreign' else 99, client_id=str(uuid4()), expected_as_id=str(uuid4()) if invalid=='stale' else as_id)
