import { state, persistAssessmentContext, clearAssessmentContext, safeStorage, STORAGE_KEYS, setCurrentScreen, applyJourneyAssessmentContext } from './state.js';
import {
  authEmailForm,
  emailInput,
  authTokenForm,
  authCredentialEmailInput,
  authCredentialLabel,
  magicTokenInput,
  authPasswordConfirmField,
  authPasswordRequirements,
  authPasswordGenerateRow,
  authPasswordGenerateButton,
  authPasswordToggleButton,
  authPasswordConfirmInput,
  authPasswordConfirmToggleButton,
  requestMagicLinkButton,
  forgotPasswordButton,
  forgotPasswordCredentialButton,
  authTitle,
  authSubtitle,
  authEmailSent,
  authEmailSentAddress,
  authResendEmailButton,
  authResendCountdown,
  authChangeEmailButton,
  verifyMagicLinkButton,
  authStatus,
  authError,
  organizationInvitationContext,
  organizationInvitationName,
  organizationInvitationIntro,
  authChangeCredentialEmailButton,
  authCompleteContinueButton,
  authCompleteLogoutButton,
  chatForm,
  chatInput,
  restartButton,
  dashboardRestartButton,
  dashboardMobileExitButton,
  participantReturnManagementButton,
  dashboardProfileButton,
  dashboardOnboardingButton,
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
  adminRegressionTestsRunOfflineButton,
  adminRegressionTestsRunTechnicalButton,
  adminRegressionTestsRunFullButton,
  adminRegressionTestsCleanupButton,
  adminOrganizationsBackButton,
  adminOrganizationCreateForm,
  adminOrganizationSelect,
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
  interviewPanel,
  interviewForm,
  interviewMessages,
  interviewTextarea,
  interviewSubmitButton,
  interviewSubmitLabel,
  interviewFinishButton,
  interviewPauseButton,
  interviewAdditionalButton,
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

let organizationInvitationToken = '';

const renderOrganizationInvitation = (organization) => {
  const available = Boolean(organization?.organization_name);
  organizationInvitationContext?.classList.toggle('hidden', !available);
  if (organizationInvitationName) organizationInvitationName.textContent = available ? organization.organization_name : '';
  if (organizationInvitationIntro) organizationInvitationIntro.textContent = available ? organization.invitation_intro || '' : '';
};

export const activateOrganizationInvitation = async (tokenValue) => {
  const token = String(tokenValue || '').trim();
  if (!token) {
    organizationInvitationToken = '';
    renderOrganizationInvitation(null);
    return null;
  }
  const response = await fetch('/users/organization-invitations/' + encodeURIComponent(token));
  const organization = await readApiResponse(response, 'Приглашение недействительно или устарело.', {
    recoverUnauthorized: false,
  });
  organizationInvitationToken = token;
  renderOrganizationInvitation(organization);
  if (organization?.personal && organization?.recipient_email) {
    try { window.sessionStorage.setItem('agent4k.organizationInvitationToken', token); } catch (_error) { /* optional */ }
    window.history.replaceState({ screen: 'auth' }, '', '/');
    authCredentialEmail = organization.recipient_email;
    if (emailInput) emailInput.value = authCredentialEmail;
    configureAuthCredentialForm(organization.auth_mode === 'password' ? 'password' : 'password_registration');
    if (authTokenForm) authTokenForm.classList.remove('hidden');
    setAuthStatus(
      organization.auth_mode === 'password'
        ? `Приглашение подтверждено для ${organization.recipient_email}. Вход переключит текущий аккаунт на получателя приглашения.`
        : `Приглашение подтверждено для ${organization.recipient_email}. Создайте пароль, чтобы продолжить знакомство.`,
    );
    const conflict = document.getElementById('organization-invitation-account-conflict');
    const conflictCopy = document.getElementById('organization-invitation-account-conflict-copy');
    try {
      const currentResponse = await fetch('/users/session/restore', { credentials: 'same-origin', cache: 'no-store' });
      const current = await readApiResponse(currentResponse, 'Не удалось проверить текущий аккаунт.', { recoverUnauthorized: false });
      const currentEmail = normalizeCredentialEmail(current?.user?.email);
      const recipientEmail = normalizeCredentialEmail(organization.recipient_email);
      const hasConflict = Boolean(current?.authenticated && currentEmail && currentEmail !== recipientEmail);
      conflict?.classList.toggle('hidden', !hasConflict);
      if (hasConflict && conflictCopy) {
        conflictCopy.textContent = `Сейчас открыт аккаунт ${currentEmail}. Приглашение предназначено для ${recipientEmail}.`;
      }
    } catch {
      conflict?.classList.add('hidden');
    }
    magicTokenInput?.focus();
  } else {
    try { window.sessionStorage.setItem('agent4k.organizationInvitationToken', token); } catch (_error) { /* optional */ }
  }
  return organization;
};

document.getElementById('organization-invitation-continue-button')?.addEventListener('click', () => {
  document.getElementById('organization-invitation-account-conflict')?.classList.add('hidden');
  magicTokenInput?.focus();
});
document.getElementById('organization-invitation-keep-session-button')?.addEventListener('click', () => {
  organizationInvitationToken = '';
  try { window.sessionStorage.removeItem('agent4k.organizationInvitationToken'); } catch (_error) { /* optional */ }
  window.location.assign('/');
});
import { advanceSessionGeneration, readApiResponse, createOperationId } from './api.js';
import {
  buildExistingUserAgentMessage,
  shouldOfferNoChangesQuickReply,
  hasRequiredProfileFields,
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
  loadInterview,
  loadProcessing,
  loadReport,
  loadDashboard,
  loadAdminDashboard,
  loadAdminOrganizations,
  loadAdminRegressionTests,
  loadAdminPromptLab,
  loadAdminReports,
  loadAdminMethodology,
  loadAdminReportDetail,
  openOnboardingScreen,
} from './screen-loaders.js';
import { ASSESSMENT_EXTERNAL_ANSWER_TRANSFER_ENABLED } from './config.js';

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
let authCredentialStep = 1;
let newPasswordDraft = '';
let authCredentialEmail = '';
let authPasswordVisible = false;
let authPasswordConfirmVisible = false;
let authActionToken = '';
let authResendTimer = null;
let authRequestInFlight = false;
let authCredentialInFlight = false;
let authResetRequestInFlight = false;
let authPendingEmailAction = 'verification';
let authPendingTokenAction = '';
let authOperationGeneration = 0;
const AUTH_RESEND_TIMING_KEY = 'agent4k.authResendTiming';

const stopAuthResendCountdown = () => {
  if (authResendTimer) {
    window.clearInterval(authResendTimer);
    authResendTimer = null;
  }
};

const startAuthResendCountdown = (timing = null) => {
  stopAuthResendCountdown();
  let deadline = Number(timing?.deadline || 0);
  if (!deadline && timing?.next_request_at && timing?.server_time) {
    const serverRemaining = Date.parse(timing.next_request_at) - Date.parse(timing.server_time);
    if (Number.isFinite(serverRemaining)) deadline = Date.now() + Math.max(0, serverRemaining);
  }
  if (!deadline && timing?.next_request_at) deadline = Date.parse(timing.next_request_at);
  if (!deadline && Number.isFinite(Number(timing?.retry_after_seconds))) {
    deadline = Date.now() + Math.max(0, Number(timing.retry_after_seconds)) * 1000;
  }
  if (!deadline) {
    try { deadline = Number(JSON.parse(window.localStorage.getItem(AUTH_RESEND_TIMING_KEY) || '{}').deadline || 0); }
    catch (_error) { deadline = 0; }
  }
  if (deadline > Date.now()) {
    try { window.localStorage.setItem(AUTH_RESEND_TIMING_KEY, JSON.stringify({ deadline })); } catch (_error) { /* no storage */ }
  }
  const render = () => {
    if (!authResendEmailButton) return;
    const secondsLeft = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    authResendEmailButton.disabled = secondsLeft > 0;
    authResendEmailButton.textContent = 'Отправить повторно';
    if (authResendCountdown) {
      authResendCountdown.hidden = secondsLeft <= 0;
      authResendCountdown.textContent = `Повторная отправка доступна через ${secondsLeft} сек.`;
    }
  };
  render();
  authResendTimer = window.setInterval(() => {
    render();
    if (deadline <= Date.now()) {
      stopAuthResendCountdown();
      try { window.localStorage.removeItem(AUTH_RESEND_TIMING_KEY); } catch (_error) { /* no storage */ }
    }
  }, 1000);
};

const showEmailVerificationPending = (email, timing = null) => {
  authPendingEmailAction = 'verification';
  authResendEmailButton?.classList.remove('hidden');
  if (authResendCountdown) authResendCountdown.hidden = false;
  authEmailForm?.classList.add('hidden');
  authTokenForm?.classList.add('hidden');
  authEmailSent?.classList.remove('hidden');
  authTitle?.classList.add('hidden');
  authSubtitle?.classList.add('hidden');
  if (authEmailSentAddress) authEmailSentAddress.textContent = email;
  const title = authEmailSent?.querySelector('h2');
  const paragraphs = authEmailSent?.querySelectorAll('.auth-email-sent-copy p');
  if (title) title.textContent = 'Проверьте почту';
  if (paragraphs?.[0]) paragraphs[0].innerHTML = 'Мы отправили ссылку для подтверждения на <strong id="auth-email-sent-address"></strong>.';
  const sentAddress = document.getElementById('auth-email-sent-address');
  if (sentAddress) sentAddress.textContent = email;
  if (paragraphs?.[1]) paragraphs[1].textContent = 'Продолжите регистрацию во вкладке, которая откроется из письма. Эту вкладку можно закрыть.';
  if (authChangeEmailButton) authChangeEmailButton.textContent = 'Изменить email';
  setAuthStatus('');
  showError(authError, '');
  startAuthResendCountdown(timing);
};

const showAccessUnavailable = (email) => {
  authPendingEmailAction = 'access';
  authEmailForm?.classList.add('hidden');
  authTokenForm?.classList.add('hidden');
  authEmailSent?.classList.remove('hidden');
  authTitle?.classList.add('hidden');
  authSubtitle?.classList.add('hidden');
  const title = authEmailSent?.querySelector('h2');
  const paragraphs = authEmailSent?.querySelectorAll('.auth-email-sent-copy p');
  if (title) title.textContent = 'Доступ пока не открыт';
  if (paragraphs?.[0]) paragraphs[0].textContent = 'Этот email пока не добавлен в список участников организации. Проверьте адрес или обратитесь к HR либо организатору оценки.';
  if (paragraphs?.[1]) paragraphs[1].textContent = email;
  if (authResendEmailButton) {
    authResendEmailButton.disabled = false;
    authResendEmailButton.textContent = 'Проверить снова';
  }
  if (authResendCountdown) authResendCountdown.hidden = true;
  if (authChangeEmailButton) authChangeEmailButton.textContent = 'Изменить email';
  setAuthStatus('');
  showError(authError, '');
};

const showEmailEntry = () => {
  authOperationGeneration += 1;
  authCredentialInFlight = false;
  stopAuthResendCountdown();
  authEmailSent?.classList.add('hidden');
  authTokenForm?.classList.add('hidden');
  authEmailForm?.classList.remove('hidden');
  authTitle?.classList.remove('hidden');
  authSubtitle?.classList.remove('hidden');
  authResendEmailButton?.classList.remove('hidden');
  if (authResendCountdown) authResendCountdown.hidden = true;
  if (authTitle) authTitle.textContent = 'Добро пожаловать';
  if (authSubtitle) authSubtitle.textContent = 'Введите рабочий email, чтобы продолжить вход.';
  if (requestMagicLinkButton) requestMagicLinkButton.textContent = 'Продолжить';
  forgotPasswordButton?.classList.add('hidden');
  setAuthStatus('');
  showError(authError, '');
  emailInput?.focus();
};

const syncAuthPasswordVisibility = () => {
  const isRegistration = authCredentialMode === 'password_registration';
  const isPasswordMode = authCredentialMode === 'password' || authCredentialMode === 'password_reset' || isRegistration;
  if (magicTokenInput) {
    magicTokenInput.type = isPasswordMode && authPasswordVisible ? 'text' : isPasswordMode ? 'password' : 'text';
  }
  if (authPasswordConfirmInput) {
    authPasswordConfirmInput.type = authPasswordConfirmVisible ? 'text' : 'password';
  }
  if (authPasswordToggleButton) {
    authPasswordToggleButton.textContent = authPasswordVisible ? 'Скрыть' : 'Показать';
  }
  if (authPasswordConfirmToggleButton) {
    authPasswordConfirmToggleButton.textContent = authPasswordConfirmVisible ? 'Скрыть' : 'Показать';
  }
};

const passwordRandomInt = (max) => {
  if (window.crypto?.getRandomValues) {
    const bucket = new Uint32Array(1);
    window.crypto.getRandomValues(bucket);
    return bucket[0] % max;
  }
  return Math.floor(Math.random() * max);
};

const shufflePasswordChars = (chars) => {
  const result = [...chars];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swapIndex = passwordRandomInt(index + 1);
    [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
  }
  return result.join('');
};

const generateStrongPassword = () => {
  const lower = 'abcdefghijkmnopqrstuvwxyz';
  const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
  const digits = '23456789';
  const symbols = '!@#$%+-_=';
  const all = lower + upper + digits + symbols;
  const chars = [
    lower[passwordRandomInt(lower.length)],
    upper[passwordRandomInt(upper.length)],
    digits[passwordRandomInt(digits.length)],
    symbols[passwordRandomInt(symbols.length)],
  ];
  while (chars.length < 10) {
    chars.push(all[passwordRandomInt(all.length)]);
  }
  return shufflePasswordChars(chars);
};

const normalizeCredentialEmail = (value) => String(value || '').trim().toLowerCase();

const fillStoredPasswordIfAvailable = async () => {
  if (authCredentialMode !== 'password' || !magicTokenInput || magicTokenInput.value) {
    return;
  }
  if (!window.PasswordCredential || !navigator.credentials?.get) {
    return;
  }
  const email = normalizeCredentialEmail(authCredentialEmail || emailInput?.value);
  if (!email) {
    return;
  }
  try {
    const credential = await navigator.credentials.get({
      password: true,
      mediation: 'optional',
    });
    if (
      credential?.type === 'password' &&
      normalizeCredentialEmail(credential.id) === email &&
      typeof credential.password === 'string'
    ) {
      magicTokenInput.value = credential.password;
    }
  } catch {
    // Browser password managers are optional; login must keep working without them.
  }
};

const offerPasswordSave = async ({ email, password }) => {
  if (!window.PasswordCredential || !navigator.credentials?.store) {
    return;
  }
  const normalizedEmail = normalizeCredentialEmail(email);
  if (!normalizedEmail || !password) {
    return;
  }
  try {
    await navigator.credentials.store(
      new window.PasswordCredential({
        id: normalizedEmail,
        name: normalizedEmail,
        password,
      }),
    );
  } catch {
    // A declined or unsupported save prompt should not block successful auth.
  }
};

const configureAuthCredentialForm = (mode) => {
  authCredentialMode = mode || 'dev_token';
  const isRegistration = authCredentialMode === 'password_registration';
  const isReset = authCredentialMode === 'password_reset';
  const isNewPassword = isRegistration || isReset;
  const isPasswordMode = authCredentialMode === 'password' || isNewPassword;
  const authPanel = authTokenForm?.closest('.auth-panel');
  const stepIndicator = document.getElementById('auth-credential-step-indicator');
  authPanel?.classList.toggle('auth-panel--password-create', isNewPassword);
  stepIndicator?.classList.toggle('hidden', !isNewPassword);
  if (stepIndicator) {
    stepIndicator.textContent = 'Шаг 1 из 2';
    stepIndicator.dataset.step = '1';
  }
  authEmailForm?.classList.add('hidden');
  authEmailSent?.classList.add('hidden');
  authTitle?.classList.remove('hidden');
  authSubtitle?.classList.remove('hidden');
  authCredentialStep = 1;
  newPasswordDraft = '';
  if (authTitle) authTitle.textContent = isReset ? 'Создайте новый пароль' : isRegistration ? 'Создайте пароль' : 'С возвращением';
  if (authSubtitle) authSubtitle.textContent = isReset
    ? 'Задайте новый пароль для рабочего аккаунта.'
    : isRegistration
      ? 'Он понадобится для следующих входов в систему.'
      : `Введите пароль для ${authCredentialEmail || 'рабочего аккаунта'}.`;
  if (authCredentialLabel) {
    authCredentialLabel.textContent = isPasswordMode ? 'Пароль' : 'Код или ссылка для входа';
  }
  authPasswordVisible = false;
  authPasswordConfirmVisible = false;
  if (authCredentialEmailInput) {
    authCredentialEmailInput.value = String(authCredentialEmail || emailInput?.value || '').trim();
  }
  if (magicTokenInput) {
    magicTokenInput.name = isNewPassword ? 'new-password' : isPasswordMode ? 'password' : 'one-time-code';
    magicTokenInput.autocomplete = isNewPassword ? 'new-password' : isPasswordMode ? 'current-password' : 'one-time-code';
    magicTokenInput.placeholder = isPasswordMode ? 'Введите пароль' : 'Вставьте код или ссылку из письма';
    magicTokenInput.value = '';
  }
  if (authPasswordConfirmField) authPasswordConfirmField.classList.add('hidden');
  if (authPasswordConfirmInput) {
    authPasswordConfirmInput.name = isRegistration ? 'new-password-confirm' : 'password-confirm-disabled';
    authPasswordConfirmInput.required = false;
    authPasswordConfirmInput.value = '';
  }
  if (authPasswordRequirements) {
    authPasswordRequirements.classList.toggle('hidden', !isNewPassword);
  }
  if (authPasswordGenerateRow) {
    authPasswordGenerateRow.classList.toggle('hidden', !isNewPassword);
  }
  if (authPasswordToggleButton) {
    authPasswordToggleButton.classList.toggle('hidden', !isPasswordMode);
  }
  if (authPasswordConfirmToggleButton) {
    authPasswordConfirmToggleButton.classList.add('hidden');
  }
  syncAuthPasswordVisibility();
  if (verifyMagicLinkButton) {
    verifyMagicLinkButton.textContent = 'Продолжить';
  }
  forgotPasswordCredentialButton?.classList.toggle('hidden', authCredentialMode !== 'password');
};

const NEW_PASSWORD_ERROR = 'Используйте не менее 10 символов: заглавную и строчную латинские буквы, цифру и спецсимвол. Пробелы и кириллица не допускаются.';
const isValidNewPassword = (value) => /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9])[!-~]{10,}$/.test(value);

