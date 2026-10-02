from __future__ import annotations

import json
from uuid import UUID, uuid4

from Api.assessment_configuration import definition_checksum
from Api.m6_assessment_contracts import validate_assessment


def ensure_schema(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_assessment_requests (
        id UUID PRIMARY KEY, as_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id),
        evidence_revision_id UUID NOT NULL REFERENCES m6_analysis_revisions(id), mode TEXT NOT NULL CHECK(mode IN ('interim','final')),
        input_json JSONB NOT NULL, input_hash TEXT NOT NULL, mechanism_json JSONB NOT NULL, mechanism_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
        created_by BIGINT NOT NULL REFERENCES users(id), synthetic_confirmed BOOLEAN NOT NULL CHECK(synthetic_confirmed),
        lease_token UUID, lease_expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(as_db_id,evidence_revision_id,mode,mechanism_hash), UNIQUE(id,as_db_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_assessment_request_keys (
        as_db_id BIGINT NOT NULL, key TEXT NOT NULL, request_id UUID NOT NULL,
        PRIMARY KEY(as_db_id,key), FOREIGN KEY(request_id,as_db_id) REFERENCES m6_assessment_requests(id,as_db_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_assessment_attempts (
        id UUID PRIMARY KEY, request_id UUID NOT NULL REFERENCES m6_assessment_requests(id), attempt_no INTEGER NOT NULL,
        lease_token UUID NOT NULL, status TEXT NOT NULL, trace_json JSONB NOT NULL DEFAULT '{}', error_code TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(request_id,attempt_no), UNIQUE(id,request_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_assessment_revisions (
        id UUID PRIMARY KEY, request_id UUID NOT NULL UNIQUE, as_db_id BIGINT NOT NULL, accepted_attempt_id UUID NOT NULL,
        mode TEXT NOT NULL, output_json JSONB NOT NULL, output_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(id,as_db_id), FOREIGN KEY(request_id,as_db_id) REFERENCES m6_assessment_requests(id,as_db_id),
        FOREIGN KEY(accepted_attempt_id,request_id) REFERENCES m6_assessment_attempts(id,request_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_indicator_assessments (
        id UUID PRIMARY KEY, as_db_id BIGINT NOT NULL REFERENCES m5_assessment_situations(id), indicator_id TEXT NOT NULL,
        UNIQUE(as_db_id,indicator_id), UNIQUE(id,as_db_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_indicator_assessment_revisions (
        id UUID PRIMARY KEY, indicator_assessment_id UUID NOT NULL, assessment_revision_id UUID NOT NULL,
        as_db_id BIGINT NOT NULL, content_json JSONB NOT NULL, content_hash TEXT NOT NULL,
        FOREIGN KEY(indicator_assessment_id,as_db_id) REFERENCES m6_indicator_assessments(id,as_db_id),
        FOREIGN KEY(assessment_revision_id,as_db_id) REFERENCES m6_assessment_revisions(id,as_db_id),
        UNIQUE(indicator_assessment_id,assessment_revision_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_no_assessment_revisions (
        id UUID PRIMARY KEY, assessment_revision_id UUID NOT NULL, as_db_id BIGINT NOT NULL, indicator_id TEXT NOT NULL,
        content_json JSONB NOT NULL, content_hash TEXT NOT NULL,
        FOREIGN KEY(assessment_revision_id,as_db_id) REFERENCES m6_assessment_revisions(id,as_db_id),
        UNIQUE(assessment_revision_id,indicator_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS m6_c54_revisions (
        id UUID PRIMARY KEY, assessment_revision_id UUID NOT NULL UNIQUE, as_db_id BIGINT NOT NULL,
        handoff_id UUID NOT NULL REFERENCES m5_c45_handoffs(handoff_id), mode TEXT NOT NULL,
        payload_json JSONB NOT NULL, payload_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY(assessment_revision_id,as_db_id) REFERENCES m6_assessment_revisions(id,as_db_id))""")
    connection.execute("""CREATE OR REPLACE FUNCTION prevent_m6_assessment_revision_change() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'M6 assessment revision is immutable'; END; $$ LANGUAGE plpgsql""")
    for table in ("m6_assessment_revisions", "m6_indicator_assessment_revisions", "m6_no_assessment_revisions", "m6_c54_revisions"):
        connection.execute(f"DROP TRIGGER IF EXISTS immutable_m6_assessment ON {table}")
        connection.execute(f"CREATE TRIGGER immutable_m6_assessment BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_m6_assessment_revision_change()")
    connection.execute("""CREATE OR REPLACE FUNCTION protect_m6_assessment_request_input() RETURNS trigger AS $$
        BEGIN
            IF NEW.as_db_id IS DISTINCT FROM OLD.as_db_id
               OR NEW.evidence_revision_id IS DISTINCT FROM OLD.evidence_revision_id
               OR NEW.mode IS DISTINCT FROM OLD.mode
               OR NEW.input_json IS DISTINCT FROM OLD.input_json
               OR NEW.input_hash IS DISTINCT FROM OLD.input_hash
               OR NEW.mechanism_json IS DISTINCT FROM OLD.mechanism_json
               OR NEW.mechanism_hash IS DISTINCT FROM OLD.mechanism_hash
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.synthetic_confirmed IS DISTINCT FROM OLD.synthetic_confirmed THEN
                RAISE EXCEPTION 'M6 assessment request input is immutable';
            END IF;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    connection.execute("DROP TRIGGER IF EXISTS immutable_m6_assessment_request_input ON m6_assessment_requests")
    connection.execute("""CREATE TRIGGER immutable_m6_assessment_request_input BEFORE UPDATE ON m6_assessment_requests
        FOR EACH ROW EXECUTE FUNCTION protect_m6_assessment_request_input()""")


def build_input(connection, evidence_revision_id: str) -> tuple[int, str, dict]:
    evidence = connection.execute("""SELECT a.*,r.input_json,r.input_hash,r.handoff_id,r.mode AS request_mode,
        h.boundary_sequence,h.envelope_checksum,s.status AS as_status
        FROM m6_analysis_revisions a JOIN m6_processing_requests r ON r.id=a.request_id
        JOIN m5_c45_handoffs h ON h.handoff_id=r.handoff_id
        JOIN m5_assessment_situations s ON s.id=r.as_db_id WHERE a.id=%s""", (UUID(evidence_revision_id),)).fetchone()
    if not evidence:
        raise ValueError("M6_ANALYSIS_NOT_FOUND")
    if definition_checksum(evidence["input_json"]) != evidence["input_hash"] or definition_checksum(evidence["output_json"]) != evidence["output_hash"]:
        raise ValueError("CHECKSUM_MISMATCH")
    mode = "final" if evidence["input_json"]["mode"] == "final_as" else "interim"
    request_mode = "final" if evidence["request_mode"] == "final_as" else evidence["request_mode"]
    if mode != request_mode:
        raise ValueError("M6_MODE_INVALID")
    if mode == "final" and evidence["as_status"] != "closed":
        raise ValueError("M6_STATE_INVALID")
    if mode == "interim" and evidence["as_status"] not in {"scenario_ended", "closed"}:
        raise ValueError("M6_STATE_INVALID")
    latest = connection.execute("SELECT max(boundary_sequence) AS boundary FROM m5_c45_handoffs WHERE assessment_situation_db_id=%s AND mode=%s",
                                (evidence["as_db_id"], mode)).fetchone()["boundary"]
    if latest != evidence["boundary_sequence"]:
        raise ValueError("M6_STALE_EVIDENCE_REVISION")
    value = {"schema_version": 1, "mode": mode, "evidence_revision_id": str(evidence["id"]),
             "evidence_hash": evidence["output_hash"], "handoff_id": str(evidence["handoff_id"]),
             "handoff_checksum": evidence["envelope_checksum"], "boundary_sequence": evidence["boundary_sequence"],
             "material": evidence["input_json"], "evidence_analysis": evidence["output_json"]}
    return int(evidence["as_db_id"]), str(evidence["handoff_id"]), value


def enqueue(connection, *, evidence_revision_id: str, key: str, mechanism: dict, created_by: int):
    as_db_id, _, value = build_input(connection, evidence_revision_id)
    connection.execute("SELECT id FROM m5_assessment_situations WHERE id=%s FOR UPDATE", (as_db_id,)).fetchone()
    ih, mh = definition_checksum(value), definition_checksum(mechanism)
    existing = connection.execute("""SELECT r.* FROM m6_assessment_request_keys k
        JOIN m6_assessment_requests r ON r.id=k.request_id WHERE k.as_db_id=%s AND k.key=%s""", (as_db_id,key)).fetchone()
    if existing:
        if existing["input_hash"] != ih or existing["mechanism_hash"] != mh:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return dict(existing)
    row = connection.execute("""INSERT INTO m6_assessment_requests
        (id,as_db_id,evidence_revision_id,mode,input_json,input_hash,mechanism_json,mechanism_hash,status,created_by,synthetic_confirmed)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,'queued',%s,TRUE)
        ON CONFLICT(as_db_id,evidence_revision_id,mode,mechanism_hash) DO NOTHING RETURNING *""",
        (uuid4(),as_db_id,UUID(evidence_revision_id),value["mode"],json.dumps(value,ensure_ascii=False),ih,
         json.dumps(mechanism,ensure_ascii=False),mh,created_by)).fetchone()
    if not row:
        row = connection.execute("SELECT * FROM m6_assessment_requests WHERE as_db_id=%s AND evidence_revision_id=%s AND mode=%s AND mechanism_hash=%s",
                                 (as_db_id,UUID(evidence_revision_id),value["mode"],mh)).fetchone()
    connection.execute("INSERT INTO m6_assessment_request_keys VALUES (%s,%s,%s)", (as_db_id,key,row["id"]))
    return dict(row)


def existing_key(connection, evidence_revision_id: str, key: str, mechanism_ref: str):
    row=connection.execute("""SELECT r.* FROM m6_analysis_revisions a
        JOIN m6_assessment_request_keys k ON k.as_db_id=a.as_db_id
        JOIN m6_assessment_requests r ON r.id=k.request_id
        WHERE a.id=%s AND k.key=%s""",(UUID(evidence_revision_id),key)).fetchone()
    if row and (row["evidence_revision_id"] != UUID(evidence_revision_id)
                or row["mechanism_json"]["ref"] != mechanism_ref):
        raise ValueError("IDEMPOTENCY_CONFLICT")
    return dict(row) if row else None


def claim(connection, request_id):
    row = connection.execute("SELECT * FROM m6_assessment_requests WHERE id=%s FOR UPDATE", (UUID(str(request_id)),)).fetchone()
    if not row: raise ValueError("M6_ASSESSMENT_REQUEST_NOT_FOUND")
    if row["status"] == "succeeded": return None
    if row["status"] == "running" and connection.execute("SELECT %s > NOW() AS active", (row["lease_expires_at"],)).fetchone()["active"]: return None
    connection.execute("UPDATE m6_assessment_attempts SET status='expired' WHERE request_id=%s AND status='running'", (row["id"],))
    token, attempt = uuid4(), uuid4()
    connection.execute("UPDATE m6_assessment_requests SET status='running',lease_token=%s,lease_expires_at=NOW()+%s*INTERVAL '1 second' WHERE id=%s",
                       (token,int(row["mechanism_json"]["lease_seconds"]),row["id"]))
    connection.execute("""INSERT INTO m6_assessment_attempts(id,request_id,attempt_no,lease_token,status)
        SELECT %s,%s,COALESCE(MAX(attempt_no),0)+1,%s,'running' FROM m6_assessment_attempts WHERE request_id=%s""",
        (attempt,row["id"],token,row["id"]))
    return {**dict(row),"lease_token":token,"attempt_id":attempt}


def finish(connection, job, output, trace, error=None):
    row = connection.execute("SELECT * FROM m6_assessment_requests WHERE id=%s FOR UPDATE", (job["id"],)).fetchone()
    if row["lease_token"] != job["lease_token"] or row["status"] != "running": return False
    if connection.execute("SELECT %s <= NOW() AS expired", (row["lease_expires_at"],)).fetchone()["expired"]: return False
    if output is not None:
        output = validate_assessment(output,row["input_json"])
        revision = uuid4()
        connection.execute("""INSERT INTO m6_assessment_revisions
            (id,request_id,as_db_id,accepted_attempt_id,mode,output_json,output_hash)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (revision,row["id"],row["as_db_id"],job["attempt_id"],row["mode"],json.dumps(output,ensure_ascii=False),definition_checksum(output)))
        ia_refs, absent_refs, failure_refs = [], [], []
        if row["mode"] == "final":
            for item in output["targets"]:
                if item["status"] == "ASSESSED":
                    connection.execute("INSERT INTO m6_indicator_assessments VALUES (%s,%s,%s) ON CONFLICT(as_db_id,indicator_id) DO NOTHING",
                                       (uuid4(),row["as_db_id"],item["indicator_id"]))
                    logical = connection.execute("SELECT id FROM m6_indicator_assessments WHERE as_db_id=%s AND indicator_id=%s",
                                                 (row["as_db_id"],item["indicator_id"])).fetchone()["id"]
                    ir = uuid4(); connection.execute("""INSERT INTO m6_indicator_assessment_revisions
                        VALUES (%s,%s,%s,%s,%s::jsonb,%s)""", (ir,logical,revision,row["as_db_id"],json.dumps(item,ensure_ascii=False),definition_checksum(item)))
                    ia_refs.append({"indicator_id":item["indicator_id"],"assessment_id":str(logical),"revision_id":str(ir)})
                elif item["status"] == "NO_ASSESSMENT":
                    nr=uuid4();connection.execute("INSERT INTO m6_no_assessment_revisions VALUES (%s,%s,%s,%s,%s::jsonb,%s)",
                        (nr,revision,row["as_db_id"],item["indicator_id"],json.dumps(item,ensure_ascii=False),definition_checksum(item)))
                    absent_refs.append({"indicator_id":item["indicator_id"],"reason_revision_id":str(nr)})
                else:
                    failure_refs.append({"indicator_id":item["indicator_id"],"error_code":"TARGET_TECHNICAL_FAILURE"})
        c54 = {"schema_version":1,"contract":"C-54","mode":row["mode"],
               "status":"partial_failure" if failure_refs else "completed",
               "assessment_revision_id":str(revision),"evidence_revision_id":str(row["evidence_revision_id"]),
               "handoff_id":row["input_json"]["handoff_id"],"boundary_sequence":row["input_json"]["boundary_sequence"],
               "indicator_assessment_refs":ia_refs,"no_assessment_refs":absent_refs,
               "technical_failure_refs":failure_refs,
               "interim_targets":output["targets"] if row["mode"]=="interim" else [],"limitations":[]}
        c54id=uuid4();connection.execute("INSERT INTO m6_c54_revisions VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (c54id,revision,row["as_db_id"],UUID(c54["handoff_id"]),row["mode"],json.dumps(c54,ensure_ascii=False),definition_checksum(c54)))
        for item in output["targets"]:
            receipt_status = "technical_failure" if item["status"] == "TECHNICAL_FAILURE" else "accepted"
            receiver_payload = {"contract":"C-54","c54_revision_id":str(c54id),
                "assessment_revision_id":str(revision),"target":item,"summary":c54}
            validation = {"errors": ["TARGET_TECHNICAL_FAILURE"] if receipt_status == "technical_failure" else [],
                "methodological_result": item["status"] == "ASSESSED", "semantic_contract": True}
            connection.execute("""INSERT INTO m5_c54_receipts
                (assessment_situation_db_id,handoff_id,receipt_id,mode,indicator_id,m2_version,
                 boundary_sequence,status,payload_json,validation_json,controlled_test)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,TRUE)""",
                (row["as_db_id"],UUID(c54["handoff_id"]),uuid4(),row["mode"],item["indicator_id"],item["m2_version"],
                 c54["boundary_sequence"],receipt_status,json.dumps(receiver_payload,ensure_ascii=False),
                 json.dumps(validation,ensure_ascii=False)))
    status = "succeeded" if output is not None else "failed"
    connection.execute("UPDATE m6_assessment_attempts SET status=%s,trace_json=%s::jsonb,error_code=%s WHERE id=%s",
                       (status,json.dumps(trace,ensure_ascii=False),error,job["attempt_id"]))
    connection.execute("UPDATE m6_assessment_requests SET status=%s,lease_token=NULL,lease_expires_at=NULL WHERE id=%s", (status,row["id"]))
    return True


def read_request(connection, request_id):
    row=connection.execute("""SELECT r.id,r.status,r.created_at,a.id AS assessment_revision_id,c.id AS c54_revision_id
        FROM m6_assessment_requests r LEFT JOIN m6_assessment_revisions a ON a.request_id=r.id
        LEFT JOIN m6_c54_revisions c ON c.assessment_revision_id=a.id WHERE r.id=%s""",(UUID(str(request_id)),)).fetchone()
    if not row: raise ValueError("M6_ASSESSMENT_REQUEST_NOT_FOUND")
    return dict(row)


def read_result(connection, revision_id):
    row=connection.execute("""SELECT a.*,r.input_json,r.input_hash,c.id AS c54_id,c.payload_json,c.payload_hash
        FROM m6_assessment_revisions a JOIN m6_assessment_requests r ON r.id=a.request_id
        JOIN m6_c54_revisions c ON c.assessment_revision_id=a.id WHERE a.id=%s""",(UUID(str(revision_id)),)).fetchone()
    if not row: raise ValueError("M6_ASSESSMENT_NOT_FOUND")
    if definition_checksum(row["input_json"])!=row["input_hash"] or definition_checksum(row["output_json"])!=row["output_hash"] or definition_checksum(row["payload_json"])!=row["payload_hash"]:
        raise ValueError("CHECKSUM_MISMATCH")
    validate_assessment(row["output_json"],row["input_json"])
    ia=connection.execute("""SELECT i.indicator_id,r.id AS revision_id,r.content_json FROM m6_indicator_assessment_revisions r
        JOIN m6_indicator_assessments i ON i.id=r.indicator_assessment_id WHERE r.assessment_revision_id=%s""",(row["id"],)).fetchall()
    absent=connection.execute("SELECT indicator_id,id AS revision_id,content_json FROM m6_no_assessment_revisions WHERE assessment_revision_id=%s",(row["id"],)).fetchall()
    return {"id":row["id"],"request_id":row["request_id"],"mode":row["mode"],"input":row["input_json"],
            "output":row["output_json"],"indicator_assessments":[dict(x) for x in ia],
            "no_assessments":[dict(x) for x in absent],"c54":{"id":row["c54_id"],"payload":row["payload_json"]}}
