"""Frozen v1.2 scenario bindings for the isolated specialist battery."""
from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path

from Api.assessment_case_contracts import PreparedCaseV4
from Api.m5_package import digest
from Api.m5_passport import missing
from Api.m5_passport_v12 import SCENARIO_FIELDS
from scripts.build_m5_sales_package import _participant_presentation, _ref

RULE_PACKAGE = "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.6.0"
FACILITATOR = "FACILITATOR"
PILOT_CASE_SUFFIX = "-pilot.1"
_MATERIAL_LINK = re.compile(r"(?<![\w+/=:@.%-])m5-material://[^\s<>\"'`«»“”‘’(){}\[\]]+")


def material_links(text: str) -> list[tuple[int, str]]:
    """Read complete internal link tokens, keeping suffixes inside the address."""
    return [(match.start(), match.group().rstrip(".,;:!?")) for match in _MATERIAL_LINK.finditer(text)]


def source_case_version(version: str, *, pilot: bool) -> str:
    if pilot and not version.endswith(PILOT_CASE_SUFFIX):
        raise ValueError("M5_BATTERY_PILOT_CASE_VERSION_INVALID")
    return version.removesuffix(PILOT_CASE_SUFFIX) if pilot else version


def load_scenario(case: dict, directory: Path, *, pilot: bool = False) -> dict:
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
        source_case_version(version, pilot=pilot), case["passport_source"]["sha256"],
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
    material_sections = overlay.get("material_sections", {})
    for material_id, headings in material_sections.items():
        if (material_id not in material_ids - fact_ids or not isinstance(headings, list) or not headings
                or any(not isinstance(heading, str) or not heading.strip() or "\n" in heading for heading in headings)
                or len(set(headings)) != len(headings)):
            raise missing(case_id, version, f"17.2/{material_id}/sections")
    for key, role in roles.items():
        if not set(role["known_material_ids"] + role.get("partial_material_ids", [])) <= material_ids - fact_ids:
            raise missing(case_id, version, f"17.2/{key}/Кому известно до начала")
        for material_id, allowed in role.get("known_material_sections", {}).items():
            if (material_id not in role.get("partial_material_ids", ()) or material_id in role["known_material_ids"]
                    or not isinstance(allowed, list) or not allowed or len(allowed) != len(set(allowed))
                    or not set(allowed) < set(material_sections.get(material_id, ()))):
                raise missing(case_id, version, f"17.2/{material_id}/{key}/sections")
    material_source = overlay.get("material_source")
    generation_addendum = overlay.get("generation_addendum")
    if material_source is not None:
        material_id, heading = material_source["material_id"], material_source["section"]
        readers = material_source["reader_ids"]
        opening_evidence = material_source.get("opening_reply_evidence")
        if (material_id not in start["Последовательность предъявления"]
                or heading not in material_sections.get(material_id, ())
                or material_source["link_section"] not in set(material_sections[material_id]) - {heading}
                or not material_source["version_label"].strip() or not material_source["opening_confirmation"].strip()
                or not isinstance(generation_addendum, str)
                or not generation_addendum.strip() or not readers or len(readers) != len(set(readers))
                or not any(row["id"] == material_source["event_id"] and row["kind"] == "transfer_reply"
                           and row.get("reply_confirmation") and set(readers) <= set(row["speaker_ids"]) for row in settings)
                or any(material_id in roles.get(reader, {}).get("known_material_ids", ())
                       or heading in roles.get(reader, {}).get("known_material_sections", {}).get(material_id, ())
                       for reader in readers)):
            raise missing(case_id, version, f"17.2/{material_id}/material_source")
        if "opening_reply_evidence" in material_source and (
                not isinstance(opening_evidence, str) or not opening_evidence.strip()
                or not material_source.get("opening_follow_up")):
            raise missing(case_id, version, "17.3/E01_RECEIPT/opening_reply_evidence")
        if "opening_plain_confirmation" in material_source and (
                material_source["opening_plain_confirmation"] is not True or not opening_evidence):
            raise missing(case_id, version, "17.3/E01_RECEIPT/opening_plain_confirmation")
        if identifier := material_source.get("version_identifier"):
            examples = ", ".join(identifier["examples"])
            generation_addendum += (f"\n{identifier['instruction']} Формат: {identifier['pattern']}. "
                                    f"Примеры идентификаторов: {examples}.")
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
        **({"material_sections": material_sections} if material_sections else {}),
        **({"material_source": material_source, "generation_addendum": generation_addendum} if material_source else {}),
        "events": [
            {**row, "passport": event_by_id[row["id"]],
             "source": case["passport_sources"][f"17.3/{row['id']}"]}
            for row in settings
        ],
    }


