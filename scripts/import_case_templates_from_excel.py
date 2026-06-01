from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from Api.database import get_connection, recompute_case_quality_checks


XLSX_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}
VALID_CASE_ID_RE = re.compile(r"^(C|T)-F\d{2}-\d{3}$")
PLACEHOLDER_CASE_TEXT_PREFIX = "TXT-"


@dataclass
class PassportRecord:
    type_code: str
    type_name: str
    goal: str
    context: str
    stakeholders_text: str
    triggers_text: str
    artifact_text: str
    structure_text: str
    checked_skills_text: str
    selection_tags_text: str
    roles_text: str
    role_personalization_rules: str
    personalization_text: str
    difficulty_toggles_text: str
    estimated_time_text: str
    interactivity_mode: str
    format_control_rules: str
    evaluation_criteria_text: str
    red_flags_text: str
    scoring_aggregation_rules: str
    bad_case_risks: str
    generation_notes: str
    recommended_answer_length: str


@dataclass
class RegistryRecord:
    case_id: str
    type_code: str
    title: str
    roles_text: str
    context_domain: str
    trigger_event: str
    stakeholders: str
    skill_codes: list[str]
    difficulty_level: str
    estimated_time_min: int | None
    personalization_text: str
    case_text_id: str
    status: str
    version: int
    methodologist_comment: str


@dataclass
class BaseCaseRecord:
    case_text_id: str
    case_id: str
    type_code: str
    title: str
    intro_context: str
    facts_data: str
    stakeholders: str
    trigger_details: str
    task_for_user: str
    artifact_text: str
    structure_hint: str
    constraints_text: str
    dialogue_turns: str
    personalization_text: str
    difficulty_variants: str
    evaluator_notes: str
    status: str
    version: int
    author_name: str
    reviewer_name: str
    methodologist_comment: str


@dataclass
class SkillRubricRecord:
    skill_code: str
    anchors_l1: str
    anchors_l2: str
    anchors_l3: str
    red_flags_text: str
    evidence_text: str
    examples_text: str
    comment_text: str


@dataclass
class RoleSkillTargetRecord:
    skill_code: str
    role_code: str
    target_level_code: str


class WorkbookReader:
    def __init__(self, workbook_path: Path) -> None:
        self.workbook_path = workbook_path
        self._zip = zipfile.ZipFile(workbook_path)
        self._shared_strings = self._load_shared_strings()
        self._sheet_targets = self._load_sheet_targets()

    def close(self) -> None:
        self._zip.close()

    def _load_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return []
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        shared: list[str] = []
        for si in root.findall("a:si", XLSX_NS):
            shared.append("".join(t.text or "" for t in si.findall(".//a:t", XLSX_NS)))
        return shared

    def _load_sheet_targets(self) -> dict[str, str]:
        workbook = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("p:Relationship", XLSX_NS)}
        targets: dict[str, str] = {}
        for sheet in workbook.find("a:sheets", XLSX_NS):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            targets[name] = "xl/" + relmap[rel_id]
        return targets

    def read_sheet(self, sheet_name: str) -> list[list[str]]:
        target = self._sheet_targets[sheet_name]
        root = ET.fromstring(self._zip.read(target))
        rows: list[list[str]] = []
        sheet_data = root.find("a:sheetData", XLSX_NS)
        if sheet_data is None:
            return rows
        for row in sheet_data.findall("a:row", XLSX_NS):
            values: dict[int, str] = {}
            for cell in row.findall("a:c", XLSX_NS):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", ref)
                if not match:
                    continue
                column_index = self._column_to_index(match.group(1))
                values[column_index] = self._cell_value(cell)
            max_index = max(values.keys(), default=-1)
            rows.append([values.get(i, "") for i in range(max_index + 1)])
        return rows

    def _cell_value(self, cell: ET.Element) -> str:
        value_type = cell.attrib.get("t")
        if value_type == "inlineStr":
            inline = cell.find("a:is", XLSX_NS)
            if inline is None:
                return ""
            return "".join(node.text or "" for node in inline.findall(".//a:t", XLSX_NS)).strip()
        value_node = cell.find("a:v", XLSX_NS)
        if value_node is None or value_node.text is None:
            return ""
        raw = value_node.text
        if value_type == "s":
            return self._shared_strings[int(raw)].strip()
        return raw.strip()

    @staticmethod
    def _column_to_index(column_name: str) -> int:
        value = 0
        for char in column_name:
            if char.isalpha():
                value = value * 26 + (ord(char.upper()) - 64)
        return value - 1


def clean_text(value: str) -> str:
    return re.sub(r"[ \t]+", " ", (value or "").replace("\r", "")).strip()


def valid_case_id(value: str) -> bool:
    return bool(VALID_CASE_ID_RE.match(clean_text(value)))


