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

const dateLabel = (value) => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(value)) : '—';
const statusLabels = { preparing: 'Готовится', ready: 'Готов', failed: 'Не удалось подготовить' };
const option = (value, label, selected) => '<option value="' + escapeHtml(value) + '"' +
  (String(value) === String(selected) ? ' selected' : '') + '>' + escapeHtml(label) + '</option>';

export const renderAdminReports = () => {
  const data = state.adminReports;
  if (!data) return;
  adminReportsSearch.value = state.adminReportsSearch || '';
  organization.innerHTML = (data.organizations || []).map((item) => option(item.id, item.name, data.organization_id)).join('');
  program.innerHTML = option('', 'Все программы', state.adminReportsProgram || '') +
    (data.programs || []).map((item) => option(item, item, state.adminReportsProgram)).join('');
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
          customerAccess: true, returnTarget: 'admin-reports' });
      });
      const pdf = document.createElement('a');
      pdf.className = 'ghost-button compact-ghost';
      pdf.textContent = 'PDF';
      pdf.href = '/users/admin/m8-access/reports/' + encodeURIComponent(item.report_id) + '/pdf';
      actions.append(open, pdf);
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
    program: state.adminReportsProgram || '', status: state.adminReportsStatus || '' });
  if (state.adminReportsOrganizationId) params.set('organization_id', String(state.adminReportsOrganizationId));
  const response = await fetch('/users/admin/m8-access/reports?' + params, { credentials: 'same-origin' });
  const data = await readApiResponse(response, 'Не удалось загрузить список Report.');
  if (epoch !== requestEpoch || identityEpoch !== state.identityEpoch || state.currentScreen !== 'admin-reports') return;
  state.adminReports = data;
  state.adminReportsOrganizationId = data.organization_id;
  persistAssessmentContext();
  renderAdminReports();
};

const refresh = () => {
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

export const openAdminReports = async () => {
  setCurrentScreen('admin-reports');
  syncUrlState('admin-reports');
  hideAllPanels();
  adminReportsPanel.classList.remove('hidden');
  refresh();
};

adminReportsSearch?.addEventListener('input', () => {
  clearTimeout(searchTimer);
  state.adminReportsSearch = adminReportsSearch.value;
  state.adminReportsPage = 1;
  searchTimer = setTimeout(refresh, 250);
});
organization?.addEventListener('change', () => {
  state.adminReportsOrganizationId = Number(organization.value);
  state.adminReportsProgram = '';
  state.adminReportsPage = 1;
  state.adminReports = null;
  persistAssessmentContext();
  refresh();
});
program?.addEventListener('change', () => {
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
  state.adminReportsStatus = '';
  state.adminReportsPage = 1;
  persistAssessmentContext();
  refresh();
});
