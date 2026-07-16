from __future__ import annotations

import csv
import io
import json
import logging
import re
from urllib.parse import quote
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response as FastAPIResponse
from fastapi.responses import Response

from Api.admin_report_dialogue_pdf_service import admin_report_dialogue_pdf_service
from Api.admin_report_expert_export_service import admin_report_expert_export_service
from Api.admin_reports_pdf_service import admin_reports_pdf_service
from Api.app_version import get_app_version
from Api.auth_service import AuthAccessDeniedError, AuthRateLimitError, auth_service, normalize_email
from Api.config import settings
from Api.assessment_service import assessment_service
from Api.agent import interviewer_agent
from Api.database import get_connection, get_level_percent_map, recompute_case_quality_checks
from Api.database import get_case_methodology_versions
from Api.pdf_report_service import pdf_report_service
from Api.progress_service import operation_progress_service
from Api.mbti_refinement_service import mbti_refinement_service
from Api.org_access import (
    AdminScope,
    admin_scope_sql,
    assign_user_organization_from_email,
    ensure_configured_organizations,
    get_admin_scope,
    normalize_org_code,
)
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
from Api.schemas import (
    AdminDashboard,
    AdminDetailedReportItem,
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
    AdminReportDetailResponse,
    AdminDetailedReportsResponse,
    AdminExpertCommentUpdateRequest,
    AdminExpertGroupExportRequest,
    AdminInsightCard,
    AdminMetricCard,
    AdminOrganizationImportResult,
    AdminOrganizationAdminRequest,
    AdminOrganizationCreateRequest,
    AdminOrganizationDomainRequest,
    AdminOrganizationItem,
    AdminOrganizationMemberRequest,
    AdminOrganizationMembersImportRequest,
    AdminOrganizationsResponse,
    AdminOrganizationUpdateRequest,
    AdminRegressionTestRunResponse,
    AdminRegressionTestStatusResponse,
    AppVersionResponse,
    AuthEmailRequest,
    AuthEmailRequestResponse,
    AuthEmailVerifyRequest,
    AuthPasswordLoginRequest,
    AuthPasswordRegisterRequest,
    PromptLabCaseOption,
    PromptLabCaseRunRequest,
    PromptLabCaseRunResponse,
    PromptLabDialoguePreviewRequest,
    PromptLabDialoguePreviewResponse,
    PromptLabDialogueTurnRequest,
    PromptLabDialogueTurnResponse,
    PromptLabSystemCasePreviewResponse,
    PromptLabCaseRunSummary,
    PromptLabDashboard,
    PromptLabPromptCreateRequest,
    PromptLabPromptVersion,
    PromptLabUserOption,
    AgentMessageRequest,
    AgentReply,
    AssessmentMessageRequest,
    AssessmentMessageResponse,
    AssessmentTimerControlRequest,
    MbtiRefinementMessageRequest,
    MbtiRefinementMessageResponse,
    MbtiRefinementStartResponse,
    MbtiRefinementStateResponse,
    AssessmentSessionLookupResponse,
    AssessmentCard,
    AssessmentReportInterpretationResponse,
    AssessmentReport,
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
    UserSessionBootstrapResponse,
    UserSessionRestoreResponse,
    UserResponse,
)


router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger("agent4k.admin")
SESSION_COOKIE_NAME = "agent4k_session_token"
ADMIN_ROLE_CODE = "admin"
ADMIN_ROLE_NAME = "Администратор"
ADMIN_FULL_NAME = "Администратор системы"
ADMIN_EMAIL = "admin@agent4k.local"
ADMIN_PERIODS = {
    "7d": {"days": 7, "bucket": "day", "label": "Последние 7 дней"},
    "14d": {"days": 14, "bucket": "day", "label": "Последние 14 дней"},
    "30d": {"days": 30, "bucket": "day", "label": "Последние 30 дней"},
    "90d": {"days": 90, "bucket": "month", "label": "Последние 3 месяца"},
    "180d": {"days": 180, "bucket": "month", "label": "Последние 6 месяцев"},
    "365d": {"days": 365, "bucket": "month", "label": "Последние 12 месяцев"},
}
MONTH_LABELS_RU = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "май",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}


@router.get("/version", response_model=AppVersionResponse)
def get_application_version() -> AppVersionResponse:
    return AppVersionResponse(version=get_app_version())
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
        "description": "При необходимости собираем MBTI-сигналы и уточняющие вопросы.",
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


