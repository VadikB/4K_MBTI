from copy import deepcopy
import pytest
from Api.m5_case_runtime import checksum
from Api.m8_recommendations import generate, profile_projection, load_package
from Api.m8_results import _present_report


def fixture(outcome='partial_score'):
    action=load_package()['templates']['supported_actions'][0]['confirmed_action']
    target={'indicator_id':'K1.I01','m2_version':'v1.1','status':'ASSESSED','outcome':'L1',
        'rationale':'Участник назвал прямо заявленные цели сторон, но не проверил предположения.',
        'descriptor_basis':action,'opportunity':'PRESENT','opportunity_basis':'Материал предоставлен и обсуждён.',
        'uncertainty':None,'contradictions':[], 'refs':[{'kind':'evidence','id':'e1','meaning':action}],
        'confidence':{'confirmed_features':[action],'limitations':['Проверка гипотез не наблюдалась.']}}
    obs={**target,'revision_id':'ia-1','assessment_revision_id':'a1','evidence_revision_id':'evidence-1','assessment_situation_id':'as1'}
    payload={'cycle_id':'c1','results_version':'m8-results/1.0.0','profile_ref':{'id':'p1'},
        'assessed_skill_profile':[{'skill_id':'K1.1','outcome':outcome,'score':{'value':2.4},
            'comparison':{'status':'NOT_COMPARABLE','target_level':'L2'},
            'components':[{'component_id':'K1.C1','required_indicator_ids':['K1.I01','K1.I02'],
                           'included_indicator_ids':['K1.I01'],'missing_indicator_ids':['K1.I02']}]}],
        'observations':[obs], 'admissions':[{'indicator_id':'K1.I01','interpretation_admissible':True,
                                          'numeric_admissible':False,'interpretable_revision_ids':['ia-1']}]}
    if outcome in ('no_result','result_without_score'):
        payload['assessed_skill_profile'][0].pop('score')
    projection={'revision_id':'ia-1','target':target,'criterion':{'id':'K1.I01','skill_id':'K1.1','component_id':'K1.C1',
        'name':'Цели участников','function':'Выявлять цели участников','product':'Карта целей','levels':{'L1':action}},
        'bundle':{'limitations':[],'contradictions':[]},'traces':[{'ref':target['refs'][0],
        'fragments':[{'id':'f1','turn_id':'t1','quote':'Хочет согласовать срок'}]}],
        'material_ref':{'boundary_sequence':3},'ia_checksum':'i'*64,'evidence_checksum':'e'*64}
    resolved={'cycle_id':'c1','results_revision_id':'r1','projections':[projection]}
    return {**payload,'results_revision_id':'r1'},resolved


def run(data, resolved):
    resolved=deepcopy(resolved)
    resolved['results_checksum']=checksum({k:v for k,v in data.items() if k!='results_revision_id'})
    return generate(data, {'content':{'role_profile':{'card':{'typical_tasks':['согласование срока']}},
                                     'user_context':{'email':'private@example.invalid'}}}, resolved=resolved)


@pytest.mark.parametrize('outcome',['full_score','partial_score','result_without_score'])
def test_r11_04_06_07_supported_grounded_types(outcome):
    data,resolved=fixture(outcome)
    result=run(data,resolved)
    assert {x['type'] for x in result['recommendations']}=={'Development','Consolidation / Maintenance','Application / Transfer'}
    assert all(x['basis_refs'][0]['results_revision_id']=='r1' for x in result['recommendations'])
    assert all('K1.I02' not in str(x) and x['gap_ref'] is None for x in result['recommendations'])
    assert 'private@example.invalid' not in str(result)
    assert data['assessed_skill_profile'][0]['comparison']['status']=='NOT_COMPARABLE'


def test_r11_01_ie_before_valid_and_order_invariance():
    data,resolved=fixture()
    ie=deepcopy(data['observations'][0]);ie.update(indicator_id='K1.I02',revision_id='ie',outcome='INSUFFICIENT_EVIDENCE',refs=[])
    ie['confidence']={'confirmed_features':[]}
    data['observations'].insert(0,ie)
    result=run(data,resolved)
    assert result['recommendations'] and all(x['basis_refs'][0]['ia_revision_id']=='ia-1' for x in result['recommendations'])
    data['observations'].reverse()
    assert run(data,resolved)['recommendations']==result['recommendations']


def test_r11_02_untrusted_declaration_is_not_basis():
    data,_=fixture()
    assert generate(data,None)['recommendations']==[]


