from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
from fastapi import HTTPException

from Api.routes import _lock_membership_by_email, _reject_foreign_membership


pytestmark = pytest.mark.integration


@pytest.fixture
def membership_schema(test_database_url):
    schema = "arch30_membership_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users(id BIGINT PRIMARY KEY, email TEXT NOT NULL UNIQUE)")
        connection.execute("CREATE TABLE organizations(id BIGINT PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("""CREATE TABLE organization_memberships(
            organization_id BIGINT NOT NULL REFERENCES organizations(id),
            user_id BIGINT NOT NULL REFERENCES users(id),
            role TEXT NOT NULL,
            UNIQUE(organization_id, user_id), UNIQUE(user_id))""")
        connection.execute("INSERT INTO users VALUES (7, 'person@example.test')")
        connection.execute("INSERT INTO organizations VALUES (3, 'Организация А'), (4, 'Организация Б')")
        connection.commit()
    try:
        yield schema
    finally:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


def _connect(test_database_url, schema):
    connection = psycopg.connect(test_database_url, row_factory=dict_row)
    connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
    connection.commit()
    return connection


def test_concurrent_addition_rechecks_membership_after_email_lock(test_database_url, membership_schema):
    first = _connect(test_database_url, membership_schema)
    second = _connect(test_database_url, membership_schema)
    try:
        assert _lock_membership_by_email(first, email="person@example.test")["organization_id"] is None

        with ThreadPoolExecutor(max_workers=1) as executor:
            waiting = executor.submit(_lock_membership_by_email, second, email="person@example.test")
            first.execute(
                "INSERT INTO organization_memberships(organization_id,user_id,role) VALUES (3,7,'member')"
            )
            first.commit()
            observed = waiting.result(timeout=5)

        assert observed["organization_id"] == 3
        with pytest.raises(HTTPException) as raised:
            _reject_foreign_membership(observed, organization_id=4, expose_organization=False)
        assert raised.value.status_code == 409
        second.rollback()
        assert second.execute("SELECT COUNT(*) AS count FROM organization_memberships").fetchone()["count"] == 1
    finally:
        first.close()
        second.close()
