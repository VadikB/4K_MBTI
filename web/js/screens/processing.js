import { renderPreparation } from '../preparation-status.js';
import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import {
  processingPanel,
  processingTotalProgress,
  processingTotalProgressBar,
  processingStatusText,
  processingAgentsList,
  processingPhaseLabel,
  processingLegacy,
  processingOutcomeCard,
  processingOutcomeTitle,
  processingOutcomeDescription,
  processingOutcomeProgress,
  processingOutcomeNotice,
  processingOutcomeActions,
  processingOutcomeIndicator,
} from '../dom.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { clearProcessingTimer, buildProcessingAgentsState } from './chat.js';
import { tryOpenReportAfterProcessing, loadSkillAssessments, openReport } from './report.js';
import { fetchWithDeadline, readApiResponse } from '../api.js';

const ANALYSIS_POLL_INTERVAL_MS = 1200;
const CYCLE_POLL_INTERVAL_MS = 5000;
const COLLECTION_CLOSED = new Set(['collection_closed', 'calculation_pending', 'calculated', 'failed']);
const EXPIRY_REASONS = new Set(['time_budget', 'calendar_deadline']);
let cycleView = null;

const isCycleSelected = (view) => view.ownerId === state.pendingUser?.id
  && view.identityEpoch === state.identityEpoch && view.cycleId === state.productCycleId;
const isCycleViewCurrent = (view) => view === cycleView
  && state.currentScreen === 'processing' && isCycleSelected(view);
const canPollCycle = (view) => isCycleViewCurrent(view) && view.polling
  && !document.hidden && Date.now() < view.deadline;

document.addEventListener('visibilitychange', () => {
  if (!cycleView || !isCycleViewCurrent(cycleView)) return;
  if (document.hidden) clearProcessingTimer();
  else if (canPollCycle(cycleView)) void pollAnalysisStatus();
});
window.addEventListener('agent4k:assessment-context-cleared', () => {
  cycleView?.request?.abort();
  cycleView = null;
});
const ANALYSIS_STEP_LABELS = {
  queued: 'Ожидаем свободный обработчик',
  starting: 'Запускаем итоговый анализ',
  competency_1: 'Анализируем коммуникацию',
  competency_2: 'Анализируем командную работу',
  competency_3: 'Анализируем креативность',
  competency_4: 'Анализируем критическое мышление',
  retry_wait: 'Ожидаем повторную попытку',
  lease_recovered: 'Восстанавливаем прерванную обработку',
  report_ready: 'Итоговый отчет готов',
  failed: 'Не удалось завершить анализ',
};

export const renderProcessingOrbit = () => {
  const nodeIds = {
    communication: 'processing-node-communication',
    teamwork: 'processing-node-teamwork',
    creativity: 'processing-node-creativity',
    critical: 'processing-node-critical',
  };

  state.processingAgents.forEach((agent) => {
    const node = document.getElementById(nodeIds[agent.id]);
    if (!node) {
      return;
    }
    node.classList.remove('active', 'done');
    if (agent.status === 'running') {
      node.classList.add('active');
    } else if (agent.status === 'done') {
      node.classList.add('done');
    }
  });
};

export const renderProcessingProgress = () => {
  const calculatedProgress = Math.round(
    state.processingAgents.reduce((sum, agent) => sum + agent.progress, 0) / state.processingAgents.length,
  );
  const totalProgress =
    state.processingServerProgress == null ? calculatedProgress : Math.round(state.processingServerProgress);
  processingTotalProgress.textContent = totalProgress + '%';
  processingTotalProgressBar.style.width = totalProgress + '%';

  const activeAgent = state.processingAgents.find((agent) => agent.status === 'running');
  const totalPhases = state.processingAgents.length;
  const currentPhase = Math.min(state.processingStepIndex + 1, totalPhases);
  processingPhaseLabel.textContent = 'Этап ' + currentPhase + ' из ' + totalPhases;

  if (activeAgent) {
    processingStatusText.textContent = activeAgent.title + ': анализируем сохраненные ответы.';
  } else if (totalProgress >= 100) {
    processingStatusText.textContent =
      'Анализ завершен. Все четыре агента сформировали итоговую оценку по компетенциям.';
  } else {
    processingStatusText.textContent = 'Подготавливаем мульти-агентную оценку по результатам кейсов.';
  }

  processingAgentsList.innerHTML = '';
  state.processingAgents.forEach((agent) => {
    const item = document.createElement('article');
    item.className = 'card card--inset processing-agent-card ' + agent.status;
    item.innerHTML =
      '<div class="processing-agent-main">' +
      '<div class="processing-agent-order">' +
      String(agent.order).padStart(2, '0') +
      '</div>' +
      '<div class="processing-agent-copy">' +
      '<strong>' +
      agent.title +
      '</strong>' +
      '<p>' +
      agent.focus +
      '</p>' +
      '</div>' +
      '</div>' +
      '<div class="processing-agent-meta">' +
      '<span class="processing-agent-status">' +
      (agent.status === 'done' ? 'Завершен' : agent.status === 'running' ? 'В работе' : 'Ожидание') +
      '</span>' +
      '<span class="processing-agent-percent">' +
      agent.progress +
      '%</span>' +
      '</div>' +
      '<div class="processing-agent-track"><div class="processing-agent-fill" style="width:' +
      agent.progress +
      '%"></div></div>';
    processingAgentsList.appendChild(item);
  });

  renderProcessingOrbit();
};

