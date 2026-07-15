import { state, persistAssessmentContext, safeStorage, STORAGE_KEYS, setCurrentScreen } from '../state.js';
import {
  messages,
  statusCard,
  chatPanel,
  chatForm,
  chatInput,
  chatError,
  chatRoleOptions,
  chatConsentDetails,
  interviewMessages,
  interviewSummary,
  interviewCompleteActions,
  interviewPanel,
  interviewTextarea,
  interviewSubmitButton,
  interviewFinishButton,
  interviewError,
  authPanel,
  authTokenForm,
  authStatus,
  authError,
  emailInput,
  magicTokenInput,
} from '../dom.js';
import {
  processingAgentsBlueprint,
  loaderFlows,
  PROFILE_NO_CHANGES_LABEL,
  PROFILE_NO_CHANGES_MESSAGE,
} from '../config.js';
import { readApiResponse, createOperationId } from '../api.js';
import {
  escapeHtml,
  sanitizeDisplayRole,
  sanitizeDisplayMetaText,
  buildExistingUserAgentMessage,
  shouldOfferNoChangesQuickReply,
  hasRequiredProfileFields,
  harmonizeNoChangesPrompt,
} from '../utils/format.js';
import { addMessage, showAgentTyping, hideAgentTyping } from '../components/chat-messages.js';
import { showError } from '../components/errors.js';
import { hideLoader, showLoader, startLoaderProgressPolling } from '../utils/loader.js';
import { hideAllPanels, syncUrlState, returnToStart } from '../router.js';
import {
  destroyAdminCompetencyBarChart,
  destroyAdminMbtiPieChart,
  destroyAdminActivityBarChart,
} from './admin/charts.js';
import { destroyReportCompetencyBarChart } from './report.js';
import { destroyAdminSkillRadarChart } from './admin/skill-radar.js';
import { beginAssessmentPreparation, stopAssessmentPreparationPolling } from './assessment.js';
import { openDashboard } from './dashboard.js';
import { openOnboardingScreen } from '../screen-loaders.js';

const PERSONAL_DATA_CONSENT_URL = '/web/assets/docs/personal-data-consent.pdf';

const getChatSubmitButton = () => chatForm.querySelector('button[type="submit"]');

export const clearProcessingTimer = () => {
  if (state.processingTimerId) {
    window.clearTimeout(state.processingTimerId);
    state.processingTimerId = null;
  }
};

export const buildProcessingAgentsState = () =>
  processingAgentsBlueprint.map((agent, index) => ({
    ...agent,
    order: index + 1,
    progress: 0,
    status: 'pending',
  }));

