"""Lossless v1.2 passport projection and local reference validation."""
from __future__ import annotations

import re

from scripts.build_m5_sales_package import _ref

SCENARIO_FIELDS = (
    "17.1 Старт",
    "17.2 Материалы и исходная доступность",
    "17.3 Правила реакции и событий",
    "17.4 Завершение",
)
REFERENCE_ID = re.compile(r"\b(?:K[1-4]\.I\d{2}|E\d{2}_[A-Z_]+|R_[A-Z_]+|[PMFI]\d{2}|C\d{1,2})\b")
INVARIANT_LINKS = (
    "Место реализации", "Места реализации", "Место в паспорте",
    "Ссылки", "Связь", "Основание", "Связь со сценарием",
)
RISK_LINKS = ("Затронутые места", "Затронутые элементы")


def scenario_projection(passport: dict, source: dict, invalid) -> tuple[list, list, dict]:
    scenario = passport["17 Сценарий Dialogue"]
    fields = [*passport.keys()]
    pointers = {str(index): _ref("passport", source["sha256"], "Паспорт", field)["pointer"]
                for index, field in enumerate(fields, 1)}

    def pointer(*segments):
        return _ref("passport", source["sha256"], "Паспорт", *segments)["pointer"]

    def rows(value, field, required, *, text_lists=()):
        if not isinstance(value, list) or not value:
            raise invalid(field)
        for index, row in enumerate(value):
            for key in required:
                text = row.get(key) if isinstance(row, dict) else None
                if key in text_lists and isinstance(text, list) and text and all(
                    isinstance(item, str) and item.strip() for item in text
                ):
                    continue
                if not isinstance(text, str) or not text.strip():
                    raise invalid(f"{field}/{index}/{key}")
        return value

    field17 = fields[16]
    for key in SCENARIO_FIELDS:
        if not isinstance(scenario, dict) or not scenario.get(key):
            raise invalid(f"17/{key}")
        pointers[key.split(" ", 1)[0]] = pointer(field17, key)
    start, material_rows, event_rows, finish = (scenario[key] for key in SCENARIO_FIELDS)
    if not isinstance(start, dict) or not start.get("Начальное предъявление"):
        raise invalid("17.1/Начальное предъявление")
    if not isinstance(finish, dict):
        raise invalid("17.4")
    material_rows = rows(material_rows, "17.2", (
        "ID", "Название", "Содержание или требования к содержанию", "Кому известно до начала",
    ), text_lists=("Содержание или требования к содержанию",))
    event_rows = rows(event_rows, "17.3", (
        "ID", "При каком условии", "Кто действует", "Кому адресовано", "Что происходит", "Особые ограничения",
    ), text_lists=("Особые ограничения",))
    materials = {row["ID"]: (index, row) for index, row in enumerate(material_rows)}
    events = {row["ID"]: (index, row) for index, row in enumerate(event_rows)}
    if len(materials) != len(material_rows) or len(events) != len(event_rows) or materials.keys() & events.keys():
        raise invalid("17.2–17.3/ID")

    order = start.get("Последовательность предъявления")
    if not isinstance(order, list) or not order or order[0] != "P00" or any(
        not isinstance(item, str) or item not in materials for item in order
    ) or len(set(order)) != len(order):
        raise invalid("17.1/Последовательность предъявления→17.2")
    material_index = {}
    for material_id in [*order, *(key for key in materials if key not in order)]:
        index, row = materials[material_id]
        ref = pointer(field17, SCENARIO_FIELDS[1], str(index))
        material_index[material_id] = {
            "material_id": material_id, "order": len(material_index) + 1,
            "participant_visible_initially": material_id in order, "content": row,
            "source": {**source, "pointer": ref},
        }
        pointers[material_id] = pointers[f"17.2/{material_id}"] = ref
        if material_id in order:
            pointers[f"17.1/{material_id}"] = pointer(
                field17, SCENARIO_FIELDS[0], "Последовательность предъявления", str(order.index(material_id)),
            )
    steps = []
    for event_id, (index, row) in events.items():
        ref = pointer(field17, SCENARIO_FIELDS[2], str(index))
        steps.append({"step_id": event_id, "order": len(steps) + 1, "content": row,
                      "source": {**source, "pointer": ref}})
        pointers[event_id] = pointers[f"17.3/{event_id}"] = ref
    if "ID" in finish:
        finish_id = finish["ID"]
        if not isinstance(finish_id, str) or not finish_id or finish_id in pointers:
            raise invalid("17.4/ID")
        pointers[finish_id] = pointers[f"17.4/{finish_id}"] = pointers["17.4"]
        steps.append({"step_id": finish_id, "order": len(steps) + 1, "content": finish,
                      "source": {**source, "pointer": pointers["17.4"]}})

    participants = passport[fields[10]]
    if not isinstance(participants, list) or not participants or not all(isinstance(row, dict) for row in participants):
        raise invalid("11/Участники")
    for index, row in enumerate(participants):
        participant_id = row.get("ID") or row.get("RoleID")
        if participant_id:
            pointers[participant_id] = pointers[f"11/{participant_id}"] = pointer(fields[10], str(index))
    invariants = rows(passport[fields[15]], "16", ("InvariantID", "Короткий ID", "Условие"))
    for index, row in enumerate(invariants):
        key = row["Короткий ID"]
        if key in pointers or row["InvariantID"] in pointers:
            raise invalid(f"16/{index}/InvariantID")
        ref = pointer(fields[15], str(index))
        pointers[key] = pointers[f"16/{key}"] = pointers[row["InvariantID"]] = ref
    target_rows = rows(passport[fields[21]].get("Проектные условия"), "22/Проектные условия",
                       ("IndicatorID", "Условие возникновения", "Доступная форма проявления", "Риск потери"))
    for index, row in enumerate(target_rows):
        key = row["IndicatorID"]
        if key in pointers:
            raise invalid(f"22/Проектные условия/{index}/IndicatorID")
        pointers[key] = pointers[f"22/{key}"] = pointer(fields[21], "Проектные условия", str(index))

    def resolve(value, field):
        key = re.sub(r"^(\d+(?:\.\d+)?)\s+", r"\1/", value.strip())
        if key not in pointers:
            raise invalid(f"{field}→{value}: ссылка не найдена")
        return pointers[key]

    for index, row in enumerate(target_rows):
        field = f"22/Проектные условия/{index}/Место в сценарии"
        locations = row.get("Место в сценарии")
        if not isinstance(locations, list) or not locations or not all(isinstance(ref, str) for ref in locations):
            raise invalid(field)
        for ref in locations:
            resolve(ref, field)

    risks = rows(passport[fields[20]], "21", ("ID",))
    for number, records, aliases in ((16, invariants, INVARIANT_LINKS), (21, risks, RISK_LINKS)):
        for index, row in enumerate(records):
            for key in aliases:
                if key not in row:
                    continue
                links = row[key]
                field = f"{number}/{index}/{key}"
                for value in links if isinstance(links, list) else [links]:
                    if not isinstance(value, str) or not value.strip():
                        raise invalid(field)
                    if value in pointers or re.match(r"^\d+(?:\.\d+)?[/ ]\w+$", value):
                        resolve(value, field)
                    else:
                        for match in REFERENCE_ID.finditer(value):
                            resolve(match.group(), field)
    return list(material_index.values()), steps, pointers
