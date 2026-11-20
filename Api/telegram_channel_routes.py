"""Opt-in, single-tenant Telegram assessment transport. No account endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from Api.config import settings
from Api.database import get_connection
from Api.integration_assessment_configuration_routes import _require_integration_token
from Api.assessment_role_profiles import load_published_role_profile
from Api import telegram_channel as channel, telegram_subjects as subjects

router = APIRouter(prefix="/integration/v1", tags=["telegram-channel"])


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubjectRequest(StrictRequest):
    source_system: str = Field(pattern=r"^telegram_student_bot$")
    external_subject_ref: UUID
    organization_ref: str


class SubjectResponse(BaseModel):
    external_subject_ref: UUID
    status: str


class ContextRequest(StrictRequest):
    snapshot: dict
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContextRef(StrictRequest):
    assignment_ref: str = Field(min_length=1, max_length=200)


class ProgramRequest(ContextRef):
    program_definition_id: int = Field(gt=0)
    operation_id: str = Field(min_length=1, max_length=200)


class ProjectContextTerms(StrictRequest):
    context_type: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=2000)
    results_usage: str = Field(min_length=1, max_length=2000)
    case_reality_level: str = Field(min_length=1, max_length=2000)
    name_usage_rules: str = Field(min_length=1, max_length=2000)


class ProjectContextPreview(ContextRef):
    terms: ProjectContextTerms


class ProjectContextConfirmation(ContextRef):
    revision_id: int = Field(gt=0)
    preview_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActionRequest(StrictRequest):
    schema_version: int = Field(ge=1, le=1)
    action_id: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=0)
    input: dict


def authorize(authorization: str | None) -> None:
    _require_integration_token(authorization)
    if (
        not settings.tg_student_channel_enabled
        or settings.tg_student_organization_id <= 0
        or not settings.tg_student_allowed_subjects
        or not settings.tg_student_allowed_project_code
    ):
        raise HTTPException(503, detail="TELEGRAM_CHANNEL_DISABLED")


def require_subject(subject: str, organization_id: int) -> None:
    if (
        organization_id != settings.tg_student_organization_id
        or str(subject) not in settings.tg_student_allowed_subjects
    ):
        raise HTTPException(404, detail="EDUCATIONAL_ASSIGNMENT_NOT_FOUND")


def authorize_context(ref: str) -> dict:
    with get_connection() as c:
        try:
            row = channel.context(c, ref)
        except ValueError as exc:
            raise HTTPException(404, detail="EDUCATIONAL_ASSIGNMENT_NOT_FOUND") from exc
        require_subject(str(row["external_subject_ref"]), int(row["organization_id"]))
        if (row["snapshot_json"].get("project") or {}).get(
            "code"
        ) != settings.tg_student_allowed_project_code:
            raise HTTPException(404, detail="EDUCATIONAL_ASSIGNMENT_NOT_FOUND")
        return row


def error(exc: ValueError) -> HTTPException:
    code = str(exc)
    public = {
        "SUBJECT_ORGANIZATION_CONFLICT",
        "SUBJECT_ORGANIZATION_NOT_AVAILABLE",
        "SUBJECT_NOT_FOUND",
        "EDUCATIONAL_CONTEXT_SCHEMA_UNSUPPORTED",
        "EDUCATIONAL_CONTEXT_CONTACT_IDENTITY_FORBIDDEN",
        "EDUCATIONAL_CONTEXT_CHECKSUM_MISMATCH",
        "EDUCATIONAL_CONTEXT_ROLE_CHECKSUM_MISMATCH",
        "EDUCATIONAL_CONTEXT_CONFIGURATION_UNAVAILABLE",
        "EDUCATIONAL_CONTEXT_ASSIGNMENT_REF_CONFLICT",
        "EDUCATIONAL_PROGRAM_SCOPE_SELECTION_REQUIRED",
        "EDUCATIONAL_CONTEXT_PROGRAM_NOT_COMPATIBLE",
        "EDUCATIONAL_ASSIGNMENT_NOT_FOUND",
        "STALE_CHANNEL_REVISION",
        "ACTION_NOT_CURRENT",
        "IDEMPOTENCY_CONFLICT",
        "ACTION_INPUT_INVALID",
        "PROJECT_CONTEXT_PREVIEW_MISMATCH",
    }
    return HTTPException(
        409, detail=code if code in public else "CHANNEL_TEMPORARILY_UNAVAILABLE"
    )


@router.post("/subjects/resolve", response_model=SubjectResponse)
def resolve_subject(
    payload: SubjectRequest, authorization: str | None = Header(default=None)
):
    authorize(authorization)
    require_subject(
        str(payload.external_subject_ref), settings.tg_student_organization_id
    )
    if (
        payload.organization_ref
        != f"organization:{settings.tg_student_organization_id}"
    ):
        raise HTTPException(409, detail="SUBJECT_ORGANIZATION_CONFLICT")
    try:
        with get_connection() as c:
            result = subjects.resolve(
                c,
                external_subject_ref=str(payload.external_subject_ref),
                organization_id=settings.tg_student_organization_id,
            )
            c.commit()
            return result
    except ValueError as exc:
        raise error(exc) from exc


@router.get("/role-profile-versions/{version_id}")
def published_role(version_id: int, authorization: str | None = Header(default=None)):
    authorize(authorization)
    with get_connection() as c:
        try:
            role = load_published_role_profile(c, version_id)
        except ValueError as exc:
            raise HTTPException(404, detail="ROLE_PROFILE_NOT_AVAILABLE") from exc
    return {
        "id": role["id"],
        "code": role["code"],
        "version": role["version"],
        "methodology_version": role["definition"]["methodology_version"],
        "checksum": role["checksum"],
    }


@router.post("/educational-contexts/prepare")
def prepare_context(
    payload: ContextRequest, authorization: str | None = Header(default=None)
):
    authorize(authorization)
    subject = str(
        (payload.snapshot.get("participant") or {}).get("external_subject_ref") or ""
    )
    require_subject(subject, settings.tg_student_organization_id)
    if (payload.snapshot.get("project") or {}).get(
        "code"
    ) != settings.tg_student_allowed_project_code:
        raise HTTPException(404, detail="EDUCATIONAL_ASSIGNMENT_NOT_FOUND")
    try:
        with get_connection() as c:
            result = channel.prepare(
                c,
                snapshot=payload.snapshot,
                snapshot_checksum=payload.checksum,
                organization_id=settings.tg_student_organization_id,
            )
            c.commit()
        return channel.refresh(get_connection, result["assignment_ref"])
    except (ValueError, KeyError, TypeError) as exc:
        raise error(ValueError(str(exc))) from exc


@router.post("/educational-contexts/program-options")
def program_options(
    payload: ContextRef, authorization: str | None = Header(default=None)
):
    authorize(authorization)
    row = authorize_context(payload.assignment_ref)
    with get_connection() as c:
        return channel.program_options(c, row)


@router.post("/educational-contexts/connect-program")
def connect_program(
    payload: ProgramRequest, authorization: str | None = Header(default=None)
):
    authorize(authorization)
    authorize_context(payload.assignment_ref)
    try:
        with get_connection() as c:
            result = channel.connect_program(c, **payload.model_dump())
            c.commit()
            return result
    except ValueError as exc:
        raise error(exc) from exc


@router.get("/educational-assignments/{assignment_ref}/channel-state")
def channel_state(
    assignment_ref: str, authorization: str | None = Header(default=None)
):
    authorize(authorization)
    authorize_context(assignment_ref)
    try:
        with get_connection() as c:
            return channel.read_channel_state(c, assignment_ref=assignment_ref)
    except ValueError as exc:
        raise error(exc) from exc


@router.post("/educational-assignments/{assignment_ref}/channel-actions")
def channel_action(
    assignment_ref: str,
    payload: ActionRequest,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    authorize(authorization)
    authorize_context(assignment_ref)
    if not idempotency_key or len(idempotency_key) > 200:
        raise HTTPException(422, detail="ACTION_IDEMPOTENCY_KEY_REQUIRED")
    try:
        result = channel.apply_channel_action(
            get_connection,
            assignment_ref=assignment_ref,
            action_id=payload.action_id,
            expected_revision=payload.expected_revision,
            action_input=payload.input,
            idempotency_key=idempotency_key,
        )

        return result
    except ValueError as exc:
        raise error(exc) from exc


@router.post("/educational-contexts/project-context/preview")
def preview_project_context(
    payload: ProjectContextPreview, authorization: str | None = Header(default=None)
):
    authorize(authorization)
    authorize_context(payload.assignment_ref)
    try:
        with get_connection() as c:
            result = channel.preview_project_context(
                c,
                assignment_ref=payload.assignment_ref,
                terms=payload.terms.model_dump(),
            )
            c.commit()
            return result
    except (ValueError, KeyError) as exc:
        raise error(ValueError(str(exc))) from exc


@router.post("/educational-contexts/project-context/confirm")
def confirm_project_context(
    payload: ProjectContextConfirmation,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    authorize_context(payload.assignment_ref)
    try:
        with get_connection() as c:
            result = channel.confirm_project_context(c, **payload.model_dump())
            c.commit()
            return result
    except ValueError as exc:
        raise error(exc) from exc
