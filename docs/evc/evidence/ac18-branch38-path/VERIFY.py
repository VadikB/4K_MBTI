"""Offline integrity and linkage check; branch PATH never proves deployed AC18."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

if not __debug__:
    raise SystemExit('Assertions required; do not use -O')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--checkout', type=Path, help='Exact candidate checkout; adds existing Node/Python validators, no DB/LLM')
args = parser.parse_args()
root = Path(__file__).resolve().parent
remote = root / 'remote'
SHA = '38bf82448e63e55414ff55ac45fa126e9c4385f0'
MAIN = '339aff9034ff005bc20d072876b3fbef4f834c5e'
RUN = '8336eef355fc43b49c1837fc89e2868e'
PIN = '09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b'
def read(path): return json.loads(path.read_bytes())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

package_file = root / 'MANIFEST.json'
package_files_checked = 0
if package_file.is_file():
    package = read(package_file)
    assert package['candidate_sha'] == SHA and package['main_deployed_sha'] == MAIN
    for name, ref in package['files'].items():
        file = (root / name).resolve()
        assert file.is_relative_to(root.resolve()) and not file.is_symlink(), name
        assert file.stat().st_size == ref['bytes'] and digest(file) == ref['sha256'], name
        package_files_checked += 1

index = read(remote / 'delivery-manifest.json')
assert index['run_id'] == RUN and index['raw_logs_and_secret_state_exported'] is False
for name, ref in index['files'].items():
    file = (remote / name).resolve()
    assert file.is_relative_to(remote.resolve()), name
    assert file.stat().st_size == ref['bytes'] and digest(file) == ref['sha256'], name
assert not any(file.name in ('.env', 'state.json', 'server.log', 'runner.stdout.log') for file in remote.rglob('*'))
out = remote / 'run-evidence'
folders = list(out.glob('*/run.json'))
assert len(folders) == 1
folder = folders[0].parent
run = read(folders[0])
assert run['run_id'] == RUN and run['database'] == 'product4k_pytest_' + RUN
assert run['code']['sha'] == SHA and run['code']['origin_main'] == MAIN
assert run['code']['worktree_status'] == '' and len(run['code']['files']) == 18
assert run['program_source'] == 'published-pilot' and run['provider_mode'] == 'real'
assert digest(folder / 'published-release-source.json') == PIN
guard = read(out / 'launch-guard.json')
assert guard['authorization_id'] == 'AC18-BRANCH38-20261107-48b27d91'
assert guard['sha'] == SHA and guard['main_deployed_sha_unchanged'] == MAIN
assert guard['candidate_not_deployed'] and guard['formal_deployed_release_ac18'] is False
assert guard['paid_run_count_authorized'] == 1 and guard['retries_of_full_runner'] == 0
assert guard['provider_recovery']['pages'][1]['current'] == 'Resolved'
assert all(guard['published_sources_match'].values())
invocation = read(out / 'runner-invocation.json')
assert invocation['runner_invocations'] == 1 and invocation['automatic_full_runner_retry'] is False
summary = read(out / 'runner-result.json')
assert len(summary['runs']) == 1 and summary['result'] in ('PASS', 'FAIL')
assert summary['process_exit_code'] == invocation['exit_code']
passed = summary['result'] == 'PASS'
assert (invocation['exit_code'] == 0) == passed
assert (summary['runs'][0]['result'] == 'PASS') == passed
process = read(folder / 'process-result.json')
assert process['run_id'] == RUN and process['exit_code'] == invocation['exit_code']
completion = read(folder / 'completion.json')
assert completion['run_id'] == RUN
if passed:
    assert completion['status'] == 'completed' and completion['exit_code'] == 0
    assert completion['receipt_file'] == 'first-case-receipt.json'
    assert completion['receipt_sha256'] == digest(folder / 'first-case-receipt.json')
    assert not summary['runs'][0]['validation_errors']
    assert not (folder / 'failure.json').exists() and not (folder / 'failure-receipt.json').exists()
    receipt = read(folder / 'first-case-receipt.json')
    before = read(folder / 'source-to-runtime-receipt.json')
    assert receipt['assessment_answers'] == 0 and receipt['http_start_status'] == 201
    assert receipt['cycle']['started_at'] and not before['cycle']['started_at']
    assert receipt['assessment_situation']['assessment_situation_id'] == before['assessment_situation']['assessment_situation_id']
    assert receipt['functional_generation']['candidate_checksum'] == before['functional_generation']['candidate_checksum']
    assert receipt['functional_generation']['admitted_for_participant'] is True
    assert receipt['functional_generation']['admission_status'] in ('PASS', 'PASS_WITH_WARNINGS')
    assert receipt['functional_generation']['unique_operation_count'] == len(receipt['functional_generation']['calls'])
    for key in ('blocking_failures', 'deterministic_failures', 'deterministic_protocol_errors', 'incomplete_checks'):
        assert receipt['functional_generation'][key] == [], key
    assert receipt['presented_as']['dom_introduction_matched'] is True
    assert receipt['presented_as']['assessment_situation_id'] == receipt['assessment_situation']['assessment_situation_id']
    assert receipt['presented_as']['participant_payload_checksum'] == receipt['saved_checksums']['participant_payload']
    for width in (1440, 320, 390, 768):
        assert (folder / f'first-as-{width}.png').is_file()
    for phase in ('superadmin-program', 'admin-questionnaire', 'admin-assignment', 'participant-ready', 'first-as'):
        widths = read(folder / f'{phase}-viewports.json')
        assert [row['width'] for row in widths] == [1440, 320, 390, 768]
        for row in widths:
            assert 'error' not in row and row['document']['scrollWidth'] <= row['width'] + 1
            assert row['document']['visibility'] == 'visible'
            for control in row['controls']:
                geometry = control['geometry']
                assert geometry['visibility'] == 'visible' and geometry['visible_ratio'] > 0
                assert geometry['box']['x'] >= -1
                assert geometry['box']['x'] + geometry['box']['width'] <= row['width'] + 1
else:
    assert completion['status'] == 'failed' and summary['runs'][0]['validation_errors']
    assert (folder / 'failure.json').is_file() and (folder / 'failure-receipt.json').is_file()
    receipt = read(folder / 'failure-receipt.json')
    assert receipt['assessment_answers'] == 0
cleanup = read(folder / 'cleanup.json')
assert cleanup['run_id'] == RUN and cleanup['database'] == run['database']
assert all(cleanup[key] is True for key in ('owner_verified', 'database_absent', 'state_absent'))
assert cleanup['force'] is False
independent = read(out / 'cleanup-readback.json')
assert independent['database_count'] == independent['active_connections'] == 0
assert all(independent[key] is True for key in ('state_absent', 'port_free', 'read_only', 'transaction_rolled_back', 'permanent_db_not_connected'))
assert all(row['saved_before_cleanup'] for row in independent['terminal_receipts_before_cleanup'].values())
context = read(out / 'post-run-code-context.json')
assert context['main_deployed_sha'] == MAIN and context['candidate_sha'] == SHA
assert context['candidate_clean'] and context['candidate_not_deployed'] and context['merge_deploy_performed'] is False
preflight = remote / 'fresh-preflight'
assert read(preflight / 'preflight-result.json')['status'] == 'READY_FOR_ONE_UNRELEASED_BRANCH_CANDIDATE_RUN'
assert read(preflight / 'schema-comparison.json')['result'] == 'EXACT_SCOPED_SCHEMA_MATCH'
assert all(read(preflight / 'source-comparison.json')['objects_match'].values())
provider = read(preflight / 'preflight.json')['provider']
assert provider['model'] == 'deepseek-flash' and provider['model_source'] == 'provider_contract'
assert provider['legacy_env_model_ignored'] is True
source_checked = 0
if args.checkout:
    checkout = args.checkout.resolve()
    assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=checkout, text=True).strip() == SHA
    for name, expected in {**run['code']['files'], **context['candidate_ui_files']}.items():
        assert digest(checkout / name) == expected, name
        source_checked += 1
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['DB_POOL_MIN_SIZE'] = '0'
    sys.path.insert(0, str(checkout))
    spec = importlib.util.spec_from_file_location('branch_candidate_summary', checkout / 'scripts/assessment_first_case.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    normalized = module.summarize_runs(out, invocation['exit_code'])
    assert normalized['result'] == summary['result']
    assert normalized['runs'][0]['validation_errors'] == summary['runs'][0]['validation_errors']
print(json.dumps({'integrity':'PASS', 'primary_files':len(index['files']), 'source_files_checked':source_checked,
    'package_files_checked':package_files_checked,
    'candidate_path':summary['result'], 'formal_deployed_release_AC18':'NOT_CLOSED_BY_BRANCH_RUN',
    'cleanup':'PASS', 'new_provider_or_database_calls':0}, ensure_ascii=False))
