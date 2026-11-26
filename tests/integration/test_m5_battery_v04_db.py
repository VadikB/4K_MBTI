"""M5 v0.4 with controlled gateways and an isolated PostgreSQL schema."""

import json
import os
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest

from Api.assessment_contexts import create_personalized_profile
from Api.cycle_execution_manifest import (
    BATTERY_V04_SCENARIO_182, BATTERY_V04_SCENARIO_CURRENT, BATTERY_V04_SCENARIO_PACKAGE, BATTERY_V04_SCENARIO_PATCH,
    ROOT, battery_scenario_ref, build_manifest, resolve_cycle_dependency, resolve_dependency,
)
from Api.m5_battery_contract import load_scenario
from Api.m5_battery_preparation import prepare_next
from Api.m5_case_runtime import checksum
from Api.m5_catalog_integrity import resolve_configuration_catalog
from Api.m5_cycle_runtime import create_cycle_session_for_case
from Api.m5_functional_generation_service import checksum as review_checksum, review_dispatches_match
from Api.m5_passport_generation import read_as_package
from Api.m5_scenario_runtime import build_c45, trace, transition
from Api.m7_cycle_planner import _catalog, ranked_route
from Api.m7_planning_package import load_rules, methodology_targets
from scripts.plan_specialist_program_release import (
    ADMISSION_EVIDENCE, BATTERY_V04_PACKAGE, BATTERY_V04_RUNTIME, build_trace,
    publish_admitted_catalog, publish_diagnostic_battery,
)
from tests.integration.test_m5_battery_scenario_db import (
    PreparationGateway, cycle_for, ids, matched, prepare_and_start, specialist, submit,
)
from tests.integration.test_m10_product_path_db import product_db
from tests.unit.test_m5_pilot_review import CONSENT_CHECK, CONSENT_FIELD, PilotGateway


pytestmark = pytest.mark.integration
BANK = json.loads((BATTERY_V04_PACKAGE / "case-package.json").read_bytes())
SCENARIO = ROOT / BATTERY_V04_SCENARIO_CURRENT
SPEC08_LINK = "m5-material://M02/4"
REVIEW = ROOT / "assessment_definitions/prompts/m5_functional_passport/v7"
CURRENT_FRAGMENT = "Версия 4. Пакет проверен для 24 записей при ручной сверке. Автоматический запуск не проверялся."
RECIPIENT_CARD = "Карточка передачи показывает версию 3. Владелец карточки — координатор."
RECIPIENT_WINDOW = "Получатель доступен с 14:00 до 14:20. Можно подготовить черновик. Допуск ещё открыт."

MATERIALS = {
    1: {
        "P00": "На 9:00 получен неоднозначный запрос. Уточните его и согласуйте следующий рабочий шаг.",
        "M01": "Письмо заказчика. Нужно, чтобы после изменения сотрудники быстрее находили нужную карточку.",
        "M02": "Черновик. Предлагаемый ориентир — 8 из 10 поисков за две минуты. Контроль ещё не проводился.",
    },
    4: {
        "P00": "Обсудите с заказчиком возможные способы продолжить работу и выберите следующий шаг.",
        "M01": "Из-за ошибки в выгрузке заказчик не смог вовремя сверить данные перед встречей.",
        "M02": "Проверяющий подтвердил исправление в выгрузке от понедельника. Соседний участок не проверялся.",
        "M03": "Руководитель готов рассмотреть альтернативу. Повтор прежнего порядка заранее не согласован.",
        "M04": "Заказчик может выделить 15 минут на сверку. Дополнительные расходы требуют внешнего решения.",
        "M05": "Ошибку исправили, но время всё равно потеряно. Как предлагаете продолжить?",
    },
    7: {
        "P00": "Письменно объясните рабочее отклонение и обоснуйте дальнейшее решение по имеющимся материалам.",
        "M01": "Запись проверки. На тестовом участке удалось открыть средство и создать пробную запись.",
        "M02": "Из 12 сотрудников доступ имели 9. Полный рабочий результат за неделю зафиксирован у 3.",
        "M03": "Свидетельство принимающей стороны. Два показанных результата использованы. Остальные она не видела.",
        "M04": "Владелец сообщает, что при проверке использовались пробные данные. Практику всех сотрудников не проверяли.",
    },
    8: {
        "P00": "Обсудите с коллегами передачу текущей работы. Общий отсчёт — 14:00.",
        "M01": "Предыдущая передача шла через общую карточку. Получатель готовит следующий рабочий шаг.",
        "M02": f"[Актуальный профильный фрагмент]\n{CURRENT_FRAGMENT}\n\n"
               f"[Исходная карточка]\n{RECIPIENT_CARD}\n\n"
               f"[Окно и подготовка получателя]\n{RECIPIENT_WINDOW}\n\n"
               "[Остальные условия]\nАвтор доступен до 14:15. К 14:25 нужен статус подготовки. "
               "Исполнение требует внешнего допуска владельца процесса. Ответа пока нет.",
        "M03": "Автор сообщает, что актуальная версия — 4. Получатель видит в карточке версию 3 и просит уточнение.",
    },
    9: {
        "P00": "Уточните позицию руководителя и представьте профессиональную рекомендацию в рамках своего мандата.",
        "M01": "У команды уже есть очередь задач. Проверить работу новичка можно один раз в конце первой недели.",
        "M02": "В первом образце кандидат пропустил сверку. После замечания исправил её. Повторной независимой проверки не было.",
        "M03": "Руководитель: мне важно, сможет ли кандидат вести эту очередь самостоятельно. Каково ваше мнение?",
    },
}


