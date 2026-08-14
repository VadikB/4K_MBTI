from __future__ import annotations

import ast
import json
import re
import zlib
from typing import Any

import psycopg
from psycopg.rows import dict_row

from Api.assessment_prompt_resolver import prompt_resolver
from Api.assessment.case_generation.quality import CaseQualityMixin
from Api.assessment.case_generation.personalization import CasePersonalizationMixin
from Api.case_context_builder import build_case_context
from Api.case_text_cleanup import cleanup_case_list, cleanup_case_text, join_case_list
from Api.config import settings

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


class CaseGenerationMixin(CasePersonalizationMixin, CaseQualityMixin):
    def generate_case_prompt(
        self,
        *,
        full_name: str | None,
        user_identifier: str | None = None,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        user_profile: dict[str, Any] | None = None,
        prompt_snapshot: dict[str, Any] | None = None,
        case_type_code: str | None = None,
        case_title: str,
        case_context: str,
        case_task: str,
        case_skills: list[str],
        case_artifact_name: str | None = None,
        case_artifact_description: str | None = None,
        case_required_response_blocks: list[str] | None = None,
        case_skill_evidence: list[dict[str, str]] | None = None,
        case_difficulty_modifiers: list[str] | None = None,
        planned_total_duration_min: int | None = None,
        personalization_variables: str | None = None,
        personalization_map: dict[str, str] | None = None,
        case_specificity: dict[str, Any] | None = None,
        case_generation_system_prompt: str | None = None,
    ) -> str:
        position = self._normalize_profile_text(position, fallback=role_name or "Не указана")
        duties = self._normalize_profile_text(duties, fallback="Не указаны")
        company_industry = self._normalize_profile_text(
            company_industry,
            fallback=str((user_profile or {}).get("company_industry") or (user_profile or {}).get("user_domain") or "Не указана"),
        )
        case_specificity = case_specificity or self.generate_case_specificity(
            position=position,
            duties=duties,
            company_industry=company_industry,
            role_name=role_name,
            user_profile=user_profile,
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=case_context,
            case_task=case_task,
        )
        personalization_map = personalization_map or self.generate_personalization_map(
            full_name=full_name,
            position=position,
            duties=duties,
            company_industry=company_industry,
            role_name=role_name,
            user_profile=user_profile,
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=case_context,
            case_task=case_task,
            planned_total_duration_min=planned_total_duration_min,
            personalization_variables=personalization_variables,
            case_specificity=case_specificity,
        )
        personalized_context = self.apply_personalization(case_context, personalization_map)
        personalized_task = self.apply_personalization(case_task, personalization_map)
        fallback = self._fallback_case_prompt(
            full_name=full_name,
            position=position,
            duties=duties,
            role_name=role_name,
            case_title=case_title,
            case_context=personalized_context,
            case_task=personalized_task,
            case_skills=case_skills,
            case_artifact_name=case_artifact_name,
            case_required_response_blocks=case_required_response_blocks,
            case_skill_evidence=case_skill_evidence,
            personalization_map=personalization_map,
            case_specificity=case_specificity,
        )
        extra_instruction = str(case_generation_system_prompt or "").strip()
        if not extra_instruction and isinstance((prompt_snapshot or {}).get("prompts"), dict):
            extra_instruction = str(
                prompt_resolver.case_generation_instruction(
                    prompt_snapshot,
                    case_type_code=case_type_code,
                )
                or ""
            ).strip()
        if extra_instruction:
            fallback = (
                "Additional case generation system prompt:\n"
                f"{extra_instruction}\n\n"
                f"{fallback}"
            )
        # Prompt generation is the most expensive stage of the pipeline, while the
        # local fallback already contains all required methodical context. Use the
        # local version by default to keep package generation responsive.
        return self.finalize_case_prompt_text_local(
            fallback,
            role_name=role_name,
            planned_total_duration_min=planned_total_duration_min,
        )

    def finalize_case_prompt_text_local(
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
        proofread = self._fallback_proofread_case_prompt_text(sanitized)
        return self._validate_case_prompt_result(proofread, fallback=sanitized)

    def build_personalized_case_materials(
        self,
        *,
        full_name: str | None,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        user_profile: dict[str, Any] | None = None,
        case_type_code: str | None = None,
        case_title: str,
        case_context: str,
        case_task: str,
        planned_total_duration_min: int | None = None,
        personalization_variables: str | None = None,
        case_specificity: dict[str, Any] | None = None,
    ) -> tuple[dict[str, str], str, str]:
        llm_direct_path = self._should_use_llm_user_case_rewrite(case_type_code=case_type_code) and self.enabled
        if llm_direct_path:
            case_specificity = dict(case_specificity or {})
        else:
            case_specificity = case_specificity or self.generate_case_specificity(
                position=position,
                duties=duties,
                company_industry=company_industry,
                role_name=role_name,
                user_profile=user_profile,
                case_type_code=case_type_code,
                case_title=case_title,
                case_context=case_context,
                case_task=case_task,
            )
            case_specificity = dict(case_specificity or {})
        case_specificity["_template_context"] = str(case_context or "")
        case_specificity["_template_task"] = str(case_task or "")
        case_specificity["_case_title"] = str(case_title or "")
        case_specificity["_case_type_code"] = str(case_type_code or "")
        case_specificity["_personalization_variables"] = str(personalization_variables or "")
        if user_profile and not llm_direct_path:
            profile_context = dict(user_profile or {})
            case_frame = build_case_context(
                domain_family=str(
                    (profile_context.get("user_context_vars") or {}).get("domain_family")
                    or (profile_context.get("user_context_vars") or {}).get("domain_code")
                    or profile_context.get("user_domain")
                    or ""
                ),
                case_type_code=case_type_code,
                profile_processes=profile_context.get("user_processes"),
                profile_tasks=profile_context.get("user_tasks"),
                profile_stakeholders=profile_context.get("user_stakeholders"),
                profile_risks=profile_context.get("user_risks"),
                profile_constraints=profile_context.get("user_constraints"),
                profile_systems=profile_context.get("user_systems"),
                profile_artifacts=profile_context.get("user_artifacts"),
                case_specificity=case_specificity,
            )
            case_specificity = self._specialize_specificity_from_case_frame(
                case_specificity,
                case_frame,
                str(
                    (profile_context.get("user_context_vars") or {}).get("domain_family")
                    or (profile_context.get("user_context_vars") or {}).get("domain_code")
                    or profile_context.get("user_domain")
                    or ""
                ),
            )
            case_frame = build_case_context(
                domain_family=str(
                    (profile_context.get("user_context_vars") or {}).get("domain_family")
                    or (profile_context.get("user_context_vars") or {}).get("domain_code")
                    or profile_context.get("user_domain")
                    or ""
                ),
                case_type_code=case_type_code,
                profile_processes=profile_context.get("user_processes"),
                profile_tasks=profile_context.get("user_tasks"),
                profile_stakeholders=profile_context.get("user_stakeholders"),
                profile_risks=profile_context.get("user_risks"),
                profile_constraints=profile_context.get("user_constraints"),
                profile_systems=profile_context.get("user_systems"),
                profile_artifacts=profile_context.get("user_artifacts"),
                case_specificity=case_specificity,
            )
            case_specificity["_case_frame"] = case_frame
        personalization_map: dict[str, str] = {}
        raw_context = case_context
        raw_task = case_task
        if not llm_direct_path:
            personalization_map = self.generate_personalization_map(
                full_name=full_name,
                position=position,
                duties=duties,
                company_industry=company_industry,
                role_name=role_name,
                user_profile=user_profile,
                case_type_code=case_type_code,
                case_title=case_title,
                case_context=case_context,
                case_task=case_task,
                planned_total_duration_min=planned_total_duration_min,
                personalization_variables=personalization_variables,
                case_specificity=case_specificity,
            )
            raw_context = self.apply_personalization(case_context, personalization_map)
            raw_task = self.apply_personalization(case_task, personalization_map)
            case_specificity["_template_context_personalized"] = str(raw_context or "")
            case_specificity["_template_task_personalized"] = str(raw_task or "")
        formatted_context, formatted_task = self._format_user_case_materials(
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=case_context if llm_direct_path else raw_context,
            case_task=case_task if llm_direct_path else raw_task,
            role_name=role_name,
            company_industry=company_industry,
            full_name=full_name,
            position=position,
            duties=duties,
            user_profile=user_profile,
            case_specificity=case_specificity,
        )
        return (
            personalization_map,
            formatted_context,
            formatted_task,
        )

    def build_personalized_case_materials_local_fast(
        self,
        *,
        full_name: str | None,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        user_profile: dict[str, Any] | None = None,
        case_type_code: str | None = None,
        case_title: str,
        case_context: str,
        case_task: str,
        planned_total_duration_min: int | None = None,
        personalization_variables: str | None = None,
    ) -> tuple[dict[str, str], str, str]:
        case_specificity = self._fallback_case_specificity(
            position=position,
            duties=duties,
            company_industry=company_industry,
            role_name=role_name,
            user_profile=user_profile,
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=case_context,
            case_task=case_task,
        )
        placeholders = self._extract_placeholders(
            "\n".join(filter(None, [case_context, case_task, personalization_variables or ""]))
        )
        personalization_map = self._fallback_personalization_map(
            placeholders=placeholders,
            position=position,
            duties=duties,
            company_industry=company_industry,
            role_name=role_name,
            user_profile=user_profile,
            planned_total_duration_min=planned_total_duration_min,
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=case_context,
            case_task=case_task,
            case_specificity=case_specificity,
        )
        raw_context = self.apply_personalization(case_context, personalization_map)
        raw_task = self.apply_personalization(case_task, personalization_map)
        formatted_context, formatted_task = self._format_user_case_materials(
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=raw_context,
            case_task=raw_task,
            role_name=role_name,
            company_industry=company_industry,
            full_name=full_name,
            position=position,
            duties=duties,
            user_profile=user_profile,
            case_specificity=case_specificity,
        )
        return personalization_map, formatted_context, formatted_task








    def build_opening_message(self, *, case_title: str, case_context: str, case_task: str) -> str:
        parts: list[str] = []
        clean_context = (case_context or "").strip()
        clean_task = (case_task or "").strip()
        clean_task = re.sub(r"^(?:Что нужно сделать:\s*)+", "", clean_task, flags=re.IGNORECASE).strip()
        if clean_context:
            parts.append(clean_context)
        if clean_task:
            parts.append(f"Что нужно сделать:\n{clean_task}")
        return "\n\n".join(part for part in parts if part).strip()

    def _resolve_dialog_counterpart_role(
        self,
        *,
        case_title: str,
        case_context: str,
        case_task: str,
    ) -> str:
        task_text = cleanup_case_text(case_task).lower()
        combined_text = cleanup_case_text("\n".join((case_task, case_context, case_title))).lower()

        if any(
            token in task_text
            for token in (
                "с коллег",
                "коллегой",
                "коллега",
                "со специалистом",
                "специалистом",
                "специалист первой линии",
                "первой линии",
                "личный разговор",
                "сложный разговор 1:1",
                "разговор 1:1",
                "вторая линия",
                "второй линии",
                "смежной команды",
                "смежной линии",
                "смежным коллегой",
            )
        ):
            return "peer"

        if any(token in task_text for token in ("с сотрудник", "сотрудником", "подчиненн", "подчинён", "новичк")):
            return "employee"

        if any(token in task_text for token in ("с руководител", "руководителем", "лидером", "менеджером")):
            return "manager"

        if any(token in task_text for token in ("стейкхолдер", "смежн", "согласовать", "договориться со смежной")):
            return "stakeholder"

        if any(
            token in task_text
            for token in (
                "ответьте пользователю",
                "ответить пользователю",
                "ответ пользователю",
                "ответьте клиенту",
                "ответить клиенту",
                "диалог с клиент",
                "разговор с клиент",
                "разговор с пользовател",
                "разговор с заказчик",
                "ответ в рабочем чате",
            )
        ):
            return "client"

        if any(token in combined_text for token in ("коллег", "смен", "вторая линия", "смежн")):
            return "peer"
        if any(token in combined_text for token in ("сотрудник", "подчиненн", "подчинён", "новичк", "развивающ")):
            return "employee"
        if any(token in combined_text for token in ("руковод", "лидер")):
            return "manager"
        if any(token in combined_text for token in ("стейкхолдер", "смежная сторона", "смежный отдел", "смежная команда")):
            return "stakeholder"
        if any(token in combined_text for token in ("клиент", "пользоват", "заказчик", "заявител")):
            return "client"
        return "generic"

    def build_dialog_counterpart_opening_message(
        self,
        *,
        case_title: str,
        case_context: str,
        case_task: str,
        interactivity_mode: str | None,
    ) -> str:
        source_text = "\n".join(
            part.strip()
            for part in (case_context, case_task, case_title)
            if str(part or "").strip()
        )
        if not self._is_dialog_interactivity_mode(interactivity_mode):
            task_text = cleanup_case_text(case_task).strip()
            normalized_task = task_text.lower()
            if "ответ" in normalized_task and ("клиент" in normalized_task or "пользоват" in normalized_task):
                return "Какой ответ вы дадите пользователю в этой ситуации?"
            if "вопрос" in normalized_task or "уточ" in normalized_task:
                return "Какие вопросы вы зададите в первую очередь, чтобы прояснить ситуацию?"
            if "приоритет" in normalized_task or "распред" in normalized_task:
                return "Как вы определите первый приоритет и что возьмете в работу сначала?"
            if "причин" in normalized_task or "разоб" in normalized_task:
                return "С чего вы начнете разбор этой ситуации и что захотите проверить первым?"
            if "иде" in normalized_task or "улучш" in normalized_task:
                return "Какое решение вы предложите по этой ситуации и почему начнете именно с него?"
            return "Как вы начнете действовать в этой ситуации?"

        counterpart_role = self._resolve_dialog_counterpart_role(
            case_title=case_title,
            case_context=case_context,
            case_task=case_task,
        )
        quote_match = re.search(r"[«\"]([^»\"]{12,280})[»\"]", source_text)
        if counterpart_role == "client" and quote_match:
            return cleanup_case_text(quote_match.group(1)).strip()

        if counterpart_role == "peer":
            return (
                "Да, вижу, что между нами как коллегами по этой передаче уже накопилось напряжение. "
                "Давай спокойно разберем: что именно в этой ситуации для тебя стало самым проблемным?"
            )
        if counterpart_role == "employee":
            return (
                "Я готов обсудить ситуацию спокойно и по делу. "
                "Скажите прямо: что именно сейчас вы хотите от меня прояснить в первую очередь?"
            )
        if counterpart_role == "manager":
            return (
                "Давайте обсудим это предметно. "
                "Что именно в текущей ситуации вы считаете главным вопросом для договоренности?"
            )
        if counterpart_role == "stakeholder":
            return (
                "Со своей стороны я вижу ограничения и другой приоритет по нагрузке. "
                "Что для вас в этой ситуации критично обсудить в первую очередь?"
            )
        if quote_match:
            return cleanup_case_text(quote_match.group(1)).strip()

        normalized = source_text.lower()
        if "коллег" in normalized or "смен" in normalized:
            return (
                "Слушай, у меня правда был завал, и я перекинул это дальше без нормального комментария. "
                "Давай сразу по делу: что именно в этой передаче тебя больше всего выбило?"
            )
        if "клиент" in normalized:
            return (
                "Честно, меня эта ситуация уже раздражает: вопрос вроде закрыли, а по факту ничего не решилось. "
                "Объясните, что у вас сейчас происходит."
            )
        if "руковод" in normalized or "лидер" in normalized:
            return (
                "Я вижу, что по этой теме у нас уже накапливается напряжение. "
                "Давайте проговорим прямо: что именно сейчас требует отдельной договоренности?"
            )
        if "смеж" in normalized or "стейкхолдер" in normalized:
            return (
                "Со своей стороны скажу честно: у нас сейчас другой приоритет, и быстро подстроиться под ваш запрос не получится. "
                "Что для вас в этой ситуации критично в первую очередь?"
            )
        return (
            "Давайте начнем прямо с сути. "
            "Что именно в этой ситуации вы хотите обсудить со мной в первую очередь?"
        )

    def split_user_case_message(self, text: str) -> tuple[str, str]:
        value = str(text or "").strip()
        if not value:
            return "", ""

        normalized = value
        task_match = re.search(
            r"(?:^|\n)\s*(?:\*\*Что нужно сделать\*\*|Что нужно сделать:)\s*:?\s*([\s\S]+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if task_match:
            context = self._strip_generic_role_intro_before_real_scene(normalized[:task_match.start()].strip())
            task = cleanup_case_text(task_match.group(1)).strip()
            task = re.sub(r"^(?:(?:\*\*Что нужно сделать\*\*|Что нужно сделать:)\s*:?\s*)+", "", task, flags=re.IGNORECASE).strip()
            return context, task

        if "\n\n" in normalized:
            context, task = normalized.rsplit("\n\n", 1)
            if not re.search(r"(?:^|\n)\s*(?:\*\*Ситуация\*\*|Ситуация:?|\*\*Что известно\*\*|\*\*Что ограничивает\*\*)", task, flags=re.IGNORECASE):
                return self._strip_generic_role_intro_before_real_scene(context.strip()), cleanup_case_text(task).strip()

        return self._strip_generic_role_intro_before_real_scene(normalized), ""

    def _strip_generic_role_intro_before_real_scene(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        second_scene_match = re.search(
            r"\n\s*(?:\*\*Ситуация\*\*|Ситуация:)\s*",
            value,
            flags=re.IGNORECASE,
        )
        if not second_scene_match:
            return value

        prelude = value[:second_scene_match.start()].strip()
        real_scene = value[second_scene_match.start():].lstrip()
        if not prelude or not real_scene:
            return value

        prelude_body = re.sub(r"^\s*\*\*Ситуация\*\*\s*", "", prelude, count=1, flags=re.IGNORECASE).strip()
        prelude_body = re.sub(r"^\s*Ситуация\s*\n?", "", prelude_body, count=1, flags=re.IGNORECASE).strip()
        if not prelude_body:
            return value

        first_paragraph = re.split(r"\n\s*\n", prelude_body, maxsplit=1)[0].strip()
        if not first_paragraph:
            return value

        is_role_passport = bool(
            re.match(r"^Вы\s*[—-]", first_paragraph)
            and re.search(
                r"\b(отвечаете|управляете|обрабатываете|диагностируете|устанавливаете|настраиваете|курируете|развиваете|ведете|ведёте|руководите|работаете)\b",
                first_paragraph,
                flags=re.IGNORECASE,
            )
        )
        if not is_role_passport:
            return value

        return real_scene

    def _fallback_case_prompt(
        self,
        *,
        full_name: str | None,
        position: str | None,
        duties: str | None,
        role_name: str | None,
        case_title: str,
        case_context: str,
        case_task: str,
        case_skills: list[str],
        case_artifact_name: str | None,
        case_required_response_blocks: list[str] | None,
        case_skill_evidence: list[dict[str, str]] | None,
        personalization_map: dict[str, str],
        case_specificity: dict[str, Any] | None,
    ) -> str:
        blocks_text = ", ".join(case_required_response_blocks or []) or "не указаны"
        evidence_text = "; ".join(
            f"{item.get('skill_code') or item.get('skill_name')}: {item.get('expected_signal') or item.get('evidence_description')}"
            for item in (case_skill_evidence or [])
            if isinstance(item, dict)
        ) or "не указаны"
        return (
            "Ты агент Интервьюер в системе Agent_4K. "
            f"Проводишь интервью по кейсу «{case_title}» для пользователя {full_name or 'без имени'}. "
            f"Роль: {role_name or 'не определена'}. "
            f"Должность: {position or 'не указана'}. "
            f"Обязанности: {duties or 'не указаны'}. "
            f"Контекст кейса: {case_context}. "
            f"Задача пользователя: {case_task}. "
            f"Навыки для оценки: {', '.join(case_skills) if case_skills else 'не указаны'}. "
            f"Ожидаемый артефакт ответа: {case_artifact_name or 'не указан'}. "
            f"Обязательные блоки ответа: {blocks_text}. "
            f"Ключевые сигналы навыков: {evidence_text}. "
            f"Ключевые параметры кейса: {self._summarize_personalization_map(personalization_map)}. "
            f"Контекстная конкретика кейса: {self._summarize_case_specificity(case_specificity)}. "
            "Веди диалог профессионально, работай как интервьюер. "
            "Твоя главная опора — сценарий и логика самого кейса. "
            "Задавай по одному уточняющему вопросу за ход и веди пользователя по сценарию этой ситуации: уточняй, как он понимает обстановку, что собирается делать, на что опирается и как будет действовать дальше в рамках кейса. "
            "Не превращай интервью в чек-лист из обязательных блоков, навыков или критериев оценки. "
            "Все служебные поля про артефакт, блоки ответа и сигналы навыков используй только внутренне для оценки, но не раскрывай их пользователю и не превращай в подсказки. "
            "Не подсказывай структуру ответа, правильные шаги, готовые варианты решения, ожидаемые метрики, список рисков или нужных участников, если пользователь сам этого еще не назвал. "
            "Если нужно уточнение, спрашивай через контекст кейса и последствия в этой ситуации, а не через методические формулировки. "
            "Не проси пользователя передавать данные или материалы во внешние ресурсы, мессенджеры, почту, облачные документы, CRM или сайты. "
            "Все ответы должны оставаться внутри текущего интервью в системе Agent_4K. "
            "Не завершай кейс самостоятельно. Ты только ведешь интервью, задаешь уточняющие вопросы по сценарию кейса и записываешь ответы пользователя. "
            "Завершение кейса происходит только по кнопке завершения или по тайм-ауту."
        )





























































    def _compose_decision_case_context(self, specificity: dict[str, Any]) -> str:
        frame = self._build_specificity_case_frame(specificity)
        workflow = frame["workflow"]
        stages = self._join_case_items((specificity.get("stage_names") or [])[:3])
        impact = cleanup_case_text(str(frame.get("impact") or "сроки и качество результата"))
        source_of_truth = cleanup_case_text(str(frame.get("source_of_truth") or "внутренним данным"))
        issue_summary = cleanup_case_text(str(specificity.get("issue_summary") or frame.get("problem_event") or "").strip())
        decision_theme = cleanup_case_text(str(specificity.get("decision_theme") or frame.get("expected_step") or "").strip())
        work_items = cleanup_case_text(str(frame.get("work_items") or "").strip())
        named_stakeholders = cleanup_case_text(str(frame.get("participants") or specificity.get("stakeholder_named_list") or "").strip())
        horeca_markers = self._domain_family_markers().get("horeca", ())
        horeca_source = " ".join(
            [
                frame["workflow"],
                str(specificity.get("system_name") or ""),
                source_of_truth,
                self._join_case_items((specificity.get("ticket_titles") or [])[:3]),
            ]
        ).lower()
        if any(marker in horeca_source for marker in horeca_markers):
            problem_intro = issue_summary or "по спорной ситуации с гостем не совпадают картина по заказу, замечанию и подтвержденному результату"
            return (
                f"Возникла конкретная проблема: {problem_intro}. "
                + (f"В ситуации уже участвуют {named_stakeholders}. " if named_stakeholders else "")
                + (f"Сейчас в фокусе такие позиции: {work_items}. " if work_items else "")
                + (f"Нужно принять решение: {decision_theme}. " if decision_theme else "")
                + "По данным смены вопрос уже можно считать закрытым, но по журналу и комментариям видно, что результат для гостя не подтвержден, а следующий шаг не зафиксирован. "
                + f"Если поторопиться, пострадают {impact}. Если затянуть решение, напряжение в смене и риск повторной жалобы только вырастут."
            )
        problem_intro = issue_summary or (
            f"по процессу «{workflow}» нет единой картины, можно ли двигать результат дальше или сначала нужно закрыть несоответствие"
        )
        sentence = (
            f"Нужно принять решение по ситуации: {problem_intro}. "
            + (f"По ситуации уже вовлечены {named_stakeholders}. " if named_stakeholders else "")
            + (f"Сейчас в фокусе {work_items}. " if work_items else "")
            + (f"Ключевой вопрос сейчас такой: {decision_theme}. " if decision_theme else "")
            + f"Проверить факты можно по {source_of_truth}. "
            + f"Часть данных говорит, что ситуацию можно двигать дальше, но часть информации еще не подтверждена. "
            f"Если поторопиться, возможны ошибка и повторная переделка. Если затянуть решение, пострадают {impact}."
        )
        if stages:
            sentence += f" Спор возникает вокруг этапов: {stages}."
        else:
            sentence += f" Проверять приходится по {source_of_truth}."
        return sentence




    def _compose_control_risk_case_context(self, specificity: dict[str, Any]) -> str:
        frame = self._build_specificity_case_frame(specificity)
        stages = self._join_case_items((specificity.get("stage_names") or [])[:3])
        variant = self._diversity_variant(
            case_type_code="F11",
            case_title=str(specificity.get("_case_title") or ""),
            specificity=specificity,
            variants=3,
        )
        horeca_markers = self._domain_family_markers().get("horeca", ())
        horeca_source = " ".join(
            [
                frame["workflow"],
                str(specificity.get("system_name") or ""),
                frame["source_of_truth"],
                self._join_case_items((specificity.get("ticket_titles") or [])[:3]),
            ]
        ).lower()
        if any(marker in horeca_source for marker in horeca_markers):
            sentence = (
                "Перед закрытием спорной ситуации по гостю обнаружилось несоответствие: вопрос уже хотят считать решенным, "
                "но замечание по заказу или подтверждение результата еще не зафиксированы полностью. "
                f"Если закрыть ситуацию в таком виде, пострадают {frame['impact']}, а следующая смена получит неполную картину."
            )
            if stages:
                sentence += f" Под вопросом остаются шаги: {stages}."
            else:
                sentence += f" Ключевой незакрытый момент — {frame['critical_step']}."
            return sentence
        if variant == 1:
            sentence = (
                f"Перед передачей результата на следующий этап по процессу {frame['workflow']} всплыло несоответствие по {frame['work_object']}: "
                f"{frame['problem_event']}. Если передать результат в таком виде, пострадают {frame['impact']}."
            )
        elif variant == 2:
            sentence = (
                f"На стыке следующего этапа по процессу {frame['workflow']} обнаружилось расхождение по {frame['work_object']}: "
                f"{frame['problem_event']}. Если пропустить это дальше, пострадают {frame['impact']}."
            )
        else:
            sentence = (
                f"Перед следующим этапом работы по процессу {frame['workflow']} обнаружилось несоответствие по {frame['work_object']}: "
                f"{frame['problem_event']}. Если передать результат в таком виде, пострадают {frame['impact']}."
            )
        if frame["current_state_inline"]:
            sentence += f" Сейчас картина выглядит так: {frame['current_state_inline']}."
        if frame["source_of_truth"]:
            sentence += f" Проверять расхождение приходится по данным из {frame['source_of_truth']}."
        if frame["bottleneck"]:
            sentence += f" Ключевая проблема сейчас в том, что {frame['bottleneck']}."
        if stages:
            sentence += f" Под вопросом остаются этапы: {stages}."
        else:
            sentence += f" Ключевой незакрытый момент — {frame['critical_step']}."
        sentence += f" При этом {frame['constraint']}."
        sentence += f" Если ошибиться, {frame['risk']}."
        return sentence

































    def _summarize_case_specificity(self, values: dict[str, Any] | None) -> str:
        if not isinstance(values, dict):
            return "не указана"
        parts: list[str] = []
        for key in ("workflow_label", "system_name", "channel", "source_of_truth", "request_type", "idea_label"):
            value = self._sanitize_personalization_value(str(values.get(key) or ""))
            if value:
                parts.append(f"{key}: {value}")
        ticket_titles = values.get("ticket_titles") or []
        if isinstance(ticket_titles, list) and ticket_titles:
            parts.append(f"ticket_titles: {', '.join(str(item) for item in ticket_titles[:3])}")
        stage_names = values.get("stage_names") or []
        if isinstance(stage_names, list) and stage_names:
            parts.append(f"stage_names: {', '.join(str(item) for item in stage_names[:4])}")
        return "; ".join(parts) if parts else "не указана"













    def _normalize_profile_text(self, value: str | None, *, fallback: str) -> str:
        cleaned = (value or "").strip()
        lowered = cleaned.lower()
        if not cleaned or lowered in {"изменений нет", "нет изменений", "нет измеенний", "не изменилось", "не изменений", "без изменений"}:
            return fallback
        return cleaned



    def _format_user_case_materials(
        self,
        *,
        case_type_code: str | None,
        case_title: str,
        case_context: str,
        case_task: str,
        role_name: str | None,
        company_industry: str | None,
        full_name: str | None = None,
        position: str | None = None,
        duties: str | None = None,
        user_profile: dict[str, Any] | None = None,
        case_specificity: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        raw_template_task = str(case_task or "").strip()
        if self._should_use_llm_user_case_rewrite(case_type_code=case_type_code) and self.enabled:
            source_context = str(case_context or "")
            source_task = str(case_task or "") or raw_template_task
            rewritten_context, rewritten_task = self._rewrite_user_case_materials_with_llm(
                case_title=case_title,
                case_type_code=case_type_code,
                case_context=source_context,
                case_task=source_task,
                role_name=role_name,
                full_name=full_name,
                position=position,
                duties=duties,
                company_industry=company_industry,
                user_profile=user_profile,
            )
            return rewritten_context, rewritten_task

        normalized_context = cleanup_case_text(self._sanitize_user_case_text(case_context, role_name=role_name))
        normalized_task = cleanup_case_text(self._sanitize_user_case_task(case_task))

        bypass_locked_context = self._should_bypass_template_locked_context(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )
        use_strict_scene_narrative = self._should_use_strict_scene_narrative(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )
        prefer_template_context = self._should_prefer_template_context(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )

        context_text, constraints_text = self._extract_user_case_constraints(normalized_context)
        context_text = self._polish_user_case_context(
            context_text,
            role_name=role_name,
            case_title=case_title,
            company_industry=company_industry,
        )
        context_text = self._inject_case_concreteness(
            context_text,
            case_title=case_title,
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )
        context_text = self._apply_plot_skeleton(
            context_text,
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        locked_context = self._build_template_locked_context(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )
        if locked_context and not bypass_locked_context:
            context_text = self._light_polish_template_locked_context(locked_context, role_name=role_name)
        constraints_text = self._polish_user_case_constraints(constraints_text, role_name=role_name)
        user_text_template = self._get_user_text_template(case_type_code)
        if user_text_template:
            context_text, task_text = self._apply_user_text_template(
                template=user_text_template,
                context_text=context_text,
                fallback_task=normalized_task,
                case_title=case_title,
                case_specificity=case_specificity,
            )
        else:
            task_text = self._polish_user_case_task(
                normalized_task,
                case_title=case_title,
                context_text=context_text,
                case_type_code=case_type_code,
            )

        if not context_text and case_title:
            context_text = case_title.strip()

        final_context = self._build_structured_user_case_context(
            context_text=context_text,
            case_specificity=case_specificity,
        )

        final_context = self._sanitize_user_case_text(final_context, role_name=role_name)
        final_context, _ = self._extract_user_case_constraints(final_context)
        final_context = self._polish_user_case_context(
            final_context,
            role_name=role_name,
            case_title=case_title,
            company_industry=company_industry,
        )
        if use_strict_scene_narrative:
            strict_context = self._build_strict_scene_narrative(
                case_type_code=case_type_code,
                case_specificity=case_specificity,
            )
            if strict_context:
                final_context = strict_context
            elif prefer_template_context and locked_context and not bypass_locked_context:
                final_context = self._light_polish_template_locked_context(locked_context, role_name=role_name)
        else:
            final_context = self._inject_case_concreteness(
                final_context,
                case_title=case_title,
                case_type_code=case_type_code,
                case_specificity=case_specificity,
            )
            final_context = self._apply_plot_skeleton(
                final_context,
                case_type_code=case_type_code,
                case_title=case_title,
                case_specificity=case_specificity,
            )
            locked_context = self._build_template_locked_context(
                case_type_code=case_type_code,
                case_specificity=case_specificity,
            )
            if locked_context and not bypass_locked_context and not use_strict_scene_narrative:
                final_context = self._light_polish_template_locked_context(locked_context, role_name=role_name)
        if prefer_template_context and locked_context and not bypass_locked_context and not use_strict_scene_narrative:
            final_context = self._light_polish_template_locked_context(locked_context, role_name=role_name)
        final_context, task_text = self._enforce_template_fidelity(
            case_type_code=case_type_code,
            context_text=final_context,
            task_text=task_text,
            case_specificity=case_specificity,
        )
        final_context, task_text = self._inject_case_id_prompt_details(
            final_context,
            task_text,
            case_specificity=case_specificity,
        )
        final_context = self._build_structured_user_case_context(
            context_text=final_context,
            case_specificity=case_specificity,
        )
        final_context = self._restore_minimum_case_context(
            final_context,
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        task_text = self._sanitize_user_case_task(task_text)
        if user_text_template:
            task_text = str(user_text_template.get("question_text") or task_text).strip()
        else:
            task_text = self._polish_user_case_task(
                task_text,
                case_title=case_title,
                context_text=final_context,
                case_type_code=case_type_code,
            )
        final_context, task_text = self._enforce_template_fidelity(
            case_type_code=case_type_code,
            context_text=final_context,
            task_text=task_text,
            case_specificity=case_specificity,
        )
        final_context, task_text = self._inject_case_id_prompt_details(
            final_context,
            task_text,
            case_specificity=case_specificity,
        )
        final_context = self._proofread_user_case_text(
            cleanup_case_text(final_context),
            role_name=role_name,
            is_task=False,
            case_type_code=case_type_code,
        )
        task_text = self._proofread_user_case_text(
            cleanup_case_text(task_text),
            role_name=role_name,
            is_task=True,
            case_type_code=case_type_code,
        )
        final_contract = self._build_template_contract(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )
        final_required_task = cleanup_case_text(final_contract.get("required_task_text", ""))
        user_visible_task = self._build_user_visible_case_task(
            case_type_code=case_type_code,
            context_text=final_context,
            case_title=case_title,
        )
        if str(case_type_code or "").strip().upper() in {"F01", "F02", "F03", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"} and user_visible_task:
            task_text = self._proofread_user_case_text(
                user_visible_task,
                role_name=role_name,
                is_task=True,
                case_type_code=case_type_code,
            )
        return final_context.strip(), task_text.strip()

    def _should_use_llm_user_case_rewrite(self, *, case_type_code: str | None) -> bool:
        instruction = self._get_case_text_build_instruction(case_type_code)
        if not isinstance(instruction, dict):
            return False
        return bool(str(instruction.get("instruction_text") or "").strip())

























    def _sanitize_user_case_task(self, text: str | None) -> str:
        result = str(text or "").strip()
        if not result:
            return ""
        result = result.replace("Ответьте клиенту в этой ситуации.", "Подготовьте ответ клиенту.")
        result = result.replace("Подготовьте ответ клиенту в этой ситуации.", "Подготовьте ответ клиенту.")
        result = result.replace("Подготовьте ответ заказчику в этой ситуации.", "Подготовьте ответ заказчику.")
        result = re.sub(r"\bответьте\b", "Подготовьте ответ", result, flags=re.IGNORECASE)
        result = re.sub(r"\bподготовьте короткое сообщение или тикет\b", "Подготовьте короткий и понятный ответ", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)
        if result and result[-1] not in ".!?":
            result += "."
        return result.strip()

    def _extract_user_case_constraints(self, text: str) -> tuple[str, str]:
        context = (text or "").strip()
        constraints_parts: list[str] = []
        if not context:
            return "", ""

        if "Ограничения:" in context:
            head, tail = context.split("Ограничения:", 1)
            context = head.strip()
            tail = tail.strip()
            if tail:
                constraints_parts.append(tail)

        sentences = re.split(r"(?<=[.!?])\s+", context)
        kept_sentences: list[str] = []
        for sentence in sentences:
            clean = sentence.strip()
            lowered = clean.lower()
            if not clean:
                continue
            if any(
                marker in lowered
                for marker in (
                    "не можете",
                    "не может",
                    "нельзя",
                    "в рамках регламента",
                    "в рамках своих полномочий",
                    "в рамках полномочий",
                    "не должны",
                    "не должен",
                    "не вправе",
                )
            ):
                constraints_parts.append(clean)
                continue
            kept_sentences.append(clean)

        constraints_text = " ".join(part.strip() for part in constraints_parts if part.strip())
        cleaned_context = " ".join(kept_sentences).strip()
        return cleaned_context, constraints_text


    def _get_user_text_template(self, case_type_code: str | None) -> dict[str, Any] | None:
        code = str(case_type_code or "").strip().upper()
        if not code:
            return None
        if code in self._user_text_template_cache:
            return self._user_text_template_cache[code]
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
                    SELECT type_code, template_name, structure_mode, action_prompt, question_text,
                           allow_direct_speech, industry_context_mode, is_active, version
                    FROM case_user_text_templates
                    WHERE type_code = %s
                      AND is_active = TRUE
                    """,
                    (code,),
                ).fetchone()
        except Exception:
            row = None
        template = dict(row) if row else None
        self._user_text_template_cache[code] = template
        return template

    def _apply_user_text_template(
        self,
        *,
        template: dict[str, Any],
        context_text: str,
        fallback_task: str,
        case_title: str,
        case_specificity: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        structure_mode = str(template.get("structure_mode") or "").strip().lower()
        action_prompt = str(template.get("action_prompt") or "").strip()
        question_text = str(template.get("question_text") or fallback_task).strip()
        if structure_mode == "clarification" and fallback_task:
            lowered_fallback = fallback_task.lower()
            if "уточн" in lowered_fallback or "зафиксиру" in lowered_fallback:
                question_text = fallback_task.strip()

        builders = {
            "complaint": self._reshape_complaint_case_context,
            "clarification": self._reshape_clarification_case_context,
            "conversation": self._reshape_conversation_case_context,
            "alignment": self._reshape_alignment_case_context,
            "planning": self._reshape_planning_case_context,
            "incident_review": self._reshape_incident_case_context,
            "decision": self._reshape_decision_case_context,
            "prioritization": self._reshape_priority_case_context,
            "improvement": self._reshape_improvement_case_context,
            "idea_evaluation": self._reshape_idea_evaluation_case_context,
            "control_risk": self._reshape_control_risk_case_context,
            "development_conversation": self._reshape_development_conversation_case_context,
            "change_management": self._reshape_change_management_case_context,
            "experiment_design": self._reshape_experiment_design_case_context,
            "reframing": self._reshape_reframing_case_context,
        }
        builder = builders.get(structure_mode)
        base_context = (context_text or "").strip()
        preserve_scene_context = self._should_preserve_scene_driven_context(
            structure_mode=structure_mode,
            case_specificity=case_specificity,
        )
        if not base_context and builder:
            base_context = builder(context_text, case_title=case_title)
        elif builder and not preserve_scene_context:
            base_context = builder(base_context, case_title=case_title)
        final_context = self._order_user_case_context(base_context, structure_mode=structure_mode)
        if action_prompt:
            action_prompt = action_prompt.format(
                recipient=self._resolve_user_text_recipient(structure_mode=structure_mode, case_title=case_title, context_text=final_context),
                counterparty=self._resolve_user_text_counterparty(structure_mode=structure_mode, case_title=case_title, context_text=final_context),
                goal=self._resolve_user_text_goal(structure_mode=structure_mode, case_title=case_title, context_text=final_context),
            ).strip()
        final_context = self._order_user_case_context(final_context, structure_mode=structure_mode)
        return final_context, question_text

    def _should_preserve_scene_driven_context(
        self,
        *,
        structure_mode: str | None,
        case_specificity: dict[str, Any] | None,
    ) -> bool:
        mode = str(structure_mode or "").strip().lower()
        if mode not in {
            "clarification",
            "conversation",
            "planning",
            "prioritization",
            "improvement",
            "idea_evaluation",
            "control_risk",
            "development_conversation",
        }:
            return False
        specificity = dict(case_specificity or {})
        family = self._infer_specificity_domain_family(specificity)
        situation_code = str((specificity.get("_case_frame") or {}).get("situation_code") or "").strip().lower()
        return family == "learning_and_development" and situation_code.startswith("lnd_")

    def _order_user_case_context(self, text: str, *, structure_mode: str) -> str:
        clean = (text or "").strip()
        if not clean:
            return ""

        if structure_mode == "complaint":
            return self._order_complaint_case_context(clean)

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip()]
        if not sentences:
            return clean

        action_prefixes = ("Вам нужно", "Нужно ")
        action_sentences: list[str] = []
        description_sentences: list[str] = []
        for sentence in sentences:
            if any(sentence.startswith(prefix) for prefix in action_prefixes):
                action_sentences.append(sentence)
            else:
                description_sentences.append(sentence)

        description_block = " ".join(description_sentences).strip()
        action_block = " ".join(action_sentences).strip()

        parts: list[str] = []
        if description_block:
            parts.append(description_block)
        if action_block:
            parts.append(action_block)
        return "\n\n".join(part for part in parts if part).strip()

    def _order_complaint_case_context(self, text: str) -> str:
        clean = re.sub(r"(?m)^\s*-\s.*$", "", (text or "").strip())
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        if not clean:
            return ""

        quote_match = re.search(r"«[^»]+»", clean)
        quote_block = quote_match.group(0).strip() if quote_match else ""

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", clean) if part.strip()]
        if not sentences:
            return clean

        internal_sentences: list[str] = []
        action_sentences: list[str] = []
        fallback_sentences: list[str] = []

        skip_markers = (
            "вы работаете как",
            "у вас есть доступ",
            "id обращения",
            "канал:",
            "ориентир по сроку",
            "время жалобы",
            "что видно в системе",
            "что осталось нерешённым",
            "что осталось нерешенным",
            "последствие для клиента",
            "оцениваемый",
            "инициатор жалобы",
            "возможный смежник",
            "возможная эскалация",
            "внешний клиент написал",
            "по его словам",
        )
        internal_markers = (
            "в jira видно",
            "во внутренних данных видно",
            "из внутренних данных видно",
            "из текущих данных",
            "следующий шаг",
            "статус задачи уже изменён",
            "статус задачи уже изменен",
            "статус обращения уже изменён",
            "статус обращения уже изменен",
        )

        for sentence in sentences:
            lowered = sentence.lower()
            if any(marker in lowered for marker in skip_markers):
                continue
            if sentence.startswith("Сейчас от вас ждут"):
                action_sentences.append(sentence)
                continue
            if any(marker in lowered for marker in internal_markers):
                internal_sentences.append(sentence)
                continue
            if quote_block and quote_block in sentence:
                continue
            fallback_sentences.append(sentence)

        parts: list[str] = []
        if quote_block:
            if "заказчик пишет" in clean.lower():
                parts.append(f"Во второй половине дня заказчик пишет: {quote_block}")
            elif "клиент" in clean.lower():
                parts.append(f"Во второй половине дня клиент пишет: {quote_block}")
            else:
                parts.append(quote_block)
        if internal_sentences:
            parts.append(internal_sentences[0])
        elif fallback_sentences:
            parts.append(fallback_sentences[0])
        if action_sentences:
            parts.append(action_sentences[0])
        elif len(fallback_sentences) > 1:
            parts.append(fallback_sentences[1])

        if not parts:
            parts = fallback_sentences[:2] or sentences[:2]

        assembled = "\n\n".join(part.strip() for part in parts if part.strip()).strip()
        if quote_block:
            quote_plain = quote_block.strip("«»")
            quote_tail_parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", quote_plain) if part.strip()]
            quote_tail = quote_tail_parts[-1] if quote_tail_parts else quote_plain
            before, sep, after = assembled.partition(quote_block)
            if sep:
                after = after.replace(quote_plain, "")
                after = after.replace(quote_tail, "")
                after = after.replace("»", "")
                after = re.sub(r"\s{2,}", " ", after).strip()
                assembled = f"{before}{sep}"
                if after:
                    assembled = f"{assembled} {after}".strip()
        assembled = re.sub(r"\s{2,}", " ", assembled).strip()
        return assembled

    def _resolve_user_text_recipient(self, *, structure_mode: str, case_title: str, context_text: str) -> str:
        source = f"{structure_mode} {case_title} {context_text}".lower()
        if any(word in source for word in ("jira", "тз", "требован", "разработ", "заказчик")):
            return "заказчику"
        return "клиенту"

    def _resolve_user_text_counterparty(self, *, structure_mode: str, case_title: str, context_text: str) -> str:
        source = f"{structure_mode} {case_title} {context_text}".lower()
        if "сотрудник" in source or structure_mode == "development_conversation":
            return "сотрудником"
        return "коллегой"

    def _resolve_user_text_goal(self, *, structure_mode: str, case_title: str, context_text: str) -> str:
        source = f"{structure_mode} {case_title} {context_text}".lower()
        if structure_mode == "development_conversation":
            return "обозначить проблему, договориться о следующем шаге и снизить риск повторения этого паттерна"
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return "договориться о более понятном порядке передачи задач в работу и избежать повторения таких сбоев"
        return "договориться о более понятном порядке работы и избежать повторения таких сбоев"

    def _polish_user_case_constraints(self, text: str, *, role_name: str | None) -> str:
        result = (text or "").strip()
        if not result:
            return ""

        human_role = self._humanize_role_name(role_name)
        replacements = {
            "ответ не должен выходить за регламент и полномочия": "не выходите за рамки регламента и своих полномочий",
            "ответ должен показать не только реакцию, но и организацию следующего шага": "в ответе важно не только отреагировать на ситуацию, но и обозначить следующий шаг",
            "не должен выходить за регламент и полномочия": "не выходите за рамки регламента и своих полномочий",
        }
        for source, target in replacements.items():
            result = result.replace(source, target)

        result = re.sub(r"\bдля\s+управленческой\s+роли\b", "для вашей роли", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдля\s+роли\s+исполнителя\b", "для вашей роли", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв роли\s+(?:линейный сотрудник|менеджер|лидер)\b", f"как {human_role}", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result).strip()
        if result and result[-1] not in ".!?":
            result += "."
        return result



    def _get_case_id_prompt_rule(self, case_specificity: dict[str, Any] | None) -> dict[str, Any]:
        return {}

    def _resolve_case_rule_concrete_value(
        self,
        *,
        render_kind: str,
        field_code: str,
        case_specificity: dict[str, Any] | None,
        contract: dict[str, str],
    ) -> str:
        specificity = dict(case_specificity or {})
        frame = dict(specificity.get("_case_frame") or {})
        normalized_code = str(field_code or "").strip().lower()

        candidates: tuple[str, ...]
        if render_kind == "idea":
            candidates = (
                str(specificity.get("idea_label") or ""),
                str(frame.get("idea_label") or ""),
                str(specificity.get("idea_description") or ""),
            )
        elif render_kind == "deadline":
            candidates = (
                cleanup_case_text(contract.get("deadline") or ""),
                str(frame.get("deadline") or ""),
                str(specificity.get("deadline") or ""),
            )
        elif render_kind == "criteria":
            candidates = (
                str(specificity.get("business_criteria") or ""),
                str(frame.get("business_criteria") or ""),
                str(specificity.get("metric_context") or ""),
            )
        elif render_kind == "effect":
            candidates = (
                str(specificity.get("business_impact") or ""),
                str(frame.get("risk") or ""),
                str(frame.get("stakes") or ""),
            )
        elif render_kind == "resource":
            candidates = (
                str(specificity.get("resource_profile") or ""),
                str(frame.get("resource_profile") or ""),
                str(contract.get("constraint") or ""),
            )
        elif render_kind == "channel":
            candidates = (
                str(frame.get("channel") or ""),
                str(specificity.get("channel") or ""),
            )
        elif render_kind == "task_name":
            candidates = (
                str(frame.get("work_items") or ""),
                str(specificity.get("workflow_label") or ""),
                str(frame.get("expected_step") or ""),
                str(specificity.get("critical_step") or ""),
            )
        elif render_kind == "stakeholder":
            candidates = (
                str(frame.get("participants") or ""),
                str(specificity.get("stakeholder_named_list") or ""),
                str(frame.get("stakeholder") or ""),
                str(specificity.get("primary_stakeholder") or ""),
            )
        else:
            candidates = (
                str(frame.get(normalized_code) or ""),
                str(specificity.get(normalized_code) or ""),
            )

        for value in candidates:
            if render_kind == "stakeholder" and isinstance(value, str):
                stripped = value.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    try:
                        parsed = ast.literal_eval(stripped)
                    except Exception:
                        parsed = None
                    if isinstance(parsed, (list, tuple, set)):
                        joined = ", ".join(
                            cleanup_case_text(str(item or "")).strip()
                            for item in parsed
                            if cleanup_case_text(str(item or "")).strip()
                        )
                        cleaned = cleanup_case_text(joined).strip()
                        if cleaned:
                            return cleaned
            if isinstance(value, (list, tuple, set)):
                joined = ", ".join(cleanup_case_text(str(item or "")).strip() for item in value if cleanup_case_text(str(item or "")).strip())
                cleaned = cleanup_case_text(joined).strip()
                if cleaned:
                    return cleaned
            cleaned = cleanup_case_text(str(value or "")).strip()
            if cleaned:
                return cleaned
        return ""

    def _build_case_rule_concrete_sentence(self, *, render_kind: str, value: str) -> str:
        cleaned = cleanup_case_text(str(value or "")).strip()
        if not cleaned:
            return ""
        if render_kind == "stakeholder":
            cleaned = self._normalize_user_visible_participant_phrase(cleaned)
        if render_kind == "resource":
            cleaned = self._normalize_resource_sentence(cleaned)
            lowered = cleaned.strip().lower()
            if lowered.startswith(("в распоряжении", "в доступе", "доступно", "на смене", "в команде")):
                return cleaned if cleaned.endswith(".") else f"{cleaned}."
        if render_kind == "idea":
            return f"Обсуждаемая идея здесь такая: {cleaned}."
        if render_kind == "deadline":
            return f"Ориентир по сроку здесь такой: {cleaned}."
        if render_kind == "criteria":
            return f"Оценивать решение здесь нужно по таким критериям: {cleaned}."
        if render_kind == "effect":
            return f"Для этого рабочего контура эффект или последствие будет таким: {cleaned}."
        if render_kind == "resource":
            cleaned = self._normalize_resource_sentence(cleaned)
            lowered = cleaned.lower()
            if lowered.startswith(("в распоряжении", "в доступе", "доступно", "на смене", "в команде")):
                return cleaned if cleaned.endswith(".") else f"{cleaned}."
            return f"В распоряжении команды сейчас {cleaned}."
        if render_kind == "channel":
            return f"Рабочий канал здесь такой: {cleaned}."
        if render_kind == "task_name":
            return self._render_case_scope_sentence(cleaned)
        if render_kind == "stakeholder":
            if "," in cleaned:
                return f"В ситуации уже участвуют {cleaned}."
            return f"Ключевой участник ситуации здесь — {cleaned}."
        return f"Для этой ситуации важна такая конкретика: {cleaned}."

    def _inject_case_id_prompt_details(
        self,
        context_text: str,
        task_text: str,
        *,
        case_specificity: dict[str, Any] | None,
    ) -> tuple[str, str]:
        current_context = cleanup_case_text(str(context_text or "")).strip()
        current_task = cleanup_case_text(str(task_text or "")).strip()
        case_rule = self._get_case_id_prompt_rule(case_specificity)
        if not case_rule:
            return current_context, current_task
        specificity = dict(case_specificity or {})
        frame = dict(specificity.get("_case_frame") or {})
        contract = self._build_template_contract(
            case_type_code=str(case_rule.get("type_code") or specificity.get("_case_type_code") or ""),
            case_specificity=case_specificity,
        )
        trigger_details = cleanup_case_text(str(case_rule.get("trigger_details") or "")).strip()
        task_template = cleanup_case_text(str(case_rule.get("task_template") or "")).strip()
        if trigger_details:
            trigger_tokens = [token for token in re.findall(r"[а-яёa-z0-9-]{4,}", trigger_details.lower()) if token not in {"кейс", "ситуац"}]
            current_lower = current_context.lower()
            if trigger_tokens and not any(token in current_lower for token in trigger_tokens[:3]):
                current_context = f"{current_context} {trigger_details}".strip()
        preserve_signals = case_rule.get("preserve_signals")
        if isinstance(preserve_signals, list):
            current_lower = current_context.lower()
            signal_additions: list[str] = []
            deadline = cleanup_case_text(contract.get("deadline") or "")
            expected_step = cleanup_case_text(contract.get("expected_step") or frame.get("expected_step") or specificity.get("critical_step") or "")
            source = cleanup_case_text(contract.get("regulation") or self._normalize_case_frame_source(str(frame.get("source_of_truth") or "")))
            resource_profile = cleanup_case_text(str(specificity.get("resource_profile") or ""))
            for raw_signal in preserve_signals:
                signal = str(raw_signal or "").strip().lower()
                if "срок" in signal and deadline and not any(token in current_lower for token in re.findall(r"[а-яёa-z0-9-]{3,}", deadline.lower())[:3]):
                    signal_additions.append(f"Обещанный ориентир по сроку здесь такой: {deadline}.")
                elif "адресат ситуации" in signal and "клиент" not in current_lower and "заказчик" not in current_lower:
                    stakeholder = cleanup_case_text(str(frame.get("stakeholder") or specificity.get("primary_stakeholder") or "клиент"))
                    signal_additions.append(f"Ситуация разворачивается вокруг такого адресата: {stakeholder}.")
                elif "разрыв между внутренней работой и внешним восприятием" in signal and "не видит" not in current_lower:
                    signal_additions.append("Внутри часть работы уже велась, но снаружи это не выглядит как понятный результат или подтвержденный следующий шаг.")
                elif "следующий шаг" in signal and expected_step and "следующ" not in current_lower:
                    signal_additions.append(f"При этом следующий шаг пока не зафиксирован явно: {expected_step}.")
                elif "ресурсные ограничения" in signal and resource_profile and not any(token in current_lower for token in re.findall(r"[а-яёa-z0-9-]{4,}", resource_profile.lower())[:3]):
                    signal_additions.append(f"По ресурсу ситуация ограничена так: {resource_profile}.")
                elif "первым ответить" in signal and "перв" not in current_lower:
                    signal_additions.append("Сейчас именно вам нужно первым отреагировать на ситуацию и зафиксировать дальнейшее движение.")
                elif "эскалац" in signal and source and "эскалац" not in current_lower:
                    signal_additions.append(f"Понять факты по ситуации можно по {source}.")
            for addition in signal_additions:
                if addition and addition.lower() not in current_lower:
                    current_context = f"{current_context} {addition}".strip()
                    current_lower = current_context.lower()
        concretization_rules = case_rule.get("placeholder_concretization_rules")
        if isinstance(concretization_rules, list):
            current_lower = current_context.lower()
            for raw_rule in concretization_rules:
                if not isinstance(raw_rule, dict):
                    continue
                render_kind = str(raw_rule.get("render_kind") or "").strip().lower()
                field_code = str(raw_rule.get("field_code") or "").strip()
                if not render_kind or not field_code:
                    continue
                value = self._resolve_case_rule_concrete_value(
                    render_kind=render_kind,
                    field_code=field_code,
                    case_specificity=case_specificity,
                    contract=contract,
                )
                if not value:
                    continue
                value_tokens = re.findall(r"[а-яёa-z0-9-]{3,}", value.lower())
                if value_tokens and any(token in current_lower for token in value_tokens[:3]):
                    continue
                addition = self._build_case_rule_concrete_sentence(render_kind=render_kind, value=value)
                if addition and addition.lower() not in current_lower:
                    current_context = f"{current_context} {addition}".strip()
                    current_lower = current_context.lower()
        if task_template and self._is_generic_case_task(current_task):
            current_task = task_template
        return current_context, current_task


    def _is_generic_case_task(self, text: str) -> bool:
        lowered = cleanup_case_text(str(text or "")).lower()
        lowered = re.sub(r"^\s*что\s+нужно\s+сделать:\s*", "", lowered, flags=re.IGNORECASE).strip()
        if lowered in {
            "как вы будете действовать?",
            "предложите решение.",
            "предложите решение",
            "составьте рабочий план действий.",
            "что вы сделаете в первую очередь и почему?",
        }:
            return True
        return lowered in {
            "какое решение вы предложите?",
            "что вы предложите?",
            "как вы проведете этот разговор?",
            "как вы проведёте этот разговор?",
            "как вы будете действовать",
            "что вы предложите",
            "какое решение вы предложите",
            "как вы проведете этот разговор",
            "как вы проведёте этот разговор",
        }



    def _validate_template_fidelity(self, *, case_type_code: str | None, context_text: str, task_text: str, case_specificity: dict[str, Any] | None) -> list[str]:
        requirements = self._get_case_template_requirements(case_type_code)
        if not requirements:
            return []
        contract = self._build_template_contract(case_type_code=case_type_code, case_specificity=case_specificity)
        specificity = dict(case_specificity or {})
        frame = dict(specificity.get("_case_frame") or {})
        combined = f"{context_text or ''} {task_text or ''}".lower()
        type_code = str(case_type_code or "").strip().upper()
        missing: list[str] = []
        for field_name in requirements.get("required_fields", ()):
            value = cleanup_case_text(contract.get(str(field_name), ""))
            if not value:
                missing.append(str(field_name))
                continue
            tokens = [token for token in re.findall(r"[а-яёa-z0-9-]{4,}", value.lower()) if token not in {"через", "после", "между", "этап", "этапом"}]
            if tokens and not any(token in combined for token in tokens[:3]):
                missing.append(str(field_name))
        required_task_text = contract.get("required_task_text", "")
        if required_task_text and self._is_generic_case_task(task_text):
            missing.append("required_task_text")
        structure_markers = requirements.get("structure_markers")
        if isinstance(structure_markers, (list, tuple)):
            markers = [str(item).strip().lower() for item in structure_markers if str(item).strip()]
            if markers and not any(marker in combined for marker in markers):
                structure_missing_map = {
                    "F07": "decision_structure",
                    "F09": "improvement_structure",
                    "F10": "idea_evaluation_structure",
                    "F12": "development_structure",
                }
                missing_name = structure_missing_map.get(type_code)
                if missing_name:
                    missing.append(missing_name)
        if type_code == "F01":
            deadline = contract.get("deadline", "")
            blocked_step = cleanup_case_text(str(frame.get("expected_step") or specificity.get("critical_step") or ""))
            if deadline and not any(token in combined for token in re.findall(r"[а-яёa-z0-9-]{3,}", deadline.lower())[:3]):
                missing.append("deadline_visibility")
            if blocked_step and not any(token in combined for token in re.findall(r"[а-яёa-z0-9-]{4,}", blocked_step.lower())[:3]):
                missing.append("blocked_step_visibility")
            if "не видит" not in combined and "не получил" not in combined:
                missing.append("client_visibility_gap")
            if not ("перв" in combined and ("ответ" in combined or "жалоб" in combined)):
                missing.append("first_response_role")
        if type_code == "F05":
            deadline = contract.get("deadline", "")
            resource_profile = cleanup_case_text(str(specificity.get("resource_profile") or ""))
            if deadline and not any(token in combined for token in re.findall(r"[а-яёa-z0-9-]{3,}", deadline.lower())[:3]):
                missing.append("deadline_visibility")
            if resource_profile and not any(token in combined for token in re.findall(r"[а-яёa-z0-9-]{4,}", resource_profile.lower())[:3]):
                missing.append("resource_visibility")
            if not any(marker in combined for marker in ("кто отвечает", "роли", "ответствен", "порядок работы")):
                missing.append("role_clarity")
        return missing

    def _build_template_fidelity_addendum(self, *, case_type_code: str | None, case_specificity: dict[str, Any] | None, missing_fields: list[str]) -> str:
        type_code = str(case_type_code or "").strip().upper()
        contract = self._build_template_contract(case_type_code=type_code, case_specificity=case_specificity)
        specificity = dict(case_specificity or {})
        frame = dict(specificity.get("_case_frame") or {})
        if type_code == "F11":
            details: list[str] = []
            if "operation" in missing_fields and contract.get("operation"):
                details.append(f"Под вопросом операция «{contract['operation']}»")
            if "regulation" in missing_fields and contract.get("regulation"):
                details.append(f"проверка идет по регламенту и источнику истины: {contract['regulation']}")
            if "deviation" in missing_fields and contract.get("deviation"):
                details.append(f"отклонение выглядит так: {contract['deviation']}")
            if "authority_limit" in missing_fields and contract.get("authority_limit"):
                details.append(f"самостоятельно нельзя выходить за пределы такого ограничения: {contract['authority_limit']}")
            if "escalation_target" in missing_fields and contract.get("escalation_target"):
                details.append(f"эскалация должна идти {contract['escalation_target']}")
            if "channel" in missing_fields and contract.get("channel"):
                details.append(f"рабочий канал для фиксации шага: {contract['channel']}")
            if "risk" in missing_fields and contract.get("risk"):
                details.append(f"если передать результат дальше без сверки, возможен такой риск: {contract['risk']}")
            if details:
                return ". ".join(details).strip() + "."
        if type_code == "F07" and "decision_structure" in missing_fields:
            return "Здесь важно не только выбрать действие, но и явно разложить: что уже известно, чего не хватает, какие есть варианты, по какому сигналу решение нужно будет пересмотреть."
        if type_code == "F09" and "improvement_structure" in missing_fields:
            return "Нужно смотреть на ситуацию как на узкое место процесса: предлагать несколько разных идей улучшения, а не один общий совет быть внимательнее."
        if type_code == "F10" and "idea_evaluation_structure" in missing_fields:
            return "Нужно не просто назвать хорошую идею, а оценить ее по критериям, принять решение — берём, не берём или дорабатываем — и обозначить метрику успеха."
        if type_code == "F12" and "development_structure" in missing_fields:
            return "Разговор должен привести не только к обратной связи, но и к плану развития на ближайшие 2–4 недели, формату поддержки и понятной метрике прогресса."
        if type_code == "F01":
            details: list[str] = []
            deadline = contract.get("deadline", "")
            blocked_step = cleanup_case_text(str(frame.get("expected_step") or specificity.get("critical_step") or ""))
            source = cleanup_case_text(self._normalize_case_frame_source(str(frame.get("source_of_truth") or "")))
            if "deadline_visibility" in missing_fields and deadline:
                details.append(f"Клиенту обещали вернуться с ответом {deadline}")
            if "blocked_step_visibility" in missing_fields and blocked_step:
                details.append(f"Из-за этого у клиента тормозится {blocked_step}")
            if "client_visibility_gap" in missing_fields:
                details.append("внутри часть работы уже велась, но клиент не видит ни результата, ни внятного обновления статуса")
            if "first_response_role" in missing_fields:
                details.append("сейчас именно вам нужно первым ответить на жалобу и зафиксировать следующий шаг")
            if source and "source_of_truth" in missing_fields:
                details.append(f"Проверить картину можно по {source}")
            if details:
                return ". ".join(details).strip() + "."
        if type_code == "F05":
            details = []
            deadline = contract.get("deadline", "")
            resource_profile = self._normalize_resource_sentence(str(specificity.get("resource_profile") or ""))
            if "resource_visibility" in missing_fields and resource_profile:
                if resource_profile.strip().lower().startswith(("в распоряжении", "в доступе", "доступно", "на смене", "в команде")):
                    details.append(resource_profile)
                else:
                    details.append(f"В распоряжении команды сейчас {resource_profile}")
            if "deadline_visibility" in missing_fields and deadline:
                details.append(f"Срок по этой координации ограничен: {deadline}")
            if "role_clarity" in missing_fields:
                details.append("в команде нужно явно договориться, кто за что отвечает, как идет контроль и что делать, если один из ключевых элементов сорвется")
            if details:
                return ". ".join(details).strip() + "."
        return ""

    def _enforce_template_fidelity(self, *, case_type_code: str | None, context_text: str, task_text: str, case_specificity: dict[str, Any] | None) -> tuple[str, str]:
        contract = self._build_template_contract(case_type_code=case_type_code, case_specificity=case_specificity)
        if contract.get("required_task_text") and (not task_text.strip() or self._is_generic_case_task(task_text)):
            task_text = self._build_user_visible_case_task(
                case_type_code=case_type_code,
                context_text=context_text,
                case_title="",
            )
        missing = self._validate_template_fidelity(
            case_type_code=case_type_code,
            context_text=context_text,
            task_text=task_text,
            case_specificity=case_specificity,
        )
        addendum = self._build_template_fidelity_addendum(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
            missing_fields=missing,
        )
        if addendum and addendum.lower() not in context_text.lower():
            context_text = f"{context_text.strip()} {addendum}".strip()
        return context_text.strip(), task_text.strip()







    def _build_llm_case_template_payload(
        self,
        *,
        case_id_code: str | None,
        case_title: str,
        case_type_code: str | None,
        case_context: str,
        case_task: str,
        facts_data: str | None = None,
        trigger_details: str | None = None,
        constraints_text: str | None = None,
        stakes_text: str | None = None,
        base_variant_text: str | None = None,
        hard_variant_text: str | None = None,
        personalization_variables: str | None = None,
    ) -> dict[str, Any]:
        return {
            "case_id_code": case_id_code,
            "case_title": case_title,
            "type_code": case_type_code,
            "template_context": case_context,
            "template_task": case_task,
            "facts_data": facts_data,
            "trigger_details": trigger_details,
            "constraints_text": constraints_text,
            "stakes_text": stakes_text,
            "base_variant_text": base_variant_text,
            "hard_variant_text": hard_variant_text,
            "personalization_variables": personalization_variables,
        }

    def _build_llm_user_profile_payload(
        self,
        *,
        full_name: str | None,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        user_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = dict(user_profile or {})
        payload = dict(profile)
        payload.setdefault("user_id", profile.get("user_id"))
        payload.setdefault("full_name", full_name or profile.get("full_name"))
        payload.setdefault("company_industry", company_industry or profile.get("company_industry"))
        payload.setdefault("raw_position", position or profile.get("raw_position"))
        payload.setdefault("raw_duties", profile.get("raw_duties") or duties)
        payload.setdefault("normalized_duties", profile.get("normalized_duties") or duties)
        payload.setdefault("role_selected", profile.get("role_selected"))
        payload.setdefault("role_selected_code", profile.get("role_selected_code"))
        payload.setdefault("role_name", profile.get("role_selected") or role_name or profile.get("role_name"))
        payload["profile_summary"] = self._build_human_readable_profile_summary(payload)
        return payload

    def _build_human_readable_profile_summary(self, user_profile: dict[str, Any] | None) -> str:
        profile = dict(user_profile or {})

        def _clean_list(value: Any, *, limit: int) -> list[str]:
            if not isinstance(value, list):
                return []
            result: list[str] = []
            for item in value:
                text = cleanup_case_text(str(item or "")).strip()
                if text and text not in result:
                    result.append(text)
                if len(result) >= limit:
                    break
            return result

        role_label = cleanup_case_text(
            str(profile.get("role_selected") or profile.get("role_name") or "")
        ).strip()
        position = cleanup_case_text(str(profile.get("raw_position") or "")).strip()
        duties = cleanup_case_text(
            str(profile.get("normalized_duties") or profile.get("raw_duties") or "")
        ).strip()
        domain = cleanup_case_text(
            str(
                profile.get("user_domain")
                or profile.get("company_context")
                or profile.get("company_industry")
                or ""
            )
        ).strip()
        processes = _clean_list(profile.get("user_processes"), limit=4)
        tasks = _clean_list(profile.get("user_tasks"), limit=5)
        stakeholders = _clean_list(profile.get("user_stakeholders"), limit=4)
        systems = _clean_list(profile.get("user_systems"), limit=4)
        artifacts = _clean_list(profile.get("user_artifacts"), limit=4)
        constraints = _clean_list(profile.get("user_constraints"), limit=3)
        metrics = _clean_list(profile.get("user_success_metrics"), limit=3)

        lines: list[str] = []
        if role_label or position:
            lines.append(
                f"Пользователь работает в роли «{role_label or position}»"
                + (f" на позиции «{position}»." if role_label and position and role_label != position else ".")
            )
        if domain:
            lines.append(f"Рабочий домен: {domain}.")
        if duties:
            lines.append(f"Как пользователь сам описывает работу: {duties}.")
        if processes:
            lines.append(f"Типовые рабочие процессы: {', '.join(processes)}.")
        if tasks:
            lines.append(f"Типовые задачи: {', '.join(tasks)}.")
        if stakeholders:
            lines.append(f"С кем обычно взаимодействует: {', '.join(stakeholders)}.")
        if systems:
            lines.append(f"Основные системы и каналы: {', '.join(systems)}.")
        if artifacts:
            lines.append(f"Рабочие сущности и артефакты: {', '.join(artifacts)}.")
        if constraints:
            lines.append(f"Ограничения и красные линии: {', '.join(constraints)}.")
        if metrics:
            lines.append(f"На что влияет результат работы: {', '.join(metrics)}.")
        return "\n".join(lines).strip()

    def _dump_llm_payload(self, payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    def _normalize_llm_user_case_fields(
        self,
        *,
        context: str,
        task: str,
        fallback_task: str,
        case_type_code: str | None = None,
        case_title: str | None = None,
    ) -> tuple[str, str]:
        context_text = str(context or "").strip()
        task_text = str(task or "").strip()
        fallback_task_text = str(fallback_task or "").strip()

        combined = "\n\n".join(part for part in (context_text, task_text) if part).strip()
        if not combined:
            return context_text, task_text

        has_structured_markers = bool(
            re.search(
                r"(?:^|\n)\s*(?:\*\*Ситуация\*\*|Ситуация:?|\*\*Что известно\*\*|\*\*Что ограничивает\*\*|\*\*Что нужно сделать\*\*|Что нужно сделать:)",
                combined,
                flags=re.IGNORECASE,
            )
        )
        if not has_structured_markers:
            return context_text, task_text

        normalized = combined
        if not re.search(r"^\s*(?:\*\*Ситуация\*\*|Ситуация:?)", normalized, flags=re.IGNORECASE):
            normalized = f"Ситуация\n{normalized}".strip()

        task_match = re.search(
            r"(?:^|\n)\s*(?:\*\*Что нужно сделать\*\*|Что нужно сделать:)\s*:?\s*([\s\S]+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if task_match:
            normalized_task = cleanup_case_text(task_match.group(1)).strip()
            normalized_context = normalized[:task_match.start()].strip()
        else:
            normalized_task = cleanup_case_text(task_text).strip()
            if re.search(r"(?:^|\n)\s*(?:\*\*Ситуация\*\*|Ситуация:?|\*\*Что известно\*\*|\*\*Что ограничивает\*\*|\*\*Что нужно сделать\*\*)", normalized_task, flags=re.IGNORECASE):
                normalized_task = fallback_task_text
            normalized_context = normalized.strip()

        normalized_context = re.sub(r"^\s*\*\*Ситуация\*\*\s*", "Ситуация\n", normalized_context, flags=re.IGNORECASE)
        normalized_context = re.sub(r"^\s*Ситуация\s*\n", "Ситуация\n", normalized_context, flags=re.IGNORECASE)
        normalized_context = self._strip_generic_role_intro_before_real_scene(normalized_context)
        normalized_context = normalized_context.strip()
        normalized_task = normalized_task or fallback_task_text
        normalized_task = re.sub(r"^(?:(?:\*\*Что нужно сделать\*\*|Что нужно сделать:)\s*:?\s*)+", "", normalized_task, flags=re.IGNORECASE).strip()
        normalized_task = self._cleanup_user_case_task_output(normalized_task)
        if self._should_force_user_visible_task(
            task=normalized_task,
            case_type_code=case_type_code,
        ):
            normalized_task = self._build_user_visible_case_task(
                case_type_code=case_type_code,
                context_text=normalized_context,
                case_title=str(case_title or ""),
            )
        return normalized_context, normalized_task

    def _rewrite_user_case_materials_with_llm(
        self,
        *,
        case_id_code: str | None = None,
        case_title: str,
        case_type_code: str | None = None,
        case_context: str,
        case_task: str,
        role_name: str | None,
        full_name: str | None = None,
        position: str | None = None,
        duties: str | None = None,
        company_industry: str | None = None,
        user_profile: dict[str, Any] | None = None,
        facts_data: str | None = None,
        trigger_details: str | None = None,
        constraints_text: str | None = None,
        stakes_text: str | None = None,
        base_variant_text: str | None = None,
        hard_variant_text: str | None = None,
        personalization_variables: str | None = None,
        instruction_text_override: str | None = None,
        timeout_sec: int = 120,
        strict_validation: bool = True,
    ) -> tuple[str, str]:
        if not self.enabled:
            return case_context, case_task

        case_template_payload = self._build_llm_case_template_payload(
            case_id_code=case_id_code,
            case_title=case_title,
            case_type_code=case_type_code,
            case_context=case_context,
            case_task=case_task,
            facts_data=facts_data,
            trigger_details=trigger_details,
            constraints_text=constraints_text,
            stakes_text=stakes_text,
            base_variant_text=base_variant_text,
            hard_variant_text=hard_variant_text,
            personalization_variables=personalization_variables,
        )
        user_profile_payload = self._build_llm_user_profile_payload(
            full_name=full_name,
            position=position,
            duties=duties,
            company_industry=company_industry,
            role_name=role_name,
            user_profile=user_profile,
        )
        instruction = self._get_case_text_build_instruction(case_type_code)
        instruction_text = str(instruction_text_override or "").strip() or str((instruction or {}).get("instruction_text") or "").strip()
        if not instruction_text:
            return case_context, case_task

        prompt = (
            f"{instruction_text}\n\n"
            f"Шаблон кейса:\n{self._dump_llm_payload(case_template_payload)}\n\n"
            f"Персонализированный профиль пользователя:\n{self._dump_llm_payload(user_profile_payload)}"
        )
        try:
            messages = [
                {
                    "role": "system",
                    "content": "Верни только JSON с полями context и task.",
                },
                {"role": "user", "content": prompt},
            ]
            raw = self._post_chat(messages, temperature=0.18, timeout_sec=timeout_sec)
            try:
                parsed = self._parse_json(raw)
            except Exception:
                if not strict_validation:
                    raise
                retry_messages = list(messages) + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": "Верни только корректный JSON с полями context и task."},
                ]
                retry_raw = self._post_chat(retry_messages, temperature=0.18, timeout_sec=timeout_sec)
                parsed = self._parse_json(retry_raw)
            context = str(parsed.get("context") or "")
            task = str(parsed.get("task") or "")
            if not context or not task:
                if not strict_validation:
                    raise RuntimeError("LLM returned empty user case fields")
                retry_messages = list(messages) + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": "Верни только корректный JSON с непустыми полями context и task."},
                ]
                retry_raw = self._post_chat(retry_messages, temperature=0.18, timeout_sec=timeout_sec)
                retry_parsed = self._parse_json(retry_raw)
                context = str(retry_parsed.get("context") or "")
                task = str(retry_parsed.get("task") or "")
            if not context or not task:
                raise RuntimeError("LLM returned empty user case fields")
            normalized_context, normalized_task = self._normalize_llm_user_case_fields(
                context=context,
                task=task,
                fallback_task=case_task,
                case_type_code=case_type_code,
                case_title=case_title,
            )
            issues = self._validate_llm_user_case_output(
                context=normalized_context,
                task=normalized_task,
                case_type_code=case_type_code,
                case_title=case_title,
                role_name=role_name,
            )
            if issues and strict_validation:
                retry_messages = list(messages) + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            "Текущий кейс слишком слабый и не должен быть сохранен.\n"
                            "Исправь его и верни только корректный JSON с полями context и task.\n"
                            "Обязательно устрани следующие проблемы:\n- "
                            + "\n- ".join(issues)
                        ),
                    },
                ]
                retry_raw = self._post_chat(retry_messages, temperature=0.18, timeout_sec=timeout_sec)
                retry_parsed = self._parse_json(retry_raw)
                normalized_context, normalized_task = self._normalize_llm_user_case_fields(
                    context=str(retry_parsed.get("context") or ""),
                    task=str(retry_parsed.get("task") or ""),
                    fallback_task=case_task,
                    case_type_code=case_type_code,
                    case_title=case_title,
                )
                retry_issues = self._validate_llm_user_case_output(
                    context=normalized_context,
                    task=normalized_task,
                    case_type_code=case_type_code,
                    case_title=case_title,
                    role_name=role_name,
                )
                blocking_retry_issues = [
                    issue for issue in retry_issues
                    if self._is_blocking_case_issue(issue)
                ]
                if blocking_retry_issues:
                    raise RuntimeError(
                        "Weak user case rejected: " + "; ".join(blocking_retry_issues)
                    )
            return normalized_context, normalized_task
        except Exception as exc:
            raise RuntimeError("LLM user case rewrite failed") from exc

    def _validate_llm_user_case_output(
        self,
        *,
        context: str,
        task: str,
        case_type_code: str | None,
        case_title: str,
        role_name: str | None = None,
    ) -> list[str]:
        issues: list[str] = []
        type_code = str(case_type_code or "").strip().upper()
        if self._context_mentions_client_request(context):
            if not self._context_has_request_text(context):
                issues.append("Если в кейсе фигурирует обращение, заявка, тикет, жалоба или запрос клиента, нужно показать текст обращения или его содержательное содержание.")
        if self._task_has_methodical_hints(task):
            issues.append("В задании есть методические подсказки: этапы, метрики, риски, структура ответа или порядок анализа.")
        if self._context_has_template_title_leak(context, case_title=case_title):
            issues.append("В качестве заголовка или ситуации протекло слишком шаблонное название кейса вместо живой рабочей сцены.")
        if not self._context_has_user_visible_incident_title(context):
            issues.append("В ситуации нет явного пользовательского заголовка, из-за чего интерфейс может показать сырой шаблонный title кейса.")
        if self._context_is_too_abstract(context, case_type_code=type_code):
            issues.append("Ситуация получилась слишком короткой или абстрактной: не хватает конкретных рабочих фактов, сигнала или конфликта.")
        if self._context_has_role_downgrade(context, expected_role_name=role_name):
            issues.append("Масштаб роли в ситуации занижен относительно профиля пользователя.")
        return issues

    def _is_blocking_case_issue(self, issue: str) -> bool:
        lowered = str(issue or "").lower()
        blocking_markers = (
            "масштаб роли в ситуации занижен",
        )
        return any(marker in lowered for marker in blocking_markers)

    def _context_has_user_visible_incident_title(self, context: str) -> bool:
        text = str(context or "").strip()
        if re.search(r"^\s*Ситуация:\s*\*\*[^*]{8,}\*\*", text, flags=re.IGNORECASE):
            return True
        first_line = text.splitlines()[0].strip() if text else ""
        if not first_line:
            return False
        if first_line.lower().startswith("ситуация"):
            return True
        return len(first_line.split()) >= 4

    def _context_has_template_title_leak(self, context: str, *, case_title: str) -> bool:
        lowered = f"{case_title} {context}".lower()
        generic_markers = (
            "на участке или в команде",
            "процесса или продукта",
            "в условиях неопределенности",
            "высоких ставках и конфликте целей",
            "выбор главного при перегрузе",
            "генерация идей улучшения",
            "оценка идеи:",
        )
        if any(marker in lowered for marker in generic_markers):
            return True
        clean_title = cleanup_case_text(case_title).lower()
        first_line = cleanup_case_text(str(context or "").splitlines()[0] if context else "").lower()
        if clean_title and first_line and clean_title in first_line and len(clean_title.split()) >= 6:
            return True
        return False

    def _context_is_too_abstract(self, context: str, *, case_type_code: str) -> bool:
        clean = cleanup_case_text(context)
        lowered = clean.lower()
        if len(clean) < 180 and case_type_code in {"F04", "F06", "F07", "F08", "F09", "F10", "F12"}:
            return True
        concrete_markers = 0
        if re.search(r"\b\d+\b", clean):
            concrete_markers += 1
        if any(mark in lowered for mark in ("crm", "service desk", "sla", "очеред", "заявк", "обращени", "тикет", "эскалац")):
            concrete_markers += 1
        if self._context_has_work_signal(clean):
            concrete_markers += 1
        if any(mark in lowered for mark in ("считает", "настаивает", "опасается", "хочет", "просит", "говорит", "пишет")):
            concrete_markers += 1
        if any(mark in lowered for mark in ("срок", "до конца дня", "до завтрашнего утра", "нагруз", "повторн", "статус")):
            concrete_markers += 1
        return concrete_markers < 2

    def _context_has_role_downgrade(self, context: str, *, expected_role_name: str | None) -> bool:
        expected = cleanup_case_text(expected_role_name).lower()
        if not expected:
            return False
        actual_prefix = cleanup_case_text(" ".join(str(context or "").split()[:10])).lower()
        expected_is_managerial = any(token in expected for token in ("руковод", "manager", "менедж", "lead", "head", "началь"))
        if not expected_is_managerial:
            return False
        downgraded_markers = (
            "вы — специалист",
            "вы специалист",
            "вы — сотрудник",
            "вы сотрудник",
            "вы работаете специалистом",
        )
        return any(marker in actual_prefix for marker in downgraded_markers)

    def _get_case_signal_requirements(self, case_type_code: str | None) -> tuple[str, ...]:
        type_code = str(case_type_code or "").strip().upper()
        mapping = {
            "F01": ("письмо", "жалоба", "обращение", "реплика"),
            "F02": ("запрос", "письмо", "чат", "сообщение", "реплика"),
            "F03": ("реплика", "чат", "сообщение", "жалоба"),
            "F09": ("жалоба", "обращение", "чат", "комментарий", "реплика"),
            "F10": ("идея", "чат", "звонок", "сообщение", "реплика"),
            "F12": ("реплика", "жалоба", "сообщение", "обратная связь"),
        }
        return mapping.get(type_code, ())

    def _context_has_work_signal(self, context: str, case_type_code: str | None = None) -> bool:
        lowered = str(context or "").lower()
        if any(mark in context for mark in ('"', "«", "»")):
            return True
        indirect_markers = (
            "пишет",
            "написал",
            "написала",
            "сообщает",
            "сообщил",
            "сообщила",
            "в комментариях",
            "в crm",
            "в service desk",
            "в чате",
            "в письме",
            "поступило уведомление",
            "пришла эскалация",
            "жалоба клиента",
        )
        generic_hit = any(marker in lowered for marker in indirect_markers)
        required_signal_kinds = self._get_case_signal_requirements(case_type_code)
        if not required_signal_kinds:
            return generic_hit

        kind_markers = {
            "письмо": ("письм", "email", "почт"),
            "чат": ("чат", "в чате", "в рабочем чате"),
            "звонок": ("звон", "позвонил", "созвон"),
            "жалоба": ("жалоб", "недоволь", "претенз"),
            "эскалация": ("эскалац", "эскалир"),
            "реплика": ("сказал", "сказала", "говорит", "написал", "написала", "сообщил", "сообщила", "просит"),
            "обращение": ("обращени", "заявк", "тикет", "запрос"),
            "сообщение": ("сообщен", "сообщил", "сообщила", "написал", "написала"),
            "комментарий": ("комментар",),
            "идея": ("идея", "предложил", "предложила", "предложение"),
            "обратная связь": ("обратн", "feedback", "отзыв"),
        }
        for kind in required_signal_kinds:
            markers = kind_markers.get(kind, ())
            if any(marker in lowered for marker in markers):
                return True
        return generic_hit and any(kind in {"реплика", "сообщение", "обращение"} for kind in required_signal_kinds)

    def _context_mentions_client_request(self, context: str) -> bool:
        lowered = str(context or "").lower()
        markers = (
            "обращени",
            "заявк",
            "тикет",
            "жалоб",
            "запрос клиент",
            "клиент написал",
            "клиент просит",
            "клиент сообщает",
        )
        return any(marker in lowered for marker in markers)

    def _context_has_request_text(self, context: str) -> bool:
        text = str(context or "")
        lowered = text.lower()
        if any(mark in text for mark in ('"', "«", "»")):
            return True
        content_markers = (
            "клиент пишет, что",
            "клиент сообщает, что",
            "клиент указал, что",
            "в обращении указано, что",
            "в заявке указано, что",
            "в тикете указано, что",
            "жалоба клиента в том, что",
            "суть обращения в том, что",
            "клиент просит",
            "клиент жалуется на",
        )
        return any(marker in lowered for marker in content_markers)

    def _task_has_methodical_hints(self, task: str) -> bool:
        lowered = str(task or "").lower()
        hint_patterns = (
            "опишите",
            "перечислите",
            "выделите",
            "оцените риски",
            "метрик",
            "этап",
            "шаг",
            "структур",
            "сначала",
            "затем",
            "по каким критериям",
            "критери",
            "план",
            "срок",
            "ответственн",
        )
        neutral_starts = (
            "что вы будете делать",
            "как вы будете действовать",
            "как вы проведете",
            "как вы оцените",
            "какие улучшения вы предложите",
            "как вы ответите",
            "уточните требования",
            "подготовьте ответ клиенту",
        )
        if any(lowered.startswith(prefix) for prefix in neutral_starts):
            return False
        return any(pattern in lowered for pattern in hint_patterns)

    def _should_force_user_visible_task(self, *, task: str, case_type_code: str | None) -> bool:
        value = cleanup_case_text(str(task or "")).strip()
        lowered = value.lower()
        if not value:
            return True
        if self._is_generic_case_task(value):
            return False
        if self._task_has_methodical_hints(value):
            return True
        if len(value) > 220:
            return True
        if re.search(r"\b(бер[её]м\s*/\s*не\s+бер[её]м|метрик|ответственн|срок[аиоу]?|этап[а-я]*|рисков?)\b", lowered):
            return True
        if re.search(r"\b\d+\s*[–-]?\s*\d+\b", lowered):
            return True
        if any(marker in value for marker in ("1.", "2.", "3.", "- ", "• ")):
            return True
        type_code = str(case_type_code or "").strip().upper()
        if type_code in {"F09", "F10", "F12"} and len(value.split()) > 18:
            return True
        return False

    def _cleanup_user_case_task_output(self, task: str) -> str:
        value = str(task or "").strip()
        if not value:
            return ""
        value = self._dedupe_case_text_repetitions(value, is_task=True).strip()
        value = re.sub(r"^(?:Что нужно сделать:\s*)+", "", value, flags=re.IGNORECASE).strip()
        parts = [
            part.strip()
            for part in re.split(r"\n\s*Что нужно сделать:\s*|\n{2,}", value, flags=re.IGNORECASE)
            if part.strip()
        ]
        deduped: list[str] = []
        seen: set[str] = set()
        for part in parts:
            key = re.sub(r"\s+", " ", part).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(part)
        if len(deduped) >= 2 and deduped[0].lower() == deduped[-1].lower():
            deduped = deduped[:1]
        result = "\n\n".join(deduped).strip()

        sentence_parts = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", result)
            if part.strip()
        ]
        compact_sentences: list[str] = []
        seen_sentence_keys: set[str] = set()
        for sentence in sentence_parts:
            key = re.sub(r"\s+", " ", sentence).strip().lower()
            key = re.sub(r"[.!?]+$", "", key)
            if not key or key in seen_sentence_keys:
                continue
            if compact_sentences:
                previous_key = re.sub(r"\s+", " ", compact_sentences[-1]).strip().lower()
                previous_key = re.sub(r"[.!?]+$", "", previous_key)
                if key in previous_key or previous_key in key:
                    continue
            seen_sentence_keys.add(key)
            compact_sentences.append(sentence)
        if compact_sentences:
            result = " ".join(compact_sentences).strip()
        return result

    def _inject_case_concreteness(
        self,
        text: str,
        *,
        case_title: str,
        case_type_code: str | None = None,
        case_specificity: dict[str, Any] | None = None,
    ) -> str:
        result = (text or "").strip()
        if not result:
            return ""

        lowered = f"{case_title} {result}".lower()
        type_code = (case_type_code or "").upper()
        has_direct_speech = any(mark in result for mark in ('"', "«", "»"))
        scenario = self._scenario_from_case_text(case_title=case_title, text=result)
        specificity = self._normalize_case_specificity(case_specificity or {}, self._fallback_case_specificity(
            position=None,
            duties=None,
            company_industry=None,
            role_name=None,
            user_profile=None,
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=result,
            case_task="",
        ))

        if (
            not has_direct_speech
            and (
                "клиент написал" in lowered
                or "ответить клиент" in lowered
                or "сообщение клиент" in lowered
                or "письмо клиент" in lowered
                or "первого ответа" in lowered
                or "первым ответить клиенту" in lowered
                or "жалоб" in lowered
            )
            and not any(word in lowered for word in ("разговор", "бесед", "коллег", "личный разговор"))
        ):
            result = re.sub(
                r"^Во\s+второй\s+половине\s+дня\s+клиент\s+написал\s+жалобу\s+[^.]*\.\s*",
                "",
                result,
                flags=re.IGNORECASE,
            )
            quote_text = specificity.get("message_quote") or ""
            channel = str(specificity.get("channel") or "").lower()
            if any(word in channel for word in ("jira", "комментар")):
                intro = "Во второй половине дня заказчик пишет в комментариях к задаче в Jira:"
            elif "чат" in channel:
                intro = "Во второй половине дня через чат поддержки приходит сообщение клиента:"
            else:
                intro = "Во второй половине дня клиент пишет:"
            if not quote_text:
                quote_text = "Добрый день! Вы обещали ответить до 18:00. Сейчас уже 19:00, а ответа я так и не получила. Пожалуйста, объясните, что происходит и когда будет решение."
            quote = f"{intro} «{quote_text}»."
            workflow = str(specificity.get("workflow_label") or "текущий процесс")
            source_of_truth = str(specificity.get("source_of_truth") or "внутренние данные")
            current_state = self._humanize_current_state(str(specificity.get("current_state") or ""))
            bottleneck = str(specificity.get("bottleneck") or "").strip()
            work_items = self._join_case_items((specificity.get("ticket_titles") or [])[:2])
            detail_parts = []
            if current_state:
                detail_parts.append(current_state)
            else:
                detail_parts.append(
                    f"Сейчас работа идет по процессу «{workflow}», но из {source_of_truth} не до конца понятно, какой следующий шаг уже подтвержден, а какой еще остается открытым."
                )
            if bottleneck:
                detail_parts.append(f"Ключевая проблема сейчас в том, что {bottleneck}.")
            if work_items:
                detail_parts.append(f"По ситуации уже видны такие рабочие сущности: {work_items}.")
            result = f"{quote} {' '.join(part.strip() for part in detail_parts if part.strip())}".strip()
            return result

        if type_code == "F12":
            return self._reshape_development_conversation_case_context(result, case_title=case_title)

        if type_code == "F13":
            return self._reshape_change_management_case_context(result, case_title=case_title)

        if type_code == "F14":
            return self._reshape_experiment_design_case_context(result, case_title=case_title)

        if type_code == "F15":
            return self._reshape_reframing_case_context(result, case_title=case_title)

        if type_code == "F02":
            return self._reshape_clarification_case_context(
                result,
                case_title=case_title,
                case_specificity=specificity,
            )

        if type_code == "F04":
            return self._reshape_alignment_case_context(result, case_title=case_title)

        if type_code == "F05":
            return self._compose_planning_case_context(specificity)

        if type_code == "F06":
            base = self._reshape_incident_case_context(result, case_title=case_title)
            if specificity.get("ticket_titles"):
                base = f"{base} Для разбора уже доступны материалы: {self._join_case_items(specificity['ticket_titles'][:3])}."
            return base

        if type_code == "F09":
            return self._compose_improvement_case_context(specificity)

        if type_code == "F10":
            return self._compose_idea_evaluation_case_context(specificity)

        if type_code == "F11":
            return self._compose_control_risk_case_context(specificity)

        if type_code == "F08" or any(word in lowered for word in ("приоритизац", "конфликте срочности", "что делать в первую очередь", "перегруз")):
            return self._compose_priority_case_context(specificity)

        if type_code == "F07" or any(word in lowered for word in ("выбор действия", "противоречивых сигналах", "ограниченном времени")):
            return self._compose_decision_case_context(specificity)

        if type_code in {"F03", "F12"} or (
            not type_code and any(word in lowered for word in ("разговор", "бесед", "коллег", "развивающ", "личный разговор"))
        ):
            if type_code == "F12":
                return self._compose_development_conversation_case_context(specificity)
            return self._reshape_conversation_case_context(
                result,
                case_title=case_title,
                case_specificity=specificity,
            )

        if not has_direct_speech and any(word in lowered for word in ("согласован", "смежн", "инцидент", "сбой", "ошибк", "эскалац")):
            detail = (
                f"Для разбора уже доступны конкретные материалы: {self._join_case_items(specificity['ticket_titles'][:3]) or scenario['ticket_titles_short']}."
            )
            result = f"{result} {detail}"
            return result

        if not has_direct_speech and any(word in lowered for word in ("смен", "групп", "распредел", "роли", "план")):
            detail = (
                f"В работе уже есть конкретные задачи: {self._join_case_items(specificity['ticket_titles'][:3]) or scenario['ticket_titles_short']}."
            )
            result = f"{result} {detail}"
            return result

        if not has_direct_speech and any(word in lowered for word in ("иде", "гипотез", "решени", "предлож")):
            idea_label = specificity.get("idea_label") or f"изменения порядка работы по процессу «{scenario['workflow_label']}»"
            detail = f"Например, обсуждаемая идея — «{idea_label}»."
            result = f"{result} {detail}"
            return result

        return result

    def _reshape_conversation_case_context(
        self,
        text: str,
        *,
        case_title: str,
        case_specificity: dict[str, Any] | None = None,
    ) -> str:
        source = f"{case_title} {text}".lower()
        if self._infer_specificity_domain_family(case_specificity or {}) == "maritime":
            return (
                "В последние недели один из членов экипажа несколько раз передавал вахту как завершенную, "
                "хотя следующий маневр, подтверждение обстановки и запись о фактическом результате были зафиксированы не полностью. "
                "Из-за этого следующей вахте приходилось заново уточнять ситуацию, терялось время на мостике, "
                "а в экипаже росло напряжение из-за повторных разборов. "
                "Вам нужно провести разговор с сотрудником, чтобы договориться о более понятном порядке передачи вахты, "
                "фиксации следующего шага и подтверждения действий перед сменой."
            )
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят")):
            return (
                "В последние недели один из сотрудников несколько раз передавал комплект чертежей дальше как готовый, "
                "хотя замечания по документации и исходные данные еще не были полностью согласованы. "
                "Из-за этого комплект приходилось возвращать на доработку, сроки выпуска документации сдвигались, а в группе росло напряжение. "
                "Вам нужно провести разговор с сотрудником, чтобы договориться о более понятном порядке проверки и передачи документации дальше."
            )
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "В последние недели ваш коллега несколько раз закрывал спорные ситуации по гостям как решенные, "
                "хотя замечания по заказу и договоренности со сменой еще не были до конца зафиксированы. "
                "Из-за этого гостям приходилось повторно объяснять проблему, в журнале смены появлялись пробелы, "
                "а в баре росло напряжение между сменой и администратором зала. "
                "Вам нужно провести разговор с коллегой, чтобы договориться о более понятном порядке фиксации замечаний, "
                "передачи информации по гостю и закрытия таких ситуаций."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "В последние недели ваш коллега несколько раз переводил задачи в Jira в статус «Готово», "
                "хотя требования еще не были до конца согласованы, а команда разработки позже возвращалась с уточнениями. "
                "Из-за этого задачи приходилось открывать заново, сроки подготовки ТЗ сдвигались, а в команде росло напряжение. "
                "Вам нужно провести разговор с коллегой, чтобы договориться о более понятном порядке передачи задач в работу "
                "и избежать повторения таких сбоев."
            )

        return (
            "В последние недели ваш коллега несколько раз срывал договоренности: задачи закрывались по статусу раньше, "
            "чем работа действительно доходила до результата. Из-за этого появлялись дополнительные переделки, "
            "сдвигались сроки, а в команде росло напряжение. Вам нужно провести разговор с коллегой, "
            "чтобы договориться о более понятном порядке работы и избежать повторения таких сбоев."
        )

    def _reshape_complaint_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят")):
            return (
                "Смежное подразделение пишет: "
                "«Добрый день! Комплект уже отмечен как переданный, но замечания по чертежам закрыты не полностью, а итогового подтверждения я не вижу. "
                "Поясните, пожалуйста, что реально готово и когда будет финальный результат». "
                "По внутренним данным видно, что часть проверки уже выполнена, но не все замечания закрыты и следующий шаг по комплекту явно не зафиксирован."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ", "заказчик")):
            return (
                "Во второй половине дня заказчик пишет в комментариях к задаче в Jira: "
                "«Добрый день! Задача уже отмечена как выполненная, но согласованного ТЗ и понятного итогового решения я не вижу. "
                "Поясните, пожалуйста, что именно сделано и когда я получу финальный результат». "
                "В Jira видно, что статус задачи уже изменён, но из текущих данных не до конца понятно, что именно осталось нерешённым."
            )
        return (
            "Во второй половине дня клиент пишет с жалобой: "
            "«Добрый день! Вы обещали ответить до 18:00. Сейчас уже 19:00, а ответа я так и не получила. "
            "Пожалуйста, объясните, что происходит и когда будет решение». "
            "Во внутренних данных видно, что часть работы уже велась, но клиент этого не видит, а следующий шаг нигде явно не зафиксирован."
        )

    def _reshape_clarification_case_context(
        self,
        text: str,
        *,
        case_title: str,
        case_specificity: dict[str, Any] | None = None,
    ) -> str:
        source = f"{case_title} {text}".lower()
        if self._infer_specificity_domain_family(case_specificity or {}) == "maritime":
            return (
                "Поступил запрос по судовой операции или этапу рейса, но сейчас в нем не хватает части исходных данных, "
                "подтверждения текущей обстановки и ясного следующего шага для экипажа. "
                "Если начать действовать сразу, есть риск неверно понять приоритет операции, "
                "создать рассогласование между вахтами и потерять время на повторное уточнение распоряжений."
            )
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят")):
            return (
                "Поступил запрос по комплекту документации, но сейчас в нем не хватает части исходных данных, перечня замечаний и подтвержденных ограничений. "
                "Если начать работу сразу, есть риск неверно понять объем доработки, вернуть комплект на повторное согласование и потерять время группы."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "Поступил запрос по задаче в Jira, но сейчас в нем не хватает части исходных данных, критериев готовности и подтвержденных ограничений. "
                "Если начать работу сразу, есть риск неверно понять ожидания заказчика, вернуть задачу на уточнение и потерять время команды разработки."
            )
        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code="F02",
                case_title=case_title,
                case_context=text,
                case_task="",
            ),
        )
        workflow = str(specificity.get("workflow_label") or "текущий процесс")
        source_of_truth = str(specificity.get("source_of_truth") or "рабочие данные")
        request_type = str(specificity.get("request_type") or "рабочий запрос")
        current_state = self._humanize_current_state(str(specificity.get("current_state") or ""))
        bottleneck = str(specificity.get("bottleneck") or "").strip()
        examples = self._join_case_items((specificity.get("ticket_titles") or [])[:2])
        result = (
            f"Поступил запрос по процессу «{workflow}», но сейчас в нем не хватает части исходных данных, "
            f"критериев результата и подтвержденных ограничений по задаче типа «{request_type}». "
        )
        if current_state:
            result += f"{current_state} "
        else:
            result += f"Сейчас проверять ситуацию приходится по {source_of_truth}, но картина по следующему шагу остается неполной. "
        if bottleneck:
            result += f"Основная проблема сейчас в том, что {bottleneck}. "
        if examples:
            result += f"По запросу уже фигурируют такие рабочие элементы: {examples}. "
        result += (
            "Если начать работу сразу, есть риск неверно понять задачу, получить возврат "
            "и потратить ресурс на лишнюю переделку."
        )
        return result.strip()

    def _reshape_alignment_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят")):
            return (
                "Чтобы завершить свою часть работы, вам нужно согласовать со смежным подразделением недостающие исходные данные и замечания по комплекту документации. "
                "Сейчас позиции расходятся, а без ясной договоренности есть риск передать комплект дальше с разным пониманием состава и степени готовности."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "Чтобы завершить свою часть работы, вам нужно согласовать со смежной командой недостающие входные данные по задаче в Jira. "
                "Сейчас часть требований еще не подтверждена, а без этой договоренности есть риск передать задачу дальше с разным пониманием результата."
            )
        return (
            "Для продолжения работы нужно согласовать со смежной стороной недостающие данные и следующий шаг. "
            "Сейчас позиции расходятся, а без ясной договоренности задача может зависнуть или вернуться на повторную доработку."
        )

    def _reshape_planning_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят")):
            return (
                "Сейчас в работе несколько комплектов документации, и часть из них уже начинает блокировать выпуск чертежей и передачу работы в смежные подразделения. "
                "При этом людей и времени ограниченно, а если не договориться о порядке работы сейчас, часть комплектов зависнет без понятного владельца и следующего шага."
            )
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "Сейчас в смене одновременно накопилось несколько задач по гостям и внутренней работе бара. "
                "Часть из них уже начинает влиять на скорость обслуживания, а если не договориться о порядке работы сейчас, замечания по заказам, спорные ситуации и передача информации по смене начнут провисать."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "Сейчас в работе несколько задач в Jira, и часть из них уже начинает блокировать подготовку ТЗ и передачу задач в разработку. "
                "При этом людей и времени ограниченно, а если не договориться о порядке работы сейчас, часть задач зависнет без понятного владельца и следующего шага."
            )
        return (
            "Сейчас в работе несколько задач, но людей и времени ограниченно. "
            "Если не определить порядок работы сейчас, часть задач зависнет, а часть начнет дублироваться между участниками."
        )

    def _reshape_incident_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят")):
            return (
                "На вашем участке произошел сбой: комплект документации был передан дальше, хотя замечания по чертежам и ожидаемый результат еще не были полностью согласованы. "
                "Из-за этого смежное подразделение вернуло комплект на уточнение, сроки сдвинулись, а часть проверки придется проводить заново."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "На вашем участке произошел сбой: задача в Jira была закрыта, хотя требования и ожидаемый результат еще не были полностью согласованы. "
                "Из-за этого команда разработки вернулась с уточнениями, сроки сдвинулись, а часть работы придется пересобирать заново."
            )
        return (
            "На вашем участке произошел сбой: часть работы была передана дальше с неполной или противоречивой информацией. "
            "Из-за этого возникла задержка, а следующему участнику процесса пришлось возвращать задачу на доработку."
        )

    def _reshape_decision_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "Нужно быстро принять решение по спорной ситуации с гостем, хотя данные по заказу и журналу смены частично расходятся. "
                "По одним отметкам кажется, что вопрос уже закрыт, а по другим видно, что результат для гостя не подтвержден и следующий шаг еще не согласован. "
                "Если поторопиться, есть риск новой жалобы. Если затянуть решение, смена потеряет время и напряжение в зале вырастет."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "Нужно быстро принять решение по задаче в Jira, хотя данные частично противоречат друг другу. "
                "По одним комментариям кажется, что требования уже согласованы и задачу можно передавать дальше, "
                "а по другим видно, что часть условий еще не подтверждена и есть риск возврата от команды разработки. "
                "На полную проверку времени нет: если затянуть решение, сдвинутся сроки подготовки ТЗ и следующего этапа работы."
            )

        return (
            "Нужно быстро принять решение при неполных и противоречивых данных. "
            "Если поторопиться, есть риск ошибки и повторной переделки. Если затянуть решение, сдвинутся сроки и следующий шаг по задаче."
        )

    def _reshape_priority_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "Одновременно накопилось несколько срочных задач по работе бара: часть связана с гостями, часть — с внутренней передачей информации по смене. "
                "Сделать все сразу не получится, и от порядка действий зависит, где быстрее возникнет повторная жалоба, задержка обслуживания или новый конфликт."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "На вас одновременно пришло несколько задач в Jira: одна требует срочного уточнения ТЗ, "
                "вторая уже задерживает команду разработки, а по третьей заказчик ждет обновления статуса до конца дня. "
                "Сделать все сразу не получится, и от порядка действий зависит, где команда получит наибольшую задержку и сколько задач потом вернется на доработку."
            )

        return (
            "Одновременно накопилось несколько срочных задач, но ресурсов не хватает, чтобы заняться всеми сразу. "
            "Нужно быстро определить, что делать в первую очередь, чтобы не создать лишние задержки и не потерять важный следующий шаг."
        )

    def _reshape_improvement_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "В смене бара регулярно повторяются ситуации, когда замечания по заказу и договоренности по гостю фиксируются не полностью. "
                "Из-за этого спорные вопросы приходится разбирать повторно, часть информации теряется между сменами, а команда тратит лишнее время на уже закрытые ситуации."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "Сейчас на вашем участке регулярно возникают возвраты задач на уточнение: требования не всегда доводятся до единого понимания перед передачей в разработку. "
                "Из-за этого растет время обработки задач, появляются повторные согласования и команда тратит больше ресурса на переделки."
            )
        return (
            "Сейчас в процессе есть повторяющаяся проблема, из-за которой работа замедляется, а часть задач приходится возвращать на доработку. "
            "Нужно предложить улучшение, которое поможет сократить потери времени и сделать процесс устойчивее."
        )

    def _reshape_idea_evaluation_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "Появилась идея «единая фиксация замечаний по гостю»: изменить порядок фиксации замечаний по гостям и передачи информации между баром и администратором смены. "
                "Это может сократить число повторных разборов и спорных закрытий, но есть риск, что в пиковые часы работа бара станет медленнее."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "Появилась идея «единый пакет требований перед передачей в разработку»: изменить порядок подготовки и согласования требований перед передачей задач в разработку. "
                "Это может сократить количество возвратов, но есть риск замедлить работу команды на старте и увеличить нагрузку на аналитиков."
            )
        return (
            "Появилась идея «улучшение процесса»: это изменение может дать заметный эффект, но пока неясно, стоит ли запускать его сразу и как это сделать безопасно. "
            "Нужно оценить идею и выбрать разумный режим внедрения."
        )

    def _reshape_control_risk_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "Перед закрытием вопроса по гостю вы замечаете несоответствие: по смене ситуация выглядит решенной, "
                "но замечание по заказу или подтверждение результата еще не зафиксированы полностью. "
                "Если закрыть ее в таком виде, есть риск новой жалобы и повторного разбора уже в следующей смене."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "Перед передачей задачи дальше вы заметили несоответствие: по статусу она выглядит готовой, но часть условий и договоренностей в Jira еще не подтверждена. "
                "Если передать задачу в таком виде, есть риск возврата от команды разработки и нового цикла уточнений."
            )
        return (
            "Перед следующим этапом работы обнаружилось несоответствие в данных или статусах. "
            "Если передать результат дальше в таком виде, есть риск ошибки, возврата и дополнительной задержки."
        )

    def _reshape_development_conversation_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню", "заказ", "pos-систем")):
            return (
                "В работе сотрудника повторяется одна и та же проблема: спорные ситуации по гостям отмечаются как закрытые, "
                "хотя замечания по заказу, результат для гостя и следующий шаг по смене еще не зафиксированы полностью. "
                "Из-за этого команда тратит время на повторные разборы, гостям приходится возвращаться к уже закрытым вопросам, "
                "а напряжение между баром и залом растет. "
                "Вам нужно провести разговор с сотрудником, чтобы обозначить проблему, договориться о более понятном порядке фиксации результата "
                "и снизить риск повторения таких ситуаций."
            )
        if any(word in source for word in ("jira", "тз", "требован", "разработ")):
            return (
                "В последние недели один и тот же паттерн повторяется: задачи передаются дальше как готовые, "
                "хотя требования еще не до конца согласованы и команда разработки возвращается с уточнениями. "
                "Из-за этого сроки подготовки ТЗ сдвигаются, задачи приходится открывать заново, а в команде растет напряжение. "
                "Вам нужно провести разговор с сотрудником, чтобы обозначить проблему, договориться о более понятном порядке передачи задач в работу "
                "и снизить риск повторения таких сбоев."
            )
        return (
            "В работе сотрудника повторяется проблема, которая уже влияет на сроки, качество результата или устойчивость команды. "
            "Если оставить это без разговора и понятного следующего шага, этот паттерн закрепится и начнет сильнее влиять на результат. "
            "Вам нужно провести разговор с сотрудником, чтобы обозначить проблему и договориться о следующем шаге."
        )

    def _reshape_change_management_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("jira", "тз", "требован", "разработ", "ит", "цифров")):
            return (
                "В команде запускается изменение в привычном порядке работы: часть задач теперь нужно готовить и согласовывать по-новому перед передачей в разработку. "
                "Часть коллег считает, что это усложнит процесс и замедлит работу, поэтому сопротивление уже начинает влиять на договоренности и темп команды. "
                "Если изменение внедрять без понятного плана, команда может формально согласиться, но продолжить работать по-старому."
            )
        return (
            "В команде запускается изменение в привычном порядке работы, но часть участников уже показывает сопротивление и сомневается, что новый подход действительно нужен. "
            "Если внедрять изменение без понятного плана и коммуникации, люди могут формально согласиться, но продолжить работать по-старому."
        )

    def _reshape_experiment_design_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("jira", "тз", "требован", "разработ", "ит", "цифров")):
            return (
                "Появилась идея изменить порядок подготовки требований перед передачей задач в разработку, чтобы сократить количество возвратов и повторных уточнений. "
                "Потенциал у идеи есть, но пока неясно, даст ли она эффект без лишней нагрузки на команду. "
                "Сразу раскатывать изменение на весь процесс рискованно, поэтому сначала нужен ограниченный и безопасный пилот."
            )
        return (
            "Появилась идея улучшения процесса, которая может дать заметный эффект, но пока непонятно, как проверить ее быстро и безопасно. "
            "Сразу внедрять изменение на весь процесс рискованно, поэтому сначала нужен ограниченный пилот."
        )

    def _reshape_reframing_case_context(self, text: str, *, case_title: str) -> str:
        source = f"{case_title} {text}".lower()
        if any(word in source for word in ("jira", "тз", "требован", "разработ", "ит", "цифров")):
            return (
                "Команда снова упирается в одну и ту же проблему: задачи возвращаются на уточнение, сроки сдвигаются, а привычные способы решения уже не дают заметного эффекта. "
                "Если смотреть на проблему только в прежней логике, вы снова получите те же ограничения и тот же результат. "
                "Нужно по-новому сформулировать саму проблему и найти несколько разных вариантов дальнейшего действия."
            )
        return (
            "Проблема в процессе уже застряла: привычные способы решения не дают результата, а команда начинает ходить по кругу. "
            "Нужно посмотреть на проблему под другим углом и найти несколько разных вариантов дальнейшего действия."
        )



    def _summarize_personalization_map(self, values: dict[str, str]) -> str:
        parts = []
        for key, value in values.items():
            clean = self._sanitize_personalization_value(value)
            if clean:
                parts.append(f"{key}: {clean}")
        return "; ".join(parts[:8]) if parts else "персонализация выполнена по контексту пользователя"

    def _sanitize_case_prompt_text(
        self,
        text: str,
        *,
        role_name: str | None,
        planned_total_duration_min: int | None,
    ) -> str:
        result = text or ""
        result = result.replace("агент Коммуникатор", "агент Интервьюер")
        result = result.replace("Агент Коммуникатор", "Агент Интервьюер")
        result = result.replace("AI-агента 'Коммуникатор'", "AI-агента 'Интервьюер'")
        scope_text = self._resolve_role_scope(role_name)
        result = re.sub(
            r"для\s+L\s*[—-]\s*участок(?:а)?\s*,?\s*для\s+M\s*[—-]\s*команда(?:\s*или\s*процесс)?",
            scope_text,
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"planned_total_duration_min\s*:?\s*\d*", "", result, flags=re.IGNORECASE)
        result = result.replace("Нет измеенний", "Не указаны")
        result = re.sub(r"\b(изменений нет|нет изменений|нет измеенний|не изменилось|не изменений|без изменений)\b", role_name or "Не указано", result, flags=re.IGNORECASE)
        result = re.sub(r"рабочий контекст в области [^.,;\n\"]+", "рабочий контекст процесса, соответствующего кейсу и профилю пользователя", result, flags=re.IGNORECASE)
        result = re.sub(r"\.\.\.\s*", ". ", result)
        result = re.sub(r"\s*\.\s*рике\b", ". Метрике", result, flags=re.IGNORECASE)
        result = re.sub(r"\s*\.\s*метрике\b", ". Метрике", result, flags=re.IGNORECASE)
        result = re.sub(r"\bна метрике\b", "по метрике", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\.\.", ".", result)
        result = re.sub(r"\n\s*\n+", "\n", result)
        result = self._enforce_external_sharing_policy(result)
        result = self._apply_case_prompt_grammar_rules(result)
        result = self._humanize_generated_case_language(result)
        result = self._normalize_prompt_sentences(result)
        return result.strip()

    def _fallback_proofread_case_prompt_text(self, text: str) -> str:
        result = text or ""
        replacements = {
            "Интерьюер": "Интервьюер",
            "интерьюер": "интервьюер",
            "не указаны. .": "не указаны.",
            "не указана. .": "не указана.",
            "Не указаны. .": "Не указаны.",
            "Не указана. .": "Не указана.",
            "ввиде": "в виде",
            "т.к.": "так как",
        }
        for source, target in replacements.items():
            result = result.replace(source, target)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\n\s*\n+", "\n", result)
        result = re.sub(r"([.!?])\1+", r"\1", result)
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)
        result = self._enforce_external_sharing_policy(result)
        result = self._apply_case_prompt_grammar_rules(result)
        result = self._humanize_generated_case_language(result)
        result = self._normalize_prompt_sentences(result)
        return result.strip()



    def _validate_case_prompt_result(self, text: str, *, fallback: str) -> str:
        candidate = (text or "").strip()
        fallback = (fallback or "").strip()
        if not candidate:
            return fallback
        if len(candidate) < max(120, int(len(fallback) * 0.45)):
            return fallback
        required_markers = ("Ваша задача",)
        if any(marker in fallback and marker not in candidate for marker in required_markers):
            return fallback
        if fallback.count("«") and candidate.count("«") < fallback.count("«"):
            return fallback
        if self._has_case_prompt_quality_issues(candidate):
            cleaned_fallback = self._fallback_proofread_case_prompt_text(fallback)
            if self._has_case_prompt_quality_issues(cleaned_fallback):
                return fallback
            return cleaned_fallback
        return candidate

    def _has_case_prompt_quality_issues(self, text: str) -> bool:
        candidate = (text or "").strip()
        if not candidate:
            return True
        for pattern in CASE_PROMPT_FORBIDDEN_PATTERNS:
            if re.search(pattern, candidate, flags=re.IGNORECASE):
                return True
        if "Интерьюер" in candidate:
            return True
        if ".." in candidate or ". ." in candidate:
            return True
        return False
