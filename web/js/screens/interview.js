import {
  state,
  safeStorage,
  STORAGE_KEYS,
  persistAssessmentContext,
  setCurrentScreen,
  registerLeaveInterviewCleanup,
} from '../state.js';
import {
  interviewPanel,
  interviewMessages,
  interviewScrollArea,
  interviewMessagesScroll,
  interviewSummary,
  interviewCompleteActions,
  interviewCaseBadge,
  interviewProgressFill,
  interviewCaseTitle,
  interviewCaseStatus,
  interviewTimerBadge,
  interviewTitleRow,
  interviewCaseHeading,
  interviewCompactQuery,
  interviewTextarea,
  interviewSubmitButton,
  interviewFinishButton,
  interviewError,
  caseProgressList,
  interviewRouteLabel,
  caseSidebar,
  caseSidebarToggle,
  caseSidebarToggleLabel,
  prechatError,
} from '../dom.js';
import { readApiResponse } from '../api.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { showError } from '../components/errors.js';
import { createOperationId } from '../api.js';
import { showLoader, hideLoader, startLoaderProgressPolling } from '../utils/loader.js';
import { loaderFlows } from '../config.js';
import {
  canReusePreparedAssessment,
  renderAssessmentPreparationState,
  beginAssessmentPreparation,
  retryAssessmentPreparation,
  resetAssessmentPreparationState,
} from './assessment.js';
import { openPrechat } from './ai-welcome.js';
import { openProcessing } from './processing.js';
import { recoverProfileCompletionForAssessment, shouldRecoverProfileOnAssessmentError } from './profile-recovery.js';

const interviewCaseContextByKey = new Map();

export const parseInterviewAssistantMessage = (text) => {
  const normalized = String(text || '').trim();
  if (!normalized) {
    return null;
  }

  const explicitTaskMatch = normalized.match(/([\s\S]*?)\n{1,}\s*Что нужно сделать:\s*([\s\S]+)$/i);
  if (explicitTaskMatch) {
    const context = explicitTaskMatch[1].trim();
    const task = normalizeInterviewTaskText(explicitTaskMatch[2]);
    if (context && task) {
      return { context, task };
    }
  }

  const parts = normalized
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length >= 2) {
    const task = parts[parts.length - 1];
    const context = parts.slice(0, -1).join('\n\n').trim();
    if (looksLikeInterviewTask(task) && context) {
      return { context, task };
    }
  }

  const sentences =
    normalized
      .match(/[^.!?]+[.!?]+|[^.!?]+$/g)
      ?.map((part) => part.trim())
      .filter(Boolean) || [];
  if (sentences.length >= 2) {
    const task = sentences[sentences.length - 1];
    const context = sentences.slice(0, -1).join(' ').trim();
    if (looksLikeInterviewTask(task) && context) {
      return { context, task };
    }
  }

  return null;
};

const looksLikeInterviewTask = (text) => {
  const normalized = normalizeInterviewTaskText(text).toLowerCase();
  if (!normalized) {
    return false;
  }
  return [
    'как вы',
    'ответьте',
    'предложите',
    'уточните',
    'зафиксируйте',
    'проведите',
    'подготовьте',
    'опишите',
    'сформируйте',
    'выберите',
  ].some((prefix) => normalized.startsWith(prefix));
};

const normalizeInterviewTaskText = (text) => {
  return String(text || '')
    .trim()
    .replace(/^что нужно сделать:\s*/i, '')
    .trim();
};

const normalizeInterviewSituationText = (text) => {
  return String(text || '')
    .replace(/\r\n/g, '\n')
    .trim()
    .replace(/^Ситуация:\s*\*\*[^*]+\*\*[.:]?\s*/i, '')
    .replace(/^\*\*Ситуация\*\*[.:]?\s*/i, '')
    .replace(/^Ситуация[.:]?\s*/i, '')
    .trim();
};

const extractInterviewIncidentTitle = (text) => {
  const normalized = String(text || '')
    .replace(/\r\n/g, '\n')
    .trim();
  if (!normalized) {
    return '';
  }
  const match = normalized.match(/Ситуация:\s*\*\*([^*]+)\*\*/i);
  return match ? match[1].trim() : '';
};

const renderInterviewStructuredBlock = ({ label, body = '', items = [], variant }) => {
  const section = document.createElement('section');
  section.className =
    'interview-structured-block' + (variant ? ' interview-structured-block--' + variant : '');

  const labelNode = document.createElement('div');
  labelNode.className = 'interview-structured-block-label';
  labelNode.textContent = label;
  section.appendChild(labelNode);

  if (body) {
    const bodyNode = document.createElement('div');
    bodyNode.className = 'interview-structured-block-body';
    bodyNode.textContent = body;
    section.appendChild(bodyNode);
  }

  if (items.length) {
    const list = document.createElement('ul');
    list.className = 'interview-structured-block-list';
    items.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = item;
      list.appendChild(li);
    });
    section.appendChild(list);
  }

  return section;
};

export const addInterviewMessage = (role, text) => {
  const row = document.createElement('div');
  row.className = 'interview-message' + (role === 'user' ? ' own' : '');
  if (role !== 'user') {
    const avatar = document.createElement('div');
    avatar.className = 'interview-avatar bot';
    avatar.textContent = 'AI';
    row.appendChild(avatar);
  }
  const bubble = document.createElement('div');
  bubble.className = 'interview-bubble ' + (role === 'user' ? 'user' : 'bot');
  if (role === 'user') {
    bubble.textContent = String(text ?? '').trim();
  } else {
    const parsed = parseInterviewAssistantMessage(text);
    if (parsed) {
      bubble.classList.add('structured');

      const contextLeadSection = document.createElement('div');
      contextLeadSection.className = 'interview-bubble-section lead';
      contextLeadSection.innerHTML =
        '<div class="interview-bubble-label">Вводные данные</div>' + '<div class="interview-bubble-text"></div>';
      const leadTarget = contextLeadSection.querySelector('.interview-bubble-text');
      leadTarget.appendChild(
        renderInterviewStructuredBlock({
          label: 'Ситуация',
          body: normalizeInterviewSituationText(parsed.context) || parsed.context,
        }),
      );
      bubble.appendChild(contextLeadSection);

      const taskSection = document.createElement('div');
      taskSection.className = 'interview-bubble-section task';
      taskSection.innerHTML =
        '<div class="interview-bubble-label">Что нужно сделать</div>' + '<div class="interview-bubble-task"></div>';
      taskSection.querySelector('.interview-bubble-task').textContent = parsed.task;
      bubble.appendChild(taskSection);
    } else {
      bubble.textContent = text;
    }
  }
  row.appendChild(bubble);
  interviewMessages.appendChild(row);
  scrollInterviewToBottom();
};

const scrollInterviewToBottom = () => {
  if (interviewScrollArea) {
    interviewScrollArea.scrollTop = interviewScrollArea.scrollHeight;
  }
  updateInterviewMessagesScrollIndicator();
};

const ensureLatestInterviewMessageVisible = () => {
  if (!interviewMessages || !interviewScrollArea) {
    return;
  }
  const lastMessage = interviewMessages.lastElementChild;
  if (!(lastMessage instanceof HTMLElement)) {
    scrollInterviewToBottom();
    return;
  }
  lastMessage.scrollIntoView({ block: 'end', inline: 'nearest' });
  scrollInterviewToBottom();
};

const scheduleInterviewBottomAlignment = () => {
  const align = () => ensureLatestInterviewMessageVisible();
  if (typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(() => {
      align();
      window.setTimeout(align, 80);
      window.setTimeout(align, 220);
    });
    return;
  }
  align();
  window.setTimeout(align, 80);
  window.setTimeout(align, 220);
};

const updateInterviewMessagesScrollIndicator = () => {
  if (!interviewScrollArea) return;
  const distanceFromBottom =
    interviewScrollArea.scrollHeight - interviewScrollArea.scrollTop - interviewScrollArea.clientHeight;
  const hasOverflow = interviewScrollArea.scrollHeight - interviewScrollArea.clientHeight > 8;
  const canScrollUp = hasOverflow && interviewScrollArea.scrollTop > 8;
  const canScrollDown = hasOverflow && distanceFromBottom > 8;
  interviewScrollArea
    .closest('.interview-messages-shell')
    ?.classList.toggle('can-scroll-up', canScrollUp);
  interviewScrollArea
    .closest('.interview-messages-shell')
    ?.classList.toggle('can-scroll-down', canScrollDown);
  if (interviewMessagesScroll) {
    interviewMessagesScroll.hidden = !(hasOverflow && distanceFromBottom > 24);
  }
};

