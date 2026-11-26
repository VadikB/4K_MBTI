"""Plan v1.2 turn effects without allowing the gateway to write facts or state."""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from Api.m5_addressed_scenario import SemanticTurnError, Transfer, _character_text, _fragment_bounds, _ids, _unique_start
from Api.m5_battery_contract import FACILITATOR, material_links
from Api.m5_rule_engine import CharacterReply, Decision, RuleOutcome, evaluate_rule


_LINK_MARKER = re.compile(r"[a-z][a-z0-9+.-]*://|\bwww\.", re.I)
_OPENING_LINK_MARKER = re.compile(_LINK_MARKER.pattern + r"|\bm5-material:/", re.I)


def scenario_contract(payload: dict) -> dict | None:
    return (payload.get("runtime_rules") or {}).get("battery_scenario")


@dataclass(frozen=True)
class Reply:
    speaker: str
    recipients: tuple[str, ...]
    rule_ids: tuple[str, ...]
    response: CharacterReply
    occurred_rule_ids: tuple[str, ...] | None = None
    opened_material: dict | None = None


@dataclass
class BatteryTurn:
    decisions: dict[str, tuple[dict, Decision]] = field(default_factory=dict)
    replies: list[Reply] = field(default_factory=list)
    deliveries: list[dict] = field(default_factory=list)
    transfers: list[tuple[str, Transfer]] = field(default_factory=list)
    link_deliveries: dict[str, dict] = field(default_factory=dict)
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


def _restrict_quote(fragments: list[dict], text: str, quote: str, recipients: list[str],
                    *, start: int | None = None) -> list[dict] | None:
    start = _unique_start(text, quote) if start is None else start
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


