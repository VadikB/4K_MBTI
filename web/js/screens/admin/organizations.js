import { mountInvitationDetails } from './invitation-details.js';
import { invitationMessage, invitationFacts, invitationSummary, invitationCommonMessage, exactInvitationItems, invitationLinkMessage, safeInvitationItem, invitationMissingText } from './invitation-presentation.js';
import { preparationHtml, renderPreparation, preparationPresentation } from '../../preparation-status.js';
import { createOperationId, readApiResponse, fetchWithDeadline as fetch, previewAccountPurge,
  getPendingAccountPurges, confirmAccountPurge, executeAccountPurge, accountPurgeErrorMessage } from '../../api.js';
import {
  adminOrganizationCodeInput,
  adminOrganizationCreateButton,
  adminOrganizationNameInput,
  adminOrganizationSelect,
  adminOrganizationsList,
  adminOrganizationsPanel,
  adminOrganizationsStatus,
  adminOrganizationsSubtitle,
  adminOrganizationsTitle,
} from '../../dom.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
import { persistAssessmentContext, setCurrentScreen, state, safeStorage } from '../../state.js';
import { participantReportAudience } from '../../readiness-presentation.js';
import { createAdminOrganizationDraftKey } from './organization-draft-key.js';
import { questionnaireAssignmentState } from './questionnaire-assignment-state.js';
import adminContextChoices from '../../../../assessment_definitions/contexts/competencies_4k/1.1/admin_context_choices.json' with { type: 'json' };

let selectedOrganizationId = null;
let appealsOnly = false;
const invitationRequestsInFlight = new Set();
const invitationResults = new Map();
const invitationReadbacks = new Map();
const assignmentSourceRequests = new Map();
const assignmentOperationIds = new Map();
const cancellationOperationIds = new Map();
const cancellationRequestsInFlight = new Set();
const programConnectionOperationIds = new Map();
const unverifiedProgramConnections = new Set();
const programConnectionRequestsInFlight = new Set();
const questionnairePreviews = new Map();
const questionnaireRevisions = new Map();
const staleQuestionnairePreviews = new Set();
const questionnairePreviewRequestGenerations = new Map();
const earlyDataPreviewAttempts = new Map();
const organizationViews = new Map();
const managementDrafts = new Map();
let renderedFormSignatures = new WeakMap();
const selectedAssessmentRefs = new Map();
const questionnaireConfirmRequestGenerations = new Map();
const questionnaireConfirmRequestsInFlight = new Set();
const questionnaireLoadStates = new Map();
const questionnaireLoadGenerations = new Map();
const questionnaireConfirmOutcomes = new Map();
let programConnectionOutcome = null;
let programConnectionFeedbackGeneration = 0;
let operationAnchor = null;
let restoredManagementIdentity = null;
let organizationsRequestGeneration = 0;
let assignmentViewGeneration = 0;
let organizationsReadStale = false;
let organizationsReadStaleReason = '';

const currentIdentityKey = () => String(state.pendingUser?.id || '');
const organizationKey = (organizationId) => currentIdentityKey() + ':' + Number(organizationId);
const assessmentKey = (organizationId, assessmentRef = '') =>
  organizationKey(organizationId) + ':' + String(assessmentRef || '').trim();
const confirmationStorageKey = (scope) => 'agent4k.questionnaire.confirmation.' + scope;
const readQuestionnaireOperation = (key) => {
  try {
    return window.sessionStorage.getItem(key);
  } catch { return null; }
};
const writeQuestionnaireOperation = (key, value) => {
  if (!key) return;
  try {
    if (value === null) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, String(value));
  } catch { /* Recovery within the current page remains available. */ }
};
const previewOperationStorageKey = async (scope, payload) => {
  try {
    const digest = await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(payload)));
    const fingerprint = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
    return 'agent4k.questionnaire.preview.' + scope + ':' + fingerprint;
  } catch { return null; }
};
const invitationStorageKey = (identityKey = currentIdentityKey()) => 'agent4k.pendingInvitations.' + identityKey;
const pendingInvitationOperations = (identityKey = currentIdentityKey()) => {
  if (!identityKey) return [];
  try {
    const saved = JSON.parse(safeStorage.getItem(invitationStorageKey(identityKey)) || '[]');
    return Array.isArray(saved) ? saved.filter((operation) =>
      operation && typeof operation.requestKey === 'string' && typeof operation.operationId === 'string' &&
      Number.isInteger(operation.organizationId) && typeof operation.assignmentRef === 'string' &&
      Array.isArray(operation.emails) && operation.emails.every((email) => typeof email === 'string')) : [];
  } catch { return []; }
};
const savePendingInvitationOperation = (operation, identityKey = currentIdentityKey()) => {
  const others = pendingInvitationOperations(identityKey).filter((item) => item.requestKey !== operation.requestKey);
  const key = invitationStorageKey(identityKey);
  const serialized = JSON.stringify([...others, operation]);
  safeStorage.setItem(key, serialized);
  try {
    return window.localStorage.getItem(key) === serialized;
  } catch { return false; }
};
const clearPendingInvitationOperation = (requestKey, identityKey = currentIdentityKey()) => {
  const remaining = pendingInvitationOperations(identityKey).filter((item) => item.requestKey !== requestKey);
  if (remaining.length) safeStorage.setItem(invitationStorageKey(identityKey), JSON.stringify(remaining));
  else safeStorage.removeItem(invitationStorageKey(identityKey));
};
const organizationById = (organizationId) => (state.adminOrganizations?.items || [])
  .find((item) => Number(item.id) === Number(organizationId));
const reflectConfirmedOrganizationName = (organizationId, revision, { allowAnswerFallback = false } = {}) => {
  const name = String(revision?.organization_name_current ||
    (allowAnswerFallback ? revision?.answers_json?.C01?.name : '') || '').trim();
  const organization = organizationById(organizationId);
  if (organization && name) {
    organization.name = name;
    persistAssessmentContext();
  }
};
const participantLabel = (organizationId, { user_id: userId, email } = {}) => {
  const member = (organizationById(organizationId)?.members || []).find((item) =>
    userId ? Number(item.user_id) === Number(userId) : String(item.email || '').toLowerCase() === String(email || '').toLowerCase());
  return member?.full_name || member?.email || email || (userId ? 'Участник ' + Number(userId) : 'Участник');
};
const invitationOutcomeText = (_organizationId, items) => invitationSummary(items) + '.';
const invitationResultKey = (organizationId, assessment, email) => assessmentKey(organizationId, assessment) + ':' + email.toLowerCase();
const savedInvitation = (member) => {
  const receipt = {
    email: member.email, invitation_id: member.invitation_id, operation_id: member.invitation_operation_id,
    delivery_status: member.invitation_delivery_status, link_status: member.invitation_link_status,
    created_at: member.invitation_created_at, expires_at: member.invitation_expires_at, ...member.invitation_reason,
  };
  if (['unknown', 'pending'].includes(invitationFacts(receipt).outcome)) {
    Object.assign(receipt, invitationReadbacks.get(member.invitation_id));
  }
  return safeInvitationItem(receipt);
};
const invitationFor = (organizationId, assessment, member) => {
  const local = invitationResults.get(invitationResultKey(organizationId, assessment, member.email));
  if (local) return safeInvitationItem(local);
  if (state.adminOrganizations?.is_superadmin || (assessment && member.invitation_assignment_ref === assessment)) {
    return savedInvitation(member);
  }
  return { email: member.email, delivery_status: 'not_sent' };
};
const renderInvitationFeedback = (organizationId, assessment, members) => {
  const items = members.map(member => invitationFor(organizationId, assessment, member));
  const message = invitationCommonMessage(items);
  const operator = items.some(item => item.next_action === 'operator') ? ' Настройку почтового сервиса выполняет оператор.' : '';
  return message ? '<div class="admin-invitation-common" role="status">' + escapeHtml(message + operator) + '</div>' : '';
};
export const reviewInvitationOrganization = (organizationId) => {
  organizationViews.set(Number(organizationId), 'organization-data');
  renderAdminOrganizations();
};
export const checkAdminInvitation = async (organizationId, email, assessment, operationId, invitationId) => {
  const epoch = state.identityEpoch;
  const actor = currentIdentityKey();
  const generation = assignmentViewGeneration;
  const screen = state.currentScreen;
  const valid = () => epoch === state.identityEpoch && actor === currentIdentityKey() &&
    generation === assignmentViewGeneration && screen === state.currentScreen && Number(selectedOrganizationId) === Number(organizationId);
  const query = new URLSearchParams({ assignment_ref: assessment, email });
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/personal-invitations/operations/' +
      encodeURIComponent(operationId) + '?' + query, { credentials: 'same-origin' });
    const result = await readApiResponse(response, 'Не удалось обновить сведения');
    if (!valid()) return;
    // One operation can contain several recipients. Attribute only the exact
    // saved row and leave the current registration and link on the member model.
    const items = Array.isArray(result?.items)
      ? result.items.filter(Boolean).map(safeInvitationItem).filter((item) => item.email === email) : [];
    const [updated] = items;
    if (items.length !== 1 || updated.operation_id !== operationId || updated.invitation_id !== invitationId) {
      setStatus('Не удалось подтвердить исход этой отправки.', 'error');
      return;
    }
    const { delivery_status, reason_code, reason_params, next_action } = updated;
    invitationReadbacks.set(invitationId, { delivery_status, reason_code, reason_params, next_action });
    renderAdminOrganizations();
    setStatus(invitationMessage(updated, { compact: true }), 'muted');
  } catch (error) {
    if (valid()) setStatus(error?.status === 404 ? 'Результат этой попытки пока не найден' :
      'Не удалось обновить сведения. Последний подтверждённый исход сохранён', 'error');
  }
};
export const mountAdminInvitationDetails = (dialog, organizationId, email, assessment, initial) => {
  const epoch = state.identityEpoch;
  const actor = currentIdentityKey();
  const generation = assignmentViewGeneration;
  const screen = state.currentScreen;
  const valid = () => dialog.isConnected && epoch === state.identityEpoch && actor === currentIdentityKey() &&
    generation === assignmentViewGeneration && screen === state.currentScreen && Number(selectedOrganizationId) === Number(organizationId);
  const refresh = initial.operation_id ? async (item) => {
    const query = new URLSearchParams({ assignment_ref: assessment, email });
    const response = await fetch('/users/admin/organizations/' + organizationId + '/personal-invitations/operations/' +
      encodeURIComponent(item.operation_id) + '?' + query, { credentials: 'same-origin' });
    const result = await readApiResponse(response, 'Не удалось обновить сведения');
    if (!valid()) return null;
    const updated = { ...item, ...exactInvitationItems(result, [email], [item], item.operation_id)[0] };
    invitationResults.set(invitationResultKey(organizationId, assessment, email), updated);
    renderAdminOrganizations();
    return updated;
  } : null;
  mountInvitationDetails(dialog, initial, refresh);
};
const localDateTime = (value) => {
  if (!value) return '';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('ru-RU', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
  });
};
const managementSections = ['people', 'organization-data', 'questionnaire'];
const exactBatch = (items, expected, identity, statuses) => {
  const expectedSet = new Set(expected.map(identity));
  const returned = items.map(identity);
  return items.length === expectedSet.size && new Set(returned).size === expectedSet.size &&
    returned.every((value) => expectedSet.has(value)) && items.every((item) => statuses.includes(item.status));
};
const programIdentity = (program) => program?.program_name || 'Программа оценки';
const roleIdentity = (roles = []) => roles.map((role) => role.name || role.code).filter(Boolean).join(', ') || 'не выбрана';
const organizationProgramState = (organizationId) => {
  const organization = organizationById(organizationId);
  const program = organization?.assessment_program;
  const assessmentRef = String(program?.assignment_ref || '').trim();
  if (organizationsReadStale || unverifiedProgramConnections.has(organizationKey(organizationId)) ||
      !organization || program === undefined || (program && !assessmentRef)) {
    return { status: 'unknown', assessmentRef: '', message:
      'Подключение программы пока не подтверждено. Проверьте состояние подключения.' };
  }
  if (!program) return { status: 'absent', assessmentRef: '', message: state.adminOrganizations?.is_superadmin
    ? 'Программа оценки не подключена. Подключите опубликованную программу.'
    : 'Программа оценки не подключена. Обратитесь к суперадминистратору.' };
  return { status: 'confirmed', assessmentRef, program, message: '' };
};
const requireOrganizationProgramScope = (organizationId, assessmentRef) => {
  const connection = organizationProgramState(organizationId);
  if (connection.status !== 'confirmed') {
    setStatus(connection.message, 'error');
    return false;
  }
  if (String(assessmentRef || '').trim() !== connection.assessmentRef) {
    setStatus('Подключённая программа изменилась. Обновите сведения и предпросмотр перед отправкой.', 'error');
    return false;
  }
  return true;
};
const saveManagementSelection = () => safeStorage.setItem('agent4k.adminManagement.' + currentIdentityKey(), JSON.stringify({
  organizationId: selectedOrganizationId,
  views: [...organizationViews],
  assessments: [...selectedAssessmentRefs],
}));
const restoreManagementSelection = () => {
  if (restoredManagementIdentity === currentIdentityKey()) return;
  restoredManagementIdentity = currentIdentityKey();
  try {
    const saved = JSON.parse(safeStorage.getItem('agent4k.adminManagement.' + currentIdentityKey()) || '{}');
    selectedOrganizationId = Number(saved.organizationId) || null;
    for (const [id, view] of saved.views || []) {
      if (managementSections.includes(view)) organizationViews.set(Number(id), view);
    }
    for (const [key, ref] of saved.assessments || []) {
      if (String(key).startsWith(currentIdentityKey() + ':') && typeof ref === 'string') selectedAssessmentRefs.set(key, ref);
    }
  } catch { /* Invalid local navigation is ignored; the server still controls access. */ }
};
const managementNavigation = () => ({
  ownerId: currentIdentityKey(),
  organizationId: selectedOrganizationId,
  assessmentRef: getSelectedAdminOrganizationAssessment(selectedOrganizationId),
  view: organizationViews.get(Number(selectedOrganizationId)) || 'people',
});
const restoreManagementNavigation = (navigation) => {
  if (navigation?.ownerId !== currentIdentityKey() || !Number.isInteger(navigation.organizationId)) return;
  selectedOrganizationId = navigation.organizationId;
  organizationViews.set(selectedOrganizationId, managementSections.includes(navigation.view) ? navigation.view : 'people');
  if (typeof navigation.assessmentRef === 'string') {
    selectedAssessmentRefs.set(organizationKey(selectedOrganizationId), navigation.assessmentRef);
  }
};
const formDraftKey = (organizationId, form, assessmentRef = '') => {
  const action = String(form?.dataset?.draftAction || form?.dataset?.action || 'unknown');
  return createAdminOrganizationDraftKey({
    identityKey: currentIdentityKey(),
    organizationId,
    action,
    assessmentRef,
    revisionId: action === 'unknown' ? form?.dataset?.questionnaireRevisionId || '' : '',
  });
};

const editableFields = (root) => [...root.querySelectorAll('input, textarea, select')]
  .filter((field) => field.type !== 'file' && field.type !== 'hidden' && field.name);
const formSignature = (form) => JSON.stringify([
  ...editableFields(form).map((field) => [
    field.name, field.value, ['checkbox', 'radio'].includes(field.type) ? field.checked : null,
  ]),
  ...[...form.querySelectorAll('input[type="file"][name]')].map((field) => [
    field.name,
    [...(field.files || [])].map((file) => [file.name, file.size, file.type, file.lastModified]),
  ]),
]);
const questionnaireInputSignature = (organizationId, action) => {
  const card = adminOrganizationsList.querySelector(
    '[data-organization-id="' + Number(organizationId) + '"]',
  );
  const form = card?.querySelector('form[data-action="' + action + '"]');
  return form ? formSignature(form) : '';
};
const isQuestionnaireRevisionNewer = (candidate, reference) => {
  const candidateId = Number(candidate?.id || 0);
  const referenceId = Number(reference?.id || 0);
  if (candidateId && referenceId && candidateId !== referenceId) return candidateId > referenceId;
  const candidateTime = Date.parse(candidate?.confirmed_at || candidate?.created_at || '') || 0;
  const referenceTime = Date.parse(reference?.confirmed_at || reference?.created_at || '') || 0;
  return candidateTime > referenceTime;
};
const mergeQuestionnaireRevision = (received, cached) => {
  if (!cached) return received;
  const latest = isQuestionnaireRevisionNewer(cached, received) ? cached : received;
  const confirmed = Number(cached.effective_confirmed?.id || 0) > Number(received.effective_confirmed?.id || 0)
    ? cached.effective_confirmed : received.effective_confirmed;
  return { ...latest, effective_confirmed: confirmed, readiness: received.readiness || latest.readiness };
};
const questionnaireErrorMessage = (error, fallback) => {
  const message = String(error?.message || '');
  if (message.includes('QUESTIONNAIRE_REVISION_CONFLICT')) return 'Эта редакция устарела: уже подтверждена более новая. Обновите предпросмотр.';
  if (message.includes('QUESTIONNAIRE_ORGANIZATION_NAME_CONFLICT')) return 'Название организации изменилось после сохранения черновика. Сверьте текущее название и обновите предпросмотр; введённый текст сохранён.';
  if (message.includes('QUESTIONNAIRE_CONTEXT_VERSION_CONFLICT')) return 'Сведения организации изменились после сохранения черновика. Обновите предпросмотр перед подтверждением; введённый текст сохранён.';
  if (message.includes('QUESTIONNAIRE_NOT_READY_FOR_CONFIRMATION')) return 'Анкета ещё не готова к подтверждению. Исправьте обязательные поля.';
  if (message.includes('QUESTIONNAIRE_TEMPLATE_MISMATCH')) return 'Файл создан по другой версии шаблона. Скачайте актуальный шаблон и повторите загрузку.';
  if (message.includes('QUESTIONNAIRE_FILE_TOO_LARGE')) return 'Файл анкеты слишком большой.';
  if (message.includes('IDEMPOTENCY_CONFLICT')) return 'Данные операции изменились. Повторите предпросмотр.';
  return message || fallback;
};

const membershipErrorMessage = (error, fallback) => {
  const message = String(error?.message || '');
  if (message.includes('ORGANIZATION_MEMBERSHIP_CONFLICT:')) {
    return message.split('ORGANIZATION_MEMBERSHIP_CONFLICT:', 2)[1].trim();
  }
  if (message === 'ORGANIZATION_ACCESS_PAUSED') return 'Организация неактивна. Изменение доступа станет доступно после восстановления.';
  if (message === 'LAST_ORGANIZATION_ADMIN') return 'Чтобы снять права у последнего администратора, сначала добавьте другого сотрудника.';
  if (message === 'ADMIN_EMAIL_ALREADY_LINKED') return 'Эта почта уже привязана к другому аккаунту. Укажите отдельную именную почту.';
  if (error?.status === 401) return 'Сессия истекла. Войдите снова; введённые данные формы сохранены в этой вкладке.';
  if (error?.name === 'RequestDeadlineError') return 'Не удалось подтвердить результат операции. Обновите список перед безопасным повтором.';
  if (error instanceof TypeError) return 'Не удалось связаться с сервером. Проверьте соединение.';
  if (Number(error?.status) >= 500) return fallback + ' Произошла ошибка сервиса.';
  return message || fallback;
};

const invitationRevokeErrorMessage = (error) => {
  const message = String(error?.message || '');
  const errorCode = String(error?.code || '');
  const labels = {
    INVITATION_ALREADY_USED: 'Приглашение уже использовано. Обычный вход и назначение участника сохранены.',
    INVITATION_NOT_FOUND: 'Приглашение больше не найдено. Список участников обновлён.',
    INVITATION_STATE_CHANGED: 'Состояние участника изменилось: приглашение нельзя отозвать после начала знакомства. Список участников обновлён.',
  };
  const code = Object.keys(labels).find((item) => errorCode === item || message.includes(item));
  return code ? labels[code] : (message || 'Не удалось отозвать приглашение.');
};

const captureFormDraft = (organizationId, form, { assessmentRef: assessmentOverride = null, updateSelected = true } = {}) => {
  const fields = editableFields(form);
  const assignmentField = form.querySelector('[name="assignment_ref"]');
  const assignmentRef = assessmentOverride ?? assignmentField?.value ?? form?.dataset?.assessmentRef ?? '';
  const view = form.closest('[data-admin-view]');
  const selectedRef = selectedAssessmentRefs.get(organizationKey(organizationId)) || '';
  const changedActiveScope = assessmentOverride === null && updateSelected && assignmentRef && selectedRef &&
    assignmentRef.trim() !== selectedRef && !view?.classList.contains('hidden');
  const storageRef = changedActiveScope ? selectedRef : assignmentRef;
  if (updateSelected && assignmentRef && !view?.classList.contains('hidden')) {
    selectedAssessmentRefs.set(organizationKey(organizationId), assignmentRef.trim());
  }
  const draftKey = formDraftKey(organizationId, form, storageRef);
  // A pristine form is not a user draft. In particular, an untouched empty form
  // must not mask the confirmed revision returned by the initial async GET.
  if (!managementDrafts.has(draftKey) && renderedFormSignatures.get(form) === formSignature(form)) return;
  managementDrafts.set(draftKey, {
    fields: Object.fromEntries(fields.map((field) => [field.name + ':' + field.value,
      { name: field.name, value: field === assignmentField && (assessmentOverride !== null || changedActiveScope)
        ? storageRef : field.value, checked: field.checked, type: field.type }])),
    focusedName: form.contains(document.activeElement) ? document.activeElement?.name || null : null,
    csvFileName: form.querySelector('input[type="file"][name="csv"]')?.files?.[0]?.name ||
      form.querySelector('[data-csv-reselect]')?.dataset.csvReselect || '',
  });
};

const captureParticipantSelection = (organizationId, card) => {
  const fields = [...card.querySelectorAll('input[name="invitation_email"]')];
  const assessmentRef = selectedAssessmentRefs.get(organizationKey(organizationId)) || '';
  managementDrafts.set(organizationKey(organizationId) + ':participant-selection:' + assessmentRef, {
    fields: Object.fromEntries(fields.map((field) => [field.value, { value: field.value, checked: field.checked }])),
  });
};

const syncParticipantSelection = (card) => {
  const participants = [...card.querySelectorAll('input[name="invitation_email"]')];
  const selectedCount = participants.filter((item) => item.checked).length;
  const selectAll = card.querySelector('input[name="select_all_participants"]');
  if (selectAll) {
    selectAll.checked = selectedCount === participants.length && participants.length > 0;
    selectAll.indeterminate = selectedCount > 0 && selectedCount < participants.length;
  }
  const counter = card.querySelector('[data-selected-count]');
  if (counter) counter.textContent = String(selectedCount);
  const bulkActions = card.querySelector('[data-bulk-actions]');
  if (bulkActions) bulkActions.hidden = selectedCount === 0;
};

export const captureAdminOrganizationsDraft = () => {
  if (adminOrganizationsPanel.classList.contains('hidden')) return;
  adminOrganizationsList.querySelectorAll('[data-organization-id]').forEach((card) => {
    const organizationId = Number(card.getAttribute('data-organization-id'));
    const questionnaireAccessDenied = questionnaireLoadStates.get(organizationKey(organizationId))?.accessDenied;
    card.querySelectorAll('form[data-action]').forEach((form) => {
      if (questionnaireAccessDenied && ['preview-early-data', 'preview-questionnaire'].includes(form.dataset.action)) return;
      captureFormDraft(organizationId, form);
    });
    captureParticipantSelection(organizationId, card);
    const preview = card.querySelector('.admin-questionnaire-preview');
    if (preview && !questionnaireAccessDenied) captureFormDraft(organizationId, preview);
  });
};

