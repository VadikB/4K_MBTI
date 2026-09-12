import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from Api.assessment_authoring_service import assessment_authoring_service
from Api.assessment_agent_definitions import load_agent_definition_file
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
def test_methodology_dimensions_reject_duplicate_role_codes() -> None:
    definition = {
        **LEGACY_METHODOLOGY_DEFINITION,
        "roles": [
            {"code": "manager", "name": "Менеджер", "description": "Описание"},
            {"code": "manager", "name": "Другая роль", "description": "Описание"},
        ],
    }

    with pytest.raises(ValueError, match="roles codes must be present and unique"):
        assessment_authoring_service.validate_definition(entity_type="methodology", definition=definition)


@pytest.mark.unit
def test_scenario_validation_accepts_legacy_scenario() -> None:
    assessment_authoring_service.validate_definition(
        entity_type="scenario",
        definition=LEGACY_SCENARIO_DEFINITION,
    )


def evaluator_prompt_bundle(*, omit: str | None = None) -> dict:
    return {
        "assessment_agents": {
            code: {
                "profile": {"agent_code": code, "prompt_version": 1},
                "rules": [],
            }
            for code in ("communication", "teamwork", "creativity", "critical_thinking")
            if code != omit
        }
    }


def valid_agent_definition(*, executor_code: str = "evaluation.communication") -> dict:
    return {
        "schema_version": 1,
        "competency_code": "communication",
        "instruction_markdown": "# Communication evaluator\n\nEvaluate only observable evidence.",
        "input_contract": {"code": "competency_evaluation_input", "version": 1},
        "output_contract": {"code": "competency_evaluation_output", "version": 1},
        "executor": {"code": executor_code, "version": 1},
        "runtime": {"mode": "legacy_adapter"},
    }


@pytest.mark.unit
def test_agent_definition_validation_accepts_markdown_and_registered_executor() -> None:
    assessment_authoring_service.validate_definition(
        entity_type="agent",
        definition=valid_agent_definition(),
    )


@pytest.mark.unit
def test_agent_definition_validation_accepts_bounded_universal_runtime() -> None:
    definition = valid_agent_definition()
    definition["runtime"] = {
        "mode": "universal_llm",
        "model_profile": "assessment_strict",
        "temperature": 0,
        "max_attempts": 2,
        "timeout_seconds": 30,
        "max_output_tokens": 1200,
        "fallback": "fail",
    }

    assessment_authoring_service.validate_definition(entity_type="agent", definition=definition)


@pytest.mark.unit
def test_indicator_agent_files_resolve_shared_protocol_and_validate() -> None:
    root = Path("assessment_definitions/methodologies/competencies_4k/1.1/agents")
    definitions = {}
    for path in sorted(root.glob("indicator_*_v1.json")):
        definition = load_agent_definition_file(path)
        assessment_authoring_service.validate_definition(entity_type="agent", definition=definition)
        definitions[definition["code"]] = {"definition": definition}

    methodology = json.loads(
        Path("assessment_definitions/methodologies/competencies_4k/1.1/methodology.json").read_text(encoding="utf-8")
    )
    assessment_authoring_service.validate_definition(entity_type="methodology", definition=methodology)
    assessment_authoring_service._validate_evaluator_prompt_bundle(
        methodology_definition=methodology,
        prompt_bundle={},
        agent_definitions=definitions,
    )
    assert set(definitions) == {
        "indicator_communication", "indicator_teamwork", "indicator_creativity", "indicator_critical_thinking"
    }
    assert all("Отсутствие Evidence" in item["definition"]["instruction_markdown"] for item in definitions.values())


@pytest.mark.unit
def test_agent_definition_validation_rejects_universal_legacy_fallback() -> None:
    definition = valid_agent_definition()
    definition["runtime"] = {
        "mode": "universal_llm",
        "model_profile": "assessment_strict",
        "temperature": 0,
        "max_attempts": 2,
        "timeout_seconds": 30,
        "max_output_tokens": 1200,
        "fallback": "legacy_adapter",
    }

    with pytest.raises(ValueError, match="fallback=fail"):
        assessment_authoring_service.validate_definition(entity_type="agent", definition=definition)


