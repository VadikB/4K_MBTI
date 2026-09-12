from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from Api.assessment_configuration import definition_checksum


EVALUATOR_CONTRACT_VERSION = 1
INDICATOR_EVALUATOR_CONTRACT_VERSION = 2


def validate_agent_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(runtime or {})
    mode = str(normalized.get("mode") or "").strip()
    if mode == "legacy_adapter":
        if set(normalized) != {"mode"}:
            raise ValueError("Legacy agent runtime supports only the mode field.")
        return {"mode": mode}
    if mode != "universal_llm":
        raise ValueError(f"Unsupported agent runtime mode: {mode!r}.")
    required = {
        "mode", "model_profile", "temperature", "max_attempts",
        "timeout_seconds", "max_output_tokens", "fallback",
    }
    if set(normalized) != required:
        raise ValueError("Universal LLM runtime fields must match the v1 runtime contract.")
    if str(normalized["model_profile"]) != "assessment_strict":
        raise ValueError("Unsupported universal LLM model profile.")
    temperature = float(normalized["temperature"])
    max_attempts = int(normalized["max_attempts"])
    timeout_seconds = int(normalized["timeout_seconds"])
    max_output_tokens = int(normalized["max_output_tokens"])
    if not 0 <= temperature <= 0.2:
        raise ValueError("Universal LLM temperature must be between 0 and 0.2.")
    if not 1 <= max_attempts <= 2:
        raise ValueError("Universal LLM max_attempts must be between 1 and 2.")
    if not 5 <= timeout_seconds <= 120:
        raise ValueError("Universal LLM timeout_seconds must be between 5 and 120.")
    if not 256 <= max_output_tokens <= 4096:
        raise ValueError("Universal LLM max_output_tokens must be between 256 and 4096.")
    if str(normalized["fallback"]) != "fail":
        raise ValueError("Universal LLM runtime supports only fallback=fail.")
    return {
        "mode": mode,
        "model_profile": "assessment_strict",
        "temperature": temperature,
        "max_attempts": max_attempts,
        "timeout_seconds": timeout_seconds,
        "max_output_tokens": max_output_tokens,
        "fallback": "fail",
    }


class CompetencyEvaluationInput(BaseModel):
    """Versioned orchestration input for one competency evaluator invocation.

    The contract carries both stable execution identity and all methodological
    material required by the evaluator. Persistence remains behind the legacy
    adapter during the baseline migration.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[1] = EVALUATOR_CONTRACT_VERSION
    session_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    methodology_code: str = Field(min_length=1)
    methodology_version: int = Field(gt=0)
    competency_code: str = Field(min_length=1)
    component_code: str = Field(pattern=r"^evaluation\.[a-z0-9_]+$")
    component_version: int = Field(gt=0)
    agent_definition: "AgentDefinitionInput"
    agent_prompt_config: "AgentPromptConfigInput"
    skills: list["SkillEvaluationInput"]


class AgentContractReferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    version: int = Field(gt=0)


class AgentDefinitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: int = Field(gt=0)
    checksum: str = Field(min_length=1)
    instruction_markdown: str = Field(min_length=1)
    input_contract: AgentContractReferenceInput
    output_contract: AgentContractReferenceInput
    executor: AgentContractReferenceInput
    runtime: dict[str, Any]


class AgentPromptProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_code: str | None = None
    agent_name: str | None = None
    competency_name: str | None = None
    purpose_prompt: str | None = None
    rationale_prompt: str | None = None
    evidence_prompt: str | None = None
    red_flag_prompt: str | None = None
    prompt_version: int | None = None


class AgentPromptRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_code: str | None = None
    rule_code: str
    rule_scope: str
    rule_text: str
    display_order: int


class AgentPromptConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: AgentPromptProfileInput
    rules: list[AgentPromptRuleInput]


class RubricLevelInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level_name: str
    knowledge_text: str
    skill_text: str
    behavior_text: str


class RequiredResponseBlockInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    block_code: str
    block_name: str


class MethodicalRedFlagInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    flag_code: str
    flag_name: str
    flag_description: str


class SkillEvidenceRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    related_response_block_code: str
    evidence_description: str
    expected_signal: str


class CaseEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_case_id: int = Field(gt=0)
    case_registry_id: int | None = None
    user_text: str
    expected_artifact_code: str
    expected_artifact: str
    answer_structure_hint: str
    constraints_text: str
    clarifying_questions: str
    required_response_blocks: list[RequiredResponseBlockInput]
    methodical_red_flags: list[MethodicalRedFlagInput]
    skill_evidence: list[SkillEvidenceRuleInput]
    is_refusal_case: bool


class SkillEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: int = Field(gt=0)
    competency_skill_id: int | None = None
    skill_code: str | None = None
    skill_name: str
    competency_name: str
    rubric: dict[str, RubricLevelInput]
    cases: list[CaseEvidenceInput]


class SkillEvaluationOutput(BaseModel):
    """Normalized form of the existing ``SkillEvaluation`` result."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)

    skill_id: int = Field(gt=0)
    competency_skill_id: int | None = None
    skill_code: str | None = None
    skill_name: str
    competency_name: str
    level_code: Literal["L1", "L2", "L3", "N/A"]
    level_name: str
    rubric_match_scores: dict[str, int]
    structural_elements: dict[str, bool]
    red_flags: list[str]
    found_evidence: list[dict[str, str]]
    detected_required_blocks: list[str]
    missing_required_blocks: list[str]
    block_coverage_percent: int | None = Field(default=None, ge=0, le=100)
    rationale: str
    evidence_excerpt: str
    source_session_case_ids: list[int]


