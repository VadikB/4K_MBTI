import { state, persistAssessmentContext, clearAssessmentContext, safeStorage, STORAGE_KEYS, setCurrentScreen } from './state.js';
import {
  authEmailForm,
  emailInput,
  authTokenForm,
  authCredentialLabel,
  magicTokenInput,
  authPasswordConfirmField,
  authPasswordConfirmInput,
  requestMagicLinkButton,
  verifyMagicLinkButton,
  authStatus,
  authError,
  chatForm,
  chatInput,
  chatMicButton,
  restartButton,
  dashboardRestartButton,
  dashboardMobileExitButton,
  dashboardProfileButton,
  adminLogoutButton,
  adminProfileButton,
  adminStartAssessmentButton,
  adminOpenReportsButton,
  adminOpenPromptLabButton,
  adminOpenMethodologyButton,
  adminOpenOrganizationsButton,
  adminOpenRegressionTestsButton,
  adminRegressionTestsBackButton,
  adminRegressionTestsRunButton,
  adminRegressionTestsRunFullButton,
  adminRegressionTestsCleanupButton,
  adminOrganizationsBackButton,
  adminOrganizationCreateForm,
  adminOrganizationsList,
  adminPeriodSelect,
  adminReportsBackButton,
  adminReportsSearch,
  adminReportsPrevButton,
  adminReportsNextButton,
  adminReportsPdfButton,
  adminReportsExpertGroupButton,
  adminReportsGroupDialog,
  adminReportsGroupDialogList,
  adminReportsGroupDialogClose,
  adminReportsGroupDialogExport,
  adminReportDetailBackButton,
  adminReportDetailPdfButton,
  adminReportDetailExpertPdfButton,
  adminReportDetailDialoguesPdfButton,
  adminReportDetailExpertComment,
  adminReportDetailExpertCommentEdit,
  adminReportDetailExpertCommentCancel,
  adminReportDetailExpertCommentSave,
  adminReportDetailExpertCommentStatus,
  adminReportDetailExpertName,
  adminReportDetailExpertContacts,
  adminReportDetailExpertAssessedAt,
  adminPromptLabBackButton,
  adminPromptLabTabCasesButton,
  adminPromptLabTabDialogButton,
  adminPromptLabSourceSelect,
  adminPromptLabPromptName,
  adminPromptLabPromptText,
  adminPromptLabUserSelect,
  adminPromptLabUserName,
  adminPromptLabRoleSelect,
  adminPromptLabPosition,
  adminPromptLabCompanyIndustry,
  adminPromptLabDuties,
  adminPromptLabProfileJson,
  adminPromptLabCaseSelect,
  adminPromptLabCasePickerButton,
  adminPromptLabCaseDialog,
  adminPromptLabCaseDialogClose,
  adminPromptLabCaseDialogList,
  adminPromptLabRunButton,
  adminPromptLabDialogPrepareButton,
  adminPromptLabDialogSourceSelect,
  adminPromptLabDialogCaseSourceSelect,
  adminPromptLabDialogCasePromptText,
  adminPromptLabDialogPromptText,
  adminPromptLabDialogSendButton,
  adminPromptLabDialogResetButton,
  adminPromptLabDialogUserSelect,
  adminPromptLabDialogCasePickerButton,
  adminPromptLabDialogCaseDialog,
  adminPromptLabDialogCaseDialogClose,
  adminPromptLabDialogCaseDialogList,
  adminPromptLabDialogCaseSelect,
  adminPromptLabDialogUserMessage,
  adminMethodologyBackButton,
  adminMethodologySearch,
  adminMethodologyPrevButton,
  adminMethodologyNextButton,
  adminMethodologyDetailClose,
  adminMethodologyDetailEdit,
  adminMethodologyDetailCancel,
  adminMethodologyDetailSave,
  adminMethodologyDrawerBackdrop,
  adminMethodologyTabLibrary,
  adminMethodologyTabBranches,
  adminMethodologyTabPassports,
  interviewForm,
  interviewTextarea,
  interviewMicButton,
  interviewSubmitButton,
  interviewFinishButton,
  interviewError,
  interviewGoProcessingButton,
  interviewBackButton,
  interviewProfileButton,
  interviewExitButton,
  processingBackButton,
  reportBackButton,
  reportHomeButton,
  reportDownloadButton,
  reportInfoModal,
  reportInfoModalClose,
  reportsBackButton,
  profileBackButton,
  profileAvatarInput,
  profileEmail,
  profileTelegram,
  newUserExitButton,
  prechatExitButton,
  prechatStartButton,
  assessmentActionButton,
  startFirstAssessmentButton,
  libraryStartButton,
  welcomeProfileButton,
} from './dom.js';
import { readApiResponse } from './api.js';
import {
  buildExistingUserAgentMessage,
  shouldOfferNoChangesQuickReply,
  isAdminUserPayload,
} from './utils/format.js';
import { showError } from './components/errors.js';
import { navigateBackOrFallback } from './router.js';
import { hideLoader } from './utils/loader.js';
import { logoutAndReturnToStart } from './session.js';
import { setProfileStatus } from './components/profile-avatar.js';
import {
  loadChat,
  loadProfile,
  loadAiWelcome,
  loadDashboard,
  loadReports,
  loadAssessment,
  loadInterview,
  loadProcessing,
  loadReport,
  loadAdminDashboard,
  loadAdminOrganizations,
  loadAdminRegressionTests,
  loadAdminPromptLab,
  loadAdminReports,
  loadAdminMethodology,
  loadAdminReportDetail,
} from './screen-loaders.js';

const withScreen = (loader, callback) => {
  void (async () => {
    const module = await loader();
    await callback(module);
  })();
};

const isEditableKeyboardTarget = (target) => {
  if (!(target instanceof Element)) {
    return false;
  }
  return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
};

const appendTranscript = (field, transcript) => {
  const cleanTranscript = String(transcript || '').trim();
  if (!field || !cleanTranscript) {
    return;
  }

  const value = field.value || '';
  const selectionStart = typeof field.selectionStart === 'number' ? field.selectionStart : value.length;
  const selectionEnd = typeof field.selectionEnd === 'number' ? field.selectionEnd : selectionStart;
  const before = value.slice(0, selectionStart);
  const after = value.slice(selectionEnd);
  const prefix = before && !/\s$/.test(before) ? ' ' : '';
  const suffix = after && !/^\s/.test(after) ? ' ' : '';
  const insertion = prefix + cleanTranscript + suffix;

  field.value = before + insertion + after;
  const nextPosition = before.length + insertion.length;
  if (typeof field.setSelectionRange === 'function') {
    field.setSelectionRange(nextPosition, nextPosition);
  }
  field.dispatchEvent(new Event('input', { bubbles: true }));
  field.focus();
};

