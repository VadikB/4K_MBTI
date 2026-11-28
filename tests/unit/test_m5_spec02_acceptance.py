"""Controlled SPEC.02 probes for the deterministic and semantic admission controls."""

import json

import pytest

from Api import m5_functional_generation_service as service
from Api.cycle_execution_manifest import M5_BATTERY_PILOT_REVIEW_PACKAGES, ROOT
from Api.m5_battery_contract import load_scenario
from Api.m5_battery_profile import review
from Api.m5_source_calculations import quantity_basis_division_checks
from tests.unit.test_m5_battery_v06_profile_fit import (
    DECISIONS, LIMITS, PROFILE, RULES, SPEC02, WORK, FitGateway, cases, evidence,
)
from tests.unit.test_m5_pilot_review import PilotGateway


pytestmark = pytest.mark.unit
SCENARIO = RULES.with_name("1.10.4")
CONSISTENCY = "common.professional_consistency"
OBSERVATION = "common.independent_observation"
ADVANTAGE = "invariant:CASE.SPEC.02.I02"
M02 = "candidate_as/Материалы/M02/Текст"
M03 = "candidate_as/Материалы/M03/Текст"
M04 = "candidate_as/Материалы/M04/Текст"
M05 = "candidate_as/Материалы/M05/Текст"

PERSON_DAYS = ("Значение 3,4 рабочих дня на заявку получено как отношение суммарных "
               "трудозатрат 8 160 человеко-дней к объёму 2 400 заявок.")
M02_CONFLICT = "Значение заявлено автором как плановое, подтверждено по журналу закрытых заявок."
M03_CONCLUSION = "Значение 3,4 выше предела 3,0 из M01: вариант A выходит за требование заказчика."
M04_CONCLUSION = "Доля 88% ниже порога 90% по M01."
SAME_SERIES = "За пять рабочих дней завершено 500 заявок. Среднее 500 / 5 = 112 заявок в день."
NO_BASIS = "За отчётный период завершено 500 заявок. Среднее 500 / 5 = 100 заявок в день."
BRIDGE = "Закрыто 500 заявок за пять рабочих дней. Среднее 500 / 5 = 100 заявок в день."

PACKET = {
    "P00": "6 октября 2025. Вы сопоставляете способы профильной проверки заявок. "
           "Изучите M01–M06. Сегодня подготовьте рекомендацию коллеге и черновик "
           "заказчику к 10 октября. Срок подтверждает владелец процесса.",
    "M01": "Заказчик, v1 от 6 октября. Действующий запрос по профильной проверке заявок. "
           "Средний срок не более 3,0 рабочих дней на заявку, полнота не ниже 90%. "
           "Сопоставлять заявки, закрытые с 1 по 30 сентября 2025 по рабочему календарю. "
           "Ответ к 10 октября, завершение потока к 31 октября.",
    "M02": "Владелец A, v1 от 29 августа. Плановый показатель сентября: 2,5 рабочих дня на заявку "
           "для профильной проверки. План рассчитан для 2 400 заявок с 1 по 30 сентября 2025. "
           "Срок октября остаётся плановым.",
    "M03": "Владелец A, v2 от 3 октября. Профильная проверка: 3,4 рабочих дня на заявку, "
           "по датам начала и закрытия 2 400 завершённых заявок за 1–30 сентября 2025. "
           "Средний срок в рабочем календаре, выходные и праздники исключены. "
           "Журнал закрытых заявок подтверждает замер. Заменяет плановое значение из M02.",
    "M04": "Владелец B, v1 от 2 октября. Профильная проверка с 1 по 30 сентября 2025. "
           "Заявленный срок 2,8 рабочих дня на заявку по рабочему календарю. "
           "Заявленная полнота 88%; независимо не измерена.",
    "M05": "Проверяющий, v1 от 4 октября. Выборочная проверка B с 1 по 30 сентября 2025 "
           "охватила 100 из 2 400 закрытых заявок: по журналу 88% проверены с полным следом; "
           "срок и результаты всего потока не проверялись. Отдельно: в завершённой пробе B "
           "3 октября по отдельному журналу замерен выпуск за один рабочий день, 112 заявок в день. "
           "Показатель пробы не переносится на сентябрь. Ближайшая проверка срока 14 октября.",
    "M06": "Коллега, v1 от 6 октября. Предлагаю сегодня рекомендовать A: он планировал 2,5 рабочих "
           "дня на заявку, B заявил 2,8. По моему мнению, этого достаточно для выбора.",
}


