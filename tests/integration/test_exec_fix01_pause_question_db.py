"""Controlled provider/PG race: pause before detached ASK output is saved."""
import json

import pytest

from Api import m10_orchestration as orchestration, m7_clarification, m7_completion
from Api.m6_worker import run_request as run_evidence
from Api.m6_assessment_worker import run_request as run_assessment
from tests.integration.test_exec_fix01_clarification_db import current, database, http, RecordedEvidence, RecordedAssessment
from tests.integration.test_exec_fix01_waits_db import _queue, _open

pytestmark = pytest.mark.integration


def test_pause_during_question_generation_resume_presents_saved_ask_once_without_new_provider(current, http):
    factory = current['factory']; request = _queue(current)
    run_evidence(request['id'], connection_factory=factory, gateway=RecordedEvidence())
    with factory() as c:
        assert orchestration._queue_assessment(c); c.commit()
        assessment = c.execute("SELECT id FROM m6_assessment_requests WHERE status='queued'").fetchone()
    run_assessment(assessment['id'], connection_factory=factory, gateway=RecordedAssessment())
    class PauseDuringQuestion:
        enabled = True
        def chat(self, messages, **_kwargs):
            value = json.loads(messages[1]['content'])
            # Real independent connection; proves generation holds no Cycle lock.
            with factory() as competing:
                competing.execute("SET LOCAL lock_timeout='3s'")
                m7_completion.control(competing, cycle_id=current['cycle_id'], key='pause-during-provider',
                    action='pause', reason='synthetic pause while M7 output is in flight', initiated_by=99)
                competing.commit()
            return json.dumps({'schema_version': 1, 'admissible': True,
                'text': 'Что вы имели в виду, когда назвали этот довод основным?',
                'purpose': 'clarify_meaning', 'indicator_ids': [value['indicator_ids'][0]],
                'resolving_information': ['смысл данного ответа'], 'refusal_reason': None}, ensure_ascii=False)
    with factory() as c:
        try:
            orchestration._clarify_interim(c, gateway=PauseDuringQuestion(), connection_factory=factory)
            c.commit()
        except ValueError as error:
            # Existing present rejects paused Cycle. Saving ASK is a detached
            # commit, so presentation must be retried after resume regardless.
            assert str(error) in {'M7_CLARIFICATION_TIME_UNAVAILABLE', 'M7_COLLECTION_CLOSED'}
            c.rollback()
    with factory() as c:
        decision_id = c.execute('SELECT id FROM m7_clarification_decisions ORDER BY created_at DESC LIMIT 1').fetchone()['id']
        saved = m7_clarification.read(c, str(decision_id))
        assert saved['status'] == 'ASK' and saved['question_turn_id'] is None
        assert _open(c, current)['interval_type'] == 'authorized_pause'
        m7_completion.control(c, cycle_id=current['cycle_id'], key='resume-after-provider', action='resume',
            reason='synthetic explicit resume', initiated_by=99); c.commit()
    class NeverCallQuestionProvider:
        enabled = True
        def chat(self, *_args, **_kwargs): raise AssertionError('saved ASK must not be regenerated')
    with factory() as c:
        orchestration._clarify_interim(c, gateway=NeverCallQuestionProvider(), connection_factory=factory); c.commit()
        shown = m7_clarification.read(c, str(decision_id))
        assert shown['question_turn_id'] is not None
        assert _open(c, current)['interval_type'] == 'collecting'
        assert c.execute("SELECT count(*) AS n FROM m5_dialogue_turns WHERE speaker_id='m7-clarification'").fetchone()['n'] == 1
