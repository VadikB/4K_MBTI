import { readApiResponse } from '../../api.js';
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
          '</span>' +
          '<button type="button" data-action="' +
          deleteAction +
          '" data-value="' +
          escapeHtml(label) +
          '" aria-label="Удалить">×</button>' +
          '</span>'
        );
      })
      .join('') +
    '</div>'
  );
};

const renderMemberList = (items) => {
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
        const details = item.raw_position || item.job_description || item.raw_duties || '';
        const preparationStatus = String(item.assessment_preparation_status || '');
        const isPreparing = preparationStatus === 'queued' || preparationStatus === 'running';
        const isPrepared = item.assessment_prepared === true;
        const canPrepare = item.assessment_profile_ready === true && !isPreparing && !isPrepared;
        const preparationButton = isPrepared
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
        const passwordButton = hasPassword
          ? '<button class="admin-organization-password-button" type="button" data-action="reset-member-password" data-value="' +
            escapeHtml(email) +
            '" title="Сбросить пароль" aria-label="Сбросить пароль">Сбросить пароль</button>'
          : '<span class="admin-organization-password-state" title="Пользователь еще не задавал пароль">Пароль не задан</span>';
        return (
          '<div class="admin-organization-member">' +
          '<div class="admin-organization-member-main"><strong>' +
          escapeHtml(label) +
          '</strong>' +
          (details ? '<span>' + escapeHtml(details) + '</span>' : '') +
          '</div>' +
          '<div class="admin-organization-member-actions">' +
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
    adminOrganizationsTitle.textContent = data?.title || 'Организации';
  }
  if (adminOrganizationsSubtitle) {
    adminOrganizationsSubtitle.textContent = data?.subtitle || 'Управление доменами и администраторами организаций.';
  }
  const organizations = Array.isArray(data?.items) ? data.items : [];
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
        ' отчетов</span><button class="ghost-button compact-ghost" type="button" data-action="prepare-organization-assessments"' +
        (batchIsRunning || !isActive ? ' disabled' : '') +
        '>Подготовить кейсы всем</button><button class="ghost-button compact-ghost danger" type="button" data-action="delete-organization">' +
        actionLabel +
        '</button></div>' +
        '</div>' +
        renderOrganizationBatchProgress(orgId) +
        '<form class="admin-organization-profile-form" data-action="update-profile">' +
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
        renderTagList(org.domains || [], 'Домены не заданы.', 'domain', 'delete-domain') +
        '<form class="admin-organization-inline-form" data-action="add-domain"><input type="text" placeholder="company.ru"><button class="ghost-button compact-ghost" type="submit">Добавить</button></form>' +
        '</section>' +
        '<section><h4>Администраторы</h4>' +
        renderTagList(org.admins || [], 'Администраторы не заданы.', 'admin', 'delete-admin') +
        '<form class="admin-organization-inline-form" data-action="add-admin"><input type="email" placeholder="admin@company.ru"><button class="ghost-button compact-ghost" type="submit">Добавить</button></form>' +
        '</section>' +
        '</div>' +
        '<section class="admin-organization-members-section"><h4>Участники</h4>' +
        renderMemberList(org.members || []) +
        '<form class="admin-organization-member-form" data-action="add-member">' +
        '<input name="email" type="email" placeholder="user@company.ru" required>' +
        '<input name="full_name" type="text" placeholder="ФИО">' +
        '<input name="role_description" type="text" placeholder="Описание роли / должность">' +
        '<textarea name="job_instructions" placeholder="Должностные инструкции"></textarea>' +
        '<button class="ghost-button compact-ghost" type="submit">Привязать</button>' +
        '</form>' +
        '<form class="admin-organization-import-form" data-action="import-members">' +
        '<input name="csv" type="file" accept=".csv,text/csv">' +
        '<span>CSV: email, full_name, role_description, job_instructions</span>' +
        '<button class="ghost-button compact-ghost" type="submit">Импорт</button>' +
        '</form>' +
        '</section>' +
        '</article>'
      );
    })
    .join('');
};

export const openAdminOrganizations = async () => {
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
