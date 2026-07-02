from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from Api.case_context_builder import build_case_context
from Api.communication_agent import competency_assessment_agents
from Api.database import get_case_methodology_versions, get_connection
from Api.deepseek_client import DeepSeekTurnResult, deepseek_client
from Api.mbti.service import mbti_assessment_service
from Api.progress_service import operation_progress_service
from Api.schemas import UserResponse


@dataclass(slots=True)
class AssessmentSessionPlan:
    session_id: int
    session_code: str
    current_session_case_id: int | None
    current_case_title: str | None
    current_case_number: int
    total_cases: int
    current_case_time_limit_minutes: int | None
    current_case_planned_duration_minutes: int | None
    current_case_started_at: datetime | None
    opening_message: str | None


@dataclass(slots=True)
class AssessmentTurnReply:
    session_code: str
    session_id: int
    session_case_id: int | None
    case_title: str | None
    case_number: int
    total_cases: int
    message: str
    case_completed: bool
    assessment_completed: bool
    result_status: str | None = None
    completion_score: float | None = None
    evaluator_summary: str | None = None
    case_time_limit_minutes: int | None = None
    planned_case_duration_minutes: int | None = None
    case_started_at: datetime | None = None
    case_time_remaining_seconds: int | None = None
    time_expired: bool = False
    history_match_case: bool = False
    history_match_case_text: bool = False
    history_match_type: bool = False
    history_last_used_at: datetime | None = None
    history_use_count: int = 0
    history_flag: str | None = None
    history_is_new: bool = False
    is_dialog_case: bool = False
    pending_auto_finish: bool = False
    auto_finish_delay_ms: int | None = None
    mbti_case_result: dict[str, object] | None = None
    mbti_followup_questions: list[str] | None = None
    mbti_followup_pending: bool = False
    mbti_followup_index: int | None = None
    mbti_followup_total: int | None = None
    mbti_summary: dict[str, object] | None = None


