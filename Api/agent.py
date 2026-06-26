from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from uuid import uuid4

from Api.assessment_service import assessment_service
from Api.database import get_connection
from Api.deepseek_client import deepseek_client
from Api.domain_sources import external_knowledge_service
from Api.profile_normalization import (
    build_profile_normalization_result,
    clean_position as normalize_profile_position,
    cleanup_duty_item as normalize_duty_item,
    fallback_normalize_duties_items,
    format_duties_items,
    normalize_company_industry_fallback,
    normalize_text as normalize_profile_text,
    parse_bullets as parse_bullet_list,
)
from Api.progress_service import operation_progress_service
from Api.schemas import (
    AgentReply,
    AssessmentMessageResponse,
    AssessmentStartResponse,
    UserResponse,
)


STOP_WORDS = {
    "для", "как", "это", "или", "если", "при", "что", "его", "ее", "так", "уже", "через",
    "над", "под", "без", "из", "по", "на", "от", "до", "не", "но", "и", "в", "во", "с", "со",
    "к", "ко", "а", "о", "об", "обо", "за", "мы", "вы", "они", "она", "он", "их", "наш",
    "ваш", "этот", "эта", "эти", "того", "также", "рамках", "уровне", "очень", "который",
}

NO_CHANGES_PHRASES = {
    "изменений нет",
    "нет изменений",
    "нет изменений в профиле",
    "ничего не изменилось",
    "ничего не поменялось",
    "без изменений",
    "все без изменений",
    "все по прежнему",
    "все по-старому",
    "все осталось как есть",
    "оставить как есть",
    "оставить без изменений",
    "ничего обновлять не нужно",
    "обновлять не нужно",
    "обновлять не надо",
    "не требуется",
    "не нужно",
    "не надо",
    "не нужно обновлять",
    "не надо обновлять",
    "не нужно менять",
    "не надо менять",
    "заполнять не нужно",
    "профиль заполнять не нужно",
    "профиль не нужно заполнять",
    "профиль актуален",
    "все актуально",
    "все актуально у меня",
    "должность актуальна",
    "обязанности актуальны",
    "должность и обязанности актуальны",
    "ничего менять не нужно",
    "ничего менять не надо",
}

ROLE_HINTS = {
    "linear_employee": {
        "инструкция", "чек", "чеклист", "тикет", "заявка", "обработка", "операцион", "регламент",
        "поддержк", "диагност", "статус", "эскалац", "сервис", "оператор", "исполн", "sla",
        "фиксир", "уточня", "проверя", "обновля", "сопровож",
    },
    "manager": {
        "команда", "координац", "приоритет", "план", "срок", "ресурс", "стейкхолдер", "roadmap",
        "бэклог", "встреч", "декомпоз", "контроль", "наставнич", "управлен", "проект", "delivery",
        "распределя", "согласовы", "зависимост", "загрузка",
    },
    "leader": {
        "стратег", "инвести", "бюджет", "трансформац", "портфель", "организац", "культура",
        "партнер", "регулятор", "бизнес", "направлен", "kpi", "okr", "кризис", "видение", "governance",
        "изменени", "масштаб", "политик", "система", "риск", "инициатив",
    },
}

POSITION_ROLE_HINTS = {
    "linear_employee": {
        "специалист", "оператор", "ассистент", "координатор", "исполнитель", "бухгалтер", "администратор",
        "аналитик", "консультант", "инженер", "эксперт", "business analyst", "system analyst",
    },
    "manager": {
        "менеджер", "тимлид", "руководитель группы", "руководитель проекта", "супервайзер", "куратор",
        "начальник отдела", "project manager", "product manager",
    },
    "leader": {
        "директор", "head", "chief", "cpo", "ceo", "cto", "cfo", "coo", "chro", "vp",
        "вице-президент", "руководитель направления", "директор по", "руководитель департамента",
        "директор направления", "управляющий директор",
    },
}

USER_SELECT_SQL = """
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
        p.role_selected,
        p.role_selected_code,
        p.role_confidence,
        p.role_rationale,
        p.role_consistency_status,
        p.role_consistency_comment,
        p.company_context,
        p.profile_metadata,
        p.raw_input,
        p.normalized_input,
        p.role_interpretation,
        p.user_work_context,
        p.role_limits,
        p.role_vocabulary,
        p.domain_profile,
        p.role_skill_profile,
        p.adaptation_rules_for_cases,
        p.user_domain,
        p.user_processes,
        p.user_tasks,
        p.user_stakeholders,
        p.user_risks,
        p.user_constraints,
        p.user_artifacts,
        p.user_systems,
        p.user_success_metrics,
        p.data_quality_notes,
        p.domain_resolution_status,
        p.domain_confidence,
        p.profile_quality,
        p.profile_build_instruction_code,
        p.profile_build_summary,
        p.profile_build_trace,
        u.active_profile_id,
        u.phone,
        u.telegram,
        u.personal_data_consent_accepted_at,
        u.personal_data_consent_version,
        u.company_industry
    FROM users u
    LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
"""


def _is_assessment_allowed_for_user(user: UserResponse | None) -> bool:
    if user is None:
        return False
    normalized_role = str(user.job_description or "").strip().lower()
    return normalized_role != "администратор"


class ConversationMode(StrEnum):
    EXISTING_USER = "existing_user"
    NEW_USER = "new_user"


class ConversationStage(StrEnum):
    ASK_PERSONAL_DATA_CONSENT = "ask_personal_data_consent"
    ASK_POSITION = "ask_position"
    ASK_DUTIES = "ask_duties"
    ASK_ROLE = "ask_role"
    ASK_COMPANY_INDUSTRY = "ask_company_industry"
    ASK_FULL_NAME = "ask_full_name"
    ASK_TELEGRAM = "ask_telegram"
    COMPLETE = "complete"


@dataclass(slots=True)
class RoleMatch:
    role_id: int
    code: str
    name: str
    confidence: float
    rationale: str


@dataclass(slots=True)
class ConversationState:
    session_id: str
    login_identifier: str
    mode: ConversationMode
    stage: ConversationStage
    user: UserResponse | None = None
    user_id: int | None = None
    full_name: str | None = None
    position: str | None = None
    duties: str | None = None
    selected_role_id: int | None = None
    telegram: str | None = None
    consent_version: int | None = None
    consent_text: str | None = None
    company_industry: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)


def _trimmed(value: str) -> str:
    return value.strip()


def _means_no_changes(text: str) -> bool:
    normalized = " ".join(text.lower().replace("ё", "е").split())
    if any(phrase in normalized for phrase in NO_CHANGES_PHRASES):
        return True

    if normalized in {"нет", "неа", "нету", "ага нет", "нет спасибо"}:
        return True

    if re.match(r"^(нет|неа|нету)(\b|[,.!?:])", normalized):
        if any(marker in normalized for marker in {"измен", "обнов", "менять", "коррект"}):
            return True
        if any(marker in normalized for marker in {"все актуаль", "без измен", "по прежнему", "как есть"}):
            return True
        if len(normalized.split()) <= 3:
            return True

    if normalized.startswith(("все актуально", "профиль актуален", "без изменений", "оставить как есть")):
        return True

    return False


