import { bindReportPdf } from '../../utils/report-download.js';
import { state, persistAssessmentContext, setCurrentScreen } from '../../state.js';
import { adminReportsPanel, adminReportsSearch, adminReportsFound, adminReportsList,
  adminReportsPageSummary, adminReportsPageIndicator, adminReportsPrevButton,
  adminReportsNextButton } from '../../dom.js';
import { escapeHtml } from '../../utils/format.js';
import { readApiResponse } from '../../api.js';
import { hideAllPanels, syncUrlState } from '../../router.js';

const organization = document.getElementById('admin-reports-organization');
const program = document.getElementById('admin-reports-program');
const status = document.getElementById('admin-reports-status');
const clear = document.getElementById('admin-reports-clear');
const PAGE_SIZE = 12;
let requestEpoch = 0;
let searchTimer;
let scopedProgram = null;

const dateLabel = (value) => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(value)) : '—';
const statusLabels = { preparing: 'Готовится', ready: 'Готов', failed: 'Не удалось подготовить' };
const option = (value, label, selected) => '<option value="' + escapeHtml(value) + '"' +
  (String(value) === String(selected) ? ' selected' : '') + '>' + escapeHtml(label) + '</option>';

export const renderAdminReports = () => {
  const data = state.adminReports;
  if (!data) return;
  adminReportsSearch.value = state.adminReportsSearch || '';
  organization.innerHTML = (data.organizations || []).map((item) => option(item.id, item.name, data.organization_id)).join('');
  const programs = new Set(data.programs || []);
  if (state.adminReportsProgram) programs.add(state.adminReportsProgram);
  const exactValue = scopedProgram ? 'program-definition:' + scopedProgram.id : '';
  program.innerHTML = option('', 'Все программы', exactValue || state.adminReportsProgram || '') +
    (scopedProgram ? option(exactValue, scopedProgram.label, exactValue) : '') +
    [...programs].map((item) => option(item, item, state.adminReportsProgram)).join('');
  status.value = state.adminReportsStatus || '';
  adminReportsFound.textContent = 'Найдено: ' + data.total;
  adminReportsList.innerHTML = '';
  for (const item of data.items || []) {
    const row = document.createElement('article');
    row.className = 'admin-report-row admin-report-row--m8';
    const ready = item.status === 'ready' && item.report_id;
    row.innerHTML = '<div class="admin-report-cell admin-report-user"><strong>' +
      escapeHtml(item.full_name || 'Участник') + '</strong></div>' +
      '<div class="admin-report-cell">' + escapeHtml(item.program_name || '—') + '</div>' +
      '<div class="admin-report-cell admin-report-date">' + escapeHtml(dateLabel(item.collection_closed_at)) + '</div>' +
      '<div class="admin-report-cell admin-report-status"><span class="admin-status-pill ' +
      (item.status === 'ready' ? 'done' : item.status === 'failed' ? 'draft' : 'active') + '">' +
      statusLabels[item.status] + '</span></div>' +
      '<div class="admin-report-cell admin-report-download-action"></div>';
    if (ready) {
      const actions = row.lastElementChild;
      const open = document.createElement('button');
      open.className = 'ghost-button compact-ghost';
      open.type = 'button';
      open.textContent = 'Открыть';
      open.addEventListener('click', async () => {
        const module = await import('../report.js');
        module.openReport({ m8CycleId: item.cycle_id, m8ReportId: item.report_id,
          customerAccess: true, returnTarget: 'admin-reports',
          returnToManagement: window.history.state?.returnToManagement === true });
      });
      const pdf = document.createElement('button');
      pdf.type = 'button';
      pdf.className = 'ghost-button compact-ghost';
      pdf.textContent = 'PDF';
      const status = document.createElement('span');
      status.className = 'report-pdf-status'; status.setAttribute('role', 'status');
      bindReportPdf(pdf, { status,
        url: '/users/admin/m8-access/reports/' + encodeURIComponent(item.report_id) + '/pdf',
        filename: `4k-report-${item.report_id}.pdf`,
      });
      actions.append(open, pdf, status);
    }
    adminReportsList.appendChild(row);
  }
  if (!data.items?.length) {
    adminReportsList.innerHTML = '<p class="report-empty-state">По текущим фильтрам закрытые оценки не найдены.</p>';
  }
  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const shown = Math.min(data.total, (data.page - 1) * PAGE_SIZE + data.items.length);
  adminReportsPageSummary.textContent = 'Показано ' + shown + ' из ' + data.total;
  adminReportsPageIndicator.textContent = data.page + ' / ' + totalPages;
  adminReportsPrevButton.disabled = data.page <= 1;
  adminReportsNextButton.disabled = data.page >= totalPages;
};

