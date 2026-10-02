from __future__ import annotations

import hashlib
import json
from typing import Any

from Api.assessment_runtime import validate_scenario_definition
from Api.snapshot_integrity import execution_snapshot_integrity


LEGACY_METHODOLOGY_CODE = "competencies_4k"
LEGACY_SCENARIO_CODE = "standard_4k_interview"
LEGACY_CONFIGURATION_CODE = "4k_standard_v1"

LEGACY_ROLES: list[dict[str, Any]] = [
    {
        "code": "linear_employee",
        "name": "Линейный сотрудник",
        "description": "Выполняет конкретные задачи по правилам, инструкциям или стандартным процессам.",
    },
    {
        "code": "manager",
        "name": "Менеджер",
        "description": "Координирует людей, задачи, сроки и приоритеты для достижения результата.",
    },
    {
        "code": "leader",
        "name": "Лидер",
        "description": "Задаёт направление, ведёт изменения и принимает решения с долгосрочными последствиями.",
    },
]

LEGACY_LEVELS: list[dict[str, Any]] = [
    {"code": "L1", "name": "Базовый", "order": 1},
    {"code": "L2", "name": "Уверенный", "order": 2},
    {"code": "L3", "name": "Продвинутый", "order": 3},
]

LEGACY_METHODOLOGY_DEFINITION: dict[str, Any] = {
    "schema_version": 1,
    "code": LEGACY_METHODOLOGY_CODE,
    "version": 1,
    "methodology_version": "1.0",
    "roles": LEGACY_ROLES,
    "levels": LEGACY_LEVELS,
    "competencies": [
        {"code": "communication", "evaluator": "evaluation.communication", "evaluator_version": 1},
        {"code": "teamwork", "evaluator": "evaluation.teamwork", "evaluator_version": 1},
        {"code": "creativity", "evaluator": "evaluation.creativity", "evaluator_version": 1},
        {"code": "critical_thinking", "evaluator": "evaluation.critical_thinking", "evaluator_version": 1},
    ],
    "aggregation": {"component": "evaluation.aggregate", "component_version": 1},
}


def ensure_methodology_role_projection(connection, definition: dict[str, Any]) -> None:
    """Materialize versioned roles for legacy tables that still reference numeric role IDs."""
    for role in definition.get("roles") or []:
        connection.execute(
            """
            INSERT INTO roles (code, name, short_definition, mission, personalization_variables)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO NOTHING
            """,
            (
                role["code"],
                role["name"],
                role["description"],
                role["description"],
                "position, duties, company_industry",
            ),
        )


