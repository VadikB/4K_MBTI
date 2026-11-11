"""Existing managed scope survives exclusion; this does not grant new eligibility."""
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi import HTTPException

from Api.assessment_assignment_sources import has_managed_assignment
from Api.routes import _require_unmanaged_profile_path


pytestmark = pytest.mark.integration


@pytest.fixture
def assignment_db(test_database_url):
    schema = 'remarks_participation_pytest_' + uuid4().hex
    marker = 'p4k-remarks-fix02:' + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL('COMMENT ON SCHEMA {} IS {}').format(
            psycopg.sql.Identifier(schema), psycopg.sql.Literal(marker)))
        connection.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
        connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY,email TEXT NOT NULL)')
        connection.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY,is_active BOOLEAN NOT NULL)')
        connection.execute('''CREATE TABLE organization_memberships(
            organization_id BIGINT,user_id BIGINT,role TEXT,is_participant BOOLEAN NOT NULL)''')
        connection.execute('''CREATE TABLE questionnaire_response_revisions(
            id BIGINT PRIMARY KEY,organization_id BIGINT,assignment_ref TEXT,status TEXT)''')
        connection.execute('''CREATE TABLE organization_assessment_assignments(
            id BIGINT PRIMARY KEY,organization_id BIGINT,recipient_user_id BIGINT,
            assignment_ref TEXT,status TEXT,revoked_at TIMESTAMP)''')
        connection.execute('CREATE TABLE organization_assessment_source_bindings(id BIGINT PRIMARY KEY)')
        connection.execute('''CREATE TABLE organization_invitations(
            organization_id BIGINT,recipient_email TEXT,assignment_ref TEXT,purpose TEXT,
            revoked_at TIMESTAMP,created_by_user_id BIGINT)''')
        connection.execute("INSERT INTO users VALUES(7,'subject@example.test'),(8,'other@example.test')")
        connection.execute('INSERT INTO organizations VALUES(3,TRUE),(4,TRUE)')
        connection.execute("INSERT INTO questionnaire_response_revisions VALUES(21,3,'managed','confirmed')")
        connection.execute("INSERT INTO organization_assessment_assignments VALUES(31,3,7,'managed','active',NULL)")
        connection.commit()
    try:
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
            yield connection
            connection.rollback()
    finally:
        with psycopg.connect(test_database_url) as connection:
            saved_marker = connection.execute('''SELECT obj_description(oid,'pg_namespace')
                FROM pg_namespace WHERE nspname=%s''', (schema,)).fetchone()[0]
            assert saved_marker == marker
            connection.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


@pytest.mark.parametrize('role', ['member', 'admin'])
def test_exclusion_does_not_turn_existing_assignment_into_unmanaged(assignment_db, role):
    connection = assignment_db
    connection.execute('INSERT INTO organization_memberships VALUES(3,7,%s,TRUE)', (role,))
    assert has_managed_assignment(connection, user_id=7)
    before = connection.execute('SELECT * FROM organization_assessment_assignments').fetchall()

    connection.execute('UPDATE organization_memberships SET is_participant=FALSE WHERE user_id=7')

    assert has_managed_assignment(connection, user_id=7)
    with pytest.raises(HTTPException) as denied:
        _require_unmanaged_profile_path(connection, user_id=7)
    assert denied.value.status_code == 409
    assert denied.value.detail.startswith('W02_MANAGED_ASSIGNMENT:')
    assert connection.execute('SELECT * FROM organization_assessment_assignments').fetchall() == before
    assert connection.execute('SELECT role,is_participant FROM organization_memberships').fetchone() == {
        'role': role, 'is_participant': False,
    }


@pytest.mark.parametrize('status,revoked', [('cancelled', False), ('revoked', True), ('active', True)])
def test_exclusion_keeps_assignment_termination_checks(assignment_db, status, revoked):
    connection = assignment_db
    connection.execute("INSERT INTO organization_memberships VALUES(3,7,'member',FALSE)")
    connection.execute('''UPDATE organization_assessment_assignments SET status=%s,
        revoked_at=CASE WHEN %s THEN NOW() ELSE NULL END''', (status, revoked))
    assert not has_managed_assignment(connection, user_id=7)
    _require_unmanaged_profile_path(connection, user_id=7)


@pytest.mark.parametrize('change', ['unconfirmed', 'inactive_org', 'foreign_assignment', 'absent_membership'])
def test_existing_assignment_still_requires_matching_confirmed_active_scope(assignment_db, change):
    connection = assignment_db
    connection.execute("INSERT INTO organization_memberships VALUES(3,7,'member',FALSE)")
    if change == 'unconfirmed':
        connection.execute("UPDATE questionnaire_response_revisions SET status='draft'")
    elif change == 'inactive_org':
        connection.execute('UPDATE organizations SET is_active=FALSE WHERE id=3')
    elif change == 'foreign_assignment':
        connection.execute('UPDATE organization_assessment_assignments SET organization_id=4')
    else:
        connection.execute('DELETE FROM organization_memberships WHERE user_id=7')
    assert not has_managed_assignment(connection, user_id=7)


def test_saved_invitation_scope_keeps_its_existing_revocation_guard(assignment_db):
    connection = assignment_db
    connection.execute("INSERT INTO organization_memberships VALUES(3,7,'member',FALSE)")
    connection.execute('DELETE FROM organization_assessment_assignments')
    connection.execute("""INSERT INTO organization_invitations
        VALUES(3,'subject@example.test','managed','personal_registration',NULL,8)""")
    assert has_managed_assignment(connection, user_id=7)
    connection.execute('UPDATE organization_invitations SET revoked_at=NOW()')
    assert not has_managed_assignment(connection, user_id=7)
