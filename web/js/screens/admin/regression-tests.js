import { readApiResponse } from '../../api.js';
import {
  adminRegressionTestsCleanupButton,
  adminRegressionTestsMetrics,
  adminRegressionTestsPanel,
  adminRegressionTestsResultTitle,
  adminRegressionTestsRunFullButton,
  adminRegressionTestsRunButton,
  adminRegressionTestsStatus,
  adminRegressionTestsSteps,
  adminRegressionTestsSubtitle,
  adminRegressionTestsTitle,
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

const STEP_LABELS = {
  cleanup: 'Очистка данных',
  organization: 'Организация и пользователи',
  assessment_linear_employee: 'Assessment: линейный сотрудник',
  assessment_manager: 'Assessment: менеджер',
  assessment_leader: 'Assessment: лидер',
  assertions: 'Проверка результатов',
  summary: 'Итог',
};

const getStepLabel = (name) => STEP_LABELS[String(name || '')] || name || 'Шаг';

let regressionPollTimerId = null;

const stopRegressionPolling = () => {
  if (regressionPollTimerId) {
    window.clearInterval(regressionPollTimerId);
    regressionPollTimerId = null;
  }
};

const setStatus = (message, tone = 'muted') => {
  if (!adminRegressionTestsStatus) {
    return;
  }
  adminRegressionTestsStatus.textContent = message || '';
  adminRegressionTestsStatus.classList.toggle('hidden', !message);
  adminRegressionTestsStatus.dataset.tone = tone;
};

const setButtonsDisabled = (disabled) => {
  if (adminRegressionTestsRunButton) {
    adminRegressionTestsRunButton.disabled = disabled;
    adminRegressionTestsRunButton.textContent = disabled ? 'Запускаем...' : 'Запустить smoke';
  }
  if (adminRegressionTestsRunFullButton) {
    adminRegressionTestsRunFullButton.disabled = disabled;
    adminRegressionTestsRunFullButton.textContent = disabled ? 'Прогоняем...' : 'Полный прогон';
  }
  if (adminRegressionTestsCleanupButton) {
    adminRegressionTestsCleanupButton.disabled = disabled;
  }
};

const renderMetric = (label, value, delta = '') =>
  '<article class="card admin-metric-card"><span>' +
  escapeHtml(label) +
  '</span><strong>' +
  escapeHtml(value) +
  '</strong><small>' +
  escapeHtml(delta) +
  '</small></article>';

const renderSteps = (steps = []) => {
  if (!adminRegressionTestsSteps) {
    return;
  }
  if (!steps.length) {
    adminRegressionTestsSteps.innerHTML = '<p class="report-empty-state">Запустите smoke-тест, чтобы увидеть шаги проверки.</p>';
    return;
  }
  adminRegressionTestsSteps.innerHTML = steps
    .map((step) => {
      const status = String(step.status || 'pending').toLowerCase();
      return (
        '<article class="admin-regression-test-step" data-status="' +
        escapeHtml(status) +
        '">' +
        '<strong>' +
        escapeHtml(getStepLabel(step.name)) +
        '</strong><span>' +
        escapeHtml(status) +
        '</span><p>' +
        escapeHtml(step.message || '') +
        '</p></article>'
      );
    })
    .join('');
};

const getRunProgress = (run) => {
  const steps = Array.isArray(run?.steps) ? run.steps : [];
  const total = Math.max(steps.length, 1);
  const passed = steps.filter((step) => String(step.status || '').toLowerCase() === 'passed').length;
  const failed = steps.some((step) => ['failed', 'error'].includes(String(step.status || '').toLowerCase()));
  const runningIndex = steps.findIndex((step) => String(step.status || '').toLowerCase() === 'running');
  if (run?.status === 'passed') {
    return 100;
  }
  if (failed || run?.status === 'failed') {
    return Math.round((passed / total) * 100);
  }
  const runningBonus = runningIndex >= 0 ? 0.5 : 0;
  return Math.max(5, Math.min(95, Math.round(((passed + runningBonus) / total) * 100)));
};

const renderRunProgress = (run) => {
  if (!adminRegressionTestsSteps || !run || !['running', 'passed', 'failed'].includes(String(run.status || '').toLowerCase())) {
    return '';
  }
  const progress = getRunProgress(run);
  const elapsed = Number(run.duration_seconds || 0);
  const currentStep = (run.steps || []).find((step) => String(step.status || '').toLowerCase() === 'running');
  const statusText =
    run.status === 'running'
      ? currentStep?.message || run.summary || 'Полный прогон выполняется.'
      : run.summary || 'Прогон завершен.';
  return (
    '<section class="admin-regression-progress" aria-label="Прогресс регрессионного теста">' +
    '<div class="admin-regression-progress-row"><strong>' +
    escapeHtml(run.title || 'Regression') +
    '</strong><span>' +
    escapeHtml(progress + '% · ' + elapsed.toFixed(1) + ' сек') +
    '</span></div><div class="admin-regression-progress-track"><span style="width: ' +
    escapeHtml(progress) +
    '%"></span></div><p>' +
    escapeHtml(statusText) +
    '</p></section>'
  );
};

export const renderAdminRegressionTests = () => {
  const data = state.adminRegressionTests || {};
  const lastRun = data.last_run || null;

  if (adminRegressionTestsTitle) {
    adminRegressionTestsTitle.textContent = data.title || 'Регрессионные тесты';
  }
  if (adminRegressionTestsSubtitle) {
    adminRegressionTestsSubtitle.textContent =
      data.subtitle || 'Быстрые проверки организации, пользователей, отчетов и MBTI readiness.';
  }
  if (adminRegressionTestsMetrics) {
    adminRegressionTestsMetrics.innerHTML =
      renderMetric('MBTI', data.mbti_enabled ? 'Включен' : 'Выключен', data.mbti_store_available ? 'Индекс доступен' : 'Индекс не загружен') +
      renderMetric('Последний запуск', lastRun ? lastRun.status : 'Нет', lastRun ? lastRun.duration_seconds + ' сек' : 'Smoke еще не запускался') +
      renderMetric('Тестовые данные', '__autotest__', data.cleanup_hint || 'Удаляются отдельно') +
      renderMetric('Режимы', 'Smoke / Full', 'Full запускает реальные assessment-сессии');
  }
  if (adminRegressionTestsResultTitle) {
    adminRegressionTestsResultTitle.textContent = lastRun
      ? lastRun.title + ': ' + lastRun.status
      : 'Тесты еще не запускались';
  }
  if (lastRun?.status === 'running') {
    setButtonsDisabled(true);
    setStatus(lastRun.summary || 'Полный регрессионный прогон выполняется...', 'muted');
  } else {
    stopRegressionPolling();
  }
  if (adminRegressionTestsSteps) {
    adminRegressionTestsSteps.parentElement?.querySelector('.admin-regression-progress')?.remove();
    adminRegressionTestsSteps.insertAdjacentHTML('beforebegin', renderRunProgress(lastRun));
  }
  renderSteps(lastRun?.steps || []);
};

const pollAdminRegressionTests = async () => {
  try {
    await loadAdminRegressionTests();
  } catch (error) {
    setStatus(error.message || 'Не удалось обновить статус полного прогона.', 'error');
  }
};

const startRegressionPolling = () => {
  stopRegressionPolling();
  regressionPollTimerId = window.setInterval(pollAdminRegressionTests, 2500);
};

export const loadAdminRegressionTests = async () => {
  const response = await fetch('/users/admin/regression-tests', { credentials: 'same-origin' });
  const data = await readApiResponse(response, 'Не удалось загрузить регрессионные тесты.');
  state.adminRegressionTests = data;
  persistAssessmentContext();
  renderAdminRegressionTests();
  return data;
};

export const runAdminRegressionTests = async () => {
  setButtonsDisabled(true);
  setStatus('Запускаем smoke-регрессию...', 'muted');
  try {
    const response = await fetch('/users/admin/regression-tests/run', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await readApiResponse(response, 'Не удалось запустить регрессионные тесты.');
    state.adminRegressionTests = {
      ...(state.adminRegressionTests || {}),
      last_run: data,
    };
    persistAssessmentContext();
    renderAdminRegressionTests();
    setStatus(data.summary || 'Smoke-регрессия завершена.', data.status === 'passed' ? 'success' : 'error');
  } catch (error) {
    setStatus(error.message || 'Не удалось запустить регрессионные тесты.', 'error');
  } finally {
    setButtonsDisabled(false);
  }
};

export const runAdminFullRegressionTests = async () => {
  setButtonsDisabled(true);
  setStatus('Запускаем полный регрессионный прогон. Это может занять несколько минут...', 'muted');
  startRegressionPolling();
  try {
    const response = await fetch('/users/admin/regression-tests/run-full', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await readApiResponse(response, 'Не удалось запустить полный регрессионный прогон.');
    state.adminRegressionTests = {
      ...(state.adminRegressionTests || {}),
      last_run: data,
    };
    persistAssessmentContext();
    renderAdminRegressionTests();
    setStatus(data.summary || 'Полный регрессионный прогон завершен.', data.status === 'passed' ? 'success' : 'error');
  } catch (error) {
    setStatus(error.message || 'Не удалось запустить полный регрессионный прогон.', 'error');
  } finally {
    stopRegressionPolling();
    setButtonsDisabled(false);
  }
};

export const cleanupAdminRegressionTests = async () => {
  setButtonsDisabled(true);
  setStatus('Удаляем __autotest__ данные...', 'muted');
  try {
    const response = await fetch('/users/admin/regression-tests/cleanup', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    });
    const data = await readApiResponse(response, 'Не удалось очистить __autotest__ данные.');
    await loadAdminRegressionTests();
    const deleted = data.deleted || {};
    setStatus(
      'Удалено: пользователей ' +
        Number(deleted.users || 0) +
        ', сессий ' +
        Number(deleted.sessions || 0) +
        ', организаций ' +
        Number(deleted.organizations || 0) +
        '.',
      'success',
    );
  } catch (error) {
    setStatus(error.message || 'Не удалось очистить __autotest__ данные.', 'error');
  } finally {
    setButtonsDisabled(false);
  }
};

export const openAdminRegressionTests = async () => {
  setCurrentScreen('admin-regression-tests');
  persistAssessmentContext();
  syncUrlState('admin-regression-tests');
  hideAllPanels();
  adminRegressionTestsPanel?.classList.remove('hidden');
  setStatus('');
  renderAdminRegressionTests();
  await loadAdminRegressionTests();
  if (state.adminRegressionTests?.last_run?.status === 'running') {
    startRegressionPolling();
  }
};
