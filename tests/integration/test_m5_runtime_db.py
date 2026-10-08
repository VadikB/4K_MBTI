from __future__ import annotations

import copy
import json
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.database import ensure_m5_runtime_schema
from Api.m5_storage import (M5ImportConflict, import_package, package_readback,
                            prepare_assessment_situation as _prepare_assessment_situation,
                            record_technical_qa_evidence)
from Api.m5_cycle_runtime import create_cycle_session_for_case
from Api.m5_rule_engine import ControlledCharacterAdapter, ControlledSemanticAdapter
from Api.llm.contracts import LlmResponse
from Api.m5_scenario_runtime import (build_c45, execute_technical_c45, run_model_check_case03,
                                     start, submit_turn, trace, transition)
from Api.m5_case_runtime import checksum
from Api.snapshot_integrity import SNAPSHOT_OWNER_MISMATCH, SnapshotIntegrityError
from scripts.build_m5_case_package import OUTPUT


def prepare_assessment_situation(connection, **kwargs):
    cycle, session = create_cycle_session_for_case(
        connection,
        personalized_profile_id=kwargs["personalized_profile_id"],
        case_id=kwargs["case_id"],
        case_version=kwargs["case_version"],
        created_by=kwargs.get("qa_authorized_by", 99),
        usage_scope=kwargs.get("usage_scope", "assessment"),
    )
    return _prepare_assessment_situation(
        connection, cycle_db_id=int(cycle["id"]), session_db_id=int(session["id"]), **kwargs,
    )


