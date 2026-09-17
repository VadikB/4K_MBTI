"""Build deterministic M4 context artifacts from the supplied FROZEN DOCX."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
EXPECTED_SECTIONS = tuple(f"M4.{number}" for number in range(1, 7))
USER_CONTEXT_FIELDS = (
    ("ФИО", "full_name", "identity"),
    ("Контакты", "contacts", "identity"),
    ("Должность или статус", "position_or_status", "professional"),
    ("Подразделение или программа", "unit_or_program", "professional"),
    ("Специализация", "specialization", "professional"),
    ("Опыт в текущей роли", "current_role_experience", "professional"),
    ("Регулярные задачи", "regular_tasks", "professional"),
    ("Рабочие материалы", "work_materials", "professional"),
    ("Системы и инструменты", "systems_and_tools", "professional"),
    ("Дополнительная информация", "additional_information", "professional"),
    ("Нерелевантные области", "irrelevant_areas", "professional"),
)
ORGANIZATION_REQUIRED_FIELDS = (
    "name", "organization_type", "industry", "activity_description",
    "case_reality_level", "organization_name_usage_rules",
)


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{{{WORD_NS['w']}}}t":
            parts.append(node.text or "")
        elif node.tag == f"{{{WORD_NS['w']}}}br":
            parts.append("\n")
        elif node.tag == f"{{{WORD_NS['w']}}}tab":
            parts.append("\t")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in "".join(parts).split("\n")).strip()


def _cell_text(cell: ET.Element) -> str:
    values = [_paragraph_text(paragraph) for paragraph in cell.findall(".//w:p", WORD_NS)]
    return "\n".join(value for value in values if value)


def read_docx(path: Path) -> tuple[list[dict], list[list[list[str]]]]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", WORD_NS)
    if body is None:
        raise ValueError("M4 DOCX has no document body.")
    blocks: list[dict] = []
    tables: list[list[list[str]]] = []
    for child in body:
        if child.tag == f"{{{WORD_NS['w']}}}p":
            value = _paragraph_text(child)
            if value:
                style = child.find("w:pPr/w:pStyle", WORD_NS)
                blocks.append({
                    "type": "paragraph",
                    "style": style.attrib.get(f"{{{WORD_NS['w']}}}val", "") if style is not None else "",
                    "text": value,
                })
        elif child.tag == f"{{{WORD_NS['w']}}}tbl":
            rows = [[_cell_text(cell) for cell in row.findall("./w:tc", WORD_NS)] for row in child.findall("./w:tr", WORD_NS)]
            tables.append(rows)
            blocks.append({"type": "table", "rows": rows})
    return blocks, tables


def markdown_source(blocks: list[dict]) -> str:
    output: list[str] = []
    for index, block in enumerate(blocks):
        if block["type"] == "table":
            rows = block["rows"]
            if not rows or len({len(row) for row in rows}) != 1:
                raise ValueError("M4 source table has inconsistent columns.")
            clean = lambda value: value.replace("|", "\\|").replace("\n", "<br>")
            output.append("| " + " | ".join(map(clean, rows[0])) + " |")
            output.append("| " + " | ".join("---" for _ in rows[0]) + " |")
            output.extend("| " + " | ".join(map(clean, row)) + " |" for row in rows[1:])
        else:
            value = block["text"].replace("\n", "<br>\n")
            style = block["style"].lower()
            if index == 0:
                value = f"# {value}"
            elif style.startswith("heading"):
                level = re.search(r"\d+", style)
                value = f"{'#' * (int(level.group()) + 1 if level else 2)} {value}"
            output.append(value)
        output.append("")
    return "\n".join(output).rstrip() + "\n"


def _rows(table: list[list[str]], header: tuple[str, ...]) -> list[dict[str, str]]:
    if not table or tuple(table[0]) != header or any(len(row) != len(header) for row in table[1:]):
        raise ValueError(f"Unexpected M4 table: {header}.")
    return [dict(zip(header, row)) for row in table[1:]]


def build_contract(blocks: list[dict], tables: list[list[list[str]]]) -> dict:
    if len(tables) != 9:
        raise ValueError("M4 must contain nine tables.")
    paragraphs = [block["text"] for block in blocks if block["type"] == "paragraph"]
    if not all(any(value.startswith(section + " ") for value in paragraphs) for section in EXPECTED_SECTIONS):
        raise ValueError("M4.1-M4.6 must all be present.")

    organization_sections = _rows(tables[1], ("Раздел", "Содержание"))
    user_rows = _rows(tables[2], ("Поле", "Содержание"))
    if [row["Поле"] for row in user_rows] != [name for name, _, _ in USER_CONTEXT_FIELDS]:
        raise ValueError("Unexpected M4 UserContext fields.")
    user_fields = []
    for row, (_, key, category) in zip(user_rows, USER_CONTEXT_FIELDS):
        user_fields.append({
            "name": row["Поле"], "key": key, "category": category,
            "required": key == "full_name", "meaning": row["Содержание"],
            "allowed_for_case_generation": category == "professional",
            "allowed_for_evaluation": False,
        })

    contract = {
        "schema_version": 1,
        "kind": "m4_context_contract",
        "methodology_version": "1.1",
        "status": "draft",
        "source_status": "FROZEN",
        "organization_context": {
            "required_fields": list(ORGANIZATION_REQUIRED_FIELDS),
            "optional_site": True,
            "sections": [
                {"name": row["Раздел"], "meaning": row["Содержание"]}
                for row in organization_sections
            ],
            "confirmation_required": True,
        },
        "user_context": {
            "fields": user_fields,
            "states": ["draft", "needs_clarification", "confirmed", "archived"],
            "confirmation_required": True,
        },
        "composition_sources": _rows(tables[3], ("Источник", "Вклад")),
        "precedence_rules": _rows(tables[4], ("Содержание", "Определяющий источник и правило")),
        "m5_transfer": _rows(tables[5], ("Источник", "Передаваемые сведения и назначение")),
        "conflict_policy": {
            "exclude_disputed_facts": True,
            "block_on": ["role_selection", "authority", "mandatory_organization_constraint"],
            "missing_optional_fields_block": False,
            "infer_missing_facts": False,
        },
        "personalized_profile": {
            "source_count": 3,
            "role_profile_count": 1,
            "immutable_after_first_case_use": True,
            "exclude_identity_and_contacts_from_m5": True,
        },
    }
    validate_contract(contract)
    return contract


def validate_contract(contract: dict) -> None:
    if contract.get("schema_version") != 1 or contract.get("kind") != "m4_context_contract":
        raise ValueError("Unexpected M4 contract identity.")
    if contract.get("methodology_version") != "1.1" or contract.get("status") != "draft" or contract.get("source_status") != "FROZEN":
        raise ValueError("Expected M4 FROZEN source in a methodology 1.1 draft package.")
    organization = contract.get("organization_context") or {}
    if tuple(organization.get("required_fields") or []) != ORGANIZATION_REQUIRED_FIELDS or len(organization.get("sections") or []) != 6:
        raise ValueError("Incomplete M4 OrganizationContext contract.")
    fields = (contract.get("user_context") or {}).get("fields") or []
    if [field.get("key") for field in fields] != [key for _, key, _ in USER_CONTEXT_FIELDS]:
        raise ValueError("Incomplete M4 UserContext contract.")
    if [field["key"] for field in fields if field.get("required")] != ["full_name"]:
        raise ValueError("Only full_name is required in M4 UserContext.")
    if any(field["allowed_for_case_generation"] for field in fields if field["category"] == "identity"):
        raise ValueError("M4 identity data cannot be used for case generation.")
    if len(contract.get("composition_sources") or []) != 3 or len(contract.get("precedence_rules") or []) != 4 or len(contract.get("m5_transfer") or []) != 11:
        raise ValueError("Incomplete M4 composition or transfer rules.")
    profile = contract.get("personalized_profile") or {}
    if profile.get("source_count") != 3 or profile.get("role_profile_count") != 1 or not profile.get("immutable_after_first_case_use"):
        raise ValueError("Invalid M4 PersonalizedProfile rules.")


def personalized_profile_schema() -> dict:
    source_ref = {
        "type": "object",
        "required": ["version_id", "checksum"],
        "properties": {
            "version_id": {"type": "integer", "minimum": 1},
            "checksum": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "m4-personalized-profile-v1.schema.json",
        "title": "Снимок PersonalizedProfile M4",
        "type": "object",
        "required": ["schema_version", "methodology_version", "organization_id", "status", "sources", "content", "provenance", "conflicts", "checksum"],
        "properties": {
            "schema_version": {"const": 1},
            "methodology_version": {"const": "1.1"},
            "organization_id": {"type": "integer", "minimum": 1},
            "status": {"enum": ["ready", "blocked"]},
            "sources": {
                "type": "object",
                "required": ["organization_context", "role_profile", "user_context"],
                "properties": {name: source_ref for name in ("organization_context", "role_profile", "user_context")},
                "additionalProperties": False,
            },
            "content": {
                "type": "object",
                "description": "Только подтверждённый содержательный контекст без ФИО и контактов.",
                "required": ["organization_context", "role_profile", "user_context"],
                "properties": {
                    "organization_context": {"type": "object"},
                    "role_profile": {"type": "object"},
                    "user_context": {
                        "type": "object",
                        "not": {"anyOf": [{"required": ["full_name"]}, {"required": ["contacts"]}]},
                    },
                },
                "additionalProperties": False,
            },
            "provenance": {"type": "object"},
            "conflicts": {"type": "array", "items": {"type": "object"}},
            "checksum": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        },
        "additionalProperties": False,
    }


def write_package(source_docx: Path, output_dir: Path) -> None:
    blocks, tables = read_docx(source_docx)
    source = markdown_source(blocks)
    contract = json.dumps(build_contract(blocks, tables), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    schema = json.dumps(personalized_profile_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "m4_context_source.md": source,
        "context_contract.json": contract,
        "personalized_profile.schema.json": schema,
    }
    for name, content in artifacts.items():
        (output_dir / name).write_text(content, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "methodology_version": "1.1",
        "status": "draft",
        "source_status": "FROZEN",
        "artifacts": [
            {"name": name, "sha256": hashlib.sha256(content.encode()).hexdigest()}
            for name, content in sorted(artifacts.items())
        ],
        "sources": [{"name": source_docx.name, "sha256": hashlib.sha256(source_docx.read_bytes()).hexdigest()}],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-docx", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    write_package(args.source_docx, args.output_dir)


if __name__ == "__main__":
    main()
