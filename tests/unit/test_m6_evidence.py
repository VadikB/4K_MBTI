import copy
import json
import pytest
from pydantic import ValidationError
from Api.m6_contracts import validate_analysis
from Api.m6_package import load_mechanism, verify_mechanism
from Api.m6_evidence_service import evaluate
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
    assert validate_analysis(result, value)['evidence'][0]['type'] == 'Composite'
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
