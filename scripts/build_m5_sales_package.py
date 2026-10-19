"""Собрать JSON-native draft-пакет девяти Sales Case/AS без промежуточного XLSX."""
from __future__ import annotations

import argparse
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
    presentation = str(_first(material, "Предъявление", "presentation", default="")).lower()
    audience = str(_first(material, "Аудитория", "audience", default="")).lower()
    return ("старт" in presentation or "сразу" in presentation) and not any(
        marker in audience for marker in ("служеб", "оценщ", "систем")
    )


def _list_or_dict_items(value: Any) -> list[tuple[str | int, dict[str, Any]]]:
    if isinstance(value, list):
        return [(index, item if isinstance(item, dict) else {"value": item}) for index, item in enumerate(value)]
    if isinstance(value, dict):
        return [(key, item if isinstance(item, dict) else {"value": item}) for key, item in value.items()]
    return []


def _build_case(case_entry: dict, as_entry: dict, m2: dict[str, tuple[str, str]]) -> dict:
    case = json.loads(case_entry["path"].read_text())
    situation = json.loads(as_entry["path"].read_text())
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
        targets.append({
            "indicator_id": indicator_id,
            "m2_version": str(_first(item, "version", "Версия M2")),
            "skill_id": skill_id,
            "component_id": component_id,
            "observation_condition": str(_first(item, "Условие возникновения", "Проектные условия наблюдения", "Проектное условие", "Проектные условия")),
            "scenario_locations": [str(_first(item, "Место", "Место или ветвь", default="SOURCE_NOT_SPECIFIED"))],
            "branch_condition": str(_first(item, "Условие возникновения", "Проектные условия наблюдения", "Проектное условие", "Проектные условия")),
            "event_condition": str(_first(item, "Событие возникновения", "Условие возникновения", "Проектное условие", default="SOURCE_NOT_SPECIFIED")),
            "observable_action": str(_first(item, "Доступная форма проявления", "Доступная форма", default="SOURCE_NOT_SPECIFIED")),
            "validity_risk": str(_first(item, "Риск и правило реализации", "Риск потери условий", "Риск реализации", "Риск", default="SOURCE_NOT_SPECIFIED")),
            "source": _ref(as_entry["path"].name, as_entry["sha256"], "IndicatorObservability", index),
        })
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
    scenario_root_key = "Сценарий"
    scenario_value = situation[scenario_root_key]
    if isinstance(scenario_value, dict) and "Этапы" in scenario_value:
        scenario_value = scenario_value["Этапы"]
        scenario_parts: tuple[str, ...] = (scenario_root_key, "Этапы")
    else:
        scenario_parts = (scenario_root_key,)
    scenario = []
    for order, (source_key, item) in enumerate(_list_or_dict_items(scenario_value), 1):
        step_id = str(_first(item, "StageID", "StepID", default=f"AS-STAGE-{order}"))
        scenario.append({"step_id": step_id, "order": order, "content": item,
                         "source": _ref(as_entry["path"].name, as_entry["sha256"], *scenario_parts, source_key)})
    characters_value = _first(situation, "Участники", default=[])
    characters = []
    for order, (source_key, item) in enumerate(_list_or_dict_items(characters_value), 1):
        character_id = str(_first(item, "CharacterID", default=f"AS-CHARACTER-{order}"))
        characters.append({"character_id": character_id, "order": order, "content": item,
                           "source": _ref(as_entry["path"].name, as_entry["sha256"], "Участники", source_key)})
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
        unresolved_decisions=unresolved,
    )
    return result.model_dump()


def build_package(source_root: Path) -> tuple[dict, dict, list[dict], list[dict]]:
    source_manifest, entries = _source_entries(source_root)
    m2 = _m2_index()
    cases = [_build_case(entries[(f"CASE.SPEC.{number:02d}", "case")],
                         entries[(f"CASE.SPEC.{number:02d}", "sales_as")], m2)
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
        "opening": _first(case["author_assessment_situation"], "P00", "Заголовок участнику"),
        "initial_materials": [{"material_id": item["material_id"], "content": item["content"]}
                              for item in case["materials"] if item["participant_visible_initially"]],
    } for case in cases]
    package = {
        "schema_version": 3, "kind": "m5_case_package", "methodology_version": "1.1",
        "version": "0.1", "status": "draft", "source_status": "WORKING", "runtime_enabled": False,
        "scope": {"professional_context": "Sales", "base_role": BASE_ROLE, "case_count": 9,
                  "excluded": ["HR", "mini_cases"]},
        "cases": cases,
        "blockers": ["SLS02_RUNTIME_AS_NOT_IMPLEMENTED", "CASE_DIALOGUE_QA_NOT_RUN",
                     "METHODOLOGY_REVIEW_NOT_APPROVED", "RUNTIME_ADMISSION_DISABLED"],
    }
    return package, source_manifest, mapping, preview


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
    execution_rules = {"schema_version": 1, "status": "not_structured", "owner_task": "SLS02/SLS03", "cases": {}}
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
