from __future__ import annotations

import json
from contextlib import contextmanager

import psycopg
import pytest
from psycopg.rows import dict_row

from Api import assessment_analysis_queue as queue_module
from Api.assessment_analysis_queue import AssessmentAnalysisQueue
from Api.assessment_configuration import LEGACY_METHODOLOGY_DEFINITION, LEGACY_SCENARIO_DEFINITION, definition_checksum
from Api.config import settings


def frozen_agent_definitions() -> dict:
    result = {}
    for competency in LEGACY_METHODOLOGY_DEFINITION["competencies"]:
        code = competency["code"]
        definition = {
            "schema_version": 1, "code": code, "version": 1, "competency_code": code,
            "instruction_markdown": f"Оцени компетенцию {code}.",
            "input_contract": {"code": "competency_evaluation_input", "version": 1},
            "output_contract": {"code": "competency_evaluation_output", "version": 1},
            "executor": {"code": competency["evaluator"], "version": 1},
            "runtime": {"mode": "legacy_adapter"},
        }
        result[code] = {
            "id": len(result) + 1, "code": code, "name": code, "version": 1,
            "checksum": definition_checksum(definition), "definition": definition,
        }
    return result


@pytest.fixture
def analysis_database(test_database_url, monkeypatch):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_shadow_evaluation_runs")
        connection.execute("DROP TABLE IF EXISTS assessment_stage_runs")
        connection.execute("DROP TABLE IF EXISTS assessment_analysis_jobs")
        connection.execute("DROP TABLE IF EXISTS user_sessions")
        connection.execute(
            """
            CREATE TABLE user_sessions (
                id SERIAL PRIMARY KEY,
                session_code TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                started_at TIMESTAMP DEFAULT NOW(),
                finished_at TIMESTAMP,
                analysis_started_at TIMESTAMP,
                analysis_completed_at TIMESTAMP,
                error_stage TEXT,
                error_code TEXT,
                error_message TEXT,
                error_retryable BOOLEAN NOT NULL DEFAULT FALSE
                ,current_stage_id TEXT
                ,execution_snapshot_json JSONB
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_stage_runs (
                id BIGSERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
                preparation_job_id BIGINT,
                stage_id TEXT NOT NULL,
                component_code TEXT NOT NULL,
                component_version INTEGER NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL,
                input_json JSONB,
                output_json JSONB,
                error_code TEXT,
                error_message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (session_id, stage_id, attempt)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_analysis_jobs (
                id BIGSERIAL PRIMARY KEY,
                operation_id TEXT NOT NULL UNIQUE,
                session_id INTEGER NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                current_step TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                error_code TEXT,
                error_message TEXT,
                retryable BOOLEAN NOT NULL DEFAULT TRUE,
                worker_id TEXT,
                locked_at TIMESTAMP,
                next_attempt_at TIMESTAMP NOT NULL DEFAULT NOW(),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX idx_assessment_analysis_jobs_active_session
            ON assessment_analysis_jobs(session_id)
            WHERE status IN ('queued', 'running')
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_shadow_evaluation_runs (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL REFERENCES user_sessions(id) ON DELETE CASCADE,
                competency_code TEXT NOT NULL,
                official_agent_code TEXT NOT NULL,
                official_agent_version INTEGER NOT NULL,
                official_agent_checksum TEXT NOT NULL,
                shadow_agent_code TEXT NOT NULL,
                shadow_agent_version INTEGER NOT NULL,
                shadow_agent_checksum TEXT NOT NULL,
                status TEXT NOT NULL,
                official_summary_json JSONB NOT NULL,
                shadow_summary_json JSONB,
                comparison_json JSONB,
                error_code TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP,
                UNIQUE (session_id, competency_code, shadow_agent_code, shadow_agent_version)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO user_sessions (id, session_code, user_id, status, execution_snapshot_json)
            VALUES (501, 'analysis-integration-session', 101, 'active', %s::jsonb)
            """
            ,
            (
                json.dumps(
                    {
                        "methodology": {
                            "code": "competencies_4k",
                            "version": 1,
                            "definition": LEGACY_METHODOLOGY_DEFINITION,
                        },
                        "scenario": {"definition": LEGACY_SCENARIO_DEFINITION},
                        "prompts": {"agent_definitions": frozen_agent_definitions()},
                    },
                    ensure_ascii=False,
                ),
            ),
        )

    @contextmanager
    def test_connection():
        with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
            yield connection

    monkeypatch.setattr(queue_module, "get_connection", test_connection)
    yield test_connection

    with psycopg.connect(test_database_url) as connection:
        connection.execute("DROP TABLE IF EXISTS assessment_shadow_evaluation_runs")
        connection.execute("DROP TABLE IF EXISTS assessment_stage_runs")
        connection.execute("DROP TABLE IF EXISTS assessment_analysis_jobs")
        connection.execute("DROP TABLE IF EXISTS user_sessions")


def enqueue_analysis(queue: AssessmentAnalysisQueue) -> dict:
    return queue.enqueue_retry(session_id=501, user_id=101)