const getCurrentCaseDropdownLabel = () => {
  if (state.assessmentCaseTitle) {
    return state.assessmentCaseTitle;
  }
  if (state.assessmentCaseNumber) {
    return 'Кейс ' + state.assessmentCaseNumber;
  }
  return 'Кейс';
};

const updateCaseSidebarToggle = () => {
  if (!caseSidebarToggle || !caseSidebarToggleLabel) return;
  const label = getCurrentCaseDropdownLabel();
  caseSidebarToggleLabel.textContent = label;
  caseSidebarToggle.setAttribute('aria-label', 'Список кейсов: ' + label);
};

const setCaseSidebarOpen = (isOpen) => {
  if (!caseSidebar || !caseSidebarToggle) return;
  caseSidebar.classList.toggle('is-open', isOpen);
  caseSidebarToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
};

const placeInterviewTimerBadge = () => {
  if (!interviewTimerBadge || !interviewTitleRow || !interviewCaseHeading) return;
  const compact = Boolean(interviewCompactQuery?.matches);
  const target = compact ? interviewTitleRow : interviewCaseHeading;
  if (interviewTimerBadge.parentElement !== target) {
    target.appendChild(interviewTimerBadge);
  }
};

const renderSingleTurnCaseCard = (text) => {
  interviewSummary.innerHTML = '';
  const parsed = parseInterviewAssistantMessage(text);

  if (parsed) {
    interviewSummary.appendChild(
      renderInterviewStructuredBlock({
        label: 'Ситуация',
        body: normalizeInterviewSituationText(parsed.context) || parsed.context,
      }),
    );
    interviewSummary.appendChild(
      renderInterviewStructuredBlock({
        label: 'Что нужно сделать',
        body: parsed.task,
        variant: 'task',
      }),
    );
  } else {
    interviewSummary.textContent = text;
  }

  interviewSummary.classList.remove('hidden');
};

const cacheCurrentCaseContext = (caseKey, assistantMessage) => {
  if (!caseKey || !assistantMessage) {
    return;
  }
  const parsed = parseInterviewAssistantMessage(assistantMessage);
  if (parsed) {
    interviewCaseContextByKey.set(caseKey, {
      context: normalizeInterviewSituationText(parsed.context) || parsed.context,
      task: parsed.task,
    });
    return;
  }
  const normalized = String(assistantMessage || '').trim();
  if (normalized) {
    interviewCaseContextByKey.set(caseKey, {
      context: normalized,
      task: '',
    });
  }
};

const renderFollowupCaseContext = (caseKey, mbtiFeedbackText = '') => {
  const cached = caseKey ? interviewCaseContextByKey.get(caseKey) : null;
  interviewSummary.innerHTML = '';

  const introBlock = renderInterviewStructuredBlock({
    label: 'Кейс, по которому уточняем ответ',
    body:
      'Сначала напомним исходную ситуацию, чтобы уточняющий вопрос оставался привязанным к тому же кейсу.',
  });
  interviewSummary.appendChild(introBlock);

  if (cached?.context) {
    interviewSummary.appendChild(
      renderInterviewStructuredBlock({
        label: 'Ситуация',
        body: cached.context,
      }),
    );
  }

  if (cached?.task) {
    interviewSummary.appendChild(
      renderInterviewStructuredBlock({
        label: 'Что нужно было сделать',
        body: cached.task,
        variant: 'task',
      }),
    );
  }

  if (!cached?.context && !cached?.task) {
    interviewSummary.appendChild(
      renderInterviewStructuredBlock({
        label: 'Кейс',
        body: state.assessmentCaseTitle || 'Контекст кейса временно недоступен, но уточнение относится к только что завершенному кейсу.',
      }),
    );
  }

  if (mbtiFeedbackText) {
    interviewSummary.appendChild(
      renderInterviewStructuredBlock({
        label: 'MBTI по кейсу',
        body: mbtiFeedbackText,
      }),
    );
  }

  interviewSummary.classList.remove('hidden');
};

