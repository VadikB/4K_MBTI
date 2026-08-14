from __future__ import annotations

import re
import zlib
from typing import Any

import psycopg
from psycopg.rows import dict_row

from Api.case_text_cleanup import cleanup_case_list, cleanup_case_text, join_case_list
from Api.config import settings
from Api.assessment.case_generation.specificity import CaseSpecificityMixin
from Api.assessment.case_generation.text_pipeline import CaseTextPipelineMixin

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


class CaseQualityMixin(CaseTextPipelineMixin, CaseSpecificityMixin):


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
