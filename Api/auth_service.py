from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from Api.config import settings
from Api.database import get_connection
from Api.email_service import send_magic_link_email
from Api.org_access import assign_user_organization_from_email, ensure_configured_organizations
from Api.schemas import UserResponse
from Api.web_session_service import USER_SELECT_SQL


logger = logging.getLogger("agent4k.auth")

EMAIL_PROVIDER = "email_magic_link"
PASSWORD_HASH_ITERATIONS = 210_000


class AuthRateLimitError(ValueError):
    pass


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


@dataclass(slots=True)
class PasswordLoginResult:
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


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    password_value = str(password or "")
    if not password_value:
        raise ValueError("Введите пароль.")
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_value.encode("utf-8"),
        salt_value.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return salt_value, digest


def _verify_password(password: str, *, salt: str | None, password_hash: str | None) -> bool:
    if not salt or not password_hash:
        return False
    _, candidate_hash = _hash_password(password, salt=salt)
    return secrets.compare_digest(candidate_hash, str(password_hash))


def validate_password_strength(password: str, *, password_confirm: str | None = None) -> None:
    password_value = str(password or "")
    if password_confirm is not None and password_value != str(password_confirm or ""):
        raise ValueError("Пароли не совпадают.")
    if len(password_value) < 10:
        raise ValueError("Пароль должен содержать минимум 10 символов.")
    if not any(symbol.islower() for symbol in password_value):
        raise ValueError("Пароль должен содержать хотя бы одну строчную букву.")
    if not any(symbol.isupper() for symbol in password_value):
        raise ValueError("Пароль должен содержать хотя бы одну заглавную букву.")
    if not any(symbol.isdigit() for symbol in password_value):
        raise ValueError("Пароль должен содержать хотя бы одну цифру.")


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
                """
                CREATE TABLE IF NOT EXISTS auth_password_credentials (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_login_at TIMESTAMP
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
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_password_credentials_email
                ON auth_password_credentials(LOWER(email))
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_password_credentials_user_id ON auth_password_credentials(user_id)"
            )
            connection.commit()

    def _enforce_magic_link_rate_limit(
        self,
        connection,
        *,
        email: str,
        client_ip: str | None,
    ) -> None:
        if settings.auth_magic_link_dev_mode:
            return

        cooldown_seconds = max(int(settings.auth_magic_link_resend_cooldown_seconds or 0), 0)
        if cooldown_seconds:
            recent_row = connection.execute(
                """
                SELECT created_at
                FROM auth_magic_links
                WHERE LOWER(email) = %s
                  AND created_at > NOW() - (%s * INTERVAL '1 second')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (email, cooldown_seconds),
            ).fetchone()
            if recent_row is not None:
                raise AuthRateLimitError(
                    "Ссылка уже отправлена. Проверьте почту или запросите новую ссылку чуть позже."
                )

        email_hourly_limit = max(int(settings.auth_magic_link_email_hourly_limit or 0), 0)
        if email_hourly_limit:
            email_count_row = connection.execute(
                """
                SELECT COUNT(*) AS request_count
                FROM auth_magic_links
                WHERE LOWER(email) = %s
                  AND created_at > NOW() - INTERVAL '1 hour'
                """,
                (email,),
            ).fetchone()
            if int(email_count_row["request_count"] or 0) >= email_hourly_limit:
                raise AuthRateLimitError(
                    "Слишком много запросов на вход для этого email. Попробуйте позже."
                )

        ip_hourly_limit = max(int(settings.auth_magic_link_ip_hourly_limit or 0), 0)
        if client_ip and ip_hourly_limit:
            ip_count_row = connection.execute(
                """
                SELECT COUNT(*) AS request_count
                FROM auth_magic_links
                WHERE client_ip = %s
                  AND created_at > NOW() - INTERVAL '1 hour'
                """,
                (client_ip,),
            ).fetchone()
            if int(ip_count_row["request_count"] or 0) >= ip_hourly_limit:
                raise AuthRateLimitError("Слишком много запросов на вход. Попробуйте позже.")

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
            self._enforce_magic_link_rate_limit(
                connection,
                email=normalized_email,
                client_ip=client_ip,
            )
            connection.execute(
                """
                UPDATE auth_magic_links
                SET used_at = NOW()
                WHERE LOWER(email) = %s
                  AND used_at IS NULL
                """,
                (normalized_email,),
            )
            connection.execute(
                """
                INSERT INTO auth_magic_links (email, token_hash, expires_at, client_ip, user_agent)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (normalized_email, token_hash, expires_at, client_ip, user_agent),
            )
            connection.commit()

        login_url = settings.app_base_url.rstrip("/") + "/?token=" + quote(raw_token, safe="")
        if not settings.auth_magic_link_dev_mode:
            send_magic_link_email(
                email=normalized_email,
                login_url=login_url,
                expires_at=expires_at,
            )

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
                UPDATE users
                SET email = %s
                WHERE id = %s
                  AND (
                    email IS NULL
                    OR TRIM(email) = ''
                    OR LOWER(email) = %s
                    OR LOWER(email) LIKE '%%@auto.local'
                  )
                """,
                (normalized_email, user_id, normalized_email),
            )

            connection.execute(
                """
                UPDATE auth_magic_links
                SET used_at = NOW()
                WHERE id = %s
                """,
                (link_row["id"],),
            )
            ensure_configured_organizations(connection)
            assign_user_organization_from_email(connection, user_id=user_id, email=normalized_email)

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

    def _ensure_user_identity(
        self,
        connection,
        *,
        user_id: int,
        email: str,
        provider: str,
    ) -> None:
        identity_row = connection.execute(
            """
            SELECT id
            FROM user_identities
            WHERE LOWER(email) = %s
            LIMIT 1
            """,
            (email,),
        ).fetchone()
        if identity_row is not None:
            connection.execute(
                """
                UPDATE user_identities
                SET user_id = %s,
                    provider = %s,
                    provider_subject = %s,
                    is_primary = TRUE,
                    is_verified = TRUE,
                    verified_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (user_id, provider, email, int(identity_row["id"])),
            )
            return

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
            ON CONFLICT (provider, provider_subject) WHERE provider_subject IS NOT NULL DO UPDATE
            SET user_id = EXCLUDED.user_id,
                email = EXCLUDED.email,
                is_verified = TRUE,
                verified_at = NOW(),
                updated_at = NOW()
            """,
            (user_id, provider, email, email),
        )

    def _is_superadmin_email(self, email: str) -> bool:
        normalized_superadmin_emails = {
            normalize_email(value)
            for value in str(settings.superadmin_emails_raw or "").replace(";", ",").split(",")
            if str(value or "").strip()
        }
        return email in normalized_superadmin_emails

    def _find_or_create_superadmin_user(self, connection, *, email: str) -> tuple[int, bool]:
        if not self._is_superadmin_email(email):
            raise ValueError("Неверный email или пароль.")

        user_row = connection.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(email) = %s
            LIMIT 1
            """,
            (email,),
        ).fetchone()
        if user_row is not None:
            return int(user_row["id"]), False

        created_user = connection.execute(
            """
            INSERT INTO users (full_name, email, role_id, job_description, phone, company_industry)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            ("Суперадминистратор", email, None, None, None, None),
        ).fetchone()
        return int(created_user["id"]), True

    def get_password_auth_mode(self, *, email: str) -> str:
        self.ensure_schema()
        normalized_email = normalize_email(email)
        with get_connection() as connection:
            credential_row = connection.execute(
                """
                SELECT id
                FROM auth_password_credentials
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            ).fetchone()
            if credential_row is not None:
                return "password"

            user_row = connection.execute(
                """
                SELECT id
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            ).fetchone()
            if user_row is not None or self._is_superadmin_email(normalized_email):
                return "password_registration"
        raise ValueError("Пользователь с таким email не найден. Обратитесь к администратору организации.")

    def register_password(self, *, email: str, password: str, password_confirm: str) -> PasswordLoginResult:
        self.ensure_schema()
        normalized_email = normalize_email(email)
        validate_password_strength(password, password_confirm=password_confirm)

        with get_connection() as connection:
            credential_row = connection.execute(
                """
                SELECT id
                FROM auth_password_credentials
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            ).fetchone()
            if credential_row is not None:
                raise ValueError("Пароль для этого email уже задан. Войдите с паролем.")

            user_row = connection.execute(
                """
                SELECT id
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            ).fetchone()
            is_new_user = False
            if user_row is not None:
                user_id = int(user_row["id"])
            else:
                user_id, is_new_user = self._find_or_create_superadmin_user(
                    connection,
                    email=normalized_email,
                )

            salt, password_hash = _hash_password(password)
            connection.execute(
                """
                INSERT INTO auth_password_credentials (user_id, email, password_hash, password_salt, last_login_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (user_id, normalized_email, password_hash, salt),
            )
            self._ensure_user_identity(
                connection,
                user_id=user_id,
                email=normalized_email,
                provider=EMAIL_PROVIDER,
            )
            ensure_configured_organizations(connection)
            assign_user_organization_from_email(connection, user_id=user_id, email=normalized_email)
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
            raise ValueError("Пользователь не найден после регистрации пароля.")
        logger.info("Password registered for %s", normalized_email)
        return PasswordLoginResult(
            user=UserResponse(**dict(user_row)),
            is_new_user=is_new_user,
            email=normalized_email,
        )

    def verify_password_login(self, *, email: str, password: str) -> PasswordLoginResult:
        self.ensure_schema()
        normalized_email = normalize_email(email)
        cleaned_password = str(password or "")
        if not cleaned_password:
            raise ValueError("Введите пароль.")

        with get_connection() as connection:
            credential_row = connection.execute(
                """
                SELECT user_id, email, password_hash, password_salt
                FROM auth_password_credentials
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (normalized_email,),
            ).fetchone()

            is_new_user = False
            if credential_row is not None:
                if not _verify_password(
                    cleaned_password,
                    salt=credential_row["password_salt"],
                    password_hash=credential_row["password_hash"],
                ):
                    raise ValueError("Неверный email или пароль.")
                user_id = int(credential_row["user_id"])
            else:
                raise ValueError("Пароль еще не задан. Пройдите первичную регистрацию.")

            connection.execute(
                """
                UPDATE auth_password_credentials
                SET last_login_at = NOW()
                WHERE LOWER(email) = %s
                """,
                (normalized_email,),
            )
            self._ensure_user_identity(
                connection,
                user_id=user_id,
                email=normalized_email,
                provider=EMAIL_PROVIDER,
            )
            connection.execute(
                """
                UPDATE users
                SET email = %s
                WHERE id = %s
                  AND (
                    email IS NULL
                    OR TRIM(email) = ''
                    OR LOWER(email) = %s
                    OR LOWER(email) LIKE '%%@auto.local'
                  )
                """,
                (normalized_email, user_id, normalized_email),
            )
            ensure_configured_organizations(connection)
            assign_user_organization_from_email(connection, user_id=user_id, email=normalized_email)
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
            raise ValueError("Пользователь не найден после входа.")
        logger.info("Password login verified for %s", normalized_email)
        return PasswordLoginResult(
            user=UserResponse(**dict(user_row)),
            is_new_user=is_new_user,
            email=normalized_email,
        )


auth_service = AuthService()
