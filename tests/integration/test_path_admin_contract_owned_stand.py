"""AC06/07/09/10: actual routes, sessions, resolvers and disposable PostgreSQL."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.integration


def test_path_admin_contract_on_owned_postgresql(tmp_path):
    # No developer .env/DB fallback. test_stand validates localhost and ownership.
    admin_url = os.getenv('STAND_ADMIN_URL', '')
    if not admin_url:
        pytest.skip('STAND_ADMIN_URL required for a new marker-owned database')
    from scripts.test_stand import environment
    state = tmp_path / 'state.json'
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
    env.update(STAND_ADMIN_URL=admin_url, PYTHON_DOTENV_DISABLED='1')

    def cli(action):
        result = subprocess.run([sys.executable, 'scripts/test_stand.py', action,
            '--state', str(state)], env=env, capture_output=True, text=True, timeout=180)
        print(result.stdout)
        assert result.returncode == 0, result.stderr

    cli('create')
    try:
        cli('bootstrap')
        cli('seed')
        previous = os.environ.get('STAND_ADMIN_URL')
        os.environ['STAND_ADMIN_URL'] = admin_url
        try:
            isolated = environment(json.loads(state.read_text()))
        finally:
            if previous is None:
                os.environ.pop('STAND_ADMIN_URL', None)
            else:
                os.environ['STAND_ADMIN_URL'] = previous
        isolated.update(PYTHON_DOTENV_DISABLED='1', AUDIT_LOGS_TO_DB='false',
                        PATH_ADMIN_EVIDENCE=str(tmp_path / 'checks.json'))
        checked = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-ra',
            'tests/path_admin_contract_checks.py', '--run-integration'],
            env=isolated, capture_output=True, text=True, timeout=240)
        print(checked.stdout)
        print(checked.stderr)
        evidence = Path(os.getenv('PATH_ADMIN_EVIDENCE_DIRECTORY', str(tmp_path / 'export')))
        evidence.mkdir(parents=True, exist_ok=True)
        # Persist diagnostics even on test failure, BEFORE marker-guarded cleanup.
        (evidence / 'checks.json').write_bytes((tmp_path / 'checks.json').read_bytes())
        (evidence / 'pytest.txt').write_text(checked.stdout + checked.stderr)
        assert checked.returncode == 0, 'real HTTP/PostgreSQL contract checks failed'
    finally:
        cli('destroy')
        evidence = Path(os.getenv('PATH_ADMIN_EVIDENCE_DIRECTORY', str(tmp_path / 'export')))
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / 'cleanup.json').write_bytes((tmp_path / 'cleanup.json').read_bytes())
