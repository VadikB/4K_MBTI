export const state = {
  sessionId: null,
  completed: false,
  isChatSubmitting: false,
  pendingAgentMessage: null,
  pendingActionOptions: [],
  pendingConsentTitle: null,
  pendingConsentText: null,
  pendingUser: null,
  dashboard: null,
  isAdmin: false,
  adminDashboard: null,
  adminOrganizations: null,
  adminPromptLab: null,
  adminPromptLabPreviewResult: null,
  adminPromptLabResult: null,
  adminPromptLabTab: 'cases',
  adminPromptLabSelectedCaseCodes: [],
  adminPromptLabRunning: false,
  adminPromptLabDialogPreview: null,
  adminPromptLabDialogHistory: [],
  adminPromptLabDialogRunning: false,
  adminPromptLabDialogPrepared: false,
  adminPromptLabDialogSelectedCaseCode: null,
  adminMethodology: null,
  adminMethodologyDetail: null,
  adminMethodologyDetailCode: null,
  adminMethodologyEditMode: false,
  adminMethodologySaving: false,
  adminMethodologyDraft: null,
  adminMethodologyActiveTextField: 'intro_context',
  adminMethodologyPage: 1,
  adminMethodologyRiskUi: {
    skillGaps: { collapsed: true, page: 1 },
    singlePoints: { collapsed: true, page: 1 },
    caseQuality: { collapsed: true, page: 1 },
  },
  adminMethodologySearch: '',
  adminMethodologyTab: 'library',
  adminReports: null,
  adminReportDetail: null,
  adminReportDetailSessionId: null,
  adminReportDetailSkillAssessments: [],
  adminReportDetailSkillAssessmentsLoading: false,
  adminReportDetailExpertCommentEditing: false,
  adminReportDetailExpertCommentOriginal: '',
  adminReportDetailExpertCommentDirty: false,
  adminReportDetailExpertMetaOriginal: {
    expert_name: '',
    expert_contacts: '',
    expert_assessed_at: '',
  },
  adminReportsSearch: '',
  adminReportsPage: 1,
  adminReportsSelectedSessionIds: [],
  adminPeriodKey: '30d',
  pendingRoleOptions: [],
  pendingNoChangesQuickReply: false,
  resumeAssessmentAfterProfileCompletion: false,
  assessmentSessionCode: null,
  assessmentCaseNumber: 0,
  assessmentTotalCases: 0,
  assessmentCaseTitle: null,
  onboardingIndex: 0,
  isNewUserFlow: false,
  onboardingShown: false,
  newUserSequenceStep: 'onboarding',
  assessmentTimeLimitMinutes: null,
  assessmentCaseStartedAt: null,
  assessmentRemainingSeconds: null,
  assessmentTimerId: null,
  assessmentTimeoutInFlight: false,
  assessmentAutoFinishTimerId: null,
  assessmentPauseInFlight: false,
  activeInterviewCaseKey: null,
  caseOutcomeByNumber: {},
  processingTimerId: null,
  processingStepIndex: 0,
  processingAgents: [],
  assessmentSessionId: null,
  skillAssessments: [],
  reportCompetencyTab: 'Коммуникация',
  reportReturnTarget: 'home',
  processingAnimationDone: false,
  processingDataLoaded: false,
  processingAutoTransitionStarted: false,
  assessmentPreparationStatus: 'idle',
  assessmentPreparationProgressPercent: 0,
  assessmentPreparationTitle: '',
  assessmentPreparationMessage: '',
  assessmentPreparationOperationId: null,
  assessmentPreparationPollId: null,
  adminPromptLabProgressStatus: 'idle',
  adminPromptLabProgressPercent: 0,
  adminPromptLabProgressTitle: '',
  adminPromptLabProgressMessage: '',
  adminPromptLabOperationId: null,
  adminPromptLabPollId: null,
  preparedAssessmentStartResponse: null,
  assessmentMbtiSummary: null,
  profileSummary: null,
  profileAvatarDraft: null,
  profileSelectedSessionId: null,
  profileHistoryPage: 1,
  profileSkillAssessments: [],
  profileSkillsBySession: {},
  currentScreen: 'auth',
};

