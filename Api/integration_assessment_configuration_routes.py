"""Service-only read interface for published assessment configurations."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from Api.config import settings
from Api.database import get_connection
from Api.integration_assessment_configurations import list_published_configurations


router = APIRouter(prefix="/integration/v1", tags=["integration"])


class PublishedAssessmentConfigurationResponse(BaseModel):
    id: int
    ref: str
    code: str
    name: str
    methodology_ref: str
    reference_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    is_default: bool


def _require_integration_token(authorization: str | None) -> None:
    configured = settings.tg_bot_integration_token
    if not configured or len(configured) < 32:
        raise HTTPException(status_code=503, detail="Интеграция Telegram-бота отключена.")
    scheme, separator, token = str(authorization or "").partition(" ")
    if not (
        separator == " "
        and scheme.lower() == "bearer"
        and token
        and secrets.compare_digest(token, configured)
    ):
        raise HTTPException(status_code=401, detail="Недействительный integration token.")


@router.get(
    "/assessment-configurations",
    response_model=list[PublishedAssessmentConfigurationResponse],
)
def get_published_assessment_configurations(
    authorization: str | None = Header(default=None),
) -> list[PublishedAssessmentConfigurationResponse]:
    _require_integration_token(authorization)
    with get_connection() as connection:
        options = list_published_configurations(connection)
    return [PublishedAssessmentConfigurationResponse(**item) for item in options]
