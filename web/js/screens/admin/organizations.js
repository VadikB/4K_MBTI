import { createOperationId, readApiResponse, fetchWithDeadline as fetch } from '../../api.js';
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
import { createAdminOrganizationDraftKey } from './organization-draft-key.js';

let selectedOrganizationId = null;
const invitationRequestsInFlight = new Set();
const invitationOperationIds = new Map();
const assignmentSourceRequests = new Set();
const assignmentOperationIds = new Map();
const questionnairePreviews = new Map();
const questionnaireRevisions = new Map();
const staleQuestionnairePreviews = new Set();
const questionnairePreviewRequestGenerations = new Map();
const organizationViews = new Map();
const managementDrafts = new Map();
const selectedAssessmentRefs = new Map();
const questionnaireConfirmRequestGenerations = new Map();
const questionnaireConfirmRequestsInFlight = new Set();
const questionnaireLoadStates = new Map();
const questionnaireConfirmOutcomes = new Map();
let operationAnchor = null;
let restoredManagementIdentity = null;

const currentIdentityKey = () => String(state.pendingUser?.id || '');
const organizationKey = (organizationId) => currentIdentityKey() + ':' + Number(organizationId);
const assessmentKey = (organizationId, assessmentRef = '') =>
  organizationKey(organizationId) + ':' + String(assessmentRef || '').trim();
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
      if (['people', 'organization-data', 'questionnaire'].includes(view)) organizationViews.set(Number(id), view);
    }
    for (const [key, ref] of saved.assessments || []) {
      if (String(key).startsWith(currentIdentityKey() + ':') && typeof ref === 'string') selectedAssessmentRefs.set(key, ref);
    }
  } catch { /* Invalid local navigation is ignored; the server still controls access. */ }
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
const questionnaireErrorMessage = (error, fallback) => {
  const message = String(error?.message || '');
  if (message.includes('QUESTIONNAIRE_REVISION_CONFLICT')) return 'Эта редакция устарела: уже подтверждена более новая. Обновите предпросмотр.';
  if (message.includes('QUESTIONNAIRE_NOT_READY_FOR_CONFIRMATION')) return 'Анкета ещё не готова к подтверждению. Исправьте обязательные поля.';
  if (message.includes('QUESTIONNAIRE_RECIPIENTS_CONFLICT')) return 'Проверьте выбранных получателей результатов.';
  if (message.includes('REPORT_RECIPIENT_SCOPE_CONFLICT')) return 'Один из выбранных получателей больше не имеет доступа к организации.';
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
  if (error?.status === 401) return 'Сессия истекла. Войдите снова; введённые данные формы сохранены в этой вкладке.';
  if (error?.name === 'RequestDeadlineError') return 'Не удалось подтвердить результат операции. Обновите список перед безопасным повтором.';
  if (error instanceof TypeError) return 'Не удалось связаться с сервером. Проверьте соединение.';
  if (Number(error?.status) >= 500) return 'Не удалось добавить пользователя. Произошла ошибка сервиса.';
  return message || fallback;
};

const transferErrorMessage = (error) => {
  const message = String(error?.message || '');
  const labels = {
    ORGANIZATION_TRANSFER_LAST_ADMIN: 'Нельзя перенести последнего администратора организации. Сначала назначьте другого администратора.',
    ORGANIZATION_TRANSFER_ACTIVE_ACQUAINTANCE: 'Перенос заблокирован: участник проходит знакомство с оценкой.',
    ORGANIZATION_TRANSFER_SOURCE_CHANGED: 'Состав организации изменился. Обновите список и повторите перенос.',
    ORGANIZATION_TRANSFER_TARGET_INACTIVE: 'Целевая организация неактивна.',
    ORGANIZATION_TRANSFER_TARGET_NOT_FOUND: 'Целевая организация не найдена.',
  };
  const code = Object.keys(labels).find((item) => message.includes(item));
  return code ? labels[code] : membershipErrorMessage(error, 'Не удалось перенести участника.');
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
  managementDrafts.set(formDraftKey(organizationId, form, storageRef), {
    fields: Object.fromEntries(fields.map((field) => [field.name + ':' + field.value,
      { name: field.name, value: field === assignmentField && (assessmentOverride !== null || changedActiveScope)
        ? storageRef : field.value, checked: field.checked, type: field.type }])),
    focusedName: form.contains(document.activeElement) ? document.activeElement?.name || null : null,
  });
};

const captureParticipantSelection = (organizationId, card) => {
  const fields = [...card.querySelectorAll('input[name="invitation_email"]')];
  managementDrafts.set(organizationKey(organizationId) + ':participant-selection:organization', {
    fields: Object.fromEntries(fields.map((field) => [field.value, { value: field.value, checked: field.checked }])),
  });
};

export const captureAdminOrganizationsDraft = () => {
  if (adminOrganizationsPanel.classList.contains('hidden')) return;
  adminOrganizationsList.querySelectorAll('[data-organization-id]').forEach((card) => {
    const organizationId = Number(card.getAttribute('data-organization-id'));
    card.querySelectorAll('form[data-action]').forEach((form) => captureFormDraft(organizationId, form));
    captureParticipantSelection(organizationId, card);
    const preview = card.querySelector('.admin-questionnaire-preview');
    if (preview) captureFormDraft(organizationId, preview);
  });
};

const restoreFormDraft = (organizationId, form) => {
  const selectedRef = selectedAssessmentRefs.get(organizationKey(organizationId));
  const assignmentField = form.querySelector('[name="assignment_ref"]');
  if (assignmentField && selectedRef) assignmentField.value = selectedRef;
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
  form.querySelector('[name="' + CSS.escape(draft.focusedName || '') + '"]')?.focus({ preventScroll: true });
  return true;
};

const restoreConfirmedRevisionForm = (form, revision) => {
  if (!form || !revision) return false;
  const sourceAuthor = form.querySelector('[name="source_author"]');
  if (sourceAuthor && revision.source_author) sourceAuthor.value = String(revision.source_author);
  if (form.dataset.action !== 'preview-early-data') return Boolean(sourceAuthor?.value);
  const answers = revision.answers_json || {};
  const values = {
    organization_name: answers.C01?.name,
    organization_type: answers.C01?.organization_type,
    industry: answers.C01?.industry,
    activity_description: answers.C01?.activity_description,
    purpose: answers.C02a?.participant_text,
    results_usage: answers.C03?.participant_text,
    result_recipients: answers.C04?.answer,
    organizer: answers.C21?.organizer,
    responsible_contact: answers.C21?.responsible_contact,
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
    const selection = managementDrafts.get(organizationKey(organizationId) + ':participant-selection:organization');
    card.querySelectorAll('input[name="invitation_email"]').forEach((field) => {
      if (selection?.fields?.[field.value]) field.checked = selection.fields[field.value].checked;
    });
    card.querySelectorAll('.admin-questionnaire-preview').forEach((preview) =>
      updateAdminOrganizationQuestionnaireRecipients(organizationId, preview));
  });
};

const clearAdminOrganizationsSessionState = () => {
  selectedOrganizationId = null;
  invitationRequestsInFlight.clear();
  invitationOperationIds.clear();
  assignmentSourceRequests.clear();
  assignmentOperationIds.clear();
  questionnairePreviews.clear();
  questionnaireRevisions.clear();
  staleQuestionnairePreviews.clear();
  questionnairePreviewRequestGenerations.clear();
  organizationViews.clear();
  managementDrafts.clear();
  selectedAssessmentRefs.clear();
  questionnaireConfirmRequestGenerations.clear();
  questionnaireConfirmRequestsInFlight.clear();
  questionnaireLoadStates.clear();
  questionnaireConfirmOutcomes.clear();
  operationAnchor = null;
  restoredManagementIdentity = null;
};

window.addEventListener('agent4k:assessment-context-cleared', clearAdminOrganizationsSessionState);

