from copy import deepcopy
import json
from pathlib import Path
import pytest
from Api import m6_admission as admission
from Api.m6_admission_package import load_mechanism
from Api.m6_cycle_aggregation import calculate
from tests.m6_admission_fixture import RecordedAdmissionGateway


class Result:
    def __init__(self, row): self.row = row
    def fetchone(self): return self.row


class Connection:
    def __init__(self, required=1): self.required = required
    def execute(self, query, params):
        return Result({'observation_requirements_json':[
            {'indicator_id':'K1.I13','distinct_as_required':self.required}]} if self.required else None)


def observation(n, level='L1'):
    return {'indicator_id':'K1.I13','assessment_situation_id':f'as{n}','revision_id':f'r{n}',
            'outcome':level,'opportunity':'PRESENT'}


@pytest.fixture
def material_resolver(monkeypatch):
    fixture = json.loads(Path('tests/fixtures/m6_gc/v1/candidates/independent.json').read_text())
    def resolve(connection, *, cycle_id, observations):
        obs = observations[0]
        material = deepcopy(fixture['material']);material['as_id'] = obs['assessment_situation_id']
        return [{'revision_id':obs['revision_id'],'material':material,'evidence_analysis':fixture['draft_analysis'],
                 'bundle':next(x for x in fixture['draft_analysis']['bundles'] if x['indicator_id']==obs['indicator_id']),
                 'criterion':material['criteria'][0],'target':{'indicator_id':obs['indicator_id']}}]
    monkeypatch.setattr(admission, 'resolve', resolve)
    return resolve


def run(observations, gateway, required=1):
    version, decisions, limitations = admission.decide(Connection(required), cycle_id='cycle', observations=observations, gateway=gateway)
    assert version == admission.VERSION
    result = calculate(hierarchy=[{'skill_id':'K1.3','components':[{'component_id':'K1.C07','indicator_ids':['K1.I13']}]}],
        observations=observations,decisions=decisions,planned_indicator_ids=['K1.I13'],composition_version='v')
    return decisions[0], result


def test_variation_l1_l3_single_zero_and_plan_sufficiency(material_resolver):
    d, result = run([observation(1),observation(2,'L3')],RecordedAdmissionGateway(),2)
    assert d['numeric_admissible']
    assert result['indicator_contributions'][0]['score']['value']==2
    assert result['indicator_contributions'][0]['spread']==2
    d, result = run([observation(1,'L0')],RecordedAdmissionGateway())
    assert result['skill_outcomes'][0]['score']['value']==0
    for required in (2,None):
        d, result=run([observation(1)],RecordedAdmissionGateway(),required)
        assert d['interpretation_admissible'] and not d['numeric_admissible']
        assert result['skill_outcomes'][0]['outcome']=='result_without_score'


@pytest.mark.parametrize('joint',['NOT_COMPARABLE','INSUFFICIENT_MATERIAL'])
def test_no_mean_keeps_exact_individual_basis(material_resolver,joint):
    d,result=run([observation(1),observation(2,'L3')],RecordedAdmissionGateway(joint=joint))
    assert d['interpretable_revision_ids']==['r1','r2'] and not d['included_revision_ids']
    assert result['skill_outcomes'][0]['outcome']=='result_without_score'


def test_exclusion_changes_denominator_not_required_coverage(material_resolver):
    d,result=run([observation(1),observation(2,'L3')],RecordedAdmissionGateway(individual={'r2':'NOT_ADMITTED'}))
    assert d['included_revision_ids']==['r1'] and d['excluded_revision_ids']==['r2']
    assert result['indicator_contributions'][0]['score']['value']==1
    assert result['indicator_contributions'][0]['as_count']==1
    assert result['coverage']['cycle_plan']['admissible_contributions']['denominator']==1
    d,result=run([observation(1)],RecordedAdmissionGateway(individual='NOT_ADMITTED'))
    assert result['skill_outcomes'][0]['outcome']=='no_result'