const restoreFormDraft = (organizationId, form) => {
  const selectedRef = selectedAssessmentRefs.get(organizationKey(organizationId));
  const assignmentField = form.querySelector('[name="assignment_ref"]');
  if (assignmentField && assignmentField.type !== 'hidden' && selectedRef) assignmentField.value = selectedRef;
  const assessmentRef = assignmentField?.value || form?.dataset?.assessmentRef || '';
  const draft = managementDrafts.get(formDraftKey(organizationId, form, assessmentRef));
  if (!draft) return false;
  editableFields(form).forEach((field) => {
    const candidates = Object.values(draft.fields).filter((item) => item.name === field.name);
    const saved = ['checkbox', 'radio'].includes(field.type)
      ? candidates.find((item) => item.value === field.value)
      : candidates[0];
    if (!saved) return;
    if (['checkbox', 'radio'].includes(field.type)) field.checked = saved.checked;
    else field.value = saved.value;
  });
  if (draft.csvFileName && form.querySelector('input[type="file"][name="csv"]') &&
      !form.querySelector('[data-csv-reselect]')) {
    const notice = document.createElement('p');
    notice.dataset.csvReselect = draft.csvFileName;
    notice.className = 'form-status';
    notice.textContent = 'Выберите CSV-файл повторно. Остальные поля сохранены.';
    form.querySelector('input[type="file"][name="csv"]').after(notice);
  }
  form.querySelector('[name="' + CSS.escape(draft.focusedName || '') + '"]')?.focus({ preventScroll: true });
  return true;
};

const restoreConfirmedRevisionForm = (form, revision) => {
  if (!form || !revision) return false;
  if (form.dataset.action !== 'preview-early-data') return true;
  const answers = revision.answers_json || {};
  const values = {
    organization_name: answers.C01?.name,
    organization_type: answers.C01?.organization_type,
    industry: answers.C01?.industry,
    activity_description: answers.C01?.activity_description,
    purpose: answers.C02a?.participant_text,
    results_usage: answers.C03?.participant_text,
    case_reality_level: answers.C17?.case_reality_level,
    organization_name_usage_rules: answers.C17?.organization_name_usage_rules,
  };
  let restored = false;
  Object.entries(values).forEach(([name, value]) => {
    const field = form.querySelector('[name="' + name + '"]');
    if (!field || value === undefined || value === null) return;
    field.value = String(value);
    restored = true;
  });
  return restored;
};

const restoreAdminOrganizationsDraft = () => {
  adminOrganizationsList.querySelectorAll('[data-organization-id]').forEach((card) => {
    const organizationId = Number(card.getAttribute('data-organization-id'));
    card.querySelectorAll('form[data-action], .admin-questionnaire-preview').forEach((form) =>
      restoreFormDraft(organizationId, form));
    const assessmentRef = selectedAssessmentRefs.get(organizationKey(organizationId)) || '';
    const selection = managementDrafts.get(organizationKey(organizationId) + ':participant-selection:' + assessmentRef);
    card.querySelectorAll('input[name="invitation_email"]').forEach((field) => {
      if (selection?.fields?.[field.value]) field.checked = selection.fields[field.value].checked;
    });
    syncParticipantSelection(card);
    card.querySelectorAll('.admin-questionnaire-preview').forEach((preview) =>
      updateAdminOrganizationQuestionnaireConfirmState(organizationId, preview));
  });
};

const clearAdminOrganizationsSessionState = () => {
  assignmentViewGeneration += 1;
  selectedOrganizationId = null;
  invitationRequestsInFlight.clear();
  invitationResults.clear();
  invitationReadbacks.clear();
  assignmentSourceRequests.clear();
  assignmentOperationIds.clear();
  cancellationOperationIds.clear();
  cancellationRequestsInFlight.clear();
  programConnectionOperationIds.clear();
  programConnectionOutcome = null;
  programConnectionFeedbackGeneration += 1;
  unverifiedProgramConnections.clear();
  programConnectionRequestsInFlight.clear();
  questionnairePreviews.clear();
  questionnaireRevisions.clear();
  staleQuestionnairePreviews.clear();
  questionnairePreviewRequestGenerations.clear();
  earlyDataPreviewAttempts.clear();
  organizationViews.clear();
  managementDrafts.clear();
  renderedFormSignatures = new WeakMap();
  selectedAssessmentRefs.clear();
  questionnaireConfirmRequestGenerations.clear();
  questionnaireConfirmRequestsInFlight.clear();
  questionnaireLoadStates.clear();
  questionnaireConfirmOutcomes.clear();
  operationAnchor = null;
  restoredManagementIdentity = null;
  organizationsReadStale = false;
  organizationsReadStaleReason = '';
};

window.addEventListener('agent4k:assessment-context-cleared', clearAdminOrganizationsSessionState);

const clearInaccessibleOrganizationState = (organizations) => {
  const allowed = new Set(organizations.map((org) => organizationKey(org.id)));
  if (programConnectionOutcome && !allowed.has(organizationKey(programConnectionOutcome.organizationId))) {
    clearProgramConnectionFeedback();
  }
  for (const drafts of [managementDrafts, selectedAssessmentRefs, questionnairePreviews, questionnaireRevisions,
    questionnairePreviewRequestGenerations, earlyDataPreviewAttempts, questionnaireConfirmOutcomes]) {
    for (const key of drafts.keys()) {
      const scopedKey = String(key);
      if (scopedKey.startsWith(currentIdentityKey() + ':') &&
          ![...allowed].some((allowedKey) => scopedKey === allowedKey || scopedKey.startsWith(allowedKey + ':'))) {
        drafts.delete(key);
      }
    }
  }
  for (const key of staleQuestionnairePreviews) {
    if (String(key).startsWith(currentIdentityKey() + ':') &&
        ![...allowed].some((allowedKey) => String(key).startsWith(allowedKey + ':'))) {
      staleQuestionnairePreviews.delete(key);
    }
  }
  for (const organizationId of organizationViews.keys()) {
    if (!organizations.some((org) => Number(org.id) === Number(organizationId))) organizationViews.delete(organizationId);
  }
  for (const key of unverifiedProgramConnections) {
    if (!allowed.has(key)) unverifiedProgramConnections.delete(key);
  }
};

const escapeHtml = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const contextChoiceSelect = (field, currentValue) => {
  const current = String(currentValue || '');
  const choices = adminContextChoices.fields[field];
  const options = choices.map((value) => '<option value="' + escapeHtml(value) + '"' +
    (value === current ? ' selected' : '') + '>' + escapeHtml(value) + '</option>').join('');
  const legacy = current && !choices.includes(current)
    ? '<option value="' + escapeHtml(current) + '" selected>Ранее сохранено: ' + escapeHtml(current) + '</option>' : '';
  return '<select name="' + field + '">' +
    '<option value="" disabled' + (current ? '' : ' selected') + '>Выберите вариант</option>' +
    options + legacy + '</select>';
};

const readinessLabel = (status) => ({
  ready: 'Готово', data_missing: 'Данные не заполнены', draft_unconfirmed: 'Черновик не подтверждён',
  incomplete: 'Требуется заполнение', not_started: 'Не начато', in_progress: 'Идёт подготовка',
  idle: 'Не запущено', preparing: 'Идёт подготовка',
})[status] || 'Не удалось проверить';
const readinessRow = (title, item, target) => '<li><strong>' + escapeHtml(title) + ': ' +
  escapeHtml(readinessLabel(item?.status)) + '</strong><span>' +
  escapeHtml(item?.message || 'Не удалось получить состояние. Повторите открытие раздела.') + '</span>' +
  (target ? '<button type="button" class="text-button" data-action="show-admin-view" data-view="' +
    target + '">Перейти</button>' : '') + '</li>';
const readinessMarkup = (selectedRef, readiness) => !selectedRef || !readiness
  ? '<div class="admin-readiness-panel admin-readiness-panel--empty" data-readiness-status="not-selected"><strong>' +
    (selectedRef ? 'Готовность выбранной оценки ещё не рассчитана' : 'Выберите программу и роль в оценке') +
    '</strong><p>' + (selectedRef
      ? 'Сохраните сведения или загрузите анкету, чтобы увидеть готовность этой оценки.'
      : 'Подключённая программа определяет оценку автоматически.') + '</p></div>'
  : '<div class="admin-readiness-panel" data-readiness-status="' +
  escapeHtml(readiness?.status || 'unavailable') + '"><strong>Готовность выбранной оценки</strong><ul>' +
  readinessRow('Ранние сведения', readiness?.early, 'organization-data') +
  readinessRow('Контекст', readiness?.context, 'organization-data') +
  readinessRow('Участники', readiness?.roles, readiness?.roles?.action_view || null) +
  readinessRow('Подготовка', readiness?.preparation, null) + '</ul>' +
  '<p>Добавлять участников можно до заполнения анкеты. Приглашение, назначение и начало оценки проверяются сервером отдельно.</p></div>';

const organizationDataReadiness = (programState, readiness, roleLabel, sourceMarkup) => {
  const program = programState.program;
  if (!program) {
    return '<div class="admin-readiness-panel admin-data-readiness" data-questionnaire-program-state="' +
      programState.status + '"><p>' + escapeHtml(programState.message) + '</p>' +
      (programState.status === 'unknown'
        ? '<button type="button" class="text-button" data-action="check-program-connection">Проверить состояние подключения</button>' : '') + '</div>';
  }
  const label = readiness ? readinessLabel(readiness.status) : 'ещё не рассчитана';
  return '<details class="admin-readiness-panel admin-data-readiness" data-readiness-status="' +
    escapeHtml(readiness?.status || 'not-calculated') + '"><summary>Готовность оценки · ' + escapeHtml(label) +
    '</summary><section class="admin-assessment-identity" aria-label="Выбранная оценка программы"><strong>' +
    escapeHtml(programIdentity(program)) + '</strong><dl><dt>Версия программы</dt><dd>' +
    escapeHtml(program.program_version) + '</dd><dt>Роль в оценке</dt><dd>' + escapeHtml(roleLabel) + '</dd></dl></section>' +
    (readiness ? '<ul>' + readinessRow('Ранние сведения', readiness.early, null) +
      readinessRow('Контекст', readiness.context, null) +
      readinessRow('Участники', readiness.roles, readiness.roles?.action_view || null) +
      readinessRow('Подготовка', readiness.preparation, null) + '</ul>'
      : '<p>Подтвердите сведения, чтобы проверить готовность оценки.</p>') + sourceMarkup + '</details>';
};

const participantPreviewMarkup = '<aside class="admin-data-participant-preview" data-organization-participant-preview>' +
  '<h4>Как увидит участник</h4><div class="admin-data-participant-briefing">' +
  '<h5 data-preview-value="organization_name" data-empty="Название организации"></h5>' +
  '<dl><dt>Зачем проводится оценка</dt><dd data-preview-value="purpose" data-empty="Цель пока не указана."></dd>' +
  '<dt>Как будут использоваться результаты</dt><dd data-preview-value="results_usage" data-empty="Использование результатов пока не указано."></dd>' +
  '<dt>Кто увидит результат</dt><dd>' + participantReportAudience + '</dd></dl></div></aside>';

const operationRoot = () => {
  if (!operationAnchor || operationAnchor.identity !== currentIdentityKey()) return null;
  const card = adminOrganizationsList.querySelector('[data-organization-id="' + operationAnchor.organizationId + '"]');
  return card?.querySelector(operationAnchor.selector) || card?.querySelector('.admin-questionnaire-confirmation') || null;
};

const setLocalOperationStatus = (root, message, tone) => {
  let local = root?.querySelector('[data-operation-status]');
  if (!local && root) {
    local = document.createElement('p');
    local.className = 'admin-organizations-status';
    local.dataset.operationStatus = '';
    local.setAttribute('aria-live', 'polite');
    local.setAttribute('role', 'status');
    local.tabIndex = -1;
    root.append(local);
  }
  if (local) {
    local.textContent = message || '';
    local.dataset.tone = tone;
    local.classList.toggle('hidden', !message);
  }
  return local;
};

const organizationDataForm = (organizationId) => adminOrganizationsList.querySelector(
  '[data-organization-id="' + Number(organizationId) + '"] form[data-action="preview-early-data"]',
);
const confirmationNeedsReadback = (outcome) => ['unknown', 'conflict', 'rejected'].includes(outcome?.status);

const updateOrganizationDataForm = (form) => {
  if (!form) return;
  const organizationId = Number(form.closest('[data-organization-id]').dataset.organizationId);
  const key = assessmentKey(organizationId, form.dataset.assessmentRef);
  const outcome = questionnaireConfirmOutcomes.get(key);
  const busy = earlyDataPreviewAttempts.get(key)?.inFlight || questionnaireConfirmRequestsInFlight.has(key);
  const unchanged = form.hasAttribute('data-confirmed-form') && editableFields(form).every((field) =>
    field instanceof HTMLSelectElement ? field.selectedOptions[0]?.defaultSelected : field.value === field.defaultValue);

  const preview = form.parentElement.querySelector('[data-organization-participant-preview]');
  preview.querySelectorAll('[data-preview-value]').forEach((value) => {
    value.textContent = form.elements[value.dataset.previewValue].value.trim() || value.dataset.empty;
  });

  const reviewButton = form.querySelector('[data-action="confirm-questionnaire"]');
  const needsReadback = confirmationNeedsReadback(outcome);
  const canReview = reviewButton && !staleQuestionnairePreviews.has(key) && !needsReadback;
  if (reviewButton) {
    reviewButton.hidden = !canReview || unchanged;
    updateAdminOrganizationQuestionnaireConfirmState(organizationId, reviewButton.closest('.admin-questionnaire-preview'));
  }
  const renameNotice = form.querySelector('[data-organization-rename]');
  if (renameNotice) renameNotice.hidden = !canReview;
  form.querySelector('[data-organization-confirmed]').hidden = !unchanged || needsReadback;
  const previous = form.querySelector('[data-previous-organization-revision]');
  if (previous) previous.hidden = unchanged;
  const submit = form.querySelector('[data-early-data-submit]');
  submit.hidden = unchanged || Boolean(canReview) || needsReadback;
  submit.disabled = Boolean(busy) || form.hasAttribute('data-confirmation-unavailable');
  submit.textContent = earlyDataPreviewAttempts.get(key)?.inFlight ? 'Проверяем сведения…' :
    busy ? 'Подтверждаем…' : 'Подтвердить сведения';
  const check = form.querySelector('[data-action="check-questionnaire-confirmation"]');
  if (check) check.disabled = Boolean(busy);
};

const organizationDataIsVisible = (organizationId, assessmentRef) =>
  state.currentScreen === 'admin-organizations' && Number(selectedOrganizationId) === Number(organizationId) &&
  organizationViews.get(Number(organizationId)) === 'organization-data' &&
  organizationDataForm(organizationId)?.dataset.assessmentRef === assessmentRef;
const focusOrganizationDataAction = (organizationId, assessmentRef) => {
  if (!organizationDataIsVisible(organizationId, assessmentRef) || document.activeElement !== document.body) return;
  organizationDataForm(organizationId).querySelector(
    '[data-organization-confirmed]:not([hidden]), .admin-questionnaire-confirmation button:not([hidden]):enabled',
  )?.focus({ preventScroll: true });
};

const setOrganizationDataStatus = (organizationId, assessmentRef, message, tone) => {
  if (!organizationDataIsVisible(organizationId, assessmentRef)) return;
  const form = organizationDataForm(organizationId);
  const root = form.querySelector('.admin-questionnaire-confirmation');
  const focus = !form.contains(document.activeElement) || root.contains(document.activeElement);
  setStatus(message, tone, root, { focus });
};

const setStatus = (message, tone = 'muted', root = operationRoot(), { focus = true } = {}) => {
  if (!adminOrganizationsStatus) return;
  adminOrganizationsStatus.textContent = message || '';
  adminOrganizationsStatus.classList.toggle('hidden', !message);
  adminOrganizationsStatus.dataset.tone = tone;
  const local = setLocalOperationStatus(root, message, tone);
  adminOrganizationsStatus.classList.toggle('hidden', !message || Boolean(local));
  if (focus && message && tone !== 'loading' && !adminOrganizationsPanel.classList.contains('hidden')) {
    const target = local || adminOrganizationsStatus;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: 'nearest' });
  }
};

const programConnectionForm = (organizationId) => adminOrganizationsList?.querySelector(
  '[data-organization-id="' + Number(organizationId) + '"] form[data-action="connect-assessment-program"]',
);
const connectedProgramId = (organizationId) => Number(state.adminOrganizations?.items
  ?.find((org) => Number(org.id) === Number(organizationId))?.assessment_program?.program_definition_id || 0);
const clearProgramConnectionFeedback = () => {
  programConnectionFeedbackGeneration += 1;
  if (programConnectionOutcome && adminOrganizationsStatus?.textContent === programConnectionOutcome.message) {
    adminOrganizationsStatus.textContent = '';
    adminOrganizationsStatus.classList.add('hidden');
  }
  programConnectionOutcome = null;
  adminOrganizationsList?.querySelectorAll('form[data-action="connect-assessment-program"] [data-operation-status]')
    .forEach((element) => element.remove());
};
const restoreProgramConnectionFeedback = () => {
  const outcome = programConnectionOutcome;
  if (!outcome) return;
  const form = programConnectionForm(outcome.organizationId);
  if (outcome.identityEpoch !== state.identityEpoch || outcome.identityKey !== currentIdentityKey() ||
      Number(selectedOrganizationId) !== outcome.organizationId ||
      Number(form?.elements.program_definition_id?.value) !== outcome.programDefinitionId ||
      connectedProgramId(outcome.organizationId) !== outcome.connectedProgramDefinitionId) {
    clearProgramConnectionFeedback();
    return;
  }
  // Rehydrate only this exact form, without replaying focus/global messages.
  setLocalOperationStatus(form, outcome.message, outcome.tone);
};

// Remember the action by stable DOM attributes: mutations re-render the card.
const trackOperation = (event) => {
  const target = event.target instanceof Element ? event.target : null;
  const form = event.type === 'submit' ? target?.closest('form[data-action]') : null;
  const button = event.type === 'click' ? target?.closest('button[data-action]') : null;
  if (!form && (!button || ['show-admin-view', 'refresh-questionnaire-preview', 'use-legacy-profile',
    'open-member-card', 'open-member-report', 'view-admin-access'].includes(button.dataset.action))) return;
  const root = form || button.closest('.admin-questionnaire-preview') || button.parentElement;
  const card = root?.closest('[data-organization-id]');
  if (!card) return;
  clearProgramConnectionFeedback();
  const selector = form ? 'form[data-action="' + CSS.escape(form.dataset.action) + '"]'
    : root.matches('.admin-questionnaire-preview')
      ? '.admin-questionnaire-preview[data-questionnaire-revision-id="' + root.dataset.questionnaireRevisionId + '"]'
      : root.closest('[data-organization-admins]') ? '[data-organization-admins]'
        : '[data-admin-view="' + CSS.escape(root.closest('[data-admin-view]')?.dataset.adminView || 'people') + '"]';
  operationAnchor = { identity: currentIdentityKey(), organizationId: Number(card.dataset.organizationId), selector };
  // Keep the result anchor, but a confirmation dialog is not a running command.
  if (form?.dataset.action !== 'preview-early-data' &&
      !['cancel-member-assignment', 'revoke-member-invitation', 'purge-account', 'delete-admin',
        'confirm-questionnaire', 'check-questionnaire-confirmation', 'open-organization-reports'].includes(button?.dataset.action)) {
    setStatus('Выполняем действие…', 'loading');
  }
};
adminOrganizationsPanel?.addEventListener('submit', trackOperation, true);
adminOrganizationsPanel?.addEventListener('click', trackOperation, true);
adminOrganizationsPanel?.addEventListener('change', (event) => {
  if (event.target instanceof Element && event.target.matches(
    'form[data-action="connect-assessment-program"] select[name="program_definition_id"]',
  )) clearProgramConnectionFeedback();
});

const requestOrganizations = async (url, options, fallbackMessage, isCurrent = () => true) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const requestGeneration = ++organizationsRequestGeneration;
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });
  const data = await readApiResponse(response, fallbackMessage);
  if (!isCurrent() || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
      requestGeneration !== organizationsRequestGeneration) return null;
  // Preserve live input, not the earlier draft captured before this request.
  // Keep this after the identity/generation guard and before replacing the data.
  captureAdminOrganizationsDraft();
  organizationsReadStale = false;
  organizationsReadStaleReason = '';
  state.adminOrganizations = data;
  persistAssessmentContext();
  renderAdminOrganizations();
  return data;
};

const markOrganizationsReadStale = (reason) => {
  captureAdminOrganizationsDraft();
  organizationsReadStale = true;
  organizationsReadStaleReason = String(reason || 'Не удалось подтвердить актуальное состояние.');
  renderAdminOrganizations();
};

export const refreshAdminOrganizationsSafely = async ({ isCurrent = () => true } = {}) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const requestGeneration = organizationsRequestGeneration + 1;
  try {
    const data = await requestOrganizations(
      '/users/admin/organizations',
      { method: 'GET', headers: {} },
      'Не удалось обновить организации.', isCurrent,
    );
    if (!data || !isCurrent()) return false;
    setStatus('Состояние организаций обновлено.', 'success', undefined, { focus: false });
    return true;
  } catch (error) {
    if (!isCurrent() || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
        organizationsRequestGeneration !== requestGeneration) return false;
    markOrganizationsReadStale(error.message || 'Не удалось обновить организации.');
    setStatus('Состояние не обновлено. Последние показанные данные могут быть устаревшими.', 'error', undefined, { focus: false });
    return false;
  }
};

const requestOrganizationsImport = async (url, csvText) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const requestGeneration = ++organizationsRequestGeneration;
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_text: csvText }),
  });
  const data = await readApiResponse(response, 'Не удалось импортировать участников.');
  if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
      organizationsRequestGeneration !== requestGeneration) return null;
  captureAdminOrganizationsDraft();
  organizationsReadStale = false;
  organizationsReadStaleReason = '';
  state.adminOrganizations = data.organizations || data;
  persistAssessmentContext();
  renderAdminOrganizations();
  return data;
};

export const loadAdminOrganizations = async ({ isCurrent = () => true } = {}) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const requestGeneration = organizationsRequestGeneration + 1;
  let data;
  try {
    data = await requestOrganizations(
      '/users/admin/organizations',
      { method: 'GET', headers: {} },
      'Не удалось загрузить организации.', isCurrent,
    );
  } catch (error) {
    if (!isCurrent() || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
        organizationsRequestGeneration !== requestGeneration) return null;
    markOrganizationsReadStale('Не удалось подтвердить актуальное подключение программы.');
    throw error;
  }
  if (!data || !isCurrent() || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  await Promise.all((data.items || []).map((org) => loadQuestionnaireRevisions(
    org.id, { identityEpoch, identityKey, render: false, isCurrent },
  )));
  if (!isCurrent() || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  captureAdminOrganizationsDraft();
  renderAdminOrganizations();
  return data;
};

const loadQuestionnaireRevisions = async (organizationId, context = {}) => {
  const identityEpoch = context.identityEpoch ?? state.identityEpoch;
  const identityKey = context.identityKey ?? currentIdentityKey();
  if (context.isCurrent?.() === false || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  const key = organizationKey(organizationId);
  const generation = (questionnaireLoadGenerations.get(key) || 0) + 1;
  questionnaireLoadGenerations.set(key, generation);
  questionnaireLoadStates.set(key, { status: 'loading' });
  if (context.render !== false) {
    captureAdminOrganizationsDraft();
    renderAdminOrganizations();
  }
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire', {
      credentials: 'same-origin',
    });
    const result = await readApiResponse(response, 'Не удалось загрузить сохранённые анкеты.');
    if (context.isCurrent?.() === false || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
        questionnaireLoadGenerations.get(key) !== generation) return null;
    const items = Array.isArray(result?.items) ? result.items : [];
    const merged = new Map(items.map((item) => [item.assignment_ref, item]));
    for (const cached of questionnaireRevisions.get(key) || []) {
      const received = merged.get(cached.assignment_ref);
      if (received) merged.set(cached.assignment_ref, mergeQuestionnaireRevision(received, cached));
    }
    questionnaireRevisions.set(key, [...merged.values()]);
    questionnaireLoadStates.set(key, { status: items.length ? 'ready' : 'empty' });
    if (context.render !== false) {
      captureAdminOrganizationsDraft();
      renderAdminOrganizations();
    }
    return items;
  } catch (error) {
    if (context.isCurrent?.() === false || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
        questionnaireLoadGenerations.get(key) !== generation) return null;
    const accessDenied = error?.status === 401 || error?.status === 403;
    if (accessDenied) {
      questionnaireRevisions.delete(key);
      // A denied read must not resurrect the snapshot captured before the GET.
      for (const draftKey of managementDrafts.keys()) {
        if (['preview-early-data', 'preview-questionnaire', 'questionnaire-preview']
          .some((action) => String(draftKey).startsWith(key + ':' + action + ':'))) managementDrafts.delete(draftKey);
      }
      for (const scopedState of [questionnairePreviews, earlyDataPreviewAttempts, questionnaireConfirmOutcomes]) {
        for (const scopeKey of scopedState.keys()) {
          if (String(scopeKey).startsWith(key + ':')) scopedState.delete(scopeKey);
        }
      }
    }
    questionnaireLoadStates.set(key, {
      status: 'error', accessDenied, message: accessDenied
        ? 'Нет доступа к сохранённым анкетам этой организации.'
        : error.message || 'Не удалось загрузить сохранённые анкеты.',
    });
    if (context.render !== false) {
      if (!accessDenied) captureAdminOrganizationsDraft();
      renderAdminOrganizations();
    }
    return null;
  }
};

