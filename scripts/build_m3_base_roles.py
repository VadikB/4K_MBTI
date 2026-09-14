"""Build complete deterministic M3 draft artifacts from the supplied DOCX files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
ROLE_CODES = (
    "operational_employee",
    "specialist_expert",
    "team_lead",
    "project_product_process_manager",
    "direction_system_leader",
    "student",
)
DESCRIPTION_FIELDS = (
    ("Название роли", "name"),
    ("Короткое описание роли", "short_description"),
    ("Ключевые признаки роли", "key_characteristics"),
    ("Примеры, для кого подходит роль", "examples"),
)
CARD_FIELDS = (
    ("Основная миссия роли", "mission"),
    ("Объект ответственности", "responsibility_object"),
    ("Типовые задачи", "typical_tasks"),
    ("Объекты работы", "work_objects"),
    ("Горизонт планирования", "planning_horizon"),
    ("Масштаб влияния", "influence_scale"),
    ("Типичная неопределённость", "typical_uncertainty"),
    ("Полномочия — можно самостоятельно", "independent_authority"),
    ("Полномочия — требуется согласование", "approval_required"),
    ("Эскалация — что и куда", "escalation"),
    ("Ограничения роли", "role_constraints"),
    ("Типовые критерии результата роли", "result_criteria"),
    ("Типовые риски и ставки", "risks_and_stakes"),
    ("Типовой контур взаимодействия", "interaction_context"),
    ("Типовые сценарии", "typical_scenarios"),
    ("Источники информации", "information_sources"),
    ("Шаблоны и инструменты", "templates_and_tools"),
)
VALIDITY_CHECKS = (
    "Полномочия", "Объект ответственности", "Масштаб", "Горизонт",
    "Неопределённость", "Ресурсы и мандат", "Контур взаимодействия",
    "Ограничения", "Сохранение ролевой логики при персонализации",
)
INVARIANTS = (
    "Способ получения результата", "Объект ответственности", "Тип полномочий",
    "Масштаб деятельности", "Характер взаимодействия",
)


def _paragraph_text(paragraph: ET.Element) -> str:
    parts = []
    for node in paragraph.iter():
        if node.tag == f"{{{WORD_NS['w']}}}t":
            parts.append(node.text or "")
        elif node.tag == f"{{{WORD_NS['w']}}}br":
            parts.append("\n")
        elif node.tag == f"{{{WORD_NS['w']}}}tab":
            parts.append("\t")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in "".join(parts).split("\n")).strip()


def _word_blocks(path: Path) -> tuple[list[dict], list[list[list[str]]]]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", WORD_NS)
    if body is None:
        raise ValueError("DOCX has no document body.")
    blocks = []
    tables = []
    for child in body:
        if child.tag == f"{{{WORD_NS['w']}}}p":
            value = _paragraph_text(child)
            if not value:
                continue
            style = child.find("w:pPr/w:pStyle", WORD_NS)
            blocks.append({"type": "paragraph", "style": style.attrib.get(f"{{{WORD_NS['w']}}}val", "") if style is not None else "", "text": value})
        elif child.tag == f"{{{WORD_NS['w']}}}tbl":
            rows = []
            for row in child.findall("./w:tr", WORD_NS):
                rows.append([_cell_text(cell) for cell in row.findall("./w:tc", WORD_NS)])
            tables.append(rows)
            blocks.append({"type": "table", "rows": rows})
    return blocks, tables


def _markdown_source(blocks: list[dict]) -> str:
    output = []
    for index, block in enumerate(blocks):
        if block["type"] == "table":
            rows = block["rows"]
            if not rows or len({len(row) for row in rows}) != 1:
                raise ValueError("M3 source table has inconsistent columns.")
            clean = lambda value: value.replace("|", "\\|").replace("\n", "<br>")
            output.append("| " + " | ".join(map(clean, rows[0])) + " |")
            output.append("| " + " | ".join("---" for _ in rows[0]) + " |")
            output.extend("| " + " | ".join(map(clean, row)) + " |" for row in rows[1:])
        else:
            text = block["text"].replace("\n", "<br>\n")
            style = block["style"].lower()
            if index == 0:
                text = f"# {text}"
            elif style.startswith("heading"):
                level = re.search(r"\d+", style)
                text = f"{'#' * (int(level.group()) + 1 if level else 2)} {text}"
            output.append(text)
        output.append("")
    return "\n".join(output).rstrip() + "\n"


def _contract_rows(table: list[list[str]], *, header: tuple[str, str]) -> list[dict[str, str]]:
    if not table or table[0] != list(header) or any(len(row) != 2 for row in table[1:]):
        raise ValueError(f"Unexpected M3 contract table: {header}.")
    return [{"name": row[0], "meaning": row[1]} for row in table[1:]]


def build_role_profile_contract(blocks: list[dict], tables: list[list[list[str]]]) -> dict:
    if len(tables) != 6:
        raise ValueError("Expected six M3 RoleProfile tables.")
    description = _contract_rows(tables[2], header=("Поле", "Нормативное содержание"))
    card = _contract_rows(tables[3], header=("Поле", "Нормативное содержание"))
    if [item["name"] for item in description] != [name for name, _ in DESCRIPTION_FIELDS]:
        raise ValueError("M3 description fields differ from BaseRole cards.")
    if [re.sub(r"^2\.\d+\s+", "", item["name"]) for item in card] != [name for name, _ in CARD_FIELDS]:
        raise ValueError("M3 card fields differ from BaseRole cards.")
    for item, (_, key) in zip(description, DESCRIPTION_FIELDS):
        item["key"] = key
    for item, (_, key) in zip(card, CARD_FIELDS):
        item["key"] = key
    checks = _contract_rows(tables[4], header=("Проверка", "Нормативный вопрос"))
    invariants = _contract_rows(tables[5], header=("Инвариант", "Что должно сохраняться"))
    paragraphs = [block["text"] for block in blocks if block["type"] == "paragraph"]
    try:
        start = paragraphs.index("RoleProfile может формироваться:")
        end = paragraphs.index(next(value for value in paragraphs[start + 1:] if value.startswith("При ручном формировании")))
    except (ValueError, StopIteration) as exc:
        raise ValueError("M3 formation methods were not found.") from exc
    contract = {
        "schema_version": 1,
        "kind": "m3_role_profile_contract",
        "methodology_version": "1.1",
        "status": "draft",
        "description_fields": description,
        "card_fields": card,
        "role_validity_checks": checks,
        "base_role_invariants": invariants,
        "formation_methods": paragraphs[start + 1:end],
    }
    validate_role_profile_contract(contract)
    return contract


def validate_role_profile_contract(contract: dict) -> None:
    if contract.get("schema_version") != 1 or contract.get("methodology_version") != "1.1" or contract.get("status") != "draft":
        raise ValueError("Expected a draft M3 RoleProfile contract for methodology 1.1.")
    if len(contract.get("description_fields") or []) != 4 or len(contract.get("card_fields") or []) != 17:
        raise ValueError("M3 RoleProfile must define 4 description and 17 card fields.")
    if [item.get("key") for item in contract["description_fields"]] != [key for _, key in DESCRIPTION_FIELDS]:
        raise ValueError("M3 description field keys are inconsistent.")
    if [item.get("key") for item in contract["card_fields"]] != [key for _, key in CARD_FIELDS]:
        raise ValueError("M3 card field keys are inconsistent.")
    if [item["name"] for item in contract.get("role_validity_checks") or []] != list(VALIDITY_CHECKS):
        raise ValueError("M3 RoleProfile must define all nine role-validity checks.")
    if [item["name"] for item in contract.get("base_role_invariants") or []] != list(INVARIANTS):
        raise ValueError("M3 RoleProfile must define all five BaseRole invariants.")
    if len(contract.get("formation_methods") or []) != 4:
        raise ValueError("M3 RoleProfile must define four formation methods.")
    for group in ("description_fields", "card_fields", "role_validity_checks", "base_role_invariants"):
        if not all(item.get("name") and item.get("meaning") for item in contract[group]):
            raise ValueError(f"Incomplete M3 {group}.")


def _cell_text(cell: ET.Element) -> str:
    paragraphs = []
    for paragraph in cell.findall(".//w:p", WORD_NS):
        value = _paragraph_text(paragraph)
        if value:
            paragraphs.append(value)
    return "\n".join(paragraphs)


def _tables(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    result = []
    for table in root.findall(".//w:tbl", WORD_NS):
        rows = table.findall("./w:tr", WORD_NS)
        fields = {}
        for row in rows[1:]:
            cells = row.findall("./w:tc", WORD_NS)
            if len(cells) != 2:
                raise ValueError("Every M3 BaseRole row must contain two cells.")
            key, value = map(_cell_text, cells)
            if key in fields:
                raise ValueError(f"Duplicate M3 field: {key}.")
            fields[key] = value
        result.append(fields)
    return result


def validate_package(package: dict) -> None:
    if package.get("schema_version") != 1 or package.get("methodology_version") != "1.1" or package.get("status") != "draft":
        raise ValueError("Expected a draft M3 package for methodology 1.1.")
    roles = package.get("base_roles")
    if not isinstance(roles, list) or tuple(role.get("code") for role in roles) != ROLE_CODES:
        raise ValueError("Expected six ordered, unique M3 BaseRoles.")
    description_keys = {key for _, key in DESCRIPTION_FIELDS}
    card_keys = {key for _, key in CARD_FIELDS}
    for role in roles:
        if set(role) != {"code", "description", "card"}:
            raise ValueError(f"Unexpected fields in {role.get('code')}.")
        for field, keys in (("description", description_keys), ("card", card_keys)):
            values = role[field]
            if not isinstance(values, dict) or set(values) != keys or not all(isinstance(v, str) and v.strip() for v in values.values()):
                raise ValueError(f"Incomplete {field} for {role['code']}.")


def build_package(base_roles_docx: Path) -> dict:
    tables = _tables(base_roles_docx)
    if len(tables) != 12:
        raise ValueError("Expected two tables for each of six BaseRoles.")
    roles = []
    for index, code in enumerate(ROLE_CODES):
        description_source, card_source = tables[2 * index:2 * index + 2]
        if set(description_source) != {source for source, _ in DESCRIPTION_FIELDS}:
            raise ValueError(f"Unexpected description fields for {code}.")
        if set(card_source) != {source for source, _ in CARD_FIELDS}:
            raise ValueError(f"Unexpected card fields for {code}.")
        roles.append({
            "code": code,
            "description": {target: description_source[source] for source, target in DESCRIPTION_FIELDS},
            "card": {target: card_source[source] for source, target in CARD_FIELDS},
        })
    package = {"schema_version": 1, "kind": "role_profiles", "methodology_version": "1.1", "status": "draft", "base_roles": roles}
    validate_package(package)
    return package


def write_package(package: dict, base_roles_docx: Path, role_profile_docx: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(package, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (output_dir / "base_roles.json").write_text(content, encoding="utf-8")
    role_blocks, role_tables = _word_blocks(role_profile_docx)
    role_contract = build_role_profile_contract(role_blocks, role_tables)
    contract_content = json.dumps(role_contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (output_dir / "role_profile_contract.json").write_text(contract_content, encoding="utf-8")
    base_markdown = _markdown_source(_word_blocks(base_roles_docx)[0])
    role_markdown = _markdown_source(role_blocks)
    (output_dir / "base_roles_source.md").write_text(base_markdown, encoding="utf-8")
    (output_dir / "role_profile_source.md").write_text(role_markdown, encoding="utf-8")
    normative_artifacts = [
        {"name": name, "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()}
        for name, value in (
            ("base_roles_source.md", base_markdown),
            ("role_profile_contract.json", contract_content),
            ("role_profile_source.md", role_markdown),
        )
    ]
    manifest = {
        "schema_version": 1,
        "methodology_version": "1.1",
        "status": "draft",
        "artifact": {"name": "base_roles.json", "sha256": hashlib.sha256(content.encode()).hexdigest()},
        "normative_artifacts": normative_artifacts,
        "sources": [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in (base_roles_docx, role_profile_docx)],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-roles-docx", type=Path, required=True)
    parser.add_argument("--role-profile-docx", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    write_package(build_package(args.base_roles_docx), args.base_roles_docx, args.role_profile_docx, args.output_dir)


if __name__ == "__main__":
    main()
