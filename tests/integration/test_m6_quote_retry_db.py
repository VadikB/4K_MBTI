"""Recorded M6 replies through the product handoff, dispatcher, and durable readback."""
import json
from uuid import uuid4

import pytest

from Api import m10_orchestration, m6_repository, m6_worker_v2
from Api.m10_product_flow import start_or_resume
from Api.m5_rule_engine import ControlledCharacterAdapter, ControlledSemanticAdapter
from Api.m5_scenario_runtime import build_c45, submit_turn, transition
from tests.integration.test_m10_product_path_db import EvidenceGateway, product_db

pytestmark = pytest.mark.integration


def candidate(value, base, shape):
    turn, = [turn for turn in value['turns'] if turn['speaker_type'] == 'assessee']
    assert turn['content'] == 'уточню цену, уточню срок'
    turn_id = turn['turn_id']
    criterion = value['criteria'][0]
    indicator = criterion['id']
    bundle = next(item for item in base['bundles'] if item['indicator_id'] == indicator)
    if shape in {'empty', 'initial_empty', 'irrelevant', 'unclear'}:
        bundle['opportunity_basis'] = 'Участник обозначил намерение, результат действия в ходе не представлен.'
    if shape in {'initial_empty', 'irrelevant', 'unclear'}:
        base['attribution_notes'] = [{
            'indicator_id': indicator, 'reason': 'unclear' if shape == 'unclear' else 'irrelevant',
            'explanation': 'Намерение уточнить срок не показывает способ проверки исходных данных.',
            'context_refs': [{'kind': 'turn', 'id': turn_id, 'meaning': 'Источник наблюдения о намерении'}],
        }]
    if shape in {'empty', 'initial_empty', 'irrelevant'}:
        return base
    short = shape in {'ambiguous', 'extra_start'}
    fragment = {'id': 'f', 'turn_id': turn_id, 'quote': 'уточню' if short else 'уточню срок'}
    if shape == 'extra_start':
        fragment['start'] = 0
    base['fragments'] = [fragment]
    if shape == 'fragment_only':
        return base
    base['signals'] = [{'id': 's', 'fragment_id': 'f', 'observation': 'Намерение уточнить срок',
                        'form_description': 'намерение', 'context_refs': []}]
    if shape == 'unclear':
        return base
    base['evidence'] = [{
        'id': 'e', 'indicator_id': indicator, 'm2_version': criterion['m2_version'], 'type': 'Simple',
        'interpretation': 'Намерение уточнить срок', 'bs_ids': ['s'], 'fragment_ids': ['f'],
        'attribution': {'function': criterion['function'], 'product': criterion['product'],
                        'evidence_pattern': criterion['evidence_pattern'], 'boundaries': criterion['boundary']},
        'ordered_turn_ids': [turn_id], 'context_refs': [], 'limitations': [],
    }]
    bundle['evidence_ids'] = ['e']
    return base


@pytest.mark.parametrize(('replies', 'expected_status', 'expected_codes', 'counts'), [
    (('extra_start', 'empty'), 'failed', [('M6_FRAGMENT_REPAIR_MISSING', 'fragments')], None),
    (('ambiguous', 'fragment_only'), 'failed', [
        ('M6_FRAGMENT_REPAIR_SIGNAL_MISSING', 'signals'), ('M6_FRAGMENT_REPAIR_EVIDENCE_MISSING', 'evidence'),
    ], None),
    (('complete',), 'succeeded', [], (1, 1, 1, 0)),
    (('extra_start', 'complete'), 'succeeded', [], (1, 1, 1, 0)),
    (('initial_empty',), 'succeeded', [], (0, 0, 0, 1)),
    (('ambiguous', 'irrelevant'), 'succeeded', [], (0, 0, 0, 1)),
    (('ambiguous', 'unclear'), 'succeeded', [], (1, 1, 0, 1)),
], ids=['schema-then-empty', 'quote-then-fragment-only', 'unique', 'clarified', 'initial-empty', 'irrelevant', 'unclear'])
def test_m6_quote_retry_worker(product_db, replies, expected_status, expected_codes, counts):
    class Gateway(EvidenceGateway):
        def __init__(self):
            self.calls = []

        def chat(self, messages, **kwargs):
            value = json.loads(messages[1]['content'])
            base = json.loads(super().chat(messages))
            self.calls.append(messages[-1]['content'])
            return json.dumps(candidate(value, base, replies[len(self.calls) - 1]), ensure_ascii=False)

    with product_db() as connection:
        started = start_or_resume(connection, user_id=99, key='retry-start')
        as_id = str(started['decision']['assessment_situation_id'])
        submit_turn(connection, assessment_situation_id=as_id, request_id='retry-turn', turn_id=str(uuid4()),
                    content='уточню цену, уточню срок', semantic_adapter=ControlledSemanticAdapter({}),
                    character_adapter=ControlledCharacterAdapter({}))
        transition(connection, assessment_situation_id=as_id, action='scenario_end',
                   reason='participant_completed', request_id='retry-end')
        handoff = build_c45(connection, as_id, mode='interim')
        request = m10_orchestration.enqueue_handoff(connection, handoff_id=str(handoff['handoff_id']), created_by=99)
        connection.commit()

    gateway = Gateway()
    assert m6_worker_v2.recover_pending(product_db, gateway=gateway)
    with product_db() as connection:
        row = m6_repository.read_request(connection, request['id'])
        attempt = connection.execute('''SELECT status,error_code,trace_json FROM m6_processing_attempts
            WHERE request_id=%s''', (request['id'],)).fetchone()
        revision = row['analysis_revision_id']
        analysis = m6_repository.read_analysis(connection, revision)['analysis'] if revision else None
        if not revision:
            assert connection.execute('SELECT count(*) AS n FROM m6_bundle_revisions').fetchone()['n'] == 0
    diagnostics = attempt['trace_json']['validation_attempts']
    errors = [(issue['code'], issue['path']) for issue in diagnostics[-1].get('validation_errors', [])]
    observed_counts = tuple(len(analysis[key]) for key in ('fragments', 'signals', 'evidence', 'attribution_notes')) if analysis else None
    spans = [[item['start'], item['end']] for item in analysis['fragments']] if analysis else []
    print('M6_WORKER_READBACK ' + json.dumps({
        'replies': replies, 'mechanism': request['mechanism_json']['ref'], 'calls': len(gateway.calls),
        'request_status': row['status'], 'attempt_status': attempt['status'], 'error_code': attempt['error_code'],
        'analysis_counts': observed_counts, 'spans': spans, 'validation_attempts': diagnostics,
    }, ensure_ascii=False))
    assert len(gateway.calls) == len(replies)
    assert row['status'] == attempt['status'] == expected_status
    assert errors == expected_codes
    assert observed_counts == counts
    assert attempt['error_code'] == (expected_codes[0][0] if expected_codes else None)
    if spans:
        assert spans == [[13, 24]]
    if analysis and analysis['evidence']:
        fragment, = analysis['fragments']
        signal, = analysis['signals']
        evidence, = analysis['evidence']
        assert evidence['bs_ids'] == [signal['id']]
        assert evidence['fragment_ids'] == [signal['fragment_id']] == [fragment['id']]
        assert evidence['indicator_id'] == request['input_json']['criteria'][0]['id']
    if replies[0] == 'extra_start':
        assert diagnostics[0]['validation_errors'] == [
            {'code': 'extra_forbidden', 'path': 'fragments.0.start'},
            {'code': 'M6_FRAGMENT_QUOTE_AMBIGUOUS', 'path': 'fragments.0.quote'},
        ]