const disableTextareaAssistFeatures = (element) => {
  if (!(element instanceof HTMLElement)) {
    return;
  }
  element.setAttribute('autocomplete', 'off');
  element.setAttribute('autocorrect', 'off');
  element.setAttribute('autocapitalize', 'off');
  element.setAttribute('spellcheck', 'false');
  element.setAttribute('data-form-type', 'other');
};

const renderInterviewMeta = () => {
  interviewCaseBadge.textContent = 'Кейс ' + state.assessmentCaseNumber + ' из ' + state.assessmentTotalCases;
  interviewCaseTitle.textContent = state.assessmentCaseTitle || 'Кейс';
  interviewCaseStatus.textContent = '';
  if (interviewProgressFill) {
    const totalCases = Math.max(1, Number(state.assessmentTotalCases || 0));
    const caseNumber = Math.max(1, Math.min(totalCases, Number(state.assessmentCaseNumber || 1)));
    const caseProgress = totalCases > 1 ? (caseNumber - 1) / (totalCases - 1) : 1;
    interviewProgressFill.style.width = Math.round(caseProgress * 50) + '%';
  }
};

const renderCaseProgress = (assessmentCompleted = false) => {
  caseProgressList.innerHTML = '';

  if (!state.assessmentTotalCases) {
    interviewRouteLabel.textContent = 'Подготовка';
    updateCaseSidebarToggle();
    return;
  }

  interviewRouteLabel.textContent = assessmentCompleted ? 'Завершено' : 'Текущий кейс: ' + state.assessmentCaseNumber;

  for (let index = 1; index <= state.assessmentTotalCases; index += 1) {
    const item = document.createElement('div');
    let status = 'pending';
    let statusLabel = 'В очереди';
    const outcome = state.caseOutcomeByNumber[index];

    if (assessmentCompleted || index < state.assessmentCaseNumber) {
      status = 'done';
      statusLabel = outcome || 'Завершен';
    } else if (index === state.assessmentCaseNumber) {
      status = 'active';
      statusLabel = 'Текущий';
    }

    item.className = 'case-progress-item ' + status;
    const outcomeClass =
      outcome === 'Пройден' || outcome === 'Пройден по тайм-ауту'
        ? ' outcome-success'
        : outcome === 'Пропущен'
          ? ' outcome-failed'
          : outcome === 'Тайм-аут без ответа'
            ? ' outcome-timeout'
            : '';
    const titleText =
      index === state.assessmentCaseNumber && state.assessmentCaseTitle
        ? state.assessmentCaseTitle
        : statusLabel;
    const metaText =
      index === state.assessmentCaseNumber && state.assessmentCaseTitle
        ? statusLabel
        : '';

    item.innerHTML =
      '<div class="case-progress-index">' +
      String(index).padStart(2, '0') +
      '</div>' +
      '<div class="case-progress-copy' +
      outcomeClass +
      '">' +
      '<strong>' +
      titleText +
      '</strong>' +
      (metaText ? '<span>' + metaText + '</span>' : '') +
      '</div>';
    caseProgressList.appendChild(item);
  }
  updateCaseSidebarToggle();
  setCaseSidebarOpen(false);
};

export const clearInterviewTimer = () => {
  if (state.assessmentTimerId) {
    window.clearInterval(state.assessmentTimerId);
    state.assessmentTimerId = null;
  }
  state.assessmentTimeoutInFlight = false;
};

export const pauseAssessmentTimerIfNeeded = async () => {
  if (
    !state.assessmentSessionCode ||
    state.assessmentPauseInFlight ||
    state.assessmentTimeoutInFlight ||
    !state.activeInterviewCaseKey
  ) {
    return;
  }
  state.assessmentPauseInFlight = true;
  try {
    await fetch('/users/assessment/pause', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_code: state.assessmentSessionCode,
      }),
    });
  } catch (_error) {
    // keep timer pause best-effort when leaving the interview screen
  } finally {
    state.assessmentPauseInFlight = false;
  }
};