@pytest.mark.parametrize(("documents", "expected"), [
    ({"M03": "Отчёт за двадцать дней: 500 заявок. В среднем 500 / 20 = 25 заявок в день."},
     [("battery_division_provenance", "PASS")]),
    ({"M03": "Отчёт за 20 дней: 500 заявок. В среднем 500 / 20 = 25 заявок в день."},
     [("battery_division_provenance", "PASS")]),
    ({"M03": "Обработано 500 заявок. В смене пять специалистов. В среднем 500 / 5 = 100 заявок в день."},
     [("battery_division_basis", "FAIL")]),
    ({"M01": "За 20 дней закрыто 500 заявок.", "M03": "По M01 рассчитано среднее 500 / 20 = 25 заявок в день."},
     [("battery_division_provenance", "PASS")]),
    ({"M01": "Закрыто 500 заявок.", "M02": "Рабочий этап занял 20 дней.",
      "M03": "500 (M01) / 20 (M02) = 25 заявок в день."},
     [("battery_division_provenance", "PASS")]),
    ({"M01": "За 20 дней закрыто 500 заявок.", "M03": "Из свода среднее 500 / 20 = 25 заявок в день."},
     [("battery_division_provenance", "REVIEW_REQUIRED")]),
    ({"M01": "Закрыто 500 заявок.", "M03": "500 (M01) / 20 (M09) = 25 заявок в день."},
     [("battery_division_provenance", "REVIEW_REQUIRED")]),
    ({"M03": "За пять рабочих дней закрыто 500 заявок. Работало пять специалистов. "
             "Среднее 500 / 5 = 100 заявок в день."},
     [("battery_division_provenance", "REVIEW_REQUIRED")]),
    ({"M03": "В отчёте 8 160 человеко-дней и 2 400 заявок. 8 160 / 2 400 = 3,4 человеко-дня на заявку."},
     [("battery_division_provenance", "PASS")]),
    ({"M03": PERSON_DAYS + " 8 160 / 2 400 = 3,4."},
     [("battery_division_basis", "FAIL"), ("battery_division_provenance", "REVIEW_REQUIRED")]),
    ({"M03": NO_BASIS}, [("battery_division_provenance", "REVIEW_REQUIRED")]),
    ({"M03": "5 рабочих дней, 500 заявок. Среднее 500 / 5 = 100."},
     [("battery_division_provenance", "REVIEW_REQUIRED")]),
    ({"M03": SAME_SERIES},
     [("battery_division_result", "FAIL"), ("battery_division_provenance", "PASS")]),
    ({"M03": BRIDGE + " В отдельной пробе 3 октября по журналу замерено 112 заявок за рабочий день."},
     [("battery_division_provenance", "PASS")]),
])
def test_quantities_are_typed_located_and_recomputed(documents, expected):
    decisions = quantity_basis_division_checks("M03", documents)
    assert [(item["code"], item["status"]) for item in decisions] == expected


@pytest.fixture(scope="module")
def scenario_snapshot():
    case = cases()[SPEC02]
    design = load_scenario(case, SCENARIO)
    gateway = FitGateway({SPEC02: {"work": evidence("regular_tasks", WORK),
                                  "decision": evidence("decision_situations", DECISIONS),
                                  "authority": evidence("constraints_and_interactions", LIMITS)}})
    fit = review(PROFILE, [design], gateway, operation_id="spec02-acceptance")[SPEC02]
    return service.build_passport_snapshot(
        case_version=case, profile=PROFILE, operation_id="spec02-acceptance", synthetic=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"],
        battery_scenario_package=SCENARIO, battery_profile_fit=fit,
    )


