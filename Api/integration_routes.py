from __future__ import annotations

import secrets
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from Api.auth_service import normalize_email
from Api.config import settings
from Api.database import get_connection
from Api.integration_identity_service import resolve_or_provision_participant


router = APIRouter(prefix="/integration/v1", tags=["integration"])


class ParticipantIdentityRequest(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_request_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Введите имя участника.")
        return cleaned


class ParticipantIdentityResponse(BaseModel):
    agent4k_user_id: int
    status: Literal["existing", "provisioned"]


def _require_integration_token(authorization: str | None) -> None:
    configured = settings.tg_bot_integration_token
    if not configured:
        raise HTTPException(status_code=503, detail="Интеграция Telegram-бота отключена.")
    if len(configured) < 32:
        raise HTTPException(status_code=503, detail="Integration token настроен небезопасно.")
    scheme, separator, token = str(authorization or "").partition(" ")
    valid = (
        separator == " "
        and scheme.lower() == "bearer"
        and bool(token)
        and secrets.compare_digest(token, configured)
    )
    if not valid:
        raise HTTPException(status_code=401, detail="Недействительный integration token.")


@router.post("/participants/resolve", response_model=ParticipantIdentityResponse)
def resolve_participant_identity(
    payload: ParticipantIdentityRequest,
    authorization: str | None = Header(default=None),
) -> ParticipantIdentityResponse:
    _require_integration_token(authorization)
    with get_connection() as connection:
        resolved = resolve_or_provision_participant(
            connection,
            email=payload.email,
            display_name=payload.display_name,
        )
        connection.commit()
    return ParticipantIdentityResponse(
        agent4k_user_id=resolved.agent4k_user_id,
        status="provisioned" if resolved.created else "existing",
    )
