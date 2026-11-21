import json
from copy import deepcopy

import pytest

from Api import m5_functional_generation_service as service
from Api.m5_addressed_contract import validate_scenario_contract
from Api.m5_passport_generation import ADDRESSED_RUNTIME, BANK_PACKAGE, provider_basis
from Api.m5_runtime_rules import load_runtime_rule_package
from tests.passport_as_fixture import synthetic_as
from tests.unit.test_m5_passport_bank import CaptureGateway


@pytest.fixture
def spec03():
    cases = json.loads((BANK_PACKAGE / "case-package.json").read_bytes())["cases"]
    rules = load_runtime_rule_package(ADDRESSED_RUNTIME, cases, expected_case_package_version="0.6")
    case = cases[2]
    binding = rules["bindings"]["case_bindings"][case["case_id"]]
    return case, binding["scenario_contract"]


def _snapshot(spec03):
    case, design = spec03
    return service.build_passport_snapshot(
        case_version=case, profile={}, operation_id="m5-02", synthetic=True,
        runtime_rule_ref={"version": "1.4.0", "scenario_contract": design},
    )


class ScenarioGateway(CaptureGateway):
    def __init__(self, candidates):
        super().__init__("pass")
        self.candidates = iter(candidates)

    def chat_with_trace(self, messages, **kwargs):
        reply = super().chat_with_trace(messages, **kwargs)
        if ":generation:" in kwargs["routing_key"]:
            reply.content = json.dumps(next(self.candidates), ensure_ascii=False)
        return reply


@pytest.mark.parametrize("variant", [0, 1])
def test_addressed_candidate_has_frozen_start_roles_and_event_references(spec03, variant):
    snapshot = _snapshot(spec03)
    basis = provider_basis(snapshot)
    design = basis["scenario_contract"]
    candidate = synthetic_as(basis, variant=variant)
    result = service.prepare(snapshot, ScenarioGateway([candidate]))
    assert result["admitted_for_participant"]
    case = result["compiled_case"]
    assert [row["material_id"] for row in case["materials"] if row["participant_visible_initially"]] == [
        "P00", "M01", "M02", "M03"
    ]
    assert [row["material_id"] for row in case["participant_presentation"]["initial_materials"]] == ["M01", "M02", "M03"]
    assert case["participant_presentation"]["introduction"] == candidate["Материалы"][0]["Текст"]
    assert candidate["Материалы"][-1]["Текст"] not in json.dumps(case["participant_presentation"], ensure_ascii=False)
    target = next(item for item in case["indicator_targets"] if item["indicator_id"] == "K2.I08")
    assert target["material_refs"] == ["M04"]
    assert target["event_refs"] == ["E01_UPDATE", "E02_TRANSFER"]
    rules = result["execution_rules"]["cases"][case["case_id"]]
    event = next(item for item in rules["materials"] if item["material_id"] == "M04")
    assert event["speaker_id"] == "COLLEAGUE_1"
    assert event["event_condition"]["text"] == design["events"]["E01_UPDATE"]["condition"]
    assert set(basis["requirements"]["required_top_level_fields_exact"]).isdisjoint(
        design["candidate_contract"]["sealed_fields"]
    )


@pytest.mark.parametrize("defect,path", [
    ("early", "Стартовые MaterialIDs"),
    ("binding", "RuntimeBindings"),
    ("event_refs", "IndicatorObservability/K2.I08/event_refs"),
    ("material_refs", "IndicatorObservability/K2.I08/material_refs"),
    ("leak", "Материалы/P00/Текст"),
])
def test_addressed_candidate_refuses_structural_damage_even_if_reviewers_pass(spec03, defect, path):
    snapshot = _snapshot(spec03)
    candidate = synthetic_as(provider_basis(snapshot))
    if defect == "early":
        candidate["Стартовые MaterialIDs"] = ["P00", "M01", "M02", "M03", "M04"]
    elif defect == "binding":
        candidate["RuntimeBindings"] = {"E01_UPDATE": {"material_ids": []}}
    elif defect in {"event_refs", "material_refs"}:
        next(row for row in candidate["IndicatorObservability"] if row["IndicatorID"] == "K2.I08")[defect] = []
    else:
        candidate["Материалы"][0]["Текст"] += " " + candidate["Материалы"][-1]["Текст"]
    gateway = ScenarioGateway([candidate, candidate])
    result = service.prepare(snapshot, gateway)
    assert not result["admitted_for_participant"]
    assert result["compiled_case"] is result["execution_rules"] is None
    assert f"candidate_as/{path}" in [error["path"] for error in result["deterministic_validation"]["errors"]]


def test_repaired_candidate_repeats_all_review_batches(spec03):
    snapshot = _snapshot(spec03)
    fixed = synthetic_as(provider_basis(snapshot))
    damaged = deepcopy(fixed)
    damaged["Стартовые MaterialIDs"] = ["P00", "M01", "M02", "M03", "M04"]
    gateway = ScenarioGateway([damaged, fixed])
    result = service.prepare(snapshot, gateway)
    assert result["admitted_for_participant"] and result["repair"]
    expected = result["tester"]["independent_checks"]
    for role in ("tester", "challenger"):
        batches = [payload for route, _, payload in gateway.calls
                   if f":{role}:" in route and payload["candidate_checksum"] == result["candidate_checksum"]]
        reviews = [(batch["applicability_plan"]["required_checks"] if role == "tester" else batch["protected_checks"])
                   for batch in batches]
        assert [row["check_id"] for batch in reviews for row in batch] == [
            row["check_id"] for row in expected[role] if row["status"] != "NOT_APPLICABLE"
        ]
        assert all(payload["scenario_contract"] == snapshot["scenario_contract"] for payload in batches)


def test_missing_binding_or_condition_refuses_preparation(spec03):
    case, design = spec03
    for field in ("material_ids", "condition"):
        broken = deepcopy(design)
        broken["events"]["E01_UPDATE"].pop(field)
        with pytest.raises(ValueError, match=f"events/E01_UPDATE/{field}"):
            validate_scenario_contract(case, broken)