const getRemainingCaseTimeMs = () => {
  if (typeof state.assessmentRemainingSeconds === 'number') {
    return Math.max(0, state.assessmentRemainingSeconds * 1000);
  }

  if (!state.assessmentCaseStartedAt || !state.assessmentTimeLimitMinutes) {
    return null;
  }

  const startedAtMs = new Date(state.assessmentCaseStartedAt).getTime();
  if (Number.isNaN(startedAtMs)) {
    return null;
  }

  const deadlineMs = startedAtMs + state.assessmentTimeLimitMinutes * 60 * 1000;
  return Math.max(0, deadlineMs - Date.now());
};

const formatRemainingTime = (remainingMs) => {
  const totalSeconds = Math.max(0, Math.ceil(remainingMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return String(minutes).padStart(2, '0') + ':' + String(seconds).padStart(2, '0');
};

const clearAssessmentAutoFinishTimer = () => {
  if (state.assessmentAutoFinishTimerId) {
    window.clearTimeout(state.assessmentAutoFinishTimerId);
    state.assessmentAutoFinishTimerId = null;
  }
};

let assessmentTransitionLoaderTimerId = null;

const clearAssessmentTransitionLoaderTimer = () => {
  if (assessmentTransitionLoaderTimerId) {
    window.clearTimeout(assessmentTransitionLoaderTimerId);
    assessmentTransitionLoaderTimerId = null;
  }
};

const scheduleAssessmentTransitionLoader = (operationId) => {
  clearAssessmentTransitionLoaderTimer();
  if (!operationId) {
    return;
  }
  const isFinalCase =
    Number(state.assessmentCaseNumber || 0) >= Number(state.assessmentTotalCases || 0) &&
    Number(state.assessmentTotalCases || 0) > 0;
  const title = isFinalCase ? 'Формируем итоговый отчет' : 'Завершаем кейс';
  const text = isFinalCase
    ? 'Проверяем последний кейс, обновляем MBTI и собираем итоговый профиль компетенций.'
    : 'Проверяем ответ, уточняем сигналы по кейсу и подготавливаем следующий шаг.';
  assessmentTransitionLoaderTimerId = window.setTimeout(() => {
    showLoader(title, text, loaderFlows.assessmentTurn);
    startLoaderProgressPolling(operationId);
  }, 650);
};

const stopAssessmentTransitionLoader = () => {
  clearAssessmentTransitionLoaderTimer();
  hideLoader();
};

const updateInterviewTimer = () => {
  const remainingMs = getRemainingCaseTimeMs();
  if (remainingMs === null) {
    interviewTimerBadge.textContent = 'Без лимита';
    interviewTimerBadge.classList.remove('is-low-time');
    return false;
  }

  if (remainingMs <= 0) {
    interviewTimerBadge.textContent = '00:00';
    interviewTimerBadge.classList.add('is-low-time');
    interviewCaseStatus.textContent = 'Кейс завершается автоматически из-за окончания времени.';
    return true;
  }

  interviewTimerBadge.textContent = formatRemainingTime(remainingMs);
  interviewTimerBadge.classList.toggle('is-low-time', remainingMs < 180000);
  return false;
};


const getMbtiOverallBlock = (payload) => {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  return payload['общий_итог'] || payload.overall_result || payload.overall || null;
};

const normalizeMbtiSignals = (overallBlock) => {
  if (!overallBlock || typeof overallBlock !== 'object') {
    return [];
  }
  const candidates = overallBlock['вероятные_сигналы_темперамента'] || overallBlock.probable_signals || overallBlock.signals;
  return Array.isArray(candidates)
    ? candidates.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
};

const buildMbtiCaseFeedbackText = (data) => {
  const overallBlock = getMbtiOverallBlock(data?.mbti_case_result);
  const signals = normalizeMbtiSignals(overallBlock);
  const score = overallBlock?.['оценка'] ?? overallBlock?.score ?? null;
  const conclusion = String(
    overallBlock?.['краткий_вывод'] || overallBlock?.summary || overallBlock?.conclusion || '',
  ).trim();
  const questions = Array.isArray(data?.mbti_followup_questions)
    ? data.mbti_followup_questions.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  const includeFollowupList = !Boolean(data?.mbti_followup_pending);

  if (!signals.length && score === null && !conclusion && !questions.length) {
    return '';
  }

  const parts = [];
  if (signals.length) {
    parts.push('MBTI-сигналы по кейсу: ' + signals.join(', ') + '.');
  }
  if (score !== null && score !== undefined && score !== '') {
    parts.push('Уверенность оценки: ' + score + '/100.');
  }
  if (conclusion) {
    parts.push(conclusion);
  }
  if (questions.length && includeFollowupList) {
    parts.push(
      'Уточняющие вопросы: ' +
        questions.map((question, index) => (index + 1) + '. ' + question).join(' '),
    );
  }
  return parts.join(' ');
};

const handleAssessmentResponse = (data) => {
  const previousCaseNumber = state.assessmentCaseNumber;
  const previousCaseKey = state.activeInterviewCaseKey;
  const nextCaseKey = data.session_case_id ? String(data.session_case_id) : null;
  const caseChanged = previousCaseKey && nextCaseKey && previousCaseKey !== nextCaseKey;
  const isDialogCase = Boolean(data.is_dialog_case);

  if (data.case_completed && data.result_status) {
    const completedCaseNumber = caseChanged ? previousCaseNumber : data.case_number;
    if (completedCaseNumber) {
      let outcomeLabel = data.result_status === 'passed' ? 'Пройден' : 'Пропущен';
      if (data.time_expired) {
        outcomeLabel = data.result_status === 'passed' ? 'Пройден по тайм-ауту' : 'Тайм-аут без ответа';
      }
      state.caseOutcomeByNumber[completedCaseNumber] = outcomeLabel;
    }
  }

  state.assessmentSessionCode = data.session_code;
  state.assessmentSessionId = data.session_id;
  state.assessmentCaseNumber = data.case_number;
  state.assessmentTotalCases = data.total_cases;
  state.assessmentCaseTitle = data.case_title;
  state.assessmentTimeLimitMinutes = data.case_time_limit_minutes || null;
  state.assessmentCaseStartedAt = data.case_started_at || null;
  state.assessmentRemainingSeconds =
    typeof data.case_time_remaining_seconds === 'number' ? data.case_time_remaining_seconds : null;
  state.activeInterviewCaseKey = nextCaseKey;

  if (caseChanged) {
    interviewMessages.innerHTML = '';
  }

  let assistantMessage = data.message;
  if (caseChanged && assistantMessage.includes('\n\nСледующий кейс:\n')) {
    assistantMessage = assistantMessage.split('\n\nСледующий кейс:\n')[1];
  }
  const suppressAssistantBubble =
    Boolean(data.pending_auto_finish) &&
    assistantMessage.trim() === 'Ответ зафиксирован. Завершаем кейс автоматически.';
  const incidentTitle = extractInterviewIncidentTitle(assistantMessage);
  if (incidentTitle) {
    state.assessmentCaseTitle = incidentTitle;
  }

  if (!data.mbti_followup_pending && assistantMessage && nextCaseKey) {
    cacheCurrentCaseContext(nextCaseKey, assistantMessage);
  }

  renderInterviewMeta();
  renderCaseProgress(Boolean(data.assessment_completed));
  clearInterviewTimer();
  clearAssessmentAutoFinishTimer();
  interviewPanel.classList.toggle('single-turn-mode', !isDialogCase);

  if (!isDialogCase && assistantMessage && !suppressAssistantBubble) {
    if (data.mbti_followup_pending) {
      addInterviewMessage('assistant', assistantMessage);
    } else {
      renderSingleTurnCaseCard(assistantMessage);
    }
  } else {
    if (isDialogCase) {
      interviewSummary.classList.add('hidden');
      interviewSummary.textContent = '';
      interviewSummary.innerHTML = '';
    }
  }

  if (isDialogCase && !suppressAssistantBubble) {
    addInterviewMessage('assistant', assistantMessage);
  }

  const mbtiFeedbackText = data.case_completed || data.mbti_followup_pending ? buildMbtiCaseFeedbackText(data) : '';
  if (data.mbti_followup_pending) {
    renderFollowupCaseContext(nextCaseKey || previousCaseKey, mbtiFeedbackText);
  }
  if (mbtiFeedbackText && !data.mbti_followup_pending && !isDialogCase && !interviewSummary.classList.contains('hidden')) {
    const mbtiBlock = renderInterviewStructuredBlock({
      label: 'MBTI по кейсу',
      body: mbtiFeedbackText,
    });
    interviewSummary.prepend(mbtiBlock);
  }
  if (mbtiFeedbackText && !data.mbti_followup_pending) {
    addInterviewMessage('assistant', mbtiFeedbackText);
  }

  if (data.mbti_summary && typeof data.mbti_summary === 'object') {
    state.assessmentMbtiSummary = data.mbti_summary;
    persistAssessmentContext();
  }

  if (data.assessment_completed) {
    interviewCaseStatus.textContent = 'Все кейсы пройдены, результаты сохранены в БД.';
    renderCaseProgress(true);
    interviewTimerBadge.textContent = 'Готово';
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    interviewPanel.classList.add('completed');
    interviewCompleteActions.classList.remove('hidden');
    safeStorage.setItem(STORAGE_KEYS.completionPending, '1');
    openProcessing();
    return;
  }

  if (data.mbti_followup_pending) {
    interviewCaseStatus.textContent =
      'Уточняем ответы по этому кейсу перед переходом к следующему.';
    interviewTimerBadge.textContent =
      data.mbti_followup_index && data.mbti_followup_total
        ? 'Уточнение ' + data.mbti_followup_index + '/' + data.mbti_followup_total
        : 'Уточнение';
    interviewTextarea.disabled = false;
    interviewSubmitButton.disabled = false;
    interviewFinishButton.disabled = true;
    interviewPanel.classList.remove('completed');
    interviewCompleteActions.classList.add('hidden');
    interviewTextarea.focus();
    scheduleInterviewBottomAlignment();
    return;
  }

  if (data.pending_auto_finish) {
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    interviewPanel.classList.remove('completed');
    interviewCompleteActions.classList.add('hidden');
    interviewCaseStatus.textContent = 'Кейс будет автоматически завершен.';
    const delayMs = Math.max(800, Number(data.auto_finish_delay_ms || 2200));
    state.assessmentAutoFinishTimerId = window.setTimeout(() => {
      state.assessmentAutoFinishTimerId = null;
      void submitAssessmentMessage('__auto_finish_case__');
    }, delayMs);
    return;
  }

  interviewTextarea.disabled = false;
  interviewSubmitButton.disabled = false;
  interviewFinishButton.disabled = false;
  interviewPanel.classList.remove('completed');
  interviewCompleteActions.classList.add('hidden');
  interviewTextarea.focus();
  scheduleInterviewBottomAlignment();

  if (!updateInterviewTimer()) {
    state.assessmentTimerId = window.setInterval(() => {
      if (typeof state.assessmentRemainingSeconds === 'number' && state.assessmentRemainingSeconds > 0) {
        state.assessmentRemainingSeconds -= 1;
      }
      if (updateInterviewTimer() && !state.assessmentTimeoutInFlight) {
        state.assessmentTimeoutInFlight = true;
        interviewTextarea.disabled = true;
        interviewSubmitButton.disabled = true;
        interviewFinishButton.disabled = true;
        void submitAssessmentMessage('__timeout__');
      }
    }, 1000);
  } else if (!state.assessmentTimeoutInFlight) {
    state.assessmentTimeoutInFlight = true;
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    void submitAssessmentMessage('__timeout__');
  }
};

const submitAssessmentMessage = async (text) => {
  const operationId = createOperationId();
  scheduleAssessmentTransitionLoader(operationId);
  try {
    const response = await fetch('/users/assessment/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Agent4K-Operation-Id': operationId,
      },
      body: JSON.stringify({
        session_code: state.assessmentSessionCode,
        message: text,
      }),
    });
    const data = await readApiResponse(response, 'Не удалось обработать ответ по кейсу.');
    stopAssessmentTransitionLoader();
    handleAssessmentResponse(data);
  } catch (error) {
    stopAssessmentTransitionLoader();
    throw error;
  }
};

