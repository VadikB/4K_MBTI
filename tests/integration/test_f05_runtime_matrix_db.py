"""F05: execute the versioned 34-scenario plan through product preparation/runtime APIs."""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from Api import participant_profile
from Api import m10_orchestration
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import publication_plan, publish_catalog
from Api.m5_functional_generation_service import checksum as functional_checksum
from Api.m5_rule_engine import CharacterReply, Decision, RuleOutcome
from Api.m5_rule_engine import DeepSeekCharacterAdapter, DeepSeekSemanticAdapter
from Api.m5_runtime_rules import import_runtime_rule_version, load_runtime_rule_package
from Api.m5_scenario_runtime import submit_turn, trace, transition
from Api.m5_storage import import_package
from Api.m10_product_flow import read_runtime, start_prepared
from Api.m7_completion import complete
from Api.m6_worker_v2 import run_request as run_evidence
from Api.m6_assessment_worker_v2 import run_request as run_assessment
from Api.m8_results import read_latest_report
from Api.product_cycle_preparation_queue import ProductCyclePreparationQueue
from Api.schemas import PersonalizedProfileSelection
from scripts.build_m5_functional_package import OUTPUT as FUNCTIONAL_OUTPUT
from scripts.build_m5_sales_package import build_execution_rules
from tests.integration.test_m10_product_path_db import product_db, _drain_product_pipeline  # noqa: F401

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]
SOURCE = FUNCTIONAL_OUTPUT / "sources/functional-v0.2"
PLAN = SOURCE / "08_qa/Scenario_regression_plan_v0.2.json"
GLOBAL_CASES = [f"CASE.SPEC.{number:02d}" for number in range(1, 9)]
SCOPE_CASES = {
    "R_SCOPE_PRICE": "CASE.SPEC.02", "R_SCOPE_NEW_PROFESSION": "CASE.SPEC.04",
    "R_SCOPE_NO_REAL_EVENT": "CASE.SPEC.05", "R_SCOPE_NO_ROLE": "CASE.SPEC.06",
    "R_SCOPE_LINKS": "CASE.SPEC.02", "R_SCOPE_PAUSE": "CASE.SPEC.08",
    "R_SCOPE_BUDGET": "CASE.SPEC.01", "R_SCOPE_INVARIANT": "CASE.SPEC.02",
}


