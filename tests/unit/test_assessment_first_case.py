from scripts.assessment_first_case import preflight


def test_code_identity_includes_readonly_viewport_collector(monkeypatch):
    import hashlib
    from scripts import assessment_first_case as runner
    # Unit-only Git metadata fixture: a shallow CI checkout need not have
    # origin/main. File bytes/hash stay real; runtime still requires that ref.
    metadata = {('rev-parse', 'HEAD'): '1' * 40,
                ('branch', '--show-current'): 'synthetic-unit',
                ('rev-parse', 'origin/main'): '2' * 40,
                ('status', '--short'): ''}
    def git_output(command, **kwargs):
        assert command[0] == 'git' and kwargs['cwd'] == runner.ROOT
        return metadata[tuple(command[1:])]
    monkeypatch.setattr(runner.subprocess, 'check_output', git_output)
    relative = 'tests/browser/fixtures/path-viewports.mjs'
    assert runner.code_identity()['files'][relative] == hashlib.sha256((runner.ROOT / relative).read_bytes()).hexdigest()
    for relative in ('tests/browser/fixtures/auth-password-form.mjs', 'tests/browser/fixtures/failure-page.mjs'):
        assert runner.code_identity()['files'][relative] == hashlib.sha256((runner.ROOT / relative).read_bytes()).hexdigest()


def test_code_identity_missing_origin_main_still_fails_closed(monkeypatch):
    import subprocess
    import pytest
    from scripts import assessment_first_case as runner
    def git_output(command, **kwargs):
        if command == ['git', 'rev-parse', 'origin/main']:
            raise subprocess.CalledProcessError(128, command)
        return 'synthetic-unit'
    monkeypatch.setattr(runner.subprocess, 'check_output', git_output)
    with pytest.raises(subprocess.CalledProcessError) as stopped:
        runner.code_identity()
    assert stopped.value.cmd == ['git', 'rev-parse', 'origin/main']
    assert stopped.value.returncode == 128


def test_source_selection_cannot_leak_into_functional_diagnostic():
    import pytest
    from scripts.assessment_first_case import select_release
    assert select_release('functional-diagnostic') is None
    with pytest.raises(ValueError, match='REQUIRES_PUBLISHED_PILOT'):
        select_release('functional-diagnostic', version='1.2')


def test_cli_bad_source_is_rejected_before_env_file_and_machine_checks(monkeypatch):
    import sys
    import pytest
    import dotenv
    from scripts import assessment_first_case as runner
    monkeypatch.setattr(sys, 'argv', ['assessment_first_case.py', '--program-source', 'published-pilot',
        '--program-version', '1.2', '--env-file', '/must-not-be-read.env'])
    monkeypatch.setattr(dotenv, 'dotenv_values', lambda *a, **kw: pytest.fail('must not read credentials'))
    monkeypatch.setattr(runner, 'preflight', lambda *a, **kw: pytest.fail('must not connect/probe'))
    with pytest.raises(SystemExit) as stopped:
        runner.main()
    assert stopped.value.code == 2


def test_cli_passes_selected_ref_not_ambient_override_to_bootstrap(tmp_path, monkeypatch):
    import json
    import sys
    from scripts import assessment_first_case as runner
    from tests.path_start_release_source import load_release_receipt
    _, expected = load_release_receipt()
    seen = []
    monkeypatch.setenv('P4K_PUBLISHED_RELEASE_REF', 'must-not-inherit')
    monkeypatch.setattr(sys, 'argv', ['assessment_first_case.py', '--program-source', 'published-pilot',
        '--directory', str(tmp_path), '--check-bootstrap'])
    monkeypatch.setattr(runner, 'preflight', lambda *a, **kw: {'status': 'READY'})
    monkeypatch.setattr(runner, 'code_identity', lambda: {'scope': 'synthetic_unit_fixture'})
    monkeypatch.setattr(runner, 'check_bootstrap', lambda d, p, py, env: seen.append(env))
    monkeypatch.setattr(runner, 'summarize_runs', lambda *a: {'exit_code': 0})
    assert runner.main() == 0
    assert json.loads(seen[0]['P4K_PUBLISHED_RELEASE_REF']) == expected

def test_preflight_reports_named_blockers_without_secret_values(monkeypatch):
    monkeypatch.delenv('STAND_ADMIN_URL',raising=False);monkeypatch.setenv('DEEPSEEK_API_KEYS','must-not-leak');monkeypatch.delenv('DEEPSEEK_MODEL',raising=False)
    result=preflight(0)
    assert result['status']=='BLOCKED'
    assert {item['code'] for item in result['checks']} >= {'isolated_database_admin','real_provider','browser'}
    assert 'must-not-leak' not in repr(result)


