"""SPEC.08 generation and addressed knowledge through the real QA lifecycle."""

import json
from hashlib import sha256
from uuid import uuid4

import pytest

from Api.m5_battery_preparation import prepare_next
from Api.m5_scenario_runtime import trace, transition
from tests.integration.test_m5_battery_scenario_db import ids, matched, prepare_and_start, specialist, submit
from tests.integration.test_m5_battery_v04_db import (
    CURRENT_FRAGMENT, RECIPIENT_CARD, SPEC08_LINK, V04Gateway, export, start_case, v04,
)
from tests.integration.test_m10_product_path_db import product_db


pytestmark = pytest.mark.integration
RECIPIENT = "R_RECIPIENT"
PROFILE_HEADING = "[Актуальный профильный фрагмент]"
CARD_HEADING = "[Исходная карточка]"
WINDOW_HEADING = "[Окно и подготовка получателя]"
LIMITS_HEADING = "[Остальные условия]"
M02_PATH = "candidate_as/Материалы/M02/Текст"


class DeliveryGateway(V04Gateway):
    def __init__(self, defect=None, *, repeat=False):
        super().__init__()
        self.defect = defect
        self.repeat = repeat
        self.generation_io = []

    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        routing = kwargs["routing_key"]
        if ":generation:" in routing:
            candidate = json.loads(response.content)
            material = next(row for row in candidate["Материалы"] if row["MaterialID"] == "M02")
            text = material["Текст"]
            if self.repeat or ":repair:" not in routing:
                if self.defect == "heading":
                    text = text.replace(CARD_HEADING, "[Старая карточка]")
                elif self.defect == "duplicate":
                    text = text.replace(RECIPIENT_CARD, RECIPIENT_CARD + "\n" + CURRENT_FRAGMENT)
            material["Текст"] = text
            response.content = json.dumps(candidate, ensure_ascii=False)
            self.generation_io.append({"operation": routing, "messages": messages, "raw_response": response.content})
        return response


def recipient_turn(product_db, as_id, text="Что известно до передачи?", *, recipient=RECIPIENT):
    events, calls = submit(product_db, as_id, text, {"E04_CLARIFY": matched(speaker_ids=[recipient])},
                           recipients=(recipient,))
    assert ids(events) == ["E04_CLARIFY"]
    return calls[0]


def test_spec08_generation_and_repair_receive_scoped_instruction(product_db, v04):
    runs = {}
    for defect in (None, "heading"):
        cycle, session = start_case(product_db, v04[0][0], 8)
        gateway = DeliveryGateway(defect)
        _, saved = prepare_and_start(product_db, cycle, session, gateway)
        result = saved["execution_payload"]["ai_operations"]["functional_personalization"]
        runs[defect or "valid"] = {"generation_io": gateway.generation_io, "server": result["tester"]["aggregation"]}
    export("SPEC08-generation-repair.json", runs)
    assert len(runs["valid"]["generation_io"]) == 1
    assert len(runs["heading"]["generation_io"]) == 2
    for run in runs.values():
        assert run["server"]["status"] == "PASS"
        for call in run["generation_io"]:
            system = "\n".join(message["content"] for message in call["messages"] if message["role"] == "system")
            assert all(heading in system for heading in (PROFILE_HEADING, CARD_HEADING, WINDOW_HEADING, LIMITS_HEADING))
            assert "собственное окно" in system and "в том же порядке" in system
    repair_request = json.loads(runs["heading"]["generation_io"][-1]["messages"][-1]["content"])
    failure, = repair_request["deterministic_failures"]
    assert failure["path"] == M02_PATH
    assert CARD_HEADING in failure["expected"]
    assert "[Старая карточка]" in failure["actual"]["headings"]


