"""SPEC.08 paired controls over persisted C-34 and addressed Dialogue."""

import json
from hashlib import sha256
from uuid import uuid4

import pytest

from Api.m5_battery_preparation import prepare_next
from Api.m5_scenario_runtime import trace, transition
from tests.integration.test_m5_battery_scenario_db import ids, matched, prepare_and_start, specialist, submit
from tests.integration.test_m5_battery_v04_db import CURRENT_FRAGMENT, SPEC08_LINK, export, start_case, v04
from tests.integration.test_m5_spec08_delivery_db import DeliveryGateway, RECIPIENT, recipient_turn
from tests.integration.test_m10_product_path_db import product_db


pytestmark = pytest.mark.integration
FRAGMENT = "Ручная сверка 24 записей, без проверки автозапуска"
OPENING = "Теперь открыл ту ссылку на версию 4, которую вы мне прислали, и прочитал фрагмент."
QUESTION = "Вы уже открыли ранее присланную ссылку?"


class ReadbackGateway(DeliveryGateway):
    def __init__(self, *, title=None, version="4", repair=True):
        super().__init__()
        self.title = title
        self.version = version
        self.repair_defect = repair

    def chat_with_trace(self, messages, **kwargs):
        response = super().chat_with_trace(messages, **kwargs)
        routing = kwargs["routing_key"]
        if ":generation:" not in routing:
            return response
        candidate = json.loads(response.content)
        repairing = ":repair:" in routing and self.repair_defect
        version = "rev-4" if repairing and self.version == "ред 4" else self.version
        for row in candidate["Материалы"]:
            if row["MaterialID"] == "M02":
                row["Текст"] = (row["Текст"].replace("Версия: 4", f"Версия: {version}")
                               .replace(SPEC08_LINK, f"m5-material://M02/{version}")
                               .replace(CURRENT_FRAGMENT, FRAGMENT))
            if row["MaterialID"] == self.title and not repairing:
                row["Название"] = FRAGMENT
        response.content = json.dumps(candidate, ensure_ascii=False)
        self.generation_io[-1]["raw_response"] = response.content
        return response


def knowledge(request):
    return request["character"]["known_facts"], request["context"].get("opened_materials", [])


def knows_fragment(request):
    return FRAGMENT in json.dumps(knowledge(request), ensure_ascii=False)


@pytest.mark.parametrize("title,repair", [(None, True), ("M02", True), ("M03", True), ("M02", False), ("M03", False)])
def test_spec08_initial_titles_are_guarded(product_db, v04, title, repair):
    cycle, session = start_case(product_db, v04[0][0], 8)
    gateway = ReadbackGateway(title=title, repair=repair)
    if repair:
        as_id, saved = prepare_and_start(product_db, cycle, session, gateway)
        run = saved["execution_payload"]["ai_operations"]["functional_personalization"]
        recipient = recipient_turn(product_db, as_id)
        author = recipient_turn(product_db, as_id, recipient="R_AUTHOR")
        export(f"ecd-title-{title or 'normal'}-repaired.json", {"generation": gateway.generation_io,
               "recipient": recipient, "author": author, "server": run["tester"]["aggregation"], "repair": run.get("repair")})
        assert not knows_fragment(recipient) and knows_fragment(author)
        assert "актуальная версия — 4" in json.dumps(knowledge(recipient), ensure_ascii=False)
        assert len(gateway.generation_io) == (2 if title else 1)
        if title:
            failure, = run["repair"]["original_tester"]["aggregation"]["deterministic_failures"]
            assert failure["path"] == f"candidate_as/Материалы/{title}/Название"
    else:
        result = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=str(uuid4()),
                              actor=99, gateway=gateway)
        export(f"ecd-title-{title}-rejected.json", {"generation": gateway.generation_io, "preparation": result})
        assert result["status"] == "preparation_rejected" and len(gateway.generation_io) == 2
        assert not result.get("execution_payload") and not any(body.get("review_dispatch") for _, _, body in gateway.calls)


@pytest.mark.parametrize("sent,selected,passes", [
    ("m5-material://M02/40", "m5-material://M02/40", False),
    ("m5-material://M02/40", SPEC08_LINK, False),
    (SPEC08_LINK, SPEC08_LINK, True),
    (FRAGMENT, FRAGMENT, True),
])
def test_spec08_uses_the_complete_address_in_the_addressed_turn(product_db, v04, sent, selected, passes):
    cycle, session = start_case(product_db, v04[0][0], 8)
    as_id, _ = prepare_and_start(product_db, cycle, session, ReadbackGateway())
    before = recipient_turn(product_db, as_id)
    text = f"Получатель, направляю «{sent}», посмотрите."
    events, delivered_to = submit(product_db, as_id, text, {
        "E01_RECEIPT": matched(recipient_ids=[RECIPIENT], text=selected), "@confirmed:E01_RECEIPT": matched(),
    }, recipients=(RECIPIENT,), responses={RECIPIENT: OPENING if sent != FRAGMENT else "Получил этот текст."}, replay=True)
    after = recipient_turn(product_db, as_id, "Что получено?")
    with product_db() as connection:
        got = trace(connection, as_id)
    received = knows_fragment(after) or any(FRAGMENT in row["content_text"] for row in after["context"]["dialogue_history"])
    label = "quote" if sent == FRAGMENT else "valid" if passes else "invalid-full" if sent == selected else "invalid-shortened"
    export(f"ecd-address-{label}.json", {"turn": text, "extracted": selected, "events": events, "before": before,
           "delivery_request": delivered_to, "after": after, "state": got["state"]["state_json"]})
    assert not knows_fragment(before) and received is passes
    assert len(ids(events, "information_transferred")) == int(passes)
    if passes and sent == SPEC08_LINK:
        assert after["context"]["opened_materials"][0]["source"]["version"] == "4"