export const resetChat = () => {
  state.sessionId = null;
  state.completed = false;
  state.isChatSubmitting = false;
  state.pendingAgentMessage = null;
  state.pendingUser = null;
  state.dashboard = null;
  state.isAdmin = false;
  state.adminDashboard = null;
  state.adminReports = null;
  state.adminReportDetail = null;
  state.adminReportDetailSessionId = null;
  state.adminReportDetailSkillAssessments = [];
  state.adminReportDetailSkillAssessmentsLoading = false;
  state.adminReportsSearch = '';
  state.adminReportsPage = 1;
  state.pendingRoleOptions = [];
  state.pendingActionOptions = [];
  state.pendingConsentTitle = null;
  state.pendingConsentText = null;
  state.pendingNoChangesQuickReply = false;
  state.resumeAssessmentAfterProfileCompletion = false;
  state.assessmentSessionCode = null;
  state.assessmentCaseNumber = 0;
  state.assessmentTotalCases = 0;
  state.assessmentCaseTitle = null;
  state.onboardingIndex = 0;
  state.isNewUserFlow = false;
  state.onboardingShown = false;
  state.newUserSequenceStep = 'onboarding';
  state.assessmentTimeLimitMinutes = null;
  state.assessmentCaseStartedAt = null;
  state.assessmentRemainingSeconds = null;
  state.activeInterviewCaseKey = null;
  state.caseOutcomeByNumber = {};
  state.processingStepIndex = 0;
  state.processingAgents = buildProcessingAgentsState();
  state.assessmentSessionId = null;
  destroyAdminCompetencyBarChart();
  destroyAdminMbtiPieChart();
  destroyAdminActivityBarChart();
  destroyReportCompetencyBarChart();
  destroyAdminSkillRadarChart();
  state.skillAssessments = [];
  state.reportCompetencyTab = 'Коммуникация';
  state.processingAnimationDone = false;
  state.processingDataLoaded = false;
  state.processingAutoTransitionStarted = false;
  stopAssessmentPreparationPolling();
  state.assessmentPreparationStatus = 'idle';
  state.assessmentPreparationProgressPercent = 0;
  state.assessmentPreparationTitle = '';
  state.assessmentPreparationMessage = '';
  state.assessmentPreparationOperationId = null;
  state.preparedAssessmentStartResponse = null;
  state.profileSummary = null;
  state.profileSelectedSessionId = null;
  state.profileSkillAssessments = [];
  state.profileSkillsBySession = {};
  if (state.assessmentTimerId) {
    window.clearInterval(state.assessmentTimerId);
    state.assessmentTimerId = null;
  }
  clearProcessingTimer();
  state.assessmentTimeoutInFlight = false;
  interviewMessages.innerHTML = '';
  interviewSummary.classList.add('hidden');
  interviewSummary.textContent = '';
  interviewCompleteActions.classList.add('hidden');
  interviewPanel.classList.remove('completed');
  interviewTextarea.value = '';
  interviewTextarea.disabled = false;
  interviewSubmitButton.disabled = false;
  interviewFinishButton.disabled = false;
  showError(interviewError, '');
  messages.innerHTML = '';
  chatInput.value = '';
  chatInput.disabled = false;
  getChatSubmitButton().disabled = false;
  chatForm.classList.remove('hidden');
  showError(chatError, '');
  showError(authError, '');
  if (authStatus) {
    authStatus.textContent = '';
    authStatus.classList.add('hidden');
  }
  chatRoleOptions.innerHTML = '';
  chatRoleOptions.classList.add('hidden');
  if (chatConsentDetails) {
    chatConsentDetails.innerHTML = '';
    chatConsentDetails.classList.add('hidden');
  }
  statusCard.classList.add('hidden');
  statusCard.textContent = '';
  hideAllPanels();
  authPanel.classList.remove('hidden');
  hideLoader();
  if (authTokenForm) {
    authTokenForm.classList.add('hidden');
  }
  if (magicTokenInput) {
    magicTokenInput.value = '';
  }
  if (emailInput) {
    emailInput.focus();
  }
};

export const setStatus = (data) => {
  const user = data.user;
  if (!user) {
    statusCard.classList.add('hidden');
    statusCard.textContent = '';
    return;
  }

  const jobValue = sanitizeDisplayRole(user.raw_position || user.job_description || '');
  const dutiesValue = sanitizeDisplayMetaText(user.raw_duties || user.normalized_duties || '');
  const job = jobValue || 'не указана (обязательно)';
  const duties = dutiesValue || 'не указаны (обязательно)';

  const header = document.createElement('div');
  header.className = 'status-card__header';
  const eyebrow = document.createElement('span');
  eyebrow.className = 'status-card__eyebrow';
  eyebrow.textContent = 'Сотрудник найден';
  const name = document.createElement('h3');
  name.className = 'status-card__name';
  name.textContent = user.full_name;
  header.append(eyebrow, name);

  const meta = document.createElement('dl');
  meta.className = 'status-card__meta';
  const addRow = (label, value) => {
    const dt = document.createElement('dt');
    dt.className = 'status-card__meta-label';
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.className = 'status-card__meta-value';
    dd.textContent = value;
    meta.append(dt, dd);
  };
  addRow('Email', user.email || 'не указан');
  addRow('Должность *', job);
  addRow('Обязанности *', duties);

  statusCard.replaceChildren(header, meta);
  statusCard.classList.remove('hidden');
};

