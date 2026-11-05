"""Export this finished run, safe log projection and read-only cleanup proof."""
from argparse import Namespace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

D = Path('/home/vadim_bogachev/evidence/path-pilot-1.2-run-qxzr56r9')
DEPLOY = Path('/home/vadim_bogachev/projects/Agent4K-Test')
SHA = 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
digest = lambda data: hashlib.sha256(data).hexdigest()
canonical = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()


def save(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    assert path.read_bytes() == data


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


prepared = json.loads((D / 'prepared.json').read_bytes())
checkout = Path(prepared['checkout'])
assert json.loads((D / 'controller-result.json').read_bytes())['exit_code'] == 0
env = {key: os.environ[key] for key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR') if key in os.environ}
env.update(PYTHONPATH=str(checkout), PYTHONDONTWRITEBYTECODE='1', DB_POOL_MIN_SIZE='0')
normalized = subprocess.run([str(DEPLOY / '.venv/bin/python'), 'scripts/assessment_first_case.py',
    '--summarize-only', '--directory', str(D / 'run')], cwd=checkout, env=env,
    capture_output=True, text=True, timeout=60)
assert normalized.returncode == 0
summary = json.loads((D / 'run/runner-result.normalized.json').read_bytes())
assert summary['result'] == 'PASS' and len(summary['runs']) == 1
run = summary['runs'][0]
assert run['result'] == 'PASS' and not run['validation_errors']
run_id = run['run']['run_id']; database = run['run']['database']
assert database == 'product4k_pytest_' + run_id
run_dir = next((D / 'run').glob('*/run.json')).parent
assert not (run_dir / 'state.json').exists() and not (run_dir / 'cleanup-deferred.json').exists()
before = json.loads((run_dir / 'source-to-runtime-receipt.json').read_bytes())
after = json.loads((run_dir / 'first-case-receipt.json').read_bytes())
generated = after['functional_generation']; calls = generated['calls']
assert generated['admitted_for_participant'] is True and generated['admission_status'] in ('PASS', 'PASS_WITH_WARNINGS')
assert after['http_start_status'] == 201 and after['assessment_answers'] == 0
diagnostics = before['plan']['diagnostics']
assert len(diagnostics['full_target_set']) == 61 and len(diagnostics['planned_target_set']) == 39
assert len(diagnostics['outside_plan_target_ids']) == 22 and diagnostics['uncovered_planned_target_ids'] == []
assert len(calls) == len({call['operation_id'] for call in calls})
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=checkout, text=True).strip() == SHA
post_status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=checkout, text=True)
assert not post_status.strip()

# Maintenance SELECT only: no reconnect to/drop of any application database.
sys.path.insert(0, str(DEPLOY)); os.chdir(DEPLOY)
import psycopg
from psycopg.rows import dict_row
from dotenv import dotenv_values
from psycopg.conninfo import make_conninfo
from scripts.test_stand import admin_params
values = dotenv_values(DEPLOY / '.env')
params = admin_params(make_conninfo(host='127.0.0.1', port=55432, dbname='postgres',
    user=values['DB_USER'], password=values['DB_PASSWORD']))
with psycopg.connect(**params, options='-c default_transaction_read_only=on -c statement_timeout=10000') as c:
    assert c.execute('SELECT count(*) FROM pg_database WHERE datname=%s', (database,)).fetchone()[0] == 0
    active = c.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s', (database,)).fetchone()[0]
    assert active == 0; c.rollback()
save(D / 'cleanup-readback.json', {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
    'run_id': run_id, 'database': database, 'database_absent': True, 'state_absent': True,
    'active_connections': active, 'marker_verified_by_existing_destroy': run['cleanup']['owner_verified'],
    'force': False, 'maintenance_read_only': True, 'working_database_cleanup': False})

from Api.config import settings
from tests.path_start_release_source import collect
with psycopg.connect(host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
        user=settings.db_user, password=settings.db_password, connect_timeout=10, row_factory=dict_row,
        options='-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000') as c:
    c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    live = collect(c, program_version='1.2')
    connections = c.execute('SELECT count(*) AS n FROM organization_assessment_program_connections WHERE program_definition_id=2').fetchone()['n']
    c.rollback()
