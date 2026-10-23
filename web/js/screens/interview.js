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
  interviewPauseButton,
  interviewAdditionalButton,
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
  renderAssessmentPreparationState,
} from './assessment.js';
import { openPrechat } from './ai-welcome.js';
import { openProcessing } from './processing.js';
import { recoverProfileCompletionForAssessment, shouldRecoverProfileOnAssessmentError } from './profile-recovery.js';
import { prepareProductCycle, waitForProductCyclePreparation } from '../product-cycle-preparation.js';

const interviewCaseContextByKey = new Map();
const PRODUCT_RUNTIME_POLL_MS = 1200;
let productRuntimePollGeneration = 0;
let returnHeartbeatTimer = null;
let returnPresenceCycleId = null;
let returnPresenceGeneration = 0;
let activeInterviewDraftKey = null;
const returnClientId = (() => {
  const key = 'agent4k.returnClientId';
  let value = window.sessionStorage.getItem(key);
  if (!value) { value = crypto.randomUUID(); window.sessionStorage.setItem(key, value); }
  return value;
})();

const interviewDraftKey = () => state.productCycleId && state.productAssessmentSituationId
  ? `agent4k.assessmentDraft:${state.productCycleId}:${state.productAssessmentSituationId}`
  : null;

const restoreInterviewDraft = () => {
  const key = interviewDraftKey();
  if (key === activeInterviewDraftKey) return;
  activeInterviewDraftKey = key;
  interviewTextarea.value = key ? window.sessionStorage.getItem(key) || '' : '';
};

export const clearInterviewDraft = () => {
  const key = interviewDraftKey();
  if (key) window.sessionStorage.removeItem(key);
  activeInterviewDraftKey = key;
};

export const isCycleAssessment = () =>
  state.assessmentRuntimeKind === 'cycle' && Boolean(state.productCycleId);

const payloadText = (payload, keys) => keys
  .map((key) => typeof payload?.[key] === 'string' ? payload[key].trim() : '')
  .find(Boolean) || '';

const payloadItems = (payload, keys) => {
  const value = keys.map((key) => payload?.[key]).find(Array.isArray);
  if (!value) return [];
  return value.map((item) => {
    if (typeof item === 'string') return item.trim();
    if (!item || typeof item !== 'object') return '';
    const title = payloadText(item, ['title', 'name', 'label']);
    const body = payloadText(item, ['content', 'description', 'text']);
    return [title, body].filter(Boolean).join(': ');
  }).filter(Boolean);
};

const addProductSituationMessage = (payload) => {
  const row = document.createElement('div');
  row.className = 'interview-message interview-message--situation';
  const avatar = document.createElement('div');
  avatar.className = 'interview-avatar bot';
  avatar.textContent = 'AI';
  const bubble = document.createElement('div');
  bubble.className = 'interview-bubble bot product-situation-message';
  bubble.dataset.speakerLabel = '4К Ассистент';

  const source = typeof payload === 'string' ? { situation: payload } : payload;
  const title = payloadText(source, ['title', 'case_title']);
  const sections = [
    ['Вводная', payloadText(source, ['introduction'])],
    ['Ситуация', payloadText(source, ['initial_situation', 'situation', 'context', 'content'])],
    ['Событие', payloadText(source, ['trigger'])],
    ['Ваша роль', payloadText(source, ['assessee_position', 'role', 'position'])],
    ['Участники', payloadText(source, ['participants_and_positions'])],
    ['Задача', payloadText(source, ['assessee_task', 'task', 'question'])],
    ['Условия', payloadText(source, ['conditions_and_constraints', 'conditions', 'constraints'])],
  ].filter(([, body]) => body);
  const materials = payloadItems(source, ['initial_materials', 'available_materials', 'materials', 'attachments']);

  if (title) {
    const heading = document.createElement('h3');
    heading.className = 'product-situation-title';
    heading.textContent = title;
    bubble.appendChild(heading);
  }
  sections.forEach(([label, body]) => bubble.appendChild(renderInterviewStructuredBlock({ label, body })));
  if (materials.length) {
    bubble.appendChild(renderInterviewStructuredBlock({ label: 'Материалы', items: materials }));
  }
  if (!title && !sections.length && !materials.length) {
    const error = document.createElement('p');
    error.className = 'product-situation-error';
    error.textContent = 'Не удалось отобразить условия ситуации. Обновите страницу или обратитесь к организатору.';
    bubble.appendChild(error);
  }
  row.append(avatar, bubble);
  interviewMessages.appendChild(row);
  return row;
};