export const renderChatRoleOptions = () => {
  if (!chatRoleOptions) {
    return;
  }
  const options = Array.isArray(state.pendingRoleOptions) ? state.pendingRoleOptions : [];
  const hasPendingConsent = Boolean(state.pendingConsentText);
  const actionOptions = (Array.isArray(state.pendingActionOptions) ? state.pendingActionOptions : []).filter((option) => {
    if (!state.pendingConsentText) {
      return true;
    }
    return String(option?.value || '').trim().toLowerCase() === 'согласен';
  });
  const hasCompactActions = actionOptions.length > 0;
  const canConfirmNoChanges = hasRequiredProfileFields(state.pendingUser);
  const showNoChangesQuickReply = Boolean(state.pendingNoChangesQuickReply) && !hasPendingConsent && canConfirmNoChanges;
  chatRoleOptions.innerHTML = '';
  chatPanel.classList.toggle('compact-chat-flow', hasCompactActions);
  chatForm.classList.toggle('hidden', hasCompactActions || state.completed);
  if (chatConsentDetails) {
    chatConsentDetails.innerHTML = '';
    if (state.pendingConsentText) {
      const details = document.createElement('details');
      details.className = 'chat-consent-accordion';
      details.innerHTML =
        '<summary>' +
        escapeHtml(state.pendingConsentTitle || 'Согласие на обработку персональных данных') +
        '</summary>' +
        '<div class="chat-consent-accordion-body"><p>' +
        escapeHtml(state.pendingConsentText).replace(/\\n/g, '<br>') +
        '</p><a class="chat-consent-document-link" href="' +
        PERSONAL_DATA_CONSENT_URL +
        '" target="_blank" rel="noopener noreferrer">Открыть документ согласия</a></div>';
      chatConsentDetails.appendChild(details);
      chatConsentDetails.classList.remove('hidden');
    } else {
      chatConsentDetails.classList.add('hidden');
    }
  }
  if (!options.length && !actionOptions.length && !showNoChangesQuickReply) {
    chatRoleOptions.classList.add('hidden');
    chatPanel.classList.remove('compact-chat-flow');
    chatForm.classList.toggle('hidden', state.completed);
    return;
  }

  const list = document.createElement('div');
  list.className = 'chat-role-options-list';

  if (options.length) {
    const label = document.createElement('p');
    label.className = 'chat-role-options-label';
    label.textContent = 'Выберите одну роль:';
    chatRoleOptions.appendChild(label);
  } else if (actionOptions.length) {
    const label = document.createElement('p');
    label.className = 'chat-role-options-label';
    label.textContent = state.pendingConsentText
      ? 'Подтвердите согласие на обработку персональных данных:'
      : 'Подтвердите выбор:';
    chatRoleOptions.appendChild(label);
  }

  if (showNoChangesQuickReply) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chat-role-option-button chat-role-option-button--quiet';
    button.textContent = PROFILE_NO_CHANGES_LABEL;
    button.addEventListener('click', () => {
      void sendChatMessage(PROFILE_NO_CHANGES_MESSAGE, PROFILE_NO_CHANGES_LABEL);
    });
    list.appendChild(button);
  }

  options.forEach((option) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chat-role-option-button chat-role-option-button--quiet';
    const title = document.createElement('span');
    title.className = 'chat-role-option-title';
    title.textContent = option.name;
    button.appendChild(title);
    button.addEventListener('click', () => {
      void sendChatMessage(String(option.id));
    });
    list.appendChild(button);
  });
  actionOptions.forEach((option) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = state.pendingConsentText
      ? 'chat-role-option-button chat-role-option-button--quiet chat-consent-accept-button'
      : 'chat-role-option-button chat-role-option-button--quiet';
    if (state.pendingConsentText) {
      const checkbox = document.createElement('span');
      checkbox.className = 'chat-consent-accept-checkbox';
      checkbox.setAttribute('aria-hidden', 'true');
      button.appendChild(checkbox);
    }
    const title = document.createElement('span');
    title.className = 'chat-role-option-title';
    title.textContent = state.pendingConsentText
      ? 'Согласен на обработку персональных данных'
      : option.label || option.value;
    button.appendChild(title);
    button.addEventListener('click', () => {
      void sendChatMessage(String(option.value), String(option.label || option.value));
    });
    list.appendChild(button);
  });
  chatRoleOptions.appendChild(list);
  chatRoleOptions.classList.remove('hidden');
};

export const openChat = () => {
  setCurrentScreen('chat');
  persistAssessmentContext();
  syncUrlState('chat');
  hideAllPanels();
  chatPanel.classList.remove('hidden');
  messages.innerHTML = '';
  chatInput.disabled = state.completed || state.isChatSubmitting;
  getChatSubmitButton().disabled = state.completed || state.isChatSubmitting;
  chatForm.classList.toggle('hidden', state.completed);
  setStatus(state.pendingUser ? { user: state.pendingUser } : {});
  if (
    state.pendingUser &&
    state.pendingAgentMessage &&
    state.pendingAgentMessage.toLowerCase().includes('пользователь не найден')
  ) {
    state.pendingAgentMessage = buildExistingUserAgentMessage(state.pendingUser, state.pendingAgentMessage);
  }
  if (state.pendingAgentMessage) {
    addMessage('bot', state.pendingAgentMessage);
  }
  renderChatRoleOptions();
  if (!state.completed) {
    chatInput.focus();
  }
};