export const openInterview = () => {
  state.newUserSequenceStep = 'interview';
  setCurrentScreen('interview');
  persistAssessmentContext();
  syncUrlState('interview');
  hideAllPanels();
  interviewPanel.classList.remove('completed');
  interviewCompleteActions.classList.add('hidden');
  interviewPanel.classList.remove('hidden');
};

const startAssessmentInterview = async () => {
  if (!state.pendingUser || !state.pendingUser.id) {
    showError(prechatError, 'Не удалось определить пользователя для старта ассессмента.');
    return;
  }

  showError(prechatError, '');
  interviewMessages.innerHTML = '';
  interviewCaseContextByKey.clear();
  interviewSummary.classList.add('hidden');
  interviewSummary.textContent = '';
  renderCaseProgress(false);
  interviewTextarea.value = '';
  interviewTextarea.disabled = true;
  interviewSubmitButton.disabled = true;
  interviewFinishButton.disabled = true;
  clearInterviewTimer();
  interviewCaseStatus.textContent = 'Подготавливаем кейс...';
  showError(interviewError, '');

  try {
    const preparedData = state.preparedAssessmentStartResponse;
    let data = preparedData;
    if (!data) {
      const response = await fetch('/users/' + state.pendingUser.id + '/assessment/start', {
        method: 'POST',
      });
      data = await readApiResponse(response, 'Не удалось запустить интервью по кейсам.');
    }

    state.preparedAssessmentStartResponse = null;
    resetAssessmentPreparationState();
    renderAssessmentPreparationState();
    openInterview();
    handleAssessmentResponse(data);
  } catch (error) {
    if (shouldRecoverProfileOnAssessmentError(error.message)) {
      await recoverProfileCompletionForAssessment();
      return;
    }
    state.assessmentPreparationStatus = 'failed';
    state.assessmentPreparationProgressPercent = 0;
    state.assessmentPreparationTitle = 'Не удалось подготовить кейсы';
    state.assessmentPreparationMessage = error.message || 'Попробуйте запустить подготовку еще раз.';
    renderAssessmentPreparationState();
    showError(prechatError, error.message);
  }
};