def _build_dashboard(connection, user: UserResponse) -> UserDashboard:
    progress_row = connection.execute(
        """
        SELECT
            progress_percent,
            completed_cases,
            total_cases,
            assessment_status
        FROM user_assessment_progress
        WHERE user_id = %s
          AND assessment_code = 'competencies_4k'
        """,
        (user.id,),
    ).fetchone()

    reports_total_row = connection.execute(
        """
        SELECT COUNT(*)::int AS reports_total
        FROM user_sessions us
        WHERE us.user_id = %s
          AND us.assessment_code = 'competencies_4k'
        """,
        (user.id,),
    ).fetchone()

    report_rows = connection.execute(
        """
        WITH ranked_sessions AS (
            SELECT
                us.id,
                us.user_id,
                us.status,
                us.started_at,
                us.finished_at,
                us.expert_comment,
                ROW_NUMBER() OVER (
                    PARTITION BY us.user_id
                    ORDER BY COALESCE(us.finished_at, us.started_at) ASC NULLS LAST, us.id ASC
                )::int AS sequence_number
            FROM user_sessions us
            WHERE us.user_id = %s
              AND us.assessment_code = 'competencies_4k'
        )
        SELECT
            rs.id AS session_id,
            rs.status,
            rs.started_at,
            rs.finished_at,
            rs.expert_comment,
            rs.sequence_number,
            COALESCE(case_stats.total_cases, 0)::int AS total_cases,
            COALESCE(case_stats.completed_cases, 0)::int AS completed_cases,
            COALESCE(skill_stats.total_skills, 0)::int AS total_skills,
            COALESCE(skill_stats.assessed_skills, 0)::int AS assessed_skills,
            skill_stats.overall_score_percent
        FROM ranked_sessions rs
        LEFT JOIN (
            SELECT
                session_id,
                COUNT(*)::int AS total_cases,
                COUNT(*) FILTER (WHERE status IN ('answered', 'assessed'))::int AS completed_cases
            FROM session_cases
            GROUP BY session_id
        ) AS case_stats ON case_stats.session_id = rs.id
        LEFT JOIN (
            SELECT
                ssa.session_id,
                COUNT(*)::int AS assessed_skills,
                COUNT(DISTINCT ssa.skill_id)::int AS total_skills,
                ROUND(AVG(COALESCE(alw.percent_value, 0)))::int AS overall_score_percent
            FROM session_skill_assessments ssa
            LEFT JOIN assessment_level_weights alw ON alw.level_code = ssa.assessed_level_code
            GROUP BY ssa.session_id
        ) AS skill_stats ON skill_stats.session_id = rs.id
        ORDER BY COALESCE(rs.finished_at, rs.started_at) DESC NULLS LAST, rs.id DESC
        LIMIT 5
        """,
        (user.id,),
    ).fetchall()

    progress_percent = int(progress_row["progress_percent"]) if progress_row else 0
    completed_cases = int(progress_row["completed_cases"]) if progress_row else 0
    total_cases = int(progress_row["total_cases"]) if progress_row else 5
    assessment_status = progress_row["assessment_status"] if progress_row else "not_started"
    is_complete = assessment_status == "completed" and progress_percent >= 100

    reports = [
        AssessmentReport(
            title="4K Assessment",
            summary=(
                (
                    "Оценка завершена. "
                    f"Закрыто навыков: {int(row['assessed_skills'] or 0)} из {int(row['total_skills'] or 0)}. "
                    f"Пройдено кейсов: {int(row['completed_cases'] or 0)} из {int(row['total_cases'] or 0)}."
                )
                if row["status"] == "completed"
                else (
                    "Оценка в процессе. "
                    f"Закрыто навыков: {int(row['assessed_skills'] or 0)} из {int(row['total_skills'] or 0)}. "
                    f"Пройдено кейсов: {int(row['completed_cases'] or 0)} из {int(row['total_cases'] or 0)}."
                )
            ),
            badge=(
                f"{int(row['overall_score_percent'])}%"
                if row["status"] == "completed" and row["overall_score_percent"] is not None
                else (
                    f"{int(round((int(row['completed_cases'] or 0) / int(row['total_cases'] or 1)) * 100))}%"
                    if int(row["total_cases"] or 0) > 0
                    else "0%"
                )
            ),
            format_label="PDF",
            sequence_number=int(row["sequence_number"]) if row["sequence_number"] is not None else None,
            report_at=row["finished_at"] or row["started_at"],
            expert_comment=(str(row["expert_comment"]).strip() if row["status"] == "completed" and row["expert_comment"] else None),
        )
        for row in report_rows
    ]

    assessment_allowed = bool(user.role_id)
    available_assessments: list[AvailableAssessment] = []
    if assessment_allowed and not is_complete:
        available_assessments.append(
            AvailableAssessment(
                code="competencies_4k",
                title="Компетенции 4К",
                description="Комплексная оценка критического мышления, креативности, коммуникации и кооперации.",
                duration_minutes=45,
                status="Доступен",
            )
        )

    active_assessment = AssessmentCard(
        code="competencies_4k",
        title="Компетенции 4К",
        description=(
            "Комплексная оценка критического мышления, креативности, коммуникации и кооперации."
            if assessment_allowed
            else "Перед прохождением ассессмента нужно завершить настройку профиля."
        ),
        progress_percent=progress_percent if assessment_allowed else 0,
        completed_cases=completed_cases if assessment_allowed else 0,
        total_cases=total_cases if assessment_allowed else 0,
        status_label=(
            "Новый цикл оценки" if is_complete else "Продолжить ассессмент"
        ) if assessment_allowed else "Нужно заполнить профиль",
        button_label=("Пройти ассессмент снова" if is_complete else "Продолжить") if assessment_allowed else "Заполнить профиль",
    )

    greeting_name = user.full_name.split()[0] if user.full_name else "коллега"
    return UserDashboard(
        greeting_name=greeting_name,
        active_assessment=active_assessment,
        available_assessments=available_assessments,
        reports_total=int(reports_total_row["reports_total"]) if reports_total_row and reports_total_row["reports_total"] is not None else 0,
        reports=reports,
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


def _get_admin_scope_or_403(connection, user: UserResponse | None) -> AdminScope:
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    if str(user.email or "").strip().lower() == ADMIN_EMAIL.lower():
        return AdminScope(is_superadmin=True)
    scope = get_admin_scope(connection, user)
    connection.commit()
    if not scope.can_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return scope


def _require_superadmin(connection, user: UserResponse | None) -> AdminScope:
    scope = _get_admin_scope_or_403(connection, user)
    if not scope.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
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


def _build_admin_organizations(connection) -> AdminOrganizationsResponse:
    ensure_configured_organizations(connection)
    connection.commit()
    org_rows = connection.execute(
        """
        SELECT id, code, name, is_active, created_at, updated_at
        FROM organizations
        ORDER BY is_active DESC, name ASC, code ASC
        """
    ).fetchall()
    org_ids = [int(row["id"]) for row in org_rows]
    domains_by_org: dict[int, list[str]] = {org_id: [] for org_id in org_ids}
    admins_by_org: dict[int, list[dict]] = {org_id: [] for org_id in org_ids}
    members_by_org_list: dict[int, list[dict]] = {org_id: [] for org_id in org_ids}
    members_by_org: dict[int, int] = {org_id: 0 for org_id in org_ids}
    reports_by_org: dict[int, int] = {org_id: 0 for org_id in org_ids}
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
            """
            SELECT om.organization_id, u.id AS user_id, u.email, u.full_name
            FROM organization_memberships om
            JOIN users u ON u.id = om.user_id
            WHERE om.organization_id = ANY(%s)
              AND om.role = 'admin'
            ORDER BY LOWER(COALESCE(u.email, '')) ASC
            """,
            (org_ids,),
        ).fetchall()
        for row in admin_rows:
            email = str(row["email"] or "").strip()
            if not email:
                continue
            admins_by_org.setdefault(int(row["organization_id"]), []).append(
                {"user_id": int(row["user_id"]), "email": email, "full_name": row["full_name"]}
            )

        member_detail_rows = connection.execute(
            """
            SELECT
                om.organization_id,
                om.role,
                u.id AS user_id,
                u.email,
                u.full_name,
                u.job_description,
                c.user_id IS NOT NULL AS has_password,
                p.raw_position,
                p.raw_duties
            FROM organization_memberships om
            JOIN users u ON u.id = om.user_id
            LEFT JOIN auth_password_credentials c ON c.user_id = u.id OR LOWER(c.email) = LOWER(u.email)
            LEFT JOIN user_role_profiles p ON p.id = u.active_profile_id
            WHERE om.organization_id = ANY(%s)
            ORDER BY LOWER(COALESCE(u.email, '')) ASC
            LIMIT 500
            """,
            (org_ids,),
        ).fetchall()
        for row in member_detail_rows:
            email = str(row["email"] or "").strip()
            if not email:
                continue
            members_by_org_list.setdefault(int(row["organization_id"]), []).append(
                {
                    "user_id": int(row["user_id"]),
                    "email": email,
                    "full_name": row["full_name"],
                    "role": row["role"] or "member",
                    "has_password": bool(row["has_password"]),
                    "job_description": row["job_description"],
                    "raw_position": row["raw_position"],
                    "raw_duties": row["raw_duties"],
                }
            )

        member_rows = connection.execute(
            """
            SELECT organization_id, COUNT(*)::int AS member_count
            FROM organization_memberships
            WHERE organization_id = ANY(%s)
            GROUP BY organization_id
            """,
            (org_ids,),
        ).fetchall()
        for row in member_rows:
            members_by_org[int(row["organization_id"])] = int(row["member_count"] or 0)

        report_rows = connection.execute(
            """
            SELECT om.organization_id, COUNT(DISTINCT us.id)::int AS reports_count
            FROM organization_memberships om
            JOIN user_sessions us ON us.user_id = om.user_id
            WHERE om.organization_id = ANY(%s)
              AND us.assessment_code = 'competencies_4k'
            GROUP BY om.organization_id
            """,
            (org_ids,),
        ).fetchall()
        for row in report_rows:
            reports_by_org[int(row["organization_id"])] = int(row["reports_count"] or 0)

    return AdminOrganizationsResponse(
        title="Организации",
        subtitle="Управление доменами и администраторами организаций.",
        items=[
            AdminOrganizationItem(
                id=int(row["id"]),
                code=str(row["code"]),
                name=str(row["name"]),
                is_active=bool(row["is_active"]),
                domains=domains_by_org.get(int(row["id"]), []),
                admins=admins_by_org.get(int(row["id"]), []),
                members=members_by_org_list.get(int(row["id"]), []),
                members_count=members_by_org.get(int(row["id"]), 0),
                reports_count=reports_by_org.get(int(row["id"]), 0),
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
    if user_row is not None:
        user_id = int(user_row["id"])
    else:
        fallback_name = str(full_name or normalized_email.split("@", 1)[0]).replace(".", " ").replace("_", " ").strip()
        created_user = connection.execute(
            """
            INSERT INTO users (full_name, email, role_id, job_description, phone, company_industry)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (fallback_name[:255] or "Администратор организации", normalized_email, None, None, None, None),
        ).fetchone()
        user_id = int(created_user["id"])

    identity_row = connection.execute(
        """
        SELECT id
        FROM user_identities
        WHERE LOWER(email) = %s
        LIMIT 1
        """,
        (normalized_email,),
    ).fetchone()
    if identity_row is None:
        connection.execute(
            """
            INSERT INTO user_identities (user_id, provider, provider_subject, email, is_primary, is_verified, verified_at, updated_at)
            VALUES (%s, %s, %s, %s, TRUE, TRUE, NOW(), NOW())
            ON CONFLICT (provider, provider_subject) WHERE provider_subject IS NOT NULL DO UPDATE
            SET user_id = EXCLUDED.user_id,
                email = EXCLUDED.email,
                is_verified = TRUE,
                verified_at = NOW(),
                updated_at = NOW()
            """,
            (user_id, "email_magic_link", normalized_email, normalized_email),
        )
    else:
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
            (user_id, "email_magic_link", normalized_email, int(identity_row["id"])),
        )
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
        VALUES (%s, %s, %s, %s, TRUE, TRUE, NOW(), NOW())
        ON CONFLICT (provider, provider_subject) WHERE provider_subject IS NOT NULL DO UPDATE
        SET user_id = EXCLUDED.user_id,
            email = EXCLUDED.email,
            is_verified = TRUE,
            verified_at = NOW(),
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


def _attach_user_to_organization(
    connection,
    *,
    organization_id: int,
    email: str,
    full_name: str | None = None,
    role_description: str | None = None,
    job_instructions: str | None = None,
) -> int:
    org_row = connection.execute(
        "SELECT id FROM organizations WHERE id = %s AND is_active = TRUE LIMIT 1",
        (organization_id,),
    ).fetchone()
    if org_row is None:
        raise HTTPException(status_code=404, detail="Active organization not found")
    user_id = _ensure_org_member_user(
        connection,
        email=email,
        full_name=full_name,
        role_description=role_description,
    )
    connection.execute(
        """
        INSERT INTO organization_memberships (organization_id, user_id, role)
        VALUES (%s, %s, 'member')
        ON CONFLICT (organization_id, user_id) DO UPDATE
        SET updated_at = NOW()
        """,
        (organization_id, user_id),
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


def _build_activity_series(connection, scope: AdminScope, period_key: str) -> tuple[list[str], list[int], int, str]:
    period = ADMIN_PERIODS.get(period_key, ADMIN_PERIODS["30d"])
    bucket = period["bucket"]
    days = int(period["days"])
    period_label = str(period["label"])
    scope_sql, scope_params = admin_scope_sql(scope)

    if bucket == "day":
        rows = connection.execute(
            f"""
            WITH bounds AS (
                SELECT CURRENT_DATE - (%s::int - 1) * INTERVAL '1 day' AS start_day,
                       CURRENT_DATE AS end_day
            ),
            axis AS (
                SELECT generate_series(
                    (SELECT start_day FROM bounds),
                    (SELECT end_day FROM bounds),
                    INTERVAL '1 day'
                ) AS bucket_start
            ),
            stats AS (
                SELECT
                    DATE_TRUNC('day', finished_at) AS bucket_start,
                    COUNT(*)::int AS session_count
                FROM user_sessions
                JOIN users u ON u.id = user_sessions.user_id
                WHERE assessment_code = 'competencies_4k'
                  AND status = 'completed'
                  AND finished_at >= (SELECT start_day FROM bounds)
                  AND LOWER(COALESCE(u.email, '')) <> %s
                  {scope_sql}
                GROUP BY DATE_TRUNC('day', finished_at)
            )
            SELECT
                TO_CHAR(axis.bucket_start, 'DD.MM') AS bucket_label,
                COALESCE(stats.session_count, 0)::int AS session_count
            FROM axis
            LEFT JOIN stats ON stats.bucket_start = axis.bucket_start
            ORDER BY axis.bucket_start
            """,
            (days, ADMIN_EMAIL.lower(), *scope_params),
        ).fetchall()
    else:
        month_count = max(1, round(days / 30))
        rows = connection.execute(
            f"""
            WITH bounds AS (
                SELECT DATE_TRUNC('month', CURRENT_DATE) - (%s::int - 1) * INTERVAL '1 month' AS start_month,
                       DATE_TRUNC('month', CURRENT_DATE) AS end_month
            ),
            axis AS (
                SELECT generate_series(
                    (SELECT start_month FROM bounds),
                    (SELECT end_month FROM bounds),
                    INTERVAL '1 month'
                ) AS bucket_start
            ),
            stats AS (
                SELECT
                    DATE_TRUNC('month', finished_at) AS bucket_start,
                    COUNT(*)::int AS session_count
                FROM user_sessions
                JOIN users u ON u.id = user_sessions.user_id
                WHERE assessment_code = 'competencies_4k'
                  AND status = 'completed'
                  AND finished_at >= (SELECT start_month FROM bounds)
                  AND LOWER(COALESCE(u.email, '')) <> %s
                  {scope_sql}
                GROUP BY DATE_TRUNC('month', finished_at)
            )
            SELECT
                axis.bucket_start,
                TO_CHAR(axis.bucket_start, 'MM.YY') AS bucket_label,
                COALESCE(stats.session_count, 0)::int AS session_count
            FROM axis
            LEFT JOIN stats ON stats.bucket_start = axis.bucket_start
            ORDER BY axis.bucket_start
            """,
            (month_count, ADMIN_EMAIL.lower(), *scope_params),
        ).fetchall()
        rows = [
            {
                "bucket_label": MONTH_LABELS_RU.get(row["bucket_start"].month, str(row["bucket_label"])),
                "session_count": row["session_count"],
            }
            for row in rows
        ]

    labels = [str(row["bucket_label"]) for row in rows]
    points = [int(row["session_count"] or 0) for row in rows]
    axis_max = max(points) if points else 0
    if axis_max <= 0:
        axis_max = 1
    return labels, points, axis_max, period_label


def _build_admin_dashboard(connection, scope: AdminScope, period_key: str = "30d") -> AdminDashboard:
    scope_sql, scope_params = admin_scope_sql(scope)
    totals_row = connection.execute(
        f"""
        SELECT
            COUNT(*)::int AS total_users,
            COUNT(*) FILTER (WHERE role_id IS NOT NULL)::int AS profiled_users
        FROM users u
        WHERE LOWER(COALESCE(u.email, '')) <> %s
          {scope_sql}
        """,
        (ADMIN_EMAIL.lower(), *scope_params),
    ).fetchone()

    session_row = connection.execute(
        f"""
        SELECT
            COUNT(*)::int AS total_sessions,
            COUNT(*) FILTER (WHERE status = 'completed')::int AS completed_sessions,
            ROUND(AVG(completed_cases::numeric), 1)::numeric AS avg_completed_cases
        FROM (
            SELECT
                us.id,
                us.status,
                COUNT(sc.id) FILTER (WHERE sc.status IN ('answered', 'assessed'))::int AS completed_cases
            FROM user_sessions us
            JOIN users u ON u.id = us.user_id
            LEFT JOIN session_cases sc ON sc.session_id = us.id
            WHERE us.assessment_code = 'competencies_4k'
              AND LOWER(COALESCE(u.email, '')) <> %s
              {scope_sql}
            GROUP BY us.id, us.status
        ) AS session_stats
        """,
        (ADMIN_EMAIL.lower(), *scope_params),
    ).fetchone()

    score_row = connection.execute(
        f"""
        SELECT
            ROUND(AVG(score_percent)::numeric, 1)::numeric AS avg_score_percent
        FROM (
            SELECT
                us.id,
                AVG(alw.percent_value) AS score_percent
            FROM user_sessions us
            JOIN users u ON u.id = us.user_id
            JOIN session_skill_assessments ssa ON ssa.session_id = us.id
            JOIN assessment_level_weights alw ON alw.level_code = ssa.assessed_level_code
            WHERE us.assessment_code = 'competencies_4k'
              AND us.status = 'completed'
              AND ssa.assessed_level_code IS NOT NULL
              AND LOWER(COALESCE(u.email, '')) <> %s
              {scope_sql}
            GROUP BY us.id
        ) AS score_stats
        """,
        (ADMIN_EMAIL.lower(), *scope_params),
    ).fetchone()

    duration_row = connection.execute(
        f"""
        SELECT
            ROUND(
                AVG(
                    session_actual_minutes
                )::numeric,
                1
            )::numeric AS avg_actual_minutes
        FROM (
            SELECT
                us.id,
                SUM(COALESCE(sc.actual_duration_seconds, 0))::numeric / 60.0 AS session_actual_minutes
            FROM user_sessions us
            JOIN users u ON u.id = us.user_id
            JOIN session_cases sc ON sc.session_id = us.id
            WHERE us.assessment_code = 'competencies_4k'
              AND us.status = 'completed'
              AND LOWER(COALESCE(u.email, '')) <> %s
              {scope_sql}
            GROUP BY us.id
        ) AS duration_stats
        """,
        (ADMIN_EMAIL.lower(), *scope_params),
    ).fetchone()

    competency_rows = connection.execute(
        f"""
        SELECT
            ssa.competency_name,
            ROUND(AVG(alw.percent_value))::int AS avg_percent
        FROM session_skill_assessments ssa
        JOIN user_sessions us ON us.id = ssa.session_id
        JOIN users u ON u.id = us.user_id
        JOIN assessment_level_weights alw ON alw.level_code = ssa.assessed_level_code
        WHERE us.assessment_code = 'competencies_4k'
          AND us.status = 'completed'
          AND ssa.assessed_level_code IS NOT NULL
          AND LOWER(COALESCE(u.email, '')) <> %s
          {scope_sql}
        GROUP BY ssa.competency_name
        ORDER BY ssa.competency_name
        """,
        (ADMIN_EMAIL.lower(), *scope_params),
    ).fetchall()

    total_users = int(totals_row["total_users"] or 0)
    profiled_users = int(totals_row["profiled_users"] or 0)
    total_sessions = int(session_row["total_sessions"] or 0)
    completed_sessions = int(session_row["completed_sessions"] or 0)
    avg_score = float(score_row["avg_score_percent"] or 0)
    avg_actual_duration = float(duration_row["avg_actual_minutes"] or 0)
    avg_completed_cases = float(session_row["avg_completed_cases"] or 0)
    completion_percent = round((completed_sessions / total_sessions) * 100) if total_sessions else 0
    activity_labels, activity_points, activity_axis_max, activity_period_label = _build_activity_series(connection, scope, period_key)

    competency_average = [
        {
            "name": row["competency_name"] or "Без категории",
            "value": int(row["avg_percent"] or 0),
        }
        for row in competency_rows
    ] or [
        {"name": "Коммуникация", "value": 0},
        {"name": "Командная работа", "value": 0},
        {"name": "Креативность", "value": 0},
        {"name": "Критическое мышление", "value": 0},
    ]

    mbti_distribution = []

    weakest = min(competency_average, key=lambda item: item["value"])
    strongest = max(competency_average, key=lambda item: item["value"])

    return AdminDashboard(
        title="Сводный отчет",
        subtitle="Комплексный анализ компетенций и продуктовых метрик по сотрудникам платформы.",
        is_superadmin=scope.is_superadmin,
        metrics=[
            AdminMetricCard(label="Пользователи", value=f"{total_users}", delta=f"+{profiled_users} с профилем"),
            AdminMetricCard(label="Процент завершения", value=f"{completion_percent}%", delta=f"{completed_sessions} из {total_sessions} сессий"),
            AdminMetricCard(label="Средний индекс", value=f"{avg_score:.1f}/100", delta="по завершенным ассессментам"),
            AdminMetricCard(label="Среднее время прохождения", value=f"{avg_actual_duration:.0f} мин", delta=f"{avg_completed_cases:.1f} кейса в среднем"),
        ],
        competency_average=competency_average,
        mbti_distribution=mbti_distribution,
        insights=[
            AdminInsightCard(title="Наиболее слабый контур", description=f"Минимальный средний показатель сейчас у направления «{weakest['name']}»."),
            AdminInsightCard(title="Лучшая группа", description=f"Самый высокий средний результат показывает направление «{strongest['name']}»."),
            AdminInsightCard(title="Фокус развития", description="Админ-панель позволяет отслеживать завершение оценок и динамику загрузки платформы."),
        ],
        activity_points=activity_points,
        activity_labels=activity_labels,
        activity_axis_max=activity_axis_max,
        activity_period_key=period_key if period_key in ADMIN_PERIODS else "30d",
        activity_period_label=activity_period_label,
    )



def _extract_admin_mbti_payload(summary_payload) -> tuple[str | None, str | None, list[dict[str, str | int]]]:
    default_axes = [
        {"left": "Экстраверсия", "right": "Интроверсия", "value": 0},
        {"left": "Интуиция", "right": "Сенсорика", "value": 0},
        {"left": "Мышление", "right": "Чувство", "value": 0},
        {"left": "Суждение", "right": "Восприятие", "value": 0},
    ]
    if isinstance(summary_payload, str):
        try:
            summary_payload = json.loads(summary_payload)
        except Exception:
            summary_payload = None
    if not isinstance(summary_payload, dict) or not summary_payload:
        return None, None, default_axes

    total = summary_payload.get("общий_итог") if isinstance(summary_payload.get("общий_итог"), dict) else summary_payload
    summary_text = str(
        total.get("краткий_вывод")
        or total.get("summary")
        or total.get("вывод")
        or ""
    ).strip() or None

    mbti_type = str(
        total.get("mbti_type")
        or total.get("тип")
        or total.get("темперамент")
        or total.get("вероятный_тип")
        or ""
    ).strip() or None
    if not mbti_type and summary_text:
        type_match = re.search(r"\b([IE][NS][FT][JP])\b", summary_text)
        temperament_match = re.search(r"\b(SJ|SP|NT|NF)\b", summary_text)
        named_match = re.search(r"(Guardian|Artisan|Rational|Idealist)[-/ ]?([A-Z]{2})?", summary_text, flags=re.IGNORECASE)
        if type_match:
            mbti_type = type_match.group(1)
        elif named_match:
            label = named_match.group(1).capitalize()
            suffix = (named_match.group(2) or "").upper()
            mbti_type = f"{label}/{suffix}" if suffix else label
        elif temperament_match:
            mbti_type = temperament_match.group(1)

    axes_payload = total.get("оси") or total.get("axes") or summary_payload.get("mbti_axes")
    axes: list[dict[str, str | int]] = []
    if isinstance(axes_payload, list):
        for item in axes_payload:
            if not isinstance(item, dict):
                continue
            left = str(item.get("left") or item.get("левая_шкала") or item.get("left_label") or "").strip()
            right = str(item.get("right") or item.get("правая_шкала") or item.get("right_label") or "").strip()
            try:
                value = int(item.get("value") or item.get("значение") or 0)
            except Exception:
                value = 0
            if left and right:
                axes.append({"left": left, "right": right, "value": max(0, min(100, value))})
    return mbti_type, summary_text, axes or default_axes

def _build_admin_reports(connection, scope: AdminScope) -> AdminDetailedReportsResponse:
    scope_sql, scope_params = admin_scope_sql(scope)
    rows = connection.execute(
        f"""
        SELECT
            us.id AS session_id,
            us.user_id,
            u.full_name,
            u.phone,
            COALESCE(NULLIF(TRIM(u.company_industry), ''), 'Не указана') AS group_name,
            COALESCE(NULLIF(TRIM(u.job_description), ''), 'Не указана') AS role_name,
            us.status,
            us.expert_comment,
            score_stats.overall_score_percent,
            us.mbti_summary_json,
            us.started_at,
            us.finished_at
        FROM user_sessions us
        JOIN users u ON u.id = us.user_id
        LEFT JOIN (
            SELECT
                session_id,
                ROUND(AVG(COALESCE(alw.percent_value, 0)))::int AS overall_score_percent
                FROM session_skill_assessments ssa
                LEFT JOIN assessment_level_weights alw ON alw.level_code = ssa.assessed_level_code
                GROUP BY ssa.session_id
        ) AS score_stats ON score_stats.session_id = us.id
        WHERE us.assessment_code = 'competencies_4k'
          AND LOWER(COALESCE(u.email, '')) <> %s
          {scope_sql}
        ORDER BY COALESCE(us.finished_at, us.started_at) DESC NULLS LAST, us.id DESC
        """,
        (ADMIN_EMAIL.lower(), *scope_params),
    ).fetchall()

    items = []
    for row in rows:
        mbti_type, _, _ = _extract_admin_mbti_payload(row.get("mbti_summary_json"))
        items.append(
            AdminDetailedReportItem(
                session_id=int(row["session_id"]),
                user_id=int(row["user_id"]),
                full_name=row["full_name"] or "Без имени",
                phone=row["phone"],
                group_name=row["group_name"],
                role_name=row["role_name"],
                status="Завершено" if row["status"] == "completed" else "В процессе" if row["status"] == "active" else "Черновик",
                score_percent=int(row["overall_score_percent"]) if row["overall_score_percent"] is not None else None,
                mbti_type=mbti_type,
                started_at=row["started_at"],
                finished_at=row["finished_at"],
            )
        )

    score_values = [item.score_percent for item in items if item.score_percent is not None]
    return AdminDetailedReportsResponse(
        title="Отдельные отчеты",
        subtitle="Управление и анализ индивидуальных результатов тестирования персонала.",
        total_items=len(items),
        summary_score_percent=round(sum(score_values) / len(score_values), 1) if score_values else None,
        items=items,
    )


def _build_admin_report_detail(connection, session_id: int, scope: AdminScope) -> AdminReportDetailResponse:
    scope_sql, scope_params = admin_scope_sql(scope)
    session_row = connection.execute(
        f"""
        SELECT
            us.id AS session_id,
            us.user_id,
            us.status,
            us.started_at,
            us.finished_at,
            us.expert_comment,
            us.expert_name,
            us.expert_contacts,
            us.expert_assessed_at,
            us.mbti_summary_json,
            u.full_name,
            u.phone,
            u.telegram,
            COALESCE(NULLIF(TRIM(u.company_industry), ''), 'Не указана') AS group_name,
            COALESCE(NULLIF(TRIM(u.job_description), ''), 'Не указана') AS role_name,
            p.raw_position,
            p.raw_duties,
            p.normalized_duties,
            p.user_domain,
            p.user_processes,
            p.user_tasks,
            p.user_stakeholders,
            p.user_constraints
        FROM user_sessions us
        JOIN users u ON u.id = us.user_id
        LEFT JOIN LATERAL (
            SELECT
                urp.raw_position,
                urp.raw_duties,
                urp.normalized_duties,
                urp.user_domain,
                urp.user_processes,
                urp.user_tasks,
                urp.user_stakeholders,
                urp.user_constraints
            FROM user_role_profiles urp
            WHERE urp.user_id = u.id
            ORDER BY
                CASE WHEN urp.id = u.active_profile_id THEN 0 ELSE 1 END,
                urp.profile_version DESC NULLS LAST,
                urp.id DESC
            LIMIT 1
        ) p ON TRUE
        WHERE us.id = %s
          AND us.assessment_code = 'competencies_4k'
          AND LOWER(COALESCE(u.email, '')) <> %s
          {scope_sql}
        LIMIT 1
        """,
        (session_id, ADMIN_EMAIL.lower(), *scope_params),
    ).fetchone()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Assessment report not found")

    skill_rows = connection.execute(
        """
        SELECT
            competency_name,
            skill_name,
            assessed_level_code,
            assessed_level_name,
            rationale,
            evidence_excerpt,
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
        WHERE session_id = %s
        ORDER BY competency_name ASC, skill_name ASC
        """,
        (session_id,),
    ).fetchall()

    grouped: dict[str, list[dict]] = {}
    level_map = get_level_percent_map(connection)
    for row in skill_rows:
        competency = row["competency_name"] or "Без категории"
        grouped.setdefault(competency, []).append(dict(row))

    competency_average: list[dict[str, str | int]] = []
    for competency_name, skills in grouped.items():
        avg_percent = round(sum(level_map.get(skill["assessed_level_code"], 0) for skill in skills) / len(skills))
        evidence_hits = sum(1 for skill in skills if _parse_json_array_field(skill["found_evidence"]))
        block_values = [float(skill["block_coverage_percent"]) for skill in skills if skill["block_coverage_percent"] is not None]
        artifact_values = [float(skill["artifact_compliance_percent"]) for skill in skills if skill["artifact_compliance_percent"] is not None]
        red_flag_total = sum(len(_parse_json_array_field(skill["red_flags"])) for skill in skills)
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

    if not competency_average:
        competency_average = [
            {"name": "Коммуникация", "value": 0},
            {"name": "Командная работа", "value": 0},
            {"name": "Креативность", "value": 0},
            {"name": "Критическое мышление", "value": 0},
        ]

    score_values = [int(item["value"]) for item in competency_average if isinstance(item["value"], int)]
    score_percent = round(sum(score_values) / len(score_values)) if score_values else None
    interpretation = _build_report_interpretation_payload(skill_rows, competency_average)

    strongest_item, has_confident_strongest = _select_strongest_competency(competency_average)
    strengths: list[str] = []
    if strongest_item and has_confident_strongest:
        strengths.append(
            f"Наиболее устойчиво проявлена компетенция «{strongest_item['name']}»: средний показатель составил {strongest_item['value']}%."
        )
    if interpretation.get("response_pattern"):
        strengths.append(str(interpretation["response_pattern"]))
    if not strengths:
        strengths = ["Выраженная сильная сторона пока не выделена: для этого нужны более устойчивые сигналы по сессии."]
    growth_areas = interpretation["growth_areas"]

    quotes: list[str] = []
    seen_quotes: set[str] = set()
    for row in skill_rows:
        excerpt = (row["evidence_excerpt"] or "").strip()
        candidate = ""
        if excerpt:
            candidate = excerpt
        elif row["rationale"]:
            candidate = str(row["rationale"]).strip()
        normalized_candidate = " ".join(candidate.split()).lower()
        if (
            candidate
            and normalized_candidate
            and normalized_candidate not in seen_quotes
            and _is_meaningful_quote_candidate(candidate)
        ):
            seen_quotes.add(normalized_candidate)
            quotes.append(candidate)
        if len(quotes) >= 3:
            break

    case_rows = connection.execute(
        """
        SELECT
            sc.id AS session_case_id,
            sc.status,
            sc.started_at,
            sc.completed_at AS finished_at,
            sc.case_registry_id,
            cr.case_id_code,
            COALESCE(cr.title, 'Кейс без названия') AS case_title,
            ct.intro_context,
            ct.task_for_user,
            ct.constraints_text,
            sp.user_prompt,
            sp.final_prompt_text
        FROM session_cases sc
        LEFT JOIN cases_registry cr ON cr.id = sc.case_registry_id
        LEFT JOIN case_texts ct ON ct.cases_registry_id = cr.id
        LEFT JOIN LATERAL (
            SELECT user_prompt, final_prompt_text
            FROM session_prompts
            WHERE session_case_id = sc.id
              AND prompt_type = 'case_dialog'
            ORDER BY id DESC
            LIMIT 1
        ) sp ON TRUE
        WHERE sc.session_id = %s
        ORDER BY sc.id ASC
        """,
        (session_id,),
    ).fetchall()

    dialogue_rows = connection.execute(
        """
        SELECT
            session_case_id,
            role,
            message_text
        FROM session_case_messages
        WHERE session_id = %s
        ORDER BY session_case_id ASC, id ASC
        """,
        (session_id,),
    ).fetchall()

    analysis_rows = connection.execute(
        """
        SELECT
            scsa.session_case_id,
            s.skill_name,
            scsa.competency_name,
            ssa.assessed_level_code,
            ssa.assessed_level_name,
            scsa.artifact_compliance_percent,
            scsa.block_coverage_percent,
            scsa.red_flags,
            scsa.found_evidence,
            scsa.evidence_excerpt
        FROM session_case_skill_analysis scsa
        JOIN skills s ON s.id = scsa.skill_id
        LEFT JOIN session_skill_assessments ssa
          ON ssa.session_id = scsa.session_id
         AND ssa.user_id = scsa.user_id
         AND ssa.skill_id = scsa.skill_id
        WHERE scsa.session_id = %s
        ORDER BY scsa.session_case_id ASC, scsa.competency_name ASC, s.skill_name ASC
        """,
        (session_id,),
    ).fetchall()

    dialogue_by_case: dict[int, list[dict]] = {}
    for row in dialogue_rows:
        dialogue_by_case.setdefault(int(row["session_case_id"]), []).append(
            {
                "role": row["role"] or "assistant",
                "message_text": row["message_text"] or "",
            }
        )

    analysis_by_case: dict[int, list[dict]] = {}
    for row in analysis_rows:
        analysis_by_case.setdefault(int(row["session_case_id"]), []).append(
            {
                "skill_name": row["skill_name"] or "Навык",
                "competency_name": row["competency_name"] or "Без категории",
                "assessed_level_code": row["assessed_level_code"],
                "assessed_level_name": row["assessed_level_name"],
                "artifact_compliance_percent": row["artifact_compliance_percent"],
                "block_coverage_percent": row["block_coverage_percent"],
                "red_flags": _parse_json_array_field(row["red_flags"]),
                "found_evidence": _normalize_found_evidence_items(row["found_evidence"]),
                "evidence_excerpt": row["evidence_excerpt"],
            }
        )

    def _extract_prompt_parts(user_prompt: str | None) -> tuple[str | None, str | None]:
        prompt_text = str(user_prompt or "").strip()
        if not prompt_text:
            return None, None
        context_match = re.search(
            r"Personalized case context:\s*(.*?)(?:\nPersonalized task:|\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        task_match = re.search(r"Personalized task:\s*(.*)\Z", prompt_text, flags=re.DOTALL)
        context_text = context_match.group(1).strip() if context_match else None
        task_text = task_match.group(1).strip() if task_match else None
        if context_text or task_text:
            return context_text or None, task_text or None
        structured_match = re.search(
            r"^(.*?)(?:\n\s*\n)?Что нужно сделать:\s*(.*)\Z",
            prompt_text,
            flags=re.DOTALL,
        )
        if structured_match:
            context_text = structured_match.group(1).strip()
            task_text = structured_match.group(2).strip()
            return context_text or None, task_text or None
        if "\n\n" in prompt_text:
            context_text, task_text = prompt_text.rsplit("\n\n", 1)
            return context_text.strip() or None, task_text.strip() or None
        return prompt_text, None

    case_items: list[dict] = []
    for index, row in enumerate(case_rows, start=1):
        personalized_context, personalized_task = _extract_prompt_parts(row["user_prompt"])
        fallback_context = str(row["intro_context"] or "").strip() or None
        fallback_task = str(row["task_for_user"] or "").strip() or None
        constraints_text = str(row["constraints_text"] or "").strip() or None
        final_context = personalized_context or fallback_context
        if constraints_text and final_context:
            final_context = final_context + "\n\nОграничения:\n" + constraints_text
        elif constraints_text and not final_context:
            final_context = "Ограничения:\n" + constraints_text
        case_items.append(
            {
                "session_case_id": int(row["session_case_id"]),
                "case_number": index,
                "case_title": row["case_title"] or "Кейс без названия",
                "case_id_code": row["case_id_code"],
                "status": row["status"] or "unknown",
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "personalized_context": final_context,
                "personalized_task": personalized_task or fallback_task,
                "prompt_text": row["final_prompt_text"],
                "dialogue": dialogue_by_case.get(int(row["session_case_id"]), []),
                "skill_results": analysis_by_case.get(int(row["session_case_id"]), []),
            }
        )

    mbti_type, mbti_summary, mbti_axes = _extract_admin_mbti_payload(session_row.get("mbti_summary_json"))

    return AdminReportDetailResponse(
        session_id=int(session_row["session_id"]),
        user_id=int(session_row["user_id"]),
        full_name=session_row["full_name"] or "Без имени",
        phone=(str(session_row["phone"]).strip() if session_row["phone"] else None),
        telegram=(str(session_row["telegram"]).strip() if session_row["telegram"] else None),
        role_name=session_row["role_name"],
        group_name=session_row["group_name"],
        status="Завершено" if session_row["status"] == "completed" else "В процессе" if session_row["status"] == "active" else "Черновик",
        score_percent=score_percent,
        report_date=session_row["finished_at"] or session_row["started_at"],
        competency_average=competency_average,
        mbti_type=mbti_type,
        mbti_summary=mbti_summary,
        mbti_axes=mbti_axes,
        insight_title=interpretation["insight_title"],
        insight_text=interpretation["insight_text"],
        basis_items=interpretation["basis_items"],
        response_pattern=interpretation["response_pattern"],
        expert_comment=(str(session_row["expert_comment"]).strip() if session_row["status"] == "completed" and session_row["expert_comment"] else None),
        expert_name=(str(session_row["expert_name"]).strip() if session_row["status"] == "completed" and session_row["expert_name"] else None),
        expert_contacts=(str(session_row["expert_contacts"]).strip() if session_row["status"] == "completed" and session_row["expert_contacts"] else None),
        expert_assessed_at=(session_row["expert_assessed_at"] if session_row["status"] == "completed" else None),
        can_edit_expert_comment=session_row["status"] == "completed",
        strengths=strengths,
        growth_areas=growth_areas,
        quotes=quotes,
        profile_summary={
            "position": (session_row["raw_position"] or session_row["role_name"] or "").strip() or None,
            "duties": (session_row["normalized_duties"] or session_row["raw_duties"] or "").strip() or None,
            "domain": (session_row["user_domain"] or session_row["group_name"] or "").strip() or None,
            "processes": _parse_json_array_field(session_row["user_processes"]),
            "tasks": _parse_json_array_field(session_row["user_tasks"]),
            "stakeholders": _parse_json_array_field(session_row["user_stakeholders"]),
            "constraints": _parse_json_array_field(session_row["user_constraints"]),
        },
        case_items=case_items,
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
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


def _clear_user_session_cookie(response: FastAPIResponse) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _build_authenticated_user_response(
    *,
    connection,
    user: UserResponse,
    response: FastAPIResponse,
    login_identifier: str,
    is_new_user: bool,
) -> CheckOrCreateUserResponse:
    compact_user = _compact_user_response(user)
    _set_user_session_cookie(response, web_session_service.create_session(user.id))
    assign_user_organization_from_email(connection, user_id=user.id, email=user.email)
    admin_scope = _get_admin_scope_or_403(connection, user) if _is_admin_user(connection, user) else AdminScope()

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
        )

    agent = interviewer_agent.start(
        login_identifier=login_identifier,
        user=user,
        bootstrap_user_id=user.id if is_new_user else None,
    )
    agent = agent.model_copy(update={"user": compact_user})
    return CheckOrCreateUserResponse(
        exists=not is_new_user,
        message="Пользователь авторизован по email." if not is_new_user else "Email подтвержден. Продолжаем создание профиля.",
        user=compact_user,
        requires_user_data=is_new_user,
        agent=agent,
        dashboard=None if is_new_user else _build_dashboard(connection, user),
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
            auth_mode = auth_service.get_password_auth_mode(email=email)
        except AuthAccessDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        is_registration = auth_mode == "password_registration"
        return AuthEmailRequestResponse(
            message="Задайте пароль для первичного входа." if is_registration else "Введите пароль для входа.",
            email=email,
            expires_in_seconds=0,
            dev_mode=False,
            delivery_method=auth_mode,
            auth_mode=auth_mode,
            dev_magic_token=None,
        )
    try:
        result = auth_service.create_magic_link_request(
            email=payload.email,
            client_ip=client_ip,
            user_agent=user_agent,
        )
    except AuthAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AuthRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
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
    )


def _build_password_auth_response(
    *,
    verification,
    response: FastAPIResponse,
) -> CheckOrCreateUserResponse:
    with get_connection() as connection:
        user = verification.user
        if (
            not verification.is_new_user
            and (
                not user.role_id
                or not (user.company_industry and user.company_industry.strip())
                or not user.active_profile_id
                or not (user.normalized_duties and user.normalized_duties.strip())
            )
        ):
            repaired_user = interviewer_agent.backfill_user_profile(user.id)
            if repaired_user is not None:
                user = _strip_avatar(repaired_user)
        return _build_authenticated_user_response(
            connection=connection,
            user=user,
            response=response,
            login_identifier=verification.email,
            is_new_user=verification.is_new_user,
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
        )
    except AuthAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _build_password_auth_response(verification=verification, response=response)


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
        if (
            not verification.is_new_user
            and (
                not user.role_id
                or not (user.company_industry and user.company_industry.strip())
                or not user.active_profile_id
                or not (user.normalized_duties and user.normalized_duties.strip())
            )
        ):
            repaired_user = interviewer_agent.backfill_user_profile(user.id)
            if repaired_user is not None:
                user = _strip_avatar(repaired_user)
        return _build_authenticated_user_response(
            connection=connection,
            user=user,
            response=response,
            login_identifier=verification.email,
            is_new_user=verification.is_new_user,
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
def restore_user_session(request: Request) -> UserSessionRestoreResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        return UserSessionRestoreResponse(authenticated=False)
    full_user = _strip_avatar(user)
    compact_user = _compact_user_response(full_user)

    with get_connection() as connection:
        admin_scope = _get_admin_scope_or_403(connection, full_user) if _is_admin_user(connection, full_user) else AdminScope()
        if admin_scope.can_admin:
            return UserSessionRestoreResponse(
                authenticated=True,
                user=compact_user,
                is_admin=True,
                admin_dashboard=_build_admin_dashboard(connection, admin_scope),
            )
        return UserSessionRestoreResponse(
            authenticated=True,
            user=compact_user,
            dashboard=_build_dashboard(connection, full_user),
        )


@router.post("/session/reopen-profile", response_model=CheckOrCreateUserResponse)
def reopen_profile_session(request: Request, response: FastAPIResponse) -> CheckOrCreateUserResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия не найдена. Войдите заново.")
    with get_connection() as connection:
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
def bootstrap_user_session(user_id: int) -> UserSessionBootstrapResponse:
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
                dashboard=_build_dashboard(connection, user),
                is_admin=True,
                admin_dashboard=_build_admin_dashboard(connection, admin_scope),
            )
        return UserSessionBootstrapResponse(
            user=_compact_user_response(user),
            dashboard=_build_dashboard(connection, user),
        )


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
        _require_superadmin(connection, user)
        return _build_admin_organizations(connection)


@router.post("/admin/organizations", response_model=AdminOrganizationsResponse)
def create_admin_organization(payload: AdminOrganizationCreateRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    org_code = _normalize_admin_org_code(payload.code)
    org_name = _normalize_admin_org_name(payload.name)
    with get_connection() as connection:
        _require_superadmin(connection, user)
        try:
            connection.execute(
                """
                INSERT INTO organizations (code, name)
                VALUES (%s, %s)
                """,
                (org_code, org_name),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise HTTPException(status_code=409, detail="Organization with this code already exists") from exc
        return _build_admin_organizations(connection)


@router.patch("/admin/organizations/{organization_id}", response_model=AdminOrganizationsResponse)
def update_admin_organization(organization_id: int, payload: AdminOrganizationUpdateRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_code = _normalize_admin_org_code(payload.code) if payload.code is not None else None
    normalized_name = _normalize_admin_org_name(payload.name) if payload.name is not None else None
    if normalized_code is None and normalized_name is None:
        raise HTTPException(status_code=400, detail="No organization changes provided")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        org_row = connection.execute("SELECT id FROM organizations WHERE id = %s LIMIT 1", (organization_id,)).fetchone()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        try:
            connection.execute(
                """
                UPDATE organizations
                SET code = COALESCE(%s, code),
                    name = COALESCE(%s, name),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (normalized_code, normalized_name, organization_id),
            )
            connection.commit()
        except Exception as exc:
            connection.rollback()
            raise HTTPException(status_code=409, detail="Organization with this code already exists") from exc
        return _build_admin_organizations(connection)


@router.delete("/admin/organizations/{organization_id}", response_model=AdminOrganizationsResponse)
def delete_or_deactivate_admin_organization(organization_id: int, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    with get_connection() as connection:
        _require_superadmin(connection, user)
        org_row = connection.execute("SELECT id FROM organizations WHERE id = %s LIMIT 1", (organization_id,)).fetchone()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*)::int FROM organization_memberships WHERE organization_id = %s) AS members_count,
                (SELECT COUNT(DISTINCT us.id)::int
                 FROM organization_memberships om
                 JOIN user_sessions us ON us.user_id = om.user_id
                 WHERE om.organization_id = %s) AS reports_count
            """,
            (organization_id, organization_id),
        ).fetchone()
        is_empty = not any(int(counts[key] or 0) for key in ("members_count", "reports_count"))
        if is_empty:
            connection.execute("DELETE FROM organizations WHERE id = %s", (organization_id,))
        else:
            connection.execute(
                "UPDATE organizations SET is_active = FALSE, updated_at = NOW() WHERE id = %s",
                (organization_id,),
            )
        connection.commit()
        return _build_admin_organizations(connection)


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


@router.post("/admin/organizations/{organization_id}/admins", response_model=AdminOrganizationsResponse)
def add_admin_organization_admin(organization_id: int, payload: AdminOrganizationAdminRequest, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_email = normalize_email(payload.email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid admin email is required")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        org_row = connection.execute("SELECT id FROM organizations WHERE id = %s LIMIT 1", (organization_id,)).fetchone()
        if org_row is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        user_id = _ensure_org_admin_user(connection, email=normalized_email, full_name=payload.full_name)
        connection.execute(
            """
            INSERT INTO organization_memberships (organization_id, user_id, role)
            VALUES (%s, %s, 'admin')
            ON CONFLICT (organization_id, user_id) DO UPDATE
            SET role = 'admin',
                updated_at = NOW()
            """,
            (organization_id, user_id),
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
        user_row = connection.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(email) = %s
            LIMIT 1
            """,
            (normalized_email,),
        ).fetchone()
        if user_row is not None:
            connection.execute(
                """
                DELETE FROM organization_memberships
                WHERE organization_id = %s
                  AND user_id = %s
                  AND role = 'admin'
                """,
                (organization_id, int(user_row["id"])),
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
        _require_superadmin(connection, user)
        _attach_user_to_organization(
            connection,
            organization_id=organization_id,
            email=normalized_email,
            full_name=payload.full_name,
            role_description=payload.role_description,
            job_instructions=payload.job_instructions,
        )
        connection.commit()
        return _build_admin_organizations(connection)


@router.delete("/admin/organizations/{organization_id}/members", response_model=AdminOrganizationsResponse)
def delete_admin_organization_member(organization_id: int, email: str, request: Request) -> AdminOrganizationsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Valid member email is required")
    if normalized_email.startswith("__autotest__") or normalized_email.endswith("@autotest.local"):
        raise HTTPException(status_code=400, detail="Autotest members are protected. Use regression test cleanup instead.")
    with get_connection() as connection:
        _require_superadmin(connection, user)
        user_row = connection.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(email) = %s
            LIMIT 1
            """,
            (normalized_email,),
        ).fetchone()
        if user_row is not None:
            connection.execute(
                """
                DELETE FROM organization_memberships
                WHERE organization_id = %s
                  AND user_id = %s
                  AND role = 'member'
                """,
                (organization_id, int(user_row["id"])),
            )
            connection.commit()
        return _build_admin_organizations(connection)


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
        _require_superadmin(connection, user)
        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV header is required")
        for line_number, row in enumerate(reader, start=2):
            email = normalize_email(_csv_value(row, "email", "e-mail", "mail"))
            if not email:
                skipped_count += 1
                errors.append(f"Строка {line_number}: email не указан или некорректен")
                continue
            try:
                _attach_user_to_organization(
                    connection,
                    organization_id=organization_id,
                    email=email,
                    full_name=_csv_value(row, "full_name", "name", "fio", "фио"),
                    role_description=_csv_value(row, "role_description", "position", "job_title", "role", "должность", "роль"),
                    job_instructions=_csv_value(row, "job_instructions", "duties", "instructions", "job_description", "обязанности", "инструкции"),
                )
                imported_count += 1
            except Exception as exc:
                skipped_count += 1
                errors.append(f"Строка {line_number}: {exc}")
        connection.commit()
        organizations = _build_admin_organizations(connection)
    return AdminOrganizationImportResult(
        imported_count=imported_count,
        skipped_count=skipped_count,
        errors=errors[:20],
        organizations=organizations,
    )


@router.get("/admin/reports", response_model=AdminDetailedReportsResponse)
def get_admin_reports(request: Request) -> AdminDetailedReportsResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        return _build_admin_reports(connection, scope)


@router.get("/admin/reports/{session_id}", response_model=AdminReportDetailResponse)
def get_admin_report_detail(session_id: int, request: Request) -> AdminReportDetailResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        return _build_admin_report_detail(connection, session_id, scope)


@router.patch("/admin/reports/{session_id}/expert-comment", response_model=AdminReportDetailResponse)
def update_admin_report_expert_comment(session_id: int, payload: AdminExpertCommentUpdateRequest, request: Request) -> AdminReportDetailResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    normalized_comment = str(payload.expert_comment or "").strip() or None
    normalized_expert_name = str(payload.expert_name or "").strip() or None
    normalized_expert_contacts = str(payload.expert_contacts or "").strip() or None
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        scope_sql, scope_params = admin_scope_sql(scope)
        session_row = connection.execute(
            f"""
            SELECT id, status
            FROM user_sessions us
            JOIN users u ON u.id = us.user_id
            WHERE us.id = %s
              AND us.assessment_code = 'competencies_4k'
              {scope_sql}
            LIMIT 1
            """,
            (session_id, *scope_params),
        ).fetchone()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Assessment report not found")
        if session_row["status"] != "completed":
            raise HTTPException(status_code=409, detail="Expert comment is available only for completed assessments")

        connection.execute(
            """
            UPDATE user_sessions
            SET expert_comment = %s,
                expert_name = %s,
                expert_contacts = %s,
                expert_assessed_at = %s,
                expert_comment_updated_at = %s
            WHERE id = %s
            """,
            (
                normalized_comment,
                normalized_expert_name,
                normalized_expert_contacts,
                payload.expert_assessed_at,
                datetime.utcnow(),
                session_id,
            ),
        )
        connection.commit()
        return _build_admin_report_detail(connection, session_id, scope)


@router.get("/admin/reports/{session_id}/dialogue.pdf")
def download_admin_report_dialogue_pdf(session_id: int, request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        try:
            detail = _build_admin_report_detail(connection, session_id, scope)
            filename, pdf_bytes = admin_report_dialogue_pdf_service.build_pdf(detail)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.get("/admin/reports/{session_id}/expert.xls")
def download_admin_report_expert_excel(session_id: int, request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        detail = _build_admin_report_detail(connection, session_id, scope)
        filename, excel_bytes = admin_report_expert_export_service.build_excel(detail)

    return Response(
        content=excel_bytes,
        media_type="application/vnd.ms-excel",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.get("/admin/reports/{session_id}/expert.pdf")
def download_admin_report_expert_pdf(session_id: int, request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        try:
            detail = _build_admin_report_detail(connection, session_id, scope)
            filename, pdf_bytes = admin_report_expert_export_service.build_pdf(detail)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.post("/admin/reports/expert-group.zip")
def download_admin_reports_expert_group_zip(payload: AdminExpertGroupExportRequest, request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    session_ids = [int(session_id) for session_id in payload.session_ids if int(session_id) > 0]
    if not session_ids:
        raise HTTPException(status_code=400, detail="No assessment sessions selected")

    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        scope_sql, scope_params = admin_scope_sql(scope)

        session_rows = connection.execute(
            f"""
            SELECT us.id
            FROM user_sessions us
            JOIN users u ON u.id = us.user_id
            WHERE us.assessment_code = 'competencies_4k'
              AND us.status = 'completed'
              AND us.id = ANY(%s)
              AND LOWER(COALESCE(u.email, '')) <> %s
              {scope_sql}
            ORDER BY us.finished_at DESC NULLS LAST, us.id DESC
            """,
            (session_ids, ADMIN_EMAIL.lower(), *scope_params),
        ).fetchall()
        completed_session_ids = [int(row["id"]) for row in session_rows]
        if not completed_session_ids:
            raise HTTPException(status_code=400, detail="No completed assessments found in selection")

        details = [_build_admin_report_detail(connection, session_id, scope) for session_id in completed_session_ids]
        filename, zip_bytes = admin_report_expert_export_service.build_group_pdf_bundle(details)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.get("/admin/reports/export/expert-group.zip")
def download_admin_reports_expert_group_zip_get(request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    raw_parts: list[str] = []
    for raw_value in request.query_params.getlist("session_ids"):
        if raw_value is None:
            continue
        raw_parts.extend(part.strip() for part in str(raw_value).split(","))
    normalized_session_ids: list[int] = []
    for part in raw_parts:
        if not part:
            continue
        if not part.isdigit():
            continue
        value = int(part)
        if value > 0:
            normalized_session_ids.append(value)
    if not normalized_session_ids:
        raise HTTPException(status_code=400, detail="No assessment sessions selected")

    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        scope_sql, scope_params = admin_scope_sql(scope)

        session_rows = connection.execute(
            f"""
            SELECT us.id
            FROM user_sessions us
            JOIN users u ON u.id = us.user_id
            WHERE us.assessment_code = 'competencies_4k'
              AND us.status = 'completed'
              AND us.id = ANY(%s)
              AND LOWER(COALESCE(u.email, '')) <> %s
              {scope_sql}
            ORDER BY us.finished_at DESC NULLS LAST, us.id DESC
            """,
            (normalized_session_ids, ADMIN_EMAIL.lower(), *scope_params),
        ).fetchall()
        completed_session_ids = [int(row["id"]) for row in session_rows]
        if not completed_session_ids:
            raise HTTPException(status_code=400, detail="No completed assessments found in selection")

        details = [_build_admin_report_detail(connection, session_id, scope) for session_id in completed_session_ids]
        filename, zip_bytes = admin_report_expert_export_service.build_group_pdf_bundle(details)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.get("/admin/reports/{session_id}/cases/{session_case_id}/dialogue.pdf")
def download_admin_report_case_dialogue_pdf(session_id: int, session_case_id: int, request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        try:
            detail = _build_admin_report_detail(connection, session_id, scope)
            case_item = next((item for item in detail.case_items if int(item.session_case_id) == int(session_case_id)), None)
            if case_item is None:
                raise HTTPException(status_code=404, detail="Case dialogue not found")
            filename, pdf_bytes = admin_report_dialogue_pdf_service.build_case_pdf(detail, case_item)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.get("/admin/reports.pdf")
def download_admin_reports_pdf(request: Request) -> Response:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = web_session_service.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Admin session not found")
    with get_connection() as connection:
        scope = _get_admin_scope_or_403(connection, user)
        try:
            filename, pdf_bytes = admin_reports_pdf_service.build_pdf(_build_admin_reports(connection, scope))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; '
                'filename="admin_detailed_reports.pdf"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


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


@router.post("/session/logout")
def logout_user_session(request: Request, response: FastAPIResponse) -> dict[str, bool]:
    web_session_service.delete_session(request.cookies.get(SESSION_COOKIE_NAME))
    _clear_user_session_cookie(response)
    return {"ok": True}

@router.get("", response_model=list[UserResponse])
def get_users() -> list[UserResponse]:
    with get_connection() as connection:
        rows = connection.execute(
            USER_SELECT_SQL
            + """
            ORDER BY u.id ASC
            """
        ).fetchall()

    return [UserResponse(**dict(row)) for row in rows]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int) -> UserResponse:
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
def get_user_profile_summary(user_id: int) -> UserProfileSummaryResponse:
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

    return UserProfileSummaryResponse(
        user=user,
        total_assessments=len(history),
        completed_assessments=sum(1 for item in history if item.status == "completed"),
        average_score_percent=round(sum(score_values) / len(score_values)) if score_values else None,
        latest_session_id=history[0].session_id if history else None,
        history=history,
    )


@router.patch("/{user_id}/profile", response_model=UserResponse)
def update_user_profile(user_id: int, payload: UserProfileUpdateRequest) -> UserResponse:
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

        connection.execute(
            """
            UPDATE users
            SET email = %s,
                telegram = %s,
                avatar_data_url = %s
            WHERE id = %s
            """,
            (
                payload.email,
                payload.telegram,
                avatar_data_url,
                user_id,
            ),
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


@router.post("/agent/message", response_model=AgentReply)
def process_agent_message(payload: AgentMessageRequest, request: Request, response: FastAPIResponse) -> AgentReply:
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
    except KeyError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{user_id}/assessment/start", response_model=AssessmentStartResponse)
def start_assessment(user_id: int, request: Request) -> AssessmentStartResponse:
    operation_id = request.headers.get("X-Agent4K-Operation-Id")
    operation_progress_service.begin(
        operation_id,
        title="Подготавливаем ассессмент",
        message="Проверяем профиль пользователя и запускаем формирование оценочной сессии.",
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

    user = _user_response_from_row(row)
    if (
        not user.role_id
        or not (user.company_industry and user.company_industry.strip())
        or not user.active_profile_id
        or not (user.normalized_duties and user.normalized_duties.strip())
    ):
        repaired_user = interviewer_agent.backfill_user_profile(user.id)
        if repaired_user is not None:
            user = repaired_user
    try:
        result = interviewer_agent.start_case_interview(user=user, progress_operation_id=operation_id)
        operation_progress_service.complete(
            operation_id,
            title="Ассессмент готов",
            message="Первый кейс подготовлен. Можно начинать интервью.",
        )
        return result
    except ValueError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assessment/message", response_model=AssessmentMessageResponse)
def process_assessment_message(payload: AssessmentMessageRequest, request: Request) -> AssessmentMessageResponse:
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
        operation_progress_service.complete(
            operation_id,
            title="Итоговый отчет готов" if assessment_completed else "Следующий шаг готов",
            message=(
                "Все кейсы обработаны. Открываем экран итогового анализа."
                if assessment_completed
                else "Интервью обновлено. Можно продолжать работу с кейсом."
            ),
        )
        return result
    except ValueError as exc:
        operation_progress_service.fail(operation_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assessment/pause")
def pause_assessment_timer(payload: AssessmentTimerControlRequest) -> dict:
    try:
        assessment_service.pause_assessment_dialogue(payload.session_code)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{user_id}/assessment/{session_id}/mbti-refinement/start", response_model=MbtiRefinementStartResponse)
def start_mbti_refinement(user_id: int, session_id: int) -> MbtiRefinementStartResponse:
    with get_connection() as connection:
        try:
            result = mbti_refinement_service.start(connection, user_id=user_id, session_id=session_id)
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if 'not found' in detail.lower() else 409 if 'доступно только после завершения' in detail.lower() else 400
            raise HTTPException(status_code=status_code, detail=detail) from exc
    return MbtiRefinementStartResponse(**result)


@router.post("/{user_id}/assessment/{session_id}/mbti-refinement/message", response_model=MbtiRefinementMessageResponse)
def submit_mbti_refinement_answer(
    user_id: int,
    session_id: int,
    payload: MbtiRefinementMessageRequest,
) -> MbtiRefinementMessageResponse:
    with get_connection() as connection:
        try:
            result = mbti_refinement_service.submit_answer(
                connection,
                user_id=user_id,
                session_id=session_id,
                refinement_id=payload.refinement_id,
                answer=payload.answer,
            )
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if 'not found' in detail.lower() else 409 if 'already completed' in detail.lower() else 400
            raise HTTPException(status_code=status_code, detail=detail) from exc
    return MbtiRefinementMessageResponse(**result)


@router.get("/{user_id}/assessment/{session_id}/mbti-refinement", response_model=MbtiRefinementStateResponse)
def get_mbti_refinement_state(user_id: int, session_id: int) -> MbtiRefinementStateResponse:
    with get_connection() as connection:
        try:
            result = mbti_refinement_service.get_state(connection, user_id=user_id, session_id=session_id)
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if 'not found' in detail.lower() else 400
            raise HTTPException(status_code=status_code, detail=detail) from exc
    return MbtiRefinementStateResponse(**result)


@router.get("/{user_id}/assessment/{session_id}/skill-assessments", response_model=list[SkillAssessmentResponse])
def get_skill_assessments(user_id: int, session_id: int) -> list[SkillAssessmentResponse]:
    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")

        session_row = connection.execute(
            """
            SELECT id, mbti_summary_json
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
def get_assessment_session_by_code(user_id: int, session_code: str) -> AssessmentSessionLookupResponse:
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
def get_report_interpretation(user_id: int, session_id: int) -> AssessmentReportInterpretationResponse:
    with get_connection() as connection:
        user_row = connection.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,),
        ).fetchone()
        if user_row is None:
            raise HTTPException(status_code=404, detail="User not found")

        session_row = connection.execute(
            """
            SELECT id, mbti_summary_json
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
        interpretation["mbti_summary"] = (
            session_row["mbti_summary_json"]
            if session_row.get("mbti_summary_json") not in (None, {})
            else None
        )

    return AssessmentReportInterpretationResponse(**interpretation)


@router.get(
    "/{user_id}/assessment/{session_id}/structured-analysis",
    response_model=list[SessionCaseStructuredAnalysisResponse],
)
def get_session_case_structured_analysis(user_id: int, session_id: int) -> list[SessionCaseStructuredAnalysisResponse]:
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


@router.get("/{user_id}/assessment/{session_id}/report.pdf")
def download_skill_assessment_pdf(user_id: int, session_id: int) -> Response:
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

        try:
            filename, pdf_bytes = pdf_report_service.build_pdf(connection, user_id, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; '
                'filename="competency_profile.pdf"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )
