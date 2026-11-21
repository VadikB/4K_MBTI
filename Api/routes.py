from __future__ import annotations

import base64
import csv
from contextlib import contextmanager
import hashlib
import hmac
import io
import json
import logging
import re
import secrets
import time
import psycopg
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, Response as FastAPIResponse
from fastapi.responses import Response
from pydantic import BaseModel, Field

from Api import invitation_outcomes
from Api import assessment_assignment_operations
from Api.admin_assignment_projection import ADMIN_ASSIGNMENT_STAGES_SQL
from Api.invitation_outcomes import InvitationRefusal
from Api.app_version import get_app_version
from Api.auth_service import AuthAccessDeniedError, AuthRateLimitError, auth_service, normalize_email
from Api.config import settings
from Api.email_service import EmailDeliveryError, EmailDeliveryUncertainError, send_auth_action_email
from Api.assessment_service import assessment_service
from Api import m5_generation_lab
from Api import m5_catalog_integrity
from Api.m5_case_type_catalog import M5CaseTypeCatalogError
from Api import m5_addressed_scenario, m5_cycle_runtime, m5_scenario_runtime, m5_storage, m5_equivalent_generation
from Api import m7_cycle_planner
from Api.m7_planning_contracts import CreateCyclePlanRequest, NextSituationRequest, PresentSituationRequest
from Api import m7_route_replacement
from Api.m7_replacement_contracts import ReplaceRoutePositionRequest, GenerateEquivalentSituationRequest
from Api import m7_clarification
from Api.m7_clarification_contracts import CreateClarificationRequest,PresentClarificationRequest,ClarificationAnswerRequest,ClarificationOutcomeRequest
from Api import m7_completion
from Api import m7_return_integration
from Api.m7_completion_contracts import CompletionRequest,CycleControlRequest,AdditionalSessionRequest,BlockingWaitRequest,ReconcileC46Request,ReturnContinueRequest,ReturnHeartbeatRequest
from Api import m6_cycle_aggregation_repository
from Api.m6_cycle_aggregation_contracts import CreateAggregationRequest, CreateSubstantiveAggregationRequest
from Api.profile_access import require_unchanged_email
from Api import participant_profile
from Api import acquaintance
from Api import appeals
from Api import assessment_assignment_sources, assessment_programs
from Api.public_origin import build_public_link
from Api import questionnaire_sources
from Api import m8_results
from Api import m8_report_access
from Api import m8_report_corrections
from Api import m8_report_comparison
from Api.typst_pdf_renderer import TypstRenderError
from Api.m8_results_contracts import (CreateResultsRequest, CreateReportRequest,
    PrepareReportCorrectionRequest, PublishReportCorrectionRequest)
from Api import m10_product_flow, m10_orchestration
from Api.m10_contracts import (
    ProductCycleStartRequest, ProductCycleActionRequest, ProductNextRequest,
    ProductNextPreparationRequest, ProductNextPresentationRequest,
)
from scripts.build_m5_case_package import OUTPUT as M5_PACKAGE_DIR
from Api.assessment_role_profiles import (
    create_organization_role_profile_draft,
    get_selected_role_profile,
    list_available_role_profiles,
    publish_base_roles,
    select_role_profile_for_user,
)
from Api.assessment_preparation_queue import assessment_preparation_queue
from Api.product_cycle_preparation_queue import product_cycle_preparation_queue, public_operation
from Api import preparation_observation as preparation_observation
from Api.assessment_analysis_queue import assessment_analysis_queue
from Api.assessment_authoring_service import assessment_authoring_service, ENTITY_CONFIG
from Api.assessment_methodology_publication import publish_m2_qa_configuration
from Api.assessment_shadow_repository import assessment_shadow_repository
from Api.assessment_shadow_batch_service import assessment_shadow_batch_service
from Api.platform_access import require_platform_permission
from Api.agent import interviewer_agent
from Api.database import get_connection, get_level_percent_map, recompute_case_quality_checks
from Api.database import get_case_methodology_versions
from Api.progress_service import operation_progress_service
from Api.org_access import (
    AdminScope,
    LOCAL_SUPERADMIN_EMAIL,
    admin_scope_sql,
    assign_user_organization_from_email,
    configured_org_admin_emails,
    configured_superadmin_emails,
    ensure_configured_organizations,
    get_admin_scope,
    is_platform_protected_account,
    normalize_org_code,
)
from Api.organization_invitation_service import (
    OrganizationInvitationError,
    hash_invitation_token,
    public_context as invitation_public_context,
    resolve_invitation,
    resolve_invitation_by_id,
)
from scripts.purge_test_organization import (
    build_account_purge_plan, build_purge_plan, purge_account, purge_organization, purge_plan_fingerprint,
    require_account_plan_organization_scope,
)
from Api.deletion_ledger import append_intent, read_receipt, record_receipt
from Api.report_growth_logic import (
    WEAK_SIGNAL_RECOMMENDATIONS,
    build_ai_insight_copy,
    build_competency_growth_recommendation,
    build_interpretation_basis_items,
    build_response_pattern_text,
)
from Api.regression_tests import (
    cleanup_autotest_data,
    get_regression_status,
    run_full_regression,
    run_offline_regression,
    run_smoke_regression,
    run_technical_regression,
)
from Api.web_session_service import web_session_service
from Api.user_journey import (
    determine_cycle_next_action,
    evaluate_profile_state,
    get_or_create_onboarding_state,
    update_onboarding_state,
)

M3_ROLE_PACKAGE_DIR = Path(__file__).resolve().parents[1] / "assessment_definitions" / "role_profiles" / "competencies_4k" / "1.1"
from Api.schemas import (
    AdminDashboard,
    AdminMethodologyCaseDetailResponse,
    AdminMethodologyCaseUpdateRequest,
    AdminMethodologyBranchItem,
    AdminMethodologyChangeLogItem,
    AdminMethodologyChecklistItem,
    AdminMethodologyCaseItem,
    AdminMethodologyCaseQualityItem,
    AdminMethodologyCoverageRow,
    AdminMethodologyPassportItem,
    AdminMethodologyPersonalizationOption,
    AdminMethodologyPersonalizationValueItem,
    AdminMethodologySinglePointSkillItem,
    AdminMethodologySkillGapItem,
    AdminMethodologyRoleOption,
    AdminMethodologyResponse,
    AdminMethodologySkillOption,
    AdminMethodologySkillSignalItem,
    AdminShadowComparisonResponse,
    AdminShadowBatchRequest,
    AdminShadowBatchResponse,
    AdminMetricCard,
    AdminOrganizationImportResult,
    AdminOrganizationAdminRequest,
    AdminAccountPurgeRequest,
    AdminOrganizationCreateRequest,
    AdminOrganizationDomainRequest,
    AdminOrganizationItem,
    AdminOrganizationMemberRequest,
    AdminOrganizationTransferRequest,
    AdminOrganizationMembersImportRequest,
    AdminOrganizationPurgeRequest,
    AdminOrganizationProgramConnectionRequest,
    AdminOrganizationsResponse,
    AdminOrganizationUpdateRequest,
    QuestionnairePreviewRequest,
    QuestionnaireConfirmRequest,
    AdminRegressionTestRunResponse,
    AdminRegressionTestStatusResponse,
    AppVersionResponse,
    AuthEmailRequest,
    AuthEmailRequestResponse,
    AuthEmailVerifyRequest,
    AuthActionResponse,
    AuthPasswordForgotRequest,
    AuthPasswordLoginRequest,
    AuthPasswordRegisterRequest,
    AuthPasswordResetRequest,
    OrganizationInvitationAdminResponse,
    OrganizationInvitationCreateRequest,
    OrganizationInvitationPublicResponse,
    PersonalInvitationBatchResponse,
    PersonalInvitationRequest,
    PersonalInvitationResultItem,
    AssessmentAssignmentRequest,
    AssessmentAssignmentResultItem,
    AssessmentAssignmentBatchResponse,
    AssessmentAssignmentCancelRequest,
    AssessmentAssignmentCancelResponse,
    PromptLabCaseOption,
    PromptLabCaseRunRequest,
    PromptLabCaseRunResponse,
    PromptLabDialoguePreviewRequest,
    PromptLabDialoguePreviewResponse,
    PromptLabDialogueTurnRequest,
    PromptLabDialogueTurnResponse,
    M5PrepareSituationRequest,
    M5LabRuntimeRequest,
    M5QATurnRequest,
    M5TurnRequest,
    M5TransitionRequest,
    M5ModelCheckRequest,
    M5TechnicalC45Request,
    M5QAEvidenceRequest,
    PromptLabSystemCasePreviewResponse,
    PromptLabCaseRunSummary,
    PromptLabDashboard,
    PromptLabPromptCreateRequest,
    PromptLabPromptVersion,
    PromptLabUserOption,
    AgentMessageRequest,
    AgentProfileConfirmRequest,
    AgentReply,
    RoleProfileSelectionRequest,
    OrganizationRoleProfileDraftRequest,
    AssessmentClientEventRequest,
    AssessmentAnalysisStatusResponse,
    AssessmentMessageRequest,
    AssessmentMessageResponse,
    AssessmentPreparationEnqueueResponse,
    AssessmentPreparationBatchEnqueueResponse,
    AssessmentPreparationBatchParticipant,
    AssessmentPreparationBatchStatusResponse,
    AssessmentPreparationStatusResponse,
    AssessmentTimerControlRequest,
    AssessmentSessionLookupResponse,
    AssessmentCard,
    AssessmentReportInterpretationResponse,
    AssessmentReport,
    ParticipantAssessmentCard,
    AssessmentStartResponse,
    AvailableAssessment,
    CheckOrCreateUserRequest,
    CheckOrCreateUserResponse,
    SkillAssessmentResponse,
    UserDashboard,
    UserAssessmentHistoryItem,
    OperationProgressResponse,
    OperationProgressStep,
    SessionCaseStructuredAnalysisResponse,
    UserProfileUpdateRequest,
    UserProfileSummaryResponse,
    M8HistoryResponse,
    UserSessionBootstrapResponse,
    UserSessionRestoreResponse,
    JourneyAssessmentState,
    OnboardingStateResponse,
    OnboardingStateUpdateRequest,
    AcquaintanceAnswersRequest,
    AcquaintanceConsentRequest,
    AcquaintanceIssueRequest,
    ProfileStateResponse,
    UserJourneyStateResponse,
    UserResponse,
    AssessmentDefinitionCloneRequest,
    AssessmentDefinitionCreateRequest,
    AssessmentDefinitionTransitionRequest,
    AssessmentDefinitionUpdateRequest,
    AssessmentDefinitionVersionResponse,
    AssessmentConfigurationCreateRequest,
    AssessmentConfigurationPublishRequest,
    AssessmentConfigurationResponse,
    M5CatalogPlanRequest,
    M5CatalogPublishRequest,
    M10ProcessingRecoveryRequest,
    PlatformRoleAssignmentRequest,
)


router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger("agent4k.admin")


class InvitationDeliveryUncertainError(RuntimeError):
    """Провайдер мог принять письмо; автоматический повтор небезопасен."""


assessment_logger = logging.getLogger("agent4k.assessment")
SESSION_COOKIE_NAME = "agent4k_session_token"
ADMIN_ROLE_CODE = "admin"
ADMIN_ROLE_NAME = "Администратор"
ADMIN_FULL_NAME = "Администратор системы"
ADMIN_EMAIL = LOCAL_SUPERADMIN_EMAIL

@router.get("/version", response_model=AppVersionResponse, response_model_exclude_none=True)
def get_application_version() -> AppVersionResponse:
    return AppVersionResponse(version=get_app_version(), public_origin=(
        settings.public_app_origin if settings.app_origin_mode == "public" else None))
ADMIN_PERSONALIZATION_SOURCE_LABELS = {
    "static": "задано в шаблоне кейса",
    "from_user_profile": "из профиля пользователя",
    "hybrid": "смешанный источник",
}
ADMIN_PERSONALIZATION_FIELD_PATTERN = re.compile(r"[{}]")


def _normalize_admin_personalization_field_code(value: str | None) -> str:
    normalized = ADMIN_PERSONALIZATION_FIELD_PATTERN.sub("", str(value or "").strip()).strip().lower()
    return normalized


def _humanize_admin_personalization_field_label(code: str) -> str:
    normalized = _normalize_admin_personalization_field_code(code)
    if not normalized:
        return "Переменная"
    return normalized.replace("_", " ").strip().capitalize()


def _extract_admin_personalization_codes(*values: str | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        for match in re.findall(r"\{([^{}]+)\}", str(raw_value or "")):
            code = _normalize_admin_personalization_field_code(match)
            if code and code not in seen:
                seen.add(code)
                result.append(code)
    return result


def _normalize_admin_personalization_payload_items(items: list[AdminMethodologyPersonalizationValueItem] | None) -> list[tuple[str, str | None, str | None, bool]]:
    result: list[tuple[str, str | None, str | None, bool]] = []
    seen: set[str] = set()
    for raw_item in items or []:
        code = _normalize_admin_personalization_field_code(raw_item.field_code if raw_item else None)
        if not code or code in seen:
            continue
        seen.add(code)
        label = str(raw_item.field_label or "").strip() or None
        source_type = str(raw_item.source_type or "").strip() or None
        is_required = bool(raw_item.is_required)
        result.append((code, label, source_type, is_required))
    return result


def _build_admin_personalization_variable_string(codes: list[str]) -> str | None:
    unique_codes: list[str] = []
    seen: set[str] = set()
    for code in codes:
        normalized = _normalize_admin_personalization_field_code(code)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_codes.append(normalized)
    if not unique_codes:
        return None
    return ", ".join("{" + code + "}" for code in unique_codes)


def _normalize_phone_digits(value: str | None) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith(("7", "8")):
        return digits[-10:]
    return digits


def _normalize_methodology_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "ready":
        return "ready"
    if normalized in {"retired", "archived", "archive", "inactive"}:
        return "retired"
    return "draft"


def _parse_json_array_field(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _calculate_competency_insight_score(item: dict) -> int:
    return round(
        int(item["value"]) * 0.5
        + float(item.get("evidence_hit_rate", 0)) * 100 * 0.2
        + float(item.get("avg_block_coverage", 0)) * 0.15
        + float(item.get("avg_artifact_compliance", 0)) * 0.15
        - min(float(item.get("avg_red_flag_count", 0)) * 10, 40)
    )


def _select_strongest_competency(competency_average: list[dict]) -> tuple[dict | None, bool]:
    if not competency_average:
        return None, False
    ranked = sorted(
        competency_average,
        key=lambda item: (_calculate_competency_insight_score(item), int(item["value"])),
        reverse=True,
    )
    strongest = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    gap = _calculate_competency_insight_score(strongest) - _calculate_competency_insight_score(second) if second else 999
    is_confident = _calculate_competency_insight_score(strongest) >= 35 and gap >= 5
    return strongest, is_confident


def _build_report_interpretation_payload(skill_rows: list[dict], competency_average: list[dict]) -> dict:
    has_manifested_results = any(int(item.get("value", 0)) > 0 for item in competency_average)
    evidence_hit_rate = (
        sum(1 for row in skill_rows if _parse_json_array_field(row.get("found_evidence"))) / len(skill_rows)
        if skill_rows
        else 0
    )
    block_values = [float(row["block_coverage_percent"]) for row in skill_rows if row.get("block_coverage_percent") is not None]
    artifact_values = [float(row["artifact_compliance_percent"]) for row in skill_rows if row.get("artifact_compliance_percent") is not None]
    red_flag_avg = (
        sum(len(_parse_json_array_field(row.get("red_flags"))) for row in skill_rows) / len(skill_rows)
        if skill_rows
        else 0
    )
    has_interpretation_signal = (
        has_manifested_results
        and evidence_hit_rate >= 0.2
        and (sum(block_values) / len(block_values) if block_values else 0) >= 25
        and (sum(artifact_values) / len(artifact_values) if artifact_values else 0) >= 25
        and red_flag_avg <= 4
    )
    overall_metrics = {
        "evidence_hit_rate": evidence_hit_rate,
        "avg_block_coverage": (sum(block_values) / len(block_values) if block_values else 0),
        "avg_artifact_compliance": (sum(artifact_values) / len(artifact_values) if artifact_values else 0),
        "avg_red_flag_count": red_flag_avg,
    }
    response_pattern = build_response_pattern_text(
        overall_metrics,
        has_interpretation_signal=has_interpretation_signal,
    )
    basis_items = build_interpretation_basis_items(overall_metrics)
    strongest_item, has_confident_strongest = _select_strongest_competency(competency_average)
    insight_title, insight_text = build_ai_insight_copy(
        str(strongest_item["name"]) if strongest_item else None,
        strongest_item["value"] if strongest_item else None,
        has_manifested_results=has_manifested_results,
        has_interpretation_signal=has_interpretation_signal,
        has_confident_strongest=has_confident_strongest,
        response_pattern=response_pattern,
    )
    if has_interpretation_signal:
        weakest = sorted(competency_average, key=lambda item: int(item["value"]))[:2]
        growth_areas = [
            build_competency_growth_recommendation(str(item["name"]), item)
            for item in weakest
        ] or ["Зоны роста будут определены после появления оценок по сессии."]
    else:
        growth_areas = [*WEAK_SIGNAL_RECOMMENDATIONS]

    return {
        "insight_title": insight_title,
        "insight_text": insight_text,
        "growth_areas": growth_areas,
        "basis_items": basis_items,
        "has_interpretation_signal": has_interpretation_signal,
        "has_confident_strongest": has_confident_strongest,
        "response_pattern": response_pattern,
    }


def _is_meaningful_quote_candidate(text: str) -> bool:
    normalized = " ".join((text or "").split()).strip().lower()
    if not normalized:
        return False
    if normalized in {"нет", "none", "n/a", "na", "-", "—"}:
        return False
    if set(normalized.split()) == {"нет"}:
        return False
    return len(normalized) >= 12


def _normalize_found_evidence_items(value) -> list[str]:
    items = _parse_json_array_field(value)
    normalized: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append(text)
            continue
        if isinstance(item, dict):
            parts = [
                str(item.get("evidence_description") or "").strip(),
                str(item.get("expected_signal") or "").strip(),
                str(item.get("reason") or "").strip(),
            ]
            text = " — ".join(part for part in parts if part)
            if not text:
                block_code = str(item.get("related_response_block_code") or "").strip()
                if block_code:
                    text = f"Сигнал по блоку {block_code}"
            if text:
                normalized.append(text)
            continue
        text = str(item or "").strip()
        if text:
            normalized.append(text)
    return normalized

LOOKUP_USER_STEPS = [
    {"label": "Ищем профиль пользователя", "description": "Проверяем наличие пользователя по номеру телефона."},
    {"label": "Определяем сценарий входа", "description": "Понимаем, нужно создать профиль или открыть актуализацию."},
    {"label": "Подготавливаем следующий шаг", "description": "Формируем состояние агента и интерфейса."},
]

PROFILE_SAVE_STEPS = [
    {"label": "Очищаем и нормализуем данные", "description": "Структурируем текст обязанностей и нормализуем входные значения."},
    {"label": "Сохраняем выбранную роль", "description": "Фиксируем роль, которую пользователь выбрал из списка."},
    {"label": "Формируем расширенный профиль", "description": "Собираем рабочий контекст пользователя для дальнейшей персонализации."},
    {"label": "Подготавливаем следующий экран", "description": "Завершаем сценарий и обновляем состояние пользователя."},
]

ASSESSMENT_MESSAGE_STEPS = [
    {
        "label": "Фиксируем ответ",
        "description": "Сохраняем ответ и проверяем состояние текущего кейса.",
    },
    {
        "label": "Проверяем кейс",
        "description": "Оцениваем ответ и подготавливаем результат по текущему кейсу.",
    },
    {
        "label": "Уточняем сигналы",
        "description": "Фиксируем результат кейса и переходим к следующему этапу оценки.",
    },
    {
        "label": "Открываем следующий шаг",
        "description": "Показываем следующий кейс или завершаем всю assessment-сессию.",
    },
]

ASSESSMENT_START_STEPS = [
    {"label": "Проверяем профиль оценки", "description": "Уточняем роль пользователя и состояние активной assessment-сессии."},
    {"label": "Подбираем релевантные кейсы", "description": "При необходимости выбираем набор кейсов, покрывающий нужные навыки."},
    {"label": "Персонализируем материалы", "description": "При необходимости подставляем рабочий контекст пользователя в шаблоны кейсов."},
    {"label": "Генерируем промты интервью", "description": "При необходимости создаем системные промты для ведения диалога по кейсам."},
    {"label": "Подготавливаем интервью", "description": "Открываем текущий или первый готовый кейс в интерфейсе."},
]

USER_SELECT_SQL = """
    SELECT
        u.id,
        u.full_name,
        u.email,
        u.created_at,
        u.role_id,
        u.job_description,
        p.raw_position,
        p.raw_duties,
        p.normalized_duties,
        p.role_selected,
        p.role_selected_code,
        p.role_confidence,
        p.role_rationale,
        p.role_consistency_status,
        p.role_consistency_comment,
        p.company_context,
        p.profile_metadata,
        p.raw_input,
        p.normalized_input,
        p.role_interpretation,
        p.user_work_context,
        p.role_limits,
        p.role_vocabulary,
        p.domain_profile,
        p.role_skill_profile,
        p.adaptation_rules_for_cases,
        p.user_domain,
        p.user_processes,
        p.user_tasks,
        p.user_stakeholders,
        p.user_risks,
        p.user_constraints,
        p.user_artifacts,
        p.user_systems,
        p.user_success_metrics,
        p.data_quality_notes,
        p.domain_resolution_status,
        p.domain_confidence,
        p.profile_quality,
        p.profile_build_instruction_code,
        p.profile_build_summary,
        p.profile_build_trace,
        u.active_profile_id,
        u.phone,
        u.telegram,
        u.personal_data_consent_accepted_at,
        u.personal_data_consent_version,
        u.company_industry,
        u.avatar_data_url
    FROM users u
    LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
"""


def _user_response_from_row(row, *, include_avatar: bool = False) -> UserResponse:
    payload = dict(row)
    if not include_avatar:
        payload["avatar_data_url"] = None
    return UserResponse(**payload)


def _strip_avatar(user: UserResponse | None) -> UserResponse | None:
    if user is None:
        return None
    if not user.avatar_data_url:
        return user
    return user.model_copy(update={"avatar_data_url": None})


def _compact_user_response(user: UserResponse | None) -> UserResponse | None:
    if user is None:
        return None
    return user.model_copy(
        update={
            "avatar_data_url": None,
            "profile_metadata": None,
            "raw_input": None,
            "normalized_input": None,
            "role_interpretation": None,
            "user_work_context": None,
            "role_limits": None,
            "role_vocabulary": None,
            "domain_profile": None,
            "role_skill_profile": None,
            "adaptation_rules_for_cases": None,
            "user_processes": None,
            "user_tasks": None,
            "user_stakeholders": None,
            "user_risks": None,
            "user_constraints": None,
            "user_artifacts": None,
            "user_systems": None,
            "user_success_metrics": None,
            "data_quality_notes": None,
            "profile_quality": None,
            "profile_build_trace": None,
        }
    )


def _participant_cycle_outcome(history: dict) -> tuple[str, str, str, str, str]:
    """Project one closed Cycle; processing failure wins over an existing limited Report."""
    if history.get('status') == 'failed':
        return ('failed', 'Не удалось подготовить отчёт',
                'Ответы сохранены. Возвращаться к заданиям не требуется.',
                'open_processing', 'Посмотреть состояние')
    if history.get('report_id') and history.get('report_limited'):
        return ('report_limited', 'С ограничениями',
                'Результат доступен. В отчёте указаны ограничения оценки.',
                'open_report', 'Посмотреть результаты →')
    if history.get('report_id'):
        return ('report_ready', 'Результат готов',
                'Вы завершили оценку. В отчёте — ваши навыки, примеры из ответов и пояснения к результатам.',
                'open_report', 'Посмотреть результаты →')
    return ('processing', 'Отчёт готовится',
            'Ответы сохранены. Результаты появятся здесь, когда отчёт будет готов.',
            'open_processing', 'Посмотреть состояние')


def _build_dashboard(connection, user: UserResponse, *, profile_id=None) -> UserDashboard:
    from Api.qa_orchestration import usage_scope
    from Api.participant_dashboard import assessment_rules, assignment_contact, cycle_progress, preparation_state
    # Dashboard follows the current Cycle runtime; legacy aggregate views are not inputs.
    readiness = participant_profile.readiness(connection, user_id=user.id, profile_id=profile_id)
    cycle_rows = connection.execute("""SELECT c.id,c.cycle_id,c.status,c.started_at,c.collection_closed_at,
        c.personalized_profile_id,c.assignment_id,c.profile_ref_json,c.organization_id,
        configuration.name AS assessment_title,organization.name AS organization_name,
        COUNT(position.id) FILTER (WHERE position.state='completed')::int AS completed_cases
        FROM m5_cycles c
        JOIN assessment_personalized_profiles p ON p.id=c.personalized_profile_id
        JOIN assessment_configurations configuration ON configuration.id=p.assessment_configuration_id
        JOIN organizations organization ON organization.id=c.organization_id
        LEFT JOIN m7_route_positions position ON position.cycle_db_id=c.id
        WHERE c.owner_user_id=%s AND c.usage_scope=%s
          AND (c.collection_closed_at IS NOT NULL OR (organization.is_active=TRUE
            AND EXISTS (SELECT 1 FROM organization_memberships member
              WHERE member.user_id=c.owner_user_id AND member.organization_id=c.organization_id)))
        GROUP BY c.id,configuration.name,organization.name
        ORDER BY c.created_at DESC,c.id DESC""", (user.id, usage_scope())).fetchall()
    history_by_cycle = {item['cycle_id']: item for item in m8_results.list_owned_cycles(connection, user.id)}
    acquaintance_state = acquaintance.read_state(connection, user_id=user.id)
    current_assessments: list[ParticipantAssessmentCard] = []
    completed_assessments: list[ParticipantAssessmentCard] = []
    early = acquaintance_state['readiness']
    help_organization_id = early.get('organization_id') if early.get('assignment_ref') else None
    for raw_cycle in cycle_rows:
        cycle = dict(raw_cycle)
        cycle_id = str(cycle['cycle_id'])
        history = history_by_cycle.get(cycle_id, {})
        completed_cases = int(cycle['completed_cases'] or 0)
        progress = cycle_progress(connection, cycle)
        total_cases = progress['planned_total']
        deadline = None
        if cycle['started_at'] and cycle['status'] in {'active', 'paused', 'interrupted'}:
            try:
                deadline = m7_completion.read_status(connection, cycle_id).get('calendar_deadline')
            except ValueError:
                deadline = None
        card_preparation = None
        if cycle['status'] in {'collection_closed', 'calculation_pending', 'calculated', 'failed'}:
            status, label, description, action, button = _participant_cycle_outcome(history)
            if action == 'open_processing':
                card_preparation = preparation_observation.report_status(connection, cycle_id)
            completed_assessments.append(ParticipantAssessmentCard(
                preparation=card_preparation,
                cycle_id=cycle_id, title=history.get('program_name') or cycle['assessment_title'],
                organization_name=cycle['organization_name'], status=status,
                status_label=label, description=description, action=action,
                button_label=button, completed_cases=completed_cases,
                total_cases=total_cases, **progress, journey_state=status, report_id=history.get('report_id'),
                closed_at=cycle['collection_closed_at']))
            continue
        if cycle['status'] == 'prepared':
            from Api.assessment_start_readiness import read as read_start_readiness
            start_decision = read_start_readiness(connection, cycle_id=cycle_id, user_id=int(user.id))
            same_assignment = (acquaintance_state.get('assignment_id') == cycle['assignment_id']
                and acquaintance_state.get('late_readiness', {}).get('personalized_profile_id') == cycle['personalized_profile_id'])
            operation = (acquaintance_state.get('preparation_operation') or {}) if same_assignment else {}
            card_preparation = operation.get('preparation')
            if operation.get('status') == 'failed':
                journey_state, label, description, action, button = (
                    'preparation_failed', 'Не удалось подготовить оценку',
                    'Ваши ответы сохранены. Проверьте состояние подготовки.', 'open_readiness', 'Проверить состояние')
            elif operation.get('status') in {'queued', 'running'}:
                journey_state, label, description, action, button = (
                    'preparing', 'Подготовка оценки',
                    'Готовим план и первую ситуацию. Ваши ответы знакомства сохранены. Время оценки ещё не идёт.',
                    'open_readiness', 'Посмотреть состояние')
            elif (start_decision['can_start'] and total_cases
                    and start_decision.get('plan_revision_id') == progress['plan_revision_id']):
                journey_state, label, description, action, button = (
                    'ready', 'Готова к началу',
                    'План и первая ситуация подготовлены. Перед началом вы сможете прочитать инструкцию.',
                    'open_readiness', 'Перейти к готовности →')
            elif start_decision.get('reasons'):
                journey_state, label, description, action, button = (
                    'readiness_error', 'Не удалось подтвердить готовность',
                    'Сохранённая оценка не прошла проверку готовности. Откройте её состояние.',
                    'open_readiness', 'Проверить состояние')
            else:
                journey_state, label, description, action, button = (
                    'not_ready', 'Готовность пока не подтверждена',
                    'Проверьте сохранённое состояние оценки перед началом.', 'open_readiness', 'Проверить готовность')
        else:
            journey_state, label, description, action, button = (
                'active', 'Оценка идёт', 'Продолжите прохождение с текущей ситуации.',
                'continue', 'Продолжить оценку →')
            if progress['between_situations']:
                from Api.product_cycle_preparation_queue import latest_next_operation
                try:
                    card_preparation = (latest_next_operation(connection, cycle_id=cycle_id, user_id=int(user.id)) or {}).get('preparation')
                except ValueError:
                    card_preparation = None
                journey_state, label, description = ('between_situations',
                    'Между ситуациями', 'Ответы сохранены. Следующую ситуацию вы начнёте сами.')
            elif progress['current_position_no'] is not None:
                from Api.m7_return_integration import read_return_state
                try:
                    returning = read_return_state(connection, cycle_id=cycle_id, owner_user_id=int(user.id))
                except ValueError:
                    returning = {}  # Legacy Cycle without a saved return policy.
                if returning.get('allowed_action') in {'continue_current', 'replace_current', 'replacement_candidate_required'}:
                    journey_state, label, description, button = ('return_required', 'Можно продолжить',
                        ('Вернитесь к той же сохранённой ситуации и переписке.'
                         if returning['allowed_action'] == 'continue_current'
                         else 'Проверьте условия продолжения оценки.'), 'Вернуться к оценке →')
        if cycle['status'] != 'prepared' and history.get('status') == 'failed':
            journey_state, label, description = ('runtime_error', 'Не удалось продолжить оценку',
                'Ваши ответы сохранены. Откройте оценку, чтобы проверить состояние.')
        if not current_assessments:
            help_organization_id = cycle['organization_id']
        current_assessments.append(ParticipantAssessmentCard(
            preparation=card_preparation,
            cycle_id=cycle_id, title=cycle['assessment_title'],
            organization_name=cycle['organization_name'], status=cycle['status'], journey_state=journey_state,
            status_label=label, description=description, action=action,
            button_label=button, completed_cases=completed_cases,
            total_cases=total_cases, **progress, calendar_deadline=deadline))

    completed_assessments.sort(
        key=lambda card: (
            card.closed_at.timestamp() if card.closed_at is not None else 0,
            card.cycle_id or '',
        ),
        reverse=True,
    )

    # A new assignment may coexist with old completed Cycles. Never let history
    # suppress its preparation card, and never duplicate a Cycle as an assignment.
    assignment_id = acquaintance_state.get('assignment_id')
    has_assignment_cycle = any(
        row['assignment_id'] == assignment_id if assignment_id is not None else
        row['personalized_profile_id'] == readiness.get('id') for row in cycle_rows)
    if not current_assessments and not has_assignment_cycle:
        if early.get('organization_id') is not None:
            status, label, description, action, button = preparation_state(acquaintance_state)
            if (early['status'] == 'ready' and assignment_id is None
                    and early.get('questionnaire_revision_id') is None
                    and acquaintance_state.get('mandatory_complete')
                    and acquaintance_state.get('onboarding', {}).get('status') in {'completed', 'skipped'}
                    and not assessment_assignment_sources.has_managed_assignment(connection, user_id=int(user.id))):
                # Answers are answers_confirmed, not completed. The legacy entry
                # follows saved onboarding and the existing M4 gate; managed W02 never uses it.
                status, label, description, action, button = ('acquaintance', 'Знакомство с оценкой',
                    'Перед началом познакомьтесь с форматом оценки.',
                    'open_legacy_acquaintance' if readiness['status'] == 'ready' else 'start',
                    'Продолжить знакомство')
            timing = acquaintance_state.get('assigned_timing') or {}
            current_assessments.append(ParticipantAssessmentCard(
                rules=assessment_rules(timing) if timing.get('status') == 'resolved' else None,
                preparation=(acquaintance_state.get('preparation_operation') or {}).get('preparation'),
                title=acquaintance_state.get('assessment_name') or 'Оценка 4К',
                organization_name=early.get('organization_name'), status=status, journey_state=status,
                status_label=label, description=description, action=action, button_label=button))

    report_rows = m8_results.list_owned_reports(connection, user.id)
    latest_cycle = dict(cycle_rows[0]) if cycle_rows else None
    completed_cases = int(latest_cycle['completed_cases'] or 0) if latest_cycle else 0
    latest_card = next((card for card in current_assessments + completed_assessments
                        if latest_cycle and card.cycle_id == str(latest_cycle['cycle_id'])), None)
    total_cases = latest_card.planned_total or 0 if latest_card else 0
    is_complete = bool(latest_cycle and latest_cycle['status'] in {'collection_closed', 'calculation_pending', 'calculated', 'failed'})
    # Compatibility field: no inferred percent for an adaptive, not-yet-finished plan.
    progress_percent = 100 if is_complete else 0
    reports = [AssessmentReport(title='4K — индивидуальный отчёт',summary='Сохранённый отчёт Cycle',
        badge='Готов',format_label='PDF',sequence_number=row['revision_no'],report_at=row['created_at'])
        for row in report_rows[:5]]
    reports_total_row = {'reports_total':len(report_rows)}
    assessment_allowed = readiness['status'] == 'ready'
    available_assessments: list[AvailableAssessment] = []
    if assessment_allowed and not is_complete:
        available_assessments.append(
            AvailableAssessment(
                code="competencies_4k",
                title="Компетенции 4К",
                description="Оценка навыков 4К.",
                duration_minutes=0,
                status="Доступен",
            )
        )

    active_assessment = AssessmentCard(
        code="competencies_4k",
        title="Компетенции 4К",
        description=(
            "Оценка навыков 4К."
            if assessment_allowed
            else readiness["message"]
        ),
        progress_percent=progress_percent if assessment_allowed else 0,
        completed_cases=completed_cases if assessment_allowed else 0,
        total_cases=total_cases if assessment_allowed else 0,
        status_label=(
            "Результат готовится" if is_complete else "Продолжить оценку"
        ) if assessment_allowed else "Нужно заполнить профиль",
        button_label=("Подробнее" if is_complete else "Продолжить") if assessment_allowed else "Заполнить профиль",
    )

    greeting_name = user.full_name.split()[0] if user.full_name else "коллега"
    return UserDashboard(
        personalized_profile_id=readiness["id"], profile_readiness=readiness["status"],
        greeting_name=greeting_name,
        active_assessment=active_assessment,
        available_assessments=available_assessments,
        reports_total=int(reports_total_row["reports_total"]) if reports_total_row and reports_total_row["reports_total"] is not None else 0,
        reports=reports,
        current_assessments=current_assessments,
        completed_assessments=completed_assessments,
        administrator_contact=assignment_contact(connection, user_id=user.id, organization_id=help_organization_id),
    )


def _ensure_admin_role(connection) -> int:
    existing_role = connection.execute(
        """
        SELECT id
        FROM roles
        WHERE code = %s
        LIMIT 1
        """,
        (ADMIN_ROLE_CODE,),
    ).fetchone()
    if existing_role is not None:
        return int(existing_role["id"])

    created_role = connection.execute(
        """
        INSERT INTO roles (code, name, short_definition, mission, personalization_variables)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            ADMIN_ROLE_CODE,
            ADMIN_ROLE_NAME,
            "Административная роль для доступа к аналитике и настройкам системы.",
            "Просмотр сводной аналитики, контроль прохождений и сопровождение работы платформы.",
            "admin_dashboard, analytics_access, reports_access",
        ),
    ).fetchone()
    connection.commit()
    return int(created_role["id"])


def _ensure_admin_user(connection) -> UserResponse:
    admin_role_id = _ensure_admin_role(connection)
    existing_user = connection.execute(
        USER_SELECT_SQL
        + """
        WHERE LOWER(COALESCE(u.email, '')) = %s
        LIMIT 1
        """,
        (ADMIN_EMAIL.lower(),),
    ).fetchone()
    if existing_user is not None:
        if existing_user["role_id"] != admin_role_id or existing_user["job_description"] != ADMIN_ROLE_NAME:
            connection.execute(
                """
                UPDATE users
                SET role_id = %s,
                    job_description = %s,
                    company_industry = COALESCE(company_industry, 'Администрирование платформы оценки компетенций')
                WHERE id = %s
                """,
                (admin_role_id, ADMIN_ROLE_NAME, existing_user["id"]),
            )
            connection.commit()
            refreshed_row = connection.execute(
                USER_SELECT_SQL
                + """
                WHERE u.id = %s
                LIMIT 1
                """,
                (existing_user["id"],),
            ).fetchone()
            return UserResponse(**dict(refreshed_row))
        return UserResponse(**dict(existing_user))

    created_user = connection.execute(
        """
        INSERT INTO users (full_name, email, role_id, job_description, phone, company_industry)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            ADMIN_FULL_NAME,
            ADMIN_EMAIL,
            admin_role_id,
            ADMIN_ROLE_NAME,
            None,
            "Администрирование платформы оценки компетенций",
        ),
    ).fetchone()
    connection.commit()

    row = connection.execute(
        USER_SELECT_SQL
        + """
        WHERE u.id = %s
        LIMIT 1
        """,
        (created_user["id"],),
    ).fetchone()
    return UserResponse(**dict(row))


def _is_admin_user(connection, user: UserResponse | None) -> bool:
    if user is None:
        return False
    if str(user.email or "").strip().lower() == ADMIN_EMAIL.lower():
        return True
    return get_admin_scope(connection, user).can_admin


def _get_admin_scope_or_403(connection, user: UserResponse | None, *, commit_scope: bool = True) -> AdminScope:
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    if str(user.email or "").strip().lower() == ADMIN_EMAIL.lower():
        return AdminScope(is_superadmin=True, actor_user_id=int(user.id))
    scope = get_admin_scope(connection, user)
    if commit_scope:
        connection.commit()
    if not scope.can_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return AdminScope(
        is_superadmin=scope.is_superadmin,
        organization_ids=scope.organization_ids,
        actor_user_id=int(user.id),
    )


def _require_superadmin(connection, user: UserResponse | None) -> AdminScope:
    scope = _get_admin_scope_or_403(connection, user)
    if not scope.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return scope


def _require_organization_admin(connection, user: UserResponse | None, organization_id: int) -> AdminScope:
    scope = _get_admin_scope_or_403(connection, user)
    if not scope.is_superadmin and organization_id not in scope.organization_ids:
        raise HTTPException(status_code=403, detail="Organization admin access required")
    return scope


def _normalize_admin_org_name(value: str | None) -> str:
    name = str(value or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Organization name is required")
    return name[:255]


def _normalize_admin_org_code(value: str | None) -> str:
    code = normalize_org_code(value)
    if not code:
        raise HTTPException(status_code=400, detail="Organization code is required")
    if len(code) > 80:
        raise HTTPException(status_code=400, detail="Organization code is too long")
    return code


def _normalize_admin_org_domain(value: str | None) -> str:
    domain = str(value or "").strip().lower().lstrip("@")
    if not domain or "." not in domain or any(symbol.isspace() for symbol in domain):
        raise HTTPException(status_code=400, detail="Valid email domain is required")
    return domain[:255]


def _normalize_optional_admin_text(value: str | None, *, max_length: int = 4000) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:max_length]


def _physical_organization_purge_available() -> bool:
    database_name = str(settings.db_name or "").strip().lower()
    return bool(settings.deletion_ledger_path) or "test" in database_name or "pytest" in database_name


def _protected_account_emails() -> set[str]:
    return configured_superadmin_emails() | {normalize_email(ADMIN_EMAIL)} | {
        email for emails in configured_org_admin_emails().values() for email in emails}


def _account_has_configured_access(connection, account) -> bool:
    protected = _protected_account_emails()
    if normalize_email(account['email']) in protected:
        return True
    # Verified identities are authentication addresses of the same account.
    # A configured alias can recreate access just like its primary email.
    return connection.execute("""SELECT 1 FROM user_identities
        WHERE user_id=%s AND is_verified=TRUE AND LOWER(email)=ANY(%s) LIMIT 1""",
        (int(account['id']), sorted(protected))).fetchone() is not None


def _require_account_purge_target(connection, *, scope: AdminScope, actor, account) -> None:
    user_id = int(account['id'])
    if int(actor.id) == user_id:
        raise HTTPException(409, detail='CANNOT_PURGE_CURRENT_ACCOUNT')
    # Configuration can recreate access. Refuse instead of retaining the email
    # in a purge blacklist or silently removing another configured superadmin.
    if _account_has_configured_access(connection, account):
        raise HTTPException(409, detail='CANNOT_PURGE_CONFIGURED_ACCOUNT')
    memberships = connection.execute("""SELECT organization_id,role,is_participant
        FROM organization_memberships WHERE user_id=%s ORDER BY organization_id FOR UPDATE""",
        (user_id,)).fetchall()
    if not scope.is_superadmin and (not any(row['is_participant'] for row in memberships)
            or any(int(row['organization_id']) not in scope.organization_ids for row in memberships)):
        raise HTTPException(403, detail='ACCOUNT_PURGE_SCOPE_FORBIDDEN')
    admin_organizations = [int(row['organization_id']) for row in memberships if row['role'] == 'admin']
    if admin_organizations:
        connection.execute('SELECT id FROM organizations WHERE id=ANY(%s) ORDER BY id FOR UPDATE',
                           (admin_organizations,)).fetchall()
        last_admin = connection.execute("""SELECT organization_id FROM organization_memberships
            WHERE organization_id=ANY(%s) AND role='admin' GROUP BY organization_id
            HAVING COUNT(*)<=1 LIMIT 1""", (admin_organizations,)).fetchone()
        if last_admin:
            raise HTTPException(409, detail='CANNOT_PURGE_LAST_ORGANIZATION_ADMIN')


def _validate_account_purge_plan(connection, *, scope: AdminScope, user_id: int,
                                 tables, foreign_keys) -> None:
    if scope.is_superadmin:
        return
    try:
        require_account_plan_organization_scope(connection, user_id=user_id,
            organization_ids=scope.organization_ids, tables=tables, foreign_keys=foreign_keys)
    except ValueError as exc:
        raise HTTPException(409 if str(exc) == 'PURGE_PREVIEW_STALE' else 403, detail=str(exc)) from exc


def _invalidate_deleted_accounts(user_ids) -> None:
    # The receipt and physical deletion are already committed. A failed cache
    # eviction cannot turn a known successful deletion into a retryable failure.
    for user_id in user_ids:
        try:
            interviewer_agent.invalidate_user(int(user_id))
        except Exception:
            logger.exception('Deleted account cache invalidation failed user_id=%s', user_id)


def _project_admin_assessment_stage(row: dict) -> dict:
    cycle_status = row.get("cycle_status")
    preparation_status = row.get("preparation_status")
    acquaintance_status = row.get("acquaintance_status") or "not_started"
    plan_status = row.get("plan_status")
    admission = row.get('start_readiness') if isinstance(row.get('start_readiness'), dict) else {}
    planned = int(row.get("planned_positions") or 0)
    completed = int(row.get("completed_positions") or 0)
    progress = {"completed": completed, "planned": planned} if planned else None
    blocker = None

    if row.get("assignment_status") == "revoked" or row.get("revoked_at") is not None:
        code, label, action = "cancelled", "Назначение отменено", None
    elif row.get("report_ready"):
        code, label = "report_ready", "Отчёт готов"
        action = "open_report" if row.get("report_access") else None
    elif cycle_status == "failed" or row.get("pipeline_status") == "failed":
        code, label, action = "failed", "Обработка завершилась с ошибкой", "open_processing"
        blocker = {"reason": "Техническая обработка не завершена.", "responsible": "Система"}
    elif cycle_status in {"collection_closed", "calculation_pending", "calculated"}:
        code, label, action = "processing", "Готовится отчёт", "open_processing"
    elif cycle_status == "active":
        code, label, action = "active", "Оценка выполняется", "resume_assessment"
    elif cycle_status == "paused":
        code, label, action = "paused", "Оценка приостановлена", "resume_assessment"
        blocker = {"reason": "Оценка поставлена на разрешённую паузу.", "responsible": "Участник"}
    elif cycle_status == "interrupted":
        code, label, action = "interrupted", "Оценка прервана", "resume_assessment"
        blocker = {"reason": "Для продолжения требуется восстановить сессию.", "responsible": "Участник"}
    elif preparation_status == "failed":
        code, label, action = "preparation_failed", "Подготовка завершилась с ошибкой", "retry_preparation"
        blocker = {"reason": "Подготовка оценки не завершена.", "responsible": "Организатор оценки"}
    elif preparation_status in {"queued", "running"}:
        code, label, action = "preparing", "Идёт подготовка оценки", "check_preparation"
    elif (cycle_status == "prepared" and plan_status in {"READY", "LIMITED"} and planned > 0
          and row.get('admitted_situation') is True
          and admission.get('contract') == 'm7_start_readiness/1' and admission.get('can_start') is True
          and admission.get('cycle_id') == str(row.get('cycle_id')) and admission.get('reasons') == []):
        code, label, action = "ready_to_start", "Готов к прохождению оценки", "start_assessment"
    elif cycle_status == "prepared":
        code, label, action = "start_blocked", "Старт оценки заблокирован", None
        reason = "Для Cycle не подтверждён исполнимый план."
        if plan_status == "LIMITED":
            reason = "План ограничен и не разрешает старт полного маршрута."
        elif plan_status == "NO_ROUTE":
            reason = "Для Cycle не найден допустимый маршрут."
        elif not row.get('admitted_situation'):
            reason = "Первая оценочная ситуация ещё не допущена для участника."
        if admission.get('reasons'):
            reason = "Сервер не подтвердил условия старта: " + ", ".join(admission['reasons']) + "."
        blocker = {"reason": reason, "responsible": "Организатор оценки"}
    elif preparation_status == "completed":
        code, label, action = "preparation_complete", "Подготовка завершена, старт ещё не подтверждён", None
        blocker = {"reason": "Точный Cycle и исполнимый план ещё не подтверждены.", "responsible": "Организатор оценки"}
    elif acquaintance_status in {"answers_confirmed", "completed"}:
        code, label, action = "acquaintance_complete", "Знакомство завершено", "prepare_assessment"
    elif acquaintance_status == "in_progress":
        code, label, action = "acquaintance", "Проходит знакомство", "continue_acquaintance"
    else:
        code, label, action = "assigned", "Оценка назначена", "send_invitation"

    result_summary = None
    payload = row.get("results_payload") or {}
    skills = payload.get("assessed_skill_profile") or [] if isinstance(payload, dict) else []
    outcomes = {str(item.get("outcome")) for item in skills if item.get("outcome")}
    report_status = row.get("report_status")
    if outcomes or report_status == "no_result":
        if outcomes == {"no_result"} or (not outcomes and report_status == "no_result"):
            result_summary = {"kind": "insufficient", "label": "Недостаточно оснований для результата"}
        elif "result_without_score" in outcomes and not outcomes.intersection({"full_score", "partial_score"}):
            result_summary = {"kind": "without_score", "label": "Есть наблюдения без общего балла"}
        elif outcomes == {"full_score"} and report_status != "limited" and not any(
            (payload.get("partial_result") or {}).get(key)
            for key in ("is_incomplete", "plan_scope_limited", "observation_limited", "source_limited", "technical_failure")
        ):
            result_summary = {"kind": "full", "label": "Полный результат"}
        else:
            result_summary = {"kind": "partial", "label": "Частичный или ограниченный результат"}
        processing = payload.get("processing") or {}
        result_summary["technical_failure"] = processing.get("status") == "failed"

    description_parts = []
    if progress:
        description_parts.append(f"Прогресс: {completed} из {planned} AS плана.")
    if blocker:
        description_parts.append(f"{blocker['reason']} Ответственный: {blocker['responsible']}.")
    if result_summary:
        description_parts.append(result_summary["label"] + ".")
        if result_summary["technical_failure"]:
            description_parts.append("Есть отдельное техническое ограничение обработки.")
    return {
        "preparation": row.get("preparation"),
        "code": code, "label": label, "action": action,
        "cycle_id": str(row["cycle_id"]) if row.get("cycle_id") else None,
        "operation_id": row.get("preparation_operation_id"),
        "preparation_status": preparation_status,
        "start_readiness": row.get('start_readiness'),
        "profile_readiness": {
            "personalized_profile_id": int(row["personalized_profile_id"]),
            "status": row["profile_status"],
        } if row.get("personalized_profile_id") is not None else None,
        "acquaintance_status": acquaintance_status,
        "report_id": str(row["report_id"]) if row.get("report_id") and row.get("report_access") else None,
        "report_access": row.get("report_access_kind") if row.get("report_access") else None,
        "assignment_id": int(row["assignment_id"]),
        "progress": progress, "blocker": blocker, "result_summary": result_summary,
        "description": " ".join(description_parts) or None,
    }


def _project_member_scope_compatibility(stages: dict) -> dict:
    """Legacy flat fields are truthful only when one exact assignment is known."""
    stage = next(iter(stages.values())) if len(stages) == 1 else {}
    return {
        'assessment_preparation_operation_id': stage.get('operation_id'),
        'assessment_preparation_status': stage.get('preparation_status'),
        'assessment_prepared': stage.get('code') in {'ready_to_start', 'active', 'paused',
            'interrupted', 'processing', 'report_ready'},
        'acquaintance_status': stage.get('acquaintance_status') or 'unknown',
    }


def _remember_newest_assessment_stage(stages: dict, member_key: tuple[int, int],
                                      assignment_ref: str, stage: dict) -> None:
    """Keep the first row from a newest-first assignment projection."""
    stages.setdefault(member_key, {}).setdefault(assignment_ref, stage)


def _build_admin_organizations(connection, scope: AdminScope | None = None, *, actor_user_id: int | None = None) -> AdminOrganizationsResponse:
    ensure_configured_organizations(connection)
    connection.commit()
    scope_filter = "" if scope is None or scope.is_superadmin else "WHERE id = ANY(%s)"
    scope_params: tuple = () if not scope_filter else (list(scope.organization_ids),)
    org_rows = connection.execute(
        f"""
        SELECT id, code, name, is_active, profile, founded_year, employee_count,
               industry, website, headquarters, notes, invitation_intro, created_at, updated_at
        FROM organizations
        {scope_filter}
        ORDER BY is_active DESC, name ASC, code ASC
        """,
        scope_params,
    ).fetchall()
    org_ids = [int(row["id"]) for row in org_rows]
    hidden_user_sql = ""
    hidden_user_params: tuple = ()
    if scope is not None and not scope.is_superadmin:
        hidden_user_sql = """
          AND LOWER(u.email) <> ALL(%s)
          AND NOT EXISTS (
              SELECT 1
              FROM user_platform_roles platform_assignment
              JOIN platform_role_permissions platform_permission
                ON platform_permission.platform_role_id = platform_assignment.platform_role_id
              WHERE platform_assignment.user_id = u.id
                AND platform_assignment.revoked_at IS NULL
          )
        """
        hidden_user_params = (sorted(configured_superadmin_emails() | {LOCAL_SUPERADMIN_EMAIL}),)
    domains_by_org: dict[int, list[str]] = {org_id: [] for org_id in org_ids}
    admins_by_org: dict[int, list[dict]] = {org_id: [] for org_id in org_ids}
    members_by_org_list: dict[int, list[dict]] = {org_id: [] for org_id in org_ids}
    members_by_org: dict[int, int] = {org_id: 0 for org_id in org_ids}
    reports_by_org: dict[int, int] = {org_id: 0 for org_id in org_ids}
    latest_batch_by_org: dict[int, str] = {}
    programs_by_org: dict[int, dict] = {}
    assessment_stages: dict[tuple[int, int], dict[str, dict]] = {}
    assessment_history: dict[tuple[int, int], list[dict]] = {}
    if org_ids:
        domain_rows = connection.execute(
            """
            SELECT organization_id, domain
            FROM organization_email_domains
            WHERE organization_id = ANY(%s)
            ORDER BY domain ASC
            """,
            (org_ids,),
        ).fetchall()
        for row in domain_rows:
            domains_by_org.setdefault(int(row["organization_id"]), []).append(str(row["domain"] or ""))

        admin_rows = connection.execute(
            f"""
            SELECT om.organization_id, u.id AS user_id, u.email, u.full_name, om.is_participant
            FROM organization_memberships om
            JOIN users u ON u.id = om.user_id
            WHERE om.organization_id = ANY(%s)
              AND om.role = 'admin'
              {hidden_user_sql}
            ORDER BY LOWER(COALESCE(u.email, '')) ASC
            """,
            (org_ids, *hidden_user_params),
        ).fetchall()
        for row in admin_rows:
            email = str(row["email"] or "").strip()
            if not email:
                continue
            admins_by_org.setdefault(int(row["organization_id"]), []).append(
                {
                    "user_id": int(row["user_id"]), "email": email, "full_name": row["full_name"],
                    "is_participant": row["is_participant"],
                }
            )

        stage_rows = connection.execute(
            ADMIN_ASSIGNMENT_STAGES_SQL,
            (org_ids,),
        ).fetchall()
        for row in stage_rows:
            row = dict(row)
            member_key = (int(row["organization_id"]), int(row["recipient_user_id"]))
            assessment_history.setdefault(member_key, []).append({
                "assignment_id": int(row["assignment_id"]),
                "assignment_ref": str(row["assignment_ref"]),
                "assignment_status": str(row["assignment_status"]),
                "assignment_created_at": row.get("assignment_created_at"),
                "assignment_revoked_at": row.get("revoked_at"),
                "cycle_id": str(row["cycle_id"]) if row.get("cycle_id") else None,
                "cycle_status": row.get("cycle_status"),
            })
            if row.get('cycle_status') in {'collection_closed','calculation_pending','calculated','failed'}:
                row['preparation'] = preparation_observation.report_status(connection, str(row['cycle_id']))
            elif row.get('cycle_id'):
                from Api.product_cycle_preparation_queue import latest_next_operation
                try:
                    next_operation = latest_next_operation(connection, cycle_id=str(row['cycle_id']), user_id=int(row['recipient_user_id']))
                except ValueError:
                    next_operation = None
                if next_operation and next_operation['status'] in {'queued','running','failed'}:
                    row['preparation'] = next_operation.get('preparation')
            if not row.get('preparation') and row.get('preparation_operation_id'):
                operation = product_cycle_preparation_queue.get_owned_status(str(row['preparation_operation_id']), int(row['recipient_user_id']))
                row['preparation'] = operation.get('preparation') if operation else None
            if row.get('cycle_status') == 'prepared':
                from Api.assessment_start_readiness import read as read_start_readiness
                row['start_readiness'] = read_start_readiness(
                    connection, cycle_id=str(row['cycle_id']), user_id=int(row['recipient_user_id']))
            # Rows are newest first. Preserve the current generation while keeping every
            # older generation in assessment_history; an old revocation must not replace
            # the stage of a later active assignment with the same assignment_ref.
            _remember_newest_assessment_stage(
                assessment_stages,
                (int(row["organization_id"]), int(row["recipient_user_id"])),
                str(row["assignment_ref"]),
                _project_admin_assessment_stage(dict(row)),
            )

        member_detail_rows = connection.execute(
            f"""
            SELECT
                om.organization_id,
                om.role,
                u.id AS user_id,
                (SELECT COUNT(*) FROM participant_data_issue_reports issue
                 WHERE issue.organization_id=om.organization_id AND issue.user_id=u.id) AS issue_count,
                u.email,
                u.full_name,
                u.job_description,
                u.role_id,
                u.active_profile_id,
                u.company_industry,
                p.normalized_duties,
                c.user_id IS NOT NULL AS has_password,
                p.raw_position,
                p.raw_duties,
                personal_invitation.id AS invitation_id,
                personal_invitation.expires_at AS invitation_expires_at,
                personal_invitation.created_at AS invitation_created_at,
                personal_invitation.used_at AS invitation_used_at,
                personal_invitation.revoked_at AS invitation_revoked_at,
                personal_invitation.delivery_status AS invitation_delivery_status,
                personal_invitation.delivery_error AS invitation_delivery_error,
                personal_invitation.request_id AS invitation_operation_id,
                personal_invitation.assignment_ref AS invitation_assignment_ref,
                personal_invitation.created_by_user_id AS invitation_sender_id,
                COALESCE(assignments.assignment_refs, ARRAY[]::text[]) AS assessment_assignments,
                CASE
                    WHEN personal_invitation.id IS NULL THEN 'not_created'
                    WHEN personal_invitation.revoked_at IS NOT NULL THEN 'revoked'
                    WHEN personal_invitation.used_at IS NOT NULL THEN 'used'
                    WHEN personal_invitation.expires_at <= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') THEN 'expired'
                    ELSE 'active'
                END AS invitation_link_status,
                CASE
                    WHEN personal_invitation.id IS NULL THEN 'not_sent'
                    WHEN personal_invitation.revoked_at IS NOT NULL THEN 'revoked'
                    WHEN personal_invitation.used_at IS NOT NULL THEN 'used'
                    WHEN personal_invitation.expires_at <= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') THEN 'expired'
                    ELSE personal_invitation.delivery_status
                END AS invitation_status
            FROM organization_memberships om
            JOIN users u ON u.id = om.user_id
            LEFT JOIN auth_password_credentials c ON c.user_id = u.id OR LOWER(c.email) = LOWER(u.email)
            LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
            LEFT JOIN LATERAL (
                SELECT id, created_at, expires_at, revoked_at, used_at, delivery_status, delivery_error,
                       request_id, assignment_ref, created_by_user_id
                FROM organization_invitations oi
                WHERE oi.organization_id = om.organization_id
                  AND LOWER(oi.recipient_email) = LOWER(u.email)
                  AND oi.purpose = 'personal_registration'
                ORDER BY oi.created_at DESC, oi.id DESC
                LIMIT 1
            ) personal_invitation ON TRUE
            LEFT JOIN LATERAL (
                SELECT ARRAY_AGG(oa.assignment_ref ORDER BY oa.assignment_ref) AS assignment_refs
                FROM organization_assessment_assignments oa
                JOIN organization_assessment_source_bindings source_binding
                  ON source_binding.assignment_id=oa.id
                WHERE oa.organization_id = om.organization_id
                  AND oa.recipient_user_id = u.id
                  AND oa.status = 'active'
                  AND oa.revoked_at IS NULL
            ) assignments ON TRUE
            WHERE om.organization_id = ANY(%s)
              AND om.is_participant = TRUE
              {hidden_user_sql}
            ORDER BY LOWER(COALESCE(u.email, '')) ASC
            LIMIT 500
            """,
            (org_ids, *hidden_user_params),
        ).fetchall()
        for row in member_detail_rows:
            email = str(row["email"] or "").strip()
            if not email:
                continue
            members_by_org_list.setdefault(int(row["organization_id"]), []).append(
                {
                    "user_id": int(row["user_id"]),
                    "issue_count": int(row["issue_count"]),
                    "email": email,
                    "full_name": row["full_name"],
                    "role": row["role"] or "member",
                    "has_password": bool(row["has_password"]),
                    "job_description": row["job_description"],
                    "raw_position": row["raw_position"],
                    "raw_duties": row["raw_duties"],
                    **_project_member_scope_compatibility(assessment_stages.get(
                        (int(row['organization_id']), int(row['user_id'])), {})),
                    "assessment_profile_ready": bool(
                        row["role_id"]
                        and row["active_profile_id"]
                        and row["company_industry"]
                        and row["normalized_duties"]
                    ),
                    "invitation_id": row["invitation_id"],
                    "invitation_status": row["invitation_status"] or "not_sent",
                    "admission_status": "admitted",
                    "registration_status": "registered" if bool(row["has_password"]) else "pending",
                    "invitation_delivery_status": row["invitation_delivery_status"] or "not_sent",
                    "invitation_reason": invitation_outcomes.facts(row['invitation_delivery_status'] or 'not_sent', row.get('invitation_delivery_error')),
                    "invitation_operation_id": row.get('invitation_operation_id') if row.get('invitation_sender_id') == actor_user_id else None,
                    "invitation_assignment_ref": row["invitation_assignment_ref"],
                    "invitation_link_status": row["invitation_link_status"] or "not_created",
                    "invitation_expires_at": row["invitation_expires_at"],
                    "invitation_created_at": row["invitation_created_at"],
                    "invitation_used_at": row["invitation_used_at"],
                    "invitation_revoked_at": row["invitation_revoked_at"],
                    "assessment_assignments": list(row["assessment_assignments"] or []),
                    "assessment_stages": assessment_stages.get(
                        (int(row["organization_id"]), int(row["user_id"])), {}
                    ),
                    "assessment_history": assessment_history.get(
                        (int(row["organization_id"]), int(row["user_id"])), []
                    ),
                }
            )

        member_rows = connection.execute(
            f"""
            SELECT om.organization_id, COUNT(*)::int AS member_count
            FROM organization_memberships om
            JOIN users u ON u.id = om.user_id
            WHERE om.organization_id = ANY(%s)
              AND om.is_participant = TRUE
              {hidden_user_sql}
            GROUP BY om.organization_id
            """,
            (org_ids, *hidden_user_params),
        ).fetchall()
        for row in member_rows:
            members_by_org[int(row["organization_id"])] = int(row["member_count"] or 0)

        report_rows = connection.execute(
            """
            SELECT cycle.organization_id, COUNT(DISTINCT cycle.id)::int AS reports_count
            FROM m5_cycles cycle
            JOIN m8_results result ON result.cycle_db_id=cycle.id
            JOIN m8_result_revisions revision ON revision.results_id=result.id
            JOIN m8_reports report ON report.result_revision_id=revision.id
            WHERE cycle.organization_id = ANY(%s) AND cycle.usage_scope='assessment'
              AND report.status='ready'
              AND NOT EXISTS (SELECT 1 FROM m10_pipeline_runs pipeline
                              WHERE pipeline.cycle_db_id=cycle.id AND pipeline.status='failed')
            GROUP BY cycle.organization_id
            """,
            (org_ids,),
        ).fetchall()
        for row in report_rows:
            reports_by_org[int(row["organization_id"])] = int(row["reports_count"] or 0)

        batch_rows = connection.execute(
            """
            SELECT DISTINCT ON (organization_id) organization_id, batch_id
            FROM assessment_preparation_batches
            WHERE organization_id = ANY(%s)
            ORDER BY organization_id, created_at DESC, id DESC
            """,
            (org_ids,),
        ).fetchall()
        for row in batch_rows:
            latest_batch_by_org[int(row["organization_id"])] = str(row["batch_id"])

        for organization_id in org_ids:
            program = assessment_programs.current_connection(
                connection, organization_id=organization_id)
            if program:
                programs_by_org[organization_id] = program

    return AdminOrganizationsResponse(
        title="Организации",
        subtitle="Управление доменами и администраторами организаций.",
        is_superadmin=bool(scope is None or scope.is_superadmin),
        physical_purge_available=_physical_organization_purge_available(),
        purge_preview_available=bool(scope is None or scope.can_admin),
        assessment_programs=assessment_programs.list_published(connection)
            if scope is None or scope.is_superadmin else [],
        items=[
            AdminOrganizationItem(
                id=int(row["id"]),
                code=str(row["code"]),
                name=str(row["name"]),
                is_active=bool(row["is_active"]),
                profile=row["profile"],
                founded_year=row["founded_year"],
                employee_count=row["employee_count"],
                industry=row["industry"],
                website=row["website"],
                headquarters=row["headquarters"],
                notes=row["notes"],
                invitation_intro=row["invitation_intro"],
                domains=domains_by_org.get(int(row["id"]), []),
                admins=admins_by_org.get(int(row["id"]), []),
                members=members_by_org_list.get(int(row["id"]), []),
                members_count=members_by_org.get(int(row["id"]), 0),
                reports_count=reports_by_org.get(int(row["id"]), 0),
                assessment_preparation_batch_id=latest_batch_by_org.get(int(row["id"])),
                assessment_program=assessment_programs.public_program(programs_by_org.get(int(row["id"]))),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in org_rows
        ],
    )


def _ensure_org_admin_user(connection, *, email: str, full_name: str | None = None) -> int:
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid admin email is required")
    user_row = connection.execute(
        """
        SELECT id
        FROM users
        WHERE LOWER(email) = %s
        LIMIT 1
        """,
        (normalized_email,),
    ).fetchone()
    identity_row = connection.execute(
        "SELECT user_id FROM user_identities WHERE LOWER(email) = %s LIMIT 1",
        (normalized_email,),
    ).fetchone()
    if identity_row is not None:
        if user_row is None or identity_row["user_id"] != user_row["id"]:
            raise HTTPException(status_code=409, detail="ADMIN_EMAIL_ALREADY_LINKED")
        return int(user_row["id"])

    if user_row is not None:
        user_id = int(user_row["id"])
    else:
        fallback_name = normalized_email.split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
        name = _normalize_optional_admin_text(full_name, max_length=255) or fallback_name[:255]
        created_user = connection.execute(
            """
            INSERT INTO users (full_name, email, role_id, job_description, phone, company_industry)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (name or "Администратор организации", normalized_email, None, None, None, None),
        ).fetchone()
        user_id = int(created_user["id"])

    identity = connection.execute(
        """
        INSERT INTO user_identities (user_id, provider, provider_subject, email, is_primary, is_verified, verified_at, updated_at)
        VALUES (%s, %s, %s, %s, TRUE, FALSE, NULL, NOW())
        ON CONFLICT (provider, provider_subject) WHERE provider_subject IS NOT NULL DO NOTHING
        RETURNING user_id
        """,
        (user_id, "email_magic_link", normalized_email, normalized_email),
    ).fetchone()
    if identity is None:
        raise HTTPException(status_code=409, detail="ADMIN_EMAIL_ALREADY_LINKED")
    return user_id


def _ensure_org_member_user(
    connection,
    *,
    email: str,
    full_name: str | None = None,
    role_description: str | None = None,
) -> int:
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid member email is required")
    clean_name = _normalize_optional_admin_text(full_name, max_length=255)
    fallback_name = str(clean_name or normalized_email.split("@", 1)[0]).replace(".", " ").replace("_", " ").strip()
    clean_role = _normalize_optional_admin_text(role_description, max_length=1000)
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
            (fallback_name[:255] or "Пользователь", normalized_email, None, clean_role, None, None),
        ).fetchone()
        user_id = int(created_user["id"])
    else:
        user_id = int(user_row["id"])
        connection.execute(
            """
            UPDATE users
            SET full_name = COALESCE(%s, full_name),
                job_description = COALESCE(%s, job_description)
            WHERE id = %s
            """,
            (clean_name, clean_role, user_id),
        )

    connection.execute(
        """
        INSERT INTO user_identities (user_id, provider, provider_subject, email, is_primary, is_verified, verified_at, updated_at)
        VALUES (%s, %s, %s, %s, TRUE, FALSE, NULL, NOW())
        ON CONFLICT (provider, provider_subject) WHERE provider_subject IS NOT NULL DO UPDATE
        SET user_id = EXCLUDED.user_id,
            email = EXCLUDED.email,
            updated_at = NOW()
        """,
        (user_id, "email_magic_link", normalized_email, normalized_email),
    )
    return user_id


def _upsert_org_member_profile(
    connection,
    *,
    user_id: int,
    role_description: str | None = None,
    job_instructions: str | None = None,
) -> None:
    clean_role = _normalize_optional_admin_text(role_description, max_length=1000)
    clean_instructions = _normalize_optional_admin_text(job_instructions, max_length=12000)
    if not clean_role and not clean_instructions:
        return
    active_row = connection.execute(
        "SELECT active_profile_id FROM users WHERE id = %s LIMIT 1",
        (user_id,),
    ).fetchone()
    if active_row is not None and active_row["active_profile_id"] is not None:
        connection.execute(
            """
            UPDATE user_role_profiles
            SET raw_position = COALESCE(%s, raw_position),
                raw_duties = COALESCE(%s, raw_duties),
                normalized_duties = COALESCE(%s, normalized_duties),
                raw_input = COALESCE(raw_input, '{}'::jsonb) || %s::jsonb,
                profile_updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                clean_role,
                clean_instructions,
                clean_instructions,
                json.dumps({"source": "organization_csv", "role_description": clean_role, "job_instructions": clean_instructions}, ensure_ascii=False),
                int(active_row["active_profile_id"]),
            ),
        )
        return

    version_row = connection.execute(
        "SELECT COALESCE(MAX(profile_version), 0) + 1 AS next_version FROM user_role_profiles WHERE user_id = %s",
        (user_id,),
    ).fetchone()
    profile_row = connection.execute(
        """
        INSERT INTO user_role_profiles (
            user_id, raw_position, raw_duties, normalized_duties,
            profile_metadata, raw_input, normalized_input, profile_quality,
            user_context_vars, profile_version, profile_updated_at
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, CURRENT_TIMESTAMP)
        RETURNING id
        """,
        (
            user_id,
            clean_role,
            clean_instructions,
            clean_instructions,
            json.dumps({"source": "organization_import", "status": "draft"}, ensure_ascii=False),
            json.dumps({"role_description": clean_role, "job_instructions": clean_instructions}, ensure_ascii=False),
            json.dumps({"position": clean_role, "duties": clean_instructions}, ensure_ascii=False),
            json.dumps({"completeness": "draft", "needs_clarification": True}, ensure_ascii=False),
            json.dumps({"job_title": clean_role, "job_instructions": clean_instructions}, ensure_ascii=False),
            int(version_row["next_version"] or 1),
        ),
    ).fetchone()
    connection.execute("UPDATE users SET active_profile_id = %s WHERE id = %s", (int(profile_row["id"]), user_id))


def _lock_membership_by_email(connection, *, email: str) -> dict | None:
    """Serialize membership changes for one normalized account and return its current scope."""
    normalized_email = normalize_email(email)
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (normalized_email,))
    row = connection.execute(
        """
        SELECT u.id AS user_id, membership.organization_id, membership.role,
               organization.name AS organization_name
        FROM users u
        LEFT JOIN organization_memberships membership ON membership.user_id = u.id
        LEFT JOIN organizations organization ON organization.id = membership.organization_id
        WHERE LOWER(u.email) = %s
        LIMIT 1
        """,
        (normalized_email,),
    ).fetchone()
    return dict(row) if row is not None else None


def _reject_foreign_membership(
    membership: dict | None,
    *,
    organization_id: int,
    expose_organization: bool,
) -> None:
    if membership is None or membership.get("organization_id") is None:
        return
    current_organization_id = int(membership["organization_id"])
    if current_organization_id == int(organization_id):
        return
    if expose_organization:
        organization_name = str(membership.get("organization_name") or "другая организация")
        raise HTTPException(
            status_code=409,
            detail=(
                "ORGANIZATION_MEMBERSHIP_CONFLICT: Пользователь связан с организацией "
                f"«{organization_name}». Управляйте его участием в текущей организации."
            ),
        )
    raise HTTPException(
        status_code=409,
        detail=(
            "ORGANIZATION_MEMBERSHIP_CONFLICT: Не удалось добавить пользователя: он связан "
            "с другой организацией. Обратитесь к суперадминистратору."
        ),
    )


def _reject_platform_protected_account(connection, *, email: str, user_id: int | None = None) -> None:
    if is_platform_protected_account(connection, email=email, user_id=user_id):
        raise HTTPException(
            status_code=409,
            detail="Не удалось добавить пользователя в организацию.",
        )


def _execute_membership_write(
    connection,
    *,
    email: str,
    organization_id: int,
    expose_existing_organization: bool,
    query: str,
    params: tuple,
) -> None:
    connection.execute("SAVEPOINT organization_membership_write")
    try:
        connection.execute(query, params)
        connection.execute("RELEASE SAVEPOINT organization_membership_write")
    except psycopg.errors.UniqueViolation:
        connection.execute("ROLLBACK TO SAVEPOINT organization_membership_write")
        connection.execute("RELEASE SAVEPOINT organization_membership_write")
        membership = _lock_membership_by_email(connection, email=email)
        _reject_foreign_membership(
            membership,
            organization_id=organization_id,
            expose_organization=expose_existing_organization,
        )
        if membership is None or membership.get("organization_id") is None:
            raise


def _attach_user_to_organization(
    connection,
    *,
    organization_id: int,
    email: str,
    full_name: str | None = None,
    role_description: str | None = None,
    job_instructions: str | None = None,
    admission_source: str,
    admitted_by_user_id: int,
    expose_existing_organization: bool = False,
) -> int:
    org_row = connection.execute(
        "SELECT id FROM organizations WHERE id = %s AND is_active = TRUE LIMIT 1",
        (organization_id,),
    ).fetchone()
    if org_row is None:
        raise HTTPException(status_code=404, detail="Active organization not found")
    membership = _lock_membership_by_email(connection, email=email)
    _reject_platform_protected_account(
        connection,
        email=email,
        user_id=int(membership["user_id"]) if membership is not None else None,
    )
    _reject_foreign_membership(
        membership,
        organization_id=organization_id,
        expose_organization=expose_existing_organization,
    )
    user_id = _ensure_org_member_user(
        connection,
        email=email,
        full_name=full_name,
        role_description=role_description,
    )
    _execute_membership_write(
        connection,
        email=email,
        organization_id=organization_id,
        expose_existing_organization=expose_existing_organization,
        query="""
        INSERT INTO organization_memberships (
            organization_id, user_id, role, admission_source, admitted_by_user_id, admitted_at
        )
        VALUES (%s, %s, 'member', %s, %s, NOW())
        ON CONFLICT (organization_id, user_id) DO UPDATE
        SET is_participant = TRUE,
            admission_source = EXCLUDED.admission_source,
            admitted_by_user_id = EXCLUDED.admitted_by_user_id,
            admitted_at = EXCLUDED.admitted_at,
            updated_at = NOW()
        """,
        params=(organization_id, user_id, admission_source, admitted_by_user_id),
    )
    connection.execute("SAVEPOINT org_member_profile")
    try:
        _upsert_org_member_profile(
            connection,
            user_id=user_id,
            role_description=role_description,
            job_instructions=job_instructions,
        )
        connection.execute("RELEASE SAVEPOINT org_member_profile")
    except Exception:
        connection.execute("ROLLBACK TO SAVEPOINT org_member_profile")
        connection.execute("RELEASE SAVEPOINT org_member_profile")
    return user_id


def _csv_value(row: dict[str, str], *names: str) -> str | None:
    normalized = {str(key or "").strip().lower(): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _build_admin_dashboard(connection, scope: AdminScope, period_key: str = "30d") -> AdminDashboard:
    organization_filter = "" if scope.is_superadmin else " AND cycle.organization_id=ANY(%s)"
    organization_params: tuple = () if scope.is_superadmin else (list(scope.organization_ids),)
    cycle_counts = connection.execute(
        f"""SELECT COUNT(*) FILTER (WHERE cycle.started_at IS NOT NULL)::int AS started,
                   COUNT(*) FILTER (WHERE cycle.started_at IS NOT NULL
                                      AND cycle.collection_closed_at IS NOT NULL)::int AS closed
            FROM m5_cycles cycle
            WHERE cycle.usage_scope='assessment' {organization_filter}""",
        organization_params,
    ).fetchone()
    report_counts = connection.execute(
        f"""SELECT COUNT(DISTINCT cycle.id)::int AS ready
            FROM m5_cycles cycle
            JOIN m8_results result ON result.cycle_db_id=cycle.id
            JOIN m8_result_revisions revision ON revision.results_id=result.id
            JOIN m8_reports report ON report.result_revision_id=revision.id
            WHERE cycle.usage_scope='assessment' AND report.status IN ('ready','limited','no_result')
              AND NOT EXISTS (
                SELECT 1 FROM m10_pipeline_runs pipeline
                WHERE pipeline.cycle_db_id=cycle.id AND pipeline.status='failed')
              {organization_filter}""",
        organization_params,
    ).fetchone()
    started = int(cycle_counts["started"] or 0)
    closed = int(cycle_counts["closed"] or 0)
    ready = int(report_counts["ready"] or 0)
    return AdminDashboard(
        title="Сводный отчет",
        subtitle="Современные оценки организации и готовность результатов.",
        is_superadmin=scope.is_superadmin,
        metrics=[
            AdminMetricCard(label="Готовых отчётов", value=str(ready), delta="За всё время"),
            AdminMetricCard(label="Прохождение оценки", value=(f"Завершено {closed} из {started}"
                if started else "Оценки ещё не начинались"), delta="За всё время"),
        ],
        competency_average=[],
        insights=[],
        activity_points=[],
        activity_labels=[],
        activity_axis_max=1,
        activity_period_key="30d",
        activity_period_label="",
    )



def _build_admin_methodology(connection) -> AdminMethodologyResponse:
    metrics_row = connection.execute(
        """
        SELECT
            COUNT(*)::int AS total_cases,
            COUNT(*) FILTER (WHERE status = 'ready')::int AS ready_cases,
            COUNT(*) FILTER (WHERE status = 'draft')::int AS draft_cases,
            COUNT(*) FILTER (
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM case_registry_roles crr
                    WHERE crr.cases_registry_id = cr.id
                )
            )::int AS cases_without_roles
        FROM cases_registry cr
        """
    ).fetchone()

    passports_rows = connection.execute(
        """
        SELECT
            ctp.id,
            ctp.type_code,
            ctp.type_name,
            ctp.status,
            cra.artifact_name,
            ctp.interactivity_mode,
            ctp.recommended_answer_length,
            ctp.selection_tags,
            COUNT(DISTINCT cr.id) FILTER (WHERE cr.status = 'ready')::int AS ready_cases_count,
            COUNT(DISTINCT crrb.id)::int AS required_blocks_count,
            COUNT(DISTINCT ctrf.id)::int AS red_flags_count,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.name ORDER BY r.name), NULL) AS role_names
        FROM case_type_passports ctp
        JOIN case_response_artifacts cra ON cra.id = ctp.artifact_id
        LEFT JOIN cases_registry cr ON cr.case_type_passport_id = ctp.id
        LEFT JOIN case_required_response_blocks crrb ON crrb.case_type_passport_id = ctp.id
        LEFT JOIN case_type_red_flags ctrf ON ctrf.case_type_passport_id = ctp.id AND ctrf.is_active = TRUE
        LEFT JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
        LEFT JOIN roles r ON r.id = crr.role_id
        GROUP BY ctp.id, ctp.type_code, ctp.type_name, ctp.status, cra.artifact_name, ctp.interactivity_mode, ctp.recommended_answer_length, ctp.selection_tags
        ORDER BY ctp.type_code ASC
        """
    ).fetchall()

    case_rows = connection.execute(
        """
        SELECT
            cr.id,
            cr.case_id_code,
            cr.title,
            ctp.type_code,
            cr.status,
            cr.difficulty_level,
            cr.estimated_time_min,
            cr.stakeholders_text,
            ctp.interactivity_mode,
            ctp.recommended_answer_length,
            txt.expected_artifact,
            ctp.selection_tags,
            COUNT(DISTINCT cqc.id) FILTER (WHERE cqc.passed)::int AS passed_checks,
            COUNT(DISTINCT cqc.id)::int AS total_checks,
            ARRAY_REMOVE(
                ARRAY_AGG(DISTINCT CASE WHEN cqc.passed = FALSE THEN COALESCE(cqc.comment, cqc.check_name) END),
                NULL
            ) AS failed_check_comments,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.name ORDER BY r.name), NULL) AS role_names,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT s.skill_name ORDER BY s.skill_name), NULL) AS skill_names
        FROM cases_registry cr
        JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
        LEFT JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
        LEFT JOIN roles r ON r.id = crr.role_id
        LEFT JOIN case_registry_skills crs ON crs.cases_registry_id = cr.id
        LEFT JOIN skills s ON s.id = crs.skill_id
        LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
        LEFT JOIN case_quality_checks cqc ON cqc.cases_registry_id = cr.id
        GROUP BY
            cr.id,
            cr.case_id_code,
            cr.title,
            ctp.type_code,
            cr.status,
            cr.difficulty_level,
            cr.estimated_time_min,
            cr.stakeholders_text,
            ctp.interactivity_mode,
            ctp.recommended_answer_length,
            txt.expected_artifact,
            ctp.selection_tags
        ORDER BY cr.updated_at DESC NULLS LAST, cr.id DESC
        """
    ).fetchall()

    branch_rows = connection.execute(
        """
        WITH role_case_stats AS (
            SELECT
                r.code AS role_code,
                r.name AS role_name,
                COUNT(DISTINCT cr.id)::int AS case_count,
                COUNT(DISTINCT cr.id) FILTER (WHERE cr.status = 'ready')::int AS ready_case_count
            FROM roles r
            LEFT JOIN case_registry_roles crr ON crr.role_id = r.id
            LEFT JOIN cases_registry cr ON cr.id = crr.cases_registry_id
            WHERE r.code IN ('linear_employee', 'manager', 'leader')
            GROUP BY r.code, r.name
        ),
        role_skill_stats AS (
            SELECT
                r.code AS role_code,
                COUNT(DISTINCT crs.skill_id)::int AS skill_count,
                COUNT(DISTINCT s.competency_name)::int AS competency_count
            FROM roles r
            LEFT JOIN case_registry_roles crr ON crr.role_id = r.id
            LEFT JOIN cases_registry cr ON cr.id = crr.cases_registry_id AND cr.status = 'ready'
            LEFT JOIN case_registry_skills crs ON crs.cases_registry_id = cr.id
            LEFT JOIN skills s ON s.id = crs.skill_id
            WHERE r.code IN ('linear_employee', 'manager', 'leader')
            GROUP BY r.code
        ),
        totals AS (
            SELECT
                COUNT(DISTINCT id)::int AS total_skills,
                COUNT(DISTINCT competency_name)::int AS total_competencies
            FROM skills
        )
        SELECT
            rcs.role_name,
            rcs.case_count,
            rcs.ready_case_count,
            CASE
                WHEN totals.total_skills > 0 THEN ROUND(COALESCE(rss.skill_count, 0)::numeric / totals.total_skills * 100)
                ELSE 0
            END::int AS skill_coverage_percent,
            CASE
                WHEN totals.total_competencies > 0 THEN ROUND(COALESCE(rss.competency_count, 0)::numeric / totals.total_competencies * 100)
                ELSE 0
            END::int AS competency_coverage_percent
        FROM role_case_stats rcs
        LEFT JOIN role_skill_stats rss ON rss.role_code = rcs.role_code
        CROSS JOIN totals
        ORDER BY
            CASE rcs.role_name
                WHEN 'Линейный сотрудник' THEN 1
                WHEN 'Менеджер' THEN 2
                WHEN 'Лидер' THEN 3
                ELSE 10
            END
        """
    ).fetchall()

    coverage_rows = connection.execute(
        """
        SELECT
            s.competency_name,
            COUNT(DISTINCT CASE WHEN r.code = 'linear_employee' THEN cr.id END)::int AS linear_value,
            COUNT(DISTINCT CASE WHEN r.code = 'manager' THEN cr.id END)::int AS manager_value,
            COUNT(DISTINCT CASE WHEN r.code = 'leader' THEN cr.id END)::int AS leader_value
        FROM skills s
        LEFT JOIN case_registry_skills crs ON crs.skill_id = s.id
        LEFT JOIN cases_registry cr ON cr.id = crs.cases_registry_id AND cr.status = 'ready'
        LEFT JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
        LEFT JOIN roles r ON r.id = crr.role_id
        GROUP BY s.competency_name
        ORDER BY s.competency_name
        """
    ).fetchall()

    skill_gap_rows = connection.execute(
        """
        WITH role_skill_grid AS (
            SELECT
                r.id AS role_id,
                r.name AS role_name,
                s.id AS skill_id,
                s.skill_name,
                s.competency_name
            FROM roles r
            CROSS JOIN skills s
            WHERE r.code IN ('linear_employee', 'manager', 'leader')
        ),
        ready_case_skill_counts AS (
            SELECT
                crr.role_id,
                crs.skill_id,
                COUNT(DISTINCT cr.id)::int AS ready_case_count
            FROM cases_registry cr
            JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
            JOIN case_registry_skills crs ON crs.cases_registry_id = cr.id
            WHERE cr.status = 'ready'
            GROUP BY crr.role_id, crs.skill_id
        )
        SELECT
            rsg.role_name,
            rsg.skill_name,
            rsg.competency_name,
            COALESCE(rcsc.ready_case_count, 0)::int AS ready_case_count,
            CASE
                WHEN COALESCE(rcsc.ready_case_count, 0) = 0 THEN 'critical'
                WHEN COALESCE(rcsc.ready_case_count, 0) = 1 THEN 'warning'
                ELSE 'ok'
            END AS severity
        FROM role_skill_grid rsg
        LEFT JOIN ready_case_skill_counts rcsc
            ON rcsc.role_id = rsg.role_id
           AND rcsc.skill_id = rsg.skill_id
        WHERE COALESCE(rcsc.ready_case_count, 0) <= 1
        ORDER BY
            CASE
                WHEN COALESCE(rcsc.ready_case_count, 0) = 0 THEN 1
                ELSE 2
            END,
            rsg.role_name ASC,
            rsg.competency_name ASC,
            rsg.skill_name ASC
        LIMIT 12
        """
    ).fetchall()

    single_point_rows = connection.execute(
        """
        WITH ready_skill_type_role AS (
            SELECT
                s.id AS skill_id,
                s.skill_name,
                s.competency_name,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.name ORDER BY r.name), NULL) AS role_names,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT ctp.type_code ORDER BY ctp.type_code), NULL) AS type_codes,
                COUNT(DISTINCT cr.id)::int AS ready_case_count,
                COUNT(DISTINCT ctp.type_code)::int AS type_count
            FROM skills s
            JOIN case_registry_skills crs ON crs.skill_id = s.id
            JOIN cases_registry cr ON cr.id = crs.cases_registry_id AND cr.status = 'ready'
            JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
            JOIN roles r ON r.id = crr.role_id
            JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
            WHERE r.code IN ('linear_employee', 'manager', 'leader')
            GROUP BY s.id, s.skill_name, s.competency_name
        )
        SELECT
            skill_name,
            competency_name,
            role_names,
            type_codes,
            ready_case_count
        FROM ready_skill_type_role
        WHERE type_count <= 1
        ORDER BY ready_case_count ASC, competency_name ASC, skill_name ASC
        LIMIT 10
        """
    ).fetchall()

    case_quality_rows = connection.execute(
        """
        WITH skill_case_quality AS (
            SELECT
                sc.case_registry_id,
                cr.case_id_code,
                cr.title,
                ctp.type_code,
                COUNT(*)::int AS assessments_count,
                AVG(
                    CASE
                        WHEN ssa.red_flags ~ '^\\s*\\[' THEN jsonb_array_length(ssa.red_flags::jsonb)::numeric
                        ELSE 0::numeric
                    END
                ) AS avg_red_flag_count,
                AVG(
                    CASE
                        WHEN ssa.missing_required_blocks ~ '^\\s*\\[' THEN jsonb_array_length(ssa.missing_required_blocks::jsonb)::numeric
                        ELSE 0::numeric
                    END
                ) AS avg_missing_blocks_count,
                AVG(ssa.block_coverage_percent::numeric) FILTER (WHERE ssa.block_coverage_percent IS NOT NULL) AS avg_block_coverage_percent,
                ROUND(
                    AVG(
                        CASE
                            WHEN ssa.assessed_level_code IN ('N/A', 'L1') THEN 100::numeric
                            ELSE 0::numeric
                        END
                    )
                )::int AS low_level_rate_percent
            FROM session_skill_assessments ssa
            JOIN session_cases sc ON sc.session_id = ssa.session_id
            JOIN cases_registry cr ON cr.id = sc.case_registry_id
            JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
            GROUP BY sc.case_registry_id, cr.case_id_code, cr.title, ctp.type_code
        )
        SELECT
            case_id_code,
            title,
            type_code,
            assessments_count,
            ROUND(COALESCE(avg_red_flag_count, 0), 2) AS avg_red_flag_count,
            ROUND(COALESCE(avg_missing_blocks_count, 0), 2) AS avg_missing_blocks_count,
            ROUND(avg_block_coverage_percent, 2) AS avg_block_coverage_percent,
            low_level_rate_percent,
            CASE
                WHEN COALESCE(avg_red_flag_count, 0) >= 2 THEN 'Часто срабатывают red flags'
                WHEN COALESCE(avg_missing_blocks_count, 0) >= 1 THEN 'Часто не добираются обязательные блоки'
                WHEN low_level_rate_percent >= 70 THEN 'Кейс часто дает низкие уровни'
                WHEN avg_block_coverage_percent IS NOT NULL AND avg_block_coverage_percent < 50 THEN 'Низкое покрытие структуры ответа'
                ELSE 'Требует наблюдения'
            END AS issue_label
        FROM skill_case_quality
        WHERE assessments_count > 0
        ORDER BY
            COALESCE(avg_red_flag_count, 0) DESC,
            COALESCE(avg_missing_blocks_count, 0) DESC,
            low_level_rate_percent DESC,
            assessments_count DESC,
            case_id_code ASC
        LIMIT 8
        """
    ).fetchall()

    total_cases = int(metrics_row["total_cases"] or 0)
    ready_cases = int(metrics_row["ready_cases"] or 0)
    draft_cases = int(metrics_row["draft_cases"] or 0)
    cases_without_roles = int(metrics_row["cases_without_roles"] or 0)
    ready_rate = round((ready_cases / total_cases) * 100) if total_cases else 0

    qa_ready_count = 0
    methodology_cases: list[AdminMethodologyCaseItem] = []
    for row in case_rows:
        passed_checks = int(row["passed_checks"] or 0)
        total_checks = int(row["total_checks"] or 0)
        qa_ready = total_checks > 0 and passed_checks == total_checks
        if qa_ready:
            qa_ready_count += 1
        methodology_cases.append(
            AdminMethodologyCaseItem(
                case_id_code=row["case_id_code"],
                title=row["title"] or "Без названия",
                type_code=row["type_code"] or "—",
                status=row["status"] or "draft",
                difficulty_level=row["difficulty_level"] or "base",
                estimated_time_min=int(row["estimated_time_min"]) if row["estimated_time_min"] is not None else None,
                roles=[str(item) for item in (row["role_names"] or []) if item],
                skills=[str(item) for item in (row["skill_names"] or []) if item],
                stakeholders_text=row["stakeholders_text"],
                interactivity_mode=row["interactivity_mode"],
                recommended_answer_length=row["recommended_answer_length"],
                expected_artifact=row["expected_artifact"],
                selection_tags=[str(item) for item in (row["selection_tags"] or []) if item],
                qa_ready=qa_ready,
                passed_checks=passed_checks,
                total_checks=total_checks,
                qa_blockers=[str(item) for item in (row["failed_check_comments"] or []) if item],
            )
        )

    methodology_passports = [
        AdminMethodologyPassportItem(
            type_code=row["type_code"],
            type_name=row["type_name"],
            artifact_name=row["artifact_name"],
            status=row["status"],
            ready_cases_count=int(row["ready_cases_count"] or 0),
            required_blocks_count=int(row["required_blocks_count"] or 0),
            red_flags_count=int(row["red_flags_count"] or 0),
            roles=[str(item) for item in (row["role_names"] or []) if item],
            interactivity_mode=row["interactivity_mode"],
            recommended_answer_length=row["recommended_answer_length"],
            selection_tags=[str(item) for item in (row["selection_tags"] or []) if item],
        )
        for row in passports_rows
    ]

    methodology_branches = [
        AdminMethodologyBranchItem(
            role_name=row["role_name"] or "Без роли",
            case_count=int(row["case_count"] or 0),
            ready_case_count=int(row["ready_case_count"] or 0),
            skill_coverage_percent=int(row["skill_coverage_percent"] or 0),
            competency_coverage_percent=int(row["competency_coverage_percent"] or 0),
        )
        for row in branch_rows
    ]

    methodology_coverage = [
        AdminMethodologyCoverageRow(
            competency_name=row["competency_name"] or "Без категории",
            linear_value=int(row["linear_value"] or 0),
            manager_value=int(row["manager_value"] or 0),
            leader_value=int(row["leader_value"] or 0),
        )
        for row in coverage_rows
    ]
    methodology_skill_gaps = [
        AdminMethodologySkillGapItem(
            role_name=row["role_name"] or "Без роли",
            skill_name=row["skill_name"] or "Без навыка",
            competency_name=row["competency_name"] or "Без категории",
            ready_case_count=int(row["ready_case_count"] or 0),
            severity=row["severity"] or "warning",
        )
        for row in skill_gap_rows
    ]
    methodology_single_point_skills = [
        AdminMethodologySinglePointSkillItem(
            skill_name=row["skill_name"] or "Без навыка",
            competency_name=row["competency_name"] or "Без категории",
            role_names=[str(item) for item in (row["role_names"] or []) if item],
            type_codes=[str(item) for item in (row["type_codes"] or []) if item],
            ready_case_count=int(row["ready_case_count"] or 0),
        )
        for row in single_point_rows
    ]
    methodology_case_quality_hotspots = [
        AdminMethodologyCaseQualityItem(
            case_id_code=row["case_id_code"],
            title=row["title"] or "Без названия",
            type_code=row["type_code"] or "—",
            assessments_count=int(row["assessments_count"] or 0),
            avg_red_flag_count=float(row["avg_red_flag_count"] or 0),
            avg_missing_blocks_count=float(row["avg_missing_blocks_count"] or 0),
            avg_block_coverage_percent=float(row["avg_block_coverage_percent"]) if row["avg_block_coverage_percent"] is not None else None,
            low_level_rate_percent=int(row["low_level_rate_percent"] or 0),
            issue_label=row["issue_label"] or "Требует наблюдения",
        )
        for row in case_quality_rows
    ]

    return AdminMethodologyResponse(
        title="Управление кейсами",
        subtitle="Библиотека кейсов, ветки тестирования и методическая готовность базы.",
        metrics=[
            AdminMetricCard(label="Всего кейсов", value=str(total_cases), delta=f"{ready_cases} готовы к использованию"),
            AdminMetricCard(label="Активные", value=str(ready_cases), delta=f"{ready_rate}% базы"),
            AdminMetricCard(label="Черновики", value=str(draft_cases), delta="Требуют доработки"),
            AdminMetricCard(label="QA готовность", value=str(qa_ready_count), delta=f"{cases_without_roles} без ролей"),
        ],
        branches=methodology_branches,
        coverage=methodology_coverage,
        skill_gaps=methodology_skill_gaps,
        single_point_skills=methodology_single_point_skills,
        case_quality_hotspots=methodology_case_quality_hotspots,
        passports=methodology_passports,
        cases=methodology_cases,
    )


def _build_admin_methodology_case_detail(connection, case_id_code: str) -> AdminMethodologyCaseDetailResponse:
    case_row = connection.execute(
        """
        SELECT
            cr.id,
            cr.case_id_code,
            cr.title,
            ctp.type_code,
            ctp.type_name,
            cra.artifact_name,
            cra.description AS artifact_description,
            cr.stakeholders_text,
            ctp.interactivity_mode,
            ctp.recommended_answer_length,
            ctp.selection_tags,
            ctp.role_personalization_rules,
            ctp.format_control_rules,
            ctp.scoring_aggregation_rules,
            ctp.bad_case_risks,
            ctp.generation_notes,
            ctp.status AS passport_status,
            cr.status AS case_status,
            txt.status AS case_text_status,
            cr.status,
            cr.difficulty_level,
            cr.estimated_time_min,
            cr.trigger_event,
            txt.intro_context,
            txt.facts_data,
            txt.participants_roles,
            txt.trigger_details,
            txt.task_for_user,
            txt.expected_artifact,
            txt.answer_structure_hint,
            txt.constraints_text,
            txt.dialog_turns_hint,
            txt.stakes_text,
            txt.personalization_variables,
            txt.personalization_options,
            txt.difficulty_toggles,
            txt.evaluation_notes,
            txt.author_name,
            txt.reviewer_name,
            txt.methodologist_comment,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.id ORDER BY r.id), NULL) AS role_ids,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT r.name ORDER BY r.name), NULL) AS role_names,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT s.id ORDER BY s.id), NULL) AS skill_ids,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT s.skill_name ORDER BY s.skill_name), NULL) AS skill_names
        FROM cases_registry cr
        JOIN case_type_passports ctp ON ctp.id = cr.case_type_passport_id
        JOIN case_response_artifacts cra ON cra.id = ctp.artifact_id
        LEFT JOIN case_texts txt ON txt.cases_registry_id = cr.id
        LEFT JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
        LEFT JOIN roles r ON r.id = crr.role_id
        LEFT JOIN case_registry_skills crs ON crs.cases_registry_id = cr.id
        LEFT JOIN skills s ON s.id = crs.skill_id
        WHERE cr.case_id_code = %s
        GROUP BY
            cr.id,
            cr.case_id_code,
            cr.title,
            ctp.type_code,
            ctp.type_name,
            cra.artifact_name,
            cra.description,
            cr.stakeholders_text,
            ctp.interactivity_mode,
            ctp.recommended_answer_length,
            ctp.selection_tags,
            ctp.role_personalization_rules,
            ctp.format_control_rules,
            ctp.scoring_aggregation_rules,
            ctp.bad_case_risks,
            ctp.generation_notes,
            ctp.status,
            txt.status,
            cr.status,
            cr.difficulty_level,
            cr.estimated_time_min,
            cr.trigger_event,
            txt.intro_context,
            txt.facts_data,
            txt.participants_roles,
            txt.trigger_details,
            txt.task_for_user,
            txt.expected_artifact,
            txt.answer_structure_hint,
            txt.constraints_text,
            txt.dialog_turns_hint,
            txt.stakes_text,
            txt.personalization_variables,
            txt.personalization_options,
            txt.difficulty_toggles,
            txt.evaluation_notes,
            txt.author_name,
            txt.reviewer_name,
            txt.methodologist_comment
        LIMIT 1
        """,
        (case_id_code,),
    ).fetchone()
    if case_row is None:
        raise HTTPException(status_code=404, detail="Case not found")

    quality_rows = connection.execute(
        """
        SELECT check_code, check_name, passed, comment
        FROM case_quality_checks
        WHERE cases_registry_id = %s
        ORDER BY check_name ASC, check_code ASC
        """,
        (case_row["id"],),
    ).fetchall()
    qa_blockers = [str(row["comment"] or row["check_name"]) for row in quality_rows if row["passed"] is False]

    response_block_rows = connection.execute(
        """
        SELECT block_name
        FROM case_required_response_blocks
        WHERE case_type_passport_id = (
            SELECT case_type_passport_id
            FROM cases_registry
            WHERE id = %s
        )
        ORDER BY display_order ASC, block_name ASC
        """,
        (case_row["id"],),
    ).fetchall()

    red_flag_rows = connection.execute(
        """
        SELECT flag_name
        FROM case_type_red_flags
        WHERE case_type_passport_id = (
            SELECT case_type_passport_id
            FROM cases_registry
            WHERE id = %s
        )
          AND is_active = TRUE
        ORDER BY severity DESC, flag_name ASC
        """,
        (case_row["id"],),
    ).fetchall()

    personalization_rows = connection.execute(
        """
        SELECT field_code, field_name, description, source_type, is_required
        FROM case_personalization_fields
        ORDER BY
            CASE source_type
                WHEN 'from_user_profile' THEN 0
                WHEN 'hybrid' THEN 1
                ELSE 2
            END,
            field_name ASC
        """,
    ).fetchall()

    personalization_option_map = {
        _normalize_admin_personalization_field_code(row["field_code"]): row
        for row in personalization_rows
        if _normalize_admin_personalization_field_code(row["field_code"])
    }
    personalization_codes = _extract_admin_personalization_codes(
        case_row["intro_context"],
        case_row["facts_data"],
        case_row["task_for_user"],
        case_row["constraints_text"],
        case_row["personalization_variables"],
    )
    personalization_codes = list(
        dict.fromkeys(
            [
                *personalization_codes,
                *[
                    _normalize_admin_personalization_field_code(item)
                    for item in (case_row["personalization_variables"] or "").split(",")
                ],
            ]
        )
    )

    skill_signal_rows = connection.execute(
        """
        SELECT
            s.skill_name,
            s.competency_name,
            ctse.related_response_block_code,
            ctse.evidence_description,
            ctse.expected_signal
        FROM case_type_skill_evidence ctse
        JOIN skills s ON s.id = ctse.skill_id
        WHERE ctse.case_type_passport_id = (
            SELECT case_type_passport_id
            FROM cases_registry
            WHERE id = %s
        )
        ORDER BY s.competency_name ASC, s.skill_name ASC
        """,
        (case_row["id"],),
    ).fetchall()

    role_option_rows = connection.execute(
        """
        SELECT id, code, name
        FROM roles
        WHERE code IN ('linear_employee', 'manager', 'leader')
        ORDER BY
            CASE code
                WHEN 'linear_employee' THEN 1
                WHEN 'manager' THEN 2
                WHEN 'leader' THEN 3
                ELSE 99
            END,
            name ASC
        """
    ).fetchall()

    skill_option_rows = connection.execute(
        """
        SELECT id, skill_code, skill_name, competency_name
        FROM skills
        ORDER BY competency_name ASC, skill_name ASC
        """
    ).fetchall()
    change_log_rows = connection.execute(
        """
        SELECT created_at, changed_by, entity_scope, action, summary
        FROM case_methodology_change_log
        WHERE case_registry_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT 12
        """,
        (case_row["id"],),
    ).fetchall()
    methodology_versions = get_case_methodology_versions(connection, int(case_row["id"]))

    return AdminMethodologyCaseDetailResponse(
        case_id_code=case_row["case_id_code"],
        title=case_row["title"] or "Без названия",
        case_registry_version=methodology_versions["case_registry_version"],
        case_text_version=methodology_versions["case_text_version"],
        case_type_passport_version=methodology_versions["case_type_passport_version"],
        required_blocks_version=methodology_versions["required_blocks_version"],
        red_flags_version=methodology_versions["red_flags_version"],
        skill_evidence_version=methodology_versions["skill_evidence_version"],
        difficulty_modifiers_version=methodology_versions["difficulty_modifiers_version"],
        personalization_fields_version=methodology_versions["personalization_fields_version"],
        type_code=case_row["type_code"] or "—",
        type_name=case_row["type_name"] or "Тип не указан",
        artifact_name=case_row["artifact_name"] or "Артефакт не указан",
        artifact_description=case_row["artifact_description"],
        stakeholders_text=case_row["stakeholders_text"],
        interactivity_mode=case_row["interactivity_mode"],
        recommended_answer_length=case_row["recommended_answer_length"],
        selection_tags=[str(item) for item in (case_row["selection_tags"] or []) if item],
        role_personalization_rules=case_row["role_personalization_rules"],
        format_control_rules=case_row["format_control_rules"],
        scoring_aggregation_rules=case_row["scoring_aggregation_rules"],
        bad_case_risks=case_row["bad_case_risks"],
        generation_notes=case_row["generation_notes"],
        passport_status=case_row["passport_status"] or "draft",
        case_status=case_row["case_status"] or "draft",
        case_text_status=case_row["case_text_status"] or "draft",
        status=case_row["status"] or "draft",
        difficulty_level=case_row["difficulty_level"] or "base",
        estimated_time_min=int(case_row["estimated_time_min"]) if case_row["estimated_time_min"] is not None else None,
        roles=[str(item) for item in (case_row["role_names"] or []) if item],
        skills=[str(item) for item in (case_row["skill_names"] or []) if item],
        intro_context=case_row["intro_context"],
        facts_data=case_row["facts_data"],
        participants_roles=case_row["participants_roles"],
        trigger_event=case_row["trigger_event"],
        trigger_details=case_row["trigger_details"],
        task_for_user=case_row["task_for_user"],
        expected_artifact=case_row["expected_artifact"],
        answer_structure_hint=case_row["answer_structure_hint"],
        constraints_text=case_row["constraints_text"],
        dialog_turns_hint=case_row["dialog_turns_hint"],
        stakes_text=case_row["stakes_text"],
        personalization_variables=case_row["personalization_variables"],
        personalization_options_text=case_row["personalization_options"],
        difficulty_toggles=case_row["difficulty_toggles"],
        evaluation_notes=case_row["evaluation_notes"],
        author_name=case_row["author_name"],
        reviewer_name=case_row["reviewer_name"],
        methodologist_comment=case_row["methodologist_comment"],
        personalization_fields=[
            (
                str(personalization_option_map[code]["field_name"])
                if code in personalization_option_map and personalization_option_map[code]["field_name"]
                else _humanize_admin_personalization_field_label(code)
            )
            for code in personalization_codes
        ],
        required_blocks=[str(row["block_name"]) for row in response_block_rows if row["block_name"]],
        red_flags=[str(row["flag_name"]) for row in red_flag_rows if row["flag_name"]],
        qa_blockers=qa_blockers,
        quality_checks=[
            AdminMethodologyChecklistItem(
                code=row["check_code"],
                name=row["check_name"],
                passed=bool(row["passed"]),
                comment=row["comment"],
            )
            for row in quality_rows
        ],
        skill_signals=[
            AdminMethodologySkillSignalItem(
                skill_name=row["skill_name"],
                competency_name=row["competency_name"] or "Без категории",
                related_response_block_code=row["related_response_block_code"],
                evidence_description=row["evidence_description"],
                expected_signal=row["expected_signal"],
            )
            for row in skill_signal_rows
        ],
        selected_role_ids=[int(item) for item in (case_row["role_ids"] or []) if item is not None],
        selected_skill_ids=[int(item) for item in (case_row["skill_ids"] or []) if item is not None],
        role_options=[
            AdminMethodologyRoleOption(
                id=int(row["id"]),
                code=row["code"],
                name=row["name"],
            )
            for row in role_option_rows
        ],
        skill_options=[
            AdminMethodologySkillOption(
                id=int(row["id"]),
                skill_code=row["skill_code"],
                skill_name=row["skill_name"],
                competency_name=row["competency_name"],
            )
            for row in skill_option_rows
        ],
        personalization_options=[
            AdminMethodologyPersonalizationOption(
                field_code=str(row["field_code"]),
                field_name=str(row["field_name"]),
                description=row["description"],
                source_type=str(row["source_type"]),
                is_required=bool(row["is_required"]),
            )
            for row in personalization_rows
        ],
        personalization_items=[
            AdminMethodologyPersonalizationValueItem(
                field_code=code,
                field_label=(
                    str(personalization_option_map[code]["field_name"])
                    if code in personalization_option_map and personalization_option_map[code]["field_name"]
                    else _humanize_admin_personalization_field_label(code)
                ),
                field_value_template=None,
                description=(
                    str(personalization_option_map[code]["description"])
                    if code in personalization_option_map and personalization_option_map[code]["description"]
                    else None
                ),
                source_type=(
                    str(personalization_option_map[code]["source_type"])
                    if code in personalization_option_map and personalization_option_map[code]["source_type"]
                    else "static"
                ),
                is_required=(
                    bool(personalization_option_map[code]["is_required"])
                    if code in personalization_option_map
                    else False
                ),
                display_order=index,
            )
            for index, code in enumerate(personalization_codes, start=1)
        ],
        change_log=[
            AdminMethodologyChangeLogItem(
                changed_at=row["created_at"],
                changed_by=row["changed_by"] or "Система",
                entity_scope=row["entity_scope"],
                action=row["action"],
                summary=row["summary"],
            )
            for row in change_log_rows
        ],
    )


def _set_user_session_cookie(response: FastAPIResponse, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.auth_session_secure_cookie,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


def _clear_user_session_cookie(response: FastAPIResponse) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _public_invitation_by_token(token: str | None) -> OrganizationInvitationPublicResponse | None:
    if not token:
        return None
    with get_connection() as connection:
        invitation = resolve_invitation(connection, token=token)
    return OrganizationInvitationPublicResponse(**invitation_public_context(invitation))


def _public_invitation_by_id(invitation_id: int | None) -> OrganizationInvitationPublicResponse | None:
    if invitation_id is None:
        return None
    try:
        with get_connection() as connection:
            invitation = resolve_invitation_by_id(
                connection,
                invitation_id=invitation_id,
                allow_used=True,
            )
    except OrganizationInvitationError:
        return None
    return OrganizationInvitationPublicResponse(**invitation_public_context(invitation))


def _organization_context_for_user(
    connection,
    user_id: int,
    preferred_organization_id: int | None = None,
) -> OrganizationInvitationPublicResponse | None:
    row = connection.execute(
        """
        SELECT organization.id, organization.name, organization.invitation_intro
        FROM organization_memberships membership
        JOIN organizations organization ON organization.id = membership.organization_id
        WHERE membership.user_id = %s
          AND (%s::BIGINT IS NULL OR organization.id = %s::BIGINT)
          AND organization.is_active = TRUE
          AND (
            membership.role = 'admin'
            OR membership.admission_source IN ('admin_add', 'csv_import')
          )
        LIMIT 2
        """,
        (user_id, preferred_organization_id, preferred_organization_id),
    ).fetchall()
    if len(row) != 1:
        return None
    return OrganizationInvitationPublicResponse(
        organization_id=int(row[0]["id"]),
        organization_name=str(row[0]["name"]),
        invitation_intro=str(row[0]["invitation_intro"] or "").strip() or None,
        expires_at=None,
    )


def _build_authenticated_user_response(
    *,
    connection,
    user: UserResponse,
    response: FastAPIResponse,
    login_identifier: str,
    is_new_user: bool,
    organization_invitation_id: int | None = None,
) -> CheckOrCreateUserResponse:
    compact_user = _compact_user_response(user)
    assign_user_organization_from_email(connection, user_id=user.id, email=user.email)
    admin_scope = _get_admin_scope_or_403(connection, user) if _is_admin_user(connection, user) else AdminScope()
    preferred_organization_id = None
    if organization_invitation_id is not None:
        selected = connection.execute(
            """
            SELECT invitation.organization_id
            FROM organization_invitations invitation
            JOIN organization_memberships membership
              ON membership.organization_id = invitation.organization_id
             AND membership.user_id = %s
            JOIN organizations organization ON organization.id = invitation.organization_id
            WHERE invitation.id = %s
              AND invitation.purpose = 'personal_registration'
              AND LOWER(invitation.recipient_email) = LOWER(%s)
              AND organization.is_active = TRUE
              AND (membership.role = 'admin' OR membership.admission_source IN ('admin_add', 'csv_import'))
              AND (
                invitation.used_at IS NOT NULL
                OR (invitation.revoked_at IS NULL AND invitation.expires_at > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'))
              )
            LIMIT 1
            """,
            (user.id, organization_invitation_id, user.email),
        ).fetchone()
        preferred_organization_id = int(selected["organization_id"]) if selected else None
    organization = _organization_context_for_user(connection, user.id, preferred_organization_id)
    _set_user_session_cookie(
        response,
        web_session_service.create_session(user.id, selected_organization_id=preferred_organization_id),
    )

    if admin_scope.can_admin:
        return CheckOrCreateUserResponse(
            exists=True,
            message="Выполнен вход в административный раздел.",
            user=compact_user,
            requires_user_data=False,
            agent=AgentReply(
                session_id="admin-session",
                message="Выполнен вход администратора.",
                stage="admin",
                completed=True,
                user=compact_user,
            ),
            is_admin=True,
            admin_dashboard=_build_admin_dashboard(connection, admin_scope),
            organization=organization,
        )

    managed_assignment = assessment_assignment_sources.has_managed_assignment(connection, user_id=int(user.id))
    agent = (AgentReply(session_id='acquaintance-session', stage='acquaintance', completed=False,
                        message='Продолжите знакомство с назначенной оценкой.', user=compact_user)
        if managed_assignment else interviewer_agent.start(
            login_identifier=login_identifier, user=user, bootstrap_user_id=user.id if is_new_user else None))
    agent = agent.model_copy(update={"user": compact_user})
    return CheckOrCreateUserResponse(
        exists=not is_new_user,
        message="Пользователь авторизован по email." if not is_new_user else "Email подтвержден. Продолжаем создание профиля.",
        user=compact_user,
        requires_user_data=is_new_user,
        agent=agent,
        dashboard=None if is_new_user else _build_dashboard(connection, user),
        organization=organization,
    )


@router.post("/check-or-create", response_model=CheckOrCreateUserResponse)
def check_or_create_user(payload: CheckOrCreateUserRequest, request: Request, response: FastAPIResponse) -> CheckOrCreateUserResponse:
    raise HTTPException(
        status_code=410,
        detail="Вход по номеру телефона отключен. Используйте авторизацию по email.",
    )


@router.post("/auth/email/request-link", response_model=AuthEmailRequestResponse)
def request_email_magic_link(payload: AuthEmailRequest, request: Request) -> AuthEmailRequestResponse:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    if not settings.auth_magic_link_dev_mode:
        try:
            email = normalize_email(payload.email)
            auth_mode = auth_service.get_password_auth_mode(
                email=email,
                organization_invitation_token=payload.organization_invitation_token,
            )
        except AuthAccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        is_registration = auth_mode == "password_registration"
        if is_registration and settings.auth_email_verification_required:
            try:
                action_result = auth_service.create_auth_action_request(
                    email=email,
                    purpose="email_verification",
                    organization_invitation_token=payload.organization_invitation_token,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
            except AuthRateLimitError as exc:
                headers = ({"Retry-After":str(exc.retry_after_seconds)}
                           if exc.retry_after_seconds is not None else None)
                raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            return AuthEmailRequestResponse(
                message="Отправили ссылку подтверждения. Проверьте почту.",
                email=email,
                expires_in_seconds=max(settings.auth_action_token_ttl_minutes * 60, 0),
                dev_mode=False,
                delivery_method=settings.email_provider or "email",
                auth_mode="verification_pending",
                dev_magic_token=action_result.dev_token,
                organization=_public_invitation_by_id(action_result.organization_invitation_id),
                server_time=action_result.server_time,
                next_request_at=action_result.next_request_at,
                retry_after_seconds=max(settings.auth_magic_link_resend_cooldown_seconds,0),
            )
        return AuthEmailRequestResponse(
            message="Задайте пароль для первичного входа." if is_registration else "Введите пароль для входа.",
            email=email,
            expires_in_seconds=0,
            dev_mode=False,
            delivery_method=auth_mode,
            auth_mode=auth_mode,
            dev_magic_token=None,
            organization=_public_invitation_by_token(payload.organization_invitation_token),
        )
    try:
        result = auth_service.create_magic_link_request(
            email=payload.email,
            organization_invitation_token=payload.organization_invitation_token,
            client_ip=client_ip,
            user_agent=user_agent,
        )
    except AuthAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AuthRateLimitError as exc:
        headers = ({"Retry-After":str(exc.retry_after_seconds)}
                   if exc.retry_after_seconds is not None else None)
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AuthEmailRequestResponse(
        message=(
            "Dev-режим: токен создан локально."
            if settings.auth_magic_link_dev_mode
            else "Если email доступен для входа, мы отправили одноразовую ссылку на почту."
        ),
        email=result.email,
        expires_in_seconds=max(int((result.expires_at - datetime.now(result.expires_at.tzinfo)).total_seconds()), 0),
        dev_mode=settings.auth_magic_link_dev_mode,
        delivery_method="dev-token" if settings.auth_magic_link_dev_mode else settings.email_provider or "email",
        auth_mode="dev_token" if settings.auth_magic_link_dev_mode else "magic_link",
        dev_magic_token=result.dev_magic_token,
        organization=_public_invitation_by_id(result.organization_invitation_id),
    )


def _build_password_auth_response(
    *,
    verification,
    response: FastAPIResponse,
) -> CheckOrCreateUserResponse:
    with get_connection() as connection:
        user = verification.user
        if not verification.is_new_user and not evaluate_profile_state(user).is_complete:
            repaired_user = interviewer_agent.backfill_user_profile(user.id)
            if repaired_user is not None:
                user = _strip_avatar(repaired_user)
        return _build_authenticated_user_response(
            connection=connection,
            user=user,
            response=response,
            login_identifier=verification.email,
            is_new_user=verification.is_new_user,
            organization_invitation_id=verification.organization_invitation_id,
        )


@router.post("/auth/email/password-register", response_model=CheckOrCreateUserResponse)
def register_email_password(
    payload: AuthPasswordRegisterRequest,
    response: FastAPIResponse,
) -> CheckOrCreateUserResponse:
    if settings.auth_magic_link_dev_mode:
        raise HTTPException(status_code=400, detail="В dev-режиме используйте одноразовый токен.")
    try:
        verification = auth_service.register_password(
            email=payload.email,
            password=payload.password,
            password_confirm=payload.password_confirm,
            verification_token=payload.verification_token,
            organization_invitation_token=payload.organization_invitation_token,
        )
    except AuthAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _build_password_auth_response(verification=verification, response=response)


@router.post("/auth/email/confirm", response_model=AuthActionResponse)
def confirm_registration_email(payload: AuthEmailVerifyRequest) -> AuthActionResponse:
    try:
        email, invitation_id = auth_service.verify_auth_action_token_details(
            token=payload.token,
            purpose="email_verification",
            consume=False,
        )
    except (AuthAccessDeniedError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthActionResponse(
        message="Email подтвержден. Задайте пароль.",
        email=email,
        auth_mode="password_registration",
        organization=_public_invitation_by_id(invitation_id),
    )


@router.post("/auth/password/forgot", response_model=AuthActionResponse)
def forgot_password(payload: AuthPasswordForgotRequest, request: Request) -> AuthActionResponse:
    neutral_message = "Если учетная запись существует, мы отправили ссылку для восстановления пароля."
    if not settings.auth_password_reset_enabled:
        raise HTTPException(status_code=404, detail="Восстановление пароля отключено.")
    try:
        action_result = auth_service.create_auth_action_request(
            email=payload.email,
            purpose="password_reset",
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except AuthRateLimitError as exc:
        action_result = None
        retry_after = exc.retry_after_seconds
    except (AuthAccessDeniedError, ValueError):
        action_result = None
        retry_after = max(settings.auth_magic_link_resend_cooldown_seconds,0)
    except RuntimeError as exc:
        logger.exception("Password reset email delivery failed")
        raise HTTPException(status_code=503, detail="Не удалось отправить письмо. Попробуйте позже.") from exc
    server_time = action_result.server_time if action_result is not None else datetime.now(timezone.utc)
    retry_after = (max(settings.auth_magic_link_resend_cooldown_seconds,0)
                   if action_result is not None else retry_after)
    return AuthActionResponse(
        message=neutral_message,
        dev_action_token=action_result.dev_token if action_result is not None else None,
        server_time=server_time,
        next_request_at=(action_result.next_request_at if action_result is not None
                         else server_time+timedelta(seconds=max(retry_after or 0,0))),
        retry_after_seconds=max(retry_after or 0,0),
    )


@router.post("/auth/password/reset/validate", response_model=AuthActionResponse)
def validate_password_reset_token(payload: AuthEmailVerifyRequest) -> AuthActionResponse:
    try:
        email = auth_service.verify_auth_action_token(token=payload.token, purpose="password_reset")
    except (AuthAccessDeniedError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthActionResponse(message="Ссылка действительна. Задайте новый пароль.", email=email, auth_mode="password_reset")


@router.post("/auth/password/reset", response_model=AuthActionResponse)
def reset_password(payload: AuthPasswordResetRequest) -> AuthActionResponse:
    try:
        email = auth_service.reset_password(
            token=payload.token,
            password=payload.password,
            password_confirm=payload.password_confirm,
        )
    except (AuthAccessDeniedError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthActionResponse(message="Пароль изменён. Теперь можно войти.", email=email, auth_mode="password")


@router.post("/auth/email/password-login", response_model=CheckOrCreateUserResponse)
def login_with_email_password(
    payload: AuthPasswordLoginRequest,
    response: FastAPIResponse,
) -> CheckOrCreateUserResponse:
    if settings.auth_magic_link_dev_mode:
        raise HTTPException(status_code=400, detail="В dev-режиме используйте одноразовый токен.")
    try:
        verification = auth_service.verify_password_login(
            email=payload.email,
            password=payload.password,
            organization_invitation_token=payload.organization_invitation_token,
        )
    except AuthAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _build_password_auth_response(verification=verification, response=response)


@router.post("/auth/email/verify", response_model=CheckOrCreateUserResponse)
def verify_email_magic_link(payload: AuthEmailVerifyRequest, response: FastAPIResponse) -> CheckOrCreateUserResponse:
    token = payload.token.strip()
    if "/auth/email/verify?token=" in token:
        token = token.split("/auth/email/verify?token=", 1)[1]
    if "token=" in token:
        token = token.split("token=", 1)[1]

    try:
        verification = auth_service.verify_magic_link(token=token)
    except AuthAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with get_connection() as connection:
        user = verification.user
        if not verification.is_new_user and not evaluate_profile_state(user).is_complete:
            repaired_user = interviewer_agent.backfill_user_profile(user.id)
            if repaired_user is not None:
                user = _strip_avatar(repaired_user)
        return _build_authenticated_user_response(
            connection=connection,
            user=user,
            response=response,
            login_identifier=verification.email,
            is_new_user=verification.is_new_user,
            organization_invitation_id=verification.organization_invitation_id,
        )


@router.get("/operations/{operation_id}", response_model=OperationProgressResponse)
def get_operation_progress(operation_id: str) -> OperationProgressResponse:
    snapshot = operation_progress_service.snapshot(operation_id)
    if snapshot is None:
        return OperationProgressResponse(
            operation_id=operation_id,
            title="Подготавливаем данные",
            message="Операция уже создается. Обновляем статус...",
            status="pending",
            current_step_index=0,
            progress_percent=5,
            steps=[
                OperationProgressStep(
                    label="Ожидание запуска",
                    description="Система подготавливает прогресс операции для отображения.",
                    status="active",
                )
            ],
        )
    return OperationProgressResponse(**snapshot)


@router.get("/session/restore", response_model=UserSessionRestoreResponse)
def restore_user_session(request: Request, personalized_profile_id: int | None = None) -> UserSessionRestoreResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        return UserSessionRestoreResponse(authenticated=False)
    full_user = _strip_avatar(user)
    compact_user = _compact_user_response(full_user)
    selected_organization_id = web_session_service.selected_organization_id(token)

    with get_connection() as connection:
        admin_scope = _get_admin_scope_or_403(connection, full_user) if _is_admin_user(connection, full_user) else AdminScope()
        if admin_scope.can_admin:
            return UserSessionRestoreResponse(
                authenticated=True,
                user=compact_user,
                is_admin=True,
                admin_dashboard=_build_admin_dashboard(connection, admin_scope),
                organization=_organization_context_for_user(connection, full_user.id, selected_organization_id),
            )
        return UserSessionRestoreResponse(
            authenticated=True,
            user=compact_user,
            dashboard=_build_dashboard(connection, full_user, profile_id=personalized_profile_id),
            organization=_organization_context_for_user(connection, full_user.id, selected_organization_id),
        )


@router.post("/session/reopen-profile", response_model=CheckOrCreateUserResponse)
def reopen_profile_session(request: Request, response: FastAPIResponse) -> CheckOrCreateUserResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия не найдена. Войдите заново.")
    with get_connection() as connection:
        _require_unmanaged_profile_path(connection, user_id=int(user.id))
        compact_user = _compact_user_response(user)
        _set_user_session_cookie(response, web_session_service.create_session(user.id))
        assign_user_organization_from_email(connection, user_id=user.id, email=user.email)
        admin_scope = _get_admin_scope_or_403(connection, user) if _is_admin_user(connection, user) else AdminScope()
        if admin_scope.can_admin:
            login_identifier = str(user.email or "").strip().lower()
            agent = interviewer_agent.start(
                login_identifier=login_identifier,
                user=user,
                bootstrap_user_id=None,
            )
            agent = agent.model_copy(update={"user": compact_user})
            return CheckOrCreateUserResponse(
                exists=True,
                message="Открыта актуализация профиля перед оцениванием.",
                user=compact_user,
                requires_user_data=False,
                agent=agent,
                is_admin=True,
                admin_dashboard=_build_admin_dashboard(connection, admin_scope),
            )
        return _build_authenticated_user_response(
            connection=connection,
            user=user,
            response=response,
            login_identifier=str(user.email or "").strip().lower(),
            is_new_user=False,
        )


@router.get("/{user_id}/session-bootstrap", response_model=UserSessionBootstrapResponse)
def bootstrap_user_session(user_id: int, request: Request, personalized_profile_id: int | None = None) -> UserSessionBootstrapResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        row = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="User not found")

        user = _user_response_from_row(row)
        admin_scope = _get_admin_scope_or_403(connection, user) if _is_admin_user(connection, user) else AdminScope()
        if admin_scope.can_admin:
            return UserSessionBootstrapResponse(
                user=_compact_user_response(user),
                dashboard=_build_dashboard(connection, user, profile_id=personalized_profile_id),
                is_admin=True,
                admin_dashboard=_build_admin_dashboard(connection, admin_scope),
            )
        return UserSessionBootstrapResponse(
            user=_compact_user_response(user),
            dashboard=_build_dashboard(connection, user, profile_id=personalized_profile_id),
        )


def _require_matching_session_user(request: Request, user_id: int) -> UserResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия не найдена. Войдите заново.")
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Нет доступа к состоянию другого пользователя.")
    return user


def _require_unmanaged_profile_path(connection, *, user_id: int) -> None:
    if assessment_assignment_sources.has_managed_assignment(connection, user_id=user_id):
        raise HTTPException(409, detail='W02_MANAGED_ASSIGNMENT: Продолжите знакомство; источники оценки назначает организация.')


def _require_assessment_session_owner(request: Request, session_code: str) -> UserResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия не найдена. Войдите заново.")
    with get_connection() as connection:
        session_row = connection.execute(
            "SELECT user_id FROM user_sessions WHERE session_code = %s LIMIT 1",
            (session_code,),
        ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    if int(session_row["user_id"]) != int(user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к состоянию другого пользователя.")
    return user


def _onboarding_response(payload: dict) -> OnboardingStateResponse:
    return OnboardingStateResponse(
        status=str(payload["status"]),
        current_step=int(payload["current_step"] or 0),
        started_at=payload.get("started_at"),
        completed_at=payload.get("completed_at"),
        skipped_at=payload.get("skipped_at"),
        updated_at=payload.get("updated_at"),
    )


@router.get("/{user_id}/journey-state", response_model=UserJourneyStateResponse)
def get_user_journey_state(user_id: int, request: Request, personalized_profile_id: int | None = None) -> UserJourneyStateResponse:
    from Api.qa_orchestration import usage_scope
    user = _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        onboarding = get_or_create_onboarding_state(connection, user_id)
        acquaintance_state = acquaintance.read_state(connection, user_id=user.id)
        early = acquaintance_state['readiness']
        assignment_scope = early.get('assignment_ref') if early.get('questionnaire_revision_id') is not None else None
        canonical_assignment = bool(assignment_scope) or assessment_assignment_sources.has_managed_assignment(
            connection, user_id=int(user.id))
        effective_profile_id = acquaintance_state['late_readiness'].get('personalized_profile_id')
        if not assignment_scope:
            effective_profile_id = personalized_profile_id or effective_profile_id
        profile = (participant_profile.readiness(connection, user_id=user.id, profile_id=effective_profile_id)
            if effective_profile_id is not None or not assignment_scope else
            {'status': 'not_ready', 'id': None, 'organization_id': early.get('organization_id')})
        cycle = connection.execute("""SELECT c.status,c.cycle_id,
            latest_as.assessment_situation_id,latest_as.as_status,latest_as.session_id
            FROM m5_cycles c
            JOIN assessment_personalized_profiles p ON p.id=c.personalized_profile_id
            LEFT JOIN LATERAL (
                SELECT s.assessment_situation_id,s.status AS as_status,cs.session_id
                FROM m5_assessment_situations s
                JOIN m5_cycle_sessions cs ON cs.id=s.session_db_id
                WHERE s.cycle_db_id=c.id
                ORDER BY s.created_at DESC,s.id DESC LIMIT 1
            ) latest_as ON TRUE
            WHERE c.owner_user_id=%s AND c.organization_id=%s AND c.usage_scope=%s
              AND ((%s::text IS NOT NULL AND EXISTS (
                     SELECT 1 FROM participant_acquaintance_confirmations confirmation
                     WHERE confirmation.personalized_profile_id=p.id AND confirmation.user_id=c.owner_user_id
                       AND confirmation.organization_id=c.organization_id AND confirmation.assignment_ref=%s)
                    AND (c.status<>'prepared' OR p.id=%s))
                   OR (%s::text IS NULL AND p.assessment_configuration_id=%s))
            ORDER BY c.created_at DESC,c.id DESC LIMIT 1""",
            (user.id, profile.get('organization_id') or early.get('organization_id'), usage_scope(),
             assignment_scope, assignment_scope, effective_profile_id, assignment_scope,
             profile.get('assessment_configuration_id'))).fetchone()
        connection.commit()
    ready = profile['status'] == 'ready'
    assessment_status = ({'prepared':'preparing','active':'in_progress','paused':'in_progress',
        'interrupted':'in_progress','collection_closed':'analyzing','calculation_pending':'analyzing',
        'calculated':'results_ready','failed':'failed'}.get(cycle['status'], 'not_started') if cycle else 'not_started')
    report_status = 'not_ready'
    if cycle:
        with get_connection() as connection:
            pipeline = connection.execute("""SELECT p.status FROM m10_pipeline_runs p
                JOIN m5_cycles c ON c.id=p.cycle_db_id WHERE c.cycle_id=%s""", (cycle['cycle_id'],)).fetchone()
            report = connection.execute("""SELECT r.status FROM m8_reports r
                JOIN m8_result_revisions rr ON rr.id=r.result_revision_id
                JOIN m8_results mr ON mr.id=rr.results_id
                JOIN m5_cycles c ON c.id=mr.cycle_db_id
                WHERE c.cycle_id=%s AND r.audience='assessee'
                ORDER BY r.revision_no DESC LIMIT 1""", (cycle['cycle_id'],)).fetchone()
        if pipeline and pipeline['status'] == 'failed':
            assessment_status = 'failed'
            report_status = 'limited' if report else 'not_ready'
        elif report and report['status'] == 'ready':
            assessment_status = 'report_ready'
            report_status = 'ready'
    if cycle and cycle['status'] == 'prepared' and canonical_assignment:
        next_action = 'show_onboarding'
    elif cycle:
        next_action = determine_cycle_next_action(
            profile_status='complete', onboarding_status=str(onboarding['status']),
            cycle_status=str(cycle['status']),
            assessment_situation_status=str(cycle['as_status']) if cycle['as_status'] else None,
        )
    elif acquaintance_state["readiness"]["status"] != "ready":
        next_action = "wait_for_acquaintance_data"
    elif not canonical_assignment and str(onboarding['status']) in {'completed', 'skipped'}:
        # Released, genuinely unmanaged M4 clients keep their confirmation route.
        # A modern assignment (including incomplete sources) never enters it.
        next_action = 'show_dashboard' if ready else 'complete_profile'
    else:
        # Acquaintance owns the participant's recovery, including old completed/skipped
        # flags with missing mandatory steps or late organizational dependencies.
        next_action = "show_onboarding"
    # A stored Cycle owns the confirmed M4 snapshot. Reading this projection must
    # not reopen M4 or mutate Cycle intervals/time budgets.
    return UserJourneyStateResponse(
        profile=ProfileStateResponse(status='complete' if ready else 'incomplete',
            missing_fields=[] if ready else ['personalized_profile']),
        onboarding=_onboarding_response(onboarding),
        assessment=JourneyAssessmentState(
            status=assessment_status,
            runtime_kind='cycle' if cycle else None,
            cycle_id=str(cycle['cycle_id']) if cycle else None,
            cycle_session_id=str(cycle['session_id']) if cycle and cycle['session_id'] else None,
            assessment_situation_id=(
                str(cycle['assessment_situation_id'])
                if cycle and cycle['assessment_situation_id'] else None
            ),
        ),
        report_status=report_status,
        next_action=next_action,
        can_open_dashboard=bool(acquaintance_state.get('mandatory_complete')
            and str(onboarding['status']) in {'completed', 'skipped'}),
        acquaintance=acquaintance_state,
    )


@router.put("/{user_id}/onboarding", response_model=OnboardingStateResponse)
def set_user_onboarding_state(
    user_id: int,
    payload: OnboardingStateUpdateRequest,
    request: Request,
) -> OnboardingStateResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        try:
            if payload.status in {'completed', 'skipped'}:
                current = acquaintance.read_state(connection, user_id=user_id)
                if not current.get('mandatory_complete'):
                    raise ValueError('W02_MANDATORY_STEPS_REQUIRED')
            onboarding = update_onboarding_state(
                connection,
                user_id,
                status=payload.status,
                current_step=payload.current_step,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        connection.commit()
    return _onboarding_response(onboarding)


@router.get("/{user_id}/acquaintance")
def get_participant_acquaintance(user_id: int, request: Request) -> dict:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        return acquaintance.read_state(connection, user_id=user_id)


@router.put("/{user_id}/acquaintance/answers")
def save_participant_acquaintance_answers(
    user_id: int, payload: AcquaintanceAnswersRequest, request: Request,
) -> dict:
    _require_matching_session_user(request, user_id)
    try:
        with get_connection() as connection:
            result = acquaintance.save_answers(
                connection, user_id=user_id, answers=payload.answers, confirm=payload.confirm,
            )
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{user_id}/acquaintance/consent")
def accept_participant_acquaintance_consent(
    user_id: int, payload: AcquaintanceConsentRequest, request: Request,
) -> dict:
    _require_matching_session_user(request, user_id)
    try:
        with get_connection() as connection:
            result = acquaintance.accept_consent(connection, user_id=user_id, version=payload.version)
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{user_id}/acquaintance/resolve-profile")
def resolve_participant_acquaintance_profile(user_id: int, request: Request) -> dict:
    _require_matching_session_user(request, user_id)
    try:
        with get_connection() as connection:
            acquaintance.resolve_confirmed_profile(connection, user_id=user_id)
            connection.commit()
            return acquaintance.read_state(connection, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{user_id}/acquaintance/issues", status_code=201)
def report_participant_data_issue(
    user_id: int, payload: AcquaintanceIssueRequest, request: Request,
) -> dict:
    _require_matching_session_user(request, user_id)
    try:
        with get_connection() as connection:
            result = acquaintance.report_issue(connection, user_id=user_id, message=payload.message,
                operation_id=payload.operation_id, assignment_id=payload.assignment_id,
                questionnaire_revision_id=payload.questionnaire_revision_id)
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{user_id}/acquaintance/issues/operations/{operation_id}")
def read_participant_issue_operation(user_id: int, operation_id: str, request: Request,
                                     assignment_id: int | None = None,
                                     questionnaire_revision_id: int | None = None) -> dict:
    _require_matching_session_user(request, user_id)
    try:
        with get_connection() as connection:
            result = appeals.read_operation(connection, user_id=user_id, operation_id=operation_id,
                assignment_id=assignment_id, questionnaire_revision_id=questionnaire_revision_id)
            if result is None:
                raise HTTPException(status_code=404, detail='ISSUE_OPERATION_NOT_FOUND')
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{user_id}/acquaintance/issues")
def list_participant_data_issues(user_id: int, request: Request) -> dict:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        visible = ("id", "organization_id", "message", "status", "created_at",
                   "assignment_ref", "assignment_id", "questionnaire_revision_id",
                   "reply_message", "reply_author_display_name", "replied_at")
        return {"items": [{key: item[key] for key in visible} for item in appeals.list_issues(
            connection, organization_id=None, user_id=user_id)]}


class AppealReplyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def _admin_member_issues_scope(connection, request: Request, organization_id: int, user_id: int) -> int:
    actor = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    scope = _require_organization_admin(connection, actor, organization_id)
    if not scope.is_superadmin:
        current_admin = connection.execute(
            "SELECT 1 FROM organization_memberships WHERE organization_id=%s AND user_id=%s AND role='admin' FOR SHARE",
            (organization_id, int(actor.id)),
        ).fetchone()
        if not current_admin:
            raise HTTPException(status_code=403, detail="Organization admin access required")
    member = connection.execute(
        "SELECT 1 FROM organization_memberships WHERE organization_id=%s AND user_id=%s",
        (organization_id, user_id),
    ).fetchone()
    if not member:
        raise HTTPException(status_code=404, detail="Participant not found")
    return int(actor.id)


@router.get("/admin/organizations/{organization_id}/members/{user_id}/issues")
def list_admin_member_issues(organization_id: int, user_id: int, request: Request) -> dict:
    with get_connection() as connection:
        _admin_member_issues_scope(connection, request, organization_id, user_id)
        return {"items": appeals.list_issues(connection, organization_id=organization_id, user_id=user_id)}


@router.post("/admin/organizations/{organization_id}/members/{user_id}/issues/{issue_id}/claim")
def claim_admin_member_issue(organization_id: int, user_id: int, issue_id: int, request: Request) -> dict:
    with get_connection() as connection:
        actor_id = _admin_member_issues_scope(connection, request, organization_id, user_id)
        result = appeals.claim_issue(connection, organization_id=organization_id, user_id=user_id,
                                     issue_id=issue_id, actor_id=actor_id)
        if not result:
            raise HTTPException(status_code=409, detail="ISSUE_CLAIM_UNAVAILABLE")
        connection.commit()
        return result


@router.post("/admin/organizations/{organization_id}/members/{user_id}/issues/{issue_id}/reply")
def reply_admin_member_issue(organization_id: int, user_id: int, issue_id: int,
                             payload: AppealReplyRequest, request: Request) -> dict:
    with get_connection() as connection:
        actor_id = _admin_member_issues_scope(connection, request, organization_id, user_id)
        try:
            result = appeals.reply_to_issue(connection, organization_id=organization_id, user_id=user_id,
                                            issue_id=issue_id, actor_id=actor_id, message=payload.message)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        connection.commit()
        return result


@router.get("/admin/dashboard", response_model=AdminDashboard)
def get_admin_dashboard(request: Request, period: str = "30d") -> AdminDashboard:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        return _build_admin_dashboard(connection, scope, period)


@router.get("/admin/regression-tests", response_model=AdminRegressionTestStatusResponse)
def get_admin_regression_tests(request: Request) -> AdminRegressionTestStatusResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
    return get_regression_status()


@router.post("/admin/regression-tests/run", response_model=AdminRegressionTestRunResponse)
def run_admin_regression_tests(request: Request) -> AdminRegressionTestRunResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
    return run_smoke_regression()


@router.post("/admin/regression-tests/run-offline", response_model=AdminRegressionTestRunResponse)
def run_admin_offline_regression_tests(request: Request) -> AdminRegressionTestRunResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
    return run_offline_regression()


@router.post("/admin/regression-tests/run-technical", response_model=AdminRegressionTestRunResponse)
def run_admin_technical_regression_tests(request: Request) -> AdminRegressionTestRunResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
    return run_technical_regression()


@router.post("/admin/regression-tests/run-full", response_model=AdminRegressionTestRunResponse)
def run_admin_full_regression_tests(request: Request) -> AdminRegressionTestRunResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
    return run_full_regression()


@router.post("/admin/regression-tests/cleanup")
def cleanup_admin_regression_tests(request: Request) -> dict[str, object]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
    counts = cleanup_autotest_data()
    return {"ok": True, "deleted": counts}


@router.get("/admin/organizations", response_model=AdminOrganizationsResponse)
def get_admin_organizations(request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        return _build_admin_organizations(connection, scope, actor_user_id=int(user.id))


@router.get('/admin/organizations/{organization_id}/purge-preview')
def preview_admin_organization_purge(organization_id: int, request: Request) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_superadmin(connection, user)
        accounts = connection.execute("""SELECT u.id,u.email,
                NOT EXISTS(SELECT 1 FROM organization_memberships other
                  WHERE other.user_id=u.id AND other.organization_id<>%s) AS will_delete_account
            FROM organization_memberships membership JOIN users u ON u.id=membership.user_id
            WHERE membership.organization_id=%s ORDER BY LOWER(u.email),u.id""",
            (organization_id,organization_id)).fetchall()
        preview_accounts = []
        for row in accounts:
            preserved_reason = None
            if int(row['id']) == int(user.id):
                preserved_reason = 'current_account'
            elif row['will_delete_account'] and _account_has_configured_access(connection, row):
                preserved_reason = 'configured_account'
            preview_accounts.append({'user_id': int(row['id']), 'email': row['email'],
                'will_delete_account': bool(row['will_delete_account']) and preserved_reason is None,
                'preserved_reason': preserved_reason})
        try:
            counts,_,_ = build_purge_plan(connection, organization_id)
        except LookupError as exc:
            raise HTTPException(404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        except RuntimeError as exc:
            code = str(exc).split(':', 1)[0]
            if code == 'PURGE_ATTRIBUTION_SCHEMA_UNSAFE':
                logger.error("Organization purge preview blocked organization_id=%s reason=%s", organization_id, exc)
                raise HTTPException(409, detail=code) from exc
            raise
        return {'target_type':'organization','target_id':organization_id,
            'fingerprint':purge_plan_fingerprint(connection),
            'tables':counts,'total_rows':sum(counts.values()),
            'accounts':preview_accounts,
            'execution_blockers':[{'user_id': account['user_id'], 'email': account['email'],
                'reason': account['preserved_reason']} for account in preview_accounts
                if account['preserved_reason'] is not None and not account['will_delete_account']]}


@router.get('/admin/users/{user_id}/purge-preview')
def preview_admin_user_purge(user_id: int, request: Request) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _get_admin_scope_or_403(connection, user)
        connection.execute('SELECT pg_advisory_xact_lock(%s)', (8_044_001,))
        connection.execute("""SELECT organization_id FROM organization_memberships
            WHERE user_id=%s AND role='admin' ORDER BY organization_id FOR SHARE""", (int(user.id),)).fetchall()
        scope = _get_admin_scope_or_403(connection, user, commit_scope=False)
        account = connection.execute('SELECT id,email FROM users WHERE id=%s FOR UPDATE', (user_id,)).fetchone()
        if not account:
            raise HTTPException(404, detail='User not found')
        _require_account_purge_target(connection, scope=scope, actor=user, account=account)
        try:
            counts,tables,foreign_keys = build_account_purge_plan(connection,user_id)
            _validate_account_purge_plan(connection, scope=scope, user_id=user_id,
                                         tables=tables, foreign_keys=foreign_keys)
        except LookupError as exc:
            raise HTTPException(404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        except RuntimeError as exc:
            code = str(exc).split(':', 1)[0]
            if code == 'PURGE_ATTRIBUTION_SCHEMA_UNSAFE':
                logger.error("Account purge preview blocked user_id=%s reason=%s", user_id, exc)
                raise HTTPException(409, detail=code) from exc
            raise
        return {'target_type':'account','target_id':user_id,'email':account['email'],
            'fingerprint':purge_plan_fingerprint(connection),
            'tables':counts,'total_rows':sum(counts.values())}


@router.get('/admin/assessment-programs')
def get_admin_assessment_programs(request: Request) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_superadmin(connection, user)
        return {'items': [assessment_programs.public_program(item)
                          for item in assessment_programs.list_published(connection)]}


@router.get('/admin/organizations/{organization_id}/assessment-program')
def get_admin_organization_assessment_program(organization_id: int, request: Request) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
        return {'connection': assessment_programs.public_program(assessment_programs.current_connection(
            connection, organization_id=organization_id))}


@router.put('/admin/organizations/{organization_id}/assessment-program')
def connect_admin_organization_assessment_program(
    organization_id: int,
    payload: AdminOrganizationProgramConnectionRequest,
    request: Request,
) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_superadmin(connection, user)
        try:
            result = assessment_programs.connect(connection,
                organization_id=organization_id,
                program_definition_id=payload.program_definition_id,
                actor_user_id=int(user.id), operation_id=payload.operation_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        connection.commit()
        return {'connection': assessment_programs.public_program(result)}


@router.get(
    "/organization-invitations/{token}",
    response_model=OrganizationInvitationPublicResponse,
)
def get_organization_invitation(token: str) -> OrganizationInvitationPublicResponse:
    try:
        context = _public_invitation_by_token(token)
    except OrganizationInvitationError as exc:
        detail = str(exc)
        status_code = 410 if "отозвано" in detail or "истёк" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    if context is None:
        raise HTTPException(status_code=404, detail="Приглашение недействительно.")
    if context.recipient_email:
        with get_connection() as connection:
            credential = connection.execute(
                "SELECT 1 FROM auth_password_credentials WHERE LOWER(email) = %s LIMIT 1",
                (context.recipient_email,),
            ).fetchone()
        context = context.model_copy(
            update={"auth_mode": "password" if credential is not None else "password_registration"}
        )
    return context


@router.post(
    "/admin/organizations/{organization_id}/invitation",
    response_model=OrganizationInvitationAdminResponse,
)
def create_organization_invitation(
    organization_id: int,
    payload: OrganizationInvitationCreateRequest,
    request: Request,
) -> OrganizationInvitationAdminResponse:
    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=payload.expires_in_days)
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        origin = settings.public_app_origin
        organization = connection.execute(
            "SELECT id, name, invitation_intro FROM organizations WHERE id = %s AND is_active = TRUE LIMIT 1",
            (organization_id,),
        ).fetchone()
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        invitation = connection.execute(
            """
            INSERT INTO organization_invitations (
                organization_id, token_hash, expires_at, created_by_user_id, created_at
            )
            VALUES (%s, %s, %s, %s, (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'))
            RETURNING id
            """,
            (organization_id, hash_invitation_token(raw_token), expires_at, int(current_user.id)),
        ).fetchone()
        connection.commit()
    return OrganizationInvitationAdminResponse(
        invitation_id=int(invitation["id"]),
        organization_id=organization_id,
        organization_name=str(organization["name"]),
        invitation_intro=str(organization["invitation_intro"] or "").strip() or None,
        expires_at=expires_at,
        token=raw_token,
        invitation_url=build_public_link(origin, {"invite": raw_token}, mode=settings.app_origin_mode),
    )


@router.delete("/admin/organizations/{organization_id}/invitation/{invitation_id}")
def revoke_organization_invitation(
    organization_id: int,
    invitation_id: int,
    request: Request,
) -> dict[str, bool]:
    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        row = connection.execute(
            """
            UPDATE organization_invitations
            SET revoked_at = COALESCE(revoked_at, NOW())
            WHERE id = %s AND organization_id = %s
            RETURNING id
            """,
            (invitation_id, organization_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Invitation not found")
        connection.commit()
    return {"ok": True}


@router.post(
    "/admin/organizations/{organization_id}/personal-invitations",
    response_model=PersonalInvitationBatchResponse,
)
def send_personal_organization_invitations(
    organization_id: int, payload: PersonalInvitationRequest, request: Request,
) -> PersonalInvitationBatchResponse:
    actor = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    operation = str(request.headers.get('Idempotency-Key') or payload.operation_id or '').strip()
    if not operation:
        raise HTTPException(status_code=400, detail='Idempotency-Key or operation_id is required')
    with get_connection() as connection:
        _require_organization_admin(connection, actor, organization_id)
        # Bounded command lock protects the exact recipient set, including concurrent
        # disjoint batches with one ID. The owner reuses this connection throughout.
        lock_key = f'personal-invitation:{organization_id}:{operation}'
        deadline = time.monotonic() + 2.0
        locked = connection.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked', (lock_key,)).fetchone()
        while not locked.get('locked', True) and time.monotonic() < deadline:
            time.sleep(0.05)
            locked = connection.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked', (lock_key,)).fetchone()
        if not locked.get('locked', True):
            return PersonalInvitationBatchResponse(items=[PersonalInvitationResultItem(
                email=email, status='uncertain', delivery_status='sending', operation_id=operation,
                **invitation_outcomes.facts('sending'),
            ) for email in sorted(set(str(value).strip().lower() for value in payload.emails))])
        try:
            return _execute_personal_invitations(organization_id, payload, request, connection)
        finally:
            connection.rollback()
            connection.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))', (lock_key,))
            connection.commit()


def _execute_personal_invitations(
    organization_id: int,
    payload: PersonalInvitationRequest,
    request: Request,
    command_connection,
) -> PersonalInvitationBatchResponse:
    @contextmanager
    def borrow_connection():
        try:
            yield command_connection
        except Exception:
            command_connection.rollback()
            raise

    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    request_id = str(
        request.headers.get("Idempotency-Key") or payload.operation_id or ""
    ).strip() or None
    if request_id is None:
        raise HTTPException(status_code=400, detail="Idempotency-Key or operation_id is required")
    assignment_ref = str(payload.assignment_ref or "").strip()
    with borrow_connection() as connection:
        _require_organization_admin(connection, current_user, organization_id)
    invitation_secret = str(
        settings.auth_invitation_token_secret
        or settings.postmark_server_token
        or settings.unisender_go_api_key
        or ""
    )
    if len(invitation_secret) < 32:
        raise HTTPException(status_code=503, detail="EMAIL_PROVIDER_NOT_CONFIGURED")
    recipients = sorted(set(str(value).strip().lower() for value in payload.emails))
    with borrow_connection() as connection:
        saved_rows = connection.execute(
            """/* invitation-command */ SELECT id, recipient_email, assignment_ref, created_by_user_id,
                      delivery_status, delivery_error, expires_at, used_at, revoked_at, created_at
               FROM organization_invitations
               WHERE organization_id=%s AND request_id=%s AND purpose='personal_registration'""",
            (organization_id, request_id),
        ).fetchall()
    for saved in saved_rows:
        if (saved['created_by_user_id'] != current_user.id or str(saved.get('assignment_ref') or 'competencies_4k') != assignment_ref
                or (invitation_outcomes.stored_recipient_fingerprint(saved.get('delivery_error')) not in (None, invitation_outcomes.recipient_fingerprint(recipients)))):
            return PersonalInvitationBatchResponse(items=[PersonalInvitationResultItem(email=email, status='error',
                delivery_status='error', error='operation_id уже принадлежит другой операции.',
                **invitation_outcomes.facts('error', reason_code='operation_mismatch')) for email in recipients])
    saved_by_email = {str(row['recipient_email']).lower(): row for row in saved_rows}
    results: list[PersonalInvitationResultItem] = []
    for raw_email in dict.fromkeys(str(value).strip().lower() for value in payload.emails):
        invitation_id: int | None = None
        dispatched = False
        try:
            try:
                email = normalize_email(raw_email)
            except ValueError as exc:
                raise InvitationRefusal('invalid_email') from exc
            previous = saved_by_email.get(email)
            if previous and previous['delivery_status'] == 'error':
                safe = invitation_outcomes.facts('error', previous.get('delivery_error'))
                results.append(PersonalInvitationResultItem(email=email, status='error',
                    invitation_id=previous['id'], delivery_status='error', operation_id=request_id,
                    error=invitation_outcomes.message(safe['reason_code']), replayed=True, **safe))
                continue
            token_material = f"{organization_id}:{assignment_ref}:{email}:{request_id}".encode("utf-8")
            raw_token = base64.urlsafe_b64encode(
                hmac.new(invitation_secret.encode("utf-8"), token_material, hashlib.sha256).digest()
            ).decode("ascii").rstrip("=")
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            expires_at = now_utc + timedelta(hours=max(settings.auth_personal_invitation_ttl_hours,1))
            invitation_url = build_public_link(settings.app_base_url, {"invite": raw_token}, mode=settings.app_origin_mode)
            with borrow_connection() as connection:
                try:
                    _require_organization_admin(connection, current_user, organization_id)
                except HTTPException as exc:
                    raise InvitationRefusal('permission_denied') from exc
                if is_platform_protected_account(connection, email=email):
                    raise InvitationRefusal('member_unavailable')
                readiness = questionnaire_sources.assignment_readiness(
                    connection, organization_id=organization_id, assignment_ref=assignment_ref,
                )
                if readiness["status"] != "ready":
                    raise InvitationRefusal(
                        'organization_unsupported' if readiness.get('reason') == 'university_admission_not_supported' else
                        'questionnaire_incomplete' if readiness.get('reason') == 'early_minimum' else 'questionnaire_unconfirmed',
                        {'missing_fields': readiness.get('missing', [])} if readiness.get('reason') == 'early_minimum' else {},
                    )
                member = connection.execute(
                    """
                    SELECT u.id, EXISTS (
                        SELECT 1 FROM auth_password_credentials c
                        WHERE LOWER(c.email) = LOWER(u.email)
                    ) AS is_registered
                    FROM organization_memberships om
                    JOIN users u ON u.id = om.user_id
                    JOIN organizations o ON o.id = om.organization_id
                    WHERE om.organization_id = %s
                      AND LOWER(u.email) = %s
                      AND (om.role = 'admin' OR om.admission_source IN ('admin_add', 'csv_import'))
                      AND o.is_active = TRUE
                    LIMIT 1
                    """,
                    (organization_id, email),
                ).fetchone()
                if member is None:
                    raise InvitationRefusal('member_unavailable')
                if settings.auth_magic_link_dev_mode or settings.email_provider in {"", "console"}:
                    raise InvitationRefusal('mail_not_configured')
                row = connection.execute(
                    """
                    INSERT INTO organization_invitations (
                        organization_id, token_hash, expires_at, created_by_user_id,
                        recipient_email, purpose, delivery_status, request_id, assignment_ref, delivery_error, created_at
                    ) VALUES (%s, %s, %s, %s, %s, 'personal_registration', 'queued', %s, %s, %s,
                        (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'))
                    ON CONFLICT DO NOTHING
                    RETURNING id, expires_at, delivery_status
                    """,
                    (
                        organization_id,
                        hash_invitation_token(raw_token),
                        expires_at,
                        int(current_user.id),
                        email,
                        request_id,
                        assignment_ref,
                        invitation_outcomes.encode_reason('queued', 'queued', recipients=recipients),
                    ),
                ).fetchone()
                if row is None and request_id is not None:
                    row = connection.execute(
                        """
                        SELECT id, expires_at, delivery_status, token_hash, used_at, revoked_at,
                               recipient_email, organization_id, assignment_ref, created_by_user_id
                        FROM organization_invitations
                        WHERE organization_id = %s
                          AND LOWER(recipient_email) = %s
                          AND purpose = 'personal_registration'
                          AND request_id = %s
                        LIMIT 1
                        """,
                        (organization_id, email, request_id),
                    ).fetchone()
                    if row is None:
                        raise RuntimeError("Не удалось восстановить результат операции отправки.")
                    if int(row["created_by_user_id"] or -1) != int(current_user.id):
                        raise InvitationRefusal('operation_mismatch')
                    stored_assignment = str(row.get("assignment_ref") or "competencies_4k")
                    if stored_assignment != assignment_ref:
                        raise InvitationRefusal('operation_mismatch')
                if row is None:
                    raise RuntimeError("Не удалось создать приглашение.")
                invitation_id = int(row["id"])
                connection.commit()
            with borrow_connection() as connection:
                try:
                    _require_organization_admin(connection, current_user, organization_id)
                except HTTPException as exc:
                    raise InvitationRefusal('permission_changed') from exc
                if is_platform_protected_account(connection, email=email):
                    raise InvitationRefusal('member_unavailable')
                if questionnaire_sources.assignment_readiness(
                    connection, organization_id=organization_id, assignment_ref=assignment_ref,
                )["status"] != "ready":
                    raise InvitationRefusal('organization_changed')
                locked = connection.execute(
                    """SELECT id, expires_at, delivery_status, token_hash, used_at, revoked_at,
                              recipient_email, organization_id, delivery_error, created_at
                       FROM organization_invitations WHERE id = %s FOR UPDATE""",
                    (invitation_id,),
                ).fetchone()
                if locked is None:
                    raise RuntimeError("Операция отправки не найдена.")
                if int(locked["organization_id"]) != organization_id or normalize_email(locked["recipient_email"]) != email:
                    raise InvitationRefusal('operation_mismatch')
                recipient_allowed = connection.execute(
                    """SELECT EXISTS (
                           SELECT 1 FROM auth_password_credentials c
                           WHERE LOWER(c.email)=LOWER(u.email)
                         ) AS is_registered
                       FROM organization_memberships om
                       JOIN users u ON u.id=om.user_id
                       JOIN organizations o ON o.id=om.organization_id
                       WHERE om.organization_id=%s AND LOWER(u.email)=%s
                         AND (om.role='admin' OR om.admission_source IN ('admin_add','csv_import'))
                         AND o.is_active=TRUE LIMIT 1""",
                    (organization_id, email),
                ).fetchone()
                if recipient_allowed is None:
                    raise InvitationRefusal('access_changed')
                if str(locked["token_hash"]) != hash_invitation_token(raw_token):
                    raise InvitationRefusal('operation_mismatch')
                if (locked["used_at"] is not None or locked["revoked_at"] is not None
                        or locked["expires_at"] <= datetime.now(timezone.utc).replace(tzinfo=None)):
                    if locked['delivery_status'] == 'sending':
                        raise InvitationDeliveryUncertainError('Письмо могло быть принято сервисом. Состояние ссылки изменилось.')
                    raise InvitationRefusal('link_used' if locked['used_at'] else 'link_revoked' if locked['revoked_at'] else 'link_expired')
                if str(locked["delivery_status"] or "queued") == "accepted":
                    connection.commit()
                    results.append(PersonalInvitationResultItem(
                        email=email,
                        status="accepted", replayed=True,
                        invitation_id=invitation_id,
                        expires_at=locked["expires_at"], created_at=locked.get("created_at"),
                    ))
                    continue
                if str(locked["delivery_status"] or "queued") == "sending":
                    connection.commit()
                    deadline = time.monotonic() + 2.0
                    while time.monotonic() < deadline:
                        time.sleep(0.05)
                        current = connection.execute(
                            """SELECT delivery_status, expires_at, used_at, revoked_at
                               FROM organization_invitations WHERE id = %s""",
                            (invitation_id,),
                        ).fetchone()
                        if (
                            current
                            and str(current["delivery_status"]) == "accepted"
                            and current["used_at"] is None
                            and current["revoked_at"] is None
                            and current["expires_at"] > datetime.now(timezone.utc).replace(tzinfo=None)
                        ):
                            results.append(PersonalInvitationResultItem(
                                email=email, status="accepted", invitation_id=invitation_id,
                                expires_at=current["expires_at"],
                            ))
                            break
                    else:
                        raise InvitationDeliveryUncertainError(
                            "Исход предыдущей отправки неизвестен. Не повторяйте операцию; "
                            "проверьте эту же попытку."
                        )
                    continue
                if str(locked["delivery_status"] or "queued") == "error":
                    results.append(PersonalInvitationResultItem(
                        email=email, status='error', invitation_id=invitation_id,
                        error=invitation_outcomes.message(invitation_outcomes.facts('error', locked.get('delivery_error'))['reason_code']),
                        delivery_status='error', operation_id=request_id, replayed=True,
                        **invitation_outcomes.facts('error', locked.get('delivery_error')),
                    ))
                    continue
                connection.execute(
                    "UPDATE organization_invitations SET delivery_status = 'sending', delivery_started_at = NOW() WHERE id = %s",
                    (invitation_id,),
                )
                connection.commit()
            dispatched = True
            send_auth_action_email(
                email=email,
                action_url=invitation_url,
                expires_at=locked["expires_at"], created_at=locked.get("created_at"),
                purpose="organization_invitation",
            )
            with borrow_connection() as connection:
                try:
                    _require_organization_admin(connection, current_user, organization_id)
                except HTTPException as exc:
                    raise InvitationDeliveryUncertainError(
                        "Письмо могло быть принято провайдером, но права отправителя изменились."
                    ) from exc
                recipient_allowed = connection.execute(
                    """SELECT 1 FROM organization_memberships om
                       JOIN users u ON u.id=om.user_id
                       JOIN organizations o ON o.id=om.organization_id
                       WHERE om.organization_id=%s AND LOWER(u.email)=%s
                         AND (om.role='admin' OR om.admission_source IN ('admin_add','csv_import'))
                         AND o.is_active=TRUE LIMIT 1""",
                    (organization_id, email),
                ).fetchone()
                if recipient_allowed is None:
                    raise InvitationDeliveryUncertainError(
                        "Письмо могло быть принято провайдером, но организация или доступ участника изменились."
                    )
                accepted = connection.execute(
                    """UPDATE organization_invitations
                       SET delivery_status = 'accepted', sent_at = NOW(), delivery_error = %s
                       WHERE id = %s AND delivery_status = 'sending'
                         AND used_at IS NULL AND revoked_at IS NULL
                         AND expires_at > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
                       RETURNING id""",
                    (invitation_outcomes.encode_reason('accepted', 'accepted', recipients=recipients), invitation_id),
                ).fetchone()
                if accepted is None:
                    raise InvitationDeliveryUncertainError(
                        "Письмо могло быть принято провайдером, но приглашение было изменено, "
                        "отозвано или истекло до фиксации результата."
                    )
                connection.execute(
                    """
                    UPDATE organization_invitations
                    SET revoked_at = COALESCE(revoked_at, NOW())
                    WHERE organization_id = %s AND LOWER(recipient_email) = %s
                      AND purpose = 'personal_registration' AND used_at IS NULL AND revoked_at IS NULL
                      AND id <> %s
                    """,
                    (organization_id, email, invitation_id),
                )
                connection.commit()
            results.append(PersonalInvitationResultItem(email=email, status="accepted", invitation_id=invitation_id, expires_at=locked["expires_at"], created_at=locked.get("created_at")))
        except (InvitationDeliveryUncertainError, EmailDeliveryUncertainError) as exc:
            code = 'context_changed' if isinstance(exc, InvitationDeliveryUncertainError) and dispatched else 'delivery_unknown'
            logger.warning('Personal invitation outcome organization_id=%s operation_id=%s reason_code=%s',
                           organization_id, re.sub(r'[^a-zA-Z0-9_-]', '_', request_id)[:200], code)
            if invitation_id is not None:
                with borrow_connection() as connection:
                    connection.execute(
                        "UPDATE organization_invitations SET delivery_error = %s WHERE id = %s AND delivery_status = 'sending'",
                        (invitation_outcomes.encode_reason('sending', code, recipients=recipients), invitation_id),
                    )
                    connection.commit()
            results.append(PersonalInvitationResultItem(
                email=str(raw_email).strip().lower(), status='uncertain', invitation_id=invitation_id,
                error=invitation_outcomes.message(code), delivery_status='sending', operation_id=request_id,
                **invitation_outcomes.facts('sending', reason_code=code),
            ))
        except (ValueError, EmailDeliveryError) as exc:
            if dispatched and not isinstance(exc, EmailDeliveryError):
                logger.warning('Personal invitation outcome organization_id=%s operation_id=%s reason_code=delivery_unknown',
                               organization_id, re.sub(r'[^a-zA-Z0-9_-]', '_', request_id)[:200])
                # An adapter bug while reading a POST response is not a rejection receipt.
                with borrow_connection() as connection:
                    connection.execute(
                        "UPDATE organization_invitations SET delivery_error = %s WHERE id = %s AND delivery_status = 'sending'",
                        (invitation_outcomes.encode_reason('sending', 'delivery_unknown', recipients=recipients), invitation_id),
                    )
                    connection.commit()
                results.append(PersonalInvitationResultItem(email=str(raw_email).strip().lower(),
                    status='uncertain', invitation_id=invitation_id, delivery_status='sending',
                    operation_id=request_id, **invitation_outcomes.facts('sending', reason_code='delivery_unknown')))
                continue
            code = getattr(exc, 'reason_code', 'failed_unclassified')
            safe = invitation_outcomes.facts('error', reason_code=code)
            code = safe['reason_code']
            logger.warning('Personal invitation outcome organization_id=%s operation_id=%s reason_code=%s',
                           organization_id, re.sub(r'[^a-zA-Z0-9_-]', '_', request_id)[:200], code)
            if invitation_id is not None:
                with borrow_connection() as connection:
                    connection.execute(
                        """UPDATE organization_invitations
                           SET delivery_status = 'error', delivery_error = %s
                           WHERE id = %s AND delivery_status IN ('queued', 'sending')""",
                        (invitation_outcomes.encode_reason('error', code, getattr(exc, 'reason_params', {}), recipients=recipients), invitation_id),
                    )
                    connection.commit()
            previous = saved_by_email.get(str(raw_email).strip().lower())
            prior_accepted = previous and previous['delivery_status'] == 'accepted'
            link = ('used' if previous.get('used_at') else 'revoked' if previous.get('revoked_at') else
                    'expired' if previous['expires_at'] <= datetime.now(timezone.utc).replace(tzinfo=None) else 'active') if previous else None
            results.append(PersonalInvitationResultItem(email=str(raw_email).strip().lower(), status='error',
                invitation_id=invitation_id, error=invitation_outcomes.message(code),
                delivery_status='accepted' if prior_accepted else 'error', operation_id=request_id,
                link_status=link, expires_at=previous['expires_at'] if previous else None,
                **(invitation_outcomes.facts('accepted') if prior_accepted else
                   invitation_outcomes.facts('error', invitation_outcomes.encode_reason('error', code, getattr(exc, 'reason_params', {}), recipients=recipients)))))
    for item in results:
        item.operation_id = request_id
        if item.outcome is None:
            for key, value in invitation_outcomes.facts(item.delivery_status or item.status).items():
                setattr(item, key, value)
        if item.delivery_status is None:
            item.delivery_status = item.status
    return PersonalInvitationBatchResponse(items=results)


@router.get(
    "/admin/organizations/{organization_id}/personal-invitations/operations/{operation_id}",
    response_model=PersonalInvitationBatchResponse,
)
def read_personal_organization_invitation_operation(
    organization_id: int,
    operation_id: str,
    assignment_ref: str,
    request: Request,
) -> PersonalInvitationBatchResponse:
    """Read only invitations saved by one exact idempotent command."""
    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    requested_emails: list[str] = []
    for raw_email in request.query_params.getlist("email"):
        try:
            email = normalize_email(raw_email)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_INVITATION_RECIPIENT") from exc
        if email not in requested_emails:
            requested_emails.append(email)
    if len(requested_emails) > 500:
        raise HTTPException(status_code=400, detail="TOO_MANY_INVITATION_RECIPIENTS")
    with get_connection() as connection:
        _require_organization_admin(connection, current_user, organization_id)
        rows = connection.execute(
            """SELECT id,recipient_email,expires_at,delivery_status,delivery_error,used_at,revoked_at,created_at
               FROM organization_invitations
               WHERE organization_id=%s AND created_by_user_id=%s
                 AND purpose='personal_registration' AND request_id=%s AND assignment_ref=%s
               ORDER BY id DESC""",
            (organization_id, int(current_user.id), operation_id, assignment_ref),
        ).fetchall()
    latest: dict[str, dict] = {}
    for row in rows:
        latest.setdefault(normalize_email(row["recipient_email"]), row)
    if not latest:
        raise HTTPException(status_code=404, detail="INVITATION_OPERATION_NOT_FOUND")
    items: list[PersonalInvitationResultItem] = []
    for email, row in latest.items():
        delivery = str(row["delivery_status"] or "uncertain")
        status = "accepted" if delivery == "accepted" else (
            "queued" if delivery == "queued" else "uncertain" if delivery == "sending" else "error"
        )
        if row["used_at"] is not None:
            status = "already_registered"
            link_status = "used"
        elif row["revoked_at"] is not None:
            link_status = "revoked"
        elif row["expires_at"] <= datetime.now(timezone.utc).replace(tzinfo=None):
            link_status = "expired"
        else:
            link_status = "active"
        items.append(PersonalInvitationResultItem(
            email=email,
            status=status,
            invitation_id=int(row["id"]),
            expires_at=row["expires_at"],
            error=invitation_outcomes.message(invitation_outcomes.facts(delivery, row.get('delivery_error'))['reason_code']) if delivery != 'accepted' else None,
            operation_id=operation_id, created_at=row.get('created_at'),
            **invitation_outcomes.facts(delivery, row.get('delivery_error')),
            delivery_status=delivery,
            link_status=link_status,
        ))
    for email in requested_emails:
        if email not in latest:
            # No saved row can mean a pre-commit loss or a per-recipient refusal.
            # Neither outcome may be invented by readback.
            items.append(PersonalInvitationResultItem(email=email, status='uncertain', operation_id=operation_id, **invitation_outcomes.facts('unknown')))
    return PersonalInvitationBatchResponse(items=items)


@router.get('/admin/organizations/{organization_id}/assessment-source-options')
def get_organization_assessment_source_options(organization_id: int, request: Request) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
        return assessment_assignment_sources.options(connection, organization_id=organization_id)


@router.post(
    "/admin/organizations/{organization_id}/assessment-assignments",
    response_model=AssessmentAssignmentBatchResponse,
)
def assign_organization_assessment(
    organization_id: int,
    payload: AssessmentAssignmentRequest,
    request: Request,
) -> AssessmentAssignmentBatchResponse:
    """Persist an explicit scoped assignment without registration mail or preparation."""
    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    assignment_ref = str(payload.assignment_ref).strip()
    recipient_ids = sorted(set(int(value) for value in payload.user_ids))
    command = assessment_assignment_operations.command_request(assignment_ref=assignment_ref,
        user_ids=recipient_ids, role_profile_version_id=payload.role_profile_version_id,
        assessment_configuration_id=payload.assessment_configuration_id)
    fingerprint = assessment_assignment_operations.fingerprint(command, legacy=True)
    results: list[AssessmentAssignmentResultItem] = []
    with get_connection() as connection:
        assignment_scope = _require_organization_admin(connection, current_user, organization_id)
        try:
            created = assessment_assignment_operations.claim(connection, organization_id=organization_id,
                actor_user_id=int(current_user.id), operation_id=payload.operation_id, request=command)
            if not created:
                saved = assessment_assignment_operations.read(connection, organization_id=organization_id,
                    actor_user_id=int(current_user.id), operation_id=payload.operation_id, request=command)
                return AssessmentAssignmentBatchResponse(**saved)
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        previous = connection.execute(
            """SELECT DISTINCT request_fingerprint
               FROM organization_assessment_assignments
               WHERE organization_id=%s AND created_by_user_id=%s AND operation_id=%s""",
            (organization_id, int(current_user.id), payload.operation_id),
        ).fetchall()
        if previous and any(str(row["request_fingerprint"]) not in {
                fingerprint, assessment_assignment_operations.fingerprint(command)} for row in previous):
            raise HTTPException(status_code=409, detail="operation_id уже использован с другим набором назначения.")
        if previous:
            # A pre-ledger operation may already own historical assignments.
            # It must never execute again against a replacement generation.
            saved = assessment_assignment_operations.read(connection, organization_id=organization_id,
                actor_user_id=int(current_user.id), operation_id=payload.operation_id, request=command)
            connection.commit()
            return AssessmentAssignmentBatchResponse(**saved)
        readiness = questionnaire_sources.assignment_readiness(
            connection, organization_id=organization_id, assignment_ref=assignment_ref,
        )
        if readiness["status"] != "ready":
            raise HTTPException(
                status_code=409,
                detail="ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED",
            )
        try:
            try:
                program_binding = assessment_programs.resolve(
                    connection, organization_id=organization_id, assignment_ref=assignment_ref,
                    role_profile_version_id=payload.role_profile_version_id,
                )
            except ValueError as program_error:
                if str(program_error) != 'PROGRAM_NOT_CONNECTED':
                    raise
                # Compatibility for organizations admitted before ProgramDefinition.
                # New connections are created only through assessment_programs.connect().
                program_binding = assessment_assignment_sources.resolve_pilot_binding(
                    connection, organization_id=organization_id, assignment_ref=assignment_ref)
        except ValueError as exc:
            error_code = str(exc)
            logger.warning(
                "Assessment assignment source resolution failed organization_id=%s code=%s",
                organization_id,
                error_code,
            )
            public_codes = {
                "PROGRAM_ROLE_SELECTION_REQUIRED",
                "PROGRAM_ROLE_NOT_AVAILABLE",
                "PROGRAM_NOT_CONNECTED",
                "PROGRAM_NOT_AVAILABLE",
                "PROGRAM_NOT_AVAILABLE_FOR_NEW_ASSIGNMENTS",
                "PROGRAM_ASSIGNMENT_REF_MISMATCH",
                "PROGRAM_CONFIGURATION_NOT_AVAILABLE",
                "PROGRAM_CATALOG_NOT_AVAILABLE",
                "PROGRAM_CATALOG_VERSION_MISMATCH",
                "PROGRAM_CATALOG_SCOPE_MISMATCH",
            }
            raise HTTPException(status_code=409, detail=(
                error_code if error_code in public_codes else "PROGRAM_CONFIGURATION_NOT_AVAILABLE"
            )) from exc
        if payload.assessment_configuration_id is not None and (
            int(payload.assessment_configuration_id) != int(program_binding["assessment_configuration_id"])
            or int(payload.role_profile_version_id) != int(program_binding["role_profile_version_id"])
        ):
            raise HTTPException(
                status_code=409,
                detail="PROGRAM_SOURCE_SELECTION_STALE",
            )
        for user_id in recipient_ids:
            member = connection.execute(
                """SELECT om.user_id
                   FROM organization_memberships om
                   JOIN organizations o ON o.id=om.organization_id
                   WHERE om.organization_id=%s AND om.user_id=%s
                     AND om.is_participant=TRUE AND o.is_active=TRUE
                   LIMIT 1""",
                (organization_id, user_id),
            ).fetchone()
            if member is None:
                results.append(AssessmentAssignmentResultItem(
                    user_id=user_id, status="not_assigned",
                    error="Участник не связан с этой активной организацией.",
                    reason_code="ASSIGNMENT_RECIPIENT_NOT_ELIGIBLE",
                ))
                continue
            row = connection.execute(
                """INSERT INTO organization_assessment_assignments (
                     organization_id,recipient_user_id,assignment_ref,created_by_user_id,
                     questionnaire_revision_id,status,operation_id,request_fingerprint
                   ) VALUES (%s,%s,%s,%s,%s,'active',%s,%s)
                   ON CONFLICT (organization_id,recipient_user_id,assignment_ref)
                   WHERE status='active' AND revoked_at IS NULL DO NOTHING
                   RETURNING id""",
                (
                    organization_id, user_id, assignment_ref, int(current_user.id),
                    readiness.get("questionnaire_revision_id"), payload.operation_id, fingerprint,
                ),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    """SELECT id FROM organization_assessment_assignments
                       WHERE organization_id=%s AND recipient_user_id=%s AND assignment_ref=%s
                         AND status='active' AND revoked_at IS NULL""",
                    (organization_id, user_id, assignment_ref),
                ).fetchone()
                if row is None:
                    raise HTTPException(409, detail='ASSIGNMENT_STATE_STALE')
                results.append(AssessmentAssignmentResultItem(
                    user_id=user_id, status="already_assigned",
                    assignment_id=int(row["id"]),
                ))
            else:
                results.append(AssessmentAssignmentResultItem(
                    user_id=user_id, status="assigned", assignment_id=int(row["id"]),
                ))
            if row:
                try:
                    assessment_assignment_sources.bind(connection, assignment_id=int(row['id']),
                        organization_id=organization_id,
                        configuration_id=int(program_binding['assessment_configuration_id']),
                        role_version_id=int(program_binding['role_profile_version_id']),
                        questionnaire_revision_id=readiness['questionnaire_revision_id'],
                        actor_user_id=int(current_user.id), operation_id=payload.operation_id)
                except ValueError as exc:
                    raise HTTPException(409, detail=str(exc)) from exc
        response = AssessmentAssignmentBatchResponse(items=results)
        assessment_assignment_operations.save(connection, organization_id=organization_id,
            actor_user_id=int(current_user.id), operation_id=payload.operation_id,
            request=command, result=response.model_dump())
        connection.commit()
    return AssessmentAssignmentBatchResponse(items=results)


@router.get(
    "/admin/organizations/{organization_id}/assessment-assignments/operations/{operation_id}",
    response_model=AssessmentAssignmentBatchResponse,
)
def read_organization_assessment_assignment_operation(
    organization_id: int,
    operation_id: str,
    assignment_ref: str,
    user_ids: str,
    request: Request,
    role_profile_version_id: int | None = None,
    assessment_configuration_id: int | None = None,
) -> AssessmentAssignmentBatchResponse:
    """Confirm the exact committed assignment command, never a coincidental stale assignment."""
    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    try:
        recipients = sorted(set(int(value) for value in str(user_ids or "").split(",") if value.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ASSIGNMENT_READBACK_RECIPIENTS_INVALID") from exc
    if not recipients:
        raise HTTPException(status_code=400, detail="ASSIGNMENT_READBACK_RECIPIENTS_REQUIRED")
    command = assessment_assignment_operations.command_request(assignment_ref=assignment_ref,
        user_ids=recipients, role_profile_version_id=role_profile_version_id,
        assessment_configuration_id=assessment_configuration_id)
    with get_connection() as connection:
        _require_organization_admin(connection, current_user, organization_id)
        try:
            saved = assessment_assignment_operations.read(connection, organization_id=organization_id,
                actor_user_id=int(current_user.id), operation_id=operation_id, request=command)
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        if saved is None:
            raise HTTPException(status_code=404, detail="ASSIGNMENT_OPERATION_NOT_FOUND")
    return AssessmentAssignmentBatchResponse(**saved)


@router.post(
    "/admin/organizations/{organization_id}/assessment-assignments/{assignment_id}/cancel",
    response_model=AssessmentAssignmentCancelResponse,
)
def cancel_organization_assessment_assignment(
    organization_id: int, assignment_id: int,
    payload: AssessmentAssignmentCancelRequest, request: Request,
) -> AssessmentAssignmentCancelResponse:
    from Api import assessment_assignment_cancellation
    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_organization_admin(connection, current_user, organization_id)
        try:
            result = assessment_assignment_cancellation.cancel(
                connection, organization_id=organization_id, assignment_id=assignment_id,
                actor_user_id=int(current_user.id), operation_id=payload.operation_id,
            )
            connection.commit()
            return AssessmentAssignmentCancelResponse(**result)
        except assessment_assignment_cancellation.CancellationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.code) from exc


@router.delete("/admin/organizations/{organization_id}/personal-invitations/{invitation_id}")
def revoke_personal_organization_invitation(
    organization_id: int,
    invitation_id: int,
    request: Request,
) -> dict[str, bool]:
    current_user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_organization_admin(connection, current_user, organization_id)
        invitation = connection.execute(
            """SELECT id,used_at,revoked_at,recipient_email
               FROM organization_invitations
               WHERE id=%s AND organization_id=%s AND purpose='personal_registration'
               FOR UPDATE""",
            (invitation_id, organization_id),
        ).fetchone()
        if invitation is None:
            raise HTTPException(status_code=404, detail="INVITATION_NOT_FOUND")
        if invitation["used_at"] is not None:
            raise HTTPException(status_code=409, detail="INVITATION_ALREADY_USED")
        if invitation["revoked_at"] is not None:
            return {"ok": True}
        recipient = connection.execute(
            """SELECT id FROM users
               WHERE LOWER(email)=LOWER(%s)
               LIMIT 1
               FOR UPDATE""",
            (invitation["recipient_email"],),
        ).fetchone()
        if recipient is not None:
            acquaintance_started = connection.execute(
                """SELECT 1 FROM participant_acquaintance_states
                   WHERE user_id=%s AND organization_id=%s
                     AND (status <> 'not_started' OR current_step > 0)
                   LIMIT 1
                   FOR UPDATE""",
                (int(recipient["id"]), organization_id),
            ).fetchone()
            if acquaintance_started is not None:
                raise HTTPException(status_code=409, detail="INVITATION_STATE_CHANGED")
        row = connection.execute(
            """
            UPDATE organization_invitations SET revoked_at=NOW()
            WHERE id=%s AND organization_id=%s AND purpose='personal_registration'
              AND used_at IS NULL AND revoked_at IS NULL
            RETURNING id
            """,
            (invitation_id, organization_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=409, detail="INVITATION_STATE_CHANGED")
        connection.commit()
    return {"ok": True}


@router.post("/admin/organizations", response_model=AdminOrganizationsResponse)
def create_admin_organization(payload: AdminOrganizationCreateRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    org_code = _normalize_admin_org_code(payload.code)
    org_name = _normalize_admin_org_name(payload.name)
    with get_connection() as connection:
        scope = _require_superadmin(connection, user)
        try:
            connection.execute(
                """
                INSERT INTO organizations (code, name)
                VALUES (%s, %s)
                """,
                (org_code, org_name),
            )
            connection.execute(
                "DELETE FROM organization_deletion_tombstones WHERE code_sha256=%s",
                (hashlib.sha256(org_code.encode("utf-8")).hexdigest(),),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise HTTPException(status_code=409, detail="Organization with this code already exists") from exc
        return _build_admin_organizations(connection, scope)


@router.patch("/admin/organizations/{organization_id}", response_model=AdminOrganizationsResponse)
def update_admin_organization(organization_id: int, payload: AdminOrganizationUpdateRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_code = _normalize_admin_org_code(payload.code) if payload.code is not None else None
    normalized_name = _normalize_admin_org_name(payload.name) if payload.name is not None else None
    profile_fields_supplied = any(
        field in payload.model_fields_set
        for field in (
            "founded_year", "employee_count", "industry", "website", "headquarters", "notes",
            "invitation_intro",
        )
    )
    if normalized_code is None and normalized_name is None and not profile_fields_supplied:
        raise HTTPException(status_code=400, detail="No organization changes provided")
    current_year = datetime.now().year
    if payload.founded_year is not None and not 1000 <= payload.founded_year <= current_year + 1:
        raise HTTPException(status_code=400, detail="Founded year is invalid")
    if payload.employee_count is not None and payload.employee_count < 0:
        raise HTTPException(status_code=400, detail="Employee count cannot be negative")
    with get_connection() as connection:
        scope = _require_organization_admin(connection, user, organization_id)
        if not scope.is_superadmin and ({"code", "name"} & payload.model_fields_set):
            raise HTTPException(
                status_code=403,
                detail="Имя организации меняется при подтверждении анкеты; код закреплённой организации недоступен для изменения.",
            )
        org_row = connection.execute("SELECT id FROM organizations WHERE id = %s LIMIT 1", (organization_id,)).fetchone()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        try:
            connection.execute(
                """
                UPDATE organizations
                SET code = COALESCE(%s, code),
                    name = COALESCE(%s, name),
                    founded_year = CASE WHEN %s THEN %s ELSE founded_year END,
                    employee_count = CASE WHEN %s THEN %s ELSE employee_count END,
                    industry = CASE WHEN %s THEN %s ELSE industry END,
                    website = CASE WHEN %s THEN %s ELSE website END,
                    headquarters = CASE WHEN %s THEN %s ELSE headquarters END,
                    notes = CASE WHEN %s THEN %s ELSE notes END,
                    invitation_intro = CASE WHEN %s THEN %s ELSE invitation_intro END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    normalized_code,
                    normalized_name,
                    "founded_year" in payload.model_fields_set,
                    payload.founded_year,
                    "employee_count" in payload.model_fields_set,
                    payload.employee_count,
                    "industry" in payload.model_fields_set,
                    _normalize_optional_admin_text(payload.industry, max_length=255),
                    "website" in payload.model_fields_set,
                    _normalize_optional_admin_text(payload.website, max_length=500),
                    "headquarters" in payload.model_fields_set,
                    _normalize_optional_admin_text(payload.headquarters, max_length=255),
                    "notes" in payload.model_fields_set,
                    _normalize_optional_admin_text(payload.notes),
                    "invitation_intro" in payload.model_fields_set,
                    _normalize_optional_admin_text(payload.invitation_intro, max_length=1000),
                    organization_id,
                ),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise HTTPException(status_code=409, detail="Organization with this code already exists") from exc
        return _build_admin_organizations(connection, scope)


@router.delete("/admin/organizations/{organization_id}", response_model=AdminOrganizationsResponse)
def delete_or_deactivate_admin_organization(organization_id: int, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
        org_row = connection.execute("SELECT id FROM organizations WHERE id = %s LIMIT 1", (organization_id,)).fetchone()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        connection.execute(
            "UPDATE organizations SET is_active = FALSE, updated_at = NOW() WHERE id = %s",
            (organization_id,),
        )
        connection.commit()
        return _build_admin_organizations(connection)


@router.post("/admin/organizations/{organization_id}/restore", response_model=AdminOrganizationsResponse)
def restore_admin_organization(organization_id: int, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
        org_row = connection.execute(
            "SELECT id, is_active FROM organizations WHERE id = %s FOR UPDATE",
            (organization_id,),
        ).fetchone()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        connection.execute(
            "UPDATE organizations SET is_active = TRUE, updated_at = NOW() WHERE id = %s AND is_active = FALSE",
            (organization_id,),
        )
        connection.commit()
        return _build_admin_organizations(connection)


@router.post("/admin/organizations/{organization_id}/purge", response_model=AdminOrganizationsResponse)
def purge_admin_organization(
    organization_id: int,
    payload: AdminOrganizationPurgeRequest,
    request: Request,
) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if not _physical_organization_purge_available():
        raise HTTPException(status_code=404, detail="Physical organization purge is unavailable")
    if not payload.acknowledge_irreversible:
        raise HTTPException(status_code=400, detail="Irreversible purge acknowledgement is required")
    confirmation_code = str(payload.confirmation_code or "").strip()
    with get_connection() as connection:
        _require_superadmin(connection, user)
        connection.execute('SELECT pg_advisory_xact_lock(%s)', (8_044_001,))
        try:
            prior = read_receipt(connection, operation_id=payload.operation_id,
                target_type="organization", target_id=organization_id,
                fingerprint=payload.preview_fingerprint,
                actor_user_id=int(user.id), allow_legacy_actor=True)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if prior:
            return _build_admin_organizations(connection)
        organization = connection.execute(
            "SELECT id, code, is_active FROM organizations WHERE id = %s FOR UPDATE",
            (organization_id,),
        ).fetchone()
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        if confirmation_code != str(organization["code"]):
            raise HTTPException(status_code=409, detail="Confirmation code does not match organization code")
        protected_account = connection.execute("""SELECT u.id,u.email
            FROM organization_memberships membership JOIN users u ON u.id=membership.user_id
            WHERE membership.organization_id=%s
              AND NOT EXISTS(SELECT 1 FROM organization_memberships other
                WHERE other.user_id=u.id AND other.organization_id<>%s)
            ORDER BY u.id""", (organization_id, organization_id)).fetchall()
        if any(int(row['id']) == int(user.id) for row in protected_account):
            raise HTTPException(status_code=409, detail="CANNOT_PURGE_ORGANIZATION_WITH_CURRENT_ACCOUNT")
        if any(_account_has_configured_access(connection, row) for row in protected_account):
            raise HTTPException(status_code=409, detail="CANNOT_PURGE_ORGANIZATION_WITH_CONFIGURED_ACCOUNT")
        try:
            intent = {"operation_id": payload.operation_id, "target_type": "organization",
                "target_id": organization_id, "preview_fingerprint": payload.preview_fingerprint}
            def persist_intent(validated_fingerprint: str) -> None:
                nonlocal intent
                if settings.deletion_ledger_path:
                    intent = append_intent(settings.deletion_ledger_path, operation_id=payload.operation_id,
                        target_type="organization", target_id=organization_id,
                        fingerprint=validated_fingerprint)
            counts = purge_organization(
                connection,
                organization_id=organization_id,
                confirm_code=confirmation_code,
                expected_fingerprint=payload.preview_fingerprint,
                on_validated=persist_intent,
            )
            record_receipt(connection, {**intent, 'actor_user_id': int(user.id)})
            connection.commit()
        except (LookupError, ValueError) as exc:
            connection.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            connection.rollback()
            logger.exception("Physical organization purge failed organization_id=%s", organization_id)
            code = str(exc).split(':', 1)[0]
            raise HTTPException(status_code=409, detail=(code
                if code == 'PURGE_ATTRIBUTION_SCHEMA_UNSAFE' else 'PURGE_EXECUTION_FAILED')) from exc
        except Exception as exc:
            connection.rollback()
            logger.exception("Physical organization purge failed organization_id=%s", organization_id)
            raise HTTPException(status_code=409, detail="PURGE_EXECUTION_FAILED") from exc
        _invalidate_deleted_accounts(int(row['id']) for row in protected_account)
        logger.warning(
            "Physical organization purge completed organization_id=%s actor_user_id=%s rows=%s operation_id=%s",
            organization_id,
            int(user.id) if user and user.id is not None else None,
            sum(counts.values()),
            payload.operation_id,
        )
        return _build_admin_organizations(connection)


@router.post("/admin/users/{user_id}/purge")
def purge_admin_account(user_id: int, payload: AdminAccountPurgeRequest, request: Request) -> dict:
    actor = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if not _physical_organization_purge_available():
        raise HTTPException(status_code=404, detail="Physical account purge is unavailable")
    if not payload.acknowledge_irreversible:
        raise HTTPException(status_code=400, detail="Irreversible purge acknowledgement is required")
    with get_connection() as connection:
        _get_admin_scope_or_403(connection, actor)
        connection.execute('SELECT pg_advisory_xact_lock(%s)', (8_044_001,))
        connection.execute("""SELECT organization_id FROM organization_memberships
            WHERE user_id=%s AND role='admin' ORDER BY organization_id FOR SHARE""", (int(actor.id),)).fetchall()
        scope = _get_admin_scope_or_403(connection, actor, commit_scope=False)
        try:
            prior = read_receipt(connection, operation_id=payload.operation_id,
                target_type="account", target_id=user_id,
                fingerprint=payload.preview_fingerprint, actor_user_id=int(actor.id),
                allow_legacy_actor=scope.is_superadmin)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if prior:
            return {"ok": True, "deleted": {}, "operation_id": payload.operation_id,
                "idempotent": True}
        account = connection.execute("SELECT id,email FROM users WHERE id=%s FOR UPDATE", (user_id,)).fetchone()
        if account is None:
            raise HTTPException(status_code=404, detail="User not found")
        if normalize_email(payload.confirmation_email) != normalize_email(account["email"]):
            raise HTTPException(status_code=409, detail="Confirmation email does not match account")
        _require_account_purge_target(connection, scope=scope, actor=actor, account=account)
        try:
            intent = {"operation_id": payload.operation_id, "target_type": "account",
                "target_id": user_id, "preview_fingerprint": payload.preview_fingerprint}
            def persist_intent(validated_fingerprint: str) -> None:
                nonlocal intent
                if settings.deletion_ledger_path:
                    intent = append_intent(settings.deletion_ledger_path, operation_id=payload.operation_id,
                        target_type="account", target_id=user_id, fingerprint=validated_fingerprint)
            counts = purge_account(connection, user_id=user_id,
                expected_fingerprint=payload.preview_fingerprint, on_validated=persist_intent,
                validate_scope=lambda tables, foreign_keys: _validate_account_purge_plan(
                    connection, scope=scope, user_id=user_id, tables=tables, foreign_keys=foreign_keys))
            record_receipt(connection, {**intent, 'actor_user_id': int(actor.id)})
            connection.commit()
        except HTTPException:
            connection.rollback()
            raise
        except (LookupError, ValueError) as exc:
            connection.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            connection.rollback()
            logger.exception("Physical account purge failed user_id=%s", user_id)
            code = str(exc).split(':', 1)[0]
            raise HTTPException(status_code=409, detail=(code
                if code == 'PURGE_ATTRIBUTION_SCHEMA_UNSAFE' else 'PURGE_EXECUTION_FAILED')) from exc
        except Exception as exc:
            connection.rollback()
            logger.exception("Physical account purge failed user_id=%s", user_id)
            raise HTTPException(status_code=409, detail="PURGE_EXECUTION_FAILED") from exc
        _invalidate_deleted_accounts([user_id])
        logger.warning("Physical account purge completed user_id=%s actor_user_id=%s rows=%s operation_id=%s",
            user_id, int(actor.id) if actor and actor.id is not None else None,
            sum(counts.values()), payload.operation_id)
        return {"ok": True, "deleted": counts, "operation_id": payload.operation_id}


@router.post("/admin/organizations/{organization_id}/domains", response_model=AdminOrganizationsResponse)
def add_admin_organization_domain(organization_id: int, payload: AdminOrganizationDomainRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    domain = _normalize_admin_org_domain(payload.domain)
    with get_connection() as connection:
        _require_superadmin(connection, user)
        org_row = connection.execute("SELECT id FROM organizations WHERE id = %s LIMIT 1", (organization_id,)).fetchone()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        try:
            connection.execute(
                """
                INSERT INTO organization_email_domains (organization_id, domain)
                VALUES (%s, %s)
                ON CONFLICT (organization_id, domain) DO NOTHING
                """,
                (organization_id, domain),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise HTTPException(status_code=409, detail="This domain is already assigned to another organization") from exc
        return _build_admin_organizations(connection)


@router.delete("/admin/organizations/{organization_id}/domains", response_model=AdminOrganizationsResponse)
def delete_admin_organization_domain(organization_id: int, domain: str, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_domain = _normalize_admin_org_domain(domain)
    with get_connection() as connection:
        _require_superadmin(connection, user)
        connection.execute(
            """
            DELETE FROM organization_email_domains
            WHERE organization_id = %s
              AND LOWER(domain) = %s
            """,
            (organization_id, normalized_domain),
        )
        connection.commit()
        return _build_admin_organizations(connection)


def _lock_active_organization_for_admin_write(connection, organization_id: int) -> dict:
    organization = connection.execute(
        "SELECT code, is_active FROM organizations WHERE id=%s FOR NO KEY UPDATE",
        (organization_id,),
    ).fetchone()
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not organization["is_active"]:
        raise HTTPException(status_code=409, detail="ORGANIZATION_ACCESS_PAUSED")
    return organization


@router.post("/admin/organizations/{organization_id}/admins", response_model=AdminOrganizationsResponse)
def add_admin_organization_admin(organization_id: int, payload: AdminOrganizationAdminRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_email = normalize_email(payload.email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid admin email is required")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        # Account purge takes the exclusive lock before it locks memberships.
        connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (8_044_001,))
        membership = _lock_membership_by_email(connection, email=normalized_email)
        organization = _lock_active_organization_for_admin_write(connection, organization_id)
        _reject_platform_protected_account(
            connection,
            email=normalized_email,
            user_id=int(membership["user_id"]) if membership is not None else None,
        )
        _reject_foreign_membership(
            membership,
            organization_id=organization_id,
            expose_organization=True,
        )
        connection.execute(
            """DELETE FROM configured_access_suppressions
               WHERE email=%s AND access_kind='organization_admin' AND organization_code=%s""",
            (normalized_email, str(organization["code"])),
        )
        user_id = _ensure_org_admin_user(connection, email=normalized_email, full_name=payload.full_name)
        connection.execute(
            """DELETE FROM configured_organization_membership_suppressions
               WHERE user_id=%s AND organization_id=%s""",
            (user_id, organization_id),
        )
        _execute_membership_write(
            connection,
            email=normalized_email,
            organization_id=organization_id,
            expose_existing_organization=True,
            query="""
            INSERT INTO organization_memberships (
                organization_id, user_id, role, is_participant, admission_source, admitted_by_user_id, admitted_at
            )
            VALUES (%s, %s, 'admin', FALSE, 'admin_add', %s, NOW())
            ON CONFLICT (organization_id, user_id) DO UPDATE
            SET role = 'admin', updated_at = NOW()
            WHERE organization_memberships.role IS DISTINCT FROM 'admin'
            """,
            params=(organization_id, user_id, int(user.id)),
        )
        connection.commit()
        return _build_admin_organizations(connection)


@router.delete("/admin/organizations/{organization_id}/admins", response_model=AdminOrganizationsResponse)
def delete_admin_organization_admin(organization_id: int, email: str, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid admin email is required")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        # Serialize with account purge, which can also remove an administrator.
        connection.execute("SELECT pg_advisory_xact_lock_shared(%s)", (8_044_001,))
        organization = _lock_active_organization_for_admin_write(connection, organization_id)
        target = connection.execute(
            """
            SELECT om.user_id
            FROM organization_memberships om
            JOIN users u ON u.id = om.user_id
            WHERE om.organization_id = %s AND LOWER(u.email) = %s AND om.role = 'admin'
            FOR UPDATE OF om
            """,
            (organization_id, normalized_email),
        ).fetchone()
        if target is not None:
            user_id = int(target["user_id"])
            _reject_platform_protected_account(connection, email=normalized_email, user_id=user_id)
            has_other_admin = connection.execute(
                """SELECT 1 FROM organization_memberships
                   WHERE organization_id=%s AND role='admin' AND user_id<>%s LIMIT 1""",
                (organization_id, user_id),
            ).fetchone()
            if not has_other_admin:
                raise HTTPException(status_code=409, detail="LAST_ORGANIZATION_ADMIN")
            connection.execute(
                """INSERT INTO configured_access_suppressions(
                       email,access_kind,organization_code,reason,created_by_user_id
                   ) VALUES(%s,'organization_admin',%s,'superadmin_revoke',%s)
                   ON CONFLICT(email,access_kind,organization_code) DO NOTHING""",
                (normalized_email, str(organization["code"]), int(user.id)),
            )
            connection.execute(
                """DELETE FROM organization_memberships
                   WHERE organization_id=%s AND user_id=%s
                     AND role='admin' AND is_participant=FALSE""",
                (organization_id, user_id),
            )
            # Carry forward sign-in admission for historical dual-role memberships.
            connection.execute(
                """UPDATE organization_memberships
                   SET role='member', updated_at=NOW(),
                       admission_source=CASE
                           WHEN admission_source IN ('configured_admin', 'legacy_unclassified') THEN 'admin_add'
                           ELSE admission_source
                       END
                   WHERE organization_id=%s AND user_id=%s
                     AND role='admin' AND is_participant=TRUE""",
                (organization_id, user_id),
            )
            connection.commit()
        return _build_admin_organizations(connection)


@router.post("/admin/organizations/{organization_id}/members", response_model=AdminOrganizationsResponse)
def add_admin_organization_member(organization_id: int, payload: AdminOrganizationMemberRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_email = normalize_email(payload.email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid member email is required")
    with get_connection() as connection:
        scope = _require_organization_admin(connection, user, organization_id)
        _attach_user_to_organization(
            connection,
            organization_id=organization_id,
            email=normalized_email,
            full_name=payload.full_name,
            role_description=payload.role_description,
            job_instructions=payload.job_instructions,
            admission_source="admin_add",
            admitted_by_user_id=int(user.id),
            expose_existing_organization=scope.is_superadmin,
        )
        connection.commit()
        return _build_admin_organizations(connection, scope)


@router.post("/admin/users/{user_id}/transfer-organization", response_model=AdminOrganizationsResponse)
def transfer_admin_organization_user(
    user_id: int,
    payload: AdminOrganizationTransferRequest,
    request: Request,
) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    actor = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, actor)
        raise HTTPException(status_code=410, detail="ORGANIZATION_TRANSFER_REMOVED")


@router.delete("/admin/organizations/{organization_id}/members", response_model=AdminOrganizationsResponse)
def delete_admin_organization_member(organization_id: int, email: str, request: Request) -> AdminOrganizationsResponse:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
        raise HTTPException(status_code=410, detail="MEMBER_EXCLUSION_REMOVED_USE_ACCOUNT_PURGE")


@router.post("/admin/organizations/{organization_id}/members/reset-password", response_model=AdminOrganizationsResponse)
def reset_admin_organization_member_password(organization_id: int, email: str, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid member email is required")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        user_row = connection.execute(
            """
            SELECT u.id
            FROM users u
            JOIN organization_memberships om ON om.user_id = u.id
            WHERE om.organization_id = %s
              AND LOWER(u.email) = %s
            LIMIT 1
            """,
            (organization_id, normalized_email),
        ).fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="Organization member not found")
        user_id = int(user_row["id"])
        deleted_credentials = connection.execute(
            """
            DELETE FROM auth_password_credentials
            WHERE LOWER(email) = %s
               OR user_id = %s
            """,
            (normalized_email, user_id),
        )
        if deleted_credentials.rowcount == 0:
            raise HTTPException(status_code=400, detail="Пароль пользователя еще не задан.")
        connection.execute("DELETE FROM web_user_sessions WHERE user_id = %s", (user_id,))
        connection.commit()
        logger.info(
            "Password reset by admin %s for organization_id=%s member=%s",
            str(user.email or "").strip().lower() if user else "",
            organization_id,
            normalized_email,
        )
        return _build_admin_organizations(connection)


@router.post(
    "/admin/organizations/{organization_id}/members/{user_id}/prepare-assessment",
    response_model=AssessmentPreparationEnqueueResponse,
    status_code=202,
)
def prepare_admin_organization_member_assessment(
    organization_id: int,
    user_id: int,
    request: Request,
) -> AssessmentPreparationEnqueueResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token)
    if current_user is not None and int(current_user.id) == int(user_id):
        raise HTTPException(status_code=403, detail="Нельзя назначить оценку самому себе.")
    operation_id = request.headers.get("X-Agent4K-Operation-Id") or uuid4().hex
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        row = connection.execute(
            USER_SELECT_SQL
            + """
            JOIN organization_memberships om ON om.user_id = u.id
            WHERE u.id = %s
              AND om.organization_id = %s
              AND om.is_participant = TRUE
            """,
            (user_id, organization_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Organization member not found")
    user = _user_response_from_row(row)
    if not evaluate_profile_state(user).is_complete:
        raise HTTPException(
            status_code=400,
            detail="Сначала заполните роль, должностные обязанности и сферу деятельности пользователя.",
        )
    operation_progress_service.begin(
        operation_id,
        title="Предварительно готовим кейсы",
        message="Задание поставлено в очередь фоновой подготовки.",
        steps=ASSESSMENT_START_STEPS,
    )
    queued = assessment_preparation_queue.enqueue(
        operation_id=operation_id,
        user=user,
        prepare_only=True,
    )
    return AssessmentPreparationEnqueueResponse(**queued)


def _build_assessment_preparation_batch_status(
    connection,
    batch_id: str,
) -> AssessmentPreparationBatchStatusResponse | None:
    batch = connection.execute(
        """
        SELECT batch_id, organization_id
        FROM assessment_preparation_batches
        WHERE batch_id = %s
        """,
        (batch_id,),
    ).fetchone()
    if batch is None:
        return None
    rows = connection.execute(
        """
        SELECT
            item.user_id,
            u.full_name,
            u.email,
            item.operation_id,
            CASE
                WHEN item.operation_id IS NULL THEN item.initial_status
                ELSE COALESCE(job.status, item.initial_status)
            END AS status,
            COALESCE(progress.title, '') AS progress_title,
            COALESCE(progress.message, item.status_message, '') AS progress_message
        FROM assessment_preparation_batch_items item
        JOIN users u ON u.id = item.user_id
        LEFT JOIN assessment_preparation_jobs job ON job.operation_id = item.operation_id
        LEFT JOIN operation_progress progress ON progress.operation_id = item.operation_id
        WHERE item.batch_id = %s
        ORDER BY item.id ASC
        """,
        (batch_id,),
    ).fetchall()
    participants = [
        AssessmentPreparationBatchParticipant(
            user_id=int(row["user_id"]),
            full_name=row["full_name"],
            email=str(row["email"] or ""),
            status=str(row["status"] or "queued"),
            operation_id=row["operation_id"],
            progress_title=str(row["progress_title"] or "") or None,
            progress_message=str(row["progress_message"] or "") or None,
        )
        for row in rows
    ]
    terminal_statuses = {"completed", "failed", "skipped"}
    completed = sum(item.status == "completed" for item in participants)
    failed = sum(item.status == "failed" for item in participants)
    skipped = sum(item.status == "skipped" for item in participants)
    processed = completed + failed + skipped
    current = next((item for item in participants if item.status == "running"), None)
    if current is None:
        current = next((item for item in participants if item.status == "queued"), None)
    if not participants or all(item.status in terminal_statuses for item in participants):
        status = "failed" if failed and not completed else "completed"
    else:
        status = "in_progress"
    return AssessmentPreparationBatchStatusResponse(
        batch_id=str(batch["batch_id"]),
        organization_id=int(batch["organization_id"]),
        status=status,
        total_participants=len(participants),
        processed_participants=processed,
        remaining_participants=max(0, len(participants) - processed),
        completed_participants=completed,
        failed_participants=failed,
        skipped_participants=skipped,
        current_participant=current,
        participants=participants,
    )


@router.post(
    "/admin/organizations/{organization_id}/prepare-assessments",
    response_model=AssessmentPreparationBatchEnqueueResponse,
    status_code=202,
)
def prepare_admin_organization_assessments(
    organization_id: int,
    request: Request,
) -> AssessmentPreparationBatchEnqueueResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token)
    batch_id = uuid4().hex
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        organization = connection.execute(
            "SELECT id FROM organizations WHERE id = %s AND is_active = TRUE",
            (organization_id,),
        ).fetchone()
        if organization is None:
            raise HTTPException(status_code=404, detail="Active organization not found")
        rows = connection.execute(
            USER_SELECT_SQL
            + """
            JOIN organization_memberships om ON om.user_id = u.id
            WHERE om.organization_id = %s
              AND om.is_participant = TRUE
              AND u.id <> %s
            ORDER BY u.id
            """,
            (organization_id, current_user.id if current_user else -1),
        ).fetchall()
        connection.execute(
            """
            INSERT INTO assessment_preparation_batches (
                batch_id, organization_id, created_by_user_id
            )
            VALUES (%s, %s, %s)
            """,
            (batch_id, organization_id, current_user.id if current_user else None),
        )

    queued_count = 0
    completed_count = 0
    skipped_count = 0
    for row in rows:
        user = _user_response_from_row(row)
        with get_connection() as connection:
            prepared = connection.execute(
                """
                SELECT 1
                FROM user_sessions
                WHERE user_id = %s
                  AND assessment_code = 'competencies_4k'
                  AND status IN ('created', 'active')
                LIMIT 1
                """,
                (user.id,),
            ).fetchone()
        if prepared is not None:
            initial_status = "completed"
            status_message = "Кейсы уже были подготовлены."
            operation_id = None
            completed_count += 1
        elif not evaluate_profile_state(user).is_complete:
            initial_status = "skipped"
            status_message = "Не заполнены роль, обязанности или сфера деятельности."
            operation_id = None
            skipped_count += 1
        else:
            requested_operation_id = uuid4().hex
            operation_progress_service.begin(
                requested_operation_id,
                title="Предварительно готовим кейсы",
                message="Задание поставлено в очередь фоновой подготовки.",
                steps=ASSESSMENT_START_STEPS,
            )
            queued = assessment_preparation_queue.enqueue(
                operation_id=requested_operation_id,
                user=user,
                prepare_only=True,
            )
            initial_status = str(queued["status"])
            status_message = "Поставлен в очередь подготовки."
            operation_id = str(queued["operation_id"])
            queued_count += 1
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO assessment_preparation_batch_items (
                    batch_id, user_id, operation_id, initial_status, status_message
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (batch_id, user.id, operation_id, initial_status, status_message),
            )
    return AssessmentPreparationBatchEnqueueResponse(
        batch_id=batch_id,
        organization_id=organization_id,
        total_participants=len(rows),
        queued_participants=queued_count,
        completed_participants=completed_count,
        skipped_participants=skipped_count,
    )


@router.get(
    "/admin/organizations/{organization_id}/prepare-assessments/{batch_id}",
    response_model=AssessmentPreparationBatchStatusResponse,
)
def get_admin_organization_assessment_preparation_batch(
    organization_id: int,
    batch_id: str,
    request: Request,
) -> AssessmentPreparationBatchStatusResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        result = _build_assessment_preparation_batch_status(connection, batch_id)
    if result is None or result.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Assessment preparation batch not found")
    return result


@router.post("/admin/organizations/{organization_id}/members/import", response_model=AdminOrganizationImportResult)
def import_admin_organization_members(
    organization_id: int,
    payload: AdminOrganizationMembersImportRequest,
    request: Request,
) -> AdminOrganizationImportResult:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    csv_text = str(payload.csv_text or "").strip("\ufeff\n\r ")
    if not csv_text:
        raise HTTPException(status_code=400, detail="CSV content is required")

    imported_count = 0
    skipped_count = 0
    errors: list[str] = []
    with get_connection() as connection:
        scope = _require_organization_admin(connection, user, organization_id)
        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV header is required")
        for line_number, row in enumerate(reader, start=2):
            email = normalize_email(_csv_value(row, "email", "e-mail", "mail"))
            if not email:
                skipped_count += 1
                errors.append(f"Строка {line_number}: email не указан или некорректен")
                continue
            full_name = _csv_value(row, "full_name", "name", "fio", "фио")
            role_description = _csv_value(
                row, "role_description", "position", "job_title", "role", "должность", "роль"
            )
            if not full_name or not role_description:
                skipped_count += 1
                missing = "ФИО и должность" if not full_name and not role_description else (
                    "ФИО" if not full_name else "должность"
                )
                errors.append(f"Строка {line_number}: не указаны обязательные поля: {missing}")
                continue
            try:
                _attach_user_to_organization(
                    connection,
                    organization_id=organization_id,
                    email=email,
                    full_name=full_name,
                    role_description=role_description,
                    job_instructions=_csv_value(row, "job_instructions", "duties", "instructions", "job_description", "обязанности", "инструкции"),
                    admission_source="csv_import",
                    admitted_by_user_id=int(user.id),
                )
                imported_count += 1
            except Exception as exc:
                skipped_count += 1
                errors.append(f"Строка {line_number}: {exc}")
        connection.commit()
        organizations = _build_admin_organizations(connection, scope)
    return AdminOrganizationImportResult(
        imported_count=imported_count,
        skipped_count=skipped_count,
        errors=errors[:20],
        organizations=organizations,
    )


@router.get("/admin/organizations/{organization_id}/questionnaire/template")
def download_admin_organization_questionnaire_template(organization_id: int, request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
    return Response(
        content="\ufeff" + questionnaire_sources.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="p4k-corporate-questionnaire-0.2.csv"'},
    )


@router.get("/admin/organizations/{organization_id}/questionnaire")
def list_admin_organization_questionnaire_revisions(organization_id: int, request: Request) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
        rows = connection.execute(
            """SELECT revision.*, uploader.email AS uploaded_by_email,
                      uploader.full_name AS uploaded_by_name
               FROM questionnaire_response_revisions revision
               LEFT JOIN users uploader ON uploader.id=revision.uploaded_by_user_id
               WHERE revision.organization_id=%s
               ORDER BY revision.created_at DESC,revision.id DESC LIMIT 100""",
            (organization_id,),
        ).fetchall()
        latest = {}
        for row in rows:
            key = str(row["assignment_ref"])
            if key not in latest:
                confirmed = connection.execute(
                    """SELECT * FROM questionnaire_response_revisions
                       WHERE organization_id=%s AND assignment_ref=%s AND status='confirmed'
                       ORDER BY confirmed_at DESC,id DESC LIMIT 1""",
                    (organization_id, key),
                ).fetchone()
                latest[key] = {
                    **questionnaire_sources.public_revision(
                        dict(row), confirmed_row=dict(confirmed) if confirmed is not None else None,
                    ),
                    "readiness": questionnaire_sources.admin_assignment_readiness(
                        connection, organization_id=organization_id, assignment_ref=key,
                    ),
                }
        return {"items": list(latest.values())}


@router.post("/admin/organizations/{organization_id}/questionnaire/preview", status_code=201)
def preview_admin_organization_questionnaire(
    organization_id: int, payload: QuestionnairePreviewRequest, request: Request,
) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
        try:
            assessment_programs.validate_questionnaire_assignment(
                connection, organization_id=organization_id,
                assignment_ref=payload.assignment_ref,
            )
            result = questionnaire_sources.save_preview(
                connection, organization_id=organization_id, assignment_ref=payload.assignment_ref,
                channel=payload.channel, template_variant=payload.template_variant,
                template_version=payload.template_version, answers=payload.answers,
                raw_text=payload.csv_text, uploaded_by=int(user.id),
                source_author="", idempotency_key=payload.idempotency_key,
            )
            uploader = connection.execute(
                "SELECT email,full_name FROM users WHERE id=%s",
                (int(user.id),),
            ).fetchone()
            if uploader is not None:
                result = {
                    **result,
                    "uploaded_by_email": uploader["email"],
                    "uploaded_by_name": uploader["full_name"],
                }
            confirmed = connection.execute(
                """SELECT * FROM questionnaire_response_revisions
                   WHERE organization_id=%s AND assignment_ref=%s AND status='confirmed' AND id<>%s
                   ORDER BY confirmed_at DESC,id DESC LIMIT 1""",
                (organization_id, payload.assignment_ref, result["id"]),
            ).fetchone()
            connection.commit()
            return {
                **questionnaire_sources.public_revision(
                    result, confirmed_row=dict(confirmed) if confirmed is not None else None,
                ),
                "expected_organization_name": (result.get("validation_json") or {}).get("expected_organization_name"),
                "readiness": questionnaire_sources.admin_assignment_readiness(
                    connection, organization_id=organization_id, assignment_ref=payload.assignment_ref,
                ),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/organizations/{organization_id}/questionnaire/{revision_id}")
def get_admin_organization_questionnaire_revision(organization_id: int, revision_id: int, request: Request) -> dict:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
        row = connection.execute(
            """SELECT revision.*, uploader.email AS uploaded_by_email,
                      uploader.full_name AS uploaded_by_name
               FROM questionnaire_response_revisions revision
               LEFT JOIN users uploader ON uploader.id=revision.uploaded_by_user_id
               WHERE revision.id=%s AND revision.organization_id=%s""",
            (revision_id, organization_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="QUESTIONNAIRE_REVISION_NOT_FOUND")
        current_name = connection.execute(
            "SELECT name FROM organizations WHERE id=%s", (organization_id,),
        ).fetchone()["name"]
        return {**questionnaire_sources.public_revision(dict(row)), "organization_name_current": current_name}


@router.post("/admin/organizations/{organization_id}/questionnaire/{revision_id}/confirm")
def confirm_admin_organization_questionnaire(
    organization_id: int, revision_id: int, payload: QuestionnaireConfirmRequest, request: Request,
) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_organization_admin(connection, user, organization_id)
        # Organization admins confirm in their scope. A platform superadmin may record
        # customer-confirmed data only with the source_author already stored by preview.
        membership = connection.execute(
            "SELECT 1 FROM organization_memberships WHERE organization_id=%s AND user_id=%s AND role='admin'",
            (organization_id, int(user.id)),
        ).fetchone()
        scope = get_admin_scope(connection, user)
        if membership is None and not scope.is_superadmin:
            raise HTTPException(status_code=403, detail="Organization responsible confirmation required")
        try:
            candidate = connection.execute(
                "SELECT assignment_ref FROM questionnaire_response_revisions WHERE id=%s AND organization_id=%s",
                (revision_id, organization_id),
            ).fetchone()
            if candidate is None:
                raise ValueError("QUESTIONNAIRE_REVISION_NOT_FOUND")
            assessment_programs.validate_questionnaire_assignment(
                connection, organization_id=organization_id,
                assignment_ref=str(candidate['assignment_ref']),
            )
            result = questionnaire_sources.confirm(
                connection, revision_id=revision_id, organization_id=organization_id,
                confirmed_by=int(user.id),
            )
            connection.commit()
            confirmed = questionnaire_sources.public_revision(result)
            confirmed["organization_name_current"] = connection.execute(
                "SELECT name FROM organizations WHERE id=%s", (organization_id,),
            ).fetchone()["name"]
            try:
                confirmed["readiness"] = questionnaire_sources.admin_assignment_readiness(
                    connection, organization_id=organization_id,
                    assignment_ref=str(result["assignment_ref"]),
                )
            except Exception:
                # Confirmation was committed. A supplementary read cannot undo it.
                connection.rollback()
                logger.exception("Questionnaire readiness unavailable after confirmation")
                confirmed["readiness"] = None
                confirmed["readiness_refresh_required"] = True
            return confirmed
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.api_route('/admin/reports', methods=['GET', 'POST', 'PATCH'])
@router.api_route('/admin/reports.pdf', methods=['GET'])
@router.api_route('/admin/reports/{legacy_path:path}', methods=['GET', 'POST', 'PATCH'])
def retired_admin_reports(request: Request, legacy_path: str = ''):
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail='Требуется авторизация')
    raise HTTPException(410, detail='Старый маршрут отчётов закрыт. Откройте список индивидуальных Report.')


def _normalize_admin_case_role_ids(raw_role_ids: list[int], available_role_ids: set[int]) -> list[int]:
    unique_ids: list[int] = []
    seen: set[int] = set()
    for value in raw_role_ids:
        try:
            role_id = int(value)
        except (TypeError, ValueError):
            continue
        if role_id not in available_role_ids or role_id in seen:
            continue
        seen.add(role_id)
        unique_ids.append(role_id)
    return unique_ids


def _normalize_admin_case_skill_ids(raw_skill_ids: list[int], available_skill_ids: set[int]) -> list[int]:
    unique_ids: list[int] = []
    seen: set[int] = set()
    for value in raw_skill_ids:
        try:
            skill_id = int(value)
        except (TypeError, ValueError):
            continue
        if skill_id not in available_skill_ids or skill_id in seen:
            continue
        seen.add(skill_id)
        unique_ids.append(skill_id)
    return unique_ids


def _upsert_admin_methodology_case(
    connection,
    case_id_code: str,
    payload: AdminMethodologyCaseUpdateRequest,
    changed_by: str,
) -> AdminMethodologyCaseDetailResponse:
    case_row = connection.execute(
        """
        SELECT id, title, difficulty_level, estimated_time_min, trigger_event, stakeholders_text, status, case_type_passport_id
        FROM cases_registry
        WHERE case_id_code = %s
        LIMIT 1
        """,
        (case_id_code,),
    ).fetchone()
    if case_row is None:
        raise HTTPException(status_code=404, detail="Case not found")

    case_registry_id = int(case_row["id"])
    available_role_rows = connection.execute(
        """
        SELECT id
        FROM roles
        WHERE code IN ('linear_employee', 'manager', 'leader')
        """
    ).fetchall()
    available_skill_rows = connection.execute("SELECT id FROM skills").fetchall()
    available_role_ids = {int(row["id"]) for row in available_role_rows}
    available_skill_ids = {int(row["id"]) for row in available_skill_rows}
    current_role_rows = connection.execute(
        "SELECT role_id FROM case_registry_roles WHERE cases_registry_id = %s ORDER BY role_id ASC",
        (case_registry_id,),
    ).fetchall()
    current_skill_rows = connection.execute(
        "SELECT skill_id FROM case_registry_skills WHERE cases_registry_id = %s ORDER BY display_order ASC, skill_id ASC",
        (case_registry_id,),
    ).fetchall()

    normalized_role_ids = _normalize_admin_case_role_ids(payload.role_ids, available_role_ids)
    normalized_skill_ids = _normalize_admin_case_skill_ids(payload.skill_ids, available_skill_ids)
    normalized_difficulty = "hard" if str(payload.difficulty_level).strip().lower() == "hard" else "base"
    normalized_case_status = _normalize_methodology_status(payload.case_status)
    normalized_text_status = _normalize_methodology_status(payload.case_text_status)
    normalized_passport_status = _normalize_methodology_status(payload.passport_status)
    normalized_estimated_time = int(payload.estimated_time_min) if payload.estimated_time_min and int(payload.estimated_time_min) > 0 else None
    normalized_title = (payload.title or "").strip() or "Без названия"
    normalized_trigger_event = (payload.trigger_event or "").strip() or None
    normalized_stakeholders_text = (payload.stakeholders_text or "").strip() or None
    normalized_interactivity_mode = (payload.interactivity_mode or "").strip() or None
    normalized_recommended_answer_length = (payload.recommended_answer_length or "").strip() or None
    normalized_selection_tags = [str(item).strip() for item in (payload.selection_tags or []) if str(item).strip()]
    normalized_role_personalization_rules = (payload.role_personalization_rules or "").strip() or None
    normalized_format_control_rules = (payload.format_control_rules or "").strip() or None
    normalized_scoring_aggregation_rules = (payload.scoring_aggregation_rules or "").strip() or None
    normalized_bad_case_risks = (payload.bad_case_risks or "").strip() or None
    normalized_generation_notes = (payload.generation_notes or "").strip() or None
    normalized_personalization_items = _normalize_admin_personalization_payload_items(payload.personalization_items)
    passport_row = connection.execute(
        """
        SELECT
            id,
            status,
            interactivity_mode,
            recommended_answer_length,
            selection_tags,
            role_personalization_rules,
            format_control_rules,
            scoring_aggregation_rules,
            bad_case_risks,
            generation_notes
        FROM case_type_passports
        WHERE id = %s
        LIMIT 1
        """,
        (case_row["case_type_passport_id"],),
    ).fetchone()
    current_role_ids = [int(row["role_id"]) for row in current_role_rows]
    current_skill_ids = [int(row["skill_id"]) for row in current_skill_rows]
    role_mapping_changed = current_role_ids != normalized_role_ids
    skill_mapping_changed = current_skill_ids != normalized_skill_ids
    registry_changed = (
        (case_row["title"] or "") != normalized_title
        or (case_row["difficulty_level"] or "base") != normalized_difficulty
        or (case_row["estimated_time_min"] if case_row["estimated_time_min"] is not None else None) != normalized_estimated_time
        or (case_row["trigger_event"] if case_row["trigger_event"] is not None else None) != normalized_trigger_event
        or (case_row["stakeholders_text"] if case_row["stakeholders_text"] is not None else None) != normalized_stakeholders_text
        or (case_row["status"] or "draft") != normalized_case_status
        or role_mapping_changed
        or skill_mapping_changed
    )
    passport_changed = passport_row is not None and (
        (passport_row["status"] or "draft") != normalized_passport_status
        or (passport_row["interactivity_mode"] if passport_row["interactivity_mode"] is not None else None) != normalized_interactivity_mode
        or (passport_row["recommended_answer_length"] if passport_row["recommended_answer_length"] is not None else None) != normalized_recommended_answer_length
        or list(passport_row["selection_tags"] or []) != normalized_selection_tags
        or (passport_row["role_personalization_rules"] if passport_row["role_personalization_rules"] is not None else None) != normalized_role_personalization_rules
        or (passport_row["format_control_rules"] if passport_row["format_control_rules"] is not None else None) != normalized_format_control_rules
        or (passport_row["scoring_aggregation_rules"] if passport_row["scoring_aggregation_rules"] is not None else None) != normalized_scoring_aggregation_rules
        or (passport_row["bad_case_risks"] if passport_row["bad_case_risks"] is not None else None) != normalized_bad_case_risks
        or (passport_row["generation_notes"] if passport_row["generation_notes"] is not None else None) != normalized_generation_notes
    )

    connection.execute(
        """
        UPDATE cases_registry
        SET
            title = %s,
            difficulty_level = %s,
            estimated_time_min = %s,
            trigger_event = %s,
            stakeholders_text = %s,
            status = %s,
            version = CASE WHEN %s THEN version + 1 ELSE version END,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            normalized_title,
            normalized_difficulty,
            normalized_estimated_time,
            normalized_trigger_event,
            normalized_stakeholders_text,
            normalized_case_status,
            registry_changed,
            case_registry_id,
        ),
    )
    if passport_row is not None:
        connection.execute(
            """
            UPDATE case_type_passports
            SET
                status = %s,
                interactivity_mode = %s,
                recommended_answer_length = %s,
                selection_tags = %s::jsonb,
                role_personalization_rules = %s,
                format_control_rules = %s,
                scoring_aggregation_rules = %s,
                bad_case_risks = %s,
                generation_notes = %s,
                version = CASE WHEN %s THEN version + 1 ELSE version END,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                normalized_passport_status,
                normalized_interactivity_mode,
                normalized_recommended_answer_length,
                json.dumps(normalized_selection_tags, ensure_ascii=False),
                normalized_role_personalization_rules,
                normalized_format_control_rules,
                normalized_scoring_aggregation_rules,
                normalized_bad_case_risks,
                normalized_generation_notes,
                passport_changed,
                passport_row["id"],
            ),
        )

    existing_text_row = connection.execute(
        """
        SELECT
            id,
            intro_context,
            facts_data,
            participants_roles,
            trigger_details,
            task_for_user,
            expected_artifact,
            answer_structure_hint,
            constraints_text,
            dialog_turns_hint,
            stakes_text,
            personalization_variables,
            personalization_options,
            difficulty_toggles,
            evaluation_notes,
            author_name,
            reviewer_name,
            methodologist_comment,
            status
        FROM case_texts
        WHERE cases_registry_id = %s
        LIMIT 1
        """,
        (case_registry_id,),
    ).fetchone()
    if existing_text_row is None:
        normalized_intro_context = (payload.intro_context or "").strip() or ""
        normalized_facts_data = (payload.facts_data or "").strip() or None
        normalized_participants_roles = (payload.participants_roles or "").strip() or None
        normalized_trigger_details = (payload.trigger_details or "").strip() or None
        normalized_task_for_user = (payload.task_for_user or "").strip() or ""
        normalized_expected_artifact = (payload.expected_artifact or "").strip() or None
        normalized_answer_structure_hint = (payload.answer_structure_hint or "").strip() or None
        normalized_constraints_text = (payload.constraints_text or "").strip() or None
        normalized_dialog_turns_hint = (payload.dialog_turns_hint or "").strip() or None
        normalized_stakes_text = (payload.stakes_text or "").strip() or None
        normalized_personalization_codes = [item[0] for item in normalized_personalization_items] or _extract_admin_personalization_codes(
            normalized_intro_context,
            normalized_facts_data,
            normalized_task_for_user,
            normalized_constraints_text,
        )
        normalized_personalization_variables = _build_admin_personalization_variable_string(normalized_personalization_codes)
        normalized_personalization_options = (payload.personalization_options_text or "").strip() or None
        normalized_difficulty_toggles = (payload.difficulty_toggles or "").strip() or None
        normalized_evaluation_notes = (payload.evaluation_notes or "").strip() or None
        normalized_author_name = (payload.author_name or "").strip() or None
        normalized_reviewer_name = (payload.reviewer_name or "").strip() or None
        normalized_methodologist_comment = (payload.methodologist_comment or "").strip() or None
        inserted_text_row = connection.execute(
            """
            INSERT INTO case_texts (
                case_text_code,
                cases_registry_id,
                intro_context,
                facts_data,
                participants_roles,
                trigger_details,
                task_for_user,
                expected_artifact,
                answer_structure_hint,
                constraints_text,
                dialog_turns_hint,
                stakes_text,
                personalization_variables,
                personalization_options,
                difficulty_toggles,
                evaluation_notes,
                author_name,
                reviewer_name,
                methodologist_comment,
                status,
                version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            RETURNING id
            """,
            (
                f"TXT-{case_id_code}",
                case_registry_id,
                normalized_intro_context,
                normalized_facts_data,
                normalized_participants_roles,
                normalized_trigger_details,
                normalized_task_for_user,
                normalized_expected_artifact,
                normalized_answer_structure_hint,
                normalized_constraints_text,
                normalized_dialog_turns_hint,
                normalized_stakes_text,
                normalized_personalization_variables,
                normalized_personalization_options,
                normalized_difficulty_toggles,
                normalized_evaluation_notes,
                normalized_author_name,
                normalized_reviewer_name,
                normalized_methodologist_comment,
                normalized_text_status,
            ),
        ).fetchone()
        case_text_id = int(inserted_text_row["id"])
        text_changed = True
    else:
        case_text_id = int(existing_text_row["id"])
        normalized_intro_context = (payload.intro_context or "").strip() or ""
        normalized_facts_data = (payload.facts_data or "").strip() or None
        normalized_participants_roles = (payload.participants_roles or "").strip() or None
        normalized_trigger_details = (payload.trigger_details or "").strip() or None
        normalized_task_for_user = (payload.task_for_user or "").strip() or ""
        normalized_expected_artifact = (payload.expected_artifact or "").strip() or None
        normalized_answer_structure_hint = (payload.answer_structure_hint or "").strip() or None
        normalized_constraints_text = (payload.constraints_text or "").strip() or None
        normalized_dialog_turns_hint = (payload.dialog_turns_hint or "").strip() or None
        normalized_stakes_text = (payload.stakes_text or "").strip() or None
        normalized_personalization_codes = [item[0] for item in normalized_personalization_items] or _extract_admin_personalization_codes(
            normalized_intro_context,
            normalized_facts_data,
            normalized_task_for_user,
            normalized_constraints_text,
        )
        normalized_personalization_variables = _build_admin_personalization_variable_string(normalized_personalization_codes)
        normalized_personalization_options = (payload.personalization_options_text or "").strip() or None
        normalized_difficulty_toggles = (payload.difficulty_toggles or "").strip() or None
        normalized_evaluation_notes = (payload.evaluation_notes or "").strip() or None
        normalized_author_name = (payload.author_name or "").strip() or None
        normalized_reviewer_name = (payload.reviewer_name or "").strip() or None
        normalized_methodologist_comment = (payload.methodologist_comment or "").strip() or None
        text_changed = (
            (existing_text_row["intro_context"] or "") != normalized_intro_context
            or (existing_text_row["facts_data"] if existing_text_row["facts_data"] is not None else None) != normalized_facts_data
            or (existing_text_row["participants_roles"] if existing_text_row["participants_roles"] is not None else None) != normalized_participants_roles
            or (existing_text_row["trigger_details"] if existing_text_row["trigger_details"] is not None else None) != normalized_trigger_details
            or (existing_text_row["task_for_user"] or "") != normalized_task_for_user
            or (existing_text_row["expected_artifact"] if existing_text_row["expected_artifact"] is not None else None) != normalized_expected_artifact
            or (existing_text_row["answer_structure_hint"] if existing_text_row["answer_structure_hint"] is not None else None) != normalized_answer_structure_hint
            or (existing_text_row["constraints_text"] if existing_text_row["constraints_text"] is not None else None) != normalized_constraints_text
            or (existing_text_row["dialog_turns_hint"] if existing_text_row["dialog_turns_hint"] is not None else None) != normalized_dialog_turns_hint
            or (existing_text_row["stakes_text"] if existing_text_row["stakes_text"] is not None else None) != normalized_stakes_text
            or (existing_text_row["personalization_variables"] if existing_text_row["personalization_variables"] is not None else None) != normalized_personalization_variables
            or (existing_text_row["personalization_options"] if existing_text_row["personalization_options"] is not None else None) != normalized_personalization_options
            or (existing_text_row["difficulty_toggles"] if existing_text_row["difficulty_toggles"] is not None else None) != normalized_difficulty_toggles
            or (existing_text_row["evaluation_notes"] if existing_text_row["evaluation_notes"] is not None else None) != normalized_evaluation_notes
            or (existing_text_row["author_name"] if existing_text_row["author_name"] is not None else None) != normalized_author_name
            or (existing_text_row["reviewer_name"] if existing_text_row["reviewer_name"] is not None else None) != normalized_reviewer_name
            or (existing_text_row["methodologist_comment"] if existing_text_row["methodologist_comment"] is not None else None) != normalized_methodologist_comment
            or (existing_text_row["status"] or "draft") != normalized_text_status
        )
        connection.execute(
            """
            UPDATE case_texts
            SET
                intro_context = %s,
                facts_data = %s,
                participants_roles = %s,
                trigger_details = %s,
                task_for_user = %s,
                expected_artifact = %s,
                answer_structure_hint = %s,
                constraints_text = %s,
                dialog_turns_hint = %s,
                stakes_text = %s,
                personalization_variables = %s,
                personalization_options = %s,
                difficulty_toggles = %s,
                evaluation_notes = %s,
                author_name = %s,
                reviewer_name = %s,
                methodologist_comment = %s,
                status = %s,
                version = CASE WHEN %s THEN version + 1 ELSE version END,
                updated_at = NOW()
            WHERE cases_registry_id = %s
            """,
            (
                normalized_intro_context,
                normalized_facts_data,
                normalized_participants_roles,
                normalized_trigger_details,
                normalized_task_for_user,
                normalized_expected_artifact,
                normalized_answer_structure_hint,
                normalized_constraints_text,
                normalized_dialog_turns_hint,
                normalized_stakes_text,
                normalized_personalization_variables,
                normalized_personalization_options,
                normalized_difficulty_toggles,
                normalized_evaluation_notes,
                normalized_author_name,
                normalized_reviewer_name,
                normalized_methodologist_comment,
                normalized_text_status,
                text_changed,
                case_registry_id,
            ),
        )
    connection.execute("DELETE FROM case_text_personalization_values WHERE case_text_id = %s", (case_text_id,))

    connection.execute("DELETE FROM case_registry_roles WHERE cases_registry_id = %s", (case_registry_id,))
    for role_id in normalized_role_ids:
        connection.execute(
            """
            INSERT INTO case_registry_roles (cases_registry_id, role_id)
            VALUES (%s, %s)
            """,
            (case_registry_id, role_id),
        )

    connection.execute("DELETE FROM case_registry_skills WHERE cases_registry_id = %s", (case_registry_id,))
    for index, skill_id in enumerate(normalized_skill_ids, start=1):
        connection.execute(
            """
            INSERT INTO case_registry_skills (cases_registry_id, skill_id, signal_priority, is_required, display_order)
            VALUES (%s, %s, %s, TRUE, %s)
            """,
            (
                case_registry_id,
                skill_id,
                "leading" if index <= 2 else "supporting",
                index,
            ),
        )

    recompute_case_quality_checks(connection, case_registry_id)
    change_summaries: list[tuple[str, str, str]] = []
    if registry_changed:
        change_summaries.append(("case_registry", "updated", f"Обновлены параметры кейса. Статус кейса: {normalized_case_status}."))
    if text_changed:
        change_summaries.append(("case_text", "updated", f"Обновлен текст кейса. Статус текста: {normalized_text_status}."))
    if passport_changed:
        change_summaries.append(("case_type_passport", "status_changed", f"Изменен статус типа кейса: {normalized_passport_status}."))
    if role_mapping_changed:
        change_summaries.append(("case_roles", "updated", "Обновлен набор ролей кейса."))
    if skill_mapping_changed:
        change_summaries.append(("case_skills", "updated", "Обновлен набор навыков кейса."))
    if text_changed:
        change_summaries.append(("case_personalization", "updated", "Список переменных персонализации пересчитан из текста шаблона."))
    if normalized_case_status == "retired" or normalized_text_status == "retired" or normalized_passport_status == "retired":
        change_summaries.append(("lifecycle", "archived", "Кейс или связанные методические сущности переведены в архивный статус."))
    for entity_scope, action, summary in change_summaries:
        connection.execute(
            """
            INSERT INTO case_methodology_change_log (
                case_registry_id,
                entity_scope,
                action,
                summary,
                payload,
                changed_by
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                case_registry_id,
                entity_scope,
                action,
                summary,
                None,
                changed_by,
            ),
        )
    connection.commit()
    return _build_admin_methodology_case_detail(connection, case_id_code)


def _build_prompt_lab_dashboard(connection) -> PromptLabDashboard:
    production_instruction_row = connection.execute(
        """
        SELECT instruction_code, instruction_name, instruction_text, version
        FROM case_text_build_instructions
        WHERE is_active = TRUE
          AND applies_to_type_code IS NULL
        ORDER BY priority ASC, version DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    interviewer_prompt_row = connection.execute(
        """
        SELECT prompt_code, prompt_name, prompt_text, prompt_version
        FROM interviewer_agent_prompts
        WHERE prompt_code = 'case_follow_up'
          AND is_active = TRUE
        ORDER BY prompt_version DESC, prompt_code ASC
        LIMIT 1
        """
    ).fetchone()
    user_rows = connection.execute(
        """
        SELECT
            u.id,
            u.full_name,
            u.phone,
            u.role_id,
            COALESCE(p.raw_position, u.job_description) AS position,
            COALESCE(p.normalized_duties, p.raw_duties) AS duties,
            u.company_industry,
            to_jsonb(p) AS user_profile,
            r.name AS role_name
        FROM users u
        LEFT JOIN roles r ON r.id = u.role_id
        LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
        WHERE COALESCE(r.code, '') <> %s
        ORDER BY u.created_at DESC, u.id DESC
        LIMIT 100
        """,
        (ADMIN_ROLE_CODE,),
    ).fetchall()
    case_rows = connection.execute(
        """
        SELECT
            cr.case_id_code,
            cr.title,
            p.type_code,
            p.interactivity_mode,
            CASE
                WHEN LOWER(COALESCE(p.interactivity_mode, '')) LIKE '%%диалог%%' THEN TRUE
                ELSE FALSE
            END AS is_dialog_case,
            COALESCE(array_agg(DISTINCT r.name) FILTER (WHERE r.name IS NOT NULL), ARRAY[]::text[]) AS role_names
        FROM cases_registry cr
        JOIN case_type_passports p ON p.id = cr.case_type_passport_id
        LEFT JOIN case_registry_roles crr ON crr.cases_registry_id = cr.id
        LEFT JOIN roles r ON r.id = crr.role_id
        WHERE cr.status = 'ready'
        GROUP BY cr.case_id_code, cr.title, p.type_code, p.interactivity_mode
        ORDER BY cr.case_id_code ASC
        LIMIT 200
        """
    ).fetchall()
    role_rows = connection.execute(
        """
        SELECT id, code, name
        FROM roles
        WHERE code <> %s
        ORDER BY id ASC
        """,
        (ADMIN_ROLE_CODE,),
    ).fetchall()
    return PromptLabDashboard(
        prompts=[],
        users=[PromptLabUserOption(**dict(row)) for row in user_rows],
        cases=[PromptLabCaseOption(**dict(row)) for row in case_rows],
        role_options=[dict(row) for row in role_rows],
        recent_runs=[],
        production_prompt_text=(production_instruction_row["instruction_text"] if production_instruction_row else None),
        production_prompt_name=(production_instruction_row["instruction_name"] if production_instruction_row else None),
        production_instruction_code=(production_instruction_row["instruction_code"] if production_instruction_row else None),
        production_instruction_version=(production_instruction_row["version"] if production_instruction_row else None),
        interviewer_prompt_text=(interviewer_prompt_row["prompt_text"] if interviewer_prompt_row else None),
        interviewer_prompt_name=(interviewer_prompt_row["prompt_name"] if interviewer_prompt_row else None),
        interviewer_prompt_code=(interviewer_prompt_row["prompt_code"] if interviewer_prompt_row else None),
        interviewer_prompt_version=(interviewer_prompt_row["prompt_version"] if interviewer_prompt_row else None),
    )


def _get_prompt_lab_prompt(connection, prompt_id: int | None):
    if prompt_id is None:
        return None
    return connection.execute(
        """
        SELECT id, name, prompt_text, created_by, created_at
        FROM prompt_lab_case_prompts
        WHERE id = %s
        """,
        (prompt_id,),
    ).fetchone()


@router.get("/admin/prompt-lab", response_model=PromptLabDashboard)
def get_prompt_lab_dashboard(request: Request) -> PromptLabDashboard:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        return _build_prompt_lab_dashboard(connection)


@router.get("/admin/m5-lab")
def get_m5_lab_catalog(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, user)
        package = json.loads((M5_PACKAGE_DIR / "case-package.json").read_text())
        return m5_storage.qa_lab_catalog(connection, package)


@router.post("/admin/m5-lab/migrate-current-profile")
def migrate_current_profile_to_m4(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, user)
        try:
            result = m5_storage.migrate_legacy_test_profile(
                connection, user_id=int(user.id), authorized_by=int(user.id))
            connection.commit()
            return result
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-lab/publish-m3-base-roles")
def publish_m3_base_roles_for_m5_lab(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, user)
        try:
            package = json.loads((M3_ROLE_PACKAGE_DIR / "base_roles.json").read_text(encoding="utf-8"))
            manifest = json.loads((M3_ROLE_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
            result = publish_base_roles(
                connection,
                package=package,
                manifest=manifest,
                published_by_user_id=int(user.id),
                decision_basis="Владелец подтвердил human review и публикацию M3 v1.1 для test 2026-10-01",
            )
            connection.commit()
            return result
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-lab/publish-m2-qa-configuration")
def publish_m2_qa_configuration_for_m5_lab(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, user)
        try:
            result = publish_m2_qa_configuration(
                connection,
                published_by_user_id=int(user.id),
                decision_basis="Владелец подтвердил human review и публикацию M2 v1.1 для test 2026-10-01",
            )
            connection.commit()
            return result
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/admin/m5-lab/runs/{run_id}")
def get_m5_lab_run(run_id: UUID, request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, user)
        runtime_row = connection.execute("""
            SELECT r.*, s.assessment_situation_id, s.status AS as_status, s.snapshot_json
            FROM m5_runtime_lab_runs r JOIN m5_assessment_situations s ON s.id=r.assessment_situation_db_id
            WHERE r.run_id=%s
        """, (run_id,)).fetchone()
        if runtime_row is None:
            raise HTTPException(status_code=404, detail="Прогон M5 не найден")
        result = dict(runtime_row)
        result["trace"] = m5_scenario_runtime.trace(connection, str(runtime_row["assessment_situation_id"]))
        return result


@router.post("/admin/m5-lab/runs")
def create_m5_lab_run(payload: M5LabRuntimeRequest, request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, user)
        try:
            existing = connection.execute("""
                SELECT r.*, s.assessment_situation_id, s.status AS as_status, s.snapshot_json
                FROM m5_runtime_lab_runs r JOIN m5_assessment_situations s ON s.id=r.assessment_situation_db_id
                WHERE r.run_id=%s
            """, (payload.run_id,)).fetchone()
            request_checksum = m5_generation_lab.digest(m5_generation_lab.json_bytes(payload.model_dump(mode="json")))
            if existing:
                if existing["created_by"] != int(user.id) or existing["request_checksum"] != request_checksum:
                    raise ValueError("run_id уже использован с другим запросом")
                result = dict(existing)
                result["trace"] = m5_scenario_runtime.trace(connection, str(existing["assessment_situation_id"]))
                return result
            m5_storage.import_package_directory(connection, M5_PACKAGE_DIR)
            policy = json.loads((M5_PACKAGE_DIR / "admission-policy.json").read_text())
            cycle, session = m5_cycle_runtime.create_cycle_session_for_case(
                connection, personalized_profile_id=payload.personalized_profile_id,
                case_id=payload.case_id, case_version=payload.case_version,
                created_by=int(user.id), usage_scope="qa",
            )
            prepared = m5_storage.prepare_assessment_situation(
                connection, assessment_situation_id=str(uuid4()), case_id=payload.case_id,
                case_version=payload.case_version, personalized_profile_id=payload.personalized_profile_id,
                cycle_db_id=int(cycle["id"]), session_db_id=int(session["id"]),
                substitutions=payload.substitutions, policy=policy, usage_scope="qa", qa_authorized_by=int(user.id),
            )
            started = m5_scenario_runtime.start(connection, prepared["assessment_situation_id"])
            lab_row = connection.execute("""
                INSERT INTO m5_runtime_lab_runs
                    (run_id,created_by,assessment_situation_db_id,request_checksum,status)
                VALUES (%s,%s,%s,%s,'active') RETURNING *
            """, (payload.run_id, int(user.id), prepared["id"], request_checksum)).fetchone()
            connection.commit()
            return {**dict(lab_row), "assessment_situation_id": prepared["assessment_situation_id"],
                    "cycle_id": str(cycle["cycle_id"]), "session_id": str(session["session_id"]),
                    "as_status": "active", "snapshot_json": prepared["snapshot"],
                    "participant_payload": started["participant_payload"],
                    "trace": m5_scenario_runtime.trace(connection, prepared["assessment_situation_id"])}
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


def _m5_superadmin(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, user)
    return user


def _m5_owned_situation(request: Request, assessment_situation_id: str) -> None:
    from Api.qa_orchestration import permits
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия не найдена. Войдите заново.")
    with get_connection() as connection:
        row = connection.execute("""
            SELECT p.user_id, s.usage_scope
            FROM m5_assessment_situations s
            JOIN assessment_personalized_profiles p ON p.id=s.personalized_profile_id
            WHERE s.assessment_situation_id=%s
        """, (UUID(assessment_situation_id),)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="M5_AS_NOT_FOUND")
    if int(row["user_id"]) != int(user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к чужой Assessment Situation.")
    if not permits(row["usage_scope"]):
        raise HTTPException(status_code=403, detail="QA_AS_NOT_AVAILABLE_IN_PRODUCT_ROUTE")
    return user


def _m7_owned_cycle(request:Request,cycle_id:str):
    from Api.qa_orchestration import permits
    token=request.cookies.get(SESSION_COOKIE_NAME);user=web_session_service.get_user_by_token(token) if token else None
    if user is None:raise HTTPException(status_code=401,detail='Сессия не найдена. Войдите заново.')
    with get_connection() as connection:
        row=connection.execute('SELECT owner_user_id,usage_scope FROM m5_cycles WHERE cycle_id=%s',(UUID(cycle_id),)).fetchone()
    if not row:raise HTTPException(status_code=404,detail='M7_CYCLE_NOT_FOUND')
    if int(row['owner_user_id'])!=int(user.id):raise HTTPException(status_code=403,detail='Нет доступа к чужому Assessment Cycle.')
    if not permits(row['usage_scope']):raise HTTPException(status_code=403,detail='QA_CYCLE_NOT_AVAILABLE_IN_PRODUCT_ROUTE')
    return user


def _m7_owned_clarification(request:Request,decision_id:str):
    from Api.qa_orchestration import permits
    token=request.cookies.get(SESSION_COOKIE_NAME);user=web_session_service.get_user_by_token(token) if token else None
    if user is None:raise HTTPException(status_code=401,detail='Сессия не найдена. Войдите заново.')
    with get_connection() as connection:
        row=connection.execute("""SELECT c.owner_user_id,c.usage_scope FROM m7_clarification_decisions d
            JOIN m5_assessment_situations s ON s.id=d.assessment_situation_db_id
            JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE d.id=%s""",(UUID(decision_id),)).fetchone()
    if not row:raise HTTPException(status_code=404,detail='M7_CLARIFICATION_NOT_FOUND')
    if int(row['owner_user_id'])!=int(user.id):raise HTTPException(status_code=403,detail='Нет доступа к чужому уточнению.')
    if not permits(row['usage_scope']):raise HTTPException(status_code=403,detail='QA_CLARIFICATION_NOT_AVAILABLE_IN_PRODUCT_ROUTE')
    return user


def _m7_require_explicit_return(connection, *, owner_user_id: int,
                                cycle_id: str | None = None,
                                assessment_situation_id: str | None = None) -> None:
    """Persist the lease boundary and block every AS read/write until Continue."""
    if cycle_id is None:
        row = connection.execute("""SELECT c.cycle_id FROM m5_assessment_situations s
            JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE s.assessment_situation_id=%s""",
            (UUID(str(assessment_situation_id)),)).fetchone()
        if not row or "cycle_id" not in row:
            return
        cycle_id = str(row["cycle_id"])
    policy = connection.execute("""SELECT r.content_json->'return_policy_snapshot' AS value
        FROM m7_cycle_plans p JOIN LATERAL(SELECT content_json FROM m7_plan_revisions
          WHERE plan_id=p.id ORDER BY revision_no DESC LIMIT 1) r ON TRUE
        JOIN m5_cycles c ON c.id=p.cycle_db_id WHERE c.cycle_id=%s""",
        (UUID(str(cycle_id)),)).fetchone()
    if not policy or not policy["value"]:
        return
    try:
        event = m7_return_integration.reconcile_presence(
            connection, cycle_id=str(cycle_id), owner_user_id=owner_user_id)
    except ValueError as exc:
        if str(exc) == "M7_RETURN_CURRENT_POSITION_NOT_FOUND":
            return
        raise
    if event:
        connection.commit()
        raise HTTPException(status_code=409, detail="M7_RETURN_EXPLICIT_CONTINUE_REQUIRED")


def _persist_time_expiry_for_situation(assessment_situation_id:str):
    with get_connection() as connection:
        row=connection.execute('SELECT c.cycle_id,c.created_by FROM m5_assessment_situations s JOIN m5_cycles c ON c.id=s.cycle_db_id WHERE s.assessment_situation_id=%s',(UUID(assessment_situation_id),)).fetchone()
        if row:
            try:m7_completion.complete(connection,cycle_id=str(row['cycle_id']),key='automatic-expiry',action='time_limit',reason='automatic',initiated_by=row['created_by'])
            except ValueError:connection.rollback();return
            connection.commit()


@router.post("/admin/m5-runtime/import")
def import_m5_runtime_package(request: Request) -> dict:
    _m5_superadmin(request)
    with get_connection() as connection:
        try:
            result = m5_storage.import_package_directory(connection, M5_PACKAGE_DIR)
        except M5CaseTypeCatalogError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        readback = m5_storage.package_readback(connection, result["package_db_id"])
        connection.commit()
    return {"result": result, "readback": readback}


@router.post("/admin/m5-runtime/situations")
def prepare_m5_runtime_situation(payload: M5PrepareSituationRequest, request: Request) -> dict:
    user = _m5_superadmin(request)
    policy = json.loads((M5_PACKAGE_DIR / "admission-policy.json").read_text())
    try:
        with get_connection() as connection:
            cycle, session = m5_cycle_runtime.create_cycle_session_for_case(
                connection, personalized_profile_id=payload.personalized_profile_id,
                case_id=payload.case_id, case_version=payload.case_version,
                created_by=int(user.id), usage_scope="qa",
            )
            result = m5_storage.prepare_assessment_situation(
                connection, assessment_situation_id=str(uuid4()), case_id=payload.case_id,
                case_version=payload.case_version, personalized_profile_id=payload.personalized_profile_id,
                cycle_db_id=int(cycle["id"]), session_db_id=int(session["id"]),
                substitutions=payload.substitutions, policy=policy, usage_scope="qa", qa_authorized_by=int(user.id),
            )
            connection.commit()
            return {**result, "cycle_id": str(cycle["cycle_id"]), "session_id": str(session["session_id"])}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-runtime/situations/{assessment_situation_id}/start")
def start_m5_runtime_situation(assessment_situation_id: UUID, request: Request) -> dict:
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result = m5_scenario_runtime.start(connection, str(assessment_situation_id))
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-runtime/situations/{assessment_situation_id}/turns")
def submit_m5_runtime_turn(assessment_situation_id: UUID, payload: M5QATurnRequest, request: Request) -> dict:
    _m5_superadmin(request)
    try:
        return m5_scenario_runtime.submit_turn_detached(
            assessment_situation_id=str(assessment_situation_id), request_id=payload.request_id,
            turn_id=str(payload.turn_id), content=payload.content,
            semantic_adapter=(m5_scenario_runtime.ControlledSemanticAdapter(payload.controlled_outcomes)
                              if payload.controlled_outcomes is not None else None),
            character_adapter=(m5_scenario_runtime.ControlledCharacterAdapter(payload.controlled_character_responses)
                               if payload.controlled_character_responses is not None else None),
            connection_factory=get_connection,
        )
    except m5_addressed_scenario.SemanticTurnError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-runtime/situations/{assessment_situation_id}/transitions")
def transition_m5_runtime_situation(assessment_situation_id: UUID, payload: M5TransitionRequest, request: Request) -> dict:
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result = m5_scenario_runtime.transition(connection, assessment_situation_id=str(assessment_situation_id),
                                                    action=payload.action, reason=payload.reason, request_id=payload.request_id)
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-runtime/situations/{assessment_situation_id}/model-check")
def run_m5_runtime_model_check(assessment_situation_id: UUID, payload: M5ModelCheckRequest, request: Request) -> dict:
    _m5_superadmin(request)
    execution_rules = json.loads((M5_PACKAGE_DIR / "execution-rules.json").read_text())
    with get_connection() as connection:
        try:
            result = m5_scenario_runtime.run_model_check_case03(
                connection, assessment_situation_id=str(assessment_situation_id), scheme=payload.scheme,
                rules=execution_rules["model_checks"]["CASE-TDISC-03"],
                initiated_by=payload.initiated_by, scheme_authored_by=payload.scheme_authored_by,
                turn_id=str(payload.turn_id) if payload.turn_id else None)
            connection.commit()
            return result
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/admin/m5-runtime/situations/{assessment_situation_id}/trace")
def get_m5_runtime_trace(assessment_situation_id: UUID, request: Request) -> dict:
    _m5_superadmin(request)
    with get_connection() as connection:
        try:
            return m5_scenario_runtime.trace(connection, str(assessment_situation_id))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/admin/m5-runtime/situations/{assessment_situation_id}/c45")
def build_m5_runtime_c45(assessment_situation_id: UUID, request: Request, mode: Literal["interim", "final"] = "final") -> dict:
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result = m5_scenario_runtime.build_c45(connection, str(assessment_situation_id), mode=mode)
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-runtime/situations/{assessment_situation_id}/technical-c45")
def execute_m5_runtime_technical_c45(assessment_situation_id: UUID, payload: M5TechnicalC45Request,
                                     request: Request) -> dict:
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result = m5_scenario_runtime.execute_technical_c45(
                connection, assessment_situation_id=str(assessment_situation_id),
                indicator_id=payload.indicator_id, mode=payload.mode,
            )
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/admin/m5-runtime/situations/{assessment_situation_id}/qa-evidence")
def record_m5_runtime_qa_evidence(assessment_situation_id: UUID, payload: M5QAEvidenceRequest, request: Request) -> dict:
    user = _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result = m5_storage.record_technical_qa_evidence(
                connection, assessment_situation_id=str(assessment_situation_id), trajectory=payload.trajectory,
                expected=payload.expected, actual=payload.actual, defects=payload.defects, performed_by=int(user.id))
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/assessment/m5/situations/{assessment_situation_id}/start")
def start_owned_m5_situation(assessment_situation_id: UUID, request: Request) -> dict:
    _m5_owned_situation(request, str(assessment_situation_id))
    try:
        with get_connection() as connection:
            result = m5_scenario_runtime.start(connection, str(assessment_situation_id))
            connection.commit()
            return result
    except ValueError as exc:
        if str(exc)=='M7_TIME_LIMIT_REACHED':_persist_time_expiry_for_situation(str(assessment_situation_id))
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/assessment/m5/situations/{assessment_situation_id}/turns")
def submit_owned_m5_turn(assessment_situation_id: UUID, payload: M5TurnRequest, request: Request) -> dict:
    user = _m5_owned_situation(request, str(assessment_situation_id))
    try:
        with get_connection() as connection:
            receipt = m5_scenario_runtime.read_applied_turn_receipt(
                connection, assessment_situation_id=str(assessment_situation_id),
                request_id=payload.request_id, turn_id=str(payload.turn_id), content=payload.content,
            )
            if receipt is not None:
                connection.commit()
                return receipt
            _m7_require_explicit_return(connection, owner_user_id=int(user.id),
                                        assessment_situation_id=str(assessment_situation_id))
            semantic_adapter=character_adapter=None
            from Api.m10_test_gateway import enabled as browser_test_gateway_enabled
            if browser_test_gateway_enabled():
                from Api.m5_rule_engine import ControlledCharacterAdapter,ControlledSemanticAdapter
                from Api.m10_test_gateway import acceptance_fixture
                fixture=acceptance_fixture()
                matched=bool(fixture and payload.content==fixture['character_answer'])
                controlled_outcomes={}
                if fixture:
                    controlled_outcomes[fixture['mandatory_material_id']+':mandatory']='TRUE'
                if matched:
                    controlled_outcomes[fixture['character_material_id']+':character_reaction']='TRUE'
                semantic_adapter=ControlledSemanticAdapter(controlled_outcomes)
                character_adapter=ControlledCharacterAdapter({fixture['character_material_id']:fixture['character_response']} if matched else {})
            connection.commit()
        return m5_scenario_runtime.submit_turn_detached(
            assessment_situation_id=str(assessment_situation_id), request_id=payload.request_id,
            turn_id=str(payload.turn_id), content=payload.content, semantic_adapter=semantic_adapter,
            character_adapter=character_adapter, connection_factory=get_connection, enqueue_interim_by=int(user.id),
        )
    except m5_addressed_scenario.SemanticTurnError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc)=='M7_TIME_LIMIT_REACHED':_persist_time_expiry_for_situation(str(assessment_situation_id))
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/assessment/m5/situations/{assessment_situation_id}/transitions")
def transition_owned_m5_situation(assessment_situation_id: UUID, payload: M5TransitionRequest, request: Request) -> dict:
    user=_m5_owned_situation(request, str(assessment_situation_id))
    try:
        with get_connection() as connection:
            # Pause/resume check saved receipts before any presence mutation.
            if payload.action not in {'pause','resume'}:
                _m7_require_explicit_return(connection, owner_user_id=int(user.id),
                                            assessment_situation_id=str(assessment_situation_id))
            result = m5_scenario_runtime.transition(connection, assessment_situation_id=str(assessment_situation_id),
                                                    action=payload.action, reason=payload.reason, request_id=payload.request_id,
                                                    participant_command=True)
            if payload.action=='scenario_end':
                handoff=m5_scenario_runtime.build_c45(connection,str(assessment_situation_id),mode='interim')
                queued=m10_orchestration.enqueue_handoff(connection,handoff_id=str(handoff['handoff_id']),created_by=int(user.id))
                result={**result,'interim_processing_request_id':str(queued['id'])}
            connection.commit()
            return result
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class AssessmentDraftWrite(BaseModel):
    slot_id: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=0)
    revision: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=10000)


class AssessmentDraftAccepted(BaseModel):
    accepted: Literal[True]
    slot_id: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=1, max_length=200)
    turn_id: UUID
    clarification_id: UUID | None = None


@router.post('/assessment/m5/situations/{assessment_situation_id}/draft/accepted')
def clear_owned_accepted_draft(assessment_situation_id: UUID, payload: AssessmentDraftAccepted,
                              request: Request, response: FastAPIResponse):
    user = _m5_owned_situation(request, str(assessment_situation_id))
    from Api import assessment_drafts
    response.headers['Cache-Control'] = 'no-store'
    try:
        with get_connection() as connection:
            return assessment_drafts.consume(connection, assessment_situation_id=str(assessment_situation_id),
                                             owner_user_id=int(user.id), **payload.model_dump(mode='json'))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get('/assessment/m5/situations/{assessment_situation_id}/draft')
def get_owned_answer_draft(assessment_situation_id: UUID, request: Request, response: FastAPIResponse):
    user = _m5_owned_situation(request, str(assessment_situation_id))
    from Api import assessment_drafts
    response.headers['Cache-Control'] = 'no-store'
    try:
        with get_connection() as connection:
            _m7_require_explicit_return(connection, owner_user_id=int(user.id),
                                        assessment_situation_id=str(assessment_situation_id))
            return assessment_drafts.read(connection, assessment_situation_id=str(assessment_situation_id),
                                          owner_user_id=int(user.id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put('/assessment/m5/situations/{assessment_situation_id}/draft')
def save_owned_answer_draft(assessment_situation_id: UUID, payload: AssessmentDraftWrite,
                           request: Request, response: FastAPIResponse):
    user = _m5_owned_situation(request, str(assessment_situation_id))
    from Api import assessment_drafts
    response.headers['Cache-Control'] = 'no-store'
    try:
        with get_connection() as connection:
            _m7_require_explicit_return(connection, owner_user_id=int(user.id),
                                        assessment_situation_id=str(assessment_situation_id))
            return assessment_drafts.save(connection, assessment_situation_id=str(assessment_situation_id),
                                          owner_user_id=int(user.id), **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessment/m5/situations/{assessment_situation_id}/answer-status")
def get_owned_assessment_answer_status(assessment_situation_id: UUID, request: Request, response: FastAPIResponse,
                                     request_id: str, turn_id: UUID,
                                     clarification_id: UUID | None = None) -> dict:
    _m5_owned_situation(request, str(assessment_situation_id))
    if not request_id.strip() or len(request_id) > 200:
        raise HTTPException(status_code=422, detail="ANSWER_STATUS_REQUEST_ID_INVALID")
    from Api.assessment_answer_status import read
    response.headers['Cache-Control'] = 'no-store'
    try:
        with get_connection() as connection:
            return read(connection, assessment_situation_id=str(assessment_situation_id),
                        request_id=request_id, turn_id=str(turn_id),
                        clarification_id=str(clarification_id) if clarification_id else None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/assessment/m5/situations/{assessment_situation_id}/trace")
def get_owned_m5_trace(assessment_situation_id: UUID, request: Request) -> dict:
    user = _m5_owned_situation(request, str(assessment_situation_id))
    with get_connection() as connection:
        _m7_require_explicit_return(connection, owner_user_id=int(user.id),
                                    assessment_situation_id=str(assessment_situation_id))
        return m10_product_flow.participant_trace(m5_scenario_runtime.trace(connection, str(assessment_situation_id)))


@router.post('/assessment/cycles/prepare', status_code=202)
def prepare_owned_assessment_cycle(payload: ProductCycleStartRequest, request: Request):
    token=request.cookies.get(SESSION_COOKIE_NAME);user=web_session_service.get_user_by_token(token) if token else None
    if user is None:raise HTTPException(status_code=401,detail='Сессия не найдена. Войдите заново.')
    try:
        preparation_request = payload.model_dump(mode='json')
        with get_connection() as connection:
            scope = acquaintance.preparation_scope(connection, user_id=int(user.id),
                profile_id=payload.personalized_profile_id)
            if scope:
                preparation_request.update(scope)
        operation = product_cycle_preparation_queue.enqueue(
            operation_id=payload.idempotency_key,
            user_id=int(user.id),
            request=preparation_request,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail='Нет доступа к операции подготовки Cycle.') from exc
    except ValueError as exc:
        if str(exc) == 'PRODUCT_CYCLE_PREPARATION_IDEMPOTENCY_CONFLICT':
            raise HTTPException(status_code=409, detail='Ключ операции уже использован для другого запроса.') from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return public_operation(operation)


@router.get('/assessment/cycles/preparation/{operation_id}')
def read_owned_assessment_cycle_preparation(operation_id: str, request: Request):
    token=request.cookies.get(SESSION_COOKIE_NAME);user=web_session_service.get_user_by_token(token) if token else None
    if user is None:raise HTTPException(status_code=401,detail='Сессия не найдена. Войдите заново.')
    operation=product_cycle_preparation_queue.get_owned_status(operation_id, int(user.id))
    if operation is None:raise HTTPException(status_code=404,detail='Операция подготовки Cycle не найдена.')
    saved_scope = operation.get('request_json') or {}
    if saved_scope.get('assignment_ref'):
        with get_connection() as connection:
            readiness = acquaintance.early_readiness(connection, user_id=int(user.id))
            if any(readiness.get(key) != saved_scope.get(key) for key in
                   ('organization_id', 'assignment_ref', 'questionnaire_revision_id')):
                raise HTTPException(409, detail='W02_PREPARATION_ASSIGNMENT_SCOPE_MISMATCH')
            from Api import assessment_assignment_sources
            binding = assessment_assignment_sources.current_binding(connection, user_id=int(user.id),
                organization_id=readiness.get('organization_id'),
                assignment_ref=readiness.get('assignment_ref'),
                questionnaire_revision_id=readiness.get('questionnaire_revision_id'))
            assignment_id = int(binding['assignment_id']) if binding else None
            legacy_cycle = ((operation.get('result_json') or {}).get('plan') or {}).get('cycle_id')
            legacy_match = False
            if assignment_id is not None and 'assignment_id' not in saved_scope and operation['status'] == 'completed' and legacy_cycle:
                legacy_match = connection.execute('''SELECT 1 FROM m5_cycles
                    WHERE cycle_id=%s AND owner_user_id=%s AND assignment_id=%s''',
                    (str(legacy_cycle), int(user.id), assignment_id)).fetchone() is not None
            if saved_scope.get('assignment_id') != assignment_id and not legacy_match:
                raise HTTPException(409, detail='W02_PREPARATION_ASSIGNMENT_SCOPE_MISMATCH')
    return public_operation(operation)


@router.post('/assessment/cycles/start', status_code=201)
def start_owned_assessment_cycle(payload: ProductCycleActionRequest, request: Request):
    token=request.cookies.get(SESSION_COOKIE_NAME);user=web_session_service.get_user_by_token(token) if token else None
    if user is None:raise HTTPException(status_code=401,detail='Сессия не найдена. Войдите заново.')
    try:
        with get_connection() as connection:
            if payload.cycle_id:
                owned_cycle = connection.execute('''SELECT status,personalized_profile_id FROM m5_cycles
                    WHERE cycle_id=%s AND owner_user_id=%s''', (str(payload.cycle_id), int(user.id))).fetchone()
                if owned_cycle and owned_cycle.get('status') == 'prepared':
                    acquaintance.preparation_scope(connection, user_id=int(user.id),
                        profile_id=owned_cycle['personalized_profile_id'])
                result=m10_product_flow.start_prepared(connection,user_id=int(user.id),cycle_id=payload.cycle_id,
                    key=payload.idempotency_key)
            else:
                if acquaintance.preparation_scope(connection, user_id=int(user.id), profile_id=payload.personalized_profile_id):
                    raise ValueError('W02_PREPARED_CYCLE_REQUIRED')
                # Compatibility path for released clients. New UI always prepares first.
                with preparation_observation.synchronous(payload.idempotency_key, 'assessment', {'user_id': int(user.id)}, factory=get_connection):
                    result=m10_product_flow.start_or_resume(connection,user_id=int(user.id),key=payload.idempotency_key,
                        selected_skills=list(payload.selected_skills),profile_id=payload.personalized_profile_id)
                    runtime=m10_product_flow.read_runtime(connection,cycle_id=str(result['plan']['cycle_id']))
                    connection.commit()
                    return {**m10_product_flow.participant_presentation(result),'runtime':runtime}
            runtime=m10_product_flow.read_runtime(connection,cycle_id=str(result['plan']['cycle_id']))
            connection.commit();return {**m10_product_flow.participant_presentation(result),'runtime':runtime}
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.get('/assessment/cycles/{cycle_id}/runtime')
def read_owned_assessment_runtime(cycle_id:UUID,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            _m7_require_explicit_return(connection,owner_user_id=int(user.id),cycle_id=str(cycle_id))
            return m10_product_flow.read_runtime(connection,cycle_id=str(cycle_id))
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/next', status_code=201)
def next_owned_assessment_situation(cycle_id:UUID,payload:ProductNextPreparationRequest,request:Request):
    user = _m7_owned_cycle(request, str(cycle_id))
    try:
        operation = product_cycle_preparation_queue.enqueue(
            operation_id=payload.idempotency_key, user_id=int(user.id),
            request={'kind': 'next', 'cycle_id': str(cycle_id), **payload.model_dump(exclude_none=True)},
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail='Нет доступа к операции подготовки Cycle.') from exc
    except ValueError as exc:
        if str(exc) == 'PRODUCT_CYCLE_PREPARATION_IDEMPOTENCY_CONFLICT':
            raise HTTPException(status_code=409, detail='Ключ операции уже использован для другого запроса.') from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return public_operation(operation)


@router.post('/assessment/m7/cycles/{cycle_id}/present-next', status_code=201)
def present_owned_assessment_next(cycle_id:UUID,payload:ProductNextPresentationRequest,request:Request):
    cycle_id = str(cycle_id)
    user = _m7_owned_cycle(request, cycle_id)
    try:
        with get_connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (int(user.id),))
            _m7_require_explicit_return(connection, owner_user_id=int(user.id), cycle_id=cycle_id)
            try:
                with connection.transaction():
                    result = m10_product_flow.present_owned_next(
                        connection, cycle_id=cycle_id, user_id=int(user.id), **payload.model_dump(),
                    )
            except ValueError as exc:
                if str(exc) != 'M7_TIME_LIMIT_REACHED':
                    raise
                m7_completion.complete(connection, cycle_id=cycle_id, key='automatic-expiry',
                    action='time_limit', reason='automatic', initiated_by=int(user.id))
                result = {}
            runtime = m10_product_flow.read_runtime(connection, cycle_id=cycle_id)
            connection.commit()
            return {**m10_product_flow.participant_presentation(result), 'runtime': runtime}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/finish-situation')
def finish_owned_assessment_situation(cycle_id:UUID,payload:ProductNextRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    prepare_next = False
    try:
        with get_connection() as connection:
            result=m7_completion.finish_current_situation(connection,cycle_id=str(cycle_id),
                key=payload.idempotency_key,initiated_by=int(user.id))
            if result.get('handoff_id'):
                m10_orchestration.enqueue_handoff(connection,handoff_id=result['handoff_id'],created_by=int(user.id))
            cycle = connection.execute(
                "SELECT id,cycle_id,profile_ref_json,status FROM m5_cycles WHERE cycle_id=%s", (cycle_id,),
            ).fetchone()
            if cycle["status"] == "paused":
                from Api.participant_dashboard import cycle_progress
                progress = cycle_progress(connection, cycle)
                if (progress["between_situations"] and progress["planned_total"]
                        and progress["last_completed_position_no"] == progress["planned_total"]):
                    m7_completion.complete(connection, cycle_id=str(cycle_id),
                        key='complete-after:' + result["assessment_situation_id"], action='complete',
                        reason='user_completed_scenario', initiated_by=int(user.id), participant_command=True)
                else:
                    prepare_next = progress["between_situations"]
            connection.commit()
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc

    if prepare_next:
        # Commit the AS boundary before taking queue locks. The participant can
        # recover a missed enqueue by submitting this same boundary command.
        after_as = result['assessment_situation_id']
        key = 'next:' + after_as
        try:
            product_cycle_preparation_queue.enqueue(operation_id=key, user_id=int(user.id), request={
                'kind': 'next', 'cycle_id': str(cycle_id), 'idempotency_key': key,
                'after_assessment_situation_id': after_as,
            })
        except ValueError:
            # The Cycle or active queue scope can change after the boundary commits.
            pass
    return result


@router.post('/assessment/m7/cycles/{cycle_id}/positions/{position_no}/replacement', status_code=201)
def replace_owned_assessment_situation(cycle_id:UUID,position_no:int,payload:ReplaceRoutePositionRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            result=m7_route_replacement.replace_current(connection,cycle_id=str(cycle_id),position_no=position_no,
                expected_assessment_situation_id=payload.expected_assessment_situation_id,
                expected_state=payload.expected_state,key=payload.idempotency_key,reason=payload.reason,
                policy_ref=payload.policy_ref,requested_by=int(user.id),provider=m7_route_replacement.runtime_provider)
            connection.commit()
            if result.get('status')!='completed':
                raise HTTPException(status_code=409,detail=result.get('error_code','M7_REPLACEMENT_PREPARATION_FAILED'))
            return result
    except HTTPException:raise
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/positions/{position_no}/equivalent-candidate', status_code=201)
def generate_owned_equivalent_candidate(cycle_id:UUID,position_no:int,
        payload:GenerateEquivalentSituationRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            operation=m5_equivalent_generation.begin_generation(connection,cycle_id=str(cycle_id),
                position_no=position_no,expected_as_id=payload.expected_assessment_situation_id,
                request_key=payload.idempotency_key,requested_by=int(user.id),
                package=m5_equivalent_generation.load_variability_package(),
                provider_config=payload.provider_config_ref)
            if operation['status']=='completed':
                return {'status':'completed','operation_id':str(operation['id']),
                    'candidate_as_db_id':operation['candidate_as_db_id']}
            if operation['status'] in {'failed','rejected_late'}:
                raise HTTPException(status_code=409,detail=operation.get('error_code') or 'M5_EQUIVALENT_OPERATION_FAILED')
            claimed=m5_equivalent_generation.claim_generation(connection,str(operation['id']))
            connection.commit()
        provider=m5_equivalent_generation.runtime_provider
        if provider is None:
            with get_connection() as connection:
                failed=m5_equivalent_generation.fail_generation(connection,operation_id=str(claimed['id']),
                    lease_token=str(claimed['lease_token']),error_code='M5_EQUIVALENT_PROVIDER_UNAVAILABLE',retryable=True)
                connection.commit()
            raise HTTPException(status_code=409,detail=failed['error_code'])
        try:
            output=m5_equivalent_generation.run_provider(provider,claimed)
        except Exception as exc:
            code=f'M5_EQUIVALENT_PROVIDER_FAILED:{type(exc).__name__}'
            with get_connection() as connection:
                m5_equivalent_generation.fail_generation(connection,operation_id=str(claimed['id']),
                    lease_token=str(claimed['lease_token']),error_code=code,retryable=True)
                connection.commit()
            raise HTTPException(status_code=409,detail=code) from exc
        with get_connection() as connection:
            policy=json.loads((M5_PACKAGE_DIR/'admission-policy.json').read_text())
            result=m5_equivalent_generation.complete_generation(connection,operation_id=str(claimed['id']),
                lease_token=str(claimed['lease_token']),candidate=output,policy=policy)
            connection.commit()
        if result.get('status')!='completed':
            raise HTTPException(status_code=409,detail=result.get('error_code','M5_EQUIVALENT_CANDIDATE_NOT_ADMITTED'))
        return result
    except HTTPException:raise
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/clarifications/{decision_id}/answers')
def answer_owned_clarification(decision_id:UUID,payload:ClarificationAnswerRequest,request:Request):
    user=_m7_owned_clarification(request,str(decision_id))
    try:
        with get_connection() as connection:
            result=m7_clarification.answer(connection,decision_id=str(decision_id),request_id=payload.request_id,
                turn_id=str(payload.turn_id),content=payload.content)
            if result.get('handoff_id'):
                m10_orchestration.enqueue_handoff(connection,handoff_id=str(result['handoff_id']),created_by=int(user.id))
            connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/clarifications/{decision_id}/outcomes')
def outcome_owned_clarification(decision_id:UUID,payload:ClarificationOutcomeRequest,request:Request):
    _m7_owned_clarification(request,str(decision_id))
    try:
        with get_connection() as connection:
            result=m7_clarification.record_outcome(connection,decision_id=str(decision_id),request_id=payload.request_id,
                outcome=payload.outcome);connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.get('/assessment/m7/cycles/{cycle_id}')
def get_owned_m7_cycle(cycle_id:UUID,request:Request):
    _m7_owned_cycle(request,str(cycle_id))
    with get_connection() as connection:return m7_completion.read_status(connection,str(cycle_id))


@router.get('/assessment/m7/cycles/{cycle_id}/return-state')
def get_owned_m7_return_state(cycle_id:UUID,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            return m7_return_integration.read_return_state(connection,cycle_id=str(cycle_id),owner_user_id=int(user.id))
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/presence')
def heartbeat_owned_m7_return(cycle_id:UUID,payload:ReturnHeartbeatRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            result=m7_return_integration.heartbeat(connection,cycle_id=str(cycle_id),owner_user_id=int(user.id),
                client_id=payload.client_id,expected_as_id=payload.expected_assessment_situation_id)
            connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/return-continue')
def continue_owned_m7_return(cycle_id:UUID,payload:ReturnContinueRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            result=m7_return_integration.continue_return(connection,cycle_id=str(cycle_id),position_no=payload.position_no,
                expected_as_id=payload.expected_assessment_situation_id,expected_state=payload.expected_state,
                key=payload.idempotency_key,owner_user_id=int(user.id),generation_operation_id=payload.generation_operation_id)
            connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/control')
def control_owned_m7_cycle(cycle_id:UUID,payload:CycleControlRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            result=m7_completion.control(connection,cycle_id=str(cycle_id),key=payload.idempotency_key,action=payload.action,reason=payload.reason,initiated_by=int(user.id),participant_command=True);connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/completion')
def complete_owned_m7_cycle(cycle_id:UUID,payload:CompletionRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            result=m7_completion.complete(connection,cycle_id=str(cycle_id),key=payload.idempotency_key,action=payload.action,reason=payload.reason,initiated_by=int(user.id),participant_command=True);connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/assessment/m7/cycles/{cycle_id}/additional-sessions',status_code=201)
def create_owned_additional_session(cycle_id:UUID,payload:AdditionalSessionRequest,request:Request):
    user=_m7_owned_cycle(request,str(cycle_id))
    try:
        with get_connection() as connection:
            result=m7_completion.create_additional_session(connection,cycle_id=str(cycle_id),intent_id=payload.intent_id,key=payload.idempotency_key,created_by=int(user.id));connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.get('/admin/m7-cycles/{cycle_id}/c46')
def read_m7_c46(cycle_id:UUID,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:return m7_completion.read_c46(connection,str(cycle_id))
    except ValueError as exc:raise HTTPException(status_code=404,detail=str(exc)) from exc


@router.post('/admin/m7-cycles/{cycle_id}/c46/reconcile')
def reconcile_m7_c46(cycle_id:UUID,payload:ReconcileC46Request,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result=m7_completion.reconcile_c46(connection,cycle_id=str(cycle_id),expected_composition_checksum=payload.expected_composition_checksum,
                calculation_ref=payload.calculation_ref,coverage=payload.coverage,skill_outcomes=payload.skill_outcomes);connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post('/admin/m7-cycles/{cycle_id}/blocking-waits')
def begin_m7_blocking_wait(cycle_id:UUID,payload:BlockingWaitRequest,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            cycle=m7_completion._cycle(connection,str(cycle_id));session=connection.execute('SELECT id FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal DESC LIMIT 1',(cycle['id'],)).fetchone()
            result=m5_cycle_runtime.begin_blocking_wait(connection,cycle_db_id=cycle['id'],session_db_id=session['id'],operation_ref=payload.operation_ref,reason=payload.reason);connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.delete('/admin/m7-cycles/{cycle_id}/blocking-waits/{operation_ref}')
def end_m7_blocking_wait(cycle_id:UUID,operation_ref:str,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            cycle=m7_completion._cycle(connection,str(cycle_id));session=connection.execute('SELECT id FROM m5_cycle_sessions WHERE cycle_db_id=%s ORDER BY ordinal DESC LIMIT 1',(cycle['id'],)).fetchone()
            result=m5_cycle_runtime.end_blocking_wait(connection,cycle_db_id=cycle['id'],session_db_id=session['id'],operation_ref=operation_ref,reason='blocking_operation_finished');connection.commit();return result
    except ValueError as exc:raise HTTPException(status_code=409,detail=str(exc)) from exc


@router.post("/admin/prompt-lab/prompts", response_model=PromptLabPromptVersion)
def create_prompt_lab_prompt(payload: PromptLabPromptCreateRequest, request: Request) -> PromptLabPromptVersion:
    raise HTTPException(
        status_code=403,
        detail="Prompt changes are read-only in the application. Update prompts directly in the database as an Administrator.",
    )


@router.post("/admin/prompt-lab/case-runs", response_model=PromptLabCaseRunResponse)
def create_prompt_lab_case_run(payload: PromptLabCaseRunRequest, request: Request) -> PromptLabCaseRunResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token) if token else None
    operation_id = request.headers.get("X-Agent4K-Operation-Id")
    prompt_source = str(payload.prompt_source or "custom").strip().lower()
    use_file_prompt = prompt_source in {"file", "files", "default", "production"}
    prompt_text = None
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        if use_file_prompt:
            production_prompt_row = connection.execute(
                """
                SELECT instruction_text
                FROM case_text_build_instructions
                WHERE is_active = TRUE
                  AND applies_to_type_code IS NULL
                ORDER BY priority ASC, version DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            prompt_text = str((production_prompt_row or {}).get("instruction_text") or "").strip()
            if not prompt_text:
                raise HTTPException(status_code=400, detail="Production system prompt is not configured")
        if not use_file_prompt:
            prompt_text = str(payload.prompt_text or "").strip()
            if not prompt_text:
                raise HTTPException(status_code=400, detail="Prompt text is required")

    selected_case_codes: list[str] = []
    seen_case_codes: set[str] = set()
    for raw_code in [payload.case_id_code, *(payload.case_id_codes or [])]:
        case_code = str(raw_code or "").strip()
        if not case_code or case_code in seen_case_codes:
            continue
        selected_case_codes.append(case_code)
        seen_case_codes.add(case_code)
    if not selected_case_codes:
        raise HTTPException(status_code=400, detail="At least one case must be selected")

    def _run_case_preview(*, use_llm_personalization: bool) -> dict:
        if "__all__" in selected_case_codes:
            return assessment_service.preview_personalized_case_batch(
                user_id=payload.user_id,
                case_id_codes=all_case_codes,
                use_llm_personalization=use_llm_personalization,
                case_generation_system_prompt=prompt_text,
                full_name=payload.full_name,
                role_id=payload.role_id,
                position=payload.position,
                duties=payload.duties,
                company_industry=payload.company_industry,
                user_profile_override=payload.user_profile,
                progress_operation_id=operation_id,
            )
        if len(selected_case_codes) > 1:
            return assessment_service.preview_personalized_case_batch(
                user_id=payload.user_id,
                case_id_codes=selected_case_codes,
                use_llm_personalization=use_llm_personalization,
                case_generation_system_prompt=prompt_text,
                full_name=payload.full_name,
                role_id=payload.role_id,
                position=payload.position,
                duties=payload.duties,
                company_industry=payload.company_industry,
                user_profile_override=payload.user_profile,
                progress_operation_id=operation_id,
            )
        return assessment_service.preview_personalized_case(
            user_id=payload.user_id,
            case_id_code=selected_case_codes[0],
            use_llm_personalization=use_llm_personalization,
            case_generation_system_prompt=prompt_text,
            full_name=payload.full_name,
            role_id=payload.role_id,
            position=payload.position,
            duties=payload.duties,
            company_industry=payload.company_industry,
            user_profile_override=payload.user_profile,
        )

    try:
        progress_cases: list[tuple[str, str]] = []
        if "__all__" in selected_case_codes:
            with get_connection() as connection:
                all_case_rows = connection.execute(
                    """
                    SELECT case_id_code, title
                    FROM cases_registry
                    WHERE status = 'ready'
                    ORDER BY case_id_code ASC
                    """
                ).fetchall()
            all_case_codes = [
                str((row or {}).get("case_id_code") or "").strip()
                for row in all_case_rows
                if str((row or {}).get("case_id_code") or "").strip()
            ]
            progress_cases = [
                (
                    str((row or {}).get("case_id_code") or "").strip(),
                    str((row or {}).get("title") or "").strip(),
                )
                for row in all_case_rows
                if str((row or {}).get("case_id_code") or "").strip()
            ]
            if not all_case_codes:
                raise HTTPException(status_code=400, detail="No cases available in the system")
            operation_progress_service.begin(
                operation_id,
                title="Формируем кейсы",
                message=f"Подготавливаем генерацию {len(all_case_codes)} кейсов.",
                steps=[{"label": "Подготовка", "description": "Готовим набор шаблонов для генерации."}] + [
                    {
                        "label": f"Кейс {index} из {len(progress_cases)}",
                        "description": f"{code} · {title}" if title else code,
                    }
                    for index, (code, title) in enumerate(progress_cases, start=1)
                ],
            )
            artifacts = _run_case_preview(use_llm_personalization=True)
        elif len(selected_case_codes) > 1:
            with get_connection() as connection:
                selected_rows = connection.execute(
                    """
                    SELECT case_id_code, title
                    FROM cases_registry
                    WHERE case_id_code = ANY(%s)
                    ORDER BY case_id_code ASC
                    """,
                    (selected_case_codes,),
                ).fetchall()
            progress_cases = [
                (
                    str((row or {}).get("case_id_code") or "").strip(),
                    str((row or {}).get("title") or "").strip(),
                )
                for row in selected_rows
                if str((row or {}).get("case_id_code") or "").strip()
            ]
            operation_progress_service.begin(
                operation_id,
                title="Формируем кейсы",
                message=f"Подготавливаем генерацию {len(selected_case_codes)} кейсов.",
                steps=[{"label": "Подготовка", "description": "Готовим выбранные шаблоны кейсов."}] + [
                    {
                        "label": f"Кейс {index} из {len(progress_cases)}",
                        "description": f"{code} · {title}" if title else code,
                    }
                    for index, (code, title) in enumerate(progress_cases, start=1)
                ],
            )
            artifacts = _run_case_preview(use_llm_personalization=True)
        else:
            operation_progress_service.begin(
                operation_id,
                title="Формируем кейс",
                message="Подготавливаем генерацию кейса.",
                steps=[
                    {"label": "Подготовка", "description": "Готовим выбранный шаблон кейса."},
                    {"label": "Генерация", "description": selected_case_codes[0]},
                ],
            )
            operation_progress_service.advance(
                operation_id,
                1,
                title="Формируем кейс",
                message=f"Генерируем кейс {selected_case_codes[0]}",
            )
            artifacts = _run_case_preview(use_llm_personalization=True)
    except ValueError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(
            status_code=502,
            detail="DeepSeek не смог персонализировать кейс. Повторите попытку позже.",
        ) from exc
    except HTTPException as exc:
        operation_progress_service.fail(operation_id, message=str(exc.detail))
        raise
    except Exception as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise

    operation_progress_service.complete(
        operation_id,
        title="Кейсы готовы",
        message="Генерация кейсов завершена.",
    )

    generated_at = datetime.utcnow()
    generated_run_id = int(generated_at.timestamp() * 1000)

    return PromptLabCaseRunResponse(
        id=generated_run_id,
        prompt=None,
        created_at=generated_at,
        **artifacts,
    )


@router.get("/admin/prompt-lab/system-case-preview", response_model=PromptLabSystemCasePreviewResponse)
def get_prompt_lab_system_case_preview(
    request: Request,
    user_id: int,
    case_id_code: str,
) -> PromptLabSystemCasePreviewResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
    try:
        artifacts = assessment_service.preview_personalized_case(
            user_id=user_id,
            case_id_code=case_id_code,
            use_llm_personalization=True,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail="DeepSeek не смог персонализировать кейс. Повторите попытку позже.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromptLabSystemCasePreviewResponse(
        user=artifacts["user"],
        case=artifacts["case"],
        base_context=artifacts["base_context"],
        base_task=artifacts["base_task"],
        system_personalized_context=artifacts.get("system_personalized_context"),
        system_personalized_task=artifacts.get("system_personalized_task"),
    )


@router.post("/admin/prompt-lab/dialog-preview", response_model=PromptLabDialoguePreviewResponse)
def create_prompt_lab_dialog_preview(payload: PromptLabDialoguePreviewRequest, request: Request) -> PromptLabDialoguePreviewResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
    try:
        result = assessment_service.preview_prompt_lab_dialog(
            user_id=payload.user_id,
            case_id_code=payload.case_id_code,
            use_llm_personalization=True,
            case_generation_prompt_text=payload.case_generation_prompt_text,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail="DeepSeek не смог персонализировать кейс. Повторите попытку позже.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromptLabDialoguePreviewResponse(**result)


@router.post("/admin/prompt-lab/dialog-turn", response_model=PromptLabDialogueTurnResponse)
def create_prompt_lab_dialog_turn(payload: PromptLabDialogueTurnRequest, request: Request) -> PromptLabDialogueTurnResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    current_user = web_session_service.get_user_by_token(token) if token else None
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
    try:
        result = assessment_service.simulate_prompt_lab_dialog_turn(
            system_prompt=payload.system_prompt,
            case_title=payload.case_title,
            case_skills=payload.case_skills,
            methodical_context=payload.methodical_context,
            dialogue=payload.dialogue,
            interviewer_prompt_text=payload.interviewer_prompt_text,
            user_message=payload.user_message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PromptLabDialogueTurnResponse(**result)


@router.get("/admin/methodology", response_model=AdminMethodologyResponse)
def get_admin_methodology(request: Request) -> AdminMethodologyResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        return _build_admin_methodology(connection)


@router.get(
    "/admin/assessment-shadow-comparisons",
    response_model=AdminShadowComparisonResponse,
)
def get_admin_assessment_shadow_comparisons(request: Request) -> AdminShadowComparisonResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        return AdminShadowComparisonResponse(
            **assessment_shadow_repository.aggregate_comparisons(connection=connection)
        )


@router.post(
    "/admin/assessment-shadow-batches",
    response_model=AdminShadowBatchResponse,
)
def run_admin_assessment_shadow_batch(
    payload: AdminShadowBatchRequest,
    request: Request,
) -> AdminShadowBatchResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        try:
            if payload.dry_run:
                result = assessment_shadow_batch_service.preview(
                    connection=connection,
                    max_competency_runs=payload.max_competency_runs,
                )
            else:
                result = assessment_shadow_batch_service.execute(
                    connection=connection,
                    max_competency_runs=payload.max_competency_runs,
                    confirm_paid_calls=payload.confirm_paid_calls,
                )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return AdminShadowBatchResponse(**result)


@router.get("/admin/methodology/cases/{case_id_code}", response_model=AdminMethodologyCaseDetailResponse)
def get_admin_methodology_case_detail(case_id_code: str, request: Request) -> AdminMethodologyCaseDetailResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        return _build_admin_methodology_case_detail(connection, case_id_code)


@router.put("/admin/methodology/cases/{case_id_code}", response_model=AdminMethodologyCaseDetailResponse)
def update_admin_methodology_case(
    case_id_code: str,
    payload: AdminMethodologyCaseUpdateRequest,
    request: Request,
) -> AdminMethodologyCaseDetailResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        return _upsert_admin_methodology_case(connection, case_id_code, payload, user.full_name or ADMIN_FULL_NAME)


def _assessment_definition_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    return user


def _assessment_definition_permission(entity_type: str, action: str) -> str:
    config = ENTITY_CONFIG.get(entity_type)
    if config is None:
        raise HTTPException(status_code=404, detail="Assessment definition type not found")
    key = f"{action}_permission"
    permission = config.get(key)
    if not permission:
        raise HTTPException(status_code=400, detail="Unsupported assessment definition operation")
    return permission


def _require_assessment_definition_permission(connection, user, entity_type: str, action: str) -> None:
    try:
        require_platform_permission(connection, user, _assessment_definition_permission(entity_type, action))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/admin/assessment-definitions/{entity_type}",
    response_model=list[AssessmentDefinitionVersionResponse],
)
def list_assessment_definition_versions(entity_type: str, request: Request) -> list[AssessmentDefinitionVersionResponse]:
    user = _assessment_definition_user(request)
    if entity_type not in ENTITY_CONFIG:
        raise HTTPException(status_code=404, detail="Assessment definition type not found")
    permission = _assessment_definition_permission(entity_type, "view")
    with get_connection() as connection:
        try:
            require_platform_permission(connection, user, permission)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return [
            AssessmentDefinitionVersionResponse(**row)
            for row in assessment_authoring_service.list_versions(connection, entity_type=entity_type)
        ]


@router.post(
    "/admin/assessment-definitions/{entity_type}",
    response_model=AssessmentDefinitionVersionResponse,
)
def create_assessment_definition(
    entity_type: str,
    payload: AssessmentDefinitionCreateRequest,
    request: Request,
) -> AssessmentDefinitionVersionResponse:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_assessment_definition_permission(connection, user, entity_type, "edit")
        try:
            row = assessment_authoring_service.create_definition(
                connection,
                entity_type=entity_type,
                code=payload.code,
                name=payload.name,
                description=payload.description,
                definition=payload.definition,
                actor_user_id=int(user.id),
                comment=payload.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AssessmentDefinitionVersionResponse(**row)


@router.post(
    "/admin/assessment-definitions/{entity_type}/{version_id}/clone",
    response_model=AssessmentDefinitionVersionResponse,
)
def clone_assessment_definition_version(
    entity_type: str,
    version_id: int,
    payload: AssessmentDefinitionCloneRequest,
    request: Request,
) -> AssessmentDefinitionVersionResponse:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_assessment_definition_permission(connection, user, entity_type, "edit")
        try:
            row = assessment_authoring_service.clone_version(
                connection,
                entity_type=entity_type,
                source_version_id=version_id,
                actor_user_id=int(user.id),
                description=payload.description,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AssessmentDefinitionVersionResponse(**row)


@router.put(
    "/admin/assessment-definitions/{entity_type}/{version_id}",
    response_model=AssessmentDefinitionVersionResponse,
)
def update_assessment_definition_version(
    entity_type: str,
    version_id: int,
    payload: AssessmentDefinitionUpdateRequest,
    request: Request,
) -> AssessmentDefinitionVersionResponse:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_assessment_definition_permission(connection, user, entity_type, "edit")
        try:
            row = assessment_authoring_service.update_draft(
                connection,
                entity_type=entity_type,
                version_id=version_id,
                definition=payload.definition,
                description=payload.description,
                actor_user_id=int(user.id),
                comment=payload.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AssessmentDefinitionVersionResponse(**row)


@router.post("/admin/assessment-definitions/{entity_type}/{version_id}/validate")
def validate_assessment_definition_version(entity_type: str, version_id: int, request: Request) -> dict[str, object]:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_assessment_definition_permission(connection, user, entity_type, "edit")
        try:
            return assessment_authoring_service.validate_version(
                connection,
                entity_type=entity_type,
                version_id=version_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/admin/assessment-definitions/{entity_type}/{version_id}/submit",
    response_model=AssessmentDefinitionVersionResponse,
)
def submit_assessment_definition_version(
    entity_type: str,
    version_id: int,
    payload: AssessmentDefinitionTransitionRequest,
    request: Request,
) -> AssessmentDefinitionVersionResponse:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_assessment_definition_permission(connection, user, entity_type, "submit")
        try:
            row = assessment_authoring_service.submit_for_review(
                connection,
                entity_type=entity_type,
                version_id=version_id,
                actor_user_id=int(user.id),
                comment=payload.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AssessmentDefinitionVersionResponse(**row)


@router.post(
    "/admin/assessment-definitions/{entity_type}/{version_id}/publish",
    response_model=AssessmentDefinitionVersionResponse,
)
def publish_assessment_definition_version(
    entity_type: str,
    version_id: int,
    payload: AssessmentDefinitionTransitionRequest,
    request: Request,
) -> AssessmentDefinitionVersionResponse:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_assessment_definition_permission(connection, user, entity_type, "publish")
        try:
            row = assessment_authoring_service.publish(
                connection,
                entity_type=entity_type,
                version_id=version_id,
                actor_user_id=int(user.id),
                comment=payload.comment,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AssessmentDefinitionVersionResponse(**row)


@router.get(
    "/admin/assessment-configurations",
    response_model=list[AssessmentConfigurationResponse],
)
def list_assessment_configurations(request: Request) -> list[AssessmentConfigurationResponse]:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        try:
            require_platform_permission(connection, user, "configuration.publish")
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return [AssessmentConfigurationResponse(**row) for row in assessment_authoring_service.list_configurations(connection)]


@router.post(
    "/admin/assessment-configurations",
    response_model=AssessmentConfigurationResponse,
)
def create_assessment_configuration(
    payload: AssessmentConfigurationCreateRequest,
    request: Request,
) -> AssessmentConfigurationResponse:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        try:
            require_platform_permission(connection, user, "configuration.publish")
            row = assessment_authoring_service.create_configuration(
                connection,
                code=payload.code,
                name=payload.name,
                methodology_version_id=payload.methodology_version_id,
                scenario_version_id=payload.scenario_version_id,
                catalog_version_id=payload.catalog_version_id,
                actor_user_id=int(user.id),
                comment=payload.comment,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AssessmentConfigurationResponse(**row)


@router.post(
    "/admin/assessment-configurations/{configuration_id}/publish",
    response_model=AssessmentConfigurationResponse,
)
def publish_assessment_configuration(
    configuration_id: int,
    payload: AssessmentConfigurationPublishRequest,
    request: Request,
) -> AssessmentConfigurationResponse:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        try:
            require_platform_permission(connection, user, "configuration.publish")
            row = assessment_authoring_service.publish_configuration(
                connection,
                configuration_id=configuration_id,
                make_default=payload.make_default,
                actor_user_id=int(user.id),
                comment=payload.comment,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AssessmentConfigurationResponse(**row)


@router.post("/admin/m5-catalogs/plan")
def plan_m5_catalog_publication(payload: M5CatalogPlanRequest, request: Request) -> dict[str, object]:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        try:
            require_platform_permission(connection, user, "configuration.publish")
            if payload.organization_id is not None:
                scope = _get_admin_scope_or_403(connection, user)
                if not scope.is_superadmin and payload.organization_id not in scope.organization_ids:
                    raise PermissionError("Organization admin access required")
            return m5_catalog_integrity.publication_plan(
                connection, package_db_id=payload.package_db_id,
                case_version_ids=payload.case_version_ids, usage_scope=payload.usage_scope,
                organization_id=payload.organization_id,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/admin/m5-catalogs/publish")
def publish_m5_catalog(payload: M5CatalogPublishRequest, request: Request) -> dict[str, object]:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        try:
            require_platform_permission(connection, user, "configuration.publish")
            if payload.organization_id is not None:
                scope = _get_admin_scope_or_403(connection, user)
                if not scope.is_superadmin and payload.organization_id not in scope.organization_ids:
                    raise PermissionError("Organization admin access required")
            return m5_catalog_integrity.publish_catalog(
                connection, catalog_id=payload.catalog_id, catalog_version=payload.catalog_version,
                package_db_id=payload.package_db_id, case_version_ids=payload.case_version_ids,
                usage_scope=payload.usage_scope, organization_id=payload.organization_id,
                published_by=int(user.id), decision_basis=payload.decision_basis,
                idempotency_key=payload.idempotency_key,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/m5-catalogs/{catalog_db_id}")
def read_m5_catalog(catalog_db_id: int, request: Request) -> dict[str, object]:
    user = _assessment_definition_user(request)
    with get_connection() as connection:
        try:
            require_platform_permission(connection, user, "configuration.publish")
            return m5_catalog_integrity.catalog_readback(connection, catalog_db_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/admin/platform-role-assignments")
def assign_platform_role(payload: PlatformRoleAssignmentRequest, request: Request) -> dict[str, object]:
    current_user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        role = connection.execute(
            "SELECT id, code FROM platform_roles WHERE code = %s LIMIT 1",
            (payload.role_code.strip(),),
        ).fetchone()
        if role is None:
            raise HTTPException(status_code=404, detail="Platform role not found")
        target_user = connection.execute("SELECT id FROM users WHERE id = %s", (payload.user_id,)).fetchone()
        if target_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        existing = connection.execute(
            """
            SELECT id
            FROM user_platform_roles
            WHERE user_id = %s
              AND platform_role_id = %s
              AND COALESCE(organization_id, 0) = COALESCE(%s, 0)
              AND revoked_at IS NULL
            LIMIT 1
            """,
            (payload.user_id, role["id"], payload.organization_id),
        ).fetchone()
        if existing is None:
            assignment = connection.execute(
                """
                INSERT INTO user_platform_roles (
                    user_id, platform_role_id, organization_id, granted_by
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (payload.user_id, role["id"], payload.organization_id, current_user.id),
            ).fetchone()
            assignment_id = int(assignment["id"])
        else:
            assignment_id = int(existing["id"])
        return {"ok": True, "assignment_id": assignment_id, "role_code": str(role["code"])}


@router.delete("/admin/platform-role-assignments/{assignment_id}")
def revoke_platform_role(assignment_id: int, request: Request) -> dict[str, object]:
    current_user = _assessment_definition_user(request)
    with get_connection() as connection:
        _require_superadmin(connection, current_user)
        row = connection.execute(
            """
            UPDATE user_platform_roles
            SET revoked_at = NOW()
            WHERE id = %s
              AND revoked_at IS NULL
            RETURNING id
            """,
            (assignment_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Active platform role assignment not found")
        return {"ok": True, "assignment_id": int(row["id"])}


@router.post("/session/logout")
def logout_user_session(request: Request, response: FastAPIResponse) -> dict[str, bool]:
    web_session_service.delete_session(request.cookies.get(SESSION_COOKIE_NAME))
    _clear_user_session_cookie(response)
    return {"ok": True}

@router.get("", response_model=list[UserResponse])
def get_users(request: Request) -> list[UserResponse]:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail="Требуется авторизация")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        scope_sql, scope_params = admin_scope_sql(scope)
        rows = connection.execute(USER_SELECT_SQL + " WHERE TRUE " + scope_sql + " ORDER BY u.id ASC", scope_params).fetchall()
    return [UserResponse(**dict(row)) for row in rows]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, request: Request) -> UserResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        row = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(**dict(row))


@router.get("/{user_id}/profile-summary", response_model=UserProfileSummaryResponse)
def get_user_profile_summary(user_id: int, request: Request) -> UserProfileSummaryResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        user_row = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()

        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")

        user = UserResponse(**dict(user_row))

        history_rows = connection.execute(
            """
            SELECT
                us.id AS session_id,
                us.session_code,
                us.status,
                us.started_at,
                us.finished_at,
                us.expert_comment,
                COALESCE(case_stats.total_cases, 0)::int AS total_cases,
                COALESCE(case_stats.completed_cases, 0)::int AS completed_cases,
                score_stats.overall_score_percent
            FROM user_sessions us
            LEFT JOIN (
                SELECT
                    session_id,
                    COUNT(*)::int AS total_cases,
                    COUNT(*) FILTER (WHERE status IN ('answered', 'assessed'))::int AS completed_cases
                FROM session_cases
                GROUP BY session_id
            ) AS case_stats ON case_stats.session_id = us.id
            LEFT JOIN (
                SELECT
                    session_id,
                    user_id,
                    ROUND(AVG(COALESCE(alw.percent_value, 0)))::int AS overall_score_percent
                FROM session_skill_assessments ssa
                LEFT JOIN assessment_level_weights alw ON alw.level_code = ssa.assessed_level_code
                GROUP BY ssa.session_id, ssa.user_id
            ) AS score_stats ON score_stats.session_id = us.id AND score_stats.user_id = us.user_id
            WHERE us.user_id = %s
              AND us.assessment_code = 'competencies_4k'
              AND us.status = 'completed'
            ORDER BY us.started_at DESC NULLS LAST, us.id DESC
            """,
            (user_id,),
        ).fetchall()

        history: list[UserAssessmentHistoryItem] = []
        score_values: list[int] = []
        for row in history_rows:
            total_cases = int(row["total_cases"] or 0)
            completed_cases = int(row["completed_cases"] or 0)
            progress_percent = int(round((completed_cases / total_cases) * 100)) if total_cases else 0
            overall_score = int(row["overall_score_percent"]) if row["overall_score_percent"] is not None else None
            if overall_score is not None:
                score_values.append(overall_score)
            history.append(
                UserAssessmentHistoryItem(
                    session_id=row["session_id"],
                    session_code=row["session_code"],
                    status=row["status"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    completed_cases=completed_cases,
                    total_cases=total_cases,
                    progress_percent=progress_percent,
                    overall_score_percent=overall_score,
                    expert_comment=(str(row["expert_comment"]).strip() if row["status"] == "completed" and row["expert_comment"] else None),
                )
            )

        cycle_history = m8_results.list_owned_cycles(connection, user_id)
        cycle_reports = [item for item in cycle_history if item["report_id"]]

    return UserProfileSummaryResponse(
        user=user,
        total_assessments=len(cycle_history),
        completed_assessments=sum(bool(item["collection_closed_at"]) for item in cycle_history),
        average_score_percent=round(sum(score_values) / len(score_values)) if score_values else None,
        latest_session_id=history[0].session_id if history else None,
        history=history,
        cycle_reports=cycle_reports,
        cycle_history=cycle_history,
        legacy_assessments_total=len(history),
    )


@router.patch("/{user_id}/profile", response_model=UserResponse)
def update_user_profile(user_id: int, payload: UserProfileUpdateRequest, request: Request) -> UserResponse:
    user = _require_matching_session_user(request, user_id)
    if 'email' in payload.model_fields_set:
        try:
            require_unchanged_email(user.email, payload.email)
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
    with get_connection() as connection:
        existing = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()

        if existing is None:
            raise HTTPException(status_code=404, detail="User not found")

        avatar_data_url = payload.avatar_data_url
        if avatar_data_url is not None and not avatar_data_url.startswith("data:image/"):
            raise HTTPException(status_code=400, detail="Некорректный формат изображения")

        fields = [name for name in ('telegram', 'avatar_data_url') if name in payload.model_fields_set]
        if fields:
            connection.execute(
                'UPDATE users SET ' + ', '.join(name + ' = %s' for name in fields) + ' WHERE id = %s',
                tuple(getattr(payload, name) for name in fields) + (user_id,),
            )
            connection.commit()

        updated = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()

    return UserResponse(**dict(updated))


def _require_profile_dialogue_owner(request: Request, session_id: str) -> UserResponse:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail="Сессия не найдена. Войдите заново.")
    with get_connection() as connection:
        owned = connection.execute(
            "SELECT 1 FROM agent_conversation_sessions WHERE session_id=%s AND user_id=%s",
            (session_id, user.id),
        ).fetchone()
    if owned is None:
        raise HTTPException(403, detail="Нет доступа к диалогу профиля.")
    return user


@router.post("/agent/message", response_model=AgentReply)
def process_agent_message(payload: AgentMessageRequest, request: Request, response: FastAPIResponse) -> AgentReply:
    user = _require_profile_dialogue_owner(request, payload.session_id)
    operation_id = request.headers.get("X-Agent4K-Operation-Id")
    try:
        operation_progress_service.begin(
            operation_id,
            title="Обновляем профиль",
            message="Сохраняем данные пользователя и формируем обновленный профиль.",
            steps=PROFILE_SAVE_STEPS,
        )
        reply = interviewer_agent.reply(
            session_id=payload.session_id,
            message=payload.message,
            authenticated_user_id=user.id,
            progress_operation_id=operation_id,
        )
        if reply.user is not None:
            _set_user_session_cookie(response, web_session_service.create_session(reply.user.id))
        operation_progress_service.complete(
            operation_id,
            title="Профиль готов",
            message="Профиль пользователя подготовлен. Можно переходить к следующему шагу.",
        )
        return reply
    except PermissionError as exc:
        raise HTTPException(403, detail="Нет доступа к диалогу профиля.") from exc
    except KeyError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _role_profile_option(role: dict) -> dict[str, object]:
    description = role["definition"]["description"]
    return {
        "version_id": role["id"],
        "code": role["code"],
        "version": role["version"],
        "name": description["name"],
        "short_description": description["short_description"],
        "scope": role["scope"],
        "organization_id": role["organization_id"],
    }


@router.post("/admin/organizations/{organization_id}/role-profiles/drafts", status_code=201)
def create_organization_role_profile(
    organization_id: int,
    payload: OrganizationRoleProfileDraftRequest,
    request: Request,
) -> dict[str, object]:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        if not scope.is_superadmin and organization_id not in scope.organization_ids:
            raise HTTPException(status_code=403, detail="Organization admin access required")
        organization = connection.execute(
            "SELECT id FROM organizations WHERE id = %s AND is_active = TRUE",
            (organization_id,),
        ).fetchone()
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        try:
            version_id = create_organization_role_profile_draft(
                connection,
                organization_id=organization_id,
                definition=payload.definition,
                provenance=payload.provenance,
                base_role_version_id=payload.base_role_version_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        connection.commit()
    return {"version_id": version_id, "organization_id": organization_id, "status": "draft"}


@router.get("/role-profiles/available")
def get_my_role_profiles(request: Request) -> dict[str, object]:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    with get_connection() as connection:
        roles = list_available_role_profiles(connection, user_id=user.id)
        selected = get_selected_role_profile(connection, user_id=user.id)
    return {
        "roles": [_role_profile_option(role) for role in roles],
        "selected_version_id": selected["id"] if selected else None,
    }


@router.put("/role-profiles/selection")
def select_my_role_profile(payload: RoleProfileSelectionRequest, request: Request) -> dict[str, object]:
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    try:
        with get_connection() as connection:
            _require_unmanaged_profile_path(connection, user_id=int(user.id))
            role = select_role_profile_for_user(connection, user_id=user.id, version_id=payload.version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _role_profile_option(role)


@router.get("/assessment/profile/options")
def get_participant_profile_options(request: Request):
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail="Требуется авторизация")
    try:
        with get_connection() as connection:
            _require_unmanaged_profile_path(connection, user_id=int(user.id))
            return participant_profile.options(connection, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.post("/agent/profile/confirm", response_model=AgentReply)
def confirm_agent_profile(payload: AgentProfileConfirmRequest, request: Request, response: FastAPIResponse) -> AgentReply:
    operation_id = request.headers.get("X-Agent4K-Operation-Id")
    try:
        authenticated_user = _require_profile_dialogue_owner(request, payload.session_id)
        with get_connection() as connection:
            _require_unmanaged_profile_path(connection, user_id=int(authenticated_user.id))
        try:
            require_unchanged_email(authenticated_user.email, payload.email)
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc
        operation_progress_service.begin(
            operation_id,
            title="Подтверждаем профиль",
            message="Сохраняем актуальные данные профиля.",
            steps=PROFILE_SAVE_STEPS,
        )
        if payload.personalized_profile is not None:
            with get_connection() as connection:
                reply, profile_id = interviewer_agent.confirm_personalized_profile(connection,
                    payload=payload, authenticated_user_id=authenticated_user.id)
                reply = reply.model_copy(update={"dashboard": _build_dashboard(connection, reply.user, profile_id=profile_id)})
                connection.commit()
            interviewer_agent.invalidate_session(payload.session_id)
        else:
            if not payload.role_id or not all((payload.position.strip(), payload.duties.strip(), payload.company_industry.strip())):
                raise ValueError('Заполните обязательные поля профиля.')
            reply = interviewer_agent.confirm_existing_profile(
                session_id=payload.session_id,
                full_name=payload.full_name,
                email=payload.email,
                telegram=payload.telegram,
                position=payload.position,
                duties=payload.duties,
                selected_role_id=payload.role_id,
                company_industry=payload.company_industry,
                consent_accepted=payload.consent_accepted,
                authenticated_user_id=authenticated_user.id,
                progress_operation_id=operation_id,
            )
            if reply.user is not None:
                with get_connection() as connection:
                    reply = reply.model_copy(update={"dashboard": _build_dashboard(connection, reply.user)})
        if reply.user is not None:
            _set_user_session_cookie(response, web_session_service.create_session(reply.user.id))
        operation_progress_service.complete(operation_id, title="Профиль готов", message="Данные подтверждены.")
        return reply
    except KeyError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/{user_id}/assessment/start",
    response_model=AssessmentPreparationEnqueueResponse,
    status_code=202,
)
def start_assessment(user_id: int, request: Request) -> AssessmentPreparationEnqueueResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        _require_unmanaged_profile_path(connection, user_id=user_id)
    operation_id = request.headers.get("X-Agent4K-Operation-Id") or uuid4().hex
    operation_progress_service.begin(
        operation_id,
        title="Подготавливаем ассессмент",
        message="Задание поставлено в очередь подготовки.",
        steps=ASSESSMENT_START_STEPS,
    )
    with get_connection() as connection:
        row = connection.execute(
            USER_SELECT_SQL
            + """
            WHERE u.id = %s
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        operation_progress_service.fail(operation_id, message="Пользователь не найден.")
        raise HTTPException(status_code=404, detail="User not found")

    queued = assessment_preparation_queue.enqueue(
        operation_id=operation_id,
        user=_user_response_from_row(row),
    )
    return AssessmentPreparationEnqueueResponse(**queued)


@router.get(
    "/assessment/preparation/{operation_id}",
    response_model=AssessmentPreparationStatusResponse,
)
def get_assessment_preparation(operation_id: str, request: Request) -> AssessmentPreparationStatusResponse:
    job = assessment_preparation_queue.get_status(operation_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание подготовки ассессмента не найдено.")
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия не найдена. Войдите заново.")
    if int(job["user_id"]) != int(user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к чужой подготовке ассессмента.")
    result_payload = job.pop("result_json", None)
    if isinstance(result_payload, str):
        result_payload = json.loads(result_payload)
    return AssessmentPreparationStatusResponse(
        **job,
        result=AssessmentStartResponse.model_validate(result_payload) if result_payload else None,
    )


@router.post("/assessment/message", response_model=AssessmentMessageResponse)
def process_assessment_message(payload: AssessmentMessageRequest, request: Request) -> AssessmentMessageResponse:
    _require_assessment_session_owner(request, payload.session_code)
    operation_id = request.headers.get("X-Agent4K-Operation-Id")
    try:
        operation_progress_service.begin(
            operation_id,
            title="Обрабатываем ответ по кейсу",
            message="Сохраняем ответ и подготавливаем следующий шаг интервью.",
            steps=ASSESSMENT_MESSAGE_STEPS,
        )
        result = interviewer_agent.continue_case_interview(
            session_code=payload.session_code,
            message=payload.message,
            progress_operation_id=operation_id,
        )
        assessment_completed = bool(getattr(result, "assessment_completed", False))
        if assessment_completed:
            assessment_analysis_queue.notify()
        operation_progress_service.complete(
            operation_id,
            title="Итоговый анализ запущен" if assessment_completed else "Следующий шаг готов",
            message=(
                "Все кейсы обработаны. Итоговый профиль формируется в фоне."
                if assessment_completed
                else "Интервью обновлено. Можно продолжать работу с кейсом."
            ),
        )
        return result
    except ValueError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{user_id}/assessment/{session_id}/analysis-status",
    response_model=AssessmentAnalysisStatusResponse,
)
def get_assessment_analysis_status(
    user_id: int,
    session_id: int,
    request: Request,
) -> AssessmentAnalysisStatusResponse:
    _require_matching_session_user(request, user_id)
    job = assessment_analysis_queue.get_status(session_id=session_id, user_id=user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задание итогового анализа не найдено.")
    return AssessmentAnalysisStatusResponse(**job)


@router.post(
    "/{user_id}/assessment/{session_id}/analysis-retry",
    response_model=AssessmentAnalysisStatusResponse,
)
def retry_assessment_analysis(
    user_id: int,
    session_id: int,
    request: Request,
) -> AssessmentAnalysisStatusResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        session_row = connection.execute(
            """
            SELECT id, user_id, status
            FROM user_sessions
            WHERE id = %s
              AND user_id = %s
            """,
            (session_id, user_id),
        ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Assessment session not found")
    if str(session_row["status"]) == "completed":
        raise HTTPException(status_code=409, detail="Итоговый отчет уже готов.")
    if str(session_row["status"]) not in {"cases_completed", "analyzing", "failed"}:
        raise HTTPException(status_code=409, detail="Повторный анализ доступен только после завершения всех кейсов.")
    assessment_analysis_queue.enqueue_retry(session_id=session_id, user_id=user_id)
    job = assessment_analysis_queue.get_status(session_id=session_id, user_id=user_id)
    if job is None:
        raise HTTPException(status_code=500, detail="Не удалось повторно запустить итоговый анализ.")
    return AssessmentAnalysisStatusResponse(**job)


@router.post("/assessment/client-event")
def log_assessment_client_event(payload: AssessmentClientEventRequest, request: Request) -> dict:
    _require_assessment_session_owner(request, payload.session_code)
    assessment_logger.info(
        "Assessment client event event=%s message_type=%s session_code=%s case_number=%s error_type=%s user_agent=%s",
        payload.event[:64],
        (payload.message_type or "")[:32],
        payload.session_code[:64],
        payload.case_number,
        (payload.error_type or "")[:64],
        (request.headers.get("user-agent") or "")[:240],
    )
    return {"ok": True}


@router.post("/assessment/pause")
def pause_assessment_timer(payload: AssessmentTimerControlRequest, request: Request) -> dict:
    _require_assessment_session_owner(request, payload.session_code)
    try:
        assessment_service.pause_assessment_dialogue(payload.session_code)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{user_id}/assessment/{session_id}/skill-assessments", response_model=list[SkillAssessmentResponse])
def get_skill_assessments(user_id: int, session_id: int, request: Request) -> list[SkillAssessmentResponse]:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")

        session_row = connection.execute(
            """
            SELECT id
            FROM user_sessions
            WHERE id = %s
              AND user_id = %s
            """,
            (session_id, user_id),
        ).fetchone()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Assessment session not found")

        rows = connection.execute(
            """
            SELECT
                id, session_id, user_id, skill_id, competency_skill_id, competency_name,
                skill_code, skill_name, assessed_level_code, assessed_level_name,
                rubric_match_scores, structural_elements, red_flags, found_evidence,
                detected_required_blocks, missing_required_blocks, block_coverage_percent,
                (
                    SELECT STRING_AGG(DISTINCT scsa.expected_artifact_name, ', ')
                    FROM session_case_skill_analysis scsa
                    WHERE scsa.session_id = session_skill_assessments.session_id
                      AND scsa.user_id = session_skill_assessments.user_id
                      AND scsa.skill_id = session_skill_assessments.skill_id
                      AND COALESCE(scsa.expected_artifact_name, '') <> ''
                ) AS expected_artifact_names,
                (
                    SELECT ROUND(AVG(scsa.artifact_compliance_percent))::int
                    FROM session_case_skill_analysis scsa
                    WHERE scsa.session_id = session_skill_assessments.session_id
                      AND scsa.user_id = session_skill_assessments.user_id
                      AND scsa.skill_id = session_skill_assessments.skill_id
                      AND scsa.artifact_compliance_percent IS NOT NULL
                ) AS artifact_compliance_percent,
                rationale,
                evidence_excerpt, source_session_case_ids, created_at, updated_at
            FROM session_skill_assessments
            WHERE user_id = %s
              AND session_id = %s
            ORDER BY competency_name ASC, skill_code ASC NULLS LAST, skill_name ASC
            """,
            (user_id, session_id),
        ).fetchall()

    return [SkillAssessmentResponse(**dict(row)) for row in rows]


@router.get(
    "/{user_id}/assessment/by-code/{session_code}",
    response_model=AssessmentSessionLookupResponse,
)
def get_assessment_session_by_code(user_id: int, session_code: str, request: Request) -> AssessmentSessionLookupResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")

        session_row = connection.execute(
            """
            SELECT id, session_code
            FROM user_sessions
            WHERE user_id = %s
              AND session_code = %s
            """,
            (user_id, session_code),
        ).fetchone()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Assessment session not found")

    return AssessmentSessionLookupResponse(
        user_id=user_id,
        session_id=int(session_row["id"]),
        session_code=str(session_row["session_code"]),
    )


@router.get(
    "/{user_id}/assessment/{session_id}/report-interpretation",
    response_model=AssessmentReportInterpretationResponse,
)
def get_report_interpretation(
    user_id: int,
    session_id: int,
    request: Request,
) -> AssessmentReportInterpretationResponse:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")

        session_row = connection.execute(
            """
            SELECT id
            FROM user_sessions
            WHERE id = %s
              AND user_id = %s
            """,
            (session_id, user_id),
        ).fetchone()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Assessment session not found")

        rows = connection.execute(
            """
            SELECT
                competency_name,
                skill_code,
                skill_name,
                assessed_level_code,
                red_flags,
                found_evidence,
                block_coverage_percent,
                (
                    SELECT ROUND(AVG(scsa.artifact_compliance_percent))::int
                    FROM session_case_skill_analysis scsa
                    WHERE scsa.session_id = session_skill_assessments.session_id
                      AND scsa.user_id = session_skill_assessments.user_id
                      AND scsa.skill_id = session_skill_assessments.skill_id
                      AND scsa.artifact_compliance_percent IS NOT NULL
                ) AS artifact_compliance_percent
            FROM session_skill_assessments
            WHERE user_id = %s
              AND session_id = %s
            ORDER BY competency_name ASC, skill_code ASC NULLS LAST, skill_name ASC
            """,
            (user_id, session_id),
        ).fetchall()
        skill_rows = [dict(row) for row in rows]
        level_percent_map = get_level_percent_map(connection)
        grouped: dict[str, list[dict]] = {}
        for row in skill_rows:
            grouped.setdefault(row["competency_name"] or "Без категории", []).append(row)
        competency_average = []
        for competency_name, skills in grouped.items():
            avg_percent = round(
                sum(level_percent_map.get(skill["assessed_level_code"], 0) for skill in skills) / len(skills)
            )
            evidence_hits = sum(1 for skill in skills if _parse_json_array_field(skill.get("found_evidence")))
            block_values = [float(skill["block_coverage_percent"]) for skill in skills if skill.get("block_coverage_percent") is not None]
            artifact_values = [float(skill["artifact_compliance_percent"]) for skill in skills if skill.get("artifact_compliance_percent") is not None]
            red_flag_total = sum(len(_parse_json_array_field(skill.get("red_flags"))) for skill in skills)
            competency_average.append(
                {
                    "name": competency_name,
                    "value": avg_percent,
                    "evidence_hit_rate": round(evidence_hits / len(skills), 2),
                    "avg_block_coverage": round(sum(block_values) / len(block_values), 2) if block_values else 0,
                    "avg_artifact_compliance": round(sum(artifact_values) / len(artifact_values), 2) if artifact_values else 0,
                    "avg_red_flag_count": round(red_flag_total / len(skills), 2),
                }
            )
        competency_average.sort(key=lambda item: str(item["name"]))
        interpretation = _build_report_interpretation_payload(skill_rows, competency_average)

    return AssessmentReportInterpretationResponse(**interpretation)


@router.get(
    "/{user_id}/assessment/{session_id}/structured-analysis",
    response_model=list[SessionCaseStructuredAnalysisResponse],
)
def get_session_case_structured_analysis(
    user_id: int,
    session_id: int,
    request: Request,
) -> list[SessionCaseStructuredAnalysisResponse]:
    _require_matching_session_user(request, user_id)
    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")

        session_row = connection.execute(
            """
            SELECT id
            FROM user_sessions
            WHERE id = %s
              AND user_id = %s
            """,
            (session_id, user_id),
        ).fetchone()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Assessment session not found")

        rows = connection.execute(
            """
            SELECT
                scsa.id,
                scsa.session_id,
                scsa.user_id,
                scsa.session_case_id,
                scsa.case_registry_id,
                cr.case_id_code,
                cr.title AS case_title,
                scsa.skill_id,
                s.skill_code,
                s.skill_name,
                scsa.competency_name,
                scsa.expected_artifact_code,
                scsa.expected_artifact_name,
                scsa.detected_artifact_parts,
                scsa.missing_artifact_parts,
                scsa.artifact_compliance_percent,
                scsa.structural_elements,
                scsa.detected_required_blocks,
                scsa.missing_required_blocks,
                scsa.block_coverage_percent,
                scsa.red_flags,
                scsa.found_evidence,
                scsa.detected_signals,
                scsa.evidence_excerpt,
                scsa.source_message_count,
                scsa.analyzed_at,
                scsa.updated_at
            FROM session_case_skill_analysis scsa
            JOIN skills s ON s.id = scsa.skill_id
            LEFT JOIN cases_registry cr ON cr.id = scsa.case_registry_id
            WHERE scsa.user_id = %s
              AND scsa.session_id = %s
            ORDER BY scsa.session_case_id ASC, scsa.competency_name ASC, s.skill_code ASC NULLS LAST, s.skill_name ASC
            """,
            (user_id, session_id),
        ).fetchall()

    return [SessionCaseStructuredAnalysisResponse(**dict(row)) for row in rows]


@router.get('/{user_id}/assessment/{session_id}/report.pdf')
def retired_skill_assessment_pdf(user_id: int, session_id: int, request: Request):
    _require_matching_session_user(request, user_id)
    raise HTTPException(410, detail='Старый PDF отчёта закрыт. Используйте сохранённый M8 Report.')


# PM-05: restricted QA evidence processing. Never produces IA or a user report.
from Api import m6_repository, m6_input_resolver_v2 as m6_input_resolver, m6_package, m6_worker
from Api.m6_contracts import CreateEvidenceRequest
from fastapi import BackgroundTasks


@router.post('/admin/m6-evidence/requests', status_code=202)
def create_m6_evidence_request(payload: CreateEvidenceRequest, request: Request, background_tasks: BackgroundTasks):
    user = _m5_superadmin(request)
    try:
        handoff_id = str(UUID(payload.handoff_id))
        with get_connection() as connection:
            existing = m6_repository.existing_key(connection, handoff_id, payload.idempotency_key, payload.mechanism_ref)
            if existing:
                request_id = existing['id']
            else:
                as_db_id, material = m6_input_resolver.resolve(connection, handoff_id)
                mechanism = m6_package.load_mechanism(payload.mechanism_ref)
                saved = m6_repository.enqueue(connection, as_db_id=as_db_id, handoff_id=handoff_id,
                    key=payload.idempotency_key, material=material, mechanism=mechanism, created_by=int(user.id))
                request_id = saved['id']
            connection.commit()
            result = m6_repository.read_request(connection, request_id)
        background_tasks.add_task(m6_worker.run_request, str(request_id))
        return result
    except (ValueError, KeyError, OSError) as exc:
        raise HTTPException(409, detail='M6_REQUEST_REJECTED') from exc


@router.get('/admin/m6-evidence/requests/{request_id}')
def get_m6_evidence_request(request_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            return m6_repository.read_request(connection, request_id)
    except ValueError as exc:
        raise HTTPException(404, detail='M6_REQUEST_NOT_FOUND') from exc


@router.get('/admin/m6-evidence/analyses/{revision_id}')
def get_m6_evidence_analysis(revision_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            return m6_repository.read_analysis(connection, revision_id)
    except ValueError as exc:
        raise HTTPException(404, detail='M6_ANALYSIS_UNAVAILABLE') from exc


# PM-05 M6-B: restricted synthetic QA path for interim analysis, IA and C-54.
from Api import m6_assessment_repository, m6_assessment_package, m6_assessment_worker
from Api.m6_assessment_contracts import CreateAssessmentRequest


@router.post('/admin/m6-assessments/requests', status_code=202)
def create_m6_assessment_request(payload: CreateAssessmentRequest, request: Request, background_tasks: BackgroundTasks):
    user = _m5_superadmin(request)
    try:
        revision_id = str(UUID(payload.evidence_revision_id))
        with get_connection() as connection:
            saved = m6_assessment_repository.existing_key(connection, revision_id, payload.idempotency_key, payload.mechanism_ref)
            if not saved:
                mechanism = m6_assessment_package.load_mechanism(payload.mechanism_ref)
                saved = m6_assessment_repository.enqueue(connection, evidence_revision_id=revision_id,
                    key=payload.idempotency_key, mechanism=mechanism, created_by=int(user.id))
            connection.commit()
            result = m6_assessment_repository.read_request(connection, saved['id'])
        background_tasks.add_task(m6_assessment_worker.run_request, str(saved['id']))
        return result
    except (ValueError, KeyError, OSError) as exc:
        raise HTTPException(409, detail='M6_ASSESSMENT_REQUEST_REJECTED') from exc


@router.get('/admin/m6-assessments/requests/{request_id}')
def get_m6_assessment_request(request_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            return m6_assessment_repository.read_request(connection, request_id)
    except ValueError as exc:
        raise HTTPException(404, detail='M6_ASSESSMENT_REQUEST_NOT_FOUND') from exc


@router.get('/admin/m6-assessments/results/{revision_id}')
def get_m6_assessment_result(revision_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            return m6_assessment_repository.read_result(connection, revision_id)
    except ValueError as exc:
        raise HTTPException(404, detail='M6_ASSESSMENT_UNAVAILABLE') from exc


@router.post('/admin/m6-cycles/{cycle_id}/calculations', status_code=201)
def create_m6_cycle_calculation(cycle_id: UUID, payload: CreateAggregationRequest, request: Request):
    user = _m5_superadmin(request)
    try:
        with get_connection() as connection:
            cycle = connection.execute("SELECT usage_scope FROM m5_cycles WHERE cycle_id=%s", (cycle_id,)).fetchone()
            if not cycle or cycle['usage_scope'] != 'qa':
                raise ValueError('M6_MANUAL_ADMISSION_QA_ONLY')
            result = m6_cycle_aggregation_repository.create(connection, cycle_id=str(cycle_id),
                key=payload.idempotency_key, expected_composition_checksum=payload.expected_composition_checksum,
                admission_mechanism_version=payload.admission_mechanism_version,
                decisions=[x.model_dump() for x in payload.decisions], created_by=int(user.id))
            connection.commit()
            return result
    except (ValueError, KeyError, OSError) as exc:
        raise HTTPException(409, detail=str(exc)) from exc



@router.post('/admin/m6-cycles/{cycle_id}/substantive-calculations', status_code=201)
def create_m6_substantive_calculation(cycle_id: UUID, payload: CreateSubstantiveAggregationRequest, request: Request):
    user = _m5_superadmin(request)
    try:
        return m6_cycle_aggregation_repository.create_substantive_detached(
            cycle_id=str(cycle_id), key=payload.idempotency_key,
            expected_composition_checksum=payload.expected_composition_checksum, created_by=int(user.id),
            connection_factory=get_connection)
    except (ValueError, KeyError, OSError) as exc:
        raise HTTPException(409, detail='M6_SUBSTANTIVE_CALCULATION_UNAVAILABLE') from exc


@router.get('/admin/m6-cycles/{cycle_id}/calculations/latest')
def get_latest_m6_cycle_calculation(cycle_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            return m6_cycle_aggregation_repository.read_latest_for_cycle(connection, str(cycle_id))
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


# PM-06/PM-07 M8: versioned Results and C-67. Creation remains an explicit
# authorized operation until the Task 10 orchestration path is accepted.
@router.post('/admin/m8-cycles/{cycle_id}/results', status_code=201)
def create_m8_results(cycle_id: UUID, payload: CreateResultsRequest, request: Request):
    user = _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result = m8_results.create_results(connection, cycle_id=str(cycle_id), calculation_id=payload.calculation_id,
                key=payload.idempotency_key, target_profile=None, created_by=int(user.id))
            connection.commit(); return result
    except (ValueError, KeyError) as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.post('/admin/m8-reports', status_code=201)
def create_m8_report(payload: CreateReportRequest, request: Request):
    user = _m5_superadmin(request)
    try:
        return m8_results.create_report_detached(
            results_revision_id=payload.results_revision_id, audience=payload.audience,
            key=payload.idempotency_key,
            target_profile=payload.target_profile.model_dump() if payload.target_profile else None,
            created_by=int(user.id), connection_factory=get_connection)
    except (ValueError, KeyError) as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.post('/admin/m8-report-corrections/candidates', status_code=201)
def prepare_m8_report_correction(payload: PrepareReportCorrectionRequest, request: Request):
    user = _m5_superadmin(request)
    try:
        with get_connection() as connection:
            prepared = m8_report_corrections.prepare(connection,
                expected_report_id=payload.expected_report_id, result_revision_id=payload.result_revision_id,
                kind=payload.kind, incident_ref=payload.incident_ref,
                participant_reason=payload.participant_reason, descriptive=payload.descriptive,
                created_by=int(user.id))
            connection.commit()
            return prepared
    except (ValueError, KeyError) as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.post('/admin/m8-report-corrections', status_code=201)
def publish_m8_report_correction(payload: PublishReportCorrectionRequest, request: Request):
    user = _m5_superadmin(request)
    try:
        with get_connection() as connection:
            report = m8_report_corrections.publish(connection,
                candidate_id=payload.candidate_id, expected_report_id=payload.expected_report_id,
                key=payload.idempotency_key, created_by=int(user.id))
            connection.commit()
            return report
    except (ValueError, KeyError) as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.get('/admin/m8-reports/{report_id}')
def read_admin_m8_report(report_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection: return m8_results.read_report(connection, str(report_id))
    except ValueError as exc: raise HTTPException(404, detail=str(exc)) from exc


@router.get('/admin/m8-reports/{report_id}/pdf')
def download_admin_m8_report(report_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            report = m8_results.read_report(connection, str(report_id))
            report['correction'] = m8_report_corrections.public_notice(connection, report)
    except ValueError as exc: raise HTTPException(404, detail=str(exc)) from exc
    pdf = _render_saved_report_pdf(report)
    return Response(content=pdf, media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="4k-report-{report_id}.pdf"'})


def _m8_owned_cycle(request: Request, cycle_id: str):
    user = _m7_owned_cycle(request, cycle_id)
    with get_connection() as connection:
        if not m8_results.owner_can_read_cycle(connection, cycle_id, user.id):
            raise HTTPException(403, detail='Нет доступа к Cycle этой организации.')
    return user


@router.get('/assessment/m8/history', response_model=M8HistoryResponse)
def read_owned_m8_history(request: Request):
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail='Требуется авторизация')
    with get_connection() as connection:
        cycles = m8_results.list_owned_cycles(connection, user.id)
    return {'owner_user_id':user.id, 'cycles':cycles, 'assessments_total':len(cycles),
            'reports_total':sum(bool(c['report_id']) for c in cycles),
            'completed_assessments':sum(bool(c['collection_closed_at']) for c in cycles)}


@router.get('/assessment/m8/cycles/{cycle_id}/status')
def read_owned_m8_status(cycle_id: UUID, request: Request):
    _m8_owned_cycle(request, str(cycle_id))
    with get_connection() as connection:
        cycle = m7_completion.read_status(connection, str(cycle_id))
        pipeline = connection.execute("""SELECT p.status,p.stage,p.error_code FROM m10_pipeline_runs p
            JOIN m5_cycles c ON c.id=p.cycle_db_id WHERE c.cycle_id=%s""", (cycle_id,)).fetchone()
        cycle = {**cycle, 'preparation': preparation_observation.report_status(connection, str(cycle_id)) if pipeline else None}
        if pipeline and pipeline['status']=='failed':
            try:
                report = m8_results.read_latest_report(connection, str(cycle_id), 'assessee')
            except ValueError:
                report = None
            if not report or report.get('c67', {}).get('processing', {}).get('status', 'failed') == 'failed':
                return {**cycle,'results_status':'failed',
                    'report_status':'limited' if report else 'not_created',
                    'report_id':report['id'] if report else None,
                    'pipeline_stage':pipeline['stage'],
                    'processing_error':pipeline['error_code'],
                    'processing':{'contract_version':'m10-processing-recovery/1.0.0','status':'failed',
                        'message':'Не удалось завершить техническую обработку. Сохранённые ответы не потеряны.',
                        'allowed_actions':[]}}
        try:
            report = m8_results.read_latest_report(connection, str(cycle_id), 'assessee')
            partial = report['c67'].get('partial_result')
            new_cycle = ({'action':'start_new_cycle','method':'POST','href':'/assessment/cycles/start',
                          'availability':'requires_current_profile_configuration_catalog_and_membership'}
                         if partial and partial.get('is_incomplete') else None)
            return {**cycle, 'results_status': 'ready', 'report_status': report['status'], 'report_id': report['id'],
                    'pipeline_stage': pipeline['stage'] if pipeline else 'report_ready', 'processing_error': None,
                    'processing':{'contract_version':'m10-processing-recovery/1.0.0',
                        'status':'recovered' if pipeline and pipeline['stage']=='recovered_report_ready' else 'completed',
                        'message':'Обработка восстановлена.' if pipeline and pipeline['stage']=='recovered_report_ready' else 'Обработка завершена.',
                        'allowed_actions':([new_cycle] if new_cycle else [])},
                    'partial_result':partial,'new_cycle':new_cycle}
        except ValueError:
            try:
                m8_results.read_latest_results(connection, str(cycle_id))
                return {**cycle, 'results_status': 'ready', 'report_status': 'not_created', 'report_id': None,
                        'pipeline_stage':pipeline['stage'] if pipeline else 'results_ready','processing_error':None,
                        'processing':{'contract_version':'m10-processing-recovery/1.0.0','status':'processing',
                                      'message':'Готовится представление результата.','allowed_actions':[]}}
            except ValueError:
                pass
            result_status = 'processing' if cycle['collection_status'] in {'collection_closed','calculation_pending'} else cycle['collection_status']
            return {**cycle, 'results_status': result_status, 'report_status': 'not_created', 'report_id': None,
                    'pipeline_stage':pipeline['stage'] if pipeline else None,'processing_error':None,
                    'processing':{'contract_version':'m10-processing-recovery/1.0.0','status':'processing',
                                  'message':'Результат обрабатывается.','allowed_actions':[]}}


@router.post('/admin/assessment/m8/cycles/{cycle_id}/processing-recovery', status_code=202)
def request_m8_processing_recovery(cycle_id: UUID, payload: M10ProcessingRecoveryRequest, request: Request):
    user = _assessment_definition_user(request)
    try:
        with get_connection() as connection:
            require_platform_permission(connection, user, "configuration.publish")
            scope = _get_admin_scope_or_403(connection, user)
            if not scope.is_superadmin:
                raise PermissionError("Service recovery requires superadmin authority")
            cycle = connection.execute("SELECT organization_id FROM m5_cycles WHERE cycle_id=%s", (cycle_id,)).fetchone()
            if cycle is None:
                raise ValueError("M5_CYCLE_NOT_FOUND")
            result = m10_orchestration.request_processing_recovery(
                connection, cycle_id=str(cycle_id), idempotency_key=payload.idempotency_key,
                created_by=int(user.id))
            connection.commit()
            return {"recovery_id":str(result['id']),"status":result['status'],
                    "contract_version":"m10-processing-recovery/1.0.0"}
    except PermissionError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from exc


@router.get('/assessment/m8/cycles/{cycle_id}/results')
def read_owned_m8_results(cycle_id: UUID, request: Request):
    _m8_owned_cycle(request, str(cycle_id))
    try:
        with get_connection() as connection: return m8_results.read_latest_results(connection, str(cycle_id))
    except ValueError as exc: raise HTTPException(404, detail=str(exc)) from exc


@router.get('/assessment/m8/cycles/{cycle_id}/reports/latest')
def read_owned_m8_report(cycle_id: UUID, request: Request):
    _m8_owned_cycle(request, str(cycle_id))
    try:
        with get_connection() as connection:
            report = m8_results.read_latest_report(connection, str(cycle_id), 'assessee')
            return {**m8_report_access.public_projection(report),
                    "correction": m8_report_corrections.public_notice(connection, report)}
    except ValueError as exc: raise HTTPException(404, detail=str(exc)) from exc


def _owned_saved_report(request: Request, report_id: UUID, *, include_correction: bool = False):
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail='Требуется авторизация')
    with get_connection() as connection:
        scope = connection.execute("""SELECT c.cycle_id,p.audience FROM m8_reports p
            JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
            JOIN m8_results r ON r.id=rr.results_id JOIN m5_cycles c ON c.id=r.cycle_db_id
            WHERE p.id=%s""", (report_id,)).fetchone()
        if not scope:
            raise HTTPException(404, detail='M8_REPORT_NOT_FOUND')
        if scope['audience'] != 'assessee' or not m8_results.owner_can_read_cycle(connection, str(scope['cycle_id']), user.id):
            raise HTTPException(403, detail='Нет доступа к этому Report.')
        try:
            report = m8_results.read_report(connection, str(report_id))
            if include_correction:
                report['correction'] = m8_report_corrections.public_notice(connection, report)
            return report
        except ValueError as exc:
            raise HTTPException(409, detail='Сохранённый Report временно недоступен.') from exc


@router.get('/assessment/m8/reports/{report_id}')
def read_owned_saved_m8_report(report_id: UUID, request: Request):
    report = _owned_saved_report(request, report_id, include_correction=True)
    return {**m8_report_access.public_projection(report), "correction": report['correction']}


@router.get('/assessment/m8/reports/{report_id}/comparison')
def compare_owned_saved_m8_report(report_id: UUID, request: Request, previous_report_id: UUID | None = None):
    """Compare exact saved reports; omission selects the latest earlier completed Cycle."""
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail='Требуется авторизация')
    with get_connection() as connection:
        current_scope = connection.execute("""SELECT p.id,c.id AS cycle_db_id,c.cycle_id,c.organization_id,
                c.owner_user_id,c.created_at AS cycle_created_at,c.collection_closed_at
            FROM m8_reports p
            JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
            JOIN m8_results r ON r.id=rr.results_id JOIN m5_cycles c ON c.id=r.cycle_db_id
            WHERE p.id=%s AND p.audience='assessee'""", (report_id,)).fetchone()
        if not current_scope:
            raise HTTPException(404, detail='M8_REPORT_NOT_FOUND')
        if not current_scope['collection_closed_at'] or not m8_results.owner_can_read_cycle(
            connection, str(current_scope['cycle_id']), user.id
        ):
            raise HTTPException(403, detail='Нет доступа к текущему Report.')
        if previous_report_id:
            previous_scope = connection.execute("""SELECT p.id,c.cycle_id,c.organization_id,c.owner_user_id,
                    c.created_at AS cycle_created_at,c.collection_closed_at
                FROM m8_reports p
                JOIN m8_result_revisions rr ON rr.id=p.result_revision_id
                JOIN m8_results r ON r.id=rr.results_id JOIN m5_cycles c ON c.id=r.cycle_db_id
                WHERE p.id=%s AND p.audience='assessee'""", (previous_report_id,)).fetchone()
        else:
            previous_scope = connection.execute("""SELECT p.id,c.cycle_id,c.organization_id,c.owner_user_id,
                    c.created_at AS cycle_created_at,c.collection_closed_at
                FROM m5_cycles c JOIN m8_results r ON r.cycle_db_id=c.id
                JOIN m8_result_revisions rr ON rr.results_id=r.id
                JOIN m8_reports p ON p.result_revision_id=rr.id AND p.audience='assessee'
                WHERE c.owner_user_id=%s AND c.organization_id=%s AND c.id<>%s
                  AND c.collection_closed_at IS NOT NULL AND c.collection_closed_at<%s
                ORDER BY c.collection_closed_at DESC,c.id DESC,
                  (p.id=(SELECT current.report_id FROM m8_published_reports current
                         WHERE current.cycle_db_id=c.id)) DESC NULLS LAST,
                  rr.revision_no DESC,p.revision_no DESC LIMIT 1""",
                (user.id, current_scope['organization_id'], current_scope['cycle_db_id'], current_scope['collection_closed_at'])).fetchone()
        if not previous_scope:
            raise HTTPException(404, detail='PREVIOUS_COMPLETED_REPORT_NOT_FOUND')
        valid_pair = (
            int(previous_scope['owner_user_id']) == int(user.id)
            and previous_scope['organization_id'] == current_scope['organization_id']
            and str(previous_scope['cycle_id']) != str(current_scope['cycle_id'])
            and previous_scope['collection_closed_at'] is not None
            and previous_scope['collection_closed_at'] < current_scope['collection_closed_at']
            and m8_results.owner_can_read_cycle(connection, str(previous_scope['cycle_id']), user.id)
        )
        if not valid_pair:
            raise HTTPException(403, detail='Предыдущий Report недоступен или не относится к допустимой паре.')
        try:
            current = m8_results.read_report(connection, report_id)
            previous = m8_results.read_report(connection, previous_scope['id'])
            return m8_report_comparison.compare_reports(current, previous)
        except ValueError as exc:
            raise HTTPException(409, detail=str(exc)) from exc


@router.get('/assessment/m8/reports/{report_id}/comparison.pdf')
def download_owned_m8_report_comparison(report_id: UUID, request: Request, previous_report_id: UUID | None = None):
    comparison = compare_owned_saved_m8_report(report_id, request, previous_report_id)
    try:
        pdf = m8_report_comparison.render_comparison_pdf(comparison)
    except TypstRenderError as exc:
        raise HTTPException(503, detail='PDF временно недоступен. Повторите скачивание.') from exc
    return Response(content=pdf, media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="4k-report-comparison-{report_id}.pdf"'
    })


def _render_saved_report_pdf(report: dict) -> bytes:
    try:
        return m8_results.render_pdf(report)
    except TypstRenderError as exc:
        raise HTTPException(503, detail='PDF временно недоступен. Повторите скачивание.') from exc


@router.get('/assessment/m8/reports/{report_id}/pdf')
def download_owned_m8_report(report_id: UUID, request: Request):
    report = _owned_saved_report(request, report_id, include_correction=True)
    pdf = _render_saved_report_pdf(report)
    return Response(content=pdf, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="4k-report-{report_id}.pdf"'})


def _customer_saved_report(request: Request, report_id: UUID, *, channel: str = 'api', project: bool = True):
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail='Требуется авторизация')
    with get_connection() as connection:
        if not m8_report_access.customer_can_read_report(connection, report_id=str(report_id), user_id=int(user.id)):
            raise HTTPException(403, detail='Готовый Report недоступен текущему пользователю.')
        try:
            saved = m8_results.read_report(connection, str(report_id))
            notice = m8_report_corrections.public_notice(connection, saved)
            report = ({**m8_report_access.customer_projection(saved),
                       "correction": notice} if project else {**saved, "correction": notice})
            m8_report_access.record_access(connection, report_id=str(report_id), user_id=int(user.id), channel=channel)
            connection.commit()
            return report
        except ValueError as exc:
            raise HTTPException(409, detail='Сохранённый Report временно недоступен.') from exc


@router.get('/admin/m8-access/cycles/{cycle_id}/reports/latest')
def current_customer_m8_report(cycle_id: UUID, request: Request):
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail='Требуется авторизация')
    with get_connection() as connection:
        cycle = connection.execute('SELECT id FROM m5_cycles WHERE cycle_id=%s', (cycle_id,)).fetchone()
        if not cycle:
            raise HTTPException(404, detail='M8_REPORT_NOT_FOUND')
        report_id = m8_report_corrections.current_report_id(connection, cycle['id'])
        if not report_id or not m8_report_access.customer_can_read_report(
            connection, report_id=report_id, user_id=int(user.id)):
            raise HTTPException(403, detail='Готовый Report недоступен текущему пользователю.')
        return {'id': report_id}


@router.get('/admin/m8-access/reports')
def list_customer_m8_reports(request: Request, organization_id: int | None = None,
                             query: str = '', program: str = '', program_definition_id: int | None = None,
                             status: str = '',
                             page: int = 1, page_size: int = 12):
    user = web_session_service.get_user_by_token(request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(401, detail='Требуется авторизация')
    if (page < 1 or not 1 <= page_size <= 50 or len(query) > 200 or len(program) > 200
            or (program_definition_id is not None and program_definition_id < 1)):
        raise HTTPException(422, detail='Некорректные параметры списка Report.')
    with get_connection() as connection:
        try:
            return m8_report_access.page_customer_reports(connection, user_id=int(user.id),
                organization_id=organization_id, query=query, program=program,
                program_definition_id=program_definition_id, status=status,
                page=page, page_size=page_size)
        except PermissionError as exc:
            raise HTTPException(403, detail='Организация недоступна.') from exc
        except ValueError as exc:
            raise HTTPException(422, detail='Некорректный статус Report.') from exc


@router.get('/admin/m8-access/reports/{report_id}')
def read_customer_m8_report(report_id: UUID, request: Request):
    return _customer_saved_report(request, report_id)


@router.get('/admin/m8-access/reports/{report_id}/pdf')
def download_customer_m8_report(report_id: UUID, request: Request):
    report = _customer_saved_report(request, report_id, channel='pdf', project=False)
    return Response(content=_render_saved_report_pdf(report), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="4k-report-{report_id}.pdf"'})


# PM-04 M7: restricted QA path for executable Cycle plan and next AS.
@router.post('/admin/m7-plans', status_code=201)
def create_m7_plan(payload: CreateCyclePlanRequest, request: Request):
    user=_m5_superadmin(request)
    try:
        with get_connection() as connection:
            result=m7_cycle_planner.create_plan(connection,personalized_profile_id=payload.personalized_profile_id,
                selected_skills=payload.selected_skills,created_by=int(user.id),key=payload.idempotency_key,
                time_budget_seconds=payload.time_budget_seconds,calendar_window_seconds=payload.calendar_window_seconds)
            connection.commit();return result
    except (ValueError,KeyError,OSError) as exc:
        raise HTTPException(409,detail=str(exc)) from exc


@router.get('/admin/m7-plans/{cycle_id}')
def get_m7_plan(cycle_id: UUID, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:return m7_cycle_planner.read_plan(connection,str(cycle_id))
    except ValueError as exc:raise HTTPException(404,detail=str(exc)) from exc


@router.post('/admin/m7-plans/{cycle_id}/next', status_code=202)
def choose_m7_next(cycle_id: UUID, payload: NextSituationRequest, request: Request):
    user=_m5_superadmin(request);policy=json.loads((M5_PACKAGE_DIR/'admission-policy.json').read_text())
    try:
        with get_connection() as connection:
            result=m7_cycle_planner.choose_next(connection,cycle_id=str(cycle_id),
                expected_plan_revision_id=payload.expected_plan_revision_id,key=payload.idempotency_key,
                created_by=int(user.id),policy=policy)
            connection.commit();return result
    except (ValueError,KeyError,OSError) as exc:raise HTTPException(409,detail=str(exc)) from exc


@router.post('/admin/m7-decisions/{decision_id}/present')
def present_m7_decision(decision_id: UUID, payload: PresentSituationRequest, request: Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result=m7_cycle_planner.present(connection,decision_id=str(decision_id),expected_revision=payload.expected_decision_revision)
            connection.commit();return result
    except ValueError as exc:raise HTTPException(409,detail=str(exc)) from exc


@router.post('/admin/m7-clarifications',status_code=201)
def create_m7_clarification(payload:CreateClarificationRequest,request:Request):
    user=_m5_superadmin(request)
    try:
        return m7_clarification.decide_detached(c54_revision_id=payload.c54_revision_id,
            key=payload.idempotency_key,created_by=int(user.id),connection_factory=get_connection)
    except (ValueError,KeyError,OSError) as exc:raise HTTPException(409,detail=str(exc)) from exc


@router.post('/admin/m7-clarifications/{decision_id}/present')
def present_m7_clarification(decision_id:UUID,payload:PresentClarificationRequest,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result=m7_clarification.present(connection,decision_id=str(decision_id),expected_c54_revision_id=payload.expected_c54_revision_id)
            connection.commit();return result
    except ValueError as exc:raise HTTPException(409,detail=str(exc)) from exc


@router.get('/admin/m7-clarifications/{decision_id}')
def read_m7_clarification(decision_id:UUID,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:return m7_clarification.read(connection,str(decision_id))
    except ValueError as exc:raise HTTPException(404,detail=str(exc)) from exc


@router.post('/admin/m7-clarifications/{decision_id}/answers')
def answer_m7_clarification(decision_id:UUID,payload:ClarificationAnswerRequest,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result=m7_clarification.answer(connection,decision_id=str(decision_id),request_id=payload.request_id,
                turn_id=payload.turn_id,content=payload.content);connection.commit();return result
    except ValueError as exc:raise HTTPException(409,detail=str(exc)) from exc


@router.post('/admin/m7-clarifications/{decision_id}/outcomes')
def record_m7_clarification_outcome(decision_id:UUID,payload:ClarificationOutcomeRequest,request:Request):
    _m5_superadmin(request)
    try:
        with get_connection() as connection:
            result=m7_clarification.record_outcome(connection,decision_id=str(decision_id),request_id=payload.request_id,outcome=payload.outcome)
            connection.commit();return result
    except ValueError as exc:raise HTTPException(409,detail=str(exc)) from exc
