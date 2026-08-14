from __future__ import annotations

import json
from typing import Any

from Api.assessment_configuration import canonical_json, definition_checksum
from Api.assessment_runtime import component_registry, validate_scenario_definition


ENTITY_CONFIG = {
    "methodology": {
        "versions": "assessment_methodology_versions",
        "parents": "assessment_methodologies",
        "parent_fk": "methodology_id",
        "edit_permission": "methodology.edit_draft",
        "submit_permission": "methodology.submit",
        "publish_permission": "methodology.publish",
    },
    "scenario": {
        "versions": "assessment_scenario_versions",
        "parents": "assessment_scenarios",
        "parent_fk": "scenario_id",
        "edit_permission": "scenario.edit_draft",
        "submit_permission": "scenario.submit",
        "publish_permission": "scenario.publish",
    },
}


class AssessmentAuthoringService:
    def _config(self, entity_type: str) -> dict[str, str]:
        try:
            return ENTITY_CONFIG[entity_type]
        except KeyError as exc:
            raise ValueError("Unsupported assessment definition type.") from exc

    def list_versions(self, connection, *, entity_type: str) -> list[dict[str, Any]]:
        config = self._config(entity_type)
        rows = connection.execute(
            f"""
            SELECT version_row.id, parent.code, parent.name, version_row.version,
                   version_row.status, version_row.description, version_row.definition_json,
                   version_row.checksum, version_row.created_at, version_row.published_at
            FROM {config['versions']} version_row
            JOIN {config['parents']} parent ON parent.id = version_row.{config['parent_fk']}
            ORDER BY parent.code ASC, version_row.version DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def clone_version(
        self,
        connection,
        *,
        entity_type: str,
        source_version_id: int,
        actor_user_id: int,
        description: str | None,
    ) -> dict[str, Any]:
        config = self._config(entity_type)
        source = connection.execute(
            f"""
            SELECT id, {config['parent_fk']} AS parent_id, definition_json, version
            FROM {config['versions']}
            WHERE id = %s
            FOR UPDATE
            """,
            (source_version_id,),
        ).fetchone()
        if source is None:
            raise ValueError("Source assessment definition version was not found.")
        next_row = connection.execute(
            f"SELECT COALESCE(MAX(version), 0) + 1 AS version FROM {config['versions']} WHERE {config['parent_fk']} = %s",
            (source["parent_id"],),
        ).fetchone()
        definition = dict(source["definition_json"] or {})
        definition["version"] = int(next_row["version"])
        created = connection.execute(
            f"""
            INSERT INTO {config['versions']} (
                {config['parent_fk']}, version, status, description, definition_json, checksum
            )
            VALUES (%s, %s, 'draft', %s, %s::jsonb, %s)
            RETURNING *
            """,
            (
                source["parent_id"],
                int(next_row["version"]),
                str(description or "").strip() or f"Draft cloned from version {source['version']}",
                canonical_json(definition),
                definition_checksum(definition),
            ),
        ).fetchone()
        self._audit(
            connection,
            entity_type=entity_type,
            entity_id=int(created["id"]),
            action="draft_created",
            actor_user_id=actor_user_id,
            before=None,
            after=dict(created),
            comment=description,
        )
        return dict(created)

    def update_draft(
        self,
        connection,
        *,
        entity_type: str,
        version_id: int,
        definition: dict[str, Any],
        description: str | None,
        actor_user_id: int,
        comment: str | None,
    ) -> dict[str, Any]:
        config = self._config(entity_type)
        current = connection.execute(
            f"SELECT * FROM {config['versions']} WHERE id = %s FOR UPDATE",
            (version_id,),
        ).fetchone()
        if current is None:
            raise ValueError("Assessment definition version was not found.")
        if current["status"] != "draft":
            raise ValueError("Only draft assessment definitions can be edited.")
        normalized = dict(definition or {})
        normalized["version"] = int(current["version"])
        updated = connection.execute(
            f"""
            UPDATE {config['versions']}
            SET definition_json = %s::jsonb, checksum = %s, description = %s
            WHERE id = %s
            RETURNING *
            """,
            (
                canonical_json(normalized),
                definition_checksum(normalized),
                str(description or "").strip() or current["description"],
                version_id,
            ),
        ).fetchone()
        self._audit(
            connection,
            entity_type=entity_type,
            entity_id=version_id,
            action="draft_updated",
            actor_user_id=actor_user_id,
            before=dict(current),
            after=dict(updated),
            comment=comment,
        )
        return dict(updated)

    def submit_for_review(self, connection, *, entity_type: str, version_id: int, actor_user_id: int, comment: str | None) -> dict[str, Any]:
        config = self._config(entity_type)
        current = connection.execute(
            f"SELECT * FROM {config['versions']} WHERE id = %s FOR UPDATE",
            (version_id,),
        ).fetchone()
        if current is None:
            raise ValueError("Assessment definition version was not found.")
        if current["status"] != "draft":
            raise ValueError("Only draft assessment definitions can be submitted.")
        self.validate_definition(entity_type=entity_type, definition=dict(current["definition_json"] or {}))
        updated = connection.execute(
            f"UPDATE {config['versions']} SET status = 'ready_for_review' WHERE id = %s RETURNING *",
            (version_id,),
        ).fetchone()
        self._audit(connection, entity_type=entity_type, entity_id=version_id, action="submitted_for_review", actor_user_id=actor_user_id, before=dict(current), after=dict(updated), comment=comment)
        return dict(updated)

    def validate_version(self, connection, *, entity_type: str, version_id: int) -> dict[str, Any]:
        config = self._config(entity_type)
        current = connection.execute(
            f"SELECT id, status, definition_json, checksum FROM {config['versions']} WHERE id = %s",
            (version_id,),
        ).fetchone()
        if current is None:
            raise ValueError("Assessment definition version was not found.")
        definition = dict(current["definition_json"] or {})
        self.validate_definition(entity_type=entity_type, definition=definition)
        expected_checksum = definition_checksum(definition)
        if str(current["checksum"]) != expected_checksum:
            raise ValueError("Assessment definition checksum does not match its content.")
        return {"ok": True, "version_id": int(current["id"]), "status": str(current["status"]), "checksum": expected_checksum}

    def publish(self, connection, *, entity_type: str, version_id: int, actor_user_id: int, comment: str | None) -> dict[str, Any]:
        config = self._config(entity_type)
        current = connection.execute(
            f"SELECT * FROM {config['versions']} WHERE id = %s FOR UPDATE",
            (version_id,),
        ).fetchone()
        if current is None:
            raise ValueError("Assessment definition version was not found.")
        if current["status"] != "ready_for_review":
            raise ValueError("Only reviewed assessment definitions can be published.")
        self.validate_definition(entity_type=entity_type, definition=dict(current["definition_json"] or {}))
        updated = connection.execute(
            f"UPDATE {config['versions']} SET status = 'published', published_at = NOW() WHERE id = %s RETURNING *",
            (version_id,),
        ).fetchone()
        self._audit(connection, entity_type=entity_type, entity_id=version_id, action="published", actor_user_id=actor_user_id, before=dict(current), after=dict(updated), comment=comment)
        return dict(updated)

    def validate_definition(self, *, entity_type: str, definition: dict[str, Any]) -> None:
        self._config(entity_type)
        if "mbti" in json.dumps(definition, ensure_ascii=False).lower():
            raise ValueError("MBTI is not allowed in the 4K assessment definition.")
        if entity_type == "scenario":
            validate_scenario_definition(definition)
            return
        competencies = definition.get("competencies")
        if not isinstance(competencies, list) or not competencies:
            raise ValueError("Assessment methodology must define competencies.")
        seen: set[str] = set()
        for competency in competencies:
            if not isinstance(competency, dict):
                raise ValueError("Every competency must be an object.")
            code = str(competency.get("code") or "").strip()
            evaluator = str(competency.get("evaluator") or "").strip()
            version = int(competency.get("evaluator_version") or 0)
            if not code or code in seen:
                raise ValueError("Competency codes must be present and unique.")
            component_registry.resolve(evaluator, version)
            seen.add(code)

    def _audit(self, connection, *, entity_type: str, entity_id: int, action: str, actor_user_id: int, before: dict[str, Any] | None, after: dict[str, Any] | None, comment: str | None) -> None:
        connection.execute(
            """
            INSERT INTO assessment_definition_audit_log (
                entity_type, entity_id, action, actor_user_id, before_json, after_json, comment
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (
                entity_type,
                entity_id,
                action,
                actor_user_id,
                canonical_json(before) if before is not None else None,
                canonical_json(after) if after is not None else None,
                str(comment or "").strip() or None,
            ),
        )


assessment_authoring_service = AssessmentAuthoringService()
