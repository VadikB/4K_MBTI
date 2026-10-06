from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib

from Api.org_access import EXPLICIT_MEMBER_ADMISSION_SOURCES, normalize_email_for_access


class OrganizationInvitationError(ValueError):
    pass


@dataclass(frozen=True)
class OrganizationInvitationContext:
    invitation_id: int
    organization_id: int
    organization_name: str
    invitation_intro: str | None
    expires_at: datetime


def hash_invitation_token(token: str) -> str:
    return hashlib.sha256(str(token or "").strip().encode("utf-8")).hexdigest()


def resolve_invitation(connection, *, token: str) -> OrganizationInvitationContext:
    cleaned = str(token or "").strip()
    if not cleaned:
        raise OrganizationInvitationError("Приглашение недействительно.")
    row = connection.execute(
        """
        SELECT invitation.id, invitation.organization_id, invitation.expires_at,
               invitation.revoked_at, organization.name, organization.invitation_intro,
               organization.is_active
        FROM organization_invitations invitation
        JOIN organizations organization ON organization.id = invitation.organization_id
        WHERE invitation.token_hash = %s
        LIMIT 1
        """,
        (hash_invitation_token(cleaned),),
    ).fetchone()
    if row is None or not row["is_active"]:
        raise OrganizationInvitationError("Приглашение недействительно.")
    if row["revoked_at"] is not None:
        raise OrganizationInvitationError("Приглашение отозвано.")
    if row["expires_at"] is None or row["expires_at"] <= datetime.now():
        raise OrganizationInvitationError("Срок действия приглашения истёк.")
    return OrganizationInvitationContext(
        invitation_id=int(row["id"]),
        organization_id=int(row["organization_id"]),
        organization_name=str(row["name"]),
        invitation_intro=str(row["invitation_intro"] or "").strip() or None,
        expires_at=row["expires_at"],
    )


def resolve_invitation_by_id(connection, *, invitation_id: int) -> OrganizationInvitationContext:
    row = connection.execute(
        """
        SELECT invitation.id, invitation.organization_id, invitation.expires_at,
               invitation.revoked_at, organization.name, organization.invitation_intro,
               organization.is_active
        FROM organization_invitations invitation
        JOIN organizations organization ON organization.id = invitation.organization_id
        WHERE invitation.id = %s
        LIMIT 1
        """,
        (invitation_id,),
    ).fetchone()
    if row is None or not row["is_active"]:
        raise OrganizationInvitationError("Приглашение недействительно.")
    if row["revoked_at"] is not None:
        raise OrganizationInvitationError("Приглашение отозвано.")
    if row["expires_at"] is None or row["expires_at"] <= datetime.now():
        raise OrganizationInvitationError("Срок действия приглашения истёк.")
    return OrganizationInvitationContext(
        invitation_id=int(row["id"]),
        organization_id=int(row["organization_id"]),
        organization_name=str(row["name"]),
        invitation_intro=str(row["invitation_intro"] or "").strip() or None,
        expires_at=row["expires_at"],
    )


def ensure_email_admitted_to_invitation(connection, *, email: str, invitation: OrganizationInvitationContext) -> None:
    normalized = normalize_email_for_access(email)
    row = connection.execute(
        """
        SELECT DISTINCT membership.role, membership.admission_source
        FROM organization_memberships membership
        JOIN users user_account ON user_account.id = membership.user_id
        LEFT JOIN user_identities identity ON identity.user_id = user_account.id
        WHERE membership.organization_id = %s
          AND (
            LOWER(user_account.email) = %s
            OR LOWER(identity.email) = %s
          )
        """,
        (invitation.organization_id, normalized, normalized),
    ).fetchall()
    admitted = any(
        item["role"] == "admin"
        or (item["role"] == "member" and item["admission_source"] in EXPLICIT_MEMBER_ADMISSION_SOURCES)
        for item in row
    )
    if not admitted:
        raise OrganizationInvitationError(
            "Этот email не добавлен в список участников выбранной организации."
        )


def public_context(invitation: OrganizationInvitationContext) -> dict:
    return {
        "organization_id": invitation.organization_id,
        "organization_name": invitation.organization_name,
        "invitation_intro": invitation.invitation_intro,
        "expires_at": invitation.expires_at,
    }
