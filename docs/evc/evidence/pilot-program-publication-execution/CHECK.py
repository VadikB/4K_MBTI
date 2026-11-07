"""Независимая offline проверка сохранённой публикации, без DB/.env/LLM."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

if not __debug__:
    raise RuntimeError('PUBLICATION_EVIDENCE_REQUIRES_ASSERTIONS')
ROOT = Path(__file__).resolve().parents[4]
os.environ.clear()
os.environ.update(AGENT4K_ISOLATED_STAND='1', AGENT4K_STAND_MARKER='stand-10.2:publication-offline',
    DB_HOST='127.0.0.1', DB_NAME='product4k_pytest_publication_offline', DB_USER='offline', DB_POOL_MIN_SIZE='0')
attempts = []


class NoSocket(socket.socket):
    def __new__(cls, *args, **kwargs):
        attempts.append(True)
        raise AssertionError('OFFLINE_NETWORK_FORBIDDEN')


socket.socket = NoSocket
sys.path.insert(0, str(ROOT))
from tests.path_start_release_source import load_release_receipt
from Api.pilot_plan_admission import build_snapshot, validate_program


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), default=str).encode()).hexdigest()


def check(directory):
    def read(name):
        return json.loads((directory / name).read_bytes())

    remote = read('remote-execution.json')
    assert remote['exit_code'] == 0 and remote['stdout']['result'] == 'PUBLISHED_READBACK_VERIFIED'
    assert sha(directory / 'EXECUTE_APPROVED.py') == remote['driver_sha256']
    for item in remote['stdout']['files']:
        path = directory / item['name']
        assert path.name == item['name'] and path.parent == directory
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
    result = read('publication-result.json')
    assert result['contract'] == 'pilot-program-publication/1'
    assert result['result'] == 'PUBLISHED_READBACK_VERIFIED'
    assert result['runtime_sha'] == 'e63eba67d77fb73f7fb9bb219bc3fe5d3807a909'
    assert result['application_version'] == '2.0.66'
    assert result['publisher_invocations'] == 1 and result['provider_calls_by_operation'] == 0
    assert result['retirement_performed'] is result['activation_performed'] is result['path_performed'] is False
    assert result['PREP_DIAG_01_root_cause'] == 'UNKNOWN'
    selector = result['source_ref']
    source, selected = load_release_receipt(path=directory / 'published-release-source.json',
        sha256=selector['sha256'], version='1.2')
    assert selector['sha256'] == '09892e3882380d530e42142f4128884a2771861907c4c0c414e0f143e1fbe10b'
    assert selector['program'] == selected['program']
    assert source['source_code_sha'] == result['runtime_sha']
    assert source['target']['database'] == 'agent4k_test' and source['target']['read_only'] is True
    assert source['contains_user_history'] is source['new_methodology_approval'] is False
    program = source['program']
    assert program['id'] == 2 and program['version'] == '1.2' and program['status'] == 'published'
    assert program['definition_checksum'] == 'b4e8270fd10436c417d7b40b8be8049dc2e9329f42a1ffa6d725877480d04718'
    assert result['program'] == {key: program[key] for key in result['program']}
    assert result['publisher_user_id'] == 4 and result['allowed_role_profile_version_ids'] == [2]
    assert program['published_at'] is not None
    snapshot = program['source_refs_json']['pilot_plan_admission']
    assert snapshot == build_snapshot(ROOT / 'assessment_definitions/planning/specialist_pilot_admission/v0.1')
    assert snapshot['snapshot_checksum'] == result['snapshot_checksum'] == 'daa715b153f16e9ebc4ea6744a1c8541c5e269e248bba4b5c37723571e6ccfce'
    design = validate_program(program, [2], snapshot)
    assert len(design['full_m2_matrix']) == 61 and len(design['proposed_target_ids']) == 39
    assert len(design['observation_occurrences']) == 55
    baseline = json.loads((ROOT / 'tests/browser/fixtures/path-start-release.json').read_bytes())
    before = read('prepublication.json')
    assert before['result'] == 'FRESH_PREFLIGHT_PASS' and before['version_1_2_free'] is True
    assert before['tracked_clean'] and before['transaction_read_only'] and before['transaction_rolled_back']
    assert before['publisher'] == {'id': 4, 'configured_superadmin': True, 'not_suppressed': True}
    for key, expected in before['source_hashes'].items():
        assert object_sha(baseline[key]) == expected
        if key != 'program':
            assert object_sha(source[key]) == expected
    for key in ('preserved_legacy_1_1', 'other_program_rows_unchanged',
                'other_allowed_role_rows_unchanged', 'org_connections_unchanged', 'schema_unchanged'):
        assert result[key] is True
    assert result['new_program_org_connections'] == 0
    assert before['schema_comparison']['actual_metadata_checksum'] == result['schema_metadata_checksum']
    assert before['schema_comparison']['result'] == 'EXACT_SCOPED_SCHEMA_MATCH'
    invocation = read('publisher-invocation.json')
    assert invocation['exit_code'] == 0 and not invocation['timed_out']
    assert invocation['invocations'] == 1 and invocation['retry'] is False
    assert invocation['argv'][-1] == '--publish'
    decision = read('owner-decision.json')
    assert decision['decision'] == 'OWNER_APPROVED_CONDITIONAL_PUBLICATION'
    assert decision['program']['version'] == '1.2' and decision['program']['publisher_user_id'] == 4
    regression = read('retirement-regression.json')
    assert regression['test_counts']['total_passed'] == 29 and regression['exit_code'] == 0
    assert regression['provider_calls'] == 0 and regression['permanent_database_touched'] is False
    assert regression['ownership_before_cleanup']['owner_verified'] is True
    cleanup = read('cleanup.json')
    assert cleanup['run_id'] == regression['ownership_before_cleanup']['run_id']
    assert cleanup['owner_verified'] and cleanup['database_absent'] and cleanup['state_absent']
    assert cleanup['remaining_owned_databases'] == cleanup['remaining_owned_connections'] == 0
    assert cleanup['container_auto_removed'] and cleanup['permanent_database_touched'] is False
    assert cleanup['force'] is False
    assert not attempts
    assert not any(key in sys.modules for key in ('Api.config', 'Api.database', 'Api.llm'))
    return {'result': 'PASS_OFFLINE_PUBLISHED_RECEIPT', 'program_id': 2, 'program_version': '1.2',
        'receipt_sha256': selected['sha256'], 'source_objects_preserved': 5,
        'cases': len(source['cases']), 'original_qa': sum(len(c['qa_evidence']) for c in source['cases']),
        'recomputed_artifacts': len(source['artifact_readback']), 'socket_attempts': 0,
        'db_connections': 0, 'provider_calls': 0, 'path_result': 'NOT_RUN_NOT_AUTHORIZED'}


if __name__ == '__main__':
    print(json.dumps(check(Path(__file__).parent), ensure_ascii=False))
