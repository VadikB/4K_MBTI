from collections import Counter
from copy import deepcopy
import json

import pytest

from Api import m5_functional_generation_service as service
from Api.m5_passport_generation import (
    ADDRESSED_RUNTIME, AS_PACKAGE, BANK_PACKAGE, build_event_material_delivery, provider_basis,
)
from Api.m5_runtime_rules import load_runtime_rule_package
from tests.passport_as_fixture import synthetic_as
from tests.unit.test_m5_passport_bank import CaptureGateway


@pytest.fixture(scope="module")
def cases():
    return {case["case_id"]: case for case in json.loads((BANK_PACKAGE / "case-package.json").read_bytes())["cases"]}


class Gateway(CaptureGateway):
    def __init__(self, *candidates, block_first=False):
        super().__init__("pass")
        self.candidates = iter(candidates)
        self.block_first = block_first

    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        routing, _, payload = self.calls[-1]
        if ":generation:" in routing:
            response.content = json.dumps(next(self.candidates), ensure_ascii=False)
        elif (self.block_first and ":tester:" in routing
              and payload["candidate_as"]["Название"] == "Синтетическая ситуация"):
            result = json.loads(response.content)
            for check in result["checks"]:
                if check["check_id"] == "common.confidentiality":
                    check.update(status="FAIL", findings=[{
                        "code": "SYNTHETIC_TITLE", "severity": "blocking",
                        "paths": ["candidate_as/Название"], "reason": "Синтетическая блокирующая находка.",
                        "requirement_ref": check["check_id"],
                    }])
            response.content = json.dumps(result, ensure_ascii=False)
        return response


def _snapshot(case, **kwargs):
    return service.build_passport_snapshot(case_version=case, profile={}, operation_id="event-materials",
                                           synthetic=True, **kwargs)


def _counts(gateway):
    return Counter("repair" if ":repair:" in route else route.split(":")[1] for route, _, _ in gateway.calls)


def _assert_review_identity(gateway, prepared):
    reviewers = [payload for route, _, payload in gateway.calls if ":generation:" not in route]
    for payload in reviewers:
        assert service.checksum(payload["candidate_as"]) == payload["candidate_checksum"]
    final = [payload for payload in reviewers if payload["candidate_checksum"] == prepared["candidate_checksum"]]
    assert final
    assert all(payload["candidate_as"] == prepared["candidate_as"] for payload in final)
    assert prepared["tester"]["reviewed_candidate_checksum"] == prepared["candidate_checksum"]


