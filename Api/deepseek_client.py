from __future__ import annotations

import ast
import json
import logging
import re
import zlib
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from Api.case_context_builder import build_case_context
from Api.case_text_cleanup import cleanup_case_list, cleanup_case_text, join_case_list
from Api.config import settings
from Api.database import get_active_interviewer_prompt, get_connection
from Api.assessment.case_generation import CaseGenerationMixin
from Api.assessment.interview import DialogContextBuilder, DialogFallbackEngine, DialogPolicy, DialogStateMachine, InterviewerPromptBuilder, InterviewerService, InterviewerTurnResult
from Api.llm.deepseek_gateway import DeepSeekGateway
from Api.assessment_prompt_resolver import prompt_resolver

logger = logging.getLogger("agent4k.deepseek")

FORBIDDEN_EXTERNAL_RESOURCE_PATTERNS = (
    r"https?://\S+",
    r"www\.\S+",
    r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b",
    r"\btelegram\b",
    r"\bwhatsapp\b",
    r"\bslack\b",
    r"\bdiscord\b",
    r"\bgoogle\s*(docs|drive|forms|sheet|sheets)\b",
    r"\bdropbox\b",
    r"\bone\s*drive\b",
    r"\bfigma\b",
    r"\bnotion\b",
    r"\bmiro\b",
    r"\bcrm\b",
    r"\bпочт[ауеы]\b",
    r"\bemail\b",
    r"\bтелеграм\b",
    r"\bватсап\b",
    r"\bсайт\b",
    r"\bоблако\b",
    r"\bмессенджер\b",
)

FORBIDDEN_EXTERNAL_ACTION_PATTERN = (
    r"(отправ(?:ь|ьте|ить|ляй|ляем|лено)|"
    r"перешл(?:и|ите|ать|яй)|"
    r"загруз(?:и|ите|ить|ка)|"
    r"размест(?:и|ите|ить)|"
    r"опублику(?:й|йте|й|ать)|"
    r"переда(?:й|йте|ть)|"
    r"подел(?:ись|итесь|ить)|"
    r"скин(?:ь|ьте|уть)|"
    r"заполн(?:и|ите|ить)|"
    r"внес(?:и|ите|ти))"
)

CASE_PROMPT_FORBIDDEN_PATTERNS = (
    r"\bдля\s+L\b",
    r"\bдля\s+M\b",
    r"\bL/M\b",
    r"\bplanned_total_duration_min\b",
    r"\{[^{}]+\}",
    r"\bв процессе обработка\b",
    r"\bпо вопросу сбой\b",
    r"\bпо вопросу отсутствие\b",
    r"\bкарточка тикета\b",
    r"\bкарточка запроса\b",
    r"\bпродвинуть завершить\b",
    r"\bтем человеком, кому нужно первым ответить\b",
)

CASE_TEXT_GENERIC_PATTERNS = (
    r"\bоперационн(?:ая|ый|ое)\s+команд",
    r"\bключев(?:ой|ая|ое)\s+рабоч(?:ий|ая|ее)\s+процесс",
    r"\bрабоч(?:ая|ий|ее)\s+систем",
    r"\bрабоч(?:ий|ая|ее)\s+объект",
    r"\bтипов(?:ой|ая|ое)\s+участник",
    r"\bтипов(?:ой|ая|ое)\s+процесс",
    r"\bтипов(?:ой|ая|ое)\s+артефакт",
    r"\bтекущая\s+операционная\s+работа\s+команд",
    r"\bпервом\s+источнике\s+данных\s+и\s+в\s+втором\s+источнике",
)

DeepSeekTurnResult = InterviewerTurnResult


@dataclass(slots=True)
class DeepSeekRoleDecision:
    role_code: str
    confidence: float
    rationale: str


