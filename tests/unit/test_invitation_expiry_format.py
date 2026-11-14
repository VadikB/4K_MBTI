from datetime import datetime, timedelta, timezone

from Api.email_service import _utc_expiry_label
from Api.schemas import AdminOrganizationMemberItem, OrganizationInvitationPublicResponse, PersonalInvitationResultItem


def test_invitation_expiry_has_same_instant_in_api_and_mail() -> None:
    utc_expiry = datetime(2026, 11, 14, 12, 30)
    moscow_expiry = utc_expiry.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=3)))
    item = PersonalInvitationResultItem(email="person@example.test", status="accepted", expires_at=utc_expiry)
    public = OrganizationInvitationPublicResponse(organization_id=3, organization_name="Synthetic",
        expires_at=moscow_expiry)
    member = AdminOrganizationMemberItem(user_id=19, email="person@example.test", invitation_expires_at=utc_expiry)

    assert item.model_dump(mode="json")["expires_at"] == "2026-11-14T12:30:00Z"
    assert public.model_dump(mode="json")["expires_at"] == "2026-11-14T12:30:00Z"
    assert member.model_dump(mode="json")["invitation_expires_at"] == "2026-11-14T12:30:00Z"
    assert _utc_expiry_label(utc_expiry) == _utc_expiry_label(moscow_expiry) == "14.11.2026 12:30 UTC"
