"""Replay the recorded C2 deadline and route each valid interpretation through admission."""
import json

import pytest

from Api import m5_functional_generation_service as service
from Api.cycle_execution_manifest import M5_BATTERY_PILOT_REVIEW_PACKAGES, ROOT
from tests.unit.test_m5_battery_v06_profile_fit import PROFILE, RULES, cases
from tests.unit.test_m5_pilot_review import PilotGateway


pytestmark = pytest.mark.unit
CHECK = "common.scenario_executability"
I05 = "invariant:CASE.SPEC.03.I05"
M01_PATH = "candidate_as/Материалы/M01/Текст"
M03_PATH = "candidate_as/Материалы/M03/Текст"
M01 = ("К пятнице 17:00 нужен окончательный ответ по проверенной партии после подтверждения обеих частей. "
       "К пятнице 16:00 можно сообщить предварительный статус с указанием непроверенных частей.")
M04 = ("Заказчик в пятницу сообщил C2 об изменении периода с апреля на май. C1 должен пересчитать объём за май. "
       "C3 должен заново собрать выборку для отдельной проверки качества за май. Оба результата пока не подтверждены. "
       "C2 использует обе проверки для итоговой части. Условия предварительного статуса из M01 сохраняются.")
C1 = "C1: «В рабочем окне пятницы 10:00–12:00 за 90 минут сверю объём по актуальному реестру.»"
C3 = "C3: «В пятницу с 13:00 до 15:00 мне нужен час для проверки качества после получения актуальной выборки.»"
C3_LATE = C3.removesuffix("»") + " Передачу пока предлагаю на 16:00.»"
# This role statement is copied from the recorded generation of 1.10.3, with no paraphrase.
RECORDED_C2 = (
    "C2: «Я вела переписку с заказчиком и собрала текущий свод. Итоговую часть могу готовить после получения "
    "обоих профильных входов. Моё окно для итогового действия — рабочий день 14:00–16:00, длительность 60 минут. "
    "Мне нужно получить оба подтверждения до 16:00 пятницы, чтобы успеть к сроку 17:00. "
    "Профессиональный статус частей подтверждают C1 и C3.»"
)
ON_TIME = RECORDED_C2.replace("до 16:00 пятницы", "к 15:00 пятницы")
LATE_OFFER = (
    "C2: «Итоговую часть могу готовить только после получения обоих входов. "
    "Моё окно для итогового действия — пятница 14:00–16:00, длительность 60 минут. "
    "Передача в 16:00 пока предложена, а срок итогового ответа требует согласования. "
)
PRELIMINARY = LATE_OFFER + "Обсудим, какие ограничения сможем сообщить в предварительном статусе к 16:00.»"
RESCHEDULE = LATE_OFFER + "Могу запросить у заказчика другую дату итогового ответа; её ещё не согласовали.»"
UNSUPPORTED_PROMISE = (
    LATE_OFFER + "Статус не нужен: итоговая часть точно будет готова в пятницу к 17:00 по старому сроку.»"
)
PARTIAL = (
    "C2: «Общую структуру ответа готовлю заранее. Окно для итогового действия — пятница 14:00–16:00, "
    "длительность 60 минут. После двух входов остаётся только заключительная сверка на 15 минут. "
    "C1 и C3 могут предложить передачу до 15:45.»"
)


@pytest.fixture
def snapshot():
    return service.build_passport_snapshot(
        case_version=cases()["CASE.SPEC.03"], profile=PROFILE, operation_id="handoff-regression", synthetic=True,
        as_package=ROOT / M5_BATTERY_PILOT_REVIEW_PACKAGES["7.0.0"],
        battery_scenario_package=RULES.with_name("1.10.4"),
    )


class HandoffGateway(PilotGateway):
    def __init__(self, initial, *, repaired=None, schedule_review=None):
        super().__init__()
        self.initial_schedule = initial
        self.repaired_schedule = repaired if repaired is not None else initial
        self.schedule_review = schedule_review

    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        routing = kwargs["routing_key"]
        if ":generation:" in routing:
            candidate = json.loads(response.content)
            candidate["AssessmentSituationID"] = "spec03-handoff-replay"
            c2 = self.repaired_schedule if ":repair:" in routing else self.initial_schedule
            materials = {row["MaterialID"]: row for row in candidate["Материалы"]}
            materials["M01"]["Текст"] = M01
            c3 = C3_LATE if c2.startswith(LATE_OFFER) else C3
            materials["M03"]["Текст"] = "\n".join((C1, c2, c3))
            materials["M04"]["Текст"] = M04
            response.content = json.dumps(candidate, ensure_ascii=False)
        return response

    def review_response(self, routing, payload, checks):
        definitions = ((payload.get("applicability_plan") or {}).get("required_checks") or payload["protected_checks"])
        if criterion := next((row for row in definitions if row["check_id"] == CHECK), None):
            assert criterion["protected"]
            assert criterion["source_ref"]["case_content"]["version"] == "2.1.4"
            requirement = criterion["requirement"]["case_content"]
            assert "Получение в 16:00 оставляет ноль минут" in requirement
            assert "намеренную несогласованную позицию коллеги" in requirement
            assert "часть работы C2 может выполняться заранее" in requirement
            assert any("17.2 Материалы и исходная доступность/3" in row["pointer"]
                       for row in criterion["source_ref"]["supplemental_locations"])
            assert {M01_PATH.removesuffix("/Текст"), M03_PATH.removesuffix("/Текст")} <= set(
                criterion["finding_evidence_sections"])
            status, reason = self.schedule_review or ("PASS", "В 15:00 остаётся 60 минут для C2.")
            row = next(row for row in checks if row["check_id"] == CHECK)
            row.update(status=status, reason=reason, evidence_paths=[M01_PATH, M03_PATH],
                       adversarial_review={"candidate_conflicts": [M03_PATH], "resolution": reason})
            if status == "FAIL":
                row["findings"] = [{
                    "code": "SPEC03_UNSUPPORTED_FINAL_DEADLINE", "severity": "blocking", "paths": [M01_PATH, M03_PATH],
                    "reason": reason, "requirement_ref": CHECK,
                }]
        return super().review_response(routing, payload, checks)


