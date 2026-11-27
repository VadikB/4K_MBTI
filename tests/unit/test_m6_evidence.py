import copy
import json
import pytest
from pydantic import ValidationError
from Api.m6_contracts import validate_analysis
from Api.m6_package import load_mechanism, verify_mechanism
from Api.m6_evidence_service import evaluate
from Api.m6_evidence_service_v2 import validate_current_analysis
from Api.assessment_configuration import definition_checksum

pytestmark=pytest.mark.unit


def material():
    return {'turns':[{'turn_id':'t1','speaker_type':'assessee','sequence_no':1,'content':'Да 🙂 нет'}],
            'events':[], 'materials':[], 'indicator_targets':[{'indicator_id':'K1.I01','m2_version':'v1.1'}],
            'criteria':[{'id':'K1.I01','m2_version':'v1.1','function':'f','product':'p',
                         'evidence_pattern':'e','boundary':'b'}]}


def output(empty=False):
    return {'schema_version':1,
        'fragments':[] if empty else [{'id':'f1','turn_id':'t1','start':3,'end':4,'quote':'🙂'}],
        'signals':[] if empty else [{'id':'s1','fragment_id':'f1','observation':'synthetic','form_description':'synthetic','context_refs':[]}],
        'evidence':[] if empty else [{'id':'e1','indicator_id':'K1.I01','m2_version':'v1.1','type':'Simple','interpretation':'synthetic',
            'bs_ids':['s1'],'fragment_ids':['f1'],'attribution':{'function':'f','product':'p','evidence_pattern':'e','boundaries':'b'},
            'context_refs':[],'limitations':[],'ordered_turn_ids':['t1']}],
        'bundles':[{'indicator_id':'K1.I01','evidence_ids':[] if empty else ['e1'],
            'opportunity_basis':'synthetic fixture, not approved GC','context_refs':[],'limitations':[],'contradictions':[]}],
        'attribution_notes':[]}


@pytest.mark.parametrize('empty',[False,True])
def test_chain_and_empty_bundle(empty):
    assert validate_analysis(output(empty),material())['bundles'][0]['evidence_ids']==([] if empty else ['e1'])


@pytest.mark.parametrize('mutation',[
    lambda x:x['fragments'][0].update(quote='bad'),
    lambda x:x['fragments'][0].update(end=99),
    lambda x:x['signals'][0].update(fragment_id='unknown'),
    lambda x:x['evidence'][0].update(indicator_id='K2.I01'),
    lambda x:x['evidence'][0].update(m2_version='v9'),
    lambda x:x['evidence'][0].update(type='Composite'),
    lambda x:x['bundles'][0].update(evidence_ids=[]),
    lambda x:x.update(level='L0'),
    lambda x:x['signals'][0].update(context_refs=[{'kind':'event','id':'missing','meaning':'bad'}]),
])
def test_invalid_chain_rejected(mutation):
    value=output(); mutation(value)
    with pytest.raises((ValueError,ValidationError)): validate_analysis(value,material())


def test_system_turn_cannot_be_fragment():
    value=material();value['turns'][0]['speaker_type']='system'
    with pytest.raises(ValueError,match='AUTHOR'): validate_analysis(output(),value)


def test_attribution_must_equal_frozen_m2_criterion():
    result = output()
    result['evidence'][0]['attribution']['function'] = 'invented'
    with pytest.raises(ValueError, match='M6_ATTRIBUTION_MISMATCH'):
        validate_analysis(result, material())


@pytest.mark.parametrize('kind,record', [
    ('turn', {'turn_id':'t2','speaker_type':'assessee','sequence_no':2,'content':'later'}),
    ('event', {'event_id':'e2','sequence_no':2}),
    ('material', {'material_id':'m2','available_sequence':2}),
])
def test_signal_cannot_reference_future_context(kind, record):
    value = material()
    collection = {'turn':'turns', 'event':'events', 'material':'materials'}[kind]
    value[collection].append(record)
    result = output()
    ref_id = next(v for k, v in record.items() if k.endswith('_id'))
    result['signals'][0]['context_refs'] = [{'kind':kind, 'id':ref_id, 'meaning':'future'}]
    with pytest.raises(ValueError, match='M6_CONTEXT_FUTURE'):
        validate_analysis(result, value)