const setupSpeechInput = (button, field) => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!button || !field || !SpeechRecognition) {
    return;
  }

  let recognition = null;
  let listening = false;
  let shouldListen = false;

  const syncDisabled = () => {
    button.disabled = field.disabled;
    if (field.disabled && recognition && listening) {
      shouldListen = false;
      recognition.abort();
    }
  };

  const setListening = (nextListening) => {
    listening = nextListening;
    button.classList.toggle('is-listening', listening);
    button.setAttribute('aria-pressed', listening ? 'true' : 'false');
    button.title = listening ? 'Остановить диктовку' : 'Продиктовать ответ';
    button.setAttribute('aria-label', button.title);
  };

  button.classList.remove('hidden');
  button.setAttribute('aria-pressed', 'false');
  syncDisabled();

  const disabledObserver = new MutationObserver(syncDisabled);
  disabledObserver.observe(field, { attributes: true, attributeFilter: ['disabled'] });

  button.addEventListener('click', () => {
    if (field.disabled) {
      return;
    }
    if (recognition && listening) {
      shouldListen = false;
      recognition.stop();
      return;
    }

    shouldListen = true;
    recognition = new SpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.interimResults = false;
    recognition.continuous = true;
    recognition.maxAlternatives = 1;

    recognition.addEventListener('start', () => setListening(true));
    recognition.addEventListener('end', () => {
      setListening(false);
      if (shouldListen && !field.disabled) {
        recognition.start();
      }
    });
    recognition.addEventListener('error', (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        shouldListen = false;
      }
      setListening(false);
    });
    recognition.addEventListener('result', (event) => {
      const transcript = Array.from(event.results)
        .slice(event.resultIndex)
        .filter((result) => result.isFinal)
        .map((result) => result[0]?.transcript || '')
        .join(' ');
      appendTranscript(field, transcript);
    });

    recognition.start();
  });
};

const changeAdminReportsPage = (direction) => {
  const nextPage = Math.max(1, (state.adminReportsPage || 1) + direction);
  if (nextPage === state.adminReportsPage) {
    return;
  }
  state.adminReportsPage = nextPage;
  persistAssessmentContext();
  withScreen(loadAdminReports, (module) => module.renderAdminReports());
};

const setAuthStatus = (message = '', { isError = false } = {}) => {
  if (!authStatus) {
    return;
  }
  authStatus.textContent = message;
  authStatus.classList.toggle('hidden', !message);
  authStatus.classList.toggle('error', isError);
};

let authCredentialMode = 'dev_token';
let authCredentialEmail = '';

const configureAuthCredentialForm = (mode) => {
  authCredentialMode = mode || 'dev_token';
  const isRegistration = authCredentialMode === 'password_registration';
  const isPasswordMode = authCredentialMode === 'password' || isRegistration;
  if (authCredentialLabel) {
    authCredentialLabel.textContent = isPasswordMode ? 'Пароль' : 'Код или ссылка для входа';
  }
  if (magicTokenInput) {
    magicTokenInput.type = isPasswordMode ? 'password' : 'text';
    magicTokenInput.autocomplete = isRegistration ? 'new-password' : isPasswordMode ? 'current-password' : 'one-time-code';
    magicTokenInput.placeholder = isPasswordMode ? 'Введите пароль' : 'Вставьте код или ссылку из письма';
    magicTokenInput.value = '';
  }
  if (authPasswordConfirmField) {
    authPasswordConfirmField.classList.toggle('hidden', !isRegistration);
  }
  if (authPasswordConfirmInput) {
    authPasswordConfirmInput.required = isRegistration;
    authPasswordConfirmInput.value = '';
  }
  if (verifyMagicLinkButton) {
    verifyMagicLinkButton.textContent = isRegistration ? 'Задать пароль и войти' : 'Войти';
  }
};

const applyAuthResponse = async (data) => {
  const agent = data.agent || null;

  state.sessionId = agent?.session_id || null;
  state.pendingUser = data.user || null;
  state.dashboard = data.dashboard || null;
  state.isAdmin = isAdminUserPayload(data.user, Boolean(data.is_admin));
  state.adminDashboard = data.admin_dashboard || null;
  state.pendingRoleOptions = Array.isArray(agent?.role_options) ? agent.role_options : [];
  state.pendingActionOptions = Array.isArray(agent?.action_options) ? agent.action_options : [];
  state.pendingConsentTitle = agent?.consent_title || null;
  state.pendingConsentText = agent?.consent_text || null;
  state.isNewUserFlow = !data.exists;
  state.pendingAgentMessage = data.exists
    ? buildExistingUserAgentMessage(data.user, agent?.message || data.message || '')
    : agent?.message || data.message || null;
  state.pendingNoChangesQuickReply = data.exists && shouldOfferNoChangesQuickReply(state.pendingAgentMessage);

  if (state.isAdmin) {
    state.sessionId = null;
    state.pendingAgentMessage = null;
    state.pendingRoleOptions = [];
    state.pendingNoChangesQuickReply = false;
    setCurrentScreen('admin');
    persistAssessmentContext();
    hideLoader();
    const adminDashboardModule = await loadAdminDashboard();
    adminDashboardModule.openAdminDashboard();
    return;
  }

  hideLoader();
  const chatModule = await loadChat();
  chatModule.openChat();
};

