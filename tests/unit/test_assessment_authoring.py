from types import SimpleNamespace

import pytest

from Api.assessment_authoring_service import assessment_authoring_service
from Api.assessment_configuration import LEGACY_METHODOLOGY_DEFINITION, LEGACY_SCENARIO_DEFINITION
from Api.platform_access import has_platform_permission


@pytest.mark.unit
def test_methodology_validation_accepts_registered_four_evaluators() -> None:
    assessment_authoring_service.validate_definition(
        entity_type="methodology",
        definition=LEGACY_METHODOLOGY_DEFINITION,
    )


@pytest.mark.unit
def test_methodology_validation_rejects_unknown_evaluator() -> None:
    definition = {
        "competencies": [
            {"code": "communication", "evaluator": "evaluation.unknown", "evaluator_version": 1}
        ]
    }
    with pytest.raises(ValueError, match="Unknown assessment component"):
        assessment_authoring_service.validate_definition(entity_type="methodology", definition=definition)


@pytest.mark.unit
def test_scenario_validation_accepts_legacy_scenario() -> None:
    assessment_authoring_service.validate_definition(
        entity_type="scenario",
        definition=LEGACY_SCENARIO_DEFINITION,
    )


@pytest.mark.unit
def test_authoring_validation_rejects_mbti_anywhere() -> None:
    definition = dict(LEGACY_SCENARIO_DEFINITION)
    definition["description"] = "MBTI enabled"
    with pytest.raises(ValueError, match="MBTI"):
        assessment_authoring_service.validate_definition(entity_type="scenario", definition=definition)


class PermissionConnection:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    def execute(self, _statement, _params):
        allowed = self.allowed

        class Result:
            def fetchone(self):
                return {"allowed": True} if allowed else None

        return Result()


@pytest.mark.unit
def test_methodologist_permission_is_loaded_from_platform_roles() -> None:
    user = SimpleNamespace(id=17, email="methodologist@example.test")
    assert has_platform_permission(PermissionConnection(True), user, "methodology.edit_draft") is True
    assert has_platform_permission(PermissionConnection(False), user, "methodology.publish") is False


@pytest.mark.unit
def test_configured_superadmin_bypasses_platform_assignment(monkeypatch) -> None:
    monkeypatch.setattr("Api.platform_access.configured_superadmin_emails", lambda: {"root@example.test"})
    user = SimpleNamespace(id=1, email="root@example.test")
    assert has_platform_permission(PermissionConnection(False), user, "methodology.publish") is True
