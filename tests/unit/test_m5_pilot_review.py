"""Versioned reviewer dispatch, references and validation before semantic review."""
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from Api import m5_functional_generation_service as service
from Api.cycle_execution_manifest import M5_BATTERY_PILOT_REVIEW_PACKAGE, ROOT
from Api.m5_functional_tester import SERVER_BOUND_PROTOCOL, normalize_results
from tests.unit.test_m5_battery_review import PreparationGateway, snapshot
from tests.integration.test_m5_battery_scenario_db import synthetic_as


class PilotGateway(PreparationGateway):
    def __init__(self, *, initial=None, repaired=None, change_dispatch=None):
        super().__init__("pass")
        self.initial = initial
        self.repaired = repaired
        self.change_dispatch = change_dispatch

    def chat_with_trace(self, messages, **kwargs):
        routing = kwargs["routing_key"]
        payload = json.loads(messages[-1]["content"])
        self.calls.append((routing, deepcopy(messages), payload))
        if ":generation:" in routing:
            generated = synthetic_as(payload)
            replacement = self.repaired if ":repair:" in routing else self.initial
            if replacement is not None:
                generated["Применённые замены"] = replacement
            return SimpleNamespace(content=json.dumps(generated), sent={"messages": messages}, provider={})
        result = self.review(routing, payload)
        sent = deepcopy(messages)
        if self.change_dispatch is not None:
            dispatch = json.loads(sent[-1]["content"])
            dispatch["review_dispatch"].update(self.change_dispatch)
            sent[-1]["content"] = json.dumps(dispatch)
        result.sent["messages"] = sent
        return result

    def review_response(self, routing, payload, checks):
        assert "candidate_checksum" not in payload["required_output"]
        assert "candidate_checksum" not in payload
        # A stored legacy body can carry a truncated echo. It is not trusted.
        return SimpleNamespace(content=json.dumps({"candidate_checksum": "short", "checks": checks}),
                               sent={}, provider={})


def v5_snapshot(case=9):
    return snapshot(case, package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGE)


@pytest.mark.parametrize("stale_context", [
    {"reviewer": "another-role"}, {"round": 0}, {"operation_id": "wrong-operation"}, {"batch_no": 80},
])
def test_wrong_sent_request_is_not_admitted(stale_context):
    result = service.prepare(v5_snapshot(), PilotGateway(change_dispatch=stale_context))
    assert result["tester"]["aggregation"]["status"] == "INCOMPLETE"
    assert not result["admitted_for_participant"]
    checks = result["tester"]["aggregation"]["incomplete_checks"]
    assert {row["protocol_errors"][0]["code"] for row in checks} == {"REVIEW_DISPATCH_MISMATCH"}


def test_short_echo_is_ignored_only_for_the_bound_dispatch():
    frozen = v5_snapshot()
    gateway = PilotGateway()
    prepared = service.prepare(frozen, gateway)
    assert prepared["admitted_for_participant"]
    trace = service.build_persistence_trace(frozen, prepared)
    from Api.assessment_start_readiness import functional_gate

    functional_gate(trace, operation_id=frozen["operation_id"])
    batch = trace["tester"]["provider_operation"]["batches"][0]
    assert batch["calls"][0]["review_dispatch"]["candidate_sha256"] == prepared["candidate_checksum"]
    batch["calls"][0]["review_dispatch"]["round"] = 0
    with pytest.raises(ValueError, match="PILOT_PLAN_REVIEW_DISPATCH_MISMATCH"):
        functional_gate(trace, operation_id=frozen["operation_id"])


@pytest.mark.parametrize("repaired,admitted", [
    ([], True),
    ([{"Место": "17.2/M01", "Источник": "M4", "Что заменено": "Контекст задачи", "Предел": "Граница сохранена"}], True),
    (["Повторная ошибка формы"], False),
    ("Повторный абзац", False),
])
def test_structural_failure_reaches_repair_before_either_reviewer(repaired, admitted):
    gateway = PilotGateway(initial="Абзац вместо массива", repaired=repaired)
    result = service.prepare(v5_snapshot(), gateway)
    assert result["admitted_for_participant"] is admitted
    assert len(gateway.calls) > 2 if admitted else len(gateway.calls) == 2
    repair_request = gateway.calls[1][2]
    assert gateway.calls[1][0].split(":")[2] == "repair"
    assert repair_request["deterministic_failures"][0]["path"] == "candidate_as/Применённые замены"
    assert repair_request["deterministic_failures"][0]["actual"] == "str"
    assert repair_request["deterministic_failures"][0]["expected"]["type"] == "array"
    assert result["repair"]["original_tester"]["review_skipped"] == "INVALID_CANDIDATE_STRUCTURE"
    if admitted:
        assert all(payload["review_dispatch"]["round"] == 2 for _, _, payload in gateway.calls[2:])


@pytest.mark.parametrize("address,expected", [
    ("candidate_as/Материалы[0].Текст", "PASS"),
    ("/candidate_as/Материалы/0/Текст", "PASS"),
    ("candidate_as/Материалы/M01/Текст", "PASS"),
    ("candidate_as/Материалы/M02/Текст", "TECHNICAL_ERROR"),
    ("candidate_as/Материалы/M03/Текст", "TECHNICAL_ERROR"),
    ("candidate_as/Материалы/M01/Отсутствует", "TECHNICAL_ERROR"),
    ("candidate_as/Материалы/M01/MaterialID", "TECHNICAL_ERROR"),
])
def test_reviewer_addresses_must_exist_and_support_the_current_criterion(address, expected):
    plan = {
        "protocol": {"scope": "battery_v0.3_qa", "version": SERVER_BOUND_PROTOCOL},
        "required_checks": [{"check_id": "one", "mandatory": True, "protected": True,
                             "finding_evidence_sections": ["candidate_as/Материалы/M01"]}],
        "not_applicable_checks": [],
    }
    candidate = {"Материалы": [
        {"MaterialID": "M01", "Текст": "Основание"},
        {"MaterialID": "M02", "Текст": "Другая ситуация"},
        {"MaterialID": "M03", "Текст": "Одна строка"},
        {"MaterialID": "M03", "Текст": "Другая строка"},
    ]}
    raw = {"check_id": "one", "status": "PASS", "evidence_paths": [address],
           "adversarial_review": {"candidate_conflicts": [], "resolution": "Сопоставлено основание."}}
    assert normalize_results(plan, [raw], candidate_as=candidate)[0]["status"] == expected
    assert normalize_results(plan, [], candidate_as=candidate, reviewer="challenger")[0]["reason"].startswith("Challenger")
    raw["adversarial_review"]["resolution"] = ""
    assert normalize_results(plan, [raw], candidate_as=candidate)[0]["status"] == "TECHNICAL_ERROR"
