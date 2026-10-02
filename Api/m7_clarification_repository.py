from __future__ import annotations
import json
from uuid import UUID,uuid4
from Api.m5_case_runtime import checksum

def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_clarification_decisions(
        id UUID PRIMARY KEY,assessment_situation_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        c54_revision_id UUID NOT NULL REFERENCES m6_c54_revisions(id),status TEXT NOT NULL CHECK(status IN('ASK','NO_QUESTION','NEW_AS','WAIT_TECHNICAL','STOP')),
        input_json JSONB NOT NULL,input_checksum TEXT NOT NULL,mechanism_json JSONB,mechanism_checksum TEXT,
        question_json JSONB,explanation_json JSONB NOT NULL,trace_json JSONB NOT NULL DEFAULT '{}',created_by BIGINT NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(assessment_situation_db_id,c54_revision_id),UNIQUE(id,assessment_situation_db_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_clarification_keys(assessment_situation_db_id BIGINT NOT NULL,key TEXT NOT NULL,
        request_hash TEXT NOT NULL,decision_id UUID NOT NULL REFERENCES m7_clarification_decisions(id),PRIMARY KEY(assessment_situation_db_id,key))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_clarification_deliveries(decision_id UUID PRIMARY KEY REFERENCES m7_clarification_decisions(id),
        question_turn_id UUID NOT NULL UNIQUE,sequence_no INTEGER NOT NULL,delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m7_clarification_responses(decision_id UUID PRIMARY KEY REFERENCES m7_clarification_decisions(id),
        outcome TEXT NOT NULL CHECK(outcome IN('answered','no_answer','refused')),request_id TEXT NOT NULL,answer_turn_id UUID UNIQUE,sequence_no INTEGER,
        handoff_id UUID REFERENCES m5_c45_handoffs(handoff_id),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CHECK((outcome='answered' AND answer_turn_id IS NOT NULL) OR (outcome<>'answered' AND answer_turn_id IS NULL)))""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m7_clarification_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M7 clarification history is immutable';END;$$ LANGUAGE plpgsql""")
    for table in ('m7_clarification_decisions','m7_clarification_deliveries','m7_clarification_responses'):
        connection.execute(f'DROP TRIGGER IF EXISTS immutable_m7_clarification ON {table}')
        connection.execute(f'CREATE TRIGGER immutable_m7_clarification BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_m7_clarification_change()')

def existing(connection,as_db_id,key,request_hash):
    row=connection.execute("SELECT decision_id,request_hash FROM m7_clarification_keys WHERE assessment_situation_db_id=%s AND key=%s",(as_db_id,key)).fetchone()
    if not row:return None
    if row['request_hash']!=request_hash:raise ValueError('IDEMPOTENCY_CONFLICT')
    return read(connection,row['decision_id'])

def save(connection,*,as_db_id,c54_revision_id,key,request_hash,status,input_value,mechanism,question,explanation,trace,created_by):
    prior=connection.execute("SELECT id FROM m7_clarification_decisions WHERE assessment_situation_db_id=%s AND c54_revision_id=%s",
        (as_db_id,UUID(c54_revision_id))).fetchone()
    if prior:
        connection.execute('INSERT INTO m7_clarification_keys VALUES(%s,%s,%s,%s)',(as_db_id,key,request_hash,prior['id']))
        return read(connection,prior['id'])
    did=uuid4();row=connection.execute("""INSERT INTO m7_clarification_decisions
        (id,assessment_situation_db_id,c54_revision_id,status,input_json,input_checksum,mechanism_json,mechanism_checksum,question_json,explanation_json,trace_json,created_by)
        VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s) RETURNING *""",
        (did,as_db_id,UUID(c54_revision_id),status,json.dumps(input_value,ensure_ascii=False),checksum(input_value),json.dumps(mechanism) if mechanism else None,
         mechanism.get('snapshot_checksum') if mechanism else None,json.dumps(question,ensure_ascii=False) if question else None,json.dumps(explanation,ensure_ascii=False),json.dumps(trace,ensure_ascii=False),created_by)).fetchone()
    connection.execute('INSERT INTO m7_clarification_keys VALUES(%s,%s,%s,%s)',(as_db_id,key,request_hash,did));return dict(row)

def read(connection,decision_id):
    row=connection.execute("""SELECT d.*,q.question_turn_id,q.sequence_no AS question_sequence,r.outcome AS response_outcome,r.request_id AS response_request_id,
        r.answer_turn_id,r.sequence_no AS answer_sequence,r.handoff_id FROM m7_clarification_decisions d
        LEFT JOIN m7_clarification_deliveries q ON q.decision_id=d.id LEFT JOIN m7_clarification_responses r ON r.decision_id=d.id WHERE d.id=%s""",(UUID(str(decision_id)),)).fetchone()
    if not row:raise ValueError('M7_CLARIFICATION_NOT_FOUND')
    if checksum(row['input_json'])!=row['input_checksum']:raise ValueError('CHECKSUM_MISMATCH')
    return dict(row)
