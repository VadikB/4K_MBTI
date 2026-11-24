"""CASES.md v0.3 through PM-03, the controlled gateway, and PostgreSQL PM-04."""
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from Api.assessment_contexts import confirm_user_context, create_personalized_profile, create_user_context_draft
from Api.m5_battery_preparation import prepare_next
from Api.m5_cycle_runtime import create_cycle_session_for_case, start_session
from Api.m5_functional_generation_service import checksum
from Api.m5_rule_engine import DeepSeekCharacterAdapter, DeepSeekSemanticAdapter
from Api.m5_scenario_runtime import build_c45, start, submit_turn_detached, trace, transition
from Api.m10_product_flow import participant_trace
from tests.integration.test_m5_battery_bank_db import install_battery
from tests.integration.test_m10_product_path_db import product_db
from tests.unit.test_m5_passport_bank import CaptureGateway

pytestmark = pytest.mark.integration
VERSIONS = ("v0.6", "v0.7", "v0.5", "v0.6", "v0.6", "v0.5", "v0.5", "v0.5", "v0.5")


def reference(number):
    return f"CASE.SPEC.{number:02d}", VERSIONS[number - 1]


def synthetic_as(payload):
    design = payload["scenario_contract"]
    return {
        "AssessmentSituationID": str(uuid4()), "Version": "qa.1", "Название": "Согласование рабочего процесса",
        "Применённые замены": [],
        "Материалы": [{"MaterialID": key, "Название": f"Рабочая запись {key}",
                      "Текст": f"Синтетический материал {key}: проверяем только подтверждённые условия."}
                     for key in design["material_ids"]],
        "Активные персонажи": [
            {"CharacterID": key, "Имя": f"Роль {key}", "Текст": f"Позиция персонажа {key}."} for key in design["roles"]
        ],
        "Закрытые фиксированные факты": [
            {"FactID": key, "Текст": f"Закрытая запись {key}: значение {index + 14}."}
            for index, key in enumerate(design["fact_ids"])
        ],
        "IndicatorObservability": [
            {"IndicatorID": target["indicator_id"], "Конкретное условие": target["event_condition"],
             "Форма проявления": target["observable_action"], "Дефект потери": target["validity_risk"],
             "material_refs": ["M01"], "event_refs": [design["events"][0]["id"]],
             "character_refs": [], "authority_refs": ["participant"]}
            for target in payload["normative_indicator_targets"]
        ],
    }


class PreparationGateway(CaptureGateway):
    def chat_with_trace(self, messages, **kwargs):
        routing = kwargs["routing_key"]
        if ":generation:" not in routing:
            return super().chat_with_trace(messages, **kwargs)
        payload = json.loads(messages[-1]["content"])
        self.calls.append((routing, deepcopy(messages), payload))
        result = synthetic_as(payload)
        if self.mode in {"repair", "reject"} and (":repair:" not in routing or self.mode == "reject"):
            result["IndicatorObservability"][0]["Форма проявления"] = ""
        # A provider might return an old field after repair. The sealed value
        # always comes from the exact source, before either reviewer sees it.
        result["Стартовые MaterialIDs"] = ["STALE"]
        result["RuntimeBindings"] = {"STALE": {"delivery_id": "M99"}}
        result["События"] = [{"EventID": "STALE"}]
        return SimpleNamespace(content=json.dumps(result, ensure_ascii=False), sent={},
                               provider={"finish_reason": "stop"})


class TurnGateway:
    enabled = True

    def __init__(self, rules, *, control, recipients=(), responses=None, fragments=None):
        self.rules = rules
        self.control = control
        self.recipients = recipients
        self.responses = responses or {}
        self.fragments = fragments
        self.character_calls = []

    def chat(self, messages, **kwargs):
        data = json.loads(messages[-1]["content"])
        if "character" in data:
            self.character_calls.append(data)
            speaker = data["character"]["character_id"]
            return json.dumps({"response": self.responses.get(speaker, f"{speaker}: это пока не подтверждено.")})
        condition = data["condition"]
        if isinstance(condition, str):
            details = {"fragments": self.fragments or [
                {"text": data["message"], "recipient_ids": list(self.recipients)}
            ]}
            result = {"code": "MATCH", "details": details}
        elif "finish" in condition:
            result = {"code": self.control}
        elif "effect" in condition:
            result = self.rules.get("@confirmed:" + condition["event_id"], {"code": "NO_MATCH"})
        elif "passport_rule" not in condition:
            result = self.rules.get("@accepted", {"code": "NO_MATCH"})
        else:
            result = self.rules.get(condition["passport_rule"]["ID"], {"code": "NO_MATCH"})
        return json.dumps({"basis": "Управляемый ответ тестового шлюза", **result}, ensure_ascii=False)


