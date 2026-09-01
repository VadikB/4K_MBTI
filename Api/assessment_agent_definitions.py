from __future__ import annotations

from typing import Any

from Api.assessment_configuration import canonical_json, definition_checksum


def ensure_legacy_agent_definitions(connection) -> int:
    """Bootstrap immutable v1 definitions from existing active prompt profiles."""

    created_count = 0
    profiles = connection.execute(
        """
        SELECT agent_code, agent_name, competency_name, purpose_prompt,
               rationale_prompt, evidence_prompt, red_flag_prompt, prompt_version
        FROM assessment_agent_prompt_profiles
        WHERE is_active = TRUE
        ORDER BY agent_code
        """
    ).fetchall()
    for profile in profiles:
        agent_code = str(profile["agent_code"])
        rules = connection.execute(
            """
            SELECT rule_code, rule_scope, rule_text, display_order
            FROM assessment_agent_prompt_rules
            WHERE agent_code = %s AND is_active = TRUE
            ORDER BY display_order, id
            """,
            (agent_code,),
        ).fetchall()
        instruction_sections = [
            f"# {profile['agent_name']}",
            str(profile["purpose_prompt"] or "").strip(),
            "## Обоснование оценки",
            str(profile["rationale_prompt"] or "").strip(),
            "## Evidence rules",
            str(profile["evidence_prompt"] or "").strip(),
            "## Red flags",
            str(profile["red_flag_prompt"] or "").strip(),
        ]
        if rules:
            instruction_sections.extend(
                [
                    "## Дополнительные правила",
                    "\n".join(f"- {str(rule['rule_text']).strip()}" for rule in rules),
                ]
            )
        definition = {
            "schema_version": 1,
            "code": agent_code,
            "version": 1,
            "competency_code": agent_code,
            "instruction_markdown": "\n\n".join(section for section in instruction_sections if section),
            "input_contract": {"code": "competency_evaluation_input", "version": 1},
            "output_contract": {"code": "competency_evaluation_output", "version": 1},
            "executor": {"code": f"evaluation.{agent_code}", "version": 1},
            "runtime": {"mode": "legacy_adapter"},
            "legacy_prompt_version": int(profile["prompt_version"]),
        }
        parent = connection.execute(
            """
            INSERT INTO assessment_agent_definitions (code, name, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET code = EXCLUDED.code
            RETURNING id
            """,
            (
                agent_code,
                str(profile["agent_name"]),
                f"Bootstrap definition for {profile['competency_name']}.",
            ),
        ).fetchone()
        inserted = connection.execute(
            """
            INSERT INTO assessment_agent_definition_versions (
                agent_definition_id, version, status, description,
                definition_json, checksum, published_at
            )
            VALUES (%s, 1, 'published', %s, %s::jsonb, %s, NOW())
            ON CONFLICT (agent_definition_id, version) DO NOTHING
            RETURNING id
            """,
            (
                int(parent["id"]),
                "Bootstrap from active evaluator prompt profile.",
                canonical_json(definition),
                definition_checksum(definition),
            ),
        ).fetchone()
        if inserted is not None:
            created_count += 1
    return created_count


def load_published_agent_definition_bundle(
    connection,
    *,
    methodology_definition: dict[str, Any],
) -> dict[str, Any]:
    bundle: dict[str, Any] = {}

    def load_reference(*, reference: dict[str, Any], evaluator_code: str, evaluator_version: int) -> None:
        definition_code = str(reference.get("code") or evaluator_code.removeprefix("evaluation.")).strip()
        definition_version = int(reference.get("version") or 0)
        existing = bundle.get(definition_code)
        if existing is not None:
            if definition_version and int(existing["version"]) != definition_version:
                raise ValueError(f"Agent definition bundle cannot contain two versions of {definition_code}.")
            return
        params: list[Any] = [definition_code]
        version_filter = ""
        if definition_version > 0:
            version_filter = "AND version_row.version = %s"
            params.append(definition_version)
        row = connection.execute(
            f"""
            SELECT version_row.id, parent.code, parent.name, version_row.version,
                   version_row.definition_json, version_row.checksum
            FROM assessment_agent_definition_versions version_row
            JOIN assessment_agent_definitions parent ON parent.id = version_row.agent_definition_id
            WHERE parent.code = %s
              AND version_row.status = 'published'
              {version_filter}
            ORDER BY version_row.version DESC
            LIMIT 1
            """,
            tuple(params),
        ).fetchone()
        if row is None:
            requested = f"{definition_code} v{definition_version}" if definition_version else definition_code
            raise ValueError(f"Published agent definition is not available: {requested}.")
        definition = dict(row["definition_json"] or {})
        executor = dict(definition.get("executor") or {})
        if (str(executor.get("code") or ""), int(executor.get("version") or 0)) != (
            evaluator_code,
            evaluator_version,
        ):
            raise ValueError(
                f"Agent definition {definition_code} executor does not match {evaluator_code} v{evaluator_version}."
            )
        bundle[definition_code] = {
            "id": int(row["id"]),
            "code": str(row["code"]),
            "name": str(row["name"]),
            "version": int(row["version"]),
            "checksum": str(row["checksum"]),
            "definition": definition,
        }

    for competency in methodology_definition.get("competencies") or []:
        evaluator_code = str((competency or {}).get("evaluator") or "").strip()
        evaluator_version = int((competency or {}).get("evaluator_version") or 0)
        reference = (competency or {}).get("agent_definition")
        reference = dict(reference) if isinstance(reference, dict) else {}
        load_reference(reference=reference, evaluator_code=evaluator_code, evaluator_version=evaluator_version)
        shadow = (competency or {}).get("shadow_evaluation")
        if isinstance(shadow, dict):
            shadow_reference = shadow.get("agent_definition")
            if not isinstance(shadow_reference, dict):
                raise ValueError("Shadow evaluation must declare agent_definition.")
            load_reference(
                reference=shadow_reference,
                evaluator_code=evaluator_code,
                evaluator_version=evaluator_version,
            )
    return bundle