const handleEmailMagicLinkRequest = async () => {
  showError(authError, '');
  setAuthStatus('');

  const email = emailInput.value.trim();
  if (!email) {
    showError(authError, 'введите email');
    emailInput.focus();
    return;
  }

  try {
    if (requestMagicLinkButton) {
      requestMagicLinkButton.disabled = true;
      requestMagicLinkButton.textContent = 'Проверяем...';
    }
    if (emailInput) {
      emailInput.disabled = true;
    }
    setAuthStatus('Проверяем email...');
    clearAssessmentContext();
    state.sessionId = null;
    state.pendingAgentMessage = null;
    state.pendingRoleOptions = [];
    state.pendingNoChangesQuickReply = false;
    state.pendingUser = null;
    state.dashboard = null;
    state.isAdmin = false;
    state.adminDashboard = null;
    state.isNewUserFlow = false;
    safeStorage.removeItem(STORAGE_KEYS.sessionId);
    safeStorage.removeItem(STORAGE_KEYS.pendingAgentMessage);
    safeStorage.removeItem(STORAGE_KEYS.pendingRoleOptions);
    safeStorage.removeItem(STORAGE_KEYS.pendingNoChangesQuickReply);
    const response = await fetch('/users/auth/email/request-link', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
    });
    const data = await readApiResponse(response, 'Не удалось отправить ссылку для входа.');
    const isDevMode = Boolean(data.dev_mode || data.dev_magic_token);
    const nextMode = isDevMode ? 'dev_token' : data.auth_mode || data.delivery_method || 'password';
    authCredentialEmail = data.email || email;
    configureAuthCredentialForm(nextMode);
    if (authTokenForm) {
      authTokenForm.classList.remove('hidden');
    }
    if (magicTokenInput) {
      magicTokenInput.value = data.dev_magic_token || '';
      magicTokenInput.focus();
    }
    setAuthStatus(
      isDevMode
        ? 'Dev-режим: токен подставлен автоматически. Можно сразу нажать «Войти».'
        : data.message || 'Введите пароль для входа.',
    );
  } catch (error) {
    hideLoader();
    setAuthStatus('');
    showError(authError, error.message);
  } finally {
    if (requestMagicLinkButton) {
      requestMagicLinkButton.disabled = false;
      requestMagicLinkButton.textContent = 'Продолжить';
    }
    if (emailInput) {
      emailInput.disabled = false;
    }
  }
};

export const verifyEmailMagicLinkToken = async (tokenValue = null) => {
  showError(authError, '');
  const token = String(tokenValue ?? magicTokenInput?.value ?? '').trim();
  if (!token) {
    showError(authError, 'вставьте код или ссылку из письма');
    magicTokenInput.focus();
    return;
  }

  try {
    const response = await fetch('/users/auth/email/verify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'same-origin',
      body: JSON.stringify({ token }),
    });
    const data = await readApiResponse(response, 'Не удалось подтвердить вход.');
    setAuthStatus('Email подтвержден. Загружаем ваш профиль...');
    await applyAuthResponse(data);
  } catch (error) {
    showError(authError, error.message);
  }
};

const submitEmailPassword = async () => {
  showError(authError, '');
  const email = String(authCredentialEmail || emailInput?.value || '').trim();
  const password = String(magicTokenInput?.value || '');
  const passwordConfirm = String(authPasswordConfirmInput?.value || '');
  const isRegistration = authCredentialMode === 'password_registration';

  if (!email) {
    showError(authError, 'введите email');
    emailInput?.focus();
    return;
  }
  if (!password) {
    showError(authError, 'введите пароль');
    magicTokenInput?.focus();
    return;
  }
  if (isRegistration && password !== passwordConfirm) {
    showError(authError, 'пароли не совпадают');
    authPasswordConfirmInput?.focus();
    return;
  }

  try {
    if (verifyMagicLinkButton) {
      verifyMagicLinkButton.disabled = true;
      verifyMagicLinkButton.textContent = isRegistration ? 'Регистрируем...' : 'Входим...';
    }
    const response = await fetch(
      isRegistration ? '/users/auth/email/password-register' : '/users/auth/email/password-login',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify(
          isRegistration
            ? { email, password, password_confirm: passwordConfirm }
            : { email, password },
        ),
      },
    );
    const data = await readApiResponse(response, 'Не удалось выполнить вход.');
    setAuthStatus(isRegistration ? 'Пароль задан. Загружаем профиль...' : 'Вход выполнен. Загружаем профиль...');
    await applyAuthResponse(data);
  } catch (error) {
    showError(authError, error.message);
  } finally {
    if (verifyMagicLinkButton) {
      verifyMagicLinkButton.disabled = false;
      verifyMagicLinkButton.textContent = isRegistration ? 'Задать пароль и войти' : 'Войти';
    }
  }
};

export const initWiring = () => {
authEmailForm.addEventListener('submit', (event) => {
  if (!authEmailForm.reportValidity()) {
    return;
  }
  event.preventDefault();
  void handleEmailMagicLinkRequest();
});

if (requestMagicLinkButton) {
  requestMagicLinkButton.addEventListener('click', (event) => {
    if (!authEmailForm.reportValidity()) {
      return;
    }
    event.preventDefault();
    void handleEmailMagicLinkRequest();
  });
}

authTokenForm.addEventListener('submit', (event) => {
  if (!authTokenForm.reportValidity()) {
    return;
  }
  event.preventDefault();
  if (authCredentialMode === 'password' || authCredentialMode === 'password_registration') {
    void submitEmailPassword();
    return;
  }
  void verifyEmailMagicLinkToken();
});

setupSpeechInput(chatMicButton, chatInput);
setupSpeechInput(interviewMicButton, interviewTextarea);

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = chatInput.value.trim();
  withScreen(loadChat, (module) => module.sendChatMessage(text));
});

restartButton.addEventListener('click', (event) => {
  void logoutAndReturnToStart(event.currentTarget);
});

dashboardRestartButton.addEventListener('click', (event) => {
  void logoutAndReturnToStart(event.currentTarget);
});

if (dashboardMobileExitButton) {
  dashboardMobileExitButton.addEventListener('click', (event) => {
    void logoutAndReturnToStart(event.currentTarget);
  });
}

adminLogoutButton.addEventListener('click', (event) => {
  void logoutAndReturnToStart(event.currentTarget);
});

if (adminOpenReportsButton) {
  adminOpenReportsButton.addEventListener('click', () => {
    withScreen(loadAdminReports, (module) => module.openAdminReports());
  });
}

if (adminStartAssessmentButton) {
  adminStartAssessmentButton.addEventListener('click', () => {
    withScreen(loadAdminDashboard, (module) => module.openAdminAssessmentDashboard());
  });
}

if (adminOpenOrganizationsButton) {
  adminOpenOrganizationsButton.addEventListener('click', () => {
    withScreen(loadAdminOrganizations, (module) => module.openAdminOrganizations());
  });
}

