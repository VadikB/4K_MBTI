from __future__ import annotations

from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

from Api import assessment_programs


pytestmark = pytest.mark.integration


@pytest.fixture
def program_db(test_database_url):
    schema = 'arch30_program_pytest_' + uuid4().hex
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute(psycopg.sql.SQL('CREATE SCHEMA {}').format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
        connection.execute('CREATE TABLE users(id BIGINT PRIMARY KEY)')
        connection.execute('CREATE TABLE organizations(id BIGINT PRIMARY KEY)')
        connection.execute("""CREATE TABLE assessment_configurations(
            id BIGINT PRIMARY KEY,code TEXT,status TEXT,catalog_version_id BIGINT,
            methodology_version_id BIGINT,scenario_version_id BIGINT,prompt_bundle_checksum TEXT)""")
        connection.execute("""CREATE TABLE m5_catalogs(
            id BIGINT PRIMARY KEY,status TEXT,usage_scope TEXT,organization_id BIGINT)""")
        connection.execute("""CREATE TABLE assessment_role_profiles(
            id BIGINT PRIMARY KEY,code TEXT)""")
        connection.execute("""CREATE TABLE assessment_role_profile_versions(
            id BIGINT PRIMARY KEY,role_profile_id BIGINT REFERENCES assessment_role_profiles(id),
            version TEXT,status TEXT,methodology_version TEXT,definition_json JSONB)""")
        assessment_programs.ensure_schema(connection)
        connection.execute('INSERT INTO users VALUES(1),(2)')
        connection.execute('INSERT INTO organizations VALUES(10)')
        connection.execute("INSERT INTO m5_catalogs VALUES(20,'published','assessment',NULL)")
        connection.execute("INSERT INTO assessment_configurations VALUES(30,'nine-cases','published',20,1,1,'prompt-checksum')")
        connection.execute("INSERT INTO assessment_role_profiles VALUES(40,'specialist_expert')")
        connection.execute("""INSERT INTO assessment_role_profile_versions
            VALUES(50,40,'1.0','published','1.1','{"description":{"name":"Специалист"}}')""")
        checksum = assessment_programs.definition_checksum(code='4k-pilot', version='1.0',
            name='4K Pilot', assignment_ref='competencies_4k', mode='dialogue',
            configuration_id=30, role_version_ids=[50], catalog_version_id=20,
            source_refs={'methodology_version_id': 1, 'scenario_version_id': 1})
        program_id = connection.execute("""INSERT INTO assessment_program_definitions
            (code,version,name,assignment_ref,mode,status,assessment_configuration_id,
             catalog_version_id,source_refs_json,definition_checksum,published_by_user_id,published_at)
            VALUES('4k-pilot','1.0','4K Pilot','competencies_4k','dialogue','draft',30,20,
                '{"methodology_version_id":1,"scenario_version_id":1}',%s,1,NOW())
            RETURNING id""", (checksum,)).fetchone()['id']
        connection.execute('INSERT INTO assessment_program_allowed_roles VALUES(%s,50,0)', (program_id,))
        connection.execute("UPDATE assessment_program_definitions SET status='published' WHERE id=%s", (program_id,))
        connection.commit()
    try:
        connection = psycopg.connect(test_database_url, row_factory=dict_row)
        connection.execute(psycopg.sql.SQL('SET search_path TO {}').format(psycopg.sql.Identifier(schema)))
        connection.commit()
        yield connection, int(program_id)
        connection.close()
    finally:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL('DROP SCHEMA {} CASCADE').format(psycopg.sql.Identifier(schema)))


def test_program_connect_resolve_and_immutability(program_db):
    connection, program_id = program_db
    connected = assessment_programs.connect(connection, organization_id=10,
        program_definition_id=program_id, actor_user_id=1, operation_id='connect-program-0001')
    connection.commit()
    assert connected['program_version'] == '1.0'
    resolved = assessment_programs.resolve(connection, organization_id=10,
        assignment_ref='competencies_4k')
    assert resolved['assessment_configuration_id'] == 30
    assert resolved['role_profile_version_id'] == 50
    assert assessment_programs.connect(connection, organization_id=10,
        program_definition_id=program_id, actor_user_id=1,
        operation_id='connect-program-0001')['connection_id'] == connected['connection_id']
    with pytest.raises(psycopg.errors.RaiseException):
        connection.execute("UPDATE assessment_program_definitions SET name='changed' WHERE id=%s", (program_id,))
    connection.rollback()


def test_retired_program_stops_new_resolution_without_rewriting_connection(program_db):
    connection, program_id = program_db
    assessment_programs.connect(connection, organization_id=10, program_definition_id=program_id,
        actor_user_id=1, operation_id='connect-program-0002')
    connection.execute("UPDATE assessment_program_definitions SET status='retired' WHERE id=%s", (program_id,))
    connection.commit()
    assert assessment_programs.current_connection(connection, organization_id=10)['program_status'] == 'retired'
    with pytest.raises(ValueError, match='PROGRAM_NOT_AVAILABLE_FOR_NEW_ASSIGNMENTS'):
        assessment_programs.resolve(connection, organization_id=10, assignment_ref='competencies_4k')


def test_existing_program_connection_actor_fk_migrates_without_rewriting_business_data(program_db):
    connection, program_id = program_db
    connected = assessment_programs.connect(connection, organization_id=10,
        program_definition_id=program_id, actor_user_id=2, operation_id='connect-program-migration')
    constraint = connection.execute("""SELECT constraint_row.conname
        FROM pg_constraint constraint_row JOIN pg_attribute attribute
          ON attribute.attrelid=constraint_row.conrelid AND attribute.attnum=ANY(constraint_row.conkey)
        WHERE constraint_row.conrelid='organization_assessment_program_connections'::regclass
          AND constraint_row.confrelid='users'::regclass
          AND attribute.attname='connected_by_user_id'""").fetchone()['conname']
    connection.execute(psycopg.sql.SQL("ALTER TABLE organization_assessment_program_connections DROP CONSTRAINT {}")
        .format(psycopg.sql.Identifier(constraint)))
    connection.execute("ALTER TABLE organization_assessment_program_connections ALTER COLUMN connected_by_user_id SET NOT NULL")
    connection.execute("""ALTER TABLE organization_assessment_program_connections
        ADD CONSTRAINT legacy_connected_by_fk FOREIGN KEY(connected_by_user_id)
        REFERENCES users(id) ON DELETE RESTRICT""")
    connection.commit()

    assessment_programs.ensure_schema(connection)
    connection.execute('DELETE FROM users WHERE id=2')
    row = connection.execute("""SELECT id,organization_id,program_definition_id,is_current,
        operation_id,connected_by_user_id FROM organization_assessment_program_connections
        WHERE id=%s""", (connected['connection_id'],)).fetchone()

    assert row == {
        'id': connected['connection_id'], 'organization_id': 10,
        'program_definition_id': program_id, 'is_current': True,
        'operation_id': 'connect-program-migration', 'connected_by_user_id': None,
    }
