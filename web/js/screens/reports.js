import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import { reportsPanel, profileHistoryList } from '../dom.js';
import { PROFILE_HISTORY_PAGE_SIZE } from '../config.js';
import { escapeHtml, formatProfileDate } from '../utils/format.js';
import { readApiResponse } from '../api.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { loadProfileSummary, renderProfile } from './profile.js';
import { loadSkillAssessments, openReport, buildProfileSkillsMarkup } from './report.js';

export const openProfileHistoryReport = async (sessionId, triggerButton = null) => {
  if (!state.pendingUser?.id || !sessionId) {
    return;
  }

  const ownerId = state.pendingUser.id; const epoch = state.identityEpoch;
  const previousSessionId = state.assessmentSessionId;
  const previousSkillAssessments = state.skillAssessments;
  const previousReportInterpretation = state.reportInterpretation;
  const previousButtonText = triggerButton ? triggerButton.textContent : '';

  if (triggerButton) {
    triggerButton.disabled = true;
    triggerButton.textContent = 'Открываем...';
  }

  try {
    state.assessmentSessionId = sessionId;
    state.reportCompetencyTab = 'Коммуникация';
    persistAssessmentContext();
    await loadSkillAssessments();
    if (state.identityEpoch !== epoch || state.pendingUser?.id !== ownerId) return;
    openReport({ returnTarget: 'reports' });
  } catch (error) {
    if (state.identityEpoch !== epoch || state.pendingUser?.id !== ownerId) return;
    state.assessmentSessionId = previousSessionId;
    state.skillAssessments = previousSkillAssessments;
    state.reportInterpretation = previousReportInterpretation;
    persistAssessmentContext();
    if (triggerButton) {
      triggerButton.textContent = 'Не удалось открыть';
      window.setTimeout(() => {
        triggerButton.disabled = false;
        triggerButton.textContent = previousButtonText || 'Открыть отчет';
      }, 1800);
    }
    console.error('Failed to open history report', error);
  }
};

export const loadProfileSessionSkills = async (sessionId) => {
  if (!state.pendingUser?.id || !sessionId) {
    state.profileSkillAssessments = [];
    renderProfile();
    return;
  }
  const ownerId = state.pendingUser.id; const epoch = state.identityEpoch;
  const response = await fetch('/users/' + ownerId + '/assessment/' + sessionId + '/skill-assessments');
  const data = await readApiResponse(response, 'Не удалось загрузить навыки по выбранной попытке.');
  if (state.pendingUser?.id !== ownerId || state.identityEpoch !== epoch) return;
  state.profileSkillAssessments = data;
  state.profileSkillsBySession[sessionId] = data;
  renderReportsPage();
};