const clearInaccessibleOrganizationState = (organizations) => {
  const allowed = new Set(organizations.map((org) => organizationKey(org.id)));
  for (const drafts of [managementDrafts, selectedAssessmentRefs, questionnairePreviews, questionnaireRevisions,
    questionnairePreviewRequestGenerations]) {
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
};

const escapeHtml = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

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
    (selectedRef ? 'Готовность выбранной оценки «' + escapeHtml(selectedRef) + '» ещё не рассчитана' : 'Выберите оценку') +
    '</strong><p>' + (selectedRef
      ? 'Сохраните сведения или загрузите анкету, чтобы увидеть готовность этой оценки.'
      : 'Укажите оценку в форме ниже, чтобы начать подготовку.') + '</p></div>'
  : '<div class="admin-readiness-panel" data-readiness-status="' +
  escapeHtml(readiness?.status || 'unavailable') + '"><strong>Готовность выбранной оценки' +
  (selectedRef ? ' «' + escapeHtml(selectedRef) + '»' : '') + '</strong><ul>' +
  readinessRow('Ранние сведения', readiness?.early, 'organization-data') +
  readinessRow('Контекст', readiness?.context, 'organization-data') +
  readinessRow('Участники', readiness?.roles, readiness?.roles?.action_view || null) +
  readinessRow('Подготовка', readiness?.preparation, null) + '</ul>' +
  '<p>Добавлять участников можно до заполнения анкеты. Приглашение, назначение и начало оценки проверяются сервером отдельно.</p></div>';

const operationRoot = () => {
  if (!operationAnchor || operationAnchor.identity !== currentIdentityKey()) return null;
  const card = adminOrganizationsList.querySelector('[data-organization-id="' + operationAnchor.organizationId + '"]');
  return card?.querySelector(operationAnchor.selector) || card?.querySelector('.admin-questionnaire-confirmation') || null;
};

const setStatus = (message, tone = 'muted') => {
  if (!adminOrganizationsStatus) {
    return;
  }
  adminOrganizationsStatus.textContent = message || '';
  adminOrganizationsStatus.classList.toggle('hidden', !message);
  adminOrganizationsStatus.dataset.tone = tone;
  let local = operationRoot()?.querySelector('[data-operation-status]');
  if (!local && operationRoot()) {
    local = document.createElement('p');
    local.className = 'admin-organizations-status';
    local.dataset.operationStatus = '';
    local.setAttribute('aria-live', 'polite');
    local.setAttribute('role', 'status');
    local.tabIndex = -1;
    operationRoot().append(local);
  }
  if (local) {
    local.textContent = message || '';
    local.dataset.tone = tone;
    local.classList.toggle('hidden', !message);
  }
  adminOrganizationsStatus.classList.toggle('hidden', !message || Boolean(local));
  if (message && tone !== 'loading' && !adminOrganizationsPanel.classList.contains('hidden')) {
    const target = local || adminOrganizationsStatus;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: 'nearest' });
  }
};

// Remember the action by stable DOM attributes: mutations re-render the card.
const trackOperation = (event) => {
  const target = event.target instanceof Element ? event.target : null;
  const form = event.type === 'submit' ? target?.closest('form[data-action]') : null;
  const button = event.type === 'click' ? target?.closest('button[data-action]') : null;
  if (!form && (!button || ['show-admin-view', 'refresh-questionnaire-preview', 'use-legacy-profile'].includes(button.dataset.action))) return;
  const root = form || button.closest('.admin-questionnaire-preview') || button.parentElement;
  const card = root?.closest('[data-organization-id]');
  if (!card) return;
  const selector = form ? 'form[data-action="' + CSS.escape(form.dataset.action) + '"]'
    : root.matches('.admin-questionnaire-preview')
      ? '.admin-questionnaire-preview[data-questionnaire-revision-id="' + root.dataset.questionnaireRevisionId + '"]'
      : '[data-admin-view="' + CSS.escape(root.closest('[data-admin-view]')?.dataset.adminView || 'people') + '"]';
  operationAnchor = { identity: currentIdentityKey(), organizationId: Number(card.dataset.organizationId), selector };
  setStatus('Выполняем действие…', 'loading');
};
adminOrganizationsPanel?.addEventListener('submit', trackOperation, true);
adminOrganizationsPanel?.addEventListener('click', trackOperation, true);

const requestOrganizations = async (url, options, fallbackMessage) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });
  const data = await readApiResponse(response, fallbackMessage);
  if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  state.adminOrganizations = data;
  persistAssessmentContext();
  renderAdminOrganizations();
  return data;
};

const requestOrganizationsImport = async (url, csvText) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_text: csvText }),
  });
  const data = await readApiResponse(response, 'Не удалось импортировать участников.');
  if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  state.adminOrganizations = data.organizations || data;
  persistAssessmentContext();
  renderAdminOrganizations();
  return data;
};

export const loadAdminOrganizations = async () => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const data = await requestOrganizations(
    '/users/admin/organizations',
    { method: 'GET', headers: {} },
    'Не удалось загрузить организации.',
  );
  if (!data || state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  await Promise.all((data.items || []).map((org) => loadQuestionnaireRevisions(
    org.id, { identityEpoch, identityKey, render: false },
  )));
  if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
  renderAdminOrganizations();
  return data;
};

const loadQuestionnaireRevisions = async (organizationId, context = {}) => {
  const identityEpoch = context.identityEpoch ?? state.identityEpoch;
  const identityKey = context.identityKey ?? currentIdentityKey();
  const key = organizationKey(organizationId);
  questionnaireLoadStates.set(key, { status: 'loading' });
  if (context.render !== false) renderAdminOrganizations();
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire', {
      credentials: 'same-origin',
    });
    const result = await readApiResponse(response, 'Не удалось загрузить сохранённые анкеты.');
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
    const items = Array.isArray(result?.items) ? result.items : [];
    const merged = new Map(items.map((item) => [item.assignment_ref, item]));
    for (const cached of questionnaireRevisions.get(key) || []) {
      const received = merged.get(cached.assignment_ref);
      if (!received || isQuestionnaireRevisionNewer(cached, received)) merged.set(cached.assignment_ref, cached);
    }
    questionnaireRevisions.set(key, [...merged.values()]);
    questionnaireLoadStates.set(key, { status: items.length ? 'ready' : 'empty' });
    if (context.render !== false) renderAdminOrganizations();
    return items;
  } catch (error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return null;
    const accessDenied = error?.status === 401 || error?.status === 403;
    if (accessDenied) {
      questionnaireRevisions.delete(key);
      for (const scopeKey of questionnairePreviews.keys()) {
        if (String(scopeKey).startsWith(key + ':')) questionnairePreviews.delete(scopeKey);
      }
    }
    questionnaireLoadStates.set(key, {
      status: 'error', message: accessDenied
        ? 'Нет доступа к сохранённым анкетам этой организации.'
        : error.message || 'Не удалось загрузить сохранённые анкеты.',
    });
    if (context.render !== false) renderAdminOrganizations();
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
  captureAdminOrganizationsDraft();
  selectedOrganizationId = Number(organizationId) || null;
  saveManagementSelection();
  renderAdminOrganizations();
};

export const selectAdminOrganizationView = (organizationId, view) => {
  captureAdminOrganizationsDraft();
  const allowed = new Set(['people', 'organization-data', 'questionnaire']);
  organizationViews.set(Number(organizationId), allowed.has(view) ? view : 'people');
  saveManagementSelection();
  renderAdminOrganizations();
};

export const selectAdminOrganizationAssessment = (organizationId, form, assessmentRef, previousRef = '') => {
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
    });
  card?.querySelectorAll('.admin-questionnaire-preview').forEach((preview) => preview.remove());
  card?.querySelectorAll('.admin-readiness-panel').forEach((panel) => {
    panel.outerHTML = readinessMarkup(nextRef, revision?.readiness || null);
  });
};

export const getSelectedAdminOrganizationAssessment = (organizationId) =>
  selectedAssessmentRefs.get(organizationKey(organizationId)) ||
  (questionnaireRevisions.get(organizationKey(organizationId)) || [])[0]?.assignment_ref || '';

export const markAdminOrganizationQuestionnairePreviewStale = (organizationId, assessmentRef = '') => {
  const selectedRef = String(assessmentRef || getSelectedAdminOrganizationAssessment(organizationId)).trim();
  const key = assessmentKey(organizationId, selectedRef);
  if (!questionnairePreviews.has(key)) return;
  staleQuestionnairePreviews.add(key);
  const card = adminOrganizationsList.querySelector('[data-organization-id="' + Number(organizationId) + '"]');
  card?.querySelectorAll('.admin-questionnaire-preview').forEach((preview) => {
    if (!preview.querySelector('[data-preview-stale]')) {
      preview.querySelector('strong')?.insertAdjacentHTML('afterend',
        '<p class="form-status error" data-preview-stale>Данные изменились. Обновите предпросмотр перед подтверждением. ' +
        '<button type="button" class="text-button" data-action="refresh-questionnaire-preview">Обновить предпросмотр</button></p>');
    }
    const confirmButton = preview.querySelector('[data-action="confirm-questionnaire"]');
    if (confirmButton) confirmButton.disabled = true;
  });
};