export const STORAGE_KEYS = {
  pendingUser: 'agent4k.pendingUser',
  dashboard: 'agent4k.dashboard',
  isAdmin: 'agent4k.isAdmin',
  adminDashboard: 'agent4k.adminDashboard',
  adminOrganizations: 'agent4k.adminOrganizations',
  adminMethodology: 'agent4k.adminMethodology',
  adminMethodologyDetail: 'agent4k.adminMethodologyDetail',
  adminMethodologyDetailCode: 'agent4k.adminMethodologyDetailCode',
  adminMethodologySearch: 'agent4k.adminMethodologySearch',
  adminMethodologyTab: 'agent4k.adminMethodologyTab',
  adminReports: 'agent4k.adminReports',
  adminReportDetail: 'agent4k.adminReportDetail',
  adminReportDetailSessionId: 'agent4k.adminReportDetailSessionId',
  adminReportsSearch: 'agent4k.adminReportsSearch',
  adminReportsPage: 'agent4k.adminReportsPage',
  adminPeriodKey: 'agent4k.adminPeriodKey',
  pendingRoleOptions: 'agent4k.pendingRoleOptions',
  pendingNoChangesQuickReply: 'agent4k.pendingNoChangesQuickReply',
  resumeAssessmentAfterProfileCompletion: 'agent4k.resumeAssessmentAfterProfileCompletion',
  assessmentSessionId: 'agent4k.assessmentSessionId',
  assessmentSessionCode: 'agent4k.assessmentSessionCode',
  assessmentTotalCases: 'agent4k.assessmentTotalCases',
  assessmentMbtiSummary: 'agent4k.assessmentMbtiSummary',
  assessmentCompletedOnce: 'agent4k.assessmentCompletedOnce',
  completionPending: 'agent4k.completionPending',
  sessionId: 'agent4k.sessionId',
  pendingAgentMessage: 'agent4k.pendingAgentMessage',
  pendingActionOptions: 'agent4k.pendingActionOptions',
  pendingConsentTitle: 'agent4k.pendingConsentTitle',
  pendingConsentText: 'agent4k.pendingConsentText',
  completed: 'agent4k.completed',
  isNewUserFlow: 'agent4k.isNewUserFlow',
  currentScreen: 'agent4k.currentScreen',
};

const memoryStorage = new Map();

export const safeStorage = {
  getItem(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (_error) {
      return memoryStorage.has(key) ? memoryStorage.get(key) : null;
    }
  },
  setItem(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (_error) {
      memoryStorage.set(key, value);
    }
  },
  removeItem(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (_error) {
      memoryStorage.delete(key);
    }
  },
};

let leaveInterviewCleanup = () => {};
export const registerLeaveInterviewCleanup = (fn) => {
  leaveInterviewCleanup = typeof fn === 'function' ? fn : () => {};
};

export const setCurrentScreen = (screen) => {
  if (state.currentScreen === 'interview' && screen !== 'interview') {
    leaveInterviewCleanup();
  }
  state.currentScreen = screen;
  safeStorage.setItem(STORAGE_KEYS.currentScreen, screen);
};

