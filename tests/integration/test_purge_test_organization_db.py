from uuid import uuid4

import psycopg
import pytest

from scripts.purge_test_organization import build_purge_plan, purge_organization


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
            email TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE auth_password_credentials(
            id BIGINT PRIMARY KEY,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL)""")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY, code TEXT UNIQUE, name TEXT)")
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
        connection.execute("INSERT INTO user_identities VALUES (101,10,'orphan@example.test'),(301,30,'shared@example.test')")
        connection.execute("INSERT INTO auth_password_credentials VALUES (102,10,'orphan@example.test'),(302,30,'shared@example.test')")
        connection.execute("INSERT INTO organizations VALUES (1, 'purge-me', 'Purge me'), (2, 'keep-me', 'Keep me')")
        connection.execute("""INSERT INTO organization_memberships(organization_id,user_id) VALUES
            (1,10),(1,30),(2,20),(2,30)""")
        profile_id = connection.execute(
            "INSERT INTO assessment_profiles(organization_id,snapshot) VALUES (1,'frozen') RETURNING id"
        ).fetchone()[0]
        connection.execute("INSERT INTO assessment_results(profile_id,result) VALUES (%s,'frozen')", (profile_id,))
        connection.execute("INSERT INTO user_sessions VALUES (100,10),(200,20),(300,30)")
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
    purge_db.execute("DELETE FROM organization_memberships WHERE organization_id=2 AND user_id=30")
    purge_db.execute("INSERT INTO organization_memberships(organization_id,user_id) VALUES (2,30)")
    assert purge_db.execute(
        "SELECT COUNT(*) FROM organization_memberships WHERE organization_id=2 AND user_id=30"
    ).fetchone()[0] == 1
    assert purge_db.execute("SELECT COUNT(*) FROM assessment_profiles").fetchone()[0] == 0
    assert purge_db.execute("SELECT COUNT(*) FROM assessment_results").fetchone()[0] == 0