export const updateAdminOrganizationQuestionnaireRecipients = (organizationId, preview) => {
  if (!preview) return;
  const participant = preview.querySelector('input[name="questionnaire_recipient"][value="participant"]');
  if (participant) { participant.checked = true; participant.disabled = true; }
  const adminToggle = preview.querySelector('input[name="questionnaire_recipient"][value="organization_admin"]');
  const userFields = [...preview.querySelectorAll('input[name="questionnaire_recipient_user"]')];
  const busy = questionnaireConfirmRequestsInFlight.has(assessmentKey(organizationId, preview.dataset.assessmentRef));
  const outcome = questionnaireConfirmOutcomes.get(assessmentKey(organizationId, preview.dataset.assessmentRef));
  const uncertain = outcome?.status === 'unknown' && Number(outcome.revisionId) === Number(preview.dataset.questionnaireRevisionId);
  if (adminToggle) adminToggle.disabled = busy || uncertain;
  if (!adminToggle?.checked) userFields.forEach((field) => { field.checked = false; field.disabled = true; });
  else userFields.forEach((field) => { field.disabled = busy || uncertain; });
  const selectedUsers = userFields.filter((field) => field.checked).length;
  const valid = !adminToggle?.checked || selectedUsers > 0;
  const error = preview.querySelector('[data-questionnaire-recipient-error]');
  if (error) {
    error.textContent = valid ? '' : 'Выберите хотя бы одного представителя заказчика.';
    error.classList.toggle('hidden', valid);
  }
  const projection = preview.querySelector('[data-questionnaire-recipient-projection]');
  if (projection) projection.textContent = adminToggle?.checked && selectedUsers
    ? projection.dataset.adminProjection : projection.dataset.participantProjection;
  const confirmButton = preview.querySelector('[data-action="confirm-questionnaire"]');
  if (confirmButton) confirmButton.disabled = !valid || uncertain ||
    staleQuestionnairePreviews.has(assessmentKey(organizationId, preview.dataset.assessmentRef)) ||
    questionnaireConfirmRequestsInFlight.has(assessmentKey(organizationId, preview.dataset.assessmentRef));
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

export const addAdminOrganizationAdmin = async (organizationId, email) => {
  const normalizedEmail = String(email || '').trim();
  if (!normalizedEmail) {
    setStatus('Укажите email администратора.', 'error');
    return;
  }
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/admins',
      { method: 'POST', body: JSON.stringify({ email: normalizedEmail }) },
      'Не удалось добавить администратора.',
    );
    setStatus('Администратор добавлен.', 'success');
  } catch (error) {
    setStatus(membershipErrorMessage(error, 'Не удалось добавить администратора.'), 'error');
  }
};

export const deleteAdminOrganizationAdmin = async (organizationId, email) => {
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/admins?email=' + encodeURIComponent(email),
      { method: 'DELETE', headers: {} },
      'Не удалось удалить администратора.',
    );
    setStatus('Администратор удален.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось удалить администратора.', 'error');
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

export const deleteAdminOrganizationMember = async (organizationId, email) => {
  try {
    const result = await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/members?email=' + encodeURIComponent(email),
      { method: 'DELETE', headers: {} },
      'Не удалось отвязать участника.',
    );
    const action = result?.membership_action;
    setStatus(action?.result === 'already_absent'
      ? 'Связь участника с организацией уже отсутствовала. Аккаунт пользователя не изменён.'
      : 'Участник убран из организации. Аккаунт пользователя сохранён; повторное добавление не потребует новой регистрации.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось отвязать участника.', 'error');
  }
};

export const transferAdminOrganizationMember = async (organizationId, userId, targetOrganizationId, targetRole) => {
  try {
    await requestOrganizations(
      '/users/admin/users/' + Number(userId) + '/transfer-organization',
      {
        method: 'POST',
        body: JSON.stringify({
          expected_source_organization_id: Number(organizationId),
          target_organization_id: Number(targetOrganizationId),
          target_role: targetRole === 'admin' ? 'admin' : 'member',
          operation_id: createOperationId(),
        }),
      },
      'Не удалось перенести участника.',
    );
    setStatus('Участник перенесён. Старые назначения и приглашения отозваны, активные веб-сессии завершены.', 'success');
    return true;
  } catch (error) {
    setStatus(transferErrorMessage(error), 'error');
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

export const sendAdminOrganizationMemberInvitation = async (organizationId, emailOrEmails, assignmentRef) => {
  const emails = (Array.isArray(emailOrEmails) ? emailOrEmails : [emailOrEmails])
    .map((email) => String(email || '').trim().toLowerCase())
    .filter(Boolean);
  const assessment = String(assignmentRef || '').trim();
  if (!assessment) {
    setStatus('Сначала укажите оценку в разделе «Данные организации».', 'error');
    return;
  }
  const requestKey = organizationId + ':' + assessment + ':' + [...new Set(emails)].sort().join(',');
  if (!emails.length || invitationRequestsInFlight.has(requestKey)) return;
  const operationId = invitationOperationIds.get(requestKey) || createOperationId();
  invitationOperationIds.set(requestKey, operationId);
  try {
    invitationRequestsInFlight.add(requestKey);
    const response = await fetch('/users/admin/organizations/' + organizationId + '/personal-invitations', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operationId },
      body: JSON.stringify({ emails, assignment_ref: assessment, operation_id: operationId }),
    });
    const result = await readApiResponse(response, 'Не удалось отправить приглашение.');
    const items = Array.isArray(result.items) ? result.items : [];
    const failed = items.filter((item) => item.status === 'error');
    const queued = items.filter((item) => item.status === 'queued');
    const accepted = items.filter((item) => item.status === 'accepted');
    const uncertain = items.filter((item) => item.status === 'uncertain');
    const registered = items.filter((item) => item.status === 'already_registered');
    invitationOperationIds.delete(requestKey);
    await loadAdminOrganizations();
    if (failed.length || uncertain.length) {
      setStatus(
        'Принято провайдером: ' + accepted.length + '. Уже зарегистрированы: ' + registered.length + '. В очереди: ' + queued.length +
          '. Неопределённый исход: ' + uncertain.length + '. Ошибок: ' + failed.length + '. ' +
          [...uncertain, ...failed].map((item) => item.email + ': ' + (item.error || 'ошибка отправки')).join('; '),
        'error',
      );
    } else if (queued.length) {
      setStatus('Принято провайдером: ' + accepted.length + '. Уже зарегистрированы: ' + registered.length + '. В очереди: ' + queued.length + '.', 'muted');
    } else {
      setStatus('Почтовый сервис принял приглашения: ' + accepted.length + '. Уже зарегистрированы: ' + registered.length + '.', 'success');
    }
  } catch (error) {
    const message = error instanceof TypeError || error?.message === 'Failed to fetch'
      ? 'Не удалось связаться с сервером. Повторите отправку — операция не будет продублирована.'
      : error.message || 'Не удалось отправить приглашение.';
    setStatus(message, 'error');
  } finally {
    invitationRequestsInFlight.delete(requestKey);
  }
};

export const assignAdminOrganizationAssessment = async (organizationId, userIds, assignmentRef, roleProfileVersionId = null) => {
  const selected = [...new Set((userIds || []).map(Number).filter(Boolean))];
  const assessment = String(assignmentRef || '').trim();
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
  const operationKey = requestKey + ':' + selected.slice().sort((left, right) => left - right).join(',');
  const operationId = assignmentOperationIds.get(operationKey) || createOperationId();
  assignmentOperationIds.set(operationKey, operationId);
  if (assignmentSourceRequests.has(requestKey)) return false;
  assignmentSourceRequests.add(requestKey);
  const identityEpoch = state.identityEpoch;
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/assessment-assignments', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_ids: selected, assignment_ref: assessment, operation_id: operationId,
        ...(roleProfileVersionId ? { role_profile_version_id: Number(roleProfileVersionId) } : {}) }),
    });
    const result = await readApiResponse(response, 'Не удалось назначить оценку.');
    const items = Array.isArray(result.items) ? result.items : [];
    const assigned = items.filter((item) => item.status === 'assigned').length;
    const existing = items.filter((item) => item.status === 'already_assigned').length;
    const failed = items.filter((item) => item.status === 'not_assigned');
    await loadAdminOrganizations();
    if (state.identityEpoch !== identityEpoch) return false;
    assignmentOperationIds.delete(operationKey);
    setStatus(
      'Назначена: ' + assigned + '. Уже была назначена: ' + existing + '. Не назначена: ' + failed.length +
        (failed.length ? '. ' + failed.map((item) => item.user_id + ': ' + item.error).join('; ') : '') +
        '. Оценка для специалистов назначена со всеми проверенными источниками.',
      failed.length ? 'error' : 'success',
    );
    return failed.length === 0;
  } catch (error) {
    setStatus(error.message || 'Не удалось назначить оценку.', 'error');
    offerAssessmentDataNavigation(organizationId, assessment);
    return false;
  } finally {
    assignmentSourceRequests.delete(requestKey);
  }
};

