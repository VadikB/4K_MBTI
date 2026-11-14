"""Test-only upstream plan-policy substitution; real AS/start checks remain.

Old static component fixtures are NOT an accepted pilot plan. This module is
never imported by main or Api. Full PATH/real-provider runners must not load it.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "browser-component-plan-boundary/1"


def validate_activation(state, env):
    if not (
        state.get("component_plan_fixture") == FIXTURE
        and state.get("gateway") == 1
        and state.get("provider_mode", "disabled") == "disabled"
        and not state.get("path29_full_path")
        and state.get("path29_program_source") is None
        and env.get("AGENT4K_ISOLATED_STAND") == "1"
        and env.get("AGENT4K_COMPONENT_PLAN_FIXTURE") == FIXTURE
        and env.get("DB_NAME") == state.get("database")
        and str(state.get("database", "")).startswith("product4k_pytest_")
        and env.get("AGENT4K_STAND_MARKER") == state.get("owner_marker")
        and str(state.get("owner_marker", "")).startswith("stand-10.2:")
    ):
        raise RuntimeError("COMPONENT_PLAN_FIXTURE_REQUIRES_DISABLED_PROVIDER_OWNED_STAND")


def load_policy():
    policy = json.loads((ROOT / "tests/browser/fixtures/component-plan-boundary-v1.json").read_bytes())
    cases = {}
    for ref in policy["sources"]:
        data = (ROOT / ref["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise ValueError("COMPONENT_PLAN_FIXTURE_SOURCE_CHANGED")
        source = json.loads(data)
        for row in source.get("cases", [source]):
            if row["case_id"] in ref["case_ids"]:
                cases[(row["case_id"], row["version"])] = row
    return policy, cases


def component_plan_gate(content, cycle, *, real_gate):
    try:
        return real_gate(content, cycle)
    except ValueError as error:
        if str(error) not in {"PILOT_PLAN_PLANNED_TARGET_GAP", "PILOT_PLAN_APPROVED_BINDING_REQUIRED"}:
            raise
        # Only the exact legacy static fixtures receive a synthetic upstream
        # plan-policy input. Never authorize an arbitrary LIMITED or opt-in plan.
        policy, cases = load_policy()
        catalog = content.get("catalog_ref") or {}
        if (content.get("pilot_plan_binding") is not None or content.get("schema_version") != 1
                or content.get("status") != "LIMITED" or not content.get("route")
                or any(catalog.get(key) != value for key, value in policy["catalog"].items())):
            raise error
        covered = set()
        for row in content["route"]:
            case = cases.get((row["case_id"], row["case_version"]))
            if (case is None or row.get("eligible") is not True
                    or set(row["target_ids"]) != {item["indicator_id"] for item in case["indicator_targets"]}):
                raise error
            covered.update(row["target_ids"])
        # Validate all remaining plan invariants using the real pure gate with
        # the upstream policy boundary projected to the fixture's covered set.
        # No stored plan, full M2, checksum, AS, timer or admission is rewritten.
        projected = deepcopy(content)
        projected["full_target_set"] = [row for row in content["full_target_set"] if row["indicator_id"] in covered]
        projected["planned_target_set"] = projected["full_target_set"]
        projected.update(status="READY", uncovered_target_ids=[])
        projected_cycle = {**cycle, "target_set_json": [
            {key: row[key] for key in ("indicator_id", "m2_version")} for row in projected["full_target_set"]]}
        return real_gate(projected, projected_cycle)


def install(state):
    validate_activation(state, os.environ)
    from scripts.test_stand import owned
    with owned(state):
        pass
    from Api import assessment_start_readiness
    from Api import acquaintance
    from tests.legacy_acquaintance_fixture import legacy_readiness
    acquaintance.early_readiness = legacy_readiness
    original = assessment_start_readiness.plan_gate
    assessment_start_readiness.plan_gate = lambda content, cycle: component_plan_gate(
        content, cycle, real_gate=original)
    print("SYNTHETIC_COMPONENT_PLAN_BOUNDARY: NOT_HUMAN_REVIEW NOT_PILOT_ADMISSION NOT_FULL_PATH", flush=True)
    print("SYNTHETIC_LEGACY_ACQUAINTANCE_BOUNDARY: NOT_REMAIN04_WAITING_OR_ASSIGNMENT_PROOF", flush=True)


def create_app():
    state = json.loads(Path(os.environ["STAND_STATE"]).read_bytes())
    install(state)
    from main import app
    @app.get('/__pytest__/execution-export/{cycle_id}')
    def execution_export(cycle_id: str):
        from tests.assessment_execution_export import execution_export as readback
        return readback(cycle_id)
    return app
