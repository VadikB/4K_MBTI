from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from Api import educational_contexts


pytestmark = pytest.mark.integration


@pytest.fixture
def educational_db(test_database_url, monkeypatch):
    schema = "educational_context_pytest_" + uuid4().hex
    connection = psycopg.connect(test_database_url, row_factory=dict_row)
    connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
    connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
    connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY)")
    connection.execute("CREATE TABLE organizations(id BIGSERIAL PRIMARY KEY,code TEXT UNIQUE,name TEXT)")
    connection.execute("""CREATE TABLE organization_memberships(
        organization_id BIGINT,user_id BIGINT,role TEXT,admission_source TEXT,admitted_at TIMESTAMP,
        UNIQUE(organization_id,user_id))""")
    connection.execute("""CREATE TABLE organization_assessment_assignments(
        id BIGSERIAL PRIMARY KEY,organization_id BIGINT,recipient_user_id BIGINT,assignment_ref TEXT,
        status TEXT,operation_id TEXT,request_fingerprint TEXT,revoked_at TIMESTAMP)""")
    connection.execute("""CREATE TABLE questionnaire_response_revisions(
        id BIGINT,organization_id BIGINT,assignment_ref TEXT,status TEXT)""")
    connection.execute("""CREATE TABLE assessment_personalized_profiles(
        id BIGINT,user_id BIGINT,organization_id BIGINT,assessment_configuration_id BIGINT,
        role_profile_version_id BIGINT,status TEXT)""")
    connection.execute("INSERT INTO users VALUES(42)")
    monkeypatch.setattr(educational_contexts, "load_published_role_profile", lambda _c, _id: {
        "id": 17, "checksum": "b" * 64,
    })
    monkeypatch.setattr(
        educational_contexts.assessment_programs,
        "resolve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("PROGRAM_NOT_CONNECTED")),
    )
    connection.commit()
    yield connection
    connection.close()
    with psycopg.connect(test_database_url) as cleanup:
        cleanup.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


def snapshot() -> dict:
    return {
        "schema_version": 1,
        "kind": "educational_project_assessment_context",
        "assignment_ref": "edu:4k-tg-bot:p1:a2",
        "course": {"external_id": "tba-2026", "name": "ТБА", "cohort": "М01"},
        "participant": {"local_ref": "participant:3", "agent4k_user_id": 42},
        "role": {
            "agent4k_role_profile_version_id": 17,
            "agent4k_role_profile_checksum": "b" * 64,
        },
    }


def checksum(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def test_prepare_registers_immutable_context_and_is_idempotent(educational_db):
    value = snapshot()
    first = educational_contexts.prepare(
        educational_db, snapshot=value, snapshot_checksum=checksum(value)
    )
    second = educational_contexts.prepare(
        educational_db, snapshot=value, snapshot_checksum=checksum(value)
    )
    educational_db.commit()

    assert second == first
    assert first["status"] == "awaiting_admission"
    assert set(first["reasons"]) == {
        "QUESTIONNAIRE_NOT_CONFIRMED",
        "PROGRAM_NOT_CONNECTED",
        "PERSONALIZED_PROFILE_NOT_CONFIRMED",
        "ASSIGNMENT_NOT_ACTIVE",
    }
    membership = educational_db.execute(
        "SELECT admission_source FROM organization_memberships"
    ).fetchone()
    assert membership["admission_source"] == "integration_api"
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        educational_db.execute(
            "UPDATE external_educational_contexts SET snapshot_json='{}'::jsonb"
        )


def test_prepare_rejects_contact_identity(educational_db):
    value = {**snapshot(), "participant": {**snapshot()["participant"], "email": "x@example.test"}}
    with pytest.raises(ValueError, match="CONTACT_IDENTITY_FORBIDDEN"):
        educational_contexts.prepare(
            educational_db, snapshot=value, snapshot_checksum=checksum(value)
        )


def test_prepare_uses_admitted_active_assignment(educational_db, monkeypatch):
    value = snapshot()
    first = educational_contexts.prepare(
        educational_db, snapshot=value, snapshot_checksum=checksum(value)
    )
    educational_db.execute(
        "INSERT INTO questionnaire_response_revisions VALUES(81,%s,%s,'confirmed')",
        (first["organization_id"], first["assignment_ref"]),
    )
    educational_db.execute(
        "INSERT INTO assessment_personalized_profiles VALUES(71,42,%s,61,17,'ready')",
        (first["organization_id"],),
    )
    active = educational_db.execute(
        """INSERT INTO organization_assessment_assignments(
             organization_id,recipient_user_id,assignment_ref,status,operation_id,request_fingerprint)
           VALUES(%s,42,%s,'active','human-admission','fingerprint') RETURNING id""",
        (first["organization_id"], first["assignment_ref"]),
    ).fetchone()
    monkeypatch.setattr(
        educational_contexts.assessment_programs,
        "resolve",
        lambda *_args, **_kwargs: {"assessment_configuration_id": 61},
    )
    monkeypatch.setattr(
        educational_contexts.acquaintance,
        "preparation_scope",
        lambda *_args, **_kwargs: {
            "personalized_profile_id": 71,
            "organization_id": first["organization_id"],
            "assignment_ref": first["assignment_ref"],
            "questionnaire_revision_id": 81,
            "profile_checksum": "profile-checksum",
        },
    )

    admitted = educational_contexts.prepare(
        educational_db, snapshot=value, snapshot_checksum=checksum(value)
    )
    assert admitted["status"] == "preparing"
    assert admitted["assignment_id"] == active["id"]
    assert admitted["reasons"] == []
    assert admitted["preparation_request"]["personalized_profile_id"] == 71
