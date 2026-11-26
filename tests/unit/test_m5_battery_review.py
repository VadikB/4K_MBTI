"""Plan 03 and paired reviewer responses against one assembled AS."""
from copy import deepcopy
import json

import pytest

from Api import m5_functional_generation_service as service
from Api.assessment_start_readiness import functional_gate
from Api.cycle_execution_manifest import BATTERY_CASE_PACKAGE, M5_BATTERY_REVIEW_PACKAGE, ROOT
from Api.m5_battery_contract import RULE_PACKAGE
from Api.m5_functional_tester import aggregate, normalize_results
from Api.m5_passport_generation import AS_PACKAGE, CURRENT_AS_PACKAGE, load_bank_case
from tests.integration.test_m5_battery_scenario_db import PreparationGateway, reference


def snapshot(number, *, package=ROOT / M5_BATTERY_REVIEW_PACKAGE):
    case, bank = load_bank_case(reference(number)[0], ROOT / BATTERY_CASE_PACKAGE)
    profile = {"user_context": {
        "regular_tasks": ["Сверяю методы обработки рабочих записей"],
        "additional_information": {"professional_recommendation": {"confirmed": True, "basis": "Тестовый профиль"}},
    }}
    return service.build_passport_snapshot(
        case_version=case, profile=profile, operation_id=f"review-03-{number}", synthetic=True,
        as_package=package, battery_scenario_package=ROOT / RULE_PACKAGE, package_ref=bank,
    )


def test_resolve_all_nine_before_gateway():
    counts = []
    for number in range(1, 10):
        frozen = snapshot(number)
        plan, case = frozen["applicability_plan"], frozen["case_version"]
        v12 = case["passport"]
        counts.append(len(plan["indicator_descriptors"]))
        assert plan["case_ref"]["checksum"] == frozen["refs"]["case"]["case_version_checksum"]
        assert plan["case_ref"]["passport"] == case["passport_source"]
        assert plan["risk_context"]["risks"] == v12["21 Риски невалидной реализации"]
        ids = {item["check_id"] for item in plan["required_checks"]}
        assert not any(key.startswith(("risk:", "critical_prohibition:")) for key in ids)
        assert {f"invariant:{row['InvariantID']}" for row in v12["16 Инвариантное ядро"]} <= ids
        checks = {row["source_ref"]["indicator_id"]: row for row in plan["required_checks"]
                  if row["category"] == "indicator_observability" and row["check_id"].startswith("indicator:")}
        assert set(checks) == set(v12["22 IndicatorIDs"]["Точный перечень"])
        for row in v12["22 IndicatorIDs"]["Проектные условия"]:
            check = checks[row["IndicatorID"]]
            definition = check["requirement"]
            definition = definition.get("passport_or_protocol", definition)
            assert definition["opportunity"] == row["Условие возникновения"]
            assert definition["locations"] == row["Место в сценарии"]
            assert definition["observable_form"] == row["Доступная форма проявления"]
            assert definition["validity_risk"] == row["Риск потери"]
            target = next(t for t in case["indicator_targets"] if t["indicator_id"] == row["IndicatorID"])
            assert check["source_ref"]["m2"] == target["normative_source"]
            assert check["source_ref"]["locations"][0] == target["source"]
        design = frozen["battery_scenario"]
        assert {row["id"] for row in design["events"]} == {row["ID"] for row in v12["17 Сценарий Dialogue"]["17.3 Правила реакции и событий"]}
        assert len(plan["required_checks"]) <= len(snapshot(number, package=CURRENT_AS_PACKAGE)["applicability_plan"]["required_checks"])
    assert counts == [4, 9, 9, 7, 6, 5, 6, 4, 5]
    spec02 = {c["check_id"]: c for c in snapshot(2)["applicability_plan"]["required_checks"]}
    assert "выборка является существенным условием" in spec02["invariant:CASE.SPEC.02.I05"]["requirement"]["case_content"]
    assert "сообщении коллеге или черновике заказчику" in spec02["indicator:K1.I09"]["requirement"]["case_content"]



