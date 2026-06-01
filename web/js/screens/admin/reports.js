import { state, persistAssessmentContext, setCurrentScreen } from '../../state.js';
import {
  adminReportsPanel,
  adminReportsTitle,
  adminReportsSubtitle,
  adminReportsSearch,
  adminReportsPdfButton,
  adminReportsFound,
  adminReportsList,
  adminReportsSummaryScore,
  adminReportsPageSummary,
  adminReportsPageIndicator,
  adminReportsPrevButton,
  adminReportsNextButton,
  adminReportsExpertGroupButton,
  adminReportsGroupDialog,
  adminReportsGroupDialogClose,
  adminReportsGroupDialogList,
  adminReportsGroupDialogSummary,
  adminReportsGroupDialogExport,
  adminReportsBackButton,
} from '../../dom.js';
import { ADMIN_REPORTS_PAGE_SIZE } from '../../config.js';
import { escapeHtml, sanitizeDisplayRole, sanitizeDisplayMetaText, buildInitials, formatAdminReportDate } from '../../utils/format.js';
import { readApiResponse } from '../../api.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
import { getAdminStatusBadgeLabel } from './skill-radar.js';
import { openAdminReportDetail } from './report-detail.js';
export const getFilteredAdminReports = () => {
  const items = Array.isArray(state.adminReports?.items) ? state.adminReports.items : [];
  const query = String(state.adminReportsSearch || '')
    .trim()
    .toLowerCase();
  if (!query) {
    return items;
  }
  return items.filter((item) => {
    const haystack = [
      item.full_name,
      item.group_name,
      item.role_name,
      item.status,
      item.phone,
      String(item.user_id),
      String(item.session_id),
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  });
};

export const renderAdminReports = () => {
  const reports = state.adminReports;
  if (!reports) {
    return;
  }

  adminReportsTitle.textContent = reports.title || 'Отдельные отчеты';
  adminReportsSubtitle.textContent =
    reports.subtitle || 'Управление и анализ индивидуальных результатов тестирования персонала.';
  if (adminReportsSearch) {
    adminReportsSearch.value = state.adminReportsSearch || '';
  }

  const filteredItems = getFilteredAdminReports();
  const totalPages = Math.max(1, Math.ceil(filteredItems.length / ADMIN_REPORTS_PAGE_SIZE));
  if (state.adminReportsPage > totalPages) {
    state.adminReportsPage = totalPages;
  }
  if (state.adminReportsPage < 1) {
    state.adminReportsPage = 1;
  }
  const pageStart = (state.adminReportsPage - 1) * ADMIN_REPORTS_PAGE_SIZE;
  const pageItems = filteredItems.slice(pageStart, pageStart + ADMIN_REPORTS_PAGE_SIZE);
  adminReportsFound.textContent = 'Найдено: ' + filteredItems.length;
  const selectedIds = new Set((state.adminReportsSelectedSessionIds || []).map((value) => Number(value)));

  const scoreValues = filteredItems.map((item) => item.score_percent).filter((value) => typeof value === 'number');
  adminReportsSummaryScore.textContent = scoreValues.length
    ? Math.round((scoreValues.reduce((sum, value) => sum + value, 0) / scoreValues.length) * 10) / 10 + '%'
    : '—';

  adminReportsList.innerHTML = '';
  if (!filteredItems.length) {
    adminReportsList.innerHTML = '<p class="report-empty-state">По текущему фильтру отчеты не найдены.</p>';
    if (adminReportsPageSummary) {
      adminReportsPageSummary.textContent = 'Показано 0 из 0 отчетов';
    }
    if (adminReportsPageIndicator) {
      adminReportsPageIndicator.textContent = '0 / 0';
    }
    if (adminReportsPrevButton) {
      adminReportsPrevButton.disabled = true;
    }
    if (adminReportsNextButton) {
      adminReportsNextButton.disabled = true;
    }
    return;
  }

  pageItems.forEach((item) => {
    const row = document.createElement('article');
    row.className = 'admin-report-row';
    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    const scorePercent = typeof item.score_percent === 'number' ? item.score_percent : 0;
    const scoreLabel = typeof item.score_percent === 'number' ? item.score_percent + '%' : '—';
    const groupName = sanitizeDisplayMetaText(item.group_name || '') || 'Не указана';
    const roleName = sanitizeDisplayRole(item.role_name || '') || 'Роль не указана';
    const isCompleted = item.status === 'Завершено';
    const checked = selectedIds.has(Number(item.session_id));
    row.innerHTML =
      '<div class="admin-report-cell admin-report-select-cell">' +
      '<label class="admin-report-select-toggle' +
      (isCompleted ? '' : ' is-disabled') +
      '">' +
      '<input class="admin-report-select-checkbox" type="checkbox" name="session_ids" form="admin-reports-expert-group-form" value="' +
      Number(item.session_id) +
      '" ' +
      (checked ? 'checked ' : '') +
      (isCompleted ? '' : 'disabled ') +
      'aria-label="Выбрать отчет по сессии ' +
      item.session_id +
      '">' +
      '</label>' +
      '</div>' +
      '<div class="admin-report-cell admin-report-user">' +
      '<div class="admin-report-copy">' +
      '<strong>' +
      item.full_name +
      '</strong>' +
      '<span>ID ' +
      item.user_id +
      '</span>' +
      '</div>' +
      '</div>' +
      '<div class="admin-report-cell admin-report-group">' +
      '<strong>' +
      groupName +
      '</strong>' +
      '<span>' +
      roleName +
      '</span>' +
      '</div>' +
      '<div class="admin-report-cell admin-report-status">' +
      '<span class="admin-status-pill ' +
      (item.status === 'Завершено' ? 'done' : item.status === 'В процессе' ? 'active' : 'draft') +
      '">' +
      item.status +
      '</span>' +
      '</div>' +
      '<div class="admin-report-cell admin-report-score">' +
      '<strong>' +
      scoreLabel +
      '</strong>' +
      '<div class="admin-report-score-track"><span style="width:' +
      scorePercent +
      '%"></span></div>' +
      '</div>' +
      '<div class="admin-report-cell admin-report-mbti">' +
      (item.mbti_type || 'Нет данных') +
      '</div>' +
      '<div class="admin-report-cell admin-report-date">' +
      formatAdminReportDate(item) +
      '</div>' +
      '<div class="admin-report-cell admin-report-download-action">' +
      '<button class="ghost-button compact-ghost admin-report-download-button" type="button" aria-label="Скачать PDF отчета по сессии ' +
      item.session_id +
      '">Скачать</button>' +
      '</div>';
    const openDetail = () => {
      void openAdminReportDetail(item.session_id);
    };
    const reportDownloadButton = row.querySelector('.admin-report-download-button');
    const selectCheckbox = row.querySelector('.admin-report-select-checkbox');
    const selectToggle = row.querySelector('.admin-report-select-toggle');
    if (selectToggle) {
      selectToggle.addEventListener('click', (event) => {
        event.stopPropagation();
      });
    }
    if (selectCheckbox) {
      selectCheckbox.addEventListener('click', (event) => {
        event.stopPropagation();
      });
      selectCheckbox.addEventListener('change', (event) => {
        event.stopPropagation();
        const sessionId = Number(item.session_id);
        const current = new Set((state.adminReportsSelectedSessionIds || []).map((value) => Number(value)));
        if (event.target.checked) {
          current.add(sessionId);
        } else {
          current.delete(sessionId);
        }
        state.adminReportsSelectedSessionIds = Array.from(current);
        renderAdminReports();
      });
    }
    if (reportDownloadButton) {
      reportDownloadButton.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        window.location.href = '/users/' + item.user_id + '/assessment/' + item.session_id + '/report.pdf';
      });
    }
    row.addEventListener('click', openDetail);
    row.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openDetail();
      }
    });
    adminReportsList.appendChild(row);
  });

  if (adminReportsPageSummary) {
    adminReportsPageSummary.textContent =
      'Показано ' + (pageStart + 1) + '–' + (pageStart + pageItems.length) + ' из ' + filteredItems.length + ' отчетов';
  }
  if (adminReportsPageIndicator) {
    adminReportsPageIndicator.textContent = state.adminReportsPage + ' / ' + totalPages;
  }
  if (adminReportsPrevButton) {
    adminReportsPrevButton.disabled = state.adminReportsPage <= 1;
  }
  if (adminReportsNextButton) {
    adminReportsNextButton.disabled = state.adminReportsPage >= totalPages;
  }
  if (adminReportsExpertGroupButton) {
    const completedCount = filteredItems.filter((item) => item.status === 'Завершено').length;
    const selectedCompletedCount = filteredItems.filter(
      (item) => item.status === 'Завершено' && selectedIds.has(Number(item.session_id)),
    ).length;
    adminReportsExpertGroupButton.disabled = completedCount <= 0;
    adminReportsExpertGroupButton.textContent =
      selectedCompletedCount > 0 ? 'Выгрузить ассесменты (' + selectedCompletedCount + ')' : 'Выгрузить ассесменты';
  }
};

