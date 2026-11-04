"""No DB/provider: synthetic evidence validates the actual runner/Node contract."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.assessment_first_case import summarize_runs

FIXTURE = Path(__file__).resolve().parents[1] / 'browser/fixtures/first-case-success.json'


def save(directory, name, value):
    (directory / (name + '.json')).write_text(json.dumps(value))


def successful_run(root, name='run'):
    directory = root / name
    directory.mkdir()
    run = {'run_id': name, 'database': 'product4k_pytest_' + name}
    save(directory, 'run', run)
    save(directory, 'cleanup', {**run, 'owner_verified': True, 'database_absent': True, 'state_absent': True})
    after = json.loads(FIXTURE.read_text())
    before = copy.deepcopy(after)
    before['cycle']['started_at'] = before['sessions'][0]['started_at'] = before['assessment_situation']['started_at'] = None
    save(directory, 'source-to-runtime-receipt', before)
    save(directory, 'first-case-receipt', after)
    # Only a synthetic file-existence fixture, not a real browser screenshot.
    (directory / 'first-case.png').write_bytes(b'synthetic-test-only')
    complete(directory, name)
    return directory


def complete(directory, name='run'):
    save(directory, 'completion', {'run_id': name, 'status': 'completed', 'exit_code': 0,
        'receipt_file': 'first-case-receipt.json',
        'receipt_sha256': hashlib.sha256((directory / 'first-case-receipt.json').read_bytes()).hexdigest()})


def result(root, exit_code=0):
    return summarize_runs(root, exit_code)['runs'][0]['result']


def test_reproduced_nonzero_exit_failure_and_empty_receipt_is_not_pass(tmp_path):
    directory = successful_run(tmp_path)
    save(directory, 'failure', {})
    save(directory, 'first-case-receipt', {})
    assert result(tmp_path, 1) == 'FAIL'


@pytest.mark.parametrize('name', ['completion', 'cleanup', 'source-to-runtime-receipt', 'first-case-receipt'])
def test_incomplete_evidence_never_passes(tmp_path, name):
    directory = successful_run(tmp_path)
    (directory / (name + '.json')).unlink()
    assert result(tmp_path) == 'FAIL'


@pytest.mark.parametrize('name', ['failure', 'failure-receipt', 'cleanup-deferred'])
def test_failure_artifact_even_empty_blocks_pass(tmp_path, name):
    directory = successful_run(tmp_path)
    save(directory, name, {})
    assert result(tmp_path) == 'FAIL'


@pytest.mark.parametrize('contents', ['{}', 'null', '{broken', '[]'])
def test_invalid_receipt_never_passes_or_crashes(tmp_path, contents):
    directory = successful_run(tmp_path)
    (directory / 'first-case-receipt.json').write_text(contents)
    complete(directory)
    assert result(tmp_path) == 'FAIL'


def test_failure_exit_without_failure_artifact_is_not_pass(tmp_path):
    successful_run(tmp_path)
    assert result(tmp_path, 1) == 'FAIL'


@pytest.mark.parametrize('status', ['PASS', 'PASS_WITH_WARNINGS'])
def test_complete_success_with_bound_evidence_passes(tmp_path, status):
    directory = successful_run(tmp_path)
    receipt = json.loads((directory / 'first-case-receipt.json').read_text())
    receipt['functional_generation']['admission_status'] = status
    save(directory, 'first-case-receipt', receipt)
    complete(directory)
    summary = summarize_runs(tmp_path, 0)
    assert summary['runs'][0]['result'] == 'PASS'
    assert summary['result'] == 'PASS'


@pytest.mark.parametrize('corruption', ['receipt_hash', 'cleanup_owner', 'completion_status', 'completion_exit',
    'completion_owner', 'answer', 'unadmitted', 'stage', 'presented_as', 'pre_start_chain', 'screenshot'])
def test_corrupt_completion_or_evidence_blocks_pass(tmp_path, corruption):
    directory = successful_run(tmp_path)
    if corruption == 'receipt_hash':
        (directory / 'first-case-receipt.json').write_text(FIXTURE.read_text() + '\n')
    elif corruption == 'cleanup_owner':
        value = json.loads((directory / 'cleanup.json').read_text()); value['run_id'] = 'foreign'
        save(directory, 'cleanup', value)
    elif corruption.startswith('completion_'):
        value = json.loads((directory / 'completion.json').read_text())
        value[{'completion_status': 'status', 'completion_exit': 'exit_code', 'completion_owner': 'run_id'}[corruption]] = {
            'completion_status': 'failed', 'completion_exit': 1, 'completion_owner': 'foreign'}[corruption]
        save(directory, 'completion', value)
    elif corruption == 'screenshot':
        (directory / 'first-case.png').unlink()
    elif corruption == 'pre_start_chain':
        value = json.loads((directory / 'source-to-runtime-receipt.json').read_text())
        value['assessment_situation']['assessment_situation_id'] = 'foreign'
        save(directory, 'source-to-runtime-receipt', value)
    else:
        value = json.loads((directory / 'first-case-receipt.json').read_text())
        if corruption == 'answer': value['assessment_answers'] = 1
        if corruption == 'unadmitted': value['functional_generation']['admitted_for_participant'] = False
        if corruption == 'stage': value['functional_generation']['stages']['tester']['batch_count'] = 0
        if corruption == 'presented_as': value['presented_as']['assessment_situation_id'] = 'foreign'
        save(directory, 'first-case-receipt', value)
        complete(directory)
    assert result(tmp_path) == 'FAIL'


def test_mixed_batch_uses_each_runs_recorded_process_exit(tmp_path):
    good = successful_run(tmp_path, 'good')
    bad = successful_run(tmp_path, 'bad')
    save(good, 'process-result', {'run_id': 'good', 'exit_code': 0})
    save(bad, 'process-result', {'run_id': 'bad', 'exit_code': 1})
    results = {r['run']['run_id']: r['result'] for r in summarize_runs(tmp_path, 1)['runs']}
    assert results == {'good': 'PASS', 'bad': 'FAIL'}


def test_empty_batch_is_failure(tmp_path):
    summary = summarize_runs(tmp_path, 0)
    assert summary['result'] == 'FAIL'
    assert summary['exit_code'] == 1


def test_process_result_is_recorded_only_for_new_runs(tmp_path):
    from scripts.assessment_first_case import record_process_result
    old = successful_run(tmp_path, 'old')
    previous = set(tmp_path.glob('*/run.json'))
    new = successful_run(tmp_path, 'new')
    record_process_result(tmp_path, previous, 1)
    assert not (old / 'process-result.json').exists()
    assert json.loads((new / 'process-result.json').read_text()) == {'run_id': 'new', 'exit_code': 1}


def test_summarize_cli_returns_failure_for_invalid_evidence_even_if_child_exited_zero(tmp_path, monkeypatch, capsys):
    import sys
    from scripts.assessment_first_case import main
    directory = successful_run(tmp_path)
    save(directory, 'first-case-receipt', {})
    save(tmp_path, 'runner-result', {'exit_code': 0})
    monkeypatch.setattr(sys, 'argv', ['assessment_first_case.py', '--directory', str(tmp_path), '--summarize-only'])
    assert main() == 1
    value = json.loads((tmp_path / 'runner-result.normalized.json').read_text())
    assert value['process_exit_code'] == 0 and value['exit_code'] == 1 and value['result'] == 'FAIL'
    capsys.readouterr()
