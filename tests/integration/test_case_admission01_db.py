"""Actual PostgreSQL/HTTP readback of rejected Next, with existing synthetic gateway."""
import pytest
from tests.integration.test_m10_product_path_db import product_db
from tests.integration.test_m10_product_path_db import (
    test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases as functional_path,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('outcome', ['FAIL', 'INCOMPLETE', 'JSON_EXHAUSTED'])
def test_admission01_next_failure_preserves_closed_work_and_safe_http_readback(
        product_db, monkeypatch, tmp_path, outcome):
    functional_path(product_db, monkeypatch, tmp_path, True, False, None, None, next_failure=outcome)



@pytest.mark.parametrize('case', ['TECHNICAL_RETRY', 'CALENDAR_EXPIRY'])
def test_asux04_prepared_next_keeps_exact_route_and_time(product_db, monkeypatch, tmp_path, case):
    functional_path(product_db, monkeypatch, tmp_path, True, False, None, None,
                    next_failure='TECHNICAL' if case == 'TECHNICAL_RETRY' else None,
                    next_expiry=case == 'CALENDAR_EXPIRY')


def test_passport_bank_standard_first_start_and_next(product_db, monkeypatch, tmp_path):
    functional_path(product_db, monkeypatch, tmp_path, False, False, "after_provider", None,
                    passport_bank=True, refresh_profile_before_recovery=True)