const offerAssessmentDataNavigation = (organizationId, assessmentRef) => {
  const target = operationRoot()?.querySelector('[data-operation-status]') || adminOrganizationsStatus;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'text-button';
  button.textContent = assessmentRef ? 'Открыть данные оценки «' + assessmentRef + '»' : 'Выбрать оценку и подготовить сведения';
  button.onclick = () => {
    if (assessmentRef) selectedAssessmentRefs.set(organizationKey(organizationId), assessmentRef);
    selectAdminOrganizationView(organizationId, 'organization-data');
  };
  target?.append(button);
};

export const revokeAdminOrganizationMemberInvitation = async (organizationId, invitationId) => {
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/personal-invitations/' + invitationId, {
      method: 'DELETE',
      credentials: 'same-origin',
    });
    await readApiResponse(response, 'Не удалось отозвать приглашение.');
    await loadAdminOrganizations();
    setStatus('Приглашение отозвано.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось отозвать приглашение.', 'error');
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
  const action = payload?.channel === 'csv' ? 'preview-questionnaire' : 'preview-early-data';
  const submittedForm = adminOrganizationsList.querySelector(
    '[data-organization-id="' + Number(organizationId) + '"] form[data-action="' + action + '"]',
  );
  const submittedSignature = questionnaireInputSignature(organizationId, action, payload?.assignment_ref);
  captureAdminOrganizationsDraft();
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const scopeKey = assessmentKey(organizationId, payload?.assignment_ref);
  const requestGeneration = (questionnairePreviewRequestGenerations.get(scopeKey) || 0) + 1;
  questionnairePreviewRequestGenerations.set(scopeKey, requestGeneration);
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/preview', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const preview = await readApiResponse(response, 'Не удалось распознать анкету.');
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    if (questionnairePreviewRequestGenerations.get(scopeKey) !== requestGeneration) return;
    const currentForm = adminOrganizationsList.querySelector(
      '[data-organization-id="' + Number(organizationId) + '"] form[data-action="' + action + '"]',
    );
    const draftKey = organizationKey(organizationId) + ':' + action + ':' + String(payload?.assignment_ref || '').trim();
    const inputChanged = questionnaireInputSignature(organizationId, action, payload?.assignment_ref) !== submittedSignature;
    if (currentForm && inputChanged) captureFormDraft(organizationId, currentForm);
    else if (!managementDrafts.has(draftKey) && submittedForm) captureFormDraft(organizationId, submittedForm);
    questionnairePreviews.set(scopeKey, preview);
    if (inputChanged) staleQuestionnairePreviews.add(scopeKey);
    else staleQuestionnairePreviews.delete(scopeKey);
    renderAdminOrganizations();
    setStatus(inputChanged
      ? 'Данные изменились во время предпросмотра. Обновите предпросмотр перед подтверждением.'
      : preview.status === 'ready_for_confirmation'
      ? 'Анкета распознана. Проверьте сведения и подтвердите источник.'
      : 'Черновик сохранён. Исправьте перечисленные ошибки или заполните обязательные поля.',
    !inputChanged && preview.status === 'ready_for_confirmation' ? 'success' : 'error');
  } catch (error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    if (questionnairePreviewRequestGenerations.get(scopeKey) !== requestGeneration) return;
    if (getSelectedAdminOrganizationAssessment(organizationId) === String(payload?.assignment_ref || '').trim()) {
      setStatus(questionnaireErrorMessage(error, 'Не удалось распознать анкету.'), 'error');
    }
  }
};

export const confirmAdminOrganizationQuestionnaire = async (organizationId, revisionId, recipients, recipientUserIds = []) => {
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const card = adminOrganizationsList.querySelector('[data-organization-id="' + Number(organizationId) + '"]');
  const confirmButton = card?.querySelector('[data-action="confirm-questionnaire"][data-value="' + Number(revisionId) + '"]');
  const submittedRef = String(confirmButton?.closest('.admin-questionnaire-preview')?.getAttribute('data-assessment-ref') || '').trim();
  const submittedForms = new Map([...card?.querySelectorAll(
    'form[data-action="preview-early-data"], form[data-action="preview-questionnaire"]',
  ) || []].map((form) => [String(form.dataset.action), { form, signature: formSignature(form) }]));
  captureAdminOrganizationsDraft();
  const requestKey = assessmentKey(organizationId, submittedRef);
  const priorOutcome = questionnaireConfirmOutcomes.get(requestKey);
  if (questionnaireConfirmRequestsInFlight.has(requestKey) ||
    (priorOutcome?.status === 'unknown' && Number(priorOutcome.revisionId) === Number(revisionId))) return;
  questionnaireConfirmRequestsInFlight.add(requestKey);
  updateAdminOrganizationQuestionnaireRecipients(organizationId, confirmButton?.closest('.admin-questionnaire-preview'));
  if (confirmButton) {
    confirmButton.disabled = true;
    confirmButton.textContent = 'Подтверждаем…';
  }
  const requestGeneration = (questionnaireConfirmRequestGenerations.get(requestKey) || 0) + 1;
  questionnaireConfirmRequestGenerations.set(requestKey, requestGeneration);
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/' + revisionId + '/confirm', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipients, recipient_user_ids: recipientUserIds }),
    });
    const confirmed = await readApiResponse(response, 'Не удалось подтвердить анкету.');
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    const confirmedRef = String(confirmed?.assignment_ref || '').trim();
    const confirmedKey = assessmentKey(organizationId, confirmedRef);
    if (questionnaireConfirmRequestGenerations.get(requestKey) !== requestGeneration) return;
    if (Number(confirmed?.id) !== Number(revisionId) || confirmed.status !== 'confirmed' || confirmedRef !== submittedRef) {
      throw new Error('Не удалось проверить ответ подтверждения.');
    }
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    if (questionnaireConfirmRequestGenerations.get(requestKey) !== requestGeneration) return;
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
      renderAdminOrganizations();
      if (getSelectedAdminOrganizationAssessment(organizationId) === submittedRef) {
        setStatus('Подтверждение завершено. Показана более новая серверная редакция.', 'success');
      }
      return;
    }
    questionnaireRevisions.set(revisionsKey,
      [confirmed, ...revisions.filter((item) => String(item.assignment_ref || '').trim() !== confirmedRef)]);
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
    const outcome = { status: 'confirmed', revisionId, assignmentRef: submittedRef, recipients, recipientUserIds };
    questionnaireConfirmOutcomes.set(requestKey, outcome);
    questionnaireConfirmRequestsInFlight.delete(requestKey);
    renderAdminOrganizations();
    if (getSelectedAdminOrganizationAssessment(organizationId) === submittedRef) {
      setStatus('Сведения подтверждены. Обновляем готовность…', 'success');
    }
    void refreshConfirmedReadiness(organizationId, outcome, { identityEpoch, identityKey, requestKey, requestGeneration });
  } catch (error) {
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey) return;
    if (questionnaireConfirmRequestGenerations.get(requestKey) !== requestGeneration) return;
    if (!error?.status || error.status >= 500) {
      questionnaireConfirmOutcomes.set(requestKey, {
        status: 'unknown', revisionId, assignmentRef: submittedRef, recipients, recipientUserIds,
      });
      captureAdminOrganizationsDraft();
      renderAdminOrganizations();
      if (getSelectedAdminOrganizationAssessment(organizationId) === submittedRef) {
        setStatus('Ответ не получен. Итог подтверждения неизвестен. Проверьте результат; повторно отправлять сведения пока не нужно.', 'error');
      }
    } else {
      if (getSelectedAdminOrganizationAssessment(organizationId) === submittedRef) {
        setStatus(questionnaireErrorMessage(error, 'Не удалось подтвердить анкету.'), 'error');
      }
    }
  } finally {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey &&
      questionnaireConfirmRequestGenerations.get(requestKey) === requestGeneration) {
      questionnaireConfirmRequestsInFlight.delete(requestKey);
      const currentButton = adminOrganizationsList.querySelector(
        '[data-organization-id="' + Number(organizationId) + '"] [data-action="confirm-questionnaire"][data-value="' + Number(revisionId) + '"]',
      );
      if (currentButton) {
        currentButton.textContent = 'Подтвердить сведения';
        updateAdminOrganizationQuestionnaireRecipients(organizationId, currentButton.closest('.admin-questionnaire-preview'));
      }
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
    if (!refreshed || Number(refreshed.id) < Number(outcome.revisionId) || !refreshed.readiness) {
      throw new Error('Готовность подтверждённой редакции ещё недоступна.');
    }
    const key = organizationKey(organizationId);
    const cached = questionnaireRevisions.get(key) || [];
    const merged = new Map(cached.map((item) => [item.assignment_ref, item]));
    for (const item of result.items) {
      const prior = merged.get(item.assignment_ref);
      if (!prior || !isQuestionnaireRevisionNewer(prior, item)) merged.set(item.assignment_ref, item);
    }
    captureAdminOrganizationsDraft();
    questionnaireRevisions.set(key, [...merged.values()]);
    questionnaireConfirmOutcomes.delete(context.requestKey);
    renderAdminOrganizations();
    if (getSelectedAdminOrganizationAssessment(organizationId) === outcome.assignmentRef) {
      setStatus(Number(refreshed.id) > Number(outcome.revisionId)
        ? 'Подтверждение завершено. Показана более новая серверная редакция.'
        : 'Сведения подтверждены. Готовность обновлена. Перейдите к участникам и назначению.', 'success');
    }
  } catch {
    if (!isCurrent()) return;
    outcome.status = 'refresh_failed';
    captureAdminOrganizationsDraft();
    renderAdminOrganizations();
    if (getSelectedAdminOrganizationAssessment(organizationId) === outcome.assignmentRef) {
      setStatus('Сведения подтверждены. Не удалось обновить готовность. Проверьте результат.', 'error');
    }
  }
};