const showPasswordConfirmationStep = () => {
  authCredentialStep = 2;
  const stepIndicator = document.getElementById('auth-credential-step-indicator');
  if (stepIndicator) {
    stepIndicator.textContent = 'Шаг 2 из 2';
    stepIndicator.dataset.step = '2';
  }
  authPasswordVisible = false;
  if (authTitle) authTitle.textContent = authCredentialMode === 'password_reset'
    ? 'Подтвердите новый пароль'
    : 'Подтвердите пароль';
  if (authSubtitle) authSubtitle.textContent = 'Введите пароль повторно';
  if (authCredentialLabel) authCredentialLabel.textContent = 'Введите пароль повторно';
  if (magicTokenInput) {
    magicTokenInput.value = '';
    magicTokenInput.placeholder = 'Введите пароль повторно';
  }
  authPasswordGenerateRow?.classList.add('hidden');
  if (verifyMagicLinkButton) {
    verifyMagicLinkButton.textContent = authCredentialMode === 'password_reset' ? 'Сохранить пароль' : 'Создать пароль';
  }
  if (authChangeCredentialEmailButton) authChangeCredentialEmailButton.textContent = 'Вернуться назад';
  syncAuthPasswordVisibility();
  magicTokenInput?.focus();
};

const showPasswordCreationStep = () => {
  authCredentialStep = 1;
  const stepIndicator = document.getElementById('auth-credential-step-indicator');
  if (stepIndicator) {
    stepIndicator.textContent = 'Шаг 1 из 2';
    stepIndicator.dataset.step = '1';
  }
  authPasswordVisible = false;
  const isReset = authCredentialMode === 'password_reset';
  if (authTitle) authTitle.textContent = isReset ? 'Создайте новый пароль' : 'Создайте пароль';
  if (authSubtitle) authSubtitle.textContent = isReset ? 'Он заменит ваш текущий пароль' : 'Он понадобится для следующих входов в систему.';
  if (authCredentialLabel) authCredentialLabel.textContent = 'Пароль';
  if (magicTokenInput) {
    magicTokenInput.value = newPasswordDraft;
    magicTokenInput.placeholder = 'Введите пароль';
  }
  authPasswordGenerateRow?.classList.remove('hidden');
  if (verifyMagicLinkButton) verifyMagicLinkButton.textContent = 'Продолжить';
  if (authChangeCredentialEmailButton) authChangeCredentialEmailButton.textContent = 'Вернуться назад';
  syncAuthPasswordVisibility();
  magicTokenInput?.focus();
};

