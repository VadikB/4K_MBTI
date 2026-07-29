import { state, persistAssessmentContext } from '../state.js';
import {
  assessmentPreparing,
  assessmentActionButton,
  assessmentStatusLabel,
  assessmentProgressBar,
  assessmentPreparingPercent,
  welcomeAssessmentPreparing,
  startFirstAssessmentButton,
  welcomeAssessmentTitle,
  welcomeAssessmentText,
  welcomeAssessmentRing,
  welcomeAssessmentPercent,
  libraryAssessmentPreparing,
  libraryStartButton,
  libraryAssessmentRing,
  libraryAssessmentPercent,
  prechatStartButton,
  prechatAssessmentPreparing,
  prechatAssessmentTitle,
  prechatAssessmentText,
  prechatAssessmentRing,
  prechatAssessmentPercent,
} from '../dom.js';
import { createOperationId, readApiResponse } from '../api.js';
import { hasIncompleteAssessment } from './dashboard.js';
import { renderAiWelcomeState } from './ai-welcome.js';
import { renderDashboard } from './dashboard.js';
import { recoverProfileCompletionForAssessment, shouldRecoverProfileOnAssessmentError } from './profile-recovery.js';

export const stopAssessmentPreparationPolling = () => {
  if (state.assessmentPreparationPollId) {
    window.clearInterval(state.assessmentPreparationPollId);
    state.assessmentPreparationPollId = null;
  }
};

export const resetAssessmentPreparationState = () => {
  stopAssessmentPreparationPolling();
  state.assessmentPreparationOperationId = null;
  state.preparedAssessmentStartResponse = null;
  state.assessmentPreparationStatus = 'idle';
  state.assessmentPreparationProgressPercent = 0;
  state.assessmentPreparationTitle = '';
  state.assessmentPreparationMessage = '';
};

export const canReusePreparedAssessment = () => {
  if (hasIncompleteAssessment()) {
    return true;
  }
  return Boolean(state.preparedAssessmentStartResponse);
};

export const isAssessmentPreparing = () => state.assessmentPreparationStatus === 'preparing';

export const updatePreparingRing = (ring, percentNode, progressPercent) => {
  if (!ring || !percentNode) {
    return;
  }
  const normalized = Math.max(0, Math.min(100, Number(progressPercent || 0)));
  ring.style.setProperty('--progress', normalized + '%');
  percentNode.textContent = normalized + '%';
};

