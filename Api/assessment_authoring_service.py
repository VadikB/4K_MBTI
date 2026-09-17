from __future__ import annotations

import json
from typing import Any

from Api.assessment_agent_definitions import load_published_agent_definition_bundle
from Api.assessment_configuration import canonical_json, definition_checksum
from Api.assessment_prompt_resolver import load_active_prompt_bundle
from Api.assessment_runtime import component_registry, validate_scenario_definition
from Api.assessment_evaluator_contracts import validate_agent_runtime


ENTITY_CONFIG = {
    "methodology": {
        "versions": "assessment_methodology_versions",
        "parents": "assessment_methodologies",
        "parent_fk": "methodology_id",
        "edit_permission": "methodology.edit_draft",
        "submit_permission": "methodology.submit",
        "publish_permission": "methodology.publish",
        "view_permission": "methodology.view",
    },
    "scenario": {
        "versions": "assessment_scenario_versions",
        "parents": "assessment_scenarios",
        "parent_fk": "scenario_id",
        "edit_permission": "scenario.edit_draft",
        "submit_permission": "scenario.submit",
        "publish_permission": "scenario.publish",
        "view_permission": "scenario.view",
    },
    "agent": {
        "versions": "assessment_agent_definition_versions",
        "parents": "assessment_agent_definitions",
        "parent_fk": "agent_definition_id",
        "edit_permission": "agent.edit_draft",
        "submit_permission": "agent.submit",
        "publish_permission": "agent.publish",
        "view_permission": "agent.view",
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

    def create_definition(
        self,
        connection,
        *,
        entity_type: str,
        code: str,
        name: str,
        description: str | None,
        definition: dict[str, Any],
        actor_user_id: int,
        comment: str | None,
    ) -> dict[str, Any]:
        config = self._config(entity_type)
        normalized_code = str(code or "").strip()
        normalized_name = str(name or "").strip()
        if not normalized_code or not normalized_name:
            raise ValueError("Assessment definition code and name are required.")
        if connection.execute(
            f"SELECT id FROM {config['parents']} WHERE code = %s",
            (normalized_code,),
        ).fetchone() is not None:
            raise ValueError("Assessment definition code already exists.")
        normalized = dict(definition or {})
        normalized["code"] = normalized_code
        normalized["version"] = 1
        self.validate_definition(entity_type=entity_type, definition=normalized)
        parent = connection.execute(
            f"""
            INSERT INTO {config['parents']} (code, name, description)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (normalized_code, normalized_name, str(description or "").strip() or None),
        ).fetchone()
        created = connection.execute(
            f"""
            INSERT INTO {config['versions']} (
                {config['parent_fk']}, version, status, description, definition_json, checksum
            )
            VALUES (%s, 1, 'draft', %s, %s::jsonb, %s)
            RETURNING *
            """,
            (
                int(parent["id"]),
                str(description or "").strip() or None,
                canonical_json(normalized),
                definition_checksum(normalized),
            ),
        ).fetchone()
        self._audit(
            connection,
            entity_type=entity_type,
            entity_id=int(created["id"]),
            action="definition_created",
            actor_user_id=actor_user_id,
            before=None,
            after=dict(created),
            comment=comment,
        )
        return {**dict(created), "code": normalized_code, "name": normalized_name}

    def list_configurations(self, connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT id, code, name, methodology_version_id, scenario_version_id,
                   status, is_default, prompt_bundle_checksum, created_at, published_at
            FROM assessment_configurations
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def create_configuration(
        self,
        connection,
        *,
        code: str,
        name: str,
        methodology_version_id: int,
        scenario_version_id: int,
        actor_user_id: int,
        comment: str | None,
    ) -> dict[str, Any]:
        normalized_code = str(code or "").strip()
        normalized_name = str(name or "").strip()
        if not normalized_code or not normalized_name:
            raise ValueError("Assessment configuration code and name are required.")
        if connection.execute(
            "SELECT id FROM assessment_configurations WHERE code = %s",
            (normalized_code,),
        ).fetchone() is not None:
            raise ValueError("Assessment configuration code already exists.")
        versions = connection.execute(
            """
            SELECT methodology_version.status AS methodology_status,
                   scenario_version.status AS scenario_status
            FROM assessment_methodology_versions methodology_version
            CROSS JOIN assessment_scenario_versions scenario_version
            WHERE methodology_version.id = %s AND scenario_version.id = %s
            """,
            (methodology_version_id, scenario_version_id),
        ).fetchone()
        if versions is None:
            raise ValueError("Methodology or scenario version was not found.")
        if versions["methodology_status"] != "published" or versions["scenario_status"] != "published":
            raise ValueError("Assessment configuration requires published methodology and scenario versions.")
        created = connection.execute(
            """
            INSERT INTO assessment_configurations (
                code, name, methodology_version_id, scenario_version_id,
                status, is_default
            )
            VALUES (%s, %s, %s, %s, 'draft', %s)
            RETURNING *
            """,
            (normalized_code, normalized_name, methodology_version_id, scenario_version_id, False),
        ).fetchone()
        self._audit(
            connection,
            entity_type="configuration",
            entity_id=int(created["id"]),
            action="configuration_created",
            actor_user_id=actor_user_id,
            before=None,
            after=dict(created),
            comment=comment,
        )
        return dict(created)

    def publish_configuration(
        self,
        connection,
        *,
        configuration_id: int,
        make_default: bool,
        actor_user_id: int,
        comment: str | None,
    ) -> dict[str, Any]:
        current = connection.execute(
            """
            SELECT configuration.*,
                   methodology_version.status AS methodology_status,
                   methodology_version.definition_json AS methodology_definition,
                   scenario_version.status AS scenario_status
            FROM assessment_configurations configuration
            JOIN assessment_methodology_versions methodology_version
              ON methodology_version.id = configuration.methodology_version_id
            JOIN assessment_scenario_versions scenario_version
              ON scenario_version.id = configuration.scenario_version_id
            WHERE configuration.id = %s
            FOR UPDATE OF configuration
            """,
            (configuration_id,),
        ).fetchone()
        if current is None:
            raise ValueError("Assessment configuration was not found.")
        if current["status"] != "draft":
            raise ValueError("Only draft assessment configurations can be published.")
        if current["methodology_status"] != "published" or current["scenario_status"] != "published":
            raise ValueError("Configuration components must remain published.")
        prompt_bundle = load_active_prompt_bundle(connection)
        agent_definitions = load_published_agent_definition_bundle(
            connection,
            methodology_definition=dict(current["methodology_definition"] or {}),
        )
        self._validate_evaluator_prompt_bundle(
            methodology_definition=dict(current["methodology_definition"] or {}),
            prompt_bundle=prompt_bundle,
            agent_definitions=agent_definitions,
        )
        prompt_bundle["agent_definitions"] = agent_definitions
        if make_default:
            connection.execute("UPDATE assessment_configurations SET is_default = FALSE WHERE id <> %s", (configuration_id,))
        updated = connection.execute(
            """
            UPDATE assessment_configurations
            SET status = 'published', published_at = NOW(), is_default = %s,
                prompt_bundle_json = %s::jsonb, prompt_bundle_checksum = %s
            WHERE id = %s
            RETURNING *
            """,
            (bool(make_default), canonical_json(prompt_bundle), definition_checksum(prompt_bundle), configuration_id),
        ).fetchone()
        self._audit(
            connection,
            entity_type="configuration",
            entity_id=configuration_id,
            action="configuration_published",
            actor_user_id=actor_user_id,
            before=dict(current),
            after=dict(updated),
            comment=comment,
        )
        return dict(updated)

    def _validate_evaluator_prompt_bundle(
        self,
        *,
        methodology_definition: dict[str, Any],
        prompt_bundle: dict[str, Any],
        agent_definitions: dict[str, Any] | None = None,
    ) -> None:
        assessment_agents = prompt_bundle.get("assessment_agents")
        assessment_agents = assessment_agents if isinstance(assessment_agents, dict) else {}

        missing: list[str] = []
        invalid: list[str] = []
        schema_version = int(methodology_definition.get("schema_version") or 1)
        for competency in methodology_definition.get("competencies") or []:
            evaluator_code = str((competency or {}).get("evaluator") or "").strip()
            agent_code = evaluator_code.removeprefix("evaluation.")
            reference = (competency or {}).get("agent_definition")
            reference = dict(reference) if isinstance(reference, dict) else {}
            definition_code = str(reference.get("code") or agent_code).strip()
            frozen_definition = dict((agent_definitions or {}).get(definition_code) or {})
            definition_payload = dict(frozen_definition.get("definition") or {})
            runtime = dict(definition_payload.get("runtime") or {})
            if schema_version >= 2:
                input_contract = dict(definition_payload.get("input_contract") or {})
                output_contract = dict(definition_payload.get("output_contract") or {})
                executor = dict(definition_payload.get("executor") or {})
                if runtime.get("mode") != "universal_llm":
                    raise ValueError("Indicator methodology requires universal_llm agent definitions.")
                if (input_contract.get("code"), int(input_contract.get("version") or 0)) != (
                    "competency_evaluation_input", 2,
                ) or (output_contract.get("code"), int(output_contract.get("version") or 0)) != (
                    "competency_evaluation_output", 2,
                ):
                    raise ValueError("Indicator methodology requires evaluator contracts version 2.")
                if (executor.get("code"), int(executor.get("version") or 0)) != (evaluator_code, 2):
                    raise ValueError("Indicator methodology requires an evaluator executor version 2.")
                continue
            shadow = (competency or {}).get("shadow_evaluation")
            if isinstance(shadow, dict):
                shadow_reference = dict(shadow.get("agent_definition") or {})
                shadow_code = str(shadow_reference.get("code") or "").strip()
                shadow_frozen = dict((agent_definitions or {}).get(shadow_code) or {})
                shadow_runtime = dict((shadow_frozen.get("definition") or {}).get("runtime") or {})
                if runtime.get("mode") != "legacy_adapter":
                    raise ValueError("Shadow comparison requires an official legacy_adapter evaluator.")
                if shadow_runtime.get("mode") != "universal_llm":
                    raise ValueError("Shadow comparison requires a universal_llm shadow agent.")
                shadow_skill_codes = shadow.get("skill_codes")
                if not isinstance(shadow_skill_codes, list) or not {
                    str(code).strip() for code in shadow_skill_codes if str(code).strip()
                }:
                    raise ValueError("Shadow evaluation must define skill_codes.")
            if runtime.get("mode") == "universal_llm":
                skill_codes = (competency or {}).get("skill_codes")
                if not isinstance(skill_codes, list) or not {
                    str(code).strip() for code in skill_codes if str(code).strip()
                }:
                    raise ValueError(
                        f"Universal evaluator competency {competency.get('code')} must define skill_codes."
                    )
                continue
            config = assessment_agents.get(agent_code)
            if not isinstance(config, dict):
                missing.append(agent_code)
                continue
            profile = config.get("profile")
            if not isinstance(profile, dict):
                invalid.append(agent_code)
                continue
            profile_agent_code = str(profile.get("agent_code") or "").strip()
            prompt_version = int(profile.get("prompt_version") or 0)
            if profile_agent_code != agent_code or prompt_version < 1:
                invalid.append(agent_code)

        if missing:
            raise ValueError(
                "Assessment prompt bundle is missing evaluator profiles: " + ", ".join(sorted(missing)) + "."
            )
        if invalid:
            raise ValueError(
                "Assessment prompt bundle contains invalid evaluator profiles: " + ", ".join(sorted(invalid)) + "."
            )

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
        if entity_type == "scenario":
            validate_scenario_definition(definition)
            return
        if entity_type == "agent":
            self._validate_agent_definition(definition)
            return
        competencies = definition.get("competencies")
        if not isinstance(competencies, list) or not competencies:
            raise ValueError("Assessment methodology must define competencies.")
        schema_version = int(definition.get("schema_version") or 1)
        if schema_version >= 2 or "roles" in definition or "levels" in definition:
            self._validate_methodology_dimensions(definition)
        if schema_version >= 2:
            self._validate_indicator_hierarchy(definition)
        seen: set[str] = set()
        for competency in competencies:
            if not isinstance(competency, dict):
                raise ValueError("Every competency must be an object.")
            code = str(competency.get("code") or competency.get("id") or "").strip()
            evaluator = str(competency.get("evaluator") or "").strip()
            version = int(competency.get("evaluator_version") or 0)
            if not code or code in seen:
                raise ValueError("Competency codes must be present and unique.")
            component_registry.resolve(evaluator, version)
            agent_reference = competency.get("agent_definition")
            if agent_reference is not None:
                if not isinstance(agent_reference, dict):
                    raise ValueError("Competency agent_definition must be an object.")
                definition_code = str(agent_reference.get("code") or "").strip()
                definition_version = int(agent_reference.get("version") or 0)
                if not definition_code or definition_version < 1:
                    raise ValueError("Competency agent_definition must declare code and positive version.")
            shadow = competency.get("shadow_evaluation")
            if shadow is not None:
                if not isinstance(shadow, dict):
                    raise ValueError("Competency shadow_evaluation must be an object.")
                shadow_reference = shadow.get("agent_definition")
                if not isinstance(shadow_reference, dict):
                    raise ValueError("Shadow evaluation must declare agent_definition.")
                shadow_code = str(shadow_reference.get("code") or "").strip()
                shadow_version = int(shadow_reference.get("version") or 0)
                if not shadow_code or shadow_version < 1:
                    raise ValueError("Shadow agent_definition must declare code and positive version.")
                official_definition_code = (
                    str(agent_reference.get("code") or "").strip()
                    if isinstance(agent_reference, dict)
                    else evaluator.removeprefix("evaluation.")
                )
                if shadow_code == official_definition_code:
                    raise ValueError("Official and shadow agent definitions must use different codes.")
                shadow_skill_codes = shadow.get("skill_codes")
                if not isinstance(shadow_skill_codes, list) or not {
                    str(item).strip() for item in shadow_skill_codes if str(item).strip()
                }:
                    raise ValueError("Shadow evaluation must define skill_codes.")
            seen.add(code)

    def _validate_indicator_hierarchy(self, definition: dict[str, Any]) -> None:
        if [str(item.get("code") or "") for item in definition.get("levels") or []] != ["L0", "L1", "L2", "L3"]:
            raise ValueError("Indicator methodology levels must be exactly L0-L3.")
        seen: set[str] = set()
        for competency in definition.get("competencies") or []:
            competency_id = str(competency.get("id") or "").strip()
            if not competency_id:
                raise ValueError("Indicator methodology competency must define id.")
            self._remember_methodology_id(competency_id, seen)
            for skill in competency.get("skills") or []:
                skill_id = str(skill.get("id") or "").strip()
                if not skill_id.startswith(f"{competency_id}."):
                    raise ValueError(f"Skill {skill_id} has an invalid competency parent.")
                self._remember_methodology_id(skill_id, seen)
                for component in skill.get("components") or []:
                    component_id = str(component.get("id") or "").strip()
                    if not component_id.startswith(f"{competency_id}.C"):
                        raise ValueError(f"Component {component_id} has an invalid competency parent.")
                    self._remember_methodology_id(component_id, seen)
                    for indicator in component.get("indicators") or []:
                        indicator_id = str(indicator.get("id") or "").strip()
                        if not indicator_id.startswith(f"{competency_id}.I"):
                            raise ValueError(f"Indicator {indicator_id} has an invalid competency parent.")
                        self._remember_methodology_id(indicator_id, seen)
                        rubric = indicator.get("levels")
                        if not isinstance(rubric, dict) or set(rubric) != {"L0", "L1", "L2", "L3"} or not all(
                            str(rubric[level] or "").strip() for level in ("L0", "L1", "L2", "L3")
                        ):
                            raise ValueError(f"Indicator {indicator_id} must define non-empty L0-L3.")
                        if not str(indicator.get("evidence_pattern") or "").strip():
                            raise ValueError(f"Indicator {indicator_id} must define evidence_pattern.")

    @staticmethod
    def _remember_methodology_id(value: str, seen: set[str]) -> None:
        if not value or value in seen:
            raise ValueError("Indicator methodology IDs must be present and globally unique.")
        seen.add(value)

    def _validate_methodology_dimensions(self, definition: dict[str, Any]) -> None:
        schema_version = int(definition.get("schema_version") or 1)
        fields = ("levels",) if schema_version >= 2 else ("roles", "levels")
        for field in fields:
            items = definition.get(field)
            if not isinstance(items, list) or not items:
                raise ValueError(f"Assessment methodology must define {field}.")
            seen: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(f"Every methodology {field} item must be an object.")
                code = str(item.get("code") or "").strip()
                name = str(item.get("name") or "").strip()
                label = name or (str(item.get("meaning") or "").strip() if schema_version >= 2 else "")
                if not code or not label or code in seen:
                    raise ValueError(f"Methodology {field} codes must be present and unique; names are required.")
                if field == "roles" and not str(item.get("description") or "").strip():
                    raise ValueError("Every methodology role must define description.")
                if field == "levels" and int(item.get("order") if item.get("order") is not None else -1) < 0:
                    raise ValueError("Every methodology level must define a non-negative order.")
                seen.add(code)

    def _validate_agent_definition(self, definition: dict[str, Any]) -> None:
        competency_code = str(definition.get("competency_code") or "").strip()
        instruction_markdown = str(definition.get("instruction_markdown") or "").strip()
        if not competency_code:
            raise ValueError("Agent definition must declare competency_code.")
        if not instruction_markdown:
            raise ValueError("Agent definition must contain instruction_markdown.")
        for field, expected_code in (
            ("input_contract", "competency_evaluation_input"),
            ("output_contract", "competency_evaluation_output"),
        ):
            reference = definition.get(field)
            if not isinstance(reference, dict):
                raise ValueError(f"Agent definition must declare {field}.")
            code = str(reference.get("code") or "").strip()
            version = int(reference.get("version") or 0)
            if code != expected_code or version < 1:
                raise ValueError(f"Unsupported agent {field}: {code} v{version}.")
        executor = definition.get("executor")
        if not isinstance(executor, dict):
            raise ValueError("Agent definition must declare executor.")
        component_registry.resolve(
            str(executor.get("code") or "").strip(),
            int(executor.get("version") or 0),
        )
        runtime = definition.get("runtime")
        if not isinstance(runtime, dict):
            raise ValueError("Agent definition runtime must be an object.")
        validate_agent_runtime(runtime)

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
