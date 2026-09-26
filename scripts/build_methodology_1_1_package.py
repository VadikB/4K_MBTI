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
EXPLICIT_RED_FLAG = re.compile(r"(?P<code>RF-[A-Z0-9.]+-\d+)\.\s*")
NUMBERED_RED_FLAG = re.compile(r"(?<!\S)(?P<number>\d+)\.\s+")


def _normalize_red_flag_source(raw: str) -> str:
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    return "" if text in {"—", "-"} else text


def _red_flag_transformation_evidence(
    raw: str,
    *,
    indicator_id: str,
    rule: dict[str, Any],
    red_flags: list[dict[str, str]],
) -> dict[str, Any]:
    source = _normalize_red_flag_source(raw)
    mode = str(rule.get("format") or "").strip()
    if mode == "explicit_codes":
        reconstructed = " ".join(f"{item['code']}. {item['description']}" for item in red_flags)
    elif mode == "numbered_list":
        reconstructed = " ".join(
            f"{index}. {item['description']}" for index, item in enumerate(red_flags, start=1)
        )
    elif mode == "single_text":
        reconstructed = " ".join(item["description"] for item in red_flags)
    elif mode == "none":
        reconstructed = ""
    else:
        raise ValueError(f"Unsupported Red Flag format for {indicator_id}: {mode!r}.")
    reconstructed = re.sub(r"\s+", " ", reconstructed).strip()
    if reconstructed != source:
        raise ValueError(
            f"Red Flag transformation changed normative content for {indicator_id}: "
            f"source={source!r}, reconstructed={reconstructed!r}."
        )
    return {
        "indicator_id": indicator_id,
        "format": mode,
        "red_flag_count": len(red_flags),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "reconstructed_sha256": hashlib.sha256(reconstructed.encode("utf-8")).hexdigest(),
        "status": "PASS",
    }


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


def _parse_red_flags(raw: str, *, indicator_id: str, rule: dict[str, Any]) -> list[dict[str, str]]:
    text = _normalize_red_flag_source(raw)
    mode = str(rule.get("format") or "").strip()
    if not text or text in {"—", "-"}:
        if mode not in {"none", "explicit_codes", "numbered_list", "single_text"}:
            raise ValueError(f"Unsupported Red Flag format for {indicator_id}: {mode!r}.")
        return []
    if mode == "none":
        raise ValueError(f"Indicator {indicator_id} declares no Red Flags but source text is present.")
    if mode == "explicit_codes":
        matches = list(EXPLICIT_RED_FLAG.finditer(text))
        if not matches or text[:matches[0].start()].strip():
            raise ValueError(f"Indicator {indicator_id} must start every Red Flag with an explicit code.")
        result = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            result.append({"code": match.group("code"), "description": text[match.end():end].strip()})
        return result
    if mode == "numbered_list":
        matches = list(NUMBERED_RED_FLAG.finditer(text))
        if not matches or matches[0].start() != 0:
            raise ValueError(f"Indicator {indicator_id} must contain a numbered Red Flag list.")
        numbers = [int(match.group("number")) for match in matches]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"Indicator {indicator_id} Red Flag numbering must be sequential from 1.")
        template = str(rule.get("generated_code_template") or "")
        if not template:
            raise ValueError(f"Indicator {indicator_id} numbered Red Flags require generated_code_template.")
        result = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            result.append({
                "code": template.format(indicator_id=indicator_id, number=numbers[index]),
                "description": text[match.end():end].strip(),
            })
        return result
    if mode == "single_text":
        template = str(rule.get("generated_code_template") or "")
        if not template:
            raise ValueError(f"Indicator {indicator_id} single Red Flag requires generated_code_template.")
        return [{"code": template.format(indicator_id=indicator_id, number=1), "description": text}]
    raise ValueError(f"Unsupported Red Flag format for {indicator_id}: {mode!r}.")


