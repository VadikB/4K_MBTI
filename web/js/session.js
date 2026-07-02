import { state, persistAssessmentContext, clearAssessmentContext } from './state.js';
import { readApiResponse } from './api.js';
import { isAdminUserPayload } from './utils/format.js';
import { resetChatScreen } from './screen-loaders.js';
import { returnToStart } from './router.js';
import { applyLogoutButtonPendingState } from './logout-ui.js';

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

export const resetStaleUserState = async () => {
  try {
    await fetch('/users/session/logout', {
      method: 'POST',
      credentials: 'same-origin',
    });
  } catch (_error) {
    // ignore cleanup network issues
  }
  clearAssessmentContext();
  await resetChatScreen();
  window.history.replaceState({}, '', '/?ui=' + Date.now());
};

export const restoreServerSession = async () => {
  const response = await fetch('/users/session/restore', {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось восстановить пользовательскую сессию.');
  if (!data.authenticated || !data.user) {
    return false;
  }
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
    state.currentScreen = state.dashboard ? 'dashboard' : 'chat';
  }
  persistAssessmentContext();
  return true;
};

export const restoreLocalUserSession = async () => {
  if (!state.pendingUser?.id) {
    return false;
  }

  try {
    const response = await fetch('/users/' + state.pendingUser.id + '/session-bootstrap', {
      credentials: 'same-origin',
    });
    const data = await readApiResponse(response, 'Не удалось восстановить локальную пользовательскую сессию.');
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
      state.currentScreen = 'dashboard';
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

export const logoutAndReturnToStart = async (trigger = null) => {
  const restoreButton = applyLogoutButtonPendingState(trigger);
  const startedAt = Date.now();
  await postLogoutWithTimeout();
  try {
    const elapsed = Date.now() - startedAt;
    if (elapsed < 250) {
      await wait(250 - elapsed);
    }
    clearAssessmentContext();
    await resetChatScreen();
    returnToStart();
  } catch (_error) {
    restoreButton();
    throw _error;
  }
};
