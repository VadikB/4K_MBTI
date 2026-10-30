import { state, persistAssessmentContext, clearAssessmentContext } from './state.js';
import {
  authPanel,
  authCompletePanel,
  authCompleteTitle,
  authCompleteDescription,
  authCompleteContinueButton,
  authEmailForm,
  emailInput,
  authTokenForm,
  authCredentialLabel,
  magicTokenInput,
  authPasswordConfirmField,
  authPasswordConfirmInput,
  authStatus,
  onboardingPanel,
  dashboardPanel,
  adminPanel,
  adminOrganizationsPanel,
  adminAssessmentEmptyPanel,
  adminAssessmentEmptyDescription,
  adminRegressionTestsPanel,
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
  participantAreaNavigation,
} from './dom.js';

export const hideAllPanels = () => {
  document.getElementById('session-restore-panel')?.classList.add('hidden');
  participantAreaNavigation?.classList.toggle('hidden', !state.canAdmin || state.activeArea !== 'assessment');
  authPanel.classList.add('hidden');
  authCompletePanel?.classList.add('hidden');
  onboardingPanel.classList.add('hidden');
  dashboardPanel.classList.add('hidden');
  adminPanel.classList.add('hidden');
  if (adminOrganizationsPanel) {
    adminOrganizationsPanel.classList.add('hidden');
  }
  adminAssessmentEmptyPanel?.classList.add('hidden');
  if (adminRegressionTestsPanel) {
    adminRegressionTestsPanel.classList.add('hidden');
  }
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

export const openAuthComplete = () => {
  hideAllPanels();
  state.currentScreen = 'auth-complete';
  persistAssessmentContext();
  authCompletePanel?.classList.remove('hidden');
  window.history.replaceState({ screen: 'auth-complete' }, '', '/?screen=auth-complete');
};

export const openAcquaintanceWaiting = (readiness = {}) => {
  hideAllPanels();
  const assignmentMissing = readiness.status === 'waiting_for_assignment';
  if (assignmentMissing && state.canAdmin && !state.adminDashboard?.is_superadmin) {
    participantAreaNavigation?.classList.add('hidden');
    state.currentScreen = 'admin-assessment-empty';
    state.activeArea = 'assessment';
    persistAssessmentContext();
    if (adminAssessmentEmptyDescription) {
      adminAssessmentEmptyDescription.textContent = 'Вы можете назначить себе оценку в разделе «Организация и участники» после подготовки необходимых сведений.';
    }
    adminAssessmentEmptyPanel?.classList.remove('hidden');
    window.history.replaceState({ screen: 'admin-assessment-empty' }, '', '/?screen=admin-assessment-empty');
    return;
  }
  state.currentScreen = 'auth-complete';
  persistAssessmentContext();
  if (authCompleteTitle) authCompleteTitle.textContent = assignmentMissing ? 'Оценка пока не назначена' : 'Данные для оценки готовятся';
  if (authCompleteDescription) {
    authCompleteDescription.textContent = readiness.message
      || 'Организация ещё готовит данные для вашей оценки. Когда подготовка будет завершена, здесь можно будет начать знакомство';
  }
  if (authCompleteContinueButton) {
    authCompleteContinueButton.textContent = assignmentMissing ? 'Вернуться в управление' : 'Проверить готовность';
    authCompleteContinueButton.dataset.action = assignmentMissing ? 'return-to-management' : 'check-acquaintance-readiness';
  }
  authCompletePanel?.classList.remove('hidden');
  window.history.replaceState({ screen: 'auth-complete' }, '', '/?screen=auth-complete');
};

export const navigateToScreen = (screen) => {
  persistAssessmentContext();
  const params = new URLSearchParams({
    screen,
    ui: String(Date.now()),
  });
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
  if (state.assessmentRuntimeKind === 'cycle' && state.productCycleId) params.set('cycle_id', state.productCycleId);

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
  if (emailInput) {
    emailInput.value = '';
    emailInput.focus();
  }
  if (magicTokenInput) {
    magicTokenInput.value = '';
    magicTokenInput.type = 'text';
    magicTokenInput.autocomplete = 'one-time-code';
    magicTokenInput.placeholder = 'Вставьте код или ссылку из письма';
  }
  if (authCredentialLabel) {
    authCredentialLabel.textContent = 'Код или ссылка для входа';
  }
  if (authPasswordConfirmField) {
    authPasswordConfirmField.classList.add('hidden');
  }
  if (authPasswordConfirmInput) {
    authPasswordConfirmInput.required = false;
    authPasswordConfirmInput.value = '';
  }
  if (authTokenForm) {
    authTokenForm.classList.add('hidden');
  }
  authEmailForm?.classList.remove('hidden');
  if (authStatus) {
    authStatus.textContent = '';
    authStatus.classList.add('hidden');
  }
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
