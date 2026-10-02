"""Техническая целостность доказательной цепочки; семантика проверяется GC."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ContextRef(Record):
    kind: Literal["turn", "event", "material"]
    id: str = Field(min_length=1)
    meaning: str = Field(min_length=1)


class Fragment(Record):
    id: str = Field(min_length=1)
    turn_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)


class Signal(Record):
    id: str = Field(min_length=1)
    fragment_id: str
    observation: str = Field(min_length=1)
    form_description: str = Field(min_length=1)
    context_refs: list[ContextRef]


class Attribution(Record):
    function: str = Field(min_length=1)
    product: str = Field(min_length=1)
    evidence_pattern: str = Field(min_length=1)
    boundaries: str = Field(min_length=1)


class Evidence(Record):
    id: str = Field(min_length=1)
    indicator_id: str
    m2_version: str
    type: Literal["Simple", "Composite"]
    interpretation: str = Field(min_length=1)
    bs_ids: list[str] = Field(min_length=1)
    fragment_ids: list[str] = Field(min_length=1)
    attribution: Attribution
    context_refs: list[ContextRef]
    limitations: list[str]
    composite_basis: str | None = None
    ordered_turn_ids: list[str]


class Bundle(Record):
    indicator_id: str
    evidence_ids: list[str]
    opportunity_basis: str = Field(min_length=1)
    context_refs: list[ContextRef]
    limitations: list[str]
    contradictions: list[str]


class AttributionNote(Record):
    indicator_id: str
    reason: Literal["irrelevant", "unclear"]
    explanation: str = Field(min_length=1)
    context_refs: list[ContextRef]


class EvidenceAnalysis(Record):
    schema_version: Literal[1]
    fragments: list[Fragment]
    signals: list[Signal]
    evidence: list[Evidence]
    bundles: list[Bundle]
    attribution_notes: list[AttributionNote]


def unique(items, key="id"):
    result = {getattr(x, key): x for x in items}
    if len(result) != len(items):
        raise ValueError("M6_DUPLICATE_ID")
    return result


def validate_analysis(value: dict, material: dict) -> dict:
    output = EvidenceAnalysis.model_validate(value)
    turns = {x["turn_id"]: x for x in material["turns"]}
    events = {x["event_id"]: x for x in material["events"]}
    materials = {x["material_id"]: x for x in material["materials"]}
    context = {"turn": set(turns), "event": set(events), "material": set(materials)}
    context_sequence = {
        "turn": {key: item["sequence_no"] for key, item in turns.items()},
        "event": {key: item["sequence_no"] for key, item in events.items()},
        "material": {key: item["available_sequence"] for key, item in materials.items()},
    }
    targets = {x["indicator_id"]: x for x in material["indicator_targets"]}
    criteria = {x["id"]: x for x in material["criteria"]}
    if len(criteria) != len(material["criteria"]) or set(criteria) != set(targets):
        raise ValueError("TARGET_SET_MISMATCH")
    fragments = unique(output.fragments)
    signals = unique(output.signals)
    evidence = unique(output.evidence)
    bundles = unique(output.bundles, "indicator_id")
    if set(bundles) != set(targets):
        raise ValueError("TARGET_SET_MISMATCH")
    for record in [*output.signals, *output.evidence, *output.bundles, *output.attribution_notes]:
        for ref in record.context_refs:
            if ref.id not in context[ref.kind]:
                raise ValueError("M6_CONTEXT_REFERENCE")
    for fragment in fragments.values():
        turn = turns.get(fragment.turn_id)
        if not turn or turn["speaker_type"] != "assessee":
            raise ValueError("M6_FRAGMENT_AUTHOR")
        if not fragment.start < fragment.end <= len(turn["content"]) or turn["content"][fragment.start:fragment.end] != fragment.quote:
            raise ValueError("M6_FRAGMENT_SPAN")
    for signal in signals.values():
        if signal.fragment_id not in fragments:
            raise ValueError("M6_SIGNAL_REFERENCE")
        boundary = turns[fragments[signal.fragment_id].turn_id]["sequence_no"]
        if any(context_sequence[ref.kind].get(ref.id, boundary + 1) > boundary for ref in signal.context_refs):
            raise ValueError("M6_CONTEXT_FUTURE")
    assigned = []
    for item in evidence.values():
        target = targets.get(item.indicator_id)
        if not target or item.m2_version != target["m2_version"]:
            raise ValueError("TARGET_SET_MISMATCH")
        criterion = criteria[item.indicator_id]
        expected_attribution = {
            "function": criterion["function"],
            "product": criterion["product"],
            "evidence_pattern": criterion["evidence_pattern"],
            "boundaries": criterion["boundary"],
        }
        if item.attribution.model_dump() != expected_attribution:
            raise ValueError("M6_ATTRIBUTION_MISMATCH")
        if len(set(item.bs_ids)) != len(item.bs_ids) or len(set(item.fragment_ids)) != len(item.fragment_ids):
            raise ValueError("M6_DUPLICATE_REFERENCE")
        if any(x not in signals for x in item.bs_ids):
            raise ValueError("M6_EVIDENCE_REFERENCE")
        if {signals[x].fragment_id for x in item.bs_ids} != set(item.fragment_ids):
            raise ValueError("M6_EVIDENCE_REFERENCE")
        if item.type == "Composite" and (len(item.bs_ids) < 2 or not item.composite_basis):
            raise ValueError("M6_COMPOSITE_BASIS")
        allowed_turns = {fragments[x].turn_id for x in item.fragment_ids}
        if any(x not in allowed_turns for x in item.ordered_turn_ids) or len(set(item.ordered_turn_ids)) != len(item.ordered_turn_ids):
            raise ValueError("M6_SEQUENCE_REFERENCE")
        if item.ordered_turn_ids != sorted(item.ordered_turn_ids, key=lambda x: turns[x]["sequence_no"]):
            raise ValueError("M6_SEQUENCE_ORDER")
        boundary = max(turns[fragments[x].turn_id]["sequence_no"] for x in item.fragment_ids)
        if any(context_sequence[ref.kind].get(ref.id, boundary + 1) > boundary for ref in item.context_refs):
            raise ValueError("M6_CONTEXT_FUTURE")
    for bundle in bundles.values():
        for eid in bundle.evidence_ids:
            if eid not in evidence or evidence[eid].indicator_id != bundle.indicator_id:
                raise ValueError("M6_BUNDLE_REFERENCE")
        assigned.extend(bundle.evidence_ids)
    if len(assigned) != len(set(assigned)) or set(assigned) != set(evidence):
        raise ValueError("M6_BUNDLE_REFERENCE")
    for note in output.attribution_notes:
        if note.indicator_id not in targets:
            raise ValueError("TARGET_SET_MISMATCH")
    return output.model_dump()


class CreateEvidenceRequest(Record):
    handoff_id: str
    mechanism_ref: Literal['m6_evidence/1.0.0']
    idempotency_key: str = Field(min_length=1, max_length=200)
    synthetic_material_confirmed: Literal[True]
