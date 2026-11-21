import { renderPreparation } from '../preparation-status.js';
import { state, persistAssessmentContext, safeStorage, STORAGE_KEYS, setCurrentScreen } from '../state.js';
import {
  dashboardPanel, dashboardGreeting,
  currentAssessmentsTitle, currentAssessments, completedAssessments,
  dashboardRefreshStatus, dashboardRefreshButton,
} from '../dom.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { showParticipantDialog } from '../components/participant-dialog.js';
import { initAppHeader } from '../components/app-header.js';
import { handleAssessmentEntryClick } from './interview.js';
import { readApiResponse } from '../api.js';
import { readParticipantAppeals, renderParticipantAppeals } from '../components/participant-appeals.js';
import { assessmentMetadata, formatAssessmentDate } from '../dashboard-presentation.js';

const DASHBOARD_REFRESH_INTERVAL_MS = 30000;
const DASHBOARD_RETRY_INTERVAL_MS = 60000;
let dashboardRefreshTimer = null;
let dashboardRefreshPending = false;
let appealsReadGeneration = 0;
const appealSnapshots = new WeakMap();
const header = initAppHeader({ root: dashboardPanel.querySelector('[data-app-header]'), onHome: () => openDashboard() });

const contactButton = dashboardPanel.querySelector('#dashboard-contact-button');

contactButton?.addEventListener('click', () => {
  const contact = state.dashboard?.administrator_contact;
  const body = document.createElement(contact ? 'dl' : 'p');
  if (contact) {
    body.className = 'participant-contact-details';
    const email = document.createElement('a');
    email.href = 'mailto:' + encodeURIComponent(contact.email).replace('%40', '@');
    email.textContent = contact.email;
    for (const [label, value] of [
      ['Организация', contact.organization_name], ['Администратор', contact.name], ['Эл. почта', email],
    ]) {
      if (!value) continue;
      const term = document.createElement('dt'); term.textContent = label;
      const detail = document.createElement('dd'); detail.append(value);
      body.append(term, detail);
    }
  } else {
    body.textContent = 'Контакт администратора пока не указан.';
  }
  void showParticipantDialog(contactButton, { title: contactButton.textContent, body });
});

const refreshAppeals = async () => {
  const ownerId = state.pendingUser?.id;
  if (!ownerId) return;
  const epoch = state.identityEpoch;
  const generation = ++appealsReadGeneration;
  let section = dashboardPanel.querySelector('[data-participant-appeals]');
  if (section && section.dataset.ownerId !== String(ownerId)) { section.remove(); section = null; }
  try {
    const items = await readParticipantAppeals(ownerId);
    if (generation !== appealsReadGeneration || epoch !== state.identityEpoch ||
        state.pendingUser?.id !== ownerId || state.currentScreen !== 'dashboard') return;
    if (!items.length) { section?.remove(); return; }
    if (!section) {
      section = document.createElement('section');
      section.dataset.participantAppeals = '';
      section.dataset.ownerId = String(ownerId);
      dashboardPanel.querySelector('#dashboard-appeals').append(section);
    }
    const snapshot = JSON.stringify(items);
    if (appealSnapshots.get(section) === snapshot) return;
    renderParticipantAppeals(section, items);
    appealSnapshots.set(section, snapshot);
  } catch { /* Keep the last confirmed projection for this owner until a successful refresh. */ }
};

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
    state.dashboard = payload.dashboard || state.dashboard;
    persistAssessmentContext();
    renderDashboard();
    void refreshAppeals();
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

