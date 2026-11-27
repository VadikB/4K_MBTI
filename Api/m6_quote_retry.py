"""Continuity of the candidate's evidence basis across one provider retry."""
from dataclasses import dataclass

from pydantic import ValidationError

from Api.m6_contracts import ValidationIssues, fragment_turn, quote_position


@dataclass(frozen=True)
class PriorFragment:
    participant_turn_id: str | None
    ambiguous_quote: str | None
    has_signal: bool
    indicators: frozenset[str]


def _records(value: dict, field: str):
    records = value.get(field)
    if isinstance(records, list):
        for index, record in enumerate(records):
            if isinstance(record, dict):
                yield index, record


def _links(value: dict, indicators: set[str]) -> tuple[set[str], dict[str, set[str]]]:
    signal_fragments = {}
    for _, signal in _records(value, "signals"):
        signal_id, fragment_id = signal.get("id"), signal.get("fragment_id")
        if isinstance(signal_id, str) and signal_id and isinstance(fragment_id, str) and fragment_id:
            signal_fragments.setdefault(signal_id, set()).add(fragment_id)
    # A conflicting signal ID does not establish a fragment-to-indicator link.
    fragment_by_signal = {key: next(iter(ids)) for key, ids in signal_fragments.items() if len(ids) == 1}
    by_fragment: dict[str, set[str]] = {}
    for _, record in _records(value, "evidence"):
        indicator = record.get("indicator_id")
        signal_ids, fragment_ids = record.get("bs_ids"), record.get("fragment_ids")
        if not isinstance(indicator, str) or indicator not in indicators:
            continue
        if not isinstance(signal_ids, list) or not isinstance(fragment_ids, list):
            continue
        for signal_id in signal_ids:
            fragment = fragment_by_signal.get(signal_id) if isinstance(signal_id, str) else None
            if fragment is not None and fragment in fragment_ids:
                by_fragment.setdefault(fragment, set()).add(indicator)
    return set(fragment_by_signal.values()), by_fragment


def rejected_basis(value: object, material: dict, error: ValueError) -> dict[str, PriorFragment]:
    """Read typed references from a rejected reply even if its other fields fail schema."""
    if not isinstance(value, dict):
        return {}
    turns = {item["turn_id"]: item for item in material["turns"]}
    indicators = {item["indicator_id"] for item in material["indicator_targets"]}
    with_signal, links = _links(value, indicators)
    issues = ValidationIssues()
    prior: dict[str, PriorFragment] = {}
    for index, record in _records(value, "fragments"):
        identifier, turn_id, quote = record.get("id"), record.get("turn_id"), record.get("quote")
        if not isinstance(identifier, str) or not identifier:
            continue
        path = f"fragments.{index}"
        turn = fragment_turn(turns, turn_id, path, issues) if isinstance(turn_id, str) and turn_id else None
        reason = None
        ambiguous_quote = None
        if turn is not None and isinstance(quote, str) and quote:
            _, reason = quote_position(turn["content"], quote)
            if reason:
                issues.add(reason, f"{path}.quote")
            if reason == "M6_FRAGMENT_QUOTE_AMBIGUOUS":
                ambiguous_quote = quote
        targets = frozenset(links.get(identifier, ()))
        if turn is None or reason or targets:
            prior.setdefault(identifier, PriorFragment(
                turn_id if turn is not None else None, ambiguous_quote, identifier in with_signal, targets,
            ))
    if isinstance(error, ValidationError):
        error.validation_issues = issues.items
    return prior


def validate_repaired_basis(value: dict, prior: dict[str, PriorFragment]) -> None:
    issues = ValidationIssues()
    fragments = {item["id"]: (index, item) for index, item in enumerate(value["fragments"])}
    indicators = {indicator for basis in prior.values() for indicator in basis.indicators}
    with_signal, links = _links(value, indicators)
    empty_indicators = {bundle["indicator_id"] for bundle in value["bundles"] if not bundle["evidence_ids"]}
    empty_indicators.difference_update(item["indicator_id"] for item in value["evidence"])
    reasons = {
        (note["indicator_id"], ref["id"], note["reason"])
        for note in value["attribution_notes"]
        if note["indicator_id"] in empty_indicators and note["explanation"].strip()
        for ref in note["context_refs"]
        if ref["kind"] == "turn" and ref["meaning"].strip()
    }
    for identifier, basis in prior.items():
        turn_id = basis.participant_turn_id
        irrelevant = {indicator for indicator in basis.indicators if (indicator, turn_id, "irrelevant") in reasons}
        all_irrelevant = bool(irrelevant) and basis.indicators == irrelevant
        if identifier not in fragments:
            if not all_irrelevant:
                issues.add("M6_FRAGMENT_REPAIR_MISSING", "fragments")
            continue
        index, fragment = fragments[identifier]
        if basis.ambiguous_quote is not None:
            if fragment["turn_id"] != turn_id:
                issues.add("M6_FRAGMENT_REPAIR_TURN", f"fragments.{index}.turn_id")
            if basis.ambiguous_quote not in fragment["quote"]:
                issues.add("M6_FRAGMENT_REPAIR_QUOTE", f"fragments.{index}.quote")
        signal_present = identifier in with_signal
        if basis.has_signal and not signal_present and not all_irrelevant:
            issues.add("M6_FRAGMENT_REPAIR_SIGNAL_MISSING", "signals")
        unresolved = basis.indicators - links.get(identifier, set()) - irrelevant
        for indicator in sorted(unresolved):
            if not (signal_present and fragment["turn_id"] == turn_id and (indicator, turn_id, "unclear") in reasons):
                issues.add("M6_FRAGMENT_REPAIR_EVIDENCE_MISSING", "evidence")
    issues.raise_if_any()
