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


V6_PACKAGE = ROOT / "assessment_definitions/prompts/m5_functional_passport/v6"
CONSENT_CHECK = "invariant:CASE.SPEC.04.I06"
CONSENT_FIELD = "/candidate_as/RuntimeBindings/E01_CONSENT_STEP/reply_confirmation"
OBSERVATION_CHECK = "common.independent_observation"


@pytest.mark.parametrize(("location", "remove_field", "expected"), [
    (CONSENT_FIELD, False, "PASS"),
    ("/candidate_as/События/E01_CONSENT_STEP/reply_confirmation", False, "TECHNICAL_ERROR"),
    ("/candidate_as/CaseID", False, "TECHNICAL_ERROR"),
    (CONSENT_FIELD, True, "TECHNICAL_ERROR"),
])
def test_spec04_v6_advertises_exact_consent_field_to_both_reviewers(location, remove_field, expected):
    class ConsentGateway(PilotGateway):
        def review_response(self, routing, payload, checks):
            for row in checks:
                if row["check_id"] == CONSENT_CHECK:
                    row["evidence_paths"] = [location]
            return super().review_response(routing, payload, checks)

    frozen = snapshot(4, package=V6_PACKAGE)
    gateway = ConsentGateway()
    generated = service.generate(frozen, gateway)
    if remove_field:
        del generated["candidate_as"]["RuntimeBindings"]["E01_CONSENT_STEP"]["reply_confirmation"]
        generated["candidate_checksum"] = service.checksum(generated["candidate_as"])
    reviewed = service.test_candidate(frozen, generated, gateway)
    for role, rows in reviewed["independent_checks"].items():
        row = next(row for row in rows if row["check_id"] == CONSENT_CHECK)
        assert row["status"] == expected
        if expected == "TECHNICAL_ERROR":
            assert [error["code"] for error in row["protocol_errors"]] == ["REVIEW_EVIDENCE_REQUIRED"]
        payload = next(payload for _, _, payload in gateway.calls if payload.get("review_dispatch", {}).get("reviewer") == role
                       and CONSENT_CHECK in payload["review_dispatch"]["check_ids"])
        definitions = payload["protected_checks"] if role == "challenger" else payload["applicability_plan"]["required_checks"]
        criterion = next(item for item in definitions if item["check_id"] == CONSENT_CHECK)
        assert CONSENT_FIELD.lstrip("/") in criterion["finding_evidence_sections"]
        assert CONSENT_FIELD in criterion["requirement"]["case_content"]
    frozen_v5 = v5_snapshot(4)
    rule_v5 = next(row for row in frozen_v5["applicability_plan"]["required_checks"] if row["check_id"] == CONSENT_CHECK)
    assert CONSENT_FIELD.lstrip("/") not in rule_v5["finding_evidence_sections"]


@pytest.mark.parametrize(("mode", "status", "repair_count"), [
    ("full", "PASS", 0),
    ("missing", "INCOMPLETE", 0),
    ("mixed_fixed", "PASS", 1),
    ("mixed_blocked", "FAIL", 1),
])
def test_spec02_explicit_batch_and_independent_blocker(mode, status, repair_count):
    blocker_path = "/candidate_as/Материалы/M06/Текст"

    class ObservationGateway(PilotGateway):
        def chat_with_trace(self, messages, **kwargs):
            response = super().chat_with_trace(messages, **kwargs)
            routing = kwargs["routing_key"]
            if ":generation:" in routing and mode.startswith("mixed"):
                candidate = json.loads(response.content)
                material = next(row for row in candidate["Материалы"] if row["MaterialID"] == "M06")
                if ":generation:repair:" not in routing or mode == "mixed_blocked":
                    material["Текст"] = "Правильный вывод уже дан. Подтвердите его."
                response.content = json.dumps(candidate, ensure_ascii=False)
            return response

        def review_response(self, routing, payload, checks):
            dispatch = payload["review_dispatch"]
            first = dispatch["round"] == 1
            for row in checks:
                if row["check_id"] != OBSERVATION_CHECK:
                    continue
                if dispatch["reviewer"] == "challenger" and first and mode != "full":
                    checks = [item for item in checks if item["check_id"] != OBSERVATION_CHECK]
                elif dispatch["reviewer"] == "tester" and any(
                        material["MaterialID"] == "M06" and "Правильный вывод уже дан" in material["Текст"]
                        for material in payload["candidate_as"]["Материалы"]):
                    row.update(status="FAIL", reason="M06 предрешает вывод оцениваемого.", findings=[{
                        "code": "PREDETERMINED_CONCLUSION",
                        "severity": "blocking",
                        "paths": [blocker_path],
                        "reason": "Готовый вывод в M06 лишает участника самостоятельного анализа.",
                        "requirement_ref": OBSERVATION_CHECK,
                    }])
            return super().review_response(routing, payload, checks)

    frozen = snapshot(2, package=V6_PACKAGE)
    gateway = ObservationGateway()
    prepared = service.prepare(frozen, gateway)
    assert prepared["tester"]["aggregation"]["status"] == status
    assert prepared["admitted_for_participant"] is (status == "PASS")
    repairs = [payload for routing, _, payload in gateway.calls if ":generation:repair:" in routing]
    assert len(repairs) == repair_count
    by_round = {}
    for routing, _, payload in gateway.calls:
        if "review_dispatch" not in payload:
            continue
        dispatch = payload["review_dispatch"]
        definitions = (payload["protected_checks"] if dispatch["reviewer"] == "challenger"
                       else payload["applicability_plan"]["required_checks"])
        assert payload["review_dispatch"]["check_ids"] == [item["check_id"] for item in definitions]
        assert "applicability_plan" not in payload["required_output"]["checks"][0]["check_id"]
        by_round.setdefault(dispatch["round"], set()).add(service.checksum(payload["candidate_as"]))
    assert by_round[1] == {prepared["repair"]["original_candidate_checksum"] if repair_count else prepared["candidate_checksum"]}
    original = prepared["repair"]["original_tester"] if repair_count else prepared["tester"]
    omissions = original["aggregation"]["incomplete_checks"]
    if mode != "full":
        missing, = omissions
        assert (missing["reviewer"], missing["check_id"], missing["status"], missing["batch_no"]) == (
            "challenger", OBSERVATION_CHECK, "NOT_RUN", 1,
        )
        assert missing["operation_id"] == original["challenger_operation"]["batches"][0]["operation_id"]
        assert missing["candidate_checksum"] in by_round[1]
    if repair_count:
        assert by_round[2] == {prepared["candidate_checksum"]}
        assert by_round[1].isdisjoint(by_round[2])
        blocking, = repairs[0]["blocking_failures"]
        assert blocking["reviewer"] == "tester"
        assert blocking["check_id"] == OBSERVATION_CHECK
        material_index = next(i for i, row in enumerate(repairs[0]["rejected_candidate_as"]["Материалы"])
                              if row["MaterialID"] == "M06")
        assert blocking["findings"][0]["paths"] == [f"/candidate_as/Материалы/{material_index}/Текст"]
        assert not prepared["tester"]["aggregation"]["incomplete_checks"]
        if mode == "mixed_blocked":
            assert not prepared["compiled_case"]
    if status == "PASS":
        trace = service.build_persistence_trace(frozen, prepared)
        from Api.assessment_start_readiness import functional_gate

        functional_gate(trace, operation_id=frozen["operation_id"])
