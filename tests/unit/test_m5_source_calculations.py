"""Regression for the written candidate returned by the working provider."""
import pytest

from Api import m5_functional_generation_service as service
from Api.cycle_execution_manifest import M5_BATTERY_PILOT_REVIEW_PACKAGES, ROOT
from Api.m5_battery_contract import load_scenario
from Api.m5_battery_profile import review
from Api.m5_passport_generation import provider_basis
from Api.m5_source_calculations import division_findings, window_duration_findings
from tests.integration.test_m5_battery_scenario_db import synthetic_as
from tests.unit.test_m5_battery_v06_profile_fit import (
    DECISIONS, LIMITS, PROFILE, RULES, SPEC02, WORK, FitGateway, cases, evidence,
)


pytestmark = pytest.mark.unit
M03_WORKING_PROVIDER = (
    "Основание изменения: уточнённая оценка длительности одной операции — 0,65 рабочего дня на заявку при том же "
    "объёме 500 заявок и пяти рабочих днях. Значение 6,5 рабочих дней получено как 0,65 рабочего дня на заявку "
    "× 500 заявок = 325 человеко-дней суммарно; при доступных 15 человеко-днях (пять рабочих дней × три специалиста) "
    "средний срок закрытия заявки составляет 325 / 50 = 6,5 рабочих дней. Расчёт и последствия выполняет участник."
)
C3_WORKING_PROVIDER = ("Коллега 3: «Готов обсудить включение в конкретную проверку своей части: "
                       "окно — среда 10:00–13:00, длительность 4 часа. Условия и срок проверки определяю я».")


@pytest.mark.parametrize("document", [
    "500 заявок за пять рабочих дней. Средний выпуск 500 / 5 = 100.",
    "За 3 смены обработано 100 заявок. Среднее составило 100 / 3 = 33,3.",
    "За 5 дней обработано 1\u202f000 заявок. Среднее 1 000 ÷ 5 = 200.",
    "За 5 рабочих дней обработано 500 заявок. В другом потоке за смену по журналу измерено 112 завершённых заявок.",
    "Идентификатор A325/50, отчёт от 25/06/2025, код M05/03. Версия = 2.",
    "500 заявок за 5 рабочих дней. Работали две группы. 500/5 = 100. 100/2 = 50.",
])
def test_documented_calculations_identifiers_and_independent_measurements(document):
    assert division_findings(document) == []


def test_wrong_average_and_missing_basis_are_distinguished():
    assert division_findings("500 заявок за пять рабочих дней. Средний выпуск 500 / 5 = 112.") == [
        {"code": "battery_division_result", "expression": "500 / 5 = 112", "expected_result": "100"},
    ]
    expected = [{"code": "battery_division_basis", "expression": "325 / 50 = 6,5", "missing": ["50"]}]
    assert division_findings(M03_WORKING_PROVIDER) == expected
    assert division_findings(M03_WORKING_PROVIDER + " Ссылки C50 и M50/10/2025 номера не поясняют.") == expected
    assert division_findings("9 заявок. 9/3 = 3.") == [
        {"code": "battery_division_basis", "expression": "9/3 = 3", "missing": ["3"]},
    ]


@pytest.mark.parametrize("version,status", [("1.10.0", "PASS"), ("1.10.1", "FAIL"), ("1.10.2", "FAIL")])
def test_provider_m03_repair_is_rejected_only_with_new_scenario(version, status):
    case = cases()[SPEC02]
    directory = RULES.with_name(version)
    design = load_scenario(case, directory)
    gateway = FitGateway({SPEC02: {"work": evidence("regular_tasks", WORK),
                                  "decision": evidence("decision_situations", DECISIONS),
                                  "authority": evidence("constraints_and_interactions", LIMITS)}})
    fit = review(PROFILE, [design], gateway, operation_id="numeric-regression")[SPEC02]
    snapshot = service.build_passport_snapshot(
        case_version=case, profile=PROFILE, operation_id="numeric-regression", synthetic=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"],
        battery_scenario_package=directory, battery_profile_fit=fit,
    )
    candidate = synthetic_as(provider_basis(snapshot))
    next(row for row in candidate["Материалы"] if row["MaterialID"] == "M03")["Текст"] = M03_WORKING_PROVIDER
    generation = service._assemble_candidate(snapshot, candidate)
    result = generation["deterministic_validation"]
    assert result["status"] == status
    if status == "FAIL":
        assert result["errors"] == [{"error_class": "candidate_validation", "check": "battery_division_basis",
                                     "path": "candidate_as/Материалы/M03/Текст"}]
        criterion = next(item for item in snapshot["applicability_plan"]["required_checks"]
                         if item["check_id"] == "common.professional_consistency")
        assert criterion["protected"] and "оба операнда" in criterion["requirement"]["case_content"]
        assert "candidate_as/Материалы/M04" in criterion["finding_evidence_sections"]


@pytest.mark.parametrize("text", [
    "Для сверки окно — в среду 10:00–13:00, длительность 180 минут.",
    "Окно — среда 09:30–13:00, длительность 3,5 часа.",
    "Первый специалист доступен в окно — в среду 10:00–13:00. Длительность сверки другого специалиста 4 часа.",
    "Дежурство через смену: окно — 23:30–04:00, длительность 4 часа.",
])
def test_valid_intervals_and_unrelated_role_statements(text):
    assert window_duration_findings(text) == []


@pytest.mark.parametrize("version,status", [("1.10.1", "PASS"), ("1.10.2", "FAIL")])
def test_provider_c3_window_requires_room_for_the_stated_duration(version, status):
    snapshot = service.build_passport_snapshot(
        case_version=cases()["CASE.SPEC.03"], profile=PROFILE, operation_id="window-regression", synthetic=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"], battery_scenario_package=RULES.with_name(version),
    )
    candidate = synthetic_as(provider_basis(snapshot))
    next(row for row in candidate["Материалы"] if row["MaterialID"] == "M03")["Текст"] = C3_WORKING_PROVIDER
    result = service._assemble_candidate(snapshot, candidate)["deterministic_validation"]
    assert result["status"] == status
    if status == "FAIL":
        assert result["errors"] == [{"error_class": "candidate_validation", "check": "battery_window_duration_exceeds",
                                     "path": "candidate_as/Материалы/M03/Текст"}]
        failed, = [item for item in result["checks"] if item["result"] == "FAIL"]
        assert failed["actual"]["duration_minutes"] == "240" and failed["actual"]["available_minutes"] == 180
