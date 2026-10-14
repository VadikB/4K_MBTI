from datetime import datetime

from Api.schemas import UserResponse
from Api.user_journey import (
    determine_cycle_next_action,
    determine_next_action,
    evaluate_profile_state,
    normalize_assessment_status,
)


def make_user(**overrides) -> UserResponse:
    payload = {
        "id": 1,
        "full_name": "Тестовый Пользователь",
        "email": "user@example.test",
        "created_at": datetime(2026, 1, 1),
        "role_id": 7,
        "job_description": "Руководитель проектов",
        "raw_position": "Руководитель проектов",
        "raw_duties": "Управляет проектами",
        "normalized_duties": "Управление проектами",
        "active_profile_id": 11,
        "company_industry": "ИТ",
        "personal_data_consent_accepted_at": datetime(2026, 1, 1),
    }
    payload.update(overrides)
    return UserResponse(**payload)


def test_complete_profile_uses_one_consistent_required_field_set() -> None:
    state = evaluate_profile_state(make_user(telegram=None))

    assert state.status == "complete"
    assert state.missing_fields == ()


def test_incomplete_profile_reports_every_missing_field() -> None:
    state = evaluate_profile_state(
        make_user(
            personal_data_consent_accepted_at=None,
            raw_position=None,
            job_description=None,
            raw_duties=None,
            normalized_duties=None,
            role_id=None,
            company_industry=" ",
            active_profile_id=None,
        )
    )

    assert state.status == "incomplete"
    assert set(state.missing_fields) == {
        "personal_data_consent",
        "position",
        "duties",
        "role",
        "company_industry",
        "active_profile",
    }


def test_journey_prioritizes_profile_then_onboarding_then_assessment() -> None:
    assert determine_next_action(
        profile_status="incomplete",
        onboarding_status="completed",
        assessment_status="in_progress",
    ) == "complete_profile"
    assert determine_next_action(
        profile_status="complete",
        onboarding_status="not_started",
        assessment_status="in_progress",
    ) == "show_onboarding"
    assert determine_next_action(
        profile_status="complete",
        onboarding_status="skipped",
        assessment_status="in_progress",
    ) == "resume_assessment"
    assert determine_next_action(
        profile_status="complete",
        onboarding_status="completed",
        assessment_status="cases_completed",
    ) == "show_processing"
    assert determine_next_action(
        profile_status="complete",
        onboarding_status="completed",
        assessment_status="analyzing",
    ) == "show_processing"


def test_assessment_status_is_normalized_for_user_journey() -> None:
    assert normalize_assessment_status(None) == "not_started"
    assert normalize_assessment_status("created") == "preparing"
    assert normalize_assessment_status("active") == "in_progress"
    assert normalize_assessment_status("completed") == "report_ready"
    assert normalize_assessment_status("failed") == "failed"


def test_cycle_runtime_drives_journey_without_reopening_confirmed_profile() -> None:
    assert determine_cycle_next_action(
        profile_status="incomplete", onboarding_status="in_progress",
        cycle_status="active", assessment_situation_status="active",
    ) == "resume_assessment"
    assert determine_cycle_next_action(
        profile_status="complete", onboarding_status="completed",
        cycle_status="paused", assessment_situation_status="paused",
    ) == "resume_assessment"
    assert determine_cycle_next_action(
        profile_status="complete", onboarding_status="completed",
        cycle_status="calculation_pending", assessment_situation_status="closed",
    ) == "show_processing"
    assert determine_cycle_next_action(
        profile_status="complete", onboarding_status="completed",
        cycle_status="failed", assessment_situation_status="closed",
    ) == "show_assessment_error"
    assert determine_cycle_next_action(
        profile_status="complete", onboarding_status="completed",
        cycle_status="calculated", assessment_situation_status="closed",
    ) == "show_dashboard"
    assert determine_cycle_next_action(
        profile_status="complete", onboarding_status="completed",
        cycle_status="active", assessment_situation_status=None,
    ) == "show_assessment_error"