@pytest.mark.parametrize("repeat", [False, True])
def test_spec08_exact_copy_cannot_enter_initial_knowledge(product_db, v04, repeat):
    cycle, session = start_case(product_db, v04[0][0], 8)
    gateway = DeliveryGateway("duplicate", repeat=repeat)
    if repeat:
        result = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=str(uuid4()),
                              actor=99, gateway=gateway)
        export("SPEC08-copy-rejected.json", {"generation_io": gateway.generation_io, "result": result})
        assert result["status"] == "preparation_rejected"
        assert len(gateway.generation_io) == 2
        assert not any(body.get("review_dispatch") for _, _, body in gateway.calls)
        return
    as_id, saved = prepare_and_start(product_db, cycle, session, gateway)
    result = saved["execution_payload"]["ai_operations"]["functional_personalization"]
    before = recipient_turn(product_db, as_id)
    export("SPEC08-copy-repaired.json", {"generation_io": gateway.generation_io, "repair": result.get("repair"),
                                         "server": result["tester"]["aggregation"], "first_request": before})
    assert CURRENT_FRAGMENT not in json.dumps(before, ensure_ascii=False)
    assert "актуальная версия — 4" in json.dumps(before, ensure_ascii=False)
    assert len(gateway.generation_io) == 2
    failure, = result["repair"]["original_tester"]["aggregation"]["deterministic_failures"]
    assert failure["path"] == M02_PATH and failure["actual"]["visible_section"] == CARD_HEADING


@pytest.mark.parametrize("method", ["quote", "link", "unconfirmed", "denied", "stale", "wrong_recipient", "promise"])
def test_spec08_acquired_knowledge_stays_with_recipient(product_db, v04, method):
    cycle, session = start_case(product_db, v04[0][0], 8)
    gateway = DeliveryGateway()
    as_id, saved = prepare_and_start(product_db, cycle, session, gateway)
    before = recipient_turn(product_db, as_id)
    assert CURRENT_FRAGMENT not in json.dumps(before, ensure_ascii=False)
    recipient = "R_AUTHOR" if method == "wrong_recipient" else RECIPIENT
    value = {"quote": CURRENT_FRAGMENT, "denied": "m5-material://M02/4/restricted",
             "stale": "m5-material://M02/3"}.get(method, SPEC08_LINK)
    message = "После согласования пришлю фрагмент." if method == "promise" else f"Направляю {recipient}: {value}"
    rules = {} if method == "promise" else {"E01_RECEIPT": matched(recipient_ids=[recipient], text=value)}
    if method != "unconfirmed":
        rules["@confirmed:E01_RECEIPT"] = matched()
    reply = {"quote": "Получил текст версии 4.", "unconfirmed": "Вижу ссылку, ещё не открывал."}.get(
        method, "Открыл ссылку на версию 4 и прочитал её фрагмент.")
    events, on_delivery = submit(product_db, as_id, message, rules, recipients=(recipient,),
                                 responses={recipient: reply}, replay=True)
    after = recipient_turn(product_db, as_id, "Что удалось получить?")
    with product_db() as connection:
        transition(connection, assessment_situation_id=as_id, action="pause", reason="synthetic", request_id="pause")
        transition(connection, assessment_situation_id=as_id, action="resume", reason="synthetic", request_id="resume")
        state = trace(connection, as_id)["state"]["state_json"]
        connection.commit()
    resumed = recipient_turn(product_db, as_id, "Какие точные сведения у вас есть после паузы?")
    author = recipient_turn(product_db, as_id, "К вам пришла адресная передача?", recipient="R_AUTHOR")
    generation = saved["execution_payload"]["ai_operations"]["functional_personalization"]
    export(f"SPEC08-{method}.json", {"gateway": "SYNTHETIC CONTROLLED", "generation_io": gateway.generation_io,
                                     "source": generation["source_snapshot"]["refs"], "as": generation["accepted_as"],
                                     "server": generation["tester"]["aggregation"], "first_request": before,
                                     "on_delivery": on_delivery, "events": events, "after": after,
                                     "resumed": resumed, "other_role": author, "state": state})
    received = method in {"link", "quote"}
    for request in (after, resumed):
        assert (CURRENT_FRAGMENT in json.dumps(request, ensure_ascii=False)) is received
    assert not author["context"].get("opened_materials")
    if method == "link":
        assert CURRENT_FRAGMENT not in json.dumps(on_delivery, ensure_ascii=False)
        opened, = resumed["context"]["opened_materials"]
        assert opened["source"]["version"] == "4" and opened["source"]["material_id"] == "M02"
        assert opened["source"]["fragment_sha256"] == sha256(CURRENT_FRAGMENT.encode()).hexdigest()
        assert opened["recipient_id"] == RECIPIENT and opened["text"] == CURRENT_FRAGMENT
        assert ids(events, "information_transferred") == ["E01_RECEIPT"]
    if method in {"unconfirmed", "denied", "stale", "wrong_recipient", "promise"}:
        assert not state.get("battery_opened_materials")
    if method in {"denied", "stale", "wrong_recipient", "promise"}:
        assert not ids(events, "information_transferred")
