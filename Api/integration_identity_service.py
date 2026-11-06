from __future__ import annotations

from dataclasses import dataclass

from Api.auth_service import normalize_email


@dataclass(frozen=True, slots=True)
class ParticipantIdentityResolution:
    agent4k_user_id: int
    created: bool


def resolve_or_provision_participant(
    connection,
    *,
    email: str,
    display_name: str,
) -> ParticipantIdentityResolution:
    normalized_email = normalize_email(email)
    normalized_name = str(display_name or "").strip()
    if not normalized_name or len(normalized_name) > 255:
        raise ValueError("Имя участника должно содержать от 1 до 255 символов.")

    existing = connection.execute(
        "SELECT id FROM users WHERE LOWER(email) = %s ORDER BY id LIMIT 1",
        (normalized_email,),
    ).fetchone()
    if existing is not None:
        return ParticipantIdentityResolution(
            agent4k_user_id=int(existing["id"]),
            created=False,
        )

    created = connection.execute(
        """
        INSERT INTO users (full_name, email, role_id, job_description, phone, company_industry)
        VALUES (%s, %s, NULL, NULL, NULL, NULL)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        """,
        (normalized_name, normalized_email),
    ).fetchone()
    if created is not None:
        return ParticipantIdentityResolution(
            agent4k_user_id=int(created["id"]),
            created=True,
        )

    concurrent = connection.execute(
        "SELECT id FROM users WHERE LOWER(email) = %s ORDER BY id LIMIT 1",
        (normalized_email,),
    ).fetchone()
    if concurrent is None:
        raise RuntimeError("Не удалось получить созданного пользователя 4К.")
    return ParticipantIdentityResolution(
        agent4k_user_id=int(concurrent["id"]),
        created=False,
    )
