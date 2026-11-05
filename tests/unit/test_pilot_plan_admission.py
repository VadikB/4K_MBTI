"""Synthetic contract/mutation checks, not a provider run or human Case review."""
from copy import deepcopy

import pytest

from Api.m5_case_runtime import checksum
from Api.assessment_programs import public_program
from Api.pilot_plan_admission import ROOT, build_snapshot, project_plan, validate_program, validate_snapshot

pytestmark = pytest.mark.unit
PACKAGE = ROOT / "assessment_definitions/planning/specialist_pilot_admission/v0.1"


def snapshot():
    return build_snapshot(PACKAGE)


def seal(value):
    value["snapshot_checksum"] = checksum({key: item for key, item in value.items() if key != "snapshot_checksum"})
    return value


def inputs(value):
    p = value["review"]["payload"]
    return dict(targets=p["full_m2_matrix"], catalog=[{
        "case_id": row["case_id"], "case_version": row["version"], "eligible": True,
        "target_ids": row["target_ids"], "reasons": [],
    } for row in p["cases"]], catalog_ref={
        "id": p["catalog_ref"]["catalog_id"], "version": p["catalog_ref"]["catalog_version"],
        "checksum": p["catalog_ref"]["manifest_checksum"], "m2_checksum": p["m2_checksum"],
    }, role_ref=p["role_refs"][0])


def program(value):
    p = deepcopy(value["review"]["payload"]["program"])
    p["version"] = "synthetic-next-version"
    p["source_refs_json"]["pilot_plan_admission"] = value
    return p


def test_approved_source_build_keeps_historical_review_and_does_not_activate_runtime():
    s = snapshot()
    p = validate_snapshot(s)
    assert p["runtime_authorization"] == "NONE"
    assert p["methodologist_approval"].startswith("PENDING")
    assert s["owner_decision"]["methodologist"]["status"] == "APPROVED_FOR_EXACT_PROPOSAL"
    assert s["owner_decision"]["runtime_authorization"] == "NONE"
    assert p["full_m2_count"] == 61 and len(p["proposed_target_ids"]) == 39
    assert len(p["absent_target_ids"]) == 22 and len(p["observation_occurrences"]) == 55
    p["full_m2_matrix"].clear()
    assert len(s["review"]["payload"]["full_m2_matrix"]) == 61


def test_exact_projection_keeps_full_m2_separate_and_approved_eight_case_order():
    s = snapshot()
    args = inputs(s)
    result = project_plan(s, **args)
    assert len(args["targets"]) == 61
    assert len(result["planned_targets"]) == 39 and len(result["outside_plan_target_ids"]) == 22
    assert [row["case_id"] for row in result["route"]] == [
        "CASE.SPEC.02", "CASE.SPEC.03", "CASE.SPEC.04", "CASE.SPEC.07",
        "CASE.SPEC.05", "CASE.SPEC.01", "CASE.SPEC.06", "CASE.SPEC.08"]
    assert "CASE.SPEC.09" not in {row["case_id"] for row in result["route"]}
    assert result["timing"] == {"time_budget_seconds": 7200, "calendar_window_seconds": 259200}


def test_public_program_projection_does_not_expose_internal_approval_or_observation_conditions():
    value = program(snapshot())
    original = deepcopy(value)
    result = public_program(value)
    assert result["source_refs_projection"] == "PUBLIC_REFS_NOT_EXECUTION_DEFINITION"
    assert result["pilot_plan_ref"]["snapshot_checksum"] == snapshot()["snapshot_checksum"]
    assert "pilot_plan_admission" not in result["source_refs_json"]
    assert value == original
    result["source_refs_json"]["methodology_version_id"] = -1
    assert value == original
    assert public_program(None) is None
    legacy = {"id": 3, "source_refs_json": {"methodology_version_id": 1}}
    assert public_program(legacy) == legacy
    assert public_program({"id": 4}) == {"id": 4}


@pytest.mark.parametrize("mutate", [
    lambda s: s.pop("snapshot_checksum"),
    lambda s: s["owner_decision"]["methodologist"].update(status="PENDING"),
    lambda s: s["owner_decision"]["productologist"].update(decision_ids=["P1"]),
    lambda s: s["owner_decision"].update(proposal_payload_checksum="0" * 64),
    lambda s: s["review"]["payload"]["proposed_target_ids"].pop(),
    lambda s: s["review"]["payload"]["full_m2_matrix"].pop(),
    lambda s: s["review"]["payload"]["proposed_primary_route"].reverse(),
    lambda s: s["review"]["payload"]["observation_occurrences"][0].update(observation_condition=""),
    lambda s: s["review"]["payload"]["observation_occurrences"][0].update(actual_opportunity="PRESENT"),
    lambda s: s["source_files"].update({next(iter(s["source_files"])): "0" * 64}),
])
def test_unknown_or_modified_snapshot_never_grants_admission(mutate):
    s = snapshot()
    mutate(s)
    # Even an accidental re-seal cannot repair the inner decision/review chain.
    if "snapshot_checksum" in s:
        seal(s)
    with pytest.raises(ValueError, match="PILOT_PLAN_"):
        validate_snapshot(s)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(version="1.1"),
    lambda p: p.update(assessment_configuration_id=999),
    lambda p: p.update(catalog_version_id=999),
    lambda p: p.update(assignment_ref="other"),
    lambda p: p["source_refs_json"].update(prompt_bundle_checksum="0" * 64),
])
def test_opt_in_needs_new_program_version_with_unchanged_sources(mutate):
    s = snapshot()
    p = program(s)
    assert validate_program(p, [2], s)
    mutate(p)
    with pytest.raises(ValueError, match="PILOT_PLAN_"):
        validate_program(p, [2], s)


@pytest.mark.parametrize("mutate", [
    lambda a: a["targets"].pop(),
    lambda a: a["targets"][0].update(m2_version="wrong"),
    lambda a: a["catalog_ref"].update(checksum="0" * 64),
    lambda a: a["catalog_ref"].update(m2_checksum="0" * 64),
    lambda a: a["catalog"].pop(),
    lambda a: a["catalog"][1].update(eligible=False),
    lambda a: a["catalog"][1]["target_ids"].pop(),
    lambda a: a["role_ref"].update(checksum="0" * 64),
])
def test_projection_rejects_unapproved_source_or_missing_planned_opportunity(mutate):
    s = snapshot()
    args = deepcopy(inputs(s))
    mutate(args)
    with pytest.raises(ValueError, match="PILOT_PLAN_"):
        project_plan(s, **args)