def test_evidence_context_may_use_later_composite_fragment_but_not_future_after_it():
    value = material()
    value['turns'] += [
        {'turn_id':'t2','speaker_type':'assessee','sequence_no':2,'content':'second'},
        {'turn_id':'t3','speaker_type':'assessee','sequence_no':3,'content':'future'},
    ]
    result = output()
    result['fragments'].append({'id':'f2','turn_id':'t2','start':0,'end':6,'quote':'second'})
    result['signals'].append({'id':'s2','fragment_id':'f2','observation':'second','form_description':'action','context_refs':[]})
    evidence = result['evidence'][0]
    evidence.update(type='Composite', bs_ids=['s1','s2'], fragment_ids=['f1','f2'],
                    composite_basis='ordered change', ordered_turn_ids=['t1','t2'],
                    context_refs=[{'kind':'turn','id':'t2','meaning':'second manifestation'}])
    assert validate_current_analysis(result, value)['evidence'][0]['type'] == 'Composite'
    evidence['type'] = 'Simple'
    with pytest.raises(ValueError, match='M6_SIMPLE_BASIS'):
        validate_current_analysis(result, value)
    assert validate_analysis(result, value)['evidence'][0]['type'] == 'Simple'
    evidence['type'] = 'Composite'
    evidence['context_refs'] = [{'kind':'turn','id':'t3','meaning':'future'}]
    with pytest.raises(ValueError, match='M6_CONTEXT_FUTURE'):
        validate_analysis(result, value)


def test_snapshot_prompt_and_no_numeric_assessment(tmp_path):
    mechanism=load_mechanism('m6_evidence/1.0.0')
    h=definition_checksum(mechanism)
    class Gateway:
        enabled=True
        def chat(self,messages,**kwargs):
            assert mechanism['prompt'] in messages[0]['content']
            return json.dumps(output(True))
    assert evaluate(material(),mechanism,h,gateway=Gateway())[0]['evidence']==[]
    changed=copy.deepcopy(mechanism);changed['prompt']='changed'
    with pytest.raises(ValueError): verify_mechanism(changed,h)


def test_current_mechanism_is_new_immutable_draft():
    from Api.m6_package_v2 import load_mechanism as load_current
    mechanism = load_current()
    assert mechanism['manifest']['version'] == '1.0.1'
    assert mechanism['manifest']['supersedes'] == 'm6_evidence/1.0.0'
    assert 'quote == turn.content[start:end]' in mechanism['prompt']
    assert mechanism['operation']['provider_contract']['version'] == '1.0.0'
    assert mechanism['operation']['thinking'] == {'type': 'disabled'}
    verify_mechanism(mechanism, definition_checksum(mechanism))


def test_current_mechanism_retries_rejected_json_without_coercion():
    from Api.m6_evidence_service_v2 import evaluate as evaluate_current
    from Api.m6_package_v2 import load_mechanism as load_current
    mechanism = load_current()
    class Gateway:
        enabled = True
        calls = 0
        def chat(self, messages, **kwargs):
            self.calls += 1
            return 'not json' if self.calls == 1 else json.dumps(output(True))
    gateway = Gateway()
    result, trace = evaluate_current(material(), mechanism, definition_checksum(mechanism), gateway=gateway)
    assert result['evidence'] == [] and gateway.calls == 2
    assert [x['status'] for x in trace['validation_attempts']] == ['rejected', 'accepted']