export const finishProcessingSequence = () => {
  state.processingAgents = state.processingAgents.map((agent) => ({
    ...agent,
    progress: 100,
    status: 'done',
  }));
  state.processingStepIndex = Math.max(0, state.processingAgents.length - 1);
  state.processingAnimationDone = true;
  state.processingServerProgress = 100;
  renderProcessingProgress();
  tryOpenReportAfterProcessing();
};

export const openProcessing = ({ cycleId = state.productCycleId, confirmedCollection = null, completion = null } = {}) => {
  cycleView?.request?.abort();
  const previous = cycleView && isCycleSelected(cycleView) && cycleView.cycleId === cycleId ? cycleView : null;
  cycleView = null;
  if (cycleId) {
    state.productCycleId = cycleId;
    state.assessmentRuntimeKind = 'cycle';
    persistAssessmentContext();
    const budgetKey = 'p4k-report-wait:' + JSON.stringify([state.pendingUser?.id, cycleId]);
    let deadline = previous?.deadline;
    try {
      deadline ??= Number(window.sessionStorage.getItem(budgetKey)) || null;
      deadline ??= Date.now() + 60000;
      window.sessionStorage.setItem(budgetKey, String(deadline));
    } catch { /* Use the in-memory deadline when storage is unavailable. */ }
    cycleView = {
      cycleId, ownerId: state.pendingUser?.id, identityEpoch: state.identityEpoch,
      snapshot: previous?.snapshot ?? confirmedCollection,
      completionPending: Boolean(completion),
      deadline: deadline ?? Date.now() + 60000, delay: CYCLE_POLL_INTERVAL_MS, polling: false,
    };
  }

  setCurrentScreen('processing');
  syncUrlState('processing');
  hideAllPanels();
  processingPanel.classList.remove('hidden');
  processingPanel.classList.toggle('processing-panel--cycle', Boolean(cycleView));
  clearProcessingTimer();
  if (cycleView) {
    const view = cycleView;
    processingOutcomeCard.classList.remove('hidden');
    processingLegacy.classList.add('hidden');
    renderCycleOutcome(view, 'confirming');
    processingOutcomeTitle.focus();
    void import('./interview.js').then((module) => {
      if (isCycleViewCurrent(view)) module.recoverCompletedInterviewAnswers(view.cycleId);
    }).catch(() => { /* Keep pending receipts for later recovery. */ });
    if (completion) {
      void completion.then((receipt) => {
        if (!isCycleViewCurrent(view)) return;
        view.completionPending = false;
        if (receipt?.cycle_id === view.cycleId && COLLECTION_CLOSED.has(receipt.states?.cycle)
            && !hasConfirmedClosure(view.snapshot)) {
          view.snapshot = { collection_status: receipt.states.cycle, close_reason: receipt.reason };
        }
        void pollAnalysisStatus();
      });
    } else void pollAnalysisStatus();
    return;
  }

  processingOutcomeCard.classList.add('hidden');
  processingLegacy.classList.remove('hidden');
  state.processingStepIndex = 0;
  state.processingAgents = buildProcessingAgentsState();
  state.processingAnimationDone = false;
  state.processingDataLoaded = false;
  state.processingAutoTransitionStarted = false;
  state.processingServerProgress = 0;
  processingStatusText.textContent = 'Подтягиваем итоговые оценки и формируем профиль компетенций.';
  renderProcessingProgress();
  void pollAnalysisStatus();
};

