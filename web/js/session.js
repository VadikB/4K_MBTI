import { state, persistAssessmentContext, clearAssessmentContext } from './state.js';
import { advanceSessionGeneration, getSessionGeneration, readApiResponse } from './api.js';
import { isAdminUserPayload } from './utils/format.js';
import { resetChatScreen } from './screen-loaders.js';
import { returnToStart } from './router.js';
import { applyLogoutButtonPendingState, resetLogoutButtonsState } from './logout-ui.js';

const clearProfileDisplay = () => {
  document.getElementById('profile-avatar-image')?.removeAttribute('src');
  document.getElementById('profile-avatar-image')?.classList.add('hidden');
  document.getElementById('profile-avatar')?.replaceChildren();
  for (const id of ['profile-full-name', 'profile-email', 'profile-phone', 'profile-telegram', 'profile-job-description', 'profile-company-industry']) {
    const field = document.getElementById(id);
    if (field) field.value = '';
  }
  for (const id of ['profile-name', 'profile-role', 'profile-history-list', 'profile-save-status', 'chat-profile-confirmation', 'm8-report-skills', 'm8-report-recommendations', 'm8-report-metadata', 'm8-report-state', 'm8-report-coverage', 'm8-report-limitations', 'm8-report-recommendation-notices']) {
    document.getElementById(id)?.replaceChildren();
  }
  const download = document.getElementById('report-download-button');
  if (download) { delete download.dataset.m8ReportId; download.disabled = true; }
  const total = document.getElementById('profile-total-assessments');
  const average = document.getElementById('profile-average-score');
  if (total) total.textContent = '0';
  if (average) average.textContent = '0%';
};

const wait = (ms) =>
  new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });

const postLogoutWithTimeout = async (timeoutMs = 900) => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    await fetch('/users/session/logout', {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      signal: controller.signal,
    });
  } catch (_error) {
    // ignore logout network issues and still clear local state
  } finally {
    window.clearTimeout(timeoutId);
  }
};

export const isMissingUserError = (error) => {
  const message = String(error?.message || '').toLowerCase();
  return message.includes('user not found') || message.includes('пользователь не найден');
};

export const resetStaleUserState = async ({ advance = true, broadcast = true } = {}) => {
  const recoveryGeneration = advance
    ? advanceSessionGeneration({ broadcast })
    : getSessionGeneration();
  clearAssessmentContext();
  clearProfileDisplay();
  state.sessionId = null;
  state.pendingUser = null;
  state.dashboard = null;
  state.isAdmin = false;
  state.adminDashboard = null;
  state.pendingAgentMessage = null;
  state.pendingRoleOptions = [];
  state.pendingNoChangesQuickReply = false;
  state.assessmentSessionId = null;
  state.assessmentSessionCode = null;
  state.assessmentTotalCases = 0;
  returnToStart();
  // A late 401 can belong to another tab's old session. Never revoke the
  // current shared-cookie session here; explicit logout owns that operation.
  try {
    await resetChatScreen({ shouldReset: () => getSessionGeneration() === recoveryGeneration });
  } catch (_error) {
    // Expired sessions must still return to auth if lazy screen cleanup fails.
  }
};

const selectedProfileQuery = () => state.dashboard?.personalized_profile_id
  ? '?personalized_profile_id=' + encodeURIComponent(state.dashboard.personalized_profile_id) : '';