def test_current_mechanism_preserves_domain_validation_error_in_trace():
    from Api.m6_evidence_service_v2 import evaluate as evaluate_current
    from Api.m6_package_v2 import load_mechanism as load_current
    mechanism = load_current()
    invalid = output(True)
    invalid['bundles'][0]['evidence_ids'] = ['missing-evidence']

    class Gateway:
        enabled = True
        def chat(self, messages, **kwargs):
            return json.dumps(invalid)

    with pytest.raises(ValueError, match='M6_BUNDLE_REFERENCE') as failure:
        evaluate_current(material(), mechanism, definition_checksum(mechanism), gateway=Gateway())
    attempts = failure.value.ai_trace['validation_attempts']
    assert attempts[-1]['error_code'] == 'M6_BUNDLE_REFERENCE'


def test_fragment_span_retry_explains_exact_unicode_invariant():
    from Api.m6_validation_retry import call_and_validate
    calls = []

    class Gateway:
        enabled = True
        def chat(self, messages, **kwargs):
            calls.append(messages)
            return json.dumps({'attempt': len(calls)})

    def reject(_value):
        raise ValueError('M6_FRAGMENT_SPAN')

    with pytest.raises(ValueError, match='M6_FRAGMENT_SPAN'):
        call_and_validate(gateway=Gateway(), messages=[{'role': 'user', 'content': '{}'}],
                          operation={'provider': 'deepseek', 'endpoint': 'https://api.deepseek.com/chat/completions',
                                     'model': 'deepseek-flash', 'parameters': {}, 'response_format': 'text'},
                          routing_key='span', validate=reject, max_attempts=2)
    feedback = calls[1][-1]['content']
    assert 'end-start' in feedback and 'content[start:end]' in feedback and 'Unicode' in feedback


@pytest.mark.parametrize(("quote", "speaker", "offsets"), [
    ("🙂", "assessee", "start=3, end=4"),
    ("после", "assessee", "start=5, end=10"),
    ("До", "assessee", None),
    ("После", "assessee", None),
    ("🙂", "character", None),
])
def test_fragment_span_retry_supplies_only_unambiguous_deterministic_offsets(quote, speaker, offsets):
    from Api.m6_validation_retry import _fragment_span_hints
    original = {'turns': [{'turn_id': 't1', 'speaker_type': speaker, 'content': 'До 🙂 после и До'}]}
    candidate = {'fragments': [None, {'id': 'f1', 'turn_id': 't1', 'start': 0, 'end': 99, 'quote': quote}]}
    hints = _fragment_span_hints(candidate, [{'role': 'user', 'content': json.dumps(original, ensure_ascii=False)}])
    if offsets is None:
        assert hints == ""
    else:
        assert hints.endswith(f"fragments[1]: {offsets}.")


@pytest.mark.parametrize(("mutation", "path", "rule"), [
    ({"start": 4}, "end", "span_end_not_after_start"),
    ({"end": 99}, "end", "span_end_exceeds_turn"),
    ({"quote": "иное"}, "quote", "span_quote_mismatch"),
])
def test_current_mechanism_records_a_safe_specific_span_failure(mutation, path, rule):
    from Api.m6_evidence_service_v2 import evaluate as evaluate_current
    from Api.m6_package_v2 import load_mechanism as load_current

    mechanism = load_current()
    invalid = output()
    invalid['fragments'][0].update(mutation)

    class Gateway:
        enabled = True

        def chat(self, messages, **kwargs):
            return json.dumps(invalid)

    with pytest.raises(ValueError, match="M6_FRAGMENT_SPAN") as failure:
        evaluate_current(material(), mechanism, definition_checksum(mechanism), gateway=Gateway())
    first, second = failure.value.ai_trace["validation_attempts"]
    for check in (first, second):
        assert check["error_code"] == "M6_FRAGMENT_SPAN"
        assert check["stage"] == "contract"
        assert check["issues"] == [{"path": ["fragments", 0, path], "rule": rule}]


