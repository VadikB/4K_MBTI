from __future__ import annotations

import hashlib
from dataclasses import dataclass

from Api.config import settings


ORG_ADMIN_ROLE = "admin"
ORG_MEMBER_ROLE = "member"
EXPLICIT_MEMBER_ADMISSION_SOURCES = frozenset({"admin_add", "csv_import", "superadmin_transfer"})


@dataclass(frozen=True)
class AdminScope:
    is_superadmin: bool = False
    organization_ids: tuple[int, ...] = ()

    @property
    def can_admin(self) -> bool:
        return self.is_superadmin or bool(self.organization_ids)


def normalize_email_for_access(value: str | None) -> str:
    return str(value or "").strip().lower()


def email_domain(value: str | None) -> str:
    email = normalize_email_for_access(value)
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].strip().lower()


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _parse_code_map(value: str | None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for group in str(value or "").split(";"):
        raw_group = group.strip()
        if not raw_group or ":" not in raw_group:
            continue
        raw_code, raw_values = raw_group.split(":", 1)
        code = normalize_org_code(raw_code)
        values = _split_csv(raw_values)
        if code and values:
            result.setdefault(code, []).extend(values)
    return result


def _parse_name_map(value: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for group in str(value or "").split(";"):
        raw_group = group.strip()
        if not raw_group or ":" not in raw_group:
            continue
        raw_code, raw_name = raw_group.split(":", 1)
        code = normalize_org_code(raw_code)
        name = raw_name.strip()
        if code and name:
            result[code] = name
    return result


def normalize_org_code(value: str | None) -> str:
    code = str(value or "").strip().lower()
    normalized = []
    for symbol in code:
        if symbol.isalnum() or symbol in {"_", "-"}:
            normalized.append(symbol)
        elif symbol.isspace():
            normalized.append("-")
    return "".join(normalized).strip("-_")


def configured_superadmin_emails() -> set[str]:
    return {normalize_email_for_access(item) for item in _split_csv(settings.superadmin_emails_raw)}


def configured_access_suppressed(connection, *, email: str, access_kind: str,
                                 organization_code: str = "") -> bool:
    return connection.execute(
        """SELECT 1 FROM configured_access_suppressions
           WHERE LOWER(email)=%s AND access_kind=%s AND organization_code=%s LIMIT 1""",
        (normalize_email_for_access(email), access_kind, normalize_org_code(organization_code)),
    ).fetchone() is not None


def configured_org_admin_emails() -> dict[str, list[str]]:
    return {
        code: [normalize_email_for_access(email) for email in emails if normalize_email_for_access(email)]
        for code, emails in _parse_code_map(settings.org_admin_emails_raw).items()
    }


def configured_org_domains() -> dict[str, list[str]]:
    return {
        code: [domain.lower().lstrip("@") for domain in domains if domain.lower().lstrip("@")]
        for code, domains in _parse_code_map(settings.org_member_domains_raw).items()
    }


def configured_org_names() -> dict[str, str]:
    return _parse_name_map(settings.org_names_raw)


def ensure_configured_organizations(connection) -> None:
    org_names = configured_org_names()
    admin_map = configured_org_admin_emails()
    domain_map = configured_org_domains()
    org_codes = set(org_names)
    org_codes.update(admin_map)
    org_codes.update(domain_map)

    for org_code in sorted(org_codes):
        code_sha256 = hashlib.sha256(org_code.encode("utf-8")).hexdigest()
        deleted = connection.execute(
            "SELECT 1 FROM organization_deletion_tombstones WHERE code_sha256=%s",
            (code_sha256,),
        ).fetchall()
        if deleted:
            continue
        org_name = org_names.get(org_code) or org_code.replace("-", " ").replace("_", " ").title()
        connection.execute(
            """
            INSERT INTO organizations (code, name)
            VALUES (%s, %s)
            ON CONFLICT (code) DO NOTHING
            """,
            (org_code, org_name),
        )

    for org_code, domains in domain_map.items():
        org_row = connection.execute(
            "SELECT id FROM organizations WHERE code = %s AND is_active = TRUE LIMIT 1",
            (org_code,),
        ).fetchone()
        if org_row is None:
            continue
        org_id = int(org_row["id"])
        for domain in domains:
            connection.execute(
                """
                INSERT INTO organization_email_domains (organization_id, domain)
                VALUES (%s, %s)
                ON CONFLICT (organization_id, domain) DO NOTHING
                """,
                (org_id, domain),
            )


def assign_user_organization_from_email(connection, *, user_id: int, email: str | None) -> None:
    normalized_email = normalize_email_for_access(email)
    if not normalized_email:
        return

    ensure_configured_organizations(connection)

    admin_map = configured_org_admin_emails()
    for org_code, emails in admin_map.items():
        if normalized_email not in emails:
            continue
        if configured_access_suppressed(
            connection, email=normalized_email, access_kind="organization_admin",
            organization_code=org_code,
        ):
            return
        org_row = connection.execute(
            "SELECT id FROM organizations WHERE code = %s AND is_active = TRUE LIMIT 1",
            (org_code,),
        ).fetchone()
        if org_row is None:
            continue
        suppressed = connection.execute(
            """
            SELECT 1 FROM configured_organization_membership_suppressions
            WHERE user_id = %s AND organization_id = %s
            LIMIT 1
            """,
            (user_id, int(org_row["id"])),
        ).fetchone()
        if suppressed:
            return
        _upsert_membership(
            connection,
            organization_id=int(org_row["id"]),
            user_id=user_id,
            role=ORG_ADMIN_ROLE,
            admission_source="configured_admin",
        )
        return


def email_has_organization_access(connection, *, email: str | None) -> bool:
    normalized_email = normalize_email_for_access(email)
    if not normalized_email:
        return False
    if normalized_email in configured_superadmin_emails() and not configured_access_suppressed(
        connection, email=normalized_email, access_kind="superadmin"
    ):
        return True

    ensure_configured_organizations(connection)

    for org_code, emails in configured_org_admin_emails().items():
        if normalized_email not in emails:
            continue
        configured_access = connection.execute(
            """
            SELECT 1
            FROM organizations organization
            LEFT JOIN users user_row ON LOWER(user_row.email) = %s
            LEFT JOIN configured_organization_membership_suppressions suppression
              ON suppression.user_id = user_row.id
             AND suppression.organization_id = organization.id
            WHERE organization.code = %s
              AND organization.is_active = TRUE
              AND suppression.user_id IS NULL
            LIMIT 1
            """,
            (normalized_email, org_code),
        ).fetchone()
        if configured_access:
            return True

    membership_rows = connection.execute(
        """
        SELECT DISTINCT om.organization_id, om.role, om.admission_source
        FROM organization_memberships om
        JOIN organizations o ON o.id = om.organization_id
        JOIN users u ON u.id = om.user_id
        LEFT JOIN user_identities ui ON ui.user_id = u.id
        WHERE o.is_active = TRUE
          AND (
            LOWER(u.email) = %s
            OR LOWER(ui.email) = %s
          )
        """,
        (normalized_email, normalized_email),
    ).fetchall()
    if any(row["role"] == ORG_ADMIN_ROLE for row in membership_rows):
        return True
    member_rows = [
        row for row in membership_rows
        if row["role"] == ORG_MEMBER_ROLE and row["admission_source"] in EXPLICIT_MEMBER_ADMISSION_SOURCES
    ]
    return len(member_rows) == 1


def _upsert_membership(
    connection,
    *,
    organization_id: int,
    user_id: int,
    role: str,
    admission_source: str,
    admitted_by_user_id: int | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO organization_memberships (
            organization_id, user_id, role, admission_source, admitted_by_user_id, admitted_at
        )
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (organization_id, user_id) DO UPDATE
        SET role = CASE
                WHEN organization_memberships.role = 'admin' THEN organization_memberships.role
                ELSE EXCLUDED.role
            END,
            admission_source = EXCLUDED.admission_source,
            admitted_by_user_id = EXCLUDED.admitted_by_user_id,
            admitted_at = EXCLUDED.admitted_at,
            updated_at = NOW()
        """,
        (organization_id, user_id, role, admission_source, admitted_by_user_id),
    )


def get_admin_scope(connection, user) -> AdminScope:
    if user is None:
        return AdminScope()
    email = normalize_email_for_access(getattr(user, "email", None))
    if email and email in configured_superadmin_emails() and not configured_access_suppressed(
        connection, email=email, access_kind="superadmin"
    ):
        return AdminScope(is_superadmin=True)

    assign_user_organization_from_email(connection, user_id=int(user.id), email=email)
    rows = connection.execute(
        """
        SELECT membership.organization_id
        FROM organization_memberships membership
        JOIN organizations organization ON organization.id = membership.organization_id
        WHERE membership.user_id = %s
          AND membership.role = %s
          AND organization.is_active = TRUE
        ORDER BY membership.organization_id ASC
        """,
        (int(user.id), ORG_ADMIN_ROLE),
    ).fetchall()
    return AdminScope(organization_ids=tuple(int(row["organization_id"]) for row in rows))


def admin_scope_sql(scope: AdminScope, *, user_alias: str = "u") -> tuple[str, tuple]:
    if scope.is_superadmin:
        return "", ()
    if not scope.organization_ids:
        return " AND FALSE", ()
    return (
        f"""
        AND EXISTS (
            SELECT 1
            FROM organization_memberships report_org_scope
            WHERE report_org_scope.user_id = {user_alias}.id
              AND report_org_scope.organization_id = ANY(%s)
        )
        """,
        (list(scope.organization_ids),),
    )
