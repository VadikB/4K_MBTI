from copy import deepcopy
import pytest
from Api.m8_recommendations import generate, profile_projection
from Api.m8_results import _present_report
from Api.m5_case_runtime import checksum
from test_m8_recommendations import fixture


def generate_for(profile):
    data, resolved = fixture()
    resolved['results_checksum'] = checksum({k:v for k,v in data.items() if k != 'results_revision_id'})
    return generate(data, profile, resolved=resolved)


def test_task112_task_priority_and_auditable_role_boundaries():
    profile = {'content': {'organization_context': {'activity_description':'Обучение'},
        'role_profile': {'card': {'typical_tasks':['Согласовать план'],
            'approval_required':'Изменение бюджета согласовать', 'role_constraints':'Не менять бюджет самостоятельно'}},
        'user_context': {'regular_tasks':['Анализ запросов'], 'full_name':'PRIVATE', 'contacts':'PRIVATE'}}}
    result = generate_for(profile)
    assert result['input']['context_selection']['selected_path'] == 'user_context.regular_tasks'
    for item in result['recommendations']:
        assert 'Анализ запросов' in item['application_context']
        assert 'Не менять бюджет самостоятельно' in str(item['limitations'])
        assert 'Изменение бюджета согласовать' in str(item['limitations'])
    assert 'PRIVATE' not in str(result)


@pytest.mark.parametrize('section,fields,path', [
    ('role_profile', {'card':{'typical_tasks':['Планирование']}}, 'role_profile.typical_tasks'),
    ('organization_context', {'activity_description':'Обучение'}, 'organization_context.activity_description'),
    ('user_context', {'position_or_status':'Эксперт'}, 'user_context.position_or_status'),
])
def test_task112_partial_context(section, fields, path):
    result = generate_for({'content':{section:fields}})
    assert result['input']['context_selection']['selected_path'] == path
    assert result['input']['context_selection']['status'] == 'available'


def test_task112_empty_and_invalid_are_different():
    empty = generate_for({'content':{'user_context':{'full_name':'PRIVATE'}}})
    assert empty['input']['context_selection']['status'] == 'missing'
    assert 'PRIVATE' not in str(empty)
    with pytest.raises(ValueError, match='PROFILE'):
        profile_projection({'content':['invalid']})


def test_task112_preserves_verified_11_report_presentation():
    saved = {'recommendations':[{'goal':'Проверенный текст'}],
             'recommendation_generation':{'contract_version':'m8-recommendations/1.1.0'}}
    original = deepcopy(saved)
    assert _present_report(saved) == original
    assert saved == original


@pytest.mark.parametrize('profile', [
    {'schema_version':2}, {'status':'blocked'},
    {'content':{'role_profile':{'card':{'role_constraints':{'email':'PRIVATE'}}}}},
    {'content':{'user_context':{'regular_tasks':[{'full_name':'PRIVATE'}]}}},
])
def test_task112_invalid_projection_fails_without_exposing_values(profile):
    with pytest.raises(ValueError, match='^M8_PROFILE_INVALID$'):
        profile_projection(profile)


def test_task112_context_does_not_change_basis_or_types():
    empty = generate_for(None)
    rich = generate_for({'content':{'user_context':{'regular_tasks':['Планирование']}}})
    assert [(r['type'],r['basis_refs']) for r in empty['recommendations']] == [
        (r['type'],r['basis_refs']) for r in rich['recommendations']]
