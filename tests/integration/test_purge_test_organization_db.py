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
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY, email TEXT NOT NULL)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY, code TEXT UNIQUE, name TEXT)")
        connection.execute("""CREATE TABLE organization_memberships(
            id BIGSERIAL PRIMARY KEY,
            organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
            user_id BIGINT REFERENCES users(id))""")
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
        connection.execute("INSERT INTO users VALUES (10, 'member@example.test'), (20, 'other@example.test')")
        connection.execute("INSERT INTO organizations VALUES (1, 'purge-me', 'Purge me'), (2, 'keep-me', 'Keep me')")
        connection.execute("INSERT INTO organization_memberships(organization_id,user_id) VALUES (1,10),(2,20)")
        profile_id = connection.execute(
            "INSERT INTO assessment_profiles(organization_id,snapshot) VALUES (1,'frozen') RETURNING id"
        ).fetchone()[0]
        connection.execute("INSERT INTO assessment_results(profile_id,result) VALUES (%s,'frozen')", (profile_id,))
        connection.execute("INSERT INTO user_sessions VALUES (100,10),(200,20)")
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


def test_full_purge_removes_linked_history_and_preserves_users(purge_db):
    counts = purge_organization(purge_db, organization_id=1, confirm_code="purge-me")
    purge_db.commit()

    assert any(name.endswith(".assessment_results") and count == 1 for name, count in counts.items())
    assert purge_db.execute("SELECT id FROM organizations ORDER BY id").fetchall() == [(2,)]
    assert purge_db.execute("SELECT id FROM users ORDER BY id").fetchall() == [(10,), (20,)]
    assert purge_db.execute("SELECT id FROM user_sessions ORDER BY id").fetchall() == [(200,)]
    assert purge_db.execute("SELECT COUNT(*) FROM assessment_profiles").fetchone()[0] == 0
    assert purge_db.execute("SELECT COUNT(*) FROM assessment_results").fetchone()[0] == 0
