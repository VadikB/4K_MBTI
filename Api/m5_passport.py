"""Project normative M5 inputs from the selected passport and pinned M2/M3 artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from Api.assessment_case_contracts import CaseVersionV4
from Api.m5_case_type_catalog import load_case_type_catalog
from Api.m5_package import digest
from Api.m5_passport_v12 import scenario_projection
from scripts.build_m3_base_roles import CARD_FIELDS, DESCRIPTION_FIELDS
from scripts.build_m4_context_package import USER_CONTEXT_FIELDS
from scripts.build_m5_sales_package import _minutes, _ref

PASSPORT_FIELDS = (
    "1 CaseID", "2 Название", "3 CaseTypeIDs", "4 Логика связи CT", "5 Формат Case",
    "6 ApplicableBaseRoles", "7 Version", "8 Исходная ситуация", "9 Trigger",
    "10 Позиция оцениваемого", "11 Участники и позиции", "12 Задача оцениваемого",
    "13 Условия и ограничения", "14 Applicability", "15 Функциональный результат",
    "16 Инвариантное ядро", "17 Сценарий Dialogue", "18 Правила персонализации и ролевой адаптации",
    "19 Параметры сложности", "20 Плановое время", "21 Риски невалидной реализации", "22 IndicatorIDs",
)
NESTED_FIELDS = {
    17: ("Граница исполнения", "Границы распознавания", "Закрытая карта дополнительных сведений",
         "Конкретизация персонажей", "На старте", "Правила управления", "События",
         "Состояния", "Тип", "Функции материалов"),
    18: ("Базовая роль", "Изменяемые параметры", "Источники контекста и пробелы", "Критические запреты",
         "Минимальный контекст", "Общее правило адаптации", "Обязательные функции",
         "Применимость по деятельности", "Функциональная граница"),
    19: ("Настраивается", "Нельзя", "Объём", "Проверка времени", "Фиксировано"),
    20: ("Диапазон минут", "Минут", "Минимум минут", "Максимум минут", "Правило"),
    22: ("Версии M2", "Проектные условия", "Точный перечень"),
}
INDICATOR_FIELDS = (
    "ComponentID", "IndicatorID", "SkillID", "Версия M2", "Доступная форма проявления",
    "Источник M2", "Материалы и факты по функции", "Название", "Проектное условие",
    "Риск потери", "Состояние", "Условие возникновения", "Функциональные условия",
)
EVENT_FIELDS = ("EventID", "Действие", "Изменение состояния", "Когда запрещено", "Повторение",
                "Сведения и аудитория", "Условие запуска")
ORGANIZATION_FIELDS = (
    "organization_type", "industry", "activity_description", "activities", "products_services_programs",
    "main_result", "recipients", "size", "geography", "employee_common_context", "general_rules",
    "comments", "terminology", "case_reality_level", "organization_name_usage_rules", "anonymization_rules",
    "forbidden_topics",
)
USER_FIELDS = tuple(key for _, key, category in USER_CONTEXT_FIELDS if category == "professional")


def missing(case_id: str, version: str, path: str) -> ValueError:
    return ValueError(f"M5_PASSPORT_REQUIREMENT_INVALID:{case_id}:{version}:{path}")


def _project(value: Any, keys: tuple[str, ...]) -> dict:
    return {key: value[key] for key in keys if key in value} if isinstance(value, dict) else {}


def _rows(value: Any, keys: tuple[str, ...]) -> list[dict]:
    return [_project(row, keys) for row in value] if isinstance(value, list) else []


def project_passport(raw: dict, case_id: str, version: str) -> dict:
    # Older immutable CaseVersions used several slightly different field names.
    if not isinstance(raw, dict):
        raise missing(case_id, version, "Паспорт")
    indexed = {key.split(" ", 1)[0]: value for key, value in raw.items()}
    if len(indexed) != len(raw):
        raise missing(case_id, version, "Паспорт/номер поля")
    passport = {}
    for number, key in enumerate(PASSPORT_FIELDS, 1):
        value = indexed.get(str(number))
        if value is None or value == "" or (number != 21 and value in ([], {})):
            raise missing(case_id, version, key)
        if number in NESTED_FIELDS:
            allowed = NESTED_FIELDS[number]
            projected = _project(value, allowed)
            if number != 20 and set(projected) != set(allowed):
                absent = next(name for name in allowed if name not in projected)
                raise missing(case_id, version, f"{number}/{absent}")
            value = projected
        passport[key] = value
    if passport["1 CaseID"] != case_id:
        raise missing(case_id, version, "1 CaseID")
    passport["7 Version"] = version
    invariants = "16 Инвариантное ядро"
    passport[invariants] = _rows(passport[invariants], ("InvariantID", "Короткий ID", "Условие"))
    if not passport[invariants] or any(
        not isinstance(row.get("InvariantID"), str) or not row["InvariantID"].strip()
        or not isinstance(row.get("Условие"), str) or not row["Условие"].strip()
        for row in passport[invariants]
    ):
        raise missing(case_id, version, "16/InvariantID, Условие")
    adaptation = passport["18 Правила персонализации и ролевой адаптации"]
    for key in ("Критические запреты", "Обязательные функции", "Общее правило адаптации",
                "Источники контекста и пробелы", "Применимость по деятельности"):
        if not adaptation.get(key):
            raise missing(case_id, version, f"18/{key}")
    scenario = passport["17 Сценарий Dialogue"]
    scenario["События"] = _rows(scenario.get("События"), EVENT_FIELDS)
    scenario["Правила управления"] = _rows(scenario.get("Правила управления"), ("RuleID", "Правило"))
    if not scenario["Правила управления"] or any(set(rule) != {"RuleID", "Правило"} for rule in scenario["Правила управления"]):
        raise missing(case_id, version, "17/Правила управления")
    if not scenario["События"] or any(
        set(event) != set(EVENT_FIELDS) or not all(isinstance(value, str) and value.strip() for value in event.values())
        for event in scenario["События"]
    ):
        raise missing(case_id, version, "17/События")
    ids = [event["EventID"] for event in scenario["События"]]
    if not all(isinstance(value, str) and value for value in ids) or len(ids) != len(set(ids)):
        raise missing(case_id, version, "17/События/EventID")
    materials, starts = (scenario.get(key) for key in ("Функции материалов", "На старте"))
    if (not isinstance(materials, dict) or not isinstance(starts, list) or "P00" not in starts
            or not all(isinstance(item, str) and item in materials for item in starts)
            or len(starts) != len(set(starts))):
        raise missing(case_id, version, "17/На старте→Функции материалов")
    fixed = passport["19 Параметры сложности"].get("Фиксировано")
    if not isinstance(fixed, dict) or type(fixed.get("Активные персонажи")) is not int or fixed["Активные персонажи"] < 0:
        raise missing(case_id, version, "19/Фиксировано/Активные персонажи")
    targets = passport["22 IndicatorIDs"]
    targets["Проектные условия"] = _rows(targets.get("Проектные условия"), INDICATOR_FIELDS)
    return passport


def load_m2(path: Path, source_manifest: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    methodology = json.loads(raw)
    sources = json.loads(source_manifest.read_text())["entries"]
    versions = {item["id"].split(".")[1]: item for item in sources if item["id"].endswith(".matrix")}
    index = {}
    for competency in methodology["competencies"]:
        source = versions[competency["id"]]
        for skill in competency["skills"]:
            for component in skill["components"]:
                for indicator in component["indicators"]:
                    index[indicator["id"]] = {
                        "skill_id": skill["id"], "component_id": component["id"],
                        "m2_version": "v" + source["version"],
                        "source": {key: source[key] for key in ("id", "version", "sha256")},
                        "descriptor": indicator,
                    }
    return index, {"id": "m2-competencies-4k", "version": methodology["methodology_version"],
                   "checksum": digest(raw)}


def compile_passport(*, raw: dict, case_id: str, version: str, status: str, source: dict,
                     m2: dict, m3: dict, as_contract_ref: dict, selected_base_role: str | None = None,
                     passport_version: str = "1.1") -> dict:
    v12 = passport_version == "1.2"
    if v12:
        for field in PASSPORT_FIELDS:
            if not raw.get(field):
                raise missing(case_id, version, field)
        if set(raw) != set(PASSPORT_FIELDS) or (raw[PASSPORT_FIELDS[0]], raw[PASSPORT_FIELDS[6]]) != (case_id, version):
            raise missing(case_id, version, "Паспорт/поля и идентичность")
        passport = {field: raw[field] for field in PASSPORT_FIELDS}
        materials, scenario, locations = scenario_projection(passport, source, lambda path: missing(case_id, version, path))
    else:
        passport = project_passport(raw, case_id, version)
        materials = []
        locations = {}
        scenario = [
            {"step_id": event["EventID"], "order": index + 1, "content": event,
             "source": {**source, "pointer": f"/Паспорт/17 Сценарий Dialogue/События/{index}"}}
            for index, event in enumerate(passport[PASSPORT_FIELDS[16]]["События"])
        ]
    prefix = dict(case_id=case_id, version=version, status=status, passport=passport)
    role_labels = passport["6 ApplicableBaseRoles"]
    role_codes = {role["description"]["name"]: role["code"] for role in m3["base_roles"]}
    if not isinstance(role_labels, list) or not all(isinstance(label, str) and label in role_codes for label in role_labels):
        raise missing(case_id, version, "6 ApplicableBaseRoles→M3")
    roles = {role_codes[label] for label in role_labels}
    if selected_base_role is None and len(roles) == 1:
        selected_base_role = next(iter(roles))
    if selected_base_role not in roles:
        raise missing(case_id, version, "6 ApplicableBaseRoles→BaseRole")
    case_types = passport["3 CaseTypeIDs"]
    load_case_type_catalog().validate(case_types, case_id=case_id, pointer=f"/{version}/3 CaseTypeIDs")
    logic = passport["4 Логика связи CT"]
    if not v12 and not isinstance(logic, str):
        raise missing(case_id, version, "4 Логика связи CT")
    if v12:
        if isinstance(logic, dict):
            logic_ids = set(logic) - {"Связь"}
        elif isinstance(logic, list):
            logic_ids = {item.get("CaseTypeID") for item in logic if isinstance(item, dict)}
        else:
            logic_ids = set(re.findall(r"\bCT\d{2}\b", logic)) if isinstance(logic, str) else set()
        if logic_ids != set(case_types):
            raise missing(case_id, version, "4 Логика связи CT→3 CaseTypeIDs")
    applicability_rows = passport["14 Applicability"]
    if not isinstance(applicability_rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("SkillID"), str)
        or not isinstance(row.get("ComponentIDs"), list) or not row["ComponentIDs"]
        for row in applicability_rows
    ):
        raise missing(case_id, version, "14 Applicability/SkillID,ComponentIDs")
    applicability = [{"skill_id": row["SkillID"], "component_id": component, "required": True}
                     for row in applicability_rows for component in row["ComponentIDs"]]
    target_fields = passport["22 IndicatorIDs"]
    exact, conditions, versions = (target_fields.get(name) for name in ("Точный перечень", "Проектные условия", "Версии M2"))
    if (not isinstance(exact, list) or not exact or not all(isinstance(key, str) for key in exact)
            or len(exact) != len(set(exact)) or not isinstance(versions, dict)):
        raise missing(case_id, version, "22/Точный перечень, Версии M2")
    if any(not isinstance(row.get("IndicatorID"), str) for row in conditions):
        raise missing(case_id, version, "22/Проектные условия/IndicatorID")
    rows = {row["IndicatorID"]: (index, row) for index, row in enumerate(conditions)}
    if set(rows) != set(exact) or len(rows) != len(conditions):
        raise missing(case_id, version, "22/Точный перечень→Проектные условия")
    targets = []
    for indicator_id in exact:
        index, row = rows[indicator_id]
        norm = m2.get(indicator_id)
        if (not norm or (row.get("SkillID"), row.get("ComponentID"), row.get("Версия M2"))
                != (norm["skill_id"], norm["component_id"], norm["m2_version"])
                or versions.get(indicator_id.split(".")[0]) != norm["m2_version"]
                or {"skill_id": norm["skill_id"], "component_id": norm["component_id"], "required": True}
                not in applicability):
            raise missing(case_id, version, f"22/{indicator_id}→Applicability,M2")
        condition = row.get("Условие возникновения") if v12 else (
            row.get("Проектное условие") or row.get("Функциональные условия")
        )
        if not condition or not row.get("Доступная форма проявления") or not row.get("Риск потери"):
            raise missing(case_id, version, f"22/{indicator_id}/Проектное условие, форма, риск")
        targets.append({
            "indicator_id": indicator_id, "skill_id": norm["skill_id"], "component_id": norm["component_id"],
            "m2_version": norm["m2_version"], "observation_condition": "\n".join(condition) if isinstance(condition, list) else condition,
            "scenario_locations": row["Место в сценарии"] if v12 else [],
            "branch_condition": None, "event_condition": row.get("Условие возникновения"),
            "observable_action": row["Доступная форма проявления"], "validity_risk": row["Риск потери"],
            "normative_source": norm["source"], "source": {
                **source, "pointer": f"/Паспорт/22 IndicatorIDs/Проектные условия/{index}",
            },
        })
    time = passport["20 Плановое время"]
    try:
        low, high = _minutes({key: value for key, value in time.items() if key != "Правило"})
    except ValueError as exc:
        raise missing(case_id, version, "20 Плановое время") from exc
    case_format = passport["5 Формат Case"]
    if v12:
        label = case_format.casefold() if isinstance(case_format, str) else ""
        case_format = next((value for prefix, value in (
            ("диалогов", "Диалоговый"), ("многоролев", "Многоролевой"),
            ("аналитико-рефлексивный письменный", "Письменный"),
        ) if label.startswith(prefix)), None)
        if case_format is None:
            raise missing(case_id, version, "5 Формат Case")
    return CaseVersionV4.model_validate({
        **prefix, "schema_version": 4, "passport_version": passport_version, "as_contract_ref": as_contract_ref,
        "passport_source": source, "title": passport["2 Название"], "base_role": selected_base_role,
        "format": case_format, "planned_min_minutes": low, "planned_max_minutes": high,
        "case_type_ids": case_types, "applicability": applicability, "indicator_targets": targets,
        "passport_sources": {
            **{key: {**source, "pointer": _ref("passport", source["sha256"], "Паспорт", key)["pointer"]}
               for key in passport},
            **{key: {**source, "pointer": pointer} for key, pointer in locations.items()},
        },
        "characters": [], "materials": materials, "scenario": scenario,
    }).model_dump(exclude_unset=True)


def allowed_profile(profile: dict, *, include_confirmed_work: bool = False) -> dict:
    organization = profile.get("organization_context") or {}
    role = profile.get("role_profile") or {}
    allowed_organization = _project(organization, ORGANIZATION_FIELDS)
    if allowed_organization.get("organization_name_usage_rules") == "Можно использовать настоящее название":
        allowed_organization.update(_project(organization, ("name",)))
    user_fields = (*USER_FIELDS, "decision_situations", "constraints_and_interactions") if include_confirmed_work else USER_FIELDS
    return {
        "organization_context": allowed_organization,
        "role_profile": {
            **_project(role, ("code", "base_role_code", "kind", "methodology_version")),
            "description": _project(role.get("description"), tuple(key for _, key in DESCRIPTION_FIELDS if key != "examples")),
            "card": _project(role.get("card"), tuple(key for _, key in CARD_FIELDS)),
        },
        "user_context": _project(profile.get("user_context"), user_fields),
    }
