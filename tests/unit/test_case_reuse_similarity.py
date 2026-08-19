from Api.case_reuse_service import calculate_profile_similarity


def _profile(**overrides):
    profile = {
        "role_id": 7,
        "user_domain": "клиентская поддержка",
        "domain_profile": {"family": "service"},
        "user_tasks": ["обработка обращений", "эскалация инцидентов"],
        "user_processes": ["service desk"],
        "user_stakeholders": ["клиенты", "техническая команда"],
        "user_systems": ["Jira", "CRM"],
        "user_artifacts": ["тикет", "отчет SLA"],
        "user_constraints": ["срок SLA"],
        "user_risks": ["отток клиента"],
    }
    profile.update(overrides)
    return profile


def test_identical_profiles_have_full_similarity():
    result = calculate_profile_similarity(_profile(), _profile())

    assert result.compatible is True
    assert result.score == 1.0
    assert all(value == 1.0 for value in result.components.values())


def test_different_roles_are_incompatible():
    result = calculate_profile_similarity(_profile(), _profile(role_id=8))

    assert result.compatible is False
    assert result.score == 0.0
    assert result.components == {}


def test_similarity_is_explainable_and_weighted():
    result = calculate_profile_similarity(
        _profile(),
        _profile(user_stakeholders=["поставщики"], user_constraints=["бюджет"], user_risks=["штраф"]),
    )

    assert result.compatible is True
    assert 0.0 < result.score < 1.0
    assert set(result.components) == {
        "domain",
        "tasks_processes",
        "stakeholders",
        "systems_artifacts",
        "constraints_risks",
    }
