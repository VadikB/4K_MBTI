"""Однократный запуск существующего --check-bootstrap через SSH stdin; не runtime."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path('/home/vadim_bogachev/projects/Agent4K-Test')
RUNTIME = 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
RECEIPT = Path('/home/vadim_bogachev/evidence/pilot-program-1.2-wryr3q10/published-release-source.json')
DIGEST = '09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b'


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    require(path.read_bytes() == data, 'EVIDENCE_WRITE_READBACK_FAILED')


def main():
    require(sys.argv[1:] == ['--free-bootstrap-only'], 'EXPLICIT_FREE_MODE_REQUIRED')
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == RUNTIME, 'RUNTIME_DRIFT')
    require(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], text=True).strip(), 'TRACKED_SOURCE_DIRTY')
    require(hashlib.sha256(RECEIPT.read_bytes()).hexdigest() == DIGEST, 'PUBLISHED_RECEIPT_BYTES_DRIFT')
    from tests.path_start_release_source import load_release_receipt
    _, reference = load_release_receipt(path=RECEIPT, sha256=DIGEST, version='1.2')
    require(reference['program']['id'] == 2, 'PUBLISHED_PROGRAM_ID_DRIFT')
    directory = Path(tempfile.mkdtemp(prefix='path-pilot-1.2-bootstrap-', dir='/home/vadim_bogachev/evidence'))
    argv = [str(ROOT / '.venv/bin/python'), 'scripts/assessment_first_case.py',
        '--env-file', str(ROOT / '.env'), '--python', str(ROOT / '.venv/bin/python'),
        '--program-source', 'published-pilot', '--program-receipt', str(RECEIPT),
        '--program-receipt-sha256', DIGEST, '--program-version', '1.2',
        '--db-admin-port', '55432', '--port', '18861', '--directory', str(directory), '--check-bootstrap']
    save(directory / 'launch-guard.json', {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
        'runtime_sha': RUNTIME, 'tracked_clean': True, 'selected': reference,
        'owner_scope': 'FREE_BOOTSTRAP_ONLY_NO_PAID_PATH', 'argv': argv,
        'environment_overrides': {'PYTHONPATH': str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1'}})
    # Единственный mode — штатный free bootstrap. Прямого подключения к рабочей БД нет.
    result = subprocess.run(argv, cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True)
    safe_lines = [line for line in result.stdout.splitlines() if line in {
        'bootstrap ready',
        'PATH-START exact published nine-case mirror ready; only synthetic superadmin pre-created',
        'Owned stand removed',
        'PASS bootstrap_repeat; sources verified; LLM_CALLS=0; owned database removed',
    } or re.fullmatch(r'Created empty owned stand: product4k_pytest_[a-f0-9]{32} application_tables=0', line)]
    save(directory / 'process-invocation.json', {'exit_code': result.returncode,
        'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(),
        'stderr_sha256': hashlib.sha256(result.stderr.encode()).hexdigest(),
        'safe_stdout_lines': safe_lines, 'raw_output_not_exported': True, 'invocations': 1})
    files = []
    for path in sorted(directory.rglob('*.json')):
        # State/password/connection не выгружаются даже при неуспешном cleanup.
        if path.name == 'state.json':
            continue
        data = path.read_bytes()
        files.append({'name': str(path.relative_to(directory)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()})
    summary_path = directory / 'runner-result.json'
    summary = json.loads(summary_path.read_bytes()) if summary_path.exists() else None
    print(json.dumps({'process_exit_code': result.returncode, 'directory': str(directory),
        'summary_result': summary.get('result') if summary else 'UNAVAILABLE',
        'runs': [{'run_id': run.get('run', {}).get('run_id'), 'result': run.get('result'),
                  'validation_errors': run.get('validation_errors')} for run in summary.get('runs', [])] if summary else [],
        'files': files}))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
