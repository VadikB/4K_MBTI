from __future__ import annotations

import copy
import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_storage import M5ImportConflict, import_package, package_readback
from Api.m5_storage import prepare_assessment_situation
from Api.m5_cycle_runtime import create_cycle_session_for_case
from Api.m5_rule_engine import ControlledCharacterAdapter, ControlledSemanticAdapter
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
from Api.m5_scenario_runtime import build_c45, start, submit_turn, transition
from Api.m6_input_resolver import resolve as resolve_m6_input
from scripts.build_m5_sales_package import build_execution_rules
from scripts.build_m5_functional_package import OUTPUT

RUNTIME_PACKAGE = OUTPUT.parent.parent / "functional-personalization-runtime/1.2.0"


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


@pytest.mark.integration
def test_versioned_runtime_rules_execute_all_nine_functional_cases(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    legacy_rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    loaded = load_runtime_rule_package(RUNTIME_PACKAGE, package["cases"])
    compiled = build_execution_rules(package["cases"], loaded["bindings"])
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_functional_runtime_" + uuid4().hex
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
        import_package(connection, package=package, manifest=manifest, execution_rules=legacy_rules)
        imported_rules = import_runtime_rule_version(connection, loaded, compiled)
        repeated_rules = import_runtime_rule_version(connection, loaded, compiled)
        assert repeated_rules == {**imported_rules, "created": False}
        with pytest.raises(psycopg.Error, match="Versioned M5 runtime rules are immutable"):
            with connection.transaction():
                connection.execute(
                    "UPDATE m5_runtime_rule_versions SET owner='changed' WHERE id=%s",
                    (imported_rules["id"],),
                )
        connection.execute(
            "INSERT INTO assessment_personalized_profiles VALUES (7,'ready',%s::jsonb,'{}'::jsonb,%s)",
            (json.dumps({"base_role": "specialist_expert"}), "7" * 64),
        )
        case_by_id = {case["case_id"]: case for case in package["cases"]}
        expected_calls = {case_id: sum(
            len(event.get("speaker_ids") or [])
            for event in binding["events"].values() if event["function"] == "character_reaction"
        ) for case_id, binding in loaded["bindings"]["case_bindings"].items()}
        for case_id, case in case_by_id.items():
            cycle, session = create_cycle_session_for_case(
                connection, personalized_profile_id=7, case_id=case_id,
                case_version=case["version"], created_by=99, usage_scope="qa",
            )
            prepared = prepare_assessment_situation(
                connection, assessment_situation_id=str(uuid4()), case_id=case_id,
                case_version=case["version"], personalized_profile_id=7,
                cycle_db_id=int(cycle["id"]), session_db_id=int(session["id"]),
                substitutions=[], policy={
                    "id": "pers-runtime-qa", "version": "1",
                    "allowed_case_statuses": ["WORKING"],
                    "required_evidence_scopes": ["case_format", "case_dialogue", "assessment_situation"],
                },
                usage_scope="qa", qa_authorized_by=99,
                runtime_rule_version_id=imported_rules["id"],
            )
            assert prepared["execution_payload"]["runtime_rule_ref"]["version"] == "1.2.0"
            reactions = [item for item in prepared["execution_payload"]["materials"]
                         if item["kind"] == "character_reaction"]
            decisions = {f"{item['material_id']}:character_reaction": "TRUE" for item in reactions}
            responses = {item["material_id"]: f"Ответ {item['speaker_id']}" for item in reactions}
            start(connection, prepared["assessment_situation_id"])
            turn = submit_turn(
                connection, assessment_situation_id=prepared["assessment_situation_id"],
                request_id=f"runtime-{case_id}", turn_id=str(uuid4()), content="Проверочный содержательный ход",
                semantic_adapter=ControlledSemanticAdapter(decisions),
                character_adapter=ControlledCharacterAdapter(responses),
            )
            calls = [item for item in turn["events"] if item["event_type"] == "character_response"]
            assert len(calls) == expected_calls[case_id]
            if case_id in {"CASE.SPEC.02", "CASE.SPEC.07"}:
                assert calls == []
            if case_id == "CASE.SPEC.01":
                transition(connection, assessment_situation_id=prepared["assessment_situation_id"],
                           action="scenario_end", reason="A01 preservation", request_id="a01-end")
                transition(connection, assessment_situation_id=prepared["assessment_situation_id"],
                           action="close", reason="A01 preservation", request_id="a01-close")
                handoff = build_c45(connection, prepared["assessment_situation_id"])
                _, m6_input = resolve_m6_input(connection, str(handoff["handoff_id"]))
                source_targets = {
                    item["IndicatorID"]: item
                    for item in case["author_assessment_situation"]["IndicatorObservability"]
                }
                assert len(m6_input["indicator_targets"]) == len(source_targets)
                for target in m6_input["indicator_targets"]:
                    source = source_targets[target["indicator_id"]]
                    assert target["observation_condition"] == source["Конкретное условие"]
                    assert target["material_refs"] == source["Материалы и факты"]
                    assert target["adaptation_constraints"] == source["Что сохранить при адаптации"]
                    assert target["invariant_refs"] == source["Связанные инварианты"]
        connection.rollback()
