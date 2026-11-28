"""Scoped continuity for the versioned Evidence retry."""
from dataclasses import dataclass

from pydantic import ValidationError

from Api.m6_candidate_v3 import attach_criterion_attribution
from Api.m6_contracts import ValidationIssues, candidate_records, fragment_turn, quote_position
from Api.m6_quote_retry import (
    IndexedRecord, LinkAddress, PriorFragment, VerifiedReply, indexed_rows, link_address, rejected_basis,
    validate_repaired_basis, validate_verified_basis, validate_verified_bundles, verified_basis,
)
from Api.m6_validation_retry import validation_failure


class LinkIssues(ValidationIssues):
    def add(self, code: str, path: str, *, legacy_code: str | None = None, **details: str):
        super().add(code, path, legacy_code=legacy_code)
        self.items[-1].update(details)


@dataclass(frozen=True)
class EvidenceLink:
    evidence: IndexedRecord
    signal: IndexedRecord
    fragment: IndexedRecord

    @property
    def address(self) -> LinkAddress:
        return link_address(self.evidence.value, self.signal.value)

    def at_path(self, path: str) -> bool:
        fields = {"evidence": self.evidence, "signals": self.signal, "fragments": self.fragment}
        field, _, index = path.partition(".")
        return field in fields and index.split(".")[0] == str(fields[field].index)

    def details(self) -> dict:
        turn = self.fragment.value.get("turn_id")
        return {**self.address._asdict(), "turn_id": turn if isinstance(turn, str) else ""}


def _links(value: object) -> list[EvidenceLink]:
    fragments = {record.value["id"]: record for record in indexed_rows(value, "fragments")}
    signals = {record.value["id"]: record for record in indexed_rows(value, "signals")}
    links = {}
    for evidence in indexed_rows(value, "evidence"):
        indicator = evidence.value.get("indicator_id")
        fragment_ids, signal_ids = evidence.value.get("fragment_ids"), evidence.value.get("bs_ids")
        if not isinstance(indicator, str) or not isinstance(fragment_ids, list) or not isinstance(signal_ids, list):
            continue
        for signal_id in signal_ids:
            signal = signals.get(signal_id) if isinstance(signal_id, str) else None
            fragment_id = signal.value.get("fragment_id") if signal else None
            fragment = fragments.get(fragment_id) if isinstance(fragment_id, str) else None
            if fragment is not None and fragment_id in fragment_ids:
                link = EvidenceLink(evidence, signal, fragment)
                links[link.address] = link
    return list(links.values())


@dataclass(frozen=True)
class RepairBasis:
    links: list[EvidenceLink]
    verified: VerifiedReply
    unlinked_citations: dict[str, PriorFragment]
    feedback: dict


def collect_repair_basis(value: object, material: dict, error: ValueError) -> RepairBasis:
    citations = rejected_basis(value, material, error)
    targets = {target["indicator_id"] for target in material["indicator_targets"]}
    links = [link for link in _links(value) if link.address.indicator_id in targets]
    invalid_rows = frozenset(
        (path[0], path[1]) for issue in error.errors(include_input=False) if len(path := issue["loc"]) >= 2
        and isinstance(path[1], int)
    ) if isinstance(error, ValidationError) else frozenset()
    hydrated = attach_criterion_attribution(value, material) if isinstance(value, dict) else value
    verified = verified_basis(hydrated, material, quote_contract=True, invalid_rows=invalid_rows)
    verified_addresses = {
        link_address(item.evidence.value, signal.value)
        for item in verified.evidence for signal, _ in item.sources
    }
    _, failures = validation_failure(error)
    readable = []
    for link in links:
        if link.address in verified_addresses:
            continue
        violations = [
            issue for issue in (*failures, *verified.failures)
            if link.at_path(issue["path"])
        ]
        readable.append({
            **link.details(),
            "violations": list({(item["code"], item["path"]): item for item in violations}.values())
            or [{"code": "M6_LINK_NOT_VERIFIED", "path": f"evidence.{link.evidence.index}"}],
        })
    linked_fragments = {link.address.fragment_id for link in links}
    return RepairBasis(links, verified, {key: item for key, item in citations.items() if key not in linked_fragments}, {
        "verified_links": [link.details() for link in links if link.address in verified_addresses],
        "verified_bundles": [row.value["indicator_id"] for row in verified.bundles],
        "readable_links": readable,
    })


def _relation(address: LinkAddress) -> tuple[str, str, str]:
    return address.indicator_id, address.fragment_id, address.signal_id


