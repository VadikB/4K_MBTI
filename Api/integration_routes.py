from __future__ import annotations

import secrets
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from Api.auth_service import normalize_email
from Api.config import settings
from Api.database import get_connection
from Api.integration_identity_service import resolve_or_provision_participant
from Api.assessment_role_profiles import load_published_role_profile
from Api import educational_contexts
from Api.product_cycle_preparation_queue import product_cycle_preparation_queue


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


class PublishedRoleProfileResponse(BaseModel):
    id: int
    code: str
    version: int
    methodology_version: str
    checksum: str


class EducationalContextPrepareRequest(BaseModel):
    snapshot: dict
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class EducationalContextPrepareResponse(BaseModel):
    operation_id: str
    status: Literal["awaiting_admission", "preparing", "prepared"]
    organization_id: int
    assignment_id: int
    assignment_ref: str
    reasons: list[str]
    cycle_id: str | None


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


@router.get(
    "/role-profile-versions/{version_id}",
    response_model=PublishedRoleProfileResponse,
)
def get_published_role_profile(
    version_id: int,
    authorization: str | None = Header(default=None),
) -> PublishedRoleProfileResponse:
    _require_integration_token(authorization)
    try:
        with get_connection() as connection:
            role = load_published_role_profile(connection, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Опубликованная версия роли не найдена.") from exc
    return PublishedRoleProfileResponse(
        id=int(role["id"]),
        code=str(role["code"]),
        version=int(role["version"]),
        methodology_version=str(role["definition"]["methodology_version"]),
        checksum=str(role["checksum"]),
    )


@router.post(
    "/educational-contexts/prepare",
    response_model=EducationalContextPrepareResponse,
)
def prepare_educational_context(
    payload: EducationalContextPrepareRequest,
    authorization: str | None = Header(default=None),
) -> EducationalContextPrepareResponse:
    _require_integration_token(authorization)
    try:
        with get_connection() as connection:
            result = educational_contexts.prepare(
                connection,
                snapshot=payload.snapshot,
                snapshot_checksum=payload.checksum,
            )
            connection.commit()
        preparation_request = result.pop("preparation_request", None)
        recipient_user_id = result.pop("recipient_user_id", None)
        context_id = result.pop("context_id", None)
        if preparation_request is not None:
            operation = product_cycle_preparation_queue.enqueue(
                operation_id=str(preparation_request["idempotency_key"]),
                user_id=int(recipient_user_id),
                request=preparation_request,
            )
            cycle_id = None
            if operation.get("status") == "completed":
                cycle_id = str(
                    (((operation.get("result_json") or {}).get("plan") or {}).get("cycle_id"))
                    or ""
                ) or None
            operation_reasons = (
                ["CYCLE_PREPARATION_FAILED"] if operation.get("status") == "failed" else []
            )
            with get_connection() as connection:
                educational_contexts.record_preparation(
                    connection,
                    context_id=int(context_id),
                    operation_id=str(operation["operation_id"]),
                    status=str(operation["status"]),
                    cycle_id=cycle_id,
                    reasons=operation_reasons,
                )
                connection.commit()
            result["operation_id"] = str(operation["operation_id"])
            result["status"] = (
                "prepared" if cycle_id
                else "awaiting_admission" if operation.get("status") == "failed"
                else "preparing"
            )
            result["reasons"] = operation_reasons
            result["cycle_id"] = cycle_id
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EducationalContextPrepareResponse(**result)
