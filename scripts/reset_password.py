from __future__ import annotations

import argparse
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from Api.auth_service import auth_service, normalize_email
from Api.config import settings
from Api.database import get_connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset a superadmin password credential so the user can set a new password on next login.",
    )
    parser.add_argument("--email", required=True, help="Superadmin email from SUPERADMIN_EMAILS.")
    return parser.parse_args()


def configured_superadmin_emails() -> set[str]:
    emails: set[str] = set()
    for value in str(settings.superadmin_emails_raw or "").replace(";", ",").split(","):
        cleaned = str(value or "").strip()
        if cleaned:
            emails.add(normalize_email(cleaned))
    return emails


def main() -> int:
    args = parse_args()
    try:
        email = normalize_email(args.email)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if email not in configured_superadmin_emails():
        print(
            f"{email} is not listed in SUPERADMIN_EMAILS. Refusing to reset password.",
            file=sys.stderr,
        )
        return 3

    auth_service.ensure_schema()
    with get_connection() as connection:
        user_row = connection.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(email) = %s
            LIMIT 1
            """,
            (email,),
        ).fetchone()
        user_id = int(user_row["id"]) if user_row is not None else None
        credential_deleted = connection.execute(
            """
            DELETE FROM auth_password_credentials
            WHERE LOWER(email) = %s
            """,
            (email,),
        ).rowcount
        sessions_deleted = 0
        if user_id is not None:
            sessions_deleted = connection.execute(
                """
                DELETE FROM web_user_sessions
                WHERE user_id = %s
                """,
                (user_id,),
            ).rowcount
        connection.commit()

    print(
        "Password reset prepared for "
        f"{email}. credentials_deleted={credential_deleted}, sessions_deleted={sessions_deleted}."
    )
    print("On next login this superadmin will be asked to set and confirm a new password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
