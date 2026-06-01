import { state, persistAssessmentContext, safeStorage, STORAGE_KEYS, setCurrentScreen } from '../state.js';
import {
  dashboardPanel,
  dashboardGreeting,
  dashboardUserName,
  dashboardUserRole,
  dashboardAvatar,
  assessmentTitle,
  assessmentDescription,
  assessmentStatusLabel,
  assessmentCasesLabel,
  assessmentProgressBar,
  assessmentActionButton,
  availableAssessments,
  reportsList,
} from '../dom.js';
import { staticAssessments } from '../config.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { sanitizeDisplayRole, getSignupFirstName, buildInitials, escapeHtml } from '../utils/format.js';
import {
  canReusePreparedAssessment,
  renderAssessmentPreparationState,
  beginAssessmentPreparation,
} from './assessment.js';
import { handleAssessmentEntryClick } from './interview.js';
import { openReports } from './reports.js';

export const renderDashboard = () => {
  const dashboard = state.dashboard;
  if (!dashboard) {
    return;
  }

  const user = state.pendingUser;
  const position = sanitizeDisplayRole(user && user.job_description ? user.job_description : '');
  const progressText =
    dashboard.active_assessment.progress_percent >= 100
      ? 'Завершено ' + dashboard.active_assessment.progress_percent + '%'
      : 'Завершено ' + dashboard.active_assessment.progress_percent + '%';

  dashboardGreeting.textContent = 'Добро пожаловать, ' + (user?.full_name || dashboard.greeting_name);
  dashboardUserName.textContent = user
    ? getSignupFirstName(user.full_name, dashboard.greeting_name)
    : getSignupFirstName(dashboard.greeting_name);
  dashboardUserRole.textContent = position;
  dashboardUserRole.style.display = position ? '' : 'none';
  dashboardAvatar.textContent = buildInitials(user ? user.full_name : dashboard.greeting_name);
  assessmentTitle.textContent =
    dashboard.active_assessment.code === 'competencies_4k' ? 'Компетенции 4К' : dashboard.active_assessment.title;
  assessmentDescription.textContent = dashboard.active_assessment.description;
  assessmentStatusLabel.textContent = progressText;
  assessmentCasesLabel.textContent =
    dashboard.active_assessment.completed_cases + ' из ' + dashboard.active_assessment.total_cases + ' кейсов';
  assessmentProgressBar.style.width = dashboard.active_assessment.progress_percent + '%';
  assessmentActionButton.textContent = canReusePreparedAssessment()
    ? 'Перейти к кейсам'
    : dashboard.active_assessment.button_label;
  renderAssessmentPreparationState();

  availableAssessments.innerHTML = '';
  dashboard.available_assessments.forEach((item, index) => {
    const card = document.createElement('article');
    card.className = 'card assessment-mini-card';
    const actionMarkup =
      index === 0
        ? '<button id="dashboard-mini-start" class="mini-card-action-button" type="button">' +
          (canReusePreparedAssessment() ? 'К кейсам' : 'Начать') +
          '</button>' +
          '<div id="dashboard-mini-preparing" class="preparing-hero preparing-hero--mini hidden" aria-live="polite">' +
          '<div id="dashboard-mini-ring" class="preparing-hero-row" style="--progress: 0%;">' +
          '<span class="preparing-hero-pulse" aria-hidden="true"></span>' +
          '<span id="dashboard-mini-percent" class="preparing-hero-value">0%</span>' +
          '</div>' +
          '</div>'
        : '<span>' + escapeHtml(item.status) + '</span>';
    card.innerHTML =
      '<div class="mini-card-icon"><img src="/web/assets/icons/4k-icon.svg" alt="" aria-hidden="true"></div>' +
      '<h3>' +
      escapeHtml(item.title) +
      '</h3>' +
      '<p>' +
      escapeHtml(item.description) +
      '</p>' +
      '<div class="mini-card-meta"><span>' +
      escapeHtml(item.duration_minutes) +
      ' минут</span>' +
      actionMarkup +
      '</div>';
    if (index === 0) {
      const actionButton = card.querySelector('.mini-card-action-button');
      actionButton.addEventListener('click', handleAssessmentEntryClick);
    }
    availableAssessments.appendChild(card);
  });
  renderAssessmentPreparationState();

  staticAssessments.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'card is-placeholder assessment-mini-card muted-card ' + item.tone;
    card.innerHTML =
      '<div class="mini-card-icon muted-icon"><img src="/web/assets/icons/4k-icon.svg" alt="" aria-hidden="true"></div>' +
      '<h3>' +
      item.title +
      '</h3>' +
      '<p>' +
      item.description +
      '</p>' +
      '<div class="mini-card-meta"><span>' +
      item.duration +
      '</span><span>Скоро</span></div>';
    availableAssessments.appendChild(card);
  });

  reportsList.innerHTML = '';
  const reportsCount = Number.isFinite(Number(dashboard.reports_total))
    ? Number(dashboard.reports_total)
    : Array.isArray(dashboard.reports)
      ? dashboard.reports.length
      : 0;
  const reportsSummary = document.createElement('button');
  reportsSummary.type = 'button';
  reportsSummary.className = 'reports-summary-button';
  reportsSummary.innerHTML =
    '<div class="reports-summary-copy">' +
    '<span class="reports-summary-label">Всего отчетов по оценке</span>' +
    '<strong class="reports-summary-count">' +
    reportsCount +
    '</strong>' +
    '</div>' +
    '<span class="reports-summary-action">Перейти к отчетам</span>';
  reportsSummary.addEventListener('click', () => {
    void openReports();
  });
  reportsList.appendChild(reportsSummary);
};

export const openDashboard = () => {
  setCurrentScreen('dashboard');
  persistAssessmentContext();
  syncUrlState('dashboard');
  hideAllPanels();
  renderDashboard();
  dashboardPanel.classList.remove('hidden');
  void beginAssessmentPreparation();
};

export const hasIncompleteAssessment = () => {
  if (!state.dashboard || !state.dashboard.active_assessment) {
    return false;
  }
  const progress = Number(state.dashboard.active_assessment.progress_percent || 0);
  return progress > 0 && progress < 100;
};

export const hasAssessmentHistory = () => {
  const dashboardProgress = Number(state.dashboard?.active_assessment?.progress_percent || 0);
  const dashboardCompletedCases = Number(state.dashboard?.active_assessment?.completed_cases || 0);
  const hasReports = Array.isArray(state.dashboard?.reports) && state.dashboard.reports.length > 0;
  const hasProfileSessions = Array.isArray(state.profileSummary?.sessions) && state.profileSummary.sessions.length > 0;
  const hasCompletedAssessmentFlag = safeStorage.getItem(STORAGE_KEYS.assessmentCompletedOnce) === '1';

  return dashboardProgress > 0 || dashboardCompletedCases > 0 || hasReports || hasProfileSessions || hasCompletedAssessmentFlag;
};

export const hasCompletedAssessmentBefore = () =>
  hasAssessmentHistory() ||
  Boolean(state.assessmentSessionId) ||
  safeStorage.getItem(STORAGE_KEYS.assessmentCompletedOnce) === '1';
