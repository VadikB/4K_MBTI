from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from Api.config import settings
from Api.database import get_connection
from Api.schemas import UserResponse
from Api.web_session_service import USER_SELECT_SQL


logger = logging.getLogger("agent4k.auth")

EMAIL_PROVIDER = "email_magic_link"


@dataclass(slots=True)
class MagicLinkRequestResult:
    email: str
    expires_at: datetime
    dev_magic_token: str | None = None


@dataclass(slots=True)
class MagicLinkVerificationResult:
    user: UserResponse
    is_new_user: bool
    email: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(value: str | None) -> str:
    email = str(value or "").strip().lower()
    if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Введите корректный email.")
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise ValueError("Введите корректный email.")
    return email


def _hash_magic_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_placeholder_full_name(email: str) -> str:
    local_part = str(email or "").split("@", 1)[0].strip()
    if not local_part:
        return "Новый пользователь"
    candidate = local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return candidate[:255] or "Новый пользователь"


class AuthService:
    def ensure_schema(self) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_identities (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    provider_subject TEXT,
                    email TEXT,
                    phone TEXT,
                    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
                    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                    verified_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_magic_links (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    client_ip TEXT,
                    user_agent TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_identities_user_id ON user_identities(user_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_identities_provider ON user_identities(provider)"
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_user_identities_provider_subject
                ON user_identities(provider, provider_subject)
                WHERE provider_subject IS NOT NULL
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_user_identities_email
                ON user_identities(LOWER(email))
                WHERE email IS NOT NULL
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_magic_links_email ON auth_magic_links(LOWER(email))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_magic_links_expires_at ON auth_magic_links(expires_at)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_magic_links_token_hash ON auth_magic_links(token_hash)"
            )
            connection.commit()

    def create_magic_link_request(
        self,
        *,
        email: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> MagicLinkRequestResult:
        self.ensure_schema()
        normalized_email = normalize_email(email)
        raw_token = secrets.token_urlsafe(24)
        token_hash = _hash_magic_token(raw_token)
        expires_at = _utc_now() + timedelta(minutes=max(settings.auth_magic_link_ttl_minutes, 5))

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO auth_magic_links (email, token_hash, expires_at, client_ip, user_agent)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (normalized_email, token_hash, expires_at, client_ip, user_agent),
            )
            connection.commit()

        logger.info("Magic link requested for %s", normalized_email)
        return MagicLinkRequestResult(
            email=normalized_email,
            expires_at=expires_at,
            dev_magic_token=raw_token if settings.auth_magic_link_dev_mode else None,
        )

    def verify_magic_link(self, *, token: str) -> MagicLinkVerificationResult:
        self.ensure_schema()
        cleaned_token = str(token or "").strip()
        if not cleaned_token:
            raise ValueError("Токен входа не найден.")

        token_hash = _hash_magic_token(cleaned_token)
        with get_connection() as connection:
            link_row = connection.execute(
                """
                SELECT id, email, expires_at, used_at
                FROM auth_magic_links
                WHERE token_hash = %s
                LIMIT 1
                """,
                (token_hash,),
            ).fetchone()
            if link_row is None:
                raise ValueError("Ссылка для входа недействительна.")
            if link_row["used_at"] is not None:
                raise ValueError("Эта ссылка уже была использована.")
            expires_at = link_row["expires_at"]
            if expires_at is None or expires_at < datetime.now():
                raise ValueError("Срок действия ссылки истек. Запросите новую ссылку.")

            normalized_email = normalize_email(link_row["email"])
            identity_row = connection.execute(
                """
                SELECT user_id
                FROM user_identities
                WHERE provider = %s
                  AND LOWER(email) = %s
                LIMIT 1
                """,
                (EMAIL_PROVIDER, normalized_email),
            ).fetchone()

            is_new_user = False
            if identity_row is not None:
                user_id = int(identity_row["user_id"])
            else:
                user_row = connection.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE LOWER(email) = %s
                    LIMIT 1
                    """,
                    (normalized_email,),
                ).fetchone()
                if user_row is None:
                    created_user = connection.execute(
                        """
                        INSERT INTO users (full_name, email, role_id, job_description, phone, company_industry)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (_build_placeholder_full_name(normalized_email), normalized_email, None, None, None, None),
                    ).fetchone()
                    user_id = int(created_user["id"])
                    is_new_user = True
                else:
                    user_id = int(user_row["id"])

                connection.execute(
                    """
                    INSERT INTO user_identities (
                        user_id,
                        provider,
                        provider_subject,
                        email,
                        is_primary,
                        is_verified,
                        verified_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, TRUE, TRUE, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id, EMAIL_PROVIDER, normalized_email, normalized_email),
                )

            connection.execute(
                """
                UPDATE auth_magic_links
                SET used_at = NOW()
                WHERE id = %s
                """,
                (link_row["id"],),
            )

            user_row = connection.execute(
                USER_SELECT_SQL
                + """
                WHERE u.id = %s
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            connection.commit()

        if user_row is None:
            raise ValueError("Пользователь не найден после подтверждения входа.")
        logger.info("Magic link verified for %s", normalized_email)
        return MagicLinkVerificationResult(
            user=UserResponse(**dict(user_row)),
            is_new_user=is_new_user,
            email=normalized_email,
        )


auth_service = AuthService()
