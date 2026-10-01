from uuid import uuid4

import pytest

from Api.m5_generation_lab import GenerationRequest, build_generation_input, gateway, generate


@pytest.mark.llm
@pytest.mark.parametrize("case_id,role", [("CASE-TDISC-04", "team_lead"), ("CASE-TDISC-01", "project_product_process_manager")])
def test_m5_real_role_generation(case_id, role):
    if not gateway.enabled:
        pytest.skip("DeepSeek is not configured")
    snapshot = build_generation_input(GenerationRequest(run_id=uuid4(), case_id=case_id, base_role=role, mode="llm"))
    output = generate(snapshot)
    assert output["presentation"]
    assert output["mode"] == "llm"
    assert len(output["observability"]) > 1
    assert output["methodological_qa"] == "NOT_RUN"
