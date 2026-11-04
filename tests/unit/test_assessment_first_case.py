from scripts.assessment_first_case import preflight

def test_preflight_reports_named_blockers_without_secret_values(monkeypatch):
    monkeypatch.delenv('STAND_ADMIN_URL',raising=False);monkeypatch.setenv('DEEPSEEK_API_KEYS','must-not-leak');monkeypatch.delenv('DEEPSEEK_MODEL',raising=False)
    result=preflight(0)
    assert result['status']=='BLOCKED'
    assert {item['code'] for item in result['checks']} >= {'isolated_database_admin','real_provider','browser'}
    assert 'must-not-leak' not in repr(result)


def test_reproduce_imported_source_and_only_two_status_changes():
    import copy
    import json
    from Api.assessment_case_contracts import validate_case_version
    from Api.m5_case_runtime import checksum
    from tests.assessment_first_case_evidence import FUNCTIONAL, changed_paths

    package = json.loads((FUNCTIONAL / 'case-package.json').read_text())
    source = next(case for case in package['cases'] if case['case_id'] == 'CASE.SPEC.02')
    fixture = copy.deepcopy(source)
    fixture['status'] = 'FROZEN'
    assert checksum(fixture) == '663bfc6c7452761ee951b92f7ebf45e77be2e06edfbacbf2dc8b58adbe45d231'
    fixture['author_case']['Status'] = 'FROZEN'
    imported = validate_case_version(fixture).model_dump(exclude_unset=True)
    assert checksum(imported) == '179fa0f8192862bee6af3190c8560f9c5ed133cc2fe07d6f5b6a98e6e3c9b729'
    assert {change['path'] for change in changed_paths(source, imported)} == {'/status', '/author_case/Status'}


def test_repair_is_counted_once_and_secrets_not_exported():
    from tests.assessment_first_case_evidence import provider_calls, functional_receipt
    operation = {'operation_id': 'synthetic:repair', 'kind': 'generation_repair',
        'input_checksum': 'synthetic',
        'sent': {'provider': 'deepseek', 'messages': ['must-not-export'], 'api_key': 'must-not-export'},
        'provider': {'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12}}}
    trace = {'generation_operation': operation,
        'repair': {'repair_generation_operation': operation},
        'tester': {'aggregation': {'status': 'PASS'}}, 'admitted_for_participant': True}
    calls = provider_calls(trace)
    assert len(calls) == 1
    assert 'must-not-export' not in repr(calls)
    assert functional_receipt(trace)['usage']['total_tokens'] == 12


def test_duplicate_operation_with_different_usage_is_rejected():
    import pytest
    from tests.assessment_first_case_evidence import provider_calls
    with pytest.raises(ValueError, match='OPERATION_ID_CONTENT_CONFLICT'):
        provider_calls([
            {'operation_id': 'same', 'sent': {}, 'provider': {'usage': {'total_tokens': 1}}},
            {'operation_id': 'same', 'sent': {}, 'provider': {'usage': {'total_tokens': 2}}},
        ])