def test_reproduce_imported_source_and_only_two_status_changes():
    import copy
    import json
    from Api.assessment_case_contracts import validate_case_version
    from Api.m5_case_runtime import checksum
    from tests.assessment_first_case_evidence import FUNCTIONAL, changed_paths

    package = json.loads((FUNCTIONAL / 'case-package.json').read_text())
    source = next(case for case in package['cases'] if case['case_id'] == 'CASE.SPEC.02')
    fixture = copy.deepcopy(source)
    fixture['status'] = 'FROZEN'
    assert checksum(fixture) == '663bfc6c7452761ee951b92f7ebf45e77be2e06edfbacbf2dc8b58adbe45d231'
    fixture['author_case']['Status'] = 'FROZEN'
    imported = validate_case_version(fixture).model_dump(exclude_unset=True)
    assert checksum(imported) == '179fa0f8192862bee6af3190c8560f9c5ed133cc2fe07d6f5b6a98e6e3c9b729'
    assert {change['path'] for change in changed_paths(source, imported)} == {'/status', '/author_case/Status'}


def test_repair_is_counted_once_and_secrets_not_exported():
    from tests.assessment_first_case_evidence import provider_calls, functional_receipt
    operation = {'operation_id': 'synthetic:repair', 'kind': 'generation_repair',
        'input_checksum': 'synthetic',
        'sent': {'provider': 'deepseek', 'messages': ['must-not-export'], 'api_key': 'must-not-export'},
        'provider': {'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12}}}
    trace = {'generation_operation': operation,
        'repair': {'repair_generation_operation': operation},
        'tester': {'aggregation': {'status': 'PASS'}}, 'admitted_for_participant': True}
    calls = provider_calls(trace)
    assert len(calls) == 1
    assert 'must-not-export' not in repr(calls)
    assert functional_receipt(trace)['usage']['total_tokens'] == 12


def test_duplicate_operation_with_different_usage_is_rejected():
    import pytest
    from tests.assessment_first_case_evidence import provider_calls
    with pytest.raises(ValueError, match='OPERATION_ID_CONTENT_CONFLICT'):
        provider_calls([
            {'operation_id': 'same', 'sent': {}, 'provider': {'usage': {'total_tokens': 1}}},
            {'operation_id': 'same', 'sent': {}, 'provider': {'usage': {'total_tokens': 2}}},
        ])


def test_summary_separates_bootstrap_scope_and_requires_cleanup(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    from scripts.assessment_first_case import summarize_runs
    directory = tmp_path / 'run'
    directory.mkdir()
    run = {'scope': 'bootstrap_repeat', 'run_id': 'synthetic', 'database': 'product4k_pytest_synthetic'}
    (directory / 'run.json').write_text(json.dumps(run))
    source = Path(__file__).resolve().parents[2] / 'docs/evc/evidence/assessment-contour-2026-11-04/source-provenance.json'
    (directory / 'source-provenance.json').write_bytes(source.read_bytes())
    (directory / 'completion.json').write_text(json.dumps({'run_id': 'synthetic', 'status': 'completed',
        'exit_code': 0, 'receipt_file': 'source-provenance.json',
        'receipt_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}))
    assert summarize_runs(tmp_path, 0)['runs'][0]['result'] == 'FAIL'
    (directory / 'cleanup.json').write_text(json.dumps({
        **run, 'owner_verified': True, 'database_absent': True, 'state_absent': True}))
    assert summarize_runs(tmp_path, 0)['runs'][0]['result'] == 'PASS_BOOTSTRAP_ONLY'


def test_candidate_checksum_uses_generator_contract_not_snapshot_contract():
    from Api.m5_functional_generation_service import checksum as candidate_checksum
    from Api.m5_case_runtime import checksum as snapshot_checksum
    from tests.assessment_first_case_evidence import functional_receipt
    candidate = {'CaseID': 'CASE.SPEC.02', 'synthetic': True}
    expected = candidate_checksum(candidate)
    assert expected != snapshot_checksum(candidate)
    receipt = functional_receipt({'accepted_as': candidate, 'candidate_checksum': expected})
    assert receipt['candidate_recomputed_checksum'] == expected


def test_incomplete_admission_preserves_check_id_and_technical_reason():
    from tests.assessment_first_case_evidence import functional_receipt
    receipt = functional_receipt({'tester': {'aggregation': {'status': 'INCOMPLETE',
        'incomplete_checks': [{'check_id': 'common.authority', 'status': 'NOT_RUN',
            'reason': 'Tester не вернул обязательный результат.', 'evidence_paths': []}]}},
        'admitted_for_participant': False})
    assert receipt['admission_status'] == 'INCOMPLETE'
    assert receipt['incomplete_checks'][0]['check_id'] == 'common.authority'
    assert receipt['incomplete_checks'][0]['status'] == 'NOT_RUN'


def test_lineage_export_never_guesses_missing_or_ambiguous_assignments():
    from tests.assessment_first_case_evidence import assignment_lineage
    class Connection:
        def __init__(self, count):
            self.count = count
            self.queries = 0
        def execute(self, sql, params):
            self.queries += 1
            assert params == (3, 'specialist-pilot', 11)
            assert 'identity_json' not in sql and 'answers_json' not in sql
            return self
        def fetchall(self):
            return [{} for _ in range(self.count)]
    for count in (0, 2):
        connection = Connection(count)
        assert assignment_lineage(connection, user_id=3, assignment_ref='specialist-pilot', configuration_id=11) == {
            'status': 'UNKNOWN_OR_AMBIGUOUS', 'matching_assignments': count}
        assert connection.queries == 1
