"""Pure source regression: no DB, paid calls, or manufactured QA results."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tests.path_start_release_source import validate_release

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def release():
    return json.loads((ROOT / 'browser/fixtures/path-start-release.json').read_text())


def test_exact_published_sources_match_repository(release):
    from scripts.plan_specialist_program_release import build_admitted_materials
    from Api.m5_case_runtime import checksum
    package, runtime, refs = build_admitted_materials(release['catalog']['decision_basis'])
    validate_release(release)
    assert {case['case_id']: checksum(case) for case in package['cases']} == {
        case['case_id']: case['content_checksum'] for case in release['cases']}
    for case in release['cases']:
        for qa in case['qa_evidence']:
            assert qa['evidence_json']['evidence_ref'] == refs[qa['scope']]
            path = ROOT.parent / refs[qa['scope']]['path']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == refs[qa['scope']]['sha256']
    assert runtime['manifest_checksum'] == release['catalog']['manifest_json']['runtime_rule_ref']['manifest_checksum']


def future_release_fixture(release):
    """Metadata model only; no new program is actually published by this test."""
    import copy
    from Api.assessment_programs import definition_checksum
    from tests.unit.test_pilot_plan_admission import snapshot
    value = copy.deepcopy(release)
    program = value['program']
    program['version'] = 'synthetic-next-version'
    program['source_refs_json']['pilot_plan_admission'] = snapshot()
    program['definition_checksum'] = definition_checksum(code=program['code'], version=program['version'],
        name=program['name'], assignment_ref=program['assignment_ref'], mode=program['mode'],
        configuration_id=program['assessment_configuration_id'], catalog_version_id=program['catalog_version_id'],
        role_version_ids=[role['id'] for role in value['roles']], source_refs=program['source_refs_json'])
    return value


def test_new_exact_program_snapshot_can_be_verified_without_switching_current_fixture(release):
    future = future_release_fixture(release)
    validate_release(future)
    assert release['program']['version'] == '1.1'
    assert 'pilot_plan_admission' not in release['program']['source_refs_json']


def test_future_program_cannot_lose_human_plan_decision(release):
    future = future_release_fixture(release)
    future['program']['source_refs_json']['pilot_plan_admission']['owner_decision']['methodologist']['status'] = 'PENDING'
    with pytest.raises(ValueError, match='PILOT_PLAN_'):
        validate_release(future)


@pytest.mark.parametrize('mutation', [
    lambda s: s['program'].update(version='1.2'),
    lambda s: s['configuration'].update(catalog_version_id=99),
    lambda s: s['program']['source_refs_json'].update(prompt_bundle_checksum='0' * 64),
    lambda s: s['cases'].pop(),
    lambda s: s['cases'][0]['qa_evidence'].pop(),
    lambda s: s['cases'][0]['qa_evidence'][0]['evidence_json']['origin'].update(synthetic=True),
    lambda s: s['cases'][0]['admission'].update(admitted=False),
    lambda s: s['cases'][0].update(content_checksum='0' * 64),
    lambda s: s['artifact_readback'][0].update(recomputed_checksum='0' * 64),
])
def test_changed_or_synthetic_source_is_rejected(release, mutation):
    changed = copy.deepcopy(release)
    mutation(changed)
    with pytest.raises(AssertionError):
        validate_release(changed)


@pytest.mark.parametrize('isolated,database,maximum,table', [
    ('0', 'product4k_pytest_example', 0, 'm5_catalogs'),
    ('1', 'agent4k_test', 0, 'm5_catalogs'),
    ('1', 'product4k_pytest_example', 2, 'm5_catalogs'),
    ('1', 'product4k_pytest_example', 0, 'users'),
    ('0', 'product4k_pytest_example', 0, 'assessment_program_definitions'),
    ('1', 'agent4k_test', 0, 'assessment_program_definitions'),
    ('1', 'product4k_pytest_example', 2, 'assessment_program_definitions'),
])
def test_id_reservation_refuses_nonowned_or_occupied_target(monkeypatch, isolated, database, maximum, table):
    from tests.path_start_release_inputs import reserve_release_ids
    monkeypatch.setenv('AGENT4K_ISOLATED_STAND', isolated)
    statements = []
    class Connection:
        def execute(self, sql, params=None):
            statements.append(sql)
            return self
        def fetchone(self):
            return {'name': database, 'n': maximum}
    with pytest.raises(AssertionError):
        reserve_release_ids(Connection(), table, 2)
    assert not any('setval' in sql for sql in statements)


@pytest.mark.parametrize('table', [
    'm5_case_versions', 'm5_catalogs', 'assessment_configurations', 'assessment_program_definitions',
])
def test_id_reservation_accepts_each_release_table_on_empty_owned_target(monkeypatch, table):
    from tests.path_start_release_inputs import reserve_release_ids
    monkeypatch.setenv('AGENT4K_ISOLATED_STAND', '1')
    statements = []
    class Connection:
        def execute(self, sql, params=None):
            statements.append((sql, params))
            return self
        def fetchone(self):
            return {'name': 'product4k_pytest_positive', 'n': 0}
    reserve_release_ids(Connection(), table, 2)
    assert statements[-1][1] == (table, 'id', 2)
    assert 'setval' in statements[-1][0]


def test_default_receipt_is_still_byte_pinned_legacy_1_1():
    from tests.path_start_release_source import DEFAULT_RECEIPT_SHA256, load_release_receipt
    source, ref = load_release_receipt()
    assert source['program']['version'] == ref['program']['version'] == '1.1'
    assert ref['sha256'] == DEFAULT_RECEIPT_SHA256
    assert 'pilot_plan_admission' not in source['program']['source_refs_json']


def selected_fixture(tmp_path, release, *, future=True):
    from tests.path_start_release_source import load_release_receipt
    value = future_release_fixture(release) if future else copy.deepcopy(release)
    if future:
        value['program']['id'] = 3  # SYNTHETIC future metadata, not a real publication id.
    path = tmp_path / 'synthetic-metadata-source.json'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, value, load_release_receipt(path=path, sha256=digest, version=value['program']['version'])[1]


def test_explicit_future_metadata_is_exactly_selected_without_replacing_default(tmp_path, release):
    from tests.path_start_release_source import load_release_reference, load_release_receipt
    path, value, ref = selected_fixture(tmp_path, release)
    actual, selected = load_release_reference(ref)
    assert actual == value and selected == ref
    assert selected['program']['id'] == 3 and selected['path'] == str(path)
    assert load_release_receipt()[0]['program']['version'] == '1.1'


@pytest.mark.parametrize('parts', [
    {'path': 'unused'}, {'sha256': '0' * 64}, {'version': '1.2'},
    {'path': 'unused', 'sha256': '0' * 64}, {'path': 'unused', 'version': '1.2'},
    {'sha256': '0' * 64, 'version': '1.2'},
    {'path': 'unused', 'sha256': 'not-a-hash', 'version': '1.2'},
])
def test_partial_or_bad_selector_rejected_without_reading_files(parts, monkeypatch):
    from tests.path_start_release_source import load_release_receipt
    monkeypatch.setattr(Path, 'read_bytes', lambda *args: pytest.fail('must not read any source'))
    with pytest.raises(ValueError, match='COMPLETE_SELECTOR_REQUIRED'):
        load_release_receipt(**parts)


@pytest.mark.parametrize('corrupt', ['sha', 'version', 'bytes', 'program', 'missing_ref', 'qa'])
def test_changed_selection_is_rejected(tmp_path, release, corrupt):
    from tests.path_start_release_source import load_release_reference
    path, value, ref = selected_fixture(tmp_path, release)
    if corrupt == 'sha': ref['sha256'] = '0' * 64
    if corrupt == 'version': ref['program']['version'] = 'wrong-version'
    if corrupt == 'bytes': path.write_text(path.read_text() + '\n')
    if corrupt == 'program': ref['program']['id'] = 99
    if corrupt == 'missing_ref': ref.pop('program')
    if corrupt == 'qa':
        value['cases'][0]['qa_evidence'][0]['evidence_json']['origin']['synthetic'] = True
        path.write_text(json.dumps(value)); ref['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='RELEASE_RECEIPT_'):
        load_release_reference(ref)


def test_stage_preserves_exact_bytes_and_survives_original_removal(tmp_path, release):
    from tests.path_start_release_source import load_release_reference, stage_release_receipt
    path, value, ref = selected_fixture(tmp_path, release)
    evidence = tmp_path / 'owned-evidence'; evidence.mkdir()
    staged = stage_release_receipt(ref, evidence)
    assert Path(staged['path']).read_bytes() == path.read_bytes()
    assert staged['sha256'] == ref['sha256'] and staged['program'] == ref['program']
    path.unlink()
    assert load_release_reference(staged)[0] == value
    with pytest.raises(FileExistsError):
        stage_release_receipt(staged, evidence)


def test_seed_bad_selection_stops_before_sql(tmp_path, release):
    from tests.path_start_release_inputs import seed_release
    _, _, ref = selected_fixture(tmp_path, release)
    ref['sha256'] = '0' * 64
    class NoSQL:
        def execute(self, *args, **kwargs):
            pytest.fail('must validate source before SQL')
    with pytest.raises(ValueError, match='SHA256_MISMATCH'):
        seed_release(NoSQL(), 1, receipt_reference=ref)


@pytest.mark.parametrize('future', [False, True])
def test_fresh_loader_cannot_import_config_database_or_provider(tmp_path, release, future):
    import os
    import subprocess
    import sys
    path, _, ref = selected_fixture(tmp_path, release, future=future)
    script = '''
import importlib.abc,sys
class NoInfrastructure(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname in ('Api.config','Api.database') or fullname.startswith('Api.llm'):
            raise AssertionError('SOURCE_SELECTION_IMPORTED_INFRASTRUCTURE')
sys.meta_path.insert(0, NoInfrastructure())
from tests.path_start_release_source import load_release_receipt
load_release_receipt(path=sys.argv[1],sha256=sys.argv[2],version=sys.argv[3])
print('PASS_PURE_SOURCE_SELECTION')
'''
    result = subprocess.run([sys.executable, '-c', script, str(path), ref['sha256'], ref['program']['version']],
        cwd=ROOT.parent, env={key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'PASS_PURE_SOURCE_SELECTION'
