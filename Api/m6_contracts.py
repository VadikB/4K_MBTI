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


class FragmentQuote(Record):
    id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class EvidenceCandidate(Record):
    schema_version: Literal[2]
    fragments: list[FragmentQuote]
    signals: list[Signal]
    evidence: list[Evidence]
    bundles: list[Bundle]
    attribution_notes: list[AttributionNote]


class ValidationIssues:
    def __init__(self):
        self.items: list[dict[str, str]] = []
        self.primary_code: str | None = None

    def add(self, code: str, path: str, *, legacy_code: str | None = None):
        self.items.append({"code": code, "path": path})
        if self.primary_code is None:
            self.primary_code = legacy_code or code

    def raise_if_any(self):
        if self.primary_code is not None:
            error = ValueError(self.primary_code)
            error.validation_issues = self.items
            raise error


def quote_position(content: str, quote: str) -> tuple[int, str | None]:
    start = content.find(quote)
    if start < 0:
        return start, "M6_FRAGMENT_QUOTE_NOT_FOUND"
    if content.find(quote, start + 1) >= 0:
        return -1, "M6_FRAGMENT_QUOTE_AMBIGUOUS"
    return start, None


def fragment_turn(turns: dict, turn_id: str, path: str, issues: ValidationIssues,
                  *, legacy_code: str | None = None):
    turn = turns.get(turn_id)
    if turn is None:
        issues.add("M6_FRAGMENT_TURN_UNKNOWN", f"{path}.turn_id", legacy_code=legacy_code)
        return None
    if turn["speaker_type"] != "assessee":
        issues.add("M6_FRAGMENT_AUTHOR", f"{path}.turn_id")
        return None
    return turn


def check_fragment_span(content: str, start: int | None, end: int | None, quote: str | None,
                        path: str, issues: ValidationIssues) -> None:
    """Check the v1 span, including readable citation fields in a rejected fragment."""
    if start is not None and end is not None:
        if start < end <= len(content):
            if quote is not None:
                if content[start:end] == quote:
                    return
                issues.add("M6_FRAGMENT_RANGE_MISMATCH", f"{path}.quote", legacy_code="M6_FRAGMENT_SPAN")
        else:
            if start >= len(content):
                issues.add("M6_FRAGMENT_RANGE_INVALID", f"{path}.start", legacy_code="M6_FRAGMENT_SPAN")
            if end <= start or end > len(content):
                issues.add("M6_FRAGMENT_RANGE_INVALID", f"{path}.end", legacy_code="M6_FRAGMENT_SPAN")
    if quote is not None:
        _, reason = quote_position(content, quote)
        if reason:
            issues.add(reason, f"{path}.quote", legacy_code="M6_FRAGMENT_SPAN")


def candidate_records(candidate: object, field: str):
    if not isinstance(candidate, dict) or not isinstance(candidate.get(field), list):
        return
    for index, record in enumerate(candidate[field]):
        if isinstance(record, dict):
            yield index, record


def assemble_fragment(fragment: FragmentQuote, turns: dict, path: str, issues: ValidationIssues) -> dict | None:
    turn = fragment_turn(turns, fragment.turn_id, path, issues)
    if turn is None:
        return None
    start, reason = quote_position(turn["content"], fragment.quote)
    if reason:
        issues.add(reason, f"{path}.quote")
        return None
    return {**fragment.model_dump(), "start": start, "end": start + len(fragment.quote)}


def assemble_analysis(value: dict, material: dict) -> dict:
    candidate = EvidenceCandidate.model_validate(value)
    turns = {item["turn_id"]: item for item in material["turns"]}
    issues = ValidationIssues()
    fragments = []
    for index, fragment in enumerate(candidate.fragments):
        assembled = assemble_fragment(fragment, turns, f"fragments.{index}", issues)
        if assembled is not None:
            fragments.append(assembled)
    issues.raise_if_any()
    return {**candidate.model_dump(), "schema_version": 1, "fragments": fragments}


def _index_unique(items, field: str, issues: ValidationIssues, *, key="id"):
    result = {}
    for index, item in enumerate(items):
        identifier = getattr(item, key)
        if identifier in result:
            issues.add("M6_DUPLICATE_ID", f"{field}.{index}.{key}")
        else:
            result[identifier] = item
    return result


def _duplicate_entries(values, path: str, issues: ValidationIssues, code: str):
    seen = set()
    for index, value in enumerate(values):
        if value in seen:
            issues.add(code, f"{path}.{index}")
        seen.add(value)