def export(name, value):
    directory = os.environ.get("M5_V04_EVIDENCE_DIR")
    if directory:
        output = Path(directory) / name
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, ensure_ascii=False, default=str, indent=2) + "\n")


class V04Gateway(PilotGateway):
    def chat_with_trace(self, messages, **kwargs):
        result = super().chat_with_trace(messages, **kwargs)
        if ":generation:" not in kwargs["routing_key"]:
            return result
        body = self.calls[-1][2]
        number = int(body["case"]["CaseID"].split(".")[-1])
        candidate = json.loads(result.content)
        archive = os.environ.get("M5_V04_LEGACY_EVIDENCE_ZIP")
        if number not in MATERIALS and archive:
            with ZipFile(archive) as source:
                prior = json.loads(source.read(f"evidence05/v5/CASE.SPEC.{number:02d}/candidate.json"))
            for field in ("Материалы", "Активные персонажи", "Закрытые фиксированные факты"):
                assert candidate[field] == [] or len(candidate[field]) == len(prior[field])
                candidate[field] = prior[field]
        for material in candidate["Материалы"]:
            material["Текст"] = MATERIALS.get(number, {}).get(material["MaterialID"], material["Текст"])
            if number == 8 and material["MaterialID"] == "M02" and body["scenario_contract"].get("material_source"):
                material["Текст"] = material["Текст"].replace("[Актуальный профильный фрагмент]\n",
                                                               "[Актуальный профильный фрагмент]\nВерсия: 4\n")
                material["Текст"] += f" Адресная ссылка доступна получателю на чтение.\n{SPEC08_LINK}"
        if number == 1:
            facts = {"F04": "Целевой эффект — 8 из 10 поисков не дольше двух минут.",
                     "F05": "Причину задержки ещё не подтвердили. Зафиксированы три повторных поиска."}
            for fact in candidate["Закрытые фиксированные факты"]:
                fact["Текст"] = facts.get(fact["FactID"], fact["Текст"])
        result.content = json.dumps(candidate, ensure_ascii=False)
        return result

    def review_response(self, routing, payload, checks):
        for row in checks:
            if row["check_id"] == CONSENT_CHECK:
                row["evidence_paths"] = [CONSENT_FIELD]
        return super().review_response(routing, payload, checks)


@pytest.fixture
def v04(product_db, specialist):
    with product_db() as connection:
        published = install_v04(connection)
        replay = install_v04(connection)
        assert replay["catalog"]["idempotent"] and replay["catalog_readback"] == published["catalog_readback"]
        assert {row["status"] for row in published["readback"]["cases"]} == {"WORKING"}
        catalog_id = published["catalog"]["catalog_db_id"]
        connection.execute("""INSERT INTO assessment_configurations
            (id,methodology_version_id,status,code,name,catalog_version_id)
            VALUES (3,1,'published','m5-v04-qa','SYNTHETIC M5 v0.4 QA',%s)""", (catalog_id,))
        profiles = []
        for previous in specialist:
            context = connection.execute("""SELECT organization_context_version_id,user_context_version_id,
                role_profile_version_id FROM assessment_personalized_profiles WHERE id=%s""", (previous,)).fetchone()
            profiles.append(create_personalized_profile(connection, user_id=99, assessment_configuration_id=3, **context)["id"])
        connection.commit()
    return profiles, catalog_id


