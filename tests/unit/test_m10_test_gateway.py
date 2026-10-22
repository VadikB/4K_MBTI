import pytest

from Api.m10_test_gateway import _acceptance_output, acceptance_contracts


def m7_input(case_id, indicator_ids):
    return {
        'case_ref': {'id': case_id, 'version': 'synthetic'},
        'indicator_ids': indicator_ids,
        'uncertainties': [{'indicator_id': item} for item in indicator_ids],
    }


def test_m7_question_is_selected_by_case_ref_not_indicator_heuristic():
    fixture = {'question': 'legacy value is not used', 'character_question': 'legacy value is not used'}
    default = _acceptance_output(m7_input('CASE-TDISC-01', ['K2.I10']), fixture)
    character = _acceptance_output(m7_input('CASE-BROWSER-CHARACTER-01', ['K2.I10']), fixture)

    assert default['text'] == 'Что вы имели в виду под разными основаниями готовности в своём ответе?'
    assert character['text'] == 'Что вы имели в виду под проверкой одного запроса в своём ответе?'
    assert default['indicator_ids'] == character['indicator_ids'] == ['K2.I10']


def test_character_contract_reports_missing_required_indicator_immediately():
    with pytest.raises(ValueError, match='BROWSER_FIXTURE_INDICATOR_MISMATCH.*K2.I10'):
        _acceptance_output(m7_input('CASE-BROWSER-CHARACTER-01', ['K1.I13']), {})


def test_unknown_case_does_not_fall_back_to_another_fixture():
    with pytest.raises(ValueError, match='UNKNOWN_BROWSER_FIXTURE_CASE:CASE-UNKNOWN'):
        _acceptance_output(m7_input('CASE-UNKNOWN', ['K2.I10']), {})


def test_each_browser_contract_declares_input_actions_question_and_m7_status():
    contracts = acceptance_contracts()
    assert {item['id'] for item in contracts} == {
        'browser-character-dialogue-v1', 'browser-default-dialogue-v1'}
    for contract in contracts:
        assert contract['accepted_inputs']
        assert isinstance(contract['actions'], dict)
        assert contract['m7']['question'].endswith('?')
        assert contract['m7']['expected_status'] == 'ASK'
