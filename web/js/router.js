import { state, persistAssessmentContext, clearAssessmentContext } from './state.js';
import {
  authPanel,
  phoneInput,
  onboardingPanel,
  dashboardPanel,
  adminPanel,
  adminPromptLabPanel,
  adminMethodologyPanel,
  adminReportsPanel,
  adminReportDetailPanel,
  aiWelcomePanel,
  prechatPanel,
  interviewPanel,
  profilePanel,
  reportsPanel,
  processingPanel,
  reportPanel,
  chatPanel,
} from './dom.js';

export const hideAllPanels = () => {
  authPanel.classList.add('hidden');
  onboardingPanel.classList.add('hidden');
  dashboardPanel.classList.add('hidden');
  adminPanel.classList.add('hidden');
  if (adminPromptLabPanel) {
    adminPromptLabPanel.classList.add('hidden');
  }
  adminMethodologyPanel.classList.add('hidden');
  adminReportsPanel.classList.add('hidden');
  adminReportDetailPanel.classList.add('hidden');
  aiWelcomePanel.classList.add('hidden');
  prechatPanel.classList.add('hidden');
  interviewPanel.classList.add('hidden');
  profilePanel.classList.add('hidden');
  reportsPanel.classList.add('hidden');
  processingPanel.classList.add('hidden');
  reportPanel.classList.add('hidden');
  chatPanel.classList.add('hidden');
};

export const navigateToScreen = (screen) => {
  persistAssessmentContext();
  const params = new URLSearchParams({
    screen,
    ui: String(Date.now()),
  });
  if (state.pendingUser?.id) {
    params.set('user_id', String(state.pendingUser.id));
    params.set('full_name', state.pendingUser.full_name || 'Пользователь');
    params.set('job_description', state.pendingUser.job_description || 'Должность не указана');
  }
  if (state.assessmentSessionId) {
    params.set('session_id', String(state.assessmentSessionId));
  }

  if (state.adminReportDetailSessionId) {
    params.set('admin_report_session_id', String(state.adminReportDetailSessionId));
  }
  if (state.assessmentSessionCode) {
    params.set('session_code', state.assessmentSessionCode);
  }
  if (state.assessmentTotalCases) {
    params.set('total_cases', String(state.assessmentTotalCases));
  }
  window.location.replace('/?' + params.toString());
};

export const syncUrlState = (screen, options = {}) => {
  const { replace = false } = options;
  const params = new URLSearchParams();
  params.set('screen', screen);
  params.set('ui', String(Date.now()));

  if (state.pendingUser?.id) {
    params.set('user_id', String(state.pendingUser.id));
    params.set('full_name', state.pendingUser.full_name || 'Пользователь');
    params.set('job_description', state.pendingUser.job_description || 'Должность не указана');
  }

  if (state.sessionId) {
    params.set('agent_session_id', state.sessionId);
  }

  if (state.assessmentSessionId) {
    params.set('session_id', String(state.assessmentSessionId));
  }

  if (state.adminReportDetailSessionId) {
    params.set('admin_report_session_id', String(state.adminReportDetailSessionId));
  }

  if (state.assessmentSessionCode) {
    params.set('session_code', state.assessmentSessionCode);
  }

  if (state.assessmentTotalCases) {
    params.set('total_cases', String(state.assessmentTotalCases));
  }

  const nextUrl = '/?' + params.toString();
  const currentUrl = window.location.pathname + window.location.search;
  if (currentUrl === nextUrl) {
    return;
  }

  if (replace || !window.history.state) {
    window.history.replaceState({ screen }, '', nextUrl);
    return;
  }

  window.history.pushState({ screen }, '', nextUrl);
};

export const returnToStart = () => {
  clearAssessmentContext();
  state.currentScreen = 'auth';
  hideAllPanels();
  authPanel.classList.remove('hidden');
  phoneInput.value = '';
  phoneInput.focus();
  window.history.replaceState({ screen: 'auth' }, '', '/');
};

export const navigateBackOrFallback = (fallback) => {
  if (window.history.length > 1) {
    window.history.back();
    return;
  }

  if (typeof fallback === 'function') {
    fallback();
  }
};