def test_replay_spec02_challenger_009_requires_five_resolutions():
    # Exact stored response from the synthetic SPEC.02 v0.6 admission on 2026-11-24.
    recorded = json.loads(
        (ROOT / "tests/fixtures/m5/spec02-challenger-009-response.txt").read_text(encoding="utf-8")
    )
    check_ids = (
        "indicator:K4.I13", "indicator:K4.I14", "indicator:K4.I16", "indicator:K4.I17",
        "indicator:K1.I06", "indicator:K1.I09", "critical_prohibition:01", "critical_prohibition:02",
    )
    plan = {
        "required_checks": [{"check_id": check_id, "mandatory": True, "protected": True}
                            for check_id in check_ids],
        "not_applicable_checks": [],
    }
    candidate_checksum = "6dd4ebfd727a9bbaaa9bf0d865b66867500e7c4cac4fa564031982e1639880dc"
    deterministic = {"status": "PASS", "checks": [{"result": "PASS"}]}
    resolutions = {
        "indicator:K4.I16": (
            "M01 задаёт четыре независимых требования. M02 и M03 различают плановый и подтверждённый "
            "срок A, M04 отдельно описывает план B. Эти сведения позволяют сравнить A и B по требованиям M01."
        ),
        "indicator:K4.I17": (
            "M03 подтверждает ручной этап и срок A от восьми дней. M04 помечает срок и охват B как плановые. "
            "Участник может отдельно оценить риск задержки A и риск неподтверждённого результата B."
        ),
        "indicator:K1.I06": (
            "P00 задаёт две письменные задачи, M01 отделяет требования заказчика, а M05 ограничивает "
            "доказательство выборкой. Участник может выбрать факты, относящиеся к задаче, и указать границы вывода."
        ),
        "critical_prohibition:01": (
            "M01 задаёт срок, охват, критерии и подтверждённый объём. Условия A в M02–M03 и B в M04–M05 "
            "описывают те же параметры без ценового преимущества как основания выбора."
        ),
        "critical_prohibition:02": (
            "M04 обозначает охват B в 40 заявок как план. M05 подтверждает данные по 12 заявкам и "
            "явно ограничивает вывод выборкой. Пригодность B на весь охват остаётся открытой."
        ),
    }

    original = service._bound_batch_checks(recorded, plan["required_checks"], candidate_checksum)
    assert [row["check_id"] for row in original] == list(check_ids)
    assert all(row["status"] == "PASS" and row["reason"] for row in original)
    assert {row["check_id"] for row in original if not row["adversarial_review"]["resolution"]} == set(resolutions)
    before = aggregate(deterministic, normalize_results(plan, original))
    assert before["status"] == "INCOMPLETE"
    assert not before["admitted_for_participant"]
    assert {row["check_id"]: row["status"] for row in before["incomplete_checks"]} == dict.fromkeys(
        resolutions, "TECHNICAL_ERROR",
    )

    control = deepcopy(recorded)
    for row in control["checks"]:
        if row["check_id"] in resolutions:
            assert row["adversarial_review"] == {"candidate_conflicts": [], "resolution": ""}
            row["adversarial_review"]["resolution"] = resolutions[row["check_id"]]
    corrected = service._bound_batch_checks(control, plan["required_checks"], candidate_checksum)
    after = aggregate(deterministic, normalize_results(plan, corrected))
    assert after["status"] == "PASS"
    assert after["admitted_for_participant"]
    assert after["verification_errors"] == []