class CaseSkillAnalysisOutput(BaseModel):
    """Validated case-level evidence analysis persisted alongside skill results."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)

    session_case_id: int = Field(gt=0)
    case_registry_id: int | None = None
    skill_id: int = Field(gt=0)
    competency_name: str
    expected_artifact_code: str | None = None
    expected_artifact_name: str | None = None
    detected_artifact_parts: list[str]
    missing_artifact_parts: list[str]
    artifact_compliance_percent: int | None = Field(default=None, ge=0, le=100)
    structural_elements: dict[str, bool]
    detected_required_blocks: list[str]
    missing_required_blocks: list[str]
    block_coverage_percent: int | None = Field(default=None, ge=0, le=100)
    red_flags: list[str]
    found_evidence: list[dict[str, str]]
    detected_signals: list[str]
    evidence_excerpt: str
    source_message_count: int = Field(ge=0)


class CompetencyEvaluationOutput(BaseModel):
    """Validated result returned to the scenario runtime by an evaluator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[1] = EVALUATOR_CONTRACT_VERSION
    competency_code: str = Field(min_length=1)
    component_code: str = Field(pattern=r"^evaluation\.[a-z0-9_]+$")
    component_version: int = Field(gt=0)
    status: Literal["evaluated", "no_assessments"]
    assessments: list[SkillEvaluationOutput]
    case_analyses: list[CaseSkillAnalysisOutput]


class IndicatorLevelDescriptorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    descriptor: str = Field(min_length=1)


class IndicatorRedFlagDefinitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    description: str = Field(min_length=1)


class IndicatorEvidenceRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    related_response_block_code: str
    evidence_description: str = Field(min_length=1)
    expected_signal: str


class IndicatorCaseEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_case_id: int = Field(gt=0)
    case_registry_id: int | None = None
    user_text: str
    expected_artifact_code: str
    expected_artifact: str
    answer_structure_hint: str
    constraints_text: str
    required_response_blocks: list[RequiredResponseBlockInput]
    methodical_red_flags: list[MethodicalRedFlagInput]
    indicator_evidence: list[IndicatorEvidenceRuleInput]
    is_refusal_case: bool


class IndicatorEvaluationMaterialInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator_code: str = Field(pattern=r"^K[1-4]\.I\d{2}$")
    indicator_name: str = Field(min_length=1)
    function: str = Field(min_length=1)
    product: str = Field(min_length=1)
    levels: dict[Literal["L0", "L1", "L2", "L3"], IndicatorLevelDescriptorInput]
    boundary: str = Field(min_length=1)
    evidence_pattern: str = Field(min_length=1)
    red_flags: list[IndicatorRedFlagDefinitionInput]
    cases: list[IndicatorCaseEvidenceInput]

    @model_validator(mode="after")
    def require_all_levels(self) -> "IndicatorEvaluationMaterialInput":
        if set(self.levels) != {"L0", "L1", "L2", "L3"}:
            raise ValueError("Indicator material must define exactly L0-L3.")
        return self


class ComponentEvaluationMaterialInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component_code: str = Field(pattern=r"^K[1-4]\.C\d{2}$")
    component_name: str = Field(min_length=1)
    indicators: list[IndicatorEvaluationMaterialInput] = Field(min_length=1)


class SkillIndicatorEvaluationMaterialInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_code: str = Field(pattern=r"^K[1-4]\.\d+$")
    skill_name: str = Field(min_length=1)
    components: list[ComponentEvaluationMaterialInput] = Field(min_length=1)


class CompetencyIndicatorEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[2] = INDICATOR_EVALUATOR_CONTRACT_VERSION
    session_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    methodology_code: str = Field(min_length=1)
    methodology_version_id: int = Field(gt=0)
    methodology_version: str = Field(min_length=1)
    competency_code: str = Field(pattern=r"^K[1-4]$")
    component_code: str = Field(pattern=r"^evaluation\.[a-z0-9_]+$")
    component_version: int = Field(gt=0)
    agent_definition: AgentDefinitionInput
    skills: list[SkillIndicatorEvaluationMaterialInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_hierarchy(self) -> "CompetencyIndicatorEvaluationInput":
        runtime = validate_agent_runtime(self.agent_definition.runtime)
        if runtime["mode"] != "universal_llm":
            raise ValueError("Indicator evaluator requires universal_llm runtime.")
        if (self.agent_definition.input_contract.code, self.agent_definition.input_contract.version) != (
            "competency_evaluation_input", INDICATOR_EVALUATOR_CONTRACT_VERSION,
        ):
            raise ValueError("Indicator evaluator input contract must use version 2.")
        if (self.agent_definition.output_contract.code, self.agent_definition.output_contract.version) != (
            "competency_evaluation_output", INDICATOR_EVALUATOR_CONTRACT_VERSION,
        ):
            raise ValueError("Indicator evaluator output contract must use version 2.")
        if (self.agent_definition.executor.code, self.agent_definition.executor.version) != (
            self.component_code, self.component_version,
        ):
            raise ValueError("Indicator evaluator executor does not match input component.")
        seen: set[str] = set()
        for skill in self.skills:
            if not skill.skill_code.startswith(self.competency_code + "."):
                raise ValueError("Skill does not belong to input competency.")
            if skill.skill_code in seen:
                raise ValueError("Duplicate methodology identifier in evaluator input.")
            seen.add(skill.skill_code)
            for component in skill.components:
                if not component.component_code.startswith(self.competency_code + ".C"):
                    raise ValueError("Component does not belong to input competency.")
                if component.component_code in seen:
                    raise ValueError("Duplicate methodology identifier in evaluator input.")
                seen.add(component.component_code)
                for indicator in component.indicators:
                    if not indicator.indicator_code.startswith(self.competency_code + ".I"):
                        raise ValueError("Indicator does not belong to input competency.")
                    if indicator.indicator_code in seen:
                        raise ValueError("Duplicate methodology identifier in evaluator input.")
                    seen.add(indicator.indicator_code)
                    flag_codes = [item.code for item in indicator.red_flags]
                    if len(flag_codes) != len(set(flag_codes)):
                        raise ValueError("Duplicate red flag code in evaluator input.")
        return self


class IndicatorEvidenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_case_id: int = Field(gt=0)
    observation: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)


class IndicatorAssessmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    indicator_code: str = Field(pattern=r"^K[1-4]\.I\d{2}$")
    evidence_state: Literal["observed", "insufficient_evidence", "not_assessed"]
    level_code: Literal["L0", "L1", "L2", "L3"] | None = None
    evidence: list[IndicatorEvidenceOutput]
    red_flag_codes: list[str]
    rationale: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_evidence_state(self) -> "IndicatorAssessmentOutput":
        if self.evidence_state == "observed":
            if self.level_code is None or not self.evidence:
                raise ValueError("Observed indicator requires level_code and evidence.")
        elif self.level_code is not None or self.evidence:
            raise ValueError("Unobserved indicator cannot have level_code or evidence.")
        return self


class CompetencyIndicatorEvaluationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal[2] = INDICATOR_EVALUATOR_CONTRACT_VERSION
    competency_code: str = Field(pattern=r"^K[1-4]$")
    component_code: str = Field(pattern=r"^evaluation\.[a-z0-9_]+$")
    component_version: int = Field(gt=0)
    status: Literal["evaluated", "no_assessments"]
    indicator_assessments: list[IndicatorAssessmentOutput]

    @model_validator(mode="after")
    def validate_status(self) -> "CompetencyIndicatorEvaluationOutput":
        if (self.status == "evaluated") != bool(self.indicator_assessments):
            raise ValueError("Evaluator output status does not match indicator assessments.")
        return self


class LegacyCompetencyAgent(Protocol):
    def evaluate_session(
        self,
        *,
        connection: Any,
        session_id: int,
        user_id: int,
    ) -> list[Any]: ...


class ContractAwareLegacyCompetencyAgent(LegacyCompetencyAgent, Protocol):
    def load_evaluation_materials(
        self,
        *,
        connection: Any,
        session_id: int,
        prompt_snapshot: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]: ...

    def evaluate_contract(
        self,
        *,
        connection: Any,
        input_data: CompetencyEvaluationInput,
    ) -> Any: ...


