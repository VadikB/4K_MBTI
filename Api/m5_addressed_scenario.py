"""Plan the effects of a turn against a sealed, addressed scenario."""
from __future__ import annotations

from dataclasses import dataclass, field

from Api.m5_rule_engine import CharacterReply, Decision, RuleOutcome, evaluate_rule


class SemanticTurnError(ValueError):
    """The turn is saved and can be classified again with the same identity."""

    def __init__(self, code: str, decisions: dict[str, tuple[dict, Decision]]):
        super().__init__(code)
        self.decisions = decisions


@dataclass(frozen=True)
class Transfer:
    sender_id: str
    recipient_ids: tuple[str, ...]
    text: str


@dataclass
class TurnPlan:
    decisions: dict[str, tuple[dict, Decision]] = field(default_factory=dict)
    replies: dict[str, CharacterReply] = field(default_factory=dict)
    ending: str | None = None
    update: bool = False
    transfer: Transfer | None = None
    fragments: list[dict] | None = None


def scenario_contract(payload: dict) -> dict | None:
    return (payload.get("runtime_rules") or {}).get("scenario_contract")


def _ids(value: object, allowed: set[str]) -> bool:
    return (isinstance(value, list) and bool(value)
            and all(isinstance(item, str) and item in allowed for item in value)
            and len(set(value)) == len(value))


def _transfer(decision: Decision, *, text: str, update_text: str, sender_id: str,
              roles: set[str]) -> Transfer | None:
    if ((decision.code, decision.outcome) not in {
        ("DIRECT", RuleOutcome.TRUE), ("DELEGATE", RuleOutcome.TRUE)
    } or not isinstance(decision.details, dict)):
        return None
    recipients = decision.details.get("recipient_ids")
    message = decision.details.get("text")
    direct = decision.code == "DIRECT"
    if not _ids(recipients, roles if direct else roles - {sender_id}):
        return None
    if not isinstance(message, str) or not message.strip() or message not in (text if direct else update_text):
        return None
    return Transfer("assessee" if direct else sender_id, tuple(recipients), message)


def _unique_start(text: str, quote: str) -> int:
    start = text.find(quote)
    return start if start >= 0 and text.find(quote, start + 1) < 0 else -1


def _fragment_bounds(fragments: object, text: str, roles: set[str]) -> list[dict]:
    if not isinstance(fragments, list):
        return []
    bounds = []
    for fragment in fragments:
        if not isinstance(fragment, dict) or not _ids(fragment.get("recipient_ids"), roles):
            return []
        quote = fragment.get("text")
        if not isinstance(quote, str) or not quote.strip():
            return []
        start = _unique_start(text, quote)
        if start < 0:
            return []
        end = start + len(quote)
        if "end_text" in fragment:
            end_quote = fragment["end_text"]
            if not isinstance(end_quote, str) or not end_quote.strip():
                return []
            end_start = _unique_start(text, end_quote)
            if end_start < end:
                return []
            end = end_start + len(end_quote)
        bounds.append({"start": start, "end": end, "recipient_ids": fragment["recipient_ids"]})
    bounds.sort(key=lambda item: item["start"])
    if any(left["end"] > right["start"] for left, right in zip(bounds, bounds[1:])):
        return []
    return bounds


def _character_text(text: str, fragments: list[dict], speaker_id: str) -> str:
    return "\n".join(text[item["start"]:item["end"]] for item in fragments if speaker_id in item["recipient_ids"])


def _character_history(state: dict, speaker_id: str, turn_id: str, plan: TurnPlan,
                       update_sequence: int | None) -> tuple[list[dict], list[str]]:
    shares = {item["message_turn_id"]: item for item in state.get("addressed_transfers", [])}
    transfer = plan.transfer
    if transfer and transfer.sender_id == "assessee":
        shares[turn_id] = {"text": transfer.text, "recipient_ids": transfer.recipient_ids}
    facts = [item["text"] for item in shares.values() if speaker_id in item["recipient_ids"]]
    if transfer and transfer.sender_id != "assessee" and speaker_id in transfer.recipient_ids:
        facts.append(transfer.text)

    saved_fragments = state.get("turn_fragments", {})
    withheld = set(state.get("withheld_turn_ids", ()))
    history = []
    for item in state["dialogue_history"]:
        item_id = item["turn_id"]
        if item_id in withheld:
            continue
        share = shares.get(item_id)
        if share:
            if speaker_id in share["recipient_ids"]:
                history.append({**item, "content_text": share["text"]})
        elif item["speaker_type"] == "assessee":
            fragments = plan.fragments if item_id == turn_id else saved_fragments.get(item_id)
            if fragments is not None:
                content = _character_text(item["content_text"], fragments, speaker_id)
                if content:
                    history.append({**item, "content_text": content})
            elif update_sequence is None or item["sequence_no"] < update_sequence:
                history.append(item)
        elif item["speaker_id"] == speaker_id:
            history.append(item)
    return history, facts