def matched(**details):
    return {"code": "MATCH", **({"details": details} if details else {})}


@pytest.fixture
def specialist(product_db):
    with product_db() as connection:
        published = install_battery(connection)
        connection.execute("ALTER TABLE assessment_configurations ADD COLUMN catalog_version_id BIGINT")
        connection.execute("""INSERT INTO assessment_configurations
            (id,methodology_version_id,status,code,name,catalog_version_id)
            VALUES (2,1,'published','scenario-02-qa','Synthetic 02 QA',%s)""", (published["catalog"]["catalog_db_id"],))
        context = connection.execute("""SELECT organization_context_version_id,user_context_version_id
            FROM assessment_personalized_profiles WHERE id=%s""", (product_db.profile_id,)).fetchone()
        role = connection.execute("""SELECT v.id FROM assessment_role_profile_versions v
            JOIN assessment_role_profiles r ON r.id=v.role_profile_id
            WHERE r.code='specialist_expert' AND r.scope='base' AND v.status='published'""").fetchone()["id"]
        without_mandate = create_personalized_profile(
            connection, user_id=99, assessment_configuration_id=2, role_profile_version_id=role, **context,
        )["id"]
        context["user_context_version_id"] = create_user_context_draft(
            connection, user_id=99, identity={"full_name": "QA Synthetic"},
            professional={"regular_tasks": ["Проверяю рабочие предложения и рекомендую будущего коллегу"],
                          "additional_information": {"professional_recommendation": {
                              "confirmed": True, "basis": "Синтетический подтверждённый M4 контекст",
                          }}},
        )
        confirm_user_context(connection, version_id=context["user_context_version_id"], user_id=99)
        with_mandate = create_personalized_profile(
            connection, user_id=99, assessment_configuration_id=2, role_profile_version_id=role, **context,
        )["id"]
        connection.commit()
    return with_mandate, without_mandate


def cycle_for(product_db, profile, number, *next_cases):
    with product_db() as connection:
        case_id, version = reference(number)
        cycle, session = create_cycle_session_for_case(
            connection, personalized_profile_id=profile, case_id=case_id, case_version=version,
            created_by=99, usage_scope="qa", diagnostic=True, scenario_tests=True,
            next_cases=tuple(reference(item) for item in next_cases),
        )
        connection.commit()
    return cycle, session


def prepare_and_start(product_db, cycle, session, gateway, *, first=True):
    as_id = str(uuid4())
    saved = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=as_id, actor=99, gateway=gateway)
    assert saved["status"] == "rejected"  # built C-34, accessible by the existing server QA override
    with product_db() as connection:
        if first:
            start_session(connection, session_id=str(session["session_id"]))
        start(connection, as_id)
        start(connection, as_id)
        connection.commit()
    return as_id, saved


def submit(product_db, as_id, text, rules, *, control="CONTINUE", recipients=(), responses=None, fragments=None, replay=False):
    with product_db() as connection:
        payload = connection.execute(
            "SELECT execution_payload_json FROM m5_assessment_situations WHERE assessment_situation_id=%s", (as_id,),
        ).fetchone()["execution_payload_json"]
    gateway = TurnGateway(rules, control=control, recipients=recipients, responses=responses, fragments=fragments)
    args = {
        "assessment_situation_id": as_id, "request_id": str(uuid4()), "turn_id": str(uuid4()), "content": text,
        "connection_factory": product_db, "semantic_adapter": DeepSeekSemanticAdapter(gateway, operation=payload["ai_operations"]["semantic_decision"]),
        "character_adapter": DeepSeekCharacterAdapter(gateway, operation=payload["ai_operations"]["character_response"]),
    }
    result = submit_turn_detached(**args)
    if replay:
        calls = len(gateway.character_calls)
        repeated = submit_turn_detached(**args)
        assert repeated["idempotent"] and repeated["events"] == result["events"]
        assert len(gateway.character_calls) == calls
    return result["events"], gateway.character_calls


