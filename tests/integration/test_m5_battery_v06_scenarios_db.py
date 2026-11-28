"""Exercise the nine v0.6 sources through PM-03, PM-04 and the C-45 handoff."""
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from Api.assessment_contexts import confirm_user_context, create_personalized_profile, create_user_context_draft
from Api.cycle_execution_manifest import BATTERY_V06_SCENARIO_PACKAGE, ROOT
from Api.m5_battery_preparation import prepare_next
from Api.m5_cycle_runtime import create_cycle_session_for_case
from Api.m5_scenario_runtime import trace, transition
from scripts.plan_specialist_program_release import BATTERY_V06_PACKAGE, publish_diagnostic_battery
from tests.integration.test_m10_product_path_db import product_db
from tests.integration.test_m5_battery_scenario_db import matched, prepare_and_start, submit
from tests.integration.test_m5_battery_v04_db import SPEC08_LINK, V04Gateway, exercise_case_matrix
from tests.integration.test_m5_spec08_delivery_db import RECIPIENT, recipient_turn
from tests.integration.test_m5_spec08_readback_db import FRAGMENT, OPENING, ReadbackGateway, knows_fragment


pytestmark = pytest.mark.integration
BANK = json.loads((BATTERY_V06_PACKAGE / "case-package.json").read_bytes())

TASKS = "Сопоставляю способы проверки заявок по журналам объёма, срокам и полноте подтверждённых заключений."
DECISIONS = "Сопоставил два способа проверки по журналу заявок и рекомендовал пробу с дополнительной сверкой перед обещанием срока заказчику."
AUTHORITY = "Изучаю источники, самостоятельно рекомендую следующий шаг, предлагаю проверку и задаю предварительные условия. Срок утверждает владелец процесса, соответствие подтверждает инженер."

M05_BASIS = ("Ирина, инженер проверки, 23 ноября, протокол 2, выполнено. В журнале тестового потока B "
             "500 обработанных заявок за пять рабочих дней 16–20 ноября. ")
M05_SEPARATE = ("В отдельном однодневном прогоне 20 ноября по журналу стенда за полную рабочую смену "
               "измерено 112 завершённых заявок другой партии. ")
M05_DERIVED = "Средний выпуск этой же пятидневной серии по расчёту — 112 заявок за рабочий день. "
M05_LIMIT = ("Журнал подтверждает результат обработки в тесте. Перенос журнала и полноту следа в текущем потоке не проверяли. "
             "Ирина может сверить полноту следа на текущей выборке 24 ноября до 12:00.")
M05_CHECK = "invariant:CASE.SPEC.02.I05"
M05_PATH = "candidate_as/Материалы/M05/Текст"