const showPasswordResetComplete = (email) => {
  authPendingEmailAction = 'reset-complete';
  authCredentialMode = 'password';
  authCredentialStep = 1;
  newPasswordDraft = '';
  authTokenForm?.classList.add('hidden');
  authEmailForm?.classList.add('hidden');
  authEmailSent?.classList.remove('hidden');
  const title = authEmailSent?.querySelector('h2');
  const paragraphs = authEmailSent?.querySelectorAll('.auth-email-sent-copy p');
  if (title) title.textContent = 'Пароль изменён';
  if (paragraphs?.[0]) paragraphs[0].textContent = 'Новый пароль сохранён. Вернитесь ко входу.';
  if (paragraphs?.[1]) paragraphs[1].textContent = email;
  authResendEmailButton?.classList.add('hidden');
  if (authChangeEmailButton) authChangeEmailButton.textContent = 'Вернуться ко входу';
};

const isNewPasswordMode = () => authCredentialMode === 'password_registration' || authCredentialMode === 'password_reset';
const hasUnsupportedPasswordChars = (value) => /[^!-~]/.test(String(value || ''));

magicTokenInput?.addEventListener('keydown', (event) => {
  if (isNewPasswordMode() && event.key === ' ' && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault();
    showError(authError, 'Пробелы в пароле не допускаются.');
  }
});

magicTokenInput?.addEventListener('beforeinput', (event) => {
  if (isNewPasswordMode() && typeof event.data === 'string' && hasUnsupportedPasswordChars(event.data)) {
    event.preventDefault();
    showError(authError, 'Пробелы и кириллица в пароле не допускаются.');
  }
});

magicTokenInput?.addEventListener('paste', (event) => {
  const value = event.clipboardData?.getData('text') || '';
  if (isNewPasswordMode() && hasUnsupportedPasswordChars(value)) {
    event.preventDefault();
    showError(authError, 'Вставка отклонена: пробелы и кириллица в пароле не допускаются.');
  }
});

magicTokenInput?.addEventListener('input', () => {
  magicTokenInput.removeAttribute('aria-invalid');
  showError(authError, '');
});

const requirementsTrigger = document.getElementById('auth-password-requirements-trigger');
const requirementsPopover = document.getElementById('auth-password-requirements-popover');
let requirementsCloseTimer = null;
const positionRequirementsPopover = () => {
  if (!requirementsTrigger || !requirementsPopover || requirementsPopover.classList.contains('hidden')) return;
  const trigger = requirementsTrigger.getBoundingClientRect();
  const popover = requirementsPopover.getBoundingClientRect();
  const margin = 16;
  const gap = 6;
  const left = Math.min(
    Math.max(trigger.left, margin),
    Math.max(margin, window.innerWidth - popover.width - margin),
  );
  const fitsAbove = trigger.top - gap - popover.height >= margin;
  const top = fitsAbove
    ? trigger.top - gap - popover.height
    : Math.min(trigger.bottom + gap, window.innerHeight - popover.height - margin);
  requirementsPopover.style.left = `${left}px`;
  requirementsPopover.style.top = `${Math.max(margin, top)}px`;
};
const setRequirementsOpen = (open) => {
  if (requirementsCloseTimer) {
    window.clearTimeout(requirementsCloseTimer);
    requirementsCloseTimer = null;
  }
  requirementsPopover?.classList.toggle('hidden', !open);
  requirementsTrigger?.setAttribute('aria-expanded', String(open));
  if (open) window.requestAnimationFrame(positionRequirementsPopover);
};
requirementsTrigger?.addEventListener('pointerdown', (event) => {
  const open = requirementsTrigger.getAttribute('aria-expanded') === 'true';
  const openedByHover = requirementsTrigger.dataset.openedByHover === 'true';
  event.preventDefault();
  requirementsTrigger.focus();
  setRequirementsOpen(openedByHover ? true : !open);
  delete requirementsTrigger.dataset.openedByHover;
});
requirementsTrigger?.addEventListener('click', (event) => {
  if (event.detail !== 0) return;
  setRequirementsOpen(requirementsTrigger.getAttribute('aria-expanded') !== 'true');
});
requirementsTrigger?.addEventListener('focus', () => setRequirementsOpen(true));
requirementsTrigger?.addEventListener('mouseenter', () => {
  if (requirementsTrigger.getAttribute('aria-expanded') !== 'true') {
    requirementsTrigger.dataset.openedByHover = 'true';
  }
  setRequirementsOpen(true);
});
authPasswordRequirements?.addEventListener('mouseleave', () => {
  requirementsCloseTimer = window.setTimeout(() => setRequirementsOpen(false), 150);
});
requirementsPopover?.addEventListener('mouseenter', () => setRequirementsOpen(true));
window.addEventListener('resize', positionRequirementsPopover);
window.addEventListener('scroll', positionRequirementsPopover, true);
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') setRequirementsOpen(false); });
document.addEventListener('pointerdown', (event) => {
  if (authPasswordRequirements && !authPasswordRequirements.contains(event.target)) setRequirementsOpen(false);
});