def _material_sections(text: str, headings: list[str]) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    heading = None
    for line in text.splitlines():
        if line.strip() in headings:
            heading = line.strip()
            if heading in sections:
                return {}
            sections[heading] = []
        elif heading is not None:
            sections[heading].append(line)
        elif line.strip():
            return {}
    result = {key: "\n".join(lines).strip() for key, lines in sections.items()}
    return result if list(result) == headings and all(result.values()) else {}


def _source_fragment(binding: dict, sections: dict[str, str]) -> dict | None:
    first, _, text = sections[binding["section"]].partition("\n")
    label = binding["version_label"]
    version = first[len(label):].strip() if first.startswith(label) else ""
    identifier = binding.get("version_identifier")
    version_pattern = identifier["pattern"] if identifier else r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
    if not text.strip() or not re.fullmatch(version_pattern, version):
        return None
    material_id = binding["material_id"]
    link = f"m5-material://{material_id}/{version}"
    link_text = sections[binding["link_section"]]
    available_links = ([token for _, token in material_links(link_text)] if identifier
                       else re.findall(r"m5-material://[A-Za-z0-9._/-]+", link_text))
    if link not in available_links:
        return None
    text = text.strip()
    return {"source": {"material_id": material_id, "section": binding["section"], "version": version,
                       "link": link, "fragment_sha256": digest(text.encode())}, "text": text}


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate_profile(profile: dict, design: dict, *, has_work_evidence: bool = False) -> None:
    context = profile.get("user_context") or {}
    role = profile.get("role_profile") or {}
    if not (has_work_evidence or context.get("regular_tasks") or role.get("card", {}).get("regular_tasks")):
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


