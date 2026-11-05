"""The component substitution cannot become product/paid PATH admission."""
from copy import deepcopy
from pathlib import Path

import pytest

from Api.assessment_start_readiness import plan_gate
from Api.m7_planning_package import methodology_targets
from tests.browser_component_app import FIXTURE, component_plan_gate, load_policy, validate_activation

pytestmark = pytest.mark.unit


def activation():
    state = {"component_plan_fixture": FIXTURE, "gateway": 1, "provider_mode": "disabled",
             "database": "product4k_pytest_component", "owner_marker": "stand-10.2:synthetic"}
    env = {"AGENT4K_COMPONENT_PLAN_FIXTURE": FIXTURE, "AGENT4K_ISOLATED_STAND": "1",
           "DB_NAME": state["database"], "AGENT4K_STAND_MARKER": state["owner_marker"]}
    return state, env


def legacy_plan():
    policy, cases = load_policy()
    source = cases[("CASE-TDISC-01", "v0.1")]
    full = methodology_targets(["K1", "K2", "K3", "K4"])
    covered = [row["indicator_id"] for row in source["indicator_targets"]]
    plan = {"schema_version": 1, "status": "LIMITED", "full_target_set": full,
            "planned_target_set": full, "catalog_ref": policy["catalog"],
            "uncovered_target_ids": sorted({row["indicator_id"] for row in full} - set(covered)),
            "route": [{"case_id": source["case_id"], "case_version": source["version"],
                       "target_ids": covered, "eligible": True}],
            "time_budget_seconds": 3600, "calendar_window_seconds": 259200}
    return plan, {"target_set_json": full, "time_budget_seconds": 3600, "calendar_window_seconds": 259200}


def test_explicit_disabled_provider_owned_activation_only():
    validate_activation(*activation())


def test_changed_component_source_is_rejected(monkeypatch):
    read = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda path: b"{}" if path.name == "case-package.json" else read(path))
    with pytest.raises(ValueError, match="COMPONENT_PLAN_FIXTURE_SOURCE_CHANGED"):
        load_policy()


@pytest.mark.parametrize("mutate", [
    lambda s, e: s.pop("component_plan_fixture"),
    lambda s, e: s.update(gateway=0),
    lambda s, e: s.update(provider_mode="real"),
    lambda s, e: s.update(path29_full_path=True),
    lambda s, e: s.update(path29_program_source="published-pilot"),
    lambda s, e: e.pop("AGENT4K_COMPONENT_PLAN_FIXTURE"),
    lambda s, e: e.update(AGENT4K_ISOLATED_STAND="0"),
    lambda s, e: e.update(DB_NAME="working_database"),
    lambda s, e: e.update(AGENT4K_STAND_MARKER="foreign"),
])
def test_reject_activation_before_importing_product_or_opening_database(mutate):
    state, env = activation()
    mutate(state, env)
    with pytest.raises(RuntimeError, match="COMPONENT_PLAN_FIXTURE_REQUIRES"):
        validate_activation(state, env)


def test_component_policy_is_explicit_and_does_not_modify_stored_full_m2_or_real_gate():
    plan, cycle = legacy_plan()
    original = deepcopy((plan, cycle))
    with pytest.raises(ValueError, match="PILOT_PLAN_PLANNED_TARGET_GAP"):
        plan_gate(plan, cycle)
    assert component_plan_gate(plan, cycle, real_gate=plan_gate) is None
    assert (plan, cycle) == original
    assert len(cycle["target_set_json"]) == 61
    with pytest.raises(ValueError, match="PILOT_PLAN_PLANNED_TARGET_GAP"):
        plan_gate(plan, cycle)


@pytest.mark.parametrize("mutate", [
    lambda p, c: p["catalog_ref"].update(id="specialist-pilot"),
    lambda p, c: p["catalog_ref"].update(version="2"),
    lambda p, c: p["route"][0].update(case_id="CASE.SPEC.02"),
    lambda p, c: p["route"][0].update(case_version="different"),
    lambda p, c: p["route"][0]["target_ids"].pop(),
    lambda p, c: p["route"][0].update(eligible=False),
    lambda p, c: p.update(pilot_plan_binding={"contract": "foreign"}),
    lambda p, c: p.update(status="NO_ROUTE"),
    lambda p, c: p.update(time_budget_seconds=0),
    lambda p, c: c.update(calendar_window_seconds=1),
    lambda p, c: p["uncovered_target_ids"].pop(),
])
def test_no_arbitrary_limited_optin_route_or_timing_is_permitted(mutate):
    plan, cycle = deepcopy(legacy_plan())
    mutate(plan, cycle)
    with pytest.raises(ValueError, match="PILOT_PLAN_"):
        component_plan_gate(plan, cycle, real_gate=plan_gate)


@pytest.mark.parametrize("variant,budget,calendar", [("budget", 30, 259200), ("deadline", 3600, 30)])
def test_short_timing_is_frozen_before_preparing_as(monkeypatch, variant, budget, calendar):
    from scripts.browser_stand import prepare_time_variant
    calls = []
    plan = {"cycle_id": "synthetic-cycle", "revision_id": "synthetic-initial-revision"}
    def create(connection, **kwargs):
        calls.append(("create", kwargs))
        return plan
    def prepare(connection, **kwargs):
        calls.append(("prepare", kwargs))
        return {"plan": plan}
    monkeypatch.setattr("Api.m7_cycle_planner.create_plan", create)
    monkeypatch.setattr("Api.m10_product_flow.prepare", prepare)
    prepare_time_variant(object(), variant=variant, user_id=1, profile_id=2)
    assert [name for name, _ in calls] == ["create", "prepare"]
    assert calls[0][1]["usage_scope"] == "qa"
    assert calls[0][1]["time_budget_seconds"] == budget
    assert calls[0][1]["calendar_window_seconds"] == calendar


def test_short_timing_fixture_rejects_different_revision(monkeypatch):
    from scripts.browser_stand import prepare_time_variant
    monkeypatch.setattr("Api.m7_cycle_planner.create_plan", lambda *a, **kw: {"cycle_id": "c", "revision_id": "initial"})
    monkeypatch.setattr("Api.m10_product_flow.prepare", lambda *a, **kw: {"plan": {"cycle_id": "c", "revision_id": "stale"}})
    with pytest.raises(ValueError, match="BROWSER_TIME_PREPARATION_PLAN_MISMATCH"):
        prepare_time_variant(object(), variant="budget", user_id=1, profile_id=2)


def test_short_timing_fixture_has_no_unknown_variant_fallback():
    from scripts.browser_stand import prepare_time_variant
    with pytest.raises(ValueError, match="BROWSER_TIME_VARIANT_INVALID"):
        prepare_time_variant(object(), variant="unknown", user_id=1, profile_id=2)