class PairedGateway(PreparationGateway):
    first = "candidate_as/Материалы/M01/Текст"
    second = "candidate_as/Материалы/M05/Текст"
    criterion = "common.professional_consistency"

    def review_response(self, routing, payload, checks):
        tester = ":tester:" in routing
        check = next((item for item in checks if item["check_id"] == self.criterion), None)
        if check is None:
            return super().review_response(routing, payload, checks)
        if self.mode in {"synonyms", "shared_word"}:
            reasons = (
                ("«Рабочая запись» и «карточка» относятся к одному объекту.",
                 "Смысл совпадает. Оба источника описывают карточку поставки.")
                if self.mode == "synonyms" else
                ("Один срок относится к подготовке, другой к подтверждению.",
                 "Слово «срок» различимо по этапу. Проверка и готовность разделены.")
            )
            check.update(evidence_paths=[self.first, self.second], reason=reasons[not tester])
            check["adversarial_review"] = {
                "candidate_conflicts": [self.first, self.second], "resolution": reasons[not tester],
            }
        elif not tester and self.mode in {"adversarial", "mixed"}:
            check.pop("adversarial_review")
        elif not tester and self.mode == "malformed":
            response = super().review_response(routing, payload, checks)
            response.content = "{" if ":json-retry" not in routing else "["
            return response
        elif not tester and self.mode == "malformed_once" and ":json-retry" not in routing:
            response = super().review_response(routing, payload, checks)
            response.content = "{"
            return response
        elif self.mode in {"false", "case_id", "profession", "recipient", "mixed"} and (
                tester or self.mode in {"profession", "recipient"}):
            paths = ["candidate_as/CaseID"] if self.mode == "case_id" else [self.first, self.second]
            reason = {
                "false": "Записка M05 относится к найму, а M01 к обработке поставки.",
                "case_id": "У требования нет предметной опоры.",
                "profession": ("М01 о поставке, M05 о проверке навыка найма." if tester
                               else "Сменился объект: профильная проверка оценивает собеседование, задача ведёт поставку."),
                "recipient": ("Из инструкции пропал адресат заказчик." if tester
                              else "Доступная инструкция оставляет одну письменную часть для коллеги."),
                "mixed": "Профильная проверка описывает собеседование вместо обработки поставки.",
            }[self.mode]
            if self.mode == "recipient":
                paths = ["candidate_as/Материалы/P00/Текст"]
            check.update(status="FAIL", reason=reason, evidence_paths=paths, findings=[{
                "code": "PAIR_FIXTURE", "severity": "blocking", "paths": paths, "reason": reason,
                "requirement_ref": self.criterion,
                "expected": "Рабочий объект и оба адресата сохранены",
                "actual": reason,
            }])
        return super().review_response(routing, payload, checks)


def fixture_generation(frozen, mode):
    generated = service.generate(frozen, PreparationGateway("pass"))
    candidate = generated["candidate_as"]
    docs = {row["MaterialID"]: row for row in candidate["Материалы"]}
    docs["P00"]["Текст"] = ("Передайте рекомендацию коллеге."
                             if mode == "recipient" else "Подготовьте рекомендацию коллеге и отдельный черновик заказчику.")
    docs["M01"]["Текст"] = "Карточка поставки. Срок подготовки — сегодня, подтверждение до пятницы ещё не получено."
    docs["M05"]["Текст"] = (
        "Отдел кадров проверил навык интервьюирования кандидата." if mode in {"profession", "mixed"}
        else "Инженер проверил на копии, что рабочая запись видна только владельцу. Срок подтверждения поставки открытый."
    )
    generated["candidate_checksum"] = service.checksum(candidate)
    generated["deterministic_validation"] = service.deterministic_checks(frozen, candidate)
    return generated


@pytest.mark.parametrize(("mode", "outcome"), [
    ("synonyms", "PASS"), ("shared_word", "PASS"), ("false", "FAIL"),
    ("case_id", "INCOMPLETE"), ("profession", "FAIL"), ("recipient", "FAIL"),
    ("adversarial", "INCOMPLETE"), ("mixed", "FAIL"), ("malformed", "INCOMPLETE"),
    ("malformed_once", "PASS"),
])
def test_paired_decisions(mode, outcome):
    frozen, gateway = snapshot(2), PairedGateway(mode)
    if mode == "recipient":
        gateway.criterion = "common.authority"
    generated = fixture_generation(frozen, mode)
    result = service.test_candidate(frozen, generated, gateway)
    sha = generated["candidate_checksum"]
    assert result["reviewed_candidate_checksum"] == sha
    for _, _, payload in gateway.calls:
        assert payload["candidate_checksum"] == sha and payload["candidate_as"] == generated["candidate_as"]
        assert payload["source_ref"] == frozen["applicability_plan"]["case_ref"]
    decision = result["aggregation"]
    assert decision["status"] == outcome
    assert not decision["deterministic_failures"]
    assert {row["reviewer"] for row in decision["blocking_failures"]} == (
        {"tester", "challenger"} if mode in {"profession", "recipient"} else
        {"tester"} if mode in {"false", "mixed"} else set()
    )
    if mode == "false":
        assert "Инженер проверил на копии" in next(row["Текст"] for row in generated["candidate_as"]["Материалы"]
                                                 if row["MaterialID"] == "M05")
    if mode == "mixed":
        assert {row["reviewer"] for row in decision["verification_errors"]} == {"challenger"}
    if mode == "case_id":
        assert decision["verification_errors"][0]["code"] == "FINDING_EVIDENCE_UNRELATED"
    if mode.startswith("malformed"):
        batch = result["challenger_operation"]["batches"][0]
        assert [call["attempt"] for call in batch["calls"]] == [1, 2]
        assert batch["calls"][0]["response_content"] == "{"
        assert batch["parse_failures"][0]["code"] == "PROVIDER_JSON_INVALID"
        if mode == "malformed":
            assert batch["calls"][1]["response_content"] == "["
            assert len(batch["parse_failures"]) == 2