def validate_candidate(snapshot: dict, value: dict, check, *, detailed: bool = False) -> list[str]:
    from Api.m5_passport_generation import ADAPTED_FIELDS, REF_FIELDS, _indexed, _ids, _text

    missing_paths = []

    def validate(code, passed, path, actual, expected, reason):
        if detailed:
            check(code, passed, actual, path=path, expected=expected, reason=reason)
        else:
            check(code, passed, path=path)

    def record_missing(path, expected, actual):
        if detailed:
            missing_paths.extend(f"{path}/{key}" for key in sorted(set(expected) - set(actual)))

    design = snapshot["battery_scenario"]
    generated_fields = set(snapshot["as_contract"]["fields"])
    sealed = bind(snapshot, {})
    fields = generated_fields | sealed.keys()
    validate("battery_candidate_fields", set(value) == fields, "candidate_as", sorted(value), sorted(fields),
             "Набор полей AS задан контрактом генерации и закреплёнными полями паспорта.")
    record_missing("candidate_as", fields, value)
    if detailed:
        for key, expected in sealed.items():
            actual = value.get(key)
            if key == "RuntimeBindings" and isinstance(actual, dict) and actual.keys() == expected.keys():
                for event_id, rule in expected.items():
                    actual_rule = actual[event_id]
                    if isinstance(actual_rule, dict) and actual_rule.keys() == rule.keys():
                        for field, target in rule.items():
                            validate("battery_event_binding", actual_rule[field] == target,
                                     f"candidate_as/{key}/{event_id}/{field}", actual_rule[field], target,
                                     "Параметр события должен совпадать с закреплённой привязкой сценария.")
                        continue
                    validate("battery_event_binding", actual_rule == rule, f"candidate_as/{key}/{event_id}",
                             actual_rule, rule, "Привязка события должна полностью совпадать с закреплённым правилом.")
                continue
            validate("battery_server_binding", actual == expected, f"candidate_as/{key}", actual, expected,
                     "Значение закреплено точной версией паспорта и сценария.")
    for field in ("AssessmentSituationID", "Version", "Название"):
        actual = value.get(field)
        validate("required_text", _text(actual), f"candidate_as/{field}", actual, "non_empty_string",
                 "Поле идентификации или представления должно быть непустым текстом.")
    substitutions = value.get("Применённые замены")
    substitution_schema = snapshot["as_contract"]["fields"]["Применённые замены"]
    if not isinstance(substitution_schema, dict):
        validate("required_list", isinstance(substitutions, list), "candidate_as/Применённые замены",
                 substitutions, "array", "Замены передаются списком.")
    else:
        if not isinstance(substitutions, list):
            validate("battery_substitution_type", False, "candidate_as/Применённые замены",
                     type(substitutions).__name__, substitution_schema, "Поле должно быть массивом объектов.")
        else:
            expected_fields = set(substitution_schema["items"]["required"])
            for index, row in enumerate(substitutions):
                validate("battery_substitution_item", isinstance(row, dict) and set(row) == expected_fields
                         and all(_text(item) for item in row.values()), f"candidate_as/Применённые замены/{index}",
                         row, substitution_schema["items"],
                         "Подстановка должна содержать место, источник, содержание и предел замены.")
    tables = (
        ("Материалы", "MaterialID", design["material_ids"], ("Название", "Текст")),
        ("Закрытые фиксированные факты", "FactID", design["fact_ids"], ("Текст",)),
        ("Активные персонажи", "CharacterID", design["roles"], ("Имя", "Текст")),
    )
    indexed = {}
    for field, key, ids, required_text in tables:
        path = f"candidate_as/{field}"
        raw_rows = value.get(field)
        rows = _indexed(raw_rows, key)
        actual = ([row.get(key) if isinstance(row, dict) else None for row in raw_rows]
                  if isinstance(raw_rows, list) else raw_rows)
        validate("battery_namespace", rows is not None and rows.keys() == set(ids),
                 path, actual, sorted(ids), "Требуется по одной записи с каждым закреплённым идентификатором.")
        indexed[field] = rows or {}
        if rows is not None:
            record_missing(path, ids, rows)
        for identifier, row in indexed[field].items():
            row_path = f"{path}/{identifier}"
            expected_fields = {key, *required_text}
            invalid_text = {name: row.get(name) for name in required_text if not _text(row.get(name))}
            validate("battery_content_fields", set(row) == expected_fields and not invalid_text, row_path,
                     {"fields": sorted(row), "invalid_text": invalid_text},
                     {"fields": sorted(expected_fields), "non_empty_text_fields": list(required_text)},
                     "Запись должна содержать поля контракта и непустой текст.")
            record_missing(row_path, expected_fields, row)
    documents = indexed["Материалы"]
    for material_id, headings in design.get("material_sections", {}).items():
        text = documents.get(material_id, {}).get("Текст")
        sections = _material_sections(text, headings) if isinstance(text, str) else {}
        binding = design.get("material_source")
        protected = binding and binding["material_id"] == material_id
        actual = None
        if protected:
            found = re.findall(r"(?m)^\s*(\[[^\[\]\r\n]+\])[^\S\r\n]*$", text) if isinstance(text, str) else []
            actual = {"headings": found, "missing": [heading for heading in headings if heading not in found],
                      "unexpected": [heading for heading in found if heading not in headings],
                      "text_type": type(text).__name__}
        path = f"candidate_as/Материалы/{material_id}/Текст"
        validate("battery_material_sections", bool(sections), path, actual, headings,
                 "Разделы с разными правами знания должны иметь точные заголовки, порядок и непустой текст.")
        if not protected or not sections:
            continue
        source = _source_fragment(binding, sections)
        identifier = binding.get("version_identifier")
        validate("battery_material_source", source is not None, path,
                 {"first_line": sections[binding["section"]].splitlines()[0], "link_section": binding["link_section"]},
                 {"version_label": binding["version_label"], "link_template": f"m5-material://{material_id}/<версия>",
                  **({"pattern": identifier["pattern"], "examples": identifier["examples"],
                      "link_example": f"m5-material://{material_id}/{identifier['examples'][0]}"} if identifier else {})},
                 "Укажите точную версию исходного фрагмента и соответствующую ей адресную ссылку.")
        if source is None:
            continue
        protected_text = _normalized_text(source["text"])
        for speaker, role in design["roles"].items():
            if material_id in role["known_material_ids"]:
                continue
            visible = {heading: sections[heading] for heading in role.get("known_material_sections", {}).get(material_id, ())}
            visible.update({key: documents.get(key, {}).get("Текст") for key in role["known_material_ids"]})
            for location, content in visible.items():
                if isinstance(content, str) and protected_text in _normalized_text(content):
                    target_path = path if location in sections else f"candidate_as/Материалы/{location}/Текст"
                    validate("battery_material_knowledge_leak", False, target_path,
                             {"role": speaker, "visible_section": location, "source": source["source"]},
                             {"protected_section": binding["section"]},
                             "Полная копия закрытого фрагмента попала в начальное знание адресата. Удалите её из видимого текста.")
            if identifier:
                visible_ids = set(role["known_material_ids"]) | role.get("known_material_sections", {}).keys()
                for visible_id in sorted(visible_ids):
                    title = documents.get(visible_id, {}).get("Название")
                    if isinstance(title, str) and protected_text in _normalized_text(title):
                        validate("battery_material_knowledge_leak", False, f"candidate_as/Материалы/{visible_id}/Название",
                                 {"role": speaker, "visible_material": visible_id, "source": source["source"]},
                                 {"protected_section": binding["section"]},
                                 "Полная копия закрытого фрагмента попала в видимое название. Оставьте только обычный заголовок.")
    if not detailed:  # Preserve the substring check for the frozen 02 protocol.
        documents = indexed["Материалы"]
        closed = [row for key, row in documents.items() if key not in design["start_ids"]]
        closed.extend(indexed["Закрытые фиксированные факты"].values())
        for key in design["start_ids"]:
            text = documents.get(key, {}).get("Текст")
            if _text(text):
                check("battery_closed_content", not any(
                    _text(row.get("Текст")) and row["Текст"].casefold() in text.casefold() for row in closed
                ), path=f"candidate_as/Материалы/{key}/Текст")
    raw_observed = value.get("IndicatorObservability")
    observed = _indexed(raw_observed, "IndicatorID")
    targets = {row["indicator_id"] for row in snapshot["case_version"]["indicator_targets"]}
    actual = ([row.get("IndicatorID") if isinstance(row, dict) else None for row in raw_observed]
              if isinstance(raw_observed, list) else raw_observed)
    validate("battery_target_set", observed is not None and observed.keys() == targets,
             "candidate_as/IndicatorObservability", actual, sorted(targets),
             "Карта наблюдаемости содержит ровно по одной записи для каждой закреплённой цели.")
    if observed is not None:
        record_missing("candidate_as/IndicatorObservability", targets, observed)
    allowed = {
        "material_refs": set(design["material_ids"]), "event_refs": {row["id"] for row in design["events"]}
        | {design["finish"].get("ID", "SCENARIO_COMPLETION")},
        "character_refs": set(design["roles"]), "authority_refs": {"participant", *(f"character:{key}" for key in design["roles"])},
    }
    for indicator, row in (observed or {}).items():
        path = f"candidate_as/IndicatorObservability/{indicator}"
        fields = {"IndicatorID", *ADAPTED_FIELDS, *REF_FIELDS}
        invalid_text = {name: row.get(name) for name in ADAPTED_FIELDS if not _text(row.get(name))}
        validate("battery_observability", set(row) == fields and not invalid_text, path,
                 {"fields": sorted(row), "invalid_text": invalid_text},
                 {"fields": sorted(fields), "non_empty_text_fields": list(ADAPTED_FIELDS)},
                 "Для наблюдаемости нужны конкретное условие, форма проявления и риск потери.")
        record_missing(path, fields, row)
        for field, namespace in allowed.items():
            refs = row.get(field)
            bound = design["observability_references"].get(indicator, {}).get(field)
            validate("battery_observability_reference",
                     _ids(refs) and set(refs) <= namespace and (not detailed or bound is None or refs == bound),
                     f"{path}/{field}", refs, bound if bound is not None else {"allowed_ids": sorted(namespace)},
                     "Ссылки должны совпадать с закреплёнными местами проектного условия.")
    return missing_paths


