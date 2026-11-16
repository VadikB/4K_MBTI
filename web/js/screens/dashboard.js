import { state, persistAssessmentContext, safeStorage, STORAGE_KEYS, setCurrentScreen } from '../state.js';
import {
  dashboardPanel, dashboardGreeting, dashboardUserName, dashboardUserRole, dashboardAvatar,
  currentAssessmentsTitle, currentAssessments, completedAssessments,
  dashboardRefreshStatus, dashboardRefreshButton,
} from '../dom.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { sanitizeDisplayRole, getSignupFirstName, buildInitials } from '../utils/format.js';
import { handleAssessmentEntryClick } from './interview.js';
import { readApiResponse } from '../api.js';
import { assessmentPositionText } from '../dashboard-presentation.js';

const DASHBOARD_REFRESH_INTERVAL_MS = 30000;
const DASHBOARD_RETRY_INTERVAL_MS = 60000;
let dashboardRefreshTimer = null;
let dashboardRefreshPending = false;

const scheduleDashboardRefresh = (delay = DASHBOARD_REFRESH_INTERVAL_MS) => {
  window.clearTimeout(dashboardRefreshTimer);
  dashboardRefreshTimer = window.setTimeout(() => {
    if (state.currentScreen === 'dashboard') void refreshDashboard();
  }, delay);
};

const refreshDashboard = async () => {
  if (dashboardRefreshPending || state.currentScreen !== 'dashboard' || !state.pendingUser?.id) return;
  dashboardRefreshPending = true;
  const ownerId = state.pendingUser.id;
  const identityEpoch = state.identityEpoch;
  const profileQuery = state.dashboard?.personalized_profile_id
    ? `?personalized_profile_id=${encodeURIComponent(state.dashboard.personalized_profile_id)}` : '';
  try {
    const response = await fetch(`/users/${encodeURIComponent(ownerId)}/session-bootstrap${profileQuery}`, {
      credentials: 'same-origin',
    });
    const payload = await readApiResponse(response, 'Не удалось обновить сведения');
    if (state.currentScreen !== 'dashboard' || state.identityEpoch !== identityEpoch || state.pendingUser?.id !== ownerId) return;
    const focusedAction = document.activeElement?.dataset?.dashboardAction || null;
    const focusedCycleId = document.activeElement?.dataset?.cycleId || null;
    state.dashboard = payload.dashboard || state.dashboard;
    persistAssessmentContext();
    renderDashboard();
    if (focusedAction) {
      const matchingButton = [...dashboardPanel.querySelectorAll('[data-dashboard-action]')].find((button) =>
        button.dataset.dashboardAction === focusedAction && button.dataset.cycleId === focusedCycleId);
      matchingButton?.focus({ preventScroll: true });
    }
    dashboardRefreshStatus.classList.add('hidden');
    scheduleDashboardRefresh();
  } catch (_error) {
    if (state.currentScreen === 'dashboard' && state.identityEpoch === identityEpoch && state.pendingUser?.id === ownerId) {
      dashboardRefreshStatus.classList.remove('hidden');
      scheduleDashboardRefresh(DASHBOARD_RETRY_INTERVAL_MS);
    }
  } finally {
    dashboardRefreshPending = false;
  }
};

dashboardRefreshButton?.addEventListener('click', () => void refreshDashboard());
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && state.currentScreen === 'dashboard') void refreshDashboard();
});

const formatDeadline = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const datePart = new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric', month: 'long', timeZone: 'Europe/Moscow',
  }).format(date);
  const timePart = new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Europe/Moscow',
  }).format(date);
  return `Завершить до ${datePart}, ${timePart} (МСК)`;
};

const performCardAction = async (card, event) => {
  if (card.cycle_id) {
    state.productCycleId = card.cycle_id;
    state.assessmentRuntimeKind = 'cycle';
    persistAssessmentContext();
  }
  if (card.action === 'open_report') {
    const { openReportScreen } = await import('../screen-loaders.js');
    await openReportScreen({ returnTarget: 'home', m8CycleId: card.cycle_id, m8ReportId: card.report_id });
    return;
  }
  if (card.action === 'open_processing') {
    const { openProcessingScreen } = await import('../screen-loaders.js');
    await openProcessingScreen();
    return;
  }
  if (['acquaintance', 'open_readiness'].includes(card.action)) {
    const { openOnboardingScreen } = await import('../screen-loaders.js');
    await openOnboardingScreen({ readOnlyEntry: true, expectedCycleId: card.cycle_id || null });
    return;
  }
  if (card.action === 'continue' && card.cycle_id) {
    const { loadInterview } = await import('../screen-loaders.js');
    const interview = await loadInterview();
    interview.openInterview(); // The saved return-flow still requires its explicit Continue.
    return;
  }
  await handleAssessmentEntryClick(event);
};

