"""Controlled publication of the reviewed M2 1.1 package for M4/M5 QA."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from Api.assessment_agent_definitions import load_agent_definition_file
from Api.assessment_authoring_service import assessment_authoring_service
from Api.assessment_configuration import definition_checksum
from scripts.build_methodology_1_1_package import validate_package


PACKAGE_DIR = (
    Path(__file__).resolve().parents[1]
    / "assessment_definitions"
    / "methodologies"
    / "competencies_4k"
    / "1.1"
)
CONFIGURATION_CODE = "4k_m5_qa_v1_1"
SCENARIO_CODE = "standard_4k_interview"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"M2 artifact must contain a JSON object: {path.name}.")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified_m2_package(package_dir: Path = PACKAGE_DIR) -> dict[str, Any]:
    """Load M2 only after all manifest-controlled artifacts have been verified."""
    manifest = _read_json(package_dir / "manifest.json")
    methodology = _read_json(package_dir / "methodology.json")
    normative_control = _read_json(package_dir / "normative-control.json")
    if manifest.get("methodology_code") != "competencies_4k" or manifest.get("methodology_version") != "1.1":
        raise ValueError("M2 manifest must identify competencies_4k methodology 1.1.")
    if manifest.get("status") != "draft" or methodology.get("status") != "draft":
        raise ValueError("Only the reviewed M2 1.1 draft package can enter publication lifecycle.")
    artifact = manifest.get("artifact") or {}
    if artifact != {"name": "methodology.json", "sha256": _sha256(package_dir / "methodology.json")}:
        raise ValueError("M2 methodology checksum does not match its manifest.")
    for group in ("agent_artifacts", "control_artifacts"):
        for item in manifest.get(group) or []:
            name = str(item.get("name") or "")
            path = (package_dir / name) if name != "methodology-package-v2.schema.json" else (
                package_dir.parents[2] / "schemas" / name
            )
            if not name or not path.is_file() or item.get("sha256") != _sha256(path):
                raise ValueError(f"M2 controlled artifact checksum mismatch: {name or group}.")
    transformation = manifest.get("transformation_validation") or {}
    transformation_path = package_dir / str(transformation.get("name") or "")
    if transformation.get("status") != "PASS" or not transformation_path.is_file() or (
        transformation.get("sha256") != _sha256(transformation_path)
    ):
        raise ValueError("M2 transformation validation is absent or differs from the manifest.")
    validate_package(methodology, normative_control=normative_control)
    agents = [
        load_agent_definition_file(package_dir / str(item["name"]))
        for item in manifest["agent_artifacts"]
        if str(item["name"]).endswith(".json")
    ]
    return {"manifest": manifest, "methodology": methodology, "agents": agents}


def _ensure_agent(connection, *, definition: dict[str, Any], actor_user_id: int, decision_basis: str) -> dict[str, Any]:
    code = str(definition["code"])
    version = int(definition["version"])
    expected = dict(definition)
    expected["code"] = code
    expected["version"] = version
    checksum = definition_checksum(expected)
    row = connection.execute(
        """
        SELECT version_row.*
        FROM assessment_agent_definitions parent
        JOIN assessment_agent_definition_versions version_row
          ON version_row.agent_definition_id = parent.id
        WHERE parent.code = %s AND version_row.version = %s
        FOR UPDATE OF version_row
        """,
        (code, version),
    ).fetchone()
    if row is None:
        row = assessment_authoring_service.create_definition(
            connection,
            entity_type="agent",
            code=code,
            name=f"M2 1.1 evaluator {definition['competency_code']}",
            description="Versioned evaluator from the reviewed M2 1.1 package.",
            definition=expected,
            actor_user_id=actor_user_id,
            comment=decision_basis,
        )
    elif str(row["checksum"]) != checksum:
        raise ValueError(f"Existing agent definition {code} v{version} differs from the M2 package.")
    if row["status"] == "draft":
        row = assessment_authoring_service.submit_for_review(
            connection, entity_type="agent", version_id=int(row["id"]),
            actor_user_id=actor_user_id, comment=decision_basis,
        )
    if row["status"] == "ready_for_review":
        row = assessment_authoring_service.publish(
            connection, entity_type="agent", version_id=int(row["id"]),
            actor_user_id=actor_user_id, comment=decision_basis,
        )
    if row["status"] != "published":
        raise ValueError(f"Agent definition {code} v{version} cannot be used for M2 publication.")
    return dict(row)


def _ensure_methodology(connection, *, definition: dict[str, Any], actor_user_id: int, decision_basis: str) -> dict[str, Any]:
    existing = connection.execute(
        """
        SELECT version_row.*
        FROM assessment_methodologies parent
        JOIN assessment_methodology_versions version_row ON version_row.methodology_id = parent.id
        WHERE parent.code = 'competencies_4k'
          AND version_row.definition_json->>'methodology_version' = '1.1'
        ORDER BY version_row.version DESC
        LIMIT 1
        FOR UPDATE OF version_row
        """
    ).fetchone()
    if existing is None:
        source = connection.execute(
            """
            SELECT version_row.id
            FROM assessment_methodologies parent
            JOIN assessment_methodology_versions version_row ON version_row.methodology_id = parent.id
            WHERE parent.code = 'competencies_4k'
            ORDER BY version_row.version DESC LIMIT 1
            """
        ).fetchone()
        if source is None:
            row = assessment_authoring_service.create_definition(
                connection, entity_type="methodology", code="competencies_4k",
                name="Методология 4К", description="M2 methodology 1.1.",
                definition=definition, actor_user_id=actor_user_id, comment=decision_basis,
            )
        else:
            row = assessment_authoring_service.clone_version(
                connection, entity_type="methodology", source_version_id=int(source["id"]),
                actor_user_id=actor_user_id, description="M2 methodology 1.1.",
            )
            row = assessment_authoring_service.update_draft(
                connection, entity_type="methodology", version_id=int(row["id"]),
                definition=definition, description="M2 methodology 1.1.",
                actor_user_id=actor_user_id, comment=decision_basis,
            )
    else:
        row = dict(existing)
        expected = dict(definition)
        expected["version"] = int(row["version"])
        if str(row["checksum"]) != definition_checksum(expected):
            raise ValueError("Existing competencies_4k methodology 1.1 differs from the reviewed package.")
    if row["status"] == "draft":
        row = assessment_authoring_service.submit_for_review(
            connection, entity_type="methodology", version_id=int(row["id"]),
            actor_user_id=actor_user_id, comment=decision_basis,
        )
    if row["status"] == "ready_for_review":
        row = assessment_authoring_service.publish(
            connection, entity_type="methodology", version_id=int(row["id"]),
            actor_user_id=actor_user_id, comment=decision_basis,
        )
    if row["status"] != "published":
        raise ValueError("M2 methodology 1.1 cannot be used for QA configuration.")
    return dict(row)


def publish_m2_qa_configuration(
    connection,
    *,
    published_by_user_id: int,
    decision_basis: str,
    package_dir: Path = PACKAGE_DIR,
) -> dict[str, Any]:
    """Publish exact M2 1.1 content and a non-default QA configuration."""
    if not str(decision_basis or "").strip():
        raise ValueError("M2 publication decision basis is required.")
    package = load_verified_m2_package(package_dir)
    agent_rows = [
        _ensure_agent(
            connection, definition=definition, actor_user_id=published_by_user_id,
            decision_basis=decision_basis,
        )
        for definition in package["agents"]
    ]
    methodology = _ensure_methodology(
        connection, definition=package["methodology"], actor_user_id=published_by_user_id,
        decision_basis=decision_basis,
    )
    scenario = connection.execute(
        """
        SELECT version_row.id
        FROM assessment_scenarios parent
        JOIN assessment_scenario_versions version_row ON version_row.scenario_id = parent.id
        WHERE parent.code = %s AND version_row.status = 'published'
        ORDER BY version_row.version DESC LIMIT 1
        """,
        (SCENARIO_CODE,),
    ).fetchone()
    if scenario is None:
        raise ValueError("Published standard_4k_interview scenario is required.")
    configuration = connection.execute(
        "SELECT * FROM assessment_configurations WHERE code = %s FOR UPDATE",
        (CONFIGURATION_CODE,),
    ).fetchone()
    if configuration is None:
        configuration = assessment_authoring_service.create_configuration(
            connection, code=CONFIGURATION_CODE, name="M4/M5 QA — M2 1.1",
            methodology_version_id=int(methodology["id"]), scenario_version_id=int(scenario["id"]),
            actor_user_id=published_by_user_id, comment=decision_basis,
        )
    elif (
        int(configuration["methodology_version_id"]) != int(methodology["id"])
        or int(configuration["scenario_version_id"]) != int(scenario["id"])
    ):
        raise ValueError("Existing M4/M5 QA configuration points to different frozen versions.")
    if configuration["status"] == "draft":
        configuration = assessment_authoring_service.publish_configuration(
            connection, configuration_id=int(configuration["id"]), make_default=False,
            actor_user_id=published_by_user_id, comment=decision_basis,
        )
    if configuration["status"] != "published" or bool(configuration["is_default"]):
        raise ValueError("M4/M5 QA configuration must be published and non-default.")
    source_checksum = str(package["manifest"]["artifact"]["sha256"])
    publication = connection.execute(
        """
        INSERT INTO assessment_methodology_publications (
            methodology_code, methodology_version, source_artifact_checksum,
            source_manifest_json, methodology_version_id, agent_version_ids_json,
            configuration_id, published_by_user_id, decision_basis
        ) VALUES ('competencies_4k', '1.1', %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s)
        ON CONFLICT (methodology_code, methodology_version, source_artifact_checksum) DO NOTHING
        RETURNING id
        """,
        (
            source_checksum,
            json.dumps(package["manifest"], ensure_ascii=False),
            int(methodology["id"]),
            json.dumps([int(row["id"]) for row in agent_rows]),
            int(configuration["id"]),
            published_by_user_id,
            decision_basis.strip(),
        ),
    ).fetchone()
    idempotent = publication is None
    if publication is None:
        publication = connection.execute(
            """
            SELECT id,methodology_version_id,agent_version_ids_json,configuration_id
            FROM assessment_methodology_publications
            WHERE methodology_code='competencies_4k' AND methodology_version='1.1'
              AND source_artifact_checksum=%s
            """,
            (source_checksum,),
        ).fetchone()
        expected_agent_ids = [int(row["id"]) for row in agent_rows]
        if (
            publication is None
            or int(publication["methodology_version_id"]) != int(methodology["id"])
            or list(publication["agent_version_ids_json"]) != expected_agent_ids
            or int(publication["configuration_id"]) != int(configuration["id"])
        ):
            raise ValueError("Existing M2 publication audit differs from the resolved frozen versions.")
    return {
        "publication_id": int(publication["id"]),
        "idempotent": idempotent,
        "methodology_version_id": int(methodology["id"]),
        "methodology_checksum": str(methodology["checksum"]),
        "agent_version_ids": [int(row["id"]) for row in agent_rows],
        "scenario_version_id": int(scenario["id"]),
        "configuration_id": int(configuration["id"]),
        "configuration_code": CONFIGURATION_CODE,
        "is_default": False,
        "source_artifact_checksum": source_checksum,
    }
