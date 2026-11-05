"""Offline evidence audit (stdlib only). PASS here never means PATH PASS."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
    return hashlib.sha256(data.encode()).hexdigest()


manifest = json.loads((HERE / 'MANIFEST.json').read_text())
for relative, expected in manifest['files'].items():
    assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative

run = json.loads((HERE / 'free-sql/run.json').read_text())
result = json.loads((HERE / 'free-sql/regression-result.json').read_text())
cleanup = json.loads((HERE / 'free-sql/cleanup.json').read_text())
proof = json.loads((HERE / 'free-sql/export-before-cleanup.json').read_text())
receipt_file = HERE / 'free-sql/plan-receipt.json'
receipt = json.loads(receipt_file.read_text())
for row in (result, cleanup):
    assert row['run_id'] == run['run_id'] and row['database'] == run['database']
assert run['database'] == 'product4k_pytest_' + run['run_id']
assert run['sha'] == manifest['implementation_sha']
assert result['result'] == 'PASS_FREE_DIAGNOSTICS_NOT_PATH' and result['pytest_exit_code'] == 0
assert run['llm_calls'] == result['llm_calls'] == proof['llm_calls'] == 0
assert run['provider_mode'] == result['provider_mode'] == 'disabled'
assert all(cleanup[key] is True for key in ('owner_verified', 'database_absent', 'state_absent'))
assert cleanup['force'] is False and result['receipt_unchanged_after_cleanup'] is True
assert proof['phase'] == 'DURABLE_RECEIPT_READ_WHILE_OWNED_DB_EXISTS'
assert hashlib.sha256(receipt_file.read_bytes()).hexdigest() == proof['receipt_sha256'] == result['receipt_sha256']
assert receipt['status'] == receipt['diagnostics']['status'] == 'LIMITED' and receipt['revision_no'] == 2
assert receipt['content_checksum_matches'] is True and receipt['status_matches_revision'] is True
assert receipt['content_checksum'] == receipt['content_recomputed_checksum']
assert digest(receipt['diagnostics']) == receipt['diagnostics_checksum']
assert receipt['diagnostics']['uncovered_target_ids']
assert any(item['reasons'] for item in receipt['diagnostics']['catalog'])
assert '43 passed' in (HERE / 'free-sql/pytest.log').read_text()

# The old primary receipt is unchanged, not retroactively repaired/reclassified.
historical = json.loads((ROOT / 'docs/evc/evidence/path-start-2dc98c6-run/run/source-to-runtime-receipt.json').read_text())
assert historical['plan']['status'] == 'LIMITED'
assert historical['functional_generation']['admission_status'] == 'PASS'
assert historical['assessment_answers'] == 0 and historical['cycle']['started_at'] is None
assert historical['assessment_situation']['started_at'] is None
assert 'diagnostics' not in historical['plan']
print(json.dumps({'result': 'PASS_OFFLINE_DIAGNOSTICS_AUDIT_NOT_PATH',
    'verified_files': len(manifest['files']), 'implementation_sha': run['sha'],
    'sql_regressions': 43, 'new_llm_calls': 0, 'owned_cleanup': 'PASS',
    'historical_path': 'FAIL_PLAN_NOT_READY', 'historical_full_plan': 'UNKNOWN_NOT_EXPORTED'}, indent=2))