const outcomeCopy = {
  confirming: ['Проверяем завершение оценки', 'Уточняем состояние оценки.'],
  confirmationError: ['Завершение не подтверждено', 'Не удалось получить подтверждение.'],
  waiting: ['Спасибо за ваши ответы', 'Готовим результат. Он будет доступен в ваших оценках.'],
  offline: ['Готовим результат', 'Последнее подтверждённое состояние: сбор ответов завершён.'],
  expired: ['Время оценки закончилось', 'Сбор новых ответов закрыт. Учтём сохранённые ответы.'],
  ready: ['Ваш результат готов', 'Вы можете открыть отчёт и радар.'],
  limited: ['Ваш результат готов', 'В отчёте указано, какие навыки удалось оценить.'],
  failed: ['Не удалось подготовить результат', 'Ваши ответы сохранены.'],
  accessDenied: ['Нет доступа к этой оценке', 'Доступ к результату ограничен.'],
  unavailable: ['Оценка не найдена', 'Не удалось найти запрошенное прохождение.'],
};

const retryLabels = {
  confirming: 'Проверить состояние',
  confirmationError: 'Повторить проверку',
  waiting: 'Проверить готовность',
  offline: 'Повторить проверку',
  expired: 'Проверить готовность',
  failed: 'Проверить ещё раз',
};

const hasConfirmedClosure = (snapshot) => COLLECTION_CLOSED.has(snapshot?.collection_status);
const hasFailedProcessing = (snapshot) => snapshot?.processing?.status === 'failed'
  || snapshot?.results_status === 'failed';
const availableReport = (snapshot) => ['ready', 'limited'].includes(snapshot?.report_status)
  ? snapshot.report_id || null : null;

const cycleOutcomeKind = (snapshot) => {
  if (hasFailedProcessing(snapshot)) return 'failed';
  if (availableReport(snapshot)) {
    const partial = snapshot.partial_result;
    const limited = snapshot.report_status === 'limited' || partial?.plan_completed === false
      || partial?.is_incomplete === true || partial?.plan_scope_limited === true
      || partial?.observation_limited === true || partial?.context_limited === true
      || partial?.source_limited === true || partial?.technical_failure === true
      || partial?.limitation_reasons?.length > 0;
    return limited ? 'limited' : 'ready';
  }
  if (!hasConfirmedClosure(snapshot)) return 'confirmationError';
  return EXPIRY_REASONS.has(snapshot.close_reason) ? 'expired' : 'waiting';
};

const addOutcomeButton = (label, handler) => {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = label;
  button.addEventListener('click', handler);
  processingOutcomeActions.appendChild(button);
  return button;
};

const confirmedProgress = (snapshot) => {
  const { completed, total } = snapshot?.route_progress ?? {};
  return Number.isInteger(completed) && Number.isInteger(total) && total > 0 && completed >= 0 && completed <= total
    ? `Завершено ситуаций: ${completed} из ${total}.` : '';
};