export const renderAssessmentPreparationState = () => {
  const status = state.assessmentPreparationStatus;
  const progressPercent = Math.max(0, Math.min(100, Number(state.assessmentPreparationProgressPercent || 0)));
  const title = state.assessmentPreparationTitle || 'Подготавливаем кейсы';
  const message = state.assessmentPreparationMessage || 'Система собирает персонализированный набор кейсов.';
  const ready = canReusePreparedAssessment();
  const failed = status === 'failed';
  const preparing = status === 'preparing';
  const backendLabel = String(state.dashboard?.active_assessment?.button_label || '').toLowerCase();
  const shouldRepeat = !hasIncompleteAssessment() && (Boolean(state.dashboard?.completed_assessments?.length) || backendLabel.includes('снова'));
  const welcomeDefaultLabel = shouldRepeat ? 'Пройти ассессмент снова' : 'Начать первый ассессмент';
  const libraryDefaultLabel = shouldRepeat ? 'Снова' : 'Начать';

  if (assessmentPreparing) {
    assessmentPreparing.classList.toggle('hidden', !preparing);
  }
  if (assessmentActionButton) {
    assessmentActionButton.classList.toggle('hidden', preparing);
    assessmentActionButton.disabled = preparing;
    assessmentActionButton.textContent = ready
      ? 'Перейти к кейсам'
      : failed
        ? 'Попробовать снова'
        : state.dashboard?.active_assessment?.button_label || 'Начать';
  }
  if (ready && assessmentStatusLabel) {
    assessmentStatusLabel.textContent = title;
  }
  if (ready && assessmentProgressBar) {
    assessmentProgressBar.style.width = progressPercent + '%';
  }
  updatePreparingRing(assessmentPreparing, assessmentPreparingPercent, preparing ? progressPercent : 0);

  if (welcomeAssessmentPreparing) {
    welcomeAssessmentPreparing.classList.toggle('hidden', !preparing);
  }
  if (startFirstAssessmentButton) {
    startFirstAssessmentButton.classList.toggle('hidden', preparing);
    startFirstAssessmentButton.disabled = preparing;
    const welcomeButtonLabel = ready ? 'Перейти к кейсам' : failed ? 'Попробовать снова' : welcomeDefaultLabel;
    startFirstAssessmentButton.innerHTML =
      '<span>' +
      welcomeButtonLabel +
      '</span><img class="button-arrow" src="/web/assets/icons/forward-arrow-white-icon.svg" alt="" aria-hidden="true">';
  }
  if (welcomeAssessmentTitle) {
    welcomeAssessmentTitle.textContent = title;
  }
  if (welcomeAssessmentText) {
    welcomeAssessmentText.textContent = message;
  }
  updatePreparingRing(welcomeAssessmentRing, welcomeAssessmentPercent, preparing ? progressPercent : 0);

  if (libraryAssessmentPreparing) {
    libraryAssessmentPreparing.classList.toggle('hidden', !preparing);
  }
  if (libraryStartButton) {
    libraryStartButton.classList.toggle('hidden', preparing);
    libraryStartButton.disabled = preparing;
    libraryStartButton.textContent = ready ? 'К кейсам' : failed ? 'Попробовать снова' : libraryDefaultLabel;
  }
  updatePreparingRing(libraryAssessmentRing, libraryAssessmentPercent, preparing ? progressPercent : 0);

  const dashboardMiniStart = document.getElementById('dashboard-mini-start');
  const dashboardMiniPreparing = document.getElementById('dashboard-mini-preparing');
  const dashboardMiniRing = document.getElementById('dashboard-mini-ring');
  const dashboardMiniPercent = document.getElementById('dashboard-mini-percent');
  if (dashboardMiniPreparing) {
    dashboardMiniPreparing.classList.toggle('hidden', !preparing);
  }
  if (dashboardMiniStart) {
    dashboardMiniStart.classList.toggle('hidden', preparing);
    dashboardMiniStart.disabled = preparing;
    dashboardMiniStart.textContent = ready ? 'К кейсам' : failed ? 'Попробовать снова' : 'Начать';
  }
  updatePreparingRing(dashboardMiniRing, dashboardMiniPercent, preparing ? progressPercent : 0);

  if (prechatStartButton) {
    prechatStartButton.classList.toggle('hidden', preparing);
    prechatStartButton.disabled = preparing;
    prechatStartButton.textContent = ready ? 'Начать' : failed ? 'Попробовать снова' : 'Начать';
  }
  if (prechatAssessmentPreparing) {
    prechatAssessmentPreparing.classList.toggle('hidden', !preparing);
  }
  if (prechatAssessmentTitle) {
    prechatAssessmentTitle.textContent = title;
  }
  if (prechatAssessmentText) {
    prechatAssessmentText.textContent = message;
  }
  updatePreparingRing(prechatAssessmentRing, prechatAssessmentPercent, preparing ? progressPercent : 0);
};

export const startAssessmentPreparationPolling = (operationId) => {
  stopAssessmentPreparationPolling();
  if (!operationId) {
    return;
  }
  const poll = async () => {
    try {
      const response = await fetch('/users/operations/' + operationId, {
        credentials: 'same-origin',
      });
      if (!response.ok) {
        return;
      }
      const snapshot = await response.json();
      if (state.assessmentPreparationOperationId !== operationId) {
        stopAssessmentPreparationPolling();
        return;
      }
      state.assessmentPreparationProgressPercent = Number(snapshot.progress_percent || 0);
      state.assessmentPreparationTitle = snapshot.title || 'Подготавливаем кейсы';
      state.assessmentPreparationMessage = snapshot.message || 'Система собирает персонализированный набор кейсов.';
      if (snapshot.status === 'failed') {
        state.assessmentPreparationStatus = 'failed';
      }
      renderAssessmentPreparationState();
      if (snapshot.status === 'completed' || snapshot.status === 'failed') {
        stopAssessmentPreparationPolling();
      }
    } catch (_error) {
      // keep background preparation resilient to short polling issues
    }
  };
  void poll();
  state.assessmentPreparationPollId = window.setInterval(() => {
    void poll();
  }, 1500);
};