def validate_analysis(value: dict, material: dict, *, enforce_simple_basis: bool = False) -> dict:
    output = EvidenceAnalysis.model_validate(value)
    issues = ValidationIssues()
    turns = {x["turn_id"]: x for x in material["turns"]}
    context_sequence = {
        "turn": {key: item["sequence_no"] for key, item in turns.items()},
        "event": {item["event_id"]: item["sequence_no"] for item in material["events"]},
        "material": {item["material_id"]: item["available_sequence"] for item in material["materials"]},
    }
    targets = {x["indicator_id"]: x for x in material["indicator_targets"]}
    criteria = {x["id"]: x for x in material["criteria"]}
    if len(criteria) != len(material["criteria"]) or set(criteria) != set(targets):
        issues.add("TARGET_SET_MISMATCH", "criteria")
        issues.raise_if_any()
    fragments = _index_unique(output.fragments, "fragments", issues)
    signals = _index_unique(output.signals, "signals", issues)
    evidence = _index_unique(output.evidence, "evidence", issues)
    bundles = _index_unique(output.bundles, "bundles", issues, key="indicator_id")
    if set(bundles) != set(targets):
        issues.add("TARGET_SET_MISMATCH", "bundles")
    for field in ("signals", "evidence", "bundles", "attribution_notes"):
        for index, record in enumerate(getattr(output, field)):
            for ref_index, ref in enumerate(record.context_refs):
                if ref.id not in context_sequence[ref.kind]:
                    issues.add("M6_CONTEXT_REFERENCE", f"{field}.{index}.context_refs.{ref_index}.id")
    for index, fragment in enumerate(output.fragments):
        path = f"fragments.{index}"
        turn = fragment_turn(turns, fragment.turn_id, path, issues, legacy_code="M6_FRAGMENT_AUTHOR")
        if turn is not None:
            check_fragment_span(turn["content"], fragment.start, fragment.end, fragment.quote, path, issues)

    def check_future(refs, path, boundary):
        for index, ref in enumerate(refs):
            sequence = context_sequence[ref.kind].get(ref.id)
            if sequence is not None and sequence > boundary:
                issues.add("M6_CONTEXT_FUTURE", f"{path}.context_refs.{index}.id")

    for index, signal in enumerate(output.signals):
        path = f"signals.{index}"
        fragment = fragments.get(signal.fragment_id)
        if fragment is None:
            issues.add("M6_SIGNAL_REFERENCE", f"{path}.fragment_id")
        elif fragment.turn_id in turns:
            check_future(signal.context_refs, path, turns[fragment.turn_id]["sequence_no"])

    for index, item in enumerate(output.evidence):
        path = f"evidence.{index}"
        target = targets.get(item.indicator_id)
        if target is None:
            issues.add("TARGET_SET_MISMATCH", f"{path}.indicator_id")
        else:
            if item.m2_version != target["m2_version"]:
                issues.add("TARGET_SET_MISMATCH", f"{path}.m2_version")
            criterion = criteria[item.indicator_id]
            for field, expected in (("function", "function"), ("product", "product"),
                                    ("evidence_pattern", "evidence_pattern"), ("boundaries", "boundary")):
                if getattr(item.attribution, field) != criterion[expected]:
                    issues.add("M6_ATTRIBUTION_MISMATCH", f"{path}.attribution.{field}")
        _duplicate_entries(item.bs_ids, f"{path}.bs_ids", issues, "M6_DUPLICATE_REFERENCE")
        _duplicate_entries(item.fragment_ids, f"{path}.fragment_ids", issues, "M6_DUPLICATE_REFERENCE")
        missing_signals = False
        for ref_index, signal_id in enumerate(item.bs_ids):
            if signal_id not in signals:
                missing_signals = True
                issues.add("M6_EVIDENCE_REFERENCE", f"{path}.bs_ids.{ref_index}")
        if not missing_signals and {signals[x].fragment_id for x in item.bs_ids} != set(item.fragment_ids):
            issues.add("M6_EVIDENCE_REFERENCE", f"{path}.fragment_ids")
        if item.type == "Composite":
            if len(item.bs_ids) < 2:
                issues.add("M6_COMPOSITE_BASIS", f"{path}.bs_ids")
            if not item.composite_basis:
                issues.add("M6_COMPOSITE_BASIS", f"{path}.composite_basis")
        allowed_turns = {fragments[x].turn_id for x in item.fragment_ids if x in fragments}
        invalid_order_ref = False
        for ref_index, turn_id in enumerate(item.ordered_turn_ids):
            if turn_id not in allowed_turns:
                invalid_order_ref = True
                issues.add("M6_SEQUENCE_REFERENCE", f"{path}.ordered_turn_ids.{ref_index}")
        _duplicate_entries(item.ordered_turn_ids, f"{path}.ordered_turn_ids", issues, "M6_SEQUENCE_REFERENCE")
        if not invalid_order_ref and all(x in turns for x in item.ordered_turn_ids):
            if item.ordered_turn_ids != sorted(item.ordered_turn_ids, key=lambda x: turns[x]["sequence_no"]):
                issues.add("M6_SEQUENCE_ORDER", f"{path}.ordered_turn_ids")
        if allowed_turns and all(x in fragments for x in item.fragment_ids) and allowed_turns <= turns.keys():
            boundary = max(turns[x]["sequence_no"] for x in allowed_turns)
            check_future(item.context_refs, path, boundary)

    assigned = set()
    for index, bundle in enumerate(output.bundles):
        for ref_index, eid in enumerate(bundle.evidence_ids):
            if eid in assigned or eid not in evidence or evidence[eid].indicator_id != bundle.indicator_id:
                issues.add("M6_BUNDLE_REFERENCE", f"bundles.{index}.evidence_ids.{ref_index}")
            assigned.add(eid)
    for index, item in enumerate(output.evidence):
        if item.id not in assigned:
            issues.add("M6_BUNDLE_REFERENCE", f"evidence.{index}.id")
    for index, note in enumerate(output.attribution_notes):
        if note.indicator_id not in targets:
            issues.add("TARGET_SET_MISMATCH", f"attribution_notes.{index}.indicator_id")
    if enforce_simple_basis:
        for index, item in enumerate(output.evidence):
            if item.type == "Simple" and len(item.bs_ids) != 1:
                issues.add("M6_SIMPLE_BASIS", f"evidence.{index}.bs_ids")
    issues.raise_if_any()
    return output.model_dump()


class CreateEvidenceRequest(Record):
    handoff_id: str
    mechanism_ref: Literal['m6_evidence/1.0.0']
    idempotency_key: str = Field(min_length=1, max_length=200)
    synthetic_material_confirmed: Literal[True]
