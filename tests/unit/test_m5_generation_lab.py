from uuid import uuid4

import pytest

from Api.m5_generation_lab import GenerationRequest, build_generation_input, generate

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("role", ["team_lead", "project_product_process_manager"])
def test_generation_preserves_role_and_multiple_indicators(role):
    request = GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role=role)
    snapshot = build_generation_input(request)
    result = generate(snapshot)
    assert result["base_role"] == role
    assert len(result["observability"]) == 2
    assert snapshot["profile"]["authority"] in result["presentation"]
    assert result["methodological_qa"] == "NOT_RUN"
    assert not result["admitted_for_assessment"]


def test_role_projections_are_distinct_without_user_identity():
    inputs = [build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role=role))
              for role in ("team_lead", "project_product_process_manager")]
    assert inputs[0]["profile"]["authority"] != inputs[1]["profile"]["authority"]
    assert all("full_name" not in x["profile"] and "contacts" not in x["profile"] for x in inputs)


def test_llm_receives_no_hidden_facts_or_indicator_hints():
    class Gateway:
        enabled = True

        def chat(self, messages, **kwargs):
            assert "Скрытые факты" not in messages[1]["content"]
            assert "K4.I02" not in messages[1]["content"]
            assert "36/180" not in messages[1]["content"]
            return '{"presentation": "Учебная ситуация: после обновления число повторных обращений выросло с 5 до 15. Вы руководите поддержкой. Какие действия предпримете?"}'

    snapshot = build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role="team_lead", mode="llm"))
    assert generate(snapshot, Gateway())["mode"] == "llm"


def test_llm_failure_does_not_silently_fallback_to_template():
    class Gateway:
        enabled = False

    snapshot = build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role="team_lead", mode="llm"))
    with pytest.raises(RuntimeError, match="LLM_UNAVAILABLE"):
        generate(snapshot, Gateway())
