"""Собрать JSON-native draft-пакет девяти Sales Case/AS без промежуточного XLSX."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Api.assessment_case_contracts import CaseVersionV3
from Api.m5_case_runtime import checksum
from Api.m5_package import digest, json_bytes, verify_package_directory

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assessment_definitions/cases/competencies_4k/sales-pilot/0.1"
M2 = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"
M3 = ROOT / "assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json"
BASE_ROLE = "specialist_expert"


def _first(value: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in value:
            return value[key]
    return default


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _ref(name: str, sha256: str, *parts: str | int) -> dict[str, str]:
    pointer = "".join(f"/{_pointer_token(str(part))}" for part in parts)
    return {"file": f"sources/{name}", "sha256": sha256, "pointer": pointer}


def _minutes(value: Any) -> tuple[int, int]:
    if isinstance(value, int) and 0 < value <= 240:
        return value, value
    candidates: list[int] = []
    if isinstance(value, dict):
        preferred = [item for key, item in value.items() if "мин" in key.lower() or "диапазон" in key.lower()]
        values = preferred or list(value.values())
        for item in values:
            candidates.extend(int(number) for number in re.findall(r"(?<!\d)\d{1,3}(?!\d)", str(item)))
    else:
        candidates.extend(int(number) for number in re.findall(r"(?<!\d)\d{1,3}(?!\d)", str(value)))
    candidates = [number for number in candidates if 0 < number <= 240]
    if not candidates:
        raise ValueError("Planned minutes are absent or ambiguous")
    return min(candidates), max(candidates)


def _m2_index() -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for competency in json.loads(M2.read_text())["competencies"]:
        for skill in competency["skills"]:
            for component in skill["components"]:
                for indicator in component["indicators"]:
                    result[indicator["id"]] = (skill["id"], component["id"])
    return result


def _source_entries(source_root: Path) -> tuple[dict, dict[tuple[str, str], dict]]:
    manifest = json.loads((source_root / "manifest.json").read_text())
    selected: dict[tuple[str, str], dict] = {}
    for item in manifest["files"]:
        path = source_root.parent / item["file"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path.read_bytes()) != item["sha256"]:
            raise ValueError(f"Author source checksum mismatch: {item['file']}")
        key = (item["case_id"], item["kind"])
        if key in selected:
            raise ValueError(f"Duplicate selected author source: {key}")
        selected[key] = {**item, "path": path}
    expected = {(f"CASE.SPEC.{number:02d}", kind) for number in range(1, 10) for kind in ("case", "sales_as")}
    if set(selected) != expected:
        raise ValueError(f"Expected exactly nine Case/Sales AS pairs: {sorted(expected ^ set(selected))}")
    return manifest, selected


def _visibility(material: dict[str, Any]) -> bool:
    presentation = " ".join(str(value) for value in (
        _first(material, "Предъявление", "presentation", default=""),
        _first(material, "Когда", "when", default=""),
    )).lower()
    audience = str(_first(material, "Аудитория", "audience", default="")).lower()
    excluded = ("отсутствует в старт", "не при старт", "только по ", "после ")
    return ("старт" in presentation or "сразу" in presentation) and not any(
        marker in presentation for marker in excluded
    ) and not any(
        marker in audience for marker in ("служеб", "оценщ", "систем")
    )


def _readable_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(filter(None, (_readable_text(item) for item in value))).strip()
    if isinstance(value, dict):
        direct = _first(value, "Текст", "text", "content")
        if direct is not None:
            return _readable_text(direct)
        hidden = {"AssessmentSituationID", "MaterialID", "Аудитория", "Предъявление", "Происхождение"}
        lines = []
        for key, item in value.items():
            if key in hidden:
                continue
            rendered = _readable_text(item)
            if rendered:
                lines.append(f"{key}: {rendered}")
        return "\n".join(lines).strip()
    return str(value).strip() if value is not None else ""


def _start_material_ids(situation: dict[str, Any], materials: list[dict[str, Any]]) -> list[str]:
    explicit = situation.get("Стартовые MaterialIDs")
    if isinstance(explicit, list):
        return [str(item) for item in explicit]
    ids = [item["material_id"] for item in materials if item["participant_visible_initially"]]
    start_rules = []
    for key in ("Начальное предъявление", "Объём предъявления", "Правила предъявления", "Правила предъявления и ведения"):
        value = situation.get(key)
        if value is not None:
            start_rules.append(_readable_text(value))
    start_text = "\n".join(start_rules)
    for material_id in re.findall(r"\b(?:P00|M\d{2})\b", start_text):
        if material_id not in ids and not re.search(
            rf"{re.escape(material_id)}[^\n]{{0,80}}(?:отсутствует в старт|только по)", start_text, re.IGNORECASE
        ):
            ids.append(material_id)
    if any(item["material_id"] == "P00" for item in materials) and "P00" not in ids:
        ids.insert(0, "P00")
    return ids


def _organization_name(situation: dict[str, Any]) -> str | None:
    context = situation.get("Контекст") if isinstance(situation.get("Контекст"), dict) else {}
    if str(context.get("Организация") or "").strip():
        return str(context["Организация"]).strip()
    snapshot = situation.get("Контекстный снимок") if isinstance(situation.get("Контекстный снимок"), dict) else {}
    profile = snapshot.get("PersonalizedProfile") if isinstance(snapshot.get("PersonalizedProfile"), dict) else {}
    transfer = profile.get("Передача в M5") if isinstance(profile.get("Передача в M5"), dict) else {}
    return str(transfer.get("Организация") or "").strip() or None


def _participant_presentation(case_id: str, passport: dict[str, Any], situation: dict[str, Any],
                              as_entry: dict, materials: list[dict[str, Any]]) -> dict[str, Any]:
    start_ids = _start_material_ids(situation, materials)
    by_id = {item["material_id"]: item for item in materials}
    p00 = situation.get("P00") if isinstance(situation.get("P00"), dict) else None
    if p00 is not None:
        introduction = _readable_text(p00)
    elif "P00" in by_id:
        introduction = _readable_text(by_id["P00"]["content"])
    else:
        raise ValueError(f"Participant introduction is absent: {case_id}")
    initial_materials = []
    for material_id in start_ids:
        if material_id == "P00":
            continue
        material = by_id.get(material_id)
        if material is None:
            raise ValueError(f"Unknown initial material: {case_id} {material_id}")
        content = material["content"]
        text = _readable_text(content)
        if not text:
            raise ValueError(f"Initial material text is absent: {case_id} {material_id}")
        initial_materials.append({
            "material_id": material_id,
            "title": str(_first(content, "Название", "title", default=material_id)).strip(),
            "text": text,
            "source": material["source"],
        })
    presentation = {
        "assessment_situation_id": str(situation["AssessmentSituationID"]),
        "version": str(_first(situation, "Version", "Версия")),
        "source": _ref(as_entry["path"].name, as_entry["sha256"]),
        "title": str(_first(situation, "Заголовок участнику", default=passport["2 Название"])),
        "introduction": introduction,
        "initial_situation": str(passport["8 Исходная ситуация"]),
        "trigger": str(passport["9 Trigger"]),
        "assessee_position": str(passport["10 Позиция оцениваемого"]),
        "participants_and_positions": str(passport["11 Участники и позиции"]),
        "assessee_task": str(passport["12 Задача оцениваемого"]),
        "conditions_and_constraints": str(passport["13 Условия и ограничения"]),
        "initial_materials": initial_materials,
        "substitution_targets": [],
    }
    organization_name = _organization_name(situation)
    if organization_name:
        values = [("introduction", introduction), *[
            (f"initial_materials.{index}.text", item["text"]) for index, item in enumerate(initial_materials)
        ]]
        for path, text in values:
            if organization_name.casefold() in text.casefold():
                presentation["substitution_targets"].append({
                    "slot": "organization_name", "path": path, "source_value": organization_name,
                })
    return presentation


def _list_or_dict_items(value: Any) -> list[tuple[str | int, dict[str, Any]]]:
    if isinstance(value, list):
        return [(index, item if isinstance(item, dict) else {"value": item}) for index, item in enumerate(value)]
    if isinstance(value, dict):
        return [(key, item if isinstance(item, dict) else {"value": item}) for key, item in value.items()]
    return []


def compile_case_values(*, case: dict, situation: dict, case_source_name: str,
                        case_source_checksum: str, as_source_name: str,
                        as_source_checksum: str,
                        m2: dict[str, tuple[str, str]] | None = None,
                        source_schema_profile: str = "sales-author-json-v1") -> dict:
    """Compile one immutable author/generated full AS into the runtime Case contract."""
    case_entry = {"path": Path(case_source_name), "sha256": case_source_checksum}
    as_entry = {"path": Path(as_source_name), "sha256": as_source_checksum}
    m2 = m2 or _m2_index()
    passport = case["Паспорт"]
    case_id = str(_first(case, "CaseID", default=passport.get("1 CaseID")))
    version = str(_first(case, "Version", "Версия", default=passport.get("7 Version")))
    if situation.get("CaseID") != case_id or situation.get("CaseVersion") != version:
        raise ValueError(f"Case/AS identity mismatch: {case_id} {version}")
    if str(situation.get("BaseRole", "")).strip().lower() != "специалист / эксперт":
        raise ValueError(f"Unexpected Sales base role: {case_id}")
    applicability = []
    for item in passport["14 Applicability"]:
        for component_id in item["ComponentIDs"]:
            applicability.append({"skill_id": item["SkillID"], "component_id": component_id, "required": True})
    observations = situation["IndicatorObservability"]
    targets = []
    for index, item in enumerate(observations):
        indicator_id = str(_first(item, "indicator_id", "IndicatorID"))
        skill_id = str(_first(item, "skill_id", "SkillID"))
        component_id = str(_first(item, "component_id", "ComponentID"))
        if m2.get(indicator_id) != (skill_id, component_id):
            raise ValueError(f"M2 hierarchy mismatch: {case_id} {indicator_id}")
        target = {
            "indicator_id": indicator_id,
            "m2_version": str(_first(item, "version", "Версия M2")),
            "skill_id": skill_id,
            "component_id": component_id,
            "source": _ref(as_entry["path"].name, as_entry["sha256"], "IndicatorObservability", index),
        }
        if source_schema_profile in {"functional-personalization-indicator-v1", "functional-personalization-indicator-v2"}:
            expected_keys = {
                "IndicatorID", "SkillID", "ComponentID", "Название", "Версия M2",
                "Нормативный источник", "Материалы и факты", "Конкретное условие",
                "Что сохранить при адаптации", "Дефект потери", "Форма проявления",
                "Проектная возможность", "Фактическое возникновение", "Evidence и IA",
                "Связанные инварианты",
            }
            if set(item) != expected_keys:
                raise ValueError(
                    f"Unsupported functional IndicatorObservability schema: {case_id} {indicator_id} "
                    f"missing={sorted(expected_keys - set(item))} extra={sorted(set(item) - expected_keys)}"
                )
            runtime_item = item
            runtime_pointer = ("IndicatorObservability", index)
            if source_schema_profile == "functional-personalization-indicator-v2":
                layers = situation.get("IndicatorTargetLayers") or {}
                adapted = ((layers.get("adapted") or {}).get("targets") or [])
                adapted_by_id = {value.get("IndicatorID"): value for value in adapted if isinstance(value, dict)}
                runtime_item = adapted_by_id.get(indicator_id)
                if not isinstance(runtime_item, dict):
                    raise ValueError(f"Missing adapted IndicatorTarget: {case_id} {indicator_id}")
                runtime_pointer = ("IndicatorTargetLayers", "adapted", "targets",
                                   list(adapted_by_id).index(indicator_id))
            condition = runtime_item["Конкретное условие"]
            locations = list(dict.fromkeys(re.findall(r"\bS\d+\b", condition)))
            target.update({
                "observation_condition": condition,
                "scenario_locations": locations,
                "branch_condition": None,
                "event_condition": None,
                "observable_action": runtime_item["Форма проявления"],
                "validity_risk": runtime_item["Дефект потери"],
                "author_title": item["Название"],
                "normative_source": item["Нормативный источник"],
                "material_refs": runtime_item["Материалы и факты"],
                "adaptation_constraints": runtime_item["Что сохранить при адаптации"],
                "design_opportunity": item["Проектная возможность"],
                "actual_occurrence": item["Фактическое возникновение"],
                "evidence_status": item["Evidence и IA"],
                "invariant_refs": item["Связанные инварианты"],
                "condition_absence_reason": "SOURCE_HAS_NO_SEPARATE_BRANCH_OR_EVENT_PREDICATE",
                "author_basis": {
                    "source": _ref(as_entry["path"].name, as_entry["sha256"], "IndicatorObservability", index),
                    "target_checksum": hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True,
                                                                  separators=(",", ":")).encode()).hexdigest(),
                },
                "adapted_source": _ref(as_entry["path"].name, as_entry["sha256"], *runtime_pointer),
            })
        elif source_schema_profile == "sales-author-json-v1":
            target.update({
                "observation_condition": str(_first(item, "Условие возникновения", "Проектные условия наблюдения", "Проектное условие", "Проектные условия")),
                "scenario_locations": [str(_first(item, "Место", "Место или ветвь", default="SOURCE_NOT_SPECIFIED"))],
                "branch_condition": str(_first(item, "Условие возникновения", "Проектные условия наблюдения", "Проектное условие", "Проектные условия")),
                "event_condition": str(_first(item, "Событие возникновения", "Условие возникновения", "Проектное условие", default="SOURCE_NOT_SPECIFIED")),
                "observable_action": str(_first(item, "Доступная форма проявления", "Доступная форма", default="SOURCE_NOT_SPECIFIED")),
                "validity_risk": str(_first(item, "Риск и правило реализации", "Риск потери условий", "Риск реализации", "Риск", default="SOURCE_NOT_SPECIFIED")),
            })
        else:
            raise ValueError(f"Unsupported source schema profile: {source_schema_profile}")
        targets.append(target)
    exact_value = _first(situation, "IndicatorIDs")
    raw_exact_ids = (list(exact_value) if isinstance(exact_value, list) else
                     re.findall(r"K[1-4]\.I\d{2}", json.dumps(passport["22 IndicatorIDs"], ensure_ascii=False)))
    exact_ids = list(dict.fromkeys(raw_exact_ids))
    projected_ids = [item["indicator_id"] for item in targets]
    if len(exact_ids) != len(set(exact_ids)) or set(exact_ids) != set(projected_ids):
        raise ValueError(f"Indicator target projection mismatch: {case_id}")
    material_value = _first(situation, "Материалы", "Материалы участника", default=[])
    materials = []
    for order, (source_key, item) in enumerate(_list_or_dict_items(material_value), 1):
        material_id = str(_first(item, "MaterialID", "DataID", default=f"AS-MATERIAL-{order}"))
        materials.append({"material_id": material_id, "order": order,
                          "participant_visible_initially": _visibility(item), "content": item,
                          "source": _ref(as_entry["path"].name, as_entry["sha256"],
                                         "Материалы" if "Материалы" in situation else "Материалы участника", source_key)})
    scenario_root_key = "Сценарий" if "Сценарий" in situation else "События"
    if scenario_root_key not in situation:
        raise ValueError(f"Required scenario/events field is absent: {case_id}")
    scenario_value = situation[scenario_root_key]
    if isinstance(scenario_value, dict) and "Этапы" in scenario_value:
        scenario_value = scenario_value["Этапы"]
        scenario_parts: tuple[str, ...] = (scenario_root_key, "Этапы")
    else:
        scenario_parts = (scenario_root_key,)
    scenario = []
    for order, (source_key, item) in enumerate(_list_or_dict_items(scenario_value), 1):
        step_id = str(_first(item, "StageID", "StepID", "EventID", default=f"AS-STAGE-{order}"))
        scenario.append({"step_id": step_id, "order": order, "content": item,
                         "source": _ref(as_entry["path"].name, as_entry["sha256"], *scenario_parts, source_key)})
    characters_root_key = "Участники" if "Участники" in situation else "Активные персонажи"
    characters_value = _first(situation, characters_root_key, default=[])
    characters = []
    for order, (source_key, item) in enumerate(_list_or_dict_items(characters_value), 1):
        character_id = str(_first(item, "CharacterID", default=f"AS-CHARACTER-{order}"))
        characters.append({"character_id": character_id, "order": order, "content": item,
                           "source": _ref(as_entry["path"].name, as_entry["sha256"], characters_root_key, source_key)})
    planned = _first(situation, "Плановое время", "Плановое время минут")
    planned_min, planned_max = _minutes(planned)
    passport_sources = {key: _ref(case_entry["path"].name, case_entry["sha256"], "Паспорт", key) for key in passport}
    unresolved = []
    if not characters and case_id not in {"CASE.SPEC.02", "CASE.SPEC.07"}:
        unresolved.append("CHARACTER_PROJECTION_REQUIRES_SLS02")
    result = CaseVersionV3(
        case_id=case_id, version=version, status=str(_first(case, "Status", "Статус")),
        title=str(passport["2 Название"]), base_role=BASE_ROLE, format=str(passport["5 Формат Case"]),
        planned_min_minutes=planned_min, planned_max_minutes=planned_max,
        passport=passport, passport_sources=passport_sources,
        case_type_ids=list(passport["3 CaseTypeIDs"]), applicability=applicability,
        indicator_targets=targets, characters=characters, materials=materials, scenario=scenario,
        author_case=case, author_assessment_situation=situation,
        author_case_source=_ref(case_entry["path"].name, case_entry["sha256"]),
        author_as_source=_ref(as_entry["path"].name, as_entry["sha256"]),
        participant_presentation=_participant_presentation(case_id, passport, situation, as_entry, materials),
        unresolved_decisions=unresolved,
    )
    return result.model_dump()


def _build_case(case_entry: dict, as_entry: dict, m2: dict[str, tuple[str, str]],
                source_schema_profile: str) -> dict:
    case = json.loads(case_entry["path"].read_text())
    situation = json.loads(as_entry["path"].read_text())
    return compile_case_values(
        case=case, situation=situation,
        case_source_name=case_entry["path"].name, case_source_checksum=case_entry["sha256"],
        as_source_name=as_entry["path"].name, as_source_checksum=as_entry["sha256"], m2=m2,
        source_schema_profile=source_schema_profile,
    )


def build_package(source_root: Path, *, source_schema_profile: str = "sales-author-json-v1") -> tuple[dict, dict, list[dict], list[dict]]:
    source_manifest, entries = _source_entries(source_root)
    m2 = _m2_index()
    cases = [_build_case(entries[(f"CASE.SPEC.{number:02d}", "case")],
                         entries[(f"CASE.SPEC.{number:02d}", "sales_as")], m2,
                         source_schema_profile)
             for number in range(1, 10)]
    mapping = [{
        "case_id": case["case_id"], "case_version": case["version"],
        "as_id": _first(case["author_assessment_situation"], "AssessmentSituationID"),
        "as_version": _first(case["author_assessment_situation"], "Version", "Версия"),
        "case_source": case["author_case_source"], "as_source": case["author_as_source"],
        "indicator_ids": [item["indicator_id"] for item in case["indicator_targets"]],
        "characters": len(case["characters"]), "materials": len(case["materials"]),
        "scenario_steps": len(case["scenario"]), "unresolved": case["unresolved_decisions"],
    } for case in cases]
    preview = [{
        "case_id": case["case_id"], "version": case["version"], "title": case["title"],
        "format": case["format"], "planned_minutes": [case["planned_min_minutes"], case["planned_max_minutes"]],
        "presentation": case["participant_presentation"],
        "initial_materials": case["participant_presentation"]["initial_materials"],
    } for case in cases]
    package = {
        "schema_version": 3, "kind": "m5_case_package", "methodology_version": "1.1",
        "version": "0.1", "status": "draft", "source_status": "WORKING", "runtime_enabled": False,
        "scope": {"professional_context": "Sales", "base_role": BASE_ROLE, "case_count": 9,
                  "excluded": ["HR", "mini_cases"]},
        "cases": cases,
        "blockers": ["CASE_DIALOGUE_QA_NOT_RUN",
                     "METHODOLOGY_REVIEW_NOT_APPROVED", "RUNTIME_ADMISSION_DISABLED"],
    }
    return package, source_manifest, mapping, preview


def build_execution_rules(cases: list[dict], event_bindings: dict | None = None) -> dict:
    """Структурирует только явно заданные автором события; не добавляет продуктовых эвристик."""
    result: dict[str, dict] = {}
    for case in cases:
        initial_ids = {item["material_id"] for item in case["participant_presentation"]["initial_materials"]}
        stages = []
        materials = []
        for step in sorted(case["scenario"], key=lambda item: item["order"]):
            content = step["content"]
            event = content.get("Событие") or "author_event"
            occurrence = content.get("Условие возникновения") or content.get("Условие запуска")
            constraints = content.get("Условия") or content.get("Когда запрещено")
            stages.append({
                "step_id": step["step_id"], "order": step["order"], "event": event,
                "condition": occurrence or constraints, "action": content.get("Действие"),
                "state_change": content.get("Изменение состояния"),
                "audience_rule": content.get("Сведения и аудитория"),
                "repeat_rule": content.get("Повторение"), "forbidden_when": constraints,
                "source": step["source"],
            })
            explicit = ((event_bindings or {}).get("case_bindings") or {}).get(case["case_id"], {}).get("events", {}).get(step["step_id"])
            reaction_speakers = (explicit or {}).get("speaker_ids", [])
            legacy_reaction = event == "character_response" or step["step_id"].endswith("_REPLY")
            if (explicit or {}).get("function") == "character_reaction" or (explicit is None and legacy_reaction):
                selected = [item for item in case["characters"]
                            if not reaction_speakers or item["character_id"] in reaction_speakers]
                for character in selected:
                    materials.append({
                        "material_id": (f"CHARACTER.{character['character_id']}.{step['step_id']}"
                                        if explicit is not None else f"CHARACTER.{character['character_id']}"),
                        "kind": "character_reaction", "speaker_id": character["character_id"],
                        "participant_payload": None,
                        "disclosure_condition": {"type": "never"},
                        "event_condition": {"type": "semantic_author_condition", "text": occurrence,
                                            "source": step["source"]},
                        "reaction_rule": content.get("Действие"),
                        "forbidden_when": constraints,
                        "result_check": "Персонаж отвечает только за собственную позицию и полномочия.",
                    })
        for material in sorted(case["materials"], key=lambda item: item["order"]):
            if material["material_id"] in initial_ids or material["material_id"] == "P00":
                continue
            content = material["content"]
            stage_id = str(content.get("Предъявление") or "")
            stage = next((item for item in stages if item["step_id"] in stage_id), None)
            materials.append({
                "material_id": material["material_id"], "kind": "mandatory_update",
                "speaker_id": None, "participant_payload": content,
                "disclosure_condition": {"type": "mandatory"},
                "event_condition": {"type": "semantic_author_condition",
                                    "text": (stage or {}).get("condition"),
                                    "source": (stage or {}).get("source")},
                "reaction_rule": content.get("Комментарий предъявления") or content.get("Предъявление"),
                "result_check": "Материал предъявляется однократно при подтверждённом авторском условии.",
            })
        result[case["case_id"]] = {
            "schema_version": 1, "case_version": case["version"],
            "initial_material_ids": sorted(initial_ids), "actorless": not case["characters"],
            "characters": case["characters"], "materials": materials, "scenario": stages,
        }
    return {"schema_version": 2, "status": "structured_draft", "owner_task": "SLS03", "cases": result}


def write_package(source_root: Path, destination: Path = OUTPUT) -> dict:
    if (destination / "manifest.json").exists():
        existing = json.loads((destination / "manifest.json").read_text())
        if existing.get("status") != "draft":
            raise ValueError("Refusing to overwrite a non-draft package")
    package, source_manifest, mapping, preview = build_package(source_root)
    destination.mkdir(parents=True, exist_ok=True)
    source_dir = destination / "sources"
    source_dir.mkdir(exist_ok=True)
    for item in source_manifest["files"]:
        shutil.copyfile(source_root.parent / item["file"], source_dir / Path(item["file"]).name)
    shutil.copyfile(source_root / "manifest.json", source_dir / "source-selection-manifest.json")
    execution_rules = build_execution_rules(package["cases"])
    verification = {
        "schema_version": 1, "result": "PASS", "scope": "static_sales_package",
        "case_count": 9, "assessment_situation_count": 9,
        "indicator_target_count": sum(len(case["indicator_targets"]) for case in package["cases"]),
        "package_checksum": checksum(package), "case_dialogue_qa": "NOT_RUN",
        "runtime_execution": "NOT_RUN", "m6_execution": "NOT_RUN", "runtime_admission": "DISABLED",
    }
    files = {
        "case-package.json": json_bytes(package),
        "case.schema.json": json_bytes(CaseVersionV3.model_json_schema()),
        "execution-rules.json": json_bytes(execution_rules),
        "mapping-report.json": json_bytes(mapping),
        "participant-preview.json": json_bytes(preview),
        "verification-report.json": json_bytes(verification),
    }
    for name, data in files.items():
        (destination / name).write_bytes(data)
    artifacts = [{"name": name, "sha256": digest(data)} for name, data in sorted(files.items())]
    for path in sorted(source_dir.iterdir()):
        artifacts.append({"name": f"sources/{path.name}", "sha256": digest(path.read_bytes())})
    manifest = {
        "schema_version": 3, "id": "m5-sales-pilot-cases", "version": "0.1", "status": "draft",
        "source_status": "WORKING", "runtime_enabled": False, "artifacts": artifacts,
        "dependencies": {"m2": digest(M2.read_bytes()), "m3": digest(M3.read_bytes())},
        "source_selection": {"handoff_revision": source_manifest["handoff_revision"],
                             "reference_main": source_manifest["reference_main"]},
    }
    (destination / "manifest.json").write_bytes(json_bytes(manifest))
    verify_package_directory(destination)
    return verification


def dry_run(source_root: Path) -> dict:
    package, source_manifest, mapping, _ = build_package(source_root)
    return {
        "mode": "dry_run", "package_schema_version": 3, "case_count": len(package["cases"]),
        "case_versions": mapping, "source_revision": source_manifest["handoff_revision"],
        "package_checksum": checksum(package), "runtime_enabled": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path, nargs="?")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = verify_package_directory(args.output)
    elif args.source_root is None:
        parser.error("source_root is required unless --verify-only is used")
    elif args.dry_run:
        result = dry_run(args.source_root)
    else:
        result = write_package(args.source_root, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
