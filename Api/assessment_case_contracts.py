"""Файловые контракты M5 v1.1, совместимые schema v2/v3."""
from __future__ import annotations
import re
from typing import Annotated, Any, Literal
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

class VersionRef(Contract):
    id: Text
    version: Text
    checksum: Checksum

class Substitution(Contract):
    slot: Text
    value: Text
    source_path: Text
    source_checksum: Checksum

class SourceRefV2(Contract):
    file: Text
    sheet: Text
    row: Annotated[int, Field(gt=0)]
    field: Text

class JsonSourceRefV3(Contract):
    file: Text
    sha256: Checksum
    pointer: Annotated[str, Field(pattern=r"^(/.*)?$")]

class IndicatorTargetV2(Contract):
    indicator_id: IndicatorID
    m2_version: Text
    skill_id: Annotated[str, Field(pattern=r"^K[1-4]\.\d+$")]
    component_id: Annotated[str, Field(pattern=r"^K[1-4]\.C\d{2}$")]
    observation_condition: Text
    scenario_locations: Annotated[list[Text], Field(min_length=1)]
    branch_condition: Text
    event_condition: Text
    observable_action: Text
    validity_risk: Text
    source: SourceRefV2

class CaseMaterialV2(Contract):
    material_id: Text
    code: Text
    title: Text
    internal_rule: Text
    participant_payload: str | None = None
    disclosure_condition: dict[str, Any]
    event_condition: dict[str, Any]
    reaction_rule: Text
    result_check: Text
    kind: Literal["data", "mandatory_update", "conditional_material", "internal_check", "model_rules", "model_check", "character_reaction", "mixed_source"]
    classification_status: Literal["structured", "source_unresolved"]
    source: SourceRefV2
    speaker_id: str | None = None

class ScenarioStepV2(Contract):
    step_id: Text
    code: Text
    order: Annotated[int, Field(gt=0)]
    title: Text
    rules: Text
    source: SourceRefV2

class CaseCharacterV2(Contract):
    character_id: Text
    order: Annotated[int, Field(gt=0)]
    name_and_role: Text
    public_position: Text
    closed_card: Text
    source: SourceRefV2

class CaseVersionV2(Contract):
    schema_version: Literal[2] = 2
    case_id: Text
    version: Text
    status: Literal["WORKING", "REVIEW", "FROZEN"]
    title: Text
    base_role: Text
    format: Text
    planned_min_minutes: Annotated[int, Field(gt=0)]
    planned_max_minutes: Annotated[int, Field(gt=0)]
    passport: dict[str, Any]
    passport_sources: dict[str, SourceRefV2]
    case_type_ids: Annotated[list[Annotated[str, Field(pattern=r"^CT\d{2}$")]], Field(min_length=1)]
    applicability: Annotated[list[Applicability], Field(min_length=1)]
    indicator_targets: Annotated[list[IndicatorTargetV2], Field(min_length=1)]
    characters: Annotated[list[CaseCharacterV2], Field(min_length=1)]
    materials: Annotated[list[CaseMaterialV2], Field(min_length=1)]
    scenario: Annotated[list[ScenarioStepV2], Field(min_length=1)]
    unresolved_decisions: list[Text] = []

    @model_validator(mode="after")
    def check_v2(self):
        unique(self.case_type_ids, "CaseTypeID")
        unique([x.indicator_id for x in self.indicator_targets], "Case IndicatorID")
        unique([x.character_id for x in self.characters], "CharacterID")
        unique([x.material_id for x in self.materials], "DataID")
        unique([x.step_id for x in self.scenario], "StepID")
        if self.planned_min_minutes > self.planned_max_minutes:
            raise ValueError("Planned time range is reversed")
        components = {(x.skill_id, x.component_id) for x in self.applicability}
        if any((x.skill_id, x.component_id) not in components for x in self.indicator_targets):
            raise ValueError("Indicator target is outside Applicability")
        passport_ids = self.passport.get("IndicatorIDs", "")
        if isinstance(passport_ids, str):
            passport_ids = re.findall(r"K[1-4]\.I\d{2}", passport_ids)
        if set(passport_ids) != {x.indicator_id for x in self.indicator_targets}:
            raise ValueError("Passport IndicatorIDs differ from exact targets")
        return self

class IndicatorTargetV3(Contract):
    indicator_id: IndicatorID
    m2_version: Text
    skill_id: Annotated[str, Field(pattern=r"^K[1-4]\.\d+$")]
    component_id: Annotated[str, Field(pattern=r"^K[1-4]\.C\d{2}$")]
    observation_condition: Text
    scenario_locations: list[Text]
    branch_condition: Text
    event_condition: Text
    observable_action: Text
    validity_risk: Text
    source: JsonSourceRefV3

class CaseCharacterV3(Contract):
    character_id: Text
    order: Annotated[int, Field(gt=0)]
    content: dict[str, Any]
    source: JsonSourceRefV3

class CaseMaterialV3(Contract):
    material_id: Text
    order: Annotated[int, Field(gt=0)]
    participant_visible_initially: bool
    content: dict[str, Any]
    source: JsonSourceRefV3

class ScenarioStepV3(Contract):
    step_id: Text
    order: Annotated[int, Field(gt=0)]
    content: dict[str, Any]
    source: JsonSourceRefV3

