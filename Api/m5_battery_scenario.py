"""Plan v1.2 turn effects without allowing the gateway to write facts or state."""
from __future__ import annotations

from dataclasses import dataclass, field

from Api.m5_addressed_scenario import SemanticTurnError, Transfer, _character_text, _fragment_bounds, _ids, _unique_start
from Api.m5_battery_contract import FACILITATOR
from Api.m5_rule_engine import CharacterReply, Decision, RuleOutcome, evaluate_rule


def scenario_contract(payload: dict) -> dict | None:
    return (payload.get("runtime_rules") or {}).get("battery_scenario")


@dataclass(frozen=True)
class Reply:
    speaker: str
    recipients: tuple[str, ...]
    rule_ids: tuple[str, ...]
    response: CharacterReply
    occurred_rule_ids: tuple[str, ...] | None = None


@dataclass
class BatteryTurn:
    decisions: dict[str, tuple[dict, Decision]] = field(default_factory=dict)
    replies: list[Reply] = field(default_factory=list)
    deliveries: list[dict] = field(default_factory=list)
    transfers: list[tuple[str, Transfer]] = field(default_factory=list)
    fragments: list[dict] = field(default_factory=list)
    ending: str | None = None


def _private_history(state: dict, speaker: str, current_turn: str) -> list[dict]:
    audiences = state.get("battery_audiences", {})
    fragments = state.get("battery_fragments", {})
    history = []
    for item in state["dialogue_history"]:
        turn_id = item["turn_id"]
        if turn_id == current_turn:
            continue
        if item["speaker_type"] == "assessee":
            content = _character_text(item["content_text"], fragments.get(turn_id, []), speaker)
            if content:
                history.append({**item, "content_text": content})
        elif speaker == item["speaker_id"] or speaker in audiences.get(turn_id, []):
            history.append(item)
    return history


def _restrict_quote(fragments: list[dict], text: str, quote: str, recipients: list[str]) -> list[dict] | None:
    start = _unique_start(text, quote)
    end = start + len(quote)
    for index, fragment in enumerate(fragments):
        if (fragment["start"] <= start < end <= fragment["end"]
                and set(recipients) <= set(fragment["recipient_ids"])):
            parts = [
                {**fragment, "end": start},
                {"start": start, "end": end, "recipient_ids": recipients},
                {**fragment, "start": end},
            ]
            return [*fragments[:index], *(part for part in parts if part["start"] < part["end"]), *fragments[index + 1:]]
    return None


