import { reportHeader } from '../components/report-header.js';
import { bindReportPdf } from '../utils/report-download.js';
import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import { reportsPanel, profileHistoryList } from '../dom.js';
import { PROFILE_HISTORY_PAGE_SIZE } from '../config.js';
import { escapeHtml, formatProfileDate } from '../utils/format.js';
import { readApiResponse } from '../api.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { openReport } from './report.js';

let historyRequestEpoch = 0;

const statusLabels = {
  processing: 'Отчёт готовится',
  results_ready: 'Результат готов, отчёт готовится',
  failed: 'Не удалось подготовить отчёт. Ответы сохранены.',
  report_ready: 'Отчёт доступен',
};

export const renderReportsPage = () => {
  const closedStatuses = new Set(['processing', 'results_ready', 'failed', 'report_ready']);
  const cycles = (state.reportHistoryCycles || []).filter((item) =>
    item.collection_closed_at || closedStatuses.has(item.status));
  profileHistoryList.replaceChildren();
  if (!cycles.length) {
    profileHistoryList.innerHTML = '<p class="report-empty-state">Предыдущих завершённых оценок пока нет.</p>';
    return;
  }

  const totalPages = Math.ceil(cycles.length / PROFILE_HISTORY_PAGE_SIZE);
  state.profileHistoryPage = Math.min(Math.max(1, state.profileHistoryPage || 1), totalPages);
  const start = (state.profileHistoryPage - 1) * PROFILE_HISTORY_PAGE_SIZE;
  for (const item of cycles.slice(start, start + PROFILE_HISTORY_PAGE_SIZE)) {
    const card = document.createElement('article');
    card.className = 'profile-history-accordion cycle-report';
    card.dataset.cycleId = item.cycle_id;
    const label = item.status === 'report_ready' && item.report_id
      ? statusLabels.report_ready : statusLabels[item.status] || statusLabels.processing;
    card.innerHTML = `<h3>${escapeHtml(item.program_name || 'Программа оценки не указана')}</h3>` +
      `<p class="cycle-report-date">${escapeHtml(formatProfileDate(item.collection_closed_at))}</p>` +
      `<p class="cycle-report-status">${escapeHtml(label)}</p>`;
    if (item.status === 'report_ready' && item.report_id) {
      const open = document.createElement('button');
      open.type = 'button'; open.className = 'ghost-button cycle-report-open';
      open.textContent = 'Открыть отчёт';
      open.addEventListener('click', () => openReport({
        returnTarget: 'reports', m8CycleId: item.cycle_id, m8ReportId: item.report_id,
      }));
      const pdf = document.createElement('button');
      pdf.type = 'button';
      pdf.className = 'primary-button cycle-report-pdf';

      pdf.textContent = 'Скачать PDF';
      const status = document.createElement('p');
      status.className = 'report-pdf-status'; status.setAttribute('role', 'status');
      bindReportPdf(pdf, { status,
        url: `/users/assessment/m8/reports/${encodeURIComponent(item.report_id)}/pdf`,
        filename: `4k-report-${item.report_id}.pdf`,
      });
      card.append(open, pdf, status);
    } else {
      const refresh = document.createElement('button');
      refresh.type = 'button'; refresh.className = 'ghost-button';
      refresh.textContent = 'Обновить состояние';
      refresh.addEventListener('click', () => void openReports());
      card.append(refresh);
    }
    profileHistoryList.appendChild(card);
  }

  if (totalPages > 1) {
    const pager = document.createElement('nav');
    pager.className = 'profile-history-pagination';
    pager.setAttribute('aria-label', 'Страницы истории оценок');
    const previous = document.createElement('button');
    previous.type = 'button'; previous.className = 'ghost-button compact-ghost';
    previous.textContent = 'Назад'; previous.disabled = state.profileHistoryPage === 1;
    const next = document.createElement('button');
    next.type = 'button'; next.className = 'ghost-button compact-ghost';
    next.textContent = 'Вперёд'; next.disabled = state.profileHistoryPage === totalPages;
    const position = document.createElement('span');
    position.className = 'profile-history-page-indicator';
    position.textContent = `${state.profileHistoryPage} из ${totalPages}`;
    previous.addEventListener('click', () => { state.profileHistoryPage -= 1; renderReportsPage(); });
    next.addEventListener('click', () => { state.profileHistoryPage += 1; renderReportsPage(); });
    pager.append(previous, position, next);
    profileHistoryList.appendChild(pager);
  }
};

export const openReports = async () => {
  reportHeader(reportsPanel).updateUser(state.pendingUser);
  const ownerId = state.pendingUser?.id;
  const identityEpoch = state.identityEpoch;
  const requestEpoch = ++historyRequestEpoch;
  ++state.reportRequestEpoch;
  setCurrentScreen('reports');
  persistAssessmentContext();
  syncUrlState('reports');
  hideAllPanels();
  reportsPanel.classList.remove('hidden');
  profileHistoryList.innerHTML = '<p class="report-empty-state">Загружаем историю прохождений…</p>';
  const isCurrent = () => requestEpoch === historyRequestEpoch
    && state.identityEpoch === identityEpoch && state.pendingUser?.id === ownerId
    && state.currentScreen === 'reports';
  try {
    const response = await fetch('/users/assessment/m8/history', { credentials: 'same-origin' });
    const data = await readApiResponse(response, 'Не удалось загрузить историю оценок.');
    if (!isCurrent()) return;
    if (!Array.isArray(data.cycles)) throw new Error('Некорректный ответ истории оценок.');
    state.reportHistoryCycles = data.cycles;
    renderReportsPage();
  } catch (error) {
    if (!isCurrent()) return;
    profileHistoryList.innerHTML = `<p class="report-empty-state" role="alert">${escapeHtml(error.message)}</p>`;
    const retry = document.createElement('button');
    retry.type = 'button'; retry.className = 'ghost-button';
    retry.textContent = 'Повторить загрузку';
    retry.addEventListener('click', () => void openReports());
    profileHistoryList.appendChild(retry);
  }
};