if (adminOpenRegressionTestsButton) {
  adminOpenRegressionTestsButton.addEventListener('click', () => {
    withScreen(loadAdminRegressionTests, (module) => module.openAdminRegressionTests());
  });
}

if (adminOpenPromptLabButton) {
  adminOpenPromptLabButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => module.openAdminPromptLab());
  });
}

if (adminOpenMethodologyButton) {
  adminOpenMethodologyButton.addEventListener('click', () => {
    withScreen(loadAdminMethodology, (module) => module.openAdminMethodology());
  });
}

if (adminPeriodSelect) {
  adminPeriodSelect.addEventListener('change', () => {
    const nextPeriod = adminPeriodSelect.value || '30d';
    void (async () => {
      try {
        state.adminPeriodKey = nextPeriod;
        const module = await loadAdminDashboard();
        await module.loadAdminDashboard(nextPeriod);
        module.renderAdminDashboard();
      } catch (error) {
        console.error('Failed to refresh admin dashboard', error);
      }
    })();
  });
}

if (adminReportsBackButton) {
  adminReportsBackButton.addEventListener('click', () => {
    withScreen(loadAdminDashboard, (module) => module.openAdminDashboard());
  });
}

if (adminPromptLabBackButton) {
  adminPromptLabBackButton.addEventListener('click', () => {
    withScreen(loadAdminDashboard, (module) => module.openAdminDashboard());
  });
}

if (adminOrganizationsBackButton) {
  adminOrganizationsBackButton.addEventListener('click', () => {
    withScreen(loadAdminDashboard, (module) => module.openAdminDashboard());
  });
}

if (adminRegressionTestsBackButton) {
  adminRegressionTestsBackButton.addEventListener('click', () => {
    withScreen(loadAdminDashboard, (module) => module.openAdminDashboard());
  });
}

if (adminRegressionTestsRunButton) {
  adminRegressionTestsRunButton.addEventListener('click', () => {
    withScreen(loadAdminRegressionTests, (module) => module.runAdminRegressionTests());
  });
}

if (adminRegressionTestsRunFullButton) {
  adminRegressionTestsRunFullButton.addEventListener('click', () => {
    if (!window.confirm('Запустить полный прогон assessment-сценариев? Это может занять несколько минут и выполнить реальные LLM-вызовы.')) {
      return;
    }
    withScreen(loadAdminRegressionTests, (module) => module.runAdminFullRegressionTests());
  });
}

if (adminRegressionTestsCleanupButton) {
  adminRegressionTestsCleanupButton.addEventListener('click', () => {
    if (!window.confirm('Удалить только данные с префиксом __autotest__?')) {
      return;
    }
    withScreen(loadAdminRegressionTests, (module) => module.cleanupAdminRegressionTests());
  });
}

if (adminOrganizationCreateForm) {
  adminOrganizationCreateForm.addEventListener('submit', (event) => {
    event.preventDefault();
    withScreen(loadAdminOrganizations, (module) => module.createAdminOrganization());
  });
}

if (adminOrganizationsList) {
  adminOrganizationsList.addEventListener('submit', (event) => {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (!form) {
      return;
    }
    event.preventDefault();
    const card = form.closest('[data-organization-id]');
    const organizationId = Number(card?.getAttribute('data-organization-id'));
    const input = form.querySelector('input');
    const value = input?.value || '';
    if (!organizationId) {
      return;
    }
    if (form.dataset.action === 'add-domain') {
      withScreen(loadAdminOrganizations, async (module) => {
        await module.addAdminOrganizationDomain(organizationId, value);
        if (input) input.value = '';
      });
      return;
    }
    if (form.dataset.action === 'add-admin') {
      withScreen(loadAdminOrganizations, async (module) => {
        await module.addAdminOrganizationAdmin(organizationId, value);
        if (input) input.value = '';
      });
      return;
    }
    if (form.dataset.action === 'add-member') {
      const formData = new FormData(form);
      withScreen(loadAdminOrganizations, async (module) => {
        await module.addAdminOrganizationMember(organizationId, {
          email: formData.get('email'),
          full_name: formData.get('full_name'),
          role_description: formData.get('role_description'),
          job_instructions: formData.get('job_instructions'),
        });
        form.reset();
      });
      return;
    }
    if (form.dataset.action === 'import-members') {
      const fileInput = form.querySelector('input[type="file"]');
      const file = fileInput?.files?.[0];
      if (!file) {
        return;
      }
      file.text().then((csvText) => {
        withScreen(loadAdminOrganizations, async (module) => {
          await module.importAdminOrganizationMembers(organizationId, csvText);
          form.reset();
        });
      });
    }
  });

  adminOrganizationsList.addEventListener('click', (event) => {
    const button = event.target instanceof Element ? event.target.closest('button[data-action]') : null;
    if (!button) {
      return;
    }
    const card = button.closest('[data-organization-id]');
    const organizationId = Number(card?.getAttribute('data-organization-id'));
    const value = button.getAttribute('data-value') || '';
    if (!organizationId) {
      return;
    }
    if (button.dataset.action === 'delete-organization') {
      const organizationName = card?.querySelector('h3')?.textContent?.trim() || 'организацию';
      const isDeleteAction = String(button.textContent || '').trim().toLowerCase().includes('удал');
      const message = isDeleteAction
        ? 'Удалить организацию «' + organizationName + '»? Это действие нельзя отменить.'
        : 'Деактивировать организацию «' + organizationName + '»? Новые пользователи больше не будут автоматически привязываться к ней.';
      if (!window.confirm(message)) {
        return;
      }
      withScreen(loadAdminOrganizations, (module) => module.deleteOrDeactivateAdminOrganization(organizationId, organizationName));
      return;
    }
    if (!value) {
      return;
    }
    if (button.dataset.action === 'delete-domain') {
      withScreen(loadAdminOrganizations, (module) => module.deleteAdminOrganizationDomain(organizationId, value));
      return;
    }
    if (button.dataset.action === 'delete-admin') {
      withScreen(loadAdminOrganizations, (module) => module.deleteAdminOrganizationAdmin(organizationId, value));
      return;
    }
    if (button.dataset.action === 'delete-member') {
      withScreen(loadAdminOrganizations, (module) => module.deleteAdminOrganizationMember(organizationId, value));
    }
  });
}

