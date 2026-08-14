from __future__ import annotations

import json
import re
from typing import Any

from Api.case_context_builder import build_case_context
from Api.case_text_cleanup import cleanup_case_list, cleanup_case_text, join_case_list


class CasePersonalizationMixin:
    def generate_personalization_map(
        self,
        *,
        full_name: str | None,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        user_profile: dict[str, Any] | None,
        case_type_code: str | None = None,
        case_title: str,
        case_context: str,
        case_task: str,
        planned_total_duration_min: int | None,
        personalization_variables: str | None,
        case_specificity: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        placeholders = self._extract_placeholders(
            "\n".join(filter(None, [case_context, case_task, personalization_variables or ""]))
        )
        placeholders = list(placeholders)

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
        fallback = self._fallback_personalization_map(
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
        if (
            not self.enabled
            or not placeholders
            or not self._should_use_llm_personalization_map(
                position=position,
                duties=duties,
                company_industry=company_industry,
                case_type_code=case_type_code,
                placeholders=placeholders,
            )
        ):
            return fallback

        profile_context = user_profile or {}
        prompt = (
            "Сформируй значения переменных персонализации для кейса.\n"
            "Нужно вернуть только JSON-объект вида "
            '{"values":{"placeholder":"value"}} без пояснений.\n'
            "Правила:\n"
            "1. Используй только перечисленные переменные.\n"
            "2. Опирайся только на шаблон кейса и профиль пользователя.\n"
            "3. Нельзя менять центральный конфликт кейса, тип кейса, проверяемые навыки и общий масштаб ситуации.\n"
            "4. Значения должны быть реалистичными, короткими, конкретными и пригодными для прямой подстановки в текст.\n"
            "5. Не добавляй фигурные скобки в ключи.\n"
            "6. Если значение нельзя уверенно вывести, используй наиболее уместный вариант из контекста кейса и профиля.\n"
            "7. Не придумывай лишние детали, если их нельзя уверенно вывести из профиля и кейса.\n"
            "8. Не используй абстрактные формулировки вроде 'операционная команда', 'ключевой рабочий процесс' или 'рабочая система'. "
            "Подставляй правдоподобные сущности: очередь тикетов, обработка инцидентов, Service Desk, группа сопровождения, окно согласования, журнал ошибок.\n\n"
            f"Пользователь: {full_name or 'не указано'}\n"
            f"Должность: {position or 'не указана'}\n"
            f"Обязанности: {duties or 'не указаны'}\n"
            f"Индустрия: {company_industry or 'не указана'}\n"
            f"Роль: {role_name or 'не определена'}\n"
            f"Профиль пользователя: {json.dumps(profile_context, ensure_ascii=False, default=str)}\n\n"
            f"Кейс: {case_title}\n"
            f"Контекст кейса: {case_context or 'не указан'}\n"
            f"Задача кейса: {case_task or 'не указана'}\n"
            f"Контекстная конкретика кейса: {json.dumps(case_specificity, ensure_ascii=False, default=str)}\n"
            f"Переменные: {json.dumps(placeholders, ensure_ascii=False, default=str)}\n"
            f"Базовые fallback-значения: {json.dumps(fallback, ensure_ascii=False, default=str)}"
        )
        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Ты заполняешь переменные персонализации кейса для HR-assessment системы. "
                            "Возвращай только JSON без markdown и комментариев."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                routing_key=(
                    f"user:{user_identifier}"
                    if str(user_identifier or "").strip()
                    else f"profile:{full_name or ''}|{position or ''}|{company_industry or ''}"
                ),
            )
            parsed = self._parse_json(raw)
            values = parsed.get("values") if isinstance(parsed, dict) else None
            if not isinstance(values, dict):
                return fallback
            result: dict[str, str] = {}
            for placeholder in placeholders:
                generated = values.get(placeholder)
                if generated is None:
                    generated = fallback.get(placeholder, "")
                if self._should_prefer_fallback_personalization_value(
                    placeholder=placeholder,
                    generated=generated,
                    fallback_value=fallback.get(placeholder, ""),
                ):
                    generated = fallback.get(placeholder, "")
                result[placeholder] = self._normalize_placeholder_value(
                    placeholder,
                    self._sanitize_personalization_value(str(generated)),
                )
            return {key: cleanup_case_text(value) for key, value in result.items()}
        except Exception:
            return fallback

    def _should_use_llm_personalization_map(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        case_type_code: str | None,
        placeholders: list[str] | None,
    ) -> bool:
        if not self.enabled:
            return False
        if not placeholders:
            return False
        family = self._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        type_code = str(case_type_code or "").strip().upper()
        # After the domain-driven refactor the local personalization layer is
        # good enough for recognized professional domains and is much faster.
        if family != "generic" and type_code in {
            "F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10", "F11", "F12",
        }:
            return False
        return True

    def generate_case_specificity(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        user_profile: dict[str, Any] | None,
        case_type_code: str | None,
        case_title: str,
        case_context: str,
        case_task: str,
    ) -> dict[str, Any]:
        cache_key = (
            str(position or "").strip().lower(),
            str(duties or "").strip().lower(),
            str(company_industry or "").strip().lower(),
            str(role_name or "").strip().lower(),
            str(case_type_code or "").strip().upper(),
            str(case_title or "").strip().lower(),
        )
        cached = self._case_specificity_cache.get(cache_key)
        if cached is not None:
            return dict(cached)

        fallback = self._fallback_case_specificity(
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
        if not self._should_use_llm_case_specificity(
            position=position,
            duties=duties,
            company_industry=company_industry,
            case_type_code=case_type_code,
        ):
            self._case_specificity_cache[cache_key] = dict(fallback)
            return fallback
        if not self.enabled:
            self._case_specificity_cache[cache_key] = dict(fallback)
            return fallback

        prompt = (
            "Сгенерируй живую и реалистичную конкретику для бизнес-кейса. "
            "Нужно учитывать сферу компании, должность и обязанности пользователя. "
            "Верни только JSON без пояснений.\n"
            "Поля JSON:\n"
            "- workflow_label: понятное название процесса для пользователя;\n"
            "- workflow_name: более предметное внутреннее название процесса;\n"
            "- system_name: правдоподобная рабочая система;\n"
            "- channel: канал, где появляется сообщение или задача;\n"
            "- source_of_truth: где пользователь видит внутренние данные;\n"
            "- request_type: тип запроса или ситуации;\n"
            "- ticket_titles: массив из 2-3 правдоподобных названий тикетов/задач/инцидентов;\n"
            "- stage_names: массив из 3-4 правдоподобных названий этапов;\n"
            "- idea_label: короткое реалистичное название идеи или улучшения;\n"
            "- current_state: 1-2 предложения о том, как процесс сейчас реально идет и где именно возникает затык;\n"
            "- bottleneck: короткое описание узкого места или повторяющегося сбоя;\n"
            "- idea_description: 1 предложение о том, как именно должна работать обсуждаемая идея;\n"
            "- message_quote: одно короткое прямое сообщение участника, если оно уместно для кейса;\n"
            "- primary_stakeholder: основной участник ситуации;\n"
            "- adjacent_team: смежная команда или функция;\n"
            "- business_impact: понятное бизнес-последствие.\n\n"
            "Правила:\n"
            "1. Не меняй тип кейса, центральный конфликт и масштаб ситуации.\n"
            "2. Не добавляй экзотических деталей, которых не требует контекст.\n"
            "3. Сообщение участника должно звучать естественно и по-деловому.\n"
            "4. Не добавляй внутренние ID, номера карточек или технические коды в прямую речь участника.\n"
            "5. Конкретика должна помогать сделать кейс живее, а не переписывать его заново.\n"
            "6. Для кейсов F09 и F10 обязательно конкретно опиши текущее узкое место и саму идею, а не только назови их.\n\n"
            f"Тип кейса: {case_type_code or 'не указан'}\n"
            f"Должность: {position or 'не указана'}\n"
            f"Обязанности: {duties or 'не указаны'}\n"
            f"Сфера компании: {company_industry or 'не указана'}\n"
            f"Роль пользователя: {role_name or 'не указана'}\n"
            f"Профиль пользователя: {json.dumps(user_profile or {}, ensure_ascii=False, default=str)}\n"
            f"Название кейса: {case_title}\n"
            f"Контекст кейса: {case_context or 'не указан'}\n"
            f"Задание кейса: {case_task or 'не указано'}\n"
            f"Fallback-конкретика: {json.dumps(fallback, ensure_ascii=False, default=str)}"
        )
        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Ты делаешь бизнес-кейсы живыми и предметными, не ломая их методический смысл.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            parsed = self._parse_json(raw)
            if not isinstance(parsed, dict):
                self._case_specificity_cache[cache_key] = dict(fallback)
                return fallback
            normalized = self._normalize_case_specificity_with_profile(
                parsed,
                fallback,
                position=position,
                duties=duties,
                company_industry=company_industry,
            )
            self._case_specificity_cache[cache_key] = dict(normalized)
            return normalized
        except Exception:
            self._case_specificity_cache[cache_key] = dict(fallback)
            return fallback

    def _should_use_llm_case_specificity(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        case_type_code: str | None,
    ) -> bool:
        if not self.enabled:
            return False
        family = self._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        type_code = str(case_type_code or "").strip().upper()
        strong_fallback_families = {
            "it_support",
            "business_analysis",
            "horeca",
            "maritime",
            "engineering",
            "beauty",
            "food_production",
            "client_service",
            "learning_and_development",
            "hr",
            "finance",
            "logistics",
        }
        if family in strong_fallback_families and type_code in {
            "F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10", "F11", "F12",
        }:
            return False
        if family == "generic":
            return True
        return True

    def apply_personalization(self, template: str | None, values: dict[str, str]) -> str:
        if not template:
            return ""
        result = template
        for key, value in values.items():
            result = result.replace("{" + key + "}", value)
        return result

    def _extract_placeholders(self, text: str) -> list[str]:
        values = []
        seen: set[str] = set()
        for match in re.findall(r"\{([^{}]+)\}", text):
            key = match.strip()
            if key and key not in seen:
                seen.add(key)
                values.append(key)
        return values

    def _fallback_personalization_map(
        self,
        *,
        placeholders: list[str],
        position: str | None,
        duties: str | None,
        company_industry: str | None,
        role_name: str | None,
        user_profile: dict[str, Any] | None,
        planned_total_duration_min: int | None,
        case_type_code: str | None = None,
        case_title: str | None = None,
        case_context: str | None = None,
        case_task: str | None = None,
        case_specificity: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        normalized_company_industry = self.normalize_company_industry(
            company_industry=company_industry,
            position=position,
            duties=duties,
        )
        domain_profile = self._extract_domain_profile_from_user_profile(user_profile)
        user_work_context = self._extract_user_work_context_from_profile(user_profile)
        adaptation_rules = (user_profile or {}).get("adaptation_rules_for_cases") or {}
        inferred_domain = self._infer_domain(position=position, duties=duties, company_industry=company_industry)
        prioritize_runtime_domain = self._should_prioritize_runtime_domain(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        runtime_domain_family = self._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        domain = str(
            (inferred_domain if prioritize_runtime_domain else None)
            or domain_profile.get("domain_label")
            or user_work_context.get("user_domain")
            or (user_profile or {}).get("user_domain")
            or normalized_company_industry
            or inferred_domain
        )
        profile_context = user_profile or {}
        profile_processes = (
            user_work_context.get("user_processes")
            or domain_profile.get("processes")
            or profile_context.get("user_processes")
            or []
        )
        profile_tasks = (
            user_work_context.get("user_tasks")
            or domain_profile.get("tasks")
            or profile_context.get("user_tasks")
            or []
        )
        profile_stakeholders = (
            user_work_context.get("user_stakeholders")
            or domain_profile.get("stakeholders")
            or profile_context.get("user_stakeholders")
            or []
        )
        profile_risks = (
            user_work_context.get("user_risks")
            or domain_profile.get("risks")
            or profile_context.get("user_risks")
            or []
        )
        profile_constraints = (
            user_work_context.get("user_constraints")
            or domain_profile.get("constraints")
            or profile_context.get("user_constraints")
            or []
        )
        profile_systems = domain_profile.get("systems") or []
        profile_artifacts = domain_profile.get("artifacts") or []
        profile_processes = cleanup_case_list(profile_processes, limit=4)
        profile_tasks = cleanup_case_list(profile_tasks, limit=5)
        profile_stakeholders = cleanup_case_list(profile_stakeholders, limit=4)
        profile_risks = cleanup_case_list(profile_risks, limit=4)
        profile_constraints = cleanup_case_list(profile_constraints, limit=3)
        profile_systems = cleanup_case_list(profile_systems, limit=3)
        profile_artifacts = cleanup_case_list(profile_artifacts, limit=4)
        if prioritize_runtime_domain:
            profile_processes = []
            profile_tasks = []
            profile_stakeholders = []
            profile_risks = []
            profile_constraints = []
            profile_systems = []
            profile_artifacts = []
        role_vocabulary = profile_context.get("role_vocabulary") or {}
        process = profile_processes[0] if profile_processes else self._infer_process(position=position, duties=duties)
        inferred_client_type = self._infer_client_type(position=position, duties=duties)
        client_type = inferred_client_type
        if profile_stakeholders:
            first_stakeholder = str(profile_stakeholders[0] or "").strip().lower()
            if any(word in first_stakeholder for word in ("клиент", "заказчик", "гость", "пользователь")):
                client_type = str(profile_stakeholders[0]).strip()
        scenario = self._build_case_scenario_seed(
            domain=domain,
            process=process,
            position=position,
            duties=duties,
            role_name=role_name,
        )
        scenario = self._apply_profile_case_context_overrides(
            scenario,
            user_profile=user_profile,
        )
        scenario = self._enrich_scenario_seed(
            scenario,
            domain=domain,
            process=process,
            position=position,
            duties=duties,
            role_name=role_name,
            case_type_code=case_type_code,
            case_title=case_title,
        )
        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=position,
                duties=duties,
                company_industry=company_industry,
                role_name=role_name,
                user_profile=user_profile,
                case_type_code=case_type_code,
                case_title=case_title or "",
                case_context=case_context or "",
                case_task=case_task or "",
            ),
        )
        case_context = build_case_context(
            domain_family=runtime_domain_family if prioritize_runtime_domain else str(domain_profile.get("domain_family") or domain_profile.get("domain_code") or ""),
            case_type_code=case_type_code,
            profile_processes=profile_processes,
            profile_tasks=profile_tasks,
            profile_stakeholders=profile_stakeholders,
            profile_risks=profile_risks,
            profile_constraints=profile_constraints,
            profile_systems=profile_systems,
            profile_artifacts=profile_artifacts,
            case_specificity=specificity,
        )
        specificity = self._specialize_specificity_from_case_frame(
            specificity,
            case_context,
            runtime_domain_family if prioritize_runtime_domain else str(domain_profile.get("domain_family") or domain_profile.get("domain_code") or ""),
        )
        case_context = build_case_context(
            domain_family=runtime_domain_family if prioritize_runtime_domain else str(domain_profile.get("domain_family") or domain_profile.get("domain_code") or ""),
            case_type_code=case_type_code,
            profile_processes=profile_processes,
            profile_tasks=profile_tasks,
            profile_stakeholders=profile_stakeholders,
            profile_risks=profile_risks,
            profile_constraints=profile_constraints,
            profile_systems=profile_systems,
            profile_artifacts=profile_artifacts,
            case_specificity=specificity,
        )
        specificity["_case_frame"] = dict(case_context or {})
        scenario_stakeholder_list = str(scenario.get("stakeholder_named_list") or "").strip()
        stakeholder_value = self._select_primary_actor(
            case_context.get("key_participant")
            or scenario_stakeholder_list
            or (profile_stakeholders[0] if profile_stakeholders else specificity.get("primary_stakeholder")),
            grammatical_case="nominative",
        )
        stakeholder_list_value = (
            join_case_list(case_context.get("participants"), limit=3)
            or scenario_stakeholder_list
            or str(specificity.get("primary_stakeholder") or "")
        )
        process_list_value = join_case_list(case_context.get("processes"), limit=3)
        task_list_value = join_case_list(case_context.get("tasks"), limit=3)
        risk_list_value = join_case_list(profile_risks, limit=2)
        constraint_list_value = join_case_list(profile_constraints, limit=2)
        systems_value = join_case_list(case_context.get("systems"), limit=2)
        artifacts_value = join_case_list(case_context.get("artifacts"), limit=3)
        work_entities_value = artifacts_value or ", ".join(str(item).strip() for item in profile_tasks[:2] if str(item).strip())
        escalation_target = self._select_escalation_target(stakeholder_value, specificity.get("adjacent_team"))
        adaptation_include_value = join_case_list(adaptation_rules.get("what_to_include") or [], limit=3)
        adaptation_avoid_value = join_case_list(adaptation_rules.get("what_to_avoid") or [], limit=3)
        recommended_contexts_value = join_case_list(adaptation_rules.get("recommended_case_contexts") or [], limit=3)
        adaptation_hint = str(adaptation_rules.get("how_to_adapt_scenarios") or "").strip()
        values = {
            "роль_кратко": role_name or position or "специалист по направлению",
            "должность": position or role_name or "специалист по направлению",
            "контекст обязанностей": duties or task_list_value or "координацию рабочих задач и сопровождение внутренних процессов",
            "сфера деятельности компании": normalized_company_industry or domain,
            "процесс/сервис": case_context.get("process") or specificity["workflow_label"],
            "операция": specificity["critical_step"],
            "регламент": specificity["source_of_truth"],
            "отклонение": case_context.get("problem_event") or scenario["issue_summary"],
            "кому эскалировать": escalation_target,
            "полномочия": case_context.get("constraint") or (profile_constraints[0] if profile_constraints else scenario["limits_short"]),
            "система": (case_context.get("systems") or profile_systems or [specificity["system_name"]])[0],
            "тип клиента": client_type,
            "канал": self._normalize_channel_phrase(specificity["channel"]),
            "описание проблемы": case_context.get("problem_event") or (specificity["ticket_titles"][0] if specificity["ticket_titles"] else (profile_risks[0] if profile_risks else scenario["issue_summary"])),
            "риск": self._normalize_risk_phrase(case_context.get("risk") or scenario["incident_impact"] or specificity["business_impact"]),
            "SLA/срок": scenario["deadline"],
            "критичное действие / этап процесса": case_context.get("expected_step") or specificity["critical_step"],
            "источник данных / карточка обращения / переписка / статус в системе": artifacts_value or case_context.get("work_object") or specificity["source_of_truth"],
            "источник данных / переписка / карточка / статус": artifacts_value or case_context.get("work_object") or specificity["source_of_truth"],
            "ограничения/полномочия": case_context.get("constraint") or (profile_constraints[0] if profile_constraints else "можете уточнять детали, согласовывать корректирующие действия и эскалировать проблему профильной команде"),
            "масштаб кейса": self._resolve_role_scope(role_name),
            "контур": scenario["team_contour"],
            "тикеты": ", ".join(specificity["ticket_titles"]) or task_list_value or scenario["work_items"],
            "ошибки": scenario["error_examples"],
            "рабочий процесс": process_list_value or specificity["workflow_name"],
            "имена участников": scenario["participant_names"],
            "названия тикетов": ", ".join(specificity["ticket_titles"]) or scenario["ticket_titles"],
            "тип клиента": client_type,
            "тип запроса": specificity["request_type"],
            "данные/источники": artifacts_value or scenario["data_sources"],
            "данные/логи": artifacts_value or scenario["data_sources"],
            "стейкхолдер": stakeholder_value,
            "стейкхолдеры": stakeholder_list_value or stakeholder_value,
            "ключевые стейкхолдеры": scenario.get("stakeholder_named_list") or stakeholder_list_value or stakeholder_value,
            "смежный отдел": specificity["adjacent_team"],
            "поведение/проблема": scenario["behavior_issue"],
            "пример поведения": scenario["behavior_issue"],
            "контекст команды/проекта": scenario["team_context"],
            "тип команды": scenario.get("team_scope_label") or scenario["team_contour"],
            "что нужно": specificity["workflow_label"],
            "влияние на бизнес": specificity["business_impact"],
            "влияние": specificity["business_impact"],
            "изменение показателей": scenario.get("metric_delta") or "",
            "срок": scenario["deadline"],
            "сроки": scenario["deadline"],
            "ограничения": case_context.get("constraint") or (profile_constraints[0] if profile_constraints else scenario["limits_short"]),
            "ограничения времени/ресурса": scenario.get("time_resource_limit") or scenario["deadline"],
            "процесс": case_context.get("process") or (profile_processes[0] if profile_processes else specificity["workflow_label"]),
            "контекст процесса/продукта": process_list_value or specificity["workflow_label"],
            "тип инцидента": scenario["incident_type"],
            "последствия": scenario["incident_impact"],
            "команды": scenario["involved_teams"],
            "список задач": task_list_value or scenario["work_items"],
            "ресурс/люди": scenario.get("resource_profile") or task_list_value or scenario["work_items"],
            "ресурсы": scenario.get("resource_profile") or task_list_value or scenario["work_items"],
            "метрика": self._normalize_metric_object_phrase(scenario.get("metric_label") or specificity["business_impact"]),
            "метрики": scenario.get("metric_label") or specificity["business_impact"],
            "критерии бизнеса": scenario.get("business_criteria") or specificity["business_impact"],
            "пользователи/клиенты": scenario.get("audience_label") or client_type,
            "стратегическая цель / направление / систему": scenario.get("strategic_scope") or specificity["workflow_label"],
            "зависимости": scenario.get("dependencies") or specificity["adjacent_team"],
            "решение/дилемма": scenario.get("decision_theme") or scenario["issue_summary"],
            "данные": scenario["data_sources"],
            "длительность смены": scenario.get("shift_duration") or "",
            "название смены": scenario.get("shift_name") or "",
            "фио участников": scenario.get("participant_names") or "",
            "названия этапов": ", ".join(specificity["stage_names"]),
            "этапы": ", ".join(specificity["stage_names"]),
            "этап/шаг": specificity["stage_names"][0] if specificity["stage_names"] else scenario["critical_step"],
            "идея": specificity["idea_label"],
            "название идеи": specificity["idea_label"],
            "типовые процессы": process_list_value,
            "типовые задачи": task_list_value,
            "типовые риски": risk_list_value,
            "типовые ограничения": constraint_list_value,
            "типовые системы": systems_value,
            "типовые артефакты": artifacts_value,
            "правила адаптации кейсов": adaptation_hint,
            "что включать в кейсы": adaptation_include_value,
            "чего избегать в кейсах": adaptation_avoid_value,
            "рекомендуемые контексты кейсов": recommended_contexts_value,
        }
        if role_vocabulary.get("work_entities"):
            values["рабочие сущности"] = join_case_list(role_vocabulary["work_entities"], limit=3)
        elif work_entities_value:
            values["рабочие сущности"] = work_entities_value
        if role_vocabulary.get("participants"):
            values["типовые участники"] = join_case_list(role_vocabulary["participants"], limit=3)
        elif stakeholder_list_value:
            values["типовые участники"] = stakeholder_list_value
        values["проблемная ситуация"] = case_context.get("problem_event") or values.get("описание проблемы", "")
        values["ключевой участник"] = stakeholder_value
        values["рабочая сущность"] = case_context.get("work_object") or artifacts_value
        values["критичное ограничение"] = case_context.get("constraint") or values.get("ограничения", "")
        values["основной риск"] = case_context.get("risk") or values.get("риск", "")
        values["ожидаемый следующий шаг"] = case_context.get("expected_step") or values.get("критичное действие / этап процесса", "")
        result: dict[str, str] = {}
        for placeholder in placeholders:
            result[placeholder] = self._normalize_placeholder_value(
                placeholder,
                self._sanitize_personalization_value(
                    values.get(placeholder, self._generic_value(placeholder, domain, process, client_type))
                ),
            )
        return {key: cleanup_case_text(value) for key, value in result.items()}

    def _apply_profile_case_context_overrides(
        self,
        scenario: dict[str, Any],
        *,
        user_profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        result = dict(scenario or {})
        if not isinstance(user_profile, dict):
            return result

        domain_profile = self._extract_domain_profile_from_user_profile(user_profile)
        user_work_context = self._extract_user_work_context_from_profile(user_profile)
        role_limits = user_profile.get("role_limits") or {}
        role_vocabulary = user_profile.get("role_vocabulary") or {}
        context_vars = user_profile.get("user_context_vars") or {}

        processes = cleanup_case_list(
            user_work_context.get("user_processes")
            or domain_profile.get("processes")
            or [],
            limit=4,
        )
        tasks = cleanup_case_list(
            user_work_context.get("user_tasks")
            or domain_profile.get("tasks")
            or [],
            limit=5,
        )
        stakeholders = cleanup_case_list(
            user_work_context.get("user_stakeholders")
            or domain_profile.get("stakeholders")
            or role_vocabulary.get("participants")
            or [],
            limit=4,
        )
        risks = cleanup_case_list(
            user_work_context.get("user_risks")
            or domain_profile.get("risks")
            or user_profile.get("user_risks")
            or [],
            limit=4,
        )
        constraints = cleanup_case_list(
            user_work_context.get("user_constraints")
            or domain_profile.get("constraints")
            or user_profile.get("user_constraints")
            or [],
            limit=4,
        )
        systems = cleanup_case_list(
            user_profile.get("user_systems")
            or domain_profile.get("systems")
            or [],
            limit=3,
        )
        artifacts = cleanup_case_list(
            user_profile.get("user_artifacts")
            or domain_profile.get("artifacts")
            or [],
            limit=4,
        )
        metrics = cleanup_case_list(
            user_profile.get("user_success_metrics")
            or domain_profile.get("success_metrics")
            or [],
            limit=3,
        )

        department = cleanup_case_text(
            str(context_vars.get("department_label") or context_vars.get("team_label") or context_vars.get("unit_label") or "")
        )
        if not department:
            department = cleanup_case_text(str(role_limits.get("interaction_scope") or ""))

        if processes:
            primary_process = processes[0]
            result["workflow_name"] = primary_process
            result["workflow_label"] = primary_process
        if department:
            result["team_contour"] = department
            result["team_context"] = department
        elif processes:
            result["team_context"] = processes[0]
        if tasks:
            result["work_items"] = join_case_list(tasks, limit=3)
            result["request_type"] = tasks[0]
            if not result.get("critical_step"):
                result["critical_step"] = tasks[0]
        if stakeholders:
            result["primary_stakeholder"] = join_case_list(stakeholders, limit=3)
            if len(stakeholders) > 1:
                result["adjacent_team"] = stakeholders[1]
        if constraints:
            result["limits_short"] = join_case_list(constraints, limit=2)
        if risks:
            result["business_impact"] = join_case_list(risks, limit=2)
        elif metrics:
            result["business_impact"] = join_case_list(metrics, limit=2)
        if systems or artifacts:
            source_parts: list[str] = []
            source_parts.extend(systems[:2])
            source_parts.extend(artifacts[:2])
            result["source_of_truth"] = join_case_list(source_parts, limit=3)
            if systems:
                result["system_name"] = systems[0]
        if tasks and not result.get("issue_summary"):
            result["issue_summary"] = f"в рабочем контуре возникла проблема вокруг «{tasks[0]}»"
        if role_vocabulary.get("participants") and not result.get("participant_names"):
            result["participant_names"] = join_case_list(role_vocabulary.get("participants") or [], limit=3)
        return result

    def _normalize_placeholder_value(self, placeholder: str, value: str) -> str:
        clean = self._sanitize_personalization_value(value)
        if not clean:
            return ""
        label = str(placeholder or "").lower()
        if label == "ограничения" or "ограничения" in label:
            return self._normalize_constraint_phrase(clean)
        if "источник данных / переписка / карточка / статус" in label:
            return self._normalize_access_source_phrase(clean)
        if "данные/источники" in label or "источник данных" in label:
            return self._normalize_data_sources_phrase(clean)
        if "sla/срок" in label:
            return self._normalize_sla_phrase(clean)
        if label == "срок" or "сроки" in label:
            return self._normalize_deadline_phrase(clean)
        if "критичное действие" in label or "этап процесса" in label:
            return self._normalize_action_step_phrase(clean)
        if "канал" in label:
            return self._normalize_channel_phrase(clean)
        if label == "риск" or " риск" in f" {label} ":
            return self._normalize_risk_phrase(clean)
        if "стейкхолдеры" in label:
            if re.search(r"[А-ЯЁA-Z][а-яёa-z-]+\s+[А-ЯЁA-Z][а-яёa-z-]+", clean):
                return self._normalize_named_stakeholder_list_phrase(clean, grammatical_case="genitive")
            return self._normalize_stakeholder_list_phrase(clean, grammatical_case="genitive")
        if "стейкхолдер" in label:
            return self._normalize_stakeholder_phrase(clean, grammatical_case="nominative")
        if "зависимости" in label:
            return self._normalize_dependency_phrase(clean)
        if "критерии бизнеса" in label:
            return self._normalize_business_criteria_phrase(clean)
        return clean

    def _should_prefer_fallback_personalization_value(
        self,
        *,
        placeholder: str,
        generated: Any,
        fallback_value: Any,
    ) -> bool:
        label = str(placeholder or "").lower()
        generated_text = self._sanitize_personalization_value(str(generated or ""))
        fallback_text = self._sanitize_personalization_value(str(fallback_value or ""))
        if not generated_text or not fallback_text:
            return False

        role_anchored_placeholders = (
            "стейкхолдеры",
            "стейкхолдер",
            "ключевые стейкхолдеры",
            "типовые участники",
            "рабочие сущности",
            "ключевой участник",
            "рабочая сущность",
            "критичное ограничение",
            "основной риск",
            "ожидаемый следующий шаг",
        )
        if not any(token in label for token in role_anchored_placeholders):
            return False

        if self._contains_named_people(generated_text) and not self._contains_named_people(fallback_text):
            return True

        return False

    def _contains_named_people(self, text: str) -> bool:
        cleaned = str(text or "").strip()
        if not cleaned:
            return False
        return bool(
            re.search(r"\b[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+\b", cleaned)
            or re.search(r"\b[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+\b", cleaned)
        )

    def _normalize_constraint_phrase(self, text: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""

        lowered = normalized.lower()
        exact_replacements = {
            "действуете в рамках регламента первой линии": "работе в рамках регламента первой линии",
            "нельзя закрывать заявку без подтверждения результата и нужно фиксировать все действия в системе": "закрытию заявок без подтверждения результата и фиксации всех действий в системе",
            "нельзя закрывать обращение без подтверждения результата и нужно фиксировать все действия в системе": "закрытию обращений без подтверждения результата и фиксации всех действий в системе",
            "нужно фиксировать все действия в системе": "фиксации всех действий в системе",
        }
        if lowered in exact_replacements:
            return exact_replacements[lowered]

        normalized = re.sub(
            r"^\s*действуете\s+в\s+рамках\s+",
            "работе в рамках ",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"^\s*нельзя\s+закрывать\s+заявк[ауи]\s+без\s+подтверждения\s+результата\s+и\s+нужно\s+фиксировать\s+все\s+действия\s+в\s+системе\s*$",
            "закрытию заявок без подтверждения результата и фиксации всех действий в системе",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(
            r"^\s*нельзя\s+закрывать\s+обращени[ея]\s+без\s+подтверждения\s+результата\s+и\s+нужно\s+фиксировать\s+все\s+действия\s+в\s+системе\s*$",
            "закрытию обращений без подтверждения результата и фиксации всех действий в системе",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"\s{2,}", " ", normalized).strip()
        return normalized

    def _normalize_stakeholder_list_phrase(self, text: str, *, grammatical_case: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        parts = [part.strip() for part in re.split(r",|\s+и\s+", normalized) if part.strip()]
        if not parts:
            return self._normalize_stakeholder_phrase(normalized, grammatical_case=grammatical_case)
        converted = [
            self._normalize_stakeholder_phrase(part, grammatical_case=grammatical_case)
            for part in parts
        ]
        if len(converted) == 1:
            return converted[0]
        if len(converted) == 2:
            return f"{converted[0]} и {converted[1]}"
        return ", ".join(converted[:-1]) + f" и {converted[-1]}"

    def _to_genitive_word(self, word: str) -> str:
        value = str(word or "").strip()
        if not value:
            return ""
        lower = value.lower()
        exact = {
            "ольга": "Ольги",
            "антон": "Антона",
            "илья": "Ильи",
            "марина": "Марины",
            "светлана": "Светланы",
            "алексей": "Алексея",
            "сергей": "Сергея",
            "роман": "Романа",
            "дарья": "Дарьи",
            "никита": "Никиты",
            "константин": "Константина",
            "павел": "Павла",
            "татьяна": "Татьяны",
            "денис": "Дениса",
            "анна": "Анны",
            "дмитрий": "Дмитрия",
            "игорь": "Игоря",
            "виктор": "Виктора",
            "ксения": "Ксении",
            "елена": "Елены",
        }
        if lower in exact:
            return exact[lower]
        if re.search(r"(ова|ева|ина|ына|ая)$", lower):
            return value[:-1] + "ой"
        if re.search(r"(ов|ев|ин|ын)$", lower):
            return value + "а"
        if lower.endswith("ий"):
            return value[:-2] + "ия"
        if lower.endswith("ей"):
            return value[:-2] + "ея"
        if lower.endswith("й"):
            return value[:-1] + "я"
        if lower.endswith("ь"):
            return value[:-1] + "я"
        if lower.endswith("я"):
            return value[:-1] + "и"
        if lower.endswith("а"):
            base = value[:-1]
            return base + ("и" if base.lower().endswith(("г", "к", "х", "ж", "ч", "ш", "щ")) else "ы")
        if re.search(r"[бвгджзклмнпрстфхцчшщ]$", lower):
            return value + "а"
        return value

    def _normalize_named_stakeholder_phrase(self, text: str, *, grammatical_case: str) -> str:
        normalized = str(text or "").strip()
        if not normalized or grammatical_case != "genitive":
            return normalized
        title_map = {
            "руководитель смены": "руководителя смены",
            "руководитель смены поддержки": "руководителя смены поддержки",
            "инженер второй линии": "инженера второй линии",
            "специалист по эскалациям": "специалиста по эскалациям",
            "координатор очереди": "координатора очереди",
            "внутренний заказчик": "внутреннего заказчика",
            "заказчик": "заказчика",
            "пользователь": "пользователя",
            "гость": "гостя",
            "администратор зала": "администратора зала",
            "старший смены": "старшего смены",
            "капитан": "капитана",
            "старший помощник": "старшего помощника",
            "вахтенный офицер": "вахтенного офицера",
            "мастер смены": "мастера смены",
            "технолог": "технолога",
            "контролер отк": "контролера ОТК",
            "контролёр отк": "контролера ОТК",
            "руководитель участка": "руководителя участка",
            "смежный специалист": "смежного специалиста",
            "координатор": "координатора",
            "аналитик": "аналитика",
            "тимлид разработки": "тимлида разработки",
            "сотрудник смены": "сотрудника смены",
            "специалист первой линии": "специалиста первой линии",
            "коллега": "коллеги",
        }
        person_pattern = re.compile(r"^(?P<title>.+?)\s+(?P<first>[А-ЯЁA-Z][а-яёa-z-]+)\s+(?P<last>[А-ЯЁA-Z][а-яёa-z-]+)$")
        match = person_pattern.match(normalized)
        if match:
            title = match.group("title").strip()
            first = self._to_genitive_word(match.group("first"))
            last = self._to_genitive_word(match.group("last"))
            title_gen = title_map.get(title.lower(), self._normalize_stakeholder_phrase(title, grammatical_case="genitive"))
            return f"{title_gen} {first} {last}".strip()
        return normalized

    def _normalize_named_stakeholder_list_phrase(self, text: str, *, grammatical_case: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        parts = [part.strip() for part in re.split(r",|\s+и\s+", normalized) if part.strip()]
        converted = [self._normalize_named_stakeholder_phrase(part, grammatical_case=grammatical_case) for part in parts]
        if len(converted) == 1:
            return converted[0]
        if len(converted) == 2:
            return f"{converted[0]} и {converted[1]}"
        return ", ".join(converted[:-1]) + f" и {converted[-1]}"

    def _normalize_data_sources_phrase(self, text: str) -> str:
        normalized = f" {text.strip()} "
        replacements = {
            " бриф на обучение ": " брифа на обучение ",
            " тз подрядчику ": " ТЗ подрядчику ",
            " программа курса ": " программы курса ",
            " финальная программа курса ": " финальной программы курса ",
            " карточка обучения ": " карточки обучения ",
            " карточка программы ": " карточки программы ",
            " карточка запуска программы ": " карточки запуска программы ",
            " дата старта в lms/hrm ": " даты старта в LMS/HRM ",
            " комментарии заказчика ": " комментариев заказчика ",
            " комментарии внутреннего эксперта ": " комментариев внутреннего эксперта ",
            " комментарии руководителя подразделения ": " комментариев руководителя подразделения ",
            " анкеты обратной связи ": " анкет обратной связи ",
            " комментарии участников ": " комментариев участников ",
            " карточка результатов пилота ": " карточки результатов пилота ",
            " история договоренностей ": " истории договоренностей ",
            " журнал задач по программе ": " журнала задач по программе ",
            " список участников ": " списка участников ",
            " календарь обучения ": " календаря обучения ",
            " график подразделения ": " графика подразделения ",
            " рабочий журнал ": " рабочего журнала ",
            " внутренний реестр задач ": " внутреннего реестра задач ",
            " карточка этапа ": " карточки этапа ",
            " карточки этапов ": " карточек этапов ",
            " карточки заявки ": " карточек заявки ",
            " карточки заявок ": " карточек заявок ",
            " карточка задания ": " карточки задания ",
            " лист согласования ": " листа согласования ",
            " комплект конструкторской документации ": " комплекта конструкторской документации ",
            " комплект кд ": " комплекта КД ",
            " история комментариев ": " истории комментариев ",
            " истории комментариев ": " историй комментариев ",
            " статус в service desk ": " статуса в Service Desk ",
            " статусы в service desk ": " статусов в Service Desk ",
            " service desk ": " Service Desk ",
            " судовой журнал ": " судового журнала ",
            " журнал вахты ": " журнала вахты ",
            " навигационная сводка ": " навигационной сводки ",
            " распоряжения капитана ": " распоряжений капитана ",
            " pos-система ": " POS-системы ",
            " журнал смены ": " журнала смены ",
            " комментарии администратора ": " комментариев администратора ",
            " карта партии ": " карты партии ",
            " лист контроля качества ": " листа контроля качества ",
            " комментарии технолога ": " комментариев технолога ",
            " листы согласования ": " листов согласования ",
            " комплект кд ": " комплекта КД ",
            " карточки jira ": " карточек Jira ",
            " базу требований ": " базы требований ",
            " комментарии команды ": " комментариев команды ",
            " комментарии по текущей задаче ": " комментариев по текущей задаче ",
            " карточка обращения ": " карточки обращения ",
            " история коммуникации в crm ": " истории коммуникации в CRM ",
            " внутренние комментарии команды ": " внутренних комментариев команды ",
            " журнал эскалаций ": " журнала эскалаций ",
            " историю согласования ": " истории согласования ",
            " комментарии в 1с ": " комментариев в 1С ",
            " карточки кандидата ": " карточки кандидата ",
            " историю статусов ": " истории статусов ",
            " комментарии в hrm ": " комментариев в HRM ",
            " журнал маршрутов ": " журнала маршрутов ",
            " карточки отгрузки ": " карточек отгрузки ",
        }
        lowered = normalized.lower()
        for source, target in replacements.items():
            if source.strip().lower() in lowered:
                normalized = re.sub(re.escape(source.strip()), target.strip(), normalized, flags=re.IGNORECASE)
                lowered = normalized.lower()
        normalized = re.sub(r"\s+,", ",", normalized)
        normalized = re.sub(r",\s*,", ", ", normalized)
        normalized = re.sub(r"\s{2,}", " ", normalized).strip(" ,")
        return normalized

    def _normalize_sla_phrase(self, text: str) -> str:
        clean = str(text or "").strip()
        lowered = clean.lower()
        mapping = {
            "до 18:00": "до 18:00",
            "до 19:00": "до 19:00",
            "до конца рабочего дня": "к концу рабочего дня",
            "до конца рабочей смены": "к концу рабочей смены",
            "концу рабочего дня": "к концу рабочего дня",
            "концу рабочей смены": "к концу рабочей смены",
            "закрытию текущей смены": "к закрытию текущей смены",
            "началу следующего этапа рейса или передачи вахты": "к началу следующего этапа рейса или передачи вахты",
        }
        if lowered in mapping:
            return mapping[lowered]
        if lowered.startswith("до "):
            return clean
        if re.fullmatch(r"\d{1,2}:\d{2}", clean):
            return f"к {clean}"
        if lowered.startswith("к "):
            return clean
        return f"к {clean}"

    def _normalize_action_step_phrase(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        normalized = value
        replacements = {
            "проверка ": "проверку ",
            "фиксация ": "фиксацию ",
            "обновление ": "обновление ",
            "подтверждение ": "подтверждение ",
            "согласование ": "согласование ",
        }
        for source, target in replacements.items():
            normalized = re.sub(rf"(?<!\w){re.escape(source)}", target, normalized, flags=re.IGNORECASE)
            normalized = re.sub(rf",\s*{re.escape(source)}", f", {target}", normalized, flags=re.IGNORECASE)
        return normalized

    def _normalize_metric_object_phrase(self, text: str) -> str:
        clean = str(text or "").strip()
        if not clean:
            return ""
        normalized = re.sub(r"^показател(?:е|ях)\s+", "", clean, flags=re.IGNORECASE)
        normalized = re.sub(r"^метрик(?:е|ах)\s+", "", normalized, flags=re.IGNORECASE)
        return normalized or clean

    def _normalize_dependency_phrase(self, text: str) -> str:
        clean = str(text or "").strip()
        if not clean:
            return ""
        replacements = {
            "судового журнала": "судовой журнал",
            "подтверждения капитана": "подтверждение капитана",
            "следующей вахты": "следующую вахту",
            "второй линии ИТ-поддержки": "вторую линию ИТ-поддержки",
            "администратора домена": "администратора домена",
            "окна обновления ПО": "окно обновления ПО",
            "POS-системы": "POS-систему",
            "журнала смены": "журнал смены",
            "решения администратора зала": "решение администратора зала",
            "карты партии": "карту партии",
            "листа контроля": "лист контроля",
            "подтверждения технолога": "подтверждение технолога",
            "смежной рабочей группы": "смежную рабочую группу",
            "внутреннего журнала": "внутренний журнал",
            "подтверждения следующего шага": "подтверждение следующего шага",
            "заказчика": "заказчика",
            "команды разработки": "команду разработки",
            "окна планирования релиза": "окно планирования релиза",
        }
        parts = [part.strip() for part in re.split(r",|\s+и\s+", clean) if part.strip()]
        converted = [replacements.get(part, part) for part in parts]
        if len(converted) == 1:
            return converted[0]
        if len(converted) == 2:
            return f"{converted[0]} и {converted[1]}"
        return ", ".join(converted[:-1]) + f" и {converted[-1]}"

    def _normalize_business_criteria_phrase(self, text: str) -> str:
        clean = str(text or "").strip()
        if not clean:
            return ""
        replacements = {
            "безошибочная передача вахты": "безошибочную передачу вахты",
            "время согласования следующего маневра": "время согласования следующего маневра",
            "отсутствие повторных уточнений": "отсутствие повторных уточнений",
            "скорость закрытия спорных ситуаций": "скорость закрытия спорных ситуаций",
            "доля возвратов": "долю возвратов",
            "выручка смены": "выручку смены",
            "срок выполнения задач": "срок выполнения задач",
            "прозрачность статуса работ": "прозрачность статуса работ",
            "SLA первой линии": "SLA первой линии",
            "своевременность обновления пользователя": "своевременность обновления пользователя",
            "доля возвратов из разработки": "долю возвратов из разработки",
            "скорость согласования ТЗ": "скорость согласования ТЗ",
            "стабильность релизного плана": "стабильность релизного плана",
            "время выпуска партии": "время выпуска партии",
            "доля возвратов на контроль": "долю возвратов на контроль",
            "процент незакрытых отклонений": "процент незакрытых отклонений",
        }
        parts = [part.strip() for part in re.split(r",|\s+и\s+", clean) if part.strip()]
        converted = [replacements.get(part, part) for part in parts]
        if len(converted) == 1:
            return converted[0]
        if len(converted) == 2:
            return f"{converted[0]} и {converted[1]}"
        return ", ".join(converted[:-1]) + f" и {converted[-1]}"

    def _normalize_case_specificity_with_profile(
        self,
        raw: dict[str, Any],
        fallback: dict[str, Any],
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> dict[str, Any]:
        normalized = self._normalize_case_specificity(raw, fallback)
        family = self._detect_domain_family(position=position, duties=duties, company_industry=company_industry)
        markers_map = self._domain_family_markers()
        support_markers = markers_map.get("it_support", ())
        engineering_markers = markers_map.get("engineering", ())
        fields_to_validate = (
            "workflow_label",
            "workflow_name",
            "system_name",
            "channel",
            "source_of_truth",
            "request_type",
            "message_quote",
            "current_state",
            "bottleneck",
            "idea_description",
            "primary_stakeholder",
            "adjacent_team",
            "business_impact",
            "critical_step",
        )

        def _contains_any_markers(markers: tuple[str, ...]) -> bool:
            for key in fields_to_validate:
                value = str(normalized.get(key) or "")
                if any(marker in value.lower() for marker in markers):
                    return True
            if any(any(marker in str(item).lower() for marker in markers) for item in normalized.get("ticket_titles") or []):
                return True
            if any(any(marker in str(item).lower() for marker in markers) for item in normalized.get("stage_names") or []):
                return True
            return False

        def _reset_marked_values(markers: tuple[str, ...]) -> None:
            for key in fields_to_validate:
                value = str(normalized.get(key) or "")
                if any(marker in value.lower() for marker in markers):
                    normalized[key] = fallback.get(key)
            if any(any(marker in str(item).lower() for marker in markers) for item in normalized.get("ticket_titles") or []):
                normalized["ticket_titles"] = fallback.get("ticket_titles") or []
            if any(any(marker in str(item).lower() for marker in markers) for item in normalized.get("stage_names") or []):
                normalized["stage_names"] = fallback.get("stage_names") or []

        is_engineering = family == "engineering"
        is_it_support = family == "it_support"
        is_beauty = family == "beauty"

        if not is_it_support and _contains_any_markers(support_markers):
            _reset_marked_values(support_markers)
        if is_beauty and _contains_any_markers(engineering_markers):
            _reset_marked_values(engineering_markers)
        if is_engineering and _contains_any_markers(support_markers):
            _reset_marked_values(support_markers)
        expected_markers = markers_map.get(family, ())
        if family == "generic":
            conflicting = [
                other_family
                for other_family, markers in markers_map.items()
                if other_family != family and self._specificity_contains_family_markers(normalized, markers)
            ]
            if conflicting:
                return dict(fallback)
            return normalized
        if family != "generic":
            conflicting = [
                other_family
                for other_family, markers in markers_map.items()
                if other_family != family and self._specificity_contains_family_markers(normalized, markers)
            ]
            has_expected = self._specificity_contains_family_markers(normalized, expected_markers) if expected_markers else False
            if conflicting and not has_expected:
                return dict(fallback)
        return normalized

    def _specialize_specificity_from_case_frame(
        self,
        specificity: dict[str, Any],
        case_frame: dict[str, Any],
        domain_family: str,
    ) -> dict[str, Any]:
        result = dict(specificity or {})
        family = str(domain_family or self._infer_specificity_domain_family(result)).strip().lower()
        situation_code = str(case_frame.get("situation_code") or "").strip()
        deadline = cleanup_case_text(str(case_frame.get("deadline") or result.get("deadline") or ""))
        risk = cleanup_case_text(str(case_frame.get("risk") or result.get("business_impact") or ""))

        if family != "learning_and_development" or not situation_code:
            return result

        overrides: dict[str, dict[str, Any]] = {
            "lnd_program_not_approved": {
                "issue_summary": "финальная версия программы обучения не согласована, хотя старт уже близко и заказчик ждет подтверждения",
                "critical_step": "согласование финальной программы и подтверждение следующего шага перед запуском",
                "source_of_truth": "финальная версия программы, комментарии заказчика и карточка обучения в LMS/HRM",
                "work_items": "финальная программа курса, комментарии заказчика, дата запуска и карточка обучения в LMS/HRM",
                "ticket_titles": [
                    "Финальная программа курса не согласована к старту",
                    "Заказчик не подтвердил последнюю версию программы",
                    "Старт обучения приближается без финального согласования",
                ],
                "request_type": "согласование программы обучения перед запуском",
                "data_sources": "финальная программа курса, комментарии заказчика, карточка обучения и дата старта в LMS/HRM",
                "behavior_issue": "финальная версия программы не доводится до подтверждения, хотя срок запуска уже наступает",
                "decision_theme": "что нужно сделать первым, чтобы быстро закрыть согласование программы без ложных обещаний по старту",
                "current_state": "Финальная версия программы все еще не подтверждена заказчиком, хотя до запуска осталось совсем мало времени.",
                "bottleneck": "финальное согласование программы перед стартом не доводится до подтвержденного результата",
                "incident_type": "незавершенное согласование программы перед запуском",
                "incident_impact": "сдвиг старта программы и повторный цикл согласования с заказчиком",
            },
            "lnd_participants_not_confirmed": {
                "issue_summary": "список участников программы не подтвержден, из-за чего команда не может безопасно запускать обучение",
                "critical_step": "подтверждение состава участников и фиксация готовности к запуску",
                "source_of_truth": "список участников, комментарии руководителя подразделения и карточка запуска программы",
                "work_items": "список участников, подтверждение руководителя подразделения, карточка запуска и календарь обучения",
                "ticket_titles": [
                    "Список участников не подтвержден перед запуском",
                    "Руководитель подразделения не дал финальное подтверждение участников",
                    "Запуск программы под риском из-за неподтвержденного состава",
                ],
                "request_type": "подтверждение состава участников перед запуском",
                "data_sources": "список участников, карточка программы, календарь обучения и комментарии руководителя подразделения",
                "behavior_issue": "состав участников остается открытым до последнего момента и не фиксируется как подтвержденный",
                "decision_theme": "что нужно зафиксировать сейчас, чтобы не запускать обучение с неполным или спорным составом",
                "current_state": "Список участников несколько раз менялся, но финальное подтверждение так и не было зафиксировано.",
                "bottleneck": "состав участников не доходит до финального подтверждения перед запуском",
                "incident_type": "неподтвержденный состав участников программы",
                "incident_impact": "срыв запуска и повторное согласование списка участников",
            },
            "lnd_schedule_conflict": {
                "issue_summary": "согласованный график обучения конфликтует с загрузкой подразделения, и старт программы приходится пересматривать",
                "critical_step": "пересогласование дат обучения и фиксация реалистичного окна запуска",
                "source_of_truth": "календарь обучения, график подразделения и подтверждения руководителя по датам",
                "work_items": "календарь обучения, загрузка подразделения, согласованные даты и доступность эксперта",
                "ticket_titles": [
                    "Согласованные даты обучения конфликтуют с загрузкой подразделения",
                    "Подразделение не может отпустить участников в ранее согласованное окно",
                    "Старт программы под риском из-за конфликта графиков",
                ],
                "request_type": "пересогласование графика программы обучения",
                "data_sources": "календарь обучения, график подразделения, карточка программы и подтверждения по доступности эксперта",
                "behavior_issue": "даты обучения согласуются без финальной проверки загрузки подразделения и доступности участников",
                "decision_theme": "какой график считать реалистичным и что нужно передвинуть, чтобы не сорвать запуск",
                "current_state": "Уже согласованное окно обучения перестало подходить подразделению, и программа рискует не стартовать по графику.",
                "bottleneck": "даты программы не синхронизированы с реальной загрузкой подразделения",
                "incident_type": "конфликт графика обучения с производственной загрузкой",
                "incident_impact": "перенос обучения и снижение явки участников",
            },
            "lnd_vendor_waiting_brief": {
                "issue_summary": "подрядчик не получил финальное ТЗ по обучению и не может двигаться дальше по подготовке программы",
                "critical_step": "передача подтвержденного брифа и финального ТЗ подрядчику",
                "source_of_truth": "бриф на обучение, ТЗ подрядчику, программа курса и комментарии внутреннего эксперта",
                "work_items": "финальный бриф, ТЗ подрядчику, программа курса и комментарии внутреннего эксперта",
                "ticket_titles": [
                    "Подрядчик ждет утвержденное ТЗ по обучению",
                    "Внешний подрядчик не получил финальный бриф",
                    "Подготовка программы остановилась из-за неподтвержденного ТЗ",
                ],
                "request_type": "передача подтвержденного ТЗ подрядчику",
                "data_sources": "финальный бриф, программа курса, карточка программы и переписка с подрядчиком",
                "behavior_issue": "ТЗ подрядчику остается в черновом статусе и не передается как подтвержденное",
                "decision_theme": "что нужно доуточнить и подтвердить, чтобы подрядчик мог безопасно продолжить подготовку",
                "current_state": "Подрядчик ждет финальное ТЗ, но внутри команды еще не зафиксирован полностью подтвержденный объем.",
                "bottleneck": "финальное ТЗ подрядчику не доводится до подтвержденной версии",
                "incident_type": "остановка подготовки программы у подрядчика",
                "incident_impact": "перенос старта и повторный цикл согласования с подрядчиком",
            },
            "lnd_feedback_not_collected": {
                "issue_summary": "после пилота нет собранной обратной связи, поэтому решение о корректировке или масштабировании программы принимается вслепую",
                "critical_step": "сбор обратной связи и фиксация выводов по пилотной программе",
                "source_of_truth": "анкеты обратной связи, комментарии участников и карточка результатов пилота",
                "work_items": "анкеты обратной связи, комментарии участников, выводы по пилоту и план корректировок программы",
                "ticket_titles": [
                    "После пилота не собрана обратная связь участников",
                    "Нет подтвержденных выводов по результатам пилотной программы",
                    "Команда обсуждает масштабирование без данных по обратной связи",
                ],
                "request_type": "сбор и разбор обратной связи после пилота",
                "data_sources": "анкеты обратной связи, карточка результатов пилота и комментарии участников и эксперта",
                "behavior_issue": "выводы по пилотной программе не фиксируются до принятия решения о следующих шагах",
                "decision_theme": "как быстро собрать минимально достаточную обратную связь и стоит ли двигать программу дальше без этих данных",
                "current_state": "Пилот уже прошел, но подтвержденной обратной связи и итоговых выводов по нему нет.",
                "bottleneck": "обратная связь по пилоту не превращается в зафиксированные выводы и следующий шаг",
                "incident_type": "отсутствие данных по результатам пилота",
                "incident_impact": "повторение слабого сценария и снижение эффекта обучения",
            },
            "lnd_next_step_owner_missing": {
                "issue_summary": "по следующему шагу после согласования обучения нет явного владельца, и задача зависает между участниками",
                "critical_step": "назначение владельца следующего шага и фиксация ответственности в карточке обучения",
                "source_of_truth": "карточка обучения, комментарии заказчика и история договоренностей по следующему шагу",
                "work_items": "карточка обучения, следующий шаг, назначение владельца и комментарии заказчика",
                "ticket_titles": [
                    "После согласования не определен владелец следующего шага",
                    "Следующий шаг по программе не закреплен за конкретным участником",
                    "Задача зависла между заказчиком, L&D и подрядчиком",
                ],
                "request_type": "фиксация владельца следующего шага по программе",
                "data_sources": "карточка обучения, история договоренностей, комментарии заказчика и журнал задач по программе",
                "behavior_issue": "следующий шаг обсуждается, но не закрепляется за конкретным владельцем и сроком",
                "decision_theme": "кого назначить владельцем следующего шага и как зафиксировать это без новой волны согласований",
                "current_state": "После очередного согласования команда так и не закрепила, кто именно должен сделать следующий шаг и в какой срок.",
                "bottleneck": "ответственность за следующий шаг не фиксируется явно после согласования",
                "incident_type": "потеря владельца следующего шага по программе",
                "incident_impact": "повторное согласование и потеря контроля над запуском программы",
            },
        }

        scene = overrides.get(situation_code)
        if not scene:
            return result

        result["domain_family"] = family
        result["domain_code"] = family
        result.update(scene)
        if deadline:
            result["deadline"] = deadline
        if risk:
            result["business_impact"] = risk
        return result

    def _infer_client_type(self, *, position: str | None, duties: str | None) -> str:
        source = f"{position or ''} {duties or ''}".lower()
        if any(word in source for word in ("поддержк", "клиент", "сервис", "обращен")):
            return "внешний клиент"
        if any(word in source for word in ("персонал", "hr", "сотрудник")):
            return "внутренний заказчик"
        return "заказчик"

    def _generic_value(self, placeholder: str, domain: str, process: str, client_type: str) -> str:
        scenario = self._build_case_scenario_seed(
            domain=domain,
            process=process,
            position=None,
            duties=None,
            role_name=None,
        )
        scenario = self._enrich_scenario_seed(
            scenario,
            domain=domain,
            process=process,
            position=None,
            duties=None,
            role_name=None,
        )
        label = placeholder.lower()
        if "сфера деятельности" in label or ("компан" in label and "сфера" in label):
            return domain
        if "масштаб" in label:
            return "уровень участка"
        if "контур" in label or "команд" in label:
            return scenario.get("team_scope_label") or scenario["team_contour"]
        if "идея" in label:
            return f"улучшение процесса {process}"
        if label == "метрика" or "метрика" in label:
            return self._normalize_metric_object_phrase(
                scenario.get("metric_label") or f"время выполнения процесса {process}, качество результата и количество возвратов"
            )
        if "метрик" in label or "показател" in label:
            return scenario.get("metric_label") or f"время выполнения процесса {process}, качество результата и количество возвратов"
        if "ресурс" in label or "люди" in label:
            return scenario.get("resource_profile") or "доступный сотрудник и ограниченное рабочее время"
        if "риск" in label:
            return self._normalize_risk_phrase(f"срыв сроков, повторные доработки и ошибки в процессе {process}")
        if "тип запроса" in label:
            return scenario["request_type"]
        if "роль_кратко" in label or label == "должность":
            return "специалист по направлению"
        if label == "операция":
            return scenario["critical_step"]
        if label == "регламент":
            return scenario["source_of_truth"]
        if label == "отклонение":
            return scenario["issue_summary"]
        if "кому эскалировать" in label:
            return self._select_escalation_target(scenario["primary_stakeholder"], scenario["adjacent_team"])
        if label == "полномочия":
            return scenario["limits_short"]
        if "данные/источники" in label or "источники" in label or "данные" in label:
            return scenario["data_sources"]
        if "данные/логи" in label or "логи" in label:
            return scenario["data_sources"]
        if "смежный отдел" in label:
            return scenario["adjacent_team"]
        if "поведение/проблема" in label:
            return scenario["behavior_issue"]
        if "контекст команды/проекта" in label:
            return scenario.get("team_scope_label") or scenario["team_context"]
        if "что нужно" in label:
            return scenario["workflow_label"]
        if "влияние на бизнес" in label:
            return scenario["business_impact"]
        if label == "влияние" or "влияние" in label:
            return scenario.get("metric_delta") or scenario["business_impact"]
        if label == "срок" or "сроки" in label:
            return scenario["deadline"]
        if label == "ограничения" or "ограничения" in label:
            return scenario["limits_short"]
        if "ограничения времени/ресурса" in label:
            return scenario.get("time_resource_limit") or scenario["deadline"]
        if label == "процесс" or label.endswith(" процесс"):
            return scenario["workflow_label"]
        if "контекст процесса/продукта" in label:
            return scenario["workflow_label"]
        if "тип инцидента" in label:
            return scenario["incident_type"]
        if "последствия" in label:
            return scenario["incident_impact"]
        if label == "команды" or "команды" in label:
            return scenario["involved_teams"]
        if "ключевые стейкхолдеры" in label:
            return scenario.get("stakeholder_named_list") or scenario["primary_stakeholder"]
        if "пользователи/клиенты" in label:
            return scenario.get("audience_label") or client_type
        if "пример поведения" in label:
            return scenario["behavior_issue"]
        if "стратегическая цель / направление / систему" in label:
            return scenario.get("strategic_scope") or scenario["workflow_label"]
        if "зависимости" in label:
            return scenario.get("dependencies") or scenario["adjacent_team"]
        if "критерии бизнеса" in label:
            return scenario.get("business_criteria") or scenario["business_impact"]
        if "решение/дилемма" in label:
            return scenario.get("decision_theme") or scenario["issue_summary"]
        if label == "данные":
            return scenario["data_sources"]
        if "список задач" in label:
            return scenario["work_items"]
        if "ресурсы" in label:
            return scenario.get("resource_profile") or scenario["work_items"]
        if "стейкхолдер" in label:
            if "стейкхолдеры" in label:
                return scenario.get("stakeholder_named_list") or scenario["primary_stakeholder"]
            return self._select_primary_actor(scenario["primary_stakeholder"], grammatical_case="nominative")
        if "тикет" in label or "обращен" in label:
            return scenario["work_items"]
        if "ошиб" in label or "сбо" in label:
            return scenario["error_examples"]
        if "стейкхолдер" in label or "участник" in label:
            return f"{client_type}, смежная команда и руководитель направления"
        if "полномоч" in label or "ограничен" in label:
            return "работа в рамках регламента, фиксация действий в системе и обязательная эскалация спорных решений"
        if "тип команды" in label:
            return scenario.get("team_scope_label") or scenario["team_contour"]
        if "задач" in label:
            return scenario["work_items"]
        if "срок" in label or "sla" in label:
            return "1 рабочий день"
        if "клиент" in label:
            return client_type
        if "канал" in label:
            return self._normalize_channel_phrase(scenario["channel"])
        if "имена" in label or "участник" in label and "имена" in label:
            return scenario["participant_names"]
        if "назван" in label and "тикет" in label:
            return scenario["ticket_titles"]
        if "процесс" in label or "сервис" in label:
            return scenario["workflow_label"]
        if "система" in label:
            return scenario["system_name"]
        if "проблем" in label:
            return scenario["issue_summary"]
        if "контекст" in label or "обязанност" in label:
            return f"работу по направлению {scenario['workflow_name']}"
        return f"{scenario['workflow_name']} в контуре {scenario['team_contour']}"
