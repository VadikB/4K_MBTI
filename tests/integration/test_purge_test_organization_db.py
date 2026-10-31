import hashlib
from uuid import uuid4

import psycopg
import pytest

from Api.deletion_ledger import append_intent, assert_reconciled, ensure_receipt_schema, record_receipt
from scripts.purge_test_organization import (
    build_account_purge_plan, build_purge_plan, purge_account,
    purge_organization, purge_plan_fingerprint,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def purge_db(test_database_url):
    schema = "organization_purge_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY, email TEXT NOT NULL, active_profile_id BIGINT)")
        connection.execute("""CREATE TABLE user_role_profiles(
            id BIGINT PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            profile TEXT NOT NULL)""")
        connection.execute("""ALTER TABLE users ADD CONSTRAINT users_active_profile_fk
            FOREIGN KEY(active_profile_id) REFERENCES user_role_profiles(id)""")
        connection.execute("""CREATE TABLE user_identities(
            id BIGINT PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE)""")
        connection.execute("""CREATE TABLE auth_password_credentials(
            id BIGINT PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE auth_action_tokens(
            id BIGINT PRIMARY KEY,email TEXT NOT NULL,token_hash TEXT NOT NULL)""")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY, code TEXT UNIQUE, name TEXT)")
        connection.execute("""CREATE TABLE organization_invitations(
            id BIGINT PRIMARY KEY,
            organization_id BIGINT REFERENCES organizations(id),
            created_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            payload TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE program_definitions(
            id BIGINT PRIMARY KEY,
            created_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            status TEXT NOT NULL,
            definition TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE questionnaire_response_revisions(
            id BIGINT PRIMARY KEY,organization_id BIGINT REFERENCES organizations(id),
            uploaded_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            confirmed_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            status TEXT NOT NULL,answers_json JSONB NOT NULL)""")
        connection.execute("""CREATE TABLE organization_assessment_assignments(
            id BIGINT PRIMARY KEY,organization_id BIGINT REFERENCES organizations(id),
            recipient_user_id BIGINT REFERENCES users(id),
            created_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            status TEXT NOT NULL,assignment_ref TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE organization_assessment_program_connections(
            id BIGINT PRIMARY KEY,organization_id BIGINT REFERENCES organizations(id),
            connected_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            is_current BOOLEAN NOT NULL,program_ref TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE organization_memberships(
            id BIGSERIAL PRIMARY KEY,
            organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
            user_id BIGINT REFERENCES users(id),
            UNIQUE(organization_id,user_id))""")
        connection.execute("""CREATE TABLE assessment_profiles(
            id BIGSERIAL PRIMARY KEY,
            organization_id BIGINT REFERENCES organizations(id) ON DELETE RESTRICT,
            snapshot TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE assessment_results(
            id BIGSERIAL PRIMARY KEY,
            profile_id BIGINT REFERENCES assessment_profiles(id) ON DELETE RESTRICT,
            result TEXT NOT NULL)""")
        connection.execute("CREATE TABLE user_sessions(id BIGINT PRIMARY KEY, user_id BIGINT REFERENCES users(id))")
        connection.execute("""CREATE TABLE m5_cycles(
            id BIGINT PRIMARY KEY,organization_id BIGINT REFERENCES organizations(id),
            owner_user_id BIGINT REFERENCES users(id),status TEXT NOT NULL)""")
        connection.execute("""CREATE FUNCTION prevent_result_delete() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION 'immutable result'; END; $$ LANGUAGE plpgsql""")
        connection.execute("""CREATE TRIGGER immutable_result BEFORE DELETE ON assessment_results
            FOR EACH ROW EXECUTE FUNCTION prevent_result_delete()""")
        connection.execute("""INSERT INTO users(id,email) VALUES
            (10, 'orphan@example.test'),
            (20, 'other@example.test'),
            (30, 'shared@example.test')""")
        connection.execute("INSERT INTO user_role_profiles VALUES (1000,10,'orphan profile'),(3000,30,'shared profile')")
        connection.execute("UPDATE users SET active_profile_id=1000 WHERE id=10")
        connection.execute("UPDATE users SET active_profile_id=3000 WHERE id=30")
        connection.execute("""INSERT INTO user_identities VALUES
            (101,10,'orphan@example.test',TRUE),
            (111,10,'verified-alias@example.test',TRUE),
            (112,10,'unverified-alias@example.test',FALSE),
            (301,30,'shared@example.test',TRUE)""")
        connection.execute("INSERT INTO auth_password_credentials VALUES (102,10,'orphan@example.test'),(302,30,'shared@example.test')")
        connection.execute("INSERT INTO auth_action_tokens VALUES (103,'orphan@example.test','old-token'),(303,'shared@example.test','shared-token')")
        connection.execute("""INSERT INTO auth_action_tokens VALUES
            (113,'verified-alias@example.test','verified-alias-token'),
            (114,'unverified-alias@example.test','unverified-control-token')""")
        connection.execute("INSERT INTO organizations VALUES (1, 'purge-me', 'Purge me'), (2, 'keep-me', 'Keep me')")
        connection.execute("""INSERT INTO organization_invitations VALUES
            (701,1,10,'owned by organization A'),
            (702,2,10,'foreign content authored by A'),
            (703,2,20,'foreign control')""")
        connection.execute("""INSERT INTO program_definitions VALUES
            (801,10,'published','shared published artifact'),
            (802,20,'published','foreign control')""")
        connection.execute("""INSERT INTO questionnaire_response_revisions VALUES
            (901,2,10,10,'confirmed','{"answer":"foreign questionnaire"}'),
            (902,2,20,20,'confirmed','{"answer":"foreign control"}')""")
        connection.execute("""INSERT INTO organization_assessment_assignments VALUES
            (911,2,20,10,'active','foreign-assignment'),
            (912,2,30,20,'active','foreign-control')""")
        connection.execute("""INSERT INTO organization_assessment_program_connections VALUES
            (921,2,10,TRUE,'foreign-program'),
            (922,2,20,FALSE,'foreign-control')""")
        connection.execute("""INSERT INTO organization_memberships(organization_id,user_id) VALUES
            (1,10),(1,30),(2,20),(2,30)""")
        profile_id = connection.execute(
            "INSERT INTO assessment_profiles(organization_id,snapshot) VALUES (1,'frozen') RETURNING id"
        ).fetchone()[0]
        connection.execute("INSERT INTO assessment_results(profile_id,result) VALUES (%s,'frozen')", (profile_id,))
        connection.execute("INSERT INTO user_sessions VALUES (100,10),(200,20),(300,30)")
        connection.execute("INSERT INTO m5_cycles VALUES(500,1,10,'active'),(600,2,30,'active')")
        connection.commit()
    try:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            connection.commit()
            yield connection
    finally:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