if (adminPromptLabTabCasesButton) {
  adminPromptLabTabCasesButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => module.setPromptLabTab('cases'));
  });
}

if (adminPromptLabTabDialogButton) {
  adminPromptLabTabDialogButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => module.setPromptLabTab('dialog'));
  });
}

if (adminPromptLabSourceSelect) {
  adminPromptLabSourceSelect.addEventListener('change', () => {
    withScreen(loadAdminPromptLab, (module) => module.syncPromptLabPromptSource());
  });
}

if (adminPromptLabPromptText) {
  adminPromptLabPromptText.addEventListener('input', () => {
    if ((adminPromptLabSourceSelect?.value || 'file') !== 'file') {
      withScreen(loadAdminPromptLab, (module) => module.markPromptLabCustomPromptDirty());
    }
  });
}

if (adminPromptLabPromptName) {
  adminPromptLabPromptName.addEventListener('input', () => {
    if ((adminPromptLabSourceSelect?.value || 'file') !== 'file') {
      withScreen(loadAdminPromptLab, (module) => module.markPromptLabCustomPromptDirty());
    }
  });
}

if (adminPromptLabUserSelect) {
  adminPromptLabUserSelect.addEventListener('change', () => {
    void (async () => {
      const module = await loadAdminPromptLab();
      module.fillPromptLabProfileFromUser(module.getSelectedPromptLabUser());
      state.adminPromptLabResult = null;
      try {
        await module.loadPromptLabSystemCasePreview();
        module.renderAdminPromptLabResult();
      } catch (error) {
        module.setPromptLabStatus(error.message || 'Не удалось загрузить кейс из системы.', 'error');
      }
    })();
  });
}

[
  adminPromptLabUserName,
  adminPromptLabRoleSelect,
  adminPromptLabPosition,
  adminPromptLabCompanyIndustry,
  adminPromptLabDuties,
  adminPromptLabProfileJson,
]
  .filter(Boolean)
  .forEach((node) => {
    node.addEventListener('input', () => {
      withScreen(loadAdminPromptLab, (module) => module.markPromptLabProfileDirty());
    });
    node.addEventListener('change', () => {
      withScreen(loadAdminPromptLab, (module) => module.markPromptLabProfileDirty());
    });
  });

if (adminPromptLabCaseSelect) {
  adminPromptLabCaseSelect.addEventListener('change', () => {
    void (async () => {
      const module = await loadAdminPromptLab();
      module.syncPromptLabCasePickerSummary();
      state.adminPromptLabResult = null;
      try {
        await module.loadPromptLabSystemCasePreview();
        module.renderAdminPromptLabResult();
      } catch (error) {
        module.setPromptLabStatus(error.message || 'Не удалось загрузить кейс из системы.', 'error');
      }
    })();
  });
}

if (adminPromptLabCasePickerButton) {
  adminPromptLabCasePickerButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => {
      module.renderPromptLabCaseDialog();
      adminPromptLabCaseDialog?.showModal();
    });
  });
}

if (adminPromptLabCaseDialogList) {
  adminPromptLabCaseDialogList.addEventListener('change', () => {
    withScreen(loadAdminPromptLab, (module) => module.syncPromptLabCaseSelectionFromDialog());
  });
}

if (adminPromptLabCaseDialog) {
  adminPromptLabCaseDialog.addEventListener('close', () => {
    void (async () => {
      const module = await loadAdminPromptLab();
      module.syncPromptLabCaseSelectionFromDialog();
      state.adminPromptLabResult = null;
      try {
        await module.loadPromptLabSystemCasePreview();
        module.renderAdminPromptLabResult();
      } catch (error) {
        module.setPromptLabStatus(error.message || 'Не удалось загрузить кейс из системы.', 'error');
      }
    })();
  });
}

if (adminPromptLabRunButton) {
  adminPromptLabRunButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => module.runAdminPromptLabCase());
  });
}

if (adminPromptLabDialogPrepareButton) {
  adminPromptLabDialogPrepareButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => module.prepareAdminPromptLabDialog());
  });
}

if (adminPromptLabDialogSourceSelect) {
  adminPromptLabDialogSourceSelect.addEventListener('change', () => {
    withScreen(loadAdminPromptLab, (module) => {
      module.syncPromptLabDialogPromptSource();
      module.renderAdminPromptLabDialogResult();
    });
  });
}

if (adminPromptLabDialogCaseSourceSelect) {
  adminPromptLabDialogCaseSourceSelect.addEventListener('change', () => {
    withScreen(loadAdminPromptLab, (module) => {
      module.syncPromptLabDialogCasePromptSource();
      module.renderAdminPromptLabDialogResult();
    });
  });
}

if (adminPromptLabDialogCasePromptText) {
  adminPromptLabDialogCasePromptText.addEventListener('input', () => {
    withScreen(loadAdminPromptLab, (module) => {
      if ((adminPromptLabDialogCaseSourceSelect?.value || 'system') !== 'system') {
        module.markPromptLabDialogCasePromptDirty();
      }
      module.renderAdminPromptLabDialogResult();
    });
  });
}

if (adminPromptLabDialogPromptText) {
  adminPromptLabDialogPromptText.addEventListener('input', () => {
    withScreen(loadAdminPromptLab, (module) => {
      if ((adminPromptLabDialogSourceSelect?.value || 'system') !== 'system') {
        module.markPromptLabDialogPromptDirty();
      }
      module.renderAdminPromptLabDialogResult();
    });
  });
}

if (adminPromptLabDialogSendButton) {
  adminPromptLabDialogSendButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => module.sendAdminPromptLabDialogTurn());
  });
}

if (adminPromptLabDialogResetButton) {
  adminPromptLabDialogResetButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => module.resetAdminPromptLabDialog());
  });
}

if (adminPromptLabDialogUserSelect) {
  adminPromptLabDialogUserSelect.addEventListener('change', () => {
    withScreen(loadAdminPromptLab, (module) => module.resetAdminPromptLabDialog());
  });
}

if (adminPromptLabDialogCasePickerButton) {
  adminPromptLabDialogCasePickerButton.addEventListener('click', () => {
    withScreen(loadAdminPromptLab, (module) => {
      module.renderPromptLabDialogCaseDialog();
      adminPromptLabDialogCaseDialog?.showModal?.();
    });
  });
}

