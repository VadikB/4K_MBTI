from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import dict_row

from Api.assessment_authoring_service import assessment_authoring_service
from Api.assessment_configuration import (
    LEGACY_METHODOLOGY_DEFINITION,
    LEGACY_SCENARIO_DEFINITION,
    load_default_execution_configuration,
)


@pytest.fixture
def authoring_connection(test_database_url):
    with psycopg.connect(test_database_url, row_factory=dict_row) as connection:
        for table in (
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

    execution = load_default_execution_configuration(connection)
    assert execution["snapshot"]["methodology"]["code"] == "flexible_4k"
    assert execution["snapshot"]["scenario"]["code"] == "adaptive_interview"
    assert execution["snapshot"]["configuration"]["code"] == "flexible_4k_default"
    assert execution["checksum"]

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
