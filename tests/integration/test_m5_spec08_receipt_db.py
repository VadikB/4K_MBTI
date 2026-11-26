"""Read back the actual speaker reply and acquired SPEC.08 knowledge."""

from hashlib import sha256

import pytest

from Api.m5_scenario_runtime import trace, transition
from tests.integration.test_m5_battery_scenario_db import matched, prepare_and_start, specialist, submit
from tests.integration.test_m5_battery_v04_db import SPEC08_LINK, export, start_case, v04
from tests.integration.test_m5_spec08_delivery_db import RECIPIENT, recipient_turn
from tests.integration.test_m5_spec08_readback_db import FRAGMENT, OPENING, ReadbackGateway, knows_fragment
from tests.integration.test_m10_product_path_db import product_db


pytestmark = pytest.mark.integration
OLD_LINK = "m5-material://M02/3"
OPENED = f"Открыл и прочитал актуальный фрагмент по ссылке {SPEC08_LINK}."
TIMED = f"У меня десять минут. Я уже открыл и прочитал актуальный фрагмент по {SPEC08_LINK}."
WRONG_AND_PROMISE = f"Прочитал {OLD_LINK}. {SPEC08_LINK} открою позже."
QUESTION = "Вы уже открыли ранее присланную ссылку?"
TIME = "Сколько времени у вас есть?"
PLAIN_TIME = "Сколько времени у вас осталось?"
MIXED_QUESTION = f"Вы открыли {OLD_LINK} или {SPEC08_LINK}?"
CYRILLIC_VERSION = "ред-7"
CYRILLIC_LINK = f"m5-material://M02/{CYRILLIC_VERSION}"
CYRILLIC_OPENING = OPENING.replace("версию 4", f"версию {CYRILLIC_VERSION}")


PROBES = [
    ("immediate", None, OPENED, OPENED, True),
    ("immediate-mixed", None, f"{OPENED} Старую ссылку {OLD_LINK} не открывал.", OPENED, True),
    ("asked", QUESTION, TIMED, TIMED, True),
    ("mixed-question", f"Вы открыли {OLD_LINK} или {SPEC08_LINK}?", TIMED, TIMED, True),
    ("volunteered", TIME, TIMED, TIMED, True),
    ("wrong-address", QUESTION, f"Открыл только {OLD_LINK}.", f"Открыл только {OLD_LINK}.", False),
    ("shortened", QUESTION, f"Открыл и прочитал {SPEC08_LINK}0.", f"Открыл и прочитал {SPEC08_LINK}", False),
    ("fabricated-quote", QUESTION, f"Вижу адрес {SPEC08_LINK}.", OPENED, False),
    ("wrong-and-promise", QUESTION, WRONG_AND_PROMISE, WRONG_AND_PROMISE, False),
    ("denied", QUESTION, f"К {SPEC08_LINK} у меня нет доступа.", None, False),
    ("ambiguous", QUESTION, "Какой-то фрагмент читал, версию не помню.", None, False),
    ("other-role", QUESTION, TIMED, TIMED, False),
    ("undelivered", TIME, TIMED, TIMED, False),
    ("correction", f"У вашей актуальной версии адрес {OLD_LINK}. Вот {SPEC08_LINK}.",
     f"Актуальный адрес другой. {OPENED}", OPENED, True),
    ("plain-single-question", f"Вы уже открыли ранее присланную ссылку {SPEC08_LINK}?", OPENING, OPENING, True),
    ("plain-mixed-question", MIXED_QUESTION, OPENING, OPENING, True),
    ("plain-old-words", PLAIN_TIME, f"{OPENING} Старую версию 3 я не открывал.", OPENING, True),
    ("plain-old-link", PLAIN_TIME, f"{OPENING} Старую ссылку {OLD_LINK} я не открывал.", OPENING, True),
    ("plain-selects-delivered-version", f"Вы открыли {OLD_LINK}?", OPENING, OPENING, True),
    ("plain-cyrillic-version", f"Вы открыли {OLD_LINK} или {CYRILLIC_LINK}?",
     CYRILLIC_OPENING, CYRILLIC_OPENING, True),
    ("plain-ambiguous", MIXED_QUESTION, "Одну из двух читал.", None, False),
    ("plain-previous-version", MIXED_QUESTION, "Читал только прежнюю версию 3.", None, False),
    ("plain-promise", PLAIN_TIME, "Открою присланную вами версию 4 позже.", None, False),
    ("plain-denial", MIXED_QUESTION, "Версию 4 я не открывал.", None, False),
    ("plain-wrong-address-question", f"Вы открыли {SPEC08_LINK}0?", "Да, открыл и прочитал.", None, False),
    ("plain-foreign-address", QUESTION, "Открыл и прочитал https://example.test/record/4.",
     "Открыл и прочитал https://example.test/record/4.", False),
    ("plain-incomplete-address", QUESTION, "Открыл и прочитал m5-material:/M02/4.",
     "Открыл и прочитал m5-material:/M02/4.", False),
]


