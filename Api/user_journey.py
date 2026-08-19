from __future__ import annotations

from dataclasses import dataclass

from Api.schemas import UserResponse


PROFILE_REQUIRED_FIELDS = (
    "personal_data_consent",
    "position",
    "duties",
    "role",
    "company_industry",
    "active_profile",
)

ONBOARDING_STATUSES = {"not_started", "in_progress", "completed", "skipped"}
ASSESSMENT_STATUS_MAP = {
    "created": "preparing",
    "active": "in_progress",
    "completed": "report_ready",
    "failed": "failed",
}


@dataclass(frozen=True)
class ProfileState:
    status: str
    missing_fields: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"


def evaluate_profile_state(user: UserResponse) -> ProfileState:
    missing_fields: list[str] = []
    if user.personal_data_consent_accepted_at is None:
        missing_fields.append("personal_data_consent")
    if not _has_text(user.raw_position) and not _has_text(user.job_description):
        missing_fields.append("position")
    if not _has_text(user.raw_duties) and not _has_text(user.normalized_duties):
        missing_fields.append("duties")
    if not user.role_id:
        missing_fields.append("role")
    if not _has_text(user.company_industry):
        missing_fields.append("company_industry")
    if not user.active_profile_id:
        missing_fields.append("active_profile")
    return ProfileState(
        status="complete" if not missing_fields else "incomplete",
        missing_fields=tuple(missing_fields),
    )


def normalize_assessment_status(status: str | None) -> str:
    normalized = str(status or "not_started")
    return ASSESSMENT_STATUS_MAP.get(normalized, normalized)


def determine_next_action(*, profile_status: str, onboarding_status: str, assessment_status: str) -> str:
    if profile_status != "complete":
        return "complete_profile"
    if onboarding_status in {"not_started", "in_progress"}:
        return "show_onboarding"
    if assessment_status == "in_progress":
        return "resume_assessment"
    if assessment_status in {"cases_completed", "analyzing"}:
        return "show_processing"
    if assessment_status == "failed":
        return "show_assessment_error"
    return "show_dashboard"


def get_or_create_onboarding_state(connection, user_id: int) -> dict:
    row = connection.execute(
        """
        INSERT INTO user_onboarding_state (user_id)
        VALUES (%s)
        ON CONFLICT (user_id) DO UPDATE SET user_id = EXCLUDED.user_id
        RETURNING user_id, status, current_step, started_at, completed_at, skipped_at, updated_at
        """,
        (user_id,),
    ).fetchone()
    return dict(row)


def update_onboarding_state(connection, user_id: int, *, status: str, current_step: int | None = None) -> dict:
    if status not in ONBOARDING_STATUSES:
        raise ValueError("Некорректный статус онбординга.")
    bounded_step = max(0, int(current_step or 0))
    row = connection.execute(
        """
        INSERT INTO user_onboarding_state (
            user_id, status, current_step, started_at, completed_at, skipped_at, updated_at
        )
        VALUES (
            %s, %s, %s,
            CASE WHEN %s = 'in_progress' THEN NOW() ELSE NULL END,
            CASE WHEN %s = 'completed' THEN NOW() ELSE NULL END,
            CASE WHEN %s = 'skipped' THEN NOW() ELSE NULL END,
            NOW()
        )
        ON CONFLICT (user_id) DO UPDATE SET
            status = EXCLUDED.status,
            current_step = EXCLUDED.current_step,
            started_at = CASE
                WHEN EXCLUDED.status = 'in_progress'
                THEN COALESCE(user_onboarding_state.started_at, NOW())
                ELSE user_onboarding_state.started_at
            END,
            completed_at = CASE
                WHEN EXCLUDED.status = 'completed' THEN NOW()
                ELSE user_onboarding_state.completed_at
            END,
            skipped_at = CASE
                WHEN EXCLUDED.status = 'skipped' THEN NOW()
                ELSE user_onboarding_state.skipped_at
            END,
            updated_at = NOW()
        RETURNING user_id, status, current_step, started_at, completed_at, skipped_at, updated_at
        """,
        (user_id, status, bounded_step, status, status, status),
    ).fetchone()
    return dict(row)


def _has_text(value: object) -> bool:
    return bool(str(value or "").strip())