def load_default_methodology_roles(connection) -> list[dict[str, Any]]:
    row = connection.execute(
        """
        SELECT methodology.code, methodology_version.version, methodology_version.definition_json
        FROM assessment_configurations configuration
        JOIN assessment_methodology_versions methodology_version
          ON methodology_version.id = configuration.methodology_version_id
        JOIN assessment_methodologies methodology
          ON methodology.id = methodology_version.methodology_id
        WHERE configuration.is_default = TRUE
          AND configuration.status = 'published'
          AND methodology_version.status = 'published'
        ORDER BY configuration.id ASC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return []
    definition = dict(row["definition_json"] or {})
    from Api.assessment_authoring_service import assessment_authoring_service

    assessment_authoring_service.validate_execution_methodology(definition)
    roles = definition.get("roles") or []
    return [dict(role) for role in roles if isinstance(role, dict)]

LEGACY_SCENARIO_DEFINITION: dict[str, Any] = {
    "schema_version": 1,
    "code": LEGACY_SCENARIO_CODE,
    "version": 1,
    "initial_stage": "prepare_profile",
    "stages": [
        {"id": "prepare_profile", "component": "profile.prepare", "component_version": 1, "on_success": "select_cases"},
        {"id": "select_cases", "component": "cases.select", "component_version": 1, "on_success": "personalize_cases"},
        {"id": "personalize_cases", "component": "cases.personalize", "component_version": 1, "execution": "parallel", "on_success": "interview"},
        {"id": "interview", "component": "interview.case_dialog", "component_version": 1, "on_success": "evaluate_competencies"},
        {"id": "evaluate_competencies", "component": "evaluation.run_methodology_evaluators", "component_version": 1, "execution": "parallel", "on_success": "aggregate"},
        {"id": "aggregate", "component": "evaluation.aggregate", "component_version": 1, "on_success": "build_report"},
        {"id": "build_report", "component": "report.build", "component_version": 1, "on_success": "complete_session"},
    ],
}


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def definition_checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def ensure_legacy_assessment_configuration(connection) -> None:
    ensure_methodology_role_projection(connection, LEGACY_METHODOLOGY_DEFINITION)
    methodology = connection.execute(
        """
        INSERT INTO assessment_methodologies (code, name, description)
        VALUES (%s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (LEGACY_METHODOLOGY_CODE, "Оценка компетенций 4K", "Базовая оценка четырех компетенций."),
    ).fetchone()
    methodology_id = int(methodology["id"])
    methodology_version = connection.execute(
        """
        INSERT INTO assessment_methodology_versions (
            methodology_id, version, status, description, definition_json, checksum, published_at
        )
        VALUES (%s, 1, 'published', %s, %s::jsonb, %s, NOW())
        ON CONFLICT (methodology_id, version) DO UPDATE SET methodology_id = EXCLUDED.methodology_id
        RETURNING id
        """,
        (
            methodology_id,
            "Legacy-фиксация текущей методологии 4K.",
            canonical_json(LEGACY_METHODOLOGY_DEFINITION),
            definition_checksum(LEGACY_METHODOLOGY_DEFINITION),
        ),
    ).fetchone()

    scenario = connection.execute(
        """
        INSERT INTO assessment_scenarios (code, name, description)
        VALUES (%s, %s, %s)
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (LEGACY_SCENARIO_CODE, "Стандартное кейсовое интервью 4K", "Текущий линейный процесс assessment."),
    ).fetchone()
    scenario_id = int(scenario["id"])
    scenario_version = connection.execute(
        """
        INSERT INTO assessment_scenario_versions (
            scenario_id, version, status, description, definition_json, checksum, published_at
        )
        VALUES (%s, 1, 'published', %s, %s::jsonb, %s, NOW())
        ON CONFLICT (scenario_id, version) DO UPDATE SET scenario_id = EXCLUDED.scenario_id
        RETURNING id
        """,
        (
            scenario_id,
            "Legacy-сценарий текущего assessment.",
            canonical_json(LEGACY_SCENARIO_DEFINITION),
            definition_checksum(LEGACY_SCENARIO_DEFINITION),
        ),
    ).fetchone()

    connection.execute(
        """
        INSERT INTO assessment_configurations (
            code, name, methodology_version_id, scenario_version_id, status, is_default
        )
        VALUES (%s, %s, %s, %s, 'published', TRUE)
        ON CONFLICT (code) DO UPDATE SET
            methodology_version_id = EXCLUDED.methodology_version_id,
            scenario_version_id = EXCLUDED.scenario_version_id
        """,
        (
            LEGACY_CONFIGURATION_CODE,
            "Стандартная оценка 4K",
            int(methodology_version["id"]),
            int(scenario_version["id"]),
        ),
    )


def load_default_execution_configuration(connection) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            configuration.id AS configuration_id,
            configuration.code AS configuration_code,
            configuration.prompt_bundle_json,
            configuration.prompt_bundle_checksum,
            methodology_version.id AS methodology_version_id,
            methodology.code AS methodology_code,
            methodology_version.version AS methodology_version,
            methodology_version.definition_json AS methodology_definition,
            scenario_version.id AS scenario_version_id,
            scenario.code AS scenario_code,
            scenario_version.version AS scenario_version,
            scenario_version.definition_json AS scenario_definition
        FROM assessment_configurations configuration
        JOIN assessment_methodology_versions methodology_version
          ON methodology_version.id = configuration.methodology_version_id
        JOIN assessment_methodologies methodology
          ON methodology.id = methodology_version.methodology_id
        JOIN assessment_scenario_versions scenario_version
          ON scenario_version.id = configuration.scenario_version_id
        JOIN assessment_scenarios scenario
          ON scenario.id = scenario_version.scenario_id
        WHERE configuration.is_default = TRUE
          AND configuration.status = 'published'
          AND methodology_version.status = 'published'
          AND scenario_version.status = 'published'
        ORDER BY configuration.id ASC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        raise RuntimeError("Published default assessment configuration is not available.")

    validate_scenario_definition(row["scenario_definition"])
    prompt_bundle = row.get("prompt_bundle_json")
    if not isinstance(prompt_bundle, dict):
        raise ValueError("Published assessment configuration requires a prompt bundle.")
    if row.get("prompt_bundle_checksum") != definition_checksum(prompt_bundle):
        raise ValueError("Published assessment prompt bundle checksum mismatch.")
    methodology_definition = dict(row["methodology_definition"] or {})
    # Import lazily: authoring uses the canonical checksum helpers in this module.
    from Api.assessment_authoring_service import assessment_authoring_service

    assessment_authoring_service.validate_execution_bundle(
        methodology_definition=methodology_definition, prompt_bundle=prompt_bundle,
    )

    snapshot = {
        "schema_version": 1,
        "_integrity": execution_snapshot_integrity(),
        "configuration": {"id": int(row["configuration_id"]), "code": str(row["configuration_code"])},
        "methodology": {
            "id": int(row["methodology_version_id"]),
            "code": str(row["methodology_code"]),
            "version": int(row["methodology_version"]),
            "definition": methodology_definition,
        },
        "scenario": {
            "id": int(row["scenario_version_id"]),
            "code": str(row["scenario_code"]),
            "version": int(row["scenario_version"]),
            "definition": row["scenario_definition"],
        },
        "prompts": prompt_bundle,
    }
    return {
        "configuration_id": int(row["configuration_id"]),
        "methodology_version_id": int(row["methodology_version_id"]),
        "scenario_version_id": int(row["scenario_version_id"]),
        "snapshot": snapshot,
        "checksum": definition_checksum(snapshot),
    }
