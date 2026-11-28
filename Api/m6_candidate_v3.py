"""Model-owned Evidence fields and scoped reviews for m6_evidence/1.0.3."""
from typing import Literal

from pydantic import Field

from Api.m6_contracts import ContextRef, EvidenceCandidate, Record, ValidationIssues, assemble_analysis, candidate_records


class EvidenceProposal(Record):
    id: str = Field(min_length=1)
    indicator_id: str
    m2_version: str
    type: Literal["Simple", "Composite"]
    interpretation: str = Field(min_length=1, pattern=r"\S")
    bs_ids: list[str] = Field(min_length=1)
    fragment_ids: list[str] = Field(min_length=1)
    context_refs: list[ContextRef]
    limitations: list[str]
    composite_basis: str | None = None
    ordered_turn_ids: list[str]


class LinkReview(Record):
    evidence_id: str = Field(min_length=1)
    indicator_id: str = Field(min_length=1)
    fragment_id: str = Field(min_length=1)
    signal_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    reason: Literal["irrelevant", "unclear"]
    explanation: str = Field(min_length=1, pattern=r"\S")


class EvidenceCandidateV3(EvidenceCandidate):
    schema_version: Literal[3]
    evidence: list[EvidenceProposal]
    repair_notes: list[LinkReview] = Field(default_factory=list)


def attach_criterion_attribution(value: dict, material: dict) -> dict:
    """Attach the four server-owned fields from the pinned criterion."""
    if not isinstance(value.get("evidence"), list):
        return value
    criteria = {item["id"]: item for item in material["criteria"]}
    evidence = list(value["evidence"])
    for index, row in candidate_records(value, "evidence"):
        indicator = row.get("indicator_id")
        criterion = criteria.get(indicator) if isinstance(indicator, str) else None
        if criterion is not None:
            evidence[index] = {**row, "attribution": {
                "function": criterion["function"], "product": criterion["product"],
                "evidence_pattern": criterion["evidence_pattern"], "boundaries": criterion["boundary"],
            }}
    return {**value, "evidence": evidence}


def assemble_reviewed_analysis(value: dict, material: dict) -> tuple[dict, list[dict]]:
    candidate = EvidenceCandidateV3.model_validate(value)
    targets = {item["indicator_id"] for item in material["indicator_targets"]}
    issues = ValidationIssues()
    for index, item in enumerate(candidate.evidence):
        if item.indicator_id not in targets:
            issues.add("TARGET_SET_MISMATCH", f"evidence.{index}.indicator_id")
    issues.raise_if_any()
    analysis = attach_criterion_attribution(candidate.model_dump(exclude={"repair_notes"}), material)
    return assemble_analysis({**analysis, "schema_version": 2}, material), [
        note.model_dump() for note in candidate.repair_notes
    ]
