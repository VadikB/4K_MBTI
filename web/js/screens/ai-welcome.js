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