if (adminPromptLabDialogCaseDialogClose) {
  adminPromptLabDialogCaseDialogClose.addEventListener('click', () => {
    adminPromptLabDialogCaseDialog?.close?.();
  });
}

if (adminPromptLabDialogCaseDialogList) {
  adminPromptLabDialogCaseDialogList.addEventListener('change', (event) => {
    withScreen(loadAdminPromptLab, (module) => {
      const target = event.target;
      if (target && target.matches && target.matches('input[type="radio"]')) {
        state.adminPromptLabDialogSelectedCaseCode = String(target.value || '').trim() || null;
        if (adminPromptLabDialogCaseSelect && state.adminPromptLabDialogSelectedCaseCode) {
          adminPromptLabDialogCaseSelect.value = state.adminPromptLabDialogSelectedCaseCode;
        }
      }
      module.syncPromptLabDialogCaseSelectionFromDialog();
      adminPromptLabDialogCaseDialog?.close?.();
      module.resetAdminPromptLabDialog();
    });
  });
}

if (adminPromptLabDialogCaseSelect) {
  adminPromptLabDialogCaseSelect.addEventListener('change', () => {
    state.adminPromptLabDialogSelectedCaseCode = String(adminPromptLabDialogCaseSelect.value || '').trim() || null;
    withScreen(loadAdminPromptLab, (module) => {
      module.syncPromptLabDialogCaseHint();
      module.syncPromptLabDialogCasePickerSummary();
      module.resetAdminPromptLabDialog();
    });
  });
}

if (adminPromptLabDialogUserMessage) {
  adminPromptLabDialogUserMessage.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      withScreen(loadAdminPromptLab, (module) => module.sendAdminPromptLabDialogTurn());
    }
  });
}

if (adminMethodologyBackButton) {
  adminMethodologyBackButton.addEventListener('click', () => {
    withScreen(loadAdminDashboard, (module) => module.openAdminDashboard());
  });
}

if (adminMethodologySearch) {
  adminMethodologySearch.addEventListener('input', () => {
    state.adminMethodologySearch = adminMethodologySearch.value || '';
    state.adminMethodologyPage = 1;
    persistAssessmentContext();
    withScreen(loadAdminMethodology, (module) => module.renderAdminMethodology());
  });
}

if (adminMethodologyPrevButton) {
  adminMethodologyPrevButton.addEventListener('click', () => {
    state.adminMethodologyPage = Math.max(1, Number(state.adminMethodologyPage || 1) - 1);
    withScreen(loadAdminMethodology, (module) => module.renderAdminMethodology());
  });
}

if (adminMethodologyNextButton) {
  adminMethodologyNextButton.addEventListener('click', () => {
    state.adminMethodologyPage = Number(state.adminMethodologyPage || 1) + 1;
    withScreen(loadAdminMethodology, (module) => module.renderAdminMethodology());
  });
}

if (adminMethodologyDetailClose) {
  adminMethodologyDetailClose.addEventListener('click', () => {
    withScreen(loadAdminMethodology, (module) => module.closeAdminMethodologyDetail());
  });
}

if (adminMethodologyDetailEdit) {
  adminMethodologyDetailEdit.addEventListener('click', () => {
    withScreen(loadAdminMethodology, (module) => module.startAdminMethodologyEditing());
  });
}

if (adminMethodologyDetailCancel) {
  adminMethodologyDetailCancel.addEventListener('click', () => {
    withScreen(loadAdminMethodology, (module) => module.cancelAdminMethodologyEditing());
  });
}

if (adminMethodologyDetailSave) {
  adminMethodologyDetailSave.addEventListener('click', () => {
    withScreen(loadAdminMethodology, (module) => module.submitAdminMethodologyEditing());
  });
}

if (adminMethodologyDrawerBackdrop) {
  adminMethodologyDrawerBackdrop.addEventListener('click', () => {
    withScreen(loadAdminMethodology, (module) => module.closeAdminMethodologyDetail());
  });
}

if (adminMethodologyTabLibrary) {
  adminMethodologyTabLibrary.addEventListener('click', () => {
    state.adminMethodologyTab = 'library';
    persistAssessmentContext();
    withScreen(loadAdminMethodology, (module) => module.renderAdminMethodologyTab());
  });
}

if (adminMethodologyTabBranches) {
  adminMethodologyTabBranches.addEventListener('click', () => {
    state.adminMethodologyTab = 'branches';
    persistAssessmentContext();
    withScreen(loadAdminMethodology, (module) => module.renderAdminMethodologyTab());
  });
}

if (adminMethodologyTabPassports) {
  adminMethodologyTabPassports.addEventListener('click', () => {
    state.adminMethodologyTab = 'passports';
    persistAssessmentContext();
    withScreen(loadAdminMethodology, (module) => module.renderAdminMethodologyTab());
  });
}

if (adminReportsSearch) {
  adminReportsSearch.addEventListener('input', () => {
    state.adminReportsSearch = adminReportsSearch.value || '';
    state.adminReportsPage = 1;
    persistAssessmentContext();
    withScreen(loadAdminReports, (module) => module.renderAdminReports());
  });
}

if (adminReportsPrevButton) {
  adminReportsPrevButton.addEventListener('click', () => {
    changeAdminReportsPage(-1);
  });
}

if (adminReportsNextButton) {
  adminReportsNextButton.addEventListener('click', () => {
    changeAdminReportsPage(1);
  });
}

document.addEventListener('keydown', (event) => {
  if (
    state.currentScreen !== 'admin-reports' ||
    event.altKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.shiftKey ||
    isEditableKeyboardTarget(event.target)
  ) {
    return;
  }
  if (event.key === 'ArrowLeft' && adminReportsPrevButton && !adminReportsPrevButton.disabled) {
    event.preventDefault();
    changeAdminReportsPage(-1);
  }
  if (event.key === 'ArrowRight' && adminReportsNextButton && !adminReportsNextButton.disabled) {
    event.preventDefault();
    changeAdminReportsPage(1);
  }
});

if (adminReportsPdfButton) {
  adminReportsPdfButton.addEventListener('click', () => {
    window.location.href = '/users/admin/reports.pdf';
  });
}

