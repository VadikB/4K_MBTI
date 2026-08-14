import pytest

from Api.assessment_prompt_resolver import prompt_resolver
from Api.communication_agent import CommunicationAgent
from Api.deepseek_client import DeepSeekClient


PROMPT_SNAPSHOT = {
    "prompts": {
        "interviewer": {
            "case_follow_up": {
                "name": "Frozen interviewer",
                "text": "Frozen prompt for {skills}",
                "version": 7,
            }
        },
        "assessment_agents": {
            "communication": {
                "profile": {"agent_code": "communication", "prompt_version": 4},
                "rules": [{"rule_code": "frozen", "rule_text": "Frozen rule"}],
            }
        },
        "case_generation_instructions": [
            {
                "instruction_code": "generic-v3",
                "instruction_text": "Frozen generic case instruction",
                "version": 3,
                "applies_to_type_code": None,
            },
            {
                "instruction_code": "f02-v2",
                "instruction_text": "Frozen F02 case instruction",
                "version": 2,
                "applies_to_type_code": "F02",
            },
        ],
    }
}


@pytest.mark.unit
def test_interviewer_prompt_is_resolved_from_session_snapshot() -> None:
    text = prompt_resolver.interviewer_prompt(
        PROMPT_SNAPSHOT,
        prompt_code="case_follow_up",
        fallback_text="fallback",
        format_values={"skills": "communication"},
    )
    assert text == "Frozen prompt for communication"


@pytest.mark.unit
def test_deepseek_facade_does_not_read_database_when_snapshot_is_present(monkeypatch) -> None:
    monkeypatch.setattr(
        "Api.deepseek_client.get_connection",
        lambda: (_ for _ in ()).throw(AssertionError("database lookup is not allowed")),
    )
    client = DeepSeekClient()
    assert client._get_interviewer_prompt_text(
        "case_follow_up",
        "fallback",
        prompt_snapshot=PROMPT_SNAPSHOT,
        skills="teamwork",
    ) == "Frozen prompt for teamwork"


@pytest.mark.unit
def test_assessment_agent_config_is_resolved_from_session_snapshot() -> None:
    agent = CommunicationAgent()

    class NoDatabaseLookup:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("active prompt tables must not be read")

    config = agent._load_agent_prompt_profile(NoDatabaseLookup(), PROMPT_SNAPSHOT)
    assert config["profile"]["prompt_version"] == 4
    assert config["rules"][0]["rule_code"] == "frozen"


@pytest.mark.unit
def test_missing_snapshot_prompt_uses_explicit_fallback() -> None:
    assert prompt_resolver.interviewer_prompt(
        {"prompts": {}},
        prompt_code="timeout_finish",
        fallback_text="timeout fallback",
    ) == "timeout fallback"


@pytest.mark.unit
def test_case_generation_prefers_type_specific_frozen_instruction() -> None:
    assert prompt_resolver.case_generation_instruction(
        PROMPT_SNAPSHOT,
        case_type_code="F02",
    ) == "Frozen F02 case instruction"
    assert prompt_resolver.case_generation_instruction(
        PROMPT_SNAPSHOT,
        case_type_code="F99",
    ) == "Frozen generic case instruction"