def install_v04(connection):
    return publish_diagnostic_battery(
        connection, published_by=99, organization_id=10, catalog_id="specialist-battery-diagnostic",
        catalog_version="0.8-qa.3", idempotency_key="m5-v04-synthetic-183", decision_basis="SYNTHETIC QA", battery_v04=True,
        scenario_ref=battery_scenario_ref(BATTERY_V04_SCENARIO_CURRENT),
    )


def start_case(product_db, profile, number, *next_cases):
    case = BANK["cases"][number - 1]
    route = [BANK["cases"][item - 1] for item in next_cases]
    with product_db() as connection:
        cycle, session = create_cycle_session_for_case(
            connection, personalized_profile_id=profile, case_id=case["case_id"], case_version=case["version"],
            created_by=99, usage_scope="qa", diagnostic=True, scenario_tests=True,
            next_cases=tuple((item["case_id"], item["version"]) for item in route),
        )
        connection.commit()
    return cycle, session


@pytest.mark.parametrize("number", range(1, 10))
def test_v04_case_matrix(product_db, v04, number):
    cycle, session = start_case(product_db, v04[0][0], number)
    assert resolve_cycle_dependency(cycle, "m5_battery_scenario") == SCENARIO
    assert resolve_cycle_dependency(cycle, "m5_functional_as") == REVIEW
    replacement = [{"Место": "17.2/M02", "Источник": "синтетический контекст M4",
                    "Что заменено": "рабочий пример", "Предел": "границы проверки сохранены"}]
    gateway = V04Gateway(initial="Абзац вместо массива", repaired=replacement) if number == 7 else V04Gateway()
    as_id, saved = prepare_and_start(product_db, cycle, session, gateway)
    payload = saved["execution_payload"]
    generation = payload["ai_operations"]["functional_personalization"]
    accepted = generation["accepted_as"]
    design = payload["runtime_rules"]["battery_scenario"]
    tester = generation["tester"]
    assert tester["aggregation"]["status"] == "PASS"
    assert {role: {row["status"] for row in rows} for role, rows in tester["independent_checks"].items()} == {
        "tester": {"PASS"}, "challenger": {"PASS"},
    }
    roles = {}
    for _, _, body in gateway.calls:
        if dispatch := body.get("review_dispatch"):
            roles.setdefault(dispatch["reviewer"], []).extend(dispatch["check_ids"])
            assert review_checksum(body["candidate_as"]) == generation["candidate_checksum"]
    required = [row["check_id"] for row in tester["independent_checks"]["tester"]]
    assert roles == {"tester": required, "challenger": required}
    assert review_checksum(accepted) == generation["candidate_checksum"]
    assert review_dispatches_match(tester, candidate_sha256=generation["candidate_checksum"],
                                   review_round=2 if number == 7 else 1)
    with product_db() as connection:
        opening = trace(connection, as_id)
    assert opening["state"]["state_json"]["disclosed_materials"] == design["start_ids"]
    steps = []

    def turn(text, rules, **kwargs):
        events, calls = submit(product_db, as_id, text, rules, **kwargs)
        steps.append({"input": text, "events": events, "character_requests": calls})
        return events, calls

    if number == 1:
        customer = {"speaker_ids": ["CUSTOMER"]}
        effects, calls = turn("Какой наблюдаемый эффект для вас будет достаточным?", {
            "E02_REPLY": matched(**customer, fact_ids=["F04"]),
        }, responses={"CUSTOMER": "Нужно 8 из 10 поисков не дольше двух минут."})
        assert ids(effects) == ["E02_REPLY"] and "8 из 10" in effects[0]["payload_json"]["response"]
        assert calls[0]["character"]["known_facts"][-1] == design["concrete_facts"]["F04"]
        effects, calls = turn("Причину уже подтвердили отдельной проверкой?", {
            "E03_CAUSE_LIMIT": matched(**customer, fact_ids=["F05"]),
        }, responses={"CUSTOMER": "Причину пока не подтвердили. Наблюдали три повторных поиска."})
        assert ids(effects) == ["E03_CAUSE_LIMIT"]
        assert calls[0]["character"]["known_facts"][-1] == design["concrete_facts"]["F05"]
        effects, _ = turn("Предлагаю сверить критерий эффекта на десяти поисках с владельцем. Как продолжим?",
                          {"E01_DOCUMENT": matched()}, replay=True)
        assert ids(effects, "mandatory_update") == ["E01_DOCUMENT"]
        assert "Черновик" in effects[0]["payload_json"]["content"]["text"]
        assert not turn("Ещё раз обсудим ту же сверку?", {"E01_DOCUMENT": matched()})[0]
    elif number == 2:
        effects, _ = turn("Где в предъявленном пакете зафиксирован предел проверки B?",
                          {"E01_FACT": matched(speaker_ids=["FACILITATOR"])},
                          responses={"FACILITATOR": "Предел описан в M05. За него наблюдение не распространяется."})
        assert ids(effects) == ["E01_FACT"]
    elif number == 3:
        turn("Коллеги C1, C2 и C3, сверим обновлённые условия вместе?", {
            "E01_UPDATE": matched(speaker_ids=["C1", "C2", "C3"]),
            "E03_REPLY": matched(speaker_ids=["C1", "C2", "C3"]),
        }, recipients=("C1", "C2", "C3"))
        material = design["concrete_materials"]["M04"]["Текст"]
        quote = material.split("\n\n", 1)[-1].split(". ", 1)[0].lstrip("«")
        _, calls = turn("C3, можно уточнить ваш вклад перед пересылкой?", {
            "E03_REPLY": matched(speaker_ids=["C3"]),
        }, recipients=("C3",))
        assert quote not in json.dumps(calls, ensure_ascii=False)
        effects, _ = turn("C2, перешлите C3 конкретный фрагмент сейчас: " + quote, {
            "E02_FORWARD": matched(recipient_ids=["C3"], text=quote), "@accepted": matched(),
        }, recipients=("C2",), responses={"C2": "Направляю C3 сейчас."}, replay=True)
        assert ids(effects, "information_transferred") == ["E02_TRANSFER"]
        _, calls = turn("C3, меняет ли переданный фрагмент ваш вклад?", {
            "E03_REPLY": matched(speaker_ids=["C3"]),
        }, recipients=("C3",))
        assert any(item["content_text"] == quote for item in calls[0]["context"]["dialogue_history"])
    elif number == 4:
        assert "возможные способы" in design["concrete_materials"]["P00"]["Текст"]
        customer = matched(speaker_ids=["CUSTOMER"])
        effects, _ = turn("Сможете выделить полчаса на сверку до встречи?", {
            "E01_REVIEW": customer, "E01_STATE_LIMIT": customer, "E01_CONSENT_STEP": customer,
        }, responses={"CUSTOMER": "Готов обсудить, но на сверку у меня 15 минут. Шаг пока не согласован."})
        assert "15 минут" in effects[0]["payload_json"]["response"]
        assert "E01_CONSENT_STEP" not in effects[0]["payload_json"]["scenario_event_ids"]
        effects, _ = turn("Тогда сверим только исправленный участок за 15 минут. Вы согласны на этот шаг?", {
            "E02_REVISION": customer, "E01_CONSENT_STEP": customer, "@confirmed:E01_CONSENT_STEP": matched(),
        }, responses={"CUSTOMER": "Согласен сверить исправленный участок за 15 минут. Исполнение дальше не утверждено."})
        assert {"E02_REVISION", "E01_CONSENT_STEP"} <= set(effects[0]["payload_json"]["scenario_event_ids"])
        assert "не утверждено" in effects[0]["payload_json"]["response"]
    elif number == 5:
        effects, _ = turn("Можно проверить один участок отдельно или объединить материалы. Какой вклад возможен?", {
            "E01_COLLEAGUE": matched(speaker_ids=["C1"]), "E03_SUPPORT": matched(speaker_ids=["C1"]),
            "@confirmed:E03_SUPPORT": matched(),
        }, responses={"C1": "Согласен обсудить варианты в своё окно. Ресурс выделяет владелец."})
        assert set(effects[0]["payload_json"]["scenario_event_ids"]) == {"E01_COLLEAGUE", "E03_SUPPORT"}
    elif number == 6:
        effects, _ = turn("Что каждая сторона может подготовить для общей пробы?", {
            "E01_DISCUSS": matched(speaker_ids=["C1", "C2", "C3"]),
        }, recipients=("C1", "C2", "C3"))
        assert {event["payload_json"]["speaker_id"] for event in effects} == {"C1", "C2", "C3"}
        effects, _ = turn("C1, возьмёте подготовку?", {
            "E01_ACCEPT": matched(speaker_ids=["C1"]), "@confirmed:E01_ACCEPT": matched(),
        }, recipients=("C1",), responses={"C1": "Подготовку беру. Пробу пока не проводили."})
        assert ids(effects) == ["E01_ACCEPT"]
    elif number == 7:
        assert accepted["Применённые замены"] == replacement and generation["repair"]
        assert "обоснуйте" in design["concrete_materials"]["P00"]["Текст"]
        assert "доступ имели 9" in design["concrete_materials"]["M02"]["Текст"]
        effects, _ = turn("Что из предъявленного действительно проверено?", {
            "E01_EXPLAIN": matched(speaker_ids=["FACILITATOR"]),
        }, responses={"FACILITATOR": "В M01 проверялась пробная запись. В M03 зафиксировано использование двух результатов."})
        assert ids(effects) == ["E01_EXPLAIN"]
    elif number == 8:
        recipient = "R_RECIPIENT"
        pending = {"E04_CLARIFY": matched(speaker_ids=[recipient])}
        effects, calls = turn("Получатель, знаете ли исходную карточку и своё окно?", pending, recipients=(recipient,),
                              responses={recipient: "Вижу карточку версии 3. До 14:20 могу подготовить черновик."})
        assert ids(effects) == ["E04_CLARIFY"]
        before = json.dumps(calls[0], ensure_ascii=False)
        assert RECIPIENT_CARD in before and RECIPIENT_WINDOW in before and CURRENT_FRAGMENT not in before
        assert CURRENT_FRAGMENT in design["concrete_materials"]["M02"]["Текст"]
        for message in ("Обещаю прислать позже. Успеете?",
                        "Вот ссылка без права чтения https://example.invalid/spec08. Доступа пока нет?"):
            effects, calls = turn(message, pending, recipients=(recipient,))
            assert not ids(effects, "information_transferred")
            assert CURRENT_FRAGMENT not in json.dumps(calls, ensure_ascii=False)
        effects, calls = turn(f"Направляю получателю актуальный текст. {CURRENT_FRAGMENT}", {
            "E01_RECEIPT": matched(recipient_ids=[recipient], text=CURRENT_FRAGMENT), "@confirmed:E01_RECEIPT": matched(),
        }, recipients=(recipient,), responses={recipient: "Получил версию 4 и условие ручной сверки."}, replay=True)
        assert [event["event_type"] for event in effects] == ["information_transferred", "character_response"]
        assert effects[0]["payload_json"]["text"] == CURRENT_FRAGMENT
        assert CURRENT_FRAGMENT in calls[0]["assessee_turn"]["content"]
        effects, calls = turn("Хватит ли полученного для черновика, можно ли начать исполнение?", {
            "E01_HANDOVER": matched(speaker_ids=[recipient]), "@confirmed:E01_HANDOVER": matched(),
            "E03_PENDING": matched(speaker_ids=[recipient]),
        }, recipients=(recipient,), responses={recipient: "Полученного хватает на черновик. Начну подготовку сейчас. Исполнение ждёт допуска."})
        assert any(CURRENT_FRAGMENT in item["content_text"] for item in calls[0]["context"]["dialogue_history"])
        assert set(effects[0]["payload_json"]["scenario_event_ids"]) == {"E01_HANDOVER", "E03_PENDING"}
        assert not ids(effects, "information_transferred")
        effects, _ = turn("Тогда версия 4 уже проверена на автоматическом запуске, верно?", {
            "E02_CORRECT": matched(speaker_ids=[recipient]),
        }, recipients=(recipient,), responses={recipient: "Версия 4 проверена при ручной сверке. Автоматический запуск не проверялся."})
        assert ids(effects) == ["E02_CORRECT"]
    else:
        manager = matched(speaker_ids=["R_MANAGER"])
        assert sum(event["material_id"] == "M03" for event in opening["events"]) == 1 and not opening["turns"]
        effects, _ = turn("Какое уже известное условие для вас самое существенное?", {"E01_MANAGER": manager},
                          responses={"R_MANAGER": "Очередь растёт, а проверку сможем сделать один раз. Поэтому важна самостоятельность."})
        assert ids(effects) == ["E01_MANAGER"]
        effects, _ = turn("Рекомендую сверить исправленный образец, прежде чем говорить о самостоятельности. Согласны?", {
            "E02_BOUNDARY": manager, "E01_MANAGER": manager,
        }, responses={"R_MANAGER": "Согласен сверить исправление. Повторной проверки не было, решения о найме пока нет."})
        assert "решения о найме пока нет" in effects[0]["payload_json"]["response"]
        effects, _ = turn("Какой отдельный итог по кандидату вы фиксируете?", {"E01_MANAGER": manager},
                          responses={"R_MANAGER": "Моё кадровое решение сейчас — отложить решение о найме до повторной проверки."})
        assert "Моё кадровое решение" in effects[0]["payload_json"]["response"]

    written_answers = {
        2: "Коллеге. В M05 для B отражено среднее 112 заявок в рабочий день в границах тестового потока. "
           "Это не подтверждает мощность в дальнейшей эксплуатации. Перед рекомендацией заказчику "
           "я сверю с инженером способ измерения и сопоставимость потока с нашим объёмом. "
           "До уточнения предложу заказчику условный следующий шаг и укажу, что предел проверки остаётся открытым.",
        7: "В рабочем режиме 9 из 12 сотрудников имели доступ, но полный результат зарегистрирован у 3. "
           "Пробная запись подтверждает только возможность создать запись. Возможные причины отклонения — ограничение "
           "процесса после получения доступа либо другой состав рабочих задач. Проверю цепочку до результата на небольшой "
           "группе пользователей и сверю, какие результаты приняла принимающая сторона. До проверки причину считаю гипотезой.",
    }
    final_text = (written_answers[number] + " Сдаю эту запись как итог." if number in written_answers
                  else "Сдаю текущий результат. На этом заканчиваю. Уточнения потом?")
    effects, calls = turn(final_text, {}, control="FINAL", replay=True)
    assert [event["event_type"] for event in effects] == ["scenario_completed"] and not calls
    with product_db() as connection:
        transition(connection, assessment_situation_id=as_id, action="close", reason="synthetic QA", request_id="qa-close")
        handoff = build_c45(connection, as_id)["envelope_json"]
    if number in {2, 7}:
        assert any("E02_SUBMISSION" in row["occurred_event_refs"] for row in handoff["conditional_opportunities"])
        assert final_text in json.dumps(handoff["dialogue"], ensure_ascii=False)
    export(f"CASE.SPEC.{number:02d}/trace.json", {
        "gateway": "SYNTHETIC CONTROLLED", "live_model": "NOT_RUN", "catalog": cycle["catalog_ref_json"],
        "execution_manifest_checksum": cycle["execution_manifest_checksum"], "source": generation["source_snapshot"]["refs"],
        "as": accepted, "review": tester, "repair": generation.get("repair"), "opening": opening,
        "turns": steps, "c45": handoff,
    })