@pytest.mark.parametrize("probe,question,reply,evidence,opened", PROBES, ids=[probe[0] for probe in PROBES])
def test_spec08_opening_follows_actual_reply(product_db, v04, probe, question, reply, evidence, opened):
    cycle, session = start_case(product_db, v04[0][0], 8)
    version = CYRILLIC_VERSION if probe == "plain-cyrillic-version" else "4"
    link = f"m5-material://M02/{version}"
    as_id, saved = prepare_and_start(product_db, cycle, session, ReadbackGateway(version=version))
    before = recipient_turn(product_db, as_id)
    sender_text = f"Получатель, передаю {link}."
    speaker = "R_AUTHOR" if probe == "other-role" else RECIPIENT
    confirmation = {
        "@confirmed:E01_RECEIPT": matched() if evidence else {"code": "NO_MATCH"},
        "@opened:E01_RECEIPT": matched(text=evidence) if evidence else {"code": "NO_MATCH"},
    }
    delivery_rule = {"E01_RECEIPT": matched(recipient_ids=[RECIPIENT], text=link)}
    delivery_events, delivery_calls = [], []
    if question is None:
        confirmation_events, calls = submit(product_db, as_id, sender_text, {**delivery_rule, **confirmation},
                                             recipients=(RECIPIENT,), responses={RECIPIENT: reply}, replay=True)
        delivery_events, delivery_calls = confirmation_events, calls
    else:
        if probe != "undelivered":
            delivery_events, delivery_calls = submit(product_db, as_id, sender_text, delivery_rule,
                                                     recipients=(RECIPIENT,),
                                                     responses={RECIPIENT: "Ссылку получил. Открою позже."}, replay=True)
        if probe == "mixed-question" or probe.startswith("plain-"):
            with product_db() as connection:
                transition(connection, assessment_situation_id=as_id, action="pause", reason="synthetic",
                           request_id="pause-before-opening")
                transition(connection, assessment_situation_id=as_id, action="resume", reason="synthetic",
                           request_id="resume-before-opening")
                connection.commit()
        route = "E02_CORRECT" if probe == "correction" else "E04_CLARIFY"
        rules = {route: matched(speaker_ids=[speaker]), **confirmation}
        if question not in {TIME, PLAIN_TIME}:
            rules["@follow_up:E01_RECEIPT"] = matched()
        confirmation_events, calls = submit(product_db, as_id, question, rules, recipients=(speaker,),
                                             responses={speaker: reply}, replay=True)
    after = recipient_turn(product_db, as_id, "Что вы теперь знаете о переданных сведениях?")
    with product_db() as connection:
        whole = trace(connection, as_id)
    state = whole["state"]["state_json"]
    deliveries = [event for event in whole["events"] if event["event_type"] == "information_transferred"]
    openings = [event for event in whole["events"] if event["payload_json"].get("opened_source")]
    decisions = [
        {key: decision[key] for key in ("decision_id", "rule_id", "rule_version", "outcome", "decision_json")}
        for decision in whole["decisions"] if decision["rule_id"] in (
            f"E01_RECEIPT:confirmed:{speaker}", f"E01_RECEIPT:opened:{speaker}",
        )
    ]
    recorded, = [event for event in confirmation_events if event["event_type"] == "character_response"]
    export(f"receipt-{probe}.json", {
        "scenario": saved["execution_payload"]["runtime_rules"]["battery_scenario"]["ref"],
        "before": before, "delivery_text": sender_text if delivery_events else None,
        "extracted": link if delivery_events else None,
        "delivery_calls": delivery_calls, "delivery_events": deliveries,
        "participant_turn": question if question is not None else sender_text,
        "character_reply": recorded, "character_calls": calls, "opening_events": openings,
        "opening_decisions": decisions, "after": after,
        "pending_materials": state.get("battery_pending_materials", []),
        "opened_materials": state.get("battery_opened_materials", []),
        "transitions": [event for event in whole["events"] if event["event_type"].startswith("interaction_")],
    })
    assert recorded["payload_json"]["response"] == reply and recorded["payload_json"]["speaker_id"] == speaker
    assert not knows_fragment(before)
    assert all(not knows_fragment(call) for call in delivery_calls)
    assert len(deliveries) == int(probe != "undelivered")
    if probe.startswith("plain-") and opened:
        match, = [item["decision_json"] for item in decisions if item["outcome"] == "TRUE"]
        assert match["code"] == "MATCH" and match["details"]["text"] == evidence
    assert knows_fragment(after) is opened
    assert len(openings) == int(opened)
    if opened:
        acquisition, = after["context"]["opened_materials"]
        assert not state.get("battery_pending_materials")
        assert acquisition["recipient_id"] == RECIPIENT and acquisition["text"] == FRAGMENT
        assert acquisition["source"]["link"] == link and acquisition["source"]["version"] == version
        assert acquisition["source"]["fragment_sha256"] == sha256(FRAGMENT.encode()).hexdigest()
        assert acquisition["delivery_event_id"] == str(deliveries[0]["event_id"])
        assert acquisition["delivery_turn_id"] == deliveries[0]["cause_json"]["turn_id"]
        assert acquisition["confirmation_turn_id"] == openings[0]["cause_json"]["character_turn_id"]
        assert "E01_RECEIPT" in recorded["payload_json"]["scenario_event_ids"]
    elif deliveries:
        waiting, = state["battery_pending_materials"]
        assert waiting["recipient_id"] == RECIPIENT and waiting["source"]["link"] == link
    if probe == "correction":
        assert recorded["payload_json"]["scenario_event_id"] == "E02_CORRECT"
        assert recorded["payload_json"]["scenario_event_ids"] == ["E02_CORRECT", "E01_RECEIPT"]