def _valid_reviews(notes: list[dict], previous: dict[LinkAddress, EvidenceLink],
                   relations: set[tuple[str, str, str]], material: dict) -> dict[LinkAddress, str]:
    reviews = {}
    issues = LinkIssues()
    turns = {row["turn_id"]: row for row in material["turns"]}
    for index, note in enumerate(notes):
        address = LinkAddress(*(note[field] for field in LinkAddress._fields))
        original = previous.get(address)
        details = {**address._asdict(), "turn_id": note["turn_id"]}
        path = f"repair_notes.{index}"
        if fragment_turn(turns, note["turn_id"], path, issues) is None:
            issues.items[-1].update(details)
        elif original is None:
            issues.add("M6_REPAIR_NOTE_UNKNOWN_LINK", path, **details)
        elif note["turn_id"] != original.fragment.value.get("turn_id"):
            issues.add("M6_REPAIR_NOTE_OTHER_TURN", f"{path}.turn_id", **details)
        elif address in reviews:
            issues.add("M6_REPAIR_NOTE_DUPLICATE", path, **details)
        elif _relation(address) in relations:
            issues.add("M6_REPAIR_NOTE_LINK_STILL_PRESENT", path, **details)
        else:
            reviews[address] = note["reason"]
    issues.raise_if_any()
    return reviews


def _validate_sources(value: dict, prior: RepairBasis, material: dict, reviews: dict[LinkAddress, str],
                      relations: set[tuple[str, str, str]]) -> None:
    turns = {row["turn_id"]: row["content"] for row in material["turns"] if row["speaker_type"] == "assessee"}
    fragments = {row.value["id"]: row for row in indexed_rows(value, "fragments")}
    signals = {row.value["id"]: row for row in indexed_rows(value, "signals")}
    issues = LinkIssues()
    for link in prior.links:
        address, details = link.address, link.details()
        assessment = reviews.get(address)
        fragment, signal = fragments.get(address.fragment_id), signals.get(address.signal_id)
        fpath = f"fragments.{fragment.index if fragment else link.fragment.index}"
        spath = f"signals.{signal.index if signal else link.signal.index}"
        turn, quote = details["turn_id"], link.fragment.value.get("quote")
        exact_quote = False
        if fragment is None:
            if assessment != "irrelevant":
                issues.add("M6_FRAGMENT_REPAIR_MISSING", f"{fpath}.id", **details)
        elif turn in turns:
            if fragment.value["turn_id"] != turn:
                issues.add("M6_FRAGMENT_REPAIR_TURN", f"{fpath}.turn_id", **details)
            if isinstance(quote, str) and quote:
                _, defect = quote_position(turns[turn], quote)
                exact_quote = defect is None
                actual = fragment.value["quote"]
                if (exact_quote and actual != quote) or (defect == "M6_FRAGMENT_QUOTE_AMBIGUOUS" and quote not in actual):
                    issues.add("M6_FRAGMENT_REPAIR_QUOTE", f"{fpath}.quote", **details)
        if assessment != "irrelevant":
            observation = link.signal.value.get("observation")
            if signal is None or signal.value["fragment_id"] != address.fragment_id:
                issues.add("M6_FRAGMENT_REPAIR_SIGNAL_MISSING", f"{spath}.fragment_id", **details)
            elif ((exact_quote or assessment == "unclear") and isinstance(observation, str)
                  and observation.strip() and signal.value["observation"] != observation):
                issues.add("M6_FRAGMENT_REPAIR_OBSERVATION_CHANGED", f"{spath}.observation", **details)
        if assessment is None and _relation(address) not in relations:
            issues.add("M6_FRAGMENT_REPAIR_EVIDENCE_MISSING", f"evidence.{link.evidence.index}.fragment_ids", **details)
    issues.raise_if_any()


def validate_link_repair(value: dict, notes: list[dict], prior: RepairBasis | None, material: dict) -> None:
    previous = {link.address: link for link in prior.links} if prior else {}
    relations = {_relation(link.address) for link in _links(value)}
    reviews = _valid_reviews(notes, previous, relations, material)
    if prior is None:
        return
    _validate_sources(value, prior, material, reviews, relations)
    validate_repaired_basis(value, prior.unlinked_citations)
    validate_verified_basis(value, prior.verified.evidence, reviewed=reviews)
    validate_verified_bundles(value, prior.verified, material, reviewed=reviews)


def address_validation_failures(issues: list[dict], candidate: object, prior: RepairBasis) -> list[dict]:
    """Record the actual pair when a retry fails before continuity can be evaluated."""
    current = _links(candidate)
    notes = dict(candidate_records(candidate, "repair_notes"))
    addressed = []
    for issue in issues:
        if "fragment_id" in issue:
            addressed.append(issue)
            continue
        field, _, tail = issue["path"].partition(".")
        position = tail.split(".")[0]
        if field == "repair_notes" and position.isdigit():
            note = notes.get(int(position), {})
            if all(isinstance(note.get(key), str) and note[key] for key in LinkAddress._fields):
                addressed.append({**issue, **{key: note[key] for key in LinkAddress._fields}})
                continue
        pairs = [link for link in current if link.at_path(issue["path"])]
        if not pairs:
            pairs = [link for link in prior.links if link.at_path(issue["path"])]
        addressed.extend(({**issue, **link.details()} for link in pairs) if pairs else [issue])
    return addressed
