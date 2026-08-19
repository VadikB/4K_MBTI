from __future__ import annotations

import pytest

from Api.auth_service import normalize_email, validate_password_strength
from Api.schemas import AuthPasswordRegisterRequest, AuthPasswordResetRequest


def test_password_policy_accepts_strong_password() -> None:
    validate_password_strength("ReliablePass42", password_confirm="ReliablePass42")


@pytest.mark.parametrize(
    "password",
    ["Short1A", "lowercase123", "UPPERCASE123", "LettersOnlyPassword"],
)
def test_password_policy_rejects_weak_password(password: str) -> None:
    with pytest.raises(ValueError):
        validate_password_strength(password, password_confirm=password)


def test_password_policy_rejects_mismatched_confirmation() -> None:
    with pytest.raises(ValueError, match="Пароли не совпадают"):
        validate_password_strength("ReliablePass42", password_confirm="ReliablePass43")


def test_registration_request_carries_verification_token() -> None:
    payload = AuthPasswordRegisterRequest(
        email="User@Example.com",
        password="ReliablePass42",
        password_confirm="ReliablePass42",
        verification_token="verification-token",
    )
    assert payload.email == "user@example.com"
    assert payload.verification_token == "verification-token"


def test_reset_request_requires_action_token_and_new_password() -> None:
    payload = AuthPasswordResetRequest(
        token="reset-token",
        password="ReliablePass42",
        password_confirm="ReliablePass42",
    )
    assert payload.token == "reset-token"


def test_email_normalization_rejects_invalid_domain() -> None:
    with pytest.raises(ValueError):
        normalize_email("user@localhost")
