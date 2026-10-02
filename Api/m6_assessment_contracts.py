from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Ref(Record):
    kind: Literal["turn", "event", "material", "evidence", "bundle"]
    id: str = Field(min_length=1)
    meaning: str = Field(min_length=1)


class ConfidenceBasis(Record):
    confirmed_features: list[str]
    alternatives_considered: list[str]
    limitations: list[str]
    reliability_protocol_ref: str | None = None


class Uncertainty(Record):
    missing_or_conflicting_feature: str = Field(min_length=1)
    impact: str = Field(min_length=1)
    clarification_needed: str = Field(min_length=1)
    resolution_information: list[str]
    requires_new_independent_action: bool


class TargetAssessment(Record):
    indicator_id: str = Field(min_length=1)
    m2_version: str = Field(min_length=1)
    status: Literal["INTERIM", "ASSESSED", "NO_ASSESSMENT", "TECHNICAL_FAILURE"]
    outcome: Literal["L0", "L1", "L2", "L3", "INSUFFICIENT_EVIDENCE"] | None = None
    descriptor_basis: str | None = None
    rationale: str = Field(min_length=1)
    refs: list[Ref]
    opportunity: Literal["PRESENT", "ABSENT", "UNKNOWN"]
    opportunity_basis: str = Field(min_length=1)
    uncertainty: Uncertainty | None = None
    contradictions: list[str]
    clarification_history: list[str]
    stop_reason: str | None = None
    confidence: ConfidenceBasis

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == "INTERIM":
            if self.outcome is not None:
                raise ValueError("M6_INTERIM_HAS_IA")
        elif self.status == "ASSESSED":
            if self.outcome is None:
                raise ValueError("M6_ASSESSMENT_OUTCOME_REQUIRED")
            if self.outcome == "L0" and self.opportunity != "PRESENT":
                raise ValueError("M6_L0_REQUIRES_OPPORTUNITY")
            if self.outcome == "INSUFFICIENT_EVIDENCE" and self.opportunity != "PRESENT":
                raise ValueError("M6_IE_REQUIRES_OPPORTUNITY")
        elif self.status == "NO_ASSESSMENT":
            if self.outcome is not None or self.opportunity != "ABSENT":
                raise ValueError("M6_NO_IA_REQUIRES_NO_OPPORTUNITY")
        elif self.outcome is not None:
            raise ValueError("M6_TECHNICAL_FAILURE_HAS_PERSON_RESULT")
        if self.outcome in {"L0", "L1", "L2", "L3"} and not self.descriptor_basis:
            raise ValueError("M6_DESCRIPTOR_BASIS_REQUIRED")
        return self


class AssessmentOutput(Record):
    schema_version: Literal[1]
    mode: Literal["interim", "final"]
    targets: list[TargetAssessment]


def validate_assessment(value: dict, assessment_input: dict) -> dict:
    output = AssessmentOutput.model_validate(value)
    if output.mode != assessment_input["mode"]:
        raise ValueError("M6_MODE_INVALID")
    material = assessment_input["material"]
    target_map = {x["indicator_id"]: x for x in material["indicator_targets"]}
    criteria = {x["id"]: x for x in material["criteria"]}
    if len(output.targets) != len(target_map) or {x.indicator_id for x in output.targets} != set(target_map):
        raise ValueError("TARGET_SET_MISMATCH")
    analysis = assessment_input["evidence_analysis"]
    ids = {
        "turn": {x["turn_id"] for x in material["turns"]},
        "event": {x["event_id"] for x in material["events"]},
        "material": {x["material_id"] for x in material["materials"]},
        "evidence": {x["id"] for x in analysis["evidence"]},
        "bundle": {x["indicator_id"] for x in analysis["bundles"]},
    }
    bundle_map = {x["indicator_id"]: x for x in analysis["bundles"]}
    for item in output.targets:
        target = target_map[item.indicator_id]
        if item.m2_version != target["m2_version"] or item.indicator_id not in criteria:
            raise ValueError("TARGET_SET_MISMATCH")
        if assessment_input["mode"] == "interim" and item.status != "INTERIM":
            raise ValueError("M6_INTERIM_HAS_IA")
        if assessment_input["mode"] == "final" and item.status == "INTERIM":
            raise ValueError("M6_FINAL_INCOMPLETE")
        for ref in item.refs:
            if ref.id not in ids[ref.kind]:
                raise ValueError("M6_ASSESSMENT_REFERENCE")
        bundle = bundle_map[item.indicator_id]
        own_evidence = set(bundle["evidence_ids"])
        if any(ref.kind == "evidence" and ref.id not in own_evidence for ref in item.refs):
            raise ValueError("M6_CROSS_TARGET_REFERENCE")
        if item.outcome == "INSUFFICIENT_EVIDENCE" and item.uncertainty is None:
            raise ValueError("M6_IE_UNCERTAINTY_REQUIRED")
        if item.status == "NO_ASSESSMENT" and item.uncertainty is None:
            raise ValueError("M6_NO_IA_REASON_REQUIRED")
        if item.status == "TECHNICAL_FAILURE" and item.uncertainty is None:
            raise ValueError("M6_TECHNICAL_FAILURE_REASON_REQUIRED")
        if item.outcome == "L0" and not any(ref.kind in {"turn", "event"} for ref in item.refs):
            raise ValueError("M6_L0_BOUNDARY_REQUIRED")
    return output.model_dump()


class CreateAssessmentRequest(Record):
    evidence_revision_id: str = Field(min_length=1)
    mechanism_ref: Literal["m6_indicator_assessment/1.0.0"]
    idempotency_key: str = Field(min_length=1, max_length=200)
    synthetic_material_confirmed: Literal[True]
