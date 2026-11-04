"""Owned PostgreSQL -> actual collector -> durable file -> cleanup; no LLM.

This deliberately inserts one synthetic negative operation. It tests diagnostics,
not the product's generation, admission, start, or the cause of PREP-DIAG-01.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def collect_fixture(state_path):
    from scripts.test_stand import owned
    state = json.loads(state_path.read_text())
    with owned(state):
        pass
    from Api.database import get_connection
    from Api.llm.deepseek_gateway import DeepSeekGateway
    from Api.m5_functional_generation_service import checksum
    assert not DeepSeekGateway().enabled, 'EXPORT_REGRESSION_MUST_HAVE_NO_PROVIDER_KEYS'
    operation_id = str(uuid4())
    candidate = {'CaseID': 'CASE.SPEC.02', 'CaseVersion': 'v0.6', 'synthetic': True}
    incomplete = [
        {'check_id': 'common.authority', 'status': 'NOT_RUN',
         'reason': 'Tester не вернул обязательный результат.', 'evidence_paths': []},
        {'check_id': 'indicator:K1.I06', 'status': 'TECHNICAL_ERROR',
         'reason': 'PASS защищённой проверки без adversarial review не допускается.',
         'evidence_paths': ['/IndicatorObservability/0']},
        {'check_id': 'case02.attractive_feature', 'status': 'INDETERMINATE',
         'reason': 'Синтетическая проверка не определена; требуется последующий разбор.',
         'evidence_paths': []},
    ]
    generation = {'operation_id': operation_id + ':generation:fixture', 'kind': 'generation',
        'input_checksum': checksum({'regression': 'no-llm'}),
        'sent': {'provider': 'fixture', 'messages': ['DO_NOT_EXPORT_SYNTHETIC_RAW_PROMPT'],
                 'api_key': 'DO_NOT_EXPORT_SYNTHETIC_KEY'}, 'provider': {'usage': {}}}
    generated = {'candidate_as': candidate, 'candidate_checksum': checksum(candidate),
        'input_snapshot_checksum': checksum({'operation_id': operation_id, 'case_id': 'CASE.SPEC.02'}),
        'generation_operation': generation, 'admitted_for_participant': False,
        'tester': {'aggregation': {'status': 'INCOMPLETE', 'incomplete_checks': incomplete,
            'blocking_failures': [], 'deterministic_failures': []}},
        'raw_response': 'DO_NOT_EXPORT_SYNTHETIC_RAW_RESPONSE'}
    with get_connection() as connection:
        user = connection.execute("""INSERT INTO users(full_name,email)
            VALUES('Синтетический участник регрессии выгрузки','path29-new@example.test') RETURNING id""").fetchone()
        connection.execute('''INSERT INTO product_cycle_preparation_operations
            (operation_id,user_id,request_json,request_checksum,status,attempts,result_json,error_code,error_message)
            VALUES(%s,%s,'{}'::jsonb,%s,'failed',1,%s::jsonb,'ValueError',
                'M5_FUNCTIONAL_AS_NOT_ADMITTED:INCOMPLETE')''',
            (operation_id, user['id'], checksum({}), json.dumps({'generated': generated}, ensure_ascii=False)))
        connection.commit()

    # The same handler as the real owned HTTP harness; no worker or HTTP mutation runs.
    from tests.path29_browser_app import path_receipt
    receipt = path_receipt()
    functional = receipt['functional_generation']
    assert functional['incomplete_checks'] == [{**item, 'aggregation_error': None} for item in incomplete]
    assert functional['candidate_checksum'] == functional['candidate_recomputed_checksum'] == checksum(candidate)
    assert functional['candidate_ref'] == {'case_id': 'CASE.SPEC.02', 'case_version': 'v0.6',
                                         'checksum': checksum(candidate)}
    assert functional['input_snapshot_checksum'] == generated['input_snapshot_checksum']
    assert functional['final_generation_operation_id'].startswith(receipt['preparation_operation']['operation_id'] + ':')
    assert receipt['assessment_situation'] is None and receipt['assessment_answers'] == 0
    assert 'DO_NOT_EXPORT' not in json.dumps(receipt)
    result = subprocess.run(['node', str(ROOT / 'tests/browser/fixtures/receipt-file.mjs'),
        str(state_path.parent / 'export-receipt.json')],
        input=json.dumps(receipt, ensure_ascii=False), text=True, capture_output=True, check=True)
    digest = json.loads(result.stdout)['sha256']
    assert digest == hashlib.sha256((state_path.parent / 'export-receipt.json').read_bytes()).hexdigest()
    assert json.loads((state_path.parent / 'export-receipt.json').read_text()) == receipt
    (state_path.parent / 'export-before-cleanup.json').write_text(json.dumps({
        'scope': 'synthetic_negative_export_fixture', 'llm_calls': 0,
        'operation_id': operation_id, 'candidate_checksum': checksum(candidate),
        'receipt_sha256': digest, 'check_count': len(incomplete),
        'check_ids': [item['check_id'] for item in incomplete],
        'statuses': [item['status'] for item in incomplete],
        'safe_reasons_preserved': True, 'raw_prompts_responses_keys_excluded': True,
        'phase': 'RECEIPT_PERSISTED_WHILE_DATABASE_EXISTS',
    }, ensure_ascii=False, indent=2) + '\n')


def run(directory):
    from scripts.test_stand import environment, owned
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    state_path = directory / 'state.json'
    def cli(action):
        subprocess.run([sys.executable, str(ROOT / 'scripts/test_stand.py'), action,
            '--state', str(state_path), '--gateway', '0', '--provider', 'disabled'], cwd=ROOT, check=True)
    cli('create')
    state = json.loads(state_path.read_text())
    (directory / 'run.json').write_text(json.dumps({'run_id': state['run_id'], 'database': state['database'],
        'scope': 'synthetic_negative_export_fixture', 'provider_mode': 'disabled', 'llm_calls': 0}, indent=2) + '\n')
    try:
        cli('bootstrap')
        subprocess.run([sys.executable, str(ROOT / 'tests/path29_browser_inputs.py'), '--state', str(state_path)],
            cwd=ROOT, env={**os.environ, 'P4K_FULL_PATH': '1'}, check=True)
        subprocess.run([sys.executable, __file__, '--directory', str(directory), '--child'],
            cwd=ROOT, env={**environment(state), 'AGENT4K_PATH29_TEST_APP': '1'}, check=True)
        proof = json.loads((directory / 'export-before-cleanup.json').read_text())
        receipt_bytes = (directory / 'export-receipt.json').read_bytes()
        with owned(state) as connection:
            assert connection.execute('SELECT 1 FROM pg_database WHERE datname=%s',
                                      (state['database'],)).fetchone()
        assert hashlib.sha256(receipt_bytes).hexdigest() == proof['receipt_sha256']
    except BaseException:
        # Preserve this exact owned state on an exporter failure, matching the browser gate.
        (directory / 'cleanup-deferred.json').write_text(json.dumps({
            'reason': 'EXPORT_REGRESSION_DID_NOT_PERSIST_VERIFIED_RECEIPT', 'database_preserved': True}) + '\n')
        raise
    cli('destroy')
    cleanup = json.loads((directory / 'cleanup.json').read_text())
    assert cleanup['database_absent'] and cleanup['state_absent']
    assert receipt_bytes == (directory / 'export-receipt.json').read_bytes()
    result = {'result': 'PASS', 'scope': 'synthetic_negative_export_fixture', 'llm_calls': 0,
        'order': ['DATABASE_CREATED', 'SYNTHETIC_FAILED_OPERATION_STORED', 'ACTUAL_COLLECTOR_READ',
                  'RECEIPT_FSYNC_AND_READBACK', 'DATABASE_EXISTENCE_CHECKED',
                  'OWNED_DATABASE_DROPPED', 'SAME_RECEIPT_READ_AFTER_CLEANUP'],
        'receipt_sha256': proof['receipt_sha256'], 'run_id': state['run_id']}
    (directory / 'regression-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    if args.child:
        collect_fixture(args.directory / 'state.json')
    else:
        run(args.directory)