def plan_turn(payload: dict, state: dict, *, text: str, turn_id: str, semantic, character) -> BatteryTurn:
    design = scenario_contract(payload)
    plan = BatteryTurn()
    roles = set(design["roles"])
    speakers = roles or {FACILITATOR}
    cards = {row["character_id"]: row for row in payload["characters"]}
    disclosed = set(state["disclosed_materials"])
    documents = design["concrete_materials"]
    facts = design["concrete_facts"]
    public_documents = {key: documents[key] for key in disclosed if key in documents}
    context = {
        "material_ids_already_available": sorted(disclosed),
        "prior_turns": [item for item in state["dialogue_history"] if item["turn_id"] != turn_id],
        "roles": {key: {"name": cards[key]["closed_card"]["Имя"], "function": role["source"]}
                  for key, role in design["roles"].items()},
    }

    def decide(key, condition, *, input_text=text, codes=("MATCH", "NO_MATCH", "UNKNOWN"), true=("MATCH",), shape=None):
        rule = {"rule_id": key, "version": design["ref"]["version"], "type": "semantic_decision",
                "condition": condition, "allowed_codes": list(codes), "true_codes": list(true), "details_by_code": shape or {}}
        value = evaluate_rule(rule, state=context, data={"public_materials": public_documents},
                              text=input_text, turn_id=turn_id, semantic_adapter=semantic)
        plan.decisions[key] = rule, value
        if value.outcome == RuleOutcome.ERROR:
            raise SemanticTurnError(value.code, plan.decisions)
        return value

    control = decide("SCENARIO_CONTROL", {"rule": design["control"]["question"], "finish": design["finish"]},
                     codes=("CONTINUE", "FINAL", "STOP", "UNKNOWN"), true=("CONTINUE",))
    if control.code in {"FINAL", "STOP"} and control.outcome == RuleOutcome.FALSE:
        plan.ending = control.code
        return plan
    if (control.code, control.outcome) != ("CONTINUE", RuleOutcome.TRUE):
        if control.code == "UNKNOWN":
            plan.replies.append(Reply(FACILITATOR, ("assessee",), ("SCENARIO_CONTROL",),
                                      CharacterReply("COMPLETED", design["control"]["clarification"], "scenario_contract")))
        return plan

    if len(roles) > 1:
        route = decide("SCENARIO_AUDIENCE", design["instructions"]["audience"],
                       shape={"MATCH": {"required": ["fragments"]}})
        if (route.code, route.outcome) == ("MATCH", RuleOutcome.TRUE):
            plan.fragments = _fragment_bounds((route.details or {}).get("fragments"), text, roles)
    else:
        plan.fragments = [{"start": 0, "end": len(text), "recipient_ids": sorted(speakers)}]
    mapping = {speaker: _character_text(text, plan.fragments, speaker) for speaker in sorted(speakers)}

    pending_replies: dict[str, list[tuple[dict, list[str]]]] = {}
    pending_deliveries = []
    for event in design["events"]:
        rule_id = event["id"]
        kind = event["kind"]
        if event["requires_material_id"] and event["requires_material_id"] not in disclosed:
            continue
        if event["delivery_id"] in disclosed:
            continue
        eligible = roles if event.get("requires_prior_replies") else event["speaker_ids"]
        selected = {speaker for speaker in eligible if mapping[speaker]}
        if not selected:
            continue
        condition = {"passport_rule": event["passport"], "allowed_speakers": sorted(selected),
                     "audience_instruction": design["instructions"]["audience"], "allowed_facts": event["fact_ids"],
                     "instruction": "Для реакции выбери затронутых говорящих. Для фактов выбери только затронутые ID."
                                    " Для передачи укажи точную переданную цитату и её фактических получателей."
                                    " Для пересылки укажи адресатов конкретной просьбы и точную разрешённую цитату из уже предъявленного материала."}
        if kind == "delivery":
            shape = {"MATCH": {"required": ["speaker_ids"]}} if event.get("requires_prior_replies") else {}
        elif kind in {"transfer", "transfer_reply"}:
            shape = {"MATCH": {"required": ["recipient_ids", "text"]}}
        elif kind == "forward":
            shape = {"MATCH": {"required": ["recipient_ids", "text"]}}
        else:
            shape = {"MATCH": {"required": ["speaker_ids"], "optional": ["fact_ids"]}}
        result = decide(rule_id, condition, shape=shape)
        if (result.code, result.outcome) != ("MATCH", RuleOutcome.TRUE):
            continue
        details = result.details or {}
        if kind == "delivery":
            required = details.get("speaker_ids") if event.get("requires_prior_replies") else []
            if not event.get("requires_prior_replies") or _ids(required, selected):
                pending_deliveries.append((event, required))
        elif kind in {"transfer", "transfer_reply"}:
            recipients, quote = details.get("recipient_ids"), details.get("text")
            scoped = (_restrict_quote(plan.fragments, text, quote, recipients)
                      if _ids(recipients, selected) and isinstance(quote, str) and quote.strip() else None)
            if scoped is not None:
                plan.fragments = scoped
                mapping = {speaker: _character_text(text, scoped, speaker) for speaker in mapping}
                plan.transfers.append((rule_id, Transfer("assessee", tuple(recipients), quote)))
                if kind == "transfer_reply":
                    for recipient in recipients:
                        pending_replies.setdefault(recipient, []).append((event, []))
        elif kind == "forward":
            recipients = details.get("recipient_ids")
            quote = details.get("text")
            sender, = event["speaker_ids"]
            material = documents[event["requires_material_id"]]["Текст"]
            if _ids(recipients, roles - {sender}) and isinstance(quote, str) and quote.strip() and quote in material:
                pending_replies.setdefault(sender, []).append(({**event, "forward_to": recipients, "forward_text": quote}, []))
        else:
            chosen = details.get("speaker_ids")
            fact_ids = details.get("fact_ids", [])
            if not _ids(chosen, selected) or (fact_ids and not _ids(fact_ids, set(event["fact_ids"]))):
                continue
            if event["fact_ids"] and not fact_ids:
                continue
            for speaker in chosen:
                pending_replies.setdefault(speaker, []).append((event, fact_ids))

    materials_with_author = {event["delivery_id"]: event["speaker_ids"][0] for event in design["events"] if event["delivery_id"]}
    for speaker, selected_rules in pending_replies.items():
        known_ids = set(design["roles"].get(speaker, {}).get("known_material_ids", ()))
        known_ids |= {key for key, owner in materials_with_author.items() if key in disclosed and speaker == owner}
        if speaker == FACILITATOR:
            known_ids = disclosed - {"P00"}
        permitted_facts = {key for _, ids in selected_rules for key in ids}
        authority = design["roles"].get(speaker, {}).get("source", "Ведущий поясняет предъявленный пакет.")
        role_card = {"character_id": speaker, "role_card": authority,
                     "knowledge_limits": design["roles"].get(speaker, {}).get("knowledge_limits", {}), "known_facts": [
            *[documents[key] for key in sorted(known_ids)],
            *design.get("scoped_materials", {}).get(speaker, ()),
            *[facts[key] for key in sorted(permitted_facts)],
        ]}
        rules = [event["passport"] for event, _ in selected_rules]
        reaction = {"material_id": f"CHARACTER.{speaker}", "reaction_rule": {
            "authority": design["instructions"]["authority"], "rules": rules,
        }}
        reply = character.respond(material=reaction, character=role_card, text=mapping[speaker], turn_id=turn_id,
                                  context={"dialogue_history": _private_history(state, speaker, turn_id)})
        if reply.status != "COMPLETED" or not reply.content:
            continue
        restricted = [value for key, value in facts.items() if key not in permitted_facts]
        restricted += [documents[key]["Текст"] for key in materials_with_author if key not in known_ids or key not in disclosed]
        if any(value.casefold() in reply.content.casefold() for value in restricted):
            continue
        recipients = {"assessee"}
        if any(event["audience"] == "addressed" for event, _ in selected_rules):
            for fragment in plan.fragments:
                if speaker in fragment["recipient_ids"]:
                    recipients.update(fragment["recipient_ids"])
        rule_ids = tuple(event["id"] for event, _ in selected_rules)
        occurred = []
        for event, _ in selected_rules:
            if not event.get("reply_confirmation"):
                occurred.append(event["id"])
                continue
            confirmation = decide(f"{event['id']}:confirmed:{speaker}", {
                "instruction": design["instructions"]["confirm_reply"], "effect": event["reply_confirmation"],
                "event_id": event["id"], "speaker": speaker, "participant_message": mapping[speaker],
            }, input_text=reply.content)
            if (confirmation.code, confirmation.outcome) == ("MATCH", RuleOutcome.TRUE):
                occurred.append(event["id"])
        plan.replies.append(Reply(speaker, tuple(sorted(recipients - {speaker})), rule_ids, reply, tuple(occurred)))
        for event, _ in selected_rules:
            if "forward_to" not in event:
                continue
            accepted = decide(event["id"] + ":accepted", {
                "instruction": design["instructions"]["accept_forward"],
                "recipients": event["forward_to"], "participant_request": mapping[speaker],
                "authorized_content": event["forward_text"],
            }, input_text=reply.content)
            if (accepted.code, accepted.outcome) == ("MATCH", RuleOutcome.TRUE):
                plan.transfers.append((event["id"], Transfer(speaker, tuple(event["forward_to"]), event["forward_text"])))

    for event, required in pending_deliveries:
        actual = {reply.speaker for reply in plan.replies
                  if set(reply.rule_ids).intersection(event.get("requires_prior_replies", ()))}
        if set(required) <= actual:
            plan.deliveries.append(event)
    return plan