def test_schema_failure_does_not_copy_extra_field_or_input_into_diagnostic():
    from Api.m6_evidence_service_v2 import evaluate as evaluate_current
    from Api.m6_package_v2 import load_mechanism as load_current

    mechanism = load_current()
    invalid = output()
    invalid["fragments"][0]["private-field"] = "private-value"

    class Gateway:
        enabled = True

        def chat(self, messages, **kwargs):
            if len(messages) > 2:
                assert "private-field" not in messages[-1]["content"]
                assert "private-value" not in messages[-1]["content"]
            return json.dumps(invalid)

    with pytest.raises(ValidationError) as failure:
        evaluate_current(material(), mechanism, definition_checksum(mechanism), gateway=Gateway())
    for check in failure.value.ai_trace["validation_attempts"]:
        assert check["error_code"] == "M6_SCHEMA_VALIDATION"
        assert check["issues"] == [{"path": ["fragments", 0, "<extra>"], "rule": "extra_forbidden"}]


def test_retry_repeats_exact_attribution_mapping_without_interpretation():
    from Api.m6_validation_retry import _attribution_hints
    hints = _attribution_hints([{'role': 'user', 'content': json.dumps(material(), ensure_ascii=False)}])
    assert 'дословной копией' in hints
    assert '"K1.I01"' in hints and '"boundaries":"b"' in hints


def test_context_reference_retry_lists_exact_closed_namespaces_without_coercion():
    from Api.m6_validation_retry import call_and_validate
    original = material()
    original['events'] = [{'event_id': 'event-1', 'sequence_no': 1}]
    original['materials'] = [{'material_id': 'material-1', 'available_sequence': 1}]
    original['initial_presentation'] = {'character_id': 'speaker-not-a-context-ref'}
    calls = []

    class Gateway:
        enabled = True
        def chat(self, messages, **kwargs):
            calls.append(messages)
            return json.dumps(output())

    def reject(_value):
        raise ValueError('M6_CONTEXT_REFERENCE')

    with pytest.raises(ValueError, match='M6_CONTEXT_REFERENCE'):
        call_and_validate(
            gateway=Gateway(),
            messages=[{'role': 'user', 'content': json.dumps(original, ensure_ascii=False)}],
            operation={'provider': 'deepseek', 'endpoint': 'https://api.deepseek.com/chat/completions',
                       'model': 'deepseek-flash', 'parameters': {}, 'response_format': 'text'},
            routing_key='context-ref', validate=reject, max_attempts=2,
        )
    feedback = calls[1][-1]['content']
    assert '"turn":["t1"]' in feedback
    assert '"event":["event-1"]' in feedback
    assert '"material":["material-1"]' in feedback
    assert 'speaker-not-a-context-ref' not in feedback
    assert 'не заменяй ошибочную ссылку произвольной допустимой' in feedback


def test_current_worker_keeps_safe_domain_error_code():
    from Api.m6_worker_v2 import _error_code
    assert _error_code(ValueError('M6_CONTEXT_REFERENCE')) == 'M6_CONTEXT_REFERENCE'
    assert (_error_code(ValueError('DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED'))
            == 'DEEPSEEK_OPERATION_IDENTITY_UNSUPPORTED')
    assert _error_code(ValueError('provider returned sensitive arbitrary text')) == 'ValueError'


def test_invalid_json_keeps_trace():
    mechanism=load_mechanism('m6_evidence/1.0.0')
    class Gateway:
        enabled=True
        def chat(self,*args,**kwargs):return 'not json'
    with pytest.raises(ValueError) as failure: evaluate(material(),mechanism,definition_checksum(mechanism),gateway=Gateway())
    assert failure.value.ai_trace['response']['content']=='not json'


