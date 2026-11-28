"""Use the immutable CaseVersion and the AS result contract to prepare and compile C-34."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from Api.assessment_case_contracts import PreparedCaseV4
from Api.cycle_execution_manifest import M5_FUNCTIONAL_AS_PACKAGE, ROOT
from Api.m5_case_runtime import checksum as runtime_checksum
from Api.m5_package import digest
from Api.m5_passport import compile_passport, load_m2, missing
from Api.m5_runtime_rules import ALLOWED_FUNCTIONS
from scripts.build_m5_sales_package import _participant_presentation, _ref, build_execution_rules

BANK_PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.6"
# The bank builder and cycles without a prompt dependency use the original publication.
AS_PACKAGE = ROOT / "assessment_definitions/prompts/m5_functional_passport/v1"
CURRENT_AS_PACKAGE = ROOT / M5_FUNCTIONAL_AS_PACKAGE
M2 = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"
M3 = ROOT / "assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json"
ADDRESSED_RUNTIME = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization-runtime/1.4.0"
SOURCE_MANIFEST = ROOT / "docs/methodology/source-sets/2026-10-01/manifest.json"

PROMPT_FILES = {
    "generator_prompt": "generator.md", "tester_prompt": "tester.md", "repair_prompt": "repair.md",
    "protocol_challenger": "challenger.md", "protocol_json_retry": "json-retry.md",
    "protocol_tester_addendum": "tester-addendum.md", "generation_contract": "as-contract.json",
}
V2_FILES = {
    **PROMPT_FILES,
    "case_content_contract": "case-content-contract.json",
    "tester_protocol": "tester-protocol.json",
}
ADAPTED_FIELDS = ("Конкретное условие", "Форма проявления", "Дефект потери")
REF_FIELDS = {"material_refs": "Материалы", "event_refs": "События",
              "character_refs": "Активные персонажи", "authority_refs": "authority"}


EVENT_CONDITION_FIELD = "Условие запуска"
LEGACY_EVENT_CONDITION_FIELD = "Условие возникновения"


def read_as_package(directory: Path = AS_PACKAGE) -> tuple[dict, dict, dict]:
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    layout = {
        "1.0.0": (PROMPT_FILES, "1.0.0"),
        "2.0.0": (V2_FILES, "1.0.0"),
        "3.0.0": (V2_FILES, "2.0.0"),
        "4.0.0": (V2_FILES, "2.0.0"),
        "5.0.0": (V2_FILES, "2.1.0"),
        "6.0.0": (V2_FILES, "2.1.0"),
        "7.0.0": (V2_FILES, "2.1.0"),
    }.get(manifest.get("version"))
    if layout is None or (manifest.get("schema_version"), manifest.get("id"), manifest.get("status")) != (
        1, "m5-functional-passport", "draft"
    ):
        raise ValueError("M5_AS_PROMPT_PACKAGE_INVALID")
    files, as_version = layout
    artifacts = {item["name"]: item["sha256"] for item in manifest["artifacts"]}
    if set(artifacts) != set(files.values()) or len(manifest["artifacts"]) != len(files):
        raise ValueError("M5_AS_PROMPT_PACKAGE_INVALID")
    refs = {}
    for key, name in files.items():
        path = directory / name
        if digest(path.read_bytes()) != artifacts[name]:
            raise ValueError(f"M5_AS_PROMPT_CHECKSUM_MISMATCH:{name}")
        refs[key] = {"path": str(path.relative_to(ROOT)), "sha256": artifacts[name]}
    refs["protocol_package"] = {"id": manifest["id"], "version": manifest["version"],
                                "checksum": digest(manifest_raw), "path": str(directory.relative_to(ROOT))}
    contract = json.loads((directory / PROMPT_FILES["generation_contract"]).read_bytes())
    if (contract.get("schema_version"), contract.get("id"), contract.get("version")) != (1, "m5-functional-as", as_version):
        raise ValueError("M5_AS_PROMPT_PACKAGE_INVALID")
    if as_version in {"2.0.0", "2.1.0"} and not (
        isinstance(contract.get("case_as_contract_ref"), dict)
        and isinstance(contract.get("event_material_rules"), dict)
    ):
        raise ValueError("M5_AS_PROMPT_PACKAGE_INVALID")
    ref = {"id": contract["id"], "version": contract["version"], "checksum": artifacts["as-contract.json"]}
    return contract, ref, refs


def read_case_content_contract(path: Path, case_id: str) -> dict | None:
    contract = json.loads(path.read_bytes())
    requirements = contract.get("requirements")
    evidence_sections = contract.get("finding_evidence_sections")
    indicator_fields = contract.get("indicator_fields")
    if not (
        contract.get("schema_version") == 1 and contract.get("id") == "m5-functional-passport-content"
        and contract.get("version") in ("1.0.0", "1.1.0") and _text(contract.get("case_id"))
        and isinstance(requirements, dict) and requirements and all(_text(value) for value in requirements.values())
        and isinstance(evidence_sections, dict) and evidence_sections.keys() == requirements.keys()
        and all(
            _ids(paths) and paths and all(path.startswith("candidate_as/") and all(path.split("/")) for path in paths)
            for paths in evidence_sections.values()
        )
        and isinstance(indicator_fields, dict) and all(_ids(fields) for fields in indicator_fields.values())
        and _ids(contract.get("initial_material_refs_required"))
    ):
        raise ValueError("M5_AS_CASE_CONTENT_CONTRACT_INVALID")
    return contract if contract["case_id"] == case_id else None


def load_bank_case(case_id: str, directory: Path = BANK_PACKAGE) -> tuple[dict, dict]:
    manifest = json.loads((directory / "manifest.json").read_bytes())
    raw = (directory / "case-package.json").read_bytes()
    expected = next(item["sha256"] for item in manifest["artifacts"] if item["name"] == "case-package.json")
    if digest(raw) != expected:
        raise ValueError("M5_BANK_PACKAGE_CHECKSUM_MISMATCH")
    package = json.loads(raw)
    case = next((item for item in package["cases"] if item["case_id"] == case_id), None)
    if case is None:
        raise ValueError(f"M5_CASE_VERSION_NOT_FOUND:{case_id}")
    return case, {"id": manifest["id"], "version": manifest["version"], "checksum": expected,
                  "compiler": manifest["compiler"]}


def normalize_case(case: dict, as_contract_ref: dict, *, m2_path: Path = M2,
                   m3_path: Path = M3) -> tuple[dict, dict, dict]:
    case_id, version = case["case_id"], case["version"]
    old_source = case.get("author_case_source") if case.get("schema_version") == 3 else case.get("passport_source")
    if not old_source:
        raise missing(case_id, version, "passport_source")
    m2, m2_ref = load_m2(m2_path, SOURCE_MANIFEST)
    projected = compile_passport(raw=case["passport"], case_id=case_id, version=version,
                                 status=case["status"], source=old_source, m2=m2,
                                 m3=json.loads(m3_path.read_bytes()), as_contract_ref=as_contract_ref,
                                 selected_base_role=case["base_role"],
                                 passport_version=case.get("passport_version", "1.1"))
    if case.get("schema_version") == 4 and case.get("as_contract_ref") != as_contract_ref:
        raise missing(case_id, version, "as_contract_ref")
    for key in ("base_role", "case_type_ids", "applicability"):
        if case[key] != projected[key]:
            raise missing(case_id, version, f"{key}→passport")
    if case.get("schema_version") == 4 and case != projected:
        raise missing(case_id, version, "CaseVersion→passport")
    return projected, m2_ref, m2


def addressed_candidate_contract(base: dict, design: dict) -> dict:
    candidate = design["candidate_contract"]
    fields = {name: description for name, description in base["fields"].items()
              if name not in candidate["sealed_fields"]}
    fields.update(candidate["field_overrides"])
    return {**base, "fields": fields}


def provider_basis(snapshot: dict) -> dict:
    case_content = snapshot.get("case_content_contract")
    return {"case": snapshot["case"], "profile": snapshot["profile"],
            "normative_indicator_targets": snapshot["case_version"]["indicator_targets"],
            **({"participant_grounding": snapshot["participant_grounding"]} if "participant_grounding" in snapshot else {}),
            **({"project_role": {key: snapshot["project_role"][key] for key in ("code", "interactions")}}
               if "project_role" in snapshot else {}),
            **({"scenario_contract": snapshot["scenario_contract"]} if "scenario_contract" in snapshot else {}),
            **({"scenario_contract": snapshot["battery_scenario"]} if "battery_scenario" in snapshot else {}),
            **({"case_content_contract": case_content,
                "m2_indicator_descriptors": snapshot["m2_indicator_descriptors"]} if case_content else {}),
            **({"event_material_delivery": snapshot["event_material_delivery"]}
               if "event_material_delivery" in snapshot else {}),
            "requirements": {
                "required_top_level_fields_exact": list(snapshot["as_contract"]["fields"]),
                "maximum_output_characters": snapshot["as_contract"]["maximum_output_characters"],
                "base_role": snapshot["case_version"]["base_role"],
                "synthetic_profile": snapshot["synthetic"],
            }}


def compact_review_payload(payload: dict, batch_checks: list[dict]) -> dict:
    """Keep a requirement inline once when the current review already carries it."""
    contract = payload.get("case_content_contract")
    case = payload.get("case")
    if not isinstance(contract, dict) or not isinstance(case, dict):
        return payload
    if (not _text(contract.get("case_id")) or contract["case_id"] != case.get("CaseID")
            or not _text(contract.get("version"))):
        return payload
    requirements = contract.get("requirements")
    if not isinstance(requirements, dict):
        return payload
    repeated = set()
    for check in batch_checks:
        check_id = check.get("check_id")
        requirement = check.get("requirement")
        if not _text(check_id) or not isinstance(requirement, dict):
            continue
        text = requirements.get(check_id)
        passport_or_protocol = requirement.get("passport_or_protocol")
        if (_text(text) and isinstance(passport_or_protocol, (str, dict)) and passport_or_protocol
                and requirement.get("case_content") == text):
            repeated.add(check_id)
    if not repeated:
        return payload
    return {**payload, "case_content_contract": {
        **contract, "requirements": {key: value for key, value in requirements.items() if key not in repeated},
    }}


def _indexed(value: object, key: str) -> dict | None:
    if not isinstance(value, list) or any(
        not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key].strip() for row in value
    ):
        return None
    result = {row[key]: row for row in value}
    return result if len(result) == len(value) else None


def _ids(value: object) -> bool:
    return (isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)
            and len(value) == len(set(value)))


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def build_event_material_delivery(case: dict, case_rules: dict) -> dict:
    scenario = case["passport"]["17 Сценарий Dialogue"]
    start_ids = scenario["На старте"]
    delayed = set(scenario["Функции материалов"]) - set(start_ids)
    # The release suffix changes CaseVersion while retaining the passport source.
    fixed = case_rules.get(case["case_id"], {}).get(case["passport_source"]["sha256"], {})
    assigned = [material_id for rule in fixed.values() for material_id in rule["material_ids"]]
    event_ids = {event["EventID"] for event in scenario["События"]}
    if (not fixed.keys() <= event_ids or not _ids(assigned) or not set(assigned) <= delayed
            or any(rule["function"] not in ALLOWED_FUNCTIONS
                   or bool(rule["material_ids"]) != (rule["function"] == "material_update")
                   for rule in fixed.values())):
        raise missing(case["case_id"], case["version"], "17→event_material_rules")
    unassigned = sorted(delayed - set(assigned))
    if unassigned and fixed.keys() == event_ids:
        raise missing(case["case_id"], case["version"], "17→event_material_rules")
    without_delivery = sorted(ALLOWED_FUNCTIONS - {"material_update"})
    events = {}
    for event in scenario["События"]:
        event_id = event["EventID"]
        if event_id in fixed:
            rule = fixed[event_id]
            delivery = {"functions": [rule["function"]], "material_ids": list(rule["material_ids"])}
        elif unassigned:
            delivery = {"functions": sorted(ALLOWED_FUNCTIONS), "allowed_material_ids": unassigned}
        else:
            delivery = {"functions": without_delivery, "material_ids": []}
        basis = event["Действие"]
        if not delayed:
            basis = f"Все материалы доступны на старте. {basis}"
        events[event_id] = {**delivery, "condition": event["Условие запуска"], "reason": basis}
    return {"start_material_ids": list(start_ids), "events": events}


def bind_event_materials(snapshot: dict, proposed: object) -> tuple[object, list[dict]]:
    delivery = snapshot.get("event_material_delivery")
    if delivery is None or not isinstance(proposed, dict):
        return proposed, []
    bindings = proposed.get("RuntimeBindings")
    if not isinstance(bindings, dict):
        return proposed, []
    starts = set(delivery["start_material_ids"])
    assembled, changes = {}, []
    for event_id, rule in delivery["events"].items():
        binding = bindings.get(event_id)
        if (not isinstance(binding, dict) or "material_ids" not in rule
                or binding.get("function") not in rule["functions"]):
            continue
        expected, actual = rule["material_ids"], binding.get("material_ids")
        if ("material_ids" not in binding
                or (expected == [] and binding["function"] == "facilitator_action"
                    and _ids(actual) and actual and set(actual) <= starts)):
            assembled[event_id] = {**binding, "material_ids": list(expected)}
            changes.append({"path": f"candidate_as/RuntimeBindings/{event_id}/material_ids",
                            "actual": actual, "assembled": list(expected)})
    if not changes:
        return proposed, []
    return {**proposed, "RuntimeBindings": {**bindings, **assembled}}, changes


def _fixed_event_conditions(snapshot: dict) -> dict[str, str]:
    rules = snapshot.get("event_material_delivery", {}).get("events", {})
    return {event_id: rule["condition"] for event_id, rule in rules.items() if rule.get("material_ids")}


def _event_condition_fields(event: dict) -> dict:
    return {key: event[key] for key in (EVENT_CONDITION_FIELD, LEGACY_EVENT_CONDITION_FIELD) if key in event}


def bind_event_conditions(snapshot: dict, proposed: object) -> tuple[object, list[dict]]:
    conditions = _fixed_event_conditions(snapshot)
    if not conditions or not isinstance(proposed, dict):
        return proposed, []
    events = _indexed(proposed.get("События"), "EventID")
    if events is None:
        return proposed, []
    changes = []
    for event_id, event in events.items():
        if event_id not in conditions:
            continue
        actual = _event_condition_fields(event)
        expected = {EVENT_CONDITION_FIELD: conditions[event_id]}
        if actual == expected:
            continue
        bound = {**event, **expected}
        bound.pop(LEGACY_EVENT_CONDITION_FIELD, None)
        events[event_id] = bound
        changes.append({"path": f"candidate_as/События/{event_id}", "actual": actual, "assembled": expected})
    return ({**proposed, "События": list(events.values())} if changes else proposed), changes


def _validate_event_material_delivery(delivery: dict, bindings: object, characters: dict, check) -> None:
    rules = delivery["events"]
    path = "candidate_as/RuntimeBindings"
    check("runtime_event_set", isinstance(bindings, dict) and bindings.keys() == rules.keys(),
          list(bindings) if isinstance(bindings, dict) else bindings, path=path, expected=list(rules),
          reason="Карта выдачи должна содержать события закреплённого паспорта.")
    if not isinstance(bindings, dict):
        return
    start_ids = set(delivery["start_material_ids"])
    flexible_ids = {material for rule in rules.values() for material in rule.get("allowed_material_ids", ())}
    known_ids = start_ids | flexible_ids | {material for rule in rules.values() for material in rule.get("material_ids", ())}
    assigned = []
    for event_id, binding in bindings.items():
        if event_id not in rules:
            continue
        rule = rules[event_id]
        event_path = f"{path}/{event_id}"
        fields = ["function", "speaker_ids", "material_ids"]
        if not isinstance(binding, dict) or binding.keys() != set(fields):
            check("runtime_event_binding", False, binding, path=event_path, expected=fields,
                  reason="Ожидается привязка события с типом действия, участниками и списком выдачи.")
            continue
        function, speakers, actual = (binding[key] for key in fields)
        functions = rule["functions"]
        check("runtime_event_binding", function in functions, function, path=f"{event_path}/function",
              expected=functions[0] if len(functions) == 1 else functions,
              reason=f"Тип действия должен соответствовать правилу выдачи. {rule['reason']}")
        speaker_options = {"allowed_speaker_ids": list(characters)} if function == "character_reaction" else {"expected": []}
        check("runtime_event_binding", _ids(speakers) and set(speakers) <= characters.keys()
              and bool(speakers) == (function == "character_reaction"), speakers,
              path=f"{event_path}/speaker_ids",
              reason="Для реакции нужен хотя бы один известный персонаж. Для остальных действий список пуст.",
              **speaker_options)
        if "material_ids" in rule or function != "material_update":
            expected = rule.get("material_ids", [])
            valid = actual == expected
            options = {"expected": expected}
        else:
            allowed = rule["allowed_material_ids"]
            valid = _ids(actual) and bool(actual) and set(actual) <= set(allowed)
            options = {"allowed_material_ids": allowed, "condition": rule["condition"]}
            if valid:
                assigned.extend(actual)
        reason = rule["reason"]
        if not valid and isinstance(actual, list) and all(isinstance(item, str) for item in actual):
            if set(actual) - known_ids:
                reason = f"Список содержит неизвестный MaterialID. {reason}"
            elif len(actual) != len(set(actual)):
                reason = f"MaterialID повторяется в списке выдачи. {reason}"
            elif rule.get("material_ids"):
                reason = f"Сохраните обязательную выдачу на этом событии. {reason}"
            elif set(actual) - start_ids:
                reason = f"Материал недоступен для выдачи на этом событии. {reason}"
        check("runtime_event_binding", valid, actual, path=f"{event_path}/material_ids", reason=reason, **options)
    if flexible_ids:
        check("runtime_delayed_materials", set(assigned) == flexible_ids and len(assigned) == len(flexible_ids),
              assigned, path=path, expected=sorted(flexible_ids),
              reason="Каждый доступный для событийной выдачи материал должен появиться ровно один раз.")


def validate_candidate(snapshot: dict, candidate: dict, check) -> list[str]:
    """Validate the shape and identify required elements that can be cited as absent."""
    content_contract = snapshot.get("case_content_contract", {})
    missing_paths = []

    def record_missing(expected, present, parent):
        if content_contract:
            missing_paths.extend(f"{parent}/{key}" for key in sorted(set(expected) - set(present)))

    passport = snapshot["case"]["Паспорт"]
    case = snapshot["case_version"]
    scenario = passport["17 Сценарий Dialogue"]
    targets = passport["22 IndicatorIDs"]
    required = snapshot["as_contract"]["fields"]
    check("top_level_contract", set(candidate) == set(required),
          {"missing": sorted(set(required) - set(candidate)), "extra": sorted(set(candidate) - set(required))})
    record_missing(required, candidate, "candidate_as")
    design = snapshot.get("scenario_contract")
    expected_fields = {
        "CaseID": case["case_id"], "CaseVersion": case["version"], "BaseRole": case["base_role"],
        "CaseTypeIDs": case["case_type_ids"], "IndicatorIDs": targets["Точный перечень"],
        "Версии M2": targets["Версии M2"],
    }
    if design is None:
        expected_fields["Стартовые MaterialIDs"] = scenario["На старте"]
    for name, value in expected_fields.items():
        check("passport_binding", candidate.get(name) == value, path=f"candidate_as/{name}")
    for field in ("AssessmentSituationID", "Version", "Название"):
        check("required_text", _text(candidate.get(field)), path=f"candidate_as/{field}")
    for field in ("Применённые замены", "Закрытые фиксированные факты"):
        check("required_list", isinstance(candidate.get(field), list), path=f"candidate_as/{field}")
    namespaces = {}
    for field, key in (("Материалы", "MaterialID"), ("Активные персонажи", "CharacterID"), ("События", "EventID")):
        if design and field == "События":
            namespaces[field] = design["events"]
        else:
            index = _indexed(candidate.get(field), key)
            check("namespace_shape:" + key, index is not None, path=f"candidate_as/{field}")
            namespaces[field] = index or {}
    materials, characters, events = (namespaces[key] for key in ("Материалы", "Активные персонажи", "События"))
    check("passport_material_set", set(materials) == set(scenario["Функции материалов"]), path="candidate_as/Материалы")
    record_missing(scenario["Функции материалов"], materials, "candidate_as/Материалы")
    check("character_count", len(characters) == passport["19 Параметры сложности"]["Фиксировано"]["Активные персонажи"],
          path="candidate_as/Активные персонажи")
    for material_id, material in materials.items():
        path = f"candidate_as/Материалы/{material_id}"
        check("participant_material_text", _text(material.get("Текст")) and _text(material.get("Название")),
              path=path)
        record_missing(("Название", "Текст"), material, path)
    if design is None:
        check("passport_event_sequence", list(events) == [event["EventID"] for event in scenario["События"]],
              path="candidate_as/События")
        record_missing((event["EventID"] for event in scenario["События"]), events, "candidate_as/События")
        for character_id, character in characters.items():
            path = f"candidate_as/Активные персонажи/{character_id}"
            check("character_card", all(_text(character.get(field)) for field in ("Имя", "Роль", "Текст"))
                  and isinstance(character.get("Начальные знания"), list), path=path)
            record_missing(("Имя", "Роль", "Текст", "Начальные знания"), character, path)
        event_fields = (
            "Действие", "Изменение состояния", "Когда запрещено", "Повторение", "Сведения и аудитория", EVENT_CONDITION_FIELD,
        )
        conditions = _fixed_event_conditions(snapshot)
        for event_id, event in events.items():
            path = f"candidate_as/События/{event_id}"
            check("scenario_event", all(_text(event.get(field)) for field in event_fields), path=path)
            record_missing(event_fields, event, path)
            if event_id in conditions:
                expected = {EVENT_CONDITION_FIELD: conditions[event_id]}
                actual = _event_condition_fields(event)
                check("runtime_event_condition", actual == expected, actual, path=path, expected=expected,
                      reason="Условие фиксированной выдачи должно совпадать с закреплённым паспортом.")
        bindings = candidate.get("RuntimeBindings")
        if isinstance(bindings, dict):
            record_missing(events, bindings, "candidate_as/RuntimeBindings")
            for event_id, binding in bindings.items():
                if isinstance(binding, dict):
                    record_missing(("function", "speaker_ids", "material_ids"), binding,
                                   f"candidate_as/RuntimeBindings/{event_id}")
        if "event_material_delivery" in snapshot:
            _validate_event_material_delivery(snapshot["event_material_delivery"], bindings, characters, check)
        else:
            _validate_legacy_event_bindings(scenario, bindings, materials, characters, events, check)
    else:
        _validate_addressed_content(candidate, design, materials, characters, check)
    observed = _indexed(candidate.get("IndicatorObservability"), "IndicatorID") or {}
    check("indicator_adapted_target_set", set(observed) == set(targets["Точный перечень"]),
          path="candidate_as/IndicatorObservability")
    record_missing(targets["Точный перечень"], observed, "candidate_as/IndicatorObservability")
    namespaces["authority"] = {"participant", *(f"character:{key}" for key in characters)}
    indicator_fields = content_contract.get("indicator_fields", {})
    requires_initial_refs = set(content_contract.get("initial_material_refs_required", ()))
    initial_materials = set(scenario["На старте"]) & materials.keys()
    for indicator_id, item in observed.items():
        path = f"candidate_as/IndicatorObservability/{indicator_id}"
        extra_fields = indicator_fields.get(indicator_id, [])
        check("indicator_adapted_condition", set(item) - set(extra_fields) == {"IndicatorID", *ADAPTED_FIELDS, *REF_FIELDS}
              and all(_text(item.get(field)) for field in ADAPTED_FIELDS), path=path)
        record_missing((*ADAPTED_FIELDS, *REF_FIELDS, *extra_fields), item, path)
        for field in extra_fields:
            check("indicator_adaptation_required_text", _text(item.get(field)), path=f"{path}/{field}")
        for field, namespace in REF_FIELDS.items():
            values = item.get(field)
            ref_path = f"{path}/{field}"
            references_valid = _ids(values) and set(values) <= set(namespaces[namespace])
            check("indicator_adaptation_references", references_valid, path=ref_path)
            if references_valid and field == "material_refs" and indicator_id in requires_initial_refs:
                check("indicator_initial_material_ref_required", not initial_materials.isdisjoint(values), path=ref_path)

    if design:
        for indicator_id, refs in design["required_observability"].items():
            for field, required_refs in refs.items():
                check("required_scenario_observability", observed.get(indicator_id, {}).get(field) == required_refs,
                      path=f"candidate_as/IndicatorObservability/{indicator_id}/{field}")
    return missing_paths


def _validate_legacy_event_bindings(scenario: dict, bindings: object, materials: dict,
                                    characters: dict, events: dict, check) -> None:
    delayed = set(materials) - set(scenario["На старте"])
    check("runtime_event_set", isinstance(bindings, dict) and bindings.keys() == events.keys(),
          path="candidate_as/RuntimeBindings")
    bound_materials = []
    for event_id, binding in (bindings.items() if isinstance(bindings, dict) else ()):
        path = f"candidate_as/RuntimeBindings/{event_id}"
        if not isinstance(binding, dict) or set(binding) != {"function", "speaker_ids", "material_ids"}:
            check("runtime_event_binding", False, path=path)
            continue
        function, speaker_ids, material_ids = (binding[key] for key in ("function", "speaker_ids", "material_ids"))
        check("runtime_event_binding", isinstance(function, str) and function in ALLOWED_FUNCTIONS
              and _ids(speaker_ids) and set(speaker_ids) <= set(characters)
              and _ids(material_ids) and set(material_ids) <= delayed
              and bool(speaker_ids) == (function == "character_reaction")
              and bool(material_ids) == (function == "material_update"), path=path)
        if _ids(material_ids):
            bound_materials.extend(material_ids)
    check("runtime_delayed_materials", set(bound_materials) == delayed and len(bound_materials) == len(delayed),
          path="candidate_as/RuntimeBindings")


def _validate_addressed_content(candidate: dict, design: dict, materials: dict, characters: dict, check) -> None:
    for field in design["candidate_contract"]["sealed_fields"]:
        check("server_bound_scenario_field", field not in candidate, path=f"candidate_as/{field}")
    check("scenario_character_ids", set(characters) == set(design["roles"]), path="candidate_as/Активные персонажи")
    material_fields = {"MaterialID", "Название", "Текст"}
    for material_id, material in materials.items():
        check("scenario_editable_material_fields", set(material) == material_fields,
              path=f"candidate_as/Материалы/{material_id}")
    character_fields = {"CharacterID", "Имя", "Роль", "Текст", "Мандат", "Границы реакций"}
    for character_id, card in characters.items():
        facts = card.get("Начальные знания")
        check("scenario_character_card", set(card) == {*character_fields, "Начальные знания"}
              and all(_text(card.get(field)) for field in character_fields)
              and isinstance(facts, list) and all(_text(fact) for fact in facts),
              path=f"candidate_as/Активные персонажи/{character_id}")

    update_id = design["events"]["E01_UPDATE"]["material_ids"][0]
    update = materials.get(update_id, {}).get("Текст")
    if not _text(update):
        return
    closed_text = " ".join(update.casefold().split())
    visible = {"Название": candidate.get("Название")}
    for material_id in design["start_material_ids"]:
        for field in ("Название", "Текст"):
            visible[f"Материалы/{material_id}/{field}"] = materials.get(material_id, {}).get(field)
    for character_id, card in characters.items():
        for field, value in card.items():
            if isinstance(value, list):
                value = " ".join(item for item in value if isinstance(item, str))
            visible[f"Активные персонажи/{character_id}/{field}"] = value
    for path, value in visible.items():
        if _text(value):
            check("delayed_content_leak", closed_text not in " ".join(value.casefold().split()),
                  path=f"candidate_as/{path}")


def compile_candidate(snapshot: dict, candidate: dict, candidate_checksum: str) -> tuple[dict, dict]:
    value = deepcopy(snapshot["case_version"])
    design = snapshot.get("scenario_contract")
    start_ids = design["start_material_ids"] if design else candidate["Стартовые MaterialIDs"]
    starts = set(start_ids)
    filename = f"generated-{candidate_checksum}.json"
    for field, key, kind in (("Материалы", "MaterialID", "materials"),
                             ("Активные персонажи", "CharacterID", "characters"), ("События", "EventID", "scenario")):
        if design and kind == "scenario":
            continue
        id_key = {"materials": "material_id", "characters": "character_id", "scenario": "step_id"}[kind]
        value[kind] = [
            {id_key: item[key], "order": index + 1, "content": item, "source": _ref(filename, candidate_checksum, field, index)}
            for index, item in enumerate(candidate[field])
        ]
    for material in value["materials"]:
        material["participant_visible_initially"] = material["material_id"] in starts
    adapted = {item["IndicatorID"]: (index, item) for index, item in enumerate(candidate["IndicatorObservability"])}
    for target in value["indicator_targets"]:
        index, concrete = adapted[target["indicator_id"]]
        if design:
            concrete = {**concrete, **design["required_observability"].get(target["indicator_id"], {})}
        target.update(observation_condition=concrete["Конкретное условие"], observable_action=concrete["Форма проявления"],
                      validity_risk=concrete["Дефект потери"], scenario_locations=concrete["event_refs"],
                      adapted_source=_ref(filename, candidate_checksum, "IndicatorObservability", index),
                      **{field: concrete[field] for field in REF_FIELDS})
    value["participant_presentation"] = _participant_presentation(
        value["case_id"], value["passport"], {**candidate, "Заголовок участнику": candidate["Название"],
                                             "Стартовые MaterialIDs": start_ids},
        {"path": Path(filename), "sha256": candidate_checksum}, value["materials"],
    )
    prepared = PreparedCaseV4.model_validate(value).model_dump(exclude_unset=True)
    bindings = {"case_bindings": {value["case_id"]: {
        "case_version": value["version"], "case_checksum": runtime_checksum(prepared),
        "events": design["events"] if design else candidate["RuntimeBindings"],
    }}}
    rules = build_execution_rules([prepared], bindings)
    if design:
        case_rules = rules["cases"][value["case_id"]]
        case_rules["scenario_contract"] = design
        update = design["events"]["E01_UPDATE"]
        delayed = next(item for item in case_rules["materials"] if item["material_id"] == update["material_ids"][0])
        delayed["speaker_id"] = update["speaker_ids"][0]
        delayed["event_condition"]["text"] = update["condition"]
    return prepared, rules
