"""No SQL/provider: contract regression of exact design, stage and time gates."""
from copy import deepcopy

import pytest

from Api.assessment_start_readiness import functional_gate, plan_gate
from Api.m5_case_runtime import checksum
from Api.m5_functional_generation_service import checksum as candidate_checksum
from Api.m5_functional_tester import aggregate
from Api.pilot_plan_admission import project_plan
from tests.unit.test_pilot_plan_admission import inputs, snapshot

pytestmark = pytest.mark.unit


def accepted_plan():
    s = snapshot()
    args = inputs(s)
    projection = project_plan(s, **args)
    sources = {name: {"kind": "program", "revision_id": "synthetic-timing", "checksum": "a" * 64,
                     "organization_id": 10, "assessment_configuration_id": 11}
               for name in ("time_budget_seconds", "calendar_window_seconds")}
    binding = {"contract": "m7_pilot_plan_binding/1", "admission_snapshot": s,
               "profile_ref": {"id": 101, "checksum": "b" * 64},
               "assignment_scope": {"assignment_id": 41, "organization_id": 10, "recipient_user_id": 99},
               "timing_sources": sources}
    binding["binding_checksum"] = checksum(binding)
    resolution = checksum({"values": projection["timing"], "sources": sources})
    cycle = {"personalized_profile_id": 101, "owner_user_id": 99, "organization_id": 10,
             "assignment_id": 41, "profile_ref_json": {"checksum": "b" * 64},
             "target_set_json": args["targets"], "selected_role_ref_json": args["role_ref"],
             **projection["timing"], "parameter_sources_json": {
                 "time_budget": sources["time_budget_seconds"], "calendar_window": sources["calendar_window_seconds"],
                 "resolution_checksum": resolution}}
    plan = {"status": "LIMITED", "full_target_set": args["targets"],
            "planned_target_set": projection["planned_targets"], "route": projection["route"],
            "catalog": args["catalog"], "catalog_ref": args["catalog_ref"],
            "uncovered_target_ids": projection["outside_plan_target_ids"],
            "outside_plan_target_ids": projection["outside_plan_target_ids"], "uncovered_planned_target_ids": [],
            "parameter_sources": sources, "parameter_resolution_checksum": resolution,
            "pilot_plan_binding": binding, **projection["timing"]}
    return deepcopy(plan), deepcopy(cycle)


def functional_trace(*, warning=False, repair=False):
    checks = [{"check_id": "synthetic-protected", "mandatory": True, "protected": True, "status": "PASS"}]
    if warning:
        checks.append({"check_id": "synthetic-warning", "mandatory": True, "protected": False,
                       "status": "FAIL", "findings": [{"severity": "non_blocking"}]})
    candidate = {"CaseID": "synthetic-case", "CaseVersion": "1"}
    trace = {"accepted_as": candidate, "candidate_checksum": candidate_checksum(candidate),
             "admitted_for_participant": True,
             "deterministic_validation": {"status": "PASS", "checks": [{"result": "PASS"}]},
             "generation_operation": {"operation_id": "synthetic:repair" if repair else "synthetic:generation",
                                      "input_checksum": "c" * 64,
                                      "kind": "generation_repair" if repair else "generation"}}
    tester = {"checks": checks, "aggregation": aggregate(trace["deterministic_validation"], checks)}
    for name in ("provider_operation", "challenger_operation"):
        batches = [{"operation_id": "synthetic:" + name, "input_checksum": "d" * 64,
                    "required_check_ids": [row["check_id"] for row in checks
                                           if name == "provider_operation" or row["protected"]]}]
        tester[name] = {"batches": batches, "input_checksum": candidate_checksum([row["input_checksum"] for row in batches])}
    trace["tester"] = tester
    trace["tester_input_checksum"] = tester["provider_operation"]["input_checksum"]
    if repair:
        trace["repair"] = {"repair_generation_operation": deepcopy(trace["generation_operation"])}
    return trace


def test_exact_accepted_limited_is_design_admissible_without_changing_full_m2():
    plan, cycle = accepted_plan()
    binding = plan_gate(plan, cycle)
    assert binding == plan["pilot_plan_binding"]
    assert len(cycle["target_set_json"]) == 61
    assert len(plan["planned_target_set"]) == 39


@pytest.mark.parametrize("mutate", [
    lambda p, c: p.pop("pilot_plan_binding"),
    lambda p, c: p.update(status="READY"),
    lambda p, c: p.update(status="NO_ROUTE"),
    lambda p, c: p["route"].pop(),
    lambda p, c: p["planned_target_set"].pop(),
    lambda p, c: p["full_target_set"].pop(),
    lambda p, c: p["outside_plan_target_ids"].pop(),
    lambda p, c: p["uncovered_planned_target_ids"].append("synthetic-gap"),
    lambda p, c: p["pilot_plan_binding"]["admission_snapshot"]["owner_decision"]["methodologist"].update(status="PENDING"),
    lambda p, c: c.update(personalized_profile_id=999),
    lambda p, c: c.update(assignment_id=999),
    lambda p, c: c.update(owner_user_id=999),
    lambda p, c: c.update(organization_id=999),
    lambda p, c: c.update(time_budget_seconds=3600),
    lambda p, c: c["parameter_sources_json"].update(resolution_checksum="0" * 64),
])
def test_missing_approval_or_foreign_scope_never_becomes_ready(mutate):
    plan, cycle = accepted_plan()
    mutate(plan, cycle)
    with pytest.raises(ValueError, match="PILOT_PLAN_"):
        plan_gate(plan, cycle)


@pytest.mark.parametrize("warning", [False, True])
@pytest.mark.parametrize("repair", [False, True])
def test_terminal_pass_or_warnings_with_all_required_stages(warning, repair):
    trace = functional_trace(warning=warning, repair=repair)
    functional_gate(trace)


@pytest.mark.parametrize("mutate", [
    lambda t: t.update(admitted_for_participant=False),
    lambda t: t.update(candidate_checksum="0" * 64),
    lambda t: t.pop("generation_operation"),
    lambda t: t["tester"].pop("provider_operation"),
    lambda t: t["tester"].pop("challenger_operation"),
    lambda t: t["tester"]["challenger_operation"]["batches"].clear(),
    lambda t: t["tester"]["provider_operation"]["batches"][0]["required_check_ids"].clear(),
    lambda t: t["tester"]["aggregation"].update(status="INCOMPLETE"),
    lambda t: t["tester"]["aggregation"].update(status="FAIL"),
    lambda t: t["repair"]["repair_generation_operation"].update(operation_id="other-candidate"),
])
def test_warnings_do_not_bypass_final_stage_or_candidate_checks(mutate):
    trace = functional_trace(warning=True, repair=True)
    mutate(trace)
    with pytest.raises(ValueError, match="PILOT_PLAN_"):
        functional_gate(trace)
