import { createOperationId, readApiResponse } from '../../api.js';
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
import { persistAssessmentContext, setCurrentScreen, state } from '../../state.js';

let selectedOrganizationId = null;
const invitationRequestsInFlight = new Set();
const invitationOperationIds = new Map();
const questionnairePreviews = new Map();
const questionnaireRevisions = new Map();
const organizationViews = new Map();
let managementDraft = null;

const editableManagementFields = () => [...adminOrganizationsPanel.querySelectorAll('input, textarea, select')]
  .filter((field) => field.type !== 'file' && field.type !== 'hidden');

export const captureAdminOrganizationsDraft = () => {
  if (adminOrganizationsPanel.classList.contains('hidden')) return;
  const fields = editableManagementFields();
  managementDraft = {
    values: fields.map((field) => ({ value: field.value, checked: field.checked })),
    focusedIndex: fields.indexOf(document.activeElement),
  };
};

const restoreAdminOrganizationsDraft = () => {
  if (!managementDraft) return;
  const fields = editableManagementFields();
  if (fields.length === managementDraft.values.length) {
    fields.forEach((field, index) => {
      field.value = managementDraft.values[index].value;
      if (['checkbox', 'radio'].includes(field.type)) field.checked = managementDraft.values[index].checked;
    });
    fields[managementDraft.focusedIndex]?.focus({ preventScroll: true });
  }
  managementDraft = null;
};

const escapeHtml = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const setStatus = (message, tone = 'muted') => {
  if (!adminOrganizationsStatus) {
    return;
  }
  adminOrganizationsStatus.textContent = message || '';
  adminOrganizationsStatus.classList.toggle('hidden', !message);
  adminOrganizationsStatus.dataset.tone = tone;
};

const requestOrganizations = async (url, options, fallbackMessage) => {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });
  const data = await readApiResponse(response, fallbackMessage);
  state.adminOrganizations = data;
  persistAssessmentContext();
  renderAdminOrganizations();
  return data;
};

const requestOrganizationsImport = async (url, csvText) => {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_text: csvText }),
  });
  const data = await readApiResponse(response, 'Не удалось импортировать участников.');
  state.adminOrganizations = data.organizations || data;
  persistAssessmentContext();
  renderAdminOrganizations();
  return data;
};

export const loadAdminOrganizations = async () => {
  const data = await requestOrganizations(
    '/users/admin/organizations',
    { method: 'GET', headers: {} },
    'Не удалось загрузить организации.',
  );
  await Promise.all((data.items || []).map(async (org) => {
    const response = await fetch('/users/admin/organizations/' + org.id + '/questionnaire', {
      credentials: 'same-origin',
    });
    if (response.ok) {
      const result = await response.json();
      questionnaireRevisions.set(Number(org.id), Array.isArray(result.items) ? result.items : []);
    }
  }));
  renderAdminOrganizations();
  return data;
};

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
  selectedOrganizationId = Number(organizationId) || null;
  renderAdminOrganizations();
};

export const selectAdminOrganizationView = (organizationId, view) => {
  const allowed = new Set(['people', 'organization-data', 'questionnaire']);
  organizationViews.set(Number(organizationId), allowed.has(view) ? view : 'people');
  renderAdminOrganizations();
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
    setStatus(error.message || 'Не удалось добавить администратора.', 'error');
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
  if (!normalizedEmail) {
    setStatus('Укажите email участника.', 'error');
    return;
  }
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/members',
      {
        method: 'POST',
        body: JSON.stringify({
          email: normalizedEmail,
          full_name: String(payload?.full_name || '').trim() || null,
          role_description: String(payload?.role_description || '').trim() || null,
          job_instructions: String(payload?.job_instructions || '').trim() || null,
        }),
      },
      'Не удалось привязать участника.',
    );
    setStatus('Участник привязан к организации.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось привязать участника.', 'error');
  }
};

