from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from Api.deepseek_client import deepseek_client


STOP_WORDS = {
    "для", "как", "это", "или", "если", "при", "что", "его", "ее", "так", "уже", "через",
    "над", "под", "без", "из", "по", "на", "от", "до", "не", "но", "и", "в", "во", "с", "со",
    "к", "ко", "а", "о", "об", "обо", "за", "мы", "вы", "они", "она", "он", "их", "наш",
    "ваш", "этот", "эта", "эти", "того", "также", "рамках", "уровне", "очень", "который",
}

CASE_REFUSAL_PHRASES = {
    "не буду проходить",
    "не хочу проходить",
    "отказываюсь проходить",
    "не буду отвечать",
    "не хочу отвечать",
    "пропускаю кейс",
    "не стану проходить",
    "не буду делать",
}

LEVEL_NAMES = {
    "L1": "Базовый",
    "L2": "Продвинутый",
    "L3": "Системный",
    "N/A": "Не проявлено",
}


@dataclass(slots=True)
class SkillEvaluation:
    skill_id: int
    competency_skill_id: int | None
    skill_code: str | None
    skill_name: str
    competency_name: str
    level_code: str
    level_name: str
    rubric_match_scores: dict[str, int]
    structural_elements: dict[str, bool]
    red_flags: list[str]
    found_evidence: list[dict[str, str]]
    detected_required_blocks: list[str]
    missing_required_blocks: list[str]
    block_coverage_percent: int | None
    rationale: str
    evidence_excerpt: str
    source_session_case_ids: list[int]