def test_package_corruption_rejected(tmp_path):
    from Api.m6_package import PACKAGE
    for name in ('manifest.json','prompt.md'):(tmp_path/name).write_bytes((PACKAGE/name).read_bytes())
    (tmp_path/'prompt.md').write_text('changed')
    with pytest.raises(ValueError,match='CHECKSUM'):load_mechanism('m6_evidence/1.0.0',tmp_path)


def test_context_limit_never_truncates_or_calls_provider():
    mechanism=load_mechanism('m6_evidence/1.0.0');mechanism['max_input_bytes']=1
    class Gateway:
        enabled=True
        def chat(self,*args,**kwargs):raise AssertionError('provider must not be called')
    with pytest.raises(ValueError,match='CONTEXT_LIMIT'):
        evaluate(material(),mechanism,definition_checksum(mechanism),gateway=Gateway())


def quote_mechanism():
    from Api.m6_package_v2 import QUOTE_REF, load_mechanism

    return load_mechanism(QUOTE_REF)


def quote_candidate(quote, *, turn_id='t1'):
    return {
        **output(), 'schema_version': 2,
        'fragments': [{'id': 'f1', 'turn_id': turn_id, 'quote': quote}],
    }


class RecordedQuotes:
    enabled = True

    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        return json.dumps(next(self.responses), ensure_ascii=False)


def run_quote_extraction(source, gateway, mechanism=None):
    from Api.m6_evidence_service_v2 import evaluate

    mechanism = mechanism or quote_mechanism()
    return evaluate(source, mechanism, definition_checksum(mechanism), gateway=gateway)


@pytest.mark.parametrize(('text', 'quote', 'span'), [
    ('Сначала сверю сроки. Затем напишу заказчику.', 'сверю сроки', (8, 19)),
    ('🧪 е\u0301 сверю сроки', 'е\u0301 сверю', (2, 10)),
])
def test_server_span_uses_code_points_and_exact_bytes(text, quote, span):
    source = material()
    source['turns'][0]['content'] = text
    candidate = quote_candidate(quote)
    gateway = RecordedQuotes(candidate)
    analysis, trace = run_quote_extraction(source, gateway)
    fragment, = analysis['fragments']
    assert (fragment['start'], fragment['end']) == span
    assert text[slice(*span)].encode() == fragment['quote'].encode() == quote.encode()
    assert analysis['signals'][0]['fragment_id'] == fragment['id']
    assert analysis['evidence'][0]['bs_ids'] == [analysis['signals'][0]['id']]
    assert analysis['schema_version'] == 1
    assert len(gateway.calls) == 1
    payload = json.loads(gateway.calls[0][1]['content'])
    assert payload['schema_version'] == 2
    assert payload['turns'][0]['content'].encode() == text.encode()
    assert json.loads(trace['response']['content']) == candidate
    assert trace['assembled_analysis'] == {'contract': 'M6.EvidenceAnalysis/1', 'checksum': definition_checksum(analysis)}


def test_same_quote_rejected_twice_with_wrong_legacy_offsets():
    from Api.m6_package_v2 import load_mechanism

    source = material()
    text = 'Сначала сверю сроки. Затем напишу заказчику.'
    source['turns'][0]['content'] = text
    legacy = output()
    legacy['fragments'][0].update(quote='сверю сроки', start=7, end=18)
    gateway = RecordedQuotes(legacy, legacy)
    with pytest.raises(ValueError, match='^M6_FRAGMENT_SPAN$') as failure:
        run_quote_extraction(source, gateway, load_mechanism())
    attempts = failure.value.ai_trace['validation_attempts']
    assert len(gateway.calls) == 2
    assert text[7:18] == ' сверю срок'
    assert [attempt['validation_errors'] for attempt in attempts] == [
        [{'code': 'M6_FRAGMENT_RANGE_MISMATCH', 'path': 'fragments.0.quote'}],
    ] * 2


