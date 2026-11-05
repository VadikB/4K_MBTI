"""Compare schema metadata only; never opens a database or applies a migration."""
import argparse
import hashlib
import json
from pathlib import Path


def checksum(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def compare(expected, actual):
    for record in (expected, actual):
        assert record['contract'] == 'path-pilot-schema-readback/1'
        assert record['transaction_read_only'] is True and record['transaction_rolled_back'] is True
        assert record['business_rows_read'] is False and record['schema_or_data_writes'] is False
        assert checksum(record['metadata']) == record['metadata_checksum']
    assert expected['target_kind'] == 'owned_empty_bootstrap' and actual['target_kind'] == 'working_server_env'
    assert expected['metadata']['requested_tables'] == actual['metadata']['requested_tables']
    missing, changed, extra = [], [], []
    for kind in ('columns', 'constraints', 'indexes', 'triggers'):
        left = {(row['table_name'], row['name']): row for row in expected['metadata'][kind]}
        right = {(row['table_name'], row['name']): row for row in actual['metadata'][kind]}
        assert len(left) == len(expected['metadata'][kind]) and len(right) == len(actual['metadata'][kind])
        for key, value in left.items():
            ref = {'kind': kind, 'table': key[0], 'name': key[1]}
            if key not in right:
                missing.append({**ref, 'expected': value})
            elif value != right[key]:
                changed.append({**ref, 'expected': value, 'actual': right[key]})
        extra.extend({'kind': kind, 'table': key[0], 'name': key[1], 'actual': value}
                     for key, value in right.items() if key not in left)
    expected_tables = set(expected['metadata']['requested_tables'])
    actual_tables = {row['table_name'] for row in actual['metadata']['columns']}
    baseline_tables = {row['table_name'] for row in expected['metadata']['columns']}
    assert baseline_tables == expected_tables
    return {'contract': 'path-pilot-schema-comparison/1',
            'result': 'EXACT_SCOPED_SCHEMA_MATCH' if not (missing or changed or extra) else 'SCHEMA_DIFFERENCES_REQUIRE_REVIEW',
            'expected_metadata_checksum': expected['metadata_checksum'],
            'actual_metadata_checksum': actual['metadata_checksum'],
            'working_server_checkout_sha': actual.get('server_checkout_sha'),
            'scope_table_count': len(expected_tables), 'missing_tables': sorted(expected_tables - actual_tables),
            'counts': {kind: {'expected': len(expected['metadata'][kind]), 'actual': len(actual['metadata'][kind])}
                       for kind in ('columns', 'constraints', 'indexes', 'triggers')},
            'missing': missing, 'changed': changed, 'extra': extra,
            'program_activation_checked': False, 'schema_or_data_writes': False,
            'business_rows_read': False, 'runtime_or_llm_pass': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected', type=Path)
    parser.add_argument('actual', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.expected.read_bytes()), json.loads(args.actual.read_bytes())),
                     ensure_ascii=False, indent=2))
