"""One approved existing runner invocation. Exclusive launch guard; no retries."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DEPLOY = Path('/home/vadim_bogachev/projects/Agent4K-Test')
DIRECTORY = Path('/home/vadim_bogachev/evidence/path-pilot-1.2-run-qxzr56r9')
SHA = 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
DIGEST = '09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b'


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def main():
    require(sys.argv[1:] == ['--one-authorized-run'], 'EXPLICIT_ONE_RUN_REQUIRED')
    prepared = json.loads((DIRECTORY / 'prepared.json').read_bytes())
    require(prepared['result'] == 'READY_FOR_ONE_AUTHORIZED_PAID_PATH', 'PREPARATION_REQUIRED')
    checkout = Path(prepared['checkout'])
    require(checkout.parent == Path('/home/vadim_bogachev/worktrees') and checkout.name.startswith('path-pilot-1.2-'), 'WRONG_EXECUTION_CHECKOUT')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == SHA, 'EXECUTION_SHA_DRIFT')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True).strip(), 'EXECUTION_CHECKOUT_DIRTY')
    require(not (checkout / '.env').exists(), 'WORKING_ENV_MUST_NOT_BE_COPIED')
    receipt = Path(prepared['selected']['path'])
    require(hashlib.sha256(receipt.read_bytes()).hexdigest() == DIGEST, 'RECEIPT_DRIFT')
    # Fresh read-only source reconciliation immediately before the paid launch.
    os.chdir(DEPLOY); sys.path.insert(0, str(DEPLOY))
    from Api.config import settings
    from tests.path_start_release_source import collect
    import psycopg
    from psycopg.rows import dict_row
    require(settings.db_name == 'agent4k_test', 'WRONG_WORKING_DATABASE')
    with psycopg.connect(host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
            user=settings.db_user, password=settings.db_password, connect_timeout=10, row_factory=dict_row,
            options='-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000') as c:
        c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        live = collect(c, program_version='1.2')
        require(c.execute('SELECT count(*) AS n FROM organization_assessment_program_connections WHERE program_definition_id=2').fetchone()['n'] == 0, 'TARGET_PROGRAM_CONNECTION_DRIFT')
        c.rollback()
    canonical = lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()
    require(canonical(live) == canonical(json.loads(receipt.read_bytes())), 'LIVE_SOURCE_DRIFT')
    argv = prepared['argv']
    require(argv[0] == str(DEPLOY / '.venv/bin/python') and argv[1] == 'scripts/assessment_first_case.py', 'EXISTING_RUNNER_REQUIRED')
    require(argv[-2:] == ['--directory', str(DIRECTORY / 'run')], 'WRONG_RUN_DIRECTORY')
    require(not any(a in argv for a in ('--preflight-only', '--check-bootstrap', '--summarize-only')), 'REAL_PATH_ONLY')
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR') if key in os.environ}
    env.update(PYTHONPATH=str(checkout), PYTHONDONTWRITEBYTECODE='1', DB_POOL_MIN_SIZE='0')
    started = time.monotonic()
    save(DIRECTORY / 'paid-launch.json', {'authorized_runner_invocations': 1, 'retry': False,
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'runtime_sha': SHA,
        'checkout': str(checkout), 'checkout_status': '', 'argv': argv,
        'prepared_file_sha256': hashlib.sha256((DIRECTORY / 'prepared.json').read_bytes()).hexdigest(),
        'receipt_sha256': DIGEST, 'fresh_live_source_equal': True, 'working_db_writes': False,
        'controller_pid': os.getpid()})
    fd = os.open(DIRECTORY / 'controller-output.private.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as log:
        child = subprocess.Popen(argv, cwd=checkout, env=env, stdout=log, stderr=log, start_new_session=True)
        save(DIRECTORY / 'controller-process.json', {'runner_pid': child.pid, 'controller_pid': os.getpid(),
            'checkout': str(checkout), 'directory': str(DIRECTORY), 'state': 'RUNNING'})
        print(json.dumps({'state': 'RUNNING', 'runner_pid': child.pid, 'directory': str(DIRECTORY)}), flush=True)
        exit_code = child.wait()
    result = {'state': 'RUNNER_FINISHED', 'exit_code': exit_code, 'elapsed_seconds': round(time.monotonic()-started, 3),
        'authorized_runner_invocations': 1, 'retry': False, 'directory': str(DIRECTORY), 'runtime_sha': SHA,
        'raw_controller_output_not_exported': True}
    summary_path = DIRECTORY / 'run/runner-result.json'
    if summary_path.exists():
        summary = json.loads(summary_path.read_bytes())
        result['runner_result'] = summary['result']
        result['runs'] = [{'run_id': row['run']['run_id'], 'result': row['result'],
            'validation_errors': row['validation_errors'], 'provider_completed_requests': row['provider_completed_requests']}
            for row in summary['runs']]
    save(DIRECTORY / 'controller-result.json', result)
    print(json.dumps(result), flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