source = json.loads(Path(prepared['selected']['path']).read_bytes())
assert canonical(live) == canonical(source) and connections == 0
schema_dir = DEPLOY / 'docs/evc/evidence/path-pilot-schema-readback'
reader = module('finished_path_schema', schema_dir / 'READ_SCHEMA.py')
schema = reader.collect(Namespace(env_file=DEPLOY / '.env', stand_state=None, checkout=DEPLOY))
previous = json.loads((D / 'live-preflight.json').read_bytes())
assert schema['metadata_checksum'] == previous['schema_comparison']['actual_metadata_checksum']
save(D / 'working-readback.json', {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
    'runtime_sha': SHA, 'read_only': True, 'rollback': True, 'same_published_source': True,
    'published_source_canonical_sha256': digest(canonical(live)), 'target_program_connections': connections,
    'schema_metadata_checksum': schema['metadata_checksum'], 'schema_unchanged': True,
    'writes_by_this_operation': False})

# Preserve original JSON/PNG bytes. Export only a declared safe server-log view.
files = {}
for path in sorted(D.rglob('*')):
    if path.is_file() and path.suffix in ('.json', '.png') and path.name != 'state.json':
        files[str(path.relative_to(D))] = path.read_bytes()
original_log = (run_dir / 'server.log').read_bytes()
safe_lines = []
for line in original_log.decode(errors='replace').splitlines():
    match = re.search(r'DeepSeek request completed duration_ms=([0-9.]+)[^\n]*routing_key=([a-f0-9-]{36}:[a-zA-Z0-9:_-]+)', line)
    if match:
        safe_lines.append('DeepSeek request completed duration_ms=' + match[1] + ' routing_key=' + match[2])
assert len(safe_lines) == run['provider_completed_requests'] == 21
safe_log = ('\n'.join(safe_lines) + '\n').encode()
relative_run = str(run_dir.relative_to(D))
files[relative_run + '/server.log'] = safe_log
redaction = {'contract': 'provider-completion-log-projection/1',
    'original_remote_path': str(run_dir / 'server.log'), 'original_sha256': digest(original_log),
    'original_bytes': len(original_log), 'export_sha256': digest(safe_log),
    'allowed_fields': ['duration_ms', 'routing_key'], 'provider_completed_requests': len(safe_lines),
    'raw_log_exported': False, 'scope': 'Sanitized copy; original remote log unchanged'}
files['server-log-export.json'] = (json.dumps(redaction, indent=2) + '\n').encode()
outcome = {'result': 'PASS', 'runtime_sha': SHA, 'app_version': '2.0.66',
    'run_id': run_id, 'program': prepared['selected']['program'],
    'preparation_operation_id': after['preparation_operation']['operation_id'],
    'cycle_id': after['cycle']['cycle_id'], 'assessment_situation': after['assessment_situation'],
    'http_start_status': after['http_start_status'], 'assessment_answers': after['assessment_answers'],
    'admission_status': generated['admission_status'], 'admitted_for_participant': True,
    'repair_used': generated['repair_used'], 'stages': generated['stages'],
    'unique_provider_operations': len(calls), 'provider_completed_http_requests': len(safe_lines),
    'json_retry_completions': sum(':json-retry' in line for line in safe_lines),
    'retained_operation_usage': generated['usage'],
    'usage_limitation': 'Earlier malformed JSON response usage not retained; these tokens are not the full billed total.',
    'plan_status': before['plan']['status'], 'full_m2': 61, 'planned_targets': 39, 'outside_plan_targets': 22,
    'route': [item['case_id'] for item in diagnostics['route']],
    'time_budget_seconds': after['cycle']['time_budget_seconds'],
    'calendar_window_seconds': after['cycle']['calendar_window_seconds'],
    'pre_start_readiness': before['start_readiness'], 'presented_as': after['presented_as'],
    'candidate_checksum': generated['candidate_checksum'], 'snapshot_checksum': after['assessment_situation']['snapshot_checksum'],
    'clean_checkout_before_and_after': True, 'owned_cleanup_verified': True,
    'working_source_schema_connections_unchanged': True, 'paid_runner_invocations': 1,
    'PREP_DIAG_01_root_cause': 'UNKNOWN'}
files['outcome.json'] = (json.dumps(outcome, ensure_ascii=False, indent=2) + '\n').encode()
manifest = {'contract': 'pilot12-paid-path-primary-evidence/1', 'files': [
    {'path': name, 'bytes': len(data), 'sha256': digest(data)} for name, data in sorted(files.items())]}
files['MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
archive = D / 'path-evidence.zip'
with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for name, data in sorted(files.items()): z.writestr(name, data)
print(json.dumps({'result': 'PASS', 'run_id': run_id, 'admission_status': generated['admission_status'],
    'as_id': after['assessment_situation']['assessment_situation_id'], 'unique_provider_operations': len(calls),
    'provider_completed_http_requests': len(safe_lines), 'usage': generated['usage'],
    'archive': str(archive), 'archive_bytes': archive.stat().st_size,
    'archive_sha256': digest(archive.read_bytes()), 'files': len(manifest['files'])}))