const waitForAssessmentPreparationResult = async (operationId) => {
  while (true) {
    try {
      const response = await fetch('/users/assessment/preparation/' + encodeURIComponent(operationId), {
        credentials: 'same-origin',
      });
      const job = await readApiResponse(response, 'Не удалось получить статус подготовки кейсов.');
      if (job.status === 'completed') {
        if (!job.result) {
          throw new Error('Подготовка завершена без данных для запуска интервью.');
        }
        return job.result;
      }
      if (job.status === 'failed') {
        throw new Error(job.error_message || 'Не удалось подготовить кейсы.');
      }
    } catch (error) {
      const message = String(error?.message || '');
      if (!/failed to fetch|networkerror|load failed|получить статус подготовки/i.test(message)) {
        throw error;
      }
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
  }
};

export const enqueueAssessmentPreparation = async (userId, operationId = createOperationId()) => {
  const response = await fetch('/users/' + userId + '/assessment/start', {
    method: 'POST',
    headers: {
      'X-Agent4K-Operation-Id': operationId,
    },
  });
  const queued = await readApiResponse(response, 'Не удалось поставить подготовку кейсов в очередь.');
  const actualOperationId = queued.operation_id || operationId;
  return {
    operationId: actualOperationId,
    resultPromise: waitForAssessmentPreparationResult(actualOperationId),
  };
};

export const shouldPrepareAssessmentInBackground = () => {
  if (state.isAdmin || !state.pendingUser?.id) {
    return false;
  }
  if (hasIncompleteAssessment()) {
    return false;
  }
  if (state.currentScreen === 'interview' || state.currentScreen === 'processing' || state.currentScreen === 'report') {
    return false;
  }
  return !state.preparedAssessmentStartResponse;
};

export const beginAssessmentPreparation = async ({ force = false } = {}) => {
  if (!state.pendingUser?.id || state.isAdmin) {
    return;
  }
  if (!force && !shouldPrepareAssessmentInBackground()) {
    renderAssessmentPreparationState();
    return;
  }
  if (!force && isAssessmentPreparing()) {
    return;
  }

  const operationId = createOperationId();
  state.assessmentPreparationOperationId = operationId;
  state.assessmentPreparationStatus = 'preparing';
  state.assessmentPreparationProgressPercent = 3;
  state.assessmentPreparationTitle = 'Подготавливаем кейсы';
  state.assessmentPreparationMessage = 'Система собирает персонализированный набор кейсов для прохождения.';
  renderAssessmentPreparationState();
  startAssessmentPreparationPolling(operationId);

  try {
    const prepared = await enqueueAssessmentPreparation(state.pendingUser.id, operationId);
    if (prepared.operationId !== operationId) {
      state.assessmentPreparationOperationId = prepared.operationId;
      startAssessmentPreparationPolling(prepared.operationId);
    }
    if (state.assessmentPreparationOperationId !== prepared.operationId) {
      return;
    }
    const data = await prepared.resultPromise;
    stopAssessmentPreparationPolling();
    state.preparedAssessmentStartResponse = data;
    state.assessmentPreparationStatus = 'ready';
    state.assessmentPreparationProgressPercent = 100;
    state.assessmentPreparationTitle = 'Кейсы готовы';
    state.assessmentPreparationMessage = 'Можно переходить к прохождению ассессмента.';
    state.assessmentSessionCode = data.session_code;
    state.assessmentSessionId = data.session_id;
    state.assessmentTotalCases = data.total_cases;
    persistAssessmentContext();
    renderAssessmentPreparationState();
    renderAiWelcomeState();
    renderDashboard();
  } catch (error) {
    if (state.assessmentPreparationOperationId !== operationId) {
      return;
    }
    stopAssessmentPreparationPolling();
    if (shouldRecoverProfileOnAssessmentError(error.message)) {
      state.assessmentPreparationStatus = 'idle';
      state.assessmentPreparationProgressPercent = 0;
      state.assessmentPreparationTitle = '';
      state.assessmentPreparationMessage = '';
      renderAssessmentPreparationState();
      await recoverProfileCompletionForAssessment();
      return;
    }
    state.assessmentPreparationStatus = 'failed';
    state.assessmentPreparationProgressPercent = 0;
    state.assessmentPreparationTitle = 'Не удалось подготовить кейсы';
    state.assessmentPreparationMessage = error.message || 'Попробуйте запустить подготовку еще раз.';
    renderAssessmentPreparationState();
  }
};

export const retryAssessmentPreparation = async () => {
  resetAssessmentPreparationState();
  renderAssessmentPreparationState();
  await beginAssessmentPreparation({ force: true });
};