export const retryAdminOrganizationQuestionnaireLoad = (organizationId) =>
  loadQuestionnaireRevisions(organizationId);

export const createAdminOrganization = async () => {
  const name = String(adminOrganizationNameInput?.value || '').trim();
  const code = String(adminOrganizationCodeInput?.value || '').trim();
  if (!name || !code) {
    setStatus('Укажите название и код организации.', 'error');
    return;
  }
  if (adminOrganizationCreateButton) {
    adminOrganizationCreateButton.disabled = true;
  }
  try {
    await requestOrganizations(
      '/users/admin/organizations',
      { method: 'POST', body: JSON.stringify({ name, code }) },
      'Не удалось создать организацию.',
    );
    if (adminOrganizationNameInput) adminOrganizationNameInput.value = '';
    if (adminOrganizationCodeInput) adminOrganizationCodeInput.value = '';
    setStatus('Организация создана.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось создать организацию.', 'error');
  } finally {
    if (adminOrganizationCreateButton) {
      adminOrganizationCreateButton.disabled = false;
    }
  }
};

export const selectAdminOrganization = (organizationId) => {
  assignmentViewGeneration += 1;
  clearProgramConnectionFeedback();
  captureAdminOrganizationsDraft();
  selectedOrganizationId = Number(organizationId) || null;
  saveManagementSelection();
  renderAdminOrganizations();
};

export const selectAdminOrganizationView = (organizationId, view) => {
  const restoreFocus = document.activeElement?.matches('[data-action="show-admin-view"]');
  assignmentViewGeneration += 1;
  captureAdminOrganizationsDraft();
  organizationViews.set(Number(organizationId), managementSections.includes(view) ? view : 'people');
  saveManagementSelection();
  renderAdminOrganizations();
  if (restoreFocus) adminOrganizationsList.querySelector('.admin-organization-step.current')?.focus({ preventScroll: true });
};

export const selectAdminOrganizationAssessment = (organizationId, form, assessmentRef, previousRef = '') => {
  assignmentViewGeneration += 1;
  const nextRef = String(assessmentRef || '').trim();
  const oldRef = String(previousRef || selectedAssessmentRefs.get(organizationKey(organizationId)) || '').trim();
  if (oldRef && oldRef !== nextRef) {
    captureFormDraft(organizationId, form, { assessmentRef: oldRef, updateSelected: false });
  }
  selectedAssessmentRefs.set(organizationKey(organizationId), nextRef);
  saveManagementSelection();
  const card = form.closest('[data-organization-id]');
  const revision = (questionnaireRevisions.get(organizationKey(organizationId)) || [])
    .find((item) => String(item.assignment_ref || '').trim() === nextRef);
  card?.querySelectorAll('form[data-action="preview-early-data"], form[data-action="preview-questionnaire"]')
    .forEach((assessmentForm) => {
      const assignmentField = assessmentForm.querySelector('[name="assignment_ref"]');
      if (assignmentField) assignmentField.value = nextRef;
      if (oldRef === nextRef) return;
      editableFields(assessmentForm).forEach((field) => {
        if (field.name === 'assignment_ref') return;
        if (['checkbox', 'radio'].includes(field.type)) field.checked = false;
        else field.value = '';
      });
      const restoredDraft = restoreFormDraft(organizationId, assessmentForm);
      if (!restoredDraft) restoreConfirmedRevisionForm(assessmentForm, revision);
      renderedFormSignatures.set(assessmentForm, formSignature(assessmentForm));
    });
  card?.querySelectorAll('.admin-questionnaire-preview').forEach((preview) => preview.remove());
  card?.querySelectorAll('[data-admin-view="questionnaire"] .admin-readiness-panel').forEach((panel) => {
    panel.outerHTML = readinessMarkup(nextRef, revision?.readiness || null);
  });
  updateOrganizationDataForm(organizationDataForm(organizationId));
};

export const getSelectedAdminOrganizationAssessment = (organizationId) =>
  selectedAssessmentRefs.get(organizationKey(organizationId)) ||
  (questionnaireRevisions.get(organizationKey(organizationId)) || [])[0]?.assignment_ref || '';

export const markAdminOrganizationQuestionnairePreviewStale = (organizationId, assessmentRef = '') => {
  const selectedRef = String(assessmentRef || getSelectedAdminOrganizationAssessment(organizationId)).trim();
  const key = assessmentKey(organizationId, selectedRef);
  if (questionnairePreviews.has(key)) {
    staleQuestionnairePreviews.add(key);
    const preview = organizationDataForm(organizationId)?.querySelector('.admin-questionnaire-preview');
    const stale = preview?.querySelector('[data-preview-stale]');
    if (stale) stale.hidden = false;
  }
  updateOrganizationDataForm(organizationDataForm(organizationId));
};

export const updateAdminOrganizationQuestionnaireConfirmState = (organizationId, preview) => {
  if (!preview) return;
  const busy = questionnaireConfirmRequestsInFlight.has(assessmentKey(organizationId, preview.dataset.assessmentRef));
  const outcome = questionnaireConfirmOutcomes.get(assessmentKey(organizationId, preview.dataset.assessmentRef));
  const scope = organizationProgramState(organizationId);
  const confirmButton = preview.querySelector('[data-action="confirm-questionnaire"]');
  if (confirmButton) confirmButton.disabled = busy || confirmationNeedsReadback(outcome) ||
    scope.status !== 'confirmed' || scope.assessmentRef !== preview.dataset.assessmentRef ||
    staleQuestionnairePreviews.has(assessmentKey(organizationId, preview.dataset.assessmentRef));
};

export const updateAdminOrganizationProfile = async (organizationId, payload) => {
  try {
    selectedOrganizationId = Number(organizationId);
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId,
      { method: 'PATCH', body: JSON.stringify(payload) },
      'Не удалось сохранить карточку организации.',
    );
    setStatus('Карточка организации сохранена.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось сохранить карточку организации.', 'error');
  }
};

export const addAdminOrganizationDomain = async (organizationId, domain) => {
  const normalizedDomain = String(domain || '').trim();
  if (!normalizedDomain) {
    setStatus('Укажите домен организации.', 'error');
    return;
  }
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/domains',
      { method: 'POST', body: JSON.stringify({ domain: normalizedDomain }) },
      'Не удалось добавить домен.',
    );
    setStatus('Домен добавлен.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось добавить домен.', 'error');
  }
};

export const deleteAdminOrganizationDomain = async (organizationId, domain) => {
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/domains?domain=' + encodeURIComponent(domain),
      { method: 'DELETE', headers: {} },
      'Не удалось удалить домен.',
    );
    setStatus('Домен удален.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось удалить домен.', 'error');
  }
};

const organizationAdminSection = (organizationId) => adminOrganizationsList?.querySelector(
  '[data-organization-id="' + Number(organizationId) + '"] [data-organization-admins]',
);

export const addAdminOrganizationAdmin = async (organizationId, { email, full_name }) => {
  const normalizedEmail = String(email || '').trim();
  if (!normalizedEmail) return false;
  const fallback = 'Не удалось добавить администратора.';
  try {
    const identityEpoch = state.identityEpoch;
    const identityKey = currentIdentityKey();
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/admins',
      { method: 'POST', body: JSON.stringify({ email: normalizedEmail, full_name: full_name || null }) },
      fallback,
    );
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
        !await refreshAdminOrganizationsSafely()) return false;
    const section = organizationAdminSection(organizationId);
    const form = section?.querySelector('form[data-action="add-admin"]');
    if (form?.elements.email.value.trim() === normalizedEmail &&
        form.elements.full_name.value.trim() === full_name) form.reset();
    setStatus('Администратор добавлен.', 'success', section);
    return true;
  } catch (error) {
    setStatus(membershipErrorMessage(error, fallback), 'error', organizationAdminSection(organizationId));
    return false;
  }
};

export const deleteAdminOrganizationAdmin = async (organizationId, email) => {
  const fallback = 'Не удалось снять права администратора.';
  setStatus('Снимаем права администратора…', 'loading', organizationAdminSection(organizationId));
  try {
    const identityEpoch = state.identityEpoch;
    const identityKey = currentIdentityKey();
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/admins?email=' + encodeURIComponent(email),
      { method: 'DELETE', headers: {} },
      fallback,
    );
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
        !await refreshAdminOrganizationsSafely()) return;
    setStatus('Права администратора сняты.', 'success', organizationAdminSection(organizationId));
  } catch (error) {
    setStatus(membershipErrorMessage(error, fallback), 'error', organizationAdminSection(organizationId));
  }
};

export const addAdminOrganizationMember = async (organizationId, payload) => {
  const normalizedEmail = String(payload?.email || '').trim();
  const fullName = String(payload?.full_name || '').trim();
  const roleDescription = String(payload?.role_description || '').trim();
  if (!normalizedEmail || !fullName || !roleDescription) {
    setStatus('Укажите email, ФИО и должность участника.', 'error');
    return false;
  }
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/members',
      {
        method: 'POST',
        body: JSON.stringify({
          email: normalizedEmail,
          full_name: fullName,
          role_description: roleDescription,
          job_instructions: String(payload?.job_instructions || '').trim() || null,
        }),
      },
      'Не удалось привязать участника.',
    );
    setStatus('Участник привязан к организации.', 'success');
    return true;
  } catch (error) {
    setStatus(membershipErrorMessage(error, 'Не удалось привязать участника.'), 'error');
    return false;
  }
};

export const resetAdminOrganizationMemberPassword = async (organizationId, email) => {
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/members/reset-password?email=' + encodeURIComponent(email),
      { method: 'POST', headers: {} },
      'Не удалось сбросить пароль участника.',
    );
    setStatus('Пароль участника сброшен. При следующем входе пользователь задаст новый пароль.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось сбросить пароль участника.', 'error');
  }
};

export const sendAdminOrganizationMemberInvitation = async (
  organizationId, emailOrEmails, assignmentRef, { readOnly = false } = {},
) => {
  const emails = [...new Set((Array.isArray(emailOrEmails) ? emailOrEmails : [emailOrEmails])
    .map((email) => String(email || '').trim().toLowerCase())
    .filter(Boolean))].sort();
  const assessment = String(assignmentRef || '').trim();
  if (!assessment) {
    setStatus('Сначала выберите оценку в данных организации', 'error');
    offerAssessmentDataNavigation(organizationId, assessment);
    return;
  }
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const viewGeneration = assignmentViewGeneration;
  const currentScreen = state.currentScreen;
  const requestKey = identityKey + ':' + Number(organizationId) + ':' + assessment + ':' + emails.join(',');
  const inFlightKey = identityEpoch + ':' + requestKey;
  if (!emails.length) { setStatus('Выберите участников для приглашения', 'error'); return; }
  if (!identityKey || invitationRequestsInFlight.has(inFlightKey)) return;
  const isCurrent = () => state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey &&
    Number(selectedOrganizationId) === Number(organizationId) && assignmentViewGeneration === viewGeneration &&
    state.currentScreen === currentScreen;
  const existing = pendingInvitationOperations(identityKey).find((item) => item.requestKey === requestKey);
  const overlap = pendingInvitationOperations(identityKey).find(item => item.requestKey !== requestKey &&
    item.organizationId === Number(organizationId) && item.assignmentRef === assessment &&
    item.emails.some(email => emails.includes(email) && !item.results?.some(result => result.email === email && invitationFacts(result).outcome === 'failed')));
  if (overlap) {
    if (isCurrent()) setStatus('Не удалось подтвердить отправку. Проверьте прежнюю попытку для выбранных участников.', 'error');
    return;
  }
  if (readOnly && !existing) return;
  const operationId = existing?.operationId || createOperationId();
  const attemptCreatedAt = existing?.createdAt || new Date().toISOString();
  if (!existing && !savePendingInvitationOperation({ requestKey, operationId, organizationId: Number(organizationId),
    assignmentRef: assessment, emails, createdAt: attemptCreatedAt }, identityKey)) {
    clearPendingInvitationOperation(requestKey, identityKey);
    if (isCurrent()) setStatus('Не удалось подготовить отправку. Приглашения ещё не отправлялись', 'error');
    return;
  }
  const readback = async () => {
    const query = new URLSearchParams({ assignment_ref: assessment });
    emails.forEach((email) => query.append('email', email));
    const response = await fetch('/users/admin/organizations/' + organizationId + '/personal-invitations/operations/' +
      encodeURIComponent(operationId) + '?' + query.toString(), { credentials: 'same-origin' });
    return readApiResponse(response, 'Исход отправки пока неизвестен.');
  };
  let readingPrevious = Boolean(existing);
  let confirmedItems = Array.isArray(existing?.results) ? existing.results.map(safeInvitationItem) : [];
  const exactItems = (result) => {
    const items = exactInvitationItems(result, emails, confirmedItems, operationId);
    const complete = Array.isArray(result?.items) && result.items.length === emails.length &&
      emails.every(email => result.items.filter(item => String(item?.email || '').trim().toLowerCase() === email).length === 1);
    if (!complete) {
      // Preserve attributable facts from a partial receipt, then read this same
      // command. An extra recipient cannot establish any new batch outcome.
      confirmedItems = items;
      savePendingInvitationOperation({ requestKey, operationId, organizationId: Number(organizationId),
        assignmentRef: assessment, emails, createdAt: attemptCreatedAt, results: items }, identityKey);
      throw new Error('INVITATION_RESPONSE_INCOMPLETE');
    }
    return items;
  };
  const showItems = async (items) => {
    confirmedItems = items;
    const unresolved = items.some((item) => ['unknown', 'pending'].includes(invitationFacts(item).outcome));
    if (unresolved) savePendingInvitationOperation({ requestKey, operationId, organizationId: Number(organizationId),
      assignmentRef: assessment, emails, createdAt: attemptCreatedAt, results: items }, identityKey);
    if (!unresolved) clearPendingInvitationOperation(requestKey, identityKey);
    if (!isCurrent()) return;
    items.forEach(item => {
      const key = invitationResultKey(organizationId, assessment, item.email);
      const current = invitationResults.get(key);
      const created = item.created_at || attemptCreatedAt;
      if (current?.operation_id !== operationId && (Number(current?.invitation_id) > Number(item.invitation_id || 0) ||
          (current?.created_at && new Date(current.created_at) > new Date(created)))) return;
      invitationResults.set(key, { ...item, operation_id: operationId, created_at: created });
    });
    const outcome = (items.some(item => item.status === 'uncertain' && !item.invitation_id) ? 'Не удалось подтвердить исход для всех выбранных участников. ' : '') + invitationOutcomeText(organizationId, items);
    try {
      await loadAdminOrganizations({ isCurrent });
      if (isCurrent()) setStatus(outcome, unresolved || items.some((item) => item.status === 'error')
        ? 'error' : items.some((item) => item.status === 'queued') ? 'muted' : 'success');
    } catch (_refreshError) {
      if (isCurrent()) renderAdminOrganizations();
      if (isCurrent()) setStatus(outcome + (items.some(item => invitationFacts(item).outcome === 'accepted')
        ? ' Письмо принято сервисом. Список участников пока не обновлён.' : ' Не удалось обновить список; показанные данные могут быть устаревшими.'),
        unresolved ? 'error' : 'muted');
    }
  };
  try {
    invitationRequestsInFlight.add(inFlightKey);
    if (isCurrent() && !existing) {
      emails.forEach(email => invitationResults.set(invitationResultKey(organizationId, assessment, email),
        { email, status: 'in_flight', operation_id: operationId }));
      renderAdminOrganizations();
      setStatus('Отправляем приглашение', 'loading');
    }
    if (existing) {
      try {
        const items = exactItems(await readback());
        if (!items) throw new Error('INVITATION_READBACK_INCOMPLETE');
        await showItems(items);
        return;
      } catch (error) {
        if (error?.status !== 404) throw error;
        if (readOnly) {
          if (isCurrent()) setStatus('Результат этой попытки пока не найден', 'error');
          return;
        }
        // A repeated send reuses the same identity when no receipt exists yet.
      }
    }
    if (!isCurrent()) return;
    readingPrevious = false;
    const response = await fetch('/users/admin/organizations/' + organizationId + '/personal-invitations', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operationId },
      body: JSON.stringify({ emails, assignment_ref: assessment, operation_id: operationId }),
    });
    const items = exactItems(await readApiResponse(response, 'Не удалось отправить приглашение.'));
    if (!items) throw new Error('INVITATION_RESPONSE_INCOMPLETE');
    await showItems(items);
  } catch (error) {
    const unknown = readingPrevious || error?.name === 'RequestDeadlineError' || error instanceof TypeError ||
      (error?.status >= 500 && error?.code !== 'EMAIL_PROVIDER_NOT_CONFIGURED') || !error?.status ||
      ['Failed to fetch', 'INVITATION_RESPONSE_INCOMPLETE',
        'INVITATION_READBACK_INCOMPLETE'].includes(error?.message);
    if (unknown) {
      try {
        const items = exactItems(await readback());
        if (!items) throw new Error('INVITATION_READBACK_INCOMPLETE');
        await showItems(items);
      } catch (_readbackError) {
        if (isCurrent()) {
          const items = emails.map(email => confirmedItems.find(item => item.email === email) ||
            { email, status: 'uncertain', operation_id: operationId,
              reason_code: _readbackError?.status === 404 ? 'operation_not_found' : 'delivery_unknown' });
          items.forEach(item => invitationResults.set(invitationResultKey(organizationId, assessment, item.email), item));
          renderAdminOrganizations();
          const message = error?.message === 'INVITATION_RESPONSE_INCOMPLETE'
            ? 'Сервер вернул неполный или противоречивый результат приглашения. Исход отправки пока неизвестен. Проверьте состояние операции перед повтором.'
            : 'Исход отправки пока неизвестен. Проверьте ту же операцию перед новой отправкой.';
          setStatus(message + ' ' + invitationOutcomeText(organizationId, items), 'error');
        }
      }
    } else {
      clearPendingInvitationOperation(requestKey, identityKey);
      if (isCurrent()) {
        const reason_code = error?.code === 'EMAIL_PROVIDER_NOT_CONFIGURED' ? 'mail_not_configured' :
          error?.code === 'INVITATION_OPERATION_MISMATCH' ? 'operation_mismatch' :
          error?.status === 401 ? 'session_expired' : error?.status === 403 ? 'permission_denied' :
          [400, 422].includes(error?.status) ? 'invalid_request' : 'failed_unclassified';
        const items = emails.map(email => ({ email, status: 'error', reason_code }));
        items.forEach(item => invitationResults.set(invitationResultKey(organizationId, assessment, item.email), item));
        renderAdminOrganizations();
        setStatus(invitationSummary(items), 'error');
      }
    }
  } finally {
    invitationRequestsInFlight.delete(inFlightKey);
    if (isCurrent()) renderAdminOrganizations();
  }
};

export const recoverAdminOrganizationInvitation = async (requestKey, options) => {
  const operation = pendingInvitationOperations().find((item) => item.requestKey === requestKey);
  if (!operation || Number(selectedOrganizationId) !== operation.organizationId) return;
  await sendAdminOrganizationMemberInvitation(operation.organizationId, operation.emails, operation.assignmentRef, options);
};

