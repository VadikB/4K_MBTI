import { state, persistAssessmentContext, setCurrentScreen, applyJourneyAssessmentContext } from '../../state.js';
import {
  adminPanel,
  adminUserName,
  adminUserRole,
  adminAvatar,
  adminTitle,
  adminStartAssessmentButton,
  adminOpenMethodologyButton,
  adminOpenOrganizationsButton,
  adminOpenRegressionTestsButton,
  adminOpenPromptLabButton,
  adminActivityTitle,
  adminMetricsGrid,
  adminInsightsGrid,
} from '../../dom.js';
import { sanitizeDisplayRole, buildInitials } from '../../utils/format.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
import { readApiResponse } from '../../api.js';
import {
  renderAdminCompetencyBarChart,
  renderAdminActivityBarChart,
} from './charts.js';
import { loadUserJourneyState } from '../../session.js';

const renderAdminSection = (sectionName, render) => {
  try {
    render();
  } catch (error) {
    console.error('Failed to render admin dashboard section:', sectionName, error);
  }
};

export const renderAdminDashboard = () => {
  const adminDashboard = state.adminDashboard;
  const user = state.pendingUser;
  if (!adminDashboard || !user) {
    return;
  }
  const adminPosition = sanitizeDisplayRole(user.job_description || '') || 'Администратор';

  adminUserName.textContent = user.full_name || 'Администратор системы';
  adminUserRole.textContent = adminPosition;
  adminAvatar.textContent = buildInitials(user.full_name || 'Администратор системы');
  adminTitle.textContent = adminDashboard.title || 'Сводный отчет';
  adminActivityTitle.innerHTML = 'Количество завершенных ассессментов за период';
  const isSuperadmin = Boolean(adminDashboard.is_superadmin);
  if (adminStartAssessmentButton) {
    adminStartAssessmentButton.classList.toggle('hidden', !isSuperadmin);
  }
  if (adminOpenOrganizationsButton) {
    adminOpenOrganizationsButton.classList.toggle('hidden', !state.isAdmin);
  }
  [adminOpenRegressionTestsButton, adminOpenMethodologyButton, adminOpenPromptLabButton].forEach((button) => {
    if (button) {
      button.classList.toggle('hidden', !isSuperadmin);
    }
  });

  adminMetricsGrid.innerHTML = '';
  (adminDashboard.metrics || []).forEach((metric) => {
    const card = document.createElement('article');
    card.className = 'card admin-metric-card';
    card.innerHTML =
      '<span>' +
      metric.label +
      '</span>' +
      '<strong>' +
      metric.value +
      '</strong>' +
      '<small>' +
      (metric.delta || '') +
      '</small>';
    adminMetricsGrid.appendChild(card);
  });

  renderAdminSection('competency chart', () => {
    renderAdminCompetencyBarChart(adminDashboard.competency_average || []);
  });

  adminInsightsGrid.innerHTML = '';
  (adminDashboard.insights || []).forEach((item) => {
    const card = document.createElement('article');
    card.className = 'card card--inset admin-insight-card';
    card.innerHTML = '<strong>' + item.title + '</strong><p>' + item.description + '</p>';
    adminInsightsGrid.appendChild(card);
  });

  renderAdminSection('activity chart', () => {
    renderAdminActivityBarChart(adminDashboard);
  });
};

export const loadAdminDashboard = async (periodKey = state.adminPeriodKey || '30d') => {
  const response = await fetch('/users/admin/dashboard?period=' + encodeURIComponent(periodKey), {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить административный дашборд.');
  state.adminDashboard = data;
  state.adminPeriodKey = data.activity_period_key || periodKey;
  persistAssessmentContext();
};

export const openAdminDashboard = () => {
  state.activeArea = 'management';
  state.isAdmin = Boolean(state.canAdmin || state.isAdmin);
  setCurrentScreen('admin');
  persistAssessmentContext();
  syncUrlState('admin');
  hideAllPanels();
  adminPanel.classList.remove('hidden');
  renderAdminDashboard();
};

export const openAdminAssessmentDashboard = async () => {
  if (!state.pendingUser?.id) {
    return;
  }
  const { captureAdminOrganizationsDraft } = await import('./organizations.js');
  captureAdminOrganizationsDraft();
  const response = await fetch('/users/' + state.pendingUser.id + '/session-bootstrap', { credentials: 'same-origin' });
  const bootstrap = await readApiResponse(response, 'Не удалось открыть собственную оценку.');
  if (!bootstrap.is_admin || bootstrap.admin_dashboard?.is_superadmin) {
    throw new Error('Личная оценка доступна только администратору организации.');
  }
  state.pendingUser = bootstrap.user;
  state.dashboard = bootstrap.dashboard;
  state.adminDashboard = bootstrap.admin_dashboard || state.adminDashboard;
  const journey = await loadUserJourneyState({ allowAdmin: true });
  applyJourneyAssessmentContext(journey);
  state.canAdmin = true;
  state.activeArea = 'assessment';
  state.isAdmin = false;
  state.preparedAssessmentStartResponse = null;
  state.assessmentPreparationStatus = 'idle';
  state.assessmentPreparationProgressPercent = 0;
  persistAssessmentContext();
  if (journey?.next_action === 'wait_for_acquaintance_data') {
    const { openAcquaintanceWaiting } = await import('../../router.js');
    openAcquaintanceWaiting(journey.acquaintance?.readiness);
    return;
  }
  if (journey?.next_action === 'show_onboarding') {
    const { openOnboardingScreen } = await import('../../screen-loaders.js');
    await openOnboardingScreen({ currentStep: Number(journey.onboarding?.current_step || 0) });
    return;
  }
  if (journey?.next_action === 'complete_profile') {
    const { recoverProfileCompletionForAssessment } = await import('../profile-recovery.js');
    await recoverProfileCompletionForAssessment({ resumeAssessment: false });
    return;
  }
  if (journey?.next_action === 'show_dashboard') {
    const { loadDashboard } = await import('../../screen-loaders.js');
    (await loadDashboard()).openDashboard();
    return;
  }
  if (journey?.next_action === 'resume_assessment') {
    if (state.assessmentRuntimeKind === 'cycle' && state.productCycleId) {
      const { loadInterview } = await import('../../screen-loaders.js');
      (await loadInterview()).openInterview();
      return;
    }
    const { loadAiWelcome } = await import('../../screen-loaders.js');
    (await loadAiWelcome()).openPrechat();
    return;
  }
  if (['show_processing', 'show_assessment_error'].includes(journey?.next_action)) {
    const { loadProcessing } = await import('../../screen-loaders.js');
    (await loadProcessing()).openProcessing();
    return;
  }
  throw new Error('Не удалось определить актуальный этап собственной оценки.');
};