@pytest.mark.parametrize(("text", "reason"), [
    (ON_TIME, "К 15:00 оба входа могут быть готовы, у C2 остаётся полный час. Коллеги договариваются о передаче сами."),
    (PRELIMINARY, "16:00 оставляет ноль минут на итог. M01 позволяет C2 согласовать статус с ограничениями."),
    (RESCHEDULE, "До 16:00 итоговая работа не вмещается. C2 может запросить перенос, окончательный срок открыт."),
    (PARTIAL, "Выполнимая зависимая работа занимает 15 минут. Остальную часть C2 может подготовить до входов."),
], ids=["15-00", "16-00-preliminary", "16-00-reschedule", "partial-work-before-inputs"])
def test_handoff_and_open_options_reach_both_reviewers(snapshot, text, reason):
    design = snapshot["battery_scenario"]
    assert design["explicit_handoff_materials"] == {"M03": "C2"}
    assert "M04" not in design["start_ids"]
    assert all("M04" not in role["known_material_ids"] for role in design["roles"].values())
    update = next(row for row in design["events"] if row["id"] == "E01_UPDATE")
    assert (update["delivery_id"], update["speaker_ids"], update["audience"]) == ("M04", ["C2"], "assessee")
    gateway = HandoffGateway(text, schedule_review=("PASS", reason))
    prepared = service.prepare(snapshot, gateway)
    assert prepared["admitted_for_participant"]
    assert prepared["deterministic_validation"]["status"] == "PASS"
    participant = prepared["compiled_case"]["participant_presentation"]
    start = {row["material_id"]: row["text"] for row in participant["initial_materials"]}
    assert set(start) == {"M01", "M02", "M03"}
    assert text in start["M03"]
    assert M04 not in participant["introduction"] + "".join(start.values())
    sent = gateway.calls[0][2]
    assert "срок внешнего ответа сам по себе не расширяет" in sent["scenario_contract"]["generation_addendum"].casefold()
    assert "CASE.SPEC.03" == sent["case"]["CaseID"]
    for rows in prepared["tester"]["independent_checks"].values():
        assert next(row for row in rows if row["check_id"] == CHECK)["reason"] == reason
        assert next(row for row in rows if row["check_id"] == I05)["status"] == "PASS"


@pytest.mark.parametrize(("repaired", "status"), [
    (ON_TIME, "PASS"), (RECORDED_C2, "UNCHANGED_CANDIDATE"),
    (RECORDED_C2.replace("60 минут", "55 минут"), "FAIL"),
], ids=["early-repair", "unchanged", "changed-but-invalid"])
def test_explicit_late_promise_reaches_repair_before_reviewers(snapshot, repaired, status):
    gateway = HandoffGateway(RECORDED_C2, repaired=repaired)
    prepared = service.prepare(snapshot, gateway)
    assert prepared["repair"]["outcome"] == status
    assert prepared["admitted_for_participant"] is (status == "PASS")
    _, _, requested = gateway.calls[1]
    failure = next(item for item in requested["deterministic_failures"]
                   if item["code"] == "battery_handoff_after_latest_start")
    assert failure["path"] == M03_PATH
    assert failure["actual"]["minutes_available_after_handoff"] == 0
    assert failure["expected"] == {"latest_handoff": "15:00", "required_minutes": "60"}
    assert "предварительный статус" in failure["reason"]
    assert all(payload["review_dispatch"]["round"] == 2 for _, _, payload in gateway.calls[2:])
    assert bool(gateway.calls[2:]) is (status == "PASS")


def test_final_promise_without_available_work_reaches_both_reviewers(snapshot):
    reason = "При передаче в 16:00 окно C2 заканчивается, а прежний окончательный срок обещан."
    gateway = HandoffGateway(UNSUPPORTED_PROMISE, schedule_review=("FAIL", reason))
    prepared = service.prepare(snapshot, gateway)
    assert prepared["deterministic_validation"]["status"] == "PASS"
    assert prepared["repair"]["outcome"] == "UNCHANGED_CANDIDATE"
    assert not prepared["admitted_for_participant"]
    for rows in prepared["tester"]["independent_checks"].values():
        result = next(row for row in rows if row["check_id"] == CHECK)
        assert result["status"] == "FAIL"
        assert result["findings"][0]["code"] == "SPEC03_UNSUPPORTED_FINAL_DEADLINE"