SPEC02_MATERIALS = {
    "P00": ("Вводная и письменное задание", "В рамках контроля обработки вы сопоставляете способы проверки заявок по журналам. "
            "Сегодня 23 ноября, 09:00. Изучите M01–M06 и к 15:00 напишите коллеге рабочую рекомендацию. "
            "Подготовьте отдельно короткий черновик для заказчика со статусом и следующим шагом к 16:00. "
            "Вы можете предложить проверку и предварительные условия. Срок утверждает владелец процесса Олег, "
            "соответствие подтверждает инженер Ирина. Если формулировка в документах неясна, задайте вопрос здесь."),
    "M01": ("Запрос заказчика", "Светлана, заказчик, 23 ноября, 09:00. Утверждены требования: к 27 ноября 16:00 "
            "нужны 500 проверенных заявок этой партии и полный след сверки по каждой записи. "
            "К 23 ноября 16:00 просим сообщить текущий статус и следующий шаг."),
    "M02": ("Исходное предложение A", "Николай, владелец A, 20 ноября, версия 1, план. "
            "Для 500 заявок текущей партии запланированы проверка и полный контрольный след к 27 ноября 16:00. "
            "Плановые трудозатраты на весь объём — 24 часа специалиста. Производственный запуск ещё не согласован."),
    "M03": ("Уточнение по варианту A", "Николай, владелец A, 23 ноября, версия 2, актуальный план. "
            "Проверяющий доступен позже, поэтому для тех же 500 проверенных заявок и полного следа "
            "актуальный срок — 30 ноября 16:00. Плановые трудозатраты остаются 24 часа специалиста."),
    "M04": ("Предложение B", "Анна, владелец B, 23 ноября, версия 1, предложение. "
            "План — проверить 500 заявок текущей партии к 27 ноября 16:00, плановые трудозатраты — 32 часа специалиста "
            "за весь объём. Предусмотрен автоматический перенос контрольного следа. Полнота переноса для текущей партии не подтверждена."),
    "M05": ("Записка о профильной проверке", M05_BASIS + M05_SEPARATE + M05_LIMIT),
    "M06": ("Письменное сообщение коллеги", "Денис, коллега, 23 ноября, 10:00, рабочая рекомендация. "
            "В обоих планах на всю партию у A указано 24 часа, у B — 32 часа. Я бы выбрал A по трудозатратам "
            "и на этом согласовал выбор способа для заказчика."),
}
DOCUMENTS = {
    "CASE.SPEC.02": SPEC02_MATERIALS,
    "CASE.SPEC.03": {
        "P00": ("Вводная и инструкция", "В общем чате C1, C2 и C3 договоритесь, как подготовить ответ по пакету проверки заявок. "
                "Вы сверяете свой участок и предлагаете порядок, общий ответ отправят после обсуждения."),
        "M01": ("Актуальный запрос заказчика", "Ольга, заказчик, 23 ноября 09:00, версия 2. Нужен статус по 24 заявкам к 13:30. "
                "Окончательный ответ после подтверждения полноты списка и способа проверки."),
        "M02": ("Текущий свод", "Свод C2 в 10:20. Первая часть всё ещё ссылается на 18 заявок из версии 1. "
                "Во второй записали, что сверка C3 завершена, хотя C3 готовность ещё не подтвердил. Свод помечен готовым."),
        "M03": ("Позиции и зависимость работ", "C1: пересчитаю актуальный список между 11:30 и 12:00. "
                "C3: проверю условия с 12:00 до 12:45 после получения списка и состава запроса. "
                "C2: могу обновить свод с 12:45 до 13:15 после обоих подтверждений."),
        "M04": ("Позднее уточнение запроса", "В версии 3 остаются 24 заявки, но в пяти из них нужна отдельная сверка "
                "даты закрытия вместо проверки только статуса. Статус по-прежнему нужен к 13:30. "
                "Автор — Ольга, заказчик, 23 ноября 11:15. Сообщение получила C2."),
    },
    "CASE.SPEC.05": {
        "P00": ("Роль и инструкция", "Вы сверяете результаты ускоренной обработки заявок. Обсудите с одним коллегой, "
                "как продолжить работу после отказа от привычного способа, и выскажите обоснованную рекомендацию."),
        "M01": ("Обращение заказчика", "Заказчик ждёт к пятнице стабильных результатов обработки. Полная остановка "
                "для проверки отклонена, потому что очередь продолжит расти. Цель сохраняется."),
        "M02": ("Два эпизода", "20 ноября сотрудник отметил потерю карточки после обновления. 23 ноября клиент сообщил "
                "о задержке уведомления, но карточка открывалась. Общую причину не проверяли."),
        "M03": ("Ресурсы и нагрузка", "Сверка журнала — 30 минут работы специалиста. Локальная проба на двух карточках — 45 минут, "
                "наблюдение за текущей обработкой — 20 минут коллеги, изменение порядка — от часа и с разрешением владельца."),
        "M04": ("Время и согласование", "Коллега доступен с 14:00 до 14:30, на согласование подхода — до 16:00. "
                "Выделение работников и изменение процесса согласует владелец. Подтверждения ещё нет."),
        "M05": ("Первая реплика коллеги", "Раз остановка исключена и времени мало, я бы закрыл запрос. Как считаешь?"),
    },
    "CASE.SPEC.06": {
        "P00": ("Вводная и инструкция", "Вы помогаете подготовить одну общую пробу проверки карточек. Обсудите в чате с тремя "
                "сторонами предварительный замысел и зафиксируйте, что удалось согласовать. Саму пробу здесь не проводим."),
        "M01": ("Ресурсы пробы", "Одна проба до 30 минут на четырёх закрытых карточках. C1 готовит средство в четверг 09:00–09:30. "
                "Работники C2 доступны в 10:00–10:30 или 14:00–14:30. C3 сможет изучить записи после 15:00. "
                "Предварительная договорённость нужна в среду к 16:00."),
        "M02": ("Ожидания сторон", "C1 хочет убедиться, что журнал открывается с обычными правами. C2 нужно понять, облегчает ли он "
                "поиск в пределах 30 минут рабочей группы. C3 просит записи о времени и случаях без результата."),
        "M03": ("Наблюдение и пределы", "C1 в понедельник открыл одну учебную карточку с расширенными правами. Это предварительная "
                "проверка, рабочих условий не проверяли. C2 предлагает искать карточку не дольше двух минут. Будущая проба может "
                "записать время до открытия и отсутствие результата в журнале."),
    },
}
ANSWER = ("Коллеге. Сначала предлагаю сверку полноты следа у Ирины 24 ноября. План B даёт 27 ноября, "
          "но тестовый журнал на другой выборке не подтверждает перенос следа в текущем потоке. По A 24 часа, а не 32, "
          "и полный след предусмотрен, однако актуальный срок 30 ноября вместо требуемых 27. "
          "Часы специалиста сами по себе не подтверждают срок. B рассмотрю после сверки. "
          "Если сверка не пройдёт, предложу владельцу согласовать с заказчиком перенос срока для A. "
          "До решения владельца дату не обещаю.")