const productEventText = (event) => {
  const payload = event?.payload_json || {};
  const content = payload.content || payload.message || payload.character_response;
  return typeof content === 'string' ? content : null;
};

const renderProductRuntime = (snapshot) => {
  const current = snapshot.current_situation;
  const previousCaseKey = state.activeInterviewCaseKey;
  const previousScrollTop = interviewScrollArea?.scrollTop || 0;
  const routePositions = Array.isArray(snapshot.route?.positions) ? snapshot.route.positions : [];
  const currentPosition = routePositions.find((position) =>
    position.current_assessment_situation_id === current?.assessment_situation_id)
    || routePositions.find((position) => ['in_progress', 'awaiting_replacement'].includes(position.state));
  const completedPositions = routePositions.filter((position) => position.state === 'completed').length;
  state.assessmentRuntimeKind = 'cycle';
  state.productCycleId = snapshot.cycle_id;
  state.productAssessmentSituationId = current?.assessment_situation_id || null;
  state.productClarificationDecisionId = snapshot.clarification?.id || null;
  state.productCycleStatus = snapshot.status?.collection_status || null;
  state.assessmentRemainingSeconds = snapshot.status?.remaining_seconds ?? null;
  state.assessmentCaseNumber = Math.max(1, Number(currentPosition?.position_no || completedPositions + 1));
  state.assessmentTotalCases = Math.max(state.assessmentCaseNumber,
    Number(snapshot.route?.progress?.total_positions || routePositions.length || 1));
  state.assessmentCaseTitle = current?.participant_payload?.title || current?.participant_payload?.case_title || 'Оценочная ситуация';
  state.activeInterviewCaseKey = current?.assessment_situation_id || null;
  persistAssessmentContext();
  restoreInterviewDraft();

  interviewMessages.innerHTML = '';
  if (current) addProductSituationMessage(current.participant_payload);
  const dialogue = [
    ...(snapshot.trace?.turns || []).map((item) => ({...item, text:item.content_text,
      role:item.speaker_type === 'assessee' ? 'user' : 'assistant'})),
    ...(snapshot.trace?.events || []).map((event) => ({...event, text:productEventText(event), role:'assistant'})),
  ].sort((a, b) => a.sequence_no - b.sequence_no);
  for (const item of dialogue) {
    if (item.text) {
      const label = item.speaker_type === 'character' ? item.speaker_name || 'Персонаж'
        : item.speaker_type === 'assessment' ? 'Уточнение к вашему ответу' : 'Материал ситуации';
      const row = addInterviewMessage(item.role, item.text, label);
      if (item.turn_id) row.dataset.turnId = item.turn_id;
    }
  }
  const clarification = snapshot.clarification;
  if (clarification?.status === 'ASK' && !clarification.response_outcome && clarification.question?.text &&
      !(snapshot.trace?.turns || []).some((turn) => turn.turn_id === clarification.question_turn_id)) {
    addInterviewMessage('assistant', clarification.question.text, 'Уточнение к вашему ответу');
  }
  if (interviewScrollArea) {
    const targetTop = current && previousCaseKey !== current.assessment_situation_id ? 0 : previousScrollTop;
    interviewScrollArea.scrollTop = targetTop;
    window.requestAnimationFrame?.(() => {
      interviewScrollArea.scrollTop = targetTop;
      updateInterviewMessagesScrollIndicator();
    });
  }
  renderInterviewMeta();
  renderCaseProgress(false);
  interviewPanel.classList.remove('single-turn-mode', 'completed');
  interviewCompleteActions.classList.add('hidden');
  interviewTimerBadge.classList.remove('is-paused');

  if (snapshot.between_situations) {
    interviewTimerBadge.classList.add('is-paused');
    interviewMessages.innerHTML = '';
    const card = document.createElement('section'); card.className = 'interview-return-card';
    const title = document.createElement('h3'); title.textContent = `Ситуация ${state.assessmentCaseNumber} завершена`;
    const copy = document.createElement('p');
    copy.textContent = 'Ответы сохранены. Сейчас пауза: время на выполнение не расходуется, но общий срок завершения оценки продолжает идти.';
    const button = document.createElement('button'); button.type = 'button'; button.className = 'primary-button';
    button.textContent = 'Приступить к следующей ситуации';
    const status = document.createElement('p'); status.setAttribute('role', 'status');
    button.addEventListener('click', async () => {
      button.disabled = true; status.textContent = 'Проверяем готовность следующей ситуации…';
      try {
        const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/next', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ idempotency_key: createOperationId() }),
        });
        const accepted = await readApiResponse(response, 'Не удалось перейти к следующей ситуации.');
        const next = accepted.operation_id ? await waitForProductCyclePreparation(accepted) : accepted;
        if (next.decision?.status === 'SELECTED') { await loadProductRuntime(); return; }
        if (['NO_ADMISSIBLE_CASE', 'OUT_OF_TIME'].includes(next.decision?.status)) {
          await completeProductCycle(); return;
        }
        status.textContent = 'Следующая ситуация ещё не готова. Попробуйте ещё раз.';
        button.disabled = false;
      } catch (error) { status.textContent = error.message; button.disabled = false; }
    });
    card.append(title, copy, button, status); interviewMessages.appendChild(card);
    interviewTextarea.disabled = true; interviewSubmitButton.disabled = true; interviewFinishButton.disabled = true;
    interviewPauseButton?.classList.add('hidden'); interviewAdditionalButton?.classList.add('hidden');
    interviewCaseStatus.textContent = 'Пауза. Следующая ситуация откроется только после вашего действия.';
    updateInterviewTimer(); scheduleInterviewBottomAlignment();
    return snapshot;
  }

  const cycleStatus = snapshot.status?.collection_status;
  const waitingQuestion = clarification?.status === 'ASK' && !clarification.response_outcome;
  const closed = ['collection_closed', 'calculation_pending', 'calculated', 'failed'].includes(cycleStatus);
  const suspended = ['paused', 'interrupted'].includes(cycleStatus);
  interviewTimerBadge.classList.toggle('is-paused', suspended);
  interviewTextarea.disabled = closed || suspended || !current;
  interviewSubmitButton.disabled = closed || suspended || !current;
  interviewFinishButton.disabled = closed || suspended || !current || waitingQuestion;
  interviewPauseButton?.classList.toggle('hidden', closed || !current || cycleStatus === 'interrupted');
  interviewAdditionalButton?.classList.toggle('hidden', closed || (!current && cycleStatus !== 'interrupted'));
  if (interviewPauseButton) interviewPauseButton.textContent = state.productCycleStatus === 'paused' ? 'Продолжить' : 'Пауза';
  if (interviewAdditionalButton) interviewAdditionalButton.textContent = cycleStatus === 'interrupted'
    ? 'Продолжить в дополнительной сессии' : 'Прервать и продолжить позже';
  interviewCaseStatus.textContent = cycleStatus === 'interrupted'
    ? 'Сессия прервана. Ответы сохранены; можно продолжить в дополнительной сессии в пределах оставшегося времени.'
    : !current
    ? 'Нет доступной оценочной ситуации. Для продолжения требуется подготовка назначения.'
    : closed
    ? snapshot.pipeline?.status === 'failed'
      ? 'Обработка завершилась ошибкой. Ответы сохранены.'
      : 'Сбор завершён. Выполняется итоговая обработка.'
    : waitingQuestion
      ? 'Ответьте на уточняющий вопрос.'
      : current?.status === 'scenario_ended'
        ? 'Проверяем, требуется ли уточнение.'
        : 'Ответы сохраняются в текущей Assessment Situation.';
  updateInterviewTimer();
  scheduleInterviewBottomAlignment();
  return snapshot;
};