if (authPasswordToggleButton) {
  authPasswordToggleButton.addEventListener('click', () => {
    authPasswordVisible = !authPasswordVisible;
    syncAuthPasswordVisibility();
    magicTokenInput?.focus();
  });
}

if (authPasswordConfirmToggleButton) {
  authPasswordConfirmToggleButton.addEventListener('click', () => {
    authPasswordConfirmVisible = !authPasswordConfirmVisible;
    syncAuthPasswordVisibility();
    authPasswordConfirmInput?.focus();
  });
}

if (authPasswordGenerateButton) {
  authPasswordGenerateButton.addEventListener('click', () => {
    const password = generateStrongPassword();
    if (magicTokenInput) {
      magicTokenInput.value = password;
    }
    authPasswordVisible = true;
    syncAuthPasswordVisibility();
    magicTokenInput?.focus();
  });
}

const applyAuthResponse = async (data) => {
  organizationInvitationToken = '';
  try { window.sessionStorage.removeItem('agent4k.organizationInvitationToken'); } catch (_error) { /* optional */ }
  if (state.pendingUser?.id !== data.user?.id) clearAssessmentContext();
  const agent = data.agent || null;
  renderOrganizationInvitation(data.organization || null);

  advanceSessionGeneration();

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
  state.pendingNoChangesQuickReply = data.exists && shouldOfferNoChangesQuickReply(state.pendingAgentMessage) && hasRequiredProfileFields(data.user);

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
  try {
    const { loadUserJourneyState } = await import('./session.js');
    const journey = await loadUserJourneyState();
    applyJourneyAssessmentContext(journey);
    if (journey?.next_action === 'wait_for_acquaintance_data') {
      const { openAcquaintanceWaiting } = await import('./router.js');
      openAcquaintanceWaiting(journey.acquaintance?.readiness);
      return;
    }
    if (journey?.next_action === 'show_onboarding') {
      await openOnboardingScreen({ currentStep: Number(journey.onboarding?.current_step || 0) });
      return;
    }
    if (journey?.next_action === 'complete_profile') {
      const profileRecovery = await import('./screens/profile-recovery.js');
      await profileRecovery.recoverProfileCompletionForAssessment({ resumeAssessment: false });
      return;
    }
    if (journey?.next_action === 'show_dashboard') {
      const module = await loadDashboard();
      module.openDashboard();
      return;
    }
    if (journey?.next_action === 'resume_assessment') {
      if (state.assessmentRuntimeKind === 'cycle' && state.productCycleId) {
        const response = await fetch('/users/assessment/cycles/' + encodeURIComponent(state.productCycleId) + '/runtime', { credentials: 'same-origin' });
        if (!response.ok) throw new Error('Cycle runtime is not available');
        const module = await import('./screen-loaders.js');
        (await module.loadInterview()).openInterview();
        return;
      }
      const module = await loadAiWelcome();
      module.openPrechat();
      return;
    }
    if (['show_processing', 'show_assessment_error'].includes(journey?.next_action)) {
      const module = await loadProcessing();
      module.openProcessing({
        initialCycleSnapshot: state.assessmentRuntimeKind === 'cycle' ? {
          results_status: journey?.assessment?.status === 'failed' ? 'failed' : 'processing',
          report_status: journey?.report_status || 'not_ready',
        } : null,
      });
      return;
    }
    throw new Error(`Неизвестный серверный этап: ${journey?.next_action || 'empty'}`);
  } catch (error) {
    console.error('Failed to route authenticated user', error);
    showError(authError, 'Не удалось определить актуальный этап. Обновите страницу или повторите вход.');
    return;
  }
};

const handleEmailMagicLinkRequest = async () => {
  if (authRequestInFlight) return;
  showError(authError, '');
  setAuthStatus('');

  const email = emailInput.value.trim();
  if (!email) {
    showError(authError, 'Введите рабочий email');
    emailInput.setAttribute('aria-invalid', 'true');
    emailInput.focus();
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showError(authError, 'Введите email в формате name@company.ru');
    emailInput.setAttribute('aria-invalid', 'true');
    emailInput.focus();
    return;
  }
  emailInput.removeAttribute('aria-invalid');

  try {
    authRequestInFlight = true;
    if (requestMagicLinkButton) {
      requestMagicLinkButton.disabled = true;
      requestMagicLinkButton.setAttribute('aria-busy', 'true');
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
      body: JSON.stringify({
        email,
        organization_invitation_token: organizationInvitationToken || null,
      }),
    });
    if (response.status === 429) {
      showEmailVerificationPending(email, { retry_after_seconds: Number(response.headers.get('Retry-After') || 0) });
    }
    const data = await readApiResponse(response, 'Не удалось отправить ссылку для входа.');
    renderOrganizationInvitation(data.organization || null);
    const isDevMode = Boolean(data.dev_mode);
    const nextMode = isDevMode ? 'dev_token' : data.auth_mode || data.delivery_method || 'password';
    authCredentialEmail = data.email || email;
    if (authCredentialEmailInput) {
      authCredentialEmailInput.value = authCredentialEmail;
    }
    configureAuthCredentialForm(nextMode);
    if (nextMode === 'verification_pending') {
      showEmailVerificationPending(authCredentialEmail, data);
      if (data.dev_magic_token) {
        await handleAuthActionToken('email_verification', data.dev_magic_token);
      }
      return;
    }
    if (authTokenForm) {
      authTokenForm.classList.remove('hidden');
    }
    if (magicTokenInput) {
      magicTokenInput.value = data.dev_magic_token || '';
      magicTokenInput.focus();
    }
    void fillStoredPasswordIfAvailable();
    setAuthStatus(
      isDevMode
        ? 'Dev-режим: токен подставлен автоматически. Можно сразу нажать «Войти».'
        : data.message || 'Введите пароль для входа.',
    );
  } catch (error) {
    hideLoader();
    setAuthStatus('');
    const message = String(error?.message || '');
    if (message.includes('не найден в активных организациях') || message.includes('не добавлен в список участников')) {
      showAccessUnavailable(email);
    } else if (message === 'Failed to fetch' || error instanceof TypeError) {
      showError(authError, 'Не удалось связаться с сервером. Попробуйте ещё раз.');
    } else {
      showError(authError, message);
    }
  } finally {
    if (requestMagicLinkButton) {
      requestMagicLinkButton.disabled = false;
      requestMagicLinkButton.removeAttribute('aria-busy');
      requestMagicLinkButton.textContent = 'Продолжить';
    }
    if (emailInput) {
      emailInput.disabled = false;
    }
    authRequestInFlight = false;
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
    const data = await readApiResponse(response, 'Не удалось подтвердить вход.', { recoverUnauthorized: false });
    setAuthStatus('Email подтвержден. Загружаем ваш профиль...');
    await applyAuthResponse(data);
  } catch (error) {
    showError(authError, error.message);
  }
};