def derive_case_text_code(raw_case_text_id: str, linked_case_id: str) -> str:
    raw = clean_text(raw_case_text_id)
    linked = clean_text(linked_case_id)
    if valid_case_id(raw):
        return raw
    if valid_case_id(linked) and linked.startswith("C-"):
        return "T-" + linked[2:]
    if valid_case_id(linked):
        return f"{linked}__TEXT"
    return f"{PLACEHOLDER_CASE_TEXT_PREFIX}{linked or 'UNKNOWN'}"


def parse_int(value: str) -> int | None:
    value = clean_text(value)
    if not value:
        return None
    digits = re.findall(r"\d+", value)
    return int(digits[0]) if digits else None


def parse_version(value: str) -> int:
    value = clean_text(value).lower()
    digits = re.findall(r"\d+", value)
    return int(digits[0]) if digits else 1


def normalize_status(value: str, default: str = "draft") -> str:
    lowered = clean_text(value).lower()
    if lowered in {"draft", "ready", "retired"}:
        return lowered
    return default


def normalize_skill_code(value: str) -> str:
    normalized = clean_text(value).replace("К", "K").replace("к", "k")
    return normalized.upper()


def split_bullets(value: str) -> list[str]:
    text = (value or "").replace("\r", "\n")
    items: list[str] = []
    for part in re.split(r"\n+", text):
        cleaned = clean_text(re.sub(r"^[•\-\d\)\.\s]+", "", part))
        if cleaned:
            items.append(cleaned)
    return items


def split_inline_tags(value: str) -> list[str]:
    text = (value or "").replace("\r", "\n")
    normalized = re.sub(r"[;,]+", "\n", text)
    items: list[str] = []
    for part in re.split(r"\n+", normalized):
        cleaned = clean_text(re.sub(r"^[•\-\d\)\.\s]+", "", part))
        if cleaned:
            items.append(cleaned)
    return items


def split_author_reviewer(value: str) -> tuple[str, str]:
    raw = clean_text(value)
    if not raw:
        return "", ""
    parts = [clean_text(part) for part in re.split(r"\s*/\s*|\s*\|\s*", raw) if clean_text(part)]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " / ".join(parts[1:])