if (adminReportsExpertGroupButton) {
  adminReportsExpertGroupButton.addEventListener('click', () => {
    withScreen(loadAdminReports, (module) => {
      module.renderAdminReportsGroupDialog();
      adminReportsGroupDialog?.showModal();
    });
  });
}

if (adminReportsGroupDialogList) {
  adminReportsGroupDialogList.addEventListener('change', () => {
    withScreen(loadAdminReports, (module) => module.syncAdminReportsSelectionFromDialog());
  });
}

if (adminReportsGroupDialogExport) {
  adminReportsGroupDialogExport.addEventListener('click', () => {
    const sessionIds = (state.adminReportsSelectedSessionIds || [])
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value) && value > 0);
    if (!sessionIds.length) {
      return;
    }
    const query = sessionIds.map((value) => 'session_ids=' + encodeURIComponent(String(value))).join('&');
    adminReportsGroupDialog?.close();
    window.location.href = '/users/admin/reports/export/expert-group.zip?' + query;
  });
}

if (adminReportDetailBackButton) {
  adminReportDetailBackButton.addEventListener('click', () => {
    withScreen(loadAdminReports, (module) => module.openAdminReports());
  });
}

if (adminReportDetailPdfButton) {
  adminReportDetailPdfButton.addEventListener('click', () => {
    if (!state.adminReportDetail?.user_id || !state.adminReportDetail?.session_id) {
      return;
    }
    window.location.href =
      '/users/' + state.adminReportDetail.user_id + '/assessment/' + state.adminReportDetail.session_id + '/report.pdf';
  });
}

if (adminReportDetailExpertPdfButton) {
  adminReportDetailExpertPdfButton.addEventListener('click', () => {
    if (!state.adminReportDetail?.session_id) {
      return;
    }
    window.location.href = '/users/admin/reports/' + state.adminReportDetail.session_id + '/expert.pdf';
  });
}

if (adminReportDetailDialoguesPdfButton) {
  adminReportDetailDialoguesPdfButton.addEventListener('click', () => {
    if (!state.adminReportDetail?.session_id) {
      return;
    }
    window.location.href = '/users/admin/reports/' + state.adminReportDetail.session_id + '/dialogue.pdf';
  });
}

if (adminReportDetailExpertCommentSave) {
  adminReportDetailExpertCommentSave.addEventListener('click', () => {
    withScreen(loadAdminReportDetail, (module) => module.saveAdminReportExpertComment());
  });
}

if (adminReportDetailExpertCommentEdit) {
  adminReportDetailExpertCommentEdit.addEventListener('click', () => {
    withScreen(loadAdminReportDetail, (module) => module.enableAdminReportExpertCommentEditing());
  });
}

if (adminReportDetailExpertCommentCancel) {
  adminReportDetailExpertCommentCancel.addEventListener('click', () => {
    withScreen(loadAdminReportDetail, (module) => module.cancelAdminReportExpertCommentEditing());
  });
}

if (adminReportDetailExpertComment) {
  adminReportDetailExpertComment.addEventListener('input', () => {
    if (!state.adminReportDetailExpertCommentEditing) {
      return;
    }
    withScreen(loadAdminReportDetail, (module) => {
      module.updateAdminExpertCommentDirtyState();
      if (adminReportDetailExpertCommentStatus) {
        adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
          ? 'Изменения не сохранены.'
          : '';
      }
    });
  });
}


if (adminReportDetailExpertName) {
  adminReportDetailExpertName.addEventListener('input', () => {
    if (!state.adminReportDetailExpertCommentEditing) {
      return;
    }
    withScreen(loadAdminReportDetail, (module) => {
      module.updateAdminExpertCommentDirtyState();
      if (adminReportDetailExpertCommentStatus) {
        adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
          ? 'Изменения не сохранены.'
          : '';
      }
    });
  });
}

if (adminReportDetailExpertContacts) {
  adminReportDetailExpertContacts.addEventListener('input', () => {
    if (!state.adminReportDetailExpertCommentEditing) {
      return;
    }
    withScreen(loadAdminReportDetail, (module) => {
      module.updateAdminExpertCommentDirtyState();
      if (adminReportDetailExpertCommentStatus) {
        adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
          ? 'Изменения не сохранены.'
          : '';
      }
    });
  });
}

if (adminReportDetailExpertAssessedAt) {
  adminReportDetailExpertAssessedAt.addEventListener('input', () => {
    if (!state.adminReportDetailExpertCommentEditing) {
      return;
    }
    withScreen(loadAdminReportDetail, (module) => {
      module.updateAdminExpertCommentDirtyState();
      if (adminReportDetailExpertCommentStatus) {
        adminReportDetailExpertCommentStatus.textContent = state.adminReportDetailExpertCommentDirty
          ? 'Изменения не сохранены.'
          : '';
      }
    });
  });
}

dashboardProfileButton.addEventListener('click', () => {
  withScreen(loadProfile, (module) => module.openProfile());
});

if (adminProfileButton) {
  adminProfileButton.addEventListener('click', () => {
    withScreen(loadProfile, (module) => module.openProfile());
  });
}

welcomeProfileButton.addEventListener('click', () => {
  withScreen(loadProfile, (module) => module.openProfile());
});


assessmentActionButton.addEventListener('click', () => {
  withScreen(loadInterview, (module) => module.handleAssessmentEntryClick());
});

startFirstAssessmentButton.addEventListener('click', () => {
  withScreen(loadInterview, (module) => module.handleAssessmentEntryClick());
});

libraryStartButton.addEventListener('click', () => {
  withScreen(loadInterview, (module) => module.handleAssessmentEntryClick());
});

prechatStartButton.addEventListener('click', () => {
  void (async () => {
    const [assessmentModule, dashboardModule] = await Promise.all([loadAssessment(), loadDashboard()]);
    if (state.assessmentPreparationStatus === 'failed') {
      void assessmentModule.retryAssessmentPreparation();
      return;
    }
    if (!assessmentModule.canReusePreparedAssessment() && !dashboardModule.hasIncompleteAssessment()) {
      void assessmentModule.beginAssessmentPreparation({ force: true });
      return;
    }
    const interviewModule = await loadInterview();
    void interviewModule.startAssessmentInterview();
  })();
});

newUserExitButton.addEventListener('click', () => {
  void logoutAndReturnToStart(newUserExitButton);
});

