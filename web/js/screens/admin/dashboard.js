import { state, persistAssessmentContext, setCurrentScreen } from '../../state.js';
import {
  adminPanel,
  adminUserName,
  adminUserRole,
  adminAvatar,
  adminTitle,
  adminActivityTitle,
  adminMetricsGrid,
  adminInsightsGrid,
} from '../../dom.js';
import { sanitizeDisplayRole, buildInitials } from '../../utils/format.js';
import { readApiResponse } from '../../api.js';
import { hideAllPanels, syncUrlState } from '../../router.js';
import {
  renderAdminCompetencyBarChart,
  renderAdminMbtiPieChart,
  renderAdminActivityBarChart,
} from './charts.js';

const renderAdminSection = (sectionName, render) => {
  try {
    render();
  } catch (error) {
    console.error('Failed to render admin dashboard section:', sectionName, error);
  }
};

export const renderAdminDashboard = () => {
  const adminDashboard = state.adminDashboard;
  const user = state.pendingUser;
  if (!adminDashboard || !user) {
    return;
  }
  const adminPosition = sanitizeDisplayRole(user.job_description || '') || 'Администратор';

  adminUserName.textContent = user.full_name || 'Администратор системы';
  adminUserRole.textContent = adminPosition;
  adminAvatar.textContent = buildInitials(user.full_name || 'Администратор системы');
  adminTitle.textContent = adminDashboard.title || 'Сводный отчет';
  adminActivityTitle.innerHTML = 'Количество завершенных ассессментов за период';

  adminMetricsGrid.innerHTML = '';
  (adminDashboard.metrics || []).forEach((metric) => {
    const card = document.createElement('article');
    card.className = 'card admin-metric-card';
    card.innerHTML =
      '<span>' +
      metric.label +
      '</span>' +
      '<strong>' +
      metric.value +
      '</strong>' +
      '<small>' +
      (metric.delta || '') +
      '</small>';
    adminMetricsGrid.appendChild(card);
  });

  renderAdminSection('competency chart', () => {
    renderAdminCompetencyBarChart(adminDashboard.competency_average || []);
  });

  renderAdminSection('mbti chart', () => {
    renderAdminMbtiPieChart(adminDashboard.mbti_distribution || []);
  });

  adminInsightsGrid.innerHTML = '';
  (adminDashboard.insights || []).forEach((item) => {
    const card = document.createElement('article');
    card.className = 'card card--inset admin-insight-card';
    card.innerHTML = '<strong>' + item.title + '</strong><p>' + item.description + '</p>';
    adminInsightsGrid.appendChild(card);
  });

  renderAdminSection('activity chart', () => {
    renderAdminActivityBarChart(adminDashboard);
  });
};

export const loadAdminDashboard = async (periodKey = state.adminPeriodKey || '30d') => {
  const response = await fetch('/users/admin/dashboard?period=' + encodeURIComponent(periodKey), {
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось загрузить административный дашборд.');
  state.adminDashboard = data;
  state.adminPeriodKey = data.activity_period_key || periodKey;
  persistAssessmentContext();
};

export const openAdminDashboard = () => {
  setCurrentScreen('admin');
  persistAssessmentContext();
  syncUrlState('admin');
  hideAllPanels();
  adminPanel.classList.remove('hidden');
  renderAdminDashboard();
};