class CompetencyEvaluationInputBuilder:
    def resolve_agent_definition(
        self,
        *,
        snapshot: dict[str, Any],
        competency: dict[str, Any],
        component_code: str,
        component_version: int,
    ) -> dict[str, Any]:
        reference = competency.get("agent_definition")
        reference = dict(reference) if isinstance(reference, dict) else {}
        definition_code = str(reference.get("code") or component_code.removeprefix("evaluation.")).strip()
        requested_version = int(reference.get("version") or 0)
        bundle = dict((snapshot.get("prompts") or {}).get("agent_definitions") or {})
        frozen = bundle.get(definition_code)
        if not isinstance(frozen, dict):
            raise ValueError(f"Frozen agent definition is missing: {definition_code}.")
        definition = dict(frozen.get("definition") or {})
        version = int(frozen.get("version") or 0)
        if requested_version and version != requested_version:
            raise ValueError(f"Frozen agent definition version mismatch: {definition_code} v{version}.")
        checksum = str(frozen.get("checksum") or "")
        if checksum != definition_checksum(definition):
            raise ValueError(f"Frozen agent definition checksum mismatch: {definition_code} v{version}.")
        input_contract = dict(definition.get("input_contract") or {})
        output_contract = dict(definition.get("output_contract") or {})
        executor = dict(definition.get("executor") or {})
        if (input_contract.get("code"), int(input_contract.get("version") or 0)) != (
            "competency_evaluation_input", EVALUATOR_CONTRACT_VERSION,
        ):
            raise ValueError(f"Unsupported agent input contract: {definition_code} v{version}.")
        if (output_contract.get("code"), int(output_contract.get("version") or 0)) != (
            "competency_evaluation_output", EVALUATOR_CONTRACT_VERSION,
        ):
            raise ValueError(f"Unsupported agent output contract: {definition_code} v{version}.")
        if (executor.get("code"), int(executor.get("version") or 0)) != (component_code, component_version):
            raise ValueError(f"Agent executor mismatch: {definition_code} v{version}.")
        runtime = validate_agent_runtime(dict(definition.get("runtime") or {}))
        return {
            "id": frozen.get("id"),
            "code": str(frozen.get("code") or definition_code),
            "name": str(frozen.get("name") or definition_code),
            "version": version,
            "checksum": checksum,
            "instruction_markdown": str(definition.get("instruction_markdown") or "").strip(),
            "input_contract": input_contract,
            "output_contract": output_contract,
            "executor": executor,
            "runtime": runtime,
        }

    def build(
        self,
        *,
        snapshot: dict[str, Any],
        session_id: int,
        user_id: int,
        competency: dict[str, Any],
        connection: Any | None = None,
        agent: LegacyCompetencyAgent | None = None,
    ) -> CompetencyEvaluationInput:
        methodology = dict(snapshot.get("methodology") or {})
        component_code = str(competency.get("evaluator") or "").strip()
        competency_code = str(competency.get("code") or "").strip()
        component_version = int(competency.get("evaluator_version") or 0)
        agent_definition = self.resolve_agent_definition(
            snapshot=snapshot,
            competency=competency,
            component_code=component_code,
            component_version=component_version,
        )
        agent_prompt_config: dict[str, Any] = {"profile": {}, "rules": []}
        skills: list[dict[str, Any]] = []
        material_loader = getattr(agent, "load_evaluation_materials", None)
        if callable(material_loader):
            if connection is None:
                raise ValueError("Evaluator material loading requires a database connection.")
            agent_prompt_config, skills = material_loader(
                connection=connection,
                session_id=session_id,
                prompt_snapshot=snapshot,
            )
        return CompetencyEvaluationInput(
            session_id=session_id,
            user_id=user_id,
            methodology_code=str(methodology.get("code") or "").strip(),
            methodology_version=int(methodology.get("version") or 0),
            competency_code=competency_code,
            component_code=component_code,
            component_version=component_version,
            agent_definition=agent_definition,
            agent_prompt_config=agent_prompt_config,
            skills=skills,
        )


class LegacyCompetencyEvaluatorAdapter:
    """Expose an existing stateful evaluator through the contract boundary."""

    def __init__(self, agent: LegacyCompetencyAgent) -> None:
        self._agent = agent

    def evaluate(
        self,
        *,
        connection: Any,
        input_data: CompetencyEvaluationInput,
    ) -> CompetencyEvaluationOutput:
        contract_evaluator = getattr(self._agent, "evaluate_contract", None)
        if callable(contract_evaluator):
            raw_result = contract_evaluator(connection=connection, input_data=input_data)
            raw_assessments = getattr(raw_result, "assessments", None)
            raw_case_analyses = getattr(raw_result, "case_analyses", None)
            if not isinstance(raw_assessments, list) or not isinstance(raw_case_analyses, list):
                raise ValueError("Contract-aware competency evaluator returned an invalid calculation result.")
        else:
            raw_assessments = self._agent.evaluate_session(
                connection=connection,
                session_id=input_data.session_id,
                user_id=input_data.user_id,
            )
            raw_case_analyses = []
        if not isinstance(raw_assessments, list):
            raise ValueError("Legacy competency evaluator must return a list of assessments.")
        assessments = [SkillEvaluationOutput.model_validate(item) for item in raw_assessments]
        case_analyses = [CaseSkillAnalysisOutput.model_validate(item) for item in raw_case_analyses]
        return CompetencyEvaluationOutput(
            competency_code=input_data.competency_code,
            component_code=input_data.component_code,
            component_version=input_data.component_version,
            status="evaluated" if assessments else "no_assessments",
            assessments=assessments,
            case_analyses=case_analyses,
        )


competency_evaluation_input_builder = CompetencyEvaluationInputBuilder()
