import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import {
  startFirstAssessmentButton,
  libraryStartButton,
  aiHeroDescription,
  aiWelcomePanel,
  prechatPanel,
  prechatError,
} from '../dom.js';
import { hideAllPanels, syncUrlState, returnToStart } from '../router.js';
import { showError } from '../components/errors.js';
import {
  canReusePreparedAssessment,
  renderAssessmentPreparationState,
  beginAssessmentPreparation,
} from './assessment.js';
import {
  hasIncompleteAssessment,
  hasCompletedAssessmentBefore,
  openDashboard,
} from './dashboard.js';
import { restoreLocalUserSession } from '../session.js';
import { openAdminDashboard } from './admin/dashboard.js';

const welcomeMbtiCard = document.getElementById('welcome-mbti-card');
const welcomeMbtiButton = document.getElementById('welcome-mbti-button');
const welcomeMbtiStatus = document.getElementById('welcome-mbti-status');

const resolveLatestCompletedSession = async () => {
  if (!state.pendingUser?.id) {
    return null;
  }
  const response = await fetch('/users/' + state.pendingUser.id + '/profile-summary');
  const payload = await response.json();
  const history = Array.isArray(payload?.history) ? payload.history : [];
  const completed = history.find((item) => String(item?.status || '').toLowerCase() === 'completed');
  if (!completed?.session_id) {
    return null;
  }
  state.assessmentSessionId = Number(completed.session_id);
  if (completed.session_code) {
    state.assessmentSessionCode = completed.session_code;
  }
  persistAssessmentContext();
  return completed;
};

const updateWelcomeMbtiCardState = ({ ready = false, loading = false, statusText = '' } = {}) => {
  if (!welcomeMbtiCard || !welcomeMbtiButton || !welcomeMbtiStatus) {
    return;
  }
  welcomeMbtiCard.classList.toggle('welcome-mbti-ready', ready);
  welcomeMbtiButton.disabled = !ready || loading;
  welcomeMbtiButton.classList.toggle('disabled', !ready || loading);
  welcomeMbtiButton.textContent = loading ? 'Открываем...' : ready ? 'Уточнить MBTI' : 'Скоро';
  welcomeMbtiStatus.textContent = statusText;
  welcomeMbtiStatus.classList.toggle('hidden', !statusText);
};

const prepareWelcomeMbtiEntry = async () => {
  if (!welcomeMbtiButton) {
    return;
  }
  const hasSummary = Boolean(state.assessmentMbtiSummary && typeof state.assessmentMbtiSummary === 'object');
  if (state.assessmentSessionId) {
    updateWelcomeMbtiCardState({
      ready: true,
      statusText: 'Уточнение доступно по последнему завершенному ассессменту.',
    });
    return;
  }

  if (!state.pendingUser?.id && !hasCompletedAssessmentBefore()) {
    updateWelcomeMbtiCardState({
      ready: false,
      statusText: 'Кнопка станет доступна после первого завершенного ассессмента.',
    });
    return;
  }

  updateWelcomeMbtiCardState({ ready: false, loading: true, statusText: 'Проверяем доступность MBTI...' });
  try {
    const session = await resolveLatestCompletedSession();
    updateWelcomeMbtiCardState({
      ready: Boolean(session?.session_id),
      statusText: session?.session_id
        ? hasSummary
          ? 'Уточнение доступно по последнему завершенному ассессменту.'
          : 'Откроем последний завершенный отчет сразу на блоке MBTI.'
        : 'MBTI станет доступен после завершения ассессмента и формирования отчета.',
    });
  } catch (error) {
    console.warn('Failed to resolve MBTI launcher state', error);
    updateWelcomeMbtiCardState({
      ready: false,
      statusText: 'Не удалось проверить доступность MBTI. Попробуйте позже.',
    });
  }
};

