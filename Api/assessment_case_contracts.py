"""Черновые файловые контракты M5; не включают подбор M7 или оценивание M6."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Text = Annotated[str, Field(min_length=1)]
Checksum = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
IndicatorID = Annotated[str, Field(pattern=r"^K[1-4]\.I\d{2}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def unique(values: list, label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


class Applicability(Contract):
    skill_id: Annotated[str, Field(pattern=r"^K[1-4]\.\d+$")]
    component_id: Annotated[str, Field(pattern=r"^K[1-4]\.C\d{2}$")]
    required: Literal[True] = True


class CaseDefinition(Contract):
    # Ровно 21 предметное поле паспорта. Статус хранится в пакете отдельно.
    case_id: Text
    title: Text
    case_type_ids: Annotated[list[Annotated[str, Field(pattern=r"^CT\d{2}$")]], Field(min_length=1)]
    ct_composition: Text
    format: Text
    applicable_base_roles: Annotated[list[Text], Field(min_length=1)]
    version: Text
    initial_situation: Text
    trigger: Text
    participant_position: Text
    actors: Text
    task: Text
    constraints: Text
    applicability: Annotated[list[Applicability], Field(min_length=1)]
    functional_result: Text
    invariant: Text
    dialogue: Text
    personalization_rules: Text
    difficulty_parameters: Text
    planned_minutes: Annotated[int, Field(gt=0)]
    invalidity_risks: Text

    @model_validator(mode="after")
    def check_lists(self):
        unique(self.case_type_ids, "CaseTypeID")
        unique(self.applicable_base_roles, "BaseRole")
        unique([x.component_id for x in self.applicability], "ComponentID")
        return self


class SourceRef(Contract):
    file: Text
    sheet: Text
    row: Annotated[int, Field(gt=0)]


class CandidateObservability(Contract):
    test_as_id: Text
    case_id: Text
    base_role: Text
    skill_id: Text
    component_id: Text
    indicator_id: IndicatorID | None
    candidate_indicator_ids: Annotated[list[IndicatorID], Field(min_length=1)]
    resolution: Literal["source_assigned", "pending_methodological_review"]
    required: Literal[True] = True
    conditions: Text
    branch: Text
    observable_action: Text
    loss_risk: Text
    source_indicator_value: Text
    source_qa_status: Text
    source: SourceRef

    @model_validator(mode="after")
    def check_resolution(self):
        unique(self.candidate_indicator_ids, "candidate IndicatorID")
        assigned = self.resolution == "source_assigned"
        if assigned != (self.indicator_id is not None):
            raise ValueError("Assigned and pending IndicatorID states disagree")
        if assigned and self.indicator_id not in self.candidate_indicator_ids:
            raise ValueError("Assigned IndicatorID is not a candidate")
        return self


class VersionRef(Contract):
    id: Text
    version: Text
    checksum: Checksum


class Observability(Contract):
    skill_id: Text
    component_id: Text
    indicator_id: IndicatorID
    required: bool
    conditions: Annotated[list[Text], Field(min_length=1)]
    branches: Annotated[list[Text], Field(min_length=1)]
    observable_action: Text
    loss_risk: Text
    qa_result: Literal["PASS", "FAIL", "NOT_RUN"]
    qa_basis: Text


class Substitution(Contract):
    slot: Text
    value: Text
    source_path: Text
    source_checksum: Checksum


class AssessmentSituation(Contract):
    """Контракт будущего снимка; наличие JSON не означает допуск или исполнение."""

    schema_version: Literal[1] = 1
    assessment_situation_id: Text
    case_ref: VersionRef
    profile_ref: VersionRef
    methodology_ref: VersionRef
    base_role: Text
    substitutions: list[Substitution]
    presentation: Text
    conditions: Text
    scenario: Text
    planned_minutes: Annotated[int, Field(gt=0)]
    observability: Annotated[list[Observability], Field(min_length=1)]
    qa_result: Literal["PASS", "FAIL", "NOT_RUN"]
    qa_basis: Text

    @model_validator(mode="after")
    def check_observability(self):
        unique([x.indicator_id for x in self.observability], "AS IndicatorID")
        unique([x.slot for x in self.substitutions], "substitution slot")
        if self.qa_result == "PASS" and any(
            x.required and x.qa_result != "PASS" for x in self.observability
        ):
            raise ValueError("Required Observability must PASS before AS can PASS")
        return self


class VerificationCheck(Contract):
    code: Text
    result: Literal["PASS", "FAIL", "NOT_RUN"]
    expected: Text
    actual: Text
    artifact_refs: list[Text]


class VerificationReport(Contract):
    schema_version: Literal[1] = 1
    verification_run_id: Text
    mode: Literal["static_package", "runtime_stub", "runtime_llm"]
    package_checksum: Checksum
    checks: Annotated[list[VerificationCheck], Field(min_length=1)]
    runtime_execution: Literal["PASS", "FAIL", "NOT_RUN"]
    m6_execution: Literal["PASS", "FAIL", "NOT_RUN"]

    @model_validator(mode="after")
    def check_mode(self):
        unique([x.code for x in self.checks], "verification check")
        if self.mode == "static_package" and (
            self.runtime_execution != "NOT_RUN" or self.m6_execution != "NOT_RUN"
        ):
            raise ValueError("Static package verification cannot confirm runtime or M6")
        return self
