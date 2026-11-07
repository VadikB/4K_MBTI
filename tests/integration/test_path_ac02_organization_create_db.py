"""AC02: real HTTP handler/transactions/DDL, synthetic auth and list projection.

No program/assessment or provider is involved. Only an owned schema in the
explicit TEST_DATABASE_URL is created and removed; never the working DB.
"""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
import pytest

from Api import routes
from Api.org_access import AdminScope
from Api.schemas import AdminOrganizationItem, AdminOrganizationsResponse

pytestmark = pytest.mark.integration


def _product_table_ddl(table):
    """Use the exact current product DDL, not an invented UNIQUE fixture."""
    source = Path(__file__).resolve().parents[2] / "Api/database.py"
    values = [node.value for node in ast.walk(ast.parse(source.read_text()))
              if isinstance(node, ast.Constant) and isinstance(node.value, str)
              and node.value.strip().startswith(f"CREATE TABLE IF NOT EXISTS {table} (")]
    assert len(values) == 1
    return values[0]


@pytest.fixture
def organization_http_db(test_database_url, monkeypatch):
    schema = "path_ac02_pytest_" + uuid4().hex
    with psycopg.connect(test_database_url) as connection:
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
        for table in ("organizations", "organization_deletion_tombstones"):
            connection.execute(_product_table_ddl(table))

    @contextmanager
    def factory():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            connection.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(schema)))
            connection.commit()
            yield connection

    def projection(connection, _scope, **_kwargs):
        items = [AdminOrganizationItem(**row) for row in connection.execute(
            "SELECT id,code,name,is_active FROM organizations ORDER BY id"
        ).fetchall()]
        return AdminOrganizationsResponse(title="Synthetic AC02", subtitle="", is_superadmin=True, items=items)

    monkeypatch.setattr(routes, "get_connection", factory)
    monkeypatch.setattr(routes.web_session_service, "get_user_by_token", lambda _token: SimpleNamespace(id=18))
    monkeypatch.setattr(routes, "_get_admin_scope_or_403", lambda *_args: AdminScope(is_superadmin=True))
    monkeypatch.setattr(routes, "_build_admin_organizations", projection)
    app = FastAPI()
    app.include_router(routes.router)
    try:
        yield TestClient(app), factory
    finally:
        with psycopg.connect(test_database_url) as connection:
            connection.execute(psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(psycopg.sql.Identifier(schema)))


@pytest.mark.parametrize("repeat_code", ["owned-ac02", " OWNED-AC02 "])
def test_create_reload_repeat_conflict_preserves_one_organization(organization_http_db, repeat_code):
    client, factory = organization_http_db
    created = client.post("/users/admin/organizations", json={"code": "owned-ac02", "name": "Owned AC02"})
    assert created.status_code == 200
    original = created.json()["items"][0]
    assert client.get("/users/admin/organizations").json()["items"] == created.json()["items"]
    repeated = client.post("/users/admin/organizations", json={"code": repeat_code, "name": "Must not replace"})
    assert repeated.status_code == 409
    assert repeated.json()["detail"] == "Organization with this code already exists"
    reloaded = client.get("/users/admin/organizations")
    assert reloaded.status_code == 200
    assert reloaded.json()["items"] == [original]
    # A separate transaction sees committed identity; duplicate rollback did not rename it.
    with factory() as connection:
        rows = connection.execute("SELECT id,code,name FROM organizations").fetchall()
        assert rows == [{"id": original["id"], "code": "owned-ac02", "name": "Owned AC02"}]
    # The connection remains usable after the conflict and does not swallow later creation.
    other = client.post("/users/admin/organizations", json={"code": "other-ac02", "name": "Other AC02"})
    assert other.status_code == 200
    assert len(other.json()["items"]) == 2
    assert other.json()["items"][0] == original
