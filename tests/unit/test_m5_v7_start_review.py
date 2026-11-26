"""Replay v7 hand-offs against the exact published pilot cases with a controlled gateway."""
from copy import deepcopy
import json

import pytest

from Api.assessment_start_readiness import functional_gate
from Api.cycle_execution_manifest import BATTERY_V04_SCENARIO_CURRENT, M5_BATTERY_PILOT_REVIEW_PACKAGES, ROOT
from Api.m5_functional_generation_service import build_passport_snapshot, build_persistence_trace, checksum, prepare
from Api.m5_functional_tester import load_protocol
from Api.m5_passport_generation import AS_PACKAGE
from scripts.release_specialist_pilot import RELEASE_DIR, load_release, release_materials
from tests.integration.test_m5_battery_v04_db import V04Gateway


pytestmark = pytest.mark.unit


class ChallengerWarning(V04Gateway):
    def review_response(self, routing, payload, checks):
        for row in checks:
            if ":challenger:" in routing and row["check_id"] == "quality.clarity":
                row.update(status="FAIL", reason="Синтетическое редакционное замечание", findings=[{
                    "code": "CLARITY_EDITORIAL", "severity": "non_blocking", "requirement_ref": "quality.clarity",
                    "reason": "Формулировку можно упростить без изменения задания.", "paths": row["evidence_paths"][:1],
                }])
        return super().review_response(routing, payload, checks)


@pytest.fixture(scope="module")
def pilot_cases():
    package, bank, _, _ = release_materials(load_release(RELEASE_DIR)[1])
    return {int(case["case_id"].split(".")[-1]): case for case in package["cases"]}, bank


def prepare_trace(pilot_cases, number, gateway):
    cases, bank = pilot_cases
    operation_id = f"v7-regression-{number}"
    snapshot = build_passport_snapshot(
        case_version=cases[number], operation_id=operation_id, synthetic=True, battery_pilot=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"],
        battery_scenario_package=ROOT / BATTERY_V04_SCENARIO_CURRENT,
        package_ref={"id": bank["id"], "version": bank["version"]},
        profile={"user_context": {
            "regular_tasks": ["Сверяю рабочие предложения и готовлю рекомендации."],
            "additional_information": {"professional_recommendation": {"confirmed": True, "basis": "Синтетический тест"}},
        }},
    )
    generated = prepare(snapshot, gateway)
    trace = build_persistence_trace(snapshot, generated)
    # JSON round-trip follows how TEST stores already prepared candidates.
    return operation_id, json.loads(json.dumps(trace))


@pytest.mark.parametrize("number", range(1, 10))
def test_v7_challenger_completes_the_same_applicable_checks_as_tester(pilot_cases, number):
    operation_id, trace = prepare_trace(pilot_cases, number, V04Gateway())
    tester = trace["tester"]
    assert tester["aggregation"]["status"] == "PASS"
    sent = {name: [check for batch in tester[name]["batches"] for check in batch["required_check_ids"]]
            for name in ("provider_operation", "challenger_operation")}
    assert sent["provider_operation"] == sent["challenger_operation"]
    assert "quality.clarity" in sent["challenger_operation"]
    if number in (2, 3):
        assert len(sent["challenger_operation"]) == {2: 22, 3: 21}[number]
    functional_gate(trace, operation_id=operation_id)


@pytest.fixture(scope="module")
def warning_trace(pilot_cases):
    return prepare_trace(pilot_cases, 2, ChallengerWarning())


def test_v7_pass_with_challenger_warning_uses_independent_results(warning_trace):
    operation_id, trace = warning_trace
    saved = trace["tester"]["aggregation"]
    assert saved["status"] == "PASS_WITH_WARNINGS"
    assert [(item["reviewer"], item["check_id"]) for item in saved["warnings"]] == [("challenger", "quality.clarity")]
    functional_gate(trace, operation_id=operation_id)


def test_v7_package_cannot_fall_back_to_archived_review(pilot_cases):
    operation_id, trace = prepare_trace(pilot_cases, 2, V04Gateway())
    tester = trace["tester"]
    # Simulate a hand-off claiming the historical result format for a v7 package.
    historical = load_protocol(AS_PACKAGE.with_name("v3") / "tester-protocol.json")
    tester["protocol"] = {key: historical[key] for key in ("id", "version", "checksum")}
    tester.pop("review_source")
    with pytest.raises(ValueError, match="PILOT_PLAN_REVIEW_PROTOCOL_MISMATCH"):
        functional_gate(trace, operation_id=operation_id)
    trace["source_snapshot"]["refs"].pop("battery_scenario")
    with pytest.raises(ValueError, match="PILOT_PLAN_REVIEW_SOURCE_MISMATCH"):
        functional_gate(trace, operation_id=operation_id)


@pytest.mark.parametrize("mutation", ["absent", "duplicate", "foreign", "foreign_operation", "role", "version", "sha"])
def test_v7_cannot_admit_incomplete_or_unbound_role_results(warning_trace, mutation):
    operation_id, trace = deepcopy(warning_trace)
    tester = trace["tester"]
    records = tester["independent_checks"]["challenger"]
    batches = tester["challenger_operation"]["batches"]
    if mutation in {"absent", "duplicate", "foreign"}:
        # Change the normalized result and receipt together. The expected IDs
        # must still come from the server, even if both stored lists agree.
        batch = batches[-1]
        ids = batch["required_check_ids"]
        row = records[-1]
        assert row["check_id"] == ids[-1]
        if mutation == "absent":
            records.pop()
            ids.pop()
        elif mutation == "duplicate":
            records.append(deepcopy(row))
            ids.append(row["check_id"])
        else:
            row["check_id"] = ids[-1] = "unrequested-review-id"
        batch["calls"][-1]["review_dispatch"]["check_ids"] = list(ids)
        expected = "PILOT_PLAN_REQUIRED_CHECKS_MISSING"
    elif mutation == "foreign_operation":
        operation_id = "another-preparation"
        expected = "PILOT_PLAN_REVIEW_DISPATCH_MISMATCH"
    else:
        key, value = {"role": ("reviewer", "tester"), "version": ("as_version", "foreign-version"),
                      "sha": ("candidate_checksum", "0" * 64)}[mutation]
        records[-1][key] = value
        expected = "PILOT_PLAN_REVIEW_RESULTS_MISMATCH"
    with pytest.raises(ValueError, match=expected):
        functional_gate(trace, operation_id=operation_id)


def test_v7_repair_uses_only_terminal_candidate_and_review_round(pilot_cases):
    operation_id, trace = prepare_trace(pilot_cases, 7, V04Gateway(initial="Неверная форма", repaired=[]))
    assert trace["repair"]["original_candidate_checksum"] != trace["candidate_checksum"]
    functional_gate(trace, operation_id=operation_id)
    wrong_round = deepcopy(trace)
    wrong_round["tester"]["challenger_operation"]["batches"][0]["calls"][-1]["review_dispatch"]["round"] = 1
    with pytest.raises(ValueError, match="PILOT_PLAN_REVIEW_DISPATCH_MISMATCH"):
        functional_gate(wrong_round, operation_id=operation_id)
    trace["accepted_as"]["AssessmentSituationID"] = "foreign-situation"
    trace["candidate_checksum"] = checksum(trace["accepted_as"])
    with pytest.raises(ValueError, match="PILOT_PLAN_REVIEW_CANDIDATE_MISMATCH"):
        functional_gate(trace, operation_id=operation_id)
