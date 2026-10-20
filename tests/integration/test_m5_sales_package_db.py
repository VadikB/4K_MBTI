from __future__ import annotations

import copy
import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_storage import (M5ImportConflict, import_package, package_readback,
                            prepare_assessment_situation)
from Api.m5_cycle_runtime import create_cycle_session_for_case
from Api.m5_rule_engine import CharacterReply, ControlledCharacterAdapter, ControlledSemanticAdapter
from Api.m5_scenario_runtime import start, submit_turn, trace
from Api.m10_product_flow import participant_trace
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
        stored_rules = readback["package"]["runtime_rules_json"]
        assert stored_rules["schema_version"] == 2
        assert stored_rules["cases"]["CASE.SPEC.02"]["actorless"] is True
        assert stored_rules["cases"]["CASE.SPEC.07"]["characters"] == []
        changed = copy.deepcopy(package)
        changed["cases"][0]["title"] += " changed"
        with pytest.raises(M5ImportConflict, match="PACKAGE_VERSION_CONTENT_CONFLICT"):
            with connection.transaction():
                import_package(connection, package=changed, manifest=manifest, execution_rules=rules)


@pytest.mark.integration
def test_sales_case03_multi_actor_turns_retry_and_provider_recovery(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_sales_runtime_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute(
            "CREATE TABLE assessment_personalized_profiles "
            "(id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL, "
            "provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)"
        )
        ensure_m5_runtime_schema(connection)
        import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        connection.execute(
            "INSERT INTO assessment_personalized_profiles VALUES (7,'ready',%s::jsonb,'{}'::jsonb,%s)",
            (json.dumps({"base_role": "specialist_expert"}), "7" * 64),
        )
        cycle, session = create_cycle_session_for_case(
            connection, personalized_profile_id=7, case_id="CASE.SPEC.03", case_version="v0.2",
            created_by=99, usage_scope="qa",
        )
        policy = {"id": "sales-sls03-qa", "version": "1", "allowed_case_statuses": ["FROZEN"],
                  "required_evidence_scopes": ["case_format", "case_dialogue", "assessment_situation"]}
        prepared = prepare_assessment_situation(
            connection, assessment_situation_id=str(uuid4()), case_id="CASE.SPEC.03", case_version="v0.2",
            personalized_profile_id=7, cycle_db_id=int(cycle["id"]), session_db_id=int(session["id"]),
            substitutions=[], policy=policy, usage_scope="qa", qa_authorized_by=99,
        )
        assert prepared["execution_payload"]["ai_operations"]["character_response"]["prompt_ref"]["version"] == "v2"
        start(connection, prepared["assessment_situation_id"])
        reactions = {f"CHARACTER.{speaker}": f"Ответ {speaker}" for speaker in ("DENIS", "ILYA", "SVETLANA")}
        decisions = {f"CHARACTER.{speaker}:character_reaction": "TRUE" for speaker in ("DENIS", "ILYA", "SVETLANA")}
        first_turn_id = str(uuid4())
        first_turn = submit_turn(
            connection, assessment_situation_id=prepared["assessment_situation_id"], request_id="sales-turn-1",
            turn_id=first_turn_id, content="Предлагаю распределить конкретные действия",
            semantic_adapter=ControlledSemanticAdapter(decisions),
            character_adapter=ControlledCharacterAdapter(reactions),
        )
        assert {item["payload_json"]["speaker_id"] for item in first_turn["events"]
                if item["event_type"] == "character_response"} == {"DENIS", "ILYA", "SVETLANA"}
        retry = submit_turn(
            connection, assessment_situation_id=prepared["assessment_situation_id"], request_id="sales-turn-1",
            turn_id=first_turn_id, content="Предлагаю распределить конкретные действия",
            semantic_adapter=ControlledSemanticAdapter(decisions),
            character_adapter=ControlledCharacterAdapter(reactions),
        )
        assert retry["idempotent"] is True
        second = submit_turn(
            connection, assessment_situation_id=prepared["assessment_situation_id"], request_id="sales-turn-2",
            turn_id=str(uuid4()), content="Уточняю действия после ответов",
            semantic_adapter=ControlledSemanticAdapter({**decisions, "M04:mandatory": "TRUE"}),
            character_adapter=ControlledCharacterAdapter(reactions),
        )
        assert sum(item["event_type"] == "character_response" for item in second["events"]) == 3
        assert sum(item["material_id"] == "M04" for item in second["events"]) == 1
        saved = trace(connection, prepared["assessment_situation_id"])
        assert len([item for item in saved["turns"] if item["speaker_type"] == "character"]) == 6
        public = participant_trace(saved)
        assert "ai_attempts" not in public and "closed_card" not in json.dumps(public, ensure_ascii=False, default=str)

        class FailThenReply:
            def __init__(self): self.calls = 0
            def respond(self, **_kwargs):
                self.calls += 1
                ai_trace = {"intended": {}, "sent": {}, "provider": {}, "response": {},
                            "identity_status": "technical_failure" if self.calls == 1 else "sent_matches_snapshot"}
                return CharacterReply("ERROR" if self.calls == 1 else "COMPLETED",
                                      None if self.calls == 1 else "Повтор успешен", "controlled",
                                      controlled_test=True, ai_trace=ai_trace)

        failure_adapter = FailThenReply()
        third_turn_id = str(uuid4())
        one_decision = {"CHARACTER.DENIS:character_reaction": "TRUE"}
        failed = submit_turn(
            connection, assessment_situation_id=prepared["assessment_situation_id"], request_id="sales-turn-3",
            turn_id=third_turn_id, content="Вопрос Денису",
            semantic_adapter=ControlledSemanticAdapter(one_decision), character_adapter=failure_adapter,
        )
        assert not any(item["event_type"] == "character_response" for item in failed["events"])
        recovered = submit_turn(
            connection, assessment_situation_id=prepared["assessment_situation_id"], request_id="sales-turn-3",
            turn_id=third_turn_id, content="Вопрос Денису",
            semantic_adapter=ControlledSemanticAdapter(one_decision), character_adapter=failure_adapter,
        )
        assert any(item["event_type"] == "character_response" for item in recovered["events"])
        attempts = trace(connection, prepared["assessment_situation_id"])["ai_attempts"]
        denis = [item for item in attempts if item["action_key"].startswith("character-response:CHARACTER.DENIS:")]
        assert [item["outcome"] for item in denis[-2:]] == ["technical_failure", "accepted"]
        connection.rollback()
