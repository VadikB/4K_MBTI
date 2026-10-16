from copy import deepcopy

from Api.m5_equivalent_generation import (
    ControlledEquivalentProvider,
    _safe_profile,
    load_variability_package,
    run_provider,
    validate_candidate,
)


def base_input():
    contract = load_variability_package()["contract"]
    targets = [{"indicator_id": "K1.I13", "m2_version": "1.1"}]
    participant = {
        "case_id": "CASE-TDISC-01", "case_version": "v0.1",
        "initial_situation": "old situation", "trigger": "old trigger",
        "assessee_position": "fixed authority", "assessee_task": "fixed task",
        "conditions_and_constraints": "fixed limits",
    }
    execution = {
        "case_id": "CASE-TDISC-01", "case_version": "v0.1",
        "characters": [{"name_and_role": "old name", "public_position": "old public"}],
        "materials": [{"participant_payload": "old situation"}],
        "indicator_targets": targets, "scenario": [{"step_id": "S1"}],
    }
    return {
        "base_role": "project_product_process_manager", "indicator_targets": targets,
        "variability_contract": contract,
        "old_content": {"participant_payload": participant, "execution_payload": execution},
    }


def candidate(value):
    old = value["old_content"]
    result = {
        "case_id": "CASE-TDISC-01", "case_version": "v0.1",
        "base_role": value["base_role"], "indicator_targets": value["indicator_targets"],
        "participant_payload": deepcopy(old["participant_payload"]),
        "execution_payload": deepcopy(old["execution_payload"]),
    }
    result["participant_payload"]["initial_situation"] = "new coherent situation"
    result["participant_payload"]["trigger"] = "new substantive trigger"
    result["execution_payload"]["materials"][0]["participant_payload"] = "new coherent situation"
    return result


def test_package_and_two_consistent_variants_are_admitted():
    value = base_input()
    first = candidate(value)
    second = candidate(value)
    second["participant_payload"]["initial_situation"] = "another coherent situation"
    second["execution_payload"]["materials"][0]["participant_payload"] = "another coherent situation"
    assert validate_candidate(value, first)["admitted"] is True
    assert validate_candidate(value, second)["admitted"] is True
    assert first != second


def test_target_invariant_authority_and_links_block_admission():
    value = base_input()
    cases = []
    changed_target = candidate(value)
    changed_target["indicator_targets"] = [{"indicator_id": "K9.I99", "m2_version": "1.1"}]
    cases.append(changed_target)
    changed_authority = candidate(value)
    changed_authority["participant_payload"]["assessee_position"] = "unlimited authority"
    cases.append(changed_authority)
    contradictory = candidate(value)
    contradictory["execution_payload"]["materials"][0]["participant_payload"] = "old situation"
    cases.append(contradictory)
    changed_scenario = candidate(value)
    changed_scenario["execution_payload"]["scenario"][0]["step_id"] = "S2"
    cases.append(changed_scenario)
    for item in cases:
        assert validate_candidate(value, item)["admitted"] is False


def test_cosmetic_name_only_is_not_substantive_and_provider_has_no_db_access():
    value = base_input()
    item = candidate(value)
    item["participant_payload"] = deepcopy(value["old_content"]["participant_payload"])
    item["execution_payload"] = deepcopy(value["old_content"]["execution_payload"])
    item["execution_payload"]["characters"][0]["name_and_role"] = "new name"
    assert validate_candidate(value, item)["admitted"] is False
    claimed = {"input_json": {"profile_content": {"role_profile": {"code": "manager"}}}}
    assert run_provider(ControlledEquivalentProvider(item), claimed) == item
    safe = _safe_profile({"email": "private@example.test", "full_name": "Private Person", "content": {
        "organization_context": {"industry": "test"}, "role_profile": {"code": "manager"},
        "user_context": {"regular_tasks": ["planning"]}, "identity": {"full_name": "Private Person"}}})
    assert "private" not in str(safe).lower() and "email" not in str(safe).lower()


def test_null_whitespace_and_linked_copy_do_not_prove_substantive_difference():
    value = base_input()
    for malformed in (None, [], {}, {"participant_payload": None, "execution_payload": {}}):
        assert validate_candidate(value, malformed)["admitted"] is False
    for replacement in (None, " "):
        item = candidate(value)
        item["participant_payload"]["initial_situation"] = replacement
        item["execution_payload"]["materials"][0]["participant_payload"] = replacement
        item["participant_payload"]["trigger"] = value["old_content"]["participant_payload"]["trigger"]
        result = validate_candidate(value, item)
        assert result["admitted"] is False
    linked_only = candidate(value)
    linked_only["participant_payload"]["trigger"] = value["old_content"]["participant_payload"]["trigger"]
    assert validate_candidate(value, linked_only)["admitted"] is False


def test_assessment_scope_requires_active_pass_evidence_and_has_no_qa_contradiction():
    value = base_input()
    value["variability_contract"].update({
        "status": "published", "usage_scope": "assessment", "content_admission": "approved",
        "admission_evidence": [{"evidence_id": "synthetic-a01", "result": "PASS", "status": "active",
                                "provenance": {"fixture": "unit-only"}}],
    })
    assert validate_candidate(value, candidate(value))["admitted"] is True
    for result, status in (("UNKNOWN", "active"), ("NOT_RUN", "active"), ("PASS", "revoked")):
        denied = deepcopy(value)
        denied["variability_contract"]["admission_evidence"][0].update(result=result, status=status)
        assert validate_candidate(denied, candidate(denied))["admitted"] is False
