from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from Api.database import get_connection


TABLES = (
    "roles",
    "competencies_4k",
    "skills",
    "competency_skills",
    "competency_skill_criteria",
    "role_skills",
    "role_skill_targets",
    "case_response_artifacts",
    "case_type_passports",
    "case_personalization_fields",
    "case_type_personalization_fields",
    "case_required_response_blocks",
    "case_type_red_flags",
    "case_type_skill_evidence",
    "case_type_difficulty_modifiers",
    "case_text_build_instructions",
    "cases_registry",
    "case_registry_roles",
    "case_registry_skills",
    "case_texts",
    "case_text_personalization_values",
    "assessment_agent_prompt_profiles",
    "assessment_agent_prompt_rules",
    "interviewer_agent_prompts",
)

PERSONAL_COLUMNS = {"author_name", "reviewer_name"}


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported value: {type(value).__name__}")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def export_bundle() -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    with get_connection() as connection:
        for table in TABLES:
            columns = connection.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            ).fetchall()
            column_names = [str(row["column_name"]) for row in columns]
            json_columns = [str(row["column_name"]) for row in columns if row["data_type"] in {"json", "jsonb"}]
            if not column_names:
                raise RuntimeError(f"Required methodology table is missing: {table}")
            primary_key_rows = connection.execute(
                """
                SELECT attribute.attname AS column_name
                FROM pg_index index_data
                JOIN pg_attribute attribute
                  ON attribute.attrelid = index_data.indrelid
                 AND attribute.attnum = ANY(index_data.indkey)
                WHERE index_data.indrelid = %s::regclass
                  AND index_data.indisprimary
                ORDER BY array_position(index_data.indkey, attribute.attnum)
                """,
                (table,),
            ).fetchall()
            primary_key = [str(row["column_name"]) for row in primary_key_rows]
            if not primary_key:
                raise RuntimeError(f"Methodology table has no primary key: {table}")
            rows = [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY {", ".join(primary_key)}').fetchall()]
            for row in rows:
                for column in PERSONAL_COLUMNS & row.keys():
                    row[column] = None
            tables.append(
                {"name": table, "columns": column_names, "json_columns": json_columns, "primary_key": primary_key, "rows": rows}
            )

    payload = {"schema_version": 1, "methodology_code": "competencies_4k", "methodology_version": "1.0", "tables": tables}
    return {**payload, "checksum": hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Экспорт неперсонального пакета методологии 1.0.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--acknowledge-production-read", action="store_true")
    args = parser.parse_args()
    if not args.acknowledge_production_read:
        parser.error("Для чтения production укажите --acknowledge-production-read")
    bundle = export_bundle()
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
    print(f"Exported {sum(len(table['rows']) for table in bundle['tables'])} rows; checksum={bundle['checksum']}")


if __name__ == "__main__":
    main()
