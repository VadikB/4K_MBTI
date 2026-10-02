from __future__ import annotations

import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_cycle_runtime import (
    create_cycle_session_for_case,
    read_cycle,
    transition_session,
)
from Api.m5_storage import import_package, prepare_assessment_situation
from scripts.build_m5_case_package import OUTPUT


@pytest.mark.integration
def test_cycle_session_membership_freeze_and_collection_boundary(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    case = package["cases"][0]
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_cycle_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute("""CREATE TABLE assessment_personalized_profiles
            (id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL,
             provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)""")
        ensure_m5_runtime_schema(connection)
        import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        connection.execute(
            "INSERT INTO assessment_personalized_profiles VALUES (7,'ready',%s::jsonb,'{}'::jsonb,%s)",
            (json.dumps({"role_profile": {"code": case["base_role"]}}), "c" * 64),
        )

        cycle, session = create_cycle_session_for_case(
            connection, personalized_profile_id=7, case_id=case["case_id"], case_version=case["version"],
            created_by=99, usage_scope="qa", time_budget_seconds=2700, calendar_window_seconds=172800,
        )
        saved = read_cycle(connection, str(cycle["cycle_id"]))
        assert saved["time_budget_seconds"] == 2700
        assert saved["calendar_window_seconds"] == 172800
        assert saved["status"] == "active"
        assert saved["sessions"][0]["status"] == "active"

        prepared = prepare_assessment_situation(
            connection, assessment_situation_id=str(uuid4()), case_id=case["case_id"],
            case_version=case["version"], personalized_profile_id=7,
            cycle_db_id=cycle["id"], session_db_id=session["id"], substitutions=[], policy=policy,
            usage_scope="qa", qa_authorized_by=99,
        )
        assert prepared["snapshot"]["cycle_ref"]["id"] == str(cycle["id"])
        assert prepared["snapshot"]["session_ref"]["id"] == str(session["id"])

        deadline = saved["calendar_deadline"]
        connection.execute(
            "UPDATE m5_cycle_time_intervals SET started_at=NOW()-INTERVAL '20 minutes' WHERE cycle_db_id=%s",
            (cycle["id"],),
        )
        transition_session(connection, session_id=str(session["session_id"]), action="pause", reason="authorized")
        paused = read_cycle(connection, str(cycle["cycle_id"]))
        assert 1498 <= paused["remaining_seconds"] <= 1500
        assert paused["calendar_deadline"] == deadline
        transition_session(connection, session_id=str(session["session_id"]), action="resume", reason="continue")
        transition_session(connection, session_id=str(session["session_id"]), action="complete", reason="normal")
        closed = read_cycle(connection, str(cycle["cycle_id"]))
        assert closed["status"] == "collection_closed"
        assert closed["sessions"][0]["status"] == "completed"
        connection.rollback()


@pytest.mark.integration
def test_as_rejects_foreign_session_and_changed_profile(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    case = package["cases"][0]
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_cycle_negative_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute("""CREATE TABLE assessment_personalized_profiles
            (id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL,
             provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)""")
        ensure_m5_runtime_schema(connection)
        import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        connection.execute(
            "INSERT INTO assessment_personalized_profiles VALUES (7,'ready',%s::jsonb,'{}'::jsonb,%s)",
            (json.dumps({"role_profile": {"code": case["base_role"]}}), "c" * 64),
        )
        first_cycle, first_session = create_cycle_session_for_case(
            connection, personalized_profile_id=7, case_id=case["case_id"], case_version=case["version"],
            created_by=99, usage_scope="qa",
        )
        second_cycle, second_session = create_cycle_session_for_case(
            connection, personalized_profile_id=7, case_id=case["case_id"], case_version=case["version"],
            created_by=99, usage_scope="qa",
        )
        with pytest.raises(ValueError, match="M7_CYCLE_SESSION_OWNERSHIP_MISMATCH"):
            prepare_assessment_situation(
                connection, assessment_situation_id=str(uuid4()), case_id=case["case_id"],
                case_version=case["version"], personalized_profile_id=7,
                cycle_db_id=first_cycle["id"], session_db_id=second_session["id"],
                substitutions=[], policy=policy, usage_scope="qa", qa_authorized_by=99,
            )
        connection.execute("UPDATE assessment_personalized_profiles SET checksum=%s WHERE id=7", ("d" * 64,))
        with pytest.raises(ValueError, match="M7_FROZEN_PROFILE_MISMATCH"):
            prepare_assessment_situation(
                connection, assessment_situation_id=str(uuid4()), case_id=case["case_id"],
                case_version=case["version"], personalized_profile_id=7,
                cycle_db_id=first_cycle["id"], session_db_id=first_session["id"],
                substitutions=[], policy=policy, usage_scope="qa", qa_authorized_by=99,
            )
        assert second_cycle["id"] != first_cycle["id"]
        connection.rollback()