class DeepSeekClient(CaseGenerationMixin):
    def __init__(self) -> None:
        self.gateway = DeepSeekGateway()
        self.dialog_policy = DialogPolicy()
        self.dialog_state_machine = DialogStateMachine()
        self.dialog_fallback_engine = DialogFallbackEngine(state_machine=self.dialog_state_machine)
        self.dialog_context_builder = DialogContextBuilder(state_machine=self.dialog_state_machine)
        self.interviewer_service = InterviewerService(
            gateway=self.gateway,
            dialog_policy=self.dialog_policy,
            context_builder=self.dialog_context_builder,
        )
        self.interviewer_prompt_builder = InterviewerPromptBuilder(
            dialog_policy=self.dialog_policy,
            context_builder=self.dialog_context_builder,
        )
        self._user_text_template_cache: dict[str, dict[str, Any]] = {}
        self._case_text_build_instruction_cache: dict[str, dict[str, Any] | None] = {}
        self._domain_catalog_cache: dict[str, dict[str, Any]] = {}
        self._company_industry_cache: dict[tuple[str, str, str], str] = {}
        self._case_specificity_cache: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}

    @property
    def api_keys(self) -> list[str]:
        return self.gateway.api_keys

    @api_keys.setter
    def api_keys(self, value: list[str]) -> None:
        self.gateway.api_keys = list(value)

    @property
    def api_key(self) -> str:
        return self.api_keys[0] if self.api_keys else ""

    @property
    def base_url(self) -> str:
        return self.gateway.base_url

    @property
    def model(self) -> str:
        return self.gateway.model

    @property
    def _request_slots(self):
        return self.gateway.request_slots

    @_request_slots.setter
    def _request_slots(self, value) -> None:
        self.gateway.request_slots = value

    @property
    def enabled(self) -> bool:
        return bool(self.api_keys)

    def _build_deepseek_routing_key(self, routing_key: str | None, messages: list[dict[str, str]]) -> str:
        return self.gateway.build_routing_key(routing_key, messages)

    def _get_deepseek_key_chain(self, routing_key: str | None, messages: list[dict[str, str]]) -> list[str]:
        return self.gateway.get_key_chain(routing_key, messages)

    def _get_interviewer_prompt_text(
        self,
        prompt_code: str,
        fallback_text: str,
        *,
        prompt_snapshot: dict[str, Any] | None = None,
        **format_values: str,
    ) -> str:
        if isinstance((prompt_snapshot or {}).get("prompts"), dict):
            return prompt_resolver.interviewer_prompt(
                prompt_snapshot,
                prompt_code=prompt_code,
                fallback_text=fallback_text,
                format_values=format_values,
            )
        stored_text: str | None = None
        try:
            with get_connection() as connection:
                stored_text = get_active_interviewer_prompt(connection, prompt_code)
        except Exception:
            stored_text = None
        prompt_text = str(stored_text or fallback_text or "").strip()
        if format_values:
            try:
                prompt_text = prompt_text.format(**format_values)
            except Exception:
                fallback_prepared = str(fallback_text or "").strip()
                if fallback_prepared:
                    try:
                        prompt_text = fallback_prepared.format(**format_values)
                    except Exception:
                        prompt_text = fallback_prepared
        return prompt_text

    def generate_domain_profile(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None = None,
    ) -> dict[str, Any]:
        fallback = self._fallback_domain_profile(
            position=position,
            duties=duties,
            company_industry=company_industry,
            role_name=role_name,
        )
        fallback = self._bind_domain_catalog_entry(
            fallback,
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        detected_family = self._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        if detected_family == "generic":
            return fallback
        if not self.enabled:
            return fallback

        prompt = (
            "Сформируй нормализованный профессиональный домен пользователя по его данным профиля. "
            "Верни только JSON без пояснений.\n"
            "Поля JSON:\n"
            "- domain_label: понятное название профессионального домена;\n"
            "- processes: массив из 3-5 типовых процессов;\n"
            "- tasks: массив из 4-6 типовых рабочих задач;\n"
            "- stakeholders: массив из 3-5 типовых участников взаимодействия;\n"
            "- systems: массив из 2-4 типовых систем, журналов или артефактов;\n"
            "- artifacts: массив из 2-4 типовых рабочих объектов/документов;\n"
            "- risks: массив из 2-4 типовых рисков;\n"
            "- constraints: массив из 2-4 типовых ограничений.\n\n"
            "Правила:\n"
            "1. Опирайся только на сферу компании, должность, обязанности и роль пользователя.\n"
            "2. Не уводи домен в другую отрасль.\n"
            "3. Не используй универсальные ИТ-примеры, если профиль явно не ИТ.\n"
            "4. Конкретика должна быть реалистичной для профессиональной среды пользователя.\n"
            "5. Если сфера узкая, выбирай наиболее вероятный реальный рабочий контур этой сферы.\n\n"
            f"Сфера компании: {company_industry or 'не указана'}\n"
            f"Должность: {position or 'не указана'}\n"
            f"Обязанности: {duties or 'не указаны'}\n"
            f"Роль: {role_name or 'не указана'}\n"
            f"Fallback-профиль: {json.dumps(fallback, ensure_ascii=False, default=str)}"
        )
        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Ты нормализуешь профессиональный домен пользователя и подбираешь отраслевую конкретику без смены сферы деятельности.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            parsed = self._parse_json(raw)
            if not isinstance(parsed, dict):
                return fallback
            normalized = self._normalize_domain_profile_with_profile(
                parsed,
                fallback,
                position=position,
                duties=duties,
                company_industry=company_industry,
            )
            return self._bind_domain_catalog_entry(
                normalized,
                position=position,
                duties=duties,
                company_industry=company_industry,
            )
        except Exception:
            return fallback

    def _get_domain_catalog_entry(self, family_name: str | None) -> dict[str, Any] | None:
        family = str(family_name or "").strip().lower()
        if not family:
            return None
        if family in self._domain_catalog_cache:
            return dict(self._domain_catalog_cache[family])
        try:
            with psycopg.connect(
                host=settings.db_host,
                port=settings.db_port,
                dbname=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                row_factory=dict_row,
            ) as connection:
                row = connection.execute(
                    """
                    SELECT domain_code, family_name, display_name, description,
                           example_industries, typical_keywords,
                           template_processes, template_tasks, template_stakeholders,
                           template_risks, template_constraints, template_systems, template_artifacts,
                           is_active, version
                    FROM domain_catalog
                    WHERE family_name = %s
                      AND is_active = TRUE
                    LIMIT 1
                    """,
                    (family,),
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return None
        entry = dict(row)
        self._domain_catalog_cache[family] = entry
        return dict(entry)

    def _bind_domain_catalog_entry(
        self,
        profile: dict[str, Any],
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> dict[str, Any]:
        result = dict(profile or {})
        family = self._detect_domain_family(position=position, duties=duties, company_industry=company_industry)
        entry = self._get_domain_catalog_entry(family)
        candidate_id: int | None = None
        needs_candidate = family == "generic" or entry is None
        if needs_candidate:
            candidate_id = self._upsert_domain_catalog_candidate(
                raw_company_industry=company_industry,
                raw_position=position,
                raw_duties=duties,
                suggested_profile=result,
                suggested_family=family,
                resolved_domain_code=(entry.get("domain_code") if entry else None),
            )
        if not entry:
            result["domain_family"] = family
            result.setdefault("domain_code", family)
            result["domain_resolution_status"] = "candidate_pending" if candidate_id else "unresolved"
            if candidate_id:
                result["domain_candidate_id"] = candidate_id
            return result
        result = self._merge_domain_catalog_template(result, entry)
        result["domain_family"] = family
        result["domain_code"] = entry.get("domain_code") or family
        result["domain_catalog_entry"] = entry
        result.setdefault("domain_display_name", entry.get("display_name"))
        result["domain_resolution_status"] = "catalog_match" if not candidate_id else "candidate_pending"
        if candidate_id:
            result["domain_candidate_id"] = candidate_id
        return result

    def _merge_domain_catalog_template(
        self,
        profile: dict[str, Any],
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(profile or {})
        if not result.get("domain_label") and entry.get("display_name"):
            result["domain_label"] = entry["display_name"]
        template_map = {
            "processes": entry.get("template_processes"),
            "tasks": entry.get("template_tasks"),
            "stakeholders": entry.get("template_stakeholders"),
            "risks": entry.get("template_risks"),
            "constraints": entry.get("template_constraints"),
            "systems": entry.get("template_systems"),
            "artifacts": entry.get("template_artifacts"),
        }
        for field_name, template_value in template_map.items():
            normalized_template = self._normalize_string_list(template_value, fallback=[])
            current_value = self._normalize_string_list(result.get(field_name), fallback=[])
            if not current_value:
                result[field_name] = normalized_template
                continue
            merged: list[str] = []
            seen: set[str] = set()
            for item in current_value + normalized_template:
                cleaned = self._sanitize_personalization_value(str(item or ""))
                key = cleaned.lower()
                if not cleaned or key in seen:
                    continue
                seen.add(key)
                merged.append(cleaned)
            result[field_name] = merged
        return result

    def _upsert_domain_catalog_candidate(
        self,
        *,
        raw_company_industry: str | None,
        raw_position: str | None,
        raw_duties: str | None,
        suggested_profile: dict[str, Any],
        suggested_family: str,
        resolved_domain_code: str | None,
    ) -> int | None:
        try:
            with psycopg.connect(
                host=settings.db_host,
                port=settings.db_port,
                dbname=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                row_factory=dict_row,
            ) as connection:
                existing = connection.execute(
                    """
                    SELECT id
                    FROM domain_catalog_candidates
                    WHERE COALESCE(raw_company_industry, '') = COALESCE(%s, '')
                      AND COALESCE(raw_position, '') = COALESCE(%s, '')
                      AND COALESCE(raw_duties, '') = COALESCE(%s, '')
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (raw_company_industry, raw_position, raw_duties),
                ).fetchone()
                payload = json.dumps(suggested_profile, ensure_ascii=False, default=str)
                if existing is not None:
                    connection.execute(
                        """
                        UPDATE domain_catalog_candidates
                        SET
                            suggested_domain_label = %s,
                            suggested_family = %s,
                            resolved_domain_code = %s,
                            suggested_profile_json = %s::jsonb,
                            last_seen_at = NOW(),
                            seen_count = seen_count + 1,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            suggested_profile.get("domain_label") or suggested_family,
                            suggested_family,
                            resolved_domain_code,
                            payload,
                            existing["id"],
                        ),
                    )
                    return int(existing["id"])
                row = connection.execute(
                    """
                    INSERT INTO domain_catalog_candidates (
                        raw_company_industry,
                        raw_position,
                        raw_duties,
                        suggested_domain_label,
                        suggested_family,
                        resolved_domain_code,
                        suggested_profile_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        raw_company_industry,
                        raw_position,
                        raw_duties,
                        suggested_profile.get("domain_label") or suggested_family,
                        suggested_family,
                        resolved_domain_code,
                        payload,
                    ),
                ).fetchone()
                return int(row["id"]) if row else None
        except Exception:
            return None

    def _post_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        timeout_sec: int = 120,
        routing_key: str | None = None,
    ) -> str:
        return self.gateway.chat(
            messages,
            temperature=temperature,
            timeout_seconds=timeout_sec,
            routing_key=routing_key,
        )


    def finalize_case_prompt_text(
        self,
        text: str,
        *,
        role_name: str | None,
        planned_total_duration_min: int | None = None,
    ) -> str:
        sanitized = self._sanitize_case_prompt_text(
            text,
            role_name=role_name,
            planned_total_duration_min=planned_total_duration_min,
        )
        proofread = self._proofread_case_prompt_text(sanitized)
        return self._validate_case_prompt_result(proofread, fallback=sanitized)




    def normalize_duties(
        self,
        *,
        position: str | None,
        duties: str | None,
    ) -> list[str] | None:
        if not self.enabled or not duties:
            return None

        prompt = (
            "Нормализуй список должностных обязанностей сотрудника. "
            "Верни только JSON c полем normalized_duties, где будет массив строк. "
            "Нужно:\n"
            "1. убрать лишние формулировки, вводные слова и повторы;\n"
            "2. выделить самостоятельные смысловые единицы;\n"
            "3. разделить обязанности на отдельные действия и зоны ответственности;\n"
            "4. не добавлять новых обязанностей от себя;\n"
            "5. формулировать каждую обязанность коротко и предметно.\n\n"
            f"Должность: {position or 'Не указана'}\n"
            f"Исходный текст обязанностей: {duties}"
        )
        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Ты структурируешь должностные обязанности сотрудников в краткий и чистый список действий и зон ответственности.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            parsed = self._parse_json(raw)
            items = parsed.get("normalized_duties")
            if not isinstance(items, list):
                return None
            result = [str(item).strip(" -\n\t") for item in items if str(item).strip(" -\n\t")]
            return result or None
        except Exception:
            return None



    def determine_role(
        self,
        *,
        position: str | None,
        duties: str | None,
        normalized_duties: str | None,
        roles: list[dict[str, Any]],
    ) -> DeepSeekRoleDecision | None:
        if not self.enabled:
            return None

        roles_text = []
        for role in roles:
            roles_text.append(
                {
                    "code": role["code"],
                    "name": role["name"],
                    "short_definition": role.get("short_definition"),
                    "mission": role.get("mission"),
                    "typical_tasks": role.get("typical_tasks"),
                    "planning_horizon": role.get("planning_horizon"),
                    "impact_scale": role.get("impact_scale"),
                    "authority_allowed": role.get("authority_allowed"),
                    "role_limits": role.get("role_limits"),
                    "escalation_rules": role.get("escalation_rules"),
                    "role_vocabulary": role.get("personalization_variables"),
                }
            )

        prompt = (
            "Определи, к какой роли относится пользователь. "
            "Верни только JSON с полями role_code, confidence и rationale. "
            "role_code должен быть одним из предложенных кодов.\n\n"
            "Логика выбора:\n"
            "- если преобладает выполнение конкретных задач по правилам, инструкциям, SLA, с уточнением и эскалацией, это linear_employee;\n"
            "- если преобладает организация работы, координация, приоритеты, сроки, распределение задач и управление зависимостями, это manager;\n"
            "- если преобладает стратегия, изменения, системные решения, крупные риски и несколько групп стейкхолдеров, это leader.\n\n"
            f"Исходная должность: {position or 'Не указана'}\n"
            f"Исходные обязанности: {duties or 'Не указаны'}\n"
            f"Нормализованные обязанности: {normalized_duties or 'Не указаны'}\n"
            f"Доступные роли: {json.dumps(roles_text, ensure_ascii=False, default=str)}"
        )

        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Ты классифицируешь сотрудников по корпоративным ролям на основе масштаба ответственности, горизонта решений, полномочий, ограничений и характера задач.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            parsed = self._parse_json(raw)
            role_code = parsed.get("role_code")
            confidence = parsed.get("confidence")
            rationale = parsed.get("rationale")
            if isinstance(role_code, str):
                try:
                    confidence_value = float(confidence)
                except (TypeError, ValueError):
                    confidence_value = 0.8
                confidence_value = max(0.0, min(1.0, confidence_value))
                return DeepSeekRoleDecision(
                    role_code=role_code.strip(),
                    confidence=confidence_value,
                    rationale=str(rationale or "").strip(),
                )
        except Exception:
            return None
        return None

    def validate_profile_context_lists(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        selected_role_name: str | None,
        selected_role_code: str | None,
        instruction_text: str | None,
        user_domain: str | None,
        domain_profile: dict[str, Any] | None,
        user_processes: list[str] | None,
        user_tasks: list[str] | None,
        user_stakeholders: list[str] | None,
        user_constraints: list[str] | None = None,
        user_artifacts: list[str] | None = None,
        user_systems: list[str] | None = None,
        user_success_metrics: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        payload = {
            "position": str(position or "").strip(),
            "duties": str(duties or "").strip(),
            "company_industry": str(company_industry or "").strip(),
            "role_name": str(role_name or "").strip(),
            "selected_role_name": str(selected_role_name or "").strip(),
            "selected_role_code": str(selected_role_code or "").strip(),
            "user_domain": str(user_domain or "").strip(),
            "domain_profile": dict(domain_profile or {}),
            "user_processes": [str(item).strip() for item in (user_processes or []) if str(item).strip()],
            "user_tasks": [str(item).strip() for item in (user_tasks or []) if str(item).strip()],
            "user_stakeholders": [str(item).strip() for item in (user_stakeholders or []) if str(item).strip()],
            "user_constraints": [str(item).strip() for item in (user_constraints or []) if str(item).strip()],
            "user_artifacts": [str(item).strip() for item in (user_artifacts or []) if str(item).strip()],
            "user_systems": [str(item).strip() for item in (user_systems or []) if str(item).strip()],
            "user_success_metrics": [str(item).strip() for item in (user_success_metrics or []) if str(item).strip()],
        }
        prompt = (
            f"{str(instruction_text or '').strip()}\n\n"
            "Ниже уже собранные списки персонализированного профиля. "
            "Твоя задача не строить профиль заново, а только проверить и очистить три списка: user_processes, user_tasks, user_stakeholders. "
            "Главный источник масштаба роли и допустимого управленческого контура — выбранная пользователем роль. "
            "Если выбранная роль указана, опирайся на нее как на основной источник интерпретации. "
            "Удали элементы, которые относятся к чужому домену, чужой функции, чужому подразделению или не имеют надежной опоры во входных данных пользователя. "
            "Ничего не добавляй от себя без явного основания. Сохраняй только реалистичные элементы, подтвержденные должностью, обязанностями, выбранной ролью и функциональным доменом пользователя. "
            "Верни только JSON с полями user_processes, user_tasks, user_stakeholders, warnings.\n\n"
            f"Данные профиля:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Проверь списки персонализированного профиля и верни только JSON без пояснений.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.12,
            )
            parsed = self._parse_json(raw)
            if not isinstance(parsed, dict):
                return None
            def _clean_list(value: Any) -> list[str]:
                if not isinstance(value, list):
                    return []
                return [self._sanitize_personalization_value(str(item)) for item in value if self._sanitize_personalization_value(str(item))]
            return {
                "user_processes": _clean_list(parsed.get("user_processes")),
                "user_tasks": _clean_list(parsed.get("user_tasks")),
                "user_stakeholders": _clean_list(parsed.get("user_stakeholders")),
                "warnings": _clean_list(parsed.get("warnings")),
            }
        except Exception:
            return None

    def generate_profile_context_lists(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        selected_role_name: str | None,
        selected_role_code: str | None,
        instruction_text: str | None,
        user_domain: str | None,
        domain_profile: dict[str, Any] | None,
        user_constraints: list[str] | None = None,
        user_artifacts: list[str] | None = None,
        user_systems: list[str] | None = None,
        user_success_metrics: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        payload = {
            "position": str(position or "").strip(),
            "duties": str(duties or "").strip(),
            "company_industry": str(company_industry or "").strip(),
            "role_name": str(role_name or "").strip(),
            "selected_role_name": str(selected_role_name or "").strip(),
            "selected_role_code": str(selected_role_code or "").strip(),
            "user_domain": str(user_domain or "").strip(),
            "domain_profile": dict(domain_profile or {}),
            "user_constraints": [str(item).strip() for item in (user_constraints or []) if str(item).strip()],
            "user_artifacts": [str(item).strip() for item in (user_artifacts or []) if str(item).strip()],
            "user_systems": [str(item).strip() for item in (user_systems or []) if str(item).strip()],
            "user_success_metrics": [str(item).strip() for item in (user_success_metrics or []) if str(item).strip()],
        }
        prompt = (
            f"{str(instruction_text or '').strip()}\n\n"
            "Ниже входные данные для построения персонализированного профиля пользователя. "
            "Сформируй только три списка: user_processes, user_tasks, user_stakeholders. "
            "Выбранная пользователем роль — главный источник масштаба и уровня ответственности. "
            "Опирайся на должность, обязанности, выбранную роль, домен и подтвержденный функциональный контекст. "
            "Учитывай системы, рабочие артефакты, ограничения и метрики как сигналы реального контура работы пользователя. "
            "Если входных данных мало, аккуратно дострой недостающие процессы, задачи и стейкхолдеров на основе выбранной роли, должности, домена, систем, артефактов и ограничений. "
            "Такая достройка допустима только внутри реалистичного рабочего контура пользователя и не должна уводить в чужую функцию или чужой уровень ответственности. "
            "Не добавляй чужие процессы, чужие задачи и чужих стейкхолдеров без явного основания. "
            "Для user_tasks не копируй одну длинную сырую фразу из обязанностей целиком. "
            "Разложи обязанности на 4-8 отдельных, коротких и нормальных рабочих задач в форме действий. "
            "Каждая задача должна быть самостоятельной, конкретной и без повторения всей исходной формулировки целиком. "
            "Процессы и задачи должны звучать как реальные рабочие действия и участки работы, а не как абстрактные корпоративные формулы. "
            "Верни только JSON с полями user_processes, user_tasks, user_stakeholders.\n\n"
            f"Входные данные:\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}"
        )
        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Сформируй списки персонализированного профиля и верни только JSON без пояснений.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.12,
            )
            parsed = self._parse_json(raw)
            if not isinstance(parsed, dict):
                return None

            def _clean_list(value: Any) -> list[str]:
                if not isinstance(value, list):
                    return []
                return [self._sanitize_personalization_value(str(item)) for item in value if self._sanitize_personalization_value(str(item))]

            return {
                "user_processes": _clean_list(parsed.get("user_processes")),
                "user_tasks": _clean_list(parsed.get("user_tasks")),
                "user_stakeholders": _clean_list(parsed.get("user_stakeholders")),
            }
        except Exception:
            return None











    def evaluate_case_turn(
        self,
        *,
        system_prompt: str,
        dialogue: list[dict[str, str]],
        case_title: str,
        case_skills: list[str],
        user_identifier: str | None = None,
        interactivity_mode: str | None = None,
        format_control_rules: str | None = None,
        recommended_answer_length: str | None = None,
        interviewer_prompt_override: str | None = None,
        fallback_user_message: str,
        role_name: str | None = None,
        position: str | None = None,
        duties: str | None = None,
        company_industry: str | None = None,
        user_profile: dict[str, Any] | None = None,
        prompt_snapshot: dict[str, Any] | None = None,
    ) -> DeepSeekTurnResult:
        dialog_case_mode = self._is_dialog_interactivity_mode(interactivity_mode)
        if dialog_case_mode and not self.enabled:
            raise RuntimeError("Dialog case requires DeepSeek, but the client is disabled.")
        fallback = self._fallback_turn(
            case_title=case_title,
            user_message=fallback_user_message,
            dialogue=dialogue,
            case_skills=case_skills,
            interactivity_mode=interactivity_mode,
        )
        if not self.enabled:
            return fallback

        messages = self.interviewer_prompt_builder.build_case_turn_messages(
            policy=self,
            system_prompt=system_prompt,
            dialogue=dialogue,
            case_title=case_title,
            case_skills=case_skills,
            dialog_case_mode=dialog_case_mode,
            interactivity_mode=interactivity_mode,
            format_control_rules=format_control_rules,
            recommended_answer_length=recommended_answer_length,
            interviewer_prompt_override=interviewer_prompt_override,
            role_name=role_name,
            position=position,
            duties=duties,
            company_industry=company_industry,
            user_profile=user_profile,
            prompt_snapshot=prompt_snapshot,
        )
        routing_key = (
            f"user:{user_identifier}"
            if str(user_identifier or "").strip()
            else f"dialog:{case_title}|{role_name or ''}|{company_industry or ''}"
        )
        return self.interviewer_service.execute_case_turn(
            policy=self,
            messages=messages,
            fallback=fallback,
            dialog_case_mode=dialog_case_mode,
            routing_key=routing_key,
            system_prompt=system_prompt,
            company_industry=company_industry,
            user_profile=user_profile,
        )

    def build_manual_finish_turn(
        self,
        *,
        system_prompt: str,
        dialogue: list[dict[str, str]],
        case_title: str,
        case_skills: list[str],
        prompt_snapshot: dict[str, Any] | None = None,
    ) -> DeepSeekTurnResult:
        return self.interviewer_service.build_manual_finish_turn(
            policy=self,
            system_prompt=system_prompt,
            dialogue=dialogue,
            case_title=case_title,
            case_skills=case_skills,
            prompt_snapshot=prompt_snapshot,
        )

    def build_timeout_turn(
        self,
        *,
        system_prompt: str,
        dialogue: list[dict[str, str]],
        case_title: str,
        prompt_snapshot: dict[str, Any] | None = None,
    ) -> DeepSeekTurnResult:
        return self.interviewer_service.build_timeout_turn(
            policy=self,
            system_prompt=system_prompt,
            dialogue=dialogue,
            case_title=case_title,
            prompt_snapshot=prompt_snapshot,
        )


    def _fallback_turn(
        self,
        *,
        case_title: str,
        user_message: str,
        dialogue: list[dict[str, str]],
        case_skills: list[str],
        interactivity_mode: str | None = None,
        force_follow_up: bool = False,
    ) -> DeepSeekTurnResult:
        if self._is_dialog_interactivity_mode(interactivity_mode):
            follow_up = self._build_dialog_case_reply(
                user_message=user_message,
                dialogue=dialogue,
            )
        else:
            follow_up = self._build_follow_up_question(
                user_message=user_message,
                dialogue=dialogue,
                case_skills=case_skills,
            )
        return DeepSeekTurnResult(
            assistant_message=follow_up,
            is_case_complete=False,
            result_status="in_progress",
            completion_score=None,
            evaluator_summary="",
        )

    def _fallback_manual_finish_turn(
        self,
        *,
        case_title: str,
        dialogue: list[dict[str, str]],
        case_skills: list[str],
    ) -> DeepSeekTurnResult:
        user_turns = sum(1 for item in dialogue if item["role"] == "user")
        result_status = "passed" if user_turns > 0 else "skipped"
        return DeepSeekTurnResult(
            assistant_message=(
                f"Кейс «{case_title}» завершен по вашей команде. "
                "Я сохранил весь диалог по кейсу в системе."
            ),
            is_case_complete=True,
            result_status=result_status,
            completion_score=None,
            evaluator_summary="",
        )

    def _fallback_timeout_turn(
        self,
        *,
        case_title: str,
        dialogue: list[dict[str, str]],
    ) -> DeepSeekTurnResult:
        user_turns = sum(1 for item in dialogue if item["role"] == "user")
        result_status = "passed" if user_turns > 0 else "skipped"
        return DeepSeekTurnResult(
            assistant_message=(
                f"Время на прохождение кейса «{case_title}» истекло. "
                "Я завершаю кейс и сохраняю весь диалог в системе."
            ),
            is_case_complete=True,
            result_status=result_status,
            completion_score=None,
            evaluator_summary="",
        )

    def _is_dialog_interactivity_mode(self, interactivity_mode: str | None) -> bool:
        return self.dialog_policy.is_dialog_mode(interactivity_mode)

    def _build_follow_up_question(
        self,
        *,
        user_message: str,
        dialogue: list[dict[str, str]],
        case_skills: list[str],
    ) -> str:
        user_text = f"{user_message} " + " ".join(item["content"] for item in dialogue if item["role"] == "user")
        assistant_text = " ".join(item["content"] for item in dialogue if item["role"] == "assistant")
        normalized_user = user_text.lower()
        normalized_skills = " ".join(case_skills).lower()
        answered_topics = self._infer_follow_up_topics_from_text(user_text)
        asked_topics = self._infer_follow_up_topics_from_text(assistant_text)

        topic_questions = {
            "communication": "Как именно вы бы донесли свое решение до заинтересованных сторон и что сделали бы, чтобы избежать недопонимания между участниками процесса?",
            "team": "Уточните, пожалуйста, кого вы бы подключили к решению кейса и как распределили бы роли и зоны ответственности внутри команды?",
            "critical_thinking": "Какие данные, альтернативные сценарии или проверочные метрики вы бы использовали, чтобы критически проверить выбранное решение?",
            "creativity": "Какие еще альтернативные или более нестандартные варианты решения вы бы рассмотрели, прежде чем выбрать финальный подход?",
            "risks": "Принято. Какие ключевые риски и ограничения вы видите в вашем подходе, и как бы вы ими управляли?",
            "metrics": "Хорошо. По каким метрикам или KPI вы бы поняли, что выбранное решение действительно сработало?",
            "steps": "Уточните, пожалуйста, последовательность действий: какие шаги вы бы сделали сначала, а какие после этого?",
            "stakeholders": "Кого из участников процесса вы бы вовлекли в реализацию решения и как распределили бы зоны ответственности?",
            "control": "Спасибо. Уточните, пожалуйста, как вы будете контролировать выполнение решения и что сделаете, если первые результаты окажутся слабее ожидаемых?",
        }

        preferred_topics: list[str] = []
        if "коммуникац" in normalized_skills:
            preferred_topics.append("communication")
        if "команд" in normalized_skills:
            preferred_topics.append("team")
        if "критичес" in normalized_skills:
            preferred_topics.append("critical_thinking")
        if "креатив" in normalized_skills:
            preferred_topics.append("creativity")
        preferred_topics.extend(["risks", "metrics", "steps", "stakeholders", "control"])

        seen_topics: set[str] = set()
        ordered_topics: list[str] = []
        for topic in preferred_topics:
            if topic not in seen_topics:
                seen_topics.add(topic)
                ordered_topics.append(topic)

        for topic in ordered_topics:
            if topic in answered_topics or topic in asked_topics:
                continue
            return topic_questions[topic]

        if "рис" not in normalized_user and "огранич" not in normalized_user:
            return topic_questions["risks"]
        if "метрик" not in normalized_user and "kpi" not in normalized_user and "показател" not in normalized_user:
            return topic_questions["metrics"]
        if "шаг" not in normalized_user and "план" not in normalized_user and "сначала" not in normalized_user:
            return topic_questions["steps"]
        return topic_questions["control"]

    def _build_dialog_direct_answer(
        self,
        *,
        normalized_user: str,
        counterpart_role: str,
        asked_stages: set[str],
    ) -> str | None:
        return self.dialog_fallback_engine.build_direct_answer(
            normalized_user=normalized_user,
            counterpart_role=counterpart_role,
            asked_stages=asked_stages,
        )

    def _infer_dialog_counterpart_role_from_text(self, scenario_text: str) -> str:
        return self.dialog_state_machine.infer_counterpart_role(scenario_text)

    def _get_dialog_stage_label(self, stage_code: str | None) -> str:
        return self.dialog_state_machine.stage_label(stage_code)

    def _build_dialog_llm_context(
        self,
        *,
        system_prompt: str,
        dialogue: list[dict[str, str]],
    ) -> dict[str, Any]:
        return self.dialog_context_builder.build_runtime_context(
            policy=self,
            system_prompt=system_prompt,
            dialogue=dialogue,
        )

    def _build_dialog_scene_anchor(self, *, system_prompt: str, case_title: str | None) -> str:
        return self.dialog_context_builder.build_scene_anchor(
            system_prompt=system_prompt,
            case_title=case_title,
        )

    def _build_dialog_domain_anchor(
        self,
        *,
        role_name: str | None,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        user_profile: dict[str, Any] | None,
    ) -> str:
        return self.dialog_context_builder.build_domain_anchor(
            policy=self,
            role_name=role_name,
            position=position,
            duties=duties,
            company_industry=company_industry,
            user_profile=user_profile,
        )

    def _build_dialog_forbidden_drift(
        self,
        *,
        system_prompt: str,
        company_industry: str | None,
        user_profile: dict[str, Any] | None,
    ) -> str:
        return self.dialog_context_builder.build_forbidden_drift(
            system_prompt=system_prompt,
            company_industry=company_industry,
            user_profile=user_profile,
        )

    def _looks_like_dialog_domain_drift(self, text: str, forbidden_drift: str) -> bool:
        return self.dialog_policy.looks_like_domain_drift(text, forbidden_drift)

    def _get_dialog_role_contract(self, counterpart_role: str) -> str:
        return self.dialog_policy.role_contract(counterpart_role)

    def _get_dialog_stage_plan(self, *, counterpart_role: str, is_development_dialog: bool) -> tuple[str, ...]:
        return self.dialog_state_machine.stage_plan(
            counterpart_role=counterpart_role,
            is_development_dialog=is_development_dialog,
        )

    def _build_dialog_stage_prompt(
        self,
        *,
        counterpart_role: str,
        is_development_dialog: bool,
        asked_stages: set[str],
    ) -> str | None:
        return self.dialog_state_machine.build_stage_prompt(
            counterpart_role=counterpart_role,
            is_development_dialog=is_development_dialog,
            asked_stages=asked_stages,
        )

    def _build_dialog_case_reply(
        self,
        *,
        user_message: str,
        dialogue: list[dict[str, str]],
    ) -> str:
        return self.dialog_fallback_engine.build_reply(
            user_message=user_message,
            dialogue=dialogue,
        )

    def _infer_dialog_reply_stages(self, text: str | None) -> set[str]:
        return self.dialog_state_machine.infer_reply_stages(text)

    def _infer_follow_up_topics_from_text(self, text: str | None) -> set[str]:
        normalized = str(text or "").lower()
        topics: set[str] = set()
        topic_keywords = {
            "communication": ("коммуник", "соглас", "объясн", "донес", "обсужд", "сообщ", "позици"),
            "team": ("команд", "роль", "ответствен", "вовлек", "распредел", "подключ"),
            "critical_thinking": ("данн", "метрик", "гипот", "альтернатив", "сценар", "провер", "доказ", "анализ"),
            "creativity": ("нестандарт", "иде", "вариант", "альтернатив", "креатив"),
            "risks": ("риск", "проблем", "сбой", "огранич", "барьер"),
            "metrics": ("метрик", "kpi", "показател", "эффект", "результат"),
            "steps": ("этап", "шаг", "план", "сначала", "далее", "после", "последователь"),
            "stakeholders": ("стейк", "заказчик", "руковод", "участник", "смежн", "клиент"),
            "control": ("контрол", "монитор", "отслед", "провер", "корректир", "пересмотр"),
        }
        for topic, keywords in topic_keywords.items():
            if any(keyword in normalized for keyword in keywords):
                topics.add(topic)
        return topics

    def _parse_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise

    def _extract_dialog_assistant_message(self, raw: str) -> str:
        text = str(raw or "").strip()
        if not text:
            raise ValueError("Empty DeepSeek dialog response")
        try:
            parsed = self._parse_json(text)
            candidate = str(parsed.get("assistant_message") or "").strip()
            if candidate:
                return self._sanitize_dialog_assistant_message(candidate)
        except Exception:
            pass

        fenced = text
        if fenced.startswith("```"):
            fenced = fenced.strip("`")
            fenced = re.sub(r"^\s*json\s*", "", fenced, count=1, flags=re.IGNORECASE).strip()

        key_match = re.search(
            r'"assistant_message"\s*:\s*"(?P<value>(?:[^"\\]|\\.)+)"',
            fenced,
            flags=re.DOTALL,
        )
        if key_match:
            try:
                decoded = json.loads(f'"{key_match.group("value")}"')
                cleaned = str(decoded or "").strip()
                if cleaned:
                    return self._sanitize_dialog_assistant_message(cleaned)
            except Exception:
                pass

        cleaned_text = fenced.strip()
        if cleaned_text.startswith("{") and cleaned_text.endswith("}"):
            cleaned_text = re.sub(r'^\{\s*"assistant_message"\s*:\s*', "", cleaned_text, count=1, flags=re.DOTALL)
            cleaned_text = cleaned_text.rstrip("}").strip().strip('"').strip()
        if not cleaned_text:
            raise ValueError("Unable to extract dialog assistant message")
        return self._sanitize_dialog_assistant_message(cleaned_text)













    def _normalize_shift_context_phrase(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        lowered = value.lower()
        if lowered.startswith("вечерняя смена"):
            return re.sub(r"^вечерняя\s+смена", "вечерней смене", value, flags=re.IGNORECASE)
        if lowered.startswith("дневная смена"):
            return re.sub(r"^дневная\s+смена", "дневной смене", value, flags=re.IGNORECASE)
        if lowered.startswith("аналитическая смена"):
            return re.sub(r"^аналитическая\s+смена", "аналитической смене", value, flags=re.IGNORECASE)
        if lowered.startswith("смена"):
            return re.sub(r"^смена", "смене", value, flags=re.IGNORECASE)
        if lowered.startswith("вахта"):
            return re.sub(r"^вахта", "вахте", value, flags=re.IGNORECASE)
        return value














    def _normalize_issue_topic_phrase(self, text: str) -> str:
        clean = str(text or "").strip()
        if not clean:
            return ""
        replacements = {
            "подтверждение статуса судовой операции и следующего шага экипажа": "подтверждения статуса судовой операции и следующего шага экипажа",
            "подтверждение статуса партии и следующего этапа производства": "подтверждения статуса партии и следующего этапа производства",
            "подтверждение статуса отгрузки": "подтверждения статуса отгрузки",
            "обновление статуса по заявке или инциденту": "обновления статуса по заявке или инциденту",
            "изменение порядка обработки обращений с повторными возвратами": "изменения порядка обработки обращений с повторными возвратами",
            "новый шаблон обновления статуса для пользователей по проблемным обращениям": "нового шаблона обновления статуса для пользователей по проблемным обращениям",
        }
        return replacements.get(clean, clean)

    def _normalize_about_phrase(self, text: str) -> str:
        clean = str(text or "").strip()
        if not clean:
            return ""
        replacements = {
            "неполная запись следующего маневра в судовом журнале": "неполной записи следующего маневра в судовом журнале",
            "неполная запись результата в журнале смены": "неполной записи результата в журнале смены",
            "неполное подтверждение результата по заявке": "неполном подтверждении результата по заявке",
            "неполная фиксация следующего шага": "неполной фиксации следующего шага",
        }
        return replacements.get(clean, clean)

    def _normalize_involved_phrase(self, text: str) -> str:
        clean = str(text or "").strip()
        if not clean:
            return ""
        replacements = {
            "вахта «Браво» и старший помощник": "вахта «Браво» и старший помощник капитана",
            "старший помощник": "старший помощник капитана",
            "вахта «Браво»": "вахта «Браво»",
        }
        return replacements.get(clean, clean)





    def _fallback_domain_profile(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
    ) -> dict[str, Any]:
        family = self._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        normalized_company_industry = self.normalize_company_industry(
            company_industry=company_industry,
            position=position,
            duties=duties,
        )
        domain = (
            self._preferred_domain_label_for_family(family)
            or normalized_company_industry
            or self._infer_domain(position=position, duties=duties, company_industry=company_industry)
        )
        process = self._infer_process(position=position, duties=duties)
        scenario = self._build_case_scenario_seed(
            domain=domain,
            process=process,
            position=position,
            duties=duties,
            role_name=role_name,
        )
        return {
            "domain_label": domain,
            "processes": [
                scenario["workflow_label"],
                scenario["critical_step"],
                scenario["request_type"],
            ],
            "tasks": self._normalize_string_list(
                scenario["ticket_titles"],
                fallback=["уточнение статуса", "фиксация следующего шага", "согласование результата"],
            ),
            "stakeholders": self._normalize_string_list(
                [scenario["primary_stakeholder"], scenario["adjacent_team"]],
                fallback=["смежная команда", "руководитель участка"],
            ),
            "systems": self._normalize_string_list(
                [scenario["system_name"], scenario["channel"], scenario["source_of_truth"]],
                fallback=[scenario["system_name"], scenario["source_of_truth"]],
            ),
            "artifacts": self._normalize_string_list(
                [scenario["source_of_truth"], scenario["work_items"]],
                fallback=[scenario["source_of_truth"]],
            ),
            "risks": self._normalize_string_list(
                [scenario["incident_impact"], scenario["business_impact"]],
                fallback=[scenario["incident_impact"], scenario["business_impact"]],
            ),
            "constraints": self._normalize_string_list(
                [scenario["limits_short"]],
                fallback=[scenario["limits_short"]],
            ),
        }

    def _normalize_domain_profile(self, raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        result = dict(fallback)
        domain_label = self._sanitize_personalization_value(str(raw.get("domain_label") or ""))
        if domain_label:
            result["domain_label"] = domain_label
        for key in ("processes", "tasks", "stakeholders", "systems", "artifacts", "risks", "constraints"):
            result[key] = self._normalize_string_list(raw.get(key), fallback=result.get(key) or [])
        return result

    def _normalize_domain_profile_with_profile(
        self,
        raw: dict[str, Any],
        fallback: dict[str, Any],
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> dict[str, Any]:
        normalized = self._normalize_domain_profile(raw, fallback)
        family = self._detect_domain_family(position=position, duties=duties, company_industry=company_industry)
        preferred_label = self._preferred_domain_label_for_family(family)
        normalized_industry = self._fallback_normalize_company_industry(company_industry)
        current_label = str(normalized.get("domain_label") or "").strip()
        if preferred_label and (not current_label or current_label == normalized_industry or current_label == family):
            normalized["domain_label"] = preferred_label
        markers_map = self._domain_family_markers()
        primary_fields = ("processes", "tasks", "stakeholders", "systems", "artifacts")

        def _contains_markers(values: list[str] | str | None, markers: tuple[str, ...]) -> bool:
            if isinstance(values, str):
                return any(marker in values.lower() for marker in markers)
            return any(any(marker in str(item).lower() for marker in markers) for item in (values or []))

        fields = ("domain_label", "processes", "tasks", "stakeholders", "systems", "artifacts", "risks", "constraints")
        conflicting = [
            other_family
            for other_family, markers in markers_map.items()
            if other_family != family and any(_contains_markers(normalized.get(key), markers) for key in fields)
        ]
        if family == "generic":
            if conflicting:
                return fallback
            return normalized
        expected_markers = markers_map.get(family, ())
        has_expected = any(_contains_markers(normalized.get(key), expected_markers) for key in fields)
        conflicting_primary = [
            other_family
            for other_family, markers in markers_map.items()
            if other_family != family and any(_contains_markers(normalized.get(key), markers) for key in primary_fields)
        ]
        if conflicting_primary:
            return fallback
        if conflicting and not has_expected:
            return fallback
        return normalized

    def _preferred_domain_label_for_family(self, family: str | None) -> str | None:
        labels = {
            "engineering": "инженерно-конструкторской деятельности",
            "beauty": "салонных и бьюти-услуг",
            "maritime": "судоходства и морских перевозок",
            "horeca": "общественного питания и ресторанного сервиса",
            "food_production": "пищевого производства",
            "client_service": "клиентского сервиса",
            "it_support": "ИТ-поддержки",
            "business_analysis": "бизнес-аналитики",
            "finance": "финансового учета",
            "learning_and_development": "обучения и развития персонала",
            "hr": "управления персоналом",
            "logistics": "логистики",
        }
        return labels.get(str(family or "").strip().lower())













    def _flatten_phrase_values(self, values: list[Any] | None, *, limit: int = 4) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values or []:
            text = str(raw or "").strip()
            if not text:
                continue
            parts = [part.strip() for part in re.split(r",\s*", text) if part.strip()]
            for part in parts:
                cleaned = self._sanitize_personalization_value(part)
                key = cleaned.lower()
                if not cleaned or key in seen:
                    continue
                seen.add(key)
                result.append(cleaned)
                if len(result) >= limit:
                    return result
        return result


    def _specificity_examples_for_case(self, specificity: dict[str, Any], *, case_kind: str) -> list[str]:
        family = self._infer_specificity_domain_family(specificity)
        markers_map = self._domain_family_markers()
        titles = [str(item).strip() for item in (specificity.get("ticket_titles") or []) if str(item).strip()]
        if titles:
            expected_markers = markers_map.get(family, ())
            has_expected = any(
                any(marker in title.lower() for marker in expected_markers)
                for title in titles
            ) if expected_markers else False
            conflicting = any(
                other_family != family and any(any(marker in title.lower() for marker in markers) for title in titles)
                for other_family, markers in markers_map.items()
            )
            if family == "generic" or has_expected or not conflicting:
                return titles[:3]

        if family == "horeca":
            if case_kind == "planning":
                return [
                    "гость ждет решение по спорному заказу",
                    "замечание по коктейлю еще не зафиксировано в журнале смены",
                    "администратор зала ждет подтверждения по конфликту с чеком",
                ]
            if case_kind == "priority":
                return [
                    "спорный заказ гостя без подтвержденного решения",
                    "замечание по заказу, которое нужно передать следующей смене",
                    "конфликт по чеку, по которому администратор ждет обновления",
                ]
        if family == "maritime":
            if case_kind == "planning":
                return [
                    "передача вахты без подтвержденного следующего маневра",
                    "запись в судовом журнале требует уточнения перед следующим этапом рейса",
                    "экипаж ждет согласованного распоряжения по ближайшему действию",
                ]
            if case_kind == "priority":
                return [
                    "уточнение записи по предыдущей вахте",
                    "подтверждение готовности к следующему маневру",
                    "передача экипажу обновленной информации по обстановке",
                ]
        if family == "engineering":
            if case_kind == "planning":
                return [
                    "комплект документации ждет закрытия замечаний по чертежам",
                    "смежное подразделение ожидает подтверждения состава доработок",
                    "следующий этап выпуска КД зависит от финальной проверки",
                ]
            if case_kind == "priority":
                return [
                    "проверка критичных замечаний по комплекту чертежей",
                    "подтверждение изменений перед передачей в смежное подразделение",
                    "финальная сверка состава документации перед выпуском",
                ]
        if family == "business_analysis":
            if case_kind == "planning":
                return [
                    "уточнение требований перед передачей задачи в разработку",
                    "согласование критериев готовности с заказчиком",
                    "подготовка обновленного ТЗ по срочной доработке",
                ]
            if case_kind == "priority":
                return [
                    "срочное уточнение ТЗ, без которого задача вернется из разработки",
                    "обновление статуса для заказчика по проблемной задаче",
                    "согласование спорного требования перед следующим этапом работы",
                ]
        if family == "it_support":
            if case_kind == "planning":
                return [
                    "заявка без подтвержденного результата от пользователя",
                    "инцидент со срочным обновлением статуса",
                    "эскалация по обращению, где следующий шаг не зафиксирован",
                ]
            if case_kind == "priority":
                return [
                    "заявка, по которой пользователь ждет ответ до конца дня",
                    "повторный инцидент без понятного следующего шага",
                    "эскалация, влияющая на работу смежной линии",
                ]
        return titles[:3] if titles else [
            "срочная задача без понятного владельца",
            "этап работы без подтвержденного следующего шага",
            "вопрос, который нельзя передавать дальше без уточнения",
        ]





















    def _stakeholder_context_sentence(self, type_code: str, named_stakeholders: str) -> str:
        people = str(named_stakeholders or "").strip()
        if not people:
            return ""
        code = str(type_code or "").upper()
        mapping = {
            "F05": f"В распределении задач и контрольных точек уже участвуют {people}.",
            "F08": f"На выбор первого приоритета уже влияют {people}.",
            "F09": f"Изменения на этом участке будут заметны для {people}.",
            "F10": f"Решение по запуску идеи будут обсуждать {people}.",
            "F03": f"Из-за этих срывов в ситуацию уже вовлечены {people}: им приходится разбирать последствия, уточнять статус и помогать с возвратами или эскалацией.",
            "F12": f"Из-за этих срывов в ситуацию уже вовлечены {people}: им приходится разбирать последствия, уточнять статус и помогать с возвратами или эскалацией.",
            "F11": f"Если риск подтвердится, в дальнейшее согласование войдут {people}.",
        }
        return mapping.get(code, "")











    def _split_template_sentences(self, text: str) -> list[str]:
        source = str(text or "").strip()
        if not source:
            return []
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", source) if part.strip()]




    def _is_template_guidance_sentence(self, sentence: str) -> bool:
        lowered = str(sentence or "").strip().lower()
        if not lowered:
            return False
        return any(
            marker in lowered
            for marker in (
                "от вас ждут",
                "сейчас важно",
                "сейчас нужно",
                "вам нужно",
                "прежде чем",
                "до того, как",
            )
        )



    def _is_template_meta_sentence(self, sentence: str) -> bool:
        lowered = str(sentence or "").strip().lower()
        if not lowered:
            return False
        meta_markers = (
            "пользователь будет вести разговор",
            "бот играет роль",
            "чат-бот",
            "отвечает на ваши реплики",
        )
        return any(marker in lowered for marker in meta_markers)










    def _uses_template_locked_context(self, *, case_type_code: str | None) -> bool:
        return str(case_type_code or "").upper() in {
            "F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10", "F11", "F12", "F13", "F14", "F15",
        }

































    def _normalize_user_visible_task(
        self,
        task_text: str,
        *,
        case_type_code: str | None,
        context_text: str,
        case_title: str,
    ) -> str:
        value = cleanup_case_text(str(task_text or ""))
        if not value:
            return ""

        value = re.sub(r"^(?:Что нужно сделать:\s*)+", "", value, flags=re.IGNORECASE).strip()
        lower_value = value.lower()
        hint_markers = (
            "по критериям",
            "сгруппируйте",
            "выделите",
            "обозначьте цель",
            "дайте обратную связь",
            "согласуйте план",
            "опишите, что известно",
            "оцените риски",
            "предложите план",
            "зафиксируйте владельцев",
            "метрик",
            "kpi",
            "на 2–4 недели",
            "на 2-4 недели",
            "выслушайте",
            "определите, какая поддержка",
            "выделите причины",
        )
        if any(marker in lower_value for marker in hint_markers) or len(value) > 140:
            fallback = self._build_user_visible_case_task(
                case_type_code=str(case_type_code or "").upper(),
                context_text=context_text,
                case_title=case_title,
            )
            if fallback:
                return fallback
        return value











    def _split_heavy_case_sentences(self, text: str) -> str:
        result = str(text or "").strip()
        if not result:
            return ""
        replacements = (
            (r";\s*горизонт работы\s*—", ". Горизонт работы —"),
            (r"\.\s*Ставки высокие:\s*на кону\s+", ". Ставки высокие: на кону "),
            (r"\.\s*Дополнительно есть ограничения среды:\s*", ". Дополнительно есть ограничения: "),
            (r"\.\s*Нужно не просто выбрать вариант, а\s*", ". Нужно не просто выбрать вариант, а "),
            (r"\.\s*Основная проблема сейчас такая:\s*", ". Основная проблема сейчас такая: "),
            (r"\.\s*Например, можно обсудить идею\s+", ". Например, можно обсудить идею "),
        )
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def _compress_structured_case_sections(
        self,
        text: str,
        *,
        readability_rules: dict[str, Any] | None = None,
    ) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        parts = [part.strip() for part in re.split(r"\n\s*\n", value) if part.strip()]
        if not parts:
            return ""

        rules = readability_rules or {}
        paragraph_rules = rules.get("paragraph_rules") if isinstance(rules, dict) else []
        intro_limit = 4
        known_limit = 4
        limits_limit = 3
        if isinstance(paragraph_rules, list):
            joined = " ".join(str(item) for item in paragraph_rules)
            if "3–5" in joined or "3-5" in joined:
                intro_limit = 5
                known_limit = 4
            if "2–4" in joined or "2-4" in joined:
                intro_limit = 4
                known_limit = 4
            if "1–3" in joined or "1-3" in joined:
                limits_limit = 3

        compacted: list[str] = []
        for part in parts:
            if part.startswith("Ситуация:"):
                compacted.append(part)
                continue
            if part.startswith("**Что известно**"):
                compacted.append(self._compress_case_bullet_block(part, max_items=known_limit, drop_generic_participant=True))
                continue
            if part.startswith("**Что ограничивает**"):
                compacted.append(self._compress_case_bullet_block(part, max_items=limits_limit, drop_generic_participant=False))
                continue
            compacted.append(self._compress_case_intro_paragraph(part, max_sentences=intro_limit))
        return "\n\n".join(part.strip() for part in compacted if part.strip()).strip()

    def _compress_case_bullet_block(
        self,
        block_text: str,
        *,
        max_items: int,
        drop_generic_participant: bool,
    ) -> str:
        lines = [line.strip() for line in str(block_text or "").splitlines() if line.strip()]
        if not lines:
            return ""
        header = lines[0]
        bullets = [line[1:].strip() if line.startswith("-") else line.strip() for line in lines[1:]]
        filtered: list[str] = []
        seen: set[str] = set()
        for bullet in bullets:
            if not bullet:
                continue
            lowered = bullet.lower()
            if drop_generic_participant and lowered in {
                "основной участник: клиент",
                "основной участник: заказчик",
                "основной участник: пользователь",
            }:
                continue
            if lowered.startswith("в фокусе:") and any(
                marker in lowered
                for marker in ("обновление клиента", "следующего шага", "фиксаци")
            ):
                continue
            if lowered.startswith("доступно:") and len(lowered) > 120:
                continue
            key = re.sub(r"[^\wа-яё]+", " ", lowered, flags=re.IGNORECASE).strip()
            if key in seen:
                continue
            seen.add(key)
            filtered.append(bullet)
            if len(filtered) >= max_items:
                break
        if not filtered:
            return header
        return header + "\n- " + "\n- ".join(filtered)

    def _compress_case_intro_paragraph(self, text: str, *, max_sentences: int) -> str:
        value = cleanup_case_text(text)
        if not value:
            return ""
        sentences = self._split_case_sentences(value)
        if not sentences:
            return value

        filtered: list[str] = []
        seen: set[str] = set()
        for sentence in sentences:
            cleaned = cleanup_case_text(sentence)
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered.startswith("например, можно обсудить идею"):
                continue
            if lowered.startswith("это касается "):
                continue
            if lowered.startswith("изменения на этом участке будут заметны"):
                continue
            if lowered.startswith("решение по запуску идеи будут обсуждать"):
                continue
            if lowered.startswith("в ситуации уже фигурируют такие рабочие объекты"):
                continue
            if lowered.startswith("сейчас в фокусе такие задачи"):
                continue
            if lowered.startswith("на выбор первого приоритета уже влияют"):
                continue
            if lowered.startswith("на этом участке доступен такой состав"):
                continue
            if lowered.startswith("по ресурсу ситуация ограничена так"):
                continue
            if lowered.startswith("в распределении задач и контрольных точек уже участвуют"):
                continue
            key = re.sub(r"[^\wа-яё]+", " ", lowered, flags=re.IGNORECASE).strip()
            if key in seen:
                continue
            seen.add(key)
            filtered.append(cleaned)

        if not filtered:
            filtered = [cleanup_case_text(sentence) for sentence in sentences if cleanup_case_text(sentence)]

        compact = filtered[:max_sentences]
        result = " ".join(compact)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()

    def _split_case_sentences(self, text: str) -> list[str]:
        value = str(text or "").strip()
        if not value:
            return []
        protected = value.replace("т. е.", "т_е_").replace("т.е.", "т_е_")
        parts = re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z0-9*])", protected)
        result: list[str] = []
        for part in parts:
            sentence = part.replace("т_е_", "т. е.").strip()
            if sentence:
                result.append(sentence)
        return result


    def _trim_case_text_overload(self, text: str, *, is_task: bool) -> str:
        result = str(text or "").strip()
        if not result:
            return ""
        if is_task:
            return result
        result = re.sub(r"\bВ ситуации уже фигурируют такие рабочие объекты:\s*([^.]*)\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bСейчас в фокусе такие задачи:\s*([^.]*)\.\s*", lambda m: f"Сейчас в фокусе: {m.group(1).strip()}. ", result, flags=re.IGNORECASE)
        result = re.sub(r"\bПроверка идет по ([^.]{120,})\.", lambda m: f"Проверка идет по {m.group(1).strip()}.", result, flags=re.IGNORECASE)
        result = re.sub(r"\bНапример, можно обсудить идею\s+«[^»]+»\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bЭто касается\s+\*\*[^*]+\*\*\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bИзменения на этом участке будут заметны для\s+[^.]+\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bРешение по запуску идеи будут обсуждать\s+[^.]+\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bНа выбор первого приоритета уже влияют\s+[^.]+\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bНа этом участке доступен такой состав:\s*[^.]+\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bПо ресурсу ситуация ограничена так:\s*[^.]+\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bВ распределении задач и контрольных точек уже участвуют\s+[^.]+\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()














    def _render_company_specificity(
        self,
        *,
        company_industry: str | None,
        case_title: str,
        text: str,
    ) -> str:
        industry = (company_industry or "").strip().lower().replace("ё", "е")
        source = f"{industry} {case_title} {text}".lower()
        if not industry:
            return ""

        if (
            industry.startswith("ит")
            or " ит " in f" {industry} "
            or any(word in source for word in ("it", "айти", "тех", "saas", "софт", "цифров", "jira", "тз", "разработ"))
        ):
            return "Компания оказывает ИТ-сервисы корпоративным клиентам, поэтому задержки по обращениям быстро влияют на их рабочие процессы."
        if any(word in source for word in ("судоход", "морск", "судно", "корабл", "капитан", "вахт", "навигац", "порт", "экипаж", "рейс", "мостик")):
            return "Компания работает в сфере судоходства и морских перевозок, поэтому любая несогласованность в передаче вахты, фиксации действий и координации экипажа быстро влияет на безопасность и сроки рейса."
        if any(word in source for word in ("космет", "парикмах", "салон", "уклад", "стриж", "волос", "beauty", "барберш")):
            return "Компания работает в сфере салонных и бьюти-услуг, поэтому любая несогласованность по результату услуги и следующему шагу быстро становится заметна клиенту."
        if any(word in source for word in ("бар", "бармен", "ресторан", "общепит", "коктейл", "гость", "меню", "официант")):
            return "Компания работает в сфере общественного питания и сервиса, поэтому любой сбой в обслуживании или закрытии заказа быстро отражается на впечатлении гостя и выручке смены."
        if any(word in source for word in ("пищев", "продукц", "партия", "сырье", "упаков", "маркиров", "карта партии", "линия производства", "отметка отк", "контролер отк")):
            return "Компания работает в пищевом производстве, поэтому любое расхождение в контроле партии или передаче на следующий этап быстро влияет на качество продукции и сроки выпуска."
        if any(word in source for word in ("ядер", "энергет", "реактор", "энергоблок", "конструкт", "чертеж", "документац", "предприят")):
            return "Компания работает в сфере ядерной энергетики, поэтому любые разрывы в согласовании и выпуске документации быстро влияют на сроки, качество решений и безопасность последующих этапов."
        if any(word in source for word in ("банк", "фин", "страх", "лизинг", "платеж")):
            return "Компания работает с финансовыми сервисами, поэтому любая ошибка в статусах и сроках быстро влияет на доверие клиентов."
        if any(word in source for word in ("логист", "достав", "склад", "транспорт")):
            return "Компания занимается доставкой и логистическими операциями, поэтому любые сбои сразу отражаются на сроках и координации."
        if any(word in source for word in ("ритейл", "розниц", "e-commerce", "маркетплейс", "магазин")):
            return "Компания работает с заказами и клиентскими обращениями в рознице, поэтому задержки быстро становятся заметны клиенту."
        if any(word in source for word in ("производ", "завод", "промышлен")):
            return "Компания связана с производством и поставками, поэтому несогласованность действий быстро влияет на сроки и исполнение обязательств."
        if any(word in source for word in ("hr", "персонал", "подбор", "рекрут", "кадров")):
            return "Компания работает с подбором и сопровождением людей, поэтому качество коммуникации и договоренностей здесь особенно важно."
        return ""
























    def _quality_token_set(self, text: str) -> set[str]:
        cleaned = cleanup_case_text(text).lower()
        tokens = {
            token
            for token in re.findall(r"[а-яёa-z0-9-]{4,}", cleaned)
            if token not in {"клиент", "команд", "задач", "ситуац", "нужно", "котор", "этого", "этой", "будет", "между"}
        }
        return tokens

    def _score_case_text_quality(
        self,
        *,
        case_type_code: str | None,
        template_context: str,
        template_task: str,
        generated_context: str,
        generated_task: str,
        user_profile: dict[str, Any] | None,
        case_specificity: dict[str, Any] | None,
        existing_contexts: list[str] | None = None,
    ) -> dict[str, Any]:
        type_code = str(case_type_code or "").upper()
        specificity = dict(case_specificity or {})
        profile = dict(user_profile or {})
        findings: list[str] = []
        strengths: list[str] = []

        task_match = cleanup_case_text(template_task) == cleanup_case_text(generated_task)
        fidelity_missing = self._validate_template_fidelity(
            case_type_code=type_code,
            context_text=generated_context,
            task_text=generated_task,
            case_specificity=specificity,
        )
        template_fidelity_score = 5.0
        if task_match:
            strengths.append("Задание пользователя сохранено без искажений.")
        else:
            template_fidelity_score -= 1.0
            findings.append("Формулировка задания отличается от шаблона.")
        if fidelity_missing:
            template_fidelity_score -= min(1.8, 0.35 * len(set(fidelity_missing)))
            findings.append("Не все обязательные элементы шаблона выражены достаточно явно.")
        template_fidelity_score = max(1.0, round(template_fidelity_score, 1))

        personalization_markers: list[str] = []
        personalization_markers.extend(_clean for _clean in cleanup_case_list(profile.get("user_processes") or [], limit=4) if _clean)
        personalization_markers.extend(_clean for _clean in cleanup_case_list(profile.get("user_tasks") or [], limit=3) if _clean)
        personalization_markers.extend(_clean for _clean in cleanup_case_list(profile.get("user_stakeholders") or [], limit=3) if _clean)
        personalization_markers.extend(
            item for item in [
                cleanup_case_text(str(profile.get("user_domain") or "")),
                cleanup_case_text(str(specificity.get("workflow_label") or "")),
                cleanup_case_text(str(specificity.get("idea_label") or "")),
                cleanup_case_text(str(specificity.get("resource_profile") or "")),
            ]
            if item
        )
        personalization_score = 5.0
        personalization_hits = 0
        combined_text = f"{generated_context} {generated_task}".lower()
        for marker in personalization_markers:
            tokens = [token for token in re.findall(r"[а-яёa-z0-9-]{4,}", marker.lower()) if token]
            if tokens and any(token in combined_text for token in tokens[:3]):
                personalization_hits += 1
        if personalization_hits >= 3:
            strengths.append("Кейс опирается на персонализированный профиль пользователя.")
        elif personalization_hits == 2:
            personalization_score -= 0.6
        else:
            personalization_score -= 1.4
            findings.append("Персонализация выражена недостаточно явно.")
        if "стейкхолдер" in combined_text:
            personalization_score -= 0.5
            findings.append("В тексте осталась слишком общая роль вместо конкретного участника.")
        personalization_score = max(1.0, round(personalization_score, 1))

        concreteness_score = 5.0
        concrete_signals = 0
        if re.search(r"\b\d+\b", generated_context):
            concrete_signals += 1
        if "обращен" in combined_text:
            concrete_signals += 1
        if any(name in generated_context for name in ("Дмитрий", "Анна", "Игор")):
            concrete_signals += 1
        if any(marker in combined_text for marker in ("crm", "журнал", "чек-лист", "sla", "1:1")):
            concrete_signals += 1
        if any(marker in combined_text for marker in ("следующий шаг по обращению", "статуса одного и того же обращения")):
            concrete_signals += 1
        if concrete_signals >= 4:
            strengths.append("Ситуация описана через конкретные предметы, действия и ограничения.")
        elif concrete_signals == 3:
            concreteness_score -= 0.5
        else:
            concreteness_score -= 1.3
            findings.append("Кейсу не хватает предметной конкретики.")
        if re.search(r"\bстатус\b", generated_context, flags=re.IGNORECASE) and "статус обращ" not in combined_text:
            concreteness_score -= 0.4
            findings.append("Не везде явно указан предмет статуса.")
        concreteness_score = max(1.0, round(concreteness_score, 1))

        readability_score = 5.0
        sentence_parts = [part.strip() for part in re.split(r"[.!?]+", cleanup_case_text(generated_context)) if part.strip()]
        if sentence_parts:
            sentence_lengths = [len(part.split()) for part in sentence_parts]
            long_sentences = sum(1 for size in sentence_lengths if size > 28)
            very_long_sentences = sum(1 for size in sentence_lengths if size > 38)
            readability_score -= min(1.5, long_sentences * 0.2 + very_long_sentences * 0.25)
            if sum(sentence_lengths) / max(len(sentence_lengths), 1) > 22:
                readability_score -= 0.3
                findings.append("Описание ситуации перегружено по длине.")
        awkward_patterns = (
            r"опирается на такие данные:\s*карточк",
            r"\bв работе регулярно повторяется одна и та же проблема\b",
            r"\bтаким действиям, как\b",
        )
        if any(re.search(pattern, generated_context, flags=re.IGNORECASE) for pattern in awkward_patterns):
            readability_score -= 0.6
            findings.append("В тексте есть тяжеловесные или неестественные формулировки.")
        readability_score = max(1.0, round(readability_score, 1))

        diversity_score = 5.0
        current_tokens = self._quality_token_set(generated_context)
        max_similarity = 0.0
        for other in existing_contexts or []:
            other_tokens = self._quality_token_set(other)
            if not current_tokens or not other_tokens:
                continue
            similarity = len(current_tokens & other_tokens) / max(len(current_tokens | other_tokens), 1)
            max_similarity = max(max_similarity, similarity)
        if max_similarity > 0.85:
            diversity_score = 2.8
            findings.append("Кейс слишком похож на другой кейс этой же сессии.")
        elif max_similarity > 0.70:
            diversity_score = 3.7
            findings.append("Сюжет кейса недостаточно отличается от соседних кейсов сессии.")
        elif max_similarity > 0.55:
            diversity_score = 4.3
        else:
            strengths.append("Кейс достаточно отличается от других кейсов сессии.")

        total_score = round(
            0.30 * template_fidelity_score
            + 0.25 * personalization_score
            + 0.20 * concreteness_score
            + 0.15 * readability_score
            + 0.10 * diversity_score,
            2,
        )
        if total_score >= 4.5:
            verdict = "Высокое качество кейса."
        elif total_score >= 4.0:
            verdict = "Хорошее качество кейса."
        elif total_score >= 3.0:
            verdict = "Кейс частично соответствует ожиданиям и требует доработки."
        else:
            verdict = "Кейс требует существенной доработки."

        return {
            "case_text_quality_score": total_score,
            "template_fidelity_score": template_fidelity_score,
            "personalization_score": personalization_score,
            "concreteness_score": concreteness_score,
            "readability_score": readability_score,
            "diversity_score": round(diversity_score, 1),
            "quality_issues": findings,
            "quality_strengths": strengths,
            "quality_verdict": verdict,
            "task_match": task_match,
            "template_fidelity_missing": fidelity_missing,
        }







    def _split_context_and_situation(self, text: str) -> tuple[str, str]:
        clean = (text or "").strip()
        if not clean:
            return "", ""
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip()]
        if not sentences:
            return clean, ""

        context_parts: list[str] = []
        situation_parts: list[str] = []
        for sentence in sentences:
            lowered = sentence.lower()
            if (
                not context_parts
                and (
                    lowered.startswith("вы ")
                    or "работаете" in lowered
                    or "отвечаете за" in lowered
                    or "участвуете" in lowered
                )
            ):
                context_parts.append(sentence)
                continue
            situation_parts.append(sentence)

        if not context_parts and sentences:
            context_parts.append(sentences[0])
            situation_parts = sentences[1:]
        return " ".join(context_parts).strip(), " ".join(situation_parts).strip()









    def _build_case_signal_prompt(self, case_type_code: str | None) -> str:
        type_code = str(case_type_code or "").strip().upper()
        mapping = {
            "F01": "Для этого типа кейса в ситуации желательно показать сигнал в виде письма, жалобы, обращения или прямой реплики участника.",
            "F02": "Для этого типа кейса в ситуации желательно показать исходный запрос: письмо, чат, сообщение, реплику или формулировку обращения.",
            "F03": "Для этого типа кейса в ситуации желательно показать живую реплику, переписку, жалобу или сообщение участника конфликта.",
            "F09": "Для этого типа кейса в ситуации желательно показать сигнал проблемы: жалобу, обращение, комментарий, сообщение в чате или реплику заказчика/участника.",
            "F10": "Для этого типа кейса в ситуации желательно показать источник идеи: чат, звонок, сообщение, реплику инициатора или короткое предложение идеи.",
            "F12": "Для этого типа кейса в ситуации желательно показать триггер разговора: реплику, жалобу, сообщение, обратную связь или цитату участника.",
        }
        return mapping.get(type_code, "Если уместно, добавь в ситуацию конкретный рабочий сигнал: письмо, сообщение, жалобу, звонок, эскалацию или реплику участника.")





    def _case_should_include_signal(self, *, context: str, case_type_code: str, case_title: str) -> bool:
        if case_type_code in {"F01", "F02", "F03", "F04", "F06", "F07", "F08", "F09", "F10", "F12"}:
            return True
        lowered = f"{case_title} {context}".lower()
        signal_markers = (
            "жалоб",
            "эскалац",
            "сообщен",
            "письм",
            "уведомл",
            "комментар",
            "написал",
            "написала",
            "crm",
            "service desk",
            "тикет",
            "обращени",
        )
        return any(marker in lowered for marker in signal_markers)








    def _context_requires_explicit_positions(self, context: str) -> bool:
        lowered = str(context or "").lower()
        strong_triggers = (
            "с одной стороны",
            "с другой стороны",
            "разные ожидания",
            "позиции расходятся",
            "спор",
            "не согласен",
            "конфликт",
        )
        soft_triggers = (
            "по-разному",
            "настаивает",
            "считает",
            "хочет",
            "опасается",
        )
        participant_markers = (
            "заказчик",
            "клиент",
            "команда",
            "руководитель",
            "смежн",
            "подрядчик",
            "эксперт",
            "hr",
            "l&d",
            "методист",
            "менеджер",
        )
        strong_count = sum(1 for trigger in strong_triggers if trigger in lowered)
        soft_count = sum(1 for trigger in soft_triggers if trigger in lowered)
        participant_count = sum(1 for marker in participant_markers if marker in lowered)
        if strong_count >= 1 and participant_count >= 2:
            return True
        if strong_count >= 1 and soft_count >= 1:
            return True
        return False

    def _context_has_explicit_positions(self, context: str) -> bool:
        text = str(context or "")
        lowered = text.lower()
        attributed_markers = (
            "считает, что",
            "настаивает, что",
            "хочет, чтобы",
            "опасается, что",
            "просит",
            "говорит:",
            "пишет:",
        )
        if any(mark in lowered for mark in attributed_markers) and (
            ":" in text or "—" in text or "«" in text or "»" in text
        ):
            return True
        return False





















    def _normalize_prompt_sentences(self, text: str) -> str:
        normalized_lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                if normalized_lines and normalized_lines[-1] != "":
                    normalized_lines.append("")
                continue
            line = re.sub(r"\s{2,}", " ", line)
            if re.match(r"^(Ситуация:|\*\*Что известно\*\*|\*\*Что ограничивает\*\*|Что нужно сделать:)", line):
                normalized_lines.append(line)
                continue
            if line and line[0].islower():
                line = line[0].upper() + line[1:]
            if line[-1] not in ".!?:":
                line += "."
            normalized_lines.append(line)
        result = "\n".join(normalized_lines)
        result = re.sub(r"([.!?])\s+([а-яё])", lambda m: f"{m.group(1)} {m.group(2).upper()}", result)
        result = re.sub(r"\s+([.,!?;:])", r"\1", result)
        return result

    def _proofread_case_prompt_text(self, text: str) -> str:
        fallback = self._fallback_proofread_case_prompt_text(text)
        if not self.enabled:
            return fallback

        prompt = (
            "Исправь текст системного промпта для интервью по кейсу. "
            "Нужно исправить только орфографию, опечатки, пробелы, пунктуацию, регистр букв "
            "и очевидные ошибки согласования слов по падежу, числу и роду. "
            "Нельзя менять смысл, структуру, набор фактов, роль пользователя, условия кейса, "
            "названия сущностей и логику инструкций. "
            "Не сокращай текст и не добавляй новые требования. "
            "Верни только исправленный текст без markdown и пояснений.\n\n"
            f"Текст промпта:\n{text}"
        )
        try:
            corrected = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Ты аккуратно вычитываешь русскоязычные промпты, исправляя орфографию и пунктуацию без изменения смысла.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            ).strip()
            normalized = self._strip_markdown_fences(corrected or fallback)
            return self._fallback_proofread_case_prompt_text(normalized)
        except Exception:
            return fallback






    def _strip_markdown_fences(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```") and cleaned.endswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        return cleaned.strip()

    def _sanitize_interviewer_message(self, text: str) -> str:
        sanitized = self._enforce_external_sharing_policy(text)
        if sanitized != (text or "").strip():
            return (
                "Опишите, пожалуйста, решение прямо в текущем диалоге. "
                "Передавать информацию во внешние сервисы, документы, мессенджеры или почту не требуется."
            )
        return self._normalize_prompt_sentences(sanitized).strip()

    def _sanitize_dialog_assistant_message(self, text: str) -> str:
        original = str(text or "").strip()
        sanitized = self._enforce_external_sharing_policy(original)
        normalized = self._normalize_prompt_sentences(sanitized).strip()
        if normalized:
            return normalized
        return self._normalize_prompt_sentences(original).strip()

    def _looks_like_dialog_meta_response(self, text: str) -> bool:
        return self.dialog_policy.looks_like_meta_response(text)

    def _enforce_external_sharing_policy(self, text: str) -> str:
        result = (text or "").strip()
        if not result:
            return self._base_external_policy_line()

        original = result
        cleaned_lines: list[str] = []
        sentence_chunks = re.split(r"(?<=[.!?])\s+|\n+", original)
        for chunk in sentence_chunks:
            original_sentence = chunk.strip()
            if not original_sentence:
                continue
            original_lowered = original_sentence.lower()
            mentions_external = any(
                re.search(pattern, original_lowered, flags=re.IGNORECASE)
                for pattern in FORBIDDEN_EXTERNAL_RESOURCE_PATTERNS
            )
            asks_external_action = re.search(FORBIDDEN_EXTERNAL_ACTION_PATTERN, original_lowered, flags=re.IGNORECASE) is not None
            if mentions_external and asks_external_action:
                continue
            sentence = original_sentence
            for pattern in FORBIDDEN_EXTERNAL_RESOURCE_PATTERNS:
                sentence = re.sub(pattern, "", sentence, flags=re.IGNORECASE)
            cleaned_lines.append(sentence)

        result = " ".join(cleaned_lines).strip()
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)

        if not result:
            return self._base_external_policy_line()

        policy_line = self._base_external_policy_line()
        if policy_line.lower() not in result.lower():
            if (
                re.search(FORBIDDEN_EXTERNAL_ACTION_PATTERN, original, flags=re.IGNORECASE)
                and any(re.search(pattern, original, flags=re.IGNORECASE) for pattern in FORBIDDEN_EXTERNAL_RESOURCE_PATTERNS)
            ):
                result = f"{result} {policy_line}".strip()
        return result

    def _base_external_policy_line(self) -> str:
        return (
            "Все ответы и материалы должны оставаться внутри текущего диалога в системе Agent_4K. "
            "Не проси пользователя передавать информацию во внешние ресурсы."
        )


deepseek_client = DeepSeekClient()