@pytest.mark.parametrize(('text', 'short', 'long', 'span'), [
    ('уточню цену, уточню срок', 'уточню', 'уточню срок', (13, 24)),
    ('ааа', 'аа', 'ааа', (0, 3)),
])
def test_repeated_quote_is_never_selected_arbitrarily(text, short, long, span):
    source = material()
    source['turns'][0]['content'] = text
    ambiguous = quote_candidate(short)
    gateway = RecordedQuotes(ambiguous, quote_candidate(long))
    analysis, trace = run_quote_extraction(source, gateway)
    fragment, = analysis['fragments']
    assert (fragment['start'], fragment['end']) == span
    assert [attempt['status'] for attempt in trace['validation_attempts']] == ['rejected', 'accepted']
    assert len(gateway.calls) == 2
    assert 'из того же хода' in gateway.calls[1][-1]['content']
    gateway = RecordedQuotes(ambiguous, ambiguous)
    with pytest.raises(ValueError, match='^M6_FRAGMENT_QUOTE_AMBIGUOUS$') as failure:
        run_quote_extraction(source, gateway)
    assert [attempt['error_code'] for attempt in failure.value.ai_trace['validation_attempts']] == [
        'M6_FRAGMENT_QUOTE_AMBIGUOUS', 'M6_FRAGMENT_QUOTE_AMBIGUOUS',
    ]
    assert len(gateway.calls) == 2


@pytest.mark.parametrize(('turn_id', 'quote', 'code', 'path'), [
    ('t1', 'сопоставлю дедлайны', 'M6_FRAGMENT_QUOTE_NOT_FOUND', 'quote'),
    ('t1', 'из другого ответа', 'M6_FRAGMENT_QUOTE_NOT_FOUND', 'quote'),
    ('t1', 'é', 'M6_FRAGMENT_QUOTE_NOT_FOUND', 'quote'),
    ('presenter', 'реплика ведущего', 'M6_FRAGMENT_AUTHOR', 'turn_id'),
    ('unknown', 'сверю сроки', 'M6_FRAGMENT_TURN_UNKNOWN', 'turn_id'),
])
def test_quote_rejection_is_local_to_the_frozen_turn(turn_id, quote, code, path):
    source = material()
    source['turns'][0]['content'] = 'e\u0301 Сначала сверю сроки.'
    source['turns'].extend([
        {'turn_id': 't2', 'speaker_type': 'assessee', 'sequence_no': 2, 'content': 'из другого ответа, сверю сроки'},
        {'turn_id': 'presenter', 'speaker_type': 'system', 'sequence_no': 3, 'content': 'реплика ведущего'},
    ])
    candidate = quote_candidate(quote, turn_id=turn_id)
    gateway = RecordedQuotes(candidate, candidate)
    with pytest.raises(ValueError, match=code) as failure:
        run_quote_extraction(source, gateway)
    attempts = failure.value.ai_trace['validation_attempts']
    assert [item['attempt_no'] for item in attempts] == [1, 2]
    assert all(item['validation_errors'] == [{'code': code, 'path': f'fragments.0.{path}'}] for item in attempts)
    # The same exact phrase in an adjacent turn has no effect on the selected turn.
    gateway = RecordedQuotes(quote_candidate('сверю сроки'))
    accepted, _ = run_quote_extraction(source, gateway)
    assert accepted['fragments'][0]['start'] == 11
    assert len(gateway.calls) == 1


def test_full_analysis_validation_reports_all_established_violations():
    source = material()
    source['turns'].append({'turn_id': 'later', 'speaker_type': 'assessee', 'sequence_no': 2, 'content': 'later'})
    candidate = quote_candidate('🙂')
    candidate['evidence'][0]['bs_ids'] = ['broken']
    candidate['evidence'][0]['attribution']['product'] = 'invented'
    candidate['evidence'][0]['context_refs'] = [{'kind': 'turn', 'id': 'later', 'meaning': 'future'}]
    gateway = RecordedQuotes(candidate, candidate)
    with pytest.raises(ValueError, match='M6_ATTRIBUTION_MISMATCH') as failure:
        run_quote_extraction(source, gateway)
    assert failure.value.ai_trace['validation_attempts'][0]['validation_errors'] == [
        {'code': 'M6_ATTRIBUTION_MISMATCH', 'path': 'evidence.0.attribution.product'},
        {'code': 'M6_EVIDENCE_REFERENCE', 'path': 'evidence.0.bs_ids.0'},
        {'code': 'M6_CONTEXT_FUTURE', 'path': 'evidence.0.context_refs.0.id'},
    ]