const submitEmailPassword = async () => {
  if (authCredentialInFlight) return;
  showError(authError, '');
  const email = String(authCredentialEmail || emailInput?.value || '').trim();
  let password = String(magicTokenInput?.value || '');
  let passwordConfirm = '';
  const isRegistration = authCredentialMode === 'password_registration';
  const isReset = authCredentialMode === 'password_reset';

  if (!email) {
    showError(authError, 'введите email');
    emailInput?.focus();
    return;
  }
  if (!password) {
    showError(authError, 'Введите пароль');
    magicTokenInput?.focus();
    return;
  }
  if ((isRegistration || isReset) && authCredentialStep === 1) {
    if (!isValidNewPassword(password)) {
      showError(authError, NEW_PASSWORD_ERROR);
      magicTokenInput?.setAttribute('aria-invalid', 'true');
      magicTokenInput?.focus();
      return;
    }
    newPasswordDraft = password;
    showPasswordConfirmationStep();
    return;
  }
  if (isRegistration || isReset) {
    passwordConfirm = password;
    password = newPasswordDraft;
    if (password !== passwordConfirm) {
      showError(authError, 'Пароли не совпадают. Попробуйте ещё раз.');
      magicTokenInput?.setAttribute('aria-invalid', 'true');
      magicTokenInput?.focus();
      return;
    }
  }

  const operationGeneration = ++authOperationGeneration;
  try {
    authCredentialInFlight = true;
    if (verifyMagicLinkButton) {
      verifyMagicLinkButton.disabled = true;
      verifyMagicLinkButton.setAttribute('aria-busy', 'true');
      verifyMagicLinkButton.textContent = isReset ? 'Сохраняем...' : isRegistration ? 'Регистрируем...' : 'Входим...';
    }
    [magicTokenInput, authPasswordToggleButton, authChangeCredentialEmailButton, authPasswordGenerateButton, forgotPasswordCredentialButton]
      .filter(Boolean)
      .forEach((control) => { control.disabled = true; });
    const response = await fetch(
      isReset ? '/users/auth/password/reset' : isRegistration ? '/users/auth/email/password-register' : '/users/auth/email/password-login',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify(
          isReset
            ? { token: authActionToken, password, password_confirm: passwordConfirm }
            : isRegistration
            ? {
                email,
                password,
                password_confirm: passwordConfirm,
                verification_token: authActionToken || null,
                organization_invitation_token: organizationInvitationToken || null,
              }
            : { email, password, organization_invitation_token: organizationInvitationToken || null },
        ),
      },
    );
    const data = await readApiResponse(response, isReset ? 'Не удалось изменить пароль.' : 'Не удалось выполнить вход.', {
      recoverUnauthorized: false,
    });
    if (operationGeneration !== authOperationGeneration) return;
    if (isReset) {
      authActionToken = '';
      authCredentialEmail = data.email || email;
      showPasswordResetComplete(authCredentialEmail);
      return;
    }
    await offerPasswordSave({ email, password });
    setAuthStatus(isRegistration ? 'Пароль задан. Загружаем профиль...' : 'Вход выполнен. Загружаем профиль...');
    await applyAuthResponse(data);
  } catch (error) {
    if (operationGeneration !== authOperationGeneration) return;
    const message = error instanceof TypeError || error?.message === 'Failed to fetch'
      ? 'Не удалось связаться с сервером. Проверьте соединение и повторите попытку.'
      : error.message;
    showError(authError, message);
  } finally {
    const isCurrentOperation = operationGeneration === authOperationGeneration;
    if (isCurrentOperation) {
      if (verifyMagicLinkButton) {
        verifyMagicLinkButton.disabled = false;
        verifyMagicLinkButton.removeAttribute('aria-busy');
        verifyMagicLinkButton.textContent = (isReset || isRegistration) && authCredentialStep === 2
          ? isReset ? 'Сохранить пароль' : 'Создать пароль'
          : (isReset || isRegistration) ? 'Продолжить' : 'Войти';
      }
      [magicTokenInput, authPasswordToggleButton, authChangeCredentialEmailButton, authPasswordGenerateButton, forgotPasswordCredentialButton]
        .filter(Boolean)
        .forEach((control) => { control.disabled = false; });
      authCredentialInFlight = false;
    }
  }
};

export const handleAuthActionToken = async (action, tokenValue) => {
  authPendingTokenAction = action;
  const token = String(tokenValue || '').trim();
  const isReset = action === 'password_reset';
  const endpoint = isReset ? '/users/auth/password/reset/validate' : '/users/auth/email/confirm';
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });
    const data = await readApiResponse(response, 'Ссылка недействительна или устарела.');
    renderOrganizationInvitation(data.organization || null);
    authActionToken = token;
    authCredentialEmail = data.email || '';
    if (emailInput) emailInput.value = authCredentialEmail;
    if (authTokenForm) authTokenForm.classList.remove('hidden');
    configureAuthCredentialForm(isReset ? 'password_reset' : 'password_registration');
    setAuthStatus('');
    magicTokenInput?.focus();
  } catch (error) {
    const networkFailure = error instanceof TypeError || error?.message === 'Failed to fetch';
    const failureMessage = String(error?.message || '').toLowerCase();
    const resetFailureTitle = failureMessage.includes('отозван')
      ? 'Ссылка отозвана'
      : failureMessage.includes('ист')
        ? 'Срок ссылки истёк'
        : failureMessage.includes('использован')
          ? 'Ссылка уже использована'
          : 'Ссылка недействительна';
    authPendingEmailAction = networkFailure ? 'action-token-retry' : isReset ? 'reset-invalid' : 'verification-invalid';
    authActionToken = token;
    setAuthStatus('');
    authEmailForm?.classList.add('hidden');
    authTokenForm?.classList.add('hidden');
    authEmailSent?.classList.remove('hidden');
    authResendEmailButton?.classList.add('hidden');
    const title = authEmailSent?.querySelector('h2');
    const paragraphs = authEmailSent?.querySelectorAll('.auth-email-sent-copy p');
    if (title) title.textContent = networkFailure ? 'Нет связи с сервером' : isReset ? resetFailureTitle : 'Не удалось проверить ссылку';
    if (paragraphs?.[0]) paragraphs[0].textContent = networkFailure
      ? 'Проверьте соединение и повторите проверку ссылки.'
      : isReset
        ? 'Срок действия ссылки истёк, она была отозвана или уже использована.'
        : 'Запросите новую ссылку и попробуйте ещё раз.';
    if (paragraphs?.[1]) paragraphs[1].textContent = '';
    if (authChangeEmailButton) authChangeEmailButton.textContent = networkFailure ? 'Повторить' : isReset ? 'Запросить новую ссылку' : 'Вернуться';
    showError(authError, '');
  }
};

const requestPasswordReset = async () => {
  if (authResetRequestInFlight || authCredentialInFlight) return;
  const operationGeneration = ++authOperationGeneration;
  showError(authError, '');
  const email = String(emailInput?.value || '').trim();
  if (!email) {
    showError(authError, 'введите email');
    emailInput?.focus();
    return;
  }
  try {
    authResetRequestInFlight = true;
    const resetTrigger = forgotPasswordCredentialButton && !forgotPasswordCredentialButton.classList.contains('hidden')
      ? forgotPasswordCredentialButton : forgotPasswordButton;
    resetTrigger?.setAttribute('aria-busy', 'true');
    [emailInput, magicTokenInput, verifyMagicLinkButton, requestMagicLinkButton,
      forgotPasswordButton, forgotPasswordCredentialButton, authChangeEmailButton,
      authChangeCredentialEmailButton, authPasswordToggleButton, authPasswordGenerateButton]
      .filter(Boolean).forEach((control) => { control.disabled = true; });
    const response = await fetch('/users/auth/password/forgot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await readApiResponse(response, 'Не удалось запросить восстановление пароля.');
    if (operationGeneration !== authOperationGeneration) return;
    if (data.dev_action_token) {
      await handleAuthActionToken('password_reset', data.dev_action_token);
    } else {
      authPendingEmailAction = 'reset';
      authEmailForm?.classList.add('hidden');
      authTokenForm?.classList.add('hidden');
      authEmailSent?.classList.remove('hidden');
      const title = authEmailSent?.querySelector('h2');
      const paragraphs = authEmailSent?.querySelectorAll('.auth-email-sent-copy p');
      if (title) title.textContent = 'Проверьте почту';
      if (paragraphs?.[0]) paragraphs[0].textContent = `Мы отправили ссылку для восстановления на ${email}.`;
      if (paragraphs?.[1]) paragraphs[1].textContent = 'Перейдите по ссылке из письма, чтобы создать новый пароль.';
      if (authChangeEmailButton) authChangeEmailButton.textContent = 'Вернуться';
      setAuthStatus('');
      startAuthResendCountdown(data);
    }
  } catch (error) {
    if (operationGeneration !== authOperationGeneration) return;
    showError(
      authError,
      error instanceof TypeError || error?.message === 'Failed to fetch'
        ? 'Не удалось связаться с сервером. Проверьте соединение и повторите запрос.'
        : error.message,
    );
  } finally {
    if (operationGeneration === authOperationGeneration) {
      authResetRequestInFlight = false;
      [forgotPasswordButton, forgotPasswordCredentialButton].filter(Boolean)
        .forEach((control) => control.removeAttribute('aria-busy'));
      [emailInput, magicTokenInput, verifyMagicLinkButton, requestMagicLinkButton,
        forgotPasswordButton, forgotPasswordCredentialButton, authChangeEmailButton,
        authChangeCredentialEmailButton, authPasswordToggleButton, authPasswordGenerateButton]
        .filter(Boolean).forEach((control) => { control.disabled = false; });
    }
  }
};

export const initWiring = () => {
window.addEventListener('storage', (event) => {
  if (event.key !== AUTH_RESEND_TIMING_KEY || authEmailSent?.classList.contains('hidden')) return;
  try {
    const deadline = Number(JSON.parse(event.newValue || '{}').deadline || 0);
    startAuthResendCountdown({ deadline });
  } catch (_error) {
    startAuthResendCountdown({ deadline: 0 });
  }
});

authEmailForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (authPendingEmailAction === 'reset-entry') {
    void requestPasswordReset();
    return;
  }
  void handleEmailMagicLinkRequest();
});

