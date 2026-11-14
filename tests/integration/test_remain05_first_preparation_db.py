"""Reuse the actual controlled queue/gateway proof, stopping at the first AS.

Upstream source/admission fixtures remain synthetic; PostgreSQL persistence,
functional tester/challenger, candidate binding, owned HTTP and queue are real.
No assessment answer, Next, Report or external provider is executed.
"""
import pytest

from tests.integration.test_m10_product_path_db import product_db  # noqa: F401
from tests.integration.test_m10_product_path_db import (
    test_functional_catalog_builds_a_separate_product_cycle_without_legacy_cases as _functional,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(("close_during_provider", "crash_phase", "tester_outcome"), [
    (False, None, None),
    (True, None, None),
    (False, "before_provider", None),
    (False, "after_provider", None),
    (False, "after_attach", None),
    (False, None, "INCOMPLETE"),
    (False, None, "FAIL"),
])
def test_first_preparation_persistence_and_admission(
    product_db, monkeypatch, tmp_path, close_during_provider, crash_phase, tester_outcome,
):
    _functional(product_db, monkeypatch, tmp_path, explicit_profile=True,
                close_during_provider=close_during_provider, crash_phase=crash_phase,
                tester_outcome=tester_outcome, first_case_only=True)