@pytest.mark.integration
def test_m5_import_readback_and_rejected_as_are_transactional(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_runtime_test_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute("CREATE TABLE assessment_personalized_profiles (id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL, provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)")
        ensure_m5_runtime_schema(connection)

        imported = import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        assert imported == {"package_db_id": imported["package_db_id"], "created": True, "case_count": 5}
        repeated = import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        assert repeated["created"] is False
        readback = package_readback(connection, imported["package_db_id"])
        assert [(x["target_count"], x["material_count"], x["scenario_step_count"]) for x in readback["cases"]] == [
            (9, 3, 4), (9, 3, 4), (8, 3, 4), (8, 5, 4), (9, 3, 4),
        ]

        changed = copy.deepcopy(package)
        changed["cases"][0]["title"] += " changed"
        with pytest.raises(M5ImportConflict, match="PACKAGE_VERSION_CONTENT_CONFLICT"):
            with connection.transaction():
                import_package(connection, package=changed, manifest=manifest, execution_rules=rules)

        connection.execute("INSERT INTO assessment_personalized_profiles VALUES (7,'ready',%s::jsonb,'{}'::jsonb,%s)",
                           (json.dumps({"role_profile": {"code": "project_product_process_manager"}}), "c" * 64))
        prepared = prepare_assessment_situation(
            connection, assessment_situation_id=str(uuid4()), case_id="CASE-TDISC-01", case_version="v0.1",
            personalized_profile_id=7, substitutions=[], policy=policy,
            usage_scope="qa", qa_authorized_by=99,
        )
        assert prepared["execution_payload"]["ai_operations"]["semantic_decision"]["model"]
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
        with pytest.raises(psycopg.Error, match="Referenced M5 CaseVersion content is immutable"):
            with connection.transaction():
                connection.execute(
                    "UPDATE m5_case_targets SET target_json = '{}'::jsonb WHERE case_version_id = "
                    "(SELECT id FROM m5_case_versions WHERE case_id='CASE-TDISC-01')"
                )

        foreign_id = uuid4()
        foreign_snapshot = copy.deepcopy(prepared["snapshot"])
        foreign_snapshot["assessment_situation_id"] = str(uuid4())
        case_version_id = connection.execute(
            "SELECT id FROM m5_case_versions WHERE case_id='CASE-TDISC-01'"
        ).fetchone()["id"]
        membership = connection.execute(
            "SELECT cycle_db_id,session_db_id FROM m5_assessment_situations WHERE id=%s", (prepared["id"],)
        ).fetchone()
        connection.execute(
            """
            INSERT INTO m5_assessment_situations
                (assessment_situation_id, case_version_id, personalized_profile_id, cycle_db_id,session_db_id,usage_scope,
                 status, snapshot_json, execution_payload_json, snapshot_checksum)
            VALUES (%s,%s,7,%s,%s,'qa','rejected',%s::jsonb,%s::jsonb,%s)
            """,
            (
                foreign_id,
                case_version_id,
                membership["cycle_db_id"],
                membership["session_db_id"],
                json.dumps(foreign_snapshot),
                json.dumps(prepared["execution_payload"]),
                checksum(foreign_snapshot),
            ),
        )
        with pytest.raises(SnapshotIntegrityError) as wrong_owner:
            trace(connection, str(foreign_id))
        assert wrong_owner.value.code == SNAPSHOT_OWNER_MISMATCH

        started = start(connection, prepared["assessment_situation_id"])
        assert started["status"] == "active"
        request_id, turn_id = "request-1", str(uuid4())
        first = submit_turn(connection, assessment_situation_id=prepared["assessment_situation_id"],
                            request_id=request_id, turn_id=turn_id, content="Покажите готовность и выборку",
                            semantic_adapter=ControlledSemanticAdapter({"CASE-TDISC-01-D1:disclosure": "TRUE"}))
        assert not first["idempotent"]
        assert {x["material_id"] for x in first["events"]} >= {"CASE-TDISC-01-D1", "CASE-TDISC-01-D3"}
        repeated_turn = submit_turn(connection, assessment_situation_id=prepared["assessment_situation_id"],
                                    request_id=request_id, turn_id=turn_id, content="другая доставка",
                                    semantic_adapter=ControlledSemanticAdapter({}))
        assert repeated_turn["idempotent"]
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="pause", reason="test", request_id="pause-1")["status"] == "paused"
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="resume", reason="test", request_id="resume-1")["status"] == "active"
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="scenario_end", reason="done", request_id="end-1")["status"] == "scenario_ended"
        assert transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="close", reason="closed", request_id="close-1")["status"] == "closed"
        saved_trace = trace(connection, prepared["assessment_situation_id"])
        assert saved_trace["status"] == "closed"
        assert len(saved_trace["turns"]) == 1
        assert len({x["event_key"] for x in saved_trace["events"]}) == len(saved_trace["events"])
        handoff = build_c45(connection, prepared["assessment_situation_id"])
        assert handoff["envelope_json"]["contract"] == "C-45"
        assert handoff["envelope_json"]["evaluation_created"] is False
        assert handoff["envelope_json"]["boundary"]["turn_ids"] == [turn_id]
        assert {item["material_id"] for item in handoff["envelope_json"]["presented_materials"]} >= {
            "CASE-TDISC-01-D1", "CASE-TDISC-01-D3"
        }

        operation = prepared["execution_payload"]["ai_operations"]["technical_c45"]

        class TechnicalGateway:
            enabled = True
            model = operation["model"]
            base_url = operation["endpoint"].removesuffix("/chat/completions")

            def chat_with_trace(self, messages, **kwargs):
                payload = {
                    "contract": "C-54", "assessment_situation_id": prepared["assessment_situation_id"],
                    "handoff_id": str(handoff["handoff_id"]), "mode": "final",
                    "indicator_id": "K1.I13", "m2_version": "v1.1",
                    "status": "technical_received", "boundary_sequence": handoff["boundary_sequence"],
                }
                sent_parameters = {key: value for key, value in kwargs.items() if key != "routing_key"}
                return LlmResponse(json.dumps(payload), {"request_id": "provider-qa-1", "model": self.model},
                                   {"provider": operation["provider"], "endpoint": operation["endpoint"],
                                    "model": self.model, "parameters": sent_parameters, "messages": messages})

        receipt = execute_technical_c45(
            connection, assessment_situation_id=prepared["assessment_situation_id"],
            indicator_id="K1.I13", gateway=TechnicalGateway(),
        )
        assert receipt["status"] == "accepted"
        assert receipt["controlled_test"] is True
        runtime_trace = trace(connection, prepared["assessment_situation_id"])
        assert runtime_trace["ai_attempts"][0]["sent_json"]["provider"] == operation["provider"]
        assert runtime_trace["c54_receipts"][0]["validation_json"]["methodological_result"] is False
        connection.rollback()