class ControlledV06Gateway(V04Gateway):
    def __init__(self, *, wrong_average=False):
        super().__init__()
        self.wrong_average = wrong_average

    def chat(self, messages, **kwargs):
        # The product still checks the cited profile field and literal quote.
        data = json.loads(messages[-1]["content"])
        return json.dumps({"cases": {case_id: {
            key: {"status": "supported", "field": criterion["fields"][0],
                  "quote": data["profile"][criterion["fields"][0]]}
            for key, criterion in criteria.items()
        } for case_id, criteria in data["cases"].items()}}, ensure_ascii=False)

    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        routing, _, data = self.calls[-1]
        if ":generation:" in routing and (documents := DOCUMENTS.get(data["case"]["CaseID"])):
            candidate = json.loads(response.content)
            for material in candidate["Материалы"]:
                material["Название"], material["Текст"] = documents[material["MaterialID"]]
                if self.wrong_average and material["MaterialID"] == "M05":
                    material["Текст"] = M05_BASIS + M05_DERIVED + M05_LIMIT
            response.content = json.dumps(candidate, ensure_ascii=False)
        return response

    def review_response(self, routing, payload, checks):
        if payload["candidate_as"]["CaseID"] == "CASE.SPEC.02":
            for row in checks:
                if row["check_id"] != M05_CHECK:
                    continue
                row["evidence_paths"] = [M05_PATH]
                if self.wrong_average:
                    reason = "Для той же серии 500 / 5 = 100, а M05 ошибочно выводит среднее 112."
                    row.update(status="FAIL", reason=reason, findings=[{
                        "code": "NUMERIC_BASIS_CONTRADICTION", "severity": "blocking", "paths": [M05_PATH],
                        "reason": reason, "requirement_ref": M05_CHECK, "expected": "500 / 5 = 100",
                        "actual": "112 выведено из той же серии",
                    }])
                else:
                    reason = "500 за пять дней и 112 за одну смену относятся к разным сериям по указанным журналам."
                    row.update(reason=reason, adversarial_review={"candidate_conflicts": [M05_PATH], "resolution": reason})
        return super().review_response(routing, payload, checks)