if (requestMagicLinkButton) {
  requestMagicLinkButton.addEventListener('click', (event) => {
    event.preventDefault();
    if (authPendingEmailAction === 'reset-entry') {
      void requestPasswordReset();
      return;
    }
    void handleEmailMagicLinkRequest();
  });
}

if (forgotPasswordButton) {
  forgotPasswordButton.addEventListener('click', () => void requestPasswordReset());
}
if (forgotPasswordCredentialButton) {
  forgotPasswordCredentialButton.addEventListener('click', () => void requestPasswordReset());
}

if (authChangeEmailButton) {
  authChangeEmailButton.addEventListener('click', () => {
    if (authPendingEmailAction === 'reset-complete') {
      authEmailSent?.classList.add('hidden');
      configureAuthCredentialForm('password');
      authTokenForm?.classList.remove('hidden');
      if (authTitle) authTitle.textContent = 'С возвращением';
      void fillStoredPasswordIfAvailable();
      magicTokenInput?.focus();
      return;
    }
    if (authPendingEmailAction === 'action-token-retry') {
      void handleAuthActionToken(authPendingTokenAction || 'email_verification', authActionToken);
      return;
    }
    if (authPendingEmailAction === 'reset-invalid') {
      showEmailEntry();
      if (emailInput && authCredentialEmail) emailInput.value = authCredentialEmail;
      authPendingEmailAction = 'reset-entry';
      if (authTitle) authTitle.textContent = 'Восстановление пароля';
      if (authSubtitle) authSubtitle.textContent = 'Введите рабочий email, чтобы получить новую ссылку.';
      if (requestMagicLinkButton) requestMagicLinkButton.textContent = 'Получить новую ссылку';
      forgotPasswordButton?.classList.remove('hidden');
      return;
    }
    showEmailEntry();
  });
}

if (authChangeCredentialEmailButton) {
  authChangeCredentialEmailButton.addEventListener('click', () => {
    if ((authCredentialMode === 'password_registration' || authCredentialMode === 'password_reset') && authCredentialStep === 2) {
      showError(authError, '');
      showPasswordCreationStep();
      return;
    }
    showEmailEntry();
  });
}

if (authCompleteLogoutButton) {
  authCompleteLogoutButton.addEventListener('click', () => void logoutAndReturnToStart(authCompleteLogoutButton));
}

if (authCompleteContinueButton) {
  authCompleteContinueButton.addEventListener('click', async () => {
    if (authCompleteContinueButton.dataset.action === 'return-to-management' && state.canAdmin) {
      withScreen(loadAdminOrganizations, (module) => module.openAdminOrganizations());
      return;
    }
    if (authCompleteContinueButton.dataset.action === 'check-acquaintance-readiness') {
      authCompleteContinueButton.disabled = true;
      try {
        const { loadUserJourneyState } = await import('./session.js');
        const journey = await loadUserJourneyState();
        if (journey?.next_action === 'wait_for_acquaintance_data') {
          const { openAcquaintanceWaiting } = await import('./router.js');
          openAcquaintanceWaiting(journey.acquaintance?.readiness);
          return;
        }
        window.location.reload();
      } finally {
        authCompleteContinueButton.disabled = false;
      }
      return;
    }
    withScreen(loadChat, (module) => module.openChat());
  });
}

if (authResendEmailButton) {
  authResendEmailButton.addEventListener('click', () => {
    if (authResendEmailButton.disabled) return;
    if (authPendingEmailAction === 'reset') {
      void requestPasswordReset();
      return;
    }
    showEmailEntry();
    void handleEmailMagicLinkRequest();
  });
}

authTokenForm.addEventListener('submit', (event) => {
  if (!authTokenForm.reportValidity()) {
    return;
  }
  event.preventDefault();
  if (authCredentialMode === 'password' || authCredentialMode === 'password_registration' || authCredentialMode === 'password_reset') {
    void submitEmailPassword();
    return;
  }
  void verifyEmailMagicLinkToken();
});

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

if (participantReturnManagementButton) {
  participantReturnManagementButton.addEventListener('click', () => {
    withScreen(loadAdminOrganizations, (module) => module.openAdminOrganizations());
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
    if (state.adminDashboard?.is_superadmin) {
      withScreen(() => import('./screens/profile-recovery.js'), (module) => module.recoverProfileCompletionForAssessment());
      return;
    }
    withScreen(loadAdminDashboard, (module) => module.openAdminAssessmentDashboard());
  });
}

document.querySelectorAll('[data-admin-area]').forEach((button) => {
  button.addEventListener('click', () => {
    if (button.dataset.adminArea === 'assessment') {
      withScreen(loadAdminDashboard, (module) => module.openAdminAssessmentDashboard());
      return;
    }
    withScreen(loadAdminOrganizations, (module) => module.openAdminOrganizations());
  });
});

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

if (adminRegressionTestsRunOfflineButton) {
  adminRegressionTestsRunOfflineButton.addEventListener('click', () => {
    withScreen(loadAdminRegressionTests, (module) => module.runAdminOfflineRegressionTests());
  });
}