const renderCycleOutcome = (view, kind, { readError = false } = {}) => {
  const snapshot = view.snapshot;
  const [title, description] = outcomeCopy[kind];
  const showSnapshot = !['confirming', 'accessDenied', 'unavailable'].includes(kind);
  const reportId = showSnapshot && !readError ? availableReport(snapshot) : null;
  const failedWithReport = kind === 'failed' && availableReport(snapshot);
  const ready = kind === 'ready' || kind === 'limited';
  processingOutcomeTitle.textContent = title;
  processingOutcomeDescription.textContent = readError && ready
    ? 'Последняя проверка подтвердила готовность результата.' : description;
  processingOutcomeProgress.textContent = showSnapshot ? confirmedProgress(snapshot) : '';
  processingOutcomeProgress.classList.toggle('hidden', !processingOutcomeProgress.textContent);
  processingOutcomeNotice.textContent = readError && hasConfirmedClosure(snapshot)
    ? 'Не удалось проверить готовность. Проверьте подключение или повторите проверку.'
    : failedWithReport ? 'Доступен отчёт с ограничениями из-за сбоя обработки.'
      : kind === 'failed' ? snapshot?.processing?.message || '' : '';
  processingOutcomeNotice.classList.toggle('hidden', !processingOutcomeNotice.textContent);

  const error = ['confirmationError', 'failed', 'offline'].includes(kind) || readError;
  processingOutcomeIndicator.classList.toggle('is-error', error);
  processingOutcomeIndicator.textContent = error ? '!' : ready ? '✓' : '◷';

  const preparation = showSnapshot && !ready ? snapshot?.preparation : null;
  let preparationPanel = processingOutcomeCard.querySelector('.processing-preparation');
  if (preparation) {
    if (!preparationPanel) {
      preparationPanel = document.createElement('div');
      preparationPanel.className = 'processing-preparation';
      processingOutcomeActions.before(preparationPanel);
    }
    renderPreparation(preparationPanel, preparation, { readError });
    preparationPanel.querySelector('[data-preparation-actions]').append(processingOutcomeActions);
  } else if (preparationPanel) {
    preparationPanel.before(processingOutcomeActions);
    preparationPanel.remove();
  }

  const retry = preparation ? 'Проверить состояние'
    : readError && hasConfirmedClosure(snapshot) ? retryLabels.offline : retryLabels[kind];
  const actionsKey = JSON.stringify([kind, reportId, retry, view.completionPending]);
  if (view.actionsKey === actionsKey) return;
  view.actionsKey = actionsKey;
  processingOutcomeActions.replaceChildren();
  if (reportId) {
    addOutcomeButton(failedWithReport ? 'Открыть отчёт с ограничениями' : 'Посмотреть результат', () => {
      if (!isCycleViewCurrent(view) || availableReport(view.snapshot) !== reportId) return;
      clearProcessingTimer();
      view.request?.abort();
      openReport({ m8CycleId: view.cycleId, m8ReportId: reportId });
    });
  }
  if (retry) {
    const button = addOutcomeButton(retry, () => void pollCycleStatus(view));
    button.disabled = view.completionPending;
  }
  addOutcomeButton('В личный кабинет', () => {
    clearProcessingTimer();
    void import('../screen-loaders.js').then(async ({ loadDashboard }) => {
      const module = await loadDashboard();
      if (isCycleViewCurrent(view)) {
        view.request?.abort();
        module.openDashboard();
      }
    });
  });
};

const pollCycleStatus = async (view) => {
  if (!isCycleViewCurrent(view) || view.completionPending) return;
  clearProcessingTimer();
  view.request?.abort();
  const request = new AbortController();
  view.request = request;
  const isCurrent = () => isCycleViewCurrent(view) && view.request === request;
  view.polling = false;
  try {
    const response = await fetchWithDeadline('/users/assessment/m8/cycles/' + encodeURIComponent(view.cycleId) + '/status', {
      credentials: 'same-origin', signal: request.signal,
    }, 4000);
    if (!isCurrent()) return;
    if (response.status === 403 || response.status === 404) {
      view.snapshot = null;
      renderCycleOutcome(view, response.status === 403 ? 'accessDenied' : 'unavailable');
      return;
    }
    const snapshot = await readApiResponse(response, 'Не удалось получить состояние оценки.');
    if (!isCurrent()) return;
    if (snapshot.cycle_id && snapshot.cycle_id !== view.cycleId) throw new Error('Получен статус другой оценки.');
    view.snapshot = snapshot;
    const kind = cycleOutcomeKind(snapshot);
    renderCycleOutcome(view, kind);
    view.polling = ['waiting', 'expired'].includes(kind);
    if (canPollCycle(view)) {
      state.processingTimerId = window.setTimeout(() => {
        if (canPollCycle(view)) void pollCycleStatus(view);
      }, view.delay);
      view.delay = Math.min(15000, view.delay * 1.5);
    }
  } catch (_error) {
    if (!isCurrent()) return;
    const confirmed = hasConfirmedClosure(view.snapshot) || hasFailedProcessing(view.snapshot)
      || Boolean(availableReport(view.snapshot));
    const previousKind = cycleOutcomeKind(view.snapshot);
    const kind = confirmed ? (previousKind === 'waiting' ? 'offline' : previousKind) : 'confirmationError';
    renderCycleOutcome(view, kind, { readError: true });
  }
};