@pytest.fixture
def v06_profile(product_db):
    with product_db() as connection:
        def publish():
            return publish_diagnostic_battery(
                connection, published_by=99, organization_id=10, catalog_id="specialist-battery-v06-diagnostic",
                catalog_version="0.9-qa.1", idempotency_key="m5-v06-controlled-scenario-matrix",
                decision_basis="SYNTHETIC SCENARIO CHECK", battery_version="v0.6",
            )

        published = publish()
        assert publish()["catalog"]["idempotent"]
        assert {row["status"] for row in published["readback"]["cases"]} == {"WORKING"}
        connection.execute("ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT")
        connection.execute("""INSERT INTO assessment_configurations
            (id,methodology_version_id,status,code,name,catalog_version_id)
            VALUES (2,1,'published','m5-v06-qa','SYNTHETIC M5 v0.6 QA',%s)""",
                           (published["catalog"]["catalog_db_id"],))
        context = connection.execute("""SELECT organization_context_version_id
            FROM assessment_personalized_profiles WHERE id=%s""", (product_db.profile_id,)).fetchone()
        role = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id
            WHERE r.code='specialist_expert' AND r.scope='base' AND v.status='published'""").fetchone()["id"]
        context_id = create_user_context_draft(connection, user_id=99, identity={"full_name": "QA Synthetic"}, professional={
            "regular_tasks": TASKS, "decision_situations": DECISIONS, "constraints_and_interactions": AUTHORITY,
            "additional_information": {"professional_recommendation": {"confirmed": True, "basis": "Синтетическая роль QA"}},
        })
        confirm_user_context(connection, version_id=context_id, user_id=99)
        profile = create_personalized_profile(connection, user_id=99, assessment_configuration_id=2,
                                              user_context_version_id=context_id, role_profile_version_id=role, **context)
        connection.commit()
    return profile["id"]


def export(name, value):
    if directory := os.environ.get("M5_V06_EVIDENCE_DIR"):
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, default=str, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("number", range(1, 10))
def test_v06_case_matrix(product_db, v06_profile, number):
    cycle, session = create_case(product_db, v06_profile, number)
    exercise_case_matrix(product_db, cycle, session, number, gateway=ControlledV06Gateway(),
                         scenario=ROOT / BATTERY_V06_SCENARIO_PACKAGE, export_trace=export, spec02_answer=ANSWER)


def create_case(product_db, profile, number):
    case = BANK["cases"][number - 1]
    with product_db() as connection:
        cycle, session = create_cycle_session_for_case(
            connection, personalized_profile_id=profile, case_id=case["case_id"], case_version=case["version"],
            created_by=99, usage_scope="qa", diagnostic=True, scenario_tests=True,
        )
        connection.commit()
    return cycle, session


def test_v06_spec02_rejects_the_wrong_derived_average_when_reviewers_find_it(product_db, v06_profile):
    cycle, _ = create_case(product_db, v06_profile, 2)
    as_id = str(uuid4())
    gateway = ControlledV06Gateway(wrong_average=True)
    saved = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=as_id,
                         actor=99, gateway=gateway)
    assert saved["status"] == "preparation_rejected"
    prepared = saved["preparation_trace"]
    assert prepared["tester"]["aggregation"]["status"] == "FAIL"
    assert prepared["repair"]["outcome"] == "FAIL"
    for reviewer in ("tester", "challenger"):
        row = next(item for item in prepared["tester"]["independent_checks"][reviewer] if item["check_id"] == M05_CHECK)
        assert row["status"] == "FAIL" and row["findings"][0]["code"] == "NUMERIC_BASIS_CONTRADICTION"
    definitions = [item for _, _, payload in gateway.calls
                   for item in ((payload.get("applicability_plan") or {}).get("required_checks")
                                or payload.get("protected_checks", ())) if item["check_id"] == M05_CHECK]
    assert len(definitions) == 4
    assert all("500 / 5 = 100" in item["requirement"]["case_content"] for item in definitions)
    with product_db() as connection:
        assert connection.execute("SELECT 1 FROM m5_assessment_situations WHERE assessment_situation_id=%s", (as_id,)).fetchone() is None
    export("CASE.SPEC.02/numeric-contradiction.json", {
        "gateway": "SYNTHETIC CONTROLLED", "input": M05_BASIS + M05_DERIVED + M05_LIMIT,
        "prepared": prepared, "review_definitions": definitions,
    })


def test_v06_spec08_resumes_the_same_addressed_delivery_before_confirmation(product_db, v06_profile):
    cycle, session = create_case(product_db, v06_profile, 8)
    as_id, _ = prepare_and_start(product_db, cycle, session, ReadbackGateway())
    text = f"Получатель, передаю {SPEC08_LINK}."
    events, requests = submit(product_db, as_id, text, {
        "E01_RECEIPT": matched(recipient_ids=[RECIPIENT], text=SPEC08_LINK),
    }, recipients=(RECIPIENT,), responses={RECIPIENT: "Ссылку вижу. Открою позже."}, replay=True)
    assert all(not knows_fragment(request) for request in requests)
    with product_db() as connection:
        before = trace(connection, as_id)["state"]["state_json"]
        transition(connection, assessment_situation_id=as_id, action="pause", reason="synthetic", request_id="test-pause")
        transition(connection, assessment_situation_id=as_id, action="resume", reason="synthetic", request_id="test-resume")
        resumed = trace(connection, as_id)["state"]["state_json"]
        connection.commit()
    assert resumed["battery_pending_materials"] == before["battery_pending_materials"]
    assert not resumed.get("battery_opened_materials")
    opening, _ = submit(product_db, as_id, "Вы уже открыли ранее присланную ссылку?", {
        "E04_CLARIFY": matched(speaker_ids=[RECIPIENT]), "@follow_up:E01_RECEIPT": matched(),
        "@confirmed:E01_RECEIPT": matched(), "@opened:E01_RECEIPT": matched(text=OPENING),
    }, recipients=(RECIPIENT,), responses={RECIPIENT: OPENING}, replay=True)
    after = recipient_turn(product_db, as_id, "Что именно вы получили?")
    assert knows_fragment(after)
    acquired, = after["context"]["opened_materials"]
    assert acquired["recipient_id"] == RECIPIENT and acquired["text"] == FRAGMENT
    assert acquired["delivery_event_id"] == str(events[0]["event_id"])
    export("CASE.SPEC.08/resumed-private-link.json", {
        "input": text, "before_pause": before, "after_resume": resumed,
        "delivery": events, "opening": opening, "acquisition": acquired,
    })
