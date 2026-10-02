from __future__ import annotations
from Api.m5_case_runtime import checksum
from uuid import UUID

def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_completion_commands(
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),key TEXT NOT NULL,request_checksum TEXT NOT NULL,
        result_json JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(cycle_db_id,key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_transition_events(
        id UUID PRIMARY KEY,cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),session_db_id BIGINT REFERENCES m5_cycle_sessions(id),
        assessment_situation_db_id BIGINT REFERENCES m5_assessment_situations(id),event_type TEXT NOT NULL,reason TEXT NOT NULL,
        initiated_by BIGINT NOT NULL REFERENCES users(id),before_json JSONB NOT NULL,after_json JSONB NOT NULL,boundary_json JSONB NOT NULL,
        effective_at TIMESTAMPTZ NOT NULL,processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_finalization_outbox(
        assessment_situation_db_id BIGINT PRIMARY KEY REFERENCES m5_assessment_situations(id),handoff_id UUID NOT NULL UNIQUE REFERENCES m5_c45_handoffs(handoff_id),
        status TEXT NOT NULL CHECK(status IN('pending','queued','failed')),m6_request_id UUID,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_continuation_intents(
        id UUID PRIMARY KEY,cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),interrupted_session_db_id BIGINT NOT NULL REFERENCES m5_cycle_sessions(id),
        status TEXT NOT NULL CHECK(status IN('pending','consumed','rejected')),snapshot_json JSONB NOT NULL,snapshot_checksum TEXT NOT NULL,
        created_by BIGINT NOT NULL REFERENCES users(id),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),consumed_at TIMESTAMPTZ)""")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_m7_pending_continuation ON m7_continuation_intents(cycle_db_id) WHERE status='pending'""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_additional_session_keys(
        cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),key TEXT NOT NULL,request_checksum TEXT NOT NULL,
        session_db_id BIGINT NOT NULL REFERENCES m5_cycle_sessions(id),PRIMARY KEY(cycle_db_id,key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_c46_revisions(
        id UUID PRIMARY KEY,cycle_db_id BIGINT NOT NULL REFERENCES m5_cycles(id),revision_no INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN('collection_snapshot','reconciled')),
        composition_checksum TEXT NOT NULL,payload_json JSONB NOT NULL,payload_checksum TEXT NOT NULL,calculation_ref_json JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(cycle_db_id,revision_no),UNIQUE(id,cycle_db_id))""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m7_completion_history_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M7 completion history is immutable';END;$$ LANGUAGE plpgsql""")
    for table in ('m7_transition_events','m7_finalization_outbox','m7_continuation_intents','m7_c46_revisions'):
        connection.execute(f'DROP TRIGGER IF EXISTS immutable_m7_completion ON {table}')
    for table in ('m7_transition_events','m7_c46_revisions'):
        connection.execute(f'CREATE TRIGGER immutable_m7_completion BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_m7_completion_history_change()')

def existing(connection,cycle_db_id,key,request_checksum):
    row=connection.execute('SELECT * FROM m7_completion_commands WHERE cycle_db_id=%s AND key=%s',(cycle_db_id,key)).fetchone()
    if not row:return None
    if row['request_checksum']!=request_checksum:raise ValueError('IDEMPOTENCY_CONFLICT')
    return row['result_json']

def read_c46(connection,cycle_db_id):
    row=connection.execute('SELECT * FROM m7_c46_revisions WHERE cycle_db_id=%s ORDER BY revision_no DESC LIMIT 1',(cycle_db_id,)).fetchone()
    if not row:raise ValueError('C46_NOT_FOUND')
    if checksum(row['payload_json'])!=row['payload_checksum']:raise ValueError('CHECKSUM_MISMATCH')
    return dict(row)
