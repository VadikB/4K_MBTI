import { state, setCurrentScreen } from '../state.js';
import {
  processingPanel,
  processingTotalProgress,
  processingTotalProgressBar,
  processingStatusText,
  processingAgentsList,
  processingPhaseLabel,
} from '../dom.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { clearProcessingTimer, buildProcessingAgentsState } from './chat.js';
import { tryOpenReportAfterProcessing, loadSkillAssessments } from './report.js';
import { readApiResponse } from '../api.js';

const ANALYSIS_POLL_INTERVAL_MS = 1200;
const ANALYSIS_STEP_LABELS = {
  queued: 'Ожидаем свободный обработчик',
  starting: 'Запускаем итоговый анализ',
  competency_1: 'Анализируем коммуникацию',
  competency_2: 'Анализируем командную работу',
  competency_3: 'Анализируем креативность',
  competency_4: 'Анализируем критическое мышление',
  mbti_summary: 'Формируем итоговый MBTI-профиль',
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

export const openProcessing = () => {
  setCurrentScreen('processing');
  syncUrlState('processing');
  hideAllPanels();
  processingPanel.classList.remove('hidden');
  clearProcessingTimer();
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
  state.processingTimerId = window.setTimeout(() => {
    void pollAnalysisStatus();
  }, ANALYSIS_POLL_INTERVAL_MS);
};

export const pollAnalysisStatus = async () => {
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