def test_v04_early_final_first_next_and_mandate(product_db, v04):
    cycle, session = start_case(product_db, v04[0][0], 1, 2)
    gateway = V04Gateway()
    first, _ = prepare_and_start(product_db, cycle, session, gateway)
    with pytest.raises(ValueError, match="M5_BATTERY_WAITING_CURRENT_AS"):
        prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=str(uuid4()), actor=99, gateway=gateway)
    events, calls = submit(product_db, first, "Заканчиваю. Можно увидеть ваш черновик?",
                           {"E01_DOCUMENT": matched()}, control="FINAL")
    assert [event["event_type"] for event in events] == ["scenario_completed"] and not calls
    with product_db() as connection:
        assert "M02" not in trace(connection, first)["state"]["state_json"]["disclosed_materials"]
        transition(connection, assessment_situation_id=first, action="close", reason="SYNTHETIC QA", request_id="first-close")
        connection.commit()
    second, saved = prepare_and_start(product_db, cycle, session, gateway, first=False)
    assert saved["snapshot"]["case_ref"]["id"] == "CASE.SPEC.02"
    replay = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=second, actor=99, gateway=gateway)
    assert replay["idempotent"] and replay["snapshot_json"] == saved["snapshot"]
    blocked, _ = start_case(product_db, v04[0][1], 9)
    empty_gateway = V04Gateway()
    with pytest.raises(ValueError, match="M5_BATTERY_PROFILE_CLARIFICATION_REQUIRED:18/professional_recommendation"):
        prepare_next(product_db, cycle_id=str(blocked["cycle_id"]), assessment_situation_id=str(uuid4()), actor=99,
                     gateway=empty_gateway)
    assert not empty_gateway.calls
    export("first-next-and-mandate.json", {"case_after_next": saved["snapshot"]["case_ref"], "case_id": "CASE.SPEC.01",
           "early_final_events": events, "early_final_m02": "absent", "replay": replay["idempotent"],
           "missing_mandate": "M5_BATTERY_PROFILE_CLARIFICATION_REQUIRED:18/professional_recommendation",
           "missing_mandate_provider_calls": 0})