const heartbeatProductPresence = async () => {
  if (!state.productCycleId || !state.productAssessmentSituationId) return;
  const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/presence', {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: returnClientId, expected_assessment_situation_id: state.productAssessmentSituationId }),
  });
  if (response.status === 409) return null;
  return readApiResponse(response, 'Не удалось подтвердить связь с оценкой.');
};

const startProductPresence = (initialContract = null) => {
  if (returnHeartbeatTimer) window.clearTimeout(returnHeartbeatTimer);
  const generation = ++returnPresenceGeneration;
  const tick = async () => {
    try {
      const contract = await heartbeatProductPresence();
      if (generation !== returnPresenceGeneration) return;
      if (!contract) { await loadReturnState(); return; }
      const intervalSeconds = Number(contract.heartbeat_interval_seconds);
      if (!Number.isFinite(intervalSeconds) || intervalSeconds <= 0) {
        throw new Error('Сервер не вернул допустимый интервал подтверждения связи.');
      }
      returnHeartbeatTimer = window.setTimeout(tick, intervalSeconds * 1000);
    } catch (error) {
      showError(interviewError, error.message);
    }
  };
  const intervalSeconds = Number(initialContract?.heartbeat_interval_seconds);
  if (Number.isFinite(intervalSeconds) && intervalSeconds > 0) {
    returnHeartbeatTimer = window.setTimeout(tick, intervalSeconds * 1000);
  } else {
    void tick();
  }
};