def test_dry_run_plan_does_not_change_data(purge_db):
    counts, _, _ = build_purge_plan(purge_db, 1)
    purge_db.rollback()
    assert any(name.endswith(".organizations") and count == 1 for name, count in counts.items())
    assert any(name.endswith(".assessment_results") and count == 1 for name, count in counts.items())
    assert purge_db.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 2
    assert purge_db.execute("SELECT COUNT(*) FROM assessment_results").fetchone()[0] == 1


def test_full_purge_removes_orphan_user_and_preserves_shared_user(purge_db):
    counts = purge_organization(purge_db, organization_id=1, confirm_code="purge-me")
    purge_db.commit()

    assert any(name.endswith(".assessment_results") and count == 1 for name, count in counts.items())
    assert purge_db.execute("SELECT id FROM organizations ORDER BY id").fetchall() == [(2,)]
    assert purge_db.execute("SELECT id FROM users ORDER BY id").fetchall() == [(20,), (30,)]
    assert purge_db.execute("SELECT user_id FROM user_identities ORDER BY user_id").fetchall() == [(30,)]
    assert purge_db.execute("SELECT user_id FROM auth_password_credentials ORDER BY user_id").fetchall() == [(30,)]
    assert purge_db.execute("SELECT id FROM user_role_profiles ORDER BY id").fetchall() == [(3000,)]
    assert purge_db.execute("SELECT id FROM user_sessions ORDER BY id").fetchall() == [(200,), (300,)]
    assert purge_db.execute("SELECT id FROM m5_cycles ORDER BY id").fetchall() == [(600,)]
    assert purge_db.execute("SELECT id,created_by_user_id FROM organization_invitations ORDER BY id").fetchall() == [
        (702, None), (703, 20)
    ]
    assert purge_db.execute("SELECT id,created_by_user_id FROM program_definitions ORDER BY id").fetchall() == [
        (801, None), (802, 20)
    ]
    assert purge_db.execute("""SELECT id,uploaded_by_user_id,confirmed_by_user_id,status,
        answers_json->>'answer' FROM questionnaire_response_revisions ORDER BY id""").fetchall() == [
        (901, None, None, 'confirmed', 'foreign questionnaire'),
        (902, 20, 20, 'confirmed', 'foreign control'),
    ]
    assert purge_db.execute("""SELECT id,recipient_user_id,created_by_user_id,status,assignment_ref
        FROM organization_assessment_assignments ORDER BY id""").fetchall() == [
        (911, 20, None, 'active', 'foreign-assignment'),
        (912, 30, 20, 'active', 'foreign-control'),
    ]
    assert purge_db.execute("""SELECT id,connected_by_user_id,is_current,program_ref
        FROM organization_assessment_program_connections ORDER BY id""").fetchall() == [
        (921, None, True, 'foreign-program'),
        (922, 20, False, 'foreign-control'),
    ]
    assert purge_db.execute("SELECT email FROM auth_action_tokens ORDER BY email").fetchall() == [
        ('shared@example.test',), ('unverified-alias@example.test',)
    ]
    assert purge_db.execute("SELECT token_hash FROM auth_action_tokens ORDER BY token_hash").fetchall() == [
        ('shared-token',), ('unverified-control-token',)
    ]
    purge_db.execute("DELETE FROM organization_memberships WHERE organization_id=2 AND user_id=30")
    purge_db.execute("INSERT INTO organization_memberships(organization_id,user_id) VALUES (2,30)")
    assert purge_db.execute(
        "SELECT COUNT(*) FROM organization_memberships WHERE organization_id=2 AND user_id=30"
    ).fetchone()[0] == 1
    assert purge_db.execute("SELECT COUNT(*) FROM assessment_profiles").fetchone()[0] == 0
    assert purge_db.execute("SELECT COUNT(*) FROM assessment_results").fetchone()[0] == 0
    assert purge_db.execute(
        "SELECT code_sha256 FROM organization_deletion_tombstones"
    ).fetchone()[0] == hashlib.sha256(b"purge-me").hexdigest()
    purge_db.execute("INSERT INTO organizations VALUES(3,'purge-me','Recreated clean')")
    purge_db.execute("INSERT INTO users(id,email) VALUES(40,'orphan@example.test')")
    purge_db.execute("INSERT INTO organization_memberships(organization_id,user_id) VALUES(3,40)")
    assert purge_db.execute("SELECT COUNT(*) FROM auth_password_credentials WHERE email='orphan@example.test'").fetchone()[0] == 0
    assert purge_db.execute("SELECT COUNT(*) FROM auth_action_tokens WHERE email='orphan@example.test'").fetchone()[0] == 0
    assert purge_db.execute("SELECT COUNT(*) FROM m5_cycles WHERE owner_user_id=40").fetchone()[0] == 0


