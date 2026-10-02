from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AdmissionDecision(Record):
    indicator_id: str = Field(min_length=1)
    included_revision_ids: list[str]
    numeric_admissible: bool
    interpretation_admissible: bool
    reason_code: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    conditions_refs: list[str]


class CreateAggregationRequest(Record):
    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_composition_checksum: str = Field(min_length=64, max_length=64)
    admission_mechanism_version: Literal["m6-admission-manual/1.0"]
    decisions: list[AdmissionDecision]
    synthetic_material_confirmed: Literal[True]