@pytest.mark.integration
def test_analysis_enqueue_is_deduplicated_and_persistent(analysis_database) -> None:
    first_queue = AssessmentAnalysisQueue()
    second_queue = AssessmentAnalysisQueue()

    first = enqueue_analysis(first_queue)
    second = enqueue_analysis(second_queue)
    restored = second_queue.get_status(session_id=501, user_id=101)

    assert first["operation_id"] == second["operation_id"]
    assert restored is not None
    assert restored["status"] == "queued"
    assert restored["session_status"] == "cases_completed"


@pytest.mark.integration
def test_analysis_claim_process_and_report_ready_transition(analysis_database, monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    evaluated: list[tuple[int, int]] = []

    class Agent:
        def __init__(self, agent_code: str):
            self.agent_code = agent_code

        def evaluate_session(self, *, connection, session_id: int, user_id: int):
            evaluated.append((session_id, user_id))
            connection.execute(
                "UPDATE user_sessions SET error_message = COALESCE(error_message, '') WHERE id = %s",
                (session_id,),
            )
            return []

    monkeypatch.setattr(
        queue_module,
        "competency_assessment_agents",
        [Agent(item["code"]) for item in LEGACY_METHODOLOGY_DEFINITION["competencies"]],
    )
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)

    enqueue_analysis(queue)
    claimed = queue._claim_next("analysis-worker")
    assert claimed is not None

    running = queue.get_status(session_id=501, user_id=101)
    assert running is not None
    assert running["status"] == "running"
    assert running["session_status"] == "analyzing"

    queue._process(claimed)
    completed = queue.get_status(session_id=501, user_id=101)

    assert evaluated == [(501, 101)] * 4
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["session_status"] == "completed"
    assert completed["progress_percent"] == 100
    assert completed["current_step"] == "report_ready"
    assert completed["completed_at"] is not None


@pytest.mark.integration
def test_terminal_failure_can_be_retried_without_duplicate_active_job(analysis_database, monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()

    class FailingAgent:
        agent_code = "communication"

        def evaluate_session(self, **_kwargs):
            raise RuntimeError("integration analysis failure")

    monkeypatch.setattr(queue_module.settings, "assessment_queue_max_attempts", 1)
    monkeypatch.setattr(queue_module, "competency_assessment_agents", [FailingAgent()])
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)

    first = enqueue_analysis(queue)
    claimed = queue._claim_next("failing-worker")
    assert claimed is not None
    queue._process(claimed)

    failed = queue.get_status(session_id=501, user_id=101)
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["session_status"] == "failed"
    assert failed["retryable"] is True
    assert "integration analysis failure" in failed["error_message"]

    retried = enqueue_analysis(queue)
    duplicate = enqueue_analysis(queue)
    restored = queue.get_status(session_id=501, user_id=101)

    assert retried["operation_id"] != first["operation_id"]
    assert duplicate["operation_id"] == retried["operation_id"]
    assert restored is not None
    assert restored["status"] == "queued"
    assert restored["session_status"] == "cases_completed"


@pytest.mark.integration
def test_universal_queue_completes_without_legacy_agent(analysis_database, monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    definitions = frozen_agent_definitions()
    communication = definitions["communication"]
    communication["definition"]["runtime"] = {
        "mode": "universal_llm",
        "model_profile": "assessment_strict",
        "temperature": 0,
        "max_attempts": 1,
        "timeout_seconds": 30,
        "max_output_tokens": 1200,
        "fallback": "fail",
    }
    communication["checksum"] = definition_checksum(communication["definition"])
    competency = dict(LEGACY_METHODOLOGY_DEFINITION["competencies"][0])
    competency["skill_codes"] = ["active_listening"]
    snapshot = {
        "methodology": {
            "code": "universal_queue_test",
            "version": 1,
            "definition": {"competencies": [competency]},
        },
        "scenario": {"definition": LEGACY_SCENARIO_DEFINITION},
        "prompts": {"agent_definitions": {"communication": communication}},
    }
    with analysis_database() as connection:
        connection.execute(
            "UPDATE user_sessions SET execution_snapshot_json = %s::jsonb WHERE id = 501",
            (json.dumps(snapshot, ensure_ascii=False),),
        )

    class Provider:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, []

    class Gateway:
        def chat(self, *_args, **_kwargs):
            return json.dumps(
                {
                    "contract_version": 1,
                    "competency_code": "communication",
                    "component_code": "evaluation.communication",
                    "component_version": 1,
                    "status": "no_assessments",
                    "assessments": [],
                    "case_analyses": [],
                }
            )

    monkeypatch.setattr(queue_module, "competency_assessment_agents", [])
    monkeypatch.setattr(queue_module, "UniversalEvaluationMaterialProvider", lambda **_kwargs: Provider())
    monkeypatch.setattr("Api.assessment_competency_executor.DeepSeekGateway", Gateway)
    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", True)
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)

    enqueue_analysis(queue)
    claimed = queue._claim_next("universal-worker")
    assert claimed is not None
    queue._process(claimed)
    completed = queue.get_status(session_id=501, user_id=101)

    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["session_status"] == "completed"