export const deleteAdminOrganizationMember = async (organizationId, email) => {
  try {
    await requestOrganizations(
      '/users/admin/organizations/' + organizationId + '/members?email=' + encodeURIComponent(email),
      { method: 'DELETE', headers: {} },
      'Не удалось отвязать участника.',
    );
    setStatus('Участник отвязан от организации.', 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось отвязать участника.', 'error');
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
    invitationOperationIds.delete(requestKey);
    await loadAdminOrganizations();
    if (failed.length || uncertain.length) {
      setStatus(
        'Принято провайдером: ' + accepted.length + '. В очереди: ' + queued.length +
          '. Неопределённый исход: ' + uncertain.length + '. Ошибок: ' + failed.length + '. ' +
          [...uncertain, ...failed].map((item) => item.email + ': ' + (item.error || 'ошибка отправки')).join('; '),
        'error',
      );
    } else if (queued.length) {
      setStatus('Принято провайдером: ' + accepted.length + '. В очереди: ' + queued.length + '.', 'muted');
    } else {
      setStatus('Почтовый сервис принял приглашения: ' + accepted.length + '.', 'success');
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
  try {
    const result = await requestOrganizationsImport('/users/admin/organizations/' + organizationId + '/members/import', text);
    const errorsText = Array.isArray(result.errors) && result.errors.length ? ' Ошибки: ' + result.errors.slice(0, 3).join('; ') : '';
    setStatus('Импортировано: ' + Number(result.imported_count || 0) + '. Пропущено: ' + Number(result.skipped_count || 0) + '.' + errorsText, result.skipped_count ? 'error' : 'success');
  } catch (error) {
    setStatus(error.message || 'Не удалось импортировать участников.', 'error');
  }
};

export const previewAdminOrganizationQuestionnaire = async (organizationId, payload) => {
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/preview', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const preview = await readApiResponse(response, 'Не удалось распознать анкету.');
    questionnairePreviews.set(Number(organizationId), preview);
    renderAdminOrganizations();
    setStatus(preview.status === 'ready_for_confirmation'
      ? 'Анкета распознана. Проверьте сведения и подтвердите источник.'
      : 'Черновик сохранён. Исправьте перечисленные ошибки или заполните обязательные поля.',
    preview.status === 'ready_for_confirmation' ? 'success' : 'error');
  } catch (error) { setStatus(error.message, 'error'); }
};

export const confirmAdminOrganizationQuestionnaire = async (organizationId, revisionId, recipients, recipientUserIds = []) => {
  try {
    const response = await fetch('/users/admin/organizations/' + organizationId + '/questionnaire/' + revisionId + '/confirm', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipients, recipient_user_ids: recipientUserIds }),
    });
    await readApiResponse(response, 'Не удалось подтвердить анкету.');
    questionnairePreviews.delete(Number(organizationId));
    renderAdminOrganizations();
    setStatus('Источник анкеты подтверждён и опубликован новой редакцией.', 'success');
  } catch (error) { setStatus(error.message, 'error'); }
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

const renderMemberList = (items, { isSuperadmin = false } = {}) => {
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
            '" aria-label="Отвязать">×</button>';
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
        const sendLabel = item.invitation_id ? 'Отправить повторно' : 'Отправить';
        const invitationButton = '<button type="button" data-action="send-member-invitation" data-value="' + escapeHtml(email) + '">' + sendLabel + '</button>';
        const revokeButton = (invitationStatus === 'accepted' || invitationStatus === 'queued' || invitationStatus === 'sending')
          ? '<button type="button" data-action="revoke-member-invitation" data-invitation-id="' + Number(item.invitation_id) + '" data-value="' + escapeHtml(email) + '">Отозвать ссылку</button>'
          : '';
        return (
          '<div class="admin-organization-member">' +
          '<label class="admin-organization-member-select"><input type="checkbox" name="invitation_email" value="' + escapeHtml(email) + '" aria-label="Выбрать ' + escapeHtml(email) + '"></label>' +
          '<div class="admin-organization-member-main"><strong>' +
          escapeHtml(label) +
          '</strong>' +
          (details ? '<span>' + escapeHtml(details) + '</span>' : '') +
          '</div>' +
          '<div class="admin-organization-member-statuses">' +
          '<span class="admin-organization-invitation-state">Допуск: разрешён</span>' +
          '<span class="admin-organization-invitation-state">' + escapeHtml(registrationLabel) + '</span>' +
          '<span class="admin-organization-invitation-state">' + escapeHtml(deliveryLabels[item.invitation_delivery_status] || invitationLabels[invitationStatus] || invitationStatus) + '</span>' +
          '<span class="admin-organization-invitation-state">' + escapeHtml(linkLabels[item.invitation_link_status] || item.invitation_link_status || 'Ссылка: не создана') + '</span>' +
          '</div>' +
          '<div class="admin-organization-member-actions">' +
          invitationButton + revokeButton +
          preparationButton +
          passwordButton +
          removeButton +
          '</div>' +
          '</div>'
        );
      })
      .join('') +
    '</div>'
  );
};