export const handleAssessmentEntryClick = () => {
  if (canReusePreparedAssessment()) {
    openPrechat();
    return;
  }
  if (state.assessmentPreparationStatus === 'failed') {
    void retryAssessmentPreparation();
    return;
  }
  void beginAssessmentPreparation({ force: true });
};

export const initInterview = () => {
  disableTextareaAssistFeatures(interviewTextarea);
  placeInterviewTimerBadge();
  interviewCompactQuery?.addEventListener('change', placeInterviewTimerBadge);

  if (interviewMessagesScroll && interviewScrollArea) {
    interviewMessagesScroll.addEventListener('click', () => {
      interviewScrollArea.scrollTo({ top: interviewScrollArea.scrollHeight, behavior: 'smooth' });
    });
  }

  if (interviewScrollArea) {
    interviewScrollArea.addEventListener('scroll', updateInterviewMessagesScrollIndicator, { passive: true });
    window.addEventListener('resize', updateInterviewMessagesScrollIndicator);
    const messagesObserver = new MutationObserver(updateInterviewMessagesScrollIndicator);
    messagesObserver.observe(interviewScrollArea, { childList: true, subtree: true });
  }

  if (caseSidebarToggle) {
    caseSidebarToggle.addEventListener('click', () => {
      setCaseSidebarOpen(!caseSidebar?.classList.contains('is-open'));
    });
  }

  document.addEventListener('click', (event) => {
    if (!caseSidebar?.classList.contains('is-open')) return;
    if (caseSidebar.contains(event.target)) return;
    setCaseSidebarOpen(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      setCaseSidebarOpen(false);
    }
  });

  registerLeaveInterviewCleanup(() => {
    clearInterviewTimer();
    void pauseAssessmentTimerIfNeeded();
  });
};

export { startAssessmentInterview, submitAssessmentMessage, updateInterviewTimer };
