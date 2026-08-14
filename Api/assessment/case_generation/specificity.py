from __future__ import annotations

import re
import zlib
from typing import Any


class CaseSpecificityMixin:
    def normalize_company_industry(
        self,
        *,
        company_industry: str | None,
        position: str | None = None,
        duties: str | None = None,
    ) -> str | None:
        cleaned = (company_industry or "").strip()
        if not cleaned:
            return None

        fallback = self._fallback_normalize_company_industry(cleaned)
        cache_key = (
            cleaned.lower(),
            str(position or "").strip().lower(),
            str(duties or "").strip().lower(),
        )
        cached = self._company_industry_cache.get(cache_key)
        if cached:
            return cached
        if not self.enabled or not self._should_use_llm_company_industry(
            company_industry=cleaned,
            position=position,
            duties=duties,
        ):
            self._company_industry_cache[cache_key] = fallback
            return fallback

        prompt = (
            "Нормализуй сферу деятельности компании до краткой предметной формулировки в родительном падеже. "
            "Верни только JSON с полем company_industry_normalized. "
            "Примеры корректного формата: "
            "\"финансовых услуг\", \"информационных технологий\", \"розничной торговли\", \"логистики и транспорта\". "
            "Не добавляй пояснений и не придумывай новую отрасль, если исходный ввод уже понятен.\n\n"
            f"Сфера деятельности компании: {cleaned}\n"
            f"Должность пользователя: {position or 'Не указана'}\n"
            f"Обязанности пользователя: {duties or 'Не указаны'}"
        )
        try:
            raw = self._post_chat(
                [
                    {
                        "role": "system",
                        "content": "Ты нормализуешь отрасли и сферы деятельности компаний для внутренних профилей сотрудников.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            parsed = self._parse_json(raw)
            normalized = str(parsed.get("company_industry_normalized") or "").strip()
            result = normalized or fallback
            self._company_industry_cache[cache_key] = result
            return result
        except Exception:
            self._company_industry_cache[cache_key] = fallback
            return fallback

    def _should_use_llm_company_industry(
        self,
        *,
        company_industry: str,
        position: str | None,
        duties: str | None,
    ) -> bool:
        cleaned = str(company_industry or "").strip()
        if not cleaned:
            return False
        lowered = cleaned.lower()
        family = self._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        if family != "generic":
            return False
        if len(lowered) <= 48 and not any(ch in lowered for ch in ",.;:!?/\\"):
            return False
        return True

    def _fallback_case_specificity(
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
        domain_profile = self._extract_domain_profile_from_user_profile(user_profile)
        user_work_context = self._extract_user_work_context_from_profile(user_profile)
        normalized_company_industry = self.normalize_company_industry(
            company_industry=company_industry,
            position=position,
            duties=duties,
        )
        inferred_domain = self._infer_domain(position=position, duties=duties, company_industry=company_industry)
        prioritize_runtime_domain = self._should_prioritize_runtime_domain(
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
        process = (
            (None if prioritize_runtime_domain else (user_work_context.get("user_processes") or [None])[0])
            or (domain_profile.get("processes") or [None])[0]
            or (None if prioritize_runtime_domain else (user_profile or {}).get("user_processes", [None])[0])
            or self._infer_process(position=position, duties=duties)
        )
        scenario = self._build_case_scenario_seed(
            domain=domain,
            process=process,
            position=position,
            duties=duties,
            role_name=role_name,
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
        scenario = self._specialize_scenario_from_template(
            scenario,
            case_type_code=case_type_code,
            case_title=case_title,
            case_context=case_context,
            case_task=case_task,
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        text_scenario = self._scenario_from_case_text(case_title=case_title, text=f"{case_context}\n{case_task}")
        stage_names = self._default_stage_names(
            case_type_code=case_type_code,
            workflow_name=scenario["workflow_name"],
            critical_step=scenario["critical_step"],
        )
        preferred_ticket_source: Any = scenario["ticket_titles"]
        is_engineering_profile = self._is_engineering_industry_profile(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        if not is_engineering_profile:
            if text_scenario.get("ticket_title_list"):
                preferred_ticket_source = text_scenario.get("ticket_title_list")
            elif text_scenario.get("workflow_label") and text_scenario.get("workflow_label") != "текущая операционная работа команды":
                preferred_ticket_source = text_scenario.get("ticket_titles_short") or preferred_ticket_source
        ticket_titles = self._normalize_string_list(
            preferred_ticket_source,
            fallback=[
                item.strip(" «»\"")
                for item in str(scenario["ticket_titles"]).split(",")
                if item.strip()
            ],
        )
        message_quote = self._default_message_quote(
            case_type_code=case_type_code,
            case_title=case_title,
            scenario=scenario,
            position=position,
            duties=duties,
        )
        return {
            "workflow_label": scenario["workflow_label"],
            "workflow_name": scenario["workflow_name"],
            "system_name": scenario["system_name"],
            "channel": scenario["channel"],
            "source_of_truth": scenario["source_of_truth"],
            "request_type": scenario["request_type"],
            "ticket_titles": ticket_titles,
            "stage_names": stage_names,
            "idea_label": self._default_idea_label(case_type_code=case_type_code, workflow_label=scenario["workflow_label"]),
            "current_state": self._default_current_state_description(
                case_type_code=case_type_code,
                scenario=scenario,
                position=position,
                duties=duties,
            ),
            "bottleneck": self._default_bottleneck_description(
                case_type_code=case_type_code,
                scenario=scenario,
                position=position,
                duties=duties,
            ),
            "idea_description": self._default_idea_description(
                case_type_code=case_type_code,
                scenario=scenario,
                position=position,
                duties=duties,
            ),
            "message_quote": message_quote,
            "primary_stakeholder": scenario["primary_stakeholder"],
            "adjacent_team": scenario["adjacent_team"],
            "business_impact": scenario["business_impact"],
            "critical_step": scenario["critical_step"],
            "participant_names": scenario.get("participant_names") or "",
            "stakeholder_named_list": scenario.get("stakeholder_named_list") or "",
            "shift_name": scenario.get("shift_name") or "",
            "shift_duration": scenario.get("shift_duration") or "",
            "work_items": scenario.get("work_items") or "",
            "resource_profile": scenario.get("resource_profile") or "",
            "metric_label": scenario.get("metric_label") or "",
            "metric_delta": scenario.get("metric_delta") or "",
            "decision_theme": scenario.get("decision_theme") or "",
        }

    def _specialize_scenario_from_template(
        self,
        scenario: dict[str, str],
        *,
        case_type_code: str | None,
        case_title: str,
        case_context: str,
        case_task: str,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> dict[str, str]:
        result = dict(scenario)
        family = self._detect_domain_family(
            position=position,
            duties=duties,
            company_industry=company_industry,
        )
        title = str(case_title or "").lower()
        template = f"{case_context or ''} {case_task or ''}".lower()
        if str(case_type_code or "").upper() != "F02":
            return result

        if family == "it_support":
            if "сырой" in title or "входных данных" in title:
                result["request_type"] = "сводку по обращениям с просроченным обновлением статуса"
                result["data_sources"] = "рабочего журнала, карточек обращений и комментариев в Service Desk"
                result["source_of_truth"] = "карточки обращений, история комментариев и статусы в Service Desk"
                result["critical_step"] = "подтверждение состава данных, критериев результата и владельца следующего шага"
                result["ticket_titles"] = "«Нет ответа по обращению после обещанного срока», «Повторная жалоба на закрытый вопрос», «Обращение передано дальше без подтвержденного следующего шага»"
            elif "межфункциональ" in title or "плавающим объёмом" in title:
                result["request_type"] = "координацию эскалации по группе проблемных обращений"
                result["data_sources"] = "очереди Service Desk, комментариев смежных линий и журнала эскалаций"
                result["source_of_truth"] = "очередь обращений, комментарии смежных линий и журнал эскалаций"
                result["critical_step"] = "согласование объема, ролей и ответственного за итоговый результат"
                result["ticket_titles"] = "«Эскалация по клиентскому обращению без согласованного владельца», «Смежная линия просит запуск без полного объема данных», «Группа обращений требует срочной координации между линиями поддержки»"
            elif ("понятно" in title and "удобно" in title) or "критериев" in title or "приоритетов" in title:
                result["request_type"] = "новый шаблон обновления статуса для пользователей по проблемным обращениям"
                result["data_sources"] = "истории обращений, шаблонов ответов и комментариев пользователей"
                result["source_of_truth"] = "истории обращений, шаблоны ответов и комментарии пользователей"
                result["critical_step"] = "уточнение целевого пользователя, обязательного объема и критериев понятного результата"
                result["ticket_titles"] = "«Пользователь не понял итог последнего обновления», «Шаблон ответа не покрывает спорные случаи», «Обращение закрыто без ясного описания результата»"
            elif "изменение процесса" in title or "конфликтом интересов" in title:
                result["request_type"] = "изменение порядка обработки обращений с повторными возвратами"
                result["data_sources"] = "журнала обращений, SLA-отчетов и комментариев руководителя смены"
                result["source_of_truth"] = "журнал обращений, SLA-отчеты и комментарии руководителя смены"
                result["critical_step"] = "фиксация рамки изменений, метрики успеха и обязательных ограничений"
                result["ticket_titles"] = "«Повторные возвраты по заявкам после формального закрытия», «Нет единого правила эскалации спорных обращений», «Смена по-разному понимает момент передачи следующего шага»"
        elif family == "business_analysis":
            if "сырой" in title or "входных данных" in title:
                result["request_type"] = "черновик ТЗ по срочной доработке без полного описания требований"
                result["data_sources"] = "карточки Jira, базы требований и комментариев заказчика"
                result["source_of_truth"] = "карточка Jira, база требований и комментарии заказчика"
                result["critical_step"] = "уточнение объема, критериев готовности и обязательных ограничений"
            elif "изменение процесса" in title:
                result["request_type"] = "обновление процесса согласования требований перед передачей в разработку"
                result["data_sources"] = "карточек Jira, истории согласований и текущих правил передачи задач"
        elif family == "maritime":
            if "сырой" in title or "входных данных" in title:
                result["request_type"] = "уточнение данных по следующему маневру и передаче вахты"
                result["data_sources"] = "судового журнала, журнала вахты и распоряжений капитана"
                result["source_of_truth"] = "судовой журнал, журнал вахты и распоряжения капитана"
                result["critical_step"] = "подтверждение следующего маневра, состава данных и ответственного по вахте"
        elif family == "horeca":
            if "сырой" in title or "входных данных" in title:
                result["request_type"] = "разбор спорной ситуации по заказу гостя до закрытия смены"
                result["data_sources"] = "POS-системы, журнала смены и комментариев администратора"
                result["source_of_truth"] = "POS-система, журнал смены и комментарии администратора"
                result["critical_step"] = "уточнение результата для гостя, объема действий и следующего шага по смене"
        elif family == "engineering":
            if "сырой" in title or "входных данных" in title:
                result["request_type"] = "доработку комплекта КД по замечаниям без полного состава исходных данных"
                result["data_sources"] = "карточки задания, листа согласования и комплекта КД"
                result["source_of_truth"] = "карточка задания, лист согласования и комплект КД"
                result["critical_step"] = "уточнение состава замечаний, объема доработки и критерия готовности комплекта"

        if "нужно срочно сделать" in template and "как обычно, только без лишнего" in template and family == "generic":
            result["request_type"] = "сводку по проблемным этапам работы"
            result["data_sources"] = "рабочего журнала, карточек этапов и внутренних комментариев команды"
            result["critical_step"] = "уточнение состава данных, объема результата и обязательных ограничений"
        return result

    def _extract_domain_profile_from_user_profile(self, user_profile: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(user_profile, dict):
            return {}
        result: dict[str, Any] = {}
        top_level_domain_profile = user_profile.get("domain_profile")
        if isinstance(top_level_domain_profile, dict):
            result.update(top_level_domain_profile)
        context_vars = user_profile.get("user_context_vars")
        if isinstance(context_vars, dict):
            domain_profile = context_vars.get("domain_profile")
            if isinstance(domain_profile, dict):
                legacy_context_only_fields = {"processes", "tasks", "stakeholders", "risks", "constraints"}
                for key, value in domain_profile.items():
                    if key in legacy_context_only_fields:
                        continue
                    result.setdefault(key, value)
        user_work_context = user_profile.get("user_work_context")
        if isinstance(user_work_context, dict):
            if isinstance(user_work_context.get("user_domain"), str) and user_work_context.get("user_domain"):
                result.setdefault("domain_label", user_work_context.get("user_domain"))
            field_mapping = {
                "user_processes": "processes",
                "user_tasks": "tasks",
                "user_stakeholders": "stakeholders",
                "user_risks": "risks",
                "user_constraints": "constraints",
            }
            for source_key, target_key in field_mapping.items():
                value = user_work_context.get(source_key)
                if isinstance(value, list) and value and not result.get(target_key):
                    result[target_key] = value
        top_level_artifacts = user_profile.get("user_artifacts")
        if isinstance(top_level_artifacts, list) and top_level_artifacts:
            result["artifacts"] = top_level_artifacts
        top_level_systems = user_profile.get("user_systems")
        if isinstance(top_level_systems, list) and top_level_systems:
            result["systems"] = top_level_systems
        top_level_metrics = user_profile.get("user_success_metrics")
        if isinstance(top_level_metrics, list) and top_level_metrics:
            result["success_metrics"] = top_level_metrics
        top_level_quality = user_profile.get("profile_quality")
        if isinstance(top_level_quality, dict) and top_level_quality:
            result["profile_quality"] = top_level_quality
        top_level_notes = user_profile.get("data_quality_notes")
        if isinstance(top_level_notes, list) and top_level_notes:
            result["data_quality_notes"] = top_level_notes
        return result

    def _extract_user_work_context_from_profile(self, user_profile: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(user_profile, dict):
            return {}
        user_work_context = user_profile.get("user_work_context")
        if isinstance(user_work_context, dict):
            return dict(user_work_context)
        return {
            "user_domain": user_profile.get("user_domain"),
            "company_industry_context": user_profile.get("company_context"),
            "user_processes": user_profile.get("user_processes") or [],
            "user_tasks": user_profile.get("user_tasks") or [],
            "user_stakeholders": user_profile.get("user_stakeholders") or [],
            "user_risks": user_profile.get("user_risks") or [],
            "user_constraints": user_profile.get("user_constraints") or [],
        }

    def _is_engineering_industry_profile(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> bool:
        source = f"{position or ''} {duties or ''} {company_industry or ''}".lower()
        return any(
            word in source
            for word in (
                "ядер",
                "энергет",
                "инженер",
                "разработ",
                "developer",
                "software",
                "backend",
                "frontend",
                "fullstack",
                "full stack",
                "devops",
                "ml",
                "machine learning",
                "data science",
                "python",
                "java",
                "golang",
                "go developer",
                "c++",
                "c#",
                "javascript",
                "typescript",
                "sql",
                "api",
                "микросервис",
                "платформ",
                "прод",
                "production",
                "релиз",
                "деплой",
                "repo",
                "git",
                "код",
                "конструкт",
                "чертеж",
                "документац",
                "предприят",
                "энергоблок",
                "реактор",
                "кд",
            )
        )

    def _is_learning_and_development_profile(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> bool:
        source = f"{position or ''} {duties or ''} {company_industry or ''}".lower()
        return any(
            marker in source
            for marker in (
                "корпоративн обучен",
                "обучен",
                "l&d",
                "learning and development",
                "lms",
                "курс",
                "тренинг",
                "учебн",
                "программ развития",
                "развитие персонала",
            )
        )

    def _is_it_support_profile(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> bool:
        source = f"{position or ''} {duties or ''} {company_industry or ''}".lower()
        return any(
            word in source
            for word in (
                "техпод",
                "helpdesk",
                "service desk",
                "системный администратор",
                "картридж",
                "принтер",
                "vpn",
                "рабочее место",
                "учетн",
                "программное обеспечение",
            )
        )

    def _is_client_service_profile(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> bool:
        source = f"{position or ''} {duties or ''} {company_industry or ''}".lower()
        explicit_phrases = (
            "клиентская поддержка",
            "клиентский сервис",
            "customer support",
            "успешность клиентов",
            "customer success",
        )
        if any(phrase in source for phrase in explicit_phrases):
            return True
        has_client_anchor = any(word in source for word in ("клиент", "клиентск", "заказчик", "crm"))
        has_service_context = any(
            word in source
            for word in ("обращен", "жалоб", "эскалац", "sla", "сервис", "поддержк", "ответ")
        )
        return has_client_anchor and has_service_context

    def _is_beauty_industry_profile(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> bool:
        source = f"{position or ''} {duties or ''} {company_industry or ''}".lower()
        return any(
            word in source
            for word in (
                "космет",
                "парикмах",
                "салон",
                "уклад",
                "стриж",
                "волос",
                "beauty",
                "клиент салона",
                "барберш",
            )
        )

    def _detect_domain_family(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> str:
        source = f"{position or ''} {duties or ''} {company_industry or ''}".lower()
        # L&D specialists often describe their work as "разработка программ
        # обучения". Check that explicit domain before the broad engineering
        # marker "разработ", otherwise training profiles become software or
        # engineering profiles.
        if self._is_learning_and_development_profile(
            position=position,
            duties=duties,
            company_industry=company_industry,
        ):
            return "learning_and_development"
        if self._is_engineering_industry_profile(position=position, duties=duties, company_industry=company_industry):
            return "engineering"
        if self._is_beauty_industry_profile(position=position, duties=duties, company_industry=company_industry):
            return "beauty"
        if any(
            word in source
            for word in (
                "судоход",
                "моряк",
                "судно",
                "корабл",
                "капитан",
                "вахт",
                "навигац",
                "порт",
                "экипаж",
                "рейс",
                "мостик",
                "лоцман",
                "швартов",
            )
        ):
            return "maritime"
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "официант", "хостес", "коктейл", "гость", "меню")):
            return "horeca"
        if any(word in source for word in ("пищев", "продукц", "партия", "упаков", "сырье", "маркиров", "карта партии", "линия производства", "отметка отк", "контролер отк")):
            return "food_production"
        if self._is_client_service_profile(position=position, duties=duties, company_industry=company_industry):
            return "client_service"
        if self._is_it_support_profile(position=position, duties=duties, company_industry=company_industry):
            return "it_support"
        if any(word in source for word in ("аналит", "требован", "бизнес-постанов", "постановк", "тз", "jira", "story", "критерии приемки")):
            return "business_analysis"
        if any(word in source for word in ("финанс", "оплат", "счет", "бюджет", "платеж", "банк")):
            return "finance"
        if any(word in source for word in ("hr", "персонал", "подбор", "адаптац", "кадр", "рекрут")):
            return "hr"
        if any(word in source for word in ("логист", "склад", "достав", "маршрут", "отгруз")):
            return "logistics"
        return "generic"

    def _domain_family_markers(self) -> dict[str, tuple[str, ...]]:
        return {
            "engineering": ("plm", "чертеж", "кд", "конструкт", "документац", "реактор", "энергоблок", "лист согласования"),
            "beauty": ("салон", "стриж", "уклад", "волос", "карта услуги", "администратор салона", "клиент салона"),
            "maritime": ("судно", "корабл", "капитан", "вахт", "рейс", "порт", "экипаж", "судовой журнал", "мостик", "навигац"),
            "horeca": ("бар", "бармен", "гость", "коктейл", "барная стойка", "ресторан", "заказ гостя", "касса"),
            "food_production": ("партия", "упаков", "сырье", "маркиров", "сменный журнал", "контроль качества", "карта партии", "линия производства", "отметка отк", "контролер отк"),
            "client_service": ("клиентск", "внешний клиент", "обращение клиента", "жалоб", "crm", "сервис", "эскалац"),
            "it_support": ("service desk", "jira", "vpn", "картридж", "принтер", "инцидент", "эскалац", "заявк", "учетн", "вторая линия"),
            "business_analysis": ("тз", "требован", "story", "критерии приемки", "jira", "аналитик"),
            "finance": ("платеж", "1с", "счет", "бюджет", "согласование оплаты"),
            "hr": ("кандидат", "оффер", "hrm", "адаптац", "рекрут", "кадров", "подбор персонала"),
            "learning_and_development": ("обучен", "l&d", "lms", "курс", "тренинг", "учебн", "подрядчик", "эксперт", "программа обучения", "эффективность обучения"),
            "logistics": ("отгруз", "маршрут", "склад", "достав", "tms"),
        }

    def _specificity_contains_family_markers(
        self,
        values: dict[str, Any],
        markers: tuple[str, ...],
    ) -> bool:
        scalar_fields = (
            "workflow_label",
            "workflow_name",
            "system_name",
            "channel",
            "source_of_truth",
            "request_type",
            "idea_label",
            "current_state",
            "bottleneck",
            "idea_description",
            "message_quote",
            "primary_stakeholder",
            "adjacent_team",
            "business_impact",
            "critical_step",
        )
        for key in scalar_fields:
            value = str(values.get(key) or "")
            if any(marker in value.lower() for marker in markers):
                return True
        for key in ("ticket_titles", "stage_names"):
            if any(any(marker in str(item).lower() for marker in markers) for item in (values.get(key) or [])):
                return True
        return False

    def _normalize_string_list(self, raw: Any, *, fallback: list[str]) -> list[str]:
        if isinstance(raw, list):
            items = [self._sanitize_personalization_value(str(item)) for item in raw]
        elif isinstance(raw, str):
            items = [
                self._sanitize_personalization_value(part.strip(" -—\n\t«»\""))
                for part in re.split(r"[,;]\s*|\n+", raw)
                if part.strip(" -—\n\t«»\"")
            ]
        else:
            items = []
        cleaned = [item for item in items if item]
        return cleaned or [item for item in fallback if item]

    def _infer_specificity_domain_family(self, specificity: dict[str, Any]) -> str:
        family = str(specificity.get("domain_family") or specificity.get("domain_code") or "").strip().lower()
        if family:
            return family
        case_frame = dict(specificity.get("_case_frame") or {})
        situation_code = str(case_frame.get("situation_code") or "").strip().lower()
        if situation_code.startswith("lnd_"):
            return "learning_and_development"
        if situation_code.startswith("client_") or situation_code.startswith("service_"):
            return "client_service"
        if situation_code.startswith("eng_"):
            return "engineering"
        if situation_code.startswith("support_") or situation_code.startswith("it_"):
            return "it_support"
        markers_map = self._domain_family_markers()
        for name, markers in markers_map.items():
            if self._specificity_contains_family_markers(specificity, markers):
                return name
        return "generic"

    def _format_case_scope(self, label: str) -> str:
        value = str(label or "").strip()
        if not value:
            return ""
        if value.startswith("**") and value.endswith("**"):
            return value
        return f"**{value}**"

    def _default_stage_names(self, *, case_type_code: str | None, workflow_name: str, critical_step: str) -> list[str]:
        type_code = (case_type_code or "").upper()
        if type_code == "F01":
            return ["получение жалобы", "проверка статуса", "фиксация следующего шага", "обновление клиента"]
        if type_code == "F03" or type_code == "F12":
            return ["разбор фактов", "обсуждение последствий", "договоренность о новом порядке", "контроль повторения"]
        if type_code == "F08":
            return ["проверка очереди задач", "выбор приоритета", "фиксация владельца", "обновление статуса"]
        if type_code == "F10" or type_code == "F14":
            return ["формулировка идеи", "оценка рисков", "пилот", "подведение итогов"]
        return ["первичная проверка", critical_step, "согласование следующего шага", "контроль результата"]

    def _default_idea_label(self, *, case_type_code: str | None, workflow_label: str) -> str:
        type_code = (case_type_code or "").upper()
        if type_code in {"F09", "F10", "F14", "F15"}:
            return f"чек-лист следующего шага в процессе «{workflow_label}»"
        return f"улучшение процесса «{workflow_label}»"

    def _default_current_state_description(
        self,
        *,
        case_type_code: str | None,
        scenario: dict[str, str],
        position: str | None,
        duties: str | None,
    ) -> str:
        source = f"{position or ''} {duties or ''} {scenario.get('workflow_label') or ''}".lower()
        shift_name = str(scenario.get("shift_name") or "").strip()
        metric_delta = str(scenario.get("metric_delta") or "").strip()
        shift_name_on = shift_name
        if shift_name_on:
            shift_name_on = re.sub(r"^вечерняя\s+смена\b", "вечерней смене", shift_name_on, flags=re.IGNORECASE)
            shift_name_on = re.sub(r"^дневная\s+смена\b", "дневной смене", shift_name_on, flags=re.IGNORECASE)
            shift_name_on = re.sub(r"^аналитическая\s+смена\b", "аналитической смене", shift_name_on, flags=re.IGNORECASE)
            shift_name_on = re.sub(r"^смена\b", "смене", shift_name_on, flags=re.IGNORECASE)
        shift_name_bold = self._format_case_scope(shift_name) if shift_name else ""
        shift_name_on_bold = self._format_case_scope(shift_name_on) if shift_name_on else ""
        if metric_delta and metric_delta[-1] not in ".!?":
            metric_delta += "."
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "заказ")):
            return (
                f"По спорным заказам команда работает через бармена, администратора зала и журнал смены {shift_name_bold or shift_name}, "
                f"но замечание гостя и следующий шаг фиксируются не в одном месте. {metric_delta}"
            )
        if any(word in source for word in ("судоход", "моряк", "судно", "корабл", "вахт", "экипаж", "рейс")):
            return (
                f"По вахте следующий шаг передают через судовой журнал и устную смену {shift_name_bold or shift_name}, "
                f"но подтверждение результата иногда остается неполным. {metric_delta}"
            )
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац")):
            return (
                "Комплект документации уже проходит проверку и согласование, "
                f"но на стыке этапов теряются подтверждения по замечаниям. {metric_delta}"
            )
        if any(word in source for word in ("jira", "тз", "требован", "story", "аналит", "разработ")):
            return (
                "Задача уже проходит уточнение требований и согласование с заказчиком, "
                f"но следующий шаг и критерии результата фиксируются не до конца. {metric_delta}"
            )
        if any(word in source for word in ("клиентск", "crm", "обращен", "жалоб", "эскалац", "сервис")):
            return (
                "По обращениям клиентов часть статусов уже обновлена, "
                f"но подтверждение результата и следующий шаг по обращению фиксируются не до конца. {metric_delta}"
            )
        if any(word in source for word in ("service desk", "инцидент", "заяв", "техпод", "vpn", "принтер")):
            return (
                f"Обращение уже прошло регистрацию и обновление статуса на {shift_name_on or 'текущей смене поддержки'}, "
                f"но фактический результат или следующий шаг зафиксированы не полностью. {metric_delta}"
            )
        return (
            f"Работа идет по процессу «{scenario.get('workflow_label') or 'текущему процессу'}» на участке {shift_name_on_bold or 'текущей смены'}, "
            f"но на одном из этапов теряется подтверждение результата, следующего шага или ответственного. {metric_delta}"
        )

    def _default_bottleneck_description(
        self,
        *,
        case_type_code: str | None,
        scenario: dict[str, str],
        position: str | None,
        duties: str | None,
    ) -> str:
        source = f"{position or ''} {duties or ''} {scenario.get('workflow_label') or ''}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "заказ")):
            return "замечания по заказу и договоренности по гостю закрываются раньше, чем команда фиксирует итог и следующий шаг"
        if any(word in source for word in ("судоход", "моряк", "судно", "корабл", "вахт", "экипаж", "рейс")):
            return "следующий маневр и подтверждение результата по вахте фиксируются не полностью перед передачей смены"
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац")):
            return "замечания по документации и готовность следующего этапа подтверждаются не в одном контуре"
        if any(word in source for word in ("jira", "тз", "требован", "story", "аналит", "разработ")):
            return "требования и критерии готовности передаются дальше без окончательной фиксации общего понимания"
        if any(word in source for word in ("service desk", "инцидент", "заяв", "техпод", "vpn", "принтер")):
            return "обращение закрывают или передают дальше раньше, чем подтвержден фактический результат, следующий шаг и обновление пользователя"
        return "критичный шаг подтверждения результата и следующего действия фиксируется непоследовательно"

    def _default_idea_description(
        self,
        *,
        case_type_code: str | None,
        scenario: dict[str, str],
        position: str | None,
        duties: str | None,
    ) -> str:
        source = f"{position or ''} {duties or ''} {scenario.get('workflow_label') or ''}".lower()
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "заказ")):
            return (
                "Перед закрытием спорной ситуации по гостю команда будет фиксировать замечание, согласованный следующий шаг "
                "и ответственного прямо в журнале смены."
            )
        if any(word in source for word in ("судоход", "моряк", "судно", "корабл", "вахт", "экипаж", "рейс")):
            return (
                "Перед передачей вахты следующий маневр, подтверждение результата и ответственный шаг будут явно подтверждаться "
                "в журнале и устно между вахтами."
            )
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац")):
            return (
                "Перед передачей комплекта документации дальше команда будет отдельно фиксировать закрытие замечаний "
                "и подтверждение готовности следующего этапа."
            )
        if any(word in source for word in ("jira", "тз", "требован", "story", "аналит", "разработ")):
            return (
                "Перед передачей задачи в разработку аналитик будет фиксировать согласованные требования, критерии готовности "
                "и следующий шаг в одном месте."
            )
        if any(word in source for word in ("service desk", "инцидент", "заяв", "техпод", "vpn", "принтер")):
            return (
                "Перед закрытием обращения специалист будет отдельно подтверждать фактический результат, следующее действие "
                "и обновление пользователя."
            )
        return "Новый порядок работы должен заставлять команду явно фиксировать итог шага, следующего владельца и подтверждение результата."

    def _default_message_quote(
        self,
        *,
        case_type_code: str | None,
        case_title: str,
        scenario: dict[str, str],
        position: str | None,
        duties: str | None,
    ) -> str:
        source = f"{case_title} {position or ''} {duties or ''}".lower()
        type_code = (case_type_code or "").upper()
        if type_code == "F01" and any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят")):
            return "Добрый день! Комплект уже отмечен как переданный, но замечания по чертежам закрыты не полностью, а итогового подтверждения я не вижу. Поясните, пожалуйста, что реально готово и когда будет финальный результат."
        if type_code == "F01" and any(word in source for word in ("судоход", "моряк", "судно", "корабл", "капитан", "вахт", "навигац", "порт", "экипаж", "рейс", "мостик")):
            return "Добрый день! Вахта уже отмечена как переданная, но я не вижу понятного подтверждения по следующему маневру и записи о фактическом результате. Поясните, пожалуйста, что сейчас действительно завершено и каков следующий шаг."
        if type_code == "F01" and any(word in source for word in ("космет", "парикмах", "салон", "уклад", "стриж", "волос")):
            return "Добрый день! Услуга уже отмечена как завершенная, но итоговый результат не соответствует тому, что мы согласовали. Поясните, пожалуйста, что именно сейчас считается готовым и как вы будете это исправлять."
        if type_code == "F01" and any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "коктейл", "гость", "меню")):
            return "Добрый день! Заказ уже отмечен как закрытый, но результат меня не устроил, и я не вижу зафиксированного решения по ситуации. Поясните, пожалуйста, что сейчас считается завершенным и что вы будете делать дальше."
        if type_code == "F01" and any(word in source for word in ("пищев", "партия", "сырье", "упаков", "маркиров", "карта партии", "линия производства", "отметка отк", "контролер отк")):
            return "Добрый день! Партия уже отмечена как переданная дальше, но подтверждения по контролю качества я не вижу. Поясните, пожалуйста, что сейчас действительно подтверждено и когда будет финальный статус."
        if type_code == "F01" and any(word in source for word in ("jira", "тз", "требован", "story", "аналит")):
            return "Добрый день! Задача уже отмечена как выполненная, но согласованного ТЗ и понятного итогового решения я не вижу. Поясните, пожалуйста, что именно сделано и когда я получу финальный результат."
        if type_code == "F01":
            return "Добрый день! Вы обещали ответить до 18:00. Сейчас уже 19:00, а ответа я так и не получила. Пожалуйста, объясните, что происходит и когда будет решение."
        if type_code in {"F03", "F12"}:
            return "Я считал, что задачу уже можно было передавать дальше и это не вызовет проблем."
        if type_code in {"F09", "F10", "F14", "F15"}:
            return f"Может, стоит попробовать изменить порядок работы по процессу «{scenario['workflow_label']}», чтобы сократить возвраты и повторные согласования?"
        return ""

    def _build_case_scenario_seed(
        self,
        *,
        domain: str,
        process: str,
        position: str | None,
        duties: str | None,
        role_name: str | None,
    ) -> dict[str, str]:
        source = f"{domain} {process} {position or ''} {duties or ''} {role_name or ''}".lower()

        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "предприят", "энергоблок", "реактор", "кд")):
            return {
                "team_contour": "группа инженерно-конструкторской подготовки",
                "system_name": "PLM-система и реестр конструкторской документации",
                "channel": "карточка задания в PLM и замечания в листе согласования",
                "issue_summary": "комплект документации передан дальше, хотя замечания по чертежам и исходные данные закрыты не полностью",
                "critical_step": "проверка замечаний по чертежам, фиксация следующего шага и подтверждение готовности комплекта",
                "source_of_truth": "карточка задания, лист согласования и комплект конструкторской документации",
                "work_items": "комплект КД по узлу, замечания по чертежам и задание на доработку проектных решений",
                "error_examples": "неучтенное замечание по чертежу, неполный комплект исходных данных, передача документации без подтвержденной проверки",
                "workflow_name": "подготовка и проверка конструкторской документации",
                "workflow_label": "подготовка и проверка конструкторской документации",
                "participant_names": "Сергей, Ирина, Павел",
                "ticket_titles": "«Комплект чертежей по узлу передан без закрытия замечаний», «Не подтверждена проверка изменений в чертеже», «Доработка КД ушла в смежное подразделение без финального согласования»",
                "request_type": "согласование замечаний и подтверждение готовности комплекта документации",
                "data_sources": "карточки заданий, листы согласования и комплект КД",
                "primary_stakeholder": "смежное подразделение, главный конструктор и руководитель группы",
                "adjacent_team": "смежный проектный отдел",
                "behavior_issue": "документация передается дальше до полного закрытия замечаний и согласования исходных данных",
                "team_context": "группа инженерно-конструкторской подготовки",
                "business_impact": "сроки выпуска документации, качество проектных решений и риск повторных доработок",
                "deadline": "к контрольной дате выпуска комплекта",
                "limits_short": "нельзя передавать комплект дальше без проверки замечаний, подтверждения исходных данных и фиксации решений",
                "incident_type": "передача документации с незакрытыми замечаниями",
                "incident_impact": "возврат комплекта на доработку, срыв срока и дополнительная проверка",
                "involved_teams": "конструкторская группа и смежный проектный отдел",
            }
        if any(
            word in source
            for word in (
                "судоход",
                "моряк",
                "судно",
                "корабл",
                "капитан",
                "вахт",
                "навигац",
                "порт",
                "экипаж",
                "рейс",
                "мостик",
                "лоцман",
                "швартов",
            )
        ):
            return {
                "team_contour": "вахта судна и командный состав рейса",
                "system_name": "судовой журнал, навигационная сводка и журнал вахты",
                "channel": "запись в судовом журнале, сообщения с мостика и сменный журнал вахты",
                "issue_summary": "этап рейсовой или вахтенной работы отмечен как завершенный, хотя следующий шаг, подтверждение обстановки или согласование действий экипажа закрыты не полностью",
                "critical_step": "проверка навигационной обстановки, фиксация следующего шага в журнале и подтверждение действий вахты",
                "source_of_truth": "судовой журнал, навигационная сводка, журнал вахты и распоряжения капитана",
                "work_items": "записи о маневре, задачи вахты, подготовка к швартовке и согласование действий экипажа",
                "error_examples": "следующий шаг по маневру не зафиксирован, вахта передана без полного подтверждения обстановки, распоряжение капитана исполнено частично",
                "workflow_name": "ведения вахты и координации судовых операций",
                "workflow_label": "ведение вахты и координация судовых операций",
                "participant_names": "Капитан, старший помощник, вахтенный офицер",
                "ticket_titles": "«Вахта передана без фиксации следующего маневра», «Подготовка к швартовке не подтверждена в журнале», «Распоряжение капитана выполнено частично без отметки о результате»",
                "request_type": "подтверждение статуса судовой операции и следующего шага экипажа",
                "data_sources": "судовой журнал, навигационная сводка, журнал вахты и распоряжения капитана",
                "primary_stakeholder": "капитан, командный состав и смежная береговая служба",
                "adjacent_team": "береговая служба или следующая вахта",
                "behavior_issue": "вахтенные действия отмечаются как завершенные до полного подтверждения обстановки, фиксации следующего шага и передачи информации экипажу",
                "team_context": "вахта судна и командный состав рейса",
                "business_impact": "безопасность судовых операций, сроки рейса и согласованность действий экипажа",
                "deadline": "до начала следующего этапа рейса или передачи вахты",
                "limits_short": "нельзя подтверждать завершение судовой операции без записи в журнале, подтверждения обстановки и согласования следующего шага с командным составом",
                "incident_type": "неполная фиксация или передача судовой операции",
                "incident_impact": "ошибка в координации вахты, задержка следующего этапа рейса и дополнительная проверка обстановки",
                "involved_teams": "вахта судна, командный состав и береговая служба",
            }
        if any(word in source for word in ("космет", "парикмах", "салон", "уклад", "стриж", "волос", "beauty", "барберш")):
            return {
                "team_contour": "смена салона красоты",
                "system_name": "журнал записи клиентов и карта услуги",
                "channel": "запись клиента, комментарии администратора и карта услуги",
                "issue_summary": "услуга отмечена как завершенная, хотя итоговый результат или следующий шаг с клиентом не подтверждены",
                "critical_step": "подтверждение результата с клиентом, фиксация замечаний и согласование корректирующего действия",
                "source_of_truth": "карта клиента, журнал записи и комментарии администратора салона",
                "work_items": "записи клиентов, карты услуг, замечания по результату стрижки или укладки",
                "error_examples": "результат не подтвержден клиентом, замечание по услуге не зафиксировано, следующий шаг после жалобы не согласован",
                "workflow_name": "обслуживание клиентов в салоне красоты",
                "workflow_label": "обслуживание клиентов в салоне красоты",
                "participant_names": "Марина, Ольга, Светлана",
                "ticket_titles": "«Клиент не подтвердил результат стрижки», «Замечание по укладке не зафиксировано в карте услуги», «Повторный визит после спорного результата услуги»",
                "request_type": "уточнение результата услуги и следующего шага по клиенту",
                "data_sources": "карта клиента, журнал записи и комментарии администратора",
                "primary_stakeholder": "клиент салона, администратор и руководитель смены",
                "adjacent_team": "администратор салона",
                "behavior_issue": "результат услуги отмечается как завершенный до полного подтверждения со стороны клиента",
                "team_context": "смена салона красоты",
                "business_impact": "удовлетворенность клиента, повторные визиты и репутация салона",
                "deadline": "до конца текущей смены",
                "limits_short": "нельзя обещать клиенту изменения вне регламента услуги и нужно фиксировать все договоренности в карте клиента",
                "incident_type": "некорректное закрытие услуги или отсутствие фиксации следующего шага по клиенту",
                "incident_impact": "повторная жалоба клиента и дополнительная корректировка услуги",
                "involved_teams": "мастер смены и администратор салона",
            }
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "официант", "хостес", "коктейл", "гость", "меню")):
            return {
                "team_contour": "смена бара и зала",
                "system_name": "POS-система и журнал смены бара",
                "channel": "лента заказов, комментарии администратора и журнал смены",
                "issue_summary": "заказ гостя или сменное действие отмечены как завершенные, хотя результат для гостя или следующий шаг фактически не подтверждены",
                "critical_step": "подтверждение результата с гостем, фиксация замечаний и согласование следующего действия по смене",
                "source_of_truth": "POS-система, журнал смены и комментарии администратора зала",
                "work_items": "чеки гостей, заказы по бару, возвраты по позициям и замечания по обслуживанию",
                "error_examples": "заказ закрыт до подтверждения гостя, замечание по напитку не зафиксировано, следующий шаг по конфликтной ситуации не назначен",
                "workflow_name": "обслуживание гостей и работа бара",
                "workflow_label": "обслуживание гостей и работа бара",
                "participant_names": "Илья, Марина, Светлана",
                "ticket_titles": "«Гость не подтвердил результат по заказу» , «Замечание по коктейлю не зафиксировано в журнале смены», «Конфликт по чеку закрыт без согласованного следующего шага»",
                "request_type": "уточнение результата обслуживания и следующего шага по гостю",
                "data_sources": "POS-система, журнал смены и комментарии администратора",
                "primary_stakeholder": "гость, администратор зала и старший смены",
                "adjacent_team": "администратор зала",
                "behavior_issue": "заказы или спорные ситуации закрываются до фактического подтверждения результата со стороны гостя",
                "team_context": "смена бара и зала",
                "business_impact": "удовлетворенность гостей, возвраты по заказам и выручка смены",
                "deadline": "до закрытия текущей смены",
                "limits_short": "нельзя обещать гостю компенсацию или менять правила обслуживания без согласования со старшим смены и нужно фиксировать замечания в журнале",
                "incident_type": "некорректное закрытие заказа или конфликтной ситуации по гостю",
                "incident_impact": "жалоба гостя, повторное приготовление и задержка работы смены",
                "involved_teams": "бар, зал и администратор смены",
            }
        if any(word in source for word in ("пищев", "продукц", "партия", "упаков", "сырье", "маркиров", "карта партии", "линия производства", "отметка отк", "контролер отк")):
            return {
                "team_contour": "производственная смена пищевого участка",
                "system_name": "журнал смены, лист контроля партии и система учета производства",
                "channel": "журнал смены, отметки ОТК и карта партии",
                "issue_summary": "партия или этап производства отмечены как завершенные, хотя контроль качества или следующий шаг еще не подтверждены",
                "critical_step": "подтверждение параметров партии, фиксация отклонений и согласование следующего этапа производства",
                "source_of_truth": "карта партии, журнал смены, лист контроля качества и комментарии технолога",
                "work_items": "партии продукции, листы контроля, замечания ОТК и задания на упаковку",
                "error_examples": "партия передана дальше без отметки ОТК, отклонение по сырью не зафиксировано, следующий этап запущен без подтвержденного решения",
                "workflow_name": "выпуск и контроль партии пищевой продукции",
                "workflow_label": "выпуск и контроль партии пищевой продукции",
                "participant_names": "Технолог, мастер смены, контролер ОТК",
                "ticket_titles": "«Партия передана на упаковку без отметки ОТК», «Отклонение по сырью не закрыто в карте партии», «Маркировка запущена без подтверждения корректирующего действия»",
                "request_type": "подтверждение статуса партии и следующего этапа производства",
                "data_sources": "карта партии, журнал смены, лист контроля качества и комментарии технолога",
                "primary_stakeholder": "мастер смены, технолог и контролер ОТК",
                "adjacent_team": "участок упаковки или контроля качества",
                "behavior_issue": "следующий этап производства запускается до полного подтверждения параметров партии и фиксации отклонений",
                "team_context": "производственная смена пищевого участка",
                "business_impact": "сроки выпуска партии, качество продукции и риск возврата или списания",
                "deadline": "до передачи партии на следующий этап",
                "limits_short": "нельзя передавать партию дальше без отметки контроля качества и нужно фиксировать все отклонения в карте партии",
                "incident_type": "передача партии с неподтвержденным контролем качества",
                "incident_impact": "возврат партии, остановка следующего этапа и дополнительные проверки",
                "involved_teams": "производственный участок, ОТК и участок упаковки",
            }
        if any(word in source for word in ("информационн", "ит ", " техпод", "helpdesk", "service desk", "картридж", "принтер", "vpn", "программное обеспечение", "рабочее место", "учетн", "поддержка рабочих мест", "заявок пользователей")):
            return {
                "team_contour": "линия ИТ-поддержки рабочих мест",
                "system_name": "Service Desk и журнал обращений",
                "channel": "очередь заявок и комментарии в Service Desk",
                "issue_summary": "пользователь не получил подтвержденный результат по заявке и повторно обращается в поддержку",
                "critical_step": "проверка фактического результата, фиксация следующего шага и обновление пользователя",
                "source_of_truth": "карточка заявки, история комментариев и статус в Service Desk",
                "work_items": "заявки на установку ПО, инциденты с принтерами и запросы на восстановление доступа",
                "error_examples": "закрытие заявки без подтверждения результата, незафиксированный следующий шаг, возврат инцидента после повторного обращения",
                "workflow_name": "поддержка рабочих мест и обработка заявок пользователей",
                "workflow_label": "поддержка рабочих мест и заявок пользователей",
                "participant_names": "Анна, Ирина, Максим",
                "ticket_titles": "«Не устанавливается VPN-клиент», «После замены картриджа принтер печатает с полосами», «Нет доступа к корпоративной почте после переустановки ПО»",
                "request_type": "обновление статуса по заявке или инциденту",
                "data_sources": "карточки заявок, истории комментариев и статуса в Service Desk",
                "primary_stakeholder": "пользователь, руководитель смены поддержки и смежная линия",
                "adjacent_team": "вторая линия ИТ-поддержки",
                "behavior_issue": "сотрудник закрывает заявку по статусу раньше, чем пользователь подтверждает фактический результат",
                "team_context": "линия ИТ-поддержки рабочих мест",
                "business_impact": "сроки решения заявок, повторные обращения и доверие внутренних пользователей к поддержке",
                "deadline": "до конца рабочей смены",
                "limits_short": "нельзя закрывать заявку без подтверждения результата и нужно фиксировать все действия в системе",
                "incident_type": "некорректное закрытие заявки или инцидента",
                "incident_impact": "повторное обращение пользователя и задержка следующего шага по заявке",
                "involved_teams": "ваша смена поддержки и вторая линия ИТ-поддержки",
            }
        if any(word in source for word in ("логист", "склад", "достав", "маршрут")):
            return {
                "team_contour": "смена логистической координации",
                "system_name": "TMS и складской журнал операций",
                "channel": "рабочий чат смены и журнал отгрузок",
                "issue_summary": "заказ завис на этапе отгрузки, а статус в системе не совпадает с фактическим выполнением",
                "critical_step": "подтверждение статуса отгрузки и переназначение ответственного по смене",
                "source_of_truth": "карточка отгрузки, журнал маршрутов и комментарии смены",
                "work_items": "отгрузки с отклонением по сроку, возвраты, внутренние запросы на переупаковку",
                "error_examples": "необновленный статус доставки, пропущенная отметка о приемке, дублирование задач между сменами",
                "workflow_name": "исполнение логистических операций",
                "workflow_label": "координация отгрузок и доставки",
                "participant_names": "Алексей, Марина, Олег",
                "ticket_titles": "«Отгрузка не ушла в рейс», «Статус доставки не обновлен», «Возврат на склад без комментария»",
                "request_type": "подтверждение статуса отгрузки",
                "data_sources": "карточки отгрузки, журнал маршрутов и комментарии смены",
                "primary_stakeholder": "логист, склад и руководитель смены",
                "adjacent_team": "складская смена",
                "behavior_issue": "ключевые действия выполняются без синхронизации со смежной сменой",
                "team_context": "смена логистической координации",
                "business_impact": "сроки отгрузки и обещания клиентам по доставке",
                "deadline": "до конца смены",
                "limits_short": "нельзя менять внешние сроки без согласования и нужно фиксировать статус в системе",
                "incident_type": "расхождение статуса отгрузки с фактическим выполнением",
                "incident_impact": "задержки в доставке и повторные ручные проверки",
                "involved_teams": "логистическая смена и складская команда",
            }
        if any(word in source for word in ("аналит", "требован", "бизнес-постанов", "постановк", "тз", "jira", "story", "критерии приемки")):
            return {
                "team_contour": "команда аналитики и постановки задач",
                "system_name": "Jira и база требований",
                "channel": "комментарии к задаче в Jira",
                "issue_summary": "задача была отмечена как выполненная, хотя согласованное ТЗ и итоговая логика остались непроясненными",
                "critical_step": "уточнение, что именно согласовано, и фиксация следующего шага по задаче",
                "source_of_truth": "карточка задачи, история комментариев и база требований",
                "work_items": "истории пользователя, запросы на доработку, дефекты после релиза",
                "error_examples": "неполные критерии приемки, незафиксированная договоренность по ТЗ, конфликт приоритетов",
                "workflow_name": "сбор и согласование требований",
                "workflow_label": "подготовка требований и постановка задач",
                "participant_names": "Никита, Дарья, Константин",
                "ticket_titles": "«ТЗ не согласовано, но задача уже закрыта», «Story без критериев приемки», «Доработка ушла в разработку без финальной договоренности»",
                "request_type": "уточнение и согласование требований по задаче",
                "data_sources": "карточки Jira, базу требований и комментарии команды",
                "primary_stakeholder": "заказчик, аналитик и команда разработки",
                "adjacent_team": "команда разработки",
                "behavior_issue": "задачи уходят в работу без единого понимания объема и критериев готовности",
                "team_context": "команда аналитики и постановки задач",
                "business_impact": "сроки реализации доработки и качество результата после релиза",
                "deadline": "к концу рабочего дня",
                "limits_short": "нельзя отправлять задачу в работу без согласованного объема и критериев готовности",
                "incident_type": "запуск работы по неполным требованиям",
                "incident_impact": "переделки, конфликт приоритетов и сдвиг срока релиза",
                "involved_teams": "аналитики и команда разработки",
            }
        if any(word in source for word in ("финанс", "счет", "оплат", "бюджет", "платеж")):
            return {
                "team_contour": "группа финансового согласования",
                "system_name": "1С и реестр платежных согласований",
                "channel": "очередь согласований и комментарии в карточке заявки",
                "issue_summary": "согласование платежа остановилось из-за расхождения данных и отсутствия подтвержденного следующего шага",
                "critical_step": "уточнение ответственного за согласование и фиксация срока следующего действия",
                "source_of_truth": "карточка заявки, история согласования и комментарии в 1С",
                "work_items": "заявки на оплату, срочные согласования, возвраты документов на доработку",
                "error_examples": "расхождение в сумме заявки, отсутствие подтверждающего документа, пропущенный срок согласования",
                "workflow_name": "финансовое согласование заявок",
                "workflow_label": "согласование платежей и заявок",
                "participant_names": "Елена, Сергей, Павел",
                "ticket_titles": "«Платеж завис на согласовании», «Возврат заявки из-за расхождения суммы», «Срочный счет без подтверждающих документов»",
                "request_type": "согласование платежа",
                "data_sources": "карточки заявки, историю согласования и комментарии в 1С",
                "primary_stakeholder": "инициатор заявки, финансовый контролер и руководитель подразделения",
                "adjacent_team": "финансовый контроль",
                "behavior_issue": "следующий шаг по согласованию не фиксируется вовремя",
                "team_context": "команда финансового согласования",
                "business_impact": "сроки оплаты и выполнение обязательств перед контрагентом",
                "deadline": "в течение рабочего дня",
                "limits_short": "нельзя проводить платеж без полного комплекта подтверждений",
                "incident_type": "остановка согласования заявки",
                "incident_impact": "задержка платежа и повторный цикл согласования",
                "involved_teams": "финансовый контроль и инициирующее подразделение",
            }
        if self._is_client_service_profile(position=position, duties=duties, company_industry=None):
            return {
                "team_contour": "команда клиентской поддержки и сервисной координации",
                "system_name": "CRM и журнал клиентских обращений",
                "channel": "очередь обращений, карточка клиента и служебные комментарии в CRM",
                "issue_summary": "по обращению клиента не зафиксирован следующий шаг или клиент не получил согласованное обновление по статусу",
                "critical_step": "подтверждение статуса обращения, фиксация следующего шага и согласование срока обратной связи клиенту",
                "source_of_truth": "карточка обращения, история коммуникации в CRM и внутренние комментарии команды",
                "work_items": "жалобы клиентов, запросы на обратную связь, эскалации по сервису и обращения с просроченным ответом",
                "error_examples": "клиенту не отправлено обновление, срок ответа сорван, эскалация ушла без владельца, смежная команда не подтвердила следующий шаг",
                "workflow_name": "обработка клиентских обращений и сервисная координация",
                "workflow_label": "клиентская поддержка и сопровождение обращений",
                "participant_names": "Мария, Олег, Светлана",
                "ticket_titles": [
                    "Клиент не получил ответ по обращению в обещанный срок",
                    "Жалоба эскалирована без назначенного владельца",
                    "Статус обращения обновлен в CRM, но клиент не уведомлен",
                ],
                "request_type": "обновление клиента по обращению и фиксация следующего шага",
                "data_sources": "карточки обращений, история переписки в CRM, комментарии смежных команд и журнал эскалаций",
                "primary_stakeholder": "клиент, руководитель клиентской поддержки и смежная сервисная команда",
                "adjacent_team": "смежная команда исполнения или экспертная линия",
                "behavior_issue": "команда обновляет статус обращения внутри системы, но не синхронизирует следующий шаг с клиентом и смежниками",
                "team_context": "команда клиентской поддержки и сервисной координации",
                "business_impact": "удовлетворенность клиента, сроки ответа и риск повторных жалоб",
                "deadline": "клиент ждет обновление до конца рабочего дня по SLA",
                "limits_short": "нельзя обещать клиенту срок или решение без подтверждения от ответственной команды и нужно фиксировать все обновления в CRM",
                "incident_type": "потеря следующего шага или статуса по клиентскому обращению",
                "incident_impact": "повторная жалоба клиента, эскалация и снижение доверия к сервису",
                "involved_teams": "клиентская поддержка, смежная сервисная команда и руководитель направления",
            }
        if any(word in source for word in ("обучен", "l&d", "lms", "курс", "тренинг", "учебн", "развит", "подрядчик", "эксперт")):
            return {
                "team_contour": "команда обучения и развития персонала",
                "system_name": "LMS, HRM и план-график обучения",
                "channel": "почта, календарь обучения и карточка программы в LMS/HRM",
                "issue_summary": "потребность в обучении или следующий шаг по программе не зафиксированы вовремя, из-за чего подготовка или проведение обучения останавливаются",
                "critical_step": "уточнение потребности, согласование формата программы и фиксация владельца следующего шага",
                "source_of_truth": "бриф на обучение, программа курса, карточка обучения в LMS/HRM и комментарии заказчика",
                "work_items": "запросы на обучение, программы курсов, списки участников, задачи подрядчику и формы обратной связи",
                "error_examples": "потребность в обучении понята неполно, программа не согласована в срок, подрядчик не получил подтвержденное ТЗ, обратная связь не собрана после обучения",
                "workflow_name": "планирование и организация обучения сотрудников",
                "workflow_label": "обучение и развитие персонала",
                "participant_names": "Елена, Наталья, Сергей",
                "ticket_titles": [
                    "Руководитель не подтвердил финальную потребность в обучении",
                    "Программа курса не согласована к старту",
                    "Подрядчик ждет утвержденное ТЗ по обучению",
                ],
                "request_type": "согласование обучения и следующего шага по программе",
                "data_sources": "брифы на обучение, карточки программ в LMS/HRM, календарь обучения и обратная связь участников",
                "primary_stakeholder": "руководитель подразделения, участники обучения и L&D-менеджер",
                "adjacent_team": "внутренние эксперты, HR / L&D-команда и внешний подрядчик",
                "behavior_issue": "следующий шаг по обучению не фиксируется вовремя или программа запускается без полного согласования потребности и ограничений",
                "team_context": "команда обучения и развития персонала",
                "business_impact": "срыв сроков запуска обучения, низкая вовлеченность участников и снижение эффекта программы",
                "deadline": "до старта программы осталось 3 рабочих дня",
                "limits_short": "нельзя обещать сроки, формат или результат обучения без согласования с заказчиком, графиком подразделения и доступностью эксперта или подрядчика",
                "incident_type": "срыв или остановка подготовки программы обучения",
                "incident_impact": "перенос обучения, потеря доверия заказчика и повторный цикл согласования",
                "involved_teams": "L&D-команда, руководитель подразделения, внутренние эксперты и подрядчик",
            }
        if any(word in source for word in ("hr", "персонал", "подбор", "адаптац", "сотрудник")):
            return {
                "team_contour": "команда подбора и адаптации",
                "system_name": "HRM и реестр кандидатов",
                "channel": "рабочий чат рекрутинга и карточка кандидата",
                "issue_summary": "по кандидату или сотруднику не зафиксирован следующий шаг, из-за чего процесс адаптации или подбора остановился",
                "critical_step": "назначение владельца следующего шага и фиксация срока обратной связи",
                "source_of_truth": "карточка кандидата, история статусов и комментарии в HRM",
                "work_items": "интервью, офферы, задачи по адаптации, запросы на обратную связь",
                "error_examples": "пропущенная обратная связь кандидату, незафиксированное решение по этапу, дублирование задач по адаптации",
                "workflow_name": "подбор и адаптация сотрудников",
                "workflow_label": "подбор и выход сотрудников",
                "participant_names": "Ольга, Виктор, Ксения",
                "ticket_titles": "«Кандидату не дали обратную связь после интервью», «Оффер не согласован в срок», «Задачи по адаптации без ответственного»",
                "request_type": "обратная связь кандидату или сотруднику",
                "data_sources": "карточки кандидата, историю статусов и комментарии в HRM",
                "primary_stakeholder": "кандидат, руководитель и HR-партнер",
                "adjacent_team": "команда подбора",
                "behavior_issue": "следующий шаг по кандидату или сотруднику не фиксируется вовремя",
                "team_context": "команда подбора и адаптации",
                "business_impact": "сроки выхода сотрудника и качество опыта кандидата",
                "deadline": "в течение ближайших двух дней",
                "limits_short": "нельзя обещать решение без согласования с руководителем",
                "incident_type": "потеря следующего шага по кандидату или сотруднику",
                "incident_impact": "срыв сроков подбора или адаптации и потеря доверия",
                "involved_teams": "HR-команда и нанимающий руководитель",
            }

        return {
            "team_contour": "рабочая группа участка",
            "system_name": "рабочий журнал и внутренний реестр задач",
            "channel": "рабочий журнал, служебные комментарии и внутренняя переписка команды",
            "issue_summary": "часть работы движется дальше без ясной фиксации следующего шага, владельца и подтверждения результата",
            "critical_step": "фиксирование следующего шага, ответственного и подтверждение результата по этапу работы",
            "source_of_truth": "рабочий журнал, карточка этапа и комментарии по текущей задаче",
            "work_items": "рабочие задачи участка, этапы выполнения и внутренние запросы на уточнение",
            "error_examples": "неполные входные данные, дублирование действий, пропущенная фиксация следующего шага",
            "workflow_name": process,
            "workflow_label": self._humanize_process_name(process),
            "participant_names": "Анна, Дмитрий, Игорь",
            "ticket_titles": "«Срочный внутренний запрос без владельца», «Этап работы не подтвержден в журнале», «Задача передана дальше без следующего шага»",
            "request_type": "уточнение статуса этапа работы и следующего шага",
            "data_sources": "рабочий журнал, карточки этапов и внутренние комментарии команды",
            "primary_stakeholder": "инициатор задачи, смежная команда и руководитель участка",
            "adjacent_team": "смежная рабочая группа",
            "behavior_issue": "часть задач выполняется без ясного владельца, подтвержденного результата и зафиксированного следующего шага",
            "team_context": "рабочая группа участка",
            "business_impact": "сроки выполнения работы, предсказуемость процесса и нагрузка на команду",
            "deadline": "в течение рабочего дня",
            "limits_short": "нельзя менять внешние приоритеты или подтверждать завершение этапа без фиксации результата и согласования следующего шага",
            "incident_type": "разрыв в передаче этапа работы или неполная фиксация результата",
            "incident_impact": "срыв срока, повторная работа и путаница в ответственности",
            "involved_teams": "ваш участок и смежная рабочая группа",
        }

    def _split_named_people(self, text: str | None) -> list[str]:
        raw = str(text or "").strip()
        if not raw:
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]

    def _build_case_theme_seed(
        self,
        *,
        case_type_code: str | None,
        case_title: str | None,
        workflow_label: str | None,
        shift_name: str | None,
        participant_names: str | None,
    ) -> int:
        parts = [
            str(case_type_code or "").upper(),
            str(case_title or ""),
            str(workflow_label or ""),
            str(shift_name or ""),
            str(participant_names or ""),
        ]
        return zlib.crc32("||".join(parts).encode("utf-8", errors="ignore")) & 0xFFFFFFFF

    def _apply_case_focus_variation(
        self,
        scenario: dict[str, str],
        *,
        case_type_code: str | None,
        case_title: str | None,
    ) -> dict[str, str]:
        result = dict(scenario or {})
        type_code = str(case_type_code or "").upper()
        people = self._split_named_people(result.get("participant_names"))
        primary_name = people[0] if people else "Анна Воронова"
        second_name = people[1] if len(people) > 1 else primary_name
        third_name = people[2] if len(people) > 2 else second_name
        family = self._infer_specificity_domain_family(result)
        workflow = str(result.get("workflow_label") or result.get("workflow_name") or "текущий процесс")
        shift_name = str(result.get("shift_name") or "текущая смена")
        deadline = str(result.get("deadline") or "к концу текущей смены")
        seed = self._build_case_theme_seed(
            case_type_code=type_code,
            case_title=case_title,
            workflow_label=workflow,
            shift_name=shift_name,
            participant_names=result.get("participant_names"),
        )
        variant = seed % 3

        def choose(*values: str) -> str:
            options = [value for value in values if str(value or "").strip()]
            if not options:
                return ""
            return options[variant % len(options)]

        if family == "it_support":
            if type_code == "F01":
                result["stakeholder_named_list"] = choose(
                    f"пользователь Антон Беляев, руководитель смены Ольга Назарова и инженер второй линии Илья Романов",
                    f"пользователь {second_name}, руководитель смены {primary_name} и инженер второй линии {third_name}",
                    f"внутренний заказчик {second_name}, руководитель смены {primary_name} и инженер второй линии {third_name}",
                )
                result["primary_stakeholder"] = choose("пользователь", "внутренний заказчик", "пользователь")
                result["work_items"] = choose(
                    "обращение #45821 по VPN для филиала «Север», повторная жалоба на закрытую заявку и запрос на подтверждение следующего шага",
                    "обращение #46107 по печати на участке логистики, комментарий о закрытии без результата и повторный запрос на обновление статуса",
                    "обращение #47214 по восстановлению доступа после переустановки ПО, жалоба на отсутствие ответа и запрос на эскалацию",
                )
                result["ticket_titles"] = choose(
                    "«Не получен ответ по обращению #45821», «VPN для филиала “Север” закрыт без подтверждения результата», «Повторная жалоба на статус в Service Desk»",
                    "«Не решена проблема печати на участке логистики», «Заявка закрыта без фактического результата», «Пользователь повторно просит обновление по статусу»",
                    "«Нет доступа после переустановки ПО», «Ответ по обращению не получен в обещанный срок», «Требуется эскалация по заявке с просроченным SLA»",
                )
                result["deadline"] = choose("до 18:00 текущей смены", "до 19:00 текущей смены", deadline)
            elif type_code == "F02":
                result["stakeholder_named_list"] = choose(
                    f"руководитель смены {primary_name}, инженер второй линии {third_name} и внутренний заказчик {second_name}",
                    f"руководитель смены {primary_name}, смежный инженер {second_name} и внутренний заказчик {third_name}",
                    f"руководитель смены {primary_name}, аналитик поддержки {second_name} и инженер второй линии {third_name}",
                )
                result["primary_stakeholder"] = "руководитель смены поддержки"
                result["request_type"] = choose(
                    "сводку по обращениям с просроченным обновлением статуса",
                    "список заявок, переданных дальше без подтвержденного следующего шага",
                    "подборку спорных обращений с повторными возвратами из Service Desk",
                )
                result["work_items"] = choose(
                    "заявки с просроченным обновлением статуса, обращения без подтвержденного следующего шага и возвраты после преждевременного закрытия",
                    "эскалации без владельца, заявки с повторным возвратом и обращения без итогового комментария пользователю",
                    "запросы на восстановление доступа, обращения по VPN и инциденты печати с неполным подтверждением результата",
                )
            elif type_code == "F03":
                result["stakeholder_named_list"] = choose(
                    f"сотрудник смены {second_name}, руководитель смены {primary_name} и инженер второй линии {third_name}",
                    f"специалист первой линии {second_name}, руководитель смены {primary_name} и внутренний заказчик {third_name}",
                    f"коллега {second_name}, руководитель смены {primary_name} и аналитик качества {third_name}",
                )
                result["behavior_issue"] = choose(
                    "сотрудник закрывает заявку по статусу раньше, чем пользователь подтверждает фактический результат",
                    "сотрудник передает обращение дальше без зафиксированного следующего шага и обновления пользователя",
                    "сотрудник меняет статус заявки до того, как команда согласует фактический результат и владельца следующего шага",
                )
            elif type_code == "F05":
                result["stakeholder_named_list"] = choose(
                    f"руководитель смены {primary_name}, специалист первой линии {second_name} и инженер второй линии {third_name}",
                    f"руководитель смены {primary_name}, координатор очереди {second_name} и инженер второй линии {third_name}",
                    f"руководитель смены {primary_name}, специалист по эскалациям {second_name} и инженер второй линии {third_name}",
                )
                result["work_items"] = choose(
                    "обращения по VPN для филиала «Север», инциденты печати на участке логистики и запросы на восстановление доступа после переустановки ПО",
                    "срочные запросы на установку ПО, повторные жалобы по закрытым обращениям и эскалации без владельца следующего шага",
                    "инциденты с корпоративной почтой, обращения по принтерам и задачи на обновление рабочих мест перед закрытием смены",
                )
            elif type_code == "F08":
                result["stakeholder_named_list"] = choose(
                    f"пользователь {second_name}, руководитель смены {primary_name} и инженер второй линии {third_name}",
                    f"внутренний заказчик {second_name}, руководитель смены {primary_name} и координатор очереди {third_name}",
                    f"пользователь {second_name}, руководитель смены {primary_name} и администратор домена {third_name}",
                )
                result["work_items"] = choose(
                    "повторная жалоба по VPN для филиала «Север», печать на участке логистики и восстановление доступа после переустановки ПО",
                    "обращение с истекающим SLA, заявка на восстановление доступа для нового сотрудника и инцидент с принтером на складе",
                    "срочный запрос по корпоративной почте, возврат по закрытой заявке и обращение по доступу к сетевому ресурсу",
                )
            elif type_code == "F09":
                result["stakeholder_named_list"] = choose(
                    f"руководитель смены {primary_name}, аналитик качества {second_name} и инженер второй линии {third_name}",
                    f"руководитель смены {primary_name}, внутренний заказчик {second_name} и специалист по эскалациям {third_name}",
                    f"руководитель смены {primary_name}, пользователь {second_name} и инженер второй линии {third_name}",
                )
                result["decision_theme"] = choose(
                    "как сократить долю повторных обращений без потери скорости закрытия заявок",
                    "как убрать преждевременное закрытие обращений и вернуть прозрачный следующий шаг",
                    "как снизить количество возвратов по спорным обращениям в пределах текущего состава смены",
                )
            elif type_code == "F10":
                result["stakeholder_named_list"] = choose(
                    f"руководитель смены {primary_name}, аналитик качества {second_name} и инженер второй линии {third_name}",
                    f"руководитель смены {primary_name}, координатор очереди {second_name} и администратор домена {third_name}",
                    f"руководитель смены {primary_name}, пользователь {second_name} и инженер второй линии {third_name}",
                )
                result["decision_theme"] = choose(
                    "стоит ли запускать обязательный чек-лист подтверждения результата перед закрытием обращения",
                    "нужно ли вводить явного владельца следующего шага в карточке заявки перед эскалацией",
                    "имеет ли смысл пилотировать новый шаблон обновления пользователя на спорных обращениях",
                )
            elif type_code == "F11":
                result["stakeholder_named_list"] = choose(
                    f"пользователь {second_name}, руководитель смены {primary_name} и инженер второй линии {third_name}",
                    f"внутренний заказчик {second_name}, руководитель смены {primary_name} и инженер второй линии {third_name}",
                    f"пользователь {second_name}, руководитель смены {primary_name} и администратор домена {third_name}",
                )
                result["issue_summary"] = choose(
                    "статус в Service Desk закрыт, а в комментариях по заявке нет подтверждения фактического результата",
                    "в карточке заявки указан завершенный шаг, но пользователь повторно пишет, что проблема не решена",
                    "по истории комментариев следующий шаг уже передан дальше, а подтверждение результата в Service Desk отсутствует",
                )
            elif type_code == "F12":
                result["stakeholder_named_list"] = choose(
                    f"сотрудник смены {second_name}, руководитель смены {primary_name} и инженер второй линии {third_name}",
                    f"специалист первой линии {second_name}, руководитель смены {primary_name} и аналитик качества {third_name}",
                    f"коллега {second_name}, руководитель смены {primary_name} и координатор очереди {third_name}",
                )
                result["behavior_issue"] = choose(
                    "сотрудник преждевременно закрывает спорные заявки и не фиксирует следующий шаг",
                    "сотрудник передает обращение дальше без понятного статуса для пользователя и команды",
                    "сотрудник формально завершает заявку, хотя подтверждение результата еще не получено",
                )
        else:
            if type_code in {"F03", "F12"}:
                result["stakeholder_named_list"] = choose(
                    f"{primary_name}, {second_name} и {third_name}",
                    f"{second_name}, {primary_name} и {third_name}",
                    f"{second_name}, {third_name} и {primary_name}",
                )
            elif type_code in {"F05", "F08"}:
                result["work_items"] = choose(
                    str(result.get("work_items") or ""),
                    str(result.get("work_items") or ""),
                    str(result.get("work_items") or ""),
                )
        return result

    def _enrich_scenario_seed(
        self,
        scenario: dict[str, str],
        *,
        domain: str,
        process: str,
        position: str | None,
        duties: str | None,
        role_name: str | None,
        case_type_code: str | None = None,
        case_title: str | None = None,
    ) -> dict[str, str]:
        result = dict(scenario or {})
        source = " ".join(
            [
                str(domain or ""),
                str(process or ""),
                str(position or ""),
                str(duties or ""),
                str(result.get("workflow_label") or ""),
                str(result.get("team_contour") or ""),
            ]
        ).lower()

        def fill_defaults(*, names: str, shift_name: str, shift_duration: str, resource_profile: str, metric_label: str, metric_delta: str, stakeholder_named_list: str, audience_label: str, strategic_scope: str, dependencies: str, business_criteria: str, decision_theme: str, work_items: str | None = None, deadline: str | None = None, team_scope_label: str | None = None) -> dict[str, str]:
            result["participant_names"] = names
            result["shift_name"] = shift_name
            result["shift_duration"] = shift_duration
            result["resource_profile"] = resource_profile
            result["metric_label"] = metric_label
            result["metric_delta"] = metric_delta
            result["stakeholder_named_list"] = stakeholder_named_list
            result["audience_label"] = audience_label
            result["strategic_scope"] = strategic_scope
            result["dependencies"] = dependencies
            result["business_criteria"] = business_criteria
            result["decision_theme"] = decision_theme
            result["time_resource_limit"] = f"{resource_profile}; горизонт работы — {shift_duration}"
            result["team_scope_label"] = team_scope_label or f"{result.get('team_contour') or 'рабочая группа'}, {shift_name}"
            if work_items:
                result["work_items"] = work_items
            if deadline:
                result["deadline"] = deadline
            return result

        if any(word in source for word in ("ит-поддерж", "service desk", "vpn", "рабочих мест", "заявок пользователей")):
            result = fill_defaults(
                names="Ольга Назарова, Антон Беляев, Илья Романов",
                shift_name="вечерняя смена поддержки «Север»",
                shift_duration="8 часов, с 14:00 до 22:00",
                resource_profile="2 специалиста первой линии на смене и 1 инженер второй линии на подхвате",
                metric_label="показателях вечерней смены: среднем времени решения обращений и доле повторных обращений",
                metric_delta="За последние 2 недели среднее время решения выросло с 3,5 до 5 часов, а доля повторных обращений — с 9% до 17%",
                stakeholder_named_list="пользователь Антон Беляев, руководитель смены Ольга Назарова и инженер второй линии Илья Романов",
                audience_label="пользователей вечерней смены офиса и внутренних заказчиков",
                strategic_scope="устойчивость линии поддержки рабочих мест и качество закрытия обращений",
                dependencies="второй линии ИТ-поддержки, администратора домена и окна обновления ПО",
                business_criteria="SLA первой линии, доля повторных обращений и своевременность обновления пользователя",
                decision_theme="нужно ли передавать заявку дальше при неполном подтверждении результата и истекающем SLA",
                work_items="обращения по VPN для филиала «Север», инциденты печати на участке логистики и запросы на восстановление доступа после переустановки ПО",
                deadline="к 18:00 текущей смены",
                team_scope_label="вечерняя смена первой линии ИТ-поддержки",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        if any(word in source for word in ("инженер", "конструкт", "чертеж", "документац", "кд", "plm", "конструкторск")):
            result = fill_defaults(
                names="Сергей Волков, Ирина Крылова, Павел Демин",
                shift_name="инженерная смена КБ «Орион»",
                shift_duration="8 часов, с 09:00 до 18:00",
                resource_profile="ведущий конструктор, инженер-конструктор и нормоконтроль на согласовании",
                metric_label="показателях конструкторского блока: сроке выпуска комплекта КД и доле возвратов на доработку",
                metric_delta="За 3 недели срок выпуска комплекта вырос с 4 до 6 дней, а доля возвратов на доработку — с 8% до 15%",
                stakeholder_named_list="главный конструктор Сергей Волков, инженер-конструктор Ирина Крылова и специалист нормоконтроля Павел Демин",
                audience_label="смежных инженерных подразделений, нормоконтроля и производства",
                strategic_scope="устойчивость выпуска конструкторской документации и качество передачи комплекта в производство",
                dependencies="PLM-системы, листа согласования, нормоконтроля и подтверждения смежного подразделения",
                business_criteria="срок выпуска КД, доля возвратов на доработку и число незакрытых замечаний перед передачей",
                decision_theme="можно ли передавать комплект документации дальше без полного закрытия замечаний и подтверждения версии",
                work_items="комплект КД по узлу, замечания по чертежам, спецификация и лист согласования изменений",
                deadline="к контрольной дате выпуска комплекта",
                team_scope_label="конструкторский блок и нормоконтроль",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        if any(word in source for word in ("клиентск", "жалоб", "обращен", "crm", "сервисн", "поддержк клиентов")):
            result = fill_defaults(
                names="Анна Воронова, Дмитрий Громов, Игорь Лапшин",
                shift_name="дневная сервисная смена «Клиентский контур»",
                shift_duration="8 часов, с 09:00 до 18:00",
                resource_profile="2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях",
                metric_label="показателях клиентского сервиса: сроке первого ответа, доле повторных жалоб и прозрачности статуса обращения",
                metric_delta="За 2 недели срок первого ответа вырос с 45 до 80 минут, а доля повторных жалоб — с 6% до 12%",
                stakeholder_named_list="клиент Анна Воронова, руководитель клиентской поддержки Дмитрий Громов и координатор эскалаций Игорь Лапшин",
                audience_label="клиентов сервиса и смежной сервисной команды",
                strategic_scope="стабильность клиентского сервиса и управляемость эскалированных обращений",
                dependencies="CRM, журнала эскалаций, смежной сервисной команды и подтверждения следующего шага",
                business_criteria="срок первого ответа, доля повторных жалоб и прозрачность статуса обращения",
                decision_theme="что взять в работу первым, чтобы удержать SLA и не потерять контроль над эскалированным обращением",
                work_items="обращение с просроченным ответом, жалоба без назначенного владельца и статус в CRM без обновления клиента",
                deadline="клиент ждет обновление до конца рабочего дня по SLA",
                team_scope_label="линия клиентской поддержки и эскалаций",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        if any(word in source for word in ("обучен", "развити", "l&d", "lms", "тренинг", "курс", "подрядчик", "эксперт")):
            result = fill_defaults(
                names="Елена Соколова, Наталья Козлова, Сергей Мельников",
                shift_name="проектный цикл обучения «Весна»",
                shift_duration="рабочая неделя запуска программы",
                resource_profile="L&D-менеджер, внутренний эксперт и подрядчик на согласовании программы",
                metric_label="показателях программы: сроке запуска обучения, вовлеченности участников и доле завершения программы",
                metric_delta="За квартал средний срок запуска программ вырос с 10 до 16 дней, а доля завершения — снизилась с 92% до 84%",
                stakeholder_named_list="руководитель подразделения Елена Соколова, внутренний эксперт Наталья Козлова и подрядчик Сергей Мельников",
                audience_label="заказчиков обучения, участников программы и HR / L&D-команды",
                strategic_scope="предсказуемость запуска программ обучения и качество согласования потребности",
                dependencies="LMS, календаря обучения, подтверждения руководителя и готовности подрядчика",
                business_criteria="срок запуска программы, вовлеченность участников и доля завершения обучения",
                decision_theme="что делать в первую очередь, если потребность и формат программы еще не согласованы до конца",
                work_items="потребность в обучении, программа курса, список участников и ТЗ подрядчику",
                deadline="до старта программы осталось 3 рабочих дня",
                team_scope_label="контур обучения и развития персонала",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        if any(word in source for word in ("jira", "требован", "аналит", "постановк", "разработк")):
            result = fill_defaults(
                names="Дарья Морозова, Никита Савельев, Константин Рябов",
                shift_name="аналитическая смена продукта «Core»",
                shift_duration="8 часов, с 10:00 до 19:00",
                resource_profile="1 ведущий аналитик, 1 системный аналитик и 1 разработчик на уточнения",
                metric_label="показателях продукта: доле возвратов задач из разработки и среднем времени согласования требований",
                metric_delta="За месяц доля возвратов выросла с 12% до 21%, а среднее согласование требований — с 1,5 до 3 дней",
                stakeholder_named_list="заказчик Дарья Морозова, аналитик Никита Савельев и тимлид разработки Константин Рябов",
                audience_label="внутренних заказчиков продукта и команду разработки",
                strategic_scope="качество подготовки требований и предсказуемость релизного контура",
                dependencies="заказчика, команды разработки и окна планирования релиза",
                business_criteria="доля возвратов из разработки, скорость согласования ТЗ и стабильность релизного плана",
                decision_theme="можно ли запускать задачу в разработку без финального согласования объема и критериев готовности",
                work_items="story по срочной доработке биллинга, согласование критериев приемки и обновление ТЗ по спорному требованию",
                deadline="к 16:00 текущего рабочего дня",
                team_scope_label="команда аналитики и постановки задач продукта «Core»",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        if any(word in source for word in ("вахт", "суд", "мор", "кораб", "экипаж", "порт")):
            result = fill_defaults(
                names="Сергей Колесников, Алексей Пахомов, Роман Устинов",
                shift_name="вахта «Браво»",
                shift_duration="4 часа, с 08:00 до 12:00",
                resource_profile="3 человека на мостике и старший помощник капитана на подтверждении",
                metric_label="показателях вахты: времени передачи смены и числе повторных уточнений по действиям экипажа",
                metric_delta="За 3 рейса время передачи вахты выросло с 12 до 20 минут, а число повторных уточнений — с 1 до 4 за смену",
                stakeholder_named_list="капитан Сергей Колесников, старший помощник Алексей Пахомов и вахтенный офицер Роман Устинов",
                audience_label="капитана, следующей вахты и береговой службы",
                strategic_scope="безопасность судовых операций и устойчивость передачи вахты",
                dependencies="судового журнала, подтверждения капитана и следующей вахты",
                business_criteria="безошибочная передача вахты, время согласования следующего маневра и отсутствие повторных уточнений",
                decision_theme="можно ли передавать вахту дальше без полного подтверждения следующего маневра",
                work_items="подтверждение следующего маневра, уточнение записи в судовом журнале и передача команды следующей вахте",
                deadline="до 11:40 текущей вахты",
                team_scope_label="вахта «Браво» на мостике",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        if any(word in source for word in ("бар", "гост", "ресторан", "смены", "pos")):
            result = fill_defaults(
                names="Марина Орлова, Илья Фадеев, Светлана Кузнецова",
                shift_name="вечерняя смена бара «Amber»",
                shift_duration="10 часов, с 12:00 до 22:00",
                resource_profile="2 бармена, 1 администратор зала и 1 старший смены",
                metric_label="показателях смены: среднем времени закрытия спорных ситуаций по гостям и доле возвратов по заказам",
                metric_delta="За 10 смен среднее время разбора выросло с 6 до 11 минут, а возвраты по заказам — с 4% до 9%",
                stakeholder_named_list="гость Марина Орлова, администратор зала Светлана Кузнецова и старший смены Илья Фадеев",
                audience_label="гостей вечерней смены и администратора зала",
                strategic_scope="качество сервиса бара и стабильность передачи смены",
                dependencies="POS-системы, журнала смены и решения администратора зала",
                business_criteria="скорость закрытия спорных ситуаций, доля возвратов и выручка смены",
                decision_theme="можно ли закрыть спорную ситуацию без полного подтверждения результата со стороны гостя",
                work_items="спорные заказы по коктейлям, возвраты по чеку и передача нерешенных замечаний следующей смене",
                deadline="до закрытия смены в 22:00",
                team_scope_label="вечерняя смена бара и зала",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        if any(word in source for word in ("пищев", "отк", "парти", "упаков")):
            result = fill_defaults(
                names="Татьяна Смирнова, Павел Егоров, Денис Королев",
                shift_name="смена участка упаковки №2",
                shift_duration="12 часов, с 08:00 до 20:00",
                resource_profile="мастер смены, технолог и контролер ОТК на партии",
                metric_label="показателях смены: времени выпуска партии и доле возвратов на повторный контроль",
                metric_delta="За неделю время выпуска выросло с 5,2 до 6,4 часа, а возвраты на повторный контроль — с 3% до 8%",
                stakeholder_named_list="мастер смены Татьяна Смирнова, технолог Павел Егоров и контролер ОТК Денис Королев",
                audience_label="производственной смены, ОТК и участка упаковки",
                strategic_scope="устойчивость выпуска партии и качество подтверждения отклонений",
                dependencies="карты партии, листа контроля и подтверждения технолога",
                business_criteria="время выпуска партии, доля возвратов на контроль и процент незакрытых отклонений",
                decision_theme="можно ли передавать партию на следующий этап без полного подтверждения замечаний ОТК",
                work_items="партии с отклонением по сырью, задания на упаковку и корректирующие действия по маркировке",
                deadline="до 19:30 текущей смены",
                team_scope_label="смена участка упаковки №2",
            )
            return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)
        result = fill_defaults(
            names="Анна Воронова, Дмитрий Громов, Игорь Лапшин",
            shift_name="дневная смена участка «Альфа»",
            shift_duration="8 часов, с 09:00 до 18:00",
            resource_profile="2 сотрудника участка и 1 смежный специалист на согласовании",
            metric_label="показателях участка: сроке выполнения задач и доле возвратов на доработку",
            metric_delta="За 2 недели срок выполнения вырос с 1,2 до 1,8 дня, а возвраты на доработку — с 11% до 19%",
            stakeholder_named_list="руководитель участка Анна Воронова, смежный специалист Дмитрий Громов и координатор Игорь Лапшин",
            audience_label="внутренних заказчиков участка и смежной команды",
            strategic_scope="предсказуемость работы участка и качество передачи следующего шага",
            dependencies="смежной рабочей группы, внутреннего журнала и подтверждения следующего шага",
            business_criteria="срок выполнения задач, доля возвратов и прозрачность статуса работ",
            decision_theme="можно ли передавать задачу дальше без полного подтверждения результата и владельца следующего шага",
            team_scope_label="дневная смена участка «Альфа»",
        )
        return self._apply_case_focus_variation(result, case_type_code=case_type_code, case_title=case_title)

    def _humanize_process_name(self, process: str | None) -> str:
        value = (process or "").strip()
        lowered = value.lower()
        mapping = {
            "обработки клиентских обращений": "работа с клиентскими обращениями",
            "исполнения логистических операций": "координация отгрузок и доставки",
            "финансового согласования": "согласование платежей",
            "финансовое согласование заявок": "согласование платежей и заявок",
            "сбора и согласования требований": "подготовка требований и постановка задач",
            "подбора и адаптации сотрудников": "подбор и выход сотрудников",
            "исполнения ключевого рабочего процесса": "текущая операционная работа команды",
        }
        return mapping.get(lowered, value or "текущая операционная работа команды")

    def _should_prioritize_runtime_domain(
        self,
        *,
        position: str | None,
        duties: str | None,
        company_industry: str | None,
    ) -> bool:
        source = f"{position or ''} {duties or ''} {company_industry or ''}".lower()
        if self._is_learning_and_development_profile(
            position=position,
            duties=duties,
            company_industry=company_industry,
        ):
            return True
        if self._is_engineering_industry_profile(position=position, duties=duties, company_industry=company_industry):
            return True
        if self._is_it_support_profile(position=position, duties=duties, company_industry=company_industry):
            return True
        return any(
            word in source
            for word in (
                "аналит",
                "требован",
                "business analyst",
                "бизнес-постанов",
                "jira",
                "story",
                "критерии приемки",
            )
        )

    def _infer_domain(self, *, position: str | None, duties: str | None, company_industry: str | None = None) -> str:
        source = f"{position or ''} {duties or ''}".lower()
        if any(hint in source for hint in ("обучен", "l&d", "lms", "курс", "тренинг", "учебн", "развит")):
            return "обучения и развития персонала"
        if self._is_engineering_industry_profile(position=position, duties=duties, company_industry=company_industry):
            return "разработки программных продуктов"
        if self._is_it_support_profile(position=position, duties=duties, company_industry=company_industry):
            return "ИТ-поддержки"
        if any(hint in source for hint in ("аналит", "требован", "бизнес-постанов", "постановк", "jira", "story", "критерии приемки")):
            return "бизнес-аналитики"
        company_value = self._fallback_normalize_company_industry(company_industry)
        if company_value:
            return company_value
        if self._is_client_service_profile(position=position, duties=duties, company_industry=company_industry):
            return "клиентского сервиса"
        mapping = [
            (("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "реактор", "энергоблок"), "инженерно-конструкторской деятельности"),
            (("космет", "парикмах", "салон", "уклад", "стриж", "волос", "beauty"), "салонных и бьюти-услуг"),
            (("судоход", "моряк", "судно", "корабл", "капитан", "вахт", "навигац", "порт", "экипаж", "рейс", "мостик"), "судоходства и морских перевозок"),
            (("бармен", "бар", "ресторан", "общепит", "официант", "хостес", "коктейл", "гость", "меню"), "общественного питания и ресторанного сервиса"),
            (("пищев", "продукц", "партия", "упаков", "сырье", "маркиров", "карта партии", "линия производства", "отметка отк", "контролер отк"), "пищевого производства"),
            (("аналитик", "бизнес", "постановк", "требован"), "бизнес-аналитики"),
            (("картридж", "принтер", "программное обеспечение", "рабочее место", "учетн", "техпод", "helpdesk"), "ИТ-поддержки"),
            (("обучен", "l&d", "lms", "курс", "тренинг", "учебн", "развит"), "обучения и развития персонала"),
            (("hr", "персонал", "подбор", "сотрудник", "кадров"), "управления персоналом"),
            (("поддержк", "обращен", "клиент", "сервис"), "клиентского сервиса"),
            (("финанс", "бюджет", "оплат", "счет"), "финансового учета"),
            (("логист", "постав", "склад", "достав"), "логистики"),
            (("продаж", "crm", "сделк"), "продаж"),
            (("маркет", "кампан", "трафик"), "маркетинга"),
            (("проект", "delivery", "roadmap"), "проектного управления"),
        ]
        for hints, value in mapping:
            if any(hint in source for hint in hints):
                return value
        return "операционной деятельности"

    def _infer_process(self, *, position: str | None, duties: str | None) -> str:
        source = f"{position or ''} {duties or ''}".lower()
        if any(word in source for word in ("ядер", "энергет", "инженер", "конструкт", "чертеж", "документац", "реактор", "энергоблок")):
            return "подготовки и проверки конструкторской документации"
        if any(
            word in source
            for word in (
                "разработ",
                "developer",
                "backend",
                "frontend",
                "fullstack",
                "full stack",
                "devops",
                "python",
                "java",
                "golang",
                "javascript",
                "typescript",
                "ml",
                "machine learning",
                "data science",
                "прод",
                "релиз",
                "деплой",
                "код",
            )
        ):
            return "разработки, вывода в прод и сопровождения программных решений"
        if any(word in source for word in ("космет", "парикмах", "салон", "уклад", "стриж", "волос", "beauty")):
            return "обслуживания клиентов в салоне красоты"
        if any(word in source for word in ("судоход", "моряк", "судно", "корабл", "капитан", "вахт", "навигац", "порт", "экипаж", "рейс", "мостик")):
            return "ведения вахты и координации судовых операций"
        if any(word in source for word in ("бармен", "бар", "ресторан", "общепит", "официант", "хостес", "коктейл", "гость", "меню")):
            return "обслуживания гостей и работы бара"
        if any(word in source for word in ("пищев", "продукц", "партия", "упаков", "сырье", "маркиров", "карта партии", "линия производства", "отметка отк", "контролер отк")):
            return "выпуска и контроля партии пищевой продукции"
        if any(word in source for word in ("постановк", "требован", "аналитик", "бизнес")):
            return "сбора и согласования требований"
        if self._is_client_service_profile(position=position, duties=duties, company_industry=None):
            return "обработки клиентских обращений и координации сервиса"
        if any(word in source for word in ("картридж", "принтер", "программное обеспечение", "рабочее место", "учетн", "техпод", "helpdesk")):
            return "поддержки рабочих мест и обработки заявок пользователей"
        if any(word in source for word in ("обучен", "l&d", "lms", "курс", "тренинг", "учебн", "развит")):
            return "планирования и организации обучения сотрудников"
        if any(word in source for word in ("персонал", "hr", "подбор")):
            return "подбора и адаптации сотрудников"
        if any(word in source for word in ("поддержк", "обращен", "клиент")):
            return "обработки клиентских обращений"
        if any(word in source for word in ("финанс", "бюджет")):
            return "финансового согласования"
        if any(word in source for word in ("логист", "склад", "достав")):
            return "исполнения логистических операций"
        return "исполнения ключевого рабочего процесса"

    def _fallback_normalize_company_industry(self, company_industry: str | None) -> str | None:
        original = (company_industry or "").strip()
        if not original:
            return None
        original = re.sub(r"\s+роль\s*:\s*.+$", "", original, flags=re.IGNORECASE).strip(" /")
        cleaned = original.lower().replace("ё", "е")
        if not cleaned:
            return None
        mapping = [
            (("банк", "финанс", "страх", "инвест"), "финансовых услуг"),
            (("it", "ит", "айти", "software", "saas", "цифров", "разработк", "продукт", "jira", "тз"), "информационных технологий"),
            (("ритейл", "рознич", "магазин", "e-commerce", "ecommerce", "маркетплейс"), "розничной торговли"),
            (("логист", "склад", "достав", "транспорт"), "логистики и транспорта"),
            (("телеком", "связ", "оператор"), "телекоммуникаций"),
            (("медиц", "здрав", "фарма", "клиник"), "здравоохранения и фармацевтики"),
            (("образован", "обучен", "университет", "школ"), "образования"),
            (("производ", "завод", "фабрик", "промышл"), "производства"),
            (("строит", "девелоп", "недвиж"), "строительства и недвижимости"),
            (("госс", "государ", "муницип", "бюджет"), "государственного сектора"),
            (("энерг", "нефт", "газ", "электр"), "энергетики"),
            (("судоход", "морск", "судно", "корабл", "порт", "экипаж", "рейс"), "судоходства и морских перевозок"),
            (("агро", "сельск", "ферм"), "агропромышленного комплекса"),
            (("маркет", "реклам", "бренд", "pr"), "маркетинга и рекламы"),
        ]
        for hints, value in mapping:
            if any(hint in cleaned for hint in hints):
                return value
        return original or None

    def _sanitize_personalization_value(self, value: str) -> str:
        cleaned = (value or "").strip().strip(".")
        lowered = cleaned.lower()
        if lowered in {"изменений нет", "нет изменений", "нет измеенний", "не изменилось", "не изменений", "без изменений"}:
            return ""
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1].strip()
        return cleaned

    def _scenario_from_case_text(self, *, case_title: str, text: str) -> dict[str, str]:
        source = f"{case_title} {text}".lower()
        maritime_markers = ("судоход", "морск", "судно", "корабл", "вахт", "экипаж", "рейс", "капитан", "судовой журнал", "мостик", "швартов", "маневр")
        if (
            any(marker in source for marker in ("клиент написал", "ответить клиент", "сообщение клиент", "письмо клиент", "первого ответа", "первым ответить клиенту", "жалоб", "заказчик"))
            and not any(word in source for word in ("разговор", "бесед", "коллег", "личный разговор"))
        ):
            return {
                "ticket_example": "«Нет ответа по обращению #45821»",
                "ticket_titles_short": "тикет «Нет ответа по обращению #45821», инцидент «Повторная жалоба на задержку ответа» и запрос на эскалацию по обращению крупного клиента",
                "ticket_title_list": [
                    "тикет «Нет ответа по обращению #45821»",
                    "инцидент «Повторная жалоба на задержку ответа»",
                    "запрос на эскалацию по обращению крупного клиента",
                ],
                "employee_name": "Анна",
                "workflow_label": "работа с клиентскими обращениями",
                "case_card_title": "№45821",
                "case_card_subject": "«Нет ответа клиенту после обещанного срока»",
            }
        if any(word in source for word in ("разговор", "бесед", "коллег", "развивающ", "личный разговор")):
            if any(word in source for word in maritime_markers):
                return {
                    "ticket_example": "«Передача вахты без подтвержденного следующего маневра»",
                    "ticket_titles_short": "передача вахты без подтвержденного следующего маневра, повторные уточнения по судовому журналу и возврат к уже согласованным действиям экипажа",
                    "ticket_title_list": [
                        "передача вахты без подтвержденного следующего маневра",
                        "повторные уточнения по судовому журналу",
                        "возврат к уже согласованным действиям экипажа",
                    ],
                    "employee_name": "Алексей",
                    "workflow_label": "разбор качества передачи вахты и координации экипажа",
                    "case_card_title": "№M-18317",
                    "case_card_subject": "«Повторные возвраты к уже переданной вахте»",
                }
            return {
                "ticket_example": "«Повторное закрытие обращения без решения»",
                "ticket_titles_short": "повторное закрытие обращения без решения, жалобы коллег на возвраты и рост повторных обращений",
                "ticket_title_list": [
                    "повторное закрытие обращения без решения",
                    "жалобы коллег на возвраты",
                    "рост повторных обращений",
                ],
                "employee_name": "Максим",
                "workflow_label": "разбор качества работы по обращениям",
                "case_card_title": "№18317",
                "case_card_subject": "«Повторные возвраты по обращениям после закрытия»",
            }
        if any(word in source for word in ("согласован", "смежн", "инцидент", "сбой", "ошибк", "эскалац")):
            if any(word in source for word in maritime_markers):
                return {
                    "ticket_example": "«Передача вахты без фиксации следующего маневра»",
                    "ticket_titles_short": "инцидент «Передача вахты без фиксации следующего маневра», запись в судовом журнале с неполным подтверждением результата и разбор «Следующий шаг экипажа не был явно подтвержден при смене вахты»",
                    "ticket_title_list": [
                        "инцидент «Передача вахты без фиксации следующего маневра»",
                        "запись в судовом журнале с неполным подтверждением результата",
                        "разбор «Следующий шаг экипажа не был явно подтвержден при смене вахты»",
                    ],
                    "employee_name": "Елена",
                    "workflow_label": "локальный разбор инцидента при передаче вахты",
                    "case_card_title": "№M-31244",
                    "case_card_subject": "«Противоречивые данные по передаче вахты и следующему маневру»",
                }
            return {
                "ticket_example": "«Некорректное закрытие обращения после внутренней обработки»",
                "ticket_titles_short": "инцидент «Некорректное закрытие обращения после внутренней обработки», тикет «Не совпадают статусы в Service Desk и фактический результат» и запись разбора «Следующий шаг не был зафиксирован после закрытия»",
                "ticket_title_list": [
                    "инцидент «Некорректное закрытие обращения после внутренней обработки»",
                    "тикет «Не совпадают статусы в Service Desk и фактический результат»",
                    "запись разбора «Следующий шаг не был зафиксирован после закрытия»",
                ],
                "employee_name": "Елена",
                "workflow_label": "локальный разбор инцидента и восстановление корректного статуса",
                "case_card_title": "№31244",
                "case_card_subject": "«Противоречивые данные по закрытию обращения и следующему шагу»",
            }
        if any(word in source for word in ("смен", "групп", "роли", "план")):
            if any(word in source for word in maritime_markers):
                return {
                    "ticket_example": "«Передача вахты без подтвержденного следующего маневра»",
                    "ticket_titles_short": "передача вахты без подтвержденного следующего маневра, уточнение записи в судовом журнале и ожидание распоряжения по ближайшему действию экипажа",
                    "ticket_title_list": [
                        "передача вахты без подтвержденного следующего маневра",
                        "уточнение записи в судовом журнале",
                        "ожидание распоряжения по ближайшему действию экипажа",
                    ],
                    "employee_name": "Игорь",
                    "workflow_label": "координация задач вахты и передачи смены",
                    "case_card_title": "№M-27104",
                    "case_card_subject": "«Передача вахты без закрепленных действий и приоритетов»",
                }
            return {
                "ticket_example": "«Задержка статуса по срочному инциденту»",
                "ticket_titles_short": "тикет «Задержка статуса по срочному инциденту», запрос «Нужна эскалация по клиентскому обращению» и задача «Передать смену без потери приоритетов»",
                "ticket_title_list": [
                    "тикет «Задержка статуса по срочному инциденту»",
                    "запрос «Нужна эскалация по клиентскому обращению»",
                    "задача «Передать смену без потери приоритетов»",
                ],
                "employee_name": "Игорь",
                "workflow_label": "координация задач смены",
                "case_card_title": "№27104",
                "case_card_subject": "«Смена без закрепленных ролей и очереди задач»",
            }
        if any(word in source for word in ("иде", "решени", "гипотез", "предлож")):
            if any(word in source for word in maritime_markers):
                return {
                    "ticket_example": "«Сократить возвраты к уже переданной вахте»",
                    "ticket_titles_short": "инициатива «Сократить возвраты к уже переданной вахте», спор по порядку подтверждения маневра и риск лишней нагрузки на экипаж",
                    "ticket_title_list": [
                        "инициатива «Сократить возвраты к уже переданной вахте»",
                        "спор по порядку подтверждения маневра",
                        "риск лишней нагрузки на экипаж",
                    ],
                    "employee_name": "Дарья",
                    "workflow_label": "изменение порядка передачи вахты и подтверждения следующего шага",
                    "case_card_title": "№M-21409",
                    "case_card_subject": "«Идея нового порядка передачи вахты»",
                }
            return {
                "ticket_example": "«Сократить возвраты по входящим запросам»",
                "ticket_titles_short": "инициатива «Сократить возвраты по входящим запросам», спор по приоритетам и риск дополнительной нагрузки на команду",
                "ticket_title_list": [
                    "инициатива «Сократить возвраты по входящим запросам»",
                    "спор по приоритетам",
                    "риск дополнительной нагрузки на команду",
                ],
                "employee_name": "Дарья",
                "workflow_label": "изменение порядка обработки запросов",
                "case_card_title": "№39012",
                "case_card_subject": "«Идея изменить порядок обработки входящих запросов»",
            }
        return {
            "ticket_example": "«Срочный запрос без следующего шага»",
            "ticket_titles_short": "срочный запрос без следующего шага, задача без владельца и инцидент без обновленного статуса",
            "ticket_title_list": [
                "срочный запрос без следующего шага",
                "задача без владельца",
                "инцидент без обновленного статуса",
            ],
            "employee_name": "Анна",
            "workflow_label": "текущая операционная работа команды",
            "case_card_title": "№24018",
            "case_card_subject": "«Срочный запрос без зафиксированного следующего шага»",
        }
