"""Operational SQL guards in an owned DB. All program/actor metadata is SYNTHETIC."""
from copy import deepcopy
import json
from pathlib import Path

import psycopg
import pytest

from Api import assessment_programs
from tests.integration.test_arch30_program_definition_db import program_db

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = json.loads((ROOT / "docs/evc/evidence/pilot-program-publication-preflight/operations-proposal.json").read_bytes())
RETIRE_SQL = PROPOSAL["retirement"]["sql_template"]


@pytest.fixture
def release_db(program_db, request):
    c, unrelated = program_db
    requested_status = getattr(request, "param", "published")

    def add(version, status):
        checksum = assessment_programs.definition_checksum(
            code="specialist_pilot", version=version, name="SYNTHETIC operational guard",
            assignment_ref="specialist-pilot", mode="dialogue",
            configuration_id=30, catalog_version_id=20, role_version_ids=[50],
            source_refs={"synthetic": True},
        )
        row = c.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,
             catalog_version_id,source_refs_json,definition_checksum,published_by_user_id)
            VALUES('specialist_pilot',%s,'SYNTHETIC operational guard','specialist-pilot',
                'dialogue','draft',30,20,'{"synthetic":true}',%s,1) RETURNING id""",
            (version, checksum)).fetchone()
        ident = row["id"]
        c.execute("INSERT INTO assessment_program_allowed_roles VALUES(%s,50,0)", (ident,))
        if status != "draft":
            c.execute("""UPDATE assessment_program_definitions SET status='published',published_at=NOW()
                WHERE id=%s""", (ident,))
        if status == "retired":
            c.execute("UPDATE assessment_program_definitions SET status='retired' WHERE id=%s", (ident,))
        return ident, checksum

    legacy, _ = add("1.1", "published")
    target, checksum = add("1.2", requested_status)
    c.commit()
    return c, target, checksum, legacy, unrelated


def snapshot(c):
    return {
        "programs": [dict(row) for row in c.execute(
            "SELECT * FROM assessment_program_definitions ORDER BY id").fetchall()],
        "roles": [dict(row) for row in c.execute(
            "SELECT * FROM assessment_program_allowed_roles ORDER BY program_definition_id,display_order").fetchall()],
    }


@pytest.mark.parametrize("release_db,mode", [
    ("published", "missing_id"),
    ("published", "wrong_checksum"),
    ("published", "wrong_code"),
    ("published", "wrong_version"),
    ("draft", "same"),
    ("retired", "same"),
    ("published", "current_connection"),
    ("published", "historical_connection"),
], indirect=["release_db"])
def test_retirement_guard_rejects_unapproved_target_or_any_connection(release_db, mode):
    c, target, checksum, legacy, unrelated = release_db
    chosen = target
    if mode == "missing_id":
        chosen = -1
    elif mode == "wrong_checksum":
        checksum = "0" * 64
    elif mode == "wrong_code":
        chosen = unrelated
        checksum = c.execute("SELECT definition_checksum FROM assessment_program_definitions WHERE id=%s",
                             (chosen,)).fetchone()["definition_checksum"]
    elif mode == "wrong_version":
        chosen = legacy
        checksum = c.execute("SELECT definition_checksum FROM assessment_program_definitions WHERE id=%s",
                             (chosen,)).fetchone()["definition_checksum"]
    elif mode in {"current_connection", "historical_connection"}:
        c.execute("""INSERT INTO organization_assessment_program_connections
            (organization_id,program_definition_id,connected_by_user_id,operation_id,
             request_fingerprint,is_current)
            VALUES(10,%s,1,'synthetic-guard','synthetic-guard',%s)""",
            (target, mode == "current_connection"))
        c.commit()
    before = snapshot(c)
    assert c.execute(RETIRE_SQL, (chosen, checksum)).fetchall() == []
    c.rollback()
    assert snapshot(c) == before


def test_exact_retirement_preserves_every_field_role_and_old_program(release_db):
    c, target, checksum, _, _ = release_db
    before = snapshot(c)
    locked = c.execute("SELECT * FROM assessment_program_definitions WHERE id=%s FOR UPDATE",
                       (target,)).fetchone()
    assert locked["status"] == "published" and locked["definition_checksum"] == checksum
    assert c.execute("SELECT count(*) AS n FROM organization_assessment_program_connections "
                     "WHERE program_definition_id=%s", (target,)).fetchone()["n"] == 0
    changed = c.execute(RETIRE_SQL, (target, checksum)).fetchall()
    assert len(changed) == 1 and changed[0]["status"] == "retired"
    expected = deepcopy(before)
    next(row for row in expected["programs"] if row["id"] == target)["status"] = "retired"
    assert snapshot(c) == expected
    c.commit()
    assert snapshot(c) == expected
    assert c.execute(RETIRE_SQL, (target, checksum)).fetchall() == []
    assert target not in {row["id"] for row in assessment_programs.list_published(c)}
    with pytest.raises(ValueError, match="PROGRAM_NOT_AVAILABLE"):
        assessment_programs.connect(c, organization_id=10, program_definition_id=target,
            actor_user_id=1, operation_id="synthetic-retired-denied")
    c.rollback()


@pytest.mark.parametrize("release_db", ["published", "retired"], indirect=True)
@pytest.mark.parametrize("mutation", [
    "UPDATE assessment_program_definitions SET name='changed' WHERE id=%s",
    "DELETE FROM assessment_program_definitions WHERE id=%s",
    "DELETE FROM assessment_program_allowed_roles WHERE program_definition_id=%s",
])
def test_published_or_retired_definition_and_roles_stay_immutable(release_db, mutation):
    c, target, _, _, _ = release_db
    before = snapshot(c)
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        c.execute(mutation, (target,))
    c.rollback()
    assert snapshot(c) == before


@pytest.mark.parametrize("release_db", ["retired"], indirect=True)
def test_retirement_is_not_inverse_republication(release_db):
    c, target, _, _, _ = release_db
    before = snapshot(c)
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        c.execute("UPDATE assessment_program_definitions SET status='published' WHERE id=%s", (target,))
    c.rollback()
    assert snapshot(c) == before


def test_failure_after_status_update_can_rollback_before_commit(release_db):
    c, target, checksum, _, _ = release_db
    before = snapshot(c)
    try:
        assert len(c.execute(RETIRE_SQL, (target, checksum)).fetchall()) == 1
        raise RuntimeError("SYNTHETIC_POST_UPDATE_CHECK_FAILURE")
    except RuntimeError:
        c.rollback()
    assert snapshot(c) == before