export const persistAssessmentContext = () => {
  if (state.sessionId) {
    safeStorage.setItem(STORAGE_KEYS.sessionId, state.sessionId);
  }
  if (state.pendingAgentMessage) {
    safeStorage.setItem(STORAGE_KEYS.pendingAgentMessage, state.pendingAgentMessage);
  }
  safeStorage.setItem(STORAGE_KEYS.pendingActionOptions, JSON.stringify(state.pendingActionOptions || []));
  if (state.pendingConsentTitle) {
    safeStorage.setItem(STORAGE_KEYS.pendingConsentTitle, state.pendingConsentTitle);
  } else {
    safeStorage.removeItem(STORAGE_KEYS.pendingConsentTitle);
  }
  if (state.pendingConsentText) {
    safeStorage.setItem(STORAGE_KEYS.pendingConsentText, state.pendingConsentText);
  } else {
    safeStorage.removeItem(STORAGE_KEYS.pendingConsentText);
  }
  safeStorage.setItem(STORAGE_KEYS.completed, state.completed ? '1' : '0');
  safeStorage.setItem(STORAGE_KEYS.isNewUserFlow, state.isNewUserFlow ? '1' : '0');
  safeStorage.setItem(STORAGE_KEYS.currentScreen, state.currentScreen || 'auth');
  if (state.pendingUser) {
    safeStorage.setItem(STORAGE_KEYS.pendingUser, JSON.stringify(state.pendingUser));
  }
  if (state.dashboard) {
    safeStorage.setItem(STORAGE_KEYS.dashboard, JSON.stringify(state.dashboard));
  }
  safeStorage.setItem(STORAGE_KEYS.isAdmin, state.isAdmin ? '1' : '0');
  if (state.adminDashboard) {
    safeStorage.setItem(STORAGE_KEYS.adminDashboard, JSON.stringify(state.adminDashboard));
  }
  if (state.adminOrganizations) {
    safeStorage.setItem(STORAGE_KEYS.adminOrganizations, JSON.stringify(state.adminOrganizations));
  }
  if (state.adminMethodology) {
    safeStorage.setItem(STORAGE_KEYS.adminMethodology, JSON.stringify(state.adminMethodology));
  }
  if (state.adminMethodologyDetail) {
    safeStorage.setItem(STORAGE_KEYS.adminMethodologyDetail, JSON.stringify(state.adminMethodologyDetail));
  }
  if (state.adminMethodologyDetailCode) {
    safeStorage.setItem(STORAGE_KEYS.adminMethodologyDetailCode, state.adminMethodologyDetailCode);
  }
  if (state.adminReports) {
    safeStorage.setItem(STORAGE_KEYS.adminReports, JSON.stringify(state.adminReports));
  }
  if (state.adminReportDetail) {
    safeStorage.setItem(STORAGE_KEYS.adminReportDetail, JSON.stringify(state.adminReportDetail));
  }
  if (state.adminReportDetailSessionId) {
    safeStorage.setItem(STORAGE_KEYS.adminReportDetailSessionId, String(state.adminReportDetailSessionId));
  }
  if (state.adminPeriodKey) {
    safeStorage.setItem(STORAGE_KEYS.adminPeriodKey, state.adminPeriodKey);
  }
  safeStorage.setItem(STORAGE_KEYS.adminMethodologySearch, state.adminMethodologySearch || '');
  safeStorage.setItem(STORAGE_KEYS.adminMethodologyTab, state.adminMethodologyTab || 'library');
  safeStorage.setItem(STORAGE_KEYS.pendingRoleOptions, JSON.stringify(state.pendingRoleOptions || []));
  safeStorage.setItem(STORAGE_KEYS.pendingNoChangesQuickReply, state.pendingNoChangesQuickReply ? '1' : '0');
  safeStorage.setItem(
    STORAGE_KEYS.resumeAssessmentAfterProfileCompletion,
    state.resumeAssessmentAfterProfileCompletion ? '1' : '0',
  );
  safeStorage.setItem(STORAGE_KEYS.adminReportsSearch, state.adminReportsSearch || '');
  safeStorage.setItem(STORAGE_KEYS.adminReportsPage, String(state.adminReportsPage || 1));
  if (state.assessmentSessionId) {
    safeStorage.setItem(STORAGE_KEYS.assessmentSessionId, String(state.assessmentSessionId));
  }
  if (state.assessmentSessionCode) {
    safeStorage.setItem(STORAGE_KEYS.assessmentSessionCode, state.assessmentSessionCode);
  }
  if (state.assessmentTotalCases) {
    safeStorage.setItem(STORAGE_KEYS.assessmentTotalCases, String(state.assessmentTotalCases));
  }
  if (state.assessmentMbtiSummary) {
    safeStorage.setItem(STORAGE_KEYS.assessmentMbtiSummary, JSON.stringify(state.assessmentMbtiSummary));
  } else {
    safeStorage.removeItem(STORAGE_KEYS.assessmentMbtiSummary);
  }
  if (state.assessmentSessionId || state.skillAssessments.length > 0) {
    safeStorage.setItem(STORAGE_KEYS.assessmentCompletedOnce, '1');
  }
};

