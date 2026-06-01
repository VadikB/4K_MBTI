from __future__ import annotations

import argparse
from dataclasses import dataclass

from Api.agent import interviewer_agent
from Api.database import ensure_core_schema, get_connection, recompute_case_quality_checks


@dataclass(slots=True)
class UpdateSummary:
    database_name: str
    current_schema: str
    users_total: int
    case_types_total: int
    prompts_total: int
    consent_documents_total: int
    backfilled_users: int = 0


def _load_summary() -> UpdateSummary:
    with get_connection() as connection:
        db_row = connection.execute(
            """
            SELECT
                current_database() AS database_name,
                current_schema() AS current_schema
            """
        ).fetchone()
        users_total = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        case_types_total = connection.execute("SELECT COUNT(*) AS total FROM case_type_passports").fetchone()["total"]
        prompts_total = connection.execute("SELECT COUNT(*) AS total FROM interviewer_agent_prompts").fetchone()["total"]
        consent_documents_total = connection.execute("SELECT COUNT(*) AS total FROM consent_documents").fetchone()["total"]
    return UpdateSummary(
        database_name=db_row["database_name"],
        current_schema=db_row["current_schema"],
        users_total=users_total,
        case_types_total=case_types_total,
        prompts_total=prompts_total,
        consent_documents_total=consent_documents_total,
    )


def _print_summary(summary: UpdateSummary, *, title: str) -> None:
    print(title)
    print(f"  database: {summary.database_name}")
    print(f"  schema: {summary.current_schema}")
    print(f"  users: {summary.users_total}")
    print(f"  case_type_passports: {summary.case_types_total}")
    print(f"  interviewer_agent_prompts: {summary.prompts_total}")
    print(f"  consent_documents: {summary.consent_documents_total}")
    if summary.backfilled_users:
        print(f"  backfilled_users: {summary.backfilled_users}")


def run_check() -> None:
    summary = _load_summary()
    _print_summary(summary, title="Database connection check passed.")


def run_apply(*, backfill_users: bool, recompute_case_quality: bool) -> None:
    print("Applying database updates...")
    ensure_core_schema()

    backfilled_users = 0
    if backfill_users:
        print("Running incomplete user profile backfill...")
        backfilled_users = interviewer_agent.backfill_incomplete_users()

    if recompute_case_quality:
        print("Recomputing case quality checks...")
        recompute_case_quality_checks()

    summary = _load_summary()
    summary.backfilled_users = backfilled_users
    _print_summary(summary, title="Database update completed successfully.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bring an already deployed Agent_4K PostgreSQL database to the current application schema.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify the connection and print a short database summary.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply schema updates via ensure_core_schema().",
    )
    parser.add_argument(
        "--backfill-users",
        action="store_true",
        help="Also backfill incomplete user profiles after schema updates.",
    )
    parser.add_argument(
        "--recompute-case-quality",
        action="store_true",
        help="Also recompute case quality checks after schema updates.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.check and not args.apply:
        parser.error("Choose one of: --check or --apply")

    if args.check and args.apply:
        parser.error("Use either --check or --apply, not both together")

    if args.check:
        run_check()
        return

    run_apply(
        backfill_users=args.backfill_users,
        recompute_case_quality=args.recompute_case_quality,
    )


if __name__ == "__main__":
    main()
