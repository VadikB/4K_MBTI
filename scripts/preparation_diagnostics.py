#!/usr/bin/env python3
"""Закрытый read-only поиск подготовки по публичному коду. Не HTTP/API для организации."""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Api.database import get_connection
from Api.preparation_observation import OWNERS


def _provider_receipt(operation):
    return {key: operation.get(key) for key in (
        'kind', 'operation_id', 'input_checksum', 'calls', 'parse_failures',
    )}


def _review_receipts(tested):
    result = {}
    for reviewer, key in (('tester', 'provider_operation'), ('challenger', 'challenger_operation')):
        checks = {check['check_id']: check for check in
                  (tested.get('independent_checks') or {}).get(reviewer, [])}
        result[reviewer] = [
            {**_provider_receipt(batch), 'batch_no': batch['batch_no'],
             'required_check_ids': batch['required_check_ids'],
             **({'clarification': {key: batch['clarification'][key] for key in
                 ('accepted_check_ids', 'error', 'elapsed_ms') if key in batch['clarification']}}
                if batch.get('clarification') else {}),
             'protocol_errors': [
                 {**error, 'check_id': check_id, 'reviewer': reviewer, 'batch_no': batch['batch_no']}
                 for check_id in batch['required_check_ids']
                 for error in checks.get(check_id, {}).get('protocol_errors', [])
             ]}
            for batch in (tested.get(key) or {}).get('batches', [])
        ]
    return result


def _functional_preparation(connection, operation, failure):
    prepared = failure
    if operation['status'] == 'completed' and operation['prepared_as_db_id'] is not None:
        receipt = connection.execute('''SELECT s.execution_payload_json
                #>'{ai_operations,functional_personalization}' AS trace
            FROM m5_assessment_situations s JOIN m5_cycles c ON c.id=s.cycle_db_id
            WHERE s.id=%s AND c.cycle_id::text=%s''',
            (operation['prepared_as_db_id'], operation['prepared_cycle_id'])).fetchone()
        prepared = receipt['trace'] if receipt else None
    generation = (prepared or {}).get('generation_operation')
    if not generation or not isinstance(generation.get('operation_id'), str):
        return None
    operation_id = generation['operation_id'].rsplit(':generation:', 1)[0]
    if operation_id != operation['operation_id']:
        # A replay can read an AS that was prepared by an earlier operation.
        return None
    tested = prepared['tester']
    repair = prepared.get('repair')
    refs = (prepared.get('source_snapshot') or {}).get('refs') or {}
    return {
        'operation_id': operation_id,
        'candidate_checksum': prepared['candidate_checksum'],
        'input_snapshot_checksum': prepared.get('input_snapshot_checksum'),
        'package': refs.get('protocol_package') or (tested.get('review_source') or {}).get('review_package'),
        'tester_protocol': tested['protocol'],
        'admission_status': tested['aggregation']['status'],
        'admitted_for_participant': prepared['admitted_for_participant'],
        'generation': _provider_receipt(repair['original_generation_operation'] if repair else generation),
        'initial_reviews': _review_receipts(repair['original_tester'] if repair else tested),
        'repair': {**_provider_receipt(repair['repair_generation_operation']),
                   'original_candidate_checksum': repair['original_candidate_checksum'],
                   'outcome': repair.get('outcome')} if repair else None,
        'recheck': _review_receipts(tested) if repair and repair.get('outcome') != 'UNCHANGED_CANDIDATE' else None,
    }