def plan_turn(payload: dict, state: dict, *, text: str, turn_id: str, semantic, character) -> TurnPlan:
    design = scenario_contract(payload)
    plan = TurnPlan()
    cards = {item["character_id"]: item["closed_card"] for item in payload["characters"]}
    roster = {speaker_id: {"name": card["Имя"], "role": card["Роль"], **design["roles"][speaker_id]}
              for speaker_id, card in cards.items()}
    events = design["events"]
    update = events["E01_UPDATE"]
    material_id = update["material_ids"][0]
    disclosed = material_id in state["disclosed_materials"]
    if disclosed:
        plan.fragments = []
    public_state = {key: state[key] for key in ("status", "current_stage", "dialogue_history", "events")}
    public_state.update(roster=roster, update_delivered=disclosed)

    def decide(event_id, condition, codes, true_codes, *, details_by_code=None, data=None):
        rule = {"rule_id": event_id, "version": "3" if event_id == "E03_REPLY" else "2", "type": "semantic_decision",
                "condition": condition, "allowed_codes": list(codes), "true_codes": list(true_codes),
                "details_by_code": details_by_code or {}}
        result = evaluate_rule(rule, state=public_state, data=data or {}, text=text, turn_id=turn_id,
                               semantic_adapter=semantic)
        plan.decisions[event_id] = rule, result
        if result.outcome == RuleOutcome.ERROR:
            raise SemanticTurnError(result.code, plan.decisions)
        return result

    control = design["control"]
    intent = decide("SCENARIO_CONTROL", control, control["codes"], ("CONTINUE",))
    if intent.code in {"FINAL", "STOP"} and intent.outcome == RuleOutcome.FALSE:
        plan.ending = intent.code
        return plan
    if intent.code != "CONTINUE" or intent.outcome != RuleOutcome.TRUE:
        return plan

    update_sequence = None
    if not disclosed:
        decision = decide("E01_UPDATE", update["condition"], ("MATCH", "NO_MATCH", "UNKNOWN"), ("MATCH",))
        if decision.code == "MATCH" and decision.outcome == RuleOutcome.TRUE:
            plan.update = True
            return plan
    else:
        # If a saved delivery has no recoverable boundary, hide unaddressed history.
        update_sequence = next((event["sequence_no"] for event in state["events"]
                                if event["event_type"] == "mandatory_update" and event["material_id"] == material_id), 0)
        transfer = events["E02_TRANSFER"]
        record = next(item for item in payload["materials"] if item["material_id"] == material_id)
        update_text = record["participant_payload"]["Текст"]
        sender_id = update["speaker_ids"][0]
        transfer_codes = ("DIRECT", "DELEGATE")
        decision = decide("E02_TRANSFER", {"condition": transfer["condition"], "codes": transfer["classification"]},
                          (*transfer_codes, "NO_MATCH", "UNKNOWN"), transfer_codes,
                          details_by_code={code: {"required": ["recipient_ids", "text"]} for code in transfer_codes},
                          data={"delivered_text": update_text, "sender_id": sender_id})
        plan.transfer = _transfer(decision, text=text, update_text=update_text, sender_id=sender_id, roles=set(cards))
        if not plan.transfer and (decision.code, decision.outcome) != ("NO_MATCH", RuleOutcome.FALSE):
            return plan

    reply = events["E03_REPLY"]
    classify_audience = disclosed and not plan.transfer
    reply_details = {"MATCH": {"required": ["speaker_ids"]}}
    condition = {"condition": reply["condition"], "output": reply["classification"]}
    if classify_audience:
        reply_details["MATCH"]["required"].append("fragments")
        reply_details.update({code: {"optional": ["fragments"]} for code in ("NO_MATCH", "UNKNOWN")})
        condition["audience"] = (
            "Раздели последнее message на непересекающиеся точные цитаты по фактическим адресатам. "
            "Для каждой части верни её text и recipient_ids из roster. Для длинной части допустимо вернуть "
            "в text её точное начало, а в end_text её точный конец. Начало и конец должны встречаться в message "
            "ровно по одному разу. recipient_ids относятся ко всей части от начала до конца. "
            "Отдели личное уточнение от соседних вопросов. Для действительно общей части укажи весь roster. "
            "Пропусти части с неясной аудиторией. speaker_ids означает персонажей, которые отвечают."
        )
    choice = decide("E03_REPLY", condition, ("MATCH", "NO_MATCH", "UNKNOWN"), ("MATCH",),
                    details_by_code=reply_details)
    details = choice.details if isinstance(choice.details, dict) else {}
    if classify_audience:
        plan.fragments = _fragment_bounds(details.get("fragments"), text, set(cards))
    speakers = details.get("speaker_ids")
    if choice.code != "MATCH" or choice.outcome != RuleOutcome.TRUE or not _ids(speakers, set(reply["speaker_ids"])):
        return plan
    for material in payload["materials"]:
        speaker_id = material.get("speaker_id")
        if material["kind"] != "character_reaction" or speaker_id not in speakers:
            continue
        if plan.transfer:
            current = plan.transfer.text if speaker_id in plan.transfer.recipient_ids else ""
        elif plan.fragments is None:
            current = text
        else:
            current = _character_text(text, plan.fragments, speaker_id)
        if not current:
            continue
        history, facts = _character_history(state, speaker_id, turn_id, plan, update_sequence)
        card = cards[speaker_id]
        if disclosed and speaker_id == sender_id:
            facts.append(update_text)
        plan.replies[material["material_id"]] = character.respond(
            material=material,
            character={"character_id": speaker_id, "role_card": card, "public_position": card["Текст"],
                       "known_facts": [*card["Начальные знания"], *facts],
                       "disclosure_constraints": {"rule": material["result_check"], "recipient_ids": ["assessee"]}},
            text=current, turn_id=turn_id, context={"dialogue_history": history, "stage": state["current_stage"]},
        )
    return plan
