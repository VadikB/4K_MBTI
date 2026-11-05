"""Real owned bootstrap/seed/cleanup; no LLM, real publication or human QA.

Future program metadata is an explicitly SYNTHETIC model in a disposable DB.
The original 27 published Case QA records are copied, not newly approved.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import pytest

from scripts.test_stand import ROOT, admin_params
from tests.path_start_release_source import DEFAULT_RECEIPT, load_release_receipt
from tests.unit.test_path_start_release_source import future_release_fixture

pytestmark = pytest.mark.integration


@pytest.fixture
def owned_release_stand(test_database_url, tmp_path):
    admin = os.getenv('STAND_ADMIN_URL')
    if not admin:
        pytest.skip('Explicit localhost maintenance STAND_ADMIN_URL is required')
    params = admin_params(admin)
    reference = conninfo_to_dict(test_database_url)
    assert all(str(params.get(k, '5432' if k == 'port' else ''))
               == str(reference.get(k, '5432' if k == 'port' else '')) for k in ('host', 'port', 'user'))
    state_path = tmp_path / 'state.json'
    env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
    env.update(STAND_ADMIN_URL=admin, PYTHONPATH=str(ROOT))
    audit = {'scope': 'FREE_OWNED_BOOTSTRAP_NOT_PATH_NOT_LLM_OR_PERSISTENT_PUBLICATION',
             'provider_calls': 0, 'status': 'NOT_COMPLETED'}

    def cli(action):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/test_stand.py'), action,
            '--state', str(state_path), '--gateway', '0', '--provider', 'disabled', '--port', '18879'],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr

    cli('create')
    try:
        state = json.loads(state_path.read_bytes())
        audit.update(run_id=state['run_id'], database=state['database'])
        assert state['database'] == 'product4k_pytest_' + state['run_id']
        cli('bootstrap')
        yield state_path, env, audit
        audit['status'] = 'ASSERTIONS_COMPLETED'
    finally:
        cli('destroy')
        audit['cleanup'] = json.loads((tmp_path / 'cleanup.json').read_bytes())
        assert all(audit['cleanup'][key] is True for key in ('owner_verified', 'database_absent', 'state_absent'))
        assert audit['cleanup']['force'] is False
        if directory := os.getenv('P4K_HARNESS_EVIDENCE_DIRECTORY'):
            directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
            (directory / (audit['run_id'] + '.json')).write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')


def run_seed(state_path, env, selected=None):
    env = {**env, 'P4K_FULL_PATH': '1', 'P4K_PROGRAM_SOURCE': 'published-pilot'}
    if selected is not None:
        env['P4K_PUBLISHED_RELEASE_REF'] = json.dumps(selected)
    return subprocess.run([sys.executable, str(ROOT / 'tests/path29_browser_inputs.py'),
        '--state', str(state_path)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)


@pytest.mark.parametrize('future', [False, True], ids=['legacy_1_1', 'synthetic_future_metadata'])
def test_exact_release_seed_minimal_sources_and_cleanup(owned_release_stand, tmp_path, future):
    state_path, env, audit = owned_release_stand
    source = json.loads(DEFAULT_RECEIPT.read_bytes())
    selected = None
    if future:
        source = future_release_fixture(source)
        source['program']['id'] = 3  # Test metadata only, no assigned persistent publication ID.
        path = tmp_path / 'synthetic-future-metadata.json'
        path.write_text(json.dumps(source, ensure_ascii=False, indent=2) + '\n')
        _, selected = load_release_receipt(path=path,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), version=source['program']['version'])
    seeded = run_seed(state_path, env, selected)
    assert seeded.returncode == 0, seeded.stdout + seeded.stderr
    state = json.loads(state_path.read_bytes())
    provenance = json.loads((tmp_path / 'source-provenance.json').read_bytes())
    assert provenance['release'] == source
    ref = state['path29']['published_release_ref']
    assert load_release_receipt(path=tmp_path / 'published-release-source.json', sha256=ref['sha256'],
                                version=source['program']['version'])[0] == source
    with psycopg.connect(**{**state['connection'], 'dbname': state['database']}, row_factory=dict_row) as c:
        counts = {name: c.execute('SELECT count(*) AS n FROM ' + table).fetchone()['n']
                  for name, table in {'users': 'users', 'organizations': 'organizations',
                      'memberships': 'organization_memberships', 'assignments': 'organization_assessment_assignments',
                      'profiles': 'assessment_personalized_profiles', 'cycles': 'm5_cycles'}.items()}
        assert counts == {'users': 1, 'organizations': 0, 'memberships': 0, 'assignments': 0, 'profiles': 0, 'cycles': 0}
        program = dict(c.execute('SELECT * FROM assessment_program_definitions WHERE id=%s',
                               (source['program']['id'],)).fetchone())
        assert all(program[key] == value for key, value in ref['program'].items())
        assert program['source_refs_json'] == source['program']['source_refs_json']
        qa_count = c.execute('''SELECT count(*) AS n FROM m5_qa_evidence qa
            JOIN m5_catalog_case_versions member ON member.case_version_id=qa.case_version_id
            WHERE member.catalog_db_id=%s''', (source['catalog']['id'],)).fetchone()['n']
        assert qa_count == 27
        for original in source['cases']:
            actual_qa = [dict(row) for row in c.execute('''SELECT scope,result,evidence_json,evidence_checksum
                FROM m5_qa_evidence WHERE case_version_id=%s ORDER BY scope,evidence_checksum''',
                (original['id'],)).fetchall()]
            assert actual_qa == original['qa_evidence']
        from tests.path_start_release_inputs import reserve_release_ids
        # Existing program IDs cannot be reused, even on our owned DB.
        from unittest.mock import patch
        with patch.dict(os.environ, {'AGENT4K_ISOLATED_STAND': '1'}):
            with pytest.raises(AssertionError, match='RELEASE_ID_ALREADY_OCCUPIED'):
                reserve_release_ids(c, 'assessment_program_definitions', source['program']['id'])
    audit.update(mode='SYNTHETIC_FUTURE_METADATA' if future else 'EXACT_EXISTING_1_1_SOURCE',
                 selected_program=ref['program'], source_receipt_sha256=ref['sha256'],
                 initial_counts=counts, original_case_qa_count=qa_count, original_case_qa_unchanged=True)


def test_changed_receipt_refused_before_seed_writes(owned_release_stand, tmp_path):
    state_path, env, audit = owned_release_stand
    _, selected = load_release_receipt()
    selected['sha256'] = '0' * 64
    seeded = run_seed(state_path, env, selected)
    assert seeded.returncode != 0 and 'RELEASE_RECEIPT_SHA256_MISMATCH' in seeded.stderr
    state = json.loads(state_path.read_bytes())
    with psycopg.connect(**{**state['connection'], 'dbname': state['database']}) as c:
        assert c.execute('SELECT count(*) FROM users').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM assessment_program_definitions').fetchone()[0] == 0
    audit.update(mode='NEGATIVE_CHANGED_SOURCE', rejected_before_seed=True, users=0, program_definitions=0)
