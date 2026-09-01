from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.assessment_agent_definitions import ensure_legacy_agent_definitions
from Api.assessment_competency_executor import CompetencyEvaluatorExecutor
from Api.assessment_authoring_service import assessment_authoring_service
from Api.assessment_configuration import (
    LEGACY_METHODOLOGY_DEFINITION,
    LEGACY_SCENARIO_DEFINITION,
    canonical_json,
    definition_checksum,
    ensure_legacy_assessment_configuration,
    load_default_execution_configuration,
)
from Api.assessment_evaluator_contracts import competency_evaluation_input_builder
from Api.config import settings


@pytest.fixture
def authoring_connection(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        for table in (
            "assessment_agent_prompt_rules",
            "assessment_agent_prompt_profiles",
            "assessment_agent_definition_versions",
            "assessment_agent_definitions",
            "assessment_definition_audit_log",
            "assessment_configurations",
            "assessment_scenario_versions",
            "assessment_scenarios",
            "assessment_methodology_versions",
            "assessment_methodologies",
        ):
            connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        connection.execute("CREATE TABLE assessment_methodologies (id BIGSERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT)")
        connection.execute("CREATE TABLE assessment_scenarios (id BIGSERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT)")
        connection.execute("CREATE TABLE assessment_agent_definitions (id BIGSERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT)")
        connection.execute(
            """
            CREATE TABLE assessment_agent_definition_versions (
                id BIGSERIAL PRIMARY KEY,
                agent_definition_id BIGINT NOT NULL REFERENCES assessment_agent_definitions(id),
                version INTEGER NOT NULL, status TEXT NOT NULL, description TEXT,
                definition_json JSONB NOT NULL, checksum TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(), published_at TIMESTAMP,
                UNIQUE (agent_definition_id, version)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_methodology_versions (
                id BIGSERIAL PRIMARY KEY, methodology_id BIGINT NOT NULL REFERENCES assessment_methodologies(id),
                version INTEGER NOT NULL, status TEXT NOT NULL, description TEXT, definition_json JSONB NOT NULL,
                checksum TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT NOW(), published_at TIMESTAMP,
                UNIQUE (methodology_id, version)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_scenario_versions (
                id BIGSERIAL PRIMARY KEY, scenario_id BIGINT NOT NULL REFERENCES assessment_scenarios(id),
                version INTEGER NOT NULL, status TEXT NOT NULL, description TEXT, definition_json JSONB NOT NULL,
                checksum TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT NOW(), published_at TIMESTAMP,
                UNIQUE (scenario_id, version)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_configurations (
                id BIGSERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                methodology_version_id BIGINT NOT NULL REFERENCES assessment_methodology_versions(id),
                scenario_version_id BIGINT NOT NULL REFERENCES assessment_scenario_versions(id),
                prompt_bundle_json JSONB, prompt_bundle_checksum TEXT, status TEXT NOT NULL,
                is_default BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMP NOT NULL DEFAULT NOW(), published_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_definition_audit_log (
                id BIGSERIAL PRIMARY KEY, entity_type TEXT NOT NULL, entity_id BIGINT NOT NULL,
                action TEXT NOT NULL, actor_user_id INTEGER, before_json JSONB, after_json JSONB,
                comment TEXT, created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_agent_prompt_profiles (
                agent_code TEXT PRIMARY KEY, agent_name TEXT NOT NULL, competency_name TEXT NOT NULL,
                purpose_prompt TEXT NOT NULL, rationale_prompt TEXT NOT NULL,
                evidence_prompt TEXT NOT NULL, red_flag_prompt TEXT NOT NULL,
                prompt_version INTEGER NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE assessment_agent_prompt_rules (
                id BIGSERIAL PRIMARY KEY,
                agent_code TEXT NOT NULL REFERENCES assessment_agent_prompt_profiles(agent_code),
                rule_code TEXT NOT NULL, rule_scope TEXT NOT NULL, rule_text TEXT NOT NULL,
                display_order INTEGER NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
            """
        )
        connection.execute(
            """
            INSERT INTO assessment_agent_prompt_profiles (
                agent_code, agent_name, competency_name, purpose_prompt,
                rationale_prompt, evidence_prompt, red_flag_prompt, prompt_version
            ) VALUES
                ('communication', 'Communication', 'Коммуникация', 'purpose', 'rationale', 'evidence', 'red flags', 1),
                ('teamwork', 'Teamwork', 'Командность', 'purpose', 'rationale', 'evidence', 'red flags', 1),
                ('creativity', 'Creativity', 'Креативность', 'purpose', 'rationale', 'evidence', 'red flags', 1),
                ('critical_thinking', 'Critical Thinking', 'Критическое мышление', 'purpose', 'rationale', 'evidence', 'red flags', 1)
            """
        )
        for agent_code, agent_name in (
            ("communication", "Communication"),
            ("teamwork", "Teamwork"),
            ("creativity", "Creativity"),
            ("critical_thinking", "Critical Thinking"),
        ):
            parent = connection.execute(
                "INSERT INTO assessment_agent_definitions (code, name) VALUES (%s, %s) RETURNING id",
                (agent_code, agent_name),
            ).fetchone()
            definition = {
                "schema_version": 1,
                "code": agent_code,
                "version": 1,
                "competency_code": agent_code,
                "instruction_markdown": f"# {agent_name}\n\nLegacy evaluator instruction.",
                "input_contract": {"code": "competency_evaluation_input", "version": 1},
                "output_contract": {"code": "competency_evaluation_output", "version": 1},
                "executor": {"code": f"evaluation.{agent_code}", "version": 1},
                "runtime": {"mode": "legacy_adapter"},
            }
            connection.execute(
                """
                INSERT INTO assessment_agent_definition_versions (
                    agent_definition_id, version, status, definition_json, checksum, published_at
                ) VALUES (%s, 1, 'published', %s::jsonb, %s, NOW())
                """,
                (int(parent["id"]), canonical_json(definition), definition_checksum(definition)),
            )
        yield connection


@pytest.mark.integration
def test_new_methodology_and_scenario_can_be_published_as_default_configuration(authoring_connection) -> None:
    connection = authoring_connection
    methodology = assessment_authoring_service.create_definition(
        connection,
        entity_type="methodology",
        code="flexible_4k",
        name="Гибкая методология 4K",
        description="Created entirely through authoring API semantics.",
        definition=LEGACY_METHODOLOGY_DEFINITION,
        actor_user_id=101,
        comment="create methodology",
    )
    scenario = assessment_authoring_service.create_definition(
        connection,
        entity_type="scenario",
        code="adaptive_interview",
        name="Адаптивное интервью",
        description="Created entirely through authoring API semantics.",
        definition=LEGACY_SCENARIO_DEFINITION,
        actor_user_id=101,
        comment="create scenario",
    )

    for entity_type, version_id in (("methodology", methodology["id"]), ("scenario", scenario["id"])):
        assessment_authoring_service.submit_for_review(
            connection,
            entity_type=entity_type,
            version_id=version_id,
            actor_user_id=101,
            comment="review",
        )
        published = assessment_authoring_service.publish(
            connection,
            entity_type=entity_type,
            version_id=version_id,
            actor_user_id=202,
            comment="publish",
        )
        assert published["status"] == "published"

    configuration = assessment_authoring_service.create_configuration(
        connection,
        code="flexible_4k_default",
        name="Гибкая конфигурация 4K",
        methodology_version_id=methodology["id"],
        scenario_version_id=scenario["id"],
        actor_user_id=202,
        comment="bind published definitions",
    )
    published_configuration = assessment_authoring_service.publish_configuration(
        connection,
        configuration_id=configuration["id"],
        make_default=True,
        actor_user_id=202,
        comment="publish configuration",
    )

    assert published_configuration["status"] == "published"
    assert published_configuration["prompt_bundle_json"] is not None
    assert published_configuration["prompt_bundle_checksum"]
    assert set(published_configuration["prompt_bundle_json"]["agent_definitions"]) == {
        "communication",
        "teamwork",
        "creativity",
        "critical_thinking",
    }

    execution = load_default_execution_configuration(connection)
    assert execution["snapshot"]["methodology"]["code"] == "flexible_4k"
    assert execution["snapshot"]["scenario"]["code"] == "adaptive_interview"
    assert execution["snapshot"]["configuration"]["code"] == "flexible_4k_default"
    assert execution["snapshot"]["prompts"]["agent_definitions"]["communication"]["version"] == 1
    assert execution["checksum"]

    communication_v1 = connection.execute(
        """
        SELECT version_row.id
        FROM assessment_agent_definition_versions version_row
        JOIN assessment_agent_definitions parent ON parent.id = version_row.agent_definition_id
        WHERE parent.code = 'communication' AND version_row.version = 1
        """
    ).fetchone()
    communication_v2 = assessment_authoring_service.clone_version(
        connection,
        entity_type="agent",
        source_version_id=int(communication_v1["id"]),
        actor_user_id=101,
        description="Agent v2 draft",
    )
    updated_definition = dict(communication_v2["definition_json"])
    updated_definition["instruction_markdown"] += "\n\n## Version 2\nAdditional evidence rule."
    assessment_authoring_service.update_draft(
        connection,
        entity_type="agent",
        version_id=int(communication_v2["id"]),
        definition=updated_definition,
        description="Agent v2 draft",
        actor_user_id=101,
        comment="update agent draft",
    )
    assessment_authoring_service.submit_for_review(
        connection,
        entity_type="agent",
        version_id=int(communication_v2["id"]),
        actor_user_id=101,
        comment="review agent",
    )
    assessment_authoring_service.publish(
        connection,
        entity_type="agent",
        version_id=int(communication_v2["id"]),
        actor_user_id=202,
        comment="publish agent",
    )

    frozen_after_agent_publish = load_default_execution_configuration(connection)
    assert frozen_after_agent_publish["snapshot"]["prompts"]["agent_definitions"]["communication"]["version"] == 1

    actions = {
        row["action"]
        for row in connection.execute("SELECT action FROM assessment_definition_audit_log").fetchall()
    }
    assert {
        "definition_created",
        "submitted_for_review",
        "published",
        "configuration_created",
        "configuration_published",
    }.issubset(actions)


@pytest.mark.integration
def test_published_execution_snapshot_is_unchanged_by_a_new_draft(authoring_connection) -> None:
    connection = authoring_connection
    methodology = assessment_authoring_service.create_definition(
        connection,
        entity_type="methodology",
        code="immutable_4k",
        name="Immutable 4K",
        description="Published baseline methodology.",
        definition=LEGACY_METHODOLOGY_DEFINITION,
        actor_user_id=101,
        comment="create",
    )
    scenario = assessment_authoring_service.create_definition(
        connection,
        entity_type="scenario",
        code="immutable_interview",
        name="Immutable interview",
        description="Published baseline scenario.",
        definition=LEGACY_SCENARIO_DEFINITION,
        actor_user_id=101,
        comment="create",
    )
    for entity_type, version_id in (("methodology", methodology["id"]), ("scenario", scenario["id"])):
        assessment_authoring_service.submit_for_review(
            connection,
            entity_type=entity_type,
            version_id=version_id,
            actor_user_id=101,
            comment="review",
        )
        assessment_authoring_service.publish(
            connection,
            entity_type=entity_type,
            version_id=version_id,
            actor_user_id=202,
            comment="publish",
        )
    configuration = assessment_authoring_service.create_configuration(
        connection,
        code="immutable_default",
        name="Immutable default",
        methodology_version_id=methodology["id"],
        scenario_version_id=scenario["id"],
        actor_user_id=202,
        comment="bind",
    )
    assessment_authoring_service.publish_configuration(
        connection,
        configuration_id=configuration["id"],
        make_default=True,
        actor_user_id=202,
        comment="publish",
    )
    before = load_default_execution_configuration(connection)

    draft = assessment_authoring_service.clone_version(
        connection,
        entity_type="methodology",
        source_version_id=methodology["id"],
        actor_user_id=101,
        description="Unpublished revision.",
    )
    changed_definition = dict(draft["definition_json"])
    changed_definition["aggregation"] = {
        "component": "evaluation.aggregate",
        "component_version": 1,
        "draft_marker": True,
    }
    assessment_authoring_service.update_draft(
        connection,
        entity_type="methodology",
        version_id=draft["id"],
        definition=changed_definition,
        description="Unpublished revision.",
        actor_user_id=101,
        comment="edit draft",
    )

    after = load_default_execution_configuration(connection)
    assert after == before
    assert after["snapshot"]["methodology"]["version"] == 1
    assert "draft_marker" not in after["snapshot"]["methodology"]["definition"]["aggregation"]


@pytest.mark.integration
def test_active_legacy_profiles_bootstrap_immutable_agent_definitions(authoring_connection) -> None:
    connection = authoring_connection
    connection.execute("DELETE FROM assessment_agent_definition_versions")
    connection.execute("DELETE FROM assessment_agent_definitions")

    assert ensure_legacy_agent_definitions(connection) == 4
    assert ensure_legacy_agent_definitions(connection) == 0

    rows = connection.execute(
        """
        SELECT parent.code, version_row.version, version_row.status,
               version_row.definition_json, version_row.checksum
        FROM assessment_agent_definition_versions version_row
        JOIN assessment_agent_definitions parent ON parent.id = version_row.agent_definition_id
        ORDER BY parent.code
        """
    ).fetchall()
    assert len(rows) == 4
    assert {row["status"] for row in rows} == {"published"}
    assert all(row["definition_json"]["instruction_markdown"] for row in rows)
    assert all(row["checksum"] for row in rows)
    ensure_legacy_assessment_configuration(connection)


@pytest.mark.integration
def test_agent_v2_is_frozen_and_executed_from_published_configuration(authoring_connection, monkeypatch) -> None:
    connection = authoring_connection
    communication_v1 = connection.execute(
        """
        SELECT version_row.id
        FROM assessment_agent_definition_versions version_row
        JOIN assessment_agent_definitions parent ON parent.id = version_row.agent_definition_id
        WHERE parent.code = 'communication' AND version_row.version = 1
        """
    ).fetchone()
    communication_v2 = assessment_authoring_service.clone_version(
        connection,
        entity_type="agent",
        source_version_id=int(communication_v1["id"]),
        actor_user_id=101,
        description="Smoke-test agent v2.",
    )
    definition_v2 = dict(communication_v2["definition_json"])
    definition_v2["instruction_markdown"] = "# Communication v2\n\nSMOKE_AGENT_V2_MARKER"
    definition_v2["runtime"] = {
        "mode": "universal_llm",
        "model_profile": "assessment_strict",
        "temperature": 0,
        "max_attempts": 1,
        "timeout_seconds": 30,
        "max_output_tokens": 1200,
        "fallback": "fail",
    }
    assessment_authoring_service.update_draft(
        connection,
        entity_type="agent",
        version_id=int(communication_v2["id"]),
        definition=definition_v2,
        description="Smoke-test agent v2.",
        actor_user_id=101,
        comment="Set unique frozen instruction.",
    )
    assessment_authoring_service.submit_for_review(
        connection,
        entity_type="agent",
        version_id=int(communication_v2["id"]),
        actor_user_id=101,
        comment="Review smoke definition.",
    )
    assessment_authoring_service.publish(
        connection,
        entity_type="agent",
        version_id=int(communication_v2["id"]),
        actor_user_id=202,
        comment="Publish smoke definition.",
    )

    methodology_definition = dict(LEGACY_METHODOLOGY_DEFINITION)
    methodology_definition["competencies"] = [dict(item) for item in LEGACY_METHODOLOGY_DEFINITION["competencies"]]
    methodology_definition["competencies"][0]["agent_definition"] = {
        "code": "communication",
        "version": 2,
    }
    methodology_definition["competencies"][0]["skill_codes"] = ["active_listening"]
    methodology = assessment_authoring_service.create_definition(
        connection,
        entity_type="methodology",
        code="agent_v2_smoke",
        name="Agent v2 smoke methodology",
        description="Explicit agent-version smoke test.",
        definition=methodology_definition,
        actor_user_id=101,
        comment="Create smoke methodology.",
    )
    scenario = assessment_authoring_service.create_definition(
        connection,
        entity_type="scenario",
        code="agent_v2_smoke_scenario",
        name="Agent v2 smoke scenario",
        description="Smoke scenario.",
        definition=LEGACY_SCENARIO_DEFINITION,
        actor_user_id=101,
        comment="Create smoke scenario.",
    )
    for entity_type, version_id in (("methodology", methodology["id"]), ("scenario", scenario["id"])):
        assessment_authoring_service.submit_for_review(
            connection,
            entity_type=entity_type,
            version_id=int(version_id),
            actor_user_id=101,
            comment="Review smoke definition.",
        )
        assessment_authoring_service.publish(
            connection,
            entity_type=entity_type,
            version_id=int(version_id),
            actor_user_id=202,
            comment="Publish smoke definition.",
        )
    configuration = assessment_authoring_service.create_configuration(
        connection,
        code="agent_v2_smoke_configuration",
        name="Agent v2 smoke configuration",
        methodology_version_id=int(methodology["id"]),
        scenario_version_id=int(scenario["id"]),
        actor_user_id=202,
        comment="Bind smoke definitions.",
    )
    assessment_authoring_service.publish_configuration(
        connection,
        configuration_id=int(configuration["id"]),
        make_default=True,
        actor_user_id=202,
        comment="Publish smoke configuration.",
    )
    snapshot = load_default_execution_configuration(connection)["snapshot"]
    frozen = snapshot["prompts"]["agent_definitions"]["communication"]
    assert frozen["version"] == 2
    assert frozen["checksum"] == definition_checksum(frozen["definition"])

    class MaterialProvider:
        agent_code = "communication"

        def load_evaluation_materials(self, **_kwargs):
            return {"profile": {}, "rules": []}, []

    class FakeGateway:
        def chat(self, messages, *, temperature, timeout_seconds, max_tokens=None, routing_key=None):
            self.messages = messages
            return canonical_json(
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

    strategy = MaterialProvider()
    gateway = FakeGateway()
    competency = snapshot["methodology"]["definition"]["competencies"][0]
    input_data = competency_evaluation_input_builder.build(
        snapshot=snapshot,
        session_id=501,
        user_id=101,
        competency=competency,
        connection=connection,
        agent=strategy,
    )
    monkeypatch.setattr(settings, "assessment_universal_llm_enabled", True)
    output = CompetencyEvaluatorExecutor([strategy], llm_gateway=gateway).execute(
        connection=connection,
        input_data=input_data,
    )

    assert input_data.agent_definition.version == 2
    assert "SMOKE_AGENT_V2_MARKER" in input_data.agent_definition.instruction_markdown
    assert "SMOKE_AGENT_V2_MARKER" in gateway.messages[0]["content"]
    assert output.component_code == "evaluation.communication"
    assert output.status == "no_assessments"


@pytest.mark.integration
def test_configuration_freezes_distinct_shadow_agent_definition(authoring_connection) -> None:
    connection = authoring_connection
    shadow_definition = {
        "schema_version": 1,
        "competency_code": "communication",
        "instruction_markdown": "# Communication universal shadow",
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
    shadow = assessment_authoring_service.create_definition(
        connection,
        entity_type="agent",
        code="communication_shadow",
        name="Communication shadow",
        description="Synthetic universal shadow.",
        definition=shadow_definition,
        actor_user_id=101,
        comment="Create shadow.",
    )
    assessment_authoring_service.submit_for_review(
        connection, entity_type="agent", version_id=shadow["id"], actor_user_id=101, comment="Review."
    )
    assessment_authoring_service.publish(
        connection, entity_type="agent", version_id=shadow["id"], actor_user_id=202, comment="Publish."
    )
    methodology_definition = dict(LEGACY_METHODOLOGY_DEFINITION)
    methodology_definition["competencies"] = [dict(LEGACY_METHODOLOGY_DEFINITION["competencies"][0])]
    methodology_definition["competencies"][0]["agent_definition"] = {"code": "communication", "version": 1}
    methodology_definition["competencies"][0]["shadow_evaluation"] = {
        "agent_definition": {"code": "communication_shadow", "version": 1},
        "skill_codes": ["active_listening"],
    }
    methodology = assessment_authoring_service.create_definition(
        connection,
        entity_type="methodology",
        code="shadow_methodology",
        name="Shadow methodology",
        description="Synthetic shadow methodology.",
        definition=methodology_definition,
        actor_user_id=101,
        comment="Create.",
    )
    scenario = assessment_authoring_service.create_definition(
        connection,
        entity_type="scenario",
        code="shadow_scenario",
        name="Shadow scenario",
        description="Synthetic shadow scenario.",
        definition=LEGACY_SCENARIO_DEFINITION,
        actor_user_id=101,
        comment="Create.",
    )
    for entity_type, version_id in (("methodology", methodology["id"]), ("scenario", scenario["id"])):
        assessment_authoring_service.submit_for_review(
            connection, entity_type=entity_type, version_id=version_id, actor_user_id=101, comment="Review."
        )
        assessment_authoring_service.publish(
            connection, entity_type=entity_type, version_id=version_id, actor_user_id=202, comment="Publish."
        )
    configuration = assessment_authoring_service.create_configuration(
        connection,
        code="shadow_configuration",
        name="Shadow configuration",
        methodology_version_id=methodology["id"],
        scenario_version_id=scenario["id"],
        actor_user_id=202,
        comment="Bind.",
    )
    published = assessment_authoring_service.publish_configuration(
        connection,
        configuration_id=configuration["id"],
        make_default=False,
        actor_user_id=202,
        comment="Publish.",
    )

    bundle = published["prompt_bundle_json"]["agent_definitions"]
    assert bundle["communication"]["version"] == 1
    assert bundle["communication_shadow"]["version"] == 1
    assert bundle["communication_shadow"]["checksum"] == definition_checksum(
        bundle["communication_shadow"]["definition"]
    )