def test_battery_review_requests_explicit_resolution_from_both_roles():
    frozen, gateway = snapshot(2), PreparationGateway("pass")
    generated = service.generate(frozen, gateway)
    service.test_candidate(frozen, generated, gateway)

    reviewers = set()
    for routing, messages, payload in gateway.calls:
        role = routing.split(":")[1]
        if role not in {"tester", "challenger"}:
            continue
        reviewers.add(role)
        resolution = payload["required_output"]["checks"][0]["adversarial_review"]["resolution"]
        assert "PASS по обязательному защищённому критерию" in resolution
        assert "из evidence_paths" in resolution
        assert "При пустом candidate_conflicts" in resolution
        assert "каждый указанный конфликт" in resolution
        assert "Пустая строка даёт TECHNICAL_ERROR" in resolution
        prompt = messages[0 if role == "challenger" else 1]["content"]
        assert "adversarial_review.resolution" in prompt
        assert "Пустой resolution даёт TECHNICAL_ERROR" in prompt
    assert reviewers == {"tester", "challenger"}


def test_server_detects_lost_recipient_without_a_reviewer():
    frozen = snapshot(3)
    generated = service.generate(frozen, PreparationGateway("pass"))
    candidate = deepcopy(generated["candidate_as"])
    event = candidate["RuntimeBindings"]["E01_UPDATE"]
    expected = event["audience"]
    event["audience"] = None
    checked = service.deterministic_checks(frozen, candidate)
    failures = [row for row in checked["checks"] if row["result"] == "FAIL"]
    assert failures == [{
        "code": "battery_event_binding", "result": "FAIL", "actual": None, "expected": expected,
        "path": "candidate_as/RuntimeBindings/E01_UPDATE/audience",
        "reason": "Параметр события должен совпадать с закреплённой привязкой сценария.",
    }]


def test_preexisting_battery_snapshot_can_still_run_and_read_v3():
    frozen = snapshot(2, package=AS_PACKAGE.with_name("v3"))
    gateway = PreparationGateway("pass")
    result = service.prepare(frozen, gateway)
    assert result["tester"]["protocol"]["version"] == "2.1.0"
    assert result["admitted_for_participant"]
    assert "review_source" not in result["tester"]
    saved = json.loads(json.dumps(service.build_persistence_trace(frozen, result)))
    assert saved["source_snapshot"]["refs"]["protocol_package"]["version"] == "3.0.0"
    assert saved["source_snapshot"]["refs"]["battery_scenario"]
    functional_gate(saved, operation_id=frozen["operation_id"])
    saved["source_snapshot"]["refs"]["protocol_package"]["checksum"] = "0" * 64
    with pytest.raises(ValueError, match="PILOT_PLAN_REVIEW_PROTOCOL_MISMATCH"):
        functional_gate(saved, operation_id=frozen["operation_id"])


class RepairGateway(PairedGateway):
    def __init__(self, mode, repair_response):
        super().__init__(mode)
        self.repair_response = repair_response
        self.original = None

    def chat_with_trace(self, messages, **kwargs):
        routing = kwargs["routing_key"]
        response = super().chat_with_trace(messages, **kwargs)
        if ":generation:" not in routing:
            return response
        if ":repair:" not in routing:
            self.original = response.content
        elif self.repair_response == "unchanged":
            response.content = self.original
        elif self.repair_response == "invalid":
            response.content = "{"
        return response


