from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from Api import telegram_subjects as subjects, telegram_channel as channel

pytestmark = pytest.mark.integration


@pytest.fixture
def db(test_database_url):
    schema = "telegram_subject_pytest_" + uuid4().hex
    c = psycopg.connect(test_database_url, row_factory=dict_row)
    c.execute(
        psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema))
    )
    c.execute(
        psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema))
    )
    c.execute("""CREATE TABLE users(id BIGSERIAL PRIMARY KEY,full_name TEXT,email TEXT,
        role_id BIGINT,job_description TEXT,phone TEXT,company_industry TEXT)""")
    c.execute(
        "CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN NOT NULL)"
    )
    c.execute("""CREATE TABLE organization_memberships(organization_id BIGINT,user_id BIGINT,role TEXT,
        admission_source TEXT,admitted_at TIMESTAMP,is_participant BOOLEAN DEFAULT TRUE,UNIQUE(organization_id,user_id))""")
    c.execute(
        """CREATE TABLE organization_assessment_assignments(id BIGSERIAL PRIMARY KEY,
        organization_id BIGINT,recipient_user_id BIGINT,assignment_ref TEXT,created_by_user_id BIGINT,
        questionnaire_revision_id BIGINT,status TEXT,operation_id TEXT,request_fingerprint TEXT,revoked_at TIMESTAMP)"""
    )
    c.execute("""CREATE UNIQUE INDEX assignment_active_unique ON organization_assessment_assignments
        (organization_id,recipient_user_id,assignment_ref) WHERE status='active' AND revoked_at IS NULL""")
    c.execute("""CREATE TABLE assessment_program_definitions(id BIGINT,code TEXT,version TEXT,name TEXT,
        status TEXT,assessment_configuration_id BIGINT,assignment_ref TEXT,definition_checksum TEXT)""")
    c.execute(
        "CREATE TABLE assessment_program_allowed_roles(program_definition_id BIGINT,role_profile_version_id BIGINT)"
    )
    c.execute("CREATE TABLE user_identities(user_id BIGINT,provider TEXT)")
    c.execute("CREATE TABLE web_user_sessions(user_id BIGINT)")
    c.execute("INSERT INTO organizations VALUES(17,TRUE),(18,TRUE)")
    channel.ensure_schema(c)
    c.commit()
    yield c, test_database_url, schema
    c.close()
    with psycopg.connect(test_database_url) as cleanup:
        cleanup.execute(
            psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(
                psycopg.sql.Identifier(schema)
            )
        )


def test_subject_is_opaque_idempotent_and_not_a_login_account(db):
    c, _, _ = db
    subject = str(uuid4())
    first = subjects.resolve(c, external_subject_ref=subject, organization_id=17)
    second = subjects.resolve(c, external_subject_ref=subject, organization_id=17)
    assert first == {"external_subject_ref": subject, "status": "provisioned"}
    assert second == {"external_subject_ref": subject, "status": "existing"}
    assert c.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 1
    user = c.execute("SELECT * FROM users").fetchone()
    assert all(
        user[x] is None
        for x in ("email", "role_id", "job_description", "phone", "company_industry")
    )
    assert c.execute("SELECT count(*) AS n FROM user_identities").fetchone()["n"] == 0
    assert c.execute("SELECT count(*) AS n FROM web_user_sessions").fetchone()["n"] == 0
    with pytest.raises(ValueError, match="SUBJECT_ORGANIZATION_CONFLICT"):
        subjects.resolve(c, external_subject_ref=subject, organization_id=18)
    assert c.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 1


def test_subject_mapping_cannot_be_rebound(db):
    c, _, _ = db
    subject = str(uuid4())
    subjects.resolve(c, external_subject_ref=subject, organization_id=17)
    c.commit()
    with pytest.raises(psycopg.Error, match="immutable"):
        c.execute(
            "UPDATE telegram_assessment_subjects SET organization_id=18 WHERE external_subject_ref=%s",
            (subject,),
        )
    c.rollback()
    assert subjects.load(c, subject, 17)["organization_id"] == 17


def test_channel_replay_returns_committed_result_without_reapplying(db, monkeypatch):
    c, url, schema = db

    @contextmanager
    def factory():
        with psycopg.connect(url, row_factory=dict_row) as conn:
            conn.execute(
                psycopg.sql.SQL("SET search_path TO {}").format(
                    psycopg.sql.Identifier(schema)
                )
            )
            yield conn

    subject = str(uuid4())
    subjects.resolve(c, external_subject_ref=subject, organization_id=17)
    owner = subjects.load(c, subject, 17)["runtime_owner_id"]
    c.execute(
        """INSERT INTO external_educational_contexts(source_system,assignment_ref,organization_id,
        recipient_user_id,external_subject_ref,runtime_assignment_ref,status,snapshot_json,snapshot_checksum)
        VALUES('4k_tg_bot','synthetic-ref',17,%s,%s,'canonical','awaiting_admission','{}','checksum')""",
        (owner, subject),
    )
    request, request_hash = channel._channel_request(
        assignment_ref="synthetic-ref",
        action_id="old",
        expected_revision=1,
        action_input={"kind": "confirm"},
    )
    operation = channel._reserve_channel_operation(
        c,
        assignment_ref="synthetic-ref",
        idempotency_key="key",
        request=request,
        request_checksum=request_hash,
        execution={},
    )
    saved = {
        "schema_version": 1,
        "assignment_ref": "synthetic-ref",
        "state": "waiting",
        "revision": 2,
    }
    channel._complete_channel_operation(c, operation_id=operation["id"], result=saved)
    c.commit()

    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must not execute runtime/LLM again")

    monkeypatch.setattr(channel, "_require_current_action", forbidden)
    monkeypatch.setattr(channel, "refresh", forbidden)
    assert (
        channel.apply_channel_action(
            factory,
            assignment_ref="synthetic-ref",
            action_id="old",
            expected_revision=1,
            action_input={"kind": "confirm"},
            idempotency_key="key",
        )
        == saved
    )
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        channel.apply_channel_action(
            factory,
            assignment_ref="synthetic-ref",
            action_id="old",
            expected_revision=1,
            action_input={"kind": "text", "text": "different"},
            idempotency_key="key",
        )