def ids(events, kind=None):
    return [item["payload_json"].get("scenario_event_id") for item in events
            if kind is None or item["event_type"] == kind]


@pytest.mark.parametrize("number", range(1, 10))
def test_battery_case_matrix(product_db, specialist, number):
    cycle, session = cycle_for(product_db, specialist[0], number)
    gateway = PreparationGateway("repair" if number == 1 else "pass")
    as_id, saved = prepare_and_start(product_db, cycle, session, gateway)
    payload = saved["execution_payload"]
    design = payload["runtime_rules"]["battery_scenario"]
    generation = payload["ai_operations"]["functional_personalization"]
    receipts = {generation["candidate_checksum"]}
    if number == 1:
        assert generation["repair"]
        assert generation["repair"]["original_candidate_checksum"] != generation["candidate_checksum"]
        receipts.add(generation["repair"]["original_candidate_checksum"])
    reviewer_calls = [(route, body) for route, _, body in gateway.calls if "candidate_as" in body]
    assert all(body["candidate_checksum"] == checksum(body["candidate_as"]) for route, body in reviewer_calls)
    for sha in receipts:
        assert {role for role in ("tester", "challenger") if any(
            f":{role}:" in route and body["candidate_checksum"] == sha for route, body in reviewer_calls
        )} == {"tester", "challenger"}
    assert all("author_as_example" not in body and "author_assessment_situation" not in body for _, _, body in gateway.calls)
    assert generation["candidate_checksum"] == checksum(generation["accepted_as"])
    assert generation["author_content_binding"]["provider_candidate_checksum"] != generation["candidate_checksum"]
    assert generation["accepted_as"]["Стартовые MaterialIDs"] == design["start_ids"]
    with product_db() as connection:
        current = trace(connection, as_id)
        assert current["state"]["state_json"]["disclosed_materials"] == design["start_ids"]
        public = participant_trace(current)
    public_ids = [row["material_id"] for row in public["events"]]
    assert [key for key in design["start_ids"] if key != "P00" and (not design["opening"] or key != "M05")] == public_ids
    assert len(public["turns"]) == int(number in {4, 5})
    if number in {4, 5}:
        assert public["turns"][0]["content_text"] == design["concrete_materials"]["M05"]["Текст"]
    assert all(key not in public_ids for key in design["fact_ids"])

    if number == 1:
        events, calls = submit(product_db, as_id, "Как называется этот чат?", {})
        assert not events and not calls
        events, calls = submit(product_db, as_id, "Так тоже можно, на этом всё или ещё обсудим?",
                               {"E01_DOCUMENT": matched()}, control="UNKNOWN")
        assert ids(events) == ["SCENARIO_CONTROL"] and not calls
        assert events[0]["payload_json"]["response"] == design["control"]["clarification"]
        for text in ("К какой дате относится запрос?", "Уточните, к какому этапу относится названный срок."):
            events, calls = submit(product_db, as_id, text, {"E02_REPLY": matched(speaker_ids=["CUSTOMER"], fact_ids=["F01"])})
            assert ids(events) == ["E02_REPLY"]
            assert design["concrete_facts"]["F01"] in calls[0]["character"]["known_facts"]
            assert design["concrete_facts"]["F02"] not in calls[0]["character"]["known_facts"]
        events, _ = submit(product_db, as_id, "Предлагаю согласовать объём с владельцем, как считаете?",
                           {"E01_DOCUMENT": matched(), "E05_NEXT_STEP": matched(speaker_ids=["CUSTOMER"])}, replay=True)
        assert ids(events) == ["E05_NEXT_STEP", "E01_DOCUMENT"]
        with product_db() as connection:
            transition(connection, assessment_situation_id=as_id, action="pause", reason="qa", request_id="qa-pause")
            transition(connection, assessment_situation_id=as_id, action="resume", reason="qa", request_id="qa-resume")
            connection.commit()
        events, _ = submit(product_db, as_id, "Обсудим предложенный шаг ещё раз?", {"E01_DOCUMENT": matched()})
        assert not events
    elif number in {2, 7}:
        rule = "E01_FACT" if number == 2 else "E01_EXPLAIN"
        unknown = "E03_UNKNOWN" if number == 2 else "E03_UNAVAILABLE"
        events, calls = submit(product_db, as_id, "Что означает ограничение в предъявленном протоколе?",
                               {rule: matched(speaker_ids=["FACILITATOR"])})
        assert ids(events) == [rule] and calls[0]["character"]["character_id"] == "FACILITATOR"
        events, _ = submit(product_db, as_id, "Каков результат будущего испытания?",
                           {unknown: matched(speaker_ids=["FACILITATOR"])})
        assert ids(events) == [unknown] and "не подтверждено" in events[0]["payload_json"]["response"]
    elif number == 3:
        events, _ = submit(product_db, as_id, "Предлагаю согласовать части: пока жду, что ответят C1 и C3.",
                           {"E01_UPDATE": matched(speaker_ids=["C1", "C3"])}, recipients=("C1", "C3"))
        assert not events
        events, _ = submit(product_db, as_id, "Вместе сверим версии, коллеги?",
                           {"E01_UPDATE": matched(speaker_ids=["C1", "C2", "C3"]),
                            "E03_REPLY": matched(speaker_ids=["C1", "C2", "C3"])},
                           recipients=("C1", "C2", "C3"))
        assert ids(events)[-1] == "E01_UPDATE"
        delivery = events[-1]["payload_json"]
        assert (delivery["author_id"], delivery["speaker_id"], delivery["recipient_ids"]) == ("CUSTOMER", "C2", ["assessee"])
        message = "C1, сообщаю уточнение: окно ограничено пятницей."
        events, calls = submit(product_db, as_id, message, {
            "E02_TRANSFER": matched(recipient_ids=["C1"], text=message), "E03_REPLY": matched(speaker_ids=["C1"]),
        }, recipients=("C1",))
        assert ids(events, "information_transferred") == ["E02_TRANSFER"]
        assert design["concrete_materials"]["M04"] not in calls[0]["character"]["known_facts"]
        text = "C3, позже перешлю уточнение. Какой вклад вы подтвердили?"
        events, calls = submit(product_db, as_id, text, {"E03_REPLY": matched(speaker_ids=["C3"])}, recipients=("C3",))
        assert not ids(events, "information_transferred")
        assert message not in json.dumps(calls, ensure_ascii=False)
        assert design["concrete_materials"]["M04"] not in calls[0]["character"]["known_facts"]
        events, _ = submit(product_db, as_id, "C2, перешлите C3 только оговорку о подтверждённых условиях сейчас.", {
            "E02_FORWARD": matched(recipient_ids=["C3"], text="проверяем только подтверждённые условия."), "@accepted": matched(),
        }, recipients=("C2",), responses={"C2": "Принимаю и направляю C3 сейчас."})
        transfer = next(event["payload_json"] for event in events if event["event_type"] == "information_transferred")
        assert transfer["sender_id"] == "C2" and transfer["recipient_ids"] == ["C3"]
        assert transfer["scenario_event_id"] == "E02_TRANSFER"
        assert transfer["text"] == "проверяем только подтверждённые условия."
    elif number == 4:
        events, calls = submit(product_db, as_id, "Предлагаю согласовать новый порядок с вами и оставить резерв времени.",
                               {"E01_REVIEW": matched(speaker_ids=["CUSTOMER"]), "E01_STATE_LIMIT": matched(speaker_ids=["CUSTOMER"])})
        assert ids(events) == ["E01_REVIEW"]
        assert events[0]["payload_json"]["scenario_event_ids"] == ["E01_REVIEW", "E01_STATE_LIMIT"]
        assert not any(value in calls[0]["character"]["known_facts"] for value in design["concrete_facts"].values())
        events, _ = submit(product_db, as_id, "Учёл ограничение: отправлю только исправленный фрагмент.",
                           {"E02_REVISION": matched(speaker_ids=["CUSTOMER"])})
        assert ids(events) == ["E02_REVISION"]
    elif number == 5:
        events, _ = submit(product_db, as_id, "Можно проверить один участок отдельно или объединить материалы; готовы помочь?",
                           {"E01_COLLEAGUE": matched(speaker_ids=["C1"]), "E03_SUPPORT": matched(speaker_ids=["C1"]),
                            "@confirmed:E03_SUPPORT": matched()},
                           responses={"C1": "Поддерживаю обсуждение, распоряжаться ресурсом не могу."})
        assert len(events) == 1 and set(events[0]["payload_json"]["scenario_event_ids"]) == {"E01_COLLEAGUE", "E03_SUPPORT"}
        assert "не могу" in events[0]["payload_json"]["response"]
    elif number == 6:
        events, _ = submit(product_db, as_id, "Что каждая сторона готова взять в подготовке общей пробы?",
                           {"E01_DISCUSS": matched(speaker_ids=["C1", "C2", "C3"])}, recipients=("C1", "C2", "C3"))
        assert {event["payload_json"]["speaker_id"] for event in events} == {"C1", "C2", "C3"}
        assert set(ids(events)) == {"E01_DISCUSS"}
        events, _ = submit(product_db, as_id, "C1, возьмёте подготовку? Тогда результат пробы пока открыт.",
                           {"E01_ACCEPT": matched(speaker_ids=["C1"]), "@confirmed:E01_ACCEPT": matched()},
                           recipients=("C1",), responses={"C1": "Подготовку беру, пробу мы пока не проводили."})
        assert events[0]["payload_json"]["scenario_event_ids"] == ["E01_ACCEPT"]
        assert "не проводили" in events[0]["payload_json"]["response"]
    elif number == 8:
        events, _ = submit(product_db, as_id, "R_RECIPIENT, передаю фрагмент: версия четыре, исполнение ждёт согласования.",
                           {"E01_RECEIPT": matched(recipient_ids=["R_RECIPIENT"], text="версия четыре"),
                            "@confirmed:E01_RECEIPT": matched()},
                           recipients=("R_RECIPIENT",), responses={"R_RECIPIENT": "Версию четыре получил."})
        assert [event["event_type"] for event in events] == ["information_transferred", "character_response"]
        assert ids(events, "information_transferred") == ["E01_RECEIPT"]
        assert ids(events, "character_response") == ["E01_RECEIPT"]
        events, _ = submit(product_db, as_id, "R_AUTHOR, передам остальное после внешнего согласования; оно уже пришло?",
                           {"E03_PENDING": matched(speaker_ids=["R_AUTHOR"])}, recipients=("R_AUTHOR",))
        assert ids(events) == ["E03_PENDING"] and "не подтверждено" in events[0]["payload_json"]["response"]
    else:
        events, _ = submit(product_db, as_id, "Моя рекомендация условна: исправление было, но чем подтверждено повторение?",
                           {"E02_BOUNDARY": matched(speaker_ids=["R_MANAGER"]), "E01_MANAGER": matched(speaker_ids=["R_MANAGER"])})
        assert len(events) == 1 and events[0]["payload_json"]["speaker_id"] == "R_MANAGER"
        assert events[0]["payload_json"]["scenario_event_ids"] == ["E02_BOUNDARY", "E01_MANAGER"]

    events, calls = submit(product_db, as_id, "Сдаю как есть и на этом заканчиваю. А детали потом уточним?",
                           {"E01_DOCUMENT": matched(), "E01_UPDATE": matched()}, control="FINAL", replay=True)
    assert [event["event_type"] for event in events] == ["scenario_completed"] and not calls
    with product_db() as connection:
        assert trace(connection, as_id)["status"] == "scenario_ended"
        transition(connection, assessment_situation_id=as_id, action="close", reason="qa", request_id="qa-close")
        handoff = build_c45(connection, as_id)["envelope_json"]
    assert len(handoff["conditional_opportunities"]) == len(generation["accepted_as"]["IndicatorIDs"])
    if number in {2, 7}:
        assert any("E02_SUBMISSION" in item["occurred_event_refs"] for item in handoff["conditional_opportunities"])


