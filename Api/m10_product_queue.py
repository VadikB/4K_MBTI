"""Product queue adapter; leaves the frozen synthetic QA enqueue API unchanged."""
from __future__ import annotations

import json
from uuid import UUID, uuid4

from Api.assessment_configuration import definition_checksum
from Api import m6_assessment_repository, m6_repository


def enqueue_evidence(connection, *, as_db_id, handoff_id, key, material, mechanism, created_by):
    connection.execute("SELECT id FROM m5_assessment_situations WHERE id=%s FOR UPDATE", (as_db_id,)).fetchone()
    input_hash, mechanism_hash = definition_checksum(material), definition_checksum(mechanism)
    existing = m6_repository.existing_key(connection, handoff_id, key, mechanism["ref"])
    if existing:
        if existing["input_hash"] != input_hash or existing["mechanism_hash"] != mechanism_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return dict(existing)
    row = connection.execute("""INSERT INTO m6_processing_requests
        (id,as_db_id,handoff_id,mode,input_json,input_hash,mechanism_json,mechanism_hash,status,created_by,synthetic_confirmed)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,'queued',%s,FALSE)
        ON CONFLICT(as_db_id,mode,input_hash,mechanism_hash) DO NOTHING RETURNING *""",
        (uuid4(), as_db_id, UUID(handoff_id), material["mode"], json.dumps(material, ensure_ascii=False), input_hash,
         json.dumps(mechanism, ensure_ascii=False), mechanism_hash, created_by)).fetchone()
    if not row:
        row = connection.execute("""SELECT * FROM m6_processing_requests
            WHERE as_db_id=%s AND mode=%s AND input_hash=%s AND mechanism_hash=%s""",
            (as_db_id, material["mode"], input_hash, mechanism_hash)).fetchone()
    connection.execute("INSERT INTO m6_request_keys VALUES (%s,%s,%s)", (as_db_id, key, row["id"]))
    return dict(row)


def enqueue_assessment(connection, *, evidence_revision_id, key, mechanism, created_by):
    as_db_id, _, value = m6_assessment_repository.build_input(connection, evidence_revision_id)
    connection.execute("SELECT id FROM m5_assessment_situations WHERE id=%s FOR UPDATE", (as_db_id,)).fetchone()
    input_hash, mechanism_hash = definition_checksum(value), definition_checksum(mechanism)
    existing = m6_assessment_repository.existing_key(connection, evidence_revision_id, key, mechanism["ref"])
    if existing:
        if existing["input_hash"] != input_hash or existing["mechanism_hash"] != mechanism_hash:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return existing
    row = connection.execute("""INSERT INTO m6_assessment_requests
        (id,as_db_id,evidence_revision_id,mode,input_json,input_hash,mechanism_json,mechanism_hash,status,created_by,synthetic_confirmed)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,'queued',%s,FALSE)
        ON CONFLICT(as_db_id,evidence_revision_id,mode,mechanism_hash) DO NOTHING RETURNING *""",
        (uuid4(), as_db_id, UUID(evidence_revision_id), value["mode"], json.dumps(value, ensure_ascii=False), input_hash,
         json.dumps(mechanism, ensure_ascii=False), mechanism_hash, created_by)).fetchone()
    if not row:
        row = connection.execute("""SELECT * FROM m6_assessment_requests
            WHERE as_db_id=%s AND evidence_revision_id=%s AND mode=%s AND mechanism_hash=%s""",
            (as_db_id, UUID(evidence_revision_id), value["mode"], mechanism_hash)).fetchone()
    connection.execute("INSERT INTO m6_assessment_request_keys VALUES (%s,%s,%s)", (as_db_id, key, row["id"]))
    return dict(row)