def _normalize_flag_code_fragment(value: str) -> str:
    normalized = clean_text(value).lower()
    normalized = normalized.replace("ё", "е")
    normalized = normalized.replace("=", " ")
    normalized = re.sub(r"[^\w\s]+", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", "_", normalized).strip("_")
    return normalized


def _infer_red_flag_severity(flag_name: str) -> str:
    lowered = clean_text(flag_name).lower()
    critical_markers = (
        "обвин",
        "угроз",
        "манипуляц",
        "нет ",
        "игнор",
        "самодеятельность",
        "ярлык",
    )
    return "high" if any(marker in lowered for marker in critical_markers) else "medium"


def parse_red_flags(value: str) -> list[tuple[str, str, str, str, bool]]:
    items = split_bullets(value)
    parsed: list[tuple[str, str, str, str, bool]] = []
    seen_codes: set[str] = set()
    for item in items:
        flag_code = _normalize_flag_code_fragment(item)
        if not flag_code:
            continue
        base_code = flag_code
        suffix = 2
        while flag_code in seen_codes:
            flag_code = f"{base_code}_{suffix}"
            suffix += 1
        seen_codes.add(flag_code)
        parsed.append(
            (
                flag_code,
                item,
                f"Импортировано из карты кейсов: {item}.",
                _infer_red_flag_severity(item),
                True,
            )
        )
    return parsed


def parse_roles(value: str) -> list[str]:
    resolved: list[str] = []
    lowered = clean_text(value).lower().replace("ё", "е")
    patterns = [
        (r"(^|[\s,;/(\[])l($|[\s,;/)\]])|линейн", "linear_employee"),
        (r"(^|[\s,;/(\[])m($|[\s,;/)\]])|менедж", "manager"),
        (r"leader|лидер", "leader"),
    ]
    for pattern, role_code in patterns:
        if re.search(pattern, lowered) and role_code not in resolved:
            resolved.append(role_code)
    return resolved


def infer_type_category(type_code: str, registry_rows: Iterable[RegistryRecord]) -> str:
    prefix_weight: dict[str, int] = {}
    for row in registry_rows:
        if row.type_code != type_code:
            continue
        for skill_code in row.skill_codes:
            prefix = skill_code.split(".", 1)[0]
            prefix_weight[prefix] = prefix_weight.get(prefix, 0) + 1
    if not prefix_weight:
        return "communication"
    dominant_prefix = max(prefix_weight.items(), key=lambda item: item[1])[0]
    return {
        "K1": "communication",
        "K2": "teamwork",
        "K3": "creative",
        "K4": "analytical",
    }.get(dominant_prefix, "communication")


def infer_artifact_code(value: str) -> str:
    lowered = clean_text(value).lower()
    if "вопрос" in lowered and "резюм" in lowered:
        return "questions_summary"
    if "сценар" in lowered or "диалог" in lowered:
        return "dialogue_script"
    if "список" in lowered and "идей" in lowered:
        return "action_plan"
    if "вариант" in lowered and "риск" in lowered and "решен" in lowered:
        return "action_plan"
    if "пилот" in lowered or "метрик" in lowered and "план" in lowered:
        return "pilot_plan"
    if "анализ причин" in lowered:
        return "root_cause_analysis"
    if "приорит" in lowered or "ранжир" in lowered:
        return "prioritization"
    if "план" in lowered:
        return "action_plan"
    return "stakeholder_message"


def infer_interactivity_limits(
    interactivity_mode: str,
    recommended_answer_length: str = "",
    format_control_rules: str = "",
) -> tuple[int | None, int | None]:
    normalized = clean_text(interactivity_mode).lower()
    candidate_text = " ".join(
        part for part in (clean_text(format_control_rules), clean_text(recommended_answer_length)) if part
    )
    numbers = [int(match) for match in re.findall(r"\d+", candidate_text)]
    upper_bound = max(numbers) if numbers else None
    if "диалог" in normalized:
        if upper_bound and upper_bound > 0:
            return (upper_bound + 1) // 2, upper_bound
        return 4, 8
    if normalized == "1 ход":
        return 2, 4
    if upper_bound and upper_bound > 0:
        return (upper_bound + 1) // 2, upper_bound
    return None, None


def load_passports(reader: WorkbookReader) -> dict[str, PassportRecord]:
    rows = reader.read_sheet("Паспорт типов кейсов")
    passports: dict[str, PassportRecord] = {}
    for row in rows[1:]:
        if not row:
            continue
        type_code = clean_text(row[0] if len(row) > 0 else "")
        if not type_code:
            continue
        passports[type_code] = PassportRecord(
            type_code=type_code,
            type_name=clean_text(row[1] if len(row) > 1 else ""),
            goal=clean_text(row[2] if len(row) > 2 else ""),
            context=clean_text(row[3] if len(row) > 3 else ""),
            stakeholders_text=(row[4] if len(row) > 4 else "").strip(),
            triggers_text=(row[5] if len(row) > 5 else "").strip(),
            artifact_text=clean_text(row[6] if len(row) > 6 else ""),
            structure_text=(row[7] if len(row) > 7 else "").strip(),
            checked_skills_text=(row[8] if len(row) > 8 else "").strip(),
            selection_tags_text=(row[9] if len(row) > 9 else "").strip(),
            roles_text=clean_text(row[10] if len(row) > 10 else ""),
            role_personalization_rules=(row[11] if len(row) > 11 else "").strip(),
            personalization_text=(row[12] if len(row) > 12 else "").strip(),
            difficulty_toggles_text=(row[13] if len(row) > 13 else "").strip(),
            estimated_time_text=clean_text(row[14] if len(row) > 14 else ""),
            interactivity_mode=clean_text(row[15] if len(row) > 15 else ""),
            format_control_rules=(row[16] if len(row) > 16 else "").strip(),
            evaluation_criteria_text=(row[17] if len(row) > 17 else "").strip(),
            red_flags_text=(row[18] if len(row) > 18 else "").strip(),
            scoring_aggregation_rules=(row[19] if len(row) > 19 else "").strip(),
            bad_case_risks=(row[20] if len(row) > 20 else "").strip(),
            generation_notes=(row[21] if len(row) > 21 else "").strip(),
            recommended_answer_length=clean_text(row[22] if len(row) > 22 else ""),
        )
    return passports


def load_registry(reader: WorkbookReader) -> list[RegistryRecord]:
    rows = reader.read_sheet("Реестр кейсов")
    records: list[RegistryRecord] = []
    for row in rows[1:]:
        case_id = clean_text(row[0] if len(row) > 0 else "")
        if not valid_case_id(case_id):
            continue
        skills = [
            normalize_skill_code(row[index])
            for index in range(7, 12)
            if len(row) > index and clean_text(row[index])
        ]
        records.append(
            RegistryRecord(
                case_id=case_id,
                type_code=clean_text(row[1] if len(row) > 1 else ""),
                title=clean_text(row[2] if len(row) > 2 else ""),
                roles_text=clean_text(row[3] if len(row) > 3 else ""),
                context_domain=clean_text(row[4] if len(row) > 4 else ""),
                trigger_event=clean_text(row[5] if len(row) > 5 else ""),
                stakeholders=(row[6] if len(row) > 6 else "").strip(),
                skill_codes=skills,
                difficulty_level=normalize_status(clean_text(row[12] if len(row) > 12 else "").replace("base", "draft"), default="draft"),
                estimated_time_min=parse_int(row[13] if len(row) > 13 else ""),
                personalization_text=(row[14] if len(row) > 14 else "").strip(),
                case_text_id=clean_text(row[15] if len(row) > 15 else ""),
                status=normalize_status(row[16] if len(row) > 16 else "", default="draft"),
                version=parse_version(row[17] if len(row) > 17 else ""),
                methodologist_comment=(row[19] if len(row) > 19 else "").strip(),
            )
        )
    for record in records:
        record.difficulty_level = "hard" if clean_text(record.difficulty_level).lower() == "hard" else "base"
    return records


def load_base_cases(reader: WorkbookReader) -> dict[str, BaseCaseRecord]:
    rows = reader.read_sheet("База кейсов")
    base_cases: dict[str, BaseCaseRecord] = {}
    seen_case_text_ids: dict[str, str] = {}
    for row in rows[1:]:
        case_text_id = clean_text(row[0] if len(row) > 0 else "")
        linked_case_id = clean_text(row[1] if len(row) > 1 else "")
        if not valid_case_id(linked_case_id):
            continue
        canonical_case_text_id = derive_case_text_code(case_text_id, linked_case_id)
        unique_case_text_id = canonical_case_text_id
        previous_owner = seen_case_text_ids.get(canonical_case_text_id)
        if previous_owner and previous_owner != linked_case_id:
            unique_case_text_id = f"{canonical_case_text_id}__{linked_case_id}"
        seen_case_text_ids[unique_case_text_id] = linked_case_id
        if unique_case_text_id == canonical_case_text_id:
            seen_case_text_ids[canonical_case_text_id] = linked_case_id
        author_name, reviewer_name = split_author_reviewer(row[18] if len(row) > 18 else "")
        base_cases[linked_case_id] = BaseCaseRecord(
            case_text_id=unique_case_text_id,
            case_id=linked_case_id,
            type_code=clean_text(row[2] if len(row) > 2 else ""),
            title=clean_text(row[3] if len(row) > 3 else ""),
            intro_context=(row[4] if len(row) > 4 else "").strip(),
            facts_data=(row[5] if len(row) > 5 else "").strip(),
            stakeholders=(row[6] if len(row) > 6 else "").strip(),
            trigger_details=(row[7] if len(row) > 7 else "").strip(),
            task_for_user=(row[8] if len(row) > 8 else "").strip(),
            artifact_text=clean_text(row[9] if len(row) > 9 else ""),
            structure_hint=(row[10] if len(row) > 10 else "").strip(),
            constraints_text=(row[11] if len(row) > 11 else "").strip(),
            dialogue_turns=(row[12] if len(row) > 12 else "").strip(),
            personalization_text=(row[13] if len(row) > 13 else "").strip(),
            difficulty_variants=(row[14] if len(row) > 14 else "").strip(),
            evaluator_notes=(row[15] if len(row) > 15 else "").strip(),
            status=normalize_status(row[16] if len(row) > 16 else "", default="draft"),
            version=parse_version(row[17] if len(row) > 17 else ""),
            author_name=author_name,
            reviewer_name=reviewer_name,
            methodologist_comment=(row[20] if len(row) > 20 else "").strip(),
        )
    return base_cases


def load_skill_rubrics(reader: WorkbookReader) -> list[SkillRubricRecord]:
    rows = reader.read_sheet("Рубрика оценки")
    records: list[SkillRubricRecord] = []
    for row in rows[1:]:
        skill_code = normalize_skill_code(row[0] if len(row) > 0 else "")
        if not skill_code:
            continue
        records.append(
            SkillRubricRecord(
                skill_code=skill_code,
                anchors_l1=(row[4] if len(row) > 4 else "").strip(),
                anchors_l2=(row[5] if len(row) > 5 else "").strip(),
                anchors_l3=(row[6] if len(row) > 6 else "").strip(),
                red_flags_text=(row[7] if len(row) > 7 else "").strip(),
                evidence_text=(row[8] if len(row) > 8 else "").strip(),
                examples_text=(row[9] if len(row) > 9 else "").strip(),
                comment_text=(row[10] if len(row) > 10 else "").strip(),
            )
        )
    return records


def _is_marked_target(value: str) -> bool:
    normalized = clean_text(value).lower()
    return normalized in {"x", "х", "1", "+"}


def load_role_skill_targets(reader: WorkbookReader) -> list[RoleSkillTargetRecord]:
    rows = reader.read_sheet("Карта компетенций")
    records: list[RoleSkillTargetRecord] = []
    role_columns = {
        "linear_employee": (3, 4, 5),
        "manager": (6, 7, 8),
        "leader": (9, 10, 11),
    }
    level_map = {
        0: "L1",
        1: "L2",
        2: "L3",
    }
    for row in rows[2:]:
        skill_code = normalize_skill_code(row[0] if len(row) > 0 else "")
        if not skill_code:
            continue
        for role_code, columns in role_columns.items():
            marked_levels = [
                level_map[offset]
                for offset, column_index in enumerate(columns)
                if len(row) > column_index and _is_marked_target(row[column_index])
            ]
            if not marked_levels:
                continue
            target_level_code = marked_levels[-1]
            records.append(RoleSkillTargetRecord(skill_code=skill_code, role_code=role_code, target_level_code=target_level_code))
    return records


def build_placeholder_base_case(registry_row: RegistryRecord) -> BaseCaseRecord:
    task = registry_row.title.rstrip(".")
    if not task.endswith("?"):
        task = f"{task}. Опишите ваше решение и следующий шаг."
    case_text_code = registry_row.case_text_id if valid_case_id(registry_row.case_text_id) else f"{PLACEHOLDER_CASE_TEXT_PREFIX}{registry_row.case_id}"
    return BaseCaseRecord(
        case_text_id=case_text_code,
        case_id=registry_row.case_id,
        type_code=registry_row.type_code,
        title=registry_row.title,
        intro_context=registry_row.context_domain or registry_row.title,
        facts_data=registry_row.stakeholders,
        stakeholders=registry_row.stakeholders,
        trigger_details=registry_row.trigger_event,
        task_for_user=task,
        artifact_text="",
        structure_hint="",
        constraints_text="",
        dialogue_turns="",
        personalization_text=registry_row.personalization_text,
        difficulty_variants="",
        evaluator_notes="Автоматически созданный placeholder: в Excel не найден текст кейса по связанному CaseID.",
        status="draft",
        version=registry_row.version,
        author_name="",
        reviewer_name="",
        methodologist_comment=registry_row.methodologist_comment,
    )


def ensure_personalization_fields(connection, passport_id: int, text_value: str) -> None:
    placeholders = re.findall(r"\{([^{}]+)\}", text_value or "")
    seen_codes: list[str] = []
    for placeholder in placeholders:
        code = re.sub(r"[^a-zA-Z0-9_]+", "_", placeholder.strip()).strip("_").lower()
        if not code or code in seen_codes:
            continue
        seen_codes.append(code)
        row = connection.execute(
            """
            INSERT INTO case_personalization_fields (field_code, field_name, description, source_type, is_required)
            VALUES (%s, %s, %s, 'excel_import', FALSE)
            ON CONFLICT (field_code) DO UPDATE
            SET field_name = EXCLUDED.field_name,
                description = EXCLUDED.description
            RETURNING id
            """,
            (code, placeholder.strip(), f"Импортировано из Excel: {placeholder.strip()}"),
        ).fetchone()
        field_id = row["id"]
        connection.execute(
            """
            INSERT INTO case_type_personalization_fields (case_type_passport_id, personalization_field_id, display_order, version)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (case_type_passport_id, personalization_field_id) DO UPDATE
            SET display_order = EXCLUDED.display_order
            """,
            (passport_id, field_id, len(seen_codes)),
        )


def upsert_passports(connection, passports: dict[str, PassportRecord], registry_rows: list[RegistryRecord]) -> dict[str, int]:
    artifact_map = {
        row["artifact_code"]: row["id"]
        for row in connection.execute("SELECT id, artifact_code FROM case_response_artifacts").fetchall()
    }
    passport_ids: dict[str, int] = {}
    for type_code, record in passports.items():
        artifact_code = infer_artifact_code(record.artifact_text)
        artifact_id = artifact_map[artifact_code]
        time_values = [int(value) for value in re.findall(r"\d+", record.estimated_time_text)]
        recommended_min = time_values[0] if time_values else None
        recommended_max = time_values[-1] if time_values else recommended_min
        max_user_messages, max_total_turns = infer_interactivity_limits(
            record.interactivity_mode,
            record.recommended_answer_length,
            record.format_control_rules,
        )
        roles = parse_roles(record.roles_text)
        category = infer_type_category(type_code, registry_rows)
        description = "\n".join(part for part in [record.goal, record.context] if part)
        selection_tags = split_inline_tags(record.selection_tags_text)
        row = connection.execute(
            """
            INSERT INTO case_type_passports (
                type_code,
                type_name,
                type_category,
                description,
                artifact_id,
                base_structure_description,
                success_criteria,
                recommended_time_min,
                recommended_time_max,
                interactivity_mode,
                max_user_messages,
                max_total_turns,
                recommended_answer_length,
                selection_tags,
                role_personalization_rules,
                format_control_rules,
                scoring_aggregation_rules,
                bad_case_risks,
                generation_notes,
                allowed_role_linear,
                allowed_role_manager,
                allowed_role_leader,
                status,
                version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', 1)
            ON CONFLICT (type_code) DO UPDATE
            SET
                type_name = EXCLUDED.type_name,
                type_category = EXCLUDED.type_category,
                description = EXCLUDED.description,
                artifact_id = EXCLUDED.artifact_id,
                base_structure_description = EXCLUDED.base_structure_description,
                success_criteria = EXCLUDED.success_criteria,
                recommended_time_min = EXCLUDED.recommended_time_min,
                recommended_time_max = EXCLUDED.recommended_time_max,
                interactivity_mode = EXCLUDED.interactivity_mode,
                max_user_messages = EXCLUDED.max_user_messages,
                max_total_turns = EXCLUDED.max_total_turns,
                recommended_answer_length = EXCLUDED.recommended_answer_length,
                selection_tags = EXCLUDED.selection_tags,
                role_personalization_rules = EXCLUDED.role_personalization_rules,
                format_control_rules = EXCLUDED.format_control_rules,
                scoring_aggregation_rules = EXCLUDED.scoring_aggregation_rules,
                bad_case_risks = EXCLUDED.bad_case_risks,
                generation_notes = EXCLUDED.generation_notes,
                allowed_role_linear = EXCLUDED.allowed_role_linear,
                allowed_role_manager = EXCLUDED.allowed_role_manager,
                allowed_role_leader = EXCLUDED.allowed_role_leader,
                updated_at = NOW()
            RETURNING id
            """,
            (
                record.type_code,
                record.type_name or record.type_code,
                category,
                description,
                artifact_id,
                record.structure_text,
                record.evaluation_criteria_text,
                recommended_min,
                recommended_max,
                record.interactivity_mode,
                max_user_messages,
                max_total_turns,
                record.recommended_answer_length,
                json.dumps(selection_tags, ensure_ascii=False),
                record.role_personalization_rules,
                record.format_control_rules,
                record.scoring_aggregation_rules,
                record.bad_case_risks,
                record.generation_notes,
                "linear_employee" in roles,
                "manager" in roles,
                "leader" in roles,
            ),
        ).fetchone()
        passport_id = int(row["id"])
        passport_ids[type_code] = passport_id
        ensure_personalization_fields(connection, passport_id, record.personalization_text)
        connection.execute(
            """
            DELETE FROM case_type_red_flags
            WHERE case_type_passport_id = %s
            """,
            (passport_id,),
        )
        for flag_code, flag_name, flag_description, severity, is_active in parse_red_flags(record.red_flags_text):
            connection.execute(
                """
                INSERT INTO case_type_red_flags (
                    case_type_passport_id,
                    flag_code,
                    flag_name,
                    flag_description,
                    severity,
                    is_active,
                    version
                )
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (case_type_passport_id, flag_code) DO UPDATE
                SET
                    flag_name = EXCLUDED.flag_name,
                    flag_description = EXCLUDED.flag_description,
                    severity = EXCLUDED.severity,
                    is_active = EXCLUDED.is_active,
                    version = GREATEST(case_type_red_flags.version, EXCLUDED.version)
                """,
                (passport_id, flag_code, flag_name, flag_description, severity, is_active),
            )
    return passport_ids


def fetch_role_ids(connection) -> dict[str, int]:
    return {row["code"]: int(row["id"]) for row in connection.execute("SELECT id, code FROM roles").fetchall()}


def fetch_skill_ids(connection) -> dict[str, int]:
    return {row["skill_code"].upper(): int(row["id"]) for row in connection.execute("SELECT id, skill_code FROM skills").fetchall()}


def upsert_registry(
    connection,
    registry_rows: list[RegistryRecord],
    base_cases: dict[str, BaseCaseRecord],
    passport_ids: dict[str, int],
) -> dict[str, int]:
    role_ids = fetch_role_ids(connection)
    skill_ids = fetch_skill_ids(connection)
    case_registry_ids: dict[str, int] = {}

    for row in registry_rows:
        passport_id = passport_ids[row.type_code]
        existing = connection.execute(
            "SELECT id, status FROM cases_registry WHERE case_id_code = %s",
            (row.case_id,),
        ).fetchone()
        incoming_status = normalize_status(row.status or "draft", default="draft")
        preserved_status = existing["status"] if existing else incoming_status
        registry_id = connection.execute(
            """
            INSERT INTO cases_registry (
                case_id_code,
                case_type_passport_id,
                title,
                context_domain,
                trigger_event,
                stakeholders_text,
                estimated_time_min,
                difficulty_level,
                status,
                version,
                methodologist_comment
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (case_id_code) DO UPDATE
            SET
                case_type_passport_id = EXCLUDED.case_type_passport_id,
                title = EXCLUDED.title,
                context_domain = EXCLUDED.context_domain,
                trigger_event = EXCLUDED.trigger_event,
                stakeholders_text = EXCLUDED.stakeholders_text,
                estimated_time_min = EXCLUDED.estimated_time_min,
                difficulty_level = EXCLUDED.difficulty_level,
                status = %s,
                version = GREATEST(cases_registry.version, EXCLUDED.version),
                methodologist_comment = EXCLUDED.methodologist_comment,
                updated_at = NOW()
            RETURNING id
            """,
            (
                row.case_id,
                passport_id,
                row.title,
                row.context_domain,
                row.trigger_event,
                row.stakeholders,
                row.estimated_time_min,
                row.difficulty_level,
                incoming_status,
                row.version,
                row.methodologist_comment,
                preserved_status,
            ),
        ).fetchone()["id"]
        case_registry_ids[row.case_id] = int(registry_id)

        connection.execute("DELETE FROM case_registry_roles WHERE cases_registry_id = %s", (registry_id,))
        for role_code in parse_roles(row.roles_text):
            role_id = role_ids.get(role_code)
            if role_id:
                connection.execute(
                    "INSERT INTO case_registry_roles (cases_registry_id, role_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (registry_id, role_id),
                )

        connection.execute("DELETE FROM case_registry_skills WHERE cases_registry_id = %s", (registry_id,))
        for display_order, skill_code in enumerate(row.skill_codes, start=1):
            skill_id = skill_ids.get(skill_code)
            if skill_id:
                connection.execute(
                    """
                    INSERT INTO case_registry_skills (cases_registry_id, skill_id, signal_priority, is_required, display_order)
                    VALUES (%s, %s, 'leading', TRUE, %s)
                    ON CONFLICT (cases_registry_id, skill_id) DO UPDATE
                    SET signal_priority = EXCLUDED.signal_priority,
                        is_required = EXCLUDED.is_required,
                        display_order = EXCLUDED.display_order
                    """,
                    (registry_id, skill_id, display_order),
                )

        base_case = base_cases.get(row.case_id) or build_placeholder_base_case(row)
        case_text_status = normalize_status(base_case.status or "draft", default="draft")
        existing_text = connection.execute(
            "SELECT id, status, case_text_code FROM case_texts WHERE cases_registry_id = %s",
            (registry_id,),
        ).fetchone()
        preserved_text_status = existing_text["status"] if existing_text else case_text_status
        common_payload = (
            base_case.case_text_id,
            registry_id,
            base_case.intro_context or row.context_domain or row.title,
            "\n".join(part for part in [base_case.facts_data, base_case.stakeholders] if part),
            base_case.trigger_details or row.trigger_event,
            base_case.task_for_user or row.title,
            base_case.constraints_text,
            base_case.dialogue_turns,
            base_case.personalization_text or row.personalization_text,
            base_case.structure_hint,
            base_case.difficulty_variants,
            "\n\n".join(part for part in [base_case.evaluator_notes, base_case.methodologist_comment] if part),
            base_case.stakeholders,
            base_case.artifact_text,
            base_case.structure_hint,
            base_case.dialogue_turns,
            base_case.personalization_text or row.personalization_text,
            base_case.difficulty_variants,
            base_case.evaluator_notes,
            base_case.author_name,
            base_case.reviewer_name,
            base_case.methodologist_comment,
            preserved_text_status,
            base_case.version,
        )
        if existing_text:
            connection.execute(
                """
                UPDATE case_texts
                SET
                    case_text_code = %s,
                    cases_registry_id = %s,
                    intro_context = %s,
                    facts_data = %s,
                    trigger_details = %s,
                    task_for_user = %s,
                    constraints_text = %s,
                    stakes_text = %s,
                    personalization_variables = %s,
                    base_variant_text = %s,
                    hard_variant_text = %s,
                    notes = %s,
                    participants_roles = %s,
                    expected_artifact = %s,
                    answer_structure_hint = %s,
                    dialog_turns_hint = %s,
                    personalization_options = %s,
                    difficulty_toggles = %s,
                    evaluation_notes = %s,
                    author_name = %s,
                    reviewer_name = %s,
                    methodologist_comment = %s,
                    status = %s,
                    version = GREATEST(version, %s),
                    updated_at = NOW()
                WHERE cases_registry_id = %s
                """,
                common_payload + (registry_id,),
            )
        else:
            connection.execute(
                """
                INSERT INTO case_texts (
                    case_text_code,
                    cases_registry_id,
                    intro_context,
                    facts_data,
                    trigger_details,
                    task_for_user,
                    constraints_text,
                    stakes_text,
                    personalization_variables,
                    base_variant_text,
                    hard_variant_text,
                    notes,
                    participants_roles,
                    expected_artifact,
                    answer_structure_hint,
                    dialog_turns_hint,
                    personalization_options,
                    difficulty_toggles,
                    evaluation_notes,
                    author_name,
                    reviewer_name,
                    methodologist_comment,
                    status,
                    version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (case_text_code) DO UPDATE
                SET
                    cases_registry_id = EXCLUDED.cases_registry_id,
                    intro_context = EXCLUDED.intro_context,
                    facts_data = EXCLUDED.facts_data,
                    trigger_details = EXCLUDED.trigger_details,
                    task_for_user = EXCLUDED.task_for_user,
                    constraints_text = EXCLUDED.constraints_text,
                    stakes_text = EXCLUDED.stakes_text,
                    personalization_variables = EXCLUDED.personalization_variables,
                    base_variant_text = EXCLUDED.base_variant_text,
                    hard_variant_text = EXCLUDED.hard_variant_text,
                    notes = EXCLUDED.notes,
                    participants_roles = EXCLUDED.participants_roles,
                    expected_artifact = EXCLUDED.expected_artifact,
                    answer_structure_hint = EXCLUDED.answer_structure_hint,
                    dialog_turns_hint = EXCLUDED.dialog_turns_hint,
                    personalization_options = EXCLUDED.personalization_options,
                    difficulty_toggles = EXCLUDED.difficulty_toggles,
                    evaluation_notes = EXCLUDED.evaluation_notes,
                    author_name = EXCLUDED.author_name,
                    reviewer_name = EXCLUDED.reviewer_name,
                    methodologist_comment = EXCLUDED.methodologist_comment,
                    status = EXCLUDED.status,
                    version = GREATEST(case_texts.version, EXCLUDED.version),
                    updated_at = NOW()
                """,
                common_payload,
            )
    return case_registry_ids


def upsert_skill_rubrics(connection, rubric_rows: list[SkillRubricRecord]) -> None:
    skill_ids = fetch_skill_ids(connection)
    for row in rubric_rows:
        skill_id = skill_ids.get(row.skill_code)
        if not skill_id:
            continue
        common_tail = (
            row.evidence_text,
            row.examples_text,
            row.comment_text,
        )
        for level_code, anchors_text in (
            ("L1", row.anchors_l1),
            ("L2", row.anchors_l2),
            ("L3", row.anchors_l3),
        ):
            if not any([anchors_text, row.evidence_text, row.examples_text, row.comment_text]):
                continue
            connection.execute(
                """
                INSERT INTO skill_level_rubrics (
                    skill_id,
                    level_code,
                    anchors_text,
                    evidence_to_look_for,
                    examples_text,
                    comment,
                    version
                )
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (skill_id, level_code) DO UPDATE
                SET
                    anchors_text = EXCLUDED.anchors_text,
                    evidence_to_look_for = EXCLUDED.evidence_to_look_for,
                    examples_text = EXCLUDED.examples_text,
                    comment = EXCLUDED.comment,
                    version = GREATEST(skill_level_rubrics.version, EXCLUDED.version),
                    updated_at = NOW()
                """,
                (skill_id, level_code, anchors_text, *common_tail),
            )


def upsert_role_targets(connection, target_rows: list[RoleSkillTargetRecord]) -> None:
    skill_ids = fetch_skill_ids(connection)
    role_ids = fetch_role_ids(connection)
    for row in target_rows:
        skill_id = skill_ids.get(row.skill_code)
        role_id = role_ids.get(row.role_code)
        if not skill_id or not role_id:
            continue
        connection.execute(
            """
            INSERT INTO role_skill_targets (role_id, skill_id, target_level_code)
            VALUES (%s, %s, %s)
            ON CONFLICT (role_id, skill_id) DO UPDATE
            SET
                target_level_code = EXCLUDED.target_level_code,
                updated_at = NOW()
            """,
            (role_id, skill_id, row.target_level_code),
        )


def build_dry_run(connection, registry_rows: list[RegistryRecord]) -> tuple[list[str], list[str], list[str], list[str]]:
    existing_rows = connection.execute("SELECT case_id_code, title FROM cases_registry").fetchall()
    existing_map = {row["case_id_code"]: row["title"] for row in existing_rows}
    creates: list[str] = []
    updates: list[str] = []
    keeps: list[str] = []
    for row in registry_rows:
        existing_title = existing_map.get(row.case_id)
        if existing_title is None:
            creates.append(row.case_id)
        elif clean_text(existing_title) != clean_text(row.title):
            updates.append(row.case_id)
        else:
            keeps.append(row.case_id)
    excluded = sorted(existing for existing in existing_map if existing not in {row.case_id for row in registry_rows})
    return creates, updates, keeps, excluded


def print_dry_run_summary(registry_rows: list[RegistryRecord], creates: list[str], updates: list[str], keeps: list[str], excluded: list[str]) -> None:
    print("VALID_CASE_IDS", len(registry_rows))
    print("CREATE_COUNT", len(creates))
    print("UPDATE_COUNT", len(updates))
    print("KEEP_COUNT", len(keeps))
    print("EXCLUDED_EXISTING_COUNT", len(excluded))
    print("CREATE_SAMPLE", creates[:20])
    print("UPDATE_SAMPLE", updates[:20])
    print("EXCLUDED_EXISTING_SAMPLE", excluded[:20])


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely import case templates from Excel into the methodological layer.")
    parser.add_argument("--workbook", required=True, help="Absolute path to .xlsx workbook.")
    parser.add_argument("--apply", action="store_true", help="Persist changes into PostgreSQL.")
    args = parser.parse_args()

    workbook_path = Path(args.workbook).expanduser().resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    reader = WorkbookReader(workbook_path)
    try:
        passports = load_passports(reader)
        registry_rows = load_registry(reader)
        base_cases = load_base_cases(reader)
        rubric_rows = load_skill_rubrics(reader)
        role_target_rows = load_role_skill_targets(reader)
    finally:
        reader.close()

    with get_connection() as connection:
        creates, updates, keeps, excluded = build_dry_run(connection, registry_rows)
        print_dry_run_summary(registry_rows, creates, updates, keeps, excluded)
        if not args.apply:
            return

        passport_ids = upsert_passports(connection, passports, registry_rows)
        upsert_registry(connection, registry_rows, base_cases, passport_ids)
        upsert_skill_rubrics(connection, rubric_rows)
        upsert_role_targets(connection, role_target_rows)
        recompute_case_quality_checks(connection)
        connection.commit()
        final_count_row = connection.execute("SELECT COUNT(*) AS count FROM cases_registry").fetchone()
        final_count = final_count_row["count"]
        print("FINAL_CASES_REGISTRY_COUNT", final_count)


if __name__ == "__main__":
    main()
