"""Free preflight/clean Git checkout before one approved PATH; no paid launch."""
from argparse import Namespace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4

DEPLOY = Path('/home/vadim_bogachev/projects/Agent4K-Test')
SHA = 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
RECEIPT = Path('/home/vadim_bogachev/evidence/pilot-program-1.2-wryr3q10/published-release-source.json')
DIGEST = '09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b'


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    require(path.read_bytes() == data, 'EVIDENCE_READBACK_FAILED')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def main():
    require(sys.argv[1:] == ['--free-preparation-only'], 'EXPLICIT_FREE_PREPARATION_REQUIRED')
    os.chdir(DEPLOY); sys.path.insert(0, str(DEPLOY))
    directory = Path(tempfile.mkdtemp(prefix='path-pilot-1.2-run-', dir='/home/vadim_bogachev/evidence'))
    try:
        require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == SHA, 'DEPLOY_SHA_DRIFT')
        require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], text=True).strip(), 'DEPLOY_TRACKED_DIRTY')
        require(sha(RECEIPT.read_bytes()) == DIGEST, 'RECEIPT_BYTES_DRIFT')
        from tests.path_start_release_source import collect, load_release_receipt
        source, selected = load_release_receipt(path=RECEIPT, sha256=DIGEST, version='1.2')
        from Api.config import settings
        import psycopg
        from psycopg.rows import dict_row
        require(settings.db_name == 'agent4k_test', 'WRONG_WORKING_DATABASE')
        with psycopg.connect(host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
                user=settings.db_user, password=settings.db_password, connect_timeout=10, row_factory=dict_row,
                options='-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000') as c:
            c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            live = collect(c, program_version='1.2')
            connections = c.execute('SELECT count(*) AS n FROM organization_assessment_program_connections WHERE program_definition_id=%s', (2,)).fetchone()['n']
            publisher = c.execute('SELECT published_by_user_id FROM assessment_program_definitions WHERE id=2').fetchone()['published_by_user_id']
            readonly = c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']
            c.rollback()
        require(canonical(live) == canonical(source), 'LIVE_PUBLISHED_SOURCE_DRIFT')
        require(readonly == 'on' and connections == 0 and publisher == 4, 'PUBLISHED_SCOPE_DRIFT')
        schema_dir = DEPLOY / 'docs/evc/evidence/path-pilot-schema-readback'
        reader = module('path_schema_reader', schema_dir / 'READ_SCHEMA.py')
        compare = module('path_schema_compare', schema_dir / 'COMPARE.py')
        expected = json.loads((schema_dir / 'expected-schema.json').read_bytes())
        actual = reader.collect(Namespace(env_file=DEPLOY / '.env', stand_state=None, checkout=DEPLOY))
        comparison = compare.compare(expected, actual)
        require(comparison['result'] == 'EXACT_SCOPED_SCHEMA_MATCH', 'WORKING_SCHEMA_DRIFT')
        save(directory / 'live-preflight.json', {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
            'result': 'LIVE_READ_ONLY_PREFLIGHT_PASS', 'runtime_sha': SHA, 'program': selected['program'],
            'published_source_canonical_sha256': sha(canonical(live)), 'receipt_canonical_sha256': sha(canonical(source)),
            'receipt_bytes_sha256': DIGEST, 'same_source': True, 'publisher_user_id': publisher,
            'target_program_connections': connections, 'transaction_read_only': True, 'rollback': True,
            'schema_comparison': comparison, 'working_db_writes': False, 'provider_calls': 0})
        worktrees = Path('/home/vadim_bogachev/worktrees'); worktrees.mkdir(mode=0o700, exist_ok=True)
        checkout = worktrees / ('path-pilot-1.2-' + uuid4().hex)
        subprocess.run(['git', 'worktree', 'add', '--detach', str(checkout), SHA], cwd=DEPLOY, capture_output=True, check=True)
        # Real ignored directory; individual dependency links do not dirty Git.
        node_modules = checkout / 'node_modules'; node_modules.mkdir()
        for dependency in (DEPLOY / 'node_modules').iterdir():
            (node_modules / dependency.name).symlink_to(dependency, target_is_directory=dependency.is_dir())
        require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True).strip(), 'EXECUTION_CHECKOUT_NOT_CLEAN')
        require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == SHA, 'EXECUTION_SHA_DRIFT')
        env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR') if key in os.environ}
        env.update(PYTHONPATH=str(checkout), PYTHONDONTWRITEBYTECODE='1', DB_POOL_MIN_SIZE='0')
        argv = [str(DEPLOY / '.venv/bin/python'), 'scripts/assessment_first_case.py',
            '--env-file', str(DEPLOY / '.env'), '--python', str(DEPLOY / '.venv/bin/python'),
            '--program-source', 'published-pilot', '--program-receipt', str(RECEIPT),
            '--program-receipt-sha256', DIGEST, '--program-version', '1.2',
            '--db-admin-port', '55432', '--port', '18861', '--directory', str(directory / 'run')]
        free = list(argv); free[free.index('--directory') + 1] = str(directory / 'machine-preflight'); free.append('--preflight-only')
        process = subprocess.run(free, cwd=checkout, env=env, capture_output=True, text=True, timeout=90)
        require(process.returncode == 0, 'MACHINE_PREFLIGHT_FAILED')
        machine = json.loads((directory / 'machine-preflight/preflight.json').read_bytes())
        require(machine['status'] == 'READY', 'MACHINE_NOT_READY')
        require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True).strip(), 'CHECKOUT_DIRTY_AFTER_PREFLIGHT')
        result = {'result': 'READY_FOR_ONE_AUTHORIZED_PAID_PATH', 'prepared_at_utc': datetime.now(timezone.utc).isoformat(),
            'checkout': str(checkout), 'runtime_sha': SHA, 'checkout_status': '', 'directory': str(directory),
            'argv': argv, 'environment_overrides': {'PYTHONPATH': str(checkout), 'PYTHONDONTWRITEBYTECODE': '1', 'DB_POOL_MIN_SIZE': '0'},
            'dependency_mode': 'Ignored real node_modules directory with links to installed read-only dependencies; no .env copied',
            'selected': selected, 'machine_preflight': 'READY', 'working_db_writes': False,
            'provider_calls': 0, 'paid_runner_invocations': 0, 'playwright_retries': 0}
        save(directory / 'prepared.json', result)
        print(json.dumps(result)); return 0
    except Exception as exc:
        result = {'result': 'PREPARATION_STOPPED_NO_PAID_LAUNCH', 'directory': str(directory),
            'exception_type': type(exc).__name__, 'reason': str(exc) if isinstance(exc, RuntimeError) else 'DETAILS_REDACTED',
            'paid_runner_invocations': 0}
        save(directory / 'preparation-failure.json', result); print(json.dumps(result)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