def _opening_quote_matches(reply: str, quote: str | None, link: str, question: str, *, allow_plain: bool) -> bool:
    if not quote:
        return False
    start = _unique_start(reply, quote)
    if start < 0:
        return False
    links = material_links(reply)
    if not allow_plain and not links:
        return all(token == link for _, token in material_links(question))
    end = start + len(quote)
    quoted_links = [(offset, token) for offset, token in links if offset < end and offset + len(token) > start]
    if any(token != link or offset < start or offset + len(token) > end for offset, token in quoted_links):
        return False
    # MATCH ties a plain quote to the delivered version. Any explicit address in it must be a complete source token.
    if not allow_plain:
        return bool(quoted_links)
    return all(any(offset <= start + marker.start() < offset + len(token) for offset, token in quoted_links)
               for marker in _OPENING_LINK_MARKER.finditer(quote))


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
    material_source = design.get("material_source") or {}
    linked_material = design.get("linked_material")
    receipt_id = material_source.get("event_id")
    follow_up = material_source.get("opening_follow_up")
    opening_evidence = material_source.get("opening_reply_evidence")
    allow_plain = material_source.get("opening_plain_confirmation", False)
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
        if rule_id == receipt_id:
            condition["instruction"] += " Для ссылки укажи её точный адрес без окружающего текста."
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
            if not _ids(recipients, selected) or not isinstance(quote, str) or not quote.strip():
                continue
            link_submission = rule_id == receipt_id and _LINK_MARKER.search(quote)
            if link_submission and follow_up:
                scopes = [_restrict_quote(plan.fragments, text, quote, recipients, start=start)
                          for start, token in material_links(text) if token == quote]
                addressed_scopes = [scope for scope in scopes if scope is not None]
                scoped = addressed_scopes[0] if len(addressed_scopes) == 1 else None
            else:
                scoped = _restrict_quote(plan.fragments, text, quote, recipients)
            if scoped is not None:
                if link_submission:
                    if (not linked_material or quote != linked_material["source"]["link"]
                            or not set(recipients) <= set(material_source["reader_ids"])
                            or material_source["material_id"] not in disclosed):
                        continue
                    plan.link_deliveries[rule_id] = linked_material
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

    pending_openings = {}
    if follow_up and linked_material:
        receipt_rule = next(event for event in design["events"] if event["id"] == receipt_id)
        for delivery in state.get("battery_pending_materials", []):
            speaker = delivery["recipient_id"]
            if delivery["source"] != linked_material["source"] or not mapping.get(speaker):
                continue
            selected_rules = pending_replies.get(speaker, ())
            addresses = {link for _, link in material_links(mapping[speaker])}
            delivered_link = delivery["source"]["link"]
            if opening_evidence:
                if selected_rules:
                    if receipt_id not in plan.link_deliveries:
                        pending_openings[speaker] = {**linked_material, **delivery}
                    continue
                if addresses and delivered_link not in addresses:
                    continue
            elif addresses - {delivered_link} or any(event["id"] == receipt_id for event, _ in selected_rules):
                continue
            key = f"{receipt_id}:follow_up:{speaker}"
            result = decide(key, {"follow_up": follow_up, "event_id": receipt_id, "speaker": speaker,
                                  "addressed_readable_link": delivery["source"],
                                  "delivery_turn_id": delivery["delivery_turn_id"]}, input_text=mapping[speaker])
            if (result.code, result.outcome) == ("MATCH", RuleOutcome.TRUE):
                pending_openings[speaker] = {**linked_material, **delivery}
                pending_replies.setdefault(speaker, []).insert(0, ({**receipt_rule, "decision_key": key}, []))

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
        speaker_context = {"dialogue_history": _private_history(state, speaker, turn_id)}
        sent_links = [plan.link_deliveries[event["id"]] for event, _ in selected_rules
                      if event["id"] in plan.link_deliveries]
        prior_link = pending_openings.get(speaker)
        if material_source:
            speaker_context["opened_materials"] = [item for item in state.get("battery_opened_materials", [])
                                                   if item["recipient_id"] == speaker]
            openable = [binding["source"] for binding in sent_links]
            if prior_link:
                openable.append(prior_link["source"])
            if openable:
                speaker_context["addressed_readable_links"] = openable
        reply = character.respond(material=reaction, character=role_card, text=mapping[speaker], turn_id=turn_id,
                                  context=speaker_context)
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
        rule_ids = tuple(event.get("decision_key", event["id"]) for event, _ in selected_rules)
        occurred = []
        opened_material = None
        for event, _ in selected_rules:
            if not event.get("reply_confirmation"):
                occurred.append(event["id"])
                continue
            pending = prior_link if "decision_key" in event else None
            link = pending or plan.link_deliveries.get(event["id"])
            if link and opening_evidence:
                continue
            if link and follow_up and any(token != link["source"]["link"] for _, token in material_links(reply.content)):
                continue
            confirmation = decide(f"{event['id']}:confirmed:{speaker}", {
                "instruction": design["instructions"]["confirm_reply"],
                "effect": material_source["opening_confirmation"] if link else event["reply_confirmation"],
                "event_id": event["id"], "speaker": speaker, "participant_message": mapping[speaker],
                **({"addressed_readable_link": link["source"]} if link else {}),
                **({"delivery_turn_id": pending["delivery_turn_id"]} if pending else {}),
            }, input_text=reply.content)
            if (confirmation.code, confirmation.outcome) == ("MATCH", RuleOutcome.TRUE):
                occurred.append(event["id"])
                if link and not (follow_up and any(item["source"] == link["source"]
                                                  for item in speaker_context["opened_materials"])):
                    opened_material = {"source": link["source"], "text": link["text"], "recipient_id": speaker,
                                       "delivery_turn_id": pending["delivery_turn_id"] if pending else turn_id}
        if opening_evidence and (link := sent_links[0] if sent_links else prior_link):
            source = link["source"]
            if not any(item["source"] == source for item in speaker_context["opened_materials"]):
                confirmation = decide(f"{receipt_id}:opened:{speaker}", {
                    "effect": material_source["opening_confirmation"], "reply_evidence": opening_evidence,
                    "event_id": receipt_id, "speaker": speaker, "participant_message": mapping[speaker],
                    "addressed_readable_link": source, "delivery_turn_id": link.get("delivery_turn_id", turn_id),
                }, input_text=reply.content, shape={"MATCH": {"required": ["text"]}})
                if ((confirmation.code, confirmation.outcome) == ("MATCH", RuleOutcome.TRUE)
                        and _opening_quote_matches(reply.content, (confirmation.details or {}).get("text"),
                                                   source["link"], mapping[speaker], allow_plain=allow_plain)):
                    if receipt_id not in occurred:
                        occurred.append(receipt_id)
                    opened_material = {"source": source, "text": link["text"], "recipient_id": speaker,
                                       "delivery_turn_id": link.get("delivery_turn_id", turn_id)}
        plan.replies.append(Reply(speaker, tuple(sorted(recipients - {speaker})), rule_ids, reply, tuple(occurred),
                                  opened_material))
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