def test_early_final_and_first_next_use_same_frozen_rules(product_db, specialist):
    cycle, session = cycle_for(product_db, specialist[0], 1, 2)
    gateway = PreparationGateway("pass")
    first, _ = prepare_and_start(product_db, cycle, session, gateway)
    with pytest.raises(ValueError, match="M5_BATTERY_WAITING_CURRENT_AS"):
        prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=str(uuid4()), actor=99, gateway=gateway)
    events, calls = submit(product_db, first, "Завершаю предложением созвониться. Согласны?",
                           {"E01_DOCUMENT": matched()}, control="FINAL")
    assert [item["event_type"] for item in events] == ["scenario_completed"] and not calls
    with product_db() as connection:
        result = trace(connection, first)
        assert "M02" not in result["state"]["state_json"]["disclosed_materials"]
        transition(connection, assessment_situation_id=first, action="close", reason="qa", request_id="first-close")
        connection.commit()
    second, saved = prepare_and_start(product_db, cycle, session, gateway, first=False)
    replay = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=second, actor=99, gateway=gateway)
    assert replay["idempotent"] and replay["snapshot_json"] == saved["snapshot"]
    assert saved["snapshot"]["case_ref"]["id"] == "CASE.SPEC.02"


def test_spec09_requires_confirmed_mandate_and_rejected_candidate_never_persists(product_db, specialist):
    blocked, _ = cycle_for(product_db, specialist[1], 9)
    gateway = PreparationGateway("pass")
    with pytest.raises(ValueError, match="M5_BATTERY_PROFILE_CLARIFICATION_REQUIRED:18/professional_recommendation"):
        prepare_next(product_db, cycle_id=str(blocked["cycle_id"]), assessment_situation_id=str(uuid4()), actor=99, gateway=gateway)
    assert not gateway.calls
    cycle, _ = cycle_for(product_db, specialist[0], 9)
    result = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=str(uuid4()),
                          actor=99, gateway=PreparationGateway("reject"))
    assert result["status"] == "preparation_rejected"
    with product_db() as connection:
        assert connection.execute("SELECT count(*) AS n FROM m5_assessment_situations").fetchone()["n"] == 0