export const sendChatMessage = async (text, displayText = null) => {
  if (!state.sessionId || state.completed || state.isChatSubmitting) {
    return;
  }
  const messageText = String(text || '').trim();
  if (!messageText) {
    return;
  }
  const hadNoChangesQuickReply = state.pendingNoChangesQuickReply;
  state.pendingNoChangesQuickReply = false;
  safeStorage.setItem(STORAGE_KEYS.pendingNoChangesQuickReply, '0');
  renderChatRoleOptions();

  addMessage(
    'user',
    displayText ||
      (Array.isArray(state.pendingRoleOptions) && state.pendingRoleOptions.length
        ? state.pendingRoleOptions.find((item) => String(item.id) === messageText)?.name || messageText
        : messageText),
  );
  chatInput.value = '';
  showError(chatError, '');
  state.isChatSubmitting = true;
  chatInput.disabled = true;
  getChatSubmitButton().disabled = true;
  showAgentTyping();

  try {
    const operationId = state.isNewUserFlow ? createOperationId() : null;
    if (state.isNewUserFlow && operationId) {
      showLoader(
        'Актуализируем профиль',
        'Проверяем изменения, обновляем данные и подготавливаем следующий шаг.',
        loaderFlows.createOrUpdateProfile,
      );
      startLoaderProgressPolling(operationId);
    }
    const response = await fetch('/users/agent/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(operationId ? { 'X-Agent4K-Operation-Id': operationId } : {}),
      },
      body: JSON.stringify({
        session_id: state.sessionId,
        message: messageText,
      }),
    });
    const data = await readApiResponse(response, 'Не удалось обработать сообщение.');

    const botMessage = harmonizeNoChangesPrompt(data.message);
    hideAgentTyping();
    addMessage('bot', botMessage);
    state.completed = data.completed;
    state.pendingUser = data.user || state.pendingUser;
    state.assessmentSessionCode = data.assessment_session_code || state.assessmentSessionCode;
    state.pendingRoleOptions = Array.isArray(data.role_options) ? data.role_options : [];
    state.pendingActionOptions = Array.isArray(data.action_options) ? data.action_options : [];
    state.pendingConsentTitle = data.consent_title || null;
    state.pendingConsentText = data.consent_text || null;
    state.pendingAgentMessage = botMessage || state.pendingAgentMessage;
    state.pendingNoChangesQuickReply = shouldOfferNoChangesQuickReply(botMessage) && hasRequiredProfileFields(state.pendingUser);
    setStatus(data.user ? data : {});
    if (state.isNewUserFlow) {
      hideLoader();
    }
    renderChatRoleOptions();
    persistAssessmentContext();

    if (state.completed) {
      if (state.isNewUserFlow && !data.blocked) {
        void beginAssessmentPreparation();
      }
      state.isChatSubmitting = false;
      chatForm.classList.add('hidden');
      chatInput.disabled = true;
      getChatSubmitButton().disabled = true;

      window.setTimeout(() => {
        if (data.blocked) {
          state.completed = false;
          state.pendingAgentMessage = null;
          state.pendingActionOptions = [];
          state.pendingConsentTitle = null;
          state.pendingConsentText = null;
          state.isNewUserFlow = false;
          returnToStart();
          return;
        }
        if (state.resumeAssessmentAfterProfileCompletion) {
          state.resumeAssessmentAfterProfileCompletion = false;
          persistAssessmentContext();
          if (state.dashboard) {
            openDashboard();
          }
          void beginAssessmentPreparation({ force: true });
          return;
        }

        if (state.isNewUserFlow) {
          void openOnboardingScreen();
          return;
        }

        if (state.dashboard) {
          openDashboard();
        }
      }, 900);
    } else {
      state.isChatSubmitting = false;
      if (!chatForm.classList.contains('hidden')) {
        chatInput.disabled = false;
        getChatSubmitButton().disabled = false;
        chatInput.focus();
      }
    }
  } catch (error) {
    hideAgentTyping();
    if (state.isNewUserFlow) {
      hideLoader();
    }
    if (hadNoChangesQuickReply) {
      state.pendingNoChangesQuickReply = true;
      safeStorage.setItem(STORAGE_KEYS.pendingNoChangesQuickReply, '1');
      renderChatRoleOptions();
    }
    state.isChatSubmitting = false;
    if (!chatForm.classList.contains('hidden')) {
      chatInput.disabled = false;
      getChatSubmitButton().disabled = false;
      chatInput.focus();
    }
    showError(chatError, error.message);
  }
};
