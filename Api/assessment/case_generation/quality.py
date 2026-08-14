from __future__ import annotations

import re
import zlib
from typing import Any

import psycopg
from psycopg.rows import dict_row

from Api.case_text_cleanup import cleanup_case_list, cleanup_case_text, join_case_list
from Api.config import settings

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


class CaseQualityMixin:
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

    def _normalize_stakeholder_phrase(self, text: str, *, grammatical_case: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        nominative = {
            "руководитель смены поддержки": "руководитель смены поддержки",
            "руководитель группы": "руководитель группы",
            "администратор зала": "администратор зала",
            "капитан": "капитан",
            "заказчик": "заказчик",
            "внешний клиент": "внешний клиент",
            "пользователь": "пользователь",
            "вторая линия ит-поддержки": "вторая линия ИТ-поддержки",
            "вторую линию ит-поддержки": "вторая линия ИТ-поддержки",
            "смежная линия": "смежная линия",
            "смежную линию": "смежная линия",
            "смежная команда": "смежная команда",
            "смежное подразделение": "смежное подразделение",
            "технолог": "технолог",
            "руководитель проекта": "руководитель проекта",
        }
        genitive = {
            "руководитель смены поддержки": "руководителя смены поддержки",
            "руководитель группы": "руководителя группы",
            "администратор зала": "администратора зала",
            "капитан": "капитана",
            "заказчик": "заказчика",
            "внешний клиент": "внешнего клиента",
            "пользователь": "пользователя",
            "вторая линия ит-поддержки": "второй линии ИТ-поддержки",
            "вторую линию ит-поддержки": "второй линии ИТ-поддержки",
            "смежная линия": "смежной линии",
            "смежную линию": "смежной линии",
            "смежная команда": "смежной команды",
            "смежное подразделение": "смежного подразделения",
            "технолог": "технолога",
            "руководитель проекта": "руководителя проекта",
        }
        dative = {
            "руководитель смены поддержки": "руководителю смены поддержки",
            "руководитель группы": "руководителю группы",
            "администратор зала": "администратору зала",
            "капитан": "капитану",
            "заказчик": "заказчику",
            "внешний клиент": "внешнему клиенту",
            "пользователь": "пользователю",
            "вторая линия ит-поддержки": "во вторую линию ИТ-поддержки",
            "вторую линию ит-поддержки": "во вторую линию ИТ-поддержки",
            "смежная линия": "смежной линии",
            "смежную линию": "смежной линии",
            "смежная команда": "смежной команде",
            "смежное подразделение": "смежному подразделению",
            "технолог": "технологу",
            "руководитель проекта": "руководителю проекта",
        }
        if grammatical_case == "genitive":
            exact = genitive
        elif grammatical_case == "dative":
            exact = dative
        else:
            exact = nominative
        lowered = normalized.lower()
        if lowered in exact:
            return exact[lowered]
        if " и " in normalized:
            first = normalized.split(" и ", 1)[0].strip()
            first_lowered = first.lower()
            if first_lowered in exact:
                return exact[first_lowered]
        if grammatical_case == "genitive":
            normalized = re.sub(r"\bсмежную\s+линию\b", "смежной линии", normalized, flags=re.IGNORECASE)
        return normalized

    def _select_primary_actor(self, text: str | None, *, grammatical_case: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        first = raw.split(",", 1)[0].strip()
        return self._normalize_stakeholder_phrase(first or raw, grammatical_case=grammatical_case)

    def _extract_named_primary_participant(self, text: str | None) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        first = re.split(r",|\s+и\s+", raw, maxsplit=1)[0].strip()
        return first

    def _select_escalation_target(self, primary: str | None, adjacent: str | None) -> str:
        adjacent_value = self._select_primary_actor(adjacent, grammatical_case="dative")
        if adjacent_value:
            return adjacent_value
        primary_value = self._select_primary_actor(primary, grammatical_case="dative")
        if primary_value:
            return primary_value
        return str(adjacent or primary or "").strip()

    def _normalize_access_source_phrase(self, text: str) -> str:
        normalized = str(text or "").strip()
        if not normalized:
            return ""
        replacements = {
            "финальная программа курса": "финальной программе курса",
            "программа курса": "программе курса",
            "бриф на обучение": "брифу на обучение",
            "карточка обучения": "карточке обучения",
            "карточка программы": "карточке программы",
            "карточка запуска программы": "карточке запуска программы",
            "дата старта в LMS/HRM": "дате старта в LMS/HRM",
            "комментарии заказчика": "комментариям заказчика",
            "комментарии внутреннего эксперта": "комментариям внутреннего эксперта",
            "комментарии руководителя подразделения": "комментариям руководителя подразделения",
            "анкеты обратной связи": "анкетам обратной связи",
            "комментарии участников": "комментариям участников",
            "история договоренностей": "истории договоренностей",
            "журнал задач по программе": "журналу задач по программе",
            "список участников": "списку участников",
            "календарь обучения": "календарю обучения",
            "график подразделения": "графику подразделения",
            "карточка заявки": "карточке заявки",
            "карточки заявок": "карточкам заявок",
            "карточек заявок": "карточкам заявок",
            "история комментариев": "истории комментариев",
            "историй комментариев": "истории комментариев",
            "статус в Service Desk": "статусу в Service Desk",
            "статуса в Service Desk": "статусу в Service Desk",
            "статусы в Service Desk": "статусам в Service Desk",
            "статусов в Service Desk": "статусам в Service Desk",
            "карточка задачи": "карточке задачи",
            "карточка обращения": "карточке обращения",
            "карточка задания": "карточке задания",
            "карточки задания": "карточке задания",
            "лист согласования": "листу согласования",
            "листа согласования": "листу согласования",
            "комплект конструкторской документации": "комплекту конструкторской документации",
            "комплекта конструкторской документации": "комплекту конструкторской документации",
            "комплект КД": "комплекту КД",
            "комплекта КД": "комплекту КД",
            "карточки обращения": "карточке обращения",
            "история коммуникации в CRM": "истории коммуникации в CRM",
            "истории коммуникации в CRM": "истории коммуникации в CRM",
            "внутренние комментарии команды": "внутренним комментариям команды",
            "внутренних комментариев команды": "внутренним комментариям команды",
            "журнал эскалаций": "журналу эскалаций",
            "журнала эскалаций": "журналу эскалаций",
            "судовой журнал": "судовому журналу",
            "POS-система": "POS-системе",
        }
        for source, target in replacements.items():
            normalized = re.sub(re.escape(source), target, normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bкарточка заявки, истории комментариев и статуса в Service Desk\b", "карточке заявки, истории комментариев и статусу в Service Desk", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bкарточкам заявок, истории комментариев и статусам в Service Desk\b", "карточкам заявок, истории комментариев и статусам в Service Desk", normalized, flags=re.IGNORECASE)
        return normalized

    def _normalize_channel_phrase(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        lowered = value.lower()
        mappings = (
            ("service desk", "в комментариях к заявке в Service Desk"),
            ("jira", "в комментариях к задаче в Jira"),
            ("судовом журнал", "в судовом журнале"),
            ("журнале вахты", "в журнале вахты"),
            ("pos", "в POS-системе"),
            ("лента заказов", "в ленте заказов"),
            ("журнал смены", "в журнале смены"),
            ("листе согласования", "в листе согласования"),
            ("plm", "в карточке задания в PLM"),
            ("рабочий чат", "в рабочем чате"),
            ("очередь заявок", "в очереди заявок"),
            ("очередь обращений", "в очереди обращений"),
        )
        for marker, rendered in mappings:
            if marker in lowered:
                return rendered
        first_part = value.split(",")[0].strip()
        if not first_part:
            return value
        if first_part.lower().startswith(("в ", "во ", "через ")):
            return first_part
        return f"через {first_part.lower()}"

    def _normalize_risk_phrase(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        normalized = value
        replacements = {
            "срыв сроков": "срыва сроков",
            "повторные доработки": "повторных доработок",
            "ошибки в процессе": "ошибок в процессе",
            "ошибки по заявке": "ошибок по заявке",
            "задержка следующего шага": "задержки следующего шага",
            "повторное обращение пользователя": "повторного обращения пользователя",
            "жалоба гостя": "жалобы гостя",
        }
        for source, target in replacements.items():
            normalized = re.sub(source, target, normalized, flags=re.IGNORECASE)
        return normalized

    def _normalize_deadline_phrase(self, text: str) -> str:
        clean = text.strip()
        lowered = clean.lower()
        mapping = {
            "до конца рабочего дня": "до конца рабочего дня",
            "к концу рабочего дня": "до конца рабочего дня",
            "в течение рабочего дня": "до конца рабочего дня",
            "до конца рабочей смены": "до конца рабочей смены",
            "до закрытия текущей смены": "до закрытия текущей смены",
            "до передачи партии на следующий этап": "до передачи партии на следующий этап",
            "до начала следующего этапа рейса или передачи вахты": "до начала следующего этапа рейса или передачи вахты",
            "к контрольной дате выпуска комплекта": "до контрольной даты выпуска комплекта",
            "в течение ближайших двух дней": "в течение ближайших двух рабочих дней",
            "в пределах sla по клиентскому обращению": "клиент ждет обновление до конца рабочего дня по SLA",
            "до согласованной даты запуска учебной программы": "до старта программы осталось 3 рабочих дня",
            "до согласованной даты запуска программы": "до старта программы осталось 3 рабочих дня",
        }
        if lowered in mapping:
            return mapping[lowered]
        if lowered.startswith("до "):
            return clean[3:].strip()
        if lowered.startswith("к "):
            return clean[2:].strip()
        return clean

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

    def _normalize_case_specificity(self, raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        result = dict(fallback)
        if not isinstance(raw, dict):
            return result
        for key in (
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
            "issue_summary",
            "data_sources",
            "error_examples",
            "team_contour",
            "behavior_issue",
            "deadline",
            "limits_short",
            "incident_type",
            "incident_impact",
            "involved_teams",
            "resource_profile",
            "metric_label",
            "metric_delta",
            "decision_theme",
            "audience_label",
            "strategic_scope",
            "dependencies",
            "business_criteria",
            "time_resource_limit",
            "participant_names",
            "stakeholder_named_list",
            "shift_name",
            "shift_duration",
            "work_items",
        ):
            value = self._sanitize_personalization_value(str(raw.get(key) or ""))
            if value:
                result[key] = value
        result["ticket_titles"] = self._normalize_string_list(raw.get("ticket_titles"), fallback=result.get("ticket_titles") or [])
        result["stage_names"] = self._normalize_string_list(raw.get("stage_names"), fallback=result.get("stage_names") or [])
        for key in (
            "_template_context",
            "_template_task",
            "_template_context_personalized",
            "_template_task_personalized",
            "_case_title",
        ):
            value = str(raw.get(key) or "").strip()
            if value:
                result[key] = value
        for key in ("_case_frame", "_used_case_signatures"):
            value = raw.get(key)
            if value:
                result[key] = value
        for key in ("domain_family", "domain_code"):
            value = str(raw.get(key) or "").strip()
            if value:
                result[key] = value
        return result

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

    def _join_case_items(self, items: list[str] | None) -> str:
        values = [self._sanitize_personalization_value(str(item)) for item in (items or []) if str(item).strip()]
        values = [item for item in values if item]
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]} и {values[1]}"
        return f"{', '.join(values[:-1])} и {values[-1]}"

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

    def _describe_process_gap(self, specificity: dict[str, Any]) -> str:
        family = self._infer_specificity_domain_family(specificity)
        workflow = str(specificity.get("workflow_label") or "текущий процесс")
        critical_step = str(specificity.get("critical_step") or "следующий шаг")
        source = str(specificity.get("source_of_truth") or "внутренние данные")
        if family == "horeca":
            return (
                "Сейчас спорные ситуации по гостям проходят через бар, администратора зала и журнал смены, "
                "но замечания по заказу и следующий шаг фиксируются не всегда последовательно."
            )
        if family == "maritime":
            return (
                "Сейчас ключевые действия по вахте и координации экипажа фиксируются через судовой журнал и передачу смены, "
                "но подтверждение результата и следующего маневра иногда остается неполным."
            )
        if family == "engineering":
            return (
                "Сейчас комплект документации проходит проверку, согласование замечаний и передачу в смежные подразделения, "
                "но на стыке этапов часть договоренностей и подтверждений теряется."
            )
        if family == "business_analysis":
            return (
                "Сейчас задача проходит через уточнение требований, согласование с заказчиком и передачу в разработку, "
                "но единое понимание результата не всегда фиксируется до следующего этапа."
            )
        if family == "it_support":
            return (
                "Сейчас обращение проходит через регистрацию, диагностику, обновление статуса и подтверждение результата с пользователем, "
                "но на одном из шагов информация о фактическом результате или следующем действии теряется."
            )
        return (
            f"Сейчас работа идет по процессу «{workflow}» с опорой на {source}, "
            f"но критичный шаг «{critical_step}» фиксируется не всегда последовательно."
        )

    def _describe_current_idea(self, specificity: dict[str, Any]) -> str:
        family = self._infer_specificity_domain_family(specificity)
        workflow = str(specificity.get("workflow_label") or "текущий процесс")
        idea = str(specificity.get("idea_label") or f"улучшение процесса «{workflow}»")
        if family == "horeca":
            return (
                f"Сейчас обсуждается идея «{idea}»: перед закрытием спорной ситуации по гостю команда будет фиксировать замечание, "
                "согласованный следующий шаг и ответственную сторону прямо в журнале смены."
            )
        if family == "maritime":
            return (
                f"Сейчас обсуждается идея «{idea}»: перед передачей вахты следующий маневр, статус выполнения и ответственный шаг "
                "должны подтверждаться в журнале и устно между вахтами."
            )
        if family == "engineering":
            return (
                f"Сейчас обсуждается идея «{idea}»: до передачи комплекта документации дальше команда будет отдельно фиксировать "
                "закрытие замечаний и подтверждение готовности следующего этапа."
            )
        if family == "business_analysis":
            return (
                f"Сейчас обсуждается идея «{idea}»: перед передачей задачи в разработку аналитик будет фиксировать согласованные требования, "
                "критерии готовности и следующий шаг в одном месте."
            )
        if family == "it_support":
            return (
                f"Сейчас обсуждается идея «{idea}»: перед закрытием обращения специалист будет отдельно подтверждать фактический результат, "
                "следующее действие и обновление пользователя."
            )
        return f"Сейчас обсуждается идея «{idea}», которая должна сделать процесс более предсказуемым и управляемым."

    def _default_specific_case_frame(self, specificity: dict[str, Any]) -> dict[str, str]:
        family = self._infer_specificity_domain_family(specificity)
        critical_step = cleanup_case_text(str(specificity.get("critical_step") or "следующий шаг"))
        defaults: dict[str, dict[str, str]] = {
            "learning_and_development": {
                "stakeholder": "руководитель подразделения",
                "work_object": "программа обучения",
                "constraint": "нельзя подтверждать запуск обучения без согласованной программы, состава участников и следующего шага",
                "risk": "срыв сроков запуска обучения и повторный цикл согласования",
                "expected_step": "согласовать программу, зафиксировать владельца следующего шага и подтвердить реалистичный срок",
            },
            "client_service": {
                "stakeholder": "клиент",
                "work_object": "обращение клиента",
                "constraint": "нельзя обещать клиенту срок или решение без подтверждения со стороны команды и фиксации обновления в CRM",
                "risk": "повторная жалоба клиента и потеря контроля над обращением",
                "expected_step": "назначить владельца обращения, подтвердить следующий шаг и дать клиенту реалистичное обновление",
            },
            "engineering": {
                "stakeholder": "смежное подразделение",
                "work_object": "комплект конструкторской документации",
                "constraint": "нельзя передавать комплект дальше без закрытия критичных замечаний и подтверждения актуальной версии",
                "risk": "выпуск устаревшей версии документации и возврат на доработку",
                "expected_step": "сверить замечания, зафиксировать корректную версию и подтвердить готовность к передаче",
            },
            "it_support": {
                "stakeholder": "пользователь",
                "work_object": "обращение в поддержку",
                "constraint": "нельзя закрывать обращение без подтвержденного результата и зафиксированного следующего шага",
                "risk": "повторное обращение и эскалация инцидента",
                "expected_step": "проверить фактический статус решения, подтвердить следующий шаг и обновить пользователя",
            },
        }
        frame = dict(defaults.get(family, {
            "stakeholder": "заинтересованная сторона",
            "work_object": "рабочий вопрос",
            "constraint": f"нельзя передавать результат дальше, пока не закрыт шаг «{critical_step}»",
            "risk": "ошибка на следующем этапе и повторная переделка",
            "expected_step": f"закрыть шаг «{critical_step}», подтвердить владельца и зафиксировать следующий шаг",
        }))
        if critical_step and critical_step not in frame["expected_step"]:
            frame["expected_step"] = f"{frame['expected_step']} по шагу «{critical_step}»"
        return frame

    def _normalize_incident_title(self, text: str) -> str:
        title = cleanup_case_text(str(text or "")).replace("**", "").strip()
        title = re.sub(r"^\s*ситуация:\s*", "", title, flags=re.IGNORECASE).strip()
        title = title.rstrip(".")
        if title == "Рабочая ситуация требует решения":
            return ""
        left_quotes = title.count("«")
        right_quotes = title.count("»")
        if left_quotes > right_quotes:
            title = f"{title}{'»' * (left_quotes - right_quotes)}"
        title = title.strip()
        if title[:1].islower():
            title = title[:1].upper() + title[1:]
        return title

    def _incident_title_from_case_title(self, case_title: str) -> str:
        title = self._normalize_incident_title(case_title)
        if not title:
            return ""
        replacements = (
            (r"\bбез критериев и приоритетов\b", ""),
            (r"\bпри конкретной метрике и ограничении\b", ""),
            (r"\bпри высоких рисках и зависимости от смежников\b", ""),
            (r"\bпри новой инициативе, риске выгорания и зависимости от смежников\b", ""),
            (r"\bкоторый подрывает договор[её]нности и усиливает сопротивление\b", ""),
            (r"\bи выбор режима внедрения\b", ""),
            (r"\bуниверсальный кейс на\b", ""),
            (r"\bперераспределение работы команды\b", "Перераспределение работы"),
            (r"\bразговор с ключевым стейкхолдером\b", "Разговор с ключевым участником"),
            (r"\bзапрос на результат\b", "Запрос на результат"),
            (r"\bоценка идеи\b", "Оценка идеи"),
            (r"\bгенерацию идей улучшения\b", "Генерация идей улучшения"),
        )
        for pattern, replacement in replacements:
            title = re.sub(pattern, replacement, title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\s{2,}", " ", title).strip(" -,:;.")
        if "«" in title and "»" in title:
            quoted = re.search(r"«([^»]+)»", title)
            if quoted and title.lower().startswith("запрос на результат"):
                return f"Запрос на результат «{quoted.group(1).strip()}»"
        return self._normalize_incident_title(title)

    def _compose_incident_title_from_template_and_specificity(
        self,
        *,
        case_type_code: str | None,
        case_title: str,
        specificity: dict[str, Any] | None,
        case_frame: dict[str, Any] | None,
    ) -> str:
        type_code = str(case_type_code or "").upper()
        template_title = self._incident_title_from_case_title(case_title)
        frame = dict(case_frame or {})
        values = dict(specificity or {})

        problem = self._normalize_incident_title(str(frame.get("problem_event") or ""))
        issue = self._normalize_incident_title(str(values.get("bottleneck") or ""))
        idea = cleanup_case_text(str(values.get("idea_label") or "")).strip(" .")
        request_type = self._normalize_incident_title(str(values.get("request_type") or ""))
        critical_step = cleanup_case_text(str(values.get("critical_step") or frame.get("expected_step") or "")).strip(" .")

        def shorten_detail(text: str, *, max_words: int = 7) -> str:
            raw = cleanup_case_text(text).strip(" .")
            if not raw:
                return ""
            raw = re.sub(r"^\s*(клиент|обращение|эскалированное обращение)\s+", "", raw, flags=re.IGNORECASE).strip()
            words = raw.split()
            if len(words) > max_words:
                raw = " ".join(words[:max_words]).strip()
            raw = re.sub(r"\b(и|или|а|но)$", "", raw, flags=re.IGNORECASE).strip(" ,")
            return raw

        def normalize_title_quotes(text: str) -> str:
            value = cleanup_case_text(text).strip(" .")
            if not value:
                return ""
            if "«" in value and "»" in value:
                inner = re.search(r"«([^»]+)»", value)
                if inner:
                    value = inner.group(1).strip()
            return value

        if type_code == "F02":
            if "«" in case_title and "»" in case_title:
                quoted = re.search(r"«([^»]+)»", case_title)
                if quoted:
                    return self._normalize_incident_title(f"Запрос «{quoted.group(1).strip()}» без критериев")
            if request_type:
                return self._normalize_incident_title(f"Неясный запрос: {request_type}")
            if template_title:
                return template_title

        if type_code == "F03":
            if template_title and problem:
                short_problem = shorten_detail(problem)
                if "без явного владельца" in short_problem.lower():
                    short_problem = "обращение без владельца"
                if short_problem and short_problem.lower() not in template_title.lower():
                    return self._normalize_incident_title(f"{template_title}: {short_problem}")
            if template_title:
                return template_title

        if type_code == "F05":
            if template_title and problem:
                short_problem = shorten_detail(problem)
                if "без явного владельца" in short_problem.lower():
                    short_problem = "обращение без владельца"
                if short_problem:
                    return self._normalize_incident_title(f"{template_title}: {short_problem}")
            if template_title:
                return template_title

        if type_code == "F09":
            if template_title and (problem or issue):
                detail = shorten_detail(problem or issue, max_words=8)
                if "разные версии статуса" in detail.lower():
                    detail = "разные версии статуса"
                return self._normalize_incident_title(f"{template_title}: {detail.lower()}")
            if template_title:
                return template_title

        if type_code == "F10":
            if idea:
                short_idea = normalize_title_quotes(idea)
                short_idea = re.sub(r"\s+в процессе\s+.+$", "", short_idea, flags=re.IGNORECASE).strip()
                if "чек-лист" in short_idea.lower():
                    short_idea = "чек-лист следующего шага"
                return self._normalize_incident_title(f"Оценка идеи: {short_idea}")
            if template_title and problem:
                return self._normalize_incident_title(f"{template_title}: {shorten_detail(problem).lower()}")
            if template_title:
                return template_title

        if type_code == "F11":
            if template_title and critical_step:
                return self._normalize_incident_title(f"{template_title}: {critical_step.lower()}")
            if template_title:
                return template_title

        if template_title and problem and problem.lower() not in template_title.lower():
            return self._normalize_incident_title(f"{template_title}: {problem.lower()}")
        return template_title

    def _normalize_case_frame_source(self, text: str) -> str:
        value = cleanup_case_text(str(text or "")).strip()
        if not value:
            return ""
        value = self._normalize_access_source_phrase(value)
        replacements = {
            "карточка заявки, история комментариев и статус в Service Desk": "карточке заявки, истории комментариев и статусу в Service Desk",
            "карточка обращения, история коммуникации в CRM и внутренние комментарии команды": "карточке обращения, истории коммуникации в CRM и внутренним комментариям команды",
            "карточка задания, лист согласования и комплект конструкторской документации": "карточке задания, листу согласования и комплекту конструкторской документации",
            "бриф на обучение, ТЗ подрядчику, программа курса и комментарии внутреннего эксперта": "брифу на обучение, ТЗ подрядчику, программе курса и комментариям внутреннего эксперта",
            "карточка обучения, комментарии заказчика и история договоренностей по следующему шагу": "карточке обучения, комментариям заказчика и истории договоренностей по следующему шагу",
        }
        lowered = value.lower()
        for source, target in replacements.items():
            if lowered == source.lower():
                return target
        return value

    def _normalize_case_frame_focus(self, text: str) -> str:
        value = cleanup_case_text(str(text or "")).strip()
        if not value:
            return ""
        value = re.sub(r"^\s*рабочий объект\s*$", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"\s+и\s+спецификация\s+и\s+", ", спецификация и ", value, flags=re.IGNORECASE)
        return value

    def _normalize_case_frame_problem(self, text: str, *, fallback: str) -> str:
        value = cleanup_case_text(str(text or "")).strip()
        if not value:
            value = cleanup_case_text(str(fallback or "")).strip()
        value = re.sub(r"^\s*ключевая проблема сейчас такая:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^\s*ситуация такая:\s*", "", value, flags=re.IGNORECASE)
        replacements = {
            "обращение закрывают или передают дальше раньше, чем подтвержден фактический результат, следующий шаг и обновление пользователя": "обращение закрывают или передают дальше до подтверждения фактического результата",
            "замечания по документации и готовность следующего этапа подтверждаются не в одном контуре": "замечания по документации закрыты не полностью, а готовность следующего этапа не подтверждена",
        }
        for source, target in replacements.items():
            value = re.sub(re.escape(source), target, value, flags=re.IGNORECASE)
        return value.strip(" .")

    def _shorten_state_for_narrative(self, text: str) -> str:
        value = cleanup_case_text(str(text or "")).strip()
        if not value:
            return ""
        value = re.sub(r"(\d+),\s+(\d+)", r"\1,\2", value)
        value = re.sub(r"\s+(За последние\s+\d+[^.]*\.)", "", value, count=1, flags=re.IGNORECASE)
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]
        if sentences:
            value = sentences[0]
        value = re.sub(r"\s{2,}", " ", value).strip()
        if value and value[-1] not in ".!?":
            value += "."
        return value

    def _strip_metrics_from_fact(self, text: str) -> str:
        value = cleanup_case_text(str(text or "")).strip()
        if not value:
            return ""
        value = re.sub(r"\s+За\s+\d+[^.]*\.\s*$", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+За\s+последн(?:ие|юю)\s+[^.]*\.\s*$", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s{2,}", " ", value).strip(" ,")
        if value and value[-1] not in ".!?":
            value += "."
        return value

    def _select_primary_stakeholder(self, participants: list[str], fallback: str) -> str:
        cleaned = [cleanup_case_text(str(item or "")).strip() for item in participants if cleanup_case_text(str(item or "")).strip()]
        if not cleaned:
            return self._select_primary_actor(str(fallback or ""), grammatical_case="nominative")
        preferred_markers = (
            "клиент",
            "заказчик",
            "пользователь",
            "руководитель подразделения",
            "смежное подразделение",
            "подрядчик",
            "руководитель смены",
        )
        for marker in preferred_markers:
            for item in cleaned:
                if marker in item.lower():
                    return self._select_primary_actor(item, grammatical_case="nominative")
        return self._select_primary_actor(cleaned[0], grammatical_case="nominative")

    def _build_risk_sentence(self, risk: str, *, prefix: str | None = None) -> str:
        clean = cleanup_case_text(str(risk or "")).strip().rstrip(".")
        if not clean:
            return ""
        if prefix:
            return f"{prefix} главный риск — {clean}."
        return f"Главный риск — {clean}."

    def _build_specificity_case_frame(self, specificity: dict[str, Any]) -> dict[str, str]:
        semantic = self._template_semantic_fragments(specificity)
        fallback = self._default_specific_case_frame(specificity)
        explicit_case_frame = dict(specificity.get("_case_frame") or {})
        participant_raw: list[str] = []
        for value in (
            explicit_case_frame.get("key_participant"),
            explicit_case_frame.get("participants"),
            specificity.get("primary_stakeholder"),
            specificity.get("stakeholder_named_list"),
            specificity.get("participant_names"),
            specificity.get("adjacent_team"),
        ):
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    participant_raw.extend(re.split(r"[,;\n]+", str(item or "")))
            else:
                participant_raw.extend(re.split(r"[,;\n]+", str(value or "")))
        participants = cleanup_case_list(participant_raw, limit=3)
        work_item_raw = [
            part
            for value in [
                explicit_case_frame.get("artifacts"),
                explicit_case_frame.get("tasks"),
                explicit_case_frame.get("work_object"),
                specificity.get("work_items"),
            ]
            for part in re.split(r"[,;\n]+", str(value or ""))
        ]
        work_items = cleanup_case_list(work_item_raw, limit=3)
        current_state = self._humanize_current_state(
            str(
                specificity.get("current_state")
                or (explicit_case_frame.get("known_facts") or [""])[0]
                or ""
            )
        )
        current_state_inline = cleanup_case_text(
            self._shorten_state_for_narrative(
                re.sub(r"^\s*сейчас\s+", "", current_state.strip(), flags=re.IGNORECASE).rstrip(".!? ")
            ).rstrip(".!? ")
        )
        bottleneck = cleanup_case_text(
            str(
                specificity.get("bottleneck")
                or explicit_case_frame.get("problem_event")
                or ""
            )
        )
        problem_event = self._normalize_case_frame_problem(
            str(explicit_case_frame.get("problem_event") or semantic.get("mismatch") or bottleneck or current_state_inline),
            fallback=(work_items[0] if work_items else fallback["work_object"]),
        )
        incident_title = self._normalize_incident_title(str(explicit_case_frame.get("incident_title") or ""))
        if not incident_title:
            fallback_titles = cleanup_case_list(specificity.get("ticket_titles") or [], limit=1)
            request_type = cleanup_case_text(str(specificity.get("request_type") or "")).rstrip(".")
            if fallback_titles:
                incident_title = self._normalize_incident_title(fallback_titles[0])
            elif request_type:
                incident_title = self._normalize_incident_title(request_type)
            elif problem_event:
                incident_title = self._normalize_incident_title(problem_event)
        work_object = cleanup_case_text(
            str(explicit_case_frame.get("work_object") or (work_items[0] if work_items else fallback["work_object"]))
        )
        source_of_truth = self._normalize_case_frame_source(
            str(explicit_case_frame.get("source_of_truth") or specificity.get("source_of_truth") or "")
        )
        rendered_work_items = self._normalize_case_frame_focus(
            join_case_list(explicit_case_frame.get("artifacts") or explicit_case_frame.get("tasks") or work_items, limit=3)
            or work_object
        )
        risk = cleanup_case_text(
            str(explicit_case_frame.get("risk") or semantic.get("risk") or fallback["risk"])
        )
        constraint = cleanup_case_text(
            str(explicit_case_frame.get("constraint") or fallback["constraint"])
        )
        return {
            "workflow": self._format_case_scope(
                str(explicit_case_frame.get("process") or specificity.get("workflow_label") or "текущий процесс")
            ),
            "impact": cleanup_case_text(
                str(explicit_case_frame.get("impact") or specificity.get("business_impact") or "сроки и качество результата")
            ),
            "stakeholder": self._select_primary_stakeholder(
                participants,
                str(explicit_case_frame.get("key_participant") or fallback["stakeholder"]),
            ),
            "participants": join_case_list(explicit_case_frame.get("participants") or participants, limit=3) or fallback["stakeholder"],
            "work_object": work_object,
            "work_items": rendered_work_items or fallback["work_object"],
            "problem_event": problem_event or fallback["work_object"],
            "current_state": current_state,
            "current_state_inline": current_state_inline,
            "constraint": constraint,
            "risk": risk,
            "expected_step": cleanup_case_text(str(explicit_case_frame.get("expected_step") or fallback["expected_step"])),
            "critical_step": cleanup_case_text(str(specificity.get("critical_step") or explicit_case_frame.get("expected_step") or "следующий шаг")),
            "source_of_truth": source_of_truth,
            "bottleneck": bottleneck,
            "incident_title": incident_title,
            "situation_code": cleanup_case_text(str(explicit_case_frame.get("situation_code") or "")).strip(),
        }

    def _compose_learning_and_development_scene_context(
        self,
        specificity: dict[str, Any],
        *,
        case_type_code: str | None,
    ) -> str:
        frame = self._build_specificity_case_frame(specificity)
        incident_title = cleanup_case_text(str(frame.get("incident_title") or "")).rstrip(".")
        problem_event = cleanup_case_text(str(frame.get("problem_event") or ""))
        current_state = cleanup_case_text(str(frame.get("current_state") or ""))
        source_of_truth = cleanup_case_text(str(frame.get("source_of_truth") or ""))
        constraint = cleanup_case_text(str(frame.get("constraint") or ""))
        risk = cleanup_case_text(str(frame.get("risk") or ""))
        expected_step = cleanup_case_text(str(frame.get("expected_step") or ""))
        work_items = cleanup_case_text(str(frame.get("work_items") or ""))
        stakeholder = cleanup_case_text(str(frame.get("stakeholder") or "руководитель подразделения"))
        type_code = str(case_type_code or "").upper()

        intro = f"Сейчас в фокусе ситуация «{incident_title or problem_event}»."
        if type_code == "F11":
            text = (
                f"{intro} Перед следующим этапом обнаружилось несоответствие: {problem_event}. "
                f"{current_state} "
                f"Проверить детали можно по {source_of_truth}. "
                f"{self._build_risk_sentence(risk, prefix='Если передать результат дальше без проверки,')} "
                f"При этом {constraint}."
            )
            if expected_step:
                text += f" Сначала нужно {expected_step}."
            return text
        if type_code == "F08":
            text = (
                f"{intro} Сейчас нужно быстро понять, что делать в первую очередь, потому что {problem_event}. "
                f"{current_state} "
                f"{self._build_risk_sentence(risk, prefix='Если ошибиться с первым выбором,')} "
                f"В фокусе сейчас {work_items}. "
                f"При этом {constraint}."
            )
            return text
        if type_code == "F05":
            text = (
                f"{intro} Команде нужно распределить работу так, чтобы удержать ситуацию под контролем. "
                f"{current_state} "
                f"Ключевой узел сейчас — {problem_event}. "
                f"В работе уже участвуют {stakeholder}, а в фокусе находятся {work_items}. "
                f"{self._build_risk_sentence(risk, prefix='Если координация просядет,')} "
                f"При этом {constraint}."
            )
            return text
        if type_code == "F10":
            idea = cleanup_case_text(str(specificity.get("idea_label") or "улучшение участка"))
            idea_description = cleanup_case_text(str(specificity.get("idea_description") or "изменить локальный порядок работы на этом шаге"))
            text = (
                f"{intro} Появилась идея «{idea}»: {idea_description}. "
                f"Основание для идеи такое: {problem_event}. "
                f"{current_state} "
                f"Потенциально это может помочь, потому что сейчас главный риск — {cleanup_case_text(str(risk or '')).strip().rstrip('.')}. " if risk else ""
                f"Но запускать изменение нужно с учетом ограничения: {constraint}."
            )
            return text
        if type_code == "F09":
            text = (
                f"{intro} На этом участке регулярно повторяется одна и та же проблема: {problem_event}. "
                f"{current_state} "
                f"{self._build_risk_sentence(risk, prefix='Сейчас')} "
                f"В фокусе сейчас {work_items}. "
                f"Нужно предложить улучшение именно для этого узкого места, не выходя за ограничение: {constraint}."
            )
            return text
        if type_code in {"F03", "F12"}:
            text = (
                f"{intro} В повторяющихся сбоях вокруг этой ситуации уже виден устойчивый паттерн: {problem_event}. "
                f"{current_state} "
                f"{self._build_risk_sentence(risk, prefix='Если ничего не менять,')} "
                f"При этом {constraint}."
            )
            return text
        if type_code == "F02":
            text = (
                f"{intro} Сейчас запрос выглядит неоднозначно именно вокруг этого эпизода: {problem_event}. "
                f"{current_state} "
                f"Без уточнения легко получить возврат или неверный следующий шаг. "
                f"Проверять детали придется по {source_of_truth}."
            )
            return text
        return ""

    def _compose_planning_case_context(self, specificity: dict[str, Any]) -> str:
        frame = self._build_specificity_case_frame(specificity)
        return (
            f"По процессу {frame['workflow']} нужно быстро распределить работу вокруг ситуации «{frame['incident_title'] or frame['work_object']}». "
            f"{frame['current_state_inline'] or frame['problem_event']} "
            f"Сейчас в фокусе {frame['work_items']}. "
            f"Если не определить владельцев, порядок действий и контрольные точки, последствия будут такими: {frame['risk']}. "
            f"При этом {frame['constraint']}. "
            f"Следующий шаг, который должен удержать ситуацию под контролем: {frame['expected_step']}."
        )

    def _compose_priority_case_context(self, specificity: dict[str, Any]) -> str:
        frame = self._build_specificity_case_frame(specificity)
        return (
            f"По процессу {frame['workflow']} нужно быстро понять, что делать в первую очередь. "
            f"Ключевая проблема сейчас такая: {frame['problem_event']}. "
            f"{frame['current_state_inline'] or ''} "
            f"Сейчас конкурируют такие задачи: {frame['work_items']}. "
            f"Если ошибиться с первым выбором, последствия будут такими: {frame['risk']}. "
            f"При этом {frame['constraint']}."
        )

    def _format_case_scope(self, label: str) -> str:
        value = str(label or "").strip()
        if not value:
            return ""
        if value.startswith("**") and value.endswith("**"):
            return value
        return f"**{value}**"

    def _compose_improvement_case_context(self, specificity: dict[str, Any]) -> str:
        frame = self._build_specificity_case_frame(specificity)
        idea = str(specificity.get("idea_label") or "")
        current_state = frame["current_state"] or self._describe_process_gap(specificity)
        variant = self._diversity_variant(
            case_type_code="F09",
            case_title=str(specificity.get("_case_title") or ""),
            specificity=specificity,
            variants=3,
        )
        if current_state and current_state[-1] not in ".!?":
            current_state += "."
        current_state_inline = re.sub(r"^\s*сейчас\s+", "", current_state.strip(), flags=re.IGNORECASE)
        bottleneck = str(specificity.get("bottleneck") or "").strip()
        horeca_markers = self._domain_family_markers().get("horeca", ())
        horeca_source = " ".join(
            [
                frame["workflow"],
                str(specificity.get("system_name") or ""),
                str(specificity.get("source_of_truth") or ""),
                self._join_case_items((specificity.get("ticket_titles") or [])[:3]),
            ]
        ).lower()
        if any(marker in horeca_source for marker in horeca_markers):
            sentence = (
                "В смене бара регулярно повторяются одни и те же сбои: замечания по заказу фиксируются не полностью, "
                "а спорные ситуации по гостям закрываются раньше, чем команда договорится о следующем шаге. "
                f"Из-за этого страдают {frame['impact']}, а сотрудникам приходится тратить время на повторные разборы и возвраты к уже закрытым вопросам. "
                f"Сейчас проблема выглядит так: {current_state_inline} "
                "Нужно предложить улучшение, которое поможет сделать работу смены устойчивее."
            )
            if bottleneck:
                sentence += f" Основная проблема сейчас в том, что {bottleneck}."
            if idea:
                sentence += f" Например, можно обсудить идею «{idea}»."
            return sentence
        if variant == 1:
            sentence = (
                f"В процессе {frame['workflow']} команда снова и снова возвращается к одним и тем же вопросам вокруг {frame['work_object']}, хотя формально работа уже сдвигается дальше. "
                f"{current_state} "
                f"Из-за этого страдают {frame['impact']}, а время уходит не на движение вперед, а на повторные уточнения. "
                "Нужно предложить улучшение, которое уберет это узкое место."
            )
        elif variant == 2:
            sentence = (
                f"Сейчас в процессе {frame['workflow']} есть повторяющийся сбой на стыке шагов: часть работы по {frame['work_object']} считается выполненной, но команде все равно приходится к ней возвращаться. "
                f"{current_state} "
                f"Это уже влияет на {frame['impact']} и делает процесс менее предсказуемым. "
                "Нужно предложить улучшение, которое сделает этот рабочий контур устойчивее."
            )
        else:
            sentence = (
                f"В процессе {frame['workflow']} регулярно возникают возвраты, повторные согласования или лишние доработки вокруг {frame['work_object']}. "
                f"{current_state} "
                f"Из-за этого страдают {frame['impact']}, а команде приходится тратить больше времени на повторную работу. "
                "Нужно предложить улучшение, которое поможет сделать процесс устойчивее."
            )
        if bottleneck:
            sentence += f" Основная проблема сейчас в том, что {bottleneck}."
        if idea:
            sentence += f" Например, можно обсудить идею «{idea}»."
        sentence += f" При этом {frame['constraint']}."
        return sentence

    def _compose_idea_evaluation_case_context(self, specificity: dict[str, Any]) -> str:
        frame = self._build_specificity_case_frame(specificity)
        workflow = frame["workflow"]
        raw_workflow = str(specificity.get("workflow_label") or "текущему процессу")
        idea = str(specificity.get("idea_label") or f"улучшение процесса «{raw_workflow}»")
        idea_title = self._format_case_scope(idea)
        current_state = frame["current_state"] or self._describe_process_gap(specificity)
        variant = self._diversity_variant(
            case_type_code="F10",
            case_title=str(specificity.get("_case_title") or ""),
            specificity=specificity,
            variants=3,
        )
        if current_state and current_state[-1] not in ".!?":
            current_state += "."
        current_state_inline = re.sub(r"^\s*сейчас\s+", "", current_state.strip(), flags=re.IGNORECASE)
        bottleneck = str(specificity.get("bottleneck") or "").strip()
        idea_description = str(specificity.get("idea_description") or self._describe_current_idea(specificity))
        if idea_description and idea_description[-1] not in ".!?":
            idea_description += "."
        horeca_markers = self._domain_family_markers().get("horeca", ())
        horeca_source = " ".join(
            [
                workflow,
                str(specificity.get("system_name") or ""),
                str(specificity.get("source_of_truth") or ""),
                self._join_case_items((specificity.get("ticket_titles") or [])[:3]),
            ]
        ).lower()
        if any(marker in horeca_source for marker in horeca_markers):
            return (
                f"Появилась идея {idea_title}: изменить порядок работы смены по спорным ситуациям с гостями, "
                "чтобы замечания по заказу и следующий шаг фиксировались до закрытия вопроса. "
                f"Сейчас ситуация выглядит так: {current_state_inline} "
                f"Это может улучшить {frame['impact']}, но пока неясно, не замедлит ли это работу бара в пиковые часы. "
                + (f" Ключевой риск в том, что {bottleneck}." if bottleneck else "")
                + " "
                f"{idea_description}"
            )
        if variant == 1:
            opening = f"Появилась идея {idea_title}. Суть идеи такая: {idea_description}"
        elif variant == 2:
            opening = f"Команда обсуждает идею {idea_title} в процессе {frame['workflow']}. Суть идеи такая: {idea_description}"
        else:
            opening = f"Появилась идея {idea_title}. Суть идеи такая: {idea_description}"
        return (
            f"{opening} "
            f"{current_state} "
            f"Потенциальный эффект понятен, потому что это может улучшить {frame['impact']}, но пока неясно, стоит ли запускать изменение сразу и как сделать это безопасно. "
            + (f" Основная проблема сейчас такая: {bottleneck}." if bottleneck else "")
            + f" Важно учесть, что {frame['constraint']}."
        )

    def _compose_development_conversation_case_context(self, specificity: dict[str, Any]) -> str:
        frame = self._build_specificity_case_frame(specificity)
        variant = self._diversity_variant(
            case_type_code="F12",
            case_title=str(specificity.get("_case_title") or ""),
            specificity=specificity,
            variants=3,
        )
        horeca_markers = self._domain_family_markers().get("horeca", ())
        horeca_source = " ".join(
            [
                frame["workflow"],
                str(specificity.get("system_name") or ""),
                str(specificity.get("source_of_truth") or ""),
                self._join_case_items((specificity.get("ticket_titles") or [])[:3]),
            ]
        ).lower()
        if any(marker in horeca_source for marker in horeca_markers):
            return (
                "В работе сотрудника по смене бара повторяется одна и та же проблема: спорные ситуации по гостям закрываются раньше, "
                "чем замечания по заказу, результат для гостя и следующий шаг по смене фиксируются полностью. "
                f"Это уже влияет на {impact} и создает повторные разборы с администратором зала. "
                "Вам нужно провести разговор с сотрудником, чтобы обозначить проблему, договориться о более устойчивом порядке фиксации результата и снизить риск повторения таких ситуаций."
            )
        if variant == 1:
            sentence = (
                f"В работе сотрудника по процессу {frame['workflow']} повторяется один и тот же сбой вокруг {frame['work_object']}: критичный шаг «{frame['critical_step']}» закрывается формально, но не доводится до устойчивого результата. "
            )
        elif variant == 2:
            sentence = (
                f"На одном и том же участке процесса {frame['workflow']} у сотрудника снова возникает похожая проблема по {frame['work_object']}: шаг «{frame['critical_step']}» либо не фиксируется вовремя, либо передается дальше слишком рано. "
            )
        else:
            sentence = (
                f"В работе сотрудника по процессу {frame['workflow']} повторяется одна и та же проблема вокруг {frame['work_object']}: критичный шаг «{frame['critical_step']}» не доводится до конца или фиксируется слишком поздно. "
            )
        if frame["current_state_inline"]:
            sentence += f"Сейчас это выглядит так: {frame['current_state_inline']}. "
        if frame["bottleneck"]:
            sentence += f"Основная проблема в том, что {frame['bottleneck']}. "
        sentence += f"Это уже влияет на {frame['impact']} и создает повторные возвраты. "
        sentence += f"При этом {frame['constraint']}."
        sentence += " Вам нужно провести разговор с сотрудником, чтобы обозначить проблему, договориться о более устойчивом порядке работы и снизить риск повторения этого паттерна."
        return sentence

    def _diversity_variant(
        self,
        *,
        case_type_code: str,
        case_title: str,
        specificity: dict[str, Any],
        variants: int,
    ) -> int:
        seed = self._build_case_diversity_seed(
            case_type_code=case_type_code,
            case_title=case_title,
            specificity=specificity,
        )
        if variants <= 1:
            return 0
        return seed % variants

    def _build_case_diversity_seed(
        self,
        *,
        case_type_code: str,
        case_title: str,
        specificity: dict[str, Any],
    ) -> int:
        parts = [
            str(case_type_code or "").upper(),
            str(case_title or ""),
            str(specificity.get("_template_context") or ""),
            str(specificity.get("_template_task") or ""),
            str(specificity.get("domain_family") or specificity.get("domain_code") or ""),
            str(specificity.get("workflow_label") or ""),
            str(specificity.get("critical_step") or ""),
            str(specificity.get("request_type") or ""),
            str(specificity.get("idea_label") or ""),
            str(specificity.get("primary_stakeholder") or ""),
            str(specificity.get("stakeholder_named_list") or ""),
            str(specificity.get("participant_names") or ""),
            str(specificity.get("shift_name") or ""),
            str(specificity.get("work_items") or ""),
            self._join_case_items((specificity.get("ticket_titles") or [])[:3]),
        ]
        raw = "||".join(parts).encode("utf-8", errors="ignore")
        return zlib.crc32(raw) & 0xFFFFFFFF

    def _template_source_text(self, specificity: dict[str, Any]) -> str:
        return " ".join(
            part.strip()
            for part in (
                str(specificity.get("_template_context_personalized") or ""),
                str(specificity.get("_template_task_personalized") or ""),
                str(specificity.get("_template_context") or ""),
                str(specificity.get("_template_task") or ""),
            )
            if str(part or "").strip()
        ).strip()

    def _extract_template_quote(self, text: str) -> str:
        source = str(text or "")
        match = re.search(r"[«\"]([^»\"]{12,})[»\"]", source)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_template_sentence(self, text: str, markers: tuple[str, ...]) -> str:
        source = str(text or "").strip()
        if not source:
            return ""
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", source) if part.strip()]
        for sentence in sentences:
            lowered = sentence.lower()
            if any(marker.lower() in lowered for marker in markers):
                return sentence
        return ""

    def _template_semantic_fragments(self, specificity: dict[str, Any]) -> dict[str, str]:
        source = self._template_source_text(specificity)
        return {
            "quote": self._extract_template_quote(source),
            "ambiguity": self._extract_template_sentence(
                source,
                ("неясно", "не определено", "нет ясного", "не хватает", "непонятно"),
            ),
            "expectation": self._extract_template_sentence(
                source,
                ("от вас ждут", "сейчас важно", "нужно быстро", "прежде чем", "до того, как"),
            ),
            "risk": self._extract_template_sentence(
                source,
                ("если начать", "если запустить", "рискует", "потерять время", "усилить конфликт"),
            ),
            "mismatch": self._extract_template_sentence(
                source,
                ("не совпадают", "не подтвержден", "нельзя передавать", "отклонение", "контроля качества"),
            ),
        }

    def _strip_template_role_prefix(self, text: str) -> str:
        source = str(text or "").strip()
        if not source:
            return ""
        anchors = (
            "В последние недели",
            "В последнее время",
            "На ближайший период",
            "На текущий период",
            "В начале дня",
            "Во второй половине дня",
            "От ",
            "К вам поступило письмо",
            "От вас зависит",
            "Ваш коллега",
            "Один из сотрудников",
            "Один из ключевых участников",
            "У вас накапливается",
            "Появилась идея",
            "В команде появилась идея",
            "Перед передачей результата",
            "Во время выполнения",
            "В работе сотрудника",
            "Поведение ",
            "Это уже отражается",
            "Это отражается",
            "Появилось узкое место",
            "Возникло узкое место",
            "Обязательный шаг контроля качества",
            "Ваш коллега",
            "Один из коллег",
            "Перед ",
            "Клиент",
            "клиент",
            "Пользователь",
            "пользователь",
            "Заказчик",
            "заказчик",
            "Внешний клиент",
            "внешний клиент",
            "На вашем участке",
            "На одном участке",
        )
        lowered = source.lower()
        if not (
            lowered.startswith("вы работаете в роли ")
            or lowered.startswith("вы работаете как ")
            or lowered.startswith("вы работаете ")
        ):
            return source
        first_sentence_match = re.match(r"^.*?[.!?](?:\s+|$)", source, flags=re.DOTALL)
        first_sentence_end = first_sentence_match.end() if first_sentence_match else 0
        positions = [source.find(anchor) for anchor in anchors if source.find(anchor) >= max(first_sentence_end, 1)]
        if positions:
            return source[min(positions):].strip()
        if first_sentence_match:
            tail = source[first_sentence_match.end():].strip()
            if tail:
                return tail
        return self._strip_template_role_lead(source) or source

    def _remove_template_guidance_blocks(self, text: str) -> str:
        result = str(text or "").strip()
        if not result:
            return ""

        patterns = (
            r",?\s*и\s+сейчас\s+от\s+вас\s+ждут[^.?!]*[.?!]?",
            r"\s*От вас ждут[^.?!]*[.?!]?",
            r"\s*Сейчас важно[^.?!]*[.?!]?",
            r"\s*Сейчас нужно[^.?!]*[.?!]?",
            r"\s*Вам нужно[^.?!]*[.?!]?",
            r"\s*Прежде чем[^.?!]*[.?!]?",
            r"\s*До того, как[^.?!]*[.?!]?",
            r"\s*Чат-бот[^.?!]*[.?!]?",
            r"\s*Масштаб кейса[^.?!]*[.?!]?",
            r"\s*Но структура ответа[^.?!]*[.?!]?",
            r"\s*для\s+L\s*[—-][^.;!?]*(?:[.;!?]|$)?",
            r"\s*для\s+M\s*[—-][^.;!?]*(?:[.;!?]|$)?",
            r"\s*для\s+Leader\s*[—-][^.;!?]*(?:[.;!?]|$)?",
        )
        for pattern in patterns:
            result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result).strip()
        return result

    def _light_polish_template_locked_context(self, text: str, *, role_name: str | None) -> str:
        result = self._sanitize_user_case_text(text, role_name=role_name)
        if not result:
            return ""
        result = self._remove_template_guidance_blocks(result)
        result = re.sub(r"\bот\s+пользователь\b", "от пользователя", result, flags=re.IGNORECASE)
        result = re.sub(r"\bот\s+пользователи\b", "от пользователей", result, flags=re.IGNORECASE)
        result = re.sub(r"\bчерез\s+в\s+", "в ", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bкарточка заявки,\s*истори(?:й|и)\s+комментариев\s+и\s+статус(?:а|у)\s+в\s+Service\s+Desk\b",
            "карточке заявки, истории комментариев и статусу в Service Desk",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bподход\s+к\s+обновление\b", "подход к обновлению", result, flags=re.IGNORECASE)
        result = re.sub(r"\bподход\s+к\s+изменение\b", "подход к изменению", result, flags=re.IGNORECASE)
        result = re.sub(r"\bподход\s+к\s+подготовка\b", "подход к подготовке", result, flags=re.IGNORECASE)
        result = re.sub(r"\bклиентской поддержки и 1 смежный координатор на эскалациях\b", "2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях", result, flags=re.IGNORECASE)
        result = re.sub(r"\bклиентская поддержка и сопровождение обращений к клиент ждет\b", "в процессе клиентской поддержки клиент ждет", result, flags=re.IGNORECASE)
        result = re.sub(r"\bвокруг обновление клиента\b", "вокруг обновления клиента", result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result).strip()
        if result and result[-1] not in ".!?":
            result += "."
        return result

    def _build_generic_template_locked_context(self, specificity: dict[str, Any]) -> str:
        personalized = str(specificity.get("_template_context_personalized") or "").strip()
        if not personalized:
            return ""
        result = self._strip_template_role_prefix(personalized)
        result = self._remove_template_guidance_blocks(result)
        return re.sub(r"\s{2,}", " ", result).strip()

    def _strip_template_role_lead(self, sentence: str) -> str:
        text = str(sentence or "").strip()
        if not text:
            return ""
        anchors = (
            "Клиент",
            "клиент",
            "Пользователь",
            "пользователь",
            "Заказчик",
            "заказчик",
            "Внешний клиент",
            "внешний клиент",
            "От ",
            "от ",
            "В начале дня",
            "Во второй половине дня",
            "В последние недели",
            "Перед ",
            "Сейчас ",
            "Ваш коллега",
            "ваш коллега",
            "Один из коллег",
            "один из коллег",
        )
        positions = [text.find(anchor) for anchor in anchors if text.find(anchor) > 0]
        if positions:
            return text[min(positions):].strip()
        return ""

    def _build_strict_f02_template_context(self, specificity: dict[str, Any]) -> str:
        personalized = str(specificity.get("_template_context_personalized") or "").strip()
        if not personalized:
            return ""
        result = self._strip_template_role_prefix(personalized)
        result = self._remove_template_guidance_blocks(result)
        return re.sub(r"\s{2,}", " ", result).strip()

    def _build_strict_f09_template_context(self, specificity: dict[str, Any]) -> str:
        personalized = str(specificity.get("_template_context_personalized") or "").strip()
        if not personalized:
            return ""
        lowered = personalized.lower()
        anchors = (
            "в последние недели",
            "в последнее время",
            "в этом контуре",
            "в контуре ",
            "где сейчас есть узкое место",
            "это уже отражается",
            "это отражается",
        )
        positions = [lowered.find(anchor) for anchor in anchors if lowered.find(anchor) > 0]
        if positions:
            result = personalized[min(positions):].strip()
        else:
            result = self._strip_template_role_prefix(personalized)
        result = self._remove_template_guidance_blocks(result)
        result = re.sub(
            r"^В контуре\s+([^:]+):\s+(.+?)\.",
            r"В контуре \1 появилось узкое место: \2.",
            result,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s{2,}", " ", result).strip()

    def _domain_source_mismatch(self, specificity: dict[str, Any]) -> tuple[str, str]:
        family = self._infer_specificity_domain_family(specificity)
        if family == "horeca":
            return "POS-системе", "журнале смены"
        if family == "maritime":
            return "судовом журнале", "передаче вахты"
        if family == "engineering":
            return "листе согласования", "фактическом состоянии комплекта"
        if family == "business_analysis":
            return "карточке задачи в Jira", "согласованных требованиях"
        if family == "it_support":
            return "статусе обращения", "последнем комментарии по фактическому результату"
        return "первом источнике данных", "втором источнике подтверждения"

    def _title_plot_flags(self, case_title: str, *, template_text: str | None = None) -> set[str]:
        title = f"{case_title or ''} {template_text or ''}".lower()
        flags: set[str] = set()
        if any(word in title for word in ("жалоб", "претенз", "обратной связи", "срок")):
            flags.add("expectation_broken")
        if any(word in title for word in ("закрыт", "готов", "передач", "handoff")):
            flags.add("premature_close")
        if any(word in title for word in ("неясн", "сыр", "уточнен", "непол")):
            flags.add("missing_input")
        if any(word in title for word in ("перегруз", "приоритет", "в первую очередь", "главного")):
            flags.add("priority_conflict")
        if any(word in title for word in ("групп", "состав", "роли", "координац")):
            flags.add("coordination")
        if any(word in title for word in ("иде", "внедрен", "пилот", "изменен")):
            flags.add("idea")
        if any(word in title for word in ("несовпад", "контроль каче", "не подтвержден", "расхожден")):
            flags.add("mismatch")
        if any(word in title for word in ("разговор", "бесед", "договорен", "повторяющ")):
            flags.add("repeated_behavior")
        return flags

    def _render_business_impact_phrase(self, impact: str) -> str:
        value = cleanup_case_text(str(impact or "")).strip()
        if not value:
            return "сроки, качество результата и доверие к процессу"
        lowered = value.lower()
        if lowered.startswith("показател"):
            return value
        if any(marker in lowered for marker in ("сроке первого ответа", "доле повторных жалоб", "прозрачности статуса")):
            return f"показатели клиентского сервиса: {value}"
        if any(marker in lowered for marker in ("сроке запуска", "вовлеченности участников", "доле завершения")):
            return f"показатели программы обучения: {value}"
        if any(marker in lowered for marker in ("сроке выпуска", "доле возвратов", "качестве комплекта")):
            return f"показатели инженерного процесса: {value}"
        return value

    def _compose_plot_driven_complaint_context(self, specificity: dict[str, Any], *, case_title: str) -> str:
        workflow = str(specificity.get("workflow_label") or "текущий процесс")
        current_state = str(specificity.get("current_state") or self._describe_process_gap(specificity)).strip()
        if current_state and current_state[-1] not in ".!?":
            current_state += "."
        bottleneck = str(specificity.get("bottleneck") or "").strip()
        quote_text = str(specificity.get("message_quote") or "").strip()
        channel = str(specificity.get("channel") or "").lower()
        impact = self._render_business_impact_phrase(str(specificity.get("business_impact") or "сроки решения и доверие к процессу"))
        items = self._join_case_items((specificity.get("ticket_titles") or [])[:2])
        template_fragments = self._template_semantic_fragments(specificity)
        family = self._infer_specificity_domain_family(specificity)
        flags = self._title_plot_flags(
            case_title,
            template_text=f"{specificity.get('_template_context') or ''} {specificity.get('_template_task') or ''}",
        )
        if not quote_text:
            quote_text = template_fragments.get("quote") or ""
        if not quote_text:
            if "expectation_broken" in flags:
                quote_text = "Добрый день! Вы обещали дать обновление до конца дня, но ответа так и нет. Поясните, пожалуйста, что происходит и когда будет решение."
            elif "premature_close" in flags:
                quote_text = "Добрый день! Вопрос уже отмечен как решенный, но по факту проблема осталась. Поясните, пожалуйста, что именно сделано и какой следующий шаг."
            else:
                quote_text = "Добрый день! Я не понимаю, что сейчас происходит по моему вопросу и когда будет понятный итог."
        if any(word in channel for word in ("jira", "комментар")):
            intro = "Во второй половине дня заказчик пишет в комментариях к задаче:"
        elif family == "client_service":
            intro = "Во второй половине дня клиент пишет:"
        elif "чат" in channel:
            intro = "Во второй половине дня через рабочий чат приходит сообщение:"
        else:
            intro = "Во второй половине дня участник процесса пишет:"
        text = f"{intro} «{quote_text}» {current_state}"
        if bottleneck:
            text += f" Основная проблема сейчас в том, что {bottleneck}."
        else:
            text += f" Сейчас по процессу «{workflow}» уже есть движение, но следующий шаг и фактический результат видны не всем участникам одинаково."
        expectation = template_fragments.get("expectation") or ""
        if expectation and expectation not in text:
            text += f" {expectation}"
        if items:
            text += f" В ситуации уже фигурируют такие рабочие объекты: {items}."
        text += f" Из-за этого уже страдают {impact}."
        return text.strip()

    def _compose_plot_driven_clarification_context(self, specificity: dict[str, Any], *, case_title: str) -> str:
        strict_template_context = self._build_strict_f02_template_context(specificity)
        if strict_template_context:
            return strict_template_context

        workflow = str(specificity.get("workflow_label") or "текущий процесс")
        request_type = str(specificity.get("request_type") or "рабочий запрос")
        current_state = str(specificity.get("current_state") or self._describe_process_gap(specificity)).strip()
        if current_state and current_state[-1] not in ".!?":
            current_state += "."
        bottleneck = str(specificity.get("bottleneck") or "").strip()
        examples = self._join_case_items((specificity.get("ticket_titles") or [])[:3])
        template_fragments = self._template_semantic_fragments(specificity)
        flags = self._title_plot_flags(
            case_title,
            template_text=f"{specificity.get('_template_context') or ''} {specificity.get('_template_task') or ''}",
        )
        quote = template_fragments.get("quote") or ""
        opening = f"В начале работы вам приходит короткий запрос: «{quote}»." if quote else (
            f"В начале работы вам приходит короткий запрос по процессу «{workflow}»."
        )
        text = f"{opening}"
        ambiguity = template_fragments.get("ambiguity") or ""
        if ambiguity and ambiguity not in text:
            text += f" {ambiguity}"
        else:
            text += (
                f" По самому запросу пока неясно, какой результат нужен, какой объем считается обязательным "
                f"и какие ограничения нужно учесть для задачи типа «{request_type}»."
            )
        if current_state:
            text += f" {current_state}"
        if bottleneck:
            text += f" Основная проблема сейчас в том, что {bottleneck}."
        elif "missing_input" in flags:
            text += " Основная проблема сейчас в том, что команда уже видит проблему, но до сих пор не зафиксировала, каких данных не хватает для следующего шага."
        else:
            text += f" Сейчас работа по процессу «{workflow}» уже имеет несколько вариантов исполнения, и без уточнения команда может по-разному понять, что считать готовым результатом."
        if examples:
            text += f" Уже фигурируют такие рабочие элементы: {examples}."
        risk = template_fragments.get("risk") or ""
        if risk:
            text += f" {risk}"
        else:
            text += " Если начать работу сразу, есть риск двинуться не в ту сторону, получить возврат и потратить время на лишнюю переделку."
        expectation = template_fragments.get("expectation") or ""
        if expectation and expectation not in text:
            text += f" {expectation}"
        return text.strip()

    def _compose_plot_driven_conversation_context(self, specificity: dict[str, Any], *, case_title: str) -> str:
        workflow = str(specificity.get("workflow_label") or "текущий процесс")
        impact = str(specificity.get("business_impact") or "сроки и устойчивость процесса")
        critical_step = str(specificity.get("critical_step") or "следующий шаг")
        current_state = str(specificity.get("current_state") or self._describe_process_gap(specificity)).strip()
        if current_state and current_state[-1] not in ".!?":
            current_state += "."
        bottleneck = str(specificity.get("bottleneck") or "").strip()
        examples = self._join_case_items((specificity.get("ticket_titles") or [])[:2])
        text = (
            f"В последние недели в процессе «{workflow}» повторяется один и тот же паттерн: критичный шаг «{critical_step}» закрывается или передается дальше раньше, чем команда действительно подтверждает результат. "
            f"{current_state}"
        )
        if bottleneck:
            text += f" Основная проблема в том, что {bottleneck}."
        text += f" Из-за этого начинают страдать {impact}, а команде приходится возвращаться к уже закрытым вопросам."
        if examples:
            text += f" В похожих случаях уже всплывают такие рабочие объекты: {examples}."
        text += " Вам нужно провести разговор с сотрудником, чтобы договориться о более устойчивом порядке работы и снизить риск повторения этой ситуации."
        return text.strip()

    def _compose_plot_driven_control_risk_context(self, specificity: dict[str, Any], *, case_title: str) -> str:
        workflow = str(specificity.get("workflow_label") or "текущий процесс")
        impact = str(specificity.get("business_impact") or "сроки, качество результата и повторные возвраты")
        current_state = str(specificity.get("current_state") or self._describe_process_gap(specificity)).strip()
        if current_state and current_state[-1] not in ".!?":
            current_state += "."
        bottleneck = str(specificity.get("bottleneck") or "").strip()
        critical_step = str(specificity.get("critical_step") or "следующий шаг")
        left_source, right_source = self._domain_source_mismatch(specificity)
        examples = self._join_case_items((specificity.get("ticket_titles") or [])[:2])
        template_fragments = self._template_semantic_fragments(specificity)
        text = (
            f"Перед следующим этапом работы по процессу «{workflow}» обнаружилось несоответствие: данные в {left_source} и в {right_source} не совпадают, "
            f"хотя результат уже хотят передавать дальше. {current_state}"
        )
        mismatch = template_fragments.get("mismatch") or ""
        if mismatch and mismatch not in text:
            text += f" {mismatch}"
        if bottleneck:
            text += f" Ключевая проблема сейчас в том, что {bottleneck}."
        else:
            text += f" Критичный шаг «{critical_step}» еще не подтвержден так, чтобы следующему участнику процесса было понятно, на что он может опираться."
        if examples:
            text += f" В ситуации уже фигурируют такие рабочие объекты: {examples}."
        text += f" Если передать результат в таком виде, пострадают {impact}."
        return text.strip()

    def _should_bypass_template_locked_context(
        self,
        *,
        case_type_code: str | None,
        case_specificity: dict[str, Any] | None,
    ) -> bool:
        type_code = str(case_type_code or "").upper()
        if type_code not in {"F05", "F08", "F09", "F10", "F11"}:
            return False
        family = self._infer_specificity_domain_family(case_specificity or {})
        return family == "learning_and_development"

    def _build_template_locked_context(
        self,
        *,
        case_type_code: str | None,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        type_code = str(case_type_code or "").upper()
        specificity = case_specificity or {}
        if self._should_use_strict_scene_narrative(
            case_type_code=type_code,
            case_specificity=specificity,
        ) and not self._should_prefer_template_context(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            return ""
        if self._should_bypass_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            return ""
        if type_code in {"F02", "F03", "F05", "F08", "F09", "F10", "F11", "F12"} and specificity.get("_case_frame"):
            return self._inject_template_theme_details(
                self._apply_plot_skeleton(
                    "",
                    case_type_code=type_code,
                    case_title=str(specificity.get("_case_title") or ""),
                    case_specificity=specificity,
                ),
                case_type_code=type_code,
                specificity=specificity,
            )
        if type_code == "F02":
            return self._inject_template_theme_details(
                self._build_strict_f02_template_context(specificity),
                case_type_code=type_code,
                specificity=specificity,
            )
        if type_code == "F09":
            return self._inject_template_theme_details(
                self._build_strict_f09_template_context(specificity),
                case_type_code=type_code,
                specificity=specificity,
            )
        return self._inject_template_theme_details(
            self._build_generic_template_locked_context(specificity),
            case_type_code=type_code,
            specificity=specificity,
        )

    def _inject_template_theme_details(
        self,
        text: str,
        *,
        case_type_code: str | None,
        specificity: dict[str, Any] | None,
    ) -> str:
        current = str(text or "").strip()
        if not current:
            return ""
        type_code = str(case_type_code or "").upper()
        data = specificity or {}
        named_stakeholders = str(data.get("stakeholder_named_list") or "").strip()
        source = cleanup_case_text(str(data.get("source_of_truth") or ""))
        channel = cleanup_case_text(str(data.get("channel") or ""))
        additions: list[str] = []
        if type_code == "F01" and source and "Проверить детали можно по" not in current:
            additions.append(f"Проверить детали можно по {source}.")
        elif type_code == "F03" and named_stakeholders:
            conversation_target = self._extract_named_primary_participant(named_stakeholders)
            if conversation_target and conversation_target not in current:
                additions.append(f"Разговор предстоит с коллегой — {conversation_target}.")
        elif type_code == "F11" and channel:
            if re.match(r"^(?:в|во|по|через)\b", channel.lower()):
                additions.append(f"Фиксация риска должна пройти {channel}.")
            else:
                additions.append(f"Фиксация риска должна пройти через {channel}.")
        for addition in additions:
            if addition and addition not in current:
                current = f"{current} {addition}".strip()
        return current

    def _apply_plot_skeleton(
        self,
        text: str,
        *,
        case_type_code: str | None,
        case_title: str,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        current = (text or "").strip()
        type_code = str(case_type_code or "").upper()
        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code=type_code,
                case_title=case_title,
                case_context=current,
                case_task="",
            ),
        )
        specificity["_case_title"] = case_title
        if self._infer_specificity_domain_family(specificity) == "learning_and_development":
            lnd_scene = self._compose_learning_and_development_scene_context(
                specificity,
                case_type_code=type_code,
            )
            if lnd_scene and type_code in {"F02", "F03", "F05", "F08", "F09", "F10", "F11", "F12"}:
                return lnd_scene.strip()
        if type_code == "F01":
            return self._compose_plot_driven_complaint_context(specificity, case_title=case_title)
        if type_code == "F02":
            return self._compose_plot_driven_clarification_context(specificity, case_title=case_title)
        if type_code == "F03":
            return self._compose_plot_driven_conversation_context(specificity, case_title=case_title)
        if type_code == "F05":
            base = self._compose_planning_case_context(specificity)
            if "coordination" in self._title_plot_flags(
                case_title,
                template_text=f"{specificity.get('_template_context') or ''} {specificity.get('_template_task') or ''}",
            ):
                base += " Здесь особенно важно заранее договориться, кто держит на себе координацию, кому принадлежат спорные решения и как команда фиксирует контрольные точки."
            return base.strip()
        if type_code == "F08":
            base = self._compose_priority_case_context(specificity)
            if "priority_conflict" in self._title_plot_flags(
                case_title,
                template_text=f"{specificity.get('_template_context') or ''} {specificity.get('_template_task') or ''}",
            ):
                base += " У каждой из конкурирующих задач есть своя цена ошибки, поэтому здесь важен осознанный первый выбор, а не просто реакция на самый громкий сигнал."
            return base.strip()
        if type_code == "F09":
            base = self._compose_improvement_case_context(specificity)
            if "premature_close" in self._title_plot_flags(
                case_title,
                template_text=f"{specificity.get('_template_context') or ''} {specificity.get('_template_task') or ''}",
            ):
                base += " Здесь важно предложить изменение именно в том месте, где процесс формально закрывается раньше фактического результата."
            return base.strip()
        if type_code == "F10":
            base = self._compose_idea_evaluation_case_context(specificity)
            if "idea" in self._title_plot_flags(
                case_title,
                template_text=f"{specificity.get('_template_context') or ''} {specificity.get('_template_task') or ''}",
            ):
                base += " Нужно оценить не только полезность идеи, но и какой формат запуска даст сигнал без лишнего риска для текущей работы."
            return base.strip()
        if type_code == "F11":
            return self._compose_plot_driven_control_risk_context(specificity, case_title=case_title)
        if type_code == "F12":
            return self._compose_development_conversation_case_context(specificity)
        return current

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

    def _humanize_current_state(self, text: str) -> str:
        clean = cleanup_case_text(str(text or ""))
        if not clean:
            return ""
        clean = re.sub(r"^\s*сейчас\s+", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bне всегда в одном месте и не в один момент\b", "не в одном месте", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bна одном из шагов\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bиногда остается неполным\b", "остается неполным", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\bне всегда фиксируется до следующего этапа\b", "фиксируются не до конца", clean, flags=re.IGNORECASE)
        clean = re.sub(r"(\d+),\s+(\d+)", r"\1,\2", clean)
        clean = re.sub(r"([0-9%])\s+(Проверить детали можно по)\b", r"\1. \2", clean, flags=re.IGNORECASE)
        clean = re.sub(r"([0-9%])\s+(Если ничего не сделать сейчас)\b", r"\1. \2", clean, flags=re.IGNORECASE)
        clean = re.sub(r"([0-9%])\s+(Одновременно внимания требуют)\b", r"\1. \2", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s{2,}", " ", clean).strip(" ,")
        if clean and clean[-1] not in ".!?":
            clean += "."
        return clean

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

    def _humanize_role_name(self, role_name: str | None, position: str | None = None) -> str:
        role = (role_name or position or "").strip()
        lowered = role.lower()
        if not lowered:
            return "специалист"
        if lowered in {"l", "linear", "line"} or "линей" in lowered:
            return "линейный сотрудник"
        if lowered in {"m", "manager"} or "менедж" in lowered or "руковод" in lowered:
            return "менеджер"
        if lowered == "leader" or "лидер" in lowered or "дир" in lowered or "стратег" in lowered:
            return "лидер"
        return lowered

    def enforce_user_case_quality(
        self,
        *,
        case_type_code: str | None,
        case_title: str,
        case_context: str,
        case_task: str,
        role_name: str | None,
        company_industry: str | None,
        case_specificity: dict[str, Any] | None,
        existing_contexts: list[str] | None = None,
    ) -> tuple[str, str]:
        current_context = self._restore_minimum_case_context(
            (case_context or "").strip(),
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        current_task = (case_task or "").strip()
        if not current_context:
            return current_context, current_task

        locked_context = self._build_template_locked_context(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        )
        if locked_context and not self._should_bypass_template_locked_context(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        ) and not self._should_use_strict_scene_narrative(
            case_type_code=case_type_code,
            case_specificity=case_specificity,
        ):
            current_context = self._light_polish_template_locked_context(locked_context, role_name=role_name)
            current_context = self._build_structured_user_case_context(
                context_text=current_context,
                case_specificity=case_specificity,
            )
            current_context = self._proofread_user_case_text(current_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
            current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
            return current_context.strip(), current_task

        prior_contexts = [str(item).strip() for item in (existing_contexts or []) if str(item).strip()]
        if not prior_contexts:
            current_context = self._proofread_user_case_text(current_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
            current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
            return current_context, current_task

        if self._case_text_is_too_similar(current_context, prior_contexts):
            rebuilt = self._rebuild_context_from_type(
                case_type_code=case_type_code,
                case_title=case_title,
                case_specificity=case_specificity,
            )
            if rebuilt and rebuilt != current_context:
                current_context = rebuilt
            if self._case_text_is_too_similar(current_context, prior_contexts):
                current_context = self._diversify_case_context(
                    current_context,
                    case_type_code=case_type_code,
                    case_title=case_title,
                    case_specificity=case_specificity,
                )

        current_context = self._sanitize_user_case_text(current_context, role_name=role_name)
        current_context = self._polish_user_case_context(
            current_context,
            role_name=role_name,
            case_title=case_title,
            company_industry=company_industry,
        )
        current_context = self._build_structured_user_case_context(
            context_text=current_context,
            case_specificity=case_specificity,
        )
        current_task = cleanup_case_text(current_task)
        if len(current_task) < 40:
            current_task = self._polish_user_case_task(
                current_task,
                case_title=case_title,
                context_text=current_context,
                case_type_code=case_type_code,
            )
            current_task = cleanup_case_text(current_task)
        quality = self._evaluate_user_case_quality(
            case_context=current_context,
            case_task=current_task,
            case_specificity=case_specificity,
        )
        if quality["passed"]:
            current_context = self._proofread_user_case_text(current_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
            current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
            return current_context.strip(), current_task

        rebuilt = self._rebuild_context_from_type(
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        if rebuilt and rebuilt != current_context:
            rebuilt = self._sanitize_user_case_text(rebuilt, role_name=role_name)
            rebuilt = self._polish_user_case_context(
                rebuilt,
                role_name=role_name,
                case_title=case_title,
                company_industry=company_industry,
            )
            rebuilt = self._build_structured_user_case_context(
                context_text=rebuilt,
                case_specificity=case_specificity,
            )
            rebuilt_quality = self._evaluate_user_case_quality(
                case_context=rebuilt,
                case_task=current_task,
                case_specificity=case_specificity,
            )
            if rebuilt_quality["passed"]:
                rebuilt = self._proofread_user_case_text(rebuilt, role_name=role_name, is_task=False, case_type_code=case_type_code)
                current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
                return rebuilt.strip(), current_task

        minimum_context = self._restore_minimum_case_context(
            current_context,
            case_type_code=case_type_code,
            case_title=case_title,
            case_specificity=case_specificity,
        )
        minimum_context = self._sanitize_user_case_text(minimum_context, role_name=role_name)
        minimum_context = self._polish_user_case_context(
            minimum_context,
            role_name=role_name,
            case_title=case_title,
            company_industry=company_industry,
        )
        minimum_context = self._build_structured_user_case_context(
            context_text=minimum_context,
            case_specificity=case_specificity,
        )
        if len(current_task) < 40:
            current_task = self._polish_user_case_task(
                current_task,
                case_title=case_title,
                context_text=minimum_context,
                case_type_code=case_type_code,
            )
            current_task = cleanup_case_text(current_task)
        minimum_context = self._proofread_user_case_text(minimum_context, role_name=role_name, is_task=False, case_type_code=case_type_code)
        current_task = self._proofread_user_case_text(current_task, role_name=role_name, is_task=True, case_type_code=case_type_code)
        return minimum_context.strip(), current_task

    def _proofread_user_case_text(
        self,
        text: str,
        *,
        role_name: str | None,
        is_task: bool,
        case_type_code: str | None = None,
    ) -> str:
        result = cleanup_case_text(text)
        result = self._apply_case_prompt_grammar_rules(result)
        result = self._humanize_generated_case_language(result)
        result = self._apply_instruction_driven_case_text_cleanup(
            result,
            case_type_code=case_type_code,
            is_task=is_task,
        )
        result = re.sub(r"\bв процессе\s+обработк([аиуыое])\b", "в процессе обработки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+сбоя\b", "по вопросу сбоя", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+отсутствия\b", "по вопросу отсутствия", result, flags=re.IGNORECASE)
        result = re.sub(r"\b(эта|это) может улучшить\b", "Это может улучшить", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпока неясно, стоит ли запускать изменение сразу и как сделать это безопасно\b", "Пока неясно, стоит ли запускать изменение сразу и как сделать это безопасно", result, flags=re.IGNORECASE)
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)
        result = re.sub(r"([,.;:!?])([^\s\n])", r"\1 \2", result)
        result = re.sub(r"\.\s*\.", ".", result)
        result = re.sub(r":\s*\.", ":", result)
        result = re.sub(r"\bлинейный сотрудник\b", "линейный сотрудник", result, flags=re.IGNORECASE)
        result = self._dedupe_case_text_repetitions(result, is_task=is_task)
        result = self._normalize_prompt_sentences(result)
        if not is_task:
            result = re.sub(r"^(Ситуация:\s*\*\*[^*]+\*\*)\s+([А-ЯЁA-Z])", r"\1\n\n\2", result, count=1)
            result = re.sub(r"\s+(\*\*Что известно\*\*)", r"\n\n\1", result, flags=re.IGNORECASE)
            result = re.sub(r"\s+(\*\*Что ограничивает\*\*)", r"\n\n\1", result, flags=re.IGNORECASE)
            result = re.sub(r"(\*\*Что известно\*\*)\s*-", r"\1\n-", result, flags=re.IGNORECASE)
            result = re.sub(r"(\*\*Что ограничивает\*\*)\s*-", r"\1\n-", result, flags=re.IGNORECASE)
            result = re.sub(r"\n{3,}", "\n\n", result)
        if role_name:
            result = result.replace("в роли линейного аналитика", f"в роли {self._resolve_role_scope(role_name).split(':')[0].strip().lower()}")
        if is_task and result and not result.lower().startswith("что нужно сделать"):
            result = f"Что нужно сделать: {result[0].upper() + result[1:] if result else result}"
        if is_task and result and not result.endswith((".", "!", "?")):
            result += "."
        result = result.replace("потому что Это может", "потому что это может")
        result = result.replace(", но Пока неясно", ", но пока неясно")
        result = re.sub(
            r"^\s*2 специалиста\s+В распоряжении команды сейчас 2 специалиста\s+2 специалиста\s+клиентской поддержки and 1 смежный координатор на эскалациях\.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*2 специалиста\s+В распоряжении команды сейчас 2 специалиста\s+2 специалиста\s+клиентской поддержки и 1 смежный координатор на эскалациях\.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            result,
            flags=re.IGNORECASE,
        )
        result = result.replace(
            "2 специалиста В распоряжении команды сейчас 2 специалиста 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
        )
        result = result.replace(
            "В распоряжении команды сейчас 2 специалиста 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях.",
        )
        return result.strip()

    def _apply_instruction_driven_case_text_cleanup(
        self,
        text: str,
        *,
        case_type_code: str | None,
        is_task: bool,
    ) -> str:
        result = cleanup_case_text(text)
        if not is_task:
            result = self._restore_case_section_spacing(result)
        result = self._repair_case_text_fragments(result, is_task=is_task)
        result = self._strip_unresolved_case_placeholders(result, is_task=is_task)
        if not is_task:
            result = self._restore_case_section_spacing(result)
        return cleanup_case_text(result)

    def _repair_case_text_fragments(self, text: str, *, is_task: bool) -> str:
        result = str(text or "").strip()
        if not result:
            return ""

        phrase_replacements = (
            (
                r"\bКлиентской поддержки и 1 смежный координатор на эскалациях;\s*горизонт работы\s*—\s*([0-9: ]+до[0-9: ]+|[^.]+)\.",
                r"В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях. Горизонт работы — \1.",
            ),
            (
                r"\bКлиентской поддержки и 1 смежный координатор на эскалациях\b",
                "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях",
            ),
            (
                r"\bВ доступе сейчас только В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях\b",
                "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях",
            ),
            (
                r"\bСтавки высокие:\s*на кону\s+стабильность работы на этом участке:\s*стабильность работы:\s*",
                "Ставки высокие: на кону стабильность работы на этом участке — ",
            ),
            (
                r"\bприв[её]л к повторная жалоба клиента, эскалация и снижение доверия к сервису\b",
                "привел к повторной жалобе клиента, эскалации и снижению доверия к сервису",
            ),
            (
                r"\bиз клиентская поддержка, смежная сервисная команда и руководитель направления\b",
                "из клиентской поддержки, смежной сервисной команды и руководителя направления",
            ),
            (
                r"\bесть данные из карточка обращения, история коммуникации в CRM и внутренние комментарии команды\b",
                "есть данные из карточки обращения, истории коммуникации в CRM и внутренних комментариев команды",
            ),
            (
                r"\n?Сейчас\.\s*$",
                "",
            ),
            (
                r"\bКлиентская поддержка и сопровождение обращений к клиент ждет обновление\b",
                "В процессе клиентской поддержки клиент ждет обновление",
            ),
            (
                r"\bЭто касается \*\*дневная сервисная смена\b",
                "Это касается **дневной сервисной смены",
            ),
            (
                r"\bбудут заметны для клиент\b",
                "будут заметны для клиента",
            ),
            (
                r"\bвокруг обновление клиента\b",
                "вокруг обновления клиента",
            ),
            (
                r"\bэто может улучшить\b",
                "Это может улучшить",
            ),
            (
                r"\bно пока неясно\b",
                "Но пока неясно",
            ),
            (
                r"\bпотому что Это может\b",
                "потому что это может",
            ),
            (
                r"\bно Пока неясно\b",
                "но пока неясно",
            ),
            (
                r"\bдля клиент\b",
                "для клиента",
            ),
            (
                r"\bКлючевой стейкхолдер\b",
                "Ключевой участник",
            ),
            (
                r"\bключевой стейкхолдер\b",
                "ключевой участник",
            ),
            (
                r"\b1:\s+1\b",
                "1:1",
            ),
            (
                r"Что нужно сделать:\s*Что нужно сделать:\s*",
                "Что нужно сделать:\n",
            ),
        )
        for pattern, replacement in phrase_replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        result = re.sub(
            r"(?:\b2 специалиста\s+){2,}",
            "2 специалиста ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"В распоряжении команды сейчас\s+(?:2 специалиста\s+){2,}клиентской поддержки",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:В распоряжении команды сейчас 2 специалиста\s+){2,}",
            "В распоряжении команды сейчас 2 специалиста ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях\.\s*){2,}",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки и 1 смежный координатор на эскалациях. ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*2 специалиста\s+В распоряжении команды сейчас 2 специалиста\s+",
            "В распоряжении команды сейчас 2 специалиста ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*В распоряжении команды сейчас 2 специалиста\s+2 специалиста\s+клиентской поддержки",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bклиента{2,}\b", "клиента", result, flags=re.IGNORECASE)
        result = re.sub(r",\s*Но пока неясно\b", ", но пока неясно", result)
        result = re.sub(r"\bпотому что\s+Это может\b", "потому что это может", result)
        result = re.sub(r"\bвокруг обновления клиента по обращению и фиксация следующего шага\b", "вокруг обновления клиента по обращению и фиксации следующего шага", result, flags=re.IGNORECASE)
        result = re.sub(r"\b([А-ЯЁа-яё]+)\s+ждет обновление\b", lambda m: f"{m.group(1)} ждет обновления", result)
        result = re.sub(r"\bв процессе \*\*([^*]+)\*\* команда снова и снова возвращается к одним и тем же вопросам вокруг ([^.,]+)", r"В процессе **\1** команда снова и снова возвращается к одним и тем же вопросам вокруг \2", result)
        result = re.sub(r"\bпо обращениям клиентов часть статусов уже обновлена, но подтверждение результата и следующий шаг по обращению фиксируются не до конца\b", "По обращениям клиентов часть статусов уже обновлена, но подтвержденный результат и следующий шаг фиксируются не полностью", result, flags=re.IGNORECASE)
        result = re.sub(r"\bобращение закрывают или передают дальше раньше, чем подтвержден фактический результат, следующий шаг и обновление пользователя\b", "обращение закрывают или передают дальше раньше, чем подтверждены фактический результат, следующий шаг и обновление клиента", result, flags=re.IGNORECASE)
        result = re.sub(r"\bрешение по запуску идеи будут обсуждать\b", "Решение по запуску идеи будут обсуждать", result, flags=re.IGNORECASE)
        result = re.sub(
            r"(?:^|\s)Оцениваемый\s*[—:-]\s*[^.?!]*(?:\{[^}]+\}[^.?!]*)[.?!]?",
            " ",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:^|\s)Оцениваемый\s*[—:-]\s*[^.?!]*(?:;[^.?!]*){0,6}[.?!]?",
            " ",
            result,
            flags=re.IGNORECASE,
        )
        result = self._strip_unresolved_case_placeholders(result, is_task=is_task)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()

    def _strip_unresolved_case_placeholders(self, text: str, *, is_task: bool) -> str:
        result = str(text or "").strip()
        if not result:
            return ""
        result = re.sub(r"\{[^{}]{1,80}\}", "", result)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\s+([,.;:])", r"\1", result)
        result = re.sub(r"([,.;:])(?=[^\s])", r"\1 ", result)
        result = re.sub(r"(?:\s*;\s*){2,}", "; ", result)
        result = re.sub(r"\s+\.", ".", result)
        if not is_task:
            result = re.sub(r"(?:^|\s)[;,:-]\s*(?=[А-ЯЁа-яё])", " ", result)
        return cleanup_case_text(result).strip()

    def _is_generic_case_state(self, text: str) -> bool:
        value = cleanup_case_text(text).lower()
        if not value:
            return True
        generic_markers = (
            "часть статусов уже обновлена",
            "подтвержденный результат и следующий шаг фиксируются не полностью",
            "подтверждение результата и следующий шаг",
            "истории коммуникации в crm",
            "внутренним комментариям команды",
        )
        return any(marker in value for marker in generic_markers)

    def _rewrite_generic_case_state(
        self,
        *,
        case_type_code: str,
        state_text: str,
        work_items: str,
        source_text: str,
    ) -> str:
        state = cleanup_case_text(state_text)
        if not state:
            return ""
        type_code = str(case_type_code or "").upper()
        work = cleanup_case_text(work_items)
        source = cleanup_case_text(source_text)
        short_work = self._compact_case_focus_reference(work, max_items=2)

        if type_code == "F01":
            if short_work:
                return f"Внутри команды уже сделали часть шагов по ситуации: {short_work}. Но подтвержденный ответ и следующий шаг для клиента пока не собраны в одну понятную картину."
            return "Внутри команды часть работы уже сделана, но подтвержденный ответ и следующий шаг для клиента пока не собраны в одну понятную картину."
        if type_code == "F02":
            if short_work:
                return f"Внутри команды уже начали конкретные шаги: {short_work}. Но пока не хватает ясности о владельце, статусе и следующем шаге."
            return "Внутри команды уже есть отдельные действия по обращению, но по ним пока не хватает ясности о владельце, статусе и следующем шаге."
        if type_code == "F03":
            if short_work:
                return f"Ситуация уже успела вызвать напряжение: участники по-разному понимают, что происходит с такими шагами, как {short_work}."
            return "Ситуация уже успела вызвать напряжение, потому что команда и клиент видят статус обращения по-разному."
        if type_code == "F04":
            if short_work:
                return f"Часть действий уже выполнена, включая {short_work}, но без согласования между сторонами следующий шаг остается неясным."
            return "Часть действий по обращению уже выполнена, но без согласования между сторонами следующий шаг остается неясным."
        if type_code == "F05":
            if short_work:
                return f"Команда уже ведет несколько параллельных задач, включая {short_work}. Но роли, следующий шаг и контрольные точки пока не собраны в единый порядок."
            return "По части обращений работа уже идет, но роли, следующий шаг и контрольные точки пока не собраны в единый порядок."
        if type_code == "F07":
            if short_work:
                return f"По ситуации уже видны отдельные сигналы и шаги, например {short_work}, но полной и непротиворечивой картины пока нет."
            return "По обращению уже есть отдельные сигналы и действия, но полной и непротиворечивой картины пока нет."
        if type_code == "F08":
            if short_work:
                return f"Одновременно конкурируют такие задачи: {short_work}. По ним пока нет единого понимания, что брать первым."
            return "В работе одновременно несколько задач, и по ним пока нет единого понимания, что брать первым."
        if type_code == "F09":
            if short_work:
                return "Проблема повторяется не разово: команде снова приходится сверять между собой статус обращения, ответственного и следующий шаг, вместо того чтобы доводить ситуацию до результата."
            return "Проблема повторяется не разово: команде снова приходится возвращаться к статусу обращения, ответственному и следующему шагу вместо движения ситуации к результату."
        if type_code == "F10":
            if short_work:
                return f"По ситуации уже предпринимались шаги, включая {short_work}, но итог для клиента все еще выглядит спорным и неустойчивым."
            return "По обращению уже предпринимались шаги, но итог для клиента все еще выглядит спорным и неустойчивым."
        if type_code == "F11":
            return "По документам и рабочим отметкам картина пока не совпадает, поэтому безопасно передавать результат дальше нельзя."
        if type_code == "F12":
            if short_work:
                return f"Паттерн уже повторялся раньше: команда теряет единый контекст и вынуждена снова возвращаться к таким шагам, как {short_work}."
            return "Паттерн уже повторялся раньше: команда теряет единый контекст и снова возвращается к одному и тому же обращению."

        if work:
            return f"По рабочему контуру пока нет полной ясности: {work}."
        if source:
            return f"Полную картину сейчас приходится собирать по {source}."
        return state

    def _compact_case_focus_reference(self, text: str, *, max_items: int = 2) -> str:
        cleaned = cleanup_case_text(str(text or "")).strip(" .")
        if not cleaned:
            return ""
        lower = cleaned.lower()
        source_markers = ("карточк", "истори", "crm", "комментар", "журнал", "service desk")
        if sum(1 for marker in source_markers if marker in lower) >= 2:
            return ""
        if any(marker in lower for marker in ("жалоба без", "статус в crm", "обращение с просроченным", "просроченным ответом")):
            return ""
        raw_parts = [part.strip(" .") for part in re.split(r"\s*,\s*|\s*;\s*", cleaned) if part.strip(" .")]
        if len(raw_parts) <= 1:
            return cleaned
        compact = cleanup_case_list(raw_parts, limit=max_items)
        return join_case_list(compact, limit=max_items) or cleaned

    def _normalize_user_visible_participant_phrase(self, text: str) -> str:
        cleaned = self._strip_unresolved_case_placeholders(str(text or ""), is_task=False).strip(" .")
        if not cleaned:
            return ""
        replacements = (
            (r"\bключевым?\s+стейкхолдер(ом|а|у|е)?\b", lambda m: {
                "ом": "ключевым участником",
                "а": "ключевого участника",
                "у": "ключевому участнику",
                "е": "ключевом участнике",
                None: "ключевой участник",
                "": "ключевой участник",
            }.get(m.group(1), "ключевой участник")),
            (r"\bстейкхолдеры\b", "участники"),
            (r"\bстейкхолдеров\b", "участников"),
            (r"\bстейкхолдеру\b", "участнику"),
            (r"\bстейкхолдером\b", "участником"),
            (r"\bстейкхолдере\b", "участнике"),
            (r"\bстейкхолдер\b", "участник"),
        )
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        raw_parts = [part.strip(" .;") for part in re.split(r"\s*;\s*|\s*,\s*", cleaned) if part.strip(" .;")]
        filtered_parts: list[str] = []
        for part in raw_parts:
            lowered = part.lower()
            if lowered in {"оцениваемый", "смежник"}:
                continue
            if "при необходимости" in lowered and len(lowered) < 60:
                continue
            filtered_parts.append(part)
        if filtered_parts:
            cleaned = join_case_list(filtered_parts, limit=4) or "; ".join(filtered_parts)
        return cleanup_case_text(cleaned).strip(" .")

    def _clarify_status_subject(self, text: str, *, default_object: str = "обращения") -> str:
        cleaned = cleanup_case_text(str(text or "")).strip(" .")
        if not cleaned:
            return ""
        if re.search(r"\bстатус(?:а|у|ом|е)?\s+обращен", cleaned, flags=re.IGNORECASE):
            return cleaned
        cleaned = re.sub(
            r"\bразные версии статуса\b",
            "разные версии статуса одного и того же обращения",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\bкакой следующий шаг актуален\b",
            "какой следующий шаг по обращению актуален",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleanup_case_text(cleaned).strip(" .")

    def _normalize_resource_sentence(self, text: str) -> str:
        cleaned = cleanup_case_text(str(text or "")).strip(" .")
        if not cleaned:
            return ""
        marker = re.search(r"(в распоряжении команды сейчас.+)$", cleaned, flags=re.IGNORECASE)
        if marker:
            return cleanup_case_text(marker.group(1)).strip(" .")
        return cleaned

    def _render_case_scope_sentence(self, text: str) -> str:
        cleaned = cleanup_case_text(str(text or "")).strip(" .")
        if not cleaned:
            return ""
        lower = cleaned.lower()
        if any(token in lower for token in ("клиентск", "поддержк", "service desk", "обращени")):
            return f"Это касается подразделения клиентской поддержки: {cleaned}."
        if any(token in lower for token in ("смен", "эскалац")):
            return f"Это касается рабочей смены или линии работы: {cleaned}."
        if any(token in lower for token in ("разработ", "jira", "требован", "аналит")):
            return f"Это касается команды разработки и аналитики: {cleaned}."
        if any(token in lower for token in ("обучени", "курс", "lms", "hrm")):
            return f"Это касается функции обучения и развития: {cleaned}."
        if any(token in lower for token in ("экипаж", "вахт", "судов", "рейс")):
            return f"Это касается судовой смены и передачи вахты: {cleaned}."
        if any(token in lower for token in ("производ", "цех", "отк", "сырь")):
            return f"Это касается производственного подразделения: {cleaned}."
        return f"Сейчас в работе такие конкретные позиции: {cleaned}."

    def _select_conversation_counterpart(self, specificity: dict[str, Any], frame: dict[str, Any]) -> str:
        named = cleanup_case_text(str(specificity.get("stakeholder_named_list") or frame.get("participants") or "")).strip()
        if named:
            parts = [part.strip() for part in re.split(r"\s*,\s*|\s+и\s+", named) if part.strip()]
            for part in parts:
                normalized = self._normalize_user_visible_participant_phrase(part)
                lower = normalized.lower()
                if lower and lower not in {"клиент", "заказчик", "пользователь", "участник процесса"}:
                    return normalized
        primary = self._normalize_user_visible_participant_phrase(
            str(frame.get("stakeholder") or specificity.get("primary_stakeholder") or "")
        )
        if primary.lower() not in {"", "клиент", "заказчик", "пользователь", "участник процесса"}:
            return primary
        return ""

    def _restore_case_section_spacing(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        value = re.sub(r"^\s*(Ситуация:\s*\*\*[^*]+\*\*)\s*", r"\1\n\n", value, count=1, flags=re.IGNORECASE)
        value = re.sub(r"\s*(\*\*Что известно\*\*)", r"\n\n\1", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*(\*\*Что ограничивает\*\*)", r"\n\n\1", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*(Что нужно сделать:)", r"\n\n\1", value, flags=re.IGNORECASE)
        value = re.sub(r"(\*\*Что известно\*\*)\s*[-•]", r"\1\n- ", value, flags=re.IGNORECASE)
        value = re.sub(r"(\*\*Что ограничивает\*\*)\s*[-•]", r"\1\n- ", value, flags=re.IGNORECASE)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    def _humanize_generated_case_language(self, text: str) -> str:
        result = str(text or "").strip()
        if not result:
            return ""
        replacements = (
            (r"(\d+),\s+(\d+)", r"\1,\2"),
            (r"(\d{1,2}):\s+(\d{2})", r"\1:\2"),
            (r"([0-9%])\s+(Проверить детали можно по)\b", r"\1. \2"),
            (r"([0-9%])\s+(Если ничего не сделать сейчас)\b", r"\1. \2"),
            (r"([0-9%])\s+(Одновременно внимания требуют)\b", r"\1. \2"),
            (r"\bи пишет, что\b", "и сообщает, что"),
            (r"\bне складываются в одну картину\b", "дают противоречивую картину"),
            (r"\bдругая часть предупреждает о рисках\b", "другая часть указывает на риски"),
            (r"\bа по нескольким вопросам данных все еще недостаточно\b", "а по нескольким вопросам данных пока недостаточно"),
            (r"\bв контуре рабочая группа участка\b", "на этом участке"),
            (r"\bв контуре команды ([^.,;\n]+)\b", r"в работе команды \1"),
            (r"\bнужно быстро принять решение по ситуации:\s*что\b", "нужно быстро решить, что"),
            (r"\bНужно быстро принять решение по ситуации\s+что\b", "Нужно быстро решить, что"),
            (r"\bпоследствия будут такими:\s*срыв\b", "последствия будут такими: возможен срыв"),
            (r"\bпоследствия будут такими:\s*перенос\b", "последствия будут такими: возможен перенос"),
            (r"\bпоследствия будут такими:\s*повторное согласование\b", "последствия будут такими: возможно повторное согласование"),
            (r"\bпоследствия будут такими:\s*ошибки\b", "последствия будут такими: возможны ошибки"),
            (r"\bна кону ([^.,;\n]+) на этом участке\b", r"на кону \1 на этом участке"),
        )
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        return result.strip()

    def _dedupe_case_text_repetitions(self, text: str, *, is_task: bool) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        value = re.sub(r"(?:Что нужно сделать:\s*){2,}", "Что нужно сделать: ", value, flags=re.IGNORECASE)
        value = re.sub(
            r"(?:^|\n)Сейчас в фокусе ситуация\s+«[^»]+»\.\s*",
            "\n",
            value,
            flags=re.IGNORECASE,
        )
        if is_task:
            value = re.sub(r"^(?:Что нужно сделать:\s*)+", "Что нужно сделать: ", value, flags=re.IGNORECASE)

        def _line_key(line: str) -> str:
            normalized = re.sub(r"\*\*", "", line or "")
            normalized = re.sub(r"[.:!?]+$", "", normalized.strip(), flags=re.IGNORECASE)
            return normalized.lower()

        def _value_signature(line: str) -> set[str]:
            payload = re.sub(r"^-\s*(?:Проверка идет по|Доступно|В фокусе):\s*", "", line, flags=re.IGNORECASE)
            payload = payload.replace(" и ", ", ")
            chunks = [
                re.sub(r"\s+", " ", chunk.strip().lower())
                for chunk in re.split(r",", payload)
                if chunk.strip()
            ]
            if chunks:
                return set(chunks)
            tokens = re.findall(r"[а-яёa-z0-9-]{4,}", payload.lower())
            return set(tokens)

        deduped_lines: list[str] = []
        seen_line_keys: set[str] = set()
        last_check_signature: set[str] = set()
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            key = _line_key(line)
            if key and key in seen_line_keys:
                continue
            if re.match(r"^-\s*Проверка идет по:", line, flags=re.IGNORECASE):
                last_check_signature = _value_signature(line)
            elif re.match(r"^-\s*Доступно:", line, flags=re.IGNORECASE):
                available_signature = _value_signature(line)
                if last_check_signature and available_signature:
                    overlap = len(last_check_signature & available_signature)
                    baseline = max(len(last_check_signature), len(available_signature), 1)
                    if overlap / baseline >= 0.6:
                        continue
            if key:
                seen_line_keys.add(key)
            deduped_lines.append(line)

        value = "\n".join(deduped_lines)

        normalized_rows: list[str] = []
        seen_sentence_keys: set[str] = set()
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            sentences = re.split(r"(?<=[.!?])\s+", line)
            deduped_sentences: list[str] = []
            for raw_sentence in sentences:
                sentence = raw_sentence.strip()
                if not sentence:
                    continue
                key = re.sub(r"\s+", " ", re.sub(r"[.:!?]+$", "", sentence)).strip().lower()
                if len(key) >= 18 and key in seen_sentence_keys:
                    continue
                if len(key) >= 18:
                    seen_sentence_keys.add(key)
                deduped_sentences.append(sentence)
            if deduped_sentences:
                normalized_rows.append(" ".join(deduped_sentences))

        value = "\n".join(normalized_rows) if normalized_rows else value
        value = re.sub(r"\s+\n", "\n", value)
        value = re.sub(r"\n\s+", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        value = re.sub(r"\s{2,}", " ", value)
        return value.strip()

    def _evaluate_user_case_quality(
        self,
        *,
        case_context: str,
        case_task: str,
        case_specificity: dict[str, Any] | None,
    ) -> dict[str, Any]:
        context = cleanup_case_text(case_context)
        task = cleanup_case_text(case_task)
        issues: list[str] = []
        specificity = dict(case_specificity or {})

        if not context or len(context) < 140:
            issues.append("context_too_short")
        if "{" in context or "}" in context or "{" in task or "}" in task:
            issues.append("placeholder_leak")
        if ".." in context or ". ." in context:
            issues.append("punctuation_noise")
        if any(re.search(pattern, context, flags=re.IGNORECASE) for pattern in CASE_TEXT_GENERIC_PATTERNS):
            issues.append("too_generic")

        problem_markers = [
            str(specificity.get("bottleneck") or "").strip(),
            str(specificity.get("business_impact") or "").strip(),
            str(specificity.get("primary_stakeholder") or "").strip(),
            str(specificity.get("critical_step") or "").strip(),
        ]
        matched_markers = 0
        lowered_context = context.lower()
        for marker in problem_markers:
            if marker and marker.lower() in lowered_context:
                matched_markers += 1
        if matched_markers < 2 and len(context) < 220:
            issues.append("not_specific_enough")

        if not any(word in lowered_context for word in ("риск", "огранич", "следующ", "срок", "этап", "шаг")):
            issues.append("missing_case_anchor")
        if not task or len(task) < 30:
            issues.append("task_too_short")

        return {
            "passed": not issues,
            "issues": issues,
        }

    def _rebuild_context_from_type(
        self,
        *,
        case_type_code: str | None,
        case_title: str,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        type_code = str(case_type_code or "").upper()
        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code=type_code,
                case_title=case_title,
                case_context="",
                case_task="",
            ),
        )
        if type_code not in {"F01", "F02", "F03", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"}:
            return ""
        if self._should_use_strict_scene_narrative(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            return str(
                self._build_strict_scene_narrative(
                    case_type_code=type_code,
                    case_specificity=specificity,
                ) or ""
            ).strip()
        if self._should_bypass_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            return str(
                self._apply_plot_skeleton(
                    "",
                    case_type_code=type_code,
                    case_title=case_title,
                    case_specificity=specificity,
                ) or ""
            ).strip()
        locked_context = self._build_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        )
        if locked_context:
            return locked_context.strip()
        return str(
            self._apply_plot_skeleton(
                "",
                case_type_code=type_code,
                case_title=case_title,
                case_specificity=specificity,
            ) or ""
        ).strip()

    def _diversify_case_context(
        self,
        text: str,
        *,
        case_type_code: str | None,
        case_title: str,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        current = (text or "").strip()
        if not current:
            return ""
        type_code = str(case_type_code or "").upper()
        title_source = str(case_title or "").lower()
        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code=type_code,
                case_title="",
                case_context=current,
                case_task="",
            ),
        )
        if self._should_use_strict_scene_narrative(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            strict = self._build_strict_scene_narrative(
                case_type_code=type_code,
                case_specificity=specificity,
            )
            return strict.strip() if strict else current
        title_specific_addition = ""
        if type_code == "F05":
            if any(word in title_source for word in ("роли", "состав", "групп")):
                title_specific_addition = (
                    "Здесь важно заранее договориться о ролях, спорных решениях и координации."
                )
            else:
                title_specific_addition = (
                    "Здесь нужно быстро разложить задачи по людям и не допустить провисания следующего шага."
                )
        elif type_code == "F08":
            if any(word in title_source for word in ("перегруз", "главного", "приоритет")):
                title_specific_addition = (
                    "Здесь нужно выбрать главный приоритет, потому что ошибка в первом действии задержит остальные задачи."
                )
            else:
                title_specific_addition = (
                    "Ключевая сложность в том, что задачи срочные по-разному, и первый выбор влияет на остальные."
                )
        additions = {
            "F05": "Важно не только распределить загрузку, но и договориться, кто держит контроль и когда команда возвращается с обновлением.",
            "F08": "Ошибка в приоритете здесь приведет к лишней задержке и повторной работе.",
            "F09": "Важно увидеть, на каком шаге процесса команда теряет время и где появляется повторная работа.",
            "F10": self._describe_current_idea(specificity),
            "F11": "Результат уже хотят передавать дальше, хотя критичный шаг проверки еще не закрыт.",
            "F12": "Разговор нужен, чтобы закрепить новый порядок действий и не повторить ту же ошибку.",
        }
        extra = str(title_specific_addition or additions.get(type_code) or "").strip()
        if not extra or extra in current:
            return current
        return f"{current} {extra}".strip()

    def _normalize_case_similarity_text(self, text: str) -> set[str]:
        cleaned = re.sub(r"[^a-zA-Zа-яА-Я0-9\s]", " ", str(text or "").lower())
        tokens = [token for token in cleaned.split() if len(token) > 2]
        stop_words = {
            "это", "как", "что", "где", "для", "при", "или", "уже", "нужно", "сейчас",
            "если", "часть", "этом", "такой", "когда", "после", "между", "чтобы",
            "будет", "также", "который", "которые", "процессу", "процессе",
        }
        return {token for token in tokens if token not in stop_words}

    def _case_text_similarity_score(self, left: str, right: str) -> float:
        left_tokens = self._normalize_case_similarity_text(left)
        right_tokens = self._normalize_case_similarity_text(right)
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = left_tokens & right_tokens
        union = left_tokens | right_tokens
        if not union:
            return 0.0
        return len(intersection) / len(union)

    def _case_text_is_too_similar(self, current: str, existing_contexts: list[str]) -> bool:
        current_clean = (current or "").strip()
        if not current_clean:
            return False
        current_head = current_clean[:180].lower()
        for previous in existing_contexts:
            prev_clean = (previous or "").strip()
            if not prev_clean:
                continue
            if current_head == prev_clean[:180].lower():
                return True
            if self._case_text_similarity_score(current_clean, prev_clean) >= 0.72:
                return True
        return False

    def _restore_minimum_case_context(
        self,
        text: str,
        *,
        case_type_code: str | None,
        case_title: str,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        current = (text or "").strip()
        type_code = str(case_type_code or "").upper()
        if not current:
            return current

        sentence_count = len([part for part in re.split(r"(?<=[.!?])\s+", current) if part.strip()])
        if sentence_count >= 3 and len(current) >= 220:
            return current

        specificity = self._normalize_case_specificity(
            case_specificity or {},
            self._fallback_case_specificity(
                position=None,
                duties=None,
                company_industry=None,
                role_name=None,
                user_profile=None,
                case_type_code=type_code,
                case_title=case_title,
                case_context=current,
                case_task="",
            ),
        )
        if type_code not in {"F01", "F02", "F03", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"}:
            return current
        if self._should_use_strict_scene_narrative(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            strict = self._build_strict_scene_narrative(
                case_type_code=type_code,
                case_specificity=specificity,
            )
            return strict.strip() or current
        if self._should_bypass_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        ):
            rebuilt = self._apply_plot_skeleton(
                current,
                case_type_code=type_code,
                case_title=case_title,
                case_specificity=specificity,
            ).strip()
            return rebuilt or current
        locked_context = self._build_template_locked_context(
            case_type_code=type_code,
            case_specificity=specificity,
        )
        if locked_context:
            return locked_context.strip()
        rebuilt = self._apply_plot_skeleton(
            current,
            case_type_code=type_code,
            case_title=case_title,
            case_specificity=specificity,
        ).strip()
        return rebuilt or current

    def _sanitize_user_case_text(self, text: str | None, *, role_name: str | None) -> str:
        result = str(text or "").strip()
        if not result:
            return ""

        human_role = self._humanize_role_name(role_name)
        role_phrase = f"в роли {human_role}"

        replacements = {
            "в роли Линейный сотрудник": role_phrase if human_role == "линейный сотрудник" else f"в роли {human_role}",
            "в роли линейный сотрудник": role_phrase if human_role == "линейный сотрудник" else f"в роли {human_role}",
            "в роли Менеджер": f"в роли {human_role}" if human_role == "менеджер" else role_phrase,
            "в роли Лидер": f"в роли {human_role}" if human_role == "лидер" else role_phrase,
            "в роли M": f"в роли {human_role}",
            "в роли L": f"в роли {human_role}",
            "в роли Leader": f"в роли {human_role}",
            "для M": "для управленческой роли",
            "для L": "для роли исполнителя",
            "для Leader": "для лидерской роли",
            "L/M": "роли пользователя",
            "часть работы действительно велась": "часть работы действительно была выполнена",
            "ему обещали вернуться с ответом": "ему обещали предоставить ответ",
            "к текущему моменту": "к настоящему моменту",
            "тем человеком, кому нужно первым ответить": "тем сотрудником, которому нужно первым ответить",
        }
        for source, target in replacements.items():
            result = result.replace(source, target)

        result = re.sub(r"\bесли\s+кейс\s+персонализирован\s+под\s+L\b.*?(?:[.!?]|$)", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bесли\s+под\s+M\b.*?(?:[.!?]|$)", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bесли\s+кейс\s+персонализирован\s+под\s+M\b.*?(?:[.!?]|$)", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдля\s+L\s*[—-]\s*[^.]+", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдля\s+M\s*[—-]\s*[^.]+", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдля\s+Leader\s*[—-]\s*[^.]+", "", result, flags=re.IGNORECASE)
        result = re.sub(
            r"(пишет,\s+что\s+по\s+вопросу\s+.+?)\s+(ему\s+обещали\s+(?:предоставить\s+ответ|вернуться\s+с\s+ответом))",
            r"\1, \2",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bпо\s+вопросу\s+([^.,!?]+?)\s+было\s+отмечено\s+как\s+выполненное\b",
            r"по вопросу «\1» было отмечено как выполненное",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"по вопросу «тикет «([^»]+)»", r"по вопросу «\1»", result, flags=re.IGNORECASE)
        result = re.sub(r"\bориентир\s+к\s+до\s+(\d{1,2}:\d{2})\b", r"ориентир до \1", result, flags=re.IGNORECASE)
        result = re.sub(r"««\s*", "«", result)
        result = re.sub(r"\s*»»", "»", result)
        result = re.sub(r"(?:,\s*|\s+)и\s+сейчас\.$", ".", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпоявилось\s+узкое\s+место\s+появилось\s+узкое\s+место\b", "появилось узкое место", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо\s+какой\s+показателях\b", "по каким показателям", result, flags=re.IGNORECASE)
        result = re.sub(r"(%|\bчас(?:ов|а)?|\bдней?|\bминут)\s+Основн(?:ая|ое)\s+проблем", r"\1. Основная проблем", result, flags=re.IGNORECASE)
        result = re.sub(
            r"В распоряжении команды сейчас\s+(?:2 специалиста\s+){2,}клиентской поддержки",
            "В распоряжении команды сейчас 2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"(?:\b2 специалиста\s+){3,}клиентской поддержки",
            "2 специалиста клиентской поддержки",
            result,
            flags=re.IGNORECASE,
        )

        result = re.sub(r"\bв роли\s+(?:L|M|Leader)\b", role_phrase, result, flags=re.IGNORECASE)
        result = re.sub(r"\b(изменений нет|нет изменений|нет измеенний|не изменилось|не изменений|без изменений)\b", human_role, result, flags=re.IGNORECASE)
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\n\s*\n+", "\n\n", result)
        result = re.sub(r"\.\.", ".", result)
        result = re.sub(r"\s+([,.;:!?])", r"\1", result)
        result = self._apply_case_prompt_grammar_rules(result)
        if result:
            result = result[0].upper() + result[1:]
        return result.strip()

    def _polish_user_case_context(
        self,
        text: str,
        *,
        role_name: str | None,
        case_title: str,
        company_industry: str | None,
    ) -> str:
        result = (text or "").strip()
        if not result:
            return ""

        human_role = self._humanize_role_name(role_name)
        replacements = {
            "Вы работаете в роли": "Вы работаете как",
            "и участвуете в процессе": "и участвуете в работе по",
            "пишет, что": "сообщает, что",
            "теряет доверие к вашей стороне": "теряет доверие к вашей команде",
            "У вас есть доступ": "У вас есть доступ",
            "Сейчас именно вы оказались тем сотрудником": "Сейчас именно вам нужно",
            "кому нужно первым ответить на жалобу": "первым ответить на жалобу",
            "инициатор запроса": "клиент",
            "карточке тикета": "внутренней карточке обращения",
            "карточке запроса": "внутренней карточке обращения",
        }
        for source, target in replacements.items():
            result = result.replace(source, target)

        result = re.sub(r"\bв контуре\s+операционн(?:ая|ой)\s+команд[аы]\b", "в группе операционного сопровождения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв контуре\s+([^,.]+?)\s+команд[аы]\b", r"в команде \1", result, flags=re.IGNORECASE)
        result = re.sub(r"\bнужно выполнить обработка\b", "нужно выполнить обработку", result, flags=re.IGNORECASE)
        result = re.sub(r"\bриски нарушение\b", "риски нарушения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bнеполные входные данные и ограничения работа\b", "неполные входные данные и ограничения по работе", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкак\s+линейного\s+сотрудника\b", "как линейный сотрудник", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкак\s+менеджера\b", "как менеджер", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкак\s+лидера\b", "как лидер", result, flags=re.IGNORECASE)
        result = result.replace("ограничения по работе по скриптам", "обязательная работа по скриптам")
        result = re.sub(r"\bклиенты написал\b", "клиент написал", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка обращения\b", "карточке обращения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка задачи\b", "карточке задачи", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка заявки,\s*истори(?:й|и)\s+комментариев\s+и\s+статус(?:а|у)\s+в\s+Service\s+Desk\b", "карточке заявки, истории комментариев и статусу в Service Desk", result, flags=re.IGNORECASE)
        result = re.sub(r"\bистория комментариев и база требований\b", "истории комментариев и базе требований", result, flags=re.IGNORECASE)
        result = re.sub(r"\bиз\s+ваша\s+смена\s+поддержки\s+и\s+вторая\s+линия\b", "из вашей смены поддержки и второй линии", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдоступный\s+сотрудник\s+и\s+ограниченное\s+рабочее\s+время\b", "два сотрудника и ограниченное время смены", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо\s+каналу\s+очередь\s+обращений\s+и\s+служебный\s+чат\s+смены\b", "через очередь обращений и служебный чат смены", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо\s+каналу\s+очередь\s+задач\s+и\s+комментарии\s+в\s+jira\b", "в комментариях к задаче в Jira", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв\s+процессе\s+подготовка\s+требований\b", "в процессе подготовки требований", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкоманда\s+второй\s+линии\s+поддержки\b", "смежная команда второй линии поддержки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+срыв\s+sla\b", "по вопросу срыва SLA", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+неверная\s+трактовка\s+требований\b", "по вопросу неверной трактовки требований", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bпо вопросу\s+подтверждение статуса судовой операции и следующего шага экипажа\b",
            "по вопросу подтверждения статуса судовой операции и следующего шага экипажа",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bизвестно о\s+неполная запись следующего маневра в судовом журнале\b",
            "известно о неполной записи следующего маневра в судовом журнале",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bв процесс вовлечены\s+вахта «Браво» и старший помощник\b",
            "в процесс вовлечены вахта «Браво» и старший помощник капитана",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bпо его словам,\s+обращение\s+по вопросу\s+неверной\s+трактовки\s+требований\s+было\s+отмечено\s+как\s+выполненное,\s+но\s+нужный\s+результат\s+он\s+так\s+и\s+не\s+получил\b",
            "По его словам, задача уже отмечена как выполненная, но согласованного ТЗ и финального результата он так и не получил",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bчерез\s+в\s+комментариях\b", "в комментариях", result, flags=re.IGNORECASE)
        result = re.sub(r"\bограничения\s+закрытию\s+заявок\b", "ограничения по закрытию заявок", result, flags=re.IGNORECASE)
        result = re.sub(r"\bесть\s+закрытию\s+заявок\b", "есть ограничения по закрытию заявок", result, flags=re.IGNORECASE)
        result = re.sub(r"\bошибок в процессе обслуживание гостей и работа бара\b", "ошибок в процессе обслуживания гостей и работы бара", result, flags=re.IGNORECASE)
        result = re.sub(r"\bможет привести к обслуживание гостей и работа бара\b", "может привести к сбоям в обслуживании гостей и работе бара", result, flags=re.IGNORECASE)
        result = re.sub(r"\bна\s+показателях\b", "на показатели", result, flags=re.IGNORECASE)
        result = re.sub(r"\bдополнительные\s+срыва\s+сроков\b", "дополнительным срывам сроков", result, flags=re.IGNORECASE)
        result = re.sub(r"\bЭто\s+касается\s+вечерняя\s+смена\b", "Это касается вечерней смены", result, flags=re.IGNORECASE)
        result = re.sub(r"\bЭто\s+касается\s+линия\b", "Это касается линии", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв\s+процессе\s+поддержка\s+рабочих\s+мест\s+и\s+заявок\s+пользователей\b", "в процессе поддержки рабочих мест и заявок пользователей", result, flags=re.IGNORECASE)
        result = re.sub(r"\bможет\s+привести\s+к\s+поддержка\s+рабочих\s+мест\s+и\s+обработка\s+заявок\s+пользователей\b", "может привести к сбоям в поддержке рабочих мест и обработке заявок пользователей", result, flags=re.IGNORECASE)
        result = re.sub(r"\bВ этом контуре уже вовлечены\b", "В распределении работы уже участвуют", result, flags=re.IGNORECASE)
        result = re.sub(r"\bПо ситуации уже вовлечены\b", "В согласовании по этой ситуации уже участвуют", result, flags=re.IGNORECASE)
        result = re.sub(r"\bНа этот участок уже смотрят\b", "На результаты этого участка уже ориентируются", result, flags=re.IGNORECASE)
        result = re.sub(r"\bо\s+пользователях/клиентах\s+пользователь\b", "о пользователях и клиентах", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпользователях/клиентах\s+пользователь\b", "пользователях и клиентах", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв системе видно,\s+что статус обращения уже изменён\b", "В системе видно, что статус обращения уже изменён", result, flags=re.IGNORECASE)
        result = re.sub(r"\bметрике\s+время\s+обработки\b", "метрике времени обработки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bот\s+смежная\s+команда\s+второй\s+линии\s+поддержки\b", "от смежной команды второй линии поддержки", result, flags=re.IGNORECASE)
        result = re.sub(r"\bинцидент\s+типа\s+некорректное\s+закрытие\s+обращения\b", "инцидент, связанный с некорректным закрытием обращения", result, flags=re.IGNORECASE)
        result = re.sub(r"\bповторная\s+жалоба\s+клиента\s+и\s+задержка\s+следующего\s+шага\s+по\s+обращению\b", "повторная жалоба клиента и задержка следующего шага по обращению", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо вопросу\s+обращение\s+закрывается\s+по\s+статусу\s+раньше,?\s+чем\s+клиент\s+действительно\s+получает\s+решение\b", "потому что обращения закрываются по статусу раньше, чем клиент действительно получает решение", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bПоведение\s+(.+?)\s+повторяется\s+и\s+уже\s+влияет\s+на\b",
            r"Проблема повторяется: \1. Это уже влияет на",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bНужно\s+назвать\s+факты,\s+услышать\s+собеседника,\s+согласовать\s+план\s+развития\s+на\s+([^,]+),\s+определить\s+([^,]+?)\s+и\s+зафиксировать\b",
            r"Нужно назвать факты, услышать собеседника и согласовать план развития. Контрольную точку стоит назначить на \1. Отдельно нужно определить, кто именно отвечает за следующие действия. Учитывайте текущий состав: \2. Договоренности важно зафиксировать",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"\bУчитывайте\s+текущий\s+состав:\s+3\s+человека\s+на\s+мостике\s+и\s+старший\s+помощник\s+капитана\s+на\s+подтверждении\s+и\s+зафиксировать\b",
            "Учитывайте текущий состав: 3 человека на мостике и старший помощник капитана на подтверждении. Договоренности важно зафиксировать",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\bот вас ожидают короткий постмортем по локальному инциденту: что случилось, какие вероятные причины лежат в основе, какие меры нужно принять сейчас и что поменять, чтобы это не повторилось\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bлинейная роль здесь валидна только на локальном уровне\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bлинейная роль здесь валидна только как координация мини-группы\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bлинейная роль не должна брать на себя изменение внешних обязательств, чужих приоритетов или финальных сроков за пределами своего мандата\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bу линейной роли нет права угрожать санкциями, менять чужие приоритеты или обещать решения за руководителя\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bхороший ответ должен показывать рабочий способ договориться и при необходимости корректно эскалировать вопрос\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bхороший ответ должен показать реалистичный план, а не формальное распределение «всем поровну»\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bможно опираться на факты, обозначать влияние, предлагать правила взаимодействия и при необходимости зафиксировать, что следующий шаг — эскалация по правилу\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпри нехватке данных нужно уточнять и при необходимости эскалировать, а не домысливать или обещать лишнее\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв разбор уже входят конкретные элементы:\b", "Для разбора уже доступны конкретные материалы:", result, flags=re.IGNORECASE)
        result = re.sub(r"\bв работе уже есть конкретные задачи:\b", "Сейчас в работе уже есть конкретные задачи:", result, flags=re.IGNORECASE)
        result = re.sub(r"\bсейчас нужно провести личный разговор так, чтобы не сорваться в обвинения, сохранить рабочие отношения и добиться ясной договорённости\b", "Сейчас важно провести разговор спокойно, сохранить рабочие отношения и прийти к ясной договоренности", result, flags=re.IGNORECASE)
        result = re.sub(r"\bОпирайтесь на факты, обозначайте влияние и предлагайте понятный следующий шаг\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bДля разговора уже есть конкретный контекст:\b", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bСейчас важно провести разговор спокойно, сохранить рабочие отношения и прийти к ясной договоренности\b\.?", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\bСитуация:\s*", "", result, flags=re.IGNORECASE)

        result = re.sub(r"^вы\s+работаете\s+как\s+(?:линейный\s+сотрудник|менеджер|лидер)\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"^вы\s+работаете\s+(?:линейным\s+сотрудником|менеджером|лидером)\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"^вы\s*—\s*(?:линейный\s+сотрудник|менеджер|лидер)\.?\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"^\s*и\s+отвечаете\s+за\s+[^.]+?\.\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\.\s*и\s+отвечаете\s+за\s+[^.]+?\.\s*", ". ", result, flags=re.IGNORECASE)

        result = re.sub(r"\bименно вам нужно первым ответить на жалобу\b", "вам нужно первым ответить клиенту", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпервого ответа клиенту\b", "первого ответа заказчику", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпервым ответить клиенту\b", "первым ответить заказчику", result, flags=re.IGNORECASE)
        result = re.sub(r"\bчасть работы действительно была выполнена, однако клиент этого не видит\b", "часть работы уже выполнена, но клиент этого не видит", result, flags=re.IGNORECASE)
        result = re.sub(r"\bследующий шаг нигде явно не зафиксирован\b", "следующий шаг нигде явно не зафиксирован", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо его обращению обещали вернуться с ответом\b", "по его обращению обещали дать ответ", result, flags=re.IGNORECASE)
        result = re.sub(r"\bэтого не произошло\b", "этого не случилось", result, flags=re.IGNORECASE)
        result = re.sub(r"\bпо внутренней карточке обращения видно\b", "Во внутренней карточке обращения видно", result, flags=re.IGNORECASE)
        result = re.sub(r"\bно клиент этого не видит\b", "но клиент об этом не знает", result, flags=re.IGNORECASE)
        result = re.sub(r"\bа следующий шаг по обращению нигде явно не зафиксирован\b", "а следующий шаг по обращению нигде явно не зафиксирован", result, flags=re.IGNORECASE)
        result = re.sub(
            r"\bЗадержки в обработке обращений напрямую влияют на рабочие процессы клиентов\.\s*",
            "",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"([.!?])\s*,\s*работающ(?:ий|ая|ее|его|ему|ем)\s+[^.]+?\.",
            r"\1",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(
            r"^\s*,\s*работающ(?:ий|ая|ее|его|ему|ем)\s+[^.]+?\.\s*",
            "",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"([^.]{170,}?),\s+но\s+", r"\1. Но ", result)
        result = re.sub(r"([^.]{170,}?),\s+а\s+", r"\1. А ", result)
        result = re.sub(r"([^.]{170,}?),\s+и\s+при\s+этом\s+", r"\1. При этом ", result, flags=re.IGNORECASE)
        result = re.sub(r"\bПри этом цена ошибки уже заметна, но\.", "При этом цена ошибки уже заметна.", result, flags=re.IGNORECASE)
        result = re.sub(r"\.\s*,", ".", result)
        result = re.sub(r"\.\s+\.", ".", result)
        result = re.sub(r"\s{2,}", " ", result).strip()
        if result and result[-1] not in ".!?":
            result += "."
        return result

    def _get_case_text_build_instruction(self, case_type_code: str | None) -> dict[str, Any] | None:
        code = str(case_type_code or "").strip().upper()
        cache_key = code or "*"
        if cache_key in self._case_text_build_instruction_cache:
            return self._case_text_build_instruction_cache[cache_key]
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
                    SELECT instruction_code, instruction_name, applies_to_type_code, structure_mode,
                           instruction_text, priority, version
                    FROM case_text_build_instructions
                    WHERE is_active = TRUE
                      AND (applies_to_type_code = %s OR applies_to_type_code IS NULL)
                    ORDER BY
                        CASE WHEN applies_to_type_code = %s THEN 0 ELSE 1 END,
                        priority ASC,
                        version DESC
                    LIMIT 1
                    """,
                    (code or None, code or None),
                ).fetchone()
        except Exception:
            row = None
        instruction = dict(row) if row else None
        self._case_text_build_instruction_cache[cache_key] = instruction
        return instruction

    def _get_case_template_requirements(self, case_type_code: str | None) -> dict[str, Any]:
        return {}

    def _build_template_contract(self, *, case_type_code: str | None, case_specificity: dict[str, Any] | None) -> dict[str, str]:
        specificity = dict(case_specificity or {})
        frame = dict(specificity.get("_case_frame") or {})
        requirements = self._get_case_template_requirements(case_type_code)
        operation = cleanup_case_text(str(specificity.get("critical_step") or frame.get("expected_step") or ""))
        regulation = cleanup_case_text(
            self._normalize_case_frame_source(str(specificity.get("source_of_truth") or frame.get("source_of_truth") or ""))
        )
        deviation = cleanup_case_text(str(frame.get("problem_event") or specificity.get("bottleneck") or ""))
        risk = cleanup_case_text(self._normalize_risk_phrase(str(frame.get("risk") or specificity.get("business_impact") or "")))
        authority_limit = cleanup_case_text(str(frame.get("constraint") or specificity.get("resource_profile") or ""))
        escalation_target = cleanup_case_text(self._select_escalation_target(
            str(frame.get("stakeholder") or specificity.get("primary_stakeholder") or ""),
            specificity.get("adjacent_team"),
        ))
        channel = cleanup_case_text(self._normalize_channel_phrase(str(specificity.get("channel") or "")))
        deadline = cleanup_case_text(self._normalize_deadline_phrase(str(frame.get("deadline") or specificity.get("deadline") or "")))
        expected_step = cleanup_case_text(str(frame.get("expected_step") or specificity.get("critical_step") or ""))
        contract = {
            "operation": operation,
            "regulation": regulation,
            "deviation": deviation,
            "risk": risk,
            "authority_limit": authority_limit,
            "escalation_target": escalation_target,
            "channel": channel,
            "deadline": deadline,
            "expected_step": expected_step,
            "problem_event": deviation,
            "constraint": authority_limit,
            "required_task_text": str(requirements.get("required_task_text") or "").strip(),
            "required_task_style": str(requirements.get("required_task_style") or "").strip(),
        }
        return {key: cleanup_case_text(str(value or "")) for key, value in contract.items()}

    def _build_user_visible_case_task(
        self,
        *,
        case_type_code: str | None,
        context_text: str,
        case_title: str,
    ) -> str:
        requirements = self._get_case_template_requirements(case_type_code)
        task_style = str(requirements.get("task_style") or "").strip().lower()
        if not task_style:
            instruction = self._get_case_text_build_instruction(case_type_code)
            task_style = str((instruction or {}).get("structure_mode") or "").strip().lower()
        if not task_style:
            task_style = {
                "F01": "answer_message",
                "F02": "clarification",
                "F03": "conversation",
                "F04": "alignment_action",
                "F05": "coordination_plan",
                "F06": "message_or_ticket",
                "F07": "structured_decision",
                "F08": "prioritization",
                "F09": "improvement_ideas",
                "F10": "idea_evaluation",
                "F11": "message_or_ticket",
                "F12": "development_conversation",
            }.get(str(case_type_code or "").strip().upper(), "")
        lower_context = f"{case_title} {context_text}".lower()
        if task_style == "answer_message" and "заказчик" in lower_context and any(word in lower_context for word in ("jira", "тз", "разработ", "проект")):
            return "Как вы ответите заказчику в этой ситуации?"
        return self._build_user_visible_task_from_style(task_style=task_style)

    def _build_user_visible_task_from_style(self, *, task_style: str) -> str:
        style = str(task_style or "").strip().lower()
        mapping = {
            "answer_message": "Как вы ответите в этой ситуации?",
            "clarification": "Что вы сделаете, чтобы уточнить запрос и зафиксировать понимание задачи?",
            "conversation": "Как вы проведете этот разговор и о чем договоритесь по его итогам?",
            "alignment_action": "Как вы будете согласовывать следующий шаг в этой ситуации?",
            "coordination_plan": "Как вы организуете работу команды в этой ситуации?",
            "structured_decision": "Какое решение вы примете в этой ситуации и что будете проверять дальше?",
            "prioritization": "Что вы сделаете в первую очередь и почему?",
            "improvement_ideas": "Какие улучшения вы предложите для этой ситуации?",
            "idea_evaluation": "Как вы оцените эту идею и какое решение по ней примете?",
            "message_or_ticket": "Как вы будете действовать перед передачей работы дальше?",
            "development_conversation": "Как вы проведете эту развивающую беседу?",
        }
        return mapping.get(style) or "Что вы будете делать в этой ситуации?"

    def _polish_user_case_task(self, text: str, *, case_title: str, context_text: str, case_type_code: str | None = None) -> str:
        result = (text or "").strip()
        if not result:
            result = ""
        type_code = str(case_type_code or "").strip().upper()
        requirements = self._get_case_template_requirements(type_code)
        required_task_text = str(requirements.get("required_task_text") or "").strip()
        user_visible_task = self._build_user_visible_case_task(
            case_type_code=type_code,
            context_text=context_text,
            case_title=case_title,
        )
        generic_task_markers = {
            "как вы ответите?",
            "как вы будете действовать?",
            "что вы сделаете в первую очередь и почему?",
            "составьте рабочий план действий.",
            "предложите решение.",
            "разберите проблему и предложите, что нужно сделать сейчас и что изменить, чтобы она не повторилась.",
        }
        if (
            required_task_text
            and type_code in {"F01", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"}
            and (not result or len(result) < 70 or result.strip().lower() in generic_task_markers)
        ):
            return user_visible_task
        if result == required_task_text:
            return user_visible_task
        if result and len(result) >= 70:
            return result
        lower_context = f"{case_title} {context_text} {result}".lower()
        if type_code in {"F07", "F09", "F10", "F12"} and user_visible_task:
            return user_visible_task
        if (
            any(actor in lower_context for actor in ("клиент", "заказчик"))
            and any(
                phrase in lower_context
                for phrase in (
                    "ответ клиент",
                    "ответить клиент",
                    "сообщение клиент",
                    "письмо клиент",
                    "первого ответа",
                    "первым ответить клиенту",
                    "ответ заказчик",
                    "ответить заказчик",
                    "сообщение заказчик",
                    "письмо заказчик",
                    "жалоб",
                    "комментариях к задаче",
                    "чат поддержки",
                )
            )
            and not any(word in lower_context for word in ("разговор", "бесед", "коллег", "личный разговор"))
        ):
            if "заказчик" in lower_context and any(word in lower_context for word in ("jira", "тз", "требован", "разработ")):
                return "Как вы ответите заказчику в этой ситуации?"
            return "Как вы ответите в этой ситуации?"
        if any(word in lower_context for word in ("выбор действия", "противоречив", "неопределен", "неопределён", "неполных данных")):
            return "Какое решение вы примете в этой ситуации и что будете проверять дальше?"
        if any(word in lower_context for word in ("приоритизац", "что делать в первую очередь", "главное", "конфликт срочности", "перегруз")):
            return "Что вы сделаете в первую очередь и почему?"
        if any(word in lower_context for word in ("разговор", "бесед", "коллег", "развивающ", "личный разговор")):
            return "Как вы проведете этот разговор и о чем договоритесь по его итогам?"
        if any(word in lower_context for word in ("согласован", "смежн", "эскалац", "инцидент", "сбой")):
            return "Как вы будете действовать в этой ситуации?"
        if any(word in lower_context for word in ("план", "распредел", "команд", "групп", "смен", "координац", "роли")):
            return "Как вы организуете работу команды в этой ситуации?"
        if any(word in lower_context for word in ("иде", "вариант", "решени", "гипотез")):
            return user_visible_task
        return user_visible_task

    def _build_structured_user_case_context(
        self,
        *,
        context_text: str,
        case_specificity: dict[str, Any] | None = None,
    ) -> str:
        context_text = (context_text or "").strip()
        if not context_text:
            return ""
        context_text = self._merge_supporting_case_sections_into_intro(context_text)
        context_text = re.sub(r"^\s*Ситуация:\s*", "", context_text, flags=re.IGNORECASE)
        context_text = re.split(
            r"\s*\*\*(?:Что известно|Что ограничивает)\*\*[.:]?"
            r"|\s*Что нужно сделать:\s*",
            context_text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        specificity = dict(case_specificity or {})
        case_frame = dict(specificity.get("_case_frame") or {})
        case_title = str(specificity.get("_case_title") or "")
        problem_event = cleanup_case_text(str(case_frame.get("problem_event") or ""))
        work_object = cleanup_case_text(str(case_frame.get("work_object") or ""))
        incident_title = self._normalize_incident_title(str(case_frame.get("incident_title") or ""))
        type_code = str(specificity.get("_case_type_code") or "").upper()
        template_title = self._compose_incident_title_from_template_and_specificity(
            case_type_code=type_code,
            case_title=case_title,
            specificity=specificity,
            case_frame=case_frame,
        )
        if template_title and type_code in {"F02", "F03", "F05", "F09", "F10", "F11"}:
            incident_title = template_title
        if not incident_title:
            if problem_event:
                incident_title = self._normalize_incident_title(problem_event)
            elif work_object:
                incident_title = self._normalize_incident_title(f"Проблема вокруг {work_object}")
            else:
                incident_title = "Рабочая ситуация требует решения"
        if incident_title:
            title_patterns = [
                rf"^(?:\*\*{re.escape(incident_title)}\*\*\.?\s*)+",
                rf"^(?:{re.escape(incident_title)}\.?\s*)+",
            ]
            for pattern in title_patterns:
                context_text = re.sub(pattern, "", context_text.strip(), flags=re.IGNORECASE).strip()
        deadline = cleanup_case_text(
            self._normalize_deadline_phrase(str(case_frame.get("deadline") or specificity.get("deadline") or ""))
        )
        participant = self._select_primary_actor(
            str(case_frame.get("stakeholder") or specificity.get("primary_stakeholder") or ""),
            grammatical_case="nominative",
        )
        expected_step = cleanup_case_text(str(case_frame.get("expected_step") or specificity.get("critical_step") or ""))
        risk = cleanup_case_text(str(case_frame.get("risk") or specificity.get("business_impact") or ""))
        constraint = cleanup_case_text(str(case_frame.get("constraint") or ""))
        artifacts = cleanup_case_list(case_frame.get("artifacts") or [], limit=3)
        systems = cleanup_case_list(case_frame.get("systems") or [], limit=2)
        known_facts = cleanup_case_list(case_frame.get("known_facts") or [], limit=3)
        normalized_source_fact = self._normalize_case_frame_source(str(case_frame.get("source_of_truth") or ""))
        lowered_context_text = context_text.lower()
        if normalized_source_fact:
            filtered_known_facts: list[str] = []
            source_tokens = set(re.findall(r"[а-яёa-z0-9-]{4,}", normalized_source_fact.lower()))
            for fact in known_facts:
                fact_text = self._strip_metrics_from_fact(str(fact or ""))
                if not fact_text:
                    continue
                fact_text = re.sub(r"(\d+),\s+(\d+)", r"\1,\2", fact_text)
                if re.search(r"^в работе уже фигурируют", fact_text, flags=re.IGNORECASE):
                    continue
                if re.search(r"проверк\w*\s+ид[её]т\s+по", fact_text, flags=re.IGNORECASE):
                    continue
                fact_tokens = set(re.findall(r"[а-яёa-z0-9-]{4,}", fact_text.lower()))
                overlap = len(source_tokens & fact_tokens)
                if source_tokens and fact_tokens and overlap / max(len(source_tokens), 1) >= 0.5:
                    continue
                filtered_known_facts.append(fact_text)
            known_facts = filtered_known_facts[:3]

        sections: list[str] = []
        if incident_title:
            sections.append(f"Ситуация: **{incident_title}**")
        else:
            sections.append("Ситуация:")
        sections.append(context_text.strip())
        return "\n\n".join(part.strip() for part in sections if part.strip())

    def _merge_supporting_case_sections_into_intro(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""
        if not re.search(r"\*\*(?:Что известно|Что ограничивает)\*\*", value, flags=re.IGNORECASE):
            return value

        title_match = re.match(r"^\s*Ситуация:\s*\*\*([^*]+)\*\*\s*", value, flags=re.IGNORECASE)
        title = cleanup_case_text(title_match.group(1)) if title_match else ""
        body = value[title_match.end():].strip() if title_match else value
        intro = re.split(
            r"\n\s*\*\*(?:Что известно|Что ограничивает)\*\*|\n\s*Что нужно сделать:",
            body,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

        known_match = re.search(
            r"\*\*Что известно\*\*\s*(.*?)(?=(?:\n\s*\*\*Что ограничивает\*\*|\n\s*Что нужно сделать:|$))",
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        limits_match = re.search(
            r"\*\*Что ограничивает\*\*\s*(.*?)(?=(?:\n\s*Что нужно сделать:|$))",
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )

        def _extract_items(block_text: str | None) -> list[str]:
            raw = str(block_text or "").strip()
            if not raw:
                return []
            items: list[str] = []
            for line in raw.splitlines():
                cleaned = cleanup_case_text(re.sub(r"^[-•]\s*", "", line.strip()))
                if cleaned:
                    items.append(cleaned)
            if items:
                return items
            return [cleanup_case_text(part) for part in re.split(r"(?<=[.!?])\s+", raw) if cleanup_case_text(part)]

        def _sentenceize(item: str) -> str:
            sentence = cleanup_case_text(item)
            if not sentence:
                return ""
            sentence = re.sub(r"^(?:Риск:\s*)", "Главный риск — ", sentence, flags=re.IGNORECASE)
            sentence = re.sub(r"^(?:В фокусе:\s*)", "Сейчас в фокусе ", sentence, flags=re.IGNORECASE)
            sentence = re.sub(r"^(?:Доступно:\s*)", "Проверить детали можно через ", sentence, flags=re.IGNORECASE)
            if sentence and sentence[-1] not in ".!?":
                sentence += "."
            return sentence

        intro_lower = intro.lower()
        support_sentences: list[str] = []
        for item in _extract_items(known_match.group(1) if known_match else "")[:2]:
            sentence = _sentenceize(item)
            if sentence and sentence.lower() not in intro_lower:
                support_sentences.append(sentence)
        for item in _extract_items(limits_match.group(1) if limits_match else "")[:2]:
            sentence = _sentenceize(item)
            if sentence and sentence.lower() not in intro_lower:
                support_sentences.append(sentence)

        flattened_intro = " ".join(part for part in [intro, *support_sentences] if part).strip()
        flattened_intro = re.sub(r"\s{2,}", " ", flattened_intro)
        if title:
            return f"Ситуация: **{title}**\n\n{flattened_intro}".strip()
        return flattened_intro.strip()

    def _should_use_strict_scene_narrative(
        self,
        *,
        case_type_code: str | None,
        case_specificity: dict[str, Any] | None,
    ) -> bool:
        type_code = str(case_type_code or "").upper()
        if type_code not in {"F01", "F02", "F03", "F04", "F05", "F07", "F08", "F09", "F10", "F11", "F12"}:
            return False
        family = self._infer_specificity_domain_family(case_specificity or {})
        return family in {"learning_and_development", "client_service", "engineering", "it_support"}

    def _should_prefer_template_context(
        self,
        *,
        case_type_code: str | None,
        case_specificity: dict[str, Any] | None,
    ) -> bool:
        type_code = str(case_type_code or "").upper()
        requirements = self._get_case_template_requirements(type_code)
        if requirements:
            prefer = requirements.get("prefer_template_context")
            if prefer is not None:
                family = self._infer_specificity_domain_family(case_specificity or {})
                return bool(prefer) and family in {"learning_and_development", "client_service", "engineering", "it_support"}
        return False

    def _build_strict_scene_narrative(
        self,
        *,
        case_type_code: str | None,
        case_specificity: dict[str, Any] | None,
    ) -> str:
        specificity = dict(case_specificity or {})
        frame = self._build_specificity_case_frame(specificity)
        if not frame:
            return ""
        type_code = str(case_type_code or "").upper()
        contract = self._build_template_contract(case_type_code=type_code, case_specificity=specificity)
        problem = self._normalize_case_frame_problem(
            str(frame.get("problem_event") or ""),
            fallback=str(frame.get("work_object") or "рабочий вопрос"),
        )
        problem = self._clarify_status_subject(problem)
        state = self._shorten_state_for_narrative(str(frame.get("current_state_inline") or frame.get("current_state") or ""))
        source = self._normalize_case_frame_source(str(frame.get("source_of_truth") or ""))
        work_items = self._normalize_case_frame_focus(str(frame.get("work_items") or frame.get("work_object") or ""))
        state_sentence = (
            self._rewrite_generic_case_state(
                case_type_code=type_code,
                state_text=state,
                work_items=work_items,
                source_text=source,
            )
            if self._is_generic_case_state(state)
            else state
        )
        risk = cleanup_case_text(str(frame.get("risk") or ""))
        constraint = cleanup_case_text(str(frame.get("constraint") or ""))
        expected = cleanup_case_text(str(frame.get("expected_step") or ""))
        stakeholder = self._select_primary_actor(
            str(frame.get("stakeholder") or frame.get("participants") or "участник процесса"),
            grammatical_case="nominative",
        )
        if stakeholder.lower() == "участник процесса" and str(frame.get("participants") or "").strip():
            stakeholder = self._select_primary_actor(str(frame.get("participants") or "участник процесса"), grammatical_case="nominative")
        stakeholder = self._normalize_user_visible_participant_phrase(stakeholder)
        source_sentence = f"Проверить детали можно по {source}." if source else ""
        focus_sentence = f"Сейчас в фокусе {work_items}." if work_items else ""
        risk_sentence = self._build_risk_sentence(risk, prefix="Если ничего не сделать сейчас,")
        constraint_sentence = f"При этом {constraint}." if constraint else ""
        deadline = cleanup_case_text(contract.get("deadline") or self._normalize_deadline_phrase(str(frame.get("deadline") or specificity.get("deadline") or "")))
        resource_profile = self._normalize_resource_sentence(str(specificity.get("resource_profile") or ""))
        idea_label = cleanup_case_text(str(specificity.get("idea_label") or ""))
        idea_description = cleanup_case_text(str(specificity.get("idea_description") or self._describe_current_idea(specificity) or ""))
        scope_sentence = self._render_case_scope_sentence(str(specificity.get("workflow_label") or work_items or frame.get("workflow") or ""))

        if type_code == "F01":
            blocked_step = cleanup_case_text(str(frame.get("expected_step") or specificity.get("critical_step") or ""))
            deadline_sentence = f"Клиенту обещали вернуться с ответом {deadline}, но к этому моменту он не получил ни решения, ни внятного обновления статуса." if deadline else ""
            blocked_step_sentence = (
                "Из-за этого клиент не может вовремя двигаться дальше и не понимает, кто отвечает за следующий шаг."
                if blocked_step
                else ""
            )
            parts = [
                f"По жалобе проблема выглядит так: {problem}.",
                deadline_sentence,
                state_sentence,
                blocked_step_sentence,
                source_sentence,
                "Внутри часть работы уже велась, но клиент этого не видит, а следующий шаг внутри команды явно не зафиксирован.",
                "Сейчас вам нужно первым ответить клиенту, прояснить факты и зафиксировать следующий шаг.",
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F02":
            clarification_sentence = (
                "Сейчас важно уточнить входные данные, критерии результата и следующий шаг."
                if expected.lower().startswith("уточнение ")
                else "Сейчас важно уточнить критерии результата, владельца следующего шага и границы задачи."
            )
            parts = [
                f"По этой ситуации в команду пришел слишком общий запрос: {problem}.",
                state_sentence,
                source_sentence,
                "Пока неясно, что именно считать готовым результатом, на какие данные нужно опираться и что можно оставить за рамками.",
                "Если не уточнить картину сейчас, команда может начать работу в неверной рамке и пообещать больше, чем реально подтверждено.",
                clarification_sentence,
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F04":
            parts = [
                f"Нужно быстро согласовать рамку работы по ситуации: {problem}.",
                state_sentence,
                "Важно договориться о минимально достаточном результате, ролях сторон и следующем шаге.",
                constraint_sentence,
                scope_sentence,
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F05":
            coordination_anchor = cleanup_case_text(contract.get("expected_step") or expected)
            resource_sentence = ""
            if resource_profile:
                if resource_profile.strip().lower().startswith(("в распоряжении", "в доступе", "доступно", "на смене", "в команде")):
                    resource_sentence = resource_profile if resource_profile.endswith(".") else f"{resource_profile}."
                else:
                    resource_sentence = f"В распоряжении команды сейчас {resource_profile}."
            deadline_sentence = f"Срок по этой координации ограничен: {deadline}." if deadline else ""
            parts = [
                f"Команде нужно скоординировать работу по ситуации: {problem}.",
                resource_sentence,
                deadline_sentence,
                state_sentence,
                (f"Сейчас важно закрепить, кто отвечает за шаг «{coordination_anchor}»." if coordination_anchor else "Сейчас важно закрепить роли и следующий шаг."),
                "Если не распределить роли и порядок работы явно, часть задач может провиснуть или задублироваться.",
                "Нужно сразу договориться, кто держит контроль и как команда возвращается с обновлением.",
                scope_sentence,
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F07":
            parts = [
                f"Нужно принять решение по ситуации: {problem}.",
                state_sentence,
                "Важно не просто выбрать действие, а разложить, что уже известно, чего не хватает, какие есть варианты и по какому сигналу решение придется пересмотреть.",
                source_sentence,
                risk_sentence or "Если ошибиться сейчас, следующий шаг по обращению станет еще менее прозрачным.",
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F08":
            prioritization_anchor = cleanup_case_text(contract.get("risk") or risk)
            anchor_sentence = f"Первый приоритет нужно выбирать через главный риск: {prioritization_anchor}." if prioritization_anchor else ""
            tasks_sentence = f"Одновременно внимания требуют: {work_items}." if work_items else ""
            parts = [
                f"Нужно быстро понять, что делать в первую очередь, потому что {problem}.",
                tasks_sentence,
                state_sentence,
                anchor_sentence,
                constraint_sentence,
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F09":
            parts = [
                f"В процессе работы регулярно возникает одно и то же узкое место: {problem}.",
                state_sentence,
                risk_sentence or "Из-за этого команда тратит время на повторные уточнения вместо движения обращения дальше.",
                "Нужно предложить улучшение именно для этого узкого места.",
                "Идеи должны быть разными по типу: через процесс, коммуникацию, автоматизацию, формат взаимодействия или контрольный шаг.",
                scope_sentence,
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F10":
            parts = [
                f"Появилась идея улучшения по ситуации: {problem}.",
                state_sentence,
                (f"Идея состоит в следующем: {idea_description}." if idea_description else ""),
                (f"Изменение, которое обсуждается, называется так: {idea_label}." if idea_label else ""),
                "Нужно не только оценить идею в целом, но и решить: берем ее сейчас, дорабатываем или не запускаем.",
                risk_sentence or "Если запустить изменение без проверки, можно усилить текущую путаницу вместо улучшения процесса.",
                f"Нужно понять, стоит ли запускать изменение сейчас, учитывая что {constraint}." if constraint else "Нужно понять, стоит ли запускать изменение прямо сейчас.",
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F11":
            operation = cleanup_case_text(contract.get("operation") or expected)
            regulation = cleanup_case_text(contract.get("regulation") or source)
            escalation_target = cleanup_case_text(contract.get("escalation_target") or stakeholder)
            channel = cleanup_case_text(contract.get("channel") or "")
            authority_limit = cleanup_case_text(contract.get("authority_limit") or constraint)
            adjacent_team = cleanup_case_text(str(specificity.get("adjacent_team") or "смежная команда"))
            if channel and re.match(r"^(?:в|во|по|через)\b", channel.lower()):
                channel_sentence = f"Спорную ситуацию нужно зафиксировать {channel}."
            else:
                channel_sentence = f"Спорную ситуацию нужно зафиксировать через {channel}." if channel else ""
            parts = [
                (f"Перед передачей результата по операции «{operation}» обнаружилось несоответствие: {problem}." if operation else f"Перед следующим этапом обнаружилось несоответствие: {problem}."),
                state_sentence,
                (f"Проверить детали нужно по {regulation}." if regulation else source_sentence),
                (f"{adjacent_team[:1].upper() + adjacent_team[1:]} просит не задерживать процесс и провести операцию как есть." if adjacent_team else ""),
                (f"Самостоятельно вы можете только остановить движение по своему участку, уточнить данные и эскалировать вопрос {escalation_target}." if escalation_target else ""),
                (f"При этом {authority_limit}." if authority_limit else constraint_sentence),
                channel_sentence,
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F03":
            counterpart = self._select_conversation_counterpart(specificity, frame)
            parts = [
                f"Нужно провести сложный разговор по ситуации: {problem}.",
                state_sentence,
                (f"Собеседник в этом разговоре — {counterpart}." if counterpart else ""),
                (f"Главный риск сейчас такой: {risk}." if risk else ""),
                "Важно снять напряжение, обозначить границы и договориться о рабочем формате взаимодействия.",
            ]
            return " ".join(part for part in parts if part).strip()
        if type_code == "F12":
            counterpart = self._select_conversation_counterpart(specificity, frame)
            parts = [
                f"Проблема повторяется вокруг одной и той же ситуации: {problem}.",
                state_sentence,
                (f"Собеседник в этой развивающей беседе — {counterpart}." if counterpart else ""),
                (f"Из-за этого {self._build_risk_sentence(risk).lower()}" if risk else ""),
                "Нужно обсудить с участником, как изменить порядок работы, чтобы ситуация не повторялась.",
                "Разговор должен закончиться конкретным планом развития, поддержкой и понятной метрикой прогресса на ближайшие 2–4 недели.",
            ]
            return " ".join(part for part in parts if part).strip()
        return ""

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

    def _resolve_role_scope(self, role_name: str | None) -> str:
        role = (role_name or "").lower()
        if "линей" in role:
            return "уровень участка"
        if "manager" in role or "менедж" in role or "руковод" in role:
            return "уровень команды или процесса"
        if "leader" in role or "дир" in role or "стратег" in role:
            return "уровень направления или нескольких команд"
        return "масштаб, соответствующий роли пользователя"

    def _apply_case_prompt_grammar_rules(self, text: str) -> str:
        result = text or ""
        phrase_replacements = {
            "в роли Линейный сотрудник": "в роли линейного сотрудника",
            "в роли Менеджер": "в роли менеджера",
            "в роли Лидер": "в роли лидера",
            "в роли линейный аналитик": "в роли линейного сотрудника",
            "в роли линейный сотрудник": "в роли линейного сотрудника",
            "в процессе обработка ": "в процессе обработки ",
            "по вопросу сбой ": "по вопросу сбоя ",
            "по вопросу отсутствие ": "по вопросу отсутствия ",
            "не может вовремя продвинуть завершить": "не может вовремя завершить",
            "к карточка тикета": "к карточке тикета",
            "к карточка запроса": "к карточке запроса",
            "У вас есть доступ к карточка тикета": "У вас есть доступ к карточке тикета",
            "У вас есть доступ к карточка запроса": "У вас есть доступ к карточке запроса",
            "часть работы действительно велась": "часть работы действительно была выполнена",
            "ему обещали вернуться с ответом": "ему обещали предоставить ответ",
            "к текущему моменту": "к настоящему моменту",
            "тем человеком, кому нужно первым ответить": "тем сотрудником, которому необходимо первым ответить",
            "Сейчас именно вы оказались тем сотрудником, которому нужно первым ответить на жалобу": "Сейчас именно вам нужно первым ответить на жалобу",
            "Сейчас именно.": "Сейчас именно вам нужно первым ответить на жалобу.",
            "по каналу через почта": "по электронной почте",
            "Проверять ситуацию приходится по": "Проверить детали можно по",
            "не может завершить согласовать": "не может согласовать",
            "не может вовремя продвинуть согласовать": "не может вовремя согласовать",
            "продвинуть согласовать": "согласовать",
            "как распределить следующий шаг по программе": "что делать со следующим шагом по программе",
            "Перед вами стоит дилемма: нужно быстро принять решение по ситуации": "Нужно быстро принять решение по ситуации",
            "Что бы вы предложили?": "Что вы предложите?",
            "Клиентской поддержки и 1 смежный координатор на эскалациях": "клиентской поддержки и 1 смежный координатор на эскалациях",
            "От клиент, руководитель клиентской поддержки и смежная сервисная команда поступило резкое письмо": "От клиента поступило резкое письмо, копия ушла руководителю клиентской поддержки и смежной сервисной команде",
            "От заказчик поступило резкое письмо": "От заказчика поступило резкое письмо",
            "под угрозой оказывается конструкторского блока": "под угрозой оказываются показатели конструкторского блока",
            "уже известно о работа в рамках регламента": "уже известно, что часть действий выполнялась по регламенту",
            "не может завершить проверку фактического результата, фиксацию следующего шага и обновление пользователя": "не может дождаться подтверждения фактического результата, следующего шага и обновления по обращению",
            "Клиентская поддержка и сопровождение обращений к клиент ждет обновление": "В процессе клиентской поддержки клиент ждет обновление",
            "Это касается **дневная сервисная смена": "Это касается **дневной сервисной смены",
            "будут заметны для клиент": "будут заметны для клиента",
            "вокруг обновление клиента": "вокруг обновления клиента",
        }
        for source, target in phrase_replacements.items():
            result = result.replace(source, target)

        regex_replacements = (
            (r"\bв роли\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)\b", self._normalize_role_phrase),
            (r"\bв процессе\s+обработк([аиуыое])\b", "в процессе обработки"),
            (r"\bпо вопросу\s+сбой\b", "по вопросу сбоя"),
            (r"\bпо вопросу\s+отсутствие\b", "по вопросу отсутствия"),
            (r"\bне может вовремя\s+продвинуть\s+завершить\b", "не может вовремя завершить"),
            (r"\bне может(?:\s+вовремя)?\s+завершить\s+согласовать\b", "не может согласовать"),
            (r"\bне может(?:\s+вовремя)?\s+продвинуть\s+согласовать\b", "не может согласовать"),
            (r"\bк карточка тикета\b", "к карточке тикета"),
            (r"\bк карточка запроса\b", "к карточке запроса"),
            (r"\bпо вопросу отсутствие обратной связи\b", "по вопросу отсутствия обратной связи"),
            (r"\bсбой в отображении данных\b", "сбоя в отображении данных"),
            (r"\bв течение\s+(\d+)\s+рабочих?\s+часов\b", r"в течение \1 рабочих часов"),
            (r"(\d+),\s+(\d+)", r"\1,\2"),
            (r"\bименно вы оказались тем человеком, кому нужно первым ответить\b", "именно вы оказались тем сотрудником, которому необходимо первым ответить"),
            (r"\bвопросу\s+сбоя\b", "вопросу сбоя"),
            (r"\bему обещали предоставить ответ до старта программы осталось (\d+) рабочих дня\b", r"ему обещали предоставить ответ в течение ближайших \1 рабочих дней"),
            (r"\bориентир до старта программы осталось (\d+) рабочих дня\b", r"ориентир: до старта программы осталось \1 рабочих дня"),
            (r"\bПеред вами стоит дилемма:\s*нужно быстро принять решение по ситуации\s*", "Нужно быстро принять решение по ситуации: "),
            (r"\bПроверять ситуацию приходится по\b", "Проверить детали можно по"),
            (r"([0-9%])\s+(Проверить детали можно по)\b", r"\1. \2"),
            (r"([0-9%])\s+(Если ничего не сделать сейчас)\b", r"\1. \2"),
            (r"([0-9%])\s+(Одновременно внимания требуют)\b", r"\1. \2"),
            (r"\bПроверить детали можно по бриф на обучение, ТЗ подрядчику, программа курса и комментарии внутреннего эксперта\b", "Проверить детали можно по брифу на обучение, ТЗ подрядчику, программе курса и комментариям внутреннего эксперта"),
            (r"\bсерь[её]зных срыва сроков, повторных доработок и ошибок в процессе клиентская поддержка и сопровождение обращений\b", "срыва сроков, повторных доработок и ошибок в процессе клиентской поддержки и сопровождения обращений"),
            (r"\bСтавки высокие: на кону клиентская поддержка и сопровождение обращений в контуре рабочая группа участка\b", "Ставки высокие: на кону стабильность клиентской поддержки и сопровождения обращений на этом участке"),
            (r"\bДанные из ([^.]+) не складываются в одну картину: одни сигналы поддерживают более быстрый и выгодный курс, другие предупреждают о ([^.]+), а третьи оставляют зону неопредел[её]нности\b", r"Данные из \1 не складываются в одну картину: часть сигналов говорит в пользу более быстрого решения, другая часть предупреждает о рисках — \2, а по нескольким вопросам данных все еще недостаточно"),
            (r"\bОт клиент, руководитель клиентской поддержки и смежная сервисная команда поступило резкое письмо\b", "От клиента поступило резкое письмо, копия ушла руководителю клиентской поддержки и смежной сервисной команде"),
            (r"\bпод угрозой оказывается клиентского сервиса:\s*([^.]+)\b", r"под угрозой оказываются показатели клиентского сервиса: \1"),
            (r"\bпод угрозой оказывается конструкторского блока:\s*([^.]+)\b", r"под угрозой оказываются показатели конструкторского блока: \1"),
            (r"\bуже известно о работа в рамках регламента, фиксация действий в системе и обязательная эскалация спорных решений\b", "уже известно, что часть действий выполнялась по регламенту, фиксировалась в системе и при необходимости эскалировалась"),
            (r"\bпо вопросу ([^,]+), ему обещали\b", r"по вопросу «\1», ему обещали"),
            (r"по вопросу ««([^»]+)»»", r"по вопросу «\1»"),
            (r"Сейчас именно\.", "Сейчас именно вам нужно первым ответить на жалобу."),
            (r"\bдо\s+(\d{1,2}):\s+(\d{2})\b", r"до \1:\2"),
            (r"\bне может завершить проверку фактического результата, фиксацию следующего шага и обновление пользователя\b", "не может дождаться подтверждения фактического результата, следующего шага и обновления по обращению"),
            (r"\bНужно быстро принять решение по ситуации что делать в первую очередь, если\b", "Нужно быстро решить, что делать в первую очередь, если"),
            (r"\bПо одним данным из брифы на обучение, карточки программ в LMS/HRM, календарь обучения и обратная связь участников\b", "По одним данным из брифа на обучение, карточки программы в LMS/HRM, календаря обучения и обратной связи участников"),
            (r"\bв контуре команда обучения и развития персонала\b", "в контуре команды обучения и развития персонала"),
            (r"\bв контуре рабочая группа участка\b", "на этом участке"),
            (r"\bнужно не просто выбрать вариант, а показать управленческую логику\b", "нужно не просто выбрать вариант, а коротко объяснить логику решения"),
            (r"\bкак вы принимаете решение сейчас, что проверяете в первую очередь и по какому сигналу готовы пересмотреть курс\b", "какие факты вы проверяете в первую очередь, какое решение принимаете сейчас и в каком случае готовы его пересмотреть"),
            (r"\bПроверка идет по финальная версия программы, комментарии заказчика и карточка обучения в LMS/HRM\b", "Проверка идет по финальной версии программы, комментариям заказчика и карточке обучения в LMS/HRM"),
            (r"\bПроверка идет по бриф на обучение, ТЗ подрядчику, программа курса и комментарии внутреннего эксперта\b", "Проверка идет по брифу на обучение, ТЗ подрядчику, программе курса и комментариям внутреннего эксперта"),
            (r"\bПроверка идет по список участников, комментарии руководителя подразделения и карточка запуска программы\b", "Проверка идет по списку участников, комментариям руководителя подразделения и карточке запуска программы"),
            (r"\bПроверка идет по календарь обучения, график подразделения и подтверждения руководителя по датам\b", "Проверка идет по календарю обучения, графику подразделения и подтверждениям руководителя по датам"),
            (r"\bПроверка идет по анкеты обратной связи, комментарии участников и карточка результатов пилота\b", "Проверка идет по анкетам обратной связи, комментариям участников и карточке результатов пилота"),
            (r"\bПроверка идет по карточка обучения, комментарии заказчика и история договоренностей по следующему шагу\b", "Проверка идет по карточке обучения, комментариям заказчика и истории договоренностей по следующему шагу"),
            (r"\bДоступно: финальная программа курса, комментарии заказчика и карточка обучения и дата старта в LMS/HRM\b", "Доступно: финальная программа курса, комментарии заказчика, карточка обучения и дата старта в LMS/HRM"),
            (r"\bДоступно: список участников, карточка программы и календарь обучения и комментарии руководителя подразделения\b", "Доступно: список участников, карточка программы, календарь обучения и комментарии руководителя подразделения"),
            (r"\bДоступно: анкеты обратной связи и карточка результатов пилота и комментарии участников и эксперта\b", "Доступно: анкеты обратной связи, карточка результатов пилота и комментарии участников и эксперта"),
            (r"\bДоступно: карточка обучения, история договоренностей и комментарии заказчика и журнал задач по программе\b", "Доступно: карточка обучения, история договоренностей, комментарии заказчика и журнал задач по программе"),
            (r"\bпривед[её]т к планирование и организация обучения сотрудников\b", "может сорвать планирование и организацию обучения сотрудников"),
            (r"\bне получил ни решения, ни обновления статуса\b", "не получил ни решения, ни обновления статуса"),
            (r"\bчасть работы действительно была выполнена, но клиент этого не видит\b", "часть работы действительно была выполнена, однако клиент этого не видит"),
            (r"\bа следующий шаг никем явно не зафиксирован\b", "а следующий шаг нигде явно не зафиксирован"),
        )
        for pattern, replacement in regex_replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        result = re.sub(r"\bпо вопросу отсутствия обратной связи после обещанного срока\b", "по вопросу отсутствия обратной связи после обещанного срока", result, flags=re.IGNORECASE)
        result = re.sub(r"\bкарточка тикета\b", "карточке тикета", result)
        result = re.sub(r"\bкарточка запроса\b", "карточке запроса", result)
        result = re.sub(r"\bне может вовремя завершить анализ\b", "не может вовремя завершить анализ", result)
        result = re.sub(r"\bне может вовремя завершить переход\b", "не может вовремя перейти", result)
        return result.strip()

    def _normalize_role_phrase(self, match: re.Match[str]) -> str:
        phrase = match.group(1).strip().lower()
        mapping = {
            "линейный сотрудник": "в роли линейного сотрудника",
            "менеджер": "в роли менеджера",
            "лидер": "в роли лидера",
        }
        return mapping.get(phrase, match.group(0))
