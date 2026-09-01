from __future__ import annotations

import argparse
import os

import psycopg
from psycopg.conninfo import conninfo_to_dict


REMOVED_PROMPT_PREFIX = "mbti.%"
REMOVED_TABLE = "session_mbti_refinements"
REMOVED_COLUMNS = {
    "user_sessions": ("mbti_summary_json",),
    "session_case_results": (
        "mbti_case_json",
        "mbti_followup_questions",
        "mbti_followup_answers",
    ),
}


def _relation_exists(connection: psycopg.Connection, relation_name: str) -> bool:
    row = connection.execute("SELECT to_regclass(%s) AS relation", (relation_name,)).fetchone()
    return bool(row and row[0])


def _column_exists(connection: psycopg.Connection, table_name: str, column_name: str) -> bool:
    row = connection.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
        )
        """,
        (table_name, column_name),
    ).fetchone()
    return bool(row and row[0])


def cleanup_removed_schema(connection: psycopg.Connection) -> dict[str, int]:
    result = {"prompts_deleted": 0, "tables_dropped": 0, "columns_dropped": 0}

    if _relation_exists(connection, "llm_prompts"):
        cursor = connection.execute(
            "DELETE FROM llm_prompts WHERE LOWER(prompt_code) LIKE %s",
            (REMOVED_PROMPT_PREFIX,),
        )
        result["prompts_deleted"] = int(cursor.rowcount or 0)

    if _relation_exists(connection, REMOVED_TABLE):
        connection.execute(f'DROP TABLE "{REMOVED_TABLE}" CASCADE')
        result["tables_dropped"] = 1

    for table_name, column_names in REMOVED_COLUMNS.items():
        if not _relation_exists(connection, table_name):
            continue
        for column_name in column_names:
            if not _column_exists(connection, table_name, column_name):
                continue
            connection.execute(f'ALTER TABLE "{table_name}" DROP COLUMN "{column_name}"')
            result["columns_dropped"] += 1

    return result


def verify_removed_schema(connection: psycopg.Connection) -> None:
    failures: list[str] = []
    if _relation_exists(connection, REMOVED_TABLE):
        failures.append(f"table {REMOVED_TABLE}")
    for table_name, column_names in REMOVED_COLUMNS.items():
        for column_name in column_names:
            if _column_exists(connection, table_name, column_name):
                failures.append(f"column {table_name}.{column_name}")
    if _relation_exists(connection, "llm_prompts"):
        row = connection.execute(
            "SELECT COUNT(*) FROM llm_prompts WHERE LOWER(prompt_code) LIKE %s",
            (REMOVED_PROMPT_PREFIX,),
        ).fetchone()
        if row and int(row[0] or 0):
            failures.append("removed prompt records")
    if failures:
        raise RuntimeError("Schema cleanup verification failed: " + ", ".join(failures))


def _database_name(database_url: str) -> str:
    return str(conninfo_to_dict(database_url).get("dbname") or "").strip().lower()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove retired personality-assessment storage.")
    parser.add_argument(
        "--confirm-destructive",
        action="store_true",
        help="Required for a database whose name does not contain test or pytest.",
    )
    parser.add_argument(
        "--backup-reference",
        help="Backup identifier required together with --confirm-destructive.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    database_url = str(os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise SystemExit("Set TEST_DATABASE_URL or DATABASE_URL.")

    database_name = _database_name(database_url)
    is_test_database = "test" in database_name or "pytest" in database_name
    if not is_test_database and not (args.confirm_destructive and str(args.backup_reference or "").strip()):
        raise SystemExit(
            "Refusing destructive cleanup outside a test database. "
            "Provide --confirm-destructive and --backup-reference after verifying a backup."
        )

    with psycopg.connect(database_url) as connection:
        result = cleanup_removed_schema(connection)
        verify_removed_schema(connection)
        connection.commit()

    print(
        "Cleanup completed: "
        f"prompts={result['prompts_deleted']}, "
        f"tables={result['tables_dropped']}, "
        f"columns={result['columns_dropped']}."
    )


if __name__ == "__main__":
    main()
