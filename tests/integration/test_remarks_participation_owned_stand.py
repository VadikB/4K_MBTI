"""F01/F02: real localhost HTTP and a new marker-owned PostgreSQL database."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


pytestmark = pytest.mark.integration


def test_remarks_participation_on_owned_postgresql(tmp_path):
    run_owned_http_suite(tmp_path, script='tests/remarks_participation_http_checks.py',
        evidence_directory_env='REMARKS_PARTICIPATION_EVIDENCE_DIRECTORY',
        evidence_file_env='REMARKS_PARTICIPATION_EVIDENCE')


def run_owned_http_suite(tmp_path, *, script, evidence_directory_env, evidence_file_env):
    admin_url = os.getenv('STAND_ADMIN_URL', '')
    if not admin_url:
        pytest.skip('STAND_ADMIN_URL required for a new marker-owned database')
    from scripts.test_stand import environment

    state_path = tmp_path / 'state.json'
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
    env.update(STAND_ADMIN_URL=admin_url, PYTHON_DOTENV_DISABLED='1')
    evidence = Path(os.getenv(evidence_directory_env, str(tmp_path / 'export')))
    evidence.mkdir(parents=True, exist_ok=True)

    def cli(action):
        checked = subprocess.run([sys.executable, 'scripts/test_stand.py', action,
            '--state', str(state_path), '--gateway', '1'], env=env,
            capture_output=True, text=True, timeout=180)
        assert checked.returncode == 0, checked.stdout + checked.stderr

    cli('create')
    try:
        cli('bootstrap')
        cli('seed')
        isolated = environment(json.loads(state_path.read_text()))
        isolated.update(PYTHON_DOTENV_DISABLED='1', AUDIT_LOGS_TO_DB='false',
            **{evidence_file_env: str(tmp_path / 'checks.json')})
        checked = subprocess.run([sys.executable, script],
            env=isolated, capture_output=True, text=True, timeout=180)
        if (tmp_path / 'checks.json').exists():
            (evidence / 'checks.json').write_bytes((tmp_path / 'checks.json').read_bytes())
        (evidence / 'http-pg.txt').write_text(checked.stdout + checked.stderr)
        assert checked.returncode == 0, checked.stdout + checked.stderr
    finally:
        cli('destroy')
        (evidence / 'cleanup.json').write_bytes((tmp_path / 'cleanup.json').read_bytes())