export const renderReportsPage = () => {
  const summary = state.profileSummary;
  profileHistoryList.innerHTML = '';
  const cycles = summary?.cycle_history || summary?.cycle_reports || [];
  for (const item of cycles) {
    const card = document.createElement('article');
    card.className = 'profile-history-accordion cycle-report';
    card.dataset.cycleId = item.cycle_id;
    const labels = {collecting:'Оценка ещё не завершена', processing:'Результат готовится', results_ready:'Результат готов, отчёт готовится', failed:'Техническая ошибка. Обработка требует восстановления.', report_ready:'Отчёт доступен'};
    if (!item.report_id) {
      card.innerHTML = `<h3>Оценка от ${escapeHtml(formatProfileDate(item.cycle_created_at || item.created_at))}</h3><p>${escapeHtml(labels[item.status] || 'Результат пока недоступен')}</p>`;
      const refresh = document.createElement('button'); refresh.type = 'button'; refresh.className = 'ghost-button'; refresh.textContent = 'Обновить состояние';
      refresh.addEventListener('click', () => { void openReports(); }); card.appendChild(refresh); profileHistoryList.appendChild(card); continue;
    }
    card.innerHTML = `<h3>Оценка от ${escapeHtml(formatProfileDate(item.cycle_created_at || item.created_at))}</h3><p>Отчёт доступен</p>` +
      `<label>Сохранённая версия<select aria-label="Версия отчёта">${item.versions.map((v) => `<option value="${escapeHtml(v.report_id)}">Результат ${v.results_revision_no} · отчёт ${v.revision_no}</option>`).join('')}</select></label>` +
      '<button type="button" class="ghost-button cycle-report-open">Открыть отчёт</button>' +
      '<a class="primary-button cycle-report-pdf">Скачать PDF</a>';
    const select = card.querySelector('select');
    const pdf = card.querySelector('.cycle-report-pdf');
    const updateDownload = () => { pdf.href = `/users/assessment/m8/reports/${encodeURIComponent(select.value)}/pdf`; };
    updateDownload(); select.addEventListener('change', updateDownload);
    card.querySelector('.cycle-report-open').addEventListener('click', () => {
      openReport({returnTarget: 'reports', m8CycleId: item.cycle_id, m8ReportId: select.value});
    });
    profileHistoryList.appendChild(card);
  }
  if (!summary?.history?.length && !cycles.length) {
    profileHistoryList.innerHTML = '<p class="report-empty-state">Пользователь еще не проходил оценку компетенций.</p>';
  } else if (summary?.history?.length) {
    const heading = document.createElement('h3');
    heading.textContent = 'Архив прежних оценок';
    profileHistoryList.appendChild(heading);
    const history = Array.isArray(summary.history) ? summary.history : [];
    const selectedIndex = state.profileSelectedSessionId
      ? history.findIndex((item) => item.session_id === state.profileSelectedSessionId)
      : -1;
    if (selectedIndex >= 0) {
      state.profileHistoryPage = Math.floor(selectedIndex / PROFILE_HISTORY_PAGE_SIZE) + 1;
    }

    const totalPages = Math.max(1, Math.ceil(history.length / PROFILE_HISTORY_PAGE_SIZE));
    state.profileHistoryPage = Math.min(Math.max(1, state.profileHistoryPage || 1), totalPages);
    const pageStart = (state.profileHistoryPage - 1) * PROFILE_HISTORY_PAGE_SIZE;
    const pageItems = history.slice(pageStart, pageStart + PROFILE_HISTORY_PAGE_SIZE);

    pageItems.forEach((item) => {
      const skills = state.profileSkillsBySession[item.session_id] || [];
      const expanded = state.profileSelectedSessionId === item.session_id;
      const card = document.createElement('article');
      card.className = 'profile-history-accordion' + (expanded ? ' active' : '');
      const statusVariant = item.status === 'completed' ? 'done' : item.status === 'active' ? 'active' : 'draft';
      const statusLabel =
        item.status === 'completed' ? 'Завершена' : item.status === 'active' ? 'В процессе' : 'Черновик';
      const scoreText = item.overall_score_percent != null ? item.overall_score_percent + '%' : '—';
      const scoreClass = item.overall_score_percent != null ? '' : ' empty';
      card.innerHTML =
        '<button type="button" class="profile-history-item" aria-expanded="' +
        (expanded ? 'true' : 'false') +
        '">' +
        '<div class="profile-history-item-main">' +
        '<span class="profile-history-item-title">Сессия #' +
        item.session_id +
        '</span>' +
        '<span class="profile-history-item-sub">' +
        formatProfileDate(item.started_at) +
        ' · ' +
        item.completed_cases +
        '/' +
        item.total_cases +
        ' кейсов</span>' +
        '</div>' +
        '<span class="profile-history-item-status ' +
        statusVariant +
        '">' +
        statusLabel +
        '</span>' +
        '<span class="profile-history-item-score' +
        scoreClass +
        '">' +
        scoreText +
        '</span>' +
        '<span class="profile-history-item-chevron" aria-hidden="true"></span>' +
        '</button>' +
        '<div class="profile-history-panel' +
        (expanded ? ' expanded' : '') +
        '">' +
        '<div class="profile-history-panel-actions">' +
        '<button type="button" class="ghost-button compact-ghost profile-history-report-button" data-session-id="' +
        item.session_id +
        '">Открыть отчет</button>' +
        '<button type="button" class="primary-button compact-primary profile-history-download-button" data-session-id="' +
        item.session_id +
        '"><img class="button-icon" src="/web/assets/icons/download-icon.svg" alt="" aria-hidden="true">Скачать PDF</button>' +
        '</div>' +
        '<div class="profile-history-panel-body">' +
        (item.expert_comment
          ? '<div class="profile-history-expert-comment"><span>Комментарий эксперта</span><p>' +
            escapeHtml(item.expert_comment) +
            '</p></div>'
          : '') +
        (expanded ? buildProfileSkillsMarkup(skills) : '') +
        '</div>' +
        '</div>';
      card.querySelector('.profile-history-item').addEventListener('click', () => {
        if (expanded) {
          state.profileSelectedSessionId = null;
          state.profileSkillAssessments = [];
          renderReportsPage();
          return;
        }
        state.profileSelectedSessionId = item.session_id;
        void loadProfileSessionSkills(item.session_id);
      });
      const reportButton = card.querySelector('.profile-history-report-button');
      if (reportButton) {
        reportButton.addEventListener('click', (event) => {
          event.stopPropagation();
          void openProfileHistoryReport(item.session_id, reportButton);
        });
      }
      const pdfButton = card.querySelector('.profile-history-download-button');
      if (pdfButton) {
        pdfButton.addEventListener('click', (event) => {
          event.stopPropagation();
          if (!state.pendingUser?.id) {
            return;
          }
          window.location.href = '/users/' + state.pendingUser.id + '/assessment/' + item.session_id + '/report.pdf';
        });
      }
      profileHistoryList.appendChild(card);
    });

    if (totalPages > 1) {
      const pagination = document.createElement('div');
      pagination.className = 'profile-history-pagination';
      pagination.innerHTML =
        '<button type="button" class="ghost-button compact-ghost profile-history-page-button prev"' +
        (state.profileHistoryPage <= 1 ? ' disabled' : '') +
        '>Назад</button>' +
        '<span class="profile-history-page-indicator">Страница ' +
        state.profileHistoryPage +
        ' из ' +
        totalPages +
        '</span>' +
        '<button type="button" class="ghost-button compact-ghost profile-history-page-button next"' +
        (state.profileHistoryPage >= totalPages ? ' disabled' : '') +
        '>Вперед</button>';

      const prevButton = pagination.querySelector('.profile-history-page-button.prev');
      const nextButton = pagination.querySelector('.profile-history-page-button.next');
      if (prevButton) {
        prevButton.addEventListener('click', () => {
          state.profileHistoryPage = Math.max(1, state.profileHistoryPage - 1);
          renderReportsPage();
        });
      }
      if (nextButton) {
        nextButton.addEventListener('click', () => {
          state.profileHistoryPage = Math.min(totalPages, state.profileHistoryPage + 1);
          renderReportsPage();
        });
      }
      profileHistoryList.appendChild(pagination);
    }
  }
};

export const openReports = async () => {
  const ownerId = state.pendingUser?.id;
  const epoch = state.identityEpoch;
  setCurrentScreen('reports');
  persistAssessmentContext();
  syncUrlState('reports');
  hideAllPanels();
  reportsPanel.classList.remove('hidden');
  profileHistoryList.innerHTML = '<p class="report-empty-state">Загружаем историю прохождений...</p>';

  try {
    await loadProfileSummary();
    if (state.identityEpoch !== epoch || state.pendingUser?.id !== ownerId || state.currentScreen !== 'reports') return;
    if (state.profileSelectedSessionId) {
      await loadProfileSessionSkills(state.profileSelectedSessionId);
      return;
    }
    state.profileSkillAssessments = [];
    renderReportsPage();
  } catch (error) {
    if (state.identityEpoch !== epoch || state.pendingUser?.id !== ownerId || state.currentScreen !== 'reports') return;
    profileHistoryList.innerHTML = '<p class="report-empty-state">' + escapeHtml(error.message) + '</p>';
  }
};
