import { readApiResponse } from '../../api.js';
import {
  adminOrganizationCodeInput,
  adminOrganizationCreateButton,
  adminOrganizationNameInput,
  adminOrganizationsList,
  adminOrganizationsPanel,
  adminOrganizationsStatus,
  adminOrganizationsSubtitle,
  adminOrganizationsTitle,
} from '../../dom.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
import { persistAssessmentContext, setCurrentScreen, state } from '../../state.js';

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

export const loadAdminOrganizations = async () =>
  requestOrganizations('/users/admin/organizations', { method: 'GET', headers: {} }, 'Не удалось загрузить организации.');

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
        const label = item.full_name ? item.full_name + ' · ' + item.email : item.email;
        const details = item.raw_position || item.job_description || item.raw_duties || '';
        return (
          '<div class="admin-organization-member">' +
          '<div><strong>' +
          escapeHtml(label) +
          '</strong>' +
          (details ? '<span>' + escapeHtml(details) + '</span>' : '') +
          '</div>' +
          '<button type="button" data-action="reset-member-password" data-value="' +
          escapeHtml(item.email) +
          '">Сбросить пароль</button>' +
          '<button type="button" data-action="delete-member" data-value="' +
          escapeHtml(item.email) +
          '" aria-label="Отвязать">×</button>' +
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
    adminOrganizationsList.innerHTML = '<p class="report-empty-state">Организации пока не созданы.</p>';
    return;
  }
  adminOrganizationsList.innerHTML = organizations
    .map((org) => {
      const orgId = Number(org.id);
      const isActive = org.is_active !== false;
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
        ' отчетов</span><button class="ghost-button compact-ghost danger" type="button" data-action="delete-organization">' +
        actionLabel +
        '</button></div>' +
        '</div>' +
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