@pytest.mark.parametrize("mode", ["late", "resumed", "unknown", "undelivered", "promise", "other", "wrong_version"])
def test_spec08_late_opening_is_tied_to_delivered_source(product_db, v04, mode):
    cycle, session = start_case(product_db, v04[0][0], 8)
    as_id, _ = prepare_and_start(product_db, cycle, session, ReadbackGateway())
    before = recipient_turn(product_db, as_id)
    delivered, delivered_to = [], []
    delivery_text = f"Получатель, передаю {SPEC08_LINK}."
    if mode != "undelivered":
        delivered, delivered_to = submit(product_db, as_id, delivery_text, {
            "E01_RECEIPT": matched(recipient_ids=[RECIPIENT], text=SPEC08_LINK),
        }, recipients=(RECIPIENT,), responses={RECIPIENT: "Ссылку вижу. Открою позже."}, replay=True)
    if mode == "resumed":
        with product_db() as connection:
            transition(connection, assessment_situation_id=as_id, action="pause", reason="synthetic", request_id="before-open")
            transition(connection, assessment_situation_id=as_id, action="resume", reason="synthetic", request_id="continue-open")
            connection.commit()
    speaker = "R_AUTHOR" if mode == "other" else RECIPIENT
    opening = {"unknown": "Какую-то ссылку видел. Не уверен, о какой речь.",
               "promise": "Пока только собираюсь открыть эту ссылку."}.get(mode, OPENING)
    request = "Вы какую-нибудь ссылку открывали?" if mode == "unknown" else QUESTION
    if mode == "wrong_version":
        request = "Вы уже открыли m5-material://M02/40?"
    observed, calls = submit(product_db, as_id, request, {
        "E04_CLARIFY": matched(speaker_ids=[speaker]),
        "@follow_up:E01_RECEIPT": matched() if mode != "unknown" else {"code": "UNKNOWN"},
        "@confirmed:E01_RECEIPT": matched() if mode not in {"unknown", "promise"} else {"code": "NO_MATCH"},
    }, recipients=(speaker,), responses={speaker: opening}, replay=True)
    after = recipient_turn(product_db, as_id, "Какие рабочие сведения вы получили?")
    with product_db() as connection:
        whole = trace(connection, as_id)
    state = whole["state"]["state_json"]
    export(f"ecd-opening-{mode}.json", {"before": before, "delivery_turn": delivery_text if delivered else None,
           "extracted": SPEC08_LINK if delivered else None, "delivery_request": delivered_to, "delivery": delivered,
           "question": request, "reply": opening, "confirmation_request": calls, "confirmation": observed,
           "events": whole["events"], "after": after, "state": state, "decisions": whole["decisions"]})
    assert not knows_fragment(before) and not any(knows_fragment(call) for call in delivered_to)
    assert len(ids(whole["events"], "information_transferred")) == int(mode != "undelivered")
    opens = [event for event in whole["events"] if event["payload_json"].get("opened_source")]
    if mode in {"late", "resumed"}:
        assert knows_fragment(after)
        opened, = state["battery_opened_materials"]
        assert opened["source"]["fragment_sha256"] == sha256(FRAGMENT.encode()).hexdigest()
        assert opened["delivery_turn_id"] == delivered[0]["cause_json"]["turn_id"]
        assert opened["source"]["version"] == "4" and opened["recipient_id"] == RECIPIENT
        event, = opens
        assert event["cause_json"]["character_turn_id"] == opened["confirmation_turn_id"]
    else:
        assert not knows_fragment(after) and not state.get("battery_opened_materials") and not opens


@pytest.mark.parametrize("version,repair", [("rev-4", True), ("ред-4", True), ("ред 4", True), ("ред 4", False)])
def test_spec08_technical_version_has_one_contract(product_db, v04, version, repair):
    cycle, _ = start_case(product_db, v04[0][0], 8)
    gateway = ReadbackGateway(version=version, repair=repair)
    result = prepare_next(product_db, cycle_id=str(cycle["cycle_id"]), assessment_situation_id=str(uuid4()), actor=99, gateway=gateway)
    label = {"rev-4": "latin", "ред-4": "cyrillic"}.get(version, "invalid-repaired" if repair else "invalid-rejected")
    export(f"ecd-identifier-{label}.json", {"version": version, "generation": gateway.generation_io, "preparation": result})
    assert result["status"] == ("rejected" if repair else "preparation_rejected")
    assert len(gateway.generation_io) == (2 if " " in version else 1)
    first = "\n".join(row["content"] for row in gateway.generation_io[0]["messages"] if row["role"] == "system")
    assert "rev-4" in first and "ред-4" in first
    if " " in version:
        request = json.loads(gateway.generation_io[-1]["messages"][-1]["content"])
        issue, = request["deterministic_failures"]
        assert issue["path"] == "candidate_as/Материалы/M02/Текст"
        assert "ред-4" in issue["expected"]["examples"]
    if repair:
        compiled = result["execution_payload"]["runtime_rules"]["battery_scenario"]["linked_material"]
        chosen = "rev-4" if " " in version else version
        assert compiled["source"]["version"] == chosen and compiled["source"]["link"] == f"m5-material://M02/{chosen}"
