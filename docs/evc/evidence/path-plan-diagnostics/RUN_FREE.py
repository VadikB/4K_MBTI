"""Reproduce owned SQL/export/cleanup diagnostics, no provider and no working DB.

Requires STAND_ADMIN_URL via a protected process environment. Does not load .env.
The existing stand creates and destroys only its exact owned test database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def run(directory):
    from psycopg.conninfo import make_conninfo
    from scripts.test_stand import owned

    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    state_path = directory / 'state.json'
    # Deliberately exclude all provider keys and developer DB configuration.
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR', 'LANG') if key in os.environ}
    env.update(STAND_ADMIN_URL=os.environ['STAND_ADMIN_URL'], PYTHONPATH=str(ROOT), DB_POOL_MIN_SIZE='0')

    def cli(action):
        subprocess.run([sys.executable, str(ROOT / 'scripts/test_stand.py'), action,
                        '--state', str(state_path), '--gateway', '0', '--provider', 'disabled'],
                       cwd=ROOT, env=env, check=True, timeout=60)

    cli('create')
    state = json.loads(state_path.read_text())
    identity = {'run_id': state['run_id'], 'database': state['database'],
                'scope': 'synthetic_plan_export_regression', 'llm_calls': 0, 'provider_mode': 'disabled',
                'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    (directory / 'run.json').write_text(json.dumps(identity, indent=2) + '\n')
    try:
        with owned(state):
            pass
        env['TEST_DATABASE_URL'] = make_conninfo(**{**state['connection'], 'dbname': state['database']})
        command = [sys.executable, '-m', 'pytest', '--run-integration', '-m', 'integration and not llm',
                   '-q', '--basetemp', str(directory / 'pytest'),
                   'tests/integration/test_m7_cycle_planner_db.py',
                   'tests/integration/test_m7_parameter_resolution_db.py',
                   'tests/integration/test_m10_product_path_db.py::test_prepare_does_not_start_time_and_explicit_start_presents_same_situation',
                   'tests/integration/test_assessment_first_case_export_db.py']
        with (directory / 'pytest.log').open('w') as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=300)
        assert result.returncode == 0, 'FREE_SQL_REGRESSIONS_FAILED: inspect private pytest.log'
        files = list((directory / 'pytest').rglob('failure-receipt.json'))
        assert len(files) == 1, 'ONE_PLAN_EXPORT_REQUIRED'
        receipt_bytes = files[0].read_bytes()
        receipt = json.loads(receipt_bytes)
        assert receipt['status'] == 'LIMITED' and receipt['revision_no'] == 2
        assert receipt['content_checksum_matches'] is True
        assert receipt['diagnostics']['uncovered_target_ids']
        preserved = directory / 'plan-receipt.json'
        shutil.copyfile(files[0], preserved)
        preserved.chmod(0o600)
        digest = hashlib.sha256(receipt_bytes).hexdigest()
        with owned(state) as connection:
            assert connection.execute('SELECT 1 FROM pg_database WHERE datname=%s',
                                      (state['database'],)).fetchone()
        proof = {'receipt_sha256': digest, 'phase': 'DURABLE_RECEIPT_READ_WHILE_OWNED_DB_EXISTS',
                 'plan_status': receipt['status'], 'revision_no': receipt['revision_no'], 'llm_calls': 0}
        (directory / 'export-before-cleanup.json').write_text(json.dumps(proof, indent=2) + '\n')
    except BaseException:
        (directory / 'cleanup-deferred.json').write_text(json.dumps({
            'reason': 'FREE_EXPORT_NOT_VERIFIED', 'owned_database_preserved': True}) + '\n')
        raise
    cli('destroy')
    cleanup = json.loads((directory / 'cleanup.json').read_text())
    assert cleanup['owner_verified'] and cleanup['database_absent'] and cleanup['state_absent']
    assert preserved.read_bytes() == receipt_bytes
    result = {**identity, 'result': 'PASS_FREE_DIAGNOSTICS_NOT_PATH', 'pytest_exit_code': 0,
              'receipt_sha256': digest, 'receipt_unchanged_after_cleanup': True,
              'cleanup_verified': True, 'force': False}
    (directory / 'regression-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    run(parser.parse_args().directory.resolve())