const stopProductPresence = () => {
  returnPresenceGeneration += 1;
  if (returnHeartbeatTimer) window.clearTimeout(returnHeartbeatTimer);
  returnHeartbeatTimer = null;
  returnPresenceCycleId = null;
};

const renderReturnCard = (value) => {
  interviewTimerBadge.classList.add('is-paused');
  updateInterviewTimer();
  interviewMessages.innerHTML = '';
  const card = document.createElement('section'); card.className = 'interview-return-card';
  const title = document.createElement('h3'); title.textContent = 'Продолжение оценки';
  const progress = value.progress || {};
  const copy = document.createElement('p');
  copy.textContent = `Пройдено ${progress.completed_positions || 0} из ${progress.total_positions || 0}. Остаток времени выполнения: ${Math.ceil(Number(value.remaining_seconds || 0) / 60)} мин.`;
  const reason = document.createElement('p');
  reason.textContent = value.allowed_action === 'replace_current'
    ? 'После продолжения текущая незавершённая ситуация будет обновлена. Частичный диалог не переносится, завершённые ситуации сохраняются.'
    : 'После продолжения откроется та же незавершённая ситуация и сохранённый диалог.';
  const button = document.createElement('button'); button.type = 'button'; button.className = 'primary-button'; button.textContent = 'Продолжить';
  const status = document.createElement('p'); status.setAttribute('role', 'status');
  button.addEventListener('click', async () => {
    button.disabled = true; status.textContent = value.allowed_action === 'replace_current' ? 'Готовим допустимое обновление ситуации…' : 'Восстанавливаем ситуацию…';
    try {
      let generationOperationId = null;
      if (value.allowed_action === 'replace_current') {
        if (!value.provider_config_ref) throw new Error('Для этого Cycle ещё не подключён допущенный provider обновления.');
        const generatedResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId)
          + '/positions/' + encodeURIComponent(value.position_no) + '/equivalent-candidate', {
          method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ expected_assessment_situation_id: value.current_assessment_situation_id,
            idempotency_key: createOperationId(), provider_config_ref: value.provider_config_ref }),
        });
        const generated = await readApiResponse(generatedResponse, 'Не удалось подготовить допустимое обновление ситуации.');
        generationOperationId = generated.operation_id;
      }
      const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/return-continue', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_no: value.position_no,
          expected_assessment_situation_id: value.current_assessment_situation_id,
          expected_state: value.current_assessment_situation_status,
          idempotency_key: createOperationId(), generation_operation_id: generationOperationId }),
      });
      const continued = await readApiResponse(response, 'Не удалось продолжить оценку.');
      if (continued.status === 'collection_closed') { openProcessing(); return; }
      state.productAssessmentSituationId = continued.assessment_situation_id;
      await heartbeatProductPresence();
      await loadProductRuntime();
    } catch (error) { status.textContent = error.message; button.disabled = false; }
  });
  card.append(title, copy, reason, button, status); interviewMessages.appendChild(card);
  interviewTextarea.disabled = true; interviewSubmitButton.disabled = true; interviewFinishButton.disabled = true;
  interviewCaseStatus.textContent = 'Пауза. Оценка продолжится только после вашего действия.';
  scheduleInterviewBottomAlignment();
};

