import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest

from Api.deletion_ledger import append_intent, assert_reconciled, ensure_receipt_schema, record_receipt
from scripts.purge_test_organization import (
    build_account_purge_plan, build_purge_plan, purge_account,
    purge_organization, purge_plan_fingerprint,
    require_account_plan_organization_scope,
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


def _validate_organization_two_plan(connection, tables, foreign_keys):
    require_account_plan_organization_scope(connection, user_id=20, organization_ids=[2],
        tables=tables, foreign_keys=foreign_keys)


def test_org_admin_purge_authorizes_own_scope_and_preserves_foreign_rows(purge_db):
    # Shared, unscoped published-artifact attribution requires a superadmin;
    # this target has no such attribution in the allowed scenario.
    purge_db.execute('UPDATE program_definitions SET created_by_user_id=NULL WHERE created_by_user_id=20')
    counts = purge_account(purge_db, user_id=20,
        validate_scope=lambda tables, keys: _validate_organization_two_plan(purge_db, tables, keys))
    purge_db.commit()
    assert any(name.endswith('.users') and value == 1 for name, value in counts.items())
    assert purge_db.execute('SELECT id FROM users ORDER BY id').fetchall() == [(10,), (30,)]
    assert purge_db.execute('SELECT id FROM organizations ORDER BY id').fetchall() == [(1,), (2,)]
    assert purge_db.execute('SELECT id FROM m5_cycles ORDER BY id').fetchall() == [(500,), (600,)]


@pytest.mark.parametrize('foreign_dependency', ['cycle', 'indirect_parent', 'attribution', 'other_owner', 'unscoped_attribution'])
def test_org_admin_purge_checks_entire_destructive_and_attribution_scope(purge_db, foreign_dependency):
    if foreign_dependency != 'unscoped_attribution':
        purge_db.execute('UPDATE program_definitions SET created_by_user_id=NULL WHERE created_by_user_id=20')
    if foreign_dependency == 'cycle':
        purge_db.execute("INSERT INTO m5_cycles VALUES(700,1,20,'active')")
    elif foreign_dependency == 'indirect_parent':
        purge_db.execute('''CREATE TABLE indirect_account_record(id BIGINT PRIMARY KEY,
            user_id BIGINT REFERENCES users(id), cycle_id BIGINT REFERENCES m5_cycles(id))''')
        purge_db.execute('INSERT INTO indirect_account_record VALUES(1,20,500)')
    elif foreign_dependency == 'attribution':
        purge_db.execute('UPDATE organization_invitations SET organization_id=1 WHERE id=703')
    elif foreign_dependency == 'other_owner':
        purge_db.execute("INSERT INTO auth_password_credentials VALUES(999,30,'other@example.test')")
    purge_db.commit()
    callbacks = []
    with pytest.raises(ValueError, match='ACCOUNT_PURGE_SCOPE_FORBIDDEN'):
        purge_account(purge_db, user_id=20, on_validated=callbacks.append,
            validate_scope=lambda tables, keys: _validate_organization_two_plan(purge_db, tables, keys))
    purge_db.rollback()
    assert callbacks == []
    assert purge_db.execute('SELECT id FROM users ORDER BY id').fetchall() == [(10,), (20,), (30,)]
    assert purge_db.execute('SELECT COUNT(*) FROM organizations').fetchone()[0] == 2


def test_account_purge_clears_multiple_frozen_attributions_and_restores_trigger_states(purge_db):
    purge_db.execute('''CREATE TRIGGER frozen_questionnaire BEFORE UPDATE OR DELETE
        ON questionnaire_response_revisions FOR EACH ROW EXECUTE FUNCTION prevent_result_delete()''')
    purge_db.execute('''CREATE TRIGGER already_disabled BEFORE UPDATE OR DELETE
        ON program_definitions FOR EACH ROW EXECUTE FUNCTION prevent_result_delete()''')
    purge_db.execute('ALTER TABLE program_definitions DISABLE TRIGGER already_disabled')
    purge_db.commit()
    purge_account(purge_db, user_id=20)
    purge_db.commit()
    assert purge_db.execute('''SELECT uploaded_by_user_id,confirmed_by_user_id,status,answers_json->>'answer'
        FROM questionnaire_response_revisions WHERE id=902''').fetchone() == (
            None, None, 'confirmed', 'foreign control')
    assert purge_db.execute("SELECT tgname,tgenabled FROM pg_trigger WHERE tgname IN ('frozen_questionnaire','already_disabled') ORDER BY tgname").fetchall() == [
        ('already_disabled', 'D'), ('frozen_questionnaire', 'O')]
    with pytest.raises(psycopg.errors.RaiseException, match='immutable result'):
        purge_db.execute("UPDATE questionnaire_response_revisions SET status='changed' WHERE id=902")
    purge_db.rollback()


@pytest.mark.parametrize(('alias', 'protected'), [
    ('verified-alias@example.test', True), ('unverified-alias@example.test', False)])
@pytest.mark.parametrize('source', ['superadmin', 'organization_admin'])
def test_configured_account_protection_uses_verified_identity_ownership(purge_db, monkeypatch, alias, protected, source):
    from Api import routes
    monkeypatch.setattr(routes, 'configured_superadmin_emails',
        lambda: {alias} if source == 'superadmin' else set())
    monkeypatch.setattr(routes, 'configured_org_admin_emails',
        lambda: {'purge-me': [alias]} if source == 'organization_admin' else {})
    assert routes._account_has_configured_access(purge_db,
        {'id': 10, 'email': 'orphan@example.test'}) is protected
    assert purge_db.execute('SELECT id FROM users ORDER BY id').fetchall() == [(10,), (20,), (30,)]


def _cascade_scope_fixture(connection):
    connection.execute('UPDATE program_definitions SET created_by_user_id=NULL WHERE created_by_user_id=20')
    connection.execute('''CREATE TABLE scoped_cascade_record(id BIGINT PRIMARY KEY,
        user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
        organization_id BIGINT REFERENCES organizations(id))''')
    connection.execute('INSERT INTO scoped_cascade_record VALUES(999,20,2),(1000,30,1)')
    schema = connection.execute('SELECT current_schema()').fetchone()[0]
    connection.commit()
    return schema


def test_concurrent_scope_change_after_validation_cannot_escape_via_user_cascade(purge_db):
    schema = _cascade_scope_fixture(purge_db)
    attempted = []
    def validate(tables, keys):
        _validate_organization_two_plan(purge_db, tables, keys)
        with psycopg.connect(purge_db.info.dsn) as concurrent:
            concurrent.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
            concurrent.execute("SET lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                concurrent.execute('UPDATE scoped_cascade_record SET organization_id=1 WHERE id=999')
            attempted.append('blocked')
    purge_account(purge_db, user_id=20, validate_scope=validate)
    purge_db.commit()
    assert attempted == ['blocked']
    assert purge_db.execute('SELECT id,organization_id FROM scoped_cascade_record').fetchall() == [(1000, 1)]


def test_concurrent_change_while_waiting_for_row_lock_rejects_stale_ctid_before_intent(purge_db):
    schema = _cascade_scope_fixture(purge_db)
    callbacks = []
    with psycopg.connect(purge_db.info.dsn) as concurrent:
        concurrent.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
        concurrent.execute('UPDATE scoped_cascade_record SET organization_id=1 WHERE id=999')
        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting = executor.submit(purge_account, purge_db, user_id=20,
                validate_scope=lambda tables, keys: _validate_organization_two_plan(purge_db, tables, keys),
                on_validated=callbacks.append)
            deadline = time.monotonic() + 5
            blocked = False
            while time.monotonic() < deadline:
                blockers = concurrent.execute('SELECT pg_blocking_pids(%s)', (purge_db.info.backend_pid,)).fetchone()[0]
                if concurrent.info.backend_pid in blockers:
                    blocked = True
                    break
                time.sleep(.01)
            concurrent.commit()
            assert blocked, 'purge must wait for the concurrently modified selected row'
            with pytest.raises(ValueError, match='PURGE_PREVIEW_STALE'):
                waiting.result(timeout=5)
    purge_db.rollback()
    assert callbacks == []
    assert purge_db.execute('SELECT id FROM users WHERE id=20').fetchone() == (20,)
    assert purge_db.execute('SELECT organization_id FROM scoped_cascade_record WHERE id=999').fetchone() == (1,)


@pytest.mark.parametrize('scope_row', ['attribution', 'ancestor'])
def test_attribution_and_indirect_ancestor_organization_are_locked_during_authorization(purge_db, scope_row):
    schema = _cascade_scope_fixture(purge_db)
    if scope_row == 'ancestor':
        purge_db.execute('CREATE TABLE scope_parent(id BIGINT PRIMARY KEY,organization_id BIGINT REFERENCES organizations(id))')
        purge_db.execute('INSERT INTO scope_parent VALUES(9,2)')
        purge_db.execute('''CREATE TABLE indirect_scope_row(id BIGINT PRIMARY KEY,user_id BIGINT REFERENCES users(id),
            parent_id BIGINT REFERENCES scope_parent(id))''')
        purge_db.execute('INSERT INTO indirect_scope_row VALUES(99,20,9)')
        purge_db.commit()
    mutation = ('UPDATE organization_invitations SET organization_id=1 WHERE id=703'
        if scope_row == 'attribution' else 'UPDATE scope_parent SET organization_id=1 WHERE id=9')
    def validate(tables, keys):
        _validate_organization_two_plan(purge_db, tables, keys)
        with psycopg.connect(purge_db.info.dsn) as concurrent:
            concurrent.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
            concurrent.execute("SET lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                concurrent.execute(mutation)
    purge_account(purge_db, user_id=20, validate_scope=validate)
    purge_db.commit()
    assert purge_db.execute('SELECT organization_id FROM organization_invitations WHERE id=703').fetchone() == (2,)
    if scope_row == 'ancestor':
        assert purge_db.execute('SELECT organization_id FROM scope_parent WHERE id=9').fetchone() == (2,)


def test_late_foreign_child_inserted_before_parent_pin_is_included_and_denied_before_intent(purge_db, monkeypatch):
    from scripts import purge_test_organization as purge_module
    schema = _cascade_scope_fixture(purge_db)
    purge_db.execute('''CREATE TABLE late_foreign_child(id BIGINT PRIMARY KEY,
        parent_id BIGINT REFERENCES scoped_cascade_record(id) ON DELETE CASCADE,
        organization_id BIGINT REFERENCES organizations(id))''')
    purge_db.commit()
    original_lock = purge_module._lock_purge_rows
    inserted = []
    def insert_before_parent_pin(connection, tables, staging_tables):
        if not inserted:
            with psycopg.connect(purge_db.info.dsn) as concurrent:
                concurrent.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
                concurrent.execute("SET lock_timeout='500ms'")
                concurrent.execute('INSERT INTO late_foreign_child VALUES(9001,999,1)')
            inserted.append('committed_before_parent_pin')
        return original_lock(connection, tables, staging_tables)
    monkeypatch.setattr(purge_module, '_lock_purge_rows', insert_before_parent_pin)
    callbacks = []
    with pytest.raises(ValueError, match='ACCOUNT_PURGE_SCOPE_FORBIDDEN'):
        purge_account(purge_db, user_id=20, on_validated=callbacks.append,
            validate_scope=lambda tables, keys: _validate_organization_two_plan(purge_db, tables, keys))
    purge_db.rollback()
    assert inserted == ['committed_before_parent_pin'] and callbacks == []
    assert purge_db.execute('SELECT id FROM users WHERE id=20').fetchone() == (20,)
    assert purge_db.execute('SELECT id,organization_id FROM late_foreign_child').fetchall() == [(9001, 1)]
    assert purge_db.execute('SELECT id FROM scoped_cascade_record ORDER BY id').fetchall() == [(999,), (1000,)]