export const restoreAssessmentContext = () => {
  try {
    const storedUser = safeStorage.getItem(STORAGE_KEYS.pendingUser);
    const storedDashboard = safeStorage.getItem(STORAGE_KEYS.dashboard);
    const storedSessionId = safeStorage.getItem(STORAGE_KEYS.assessmentSessionId);
    const storedIsAdmin = safeStorage.getItem(STORAGE_KEYS.isAdmin);
    const storedAdminDashboard = safeStorage.getItem(STORAGE_KEYS.adminDashboard);
    const storedAdminOrganizations = safeStorage.getItem(STORAGE_KEYS.adminOrganizations);
    const storedAdminMethodology = safeStorage.getItem(STORAGE_KEYS.adminMethodology);
    const storedAdminMethodologyDetail = safeStorage.getItem(STORAGE_KEYS.adminMethodologyDetail);
    const storedAdminMethodologyDetailCode = safeStorage.getItem(STORAGE_KEYS.adminMethodologyDetailCode);
    const storedAdminMethodologySearch = safeStorage.getItem(STORAGE_KEYS.adminMethodologySearch);
    const storedAdminMethodologyTab = safeStorage.getItem(STORAGE_KEYS.adminMethodologyTab);
    const storedAdminReports = safeStorage.getItem(STORAGE_KEYS.adminReports);
    const storedAdminReportDetail = safeStorage.getItem(STORAGE_KEYS.adminReportDetail);
    const storedAdminReportDetailSessionId = safeStorage.getItem(STORAGE_KEYS.adminReportDetailSessionId);
    const storedAdminPeriodKey = safeStorage.getItem(STORAGE_KEYS.adminPeriodKey);
    const storedPendingRoleOptions = safeStorage.getItem(STORAGE_KEYS.pendingRoleOptions);
    const storedPendingNoChangesQuickReply = safeStorage.getItem(STORAGE_KEYS.pendingNoChangesQuickReply);
    const storedResumeAssessmentAfterProfileCompletion = safeStorage.getItem(STORAGE_KEYS.resumeAssessmentAfterProfileCompletion);
    const storedAdminReportsSearch = safeStorage.getItem(STORAGE_KEYS.adminReportsSearch);
    const storedAdminReportsPage = safeStorage.getItem(STORAGE_KEYS.adminReportsPage);
    const storedSessionCode = safeStorage.getItem(STORAGE_KEYS.assessmentSessionCode);
    const storedTotalCases = safeStorage.getItem(STORAGE_KEYS.assessmentTotalCases);
    const storedAssessmentMbtiSummary = safeStorage.getItem(STORAGE_KEYS.assessmentMbtiSummary);
    const storedConversationSessionId = safeStorage.getItem(STORAGE_KEYS.sessionId);
    const storedPendingAgentMessage = safeStorage.getItem(STORAGE_KEYS.pendingAgentMessage);
    const storedPendingActionOptions = safeStorage.getItem(STORAGE_KEYS.pendingActionOptions);
    const storedPendingConsentTitle = safeStorage.getItem(STORAGE_KEYS.pendingConsentTitle);
    const storedPendingConsentText = safeStorage.getItem(STORAGE_KEYS.pendingConsentText);
    const storedCompleted = safeStorage.getItem(STORAGE_KEYS.completed);
    const storedIsNewUserFlow = safeStorage.getItem(STORAGE_KEYS.isNewUserFlow);
    const storedCurrentScreen = safeStorage.getItem(STORAGE_KEYS.currentScreen);
    const storedAssessmentCompletedOnce = safeStorage.getItem(STORAGE_KEYS.assessmentCompletedOnce);

    if (storedUser) {
      state.pendingUser = JSON.parse(storedUser);
    }
    if (storedDashboard) {
      state.dashboard = JSON.parse(storedDashboard);
    }
    if (storedIsAdmin) {
      state.isAdmin = storedIsAdmin === '1';
    }
    if (storedAdminDashboard) {
      state.adminDashboard = JSON.parse(storedAdminDashboard);
    }
    if (storedAdminOrganizations) {
      state.adminOrganizations = JSON.parse(storedAdminOrganizations);
    }
    if (storedAdminMethodology) {
      state.adminMethodology = JSON.parse(storedAdminMethodology);
    }
    if (storedAdminMethodologyDetail) {
      state.adminMethodologyDetail = JSON.parse(storedAdminMethodologyDetail);
    }
    if (storedAdminMethodologyDetailCode) {
      state.adminMethodologyDetailCode = storedAdminMethodologyDetailCode;
    }
    if (storedAdminMethodologySearch) {
      state.adminMethodologySearch = storedAdminMethodologySearch;
    }
    if (storedAdminMethodologyTab) {
      state.adminMethodologyTab = storedAdminMethodologyTab;
    }
    if (storedAdminReports) {
      state.adminReports = JSON.parse(storedAdminReports);
    }
    if (storedAdminReportDetail) {
      state.adminReportDetail = JSON.parse(storedAdminReportDetail);
    }
    if (storedAdminReportDetailSessionId) {
      state.adminReportDetailSessionId = Number(storedAdminReportDetailSessionId);
    }
    if (storedAdminPeriodKey) {
      state.adminPeriodKey = storedAdminPeriodKey;
    }
    if (storedPendingRoleOptions) {
      state.pendingRoleOptions = JSON.parse(storedPendingRoleOptions);
    }
    if (storedPendingNoChangesQuickReply) {
      state.pendingNoChangesQuickReply = storedPendingNoChangesQuickReply === '1';
    }
    if (storedResumeAssessmentAfterProfileCompletion) {
      state.resumeAssessmentAfterProfileCompletion = storedResumeAssessmentAfterProfileCompletion === '1';
    }
    if (storedAdminReportsSearch) {
      state.adminReportsSearch = storedAdminReportsSearch;
    }
    if (storedAdminReportsPage) {
      state.adminReportsPage = Number(storedAdminReportsPage) || 1;
    }
    if (storedSessionId) {
      state.assessmentSessionId = Number(storedSessionId);
    }
    if (storedSessionCode) {
      state.assessmentSessionCode = storedSessionCode;
    }
    if (storedTotalCases) {
      state.assessmentTotalCases = Number(storedTotalCases);
    }
    if (storedAssessmentMbtiSummary) {
      state.assessmentMbtiSummary = JSON.parse(storedAssessmentMbtiSummary);
    }
    if (storedConversationSessionId) {
      state.sessionId = storedConversationSessionId;
    }
    if (storedPendingAgentMessage) {
      state.pendingAgentMessage = storedPendingAgentMessage;
    }
    if (storedPendingActionOptions) {
      state.pendingActionOptions = JSON.parse(storedPendingActionOptions);
    }
    if (storedPendingConsentTitle) {
      state.pendingConsentTitle = storedPendingConsentTitle;
    }
    if (storedPendingConsentText) {
      state.pendingConsentText = storedPendingConsentText;
    }
    if (storedCompleted) {
      state.completed = storedCompleted === '1';
    }
    if (storedIsNewUserFlow) {
      state.isNewUserFlow = storedIsNewUserFlow === '1';
    }
    if (storedCurrentScreen) {
      state.currentScreen = storedCurrentScreen;
    }
    if (storedAssessmentCompletedOnce === '1') {
      safeStorage.setItem(STORAGE_KEYS.assessmentCompletedOnce, '1');
    }
  } catch (error) {
    console.error('Failed to restore assessment context', error);
  }
};

