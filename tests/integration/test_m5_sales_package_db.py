from __future__ import annotations

import copy
import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_storage import M5ImportConflict, import_package, package_readback
from scripts.build_m5_sales_package import OUTPUT


@pytest.mark.integration
def test_sales_package_round_trip_is_idempotent_and_immutable(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_sales_package_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE assessment_personalized_profiles "
            "(id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL, "
            "provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)"
        )
        ensure_m5_runtime_schema(connection)
        first = import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        second = import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        assert first["created"] is True
        assert second["created"] is False
        readback = package_readback(connection, first["package_db_id"])
        assert len(readback["cases"]) == 9
        assert sum(row["target_count"] for row in readback["cases"]) == 55
        changed = copy.deepcopy(package)
        changed["cases"][0]["title"] += " changed"
        with pytest.raises(M5ImportConflict, match="PACKAGE_VERSION_CONTENT_CONFLICT"):
            with connection.transaction():
                import_package(connection, package=changed, manifest=manifest, execution_rules=rules)