dashboardPanel.querySelector('#dashboard-manual-refresh')?.addEventListener('click', () => void refreshDashboard());
dashboardRefreshButton?.addEventListener('click', () => void refreshDashboard());
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && state.currentScreen === 'dashboard') void refreshDashboard();
});

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
    const ownerId = state.pendingUser?.id;
    const identityEpoch = state.identityEpoch;
    const { loadProcessing } = await import('../screen-loaders.js');
    const module = await loadProcessing();
    if (state.currentScreen === 'dashboard' && state.pendingUser?.id === ownerId
        && state.identityEpoch === identityEpoch && state.productCycleId === card.cycle_id) {
      module.openProcessing({ cycleId: card.cycle_id });
    }
    return;
  }
  if (card.action === 'open_legacy_acquaintance') {
    // Explicit server-authorized historical route, excluded for managed assignments.
    const { openOnboardingScreen } = await import('../screen-loaders.js');
    await openOnboardingScreen();
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

const appendCardAction = (article, card, { primaryEntry, history }) => {
  if ((!card.action || !card.button_label) && (history || !card.rules)) return;
  const actions = document.createElement('div');
  actions.className = 'participant-assessment-actions';
  const button = document.createElement('button');
  if (primaryEntry) button.id = 'assessment-action-button';
  button.type = 'button';
  const secondary = history || card.action === 'open_processing';
  button.className = `${secondary ? 'ghost-button' : 'primary-button'} participant-assessment-action`;
  button.dataset.dashboardAction = card.action;
  button.dataset.cycleId = card.cycle_id || '';
  button.textContent = history && card.action === 'open_report' ? 'Открыть отчёт' : card.button_label;
  button.onclick = (event) => void performCardAction(card, event);
  if (history) {
    const status = document.createElement('span');
    status.className = 'participant-assessment-status';
    status.textContent = card.status_label;
    actions.append(status);
  }
  if (card.action && card.button_label) actions.appendChild(button);
  if (!history && card.rules) {
    const rules = document.createElement('button');
    rules.className = 'text-link';
    rules.type = 'button';
    rules.textContent = 'Условия прохождения';
    rules.onclick = () => {
      const { time_budget_seconds: budget, calendar_window_seconds: windowSeconds, participant_notice: notice } = card.rules;
      const body = document.createElement('div');
      for (const text of [
        budget > 0 ? `На выполнение оценки — ${Math.ceil(budget / 60)} мин.` : '',
        windowSeconds > 0 ? `Завершите оценку в течение ${windowSeconds / 3600} ч. после её начала.` : '',
        notice,
      ].filter(Boolean)) {
        const line = document.createElement('p'); line.textContent = text; body.append(line);
      }
      void showParticipantDialog(rules, { title: rules.textContent, body });
    };
    actions.append(rules);
  }
  article.appendChild(actions);
};

const buildCard = (card, { primaryEntry = false, history = false } = {}) => {
  const article = document.createElement('article');
  article.className = history ? 'participant-assessment-card participant-assessment-card--history'
    : 'card participant-assessment-card';
  article.dataset.cycleId = card.cycle_id || '';
  article.dataset.journeyState = card.journey_state || card.status;
  const main = document.createElement('div');
  main.className = 'participant-assessment-main';
  if (history) {
    const title = document.createElement('h3');
    title.className = 'participant-assessment-title';
    title.textContent = card.title;
    const details = document.createElement('p');
    details.className = 'participant-assessment-history-details';
    details.textContent = [formatAssessmentDate(card.closed_at), card.organization_name].filter(Boolean).join(' · ');
    main.append(title, details);
  } else {
    const top = document.createElement('div');
    top.className = 'participant-assessment-top';
    const label = document.createElement('span');
    label.className = 'participant-assessment-label';
    label.textContent = 'Текущая оценка';
    top.append(label);
    const status = document.createElement('span');
    status.className = 'participant-assessment-status';
    status.textContent = card.status_label;
    top.appendChild(status);
    const title = document.createElement('h2');
    title.className = 'participant-assessment-title';
    title.textContent = card.title;
    const description = document.createElement('p');
    description.className = 'participant-assessment-description';
    description.textContent = card.description;
    main.append(top, title);
    if (card.organization_name) {
      const organization = document.createElement('p');
      organization.className = 'participant-assessment-organization';
      organization.textContent = card.organization_name;
      main.append(organization);
    }
    main.append(description);
    const metadata = document.createElement('dl');
    metadata.className = 'participant-assessment-metadata';
    assessmentMetadata(card).filter(({ label }) => label !== 'Организация').forEach(({ label, value }) => {
      const item = document.createElement('div');
      const term = document.createElement('dt'); term.textContent = label;
      const detail = document.createElement('dd'); detail.textContent = value;
      item.append(term, detail); metadata.appendChild(item);
    });
    if (metadata.children.length) main.appendChild(metadata);
    const { completed_positions: done, planned_total: total } = card;
    if (Number.isInteger(done) && Number.isInteger(total) && total > 0 && done >= 0 && done <= total) {
      const label = document.createElement('div');
      label.className = 'participant-assessment-progress';
      const text = document.createElement('span'); text.textContent = 'Завершено ситуаций';
      const count = document.createElement('strong'); count.textContent = `${done} из ${total}`;
      const meter = document.createElement('progress');
      meter.setAttribute('aria-label', text.textContent);
      meter.max = total;
      meter.value = done;
      label.append(text, count, meter);
      main.append(label);
    }
  }
  if (card.preparation) renderPreparation(main, card.preparation, { compact: true });
  article.appendChild(main);
  appendCardAction(article, card, { primaryEntry, history });
  return article;
};

const cardModels = new WeakMap();
let renderedOwner = null;
let renderedEpoch = null;
const cardBody = (card) => JSON.stringify({ ...card, preparation: null, action: null, button_label: null });
const rememberCard = (article, card, options) => cardModels.set(article, {
  body: cardBody(card), history: options.history, statusLabel: card.status_label, rules: JSON.stringify(card.rules),
  preparation: card.preparation && { ...card.preparation },
});
const updateCard = (article, card, options) => {
  const previous = cardModels.get(article);
  const main = article.querySelector('.participant-assessment-main');
  let preparation = main.querySelector('[data-preparation-status]');
  // Keep the actual disclosure, selection and controls attached during a read.
  if (previous.body !== cardBody(card) || previous.history !== options.history) {
    const next = buildCard({ ...card, preparation: null, action: null }, options);
    for (const child of [...main.children]) if (child !== preparation) child.remove();
    for (const child of [...next.querySelector('.participant-assessment-main').children]) main.insertBefore(child, preparation);
  }
  article.className = options.history ? 'participant-assessment-card participant-assessment-card--history' : 'card participant-assessment-card';
  article.dataset.journeyState = card.journey_state || card.status;
  if (preparation && (!card.preparation || !card.preparation.reference
      || preparation.dataset.preparationReferenceId !== card.preparation.reference
      || previous.preparation?.operation_id !== card.preparation.operation_id
      || previous.preparation?.kind !== card.preparation.kind)) {
    preparation.remove(); preparation = null;
  }
  if (card.preparation) renderPreparation(main, card.preparation, { compact: true });
  const actions = article.querySelector('.participant-assessment-actions');
  const button = actions?.querySelector('button');
  if (button && card.action && card.button_label && button.dataset.dashboardAction === card.action
      && previous.statusLabel === card.status_label && previous.history === options.history
      && previous.rules === JSON.stringify(card.rules)) {
    button.id = options.primaryEntry ? 'assessment-action-button' : '';
    button.textContent = options.history && card.action === 'open_report' ? 'Открыть отчёт' : card.button_label;
    button.className = `${options.history || card.action === 'open_processing' ? 'ghost-button' : 'primary-button'} participant-assessment-action`;
    button.onclick = (event) => void performCardAction(card, event);
  } else {
    actions?.remove(); appendCardAction(article, card, options);
  }
  rememberCard(article, card, options);
  return article;
};

const renderCards = (container, cards, emptyTitle, emptyDescription, reusable) => {
  if (cards.length) {
    const nodes = cards.map((card, index) => {
      const options = {
        primaryEntry: container === currentAssessments && index === 0,
        history: container === completedAssessments,
      };
      const existing = card.cycle_id && reusable.get(card.cycle_id);
      if (existing) { reusable.delete(card.cycle_id); return updateCard(existing, card, options); }
      const article = buildCard(card, options); rememberCard(article, card, options); return article;
    });
    for (const child of [...container.children]) if (!nodes.includes(child)) child.remove();
    nodes.forEach((node, index) => {
      const before = container.children[index] || null;
      if (before !== node) {
        // moveBefore preserves focus/selection when the platform supports it.
        if (container.moveBefore && node.isConnected) container.moveBefore(node, before);
        else container.insertBefore(node, before);
      }
    });
    return;
  }
  container.replaceChildren();
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
  const sameOwner = renderedOwner === user?.id && renderedEpoch === state.identityEpoch;
  const reusable = new Map(sameOwner ? [...dashboardPanel.querySelectorAll('article[data-cycle-id]')]
    .filter(node => node.dataset.cycleId).map(node => [node.dataset.cycleId, node]) : []);
  if (!sameOwner) dashboardPanel.querySelector('#dashboard-appeals')?.replaceChildren();
  renderedOwner = user?.id; renderedEpoch = state.identityEpoch;
  // Capture at application time, after the request: the user's latest focus wins.
  const focused = document.activeElement;
  const focusedCard = focused?.closest?.('article[data-cycle-id]');
  const cycleId = sameOwner && focusedCard?.dataset.cycleId;
  const wasSummary = focused?.tagName === 'SUMMARY';
  const wasCopy = focused?.hasAttribute?.('data-preparation-copy');
  const wasAction = focused?.hasAttribute?.('data-dashboard-action');
  dashboardGreeting.textContent = 'Мои оценки';
  header.updateUser(user);
  const current = Array.isArray(dashboard.current_assessments) ? dashboard.current_assessments : [];
  const completed = Array.isArray(dashboard.completed_assessments) ? dashboard.completed_assessments : [];
  currentAssessmentsTitle.textContent = current.length > 1 ? 'Текущие оценки' : 'Текущая оценка';
  renderCards(currentAssessments, current, 'Пока нет назначенных оценок', 'Когда вам назначат оценку, она появится здесь', reusable);
  renderCards(completedAssessments, completed, 'Здесь появятся результаты ваших оценок', 'Завершённые оценки пока отсутствуют', reusable);
  if (cycleId && (wasSummary || wasCopy || wasAction)
      && (!focused.isConnected || (document.activeElement === document.body && focused !== document.activeElement))) {
    const card = [...dashboardPanel.querySelectorAll('article[data-cycle-id]')].find(node => node.dataset.cycleId === cycleId);
    const target = (focused.isConnected ? focused : null)
      || (wasSummary || wasCopy ? card?.querySelector('summary') : null)
      || card?.querySelector('[data-dashboard-action]') || card?.querySelector('.participant-assessment-title')
      || currentAssessmentsTitle;
    if (!['SUMMARY', 'BUTTON'].includes(target.tagName)) target.tabIndex = -1;
    target.focus({ preventScroll: true });
  }
};

export const openDashboard = () => {
  setCurrentScreen('dashboard');
  persistAssessmentContext();
  syncUrlState('dashboard');
  hideAllPanels();
  renderDashboard();
  void refreshAppeals();
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