const buildCard = (card, { primaryEntry = false, history = false } = {}) => {
  const article = document.createElement('article');
  article.className = `card participant-assessment-card${history ? ' participant-assessment-card--history' : ''}`;
  article.dataset.cycleId = card.cycle_id || '';
  article.dataset.journeyState = card.journey_state || card.status;
  const main = document.createElement('div');
  main.className = 'participant-assessment-main';
  const top = document.createElement('div');
  top.className = 'participant-assessment-top';
  if (card.organization_name) {
    const organization = document.createElement('span');
    organization.className = 'participant-assessment-organization';
    organization.textContent = card.organization_name;
    top.appendChild(organization);
  }
  const status = document.createElement('span');
  status.className = 'participant-assessment-status';
  status.textContent = card.status_label;
  top.appendChild(status);
  main.appendChild(top);
  const title = document.createElement('h4');
  title.textContent = card.title;
  main.appendChild(title);
  const description = document.createElement('p');
  description.className = 'participant-assessment-description';
  description.textContent = card.description;
  main.appendChild(description);
  const metadata = document.createElement('dl');
  metadata.className = 'participant-assessment-metadata';
  const addMeta = (label, value) => {
    if (!value) return;
    const item = document.createElement('div');
    const term = document.createElement('dt'); term.textContent = label;
    const detail = document.createElement('dd'); detail.textContent = value;
    item.append(term, detail); metadata.append(item);
  };
  addMeta('Прохождение', assessmentPositionText(card));
  if (card.closed_at) {
    const date = new Date(card.closed_at);
    if (!Number.isNaN(date.getTime())) addMeta('Завершена', new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Moscow',
    }).format(date));
  } else addMeta('Срок оценки', formatDeadline(card.calendar_deadline));
  if (metadata.children.length) main.appendChild(metadata);
  article.appendChild(main);
  if (card.action && card.button_label) {
    const button = document.createElement('button');
    if (primaryEntry) button.id = 'assessment-action-button';
    button.type = 'button';
    button.className = `${history ? 'ghost-button' : 'primary-button'} participant-assessment-action`;
    button.dataset.dashboardAction = card.action;
    button.dataset.cycleId = card.cycle_id || '';
    button.textContent = card.button_label;
    button.addEventListener('click', (event) => void performCardAction(card, event));
    article.appendChild(button);
  }
  return article;
};

const renderCards = (container, cards, emptyTitle, emptyDescription) => {
  container.replaceChildren();
  if (cards.length) {
    cards.forEach((card, index) => container.appendChild(buildCard(card, {
      primaryEntry: container === currentAssessments && index === 0,
      history: container === completedAssessments,
    })));
    return;
  }
  const empty = document.createElement('div');
  empty.className = 'card participant-assessment-empty';
  const title = document.createElement('strong');
  title.textContent = emptyTitle;
  const description = document.createElement('p');
  description.textContent = emptyDescription;
  empty.append(title, description);
  container.appendChild(empty);
};

export const renderDashboard = () => {
  const dashboard = state.dashboard;
  if (!dashboard) return;
  const user = state.pendingUser;
  const position = sanitizeDisplayRole(user?.job_description || '');
  dashboardGreeting.textContent = 'Мои оценки';
  dashboardUserName.textContent = user
    ? getSignupFirstName(user.full_name, dashboard.greeting_name)
    : getSignupFirstName(dashboard.greeting_name);
  dashboardUserRole.textContent = position;
  dashboardUserRole.style.display = position ? '' : 'none';
  dashboardAvatar.textContent = buildInitials(user ? user.full_name : dashboard.greeting_name);
  const current = Array.isArray(dashboard.current_assessments) ? dashboard.current_assessments : [];
  const completed = Array.isArray(dashboard.completed_assessments) ? dashboard.completed_assessments : [];
  currentAssessmentsTitle.textContent = current.length > 1 ? 'Текущие оценки' : 'Текущая оценка';
  // Promote the latest closed Cycle into the main card only when no assignment is active.
  // It remains a single entry; technical Report revisions never become separate rows.
  const featured = current.length ? current : completed.slice(0, 1);
  const previous = current.length ? completed : completed.slice(1);
  renderCards(currentAssessments, featured, 'Пока нет назначенных оценок', 'Когда вам назначат оценку, она появится здесь');
  renderCards(completedAssessments, previous, 'Здесь появятся результаты ваших оценок', 'Завершённые оценки пока отсутствуют');
};

export const openDashboard = () => {
  setCurrentScreen('dashboard');
  persistAssessmentContext();
  syncUrlState('dashboard');
  hideAllPanels();
  renderDashboard();
  dashboardPanel.classList.remove('hidden');
  dashboardRefreshStatus.classList.add('hidden');
  scheduleDashboardRefresh();
};

export const hasIncompleteAssessment = () =>
  (state.dashboard?.current_assessments || []).some((card) => ['active', 'paused', 'interrupted'].includes(card.status));

export const hasAssessmentHistory = () => {
  const hasCycles = (state.dashboard?.completed_assessments || []).length > 0;
  const hasProfileSessions = Array.isArray(state.profileSummary?.sessions) && state.profileSummary.sessions.length > 0;
  return hasCycles || hasProfileSessions || safeStorage.getItem(STORAGE_KEYS.assessmentCompletedOnce) === '1';
};

export const hasCompletedAssessmentBefore = () =>
  hasAssessmentHistory() || Boolean(state.assessmentSessionId) ||
  safeStorage.getItem(STORAGE_KEYS.assessmentCompletedOnce) === '1';