def test_prepare_preserves_external_ref_and_waits_for_canonical_admission(
    db, monkeypatch
):
    c, _, _ = db
    subject = str(uuid4())
    subjects.resolve(c, external_subject_ref=subject, organization_id=17)
    c.execute(
        "INSERT INTO assessment_program_definitions VALUES(1,'synthetic','1','Synthetic','published',11,'canonical-ref','program-checksum')"
    )
    c.execute("INSERT INTO assessment_program_allowed_roles VALUES(1,2)")
    monkeypatch.setattr(
        channel,
        "load_published_role_profile",
        lambda c, id: {"id": 2, "checksum": "role-checksum"},
    )
    monkeypatch.setattr(
        channel,
        "list_published_configurations",
        lambda c: [
            {
                "id": 11,
                "ref": "agent4k:configuration:11",
                "reference_checksum": "config-checksum",
            }
        ],
    )
    snapshot = {
        "schema_version": 1,
        "kind": "educational_project_assessment_context",
        "assignment_ref": "external-bot-ref",
        "participant": {"external_subject_ref": subject},
        "role": {
            "agent4k_role_profile_version_id": 2,
            "agent4k_role_profile_checksum": "role-checksum",
        },
        "assessment_spec": {
            "assessment_configuration_ref": "agent4k:configuration:11",
            "assessment_configuration_checksum": "config-checksum",
        },
    }

    def no_program(*args, **kwargs):
        assert kwargs["assignment_ref"] == "canonical-ref"
        raise ValueError("PROGRAM_NOT_CONNECTED")

    monkeypatch.setattr(channel.assessment_programs, "resolve", no_program)
    monkeypatch.setattr(
        channel.questionnaire_sources,
        "assignment_readiness",
        lambda *args, **kwargs: {"status": "waiting"},
    )
    value = channel.prepare(
        c,
        snapshot=snapshot,
        snapshot_checksum=channel.checksum(snapshot),
        organization_id=17,
    )
    assert value["assignment_ref"] == "external-bot-ref"
    assert value["assignment_id"] is None
    assert value["reasons"] == ["PROGRAM_NOT_CONNECTED", "QUESTIONNAIRE_NOT_CONFIRMED"]
    assert (
        c.execute(
            "SELECT count(*) AS n FROM organization_assessment_assignments"
        ).fetchone()["n"]
        == 0
    )
    monkeypatch.setattr(
        channel.assessment_programs,
        "resolve",
        lambda *args, **kwargs: {"assessment_configuration_id": 11},
    )
    monkeypatch.setattr(
        channel.questionnaire_sources,
        "assignment_readiness",
        lambda *args, **kwargs: {"status": "ready", "questionnaire_revision_id": 21},
    )
    bound = []
    monkeypatch.setattr(
        channel.assessment_assignment_sources,
        "bind",
        lambda c, **kwargs: bound.append(kwargs),
    )

    def no_profile(c, **kwargs):
        raise ValueError("W02_MANDATORY_STEPS_REQUIRED")

    monkeypatch.setattr(channel.acquaintance, "preparation_scope", no_profile)
    value = channel.prepare(
        c,
        snapshot=snapshot,
        snapshot_checksum=channel.checksum(snapshot),
        organization_id=17,
    )
    assert value["assignment_id"] is not None and value["preparation_request"] is None
    assert value["reasons"] == ["W02_MANDATORY_STEPS_REQUIRED"]
    assert (
        bound[0]["questionnaire_revision_id"] == 21 and bound[0]["role_version_id"] == 2
    )
    assignment = c.execute(
        "SELECT * FROM organization_assessment_assignments"
    ).fetchone()
    assert assignment["assignment_ref"] == "canonical-ref"
    assert channel.context(c, "external-bot-ref")["snapshot_json"] == snapshot
    changed = {**snapshot, "extra": "new"}
    with pytest.raises(ValueError, match="ASSIGNMENT_REF_CONFLICT"):
        channel.prepare(
            c,
            snapshot=changed,
            snapshot_checksum=channel.checksum(changed),
            organization_id=17,
        )