export const checkAdminOrganizationConfirmation = async (organizationId, revisionId) => {
  const requestKey = [...questionnaireConfirmOutcomes.keys()].find((key) => key.startsWith(organizationKey(organizationId) + ':') &&
    Number(questionnaireConfirmOutcomes.get(key).revisionId) === Number(revisionId));
  const outcome = questionnaireConfirmOutcomes.get(requestKey);
  if (!outcome || questionnaireConfirmRequestsInFlight.has(requestKey)) return;
  const identityEpoch = state.identityEpoch;
  const identityKey = currentIdentityKey();
  const requestGeneration = questionnaireConfirmRequestGenerations.get(requestKey);
  questionnaireConfirmRequestsInFlight.add(requestKey);
  setStatus('Проверяем сохранённую редакцию и получателей…', 'loading');
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/' + revisionId, { credentials: 'same-origin' });
    const saved = await readApiResponse(response, 'Не удалось проверить подтверждение.');
    if (state.identityEpoch !== identityEpoch || currentIdentityKey() !== identityKey ||
      questionnaireConfirmOutcomes.get(requestKey) !== outcome) return;
    if (Number(saved.id) !== Number(revisionId) || saved.assignment_ref !== outcome.assignmentRef) throw new Error('Ответ относится к другой редакции.');
    captureAdminOrganizationsDraft();
    if (saved.status !== 'confirmed') {
      questionnaireConfirmOutcomes.delete(requestKey);
      renderAdminOrganizations();
      setStatus('Редакция пока не подтверждена. Можно проверить ещё раз или явно повторить подтверждение с теми же получателями.', 'muted');
      return;
    }
    const sameSet = (left, right) => JSON.stringify([...new Set(left || [])].sort()) === JSON.stringify([...new Set(right || [])].sort());
    const recipientsMatch = sameSet(saved.recipient_mapping, outcome.recipients) && sameSet(saved.recipient_user_ids, outcome.recipientUserIds);
    const revisionsKey = organizationKey(organizationId);
    const revisions = questionnaireRevisions.get(revisionsKey) || [];
    const latest = revisions.find((item) => item.assignment_ref === saved.assignment_ref);
    if (!latest || !isQuestionnaireRevisionNewer(latest, saved)) {
      questionnaireRevisions.set(revisionsKey, [saved, ...revisions.filter((item) => item.assignment_ref !== saved.assignment_ref)]);
    }
    const preview = questionnairePreviews.get(requestKey);
    if (Number(preview?.id) === Number(revisionId)) questionnairePreviews.delete(requestKey);
    outcome.status = 'confirmed';
    renderAdminOrganizations();
    setStatus(recipientsMatch ? 'Сведения подтверждены. Сохранённые получатели проверены.'
      : 'Сведения подтверждены с другим набором получателей. Показаны фактически сохранённые права; для изменения нужна новая редакция.', recipientsMatch ? 'success' : 'error');
    void refreshConfirmedReadiness(organizationId, outcome, { identityEpoch, identityKey, requestKey, requestGeneration });
  } catch (error) {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey) {
      setStatus('Не удалось проверить результат. ' + error.message + ' Повторите проверку.', 'error');
    }
  } finally {
    if (state.identityEpoch === identityEpoch && currentIdentityKey() === identityKey) questionnaireConfirmRequestsInFlight.delete(requestKey);
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

export const connectAdminOrganizationProgram = async (organizationId, programDefinitionId) => {
  const operationId = createOperationId();
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/assessment-program', {
      method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ program_definition_id: Number(programDefinitionId), operation_id: operationId }),
    });
    await readApiResponse(response, 'Не удалось подключить программу оценки.');
    await loadAdminOrganizations();
    setStatus('Опубликованная версия программы подключена к организации.', 'success');
    return true;
  } catch (error) {
    setStatus(error.message || 'Не удалось подключить программу оценки.', 'error');
    return false;
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

export const previewAdminAccountPurge = async (userId) => {
  const response = await fetch('/users/admin/users/' + Number(userId) + '/purge-preview', { credentials: 'same-origin' });
  return readApiResponse(response, 'Не удалось построить состав полного удаления аккаунта.');
};

export const purgeAdminAccount = async (userId, email, previewFingerprint) => {
  const response = await fetch('/users/admin/users/' + Number(userId) + '/purge', {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirmation_email: email, preview_fingerprint: previewFingerprint,
      operation_id: createOperationId(), acknowledge_irreversible: true }),
  });
  await readApiResponse(response, 'Не удалось полностью удалить аккаунт.');
  await loadAdminOrganizations();
  setStatus('Аккаунт «' + email + '» и связанные данные полностью удалены.', 'success');
};

const renderTagList = (items, emptyText, className, deleteAction) => {
  if (!items.length) {
    return '<p class="admin-organizations-empty">' + escapeHtml(emptyText) + '</p>';
  }
  return (
    '<div class="admin-organizations-tags">' +
    items
      .map((item) => {
        const label = typeof item === 'string' ? item : item.email;
        return (
          '<span class="admin-organizations-tag ' + className + '">' +
          '<span>' +
          escapeHtml(label) +
          '</span>' + (deleteAction ?
          '<button type="button" data-action="' +
          deleteAction +
          '" data-value="' +
          escapeHtml(label) +
          '" aria-label="Удалить">×</button>' : '') +
          '</span>'
        );
      })
      .join('') +
    '</div>'
  );
};

