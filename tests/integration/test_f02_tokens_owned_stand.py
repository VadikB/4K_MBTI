"""F02 AC02 runs only in a fresh marker-owned PostgreSQL database."""
import pytest

from tests.integration.test_remarks_participation_owned_stand import run_owned_http_suite


pytestmark = pytest.mark.integration


def test_f02_tokens_worker_and_new_account(tmp_path):
    run_owned_http_suite(tmp_path, script='tests/f02_token_http_checks.py',
        evidence_directory_env='F02_TOKEN_EVIDENCE_DIRECTORY', evidence_file_env='F02_TOKEN_EVIDENCE')