class AssessmentService:
    RECENT_CASE_DAYS = 30
    MIN_SESSION_DURATION_MIN = 55
    MAX_SESSION_DURATION_MIN = 70
    CASE_MESSAGE_LIMIT_REACHED_TEXT = "Лимит сообщений по этому кейсу достигнут. Мы фиксируем ваш ответ и завершаем кейс."
    CASE_FINISH_CONFIRMATION_TEXT = (
        "Понял. Если вы хотите завершить этот кейс сейчас, подтвердите это следующим сообщением. "
        "Если готовы продолжать, просто напишите, что продолжаем."
    )
    CASE_CONTINUE_AFTER_CONFIRMATION_TEXT = "Хорошо, продолжаем диалог. Дайте ваш ответ по ситуации в удобной для вас форме."
    MBTI_FOLLOWUP_INTRO_TEXT = "Прежде чем перейти к следующему кейсу, ответьте, пожалуйста, на уточняющие вопросы по только что завершенному кейсу."
    MBTI_FOLLOWUP_COMPLETE_TEXT = "Спасибо, уточнения по кейсу зафиксированы."
    CASE_AUTO_FINISH_DELAY_MS = 2200
    MIN_FIRST_CASE_ANSWER_WORDS = 9
    PROMPT_LAB_PREVIEW_CACHE_TTL_SECONDS = 600
    PROMPT_LAB_LLM_PERSONALIZATION_TIMEOUT_SECONDS = 45

    def __init__(self) -> None:
        self._prompt_lab_case_preview_cache: dict[str, tuple[datetime, dict]] = {}

    def _utc_now(self) -> datetime:
        return datetime.utcnow()

    def _get_is_dialog_case_for_session_case(self, connection, session_case_id: int | None) -> bool:
        if not session_case_id:
            return False
        case_row = self._get_case_for_session_case(connection, session_case_id)
        methodical_context = self._get_case_methodical_context(connection, case_row)
        return deepseek_client._is_dialog_interactivity_mode(methodical_context.get("interactivity_mode"))

    def _build_prompt_lab_case_preview_cache_key(
        self,
        *,
        user_id: int,
        case_id_code: str,
        use_llm_personalization: bool = True,
        case_generation_system_prompt: str | None = None,
        full_name: str | None = None,
        role_id: int | None = None,
        position: str | None = None,
        duties: str | None = None,
        company_industry: str | None = None,
        user_profile_override: dict | None = None,
    ) -> str:
        payload = {
            "user_id": int(user_id or 0),
            "case_id_code": str(case_id_code or "").strip(),
            "use_llm_personalization": bool(use_llm_personalization),
            "case_generation_system_prompt": str(case_generation_system_prompt or "").strip(),
            "full_name": str(full_name or "").strip(),
            "role_id": int(role_id or 0),
            "position": str(position or "").strip(),
            "duties": str(duties or "").strip(),
            "company_industry": str(company_industry or "").strip(),
            "user_profile_override": user_profile_override or {},
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)

    def _get_cached_prompt_lab_case_preview(self, cache_key: str) -> dict | None:
        cached = self._prompt_lab_case_preview_cache.get(cache_key)
        if not cached:
            return None
        cached_at, payload = cached
        if (self._utc_now() - cached_at).total_seconds() > self.PROMPT_LAB_PREVIEW_CACHE_TTL_SECONDS:
            self._prompt_lab_case_preview_cache.pop(cache_key, None)
            return None
        return copy.deepcopy(payload)

    def _set_cached_prompt_lab_case_preview(self, cache_key: str, payload: dict) -> None:
        self._prompt_lab_case_preview_cache[cache_key] = (self._utc_now(), copy.deepcopy(payload))

    def _calculate_actual_duration_seconds(self, started_at: datetime | None, completed_at: datetime | None) -> int:
        if started_at is None or completed_at is None:
            return 0
        return max(0, int((completed_at - started_at).total_seconds()))

    def _normalize_message_for_repeat_check(self, text: str | None) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        normalized = re.sub(r"[^\wа-яё0-9\s]", "", normalized, flags=re.IGNORECASE)
        return normalized.strip()

    def _is_finish_confirmation_prompt(self, text: str | None) -> bool:
        return self._normalize_message_for_repeat_check(text) == self._normalize_message_for_repeat_check(
            self.CASE_FINISH_CONFIRMATION_TEXT
        )

    def _looks_like_finish_confirmation(self, text: str | None) -> bool:
        normalized = self._normalize_message_for_repeat_check(text)
        if not normalized:
            return False
        confirmation_markers = (
            "да",
            "да завершаем",
            "завершаем",
            "подтверждаю",
            "закрываем кейс",
            "завершить кейс",
            "можно завершить",
            "заканчиваем",
            "остановимся",
            "да остановимся",
        )
        return any(marker in normalized for marker in confirmation_markers)

    def _looks_like_continue_after_confirmation(self, text: str | None) -> bool:
        normalized = self._normalize_message_for_repeat_check(text)
        if not normalized:
            return False
        continue_markers = (
            "нет",
            "не завершаем",
            "продолжаем",
            "давай продолжим",
            "давайте продолжим",
            "идем дальше",
            "идём дальше",
            "продолжим",
        )
        return any(marker in normalized for marker in continue_markers)

    def _looks_like_explicit_finish_request(self, text: str | None) -> bool:
        normalized = self._normalize_message_for_repeat_check(text)
        if not normalized:
            return False
        explicit_markers = (
            "хочу завершить кейс",
            "хочу завершить",
            "завершить кейс",
            "заверши кейс",
            "завершай кейс",
            "закончить кейс",
            "закрыть кейс",
            "не хочу проходить",
            "не хочу проходить кейс",
            "не буду проходить",
            "не буду проходить кейс",
        )
        return any(marker in normalized for marker in explicit_markers)

    def _looks_like_defer_or_refusal(self, text: str | None) -> bool:
        normalized = self._normalize_message_for_repeat_check(text)
        if not normalized:
            return False
        markers = (
            "позже",
            "потом",
            "не хочу отвечать",
            "не буду отвечать",
            "не готов отвечать",
            "не готов сейчас",
            "давайте позже",
            "вернусь позже",
            "пока не отвечу",
            "не хочу сейчас",
            "не могу сейчас ответить",
            "не могу сейчас",
            "пропущу",
            "не хочу продолжать",
            "остановимся на этом",
            "не знаю",
            "затрудняюсь ответить",
            "затрудняюсь",
            "пропущу этот вопрос",
            "не готов продолжать",
            "не хочу дальше",
            "не хочу обсуждать",
            "не буду сейчас отвечать",
            "вернемся позже",
            "вернёмся позже",
            "давайте вернемся позже",
            "давайте вернёмся позже",
        )
        return any(marker in normalized for marker in markers)

    def _build_non_repeating_follow_up(
        self,
        *,
        repeated_message: str,
        user_message: str,
        dialogue_rows,
        case_skills: list[str],
        interactivity_mode: str | None = None,
    ) -> str:
        previous_assistant_messages = [
            str(row["message_text"] or "").strip()
            for row in dialogue_rows
            if row["role"] == "assistant" and str(row["message_text"] or "").strip()
        ]
        previous_normalized = {
            self._normalize_message_for_repeat_check(item)
            for item in previous_assistant_messages
        }
        previous_topics = [
            deepseek_client._infer_follow_up_topics_from_text(item)
            for item in previous_assistant_messages[-3:]
        ]
        candidates = [
            deepseek_client._build_follow_up_question(
                user_message=user_message,
                dialogue=[{"role": row["role"], "content": row["message_text"]} for row in dialogue_rows],
                case_skills=case_skills,
            ),
            "Что в вашем решении будет самым рискованным местом на практике и как вы это заранее проверите?",
            "Как вы поймете, что решение действительно работает, и какие сигналы покажут, что его нужно корректировать?",
            "Какие шаги вы бы сделали в первую очередь после запуска решения, чтобы не потерять контроль над ситуацией?",
            "Кого вы бы вовлекли в реализацию этого решения и как распределили бы ответственность между участниками?",
        ]
        repeated_normalized = self._normalize_message_for_repeat_check(repeated_message)
        for candidate in candidates:
            candidate_normalized = self._normalize_message_for_repeat_check(candidate)
            candidate_topics = deepseek_client._infer_follow_up_topics_from_text(candidate)
            if candidate_normalized == repeated_normalized:
                continue
            if candidate_normalized in previous_normalized:
                continue
            if candidate_topics and any(candidate_topics & topic_set for topic_set in previous_topics if topic_set):
                continue
            return candidate
        return "Уточните, пожалуйста, какие контрольные точки и критерии пересмотра решения вы бы зафиксировали."

    def _looks_like_thin_case_answer(self, message: str | None) -> bool:
        normalized = str(message or "").strip().lower()
        if not normalized:
            return True
        words = re.findall(r"[a-zа-яё0-9]+", normalized, flags=re.IGNORECASE)
        if len(words) < self.MIN_FIRST_CASE_ANSWER_WORDS:
            return True
        generic_markers = (
            "разобрался",
            "разберусь",
            "решил проблему",
            "решу проблему",
            "исправил бы",
            "исправлю",
            "сделал бы все",
            "сделаю все",
            "поговорил бы",
            "уточнил бы",
            "надо разобраться",
            "нужно разобраться",
            "все решим",
            "решим вопрос",
            "решить вопрос",
        )
        if any(marker in normalized for marker in generic_markers) and len(words) < 18:
            return True
        evidence_markers = (
            "риск",
            "метрик",
            "kpi",
            "срок",
            "ответствен",
            "приоритет",
            "эскалац",
            "данн",
            "провер",
            "контрол",
            "клиент",
            "команд",
            "участник",
            "результат",
            "план",
            "шаг",
        )
        if len(words) < 14 and not any(marker in normalized for marker in evidence_markers):
            return True
        return False

    def _build_thin_case_answer_follow_up(self, *, user_message: str, dialogue_rows, case_skills: list[str]) -> str:
        follow_up = self._build_non_repeating_follow_up(
            repeated_message="",
            user_message=user_message,
            dialogue_rows=dialogue_rows,
            case_skills=case_skills,
        )
        if "кей" in follow_up.lower():
            return follow_up
        return "По текущему кейсу уточните, пожалуйста: " + follow_up[:1].lower() + follow_up[1:]

    def _has_same_follow_up_topic(self, current_message: str | None, previous_message: str | None) -> bool:
        current_topics = deepseek_client._infer_follow_up_topics_from_text(current_message)
        previous_topics = deepseek_client._infer_follow_up_topics_from_text(previous_message)
        if not current_topics or not previous_topics:
            return False
        return bool(current_topics & previous_topics)

    def _needs_non_repeating_follow_up(self, current_message: str | None, dialogue_rows) -> bool:
        assistant_rows = [
            row for row in dialogue_rows
            if row["role"] == "assistant" and str(row["message_text"] or "").strip()
        ]
        if not assistant_rows:
            return False
        current_normalized = self._normalize_message_for_repeat_check(current_message)
        current_topics = deepseek_client._infer_follow_up_topics_from_text(current_message)
        current_dialog_stages = deepseek_client._infer_dialog_reply_stages(current_message)
        recent_assistant_rows = assistant_rows[-3:]
        for row in recent_assistant_rows:
            previous_text = str(row["message_text"] or "")
            if current_normalized == self._normalize_message_for_repeat_check(previous_text):
                return True
            previous_dialog_stages = deepseek_client._infer_dialog_reply_stages(previous_text)
            if current_dialog_stages and previous_dialog_stages and (current_dialog_stages & previous_dialog_stages):
                return True
            previous_topics = deepseek_client._infer_follow_up_topics_from_text(previous_text)
            if current_topics and previous_topics and (current_topics & previous_topics):
                return True
        return False

    def ensure_assessment_session(self, user: UserResponse, progress_operation_id: str | None = None) -> AssessmentSessionPlan | None:
        if not user.id:
            raise ValueError("Пользователь не найден.")
        if not user.role_id:
            raise ValueError("Для пользователя не определена роль. Завершите настройку профиля и выберите роль.")

        with get_connection() as connection:
            operation_progress_service.advance(
                progress_operation_id,
                0,
                title="Проверяем профиль оценки",
                message="Уточняем роль пользователя и состояние активной assessment-сессии.",
            )
            existing = connection.execute(
                """
                SELECT id, session_code
                FROM user_sessions
                WHERE user_id = %s
                  AND assessment_code = 'competencies_4k'
                  AND status IN ('created', 'active')
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (user.id,),
            ).fetchone()

            if existing is not None:
                repaired_existing = self._repair_existing_session(
                    connection=connection,
                    user=user,
                    session_id=existing["id"],
                    session_code=existing["session_code"],
                    progress_operation_id=progress_operation_id,
                )
                if repaired_existing is not None:
                    repaired_session_id, repaired_session_code = repaired_existing
                    operation_progress_service.advance(
                        progress_operation_id,
                        4,
                        title="Подготавливаем интервью",
                        message="Существующая assessment-сессия восстановлена и готова к продолжению.",
                    )
                    return self._build_plan(connection, repaired_session_id, repaired_session_code)

            passed_case_rows = connection.execute(
                """
                SELECT DISTINCT sc.case_registry_id
                FROM session_case_results scr
                JOIN session_cases sc ON sc.id = scr.session_case_id
                WHERE scr.user_id = %s
                  AND scr.result_status = 'passed'
                  AND sc.case_registry_id IS NOT NULL
                """,
                (user.id,),
            ).fetchall()
            passed_case_ids = [row["case_registry_id"] for row in passed_case_rows]

            required_rows = connection.execute(
                """
                SELECT skill_id
                FROM role_skills
                WHERE role_id = %s
                  AND is_required = TRUE
                ORDER BY skill_id ASC
                """,
                (user.role_id,),
            ).fetchall()
            required_skill_ids = [row["skill_id"] for row in required_rows]
            if not required_skill_ids:
                raise ValueError("Для выбранной роли не настроены обязательные навыки. Обратитесь к администратору системы.")

            operation_progress_service.advance(
                progress_operation_id,
                1,
                title="Подбираем релевантные кейсы",
                message="Подбираем кейсы по обязательным навыкам роли и истории пользователя.",
            )
            candidate_rows = self._load_candidate_case_rows(
                connection=connection,
                role_id=user.role_id,
                required_skill_ids=required_skill_ids,
                excluded_case_ids=passed_case_ids,
            )

            candidate_case_pool_with_history_flags = self._enrich_candidate_case_pool_with_history(
                connection=connection,
                user_id=user.id,
                candidate_rows=candidate_rows,
            )

            selected_cases = self._select_minimum_cases(candidate_case_pool_with_history_flags, required_skill_ids)
            if not selected_cases:
                retry_candidate_rows = self._load_candidate_case_rows(
                    connection=connection,
                    role_id=user.role_id,
                    required_skill_ids=required_skill_ids,
                    excluded_case_ids=[],
                )
                retry_candidate_pool = self._enrich_candidate_case_pool_with_history(
                    connection=connection,
                    user_id=user.id,
                    candidate_rows=retry_candidate_rows,
                )
                selected_cases = self._select_minimum_cases(retry_candidate_pool, required_skill_ids)
            if not selected_cases:
                raise ValueError("Для выбранной роли не найдено доступных кейсов для запуска ассессмента.")

            session = connection.execute(
                """
                INSERT INTO user_sessions (session_code, user_id, role_id, assessment_code, status, source, notes)
                VALUES (%s, %s, %s, 'competencies_4k', 'created', 'auto', 'Session generated after role detection')
                RETURNING id, session_code
                """,
                (uuid4().hex, user.id, user.role_id),
            ).fetchone()
            session_id = session["id"]
            session_code = session["session_code"]

            for skill_id in required_skill_ids:
                connection.execute(
                    """
                    INSERT INTO session_skills (session_id, skill_id, status, assigned_case_count, completed_case_count)
                    VALUES (%s, %s, 'planned', 0, 0)
                    ON CONFLICT (session_id, skill_id) DO NOTHING
                    """,
                    (session_id, skill_id),
                )

            role_row = connection.execute(
                "SELECT name FROM roles WHERE id = %s",
                (user.role_id,),
            ).fetchone()
            role_name = role_row["name"] if role_row else None
            profile_row = connection.execute(
                """
                SELECT *
                FROM user_role_profiles
                WHERE id = %s
                """,
                (user.active_profile_id,),
            ).fetchone() if user.active_profile_id else None
            user_profile = dict(profile_row) if profile_row else None

            operation_progress_service.advance(
                progress_operation_id,
                2,
                title="Собираем черновик сессии",
                message="Создаем assessment-сессию и фиксируем выбранные кейсы в базе данных.",
            )
            prepared_session_cases: list[tuple[int, dict]] = []
            for index, case_row in enumerate(selected_cases, start=1):
                methodology_versions = get_case_methodology_versions(connection, int(case_row["id"]))
                session_case = connection.execute(
                    """
                    INSERT INTO session_cases (
                        session_id, user_id, role_id, case_registry_id, status, selection_reason,
                        planned_duration_minutes,
                        case_registry_version, case_text_version, case_type_passport_version,
                        required_blocks_version, red_flags_version, skill_evidence_version,
                        difficulty_modifiers_version, personalization_fields_version,
                        history_match_case, history_match_case_text, history_match_type,
                        history_last_used_at, history_use_count, history_flag, history_is_new
                    )
                    VALUES (
                        %s, %s, %s, %s, 'selected', %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        session_id,
                        user.id,
                        user.role_id,
                        case_row["id"],
                        f"Auto-selected for skill coverage. Case order #{index}.",
                        case_row["planned_duration_minutes"] or case_row["estimated_minutes"],
                        methodology_versions["case_registry_version"],
                        methodology_versions["case_text_version"],
                        methodology_versions["case_type_passport_version"],
                        methodology_versions["required_blocks_version"],
                        methodology_versions["red_flags_version"],
                        methodology_versions["skill_evidence_version"],
                        methodology_versions["difficulty_modifiers_version"],
                        methodology_versions["personalization_fields_version"],
                        case_row.get("history_match_case", False),
                        case_row.get("history_match_case_text", False),
                        case_row.get("history_match_type", False),
                        case_row.get("last_used_at"),
                        case_row.get("use_count", 0),
                        case_row.get("history_flag", "new"),
                        case_row.get("history_flag", "new") == "new",
                    ),
                ).fetchone()
                session_case_id = session_case["id"]
                connection.execute(
                    """
                    UPDATE session_cases
                    SET status = 'sent_to_personalization'
                    WHERE id = %s
                    """,
                    (session_case_id,),
                )
                connection.execute(
                    """
                    INSERT INTO user_case_assignments (
                        user_id, role_id, case_registry_id, status, selection_reason
                    )
                    VALUES (%s, %s, %s, 'selected', %s)
                    ON CONFLICT (user_id, case_registry_id) DO NOTHING
                    """,
                    (
                        user.id,
                        user.role_id,
                        case_row["id"],
                        "Automatically assigned for competencies_4k assessment.",
                    ),
                )

                for skill_id in case_row["skill_ids"]:
                    connection.execute(
                        """
                        INSERT INTO session_case_skills (session_case_id, skill_id, coverage_status)
                        VALUES (%s, %s, 'planned')
                        ON CONFLICT (session_case_id, skill_id) DO NOTHING
                    """,
                    (session_case_id, skill_id),
                )
                    connection.execute(
                        """
                        INSERT INTO user_skill_coverage (
                            user_id, role_id, skill_id, source_case_registry_id, status
                        )
                        VALUES (%s, %s, %s, %s, 'planned')
                        ON CONFLICT (user_id, skill_id, source_case_registry_id) DO NOTHING
                        """,
                        (user.id, user.role_id, skill_id, case_row["id"]),
                    )

                prepared_session_cases.append((session_case_id, dict(case_row)))

            connection.execute(
                """
                UPDATE session_skills ss
                SET assigned_case_count = summary.case_count
                FROM (
                    SELECT sc.session_id, scs.skill_id, COUNT(*)::int AS case_count
                    FROM session_cases sc
                    JOIN session_case_skills scs ON scs.session_case_id = sc.id
                    WHERE sc.session_id = %s
                    GROUP BY sc.session_id, scs.skill_id
                ) AS summary
                WHERE ss.session_id = summary.session_id
                  AND ss.skill_id = summary.skill_id
                """,
                (session_id,),
            )
            connection.commit()

            operation_progress_service.advance(
                progress_operation_id,
                3,
                title="Персонализируем материалы",
                message="Готовим персонализированный контекст и промты для каждого кейса.",
            )
            used_case_signatures: list[dict[str, str]] = []
            for session_case_id, case_row in prepared_session_cases:
                try:
                    connection.execute(
                        """
                        UPDATE session_cases
                        SET status = 'sent_to_personalization'
                        WHERE id = %s
                        """,
                        (session_case_id,),
                    )
                    self._upsert_session_case_prompt(
                        connection=connection,
                        user=user,
                        session_id=session_id,
                        session_case_id=session_case_id,
                        case_row=case_row,
                        role_name=role_name,
                        user_profile=user_profile,
                        skill_names=[name for name in case_row["skill_names"] if name],
                        progress_operation_id=progress_operation_id,
                        used_case_signatures=used_case_signatures,
                    )
                    if user_profile:
                        prioritize_runtime_domain = deepseek_client._should_prioritize_runtime_domain(
                            position=user.raw_position or user.job_description,
                            duties=user.normalized_duties or user.raw_duties,
                            company_industry=user.company_industry,
                        )
                        preview_domain_family = (
                            deepseek_client._detect_domain_family(
                                position=user.raw_position or user.job_description,
                                duties=user.normalized_duties or user.raw_duties,
                                company_industry=user.company_industry,
                            )
                            if prioritize_runtime_domain
                            else str(
                                (user_profile.get("user_context_vars") or {}).get("domain_family")
                                or (user_profile.get("user_context_vars") or {}).get("domain_code")
                                or user_profile.get("user_domain")
                                or ""
                            )
                        )
                        case_specificity = deepseek_client.generate_case_specificity(
                            position=user.raw_position or user.job_description,
                            duties=user.normalized_duties or user.raw_duties,
                            company_industry=user.company_industry,
                            role_name=role_name,
                            user_profile=user_profile,
                            case_type_code=case_row["type_code"],
                            case_title=case_row["title"],
                            case_context=case_row["intro_context"] or case_row["domain_context"] or "",
                            case_task=case_row["task_for_user"] or "",
                        )
                        case_specificity = dict(case_specificity or {})
                        case_specificity["_used_case_signatures"] = [dict(item) for item in used_case_signatures]
                        preview_frame = build_case_context(
                            domain_family=preview_domain_family,
                            case_type_code=case_row["type_code"],
                            profile_processes=None if prioritize_runtime_domain else user_profile.get("user_processes"),
                            profile_tasks=None if prioritize_runtime_domain else user_profile.get("user_tasks"),
                            profile_stakeholders=None if prioritize_runtime_domain else user_profile.get("user_stakeholders"),
                            profile_risks=None if prioritize_runtime_domain else user_profile.get("user_risks"),
                            profile_constraints=None if prioritize_runtime_domain else user_profile.get("user_constraints"),
                            profile_systems=None if prioritize_runtime_domain else user_profile.get("user_systems"),
                            profile_artifacts=None if prioritize_runtime_domain else user_profile.get("user_artifacts"),
                            case_specificity=case_specificity,
                        )
                        used_case_signatures.append(
                            {
                                "case_type_code": str(case_row["type_code"] or ""),
                                "situation_code": str(preview_frame.get("situation_code") or ""),
                                "scene_theme": str(preview_frame.get("scene_theme") or ""),
                                "incident_title": str(preview_frame.get("incident_title") or ""),
                                "problem_event": str(preview_frame.get("problem_event") or ""),
                            }
                        )
                    connection.execute(
                        """
                        UPDATE session_cases
                        SET status = 'personalized'
                        WHERE id = %s
                        """,
                        (session_case_id,),
                    )
                    connection.commit()
                except Exception as exc:
                    self._archive_broken_session(
                        connection=connection,
                        session_id=session_id,
                        reason=f"prepare: prompt generation failed for session_case_id={session_case_id}: {exc.__class__.__name__}",
                    )
                    connection.commit()
                    raise

            connection.execute(
                "UPDATE user_sessions SET status = 'active' WHERE id = %s",
                (session_id,),
            )
            connection.commit()
            operation_progress_service.advance(
                progress_operation_id,
                4,
                title="Подготавливаем интервью",
                message="Оценочная сессия создана. Первый кейс готов к показу пользователю.",
            )
            return self._build_plan(connection, session_id, session_code)

    def _load_candidate_case_rows(self, *, connection, role_id: int, required_skill_ids: list[int], excluded_case_ids: list[int]):
        return connection.execute(
            """
            SELECT
                cr.id,
                cr.case_id_code AS case_code,
                COALESCE(txt.case_text_code, 'TXT-' || cr.case_id_code) AS text_code,
                p.type_code,
                cr.version AS case_registry_version,
                COALESCE(txt.version, 1) AS case_text_version,
                COALESCE(p.version, 1) AS case_type_passport_version,
                cr.title,
                txt.intro_context,
                txt.task_for_user,
                txt.facts_data,
                txt.trigger_details,
                txt.constraints_text,
                txt.stakes_text,
                txt.base_variant_text,
                txt.hard_variant_text,
                cr.context_domain AS domain_context,
                txt.personalization_variables,
                cr.estimated_time_min AS estimated_minutes,
                cr.estimated_time_min AS planned_duration_minutes,
                array_agg(crs.skill_id ORDER BY crs.display_order) AS skill_ids,
                array_agg(s.skill_name ORDER BY crs.display_order) AS skill_names
            FROM cases_registry cr
            JOIN case_type_passports p ON p.id = cr.case_type_passport_id
            JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
            JOIN case_registry_skills crs ON crs.cases_registry_id = cr.id
            JOIN skills s ON s.id = crs.skill_id
            LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
            WHERE crr.role_id = %s
              AND cr.status = 'ready'
              AND crs.skill_id = ANY(%s)
              AND (
                  COALESCE(array_length(%s::int[], 1), 0) = 0
                  OR cr.id::int != ALL(%s::int[])
              )
            GROUP BY
                cr.id,
                cr.case_id_code,
                txt.case_text_code,
                p.type_code,
                cr.version,
                txt.version,
                p.version,
                cr.title,
                txt.intro_context,
                txt.task_for_user,
                txt.facts_data,
                txt.trigger_details,
                txt.constraints_text,
                txt.stakes_text,
                txt.base_variant_text,
                txt.hard_variant_text,
                cr.context_domain,
                txt.personalization_variables,
                cr.estimated_time_min
            ORDER BY COUNT(crs.skill_id) DESC, cr.estimated_time_min ASC NULLS LAST, cr.id ASC
            """,
            (role_id, required_skill_ids, excluded_case_ids, excluded_case_ids),
        ).fetchall()

    def _repair_existing_session(
        self,
        *,
        connection,
        user: UserResponse,
        session_id: int,
        session_code: str,
        progress_operation_id: str | None = None,
    ) -> tuple[int, str] | None:
        case_rows = connection.execute(
            """
            SELECT
                sc.id,
                sc.status,
                sc.case_registry_id,
                cr.title,
                cr.case_id_code AS case_code,
                COALESCE(txt.case_text_code, 'TXT-' || cr.case_id_code) AS text_code,
                p.type_code,
                txt.intro_context,
                txt.task_for_user,
                txt.facts_data,
                txt.trigger_details,
                txt.constraints_text,
                txt.stakes_text,
                txt.base_variant_text,
                txt.hard_variant_text,
                cr.context_domain AS domain_context,
                txt.personalization_variables,
                cr.estimated_time_min AS estimated_minutes,
                COALESCE(sc.planned_duration_minutes, cr.estimated_time_min) AS planned_duration_minutes,
                EXISTS(
                    SELECT 1
                    FROM session_prompts sp
                    WHERE sp.session_case_id = sc.id
                      AND sp.prompt_type = 'case_dialog'
                ) AS has_prompt
            FROM session_cases sc
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            LEFT JOIN case_type_passports p ON p.id = cr.case_type_passport_id
            LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
            WHERE sc.session_id = %s
            ORDER BY sc.id ASC
            """,
            (session_id,),
        ).fetchall()

        if not case_rows:
            self._archive_broken_session(
                connection=connection,
                session_id=session_id,
                reason="repair: session has no cases",
            )
            connection.commit()
            return None

        open_case_rows = [row for row in case_rows if row["status"] not in {"answered", "assessed"}]
        if not open_case_rows:
            finished_at = self._utc_now()
            connection.execute(
                """
                UPDATE user_sessions
                SET status = 'completed',
                    finished_at = COALESCE(finished_at, %s),
                    notes = CONCAT(COALESCE(notes, ''), CASE WHEN COALESCE(notes, '') = '' THEN '' ELSE E'\\n' END, %s::text)
                WHERE id = %s
                """,
                (finished_at, "repair: session auto-completed because no open cases remain", session_id),
            )
            connection.commit()
            return None

        role_row = connection.execute(
            "SELECT name FROM roles WHERE id = %s",
            (user.role_id,),
        ).fetchone()
        role_name = role_row["name"] if role_row else None
        profile_row = connection.execute(
            """
            SELECT *
            FROM user_role_profiles
            WHERE id = %s
            """,
            (user.active_profile_id,),
        ).fetchone() if user.active_profile_id else None
        user_profile = dict(profile_row) if profile_row else None

        for row in open_case_rows:
            if row["has_prompt"]:
                continue
            operation_progress_service.advance(
                progress_operation_id,
                3,
                title="Генерируем промты интервью",
                message="Восстанавливаем недостающие системные промты для открытых кейсов.",
            )
            skill_rows = connection.execute(
                """
                SELECT s.skill_name
                FROM session_case_skills scs
                JOIN skills s ON s.id = scs.skill_id
                WHERE scs.session_case_id = %s
                ORDER BY s.id ASC
                """,
                (row["id"],),
            ).fetchall()
            self._upsert_session_case_prompt(
                connection=connection,
                user=user,
                session_id=session_id,
                session_case_id=row["id"],
                case_row=row,
                role_name=role_name,
                user_profile=user_profile,
                skill_names=[skill_row["skill_name"] for skill_row in skill_rows if skill_row["skill_name"]],
                progress_operation_id=progress_operation_id,
            )

        repaired_plan = self._build_plan(connection, session_id, session_code)
        if repaired_plan.current_session_case_id is None:
            finished_at = self._utc_now()
            connection.execute(
                """
                UPDATE user_sessions
                SET status = 'completed',
                    finished_at = COALESCE(finished_at, %s),
                    notes = CONCAT(COALESCE(notes, ''), CASE WHEN COALESCE(notes, '') = '' THEN '' ELSE E'\\n' END, %s::text)
                WHERE id = %s
                """,
                (finished_at, "repair: session finalized after integrity check", session_id),
            )
            connection.commit()
            return None

        current_prompt_row = connection.execute(
            """
            SELECT 1
            FROM session_prompts
            WHERE session_case_id = %s
              AND prompt_type = 'case_dialog'
            LIMIT 1
            """,
            (repaired_plan.current_session_case_id,),
        ).fetchone()
        if current_prompt_row is None:
            self._archive_broken_session(
                connection=connection,
                session_id=session_id,
                reason="repair: current case prompt missing after rebuild",
            )
            connection.commit()
            return None

        connection.commit()
        return (session_id, session_code)

    def _archive_broken_session(self, *, connection, session_id: int, reason: str) -> None:
        finished_at = self._utc_now()
        connection.execute(
            """
            UPDATE user_sessions
            SET status = 'failed',
                finished_at = COALESCE(finished_at, %s),
                notes = CONCAT(COALESCE(notes, ''), CASE WHEN COALESCE(notes, '') = '' THEN '' ELSE E'\\n' END, %s::text)
            WHERE id = %s
            """,
            (finished_at, reason, session_id),
        )

    def _upsert_session_case_prompt(
        self,
        *,
        connection,
        user: UserResponse,
        session_id: int,
        session_case_id: int,
        case_row,
        role_name: str | None,
        user_profile: dict | None,
        skill_names: list[str],
        progress_operation_id: str | None = None,
        used_case_signatures: list[dict[str, str]] | None = None,
    ) -> None:
        methodical_context = self._get_case_methodical_context(connection, case_row)
        planned_total_duration_min = case_row["planned_duration_minutes"] or case_row["estimated_minutes"]
        existing_case_contexts = self._get_existing_session_case_contexts(
            connection,
            session_id=session_id,
            session_case_id=session_case_id,
        )
        use_direct_deepseek_output = (
            deepseek_client.enabled
            and deepseek_client._should_use_llm_user_case_rewrite(case_type_code=case_row["type_code"])
        )
        if use_direct_deepseek_output:
            case_specificity = {}
        else:
            case_specificity = deepseek_client.generate_case_specificity(
                position=user.raw_position or user.job_description,
                duties=user.normalized_duties or user.raw_duties,
                company_industry=user.company_industry,
                role_name=role_name,
                user_profile=user_profile,
                case_type_code=case_row["type_code"],
                case_title=case_row["title"],
                case_context=case_row["intro_context"] or case_row["domain_context"] or "",
                case_task=case_row["task_for_user"] or "",
            )
            case_specificity = dict(case_specificity or {})
        case_specificity["_case_id_code"] = case_row.get("case_code")
        case_specificity["_facts_data"] = case_row.get("facts_data")
        case_specificity["_trigger_details"] = case_row.get("trigger_details")
        case_specificity["_constraints_text"] = case_row.get("constraints_text")
        case_specificity["_stakes_text"] = case_row.get("stakes_text")
        case_specificity["_base_variant_text"] = case_row.get("base_variant_text")
        case_specificity["_hard_variant_text"] = case_row.get("hard_variant_text")
        case_specificity["_used_case_signatures"] = [dict(item) for item in (used_case_signatures or [])]
        if use_direct_deepseek_output:
            personalization_map = {}
            personalized_context, personalized_task = deepseek_client._rewrite_user_case_materials_with_llm(
                case_id_code=case_row.get("case_code"),
                case_title=case_row["title"],
                case_type_code=case_row["type_code"],
                case_context=case_row["intro_context"] or case_row["domain_context"] or "",
                case_task=case_row["task_for_user"] or "",
                role_name=role_name,
                full_name=user.full_name,
                position=user.raw_position or user.job_description,
                duties=user.normalized_duties or user.raw_duties,
                company_industry=user.company_industry,
                user_profile=user_profile,
                facts_data=case_row.get("facts_data"),
                trigger_details=case_row.get("trigger_details"),
                constraints_text=case_row.get("constraints_text"),
                stakes_text=case_row.get("stakes_text"),
                base_variant_text=case_row.get("base_variant_text"),
                hard_variant_text=case_row.get("hard_variant_text"),
                personalization_variables=case_row.get("personalization_variables"),
            )
        else:
            personalization_map, personalized_context, personalized_task = deepseek_client.build_personalized_case_materials(
                full_name=user.full_name,
                position=user.raw_position or user.job_description,
                duties=user.normalized_duties or user.raw_duties,
                company_industry=user.company_industry,
                role_name=role_name,
                user_profile=user_profile,
                case_type_code=case_row["type_code"],
                case_title=case_row["title"],
                case_context=case_row["intro_context"] or case_row["domain_context"] or "",
                case_task=case_row["task_for_user"] or "",
                planned_total_duration_min=planned_total_duration_min,
                personalization_variables=case_row["personalization_variables"],
                case_specificity=case_specificity,
            )
        if not use_direct_deepseek_output:
            personalized_context, personalized_task = deepseek_client.enforce_user_case_quality(
                case_type_code=case_row["type_code"],
                case_title=case_row["title"],
                case_context=personalized_context,
                case_task=personalized_task,
                role_name=role_name,
                company_industry=user.company_industry,
                case_specificity=case_specificity,
                existing_contexts=existing_case_contexts,
            )
            personalized_context = personalized_context.replace(
                "В доступе сейчас только В распоряжении команды сейчас ",
                "В распоряжении команды сейчас ",
            )
            personalized_context = re.sub(
                r"\bВ доступе сейчас только\s+В распоряжении команды сейчас\s+",
                "В распоряжении команды сейчас ",
                personalized_context,
                flags=re.IGNORECASE,
            )
            personalized_context = re.sub(
                r"В распоряжении команды сейчас\s+(?:2 специалиста\s+){2,}клиентской поддержки",
                "В распоряжении команды сейчас 2 специалиста клиентской поддержки",
                personalized_context,
                flags=re.IGNORECASE,
            )
            personalized_task = re.sub(r"\b1:\s+1\b", "1:1", personalized_task, flags=re.IGNORECASE)
        case_quality = deepseek_client._score_case_text_quality(
            case_type_code=case_row["type_code"],
            template_context=case_row["intro_context"] or case_row["domain_context"] or "",
            template_task=case_row["task_for_user"] or "",
            generated_context=personalized_context,
            generated_task=personalized_task,
            user_profile=user_profile,
            case_specificity=case_specificity,
            existing_contexts=existing_case_contexts,
        )

        operation_progress_service.advance(
            progress_operation_id,
            3,
            title="Генерируем промты интервью",
            message="Создаем персонализированные системные промты для кейсового интервью.",
        )
        prompt_text = deepseek_client.generate_case_prompt(
            full_name=user.full_name,
            user_identifier=str(user.id),
            position=user.raw_position or user.job_description,
            duties=user.normalized_duties or user.raw_duties,
            company_industry=user.company_industry,
            role_name=role_name,
            user_profile=user_profile,
            case_type_code=case_row["type_code"],
            case_title=case_row["title"],
            case_context=personalized_context,
            case_task=personalized_task,
            case_skills=skill_names,
            case_artifact_name=methodical_context["artifact_name"],
            case_artifact_description=methodical_context["artifact_description"],
            case_required_response_blocks=methodical_context["required_response_blocks"],
            case_skill_evidence=methodical_context["skill_evidence"],
            case_difficulty_modifiers=methodical_context["difficulty_modifiers"],
            planned_total_duration_min=planned_total_duration_min,
            personalization_variables=case_row["personalization_variables"],
            personalization_map=personalization_map,
            case_specificity=case_specificity,
        )
        connection.execute(
            """
            DELETE FROM session_prompts
            WHERE session_case_id = %s
              AND prompt_type = 'case_dialog'
            """,
            (session_case_id,),
        )
        connection.execute(
            """
            INSERT INTO session_prompts (
                session_id, session_case_id, prompt_type, model_name, system_prompt, user_prompt, final_prompt_text,
                case_text_quality_score, template_fidelity_score, personalization_score, concreteness_score,
                readability_score, diversity_score, quality_issues, quality_strengths, quality_verdict, case_text_quality_json
            )
            VALUES (%s, %s, 'case_dialog', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session_id,
                session_case_id,
                deepseek_client.model,
                prompt_text,
                deepseek_client.build_opening_message(
                    case_title=case_row["title"] or "",
                    case_context=personalized_context,
                    case_task=personalized_task,
                ),
                prompt_text,
                case_quality["case_text_quality_score"],
                case_quality["template_fidelity_score"],
                case_quality["personalization_score"],
                case_quality["concreteness_score"],
                case_quality["readability_score"],
                case_quality["diversity_score"],
                json.dumps(case_quality["quality_issues"], ensure_ascii=False),
                json.dumps(case_quality["quality_strengths"], ensure_ascii=False),
                case_quality["quality_verdict"],
                json.dumps(case_quality, ensure_ascii=False),
            ),
        )

    def preview_personalized_case(
        self,
        *,
        user_id: int,
        case_id_code: str,
        use_llm_personalization: bool = True,
        case_generation_system_prompt: str | None = None,
        full_name: str | None = None,
        role_id: int | None = None,
        position: str | None = None,
        duties: str | None = None,
        company_industry: str | None = None,
        user_profile_override: dict | None = None,
    ) -> dict:
        cache_key = self._build_prompt_lab_case_preview_cache_key(
            user_id=user_id,
            case_id_code=case_id_code,
            use_llm_personalization=use_llm_personalization,
            case_generation_system_prompt=case_generation_system_prompt,
            full_name=full_name,
            role_id=role_id,
            position=position,
            duties=duties,
            company_industry=company_industry,
            user_profile_override=user_profile_override,
        )
        cached = self._get_cached_prompt_lab_case_preview(cache_key)
        if cached is not None:
            return cached

        with get_connection() as connection:
            user_row = connection.execute(
                """
                SELECT
                    u.id,
                    u.full_name,
                    u.email,
                    u.created_at,
                    u.role_id,
                    u.job_description,
                    p.raw_position,
                    p.raw_duties,
                    p.normalized_duties,
                    p.role_confidence,
                    p.role_rationale,
                    u.active_profile_id,
                    u.phone,
                    u.company_industry,
                    NULL AS avatar_data_url
                FROM users u
                LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
                WHERE u.id = %s
                """,
                (user_id,),
            ).fetchone()
            if user_row is None:
                raise ValueError("User not found")
            user = UserResponse(**dict(user_row))

            effective_role_id = role_id or user.role_id
            if not effective_role_id:
                raise ValueError("User role is not defined")
            effective_full_name = str(full_name or user.full_name or "").strip() or user.full_name
            effective_position = str(position or user.raw_position or user.job_description or "").strip()
            effective_duties = str(duties or user.normalized_duties or user.raw_duties or "").strip()
            effective_company_industry = str(company_industry or user.company_industry or "").strip()

            case_row = connection.execute(
                """
                SELECT
                    cr.id,
                    cr.case_id_code AS case_code,
                    COALESCE(txt.case_text_code, 'TXT-' || cr.case_id_code) AS text_code,
                    p.type_code,
                    cr.version AS case_registry_version,
                    COALESCE(txt.version, 1) AS case_text_version,
                    COALESCE(p.version, 1) AS case_type_passport_version,
                    cr.title,
                    txt.intro_context,
                    txt.task_for_user,
                    txt.facts_data,
                    txt.trigger_details,
                    txt.constraints_text,
                    txt.stakes_text,
                    txt.base_variant_text,
                    txt.hard_variant_text,
                    cr.context_domain AS domain_context,
                    txt.personalization_variables,
                    cr.estimated_time_min AS estimated_minutes,
                    cr.estimated_time_min AS planned_duration_minutes,
                    array_agg(crs.skill_id ORDER BY crs.display_order) AS skill_ids,
                    array_agg(s.skill_name ORDER BY crs.display_order) AS skill_names
                FROM cases_registry cr
                JOIN case_type_passports p ON p.id = cr.case_type_passport_id
                JOIN case_registry_skills crs ON crs.cases_registry_id = cr.id
                JOIN skills s ON s.id = crs.skill_id
                LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
                WHERE cr.case_id_code = %s
                GROUP BY
                    cr.id,
                    cr.case_id_code,
                    txt.case_text_code,
                    p.type_code,
                    cr.version,
                    txt.version,
                    p.version,
                    cr.title,
                    txt.intro_context,
                    txt.task_for_user,
                    txt.facts_data,
                    txt.trigger_details,
                    txt.constraints_text,
                    txt.stakes_text,
                    txt.base_variant_text,
                    txt.hard_variant_text,
                    cr.context_domain,
                    txt.personalization_variables,
                    cr.estimated_time_min
                LIMIT 1
                """,
                (case_id_code,),
            ).fetchone()
            if case_row is None:
                raise ValueError("Case not found")

            role_row = connection.execute(
                "SELECT name FROM roles WHERE id = %s",
                (effective_role_id,),
            ).fetchone()
            role_name = role_row["name"] if role_row else None
            profile_row = connection.execute(
                """
                SELECT user_domain, user_processes, user_tasks, user_stakeholders,
                       user_risks, user_constraints, user_context_vars, role_limits,
                       role_vocabulary, role_skill_profile
                FROM user_role_profiles
                WHERE id = %s
                """,
                (user.active_profile_id,),
            ).fetchone() if user.active_profile_id else None
            user_profile = dict(profile_row) if profile_row else None
            if user_profile_override:
                user_profile = {
                    **(user_profile or {}),
                    **user_profile_override,
                }
            if effective_company_industry:
                user_profile = {
                    **(user_profile or {}),
                    "company_industry": effective_company_industry,
                }

            methodical_context = self._get_case_methodical_context(connection, case_row)
            planned_total_duration_min = case_row["planned_duration_minutes"] or case_row["estimated_minutes"]
            base_context = case_row["intro_context"] or case_row["domain_context"] or ""
            base_task = case_row["task_for_user"] or ""

            effective_instruction_text = str(case_generation_system_prompt or "").strip() or str(
                (deepseek_client._get_case_text_build_instruction(case_row["type_code"]) or {}).get("instruction_text") or ""
            ).strip()
            skill_names = [name for name in (case_row["skill_names"] or []) if name]
            if use_llm_personalization:
                try:
                    personalized_context, personalized_task = deepseek_client._rewrite_user_case_materials_with_llm(
                        case_id_code=case_row.get("case_code"),
                        case_title=case_row["title"],
                        case_type_code=case_row["type_code"],
                        case_context=base_context,
                        case_task=base_task,
                        role_name=role_name,
                        full_name=effective_full_name,
                        position=effective_position,
                        duties=effective_duties,
                        company_industry=effective_company_industry,
                        user_profile=user_profile,
                        facts_data=case_row.get("facts_data"),
                        trigger_details=case_row.get("trigger_details"),
                        constraints_text=case_row.get("constraints_text"),
                        stakes_text=case_row.get("stakes_text"),
                        base_variant_text=case_row.get("base_variant_text"),
                        hard_variant_text=case_row.get("hard_variant_text"),
                        personalization_variables=case_row.get("personalization_variables"),
                        instruction_text_override=effective_instruction_text,
                        timeout_sec=self.PROMPT_LAB_LLM_PERSONALIZATION_TIMEOUT_SECONDS,
                        strict_validation=True,
                    )
                except Exception:
                    _, personalized_context, personalized_task = deepseek_client.build_personalized_case_materials_local_fast(
                        full_name=effective_full_name,
                        position=effective_position,
                        duties=effective_duties,
                        company_industry=effective_company_industry,
                        role_name=role_name,
                        user_profile=user_profile,
                        case_type_code=case_row["type_code"],
                        case_title=case_row["title"],
                        case_context=base_context,
                        case_task=base_task,
                        planned_total_duration_min=planned_total_duration_min,
                        personalization_variables=case_row.get("personalization_variables"),
                    )
            else:
                _, personalized_context, personalized_task = deepseek_client.build_personalized_case_materials_local_fast(
                    full_name=effective_full_name,
                    position=effective_position,
                    duties=effective_duties,
                    company_industry=effective_company_industry,
                    role_name=role_name,
                    user_profile=user_profile,
                    case_type_code=case_row["type_code"],
                    case_title=case_row["title"],
                    case_context=base_context,
                    case_task=base_task,
                    planned_total_duration_min=planned_total_duration_min,
                    personalization_variables=case_row.get("personalization_variables"),
                )
            case_quality = deepseek_client._score_case_text_quality(
                case_type_code=case_row["type_code"],
                template_context=base_context,
                template_task=base_task,
                generated_context=personalized_context,
                generated_task=personalized_task,
                user_profile=user_profile,
                case_specificity={},
                existing_contexts=[],
            )
            opening_message = deepseek_client.build_opening_message(
                case_title=case_row["title"] or "",
                case_context=personalized_context,
                case_task=personalized_task,
            )
            system_personalized_context, system_personalized_task = self._get_latest_system_personalized_case(
                connection,
                user_id=user_id,
                case_id_code=case_id_code,
            )

        result = {
            "user": {
                "id": user.id,
                "full_name": effective_full_name,
                "role_id": effective_role_id,
                "role_name": role_name,
                "position": effective_position,
                "duties": effective_duties,
                "company_industry": effective_company_industry,
                "user_profile": user_profile,
            },
            "case": {
                "id": int(case_row["id"]),
                "case_id_code": case_row["case_code"],
                "title": case_row["title"],
                "type_code": case_row["type_code"],
                "skills": skill_names,
            },
            "base_context": base_context,
            "base_task": base_task,
            "case_specificity": {},
            "personalization_map": {},
            "personalized_context": personalized_context,
            "personalized_task": personalized_task,
            "system_personalized_context": system_personalized_context,
            "system_personalized_task": system_personalized_task,
            "opening_message": opening_message,
            "system_prompt": effective_instruction_text,
            "methodical_context": methodical_context,
            "case_quality": case_quality,
        }
        self._set_cached_prompt_lab_case_preview(cache_key, result)
        return copy.deepcopy(result)

    def preview_personalized_case_set(
        self,
        *,
        user_id: int,
        use_llm_personalization: bool = True,
        case_generation_system_prompt: str | None = None,
        full_name: str | None = None,
        role_id: int | None = None,
        position: str | None = None,
        duties: str | None = None,
        company_industry: str | None = None,
        user_profile_override: dict | None = None,
    ) -> dict:
        with get_connection() as connection:
            user_row = connection.execute(
                """
                SELECT role_id
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            ).fetchone()
            if user_row is None:
                raise ValueError("User not found")
            effective_role_id = role_id or user_row["role_id"]
            if not effective_role_id:
                raise ValueError("User role is not defined")

            required_rows = connection.execute(
                """
                SELECT skill_id
                FROM role_skills
                WHERE role_id = %s
                  AND is_required = TRUE
                ORDER BY skill_id ASC
                """,
                (effective_role_id,),
            ).fetchall()
            required_skill_ids = [row["skill_id"] for row in required_rows]
            if not required_skill_ids:
                raise ValueError("No required skills configured for selected role")

            candidate_rows = self._load_candidate_case_rows(
                connection=connection,
                role_id=effective_role_id,
                required_skill_ids=required_skill_ids,
                excluded_case_ids=[],
            )
            selected_cases = self._select_minimum_cases(candidate_rows, required_skill_ids)
            if not selected_cases:
                raise ValueError("No cases found for selected role and required skills")

        case_items = []
        for index, case_row in enumerate(selected_cases, start=1):
            item = self.preview_personalized_case(
                user_id=user_id,
                case_id_code=case_row["case_code"],
                use_llm_personalization=use_llm_personalization,
                case_generation_system_prompt=case_generation_system_prompt,
                full_name=full_name,
                role_id=effective_role_id,
                position=position,
                duties=duties,
                company_industry=company_industry,
                user_profile_override=user_profile_override,
            )
            item["case_number"] = index
            case_items.append(item)

        first_item = case_items[0]
        return {
            **first_item,
            "case": {
                **first_item["case"],
                "total_cases": len(case_items),
            },
            "case_items": case_items,
            "total_cases": len(case_items),
        }

    def preview_personalized_case_batch(
        self,
        *,
        user_id: int,
        case_id_codes: list[str],
        use_llm_personalization: bool = True,
        case_generation_system_prompt: str | None = None,
        full_name: str | None = None,
        role_id: int | None = None,
        position: str | None = None,
        duties: str | None = None,
        company_industry: str | None = None,
        user_profile_override: dict | None = None,
        progress_operation_id: str | None = None,
    ) -> dict:
        normalized_case_codes: list[str] = []
        seen_case_codes: set[str] = set()
        for raw_code in case_id_codes:
            case_code = str(raw_code or "").strip()
            if not case_code or case_code in seen_case_codes:
                continue
            normalized_case_codes.append(case_code)
            seen_case_codes.add(case_code)
        if not normalized_case_codes:
            raise ValueError("At least one case must be selected")

        case_items = []
        for index, case_code in enumerate(normalized_case_codes, start=1):
            operation_progress_service.advance(
                progress_operation_id,
                index,
                title="Формируем кейсы",
                message=f"Генерируем кейс {index} из {len(normalized_case_codes)}: {case_code}",
            )
            item = self.preview_personalized_case(
                user_id=user_id,
                case_id_code=case_code,
                use_llm_personalization=use_llm_personalization,
                case_generation_system_prompt=case_generation_system_prompt,
                full_name=full_name,
                role_id=role_id,
                position=position,
                duties=duties,
                company_industry=company_industry,
                user_profile_override=user_profile_override,
            )
            item["case_number"] = index
            case_items.append(item)

        first_item = case_items[0]
        return {
            **first_item,
            "case": {
                **first_item["case"],
                "total_cases": len(case_items),
            },
            "case_items": case_items,
            "total_cases": len(case_items),
        }

    def preview_prompt_lab_dialog(
        self,
        *,
        user_id: int,
        case_id_code: str,
        use_llm_personalization: bool = True,
        case_generation_prompt_text: str | None = None,
    ) -> dict:
        artifacts = self.preview_personalized_case(
            user_id=user_id,
            case_id_code=case_id_code,
            use_llm_personalization=use_llm_personalization,
            case_generation_system_prompt=case_generation_prompt_text,
        )
        with get_connection() as connection:
            case_row = connection.execute(
                """
                SELECT
                    cr.estimated_time_min,
                    txt.personalization_variables
                FROM cases_registry cr
                LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
                WHERE cr.case_id_code = %s
                ORDER BY txt.version DESC NULLS LAST
                LIMIT 1
                """,
                (case_id_code,),
            ).fetchone()
            interviewer_prompt_row = connection.execute(
                """
                SELECT prompt_code, prompt_name, prompt_text, prompt_version
                FROM interviewer_agent_prompts
                WHERE prompt_code = 'case_follow_up'
                  AND is_active = TRUE
                ORDER BY prompt_version DESC, prompt_code ASC
                LIMIT 1
                """
            ).fetchone()

        user_data = artifacts["user"]
        case_data = artifacts["case"]
        methodical_context = dict(artifacts.get("methodical_context") or {})
        planned_total_duration_min = (case_row["estimated_time_min"] if case_row else None) or 10
        local_case_specificity = deepseek_client._fallback_case_specificity(
            position=user_data.get("position"),
            duties=user_data.get("duties"),
            company_industry=user_data.get("company_industry"),
            role_name=user_data.get("role_name"),
            user_profile=user_data.get("user_profile"),
            case_type_code=case_data.get("type_code"),
            case_title=case_data.get("title") or "",
            case_context=artifacts.get("personalized_context") or "",
            case_task=artifacts.get("personalized_task") or "",
        )
        local_personalization_placeholders = deepseek_client._extract_placeholders(
            "\n".join(
                filter(
                    None,
                    [
                        artifacts.get("personalized_context") or "",
                        artifacts.get("personalized_task") or "",
                        (case_row["personalization_variables"] if case_row else None) or "",
                    ],
                )
            )
        )
        local_personalization_map = deepseek_client._fallback_personalization_map(
            placeholders=local_personalization_placeholders,
            position=user_data.get("position"),
            duties=user_data.get("duties"),
            company_industry=user_data.get("company_industry"),
            role_name=user_data.get("role_name"),
            user_profile=user_data.get("user_profile"),
            planned_total_duration_min=planned_total_duration_min,
            case_type_code=case_data.get("type_code"),
            case_title=case_data.get("title") or "",
            case_context=artifacts.get("personalized_context") or "",
            case_task=artifacts.get("personalized_task") or "",
            case_specificity=local_case_specificity,
        )
        final_system_prompt = deepseek_client.generate_case_prompt(
            full_name=user_data.get("full_name"),
            user_identifier=str(user_data.get("id") or ""),
            position=user_data.get("position"),
            duties=user_data.get("duties"),
            company_industry=user_data.get("company_industry"),
            role_name=user_data.get("role_name"),
            user_profile=user_data.get("user_profile"),
            case_type_code=case_data.get("type_code"),
            case_title=case_data.get("title"),
            case_context=artifacts.get("personalized_context") or "",
            case_task=artifacts.get("personalized_task") or "",
            case_skills=case_data.get("skills") or [],
            case_artifact_name=methodical_context.get("artifact_name"),
            case_artifact_description=methodical_context.get("artifact_description"),
            case_required_response_blocks=methodical_context.get("required_response_blocks") or [],
            case_skill_evidence=methodical_context.get("skill_evidence") or [],
            case_difficulty_modifiers=methodical_context.get("difficulty_modifiers") or [],
            planned_total_duration_min=planned_total_duration_min,
            personalization_variables=(case_row["personalization_variables"] if case_row else None),
            personalization_map=local_personalization_map,
            case_specificity=local_case_specificity,
        )
        counterpart_opening_message = deepseek_client.build_dialog_counterpart_opening_message(
            case_title=case_data.get("title") or "",
            case_context=artifacts.get("personalized_context") or "",
            case_task=artifacts.get("personalized_task") or "",
            interactivity_mode=methodical_context.get("interactivity_mode"),
        )
        is_dialog_case = deepseek_client._is_dialog_interactivity_mode(methodical_context.get("interactivity_mode"))
        prompt_lab_methodical_context = {
            **methodical_context,
            "user_id": user_data.get("id"),
            "role_name": user_data.get("role_name"),
            "position": user_data.get("position"),
            "duties": user_data.get("duties"),
            "company_industry": user_data.get("company_industry"),
            "user_profile": user_data.get("user_profile"),
        }
        return {
            "user": user_data,
            "case": case_data,
            "personalized_context": artifacts.get("personalized_context") or "",
            "personalized_task": artifacts.get("personalized_task") or "",
            "case_generation_prompt_text": str(
                case_generation_prompt_text
                or artifacts.get("system_prompt")
                or ""
            ).strip() or None,
            "opening_message": artifacts.get("opening_message") or "",
            "counterpart_opening_message": (counterpart_opening_message or None) if is_dialog_case else None,
            "is_dialog_case": is_dialog_case,
            "system_prompt": final_system_prompt,
            "interviewer_prompt_text": interviewer_prompt_row["prompt_text"] if interviewer_prompt_row else None,
            "interviewer_prompt_name": interviewer_prompt_row["prompt_name"] if interviewer_prompt_row else None,
            "interviewer_prompt_code": interviewer_prompt_row["prompt_code"] if interviewer_prompt_row else None,
            "interviewer_prompt_version": interviewer_prompt_row["prompt_version"] if interviewer_prompt_row else None,
            "methodical_context": prompt_lab_methodical_context,
        }

    def simulate_prompt_lab_dialog_turn(
        self,
        *,
        system_prompt: str,
        case_title: str,
        case_skills: list[str],
        methodical_context: dict | None,
        dialogue: list[dict],
        interviewer_prompt_text: str | None,
        user_message: str,
        role_name: str | None = None,
        position: str | None = None,
        duties: str | None = None,
        company_industry: str | None = None,
        user_profile: dict | None = None,
    ) -> dict:
        normalized_user_message = str(user_message or "").strip()
        if not normalized_user_message:
            raise ValueError("User message is required")

        normalized_dialogue: list[dict[str, str]] = []
        for item in dialogue or []:
            role = str((item or {}).get("role") or "").strip().lower()
            content = str((item or {}).get("content") or (item or {}).get("message_text") or "").strip()
            if role not in {"assistant", "user"} or not content:
                continue
            normalized_dialogue.append({"role": role, "content": content})

        context = dict(methodical_context or {})
        is_dialog_case = deepseek_client._is_dialog_interactivity_mode(context.get("interactivity_mode"))
        last_assistant_message = next(
            (item["content"] for item in reversed(normalized_dialogue) if item["role"] == "assistant"),
            "",
        )
        awaiting_finish_confirmation = self._is_finish_confirmation_prompt(last_assistant_message)

        if awaiting_finish_confirmation and self._looks_like_finish_confirmation(normalized_user_message):
            return {
                "assistant_message": "Понял. Завершаем кейс по вашему подтверждению.",
                "case_completed": True,
                "stop_reason": "user_confirmed_finish",
            }

        if awaiting_finish_confirmation and self._looks_like_continue_after_confirmation(normalized_user_message):
            return {
                "assistant_message": self.CASE_CONTINUE_AFTER_CONFIRMATION_TEXT,
                "case_completed": False,
                "stop_reason": "continue_after_finish_confirmation",
            }

        if is_dialog_case and self._looks_like_explicit_finish_request(normalized_user_message):
            return {
                "assistant_message": "Понял. Завершаем кейс по вашему запросу.",
                "case_completed": True,
                "stop_reason": "user_requested_finish",
            }

        normalized_dialogue.append({"role": "user", "content": normalized_user_message})

        if is_dialog_case and self._looks_like_defer_or_refusal(normalized_user_message):
            return {
                "assistant_message": self.CASE_FINISH_CONFIRMATION_TEXT,
                "case_completed": False,
                "stop_reason": "finish_confirmation_requested",
            }

        interactivity_limits = self._get_interactivity_limits(
            context.get("interactivity_mode"),
            max_user_messages=context.get("max_user_messages"),
            max_total_turns=context.get("max_total_turns"),
        )
        max_user_messages = interactivity_limits.get("max_user_messages")
        user_message_count = sum(1 for item in normalized_dialogue if item["role"] == "user")

        if max_user_messages is not None and user_message_count > max_user_messages:
            return {
                "assistant_message": self.CASE_MESSAGE_LIMIT_REACHED_TEXT,
                "case_completed": True,
                "stop_reason": "message_limit_reached",
            }

        if str(context.get("interactivity_mode") or "").strip().lower() == "1 ход" and user_message_count >= 1:
            return {
                "assistant_message": "Ответ зафиксирован. Завершаем кейс автоматически.",
                "case_completed": False,
                "stop_reason": "single_turn_auto_finish",
                "pending_auto_finish": True,
                "auto_finish_delay_ms": self.CASE_AUTO_FINISH_DELAY_MS,
            }

        turn = deepseek_client.evaluate_case_turn(
            system_prompt=system_prompt,
            dialogue=normalized_dialogue,
            case_title=case_title,
            case_skills=case_skills,
            user_identifier=str((context.get("user_id") or "")).strip() or None,
            interactivity_mode=context.get("interactivity_mode"),
            format_control_rules=context.get("format_control_rules"),
            recommended_answer_length=context.get("recommended_answer_length"),
            interviewer_prompt_override=interviewer_prompt_text,
            fallback_user_message=normalized_user_message,
            role_name=role_name,
            position=position,
            duties=duties,
            company_industry=company_industry,
            user_profile=user_profile,
        )
        dialogue_rows = [
            {"role": item["role"], "message_text": item["content"]}
            for item in normalized_dialogue
        ]
        if self._needs_non_repeating_follow_up(turn.assistant_message, dialogue_rows):
            turn.assistant_message = self._build_non_repeating_follow_up(
                repeated_message=turn.assistant_message,
                user_message=normalized_user_message,
                dialogue_rows=dialogue_rows,
                case_skills=case_skills,
                interactivity_mode=context.get("interactivity_mode"),
            )
        return {
            "assistant_message": turn.assistant_message,
            "case_completed": False,
            "stop_reason": None,
        }

    def _get_existing_session_case_contexts(
        self,
        connection,
        *,
        session_id: int,
        session_case_id: int,
    ) -> list[str]:
        rows = connection.execute(
            """
            SELECT sp.user_prompt
            FROM session_prompts sp
            JOIN session_cases sc ON sc.id = sp.session_case_id
            WHERE sc.session_id = %s
              AND sp.prompt_type = 'case_dialog'
              AND sc.id <> %s
            ORDER BY sc.id ASC
            """,
            (session_id, session_case_id),
        ).fetchall()
        results: list[str] = []
        for row in rows:
            text = str(row["user_prompt"] or "").strip()
            if not text:
                continue
            marker = "Personalized task:"
            if marker in text:
                text = text.split(marker, 1)[0].replace("Personalized case context:", "", 1).strip()
            elif "\n\n" in text:
                text = text.rsplit("\n\n", 1)[0].strip()
            if text:
                results.append(text)
        return results

    def _get_case_methodical_context(self, connection, case_row) -> dict:
        row = connection.execute(
            """
            SELECT
                p.id AS passport_id,
                p.type_code,
                p.interactivity_mode,
                p.max_user_messages,
                p.max_total_turns,
                p.recommended_answer_length,
                p.format_control_rules,
                a.artifact_name,
                a.description AS artifact_description
            FROM cases_registry cr
            LEFT JOIN case_type_passports p ON p.id = cr.case_type_passport_id
            LEFT JOIN case_response_artifacts a ON a.id = p.artifact_id
            WHERE cr.id = %s
            LIMIT 1
            """,
            (case_row["id"],),
        ).fetchone()
        if row is None or row["passport_id"] is None:
            return {
                "artifact_name": None,
                "artifact_description": None,
                "interactivity_mode": None,
                "max_user_messages": None,
                "max_total_turns": None,
                "recommended_answer_length": None,
                "format_control_rules": None,
                "required_response_blocks": [],
                "skill_evidence": [],
                "difficulty_modifiers": [],
            }

        passport_id = row["passport_id"]
        blocks = connection.execute(
            """
            SELECT block_name
            FROM case_required_response_blocks
            WHERE case_type_passport_id = %s
            ORDER BY display_order ASC, id ASC
            """,
            (passport_id,),
        ).fetchall()
        evidence_rows = connection.execute(
            """
            SELECT
                s.skill_code,
                s.skill_name,
                e.related_response_block_code,
                e.evidence_description,
                e.expected_signal,
                e.is_required
            FROM case_type_skill_evidence e
            JOIN skills s ON s.id = e.skill_id
            WHERE e.case_type_passport_id = %s
            ORDER BY s.skill_code ASC, e.related_response_block_code ASC NULLS LAST, e.id ASC
            """,
            (passport_id,),
        ).fetchall()
        modifier_rows = connection.execute(
            """
            SELECT modifier_name, difficulty_level
            FROM case_type_difficulty_modifiers
            WHERE case_type_passport_id = %s
            ORDER BY difficulty_level ASC, modifier_name ASC
            """,
            (passport_id,),
        ).fetchall()
        return {
            "artifact_name": row["artifact_name"],
            "artifact_description": row["artifact_description"],
            "interactivity_mode": row["interactivity_mode"],
            "max_user_messages": row["max_user_messages"],
            "max_total_turns": row["max_total_turns"],
            "recommended_answer_length": row["recommended_answer_length"],
            "format_control_rules": row["format_control_rules"],
            "required_response_blocks": [block["block_name"] for block in blocks if block["block_name"]],
            "skill_evidence": [dict(item) for item in evidence_rows],
            "difficulty_modifiers": [
                f"{item['modifier_name']} ({item['difficulty_level']})"
                for item in modifier_rows
                if item["modifier_name"]
            ],
        }

    def _get_interactivity_limits(
        self,
        interactivity_mode: str | None,
        *,
        max_user_messages: int | None = None,
        max_total_turns: int | None = None,
    ) -> dict[str, int | None]:
        if isinstance(max_user_messages, int) and max_user_messages > 0:
            return {
                "max_user_messages": max_user_messages,
                "max_total_turns": max_total_turns if isinstance(max_total_turns, int) and max_total_turns > 0 else None,
            }
        normalized = str(interactivity_mode or "").strip().lower()
        if normalized == "1 ход":
            return {"max_user_messages": 2, "max_total_turns": 4}
        if "диалог" in normalized:
            return {"max_user_messages": 4, "max_total_turns": 8}
        return {"max_user_messages": None, "max_total_turns": None}

    def _get_latest_system_personalized_case(
        self,
        connection,
        *,
        user_id: int,
        case_id_code: str,
    ) -> tuple[str | None, str | None]:
        prompt_row = connection.execute(
            """
            SELECT sp.user_prompt
            FROM session_prompts sp
            JOIN session_cases sc ON sc.id = sp.session_case_id
            JOIN user_sessions us ON us.id = sp.session_id
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            WHERE us.user_id = %s
              AND sp.prompt_type = 'case_dialog'
              AND cr.case_id_code = %s
            ORDER BY sp.id DESC
            LIMIT 1
            """,
            (user_id, case_id_code),
        ).fetchone()
        if prompt_row is None:
            return None, None
        context_text, task_text = deepseek_client.split_user_case_message(str(prompt_row["user_prompt"] or ""))
        return context_text or None, task_text or None

    def open_assessment_dialogue(self, session_code: str) -> AssessmentTurnReply:
        with get_connection() as connection:
            session_row = connection.execute(
                """
                SELECT id, session_code
                FROM user_sessions
                WHERE session_code = %s
                  AND assessment_code = 'competencies_4k'
                LIMIT 1
                """,
                (session_code,),
            ).fetchone()
            if session_row is None:
                raise ValueError("Assessment session not found")

            plan = self._build_plan(connection, session_row["id"], session_code)
            if plan.current_session_case_id is None or plan.current_case_title is None:
                return AssessmentTurnReply(
                    session_code=session_code,
                    session_id=plan.session_id,
                    session_case_id=None,
                    case_title=None,
                    case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    message="Все кейсы уже завершены.",
                    case_completed=True,
                    assessment_completed=True,
                result_status="passed",
                case_time_limit_minutes=None,
                planned_case_duration_minutes=None,
                case_started_at=None,
                case_time_remaining_seconds=None,
                )
            resumed_started_at = self._resume_case_timer(connection, plan.current_session_case_id)
            if resumed_started_at is not None and resumed_started_at != plan.current_case_started_at:
                plan = AssessmentSessionPlan(
                    session_id=plan.session_id,
                    session_code=plan.session_code,
                    current_session_case_id=plan.current_session_case_id,
                    current_case_title=plan.current_case_title,
                    current_case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    current_case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    current_case_planned_duration_minutes=plan.current_case_planned_duration_minutes,
                    current_case_started_at=resumed_started_at,
                    opening_message=plan.opening_message,
                )
            history_fields = self._get_session_case_history_fields(connection, plan.current_session_case_id)

            user_turn_count = self._get_case_user_turn_count(connection, plan.current_session_case_id)
            if (
                plan.current_case_started_at is not None
                and self._is_time_expired(plan.current_case_started_at, plan.current_case_time_limit_minutes)
                and user_turn_count == 0
            ):
                restarted_at = self._utc_now()
                refreshed_row = connection.execute(
                    """
                    UPDATE session_cases
                    SET started_at = %s,
                        paused_remaining_seconds = NULL,
                        status = CASE WHEN status IN ('selected', 'sent_to_personalization', 'personalized') THEN 'shown' ELSE status END
                    WHERE id = %s
                    RETURNING started_at
                    """,
                    (restarted_at, plan.current_session_case_id),
                ).fetchone()
                connection.commit()
                plan = AssessmentSessionPlan(
                    session_id=plan.session_id,
                    session_code=plan.session_code,
                    current_session_case_id=plan.current_session_case_id,
                    current_case_title=plan.current_case_title,
                    current_case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    current_case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    current_case_planned_duration_minutes=plan.current_case_planned_duration_minutes,
                    current_case_started_at=refreshed_row["started_at"] if refreshed_row else plan.current_case_started_at,
                    opening_message=plan.opening_message,
                )

            existing_message = connection.execute(
                """
                SELECT message_text
                FROM session_case_messages
                WHERE session_case_id = %s
                  AND role = 'assistant'
                ORDER BY id ASC
                LIMIT 1
                """,
                (plan.current_session_case_id,),
            ).fetchone()
            if existing_message is not None:
                if plan.current_case_started_at is None:
                    started_at = self._utc_now()
                    started_row = connection.execute(
                        """
                        UPDATE session_cases
                        SET started_at = COALESCE(started_at, %s),
                            paused_remaining_seconds = NULL,
                            status = CASE WHEN status IN ('selected', 'sent_to_personalization', 'personalized') THEN 'shown' ELSE status END
                        WHERE id = %s
                        RETURNING started_at
                        """,
                        (started_at, plan.current_session_case_id),
                    ).fetchone()
                    connection.commit()
                    plan = AssessmentSessionPlan(
                        session_id=plan.session_id,
                        session_code=plan.session_code,
                        current_session_case_id=plan.current_session_case_id,
                        current_case_title=plan.current_case_title,
                        current_case_number=plan.current_case_number,
                        total_cases=plan.total_cases,
                        current_case_time_limit_minutes=plan.current_case_time_limit_minutes,
                        current_case_planned_duration_minutes=plan.current_case_planned_duration_minutes,
                        current_case_started_at=started_row["started_at"] if started_row else None,
                        opening_message=plan.opening_message,
                    )
                return AssessmentTurnReply(
                    session_code=session_code,
                    session_id=plan.session_id,
                    session_case_id=plan.current_session_case_id,
                    case_title=plan.current_case_title,
                    case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    message=existing_message["message_text"],
                    case_completed=False,
                    assessment_completed=False,
                    case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                    case_started_at=plan.current_case_started_at,
                    case_time_remaining_seconds=self._get_remaining_case_seconds(
                        plan.current_case_started_at,
                        plan.current_case_time_limit_minutes,
                    ),
                    is_dialog_case=self._get_is_dialog_case_for_session_case(connection, plan.current_session_case_id),
                    **history_fields,
                )

            case_row = self._get_case_for_session_case(connection, plan.current_session_case_id)
            opening_message = deepseek_client.build_opening_message(
                case_title=case_row["title"],
                case_context=self._get_personalized_case_context(connection, plan.current_session_case_id, case_row),
                case_task=self._get_personalized_case_task(connection, plan.current_session_case_id, case_row),
            )
            connection.execute(
                """
                INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                VALUES (%s, %s, 'assistant', %s)
                """,
                (plan.current_session_case_id, plan.session_id, opening_message),
            )
            connection.execute(
                """
                UPDATE session_cases
                SET status = 'shown',
                    started_at = COALESCE(started_at, %s),
                    paused_remaining_seconds = NULL
                WHERE id = %s
                RETURNING started_at
                """,
                (self._utc_now(), plan.current_session_case_id),
            ).fetchone()
            started_row = connection.execute(
                """
                SELECT started_at
                FROM session_cases
                WHERE id = %s
                """,
                (plan.current_session_case_id,),
            ).fetchone()
            connection.commit()
            return AssessmentTurnReply(
                session_code=session_code,
                session_id=plan.session_id,
                session_case_id=plan.current_session_case_id,
                case_title=plan.current_case_title,
                case_number=plan.current_case_number,
                total_cases=plan.total_cases,
                message=opening_message,
                case_completed=False,
                assessment_completed=False,
                case_time_limit_minutes=plan.current_case_time_limit_minutes,
                planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                case_started_at=started_row["started_at"] if started_row else plan.current_case_started_at,
                case_time_remaining_seconds=self._get_remaining_case_seconds(
                    started_row["started_at"] if started_row else plan.current_case_started_at,
                    plan.current_case_time_limit_minutes,
                ),
                is_dialog_case=deepseek_client._is_dialog_interactivity_mode(
                    self._get_case_methodical_context(connection, case_row).get("interactivity_mode"),
                ),
                **history_fields,
            )

    def process_case_message(
        self,
        *,
        session_code: str,
        message: str,
        progress_operation_id: str | None = None,
    ) -> AssessmentTurnReply:
        with get_connection() as connection:
            operation_progress_service.advance(
                progress_operation_id,
                0,
                title="Фиксируем ответ по кейсу",
                message="Сохраняем ответ пользователя и проверяем текущее состояние кейса.",
            )
            session_row = connection.execute(
                """
                SELECT us.id, us.session_code, us.user_id, us.role_id, u.full_name, u.job_description,
                       u.company_industry, p.id AS active_profile_id,
                       p.raw_position, p.raw_duties, p.normalized_duties
                FROM user_sessions us
                JOIN users u ON u.id = us.user_id
                LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
                WHERE us.session_code = %s
                  AND us.assessment_code = 'competencies_4k'
                LIMIT 1
                """,
                (session_code,),
            ).fetchone()
            if session_row is None:
                raise ValueError("Assessment session not found")

            pending_followup_row = self._get_pending_mbti_followup(connection, session_row["id"])
            if pending_followup_row is not None:
                operation_progress_service.advance(
                    progress_operation_id,
                    2,
                    title="Уточняем ответы по кейсу",
                    message="Обрабатываем ответ на уточняющий вопрос MBTI и готовим следующий шаг.",
                )
                pending_reply = self._handle_pending_mbti_followup(
                    connection=connection,
                    session_row=session_row,
                    session_code=session_code,
                    message=message,
                    pending_row=pending_followup_row,
                    progress_operation_id=progress_operation_id,
                )
                if pending_reply is not None:
                    return pending_reply

            role_row = connection.execute(
                "SELECT name FROM roles WHERE id = %s",
                (session_row["role_id"],),
            ).fetchone() if session_row.get("role_id") else None
            role_name = role_row["name"] if role_row else None
            profile_row = connection.execute(
                """
                SELECT *
                FROM user_role_profiles
                WHERE id = %s
                """,
                (session_row["active_profile_id"],),
            ).fetchone() if session_row.get("active_profile_id") else None
            user_profile = dict(profile_row) if profile_row else None

            plan = self._build_plan(connection, session_row["id"], session_code)
            if plan.current_session_case_id is None or plan.current_case_title is None:
                raise ValueError("No active case found for this session")
            resumed_started_at = self._resume_case_timer(connection, plan.current_session_case_id)
            if resumed_started_at is not None and resumed_started_at != plan.current_case_started_at:
                plan = AssessmentSessionPlan(
                    session_id=plan.session_id,
                    session_code=plan.session_code,
                    current_session_case_id=plan.current_session_case_id,
                    current_case_title=plan.current_case_title,
                    current_case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    current_case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    current_case_planned_duration_minutes=plan.current_case_planned_duration_minutes,
                    current_case_started_at=resumed_started_at,
                    opening_message=plan.opening_message,
                )
            history_fields = self._get_session_case_history_fields(connection, plan.current_session_case_id)

            case_meta = connection.execute(
                """
                SELECT sc.started_at, cr.estimated_time_min AS estimated_minutes, cr.title
                FROM session_cases sc
                JOIN cases_registry cr ON cr.id = sc.case_registry_id
                WHERE sc.id = %s
                """,
                (plan.current_session_case_id,),
            ).fetchone()
            user_turn_count = self._get_case_user_turn_count(connection, plan.current_session_case_id)

            if (
                message not in {"__timeout__", "__finish_case__", "__auto_finish_case__"}
                and user_turn_count == 0
                and case_meta["started_at"] is not None
                and self._is_time_expired(case_meta["started_at"], case_meta["estimated_minutes"])
            ):
                restarted_at = self._utc_now()
                refreshed_row = connection.execute(
                    """
                    UPDATE session_cases
                    SET started_at = %s,
                        paused_remaining_seconds = NULL,
                        status = CASE WHEN status IN ('selected', 'sent_to_personalization', 'personalized') THEN 'shown' ELSE status END
                    WHERE id = %s
                    RETURNING started_at
                    """,
                    (restarted_at, plan.current_session_case_id),
                ).fetchone()
                case_meta = {
                    "started_at": refreshed_row["started_at"] if refreshed_row else case_meta["started_at"],
                    "estimated_minutes": case_meta["estimated_minutes"],
                    "title": case_meta["title"],
                }

            if self._is_time_expired(case_meta["started_at"], case_meta["estimated_minutes"]):
                dialogue_rows = connection.execute(
                    """
                    SELECT role, message_text
                    FROM session_case_messages
                    WHERE session_case_id = %s
                    ORDER BY id ASC
                    """,
                    (plan.current_session_case_id,),
                ).fetchall()
                prompt_row = connection.execute(
                    """
                    SELECT final_prompt_text
                    FROM session_prompts
                    WHERE session_case_id = %s
                      AND prompt_type = 'case_dialog'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (plan.current_session_case_id,),
                ).fetchone()
                timeout_turn = deepseek_client.build_timeout_turn(
                    system_prompt=prompt_row["final_prompt_text"] if prompt_row else "",
                    dialogue=[{"role": row["role"], "content": row["message_text"]} for row in dialogue_rows],
                    case_title=case_meta["title"],
                )
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], timeout_turn.assistant_message),
                )
                return self._complete_case_and_continue(
                    connection=connection,
                    session_row=session_row,
                    plan=plan,
                    turn=timeout_turn,
                    session_code=session_code,
                    time_expired=True,
                    progress_operation_id=progress_operation_id,
                )

            if message == "__finish_case__":
                dialogue_rows = connection.execute(
                    """
                    SELECT role, message_text
                    FROM session_case_messages
                    WHERE session_case_id = %s
                    ORDER BY id ASC
                    """,
                    (plan.current_session_case_id,),
                ).fetchall()
                prompt_row = connection.execute(
                    """
                    SELECT final_prompt_text
                    FROM session_prompts
                    WHERE session_case_id = %s
                      AND prompt_type = 'case_dialog'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (plan.current_session_case_id,),
                ).fetchone()
                finish_turn = deepseek_client.build_manual_finish_turn(
                    system_prompt=prompt_row["final_prompt_text"] if prompt_row else "",
                    dialogue=[{"role": row["role"], "content": row["message_text"]} for row in dialogue_rows],
                    case_title=case_meta["title"],
                    case_skills=self._get_case_skill_names(connection, plan.current_session_case_id),
                )
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], finish_turn.assistant_message),
                )
                return self._complete_case_and_continue(
                    connection=connection,
                    session_row=session_row,
                    plan=plan,
                    turn=finish_turn,
                    session_code=session_code,
                    time_expired=False,
                    progress_operation_id=progress_operation_id,
                )

            if message == "__auto_finish_case__":
                last_assistant_row = connection.execute(
                    """
                    SELECT message_text
                    FROM session_case_messages
                    WHERE session_case_id = %s
                      AND role = 'assistant'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (plan.current_session_case_id,),
                ).fetchone()
                auto_finish_turn = DeepSeekTurnResult(
                    assistant_message=str((last_assistant_row or {}).get("message_text") or self.CASE_MESSAGE_LIMIT_REACHED_TEXT),
                    is_case_complete=True,
                    result_status="passed",
                    completion_score=None,
                    evaluator_summary="",
                )
                return self._complete_case_and_continue(
                    connection=connection,
                    session_row=session_row,
                    plan=plan,
                    turn=auto_finish_turn,
                    session_code=session_code,
                    time_expired=False,
                    progress_operation_id=progress_operation_id,
                )

            dialogue_rows_before_user = connection.execute(
                """
                SELECT role, message_text
                FROM session_case_messages
                WHERE session_case_id = %s
                ORDER BY id ASC
                """,
                (plan.current_session_case_id,),
            ).fetchall()
            last_assistant_before_user = next(
                (str(row["message_text"] or "") for row in reversed(dialogue_rows_before_user) if row["role"] == "assistant"),
                "",
            )
            methodical_context = self._get_case_methodical_context(
                connection,
                self._get_case_for_session_case(connection, plan.current_session_case_id),
            )
            is_dialog_case = deepseek_client._is_dialog_interactivity_mode(methodical_context.get("interactivity_mode"))
            awaiting_finish_confirmation = self._is_finish_confirmation_prompt(last_assistant_before_user)

            if is_dialog_case and awaiting_finish_confirmation and self._looks_like_finish_confirmation(message):
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'user', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], message),
                )
                dialogue_rows = connection.execute(
                    """
                    SELECT role, message_text
                    FROM session_case_messages
                    WHERE session_case_id = %s
                    ORDER BY id ASC
                    """,
                    (plan.current_session_case_id,),
                ).fetchall()
                prompt_row = connection.execute(
                    """
                    SELECT final_prompt_text
                    FROM session_prompts
                    WHERE session_case_id = %s
                      AND prompt_type = 'case_dialog'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (plan.current_session_case_id,),
                ).fetchone()
                finish_turn = deepseek_client.build_manual_finish_turn(
                    system_prompt=prompt_row["final_prompt_text"] if prompt_row else "",
                    dialogue=[{"role": row["role"], "content": row["message_text"]} for row in dialogue_rows],
                    case_title=case_meta["title"],
                    case_skills=self._get_case_skill_names(connection, plan.current_session_case_id),
                )
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], finish_turn.assistant_message),
                )
                return self._complete_case_and_continue(
                    connection=connection,
                    session_row=session_row,
                    plan=plan,
                    turn=finish_turn,
                    session_code=session_code,
                    time_expired=False,
                    progress_operation_id=progress_operation_id,
                )

            if is_dialog_case and self._looks_like_explicit_finish_request(message):
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'user', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], message),
                )
                dialogue_rows = connection.execute(
                    """
                    SELECT role, message_text
                    FROM session_case_messages
                    WHERE session_case_id = %s
                    ORDER BY id ASC
                    """,
                    (plan.current_session_case_id,),
                ).fetchall()
                prompt_row = connection.execute(
                    """
                    SELECT final_prompt_text
                    FROM session_prompts
                    WHERE session_case_id = %s
                      AND prompt_type = 'case_dialog'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (plan.current_session_case_id,),
                ).fetchone()
                finish_turn = deepseek_client.build_manual_finish_turn(
                    system_prompt=prompt_row["final_prompt_text"] if prompt_row else "",
                    dialogue=[{"role": row["role"], "content": row["message_text"]} for row in dialogue_rows],
                    case_title=case_meta["title"],
                    case_skills=self._get_case_skill_names(connection, plan.current_session_case_id),
                )
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], finish_turn.assistant_message),
                )
                return self._complete_case_and_continue(
                    connection=connection,
                    session_row=session_row,
                    plan=plan,
                    turn=finish_turn,
                    session_code=session_code,
                    time_expired=False,
                    progress_operation_id=progress_operation_id,
                )

            if is_dialog_case and awaiting_finish_confirmation and self._looks_like_continue_after_confirmation(message):
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'user', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], message),
                )
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], self.CASE_CONTINUE_AFTER_CONFIRMATION_TEXT),
                )
                connection.commit()
                return AssessmentTurnReply(
                    session_code=session_code,
                    session_id=session_row["id"],
                    session_case_id=plan.current_session_case_id,
                    case_title=plan.current_case_title,
                    case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    message=self.CASE_CONTINUE_AFTER_CONFIRMATION_TEXT,
                    case_completed=False,
                    assessment_completed=False,
                    result_status=None,
                    completion_score=None,
                    evaluator_summary=None,
                    case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                    case_started_at=plan.current_case_started_at,
                    case_time_remaining_seconds=self._get_remaining_case_seconds(
                        plan.current_case_started_at,
                        plan.current_case_time_limit_minutes,
                    ),
                    is_dialog_case=is_dialog_case,
                    pending_auto_finish=False,
                    auto_finish_delay_ms=None,
                    **history_fields,
                )

            connection.execute(
                """
                INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                VALUES (%s, %s, 'user', %s)
                """,
                (plan.current_session_case_id, session_row["id"], message),
            )
            if is_dialog_case and self._looks_like_defer_or_refusal(message):
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], self.CASE_FINISH_CONFIRMATION_TEXT),
                )
                connection.commit()
                return AssessmentTurnReply(
                    session_code=session_code,
                    session_id=session_row["id"],
                    session_case_id=plan.current_session_case_id,
                    case_title=plan.current_case_title,
                    case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    message=self.CASE_FINISH_CONFIRMATION_TEXT,
                    case_completed=False,
                    assessment_completed=False,
                    result_status=None,
                    completion_score=None,
                    evaluator_summary=None,
                    case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                    case_started_at=plan.current_case_started_at,
                    case_time_remaining_seconds=self._get_remaining_case_seconds(
                        plan.current_case_started_at,
                        plan.current_case_time_limit_minutes,
                    ),
                    is_dialog_case=is_dialog_case,
                    pending_auto_finish=False,
                    auto_finish_delay_ms=None,
                    **history_fields,
                )

            dialogue_rows = connection.execute(
                """
                SELECT role, message_text
                FROM session_case_messages
                WHERE session_case_id = %s
                ORDER BY id ASC
                """,
                (plan.current_session_case_id,),
            ).fetchall()
            prompt_row = connection.execute(
                """
                SELECT final_prompt_text
                FROM session_prompts
                WHERE session_case_id = %s
                  AND prompt_type = 'case_dialog'
                ORDER BY id DESC
                LIMIT 1
                """,
                (plan.current_session_case_id,),
            ).fetchone()
            case_row = self._get_case_for_session_case(connection, plan.current_session_case_id)
            methodical_context = self._get_case_methodical_context(connection, case_row)
            interactivity_limits = self._get_interactivity_limits(
                methodical_context.get("interactivity_mode"),
                max_user_messages=methodical_context.get("max_user_messages"),
                max_total_turns=methodical_context.get("max_total_turns"),
            )
            user_message_count = sum(1 for row in dialogue_rows if row["role"] == "user")
            max_user_messages = interactivity_limits.get("max_user_messages")
            case_skills = self._get_case_skill_names(connection, plan.current_session_case_id)

            if user_message_count == 1 and self._looks_like_thin_case_answer(message):
                case_follow_up_message = self._build_thin_case_answer_follow_up(
                    user_message=message,
                    dialogue_rows=dialogue_rows,
                    case_skills=case_skills,
                )
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], case_follow_up_message),
                )
                connection.commit()
                return AssessmentTurnReply(
                    session_code=session_code,
                    session_id=session_row["id"],
                    session_case_id=plan.current_session_case_id,
                    case_title=plan.current_case_title,
                    case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    message=case_follow_up_message,
                    case_completed=False,
                    assessment_completed=False,
                    result_status=None,
                    completion_score=None,
                    evaluator_summary=None,
                    case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                    case_started_at=plan.current_case_started_at,
                    case_time_remaining_seconds=self._get_remaining_case_seconds(
                        plan.current_case_started_at,
                        plan.current_case_time_limit_minutes,
                    ),
                    is_dialog_case=is_dialog_case,
                    pending_auto_finish=False,
                    auto_finish_delay_ms=None,
                    **history_fields,
                )

            if max_user_messages is not None and user_message_count > max_user_messages:
                auto_finish_turn = DeepSeekTurnResult(
                    assistant_message=self.CASE_MESSAGE_LIMIT_REACHED_TEXT,
                    is_case_complete=True,
                    result_status="passed",
                    completion_score=None,
                    evaluator_summary="",
                )
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (plan.current_session_case_id, session_row["id"], auto_finish_turn.assistant_message),
                )
                connection.commit()
                return AssessmentTurnReply(
                    session_code=session_code,
                    session_id=session_row["id"],
                    session_case_id=plan.current_session_case_id,
                    case_title=plan.current_case_title,
                    case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    message=auto_finish_turn.assistant_message,
                    case_completed=False,
                    assessment_completed=False,
                    result_status=None,
                    completion_score=None,
                    evaluator_summary=None,
                    case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                    case_started_at=plan.current_case_started_at,
                    case_time_remaining_seconds=self._get_remaining_case_seconds(
                        plan.current_case_started_at,
                        plan.current_case_time_limit_minutes,
                    ),
                    is_dialog_case=is_dialog_case,
                    pending_auto_finish=True,
                    auto_finish_delay_ms=self.CASE_AUTO_FINISH_DELAY_MS,
                    **history_fields,
                )

            if str(methodical_context.get("interactivity_mode") or "").strip().lower() == "1 ход" and user_message_count >= 1:
                connection.execute(
                    """
                    INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                    VALUES (%s, %s, 'assistant', %s)
                    """,
                    (
                        plan.current_session_case_id,
                        session_row["id"],
                        "Ответ зафиксирован. Завершаем кейс автоматически.",
                    ),
                )
                connection.commit()
                return AssessmentTurnReply(
                    session_code=session_code,
                    session_id=session_row["id"],
                    session_case_id=plan.current_session_case_id,
                    case_title=plan.current_case_title,
                    case_number=plan.current_case_number,
                    total_cases=plan.total_cases,
                    message="Ответ зафиксирован. Завершаем кейс автоматически.",
                    case_completed=False,
                    assessment_completed=False,
                    result_status=None,
                    completion_score=None,
                    evaluator_summary=None,
                    case_time_limit_minutes=plan.current_case_time_limit_minutes,
                    planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                    case_started_at=plan.current_case_started_at,
                    case_time_remaining_seconds=self._get_remaining_case_seconds(
                        plan.current_case_started_at,
                        plan.current_case_time_limit_minutes,
                    ),
                    is_dialog_case=False,
                    pending_auto_finish=True,
                    auto_finish_delay_ms=self.CASE_AUTO_FINISH_DELAY_MS,
                    **history_fields,
                )

            turn = deepseek_client.evaluate_case_turn(
                system_prompt=prompt_row["final_prompt_text"] if prompt_row else "",
                dialogue=[{"role": row["role"], "content": row["message_text"]} for row in dialogue_rows],
                case_title=case_row["title"],
                case_skills=case_skills,
                user_identifier=str(session_row["user_id"]),
                interactivity_mode=methodical_context.get("interactivity_mode"),
                format_control_rules=methodical_context.get("format_control_rules"),
                recommended_answer_length=methodical_context.get("recommended_answer_length"),
                fallback_user_message=message,
                role_name=role_name,
                position=session_row["raw_position"] or session_row["job_description"],
                duties=session_row["normalized_duties"] or session_row["raw_duties"],
                company_industry=session_row["company_industry"],
                user_profile=user_profile,
            )

            if self._needs_non_repeating_follow_up(turn.assistant_message, dialogue_rows):
                turn.assistant_message = self._build_non_repeating_follow_up(
                    repeated_message=turn.assistant_message,
                    user_message=message,
                    dialogue_rows=dialogue_rows,
                    case_skills=case_skills,
                    interactivity_mode=methodical_context.get("interactivity_mode"),
                )

            connection.execute(
                """
                INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                VALUES (%s, %s, 'assistant', %s)
                """,
                (plan.current_session_case_id, session_row["id"], turn.assistant_message),
            )

            if turn.is_case_complete:
                operation_progress_service.advance(
                    progress_operation_id,
                    1,
                    title="Проверяем завершенный кейс",
                    message="Фиксируем результат кейса и подготавливаем следующий этап.",
                )
                return self._complete_case_and_continue(
                    connection=connection,
                    session_row=session_row,
                    plan=plan,
                    turn=turn,
                    session_code=session_code,
                    time_expired=False,
                    progress_operation_id=progress_operation_id,
                )

            connection.commit()
            return AssessmentTurnReply(
                session_code=session_code,
                session_id=session_row["id"],
                session_case_id=plan.current_session_case_id,
                case_title=plan.current_case_title,
                case_number=plan.current_case_number,
                total_cases=plan.total_cases,
                message=turn.assistant_message,
                case_completed=False,
                assessment_completed=False,
                result_status=None,
                completion_score=None,
                evaluator_summary=None,
                case_time_limit_minutes=plan.current_case_time_limit_minutes,
                planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                case_started_at=plan.current_case_started_at,
                case_time_remaining_seconds=self._get_remaining_case_seconds(
                    plan.current_case_started_at,
                    plan.current_case_time_limit_minutes,
                ),
                is_dialog_case=True,
                **history_fields,
            )

    def _complete_case_and_continue(
        self,
        *,
        connection,
        session_row,
        plan: AssessmentSessionPlan,
        turn: DeepSeekTurnResult,
        session_code: str,
        time_expired: bool,
        progress_operation_id: str | None = None,
    ) -> AssessmentTurnReply:
        self._finish_case(
            connection=connection,
            session_id=session_row["id"],
            session_case_id=plan.current_session_case_id,
            user_id=session_row["user_id"],
            turn=turn,
        )
        completed_case_row = self._get_case_for_session_case(connection, plan.current_session_case_id)
        completed_case_context = self._get_personalized_case_context(connection, plan.current_session_case_id, completed_case_row)
        completed_case_task = self._get_personalized_case_task(connection, plan.current_session_case_id, completed_case_row)
        completed_user_answer = self._get_case_user_messages_text(connection, plan.current_session_case_id)
        operation_progress_service.advance(
            progress_operation_id,
            2,
            title="Уточняем сигналы по кейсу",
            message="Строим MBTI-сигналы и, если нужно, готовим уточняющие вопросы по текущему кейсу.",
        )
        mbti_case_result, mbti_followup_questions = mbti_assessment_service.evaluate_case(
            session_case_id=plan.current_session_case_id,
            case_title=plan.current_case_title or completed_case_row["title"],
            case_number=plan.current_case_number,
            total_cases=plan.total_cases,
            case_context=completed_case_context,
            case_task=completed_case_task,
            user_answer=completed_user_answer,
        )
        mbti_assessment_service.save_case_result(
            connection,
            session_case_id=plan.current_session_case_id,
            case_result=mbti_case_result,
            followup_questions=mbti_followup_questions,
        )
        if mbti_followup_questions:
            operation_progress_service.advance(
                progress_operation_id,
                3,
                title="Готовим уточняющие вопросы",
                message="Остаемся на текущем кейсе и задаем короткие уточнения, чтобы не терять контекст ответа.",
            )
            followup_prompt = self._build_mbti_followup_prompt(mbti_followup_questions, 0)
            connection.execute(
                """
                INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                VALUES (%s, %s, 'assistant', %s)
                """,
                (plan.current_session_case_id, session_row["id"], followup_prompt),
            )
            connection.commit()
            return AssessmentTurnReply(
                session_code=session_code,
                session_id=session_row["id"],
                session_case_id=plan.current_session_case_id,
                case_title=plan.current_case_title,
                case_number=plan.current_case_number,
                total_cases=plan.total_cases,
                message=turn.assistant_message + "\n\n" + followup_prompt,
                case_completed=False,
                assessment_completed=False,
                result_status=None,
                completion_score=None,
                evaluator_summary=None,
                case_time_limit_minutes=plan.current_case_time_limit_minutes,
                planned_case_duration_minutes=plan.current_case_planned_duration_minutes,
                case_started_at=plan.current_case_started_at,
                case_time_remaining_seconds=None,
                time_expired=time_expired,
                is_dialog_case=self._get_is_dialog_case_for_session_case(connection, plan.current_session_case_id),
                mbti_case_result=mbti_case_result,
                mbti_followup_questions=mbti_followup_questions,
                mbti_followup_pending=True,
                mbti_followup_index=1,
                mbti_followup_total=len(mbti_followup_questions),
                **self._get_session_case_history_fields(connection, plan.current_session_case_id),
            )

        return self._advance_after_completed_case(
            connection=connection,
            session_row=session_row,
            completed_plan=plan,
            session_code=session_code,
            completion_message=turn.assistant_message,
            result_status=turn.result_status,
            time_expired=time_expired,
            mbti_case_result=mbti_case_result,
            mbti_followup_questions=mbti_followup_questions,
            progress_operation_id=progress_operation_id,
        )

    def _finish_case(
        self,
        *,
        connection,
        session_id: int,
        session_case_id: int,
        user_id: int,
        turn: DeepSeekTurnResult,
    ) -> None:
        result_status = turn.result_status if turn.result_status in {"passed", "skipped"} else "passed"
        time_row = connection.execute(
            """
            SELECT started_at
            FROM session_cases
            WHERE id = %s
            """,
            (session_case_id,),
        ).fetchone()
        completed_at = self._utc_now()
        actual_duration_seconds = self._calculate_actual_duration_seconds(
            time_row["started_at"] if time_row else None,
            completed_at,
        )
        connection.execute(
            """
            UPDATE session_cases
            SET status = 'answered',
                completed_at = %s,
                actual_duration_seconds = %s,
                failed_at = NULL
            WHERE id = %s
            """,
            (completed_at, actual_duration_seconds, session_case_id),
        )
        connection.execute(
            """
            INSERT INTO session_case_results (
                session_case_id, session_id, user_id, result_status, completion_score, evaluator_summary, passed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_case_id)
            DO UPDATE SET
                result_status = EXCLUDED.result_status,
                completion_score = EXCLUDED.completion_score,
                evaluator_summary = EXCLUDED.evaluator_summary,
                passed_at = EXCLUDED.passed_at
            """,
            (
                session_case_id,
                session_id,
                user_id,
                result_status,
                None,
                None,
                completed_at if result_status == "passed" else None,
            ),
        )

        skill_rows = connection.execute(
            """
            SELECT skill_id
            FROM session_case_skills
            WHERE session_case_id = %s
            """,
            (session_case_id,),
        ).fetchall()
        for row in skill_rows:
            skill_status = "covered" if result_status == "passed" else "planned"
            connection.execute(
                """
                UPDATE session_case_skills
                SET coverage_status = %s
                WHERE session_case_id = %s
                  AND skill_id = %s
                """,
                (skill_status, session_case_id, row["skill_id"]),
            )
            connection.execute(
                """
                UPDATE session_skills
                SET status = %s,
                    completed_case_count = completed_case_count + 1,
                    covered_at = CASE WHEN %s = 'covered' THEN %s ELSE covered_at END
                WHERE session_id = %s
                  AND skill_id = %s
                """,
                (skill_status, skill_status, completed_at, session_id, row["skill_id"]),
            )
            connection.execute(
                """
                UPDATE user_skill_coverage
                SET status = %s,
                    covered_at = CASE WHEN %s = 'covered' THEN %s ELSE covered_at END
                WHERE user_id = %s
                  AND skill_id = %s
                  AND source_case_registry_id = (
                      SELECT case_registry_id FROM session_cases WHERE id = %s
                  )
                """,
                (skill_status, skill_status, completed_at, user_id, row["skill_id"], session_case_id),
            )

    def _get_case_for_session_case(self, connection, session_case_id: int):
        return connection.execute(
            """
            SELECT
                cr.id,
                cr.title,
                cr.case_id_code AS case_code,
                COALESCE(txt.case_text_code, 'TXT-' || cr.case_id_code) AS text_code,
                p.type_code,
                txt.intro_context,
                txt.task_for_user,
                txt.facts_data,
                txt.trigger_details,
                txt.constraints_text,
                txt.stakes_text,
                txt.base_variant_text,
                txt.hard_variant_text,
                cr.context_domain AS domain_context,
                txt.personalization_variables,
                cr.estimated_time_min AS estimated_minutes,
                COALESCE(sc.planned_duration_minutes, cr.estimated_time_min) AS planned_duration_minutes
            FROM session_cases sc
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            LEFT JOIN case_type_passports p ON p.id = cr.case_type_passport_id
            LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
            WHERE sc.id = %s
            """,
            (session_case_id,),
        ).fetchone()

    def _get_personalized_case_context(self, connection, session_case_id: int, case_row) -> str:
        prompt_row = connection.execute(
            """
            SELECT user_prompt
            FROM session_prompts
            WHERE session_case_id = %s
              AND prompt_type = 'case_dialog'
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_case_id,),
        ).fetchone()
        if prompt_row and prompt_row["user_prompt"]:
            context_text, _task_text = deepseek_client.split_user_case_message(prompt_row["user_prompt"])
            return context_text or str(prompt_row["user_prompt"]).strip()
        return case_row["intro_context"] or case_row["domain_context"] or ""

    def _get_personalized_case_task(self, connection, session_case_id: int, case_row) -> str:
        prompt_row = connection.execute(
            """
            SELECT user_prompt
            FROM session_prompts
            WHERE session_case_id = %s
              AND prompt_type = 'case_dialog'
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_case_id,),
        ).fetchone()
        if prompt_row and prompt_row["user_prompt"]:
            _context_text, task_text = deepseek_client.split_user_case_message(prompt_row["user_prompt"])
            if task_text:
                return task_text
        return case_row["task_for_user"] or ""

    def _get_case_skill_names(self, connection, session_case_id: int) -> list[str]:
        rows = connection.execute(
            """
            SELECT s.skill_name
            FROM session_case_skills scs
            JOIN skills s ON s.id = scs.skill_id
            WHERE scs.session_case_id = %s
            ORDER BY s.id ASC
            """,
            (session_case_id,),
        ).fetchall()
        return [row["skill_name"] for row in rows if row["skill_name"]]

    def _get_case_user_messages_text(self, connection, session_case_id: int) -> str:
        rows = connection.execute(
            """
            SELECT message_text
            FROM session_case_messages
            WHERE session_case_id = %s
              AND role = 'user'
            ORDER BY id ASC
            """,
            (session_case_id,),
        ).fetchall()
        return "\n\n".join(
            str(row["message_text"] or "").strip()
            for row in rows
            if str(row["message_text"] or "").strip()
        ).strip()

    def _get_case_user_turn_count(self, connection, session_case_id: int) -> int:
        row = connection.execute(
            """
            SELECT COUNT(*)::int AS total
            FROM session_case_messages
            WHERE session_case_id = %s
              AND role = 'user'
            """,
            (session_case_id,),
        ).fetchone()
        return int(row["total"]) if row else 0

    def _get_session_case_history_fields(self, connection, session_case_id: int) -> dict:
        row = connection.execute(
            """
            SELECT
                history_match_case,
                history_match_case_text,
                history_match_type,
                history_last_used_at,
                history_use_count,
                history_flag,
                history_is_new
            FROM session_cases
            WHERE id = %s
            """,
            (session_case_id,),
        ).fetchone()
        if row is None:
            return {
                "history_match_case": False,
                "history_match_case_text": False,
                "history_match_type": False,
                "history_last_used_at": None,
                "history_use_count": 0,
                "history_flag": None,
                "history_is_new": False,
            }
        return dict(row)

    def _build_plan(self, connection, session_id: int, session_code: str) -> AssessmentSessionPlan:
        case_rows = connection.execute(
            """
            SELECT
                sc.id,
                sc.status,
                sc.started_at,
                sc.planned_duration_minutes,
                cr.title,
                COALESCE(sc.planned_duration_minutes, cr.estimated_time_min) AS effective_planned_duration_minutes
            FROM session_cases sc
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            WHERE sc.session_id = %s
            ORDER BY sc.id ASC
            """,
            (session_id,),
        ).fetchall()
        total_cases = len(case_rows)
        current_index = 0
        current_case_id = None
        current_case_title = None
        current_case_time_limit_minutes = None
        current_case_planned_duration_minutes = None
        current_case_started_at = None
        for index, row in enumerate(case_rows, start=1):
            if row["status"] not in {"answered", "assessed"}:
                current_index = index
                current_case_id = row["id"]
                current_case_title = row["title"]
                current_case_time_limit_minutes = row["effective_planned_duration_minutes"]
                current_case_planned_duration_minutes = row["effective_planned_duration_minutes"]
                current_case_started_at = row["started_at"]
                break
        if current_case_id is None and case_rows:
            current_index = total_cases
        return AssessmentSessionPlan(
            session_id=session_id,
            session_code=session_code,
            current_session_case_id=current_case_id,
            current_case_title=current_case_title,
            current_case_number=current_index,
            total_cases=total_cases,
            current_case_time_limit_minutes=current_case_time_limit_minutes,
            current_case_planned_duration_minutes=current_case_planned_duration_minutes,
            current_case_started_at=current_case_started_at,
            opening_message=None,
        )

    def _is_time_expired(self, started_at: datetime | None, estimated_minutes: int | None) -> bool:
        if started_at is None or not estimated_minutes:
            return False
        return self._utc_now() >= started_at + timedelta(minutes=estimated_minutes)

    def _get_remaining_case_seconds(self, started_at: datetime | None, estimated_minutes: int | None) -> int | None:
        if started_at is None or not estimated_minutes:
            return None
        remaining = int((started_at + timedelta(minutes=estimated_minutes) - self._utc_now()).total_seconds())
        return max(0, remaining)

    def _get_case_number_for_session_case(self, connection, session_id: int, session_case_id: int) -> int:
        rows = connection.execute(
            """
            SELECT id
            FROM session_cases
            WHERE session_id = %s
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
        for index, row in enumerate(rows, start=1):
            if row["id"] == session_case_id:
                return index
        return 0

    def _get_pending_mbti_followup(self, connection, session_id: int) -> dict | None:
        return connection.execute(
            """
            SELECT
                scr.session_case_id,
                scr.mbti_case_json,
                scr.mbti_followup_questions,
                scr.mbti_followup_answers,
                sc.started_at,
                sc.planned_duration_minutes,
                cr.estimated_time_min AS estimated_minutes,
                cr.title
            FROM session_case_results scr
            JOIN session_cases sc ON sc.id = scr.session_case_id
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            WHERE sc.session_id = %s
              AND jsonb_array_length(COALESCE(scr.mbti_followup_questions, '[]'::jsonb)) > jsonb_array_length(COALESCE(scr.mbti_followup_answers, '[]'::jsonb))
            ORDER BY sc.id ASC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()

    def _build_mbti_followup_prompt(self, questions: list[str], answered_count: int) -> str:
        if answered_count >= len(questions):
            return self.MBTI_FOLLOWUP_COMPLETE_TEXT
        prefix = self.MBTI_FOLLOWUP_INTRO_TEXT if answered_count == 0 else "Спасибо. И еще один короткий уточняющий вопрос по этому же кейсу."
        question = questions[answered_count]
        return (
            prefix
            + "\n\n"
            + "Уточняющий вопрос "
            + str(answered_count + 1)
            + " из "
            + str(len(questions))
            + ":\n"
            + question
        )

    def _advance_after_completed_case(
        self,
        *,
        connection,
        session_row,
        completed_plan: AssessmentSessionPlan,
        session_code: str,
        completion_message: str,
        result_status: str | None,
        time_expired: bool,
        mbti_case_result: dict[str, object] | None,
        mbti_followup_questions: list[str] | None,
        progress_operation_id: str | None = None,
    ) -> AssessmentTurnReply:
        next_plan = self._build_plan(connection, session_row["id"], session_code)
        if next_plan.current_session_case_id is None:
            operation_progress_service.advance(
                progress_operation_id,
                3,
                title="Собираем итоговый профиль",
                message="Завершаем assessment-сессию, считаем итоговые оценки и формируем финальный MBTI-профиль.",
            )
            finished_at = self._utc_now()
            connection.execute(
                """
                UPDATE user_sessions
                SET status = 'completed',
                    finished_at = COALESCE(finished_at, %s)
                WHERE id = %s
                """,
                (finished_at, session_row["id"]),
            )
            for agent in competency_assessment_agents:
                agent.evaluate_session(
                    connection=connection,
                    session_id=session_row["id"],
                    user_id=session_row["user_id"],
                )
            final_message = completion_message + " Оценка по всем кейсам завершена."
            mbti_summary = mbti_assessment_service.summarize_session(connection, session_id=session_row["id"])
            connection.commit()
            return AssessmentTurnReply(
                session_code=session_code,
                session_id=session_row["id"],
                session_case_id=completed_plan.current_session_case_id,
                case_title=completed_plan.current_case_title,
                case_number=completed_plan.current_case_number,
                total_cases=completed_plan.total_cases,
                message=final_message,
                case_completed=True,
                assessment_completed=True,
                result_status=result_status,
                completion_score=None,
                evaluator_summary=None,
                case_time_limit_minutes=completed_plan.current_case_time_limit_minutes,
                planned_case_duration_minutes=completed_plan.current_case_planned_duration_minutes,
                case_started_at=completed_plan.current_case_started_at,
                case_time_remaining_seconds=0
                if time_expired
                else self._get_remaining_case_seconds(
                    completed_plan.current_case_started_at,
                    completed_plan.current_case_time_limit_minutes,
                ),
                time_expired=time_expired,
                is_dialog_case=self._get_is_dialog_case_for_session_case(connection, completed_plan.current_session_case_id),
                mbti_case_result=mbti_case_result,
                mbti_followup_questions=mbti_followup_questions,
                mbti_summary=mbti_summary,
                **self._get_session_case_history_fields(connection, completed_plan.current_session_case_id),
            )

        operation_progress_service.advance(
            progress_operation_id,
            3,
            title="Открываем следующий кейс",
            message="Текущий кейс завершен. Подготавливаем следующий кейс без лишнего ожидания.",
        )
        next_case_row = self._get_case_for_session_case(connection, next_plan.current_session_case_id)
        intro_message = deepseek_client.build_opening_message(
            case_title=next_case_row["title"],
            case_context=self._get_personalized_case_context(connection, next_plan.current_session_case_id, next_case_row),
            case_task=self._get_personalized_case_task(connection, next_plan.current_session_case_id, next_case_row),
        )
        connection.execute(
            """
            INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
            VALUES (%s, %s, 'assistant', %s)
            """,
            (next_plan.current_session_case_id, session_row["id"], intro_message),
        )
        connection.execute(
            """
            UPDATE session_cases
            SET status = 'shown',
                started_at = COALESCE(started_at, %s),
                paused_remaining_seconds = NULL
            WHERE id = %s
            RETURNING started_at
            """,
            (self._utc_now(), next_plan.current_session_case_id),
        ).fetchone()
        started_row = connection.execute(
            """
            SELECT started_at
            FROM session_cases
            WHERE id = %s
            """,
            (next_plan.current_session_case_id,),
        ).fetchone()
        connection.commit()
        return AssessmentTurnReply(
            session_code=session_code,
            session_id=session_row["id"],
            session_case_id=next_plan.current_session_case_id,
            case_title=next_plan.current_case_title,
            case_number=next_plan.current_case_number,
            total_cases=next_plan.total_cases,
            message=completion_message + "\n\nСледующий кейс:\n" + intro_message,
            case_completed=True,
            assessment_completed=False,
            result_status=result_status,
            completion_score=None,
            evaluator_summary=None,
            case_time_limit_minutes=next_plan.current_case_time_limit_minutes,
            planned_case_duration_minutes=next_plan.current_case_planned_duration_minutes,
            case_started_at=started_row["started_at"] if started_row else next_plan.current_case_started_at,
            case_time_remaining_seconds=self._get_remaining_case_seconds(
                started_row["started_at"] if started_row else next_plan.current_case_started_at,
                next_plan.current_case_time_limit_minutes,
            ),
            time_expired=time_expired,
            is_dialog_case=deepseek_client._is_dialog_interactivity_mode(
                self._get_case_methodical_context(connection, next_case_row).get("interactivity_mode"),
            ),
            mbti_case_result=mbti_case_result,
            mbti_followup_questions=mbti_followup_questions,
            **self._get_session_case_history_fields(connection, next_plan.current_session_case_id),
        )

    def _handle_pending_mbti_followup(
        self,
        *,
        connection,
        session_row,
        session_code: str,
        message: str,
        pending_row,
        progress_operation_id: str | None = None,
    ) -> AssessmentTurnReply:
        raw_questions = pending_row["mbti_followup_questions"] or []
        raw_answers = pending_row["mbti_followup_answers"] or []
        questions = [str(item or "").strip() for item in raw_questions if str(item or "").strip()]
        answers = [str(item or "").strip() for item in raw_answers if str(item or "").strip()]
        if not questions or len(answers) >= len(questions):
            return None

        session_case_id = pending_row["session_case_id"]
        case_number = self._get_case_number_for_session_case(connection, session_row["id"], session_case_id)
        history_fields = self._get_session_case_history_fields(connection, session_case_id)
        effective_minutes = pending_row["planned_duration_minutes"] or pending_row["estimated_minutes"]

        if message in {"__timeout__", "__finish_case__", "__auto_finish_case__"}:
            prompt = self._build_mbti_followup_prompt(questions, len(answers))
            connection.commit()
            return AssessmentTurnReply(
                session_code=session_code,
                session_id=session_row["id"],
                session_case_id=session_case_id,
                case_title=pending_row["title"],
                case_number=case_number,
                total_cases=self._build_plan(connection, session_row["id"], session_code).total_cases,
                message=prompt,
                case_completed=False,
                assessment_completed=False,
                case_time_limit_minutes=effective_minutes,
                planned_case_duration_minutes=effective_minutes,
                case_started_at=pending_row["started_at"],
                case_time_remaining_seconds=None,
                is_dialog_case=False,
                mbti_followup_pending=True,
                mbti_followup_index=len(answers) + 1,
                mbti_followup_total=len(questions),
                **history_fields,
            )

        user_answer = str(message or "").strip()
        if not user_answer:
            prompt = self._build_mbti_followup_prompt(questions, len(answers))
            connection.commit()
            return AssessmentTurnReply(
                session_code=session_code,
                session_id=session_row["id"],
                session_case_id=session_case_id,
                case_title=pending_row["title"],
                case_number=case_number,
                total_cases=self._build_plan(connection, session_row["id"], session_code).total_cases,
                message=prompt,
                case_completed=False,
                assessment_completed=False,
                case_time_limit_minutes=effective_minutes,
                planned_case_duration_minutes=effective_minutes,
                case_started_at=pending_row["started_at"],
                case_time_remaining_seconds=None,
                is_dialog_case=False,
                mbti_followup_pending=True,
                mbti_followup_index=len(answers) + 1,
                mbti_followup_total=len(questions),
                **history_fields,
            )

        answers.append(user_answer)
        connection.execute(
            """
            UPDATE session_case_results
            SET mbti_followup_answers = %s::jsonb
            WHERE session_case_id = %s
            """,
            (json.dumps(answers, ensure_ascii=False), session_case_id),
        )
        connection.execute(
            """
            INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
            VALUES (%s, %s, 'user', %s)
            """,
            (session_case_id, session_row["id"], user_answer),
        )

        if len(answers) < len(questions):
            operation_progress_service.advance(
                progress_operation_id,
                3,
                title="Показываем следующее уточнение",
                message="Сохраняем ответ и задаем следующий короткий вопрос по этому же кейсу.",
            )
            prompt = self._build_mbti_followup_prompt(questions, len(answers))
            connection.execute(
                """
                INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
                VALUES (%s, %s, 'assistant', %s)
                """,
                (session_case_id, session_row["id"], prompt),
            )
            connection.commit()
            return AssessmentTurnReply(
                session_code=session_code,
                session_id=session_row["id"],
                session_case_id=session_case_id,
                case_title=pending_row["title"],
                case_number=case_number,
                total_cases=self._build_plan(connection, session_row["id"], session_code).total_cases,
                message=prompt,
                case_completed=False,
                assessment_completed=False,
                case_time_limit_minutes=effective_minutes,
                planned_case_duration_minutes=effective_minutes,
                case_started_at=pending_row["started_at"],
                case_time_remaining_seconds=None,
                is_dialog_case=False,
                mbti_followup_pending=True,
                mbti_followup_index=len(answers) + 1,
                mbti_followup_total=len(questions),
                **history_fields,
            )

        completion_message = self.MBTI_FOLLOWUP_COMPLETE_TEXT
        connection.execute(
            """
            INSERT INTO session_case_messages (session_case_id, session_id, role, message_text)
            VALUES (%s, %s, 'assistant', %s)
            """,
            (session_case_id, session_row["id"], completion_message),
        )
        completed_plan = AssessmentSessionPlan(
            session_id=session_row["id"],
            session_code=session_code,
            current_session_case_id=session_case_id,
            current_case_title=pending_row["title"],
            current_case_number=case_number,
            total_cases=self._build_plan(connection, session_row["id"], session_code).total_cases,
            current_case_time_limit_minutes=effective_minutes,
            current_case_planned_duration_minutes=effective_minutes,
            current_case_started_at=pending_row["started_at"],
            opening_message=None,
        )
        return self._advance_after_completed_case(
            connection=connection,
            session_row=session_row,
            completed_plan=completed_plan,
            session_code=session_code,
            completion_message=completion_message,
            result_status="passed",
            time_expired=False,
            mbti_case_result=None,
            mbti_followup_questions=None,
            progress_operation_id=progress_operation_id,
        )

    def _pause_case_timer(self, connection, session_case_id: int) -> int | None:
        row = connection.execute(
            """
            SELECT sc.started_at, sc.paused_remaining_seconds, cr.estimated_time_min AS estimated_minutes
            FROM session_cases sc
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            WHERE sc.id = %s
            LIMIT 1
            """,
            (session_case_id,),
        ).fetchone()
        if row is None:
            return None
        if row["paused_remaining_seconds"] is not None:
            return int(row["paused_remaining_seconds"])
        remaining = self._get_remaining_case_seconds(row["started_at"], row["estimated_minutes"])
        if remaining is None:
            return None
        connection.execute(
            """
            UPDATE session_cases
            SET paused_remaining_seconds = %s
            WHERE id = %s
            """,
            (remaining, session_case_id),
        )
        return remaining

    def _resume_case_timer(self, connection, session_case_id: int) -> datetime | None:
        row = connection.execute(
            """
            SELECT sc.started_at, sc.paused_remaining_seconds, cr.estimated_time_min AS estimated_minutes
            FROM session_cases sc
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            WHERE sc.id = %s
            LIMIT 1
            """,
            (session_case_id,),
        ).fetchone()
        if row is None:
            return None
        paused_remaining_seconds = row["paused_remaining_seconds"]
        estimated_minutes = row["estimated_minutes"]
        if paused_remaining_seconds is None or not estimated_minutes:
            return row["started_at"]
        total_seconds = max(0, int(estimated_minutes) * 60)
        elapsed_seconds = max(0, total_seconds - int(paused_remaining_seconds))
        resumed_started_at = self._utc_now() - timedelta(seconds=elapsed_seconds)
        updated = connection.execute(
            """
            UPDATE session_cases
            SET started_at = %s,
                paused_remaining_seconds = NULL
            WHERE id = %s
            RETURNING started_at
            """,
            (resumed_started_at, session_case_id),
        ).fetchone()
        return updated["started_at"] if updated else resumed_started_at

    def pause_assessment_dialogue(self, session_code: str) -> None:
        with get_connection() as connection:
            session_row = connection.execute(
                """
                SELECT id
                FROM user_sessions
                WHERE session_code = %s
                  AND assessment_code = 'competencies_4k'
                LIMIT 1
                """,
                (session_code,),
            ).fetchone()
            if session_row is None:
                raise ValueError("Assessment session not found")
            plan = self._build_plan(connection, session_row["id"], session_code)
            if plan.current_session_case_id is None:
                return
            self._pause_case_timer(connection, plan.current_session_case_id)
            connection.commit()

    def _enrich_candidate_case_pool_with_history(self, *, connection, user_id: int, candidate_rows) -> list[dict]:
        history_rows = connection.execute(
            """
            SELECT
                cr.case_id_code AS case_code,
                COALESCE(txt.case_text_code, 'TXT-' || cr.case_id_code) AS text_code,
                p.type_code,
                sc.status,
                COALESCE(scr.passed_at, scr.recorded_at, sc.completed_at, sc.started_at, us.started_at) AS used_at
            FROM session_cases sc
            JOIN user_sessions us ON us.id = sc.session_id
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
            LEFT JOIN case_type_passports p ON p.id = cr.case_type_passport_id
            LEFT JOIN session_case_results scr ON scr.session_case_id = sc.id
            WHERE us.user_id = %s
            ORDER BY COALESCE(scr.passed_at, scr.recorded_at, sc.completed_at, sc.started_at, us.started_at) DESC NULLS LAST, sc.id DESC
            """,
            (user_id,),
        ).fetchall()

        case_history: dict[str, dict] = {}
        text_history: dict[str, dict] = {}
        type_history: dict[str, dict] = {}

        for row in history_rows:
            used_at = row["used_at"]
            status = row["status"]
            case_code = row["case_code"]
            text_code = row["text_code"]
            type_code = row["type_code"]

            if case_code:
                case_entry = case_history.setdefault(case_code, {"last_used_at": used_at, "use_count": 0, "latest_status": status})
                case_entry["use_count"] += 1
                if case_entry["last_used_at"] is None or (used_at and used_at > case_entry["last_used_at"]):
                    case_entry["last_used_at"] = used_at
                    case_entry["latest_status"] = status

            if text_code:
                text_entry = text_history.setdefault(text_code, {"last_used_at": used_at, "use_count": 0, "latest_status": status})
                text_entry["use_count"] += 1
                if text_entry["last_used_at"] is None or (used_at and used_at > text_entry["last_used_at"]):
                    text_entry["last_used_at"] = used_at
                    text_entry["latest_status"] = status

            if type_code:
                type_entry = type_history.setdefault(type_code, {"last_used_at": used_at, "use_count": 0, "latest_status": status})
                type_entry["use_count"] += 1
                if type_entry["last_used_at"] is None or (used_at and used_at > type_entry["last_used_at"]):
                    type_entry["last_used_at"] = used_at
                    type_entry["latest_status"] = status

        recent_threshold = self._utc_now() - timedelta(days=self.RECENT_CASE_DAYS)
        enriched: list[dict] = []

        for raw_row in candidate_rows:
            row = dict(raw_row)
            case_meta = case_history.get(row["case_code"])
            text_meta = text_history.get(row["text_code"])
            type_meta = type_history.get(row["type_code"])

            history_match_case = case_meta is not None
            history_match_case_text = text_meta is not None
            history_match_type = type_meta is not None

            last_used_candidates = [
                meta["last_used_at"]
                for meta in (case_meta, text_meta, type_meta)
                if meta and meta.get("last_used_at") is not None
            ]
            last_used_at = max(last_used_candidates) if last_used_candidates else None
            use_count = max(
                [meta["use_count"] for meta in (case_meta, text_meta) if meta] or [0]
            )

            exact_status = (case_meta or text_meta or {}).get("latest_status")
            type_last_used = type_meta["last_used_at"] if type_meta else None
            type_recent = bool(type_last_used and type_last_used >= recent_threshold)
            exact_recent = bool(last_used_at and last_used_at >= recent_threshold)

            if not history_match_case and not history_match_case_text and not history_match_type:
                history_flag = "new"
            elif (history_match_case or history_match_case_text) and exact_status in {"shown", "answered", "assessed"}:
                history_flag = "used_recently" if exact_recent else "repeat_blocked"
            elif history_match_case or history_match_case_text:
                history_flag = "repeat_allowed"
            elif history_match_type and type_recent:
                history_flag = "same_type_recently"
            else:
                history_flag = "used_before"

            row.update(
                {
                    "history_match_case": history_match_case,
                    "history_match_case_text": history_match_case_text,
                    "history_match_type": history_match_type,
                    "last_used_at": last_used_at,
                    "use_count": use_count,
                    "history_flag": history_flag,
                    "latest_history_status": exact_status or (type_meta or {}).get("latest_status"),
                }
            )
            enriched.append(row)

        return enriched

    def _select_minimum_cases(self, candidate_rows, required_skill_ids: list[int]) -> list[dict]:
        required_order = list(dict.fromkeys(required_skill_ids))
        required_index = {skill_id: idx for idx, skill_id in enumerate(required_order)}
        full_mask = (1 << len(required_order)) - 1
        midpoint = (self.MIN_SESSION_DURATION_MIN + self.MAX_SESSION_DURATION_MIN) / 2
        duration_limit = self.MAX_SESSION_DURATION_MIN + 20

        def flag_priority(row: dict) -> int:
            return {
                "new": 0,
                "used_before": 1,
                "same_type_recently": 2,
                "used_recently": 3,
                "repeat_allowed": 4,
                "repeat_blocked": 5,
            }.get(row.get("history_flag"), 9)

        def candidate_mask(row: dict) -> int:
            mask = 0
            for skill_id in row.get("skill_ids", []):
                if skill_id in required_index:
                    mask |= 1 << required_index[skill_id]
            return mask

        def solution_key(solution: dict) -> tuple:
            total_duration = solution["total_duration"]
            in_target_range = self.MIN_SESSION_DURATION_MIN <= total_duration <= self.MAX_SESSION_DURATION_MIN
            under_limit = total_duration <= self.MAX_SESSION_DURATION_MIN
            if in_target_range:
                range_rank = 0
            elif under_limit:
                range_rank = 1
            else:
                range_rank = 2
            return (
                range_rank,
                abs(total_duration - midpoint) if in_target_range else (self.MIN_SESSION_DURATION_MIN - total_duration if total_duration < self.MIN_SESSION_DURATION_MIN else total_duration - self.MAX_SESSION_DURATION_MIN),
                solution["penalty"],
                solution["case_count"],
                total_duration,
            )

        def is_better(new_solution: dict, current_solution: dict | None) -> bool:
            if current_solution is None:
                return True
            return solution_key(new_solution) < solution_key(current_solution)

        filtered_candidates = [
            dict(row, skill_mask=candidate_mask(dict(row)))
            for row in candidate_rows
            if dict(row).get("history_flag") != "repeat_blocked"
        ]
        if not filtered_candidates:
            return []

        # Keep multiple states for the same skill mask, split by duration.
        # This prevents the selector from discarding a slightly less optimal
        # partial solution that later becomes the only valid session in the
        # target 55-70 minute window.
        dp: dict[tuple[int, int], dict] = {(0, 0): {"rows": [], "total_duration": 0, "penalty": 0, "case_count": 0}}

        for raw_row in filtered_candidates:
            row = dict(raw_row)
            row_mask = row["skill_mask"]
            row_duration = row.get("planned_duration_minutes") or row.get("estimated_minutes") or 0
            snapshot = list(dp.items())
            for (_state_mask, _state_duration), current_solution in snapshot:
                current_mask = _state_mask
                new_mask = current_mask | row_mask
                new_duration = current_solution["total_duration"] + row_duration
                duplicate_type_penalty = 0
                current_type_codes = [
                    str(item.get("type_code") or "").strip().upper()
                    for item in current_solution["rows"]
                    if str(item.get("type_code") or "").strip()
                ]
                row_type_code = str(row.get("type_code") or "").strip().upper()
                if row_type_code and row_type_code in current_type_codes:
                    duplicate_type_penalty = 35
                row_penalty = flag_priority(row) * 10 + int(row.get("use_count", 0)) + duplicate_type_penalty
                new_solution = {
                    "rows": current_solution["rows"] + [row],
                    "total_duration": new_duration,
                    "penalty": current_solution["penalty"] + row_penalty,
                    "case_count": current_solution["case_count"] + 1,
                }
                if new_duration > duration_limit:
                    continue
                state_key = (new_mask, new_duration)
                if is_better(new_solution, dp.get(state_key)):
                    dp[state_key] = new_solution

        full_candidates = [
            solution
            for (mask, _duration), solution in dp.items()
            if mask == full_mask
        ]
        if not full_candidates:
            return []

        best_full = min(full_candidates, key=solution_key)

        if best_full["total_duration"] < self.MIN_SESSION_DURATION_MIN:
            extras = [
                row for row in filtered_candidates
                if row["id"] not in {item["id"] for item in best_full["rows"]}
                and row.get("history_flag") not in {"repeat_blocked", "used_recently"}
            ]
            extras.sort(
                key=lambda row: (
                    flag_priority(row),
                    row.get("planned_duration_minutes") or row.get("estimated_minutes") or 9999,
                    row.get("id") or 999999,
                )
            )
            current_rows = list(best_full["rows"])
            current_duration = best_full["total_duration"]
            current_penalty = best_full["penalty"]
            for extra in extras:
                extra_duration = extra.get("planned_duration_minutes") or extra.get("estimated_minutes") or 0
                if current_duration + extra_duration > self.MAX_SESSION_DURATION_MIN:
                    continue
                current_rows.append(extra)
                current_duration += extra_duration
                current_penalty += flag_priority(extra) * 10 + int(extra.get("use_count", 0))
                if current_duration >= self.MIN_SESSION_DURATION_MIN:
                    break
            best_full = {
                "rows": current_rows,
                "total_duration": current_duration,
                "penalty": current_penalty,
                "case_count": len(current_rows),
            }

        return best_full["rows"] if best_full["total_duration"] <= self.MAX_SESSION_DURATION_MIN else []


assessment_service = AssessmentService()