const renderMemberList = (items, { isSuperadmin = false, selectedAssessmentRef = '', transferTargets = [] } = {}) => {
  if (!items.length) {
    return '<p class="admin-organizations-empty">Участники не привязаны.</p>';
  }
  return (
    '<div class="admin-organization-members">' +
    items
      .map((item) => {
        const email = String(item.email || '');
        const isAutotest = email.toLowerCase().startsWith('__autotest__') || email.toLowerCase().endsWith('@autotest.local');
        const hasPassword = item.has_password === true;
        const label = item.full_name ? item.full_name + ' · ' + email : email;
        const details = item.raw_position || item.job_description || item.role_description || item.raw_duties || '';
        const preparationStatus = String(item.assessment_preparation_status || '');
        const isPreparing = preparationStatus === 'queued' || preparationStatus === 'running';
        const isPrepared = item.assessment_prepared === true;
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
        const removeButton = isAutotest
          ? ''
          : '<button class="admin-organization-remove-button" type="button" data-action="delete-member" data-value="' +
            escapeHtml(email) +
            '" title="Аккаунт сохранится; повторная регистрация не потребуется" aria-label="Убрать из участников">Убрать из участников</button>';
        const passwordButton = !isSuperadmin ? '' : hasPassword
          ? '<button class="admin-organization-password-button" type="button" data-action="reset-member-password" data-value="' +
            escapeHtml(email) +
            '" title="Сбросить пароль" aria-label="Сбросить пароль">Сбросить пароль</button>'
          : '<span class="admin-organization-password-state" title="Пользователь еще не задавал пароль">Пароль не задан</span>';
        const invitationStatus = String(item.invitation_status || 'not_sent');
        const invitationLabels = { not_sent: 'Письмо не отправлено', queued: 'Письмо в очереди', sending: 'Исход отправки уточняется', accepted: 'Письмо принято провайдером', error: 'Ошибка отправки', revoked: 'Ссылка отозвана', expired: 'Ссылка истекла', used: 'Регистрация завершена' };
        const deliveryLabels = { not_sent: 'Письмо: не отправлено', queued: 'Письмо: в очереди', sending: 'Письмо: исход неизвестен', accepted: 'Письмо: принято провайдером', error: 'Письмо: ошибка' };
        const linkLabels = { not_created: 'Ссылка: не создана', active: 'Ссылка: действует 72 часа', revoked: 'Ссылка: отозвана', expired: 'Ссылка: истекла', used: 'Ссылка: использована' };
        const registrationLabel = item.registration_status === 'registered' ? 'Регистрация: завершена' : 'Регистрация: ожидается';
        const hasAssignment = (item.assessment_assignments || []).includes(selectedAssessmentRef);
        const acquaintanceStatus = String(item.acquaintance_status || 'not_started');
        const currentStage = preparationStatus === 'failed'
          ? 'Подготовка завершилась с ошибкой'
          : isPreparing
            ? 'Идёт подготовка оценки'
            : isPrepared
              ? 'Оценка подготовлена'
              : ['answers_confirmed', 'completed'].includes(acquaintanceStatus)
                ? 'Знакомство завершено'
                : acquaintanceStatus === 'in_progress'
                  ? 'Проходит знакомство'
                  : item.invitation_delivery_status === 'accepted'
                      ? 'Письмо отправлено — ожидаем начала знакомства'
                    : !hasAssignment
                      ? 'Оценка не назначена'
                      : 'Приглашение не отправлено';
        const sendLabel = item.invitation_id ? 'Отправить повторно' : 'Отправить';
        const invitationButton = '<button type="button" data-action="send-member-invitation" data-value="' + escapeHtml(email) + '">' + sendLabel + '</button>';
        const revokeButton = (invitationStatus === 'accepted' || invitationStatus === 'queued' || invitationStatus === 'sending')
          ? '<button type="button" data-action="revoke-member-invitation" data-invitation-id="' + Number(item.invitation_id) + '" data-value="' + escapeHtml(email) + '">Отозвать ссылку</button>'
          : '';
        const transferForm = !isSuperadmin || !transferTargets.length ? '' :
          '<form class="admin-organization-transfer-form" data-action="transfer-member" data-user-id="' + Number(item.user_id) + '">' +
          '<label><span>Перенести в</span><select name="target_organization_id" required><option value="">Выберите организацию</option>' +
          transferTargets.map((target) => '<option value="' + Number(target.id) + '">' + escapeHtml(target.name) + '</option>').join('') +
          '</select></label><label><span>Роль</span><select name="target_role"><option value="member">Участник</option><option value="admin">Администратор</option></select></label>' +
          '<button class="ghost-button compact-ghost" type="submit">Перенести</button></form>';
        return (
          '<div class="admin-organization-member">' +
          '<label class="admin-organization-member-select"><input type="checkbox" name="invitation_email" value="' + escapeHtml(email) + '" data-user-id="' + Number(item.user_id) + '" aria-label="Выбрать ' + escapeHtml(email) + '"></label>' +
          '<div class="admin-organization-member-main"><strong>' +
          escapeHtml(label) +
          '</strong>' +
          (details ? '<span>' + escapeHtml(details) + '</span>' : '') +
          '<span class="admin-organization-current-stage">' + escapeHtml(currentStage) + '</span>' +
          '</div>' +
          '<details class="admin-organization-member-statuses"><summary>Подробности статуса</summary><div>' +
          '<span class="admin-organization-invitation-state">Допуск: ' + escapeHtml(item.admission_status === 'denied' ? 'запрещён' : 'разрешён') + '</span>' +
          '<span class="admin-organization-invitation-state">' + escapeHtml(registrationLabel) + '</span>' +
          '<span class="admin-organization-invitation-state">' + escapeHtml(deliveryLabels[item.invitation_delivery_status] || invitationLabels[invitationStatus] || invitationStatus) + '</span>' +
          '<span class="admin-organization-invitation-state">' + escapeHtml(linkLabels[item.invitation_link_status] || item.invitation_link_status || 'Ссылка: не создана') + '</span>' +
          '<span class="admin-organization-invitation-state">Оценка: ' + escapeHtml(hasAssignment ? 'назначена' : 'не назначена') + '</span>' +
          '</div></details>' +
          '<div class="admin-organization-member-actions">' +
          invitationButton + revokeButton +
          preparationButton +
          passwordButton +
          removeButton +
          '</div>' + transferForm +
          '</div>'
        );
      })
      .join('') +
    '</div>'
  );
};