def _matrix_data(path: Path, competency_profile: dict[str, Any]) -> dict[str, Any]:
    rows = _xlsx_rows(path)
    header_index = next(index for index, row in enumerate(rows) if row and row[0] == "SkillID")
    header = {name: index for index, name in enumerate(rows[header_index])}
    result = []
    transformations = []
    for row in rows[header_index + 1:]:
        if len(row) <= header["IndicatorID"] or not row[header["IndicatorID"]]:
            continue
        get = lambda name: row[header[name]] if header[name] < len(row) else ""
        indicator_id = get("IndicatorID")
        indicator_rules = dict(competency_profile.get("indicator_red_flags") or {})
        red_flag_rule = dict(indicator_rules.get(indicator_id) or competency_profile.get("red_flags") or {})
        red_flag_source = get("Red Flags")
        red_flags = _parse_red_flags(
            red_flag_source, indicator_id=indicator_id,
            rule=red_flag_rule,
        )
        transformations.append(_red_flag_transformation_evidence(
            red_flag_source,
            indicator_id=indicator_id,
            rule=red_flag_rule,
            red_flags=red_flags,
        ))
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
    return {
        "competency_id": result[0]["id"].split(".")[0],
        "indicators": result,
        "red_flag_transformations": transformations,
    }


def _matrix_competency_id(path: Path) -> str:
    rows = _xlsx_rows(path)
    header_index = next(index for index, row in enumerate(rows) if row and row[0] == "SkillID")
    header = {name: index for index, name in enumerate(rows[header_index])}
    indicator_id = next(
        row[header["IndicatorID"]]
        for row in rows[header_index + 1:]
        if len(row) > header["IndicatorID"] and row[header["IndicatorID"]]
    )
    return indicator_id.split(".")[0]


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}.")
    return value