const openWelcomeMbti = async () => {
  if (!state.pendingUser?.id || !welcomeMbtiButton) {
    return;
  }
  updateWelcomeMbtiCardState({ ready: false, loading: true, statusText: 'Открываем MBTI-отчет...' });
  try {
    if (!state.assessmentSessionId) {
      await resolveLatestCompletedSession();
    }
    const reportModule = await import('./report.js');
    await reportModule.loadSkillAssessments();
    reportModule.openReport({ returnTarget: 'home' });
  } catch (error) {
    console.error('Failed to open MBTI report from welcome screen', error);
    updateWelcomeMbtiCardState({
      ready: true,
      statusText: error instanceof Error ? error.message : 'Не удалось открыть MBTI-отчет.',
    });
    return;
  }
  updateWelcomeMbtiCardState({
    ready: true,
    statusText: 'Открываем последний отчет с MBTI-анализом.',
  });
};

export const renderAiWelcomeState = () => {
  const isContinueMode = hasIncompleteAssessment();
  const hasHistory = hasCompletedAssessmentBefore();
  const backendLabel = String(state.dashboard?.active_assessment?.button_label || '').toLowerCase();
  const shouldRepeat = !isContinueMode && (hasHistory || backendLabel.includes('снова'));
  const prepared = canReusePreparedAssessment() && !isContinueMode;
  const primaryLabel = isContinueMode
    ? 'Продолжить ассессмент'
    : prepared
      ? 'Перейти к кейсам'
      : shouldRepeat
        ? 'Пройти ассессмент снова'
        : 'Начать первый ассессмент';

  startFirstAssessmentButton.innerHTML =
    '<span>' +
    primaryLabel +
    '</span><img class="button-arrow" src="/web/assets/icons/forward-arrow-white-icon.svg" alt="" aria-hidden="true">';
  libraryStartButton.textContent = isContinueMode
    ? 'Продолжить'
    : prepared
      ? 'К кейсам'
      : shouldRepeat
        ? 'Снова'
        : 'Начать';

  if (aiHeroDescription) {
    aiHeroDescription.textContent = isContinueMode
      ? 'Продолжите текущий ассессмент, чтобы завершить оценку компетенций и перейти к итоговому профилю.'
      : prepared
        ? 'Набор кейсов уже подготовлен. Можно сразу переходить к прохождению.'
        : shouldRepeat
          ? 'Пройдите ассессмент снова, чтобы получить новый набор кейсов и сравнить результаты с предыдущими попытками.'
          : 'Пройдите первый ассессмент, чтобы получить ваш профиль компетенций и персонализированные рекомендации от искусственного интеллекта.';
  }
  renderAssessmentPreparationState();
  if (welcomeMbtiButton) {
    welcomeMbtiButton.onclick = () => {
      void openWelcomeMbti();
    };
  }
  void prepareWelcomeMbtiEntry();
};

export const openAiWelcome = () => {
  if (hasIncompleteAssessment()) {
    openDashboard();
    return;
  }
  state.newUserSequenceStep = 'ai-welcome';
  setCurrentScreen('ai-welcome');
  persistAssessmentContext();
  syncUrlState('ai-welcome');
  renderAiWelcomeState();
  hideAllPanels();
  aiWelcomePanel.classList.remove('hidden');
  void beginAssessmentPreparation();
};

export const openWelcomeScreen = () => {
  if (state.isAdmin) {
    openAdminDashboard();
    return;
  }
  if (state.dashboard) {
    openDashboard();
    return;
  }
  openAiWelcome();
};

export const openHomePage = async () => {
  if (state.isAdmin) {
    openAdminDashboard();
    return;
  }

  if (!state.dashboard && state.pendingUser?.id) {
    try {
      await restoreLocalUserSession();
    } catch (error) {
      console.error('Failed to restore dashboard before opening home page', error);
    }
  }

  if (state.dashboard) {
    openDashboard();
    return;
  }

  returnToStart();
};

export const openPrechat = () => {
  state.newUserSequenceStep = 'prechat';
  setCurrentScreen('prechat');
  persistAssessmentContext();
  syncUrlState('prechat');
  hideAllPanels();
  showError(prechatError, '');
  renderAssessmentPreparationState();
  prechatPanel.classList.remove('hidden');
  void beginAssessmentPreparation();
};