@pytest.mark.parametrize("proposal", ["start-ids", "omitted", "exact"])
def test_spec02_binds_start_only_materials_without_repair(cases, proposal, tmp_path):
    snapshot = _snapshot(cases["CASE.SPEC.02"])
    proposed = synthetic_as(provider_basis(snapshot))
    event = proposed["RuntimeBindings"]["E01_FACT"]
    if proposal == "start-ids":
        event["material_ids"] = proposed["Стартовые MaterialIDs"]
    elif proposal == "omitted":
        del event["material_ids"]
    gateway = Gateway(proposed)
    result = service.prepare(snapshot, gateway)
    assert result["tester"]["aggregation"]["status"] == "PASS"
    assert _counts(gateway) == {"generation": 1, "tester": 5, "challenger": 4}
    assembled = deepcopy(proposed)
    assembled["RuntimeBindings"]["E01_FACT"]["material_ids"] = []
    assert result["candidate_as"] == assembled
    assert result["repair"] is None
    _assert_review_identity(gateway, result)
    trace = service.build_persistence_trace(snapshot, result)
    assert trace["accepted_as"] == assembled
    changes = [{
        "path": "candidate_as/RuntimeBindings/E01_FACT/material_ids",
        "actual": event.get("material_ids"), "assembled": [],
    }]
    assert trace["author_content_binding"] == {
        "source": "frozen_input_snapshot.case_version.passport",
        "provider_candidate_checksum": service.checksum(proposed),
        "bound_candidate_checksum": service.checksum(assembled),
        "changed": proposal != "exact",
        **({"event_material_changes": changes} if proposal != "exact" else {}),
    }
    presentation = result["compiled_case"]["participant_presentation"]
    assert presentation["introduction"] == next(x["Текст"] for x in proposed["Материалы"] if x["MaterialID"] == "P00")
    assert [row["material_id"] for row in presentation["initial_materials"]] == [
        "M01", "M02", "M03", "M04", "M05", "M06",
    ]
    assert not result["execution_rules"]["cases"]["CASE.SPEC.02"]["materials"]
    (tmp_path / "delivery.json").write_text(json.dumps({
        "status": result["tester"]["aggregation"]["status"], "calls": _counts(gateway),
        "binding": trace["author_content_binding"],
        "reviewed_candidate_checksum": trace["tester"]["reviewed_candidate_checksum"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["tester"]["reviewed_candidate_checksum"] = "0" * 64
    with pytest.raises(ValueError, match="M5_FUNCTIONAL_REVIEWED_CANDIDATE_MISMATCH"):
        service.build_persistence_trace(snapshot, result)


def test_repair_uses_same_delivery_and_keeps_independent_blocker(cases, tmp_path):
    snapshot = _snapshot(cases["CASE.SPEC.02"])
    original = synthetic_as(provider_basis(snapshot))
    original["RuntimeBindings"]["E01_FACT"]["material_ids"] = original["Стартовые MaterialIDs"]
    revised = {**original, "Название": "Исправленный заголовок"}
    gateway = Gateway(original, revised, block_first=True)
    result = service.prepare(snapshot, gateway)
    assert _counts(gateway) == {"generation": 1, "tester": 10, "challenger": 8, "repair": 1}
    initial = result["repair"]["original_tester"]["aggregation"]
    assert initial["status"] == "FAIL"
    assert not initial["deterministic_failures"]
    assert [item["check_id"] for item in initial["blocking_failures"]] == ["common.confidentiality"]
    assert result["tester"]["aggregation"]["status"] == "PASS"
    assert result["candidate_as"]["Название"] == revised["Название"]
    assert result["candidate_as"]["RuntimeBindings"]["E01_FACT"]["material_ids"] == []
    generation_input = gateway.calls[0][2]
    repair_input = next(payload for route, _, payload in gateway.calls if ":repair:" in route)
    assert generation_input["event_material_delivery"] == repair_input["event_material_delivery"]
    assert repair_input["rejected_candidate_as"]["RuntimeBindings"]["E01_FACT"]["material_ids"] == []
    assert repair_input["blocking_failures"] == initial["blocking_failures"]
    _assert_review_identity(gateway, result)
    (tmp_path / "delivery.json").write_text(json.dumps({
        "status": result["tester"]["aggregation"]["status"], "calls": _counts(gateway),
        "initial_admission": initial, "binding": result["author_content_binding"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_spec01_assembles_fixed_condition_before_generation_and_repair_reviews(cases):
    snapshot = _snapshot(cases["CASE.SPEC.01"])
    original = synthetic_as(provider_basis(snapshot))
    document, reply = original["События"]
    condition = snapshot["event_material_delivery"]["events"]["E01_DOCUMENT"]["condition"]
    document["Условие запуска"] = "После вопроса о погоде."
    reply["Условие запуска"] = "После запроса о сроке."
    repaired = deepcopy(original)
    repaired["Название"] = "Исправленный заголовок"
    repaired["События"][0]["Условие запуска"] = condition
    repaired["События"][0]["Условие возникновения"] = document["Условие запуска"]
    gateway = Gateway(original, repaired, block_first=True)
    prepared = service.prepare(snapshot, gateway)

    assert _counts(gateway) == {"generation": 1, "tester": 8, "challenger": 8, "repair": 1}
    initial = prepared["repair"]["original_tester"]["aggregation"]
    assert initial["status"] == "FAIL"
    assert not initial["deterministic_failures"]
    assert [item["check_id"] for item in initial["blocking_failures"]] == ["common.confidentiality"]
    assert prepared["tester"]["aggregation"]["status"] == "PASS"
    for route, _, payload in gateway.calls:
        if ":generation:" not in route:
            events = payload["candidate_as"]["События"]
            assert events[0]["Условие запуска"] == condition
            assert "Условие возникновения" not in events[0]
            assert events[1] == reply
    _assert_review_identity(gateway, prepared)
    trace = service.build_persistence_trace(snapshot, prepared)
    assert trace["repair"]["original_author_content_binding"]["provider_candidate_checksum"] == service.checksum(original)
    assert trace["author_content_binding"]["provider_candidate_checksum"] == service.checksum(repaired)
    assert trace["author_content_binding"]["event_condition_changes"] == [{
        "path": "candidate_as/События/E01_DOCUMENT",
        "actual": {"Условие запуска": condition, "Условие возникновения": document["Условие запуска"]},
        "assembled": {"Условие запуска": condition},
    }]
    rules = prepared["execution_rules"]["cases"]["CASE.SPEC.01"]
    stage = next(row for row in rules["scenario"] if row["step_id"] == "E01_DOCUMENT")
    material = next(row for row in rules["materials"] if row["material_id"] == "M02")
    assert stage["condition"] == material["event_condition"]["text"] == condition


@pytest.mark.parametrize(("case_id", "event", "field", "actual", "expected", "reason"), [
    ("CASE.SPEC.02", "E01_FACT", "material_ids", ["M99"], [], "неизвестный MaterialID"),
    ("CASE.SPEC.02", "E01_FACT", "function", "material_update", "facilitator_action", "Тип действия"),
    ("CASE.SPEC.01", "E01_DOCUMENT", "material_ids", [], ["M02"], "обязательную выдачу"),
    ("CASE.SPEC.01", "E01_DOCUMENT", "material_ids", ["M02", "M02"], ["M02"], "повторяется"),
    ("CASE.SPEC.01", "E02_REPLY", "material_ids", ["M02"], [], "недоступен для выдачи"),
])
def test_real_binding_violation_remains_closed_after_repair(cases, case_id, event, field, actual, expected, reason):
    snapshot = _snapshot(cases[case_id])
    proposed = synthetic_as(provider_basis(snapshot))
    proposed["RuntimeBindings"][event][field] = actual
    gateway = Gateway(proposed, {**proposed, "Название": "Повтор реальной ошибки"})
    result = service.prepare(snapshot, gateway)
    verdict = result["tester"]["aggregation"]
    assert verdict["status"] == "FAIL"
    assert not result["admitted_for_participant"]
    assert result["compiled_case"] is None
    assert result["execution_rules"] is None
    assert not verdict["blocking_failures"]
    for reviewer in result["tester"]["independent_checks"].values():
        assert {row["status"] for row in reviewer if row["status"] != "NOT_APPLICABLE"} == {"PASS"}
    repair = next(payload for route, _, payload in gateway.calls if ":repair:" in route)
    path = f"candidate_as/RuntimeBindings/{event}/{field}"
    failure, = repair["deterministic_failures"]
    assert (failure["code"], failure["path"], failure["actual"], failure["expected"]) == (
        "runtime_event_binding", path, actual, expected,
    )
    assert reason in failure["reason"]
    assert verdict["deterministic_failures"] == [failure]
    assert result["candidate_as"]["RuntimeBindings"][event][field] == actual
    assert "event_material_changes" not in result["author_content_binding"]
    batches = 10 if case_id == "CASE.SPEC.02" else 8
    assert _counts(gateway) == {"generation": 1, "tester": batches, "challenger": 8, "repair": 1}


def test_flexible_delivery_diagnostic_reports_allowed_ids_and_condition(cases):
    case = cases["CASE.SPEC.01"]
    snapshot = _snapshot(case)
    snapshot["event_material_delivery"] = build_event_material_delivery(case, {})
    proposed = synthetic_as(provider_basis(snapshot))
    proposed["RuntimeBindings"]["E01_DOCUMENT"]["material_ids"] = ["UNKNOWN"]
    gateway = Gateway(proposed, synthetic_as(provider_basis(snapshot)))
    result = service.prepare(snapshot, gateway)
    repair = next(payload for route, _, payload in gateway.calls if ":repair:" in route)
    diagnostic = next(item for item in repair["deterministic_failures"] if item["code"] == "runtime_event_binding")
    rule = snapshot["event_material_delivery"]["events"]["E01_DOCUMENT"]
    assert diagnostic["path"] == "candidate_as/RuntimeBindings/E01_DOCUMENT/material_ids"
    assert diagnostic["actual"] == ["UNKNOWN"]
    assert diagnostic["allowed_material_ids"] == ["M02"]
    assert diagnostic["condition"] == rule["condition"]
    assert result["tester"]["aggregation"]["status"] == "PASS"
    assert result["candidate_as"]["События"] == proposed["События"]


@pytest.mark.parametrize(("package_dir", "package_version"), [("v1", "1.0.0"), ("v2", "2.0.0")])
def test_historical_contract_keeps_its_preparation_behavior(cases, package_dir, package_version):
    snapshot = _snapshot(cases["CASE.SPEC.02"], as_package=AS_PACKAGE.parent / package_dir)
    proposed = synthetic_as(provider_basis(snapshot))
    proposed["RuntimeBindings"]["E01_FACT"]["material_ids"] = proposed["Стартовые MaterialIDs"]
    gateway = Gateway(proposed, {**proposed, "Название": "Исторический повтор"})
    result = service.prepare(snapshot, gateway)
    assert snapshot["refs"]["as_contract"]["version"] == "1.0.0"
    assert snapshot["refs"]["protocol_package"]["version"] == package_version
    assert "event_material_delivery" not in provider_basis(snapshot)
    assert result["tester"]["aggregation"]["status"] == "FAIL"
    assert {row["code"] for row in result["tester"]["aggregation"]["deterministic_failures"]} == {
        "runtime_event_binding", "runtime_delayed_materials",
    }


def test_addressed_spec03_keeps_runtime_rule_and_reviewer_contracts(cases):
    package = load_runtime_rule_package(ADDRESSED_RUNTIME, list(cases.values()), expected_case_package_version="0.6")
    case_id = "CASE.SPEC.03"
    design = package["bindings"]["case_bindings"][case_id]["scenario_contract"]
    snapshot = _snapshot(cases[case_id], runtime_rule_ref={"version": "1.4.0", "scenario_contract": design})
    basis = provider_basis(snapshot)
    proposed = synthetic_as(basis)
    gateway = Gateway(proposed)
    result = service.prepare(snapshot, gateway)
    assert result["tester"]["aggregation"]["status"] == "PASS"
    assert result["candidate_as"] == proposed
    assert _counts(gateway) == {"generation": 1, "tester": 4, "challenger": 4}
    assert "event_material_delivery" not in basis
    assert result["execution_rules"]["cases"][case_id]["scenario_contract"] == design
    _assert_review_identity(gateway, result)