def test_detached_account_purge_removes_credentials_and_preserves_other_accounts(purge_db):
    purge_db.execute('DELETE FROM organization_memberships WHERE user_id=20')
    purge_db.execute("INSERT INTO user_identities VALUES(201,20,'other@example.test',TRUE)")
    purge_db.execute("INSERT INTO auth_password_credentials VALUES(202,20,'other@example.test')")
    purge_db.commit()
    counts,_,_ = build_account_purge_plan(purge_db,20)
    assert any(name.endswith('.auth_password_credentials') for name in counts)
    purge_db.rollback()
    purge_account(purge_db,user_id=20)
    purge_db.commit()
    assert purge_db.execute('SELECT id FROM users ORDER BY id').fetchall() == [(10,),(30,)]
    assert purge_db.execute("SELECT COUNT(*) FROM auth_password_credentials WHERE email='other@example.test'").fetchone()[0] == 0
    assert purge_db.execute('SELECT COUNT(*) FROM organizations').fetchone()[0] == 2
    assert purge_db.execute("SELECT id,created_by_user_id FROM organization_invitations ORDER BY id").fetchall() == [
        (701, 10), (702, 10), (703, None)
    ]
    assert purge_db.execute("SELECT id,created_by_user_id FROM program_definitions ORDER BY id").fetchall() == [
        (801, 10), (802, None)
    ]