export const assignAdminOrganizationAssessment = async (organizationId, userIds, assignmentRef, roleProfileVersionId = null) => {
  const selected = [...new Set((userIds || []).map(Number).filter(Boolean))];
  const assessment = String(assignmentRef || '').trim();
  if (!requireOrganizationProgramScope(organizationId, assessment)) return false;
  if (!selected.length) {
    setStatus('Выберите хотя бы одного участника.', 'error');
    return false;
  }
  if (!assessment) {
    setStatus('Сначала выберите оценку в разделе «Данные организации».', 'error');
    offerAssessmentDataNavigation(organizationId, assessment);
    return false;
  }
  const requestKey = assessmentKey(organizationId, assessment);
  const operationKey = requestKey + ':' + selected.slice().sort((left, right) => left - right).join(',') +
    ':role:' + String(Number(roleProfileVersionId) || 'auto');
  const operationId = assignmentOperationIds.get(operationKey) || createOperationId();
  assignmentOperationIds.set(operationKey, operationId);
  if (assignmentSourceRequests.has(requestKey)) return false;
  const requestToken = Symbol('assignment');
  assignmentSourceRequests.set(requestKey, requestToken);
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const screen = state.currentScreen;
  const selectedOrganization = Number(selectedOrganizationId);
  const viewGeneration = assignmentViewGeneration;
  const programId = Number(organizationById(organizationId)?.assessment_program?.program_definition_id || 0);
  const isCurrent = () => state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey &&
    state.currentScreen === screen && Number(selectedOrganizationId) === selectedOrganization &&
    selectedOrganization === Number(organizationId) && assignmentViewGeneration === viewGeneration &&
    String(getSelectedAdminOrganizationAssessment(organizationId) || '').trim() === assessment &&
    Number(organizationById(organizationId)?.assessment_program?.program_definition_id || 0) === programId &&
    assignmentSourceRequests.get(requestKey) === requestToken;
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/assessment-assignments', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_ids: selected, assignment_ref: assessment, operation_id: operationId,
        ...(roleProfileVersionId ? { role_profile_version_id: Number(roleProfileVersionId) } : {}) }),
    });
    const result = await readApiResponse(response, 'Не удалось назначить оценку.');
    if (!isCurrent()) return false;
    const items = Array.isArray(result.items) ? result.items : [];
    const requestedIds = new Set(selected);
    const returnedIds = items.map((item) => Number(item.user_id));
    const uniqueReturnedIds = new Set(returnedIds);
    const responseMatchesRequest = items.length === selected.length &&
      uniqueReturnedIds.size === selected.length &&
      returnedIds.every((userId) => requestedIds.has(userId)) &&
      items.every((item) => ['assigned', 'already_assigned', 'not_assigned'].includes(item.status));
    if (!responseMatchesRequest) {
      setStatus('Сервер вернул неполный или противоречивый результат назначения. Обновите список перед безопасным повтором.', 'error');
      return false;
    }
    const failed = items.filter((item) => item.status === 'not_assigned');
    assignmentOperationIds.delete(operationKey);
    const outcome = items.map((item) => participantLabel(organizationId, item) + ': ' + ({ assigned: 'оценка назначена',
        already_assigned: 'эта оценка уже назначена', not_assigned: 'не назначена' })[item.status] +
        (item.error ? ' — ' + item.error : '')).join('. ') + '.';
    try {
      await loadAdminOrganizations({ isCurrent });
      if (!isCurrent()) return false;
      setStatus(outcome, failed.length ? 'error' : 'success');
    } catch (_refreshError) {
      if (!isCurrent()) return false;
      setStatus(outcome + ' Не удалось обновить список; показанные данные могут быть устаревшими. Используйте «Обновить».',
        failed.length ? 'error' : 'success');
    }
    return failed.length === 0;
  } catch (error) {
    if (!isCurrent()) return false;
    const isUnknown = error?.name === 'RequestDeadlineError' || error instanceof TypeError || error?.message === 'Failed to fetch';
    if (isUnknown) {
      try {
        const query = new URLSearchParams({ assignment_ref: assessment, user_ids: selected.join(','),
          ...(roleProfileVersionId ? { role_profile_version_id: String(roleProfileVersionId) } : {}) });
        const readbackUrl = '/users/admin/organizations/' + organizationId + '/assessment-assignments/operations/' +
          encodeURIComponent(operationId) + '?' + query.toString();
        for (let attempt = 0; attempt < 4; attempt += 1) {
          if (!isCurrent()) return false;
          let response;
          try {
            response = await fetch(readbackUrl, { credentials: 'same-origin' });
          } catch (readError) {
            if (!(readError instanceof TypeError) || attempt === 3) throw readError;
          }
          if (response && response.status !== 404) {
            const result = await readApiResponse(response, 'Итог назначения пока неизвестен.');
            if (!isCurrent()) return false;
            const items = Array.isArray(result.items) ? result.items : [];
            if (exactBatch(items, selected, (item) => Number(item?.user_id ?? item), ['assigned', 'already_assigned', 'not_assigned']) &&
              items.every((item) => item.status !== 'not_assigned')) {
              assignmentOperationIds.delete(operationKey);
              setStatus(items.map((item) => participantLabel(organizationId, item) +
                ': назначение подтверждено точным чтением операции').join('. ') + '.', 'success');
              return true;
            }
            break;
          }
          if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
        }
        setStatus('Итог назначения пока неизвестен. Обновите список и повторите проверку; новая операция не создаётся.', 'error');
      } catch (_readbackError) {
        if (!isCurrent()) return false;
        setStatus('Итог назначения пока неизвестен. Обновите список и повторите проверку; новая операция не создаётся.', 'error');
      }
    } else {
      const messages = {
        ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED: 'Проверьте и подтвердите сведения перед назначением.',
        PROGRAM_ROLE_SELECTION_REQUIRED: 'Выберите роль в оценке.',
        PROGRAM_ROLE_NOT_AVAILABLE: 'Выберите доступную роль в оценке.',
        PROGRAM_NOT_CONNECTED: 'Оценка пока недоступна для назначения. Обратитесь к суперадминистратору.',
        PROGRAM_NOT_AVAILABLE_FOR_NEW_ASSIGNMENTS: 'Эта программа сейчас недоступна для новых назначений. Обратитесь к суперадминистратору.',
        PROGRAM_ASSIGNMENT_REF_MISMATCH: 'Не удалось сопоставить сведения с доступной оценкой. Обновите данные.',
        PROGRAM_SOURCE_SELECTION_STALE: 'Сведения об оценке изменились. Обновите состояние и повторите выбор.',
        PROGRAM_CONFIGURATION_NOT_AVAILABLE: 'Настройка оценки не завершена. Обратитесь к суперадминистратору.',
        ASSIGNMENT_OPERATION_IDEMPOTENCY_CONFLICT: 'Операция уже относится к другому набору участников. Обновите список перед новой попыткой.',
      };
      const code = Object.keys(messages).find((item) => String(error?.message || '').includes(item));
      setStatus(code ? messages[code] : (error.message || 'Не удалось назначить оценку.'), 'error');
      offerAssessmentDataNavigation(organizationId, assessment);
    }
    return false;
  } finally {
    if (assignmentSourceRequests.get(requestKey) === requestToken) assignmentSourceRequests.delete(requestKey);
  }
};

export const cancelAdminOrganizationAssessment = async (organizationId, assignmentId, assessmentRefOverride = '') => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const selectedOrganization = Number(selectedOrganizationId);
  const assessmentRef = String(assessmentRefOverride || getSelectedAdminOrganizationAssessment(organizationId) || '').trim();
  const key = identityKey + ':' + Number(organizationId) + ':' + Number(assignmentId);
  const operationId = cancellationOperationIds.get(key) || createOperationId();
  cancellationOperationIds.set(key, operationId);
  if (cancellationRequestsInFlight.has(key)) return false;
  cancellationRequestsInFlight.add(key);
  setStatus('Выполняем действие…', 'loading');
  const contextIsCurrent = () => state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey &&
    Number(selectedOrganizationId) === selectedOrganization && selectedOrganization === Number(organizationId) &&
    String(getSelectedAdminOrganizationAssessment(organizationId) || '').trim() === assessmentRef;
  const restoreButton = () => {
    if (!contextIsCurrent()) return;
    const button = adminOrganizationsList.querySelector(
      '[data-organization-id="' + Number(organizationId) + '"] ' +
      '[data-action="cancel-member-assignment"][data-assignment-id="' + Number(assignmentId) + '"]',
    );
    if (button) button.disabled = false;
  };
  const refreshExactAssignment = async () => {
    const data = await requestOrganizations(
      '/users/admin/organizations',
      { method: 'GET', headers: {} },
      'Не удалось проверить состояние назначения.',
    );
    if (!data || !contextIsCurrent()) return null;
    const organization = (data.items || []).find((item) => Number(item.id) === Number(organizationId));
    if (!organization) return null;
    const stages = (organization.members || []).map((member) => member.assessment_stages?.[assessmentRef]).filter(Boolean);
    return stages.find((stage) => Number(stage.assignment_id) === Number(assignmentId)) || null;
  };
  try {
    const response = await fetch(
      '/users/admin/organizations/' + Number(organizationId) + '/assessment-assignments/' + Number(assignmentId) + '/cancel',
      {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operation_id: operationId }),
      },
    );
    const command = await readApiResponse(response, 'Не удалось отменить назначение оценки.');
    if (Number(command?.assignment_id || assignmentId) !== Number(assignmentId)) {
      throw new Error('Сервер вернул результат для другого назначения.');
    }
    if (!contextIsCurrent()) return false;
    try {
      const readback = await refreshExactAssignment();
      if (!contextIsCurrent()) return false;
      if (readback?.code === 'cancelled') {
        cancellationOperationIds.delete(key);
        setStatus('Назначение оценки отменено. Участник и его история сохранены.', 'success');
      } else {
        markOrganizationsReadStale('Команда отмены подтверждена, но точное состояние назначения не подтверждено чтением.');
        setStatus('Отмена подтверждена сервером, но список может быть устаревшим. Обновите состояние перед следующим действием.', 'muted');
      }
    } catch (error) {
      if (!contextIsCurrent()) return false;
      markOrganizationsReadStale(error.message || 'Не удалось обновить список после отмены.');
      setStatus('Назначение отменено, но обновить список не удалось. Последние показанные данные устарели.', 'muted');
    }
    return true;
  } catch (error) {
    if (!contextIsCurrent()) return false;
    if (Number(error?.status) === 409) {
      try {
        await refreshExactAssignment();
      } catch (refreshError) {
        if (contextIsCurrent()) markOrganizationsReadStale(refreshError.message || 'Не удалось обновить назначение после конфликта.');
      }
      if (contextIsCurrent()) setStatus('Назначение уже изменилось и больше не может быть отменено. Показано актуальное состояние.', 'error');
    } else if (error?.name === 'RequestDeadlineError' || error instanceof TypeError) {
      try {
        const readback = await refreshExactAssignment();
        if (!contextIsCurrent()) return false;
        if (readback?.code === 'cancelled') {
          cancellationOperationIds.delete(key);
          setStatus('Отмена подтверждена чтением после потери ответа команды.', 'success');
          return true;
        }
        markOrganizationsReadStale('Ответ команды потерян, а чтение не подтвердило её итог.');
        setStatus('Итог отмены пока неизвестен. Не создавайте новую отмену; обновите состояние или повторите с тем же ключом.', 'error');
      } catch (refreshError) {
        if (contextIsCurrent()) {
          markOrganizationsReadStale(refreshError.message || 'Не удалось выяснить итог отмены.');
          setStatus('Итог отмены неизвестен. Повтор использует тот же operation_id.', 'error');
        }
      }
    } else {
      setStatus(error.message || 'Не удалось отменить назначение оценки.', 'error');
    }
    return false;
  } finally {
    cancellationRequestsInFlight.delete(key);
    restoreButton();
  }
};

const offerAssessmentDataNavigation = (organizationId, assessmentRef) => {
  const target = operationRoot()?.querySelector('[data-operation-status]') || adminOrganizationsStatus;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'text-button';
  button.textContent = assessmentRef ? 'Открыть данные выбранной оценки' : 'Выбрать программу и подготовить сведения';
  button.onclick = () => {
    if (assessmentRef) selectedAssessmentRefs.set(organizationKey(organizationId), assessmentRef);
    selectAdminOrganizationView(organizationId, 'organization-data');
  };
  target?.append(button);
};

export const revokeAdminOrganizationMemberInvitation = async (organizationId, invitationId) => {
  setStatus('Выполняем действие…', 'loading');
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/personal-invitations/' + invitationId, {
      method: 'DELETE',
      credentials: 'same-origin',
    });
    await readApiResponse(response, 'Не удалось отозвать приглашение.');
    await loadAdminOrganizations();
    setStatus('Приглашение отозвано.', 'success');
  } catch (error) {
    const message = invitationRevokeErrorMessage(error);
    try {
      await loadAdminOrganizations();
    } catch (_refreshError) {
      // Preserve the command result even when the follow-up read is unavailable.
    }
    setStatus(message, 'error');
  }
};

export const prepareAdminOrganizationMemberAssessment = async (organizationId, userId) => {
  try {
    const response = await fetch(
      '/users/admin/organizations/' + organizationId + '/members/' + userId + '/prepare-assessment',
      { method: 'POST', credentials: 'same-origin' },
    );
    const job = await readApiResponse(response, 'Не удалось запустить предварительную подготовку кейсов.');
    setStatus('Предварительная подготовка кейсов запущена.', 'success');
    await loadAdminOrganizations();
    const operationId = String(job.operation_id || '');
    if (!operationId) return;
    for (let attempt = 0; attempt < 120; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      const statusResponse = await fetch('/users/assessment/preparation/' + encodeURIComponent(operationId), {
        credentials: 'same-origin',
      });
      const status = await readApiResponse(statusResponse, 'Не удалось получить статус подготовки кейсов.');
      if (status.status === 'completed') {
        await loadAdminOrganizations();
        setStatus('Кейсы для пользователя подготовлены заранее.', 'success');
        return;
      }
      if (status.status === 'failed') {
        await loadAdminOrganizations();
        setStatus(status.error_message || 'Предварительная подготовка кейсов завершилась ошибкой.', 'error');
        return;
      }
    }
    setStatus('Подготовка продолжается в фоне. Статус обновится при следующем открытии раздела.', 'muted');
  } catch (error) {
    setStatus(error.message || 'Не удалось подготовить кейсы.', 'error');
  }
};

const renderOrganizationBatchProgress = (organizationId) => {
  const batch = state.adminOrganizationPreparationBatches?.[organizationId];
  if (!batch || batch.status !== 'in_progress') {
    return '';
  }
  const current = batch.current_participant;
  const currentLabel = current
    ? (current.full_name || current.email) +
      (current.progress_title ? ' · ' + current.progress_title : '') +
      (current.progress_message ? ' · ' + current.progress_message : '')
    : 'Ожидание запуска';
  const percent = batch.total_participants
    ? Math.round((Number(batch.processed_participants || 0) / Number(batch.total_participants)) * 100)
    : 100;
  return (
    '<div class="admin-organization-batch-progress">' +
    '<div class="admin-organization-batch-progress-head"><strong>Массовая подготовка кейсов</strong><span>' +
    Number(batch.processed_participants || 0) +
    ' из ' +
    Number(batch.total_participants || 0) +
    '</span></div>' +
    '<div class="admin-organization-batch-progress-track"><span style="width:' +
    percent +
    '%"></span></div>' +
    '<p>' +
    escapeHtml(currentLabel) +
    '</p><small>Осталось: ' +
    Number(batch.remaining_participants || 0) +
    ' · Готово: ' +
    Number(batch.completed_participants || 0) +
    ' · Ошибки: ' +
    Number(batch.failed_participants || 0) +
    ' · Пропущено: ' +
    Number(batch.skipped_participants || 0) +
    '</small></div>'
  );
};

const activeBatchPolls = new Set();

const pollOrganizationPreparationBatch = async (organizationId, batchId) => {
  if (activeBatchPolls.has(batchId)) return;
  activeBatchPolls.add(batchId);
  try {
  for (let attempt = 0; attempt < 1800; attempt += 1) {
    const response = await fetch(
      '/users/admin/organizations/' + organizationId + '/prepare-assessments/' + encodeURIComponent(batchId),
      { credentials: 'same-origin' },
    );
    const batch = await readApiResponse(response, 'Не удалось получить прогресс массовой подготовки.');
    state.adminOrganizationPreparationBatches = {
      ...(state.adminOrganizationPreparationBatches || {}),
      [organizationId]: batch,
    };
    renderAdminOrganizations();
    if (batch.status === 'completed' || batch.status === 'failed') {
      const nextBatches = { ...(state.adminOrganizationPreparationBatches || {}) };
      delete nextBatches[organizationId];
      state.adminOrganizationPreparationBatches = nextBatches;
      await loadAdminOrganizations();
      setStatus(
        batch.failed_participants
          ? 'Массовая подготовка завершена. Есть участники с ошибками.'
          : 'Кейсы для участников организации подготовлены.',
        batch.failed_participants ? 'error' : 'success',
      );
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 2000));
  }
  } finally {
    activeBatchPolls.delete(batchId);
  }
};

export const prepareAdminOrganizationAssessments = async (organizationId) => {
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/prepare-assessments', {
      method: 'POST',
      credentials: 'same-origin',
    });
    const batch = await readApiResponse(response, 'Не удалось запустить массовую подготовку кейсов.');
    state.adminOrganizationPreparationBatches = {
      ...(state.adminOrganizationPreparationBatches || {}),
      [organizationId]: {
        ...batch,
        status: 'in_progress',
        processed_participants: Number(batch.completed_participants || 0) + Number(batch.skipped_participants || 0),
        remaining_participants:
          Number(batch.total_participants || 0) -
          Number(batch.completed_participants || 0) -
          Number(batch.skipped_participants || 0),
        failed_participants: 0,
        current_participant: null,
      },
    };
    renderAdminOrganizations();
    setStatus('Массовая подготовка кейсов запущена.', 'success');
    void pollOrganizationPreparationBatch(organizationId, batch.batch_id).catch((error) => {
      setStatus(error.message || 'Не удалось обновить прогресс массовой подготовки.', 'error');
    });
  } catch (error) {
    setStatus(error.message || 'Не удалось запустить массовую подготовку кейсов.', 'error');
  }
};

export const importAdminOrganizationMembers = async (organizationId, csvText) => {
  const text = String(csvText || '').trim();
  if (!text) {
    setStatus('Выберите CSV-файл с участниками.', 'error');
    return;
  }
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  try {
    const result = await requestOrganizationsImport('/users/admin/organizations/' + organizationId + '/members/import', text);
    if (!result || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
    const errorsText = Array.isArray(result.errors) && result.errors.length ? ' Ошибки: ' + result.errors.slice(0, 3).join('; ') : '';
    setStatus('Импортировано: ' + Number(result.imported_count || 0) + '. Пропущено: ' + Number(result.skipped_count || 0) + '.' + errorsText, result.skipped_count ? 'error' : 'success');
    return result;
  } catch (error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
    setStatus(error.message || 'Не удалось импортировать участников.', 'error');
    return null;
  }
};

export const previewAdminOrganizationQuestionnaire = async (organizationId, payload) => {
  if (!requireOrganizationProgramScope(organizationId, payload?.assignment_ref) ||
      questionnaireLoadStates.get(organizationKey(organizationId))?.accessDenied) return false;
  const earlyData = payload.channel === 'product_form';
  const action = earlyData ? 'preview-early-data' : 'preview-questionnaire';
  const submittedRef = String(payload.assignment_ref).trim();
  const scopeKey = assessmentKey(organizationId, submittedRef);
  const viewGeneration = assignmentViewGeneration;
  let attempt;
  if (earlyData) {
    if (confirmationNeedsReadback(questionnaireConfirmOutcomes.get(scopeKey)) ||
        questionnaireConfirmRequestsInFlight.has(scopeKey)) return;
    const previous = earlyDataPreviewAttempts.get(scopeKey);
    if (previous?.inFlight) return;
    const answers = JSON.stringify(payload.answers);
    attempt = { answers, idempotencyKey: previous?.answers === answers ? previous.idempotencyKey : createOperationId(), inFlight: true };
    earlyDataPreviewAttempts.set(scopeKey, attempt);
    updateOrganizationDataForm(organizationDataForm(organizationId));
    setOrganizationDataStatus(organizationId, submittedRef, '', 'muted');
  }
  const submittedForm = adminOrganizationsList.querySelector(
    '[data-organization-id="' + Number(organizationId) + '"] form[data-action="' + action + '"]',
  );
  const submittedSignature = questionnaireInputSignature(organizationId, action);
  captureAdminOrganizationsDraft();
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const requestGeneration = (questionnairePreviewRequestGenerations.get(scopeKey) || 0) + 1;
  questionnairePreviewRequestGenerations.set(scopeKey, requestGeneration);
  const isCurrent = () => state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey &&
    questionnairePreviewRequestGenerations.get(scopeKey) === requestGeneration;
  let storageKey;
  try {
    if (attempt) {
      storageKey = await previewOperationStorageKey(scopeKey, payload);
      if (!isCurrent() || questionnaireLoadStates.get(organizationKey(organizationId))?.accessDenied ||
          !requireOrganizationProgramScope(organizationId, submittedRef)) return;
      const storedKey = storageKey && readQuestionnaireOperation(storageKey);
      attempt.idempotencyKey = storedKey || attempt.idempotencyKey;
      writeQuestionnaireOperation(storageKey, attempt.idempotencyKey);
      payload = { ...payload, idempotency_key: attempt.idempotencyKey };
    }
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/preview', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const preview = await readApiResponse(response, 'Не удалось распознать анкету.');
    if (!isCurrent() || questionnaireLoadStates.get(organizationKey(organizationId))?.accessDenied) return;
    if (!(Number(preview?.id) > 0) || preview.assignment_ref !== submittedRef) {
      throw new Error('Не удалось проверить ответ сервера по этой редакции.');
    }
    if (attempt && earlyDataPreviewAttempts.get(scopeKey) === attempt) {
      earlyDataPreviewAttempts.delete(scopeKey);
      writeQuestionnaireOperation(storageKey, null);
    }
    const connection = organizationProgramState(organizationId);
    if (connection.status !== 'confirmed' || connection.assessmentRef !== submittedRef) return;
    const currentForm = adminOrganizationsList.querySelector(
      '[data-organization-id="' + Number(organizationId) + '"] form[data-action="' + action + '"]',
    );
    const draftKey = organizationKey(organizationId) + ':' + action + ':' + String(payload?.assignment_ref || '').trim();
    const inputChanged = questionnaireInputSignature(organizationId, action) !== submittedSignature;
    if (currentForm && inputChanged) captureFormDraft(organizationId, currentForm);
    else if (!managementDrafts.has(draftKey) && submittedForm) captureFormDraft(organizationId, submittedForm);
    questionnairePreviews.set(scopeKey, preview);
    if (payload?.channel === 'csv') organizationViews.set(Number(organizationId), 'organization-data');
    if (inputChanged) staleQuestionnairePreviews.add(scopeKey);
    else staleQuestionnairePreviews.delete(scopeKey);
    renderAdminOrganizations();
    const ready = preview.status === 'ready_for_confirmation';
    if (earlyData) {
      const proposedName = preview.participant_preview?.organization_name || payload.answers.C01?.name;
      const expectedName = preview.expected_organization_name ?? organizationById(organizationId)?.name;
      const renamesOrganization = proposedName && proposedName !== expectedName;
      if (ready && !inputChanged && !renamesOrganization && viewGeneration === assignmentViewGeneration &&
          organizationDataIsVisible(organizationId, submittedRef)) {
        await confirmAdminOrganizationQuestionnaire(organizationId, Number(preview.id), submittedRef);
      } else if (ready && !inputChanged && organizationDataIsVisible(organizationId, submittedRef)) {
        organizationDataForm(organizationId)?.querySelector('[data-action="confirm-questionnaire"]')?.focus();
      }
      return;
    }
    setStatus(inputChanged ? 'Данные изменились во время предпросмотра. Обновите предпросмотр перед подтверждением.' :
      ready ? 'Анкета загружена. Проверьте сведения, изменения и источник перед подтверждением.' :
        'Черновик сохранён. Исправьте перечисленные ошибки или заполните обязательные поля.',
    !inputChanged && ready ? 'success' : 'error');
  } catch (error) {
    if (!isCurrent()) return;
    if (attempt && error?.status && error.status < 500) {
      earlyDataPreviewAttempts.delete(scopeKey);
      writeQuestionnaireOperation(storageKey, null);
    }
    const message = error instanceof TypeError || error?.name === 'RequestDeadlineError'
      ? 'Не удалось получить ответ. Повторите проверку сведений.'
      : questionnaireErrorMessage(error, 'Не удалось проверить сведения.');
    if (earlyData) setOrganizationDataStatus(organizationId, submittedRef, message, 'error');
    else if (getSelectedAdminOrganizationAssessment(organizationId) === submittedRef) setStatus(message, 'error');
  } finally {
    if (attempt && earlyDataPreviewAttempts.get(scopeKey) === attempt) attempt.inFlight = false;
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey) {
      updateOrganizationDataForm(organizationDataForm(organizationId));
    }
  }
};

