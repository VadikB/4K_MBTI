from uuid import uuid4

import pytest

from Api.m5_generation_lab import GenerationRequest, build_generation_input, gateway, generate


@pytest.mark.llm
@pytest.mark.parametrize("role", ["team_lead", "project_product_process_manager"])
def test_m5_real_role_generation(role):
    if not gateway.enabled:
        pytest.skip("DeepSeek is not configured")
    snapshot = build_generation_input(GenerationRequest(run_id=uuid4(), case_id="SCR.A01", base_role=role, mode="llm"))
    output = generate(snapshot)
    assert output["presentation"]
    assert output["mode"] == "llm"
    assert len(output["observability"]) == 2
    assert output["methodological_qa"] == "NOT_RUN"
