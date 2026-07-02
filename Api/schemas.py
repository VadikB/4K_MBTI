from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None = None
    email: str | None = None
    created_at: datetime
    role_id: int | None
    job_description: str | None
    raw_position: str | None = None
    raw_duties: str | None
    normalized_duties: str | None = None
    role_selected: str | None = None
    role_selected_code: str | None = None
    role_confidence: float | None = None
    role_rationale: str | None = None
    role_consistency_status: str | None = None
    role_consistency_comment: str | None = None
    active_profile_id: int | None = None
    phone: str | None = None
    telegram: str | None = None
    personal_data_consent_accepted_at: datetime | None = None
    personal_data_consent_version: int | None = None
    company_industry: str | None = None
    company_context: str | None = None
    profile_metadata: dict | None = None
    raw_input: dict | None = None
    normalized_input: dict | None = None
    role_interpretation: dict | None = None
    user_work_context: dict | None = None
    role_limits: dict | None = None
    role_vocabulary: dict | None = None
    domain_profile: dict | None = None
    role_skill_profile: dict | None = None
    adaptation_rules_for_cases: dict | None = None
    user_domain: str | None = None
    user_processes: list[str] | None = None
    user_tasks: list[str] | None = None
    user_stakeholders: list[str] | None = None
    user_risks: list[str] | None = None
    user_constraints: list[str] | None = None
    user_artifacts: list[str] | None = None
    user_systems: list[str] | None = None
    user_success_metrics: list[str] | None = None
    data_quality_notes: list[str] | None = None
    domain_resolution_status: str | None = None
    domain_confidence: float | None = None
    profile_quality: dict | None = None
    profile_build_instruction_code: str | None = None
    profile_build_summary: str | None = None
    profile_build_trace: dict | None = None
    avatar_data_url: str | None = None


class CheckOrCreateUserRequest(BaseModel):
    phone: str
    name: str | None = None
    surname: str | None = None

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: object) -> str:
        if value is None:
            return ""
        digits = "".join(symbol for symbol in str(value) if symbol.isdigit())
        return digits

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not value:
            raise ValueError("Введите номер телефона")
        if len(value) < 10:
            raise ValueError("Введите телефон в полном формате")
        return value


class AuthEmailRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = str(value or "").strip().lower()
        if not cleaned or "@" not in cleaned:
            raise ValueError("Введите корректный email.")
        local, _, domain = cleaned.partition("@")
        if not local or not domain or "." not in domain:
            raise ValueError("Введите корректный email.")
        return cleaned


class AuthEmailRequestResponse(BaseModel):
    ok: bool = True
    message: str
    email: str
    expires_in_seconds: int
    dev_magic_token: str | None = None


