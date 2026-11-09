"""B3 / EXEC-FIX-03 joint: HTTP replay cannot reopen pipeline projection."""
import pytest

from Api import m10_orchestration as orchestration, m7_completion
from tests.integration.test_exec_fix01_clarification_db import current, database, http, _resolve, _request, _counts

pytestmark = pytest.mark.integration


def test_http_pg_accepted_answer_replay_after_closure_preserves_pipeline_and_all_revision_counts(current, http):
    decision = _resolve(current); request = _request(decision)
    body = {k: v for k, v in request.items() if k != 'decision_id'}
    url = '/users/assessment/m7/clarifications/' + str(decision['id']) + '/answers'
    with current['factory']() as c:
        orchestration.ensure_schema(c); c.commit()
    first = http.post(url, json=body)
    assert first.status_code == 200, first.text
    with current['factory']() as c:
        m7_completion.complete(c, cycle_id=current['cycle_id'], key='synthetic-final-refusal',
            action='final_refusal', reason='synthetic-explicit-refusal', initiated_by=99)
        # Synthetic terminal projection isolates the replay joint with03; no real
        # M6/M8 or report generation is claimed by this regression.
        orchestration._set_state(c, current['cycle_db'], status='ready', stage='synthetic-final-readback')
        c.commit()
        before = _counts(c)
        history_before = c.execute('SELECT count(*) AS n FROM m10_pipeline_revisions').fetchone()['n']
    replay = http.post(url, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    changed = http.post(url, json={**body, 'content': 'Изменённый ответ'})
    assert changed.status_code == 409, changed.text
    with current['factory']() as c:
        assert _counts(c) == before
        assert c.execute('SELECT count(*) AS n FROM m10_pipeline_revisions').fetchone()['n'] == history_before
        assert c.execute('SELECT status,stage FROM m10_pipeline_runs WHERE cycle_db_id=%s',
            (current['cycle_db'],)).fetchone() == {'status': 'ready', 'stage': 'synthetic-final-readback'}