const applyServerAnalysisProgress = (snapshot) => {
  const progress = Math.max(0, Math.min(100, Number(snapshot?.progress_percent || 0)));
  const step = String(snapshot?.current_step || 'queued');
  const activeIndex = /^competency_(\d)$/.test(step) ? Number(step.slice(-1)) - 1 : -1;
  const thresholds = [15, 35, 55, 75];
  state.processingServerProgress = progress;
  state.processingStepIndex = activeIndex >= 0 ? activeIndex : Math.min(3, Math.floor(progress / 25));
  state.processingAgents = state.processingAgents.map((agent, index) => {
    if (snapshot?.status === 'completed' || progress >= thresholds[index] + 15) {
      return { ...agent, progress: 100, status: 'done' };
    }
    if (index === activeIndex) {
      return { ...agent, progress: Math.max(20, Math.min(95, progress)), status: 'running' };
    }
    if (progress >= thresholds[index]) {
      return { ...agent, progress: 100, status: 'done' };
    }
    return { ...agent, progress: 0, status: 'pending' };
  });
  renderProcessingProgress();
  processingStatusText.textContent =
    ANALYSIS_STEP_LABELS[step] || 'Формируем итоговый профиль компетенций.';
};

const loadCompletedAnalysisReport = async () => {
  try {
    await loadSkillAssessments();
    state.processingDataLoaded = true;
    finishProcessingSequence();
    tryOpenReportAfterProcessing();
  } catch (error) {
    processingStatusText.textContent = error.message;
  }
};

const renderAnalysisFailure = (snapshot) => {
  clearProcessingTimer();
  state.processingServerProgress = Math.max(0, Number(snapshot?.progress_percent || 0));
  processingStatusText.textContent =
    snapshot?.error_message || 'Не удалось сформировать итоговый отчет. Можно повторить анализ.';
  processingAgentsList.innerHTML =
    '<article class="card card--inset processing-agent-card error">' +
    '<div class="processing-agent-main"><div class="processing-agent-copy">' +
    '<strong>Ошибка итогового анализа</strong>' +
    '<p>Сохраненные ответы не потеряны. Повторный запуск продолжит обработку этой сессии.</p>' +
    '</div></div>' +
    '<button type="button" class="primary-button compact-primary" data-analysis-retry>Повторить анализ</button>' +
    '</article>';
  const retryButton = processingAgentsList.querySelector('[data-analysis-retry]');
  if (retryButton) {
    retryButton.addEventListener('click', async () => {
      retryButton.disabled = true;
      processingStatusText.textContent = 'Повторно запускаем итоговый анализ...';
      try {
        const response = await fetch(
          '/users/' +
            state.pendingUser.id +
            '/assessment/' +
            state.assessmentSessionId +
            '/analysis-retry',
          {
            method: 'POST',
            credentials: 'same-origin',
          },
        );
        const nextSnapshot = await readApiResponse(response, 'Не удалось повторно запустить анализ.');
        state.processingAgents = buildProcessingAgentsState();
        applyServerAnalysisProgress(nextSnapshot);
        scheduleAnalysisPoll();
      } catch (error) {
        processingStatusText.textContent = error.message;
        retryButton.disabled = false;
      }
    });
  }
};

const scheduleAnalysisPoll = () => {
  clearProcessingTimer();
  state.processingTimerId = window.setTimeout(() => void pollAnalysisStatus(), ANALYSIS_POLL_INTERVAL_MS);
};

export const pollAnalysisStatus = async () => {
  if (cycleView) {
    await pollCycleStatus(cycleView);
    return;
  }
  if (!state.pendingUser?.id || !state.assessmentSessionId) {
    processingStatusText.textContent = 'Не удалось определить сессию итогового анализа.';
    return;
  }
  try {
    const response = await fetch(
      '/users/' +
        state.pendingUser.id +
        '/assessment/' +
        state.assessmentSessionId +
        '/analysis-status',
      { credentials: 'same-origin' },
    );
    const snapshot = await readApiResponse(response, 'Не удалось получить статус итогового анализа.');
    applyServerAnalysisProgress(snapshot);
    if (snapshot.status === 'completed' || snapshot.session_status === 'completed') {
      await loadCompletedAnalysisReport();
      return;
    }
    if (snapshot.status === 'failed') {
      renderAnalysisFailure(snapshot);
      return;
    }
    scheduleAnalysisPoll();
  } catch (error) {
    processingStatusText.textContent = error.message;
    scheduleAnalysisPoll();
  }
};
