from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from Api.database import get_connection


PROTECTED_REFERENCE_CHECKS = {
    "session_cases": None,
    "user_case_assignments": None,
    "user_skill_coverage": None,
    "user_sessions": "role_id IS NOT NULL",
    "user_role_profiles": "role_id IS NOT NULL",
    "session_skills": None,
    "session_skill_assessments": None,
    "session_case_skills": None,
    "session_case_skill_analysis": None,
}

DELETE_ORDER = (
    "assessment_agent_prompt_rules", "assessment_agent_prompt_profiles", "interviewer_agent_prompts",
    "case_text_personalization_values", "case_texts", "case_registry_roles", "case_registry_skills",
    "case_quality_checks", "case_methodology_change_log", "prompt_lab_case_runs", "cases_registry",
    "case_type_skill_evidence", "case_type_red_flags", "case_required_response_blocks",
    "case_type_difficulty_modifiers", "case_type_personalization_fields", "case_type_domain_situations",
    "case_user_text_templates", "case_type_passports", "case_personalization_fields",
    "case_response_artifacts", "case_text_build_instructions", "role_skill_targets", "role_skills",
    "competency_skill_criteria", "competency_skills", "skills", "competencies_4k", "roles",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _verify(bundle: dict[str, Any]) -> None:
    checksum = str(bundle.get("checksum") or "")
    payload = {key: value for key, value in bundle.items() if key != "checksum"}
    actual = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    if checksum != actual:
        raise RuntimeError("Methodology bundle checksum mismatch.")
    if bundle.get("methodology_code") != "competencies_4k" or bundle.get("methodology_version") != "1.0":
        raise RuntimeError("Only the competencies_4k methodology 1.0 bundle is supported.")


def import_bundle(bundle: dict[str, Any], *, apply: bool, replace_existing: bool = False) -> None:
    _verify(bundle)
    with get_connection() as connection:
        database_name = str(connection.execute("SELECT current_database() AS name").fetchone()["name"])
        if "test" not in database_name.lower() and "pytest" not in database_name.lower():
            raise RuntimeError("Import is allowed only into a database whose name contains test or pytest.")
        print(f"Target database accepted: {database_name}")
        if not apply:
            print("Bundle verified; no changes applied.")
            return
        if replace_existing:
            for table, predicate in PROTECTED_REFERENCE_CHECKS.items():
                where_clause = f" WHERE {predicate}" if predicate else ""
                count = connection.execute(sql.SQL("SELECT COUNT(*) AS count FROM {}{}").format(
                    sql.Identifier(table), sql.SQL(where_clause)
                )).fetchone()["count"]
                if count:
                    raise RuntimeError(f"Refusing replacement: protected table {table} contains {count} dependent rows.")
            for table in DELETE_ORDER:
                connection.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))
            print("Existing non-personal methodology rows removed inside transaction.")
        for table in bundle["tables"]:
            name = str(table["name"])
            columns = [str(value) for value in table["columns"]]
            primary_key = [str(value) for value in table["primary_key"]]
            json_columns = {str(value) for value in table.get("json_columns") or []}
            actual_columns = {
                str(row["column_name"])
                for row in connection.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
                    (name,),
                ).fetchall()
            }
            if not set(columns).issubset(actual_columns):
                raise RuntimeError(f"Target table {name} does not match bundle schema.")
            update_columns = [column for column in columns if column not in primary_key]
            statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}").format(
                sql.Identifier(name),
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                sql.SQL(", ").join(map(sql.Identifier, primary_key)),
                sql.SQL(", ").join(
                    sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
                    for column in update_columns
                ),
            )
            for row in table["rows"]:
                values = tuple(
                    Jsonb(row.get(column)) if column in json_columns and row.get(column) is not None else row.get(column)
                    for column in columns
                )
                connection.execute(statement, values)
            if "id" in primary_key:
                connection.execute(
                    sql.SQL("SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {}").format(
                        sql.Identifier(name)
                    ),
                    (name,),
                )
            print(f"Imported {name}: {len(table['rows'])}")
        connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка и импорт пакета методологии 1.0 в test-БД.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args()
    import_bundle(
        json.loads(args.input.read_text(encoding="utf-8")),
        apply=args.apply,
        replace_existing=args.replace_existing,
    )


if __name__ == "__main__":
    main()
