#!/usr/bin/env python3
"""Закрытый read-only поиск подготовки по публичному коду. Не HTTP/API для организации."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Api.database import get_connection
from Api.preparation_observation import OWNERS


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
                request_json->>'assignment_id' AS assignment_id, request_json->>'cycle_id' AS cycle_id,
                request_json->>'preparation_key' AS preparation_key,
                result_json->'plan'->>'cycle_id' AS prepared_cycle_id
                FROM product_cycle_preparation_operations WHERE operation_id=%s''', (row['operation_id'],)).fetchone()
            detail['operation'] = dict(op) if op else None
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
