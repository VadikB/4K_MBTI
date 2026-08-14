from __future__ import annotations

from typing import Any


def load_active_prompt_bundle(connection) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "schema_version": 1,
        "interviewer": {},
        "assessment_agents": {},
        "case_generation_instructions": [],
    }
    try:
        interviewer_rows = connection.execute(
            """
            SELECT prompt_code, prompt_name, prompt_text, prompt_version
            FROM interviewer_agent_prompts
            WHERE is_active = TRUE
            ORDER BY prompt_code ASC
            """
        ).fetchall()
        bundle["interviewer"] = {
            str(row["prompt_code"]): {
                "name": str(row["prompt_name"]),
                "text": str(row["prompt_text"]),
                "version": int(row["prompt_version"]),
            }
            for row in interviewer_rows
        }
    except Exception:
        pass

    try:
        profile_rows = connection.execute(
            """
            SELECT agent_code, agent_name, competency_name, purpose_prompt, rationale_prompt,
                   evidence_prompt, red_flag_prompt, prompt_version
            FROM assessment_agent_prompt_profiles
            WHERE is_active = TRUE
            ORDER BY agent_code ASC
            """
        ).fetchall()
        rule_rows = connection.execute(
            """
            SELECT agent_code, rule_code, rule_scope, rule_text, display_order
            FROM assessment_agent_prompt_rules
            WHERE is_active = TRUE
            ORDER BY agent_code ASC, display_order ASC, id ASC
            """
        ).fetchall()
        rules_by_agent: dict[str, list[dict[str, Any]]] = {}
        for row in rule_rows:
            rules_by_agent.setdefault(str(row["agent_code"]), []).append(dict(row))
        bundle["assessment_agents"] = {
            str(row["agent_code"]): {
                "profile": dict(row),
                "rules": rules_by_agent.get(str(row["agent_code"]), []),
            }
            for row in profile_rows
        }
    except Exception:
        pass

    try:
        instruction_rows = connection.execute(
            """
            SELECT instruction_code, instruction_name, instruction_text, version,
                   applies_to_type_code, priority
            FROM case_text_build_instructions
            WHERE is_active = TRUE
            ORDER BY priority ASC, version DESC, id DESC
            """
        ).fetchall()
        bundle["case_generation_instructions"] = [dict(row) for row in instruction_rows]
    except Exception:
        pass
    return bundle


class PromptResolver:
    def interviewer_prompt(
        self,
        snapshot: dict[str, Any] | None,
        *,
        prompt_code: str,
        fallback_text: str,
        format_values: dict[str, str] | None = None,
    ) -> str:
        prompt_row = (
            dict((snapshot or {}).get("prompts") or {})
            .get("interviewer", {})
            .get(prompt_code)
        )
        prompt_text = str((prompt_row or {}).get("text") or fallback_text or "").strip()
        if format_values:
            try:
                return prompt_text.format(**format_values)
            except Exception:
                fallback = str(fallback_text or "").strip()
                try:
                    return fallback.format(**format_values)
                except Exception:
                    return fallback
        return prompt_text

    def assessment_agent_config(
        self,
        snapshot: dict[str, Any] | None,
        *,
        agent_code: str,
    ) -> dict[str, Any] | None:
        config = dict((snapshot or {}).get("prompts") or {}).get("assessment_agents", {}).get(agent_code)
        return dict(config) if isinstance(config, dict) else None

    def case_generation_instruction(
        self,
        snapshot: dict[str, Any] | None,
        *,
        case_type_code: str | None,
    ) -> str | None:
        rows = dict((snapshot or {}).get("prompts") or {}).get("case_generation_instructions", [])
        if not isinstance(rows, list):
            return None
        normalized_type = str(case_type_code or "").strip()
        exact = [row for row in rows if str((row or {}).get("applies_to_type_code") or "").strip() == normalized_type]
        generic = [row for row in rows if not str((row or {}).get("applies_to_type_code") or "").strip()]
        selected = (exact or generic or [None])[0]
        text = str((selected or {}).get("instruction_text") or "").strip()
        return text or None


prompt_resolver = PromptResolver()