def compile_candidate(snapshot: dict, candidate: dict, checksum: str) -> tuple[dict, dict]:
    case = deepcopy(snapshot["case_version"])
    design = snapshot["battery_scenario"]
    filename = f"generated-{checksum}.json"
    opening = design["opening"]
    visible_docs = [key for key in design["start_ids"] if not opening or key != opening["material_id"]]
    materials = {row["MaterialID"]: (index, row) for index, row in enumerate(candidate["Материалы"])}
    source = None
    if binding := design.get("material_source"):
        material_id = binding["material_id"]
        sections = _material_sections(materials[material_id][1]["Текст"], design["material_sections"][material_id])
        source = _source_fragment(binding, sections)
    scoped_materials = {}
    for speaker, role in design["roles"].items():
        for material_id, headings in role.get("known_material_sections", {}).items():
            document = materials[material_id][1]
            sections = _material_sections(document["Текст"], design["material_sections"][material_id])
            scoped_materials.setdefault(speaker, []).append({
                **document, "Текст": "\n\n".join(f"{heading}\n{sections[heading]}" for heading in headings),
            })
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
                             **({"facilitator_grounding": {
                                 "profile": snapshot["profile"],
                                 "participant_grounding": snapshot["participant_grounding"],
                                 **snapshot["participant_grounding_rules"]["facilitator"],
                             }} if "participant_grounding" in snapshot else {}),
                             **({"scoped_materials": scoped_materials} if scoped_materials else {}),
                             **({"linked_material": source} if source else {}),
                             "concrete_facts": {row["FactID"]: row["Текст"] for row in candidate["Закрытые фиксированные факты"]}},
    }
    return prepared, {"schema_version": 2, "cases": {case["case_id"]: runtime}}