class InterviewerAgent:
    def __init__(self) -> None:
        self._sessions: dict[str, ConversationState] = {}
        self._lock = Lock()
        self._ensure_session_schema()

    def _ensure_session_schema(self) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    phone TEXT,
                    login_identifier TEXT,
                    mode TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                    full_name TEXT NULL,
                    position TEXT NULL,
                    duties TEXT NULL,
                    selected_role_id INTEGER NULL,
                    telegram TEXT NULL,
                    consent_version INTEGER NULL,
                    consent_text TEXT NULL,
                    company_industry TEXT NULL,
                    history_json TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                ALTER TABLE agent_conversation_sessions
                ADD COLUMN IF NOT EXISTS telegram TEXT NULL
                """
            )
            connection.execute(
                """
                ALTER TABLE agent_conversation_sessions
                ADD COLUMN IF NOT EXISTS login_identifier TEXT
                """
            )
            connection.execute(
                """
                ALTER TABLE agent_conversation_sessions
                ALTER COLUMN phone DROP NOT NULL
                """
            )
            connection.execute(
                """
                ALTER TABLE agent_conversation_sessions
                ADD COLUMN IF NOT EXISTS consent_version INTEGER NULL
                """
            )
            connection.execute(
                """
                ALTER TABLE agent_conversation_sessions
                ADD COLUMN IF NOT EXISTS consent_text TEXT NULL
                """
            )
            connection.commit()

    def _persist_session(self, state: ConversationState) -> None:
        self._ensure_session_schema()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO agent_conversation_sessions (
                    session_id,
                    phone,
                    login_identifier,
                    mode,
                    stage,
                    user_id,
                    full_name,
                    position,
                    duties,
                    selected_role_id,
                    telegram,
                    consent_version,
                    consent_text,
                    company_industry,
                    history_json,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (session_id) DO UPDATE SET
                    phone = EXCLUDED.phone,
                    login_identifier = EXCLUDED.login_identifier,
                    mode = EXCLUDED.mode,
                    stage = EXCLUDED.stage,
                    user_id = EXCLUDED.user_id,
                    full_name = EXCLUDED.full_name,
                    position = EXCLUDED.position,
                    duties = EXCLUDED.duties,
                    selected_role_id = EXCLUDED.selected_role_id,
                    telegram = EXCLUDED.telegram,
                    consent_version = EXCLUDED.consent_version,
                    consent_text = EXCLUDED.consent_text,
                    company_industry = EXCLUDED.company_industry,
                    history_json = EXCLUDED.history_json,
                    updated_at = NOW()
                """,
                (
                    state.session_id,
                    None,
                    state.login_identifier,
                    state.mode.value,
                    state.stage.value,
                    state.user_id,
                    state.full_name,
                    state.position,
                    state.duties,
                    state.selected_role_id,
                    state.telegram,
                    state.consent_version,
                    state.consent_text,
                    state.company_industry,
                    json.dumps(state.history, ensure_ascii=False),
                ),
            )
            connection.commit()

    def _restore_session(self, session_id: str) -> ConversationState | None:
        self._ensure_session_schema()
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    session_id,
                    phone,
                    login_identifier,
                    mode,
                    stage,
                    user_id,
                    full_name,
                    position,
                    duties,
                    selected_role_id,
                    telegram,
                    consent_version,
                    consent_text,
                    company_industry,
                    history_json
                FROM agent_conversation_sessions
                WHERE session_id = %s
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            user = self._load_user_by_id(connection, int(row["user_id"])) if row["user_id"] else None
            history_raw = row["history_json"] or "[]"
            try:
                history = json.loads(history_raw)
            except (TypeError, ValueError):
                history = []
        return ConversationState(
            session_id=row["session_id"],
                    login_identifier=row["login_identifier"] or row["phone"] or "",
            mode=ConversationMode(str(row["mode"])),
            stage=ConversationStage(str(row["stage"])),
            user=user,
            user_id=row["user_id"],
            full_name=row["full_name"],
            position=row["position"],
            duties=row["duties"],
            selected_role_id=row["selected_role_id"],
            telegram=row["telegram"],
            consent_version=row["consent_version"],
            consent_text=row["consent_text"],
            company_industry=row["company_industry"],
            history=history if isinstance(history, list) else [],
        )

    def normalize_text(self, value: str | None) -> str:
        return normalize_profile_text(value)

    def tokenize(self, value: str | None) -> set[str]:
        normalized = self.normalize_text(value)
        tokens: set[str] = set()
        for token in normalized.split():
            if len(token) < 4:
                continue
            if token in STOP_WORDS:
                continue
            tokens.add(token)
        return tokens

    def _clean_position(self, position: str | None) -> str | None:
        return normalize_profile_position(position)

    def _normalize_company_industry_fallback(self, company_industry: str | None) -> str | None:
        return normalize_company_industry_fallback(company_industry)

    def normalize_telegram(self, telegram: str | None) -> str | None:
        raw = str(telegram or "").strip()
        if not raw:
            return None
        normalized = raw.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "").strip()
        if normalized.lower() in {"нет", "none", "no", "-", "не указано", "нет телеграма", "нет telegram"}:
            return None
        normalized = normalized.lstrip("@").strip()
        if not normalized:
            return None
        normalized = normalized.replace(" ", "")
        return f"@{normalized}"

    def _get_active_personal_data_consent(self) -> tuple[int, str, str]:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT version, title, consent_text
                FROM consent_documents
                WHERE consent_code = 'personal_data_processing'
                  AND is_active = TRUE
                ORDER BY version DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return (
                1,
                "Согласие на обработку персональных данных",
                "Я даю согласие на обработку моих персональных данных для регистрации в системе, проведения ассессмента и формирования индивидуального отчета.",
            )
        return int(row["version"] or 1), str(row["title"] or "Согласие на обработку персональных данных"), str(row["consent_text"] or "").strip()

    def _build_personal_data_consent_prompt(self) -> tuple[int, str, str]:
        version, title, consent_text = self._get_active_personal_data_consent()
        return version, title, consent_text

    def _build_personal_data_consent_actions(self) -> list[dict[str, str]]:
        return [
            {"value": "Согласен", "label": "Согласен, продолжить"},
        ]

    def _is_consent_accepted(self, text: str) -> bool:
        normalized = self.normalize_text(text)
        return normalized in {"согласен", "согласна", "да", "принимаю", "подтверждаю", "ok", "okay"}

    def _is_consent_declined(self, text: str) -> bool:
        normalized = self.normalize_text(text)
        return normalized in {"не согласен", "не согласна", "не принимаю", "отказываюсь", "нет"}

    def _record_user_personal_data_consent(self, user_id: int, consent_version: int | None, consent_text: str | None) -> UserResponse:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE users
                SET personal_data_consent_accepted_at = CURRENT_TIMESTAMP,
                    personal_data_consent_version = %s,
                    personal_data_consent_text = %s
                WHERE id = %s
                """,
                (consent_version, consent_text, user_id),
            )
            connection.commit()
            return self._load_user_by_id(connection, user_id)

    def normalize_company_industry(
        self,
        company_industry: str | None,
        *,
        position: str | None = None,
        duties: str | None = None,
        normalized_duties: str | None = None,
    ) -> str | None:
        fallback = self._normalize_company_industry_fallback(company_industry)
        if fallback:
            return fallback

        normalized = deepseek_client.normalize_company_industry(
            company_industry=company_industry,
            position=position,
            duties=duties or normalized_duties,
        )
        return normalized or fallback

    def _cleanup_duty_item(self, item: str) -> str | None:
        return normalize_duty_item(item)

    def _fallback_normalize_duties_items(self, duties: str | None) -> list[str]:
        return fallback_normalize_duties_items(duties)

    def normalize_duties(self, position: str | None, duties: str | None) -> str | None:
        fallback_items = self._fallback_normalize_duties_items(duties)
        items = fallback_items
        if not items:
            items = deepseek_client.normalize_duties(position=position, duties=duties) or []
        if not items:
            return None
        return format_duties_items(items)

    def _load_roles(self) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, code, name, short_definition, mission, typical_tasks,
                       work_objects, planning_horizon, impact_scale, authority_allowed,
                       authority_requires_approval, escalation_rules, role_limits, red_lines,
                       success_metrics, risks, interaction_scope, communication_rules,
                       typical_scenarios, information_sources, templates_tools,
                       personalization_variables, correct_personalization_examples,
                       incorrect_personalization_examples, methodist_notes
                FROM roles
                ORDER BY id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _load_selectable_roles(self) -> list[dict]:
        return [role for role in self._load_roles() if role.get("code") in {"linear_employee", "manager", "leader"}]

    def _get_role_description(self, role_code: str | None) -> str:
        code = str(role_code or "").strip()
        descriptions = {
            "linear_employee": (
                "Это роль исполнителя: вы сами выполняете конкретные задачи по правилам, инструкциям "
                "или стандартным процессам. Примеры: специалист, инженер, аналитик, бухгалтер, тестировщик."
            ),
            "manager": (
                "Это роль организатора работы: вы координируете людей, задачи, сроки и приоритеты, "
                "чтобы довести работу до результата. Примеры: тимлид, project manager, product manager, руководитель группы."
            ),
            "leader": (
                "Это роль человека, который задает направление: принимает решения с долгосрочными последствиями, "
                "ведет изменения и влияет на систему в целом. Примеры: руководитель направления, директор функции, "
                "руководитель департамента, топ-менеджер."
            ),
        }
        return descriptions.get(code, "")

    def _build_role_selection_guidance(self, *, include_intro: bool = True) -> str:
        intro = "Выберите вашу роль в системе из списка ниже.\n\n" if include_intro else ""
        return intro + (
            "Линейный сотрудник\n"
            "Это роль исполнителя: вы сами выполняете конкретные задачи по правилам, инструкциям или стандартным процессам. "
            "Примеры: специалист, инженер, аналитик, бухгалтер, тестировщик.\n\n"
            "Менеджер\n"
            "Это роль организатора работы: вы координируете людей, задачи, сроки и приоритеты, чтобы довести работу до результата. "
            "Примеры: тимлид, project manager, product manager, руководитель группы.\n\n"
            "Лидер\n"
            "Это роль человека, который задает направление: принимает решения с долгосрочными последствиями, ведет изменения "
            "и влияет на систему в целом. Примеры: руководитель направления, директор функции, руководитель департамента, топ-менеджер."
        )

    def _build_role_options(self) -> list[dict[str, str | int]]:
        return [
            {
                "id": int(role["id"]),
                "code": str(role["code"]),
                "name": str(role["name"]),
                "description": self._get_role_description(role["code"]),
            }
            for role in self._load_selectable_roles()
        ]

    def _resolve_selected_role(self, value: str | None) -> RoleMatch | None:
        normalized = self.normalize_text(value)
        if not normalized:
            return None

        for role in self._load_selectable_roles():
            if normalized == str(role["id"]):
                return RoleMatch(
                    role_id=role["id"],
                    code=role["code"],
                    name=role["name"],
                    confidence=1.0,
                    rationale="Роль выбрана пользователем при регистрации.",
                )

            role_name = self.normalize_text(role.get("name"))
            role_code = self.normalize_text(role.get("code"))
            if normalized == role_name or normalized == role_code:
                return RoleMatch(
                    role_id=role["id"],
                    code=role["code"],
                    name=role["name"],
                    confidence=1.0,
                    rationale="Роль выбрана пользователем при регистрации.",
                )
        return None

    def _build_role_rationale(
        self,
        role_match: RoleMatch | None,
        *,
        position: str | None,
        duties: str | None,
        normalized_duties: str | None,
        selected: bool = True,
    ) -> str | None:
        if not role_match:
            return None
        source = self.normalize_text(" ".join(filter(None, [position or "", duties or "", normalized_duties or ""])))
        selected_prefix = "Роль выбрана пользователем при регистрации и подтверждается описанием обязанностей: "
        inferred_prefix = "Описание обязанностей и рабочий контекст указывают на следующее: "
        if role_match.code == "manager":
            if any(token in source for token in ("обучен", "развит", "l&d", "тренинг", "курс", "эксперт", "подрядчик")):
                return (
                    (selected_prefix if selected else inferred_prefix)
                    +
                    "пользователь планирует и организует обучение, собирает потребности, согласует формат программ, "
                    "координирует взаимодействие с экспертами и подрядчиками, что соответствует менеджерскому уровню "
                    "координации и управления зависимостями."
                )
            return (
                (selected_prefix if selected else inferred_prefix)
                +
                "в задачах присутствуют координация людей, приоритизация и согласование следующего шага, "
                "что соответствует менеджерскому уровню."
            )
        if role_match.code == "linear_employee":
            return (
                (selected_prefix if selected else inferred_prefix)
                +
                "пользователь отвечает за собственный участок процесса, выполняет задачи в рамках регламентов "
                "и эскалирует вопросы за пределами своих полномочий."
            )
        if role_match.code == "leader":
            return (
                (selected_prefix if selected else inferred_prefix)
                +
                "в задачах присутствуют управление изменениями, приоритетами и ресурсами на уровне направления."
            )
        return role_match.rationale

    def _build_role_consistency(
        self,
        *,
        selected_role_match: RoleMatch | None,
        detected_role_match: RoleMatch | None,
        position: str | None,
        duties: str | None,
        normalized_duties: str | None,
    ) -> tuple[str, str]:
        if selected_role_match is None and detected_role_match is None:
            return ("insufficient_data", "Недостаточно данных для сопоставления выбранной и интерпретированной роли.")
        if selected_role_match is None:
            return ("insufficient_data", "Роль пользователя не выбрана явно, используется только интерпретация по должности и обязанностям.")
        if detected_role_match is None:
            return ("insufficient_data", "Недостаточно признаков для независимой проверки выбранной роли.")
        if selected_role_match.code == detected_role_match.code:
            return ("consistent", "Выбранная роль согласуется с должностью и описанием обязанностей.")

        source = self.normalize_text(" ".join(filter(None, [position or "", duties or "", normalized_duties or ""])))
        if selected_role_match.code == "linear_employee" and detected_role_match.code == "manager" and "менеджер" in source:
            return (
                "partially_consistent",
                "В названии должности есть менеджерский сигнал, но роль пользователя сохранена как линейная. Нужна осторожная интерпретация через реальные обязанности.",
            )
        if selected_role_match.code == "manager" and detected_role_match.code == "linear_employee":
            return (
                "partially_consistent",
                "Пользователь выбрал менеджерскую роль, но в обязанностях пока преобладают индивидуальные операционные задачи без явного управления людьми или ресурсами.",
            )
        return (
            "inconsistent",
            f"Выбранная роль «{selected_role_match.name}» расходится с интерпретацией по обязанностям («{detected_role_match.name}»).",
        )

    def _extract_instruction_guidance(self, instruction: dict | None) -> dict:
        return {}

    def _normalize_domain_value(self, value: str | None) -> str:
        return self.normalize_text(value)

    def _get_instruction_avoid_terms(
        self,
        *,
        instruction: dict | None,
        user_domain: str | None,
    ) -> list[str]:
        guidance = self._extract_instruction_guidance(instruction)
        anti_patterns = guidance.get("cross_domain_anti_patterns") or []
        domain_text = self._normalize_domain_value(user_domain)
        result: list[str] = []
        seen: set[str] = set()
        for item in anti_patterns:
            if not isinstance(item, dict):
                continue
            when_domain = self._normalize_domain_value(item.get("when_user_domain"))
            if when_domain and when_domain not in domain_text:
                continue
            for token in item.get("avoid") or []:
                token_text = str(token).strip()
                if token_text and token_text not in seen:
                    seen.add(token_text)
                    result.append(token_text)
        return result

    def _filter_values_by_instruction_domain(
        self,
        *,
        instruction: dict | None,
        user_domain: str | None,
        values: list[str],
    ) -> list[str]:
        avoid_terms = self._get_instruction_avoid_terms(
            instruction=instruction,
            user_domain=user_domain,
        )
        if not avoid_terms:
            return values
        filtered: list[str] = []
        normalized_avoid = [self.normalize_text(item) for item in avoid_terms]
        for value in values:
            text = str(value).strip()
            normalized_text = self.normalize_text(text)
            if text and not any(token and token in normalized_text for token in normalized_avoid):
                filtered.append(text)
        return filtered

    def _get_nested_profile_value(self, payload: dict, path: str) -> object:
        current: object = payload
        for part in str(path or "").split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _find_missing_required_profile_fields(
        self,
        *,
        instruction: dict | None,
        profile_payload: dict,
    ) -> list[str]:
        guidance = self._extract_instruction_guidance(instruction)
        field_rules = guidance.get("field_rules") or {}
        required_paths = field_rules.get("minimum_required_fields") or []
        missing: list[str] = []
        for path in required_paths:
            value = self._get_nested_profile_value(profile_payload, str(path))
            is_missing = value is None
            if isinstance(value, str):
                is_missing = not value.strip()
            elif isinstance(value, list):
                is_missing = len(value) == 0
            elif isinstance(value, dict):
                is_missing = len(value) == 0
            if is_missing:
                missing.append(str(path))
        return missing

    def _build_instruction_clarification_questions(
        self,
        *,
        instruction: dict | None,
        company_context: str | None,
        role_consistency_status: str,
        domain_resolution_status: str,
    ) -> list[str]:
        guidance = self._extract_instruction_guidance(instruction)
        field_rules = guidance.get("field_rules") or {}
        clarification_rule = field_rules.get("clarification_questions") or {}
        max_items = int(clarification_rule.get("max_items") or 3)
        questions: list[str] = []
        if not company_context:
            questions.append("Уточните, пожалуйста, профиль деятельности компании или контекст подразделения, в котором вы работаете.")
        if role_consistency_status in {"partially_consistent", "inconsistent"}:
            questions.append("Подтвердите, пожалуйста, вашу роль: вы в основном выполняете задачи самостоятельно, координируете других или задаете направление работы нескольких групп?")
        if domain_resolution_status in {"fallback", "needs_clarification"}:
            questions.append("Уточните, пожалуйста, в каком именно функциональном контуре проходит основная часть вашей работы: например, обучение, клиентский сервис, финансы, инженерия или другой рабочий домен.")
        return questions[:max_items]

    def _collect_cross_domain_warnings(
        self,
        *,
        instruction: dict | None,
        user_domain: str | None,
        values: list[str],
    ) -> list[str]:
        guidance = self._extract_instruction_guidance(instruction)
        anti_patterns = guidance.get("cross_domain_anti_patterns") or []
        domain_text = self.normalize_text(user_domain)
        source_text = self.normalize_text(" ".join(str(item) for item in values if str(item).strip()))
        warnings: list[str] = []
        for item in anti_patterns:
            if not isinstance(item, dict):
                continue
            when_domain = self.normalize_text(item.get("when_user_domain"))
            if when_domain and when_domain not in domain_text:
                continue
            avoid_values = [str(token).strip() for token in (item.get("avoid") or []) if str(token).strip()]
            matched = [token for token in avoid_values if self.normalize_text(token) in source_text]
            if matched:
                warnings.append(
                    "В профиле обнаружена лексика чужого домена для текущей предметной области: "
                    + ", ".join(matched[:3])
                    + "."
                )
        return warnings

    def _apply_instruction_quality_rules(
        self,
        *,
        instruction: dict | None,
        selected_role_match: RoleMatch | None,
        detected_role_match: RoleMatch | None,
        user_domain: str | None,
        processes: list[str],
        tasks: list[str],
        stakeholders: list[str],
        risks: list[str],
        constraints: list[str],
        user_artifacts: list[str],
        user_systems: list[str],
    ) -> list[str]:
        warnings: list[str] = []
        combined_values = [
            *processes,
            *tasks,
            *stakeholders,
            *risks,
            *constraints,
            *user_artifacts,
            *user_systems,
        ]
        warnings.extend(
            self._collect_cross_domain_warnings(
                instruction=instruction,
                user_domain=user_domain,
                values=combined_values,
            )
        )
        if selected_role_match and detected_role_match:
            if selected_role_match.code == "linear_employee" and detected_role_match.code in {"manager", "leader"}:
                warnings.append(
                    "Выбранная роль сохранена как линейная, хотя в обязанностях есть отдельные сигналы более широкой ответственности. Профиль нужно интерпретировать через выбранную роль."
                )
            if selected_role_match.code in {"manager", "leader"} and detected_role_match.code == "linear_employee":
                warnings.append(
                    "Выбранная роль сохранена как управленческая, хотя в обязанностях преобладают индивидуальные операционные действия. Возможна необходимость уточнения масштаба роли."
                )
        for values_name, values in (
            ("user_tasks", tasks),
            ("user_processes", processes),
            ("user_stakeholders", stakeholders),
            ("user_risks", risks),
            ("user_constraints", constraints),
        ):
            if not values:
                warnings.append(
                    f"Поле {values_name} заполнено неполно: лучше оставить это как сигнал на уточнение, чем достраивать детали без основания."
                )
        return warnings

    def _parse_bullets(self, value: str | None) -> list[str]:
        return parse_bullet_list(value)

    def _score_position_hints(self, normalized_position: str, role_code: str) -> tuple[float, list[str]]:
        score = 0.0
        matched: list[str] = []
        for hint in POSITION_ROLE_HINTS.get(role_code, set()):
            if hint in normalized_position:
                score += 10.0 if role_code == "leader" else 7.0
                matched.append(hint)
        return score, matched

    def _heuristic_detect_role(
        self,
        position: str | None,
        duties: str | None,
        normalized_duties: str | None,
        roles: list[dict],
    ) -> RoleMatch | None:
        source_text = " ".join(filter(None, [position or "", duties or "", normalized_duties or ""])).strip()
        if not source_text:
            return None

        normalized_position = self.normalize_text(position)
        normalized_source = self.normalize_text(source_text)
        user_tokens = self.tokenize(source_text)
        if not user_tokens and not normalized_source:
            return None

        scored: list[tuple[float, dict, list[str]]] = []
        for role in roles:
            role_text = " ".join(
                str(role.get(key) or "")
                for key in [
                    "name",
                    "short_definition",
                    "mission",
                    "typical_tasks",
                    "planning_horizon",
                    "impact_scale",
                    "authority_allowed",
                    "role_limits",
                    "escalation_rules",
                    "personalization_variables",
                ]
            )
            role_tokens = self.tokenize(role_text)
            overlap = len(user_tokens & role_tokens)
            score = overlap * 2.5
            evidence: list[str] = []
            if overlap:
                evidence.append(f"совпадения по словарю роли: {overlap}")

            position_score, matched_position_hints = self._score_position_hints(normalized_position, role["code"])
            score += position_score
            if matched_position_hints:
                evidence.append(f"сигналы в должности: {', '.join(matched_position_hints[:3])}")

            for hint in ROLE_HINTS.get(role["code"], set()):
                if hint in normalized_source:
                    score += 2.0
                    if len(evidence) < 5:
                        evidence.append(f"обязанности содержат признак «{hint}»")

            scored.append((score, role, evidence))

        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_role, best_evidence = scored[0]
        if best_score <= 0:
            return None

        second_score = scored[1][0] if len(scored) > 1 else 0.0
        gap = max(best_score - second_score, 0.0)
        confidence = min(0.95, max(0.55, 0.55 + min(gap, 8.0) / 20.0 + min(best_score, 20.0) / 100.0))

        rationale_parts = []
        if best_role["code"] == "linear_employee":
            rationale_parts.append("профиль ближе к выполнению конкретных задач по правилам, регламентам и SLA")
        elif best_role["code"] == "manager":
            rationale_parts.append("профиль ближе к координации людей, сроков, приоритетов и зависимостей")
        else:
            rationale_parts.append("профиль ближе к стратегическим решениям, изменениям и управлению крупными рисками")
        if best_evidence:
            rationale_parts.append("; ".join(best_evidence[:3]))

        return RoleMatch(
            role_id=best_role["id"],
            code=best_role["code"],
            name=best_role["name"],
            confidence=round(confidence, 2),
            rationale=". ".join(part for part in rationale_parts if part),
        )

    def detect_role(self, position: str | None, duties: str | None, normalized_duties: str | None) -> RoleMatch | None:
        source_text = " ".join(filter(None, [position or "", duties or "", normalized_duties or ""])).strip()
        if not source_text:
            return None

        roles = self._load_roles()
        detected = self._heuristic_detect_role(position, duties, normalized_duties, roles)
        if detected is not None:
            return detected

        fallback_role = next((role for role in roles if role.get("code") == "linear_employee"), None)
        if fallback_role is None:
            return None

        return RoleMatch(
            role_id=fallback_role["id"],
            code=fallback_role["code"],
            name=fallback_role["name"],
            confidence=0.49,
            rationale=(
                "Явных признаков менеджерской или лидерской роли не обнаружено. "
                "По умолчанию профиль отнесен к роли линейного сотрудника как к базовому исполнительскому уровню."
            ),
        )

    def _infer_domain(self, position: str | None, duties: str | None, company_industry: str | None = None) -> str:
        source = self.normalize_text(" ".join(filter(None, [position or "", duties or ""])))
        mapping = [
            (("аналитик", "требован", "постановк"), "бизнес-аналитика"),
            (("персонал", "hr", "подбор", "кадр"), "управление персоналом"),
            (("клиент", "поддержк", "обращен", "сервис"), "клиентский сервис"),
            (("финанс", "бюджет", "счет", "оплат"), "финансовое управление"),
            (("логист", "склад", "достав", "постав"), "логистика"),
            (("продаж", "crm", "сделк"), "продажи"),
            (("маркет", "кампан", "трафик"), "маркетинг"),
            (("проект", "delivery", "roadmap"), "проектное управление"),
            (("производ", "участок", "оборуд"), "производственные процессы"),
        ]
        for hints, label in mapping:
            if any(hint in source for hint in hints):
                return label
        normalized_company_industry = self.normalize_company_industry(company_industry, position=position, duties=duties)
        if normalized_company_industry:
            return normalized_company_industry
        return "операционная деятельность"

    def _resolve_role_confidence(
        self,
        *,
        selected_role_match: RoleMatch | None,
        detected_role_match: RoleMatch | None,
        role_consistency_status: str,
        cleaned_position: str | None,
        normalized_duties_items: list[str],
    ) -> float:
        if not cleaned_position or not normalized_duties_items:
            return 0.45
        if role_consistency_status == "consistent":
            detected = float(detected_role_match.confidence if detected_role_match else 0.9)
            return round(min(1.0, max(0.9, detected)), 2)
        if role_consistency_status == "partially_consistent":
            detected = float(detected_role_match.confidence if detected_role_match else 0.75)
            return round(min(0.89, max(0.7, detected)), 2)
        if role_consistency_status == "inconsistent":
            detected = float(detected_role_match.confidence if detected_role_match else 0.6)
            return round(min(0.69, max(0.5, detected)), 2)
        return 0.45

    def _extract_user_processes(self, normalized_duties: str | None, position: str | None, duties: str | None) -> list[str]:
        source = self.normalize_text(" ".join(filter(None, [position or "", duties or "", normalized_duties or ""])))
        process_map = [
            (("обучен", "развит", "курс", "тренинг", "l&d"), "организация и сопровождение обучения"),
            (("клиент", "обращен", "сервис", "поддержк"), "обработка и сопровождение клиентских обращений"),
            (("кд", "чертеж", "документац", "конструкт"), "подготовка и согласование конструкторской документации"),
            (("vpn", "заявк", "инцидент", "service desk", "тикет"), "поддержка пользователей и обработка заявок"),
            (("финанс", "оплат", "счет", "бюджет", "акт"), "учет и контроль финансовых операций"),
            (("подбор", "ваканс", "кандидат", "собесед"), "подбор и сопровождение кандидатов"),
            (("проект", "доставк", "roadmap", "план"), "планирование и координация проектной работы"),
            (("продаж", "клиент", "сделк", "crm"), "сопровождение продаж и клиентского взаимодействия"),
        ]
        processes: list[str] = []
        for hints, label in process_map:
            if any(hint in source for hint in hints) and label not in processes:
                processes.append(label)
        if "обработка и сопровождение клиентских обращений" in processes and "сопровождение продаж и клиентского взаимодействия" in processes:
            processes.remove("сопровождение продаж и клиентского взаимодействия")
        if processes:
            return processes[:6]
        if position:
            return [f"Основной рабочий процесс в области «{position}»"]
        return []

    def _merge_unique_text_values(self, *groups: list[str], limit: int = 8) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for item in group or []:
                text = str(item).strip()
                if not text:
                    continue
                key = self.normalize_text(text)
                if key in seen:
                    continue
                seen.add(key)
                result.append(text)
                if len(result) >= limit:
                    return result
        return result

    def _split_compound_values(self, values: list[str], *, split_conjunction: bool = False) -> list[str]:
        result: list[str] = []
        for item in values or []:
            text = str(item).strip()
            if not text:
                continue
            parts = [part.strip(" .,:;") for part in re.split(r"[,;]", text) if part.strip(" .,:;")]
            normalized_parts: list[str] = []
            for part in parts or [text]:
                if split_conjunction and " и " in part and len(part.split()) >= 4:
                    normalized_parts.extend(
                        subpart.strip(" .,:;")
                        for subpart in re.split(r"\s+и\s+", part)
                        if subpart.strip(" .,:;")
                    )
                else:
                    normalized_parts.append(part)
            if not normalized_parts:
                normalized_parts = [text]
            for part in normalized_parts:
                if len(part.split()) > 8 and "," not in text and ";" not in text:
                    result.append(text)
                    break
                if part:
                    result.append(part)
        return result

    def _looks_like_case_scene(self, value: str | None) -> bool:
        text = self.normalize_text(value)
        scene_markers = (
            "не получил",
            "жалоб",
            "инцидент",
            "эскалац",
            "просроч",
            "не согласован",
            "конфликт",
            "не уведом",
            "без владельц",
            "следующий шаг не",
        )
        return any(marker in text for marker in scene_markers)

    def _looks_like_obligation_statement(self, value: str | None) -> bool:
        text = self.normalize_text(value)
        return text.startswith(
            (
                "организ",
                "контрол",
                "анализ",
                "готов",
                "обнов",
                "подтвержд",
                "зафикс",
                "соглас",
                "провер",
                "распредел",
                "вед",
                "сопровожда",
            )
        )

    def _looks_like_system_name(self, value: str | None) -> bool:
        text = self.normalize_text(value)
        return any(
            marker in text
            for marker in (
                "crm",
                "erp",
                "service desk",
                "jira",
                "sap",
                "1с",
                "lms",
                "hrm",
                "mes",
                "scada",
                "servicenow",
                "bitrix",
            )
        )

    def _build_user_tasks(
        self,
        *,
        normalized_duties_items: list[str],
        duties: str | None,
        domain_profile: dict | None,
        role: dict | None = None,
        role_code: str | None = None,
        position: str | None = None,
    ) -> list[str]:
        primary_tasks = [str(item).strip() for item in normalized_duties_items if str(item).strip()]
        fallback_tasks = [str(item).strip() for item in self._fallback_normalize_duties_items(duties) if str(item).strip()]
        role_tasks: list[str] = []
        normalized_position = self.normalize_text(position)
        if role:
            role_tasks = [
                str(item).strip()
                for item in (self._parse_bullets(role.get("typical_tasks")) + self._parse_bullets(role.get("mission")))
                if str(item).strip() and len(str(item).split()) <= 18
            ]
            if role_code in {"manager", "leader"} and any(token in normalized_position for token in ("руковод", "начальник", "head", "lead")):
                role_tasks.extend(
                    [
                        "Организация работы команды и распределение ответственности",
                        "Контроль сроков, качества и приоритетов в подразделении",
                        "Координация эскалаций и взаимодействия со смежными командами",
                    ]
                )
        duties_are_sparse = len(primary_tasks) <= 1 or all(len(str(item).split()) >= 12 for item in primary_tasks)
        if duties_are_sparse:
            return self._merge_unique_text_values(primary_tasks, role_tasks, fallback_tasks, limit=8)
        return self._merge_unique_text_values(primary_tasks, fallback_tasks, role_tasks, limit=8)

    def _build_user_processes(
        self,
        *,
        domain_profile: dict | None,
        normalized_duties: str | None,
        position: str | None,
        duties: str | None,
        ) -> list[str]:
        extracted = self._extract_user_processes(normalized_duties, position, duties)
        domain_processes = [
            str(item).strip()
            for item in self._split_compound_values(
                [str(raw).strip() for raw in ((domain_profile or {}).get("processes") or []) if str(raw).strip()]
            )
            if (
                str(item).strip()
                and not self._looks_like_case_scene(item)
                and not self._looks_like_obligation_statement(item)
                and len(str(item).split()) <= 6
            )
        ]
        return self._merge_unique_text_values(extracted, domain_processes, limit=6)

    def _extract_stakeholders(self, role_code: str | None, source_text: str) -> list[str]:
        stakeholders: list[str] = []
        mapping = [
            ("клиент", "клиент"),
            ("заказчик", "заказчик"),
            ("команд", "команда"),
            ("руковод", "руководитель"),
            ("подряд", "подрядчик"),
            ("партнер", "партнер"),
            ("регулятор", "регулятор"),
            ("hr", "HR-команда"),
            ("сотрудник", "сотрудник"),
        ]
        for token, label in mapping:
            if token in source_text and label not in stakeholders:
                stakeholders.append(label)
        if not stakeholders:
            default_map = {
                "linear_employee": ["инициатор запроса", "смежная команда", "руководитель"],
                "manager": ["команда", "смежное подразделение", "внутренний заказчик"],
                "leader": ["руководитель направления", "ключевой стейкхолдер", "внешний партнер"],
            }
            stakeholders.extend(default_map.get(role_code or "", ["смежный участник процесса"]))
        return stakeholders

    def _is_self_stakeholder(self, stakeholder: str, *, position: str | None) -> bool:
        normalized_stakeholder = self.normalize_text(stakeholder)
        normalized_position = self.normalize_text(position)
        if not normalized_stakeholder or not normalized_position:
            return False
        if normalized_stakeholder == normalized_position or normalized_stakeholder in normalized_position:
            return True
        stakeholder_tokens = {
            token for token in normalized_stakeholder.split()
            if len(token) >= 5 and token not in STOP_WORDS
        }
        position_tokens = {
            token for token in normalized_position.split()
            if len(token) >= 5 and token not in STOP_WORDS
        }
        overlap = stakeholder_tokens & position_tokens
        if "руководитель" in normalized_stakeholder and "руководитель" in normalized_position and len(overlap) >= 2:
            return True
        return False

    def _extract_risks(self, role_code: str | None, source_text: str) -> list[str]:
        risks = []
        mapping = [
            ("срок", "Срыв сроков"),
            ("иб", "Риск информационной безопасности"),
            ("безопас", "Операционный риск безопасности"),
            ("качест", "Снижение качества результата"),
            ("бюджет", "Превышение бюджета"),
            ("конфликт", "Конфликт интересов стейкхолдеров"),
            ("зависим", "Зависимость от смежных команд"),
        ]
        for token, label in mapping:
            if token in source_text and label not in risks:
                risks.append(label)
        if not risks:
            default_map = {
                "linear_employee": ["Нарушение регламента", "Неполные входные данные", "Неэскалированный инцидент"],
                "manager": ["Срыв сроков", "Конфликт приоритетов", "Блокировки между командами"],
                "leader": ["Стратегическая ошибка", "Крупный риск изменений", "Репутационные последствия"],
            }
            risks.extend(default_map.get(role_code or "", ["Операционные риски процесса"]))
        return risks

    def _extract_constraints(self, role: dict | None, source_text: str) -> list[str]:
        constraints = self._parse_bullets(role.get("role_limits") if role else None)
        if "бюджет" in source_text and "Ограничение бюджета" not in constraints:
            constraints.append("Ограничение бюджета")
        if "срок" in source_text and "Фиксированные сроки" not in constraints:
            constraints.append("Фиксированные сроки")
        return constraints[:8]

    def _build_user_stakeholders(
        self,
        *,
        role_code: str | None,
        source_text: str,
        domain_profile: dict | None,
        role_limits: dict | None = None,
        role_vocabulary: dict | None = None,
        position: str | None = None,
    ) -> list[str]:
        extracted = self._extract_stakeholders(role_code, source_text)
        domain_values = [
            item for item in self._split_compound_values(
            [str(item).strip() for item in ((domain_profile or {}).get("stakeholders") or []) if str(item).strip()],
            split_conjunction=True,
            )
            if item and not self._looks_like_case_scene(item) and len(str(item).split()) <= 6
        ]
        role_values = [
            str(item).strip()
            for item in (
                [str(item).strip() for item in ((role_limits or {}).get("communication_targets") or []) if str(item).strip()]
                + [str(item).strip() for item in ((role_vocabulary or {}).get("participants") or []) if str(item).strip()]
            )
            if str(item).strip() and len(str(item).split()) <= 8 and not self._looks_like_case_scene(item)
        ]
        merged = self._merge_unique_text_values(extracted, domain_values, role_values, limit=8)
        filtered = [item for item in merged if not self._is_self_stakeholder(item, position=position)]
        return filtered[:6]

    def _build_user_risks(
        self,
        *,
        role_code: str | None,
        source_text: str,
        domain_profile: dict | None,
        role: dict | None = None,
    ) -> list[str]:
        extracted = self._extract_risks(role_code, source_text)
        domain_values = [
            str(item).strip()
            for item in ((domain_profile or {}).get("risks") or [])
            if str(item).strip() and not self._looks_like_case_scene(item)
        ]
        role_values = [str(item).strip() for item in self._parse_bullets(role.get("risks") if role else None) if str(item).strip()]
        return self._merge_unique_text_values(extracted, domain_values, role_values, limit=6)

    def _build_user_constraints(
        self,
        *,
        role: dict | None,
        source_text: str,
        domain_profile: dict | None,
    ) -> list[str]:
        extracted = self._extract_constraints(role, source_text)
        domain_values = [
            str(item).strip()
            for item in ((domain_profile or {}).get("constraints") or [])
            if str(item).strip() and not self._looks_like_case_scene(item)
        ]
        role_values = [
            str(item).strip()
            for item in (
                self._parse_bullets(role.get("authority_requires_approval") if role else None)
                + self._parse_bullets(role.get("red_lines") if role else None)
                + self._parse_bullets(role.get("communication_rules") if role else None)
            )
            if str(item).strip()
        ]
        return self._merge_unique_text_values(extracted, domain_values, role_values, limit=8)

    def _build_role_limits(
        self,
        role: dict,
        role_code: str,
        stakeholders: list[str],
        *,
        instruction: dict | None = None,
        user_domain: str | None = None,
    ) -> dict:
        communication_targets = self._filter_values_by_instruction_domain(
            instruction=instruction,
            user_domain=user_domain,
            values=[str(item).strip() for item in stakeholders if str(item).strip()],
        )
        role_limits = {
            "decision_level": self._parse_bullets(role.get("authority_allowed")),
            "responsibility_scope": self._parse_bullets(role.get("mission")) + self._parse_bullets(role.get("typical_tasks"))[:3],
            "authority_constraints": self._parse_bullets(role.get("role_limits")),
            "approval_dependencies": self._parse_bullets(role.get("authority_requires_approval")),
            "red_lines": self._parse_bullets(role.get("red_lines")),
            "impact_scale": role.get("impact_scale"),
            "planning_horizon": role.get("planning_horizon"),
            "interaction_scope": self._parse_bullets(role.get("interaction_scope")),
            "communication_rules": self._parse_bullets(role.get("communication_rules")),
            "communication_targets": communication_targets,
            "escalation_points": self._parse_bullets(role.get("escalation_rules")),
            "typical_scenarios": self._parse_bullets(role.get("typical_scenarios")),
            "role_code": role_code,
        }
        guidance = self._extract_instruction_guidance(instruction)
        field_rules = guidance.get("field_rules") or {}
        role_limits_rule = field_rules.get("role_limits") or {}
        list_suffixes = ("level", "scope", "constraints", "points", "targets", "dependencies", "lines", "rules", "scenarios")
        for required_field in role_limits_rule.get("must_cover") or []:
            role_limits.setdefault(str(required_field), [] if str(required_field).endswith(list_suffixes) else None)
        return role_limits

    def _build_role_vocabulary(
        self,
        role: dict,
        role_code: str,
        normalized_duties: str | None,
        *,
        instruction: dict | None = None,
        user_domain: str | None = None,
        domain_profile: dict | None = None,
        processes: list[str] | None = None,
        tasks: list[str] | None = None,
        stakeholders: list[str] | None = None,
    ) -> dict:
        base_vocab = {
            "linear_employee": {
                "action_verbs": ["проверить", "зафиксировать", "уточнить", "обработать", "эскалировать"],
                "work_entities": ["задача", "журнал", "инструкция", "статус", "следующий шаг", "результат"],
                "participants": ["инициатор запроса", "смежная команда", "руководитель"],
                "phrasing_style": "конкретный операционный язык, короткие действия, работа по правилам и статусам",
            },
            "manager": {
                "action_verbs": ["согласовать", "распределить", "приоритизировать", "снять блокировки", "зафиксировать договоренности"],
                "work_entities": ["команда", "зависимость", "дедлайн", "ресурс", "стейкхолдер", "риск", "план"],
                "participants": ["команда", "смежные подразделения", "внутренние заказчики"],
                "phrasing_style": "тактический управленческий язык, координация людей, сроков и зависимостей",
            },
            "leader": {
                "action_verbs": ["определить приоритет", "изменить подход", "перераспределить инвестиции", "задать принципы", "управлять изменением"],
                "work_entities": ["стратегия", "портфель инициатив", "бюджет", "культура", "риски", "партнеры", "репутация"],
                "participants": ["руководители направлений", "ключевые стейкхолдеры", "внешние партнеры"],
                "phrasing_style": "стратегический язык решений, изменений, системных эффектов и высоких ставок",
            },
        }
        vocabulary = dict(base_vocab.get(role_code, {}))
        role_words = self._parse_bullets(role.get("personalization_variables"))
        if role_words:
            vocabulary["role_placeholders"] = role_words
        duty_items = self._parse_bullets(normalized_duties)
        if duty_items:
            vocabulary["user_phrases"] = duty_items[:5]
        domain_specific_entities: list[str] = []
        artifacts = self._split_compound_values(
            [str(item).strip() for item in ((domain_profile or {}).get("artifacts") or []) if str(item).strip()],
            split_conjunction=True,
        )
        systems = self._split_compound_values(
            [str(item).strip() for item in ((domain_profile or {}).get("systems") or []) if str(item).strip()],
            split_conjunction=True,
        )
        for item in [*artifacts, *systems]:
            text = str(item).strip()
            if (
                text
                and text not in domain_specific_entities
                and not self._looks_like_case_scene(text)
                and len(text.split()) <= 5
            ):
                domain_specific_entities.append(text)
        role_entities = self._split_compound_values(
            [
                str(item).strip()
                for item in (
                    self._parse_bullets(role.get("work_objects"))
                    + self._parse_bullets(role.get("templates_tools"))
                    + self._parse_bullets(role.get("information_sources"))
                )
                if str(item).strip()
            ],
            split_conjunction=True,
        )
        for item in role_entities:
            text = str(item).strip()
            if text and text not in domain_specific_entities and not self._looks_like_case_scene(text) and len(text.split()) <= 6:
                domain_specific_entities.append(text)
        if domain_specific_entities:
            vocabulary["work_entities"] = domain_specific_entities[:8]
        participant_values = self._split_compound_values(
            [str(item).strip() for item in (stakeholders or []) if str(item).strip()],
            split_conjunction=True,
        )
        participant_values.extend(
            self._split_compound_values(
                [
                    str(item).strip()
                    for item in (
                        self._parse_bullets(role.get("interaction_scope"))
                        + self._parse_bullets(role.get("communication_rules"))
                    )
                    if str(item).strip()
                ],
                split_conjunction=True,
            )
        )
        if participant_values:
            vocabulary["participants"] = participant_values[:6]
        guidance = self._extract_instruction_guidance(instruction)
        field_rules = guidance.get("field_rules") or {}
        role_vocab_rules = field_rules.get("role_vocabulary") or {}
        placeholder_examples = [str(item).strip() for item in (role_vocab_rules.get("placeholder_examples") or []) if str(item).strip()]
        placeholders = [str(item).strip() for item in (vocabulary.get("role_placeholders") or []) if str(item).strip()]
        for item in placeholder_examples:
            if item not in placeholders:
                placeholders.append(item)
        if placeholders:
            vocabulary["role_placeholders"] = placeholders[:12]
        if user_domain:
            if "phrasing_style" in vocabulary and vocabulary["phrasing_style"]:
                vocabulary["phrasing_style"] = f"{vocabulary['phrasing_style']}; лексика должна соответствовать домену «{user_domain}» и не содержать чужих процессов."
        vocabulary["participants"] = self._filter_values_by_instruction_domain(
            instruction=instruction,
            user_domain=user_domain,
            values=[str(item).strip() for item in (vocabulary.get("participants") or []) if str(item).strip()],
        )[:6]
        vocabulary["work_entities"] = self._filter_values_by_instruction_domain(
            instruction=instruction,
            user_domain=user_domain,
            values=[str(item).strip() for item in (vocabulary.get("work_entities") or []) if str(item).strip()],
        )[:8]
        return vocabulary

    def _build_role_skill_profile(self, role_id: int | None, role_code: str | None, *, instruction: dict | None = None) -> dict:
        if not role_id:
            return {}
        guidance = self._extract_instruction_guidance(instruction)
        field_rules = guidance.get("field_rules") or {}
        expected_scope_by_role = ((field_rules.get("role_skill_profile") or {}).get("expected_scope_by_role") or {})
        expected_scope = expected_scope_by_role.get(role_code or "")
        if not expected_scope:
            expected_scope = {
                "linear_employee": "Операционный уровень проявления навыка: выполнение, фиксация, соблюдение правил, эскалация.",
                "manager": "Тактический уровень проявления навыка: координация, согласование, приоритизация, управление зависимостями.",
                "leader": "Стратегический уровень проявления навыка: системные решения, изменения, распределение ресурсов, управление рисками.",
            }.get(role_code or "", "Ролевой уровень проявления навыка определяется типом решений и масштабом влияния.")

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT s.skill_code, s.competency_name, s.skill_name
                FROM role_skills rs
                JOIN skills s ON s.id = rs.skill_id
                WHERE rs.role_id = %s
                ORDER BY s.skill_code ASC
                """,
                (role_id,),
            ).fetchall()
        return {
            "expected_scope": expected_scope,
            "valid_skills": [
                {
                    "skill_code": row["skill_code"],
                    "competency_name": row["competency_name"],
                    "skill_name": row["skill_name"],
                }
                for row in rows
            ],
        }

    def _map_domain_resolution_status_for_profile(
        self,
        *,
        instruction: dict | None,
        runtime_status: str | None,
    ) -> str | None:
        guidance = self._extract_instruction_guidance(instruction)
        field_rules = guidance.get("field_rules") or {}
        mapping = field_rules.get("domain_resolution_status_mapping") or {}
        if runtime_status in mapping:
            return str(mapping[runtime_status]).strip() or runtime_status
        return runtime_status

    def _build_domain_profile_block(self, domain_profile: dict | None, *, instruction: dict | None = None) -> dict:
        profile = domain_profile or {}
        systems = self._split_compound_values(
            [str(item).strip() for item in (profile.get("systems") or []) if str(item).strip()],
            split_conjunction=True,
        )
        artifacts = self._split_compound_values(
            [str(item).strip() for item in (profile.get("artifacts") or []) if str(item).strip()],
            split_conjunction=True,
        )
        cleaned_systems = self._merge_unique_text_values(
            [str(item).strip() for item in systems if str(item).strip() and self._looks_like_system_name(item)],
            limit=8,
        )
        cleaned_artifacts = self._merge_unique_text_values(
            [
                str(item).strip()
                for item in artifacts
                if (
                    str(item).strip()
                    and len(str(item).split()) <= 5
                    and not self._looks_like_case_scene(item)
                    and not self._looks_like_system_name(item)
                )
            ],
            limit=8,
        )
        return {
            "domain_code": profile.get("domain_code"),
            "domain_label": profile.get("domain_label"),
            "domain_family": profile.get("domain_family"),
            "domain_display_name": profile.get("domain_label") or profile.get("domain_family"),
            "domain_resolution_status": self._map_domain_resolution_status_for_profile(
                instruction=instruction,
                runtime_status=profile.get("domain_resolution_status"),
            ),
            "systems": cleaned_systems,
            "artifacts": cleaned_artifacts,
            "typical_keywords": [str(item).strip() for item in (profile.get("keywords") or profile.get("typical_keywords") or []) if str(item).strip()][:10],
        }

    def _build_adaptation_rules_for_cases(
        self,
        *,
        domain: str | None,
        role_code: str | None,
        role: dict | None,
        processes: list[str],
        tasks: list[str],
        stakeholders: list[str],
        risks: list[str],
        constraints: list[str],
    ) -> dict:
        role_hint = {
            "linear_employee": "адаптировать сценарии под работу в рамках своего участка, правил и эскалации за пределами полномочий",
            "manager": "адаптировать сценарии под координацию людей, сроков, приоритетов и зависимостей",
            "leader": "адаптировать сценарии под стратегический выбор, изменения и согласование интересов нескольких групп",
        }.get(role_code or "", "адаптировать сценарии под реальный масштаб роли пользователя")
        include_values = []
        task_values = [str(item).strip() for item in tasks if str(item).strip() and not self._looks_like_case_scene(item)]
        process_values = [str(item).strip() for item in processes if str(item).strip() and not self._looks_like_case_scene(item)]
        stakeholder_values = self._split_compound_values(
            [str(item).strip() for item in stakeholders if str(item).strip()],
            split_conjunction=True,
        )
        for item in [*process_values[:2], *task_values[:3], *stakeholder_values[:2], *constraints[:2]]:
            text = str(item).strip()
            if text and text not in include_values:
                include_values.append(text)
        avoid_values = []
        normalized_domain = self.normalize_text(domain)
        if "обуч" in normalized_domain or "развит" in normalized_domain:
            avoid_values.extend(["термины Service Desk", "вторую линию поддержки", "закрытие тикета"])
        if "финан" in normalized_domain or "бухгал" in normalized_domain:
            avoid_values.extend(["подрядчиков обучения", "участников тренинга", "оценку курсов"])
        if "инжен" in normalized_domain or "конструкт" in normalized_domain:
            avoid_values.extend(["оценку эффективности обучения", "заказчика обучения"])
        role_scenarios = [
            str(item).strip()
            for item in self._parse_bullets(role.get("typical_scenarios") if role else None)
            if str(item).strip() and not self._looks_like_case_scene(item)
        ]
        recommended_contexts = self._merge_unique_text_values(role_scenarios[:3], process_values[:3], task_values[:3], limit=6)
        return {
            "how_to_adapt_scenarios": f"Сценарии нужно адаптировать под домен «{domain or 'не определен'}» и роль пользователя: {role_hint}.",
            "what_to_include": include_values[:6],
            "what_to_avoid": avoid_values[:6],
            "recommended_case_contexts": recommended_contexts[:4],
        }

    def _build_user_artifacts(
        self,
        *,
        domain_profile: dict | None,
        role: dict | None = None,
    ) -> list[str]:
        artifacts: list[str] = []
        raw_values = self._split_compound_values(
            [str(item).strip() for item in ((domain_profile or {}).get("artifacts") or []) if str(item).strip()],
            split_conjunction=True,
        )
        raw_values.extend(
            self._split_compound_values(
                [
                    str(item).strip()
                    for item in (
                        self._parse_bullets(role.get("work_objects") if role else None)
                        + self._parse_bullets(role.get("templates_tools") if role else None)
                    )
                    if str(item).strip()
                ],
                split_conjunction=True,
            )
        )
        for item in raw_values:
            text = str(item).strip()
            if text and text not in artifacts and not self._looks_like_case_scene(text) and len(text.split()) <= 5:
                artifacts.append(text)
        return artifacts[:8]

    def _build_user_systems(self, *, domain_profile: dict | None, role: dict | None = None) -> list[str]:
        systems: list[str] = []
        raw_values = self._split_compound_values(
            [str(item).strip() for item in ((domain_profile or {}).get("systems") or []) if str(item).strip()],
            split_conjunction=True,
        )
        raw_values.extend(
            self._split_compound_values(
                [str(item).strip() for item in self._parse_bullets(role.get("information_sources") if role else None) if str(item).strip()],
                split_conjunction=True,
            )
        )
        for item in raw_values:
            text = str(item).strip()
            if text and text not in systems and self._looks_like_system_name(text):
                systems.append(text)
        return systems[:8]

    def _build_user_success_metrics(
        self,
        *,
        domain_family: str | None,
        role_code: str | None,
        role: dict | None = None,
    ) -> list[str]:
        family = str(domain_family or "").strip().lower()
        role_metrics = [str(item).strip() for item in self._parse_bullets(role.get("success_metrics") if role else None) if str(item).strip()]
        metrics_map = {
            "learning_and_development": [
                "срок запуска программы",
                "доходимость участников",
                "удовлетворенность обучением",
                "применимость программы в работе",
            ],
            "client_service": [
                "срок ответа клиенту",
                "срок решения обращения",
                "уровень удовлетворенности клиента",
                "доля повторных обращений",
            ],
            "engineering": [
                "срок выпуска КД",
                "доля возвратов по замечаниям",
                "комплектность документации",
                "своевременная передача в производство",
            ],
            "it_support": [
                "срок реакции на заявку",
                "срок решения инцидента",
                "доля повторных обращений",
                "подтверждение результата пользователем",
            ],
        }
        metrics = list(role_metrics or metrics_map.get(family, []))
        if not metrics:
            metrics = [
                "срок выполнения следующего шага",
                "качество результата",
                "согласованность со стейкхолдерами",
            ]
        if role_code == "leader" and "достижение целевых показателей направления" not in metrics:
            metrics.append("достижение целевых показателей направления")
        return metrics[:6]

    def _build_domain_resolution_status(
        self,
        *,
        domain_code: str | None,
        best_external_candidate: dict | None,
        domain_catalog_entry: dict | None,
    ) -> str:
        code = str(domain_code or "").strip().lower()
        if best_external_candidate and code and code == str(best_external_candidate.get("resolved_domain_code") or "").strip().lower():
            return "catalog_and_external_match"
        if best_external_candidate and str(best_external_candidate.get("resolved_domain_code") or "").strip():
            return "external_match"
        if domain_catalog_entry and code and code != "generic":
            return "catalog_match"
        if code == "generic" or not code:
            return "fallback"
        return "inferred"

    def _estimate_domain_confidence(
        self,
        *,
        domain_code: str | None,
        best_external_candidate: dict | None,
        role_consistency_status: str,
    ) -> float:
        code = str(domain_code or "").strip().lower()
        if not code:
            base = 0.45
        elif code == "generic":
            base = 0.6
        else:
            base = 0.8
        if best_external_candidate and str(best_external_candidate.get("resolved_domain_code") or "").strip().lower() == code:
            base = max(base, 0.9)
        if role_consistency_status == "partially_consistent":
            base -= 0.05
        if role_consistency_status == "inconsistent":
            base -= 0.15
        return round(max(0.0, min(1.0, base)), 2)

    def _build_profile_quality(
        self,
        *,
        instruction: dict | None,
        cleaned_position: str | None,
        normalized_duties_items: list[str],
        company_context: str | None,
        role_consistency_status: str,
        domain_resolution_status: str,
        domain_confidence: float,
        role_confidence: float,
        missing_required_fields_count: int = 0,
        data_quality_notes: list[str],
    ) -> dict:
        if cleaned_position and normalized_duties_items and company_context:
            completeness = "high"
        elif cleaned_position and normalized_duties_items:
            completeness = "medium"
        else:
            completeness = "low"
        needs_clarification = (
            completeness == "low"
            or role_consistency_status == "inconsistent"
            or domain_resolution_status in {"fallback", "needs_clarification"}
        )
        clarification_questions = (
            self._build_instruction_clarification_questions(
                instruction=instruction,
                company_context=company_context,
                role_consistency_status=role_consistency_status,
                domain_resolution_status=domain_resolution_status,
            )
            if needs_clarification
            else []
        )
        profile_confidence = (float(domain_confidence) * 0.45) + (float(role_confidence) * 0.45)
        if completeness == "medium":
            profile_confidence -= 0.08
        if completeness == "low":
            profile_confidence -= 0.18
        if role_consistency_status == "partially_consistent":
            profile_confidence -= 0.05
        if role_consistency_status == "inconsistent":
            profile_confidence -= 0.12
        if domain_resolution_status in {"fallback", "needs_clarification"}:
            profile_confidence -= 0.1
        profile_confidence -= min(missing_required_fields_count, 4) * 0.04
        profile_confidence = round(max(0.0, min(1.0, profile_confidence)), 2)
        return {
            "completeness": completeness,
            "confidence": profile_confidence,
            "warnings": data_quality_notes,
            "needs_clarification": needs_clarification,
            "clarification_questions": clarification_questions,
        }

    def _load_profile_build_instruction(
        self,
        *,
        connection,
        role_code: str | None,
        domain_family: str | None,
    ) -> dict | None:
        return connection.execute(
            """
            SELECT instruction_code, instruction_name, applies_to_role_code, applies_to_domain_family,
                   instruction_text, priority, version
            FROM profile_build_instructions
            WHERE is_active = TRUE
              AND (applies_to_role_code IS NULL OR applies_to_role_code = %s)
              AND (applies_to_domain_family IS NULL OR applies_to_domain_family = %s)
            ORDER BY
                CASE WHEN applies_to_role_code IS NULL THEN 1 ELSE 0 END ASC,
                CASE WHEN applies_to_domain_family IS NULL THEN 1 ELSE 0 END ASC,
                priority ASC,
                id ASC
            LIMIT 1
            """,
            (role_code, domain_family),
        ).fetchone()

    def _build_profile_build_summary(
        self,
        *,
        instruction: dict | None,
        selected_role_match: RoleMatch | None,
        detected_role_match: RoleMatch | None,
        role_consistency_status: str,
        domain_profile: dict,
        domain_resolution_status: str,
        best_external_candidate: dict | None,
    ) -> str:
        selected_label = selected_role_match.name if selected_role_match else "не выбрана явно"
        detected_label = detected_role_match.name if detected_role_match else "не определена"
        domain_label = str(domain_profile.get("domain_label") or domain_profile.get("domain_family") or domain_profile.get("domain_code") or "не определен")
        base = (
            f"Профиль сформирован по инструкции «{instruction['instruction_name']}»."
            if instruction
            else "Профиль сформирован по встроенной инструкции системы."
        )
        role_part = (
            f" Выбранная роль: «{selected_label}», интерпретация системы: «{detected_label}»,"
            f" статус согласованности роли: {role_consistency_status}."
        )
        domain_part = (
            f" Домен определен как «{domain_label}» со статусом {domain_resolution_status}."
        )
        if best_external_candidate:
            domain_part += f" Внешний контур подтвердил это кандидатом «{best_external_candidate['candidate'].label}»."
        return f"{base}{role_part}{domain_part}"

    def _build_profile_build_trace(
        self,
        *,
        instruction: dict | None,
        selected_role_match: RoleMatch | None,
        detected_role_match: RoleMatch | None,
        role_consistency_status: str,
        role_consistency_comment: str,
        normalization: dict,
        domain_profile: dict,
        domain_resolution_status: str,
        domain_confidence: float,
        resolved_external_candidates: list[dict],
        best_external_candidate: dict | None,
        data_quality_notes: list[str],
        profile_quality: dict,
    ) -> dict:
        return {
            "instruction": {
                "code": instruction.get("instruction_code") if instruction else None,
                "name": instruction.get("instruction_name") if instruction else None,
                "version": instruction.get("version") if instruction else None,
            },
            "selected_role": {
                "code": selected_role_match.code if selected_role_match else None,
                "name": selected_role_match.name if selected_role_match else None,
            },
            "detected_role": {
                "code": detected_role_match.code if detected_role_match else None,
                "name": detected_role_match.name if detected_role_match else None,
                "confidence": detected_role_match.confidence if detected_role_match else None,
            },
            "role_consistency": {
                "status": role_consistency_status,
                "comment": role_consistency_comment,
            },
            "normalization": {
                "cleaned_position": normalization.cleaned_position,
                "normalized_company_industry": normalization.normalized_company_industry_fallback,
                "normalized_duties_items": normalization.normalized_duties_items,
            },
            "domain_resolution": {
                "domain_code": domain_profile.get("domain_code"),
                "domain_family": domain_profile.get("domain_family"),
                "domain_label": domain_profile.get("domain_label"),
                "status": domain_resolution_status,
                "confidence": domain_confidence,
            },
            "external_candidates": [
                {
                    "label": item["candidate"].label,
                    "resolved_domain_code": item.get("resolved_domain_code"),
                    "resolved_family_name": item.get("resolved_family_name"),
                    "mapping_confidence": item.get("mapping_confidence"),
                }
                for item in resolved_external_candidates
            ],
            "best_external_candidate": (
                {
                    "label": best_external_candidate["candidate"].label,
                    "resolved_domain_code": best_external_candidate.get("resolved_domain_code"),
                    "resolved_family_name": best_external_candidate.get("resolved_family_name"),
                    "mapping_confidence": best_external_candidate.get("mapping_confidence"),
                }
                if best_external_candidate
                else None
            ),
            "data_quality_notes": data_quality_notes,
            "profile_quality": profile_quality,
        }

    def _build_user_context_profile(
        self,
        *,
        connection,
        position: str | None,
        duties: str | None,
        normalized_duties: str | None,
        company_industry: str | None,
        role: dict | None,
        role_match: RoleMatch | None,
        selected_role_match: RoleMatch | None = None,
        detected_role_match: RoleMatch | None = None,
    ) -> dict:
        normalization = build_profile_normalization_result(
            position=position,
            duties=duties,
            normalized_duties=normalized_duties,
            company_industry=company_industry,
        )
        primary_role_match = selected_role_match or role_match
        source_text = normalization.source_text
        normalized_company_industry = self.normalize_company_industry(
            company_industry,
            position=position,
            duties=duties,
            normalized_duties=normalization.normalized_duties_text,
        )
        domain_profile = deepseek_client.generate_domain_profile(
            position=position,
            duties=duties or normalization.normalized_duties_text,
            company_industry=normalized_company_industry or company_industry,
            role_name=primary_role_match.name if primary_role_match else None,
        )
        external_candidates = external_knowledge_service.search_professional_candidates(
            position=position,
            duties=duties or normalized_duties,
            limit=5,
        )
        resolved_external_candidates = external_knowledge_service.resolve_candidates_to_domains(
            candidates=external_candidates,
        )
        preferred_external_domain_code = str(domain_profile.get("domain_code") or "").strip().lower()
        best_external_candidate = external_knowledge_service.select_best_resolved_candidate(
            resolved_candidates=resolved_external_candidates,
            preferred_domain_code=preferred_external_domain_code if preferred_external_domain_code and preferred_external_domain_code != "generic" else None,
        )
        for resolved_candidate in resolved_external_candidates:
            candidate = resolved_candidate["candidate"]
            resolved_domain_code = resolved_candidate.get("resolved_domain_code")
            mapping_confidence = float(resolved_candidate.get("mapping_confidence") or 0)
            if resolved_domain_code:
                external_knowledge_service.persist_mapping(
                    candidate=candidate,
                    domain_code=str(resolved_domain_code),
                    confidence_score=mapping_confidence,
                    is_verified=False,
                )
        current_domain_code = str(domain_profile.get("domain_code") or "").strip().lower()
        current_domain_family = str(domain_profile.get("domain_family") or "").strip().lower()
        if best_external_candidate and (not current_domain_code or current_domain_code == "generic" or current_domain_family == "generic"):
            external_family = str(best_external_candidate.get("resolved_family_name") or "").strip().lower()
            external_domain_code = str(best_external_candidate.get("resolved_domain_code") or "").strip().lower()
            catalog_entry = deepseek_client._get_domain_catalog_entry(external_family) if external_family else None
            if catalog_entry:
                merged_external_profile = {
                    **domain_profile,
                    "domain_code": catalog_entry.get("domain_code") or external_domain_code,
                    "domain_family": catalog_entry.get("family_name") or external_family,
                    "domain_label": catalog_entry.get("display_name") or domain_profile.get("domain_label"),
                    "domain_catalog_entry": catalog_entry,
                }
                domain_profile = deepseek_client._merge_domain_catalog_template(merged_external_profile, catalog_entry)
        role_consistency_status, role_consistency_comment = self._build_role_consistency(
            selected_role_match=selected_role_match,
            detected_role_match=detected_role_match,
            position=position,
            duties=duties,
            normalized_duties=normalized_duties,
        )
        instruction = self._load_profile_build_instruction(
            connection=connection,
            role_code=primary_role_match.code if primary_role_match else None,
            domain_family=str(domain_profile.get("domain_family") or domain_profile.get("domain_code") or ""),
        )
        domain = str(
            domain_profile.get("domain_label")
            or normalized_company_industry
            or self._infer_domain(position, duties or normalized_duties, company_industry)
        )
        processes = self._build_user_processes(
            domain_profile=domain_profile,
            normalized_duties=normalized_duties,
            position=position,
            duties=duties,
        )
        tasks = self._build_user_tasks(
            normalized_duties_items=normalization.normalized_duties_items,
            duties=duties,
            domain_profile=domain_profile,
            role=role,
            role_code=primary_role_match.code if primary_role_match else None,
            position=position,
        )
        stakeholder_seed = self._build_user_stakeholders(
            role_code=primary_role_match.code if primary_role_match else None,
            source_text=source_text,
            domain_profile=domain_profile,
            position=position,
        )
        risks = self._build_user_risks(
            role_code=primary_role_match.code if primary_role_match else None,
            source_text=source_text,
            domain_profile=domain_profile,
            role=role,
        )
        constraints = self._build_user_constraints(
            role=role,
            source_text=source_text,
            domain_profile=domain_profile,
        )
        user_artifacts = self._build_user_artifacts(domain_profile=domain_profile, role=role)
        user_systems = self._build_user_systems(domain_profile=domain_profile, role=role)
        user_success_metrics = self._build_user_success_metrics(
            domain_family=domain_profile.get("domain_family"),
            role_code=primary_role_match.code if primary_role_match else None,
            role=role,
        )
        domain_resolution_status = self._build_domain_resolution_status(
            domain_code=domain_profile.get("domain_code"),
            best_external_candidate=best_external_candidate,
            domain_catalog_entry=domain_profile.get("domain_catalog_entry"),
        )
        data_quality_notes: list[str] = []
        raw_company = str(company_industry or "")
        if "роль:" in raw_company.lower():
            data_quality_notes.append("В company_industry обнаружен служебный хвост, поле требует очистки.")
        suspicious_duties = [
            item for item in normalization.normalized_duties_items
            if item.lower().startswith(("рганиз", "ланир", "нализ", "ценива"))
        ]
        if suspicious_duties:
            data_quality_notes.append("В исходных обязанностях обнаружены признаки поврежденного текста или потери первой буквы.")
        if role_consistency_status in {"partially_consistent", "inconsistent"}:
            data_quality_notes.append(role_consistency_comment)
        if str(domain_profile.get("domain_code") or "").strip().lower() == "generic":
            data_quality_notes.append("Профиль остался в generic-контуре и требует дополнительного уточнения домена.")
        data_quality_notes.extend(
            self._apply_instruction_quality_rules(
                instruction=instruction,
                selected_role_match=selected_role_match,
                detected_role_match=detected_role_match,
                user_domain=domain,
                processes=processes,
                tasks=tasks,
                stakeholders=stakeholder_seed,
                risks=risks,
                constraints=constraints,
                user_artifacts=user_artifacts,
                user_systems=user_systems,
            )
        )
        deduped_quality_notes: list[str] = []
        seen_quality_notes: set[str] = set()
        for note in data_quality_notes:
            normalized_note = str(note).strip()
            if normalized_note and normalized_note not in seen_quality_notes:
                seen_quality_notes.add(normalized_note)
                deduped_quality_notes.append(normalized_note)
        data_quality_notes = deduped_quality_notes
        domain_confidence = self._estimate_domain_confidence(
            domain_code=domain_profile.get("domain_code"),
            best_external_candidate=best_external_candidate,
            role_consistency_status=role_consistency_status,
        )
        role_confidence = self._resolve_role_confidence(
            selected_role_match=selected_role_match,
            detected_role_match=detected_role_match,
            role_consistency_status=role_consistency_status,
            cleaned_position=normalization.cleaned_position,
            normalized_duties_items=normalization.normalized_duties_items,
        )
        role_limits = (
            self._build_role_limits(
                role or {},
                primary_role_match.code if primary_role_match else "",
                stakeholder_seed,
                instruction=instruction,
                user_domain=domain,
            )
            if role and primary_role_match
            else {}
        )
        role_vocabulary = (
            self._build_role_vocabulary(
                role or {},
                primary_role_match.code if primary_role_match else "",
                normalized_duties,
                instruction=instruction,
                user_domain=domain,
                domain_profile=domain_profile,
                processes=processes,
                tasks=tasks,
                stakeholders=stakeholder_seed,
            )
            if role and primary_role_match
            else {}
        )
        stakeholders = self._build_user_stakeholders(
            role_code=primary_role_match.code if primary_role_match else None,
            source_text=source_text,
            domain_profile=domain_profile,
            role_limits=role_limits,
            role_vocabulary=role_vocabulary,
            position=position,
        )
        llm_profile_lists = deepseek_client.generate_profile_context_lists(
            position=position,
            duties=duties or normalized_duties,
            company_industry=normalized_company_industry or company_industry,
            role_name=primary_role_match.name if primary_role_match else None,
            selected_role_name=selected_role_match.name if selected_role_match else None,
            selected_role_code=selected_role_match.code if selected_role_match else None,
            instruction_text=instruction.get("instruction_text") if instruction else None,
            user_domain=domain,
            domain_profile=domain_profile,
            user_constraints=constraints,
            user_artifacts=user_artifacts,
            user_systems=user_systems,
            user_success_metrics=user_success_metrics,
        )
        if llm_profile_lists:
            llm_processes = [str(item).strip() for item in (llm_profile_lists.get("user_processes") or []) if str(item).strip()]
            llm_tasks = [str(item).strip() for item in (llm_profile_lists.get("user_tasks") or []) if str(item).strip()]
            llm_stakeholders = [str(item).strip() for item in (llm_profile_lists.get("user_stakeholders") or []) if str(item).strip()]
            if llm_processes:
                processes = self._merge_unique_text_values(llm_processes, processes, limit=6)
            if llm_tasks:
                raw_duties_text = self.normalize_text(duties or normalized_duties or "")
                llm_tasks_normalized = {self.normalize_text(item) for item in llm_tasks if str(item).strip()}
                looks_like_single_raw_copy = (
                    len(llm_tasks) == 1
                    and bool(raw_duties_text)
                    and raw_duties_text in llm_tasks_normalized
                )
                if looks_like_single_raw_copy:
                    tasks = self._merge_unique_text_values(tasks, llm_tasks, limit=8)
                else:
                    tasks = self._merge_unique_text_values(llm_tasks, tasks, limit=8)
            if llm_stakeholders:
                stakeholders = self._merge_unique_text_values(llm_stakeholders, stakeholders, limit=6)
        llm_profile_validation = deepseek_client.validate_profile_context_lists(
            position=position,
            duties=duties or normalized_duties,
            company_industry=normalized_company_industry or company_industry,
            role_name=primary_role_match.name if primary_role_match else None,
            selected_role_name=selected_role_match.name if selected_role_match else None,
            selected_role_code=selected_role_match.code if selected_role_match else None,
            instruction_text=instruction.get("instruction_text") if instruction else None,
            user_domain=domain,
            domain_profile=domain_profile,
            user_processes=processes,
            user_tasks=tasks,
            user_stakeholders=stakeholders,
            user_constraints=constraints,
            user_artifacts=user_artifacts,
            user_systems=user_systems,
            user_success_metrics=user_success_metrics,
        )
        if llm_profile_validation:
            validated_processes = [str(item).strip() for item in (llm_profile_validation.get("user_processes") or []) if str(item).strip()]
            validated_tasks = [str(item).strip() for item in (llm_profile_validation.get("user_tasks") or []) if str(item).strip()]
            validated_stakeholders = [str(item).strip() for item in (llm_profile_validation.get("user_stakeholders") or []) if str(item).strip()]
            if validated_processes:
                processes = validated_processes[:6]
            if validated_tasks:
                tasks = validated_tasks[:8]
            if validated_stakeholders:
                stakeholders = validated_stakeholders[:6]
            validation_warnings = [
                str(item).strip()
                for item in (llm_profile_validation.get("warnings") or [])
                if str(item).strip()
            ]
            if validation_warnings:
                data_quality_notes.extend(validation_warnings[:5])
        profile_build_summary = self._build_profile_build_summary(
            instruction=instruction,
            selected_role_match=selected_role_match,
            detected_role_match=detected_role_match,
            role_consistency_status=role_consistency_status,
            domain_profile=domain_profile,
            domain_resolution_status=domain_resolution_status,
            best_external_candidate=best_external_candidate,
        )
        context_vars = {
            "domain": domain,
            "domain_code": domain_profile.get("domain_code"),
            "domain_family": domain_profile.get("domain_family"),
            "domain_catalog_entry": domain_profile.get("domain_catalog_entry"),
            "domain_profile": domain_profile,
            "external_occupation_candidates": [
                {
                    "source": item["candidate"].source,
                    "external_id": item["candidate"].external_id,
                    "label": item["candidate"].label,
                    "description": item["candidate"].description,
                    "skills": item["candidate"].skills,
                    "broader_domain": item["candidate"].broader_domain,
                    "match_score": item["candidate"].match_score,
                    "resolved_domain_code": item.get("resolved_domain_code"),
                    "resolved_family_name": item.get("resolved_family_name"),
                    "resolved_display_name": item.get("resolved_display_name"),
                    "mapping_confidence": item.get("mapping_confidence"),
                }
                for item in resolved_external_candidates
            ],
            "best_external_occupation_candidate": {
                "source": best_external_candidate["candidate"].source,
                "external_id": best_external_candidate["candidate"].external_id,
                "label": best_external_candidate["candidate"].label,
                "description": best_external_candidate["candidate"].description,
                "skills": best_external_candidate["candidate"].skills,
                "broader_domain": best_external_candidate["candidate"].broader_domain,
                "match_score": best_external_candidate["candidate"].match_score,
                "resolved_domain_code": best_external_candidate.get("resolved_domain_code"),
                "resolved_family_name": best_external_candidate.get("resolved_family_name"),
                "resolved_display_name": best_external_candidate.get("resolved_display_name"),
                "mapping_confidence": best_external_candidate.get("mapping_confidence"),
            } if best_external_candidate else None,
            "company_industry": normalized_company_industry,
            "company_industry_raw": company_industry,
            "company_context": normalized_company_industry or company_industry,
            "position": position,
            "role_code": role_match.code if role_match else None,
            "role_name": role_match.name if role_match else None,
            "selected_role_code": selected_role_match.code if selected_role_match else None,
            "selected_role_name": selected_role_match.name if selected_role_match else None,
            "role_registry_reference": {
                "short_definition": role.get("short_definition") if role else None,
                "mission": self._parse_bullets(role.get("mission") if role else None),
                "typical_tasks": self._parse_bullets(role.get("typical_tasks") if role else None),
                "work_objects": self._parse_bullets(role.get("work_objects") if role else None),
                "planning_horizon": role.get("planning_horizon") if role else None,
                "impact_scale": role.get("impact_scale") if role else None,
                "authority_allowed": self._parse_bullets(role.get("authority_allowed") if role else None),
                "authority_requires_approval": self._parse_bullets(role.get("authority_requires_approval") if role else None),
                "role_limits": self._parse_bullets(role.get("role_limits") if role else None),
                "red_lines": self._parse_bullets(role.get("red_lines") if role else None),
                "escalation_rules": self._parse_bullets(role.get("escalation_rules") if role else None),
                "success_metrics": self._parse_bullets(role.get("success_metrics") if role else None),
                "risks": self._parse_bullets(role.get("risks") if role else None),
                "interaction_scope": self._parse_bullets(role.get("interaction_scope") if role else None),
                "communication_rules": self._parse_bullets(role.get("communication_rules") if role else None),
                "typical_scenarios": self._parse_bullets(role.get("typical_scenarios") if role else None),
                "information_sources": self._parse_bullets(role.get("information_sources") if role else None),
                "templates_tools": self._parse_bullets(role.get("templates_tools") if role else None),
                "personalization_variables": self._parse_bullets(role.get("personalization_variables") if role else None),
            },
            "processes": processes,
            "tasks": tasks,
            "stakeholders": stakeholders,
            "risks": risks,
            "constraints": constraints,
            "artifacts": user_artifacts,
            "systems": user_systems,
            "success_metrics": user_success_metrics,
            "domain_resolution_status": domain_resolution_status,
            "domain_confidence": domain_confidence,
        }
        normalized_input = {
            "position_normalized": normalization.cleaned_position,
            "duties_normalized": normalization.normalized_duties_items,
            "company_industry_normalized": normalized_company_industry or company_industry,
            "selected_role_code": selected_role_match.code if selected_role_match else None,
            "selected_role_name": selected_role_match.name if selected_role_match else None,
        }
        user_work_context = {
            "user_domain": domain,
            "company_industry_context": normalized_company_industry or company_industry,
            "user_processes": processes,
            "user_tasks": tasks,
            "user_stakeholders": stakeholders,
            "user_risks": risks,
            "user_constraints": constraints,
            "user_artifacts": user_artifacts,
            "user_systems": user_systems,
            "user_success_metrics": user_success_metrics,
        }
        domain_profile_block = self._build_domain_profile_block(
            {
                **(domain_profile or {}),
                "domain_resolution_status": domain_resolution_status,
            },
            instruction=instruction,
        )
        adaptation_rules_for_cases = self._build_adaptation_rules_for_cases(
            domain=domain,
            role_code=role_match.code if role_match else None,
            role=role,
            processes=processes,
            tasks=tasks,
            stakeholders=stakeholders,
            risks=risks,
            constraints=constraints,
        )
        role_skill_profile = self._build_role_skill_profile(
            role_match.role_id if role_match else None,
            role_match.code if role_match else None,
            instruction=instruction,
        )
        profile_payload = {
            "profile_metadata": {
                "profile_version": "1.0",
                "profile_type": "personalized_user_profile",
                "source": "user_input",
                "status": "created",
            },
            "normalized_input": normalized_input,
            "role_interpretation": {
                "selected_role_code": selected_role_match.code if selected_role_match else None,
                "selected_role_name": selected_role_match.name if selected_role_match else None,
                "role_rationale": None,
                "role_confidence": role_confidence,
                "role_consistency_status": role_consistency_status,
                "role_consistency_comment": role_consistency_comment,
            },
            "user_work_context": user_work_context,
            "role_limits": role_limits,
            "role_vocabulary": role_vocabulary,
            "domain_profile": domain_profile_block,
            "role_skill_profile": role_skill_profile,
            "adaptation_rules_for_cases": adaptation_rules_for_cases,
            "profile_quality": {
                "completeness": None,
                "confidence": None,
            },
        }
        profile_quality = self._build_profile_quality(
            instruction=instruction,
            cleaned_position=normalization.cleaned_position,
            normalized_duties_items=normalization.normalized_duties_items,
            company_context=normalized_company_industry or company_industry,
            role_consistency_status=role_consistency_status,
            domain_resolution_status=domain_resolution_status,
            domain_confidence=domain_confidence,
            role_confidence=role_confidence,
            data_quality_notes=data_quality_notes,
        )
        profile_payload["profile_quality"] = profile_quality
        missing_required_fields = self._find_missing_required_profile_fields(
            instruction=instruction,
            profile_payload=profile_payload,
        )
        if missing_required_fields:
            data_quality_notes.append(
                "В профиле не заполнены обязательные поля: " + ", ".join(missing_required_fields[:10]) + "."
            )
        profile_quality = self._build_profile_quality(
            instruction=instruction,
            cleaned_position=normalization.cleaned_position,
            normalized_duties_items=normalization.normalized_duties_items,
            company_context=normalized_company_industry or company_industry,
            role_consistency_status=role_consistency_status,
            domain_resolution_status=domain_resolution_status,
            domain_confidence=domain_confidence,
            role_confidence=role_confidence,
            missing_required_fields_count=len(missing_required_fields),
            data_quality_notes=data_quality_notes,
        )
        profile_payload["profile_quality"] = profile_quality
        if missing_required_fields:
            profile_quality["needs_clarification"] = True
            existing_questions = list(profile_quality.get("clarification_questions") or [])
            if len(existing_questions) < 3:
                existing_questions.append("Уточните, пожалуйста, недостающие данные по рабочему контексту, чтобы профиль можно было собрать полностью и без доменных допущений.")
            profile_quality["clarification_questions"] = existing_questions[:3]
            profile_quality["warnings"] = data_quality_notes
        profile_payload["profile_quality"] = profile_quality
        profile_payload["profile_metadata"]["status"] = "needs_clarification" if profile_quality.get("needs_clarification") else "created"
        profile_build_trace = self._build_profile_build_trace(
            instruction=instruction,
            selected_role_match=selected_role_match,
            detected_role_match=detected_role_match,
            role_consistency_status=role_consistency_status,
            role_consistency_comment=role_consistency_comment,
            normalization=normalization,
            domain_profile=domain_profile,
            domain_resolution_status=domain_resolution_status,
            domain_confidence=domain_confidence,
            resolved_external_candidates=resolved_external_candidates,
            best_external_candidate=best_external_candidate,
            data_quality_notes=data_quality_notes,
            profile_quality=profile_quality,
        )
        return {
            "role_selected": selected_role_match.name if selected_role_match else None,
            "role_selected_code": selected_role_match.code if selected_role_match else None,
            "role_consistency_status": role_consistency_status,
            "role_consistency_comment": role_consistency_comment,
            "role_confidence": role_confidence,
            "profile_build_instruction_code": instruction.get("instruction_code") if instruction else None,
            "profile_build_summary": profile_build_summary,
            "profile_build_trace": profile_build_trace,
            "company_context": normalized_company_industry or company_industry,
            "profile_metadata": profile_payload["profile_metadata"],
            "normalized_input": normalized_input,
            "role_interpretation": profile_payload["role_interpretation"],
            "user_work_context": user_work_context,
            "domain_profile_block": domain_profile_block,
            "adaptation_rules_for_cases": adaptation_rules_for_cases,
            "user_domain": domain,
            "user_processes": processes,
            "user_tasks": tasks,
            "user_stakeholders": stakeholders,
            "user_risks": risks,
            "user_constraints": constraints,
            "user_artifacts": user_artifacts,
            "user_systems": user_systems,
            "user_success_metrics": user_success_metrics,
            "data_quality_notes": data_quality_notes,
            "domain_resolution_status": domain_resolution_status,
            "domain_confidence": domain_confidence,
            "profile_quality": profile_quality,
            "user_context_vars": context_vars,
            "role_limits": role_limits,
            "role_vocabulary": role_vocabulary,
            "role_skill_profile": role_skill_profile,
        }

    def _save_user_profile(
        self,
        *,
        connection,
        user_id: int,
        raw_position: str | None,
        raw_duties: str | None,
        normalized_duties: str | None,
        company_industry: str | None,
        role_match: RoleMatch | None,
        selected_role_match: RoleMatch | None = None,
        detected_role_match: RoleMatch | None = None,
    ) -> int:
        roles = self._load_roles()
        role = next((item for item in roles if role_match and item["id"] == role_match.role_id), None)
        user_row = connection.execute(
            "SELECT full_name FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        full_name = user_row["full_name"] if user_row else None
        profile_data = self._build_user_context_profile(
            connection=connection,
            position=raw_position,
            duties=raw_duties,
            normalized_duties=normalized_duties,
            company_industry=company_industry,
            role=role,
            role_match=role_match,
            selected_role_match=selected_role_match,
            detected_role_match=detected_role_match,
        )
        persisted_detected_role = detected_role_match or role_match
        role_rationale = self._build_role_rationale(
            persisted_detected_role,
            position=raw_position,
            duties=raw_duties,
            normalized_duties=normalized_duties,
            selected=detected_role_match is None,
        )
        raw_input = {
            "full_name": full_name,
            "position": raw_position,
            "duties": raw_duties,
            "company_industry": company_industry,
            "selected_role": profile_data["role_selected"],
        }
        role_interpretation = {
            "selected_role_code": profile_data["role_selected_code"],
            "selected_role_name": profile_data["role_selected"],
            "role_rationale": role_rationale,
            "role_confidence": persisted_detected_role.confidence if persisted_detected_role else None,
            "role_consistency_status": profile_data["role_consistency_status"],
            "role_consistency_comment": profile_data["role_consistency_comment"],
        }
        profile_metadata = {
            "profile_version": "1.0",
            "profile_type": "personalized_user_profile",
            "source": "user_input",
            "status": "needs_clarification" if profile_data["profile_quality"].get("needs_clarification") else "created",
        }
        version_row = connection.execute(
            "SELECT COALESCE(MAX(profile_version), 0) + 1 AS next_version FROM user_role_profiles WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        profile_row = connection.execute(
            """
            INSERT INTO user_role_profiles (
                user_id, role_id, detected_role, raw_position, raw_duties, normalized_duties,
                role_selected, role_selected_code, role_confidence, role_rationale,
                role_consistency_status, role_consistency_comment,
                profile_build_instruction_code, profile_build_summary, profile_build_trace,
                company_context, profile_metadata, raw_input, normalized_input, role_interpretation, user_work_context,
                role_limits, role_vocabulary, domain_profile, role_skill_profile, adaptation_rules_for_cases, user_domain,
                user_processes, user_tasks, user_stakeholders, user_risks, user_constraints,
                user_artifacts, user_systems, user_success_metrics, data_quality_notes,
                domain_resolution_status, domain_confidence, profile_quality,
                user_context_vars, profile_version, profile_updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s::jsonb,
                %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s,
                %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                %s, %s, %s::jsonb,
                %s::jsonb, %s, CURRENT_TIMESTAMP
            )
            RETURNING id
            """,
            (
                user_id,
                role_match.role_id if role_match else None,
                persisted_detected_role.code if persisted_detected_role else None,
                raw_position,
                raw_duties,
                normalized_duties,
                profile_data["role_selected"],
                profile_data["role_selected_code"],
                profile_data["role_confidence"],
                role_rationale,
                profile_data["role_consistency_status"],
                profile_data["role_consistency_comment"],
                profile_data["profile_build_instruction_code"],
                profile_data["profile_build_summary"],
                json.dumps(profile_data["profile_build_trace"], ensure_ascii=False),
                profile_data["company_context"],
                json.dumps(profile_metadata, ensure_ascii=False),
                json.dumps(raw_input, ensure_ascii=False),
                json.dumps(profile_data["normalized_input"], ensure_ascii=False),
                json.dumps(role_interpretation, ensure_ascii=False),
                json.dumps(profile_data["user_work_context"], ensure_ascii=False),
                json.dumps(profile_data["role_limits"], ensure_ascii=False),
                json.dumps(profile_data["role_vocabulary"], ensure_ascii=False),
                json.dumps(profile_data["domain_profile_block"], ensure_ascii=False),
                json.dumps(profile_data["role_skill_profile"], ensure_ascii=False),
                json.dumps(profile_data["adaptation_rules_for_cases"], ensure_ascii=False),
                profile_data["user_domain"],
                json.dumps(profile_data["user_processes"], ensure_ascii=False),
                json.dumps(profile_data["user_tasks"], ensure_ascii=False),
                json.dumps(profile_data["user_stakeholders"], ensure_ascii=False),
                json.dumps(profile_data["user_risks"], ensure_ascii=False),
                json.dumps(profile_data["user_constraints"], ensure_ascii=False),
                json.dumps(profile_data["user_artifacts"], ensure_ascii=False),
                json.dumps(profile_data["user_systems"], ensure_ascii=False),
                json.dumps(profile_data["user_success_metrics"], ensure_ascii=False),
                json.dumps(profile_data["data_quality_notes"], ensure_ascii=False),
                profile_data["domain_resolution_status"],
                profile_data["domain_confidence"],
                json.dumps(profile_data["profile_quality"], ensure_ascii=False),
                json.dumps(profile_data["user_context_vars"], ensure_ascii=False),
                version_row["next_version"],
            ),
        ).fetchone()
        connection.execute(
            "UPDATE users SET active_profile_id = %s WHERE id = %s",
            (profile_row["id"], user_id),
        )
        return profile_row["id"]

    def _build_user_response(self, row: dict) -> UserResponse:
        return UserResponse(**dict(row))

    def _load_user_by_id(self, connection, user_id: int) -> UserResponse:
        row = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()
        return self._build_user_response(row)

    def _build_backfill_payload(self, user: UserResponse) -> tuple[str | None, str | None, str | None, RoleMatch | None]:
        position = user.raw_position or user.job_description
        duties = user.raw_duties or user.normalized_duties
        normalization = build_profile_normalization_result(
            position=position,
            duties=duties,
            normalized_duties=user.normalized_duties,
            company_industry=user.company_industry,
        )
        normalized_duties = normalization.normalized_duties_text

        role_match: RoleMatch | None = None
        if user.role_id:
            role_match = self._resolve_selected_role(str(user.role_id))
        if role_match is None:
            role_match = self.detect_role(position, duties, normalized_duties)

        company_industry = user.company_industry
        if not (company_industry and company_industry.strip()):
            company_industry = self._infer_domain(position, duties or normalized_duties, user.company_industry)

        return position, duties, company_industry, role_match

    def backfill_user_profile(self, user_id: int) -> UserResponse | None:
        with get_connection() as connection:
            row = connection.execute(
                USER_SELECT_SQL
                + """
                WHERE u.id = %s
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                return None

            user = self._build_user_response(row)
            position, duties, company_industry, role_match = self._build_backfill_payload(user)
            normalized_duties = user.normalized_duties or self.normalize_duties(position, duties)

            connection.execute(
                """
                UPDATE users
                SET job_description = COALESCE(%s, job_description),
                    role_id = COALESCE(%s, role_id),
                    company_industry = COALESCE(%s, company_industry)
                WHERE id = %s
                """,
                (
                    self._clean_position(position),
                    role_match.role_id if role_match else None,
                    company_industry,
                    user_id,
                ),
            )

            detected_role_match = self.detect_role(position, duties, normalized_duties)
            self._save_user_profile(
                connection=connection,
                user_id=user_id,
                raw_position=position,
                raw_duties=duties,
                normalized_duties=normalized_duties,
                company_industry=company_industry,
                role_match=role_match,
                selected_role_match=self._resolve_selected_role(str(user.role_id)) if user.role_id else None,
                detected_role_match=detected_role_match,
            )
            connection.commit()
            return self._load_user_by_id(connection, user_id)

    def backfill_incomplete_users(self) -> int:
        updated = 0
        with get_connection() as connection:
            rows = connection.execute(
                USER_SELECT_SQL
                + """
                WHERE COALESCE(u.phone, '') <> ''
                  AND (
                    u.role_id IS NULL
                    OR NULLIF(TRIM(COALESCE(u.company_industry, '')), '') IS NULL
                    OR u.active_profile_id IS NULL
                    OR NULLIF(TRIM(COALESCE(p.normalized_duties, '')), '') IS NULL
                  )
                ORDER BY u.id ASC
                """
            ).fetchall()

        for row in rows:
            user = self._build_user_response(row)
            if self.backfill_user_profile(user.id) is not None:
                updated += 1
        return updated

    def create_user(
        self,
        *,
        full_name: str,
        email: str,
        telegram: str | None,
        consent_version: int | None,
        consent_text: str | None,
        position: str | None,
        duties: str | None,
        selected_role_id: int | None,
        company_industry: str | None,
        existing_user_id: int | None = None,
        progress_operation_id: str | None = None,
    ) -> tuple[UserResponse, RoleMatch | None]:
        normalization = build_profile_normalization_result(
            position=position,
            duties=duties,
            normalized_duties=None,
            company_industry=company_industry,
        )
        clean_position = normalization.cleaned_position
        operation_progress_service.advance(
            progress_operation_id,
            1,
            title="Очищаем и нормализуем данные",
            message="Нормализуем текст обязанностей и готовим данные профиля.",
        )
        normalized_duties = normalization.normalized_duties_text
        operation_progress_service.advance(
            progress_operation_id,
            2,
            title="Сохраняем выбранную роль",
            message="Фиксируем роль, которую пользователь выбрал в процессе регистрации.",
        )
        selected_role_match = self._resolve_selected_role(str(selected_role_id) if selected_role_id is not None else None)
        detected_role_match = self.detect_role(position, duties, normalized_duties)
        role_match = selected_role_match or detected_role_match
        normalized_telegram = self.normalize_telegram(telegram)
        with get_connection() as connection:
            if existing_user_id:
                row = connection.execute(
                    """
                    UPDATE users
                    SET full_name = %s,
                        email = %s,
                        phone = NULL,
                        telegram = %s,
                        personal_data_consent_accepted_at = CURRENT_TIMESTAMP,
                        personal_data_consent_version = %s,
                        personal_data_consent_text = %s,
                        job_description = %s,
                        role_id = %s,
                        company_industry = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        full_name,
                        email,
                        normalized_telegram,
                        consent_version,
                        consent_text,
                        clean_position,
                        selected_role_match.role_id if selected_role_match else None,
                        company_industry,
                        existing_user_id,
                    ),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    INSERT INTO users (
                        full_name, email, phone, telegram, personal_data_consent_accepted_at,
                        personal_data_consent_version, personal_data_consent_text,
                        job_description, role_id, company_industry
                    )
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        full_name,
                        email,
                        None,
                        normalized_telegram,
                        consent_version,
                        consent_text,
                        clean_position,
                        selected_role_match.role_id if selected_role_match else None,
                        company_industry,
                    ),
                ).fetchone()
            operation_progress_service.advance(
                progress_operation_id,
                3,
                title="Формируем расширенный профиль",
                message="Сохраняем контекст пользователя для персонализации кейсов.",
            )
            self._save_user_profile(
                connection=connection,
                user_id=row["id"],
                raw_position=position,
                raw_duties=duties,
                normalized_duties=normalized_duties,
                company_industry=company_industry,
                role_match=role_match,
                selected_role_match=selected_role_match,
                detected_role_match=detected_role_match,
            )
            connection.commit()
            user_response = self._load_user_by_id(connection, row["id"])

        return user_response, role_match

    def update_user(
        self,
        *,
        user_id: int,
        position: str | None,
        duties: str | None,
        selected_role_id: int | None,
        company_industry: str | None,
        telegram: str | None = None,
        progress_operation_id: str | None = None,
    ) -> tuple[UserResponse, RoleMatch | None]:
        normalization = build_profile_normalization_result(
            position=position,
            duties=duties,
            normalized_duties=None,
            company_industry=company_industry,
        )
        clean_position = normalization.cleaned_position
        operation_progress_service.advance(
            progress_operation_id,
            1,
            title="Очищаем и нормализуем данные",
            message="Нормализуем текст обязанностей и обновляем данные профиля.",
        )
        normalized_duties = normalization.normalized_duties_text
        operation_progress_service.advance(
            progress_operation_id,
            2,
            title="Сохраняем выбранную роль",
            message="Фиксируем роль, выбранную пользователем при обновлении профиля.",
        )
        selected_role_match = self._resolve_selected_role(str(selected_role_id) if selected_role_id is not None else None)
        detected_role_match = self.detect_role(position, duties, normalized_duties)
        role_match = selected_role_match or detected_role_match
        normalized_telegram = self.normalize_telegram(telegram)
        with get_connection() as connection:
            row = connection.execute(
                """
                UPDATE users
                SET job_description = %s,
                    role_id = %s,
                    telegram = COALESCE(%s, telegram),
                    company_industry = %s
                WHERE id = %s
                RETURNING id
                """,
                (
                    clean_position,
                    selected_role_match.role_id if selected_role_match else None,
                    normalized_telegram,
                    company_industry,
                    user_id,
                ),
            ).fetchone()
            operation_progress_service.advance(
                progress_operation_id,
                3,
                title="Формируем расширенный профиль",
                message="Пересобираем профиль пользователя для дальнейшей персонализации.",
            )
            self._save_user_profile(
                connection=connection,
                user_id=user_id,
                raw_position=position,
                raw_duties=duties,
                normalized_duties=normalized_duties,
                company_industry=company_industry,
                role_match=role_match,
                selected_role_match=selected_role_match,
                detected_role_match=detected_role_match,
            )
            connection.commit()
            user_response = self._load_user_by_id(connection, user_id)

        return user_response, role_match

    def start(self, login_identifier: str, user: UserResponse | None, bootstrap_user_id: int | None = None) -> AgentReply:
        session_id = uuid4().hex
        if user is not None:
            consent_version, consent_title, consent_text = self._build_personal_data_consent_prompt()
            consent_missing = user.personal_data_consent_accepted_at is None
            missing_stage = self._get_missing_profile_stage_for_existing_user(user)
            initial_stage = ConversationStage.ASK_PERSONAL_DATA_CONSENT if consent_missing else (missing_stage or ConversationStage.ASK_POSITION)
            state = ConversationState(
                session_id=session_id,
                login_identifier=login_identifier,
                mode=ConversationMode.EXISTING_USER,
                stage=initial_stage,
                user=user,
                user_id=user.id,
                full_name=user.full_name,
                position=user.raw_position or user.job_description,
                duties=user.raw_duties,
                telegram=user.telegram,
                consent_version=consent_version,
                consent_text=consent_text,
                company_industry=user.company_industry,
            )
            if initial_stage == ConversationStage.ASK_PERSONAL_DATA_CONSENT:
                reply_text = (
                    f"Пользователь найден: {user.full_name}. "
                    "Пожалуйста, ознакомьтесь с текстом согласия ниже и подтвердите выбор."
                )
            elif initial_stage == ConversationStage.ASK_ROLE:
                reply_text = (
                    f"Пользователь найден: {user.full_name}. "
                    "Чтобы продолжить работу с кейсами, " + self._build_role_selection_guidance(include_intro=False)
                )
            elif initial_stage == ConversationStage.ASK_TELEGRAM:
                reply_text = (
                    f"Пользователь найден: {user.full_name}. "
                    "Чтобы продолжить работу с кейсами, укажите ваш Telegram username, например @username. "
                    "Если Telegram нет, напишите «нет»."
                )
            elif initial_stage == ConversationStage.ASK_COMPANY_INDUSTRY:
                reply_text = (
                    f"Пользователь найден: {user.full_name}. "
                    "Чтобы продолжить работу с кейсами, укажите сферу деятельности компании, "
                    "в которой вы работаете. Например: банк, retail, телеком, производство, IT-продукт."
                )
            else:
                reply_text = (
                    f"Пользователь найден: {user.full_name}. "
                    "Нужно ли внести изменения в должность и должностные обязанности? "
                    "Если изменений нет, просто напишите, что профиль актуален или что ничего не изменилось. "
                    "Если изменения есть, отправьте сначала актуальную должность."
                )
        else:
            consent_version, consent_title, consent_text = self._build_personal_data_consent_prompt()
            state = ConversationState(
                session_id=session_id,
                login_identifier=login_identifier,
                mode=ConversationMode.NEW_USER,
                stage=ConversationStage.ASK_PERSONAL_DATA_CONSENT,
                user_id=bootstrap_user_id,
                consent_version=consent_version,
                consent_text=consent_text,
            )
            reply_text = (
                "Пользователь не найден. Давайте зарегистрируем вас. "
                "Пожалуйста, ознакомьтесь с текстом согласия ниже и подтвердите выбор."
            )

        with self._lock:
            self._sessions[session_id] = state

        state.history.append({"role": "assistant", "content": reply_text})
        self._persist_session(state)
        return AgentReply(
            session_id=session_id,
            message=reply_text,
            stage=state.stage,
            completed=False,
            consent_title=consent_title if state.stage == ConversationStage.ASK_PERSONAL_DATA_CONSENT else None,
            consent_text=state.consent_text if state.stage == ConversationStage.ASK_PERSONAL_DATA_CONSENT else None,
            action_options=self._build_personal_data_consent_actions() if state.stage == ConversationStage.ASK_PERSONAL_DATA_CONSENT else None,
            user=user,
            role_options=self._build_role_options() if state.stage == ConversationStage.ASK_ROLE else None,
        )

    def reply(self, session_id: str, message: str, progress_operation_id: str | None = None) -> AgentReply:
        text = _trimmed(message)
        if not text:
            raise ValueError("Message is required")

        with self._lock:
            state = self._sessions.get(session_id)

        if state is None:
            state = self._restore_session(session_id)
            if state is None:
                raise KeyError("Session not found")
            with self._lock:
                self._sessions[session_id] = state

        state.history.append({"role": "user", "content": text})

        if state.mode == ConversationMode.EXISTING_USER:
            reply = self._handle_existing_user(state, text, progress_operation_id=progress_operation_id)
        else:
            reply = self._handle_new_user(state, text, progress_operation_id=progress_operation_id)

        self._persist_session(state)
        return reply

    def _build_role_reply_suffix(self, role_match: RoleMatch | None) -> str:
        if role_match is None:
            return "Роль пользователя не выбрана."
        return f"Выбранная роль: {role_match.name} ({role_match.code})."

    def _get_missing_profile_stage_for_existing_user(self, user: UserResponse | None) -> ConversationStage | None:
        if user is None:
            return None
        if user.personal_data_consent_accepted_at is None:
            return ConversationStage.ASK_PERSONAL_DATA_CONSENT
        if not user.role_id:
            return ConversationStage.ASK_ROLE
        if not (user.telegram and user.telegram.strip()):
            return ConversationStage.ASK_TELEGRAM
        if not (user.company_industry and user.company_industry.strip()):
            return ConversationStage.ASK_COMPANY_INDUSTRY
        return None

    def _handle_existing_user(self, state: ConversationState, text: str, *, progress_operation_id: str | None = None) -> AgentReply:
        if state.stage == ConversationStage.COMPLETE:
            return AgentReply(
                session_id=state.session_id,
                message="Сценарий уже завершен. При необходимости начните вход заново по email.",
                stage=state.stage,
                completed=True,
            )

        if state.stage == ConversationStage.ASK_PERSONAL_DATA_CONSENT:
            if self._is_consent_accepted(text):
                if state.user_id:
                    state.user = self._record_user_personal_data_consent(state.user_id, state.consent_version, state.consent_text)
                reply_text = (
                    f"Спасибо. Согласие зафиксировано.\n\n"
                    f"Пользователь найден: {state.user.full_name if state.user else 'Пользователь'}. "
                    "Нужно ли внести изменения в должность и должностные обязанности? "
                    "Если изменений нет, просто напишите, что профиль актуален или что ничего не изменилось. "
                    "Если изменения есть, отправьте сначала актуальную должность."
                )
                state.stage = ConversationStage.ASK_POSITION
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                    user=state.user,
                )
            if self._is_consent_declined(text):
                state.stage = ConversationStage.COMPLETE
                reply_text = "Без согласия на обработку персональных данных мы не можем продолжить работу. Если захотите вернуться, начните заново с входа по email."
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=True,
                    blocked=True,
                    user=state.user,
                )
            reply_text = (
                "Пожалуйста, подтвердите согласие явно. Отметьте согласие, чтобы продолжить."
            )
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
                consent_title="Согласие на обработку персональных данных",
                consent_text=state.consent_text,
                action_options=self._build_personal_data_consent_actions(),
                user=state.user,
            )

        if state.stage == ConversationStage.ASK_POSITION and _means_no_changes(text):
            missing_stage = self._get_missing_profile_stage_for_existing_user(state.user)
            if missing_stage == ConversationStage.ASK_PERSONAL_DATA_CONSENT:
                state.stage = ConversationStage.ASK_PERSONAL_DATA_CONSENT
                _, consent_title, consent_text = self._build_personal_data_consent_prompt()
                state.consent_text = consent_text
                reply_text = (
                    "Перед продолжением нужно ознакомиться с согласием на обработку персональных данных и подтвердить выбор."
                )
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                    consent_title=consent_title,
                    consent_text=state.consent_text,
                    action_options=self._build_personal_data_consent_actions(),
                    user=state.user,
                )
            if missing_stage == ConversationStage.ASK_ROLE:
                state.stage = ConversationStage.ASK_ROLE
                reply_text = (
                    "Понял, изменения в должности и обязанностях не требуются. "
                    "Чтобы продолжить работу с кейсами, " + self._build_role_selection_guidance(include_intro=False)
                )
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                    user=state.user,
                    role_options=self._build_role_options(),
                )
            if missing_stage == ConversationStage.ASK_TELEGRAM:
                state.stage = ConversationStage.ASK_TELEGRAM
                reply_text = (
                    "Понял, изменения в должности и обязанностях не требуются. "
                    "Осталось указать ваш Telegram. Напишите username, например @username. "
                    "Если Telegram нет, напишите «нет»."
                )
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                    user=state.user,
                )
            if missing_stage == ConversationStage.ASK_COMPANY_INDUSTRY:
                state.stage = ConversationStage.ASK_COMPANY_INDUSTRY
                reply_text = (
                    "Понял, изменения в должности и обязанностях не требуются. "
                    "Осталось указать сферу деятельности компании, чтобы корректно подготовить дальнейший сценарий."
                )
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                    user=state.user,
                )

            state.stage = ConversationStage.COMPLETE
            operation_progress_service.advance(
                progress_operation_id,
                4,
                title="Подготавливаем следующий экран",
                message="Профиль актуален. Завершаем сценарий и открываем следующий экран.",
            )
            reply_text = "Спасибо за информацию. Повторно заполнять профиль не требуется."
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=True,
                user=state.user,
            )

        if state.stage == ConversationStage.ASK_POSITION:
            state.position = text
            state.stage = ConversationStage.ASK_DUTIES
            reply_text = "Спасибо. Теперь напишите ваши должностные обязанности в свободной форме."
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
            )

        if state.stage == ConversationStage.ASK_DUTIES:
            state.duties = text
            state.stage = ConversationStage.ASK_ROLE
            reply_text = "Спасибо. Теперь выберите вашу роль в системе.\n\n" + self._build_role_selection_guidance(include_intro=False)
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
                role_options=self._build_role_options(),
            )

        if state.stage == ConversationStage.ASK_ROLE:
            role_match = self._resolve_selected_role(text)
            if role_match is None:
                reply_text = "Не удалось распознать роль. Пожалуйста, выберите один вариант из списка."
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                    role_options=self._build_role_options(),
                )
            state.selected_role_id = role_match.role_id
            existing_telegram = self.normalize_telegram(state.telegram or (state.user.telegram if state.user else None))
            if not existing_telegram:
                state.stage = ConversationStage.ASK_TELEGRAM
                reply_text = (
                    "Спасибо. Теперь укажите ваш Telegram username, например @username. "
                    "Если Telegram нет, напишите «нет»."
                )
            else:
                state.stage = ConversationStage.ASK_COMPANY_INDUSTRY
                reply_text = (
                    "Спасибо. Теперь укажите сферу деятельности компании, в которой вы работаете. "
                    "Например: банк, retail, телеком, производство, IT-продукт."
                )
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
            )

        if state.stage == ConversationStage.ASK_TELEGRAM:
            state.telegram = self.normalize_telegram(text)
            state.stage = ConversationStage.ASK_COMPANY_INDUSTRY
            reply_text = (
                "Спасибо. Теперь укажите сферу деятельности компании, в которой вы работаете. "
                "Например: банк, retail, телеком, производство, IT-продукт."
            )
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
            )

        state.company_industry = text
        user, role_match = self.update_user(
            user_id=state.user_id or 0,
            position=state.position,
            duties=state.duties,
            selected_role_id=state.selected_role_id,
            telegram=state.telegram,
            company_industry=state.company_industry,
            progress_operation_id=progress_operation_id,
        )
        state.user = user
        state.stage = ConversationStage.COMPLETE
        operation_progress_service.advance(
            progress_operation_id,
            4,
            title="Подготавливаем следующий экран",
            message="Профиль обновлен. Завершаем сценарий и открываем следующий экран.",
        )
        reply_text = "Готово. Я обновил данные пользователя в базе. " + self._build_role_reply_suffix(role_match)
        if user.normalized_duties:
            reply_text += " Нормализованный список обязанностей также сохранен в профиле."
        state.history.append({"role": "assistant", "content": reply_text})
        return AgentReply(
            session_id=state.session_id,
            message=reply_text,
            stage=state.stage,
            completed=True,
            user=user,
            detected_role_id=role_match.role_id if role_match else None,
            detected_role_code=role_match.code if role_match else None,
            detected_role_name=role_match.name if role_match else None,
            detected_role_confidence=role_match.confidence if role_match else None,
            detected_role_rationale=role_match.rationale if role_match else None,
        )

    def _handle_new_user(self, state: ConversationState, text: str, *, progress_operation_id: str | None = None) -> AgentReply:
        if state.stage == ConversationStage.COMPLETE:
            return AgentReply(
                session_id=state.session_id,
                message="Сценарий уже завершен. При необходимости начните вход заново по email.",
                stage=state.stage,
                completed=True,
            )

        if state.stage == ConversationStage.ASK_PERSONAL_DATA_CONSENT:
            if self._is_consent_accepted(text):
                state.stage = ConversationStage.ASK_FULL_NAME
                reply_text = "Спасибо. Согласие на обработку персональных данных зафиксировано. Теперь напишите, пожалуйста, ФИО полностью."
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                )
            if self._is_consent_declined(text):
                state.stage = ConversationStage.COMPLETE
                reply_text = "Без согласия на обработку персональных данных мы не можем продолжить регистрацию. Если захотите вернуться, начните заново с входа по email."
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=True,
                    blocked=True,
                )
            reply_text = (
                "Пожалуйста, подтвердите согласие явно. Отметьте согласие, чтобы продолжить регистрацию."
            )
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
                consent_title="Согласие на обработку персональных данных",
                consent_text=state.consent_text,
                action_options=self._build_personal_data_consent_actions(),
            )

        if state.stage == ConversationStage.ASK_FULL_NAME:
            state.full_name = text
            state.stage = ConversationStage.ASK_TELEGRAM
            reply_text = "Спасибо. Теперь укажите ваш Telegram username, например @username. Если Telegram нет, напишите «нет»."
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
            )

        if state.stage == ConversationStage.ASK_TELEGRAM:
            state.telegram = self.normalize_telegram(text)
            state.stage = ConversationStage.ASK_POSITION
            reply_text = "Спасибо. Укажите вашу должность."
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
            )

        if state.stage == ConversationStage.ASK_POSITION:
            state.position = text
            state.stage = ConversationStage.ASK_DUTIES
            reply_text = "Отлично. Теперь опишите ваши должностные обязанности."
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
            )

        if state.stage == ConversationStage.ASK_DUTIES:
            state.duties = text
            state.stage = ConversationStage.ASK_ROLE
            reply_text = "Отлично. Теперь выберите вашу роль в системе.\n\n" + self._build_role_selection_guidance(include_intro=False)
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
                role_options=self._build_role_options(),
            )

        if state.stage == ConversationStage.ASK_ROLE:
            role_match = self._resolve_selected_role(text)
            if role_match is None:
                reply_text = "Не удалось распознать роль. Пожалуйста, выберите один вариант из списка."
                state.history.append({"role": "assistant", "content": reply_text})
                return AgentReply(
                    session_id=state.session_id,
                    message=reply_text,
                    stage=state.stage,
                    completed=False,
                    role_options=self._build_role_options(),
                )
            state.selected_role_id = role_match.role_id
            state.stage = ConversationStage.ASK_COMPANY_INDUSTRY
            reply_text = (
                "Отлично. Теперь укажите сферу деятельности компании, в которой вы работаете. "
                "Например: банк, retail, телеком, производство, IT-продукт."
            )
            state.history.append({"role": "assistant", "content": reply_text})
            return AgentReply(
                session_id=state.session_id,
                message=reply_text,
                stage=state.stage,
                completed=False,
            )

        state.company_industry = text
        user, role_match = self.create_user(
            full_name=state.full_name or "",
            email=state.login_identifier,
            telegram=state.telegram,
            consent_version=state.consent_version,
            consent_text=state.consent_text,
            position=state.position,
            duties=state.duties,
            selected_role_id=state.selected_role_id,
            company_industry=state.company_industry,
            existing_user_id=state.user_id,
            progress_operation_id=progress_operation_id,
        )
        state.user = user
        state.stage = ConversationStage.COMPLETE
        operation_progress_service.advance(
            progress_operation_id,
            4,
            title="Подготавливаем следующий экран",
            message="Пользователь создан. Завершаем регистрацию и открываем следующий экран.",
        )
        reply_text = "Готово. Новый пользователь создан и сохранен в базе данных. " + self._build_role_reply_suffix(role_match)
        if user.normalized_duties:
            reply_text += " Нормализованный список обязанностей также сохранен в профиле."
        state.history.append({"role": "assistant", "content": reply_text})
        return AgentReply(
            session_id=state.session_id,
            message=reply_text,
            stage=state.stage,
            completed=True,
            user=user,
            detected_role_id=role_match.role_id if role_match else None,
            detected_role_code=role_match.code if role_match else None,
            detected_role_name=role_match.name if role_match else None,
            detected_role_confidence=role_match.confidence if role_match else None,
            detected_role_rationale=role_match.rationale if role_match else None,
        )

    def start_case_interview(self, *, user: UserResponse, progress_operation_id: str | None = None) -> AssessmentStartResponse:
        if not _is_assessment_allowed_for_user(user):
            raise ValueError("Для роли «Администратор» ассессмент недоступен.")
        plan = assessment_service.ensure_assessment_session(user, progress_operation_id=progress_operation_id)
        if plan is None:
            raise ValueError("Не удалось подготовить assessment-сессию для пользователя.")

        reply = assessment_service.open_assessment_dialogue(plan.session_code)
        return AssessmentStartResponse(
            session_code=reply.session_code,
            session_id=reply.session_id,
            session_case_id=reply.session_case_id,
            case_title=reply.case_title,
            case_number=reply.case_number,
            total_cases=reply.total_cases,
            message=reply.message,
            assessment_completed=reply.assessment_completed,
            case_completed=reply.case_completed,
            case_time_limit_minutes=reply.case_time_limit_minutes,
            planned_case_duration_minutes=reply.planned_case_duration_minutes,
            case_started_at=reply.case_started_at,
            case_time_remaining_seconds=reply.case_time_remaining_seconds,
            time_expired=reply.time_expired,
            history_match_case=reply.history_match_case,
            history_match_case_text=reply.history_match_case_text,
            history_match_type=reply.history_match_type,
            history_last_used_at=reply.history_last_used_at,
            history_use_count=reply.history_use_count,
            history_flag=reply.history_flag,
            history_is_new=reply.history_is_new,
            is_dialog_case=reply.is_dialog_case,
            pending_auto_finish=reply.pending_auto_finish,
            auto_finish_delay_ms=reply.auto_finish_delay_ms,
            mbti_case_result=reply.mbti_case_result,
            mbti_followup_questions=reply.mbti_followup_questions,
            mbti_followup_pending=reply.mbti_followup_pending,
            mbti_followup_index=reply.mbti_followup_index,
            mbti_followup_total=reply.mbti_followup_total,
            mbti_summary=reply.mbti_summary,
        )

    def continue_case_interview(
        self,
        *,
        session_code: str,
        message: str,
        progress_operation_id: str | None = None,
    ) -> AssessmentMessageResponse:
        reply = assessment_service.process_case_message(
            session_code=session_code,
            message=message,
            progress_operation_id=progress_operation_id,
        )
        return AssessmentMessageResponse(
            session_code=reply.session_code,
            session_id=reply.session_id,
            session_case_id=reply.session_case_id,
            case_title=reply.case_title,
            case_number=reply.case_number,
            total_cases=reply.total_cases,
            message=reply.message,
            case_completed=reply.case_completed,
            assessment_completed=reply.assessment_completed,
            result_status=reply.result_status,
            completion_score=reply.completion_score,
            evaluator_summary=reply.evaluator_summary,
            case_time_limit_minutes=reply.case_time_limit_minutes,
            planned_case_duration_minutes=reply.planned_case_duration_minutes,
            case_started_at=reply.case_started_at,
            case_time_remaining_seconds=reply.case_time_remaining_seconds,
            time_expired=reply.time_expired,
            history_match_case=reply.history_match_case,
            history_match_case_text=reply.history_match_case_text,
            history_match_type=reply.history_match_type,
            history_last_used_at=reply.history_last_used_at,
            history_use_count=reply.history_use_count,
            history_flag=reply.history_flag,
            history_is_new=reply.history_is_new,
            is_dialog_case=reply.is_dialog_case,
            pending_auto_finish=reply.pending_auto_finish,
            auto_finish_delay_ms=reply.auto_finish_delay_ms,
            mbti_case_result=reply.mbti_case_result,
            mbti_followup_questions=reply.mbti_followup_questions,
            mbti_followup_pending=reply.mbti_followup_pending,
            mbti_followup_index=reply.mbti_followup_index,
            mbti_followup_total=reply.mbti_followup_total,
            mbti_summary=reply.mbti_summary,
        )


interviewer_agent = InterviewerAgent()
