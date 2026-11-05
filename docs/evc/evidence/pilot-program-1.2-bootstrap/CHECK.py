"""Повторная offline-проверка actual published bootstrap; без .env/БД/LLM."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

if not __debug__:
    raise RuntimeError('BOOTSTRAP_EVIDENCE_REQUIRES_ASSERTIONS')
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).parent
RUNTIME = 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
DIGEST = '09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b'
os.environ.clear()
os.environ.update(AGENT4K_ISOLATED_STAND='1', AGENT4K_STAND_MARKER='stand-10.2:bootstrap-offline',
    DB_HOST='127.0.0.1', DB_NAME='product4k_pytest_bootstrap_offline', DB_USER='offline', DB_POOL_MIN_SIZE='0')
attempts = []


class NoSocket(socket.socket):
    def __new__(cls, *args, **kwargs):
        attempts.append(True)
        raise AssertionError('OFFLINE_NETWORK_FORBIDDEN')


socket.socket = NoSocket
sys.path.insert(0, str(ROOT))
from scripts.assessment_first_case import summarize_runs
from tests.path_start_release_source import load_release_receipt
from Api.m5_case_runtime import checksum


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


directory = HERE / 'server-evidence'
manifest = read(directory / 'archive-files.json')
assert len(manifest['files']) == 16
for item in manifest['files']:
    path = (directory / item['path']).resolve()
    assert path.is_relative_to(directory.resolve()) and path.name != 'state.json'
    assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
remote = read(HERE / 'remote-result.json')
assert remote['exit_code'] == 0 and remote['stdout']['process_exit_code'] == 0
assert sha(HERE / 'RUN_FREE.py') == remote['launcher_sha256']
for item in remote['stdout']['files']:
    path = directory / 'bootstrap' / item['name']
    assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
first = read(HERE / 'first-attempt.json')
assert first['exit_code'] == 1 and sha(HERE / 'RUN_FREE.initial.py') == first['launcher_sha256']
failure = read(directory / 'first-attempt/failure-diagnostic.json')
assert failure['exception_type'] == 'ModuleNotFoundError' and failure['missing_modules'] == ['tests']
assert not failure['PYTHONPATH_set'] and not failure['preflight_json_present'] and failure['run_json_count'] == 0
bootstrap = directory / 'bootstrap'
preflight = read(bootstrap / 'preflight.json')
assert preflight['status'] == 'READY' and all(c['status'] == 'READY' for c in preflight['checks'])
identity = read(bootstrap / 'code-identity.json')
assert identity['sha'] == identity['origin_main'] == RUNTIME
for name, actual in identity['files'].items():
    data = subprocess.check_output(['git', 'show', RUNTIME + ':' + name], cwd=ROOT)
    assert hashlib.sha256(data).hexdigest() == actual
assert all(line.startswith('?? ') for line in identity['worktree_status'].splitlines())
fresh = summarize_runs(bootstrap, 0)
assert fresh['result'] == 'PASS' and fresh['exit_code'] == 0 and len(fresh['runs']) == 1
run = fresh['runs'][0]
assert run['result'] == 'PASS_BOOTSTRAP_ONLY' and run['validation_errors'] == []
assert run['run']['llm_calls'] == run['provider_completed_requests'] == 0
assert run['run']['run_id'] == '5d4f68db1fae48bf9c82be26b2bee390'
assert run['run']['database'] == 'product4k_pytest_' + run['run']['run_id']
run_dir = next(bootstrap.glob('*/run.json')).parent
source, selected = load_release_receipt(path=run_dir / 'published-release-source.json', sha256=DIGEST, version='1.2')
assert selected['program']['id'] == 2 and selected['program']['assessment_configuration_id'] == 11
provenance = read(run_dir / 'source-provenance.json')
assert provenance['initial_counts'] == {'users': 1, 'organizations': 0, 'memberships': 0, 'profiles': 0, 'cycles': 0, 'assignments': 0}
assert provenance['release'] == source and provenance['release_receipt_sha256'] == DIGEST
case = provenance['case']
assert checksum(case['imported_json']) == case['imported_checksum'] == case['imported_recomputed_checksum']
assert provenance['package']['imported_checksum'] == provenance['package']['imported_recomputed_checksum']
original = next(c for c in source['cases'] if c['case_id'] == case['id'])
assert case['imported_checksum'] == original['content_checksum']
actual_qa = [{k: row[k] for k in ('scope', 'result', 'evidence_json', 'evidence_checksum')}
             for row in provenance['qa_evidence']]
assert sorted(actual_qa, key=lambda q: q['scope']) == sorted(original['qa_evidence'], key=lambda q: q['scope'])
assert 'Original published QA origins preserved' in provenance['origin_contract_note']
assert provenance['methodology_approval'].startswith('NO_NEW_APPROVAL')
assert provenance['admission']['admitted'] is True
cleanup = read(bootstrap / 'cleanup-readback.json')
assert cleanup['run_id'] == run['run']['run_id'] and cleanup['database'] == run['run']['database']
assert cleanup['database_absent'] and cleanup['state_absent'] and cleanup['marker_verified_by_existing_destroy']
assert cleanup['active_database_connections'] == 0 and not cleanup['force']
assert cleanup['permanent_database_used'] is cleanup['permanent_database_writes'] is False
assert cleanup['provider_calls'] == 0
normalized = read(bootstrap / 'runner-result.normalized.json')
assert normalized['result'] == 'PASS' and normalized['runs'][0]['result'] == 'PASS_BOOTSTRAP_ONLY'
assert normalized['runs'][0]['completion'] == run['completion']
assert not list(directory.rglob('state.json'))
assert not attempts and not any(name in sys.modules for name in ('Api.config', 'Api.database', 'Api.llm'))
print(json.dumps({'result': 'PASS_BOOTSTRAP_ONLY', 'program_id': 2, 'program_version': '1.2',
    'source_receipt_sha256': DIGEST, 'run_id': run['run']['run_id'], 'files_verified': 16,
    'runtime_files_verified': len(identity['files']), 'initial_counts': provenance['initial_counts'],
    'catalog_cases': len(source['cases']), 'original_qa_source_records': sum(len(c['qa_evidence']) for c in source['cases']),
    'owned_database_absent': True, 'remaining_connections': 0, 'provider_calls': 0,
    'socket_attempts': 0, 'db_connections': 0, 'full_path': 'NOT_RUN',
    'runtime_tracked_clean': True, 'runtime_untracked_entries': len(identity['worktree_status'].splitlines()),
    'limitations': 'Bootstrap only. No human QA/admission/content quality re-review; no AS/start/answers.'}))