def lookup(connection, code):
    if not re.fullmatch(r'P4K-[A-F0-9]{24}', code):
        raise ValueError('Неверный формат кода обращения')
    # PostgreSQL16 sha256(bytea); no extension or writes. Hash cannot encode PII.
    rows = connection.execute('''SELECT * FROM preparation_observations
        WHERE 'P4K-' || upper(substr(encode(sha256(convert_to((CASE WHEN source='recovery' THEN 'report' ELSE source END) || ':' || operation_id,'UTF8')),'hex'),1,24))=%s
        ORDER BY id''', (code,)).fetchall()
    output = []
    for raw in rows:
        row = dict(raw)
        detail = {key: row[key] for key in ('source','operation_id','attempt_token','kind','stage',
            'started_at','stage_started_at','heartbeat_at','history_json','delay_events','status','error_category')}
        detail['owner'] = OWNERS.get(row['stage'], 'Проверить сохранённый этап в указанной операции')
        if row['source'] == 'cycle':
            op = connection.execute('''SELECT operation_id,status,attempts,attempt_token,locked_at,error_code,
                created_at AT TIME ZONE current_setting('TimeZone') AS enqueued_at,
                completed_at AT TIME ZONE current_setting('TimeZone') AS completed_at,
                request_json->>'assignment_id' AS assignment_id, request_json->>'cycle_id' AS cycle_id,
                request_json->>'preparation_key' AS preparation_key,
                result_json->'plan'->>'cycle_id' AS prepared_cycle_id,
                result_json->'decision'->'assigned_as_db_id' AS prepared_as_db_id,
                result_json->'generated' AS functional_failure,
                result_json->'generated'->'candidate_checksum' AS candidate_checksum,
                result_json->'generated'->'tester'->'aggregation' AS admission_aggregation,
                result_json->'generated'->'tester'->'independent_checks' AS admission_checks,
                result_json->'generated'->'deterministic_validation' AS deterministic_validation
                FROM product_cycle_preparation_operations WHERE operation_id=%s''', (row['operation_id'],)).fetchone()
            detail['operation'] = dict(op) if op else None
            if op:
                failure = detail['operation'].pop('functional_failure')
                if row['status'] == op['status'] and op['status'] in {'completed', 'failed'}:
                    detail['functional_preparation'] = _functional_preparation(connection, op, failure)
                history = row['history_json']
                if history and row['attempt_token'] != 'queued':
                    started = datetime.fromisoformat(history[0]['at'])
                    detail['timing'] = {
                        'enqueue_to_worker_ms': round((started - op['enqueued_at']).total_seconds() * 1000, 3),
                        'ready_persistence_ms': row['scope_json'].get('ready_persistence_ms'),
                    }
        elif row['source'] in {'report','recovery'}:
            op = connection.execute('''SELECT p.*,c.cycle_id,c.assignment_id,claim.token,claim.lease_until
                FROM m10_pipeline_runs p JOIN m5_cycles c ON c.id=p.cycle_db_id
                LEFT JOIN m10_report_claims claim ON claim.cycle_db_id=c.id WHERE c.cycle_id=%s''', (row['operation_id'],)).fetchone()
            detail['operation'] = dict(op) if op else None
            detail['processing_attempts'] = [dict(x) for x in connection.execute('''
                SELECT 'evidence' AS kind,e.id,e.status,e.lease_token,e.lease_expires_at
                FROM m6_processing_requests e JOIN m5_assessment_situations s ON s.id=e.as_db_id
                JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE c.cycle_id=%s
                UNION ALL
                SELECT 'assessment',a.id,a.status,a.lease_token,a.lease_expires_at
                FROM m6_assessment_requests a JOIN m5_assessment_situations s ON s.id=a.as_db_id
                JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE c.cycle_id=%s''', (row['operation_id'], row['operation_id'])).fetchall()]
        else:
            detail['operation'] = {'status': row['status'], 'scope': row['scope_json']}
        output.append(detail)
    if not rows:
        # Queued operations have no attempt yet; still resolve exactly the same code.
        op = connection.execute('''SELECT operation_id,status,attempts,locked_at,error_code,
            request_json->>'assignment_id' AS assignment_id FROM product_cycle_preparation_operations
            WHERE 'P4K-'||upper(substr(encode(sha256(convert_to('cycle:'||operation_id,'UTF8')),'hex'),1,24))=%s''', (code,)).fetchone()
        if op:
            output.append({'operation': dict(op), 'owner': OWNERS['queued']})
    if not output:
        op = connection.execute('''SELECT p.*,c.cycle_id,c.assignment_id FROM m10_pipeline_runs p
            JOIN m5_cycles c ON c.id=p.cycle_db_id
            WHERE 'P4K-'||upper(substr(encode(sha256(convert_to('report:'||c.cycle_id::text,'UTF8')),'hex'),1,24))=%s''', (code,)).fetchone()
        if op:
            output.append({'operation': dict(op), 'owner': OWNERS['answers'], 'details': 'legacy: detailed stages unavailable'})
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference')
    args = parser.parse_args()
    with get_connection() as connection:
        connection.execute('SET TRANSACTION READ ONLY')
        found = lookup(connection, args.reference)
    print(json.dumps(found, ensure_ascii=False, default=str, indent=2))
    sys.exit(0 if found else 1)
