from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TargetRequirement(Record):
    skill_id: str = Field(min_length=1)
    target_level: str | None = None


class TargetProfile(Record):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    requirements: list[TargetRequirement]


class CreateResultsRequest(Record):
    idempotency_key: str = Field(min_length=1, max_length=200)
    calculation_id: str
    synthetic_material_confirmed: Literal[True]


class CreateReportRequest(Record):
    idempotency_key: str = Field(min_length=1, max_length=200)
    results_revision_id: str
    audience: Literal["assessee", "customer", "methodology_qa"]
    target_profile: TargetProfile | None = None


class PrepareReportCorrectionRequest(Record):
    expected_report_id: str
    result_revision_id: str
    kind: Literal["explanation", "calculation"]
    incident_ref: str = Field(min_length=1, max_length=500)
    participant_reason: str = Field(min_length=1, max_length=1000)
    descriptive: dict


class PublishReportCorrectionRequest(Record):
    candidate_id: str
    expected_report_id: str
    idempotency_key: str = Field(min_length=1, max_length=200)
