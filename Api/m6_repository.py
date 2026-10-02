from __future__ import annotations

import json
from uuid import UUID, uuid4
from Api.assessment_configuration import definition_checksum
from Api.m6_contracts import validate_analysis


def ensure_schema(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS m6_processing_requests (
        id UUID PRIMARY KEY, as_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        handoff_id UUID NOT NULL REFERENCES m5_c45_handoffs(handoff_id), mode TEXT NOT NULL,
        input_json JSONB NOT NULL, input_hash TEXT NOT NULL, mechanism_json JSONB NOT NULL,
        mechanism_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
        created_by BIGINT NOT NULL REFERENCES users(id), synthetic_confirmed BOOLEAN NOT NULL CHECK(synthetic_confirmed),
        lease_token UUID, lease_expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(as_db_id,mode,input_hash,mechanism_hash), UNIQUE(id,as_db_id))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS m6_request_keys (
        as_db_id BIGINT NOT NULL, key TEXT NOT NULL, request_id UUID NOT NULL,
        PRIMARY KEY(as_db_id,key), FOREIGN KEY(request_id,as_db_id) REFERENCES m6_processing_requests(id,as_db_id))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS m6_processing_attempts (
        id UUID PRIMARY KEY, request_id UUID NOT NULL REFERENCES m6_processing_requests(id),
        attempt_no INTEGER NOT NULL, lease_token UUID NOT NULL, status TEXT NOT NULL,
        trace_json JSONB NOT NULL DEFAULT '{}', error_code TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(request_id,attempt_no), UNIQUE(id,request_id))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS m6_analysis_revisions (
        id UUID PRIMARY KEY, request_id UUID NOT NULL UNIQUE, as_db_id BIGINT NOT NULL,
        accepted_attempt_id UUID NOT NULL, output_json JSONB NOT NULL, output_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(id,as_db_id),
        FOREIGN KEY(request_id,as_db_id) REFERENCES m6_processing_requests(id,as_db_id),
        FOREIGN KEY(accepted_attempt_id,request_id) REFERENCES m6_processing_attempts(id,request_id))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS m6_evidence_bundles (
        id UUID PRIMARY KEY, as_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        indicator_id TEXT NOT NULL, UNIQUE(as_db_id,indicator_id), UNIQUE(id,as_db_id))''')
    connection.execute('''CREATE TABLE IF NOT EXISTS m6_bundle_revisions (
        bundle_id UUID NOT NULL, analysis_revision_id UUID NOT NULL, as_db_id BIGINT NOT NULL,
        content_json JSONB NOT NULL, PRIMARY KEY(bundle_id,analysis_revision_id),
        FOREIGN KEY(bundle_id,as_db_id) REFERENCES m6_evidence_bundles(id,as_db_id),
        FOREIGN KEY(analysis_revision_id,as_db_id) REFERENCES m6_analysis_revisions(id,as_db_id))''')


    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m6_revision_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M6 revision is immutable'; END; $$ LANGUAGE plpgsql""")
    for table in ('m6_analysis_revisions','m6_bundle_revisions','m6_evidence_bundles'):
        connection.execute(f'DROP TRIGGER IF EXISTS immutable_m6 ON {table}')
        connection.execute(f'CREATE TRIGGER immutable_m6 BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_m6_revision_change()')
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m6_request_input_change() RETURNS trigger AS $$
        BEGIN
            IF (NEW.as_db_id,NEW.handoff_id,NEW.mode,NEW.input_json,NEW.input_hash,
                NEW.mechanism_json,NEW.mechanism_hash,NEW.created_by,NEW.synthetic_confirmed)
               IS DISTINCT FROM
               (OLD.as_db_id,OLD.handoff_id,OLD.mode,OLD.input_json,OLD.input_hash,
                OLD.mechanism_json,OLD.mechanism_hash,OLD.created_by,OLD.synthetic_confirmed)
            THEN RAISE EXCEPTION 'M6 input is immutable'; END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    connection.execute('DROP TRIGGER IF EXISTS immutable_m6_input ON m6_processing_requests')
    connection.execute('CREATE TRIGGER immutable_m6_input BEFORE UPDATE ON m6_processing_requests FOR EACH ROW EXECUTE FUNCTION prevent_m6_request_input_change()')


def existing_key(connection, handoff_id, key, mechanism_ref):
    row = connection.execute('''SELECT r.* FROM m6_request_keys k
        JOIN m6_processing_requests r ON r.id=k.request_id
        JOIN m5_c45_handoffs h ON h.assessment_situation_db_id=k.as_db_id
        WHERE h.handoff_id=%s AND k.key=%s''', (UUID(handoff_id),key)).fetchone()
    if row and (str(row['handoff_id']) != handoff_id or row['mechanism_json']['ref'] != mechanism_ref):
        raise ValueError('IDEMPOTENCY_CONFLICT')
    return row


def enqueue(connection, *, as_db_id, handoff_id, key, material, mechanism, created_by):
    # Serialize creation per AS: both transport keys and identical effects must deduplicate.
    connection.execute('SELECT id FROM m5_assessment_situations WHERE id=%s FOR UPDATE',(as_db_id,)).fetchone()
    ih, mh = definition_checksum(material), definition_checksum(mechanism)
    existing = existing_key(connection,handoff_id,key,mechanism['ref'])
    if existing:
        if existing['input_hash'] != ih or existing['mechanism_hash'] != mh:
            raise ValueError('IDEMPOTENCY_CONFLICT')
        return dict(existing)
    row = connection.execute('''INSERT INTO m6_processing_requests
        (id,as_db_id,handoff_id,mode,input_json,input_hash,mechanism_json,mechanism_hash,status,created_by,synthetic_confirmed)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,'queued',%s,TRUE)
        ON CONFLICT(as_db_id,mode,input_hash,mechanism_hash) DO NOTHING RETURNING *''',
        (uuid4(),as_db_id,UUID(handoff_id),material['mode'],json.dumps(material,ensure_ascii=False),ih,
         json.dumps(mechanism,ensure_ascii=False),mh,created_by)).fetchone()
    if not row:
        row = connection.execute('SELECT * FROM m6_processing_requests WHERE as_db_id=%s AND mode=%s AND input_hash=%s AND mechanism_hash=%s',
                                 (as_db_id,material['mode'],ih,mh)).fetchone()
    connection.execute('INSERT INTO m6_request_keys VALUES (%s,%s,%s)',(as_db_id,key,row['id']))
    return dict(row)


def claim(connection, request_id):
    row = connection.execute('''SELECT * FROM m6_processing_requests WHERE id=%s FOR UPDATE''',(UUID(str(request_id)),)).fetchone()
    if not row:
        raise ValueError('M6_REQUEST_NOT_FOUND')
    if row['status']=='succeeded': return None
    if row['status']=='running' and connection.execute('SELECT %s > NOW() AS active',(row['lease_expires_at'],)).fetchone()['active']:
        return None
    connection.execute("UPDATE m6_processing_attempts SET status='expired' WHERE request_id=%s AND status='running'",(row['id'],))
    token=uuid4(); attempt=uuid4()
    seconds=int(row['mechanism_json']['lease_seconds'])
    connection.execute("UPDATE m6_processing_requests SET status='running',lease_token=%s,lease_expires_at=NOW()+%s*INTERVAL '1 second' WHERE id=%s",(token,seconds,row['id']))
    connection.execute('''INSERT INTO m6_processing_attempts(id,request_id,attempt_no,lease_token,status)
        SELECT %s,%s,COALESCE(MAX(attempt_no),0)+1,%s,'running' FROM m6_processing_attempts WHERE request_id=%s''',
        (attempt,row['id'],token,row['id']))
    return {**dict(row),'lease_token':token,'attempt_id':attempt}


def finish(connection, job, output, trace, error=None):
    row=connection.execute('SELECT * FROM m6_processing_requests WHERE id=%s FOR UPDATE',(job['id'],)).fetchone()
    if row['lease_token'] != job['lease_token'] or row['status'] != 'running': return False
    if connection.execute('SELECT %s <= NOW() AS expired',(row['lease_expires_at'],)).fetchone()['expired']:
        return False
    if output is not None:
        output=validate_analysis(output,row['input_json'])
        revision=uuid4()
        connection.execute('''INSERT INTO m6_analysis_revisions
            (id,request_id,as_db_id,accepted_attempt_id,output_json,output_hash) VALUES (%s,%s,%s,%s,%s::jsonb,%s)''',
            (revision,row['id'],row['as_db_id'],job['attempt_id'],json.dumps(output,ensure_ascii=False),definition_checksum(output)))
        for bundle in output['bundles']:
            connection.execute('INSERT INTO m6_evidence_bundles VALUES (%s,%s,%s) ON CONFLICT(as_db_id,indicator_id) DO NOTHING',
                               (uuid4(),row['as_db_id'],bundle['indicator_id']))
            bid=connection.execute('SELECT id FROM m6_evidence_bundles WHERE as_db_id=%s AND indicator_id=%s',
                                   (row['as_db_id'],bundle['indicator_id'])).fetchone()['id']
            connection.execute('INSERT INTO m6_bundle_revisions VALUES (%s,%s,%s,%s::jsonb)',
                               (bid,revision,row['as_db_id'],json.dumps(bundle,ensure_ascii=False)))
    status='succeeded' if output is not None else 'failed'
    connection.execute('UPDATE m6_processing_attempts SET status=%s,trace_json=%s::jsonb,error_code=%s WHERE id=%s',
                       (status,json.dumps(trace,ensure_ascii=False),error,job['attempt_id']))
    connection.execute('UPDATE m6_processing_requests SET status=%s,lease_token=NULL,lease_expires_at=NULL WHERE id=%s',(status,row['id']))
    return True


def read_request(connection, request_id):
    row=connection.execute('''SELECT r.id,r.status,r.created_at,a.id AS analysis_revision_id
        FROM m6_processing_requests r LEFT JOIN m6_analysis_revisions a ON a.request_id=r.id WHERE r.id=%s''',(UUID(str(request_id)),)).fetchone()
    if not row: raise ValueError('M6_REQUEST_NOT_FOUND')
    return dict(row)


def read_analysis(connection, revision_id):
    row=connection.execute('''SELECT a.*,r.input_json,r.input_hash FROM m6_analysis_revisions a
        JOIN m6_processing_requests r ON r.id=a.request_id WHERE a.id=%s''',(UUID(str(revision_id)),)).fetchone()
    if not row: raise ValueError('M6_ANALYSIS_NOT_FOUND')
    if definition_checksum(row['output_json']) != row['output_hash'] or definition_checksum(row['input_json']) != row['input_hash']:
        raise ValueError('CHECKSUM_MISMATCH')
    validate_analysis(row['output_json'],row['input_json'])
    bundles=connection.execute('SELECT bundle_id,content_json FROM m6_bundle_revisions WHERE analysis_revision_id=%s',(row['id'],)).fetchall()
    return {'id':row['id'],'request_id':row['request_id'],'analysis':row['output_json'],
            'material':row['input_json'],'bundles':[dict(x) for x in bundles]}
