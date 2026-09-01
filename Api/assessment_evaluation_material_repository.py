from __future__ import annotations

import re
from typing import Any


LEVEL_NAMES = {"L1": "Базовый", "L2": "Продвинутый", "L3": "Системный", "N/A": "Не проявлено"}
CASE_REFUSAL_PHRASES = {
    "не буду проходить", "не хочу проходить", "отказываюсь проходить",
    "не буду отвечать", "не хочу отвечать", "пропускаю кейс",
    "не стану проходить", "не буду делать",
}


class AssessmentEvaluationMaterialRepository:
    """Read self-contained evaluation material for explicitly frozen skill codes."""

    def load(self, connection, *, session_id: int, skill_codes: list[str]) -> list[dict[str, Any]]:
        normalized_codes = sorted({str(code).strip() for code in skill_codes if str(code).strip()})
        if not normalized_codes:
            raise ValueError("Universal evaluator material scope requires skill_codes.")
        rows = connection.execute(
            """
            SELECT DISTINCT
                s.id AS skill_id, s.skill_code, s.skill_name, s.competency_name,
                cs.id AS competency_skill_id
            FROM session_case_skills scs
            JOIN session_cases sc ON sc.id = scs.session_case_id
            JOIN skills s ON s.id = scs.skill_id
            LEFT JOIN competency_skills cs ON cs.skill_code = s.skill_code
            WHERE sc.session_id = %s
              AND s.skill_code = ANY(%s)
            ORDER BY s.skill_code ASC NULLS LAST, s.id ASC
            """,
            (session_id, normalized_codes),
        ).fetchall()
        return [
            {
                **dict(row),
                "rubric": self._load_rubric(connection, row["competency_skill_id"]),
                "cases": self._load_cases(connection, session_id=session_id, skill_id=int(row["skill_id"])),
            }
            for row in rows
        ]

    def _load_rubric(self, connection, competency_skill_id: int | None) -> dict[str, dict[str, str]]:
        if competency_skill_id is None:
            return {}
        rows = connection.execute(
            """
            SELECT level_code, level_name, knowledge_text, skill_text, behavior_text
            FROM competency_skill_criteria
            WHERE competency_skill_id = %s
            ORDER BY level_code ASC
            """,
            (competency_skill_id,),
        ).fetchall()
        return {
            row["level_code"]: {
                "level_name": row["level_name"] or LEVEL_NAMES.get(row["level_code"], row["level_code"]),
                "knowledge_text": row["knowledge_text"] or "",
                "skill_text": row["skill_text"] or "",
                "behavior_text": row["behavior_text"] or "",
            }
            for row in rows
        }

    def _load_cases(self, connection, *, session_id: int, skill_id: int) -> list[dict[str, Any]]:
        case_rows = connection.execute(
            """
            SELECT DISTINCT
                sc.id AS session_case_id, sc.case_registry_id,
                cra.artifact_code AS expected_artifact_code,
                cra.artifact_name AS expected_artifact,
                ctp.base_structure_description AS answer_structure_hint,
                txt.constraints_text, ''::text AS clarifying_questions
            FROM session_cases sc
            JOIN session_case_skills scs ON scs.session_case_id = sc.id
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            LEFT JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
            LEFT JOIN case_response_artifacts cra ON cra.id = ctp.artifact_id
            LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
            WHERE sc.session_id = %s AND scs.skill_id = %s
            ORDER BY sc.id ASC
            """,
            (session_id, skill_id),
        ).fetchall()
        payload: list[dict[str, Any]] = []
        for case_row in case_rows:
            messages = connection.execute(
                """
                SELECT message_text FROM session_case_messages
                WHERE session_case_id = %s AND role = 'user'
                ORDER BY id ASC
                """,
                (case_row["session_case_id"],),
            ).fetchall()
            methodical_rows = connection.execute(
                """
                SELECT crb.block_code, crb.block_name,
                       ctrf.flag_code, ctrf.flag_name, ctrf.flag_description,
                       cse.evidence_description, cse.expected_signal
                FROM cases_registry cr
                LEFT JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
                LEFT JOIN case_required_response_blocks crb ON crb.case_type_passport_id = ctp.id
                LEFT JOIN case_type_red_flags ctrf ON ctrf.case_type_passport_id = ctp.id
                LEFT JOIN case_type_skill_evidence cse
                  ON cse.case_type_passport_id = ctp.id AND cse.skill_id = %s
                WHERE cr.id = %s
                """,
                (skill_id, case_row["case_registry_id"]),
            ).fetchall()
            blocks: list[dict[str, str]] = []
            flags: list[dict[str, str]] = []
            evidence: list[dict[str, str]] = []
            seen_blocks: set[str] = set()
            seen_flags: set[str] = set()
            seen_evidence: set[tuple[str, str]] = set()
            for item in methodical_rows:
                block_code = str(item["block_code"] or "").strip()
                if block_code and block_code not in seen_blocks:
                    seen_blocks.add(block_code)
                    blocks.append({"block_code": block_code, "block_name": str(item["block_name"] or "").strip()})
                flag_code = str(item["flag_code"] or "").strip()
                if flag_code and flag_code not in seen_flags:
                    seen_flags.add(flag_code)
                    flags.append({
                        "flag_code": flag_code,
                        "flag_name": str(item["flag_name"] or "").strip(),
                        "flag_description": str(item["flag_description"] or "").strip(),
                    })
                description = str(item["evidence_description"] or "").strip()
                signal = str(item["expected_signal"] or "").strip()
                evidence_key = (description, signal)
                if (description or signal) and evidence_key not in seen_evidence:
                    seen_evidence.add(evidence_key)
                    evidence.append({
                        "related_response_block_code": block_code,
                        "evidence_description": description,
                        "expected_signal": signal,
                    })
            user_text = "\n".join(str(row["message_text"] or "") for row in messages)
            payload.append({
                "session_case_id": int(case_row["session_case_id"]),
                "case_registry_id": case_row["case_registry_id"],
                "user_text": user_text,
                "expected_artifact_code": case_row["expected_artifact_code"] or "",
                "expected_artifact": case_row["expected_artifact"] or "",
                "answer_structure_hint": case_row["answer_structure_hint"] or "",
                "constraints_text": case_row["constraints_text"] or "",
                "clarifying_questions": case_row["clarifying_questions"] or "",
                "required_response_blocks": blocks,
                "methodical_red_flags": flags,
                "skill_evidence": evidence,
                "is_refusal_case": self._is_refusal_case(user_text),
            })
        return payload

    def _is_refusal_case(self, user_text: str) -> bool:
        normalized = re.sub(r"\s+", " ", re.sub(r"[^a-zа-я0-9\s?%-]", " ", user_text.lower().replace("ё", "е"))).strip()
        return not normalized or any(phrase in normalized for phrase in CASE_REFUSAL_PHRASES)


class UniversalEvaluationMaterialProvider:
    def __init__(self, *, skill_codes: list[str], repository: AssessmentEvaluationMaterialRepository | None = None) -> None:
        self._skill_codes = list(skill_codes)
        self._repository = repository or assessment_evaluation_material_repository

    def load_evaluation_materials(self, *, connection, session_id: int, prompt_snapshot: dict[str, Any] | None):
        return {"profile": {}, "rules": []}, self._repository.load(
            connection,
            session_id=session_id,
            skill_codes=self._skill_codes,
        )


assessment_evaluation_material_repository = AssessmentEvaluationMaterialRepository()
