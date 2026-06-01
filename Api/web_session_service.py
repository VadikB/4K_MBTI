from __future__ import annotations

from secrets import token_urlsafe

from Api.database import get_connection
from Api.schemas import UserResponse


USER_SELECT_SQL = """
    SELECT
        u.id,
        u.full_name,
        u.email,
        u.created_at,
        u.role_id,
        u.job_description,
        p.raw_position,
        p.raw_duties,
        p.normalized_duties,
        p.role_selected,
        p.role_selected_code,
        p.role_confidence,
        p.role_rationale,
        p.role_consistency_status,
        p.role_consistency_comment,
        p.company_context,
        p.user_domain,
        p.user_artifacts,
        p.user_systems,
        p.user_success_metrics,
        p.data_quality_notes,
        p.domain_resolution_status,
        p.domain_confidence,
        p.profile_quality,
        u.active_profile_id,
        u.phone,
        u.company_industry
    FROM users u
    LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
"""


class WebSessionService:
    def ensure_schema(self) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS web_user_sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.commit()

    def create_session(self, user_id: int) -> str:
        self.ensure_schema()
        token = token_urlsafe(32)
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO web_user_sessions (token, user_id)
                VALUES (%s, %s)
                """,
                (token, user_id),
            )
            connection.commit()
        return token

    def touch_session(self, token: str) -> None:
        self.ensure_schema()
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE web_user_sessions
                SET updated_at = NOW()
                WHERE token = %s
                """,
                (token,),
            )
            connection.commit()

    def delete_session(self, token: str | None) -> None:
        if not token:
            return
        self.ensure_schema()
        with get_connection() as connection:
            connection.execute(
                """
                DELETE FROM web_user_sessions
                WHERE token = %s
                """,
                (token,),
            )
            connection.commit()

    def get_user_by_token(self, token: str | None) -> UserResponse | None:
        if not token:
            return None
        self.ensure_schema()
        with get_connection() as connection:
            row = connection.execute(
                USER_SELECT_SQL
                + """
                JOIN web_user_sessions ws ON ws.user_id = u.id
                WHERE ws.token = %s
                LIMIT 1
                """,
                (token,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE web_user_sessions
                SET updated_at = NOW()
                WHERE token = %s
                """,
                (token,),
            )
            connection.commit()
        return UserResponse(**dict(row))


web_session_service = WebSessionService()