export const confirmAdminOrganizationQuestionnaire = async (organizationId, revisionId, assessmentRef) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const card = adminOrganizationsList.querySelector('[data-organization-id="' + Number(organizationId) + '"]');
  const confirmButton = card?.querySelector('[data-action="confirm-questionnaire"][data-value="' + Number(revisionId) + '"]');
  const submittedRef = assessmentRef || confirmButton?.closest('.admin-questionnaire-preview')?.dataset.assessmentRef || '';
  if (!requireOrganizationProgramScope(organizationId, submittedRef) ||
      questionnaireLoadStates.get(organizationKey(organizationId))?.accessDenied) return false;
  const preview = questionnairePreviews.get(assessmentKey(organizationId, submittedRef));
  if (Number(preview?.id) !== Number(revisionId) || preview?.status !== 'ready_for_confirmation' ||
      staleQuestionnairePreviews.has(assessmentKey(organizationId, submittedRef))) {
    setStatus('Обновите предпросмотр перед подтверждением сведений.', 'error');
    return false;
  }
  const submittedForms = new Map([...card?.querySelectorAll(
    'form[data-action="preview-early-data"], form[data-action="preview-questionnaire"]',
  ) || []].map((form) => [String(form.dataset.action), { form, signature: formSignature(form) }]));
  captureAdminOrganizationsDraft();
  const requestKey = assessmentKey(organizationId, submittedRef);
  const priorOutcome = questionnaireConfirmOutcomes.get(requestKey);
  if (questionnaireConfirmRequestsInFlight.has(requestKey) || confirmationNeedsReadback(priorOutcome)) return;
  questionnaireConfirmRequestsInFlight.add(requestKey);
  updateOrganizationDataForm(organizationDataForm(organizationId));
  if (confirmButton) {
    confirmButton.disabled = true;
    confirmButton.textContent = 'Подтверждаем…';
  }
  const requestGeneration = (questionnaireConfirmRequestGenerations.get(requestKey) || 0) + 1;
  questionnaireConfirmRequestGenerations.set(requestKey, requestGeneration);
  const storageKey = confirmationStorageKey(requestKey);
  writeQuestionnaireOperation(storageKey, revisionId);
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/' + revisionId + '/confirm', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const confirmed = await readApiResponse(response, 'Не удалось подтвердить анкету.');
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    const confirmedRef = String(confirmed?.assignment_ref || '').trim();
    const confirmedKey = assessmentKey(organizationId, confirmedRef);
    if (questionnaireConfirmRequestGenerations.get(requestKey) !== requestGeneration) return;
    if (Number(confirmed?.id) !== Number(revisionId) || confirmed.status !== 'confirmed' || confirmedRef !== submittedRef) {
      throw new Error('Не удалось проверить ответ подтверждения.');
    }
    writeQuestionnaireOperation(storageKey, null);
    const changedActions = new Set();
    const currentCard = adminOrganizationsList.querySelector(
      '[data-organization-id="' + Number(organizationId) + '"]',
    );
    submittedForms.forEach(({ signature }, action) => {
      const form = currentCard?.querySelector('form[data-action="' + action + '"]');
      if (!form || formSignature(form) === signature) return;
      changedActions.add(action);
      captureFormDraft(organizationId, form);
    });
    const revisionsKey = organizationKey(organizationId);
    const revisions = questionnaireRevisions.get(revisionsKey) || [];
    const cachedRevision = revisions.find((item) => String(item.assignment_ref || '').trim() === confirmedRef);
    const currentRevision = cachedRevision;
    if (currentRevision && isQuestionnaireRevisionNewer(currentRevision, confirmed)) {
      questionnaireRevisions.set(revisionsKey, [mergeQuestionnaireRevision(confirmed, currentRevision),
        ...revisions.filter((item) => String(item.assignment_ref || '').trim() !== confirmedRef)]);
      renderAdminOrganizations();
      setOrganizationDataStatus(organizationId, submittedRef,
        'Сведения сохранены. Показана более новая серверная редакция.', 'muted');
      return;
    }
    questionnaireRevisions.set(revisionsKey,
      [mergeQuestionnaireRevision(confirmed, cachedRevision),
        ...revisions.filter((item) => String(item.assignment_ref || '').trim() !== confirmedRef)]);
    reflectConfirmedOrganizationName(organizationId, confirmed, { allowAnswerFallback: true });
    const currentPreview = questionnairePreviews.get(confirmedKey);
    if (!currentPreview || Number(currentPreview.id) === Number(revisionId)) {
      questionnairePreviews.delete(confirmedKey);
      staleQuestionnairePreviews.delete(confirmedKey);
    }
    for (const action of ['preview-early-data', 'preview-questionnaire']) {
      if (!changedActions.has(action) && (!currentPreview || Number(currentPreview.id) === Number(revisionId))) {
        managementDrafts.delete(organizationKey(organizationId) + ':' + action + ':' + confirmedRef);
      }
    }
    const outcome = { status: 'confirmed', revisionId, assignmentRef: submittedRef };
    questionnaireConfirmOutcomes.set(requestKey, outcome);
    questionnaireConfirmRequestsInFlight.delete(requestKey);
    renderAdminOrganizations();
    setOrganizationDataStatus(organizationId, submittedRef, '', 'muted');
    focusOrganizationDataAction(organizationId, submittedRef);
    void refreshConfirmedReadiness(organizationId, outcome, { identityEpoch, identityKey, requestKey, requestGeneration });
  } catch (error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    if (questionnaireConfirmRequestGenerations.get(requestKey) !== requestGeneration) return;
    const status = !error?.status || error.status >= 500 ? 'unknown' :
      error.status === 409 ? 'conflict' : 'rejected';
    if (status !== 'unknown') writeQuestionnaireOperation(storageKey, null);
    const message = status === 'unknown'
      ? 'Ответ сервера не получен. Проверьте, сохранилась ли эта редакция.'
      : questionnaireErrorMessage(error, 'Не удалось подтвердить сведения.');
    questionnaireConfirmOutcomes.set(requestKey, { status, revisionId, assignmentRef: submittedRef, message });
    captureAdminOrganizationsDraft();
    renderAdminOrganizations();
  } finally {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey &&
      questionnaireConfirmRequestGenerations.get(requestKey) === requestGeneration) {
      questionnaireConfirmRequestsInFlight.delete(requestKey);
      const currentButton = adminOrganizationsList.querySelector(
        '[data-organization-id="' + Number(organizationId) + '"] [data-action="confirm-questionnaire"][data-value="' + Number(revisionId) + '"]',
      );
      if (currentButton) {
        currentButton.textContent = 'Подтвердить сведения';
      }
      updateOrganizationDataForm(organizationDataForm(organizationId));
      focusOrganizationDataAction(organizationId, submittedRef);
    }
  }
};

const refreshConfirmedReadiness = async (organizationId, outcome, context) => {
  const isCurrent = () => state.identityEpoch === context.identityEpoch && currentIdentityKey() === context.identityKey &&
    questionnaireConfirmRequestGenerations.get(context.requestKey) === context.requestGeneration;
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire', { credentials: 'same-origin' });
    const result = await readApiResponse(response, 'Не удалось обновить готовность.');
    if (!isCurrent()) return;
    if (!Array.isArray(result.items)) throw new Error('Не удалось обновить готовность.');
    const refreshed = result.items.find((item) => item.assignment_ref === outcome.assignmentRef);
    if (Number(refreshed?.effective_confirmed?.id || 0) < Number(outcome.revisionId) || !refreshed?.readiness) {
      throw new Error('Готовность подтверждённой редакции ещё недоступна.');
    }
    const key = organizationKey(organizationId);
    const cached = questionnaireRevisions.get(key) || [];
    const merged = new Map(cached.map((item) => [item.assignment_ref, item]));
    for (const item of result.items) {
      const prior = merged.get(item.assignment_ref);
      merged.set(item.assignment_ref, mergeQuestionnaireRevision(item, prior));
    }
    captureAdminOrganizationsDraft();
    questionnaireRevisions.set(key, [...merged.values()]);
    questionnaireConfirmOutcomes.delete(context.requestKey);
    renderAdminOrganizations();
    if (Number(refreshed.id) > Number(outcome.revisionId)) {
      setOrganizationDataStatus(organizationId, outcome.assignmentRef,
        'Сведения сохранены. Показана более новая серверная редакция.', 'muted');
    }
  } catch {
    if (!isCurrent()) return;
    outcome.status = 'refresh_failed';
    captureAdminOrganizationsDraft();
    renderAdminOrganizations();
  }
};

export const checkAdminOrganizationConfirmation = async (organizationId, revisionId) => {
  const connection = organizationProgramState(organizationId);
  if (connection.status !== 'confirmed' || questionnaireLoadStates.get(organizationKey(organizationId))?.accessDenied) return;
  const requestKey = assessmentKey(organizationId, connection.assessmentRef);
  const outcome = questionnaireConfirmOutcomes.get(requestKey);
  if (outcome?.revisionId !== revisionId || questionnaireConfirmRequestsInFlight.has(requestKey)) return;
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const requestGeneration = questionnaireConfirmRequestGenerations.get(requestKey);
  questionnaireConfirmRequestsInFlight.add(requestKey);
  updateOrganizationDataForm(organizationDataForm(organizationId));
  setOrganizationDataStatus(organizationId, outcome.assignmentRef, 'Проверяем сохранённую редакцию…', 'loading');
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/' + revisionId, { credentials: 'same-origin' });
    const saved = await readApiResponse(response, 'Не удалось проверить подтверждение.');
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
      questionnaireConfirmOutcomes.get(requestKey) !== outcome) return;
    if (Number(saved.id) !== revisionId || saved.assignment_ref !== outcome.assignmentRef ||
        !['confirmed', 'ready_for_confirmation', 'draft', 'invalid'].includes(saved.status)) {
      throw new Error('Не удалось проверить состояние этой редакции.');
    }
    writeQuestionnaireOperation(confirmationStorageKey(requestKey), null);
    captureAdminOrganizationsDraft();
    reflectConfirmedOrganizationName(organizationId, saved);
    if (saved.status !== 'confirmed') {
      if (outcome.status === 'conflict') {
        await loadQuestionnaireRevisions(organizationId, { render: false });
        if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
        captureAdminOrganizationsDraft();
      }
      questionnaireConfirmOutcomes.delete(requestKey);
      if (outcome.status === 'conflict' || saved.status !== 'ready_for_confirmation') {
        staleQuestionnairePreviews.add(requestKey);
      } else if (outcome.restored && !managementDrafts.has(organizationKey(organizationId) + ':preview-early-data:' + outcome.assignmentRef)) {
        const latest = questionnaireRevisions.get(organizationKey(organizationId))
          ?.find((revision) => revision.assignment_ref === saved.assignment_ref);
        if (!isQuestionnaireRevisionNewer(latest, saved)) questionnairePreviews.set(requestKey, saved);
      }
      renderAdminOrganizations();
      setOrganizationDataStatus(organizationId, outcome.assignmentRef,
        outcome.status === 'conflict' ? 'Редакция не сохранена. Сверьте текущие сведения и подтвердите черновик заново.' :
          'Редакция пока не подтверждена. Можно повторить подтверждение.', 'muted');
      return;
    }
    const revisionsKey = organizationKey(organizationId);
    const revisions = questionnaireRevisions.get(revisionsKey) || [];
    const latest = revisions.find((item) => item.assignment_ref === saved.assignment_ref);
    questionnaireRevisions.set(revisionsKey, [mergeQuestionnaireRevision(saved, latest),
      ...revisions.filter((item) => item.assignment_ref !== saved.assignment_ref)]);
    const preview = questionnairePreviews.get(requestKey);
    if (Number(preview?.id) === Number(revisionId)) {
      questionnairePreviews.delete(requestKey);
      staleQuestionnairePreviews.delete(requestKey);
    }
    outcome.status = 'confirmed';
    renderAdminOrganizations();
    setOrganizationDataStatus(organizationId, outcome.assignmentRef, '', 'muted');
    void refreshConfirmedReadiness(organizationId, outcome, { identityEpoch, identityKey, requestKey, requestGeneration });
  } catch (error) {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey) {
      setOrganizationDataStatus(organizationId, outcome.assignmentRef, 'Не удалось проверить результат. Повторите проверку.', 'error');
    }
  } finally {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey) {
      questionnaireConfirmRequestsInFlight.delete(requestKey);
      updateOrganizationDataForm(organizationDataForm(organizationId));
      focusOrganizationDataAction(organizationId, outcome.assignmentRef);
    }
  }
};

export const deleteOrDeactivateAdminOrganization = async (organizationId, organizationName = '') => {
  const previousItems = Array.isArray(state.adminOrganizations?.items) ? state.adminOrganizations.items : [];
  const previousOrg = previousItems.find((item) => Number(item.id) === Number(organizationId));
  const label = String(organizationName || previousOrg?.name || 'Организация').trim();
  try {
    const data = await requestOrganizations(
      '/users/admin/organizations/' + organizationId,
      { method: 'DELETE', headers: {} },
      'Не удалось удалить или деактивировать организацию.',
    );
    const nextItems = Array.isArray(data?.items) ? data.items : [];
    const nextOrg = nextItems.find((item) => Number(item.id) === Number(organizationId));
    if (!nextOrg) {
      setStatus('Организация «' + label + '» удалена.', 'success');
      return;
    }
    if (nextOrg.is_active === false) {
      setStatus('Организация «' + label + '» деактивирована.', 'success');
      return;
    }
    setStatus('Организация «' + label + '» обновлена.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось удалить или деактивировать организацию «' + label + '».', 'error');
  }
};

export const restoreAdminOrganization = async (organizationId, organizationName = '') => {
  const label = String(organizationName || 'Организация').trim();
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/restore',
      { method: 'POST', headers: {} },
      'Не удалось восстановить организацию.',
    );
    setStatus('Организация «' + label + '» восстановлена.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось восстановить организацию «' + label + '».', 'error');
  }
};

const readAdminOrganizationProgram = async (organizationId, identityEpoch, identityKey) => {
  const readGeneration = organizationsRequestGeneration;
  const response = await fetch('/users/admin/organizations/' + organizationId + '/assessment-program', {
    method: 'GET', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
  });
  const result = await readApiResponse(response, 'Не удалось проверить подключённую версию программы.');
  if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  if (readGeneration !== organizationsRequestGeneration) {
    throw new Error('Состояние организации изменилось во время проверки. Проверьте подключение повторно.');
  }
  if (!result || !Object.hasOwn(result, 'connection') ||
      (result.connection !== null && (Number(result.connection?.organization_id) !== Number(organizationId) ||
        !Number(result.connection?.program_definition_id) || !String(result.connection?.assignment_ref || '').trim()))) {
    throw new Error('Не удалось подтвердить состояние подключения программы.');
  }
  return result.connection;
};

const applyAdminOrganizationProgramReadback = (organizationId, connection) => {
  const organizations = state.adminOrganizations;
  if (!organizations || !Array.isArray(organizations.items)) return;
  const organization = organizations.items.find((item) => Number(item.id) === Number(organizationId));
  if (!organization) return;
  captureAdminOrganizationsDraft();
  // An older collection GET must not replace this later exact readback.
  organizationsRequestGeneration += 1;
  organization.assessment_program = connection;
  persistAssessmentContext();
  renderAdminOrganizations();
};

const refreshAdminOrganizationQuestionnaireInBackground = (organizationId, identityEpoch, identityKey) => {
  void loadQuestionnaireRevisions(organizationId, { identityEpoch, identityKey, render: false });
};

const isExactProgramConnection = (connection, organizationId, programDefinitionId) =>
  Number(connection?.organization_id) === Number(organizationId) &&
  Number(connection?.program_definition_id) === Number(programDefinitionId) &&
  Boolean(String(connection?.assignment_ref || '').trim());

export const checkAdminOrganizationProgram = async (organizationId) => {
  const key = organizationKey(organizationId);
  if (programConnectionRequestsInFlight.has(key)) return false;
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  captureAdminOrganizationsDraft();
  programConnectionRequestsInFlight.add(key);
  unverifiedProgramConnections.add(key);
  renderAdminOrganizations();
  try {
    if (organizationsReadStale && !await refreshAdminOrganizationsSafely()) return false;
    const connection = await readAdminOrganizationProgram(organizationId, identityEpoch, identityKey);
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return false;
    unverifiedProgramConnections.delete(key);
    applyAdminOrganizationProgramReadback(organizationId, connection);
    setStatus(connection ? 'Состояние подключения программы подтверждено.' : organizationProgramState(organizationId).message,
      connection ? 'success' : 'muted');
    refreshAdminOrganizationQuestionnaireInBackground(organizationId, identityEpoch, identityKey);
    return true;
  } catch (_error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return false;
    captureAdminOrganizationsDraft();
    renderAdminOrganizations();
    setStatus(organizationProgramState(organizationId).message, 'error');
    return false;
  } finally {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey) programConnectionRequestsInFlight.delete(key);
  }
};

const programConnectionStateMarkup = (organizationId, connection) =>
  '<p data-program-connection-state>' + (unverifiedProgramConnections.has(organizationKey(organizationId))
    ? 'Результат подключения пока не подтверждён. После завершения проверки можно безопасно повторить запрос подключения.'
    : connection ? 'Подключено: <strong>' + escapeHtml(connection.program_name) + ' · ' +
      escapeHtml(connection.program_version) + '</strong>' : 'Программа ещё не подключена.') + '</p>';

export const connectAdminOrganizationProgram = async (organizationId, programDefinitionId) => {
  const connectionKey = organizationKey(organizationId);
  if (programConnectionRequestsInFlight.has(connectionKey)) return false;
  programConnectionRequestsInFlight.add(connectionKey);
  organizationsRequestGeneration += 1;
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  clearProgramConnectionFeedback();
  const feedbackGeneration = programConnectionFeedbackGeneration;
  const setOutcome = (message, tone) => {
    const form = programConnectionForm(organizationId);
    if (feedbackGeneration !== programConnectionFeedbackGeneration ||
        identityEpoch !== state.identityEpoch || identityKey !== currentIdentityKey() ||
        Number(selectedOrganizationId) !== Number(organizationId) ||
        Number(form?.elements.program_definition_id?.value) !== Number(programDefinitionId)) return;
    programConnectionOutcome = { identityEpoch, identityKey, organizationId: Number(organizationId),
      programDefinitionId: Number(programDefinitionId), connectedProgramDefinitionId: connectedProgramId(organizationId),
      message, tone };
    setStatus(message, tone, form);
  };
  const operationKey = organizationKey(organizationId) + ':' + Number(programDefinitionId);
  const operationId = programConnectionOperationIds.get(operationKey) || createOperationId();
  programConnectionOperationIds.set(operationKey, operationId);
  captureAdminOrganizationsDraft();
  unverifiedProgramConnections.add(organizationKey(organizationId));
  renderAdminOrganizations();
  setStatus('Проверяем результат подключения…', 'loading');
  let commandConfirmed = false;
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/assessment-program', {
      method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ program_definition_id: Number(programDefinitionId), operation_id: operationId }),
    });
    const result = await readApiResponse(response, 'Не удалось подключить программу оценки.');
    const commandConnection = result?.connection;
    if (!isExactProgramConnection(commandConnection, organizationId, programDefinitionId)) {
      throw new Error('Сервер не подтвердил точную версию подключённой программы. Обновите список перед повтором.');
    }
    commandConfirmed = true;
    const readback = await readAdminOrganizationProgram(organizationId, identityEpoch, identityKey);
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return false;
    if (!isExactProgramConnection(readback, organizationId, programDefinitionId)) {
      throw new Error('Команда принята, но повторное чтение не подтвердило подключённую версию. Обновите список перед повтором.');
    }
    unverifiedProgramConnections.delete(organizationKey(organizationId));
    applyAdminOrganizationProgramReadback(organizationId, readback);
    programConnectionOperationIds.delete(operationKey);
    setOutcome('Опубликованная версия программы подключена к организации.', 'success');
    refreshAdminOrganizationQuestionnaireInBackground(organizationId, identityEpoch, identityKey);
    return true;
  } catch (error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return false;
    if (!commandConfirmed) {
      try {
        const readback = await readAdminOrganizationProgram(organizationId, identityEpoch, identityKey);
        if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return false;
        if (isExactProgramConnection(readback, organizationId, programDefinitionId)) {
          unverifiedProgramConnections.delete(organizationKey(organizationId));
          applyAdminOrganizationProgramReadback(organizationId, readback);
          programConnectionOperationIds.delete(operationKey);
          setOutcome('Подключение подтверждено повторным чтением после потери ответа команды.', 'success');
          refreshAdminOrganizationQuestionnaireInBackground(organizationId, identityEpoch, identityKey);
          return true;
        }
      } catch { /* The original command error remains the actionable outcome. */ }
    }
    captureAdminOrganizationsDraft();
    renderAdminOrganizations();
    setOutcome('Результат подключения не подтверждён. ' +
      (error.message || 'Не удалось подключить программу оценки.'), 'error');
    return false;
  } finally {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey) programConnectionRequestsInFlight.delete(connectionKey);
  }
};

export const purgeAdminOrganization = async (organizationId, confirmationCode, previewFingerprint, organizationName = '') => {
  const label = String(organizationName || 'Организация').trim();
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/purge',
      {
        method: 'POST',
        body: JSON.stringify({
          confirmation_code: String(confirmationCode || '').trim(),
          preview_fingerprint: String(previewFingerprint || '').trim(),
          operation_id: createOperationId(),
          acknowledge_irreversible: true,
        }),
      },
      'Не удалось физически удалить организацию.',
    );
    setStatus(
      'Организация «' + label + '», все связанные данные и orphan-аккаунты физически удалены. Аккаунты участников других организаций сохранены.',
      'success',
    );
  } catch (error) {
    setStatus(error.message || 'Не удалось физически удалить организацию «' + label + '».', 'error');
  }
};

export const previewAdminOrganizationPurge = async (organizationId) => {
  const response = await fetch('/users/admin/organizations/' + organizationId + '/purge-preview', {
    credentials: 'same-origin',
  });
  return readApiResponse(response, 'Не удалось построить состав полного удаления.');
};

export const pendingAdminAccountPurges = () => getPendingAccountPurges(Number(currentIdentityKey()));

export const showAdminAccountPurgeError = (error, phase = 'execute', actorId = currentIdentityKey()) => {
  if (String(actorId) !== currentIdentityKey()) return;
  renderAdminOrganizations();
  setStatus(accountPurgeErrorMessage(error, { phase }), 'error');
};

export const previewAdminAccountPurge = (userId) => previewAccountPurge(userId);

const performConfirmedAccountPurge = async (operation, actorId) => {
  setStatus('Проверяем результат удаления человека…', 'loading');
  try {
    await executeAccountPurge(operation, { actorId: Number(actorId) });
  } catch (error) {
    showAdminAccountPurgeError(error, 'execute', actorId);
    return;
  }
  if (String(actorId) !== currentIdentityKey()) return;
  try {
    await loadAdminOrganizations();
  } catch (_error) {
    if (String(actorId) !== currentIdentityKey()) return;
    setStatus('Удаление аккаунта подтверждено. Не удалось обновить список; обновите страницу.', 'success');
    return;
  }
  if (String(actorId) === currentIdentityKey()) {
    setStatus('Аккаунт «' + operation.email + '» и связанные данные полностью удалены.', 'success');
  }
};

export const purgeAdminAccount = async (userId, email, previewFingerprint) => {
  const actorId = currentIdentityKey();
  try {
    const operation = confirmAccountPurge({ actorId, targetUserId: Number(userId), email, fingerprint: previewFingerprint });
    await performConfirmedAccountPurge(operation, actorId);
  } catch (error) {
    showAdminAccountPurgeError(error, 'execute', actorId);
  }
};

export const recoverAdminAccountPurge = async (userId) => {
  const actorId = currentIdentityKey();
  const operation = pendingAdminAccountPurges().find((item) => item.targetUserId === Number(userId));
  if (!operation) {
    setStatus('Подтверждённая операция не найдена для текущего аккаунта входа. Обновите список.', 'error');
    return;
  }
  await performConfirmedAccountPurge(operation, actorId);
};

const renderAccountPurgeButton = (account, { available = false } = {}) => {
  const userId = Number(account.user_id);
  const pending = pendingAdminAccountPurges().some((item) => item.targetUserId === userId);
  if (!userId || userId === Number(currentIdentityKey()) || (!pending && !available)) return '';
  return '<button class="admin-organization-remove-button" type="button" data-action="' +
    (pending ? 'recover-purge-account' : 'purge-account') + '" data-user-id="' + userId +
    '" data-email="' + escapeHtml(account.email) + '">' + (pending ? 'Проверить удаление' : 'Удалить человека') + '</button>';
};

export const mountAdminMemberPurge = (dialog, organizationId, userId) => {
  const item = findOrganizationMember(organizationId, userId);
  if (!item) return;
  const action = renderAccountPurgeButton(item, { available: state.adminOrganizations?.purge_preview_available === true });
  if (action) {
    const zone = dialog.querySelector('[data-card-delete]');
    zone.innerHTML = '<h4>Удаление аккаунта</h4>' + action;
    zone.hidden = false;
  }
};

const renderOrganizationDomains = (domains) => domains.length
  ? '<div class="admin-organizations-tags">' + domains.map((domain) =>
    '<span class="admin-organizations-tag domain"><span>' + escapeHtml(domain) + '</span>' +
    '<button type="button" data-action="delete-domain" data-value="' + escapeHtml(domain) +
    '" aria-label="Удалить домен">×</button></span>').join('') + '</div>'
  : '<p class="admin-organizations-empty">Домены не заданы.</p>';

