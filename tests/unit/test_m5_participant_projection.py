"""Public projection regressions; not a synthetic success claim for AS admission."""
from copy import deepcopy
import json

import pytest

from Api.assessment_case_contracts import CaseVersionV3
from Api.m5_case_runtime import _materialize_v3_presentation, build_c34_envelope, checksum
from tests.m5_participant_projection_inputs import LEGACY_FIELDS, case_value, sample

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('case_id', [f'CASE.SPEC.{i:02d}' for i in range(1, 10)])
def test_functional_public_view_is_exact_as_intro_and_start_materials_not_author_passport(case_id):
    value = sample(case_id)
    case, snapshot = value['source_case'], value['snapshot']
    public = snapshot['participant_payload']
    expected = case['participant_presentation']
    assert public['introduction'] == expected['introduction']
    assert public['initial_materials'] == expected['initial_materials']
    assert public['source'] == case['author_as_source']
    assert not (set(LEGACY_FIELDS) & set(public)), 'AUTHOR_PASSPORT_LEAKED_TO_FUNCTIONAL_PARTICIPANT'
    assert public['case_id'] == case_id and public['case_version'] == case['version']
    assert snapshot['case_ref']['checksum'] == checksum(case)
    visible_ids = [item['material_id'] for item in public['initial_materials']]
    assert visible_ids == [i for i in case['author_assessment_situation']['Стартовые MaterialIDs'] if i != 'P00']
    assert 'определяются в AS' not in json.dumps(public, ensure_ascii=False)


def test_closed_passport_is_retained_without_leaking_into_public_view_or_mutating_source():
    case = case_value('CASE.SPEC.02')
    original = deepcopy(case)
    result = sample(case=case)
    assert case == original and result['source_case'] == original
    # The faulty fields still exist in the unchanged source package, not in public AS.
    assert "[{'" in case['participant_presentation']['participants_and_positions']
    assert "{'" in case['participant_presentation']['conditions_and_constraints']
    assert 'author_case' not in result['snapshot']['participant_payload']


def test_legacy_presentation_without_frozen_functional_profile_remains_byte_equivalent():
    value = sample(functional=False)
    expected = deepcopy(value['source_case']['participant_presentation'])
    expected.pop('substitution_targets')
    expected.update(case_id='CASE.SPEC.02', case_version=value['source_case']['version'], substitutions=[])
    assert value['snapshot']['participant_payload'] == expected


@pytest.mark.parametrize('profile', ['functional-personalization-indicator-v1', 'functional-personalization-indicator-v2'])
def test_only_the_frozen_recognized_profile_selects_functional_projection(profile):
    assert not set(LEGACY_FIELDS) & set(sample(schema_profile=profile)['snapshot']['participant_payload'])
    unknown = sample(schema_profile='unknown-future-profile')['snapshot']['participant_payload']
    assert set(LEGACY_FIELDS) <= set(unknown)


def test_functional_projection_does_not_turn_failed_admission_into_permission_to_execute():
    value = sample(policy={'allowed_case_statuses': ['FROZEN'], 'required_evidence_scopes': ['case_format']})
    assert value['snapshot']['admission']['admitted'] is False
    assert value['snapshot']['admission']['reasons'] == ['case_status:WORKING', 'missing_evidence:case_format']
    with pytest.raises(ValueError, match='AS_NOT_ADMITTED'):
        build_c34_envelope(value['snapshot'])


def test_functional_projection_does_not_introduce_undeclared_substitution_or_mutate_source():
    case = CaseVersionV3.model_validate(case_value('CASE.SPEC.02'))
    before = case.model_dump()
    ref = {'checksum': 'a' * 64}
    profile = {'organization_context': {'name': 'Синтетическая организация',
                                      'organization_name_usage_rules': 'можно использовать'}}
    substitution = {'slot': 'organization_name', 'value': 'Синтетическая организация',
                    'source_path': 'organization_context.name', 'source_checksum': ref['checksum']}
    # This functional source has no organization substitution slot; unlike Sales,
    # it must not acquire one simply because its public projection changed.
    with pytest.raises(ValueError, match='SUBSTITUTION_TARGET_NOT_ALLOWED:organization_name'):
        _materialize_v3_presentation(case, profile, ref, [substitution],
                                     source_schema_profile='functional-personalization-indicator-v2')
    assert case.model_dump() == before