export const restoreServerSession = async () => {
  const response = await fetch('/users/session/restore' + selectedProfileQuery(), {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось восстановить пользовательскую сессию.');
  if (!data.authenticated || !data.user) {
    return false;
  }
  if (state.pendingUser?.id !== data.user.id) { clearAssessmentContext(); clearProfileDisplay(); }
  advanceSessionGeneration({ broadcast: false });
  state.pendingUser = data.user;
  state.dashboard = data.dashboard || null;
  state.isAdmin = isAdminUserPayload(data.user, Boolean(data.is_admin));
  state.adminDashboard = data.admin_dashboard || null;
  if (state.isAdmin) {
    state.sessionId = null;
    state.pendingAgentMessage = null;
    state.pendingRoleOptions = [];
    state.pendingNoChangesQuickReply = false;
    state.currentScreen = 'admin';
  } else if (!state.currentScreen || state.currentScreen === 'auth') {
    state.currentScreen = 'auth-complete';
  }
  persistAssessmentContext();
  return true;
};

export const restoreLocalUserSession = async () => {
  if (!state.pendingUser?.id) {
    return false;
  }

  try {
    const response = await fetch('/users/' + state.pendingUser.id + '/session-bootstrap' + selectedProfileQuery(), {
      credentials: 'same-origin',
    });
    const data = await readApiResponse(response, 'Не удалось восстановить локальную пользовательскую сессию.');
    if (state.pendingUser?.id !== data.user.id) { clearAssessmentContext(); clearProfileDisplay(); }
    advanceSessionGeneration({ broadcast: false });
    state.pendingUser = data.user;
    state.dashboard = data.dashboard;
    state.isAdmin = isAdminUserPayload(data.user, Boolean(data.is_admin));
    state.adminDashboard = data.admin_dashboard || null;
    if (state.isAdmin) {
      state.sessionId = null;
      state.pendingAgentMessage = null;
      state.pendingRoleOptions = [];
      state.pendingNoChangesQuickReply = false;
      state.currentScreen = 'admin';
    } else if (!state.currentScreen || state.currentScreen === 'auth') {
      state.currentScreen = 'auth-complete';
    }
    persistAssessmentContext();
    return true;
  } catch (error) {
    if (isMissingUserError(error)) {
      await resetStaleUserState();
      return false;
    }
    throw error;
  }
};

export const loadUserJourneyState = async () => {
  if (!state.pendingUser?.id || state.isAdmin) {
    return null;
  }
  const response = await fetch('/users/' + state.pendingUser.id + '/journey-state' + selectedProfileQuery(), {
    credentials: 'same-origin',
  });
  return readApiResponse(response, 'Не удалось определить следующий шаг пользователя.');
};

export const logoutAndReturnToStart = async (trigger = null) => {
  advanceSessionGeneration();
  const restoreButton = applyLogoutButtonPendingState(trigger);
  const startedAt = Date.now();
  try {
    clearAssessmentContext();
    clearProfileDisplay();
    await postLogoutWithTimeout();
    const elapsed = Date.now() - startedAt;
    if (elapsed < 250) {
      await wait(250 - elapsed);
    }
    clearAssessmentContext();
    try {
      await resetChatScreen();
    } catch (_error) {
      // The user must still be able to return to auth even if lazy screen reset fails.
    }
    returnToStart();
  } catch (_error) {
    restoreButton();
    throw _error;
  } finally {
    resetLogoutButtonsState();
  }
};

// Another tab can replace the shared session cookie without changing this tab's memory.
let checkingVisibleOwner = false;
const reconcileVisibleOwner = async () => {
  if (checkingVisibleOwner || !state.pendingUser?.id || !['reports','report','profile'].includes(state.currentScreen)) return;
  checkingVisibleOwner = true;
  const ownerId = state.pendingUser.id; const epoch = state.identityEpoch;
  try {
    const response = await fetch('/users/session/restore', {credentials:'same-origin', cache:'no-store'});
    const data = await response.json();
    if (state.identityEpoch !== epoch) return;
    if (!response.ok || !data.authenticated || data.user?.id !== ownerId) {
      clearAssessmentContext(); clearProfileDisplay(); returnToStart();
    }
  } catch (_) {
    // Fail closed locally; never log out a different tab's current server session.
    if (state.identityEpoch === epoch) { clearAssessmentContext(); clearProfileDisplay(); returnToStart(); }
  } finally { checkingVisibleOwner = false; }
};
window.addEventListener('focus', () => { void reconcileVisibleOwner(); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) void reconcileVisibleOwner(); });
