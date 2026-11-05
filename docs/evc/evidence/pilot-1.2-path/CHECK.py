"""Independent offline consistency check of actual PATH receipts and saved bytes."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

if not __debug__:
    raise RuntimeError('PATH_EVIDENCE_REQUIRES_ASSERTIONS')
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).parent
SHA = 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
PIN = '09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b'
safe = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
os.environ.clear(); os.environ.update(safe)
os.environ.update(AGENT4K_ISOLATED_STAND='1', AGENT4K_STAND_MARKER='stand-10.2:path-offline',
    DB_HOST='127.0.0.1', DB_NAME='product4k_pytest_path_offline', DB_USER='offline', DB_POOL_MIN_SIZE='0')
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
manifest = read(directory / 'MANIFEST.json')
assert len(manifest['files']) == 34
for item in manifest['files']:
    path = (directory / item['path']).resolve()
    assert path.is_relative_to(directory.resolve()) and path.name != 'state.json' and '.private.' not in path.name
    assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
controller = read(directory / 'controller-result.json')
assert controller['exit_code'] == 0 and controller['runner_result'] == 'PASS'
assert controller['authorized_runner_invocations'] == 1 and controller['retry'] is False
launch = read(directory / 'paid-launch.json')
assert launch['authorized_runner_invocations'] == 1 and launch['retry'] is False
assert launch['prepared_file_sha256'] == sha(directory / 'prepared.json')
assert launch['checkout_status'] == '' and launch['fresh_live_source_equal'] is True
fresh = summarize_runs(directory / 'run', 0)
assert fresh['result'] == 'PASS' and fresh['exit_code'] == 0 and len(fresh['runs']) == 1
run = fresh['runs'][0]
assert run['result'] == 'PASS' and run['validation_errors'] == []
run_id = '2ff983f12c67494b990b0f85284b8d70'
assert run['run']['run_id'] == run_id and run['run']['database'] == 'product4k_pytest_' + run_id
assert run['process_exit_code'] == 0 and run['completion']['status'] == 'completed'
run_dir = next((directory / 'run').glob('*/run.json')).parent
source, selected = load_release_receipt(path=run_dir / 'published-release-source.json', sha256=PIN, version='1.2')
assert selected['program']['id'] == 2
before = read(run_dir / 'source-to-runtime-receipt.json'); after = read(run_dir / 'first-case-receipt.json')
node = subprocess.run(['node', str(ROOT / 'tests/browser/fixtures/preparation-receipt.mjs'),
    str(run_dir / 'first-case-receipt.json'), str(run_dir / 'source-to-runtime-receipt.json'),
    str(run_dir / 'published-release-source.json')], capture_output=True, text=True)
assert node.returncode == 0, 'REAL_NODE_FIRST_CASE_VALIDATOR_FAILED'
assert before['start_readiness']['can_start'] is True and before['start_readiness']['reasons'] == []
assert after['http_start_status'] == 201 and after['assessment_answers'] == 0
assert after['presented_as']['assessment_situation_id'] == after['assessment_situation']['assessment_situation_id']
assert after['presented_as']['dom_introduction_matched'] is True and (run_dir / 'first-case.png').stat().st_size > 0
generated = after['functional_generation']; calls = generated['calls']
assert generated['admission_status'] == 'PASS' and generated['admitted_for_participant'] is True
assert generated['repair_used'] is True and len(calls) == len({c['operation_id'] for c in calls}) == 20
assert generated['stages']['tester']['batch_count'] == 5 and generated['stages']['challenger']['batch_count'] == 4
assert generated['usage']['total_tokens'] == 1523716
assert run['provider_completed_requests'] == 21
assert sum(':json-retry' in c['routing_key'] for c in run['provider_completions']) == 1
plan = before['plan']; diagnostics = plan['diagnostics']
assert plan['status'] == 'LIMITED' and plan['content_checksum_matches'] and plan['status_matches_revision']
assert plan['content_checksum'] == plan['content_recomputed_checksum']
assert checksum(diagnostics) == plan['diagnostics_checksum']
assert len(diagnostics['full_target_set']) == 61 and len(diagnostics['planned_target_set']) == 39
assert len(diagnostics['outside_plan_target_ids']) == 22 and diagnostics['uncovered_planned_target_ids'] == []
assert [r['case_id'] for r in diagnostics['route']] == ['CASE.SPEC.' + x for x in ('02','03','04','07','05','01','06','08')]
assert after['cycle']['time_budget_seconds'] == 7200 and after['cycle']['calendar_window_seconds'] == 259200
identity = read(directory / 'run/code-identity.json')
assert identity['sha'] == identity['origin_main'] == SHA and identity['worktree_status'] == ''
for name, expected in identity['files'].items():
    data = subprocess.check_output(['git', 'show', SHA + ':' + name], cwd=ROOT)
    assert hashlib.sha256(data).hexdigest() == expected
provenance = read(run_dir / 'source-provenance.json')
assert provenance['release'] == source and provenance['release_receipt_sha256'] == PIN
assert provenance['initial_counts'] == {'users': 1, 'organizations': 0, 'memberships': 0, 'profiles': 0, 'cycles': 0, 'assignments': 0}
assert provenance['methodology_approval'].startswith('NO_NEW_APPROVAL')
cleanup = read(directory / 'cleanup-readback.json')
assert cleanup['run_id'] == run_id and cleanup['database_absent'] and cleanup['state_absent']
assert cleanup['active_connections'] == 0 and cleanup['marker_verified_by_existing_destroy'] and not cleanup['force']
working = read(directory / 'working-readback.json')
assert working['read_only'] and working['rollback'] and working['same_published_source'] and working['schema_unchanged']
assert working['target_program_connections'] == 0 and working['writes_by_this_operation'] is False
log = read(directory / 'server-log-export.json')
assert log['raw_log_exported'] is False and log['export_sha256'] == sha(run_dir / 'server.log')
assert log['provider_completed_requests'] == 21
assert not list(directory.rglob('state.json')) and not list(directory.rglob('failure.json'))
assert not attempts and not any(name in sys.modules for name in ('Api.config', 'Api.database', 'Api.llm'))
print(json.dumps({'result': 'PASS_OFFLINE_ACTUAL_PATH', 'run_id': run_id,
    'program_version': '1.2', 'as_id': after['assessment_situation']['assessment_situation_id'],
    'admission': generated['admission_status'], 'start_http_status': 201, 'assessment_answers': 0,
    'unique_operations': 20, 'completed_http_requests': 21, 'retained_tokens': 1523716,
    'full_m2': 61, 'planned': 39, 'outside': 22, 'primary_files_verified': 34,
    'runtime_files_verified': len(identity['files']), 'python_socket_attempts': 0,
    'db_connections': 0, 'new_provider_calls': 0, 'owned_cleanup_verified': True,
    'checksum_scope': 'Byte hashes, projection body and same-type refs validated; internal candidate/full plan bodies not exported are verified by stored server recomputation/readiness, not independently reconstructed.'}))
