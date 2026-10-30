"""Durable PII-free deletion intents outside the restorable application database."""
from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_KEYS = {'operation_id','target_type','target_id','preview_fingerprint','requested_at'}


def _get(row, name: str, index: int):
    return row[name] if isinstance(row, dict) else row[index]


def _path(value: str) -> Path:
    path = Path(str(value or '').strip())
    if not path.is_absolute() or not path.parent.is_dir():
        raise RuntimeError('DELETION_LEDGER_PATH must be an absolute file in a provisioned directory.')
    return path


def read_intents(path_value: str) -> list[dict]:
    path = _path(path_value)
    if not path.exists():
        raise RuntimeError('DELETION_LEDGER_NOT_PROVISIONED')
    records=[]
    with path.open('r',encoding='utf-8') as stream:
        for number,line in enumerate(stream,1):
            if not line.strip():
                continue
            try:
                record=json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f'DELETION_LEDGER_CORRUPT_LINE_{number}') from exc
            if set(record) != REQUIRED_KEYS or record['target_type'] not in {'organization','account'}:
                raise RuntimeError(f'DELETION_LEDGER_INVALID_LINE_{number}')
            records.append(record)
    operations={}
    for record in records:
        prior=operations.get(record['operation_id'])
        if prior is not None and prior != record:
            raise RuntimeError('DELETION_LEDGER_OPERATION_CONFLICT')
        operations[record['operation_id']]=record
    return list(operations.values())


def append_intent(path_value: str, *, operation_id: str, target_type: str,
                  target_id: int, fingerprint: str) -> dict:
    path=_path(path_value)
    record={'operation_id':operation_id,'target_type':target_type,'target_id':int(target_id),
        'preview_fingerprint':fingerprint,
        'requested_at':datetime.now(timezone.utc).isoformat()}
    descriptor=os.open(path,os.O_RDWR|os.O_APPEND|os.O_CREAT,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX)
        os.lseek(descriptor,0,os.SEEK_SET)
        existing=os.read(descriptor,os.fstat(descriptor).st_size).decode('utf-8')
        for line in existing.splitlines():
            if not line.strip():
                continue
            prior=json.loads(line)
            if prior.get('operation_id') != operation_id:
                continue
            comparable={key:prior.get(key) for key in ('operation_id','target_type','target_id','preview_fingerprint')}
            expected={key:record[key] for key in comparable}
            if comparable != expected:
                raise ValueError('DELETION_OPERATION_IDEMPOTENCY_CONFLICT')
            return prior
        os.write(descriptor,(json.dumps(record,sort_keys=True,separators=(',',':'))+'\n').encode())
        os.fsync(descriptor)
        return record
    finally:
        fcntl.flock(descriptor,fcntl.LOCK_UN)
        os.close(descriptor)


def ensure_receipt_schema(connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS data_deletion_receipts(
        operation_id TEXT PRIMARY KEY,
        target_type TEXT NOT NULL CHECK(target_type IN ('organization','account')),
        target_id BIGINT NOT NULL,
        preview_fingerprint TEXT NOT NULL,
        applied_at TIMESTAMP NOT NULL DEFAULT NOW()
    )""")


def record_receipt(connection, record: dict) -> None:
    connection.execute("""INSERT INTO data_deletion_receipts
        (operation_id,target_type,target_id,preview_fingerprint) VALUES(%s,%s,%s,%s)
        ON CONFLICT(operation_id) DO NOTHING""",(record['operation_id'],record['target_type'],
        record['target_id'],record['preview_fingerprint']))
    saved=connection.execute("""SELECT target_type,target_id,preview_fingerprint
        FROM data_deletion_receipts WHERE operation_id=%s""",(record['operation_id'],)).fetchone()
    if (_get(saved,'target_type',0),int(_get(saved,'target_id',1)),_get(saved,'preview_fingerprint',2)) != (
            record['target_type'],int(record['target_id']),record['preview_fingerprint']):
        raise ValueError('DELETION_RECEIPT_CONFLICT')


def read_receipt(connection, *, operation_id: str, target_type: str,
                 target_id: int, fingerprint: str) -> dict | None:
    row=connection.execute("""SELECT operation_id,target_type,target_id,preview_fingerprint,applied_at
        FROM data_deletion_receipts WHERE operation_id=%s""",(operation_id,)).fetchone()
    if row is None:
        return None
    if (_get(row,'target_type',1),int(_get(row,'target_id',2)),_get(row,'preview_fingerprint',3)) != (
            target_type,int(target_id),fingerprint):
        raise ValueError('DELETION_RECEIPT_CONFLICT')
    return dict(row) if isinstance(row,dict) else {'operation_id':_get(row,'operation_id',0)}


def assert_reconciled(connection, path_value: str) -> None:
    ensure_receipt_schema(connection)
    intents=read_intents(path_value)
    if not intents:
        return
    receipts=connection.execute("SELECT operation_id FROM data_deletion_receipts").fetchall()
    applied={_get(row,'operation_id',0) for row in receipts}
    missing=[record['operation_id'] for record in intents if record['operation_id'] not in applied]
    if missing:
        raise RuntimeError('DELETION_LEDGER_REPLAY_REQUIRED:' + ','.join(missing[:10]))