if (adminRegressionTestsRunTechnicalButton) {
  adminRegressionTestsRunTechnicalButton.addEventListener('click', () => {
    withScreen(loadAdminRegressionTests, (module) => module.runAdminTechnicalRegressionTests());
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

if (adminOrganizationSelect) {
  adminOrganizationSelect.addEventListener('change', () => {
    withScreen(loadAdminOrganizations, (module) => module.selectAdminOrganization(adminOrganizationSelect.value));
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
    if (form.dataset.action === 'send-member-invitations') {
      const emails = [...card.querySelectorAll('input[name="invitation_email"]:checked')]
        .map((checkbox) => checkbox.value)
        .filter(Boolean);
      withScreen(loadAdminOrganizations, (module) =>
        module.sendAdminOrganizationMemberInvitation(
          organizationId, emails, module.getSelectedAdminOrganizationAssessment(organizationId),
        ),
      );
      return;
    }
    if (form.dataset.action === 'update-profile') {
      const formData = new FormData(form);
      const optionalNumber = (name) => {
        const value = String(formData.get(name) || '').trim();
        return value ? Number(value) : null;
      };
      withScreen(loadAdminOrganizations, (module) =>
        module.updateAdminOrganizationProfile(organizationId, {
          name: String(formData.get('name') || '').trim(),
          code: String(formData.get('code') || '').trim(),
          profile: String(formData.get('profile') || '').trim() || null,
          founded_year: optionalNumber('founded_year'),
          employee_count: optionalNumber('employee_count'),
          industry: String(formData.get('industry') || '').trim() || null,
          website: String(formData.get('website') || '').trim() || null,
          headquarters: String(formData.get('headquarters') || '').trim() || null,
          notes: String(formData.get('notes') || '').trim() || null,
        }),
      );
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
          job_instructions: null,
        });
        form.reset();
      });
      return;
    }
    if (form.dataset.action === 'preview-early-data') {
      const formData = new FormData(form);
      const value = (name) => String(formData.get(name) || '').trim();
      withScreen(loadAdminOrganizations, (module) =>
        module.previewAdminOrganizationQuestionnaire(organizationId, {
          assignment_ref: value('assignment_ref'),
          source_author: value('source_author'),
          channel: 'product_form',
          template_variant: 'corporate',
          template_version: '0.1',
          csv_text: null,
          answers: {
            C01: {
              name: value('organization_name'),
              organization_type: value('organization_type'),
              industry: value('industry'),
              activity_description: value('activity_description'),
            },
            C02a: { participant_text: value('purpose') },
            C03: { participant_text: value('results_usage') },
            C04: { answer: value('result_recipients') },
            C17: {
              case_reality_level: value('case_reality_level'),
              organization_name_usage_rules: value('organization_name_usage_rules'),
            },
            C21: {
              organizer: value('organizer'),
              responsible_contact: value('responsible_contact'),
            },
          },
          idempotency_key: createOperationId(),
        }),
      );
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
      return;
    }
    if (form.dataset.action === 'preview-questionnaire') {
      const formData = new FormData(form);
      const file = form.querySelector('input[type="file"]')?.files?.[0];
      if (!file) return;
      file.text().then((csvText) => {
        withScreen(loadAdminOrganizations, async (module) => {
          await module.previewAdminOrganizationQuestionnaire(organizationId, {
            assignment_ref: String(formData.get('assignment_ref') || '').trim(),
            source_author: String(formData.get('source_author') || '').trim(),
            channel: 'csv', template_variant: 'corporate', template_version: '0.1',
            csv_text: csvText, answers: {}, idempotency_key: createOperationId(),
          });
        });
      });
    }
  });

  adminOrganizationsList.addEventListener('focusin', (event) => {
    const field = event.target instanceof HTMLInputElement && event.target.name === 'assignment_ref'
      ? event.target : null;
    if (field) field.dataset.previousAssessmentRef = field.value;
  });

  const markQuestionnairePreviewStale = (event) => {
    const field = event.target instanceof Element ? event.target : null;
    const card = field?.closest('[data-organization-id]');
    const organizationId = Number(card?.getAttribute('data-organization-id'));
    if (!field || !organizationId || field.getAttribute('name') === 'assignment_ref') return;
    if (!field.closest('[data-action="preview-early-data"], [data-action="preview-questionnaire"], .admin-questionnaire-preview')) return;
    const assessmentRef = field.closest('.admin-questionnaire-preview')?.getAttribute('data-assessment-ref') ||
      card?.querySelector('[data-admin-view]:not(.hidden) [name="assignment_ref"]')?.value || '';
    withScreen(loadAdminOrganizations, (module) =>
      module.markAdminOrganizationQuestionnairePreviewStale(organizationId, assessmentRef));
  };
  adminOrganizationsList.addEventListener('input', markQuestionnairePreviewStale);
  adminOrganizationsList.addEventListener('change', markQuestionnairePreviewStale);

  adminOrganizationsList.addEventListener('focusout', (event) => {
    const field = event.target instanceof HTMLInputElement && event.target.name === 'assignment_ref'
      ? event.target : null;
    const form = field?.closest('form[data-action]');
    const card = field?.closest('[data-organization-id]');
    const organizationId = Number(card?.getAttribute('data-organization-id'));
    if (!field || !form || !organizationId) return;
    withScreen(loadAdminOrganizations, (module) => module.selectAdminOrganizationAssessment(
      organizationId, form, field.value, field.dataset.previousAssessmentRef || '',
    ));
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
    if (button.dataset.action === 'confirm-questionnaire') {
      const recipients = [...(card?.querySelectorAll('input[name="questionnaire_recipient"]:checked') || [])]
        .map((input) => input.value);
      const recipientUserIds = [...(card?.querySelectorAll('input[name="questionnaire_recipient_user"]:checked') || [])]
        .map((input) => Number(input.value)).filter((value) => Number.isFinite(value) && value > 0);
      if (recipientUserIds.length && !recipients.includes('organization_admin')) recipients.push('organization_admin');
      withScreen(loadAdminOrganizations, (module) =>
        module.confirmAdminOrganizationQuestionnaire(organizationId, Number(value), recipients, recipientUserIds));
      return;
    }
    if (button.dataset.action === 'prepare-organization-assessments') {
      button.disabled = true;
      button.textContent = 'Запускаем…';
      withScreen(loadAdminOrganizations, (module) => module.prepareAdminOrganizationAssessments(organizationId));
      return;
    }
    if (button.dataset.action === 'show-admin-view') {
      withScreen(loadAdminOrganizations, (module) =>
        module.selectAdminOrganizationView(organizationId, button.dataset.view));
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
      const normalizedValue = value.trim().toLowerCase();
      if (normalizedValue.startsWith('__autotest__') || normalizedValue.endsWith('@autotest.local')) {
        window.alert('Autotest-пользователей нельзя отвязывать из списка организаций. Используйте очистку регрессионных тестов.');
        return;
      }
      if (!window.confirm('Отвязать пользователя ' + value + ' от организации?')) {
        return;
      }
      withScreen(loadAdminOrganizations, (module) => module.deleteAdminOrganizationMember(organizationId, value));
      return;
    }
    if (button.dataset.action === 'reset-member-password') {
      if (!window.confirm('Сбросить пароль пользователя ' + value + '? При следующем входе он задаст новый пароль.')) {
        return;
      }
      withScreen(loadAdminOrganizations, (module) => module.resetAdminOrganizationMemberPassword(organizationId, value));
      return;
    }
    if (button.dataset.action === 'send-member-invitation') {
      withScreen(loadAdminOrganizations, (module) => module.sendAdminOrganizationMemberInvitation(
        organizationId, value, module.getSelectedAdminOrganizationAssessment(organizationId),
      ));
      return;
    }
    if (button.dataset.action === 'revoke-member-invitation') {
      const invitationId = Number(button.getAttribute('data-invitation-id'));
      if (!invitationId) return;
      withScreen(loadAdminOrganizations, (module) => module.revokeAdminOrganizationMemberInvitation(organizationId, invitationId));
      return;
    }
    if (button.dataset.action === 'prepare-member-assessment') {
      const userId = Number(button.getAttribute('data-user-id'));
      if (!userId) {
        return;
      }
      withScreen(loadAdminOrganizations, (module) =>
        module.prepareAdminOrganizationMemberAssessment(organizationId, userId),
      );
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

if (dashboardOnboardingButton) {
  dashboardOnboardingButton.addEventListener('click', () => {
    void openOnboardingScreen({ currentStep: 0, reviewMode: true });
  });
}

if (adminProfileButton) {
  adminProfileButton.addEventListener('click', () => {
    withScreen(loadProfile, (module) => module.openProfile());
  });
}

welcomeProfileButton.addEventListener('click', () => {
  withScreen(loadProfile, (module) => module.openProfile());
});


assessmentActionButton?.addEventListener('click', () => {
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

let failedInterviewMessage = null;
let interviewSendInFlight = false;

const setInterviewSubmitLabel = (label) => {
  if (interviewSubmitLabel) {
    interviewSubmitLabel.textContent = label;
  }
};

const logAssessmentClientEvent = (event, messageType = 'answer', errorType = null) => {
  if (!state.assessmentSessionCode) {
    return;
  }
  void fetch('/users/assessment/client-event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_code: state.assessmentSessionCode,
      event,
      message_type: messageType,
      case_number: Number(state.assessmentCaseNumber || 0) || null,
      error_type: errorType,
    }),
    keepalive: true,
  }).catch(() => {});
};

const resumeInterviewTimerAfterSendError = (interviewModule) => {
  // Keep the failed row and its request identity until retry/reload; Cycle time is server-owned.
  if (interviewModule.isCycleAssessment()) return;
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
};

const sendInterviewAnswer = async (text, existingMessageRow = null) => {
  showError(interviewError, '');
  const interviewModule = await loadInterview();
  const messageRow = existingMessageRow || interviewModule.addInterviewMessage('user', text);
  interviewModule.setInterviewMessageDeliveryState(messageRow, 'pending');
  if (interviewTextarea.value.trim() === text) {
    interviewTextarea.value = '';
  }
  interviewTextarea.disabled = true;
  interviewSubmitButton.disabled = true;
  interviewFinishButton.disabled = true;
  interviewModule.clearInterviewTimer();
  try {
    logAssessmentClientEvent('request_started');
    if (interviewModule.isCycleAssessment()) {
      messageRow.dataset.requestId ||= createOperationId();
      messageRow.dataset.turnId ||= crypto.randomUUID();
    }
    messageRow.productRequestIdentity ||= {
      requestId: messageRow.dataset.requestId,
      turnId: messageRow.dataset.turnId,
    };
    await interviewModule.submitAssessmentMessage(text, messageRow.productRequestIdentity);
    interviewModule.clearInterviewDraft();
    interviewModule.setInterviewMessageDeliveryState(messageRow, 'sent');
    if (interviewModule.isCycleAssessment()) interviewModule.resumeProductRuntimePolling();
    logAssessmentClientEvent('request_succeeded');
    if (failedInterviewMessage?.row === messageRow) {
      failedInterviewMessage = null;
    }
    return true;
  } catch (error) {
    const rawErrorMessage = String(error?.message || '');
    const errorMessage = /failed to fetch|networkerror|load failed/i.test(rawErrorMessage)
      ? 'Ответ не отправлен. Проверьте соединение и повторите попытку.'
      : rawErrorMessage || 'Не удалось отправить ответ. Проверьте соединение и попробуйте еще раз.';
    showError(interviewError, errorMessage);
    logAssessmentClientEvent('request_failed', 'answer', error?.name || 'unknown');
    failedInterviewMessage = { row: messageRow, text };
    interviewModule.setInterviewMessageDeliveryState(messageRow, 'failed', () => {
      void sendInterviewAnswer(text, messageRow);
    });
    if (!interviewTextarea.value.trim()) {
      interviewTextarea.value = text;
    }
    interviewTextarea.disabled = false;
    interviewSubmitButton.disabled = false;
    interviewFinishButton.disabled = false;
    interviewTextarea.focus();
    resumeInterviewTimerAfterSendError(interviewModule);
    return false;
  }
};

const submitCurrentInterviewAnswer = async () => {
  if (interviewSendInFlight) {
    return;
  }
  showError(interviewError, '');

  const text = interviewTextarea.value.trim();
  if (!text) {
    showError(interviewError, 'Введите ответ по текущей ситуации.');
    return;
  }
  if (!state.assessmentSessionCode && !state.productCycleId) {
    showError(interviewError, 'Сессия оценки не инициализирована.');
    return;
  }

  if (failedInterviewMessage && !failedInterviewMessage.row?.isConnected) {
    failedInterviewMessage = null;
  }
  if (failedInterviewMessage && failedInterviewMessage.text !== text) {
    failedInterviewMessage.row?.remove();
    failedInterviewMessage = null;
  }
  const reusableFailedRow = failedInterviewMessage?.text === text ? failedInterviewMessage.row : null;
  interviewSendInFlight = true;
  setInterviewSubmitLabel('Отправляем...');
  logAssessmentClientEvent('submit_clicked');
  try {
    const sent = await sendInterviewAnswer(text, reusableFailedRow);
    setInterviewSubmitLabel(sent ? 'Ответ сохранён' : 'Повторить отправку');
    if (sent) {
      window.setTimeout(() => setInterviewSubmitLabel('Отправить'), 1200);
    }
  } catch (error) {
    showError(interviewError, error?.message || 'Не удалось подготовить отправку ответа. Повторите попытку.');
    logAssessmentClientEvent('request_failed', 'answer', error?.name || 'prepare_failed');
    setInterviewSubmitLabel('Повторить отправку');
    interviewTextarea.disabled = false;
    interviewSubmitButton.disabled = false;
    interviewFinishButton.disabled = false;
    interviewTextarea.focus();
  } finally {
    interviewSendInFlight = false;
  }
};

interviewForm.addEventListener('submit', (event) => {
  event.preventDefault();
  void submitCurrentInterviewAnswer();
});

if (!ASSESSMENT_EXTERNAL_ANSWER_TRANSFER_ENABLED) {
  interviewPanel.classList.add('external-transfer-disabled');
  interviewMessages.classList.add('external-transfer-disabled');

  const blockProtectedCopy = (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.clipboardData) {
      event.clipboardData.clearData();
      event.clipboardData.setData('text/plain', '');
    }
    showError(
      interviewError,
      'Копирование условия, материалов и реплик собеседника ограничено для этой оценки.',
    );
  };

  const isInterviewScreenActive = () => {
    return state.currentScreen === 'interview' && !interviewPanel.classList.contains('hidden');
  };

  const protectedSelection = () => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return false;
    return [...interviewPanel.querySelectorAll(
      '.interview-message:not(.own), .interview-summary, .interview-case-guide, .interview-case-header, .case-sidebar',
    )].some((node) => selection.containsNode(node, true));
  };

  document.addEventListener('copy', (event) => {
    if (isInterviewScreenActive() && protectedSelection()) {
      blockProtectedCopy(event);
    }
  }, true);
  document.addEventListener('cut', (event) => {
    if (isInterviewScreenActive() && protectedSelection()) {
      blockProtectedCopy(event);
    }
  }, true);
  document.addEventListener('keydown', (event) => {
    if (
      isInterviewScreenActive() &&
      (event.ctrlKey || event.metaKey) &&
      ['c', 'x'].includes(String(event.key || '').toLowerCase())
    ) {
      if (protectedSelection()) blockProtectedCopy(event);
    }
  }, true);
  interviewPanel.addEventListener('contextmenu', (event) => {
    if (event.target.closest('.interview-message:not(.own), .interview-summary, .interview-case-guide, .interview-case-header, .case-sidebar')) {
      blockProtectedCopy(event);
    }
  });
  interviewPanel.addEventListener('dragstart', (event) => {
    if (event.target.closest('.interview-message:not(.own), .interview-summary, .interview-case-guide, .interview-case-header, .case-sidebar')) {
      blockProtectedCopy(event);
    }
  });
}