@pytest.mark.integration
def test_all_five_cases_run_through_qa_runtime_and_case04_has_both_branch_outcomes(test_database_url):
    package = json.loads((OUTPUT / "case-package.json").read_text())
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    policy = json.loads((OUTPUT / "admission-policy.json").read_text())
    rules = json.loads((OUTPUT / "execution-rules.json").read_text())
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        schema = "m5_scenarios_pytest_" + uuid4().hex
        connection.execute(psycopg.sql.SQL("CREATE SCHEMA {}").format(psycopg.sql.Identifier(schema)))
        connection.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(schema)))
        connection.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
        connection.execute("INSERT INTO users VALUES (99)")
        connection.execute("""CREATE TABLE assessment_personalized_profiles
            (id BIGINT PRIMARY KEY, status TEXT NOT NULL, content_json JSONB NOT NULL,
             provenance_json JSONB NOT NULL, checksum TEXT NOT NULL)""")
        ensure_m5_runtime_schema(connection)
        import_package(connection, package=package, manifest=manifest, execution_rules=rules)
        profiles = {}
        for index, role in enumerate(sorted({x["base_role"] for x in package["cases"]}), 1):
            profiles[role] = index
            connection.execute("INSERT INTO assessment_personalized_profiles VALUES (%s,'ready',%s::jsonb,'{}'::jsonb,%s)",
                               (index, json.dumps({"role_profile": {"code": role}}), str(index) * 64))

        for case in package["cases"]:
            prepared = prepare_assessment_situation(
                connection, assessment_situation_id=str(uuid4()), case_id=case["case_id"], case_version=case["version"],
                personalized_profile_id=profiles[case["base_role"]], substitutions=[], policy=policy,
                usage_scope="qa", qa_authorized_by=99,
            )
            start(connection, prepared["assessment_situation_id"])
            outcomes = {}
            for material in case["materials"]:
                condition = material["disclosure_condition"]["type"]
                if condition == "semantic_request": outcomes[f"{material['material_id']}:disclosure"] = "TRUE"
                if condition == "method_owner_unresolved": outcomes[f"{material['material_id']}:qa_unresolved_branch"] = "TRUE"
                if material["event_condition"]["type"].startswith("after_first_"):
                    outcomes[f"{material['material_id']}:mandatory"] = "TRUE"
                if material["event_condition"]["type"].startswith("on_"):
                    outcomes[f"{material['material_id']}:character_reaction"] = "TRUE"
            outcomes[f"{case['case_id']}:{case['scenario'][0]['step_id']}:completion"] = "TRUE"
            progress_turn_id = str(uuid4())
            submit_turn(connection, assessment_situation_id=prepared["assessment_situation_id"], request_id="progress-1",
                        turn_id=progress_turn_id, content="Содержательное действие без обязательного ключевого слова",
                        semantic_adapter=ControlledSemanticAdapter(outcomes),
                        character_adapter=ControlledCharacterAdapter({"CASE-TDISC-04-D3": "Нина описывает свой следующий шаг и границу ответственности."}))
            if case["case_id"] == "CASE-TDISC-03":
                scheme = {"routes": {"A": "catalog", "B": "defer", "C": "unique", "D": "defer",
                                     "E": "reject_for_input", "F": "catalog"}}
                assessee_check = run_model_check_case03(
                    connection, assessment_situation_id=prepared["assessment_situation_id"], scheme=scheme,
                    rules=rules["model_checks"]["CASE-TDISC-03"], initiated_by="assessee",
                    scheme_authored_by="assessee", turn_id=progress_turn_id)
                assert assessee_check["result"]["status"] == "COMPLETED"
                sergey_check = run_model_check_case03(
                    connection, assessment_situation_id=prepared["assessment_situation_id"],
                    scheme={"routes": {"A": "catalog"}}, rules=rules["model_checks"]["CASE-TDISC-03"],
                    initiated_by="sergey", scheme_authored_by="assessee")
                assert sergey_check["result"]["status"] == "INDETERMINATE"
            transition(connection, assessment_situation_id=prepared["assessment_situation_id"], action="scenario_end",
                       reason="controlled technical trajectory", request_id="end-1")
            saved = trace(connection, prepared["assessment_situation_id"])
            assert saved["turns"] and saved["events"] and saved["decisions"]
            assert saved["state"]["state_json"]["current_stage"] == "scenario_end"
            if case["case_id"] == "CASE-TDISC-04":
                assert any(x["speaker_type"] == "character" and x["speaker_id"] == "CASE-TDISC-04-R02"
                           for x in saved["turns"])
                assert any(x["event_type"] == "character_response" for x in saved["events"])
            handoff = build_c45(connection, prepared["assessment_situation_id"], mode="interim")
            assert handoff["envelope_json"]["boundary_sequence"] > 0
            evidence = record_technical_qa_evidence(
                connection, assessment_situation_id=prepared["assessment_situation_id"], trajectory="content_progress",
                expected={"runtime": "trace_saved"}, actual={"events": len(saved["events"])}, defects=[], performed_by=99)
            assert evidence["evidence_json"]["eligibility"] == "technical_qa"
            assert evidence["evidence_json"]["empirical_pilot"] == "NOT_RUN"

            for trajectory in ("premature_solution", "refusal_or_escalation", "pause_resume_termination"):
                extra = prepare_assessment_situation(
                    connection, assessment_situation_id=str(uuid4()), case_id=case["case_id"], case_version=case["version"],
                    personalized_profile_id=profiles[case["base_role"]], substitutions=[], policy=policy,
                    usage_scope="qa", qa_authorized_by=99)
                start(connection, extra["assessment_situation_id"])
                if trajectory == "pause_resume_termination":
                    transition(connection, assessment_situation_id=extra["assessment_situation_id"], action="pause",
                               reason="controlled pause", request_id="pause")
                    transition(connection, assessment_situation_id=extra["assessment_situation_id"], action="resume",
                               reason="controlled resume", request_id="resume")
                controlled = {}
                for material in case["materials"]:
                    if material["disclosure_condition"]["type"] == "semantic_request":
                        controlled[f"{material['material_id']}:disclosure"] = "FALSE"
                    if material["disclosure_condition"]["type"] == "method_owner_unresolved":
                        controlled[f"{material['material_id']}:qa_unresolved_branch"] = "FALSE"
                    if material["event_condition"]["type"].startswith("after_first_"):
                        controlled[f"{material['material_id']}:mandatory"] = "FALSE"
                    if material["event_condition"]["type"].startswith("on_"):
                        controlled[f"{material['material_id']}:character_reaction"] = "FALSE"
                controlled[f"{case['case_id']}:{case['scenario'][0]['step_id']}:completion"] = (
                    "FALSE" if trajectory == "premature_solution" else "UNKNOWN")
                submit_turn(connection, assessment_situation_id=extra["assessment_situation_id"], request_id="trajectory-turn",
                            turn_id=str(uuid4()), content=f"Controlled trajectory: {trajectory}",
                            semantic_adapter=ControlledSemanticAdapter(controlled),
                            character_adapter=ControlledCharacterAdapter({}))
                action = "scenario_end" if trajectory == "premature_solution" else "terminate"
                before_transition = trace(connection, extra["assessment_situation_id"])
                last_sequence_before_transition = max(x["sequence_no"] for x in before_transition["events"])
                transition(connection, assessment_situation_id=extra["assessment_situation_id"], action=action,
                           reason=trajectory, request_id="trajectory-finish")
                extra_trace = trace(connection, extra["assessment_situation_id"])
                if action == "terminate":
                    assert extra_trace["status"] == "terminated"
                    # Завершение не синтезирует предметные события: они могут появиться только при обработке Turn.
                    after_transition = [x for x in extra_trace["events"]
                                        if x["sequence_no"] > last_sequence_before_transition]
                    assert [x["event_type"] for x in after_transition] == ["interaction_terminated"]
                record_technical_qa_evidence(
                    connection, assessment_situation_id=extra["assessment_situation_id"], trajectory=trajectory,
                    expected={"action": action}, actual={"status": extra_trace["status"]}, defects=[], performed_by=99)

        case4 = next(x for x in package["cases"] if x["case_id"] == "CASE-TDISC-04")
        negative = prepare_assessment_situation(
            connection, assessment_situation_id=str(uuid4()), case_id=case4["case_id"], case_version=case4["version"],
            personalized_profile_id=profiles[case4["base_role"]], substitutions=[], policy=policy,
            usage_scope="qa", qa_authorized_by=99)
        start(connection, negative["assessment_situation_id"])
        submit_turn(connection, assessment_situation_id=negative["assessment_situation_id"], request_id="negative-1",
                    turn_id=str(uuid4()), content="Технический отрицательный пример ветви",
                    semantic_adapter=ControlledSemanticAdapter({"CASE-TDISC-04-D1.ASYA:qa_unresolved_branch": "FALSE"}))
        transition(connection, assessment_situation_id=negative["assessment_situation_id"], action="scenario_end",
                   reason="branch stayed closed", request_id="negative-end")
        negative_trace = trace(connection, negative["assessment_situation_id"])
        assert not any(x["material_id"] == "CASE-TDISC-04-D1.ASYA" and x["event_type"] == "material_disclosed"
                       for x in negative_trace["events"])
        assert any(x["material_id"] == "CASE-TDISC-04-D1.ASYA" and x["event_type"] == "conditional_branch_not_opened"
                   for x in negative_trace["events"])
        connection.rollback()
