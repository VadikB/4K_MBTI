"""Однократная операция PATH-PILOT-PROGRAM-01, не runtime/API и не retire tool.

Передаётся через SSH stdin на неизменённый test checkout. Запись в БД выполняет
только существующий publisher, один раз, после всех read-only gates. Повторный
запуск после публикации остановится на занятой версии; retry/cleanup/retire нет.
"""
from argparse import Namespace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path('/home/vadim_bogachev/projects/Agent4K-Test')
SHA = 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
CHECKSUM = 'b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718'
SNAPSHOT = 'daa715b153f16e9ebc4ea6744a1c8541c5e269e248bba4b5c37723571e6ccfce'
BASELINE_SHA = 'a3175dda9675c476ae8636d26449e5ed17e0ef7940ea0412b7431882933ae1e6'
KEYS = ('program', 'configuration', 'catalog', 'roles', 'cases', 'artifact_readback')


def require(ok, code):
    if not ok:
        raise RuntimeError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), default=str).encode()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def save(directory, name, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n').encode()
    target = directory / name
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    require(target.read_bytes() == data, 'EVIDENCE_READBACK_MISMATCH')
    return {'name': name, 'path': str(target), 'bytes': len(data), 'sha256': digest(data)}


def main():
    require(sys.argv[1:] == ['--execute-approved-publication'], 'EXPLICIT_EXECUTION_REQUIRED')
    require(__debug__, 'ASSERTIONS_REQUIRED_BY_EXISTING_SOURCE_VALIDATOR')
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    evidence_root = Path('/home/vadim_bogachev/evidence')
    evidence_root.mkdir(mode=0o700, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='pilot-program-1.2-', dir=evidence_root))
    files = []
    stage = 'read_only_preflight'
    invoked = False
    try:
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        require(head == SHA, 'RUNTIME_SHA_DRIFT')
        tracked = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], text=True)
        require(not tracked.strip(), 'RUNTIME_TRACKED_DIRTY')
        import tomllib
        version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
        require(version == '2.0.66', 'APPLICATION_VERSION_DRIFT')
        schema_dir = ROOT / 'docs/evc/evidence/path-pilot-schema-readback'
        schema_reader = module('publication_schema_reader', schema_dir / 'READ_SCHEMA.py')
        schema_compare = module('publication_schema_compare', schema_dir / 'COMPARE.py')
        expected = json.loads((schema_dir / 'expected-schema.json').read_bytes())
        actual = schema_reader.collect(Namespace(env_file=ROOT / '.env', stand_state=None, checkout=ROOT))
        comparison = schema_compare.compare(expected, actual)
        require(comparison['result'] == 'EXACT_SCOPED_SCHEMA_MATCH', 'SCHEMA_DRIFT')
        import psycopg
        from psycopg.rows import dict_row
        from Api.config import settings
        from Api.org_access import configured_superadmin_emails
        from Api.pilot_plan_admission import build_snapshot, validate_program
        from Api.assessment_programs import definition_checksum
        from tests.path_start_release_source import collect, load_release_receipt
        require(settings.db_name == 'agent4k_test', 'WRONG_DATABASE')
        params = dict(host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
                      user=settings.db_user, password=settings.db_password, connect_timeout=10,
                      options='-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000')

        def read_source(version):
            with psycopg.connect(**params, row_factory=dict_row) as c:
                c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
                result = collect(c, program_version=version)
                programs = c.execute('SELECT * FROM assessment_program_definitions ORDER BY id').fetchall()
                roles = c.execute('SELECT * FROM assessment_program_allowed_roles ORDER BY program_definition_id,display_order,role_profile_version_id').fetchall()
                connections = c.execute('SELECT * FROM organization_assessment_program_connections ORDER BY id').fetchall()
                publisher = c.execute("""SELECT u.id,
                    (LOWER(TRIM(u.email))=ANY(%s)) AS configured_superadmin,
                    NOT EXISTS(SELECT 1 FROM configured_access_suppressions s
                      WHERE LOWER(s.email)=LOWER(TRIM(u.email))
                      AND s.access_kind='superadmin' AND s.organization_code='') AS not_suppressed
                    FROM users u WHERE u.id=4""", (sorted(configured_superadmin_emails()),)).fetchone()
                resolved = c.execute("""SELECT v.id,v.version,v.checksum FROM assessment_role_profile_versions v
                    JOIN assessment_role_profiles r ON r.id=v.role_profile_id
                    WHERE r.code='specialist_expert' AND v.status='published'
                    ORDER BY v.version DESC LIMIT 1""").fetchone()
                read_only = c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']
                c.rollback()
            return result, programs, roles, connections, publisher, resolved, read_only

        baseline_file = ROOT / 'tests/browser/fixtures/path-start-release.json'
        require(digest(baseline_file.read_bytes()) == BASELINE_SHA, 'HISTORICAL_RECEIPT_DRIFT')
        baseline = json.loads(baseline_file.read_bytes())
        old, programs, roles, connections, publisher, resolved, read_only = read_source('1.1')
        require(read_only == 'on', 'READ_ONLY_REQUIRED')
        require(all(canonical(old[k]) == canonical(baseline[k]) for k in KEYS), 'PUBLISHED_SOURCE_DRIFT')
        require(publisher == {'id': 4, 'configured_superadmin': True, 'not_suppressed': True}, 'PUBLISHER_SCOPE_DRIFT')
        require(resolved['id'] == 2 and resolved['checksum'] == baseline['roles'][0]['checksum'], 'LATEST_ROLE_DRIFT')
        require(not any(p['code'] == 'specialist_pilot' and p['version'] == '1.2' for p in programs), 'VERSION_OCCUPIED_NO_RETRY')
        recipe = json.loads((ROOT / 'docs/evc/evidence/pilot-program-release-plan/program-1.2.proposed.json').read_bytes())
        snapshot = build_snapshot(ROOT / recipe['pilot_plan_snapshot_build']['package'])
        require(snapshot['snapshot_checksum'] == SNAPSHOT, 'ACCEPTED_SNAPSHOT_DRIFT')
        candidate = dict(recipe['program_fields'])
        candidate['source_refs_json'] = {**recipe['source_refs_without_pilot_plan_admission'], 'pilot_plan_admission': snapshot}
        design = validate_program(candidate, [2], snapshot)
        checksum = definition_checksum(code=candidate['code'], version=candidate['version'], name=candidate['name'],
            assignment_ref=candidate['assignment_ref'], mode=candidate['mode'],
            configuration_id=candidate['assessment_configuration_id'], catalog_version_id=candidate['catalog_version_id'],
            role_version_ids=[2], source_refs=candidate['source_refs_json'])
        require(checksum == CHECKSUM == recipe['definition_checksum_when_materialized'], 'CANDIDATE_DRIFT')
        require(len(design['full_m2_matrix']) == 61, 'FULL_M2_DRIFT')
        files.append(save(directory, 'prepublication.json', {
            'result': 'FRESH_PREFLIGHT_PASS', 'observed_at_utc': datetime.now(timezone.utc).isoformat(),
            'runtime_sha': head, 'application_version': version, 'tracked_clean': True,
            'schema_comparison': comparison, 'transaction_read_only': True, 'transaction_rolled_back': True,
            'source_hashes': {k: digest(canonical(old[k])) for k in KEYS},
            'publisher': publisher, 'resolved_role': resolved, 'version_1_2_free': True,
            'candidate_checksum': checksum, 'snapshot_checksum': SNAPSHOT,
            'all_program_rows_before_sha256': digest(canonical(programs)),
            'all_allowed_roles_before_sha256': digest(canonical(roles)),
            'org_connections_before_sha256': digest(canonical(connections)),
            'publication_performed': False, 'provider_calls': 0}))
        stage = 'existing_publisher_once'
        argv = ['.venv/bin/python', 'scripts/publish_assessment_program.py', '--code', 'specialist_pilot',
            '--version', '1.2', '--name', candidate['name'], '--assignment-ref', 'specialist-pilot',
            '--mode', 'dialogue', '--configuration-code', 'specialist_pilot_v1', '--role-code', 'specialist_expert',
            '--publisher-user-id', '4', '--pilot-plan-package', recipe['pilot_plan_snapshot_build']['package'], '--publish']
        invoked = True
        try:
            process = subprocess.run(argv, cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT), 'DB_POOL_MIN_SIZE': '0'},
                                     capture_output=True, text=True, timeout=45)
            invocation = {'exit_code': process.returncode, 'timed_out': False,
                          'stdout_sha256': digest(process.stdout.encode()), 'stderr_sha256': digest(process.stderr.encode())}
        except subprocess.TimeoutExpired:
            invocation = {'exit_code': None, 'timed_out': True, 'details_redacted': True}
        files.append(save(directory, 'publisher-invocation.json', {'argv': argv, **invocation, 'invocations': 1, 'retry': False}))
        stage = 'post_publication_readback'
        new, after_programs, after_roles, after_connections, after_publisher, _, after_ro = read_source('1.2')
        program = new['program']
        program_id = program['id']
        files.append(save(directory, 'published-release-source.json', new))
        require(program['definition_checksum'] == CHECKSUM and program['published_at'] is not None, 'PUBLISHED_DEFINITION_MISMATCH')
        require(program['source_refs_json']['pilot_plan_admission']['snapshot_checksum'] == SNAPSHOT, 'PUBLISHED_SNAPSHOT_MISMATCH')
        require(all(canonical(new[k]) == canonical(old[k]) for k in KEYS if k != 'program'), 'SOURCE_CHANGED_DURING_PUBLICATION')
        persisted = next(p for p in after_programs if p['id'] == program_id)
        require(persisted['published_by_user_id'] == 4 and persisted['status'] == 'published', 'PUBLISHER_OR_STATUS_MISMATCH')
        require(canonical([p for p in after_programs if p['id'] != program_id]) == canonical(programs), 'OTHER_PROGRAM_MUTATED')
        added_roles = [r for r in after_roles if r['program_definition_id'] == program_id]
        require(len(added_roles) == 1 and added_roles[0]['role_profile_version_id'] == 2 and added_roles[0]['display_order'] == 0, 'NEW_ROLE_LINK_MISMATCH')
        require(canonical([r for r in after_roles if r['program_definition_id'] != program_id]) == canonical(roles), 'OTHER_ROLES_MUTATED')
        require(canonical(after_connections) == canonical(connections), 'ORG_CONNECTIONS_CHANGED')
        require(not any(r['program_definition_id'] == program_id for r in after_connections), 'NEW_PROGRAM_CONNECTED')
        require(after_publisher == publisher and after_ro == 'on', 'POST_READBACK_SCOPE_DRIFT')
        source_file = next(f for f in files if f['name'] == 'published-release-source.json')
        _, reference = load_release_receipt(path=source_file['path'], sha256=source_file['sha256'], version='1.2')
        post_schema = schema_reader.collect(Namespace(env_file=ROOT / '.env', stand_state=None, checkout=ROOT))
        require(post_schema['metadata_checksum'] == actual['metadata_checksum'], 'POST_SCHEMA_DRIFT')
        require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == SHA, 'POST_RUNTIME_DRIFT')
        require(invocation['exit_code'] == 0 and not invocation['timed_out'], 'PUBLISHER_EXIT_REQUIRES_RECONCILIATION_NO_RETRY')
        result = {'contract': 'pilot-program-publication/1', 'result': 'PUBLISHED_READBACK_VERIFIED',
            'observed_at_utc': datetime.now(timezone.utc).isoformat(), 'runtime_sha': SHA, 'application_version': version,
            'program': {k: program[k] for k in ('id', 'code', 'version', 'status', 'definition_checksum', 'published_at', 'assessment_configuration_id', 'catalog_version_id')},
            'publisher_user_id': 4, 'allowed_role_profile_version_ids': [2], 'snapshot_checksum': SNAPSHOT,
            'source_ref': reference, 'preserved_legacy_1_1': True, 'unchanged_source_objects': list(KEYS[1:]),
            'other_program_rows_unchanged': True, 'other_allowed_role_rows_unchanged': True,
            'org_connections_unchanged': True, 'new_program_org_connections': 0,
            'schema_metadata_checksum': post_schema['metadata_checksum'], 'schema_unchanged': True,
            'publisher_invocations': 1, 'provider_calls_by_operation': 0, 'retirement_performed': False,
            'activation_performed': False, 'path_performed': False, 'PREP_DIAG_01_root_cause': 'UNKNOWN',
            'files': list(files)}
        files.append(save(directory, 'publication-result.json', result))
        print(json.dumps({'result': result['result'], 'directory': str(directory), 'program': result['program'], 'files': files}, default=str))
    except Exception as exc:
        failure = {'result': 'STOP_NO_RETRY_NO_AUTOMATIC_RETIREMENT', 'stage': stage,
            'exception_type': type(exc).__name__, 'safe_reason': str(exc) if isinstance(exc, RuntimeError) else 'DETAILS_REDACTED',
            'publisher_invoked': invoked, 'publication_outcome': 'REQUIRES_READBACK' if invoked else 'NOT_INVOKED',
            'files': list(files)}
        files.append(save(directory, 'failure.json', failure))
        print(json.dumps({'result': failure['result'], 'directory': str(directory), 'stage': stage, 'files': files}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
