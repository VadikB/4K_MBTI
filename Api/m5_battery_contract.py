"""Frozen v1.2 scenario bindings for the isolated specialist battery."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from Api.assessment_case_contracts import PreparedCaseV4
from Api.m5_package import digest
from Api.m5_passport import missing
from Api.m5_passport_v12 import SCENARIO_FIELDS
from scripts.build_m5_sales_package import _participant_presentation, _ref

RULE_PACKAGE = "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.6.0"
FACILITATOR = "FACILITATOR"


def load_scenario(case: dict, directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    raw = (directory / "scenario-rules.json").read_bytes()
    checksum = digest(raw)
    package = json.loads(raw)
    if (manifest["id"], manifest["version"], manifest["artifacts"]) != (
        package["id"], package["version"], [{"name": "scenario-rules.json", "sha256": checksum}],
    ) or package["schema_version"] != 1 or package["scope"] != "isolated_qa":
        raise ValueError("M5_BATTERY_SCENARIO_PACKAGE_INVALID")
    case_id, version = case["case_id"], case["version"]
    overlay = package["cases"].get(case_id)
    if not overlay or (overlay["case_version"], overlay["passport_sha256"]) != (
        version, case["passport_source"]["sha256"],
    ):
        raise missing(case_id, version, "17→scenario rule package")
    passport = case["passport"]
    source = passport["17 Сценарий Dialogue"]
    start, materials, events, finish = (source[key] for key in SCENARIO_FIELDS)
    material_ids = {row["ID"] for row in materials}
    fact_ids = {item for item in material_ids if item.startswith("F")}
    event_by_id = {row["ID"]: row for row in events}
    roles = overlay["roles"]
    settings = overlay["events"]
    if (len(settings) != len(event_by_id) or {row["id"] for row in settings} != set(event_by_id)
            or {row["delivery_id"] for row in settings if row["delivery_id"]}
            != material_ids - set(start["Последовательность предъявления"]) - fact_ids):
        raise missing(case_id, version, "17→scenario event and material coverage")
    for row in settings:
        if (not set(row["speaker_ids"]) <= (roles.keys() if roles else {FACILITATOR})
                or not set(row["fact_ids"]) <= fact_ids
                or row["requires_material_id"] not in (material_ids | {None})
                or row["kind"] not in {"reply", "delivery", "transfer", "forward", "transfer_reply"}):
            raise missing(case_id, version, f"17.3/{row['id']}→scenario rule")
    material_by_id = {row["ID"]: row for row in materials}
    for key, role in roles.items():
        if not set(role["known_material_ids"] + role.get("partial_material_ids", [])) <= material_ids - fact_ids:
            raise missing(case_id, version, f"17.2/{key}/Кому известно до начала")
    opening = overlay["opening"]
    if opening and (opening["speaker_id"] not in roles or opening["material_id"] not in start["Последовательность предъявления"]):
        raise missing(case_id, version, "17.1/Первая реплика")
    locations = {}
    for target in case["indicator_targets"]:
        references = [re.split(r"[/ ]", value.strip())[-1] for value in target["scenario_locations"]]
        references = list(dict.fromkeys(references))
        character_ids = [key for key in references if key in roles]
        locations[target["indicator_id"]] = {
            "material_refs": [key for key in references if key in material_ids - fact_ids],
            "event_refs": [key for key in references if key in event_by_id] + (
                [finish.get("ID", "SCENARIO_COMPLETION")] if "17.4" in references else []
            ),
            "character_refs": character_ids,
            "authority_refs": ["participant", *(f"character:{key}" for key in character_ids)],
        }
    role_sources = {}
    participants = passport["11 Участники и позиции"]
    for key, role in roles.items():
        source_role = participants[role["participant_index"]]
        label = next((source_role[field] for field in ("Персонаж", "Обозначение", "Роль", "Функция")
                      if isinstance(source_role.get(field), str) and source_role[field].strip()), key)
        role_sources[key] = {
            **role, "source": source_role, "public_label": label,
            "knowledge_limits": {item: material_by_id[item]["Кому известно до начала"]
                                 for item in role.get("partial_material_ids", [])},
        }
    return {
        "ref": {"id": package["id"], "version": package["version"], "checksum": checksum},
        "start_ids": start["Последовательность предъявления"], "material_ids": sorted(material_ids - fact_ids),
        "fact_ids": sorted(fact_ids), "finish": finish, "opening": opening,
        "applicability": passport["18 Правила персонализации и ролевой адаптации"],
        "profile_capability": overlay["profile_capability"], "control": package["control"],
        "instructions": package["instructions"],
        "observability_references": locations,
        "roles": role_sources,
        "events": [
            {**row, "passport": event_by_id[row["id"]],
             "source": case["passport_sources"][f"17.3/{row['id']}"]}
            for row in settings
        ],
    }


def validate_profile(profile: dict, design: dict) -> None:
    context = profile.get("user_context") or {}
    role = profile.get("role_profile") or {}
    if not context.get("regular_tasks") and not role.get("card", {}).get("regular_tasks"):
        raise ValueError("M5_BATTERY_PROFILE_CLARIFICATION_REQUIRED:18/рабочая функция")
    if capability := design["profile_capability"]:
        confirmation = (context.get("additional_information") or {}).get(capability)
        if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True or not confirmation.get("basis"):
            raise ValueError(f"M5_BATTERY_PROFILE_CLARIFICATION_REQUIRED:18/{capability}")


def candidate_contract(base: dict) -> dict:
    fields = {key: base["fields"][key] for key in (
        "AssessmentSituationID", "Version", "Название", "Применённые замены", "IndicatorObservability",
    )}
    fields.update({
        "Материалы": "MaterialID, Название, Текст для каждого material_ids из scenario_contract.",
        "Активные персонажи": "CharacterID, Имя, Текст (исходная позиция) для каждого roles из scenario_contract.",
        "Закрытые фиксированные факты": "FactID и Текст для каждого fact_ids из scenario_contract. Эти записи не являются документами.",
    })
    return {**base, "fields": fields}


def bind(snapshot: dict, proposed: object) -> object:
    if not isinstance(proposed, dict):
        return proposed
    design, case = snapshot["battery_scenario"], snapshot["case_version"]
    targets = case["passport"]["22 IndicatorIDs"]
    bound = {
        **proposed, "CaseID": case["case_id"], "CaseVersion": case["version"], "BaseRole": case["base_role"],
        "CaseTypeIDs": case["case_type_ids"], "IndicatorIDs": targets["Точный перечень"],
        "Версии M2": targets["Версии M2"], "Стартовые MaterialIDs": design["start_ids"],
        "События": [{"EventID": row["id"], **row["passport"]} for row in design["events"]],
        "RuntimeBindings": {
            row["id"]: {key: value for key, value in row.items() if key not in {"id", "passport"}}
            for row in design["events"]
        },
    }
    rows = proposed.get("IndicatorObservability")
    if isinstance(rows, list):
        bound["IndicatorObservability"] = [
            {**row, **design["observability_references"].get(row.get("IndicatorID"), {})}
            if isinstance(row, dict) and isinstance(row.get("IndicatorID"), str) else row
            for row in rows
        ]
    return bound


def validate_candidate(snapshot: dict, value: dict, check) -> None:
    from Api.m5_passport_generation import ADAPTED_FIELDS, REF_FIELDS, _indexed, _ids, _text

    design = snapshot["battery_scenario"]
    generated_fields = set(snapshot["as_contract"]["fields"])
    sealed = bind(snapshot, {})
    check("battery_candidate_fields", set(value) == generated_fields | sealed.keys())
    for field in ("AssessmentSituationID", "Version", "Название"):
        check("required_text", _text(value.get(field)), path=f"candidate_as/{field}")
    check("required_list", isinstance(value.get("Применённые замены"), list), path="candidate_as/Применённые замены")
    tables = (
        ("Материалы", "MaterialID", design["material_ids"], ("Название", "Текст")),
        ("Закрытые фиксированные факты", "FactID", design["fact_ids"], ("Текст",)),
        ("Активные персонажи", "CharacterID", design["roles"], ("Имя", "Текст")),
    )
    indexed = {}
    for field, key, ids, fields in tables:
        rows = _indexed(value.get(field), key)
        check("battery_namespace", rows is not None and rows.keys() == set(ids), path=f"candidate_as/{field}")
        indexed[field] = rows or {}
        for identifier, row in indexed[field].items():
            check("battery_content_fields", set(row) == {key, *fields}
                  and all(_text(row.get(name)) for name in fields), path=f"candidate_as/{field}/{identifier}")
    documents = indexed["Материалы"]
    closed = [row for key, row in documents.items() if key not in design["start_ids"]]
    closed.extend(indexed["Закрытые фиксированные факты"].values())
    for key in design["start_ids"]:
        text = documents.get(key, {}).get("Текст")
        if _text(text):
            check("battery_closed_content", not any(
                _text(row.get("Текст")) and row["Текст"].casefold() in text.casefold() for row in closed
            ), path=f"candidate_as/Материалы/{key}/Текст")
    observed = _indexed(value.get("IndicatorObservability"), "IndicatorID")
    targets = snapshot["case_version"]["indicator_targets"]
    check("battery_target_set", observed is not None and observed.keys() == {row["indicator_id"] for row in targets},
          path="candidate_as/IndicatorObservability")
    allowed = {
        "material_refs": set(design["material_ids"]), "event_refs": {row["id"] for row in design["events"]}
        | {design["finish"].get("ID", "SCENARIO_COMPLETION")},
        "character_refs": set(design["roles"]), "authority_refs": {"participant", *(f"character:{key}" for key in design["roles"])},
    }
    for indicator, row in (observed or {}).items():
        path = f"candidate_as/IndicatorObservability/{indicator}"
        check("battery_observability", set(row) == {"IndicatorID", *ADAPTED_FIELDS, *REF_FIELDS}
              and all(_text(row.get(field)) for field in ADAPTED_FIELDS), path=path)
        for field, namespace in allowed.items():
            refs = row.get(field)
            check("battery_observability_reference", _ids(refs) and set(refs) <= namespace, path=f"{path}/{field}")


def compile_candidate(snapshot: dict, candidate: dict, checksum: str) -> tuple[dict, dict]:
    case = deepcopy(snapshot["case_version"])
    design = snapshot["battery_scenario"]
    filename = f"generated-{checksum}.json"
    opening = design["opening"]
    visible_docs = [key for key in design["start_ids"] if not opening or key != opening["material_id"]]
    materials = {row["MaterialID"]: (index, row) for index, row in enumerate(candidate["Материалы"])}
    case["materials"] = [
        {"material_id": key, "order": order, "content": materials[key][1],
         "participant_visible_initially": key in visible_docs,
         "source": _ref(filename, checksum, "Материалы", materials[key][0])}
        for order, key in enumerate(dict.fromkeys([*design["start_ids"], *design["material_ids"]]), 1)
    ]
    case["characters"] = [
        {"character_id": row["CharacterID"], "order": index + 1,
         "content": {**row, "Роль": design["roles"][row["CharacterID"]]["public_label"], "Начальные знания": []},
         "source": _ref(filename, checksum, "Активные персонажи", index)}
        for index, row in enumerate(candidate["Активные персонажи"])
    ]
    for target in case["indicator_targets"]:
        index, adapted = next((i, row) for i, row in enumerate(candidate["IndicatorObservability"])
                              if row["IndicatorID"] == target["indicator_id"])
        target.update(observation_condition=adapted["Конкретное условие"], observable_action=adapted["Форма проявления"],
                      validity_risk=adapted["Дефект потери"],
                      adapted_source=_ref(filename, checksum, "IndicatorObservability", index),
                      **{field: adapted[field] for field in ("material_refs", "event_refs", "character_refs", "authority_refs")})
    case["participant_presentation"] = _participant_presentation(
        case["case_id"], case["passport"], {**candidate, "Стартовые MaterialIDs": visible_docs,
                                             "Заголовок участнику": candidate["Название"]},
        {"path": Path(filename), "sha256": checksum}, case["materials"],
    )
    prepared = PreparedCaseV4.model_validate(case).model_dump(exclude_unset=True)
    runtime = {
        "case_version": case["version"], "characters": case["characters"], "materials": [], "scenario": [],
        "battery_scenario": {**design, "concrete_materials": {key: row for key, (_, row) in materials.items()},
                             "concrete_facts": {row["FactID"]: row["Текст"] for row in candidate["Закрытые фиксированные факты"]}},
    }
    return prepared, {"schema_version": 2, "cases": {case["case_id"]: runtime}}