@pytest.mark.integration
@pytest.mark.parametrize("shadow_fails", [False, True])
def test_shadow_result_is_separate_and_never_blocks_official_analysis(
    analysis_database,
    monkeypatch,
    shadow_fails: bool,
) -> None:
    queue = AssessmentAnalysisQueue()
    definitions = frozen_agent_definitions()
    shadow_definition = {
        "schema_version": 1,
        "code": "communication_shadow",
        "version": 1,
        "competency_code": "communication",
        "instruction_markdown": "Synthetic shadow instruction.",
        "input_contract": {"code": "competency_evaluation_input", "version": 1},
        "output_contract": {"code": "competency_evaluation_output", "version": 1},
        "executor": {"code": "evaluation.communication", "version": 1},
        "runtime": {
            "mode": "universal_llm",
            "model_profile": "assessment_strict",
            "temperature": 0,
            "max_attempts": 1,
            "timeout_seconds": 30,
            "max_output_tokens": 1200,
            "fallback": "fail",
        },
    }
    definitions["communication_shadow"] = {
        "id": 99,
        "code": "communication_shadow",
        "name": "Communication shadow",
        "version": 1,
        "checksum": definition_checksum(shadow_definition),
        "definition": shadow_definition,
    }
    competency = dict(LEGACY_METHODOLOGY_DEFINITION["competencies"][0])
    competency["agent_definition"] = {"code": "communication", "version": 1}
    competency["shadow_evaluation"] = {
        "agent_definition": {"code": "communication_shadow", "version": 1},
        "skill_codes": ["active_listening"],
    }
    snapshot = {
        "methodology": {
            "code": "shadow_queue_test",
            "version": 1,
            "definition": {"competencies": [competency]},
        },
        "scenario": {"definition": LEGACY_SCENARIO_DEFINITION},
        "prompts": {"agent_definitions": definitions},
    }
    with analysis_database() as connection:
        connection.execute(
            "UPDATE user_sessions SET execution_snapshot_json = %s::jsonb WHERE id = 501",
            (json.dumps(snapshot, ensure_ascii=False),),
        )

    class OfficialAgent:
        agent_code = "communication"

        def evaluate_session(self, **_kwargs):
            return []

    class Provider:
        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, []

    class Gateway:
        def chat(self, *_args, **_kwargs):
            if shadow_fails:
                raise RuntimeError("synthetic provider failure")
            return json.dumps(
                {
                    "contract_version": 1,
                    "competency_code": "communication",
                    "component_code": "evaluation.communication",
                    "component_version": 1,
                    "status": "no_assessments",
                    "assessments": [],
                    "case_analyses": [],
                }
            )

    monkeypatch.setattr(queue_module, "competency_assessment_agents", [OfficialAgent()])
    monkeypatch.setattr(queue_module, "UniversalEvaluationMaterialProvider", lambda **_kwargs: Provider())
    monkeypatch.setattr("Api.assessment_competency_executor.DeepSeekGateway", Gateway)
    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", True)
    monkeypatch.setattr(settings, "assessment_universal_llm_shadow_enabled", True)
    monkeypatch.setattr(queue, "_run_job_heartbeat", lambda *_args: None)

    enqueue_analysis(queue)
    claimed = queue._claim_next("shadow-worker")
    assert claimed is not None
    queue._process(claimed)

    completed = queue.get_status(session_id=501, user_id=101)
    with analysis_database() as connection:
        shadow_row = connection.execute(
            "SELECT * FROM assessment_shadow_evaluation_runs WHERE session_id = 501"
        ).fetchone()

    assert completed is not None and completed["status"] == "completed"
    assert shadow_row["status"] == ("failed" if shadow_fails else "completed")
    assert shadow_row["error_code"] == ("UniversalCompetencyEvaluationError" if shadow_fails else None)
    assert "rationale" not in str(shadow_row["official_summary_json"])


@pytest.mark.integration
def test_expired_analysis_lease_is_recovered(analysis_database, monkeypatch) -> None:
    queue = AssessmentAnalysisQueue()
    monkeypatch.setattr(queue_module.settings, "assessment_queue_lease_timeout_seconds", 30)
    enqueue_analysis(queue)
    first_claim = queue._claim_next("dead-analysis-worker")
    assert first_claim is not None

    with analysis_database() as connection:
        connection.execute(
            """
            UPDATE assessment_analysis_jobs
            SET locked_at = NOW() - INTERVAL '2 minutes'
            WHERE session_id = 501
            """
        )

    queue._last_maintenance_monotonic = 0
    queue._run_maintenance_if_due()
    replacement_claim = queue._claim_next("replacement-analysis-worker")

    assert replacement_claim is not None
    assert replacement_claim.operation_id == first_claim.operation_id
    assert replacement_claim.worker_id == "replacement-analysis-worker"