if (prechatExitButton) {
  prechatExitButton.addEventListener('click', () => {
    void logoutAndReturnToStart(prechatExitButton);
  });
}

interviewForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  showError(interviewError, '');

  const text = interviewTextarea.value.trim();
  if (!text) {
    showError(interviewError, 'Введите ответ по текущему кейсу.');
    return;
  }
  if (!state.assessmentSessionCode) {
    showError(interviewError, 'Сессия кейсового интервью не инициализирована.');
    return;
  }

  try {
    const interviewModule = await loadInterview();
    interviewModule.addInterviewMessage('user', text);
    interviewTextarea.value = '';
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    interviewModule.clearInterviewTimer();
    await interviewModule.submitAssessmentMessage(text);
  } catch (error) {
    showError(interviewError, error.message);
    interviewTextarea.disabled = false;
    interviewSubmitButton.disabled = false;
    interviewFinishButton.disabled = false;
    const interviewModule = await loadInterview();
    if (!interviewModule.updateInterviewTimer()) {
      state.assessmentTimerId = window.setInterval(() => {
        if (typeof state.assessmentRemainingSeconds === 'number' && state.assessmentRemainingSeconds > 0) {
          state.assessmentRemainingSeconds -= 1;
        }
        if (interviewModule.updateInterviewTimer() && !state.assessmentTimeoutInFlight) {
          state.assessmentTimeoutInFlight = true;
          interviewTextarea.disabled = true;
          interviewSubmitButton.disabled = true;
          interviewFinishButton.disabled = true;
          void interviewModule.submitAssessmentMessage('__timeout__');
        }
      }, 1000);
    }
  }
});

interviewFinishButton.addEventListener('click', async () => {
  showError(interviewError, '');

  if (!state.assessmentSessionCode) {
    showError(interviewError, 'Сессия кейсового интервью не инициализирована.');
    return;
  }

  interviewTextarea.disabled = true;
  interviewSubmitButton.disabled = true;
  interviewFinishButton.disabled = true;

  try {
    const interviewModule = await loadInterview();
    interviewModule.clearInterviewTimer();
    await interviewModule.submitAssessmentMessage('__finish_case__');
  } catch (error) {
    showError(interviewError, error.message);
    interviewTextarea.disabled = false;
    interviewSubmitButton.disabled = false;
    interviewFinishButton.disabled = false;
  }
});

interviewGoProcessingButton.addEventListener('click', () => {
  safeStorage.setItem(STORAGE_KEYS.completionPending, '1');
  withScreen(loadProcessing, (module) => module.openProcessing());
});

if (interviewBackButton) {
  interviewBackButton.addEventListener('click', () => {
    navigateBackOrFallback(() => {
      withScreen(loadAiWelcome, (module) => module.openPrechat());
    });
  });
}

if (interviewProfileButton) {
  interviewProfileButton.addEventListener('click', () => {
    withScreen(loadAiWelcome, (module) => module.openHomePage());
  });
}

if (interviewExitButton) {
  interviewExitButton.addEventListener('click', (event) => {
    void logoutAndReturnToStart(event.currentTarget);
  });
}

processingBackButton.addEventListener('click', () => {
  withScreen(loadChat, (module) => module.clearProcessingTimer());
  withScreen(loadAiWelcome, (module) => module.openWelcomeScreen());
});

reportHomeButton.addEventListener('click', () => {
  withScreen(loadAiWelcome, (module) => module.openHomePage());
});

if (reportBackButton) {
  reportBackButton.addEventListener('click', () => {
    withScreen(loadReport, (module) => module.handleReportBack());
  });
}

if (reportInfoModal) {
  reportInfoModal.addEventListener('click', (event) => {
    if (event.target === reportInfoModal) {
      withScreen(loadReport, (module) => module.closeReportInfoModal());
    }
  });
}

if (reportInfoModalClose) {
  reportInfoModalClose.addEventListener('click', () => {
    withScreen(loadReport, (module) => module.closeReportInfoModal());
  });
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && reportInfoModal && !reportInfoModal.classList.contains('hidden')) {
    withScreen(loadReport, (module) => module.closeReportInfoModal());
  }
});

profileBackButton.addEventListener('click', () => {
  withScreen(loadAiWelcome, (module) => module.openWelcomeScreen());
});

profileAvatarInput.addEventListener('change', () => {
  const [file] = Array.from(profileAvatarInput.files || []);
  if (!file) {
    return;
  }
  if (!file.type.startsWith('image/')) {
    setProfileStatus('Можно загрузить только изображение.', 'error');
    profileAvatarInput.value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    state.profileAvatarDraft = typeof reader.result === 'string' ? reader.result : null;
    withScreen(loadProfile, (module) => {
      module.renderProfile();
      void module.saveProfile({
        silent: false,
        successMessage: 'Фото профиля обновлено.',
      });
    });
    profileAvatarInput.value = '';
  };
  reader.onerror = () => {
    setProfileStatus('Не удалось прочитать изображение.', 'error');
  };
  reader.readAsDataURL(file);
});

profileEmail.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    profileEmail.blur();
  }
});

profileEmail.addEventListener('blur', () => {
  const currentEmail = state.profileSummary?.user?.email || state.pendingUser?.email || '';
  const nextEmail = profileEmail.value.trim();
  if (nextEmail === currentEmail) {
    return;
  }
  withScreen(loadProfile, (module) =>
    module.saveProfile({
      silent: false,
      successMessage: 'Email обновлен.',
    }),
  );
});

profileTelegram.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    profileTelegram.blur();
  }
});

profileTelegram.addEventListener('blur', () => {
  const currentTelegram = state.profileSummary?.user?.telegram || state.pendingUser?.telegram || '';
  const nextTelegram = profileTelegram.value.trim();
  if (nextTelegram === currentTelegram) {
    return;
  }
  withScreen(loadProfile, (module) =>
    module.saveProfile({
      silent: false,
      successMessage: 'Telegram обновлен.',
    }),
  );
});

if (reportsBackButton) {
  reportsBackButton.addEventListener('click', () => {
    withScreen(loadAiWelcome, (module) => module.openWelcomeScreen());
  });
}

reportDownloadButton.addEventListener('click', () => {
  if (!state.pendingUser?.id || !state.assessmentSessionId) {
    return;
  }
  window.location.href = '/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/report.pdf';
});

};