class ParticipantMaterialV3(Contract):
    material_id: Text
    title: Text
    text: Text
    source: JsonSourceRefV3

class SubstitutionTargetV3(Contract):
    slot: Literal["organization_name"]
    path: Text
    source_value: Text

class ParticipantPresentationV3(Contract):
    assessment_situation_id: Text
    version: Text
    source: JsonSourceRefV3
    title: Text
    introduction: Text
    initial_situation: Text
    trigger: Text
    assessee_position: Text
    participants_and_positions: Text
    assessee_task: Text
    conditions_and_constraints: Text
    initial_materials: list[ParticipantMaterialV3]
    substitution_targets: list[SubstitutionTargetV3] = Field(default_factory=list)

class CaseVersionV3(Contract):
    """JSON-native author package; original author objects remain immutable snapshots."""
    schema_version: Literal[3] = 3
    case_id: Annotated[str, Field(pattern=r"^CASE\.SPEC\.\d{2}$")]
    version: Text
    status: Literal["WORKING", "REVIEW", "FROZEN"]
    title: Text
    base_role: Text
    format: Text
    planned_min_minutes: Annotated[int, Field(gt=0)]
    planned_max_minutes: Annotated[int, Field(gt=0)]
    passport: dict[str, Any]
    passport_sources: dict[str, JsonSourceRefV3]
    case_type_ids: Annotated[list[Annotated[str, Field(pattern=r"^CT\d{2}$")]], Field(min_length=1)]
    applicability: Annotated[list[Applicability], Field(min_length=1)]
    indicator_targets: Annotated[list[IndicatorTargetV3], Field(min_length=1)]
    characters: list[CaseCharacterV3]
    materials: Annotated[list[CaseMaterialV3], Field(min_length=1)]
    scenario: Annotated[list[ScenarioStepV3], Field(min_length=1)]
    participant_presentation: ParticipantPresentationV3
    author_case: dict[str, Any]
    author_assessment_situation: dict[str, Any]
    author_case_source: JsonSourceRefV3
    author_as_source: JsonSourceRefV3
    unresolved_decisions: list[Text] = []

    @model_validator(mode="after")
    def check_v3(self):
        unique(self.case_type_ids, "CaseTypeID")
        unique([x.indicator_id for x in self.indicator_targets], "Case IndicatorID")
        unique([x.character_id for x in self.characters], "CharacterID")
        unique([x.material_id for x in self.materials], "MaterialID")
        unique([x.step_id for x in self.scenario], "StepID")
        if self.planned_min_minutes > self.planned_max_minutes:
            raise ValueError("Planned time range is reversed")
        components = {(x.skill_id, x.component_id) for x in self.applicability}
        if any((x.skill_id, x.component_id) not in components for x in self.indicator_targets):
            raise ValueError("Indicator target is outside Applicability")
        return self

def validate_case_version(value: dict[str, Any]) -> CaseVersionV2 | CaseVersionV3:
    schema_version = value.get("schema_version")
    if schema_version == 2:
        return CaseVersionV2.model_validate(value)
    if schema_version == 3:
        return CaseVersionV3.model_validate(value)
    raise ValueError(f"Unsupported M5 Case schema_version: {schema_version!r}")

class QAEvidenceV2(Contract):
    scope: Literal["case_format", "case_dialogue", "assessment_situation"]
    result: Literal["PASS", "FAIL", "NOT_RUN"]
    artifact_ref: Text
    checksum: Checksum

class AdmissionDecisionV2(Contract):
    admitted: bool
    code: Literal["ADMITTED", "CASE_NOT_ADMITTED", "AS_NOT_ADMITTED"]
    reasons: list[Text]

class AssessmentSituationV2(Contract):
    schema_version: Literal[2] = 2
    assessment_situation_id: Text
    cycle_ref: VersionRef
    session_ref: VersionRef
    case_ref: VersionRef
    profile_ref: VersionRef
    methodology_refs: Annotated[list[VersionRef], Field(min_length=1)]
    base_role: Text
    substitutions: list[Substitution]
    participant_payload: dict[str, Any]
    execution_payload_ref: VersionRef
    planned_minutes: Annotated[int, Field(gt=0)]
    indicator_targets: Annotated[list[IndicatorTargetV2 | IndicatorTargetV3], Field(min_length=1)]
    qa_evidence: list[QAEvidenceV2]
    admission: AdmissionDecisionV2

    @model_validator(mode="after")
    def check_v2_as(self):
        unique([x.indicator_id for x in self.indicator_targets], "AS IndicatorID")
        unique([x.slot for x in self.substitutions], "substitution slot")
        if self.admission.admitted != (self.admission.code == "ADMITTED"):
            raise ValueError("Admission flag and code disagree")
        return self

class C34ExecutionEnvelope(Contract):
    schema_version: Literal[1] = 1
    assessment_situation_ref: VersionRef
    cycle_ref: VersionRef
    session_ref: VersionRef
    execution_payload_ref: VersionRef
    participant_payload_checksum: Checksum
    indicator_ids: Annotated[list[IndicatorID], Field(min_length=1)]
    admitted: Literal[True]

    @model_validator(mode="after")
    def check_indicators(self):
        unique(self.indicator_ids, "C-34 IndicatorID")
        return self
