"""Continuity of the candidate's evidence basis across one provider retry."""
from collections import Counter, defaultdict
from dataclasses import dataclass

from pydantic import ValidationError

from Api.m6_contracts import (
    Bundle, Evidence, Fragment, FragmentQuote, Signal, ValidationIssues, assemble_fragment, candidate_records, fragment_turn,
    quote_position, validate_analysis,
)


@dataclass(frozen=True)
class PriorFragment:
    participant_turn_id: str | None
    ambiguous_quote: str | None
    has_signal: bool
    indicators: frozenset[str]


@dataclass(frozen=True)
class IndexedRecord:
    index: int
    value: dict


@dataclass(frozen=True)
class VerifiedEvidence:
    evidence: IndexedRecord
    sources: tuple[tuple[IndexedRecord, IndexedRecord], ...]


@dataclass(frozen=True)
class VerifiedReply:
    evidence: list[VerifiedEvidence]
    bundles: list[IndexedRecord]


def _typed_rows(value: object, field: str, model, turns: dict, *, key: str = "id") -> list[IndexedRecord]:
    records = [(index, record) for index, record in candidate_records(value, field)
               if isinstance(record.get(key), str)]
    counts = Counter(record[key] for _, record in records)
    rows = []
    for index, record in records:
        if counts[record[key]] != 1:
            continue
        try:
            typed = model.model_validate(record)
        except ValidationError:
            continue
        if isinstance(typed, FragmentQuote):
            data = assemble_fragment(typed, turns, f"{field}.{index}", ValidationIssues())
        else:
            data = typed.model_dump()
        if data is not None:
            rows.append(IndexedRecord(index, data))
    return rows


def verified_basis(value: object, material: dict, *, quote_contract: bool) -> VerifiedReply:
    """Identify separately valid evidence chains and indicator summaries in a rejected reply."""
    turns = {turn["turn_id"]: turn for turn in material["turns"]}
    rows = {
        "fragments": _typed_rows(value, "fragments", FragmentQuote if quote_contract else Fragment, turns),
        "signals": _typed_rows(value, "signals", Signal, turns),
        "evidence": _typed_rows(value, "evidence", Evidence, turns),
    }
    targets = {target["indicator_id"] for target in material["indicator_targets"]}
    owners = {row.value["id"]: row.value["indicator_id"] for row in rows["evidence"]}
    # A bundle with a foreign reference must not invalidate its rightful owner's bundle.
    rows["bundles"] = [
        row for row in _typed_rows(value, "bundles", Bundle, turns, key="indicator_id")
        if row.value["indicator_id"] in targets
        and all(owners.get(eid) == row.value["indicator_id"] for eid in row.value["evidence_ids"])
    ]
    projection = {"schema_version": 1, "attribution_notes": [],
                  **{field: [record.value for record in records] for field, records in rows.items()}}
    try:
        validate_analysis(projection, material, enforce_simple_basis=True)
    except ValueError as error:
        failures = getattr(error, "validation_issues", [])
        if not failures or any(issue["path"] == "criteria" for issue in failures):
            return VerifiedReply([], [])
    else:
        failures = []
    # Evidence can be sound even if the first reply did not assign it to a bundle.
    invalid = {
        tuple(issue["path"].split(".")[:2]) for issue in failures
        if not (issue["code"] == "M6_BUNDLE_REFERENCE" and issue["path"].startswith("evidence."))
    }
    valid = {
        field: {record.value["id"]: record for index, record in enumerate(records) if (field, str(index)) not in invalid}
        for field, records in rows.items() if field != "bundles"
    }
    verified = []
    for evidence in valid["evidence"].values():
        try:
            signals = [valid["signals"][identifier] for identifier in evidence.value["bs_ids"]]
            sources = tuple((signal, valid["fragments"][signal.value["fragment_id"]]) for signal in signals)
        except KeyError:
            continue
        verified.append(VerifiedEvidence(evidence, sources))
    verified_ids = defaultdict(set)
    for basis in verified:
        item = basis.evidence.value
        verified_ids[item["indicator_id"]].add(item["id"])
    bundles = [
        row for index, row in enumerate(rows["bundles"])
        if ("bundles", str(index)) not in invalid
        and set(row.value["evidence_ids"]) == verified_ids[row.value["indicator_id"]]
    ]
    return VerifiedReply(verified, bundles)