def test_install_v04_during_legacy_cycle(product_db, specialist):
    cycle, session = cycle_for(product_db, specialist[0], 1, 2)
    gateway = PreparationGateway("pass")
    first, previous = prepare_and_start(product_db, cycle, session, gateway)
    with product_db() as connection:
        transition(connection, assessment_situation_id=first, action="pause", reason="SYNTHETIC QA", request_id="pause")
        install_v04(connection)
        transition(connection, assessment_situation_id=first, action="resume", reason="SYNTHETIC QA", request_id="resume")
        connection.commit()
    resumed = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=first, actor=99, gateway=gateway)
    assert resumed["snapshot_json"] == previous["snapshot"]
    submit(product_db, first, "На этом всё.", {}, control="FINAL")
    with product_db() as connection:
        transition(connection, assessment_situation_id=first, action="close", reason="SYNTHETIC QA", request_id="close")
        connection.commit()
    _, saved = prepare_and_start(product_db, cycle, session, gateway, first=False)
    assert saved["snapshot"]["case_ref"]["id"] == "CASE.SPEC.02"
    assert saved["execution_payload"]["runtime_rules"]["battery_scenario"]["ref"]["version"] == "1.6.0"
    assert resolve_cycle_dependency(cycle, "m5_functional_as").name == "v4"
    export("legacy-resume.json", {"old_catalog": cycle["catalog_ref_json"], "new_catalog": "0.8-qa.3",
           "old_snapshot_equal": resumed["snapshot_json"] == previous["snapshot"], "next_case": saved["snapshot"]["case_ref"]})


