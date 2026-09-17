"""Детерминированный импорт WORKING-комплекта M5 без БД, LLM и публикации."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Api.assessment_case_contracts import (
    AssessmentSituation, CandidateObservability, CaseDefinition, VerificationReport, unique,
)


ROOT = Path(__file__).resolve().parents[1]
M2 = ROOT / "assessment_definitions/methodologies/competencies_4k/1.1/methodology.json"
M3 = ROOT / "assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json"
OUTPUT = ROOT / "assessment_definitions/cases/competencies_4k/1.1"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
PASSPORT_HEADERS = [
    "CaseID", "Название", "CaseTypeIDs", "Логика связи CT", "Формат", "ApplicableBaseRoles",
    "Version", "Исходная ситуация", "Trigger", "Позиция оцениваемого", "Участники и позиции",
    "Задача", "Условия и ограничения", "Applicability Skill→Component", "Функциональный результат",
    "Инвариант", "Сценарий Dialogue", "Персонализация / роли", "Параметры сложности", "План, мин", "Риски",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def read_xlsx(data: bytes) -> dict:
    """Сохраняет все непустые ячейки и их адреса; формулы не заменяет cached value."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = ["".join(n.text or "" for n in x.findall(".//s:t", NS))
                      for x in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        rels = {x.attrib["Id"]: x.attrib["Target"]
                for x in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        result = {}
        for sheet in ET.fromstring(z.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS):
            rel = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rels[rel].lstrip("/")
            target = target if target.startswith("xl/") else "xl/" + target
            rows = []
            for row in ET.fromstring(z.read(target)).findall("s:sheetData/s:row", NS):
                cells = {}
                for c in row.findall("s:c", NS):
                    if c.find("s:f", NS) is not None:
                        raise ValueError(f"Formula requires explicit review: {sheet.attrib['name']}!{c.attrib['r']}")
                    value = c.findtext("s:v", "", NS)
                    kind = c.attrib.get("t")
                    if kind == "s":
                        value = shared[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(n.text or "" for n in c.findall(".//s:t", NS))
                    elif value and kind not in ("str", "e", "b"):
                        number = float(value)
                        value = int(number) if number.is_integer() else number
                    if value != "":
                        cells[re.sub(r"\d", "", c.attrib["r"])] = value
                if cells:
                    rows.append({"row": int(row.attrib["r"]), "cells": cells})
            result[sheet.attrib["name"]] = rows
        return result


def read_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        body = ET.fromstring(z.read("word/document.xml")).find("w:body", W)
    if body is None:
        raise ValueError("DOCX body missing")
    lines = []
    for block in body:
        if block.tag.endswith("}p"):
            lines.append("".join(n.text or "" for n in block.findall(".//w:t", W)))
        elif block.tag.endswith("}tbl"):
            for row in block.findall("w:tr", W):
                values = []
                for cell in row.findall("w:tc", W):
                    values.append(" / ".join("".join(n.text or "" for n in p.findall(".//w:t", W))
                                             for p in cell.findall(".//w:p", W)))
                lines.append(" | ".join(values))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def records(workbook: dict, sheet: str, header_row: int = 3) -> list[dict]:
    rows = workbook[sheet]
    header = next(r["cells"] for r in rows if r["row"] == header_row)
    return [{"source_row": r["row"], **{str(label): r["cells"].get(col, "") for col, label in header.items()}}
            for r in rows if r["row"] > header_row and r["cells"].get("A")]


def split_ids(value: str) -> list[str]:
    return [x.strip() for x in value.split(";") if x.strip()]


def parse_applicability(value: str) -> list[dict]:
    result = []
    for item in split_ids(value):
        match = re.fullmatch(r"(K[1-4]\.\d+)\s*→\s*(K[1-4]\.C\d{2})", item)
        if not match:
            raise ValueError(f"Invalid Applicability: {item}")
        result.append({"skill_id": match[1], "component_id": match[2], "required": True})
    return result


def load_dependency(path: Path) -> tuple[dict, dict]:
    data = path.read_bytes()
    manifest = json.loads(path.with_name("manifest.json").read_text())
    if manifest["artifact"]["name"] != path.name or digest(data) != manifest["artifact"]["sha256"]:
        raise ValueError(f"Dependency checksum mismatch: {path.name}")
    value = json.loads(data)
    if value.get("methodology_version") != "1.1":
        raise ValueError("Expected methodology 1.1 dependency")
    return value, {"name": path.name, "sha256": digest(data), "source_manifest": manifest}


def methodology_index(methodology: dict) -> tuple[dict, dict]:
    components, indicators = {}, {}
    for competency in methodology["competencies"]:
        for skill in competency["skills"]:
            for component in skill["components"]:
                components[component["id"]] = skill["id"]
                for indicator in component["indicators"]:
                    indicators[indicator["id"]] = (skill["id"], component["id"])
    return components, indicators


def validate_package(package: dict, methodology: dict, roles: dict) -> None:
    if (package.get("schema_version"), package.get("kind"), package.get("methodology_version")) != (1, "m5_case_package", "1.1"):
        raise ValueError("Unexpected M5 package identity")
    if (package.get("status"), package.get("source_status"), package.get("runtime_enabled")) != ("draft", "WORKING", False):
        raise ValueError("M5 package must remain draft/WORKING with runtime disabled")
    components, indicators = methodology_index(methodology)
    role_codes = {r["code"] for r in roles["base_roles"]}
    types = [x["CaseTypeID"] for x in package["case_types"]]
    unique(types, "CaseTypeID")
    cases = [CaseDefinition.model_validate(c) for c in package["cases"]]
    unique([c.case_id for c in cases], "CaseID")
    case_map = {c.case_id: c for c in cases}
    for case in cases:
        if set(case.case_type_ids) - set(types) or set(case.applicable_base_roles) - role_codes:
            raise ValueError(f"Unknown CT or BaseRole: {case.case_id}")
        for a in case.applicability:
            if components.get(a.component_id) != a.skill_id:
                raise ValueError(f"Applicability hierarchy mismatch: {case.case_id}")
    situations = package["test_situations"]
    unique([s["test_as_id"] for s in situations], "TestASID")
    as_map = {s["test_as_id"]: s for s in situations}
    for s in situations:
        case = case_map.get(s["case_id"])
        if not case or s["base_role"] not in case.applicable_base_roles:
            raise ValueError("Test AS case/role mismatch")
        if s["case_version"] != case.version or s["synthetic"] is not True:
            raise ValueError("Test AS version/synthetic marker mismatch")
    role_names = {r["description"]["name"]: r["code"] for r in roles["base_roles"]}
    unique([r["AS TEST ID"] for r in package["role_branches"]], "role branch")
    if {r["AS TEST ID"] for r in package["role_branches"]} != set(as_map):
        raise ValueError("Role branches and test AS differ")
    for branch in package["role_branches"]:
        s = as_map[branch["AS TEST ID"]]
        if (branch["CaseID"], role_names.get(branch["BaseRole"])) != (s["case_id"], s["base_role"]):
            raise ValueError("Role branch AS/role mismatch")
        case = case_map[s["case_id"]]
        if parse_applicability(branch["Основная Applicability"]) != [a.model_dump() for a in case.applicability]:
            raise ValueError("Role branch Applicability mismatch")
    unique([s["CaseID"] for s in package["scenarios"]], "scenario CaseID")
    if {s["CaseID"] for s in package["scenarios"]} != set(case_map):
        raise ValueError("Scenarios and Cases differ")
    for scenario in package["scenarios"]:
        if split_ids(scenario["CTIDs"]) != case_map[scenario["CaseID"]].case_type_ids:
            raise ValueError("Scenario CT composition mismatch")
    keys = []
    for raw in package["candidate_observability"]:
        o = CandidateObservability.model_validate(raw)
        s = as_map.get(o.test_as_id)
        if not s or (s["case_id"], s["base_role"]) != (o.case_id, o.base_role):
            raise ValueError("Observability AS/role mismatch")
        case = case_map[o.case_id]
        if (o.skill_id, o.component_id) not in [(a.skill_id, a.component_id) for a in case.applicability]:
            raise ValueError("Observability outside Case Applicability")
        for i in o.candidate_indicator_ids:
            if indicators.get(i) != (o.skill_id, o.component_id):
                raise ValueError("Indicator hierarchy mismatch")
        keys.append((o.test_as_id, o.indicator_id or o.component_id))
    unique(keys, "Observability link")
    for s in situations:
        expected_components = {a.component_id for a in case_map[s["case_id"]].applicability}
        actual_components = {o["component_id"] for o in package["candidate_observability"] if o["test_as_id"] == s["test_as_id"]}
        if expected_components != actual_components:
            raise ValueError("Test AS is missing an Applicability target")
    for run in package["qa_specs"]:
        if run["test_as_id"] not in as_map or run["result"] != "NOT_RUN":
            raise ValueError("QA specification cannot claim an executed run")
        s = as_map[run["test_as_id"]]
        source = run["source_fields"]
        if (source["CaseID"], role_names.get(source["BaseRole"]), source["Результат"]) != (s["case_id"], s["base_role"], "NOT RUN"):
            raise ValueError("QA source case/role/result mismatch")
    unique([r["spec_id"] for r in package["qa_specs"]], "QA spec")
    for form in package["pilot_forms"]:
        case_ids = split_ids(form["CaseIDs"])
        unique(case_ids, "form CaseID")
        if set(case_ids) - set(case_map):
            raise ValueError("Unknown Case in pilot form")
        covered = {a.component_id for cid in case_ids for a in case_map[cid].applicability}
        if covered != set(split_ids(form["Основные Components"])) or len(covered) != form["Компонентов"]:
            raise ValueError("Pilot form coverage mismatch")


def build_package(source_zip: Path, m2_path: Path = M2, m3_path: Path = M3) -> tuple[dict, dict]:
    methodology, m2_ref = load_dependency(m2_path)
    roles, m3_ref = load_dependency(m3_path)
    _, indicators = methodology_index(methodology)
    role_map = {r["description"]["name"]: r["code"] for r in roles["base_roles"]}
    source_files, texts, books = [], {}, {}
    with zipfile.ZipFile(source_zip) as z:
        for entry in sorted(z.infolist(), key=lambda e: e.filename):
            if entry.is_dir():
                continue
            data = z.read(entry)
            name = entry.filename
            source_files.append({"name": name, "sha256": digest(data)})
            if name.endswith(".xlsx"):
                books[name] = read_xlsx(data)
            elif name.endswith(".docx"):
                texts[name] = read_docx(data)
            elif name.endswith(".md"):
                texts[name] = data.decode("utf-8")
            else:
                raise ValueError(f"Unexpected source file: {name}")
    if len(source_files) != 5 or len(books) != 2 or len(texts) != 3:
        raise ValueError("Expected the five-file M5 v0.4 source set")
    consolidated = [t for t in texts.values() if all(f"M5.{i}." in t for i in range(1, 7))]
    if len(consolidated) != 1:
        raise ValueError("Expected consolidated M5.1-M5.6 source")
    catalog_name = next(n for n, b in books.items() if "CaseType Catalog" in b)
    screening_name = next(n for n, b in books.items() if "02 Паспорта 21 поле" in b)
    book = books[screening_name]
    headers = next(r["cells"] for r in book["02 Паспорта 21 поле"] if r["row"] == 3)
    if list(headers.values()) != PASSPORT_HEADERS:
        raise ValueError("Expected the 21-field M5 passport")
    case_types = records(books[catalog_name], "CaseType Catalog", 2)
    if any(len(c) != 23 for c in case_types):
        raise ValueError("Expected 22 CaseType fields plus source row")
    if {c["CaseTypeID"] for c in case_types} != {f"CT{i:02}" for i in range(1, 21)}:
        raise ValueError("Expected CT01-CT20 catalog")
    cases = []
    for row in records(book, "02 Паспорта 21 поле"):
        case = dict(zip(CaseDefinition.model_fields, (row[h] for h in PASSPORT_HEADERS)))
        case["case_type_ids"] = split_ids(row["CaseTypeIDs"])
        case["applicable_base_roles"] = [role_map[x] for x in split_ids(row["ApplicableBaseRoles"])]
        case["applicability"] = parse_applicability(row["Applicability Skill→Component"])
        cases.append(CaseDefinition.model_validate(case).model_dump())
    situations = [{
        "test_as_id": r["TestASID"], "case_id": r["CaseID"], "case_version": r["CaseVersion"],
        "base_role": role_map[r["Выбранная BaseRole"]], "synthetic": True, "source_fields": r,
    } for r in records(book, "05 Test AssessmentSituations")]
    observations = []
    for row in records(book, "06 Observability TEST"):
        raw_id = row["IndicatorID"]
        pending = raw_id == "PENDING_K2_MATRIX"
        candidates = sorted(i for i, parent in indicators.items()
                            if parent == (row["SkillID"], row["ComponentID"])) if pending else [raw_id]
        observations.append(CandidateObservability(
            test_as_id=row["TestASID"], case_id=row["CaseID"], base_role=role_map[row["Роль"]],
            skill_id=row["SkillID"], component_id=row["ComponentID"], indicator_id=None if pending else raw_id,
            candidate_indicator_ids=candidates, resolution="pending_methodological_review" if pending else "source_assigned",
            conditions=row["Содержательная возможность"], branch=row["Место/ветвь"],
            observable_action=row["Доступное проявление"], loss_risk=row["Риск потери"],
            source_indicator_value=raw_id, source_qa_status=row["QA статус"],
            source={"file": screening_name, "sheet": "06 Observability TEST", "row": row["source_row"]},
        ).model_dump())
    qa_specs = [{
        "spec_id": f"QA.{r['source_row']:03}", "test_as_id": r["TestASID"],
        "trajectory": r["Тип траектории"], "result": r["Результат"].replace(" ", "_"),
        "source_fields": r,
    } for r in records(book, "07 Протоколы dry-run")]
    package = {
        "schema_version": 1, "kind": "m5_case_package", "methodology_version": "1.1",
        "status": "draft", "source_status": "WORKING", "runtime_enabled": False,
        "catalog_source_status": "FROZEN", "dependencies": {"m2": m2_ref, "m3": m3_ref},
        "case_types": case_types, "cases": cases, "test_situations": situations,
        "candidate_observability": observations, "qa_specs": qa_specs,
        "role_branches": records(book, "04 Ролевые ветви"),
        "scenarios": records(book, "03 Сценарии"),
        "pilot_forms": records(book, "09 Формы и покрытие"),
        "blockers": ["K2_METHODOLOGICAL_REVIEW", "SCENARIO_RUNS_NOT_RUN", "M4_PERSONALIZATION_NOT_RUN",
                     "EMPIRICAL_PILOT_NOT_RUN", "M1_IMPACT_REVIEW_PENDING"],
    }
    validate_package(package, methodology, roles)
    counts = [len(package[k]) for k in ("case_types", "cases", "role_branches", "test_situations", "candidate_observability", "qa_specs")]
    if counts != [20, 20, 40, 40, 80, 160]:
        raise ValueError(f"Unexpected v0.4 source counts: {counts}")
    return package, {
        "archive": {"name": source_zip.name, "sha256": digest(source_zip.read_bytes())},
        "sources": source_files, "source_texts": texts, "source_workbooks": books,
    }


def verification_report(package: dict) -> dict:
    checksum = digest(json_bytes(package))
    counts = {k: len(package[k]) for k in ("case_types", "cases", "test_situations", "candidate_observability", "qa_specs")}
    expected_counts = dict(zip(counts, (20, 20, 40, 80, 160)))
    pending = [x for x in package["candidate_observability"] if x["indicator_id"] is None]
    return VerificationReport(
        verification_run_id="m5-static-" + checksum[:16], mode="static_package", package_checksum=checksum,
        runtime_execution="NOT_RUN", m6_execution="NOT_RUN", checks=[
            {"code": "source_counts", "result": "PASS" if counts == expected_counts else "FAIL", "expected": "20 CT; 20 Case; 40 AS; 80 Observability; 160 QA specs",
             "actual": json.dumps(counts), "artifact_refs": ["case-package.json"]},
            {"code": "m2_m3_references", "result": "PASS", "expected": "Все заполненные ссылки согласованы с M2/M3",
             "actual": "Проверены CT, роли, Skill/Component и заполненные IndicatorID", "artifact_refs": ["case-package.json"]},
            {"code": "k2_resolution", "result": "NOT_RUN", "expected": "Методическая проверка всех целей K2",
             "actual": f"Открыто строк: {len(pending)}; кандидаты сохранены без автоматического назначения", "artifact_refs": ["case-package.json"]},
            {"code": "runtime_artifacts", "result": "NOT_RUN", "expected": "Сохранённые AS, Dialogue и вход M6",
             "actual": "Файловый этап; БД, персонализация и взаимодействие не запускались", "artifact_refs": []},
        ],
    ).model_dump()


def write_package(package: dict, provenance: dict, output: Path) -> None:
    methodology, m2_ref = load_dependency(M2)
    roles, m3_ref = load_dependency(M3)
    if package["dependencies"] != {"m2": m2_ref, "m3": m3_ref}:
        raise ValueError("Pinned M2/M3 dependencies differ from local packages")
    validate_package(package, methodology, roles)
    # Проверка до первой записи: draft-пакет не может перезаписать опубликованный.
    if (output / "manifest.json").exists():
        existing = json.loads((output / "manifest.json").read_text())
        if existing.get("status") != "draft":
            raise ValueError("Refusing to overwrite a non-draft package")
    report = verification_report(package)
    artifacts = {
        "case-package.json": json_bytes(package),
        "source-workbooks.json": json_bytes(provenance["source_workbooks"]),
        "source-texts.json": json_bytes(provenance["source_texts"]),
        "case.schema.json": json_bytes(CaseDefinition.model_json_schema()),
        "assessment-situation.schema.json": json_bytes(AssessmentSituation.model_json_schema()),
        "candidate-observability.schema.json": json_bytes(CandidateObservability.model_json_schema()),
        "verification-report.schema.json": json_bytes(VerificationReport.model_json_schema()),
        "verification-report.json": json_bytes(report),
    }
    lines = ["# Статическая проверка пакета M5", "", f"Запуск: `{report['verification_run_id']}`.", "",
             "Пакет: draft / WORKING. Runtime и M6: NOT_RUN. Записей в БД этот этап не создаёт.", ""]
    for check in report["checks"]:
        lines.append(f"- **{check['result']} — {check['code']}**: {check['actual']}")
    lines.extend(["", "Исходные синтетические AS и протоколы являются проектными материалами, а не результатами исполнения.", ""])
    artifacts["verification-report.md"] = "\n".join(lines).encode()
    manifest = {
        "schema_version": 1, "status": "draft", "source_status": "WORKING", "methodology_version": "1.1",
        "archive": provenance["archive"], "sources": provenance["sources"],
        "artifacts": [{"name": name, "sha256": digest(data)} for name, data in sorted(artifacts.items())],
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    (output / "manifest.json").write_bytes(json_bytes(manifest))
    verify_directory(output)


def verify_directory(output: Path) -> dict:
    """Повторное чтение диска: состав, hashes, ссылки, схемы и честность отчёта."""
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest.get("status") != "draft" or manifest.get("source_status") != "WORKING":
        raise ValueError("Expected draft/WORKING manifest")
    entries = manifest["artifacts"]
    unique([e["name"] for e in entries], "manifest artifact")
    expected = {e["name"] for e in entries}
    actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()} - {"manifest.json"}
    if actual != expected:
        raise ValueError("Manifest artifact inventory mismatch")
    for entry in entries:
        if Path(entry["name"]).name != entry["name"]:
            raise ValueError("Only flat artifact paths are allowed")
        if digest((output / entry["name"]).read_bytes()) != entry["sha256"]:
            raise ValueError(f"Artifact checksum mismatch: {entry['name']}")
    package = json.loads((output / "case-package.json").read_text())
    methodology, m2_ref = load_dependency(M2)
    roles, m3_ref = load_dependency(M3)
    if package["dependencies"] != {"m2": m2_ref, "m3": m3_ref}:
        raise ValueError("Pinned M2/M3 dependencies differ from local packages")
    validate_package(package, methodology, roles)
    for filename, model in (
        ("case.schema.json", CaseDefinition), ("assessment-situation.schema.json", AssessmentSituation),
        ("candidate-observability.schema.json", CandidateObservability), ("verification-report.schema.json", VerificationReport),
    ):
        if json.loads((output / filename).read_text()) != model.model_json_schema():
            raise ValueError(f"Generated schema differs from contract: {filename}")
    report = VerificationReport.model_validate_json((output / "verification-report.json").read_bytes()).model_dump()
    if report != verification_report(package):
        raise ValueError("Verification report differs from saved package")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        report = verify_directory(args.output_dir)
        print(f"{report['verification_run_id']}: files/checksums/references PASS; runtime NOT_RUN")
        return
    if args.source_zip is None:
        parser.error("--source-zip is required unless --verify-only is used")
    package, provenance = build_package(args.source_zip)
    write_package(package, provenance, args.output_dir)
    print(f"M5 draft: {args.output_dir}; 20 Case; runtime NOT_RUN")


if __name__ == "__main__":
    main()