def _links(value: dict, indicators: set[str]) -> tuple[set[str], dict[str, set[str]]]:
    signal_fragments = {}
    for _, signal in candidate_records(value, "signals"):
        signal_id, fragment_id = signal.get("id"), signal.get("fragment_id")
        if isinstance(signal_id, str) and signal_id and isinstance(fragment_id, str) and fragment_id:
            signal_fragments.setdefault(signal_id, set()).add(fragment_id)
    # A conflicting signal ID does not establish a fragment-to-indicator link.
    fragment_by_signal = {key: next(iter(ids)) for key, ids in signal_fragments.items() if len(ids) == 1}
    by_fragment: dict[str, set[str]] = {}
    for _, record in candidate_records(value, "evidence"):
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
    for index, record in candidate_records(value, "fragments"):
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


def _reassessment_reasons(value: dict) -> set[tuple[str, str, str]]:
    empty_indicators = {bundle["indicator_id"] for bundle in value["bundles"] if not bundle["evidence_ids"]}
    empty_indicators.difference_update(item["indicator_id"] for item in value["evidence"])
    return {
        (note["indicator_id"], ref["id"], note["reason"])
        for note in value["attribution_notes"]
        if note["indicator_id"] in empty_indicators and note["explanation"].strip()
        for ref in note["context_refs"]
        if ref["kind"] == "turn" and ref["meaning"].strip()
    }


def validate_verified_basis(value: dict, prior: list[VerifiedEvidence]) -> None:
    reasons = _reassessment_reasons(value)
    required: dict[str, dict[str, IndexedRecord]] = {"fragments": {}, "signals": {}, "evidence": {}}
    for basis in prior:
        evidence = basis.evidence
        indicator = evidence.value["indicator_id"]
        evidence_required = False
        for signal, fragment in basis.sources:
            turn_id = fragment.value["turn_id"]
            if (indicator, turn_id, "irrelevant") in reasons:
                continue
            required["fragments"][fragment.value["id"]] = fragment
            required["signals"][signal.value["id"]] = signal
            if (indicator, turn_id, "unclear") not in reasons:
                evidence_required = True
        if evidence_required:
            required["evidence"][evidence.value["id"]] = evidence

    issues = ValidationIssues()
    for field, records in required.items():
        current = {record["id"]: (index, record) for index, record in enumerate(value[field])}
        for identifier, original in records.items():
            if identifier not in current:
                issues.add("M6_REPAIR_BASIS_MISSING", f"{field}.{original.index}.id")
                continue
            index, record = current[identifier]
            for key, previous in original.value.items():
                if record[key] != previous:
                    issues.add("M6_REPAIR_BASIS_CHANGED", f"{field}.{index}.{key}")
    issues.raise_if_any()


def validate_verified_bundles(value: dict, prior: VerifiedReply, material: dict) -> None:
    """Protect a sound summary unless the validated retry has grounds to update it."""
    current = {row["indicator_id"]: (index, row) for index, row in enumerate(value["bundles"])}
    evidence = {item["id"]: item for item in value["evidence"]}
    reasons = {(indicator, turn_id) for indicator, turn_id, _ in _reassessment_reasons(value)}
    participant_turns = {turn["turn_id"] for turn in material["turns"] if turn["speaker_type"] == "assessee"}
    prior_evidence = {basis.evidence.value["id"]: basis for basis in prior.evidence}
    issues = ValidationIssues()
    for original in prior.bundles:
        previous = original.value
        indicator = previous["indicator_id"]
        index, row = current[indicator]
        previous_ids = set(previous["evidence_ids"])
        old_payloads = [
            {key: field for key, field in prior_evidence[eid].evidence.value.items() if key != "id"}
            for eid in previous_ids
        ]
        if any(
            {key: field for key, field in evidence[eid].items() if key != "id"} not in old_payloads
            for eid in set(row["evidence_ids"]) - previous_ids
        ):
            continue
        if previous_ids:
            source_turns = {
                fragment.value["turn_id"] for eid in previous_ids for _, fragment in prior_evidence[eid].sources
            }
        else:
            source_turns = {
                ref["id"] for ref in previous["context_refs"] if ref["kind"] == "turn" and ref["id"] in participant_turns
            }
        if any((indicator, turn_id) in reasons for turn_id in source_turns):
            continue
        for field, old_value in previous.items():
            if row[field] != old_value:
                issues.add("M6_REPAIR_BUNDLE_CHANGED", f"bundles.{index}.{field}")
    issues.raise_if_any()


def validate_repaired_basis(value: dict, prior: dict[str, PriorFragment]) -> None:
    issues = ValidationIssues()
    fragments = {item["id"]: (index, item) for index, item in enumerate(value["fragments"])}
    indicators = {indicator for basis in prior.values() for indicator in basis.indicators}
    with_signal, links = _links(value, indicators)
    reasons = _reassessment_reasons(value)
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
