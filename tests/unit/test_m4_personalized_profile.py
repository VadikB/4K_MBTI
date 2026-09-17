from __future__ import annotations

import copy

import pytest

from Api.assessment_contexts import build_personalized_profile, context_checksum


def _organization() -> dict:
    return {
        "name": "Организация",
        "organization_type": "компания",
        "industry": "образование",
        "activity_description": "Разработка образовательных программ",
        "case_reality_level": "обобщённый",
        "organization_name_usage_rules": "не использовать название",
    }


def _role() -> dict:
    return {
        "schema_version": 1,
        "kind": "base_role",
        "methodology_version": "1.1",
        "code": "specialist_expert",
    }


def _build(**overrides):
    values = {
        "organization_id": 10,
        "organization_context": _organization(),
        "organization_context_ref": {"version_id": 1, "checksum": "a" * 64},
        "role_profile": _role(),
        "role_profile_ref": {"version_id": 2, "checksum": "b" * 64},
        "user_identity": {"full_name": "Иван Иванов", "contacts": "private@example.test"},
        "user_context": {"position_or_status": "Эксперт", "regular_tasks": ["Анализ"]},
        "user_context_ref": {"version_id": 3, "checksum": "c" * 64},
    }
    values.update(overrides)
    return build_personalized_profile(**values)


@pytest.mark.unit
def test_personalized_profile_excludes_identity_and_is_deterministic() -> None:
    first = _build()
    second = _build()
    assert first == second
    assert first["status"] == "ready"
    assert "Иван Иванов" not in str(first)
    assert "private@example.test" not in str(first)
    checksum = first.pop("checksum")
    assert checksum == context_checksum(first)


@pytest.mark.unit
def test_personalized_profile_blocks_unresolved_critical_conflict() -> None:
    profile = _build(conflicts=[{"type": "authority", "resolved": False, "details": "requires approval"}])
    assert profile["status"] == "blocked"


@pytest.mark.unit
def test_personalized_profile_allows_resolved_or_noncritical_conflict() -> None:
    profile = _build(conflicts=[
        {"type": "authority", "resolved": True},
        {"type": "terminology", "resolved": False},
    ])
    assert profile["status"] == "ready"


@pytest.mark.unit
def test_personalized_profile_requires_all_organization_fields() -> None:
    organization = _organization()
    organization.pop("industry")
    with pytest.raises(ValueError, match="industry"):
        _build(organization_context=organization)


@pytest.mark.unit
def test_personalized_profile_requires_only_user_full_name() -> None:
    assert _build(user_identity={"full_name": "Иван Иванов"})["status"] == "ready"
    with pytest.raises(ValueError, match="full_name"):
        _build(user_identity={})