def test_unknown_required_actor_reference_blocks_preview_without_data_loss(purge_db):
    purge_db.execute("""CREATE TABLE unsafe_foreign_authorship(
        id BIGINT PRIMARY KEY,actor_reference BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        payload TEXT NOT NULL)""")
    purge_db.execute("INSERT INTO unsafe_foreign_authorship VALUES(1,20,'foreign content')")
    purge_db.commit()

    with pytest.raises(RuntimeError, match='PURGE_ATTRIBUTION_SCHEMA_UNSAFE'):
        build_account_purge_plan(purge_db, 20)
    purge_db.rollback()

    assert purge_db.execute("SELECT id,email FROM users WHERE id=20").fetchone() == (20, 'other@example.test')
    assert purge_db.execute("SELECT actor_reference,payload FROM unsafe_foreign_authorship").fetchone() == (
        20, 'foreign content',
    )


def test_intent_callback_runs_only_after_preview_fingerprint_validation(purge_db):
    build_purge_plan(purge_db, 1)
    fingerprint = purge_plan_fingerprint(purge_db)
    purge_db.rollback()
    callbacks = []

    with pytest.raises(ValueError, match='PURGE_PREVIEW_STALE'):
        purge_organization(purge_db, organization_id=1, confirm_code='purge-me',
            expected_fingerprint='0' * 64, on_validated=callbacks.append)
    purge_db.rollback()
    assert callbacks == []

    purge_organization(purge_db, organization_id=1, confirm_code='purge-me',
        expected_fingerprint=fingerprint, on_validated=callbacks.append)
    assert callbacks == [fingerprint]


def test_external_ledger_blocks_startup_until_restore_replay_is_receipted(purge_db, tmp_path):
    ledger=tmp_path/'deletion-ledger.jsonl'
    ledger.touch(mode=0o600)
    counts,_,_=build_purge_plan(purge_db,1)
    fingerprint='a'*64
    intent=append_intent(str(ledger),operation_id='purge-restore-0001',
        target_type='organization',target_id=1,fingerprint=fingerprint)
    ensure_receipt_schema(purge_db)
    purge_db.commit()
    with pytest.raises(RuntimeError,match='DELETION_LEDGER_REPLAY_REQUIRED'):
        assert_reconciled(purge_db,str(ledger))
    purge_db.rollback()
    purge_organization(purge_db,organization_id=1,confirm_code='purge-me')
    record_receipt(purge_db,intent)
    purge_db.commit()
    assert_reconciled(purge_db,str(ledger))
    assert sum(counts.values()) > 0