const renderOrganizationAdmins = (org, canDeletePerson) => {
  const admins = org.admins || [];
  const active = org.is_active !== false;
  const canRevoke = active && admins.length > 1;
  const note = !active ? 'Организация неактивна. Изменение доступа станет доступно после восстановления.'
    : admins.length === 1 ? 'Чтобы снять права у последнего администратора, сначала добавьте другого сотрудника.' : '';
  const rows = admins.map((item) => {
    const name = escapeHtml(item.full_name || item.email);
    const email = escapeHtml(item.email);
    const participation = item.is_participant === true ? 'Также участник оценки'
      : item.is_participant === false ? 'Только административный доступ' : 'Участие не указано';
    const accessData = ' data-value="' + email + '" data-participant="' + String(item.is_participant) +
      '" data-person-name="' + name + '"';
    const viewAccessData = ' type="button" data-action="view-admin-access"' + accessData + ' data-active="' + active + '"';
    const identity = '<button class="text-button admin-access-name"' + viewAccessData + '>' + name + '</button>';
    const view = '<button class="text-button admin-access-link"' + viewAccessData +
      ' aria-label="Права доступа · ' + name + '">Права доступа</button>';
    const revoke = canRevoke ? '<button class="ghost-button compact-ghost" type="button" data-action="delete-admin"' +
      accessData + '>Снять права</button>' : '';
    const purge = renderAccountPurgeButton(item, { available: canDeletePerson });
    const actions = revoke + purge;
    return '<li class="admin-access-row"><div>' + identity +
      (item.full_name ? '<p>' + email + '</p>' : '') + '</div>' +
      '<div><strong class="admin-access-role' + (active ? '' : ' is-paused') + '">' +
      (active ? 'Администратор' : 'Доступ приостановлен') + '</strong><p>' + participation + '</p></div>' +
      '<div class="admin-access-actions">' + view +
      (actions ? renderMemberMenu(actions, 'Другие действия · ' + (item.full_name || item.email)) : '') + '</div></li>';
  }).join('');
  return '<section class="admin-access-workspace' + (active ? '' : ' is-paused') + '" data-organization-admins>' +
    '<div class="admin-access-panel"><h4>Администраторы организации</h4>' +
    (rows ? '<ul class="admin-access-list">' + rows + '</ul>'
      : '<p class="admin-organizations-empty">Администраторов пока нет.</p>') +
    (note ? '<p class="admin-access-note">' + note + '</p>' : '') + '</div>' +
    (active ? '<form class="admin-access-panel admin-access-form" data-action="add-admin">' +
      '<h4>Добавить администратора</h4><label><span>Рабочая почта</span>' +
      '<input type="email" name="email" placeholder="name@example.test" maxlength="254" required></label>' +
      '<label><span>ФИО, если известно</span><input name="full_name" maxlength="180"></label>' +
      '<p class="admin-access-note">Укажите именную почту сотрудника. Ему будут доступны анкета и все отчёты организации, включая прежние.</p>' +
      '<button class="primary-button compact-primary" type="submit">Добавить</button></form>' : '') + '</section>';
};

const stageLabels = {
  assigned: 'Оценка назначена', acquaintance: 'Знакомство', acquaintance_complete: 'Знакомство завершено',
  preparing: 'Готовится оценка', preparation_failed: 'Подготовка заблокирована',
  preparation_complete: 'Подготовка завершена, старт ещё не подтверждён', start_blocked: 'Старт оценки заблокирован',
  ready_to_start: 'Готов к прохождению оценки', active: 'Оценка выполняется', paused: 'Оценка приостановлена',
  interrupted: 'Оценка прервана', processing: 'Готовится отчёт',
  report_ready: 'Отчёт готов', failed: 'Обработка завершилась с ошибкой', cancelled: 'Назначение отменено',
};

const observedPreparation = (stage) => {
  // A historical preparation cannot override cancellation or a start blocker.
  const model = stage?.preparation;
  return model && ['preparing', 'preparation_failed', 'active', 'paused', 'interrupted', 'processing', 'failed', 'report_ready'].includes(stage.code) ? model : null;
};

const canCheckPreparation = (stage) => {
  const model = observedPreparation(stage);
  return stage?.action === 'check_preparation' || stage?.code === 'preparation_failed' ||
    (stage?.code !== 'report_ready' && (model?.status === 'failed' || model?.allowed_actions?.includes('check')));
};

const assessmentStageView = (stage, hasAssignment, includeObservation = true) => {
  const model = includeObservation ? observedPreparation(stage) : null;
  const preparation = model ? preparationPresentation(model, { readError: organizationsReadStale }) : null;
  const label = stage?.label || stageLabels[stage?.code] || stage?.code ||
    (hasAssignment ? 'Оценка назначена' : 'Оценка не назначена');
  const description = stage?.description || (stage?.code === 'cancelled' ? 'Назначение отменено.' :
    stage || hasAssignment ? 'Ожидаем следующего действия участника или системы.' : 'Для выбранной оценки назначения нет.');
  const critical = ['preparation_failed', 'start_blocked', 'failed'].includes(stage?.code) || preparation?.failed;
  if (preparation?.failed && model.kind === 'next') {
    const progress = stage.progress;
    const summary = [
      stage.code === 'paused' ? 'Оценка приостановлена.' : '',
      progress ? 'Завершено ' + progress.completed + ' из ' + progress.planned + ' ситуаций.' : '',
    ].filter(Boolean).join(' ');
    return { label: 'Не удалось подготовить следующую ситуацию', description: summary || preparation.explanation, critical };
  }
  if (preparation?.uncertain) {
    return { label: preparation.stage, description: preparation.notices[0] || preparation.explanation, critical };
  }
  if (stage?.code === 'preparing' && preparation?.explanation) {
    return { label, description: preparation.notices[0] || preparation.explanation, critical };
  }
  return { label, description, critical };
};

const renderMemberMenu = (items, label = 'Другие действия') =>
  '<details class="admin-organization-member-menu"><summary aria-label="' + escapeHtml(label) +
  '" aria-haspopup="menu" aria-expanded="false">⋯</summary><div role="menu" aria-label="' + escapeHtml(label) + '">' +
  items.replaceAll(' role="menuitem"', '').replaceAll('<button ', '<button role="menuitem" ') + '</div></details>';

const renderMemberList = (items, {
  isSuperadmin = false, canDeletePerson = false, canAssign = false, activeOrganization = true,
  selectedAssessmentRef = '', selectedAssessmentLabel = '', organizationId = selectedOrganizationId, appealsOnly = false,
} = {}) => {
  if (appealsOnly) items = items.filter(item => Number(item.issue_count || 0) > 0);
  if (!items.length) {
    return '<p class="admin-organizations-empty">' + (appealsOnly ? 'Участников с обращениями нет.' : 'Участники не привязаны.') + '</p>';
  }
  const pendingOperations = pendingInvitationOperations().filter((operation) =>
    operation.organizationId === Number(organizationId) && operation.assignmentRef === selectedAssessmentRef);
  return (
    '<div class="admin-organization-members">' +
    items
      .map((item) => {
        const email = String(item.email || '');
        const hasPassword = item.has_password === true;
        const participantName = item.full_name || email;
        const details = item.raw_position || item.job_description || item.role_description || item.raw_duties || '';
        const scopedStage = item.assessment_stages?.[selectedAssessmentRef] || null;
        const preparationStatus = String(scopedStage?.code || '');
        const preparationModel = observedPreparation(scopedStage);
        const isPreparing = preparationStatus === 'preparing';
        const isPrepared = ['preparation_complete', 'start_blocked', 'ready_to_start', 'active', 'paused', 'interrupted', 'processing', 'report_ready'].includes(preparationStatus);
        const canPrepare = item.assessment_profile_ready === true && !isPreparing && !isPrepared;
        const preparationButton = !isSuperadmin ? '' : isPrepared
          ? '<span class="admin-organization-preparation-state ready">Кейсы готовы</span>'
          : isPreparing
            ? '<span class="admin-organization-preparation-state">Подготовка…</span>'
            : '<button class="admin-organization-prepare-button" type="button" data-action="prepare-member-assessment" data-user-id="' +
              Number(item.user_id) +
              '"' +
              (canPrepare ? '' : ' disabled title="Заполните роль, обязанности и сферу деятельности"') +
              '>Подготовить кейсы</button>';
        const removeButton = isSuperadmin ? renderAccountPurgeButton(item, { available: canDeletePerson }) : '';
        const invitation = invitationFor(organizationId, selectedAssessmentRef, item);
        const invitationStatus = String(item.invitation_status || 'not_sent');
        const invitationLabels = { not_sent: 'Письмо не отправлено', queued: 'Письмо в очереди', sending: 'Исход отправки уточняется', accepted: 'Письмо принято провайдером', error: 'Ошибка отправки', revoked: 'Ссылка отозвана', expired: 'Ссылка истекла', used: 'Регистрация завершена' };
        const invitationExpiry = localDateTime(invitation.expires_at || item.invitation_expires_at);
        const registrationLabel = item.registration_status === 'registered' ? 'Регистрация: завершена' : 'Регистрация: ожидается';
        const invitationLabel = invitationLabels[invitationStatus] || 'Статус письма неизвестен';
        const deliveryLabel = invitationFacts(invitation).outcome === 'failed' ? 'Приглашение не отправлено' : invitationMessage(invitation, { compact: true });
        const linkLabel = invitationLinkMessage(invitation.link_status || item.invitation_link_status, invitationExpiry);
        const hasAssignment = (item.assessment_assignments || []).includes(selectedAssessmentRef);
        const { label: currentStage, description: stageDescription, critical } = assessmentStageView(scopedStage, hasAssignment, !isSuperadmin);
        const assignmentHistory = (item.assessment_history || [])
          .filter((entry) => !selectedAssessmentRef || entry.assignment_ref === selectedAssessmentRef)
          .map((entry) => {
            const status = entry.assignment_status === 'active' ? 'назначено' :
              entry.assignment_status === 'revoked' ? 'отменено' : entry.assignment_status || 'статус неизвестен';
            const created = localDateTime(entry.assignment_created_at);
            const revoked = localDateTime(entry.assignment_revoked_at);
            const cycle = entry.cycle_id ? 'Cycle ' + entry.cycle_id +
              (entry.cycle_status ? ' (' + entry.cycle_status + ')' : '') : 'Cycle ещё не создан';
            return ['Назначение #' + entry.assignment_id + ': ' + status, created ? 'создано ' + created : '',
              revoked ? 'отменено ' + revoked : '', cycle].filter(Boolean).join(', ');
          }).join(' · ') || 'История точного назначения отсутствует';
        const sendLabel = item.invitation_id ? 'Отправить письмо повторно' : 'Пригласить';
        const pendingInvitation = pendingOperations.find((operation) => operation.emails.includes(email.toLowerCase()));
        const pendingCheck = pendingInvitation
          ? '<button type="button" data-action="recover-member-invitation" data-receipt-only data-request-key="' +
            escapeHtml(pendingInvitation.requestKey) + '"' +
            (invitationRequestsInFlight.has(state.identityEpoch + ':' + pendingInvitation.requestKey) ? ' disabled' : '') +
            '>Проверить отправку</button>' : '';
        const saved = savedInvitation(item);
        const receiptRef = item.invitation_assignment_ref || '';
        const separateReceipt = !isSuperadmin && saved.invitation_id && (!receiptRef || receiptRef !== selectedAssessmentRef);
        const savedReceiptUnresolved = ['unknown', 'pending'].includes(invitationFacts(saved).outcome);
        const savedCheck = saved.invitation_id && saved.operation_id && receiptRef && savedReceiptUnresolved
          ? '<button type="button" data-action="check-member-invitation" data-value="' + escapeHtml(saved.email) +
            '" data-operation-id="' + escapeHtml(saved.operation_id) + '" data-assignment-ref="' + escapeHtml(receiptRef) +
            '" data-invitation-id="' + saved.invitation_id + '">Проверить отправку</button>' : '';
        const invitationButton = invitationStatus === 'used' ? '' : ['unknown', 'pending'].includes(invitationFacts(invitation).outcome) && invitation.delivery_status !== 'not_sent'
          ? pendingCheck || savedCheck
          : '<button type="button" data-action="send-member-invitation" data-value="' + escapeHtml(email) + '">' + sendLabel + '</button>';
        const revokeButton = (invitationStatus === 'accepted' || invitationStatus === 'queued' || invitationStatus === 'sending')
          ? '<button type="button" role="menuitem" data-action="revoke-member-invitation" data-participant-name="' + escapeHtml(participantName) + '" data-invitation-id="' + Number(item.invitation_id) + '" data-value="' + escapeHtml(email) + '">Отозвать приглашение</button>'
          : '';
        const cancellableStage = ['assigned', 'acquaintance', 'acquaintance_complete', 'preparing', 'preparation_failed', 'preparation_complete', 'start_blocked', 'ready_to_start'].includes(preparationStatus);
        const cancelButton = scopedStage?.assignment_id && cancellableStage
          ? '<button type="button" role="menuitem" data-action="cancel-member-assignment" data-assignment-id="' + Number(scopedStage.assignment_id) + '" data-participant-name="' + escapeHtml(participantName) + '" data-assessment-ref="' + escapeHtml(selectedAssessmentRef) + '" data-assessment-label="' + escapeHtml(selectedAssessmentLabel || 'выбранная оценка') + '" data-value="' + escapeHtml(email) + '">Отменить назначение оценки</button>'
          : '';
        const reportButton = scopedStage?.action === 'open_report' && scopedStage.report_id &&
          (isSuperadmin || (scopedStage.cycle_id && scopedStage.report_access === 'customer'))
          ? '<button type="button" data-action="open-member-report" data-report-id="' + escapeHtml(scopedStage.report_id) +
            '" data-cycle-id="' + escapeHtml(scopedStage.cycle_id || '') + '" data-report-access="' +
            escapeHtml(scopedStage.report_access || '') + '">' +
            (['insufficient', 'without_score'].includes(scopedStage.result_summary?.kind) ? 'Открыть пояснение' : 'Открыть отчёт') + '</button>' : '';
        const checkPreparationButton = (isSuperadmin
          ? scopedStage?.action === 'check_preparation' || (preparationStatus === 'preparation_failed' && scopedStage?.operation_id)
          : canCheckPreparation(scopedStage))
          ? '<button type="button" data-action="check-member-preparation">Проверить состояние</button>' : '';
        const processingButton = scopedStage?.action === 'open_processing'
          ? '<button type="button" data-action="open-member-processing" data-participant-name="' + escapeHtml(participantName) +
            '" data-stage-description="' + escapeHtml(stageDescription) + '">Подробнее об обработке</button>' : '';
        const legacyPrimary = reportButton || processingButton || checkPreparationButton ||
          (!hasAssignment && ['not_sent', 'error', 'revoked', 'expired'].includes(invitationStatus) ? invitationButton : '');
        const legacyExtras = (legacyPrimary === invitationButton ? '' : invitationButton) +
          revokeButton + cancelButton + preparationButton + removeButton;

        const link = ['used', 'revoked', 'expired'].includes(item.invitation_link_status)
          ? item.invitation_link_status : invitation.link_status || item.invitation_link_status;
        const registered = link === 'used' || item.registration_status === 'registered' || item.has_password === true;
        const delivery = invitationFacts(invitation).outcome;
        const linkInvitation = invitation.invitation_id ? invitation : saved;
        const invitationId = Number(linkInvitation.invitation_id || 0);
        const linkClosed = ['revoked', 'expired', 'used'].includes(link);
        const checkInvitation = (!linkClosed && ['unknown', 'pending', 'not_attempted'].includes(delivery)
          ? pendingCheck : '') || savedCheck;
        const resend = delivery === 'accepted' && link === 'active' && invitationId;
        const awaitingParticipant = !scopedStage || ['assigned', 'cancelled'].includes(preparationStatus);
        const canSend = activeOrganization && selectedAssessmentRef && !registered && awaitingParticipant &&
          !checkInvitation && !(separateReceipt && savedReceiptUnresolved && !linkClosed) &&
          (!['unknown', 'pending'].includes(delivery) || linkClosed);
        const send = canSend ? '<button type="button" data-action="send-member-invitation" data-value="' + escapeHtml(email) + '">' +
          (resend ? 'Отправить письмо повторно' : ['revoked', 'expired'].includes(link) ? 'Пригласить снова' :
            delivery === 'failed' ? 'Повторить отправку' : 'Пригласить') + '</button>' : '';
        const acquaintanceStarted = scopedStage?.acquaintance_status &&
          !['not_started', 'unknown'].includes(scopedStage.acquaintance_status);
        const revoke = !linkClosed && !acquaintanceStarted && invitationId &&
          ['accepted', 'queued', 'sending'].includes(linkInvitation.delivery_status || invitationStatus)
          ? '<button type="button" data-action="revoke-member-invitation" data-participant-name="' + escapeHtml(participantName) +
            '" data-invitation-id="' + invitationId + '" data-value="' + escapeHtml(email) + '">Отозвать приглашение</button>' : '';
        const assign = canAssign && !hasAssignment && (!scopedStage || preparationStatus === 'cancelled')
          ? '<button type="button" data-action="open-member-assignment" data-user-id="' + Number(item.user_id) +
            '" data-assessment-ref="' + escapeHtml(selectedAssessmentRef) + '">Назначить оценку</button>' : '';
        const hasSentMenu = Boolean(resend && send && revoke);
        const secondaries = hasSentMenu ? [send, revoke] : [revoke, cancelButton].filter(Boolean);
        const secondaryActions = secondaries.length > 1 ? renderMemberMenu(secondaries.join(''), 'Действия для ' + participantName) :
          (secondaries[0] || '').replace(' role="menuitem"', '');
        const actions = isSuperadmin
          ? legacyPrimary + ((legacyExtras.match(/<button\b/g) || []).length > 1
            ? renderMemberMenu(legacyExtras) : legacyExtras.replace(' role="menuitem"', ''))
          : reportButton || (checkPreparationButton || processingButton) + checkInvitation + assign +
            (hasSentMenu ? '' : send) + secondaryActions +
            (hasSentMenu ? cancelButton.replace(' role="menuitem"', '') : '');

        const invitationStage = !separateReceipt && !registered && !scopedStage && !hasAssignment && (link === 'revoked' ? 'Приглашение отозвано' :
          link === 'expired' ? 'Срок ссылки истёк' : delivery === 'accepted' ? 'Письмо отправлено' :
          delivery === 'failed' ? 'Не удалось отправить приглашение' : delivery === 'pending' ? 'Приглашение отправляется' :
          checkInvitation || delivery === 'unknown' ? 'Исход отправки уточняется' : !assign ? 'Не приглашён' : '');
        const invitationNote = registered ? (link === 'used' ? 'Ссылка использована · ' : '') + 'Регистрация: завершена' :
          separateReceipt ? [linkLabel, registrationLabel].join(' · ') :
          resend ? [linkLabel, registrationLabel].join(' · ') :
          linkClosed ? 'Можно отправить новое приглашение.' :
          delivery !== 'not_attempted' ? invitationMessage(invitation, { compact: true }) : '';
        const cardDescription = invitationStage
          ? resend ? linkLabel : invitationNote || (send ? 'Отправьте участнику письмо со ссылкой для входа.' : stageDescription)
          : stageDescription;
        const showInvitationNote = !reportButton && preparationStatus !== 'report_ready' &&
          (!scopedStage || preparationStatus === 'assigned' || checkInvitation) && invitationNote;
        const previousReceipt = separateReceipt && (receiptRef
          ? 'Отправка по другой оценке (' + receiptRef + ') · ' + invitationMessage(saved, { compact: true })
          : 'Не удалось подтвердить, к какой оценке относится отправка.');
        const compactStageMarkup = '<div class="admin-organization-member-stage"><strong class="admin-organization-current-stage' +
          (critical || delivery === 'failed' && invitationStage ? ' is-critical' : '') + '">' +
          escapeHtml(invitationStage || currentStage) + '</strong>' +
          (showInvitationNote ? '<span class="admin-organization-member-invitation">' + escapeHtml(invitationNote) + '</span>' : '') +
          (previousReceipt ? '<span class="admin-organization-member-invitation">' + escapeHtml(previousReceipt) + '</span>' : '') +
          ((!invitationStage || !showInvitationNote) ? '<span>' + escapeHtml(invitationStage && send
            ? 'Отправьте участнику письмо со ссылкой для входа.' : stageDescription) + '</span>' : '') +
          (invitation.next_action === 'review_organization' && (showInvitationNote || checkInvitation)
            ? '<button type="button" data-action="review-invitation-organization">Проверить сведения организации</button>' : '') + '</div>';
        return (
          '<article class="admin-organization-member" data-member-user-id="' + Number(item.user_id) + '">' +
          '<label class="admin-organization-member-select"><input type="checkbox" name="invitation_email" value="' + escapeHtml(email) + '" data-user-id="' + Number(item.user_id) + '" aria-label="Выбрать ' + escapeHtml(email) + '"></label>' +
          '<div class="admin-organization-member-main"><button type="button" class="admin-organization-member-name" data-action="open-member-card" data-user-id="' + Number(item.user_id) + '" data-participant-name="' + escapeHtml(participantName) + '" data-email="' + escapeHtml(email) + '" data-position="' + escapeHtml(details) + '" data-stage="' + escapeHtml(isSuperadmin ? currentStage : invitationStage || currentStage) + '" data-stage-description="' +
            escapeHtml(isSuperadmin ? stageDescription : cardDescription) + '" data-assignment-history="' + escapeHtml(assignmentHistory) + '" data-admission="' + escapeHtml(item.admission_status === 'denied' ? 'Запрещён' : 'Разрешён') + '" data-invitation-info="' + escapeHtml(JSON.stringify(invitation)) + '" data-invitation-assessment="' + escapeHtml(selectedAssessmentRef) + '" data-can-reset-password="' + (isSuperadmin && hasPassword ? 'true' : 'false') + '">' + escapeHtml(participantName) + '</button>' +
          '<span class="admin-organization-member-email">' + escapeHtml(email) + '</span>' +
          (item.issue_count ? '<span class="admin-organization-member-issues">С обращениями · ' + Number(item.issue_count) + '</span>' : '') +
          (details ? '<span class="admin-organization-member-position">' + escapeHtml(details) + '</span>' : '') +
          (isSuperadmin ? '<span class="admin-organization-member-invitation" title="' + escapeHtml(invitationLabel) + '">' +
          escapeHtml(deliveryLabel + ' · ' + linkLabel + ' · ' + registrationLabel) + '</span>' +
          (['failed', 'unknown', 'pending'].includes(invitationFacts(invitation).outcome) && invitation.delivery_status !== 'not_sent' && invitationMessage(invitation, { compact: true }) !== deliveryLabel
            ? '<span class="admin-invitation-reason">' + escapeHtml(invitationMessage(invitation, { compact: true })) +
              (invitationMissingText(invitation) ? ' · Не заполнены: ' + escapeHtml(invitationMissingText(invitation)) : '') + '</span>' +
              (invitation.next_action === 'review_organization' ? '<button type="button" data-action="review-invitation-organization">Проверить сведения организации</button>' : '') : '') : '') +
          '</div>' +
          (isSuperadmin ? (preparationModel ? preparationHtml(preparationModel, { compact: true }) :
            '<div class="admin-organization-member-stage"><strong class="admin-organization-current-stage' +
            (critical ? ' is-critical' : '') + '">' + escapeHtml(currentStage) + '</strong><span>' + escapeHtml(stageDescription) + '</span>' +
            (preparationStatus === 'preparation_failed' && scopedStage?.operation_id
              ? '<span>Номер случая: ' + escapeHtml(scopedStage.operation_id) + '</span>' : '') + '</div>') : compactStageMarkup) +
          '<div class="admin-organization-member-actions">' +
          actions +
          '</div>' +
          '</article>'
        );
      })
      .join('') +
    '</div>'
  );
};

const findOrganizationMember = (organizationId, userId) =>
  organizationById(organizationId)?.members?.find((item) => Number(item.user_id) === Number(userId));

export const checkAdminMemberPreparation = async (organizationId, userId) => {
  const reference = getSelectedAdminOrganizationAssessment(organizationId);
  const stage = () => findOrganizationMember(organizationId, userId)?.assessment_stages?.[reference];
  const assignmentId = stage()?.assignment_id;
  const isCurrent = () => state.currentScreen === 'admin-organizations' && selectedOrganizationId === organizationId &&
    getSelectedAdminOrganizationAssessment(organizationId) === reference;
  if (!isCurrent() || !await refreshAdminOrganizationsSafely({ isCurrent })) return;
  const currentStage = stage();
  if (assignmentId != null && currentStage?.assignment_id !== assignmentId) {
    setStatus('Назначение изменилось. Проверьте актуальную строку участника.', 'muted', undefined, { focus: false });
    return;
  }
  if (currentStage) setStatus('Состояние обновлено. ' + assessmentStageView(currentStage, true).label + '.',
    'success', undefined, { focus: false });
};