const loadReturnState = async () => {
  const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/return-state', { credentials: 'same-origin' });
  if (response.status === 409) {
    const blocked = await response.json().catch(() => ({}));
    if (['M7_RETURN_CURRENT_POSITION_NOT_FOUND', 'M7_RETURN_POLICY_NOT_SNAPSHOTTED'].includes(blocked.detail)) return false;
    throw new Error(blocked.detail || 'Не удалось проверить состояние возврата.');
  }
  const value = await readApiResponse(response, 'Не удалось проверить состояние возврата.');
  if (['continue_current', 'replace_current'].includes(value.allowed_action)) { renderReturnCard(value); return true; }
  return false;
};

export const loadProductRuntime = async ({ generation = null } = {}) => {
  if (!state.productCycleId) throw new Error('Cycle runtime не инициализирован.');
  // Check the server-owned pause before fetching any AS content. Reload/login/GET
  // never resumes a recognized absence; only the explicit command above does.
  if (await loadReturnState()) return null;
  const response = await fetch('/users/assessment/cycles/' + encodeURIComponent(state.productCycleId) + '/runtime', {
    credentials: 'same-origin',
  });
  const saved = await readApiResponse(response, 'Не удалось восстановить состояние оценки.');
  if (generation !== null && generation !== productRuntimePollGeneration) return saved;
  state.productAssessmentSituationId = saved.current_situation?.assessment_situation_id || null;
  const terminal = ['collection_closed', 'calculation_pending', 'calculated', 'failed']
    .includes(saved.status?.collection_status);
  let presenceContract = null;
  if (saved.return_policy_enabled && saved.current_situation && returnPresenceCycleId !== saved.cycle_id) {
    presenceContract = await heartbeatProductPresence();
    returnPresenceCycleId = saved.cycle_id;
  }
  const snapshot = renderProductRuntime(saved);
  if (saved.return_policy_enabled && snapshot.current_situation && presenceContract) startProductPresence(presenceContract);
  if (terminal && returnPresenceCycleId) {
    stopProductPresence();
  }
  if (['collection_closed', 'calculation_pending', 'calculated'].includes(snapshot.status?.collection_status) &&
      !interviewPanel.classList.contains('hidden')) {
    openProcessing();
  }
  return snapshot;
};

const waitForProductClarification = async (previousDecisionId = null) => {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    const snapshot = await loadProductRuntime();
    const decision = snapshot.clarification;
    if (snapshot.pipeline?.status === 'failed') throw new Error(snapshot.pipeline.error_code || 'Ошибка анализа.');
    if (decision && decision.id !== previousDecisionId) return snapshot;
    await new Promise((resolve) => window.setTimeout(resolve, PRODUCT_RUNTIME_POLL_MS));
  }
  throw new Error('Анализ уточнения ещё не завершён. Состояние можно восстановить после обновления страницы.');
};

const completeProductCycle = async () => {
  stopProductPresence();
  const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/completion', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'complete', reason: 'user_completed_scenario', idempotency_key: createOperationId() }),
  });
  await readApiResponse(response, 'Не удалось завершить сбор оценки.');
  safeStorage.setItem(STORAGE_KEYS.completionPending, '1');
  openProcessing();
};