export const loadAdminReports = async () => {
  const epoch = ++requestEpoch;
  const identityEpoch = state.identityEpoch;
  const params = new URLSearchParams({ page: String(state.adminReportsPage || 1),
    page_size: String(PAGE_SIZE), query: state.adminReportsSearch || '',
    program: scopedProgram ? '' : state.adminReportsProgram || '', status: state.adminReportsStatus || '' });
  if (state.adminReportsOrganizationId) params.set('organization_id', String(state.adminReportsOrganizationId));
  if (scopedProgram) params.set('program_definition_id', String(scopedProgram.id));
  const response = await fetch('/users/admin/m8-access/reports?' + params, { credentials: 'same-origin' });
  const data = await readApiResponse(response, 'Не удалось загрузить список отчётов.');
  if (epoch !== requestEpoch || identityEpoch !== state.identityEpoch || state.currentScreen !== 'admin-reports') return;
  state.adminReports = data;
  state.adminReportsOrganizationId = data.organization_id;
  persistAssessmentContext();
  saveReportsView();
  renderAdminReports();
};

const saveReportsView = () => {
  window.history.replaceState({ ...window.history.state, adminReportsView: {
    ownerId: String(state.pendingUser?.id || ''),
    organizationId: state.adminReportsOrganizationId,
    search: state.adminReportsSearch,
    program: state.adminReportsProgram,
    scopedProgram,
    status: state.adminReportsStatus,
    page: state.adminReportsPage,
  } }, '');
};

const refresh = () => {
  saveReportsView();
  const epoch = requestEpoch + 1;
  adminReportsList.innerHTML = '<p class="report-empty-state">Загружаем закрытые оценки...</p>';
  void loadAdminReports().catch((error) => {
    if (requestEpoch !== epoch || state.currentScreen !== 'admin-reports') return;
    adminReportsList.innerHTML = '<p class="report-empty-state">' + escapeHtml(error.message) + '</p>';
  });
};

export const changeAdminReportsPage = (direction) => {
  state.adminReportsPage = Math.max(1, (state.adminReportsPage || 1) + direction);
  persistAssessmentContext();
  refresh();
};

export const openAdminReports = async ({
  organizationId, programDefinitionId, programLabel,
  managementNavigation = window.history.state?.managementNavigation,
  returnToManagement = window.history.state?.returnToManagement === true,
} = {}) => {
  clearTimeout(searchTimer);
  scopedProgram = null;
  if (organizationId) {
    state.adminReportsOrganizationId = organizationId;
    state.adminReportsProgram = '';
    if (programDefinitionId > 0) scopedProgram = { id: programDefinitionId, label: programLabel };
    state.adminReportsPage = 1;
    state.adminReportsSearch = '';
    state.adminReportsStatus = '';
    state.adminReports = null;
  } else {
    const saved = window.history.state?.adminReportsView;
    if (saved?.ownerId === String(state.pendingUser?.id || '')) {
      state.adminReportsOrganizationId = saved.organizationId;
      state.adminReportsSearch = saved.search;
      state.adminReportsProgram = saved.program;
      state.adminReportsStatus = saved.status;
      state.adminReportsPage = saved.page;
      scopedProgram = saved.scopedProgram || null;
    }
  }
  setCurrentScreen('admin-reports');
  syncUrlState('admin-reports');
  window.history.replaceState({ ...window.history.state, returnToManagement,
    managementNavigation: returnToManagement ? managementNavigation : null }, '');
  document.getElementById('admin-reports-back-button').textContent = returnToManagement ? 'К управлению' : 'Назад';
  hideAllPanels();
  adminReportsPanel.classList.remove('hidden');
  refresh();
};

adminReportsSearch?.addEventListener('input', () => {
  clearTimeout(searchTimer);
  state.adminReportsSearch = adminReportsSearch.value;
  state.adminReportsPage = 1;
  saveReportsView();
  searchTimer = setTimeout(refresh, 250);
});
organization?.addEventListener('change', () => {
  state.adminReportsOrganizationId = Number(organization.value);
  state.adminReportsProgram = '';
  scopedProgram = null;
  state.adminReportsPage = 1;
  state.adminReports = null;
  persistAssessmentContext();
  refresh();
});
program?.addEventListener('change', () => {
  scopedProgram = null;
  state.adminReportsProgram = program.value;
  state.adminReportsPage = 1;
  persistAssessmentContext();
  refresh();
});
status?.addEventListener('change', () => {
  state.adminReportsStatus = status.value;
  state.adminReportsPage = 1;
  persistAssessmentContext();
  refresh();
});
clear?.addEventListener('click', () => {
  state.adminReportsSearch = '';
  state.adminReportsProgram = '';
  scopedProgram = null;
  state.adminReportsStatus = '';
  state.adminReportsPage = 1;
  persistAssessmentContext();
  refresh();
});
