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


@pytest.mark.parametrize('mutation', [
    lambda s: s['program'].update(version='1.2'),
    lambda s: s['configuration'].update(catalog_version_id=99),
    lambda s: s['program']['source_refs_json'].update(prompt_bundle_checksum='0' * 64),
    lambda s: s['cases'].pop(),
    lambda s: s['cases'][0]['qa_evidence'].pop(),
    lambda s: s['cases'][0]['qa_evidence'][0]['evidence_json']['origin'].update(synthetic=True),
    lambda s: s['cases'][0]['admission'].update(admitted=False),
    lambda s: s['cases'][0].update(content_checksum='0' * 64),
])
def test_changed_or_synthetic_source_is_rejected(release, mutation):
    changed = copy.deepcopy(release)
    mutation(changed)
    with pytest.raises(AssertionError):
        validate_release(changed)