export const finishProductAssessment = async () => {
  let snapshot = await loadProductRuntime();
  const current = snapshot.current_situation;
  if (!current) throw new Error('Текущая Assessment Situation не найдена.');
  if (!(snapshot.trace?.turns || []).some((turn) => turn.speaker_type === 'assessee')) {
    throw new Error('Сначала отправьте хотя бы один ответ по текущей ситуации.');
  }
  if (current.status === 'active') {
    const response = await fetch('/users/assessment/m5/situations/' + encodeURIComponent(current.assessment_situation_id) + '/transitions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'scenario_end', reason: 'user_finished_case', request_id: createOperationId() }),
    });
    await readApiResponse(response, 'Не удалось завершить основной сценарий.');
    interviewCaseStatus.textContent = 'Анализируем, требуется ли уточнение…';
    snapshot = await waitForProductClarification(snapshot.clarification?.id || null);
  }
  const clarification = snapshot.clarification;
  if (clarification?.status === 'ASK' && !clarification.response_outcome) {
    renderProductRuntime(snapshot);
    return;
  }
  stopProductPresence();
  const finishedResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/finish-situation', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: createOperationId() }),
  });
  await readApiResponse(finishedResponse, 'Не удалось завершить текущую ситуацию.');
  await loadProductRuntime();
};

export const toggleProductPause = async () => {
  const action = state.productCycleStatus === 'paused' ? 'resume' : 'pause';
  const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/control', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, reason: 'user_' + action, idempotency_key: createOperationId() }),
  });
  await readApiResponse(response, 'Не удалось изменить состояние паузы.');
  await loadProductRuntime();
};

export const createProductAdditionalSession = async () => {
  let snapshot = await loadProductRuntime();
  if (snapshot.status?.collection_status !== 'interrupted') {
    if (!(snapshot.trace?.turns || []).some((turn) => turn.speaker_type === 'assessee')) {
      throw new Error('Перед Additional Session сохраните ответ по текущей ситуации.');
    }
    stopProductPresence();
    const interruptedResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/completion', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'interrupt_for_continuation', reason: 'user_requested_additional_session', idempotency_key: createOperationId() }),
    });
    await readApiResponse(interruptedResponse, 'Не удалось прервать текущую сессию.');
    await loadProductRuntime();
    return;
  }
  if (snapshot.continuation?.status === 'pending') {
    const sessionResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/additional-sessions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent_id: snapshot.continuation.intent_id, idempotency_key: createOperationId() }),
    });
    await readApiResponse(sessionResponse, 'Не удалось создать Additional Session.');
  }
  const nextResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/next', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: createOperationId() }),
  });
  const accepted = await readApiResponse(nextResponse, 'Не удалось выбрать следующую Assessment Situation.');
  if (accepted.operation_id) await waitForProductCyclePreparation(accepted);
  await loadProductRuntime();
};

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

export const addInterviewMessage = (role, text, speakerLabel = null) => {
  const row = document.createElement('div');
  row.className = 'interview-message' + (role === 'user' ? ' own' : '');
  row.dataset.messageText = role === 'user' ? String(text ?? '').trim() : '';
  if (role !== 'user') {
    const avatar = document.createElement('div');
    avatar.className = 'interview-avatar bot';
    avatar.textContent = 'AI';
    row.appendChild(avatar);
  }
  const bubble = document.createElement('div');
  bubble.className = 'interview-bubble ' + (role === 'user' ? 'user' : 'bot');
  if (speakerLabel && role !== 'user') bubble.dataset.speakerLabel = speakerLabel;
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
  if (role === 'user') {
    const delivery = document.createElement('div');
    delivery.className = 'interview-message-delivery';
    delivery.hidden = true;
    delivery.setAttribute('aria-live', 'polite');

    const status = document.createElement('span');
    status.className = 'interview-message-delivery-status';
    delivery.appendChild(status);

    const retryButton = document.createElement('button');
    retryButton.type = 'button';
    retryButton.className = 'interview-message-retry';
    retryButton.textContent = 'Повторить';
    retryButton.hidden = true;
    delivery.appendChild(retryButton);
    row.appendChild(delivery);
  }
  interviewMessages.appendChild(row);
  scrollInterviewToBottom();
  return row;
};