@pytest.mark.parametrize(("mode", "repair_response", "status", "repair_outcome"), [
    ("adversarial", "unused", "INCOMPLETE", None),
    ("mixed", "unchanged", "FAIL", "UNCHANGED_CANDIDATE"),
    ("mixed", "invalid", "FAIL", "INVALID_REPAIR_RESPONSE"),
    ("mixed", "changed", "FAIL", "FAIL"),
])
def test_repair_receives_only_actionable_findings(mode, repair_response, status, repair_outcome):
    gateway = RepairGateway(mode, repair_response)
    result = service.prepare(snapshot(2), gateway)
    assert not result["admitted_for_participant"]
    assert result["tester"]["aggregation"]["status"] == status
    repair_calls = [payload for route, _, payload in gateway.calls if ":repair:" in route]
    if repair_outcome is None:
        assert not repair_calls and result["repair"] is None
        return
    repair = result["repair"]
    assert repair["outcome"] == repair_outcome
    assert len(repair_calls) == (2 if repair_response == "invalid" else 1)
    payload = repair_calls[0]
    assert "validation_errors" not in payload and payload["deterministic_failures"] == []
    item, = payload["blocking_failures"]
    assert item["reviewer"] == "tester" and item["check_id"] == gateway.criterion
    finding, = item["findings"]
    assert set(finding) == {"code", "paths", "reason", "expected", "actual"}
    assert repair["original_tester"]["aggregation"]["verification_errors"][0]["reviewer"] == "challenger"
    assert payload["rejected_candidate_checksum"] == service.checksum(repair["original_candidate_as"])
    if repair_response == "changed":
        assert result["candidate_checksum"] != repair["original_candidate_checksum"]
        assert result["tester"]["aggregation"]["blocking_failures"]
    else:
        assert result["candidate_checksum"] == repair["original_candidate_checksum"]
        reviews = [(route, body) for route, _, body in gateway.calls if "candidate_as" in body]
        assert len(reviews) == 6
        assert all(body["candidate_checksum"] == repair["original_candidate_checksum"] for _, body in reviews)
    if repair_response == "invalid":
        assert [row["response_content"] for row in repair["repair_generation_operation"]["calls"]] == ["{", "{"]


@pytest.mark.parametrize(("number", "check_id", "field", "identifier", "reason"), [
    (1, "common.independent_observation", "Материалы", "P00", "Вводная диктует участнику готовую карту интересов."),
    (3, "common.authority", "Активные персонажи", "C2", "Коллега распоряжается вкладом C3 без полномочий."),
    (7, "indicator:K3.I06", "Материалы", "M01", "Источник выдаёт готовые варианты вместо основания для самостоятельного поиска."),
])
def test_content_defects_across_formats(number, check_id, field, identifier, reason):
    class DefectGateway(PreparationGateway):
        def review_response(self, routing, payload, checks):
            for check in checks:
                if check["check_id"] != check_id:
                    continue
                path = f"candidate_as/{field}/{identifier}/Текст"
                phrase = reason if ":tester:" in routing else f"При сопоставлении с паспортом обнаружено следующее. {reason}"
                check.update(status="FAIL", evidence_paths=[path], reason=phrase, findings=[{
                    "code": "PASSPORT_OPPORTUNITY_LOSS", "severity": "blocking",
                    "paths": [path], "requirement_ref": check_id, "reason": phrase,
                }])
            return super().review_response(routing, payload, checks)

    frozen = snapshot(number)
    generated = service.generate(frozen, PreparationGateway("pass"))
    value = generated["candidate_as"]
    row = next(item for item in value[field] if identifier in item.values())
    row["Текст"] = reason
    generated["candidate_checksum"] = service.checksum(value)
    generated["deterministic_validation"] = service.deterministic_checks(frozen, value)
    result = service.test_candidate(frozen, generated, DefectGateway("pass"))
    assert result["aggregation"]["status"] == "FAIL"
    assert not result["aggregation"]["deterministic_failures"]
    assert [(row["reviewer"], row["check_id"]) for row in result["aggregation"]["blocking_failures"]] == [
        ("tester", check_id), ("challenger", check_id),
    ]


def test_shared_word_with_closed_fact_is_not_a_server_violation():
    frozen = snapshot(1)
    generated = service.generate(frozen, PreparationGateway("pass"))
    candidate = generated["candidate_as"]
    candidate["Закрытые фиксированные факты"][0]["Текст"] = "срок"
    next(row for row in candidate["Материалы"] if row["MaterialID"] == "P00")["Текст"] = "Уточните срок подготовки."
    assert service.deterministic_checks(frozen, candidate)["status"] == "PASS"
