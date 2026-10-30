"""Replay external deletion intents after DB restore, before API/workers are started."""
from __future__ import annotations

import argparse

from Api.config import settings
from Api.database import get_connection
from Api.deletion_ledger import assert_reconciled, ensure_receipt_schema, read_intents, record_receipt
from scripts.purge_test_organization import purge_account, purge_organization


def _get(row,name,index):
    return row[name] if isinstance(row,dict) else row[index]


def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(description='Reapply deletion tombstones after PostgreSQL restore.')
    parser.add_argument('--apply',action='store_true',help='Apply missing intents; default is read-only.')
    return parser.parse_args()


def main() -> int:
    args=parse_args()
    if not settings.deletion_ledger_path:
        raise SystemExit('DELETION_LEDGER_PATH is required.')
    intents=read_intents(settings.deletion_ledger_path)
    with get_connection() as connection:
        ensure_receipt_schema(connection)
        applied={_get(row,'operation_id',0) for row in connection.execute(
            'SELECT operation_id FROM data_deletion_receipts').fetchall()}
        missing=[record for record in intents if record['operation_id'] not in applied]
        connection.rollback()
    print(f'intents={len(intents)} missing={len(missing)} mode={"APPLY" if args.apply else "DRY_RUN"}')
    for record in missing:
        print(f"{record['operation_id']} {record['target_type']}:{record['target_id']}")
    if not args.apply:
        return 2 if missing else 0
    for record in missing:
        with get_connection() as connection:
            ensure_receipt_schema(connection)
            if record['target_type']=='organization':
                target=connection.execute('SELECT code FROM organizations WHERE id=%s FOR UPDATE',
                    (record['target_id'],)).fetchone()
                if target:
                    purge_organization(connection,organization_id=int(record['target_id']),
                        confirm_code=str(_get(target,'code',0)))
            else:
                target=connection.execute('SELECT id FROM users WHERE id=%s FOR UPDATE',
                    (record['target_id'],)).fetchone()
                if target:
                    purge_account(connection,user_id=int(record['target_id']))
            record_receipt(connection,record)
            connection.commit()
    with get_connection() as connection:
        assert_reconciled(connection,settings.deletion_ledger_path)
        connection.commit()
    print('RECONCILED')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