export const setInterviewMessageDeliveryState = (row, deliveryState, onRetry = null) => {
  if (!(row instanceof HTMLElement)) return;
  const delivery = row.querySelector('.interview-message-delivery');
  const status = row.querySelector('.interview-message-delivery-status');
  const retryButton = row.querySelector('.interview-message-retry');
  if (!delivery || !status || !retryButton) return;

  row.classList.toggle('delivery-pending', deliveryState === 'pending');
  row.classList.toggle('delivery-failed', deliveryState === 'failed');
  retryButton.onclick = null;

  if (deliveryState === 'pending') {
    delivery.hidden = false;
    status.textContent = 'Отправляем...';
    retryButton.hidden = true;
  } else if (deliveryState === 'failed') {
    delivery.hidden = false;
    status.textContent = 'Не отправлено';
    retryButton.hidden = false;
    retryButton.onclick = () => onRetry?.();
  } else {
    delivery.hidden = true;
    status.textContent = '';
    retryButton.hidden = true;
  }
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
    return 'Ситуация ' + state.assessmentCaseNumber;
  }
  return 'Ситуация';
};

const updateCaseSidebarToggle = () => {
  if (!caseSidebarToggle || !caseSidebarToggleLabel) return;
  const label = getCurrentCaseDropdownLabel();
  caseSidebarToggleLabel.textContent = label;
  caseSidebarToggle.setAttribute('aria-label', 'Маршрут оценки: ' + label);
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
  interviewCaseBadge.textContent = 'Ситуация ' + state.assessmentCaseNumber + ' из ' + state.assessmentTotalCases;
  interviewCaseTitle.textContent = state.assessmentCaseTitle || 'Оценочная ситуация';
  interviewCaseStatus.textContent = '';
  if (interviewProgressFill) {
    const totalCases = Math.max(1, Number(state.assessmentTotalCases || 0));
    const caseNumber = Math.max(1, Math.min(totalCases, Number(state.assessmentCaseNumber || 1)));
    const caseProgress = totalCases > 1 ? (caseNumber - 1) / (totalCases - 1) : 1;
    interviewProgressFill.style.width = Math.round(caseProgress * 50) + '%';
  }
};

const renderCaseProgress = (assessmentCompleted = false) => {
  if (caseProgressList) caseProgressList.innerHTML = '';

  if (!state.assessmentTotalCases) {
    if (interviewRouteLabel) interviewRouteLabel.textContent = 'Подготовка';
    updateCaseSidebarToggle();
    return;
  }

  if (interviewRouteLabel) {
    interviewRouteLabel.textContent = assessmentCompleted
      ? 'Завершено'
      : 'Текущая ситуация: ' + state.assessmentCaseNumber;
  }

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
    caseProgressList?.appendChild(item);
  }
  updateCaseSidebarToggle();
  setCaseSidebarOpen(false);
};