export const renderAdminOrganizations = () => {
  const data = state.adminOrganizations;
  if (!adminOrganizationsList) {
    return;
  }
  if (adminOrganizationsTitle) {
    adminOrganizationsTitle.textContent = data?.is_superadmin ? (data?.title || 'Организации') : 'Организация и участники';
  }
  if (adminOrganizationsSubtitle) {
    adminOrganizationsSubtitle.textContent = data?.is_superadmin
      ? (data?.subtitle || 'Управление доменами и администраторами организаций.')
      : 'Три шага подготовки: участники, данные организации и анкета.';
  }
  const organizations = Array.isArray(data?.items) ? data.items : [];
  const isSuperadmin = Boolean(data?.is_superadmin);
  document.querySelector('[data-admin-area="assessment"]')?.classList.toggle('hidden', isSuperadmin);
  document.getElementById('admin-organization-create-form')?.closest('section')?.classList.toggle(
    'hidden', !data || (!isSuperadmin && organizations.length > 0),
  );
  document.querySelector('.admin-organization-picker')?.classList.toggle('hidden', !isSuperadmin && organizations.length <= 1);
  if (!organizations.length) {
    if (adminOrganizationSelect) adminOrganizationSelect.innerHTML = '<option value="">Нет организаций</option>';
    adminOrganizationsList.innerHTML = '<p class="report-empty-state">Организации пока не созданы.</p>';
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
  adminOrganizationsList.innerHTML = organizations
    .filter((org) => Number(org.id) === Number(selectedOrganizationId))
    .map((org) => {
      const orgId = Number(org.id);
      const isActive = org.is_active !== false;
      const activeBatch = state.adminOrganizationPreparationBatches?.[orgId];
      const batchIsRunning = activeBatch?.status === 'in_progress';
      const actionLabel = Number(org.members_count || 0) || Number(org.reports_count || 0) ? 'Деактивировать' : 'Удалить';
      const questionnairePreview = questionnairePreviews.get(orgId);
      const revisions = questionnaireRevisions.get(orgId) || [];
      const currentRevision = questionnairePreview || revisions[0] || null;
      const confirmedRevision = revisions.find((item) => item.status === 'confirmed');
      const questionnaireValidation = questionnairePreview?.validation_json || {};
      const questionnaireProblems = [...(questionnaireValidation.errors || []).map((item) => item.code),
        ...(questionnaireValidation.missing || [])];
      const activeView = organizationViews.get(orgId) || 'people';
      const revisionAnswers = currentRevision?.answers_json || {};
      const answer = (questionId, field) => escapeHtml(revisionAnswers?.[questionId]?.[field] || '');
      const viewButton = (view, label) => '<button type="button" class="admin-organization-step' +
        (activeView === view ? ' current' : '') + '" data-action="show-admin-view" data-view="' + view +
        '" aria-pressed="' + String(activeView === view) + '">' + label + '</button>';
      const previewMarkup = questionnairePreview ? '<div class="admin-questionnaire-preview" role="status"><strong>Статус: ' +
        escapeHtml(questionnairePreview.status) + '</strong>' +
        (questionnaireProblems.length ? '<p>Проверить: ' + escapeHtml(questionnaireProblems.join(', ')) + '</p>' :
          '<p>Обязательные поля распознаны. Подтверждение создаст новую опубликованную редакцию.</p>') +
        (questionnairePreview.status === 'ready_for_confirmation' ?
          '<fieldset><legend>Получатели результатов по действующим правам</legend>' +
          '<label><input type="checkbox" name="questionnaire_recipient" value="participant" checked disabled> Участник — обязательный получатель</label>' +
          '<label><input type="checkbox" name="questionnaire_recipient" value="organization_admin"> Разрешить выбранным представителям заказчика</label>' +
          '<div class="admin-questionnaire-recipients">' + (org.admins || []).map((admin) =>
            '<label><input type="checkbox" name="questionnaire_recipient_user" value="' + Number(admin.user_id) + '"> ' +
            escapeHtml(admin.full_name || admin.email) + ' · ' + escapeHtml(admin.email) + '</label>').join('') + '</div>' +
          '</fieldset><button type="button" class="primary-button compact-primary" data-action="confirm-questionnaire" data-value="' +
          Number(questionnairePreview.id) + '">Подтвердить сведения</button>' : '') + '</div>' : '';
      return (
        '<article class="card card--inset admin-organization-card" data-organization-id="' +
        orgId +
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
        '>Подготовить кейсы всем</button><button class="ghost-button compact-ghost danger" type="button" data-action="delete-organization">' +
        actionLabel +
        '</button>' : '') + '</div>' +
        '</div>' +
        renderOrganizationBatchProgress(orgId) +
        (isSuperadmin ? '<form class="admin-organization-profile-form" data-action="update-profile">' +
        '<div class="admin-organization-profile-heading"><div><p class="section-label accent-label">Профиль</p><h4>Сведения об организации</h4></div>' +
        '<button class="primary-button compact-primary" type="submit">Сохранить карточку</button></div>' +
        '<label class="admin-organization-profile-wide"><span>Профиль организации</span><textarea name="profile" placeholder="Кратко опишите организацию, её деятельность и особенности">' + escapeHtml(org.profile || '') + '</textarea></label>' +
        '<label><span>Год основания</span><input name="founded_year" type="number" min="1000" max="2100" value="' + escapeHtml(org.founded_year ?? '') + '" placeholder="Например, 2012"></label>' +
        '<label><span>Численность</span><input name="employee_count" type="number" min="0" value="' + escapeHtml(org.employee_count ?? '') + '" placeholder="Количество сотрудников"></label>' +
        '<label><span>Отрасль</span><input name="industry" type="text" value="' + escapeHtml(org.industry || '') + '" placeholder="Например, финтех"></label>' +
        '<label><span>Сайт</span><input name="website" type="url" value="' + escapeHtml(org.website || '') + '" placeholder="https://company.ru"></label>' +
        '<label><span>Штаб-квартира</span><input name="headquarters" type="text" value="' + escapeHtml(org.headquarters || '') + '" placeholder="Город, страна"></label>' +
        '<label class="admin-organization-profile-wide"><span>Прочая существенная информация</span><textarea name="notes" placeholder="Структура, география, культура и другие важные сведения">' + escapeHtml(org.notes || '') + '</textarea></label>' +
        '</form>' +
        '<div class="admin-organization-columns">' +
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
        '<p>Перед отправкой выберите оценку в разделе «Данные организации» и подтвердите сведения для знакомства.</p>' +
        '<form class="admin-organization-bulk-invitation-form" data-action="send-member-invitations"><button class="primary-button compact-primary" type="submit">Отправить приглашения</button></form>' +
        renderMemberList(org.members || [], { isSuperadmin }) +
        '<form class="admin-organization-member-form" data-action="add-member">' +
        '<input name="email" type="email" placeholder="user@company.ru" required>' +
        '<input name="full_name" type="text" placeholder="ФИО">' +
        '<input name="role_description" type="text" placeholder="Должность">' +
        '<button class="primary-button compact-primary" type="submit">Добавить</button>' +
        '</form>' +
        '<form class="admin-organization-import-form" data-action="import-members">' +
        '<input name="csv" type="file" accept=".csv,text/csv">' +
        '<span>CSV: email, full_name, role_description, job_instructions</span>' +
        '<button class="ghost-button compact-ghost" type="submit">Импорт</button>' +
        '</form>' +
        '</section>' +
        '<section class="admin-organization-members-section' + (activeView === 'organization-data' ? '' : ' hidden') + '" data-admin-view="organization-data"><div class="admin-readiness-panel"><strong>Готовность ранних данных</strong><p>' +
        (confirmedRevision ? 'Можно приглашать участников для оценки «' + escapeHtml(confirmedRevision.assignment_ref) + '». Готовность назначения проверяется отдельно.' : 'Чтобы пригласить участников, заполните и подтвердите сведения для знакомства.') +
        '</p></div><h4>Данные организации и выбранной оценки</h4>' +
        '<p>Черновик и подтверждение сохраняются в общем версионируемом контуре. Изменение полей не переписывает опубликованную редакцию.</p>' +
        '<form class="admin-organization-early-data-form" data-action="preview-early-data">' +
        '<label><span>Оценка</span><input name="assignment_ref" type="text" value="' + escapeHtml(currentRevision?.assignment_ref || '') + '" placeholder="Например, 4К · поток октябрь 2026" required></label>' +
        '<label><span>Автор сведений</span><input name="source_author" type="text" placeholder="Ответственный со стороны заказчика" required></label>' +
        '<label><span>Название организации</span><input name="organization_name" value="' + answer('C01', 'name') + '" required></label>' +
        '<label><span>Тип организации</span><input name="organization_type" value="' + answer('C01', 'organization_type') + '" required></label>' +
        '<label><span>Сфера деятельности</span><input name="industry" value="' + answer('C01', 'industry') + '" required></label>' +
        '<label class="admin-organization-profile-wide"><span>Описание деятельности</span><textarea name="activity_description" required>' + answer('C01', 'activity_description') + '</textarea></label>' +
        '<label class="admin-organization-profile-wide"><span>Цель оценки</span><textarea name="purpose" required>' + answer('C02a', 'participant_text') + '</textarea></label>' +
        '<label class="admin-organization-profile-wide"><span>Использование результатов</span><textarea name="results_usage" required>' + answer('C03', 'participant_text') + '</textarea></label>' +
        '<label><span>Кто увидит результаты</span><input name="result_recipients" value="' + answer('C04', 'answer') + '" required></label>' +
        '<label><span>Организатор</span><input name="organizer" value="' + answer('C21', 'organizer') + '" required></label>' +
        '<label><span>Контакт ответственного</span><input name="responsible_contact" value="' + answer('C21', 'responsible_contact') + '" required></label>' +
        '<label><span>Реалистичность кейсов</span><input name="case_reality_level" value="' + answer('C17', 'case_reality_level') + '" required></label>' +
        '<label><span>Правила использования названия</span><input name="organization_name_usage_rules" value="' + answer('C17', 'organization_name_usage_rules') + '" required></label>' +
        '<button class="primary-button compact-primary" type="submit">Сохранить черновик и предпросмотр</button></form>' +
        (activeView === 'organization-data' ? previewMarkup : '') + '</section>' +
        '<section class="admin-organization-members-section' + (activeView === 'questionnaire' ? '' : ' hidden') + '" data-admin-view="questionnaire"><div class="admin-readiness-panel"><strong>Анкета</strong><p>Загрузка создаёт только предпросмотр. Подтверждённая версия остаётся неизменной до отдельного подтверждения.</p></div><h4>Корпоративная анкета</h4>' +
        '<p>Скачайте утверждённый UTF-8 CSV-шаблон, загрузите заполненный файл и проверьте ошибки.</p>' +
        '<p><a class="text-link" href="/users/admin/organizations/' + orgId + '/questionnaire/template">Скачать CSV-шаблон</a></p>' +
        '<form class="admin-organization-import-form" data-action="preview-questionnaire">' +
        '<label><span>Оценка</span><input name="assignment_ref" list="assessment-options-' + orgId + '" type="text" value="' + escapeHtml(currentRevision?.assignment_ref || '') + '" placeholder="Например, 4К · поток октябрь 2026" required></label>' +
        '<datalist id="assessment-options-' + orgId + '">' + revisions.map((item) => '<option value="' + escapeHtml(item.assignment_ref) + '"></option>').join('') + '</datalist>' +
        '<input name="source_author" type="text" placeholder="Автор сведений со стороны заказчика" required>' +
        '<input name="csv" type="file" accept=".csv,text/csv" required>' +
        '<button class="ghost-button compact-ghost" type="submit">Предпросмотр анкеты</button></form>' +
        (activeView === 'questionnaire' ? previewMarkup : '') +
        '</section>' +
        '</article>'
      );
    })
    .join('');
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
  restoreAdminOrganizationsDraft();
};