class ControlledMaterials(PilotGateway):
    def __init__(self, initial, repaired=None):
        super().__init__()
        self.initial_documents = {**PACKET, **initial}
        self.repaired_documents = {**PACKET, **repaired} if repaired is not None else self.initial_documents

    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        routing = kwargs["routing_key"]
        if ":generation:" in routing:
            documents = self.repaired_documents if ":repair:" in routing else self.initial_documents
            candidate = json.loads(response.content)
            candidate["AssessmentSituationID"] = "045c0dd9-cdd1-4539-89cb-c9b36a83c8b1"
            for row in candidate["Материалы"]:
                row["Текст"] = documents[row["MaterialID"]]
            response.content = json.dumps(candidate, ensure_ascii=False)
        return response

    def review_response(self, routing, payload, checks):
        definitions = ((payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"])
        documents = {row["MaterialID"]: row["Текст"] for row in payload["candidate_as"]["Материалы"]}
        violations = {
            CONSISTENCY: [
                ("CONFLICTING_SOURCE_STATUS", M02, "Один показатель назван плановым и подтверждённым.",
                 M02_CONFLICT in documents["M02"]),
                ("NO_COMPARABLE_BASIS", M05, "Из текста источников неизвестен период в 5 дней.",
                 NO_BASIS in documents["M05"]),
            ],
            ADVANTAGE: [
                ("WRONG_DURATION_UNIT", M03, "Человеко-дни на заявку не дают сроки в рабочих днях.",
                 PERSON_DAYS in documents["M03"]),
            ],
            OBSERVATION: [
                ("PROVIDED_COMPARISON", M03, "M03 уже сообщил вывод о выполнении порога M01.", M03_CONCLUSION in documents["M03"]),
                ("PROVIDED_COMPARISON", M04, "M04 уже сравнил заявленный процент с порогом M01.", M04_CONCLUSION in documents["M04"]),
            ],
        }
        for row in checks:
            check_id = row["check_id"]
            if check_id not in violations:
                continue
            definition = next(item for item in definitions if item["check_id"] == check_id)
            assert definition["protected"] and definition["requirement"]["case_content"]
            findings = [{"code": code, "severity": "blocking", "paths": [path],
                         "reason": reason, "requirement_ref": check_id}
                        for code, path, reason, violated in violations[check_id] if violated]
            if findings:
                row.update(status="FAIL", reason=" ".join(item["reason"] for item in findings),
                           evidence_paths=[path for finding in findings for path in finding["paths"]],
                           findings=findings)
            else:
                row.update(reason="В M02 статус — прежний план, M03 даёт отдельный замер; "
                                  "в M03/M04 участнику доступны исходные факты.",
                           adversarial_review={"candidate_conflicts": [],
                                               "resolution": "По текстам M01–M05 сверены предмет, период, "
                                                             "единица, статус и доступность сравнения."})
        return super().review_response(routing, payload, checks)


@pytest.mark.parametrize(("overrides", "deterministic", "admitted"), [
    ({"M05": PACKET["M05"] + " Отчёт за двадцать дней: 500 заявок. 500 / 20 = 25 заявок в день."}, "PASS", True),
    ({"M05": PACKET["M05"] + " Отчёт за 20 дней: 500 заявок. 500 / 20 = 25 заявок в день."}, "PASS", True),
    ({"M05": PACKET["M05"] + " " + BRIDGE}, "PASS", True),
    ({"M01": PACKET["M01"] + " Архивный отчёт приложен: за 20 дней закрыто 500 заявок.",
      "M05": PACKET["M05"] + " По M01 для архива 500 / 20 = 25 заявок в день."}, "PASS", True),
    ({"M05": PACKET["M05"] + " " + SAME_SERIES}, "FAIL", False),
    ({"M05": PACKET["M05"] + " " + NO_BASIS}, "PASS", False),
    ({"M05": "Закрыто 500 заявок. В смене пять специалистов. 500 / 5 = 100 заявок в день."}, "FAIL", False),
    ({"M03": PACKET["M03"] + " " + M03_CONCLUSION}, "PASS", False),
    ({"M04": PACKET["M04"] + " " + M04_CONCLUSION}, "PASS", False),
])
def test_deterministic_result_and_final_admission_are_distinct(scenario_snapshot, overrides, deterministic, admitted):
    gateway = ControlledMaterials(overrides)
    result = service.prepare(scenario_snapshot, gateway)
    assert result["deterministic_validation"]["status"] == deterministic
    assert result["admitted_for_participant"] is admitted
    if not admitted:
        assert result["tester"]["aggregation"]["status"] == "FAIL"
        assert result["repair"]["outcome"] == "UNCHANGED_CANDIDATE"
        assert not result["compiled_case"]
    else:
        assert result["tester"]["aggregation"]["status"] == "PASS" and result["compiled_case"]


@pytest.mark.parametrize(("repair", "outcome", "admitted"), [
    ({}, "PASS", True),
    (None, "UNCHANGED_CANDIDATE", False),
    ({"M02": PACKET["M02"] + " " + M02_CONFLICT}, "FAIL", False),
])
def test_repair_rechecks_both_materials_and_keeps_refusal_if_contradiction_persists(scenario_snapshot, repair, outcome, admitted):
    initial = {"M02": PACKET["M02"] + " " + M02_CONFLICT,
               "M03": PERSON_DAYS + " 8 160 / 2 400 = 3,4."}
    gateway = ControlledMaterials(initial, repair)
    result = service.prepare(scenario_snapshot, gateway)
    assert result["admitted_for_participant"] is admitted
    actual = result["repair"]["outcome"]
    assert actual == outcome
    [messages] = [messages for routing, messages, payload in gateway.calls if ":generation:repair:" in routing]
    request = json.loads(messages[-1]["content"])
    assert request["scenario_contract"]["ref"]["version"] == "1.10.4"
    assert "однозначность и дату статуса M02" in messages[0]["content"]
    assert [item["path"] for item in request["deterministic_failures"]] == [M03]
    assert all(row["MaterialID"] in PACKET for row in request["rejected_candidate_as"]["Материалы"])
    assert {row["reviewer"] for row in request["blocking_failures"]} == {"tester", "challenger"}
    assert {item["code"] for row in request["blocking_failures"] for item in row["findings"]} == {
        "CONFLICTING_SOURCE_STATUS", "WRONG_DURATION_UNIT",
    }
    rounds = {payload["review_dispatch"]["round"] for _, _, payload in gateway.calls if "review_dispatch" in payload}
    assert rounds == ({1} if repair is None else {1, 2})