export const renderAdminOrganizations = () => {
  restoreManagementSelection();
  const data = state.adminOrganizations;
  if (!adminOrganizationsList) {
    return;
  }
  const accountName = document.getElementById('admin-organizations-account-name');
  if (accountName) accountName.textContent = state.pendingUser?.full_name || state.pendingUser?.email || 'Аккаунт';
  if (adminOrganizationsTitle) {
    const activeView = organizationViews.get(Number(selectedOrganizationId)) || 'people';
    adminOrganizationsTitle.textContent = data?.is_superadmin ? (data?.title || 'Организации')
      : ({ people: 'Участники и приглашения', 'organization-data': 'Данные организации', questionnaire: 'Анкета для подготовки оценки' })[activeView];
  }
  if (adminOrganizationsSubtitle) {
    adminOrganizationsSubtitle.textContent = data?.is_superadmin
      ? (data?.subtitle || 'Управление доменами и администраторами организаций.')
      : 'Подготовьте сведения для оценки и назначьте её участникам.';
  }
  const organizations = Array.isArray(data?.items) ? data.items : [];
  clearInaccessibleOrganizationState(organizations);
  const isSuperadmin = Boolean(data?.is_superadmin);
  const physicalPurgeAvailable = Boolean(data?.physical_purge_available);
  const purgePreviewAvailable = Boolean(data?.purge_preview_available);
  const detachedAccounts = Array.isArray(data?.detached_accounts) ? data.detached_accounts : [];
  const detachedMarkup = isSuperadmin ? '<section class="card card--inset admin-detached-accounts"><h3>Ранее отвязанные аккаунты</h3>' +
    (detachedAccounts.length ? detachedAccounts.map((account) => '<div class="admin-organization-member"><span>' +
      escapeHtml(account.email) + '</span><button class="ghost-button compact-ghost danger" type="button" data-action="purge-account" data-user-id="' +
      Number(account.user_id) + '" data-email="' + escapeHtml(account.email) + '">Удалить полностью</button></div>').join('') :
      '<p class="admin-organizations-empty">Ранее отвязанных аккаунтов нет.</p>') + '</section>' : '';
  adminOrganizationsPanel.dataset.superadmin = String(isSuperadmin);
  document.querySelector('[data-admin-area="assessment"]')?.classList.toggle('hidden', isSuperadmin);
  document.getElementById('admin-organization-create-form')?.closest('section')?.classList.toggle(
    'hidden', !data || !isSuperadmin,
  );
  document.querySelector('.admin-organization-picker')?.classList.toggle('hidden', !isSuperadmin && organizations.length <= 1);
  if (!organizations.length) {
    if (adminOrganizationSelect) adminOrganizationSelect.innerHTML = '<option value="">Нет организаций</option>';
    adminOrganizationsList.innerHTML = detachedMarkup + '<p class="report-empty-state">' + (isSuperadmin
      ? 'Организации пока не созданы.'
      : 'Закреплённая организация недоступна или доступ отозван. Обратитесь к администратору платформы.') + '</p>';
    return;
  }
  if (!organizations.some((org) => Number(org.id) === Number(selectedOrganizationId))) {
    selectedOrganizationId = Number(organizations.find((org) => org.is_active !== false)?.id || organizations[0].id);
  }
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
  adminOrganizationsList.innerHTML = detachedMarkup + organizations
    .filter((org) => Number(org.id) === Number(selectedOrganizationId))
    .map((org) => {
      const orgId = Number(org.id);
      const isActive = org.is_active !== false;
      const activeBatch = state.adminOrganizationPreparationBatches?.[orgId];
      const batchIsRunning = activeBatch?.status === 'in_progress';
      const revisions = questionnaireRevisions.get(organizationKey(orgId)) || [];
      const selectedRef = selectedAssessmentRefs.get(organizationKey(orgId)) || revisions[0]?.assignment_ref || '';
      const questionnairePreview = questionnairePreviews.get(assessmentKey(orgId, selectedRef));
      const currentRevision = questionnairePreview ||
        (selectedRef ? revisions.find((item) => item.assignment_ref === selectedRef) : revisions[0]) || null;
      const readiness = currentRevision?.readiness || null;
      const questionnaireLoadState = questionnaireLoadStates.get(organizationKey(orgId));
      const questionnaireLoadMarkup = questionnaireLoadState?.status === 'error'
        ? '<div class="admin-questionnaire-load-state error" role="alert"><span>' +
          escapeHtml(questionnaireLoadState.message) + '</span><button type="button" class="text-button" data-action="retry-questionnaire-load">Повторить</button></div>'
        : questionnaireLoadState?.status === 'loading'
          ? '<div class="admin-questionnaire-load-state" role="status">Загружаем сохранённые анкеты…</div>'
          : questionnaireLoadState?.status === 'empty'
            ? '<div class="admin-questionnaire-load-state">Для этой организации ещё нет сохранённых анкет.</div>' : '';
      const questionnaireValidation = questionnairePreview?.validation_json || {};
      const questionnaireProblems = [...(questionnaireValidation.errors || []).map((item) => item.code),
        ...(questionnaireValidation.missing || [])];
      const activeView = organizationViews.get(orgId) || 'people';
      const availablePrograms = Array.isArray(data?.assessment_programs) ? data.assessment_programs : [];
      const currentProgram = org.assessment_program || null;
      const allowedRoles = Array.isArray(currentProgram?.roles) ? currentProgram.roles : [];
      const roleSelectionMarkup = allowedRoles.length > 1
        ? '<label><span>Роль программы</span><select name="role_profile_version_id" required><option value="">Выберите роль</option>' +
          allowedRoles.map((role) => '<option value="' + Number(role.version_id) + '">' + escapeHtml(role.name || role.code) + '</option>').join('') + '</select></label>'
        : allowedRoles.length === 1
          ? '<input type="hidden" name="role_profile_version_id" value="' + Number(allowedRoles[0].version_id) + '"><span>Роль: ' + escapeHtml(allowedRoles[0].name || allowedRoles[0].code) + '</span>'
          : '';
      const programMarkup = isSuperadmin ? '<form class="admin-organization-inline-form admin-organization-program-form" data-action="connect-assessment-program">' +
        '<label><span>Программа оценки</span><select name="program_definition_id" required>' +
        '<option value="">Выберите опубликованную версию</option>' + availablePrograms.map((program) =>
          '<option value="' + Number(program.id) + '"' +
          (Number(currentProgram?.program_definition_id) === Number(program.id) ? ' selected' : '') + '>' +
          escapeHtml(program.name) + ' · ' + escapeHtml(program.version) + '</option>').join('') +
        '</select></label><button class="ghost-button compact-ghost" type="submit">Подключить</button>' +
        (currentProgram ? '<p>Подключено: <strong>' + escapeHtml(currentProgram.program_name) +
          ' · ' + escapeHtml(currentProgram.program_version) + '</strong></p>' : '<p>Программа ещё не подключена.</p>') +
        '</form>' : '';
      const revisionAnswers = currentRevision?.answers_json || {};
      const answer = (questionId, field) => escapeHtml(revisionAnswers?.[questionId]?.[field] || '');
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
      const previewIsStale = staleQuestionnairePreviews.has(assessmentKey(orgId, selectedRef));
      const confirmationOutcome = questionnaireConfirmOutcomes.get(assessmentKey(orgId, selectedRef));
      const publishedRevision = revisions.find((item) => item.assignment_ref === selectedRef && item.status === 'confirmed');
      const confirmationMarkup = confirmationOutcome || publishedRevision
        ? '<div class="admin-questionnaire-confirmation" role="status"><strong>' +
          (confirmationOutcome?.status === 'unknown' ? 'Итог подтверждения неизвестен' : 'Сведения подтверждены') + '</strong>' +
          (publishedRevision ? '<p>Получатели: участник' + (publishedRevision.recipient_user_ids?.length
            ? ' и выбранные представители (' + publishedRevision.recipient_user_ids.length + ')' : '') + '.</p>' : '') +
          (confirmationOutcome ? '<p>' + (confirmationOutcome.status === 'unknown'
            ? 'Проверьте сохранение этой редакции перед повторной отправкой.'
            : confirmationOutcome.status === 'refresh_failed' ? 'Не удалось обновить готовность.' : 'Готовность обновляется…') +
            '</p><button type="button" class="ghost-button compact-ghost" data-action="check-questionnaire-confirmation" data-value="' +
            Number(confirmationOutcome.revisionId) + '">Проверить результат</button>' :
            '<button type="button" class="text-button" data-action="show-admin-view" data-view="people">Перейти к участникам и назначению</button>') + '</div>' : '';
      const participant = questionnairePreview?.participant_preview || {};
      const fieldLabels = { organization_name: 'Организация', organization_type: 'Тип организации',
        industry: 'Сфера деятельности', activity_description: 'Описание деятельности', purpose: 'Цель оценки',
        results_usage: 'Использование результатов', result_recipients: 'Кто увидит результаты',
        organizer: 'Организатор', responsible_contact: 'Контакт ответственного' };
      const validationLabels = { C01: 'сведения об организации', C02a: 'цель оценки', C03: 'использование результатов',
        C04: 'получатели результатов', C17: 'правила кейсов', C21: 'организатор и контакт' };
      const recipientProjections = questionnairePreview?.recipient_projections || {};
      const participantRows = Object.entries(fieldLabels).filter(([key]) => participant[key]).map(([key, label]) =>
        '<dt>' + escapeHtml(label) + '</dt><dd' + (key === 'result_recipients'
          ? ' data-questionnaire-recipient-projection data-participant-projection="' +
            escapeHtml(recipientProjections.participant || participant[key]) + '" data-admin-projection="' +
            escapeHtml(recipientProjections.organization_admin || participant[key]) + '"'
          : '') + '>' + escapeHtml(key === 'result_recipients'
          ? recipientProjections.participant || participant[key] : participant[key]) + '</dd>').join('');
      const changes = Array.isArray(questionnairePreview?.changes) ? questionnairePreview.changes : [];
      const changesMarkup = questionnairePreview?.is_first_publication
        ? '<p><strong>Первая публикация.</strong> Эти сведения станут текущими после подтверждения.</p>'
        : (changes.length ? '<ul>' + changes.map((change) => '<li><strong>' +
          escapeHtml(fieldLabels[change.field] || change.field) + ':</strong> «' + escapeHtml(change.before || 'не указано') +
          '» → «' + escapeHtml(change.after || 'не указано') + '»</li>').join('') + '</ul>' :
          '<p>Изменений относительно текущей подтверждённой редакции нет.</p>');
      const humanProblems = questionnaireProblems.map((item) => validationLabels[item] ||
        (String(item).includes('duplicate') ? 'повторяющиеся поля' : 'некорректно заполненные поля'));
      const previewMarkup = questionnairePreview ? '<div class="admin-questionnaire-preview" role="status" data-draft-action="questionnaire-preview" data-assessment-ref="' +
        escapeHtml(selectedRef) + '" data-preview-action="' +
        (questionnairePreview.channel === 'csv' ? 'preview-questionnaire' : 'preview-early-data') +
        '" data-questionnaire-revision-id="' + Number(questionnairePreview.id) + '"><strong>' +
        (questionnairePreview.status === 'ready_for_confirmation' ? 'Готово к подтверждению' : 'Нужно исправить анкету') + '</strong>' +
        (previewIsStale ? '<p class="form-status error" data-preview-stale>Данные изменились. Обновите предпросмотр перед подтверждением. ' +
          '<button type="button" class="text-button" data-action="refresh-questionnaire-preview">Обновить предпросмотр</button></p>' : '') +
        (humanProblems.length ? '<p>Проверьте: ' + escapeHtml([...new Set(humanProblems)].join(', ')) + '.</p>' :
          '<p>Обязательные поля распознаны.</p>') +
        '<section><h5>Что увидит участник</h5><dl>' + participantRows + '</dl></section>' +
        '<section><h5>Изменения относительно текущей редакции</h5>' + changesMarkup + '</section>' +
        (questionnairePreview.status === 'ready_for_confirmation' ?
          '<fieldset><legend>Получатели результатов по действующим правам</legend>' +
          '<label><input type="checkbox" name="questionnaire_recipient" value="participant" checked disabled> Участник — обязательный получатель</label>' +
          '<label><input type="checkbox" name="questionnaire_recipient" value="organization_admin"> Разрешить выбранным представителям заказчика</label>' +
          '<div class="admin-questionnaire-recipients">' + (org.admins || []).map((admin) =>
            '<label><input type="checkbox" name="questionnaire_recipient_user" value="' + Number(admin.user_id) + '" disabled> ' +
            escapeHtml(admin.full_name || admin.email) + ' · ' + escapeHtml(admin.email) + '</label>').join('') + '</div>' +
          '<p class="form-status error hidden" data-questionnaire-recipient-error></p>' +
          '</fieldset><button type="button" class="primary-button compact-primary" data-action="confirm-questionnaire" data-value="' +
          Number(questionnairePreview.id) + '"' + (previewIsStale ? ' disabled' : '') + '>Подтвердить сведения</button>' : '') + '</div>' : '';
      return (
        '<article class="card card--inset admin-organization-card" data-organization-id="' +
        orgId +
        '" data-organization-code="' + escapeHtml(org.code) +
        '" data-organization-active="' +
        (isActive ? 'true' : 'false') +
        '">' +
        '<div class="admin-organization-head">' +
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
        '</div>' +
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
        (isSuperadmin ? '<div class="admin-organization-columns">' +
        '<section><h4>Домены</h4>' +
        renderTagList(org.domains || [], 'Домены не заданы.', 'domain', isSuperadmin ? 'delete-domain' : '') +
        (isSuperadmin ? '<form class="admin-organization-inline-form" data-action="add-domain"><input type="text" placeholder="company.ru"><button class="ghost-button compact-ghost" type="submit">Добавить</button></form>' : '') +
        '</section>' +
        '<section><h4>Администраторы</h4>' +
        renderTagList(org.admins || [], 'Администраторы не заданы.', 'admin', isSuperadmin ? 'delete-admin' : '') +
        (isSuperadmin ? '<form class="admin-organization-inline-form" data-action="add-admin"><input type="email" placeholder="admin@company.ru"><button class="ghost-button compact-ghost" type="submit">Добавить</button></form>' : '') +
        '</section>' +
        '</div>' : '') +
        '<nav class="admin-organization-steps" aria-label="Разделы управления">' +
        viewButton('people', 'Организация и участники') +
        viewButton('organization-data', 'Данные организации') +
        viewButton('questionnaire', 'Анкета') + '</nav>' +
        '<section class="admin-organization-members-section' + (activeView === 'people' ? '' : ' hidden') + '" data-admin-view="people"><h4>Организация и участники</h4>' +
        '<p>Выбранная оценка: <strong>' + escapeHtml(selectedRef || 'не выбрана') + '</strong>. Назначение не запускает оценку.</p>' +
        '<div class="admin-organization-bulk-actions"><form class="admin-organization-bulk-invitation-form" data-action="send-member-invitations"><button class="primary-button compact-primary" type="submit">Отправить приглашения</button></form>' +
        '<form class="admin-organization-bulk-assignment-form" data-action="assign-member-assessment">' + roleSelectionMarkup + '<button class="primary-button compact-primary" type="submit">Назначить оценку</button></form></div>' +
        renderMemberList(org.members || [], {
          isSuperadmin,
          selectedAssessmentRef: selectedRef,
          transferTargets: organizations.filter((candidate) => candidate.is_active !== false && Number(candidate.id) !== orgId),
        }) +
        '<form class="admin-organization-member-form" data-action="add-member">' +
        '<h4>Добавить участника</h4><p>Для добавления нужны email, ФИО и должность.</p>' +
        '<label><span>Email</span><input name="email" type="email" placeholder="user@company.ru" required></label>' +
        '<label><span>ФИО</span><input name="full_name" type="text" placeholder="Иван Иванов" required></label>' +
        '<label><span>Должность</span><input name="role_description" type="text" placeholder="Руководитель отдела" required></label>' +
        '<button class="primary-button compact-primary" type="submit">Добавить</button>' +
        '</form>' +
        '<form class="admin-organization-import-form" data-action="import-members">' +
        '<input name="csv" type="file" accept=".csv,text/csv">' +
        '<span>CSV: email, full_name, role_description, job_instructions</span>' +
        '<button class="ghost-button compact-ghost" type="submit">Импорт</button>' +
        '</form>' +
        '</section>' +
        '<section class="admin-organization-members-section' + (activeView === 'organization-data' ? '' : ' hidden') + '" data-admin-view="organization-data">' + questionnaireLoadMarkup + readinessMarkup(selectedRef, readiness) + '<h4>Данные организации и выбранной оценки</h4>' +
        (!isSuperadmin ? '<form class="admin-organization-profile-form admin-organization-profile-form--compact" data-action="update-profile">' +
          '<div class="admin-organization-profile-heading"><strong>Карточка организации</strong><button class="primary-button compact-primary" type="submit">Сохранить карточку</button></div>' +
          '<label><span>Название</span><input name="name" value="' + escapeHtml(org.name) + '" required></label>' +
          '<label><span>Код</span><input name="code" value="' + escapeHtml(org.code) + '" required></label>' +
          '<input name="founded_year" type="hidden" value="' + escapeHtml(org.founded_year ?? '') + '">' +
          '<input name="employee_count" type="hidden" value="' + escapeHtml(org.employee_count ?? '') + '">' +
          '<input name="industry" type="hidden" value="' + escapeHtml(org.industry || '') + '">' +
          '<input name="website" type="hidden" value="' + escapeHtml(org.website || '') + '">' +
          '<input name="headquarters" type="hidden" value="' + escapeHtml(org.headquarters || '') + '">' +
          '<input name="notes" type="hidden" value="' + escapeHtml(org.notes || '') + '"></form>' : '') +
        '<p>Черновик можно редактировать. Участники увидят новые сведения после подтверждения.</p>' + legacyProfileMarkup +
        '<form class="admin-organization-early-data-form" data-action="preview-early-data">' +
        '<label><span>Оценка</span><input name="assignment_ref" type="text" value="' + escapeHtml(selectedRef) + '" placeholder="Например, 4К · поток октябрь 2026" required></label>' +
        '<label><span>Автор сведений</span><input name="source_author" type="text" value="' + escapeHtml(currentRevision?.source_author || '') + '" placeholder="Ответственный со стороны заказчика" required></label>' +
        '<label><span>Название организации</span><input name="organization_name" value="' + answer('C01', 'name') + '"></label>' +
        '<label><span>Тип организации</span><input name="organization_type" value="' + answer('C01', 'organization_type') + '"></label>' +
        '<label><span>Сфера деятельности</span><input name="industry" value="' + answer('C01', 'industry') + '"></label>' +
        '<label class="admin-organization-profile-wide"><span>Описание деятельности</span><textarea name="activity_description">' + answer('C01', 'activity_description') + '</textarea></label>' +
        '<label class="admin-organization-profile-wide"><span>Цель оценки</span><textarea name="purpose">' + answer('C02a', 'participant_text') + '</textarea></label>' +
        '<label class="admin-organization-profile-wide"><span>Использование результатов</span><textarea name="results_usage">' + answer('C03', 'participant_text') + '</textarea></label>' +
        '<label><span>Кто увидит результаты</span><input name="result_recipients" value="' + answer('C04', 'answer') + '"></label>' +
        '<label><span>Организатор</span><input name="organizer" value="' + answer('C21', 'organizer') + '"></label>' +
        '<label><span>Контакт ответственного</span><input name="responsible_contact" value="' + answer('C21', 'responsible_contact') + '"></label>' +
        '<label><span>Реалистичность кейсов</span><input name="case_reality_level" value="' + answer('C17', 'case_reality_level') + '"></label>' +
        '<label><span>Правила использования названия</span><input name="organization_name_usage_rules" value="' + answer('C17', 'organization_name_usage_rules') + '"></label>' +
        '<button class="primary-button compact-primary" type="submit">Сохранить черновик и предпросмотр</button></form>' +
        (activeView === 'organization-data' ? confirmationMarkup + previewMarkup : '') + '</section>' +
        '<section class="admin-organization-members-section' + (activeView === 'questionnaire' ? '' : ' hidden') + '" data-admin-view="questionnaire">' + questionnaireLoadMarkup + readinessMarkup(selectedRef, readiness) + '<h4>Корпоративная анкета</h4>' +
        '<p>Скачайте утверждённый UTF-8 CSV-шаблон, загрузите заполненный файл и проверьте ошибки.</p>' +
        '<p><a class="text-link" href="/users/admin/organizations/' + orgId + '/questionnaire/template">Скачать CSV-шаблон</a></p>' +
        '<form class="admin-organization-import-form" data-action="preview-questionnaire">' +
        '<label><span>Оценка</span><input name="assignment_ref" list="assessment-options-' + orgId + '" type="text" value="' + escapeHtml(selectedRef) + '" placeholder="Например, 4К · поток октябрь 2026" required></label>' +
        '<datalist id="assessment-options-' + orgId + '">' + revisions.map((item) => '<option value="' + escapeHtml(item.assignment_ref) + '"></option>').join('') + '</datalist>' +
        '<label><span>Автор сведений</span><input name="source_author" type="text" value="' + escapeHtml(currentRevision?.source_author || '') + '" placeholder="Автор сведений со стороны заказчика" required></label>' +
        '<input name="csv" type="file" accept=".csv,text/csv" required>' +
        '<button class="ghost-button compact-ghost" type="submit">Предпросмотр анкеты</button></form>' +
        (activeView === 'questionnaire' ? confirmationMarkup + previewMarkup : '') +
        '</section>' +
        '</article>'
      );
    })
    .join('');
  restoreAdminOrganizationsDraft();
};

export const openAdminOrganizations = async () => {
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
    await loadAdminOrganizations();
  } catch (error) {
    adminOrganizationsList.innerHTML = '<p class="report-empty-state">' + escapeHtml(error.message) + '</p>';
    return;
  }
  renderAdminOrganizations();
};