def test_project_role_is_pinned_from_the_exact_educational_assignment(product_db, specialist):
    from Api.telegram_channel import checksum as educational_checksum

    with product_db() as connection:
        connection.execute("ALTER TABLE participant_acquaintance_confirmations ADD COLUMN questionnaire_revision_id BIGINT")
        connection.execute("""CREATE TABLE organization_assessment_assignments
            (id BIGINT,recipient_user_id BIGINT,organization_id BIGINT,assignment_ref TEXT,status TEXT,revoked_at TIMESTAMP)""")
        connection.execute("""CREATE TABLE organization_assessment_source_bindings
            (assignment_id BIGINT,questionnaire_revision_id BIGINT,assessment_configuration_id BIGINT,role_profile_version_id BIGINT)""")
        connection.execute("""CREATE TABLE external_educational_contexts
            (assessment_assignment_id BIGINT,organization_id BIGINT,recipient_user_id BIGINT,source_system TEXT,
             snapshot_json JSONB,snapshot_checksum TEXT)""")
        role_id = connection.execute("SELECT role_profile_version_id FROM assessment_personalized_profiles WHERE id=%s",
                                     (specialist[0],)).fetchone()["role_profile_version_id"]
        connection.execute("INSERT INTO organization_assessment_assignments VALUES (41,99,10,'scenario-edu','active',NULL)")
        connection.execute("INSERT INTO organization_assessment_source_bindings VALUES (41,9,2,%s)", (role_id,))
        connection.execute("""INSERT INTO participant_acquaintance_confirmations
            (user_id,organization_id,assignment_ref,answers_json,questionnaire_revision_id,personalized_profile_id)
            VALUES (99,10,'scenario-edu','{}',9,%s)""", (specialist[0],))
        interactions = ["Работает с куратором учебного проекта", "Согласует материалы с профильным коллегой"]
        definition = {"interactions": interactions}
        external = {"role": {"code": "qa-educational-specialist", "project_role_version": 3,
                             "definition": definition, "project_role_checksum": educational_checksum(definition),
                             "agent4k_role_profile_version_id": role_id}}
        connection.execute("""INSERT INTO external_educational_contexts VALUES (41,10,99,'4k_tg_bot',%s::jsonb,%s),
            (42,10,99,'4k_tg_bot','{}','never-read')""", (json.dumps(external), educational_checksum(external)))
        connection.commit()
    cycle, session = cycle_for(product_db, specialist[0], 2)
    frozen_role = cycle["execution_manifest_json"]["runtime_refs"]["project_role"]
    with product_db() as connection:
        connection.execute("UPDATE external_educational_contexts SET snapshot_checksum='stale' WHERE assessment_assignment_id=41")
        connection.commit()
    gateway = PreparationGateway("repair")
    _, saved = prepare_and_start(product_db, cycle, session, gateway)
    expected = {"code": frozen_role["code"], "interactions": interactions}
    assert all(body["project_role"] == expected for _, _, body in gateway.calls)
    assert saved["execution_payload"]["ai_operations"]["functional_personalization"]["source_snapshot"][
        "refs"]["project_role"]["snapshot_checksum"] == educational_checksum(external)