@pytest.mark.parametrize("prior", [BATTERY_V04_SCENARIO_PACKAGE, BATTERY_V04_SCENARIO_PATCH, BATTERY_V04_SCENARIO_182])
def test_v04_catalog_keeps_original_scenario(product_db, specialist, prior):
    original_version = prior.rsplit("/", 1)[-1]
    prior_ref = battery_scenario_ref(prior) if prior != BATTERY_V04_SCENARIO_PACKAGE else None
    with product_db() as connection:
        published = publish_diagnostic_battery(
            connection, published_by=99, organization_id=10, catalog_id="specialist-battery-diagnostic",
            catalog_version="0.8-qa", idempotency_key="m5-v04-original", decision_basis="SYNTHETIC legacy 1.8.0",
            battery_v04=True, scenario_ref=prior_ref,
        )
        connection.execute("""INSERT INTO assessment_configurations
            (id,methodology_version_id,status,code,name,catalog_version_id)
            VALUES (3,1,'published','m5-v04-old','SYNTHETIC M5 v0.4 original',%s)""", (published["catalog"]["catalog_db_id"],))
        context = connection.execute("""SELECT organization_context_version_id,user_context_version_id,
            role_profile_version_id FROM assessment_personalized_profiles WHERE id=%s""", (specialist[0],)).fetchone()
        profile = create_personalized_profile(connection, user_id=99, assessment_configuration_id=3, **context)["id"]
        connection.commit()
    cycle, session = start_case(product_db, profile, 8, 2)
    assert resolve_cycle_dependency(cycle, "m5_battery_scenario") == ROOT / prior
    gateway = V04Gateway()
    as_id, original = prepare_and_start(product_db, cycle, session, gateway)
    with product_db() as connection:
        transition(connection, assessment_situation_id=as_id, action="pause", reason="SYNTHETIC QA", request_id="pause-v04")
        replacement = install_v04(connection)
        transition(connection, assessment_situation_id=as_id, action="resume", reason="SYNTHETIC QA", request_id="resume-v04")
        connection.commit()
    replay = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=as_id, actor=99, gateway=gateway)
    assert replay["snapshot_json"] == original["snapshot"]
    submit(product_db, as_id, "Заканчиваю.", {}, control="FINAL")
    with product_db() as connection:
        transition(connection, assessment_situation_id=as_id, action="close", reason="SYNTHETIC QA", request_id="close-v04")
        connection.commit()
    _, saved = prepare_and_start(product_db, cycle, session, gateway, first=False)
    assert saved["execution_payload"]["runtime_rules"]["battery_scenario"]["ref"]["version"] == original_version
    export(f"legacy-{original_version.replace('.', '')}-resume.json", {"old_catalog": cycle["catalog_ref_json"], "new_catalog": replacement["catalog_readback"],
           "old_snapshot_equal": replay["snapshot_json"] == original["snapshot"], "next_case": saved["snapshot"]["case_ref"]})