interviewSubmitButton.addEventListener('click', (event) => {
  event.preventDefault();
  void submitCurrentInterviewAnswer();
});

interviewFinishButton.addEventListener('click', async () => {
  showError(interviewError, '');

  if (interviewTextarea.value.trim()) {
    showError(interviewError, 'В поле есть неотправленный ответ. Сначала нажмите «Отправить».');
    interviewTextarea.focus();
    return;
  }

  if (!state.assessmentSessionCode && !state.productCycleId) {
    showError(interviewError, 'Сессия оценки не инициализирована.');
    return;
  }

  if (!window.confirm('Завершить прохождение? Ответы будут зафиксированы. При необходимости сначала появится уточняющий вопрос.')) {
    return;
  }

  interviewTextarea.disabled = true;
  interviewSubmitButton.disabled = true;
  interviewFinishButton.disabled = true;

  try {
    const interviewModule = await loadInterview();
    interviewModule.clearInterviewTimer();
    logAssessmentClientEvent('finish_clicked', 'finish');
    if (interviewModule.isCycleAssessment()) {
      await interviewModule.finishProductAssessment();
    } else {
      await interviewModule.submitAssessmentMessage('__finish_case__');
    }
  } catch (error) {
    showError(interviewError, error.message);
    interviewTextarea.disabled = false;
    interviewSubmitButton.disabled = false;
    interviewFinishButton.disabled = false;
  }
});

if (interviewPauseButton) {
  interviewPauseButton.addEventListener('click', async () => {
    showError(interviewError, '');
    try {
      const interviewModule = await loadInterview();
      await interviewModule.toggleProductPause();
    } catch (error) {
      showError(interviewError, error.message);
    }
  });
}

if (interviewAdditionalButton) {
  interviewAdditionalButton.addEventListener('click', async () => {
    showError(interviewError, '');
    if (!window.confirm('Завершить текущую сессию и открыть допустимую дополнительную сессию?')) return;
    interviewAdditionalButton.disabled = true;
    try {
      const interviewModule = await loadInterview();
      await interviewModule.createProductAdditionalSession();
    } catch (error) {
      showError(interviewError, error.message);
    } finally {
      interviewAdditionalButton.disabled = false;
    }
  });
}

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

if (processingBackButton) {
  processingBackButton.addEventListener('click', () => {
    withScreen(loadChat, (module) => module.clearProcessingTimer());
    withScreen(loadAiWelcome, (module) => module.openWelcomeScreen());
  });
}

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

reportDownloadButton.addEventListener('click', async () => {
  if (reportDownloadButton.dataset.m8ReportId) {
    const status = document.getElementById('report-download-status');
    if (status) status.textContent = '';
    reportDownloadButton.disabled = true;
    try {
      const reportId = reportDownloadButton.dataset.m8ReportId;
      const response = reportDownloadButton.dataset.m8ReportAccess === 'customer'
        ? await fetch('/users/admin/m8-access/reports/' + encodeURIComponent(reportId) + '/pdf')
        : await fetch('/users/assessment/m8/reports/' + encodeURIComponent(reportId) + '/pdf');
      if (!response.ok) throw new Error('PDF_UNAVAILABLE');
      const href = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = href;
      link.download = `4k-report-${reportId}.pdf`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(href), 0);
    } catch (_error) {
      if (status) status.textContent = 'Не удалось скачать PDF. Попробуйте ещё раз.';
    } finally {
      reportDownloadButton.disabled = false;
    }
    return;
  }
  if (!state.pendingUser?.id || !state.assessmentSessionId) {
    return;
  }
  window.location.href = '/users/' + state.pendingUser.id + '/assessment/' + state.assessmentSessionId + '/report.pdf';
});

};