@pytest.mark.parametrize('stage',['individual','joint'])
def test_failure_not_ie_and_no_fallback(material_resolver,stage):
    d,result=run([observation(1)],RecordedAdmissionGateway(fail=stage))
    assert not d['numeric_admissible']
    assert (d['individual'][0] if stage=='individual' else d['joint'])['status']=='PROCESSING_FAILED'
    assert result['skill_outcomes'][0]['outcome']==('no_result' if stage=='individual' else 'result_without_score')


@pytest.mark.parametrize('stage',['individual','joint'])
@pytest.mark.parametrize('fault',['timeout','invalid_json','schema','foreign_ref'])
def test_processing_fault_matrix_is_technical_not_substantive(material_resolver,stage,fault):
    class Fault(RecordedAdmissionGateway):
        def chat(self,messages,**kwargs):
            value=json.loads(messages[1]['content'])
            if value['stage'] != stage:
                return super().chat(messages,**kwargs)
            if fault == 'timeout': raise TimeoutError('synthetic timeout')
            if fault == 'invalid_json': return '{'
            valid=json.loads(super().chat(messages,**kwargs))
            if fault == 'schema': valid.pop('status')
            else:
                if stage == 'individual': valid['revision_id']='foreign'
                else: valid['considered_revision_ids']=['foreign']
            return json.dumps(valid)
    decision,result=run([observation(1)],Fault())
    failed=decision['individual'][0] if stage=='individual' else decision['joint']
    assert failed['status']=='PROCESSING_FAILED'
    assert failed['reason_code'] not in {'NOT_ADMITTED','INSUFFICIENT_EVIDENCE'}
    assert result['skill_outcomes'][0]['outcome']==('no_result' if stage=='individual' else 'result_without_score')


def test_duplicate_same_as_is_not_new_observation(material_resolver):
    with pytest.raises(ValueError,match='AMBIGUOUS_REVISION'):
        run([observation(1),{**observation(1),'revision_id':'r2'}],RecordedAdmissionGateway())


def test_foreign_reference_and_missing_context_deny_admission(material_resolver,monkeypatch):
    class Bad(RecordedAdmissionGateway):
        def chat(self,*a,**kw):
            value=json.loads(super().chat(*a,**kw));value['normative_basis']['refs'][0]['id']='foreign'
            return json.dumps(value)
    d,_=run([observation(1)],Bad())
    assert d['individual'][0]['status']=='PROCESSING_FAILED'
    monkeypatch.setattr(admission,'resolve',lambda *a,**k:(_ for _ in ()).throw(ValueError('M6_ADMISSION_MATERIAL_SCOPE')))
    gateway=RecordedAdmissionGateway();d,_=run([observation(1)],gateway)
    assert d['individual'][0]['status']=='MATERIAL_INVALID' and not gateway.calls


def test_package_checksum_and_immutable_v1(tmp_path):
    from Api.m6_admission_package import PACKAGE
    for name in ('manifest.json','prompt.md'):
        (tmp_path/name).write_bytes((PACKAGE/name).read_bytes())
    (tmp_path/'prompt.md').write_text('tampered')
    with pytest.raises(ValueError,match='CHECKSUM'):
        load_mechanism(admission.VERSION,tmp_path)
    assert load_mechanism(admission.VERSION)['manifest']['status']=='draft'


def test_unresolved_ia_does_not_silently_shrink_joint_population(material_resolver):
    d,result=run([observation(1),observation(2,'L3')],
        RecordedAdmissionGateway(individual={'r2':'INSUFFICIENT_MATERIAL'}))
    assert d['interpretable_revision_ids']==['r1']
    assert d['joint']['status']=='INPUT_NOT_READY'
    assert not d['included_revision_ids']
    assert result['skill_outcomes'][0]['outcome']=='result_without_score'