def test_future_catalog_readback_and_m7_rank(product_db, v04, monkeypatch, tmp_path):
    monkeypatch.setattr("Api.database.get_connection", product_db)
    source = build_trace(BATTERY_V04_PACKAGE, BATTERY_V04_RUNTIME)
    _, contract_ref, review_refs = read_as_package(REVIEW)
    proof = tmp_path / "synthetic-release-contract.json"
    evidence = {
        "human_review_ref": "SYNTHETIC PostgreSQL contract fixture",
        "as_contract_ref": BANK["as_contract_ref"], "prepared_as_contract_ref": contract_ref,
        "review_package": review_refs["protocol_package"], "scenario_ref": load_scenario(BANK["cases"][0], SCENARIO)["ref"],
        "runtime_rule_ref": {key: source["runtime"][key] for key in ("id", "version", "manifest_checksum")},
        "scopes": dict.fromkeys(ADMISSION_EVIDENCE, "PASS"),
        "cases": {case["case_id"]: checksum(case) for case in BANK["cases"]},
    }

    def publish(path):
        return publish_admitted_catalog(
            source, published_by=99, decision_basis="SYNTHETIC isolated import contract", catalog_id="synthetic-specialist-pilot",
            catalog_version="1.4.3", idempotency_key="synthetic-v04-pilot-183", organization_id=10,
            package_dir=BATTERY_V04_PACKAGE, runtime_dir=BATTERY_V04_RUNTIME, evidence_path=path,
        )

    with pytest.raises(ValueError, match="M5_PASSPORT_BANK_ASSESSMENT_EVIDENCE_REQUIRED"):
        publish(None)
    _, _, legacy_review = read_as_package(REVIEW.with_name("v6"))
    proof.write_text(json.dumps({**evidence, "review_package": legacy_review["protocol_package"]}))
    with pytest.raises(ValueError, match="M5_BATTERY_PILOT_REVIEW_EVIDENCE_MISMATCH"):
        publish(proof)
    old_scenario = load_scenario(BANK["cases"][0], ROOT / BATTERY_V04_SCENARIO_PACKAGE)["ref"]
    proof.write_text(json.dumps({**evidence, "scenario_ref": old_scenario}))
    with pytest.raises(ValueError, match="M5_BATTERY_PILOT_REVIEW_EVIDENCE_MISMATCH"):
        publish(proof)
    proof.write_text(json.dumps(evidence))
    released = publish(proof)
    assert publish(proof)["catalog"]["idempotent"]
    imported_cases = released["readback"]["package"]["package_json"]["cases"]
    for original, imported in zip(BANK["cases"], imported_cases, strict=True):
        assert imported["passport_source"] == original["passport_source"]
        assert imported["version"] == original["version"] + "-pilot.1"
    planned = {target["indicator_id"] for case in BANK["cases"] for target in case["indicator_targets"]}
    targets = [target for target in methodology_targets(["K1", "K2", "K3", "K4"]) if target["indicator_id"] in planned]
    rules = load_rules()
    profiles = {}
    with product_db() as connection:
        catalog_id = released["catalog"]["catalog_db_id"]
        connection.execute("""INSERT INTO assessment_configurations (id,methodology_version_id,status,code,name,catalog_version_id)
            VALUES (4,1,'published','synthetic-m5-v04','SYNTHETIC future M5 catalog',%s)""", (catalog_id,))
        ref = resolve_configuration_catalog(connection, configuration_id=4, usage_scope="assessment")
        frozen = build_manifest(profile_ref={"id": "synthetic"}, selected_role_ref={"id": "specialist_expert"},
                                target_set_checksum=checksum(targets), parameter_sources={}, catalog_ref=ref)
        assert resolve_dependency(*frozen, "m5_battery_scenario") == SCENARIO
        assert resolve_dependency(*frozen, "m5_functional_as") == REVIEW
        for confirmed, profile_id in zip((True, False), v04[0], strict=True):
            row = connection.execute("SELECT content_json FROM assessment_personalized_profiles WHERE id=%s", (profile_id,)).fetchone()
            cases = _catalog(connection, role="specialist_expert", rules=rules, planned_ids=planned,
                             catalog_db_id=catalog_id, usage_scope="assessment", battery_profile=row["content_json"],
                             battery_scenario_package=SCENARIO)
            route, uncovered = ranked_route(cases, targets)
            assert not uncovered and len(targets) == 39
            assert sum(case["eligible"] for case in cases) == (9 if confirmed else 8)
            nine = next(case for case in cases if case["case_id"] == "CASE.SPEC.09")
            assert nine["eligible"] is confirmed
            profiles["mandate_confirmed" if confirmed else "mandate_missing"] = {"catalog": cases, "route": route}
    export("M7-readback.json", {"scope": "SYNTHETIC isolated database only", "catalog": released["catalog_readback"],
           "runtime_ref": evidence["runtime_rule_ref"], "review_ref": evidence["review_package"],
           "scenario_ref": evidence["scenario_ref"], "cycle_manifest_checksum": frozen[1],
           "case_versions": released["readback"]["cases"],
           "assignments": sum(len(case["indicator_targets"]) for case in BANK["cases"]),
           "targets": targets, "profiles": profiles})
