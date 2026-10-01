"""Детерминированный offline-импорт пяти M5 Case из XLSX в schema v2."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Api.assessment_case_contracts import AssessmentSituationV2, C34ExecutionEnvelope, CaseVersionV2
from Api.m5_case_runtime import checksum
ROOT = Path(__file__).resolve().parents[1]
M2 = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"
M3 = ROOT / "assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json"
OUTPUT = ROOT / "assessment_definitions/cases/competencies_4k/1.1"
EXECUTION_RULES = ROOT / "assessment_definitions/cases/competencies_4k/m5-1.1-v0.1-authoring/execution-rules.json"
ADMISSION_POLICY = ROOT / "assessment_definitions/cases/competencies_4k/m5-1.1-v0.1-authoring/admission-policy.json"
SOURCE_NAME = "M5_Командное_обсуждение_5_комплексных_кейсов_v0_1_WORKING.xlsx"
EXPECTED_SOURCE_SHA256 = "06f528d9c9e34c4748979e4d787ce0e069990e9f4051953e395ecb3f454e53fa"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def read_xlsx(data: bytes) -> dict:
    """Прочитать значения OOXML; формулы допускаются только с сохранённым значением."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(n.text or "" for n in x.findall(".//s:t", NS)) for x in root.findall("s:si", NS)]
        rels = {x.attrib["Id"]: x.attrib["Target"] for x in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        result = {}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            rel = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rels[rel].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            rows = []
            for row in ET.fromstring(archive.read(target)).findall("s:sheetData/s:row", NS):
                cells = {}
                for cell in row.findall("s:c", NS):
                    value = cell.findtext("s:v", "", NS)
                    kind = cell.attrib.get("t")
                    if kind == "s" and value != "":
                        value = shared[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(n.text or "" for n in cell.findall(".//s:t", NS))
                    elif value != "" and kind not in ("str", "e", "b"):
                        number = float(value)
                        value = int(number) if number.is_integer() else number
                    if value != "":
                        cells[re.sub(r"\d", "", cell.attrib["r"])] = value
                if cells:
                    rows.append({"row": int(row.attrib["r"]), "cells": cells})
            result[sheet.attrib["name"]] = rows
        return result


def records(workbook: dict, sheet: str, header_row: int = 1) -> list[dict]:
    rows = workbook[sheet]
    header = next(row["cells"] for row in rows if row["row"] == header_row)
    return [{"source_row": row["row"], **{str(label): row["cells"].get(column, "") for column, label in header.items()}}
            for row in rows if row["row"] > header_row and row["cells"].get("A")]


def rows_by_key(book: dict, sheet: str) -> dict[tuple[str, str], list[dict]]:
    result: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in records(book, sheet, 1):
        result[(str(row["CaseID"]), str(row["CaseVersion"]))].append(row)
    return result


def methodology_index() -> dict[str, tuple[str, str, str]]:
    value = json.loads(M2.read_text())
    result = {}
    for competency in value["competencies"]:
        for skill in competency["skills"]:
            for component in skill["components"]:
                for indicator in component["indicators"]:
                    result[indicator["id"]] = (skill["id"], component["id"], indicator["name"])
    return result


def build_package(source: Path) -> tuple[dict, dict]:
    source_bytes = source.read_bytes()
    if digest(source_bytes) != EXPECTED_SOURCE_SHA256:
        raise ValueError("Unexpected XLSX source checksum; register a new draft version")
    book = read_xlsx(source_bytes)
    required = {"Кейсы", "Паспорта", "Участники", "Данные", "Сценарий", "Индикаторы", "Applicability", "CaseTypes", "Варианты", "Описание"}
    if set(book) != required:
        raise ValueError("Unexpected XLSX sheet inventory")
    grouped = {name: rows_by_key(book, name) for name in ("Паспорта", "Участники", "Данные", "Сценарий", "Индикаторы", "Applicability", "CaseTypes")}
    roles_value = json.loads(M3.read_text())
    role_map = {x["description"]["name"]: x["code"] for x in roles_value["base_roles"]}
    m2 = methodology_index()
    execution_rules = json.loads(EXECUTION_RULES.read_text())
    if execution_rules["source_checksum"] != EXPECTED_SOURCE_SHA256:
        raise ValueError("Execution rules apply to another XLSX source")
    cases = []
    for row in records(book, "Кейсы", 1):
        key = (str(row["CaseID"]), str(row["CaseVersion"]))
        passport_rows = sorted(grouped["Паспорта"][key], key=lambda x: int(x["FieldNo"]))
        if [int(x["FieldNo"]) for x in passport_rows] != list(range(1, 23)):
            raise ValueError(f"Expected 22 passport fields: {key}")
        passport = {str(x["FieldKey"]): x["Value"] for x in passport_rows}
        passport_sources = {str(x["FieldKey"]): {"file": SOURCE_NAME, "sheet": "Паспорта", "row": int(x["source_row"]), "field": "Value"} for x in passport_rows}
        targets = []
        for target in grouped["Индикаторы"][key]:
            indicator_id = str(target["IndicatorID"])
            expected = m2.get(indicator_id)
            actual = (target["SkillID"], target["ComponentID"], target["IndicatorName"])
            if expected != actual:
                raise ValueError(f"M2 target mismatch: {key} {indicator_id}")
            targets.append({
                "indicator_id": indicator_id, "m2_version": str(target["M2Version"]),
                "skill_id": target["SkillID"], "component_id": target["ComponentID"],
                "observation_condition": target["ObservationCondition"],
                "scenario_locations": sorted(set(re.findall(r"S\d+", str(target["ObservationCondition"])))) or ["SOURCE_UNRESOLVED"],
                "branch_condition": str(target["ObservationCondition"]),
                "event_condition": str(target["ObservationCondition"]),
                "observable_action": target["ObservableAction"], "validity_risk": target["ValidityRisk"],
                "source": {"file": SOURCE_NAME, "sheet": "Индикаторы", "row": int(target["source_row"]), "field": "IndicatorID..ValidityRisk"},
            })
        unresolved = []
        if key[0] == "CASE-TDISC-04":
            unresolved.append("CASE04_ASYA_BRANCH_CONDITION_REQUIRES_METHOD_OWNER_DECISION")
        source_materials = {x["DataID"]: x for x in grouped["Данные"][key]}
        materials = []
        for material_id, rule in execution_rules["materials"].items():
            source_id = rule.get("source_material_id", material_id)
            source_material = source_materials.get(source_id)
            if source_material is None:
                continue
            materials.append({
                "material_id": material_id, "code": material_id.removeprefix(key[0] + "-"),
                "title": source_material["Title"], "internal_rule": source_material["DataAndDisclosureRules"],
                "participant_payload": rule["participant_payload"], "disclosure_condition": rule["disclosure_condition"],
                "event_condition": rule["event_condition"], "reaction_rule": rule["reaction_rule"],
                "result_check": rule["result_check"], "kind": rule["kind"], "classification_status": "structured",
                "speaker_id": rule.get("speaker_id"),
                "source": {"file": SOURCE_NAME, "sheet": "Данные", "row": int(source_material["source_row"]), "field": "DataAndDisclosureRules"},
            })
        case = CaseVersionV2(
            case_id=key[0], version=key[1], status=row["CaseStatus"], title=row["Title"],
            base_role=role_map[row["BaseRole"]], format=row["Format"],
            planned_min_minutes=int(row["PlannedMinMinutes"]), planned_max_minutes=int(row["PlannedMaxMinutes"]),
            passport=passport, passport_sources=passport_sources,
            case_type_ids=[x["CaseTypeID"] for x in sorted(grouped["CaseTypes"][key], key=lambda x: int(x["ListPosition"]))],
            applicability=[{"skill_id": x["SkillID"], "component_id": x["ComponentID"], "required": True} for x in grouped["Applicability"][key]],
            indicator_targets=targets,
            characters=[{
                "character_id": x["CharacterID"], "order": int(x["ListPosition"]),
                "name_and_role": x["NameAndRole"], "public_position": x["PublicPosition"], "closed_card": x["ClosedCard"],
                "source": {"file": SOURCE_NAME, "sheet": "Участники", "row": int(x["source_row"]), "field": "NameAndRole..ClosedCard"},
            } for x in sorted(grouped["Участники"][key], key=lambda x: int(x["ListPosition"]))],
            materials=materials,
            scenario=[{
                "step_id": x["StepID"], "code": x["StepCode"], "order": int(x["StepOrder"]),
                "title": x["Title"], "rules": x["Rules"],
                "source": {"file": SOURCE_NAME, "sheet": "Сценарий", "row": int(x["source_row"]), "field": "Rules"},
            } for x in sorted(grouped["Сценарий"][key], key=lambda x: int(x["StepOrder"]))],
            unresolved_decisions=unresolved,
        )
        if int(row["IndicatorCount"]) != len(case.indicator_targets):
            raise ValueError(f"Indicator count mismatch: {key}")
        cases.append(case.model_dump())
    proposals = records(book, "Варианты", 1)
    if any(x["Status"] != "PROPOSAL" for x in proposals):
        raise ValueError("Only PROPOSAL rows are expected on Варианты")
    description = records(book, "Описание", 1)
    package = {
        "schema_version": 2, "kind": "m5_case_package", "methodology_version": "1.1",
        "version": "0.1", "status": "draft", "source_status": "WORKING",
        "runtime_enabled": False, "cases": cases,
        "excluded_proposals": [{k: v for k, v in x.items() if k != "source_row"} for x in proposals],
        "source_notes": [{k: v for k, v in x.items() if k != "source_row"} for x in description],
        "blockers": ["CASE_DIALOGUE_QA_NOT_RUN", "TIME_DIFFICULTY_RELIABILITY_PILOT_NOT_RUN", "CASE04_METHOD_DECISION_PENDING"],
    }
    if len(cases) != 5 or sum(len(x["indicator_targets"]) for x in cases) != 43:
        raise ValueError("Unexpected case or target count")
    return package, {"source_sha256": digest(source_bytes), "source_name": SOURCE_NAME}


def write_package(source: Path, destination: Path = OUTPUT) -> dict:
    if (destination / "manifest.json").exists():
        existing = json.loads((destination / "manifest.json").read_text())
        if existing.get("status") != "draft":
            raise ValueError("Refusing to overwrite a non-draft package")
    package, source_ref = build_package(source)
    destination.mkdir(parents=True, exist_ok=True)
    source_dir = destination / "sources"
    source_dir.mkdir(exist_ok=True)
    snapshot_path = source_dir / SOURCE_NAME
    if source.resolve() != snapshot_path.resolve():
        shutil.copyfile(source, snapshot_path)
    policy = json.loads(ADMISSION_POLICY.read_text())
    verification = {
        "schema_version": 2, "result": "PASS", "scope": "static_package",
        "case_count": len(package["cases"]), "indicator_target_count": sum(len(x["indicator_targets"]) for x in package["cases"]),
        "source_checksum": source_ref["source_sha256"], "package_checksum": checksum(package),
        "case_dialogue_qa": "NOT_RUN", "runtime_execution": "NOT_RUN", "m6_execution": "NOT_RUN",
    }
    files = {
        "case-package.json": json_bytes(package),
        "case.schema.json": json_bytes(CaseVersionV2.model_json_schema()),
        "assessment-situation.schema.json": json_bytes(AssessmentSituationV2.model_json_schema()),
        "c34-execution-envelope.schema.json": json_bytes(C34ExecutionEnvelope.model_json_schema()),
        "admission-policy.json": json_bytes(policy),
        "execution-rules.json": EXECUTION_RULES.read_bytes(),
        "verification-report.json": json_bytes(verification),
    }
    for name, data in files.items():
        (destination / name).write_bytes(data)
    artifacts = [{"name": name, "sha256": digest(data)} for name, data in sorted(files.items())]
    artifacts.append({"name": f"sources/{SOURCE_NAME}", "sha256": source_ref["source_sha256"]})
    manifest = {
        "schema_version": 2, "id": "m5-complex-cases", "version": "0.1", "status": "draft",
        "source_status": "WORKING", "runtime_enabled": False, "artifacts": artifacts,
        "dependencies": {"m2": digest(M2.read_bytes()), "m3": digest(M3.read_bytes())},
    }
    (destination / "manifest.json").write_bytes(json_bytes(manifest))
    verify_directory(destination)
    return verification


def verify_directory(destination: Path = OUTPUT) -> dict:
    manifest = json.loads((destination / "manifest.json").read_text())
    expected = {"manifest.json"} | {x["name"] for x in manifest["artifacts"]}
    actual = {str(x.relative_to(destination)) for x in destination.rglob("*") if x.is_file()}
    if actual != expected:
        raise ValueError(f"Package inventory mismatch: {sorted(actual ^ expected)}")
    for artifact in manifest["artifacts"]:
        if digest((destination / artifact["name"]).read_bytes()) != artifact["sha256"]:
            raise ValueError(f"Artifact checksum mismatch: {artifact['name']}")
    package = json.loads((destination / "case-package.json").read_text())
    for case in package["cases"]:
        CaseVersionV2.model_validate(case)
    if package["runtime_enabled"] or package["status"] != "draft":
        raise ValueError("WORKING package cannot be runtime enabled")
    return json.loads((destination / "verification-report.json").read_text())


def dry_run(source: Path) -> dict:
    package, source_ref = build_package(source)
    unresolved = []
    for case in package["cases"]:
        unresolved.extend({"case_id": case["case_id"], "code": code} for code in case["unresolved_decisions"])
        unresolved.extend({"case_id": case["case_id"], "code": f"MATERIAL_RULE_UNRESOLVED:{m['material_id']}"}
                          for m in case["materials"] if m["classification_status"] != "structured")
    return {
        "mode": "dry_run", "source": source_ref, "package_schema_version": package["schema_version"],
        "case_count": len(package["cases"]),
        "case_versions": [{"case_id": c["case_id"], "version": c["version"],
                           "targets": len(c["indicator_targets"]), "materials": len(c["materials"])} for c in package["cases"]],
        "excluded_proposal_count": len(package["excluded_proposals"]),
        "unresolved_dependencies": unresolved,
        "validation_scope": ["xlsx_structure", "passport_22_fields", "m2_indicator_hierarchy", "m3_base_role", "referential_keys"],
        "package_checksum": checksum(package),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify_directory(args.output), ensure_ascii=False, indent=2))
    elif args.source is None:
        parser.error("source is required unless --verify-only is used")
    elif args.dry_run:
        print(json.dumps(dry_run(args.source), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(write_package(args.source, args.output), ensure_ascii=False, indent=2))