class AuthEmailVerifyRequest(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("Введите код или вставьте ссылку для входа.")
        return cleaned


class AgentReply(BaseModel):
    session_id: str
    message: str
    stage: str
    completed: bool
    blocked: bool = False
    consent_title: str | None = None
    consent_text: str | None = None
    action_options: list[dict[str, str]] | None = None
    user: UserResponse | None = None
    detected_role_id: int | None = None
    detected_role_code: str | None = None
    detected_role_name: str | None = None
    detected_role_confidence: float | None = None
    detected_role_rationale: str | None = None
    assessment_session_code: str | None = None
    assessment_case_title: str | None = None
    assessment_case_number: int | None = None
    assessment_total_cases: int | None = None
    role_options: list[dict[str, str | int]] | None = None


class AssessmentCard(BaseModel):
    code: str
    title: str
    description: str
    progress_percent: int
    completed_cases: int
    total_cases: int
    status_label: str
    button_label: str


class AvailableAssessment(BaseModel):
    code: str
    title: str
    description: str
    duration_minutes: int
    status: str


class AssessmentReport(BaseModel):
    title: str
    summary: str
    badge: str
    format_label: str
    sequence_number: int | None = None
    report_at: datetime | None = None
    expert_comment: str | None = None


class AdminMetricCard(BaseModel):
    label: str
    value: str
    delta: str | None = None


class AdminInsightCard(BaseModel):
    title: str
    description: str


class PromptLabPromptVersion(BaseModel):
    id: int
    name: str
    prompt_text: str
    created_by: str | None = None
    created_at: datetime


class PromptLabUserOption(BaseModel):
    id: int
    full_name: str | None = None
    phone: str | None = None
    role_id: int | None = None
    role_name: str | None = None
    position: str | None = None
    duties: str | None = None
    company_industry: str | None = None
    user_profile: dict | None = None


class PromptLabCaseOption(BaseModel):
    case_id_code: str
    title: str
    type_code: str | None = None
    interactivity_mode: str | None = None
    is_dialog_case: bool = False
    role_names: list[str] = []


class PromptLabCaseRunSummary(BaseModel):
    id: int
    prompt_id: int | None = None
    prompt_name: str | None = None
    user_id: int
    user_name: str | None = None
    case_id_code: str
    case_title: str
    created_by: str | None = None
    created_at: datetime


class PromptLabDashboard(BaseModel):
    prompts: list[PromptLabPromptVersion]
    users: list[PromptLabUserOption]
    cases: list[PromptLabCaseOption]
    role_options: list[dict[str, str | int]]
    recent_runs: list[PromptLabCaseRunSummary]
    production_prompt_text: str | None = None
    production_prompt_name: str | None = None
    production_instruction_code: str | None = None
    production_instruction_version: int | None = None
    interviewer_prompt_text: str | None = None
    interviewer_prompt_name: str | None = None
    interviewer_prompt_code: str | None = None
    interviewer_prompt_version: int | None = None


class PromptLabPromptCreateRequest(BaseModel):
    name: str
    prompt_text: str


class PromptLabCaseRunRequest(BaseModel):
    user_id: int
    case_id_code: str | None = None
    case_id_codes: list[str] = Field(default_factory=list)
    prompt_source: str = "custom"
    prompt_id: int | None = None
    prompt_name: str | None = None
    prompt_text: str | None = None
    full_name: str | None = None
    role_id: int | None = None
    position: str | None = None
    duties: str | None = None
    company_industry: str | None = None
    user_profile: dict | None = None


class PromptLabCaseRunResponse(BaseModel):
    id: int
    prompt: PromptLabPromptVersion | None = None
    user: dict
    case: dict
    total_cases: int | None = None
    case_items: list[dict] = Field(default_factory=list)
    base_context: str
    base_task: str
    case_specificity: dict
    personalization_map: dict
    personalized_context: str
    personalized_task: str
    system_personalized_context: str | None = None
    system_personalized_task: str | None = None
    opening_message: str
    system_prompt: str
    methodical_context: dict
    case_quality: dict = Field(default_factory=dict)
    created_at: datetime


class PromptLabSystemCasePreviewResponse(BaseModel):
    user: dict
    case: dict
    base_context: str
    base_task: str
    system_personalized_context: str | None = None
    system_personalized_task: str | None = None


class PromptLabDialoguePreviewRequest(BaseModel):
    user_id: int
    case_id_code: str
    case_generation_prompt_text: str | None = None


class PromptLabDialoguePreviewResponse(BaseModel):
    user: dict
    case: dict
    personalized_context: str
    personalized_task: str
    case_generation_prompt_text: str | None = None
    opening_message: str
    counterpart_opening_message: str | None = None
    is_dialog_case: bool = False
    system_prompt: str
    interviewer_prompt_text: str | None = None
    interviewer_prompt_name: str | None = None
    interviewer_prompt_code: str | None = None
    interviewer_prompt_version: int | None = None
    methodical_context: dict = Field(default_factory=dict)


class PromptLabDialogueTurnRequest(BaseModel):
    system_prompt: str
    case_title: str
    case_skills: list[str] = Field(default_factory=list)
    methodical_context: dict = Field(default_factory=dict)
    dialogue: list[dict] = Field(default_factory=list)
    interviewer_prompt_text: str | None = None
    user_message: str


class PromptLabDialogueTurnResponse(BaseModel):
    assistant_message: str
    case_completed: bool = False
    stop_reason: str | None = None


class AdminMethodologyBranchItem(BaseModel):
    role_name: str
    case_count: int
    ready_case_count: int
    skill_coverage_percent: int
    competency_coverage_percent: int


class AdminMethodologyCoverageRow(BaseModel):
    competency_name: str
    linear_value: int
    manager_value: int
    leader_value: int


class AdminMethodologySkillGapItem(BaseModel):
    role_name: str
    skill_name: str
    competency_name: str
    ready_case_count: int
    severity: str


class AdminMethodologySinglePointSkillItem(BaseModel):
    skill_name: str
    competency_name: str
    role_names: list[str]
    type_codes: list[str]
    ready_case_count: int


class AdminMethodologyCaseQualityItem(BaseModel):
    case_id_code: str
    title: str
    type_code: str
    assessments_count: int
    avg_red_flag_count: float
    avg_missing_blocks_count: float
    avg_block_coverage_percent: float | None = None
    low_level_rate_percent: int
    issue_label: str


class AdminMethodologyPassportItem(BaseModel):
    type_code: str
    type_name: str
    artifact_name: str
    status: str
    ready_cases_count: int
    required_blocks_count: int
    red_flags_count: int
    roles: list[str]
    interactivity_mode: str | None = None
    recommended_answer_length: str | None = None
    selection_tags: list[str] = []


class AdminMethodologyCaseItem(BaseModel):
    case_id_code: str
    title: str
    type_code: str
    status: str
    difficulty_level: str
    estimated_time_min: int | None = None
    roles: list[str]
    skills: list[str]
    stakeholders_text: str | None = None
    interactivity_mode: str | None = None
    recommended_answer_length: str | None = None
    expected_artifact: str | None = None
    selection_tags: list[str] = []
    qa_ready: bool
    passed_checks: int
    total_checks: int
    qa_blockers: list[str]


class AdminMethodologyChecklistItem(BaseModel):
    code: str
    name: str
    passed: bool
    comment: str | None = None


class AdminMethodologySkillSignalItem(BaseModel):
    skill_name: str
    competency_name: str
    related_response_block_code: str | None = None
    evidence_description: str
    expected_signal: str | None = None


class AdminMethodologyRoleOption(BaseModel):
    id: int
    code: str
    name: str


class AdminMethodologySkillOption(BaseModel):
    id: int
    skill_code: str
    skill_name: str
    competency_name: str | None = None


class AdminMethodologyPersonalizationOption(BaseModel):
    field_code: str
    field_name: str
    description: str | None = None
    source_type: str
    is_required: bool = False


class AdminMethodologyPersonalizationValueItem(BaseModel):
    field_code: str
    field_label: str
    field_value_template: str | None = None
    description: str | None = None
    source_type: str
    is_required: bool = False
    display_order: int = 1


class AdminMethodologyChangeLogItem(BaseModel):
    changed_at: datetime
    changed_by: str
    entity_scope: str
    action: str
    summary: str


class AdminMethodologyCaseDetailResponse(BaseModel):
    case_id_code: str
    title: str
    case_registry_version: int
    case_text_version: int
    case_type_passport_version: int
    required_blocks_version: int
    red_flags_version: int
    skill_evidence_version: int
    difficulty_modifiers_version: int
    personalization_fields_version: int
    type_code: str
    type_name: str
    artifact_name: str
    artifact_description: str | None = None
    stakeholders_text: str | None = None
    interactivity_mode: str | None = None
    recommended_answer_length: str | None = None
    selection_tags: list[str] = []
    role_personalization_rules: str | None = None
    format_control_rules: str | None = None
    scoring_aggregation_rules: str | None = None
    bad_case_risks: str | None = None
    generation_notes: str | None = None
    passport_status: str
    case_status: str
    case_text_status: str
    status: str
    difficulty_level: str
    estimated_time_min: int | None = None
    roles: list[str]
    skills: list[str]
    intro_context: str | None = None
    facts_data: str | None = None
    participants_roles: str | None = None
    trigger_event: str | None = None
    trigger_details: str | None = None
    task_for_user: str | None = None
    expected_artifact: str | None = None
    answer_structure_hint: str | None = None
    constraints_text: str | None = None
    dialog_turns_hint: str | None = None
    stakes_text: str | None = None
    personalization_variables: str | None = None
    personalization_options_text: str | None = None
    difficulty_toggles: str | None = None
    evaluation_notes: str | None = None
    author_name: str | None = None
    reviewer_name: str | None = None
    methodologist_comment: str | None = None
    personalization_fields: list[str]
    required_blocks: list[str]
    red_flags: list[str]
    qa_blockers: list[str]
    quality_checks: list[AdminMethodologyChecklistItem]
    skill_signals: list[AdminMethodologySkillSignalItem]
    selected_role_ids: list[int]
    selected_skill_ids: list[int]
    role_options: list[AdminMethodologyRoleOption]
    skill_options: list[AdminMethodologySkillOption]
    personalization_options: list[AdminMethodologyPersonalizationOption]
    personalization_items: list[AdminMethodologyPersonalizationValueItem]
    change_log: list[AdminMethodologyChangeLogItem]


class AdminMethodologyCaseUpdateRequest(BaseModel):
    title: str
    difficulty_level: str
    passport_status: str = "draft"
    case_status: str = "draft"
    case_text_status: str = "draft"
    estimated_time_min: int | None = None
    stakeholders_text: str | None = None
    interactivity_mode: str | None = None
    recommended_answer_length: str | None = None
    selection_tags: list[str] = []
    role_personalization_rules: str | None = None
    format_control_rules: str | None = None
    scoring_aggregation_rules: str | None = None
    bad_case_risks: str | None = None
    generation_notes: str | None = None
    intro_context: str | None = None
    facts_data: str | None = None
    participants_roles: str | None = None
    trigger_event: str | None = None
    trigger_details: str | None = None
    task_for_user: str | None = None
    expected_artifact: str | None = None
    answer_structure_hint: str | None = None
    constraints_text: str | None = None
    dialog_turns_hint: str | None = None
    stakes_text: str | None = None
    personalization_items: list[AdminMethodologyPersonalizationValueItem] = []
    personalization_options_text: str | None = None
    difficulty_toggles: str | None = None
    evaluation_notes: str | None = None
    author_name: str | None = None
    reviewer_name: str | None = None
    methodologist_comment: str | None = None
    role_ids: list[int]
    skill_ids: list[int]


class AdminMethodologyResponse(BaseModel):
    title: str
    subtitle: str
    metrics: list[AdminMetricCard]
    branches: list[AdminMethodologyBranchItem]
    coverage: list[AdminMethodologyCoverageRow]
    skill_gaps: list[AdminMethodologySkillGapItem]
    single_point_skills: list[AdminMethodologySinglePointSkillItem]
    case_quality_hotspots: list[AdminMethodologyCaseQualityItem]
    passports: list[AdminMethodologyPassportItem]
    cases: list[AdminMethodologyCaseItem]


class AdminDashboard(BaseModel):
    title: str
    subtitle: str
    is_superadmin: bool = False
    metrics: list[AdminMetricCard]
    competency_average: list[dict[str, str | int | float]]
    mbti_distribution: list[dict[str, str | int]]
    insights: list[AdminInsightCard]
    activity_points: list[int]
    activity_labels: list[str]
    activity_axis_max: int
    activity_period_key: str
    activity_period_label: str


class AdminDetailedReportItem(BaseModel):
    session_id: int
    user_id: int
    full_name: str
    phone: str | None = None
    group_name: str
    role_name: str
    status: str
    score_percent: int | None = None
    mbti_type: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AdminDetailedReportsResponse(BaseModel):
    title: str
    subtitle: str
    total_items: int
    summary_score_percent: float | None = None
    items: list[AdminDetailedReportItem]


class AdminRegressionTestStep(BaseModel):
    name: str
    status: str
    message: str


class AdminRegressionTestRunResponse(BaseModel):
    status: str
    title: str
    summary: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float
    organization_id: int | None = None
    user_ids: list[int] = Field(default_factory=list)
    session_ids: list[int] = Field(default_factory=list)
    steps: list[AdminRegressionTestStep] = Field(default_factory=list)


class AdminRegressionTestStatusResponse(BaseModel):
    title: str
    subtitle: str
    mbti_enabled: bool = False
    mbti_store_available: bool = False
    last_run: AdminRegressionTestRunResponse | None = None
    cleanup_hint: str


class AdminOrganizationAdminItem(BaseModel):
    user_id: int
    email: str
    full_name: str | None = None


class AdminOrganizationMemberItem(BaseModel):
    user_id: int
    email: str
    full_name: str | None = None
    role: str = "member"
    job_description: str | None = None
    raw_position: str | None = None
    raw_duties: str | None = None


class AdminOrganizationItem(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool = True
    domains: list[str] = Field(default_factory=list)
    admins: list[AdminOrganizationAdminItem] = Field(default_factory=list)
    members: list[AdminOrganizationMemberItem] = Field(default_factory=list)
    members_count: int = 0
    reports_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminOrganizationsResponse(BaseModel):
    title: str
    subtitle: str
    items: list[AdminOrganizationItem]


class AdminOrganizationCreateRequest(BaseModel):
    code: str
    name: str


class AdminOrganizationUpdateRequest(BaseModel):
    code: str | None = None
    name: str | None = None


class AdminOrganizationDomainRequest(BaseModel):
    domain: str


class AdminOrganizationAdminRequest(BaseModel):
    email: str
    full_name: str | None = None


class AdminOrganizationMemberRequest(BaseModel):
    email: str
    full_name: str | None = None
    role_description: str | None = None
    job_instructions: str | None = None


class AdminOrganizationMembersImportRequest(BaseModel):
    csv_text: str


class AdminOrganizationImportResult(BaseModel):
    imported_count: int = 0
    skipped_count: int = 0
    errors: list[str] = Field(default_factory=list)
    organizations: AdminOrganizationsResponse


class AdminReportCaseMessage(BaseModel):
    role: str
    message_text: str


class AdminReportCaseSkillResult(BaseModel):
    skill_name: str
    competency_name: str
    assessed_level_code: str | None = None
    assessed_level_name: str | None = None
    artifact_compliance_percent: int | None = None
    block_coverage_percent: int | None = None
    red_flags: list[str] = []
    found_evidence: list[str] = []
    evidence_excerpt: str | None = None


class AdminReportCaseItem(BaseModel):
    session_case_id: int
    case_number: int
    case_title: str
    case_id_code: str | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    personalized_context: str | None = None
    personalized_task: str | None = None
    prompt_text: str | None = None
    dialogue: list[AdminReportCaseMessage] = []
    skill_results: list[AdminReportCaseSkillResult] = []


class AdminReportProfileSummary(BaseModel):
    position: str | None = None
    duties: str | None = None
    domain: str | None = None
    processes: list[str] = []
    tasks: list[str] = []
    stakeholders: list[str] = []
    constraints: list[str] = []


class AdminReportDetailResponse(BaseModel):
    session_id: int
    user_id: int
    full_name: str
    phone: str | None = None
    telegram: str | None = None
    role_name: str
    group_name: str
    status: str
    score_percent: int | None = None
    report_date: datetime | None = None
    competency_average: list[dict[str, str | int | float]]
    mbti_type: str | None = None
    mbti_summary: str | None = None
    mbti_axes: list[dict[str, str | int]]
    insight_title: str | None = None
    insight_text: str | None = None
    basis_items: list[str] = []
    response_pattern: str | None = None
    expert_comment: str | None = None
    expert_name: str | None = None
    expert_contacts: str | None = None
    expert_assessed_at: datetime | None = None
    can_edit_expert_comment: bool = False
    strengths: list[str]
    growth_areas: list[str]
    quotes: list[str]
    profile_summary: AdminReportProfileSummary | None = None
    case_items: list[AdminReportCaseItem] = []


class UserDashboard(BaseModel):
    greeting_name: str
    active_assessment: AssessmentCard
    available_assessments: list[AvailableAssessment]
    reports_total: int = 0
    reports: list[AssessmentReport]


class CheckOrCreateUserResponse(BaseModel):
    exists: bool
    message: str
    user: UserResponse | None = None
    requires_user_data: bool = False
    agent: AgentReply | None = None
    dashboard: UserDashboard | None = None
    is_admin: bool = False
    admin_dashboard: AdminDashboard | None = None


class SessionCaseStructuredAnalysisResponse(BaseModel):
    id: int
    session_id: int
    user_id: int
    session_case_id: int
    case_registry_id: int | None = None
    case_id_code: str | None = None
    case_title: str | None = None
    skill_id: int
    skill_code: str | None = None
    skill_name: str
    competency_name: str
    expected_artifact_code: str | None = None
    expected_artifact_name: str | None = None
    detected_artifact_parts: str | None = None
    missing_artifact_parts: str | None = None
    artifact_compliance_percent: int | None = None
    structural_elements: str | None = None
    detected_required_blocks: str | None = None
    missing_required_blocks: str | None = None
    block_coverage_percent: int | None = None
    red_flags: str | None = None
    found_evidence: str | None = None
    detected_signals: str | None = None
    evidence_excerpt: str | None = None
    source_message_count: int
    analyzed_at: datetime
    updated_at: datetime
    requires_user_data: bool = False
    agent: AgentReply
    dashboard: UserDashboard | None = None
    is_admin: bool = False
    admin_dashboard: AdminDashboard | None = None


class AgentMessageRequest(BaseModel):
    session_id: str
    message: str


class AssessmentStartResponse(BaseModel):
    session_code: str
    session_id: int
    session_case_id: int | None = None
    case_title: str | None = None
    case_number: int
    total_cases: int
    message: str
    assessment_completed: bool
    case_completed: bool
    case_time_limit_minutes: int | None = None
    planned_case_duration_minutes: int | None = None
    case_started_at: datetime | None = None
    case_time_remaining_seconds: int | None = None
    time_expired: bool = False
    history_match_case: bool = False
    history_match_case_text: bool = False
    history_match_type: bool = False
    history_last_used_at: datetime | None = None
    history_use_count: int = 0
    history_flag: str | None = None
    history_is_new: bool = False
    is_dialog_case: bool = False
    pending_auto_finish: bool = False
    auto_finish_delay_ms: int | None = None
    mbti_case_result: dict | None = None
    mbti_followup_questions: list[str] | None = None
    mbti_followup_pending: bool = False
    mbti_followup_index: int | None = None
    mbti_followup_total: int | None = None
    mbti_summary: dict | None = None


class AssessmentSessionLookupResponse(BaseModel):
    user_id: int
    session_id: int
    session_code: str


class AssessmentMessageRequest(BaseModel):
    session_code: str
    message: str


class AssessmentTimerControlRequest(BaseModel):
    session_code: str


class AssessmentMessageResponse(BaseModel):
    session_code: str
    session_id: int
    session_case_id: int | None = None
    case_title: str | None = None
    case_number: int
    total_cases: int
    message: str
    case_completed: bool
    assessment_completed: bool
    result_status: str | None = None
    completion_score: float | None = None
    evaluator_summary: str | None = None
    case_time_limit_minutes: int | None = None
    planned_case_duration_minutes: int | None = None
    case_started_at: datetime | None = None
    case_time_remaining_seconds: int | None = None
    time_expired: bool = False
    history_match_case: bool = False
    history_match_case_text: bool = False
    history_match_type: bool = False
    history_last_used_at: datetime | None = None
    history_use_count: int = 0
    history_flag: str | None = None
    history_is_new: bool = False
    is_dialog_case: bool = False
    pending_auto_finish: bool = False
    auto_finish_delay_ms: int | None = None
    mbti_case_result: dict | None = None
    mbti_followup_questions: list[str] | None = None
    mbti_followup_pending: bool = False
    mbti_followup_index: int | None = None
    mbti_followup_total: int | None = None
    mbti_summary: dict | None = None


class SkillAssessmentResponse(BaseModel):
    id: int
    session_id: int
    user_id: int
    skill_id: int
    competency_skill_id: int | None = None
    competency_name: str | None = None
    skill_code: str | None = None
    skill_name: str
    assessed_level_code: str
    assessed_level_name: str
    rubric_match_scores: str | None = None
    structural_elements: str | None = None
    red_flags: str | None = None
    found_evidence: str | None = None
    detected_required_blocks: str | None = None
    missing_required_blocks: str | None = None
    block_coverage_percent: int | None = None
    expected_artifact_names: str | None = None
    artifact_compliance_percent: int | None = None
    rationale: str | None = None
    evidence_excerpt: str | None = None
    source_session_case_ids: str | None = None
    created_at: datetime
    updated_at: datetime


class AssessmentReportInterpretationResponse(BaseModel):
    insight_title: str
    insight_text: str
    basis_items: list[str]
    growth_areas: list[str]
    has_interpretation_signal: bool
    has_confident_strongest: bool
    response_pattern: str
    mbti_summary: dict | None = None


class MbtiRefinementQuestion(BaseModel):
    code: str
    text: str


class MbtiRefinementStartResponse(BaseModel):
    active: bool
    completed: bool
    refinement_id: int
    question_index: int
    question_total: int
    current_confidence: int
    target_confidence: int
    current_question: MbtiRefinementQuestion | None = None
    remaining_gaps: list[str] = Field(default_factory=list)
    resolved_gaps: list[str] = Field(default_factory=list)
    updated_mbti_summary: dict | None = None


class MbtiRefinementMessageRequest(BaseModel):
    refinement_id: int
    answer: str


class MbtiRefinementMessageResponse(BaseModel):
    active: bool
    completed: bool
    refinement_id: int
    question_index: int
    question_total: int
    current_confidence: int
    target_confidence: int
    current_question: MbtiRefinementQuestion | None = None
    remaining_gaps: list[str] = Field(default_factory=list)
    resolved_gaps: list[str] = Field(default_factory=list)
    updated_mbti_summary: dict | None = None


class MbtiRefinementStateResponse(BaseModel):
    active: bool
    completed: bool
    refinement_id: int | None = None
    question_index: int = 0
    question_total: int = 0
    current_confidence: int = 0
    target_confidence: int = 75
    current_question: MbtiRefinementQuestion | None = None
    remaining_gaps: list[str] = Field(default_factory=list)
    resolved_gaps: list[str] = Field(default_factory=list)
    updated_mbti_summary: dict | None = None


class UserAssessmentHistoryItem(BaseModel):
    session_id: int
    session_code: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    completed_cases: int
    total_cases: int
    progress_percent: int
    overall_score_percent: int | None = None
    expert_comment: str | None = None


class AdminExpertCommentUpdateRequest(BaseModel):
    expert_comment: str | None = None
    expert_name: str | None = None
    expert_contacts: str | None = None
    expert_assessed_at: datetime | None = None


class AdminExpertGroupExportRequest(BaseModel):
    session_ids: list[int] = Field(default_factory=list)


class UserProfileSummaryResponse(BaseModel):
    user: UserResponse
    total_assessments: int
    completed_assessments: int
    average_score_percent: int | None = None
    latest_session_id: int | None = None
    history: list[UserAssessmentHistoryItem]


class UserProfileUpdateRequest(BaseModel):
    email: str | None = None
    telegram: str | None = None
    avatar_data_url: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Введите корректный email")
        return value

    @field_validator("telegram", mode="before")
    @classmethod
    def normalize_telegram(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("avatar_data_url", mode="before")
    @classmethod
    def normalize_avatar(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class UserSessionRestoreResponse(BaseModel):
    authenticated: bool
    user: UserResponse | None = None
    dashboard: UserDashboard | None = None
    is_admin: bool = False
    admin_dashboard: AdminDashboard | None = None


class UserSessionBootstrapResponse(BaseModel):
    user: UserResponse
    dashboard: UserDashboard
    is_admin: bool = False
    admin_dashboard: AdminDashboard | None = None


class AppVersionResponse(BaseModel):
    version: str


class OperationProgressStep(BaseModel):
    label: str
    description: str
    status: str


class OperationProgressResponse(BaseModel):
    operation_id: str
    title: str
    message: str
    status: str
    current_step_index: int
    progress_percent: int
    steps: list[OperationProgressStep]