class BaseCompetencyAgent:
    def __init__(self, competency_name: str, agent_code: str) -> None:
        self.competency_name = competency_name
        self.agent_code = agent_code
        self._semantic_rubric_cache: dict[str, dict[str, int]] = {}

    def normalize_text(self, value: str | None) -> str:
        if not value:
            return ""
        normalized = value.lower().replace("ё", "е")
        normalized = re.sub(r"[^a-zа-я0-9\s?%-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def tokenize(self, value: str | None) -> set[str]:
        tokens: set[str] = set()
        for token in self.normalize_text(value).split():
            if len(token) < 4 or token in STOP_WORDS:
                continue
            tokens.add(token)
        return tokens

    def _load_agent_prompt_profile(self, connection) -> dict[str, Any]:
        profile_row = connection.execute(
            """
            SELECT agent_code, agent_name, competency_name, purpose_prompt, rationale_prompt,
                   evidence_prompt, red_flag_prompt, prompt_version
            FROM assessment_agent_prompt_profiles
            WHERE agent_code = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (self.agent_code,),
        ).fetchone()
        rules_rows = connection.execute(
            """
            SELECT rule_code, rule_scope, rule_text, display_order
            FROM assessment_agent_prompt_rules
            WHERE agent_code = %s
              AND is_active = TRUE
            ORDER BY display_order ASC, id ASC
            """,
            (self.agent_code,),
        ).fetchall()
        return {
            "profile": dict(profile_row) if profile_row else {},
            "rules": [dict(row) for row in rules_rows],
        }

    def evaluate_session(self, *, connection, session_id: int, user_id: int) -> list[SkillEvaluation]:
        skills = self._load_session_skills(connection, session_id)
        if not skills:
            return []
        agent_prompt_config = self._load_agent_prompt_profile(connection)

        evaluations: list[SkillEvaluation] = []
        for skill in skills:
            case_payload = self._load_case_payload_for_skill(connection, session_id, skill["skill_id"])
            if not case_payload:
                evaluation = self._build_na_evaluation(
                    skill=skill,
                    rationale="По данному навыку в сессии отсутствуют связанные кейсы или сообщения пользователя.",
                )
                self._save_evaluation(connection, session_id, user_id, evaluation)
                evaluations.append(evaluation)
                continue

            case_payload = [payload for payload in case_payload if not payload.get("is_refusal_case", False)]
            if not case_payload:
                evaluation = self._build_na_evaluation(
                    skill=skill,
                    rationale="По данному навыку не осталось валидных пользовательских ответов: кейсы были пропущены, завершены без ответа или отмечены как отказные.",
                )
                self._save_evaluation(connection, session_id, user_id, evaluation)
                evaluations.append(evaluation)
                continue

            self._save_case_level_structured_analysis(
                connection=connection,
                session_id=session_id,
                user_id=user_id,
                skill=skill,
                case_payload=case_payload,
            )
            user_text = "\n".join(payload["user_text"] for payload in case_payload if payload["user_text"]).strip()
            rubric = self._load_rubric(connection, skill["competency_skill_id"])
            structural_elements = self._extract_structural_elements(user_text, case_payload)
            detected_required_blocks, missing_required_blocks, block_coverage_percent = self._summarize_required_blocks(
                structural_elements=structural_elements,
                case_payload=case_payload,
            )
            found_evidence = self._extract_found_evidence(
                user_text=user_text,
                structural_elements=structural_elements,
                case_payload=case_payload,
            )
            artifact_detected_parts, artifact_missing_parts, artifact_compliance_percent = self._summarize_artifact_compliance(
                structural_elements=structural_elements,
                payload=case_payload[0],
            )
            rubric_match_scores = self._score_against_rubric(
                user_text,
                rubric,
                skill_name=skill["skill_name"],
                agent_prompt_config=agent_prompt_config,
            )
            red_flags = self._detect_red_flags(user_text, case_payload, structural_elements)
            level_code = self._determine_level(
                user_text=user_text,
                structural_elements=structural_elements,
                rubric_match_scores=rubric_match_scores,
                red_flags=red_flags,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=artifact_missing_parts,
            )
            evaluation = SkillEvaluation(
                skill_id=skill["skill_id"],
                competency_skill_id=skill["competency_skill_id"],
                skill_code=skill["skill_code"],
                skill_name=skill["skill_name"],
                competency_name=skill["competency_name"],
                level_code=level_code,
                level_name=self._resolve_level_name(level_code, rubric),
                rubric_match_scores=rubric_match_scores,
                structural_elements=structural_elements,
                red_flags=red_flags,
                found_evidence=found_evidence,
                detected_required_blocks=detected_required_blocks,
                missing_required_blocks=missing_required_blocks,
                block_coverage_percent=block_coverage_percent,
                rationale=self._build_rationale(
                    skill_name=skill["skill_name"],
                    level_code=level_code,
                    agent_prompt_config=agent_prompt_config,
                    structural_elements=structural_elements,
                    rubric_match_scores=rubric_match_scores,
                    red_flags=red_flags,
                    found_evidence=found_evidence,
                    detected_required_blocks=detected_required_blocks,
                    missing_required_blocks=missing_required_blocks,
                    block_coverage_percent=block_coverage_percent,
                    artifact_detected_parts=artifact_detected_parts,
                    artifact_missing_parts=artifact_missing_parts,
                    artifact_compliance_percent=artifact_compliance_percent,
                ),
                evidence_excerpt=self._build_evidence_excerpt(user_text),
                source_session_case_ids=[payload["session_case_id"] for payload in case_payload],
            )
            self._save_evaluation(connection, session_id, user_id, evaluation)
            evaluations.append(evaluation)
        return evaluations

    def _build_na_evaluation(self, *, skill: dict[str, Any], rationale: str) -> SkillEvaluation:
        return SkillEvaluation(
            skill_id=skill["skill_id"],
            competency_skill_id=skill["competency_skill_id"],
            skill_code=skill["skill_code"],
            skill_name=skill["skill_name"],
            competency_name=skill["competency_name"],
            level_code="N/A",
            level_name=LEVEL_NAMES["N/A"],
            rubric_match_scores={"L1": 0, "L2": 0, "L3": 0},
            structural_elements={},
            red_flags=[],
            found_evidence=[],
            detected_required_blocks=[],
            missing_required_blocks=[],
            block_coverage_percent=None,
            rationale=rationale,
            evidence_excerpt="",
            source_session_case_ids=[],
        )

    def _resolve_level_name(self, level_code: str, rubric: dict[str, dict[str, str]]) -> str:
        rubric_row = rubric.get(level_code, {})
        return rubric_row.get("level_name") or LEVEL_NAMES.get(level_code, level_code)

    def _load_session_skills(self, connection, session_id: int) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT DISTINCT
                s.id AS skill_id,
                s.skill_code,
                s.skill_name,
                s.competency_name,
                cs.id AS competency_skill_id
            FROM session_case_skills scs
            JOIN session_cases sc ON sc.id = scs.session_case_id
            JOIN skills s ON s.id = scs.skill_id
            LEFT JOIN competency_skills cs ON cs.skill_code = s.skill_code
            WHERE sc.session_id = %s
              AND s.competency_name = %s
            ORDER BY s.skill_code ASC NULLS LAST, s.id ASC
            """,
            (session_id, self.competency_name),
        ).fetchall()
        return [dict(row) for row in rows]

    def _load_case_payload_for_skill(self, connection, session_id: int, skill_id: int) -> list[dict[str, Any]]:
        case_rows = connection.execute(
            """
            SELECT DISTINCT
                sc.id AS session_case_id,
                sc.case_registry_id,
                cra.artifact_code AS expected_artifact_code,
                cra.artifact_name AS expected_artifact,
                ctp.base_structure_description AS answer_structure_hint,
                txt.constraints_text,
                ''::text AS clarifying_questions
            FROM session_cases sc
            JOIN session_case_skills scs ON scs.session_case_id = sc.id
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            LEFT JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
            LEFT JOIN case_response_artifacts cra ON cra.id = ctp.artifact_id
            LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
            WHERE sc.session_id = %s
              AND scs.skill_id = %s
            ORDER BY sc.id ASC
            """,
            (session_id, skill_id),
        ).fetchall()

        payload: list[dict[str, Any]] = []
        for case_row in case_rows:
            message_rows = connection.execute(
                """
                SELECT message_text
                FROM session_case_messages
                WHERE session_case_id = %s
                  AND role = 'user'
                ORDER BY id ASC
                """,
                (case_row["session_case_id"],),
            ).fetchall()
            methodical_rows = connection.execute(
                """
                SELECT
                    crb.block_code,
                    crb.block_name,
                    ctrf.flag_code,
                    ctrf.flag_name,
                    ctrf.flag_description,
                    cse.evidence_description,
                    cse.expected_signal
                FROM cases_registry cr
                LEFT JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
                LEFT JOIN case_required_response_blocks crb ON crb.case_type_passport_id = ctp.id
                LEFT JOIN case_type_red_flags ctrf ON ctrf.case_type_passport_id = ctp.id
                LEFT JOIN case_type_skill_evidence cse
                    ON cse.case_type_passport_id = ctp.id
                   AND cse.skill_id = %s
                WHERE cr.id = %s
                """,
                (skill_id, case_row["case_registry_id"]),
            ).fetchall()
            required_blocks: list[dict[str, str]] = []
            seen_blocks: set[str] = set()
            methodical_red_flags: list[dict[str, str]] = []
            seen_flags: set[str] = set()
            skill_evidence: list[dict[str, str]] = []
            seen_evidence: set[tuple[str, str]] = set()
            for item in methodical_rows:
                block_code = str(item["block_code"] or "").strip()
                block_name = str(item["block_name"] or "").strip()
                if block_code and block_code not in seen_blocks:
                    seen_blocks.add(block_code)
                    required_blocks.append({"block_code": block_code, "block_name": block_name})
                flag_code = str(item["flag_code"] or "").strip()
                if flag_code and flag_code not in seen_flags:
                    seen_flags.add(flag_code)
                    methodical_red_flags.append(
                        {
                            "flag_code": flag_code,
                            "flag_name": str(item["flag_name"] or "").strip(),
                            "flag_description": str(item["flag_description"] or "").strip(),
                        }
                    )
                evidence_description = str(item["evidence_description"] or "").strip()
                expected_signal = str(item["expected_signal"] or "").strip()
                evidence_key = (evidence_description, expected_signal)
                if (evidence_description or expected_signal) and evidence_key not in seen_evidence:
                    seen_evidence.add(evidence_key)
                    skill_evidence.append(
                        {
                            "related_response_block_code": block_code,
                            "evidence_description": evidence_description,
                            "expected_signal": expected_signal,
                        }
                    )
            user_text = "\n".join(row["message_text"] for row in message_rows)
            payload.append(
                {
                    "session_case_id": case_row["session_case_id"],
                    "case_registry_id": case_row["case_registry_id"],
                    "user_text": user_text,
                    "expected_artifact_code": case_row["expected_artifact_code"] or "",
                    "expected_artifact": case_row["expected_artifact"] or "",
                    "answer_structure_hint": case_row["answer_structure_hint"] or "",
                    "constraints_text": case_row["constraints_text"] or "",
                    "clarifying_questions": case_row["clarifying_questions"] or "",
                    "required_response_blocks": required_blocks,
                    "methodical_red_flags": methodical_red_flags,
                    "skill_evidence": skill_evidence,
                    "is_refusal_case": self._is_refusal_case(user_text),
                }
            )
        return payload

    def _is_refusal_case(self, user_text: str) -> bool:
        normalized = self.normalize_text(user_text)
        if not normalized:
            return True
        return any(phrase in normalized for phrase in CASE_REFUSAL_PHRASES)

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
        rubric: dict[str, dict[str, str]] = {}
        for row in rows:
            rubric[row["level_code"]] = {
                "level_name": row["level_name"] or LEVEL_NAMES.get(row["level_code"], row["level_code"]),
                "knowledge_text": row["knowledge_text"] or "",
                "skill_text": row["skill_text"] or "",
                "behavior_text": row["behavior_text"] or "",
            }
        return rubric

    def _detect_required_block_presence(self, user_text: str, case_payload: list[dict[str, Any]]) -> dict[str, bool]:
        normalized = self.normalize_text(user_text)

        def contains_any(words: tuple[str, ...]) -> bool:
            return any(word in normalized for word in words)

        block_presence = {
            "situation_summary": contains_any(("ситуац", "проблем", "запрос", "жалоб", "контекст")),
            "status_update": contains_any(("статус", "сейчас", "уже", "в работе", "провер", "сделан")),
            "next_step": contains_any(("следующ", "дальше", "затем", "шаг", "план", "сначала")),
            "deadline": contains_any(("срок", "час", "день", "сегодня", "завтра", "обновлен")),
            "questions": "?" in user_text or contains_any(("вопрос", "уточн", "спрос")),
            "understanding_summary": contains_any(("понима", "резюм", "итог", "правильно понял")),
            "goal": contains_any(("цель", "результат", "должны достичь")),
            "fact_impact": contains_any(("факт", "влияни", "последств", "пример")),
            "agreement": contains_any(("договор", "соглас", "зафиксир", "подтверж")),
            "task_split": contains_any(("распредел", "роль", "ответствен", "кто делает")),
            "control_points": contains_any(("контроль", "синхрон", "контрольн", "ритм", "провер")),
            "fallback": contains_any(("план b", "резерв", "на случай", "если не")),
            "known_unknown": contains_any(("известн", "неизвестн", "допущен", "не хватает данных")),
            "alternatives": contains_any(("альтернатив", "вариант", "опци", "сценари")),
            "decision": contains_any(("решени", "выбира", "предлагаю", "стоит")),
            "review_point": contains_any(("пересмотр", "контрольная точка", "вернемся", "позже проверим")),
            "ideas": contains_any(("иде", "предлож", "вариант", "подход")),
            "grouping": contains_any(("сгрупп", "раздел", "категор", "тип подхода")),
            "top_choices": contains_any(("лучший", "приоритетн", "наиболее сильн", "выделю")),
            "criteria": contains_any(("критер", "метрик", "показател", "kpi", "оцен")),
            "implementation_plan": contains_any(("внедрен", "этап", "реализ", "запуст", "пилот")),
            "success_metric": contains_any(("метрик", "успех", "сработал", "показател")),
            "facts": contains_any(("факт", "обнаруж", "провер", "зафиксир")),
            "risk": contains_any(("риск", "угроз", "последств", "сбой")),
            "escalation": contains_any(("эскал", "подним", "передам", "сообщу руковод")),
            "development_plan": contains_any(("развит", "что менять", "план изменен", "в горизонте")),
            "progress_metric": contains_any(("прогресс", "признак улучшен", "по чему поймем", "метрик")),
        }
        required_codes = {
            block["block_code"]
            for payload in case_payload
            for block in payload.get("required_response_blocks", [])
            if block.get("block_code")
        }
        return {f"covers_{code}": block_presence.get(code, False) for code in required_codes}

    def _extract_structural_elements(self, user_text: str, case_payload: list[dict[str, Any]]) -> dict[str, bool]:
        normalized = self.normalize_text(user_text)
        combined_hints = " ".join(
            payload["expected_artifact"] + " " + payload["answer_structure_hint"] + " " + payload["clarifying_questions"]
            for payload in case_payload
        ).lower()
        methodical_signal_text = " ".join(
            " ".join(
                [
                    " ".join(block.get("block_name", "") for block in payload.get("required_response_blocks", [])),
                    " ".join(item.get("evidence_description", "") for item in payload.get("skill_evidence", [])),
                    " ".join(item.get("expected_signal", "") for item in payload.get("skill_evidence", [])),
                ]
            )
            for payload in case_payload
        ).lower()

        def contains_any(words: tuple[str, ...]) -> bool:
            return any(word in normalized for word in words)

        result = {
            "has_alternatives": contains_any(("альтернатив", "вариант", "опци", "сценари")),
            "has_criteria": contains_any(("критер", "метрик", "показател", "kpi", "оцен")),
            "has_risks": contains_any(("риск", "огранич", "угроз", "проблем", "сбой", "зависим")),
            "has_next_step": contains_any(("сначала", "далее", "затем", "следующ", "перв", "шаг", "план")),
            "has_questions": "?" in user_text or contains_any(("уточн", "вопрос", "спрос")),
            "has_systemness": contains_any(("система", "процесс", "взаимосвяз", "контур", "влияни", "стейкхолдер")),
            "has_predictive": contains_any(("если", "может привести", "повлияет", "сценар", "прогноз", "последств")),
            "has_balance": contains_any(("баланс", "интерес", "компромисс", "для бизнеса", "для команды", "для клиента")),
            "has_structure": sum(
                1
                for flag in (
                    contains_any(("альтернатив", "вариант", "опци", "сценари")),
                    contains_any(("критер", "метрик", "показател", "kpi", "оцен")),
                    contains_any(("риск", "огранич", "угроз", "проблем", "сбой", "зависим")),
                    contains_any(("сначала", "далее", "затем", "следующ", "перв", "шаг", "план")),
                    "?" in user_text or contains_any(("уточн", "вопрос", "спрос")),
                )
                if flag
            ) >= 2,
            "expects_alternatives": "альтернатив" in combined_hints or "вариант" in combined_hints or "альтернатив" in methodical_signal_text,
            "expects_criteria": "критер" in combined_hints or "метрик" in combined_hints or "критер" in methodical_signal_text,
            "expects_risks": "риск" in combined_hints or "огранич" in combined_hints or "риск" in methodical_signal_text,
            "expects_next_step": "шаг" in combined_hints or "план" in combined_hints or "следующ" in methodical_signal_text,
        }
        result.update(self._detect_required_block_presence(user_text, case_payload))
        return result

    def _score_against_rubric_token_fallback(self, user_text: str, rubric: dict[str, dict[str, str]]) -> dict[str, int]:
        answer_tokens = self.tokenize(user_text)
        scores = {"L1": 0, "L2": 0, "L3": 0}
        for level_code in ("L1", "L2", "L3"):
            row = rubric.get(level_code, {})
            rubric_tokens = self.tokenize(" ".join([row.get("knowledge_text", ""), row.get("skill_text", ""), row.get("behavior_text", "")]))
            scores[level_code] = len(answer_tokens & rubric_tokens)
        return scores

    def _semantic_rubric_cache_key(
        self,
        *,
        user_text: str,
        skill_name: str,
        rubric: dict[str, dict[str, str]],
        agent_prompt_config: dict[str, Any] | None,
    ) -> str:
        rules = list((agent_prompt_config or {}).get("rules") or [])
        profile = dict((agent_prompt_config or {}).get("profile") or {})
        return json.dumps(
            {
                "agent_code": self.agent_code,
                "competency": self.competency_name,
                "skill_name": skill_name,
                "user_text": user_text,
                "rubric": rubric,
                "purpose_prompt": profile.get("purpose_prompt"),
                "rules": [str(item.get("rule_text") or "").strip() for item in rules],
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def _parse_semantic_rubric_scores(self, raw: str) -> dict[str, int] | None:
        text = str(raw or "").strip()
        if not text:
            return None
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except Exception:
            return None
        scores = payload.get("scores")
        if not isinstance(scores, dict):
            return None
        normalized = {
            "L1": 1 if int(scores.get("L1", 0) or 0) > 0 else 0,
            "L2": 1 if int(scores.get("L2", 0) or 0) > 0 else 0,
            "L3": 1 if int(scores.get("L3", 0) or 0) > 0 else 0,
        }
        return normalized

    def _score_against_rubric(
        self,
        user_text: str,
        rubric: dict[str, dict[str, str]],
        *,
        skill_name: str,
        agent_prompt_config: dict[str, Any] | None = None,
    ) -> dict[str, int]:
        if not rubric or not self.normalize_text(user_text):
            return {"L1": 0, "L2": 0, "L3": 0}
        if not deepseek_client.enabled:
            return self._score_against_rubric_token_fallback(user_text, rubric)

        cache_key = self._semantic_rubric_cache_key(
            user_text=user_text,
            skill_name=skill_name,
            rubric=rubric,
            agent_prompt_config=agent_prompt_config,
        )
        cached = self._semantic_rubric_cache.get(cache_key)
        if cached is not None:
            return dict(cached)

        profile = dict((agent_prompt_config or {}).get("profile") or {})
        rules = list((agent_prompt_config or {}).get("rules") or [])
        rule_lines = [
            f"- {str(item.get('rule_text') or '').strip()}"
            for item in rules
            if str(item.get("rule_text") or "").strip()
        ]
        rubric_lines: list[str] = []
        for level_code in ("L1", "L2", "L3"):
            row = rubric.get(level_code, {})
            rubric_lines.append(
                "\n".join(
                    [
                        f"{level_code} ({row.get('level_name') or LEVEL_NAMES.get(level_code, level_code)}):",
                        f"knowledge: {row.get('knowledge_text', '').strip()}",
                        f"skill: {row.get('skill_text', '').strip()}",
                        f"behavior: {row.get('behavior_text', '').strip()}",
                    ]
                )
            )

        system_prompt = (
            "Ты оценочный агент 4K-компетенций. "
            "Твоя задача — определить проявленный уровень навыка по смыслу рубрики, а не по буквальному совпадению слов. "
            "Смотри на то, демонстрирует ли ответ пользователя знания, действия и поведение, описанные в уровнях L1-L3. "
            "Оцени строго. Не повышай уровень только из-за отдельных терминов или формально похожих слов. "
            "Верни только JSON формата "
            '{"scores":{"L1":0|1,"L2":0|1,"L3":0|1},"best_level":"N/A|L1|L2|L3","reason":"..."}. '
            "Правила: L3=1 только если ответ явно соответствует системному уровню; "
            "L2=1 только если ответ уверенно соответствует продвинутому уровню; "
            "L1=1 только если хотя бы базовое проявление навыка действительно есть. "
            "Если уровень не достигнут по смыслу рубрики, ставь 0."
        )
        if str(profile.get("purpose_prompt") or "").strip():
            system_prompt += "\nФокус агента: " + str(profile.get("purpose_prompt") or "").strip()
        if rule_lines:
            system_prompt += "\nПравила оценки:\n" + "\n".join(rule_lines)

        user_prompt = (
            f"Компетенция: {self.competency_name}\n"
            f"Навык: {skill_name}\n\n"
            "Рубрика уровней:\n"
            f"{chr(10).join(rubric_lines)}\n\n"
            "Ответ пользователя:\n"
            f"{user_text}\n\n"
            "Определи соответствие ответа уровням рубрики по смыслу."
        )

        try:
            raw = deepseek_client._post_chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                timeout_sec=45,
                routing_key=f"semantic_rubric::{self.agent_code}::{skill_name}",
            )
            parsed = self._parse_semantic_rubric_scores(raw)
            if parsed is not None:
                self._semantic_rubric_cache[cache_key] = dict(parsed)
                return parsed
        except Exception:
            pass

        return self._score_against_rubric_token_fallback(user_text, rubric)

    def _detect_red_flags(
        self,
        user_text: str,
        case_payload: list[dict[str, Any]],
        structural_elements: dict[str, bool],
    ) -> list[str]:
        normalized = self.normalize_text(user_text)
        flags: list[str] = []
        if any(phrase in normalized for phrase in ("это не моя задача", "это не моя зона", "пусть другой", "разберется кто нибудь другой")):
            flags.append("responsibility_shift")
        if any(phrase in normalized for phrase in ("идиот", "глуп", "дурак", "наехать", "давить на", "жестко наказать")):
            flags.append("aggressive_tone")
        has_constraints = any(payload["constraints_text"].strip() for payload in case_payload)
        if has_constraints and not structural_elements["has_risks"]:
            flags.append("ignoring_constraints")
        evidence_block_codes = {
            item["related_response_block_code"]
            for payload in case_payload
            for item in payload.get("skill_evidence", [])
            if item.get("related_response_block_code")
        }
        methodical_flag_codes = {
            flag["flag_code"]
            for payload in case_payload
            for flag in payload.get("methodical_red_flags", [])
            if flag.get("flag_code")
        }
        if "no_next_step" in methodical_flag_codes and not structural_elements.get("has_next_step"):
            flags.append("no_next_step")
        if "no_questions" in methodical_flag_codes and not structural_elements.get("has_questions"):
            flags.append("no_questions")
        if "no_risks" in methodical_flag_codes and not structural_elements.get("has_risks"):
            flags.append("no_risks")
        if "no_alternatives" in methodical_flag_codes and not structural_elements.get("has_alternatives"):
            flags.append("no_alternatives")
        if "no_criteria" in methodical_flag_codes and not structural_elements.get("has_criteria"):
            flags.append("no_criteria")
        if "no_status" in methodical_flag_codes and not structural_elements.get("covers_status_update", False):
            flags.append("no_status")
        if "no_summary" in methodical_flag_codes and not structural_elements.get("covers_understanding_summary", False):
            flags.append("no_summary")
        if "no_agreement" in methodical_flag_codes and not structural_elements.get("covers_agreement", False):
            flags.append("no_agreement")
        if "no_roles" in methodical_flag_codes and not structural_elements.get("covers_task_split", False):
            flags.append("no_roles")
        if "no_control" in methodical_flag_codes and not structural_elements.get("covers_control_points", False):
            flags.append("no_control")
        if "no_metric" in methodical_flag_codes and not (
            structural_elements.get("covers_success_metric", False)
            or structural_elements.get("covers_progress_metric", False)
        ):
            flags.append("no_metric")
        return flags

    def _hard_red_flags(self) -> set[str]:
        return {
            "responsibility_shift",
            "aggressive_tone",
            "ignoring_constraints",
            "no_alignment",
            "solo_mode",
            "unsafe_team_climate",
            "template_thinking",
            "no_validation",
            "risk_blindness",
        }

    def _summarize_required_blocks(
        self,
        *,
        structural_elements: dict[str, bool],
        case_payload: list[dict[str, Any]],
    ) -> tuple[list[str], list[str], int | None]:
        block_labels: dict[str, str] = {}
        for payload in case_payload:
            for block in payload.get("required_response_blocks", []):
                block_code = str(block.get("block_code") or "").strip()
                if not block_code:
                    continue
                block_labels.setdefault(block_code, str(block.get("block_name") or block_code).strip() or block_code)

        if not block_labels:
            return [], [], None

        detected = [
            label
            for code, label in block_labels.items()
            if structural_elements.get(f"covers_{code}", False)
        ]
        missing = [
            label
            for code, label in block_labels.items()
            if not structural_elements.get(f"covers_{code}", False)
        ]
        coverage_percent = round((len(detected) / len(block_labels)) * 100)
        return detected, missing, coverage_percent

    def _extract_found_evidence(
        self,
        *,
        user_text: str,
        structural_elements: dict[str, bool],
        case_payload: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        answer_tokens = self.tokenize(user_text)
        block_labels = {
            str(block.get("block_code") or "").strip(): str(block.get("block_name") or "").strip()
            for payload in case_payload
            for block in payload.get("required_response_blocks", [])
            if block.get("block_code")
        }
        found: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for payload in case_payload:
            for item in payload.get("skill_evidence", []):
                block_code = str(item.get("related_response_block_code") or "").strip()
                evidence_description = str(item.get("evidence_description") or "").strip()
                expected_signal = str(item.get("expected_signal") or "").strip()
                signal_tokens = self.tokenize(" ".join(part for part in (evidence_description, expected_signal) if part))
                matched_by_block = bool(block_code and structural_elements.get(f"covers_{block_code}", False))
                matched_by_signal = bool(signal_tokens and (answer_tokens & signal_tokens))
                if not (matched_by_block or matched_by_signal):
                    continue
                match_reason = "required_block" if matched_by_block else "signal_overlap"
                evidence_key = (block_code, evidence_description, expected_signal)
                if evidence_key in seen:
                    continue
                seen.add(evidence_key)
                found.append(
                    {
                        "related_response_block_code": block_code,
                        "related_response_block_name": block_labels.get(block_code, ""),
                        "evidence_description": evidence_description,
                        "expected_signal": expected_signal,
                        "match_reason": match_reason,
                    }
                )
        return found

    def _artifact_rule_map(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "stakeholder_message": (
                ("Адресность и контекст", "covers_situation_summary"),
                ("Статус", "covers_status_update"),
                ("Следующий шаг", "covers_next_step"),
                ("Срок обновления", "covers_deadline"),
            ),
            "questions_summary": (
                ("Уточняющие вопросы", "covers_questions"),
                ("Резюме понимания", "covers_understanding_summary"),
                ("Следующий шаг", "covers_next_step"),
            ),
            "action_plan": (
                ("Цель", "covers_goal"),
                ("План действий", "covers_task_split"),
                ("Контрольные точки", "covers_control_points"),
                ("Риски или резервный план", "has_risks"),
            ),
            "prioritization": (
                ("Альтернативы", "has_alternatives"),
                ("Критерии", "has_criteria"),
                ("Выбор решения", "covers_decision"),
                ("Точка пересмотра", "covers_review_point"),
            ),
            "dialogue_script": (
                ("Цель разговора", "covers_goal"),
                ("Факт и влияние", "covers_fact_impact"),
                ("Вопросы собеседнику", "covers_questions"),
                ("Договоренность", "covers_agreement"),
            ),
            "root_cause_analysis": (
                ("Факты и наблюдения", "covers_facts"),
                ("Риски и последствия", "covers_risk"),
                ("Причинно-следственная логика", "has_predictive"),
                ("Корректирующий шаг", "covers_next_step"),
            ),
            "pilot_plan": (
                ("Критерии оценки", "covers_criteria"),
                ("Решение по идее", "covers_decision"),
                ("План пилота", "covers_implementation_plan"),
                ("Метрика успеха", "covers_success_metric"),
            ),
        }

    def _summarize_artifact_compliance(
        self,
        *,
        structural_elements: dict[str, bool],
        payload: dict[str, Any],
    ) -> tuple[list[str], list[str], int | None]:
        artifact_code = str(payload.get("expected_artifact_code") or "").strip()
        rule_map = self._artifact_rule_map()
        rules = rule_map.get(artifact_code)
        if not rules:
            return [], [], None
        detected = [label for label, key in rules if structural_elements.get(key, False)]
        missing = [label for label, key in rules if not structural_elements.get(key, False)]
        compliance_percent = round((len(detected) / len(rules)) * 100) if rules else None
        return detected, missing, compliance_percent

    def _determine_level(
        self,
        *,
        user_text: str,
        structural_elements: dict[str, bool],
        rubric_match_scores: dict[str, int],
        red_flags: list[str],
        block_coverage_percent: int | None,
        missing_required_blocks: list[str],
        artifact_compliance_percent: int | None,
        missing_artifact_parts: list[str],
    ) -> str:
        normalized = self.normalize_text(user_text)
        if not normalized:
            return "N/A"

        l3_signal = (
            rubric_match_scores["L3"] > 0
            or (structural_elements["has_systemness"] and structural_elements["has_predictive"])
            or (structural_elements["has_balance"] and structural_elements["has_criteria"])
        )
        l2_signal = (
            rubric_match_scores["L2"] > 0
            or sum(
                1
                for flag in (
                    structural_elements["has_structure"],
                    structural_elements["has_alternatives"],
                    structural_elements["has_criteria"],
                    structural_elements["has_risks"],
                    structural_elements["has_next_step"],
                    structural_elements["has_questions"],
                )
                if flag
            ) >= 2
        )
        l1_signal = rubric_match_scores["L1"] > 0 or len(normalized.split()) >= 5

        if l3_signal:
            level = "L3"
        elif l2_signal:
            level = "L2"
        elif l1_signal:
            level = "L1"
        else:
            level = "N/A"

        if not red_flags or level == "N/A":
            level = self._adjust_level_by_structure(
                level=level,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
            )
            return self._adjust_level_by_artifact(
                level=level,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=missing_artifact_parts,
            )
        hard_red_flags = [flag for flag in red_flags if flag in self._hard_red_flags()]
        if len(hard_red_flags) >= 2:
            return "N/A"
        if hard_red_flags:
            level = {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
        level = self._adjust_level_by_structure(
            level=level,
            block_coverage_percent=block_coverage_percent,
            missing_required_blocks=missing_required_blocks,
        )
        return self._adjust_level_by_artifact(
            level=level,
            artifact_compliance_percent=artifact_compliance_percent,
            missing_artifact_parts=missing_artifact_parts,
        )

    def _adjust_level_by_structure(
        self,
        *,
        level: str,
        block_coverage_percent: int | None,
        missing_required_blocks: list[str],
    ) -> str:
        if level == "N/A" or block_coverage_percent is None:
            return level

        if block_coverage_percent == 0:
            return "N/A"
        if block_coverage_percent < 40:
            return {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
        if block_coverage_percent < 70:
            return {"L3": "L2", "L2": "L2", "L1": "L1"}.get(level, level)
        if len(missing_required_blocks) >= 3:
            return {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
        return level

    def _adjust_level_by_artifact(
        self,
        *,
        level: str,
        artifact_compliance_percent: int | None,
        missing_artifact_parts: list[str],
    ) -> str:
        if level == "N/A" or artifact_compliance_percent is None:
            return level
        if artifact_compliance_percent == 0:
            return "N/A"
        if artifact_compliance_percent < 40:
            return {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
        if artifact_compliance_percent < 70:
            return {"L3": "L2", "L2": "L2", "L1": "L1"}.get(level, level)
        if len(missing_artifact_parts) >= 3:
            return {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
        return level

    def _build_rationale(
        self,
        *,
        skill_name: str,
        level_code: str,
        agent_prompt_config: dict[str, Any] | None,
        structural_elements: dict[str, bool],
        rubric_match_scores: dict[str, int],
        red_flags: list[str],
        found_evidence: list[dict[str, str]],
        detected_required_blocks: list[str],
        missing_required_blocks: list[str],
        block_coverage_percent: int | None,
        artifact_detected_parts: list[str] | None = None,
        artifact_missing_parts: list[str] | None = None,
        artifact_compliance_percent: int | None = None,
    ) -> str:
        prompt_profile = dict((agent_prompt_config or {}).get("profile") or {})
        prompt_rules = list((agent_prompt_config or {}).get("rules") or [])
        evidence = []
        if structural_elements["has_alternatives"]:
            evidence.append("альтернативы")
        if structural_elements["has_criteria"]:
            evidence.append("критерии")
        if structural_elements["has_risks"]:
            evidence.append("риски")
        if structural_elements["has_next_step"]:
            evidence.append("следующие шаги")
        if structural_elements["has_questions"]:
            evidence.append("уточняющие вопросы")
        if structural_elements["has_systemness"]:
            evidence.append("системность")
        if structural_elements["has_predictive"]:
            evidence.append("предиктивность")
        if structural_elements["has_balance"]:
            evidence.append("баланс интересов")
        intro = str(prompt_profile.get("rationale_prompt") or "").strip()
        parts = [f"Навык «{skill_name}» отнесен к уровню {level_code}."]
        if intro:
            parts.append(intro)
        if evidence:
            parts.append(f"Выявленные признаки: {', '.join(evidence)}.")
        if prompt_rules:
            selected_rules = [str(item.get("rule_text") or "").strip() for item in prompt_rules[:2] if str(item.get("rule_text") or "").strip()]
            if selected_rules:
                parts.append(f"Фокус агента при оценке: {' '.join(selected_rules)}")
        if block_coverage_percent is not None:
            parts.append(f"Покрытие обязательных блоков ответа: {block_coverage_percent}%.")
        if artifact_compliance_percent is not None:
            parts.append(f"Соответствие ожидаемому артефакту ответа: {artifact_compliance_percent}%.")
        if detected_required_blocks:
            parts.append(f"Покрытые обязательные блоки ответа: {', '.join(detected_required_blocks)}.")
        if missing_required_blocks:
            parts.append(f"Не обнаружены блоки: {', '.join(missing_required_blocks)}.")
        if artifact_detected_parts:
            parts.append(f"Обнаружены части артефакта: {', '.join(artifact_detected_parts)}.")
        if artifact_missing_parts:
            parts.append(f"Не хватает частей артефакта: {', '.join(artifact_missing_parts)}.")
        if found_evidence:
            evidence_labels = []
            for item in found_evidence[:3]:
                label = item.get("evidence_description") or item.get("expected_signal") or item.get("related_response_block_name")
                if label:
                    evidence_labels.append(label)
            if evidence_labels:
                parts.append(f"Найденные evidence-сигналы: {', '.join(evidence_labels)}.")
        if any(rubric_match_scores.values()):
            parts.append("Семантическое соответствие рубрике: " + ", ".join(f"{level}={score}" for level, score in rubric_match_scores.items()) + ".")
        if red_flags:
            parts.append(f"Обнаружены красные флаги: {', '.join(red_flags)}.")
        return " ".join(parts)

    def _build_evidence_excerpt(self, user_text: str) -> str:
        cleaned = re.sub(r"\s+", " ", user_text).strip()
        if len(cleaned) <= 500:
            return cleaned
        return cleaned[:497] + "..."

    def _extract_detected_signals(
        self,
        *,
        structural_elements: dict[str, bool],
        found_evidence: list[dict[str, str]],
        detected_required_blocks: list[str],
        red_flags: list[str],
    ) -> list[str]:
        detected: list[str] = []
        for key, value in structural_elements.items():
            if value:
                detected.append(key)
        for item in found_evidence:
            label = str(item.get("related_response_block_code") or item.get("evidence_description") or "").strip()
            if label:
                detected.append(label)
        for block in detected_required_blocks:
            if block:
                detected.append(f"block:{block}")
        for flag in red_flags:
            if flag:
                detected.append(f"red_flag:{flag}")
        unique_detected: list[str] = []
        seen: set[str] = set()
        for item in detected:
            if item in seen:
                continue
            seen.add(item)
            unique_detected.append(item)
        return unique_detected

    def _save_case_level_structured_analysis(
        self,
        *,
        connection,
        session_id: int,
        user_id: int,
        skill: dict[str, Any],
        case_payload: list[dict[str, Any]],
    ) -> None:
        for payload in case_payload:
            user_text = payload.get("user_text") or ""
            structural_elements = self._extract_structural_elements(user_text, [payload])
            detected_required_blocks, missing_required_blocks, block_coverage_percent = self._summarize_required_blocks(
                structural_elements=structural_elements,
                case_payload=[payload],
            )
            found_evidence = self._extract_found_evidence(
                user_text=user_text,
                structural_elements=structural_elements,
                case_payload=[payload],
            )
            artifact_detected_parts, artifact_missing_parts, artifact_compliance_percent = self._summarize_artifact_compliance(
                structural_elements=structural_elements,
                payload=payload,
            )
            red_flags = self._detect_red_flags(user_text, [payload], structural_elements)
            detected_signals = self._extract_detected_signals(
                structural_elements=structural_elements,
                found_evidence=found_evidence,
                detected_required_blocks=detected_required_blocks,
                red_flags=red_flags,
            )
            source_message_count = len([line for line in user_text.splitlines() if line.strip()]) if user_text else 0
            connection.execute(
                """
                INSERT INTO session_case_skill_analysis (
                    session_id, user_id, session_case_id, case_registry_id, skill_id, competency_name,
                    expected_artifact_code, expected_artifact_name, detected_artifact_parts,
                    missing_artifact_parts, artifact_compliance_percent,
                    structural_elements, detected_required_blocks, missing_required_blocks,
                    block_coverage_percent, red_flags, found_evidence, detected_signals,
                    evidence_excerpt, source_message_count, analyzed_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    NOW(), NOW()
                )
                ON CONFLICT (session_case_id, skill_id)
                DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    user_id = EXCLUDED.user_id,
                    case_registry_id = EXCLUDED.case_registry_id,
                    competency_name = EXCLUDED.competency_name,
                    expected_artifact_code = EXCLUDED.expected_artifact_code,
                    expected_artifact_name = EXCLUDED.expected_artifact_name,
                    detected_artifact_parts = EXCLUDED.detected_artifact_parts,
                    missing_artifact_parts = EXCLUDED.missing_artifact_parts,
                    artifact_compliance_percent = EXCLUDED.artifact_compliance_percent,
                    structural_elements = EXCLUDED.structural_elements,
                    detected_required_blocks = EXCLUDED.detected_required_blocks,
                    missing_required_blocks = EXCLUDED.missing_required_blocks,
                    block_coverage_percent = EXCLUDED.block_coverage_percent,
                    red_flags = EXCLUDED.red_flags,
                    found_evidence = EXCLUDED.found_evidence,
                    detected_signals = EXCLUDED.detected_signals,
                    evidence_excerpt = EXCLUDED.evidence_excerpt,
                    source_message_count = EXCLUDED.source_message_count,
                    analyzed_at = EXCLUDED.analyzed_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    session_id,
                    user_id,
                    payload["session_case_id"],
                    payload.get("case_registry_id"),
                    skill["skill_id"],
                    skill["competency_name"],
                    payload.get("expected_artifact_code") or None,
                    payload.get("expected_artifact") or None,
                    json.dumps(artifact_detected_parts, ensure_ascii=False),
                    json.dumps(artifact_missing_parts, ensure_ascii=False),
                    artifact_compliance_percent,
                    json.dumps(structural_elements, ensure_ascii=False),
                    json.dumps(detected_required_blocks, ensure_ascii=False),
                    json.dumps(missing_required_blocks, ensure_ascii=False),
                    block_coverage_percent,
                    json.dumps(red_flags, ensure_ascii=False),
                    json.dumps(found_evidence, ensure_ascii=False),
                    json.dumps(detected_signals, ensure_ascii=False),
                    self._build_evidence_excerpt(user_text),
                    source_message_count,
                ),
            )

    def _save_evaluation(self, connection, session_id: int, user_id: int, evaluation: SkillEvaluation) -> None:
        connection.execute(
            """
            INSERT INTO session_skill_assessments (
                session_id, user_id, skill_id, competency_skill_id, competency_name, skill_code, skill_name,
                assessed_level_code, assessed_level_name, rubric_match_scores, structural_elements,
                red_flags, found_evidence, detected_required_blocks, missing_required_blocks,
                block_coverage_percent, rationale, evidence_excerpt, source_session_case_ids
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, skill_id)
            DO UPDATE SET
                competency_skill_id = EXCLUDED.competency_skill_id,
                competency_name = EXCLUDED.competency_name,
                skill_code = EXCLUDED.skill_code,
                skill_name = EXCLUDED.skill_name,
                assessed_level_code = EXCLUDED.assessed_level_code,
                assessed_level_name = EXCLUDED.assessed_level_name,
                rubric_match_scores = EXCLUDED.rubric_match_scores,
                structural_elements = EXCLUDED.structural_elements,
                red_flags = EXCLUDED.red_flags,
                found_evidence = EXCLUDED.found_evidence,
                detected_required_blocks = EXCLUDED.detected_required_blocks,
                missing_required_blocks = EXCLUDED.missing_required_blocks,
                block_coverage_percent = EXCLUDED.block_coverage_percent,
                rationale = EXCLUDED.rationale,
                evidence_excerpt = EXCLUDED.evidence_excerpt,
                source_session_case_ids = EXCLUDED.source_session_case_ids,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                user_id,
                evaluation.skill_id,
                evaluation.competency_skill_id,
                evaluation.competency_name,
                evaluation.skill_code,
                evaluation.skill_name,
                evaluation.level_code,
                evaluation.level_name,
                json.dumps(evaluation.rubric_match_scores, ensure_ascii=False),
                json.dumps(evaluation.structural_elements, ensure_ascii=False),
                json.dumps(evaluation.red_flags, ensure_ascii=False),
                json.dumps(evaluation.found_evidence, ensure_ascii=False),
                json.dumps(evaluation.detected_required_blocks, ensure_ascii=False),
                json.dumps(evaluation.missing_required_blocks, ensure_ascii=False),
                evaluation.block_coverage_percent,
                evaluation.rationale,
                evaluation.evidence_excerpt,
                json.dumps(evaluation.source_session_case_ids, ensure_ascii=False),
            ),
        )


class CommunicationAgent(BaseCompetencyAgent):
    def __init__(self) -> None:
        super().__init__("Коммуникация", "communication")

    def _extract_structural_elements(self, user_text: str, case_payload: list[dict[str, Any]]) -> dict[str, bool]:
        elements = super()._extract_structural_elements(user_text, case_payload)
        normalized = self.normalize_text(user_text)
        elements.update(
            {
                "has_message_clarity": any(word in normalized for word in ("объясн", "донес", "сформулир", "понятн", "проговор")),
                "has_audience_adaptation": any(word in normalized for word in ("кому", "для команды", "для руковод", "для клиента", "для заказчика")),
                "has_alignment": any(word in normalized for word in ("соглас", "синхрон", "договор", "подтверж", "зафиксир")),
                "has_feedback_loop": any(word in normalized for word in ("обратн", "уточн", "переспро", "подтвержу понимание")),
            }
        )
        return elements

    def _detect_red_flags(
        self,
        user_text: str,
        case_payload: list[dict[str, Any]],
        structural_elements: dict[str, bool],
    ) -> list[str]:
        flags = super()._detect_red_flags(user_text, case_payload, structural_elements)
        normalized = self.normalize_text(user_text)
        if any(phrase in normalized for phrase in ("и так поймут", "без объяснений", "не нужно обсуждать", "просто сообщу")):
            flags.append("no_alignment")
        return flags

    def _determine_level(
        self,
        *,
        user_text: str,
        structural_elements: dict[str, bool],
        rubric_match_scores: dict[str, int],
        red_flags: list[str],
        block_coverage_percent: int | None,
        missing_required_blocks: list[str],
        artifact_compliance_percent: int | None,
        missing_artifact_parts: list[str],
    ) -> str:
        if not self.normalize_text(user_text):
            return "N/A"
        if (
            rubric_match_scores["L3"] > 0
            or (
                structural_elements.get("has_message_clarity")
                and structural_elements.get("has_alignment")
                and structural_elements.get("has_feedback_loop")
                and structural_elements.get("has_audience_adaptation")
            )
        ):
            level = "L3"
        elif (
            rubric_match_scores["L2"] > 0
            or (
                structural_elements.get("has_message_clarity")
                and (structural_elements.get("has_alignment") or structural_elements.get("has_questions"))
            )
        ):
            level = "L2"
        elif rubric_match_scores["L1"] > 0 or structural_elements.get("has_message_clarity"):
            level = "L1"
        else:
            level = "N/A"

        if not red_flags or level == "N/A":
            level = self._adjust_level_by_structure(
                level=level,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
            )
            return self._adjust_level_by_artifact(
                level=level,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=missing_artifact_parts,
            )
        hard_red_flags = [flag for flag in red_flags if flag in self._hard_red_flags()]
        if len(hard_red_flags) >= 2:
            return "N/A"
        if hard_red_flags:
            level = {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
        level = self._adjust_level_by_structure(
            level=level,
            block_coverage_percent=block_coverage_percent,
            missing_required_blocks=missing_required_blocks,
        )
        return self._adjust_level_by_artifact(
            level=level,
            artifact_compliance_percent=artifact_compliance_percent,
            missing_artifact_parts=missing_artifact_parts,
        )


class TeamworkAgent(BaseCompetencyAgent):
    def __init__(self) -> None:
        super().__init__("Командная работа", "teamwork")

    def _extract_structural_elements(self, user_text: str, case_payload: list[dict[str, Any]]) -> dict[str, bool]:
        elements = super()._extract_structural_elements(user_text, case_payload)
        normalized = self.normalize_text(user_text)
        elements.update(
            {
                "has_role_distribution": any(word in normalized for word in ("роль", "ответствен", "зона ответственности", "распредел")),
                "has_involvement": any(word in normalized for word in ("подключ", "вовлек", "собер", "участник", "команд")),
                "has_support": any(word in normalized for word in ("помочь", "поддерж", "снять блокер", "разрешить конфликт")),
                "has_team_safety": any(word in normalized for word in ("довер", "безопас", "открыт", "без обвинений")),
            }
        )
        return elements

    def _detect_red_flags(
        self,
        user_text: str,
        case_payload: list[dict[str, Any]],
        structural_elements: dict[str, bool],
    ) -> list[str]:
        flags = super()._detect_red_flags(user_text, case_payload, structural_elements)
        normalized = self.normalize_text(user_text)
        if any(phrase in normalized for phrase in ("сделаю сам", "команда не нужна", "не буду никого подключать")):
            flags.append("solo_mode")
        if any(phrase in normalized for phrase in ("обвин", "виноват", "накажу", "прижму")):
            flags.append("unsafe_team_climate")
        return flags

    def _determine_level(
        self,
        *,
        user_text: str,
        structural_elements: dict[str, bool],
        rubric_match_scores: dict[str, int],
        red_flags: list[str],
        block_coverage_percent: int | None,
        missing_required_blocks: list[str],
        artifact_compliance_percent: int | None,
        missing_artifact_parts: list[str],
    ) -> str:
        if not self.normalize_text(user_text):
            return "N/A"
        if (
            rubric_match_scores["L3"] > 0
            or (
                structural_elements.get("has_role_distribution")
                and structural_elements.get("has_involvement")
                and structural_elements.get("has_support")
                and structural_elements.get("has_team_safety")
            )
        ):
            level = "L3"
        elif (
            rubric_match_scores["L2"] > 0
            or (
                structural_elements.get("has_role_distribution")
                and structural_elements.get("has_involvement")
            )
        ):
            level = "L2"
        elif rubric_match_scores["L1"] > 0 or structural_elements.get("has_involvement"):
            level = "L1"
        else:
            level = "N/A"

        if not red_flags or level == "N/A":
            level = self._adjust_level_by_structure(
                level=level,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
            )
            return self._adjust_level_by_artifact(
                level=level,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=missing_artifact_parts,
            )
        hard_red_flags = [flag for flag in red_flags if flag in self._hard_red_flags()]
        if len(hard_red_flags) >= 2:
            return "N/A"
        if hard_red_flags:
            level = {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
        level = self._adjust_level_by_structure(
            level=level,
            block_coverage_percent=block_coverage_percent,
            missing_required_blocks=missing_required_blocks,
        )
        return self._adjust_level_by_artifact(
            level=level,
            artifact_compliance_percent=artifact_compliance_percent,
            missing_artifact_parts=missing_artifact_parts,
        )


class CreativityAgent(BaseCompetencyAgent):
    def __init__(self) -> None:
        super().__init__("Креативность", "creativity")

    def _extract_structural_elements(self, user_text: str, case_payload: list[dict[str, Any]]) -> dict[str, bool]:
        elements = super()._extract_structural_elements(user_text, case_payload)
        normalized = self.normalize_text(user_text)
        elements.update(
            {
                "has_originality": any(word in normalized for word in ("нестандарт", "оригин", "новый подход", "иначе")),
                "has_experiments": any(word in normalized for word in ("пилот", "эксперимент", "прототип", "проверим на части")),
                "has_reframing": any(word in normalized for word in ("переформулир", "посмотр", "с другой стороны", "переосмыс")),
                "has_combination": any(word in normalized for word in ("комбинир", "совмест", "сочет", "объединим")),
            }
        )
        elements["has_viable_idea"] = bool(
            elements.get("has_alternatives")
            or elements.get("has_originality")
            or elements.get("has_experiments")
            or elements.get("has_reframing")
            or elements.get("has_combination")
            or elements.get("covers_decision", False)
            or elements.get("covers_implementation_plan", False)
            or any(
                phrase in normalized
                for phrase in (
                    "предлага",
                    "можно сделать",
                    "идея",
                    "улучш",
                    "автоматиз",
                    "шаблон",
                    "чек-лист",
                    "дашборд",
                )
            )
        )
        return elements

    def _detect_red_flags(
        self,
        user_text: str,
        case_payload: list[dict[str, Any]],
        structural_elements: dict[str, bool],
    ) -> list[str]:
        flags = super()._detect_red_flags(user_text, case_payload, structural_elements)
        normalized = self.normalize_text(user_text)
        if any(phrase in normalized for phrase in ("только один вариант", "других вариантов нет", "не вижу смысла думать")):
            flags.append("no_alternatives")
        if any(phrase in normalized for phrase in ("всегда делали так", "как обычно", "стандартно и все")):
            flags.append("template_thinking")
        return flags

    def _determine_level(
        self,
        *,
        user_text: str,
        structural_elements: dict[str, bool],
        rubric_match_scores: dict[str, int],
        red_flags: list[str],
        block_coverage_percent: int | None,
        missing_required_blocks: list[str],
        artifact_compliance_percent: int | None,
        missing_artifact_parts: list[str],
    ) -> str:
        normalized = self.normalize_text(user_text)
        if not normalized:
            return "N/A"
        has_viable_idea = bool(structural_elements.get("has_viable_idea"))
        has_realization_signal = bool(
            structural_elements.get("has_experiments")
            or structural_elements.get("covers_implementation_plan", False)
            or structural_elements.get("covers_success_metric", False)
            or structural_elements.get("has_next_step")
        )
        if (
            rubric_match_scores["L3"] > 0
            or (
                structural_elements.get("has_originality")
                and structural_elements.get("has_experiments")
                and structural_elements.get("has_reframing")
            )
        ):
            level = "L3"
        elif (
            rubric_match_scores["L2"] > 0
            or (
                has_viable_idea
                and (
                    structural_elements.get("has_alternatives")
                    or structural_elements.get("has_originality")
                    or structural_elements.get("has_combination")
                )
                and (structural_elements.get("has_criteria") or has_realization_signal)
            )
        ):
            level = "L2"
        elif rubric_match_scores["L1"] > 0 or has_viable_idea:
            level = "L1"
        else:
            level = "N/A"

        if not red_flags or level == "N/A":
            level = self._adjust_level_by_structure(
                level=level,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
            )
            level = self._adjust_level_by_artifact(
                level=level,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=missing_artifact_parts,
            )
        else:
            hard_red_flags = [flag for flag in red_flags if flag in self._hard_red_flags()]
            if len(hard_red_flags) >= 2:
                return "N/A"
            if hard_red_flags:
                level = {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
            level = self._adjust_level_by_structure(
                level=level,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
            )
            level = self._adjust_level_by_artifact(
                level=level,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=missing_artifact_parts,
            )

        if level == "N/A" and has_viable_idea and not any(
            flag in {"aggressive_tone", "responsibility_shift", "template_thinking"}
            for flag in red_flags
        ):
            return "L1"
        return level


class CriticalThinkingAgent(BaseCompetencyAgent):
    def __init__(self) -> None:
        super().__init__("Критическое мышление", "critical_thinking")

    def _extract_structural_elements(self, user_text: str, case_payload: list[dict[str, Any]]) -> dict[str, bool]:
        elements = super()._extract_structural_elements(user_text, case_payload)
        normalized = self.normalize_text(user_text)
        elements.update(
            {
                "has_hypotheses": any(word in normalized for word in ("гипотез", "предполож", "проверю гипотезу")),
                "has_data_reference": any(word in normalized for word in ("данн", "факт", "цифр", "метрик", "показател")),
                "has_tradeoffs": any(word in normalized for word in ("компромисс", "цена", "последств", "trade-off", "выигрыш")),
                "has_validation": any(word in normalized for word in ("провер", "валид", "свер", "сравн", "контрольная точка")),
            }
        )
        elements["has_practical_reasoning"] = bool(
            (
                elements.get("has_next_step")
                or elements.get("covers_next_step", False)
                or elements.get("covers_decision", False)
            )
            and (
                elements.get("has_risks")
                or elements.get("has_questions")
                or elements.get("has_validation")
                or elements.get("has_data_reference")
                or elements.get("has_predictive")
                or elements.get("covers_facts", False)
            )
        )
        return elements

    def _detect_red_flags(
        self,
        user_text: str,
        case_payload: list[dict[str, Any]],
        structural_elements: dict[str, bool],
    ) -> list[str]:
        flags = super()._detect_red_flags(user_text, case_payload, structural_elements)
        normalized = self.normalize_text(user_text)
        if any(phrase in normalized for phrase in ("без проверки", "и так понятно", "не нужно анализировать")):
            flags.append("no_validation")
        if any(phrase in normalized for phrase in ("неважно какие риски", "риски несущественны")):
            flags.append("risk_blindness")
        return flags

    def _determine_level(
        self,
        *,
        user_text: str,
        structural_elements: dict[str, bool],
        rubric_match_scores: dict[str, int],
        red_flags: list[str],
        block_coverage_percent: int | None,
        missing_required_blocks: list[str],
        artifact_compliance_percent: int | None,
        missing_artifact_parts: list[str],
    ) -> str:
        normalized = self.normalize_text(user_text)
        if not normalized:
            return "N/A"
        has_practical_reasoning = bool(structural_elements.get("has_practical_reasoning"))
        if (
            rubric_match_scores["L3"] > 0
            or (
                structural_elements.get("has_hypotheses")
                and structural_elements.get("has_tradeoffs")
                and structural_elements.get("has_validation")
                and structural_elements.get("has_predictive")
            )
        ):
            level = "L3"
        elif (
            rubric_match_scores["L2"] > 0
            or (
                (
                    structural_elements.get("has_criteria")
                    or structural_elements.get("covers_decision", False)
                    or structural_elements.get("has_next_step")
                )
                and (
                    structural_elements.get("has_risks")
                    or structural_elements.get("has_validation")
                    or structural_elements.get("has_data_reference")
                    or structural_elements.get("has_predictive")
                )
            )
        ):
            level = "L2"
        elif (
            rubric_match_scores["L1"] > 0
            or structural_elements.get("has_criteria")
            or structural_elements.get("has_data_reference")
            or has_practical_reasoning
        ):
            level = "L1"
        else:
            level = "N/A"

        if not red_flags or level == "N/A":
            level = self._adjust_level_by_structure(
                level=level,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
            )
            level = self._adjust_level_by_artifact(
                level=level,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=missing_artifact_parts,
            )
        else:
            hard_red_flags = [flag for flag in red_flags if flag in self._hard_red_flags()]
            if len(hard_red_flags) >= 2:
                return "N/A"
            if hard_red_flags:
                level = {"L3": "L2", "L2": "L1", "L1": "L1"}.get(level, level)
            level = self._adjust_level_by_structure(
                level=level,
                block_coverage_percent=block_coverage_percent,
                missing_required_blocks=missing_required_blocks,
            )
            level = self._adjust_level_by_artifact(
                level=level,
                artifact_compliance_percent=artifact_compliance_percent,
                missing_artifact_parts=missing_artifact_parts,
            )

        if level == "N/A" and has_practical_reasoning and not any(
            flag in {"aggressive_tone", "responsibility_shift", "risk_blindness", "no_validation"}
            for flag in red_flags
        ):
            return "L1"
        return level


communication_agent = CommunicationAgent()
teamwork_agent = TeamworkAgent()
creativity_agent = CreativityAgent()
critical_thinking_agent = CriticalThinkingAgent()

competency_assessment_agents = (
    communication_agent,
    teamwork_agent,
    creativity_agent,
    critical_thinking_agent,
)
