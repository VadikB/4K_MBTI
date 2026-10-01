from __future__ import annotations

import copy
import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_storage import M5ImportConflict, import_package, package_readback, prepare_assessment_situation
from Api.m5_scenario_runtime import start, submit_turn, trace, transition
from scripts.build_m5_case_package import OUTPUT


@pytest.mark.integration
def test_m5_import_readback_and_rejected_as_are_transactional(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_runtime_test_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE assessment_personalized_profiles (id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL, provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)")
        ensure_m5_runtime_schema(connection)

        imported = import_package(connection, package=package, manifest=manifest)
        assert imported == {"package_db_id": imported["package_db_id"], "created": True, "case_count": 5}
        repeated = import_package(connection, package=package, manifest=manifest)
        assert repeated["created"] is False
        readback = package_readback(connection, imported["package_db_id"])
        assert [(x["target_count"], x["material_count"], x["scenario_step_count"]) for x in readback["cases"]] == [
            (9, 3, 4), (9, 3, 4), (8, 3, 4), (8, 5, 4), (9, 3, 4),
        ]

        changed = copy.deepcopy(package)
        changed["cases"][0]["title"] += " changed"
        with pytest.raises(M5ImportConflict, match="PACKAGE_VERSION_CONTENT_CONFLICT"):
            with connection.transaction():
                import_package(connection, package=changed, manifest=manifest)

        connection.execute("INSERT INTO assessment_personalized_profiles VALUES (7,'ready',%s::jsonb,'{}'::jsonb,%s)",
                           (json.dumps({"role_profile": {"code": "project_product_process_manager"}}), "c" * 64))
        prepared = prepare_assessment_situation(
            connection, assessment_situation_id=str(uuid4()), case_id="CASE-TDISC-01", case_version="v0.1",
            personalized_profile_id=7, substitutions=[], policy=policy,
            usage_scope="qa",
        )
        assert prepared["status"] == "rejected"
        assert prepared["snapshot"]["admission"]["code"] == "CASE_NOT_ADMITTED"
        stored = connection.execute("""
            SELECT s.status, s.snapshot_checksum, d.policy_version, d.code, d.admitted
            FROM m5_assessment_situations s JOIN m5_admission_decisions d ON d.assessment_situation_db_id=s.id
        """).fetchone()
        assert (stored["status"], stored["policy_version"], stored["code"], stored["admitted"]) == (
            "rejected", "1.1-draft.1", "CASE_NOT_ADMITTED", False,
        )
        assert connection.execute("SELECT count(*) AS n FROM m5_case_versions").fetchone()["n"] == 5
        started = start(connection, prepared["assessment_situation_id"])
        assert started["status"] == "active"
        request_id, turn_id = "request-1", str(uuid4())
        first = submit_turn(connection, assessment_situation_id=prepared["assessment_situation_id"],
                            request_id=request_id, turn_id=turn_id, content="Покажите готовность и выборку")
        assert not first["idempotent"]
        assert {x["material_id"] for x in first["events"]} >= {"CASE-TDISC-01-D1", "CASE-TDISC-01-D3"}
        repeated_turn = submit_turn(connection, assessment_situation_id=prepared["assessment_situation_id"],
                                    request_id=request_id, turn_id=turn_id, content="другая доставка")
        assert repeated_turn["idempotent"]
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="pause", reason="test", request_id="pause-1")["status"] == "paused"
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="resume", reason="test", request_id="resume-1")["status"] == "active"
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="scenario_end", reason="done", request_id="end-1")["status"] == "scenario_ended"
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="close", reason="closed", request_id="close-1")["status"] == "closed"
        saved_trace = trace(connection, prepared["assessment_situation_id"])
        assert saved_trace["status"] == "closed"
        assert len(saved_trace["turns"]) == 1
        assert len({x["event_key"] for x in saved_trace["events"]}) == len(saved_trace["events"])
        connection.rollback()
