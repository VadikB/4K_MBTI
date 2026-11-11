"""F06: actual uploader, confirmer, revision lineage and privacy through HTTP/PG."""
import pytest

from tests.integration.test_remarks_participation_owned_stand import run_owned_http_suite


pytestmark = pytest.mark.integration


def test_remarks_questionnaire_actor_on_owned_postgresql(tmp_path):
    run_owned_http_suite(tmp_path, script='tests/remarks_questionnaire_actor_http_checks.py',
        evidence_directory_env='REMARKS_QUESTIONNAIRE_ACTOR_EVIDENCE_DIRECTORY',
        evidence_file_env='REMARKS_QUESTIONNAIRE_ACTOR_EVIDENCE')