class FunctionalGateway:
    enabled = True

    def chat_with_trace(self, messages, **kwargs):
        payload = json.loads(next(item["content"] for item in reversed(messages) if item["role"] == "user"))
        if ":generation:" in kwargs["routing_key"]:
            candidate = copy.deepcopy(payload["author_as_example"])
            material_ids = [item["MaterialID"] for item in candidate["Материалы"]]
            event_ids = [item["EventID"] for item in candidate["События"]]
            character_ids = [item["CharacterID"] for item in candidate["Активные персонажи"]]
            for index, target in enumerate(candidate["IndicatorObservability"]):
                target.update({
                    "material_refs": material_ids[:1], "event_refs": event_ids[:1],
                    "character_refs": character_ids[:1], "authority_refs": ["participant"],
                    "author_mapping": {
                        "source_pointer": f"/IndicatorObservability/{index}",
                        "source_checksum": functional_checksum(
                            payload["author_as_example"]["IndicatorObservability"][index]
                        ),
                    },
                })
            content = json.dumps(candidate, ensure_ascii=False)
        else:
            required = (payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"]
            content = json.dumps({"checks": [{
                "check_id": item["check_id"], "status": "PASS", "reason": "F05 controlled admission",
                "evidence_paths": [], "findings": [],
                "adversarial_review": {"candidate_conflicts": [], "resolution": "controlled fixture"},
            } for item in required]}, ensure_ascii=False)
        return SimpleNamespace(content=content, sent={}, provider={"finish_reason": "stop"})


class ScenarioSemanticAdapter:
    def __init__(self, outcome: RuleOutcome): self.outcome = outcome

    def decide(self, *, rule, text, turn_id, context):
        return Decision(self.outcome, rule.get("decision_code", "F05"), "F05 controlled scenario",
                        (turn_id,), adapter="controlled", controlled_test=True)


class ScenarioCharacterAdapter:
    def __init__(self, enabled: bool): self.enabled = enabled

    def respond(self, *, material, character, text, turn_id, context):
        return CharacterReply("COMPLETED" if self.enabled else "UNKNOWN",
                              "Контролируемая реакция персонажа" if self.enabled else None,
                              "controlled", controlled_test=True)


def _case_for(item: dict, index: int) -> str:
    return item.get("CaseID") or SCOPE_CASES.get(item["TestID"]) or GLOBAL_CASES[index % len(GLOBAL_CASES)]


def _scenario_outcome(test_id: str) -> RuleOutcome:
    negative = {"R_ALL_AUTHORITY", "R_ALL_NO_OPPORTUNITY", "R01_HIDDEN", "R02_PARTIAL",
                "R03_PRIVATE", "R06_LIMITED", "R06_CAUSE", "R_SCOPE_NO_REAL_EVENT",
                "R_SCOPE_NO_ROLE", "R_SCOPE_LINKS", "R_SCOPE_INVARIANT"}
    return RuleOutcome.UNKNOWN if test_id in negative else RuleOutcome.TRUE


def _jsonable(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _a06_runtime_assertions(*, test_id: str, saved: dict, paused: dict | None,
                            response: dict, replay: dict, request: dict) -> list[dict]:
    """Return named, primary-trace assertions for the A06 scenario matrix.

    These checks intentionally describe only the deterministic runtime contract.
    They do not turn a controlled adapter result into methodological acceptance.
    """
    events = saved["events"]
    turns = saved["turns"]
    event_types = [item["event_type"] for item in events]
    sequences = [int(item["sequence_no"]) for item in events]
    assertions = [
        {"code": "A06.SEQUENCE_STRICT", "passed": sequences == sorted(set(sequences)),
         "evidence": {"sequence_no": sequences}},
        {"code": "A06.REQUEST_IDEMPOTENT", "passed": replay.get("idempotent") is True,
         "evidence": {"request_id": request["request_id"], "turn_id": request["turn_id"],
                      "replay_turn_id": str(replay["turn"]["turn_id"])}},
        {"code": "A06.ONE_ASSESSEE_TURN", "passed": len([
            item for item in turns if item["speaker_type"] == "assessee"
        ]) == 1, "evidence": {"speaker_types": [item["speaker_type"] for item in turns]}},
        {"code": "A06.NO_DUPLICATE_EVENT_KEY", "passed": len([
            item["event_key"] for item in events
        ]) == len(set(item["event_key"] for item in events)),
         "evidence": {"event_keys": [item["event_key"] for item in events]}},
    ]
    if test_id == "R_ALL_PAUSE":
        assertions.append({"code": "A06.PAUSE_BEFORE_TURN", "passed": paused is not None and not paused["turns"],
                           "evidence": {"paused_turn_count": len((paused or {}).get("turns", []))}})
    if test_id == "R_ALL_STOP":
        assertions.append({"code": "A06.STOP_IS_TERMINAL", "passed": saved["status"] == "terminated",
                           "evidence": {"status": saved["status"]}})
    if test_id in {"R_ALL_NO_OPPORTUNITY", "R_ALL_FINAL_QUESTION"}:
        scenario_end = [item for item in events if item["event_type"] == "scenario_completed"]
        assertions.append({"code": "A06.SCENARIO_END_RECORDED", "passed": bool(scenario_end),
                           "evidence": {"event_types": event_types,
                                        "scenario_end_count": len(scenario_end)}})
    if test_id in {"R_ALL_AUTHORITY", "R_ALL_NO_OPPORTUNITY", "R01_HIDDEN", "R02_PARTIAL",
                   "R03_PRIVATE", "R06_LIMITED", "R06_CAUSE", "R_SCOPE_NO_REAL_EVENT",
                   "R_SCOPE_NO_ROLE", "R_SCOPE_LINKS", "R_SCOPE_INVARIANT"}:
        assertions.append({"code": "A06.UNKNOWN_DOES_NOT_OPEN_BRANCH",
                           "passed": not any(item["event_type"] in {"character_response", "mandatory_update"}
                                             for item in events if request["turn_id"] in {
                                                 item.get("cause_json", {}).get("turn_id"),
                                                 item.get("cause_json", {}).get("trigger_turn_id"),
                                             }),
                           "evidence": {"event_types": event_types}})
    assertions.append({"code": "A06.RESPONSE_BOUND_TO_REQUEST",
                       "passed": str(response["turn"]["turn_id"]) == request["turn_id"],
                       "evidence": {"response_turn_id": str(response["turn"]["turn_id"])}})
    assert all(item["passed"] for item in assertions), assertions
    return assertions


def test_f05_all_34_scenarios_use_generated_as_and_runtime_apis(product_db, monkeypatch):
    plan = json.loads(PLAN.read_text())
    assert len(plan) == 34
    with product_db() as connection:
        package = json.loads((FUNCTIONAL_OUTPUT / "case-package.json").read_text())
        manifest = json.loads((FUNCTIONAL_OUTPUT / "manifest.json").read_text())
        legacy_rules = json.loads((FUNCTIONAL_OUTPUT / "execution-rules.json").read_text())
        runtime_package = FUNCTIONAL_OUTPUT.parent.parent / "functional-personalization-runtime/1.1.0"
        fixture_package = copy.deepcopy(package)
        bindings = copy.deepcopy(load_runtime_rule_package(runtime_package, package["cases"]))
        for case in fixture_package["cases"]:
            case["status"] = "FROZEN"
            case["author_case"]["Status"] = "FROZEN"
            bindings["bindings"]["case_bindings"][case["case_id"]]["case_checksum"] = checksum(case)
        imported = import_package(connection, package=fixture_package, manifest=manifest, execution_rules=legacy_rules)
        runtime = import_runtime_rule_version(
            connection, bindings, build_execution_rules(fixture_package["cases"], bindings["bindings"]),
        )
        cases = {row["case_id"]: row for row in connection.execute(
            "SELECT * FROM m5_case_versions WHERE package_id=%s", (imported["package_db_id"],)
        ).fetchall()}
        for case in cases.values():
            for scope in ("case_format", "case_dialogue", "assessment_situation"):
                evidence = {"schema_version": 1, "eligibility": "user_admission", "scope": scope,
                    "result": "PASS", "case_ref": {"id": case["case_id"], "version": case["case_version"],
                    "checksum": case["content_checksum"]}, "base_role": case["base_role"],
                    "usage_scopes": ["assessment"],
                    "origin": {"type": "human_review", "actor_ref": "review:f05-isolated-fixture"}}
                connection.execute("""INSERT INTO m5_qa_evidence
                    (case_version_id,scope,result,evidence_json,evidence_checksum)
                    VALUES(%s,%s,'PASS',%s::jsonb,%s)""",
                    (case["id"], scope, json.dumps(evidence, ensure_ascii=False), checksum(evidence)))
        connection.execute("ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT REFERENCES m5_catalogs(id)")
        connection.execute("ALTER TABLE assessment_configurations ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE")
        specialist_role = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id
            WHERE r.code='specialist_expert' AND v.status='published'""").fetchone()["id"]
        organization_context = connection.execute("""SELECT v.id FROM assessment_organization_context_versions v
            JOIN assessment_organization_contexts c ON c.id=v.organization_context_id
            WHERE c.organization_id=10 AND v.status='published'""").fetchone()["id"]
        profiles = []
        for index, item in enumerate(plan):
            case_id = _case_for(item, index); case = cases[case_id]
            decision = publication_plan(connection, package_db_id=imported["package_db_id"],
                case_version_ids=[int(case["id"])], usage_scope="assessment", organization_id=10,
                runtime_rule_version_id=runtime["id"])
            assert decision["publishable"] is True
            catalog = publish_catalog(connection, catalog_id=f"f05-{index:02d}", catalog_version="1.0",
                package_db_id=imported["package_db_id"], case_version_ids=[int(case["id"])],
                usage_scope="assessment", organization_id=10, published_by=99,
                decision_basis="F05 isolated runtime matrix", idempotency_key=f"f05-catalog-{index:02d}",
                runtime_rule_version_id=runtime["id"])
            config_id = 1000 + index
            connection.execute("""INSERT INTO assessment_configurations
                (id,methodology_version_id,status,code,name,catalog_version_id,is_default)
                VALUES(%s,1,'published',%s,%s,%s,FALSE)""",
                (config_id, f"f05-{index:02d}", f"F05 {item['TestID']}", catalog["catalog_db_id"]))
            profile = participant_profile.confirm(connection, user_id=99,
                selection=PersonalizedProfileSelection(organization_context_version_id=organization_context,
                    role_profile_version_id=specialist_role, assessment_configuration_id=config_id),
                full_name="F05 synthetic specialist", position="", duties="")
            profiles.append(profile["id"])
        connection.execute("""CREATE TABLE product_cycle_preparation_operations (
            id BIGSERIAL PRIMARY KEY,operation_id TEXT UNIQUE,user_id BIGINT,request_json JSONB,request_checksum TEXT,
            status TEXT DEFAULT 'queued',attempts INTEGER DEFAULT 0,result_json JSONB,error_code TEXT,error_message TEXT,
            worker_id TEXT,attempt_token UUID,locked_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW(),updated_at TIMESTAMP DEFAULT NOW(),completed_at TIMESTAMP)""")
        connection.commit()

    monkeypatch.setattr("Api.product_cycle_preparation_queue.get_connection", product_db)
    real_index = 24 if os.getenv("RUN_F05_REAL_PROVIDER") == "1" else None
    real_gateway = None
    if real_index is not None:
        from dotenv import load_dotenv
        from Api.llm.deepseek_gateway import DeepSeekGateway
        env_file = os.getenv("P4K_REAL_ENV_FILE")
        if env_file: load_dotenv(env_file, override=False)
        real_gateway = DeepSeekGateway()
        assert real_gateway.enabled

    class RoutedGateway(FunctionalGateway):
        def chat_with_trace(self, messages, **kwargs):
            real_generation = os.getenv("RUN_F05_REAL_GENERATION", "1") == "1"
            if (real_index is not None and real_generation
                    and kwargs.get("routing_key", "").startswith(f"f05-{real_index:02d}-")):
                return real_gateway.chat_with_trace(messages, **kwargs)
            return super().chat_with_trace(messages, **kwargs)

    monkeypatch.setattr("Api.llm.deepseek_gateway.DeepSeekGateway", RoutedGateway)
    queue = ProductCyclePreparationQueue()
    results = []
    real_provider_evidence = None
    controlled_m8 = []
    run_indices = [real_index] if real_index is not None else list(range(len(plan)))
    for index in run_indices:
        item = plan[index]
        test_id = item["TestID"]; expected_case = _case_for(item, index)
        operation_id = f"f05-{index:02d}-{test_id.lower()}"
        queue.enqueue(operation_id=operation_id, user_id=99, request={
            "personalized_profile_id": profiles[index], "idempotency_key": operation_id,
            "selected_skills": ["K1", "K2", "K3", "K4"],
        })
        queue._process(queue._claim())
        operation = queue.get_status(operation_id)
        if operation["status"] != "completed" and os.environ.get("F05_EVIDENCE_DIR"):
            failure_path = Path(os.environ["F05_EVIDENCE_DIR"]) / "real-provider-error.json"
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            failure_path.write_text(json.dumps(_jsonable(operation), ensure_ascii=False, indent=2) + "\n")
        assert operation["status"] == "completed", operation
        prepared = operation["result_json"]
        cycle_id = str(prepared["plan"]["cycle_id"])
        as_id = str(prepared["decision"]["assessment_situation_id"])
        with product_db() as connection:
            started = start_prepared(connection, user_id=99, cycle_id=cycle_id, key=f"{operation_id}-start")
            assert started["decision"]["selected_case_id"] == expected_case
            request = {"request_id": f"{operation_id}-turn", "turn_id": str(uuid4()),
                       "content": "F05: " + item["Условие теста"]}
            if index == real_index:
                request["content"] = (
                    "Изначально я рекомендовал немедленно закрепить Сергея за задачей. "
                    "После проверки журнала испытаний выяснилось, что новая сборка дала два сбоя из пяти, "
                    "а Сергей не участвовал в этом контуре. Поэтому меняю рекомендацию: сначала назначаю "
                    "повторную проверку на десяти запусках с заранее заданным критерием — не более одного "
                    "сбоя; Сергею передаю только анализ причин, решение о внедрении принимаю после результатов."
                )
            paused = None
            if test_id == "R_ALL_PAUSE":
                transition(connection, assessment_situation_id=as_id, action="pause", reason="F05", request_id=f"{operation_id}-pause")
                paused = trace(connection, as_id)
                transition(connection, assessment_situation_id=as_id, action="resume", reason="F05", request_id=f"{operation_id}-resume")
                assert not paused["turns"]
            if index == real_index:
                operations = connection.execute("SELECT execution_payload_json FROM m5_assessment_situations WHERE assessment_situation_id=%s",
                    (as_id,)).fetchone()["execution_payload_json"]["ai_operations"]
                runtime_gateway = type(real_gateway)(
                    base_url=operations["semantic_decision"]["endpoint"].removesuffix("/chat/completions"),
                    model=operations["semantic_decision"]["model"],
                )
                semantic_adapter = DeepSeekSemanticAdapter(gateway=runtime_gateway, operation=operations["semantic_decision"])
                character_adapter = DeepSeekCharacterAdapter(gateway=runtime_gateway, operation=operations["character_response"])
            else:
                semantic_adapter = ScenarioSemanticAdapter(_scenario_outcome(test_id))
                character_adapter = ScenarioCharacterAdapter(_scenario_outcome(test_id) == RuleOutcome.TRUE)
            response = submit_turn(connection, assessment_situation_id=as_id, **request,
                semantic_adapter=semantic_adapter, character_adapter=character_adapter)
            replay = submit_turn(connection, assessment_situation_id=as_id, **request,
                semantic_adapter=ScenarioSemanticAdapter(_scenario_outcome(test_id)),
                character_adapter=ScenarioCharacterAdapter(False))
            assert replay["idempotent"] is True and str(replay["turn"]["turn_id"]) == request["turn_id"]
            if test_id == "R_ALL_STOP":
                transition(connection, assessment_situation_id=as_id, action="terminate", reason="explicit_stop",
                           request_id=f"{operation_id}-stop")
            elif test_id in {"R_ALL_NO_OPPORTUNITY", "R_ALL_FINAL_QUESTION"}:
                transition(connection, assessment_situation_id=as_id, action="scenario_end", reason="F05",
                           request_id=f"{operation_id}-end")
            saved = trace(connection, as_id)
            assertions = _a06_runtime_assertions(test_id=test_id, saved=saved, paused=paused,
                                                  response=response, replay=replay, request=request)
            runtime_readback = read_runtime(connection, cycle_id=cycle_id)
            handoff = saved["state"]["state_json"]
            generated = connection.execute("""SELECT execution_payload_json FROM m5_assessment_situations
                WHERE assessment_situation_id=%s""", (as_id,)).fetchone()["execution_payload_json"]["ai_operations"]["functional_personalization"]
            assert functional_checksum(generated["accepted_as"]) == generated["candidate_checksum"]
            assert len([turn for turn in saved["turns"] if turn["speaker_type"] == "assessee"]) == 1
            assert runtime_readback["current_situation"]["assessment_situation_id"] == as_id
            results.append({"test_id": test_id, "case_id": expected_case, "cycle_id": cycle_id,
                "assessment_situation_id": as_id, "request": request, "response": _jsonable(response),
                "events": _jsonable(saved["events"]), "state": _jsonable(handoff),
                "runtime_assertions": assertions,
                "readback": _jsonable(runtime_readback), "snapshot": {
                    "candidate_checksum": generated["candidate_checksum"],
                    "input_snapshot_checksum": generated["input_snapshot_checksum"],
                    "tester_input_checksum": generated["tester_input_checksum"],
                }})
            if index == real_index:
                complete(connection, cycle_id=cycle_id, key=f"{operation_id}-complete", action="complete",
                         reason="f05_real_provider_path", initiated_by=99)
            elif real_index is None and index in {0, 24}:
                complete(connection, cycle_id=cycle_id, key=f"{operation_id}-complete", action="complete",
                         reason="f05_controlled_m8_path", initiated_by=99)
            connection.commit()
        if real_index is None and index in {0, 24}:
            _drain_product_pipeline(product_db)
            with product_db() as connection:
                report = read_latest_report(connection, cycle_id, "assessee")
                pipeline = connection.execute("SELECT status,stage,error_code FROM m10_pipeline_runs WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)",
                                              (cycle_id,)).fetchone()
            assert pipeline == {"status": "ready", "stage": "report_ready", "error_code": None}
            controlled_m8.append({"test_id": test_id, "cycle_id": cycle_id,
                                  "pipeline": _jsonable(pipeline), "report": _jsonable(report)})
        if index == real_index:
            from Api.llm.provider_contract import load_provider_contract
            provider = load_provider_contract()
            m6_gateway = type(real_gateway)(
                api_keys=real_gateway.api_keys,
                base_url=provider["endpoint"].removesuffix("/chat/completions"),
                model=provider["model"],
            )
            assert m10_orchestration.advance_once(connection_factory=product_db, gateway=m6_gateway)
            with product_db() as connection:
                evidence_request = connection.execute(
                    "SELECT id FROM m6_processing_requests ORDER BY created_at DESC LIMIT 1").fetchone()
            run_evidence(evidence_request["id"], connection_factory=product_db, gateway=m6_gateway)
            assert m10_orchestration.advance_once(connection_factory=product_db, gateway=m6_gateway)
            with product_db() as connection:
                assessment_request = connection.execute(
                    "SELECT id FROM m6_assessment_requests ORDER BY created_at DESC LIMIT 1").fetchone()
                if assessment_request is None and os.environ.get("F05_EVIDENCE_DIR"):
                    diagnostics = connection.execute("""SELECT r.status,a.status AS attempt_status,a.error_code,a.trace_json
                        FROM m6_processing_requests r LEFT JOIN m6_processing_attempts a ON a.request_id=r.id
                        ORDER BY a.attempt_no DESC LIMIT 1""").fetchone()
                    path = Path(os.environ["F05_EVIDENCE_DIR"]) / "real-provider-processing-error.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(_jsonable(diagnostics), ensure_ascii=False, indent=2) + "\n")
            assert assessment_request is not None
            run_assessment(assessment_request["id"], connection_factory=product_db, gateway=m6_gateway)
            assert m10_orchestration.advance_once(connection_factory=product_db, gateway=m6_gateway)
            with product_db() as connection:
                report = read_latest_report(connection, cycle_id, "assessee")
                pipeline = connection.execute("SELECT status,stage,error_code FROM m10_pipeline_runs WHERE cycle_db_id=(SELECT id FROM m5_cycles WHERE cycle_id=%s)",
                                              (cycle_id,)).fetchone()
                attempts = connection.execute("SELECT action_key,action_type,outcome,input_checksum,intended_json,sent_json,provider_json,response_json,validation_json FROM m5_ai_attempts ORDER BY id").fetchall()
                assessment_diagnostics = connection.execute("""SELECT r.status,a.status AS attempt_status,a.error_code,a.trace_json
                    FROM m6_assessment_requests r LEFT JOIN m6_assessment_attempts a ON a.request_id=r.id
                    ORDER BY a.attempt_no DESC LIMIT 1""").fetchone()
                if pipeline["status"] != "ready" and os.environ.get("F05_EVIDENCE_DIR"):
                    path = Path(os.environ["F05_EVIDENCE_DIR"]) / "real-provider-assessment-error.json"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(_jsonable(assessment_diagnostics), ensure_ascii=False, indent=2) + "\n")
                assert pipeline == {"status": "ready", "stage": "report_ready", "error_code": None}, assessment_diagnostics
            assert report["c67"]["contract"] == "C-67"
            assert report["c67"]["skills"]
            real_provider_evidence = {"cycle_id": cycle_id, "test_id": test_id,
                "functional_personalization": _jsonable(generated),
                "runtime": _jsonable(results[-1]),
                "pipeline": _jsonable(pipeline), "runtime_ai_attempts": _jsonable(attempts),
                "report": _jsonable(report), "limitations": [
                    "single real-provider functional trajectory", "human methodological approval NOT_RUN"]}
    expected_count = 1 if real_index is not None else 34
    assert len(results) == expected_count
    if real_index is None:
        assert {x["test_id"] for x in results} == {x["TestID"] for x in plan}
    output = os.environ.get("F05_EVIDENCE_DIR")
    if output:
        root = Path(output); (root / "results").mkdir(parents=True, exist_ok=True)
        if real_index is None:
            for item in results:
                (root / "results" / f"{item['test_id'].lower()}.json").write_text(
                    json.dumps(item, ensure_ascii=False, indent=2) + "\n")
            summary = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "plan_ref": str(PLAN.relative_to(ROOT)), "plan_checksum": functional_checksum(PLAN.read_bytes()),
                "planned": 34, "completed": len(results), "passed_runtime_contract": len(results),
                "case_counts": {case_id: sum(x["case_id"] == case_id for x in results) for case_id in sorted(cases)},
                "limitations": ["controlled semantic/character adapters", "not a methodological CASE.SPEC.01-09 acceptance"]}
            (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
            (root / "controlled-functional-to-m8.json").write_text(
                json.dumps({"schema_version": 1, "paths": controlled_m8,
                    "limitations": ["controlled M6/M8 provider fixtures", "technical proof only"]},
                    ensure_ascii=False, indent=2) + "\n")
        if real_provider_evidence is not None:
            (root / "real-provider-to-m8.json").write_text(
                json.dumps(real_provider_evidence, ensure_ascii=False, indent=2) + "\n")
