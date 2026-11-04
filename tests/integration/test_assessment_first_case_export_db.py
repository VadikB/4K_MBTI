"""No LLM: diagnostic data must outlive its exact owned PostgreSQL database."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration


def test_incomplete_export_is_persisted_before_owned_database_cleanup(tmp_path):
    url = os.getenv('STAND_ADMIN_URL') or os.getenv('TEST_DATABASE_URL')
    assert url, 'Explicit localhost maintenance/test URL required for owned export regression'
    subprocess.run([sys.executable, 'tests/assessment_first_case_export_regression.py',
        '--directory', str(tmp_path / 'negative-export')],
        env={**os.environ, 'STAND_ADMIN_URL': url}, check=True, timeout=180)
