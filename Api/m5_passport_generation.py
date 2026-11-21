"""Use the immutable CaseVersion and the AS result contract to prepare and compile C-34."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from Api.assessment_case_contracts import PreparedCaseV4
from Api.cycle_execution_manifest import ROOT
from Api.m5_case_runtime import checksum as runtime_checksum
from Api.m5_package import digest
from Api.m5_passport import compile_passport, load_m2, missing
from Api.m5_runtime_rules import ALLOWED_FUNCTIONS
from scripts.build_m5_sales_package import _participant_presentation, _ref, build_execution_rules

BANK_PACKAGE = ROOT / "assessment_definitions/cases/competencies_4k/functional-personalization/0.6"
AS_PACKAGE = ROOT / "assessment_definitions/prompts/m5_functional_passport/v1"
M2 = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"
M3 = ROOT / "assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json"
SOURCE_MANIFEST = ROOT / "docs/methodology/source-sets/2026-10-01/manifest.json"

PROMPT_FILES = {
    "generator_prompt": "generator.md", "tester_prompt": "tester.md", "repair_prompt": "repair.md",
    "protocol_challenger": "challenger.md", "protocol_json_retry": "json-retry.md",
    "protocol_tester_addendum": "tester-addendum.md", "generation_contract": "as-contract.json",
}
ADAPTED_FIELDS = ("Конкретное условие", "Форма проявления", "Дефект потери")
REF_FIELDS = {"material_refs": "Материалы", "event_refs": "События",
              "character_refs": "Активные персонажи", "authority_refs": "authority"}


def read_as_package(directory: Path = AS_PACKAGE) -> tuple[dict, dict, dict]:
    manifest_raw = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    if (manifest["schema_version"], manifest["id"], manifest["version"]) != (1, "m5-functional-passport", "1.0.0"):
        raise ValueError("M5_AS_PROMPT_PACKAGE_INVALID")
    artifacts = {item["name"]: item["sha256"] for item in manifest["artifacts"]}
    if set(artifacts) != set(PROMPT_FILES.values()):
        raise ValueError("M5_AS_PROMPT_PACKAGE_INVALID")
    refs = {}
    for key, name in PROMPT_FILES.items():
        path = directory / name
        if digest(path.read_bytes()) != artifacts[name]:
            raise ValueError(f"M5_AS_PROMPT_CHECKSUM_MISMATCH:{name}")
        refs[key] = {"path": str(path.relative_to(ROOT)), "sha256": artifacts[name]}
    refs["protocol_package"] = {"id": manifest["id"], "version": manifest["version"],
                                "checksum": digest(manifest_raw), "path": str(directory.relative_to(ROOT))}
    contract = json.loads((directory / PROMPT_FILES["generation_contract"]).read_bytes())
    ref = {"id": contract["id"], "version": contract["version"], "checksum": artifacts["as-contract.json"]}
    return contract, ref, refs


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
                   m3_path: Path = M3) -> tuple[dict, dict]:
    case_id, version = case["case_id"], case["version"]
    old_source = case.get("author_case_source") if case.get("schema_version") == 3 else case.get("passport_source")
    if not old_source:
        raise missing(case_id, version, "passport_source")
    m2, m2_ref = load_m2(m2_path, SOURCE_MANIFEST)
    projected = compile_passport(raw=case["passport"], case_id=case_id, version=version,
                                 status=case["status"], source=old_source, m2=m2,
                                 m3=json.loads(m3_path.read_bytes()), as_contract_ref=as_contract_ref,
                                 selected_base_role=case["base_role"])
    if case.get("schema_version") == 4 and case.get("as_contract_ref") != as_contract_ref:
        raise missing(case_id, version, "as_contract_ref")
    for key in ("base_role", "case_type_ids", "applicability"):
        if case[key] != projected[key]:
            raise missing(case_id, version, f"{key}→passport")
    if case.get("schema_version") == 4 and case != projected:
        raise missing(case_id, version, "CaseVersion→passport")
    return projected, m2_ref


def provider_basis(snapshot: dict) -> dict:
    return {"case": snapshot["case"], "profile": snapshot["profile"],
            "normative_indicator_targets": snapshot["case_version"]["indicator_targets"],
            "requirements": {
                "required_top_level_fields_exact": list(snapshot["as_contract"]["fields"]),
                "maximum_output_characters": snapshot["as_contract"]["maximum_output_characters"],
                "base_role": snapshot["case_version"]["base_role"],
                "synthetic_profile": snapshot["synthetic"],
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


def validate_candidate(snapshot: dict, candidate: dict, check) -> None:
    passport = snapshot["case"]["Паспорт"]
    case = snapshot["case_version"]
    scenario = passport["17 Сценарий Dialogue"]
    targets = passport["22 IndicatorIDs"]
    required = snapshot["as_contract"]["fields"]
    check("top_level_contract", set(candidate) == set(required),
          {"missing": sorted(set(required) - set(candidate)), "extra": sorted(set(candidate) - set(required))})
    for name, value in {
        "CaseID": case["case_id"], "CaseVersion": case["version"], "BaseRole": case["base_role"],
        "CaseTypeIDs": case["case_type_ids"], "IndicatorIDs": targets["Точный перечень"],
        "Версии M2": targets["Версии M2"], "Стартовые MaterialIDs": scenario["На старте"],
    }.items():
        check("passport_binding", candidate.get(name) == value, path=f"candidate_as/{name}")
    for field in ("AssessmentSituationID", "Version", "Название"):
        check("required_text", _text(candidate.get(field)), path=f"candidate_as/{field}")
    for field in ("Применённые замены", "Закрытые фиксированные факты"):
        check("required_list", isinstance(candidate.get(field), list), path=f"candidate_as/{field}")
    namespaces = {}
    for field, key in (("Материалы", "MaterialID"), ("Активные персонажи", "CharacterID"), ("События", "EventID")):
        index = _indexed(candidate.get(field), key)
        check("namespace_shape:" + key, index is not None, path=f"candidate_as/{field}")
        namespaces[field] = index or {}
    materials, characters, events = (namespaces[key] for key in ("Материалы", "Активные персонажи", "События"))
    check("passport_material_set", set(materials) == set(scenario["Функции материалов"]), path="candidate_as/Материалы")
    check("character_count", len(characters) == passport["19 Параметры сложности"]["Фиксировано"]["Активные персонажи"],
          path="candidate_as/Активные персонажи")
    check("passport_event_sequence", list(events) == [event["EventID"] for event in scenario["События"]],
          path="candidate_as/События")
    for material_id, material in materials.items():
        check("participant_material_text", _text(material.get("Текст")) and _text(material.get("Название")),
              path=f"candidate_as/Материалы/{material_id}")
    for character_id, character in characters.items():
        check("character_card", all(_text(character.get(field)) for field in ("Имя", "Роль", "Текст"))
              and isinstance(character.get("Начальные знания"), list), path=f"candidate_as/Активные персонажи/{character_id}")
    for event_id, event in events.items():
        check("scenario_event", all(_text(event.get(field)) for field in (
            "Действие", "Изменение состояния", "Когда запрещено", "Повторение", "Сведения и аудитория", "Условие запуска"
        )), path=f"candidate_as/События/{event_id}")
    delayed = set(materials) - set(scenario["На старте"])
    bindings = candidate.get("RuntimeBindings")
    check("runtime_event_set", isinstance(bindings, dict) and set(bindings) == set(events), path="candidate_as/RuntimeBindings")
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
    observed = _indexed(candidate.get("IndicatorObservability"), "IndicatorID") or {}
    check("indicator_adapted_target_set", set(observed) == set(targets["Точный перечень"]),
          path="candidate_as/IndicatorObservability")
    namespaces["authority"] = {"participant", *(f"character:{key}" for key in characters)}
    for indicator_id, item in observed.items():
        path = f"candidate_as/IndicatorObservability/{indicator_id}"
        check("indicator_adapted_condition", set(item) == {"IndicatorID", *ADAPTED_FIELDS, *REF_FIELDS}
              and all(_text(item.get(field)) for field in ADAPTED_FIELDS), path=path)
        for field, namespace in REF_FIELDS.items():
            values = item.get(field)
            check("indicator_adaptation_references", _ids(values) and set(values) <= set(namespaces[namespace]),
                  path=f"{path}/{field}")


def compile_candidate(snapshot: dict, candidate: dict, candidate_checksum: str) -> tuple[dict, dict]:
    value = deepcopy(snapshot["case_version"])
    starts = set(candidate["Стартовые MaterialIDs"])
    filename = f"generated-{candidate_checksum}.json"
    for field, key, kind in (("Материалы", "MaterialID", "materials"),
                             ("Активные персонажи", "CharacterID", "characters"), ("События", "EventID", "scenario")):
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
        target.update(observation_condition=concrete["Конкретное условие"], observable_action=concrete["Форма проявления"],
                      validity_risk=concrete["Дефект потери"], scenario_locations=concrete["event_refs"],
                      adapted_source=_ref(filename, candidate_checksum, "IndicatorObservability", index),
                      **{field: concrete[field] for field in REF_FIELDS})
    value["participant_presentation"] = _participant_presentation(
        value["case_id"], value["passport"], {**candidate, "Заголовок участнику": candidate["Название"]},
        {"path": Path(filename), "sha256": candidate_checksum}, value["materials"],
    )
    prepared = PreparedCaseV4.model_validate(value).model_dump(exclude_unset=True)
    bindings = {"case_bindings": {value["case_id"]: {
        "case_version": value["version"], "case_checksum": runtime_checksum(prepared),
        "events": candidate["RuntimeBindings"],
    }}}
    return prepared, build_execution_rules([prepared], bindings)
