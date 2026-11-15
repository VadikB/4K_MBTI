from scripts.assessment_first_case import valid_path_budget


def test_functional_completion_cannot_erase_missing_budget(tmp_path, monkeypatch):
    import hashlib
    import json
    from types import SimpleNamespace
    from scripts import assessment_first_case as runner
    directory = tmp_path / 'synthetic-run'
    directory.mkdir()
    def write(name, value):
        (directory / (name + '.json')).write_text(json.dumps(value))
    write('run', {'run_id': 'synthetic-run', 'database': 'product4k_pytest_fixture',
                  'bounded_path': True})
    write('cleanup', {'run_id': 'synthetic-run', 'database': 'product4k_pytest_fixture',
                      'owner_verified': True, 'database_absent': True, 'state_absent': True})
    write('first-case-receipt', {'synthetic': True})
    write('source-to-runtime-receipt', {'synthetic': True})
    (directory / 'first-case.png').write_bytes(b'synthetic-image')
    digest = hashlib.sha256((directory / 'first-case-receipt.json').read_bytes()).hexdigest()
    write('completion', {'run_id': 'synthetic-run', 'status': 'completed', 'exit_code': 0,
                         'receipt_file': 'first-case-receipt.json', 'receipt_sha256': digest})
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    summary = runner.summarize_runs(tmp_path, 0)
    assert summary['result'] == 'FAIL'
    assert 'PATH_BUDGET_INVALID_OR_INCOMPLETE' in summary['runs'][0]['validation_errors']
    write('path-action-budget', {'contract': 'path-action-budget/1', 'run_id': 'synthetic-run',
        'scope': 'path29-first-case', 'status': 'completed', 'rejected': None,
        'limits': {'actions': 2, 'visuals': 2}, 'used': {'actions': 1, 'visuals': 1}})
    assert runner.summarize_runs(tmp_path, 0)['result'] == 'PASS'


def test_guarded_summary_requires_complete_matching_finite_receipt():
    budget = {'contract': 'path-action-budget/1', 'run_id': 'synthetic-run',
              'scope': 'path29-first-case', 'status': 'completed',
              'limits': {'actions': 100, 'visuals': 40},
              'used': {'actions': 99, 'visuals': 39}, 'rejected': None}
    assert valid_path_budget(budget, 'synthetic-run')
    for field, invalid in [('status', 'exceeded'), ('run_id', 'another-run'),
                           ('rejected', {'operation': 'click'}), ('limits', {}),
                           ('used', {'actions': 101, 'visuals': 0})]:
        changed = {**budget, field: invalid}
        assert not valid_path_budget(changed, 'synthetic-run')
    assert not valid_path_budget(None, 'synthetic-run')
