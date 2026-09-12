from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
EXPECTED_COUNTS = {"competencies": 4, "skills": 14, "components": 35, "indicators": 61}
LEVELS = [
    {"code": "L0", "order": 0, "meaning": "Наблюдаемое действие отсутствует или сломано либо его продукт неработоспособен; отсутствие Evidence само по себе не является L0."},
    {"code": "L1", "order": 1, "meaning": "Базовое или очевидное действие, часто с опорой на заданную структуру."},
    {"code": "L2", "order": 2, "meaning": "Самостоятельное полное действие с рабочим продуктом."},
    {"code": "L3", "order": 3, "meaning": "Качественно более развитая организация того же действия: работа с неявными элементами, отношениями, проверкой, интеграцией или перестройкой."},
]


def _text(element: ET.Element, namespace: dict[str, str], tag: str) -> str:
    return "".join(node.text or "" for node in element.findall(f".//{tag}", namespace)).strip()


def _docx_data(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = [_text(node, WORD_NS, "w:t") for node in root.findall(".//w:body/w:p", WORD_NS)]
    paragraphs = [re.sub(r"\s+", " ", value).strip() for value in paragraphs if value.strip()]
    tables: list[list[list[str]]] = []
    for table in root.findall(".//w:tbl", WORD_NS):
        rows = []
        for row in table.findall("./w:tr", WORD_NS):
            rows.append([re.sub(r"\s+", " ", _text(cell, WORD_NS, "w:t")).strip() for cell in row.findall("./w:tc", WORD_NS)])
        tables.append(rows)
    metadata = {row[0]: row[1] for row in tables[0] if len(row) >= 2}
    competency_id = metadata["CompetencyID"]
    definition = _value_after(paragraphs, "1.1. Определение")
    function = _value_after(paragraphs, "1.2. Функция компетенции")
    product = _value_after(paragraphs, "1.3. Продукт компетенции")
    logic = _value_after(paragraphs, "1.4. Логика компетенции")
    skill_pattern = re.compile(rf"^{competency_id}\.\d+ — ")
    skills = []
    for index, value in enumerate(paragraphs):
        if not skill_pattern.match(value) or value.endswith(".") or index < paragraphs.index("2. Архитектура компетенции"):
            continue
        skill_id, name = value.split(" — ", 1)
        block = paragraphs[index + 1:index + 14]
        skills.append({
            "id": skill_id,
            "name": name,
            "function": _value_after(block, "Функция"),
            "product": _value_after(block, "Продукт"),
            "place_in_logic": _value_after(block, f"Место в логике {competency_id}"),
            "boundary": _value_after(block, "Граница навыка"),
        })
    component_definitions: dict[str, str] = {}
    for table in tables[1:]:
        if not table or "ComponentID" not in table[0]:
            continue
        header = {name: index for index, name in enumerate(table[0])}
        if "Определение" not in header:
            continue
        for row in table[1:]:
            component_definitions[row[header["ComponentID"]]] = row[header["Определение"]]
    return {
        "id": competency_id,
        "name": metadata["Название"],
        "definition": definition,
        "function": function,
        "product": product,
        "logic": logic,
        "skills": skills,
        "component_definitions": component_definitions,
    }


def _value_after(values: list[str], label: str) -> str:
    try:
        return values[values.index(label) + 1]
    except (ValueError, IndexError):
        return ""


def _xlsx_rows(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [_text(item, NS, "a:t") for item in shared_root.findall("a:si", NS)]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {item.attrib["Id"]: item.attrib["Target"] for item in relations}
        first_sheet = workbook.find("a:sheets/a:sheet", NS)
        rel_id = first_sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rel_map[rel_id].lstrip("/")
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"
        sheet = ET.fromstring(archive.read(sheet_path))
    output = []
    for row in sheet.findall(".//a:sheetData/a:row", NS):
        values: dict[int, str] = {}
        for cell in row.findall("a:c", NS):
            reference = cell.attrib["r"]
            letters = re.match(r"[A-Z]+", reference).group(0)
            column = 0
            for letter in letters:
                column = column * 26 + ord(letter) - 64
            kind = cell.attrib.get("t")
            raw = cell.findtext("a:v", default="", namespaces=NS)
            if kind == "s" and raw:
                value = shared[int(raw)]
            elif kind == "inlineStr":
                value = _text(cell, NS, "a:t")
            else:
                value = raw
            values[column - 1] = re.sub(r"\s+", " ", value).strip()
        if values:
            output.append([values.get(index, "") for index in range(max(values) + 1)])
    return output


def _matrix_data(path: Path) -> dict[str, Any]:
    rows = _xlsx_rows(path)
    header_index = next(index for index, row in enumerate(rows) if row and row[0] == "SkillID")
    header = {name: index for index, name in enumerate(rows[header_index])}
    result = []
    for row in rows[header_index + 1:]:
        if len(row) <= header["IndicatorID"] or not row[header["IndicatorID"]]:
            continue
        get = lambda name: row[header[name]] if header[name] < len(row) else ""
        raw_flags = [item.strip() for item in re.split(r"(?=RF-[A-Z0-9.]+-\d+\.)|(?=\d+\. )", get("Red Flags")) if item.strip() and item.strip() not in {"—", "-"}]
        red_flags = []
        for number, item in enumerate(raw_flags, start=1):
            match = re.match(r"(RF-[A-Z0-9.]+-\d+)\.\s*(.*)", item)
            description = re.sub(r"^\d+\.\s*", "", match.group(2) if match else item).strip()
            red_flags.append({
                "code": match.group(1) if match else f"RF-{get('IndicatorID')}-{number:02d}",
                "description": description,
            })
        result.append({
            "skill_id": get("SkillID"), "skill_name": get("Skill"),
            "component_id": get("ComponentID"), "component_name": get("Component"),
            "id": get("IndicatorID"), "name": get("Indicator"),
            "function": get("Функция"), "product": get("Продукт"),
            "levels": {level: get(level) for level in ("L0", "L1", "L2", "L3")},
            "boundary": get("Границы"),
            "evidence_pattern": get("Evidence Pattern"),
            "red_flags": red_flags,
        })
    return {"competency_id": result[0]["id"].split(".")[0], "indicators": result}


def build_package(source_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    passports = sorted(source_dir.glob("M2.K*_Паспорт_*.docx"))
    matrices = sorted(source_dir.glob("M2.K*_Матрица_*.xlsx"))
    if len(passports) != 4 or len(matrices) != 4:
        raise ValueError("Expected four M2 passports and four M2 matrices.")
    passport_map = {item["id"]: item for item in map(_docx_data, passports)}
    matrix_map = {item["competency_id"]: item for item in map(_matrix_data, matrices)}
    competencies = []
    for competency_id in sorted(passport_map):
        passport = passport_map[competency_id]
        indicators = matrix_map[competency_id]["indicators"]
        skill_map = {item["id"]: {**item, "components": []} for item in passport["skills"]}
        components: dict[str, dict[str, Any]] = {}
        for indicator in indicators:
            component = components.setdefault(indicator["component_id"], {
                "id": indicator["component_id"], "name": indicator["component_name"],
                "definition": passport["component_definitions"].get(indicator["component_id"], ""), "indicators": [],
            })
            component["indicators"].append({key: value for key, value in indicator.items() if key not in {"skill_id", "skill_name", "component_id", "component_name"}})
        for component in components.values():
            parent = next(item["skill_id"] for item in indicators if item["component_id"] == component["id"])
            skill_map[parent]["components"].append(component)
        agent_suffix = {"K1": "communication", "K2": "teamwork", "K3": "creativity", "K4": "critical_thinking"}[competency_id]
        competencies.append({key: value for key, value in passport.items() if key not in {"skills", "component_definitions"}} | {
            "code": competency_id,
            "evaluator": f"evaluation.{agent_suffix}",
            "evaluator_version": 2,
            "agent_definition": {"code": f"indicator_{agent_suffix}", "version": 1},
            "skills": list(skill_map.values()),
        })
    package = {
        "schema_version": 2, "kind": "methodology", "code": "competencies_4k",
        "database_version": 2, "methodology_version": "1.1", "status": "draft",
        "levels": LEVELS, "competencies": competencies,
    }
    validate_package(package)
    sources = [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(passports + matrices)]
    return package, sources


def validate_package(package: dict[str, Any], *, enforce_release_counts: bool = True) -> None:
    if package.get("schema_version") != 2 or package.get("status") != "draft":
        raise ValueError("Methodology package must use schema version 2 and draft status.")
    if [item.get("code") for item in package.get("levels", [])] != ["L0", "L1", "L2", "L3"]:
        raise ValueError("Methodology levels must be exactly L0-L3.")
    ids: set[str] = set()
    counts = {key: 0 for key in EXPECTED_COUNTS}
    for competency in package.get("competencies", []):
        _unique_id(competency["id"], ids); counts["competencies"] += 1
        for skill in competency.get("skills", []):
            _unique_id(skill["id"], ids); counts["skills"] += 1
            if not skill["id"].startswith(competency["id"] + "."):
                raise ValueError(f"Skill {skill['id']} has an invalid parent.")
            for component in skill.get("components", []):
                _unique_id(component["id"], ids); counts["components"] += 1
                if not component["id"].startswith(competency["id"] + ".C"):
                    raise ValueError(f"Component {component['id']} has an invalid parent.")
                for indicator in component.get("indicators", []):
                    _unique_id(indicator["id"], ids); counts["indicators"] += 1
                    if not indicator["id"].startswith(competency["id"] + ".I"):
                        raise ValueError(f"Indicator {indicator['id']} has an invalid parent.")
                    if set(indicator.get("levels", {})) != {"L0", "L1", "L2", "L3"} or not all(indicator["levels"].values()):
                        raise ValueError(f"Indicator {indicator['id']} must define non-empty L0-L3.")
                    if not indicator.get("evidence_pattern"):
                        raise ValueError(f"Indicator {indicator['id']} must define Evidence Pattern.")
    if enforce_release_counts and counts != EXPECTED_COUNTS:
        raise ValueError(f"Unexpected methodology counts: {counts}.")


def _unique_id(value: str, ids: set[str]) -> None:
    if value in ids:
        raise ValueError(f"Duplicate methodology ID: {value}.")
    ids.add(value)


def write_package(package: dict[str, Any], sources: list[dict[str, str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (output_dir / "methodology.json").write_text(content, encoding="utf-8")
    package_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = {
        "schema_version": 1, "methodology_code": package["code"],
        "methodology_version": package["methodology_version"], "status": "draft",
        "artifact": {"name": "methodology.json", "sha256": package_sha},
        "agent_artifacts": [
            {
                "name": path.relative_to(output_dir).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted((output_dir / "agents").rglob("*"))
            if path.is_file()
        ],
        "sources": sources,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Сборка draft-пакета методологии 4К 1.1 из артефактов M2.")
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    package, sources = build_package(args.source_dir)
    write_package(package, sources, args.output_dir)
    print("Built methodology 1.1 draft: 4 competencies, 14 skills, 35 components, 61 indicators.")


if __name__ == "__main__":
    main()