export const mountAdminMemberAssessment = (dialog, organizationId, trigger) => {
  const { userId, invitationAssessment: assessmentRef } = trigger.dataset;
  const member = () => findOrganizationMember(organizationId, userId);
  const stageFor = (item) => item?.assessment_stages?.[assessmentRef];
  const assignmentId = stageFor(member())?.assignment_id;
  const epoch = state.identityEpoch;
  const isCurrent = () => dialog.open && epoch === state.identityEpoch && state.currentScreen === 'admin-organizations' &&
    Number(selectedOrganizationId) === organizationId && getSelectedAdminOrganizationAssessment(organizationId) === assessmentRef;
  const incident = dialog.querySelector('[data-card-incident]');
  const lastStage = incident.querySelector('[data-card-last-stage]');
  const caseLine = incident.querySelector('[data-card-case]');
  const caseNumber = caseLine.querySelector('code');
  const check = incident.querySelector('[data-card-check]');
  const copy = incident.querySelector('[data-card-copy]');
  const feedback = dialog.querySelector('[data-card-check-feedback]');
  const technical = dialog.querySelector('[data-card-technical]');
  const profile = dialog.querySelector('[data-card-profile]');
  const start = dialog.querySelector('[data-card-start]');

  const update = (stage) => {
    const model = observedPreparation(stage);
    const canCheck = canCheckPreparation(stage);
    const failed = model?.status === 'failed' || stage?.code === 'preparation_failed';
    const reference = failed ? model?.reference || '' : '';
    const hasKnownStage = Boolean(model?.stage_label && model.stage_started_at);
    incident.hidden = !canCheck && !reference;
    check.hidden = !canCheck;
    lastStage.hidden = !failed || !hasKnownStage;
    lastStage.textContent = lastStage.hidden ? '' : 'Последний подтверждённый этап · ' + model.stage_label;
    caseNumber.textContent = reference;
    caseLine.hidden = copy.hidden = !reference;
    profile.textContent = stage?.profile_readiness?.status === 'ready' ? 'Заполнены' :
      stage?.profile_readiness?.status === 'blocked' ? 'Требуют уточнения' : 'Нет подтверждённых сведений';
    start.textContent = stage?.start_readiness?.can_start === true || stage?.code === 'ready_to_start' ? 'Подтверждён' :
      stage?.start_readiness?.can_start === false || stage?.code === 'start_blocked' ? 'Заблокирован' : 'Нет подтверждённых сведений';
    technical.hidden = !model;
    if (model) renderPreparation(technical, model, { readError: organizationsReadStale });
  };

  const initial = member();
  if (initial) update(stageFor(initial));
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(caseNumber.textContent);
      feedback.textContent = 'Номер скопирован.';
    } catch {
      feedback.textContent = 'Не удалось скопировать номер.';
    }
  });
  check.addEventListener('click', async () => {
    check.disabled = true;
    feedback.textContent = 'Проверяем состояние…';
    const refreshed = await refreshAdminOrganizationsSafely({ isCurrent });
    check.disabled = false;
    if (!isCurrent()) return;
    if (!refreshed) {
      const lastKnown = observedPreparation(stageFor(member()));
      if (lastKnown) renderPreparation(technical, lastKnown, { readError: true });
      feedback.textContent = 'Не удалось обновить состояние. Показаны последние полученные сведения.';
      check.focus();
      return;
    }
    const current = member();
    const stage = stageFor(current);
    if (!current || (assignmentId != null && stage?.assignment_id !== assignmentId)) {
      feedback.textContent = 'Назначение изменилось. Откройте карточку заново.';
      return;
    }
    const view = assessmentStageView(stage, current.assessment_assignments?.includes(assessmentRef));
    dialog.querySelector('[data-card-stage]').textContent = view.label;
    dialog.querySelector('[data-card-description]').textContent = view.description;
    update(stage);
    feedback.textContent = 'Состояние обновлено.';
    (check.hidden ? dialog.querySelector('.dialog-close') : check)?.focus();
  });
};

const restoreMemberMenuFocus = ({ control, wasOpen }) => {
  const previousMenu = control.closest('.admin-organization-member-menu');
  const previousRow = previousMenu.closest('[data-member-user-id]');
  const organizationId = previousRow.closest('[data-organization-id]').dataset.organizationId;
  const row = adminOrganizationsList.querySelector(
    '[data-organization-id="' + CSS.escape(organizationId) + '"] ' +
    '[data-member-user-id="' + CSS.escape(previousRow.dataset.memberUserId) + '"]',
  );
  const cardButton = row?.querySelector('[data-action="open-member-card"]');
  const menu = row?.querySelector('.admin-organization-member-menu');
  const previousAssessment = previousRow.querySelector('[data-action="open-member-card"]').dataset.invitationAssessment;
  const item = menu && wasOpen && previousAssessment === cardButton?.dataset.invitationAssessment
    ? [...menu.querySelectorAll('[role="menuitem"]:not(:disabled)')].find((candidate) => candidate.isEqualNode(control))
    : null;
  if (item) menu.open = true;
  (item || menu?.querySelector('summary') || cardButton)?.focus({ preventScroll: true });
};