export const clearInterviewTimer = () => {
  productRuntimePollGeneration += 1;
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
    ? 'Проверяем последний кейс и собираем итоговый профиль компетенций.'
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
  const prefix = interviewTimerBadge.classList.contains('is-paused') ? 'Пауза · ' : '';
  if (remainingMs === null) {
    interviewTimerBadge.textContent = prefix + 'Без лимита';
    interviewTimerBadge.classList.remove('is-low-time');
    return false;
  }

  if (remainingMs <= 0) {
    interviewTimerBadge.textContent = prefix + '00:00';
    interviewTimerBadge.classList.add('is-low-time');
    interviewCaseStatus.textContent = 'Ситуация завершается автоматически из-за окончания времени.';
    return true;
  }

  interviewTimerBadge.textContent = prefix + formatRemainingTime(remainingMs);
  interviewTimerBadge.classList.toggle('is-low-time', remainingMs < 180000);
  return false;
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

  if (assistantMessage && nextCaseKey) {
    cacheCurrentCaseContext(nextCaseKey, assistantMessage);
  }

  renderInterviewMeta();
  renderCaseProgress(Boolean(data.assessment_completed));
  clearInterviewTimer();
  clearAssessmentAutoFinishTimer();
  interviewPanel.classList.toggle('single-turn-mode', !isDialogCase);

  if (!isDialogCase && assistantMessage && !suppressAssistantBubble) {
    renderSingleTurnCaseCard(assistantMessage);
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

  if (data.pending_auto_finish) {
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    interviewPanel.classList.remove('completed');
    interviewCompleteActions.classList.add('hidden');
    interviewCaseStatus.textContent = 'Ситуация будет автоматически завершена.';
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

const submitAssessmentMessage = async (text, requestIdentity = null) => {
  if (isCycleAssessment()) {
    if (text === '__timeout__') {
      await loadProductRuntime();
      return;
    }
    // Read without rebuilding the transcript: preserve the pending row and retry identity.
    const runtimeResponse = await fetch('/users/assessment/cycles/' + encodeURIComponent(state.productCycleId) + '/runtime', { credentials: 'same-origin' });
    const snapshot = await readApiResponse(runtimeResponse, 'Не удалось восстановить состояние оценки.');
    const clarification = snapshot.clarification;
    const isClarification = clarification?.status === 'ASK' && !clarification.response_outcome;
    const endpoint = requestIdentity?.endpoint || (isClarification
      ? '/users/assessment/m7/clarifications/' + encodeURIComponent(clarification.id) + '/answers'
      : '/users/assessment/m5/situations/' + encodeURIComponent(state.productAssessmentSituationId) + '/turns');
    if (requestIdentity) requestIdentity.endpoint = endpoint;
    const body = {
      request_id: requestIdentity?.requestId || createOperationId(),
      turn_id: requestIdentity?.turnId || crypto.randomUUID(),
      content: text,
    };
    const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    await readApiResponse(response, 'Не удалось сохранить ответ в Cycle runtime.');
    if (isClarification) {
      interviewCaseStatus.textContent = 'Повторно анализируем ответ на уточнение…';
      await waitForProductClarification(clarification.id);
    } else {
      await loadProductRuntime();
    }
    return;
  }
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
    const data = await readApiResponse(response, 'Не удалось обработать ответ по ситуации.');
    handleAssessmentResponse(data);
    stopAssessmentTransitionLoader();
  } catch (error) {
    stopAssessmentTransitionLoader();
    throw error;
  }
};

export const resumeProductRuntimePolling = () => {
  clearInterviewTimer();
  state.assessmentTimerId = window.setInterval(() => {
    if (!document.hidden && !interviewPanel.classList.contains('hidden')) {
      void loadProductRuntime({ generation: productRuntimePollGeneration }).catch((error) => showError(interviewError, error.message));
    }
  }, PRODUCT_RUNTIME_POLL_MS);
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
  if (isCycleAssessment()) {
    void loadProductRuntime().catch((error) => showError(interviewError, error.message));
    resumeProductRuntimePolling();
  }
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
    const prepared = await prepareProductCycle({
      personalized_profile_id: state.dashboard?.personalized_profile_id || null,
      idempotency_key: createOperationId(), selected_skills: ['K1', 'K2', 'K3', 'K4'],
    });
    state.assessmentRuntimeKind = 'cycle';
    state.productCycleId = prepared.plan.cycle_id;
    persistAssessmentContext();
    const response = await fetch('/users/assessment/cycles/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: state.productCycleId, idempotency_key: createOperationId() }),
    });
    const started = await readApiResponse(response, 'Не удалось запустить Cycle runtime.');
    state.assessmentRuntimeKind = 'cycle';
    state.productCycleId = started.plan.cycle_id;
    state.assessmentSessionCode = null;
    state.assessmentSessionId = null;
    state.preparedAssessmentStartResponse = null;
    if (['collection_closed', 'calculation_pending'].includes(started.runtime?.status?.collection_status)) {
      persistAssessmentContext();
      openProcessing();
      return;
    }
    openInterview();
    renderProductRuntime(started.runtime);
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
  openPrechat();
};

export const initInterview = () => {
  disableTextareaAssistFeatures(interviewTextarea);
  interviewTextarea.addEventListener('input', () => {
    const key = interviewDraftKey();
    if (!key) return;
    activeInterviewDraftKey = key;
    if (interviewTextarea.value) window.sessionStorage.setItem(key, interviewTextarea.value);
    else window.sessionStorage.removeItem(key);
  });
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

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && isCycleAssessment()) {
      void loadProductRuntime().catch((error) => showError(interviewError, error.message));
    }
  });

  registerLeaveInterviewCleanup(() => {
    clearInterviewTimer();
    stopProductPresence();
    void pauseAssessmentTimerIfNeeded();
  });
};

export { startAssessmentInterview, submitAssessmentMessage, updateInterviewTimer };