def test_schema_diagnostics_exclude_provider_controlled_values_and_field_names():
    source = material()
    candidate = quote_candidate('')
    candidate['fragments'][0]['private participant text'] = 'private participant text'
    candidate['fragments'][0]['start'] = 3
    gateway = RecordedQuotes(candidate, quote_candidate('🙂'))
    analysis, trace = run_quote_extraction(source, gateway)
    assert analysis['fragments'][0]['start'] == 3
    assert trace['validation_attempts'][0]['validation_errors'] == [
        {'code': 'string_too_short', 'path': 'fragments.0.quote'},
        {'code': 'extra_forbidden', 'path': 'fragments.0.<extra>'},
        {'code': 'extra_forbidden', 'path': 'fragments.0.start'},
    ]
    assert 'private participant text' not in gateway.calls[1][-1]['content']
    assert 'private participant text' not in json.dumps(trace['validation_attempts'])
    first, _ = trace['provider_attempts']
    assert json.loads(first['trace']['response']['content']) == candidate


def test_valid_empty_evidence_uses_one_call():
    gateway = RecordedQuotes({**output(True), 'schema_version': 2})
    analysis, _ = run_quote_extraction(material(), gateway)
    assert analysis == output(True)
    assert len(gateway.calls) == 1


@pytest.mark.parametrize(('repair', 'reason'), [
    ({**output(True), 'schema_version': 2}, 'M6_FRAGMENT_REPAIR_MISSING'),
    (quote_candidate('уточню срок', turn_id='t2'), 'M6_FRAGMENT_REPAIR_TURN'),
    (quote_candidate('проверю заказ'), 'M6_FRAGMENT_REPAIR_QUOTE'),
])
def test_disambiguation_preserves_the_fragment_and_its_turn(repair, reason):
    source = material()
    source['turns'][0]['content'] = 'уточню цену, уточню срок, проверю заказ'
    source['turns'].append({'turn_id': 't2', 'speaker_type': 'assessee', 'sequence_no': 2, 'content': 'уточню срок'})
    gateway = RecordedQuotes(quote_candidate('уточню'), repair)
    with pytest.raises(ValueError, match=reason):
        run_quote_extraction(source, gateway)
    assert len(gateway.calls) == 2


def test_absent_quote_can_be_repaired_verbatim_within_budget():
    source = material()
    source['turns'][0]['content'] = 'Сначала сверю сроки. Затем напишу заказчику.'
    gateway = RecordedQuotes(quote_candidate('сопоставлю дедлайны'), quote_candidate('сверю сроки'))
    result, trace = run_quote_extraction(source, gateway)
    assert result['fragments'][0]['start'] == 8
    assert trace['validation_attempts'][0]['error_code'] == 'M6_FRAGMENT_QUOTE_NOT_FOUND'
    assert len(gateway.calls) == 2