export const renderAdminOrganizations = () => {
  restoreManagementSelection();
  const data = state.adminOrganizations;
  if (!adminOrganizationsList) {
    return;
  }
  const accountName = document.getElementById('admin-organizations-account-name');
  if (accountName) {
    const name = state.pendingUser?.full_name || state.pendingUser?.email || 'Аккаунт';
    accountName.textContent = name;
    accountName.setAttribute('aria-label', 'Меню аккаунта: ' + name);
  }
  if (adminOrganizationsTitle) {
    const activeView = organizationViews.get(Number(selectedOrganizationId)) || 'people';
    adminOrganizationsTitle.textContent = data?.is_superadmin ? 'Организации'
      : ({ people: 'Участники оценки', 'organization-data': 'Данные организации', questionnaire: 'Анкета' })[activeView];
  }
  if (adminOrganizationsSubtitle) {
    adminOrganizationsSubtitle.textContent = data?.is_superadmin
      ? 'Программы оценки, администраторы и проблемы организации.'
      : organizationViews.get(Number(selectedOrganizationId)) === 'organization-data'
        ? 'Подготовьте сведения, которые увидят участники перед оценкой.'
        : 'Подготовьте сведения для оценки и назначьте её участникам.';
  }
  const organizations = Array.isArray(data?.items) ? data.items : [];
  clearInaccessibleOrganizationState(organizations);
  const isSuperadmin = Boolean(data?.is_superadmin);
  const summaryButton = document.getElementById('admin-organizations-back-button');
  const accountActions = accountName?.nextElementSibling;
  if (summaryButton && accountActions && accountActions.contains(summaryButton) === isSuperadmin) {
    if (isSuperadmin) accountActions.parentElement.before(summaryButton);
    else accountActions.prepend(summaryButton);
    summaryButton.classList.toggle('user-menu-item', !isSuperadmin);
  }
  const physicalPurgeAvailable = Boolean(data?.physical_purge_available);
  const purgePreviewAvailable = Boolean(data?.purge_preview_available);
  const pendingPurges = pendingAdminAccountPurges();
  const purgeRecoveryMarkup = pendingPurges.length ? '<section class="card card--inset admin-purge-recovery" role="status">' +
    '<h3>Проверка полного удаления</h3><p>Исход подтверждённой операции пока не установлен. ' +
    'Проверьте результат той же операции перед другими действиями с аккаунтом.</p>' +
    pendingPurges.map((operation) => '<div class="admin-account-row"><span>' + escapeHtml(operation.email) +
      '</span><button class="ghost-button compact-ghost" type="button" data-action="recover-purge-account" data-user-id="' +
      operation.targetUserId + '">Проверить результат удаления</button></div>').join('') + '</section>' : '';
  const staleMarkup = organizationsReadStale ? '<div class="form-status error" role="status" data-organizations-stale>' +
    '<strong>Показано последнее подтверждённое состояние.</strong> ' + escapeHtml(organizationsReadStaleReason) +
    ' <button type="button" class="text-button" data-action="refresh-admin-organizations">Обновить безопасно</button></div>' : '';
  adminOrganizationsPanel.dataset.superadmin = String(isSuperadmin);
  if (isSuperadmin) document.querySelector('[data-platform-section="organizations"]')?.setAttribute('aria-current', 'page');
  document.getElementById('platform-availability')?.classList.add('hidden');
  adminOrganizationsPanel.querySelector('.admin-organizations-shell')?.classList.remove('hidden');
  document.querySelector('[data-admin-area="assessment"]')?.classList.toggle('hidden', isSuperadmin);
  document.getElementById('admin-organization-create-form')?.closest('section')?.classList.toggle(
    'hidden', !data || !isSuperadmin,
  );
  document.querySelector('.admin-organization-picker')?.classList.toggle('hidden', !isSuperadmin && organizations.length <= 1);
  if (!organizations.length) {
    if (adminOrganizationSelect) adminOrganizationSelect.innerHTML = '<option value="">Нет организаций</option>';
    adminOrganizationsList.innerHTML = purgeRecoveryMarkup + staleMarkup + '<p class="report-empty-state">' + (isSuperadmin
      ? 'Организации пока не созданы.'
      : 'Закреплённая организация недоступна или доступ отозван. Обратитесь к администратору платформы.') + '</p>';
    return;
  }
  if (!organizations.some((org) => Number(org.id) === Number(selectedOrganizationId))) {
    selectedOrganizationId = Number(organizations.find((org) => org.is_active !== false)?.id || organizations[0].id);
  }
  const pendingInvitations = pendingInvitationOperations().filter((operation) =>
    operation.organizationId === Number(selectedOrganizationId));
  const invitationRecoveryMarkup = pendingInvitations.length
    ? '<section class="card card--inset admin-invitation-recovery" role="status"><h3>Проверка приглашений</h3>' +
      '<p>Исход предыдущей отправки ещё не подтверждён. Проверьте ту же операцию.</p>' +
      pendingInvitations.map((operation) => {
        const previousScope = !isSuperadmin && operation.assignmentRef !== organizationProgramState(operation.organizationId).assessmentRef;
        return '<div class="admin-account-row"><span>' +
          escapeHtml(operation.emails.map((email) => participantLabel(operation.organizationId, { email })).join(', ')) +
          '</span><button class="ghost-button compact-ghost" type="button" data-action="recover-member-invitation" data-request-key="' +
          escapeHtml(operation.requestKey) + '"' + (previousScope ? ' data-receipt-only' : '') + '>' +
          (isSuperadmin ? 'Проверить исход' : previousScope ? 'Проверить прежнюю попытку' : 'Восстановить отправку') +
          '</button></div>';
      }).join('') + '</section>' : '';
  if (adminOrganizationSelect) {
    adminOrganizationSelect.innerHTML = organizations
      .map(
        (org) =>
          '<option value="' + Number(org.id) + '"' +
          (Number(org.id) === Number(selectedOrganizationId) ? ' selected' : '') + '>' +
          escapeHtml(org.name) + ' · ' + escapeHtml(org.code) + (org.is_active === false ? ' — неактивна' : '') +
          '</option>',
      )
      .join('');
  }
  const preparationRoots = new Map(Array.from(adminOrganizationsList.querySelectorAll('[data-preparation-status]'), (node) => [node.dataset.preparationReferenceId, node]));
  const focusedPreparationControl = document.activeElement?.closest?.('[data-preparation-status]') ? document.activeElement : null;
  const focusedCheckUser = document.activeElement?.matches?.('[data-action="check-member-preparation"]') ? document.activeElement.closest('.admin-organization-member')?.querySelector('[data-user-id]')?.dataset.userId : null;
  const focusedConfirmation = document.activeElement?.matches?.('[data-organization-confirmed]');
  const focusedMenu = !isSuperadmin && document.activeElement?.closest?.('.admin-organization-member-menu');
  // Replacing the list can dispatch focusout and close the old menu synchronously.
  const menuFocus = focusedMenu ? { control: document.activeElement, wasOpen: focusedMenu.open } : null;
  let confirmationToRestore;
  adminOrganizationsList.innerHTML = purgeRecoveryMarkup + invitationRecoveryMarkup + staleMarkup + organizations
    .filter((org) => Number(org.id) === Number(selectedOrganizationId))
    .map((org) => {
      const orgId = Number(org.id);
      const isActive = org.is_active !== false;
      const activeBatch = state.adminOrganizationPreparationBatches?.[orgId];
      const batchIsRunning = activeBatch?.status === 'in_progress';
      const revisions = questionnaireRevisions.get(organizationKey(orgId)) || [];
      const currentProgram = org.assessment_program || null;
      const programState = organizationProgramState(orgId);
      const programConnectionUnverified = programState.status === 'unknown';
      const programConfirmed = programState.status === 'confirmed';
      const reportProgram = programConfirmed && currentProgram.pilot_plan_ref ? currentProgram : null;
      const connectedRef = String(currentProgram?.assignment_ref || '').trim();
      const storedRef = selectedAssessmentRefs.get(organizationKey(orgId)) || '';
      const selectedRef = connectedRef || storedRef || revisions[0]?.assignment_ref || '';
      if (programConfirmed && !storedRef) {
        // Local input before the first connection can move into its first scope.
        // A draft belonging to another program never moves.
        for (const action of ['preview-early-data', 'preview-questionnaire']) {
          const unscopedKey = organizationKey(orgId) + ':' + action + ':';
          const scopedKey = unscopedKey + connectedRef;
          if (managementDrafts.has(unscopedKey) && !managementDrafts.has(scopedKey)) {
            managementDrafts.set(scopedKey, managementDrafts.get(unscopedKey));
            managementDrafts.delete(unscopedKey);
          }
        }
      }
      if (connectedRef && storedRef !== connectedRef) {
        selectedAssessmentRefs.set(organizationKey(orgId), connectedRef);
      }
      const questionnairePreview = questionnairePreviews.get(assessmentKey(orgId, selectedRef));
      const savedRevision = (selectedRef ? revisions.find((item) => item.assignment_ref === selectedRef) : revisions[0]) || null;
      const currentRevision = questionnairePreview || savedRevision;
      const readiness = currentRevision?.readiness || savedRevision?.readiness || null;
      const currentReadinessMarkup = programConfirmed ? readinessMarkup(selectedRef, readiness) : '';
      const questionnaireLoadState = questionnaireLoadStates.get(organizationKey(orgId));
      const questionnaireLoadMarkup = questionnaireLoadState?.status === 'error'
        ? '<div class="admin-questionnaire-load-state error" role="alert"><span>' +
          escapeHtml(questionnaireLoadState.message) + '</span><button type="button" class="text-button" data-action="retry-questionnaire-load">Повторить</button></div>'
        : questionnaireLoadState?.status === 'loading'
          ? '<div class="admin-questionnaire-load-state" role="status">Загружаем сохранённые анкеты…</div>'
          : questionnaireLoadState?.status === 'empty'
            ? '<div class="admin-questionnaire-load-state">Для этой организации ещё нет сохранённых анкет.</div>' : '';
      const questionnaireValidation = questionnairePreview?.validation_json || {};
      const questionnaireProblems = [...(questionnaireValidation.errors || []),
        ...(questionnaireValidation.missing || [])];
      const activeView = organizationViews.get(orgId) || 'people';
      const availablePrograms = Array.isArray(data?.assessment_programs) ? data.assessment_programs : [];
      const allowedRoles = Array.isArray(currentProgram?.roles) ? currentProgram.roles : [];
      const roleCapabilities = Array.isArray(currentProgram?.role_capabilities)
        ? currentProgram.role_capabilities : allowedRoles.map((role) => ({ ...role, is_available: true }));
      const publishedRevision = revisions.find((item) => item.assignment_ref === selectedRef && item.effective_confirmed);
      const questionnaireAssignment = programConfirmed
        ? questionnaireAssignmentState(questionnaireLoadState, Boolean(publishedRevision))
        : { canAssign: false, label: 'ещё не проверена для программы' };
      if (questionnaireAssignment.canAssign && publishedRevision && (questionnairePreview || currentRevision)?.status !== 'confirmed') {
        questionnaireAssignment.label = 'действует подтверждённая редакция #' +
          publishedRevision.effective_confirmed.id + '; новый черновик ещё не подтверждён';
      }
      const rolesKnown = programConfirmed && Array.isArray(currentProgram?.roles);
      const roleAvailable = rolesKnown && roleCapabilities.some((role) => role.is_available === true && Number(role.version_id) > 0);
      const assignmentRoleLabel = !programConfirmed ? 'ещё не проверена для программы'
        : !rolesKnown ? 'актуальность не проверена'
        : allowedRoles.length ? roleIdentity(allowedRoles) + (roleAvailable ? '' : ' · недоступна') : 'недоступна';
      const assignmentBlockers = [];
      if (!programConfirmed) {
        assignmentBlockers.push(programState.message);
      } else {
        if (currentProgram.assignment_ref !== selectedRef) {
          assignmentBlockers.push('Выбранная оценка не соответствует подключённой программе.');
        }
        if (!questionnaireAssignment.canAssign) assignmentBlockers.push(questionnaireAssignment.blocker);
        if (!rolesKnown) {
          assignmentBlockers.push('Не удалось проверить доступные роли подключённой программы. Проверьте состояние подключения.');
        } else if (!roleAvailable) {
          const reasons = [...new Set(roleCapabilities.map((role) => role.unavailable_reason).filter(Boolean))];
          assignmentBlockers.push(reasons.length
            ? 'Роль в подключённой программе недоступна: ' + reasons.join('; ')
            : 'В подключённой программе нет доступной роли для назначения.');
        }
      }
      const assignmentReadinessMarkup = (isSuperadmin
        ? '<section class="admin-assignment-readiness" aria-label="Готовность назначения"><h5>Готовность назначения</h5>'
        : '<details class="admin-assignment-readiness"' + (assignmentBlockers.length ? ' open' : '') +
          '><summary>Готовность назначения</summary>') + '<dl>' +
        '<dt>Программа</dt><dd>' + (programConnectionUnverified ? 'подключение не подтверждено' : currentProgram
          ? escapeHtml(programIdentity(currentProgram)) + ' · версия ' + escapeHtml(currentProgram.program_version)
          : 'не подключена') + '</dd>' +
        '<dt>Роль в оценке</dt><dd>' + escapeHtml(assignmentRoleLabel) + '</dd>' +
        '<dt>Анкета</dt><dd>' + escapeHtml(questionnaireAssignment.label) + '</dd></dl>' +
        (assignmentBlockers.length
          ? '<div class="form-status error" role="alert"><strong>Назначение пока недоступно</strong><ul>' +
            assignmentBlockers.map((blocker) => '<li>' + escapeHtml(blocker) + '</li>').join('') + '</ul></div>' +
            (programState.status === 'absent' ? '<p data-program-next-step>Следующий шаг: ' +
              (isSuperadmin ? 'подключите опубликованную программу в форме выше.'
                : 'попросите суперадминистратора подключить опубликованную программу к организации.') + '</p>' : '') +
            (programConnectionUnverified || (programConfirmed && !rolesKnown)
              ? '<button type="button" class="text-button" data-action="check-program-connection">Проверить состояние подключения</button>' : '')
          : '<p class="form-status success">Можно назначать. Выберите участников ниже; назначение не запускает оценку.</p>') +
        (isSuperadmin ? '</section>' : '</details>');
      const roleSelectionMarkup = roleCapabilities.length
        ? '<label><span>Роль в оценке</span><select name="role_profile_version_id" required' +
          (rolesKnown ? '' : ' disabled') + '><option value="">Выберите роль</option>' +
          roleCapabilities.map((role) => {
            const selectable = role.is_available === true && Number(role.version_id) > 0;
            return '<option value="' + (selectable ? Number(role.version_id) : '') + '"' +
            (selectable ? '' : ' disabled') + (selectable && allowedRoles.length === 1 ? ' selected' : '') + '>' +
            escapeHtml(role.name || role.code) + (role.is_available ? '' : ' — ' + escapeHtml(role.unavailable_reason || 'Недоступно')) +
            '</option>';
          }).join('') + '</select></label>' : '';
      const assessmentFieldMarkup = programConfirmed
        ? '<section class="admin-assessment-identity" aria-label="Выбранная оценка программы"><strong>' +
          escapeHtml(programIdentity(currentProgram)) + '</strong><dl>' +
          '<dt>Версия программы</dt><dd>' + escapeHtml(currentProgram.program_version) + '</dd>' +
          '<dt>Роль в оценке</dt><dd>' + escapeHtml(assignmentRoleLabel) + '</dd></dl>' +
          '<input name="assignment_ref" type="hidden" value="' + escapeHtml(connectedRef) + '"></section>'
        : '<div class="form-status" role="status" data-questionnaire-program-state="' + programState.status + '">' +
          '<p>' + escapeHtml(programState.message) + '</p>' +
          (programConnectionUnverified ? '<button type="button" class="text-button" data-action="check-program-connection">Проверить состояние подключения</button>' : '') + '</div>';
      const programMarkup = isSuperadmin ? '<form class="admin-organization-inline-form admin-organization-program-form" data-action="connect-assessment-program">' +
        '<label><span>Программа оценки</span><select name="program_definition_id" required>' +
        '<option value="">Выберите опубликованную версию</option>' + availablePrograms.map((program) =>
          '<option value="' + Number(program.id) + '"' +
          (Number(currentProgram?.program_definition_id) === Number(program.id) ? ' selected' : '') + '>' +
          escapeHtml(program.name) + ' · ' + escapeHtml(program.version) + '</option>').join('') +
        '</select></label><button class="ghost-button compact-ghost" type="submit">Подключить</button>' +
        programConnectionStateMarkup(orgId, currentProgram) +
        '</form>' : '';
      const revisionAnswers = currentRevision?.answers_json || {};
      const answer = (questionId, field) => escapeHtml(revisionAnswers?.[questionId]?.[field] || '');
      const confirmedForm = programConfirmed && currentRevision?.status === 'confirmed' &&
        (revisionAnswers.C01?.name ?? org.name) === org.name;
      const organizationName = escapeHtml(currentRevision?.status === 'confirmed'
        ? org.name : revisionAnswers.C01?.name ?? org.name);
      const legacyProfile = String(org.profile || '').trim();
      const currentActivityDescription = String(revisionAnswers?.C01?.activity_description || '').trim();
      const legacyProfileMarkup = !legacyProfile ? '' :
        '<aside class="admin-organization-legacy-profile" role="note"><strong>Сохранённое описание из прежней карточки</strong>' +
        '<p>' + escapeHtml(legacyProfile) + '</p>' +
        (currentActivityDescription
          ? '<p class="admin-organization-legacy-profile-note">В текущем черновике C01 уже есть описание деятельности. Старое значение оставлено только для сверки и не перезаписывает подтверждённые сведения.</p>'
          : '<button type="button" class="ghost-button compact-ghost" data-action="use-legacy-profile">Перенести в описание деятельности</button>') +
        '</aside>';
      const viewButton = (view, label) => '<button type="button" class="admin-organization-step' +
        (activeView === view ? ' current' : '') + '" data-action="show-admin-view" data-view="' + view +
        '" aria-pressed="' + String(activeView === view) + '">' + label + '</button>';
      const key = assessmentKey(orgId, selectedRef);
      const previewIsStale = !programConfirmed || staleQuestionnairePreviews.has(key);
      let confirmationOutcome = questionnaireConfirmOutcomes.get(key);
      if (!confirmationOutcome && state.currentScreen === 'admin-organizations' && activeView === 'organization-data' &&
          programConfirmed && currentIdentityKey() &&
          !questionnaireLoadState?.accessDenied && !questionnaireConfirmRequestsInFlight.has(key)) {
        const revisionId = Number(readQuestionnaireOperation(confirmationStorageKey(key)));
        if (Number.isSafeInteger(revisionId) && revisionId > 0) {
          confirmationOutcome = {
            revisionId, assignmentRef: selectedRef, status: 'unknown', restored: true,
            message: 'Проверьте, сохранилась ли эта редакция.',
          };
          questionnaireConfirmOutcomes.set(key, confirmationOutcome);
          confirmationToRestore = { organizationId: orgId, revisionId, assessmentRef: selectedRef };
        }
      }
      const requiresReadback = confirmationNeedsReadback(confirmationOutcome);
      const savedChoiceError = (currentRevision?.validation_json?.errors || []).find(
        (error) => error.code === 'CONTEXT_CHOICE_UNSUPPORTED' ||
          String(error.code).startsWith('ADMIN_CONTEXT_CHOICES_') ||
          String(error.code).startsWith('QUESTIONNAIRE_LEGACY_CHOICES_'));
      const savedChoiceIssue = savedChoiceError
        ? (savedChoiceError.code === 'CONTEXT_CHOICE_UNSUPPORTED'
          ? 'неподдерживаемое значение: ' + (savedChoiceError.field === 'case_reality_level'
            ? 'близость ситуаций к реальной работе' : 'использование названия организации')
          : 'не удалось проверить утверждённые варианты; повторите после восстановления правил')
        : '';
      const savedChoiceWarning = savedChoiceIssue && !questionnairePreview
        ? '<p class="form-status error" role="alert" data-context-choice-warning>Проверьте: ' +
          escapeHtml(savedChoiceIssue) + '.</p>' : '';
      const revisionAttribution = (revision) => '<p class="admin-questionnaire-uploader" data-questionnaire-revision-id="' +
        Number(revision.id) + '">Внёс данные: ' + escapeHtml(revision.uploaded_by_name || revision.uploaded_by_email ||
          (Number(revision.uploaded_by_user_id) > 0 ? 'аккаунт #' + Number(revision.uploaded_by_user_id) : 'сведения не сохранены')) + '</p>';
      const resultCheck = requiresReadback || confirmationOutcome?.status === 'refresh_failed'
        ? '<div class="admin-data-confirmation-recovery" role="status">' +
          (confirmationOutcome.status === 'unknown' ? '<strong>Итог подтверждения неизвестен</strong>' : '') +
          '<p>' + escapeHtml(confirmationOutcome.message || 'Не удалось обновить готовность оценки.') + '</p>' +
          '<button type="button" class="ghost-button compact-ghost" data-action="check-questionnaire-confirmation" data-value="' +
          Number(confirmationOutcome.revisionId) + '">Проверить результат</button></div>' : '';
      const participant = questionnairePreview?.participant_preview || {};
      const fieldLabels = { organization_name: 'Организация', organization_type: 'Тип организации',
        industry: 'Сфера деятельности', activity_description: 'Описание деятельности', purpose: 'Цель оценки',
        results_usage: 'Использование результатов' };
      const validationLabels = { C01: 'сведения об организации', C02a: 'цель оценки', C03: 'использование результатов',
        C17: 'правила кейсов' };
      const changes = Array.isArray(questionnairePreview?.changes) ? questionnairePreview.changes : [];
      const changesMarkup = questionnairePreview?.is_first_publication
        ? '<p><strong>Пока нет подтверждённых сведений.</strong> Эта редакция станет текущей после подтверждения.</p>'
        : (changes.length ? '<ul>' + changes.map((change) => '<li><strong>' +
          escapeHtml(fieldLabels[change.field] || change.field) + ':</strong> «' + escapeHtml(change.before || 'не указано') +
          '» → «' + escapeHtml(change.after || 'не указано') + '»</li>').join('') + '</ul>' :
          '<p>Изменений относительно текущей подтверждённой редакции нет.</p>');
      const choiceLabels = { case_reality_level: 'близость ситуаций к реальной работе',
        organization_name_usage_rules: 'использование названия организации' };
      const humanProblems = questionnaireProblems.map((item) => {
        if (item?.code === 'CONTEXT_CHOICE_UNSUPPORTED')
          return 'неподдерживаемое значение: ' + (choiceLabels[item.field] || 'правила кейсов');
        const code = typeof item === 'string' ? item : item?.code;
        if (String(code).startsWith('ADMIN_CONTEXT_CHOICES_') ||
            String(code).startsWith('QUESTIONNAIRE_LEGACY_CHOICES_'))
          return 'не удалось проверить утверждённые варианты; повторите после восстановления правил';
        return validationLabels[code] ||
          (String(code).includes('duplicate') ? 'повторяющиеся поля' : 'некорректно заполненные поля');
      });
      const csvPreview = questionnairePreview?.channel === 'csv';
      const proposedName = participant.organization_name || questionnairePreview?.answers_json?.C01?.name;
      const expectedName = questionnairePreview?.expected_organization_name ?? org.name;
      const nameMismatch = proposedName && proposedName !== expectedName;
      const readyForConfirmation = questionnairePreview?.status === 'ready_for_confirmation';
      const previewMarkup = questionnairePreview ? '<div class="admin-questionnaire-preview" data-draft-action="questionnaire-preview" data-assessment-ref="' +
        escapeHtml(selectedRef) + '" data-preview-action="' + (csvPreview ? 'preview-questionnaire' : 'preview-early-data') +
        '" data-questionnaire-revision-id="' + Number(questionnairePreview.id) + '">' +
        '<p class="form-status error" data-preview-stale' + (previewIsStale ? '' : ' hidden') +
        '>' + (csvPreview ? 'Данные изменились. ' +
          '<button type="button" class="text-button" data-action="refresh-questionnaire-preview">Загрузить файл повторно</button>'
          : 'Форма изменилась после проверки. Подтвердите текущие сведения.') + '</p>' +
        (humanProblems.length ? '<p class="form-status error" role="alert">Проверьте: ' +
          escapeHtml([...new Set(humanProblems)].join(', ')) + '.</p>' : '') +
        (readyForConfirmation && nameMismatch ? '<p data-organization-rename>Название изменится с «' + escapeHtml(expectedName) +
          '» на «' + escapeHtml(proposedName) + '». Подтвердите переименование организации.</p>' : '') +
        (csvPreview ? '<details><summary>Сведения из загруженной анкеты</summary>' +
          revisionAttribution(questionnairePreview) + '<dl>' +
          Object.entries(fieldLabels).filter(([field]) => participant[field]).map(([field, label]) =>
            '<dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(participant[field]) + '</dd>').join('') +
          '</dl>' + changesMarkup + '</details>' : '') +
        (readyForConfirmation ? '<button type="button" class="primary-button compact-primary" data-action="confirm-questionnaire" data-value="' +
          Number(questionnairePreview.id) + '">Подтвердить сведения</button>' : '') + '</div>' : '';
      const sourceRevision = publishedRevision || savedRevision;
      const sourceMarkup = sourceRevision ? revisionAttribution(sourceRevision) : '';
      const confirmationMarkup = '<div class="admin-questionnaire-confirmation">' +
        (publishedRevision ? '<p data-previous-organization-revision hidden>Действуют ранее подтверждённые сведения, пока вы не подтвердите изменения.</p>' : '') +
        '<p data-organization-confirmed role="status" tabindex="-1" hidden>Сведения подтверждены</p>' +
        resultCheck + savedChoiceWarning + previewMarkup +
        '<button class="primary-button compact-primary" type="submit" data-early-data-submit>Подтвердить сведения</button></div>';
      const tabsMarkup = '<nav class="admin-organization-steps" aria-label="Разделы управления">' +
        viewButton('people', 'Участники оценки') +
        viewButton('organization-data', 'Данные организации') +
        viewButton('questionnaire', 'Анкета') + '</nav>';
      const reportsLink = isActive ? '<button type="button" class="text-button admin-organization-reports-link" data-action="open-organization-reports" data-program-definition-id="' +
        (reportProgram ? Number(reportProgram.program_definition_id) : '') + '" data-program-label="' +
        escapeHtml(reportProgram ? [reportProgram.program_name, reportProgram.program_version].filter(Boolean).join(' · ') : '') +
        '">Отчёты организации</button>' : '';
      const programLine = programConnectionUnverified ? 'Подключение не подтверждено' : currentProgram
        ? escapeHtml(programIdentity(currentProgram)) + ' · версия ' + escapeHtml(currentProgram.program_version)
        : 'Не подключена';
      const appealsFilter = '<button type="button" class="ghost-button compact-ghost" data-action="toggle-appeals-filter" aria-pressed="' +
        appealsOnly + '">С обращениями</button>';
      const participantTools = '<div class="admin-organization-selection"><label><input type="checkbox" name="select_all_participants"> Выбрать всех</label><strong aria-live="polite"><span data-selected-count>0</span> выбрано</strong></div>' +
        '<div class="admin-organization-bulk-actions" data-bulk-actions hidden><form class="admin-organization-bulk-invitation-form" data-action="send-member-invitations"><button class="primary-button compact-primary" type="submit">Отправить приглашения</button></form>' +
        '<form class="admin-organization-bulk-assignment-form" data-action="assign-member-assessment">' + roleSelectionMarkup + '<button class="primary-button compact-primary" type="submit"' +
        (assignmentBlockers.length ? ' disabled' : '') + '>Назначить оценку</button></form></div>';
      const members = renderInvitationFeedback(orgId, selectedRef, org.members || []) + renderMemberList(org.members || [], {
        appealsOnly,
        organizationId: orgId,
        isSuperadmin,
        activeOrganization: isActive,
        canAssign: isActive && !assignmentBlockers.length,
        canDeletePerson: purgePreviewAvailable,
        selectedAssessmentRef: selectedRef,
        selectedAssessmentLabel: currentProgram
          ? programIdentity(currentProgram) + ' · ' + roleIdentity(allowedRoles)
          : 'выбранная оценка',
      });
      const addMemberForm = '<form class="admin-organization-member-form" data-action="add-member">' +
        '<h4>Добавить участника</h4>' +
        (isSuperadmin ? '<p>Для добавления нужны email, ФИО и должность.</p>' : '') +
        '<label><span>Email</span><input name="email" type="email" placeholder="user@company.ru" required></label>' +
        '<label><span>ФИО</span><input name="full_name" type="text" placeholder="Иван Иванов" required></label>' +
        '<label><span>Должность</span><input name="role_description" type="text" placeholder="Руководитель отдела" required></label>' +
        '<button class="primary-button compact-primary" type="submit">Добавить</button>' +
        '</form>';
      const importMembersForm = '<form class="admin-organization-import-form" data-action="import-members">' +
        '<input name="csv" type="file" aria-label="Файл списка участников" accept=".csv,text/csv">' +
        '<span>CSV: email, full_name, role_description, job_instructions</span>' +
        '<button class="ghost-button compact-ghost" type="submit">Импорт</button>' +
        '</form>';

      return (
        '<article class="card card--inset admin-organization-card" data-organization-id="' +
        orgId +
        '" data-organization-code="' + escapeHtml(org.code) +
        '" data-organization-active="' +
        (isActive ? 'true' : 'false') +
        '">' +
        (isSuperadmin ? '<div class="admin-organization-head">' +
        '<div><p class="section-label accent-label">' +
        escapeHtml(org.code) +
        '</p><h3>' +
        escapeHtml(org.name) +
        '</h3><p class="admin-organization-state">' +
        (isActive ? 'Активна' : 'Деактивирована') +
        '</p></div>' +
        '<div class="admin-organization-stats"><span>' +
        Number(org.members_count || 0) +
        ' участников</span><span>' +
        Number(org.reports_count || 0) +
        ' отчетов</span>' + (isSuperadmin ? '<button class="ghost-button compact-ghost" type="button" data-action="prepare-organization-assessments"' +
        (batchIsRunning || !isActive ? ' disabled' : '') +
        '>Подготовить кейсы всем</button>' +
        (isActive
          ? '<button class="ghost-button compact-ghost danger" type="button" data-action="delete-organization">Деактивировать</button>'
          : '<button class="ghost-button compact-ghost" type="button" data-action="restore-organization">Восстановить</button>') +
        (purgePreviewAvailable
          ? '<button class="ghost-button compact-ghost danger" type="button" data-action="purge-organization" data-execution-available="' +
            String(physicalPurgeAvailable) + '">Удалить полностью</button>' : '') : '') + '</div>' +
        '</div>' : tabsMarkup + (activeView === 'organization-data' ? '' :
          '<section class="admin-organization-head" aria-label="Выбранная оценка">' +
          '<div><h3>' + escapeHtml(org.name) + '</h3><p><strong>Программа</strong> · ' + programLine + '</p></div>' +
          reportsLink + '</section>')) +
        renderOrganizationBatchProgress(orgId) +
        programMarkup +
        (isSuperadmin ? '<form class="admin-organization-profile-form" data-action="update-profile">' +
        '<div class="admin-organization-profile-heading"><div><p class="section-label accent-label">Профиль</p><h4>Сведения об организации</h4></div>' +
        '<button class="primary-button compact-primary" type="submit">Сохранить карточку</button></div>' +
        '<label><span>Название</span><input name="name" value="' + escapeHtml(org.name) + '" required></label>' +
        '<label><span>Код</span><input name="code" value="' + escapeHtml(org.code) + '" required></label>' +
        '<label><span>Год основания</span><input name="founded_year" type="number" min="1000" max="2100" value="' + escapeHtml(org.founded_year ?? '') + '" placeholder="Например, 2012"></label>' +
        '<label><span>Численность</span><input name="employee_count" type="number" min="0" value="' + escapeHtml(org.employee_count ?? '') + '" placeholder="Количество сотрудников"></label>' +
        '<label><span>Отрасль</span><input name="industry" type="text" value="' + escapeHtml(org.industry || '') + '" placeholder="Например, финтех"></label>' +
        '<label><span>Сайт</span><input name="website" type="url" value="' + escapeHtml(org.website || '') + '" placeholder="https://company.ru"></label>' +
        '<label><span>Штаб-квартира</span><input name="headquarters" type="text" value="' + escapeHtml(org.headquarters || '') + '" placeholder="Город, страна"></label>' +
        '<label class="admin-organization-profile-wide"><span>Прочая существенная информация</span><textarea name="notes" placeholder="Структура, география, культура и другие важные сведения">' + escapeHtml(org.notes || '') + '</textarea></label>' +
        '</form>' : '') +
        (isSuperadmin ? '<div class="admin-organization-columns"><section><h4>Домены</h4>' +
        renderOrganizationDomains(org.domains || []) +
        '<form class="admin-organization-inline-form" data-action="add-domain"><input type="text" placeholder="company.ru">' +
        '<button class="ghost-button compact-ghost" type="submit">Добавить</button></form></section></div>' +
        renderOrganizationAdmins(org, purgePreviewAvailable) : '') +
        (isSuperadmin ? tabsMarkup : '') +
        '<section class="admin-organization-members-section' + (activeView === 'people' ? '' : ' hidden') + '" data-admin-view="people">' +
        (isSuperadmin
          ? '<h4>Участники оценки</h4>' + appealsFilter + '<dl class="admin-people-context"><div><dt>Программа оценки</dt><dd>' +
            programLine + '</dd></div><div><dt>Роль в оценке</dt><dd>' + escapeHtml(assignmentRoleLabel) + '</dd></div></dl>' +
            '<p>Назначение не запускает оценку.</p>' + assignmentReadinessMarkup + participantTools + members + addMemberForm + importMembersForm
          : '<section class="admin-people-list" aria-labelledby="admin-people-title-' + orgId + '"><div class="admin-people-list-heading">' +
            '<h4 id="admin-people-title-' + orgId + '">Участники</h4>' + appealsFilter + '</div>' +
            assignmentReadinessMarkup + participantTools + members + '</section>' +
            '<aside class="admin-people-add">' + addMemberForm + importMembersForm + '</aside>') +
        '</section>' +
        '<section class="admin-organization-members-section' + (activeView === 'organization-data' ? '' : ' hidden') +
        '" data-admin-view="organization-data">' + (questionnaireLoadState?.status === 'empty' ? '' : questionnaireLoadMarkup) +
        '<div class="admin-data-overview">' + organizationDataReadiness(programState, readiness, assignmentRoleLabel, sourceMarkup) +
        (!isSuperadmin && activeView === 'organization-data' ? reportsLink : '') + '</div>' +
        '<div class="admin-organization-data-layout"><form class="admin-organization-early-data-form" data-action="preview-early-data" data-assessment-ref="' +
        escapeHtml(selectedRef) + '"' + (confirmedForm ? ' data-confirmed-form' : '') +
        (!programConfirmed || questionnaireLoadState?.accessDenied ? ' data-confirmation-unavailable' : '') + '>' +
        (programConfirmed ? '<input name="assignment_ref" type="hidden" value="' + escapeHtml(connectedRef) + '">' : '') +
        '<fieldset class="admin-questionnaire-field-group"><legend>Об организации</legend>' +
        '<label class="admin-organization-profile-wide"><span>Название организации</span><input name="organization_name" value="' + organizationName + '" required></label>' +
        '<label><span>Тип организации</span><input name="organization_type" value="' + answer('C01', 'organization_type') + '"></label>' +
        '<label><span>Сфера деятельности</span><input name="industry" value="' + answer('C01', 'industry') + '"></label>' +
        '<label class="admin-organization-profile-wide"><span>Описание деятельности</span><textarea name="activity_description">' + answer('C01', 'activity_description') + '</textarea></label>' +
        legacyProfileMarkup + '</fieldset>' +
        '<fieldset class="admin-questionnaire-field-group admin-data-text-fields"><legend>Сведения для знакомства</legend>' +
        '<label><span>Зачем проводится оценка</span><textarea name="purpose">' + answer('C02a', 'participant_text') + '</textarea></label>' +
        '<label><span>Как будут использоваться результаты</span><textarea name="results_usage">' + answer('C03', 'participant_text') + '</textarea></label></fieldset>' +
        '<fieldset class="admin-questionnaire-field-group admin-data-text-fields"><legend>Настройки контекста для ситуаций</legend>' +
        '<label><span>Близость ситуаций к реальной работе</span>' + contextChoiceSelect('case_reality_level', revisionAnswers?.C17?.case_reality_level) + '</label>' +
        '<label><span>Название организации в ситуациях</span>' + contextChoiceSelect('organization_name_usage_rules', revisionAnswers?.C17?.organization_name_usage_rules) + '</label></fieldset>' +
        confirmationMarkup + '</form>' + participantPreviewMarkup + '</div></section>' +
        '<section class="admin-organization-members-section' + (activeView === 'questionnaire' ? '' : ' hidden') + '" data-admin-view="questionnaire">' + questionnaireLoadMarkup + currentReadinessMarkup + '<h4>Корпоративная анкета</h4>' +
        '<form class="admin-organization-import-form" data-action="preview-questionnaire" data-assessment-ref="' + escapeHtml(selectedRef) + '">' +
        assessmentFieldMarkup +
        '<input name="csv" type="file" accept=".csv,text/csv" required>' +
        '<button class="primary-button compact-primary" type="submit"' + (programConfirmed ? '' : ' disabled') + '>Загрузить заполненную анкету</button></form>' +
        '<p><a class="text-link" href="/users/admin/organizations/' + orgId + '/questionnaire/template">Скачать шаблон</a></p>' +
        (questionnairePreview?.channel === 'csv' ? '<p class="form-status success" role="status">Анкета загружена. Подтвердите сведения в «Данных организации».</p>' : '') +
        '</section>' +
        '</article>'
      );
    })
    .join('');
  for (const freshRoot of adminOrganizationsList.querySelectorAll('[data-preparation-status]')) {
    const previousRoot = preparationRoots.get(freshRoot.dataset.preparationReferenceId);
    if (previousRoot) freshRoot.replaceWith(previousRoot);
  }
  for (const organization of organizations) for (const member of organization.members || []) {
    for (const stage of Object.values(member.assessment_stages || {})) {
      const model = stage.preparation;
      if (model) for (const root of adminOrganizationsList.querySelectorAll('[data-preparation-status]')) {
        if (root.dataset.preparationReferenceId === model.reference) renderPreparation(root, model, { readError: organizationsReadStale });
      }
    }
  }
  restoreAdminOrganizationsDraft();
  restoreProgramConnectionFeedback();
  updateOrganizationDataForm(organizationDataForm(selectedOrganizationId));
  if (menuFocus) restoreMemberMenuFocus(menuFocus);
  else if (focusedConfirmation) organizationDataForm(selectedOrganizationId)
    ?.querySelector('[data-organization-confirmed]:not([hidden])')?.focus({ preventScroll: true });
  else if (focusedPreparationControl?.isConnected) focusedPreparationControl.focus({ preventScroll: true });
  else if (focusedCheckUser) adminOrganizationsList.querySelector('[data-user-id="' + CSS.escape(focusedCheckUser) + '"]')?.closest('.admin-organization-member')?.querySelector('[data-action="check-member-preparation"]')?.focus({ preventScroll: true });
  adminOrganizationsList.querySelectorAll('form[data-action], .admin-questionnaire-preview')
    .forEach((form) => renderedFormSignatures.set(form, formSignature(form)));
  if (state.currentScreen === 'admin-organizations' && window.history.state?.screen === 'admin-organizations') {
    window.history.replaceState({ ...window.history.state, managementNavigation: managementNavigation() }, '');
  }
  if (confirmationToRestore && organizationDataIsVisible(confirmationToRestore.organizationId, confirmationToRestore.assessmentRef)) {
    void checkAdminOrganizationConfirmation(confirmationToRestore.organizationId, confirmationToRestore.revisionId);
  }
};

export const toggleAppealsFilter = () => {
  appealsOnly = !appealsOnly;
  renderAdminOrganizations();
};

export const saveAdminOrganizationsNavigation = () => {
  captureAdminOrganizationsDraft();
  saveManagementSelection();
  return managementNavigation();
};

export const openAdminOrganizations = async ({
  preserveView = false, navigation = preserveView ? window.history.state?.managementNavigation : null,
} = {}) => {
  assignmentViewGeneration += 1;
  restoreManagementSelection();
  if (!preserveView) organizationViews.clear();
  restoreManagementNavigation(navigation);
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  state.activeArea = 'management';
  state.isAdmin = Boolean(state.canAdmin || state.isAdmin);
  setCurrentScreen('admin-organizations');
  persistAssessmentContext();
  syncUrlState('admin-organizations');
  hideAllPanels();
  adminOrganizationsPanel?.classList.remove('hidden');
  setStatus('');
  adminOrganizationsList.innerHTML = '<p class="report-empty-state">Загружаем организации...</p>';
  try {
    const data = await loadAdminOrganizations();
    if (!data || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
  } catch (error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    adminOrganizationsList.innerHTML = '<p class="report-empty-state">' + escapeHtml(error.message) + '</p>';
    return;
  }
  renderAdminOrganizations();
};

export const openPlatformAvailability = (section) => {
  if (!state.adminDashboard?.is_superadmin || !['problems', 'checks'].includes(section)) {
    window.history.replaceState({}, '', '/?screen=admin-organizations');
    return openAdminOrganizations();
  }
  const content = section === 'problems'
    ? ['Проблемы', 'Раздел проблем будет доступен после подключения проверенного источника технических случаев.']
    : ['Проверки', 'Контролируемые проверки будут доступны после подключения изолированного исполнителя.'];
  state.activeArea = 'management';
  state.isAdmin = true;
  setCurrentScreen('admin-platform-' + section);
  persistAssessmentContext();
  hideAllPanels();
  adminOrganizationsPanel.dataset.superadmin = 'true';
  adminOrganizationsPanel.classList.remove('hidden');
  adminOrganizationsPanel.querySelector('.admin-organizations-shell')?.classList.add('hidden');
  const availability = document.getElementById('platform-availability');
  availability.classList.remove('hidden');
  document.getElementById('platform-availability-title').textContent = content[0];
  document.getElementById('platform-availability-description').textContent = content[1];
  const accountName = document.getElementById('admin-organizations-account-name');
  if (accountName) accountName.textContent = state.pendingUser?.full_name || state.pendingUser?.email || 'Аккаунт';
  document.querySelectorAll('[data-platform-section]').forEach((link) => {
    if (link.dataset.platformSection === section) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
};
