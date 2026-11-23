"""Actual PostgreSQL/HTTP readback of rejected Next, with existing synthetic gateway."""
import pytest
from Api.preparation_observation import reference
from scripts.preparation_diagnostics import lookup
from tests.integration.test_m10_product_path_db import product_db
from tests.integration.test_m10_product_path_db import (
    test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases as functional_path,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('outcome', ['FAIL', 'INCOMPLETE', 'JSON_EXHAUSTED'])
def test_admission01_next_failure_preserves_closed_work_and_safe_http_readback(
        product_db, monkeypatch, tmp_path, outcome):
    functional_path(product_db, monkeypatch, tmp_path, True, False, None, None, next_failure=outcome)
    with product_db() as connection:
        row = connection.execute("""SELECT operation_id FROM product_cycle_preparation_operations
            WHERE status='failed' AND request_json->>'kind'='next'""").fetchone()
        receipt = lookup(connection, reference('cycle', row['operation_id']))[-1]['functional_preparation']
    assert receipt['operation_id'] == row['operation_id']
    assert not receipt['admitted_for_participant']
    if outcome == 'FAIL':
        assert receipt['admission_status'] == 'FAIL'
        assert len(receipt['repair']['calls']) == 1
        assert receipt['recheck']['tester'] and receipt['recheck']['challenger']
        return
    assert receipt['admission_status'] == 'INCOMPLETE'
    batch = next(item for item in receipt['initial_reviews']['tester']
                 if 'common.authority' in item['required_check_ids'])
    error = next(error for error in batch['protocol_errors'] if error['check_id'] == 'common.authority')
    assert error['reviewer'] == 'tester' and error['batch_no'] == batch['batch_no']
    assert error['error_class'] == 'verification_protocol' and error['path'] == 'checks/common.authority'
    assert receipt['repair'] is None
    if outcome == 'JSON_EXHAUSTED':
        assert error['code'] == 'PROVIDER_JSON_INVALID_RETRY_EXHAUSTED'
        assert [item['attempt'] for item in batch['calls']] == [1, 2]
        assert batch['calls'][0]['input_checksum'] == batch['input_checksum']
        assert batch['calls'][1]['message_count'] == batch['calls'][0]['message_count'] + 1



@pytest.mark.parametrize('case', ['TECHNICAL_RETRY', 'CALENDAR_EXPIRY'])
def test_asux04_prepared_next_keeps_exact_route_and_time(product_db, monkeypatch, tmp_path, case):
    functional_path(product_db, monkeypatch, tmp_path, True, False, None, None,
                    next_failure='TECHNICAL' if case == 'TECHNICAL_RETRY' else None,
                    next_expiry=case == 'CALENDAR_EXPIRY')


def test_passport_bank_standard_first_start_and_next(product_db, monkeypatch, tmp_path):
    functional_path(product_db, monkeypatch, tmp_path, False, False, "after_provider", None,
                    passport_bank=True, refresh_profile_before_recovery=True)
    with product_db() as connection:
        operations = connection.execute("""SELECT operation_id FROM product_cycle_preparation_operations
            WHERE status='completed' ORDER BY created_at""").fetchall()
        receipts = [lookup(connection, reference('cycle', op['operation_id']))[-1] for op in operations]
    generated = [detail for detail in receipts if detail.get('functional_preparation')]
    assert [detail['kind'] for detail in generated] == ['assessment', 'next']
    for detail in generated:
        trace = detail['functional_preparation']
        assert trace['operation_id'] == detail['operation_id']
        assert trace['candidate_checksum'] and trace['admitted_for_participant']
        assert trace['package']['version'] == '3.0.0'
        assert trace['initial_reviews']['tester'] and trace['initial_reviews']['challenger']
        assert trace['generation']['calls'][0]['messages_utf8_bytes'] > 0
        assert detail['timing']['enqueue_to_worker_ms'] >= 0
        assert detail['timing']['ready_persistence_ms'] > 0