export const loadAdminReports = async () => {
  const response = await fetch('/users/admin/reports', {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить подробные отчеты.');
  state.adminReports = data;
  const allowedSessionIds = new Set(
    (Array.isArray(data?.items) ? data.items : [])
      .filter((item) => item.status === 'Завершено')
      .map((item) => Number(item.session_id))
      .filter((value) => Number.isFinite(value) && value > 0),
  );
  state.adminReportsSelectedSessionIds = (state.adminReportsSelectedSessionIds || [])
    .map((value) => Number(value))
    .filter((value) => allowedSessionIds.has(value));
  state.adminReportsPage = 1;
  persistAssessmentContext();
};

export const renderAdminReportsGroupDialog = () => {
  if (!adminReportsGroupDialogList || !adminReportsGroupDialogSummary) {
    return;
  }
  const completedItems = getFilteredAdminReports().filter((item) => item.status === 'Завершено');
  const selectedIds = new Set((state.adminReportsSelectedSessionIds || []).map((value) => Number(value)));
  if (!completedItems.length) {
    adminReportsGroupDialogSummary.textContent = 'По текущему фильтру нет завершенных ассессментов для выгрузки.';
    adminReportsGroupDialogList.innerHTML = '<p class="report-empty-state">Нет завершенных ассессментов.</p>';
    if (adminReportsGroupDialogExport) {
      adminReportsGroupDialogExport.disabled = true;
    }
    return;
  }
  const selectedCount = completedItems.filter((item) => selectedIds.has(Number(item.session_id))).length;
  adminReportsGroupDialogSummary.textContent =
    selectedCount > 0 ? 'Выбрано для выгрузки: ' + selectedCount : 'Выберите завершенные ассессменты для выгрузки.';
  adminReportsGroupDialogList.innerHTML = completedItems
    .map((item) => {
      const checked = selectedIds.has(Number(item.session_id));
      const groupName = sanitizeDisplayMetaText(item.group_name || '') || 'Не указана';
      const roleName = sanitizeDisplayRole(item.role_name || '') || 'Роль не указана';
      const scoreLabel = typeof item.score_percent === 'number' ? item.score_percent + '%' : '—';
      return (
        '<label class="admin-prompt-lab-case-option">' +
        '<input type="checkbox" value="' +
        Number(item.session_id) +
        '"' +
        (checked ? ' checked' : '') +
        '>' +
        '<span class="admin-prompt-lab-case-option-copy">' +
        '<strong>' +
        escapeHtml(item.full_name || '') +
        ' · ID ' +
        escapeHtml(item.user_id) +
        '</strong>' +
        '<small>' +
        escapeHtml(groupName) +
        ' · ' +
        escapeHtml(roleName) +
        ' · ' +
        escapeHtml(scoreLabel) +
        ' · ' +
        escapeHtml(formatAdminReportDate(item)) +
        '</small>' +
        '</span>' +
        '</label>'
      );
    })
    .join('');
  if (adminReportsGroupDialogExport) {
    adminReportsGroupDialogExport.disabled = selectedCount <= 0;
  }
};

export const syncAdminReportsSelectionFromDialog = () => {
  if (!adminReportsGroupDialogList) {
    return;
  }
  state.adminReportsSelectedSessionIds = Array.from(
    adminReportsGroupDialogList.querySelectorAll('input[type="checkbox"]:checked'),
  )
    .map((node) => Number(node.value || 0))
    .filter((value) => Number.isFinite(value) && value > 0);
  renderAdminReports();
  renderAdminReportsGroupDialog();
};


export const openAdminReports = async () => {
  setCurrentScreen('admin-reports');
  persistAssessmentContext();
  syncUrlState('admin-reports');
  hideAllPanels();
  adminReportsPanel.classList.remove('hidden');
  adminReportsList.innerHTML = '<p class="report-empty-state">Загружаем подробные отчеты...</p>';
  try {
    if (!state.adminReports) {
      await loadAdminReports();
    }
    renderAdminReports();
  } catch (error) {
    adminReportsList.innerHTML = '<p class="report-empty-state">' + error.message + '</p>';
  }
};