def build_package(
    source_dir: Path,
    *,
    import_profile: dict[str, Any],
    normative_control: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    passports = sorted(source_dir.glob("M2.K*_Паспорт_*.docx"))
    matrices = sorted(source_dir.glob("M2.K*_Матрица_*.xlsx"))
    source_counts = dict(import_profile.get("expected_source_counts") or {})
    if len(passports) != int(source_counts.get("passports") or 0) or len(matrices) != int(source_counts.get("matrices") or 0):
        raise ValueError(f"Unexpected M2 source counts: passports={len(passports)}, matrices={len(matrices)}.")
    passport_map = {item["id"]: item for item in map(_docx_data, passports)}
    competency_profiles = dict(import_profile.get("competencies") or {})
    matrix_map = {}
    for path in matrices:
        competency_id = _matrix_competency_id(path)
        if competency_id not in competency_profiles:
            raise ValueError(f"Import profile is missing competency {competency_id}.")
        matrix_map[competency_id] = _matrix_data(path, dict(competency_profiles[competency_id]))
    if set(passport_map) != set(competency_profiles) or set(matrix_map) != set(competency_profiles):
        raise ValueError("M2 source competencies do not match import profile.")
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
        runtime_binding = dict(competency_profiles[competency_id].get("runtime_binding") or {})
        competencies.append({key: value for key, value in passport.items() if key not in {"skills", "component_definitions"}} | {
            "code": competency_id,
            "evaluator": runtime_binding["evaluator"],
            "evaluator_version": int(runtime_binding["evaluator_version"]),
            "agent_definition": dict(runtime_binding["agent_definition"]),
            "skills": list(skill_map.values()),
        })
    identity = dict(normative_control.get("methodology") or {})
    package = {
        "schema_version": int(identity["schema_version"]), "kind": identity["kind"], "code": identity["code"],
        "database_version": int(identity["database_version"]),
        "methodology_version": identity["methodology_version"], "status": identity["status"],
        "levels": list(normative_control["levels"]), "competencies": competencies,
    }
    validate_package(package, normative_control=normative_control)
    sources = [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(passports + matrices)]
    transformation_cells = [
        evidence
        for competency_id in sorted(matrix_map)
        for evidence in matrix_map[competency_id]["red_flag_transformations"]
    ]
    transformation_report = {
        "schema_version": 1,
        "kind": "methodology_transformation_validation",
        "algorithm": "normalized_source_equals_reconstructed_output_v1",
        "status": "PASS",
        "indicator_count": len(transformation_cells),
        "red_flag_count": sum(item["red_flag_count"] for item in transformation_cells),
        "indicators": transformation_cells,
    }
    return package, sources, transformation_report


def validate_package(
    package: dict[str, Any],
    *,
    normative_control: dict[str, Any],
    enforce_release_counts: bool = True,
) -> None:
    if package.get("schema_version") != 2 or package.get("status") != "draft":
        raise ValueError("Methodology package must use schema version 2 and draft status.")
    if [item.get("code") for item in package.get("levels", [])] != ["L0", "L1", "L2", "L3"]:
        raise ValueError("Methodology levels must be exactly L0-L3.")
    ids: set[str] = set()
    expected_counts = dict(normative_control.get("expected_counts") or {})
    counts = {key: 0 for key in ("competencies", "skills", "components", "indicators")}
    red_flag_counts: dict[str, int] = {}
    red_flag_codes: set[str] = set()
    red_flag_control = dict(normative_control.get("red_flags") or {})
    code_pattern = re.compile(str(red_flag_control.get("code_pattern") or r"$^"))
    forbidden_descriptions = [re.compile(str(value)) for value in red_flag_control.get("forbidden_description_patterns") or []]
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
                    for red_flag in indicator.get("red_flags") or []:
                        code = str(red_flag.get("code") or "").strip()
                        description = str(red_flag.get("description") or "").strip()
                        match = code_pattern.fullmatch(code)
                        if match is None or match.groupdict().get("indicator_id") != indicator["id"]:
                            raise ValueError(f"Red Flag {code!r} does not belong to Indicator {indicator['id']}.")
                        if code in red_flag_codes:
                            raise ValueError(f"Duplicate Red Flag code: {code}.")
                        if not description or any(pattern.fullmatch(description) for pattern in forbidden_descriptions):
                            raise ValueError(f"Red Flag {code} has an invalid description: {description!r}.")
                        red_flag_codes.add(code)
                        red_flag_counts[competency["id"]] = red_flag_counts.get(competency["id"], 0) + 1
    if enforce_release_counts:
        expected_entities = {key: int(expected_counts[key]) for key in counts}
        if counts != expected_entities:
            raise ValueError(f"Unexpected methodology counts: {counts}.")
        expected_red_flags = dict(expected_counts.get("red_flags") or {})
        expected_by_competency = {key: int(value) for key, value in dict(expected_red_flags.get("by_competency") or {}).items()}
        actual_by_competency = {item["id"]: red_flag_counts.get(item["id"], 0) for item in package.get("competencies") or []}
        if sum(actual_by_competency.values()) != int(expected_red_flags.get("total") or 0) or actual_by_competency != expected_by_competency:
            raise ValueError(f"Unexpected Red Flag counts: {actual_by_competency}.")


def _unique_id(value: str, ids: set[str]) -> None:
    if value in ids:
        raise ValueError(f"Duplicate methodology ID: {value}.")
    ids.add(value)


def write_package(
    package: dict[str, Any],
    sources: list[dict[str, str]],
    output_dir: Path,
    *,
    control_paths: list[Path] | None = None,
    transformation_report: dict[str, Any] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (output_dir / "methodology.json").write_text(content, encoding="utf-8")
    package_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    transformation_artifact = None
    if transformation_report is not None:
        report_content = json.dumps(transformation_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        report_path = output_dir / "transformation-report.json"
        report_path.write_text(report_content, encoding="utf-8")
        transformation_artifact = {
            "name": report_path.name,
            "sha256": hashlib.sha256(report_content.encode("utf-8")).hexdigest(),
            "status": transformation_report["status"],
        }
    manifest = {
        "schema_version": 1, "methodology_code": package["code"],
        "methodology_version": package["methodology_version"], "status": "draft",
        "artifact": {"name": "methodology.json", "sha256": package_sha},
        "transformation_validation": transformation_artifact,
        "control_artifacts": [
            {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(control_paths or [])
        ],
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
    parser.add_argument("--import-profile", type=Path)
    parser.add_argument("--normative-control", type=Path)
    parser.add_argument("--schema", type=Path)
    args = parser.parse_args()
    import_profile_path = args.import_profile or args.output_dir / "import-profile.json"
    normative_control_path = args.normative_control or args.output_dir / "normative-control.json"
    schema_path = args.schema or Path(__file__).resolve().parent.parent / "assessment_definitions/schemas/methodology-package-v2.schema.json"
    package, sources, transformation_report = build_package(
        args.source_dir,
        import_profile=_load_object(import_profile_path),
        normative_control=_load_object(normative_control_path),
    )
    write_package(
        package, sources, args.output_dir,
        control_paths=[import_profile_path.resolve(), normative_control_path.resolve(), schema_path.resolve()],
        transformation_report=transformation_report,
    )
    counts = dict(_load_object(normative_control_path)["expected_counts"])
    print(
        "Built methodology draft: "
        f"{counts['competencies']} competencies, {counts['skills']} skills, "
        f"{counts['components']} components, {counts['indicators']} indicators."
    )


if __name__ == "__main__":
    main()