export const clearAssessmentStorage = () => {
  Object.values(STORAGE_KEYS).forEach((key) => {
    safeStorage.removeItem(key);
  });
};

export const clearAssessmentContext = () => {
  clearAssessmentStorage();
  state.reportInterpretation = null;
  state.assessmentMbtiSummary = null;
};

export const restoreAssessmentContextFromParams = (params) => {
  const userId = params.get('user_id');
  const sessionId = params.get('session_id');
  const adminReportSessionId = params.get('admin_report_session_id');
  const sessionCode = params.get('session_code');
  const totalCases = params.get('total_cases');
  const fullName = params.get('full_name');
  const jobDescription = params.get('job_description');

  if (userId) {
    state.pendingUser = {
      ...(state.pendingUser || {}),
      id: Number(userId),
      full_name: fullName || state.pendingUser?.full_name || 'Пользователь',
      job_description: jobDescription || state.pendingUser?.job_description || 'Должность не указана',
    };
  }

  if (sessionId) {
    state.assessmentSessionId = Number(sessionId);
  }

  if (adminReportSessionId) {
    state.adminReportDetailSessionId = Number(adminReportSessionId);
  }

  if (sessionCode) {
    state.assessmentSessionCode = sessionCode;
  }

  if (totalCases) {
    state.assessmentTotalCases = Number(totalCases);
  }
};
