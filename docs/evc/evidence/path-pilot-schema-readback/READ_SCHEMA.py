"""Metadata only. No application imports, schema bootstrap or business rows."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

TABLES = sorted('''assessment_program_definitions assessment_program_allowed_roles
organization_assessment_program_connections assessment_configurations
assessment_role_profiles assessment_role_profile_versions assessment_personalized_profiles
assessment_organization_context_versions assessment_user_context_versions
organizations users organization_assessment_assignments organization_assessment_source_bindings
questionnaire_response_revisions participant_acquaintance_confirmations
product_cycle_preparation_operations m5_case_versions m5_catalogs m5_catalog_case_versions
m5_qa_evidence m5_cycles m5_cycle_sessions m5_assessment_situations m5_dialogue_turns
m5_cycle_time_intervals m7_cycle_plans m7_plan_revisions m7_route_decisions
m7_route_assignments m7_parameter_revisions m7_route_positions m7_route_position_as_history'''.split())


def collect(args):
    import psycopg
    from psycopg.rows import dict_row
    if args.env_file:
        from dotenv import dotenv_values
        # Credentials are consumed only in memory, never included in diagnostics.
        values = dotenv_values(args.env_file)
        assert all(values.get(key) for key in ('DB_HOST', 'DB_NAME', 'DB_USER'))
        params = {key: values.get(name, default) for key, name, default in (
            ('host', 'DB_HOST', 'localhost'), ('port', 'DB_PORT', '5432'),
            ('dbname', 'DB_NAME', ''), ('user', 'DB_USER', ''), ('password', 'DB_PASSWORD', ''))}
        state = None
    else:
        state = json.loads(args.stand_state.read_bytes())
        assert state['database'].startswith('product4k_pytest_')
        params = {**state['connection'], 'dbname': state['database']}
    params.update(connect_timeout=10, options='-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000')
    with psycopg.connect(**params, row_factory=dict_row) as c:
        c.read_only = True
        c.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
        if state:
            marker = c.execute("SELECT shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()").fetchone()['marker']
            assert marker == state['owner_marker']
        version = c.execute('SHOW server_version_num').fetchone()['server_version_num']
        columns = c.execute('''SELECT t.relname AS table_name,a.attname AS name,
            format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull AS not_null,
            pg_get_expr(d.adbin,d.adrelid) AS default_expression
            FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
            JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum>0 AND NOT a.attisdropped
            LEFT JOIN pg_attrdef d ON d.adrelid=t.oid AND d.adnum=a.attnum
            WHERE n.nspname='public' AND t.relkind='r' AND t.relname=ANY(%s)
            ORDER BY t.relname,a.attname''', (TABLES,)).fetchall()
        constraints = c.execute('''SELECT t.relname AS table_name,x.conname AS name,
            x.contype AS type,x.convalidated AS validated,pg_get_constraintdef(x.oid) AS definition
            FROM pg_constraint x JOIN pg_class t ON t.oid=x.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='public' AND t.relname=ANY(%s) ORDER BY t.relname,x.conname''', (TABLES,)).fetchall()
        indexes = c.execute('''SELECT t.relname AS table_name,i.relname AS name,
            x.indisvalid AS valid,x.indisunique AS unique,pg_get_indexdef(i.oid) AS definition
            FROM pg_index x JOIN pg_class t ON t.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='public' AND t.relname=ANY(%s) ORDER BY t.relname,i.relname''', (TABLES,)).fetchall()
        triggers = c.execute('''SELECT t.relname AS table_name,g.tgname AS name,g.tgenabled AS enabled,
            pg_get_triggerdef(g.oid) AS definition,md5(pg_get_functiondef(g.tgfoid)) AS function_definition_md5
            FROM pg_trigger g JOIN pg_class t ON t.oid=g.tgrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='public' AND NOT g.tgisinternal AND t.relname=ANY(%s)
            ORDER BY t.relname,g.tgname''', (TABLES,)).fetchall()
        c.rollback()
    metadata = {'requested_tables': TABLES, 'columns': columns, 'constraints': constraints,
                'indexes': indexes, 'triggers': triggers}
    canonical = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    result = {'contract': 'path-pilot-schema-readback/1', 'observed_at_utc': datetime.now(timezone.utc).isoformat(),
              'transaction_read_only': True, 'transaction_rolled_back': True,
              'application_imported': False, 'business_rows_read': False, 'schema_or_data_writes': False,
              'target_kind': 'working_server_env' if args.env_file else 'owned_empty_bootstrap',
              'server_version_num': version, 'metadata_checksum': hashlib.sha256(canonical).hexdigest(),
              'metadata': metadata}
    if args.checkout:
        result['server_checkout_sha'] = subprocess.run(['git', '-C', str(args.checkout), 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True).stdout.strip()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--env-file', type=Path)
    group.add_argument('--stand-state', type=Path)
    parser.add_argument('--checkout', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({'result': 'SCHEMA_READBACK_FAILED', 'exception_type': type(exc).__name__,
                          'details_redacted': True}))
        raise SystemExit(2)
