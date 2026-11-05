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