@pytest.mark.parametrize('change',['ie','empty_refs','contradiction','unknown_admission','denied','uncertainty'])
def test_r11_02_05_invalid_basis_is_normal_absence(change):
    data,resolved=fixture();target=resolved['projections'][0]['target']
    if change=='ie':target['outcome']='INSUFFICIENT_EVIDENCE'
    if change=='empty_refs':target['refs']=[]
    if change=='contradiction':target['contradictions']=['Существенное противоречие']
    if change=='unknown_admission':data['admissions']=[]
    if change=='denied':data['admissions'][0]['interpretation_admissible']=False
    if change=='uncertainty':target['uncertainty']={'impact':'Неясно'}
    result=run(data,resolved)
    assert result['recommendations']==[] and result['status']=='unavailable' and result['failure_reason'] is None
    assert result['notices'] and result['diagnostics']


def test_r11_06_justified_l0_gets_practice_not_success_claim():
    data,resolved=fixture();target=resolved['projections'][0]['target']
    target.update(outcome='L0',descriptor_basis='Не различает цели',rationale='При наличии возможности цели сторон смешаны.')
    target['confidence']['confirmed_features']=[]
    result=run(data,resolved)
    assert [x['type'] for x in result['recommendations']]==['Development']
    assert 'цели сторон смешаны' in result['recommendations'][0]['goal']
    assert 'Карта целей' in result['recommendations'][0]['practice']


def test_r11_04_no_result_is_limitation():
    data,resolved=fixture('no_result');result=run(data,resolved)
    assert result['recommendations']==[] and result['notices'][0]['kind']=='INSUFFICIENT_BASIS'


def test_r11_03_foreign_results_and_ambiguous_projection_rejected():
    data,resolved=fixture();resolved['cycle_id']='other'
    with pytest.raises(ValueError,match='MISMATCH'):run(data,resolved)
    data,resolved=fixture();resolved['projections']*=2
    with pytest.raises(ValueError,match='AMBIGUOUS'):run(data,resolved)


def test_r11_09_legacy_presentation_preserves_history():
    saved={'recommendations':[{'goal':'выдуманное проявление'}],
           'recommendation_generation':{'contract_version':'m8-recommendations/1.0.0','recommendations':[{'goal':'старый текст'}]},'skills':[1]}
    original=deepcopy(saved);view=_present_report(saved)
    assert saved==original and view['skills']==[1] and view['recommendations']==[]
    assert view['recommendation_notices'][0]['kind']=='LEGACY_BASIS_UNVERIFIED'
    assert 'старый текст' not in str(view)


def test_r11_determinism_and_package_version():
    data,resolved=fixture()
    assert run(data,resolved)==run(data,resolved)
    assert run(data,resolved)['contract_version']=='m8-recommendations/1.1.0'
    assert profile_projection({'user_context':{'email':'secret','regular_tasks':['задача']}})=={'user_context':{'regular_tasks':['задача']}}


def test_canonical_m4_builder_projection_and_recommendation_context():
    from Api.assessment_contexts import build_personalized_profile
    snapshot = build_personalized_profile(organization_id=1,
        organization_context={'name':'PRIVATE NAME','organization_type':'компания','industry':'образование',
            'activity_description':'Разработка программ','case_reality_level':'обобщённый','organization_name_usage_rules':'не использовать'},
        organization_context_ref={'version_id':1},
        role_profile={'methodology_version':'1.1','card':{'mission':'Анализировать запросы', 'typical_tasks':['Согласовать план'],
                      'contacts':'PRIVATE CONTACT'}}, role_profile_ref={'version_id':2},
        user_identity={'full_name':'PRIVATE PERSON','contacts':'PRIVATE EMAIL'},
        user_context={'position_or_status':'Эксперт','regular_tasks':['Анализ'], 'email':'PRIVATE EMAIL'},
        user_context_ref={'version_id':3})
    original=deepcopy(snapshot)
    projected=profile_projection(snapshot)
    assert projected == {'organization_context':{'activity_description':'Разработка программ'},
        'role_profile':{'mission':'Анализировать запросы','typical_tasks':['Согласовать план']},
        'user_context':{'position_or_status':'Эксперт','regular_tasks':['Анализ']}}
    data,resolved=fixture()
    resolved['results_checksum']=checksum({k:v for k,v in data.items() if k!='results_revision_id'})
    result=generate(data,snapshot,resolved=resolved)
    assert result['recommendations']
    assert 'Разработка программ' in str(result['recommendations'])
    assert 'PRIVATE' not in str(result)
    assert snapshot == original
