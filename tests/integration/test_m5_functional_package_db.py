from __future__ import annotations

import copy
import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_storage import M5ImportConflict, import_package, package_readback
from scripts.build_m5_functional_package import OUTPUT


@pytest.mark.integration
def test_functional_package_round_trip_is_idempotent_and_preserves_old_versions(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_functional_" + uuid4().hex
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
        assert [(item["case_id"], item["case_version"]) for item in readback["cases"]] == [
            (f"CASE.SPEC.{number:02d}", version) for number, version in enumerate(
                ("v0.5", "v0.6", "v0.4", "v0.5", "v0.5", "v0.4", "v0.4", "v0.4", "v0.4"), 1
            )
        ]
        assert sum(item["target_count"] for item in readback["cases"]) == 55
        stored = readback["package"]["runtime_rules_json"]
        assert stored["cases"]["CASE.SPEC.02"]["actorless"] is True
        assert stored["cases"]["CASE.SPEC.07"]["actorless"] is True
        assert stored["cases"]["CASE.SPEC.03"]["scenario"][0]["condition"]
        changed = copy.deepcopy(package)
        changed["cases"][0]["passport"]["16 Инвариантное ядро"] = {"changed": True}
        with pytest.raises(M5ImportConflict, match="PACKAGE_VERSION_CONTENT_CONFLICT"):
            with connection.transaction():
                import_package(connection, package=changed, manifest=manifest, execution_rules=rules)
        connection.rollback()
