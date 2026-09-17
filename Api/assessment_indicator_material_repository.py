from __future__ import annotations

import re
from typing import Any

from Api.assessment_evaluation_material_repository import CASE_REFUSAL_PHRASES
from Api.assessment_configuration import definition_checksum
from Api.assessment_evaluator_contracts import (
    INDICATOR_EVALUATOR_CONTRACT_VERSION,
    CompetencyIndicatorEvaluationInput,
    validate_agent_runtime,
)


class AssessmentIndicatorMaterialRepository:
    """Build indicator material from frozen methodology and session-scoped case links."""

    def load(
        self,
        connection,
        *,
        session_id: int,
        methodology_version_id: int,
        competency: dict[str, Any],
    ) -> list[dict[str, Any]]:
        hierarchy, indicator_codes = self._normalize_competency(competency)
        rows = connection.execute(
            """
            SELECT sci.indicator_code, sc.id AS session_case_id, sc.case_registry_id,
                   cra.artifact_code AS expected_artifact_code,
                   cra.artifact_name AS expected_artifact,
                   ctp.base_structure_description AS answer_structure_hint,
                   txt.constraints_text, sc.required_blocks_version, sc.red_flags_version
            FROM session_case_indicators sci
            JOIN session_cases sc ON sc.id = sci.session_case_id
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            LEFT JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
            LEFT JOIN case_response_artifacts cra ON cra.id = ctp.artifact_id
            LEFT JOIN case_texts txt
              ON txt.cases_registry_id = cr.id AND txt.version = sc.case_text_version
            WHERE sc.session_id = %s
              AND sci.methodology_version_id = %s
              AND sci.indicator_code = ANY(%s)
            ORDER BY sci.indicator_code, sc.id
            """,
            (session_id, methodology_version_id, indicator_codes),
        ).fetchall()
        cases_by_indicator = {code: [] for code in indicator_codes}
        for row in rows:
            cases_by_indicator[str(row["indicator_code"])].append(
                self._load_case(connection, row=dict(row), methodology_version_id=methodology_version_id)
            )
        for skill in hierarchy:
            for component in skill["components"]:
                for indicator in component["indicators"]:
                    indicator["cases"] = cases_by_indicator[indicator["indicator_code"]]
        return hierarchy

    def _normalize_competency(self, competency: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        skills: list[dict[str, Any]] = []
        indicator_codes: list[str] = []
        for skill in competency.get("skills") or []:
            components = []
            for component in skill.get("components") or []:
                indicators = []
                for indicator in component.get("indicators") or []:
                    code = str(indicator.get("id") or "").strip()
                    levels = dict(indicator.get("levels") or {})
                    indicators.append({
                        "indicator_code": code,
                        "indicator_name": str(indicator.get("name") or "").strip(),
                        "function": str(indicator.get("function") or "").strip(),
                        "product": str(indicator.get("product") or "").strip(),
                        "levels": {key: {"descriptor": str(value).strip()} for key, value in levels.items()},
                        "boundary": str(indicator.get("boundary") or "").strip(),
                        "evidence_pattern": str(indicator.get("evidence_pattern") or "").strip(),
                        "red_flags": list(indicator.get("red_flags") or []),
                        "cases": [],
                    })
                    indicator_codes.append(code)
                components.append({
                    "component_code": str(component.get("id") or "").strip(),
                    "component_name": str(component.get("name") or "").strip(),
                    "indicators": indicators,
                })
            skills.append({
                "skill_code": str(skill.get("id") or "").strip(),
                "skill_name": str(skill.get("name") or "").strip(),
                "components": components,
            })
        if not skills or not indicator_codes or len(indicator_codes) != len(set(indicator_codes)):
            raise ValueError("Frozen competency must contain a non-empty unique indicator scope.")
        return skills, sorted(indicator_codes)

    def _load_case(self, connection, *, row: dict[str, Any], methodology_version_id: int) -> dict[str, Any]:
        messages = connection.execute(
            """
            SELECT message_text FROM session_case_messages
            WHERE session_case_id = %s AND role = 'user' ORDER BY id
            """,
            (row["session_case_id"],),
        ).fetchall()
        methodical = connection.execute(
            """
            SELECT crb.block_code, crb.block_name,
                   ctrf.flag_code, ctrf.flag_name, ctrf.flag_description,
                   cie.related_response_block_code, cie.evidence_description, cie.expected_signal
            FROM cases_registry cr
            LEFT JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
            LEFT JOIN case_required_response_blocks crb
              ON crb.case_type_passport_id = ctp.id AND crb.version = %s
            LEFT JOIN case_type_red_flags ctrf
              ON ctrf.case_type_passport_id = ctp.id AND ctrf.version = %s
            LEFT JOIN case_type_indicator_evidence cie
              ON cie.case_type_passport_id = ctp.id
             AND cie.methodology_version_id = %s
             AND cie.indicator_code = %s
            WHERE cr.id = %s
            ORDER BY crb.block_code, ctrf.flag_code, cie.display_order
            """,
            (
                row["required_blocks_version"], row["red_flags_version"],
                methodology_version_id, row["indicator_code"], row["case_registry_id"],
            ),
        ).fetchall()
        blocks, flags, evidence = [], [], []
        seen_blocks, seen_flags, seen_evidence = set(), set(), set()
        for item in methodical:
            block_code = str(item["block_code"] or "").strip()
            if block_code and block_code not in seen_blocks:
                seen_blocks.add(block_code); blocks.append({"block_code": block_code, "block_name": str(item["block_name"] or "").strip()})
            flag_code = str(item["flag_code"] or "").strip()
            if flag_code and flag_code not in seen_flags:
                seen_flags.add(flag_code); flags.append({"flag_code": flag_code, "flag_name": str(item["flag_name"] or "").strip(), "flag_description": str(item["flag_description"] or "").strip()})
            evidence_key = (str(item["related_response_block_code"] or "").strip(), str(item["evidence_description"] or "").strip(), str(item["expected_signal"] or "").strip())
            if evidence_key[1] and evidence_key not in seen_evidence:
                seen_evidence.add(evidence_key); evidence.append({"related_response_block_code": evidence_key[0], "evidence_description": evidence_key[1], "expected_signal": evidence_key[2]})
        user_text = "\n".join(str(item["message_text"] or "") for item in messages)
        normalized = re.sub(r"\s+", " ", re.sub(r"[^a-zа-я0-9\s?%-]", " ", user_text.lower().replace("ё", "е"))).strip()
        return {
            "session_case_id": int(row["session_case_id"]), "case_registry_id": row["case_registry_id"],
            "user_text": user_text, "expected_artifact_code": row["expected_artifact_code"] or "",
            "expected_artifact": row["expected_artifact"] or "", "answer_structure_hint": row["answer_structure_hint"] or "",
            "constraints_text": row["constraints_text"] or "", "required_response_blocks": blocks,
            "methodical_red_flags": flags, "indicator_evidence": evidence,
            "is_refusal_case": not normalized or any(phrase in normalized for phrase in CASE_REFUSAL_PHRASES),
        }


class CompetencyIndicatorEvaluationInputBuilder:
    def __init__(self, repository: AssessmentIndicatorMaterialRepository | None = None) -> None:
        self._repository = repository or AssessmentIndicatorMaterialRepository()

    def resolve_agent_definition(
        self,
        *,
        snapshot: dict[str, Any],
        competency: dict[str, Any],
        component_code: str,
        component_version: int,
    ) -> dict[str, Any]:
        reference = competency.get("agent_definition")
        reference = dict(reference) if isinstance(reference, dict) else {}
        definition_code = str(reference.get("code") or "").strip()
        requested_version = int(reference.get("version") or 0)
        frozen = dict(((snapshot.get("prompts") or {}).get("agent_definitions") or {}).get(definition_code) or {})
        if not frozen:
            raise ValueError(f"Frozen indicator agent definition is missing: {definition_code}.")
        definition = dict(frozen.get("definition") or {})
        version = int(frozen.get("version") or 0)
        if not requested_version or version != requested_version:
            raise ValueError(f"Frozen indicator agent definition version mismatch: {definition_code} v{version}.")
        checksum = str(frozen.get("checksum") or "")
        if checksum != definition_checksum(definition):
            raise ValueError(f"Frozen indicator agent definition checksum mismatch: {definition_code} v{version}.")
        input_contract = dict(definition.get("input_contract") or {})
        output_contract = dict(definition.get("output_contract") or {})
        executor = dict(definition.get("executor") or {})
        expected_contract = INDICATOR_EVALUATOR_CONTRACT_VERSION
        if (input_contract.get("code"), int(input_contract.get("version") or 0)) != (
            "competency_evaluation_input", expected_contract,
        ) or (output_contract.get("code"), int(output_contract.get("version") or 0)) != (
            "competency_evaluation_output", expected_contract,
        ):
            raise ValueError(f"Unsupported indicator agent contracts: {definition_code} v{version}.")
        if (executor.get("code"), int(executor.get("version") or 0)) != (component_code, component_version):
            raise ValueError(f"Indicator agent executor mismatch: {definition_code} v{version}.")
        runtime = validate_agent_runtime(dict(definition.get("runtime") or {}))
        if runtime["mode"] != "universal_llm":
            raise ValueError("Indicator evaluator requires universal_llm runtime.")
        return {
            "id": frozen.get("id"),
            "code": str(frozen.get("code") or definition_code),
            "name": str(frozen.get("name") or definition_code),
            "version": version,
            "checksum": checksum,
            "instruction_markdown": str(definition.get("instruction_markdown") or "").strip(),
            "input_contract": input_contract,
            "output_contract": output_contract,
            "executor": executor,
            "runtime": runtime,
        }

    def build(self, *, connection, snapshot: dict[str, Any], session_id: int, user_id: int,
              competency_code: str, component_code: str, component_version: int,
              agent_definition: dict[str, Any]) -> CompetencyIndicatorEvaluationInput:
        methodology = dict(snapshot.get("methodology") or {})
        definition = dict(methodology.get("definition") or {})
        competency = next((item for item in definition.get("competencies") or [] if item.get("id") == competency_code), None)
        if competency is None:
            raise ValueError(f"Frozen competency is missing: {competency_code}.")
        skills = self._repository.load(connection, session_id=session_id,
                                       methodology_version_id=int(methodology.get("id") or 0), competency=competency)
        return CompetencyIndicatorEvaluationInput(
            session_id=session_id, user_id=user_id, methodology_code=str(methodology.get("code") or ""),
            methodology_version_id=int(methodology.get("id") or 0),
            methodology_version=str(definition.get("methodology_version") or methodology.get("version") or ""),
            competency_code=competency_code, component_code=component_code, component_version=component_version,
            agent_definition=agent_definition, skills=skills,
        )


assessment_indicator_material_repository = AssessmentIndicatorMaterialRepository()