@pytest.mark.unit
def test_agent_definition_validation_rejects_missing_markdown() -> None:
    definition = valid_agent_definition()
    definition["instruction_markdown"] = ""

    with pytest.raises(ValueError, match="instruction_markdown"):
        assessment_authoring_service.validate_definition(entity_type="agent", definition=definition)


@pytest.mark.unit
def test_agent_definition_validation_rejects_unknown_executor() -> None:
    with pytest.raises(ValueError, match="Unknown assessment component"):
        assessment_authoring_service.validate_definition(
            entity_type="agent",
            definition=valid_agent_definition(executor_code="evaluation.unknown"),
        )


@pytest.mark.unit
def test_configuration_prompt_bundle_requires_every_methodology_evaluator() -> None:
    with pytest.raises(ValueError, match="critical_thinking"):
        assessment_authoring_service._validate_evaluator_prompt_bundle(
            methodology_definition=LEGACY_METHODOLOGY_DEFINITION,
            prompt_bundle=evaluator_prompt_bundle(omit="critical_thinking"),
        )


@pytest.mark.unit
def test_configuration_prompt_bundle_accepts_all_methodology_evaluators() -> None:
    assessment_authoring_service._validate_evaluator_prompt_bundle(
        methodology_definition=LEGACY_METHODOLOGY_DEFINITION,
        prompt_bundle=evaluator_prompt_bundle(),
    )


@pytest.mark.unit
def test_universal_evaluator_bundle_requires_skill_codes_but_not_legacy_prompt() -> None:
    methodology = {
        "competencies": [
            {
                "code": "communication",
                "evaluator": "evaluation.communication",
                "evaluator_version": 1,
                "agent_definition": {"code": "communication", "version": 2},
                "skill_codes": ["active_listening"],
            }
        ]
    }
    definitions = {
        "communication": {"definition": {"runtime": {"mode": "universal_llm"}}}
    }

    assessment_authoring_service._validate_evaluator_prompt_bundle(
        methodology_definition=methodology,
        prompt_bundle={},
        agent_definitions=definitions,
    )

    methodology["competencies"][0]["skill_codes"] = []
    with pytest.raises(ValueError, match="skill_codes"):
        assessment_authoring_service._validate_evaluator_prompt_bundle(
            methodology_definition=methodology,
            prompt_bundle={},
            agent_definitions=definitions,
        )


@pytest.mark.unit
def test_methodology_shadow_contract_requires_distinct_agent_and_skill_scope() -> None:
    definition = {
        "competencies": [
            {
                "code": "communication",
                "evaluator": "evaluation.communication",
                "evaluator_version": 1,
                "agent_definition": {"code": "communication", "version": 1},
                "shadow_evaluation": {
                    "agent_definition": {"code": "communication_shadow", "version": 1},
                    "skill_codes": ["active_listening"],
                },
            }
        ]
    }

    assessment_authoring_service.validate_definition(entity_type="methodology", definition=definition)

    definition["competencies"][0]["shadow_evaluation"]["agent_definition"]["code"] = "communication"
    with pytest.raises(ValueError, match="different codes"):
        assessment_authoring_service.validate_definition(entity_type="methodology", definition=definition)


@pytest.mark.unit
def test_shadow_bundle_requires_legacy_official_and_universal_shadow() -> None:
    methodology = {
        "competencies": [
            {
                "code": "communication",
                "evaluator": "evaluation.communication",
                "evaluator_version": 1,
                "agent_definition": {"code": "communication", "version": 1},
                "shadow_evaluation": {
                    "agent_definition": {"code": "communication_shadow", "version": 1},
                    "skill_codes": ["active_listening"],
                },
            }
        ]
    }
    definitions = {
        "communication": {"definition": {"runtime": {"mode": "legacy_adapter"}}},
        "communication_shadow": {"definition": {"runtime": {"mode": "universal_llm"}}},
    }

    assessment_authoring_service._validate_evaluator_prompt_bundle(
        methodology_definition=methodology,
        prompt_bundle=evaluator_prompt_bundle(),
        agent_definitions=definitions,
    )

    definitions["communication_shadow"]["definition"]["runtime"]["mode"] = "legacy_adapter"
    with pytest.raises(ValueError, match="universal_llm"):
        assessment_authoring_service._validate_evaluator_prompt_bundle(
            methodology_definition=methodology,
            prompt_bundle=evaluator_prompt_bundle(),
            agent_definitions=definitions,
        )


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