@pytest.mark.parametrize(('quote', 'reason'), [
    ('🙂', None), ('не было', 'M6_FRAGMENT_QUOTE_NOT_FOUND'), ('аа', 'M6_FRAGMENT_QUOTE_AMBIGUOUS'),
])
def test_legacy_range_diagnostic_distinguishes_missing_and_ambiguous_quotes(quote, reason):
    from Api.m6_package_v2 import load_mechanism

    source = material()
    source['turns'][0]['content'] = 'Да 🙂 ааа'
    legacy = output()
    legacy['fragments'][0].update(quote=quote, end=99)
    gateway = RecordedQuotes(legacy, legacy)
    with pytest.raises(ValueError, match='^M6_FRAGMENT_SPAN$') as failure:
        run_quote_extraction(source, gateway, load_mechanism())
    expected = [{'code': 'M6_FRAGMENT_RANGE_INVALID', 'path': 'fragments.0.end'}]
    if reason:
        expected.append({'code': reason, 'path': 'fragments.0.quote'})
    assert failure.value.ai_trace['validation_attempts'][0]['validation_errors'] == expected


def test_legacy_schema_diagnostic_lists_each_rejected_field():
    from Api.m6_package_v2 import load_mechanism

    legacy = output()
    legacy['fragments'][0]['end'] = 0
    legacy['signals'][0]['observation'] = ''
    legacy['evidence'][0]['type'] = 'Unknown'
    gateway = RecordedQuotes(legacy, output())
    _, trace = run_quote_extraction(material(), gateway, load_mechanism())
    assert trace['validation_attempts'][0]['validation_errors'] == [
        {'code': 'greater_than', 'path': 'fragments.0.end'},
        {'code': 'string_too_short', 'path': 'signals.0.observation'},
        {'code': 'literal_error', 'path': 'evidence.0.type'},
    ]


@pytest.mark.parametrize('note_shape', ['wrong-turn', 'blank', 'unclear-without-signal'])
def test_retry_rejects_unsubstantiated_attribution_note(note_shape):
    source = material()
    source['turns'][0]['content'] = 'уточню цену, уточню срок'
    source['turns'].append({'turn_id': 't2', 'speaker_type': 'assessee', 'sequence_no': 2, 'content': 'другой ответ'})
    repair = quote_candidate('уточню срок')
    empty = output(True)
    repair.update(signals=[], evidence=[], bundles=empty['bundles'])
    repair['attribution_notes'] = [{
        'indicator_id': 'K1.I01', 'reason': 'unclear' if note_shape == 'unclear-without-signal' else 'irrelevant',
        'explanation': ' ' if note_shape == 'blank' else 'Отсутствует проверка данных',
        'context_refs': [{'kind': 'turn', 'id': 't2' if note_shape == 'wrong-turn' else 't1', 'meaning': 'Основание'}],
    }]
    gateway = RecordedQuotes(quote_candidate('уточню'), repair)
    with pytest.raises(ValueError, match='M6_FRAGMENT_REPAIR_SIGNAL_MISSING') as failure:
        run_quote_extraction(source, gateway)
    assert failure.value.ai_trace['validation_attempts'][1]['validation_errors'] == [
        {'code': 'M6_FRAGMENT_REPAIR_SIGNAL_MISSING', 'path': 'signals'},
        {'code': 'M6_FRAGMENT_REPAIR_EVIDENCE_MISSING', 'path': 'evidence'},
    ]


def test_retry_requires_the_same_indicator_even_with_a_valid_chain():
    source = material()
    source['turns'][0]['content'] = 'уточню цену, уточню срок'
    source['indicator_targets'].append({'indicator_id': 'K1.I02', 'm2_version': 'v1.1'})
    source['criteria'].append({**source['criteria'][0], 'id': 'K1.I02'})
    first = quote_candidate('уточню')
    first['bundles'].append({**first['bundles'][0], 'indicator_id': 'K1.I02', 'evidence_ids': []})
    repair = quote_candidate('уточню срок')
    repair['bundles'][0]['evidence_ids'] = []
    repair['bundles'].append({**first['bundles'][1], 'evidence_ids': ['e1']})
    repair['evidence'][0]['indicator_id'] = 'K1.I02'
    with pytest.raises(ValueError, match='M6_FRAGMENT_REPAIR_EVIDENCE_MISSING'):
        run_quote_extraction(source, RecordedQuotes(first, repair))
