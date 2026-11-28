import { createAnswerDrafts, draftSlot } from '../answer-drafts.js';
import { participantFailureMessage } from '../assessment-processing-status.js';
import { renderPreparation } from '../preparation-status.js';
import {
  state,
  safeStorage,
  STORAGE_KEYS,
  persistAssessmentContext,
  setCurrentScreen,
  registerLeaveInterviewCleanup,
  applyJourneyAssessmentContext,
} from '../state.js';
import {
  interviewPanel,
  interviewMessages,
  interviewScrollArea,
  interviewMessagesScroll,
  interviewSummary,
  interviewCompleteActions,
  interviewCaseBadge,
  interviewCaseTitle,
  interviewCaseStatus,
  interviewTimerBadge,
  interviewTitleRow,
  interviewCaseHeading,
  interviewCompactQuery,
  interviewTextarea,
  interviewSubmitButton,
  interviewSubmitLabel,
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
import { createOperationId, readApiResponse, fetchWithDeadline } from '../api.js';
import { assessmentRuntimeErrorMessage, getAssessmentViewGeneration, advanceAssessmentViewGeneration } from '../assessment-errors.js';
import { hideAllPanels, syncUrlState, openAcquaintanceWaiting } from '../router.js';
import { showError } from '../components/errors.js';
import { showLoader, hideLoader, startLoaderProgressPolling } from '../utils/loader.js';
import { loaderFlows } from '../config.js';
import {
  renderAssessmentPreparationState,
} from './assessment.js';
import { openPrechat } from './ai-welcome.js';
import { openProcessing } from './processing.js';
import { recoverProfileCompletionForAssessment, shouldRecoverProfileOnAssessmentError } from './profile-recovery.js';
import { prepareProductCycle, waitForProductCyclePreparation } from '../product-cycle-preparation.js';
import { startPreparedProductCycle } from '../product-cycle-start.js';

const interviewCaseContextByKey = new Map();
const PRODUCT_RUNTIME_POLL_MS = 1200;
let productRuntimePollGeneration = 0;
let productRuntimeMutationGeneration = 0;
let returnHeartbeatTimer = null;
let returnPresenceCycleId = null;
let returnPresenceGeneration = 0;
let activeInterviewDraftKey = null;
let assessmentStartGeneration = 0;
let renderedProductMessages = null;
let renderedProductCycleId = null;
const RETURN_CONTINUE_PENDING_KEY = 'agent4k.returnContinuePending';
let interviewScrollAlignmentGeneration = 0;
let interviewScrollAlignmentFrame = null;
let interviewScrollAlignmentTimers = [];
let confirmedProductInterviewSnapshot = null;
let confirmedProductInterviewCanSend = false;
const productInterviewRequests = new Map();
const nextSituationRequests = new Map();
const returnClientId = (() => {
  const key = 'agent4k.returnClientId';
  let value;
  try { value = window.sessionStorage.getItem(key); } catch (_error) { /* storage may be disabled */ }
  if (!value) {
    value = createOperationId();
    try { window.sessionStorage.setItem(key, value); } catch (_error) { /* presence still works in this page */ }
  }
  return value;
})();

const interviewDraftKey = (scope = interviewDraftScope()) => {
  if (!scope.cycleId || !scope.situationId) return null;
  const base = `agent4k.assessmentDraft:${scope.cycleId}:${scope.situationId}`;
  return scope.clarificationId ? `${base}:${scope.ownerId}:${scope.clarificationId}` : base;
};

let durableDraft = null;
const productAnswerStorage = () => window.localStorage || window.sessionStorage;

const productInterviewReadbacks = new Map();
// Keep an already known operation recoverable if browser storage later becomes
// unreadable. Identity epoch prevents carrying this page cache into a new login.
const productInterviewPendingAnswers = new Map();

const interviewDraftScope = () => ({
  cycleId: state.productCycleId, situationId: state.productAssessmentSituationId,
  ownerId: String(state.pendingUser?.id || ''),
  clarificationId: confirmedProductInterviewSnapshot?.cycle_id === state.productCycleId
    && confirmedProductInterviewSnapshot?.current_situation?.assessment_situation_id === state.productAssessmentSituationId
    && confirmedProductInterviewSnapshot?.clarification?.status === 'ASK'
    ? confirmedProductInterviewSnapshot.clarification.id : null,
});

const interviewDraftContext = (key) => {
  try { return JSON.parse(window.sessionStorage.getItem(key + ':context') || 'null'); }
  catch (_error) { return null; }
};

const interviewDraftSignature = () => `${interviewDraftKey()}:${String(state.pendingUser?.id || '')}`;

const isCurrentInterviewDraftSaved = () => {
  if (typeof durableDraft !== 'undefined' && durableDraft) return durableDraft.saved();
  const key = interviewDraftKey();
  const revision = interviewTextarea.dataset.draftRevision;
  if (!key || !revision || !interviewTextarea.value) return false;
  try {
    const context = interviewDraftContext(key);
    return context?.ownerId === String(state.pendingUser?.id || '') && context.revision === revision
      && (context.clarificationId || null) === (interviewDraftScope().clarificationId || null)
      && window.sessionStorage.getItem(key) === interviewTextarea.value;
  } catch (_error) { return false; }
};

export const showInterviewRuntimeError = (error) => {
  if (confirmedProductInterviewSnapshot?.between_situations) {
    const card = interviewMessages.querySelector('.interview-next-card');
    if (card?.dataset.preparationState !== 'failed') {
      setNextFeedback('Не удалось обновить состояние. Проверьте состояние ещё раз.');
    }
    return;
  }
  const pending = readProductInterviewAnswer()
    || productInterviewRequests.get(productInterviewRequestKey(productInterviewAnswerScope()));
  if (confirmedProductInterviewSnapshot && (productProcessingPending(confirmedProductInterviewSnapshot)
      || productProcessingFailed(confirmedProductInterviewSnapshot)
      || confirmedProductInterviewSnapshot.blocking_system_wait === true || pending?.accepted || pending?.status === 'saved'
      || ['unknown', 'rejected'].includes(pending?.status) || currentProductInterviewReceipt(confirmedProductInterviewSnapshot, pending))) {
    productInterviewReadFailure = productInterviewNoticeKey();
    renderProductInterviewNotice(confirmedProductInterviewSnapshot);
    return;
  }
  if (productProcessingPending(confirmedProductInterviewSnapshot)) {
    showProductCommandRecovery(productInterviewAnswerScope(), 'Не удалось проверить состояние. Попробуйте ещё раз.');
    return;
  }
  delete interviewError.dataset.tone;
  showError(interviewError, assessmentRuntimeErrorMessage(error, { draftSaved: isCurrentInterviewDraftSaved() }));
};

const productNextRefusalMessage = (error) => {
  const reason = String(error?.code || error?.message || '');
  if (Number(error?.status) === 403) return 'Сервер запретил подготовку следующей ситуации для текущего доступа.';
  if (/M7_TIME_LIMIT_REACHED|OUT_OF_TIME/.test(reason)) return 'Время оценки истекло. Следующая ситуация недоступна.';
  if (/NO_ADMISSIBLE_CASE/.test(reason)) return 'Для продолжения нет допустимой ситуации.';
  if (/M7_COLLECTION_CLOSED/.test(reason)) return 'Сбор ответов уже завершён. Обновите состояние оценки.';
  return 'Сервер отклонил переход. Обновите состояние оценки перед следующим действием.';
};

export const restoreInterviewActionControls = () => {
  if (confirmedProductInterviewSnapshot?.cycle_id === state.productCycleId
      && confirmedProductInterviewSnapshot?.current_situation?.assessment_situation_id === state.productAssessmentSituationId) {
    renderProductRuntime(confirmedProductInterviewSnapshot, { fresh: false });
  }
};

const restoreInterviewDraft = () => {
  if (typeof durableDraft !== 'undefined' && durableDraft) {
    const snapshot = confirmedProductInterviewSnapshot;
    if (!state.productAssessmentSituationId || !productInterviewSourceReady(snapshot)) {
      const pending = readProductInterviewAnswer();
      if (pending && !pending.accepted) durableDraft.restorePending(pending);
      else durableDraft.suspend();
      return;
    }
    durableDraft.bind({ ...productInterviewAnswerScope(), slotId: draftSlot(snapshot),
      expiresAt: snapshot.status?.deadline || snapshot.status?.calendar_deadline });
    return;
  }
  const key = interviewDraftKey();
  const signature = interviewDraftSignature();
  if (signature === activeInterviewDraftKey) return;
  activeInterviewDraftKey = signature;
  let context = key ? interviewDraftContext(key) : null;
  const ownerId = String(state.pendingUser?.id || '');
  // Legacy ordinary drafts can be adopted only after this owner's AS runtime
  // is confirmed. They never become a draft for a newly presented M7 question.
  try {
    interviewTextarea.value = key && (!context || context.ownerId === ownerId)
      ? window.sessionStorage.getItem(key) || '' : '';
    if (key && interviewTextarea.value && !context) {
      context = { ownerId, clarificationId: interviewDraftScope().clarificationId, revision: createOperationId() };
      window.sessionStorage.setItem(key + ':context', JSON.stringify(context));
    }
  } catch (_error) {
    context = null;
    interviewTextarea.value = '';
    showError(interviewError, 'Не удалось восстановить черновик из хранилища браузера.');
  }
  interviewTextarea.dataset.draftRevision = context?.ownerId === ownerId ? context.revision || '' : '';
  const pending = readProductInterviewAnswer();
  if (pending && pending.draftRevision === undefined && key === interviewDraftKey(pending)
      && context?.ownerId === pending.ownerId && interviewTextarea.value === pending.draftValue) {
    // Upgrade a pre-revision operation before input becomes editable. Later
    // equal-text edits have a different revision and cannot be cleared by it.
    saveProductInterviewAnswer({ ...pending, draftRevision: context.revision });
  }
};

export const clearInterviewDraft = (operation = null) => {
  if (typeof durableDraft !== 'undefined' && durableDraft && operation?.draftSlotId) {
    if (operation.ownerId === String(state.pendingUser?.id || '') && operation.identityEpoch === state.identityEpoch) {
      if (operation.accepted) durableDraft.clearAccepted(operation);
      else durableDraft.suspend();
    }
    return;
  }
  if (operation && operation.cycleId === state.productCycleId
      && operation.situationId === state.productAssessmentSituationId
      && (operation.ownerId !== String(state.pendingUser?.id || '') || operation.identityEpoch !== state.identityEpoch)) return;
  const key = interviewDraftKey(operation || interviewDraftScope());
  const context = key ? interviewDraftContext(key) : null;
  const ownRevision = !operation || ((!context || context.ownerId === operation.ownerId)
    && (operation.draftRevision === undefined ? !context
      : !operation.draftRevision || context?.revision === operation.draftRevision));
  if (key && ownRevision && (!operation || window.sessionStorage.getItem(key) === operation.draftValue)) {
    window.sessionStorage.removeItem(key);
    window.sessionStorage.removeItem(key + ':context');
  }
  if (key === interviewDraftKey() && ownRevision && (!operation || isProductInterviewAnswerCurrent(operation))) {
    activeInterviewDraftKey = interviewDraftSignature();
    if (operation && isProductInterviewPresentationCurrent(operation) && interviewTextarea.value === operation.draftValue) {
      interviewTextarea.value = '';
      interviewTextarea.dataset.draftRevision = '';
    }
  }
};

const productInterviewAnswerScope = () => ({
  cycleId: state.productCycleId, situationId: state.productAssessmentSituationId,
  ownerId: String(state.pendingUser?.id || ''), identityEpoch: state.identityEpoch,
  viewGeneration: getAssessmentViewGeneration(),
});

const productInterviewAnswerKey = (scope) => `agent4k.assessmentPending:${scope.cycleId}:${scope.situationId}:${scope.ownerId}`;
const productInterviewRequestKey = (scope) => productInterviewAnswerKey(scope) + ':' + scope.identityEpoch;
const productCommandKey = (kind, scope) =>
  `agent4k.assessmentCommand:${kind}:${scope.cycleId}:${scope.situationId || 'between'}:${scope.ownerId}`;
const nextSituationRequestKey = (scope, afterAs) =>
  productCommandKey('next', { ...scope, situationId: afterAs }) + ':' + scope.identityEpoch + ':' + scope.viewGeneration;
const readProductCommand = (kind, scope) => {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(productCommandKey(kind, scope)) || 'null');
    return value?.cycleId === scope.cycleId && value?.situationId === scope.situationId
      && value?.ownerId === scope.ownerId ? value : null;
  } catch { return null; }
};
const saveProductCommand = (kind, scope, operationId) => {
  const command = { cycleId: scope.cycleId, situationId: scope.situationId,
    ownerId: scope.ownerId, operationId };
  window.sessionStorage.setItem(productCommandKey(kind, scope), JSON.stringify(command));
  return command;
};
const clearProductCommand = (kind, scope) => window.sessionStorage.removeItem(productCommandKey(kind, scope));
const showProductCommandRecovery = (scope, message, { failed = false, detail = '', lockControls = true,
  check = true, onCheck = loadProductRuntime, checkLabel = 'Проверить состояние' } = {}) => {
  if (!isProductInterviewAnswerCurrent(scope)) return;
  if (lockControls) {
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
  }
  const actionFocused = document.activeElement?.parentElement === interviewError;
  interviewError.dataset.tone = failed ? 'failed' : 'neutral';
  interviewError.classList.add('processing-notice');
  showError(interviewError, message);
  interviewError.dataset.productCommandRecovery = 'true';
  if (detail) {
    const copy = document.createElement('span'); copy.className = 'processing-notice-detail';
    copy.textContent = detail; interviewError.append(copy);
  }
  if (!check) return;
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'text-button';
  button.textContent = checkLabel;
  const sourcePhase = productInterviewSourcePhase(confirmedProductInterviewSnapshot);
  const current = () => isProductInterviewAnswerCurrent(scope) && button.isConnected
    && sourcePhase === productInterviewSourcePhase(confirmedProductInterviewSnapshot);
  button.addEventListener('click', async () => {
    if (!current()) return;
    button.disabled = true;
    try {
      await onCheck();
      if (current()) button.disabled = false;
    } catch (_error) {
      if (current()) {
        showInterviewRuntimeError(_error);
      }
    }
  });
  interviewError.append(' ', button);
  if (actionFocused) button.focus({ preventScroll: true });
};

const isProductInterviewAnswerCurrent = (operation) => state.currentScreen === 'interview'
  && !interviewPanel.classList.contains('hidden')
  && operation.cycleId === state.productCycleId && operation.situationId === state.productAssessmentSituationId
  && operation.ownerId === String(state.pendingUser?.id || '') && operation.identityEpoch === state.identityEpoch
  && operation.viewGeneration === getAssessmentViewGeneration();

const isProductInterviewPresentationCurrent = (operation) => isProductInterviewAnswerCurrent(operation)
  && renderedProductMessages?.cycleId === operation.cycleId
  && renderedProductMessages?.situationId === operation.situationId
  && renderedProductMessages?.node === interviewMessages.firstChild;

const readProductInterviewAnswer = (scope = productInterviewAnswerScope()) => {
  if (!scope.cycleId || !scope.situationId) return null;
  const cacheKey = productInterviewRequestKey({ ...scope, identityEpoch: state.identityEpoch });
  try {
    const pendingKey = productInterviewAnswerKey(scope);
    const raw = productAnswerStorage().getItem(pendingKey) || window.sessionStorage.getItem(pendingKey);
    if (!raw) { productInterviewPendingAnswers.delete(cacheKey); return null; }
    const value = JSON.parse(raw);
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const expectedEndpoint = value?.clarificationId
      ? '/users/assessment/m7/clarifications/' + encodeURIComponent(value.clarificationId) + '/answers'
      : '/users/assessment/m5/situations/' + encodeURIComponent(scope.situationId) + '/turns';
    if (!value || value.cycleId !== scope.cycleId || value.situationId !== scope.situationId
        || value.ownerId !== scope.ownerId || typeof value.text !== 'string'
        || !value.text.trim() || value.text.length > 10000 || typeof value.draftValue !== 'string'
        || typeof value.requestId !== 'string' || !value.requestId || value.requestId.length > 200
        || typeof value.turnId !== 'string' || !uuid.test(value.turnId)
        || !['prepared', 'unknown', 'accepted', 'saved', 'rejected'].includes(value.status)
        || typeof value.accepted !== 'boolean'
        || (value.clarificationId !== null && (typeof value.clarificationId !== 'string' || !uuid.test(value.clarificationId)))
        || value.endpoint !== expectedEndpoint || typeof value.sourcePhase !== 'string') return null;
    if (value.expiresAt && Date.parse(value.expiresAt) <= Date.now()) {
      productAnswerStorage().removeItem(pendingKey); window.sessionStorage.removeItem(pendingKey);
      productInterviewPendingAnswers.delete(cacheKey); return null;
    }
    const phase = JSON.parse(value.sourcePhase);
    if (!Array.isArray(phase) || phase.length !== 5 || phase.some((part) => part !== null && typeof part !== 'string')) return null;
    if (productAnswerStorage() !== window.sessionStorage && !productAnswerStorage().getItem(pendingKey)) {
      productAnswerStorage().setItem(pendingKey, raw); window.sessionStorage.removeItem(pendingKey);
    }
    const operation = { ...value, identityEpoch: state.identityEpoch, viewGeneration: getAssessmentViewGeneration() };
    productInterviewPendingAnswers.set(cacheKey, operation);
    return operation;
  } catch (_error) {
    const cached = productInterviewPendingAnswers.get(cacheKey);
    return cached ? { ...cached, viewGeneration: getAssessmentViewGeneration() } : null;
  }
};

const saveProductInterviewAnswer = (operation) => {
  // identityEpoch belongs to this page lifetime; the server operation survives reload.
  const { identityEpoch: _epoch, viewGeneration: _view, ...saved } = operation;
  productAnswerStorage().setItem(productInterviewAnswerKey(operation), JSON.stringify(saved));
  productInterviewPendingAnswers.set(productInterviewRequestKey(operation), { ...operation });
};

// One wait deadline per saved processing phase; manual reads never renew it.
const productProcessingBudgets = new Map();
const productInterviewReceipts = new Map();
let productInterviewReadFailure = null;
let productInterviewOwnSendScroll = null;
const productInterviewNoticeKey = (scope = productInterviewAnswerScope()) =>
  productCommandKey('receipt', scope) + ':' + scope.identityEpoch + ':' + scope.viewGeneration;
const rememberProductInterviewReceipt = (operation) => {
  const previousAnswer = (confirmedProductInterviewSnapshot?.trace?.turns || [])
    .filter(turn => turn.speaker_type === 'assessee').reduce((a, b) => !a || b.sequence_no > a.sequence_no ? b : a, null);
  productInterviewReceipts.set(productInterviewNoticeKey(operation), {
    turnId: operation.turnId, requestId: operation.requestId, clarificationId: operation.clarificationId ?? null,
    previousAnswerId: previousAnswer?.turn_id || null,
  });
};
const currentProductInterviewReceipt = (snapshot, operation) => {
  const processing = snapshot.answer_processing;
  if (processing?.turn_id && processing.request_id && (!operation || operation.turnId === processing.turn_id)) {
    // The server found the operation attached to the latest saved participant Turn.
    return { turnId: processing.turn_id, requestId: processing.request_id, clarificationId: null };
  }
  // An unresolved newer send must never inherit a receipt from an older Turn.
  if (operation) return operation.accepted || operation.status === 'saved' ? operation : null;
  const turns = snapshot.trace?.turns || [];
  const answerId = snapshot.clarification?.response_outcome === 'answered' ? snapshot.clarification.answer_turn_id : null;
  const latestAnswer = turns.filter(turn => turn.speaker_type === 'assessee')
    .reduce((a, b) => !a || b.sequence_no > a.sequence_no ? b : a, null);
  const known = productInterviewReceipts.get(productInterviewNoticeKey());
  const question = snapshot.clarification?.status === 'ASK' && !snapshot.clarification.response_outcome;
  if (known && (!question || known.clarificationId === snapshot.clarification.id)
      && (known.turnId === latestAnswer?.turn_id || known.previousAnswerId === (latestAnswer?.turn_id || null))
      && (!answerId || known.turnId === answerId)) return known;
  if (!productProcessingPending(snapshot) && snapshot.blocking_system_wait !== true) return null;
  const last = turns.reduce((a, b) => !a || b.sequence_no > a.sequence_no ? b : a, null);
  const turn = answerId ? turns.find(item => item.turn_id === answerId) : last;
  // On reload only the current last answer or the exact M7 answer is conclusive.
  return turn?.speaker_type === 'assessee' && turn.turn_id
    ? { turnId: turn.turn_id, requestId: turn.request_id, clarificationId: answerId ? snapshot.clarification.id : null } : null;
};
const clearProductInterviewNotice = () => {
  if (interviewError.dataset.productCommandRecovery !== 'true') return;
  showError(interviewError, '');
  delete interviewError.dataset.productCommandRecovery;
  delete interviewError.dataset.tone;
  interviewError.classList.remove('processing-notice');
};
const checkProductInterviewAnswer = async (operation) => {
  const value = await readProductInterviewAnswerStatus(operation);
  if (!isProductInterviewPresentationCurrent(operation)) return;
  applyProductInterviewAnswerStatus(operation, value, confirmedProductInterviewSnapshot);
  const pending = readProductInterviewAnswer(operation);
  if (value.status === 'absent' && pending?.status === 'unknown'
      && pending.requestId === operation.requestId && pending.turnId === operation.turnId) {
    saveProductInterviewAnswer({ ...pending, absenceChecked: true });
  }
  await loadProductRuntime();
};

const retryRejectedProductAnswer = async (operation) => {
  const snapshot = await loadProductRuntime();
  const pending = readProductInterviewAnswer(operation);
  if (!snapshot || !isProductInterviewPresentationCurrent(operation)
      || pending?.requestId !== operation.requestId || pending.rejectionConfirmed !== true
      || !confirmedProductInterviewCanSend || productInterviewSourcePhase(snapshot) !== operation.sourcePhase
      || durableDraft?.conflicted()) return;
  const draftValue = interviewTextarea.value;
  if (!draftValue.trim()) {
    interviewTextarea.focus();
    return;
  }
  productAnswerStorage().removeItem(productInterviewAnswerKey(operation));
  await sendProductInterviewAnswer(draftValue.trim(), { scope: operation, draftValue });
};

const renderProductInterviewNotice = (snapshot) => {
  const scope = productInterviewAnswerScope();
  const operation = readProductInterviewAnswer();
  const sending = productInterviewRequests.get(productInterviewRequestKey(scope));
  const receipt = currentProductInterviewReceipt(snapshot, operation);
  const unread = productInterviewReadFailure === productInterviewNoticeKey();
  const caption = interviewPanel.querySelector('.interview-timer-caption');
  if (caption) {
    const lastKnown = unread || (['unknown', 'rejected'].includes(operation?.status) && !receipt && !operation.rejectionConfirmed);
    caption.textContent = lastKnown && Number.isFinite(state.assessmentRemainingSeconds)
      ? 'Последний известный остаток' : 'Осталось на ответы';
  }
  const processing = snapshot.answer_processing;
  const waiting = productProcessingPending(snapshot) || snapshot.blocking_system_wait === true
    || (processing?.status === 'pending' && receipt?.turnId === processing.turn_id);
  const failed = productProcessingFailed(snapshot)
    || (['failed', 'rejected_late'].includes(processing?.status) && receipt?.turnId === processing.turn_id);
  const question = snapshot.clarification?.status === 'ASK' && !snapshot.clarification.response_outcome;
  const receiptInTrace = receipt && (snapshot.trace?.turns || []).some(turn => turn.turn_id === receipt.turnId
    && turn.speaker_type === 'assessee' && (!turn.request_id || !receipt.requestId || receipt.requestId === turn.request_id));
  const options = { lockControls: false };
  const statusOptions = receipt?.requestId
    ? { ...options, onCheck: () => checkProductInterviewAnswer({ ...scope, ...receipt }) }
    : options;
  if (sending && !receipt) {
    showProductCommandRecovery(scope, 'Отправляем ответ…', { ...options, check: false });
    return true;
  }
  if (operation?.status === 'rejected' && operation.rejectionConfirmed === true && !receipt) {
    const couldRetry = !unread && confirmedProductInterviewCanSend
      && productInterviewSourcePhase(snapshot) === operation.sourcePhase && !durableDraft?.conflicted();
    showProductCommandRecovery(scope, 'Ошибка отправки. Текст сохранён в поле.', { ...options, failed: true,
      ...(couldRetry ? { checkLabel: 'Повторить отправку', onCheck: () => retryRejectedProductAnswer(operation) }
        : { check: unread }) });
    return true;
  }
  if (operation?.status === 'unknown' && operation.absenceChecked && !unread && !receipt
      && confirmedProductInterviewCanSend && productInterviewSourcePhase(snapshot) === operation.sourcePhase
      && !durableDraft?.conflicted()) {
    showProductCommandRecovery(scope, 'Ответ пока не сохранён. Текст остался в поле.', { ...options, failed: true,
      checkLabel: 'Повторить отправку', onCheck: () => sendProductInterviewAnswer(operation.text, {
        scope: operation, draftValue: operation.draftValue,
      }) });
    return true;
  }
  if (['unknown', 'rejected'].includes(operation?.status) && !receipt) {
    showProductCommandRecovery(scope, 'Отправка не подтверждена.', { ...options, failed: true,
      checkLabel: 'Проверить отправку', onCheck: () => checkProductInterviewAnswer(operation) });
    return true;
  }
  if (unread && (waiting || receipt || failed)) {
    showProductCommandRecovery(scope, 'Не удалось обновить состояние', { ...statusOptions, failed: true });
    return true;
  }
  if (receipt && operation && !receiptInTrace) {
    showProductCommandRecovery(scope, 'Ответ сохранён. Состояние обработки уточняется.', statusOptions);
    return true;
  }
  if ((waiting || failed) && !question) {
    const saved = receipt ? 'Ответ сохранён. ' : '';
    const savedFailure = snapshot.failure_stage === 'answer' && snapshot.failed_answer_turn_id
      && (!operation || receipt?.turnId === snapshot.failed_answer_turn_id);
    const message = failed ? participantFailureMessage(savedFailure ? 'answer' : 'unknown')
      : receipt && !receiptInTrace ? saved + 'Состояние обработки уточняется.'
      : snapshot.finish_availability?.reason === 'WAIT_TECHNICAL' ? saved + 'Состояние обработки требует проверки.'
      : Date.now() >= productProcessingBudget(snapshot) ? saved + 'Обработка занимает больше времени.'
      : receipt ? 'Ответ сохранён. Идёт обработка' : 'Ожидайте завершения обработки.';
    const detail = !failed && receiptInTrace && snapshot.blocking_system_wait === true
      ? 'Время на ответы сейчас не расходуется.' : '';
    showProductCommandRecovery(scope, message, { ...(failed ? options : statusOptions), failed, detail });
    return true;
  }
  const last = (snapshot.trace?.turns || []).reduce((a, b) => !a || b.sequence_no > a.sequence_no ? b : a, null);
  if (receipt && !question && snapshot.current_situation?.status === 'active'
      && (operation || last?.turn_id === receipt.turnId)) {
    showProductCommandRecovery(scope, 'Ответ сохранён.', { ...options, check: false });
    return true;
  }
  clearProductInterviewNotice();
  return false;
};

const productInterviewSourcePhase = (snapshot) => JSON.stringify([
  snapshot.current_situation?.status, snapshot.clarification?.id || null,
  snapshot.clarification?.status || null, snapshot.clarification?.response_outcome || null,
  snapshot.clarification?.question_turn_id || null,
]);

const productProcessingPending = (snapshot) => snapshot?.current_situation?.status === 'scenario_ended'
  && !(snapshot.clarification?.status === 'ASK' && !snapshot.clarification.response_outcome)
  && snapshot.finish_availability?.allowed !== true;

const productProcessingBudget = (snapshot) => {
  const scope = productInterviewAnswerScope();
  const phase = snapshot?.clarification?.answer_turn_id || snapshot?.clarification?.id || 'scenario_end';
  const key = productCommandKey('wait:' + phase, scope);
  let deadline = productProcessingBudgets.get(key);
  if (!deadline) {
    try { deadline = Number(window.sessionStorage.getItem(key)); } catch { /* page cache below */ }
    if (!Number.isFinite(deadline) || deadline <= 0) deadline = Date.now() + 45000;
    productProcessingBudgets.set(key, deadline);
    try { window.sessionStorage.setItem(key, String(deadline)); } catch { /* bounded in this page */ }
  }
  return deadline;
};

const productProcessingFailed = (snapshot) => snapshot?.finish_availability?.allowed !== true
  && (Boolean(snapshot?.failure_stage) || snapshot?.pipeline?.status === 'failed'
    || snapshot?.finish_availability?.reason === 'ANALYSIS_FAILED'
    || ['failed', 'rejected_late'].includes(snapshot?.answer_processing?.status));

const productRuntimePollAllowed = () => confirmedProductInterviewSnapshot?.between_situations
  || !(productProcessingPending(confirmedProductInterviewSnapshot)
  || readProductCommand('scenario_end', productInterviewAnswerScope())
  || readProductCommand('finish_situation', productInterviewAnswerScope()))
  || (!productProcessingFailed(confirmedProductInterviewSnapshot)
    && confirmedProductInterviewSnapshot?.finish_availability?.reason !== 'WAIT_TECHNICAL'
    && Date.now() < productProcessingBudget(confirmedProductInterviewSnapshot));

const productInterviewSourceReady = (snapshot) => snapshot.clarification?.status === 'ASK' && !snapshot.clarification.response_outcome
  ? snapshot.current_situation?.status === 'scenario_ended' && Boolean(snapshot.clarification.question_turn_id)
  : snapshot.current_situation?.status === 'active';

const productInterviewReceiptAccepted = (receipt, operation) => operation.clarificationId
  ? receipt?.id === operation.clarificationId && receipt.answer_turn_id === operation.turnId
    && receipt.response_outcome === 'answered' && receipt.response_request_id === operation.requestId
  : receipt?.turn?.turn_id === operation.turnId && receipt.turn.speaker_type === 'assessee'
    && receipt.turn.content_text === operation.text && receipt.turn.request_id === operation.requestId;

const productInterviewSnapshotMatches = (snapshot, operation) => snapshot?.cycle_id === operation.cycleId
  && snapshot.current_situation?.assessment_situation_id === operation.situationId;

const readProductInterviewAnswerStatus = async (operation) => {
  const params = 'request_id=' + encodeURIComponent(operation.requestId) + '&turn_id=' + encodeURIComponent(operation.turnId)
    + (operation.clarificationId ? '&clarification_id=' + encodeURIComponent(operation.clarificationId) : '');
  const response = await fetchWithDeadline('/users/assessment/m5/situations/' + encodeURIComponent(operation.situationId)
    + '/answer-status?' + params, { credentials: 'same-origin', cache: 'no-store' });
  const value = await readApiResponse(response, 'Исход отправки пока не подтверждён.');
  if (value.cycle_id !== operation.cycleId || value.assessment_situation_id !== operation.situationId
      || value.request_id !== operation.requestId || value.turn_id !== operation.turnId
      || value.clarification_id !== operation.clarificationId || !['absent', 'accepted'].includes(value.status)) {
    throw new Error('Сервер не подтвердил идентичность исходной отправки.');
  }
  if (value.status === 'accepted' && (value.turn?.turn_id !== operation.turnId
      || value.turn.request_id !== operation.requestId
      || (operation.text !== undefined && value.turn.content_text !== operation.text)
      || value.turn.speaker_type !== 'assessee')) throw new Error('Сохранённый ответ отличается от исходной отправки.');
  return value;
};

const productInterviewAnswerResolved = (operation, value, snapshot) => value.status === 'accepted'
  && (operation.clarificationId || ['applied', 'rejected_late'].includes(value.processing_status)
    || (snapshot && operation.sourcePhase !== productInterviewSourcePhase(snapshot)));

const applyProductInterviewAnswerStatus = (operation, value, snapshot) => {
  const pending = readProductInterviewAnswer(operation);
  if (!pending || pending.requestId !== operation.requestId || pending.turnId !== operation.turnId) return false;
  if (value.status === 'accepted') {
    rememberProductInterviewReceipt(operation);
    clearInterviewDraft({ ...operation, accepted: true });
    const completed = productInterviewAnswerResolved(operation, value, snapshot);
    if (completed) {
      productAnswerStorage().removeItem(productInterviewAnswerKey(operation));
      return true;
    }
    const changed = pending.status !== 'saved';
    saveProductInterviewAnswer({ ...pending, status: 'saved' });
    return changed;
  }
  if (pending.status === 'rejected' && value.status === 'absent'
      && productInterviewSnapshotMatches(snapshot, operation)
      && operation.sourcePhase === productInterviewSourcePhase(snapshot)) {
    if (pending.rejectionConfirmed) return false;
    saveProductInterviewAnswer({ ...pending, rejectionConfirmed: true });
    return true;
  }
  // An absent receipt is not a rejected write. Only a changed source phase can
  // retire its active slot; the original identity/endpoint remains in session.
  if (!pending.accepted && operation.sourcePhase !== productInterviewSourcePhase(snapshot)) {
    productAnswerStorage().setItem(productInterviewAnswerKey(operation) + ':resolved:' + operation.requestId,
      JSON.stringify({ ...pending, status: 'superseded', resolution: 'absent_in_previous_phase' }));
    productAnswerStorage().removeItem(productInterviewAnswerKey(operation));
    clearInterviewDraft(operation);
    return true;
  }
  return false;
};

const recoverProductInterviewAnswer = (operation, snapshot) => {
  const key = productInterviewRequestKey(operation);
  if (productInterviewRequests.has(key) || productInterviewReadbacks.has(key)) return;
  const reading = readProductInterviewAnswerStatus(operation);
  productInterviewReadbacks.set(key, reading);
  void reading.then(async (value) => {
    if (!isProductInterviewPresentationCurrent(operation)) return;
    const checkedSnapshot = value.status === 'absent' && operation.status === 'rejected'
      ? await loadProductRuntime() : snapshot;
    if (!isProductInterviewPresentationCurrent(operation) || !checkedSnapshot) return;
    const changed = applyProductInterviewAnswerStatus(operation, value, checkedSnapshot);
    if (changed && (value.status === 'accepted' || operation.status === 'rejected')) showError(interviewError, '');
    if (changed && productInterviewSnapshotMatches(confirmedProductInterviewSnapshot, operation)) {
      renderProductRuntime(confirmedProductInterviewSnapshot, { fresh: false });
    }
  }).catch(() => { /* A failed readback keeps the original unknown operation. */ })
    .finally(() => { if (productInterviewReadbacks.get(key) === reading) productInterviewReadbacks.delete(key); });
};

const recoverPreviousProductInterviewAnswers = (snapshot, { completedOnly = false } = {}) => {
  const ownerId = String(state.pendingUser?.id || '');
  const prefix = `agent4k.assessmentPending:${snapshot.cycle_id}:`;
  Object.keys(productAnswerStorage()).filter((key) => key.startsWith(prefix) && key.endsWith(':' + ownerId))
    .forEach((key) => {
      let saved;
      try { saved = JSON.parse(productAnswerStorage().getItem(key)); } catch (_error) { return; }
      const operation = readProductInterviewAnswer({ cycleId: snapshot.cycle_id, ownerId,
        situationId: saved?.situationId });
      if (!operation || operation.situationId === snapshot.current_situation?.assessment_situation_id) return;
      const requestKey = productInterviewRequestKey(operation);
      if (productInterviewRequests.has(requestKey) || productInterviewReadbacks.has(requestKey)) return;
      const reading = readProductInterviewAnswerStatus(operation);
      productInterviewReadbacks.set(requestKey, reading);
      void reading.then((value) => {
        // A finished/replaced AS can be reconciled without showing its text in
        // the next AS. Never touch a later account/session or unrelated screen.
        if (operation.ownerId !== String(state.pendingUser?.id || '')
            || operation.identityEpoch !== state.identityEpoch || operation.cycleId !== state.productCycleId
            || !['interview', 'processing'].includes(state.currentScreen)) return;
        // Navigation to processing does not prove the source AS changed. Only
        // a completed server receipt may retire its operation without runtime.
        if (completedOnly && (value.status !== 'accepted'
            || !['applied', 'answered', 'rejected_late'].includes(value.processing_status))) return;
        applyProductInterviewAnswerStatus(operation, value, snapshot);
      }).catch(() => { /* Unknown remains recoverable under its original AS. */ })
        .finally(() => { if (productInterviewReadbacks.get(requestKey) === reading) productInterviewReadbacks.delete(requestKey); });
    });
};

export const recoverCompletedInterviewAnswers = (cycleId) => {
  if (state.currentScreen === 'processing' && cycleId === state.productCycleId) {
    recoverPreviousProductInterviewAnswers({ cycle_id: cycleId, current_situation: null }, { completedOnly: true });
  }
};

const reconcileProductInterviewAnswer = (snapshot) => {
  const scope = { ...productInterviewAnswerScope(), cycleId: snapshot.cycle_id,
    situationId: snapshot.current_situation?.assessment_situation_id };
  const operation = readProductInterviewAnswer(scope);
  if (!operation) return null;
  if (operation.status === 'rejected' && operation.rejectionConfirmed
      && operation.sourcePhase !== productInterviewSourcePhase(snapshot)) {
    applyProductInterviewAnswerStatus(operation, { status: 'absent' }, snapshot);
    return null;
  }
  if (operation.status === 'prepared' && !productInterviewRequests.has(productInterviewRequestKey(operation))) {
    productAnswerStorage().removeItem(productInterviewAnswerKey(operation));
    return null;
  }
  const saved = (snapshot.trace?.turns || []).some((turn) => turn.turn_id === operation.turnId
    && turn.speaker_type === 'assessee' && turn.content_text === operation.text);
  if (!saved) return operation;
  rememberProductInterviewReceipt(operation);
  clearInterviewDraft({ ...operation, accepted: true });
  // M5 commits the participant Turn before provider processing. Keep a lost
  // receipt recoverable with the same identity while its source phase remains.
  if (operation.accepted) {
    productAnswerStorage().removeItem(productInterviewAnswerKey(operation));
    return null;
  }
  operation.status = 'saved';
  saveProductInterviewAnswer(operation);
  return operation;
};

const renderProductInterviewAnswerDelivery = (snapshot, operation) => {
  const busy = operation && productInterviewRequests.has(productInterviewRequestKey(operation));
  const savedRow = operation && [...interviewMessages.children].some((row) => row.dataset.turnId === operation.turnId);
  const pendingTurnId = busy && !operation.accepted && !savedRow ? operation.turnId : null;
  const localRows = [...interviewMessages.children].filter((row) => row.dataset.pendingTurnId);
  localRows.filter((row) => row.dataset.pendingTurnId !== pendingTurnId).forEach((row) => row.remove());
  if (!operation) return;
  if (!busy && !operation.rejectionConfirmed) recoverProductInterviewAnswer(operation, snapshot);
  if (pendingTurnId && !localRows.some(row => row.dataset.pendingTurnId === pendingTurnId)) {
    const row = addInterviewMessage('user', operation.text, null, { scroll: false });
    row.dataset.pendingTurnId = pendingTurnId;
  }
  // Keep the source text visible and block only a new submit while its receipt
  // is uncertain. The status action can check that exact original operation.
  if (busy) interviewTextarea.disabled = true;
  if (operation.status === 'unknown' && !busy) interviewTextarea.readOnly = true;
  interviewSubmitButton.disabled = true;
  if (operation.status !== 'saved' && !operation.rejectionConfirmed) interviewFinishButton.disabled = true;
};

const createProductInterviewTurnId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join('-');
  }
  throw new Error('Браузер не может создать идентификатор ответа. Откройте оценку в актуальном браузере.');
};

const prepareProductInterviewAnswer = (text, draftValue, scope = productInterviewAnswerScope(),
  draftRevision = interviewDraftContext(interviewDraftKey())?.revision || null) => {
  if (!isProductInterviewPresentationCurrent(scope)) throw new Error('Ситуация изменилась. Вернитесь к текущему ответу.');
  if (typeof text !== 'string' || !text.trim() || text.length > 10000 || typeof draftValue !== 'string') {
    throw new Error('Введите ответ длиной от 1 до 10000 символов.');
  }
  if (durableDraft?.conflicted()) throw new Error('Выберите, с каким текстом черновика продолжить.');
  let existing = readProductInterviewAnswer(scope);
  if (existing?.status === 'prepared' && existing.text !== text) {
    productAnswerStorage().removeItem(productInterviewAnswerKey(existing));
    existing = null;
  }
  if (existing) {
    if (existing.text !== text) throw new Error('Сначала проверьте сохранение предыдущего ответа кнопкой в сообщении.');
    return existing;
  }
  if (productAnswerStorage().getItem(productInterviewAnswerKey(scope))) {
    throw new Error('Не удалось проверить сохранённую операцию отправки. Обновите историю.');
  }
  if (!isProductInterviewAnswerCurrent(scope)
      || !productInterviewSnapshotMatches(confirmedProductInterviewSnapshot, scope)) {
    throw new Error('Ситуация изменилась. Дождитесь обновления истории перед отправкой.');
  }
  const snapshot = confirmedProductInterviewSnapshot;
  const clarification = snapshot.clarification;
  const isClarification = clarification?.status === 'ASK' && !clarification.response_outcome;
  const operation = { cycleId: scope.cycleId, situationId: scope.situationId, ownerId: scope.ownerId,
    identityEpoch: scope.identityEpoch, viewGeneration: scope.viewGeneration, text, draftValue,
    draftRevision, draftSlotId: typeof durableDraft !== 'undefined' ? durableDraft?.slotId() : null, requestId: createOperationId(), turnId: createProductInterviewTurnId(),
    clarificationId: isClarification ? clarification.id : null,
    sourcePhase: productInterviewSourcePhase(snapshot), status: 'prepared', accepted: false,
    expiresAt: snapshot.status?.calendar_deadline || snapshot.status?.deadline || null,
    attemptCount: 0,
    endpoint: isClarification
      ? '/users/assessment/m7/clarifications/' + encodeURIComponent(clarification.id) + '/answers'
      : '/users/assessment/m5/situations/' + encodeURIComponent(scope.situationId) + '/turns' };
  productInterviewReceipts.delete(productInterviewNoticeKey(operation));
  saveProductInterviewAnswer(operation);
  return operation;
};

export const sendProductInterviewAnswer = async (text, { draftValue = interviewTextarea.value,
  scope = productInterviewAnswerScope(), draftRevision = interviewTextarea.dataset.draftRevision || null } = {}) => {
  const key = productInterviewRequestKey(scope);
  if (productInterviewRequests.has(key)) return { busy: true };
  let operation;
  try { operation = prepareProductInterviewAnswer(text, draftValue, scope, draftRevision); }
  catch (error) {
    if (isProductInterviewPresentationCurrent(scope)) showInterviewRuntimeError(error);
    return { accepted: false };
  }
  // A runtime poll started before this command may carry a valid but older
  // projection. The command's own readback will load the authoritative state.
  productRuntimeMutationGeneration += 1;
  productInterviewRequests.set(key, operation);
  productInterviewOwnSendScroll = operation;
  if (isProductInterviewPresentationCurrent(operation)) {
    showError(interviewError, '');
    renderProductRuntime(confirmedProductInterviewSnapshot, { fresh: false });
  }
  try {
    return await submitAssessmentMessage(text, operation);
  } catch (error) {
    if (isProductInterviewPresentationCurrent(operation) && operation.status !== 'prepared') {
      productInterviewReadFailure = productInterviewNoticeKey(operation);
    }
    if (!operation.accepted && error?.productTurnPostRejected === true && operation.lastPostFresh === true) {
      operation.status = 'rejected';
      saveProductInterviewAnswer(operation);
      // A 409 can also come from processing after the Turn has been committed.
      // Only the exact readback may upgrade this to a retryable refusal.
      try {
        const value = await readProductInterviewAnswerStatus(operation);
        if (isProductInterviewPresentationCurrent(operation)) {
          applyProductInterviewAnswerStatus(operation, value, confirmedProductInterviewSnapshot);
          if (value.status === 'absent') await loadProductRuntime();
        }
      } catch { /* Preserve the original operation for a later check. */ }
    }
    if (isProductInterviewPresentationCurrent(operation) && operation.status === 'prepared') {
      showError(interviewError, assessmentRuntimeErrorMessage(error, { draftSaved: isCurrentInterviewDraftSaved() }));
    }
    return { accepted: operation.accepted, pending: operation.status !== 'prepared', error };
  } finally {
    if (productInterviewRequests.get(key) === operation) productInterviewRequests.delete(key);
    if (operation.status === 'prepared') {
      const pending = readProductInterviewAnswer(operation);
      if (pending?.requestId === operation.requestId) productAnswerStorage().removeItem(productInterviewAnswerKey(operation));
    }
    if (isProductInterviewPresentationCurrent(operation)) {
      // Existing runtime projection restores phase-owned controls, then the
      // delivery hook applies only its own unresolved-operation UI lock.
      if (productInterviewSnapshotMatches(confirmedProductInterviewSnapshot, operation)) {
        renderProductRuntime(confirmedProductInterviewSnapshot, { fresh: false });
      }
      resumeProductRuntimePolling();
    }
  }
};

export const isCycleAssessment = () =>
  state.assessmentRuntimeKind === 'cycle' && Boolean(state.productCycleId);

const payloadText = (payload, keys) => keys
  .map((key) => typeof payload?.[key] === 'string' ? payload[key].trim() : '')
  .find(Boolean) || '';

const payloadItems = (payload, keys, numberMaterials = false) => {
  const value = keys.map((key) => payload?.[key]).find(Array.isArray);
  if (!value) return [];
  return value.map((item) => {
    if (typeof item === 'string') return item.trim();
    if (!item || typeof item !== 'object') return '';
    const title = payloadText(item, ['title', 'name', 'label']);
    const id = numberMaterials ? payloadText(item, ['material_id']) : '';
    const body = payloadText(item, ['content', 'description', 'text']);
    const heading = id && title && title !== id && !title.startsWith(`${id} — `) ? `${id} — ${title}` : title || id;
    return [heading, body].filter(Boolean).join(': ');
  }).filter(Boolean);
};

const addProductSituationMessage = (payload, materialsOpen) => {
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
  const role = payloadText(source, ['assessee_position', 'role', 'position']);
  const sections = [
    ['', payloadText(source, ['introduction'])],
    ['', payloadText(source, ['initial_situation', 'situation', 'context', 'content'])],
    ['', payloadText(source, ['trigger'])],
    ['Участники', payloadText(source, ['participants_and_positions'])],
    ['Ваша задача', payloadText(source, ['assessee_task', 'task', 'question'])],
    ['Условия', payloadText(source, ['conditions_and_constraints', 'conditions', 'constraints'])],
  ].filter(([, body]) => body);
  const numberMaterials = source?.number_initial_materials === true;
  const materials = payloadItems(source, ['initial_materials', 'available_materials', 'materials', 'attachments'], numberMaterials);

  if (role) {
    const caption = document.createElement('p');
    caption.className = 'product-situation-role';
    caption.textContent = 'Ваша роль в ситуации · ' + role;
    bubble.append(caption);
  }
  if (title) {
    const heading = document.createElement('h3');
    heading.className = 'product-situation-title';
    heading.textContent = title;
    bubble.appendChild(heading);
  }
  sections.forEach(([label, body]) => bubble.appendChild(renderInterviewStructuredBlock({ label, body })));
  if (materials.length) {
    const disclosure = document.createElement('details');
    disclosure.className = 'product-situation-materials';
    disclosure.open = materialsOpen ?? numberMaterials;
    const summary = document.createElement('summary');
    summary.textContent = 'Доступные сведения';
    disclosure.append(summary, renderInterviewStructuredBlock({ items: materials }));
    bubble.append(disclosure);
  }
  if (!title && !role && !sections.length && !materials.length) {
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
  if (!['material_disclosed', 'mandatory_update'].includes(event?.event_type)) return null;
  const payload = event?.payload_json || {};
  if (payload.recipient && payload.recipient !== 'assessee') return null;
  const content = payload.content;
  if (typeof content === 'string') return content;
  if (!content || typeof content !== 'object' || Array.isArray(content)) return null;
  const title = payloadText(content, ['title', 'name', 'label']);
  const body = payloadText(content, ['text', 'content', 'description']);
  return [title, body].filter(Boolean).join(': ') || null;
};

const serverRemainingSeconds = (value) => {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
};

const productTimePaused = (snapshot) => ['paused', 'interrupted'].includes(snapshot.status?.collection_status)
  || snapshot.blocking_system_wait === true;

const nextBoundary = (snapshot) => snapshot?.next_preparation_after || snapshot?.route?.positions?.find(position =>
  position.position_no === snapshot.participant_progress?.last_completed_position_no)?.current_assessment_situation_id;

const setNextFeedback = (text) => {
  const feedback = interviewMessages.querySelector('[data-next-preparation-feedback]');
  if (feedback) feedback.textContent = text;
};

const requestNextSituation = async (snapshot, action) => {
  const scope = productInterviewAnswerScope();
  const afterAs = nextBoundary(snapshot);
  const current = () => isProductInterviewAnswerCurrent(scope)
    && nextBoundary(confirmedProductInterviewSnapshot) === afterAs;
  const requestKey = nextSituationRequestKey(scope, afterAs);
  if (!current() || nextSituationRequests.has(requestKey)) return;
  const button = interviewMessages.querySelector('.next-situation-button');
  const preparationScope = { ...scope, situationId: afterAs };
  const path = '/users/assessment/m7/cycles/' + encodeURIComponent(scope.cycleId);
  const post = async (url, body) => readApiResponse(await fetchWithDeadline(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }), 'Не удалось перейти к следующей ситуации.');
  const read = async (operationId) => readApiResponse(await fetchWithDeadline(
    '/users/assessment/cycles/preparation/' + encodeURIComponent(operationId), { credentials: 'same-origin' },
  ), 'Не удалось прочитать состояние подготовки.');

  nextSituationRequests.set(requestKey, true);
  productRuntimeMutationGeneration += 1;
  if (button) button.disabled = true;
  setNextFeedback('');
  try {
    if (action === 'complete') {
      await completeProductCycle();
      return;
    }
    if (action === 'present') {
      await post(path + '/present-next', snapshot.next_presentation);
    } else {
      let pending = readProductCommand('next', preparationScope);
      if (action === 'retry' || action === 'prepare') {
        pending = saveProductCommand('next', preparationScope,
          action === 'retry' ? createOperationId() : 'next:' + afterAs);
      }
      if (pending && !pending.refused) {
        const submit = () => post(path + '/next', {
          idempotency_key: pending.operationId, after_assessment_situation_id: afterAs,
        });
        if (action === 'check') {
          try { await read(pending.operationId); }
          catch (error) {
            if (Number(error?.status) !== 404 || !current()) throw error;
            await submit();
          }
        } else {
          try { await submit(); }
          catch (error) {
            if ([403, 409, 422].includes(Number(error?.status))) {
              window.sessionStorage.setItem(productCommandKey('next', preparationScope),
                JSON.stringify({ ...pending, refused: true }));
              throw error;
            }
            // A lost receipt may follow a committed enqueue. Read the original command.
            if (!current()) return;
            await read(pending.operationId);
          }
        }
        clearProductCommand('next', preparationScope);
      } else if (snapshot.preparation_operation?.operation_id) {
        await read(snapshot.preparation_operation.operation_id);
      }
    }
    if (current()) await loadProductRuntime();
  } catch (error) {
    if (!current()) return;
    const refreshed = await loadProductRuntime().catch(() => null);
    if (current() && (!refreshed || refreshed.preparation_operation?.status !== 'failed')) {
      setNextFeedback([403, 409, 422].includes(Number(error?.status))
        ? productNextRefusalMessage(error) : 'Не удалось подтвердить действие. Проверьте состояние оценки.');
    }
  } finally {
    nextSituationRequests.delete(requestKey);
    if (current()) {
      const activeButton = interviewMessages.querySelector('.next-situation-button');
      if (activeButton) activeButton.disabled = false;
    }
  }
};

const renderNextSituation = (snapshot, progress, { fresh }) => {
  const scope = productInterviewAnswerScope();
  const afterAs = nextBoundary(snapshot);
  const op = snapshot.preparation_operation;
  const pending = readProductCommand('next', { ...scope, situationId: afterAs });
  const ready = !!snapshot.next_presentation;
  const failed = op?.status === 'failed';
  const retryPending = pending && pending.operationId !== op?.operation_id;
  const last = (progress.planned_total > 0 && progress.last_completed_position_no >= progress.planned_total)
    || ['NO_ADMISSIBLE_CASE', 'OUT_OF_TIME'].includes(op?.decision_status);
  const action = last ? 'complete' : ready ? 'present' : failed && !retryPending
    ? op.retry_allowed === true ? 'retry' : null : 'check';
  const title = state.assessmentCaseNumber ? `Ситуация ${state.assessmentCaseNumber} завершена` : 'Ситуация завершена';
  const message = last ? 'Подтверждаем завершение оценки.' : ready ? 'Следующая ситуация готова.'
    : failed && !retryPending ? op.error?.message || 'Не удалось подготовить следующую ситуацию. Обратитесь к организатору оценки.'
      : 'Готовим следующую ситуацию.';
  const requestKey = nextSituationRequestKey(scope, afterAs);
  const signature = JSON.stringify([requestKey, op?.operation_id, failed, action, title, message]);
  let card = interviewMessages.querySelector('.interview-next-card');
  if (card?.dataset.signature !== signature) {
    const actionFocused = card?.contains(document.activeElement)
      && document.activeElement.classList.contains('next-situation-button');
    card = document.createElement('section');
    card.className = 'interview-return-card interview-next-card';
    card.dataset.signature = signature;
    card.dataset.preparationState = failed && !retryPending ? 'failed' : '';
    card.dataset.preparationOperation = op?.operation_id || '';
    const icon = document.createElement('div');
    icon.className = 'interview-next-confirmed';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = '✓';
    const heading = document.createElement('h3');
    heading.textContent = title;
    const status = document.createElement('div');
    status.className = 'interview-next-status';
    status.dataset.failed = String(failed && !retryPending && !last && !ready);
    if (status.dataset.failed === 'true') {
      const refusal = document.createElement('strong');
      refusal.textContent = 'Следующая ситуация не открылась.';
      status.append(refusal);
    }
    const copy = document.createElement('p');
    copy.setAttribute('role', 'status');
    copy.textContent = message;
    status.append(copy);
    card.append(icon, heading, status);
    if (action) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'next-situation-button ' + (action === 'present' ? 'primary-button' : 'text-button');
      button.textContent = action === 'present' ? 'Приступить к следующей ситуации'
        : action === 'retry' ? 'Повторить подготовку' : 'Проверить состояние';
      button.addEventListener('click', () => {
        if (!card.isConnected || !isProductInterviewAnswerCurrent(scope)) return;
        const latest = confirmedProductInterviewSnapshot;
        const nextAction = action === 'check' && afterAs && !latest.preparation_operation
          && !readProductCommand('next', { ...scope, situationId: afterAs }) ? 'prepare' : action;
        return requestNextSituation(latest, nextAction);
      });
      (action === 'present' ? card : status).append(button);
    }
    const feedback = document.createElement('p');
    feedback.dataset.nextPreparationFeedback = '';
    feedback.setAttribute('role', 'status');
    card.append(feedback);
    interviewMessages.innerHTML = '';
    interviewMessages.append(card);
    if (actionFocused) card.querySelector('.next-situation-button')?.focus({ preventScroll: true });
    if (renderedProductMessages) renderedProductMessages.node = card;
  }
  const button = card.querySelector('.next-situation-button');
  if (button) button.disabled = nextSituationRequests.has(requestKey);
  const automatic = last ? 'complete' : !ready && !op && !pending && afterAs ? 'prepare' : null;
  if (fresh && automatic && !nextSituationRequests.has(requestKey)) {
    queueMicrotask(() => {
      if (confirmedProductInterviewSnapshot === snapshot) void requestNextSituation(snapshot, automatic);
    });
  }
};

const serverPositionCount = (value) => Number.isInteger(value) && value >= 0 ? value : null;

const clearUnconfirmedProductTime = () => {
  state.assessmentRemainingSeconds = null;
  interviewTimerBadge.classList.remove('is-paused');
  updateInterviewTimer();
};

const returnContinueIdentity = (value) => [
  state.pendingUser?.id, value.cycle_id, value.position_no,
  value.current_assessment_situation_id, value.current_assessment_situation_status,
  value.generation_operation_id ?? null,
];

const pendingReturnContinue = (value) => {
  let saved = null;
  try { saved = JSON.parse(window.sessionStorage.getItem(RETURN_CONTINUE_PENDING_KEY) || 'null'); } catch { /* stale storage */ }
  const identity = returnContinueIdentity(value);
  if (saved?.identity && JSON.stringify(saved.identity) === JSON.stringify(identity) && saved.key) return saved;
  saved = { identity, key: createOperationId() };
  window.sessionStorage.setItem(RETURN_CONTINUE_PENDING_KEY, JSON.stringify(saved));
  return saved;
};

const clearPendingReturnContinue = (value) => {
  let saved = null;
  try { saved = JSON.parse(window.sessionStorage.getItem(RETURN_CONTINUE_PENDING_KEY) || 'null'); } catch { /* stale storage */ }
  if (saved?.identity && JSON.stringify(saved.identity) === JSON.stringify(returnContinueIdentity(value))) {
    window.sessionStorage.removeItem(RETURN_CONTINUE_PENDING_KEY);
  }
};

const clearConfirmedReturnContinue = (snapshot) => {
  if (snapshot.status?.collection_status !== 'active' || !snapshot.current_situation) return;
  let saved = null;
  try { saved = JSON.parse(window.sessionStorage.getItem(RETURN_CONTINUE_PENDING_KEY) || 'null'); } catch { /* stale storage */ }
  if (saved?.identity?.[0] === state.pendingUser?.id && saved.identity[1] === snapshot.cycle_id) {
    window.sessionStorage.removeItem(RETURN_CONTINUE_PENDING_KEY);
  }
};

const olderProductRuntimeSnapshot = (incoming, presented) => {
  if (!presented || incoming?.cycle_id !== presented.cycle_id
      || incoming.current_situation?.assessment_situation_id !== presented.current_situation?.assessment_situation_id) {
    return false;
  }
  const phases = ['admitted', 'active', 'scenario_ended', 'closed'];
  if (phases.indexOf(incoming.current_situation?.status) >= 0
      && phases.indexOf(incoming.current_situation?.status) < phases.indexOf(presented.current_situation?.status)) return true;
  const incomingPreparation = incoming.preparation_operation;
  const knownPreparation = presented.preparation_operation;
  if (incomingPreparation?.operation_id && incomingPreparation.operation_id === knownPreparation?.operation_id) {
    // A worker may legitimately requeue the same operation after a lease/retry.
    // Compare server read times instead of treating queue status as monotonic.
    const receivedAt = Date.parse(incomingPreparation.preparation?.read_at);
    const presentedAt = Date.parse(knownPreparation.preparation?.read_at);
    if (Number.isFinite(receivedAt) && Number.isFinite(presentedAt) && receivedAt < presentedAt) return true;
  }
  // M5 Turn and scenario event history is append-only within one AS. A poll
  // started before a command may arrive after its authoritative readback.
  for (const [field, id] of [['turns', 'turn_id'], ['events', 'event_id']]) {
    const known = presented.trace?.[field] || [];
    if (!known.length) continue;
    const received = new Set((incoming.trace?.[field] || []).map((item) => String(item[id])));
    if (known.some((item) => !received.has(String(item[id])))) return true;
  }
  return false;
};

const renderProductRuntime = (snapshot, { fresh = true } = {}) => {
  if (olderProductRuntimeSnapshot(snapshot, confirmedProductInterviewSnapshot)) {
    return confirmedProductInterviewSnapshot;
  }
  interviewPanel.classList.toggle('between-situations', Boolean(snapshot.between_situations));
  interviewPanel.classList.toggle('product-answer-screen', Boolean(snapshot.current_situation && !snapshot.between_situations));
  const previousSituationId = state.productAssessmentSituationId;
  if (renderedProductCycleId !== snapshot.cycle_id) {
    state.caseOutcomeByNumber = {};
    renderedProductCycleId = snapshot.cycle_id;
  }
  const current = snapshot.current_situation;
  const previousCaseKey = state.activeInterviewCaseKey;
  const previousScrollTop = interviewScrollArea?.scrollTop || 0;
  const wasNearBottom = isInterviewNearBottom();
  const sameSituation = renderedProductMessages?.cycleId === snapshot.cycle_id
    && renderedProductMessages?.situationId === current?.assessment_situation_id
    && renderedProductMessages?.node === interviewMessages.firstChild;
  const routePositions = Array.isArray(snapshot.route?.positions) ? snapshot.route.positions : [];
  const currentPosition = routePositions.find((position) =>
    position.current_assessment_situation_id === current?.assessment_situation_id)
    || routePositions.find((position) => ['in_progress', 'awaiting_replacement'].includes(position.state));
  const progress = snapshot.participant_progress || {
    planned_total: snapshot.route?.progress?.total_positions, current_position_no: currentPosition?.position_no,
  };
  interviewPanel.classList.remove('return-required');
  interviewCaseBadge.hidden = Boolean(snapshot.between_situations);
  state.assessmentRuntimeKind = 'cycle';
  state.productCycleId = snapshot.cycle_id;
  state.productAssessmentSituationId = current?.assessment_situation_id || null;
  if (snapshot.between_situations && previousSituationId) {
    clearProductCommand('finish_situation', { cycleId: snapshot.cycle_id,
      situationId: previousSituationId, ownerId: String(state.pendingUser?.id || '') });
  }
  state.productClarificationDecisionId = snapshot.clarification?.id || null;
  state.productCycleStatus = snapshot.status?.collection_status || null;
  state.assessmentRemainingSeconds = serverRemainingSeconds(snapshot.status?.remaining_seconds);
  state.assessmentCaseNumber = serverPositionCount(snapshot.between_situations
    ? progress.last_completed_position_no : progress.current_position_no) || null;
  state.assessmentTotalCases = serverPositionCount(progress.planned_total);
  state.assessmentCompletedCases = serverPositionCount(snapshot.route?.progress?.completed_positions);
  state.assessmentCaseTitle = current?.participant_payload?.title || current?.participant_payload?.case_title || 'Оценочная ситуация';
  state.activeInterviewCaseKey = current?.assessment_situation_id || null;
  persistAssessmentContext();
  confirmedProductInterviewSnapshot = snapshot;
  if (fresh) productInterviewReadFailure = null;
  const commandScope = productInterviewAnswerScope();
  if (current?.status === 'scenario_ended' &&
      (snapshot.clarification?.status === 'ASK' || snapshot.finish_availability?.allowed === true)) {
    clearProductCommand('scenario_end', commandScope);
  }
  // Clear only the exact accepted revision before a new Turn rotates the draft
  // slot. A newer unsent edit can then follow the dialogue without duplicating
  // the already accepted text as a new draft.
  const pendingAnswer = reconcileProductInterviewAnswer(snapshot);
  restoreInterviewDraft();
  recoverPreviousProductInterviewAnswers(snapshot);

  const initialMaterials = current?.participant_payload?.initial_materials;
  const initialMaterialTextById = new Map((Array.isArray(initialMaterials) ? initialMaterials : [])
    .map((material) => [material?.material_id, payloadItems({ materials: [material] }, ['materials'])[0]])
    .filter(([id, text]) => id && text));
  const dialogue = [
    ...(snapshot.trace?.turns || []).map((item) => ({...item, text:item.content_text,
      role:item.speaker_type === 'assessee' ? 'user' : 'assistant'})),
    ...(snapshot.trace?.events || []).map((event) => {
      const delivery = event.payload_json;
      const privateMessage = delivery?.recipient_ids?.length === 1 && delivery.recipient_ids[0] === 'assessee';
      const sender = delivery?.speaker_name;
      return { ...event, text: productEventText(event), role: 'assistant',
        speaker_name: sender && privateMessage ? sender + ' · лично вам' : sender };
    })
      // The start message already contains initial materials. Preserve later
      // content changes and mandatory updates, even when they reuse an ID.
      .filter((event) => event.event_type !== 'material_disclosed'
        || event.text !== initialMaterialTextById.get(event.material_id)),
  ].sort((a, b) => a.sequence_no - b.sequence_no);
  const clarification = snapshot.clarification;
  if (clarification?.status === 'ASK' && !clarification.response_outcome && clarification.question?.text &&
      !dialogue.some((turn) => turn.turn_id === clarification.question_turn_id)) {
    dialogue.push({ role: 'assistant', speaker_type: 'assessment', text: clarification.question.text });
  }
  const rows = dialogue.filter(item => item.text);
  const cardKey = JSON.stringify(current?.participant_payload);
  const rowKeys = rows.map(item => JSON.stringify(item));
  const appendOnly = sameSituation && renderedProductMessages.cardKey === cardKey
    && renderedProductMessages.rowKeys.every((key, index) => key === rowKeys[index]);
  const messagesChanged = !appendOnly || renderedProductMessages.rowKeys.length !== rowKeys.length;
  if (messagesChanged) {
    cancelInterviewScrollAlignment();
    // Append-only polls keep the existing history and its focused disclosure
    // in the DOM. Other changes preserve the open state on this AS.
    if (!appendOnly) {
      const previousMaterials = sameSituation ? interviewMessages.querySelector('.product-situation-materials') : null;
      const restoreMaterialFocus = document.activeElement && previousMaterials?.contains(document.activeElement);
      const materialsOpen = previousMaterials?.open;
      interviewMessages.innerHTML = '';
      if (current) {
        const situation = addProductSituationMessage(current.participant_payload, materialsOpen);
        if (restoreMaterialFocus) situation.querySelector('summary')?.focus({ preventScroll: true });
      }
    }
    const first = appendOnly ? renderedProductMessages.rowKeys.length : 0;
    for (const item of rows.slice(first)) {
      const label = item.role === 'user' ? null : item.speaker_name
        || (item.speaker_type === 'character' ? 'Собеседник'
          : item.speaker_type === 'assessment' ? 'Уточнение к вашему ответу' : 'Материал ситуации');
      const row = addInterviewMessage(item.role, item.text, label, { scroll: false });
      if (item.turn_id) row.dataset.turnId = item.turn_id;
    }
    renderedProductMessages = { cardKey, rowKeys, node: interviewMessages.firstChild,
      cycleId: snapshot.cycle_id, situationId: current?.assessment_situation_id };
  }
  renderInterviewMeta();
  renderCaseProgress(false);
  interviewPanel.classList.remove('single-turn-mode', 'completed');
  interviewCompleteActions.classList.add('hidden');
  interviewTimerBadge.classList.remove('is-paused');

  if (snapshot.between_situations) {
    interviewFinishButton.classList.add('hidden');
    if (interviewError.dataset.productCommandRecovery === 'true') {
      showError(interviewError, '');
      delete interviewError.dataset.productCommandRecovery;
    }
    stopProductPresence();
    interviewTimerBadge.classList.toggle('is-paused', productTimePaused(snapshot));
    renderNextSituation(snapshot, progress, { fresh });
    interviewTextarea.value = '';
    interviewTextarea.placeholder = 'Ситуация завершена. Следующий ответ станет доступен после перехода.';
    interviewTextarea.disabled = true; interviewSubmitButton.disabled = true; interviewFinishButton.disabled = true;
    interviewPauseButton?.classList.add('hidden'); interviewAdditionalButton?.classList.add('hidden');
    interviewCaseStatus.textContent = '';
    confirmedProductInterviewCanSend = false;
    if (interviewSubmitLabel) interviewSubmitLabel.textContent = 'Отправить';
    clearProductInterviewNotice();
    updateInterviewTimer(); scheduleInterviewBottomAlignment();
    return snapshot;
  }

  const cycleStatus = snapshot.status?.collection_status;
  const waitingQuestion = clarification?.status === 'ASK' && !clarification.response_outcome;
  const format = current?.response_format;
  const formatLabel = interviewPanel.querySelector('.interview-response-format');
  if (formatLabel) {
    formatLabel.hidden = false;
    formatLabel.textContent = waitingQuestion ? 'Уточнение'
      : format === 'written' ? 'Письменное задание' : format === 'dialogue' ? 'Диалог' : 'Оценочная ситуация';
  }
  const closed = ['collection_closed', 'calculation_pending', 'calculated', 'failed'].includes(cycleStatus);
  const suspended = ['paused', 'interrupted'].includes(cycleStatus);
  interviewTimerBadge.classList.toggle('is-paused', productTimePaused(snapshot));
  interviewTextarea.disabled = closed || suspended || !current;
  interviewSubmitButton.disabled = closed || suspended || !current;
  interviewFinishButton.disabled = closed || suspended || !current || current.status === 'closed' || waitingQuestion
    || (current.status === 'scenario_ended' && snapshot.finish_availability?.allowed !== true);
  // Only recovery of an already saved suspension is available here.
  interviewPauseButton?.classList.toggle('hidden', cycleStatus !== 'paused' || !current);
  interviewAdditionalButton?.classList.toggle('hidden', cycleStatus !== 'interrupted' || !['pending', 'consumed'].includes(snapshot.continuation?.status));
  if (interviewPauseButton) interviewPauseButton.textContent = 'Продолжить оценку';
  if (interviewAdditionalButton) interviewAdditionalButton.textContent = 'Продолжить сохранённое прохождение';
  interviewCaseStatus.textContent = cycleStatus === 'interrupted'
    ? 'Прохождение прервано. Ответы сохранены; доступно продолжение в пределах оставшегося времени.'
    : !current ? 'Нет доступной оценочной ситуации. Для продолжения требуется подготовка назначения.' : '';
  let preparationPanel = interviewPanel.querySelector('.interview-preparation-status');
  if (snapshot.report_preparation) {
    if (!preparationPanel) { preparationPanel = document.createElement('div'); preparationPanel.id = 'interview-preparation-status'; preparationPanel.className = 'interview-preparation-status'; interviewCaseStatus.after(preparationPanel); }
    renderPreparation(preparationPanel, snapshot.report_preparation);
  } else preparationPanel?.remove();
  const sourceReady = productInterviewSourceReady(snapshot);
  const processingFailed = !waitingQuestion && productProcessingFailed(snapshot);
  const answerProcessing = snapshot.answer_processing?.status;
  confirmedProductInterviewCanSend = !interviewSubmitButton.disabled && sourceReady && !processingFailed && snapshot.blocking_system_wait !== true
    && answerProcessing !== 'pending' && answerProcessing !== 'failed';
  interviewTextarea.disabled ||= !sourceReady || processingFailed;
  interviewSubmitButton.disabled = !confirmedProductInterviewCanSend;
  if (interviewTextarea.labels?.[0]) interviewTextarea.labels[0].textContent = waitingQuestion
    ? 'Ваш ответ на уточнение' : 'Ваше сообщение';
  interviewTextarea.placeholder = closed ? 'Сбор ответов завершён.'
    : suspended ? 'Отправка недоступна до продолжения оценки.'
    : processingFailed ? ''
    : current?.status === 'scenario_ended' && !waitingQuestion
      ? snapshot.finish_availability?.allowed === true ? 'Ответы приняты. Можно завершить ситуацию.' : 'Дождитесь завершения обработки'
      : waitingQuestion ? 'Ответьте на уточнение…'
        : format === 'dialogue' ? 'Ответьте собеседнику или задайте вопрос…'
          : 'Напишите свой ответ…';
  interviewTextarea.readOnly = false;
  renderProductInterviewAnswerDelivery(snapshot, pendingAnswer);
  if (interviewTextarea.disabled && sourceReady && !closed && !suspended && !processingFailed) {
    interviewTextarea.placeholder = 'Дождитесь обновления состояния';
  }
  const sendingAnswer = productInterviewRequests.get(productInterviewRequestKey(commandScope));
  if (interviewSubmitLabel) interviewSubmitLabel.textContent = sendingAnswer && !sendingAnswer.accepted ? 'Отправляем...' : 'Отправить';
  if (durableDraft?.conflicted()) interviewSubmitButton.disabled = true;
  const pendingCommand = readProductCommand('scenario_end', commandScope)
    || readProductCommand('finish_situation', commandScope);
  if (!renderProductInterviewNotice(snapshot) && pendingCommand) {
    showProductCommandRecovery(commandScope, 'Итог завершения ситуации пока не подтверждён. Проверьте состояние той же команды.');
  }
  const yourTurn = interviewPanel.querySelector('.interview-your-turn');
  if (yourTurn) yourTurn.hidden = interviewSubmitButton.disabled;
  const hasAnswer = (snapshot.trace?.turns || []).some((turn) => turn.speaker_type === 'assessee');
  interviewFinishButton.disabled ||= !hasAnswer;
  interviewFinishButton.classList.toggle('hidden', interviewFinishButton.disabled);
  updateInterviewTimer();
  // Align after both server messages and the local pending row have their final
  // layout. Only an explicit own send may pull a reader away from old history.
  const ownSend = productInterviewOwnSendScroll && isProductInterviewPresentationCurrent(productInterviewOwnSendScroll);
  if (ownSend || (messagesChanged && (!appendOnly || wasNearBottom))) {
    const targetTop = current && previousCaseKey !== current.assessment_situation_id ? 0 : previousScrollTop;
    scheduleInterviewScrollAlignment({ top: sameSituation ? targetTop : 0,
      followBottom: Boolean(ownSend || (sameSituation && wasNearBottom)) });
  }
  productInterviewOwnSendScroll = null;
  updateInterviewMessagesScrollIndicator();
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
  const scope = productInterviewAnswerScope();
  const current = () => generation === returnPresenceGeneration && isProductInterviewAnswerCurrent(scope);
  const tick = async () => {
    if (!current()) return;
    try {
      const contract = await heartbeatProductPresence();
      if (!current()) return;
      if (!contract) { await loadReturnState(); return; }
      const intervalSeconds = Number(contract.heartbeat_interval_seconds);
      if (!Number.isFinite(intervalSeconds) || intervalSeconds <= 0) {
        throw new Error('Сервер не вернул допустимый интервал подтверждения связи.');
      }
      returnHeartbeatTimer = window.setTimeout(tick, intervalSeconds * 1000);
    } catch (error) {
      if (!current()) return;
      showInterviewRuntimeError(error);
      returnHeartbeatTimer = window.setTimeout(tick, PRODUCT_RUNTIME_POLL_MS);
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
  stopProductPresence();
  if (renderedProductCycleId !== value.cycle_id) {
    state.caseOutcomeByNumber = {};
    renderedProductCycleId = value.cycle_id;
  }
  interviewPanel.classList.remove('between-situations');
  interviewPanel.classList.remove('product-answer-screen');
  interviewPanel.classList.add('return-required');
  interviewCaseBadge.hidden = false;
  interviewPauseButton?.classList.add('hidden');
  interviewAdditionalButton?.classList.add('hidden');
  interviewFinishButton.classList.add('hidden');
  const progress = value.progress || {};
  const completedPositions = serverPositionCount(progress.completed_positions);
  const totalPositions = serverPositionCount(value.participant_progress
    ? value.participant_progress.planned_total : progress.total_positions);
  state.assessmentRuntimeKind = 'cycle';
  state.productCycleId = value.cycle_id;
  state.productAssessmentSituationId = value.current_assessment_situation_id;
  state.productCycleStatus = value.collection_status;
  state.assessmentCaseNumber = serverPositionCount(value.participant_progress
    ? value.participant_progress.current_position_no : value.position_no) || null;
  state.assessmentTotalCases = totalPositions;
  state.assessmentCompletedCases = completedPositions;
  state.assessmentCaseTitle = 'Продолжение оценки';
  renderInterviewMeta();
  renderCaseProgress(false);
  interviewTimerBadge.classList.add('is-paused');
  state.assessmentRemainingSeconds = serverRemainingSeconds(value.remaining_seconds);
  updateInterviewTimer();
  const returnKey = JSON.stringify([returnContinueIdentity(value), state.assessmentCaseNumber,
    totalPositions, value.allowed_action, value.absence_event_id]);
  const previousCard = interviewMessages.firstElementChild;
  if (previousCard?.dataset.returnKey === returnKey && !previousCard.dataset.returnUnconfirmed) return;
  interviewMessages.innerHTML = '';
  const card = document.createElement('section'); card.className = 'interview-return-card assessment-state-card';
  card.dataset.returnKey = returnKey;
  const title = document.createElement('h3'); title.textContent = 'Продолжим оценку?';
  title.id = 'interview-return-title'; card.setAttribute('aria-labelledby', title.id);
  const position = document.createElement('p');
  const positionNo = state.assessmentCaseNumber;
  position.textContent = positionNo && totalPositions && positionNo <= totalPositions
    ? `Вы остановились на ситуации ${positionNo} из ${totalPositions}.`
    : positionNo && !totalPositions ? `Вы остановились на ситуации ${positionNo}. Всего ситуаций пока неизвестно.`
      : 'Место остановки пока не подтверждено.';
  const reason = document.createElement('p');
  reason.className = 'interview-return-note';
  const replacing = value.allowed_action === 'replace_current' && Boolean(value.generation_operation_id);
  const canContinue = value.allowed_action === 'continue_current' || replacing;
  reason.textContent = replacing
    ? 'После продолжения незавершённая ситуация будет заменена. Частичный диалог сохранится в истории прежней ситуации и не переносится в новую.'
    : canContinue ? 'Откроется та же ситуация и сохранённый диалог.'
      : 'Готовность новой ситуации пока не подтверждена. Обновите состояние перед продолжением.';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = canContinue ? 'primary-button' : 'text-button';
  button.textContent = canContinue ? 'Продолжить' : 'Проверить состояние';
  const status = document.createElement('p'); status.setAttribute('role', 'status');
  button.addEventListener('click', async () => {
    const cycleId = value.cycle_id;
    let situationId = state.productAssessmentSituationId;
    const ownerId = state.pendingUser?.id;
    const identityEpoch = state.identityEpoch;
    const viewGeneration = getAssessmentViewGeneration();
    const current = () => state.productCycleId === cycleId && state.pendingUser?.id === ownerId
      && state.identityEpoch === identityEpoch && state.productAssessmentSituationId === situationId
      && state.currentScreen === 'interview' && card.isConnected && viewGeneration === getAssessmentViewGeneration();
    button.disabled = true;
    if (!canContinue) {
      try { await loadProductRuntime(); }
      catch (error) { if (current()) showInterviewRuntimeError(error); }
      finally { if (current()) button.disabled = false; }
      return;
    }
    productRuntimeMutationGeneration += 1;
    card.dataset.returnPending = 'true';
    status.textContent = replacing ? 'Открываем новую ситуацию…' : 'Восстанавливаем ситуацию…';
    try {
      const pending = pendingReturnContinue(value);
      const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(cycleId) + '/return-continue', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_no: value.position_no,
          expected_assessment_situation_id: value.current_assessment_situation_id,
          expected_state: value.current_assessment_situation_status,
          idempotency_key: pending.key, generation_operation_id: value.generation_operation_id ?? null }),
      });
      const continued = await readApiResponse(response, 'Не удалось продолжить оценку.');
      if (!current()) return;
      clearPendingReturnContinue(value);
      if (continued.status === 'collection_closed') {
        openProcessing({ confirmedCollection: { collection_status: continued.status } });
        return;
      }
      state.productAssessmentSituationId = continued.assessment_situation_id;
      situationId = state.productAssessmentSituationId;
      await heartbeatProductPresence();
      if (!current()) return;
      await loadProductRuntime();
    } catch (error) {
      if (!current()) return;
      status.textContent = 'Проверяем, была ли команда принята сервером…';
      try {
        if (!(await loadReturnState())) {
          if (!current()) return;
          await loadProductRuntime();
          if (!current()) return;
          clearPendingReturnContinue(value);
          return;
        }
        // Reuse the pending key after a confirmed return-state read.
        if (current()) { status.textContent = 'Оценка всё ещё на паузе.'; button.disabled = false; }
      } catch (_readbackError) {
        if (!current()) return;
        card.dataset.returnUnconfirmed = 'true';
        status.textContent = `${assessmentRuntimeErrorMessage(error, { draftSaved: isCurrentInterviewDraftSaved() })} Результат пока неизвестен. Обновите состояние перед повтором.`;
        return;
      }
    } finally { delete card.dataset.returnPending; }
  });
  card.append(title, position, reason, button, status); interviewMessages.appendChild(card);
  interviewTextarea.disabled = true; interviewSubmitButton.disabled = true; interviewFinishButton.disabled = true;
  interviewCaseStatus.textContent = '';
  scheduleInterviewBottomAlignment();
};

const loadReturnState = async ({ generation = productRuntimePollGeneration, isCurrent = () => true } = {}) => {
  const requestGeneration = generation ?? productRuntimePollGeneration;
  const mutationGeneration = productRuntimeMutationGeneration;
  const viewGeneration = getAssessmentViewGeneration();
  const cycleId = state.productCycleId;
  const situationId = state.productAssessmentSituationId;
  const ownerId = state.pendingUser?.id;
  const identityEpoch = state.identityEpoch;
  const screen = state.currentScreen;
  const current = () => isCurrent() && state.productCycleId === cycleId && state.pendingUser?.id === ownerId
    && state.productAssessmentSituationId === situationId && state.identityEpoch === identityEpoch
    && state.currentScreen === screen
    && requestGeneration === productRuntimePollGeneration
    && mutationGeneration === productRuntimeMutationGeneration
    && viewGeneration === getAssessmentViewGeneration();
  try {
    const response = await fetchWithDeadline('/users/assessment/m7/cycles/' + encodeURIComponent(cycleId) + '/return-state', { credentials: 'same-origin' });
    if (!current()) return false;
    if (response.status === 409) {
      const blocked = await response.json().catch(() => ({}));
      if (!current()) return false;
      if (['M7_RETURN_CURRENT_POSITION_NOT_FOUND', 'M7_RETURN_POLICY_NOT_SNAPSHOTTED'].includes(blocked.detail)) return false;
      throw new Error(blocked.detail || 'Не удалось проверить состояние возврата.');
    }
    const value = await readApiResponse(response, 'Не удалось проверить состояние возврата.');
    if (!current() || value.cycle_id !== cycleId) return false;
    if (['collection_closed', 'calculation_pending', 'calculated'].includes(value.collection_status)) {
      openProcessing();
      return true;
    }
    if (['continue_current', 'replace_current', 'replacement_candidate_required'].includes(value.allowed_action)) {
      renderReturnCard(value);
      return true;
    }
    return false;
  } catch (error) {
    if (!current()) return false;
    clearUnconfirmedProductTime();
    throw error;
  }
};

let productRuntimeReadSerial = 0;
let productRuntimeRead = null;
export const loadProductRuntime = async ({ generation = productRuntimePollGeneration } = {}) => {
  if (!state.productCycleId) throw new Error('Не удалось определить текущую оценку.');
  const requestGeneration = generation ?? productRuntimePollGeneration;
  // Polling and manual checks share the whole return-state/runtime chain.
  // Only a new context supersedes a read; a slow GET can still be presented.
  if (productRuntimeRead?.current() && productRuntimeRead.generation === requestGeneration) {
    return productRuntimeRead.promise;
  }
  const readSerial = ++productRuntimeReadSerial;
  const mutationGeneration = productRuntimeMutationGeneration;
  const viewGeneration = getAssessmentViewGeneration();
  const cycleId = state.productCycleId;
  let situationId = state.productAssessmentSituationId;
  const ownerId = state.pendingUser?.id;
  const identityEpoch = state.identityEpoch;
  const screen = state.currentScreen;
  const current = () => readSerial === productRuntimeReadSerial && state.productCycleId === cycleId && state.pendingUser?.id === ownerId
    && state.productAssessmentSituationId === situationId && state.identityEpoch === identityEpoch
    && state.currentScreen === screen
    && requestGeneration === productRuntimePollGeneration
    && mutationGeneration === productRuntimeMutationGeneration
    && viewGeneration === getAssessmentViewGeneration();
  const read = { current, generation: requestGeneration, promise: null };
  productRuntimeRead = read;
  read.promise = (async () => {
    try {
      // Check the server-owned pause before fetching any AS content. Reload/login/GET
      // never resumes a recognized absence; only the explicit command above does.
      if (await loadReturnState({ generation, isCurrent: current })) return null;
      if (!current()) return null;
      const response = await fetchWithDeadline('/users/assessment/cycles/' + encodeURIComponent(cycleId) + '/runtime', {
        credentials: 'same-origin',
      });
      const saved = await readApiResponse(response, 'Не удалось восстановить состояние оценки.');
      if (!current() || saved.cycle_id !== cycleId) return null;
      if (olderProductRuntimeSnapshot(saved, confirmedProductInterviewSnapshot)) {
        return confirmedProductInterviewSnapshot;
      }
      clearConfirmedReturnContinue(saved);
      state.productAssessmentSituationId = saved.current_situation?.assessment_situation_id || null;
      situationId = state.productAssessmentSituationId;
      const terminal = ['collection_closed', 'calculation_pending', 'calculated', 'failed']
        .includes(saved.status?.collection_status);
      const snapshot = renderProductRuntime(saved);
      if (!terminal && saved.return_policy_enabled && saved.current_situation && returnPresenceCycleId !== saved.cycle_id
          && saved.current_situation.status !== 'admitted') {
        try {
          const presenceContract = await heartbeatProductPresence();
          if (!current()) return null;
          if (presenceContract) {
            returnPresenceCycleId = saved.cycle_id;
            startProductPresence(presenceContract);
          } else {
            await loadReturnState({ generation, isCurrent: current });
          }
        } catch (error) {
          if (!current()) return null;
          showInterviewRuntimeError(error);
          returnPresenceCycleId = saved.cycle_id;
          startProductPresence();
        }
      }
      if (terminal && returnPresenceCycleId) {
        stopProductPresence();
      }
      if (terminal && !interviewPanel.classList.contains('hidden')) {
        openProcessing({ confirmedCollection: snapshot.status });
      }
      return snapshot;
    } catch (error) {
      if (!current()) return null;
      clearUnconfirmedProductTime();
      throw error;
    } finally {
      if (productRuntimeRead === read) productRuntimeRead = null;
    }
  })();
  return read.promise;
};

const waitForProductClarification = async (previousDecisionId = null) => {
  const scope = productInterviewAnswerScope();
  const deadline = productProcessingBudget(confirmedProductInterviewSnapshot);
  while (Date.now() < deadline) {
    if (!isProductInterviewAnswerCurrent(scope)) return null;
    const snapshot = await loadProductRuntime();
    if (!snapshot || !isProductInterviewAnswerCurrent(scope)) return null;
    const decision = snapshot.clarification;
    if (productProcessingFailed(snapshot) || snapshot.finish_availability?.reason === 'WAIT_TECHNICAL') return snapshot;
    if ((decision?.status === 'ASK' && !decision.response_outcome && decision.id !== previousDecisionId)
        || snapshot.finish_availability?.allowed === true) return snapshot;
    await new Promise((resolve) => window.setTimeout(resolve, Math.min(PRODUCT_RUNTIME_POLL_MS, Math.max(0, deadline - Date.now()))));
  }
  throw Object.assign(new Error('Ответ сохранён. Обработка продолжается.'), {
    name: 'ClarificationWaitLimit',
  });
};

const completeProductCycle = () => {
  const cycleId = state.productCycleId;
  const afterAs = nextBoundary(confirmedProductInterviewSnapshot);
  stopProductPresence();
  const completion = fetchWithDeadline('/users/assessment/m7/cycles/' + encodeURIComponent(cycleId) + '/completion', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'complete', reason: 'user_completed_scenario', idempotency_key: 'complete-after:' + afterAs }),
  }).then((response) => readApiResponse(response, 'Не удалось завершить сбор оценки.'))
    .catch(() => null); // A lost receipt can follow a committed closure. Read the same Cycle before offering any next step.
  openProcessing({ cycleId, completion });
};

export const finishProductAssessment = async () => {
  const scope = productInterviewAnswerScope();
  let snapshot = await loadProductRuntime();
  if (!snapshot || !isProductInterviewAnswerCurrent(scope)) return;
  const current = snapshot.current_situation;
  if (!current) throw new Error('Текущая ситуация не найдена.');
  if (readProductCommand('scenario_end', scope) || readProductCommand('finish_situation', scope)) {
    showProductCommandRecovery(scope, 'Проверяем исход предыдущего завершения ситуации. Повторную команду не отправляем.');
    return;
  }
  if (!(snapshot.trace?.turns || []).some((turn) => turn.speaker_type === 'assessee')) {
    throw new Error('Сначала отправьте хотя бы один ответ по текущей ситуации.');
  }
  if (current.status === 'active') {
    const command = saveProductCommand('scenario_end', scope, createOperationId());
    try {
      const response = await fetchWithDeadline('/users/assessment/m5/situations/' +
        encodeURIComponent(current.assessment_situation_id) + '/transitions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'scenario_end', reason: 'user_finished_case', request_id: command.operationId }),
      });
      await readApiResponse(response, 'Не удалось завершить основной сценарий.');
    } catch (error) {
      if (!isProductInterviewAnswerCurrent(scope)) return;
      if ([403, 409].includes(Number(error?.status))) clearProductCommand('scenario_end', scope);
      showProductCommandRecovery(scope, [403, 409].includes(Number(error?.status))
        ? 'Сервер отклонил завершение сценария. Обновите состояние ситуации.'
        : 'Ответ о завершении не получен. Итог команды неизвестен; проверьте состояние.');
      return;
    }
    if (!isProductInterviewAnswerCurrent(scope)) return;
    showProductCommandRecovery(scope, 'Проверяем, требуется ли уточнение.', { check: false });
    try {
      snapshot = await waitForProductClarification(snapshot.clarification?.id || null);
      if (!snapshot) return;
    } catch (error) {
      if (isProductInterviewAnswerCurrent(scope)) showProductCommandRecovery(scope,
        error.name === 'ClarificationWaitLimit'
          ? 'Ответ сохранён. Обработка продолжается.'
          : 'Не удалось проверить состояние. Попробуйте ещё раз.');
      return;
    }
  }
  const clarification = snapshot.clarification;
  if (clarification?.status === 'ASK' && !clarification.response_outcome) {
    renderProductRuntime(snapshot);
    return;
  }
  if (snapshot.finish_availability?.allowed !== true) {
    renderProductRuntime(snapshot);
    return;
  }
  const command = saveProductCommand('finish_situation', scope, createOperationId());
  try {
    const finishedResponse = await fetchWithDeadline('/users/assessment/m7/cycles/' +
      encodeURIComponent(scope.cycleId) + '/finish-situation', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idempotency_key: command.operationId }),
    });
    await readApiResponse(finishedResponse, 'Не удалось завершить текущую ситуацию.');
  } catch (error) {
    if (!isProductInterviewAnswerCurrent(scope)) return;
    if ([403, 409].includes(Number(error?.status))) clearProductCommand('finish_situation', scope);
    showProductCommandRecovery(scope, [403, 409].includes(Number(error?.status))
      ? 'Сервер отклонил закрытие ситуации. Проверьте готовность уточнения.'
      : 'Ответ о закрытии не получен. Итог команды неизвестен; проверьте состояние.');
    return;
  }
  if (!isProductInterviewAnswerCurrent(scope)) return;
  try { await loadProductRuntime(); }
  catch (error) {
    if (isProductInterviewAnswerCurrent(scope)) showProductCommandRecovery(scope,
      'Завершение принято, но чтение состояния не удалось. ' + assessmentRuntimeErrorMessage(error));
  }
};

export const toggleProductPause = async () => {
  const scope = productInterviewAnswerScope();
  if (state.productCycleStatus !== 'paused') return;
  const action = 'resume';
  const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/control', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, reason: 'user_' + action, idempotency_key: createOperationId() }),
  });
  await readApiResponse(response, 'Не удалось изменить состояние паузы.');
  if (!isProductInterviewAnswerCurrent(scope)) return;
  await loadProductRuntime();
};

export const createProductAdditionalSession = async () => {
  const scope = productInterviewAnswerScope();
  const current = () => isProductInterviewAnswerCurrent({ ...scope, situationId: state.productAssessmentSituationId });
  const snapshot = await loadProductRuntime();
  if (!snapshot || !current()) return;
  if (snapshot.status?.collection_status !== 'interrupted'
      || !['pending', 'consumed'].includes(snapshot.continuation?.status)) return;
  if (snapshot.continuation?.status === 'pending') {
    const sessionResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/additional-sessions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent_id: snapshot.continuation.intent_id, idempotency_key: createOperationId() }),
    });
    await readApiResponse(sessionResponse, 'Не удалось продолжить сохранённое прохождение.');
    if (!current()) return;
  }
  const nextResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/next', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: createOperationId() }),
  });
  const accepted = await readApiResponse(nextResponse, 'Не удалось открыть следующую ситуацию.');
  if (!current()) return;
  const prepared = accepted.operation_id ? await waitForProductCyclePreparation(accepted) : accepted;
  if (!current()) return;
  if (prepared.decision?.assessment_situation_id && !prepared.presentation) {
    const presentation = await fetchWithDeadline('/users/assessment/m7/cycles/' +
      encodeURIComponent(scope.cycleId) + '/present-next', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assessment_situation_id: prepared.decision.assessment_situation_id,
        expected_plan_revision_id: prepared.plan.revision_id }),
    });
    await readApiResponse(presentation, 'Не удалось открыть следующую ситуацию.');
  }
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

  if (label) {
    const labelNode = document.createElement('div');
    labelNode.className = 'interview-structured-block-label';
    labelNode.textContent = label;
    section.appendChild(labelNode);
  }

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

export const addInterviewMessage = (role, text, speakerLabel = null, { scroll = true } = {}) => {
  const followBottom = scroll && (role === 'user' || isInterviewNearBottom());
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
  if (followBottom) scrollInterviewToBottom();
  else updateInterviewMessagesScrollIndicator();
  return row;
};

export const setInterviewMessageDeliveryState = (row, deliveryState, onRetry = null, rejectionMessage = '') => {
  if (!(row instanceof HTMLElement)) return;
  const delivery = row.querySelector('.interview-message-delivery');
  const status = row.querySelector('.interview-message-delivery-status');
  const retryButton = row.querySelector('.interview-message-retry');
  if (!delivery || !status || !retryButton) return;
  const followBottom = row.isConnected && isInterviewNearBottom();

  row.classList.toggle('delivery-pending', deliveryState === 'pending');
  row.classList.toggle('delivery-failed', ['failed', 'rejected'].includes(deliveryState));
  retryButton.onclick = null;

  if (deliveryState === 'pending') {
    delivery.hidden = false;
    status.textContent = 'Отправляем...';
    retryButton.hidden = true;
  } else if (deliveryState === 'failed') {
    delivery.hidden = false;
    status.textContent = 'Не отправлено';
    retryButton.hidden = false;
    retryButton.textContent = 'Повторить';
    retryButton.onclick = () => onRetry?.();
  } else if (deliveryState === 'rejected') {
    delivery.hidden = false;
    status.textContent = rejectionMessage || 'Сервер отклонил ответ. Проверьте состояние ситуации.';
    retryButton.textContent = 'Проверить состояние';
    retryButton.hidden = !onRetry;
    retryButton.onclick = () => onRetry?.();
  } else if (['unknown', 'accepted', 'saved'].includes(deliveryState)) {
    delivery.hidden = false;
    status.textContent = deliveryState === 'accepted' ? 'Ответ принят. Обновляем историю.'
      : deliveryState === 'saved' ? 'Ответ сохранён. Проверяем обработку.'
        : 'Исход отправки неизвестен. Проверим сохранение перед повтором.';
    retryButton.textContent = deliveryState === 'accepted' ? 'Обновить историю' : 'Проверить и повторить';
    retryButton.hidden = !onRetry;
    retryButton.onclick = () => onRetry?.();
  } else {
    delivery.hidden = true;
    status.textContent = '';
    retryButton.hidden = true;
  }
  if (followBottom) scrollInterviewToBottom();
  else updateInterviewMessagesScrollIndicator();
};

const isInterviewNearBottom = () => !interviewScrollArea
  || interviewScrollArea.scrollHeight - interviewScrollArea.scrollTop - interviewScrollArea.clientHeight <= 24;

const cancelInterviewScrollAlignment = () => {
  interviewScrollAlignmentGeneration += 1;
  if (interviewScrollAlignmentFrame !== null) window.cancelAnimationFrame?.(interviewScrollAlignmentFrame);
  interviewScrollAlignmentFrame = null;
  interviewScrollAlignmentTimers.forEach((timer) => window.clearTimeout(timer));
  interviewScrollAlignmentTimers = [];
};

const setInterviewScrollTop = (top) => {
  if (interviewScrollArea) {
    // Restoring a reading position must not inherit CSS smooth scrolling.
    interviewScrollArea.scrollTo({ top, behavior: 'instant' });
  }
  updateInterviewMessagesScrollIndicator();
};

const scrollInterviewToBottom = () => {
  cancelInterviewScrollAlignment();
  setInterviewScrollTop(interviewScrollArea?.scrollHeight || 0);
};

const scheduleInterviewScrollAlignment = ({ top = 0, followBottom = false } = {}) => {
  cancelInterviewScrollAlignment();
  if (!interviewScrollArea) return;
  const generation = interviewScrollAlignmentGeneration;
  const node = interviewMessages.firstChild;
  const scope = JSON.stringify([state.currentScreen, state.productCycleId, state.activeInterviewCaseKey]);
  let expectedTop = interviewScrollArea.scrollTop;
  const current = () => generation === interviewScrollAlignmentGeneration
    && node === interviewMessages.firstChild
    && scope === JSON.stringify([state.currentScreen, state.productCycleId, state.activeInterviewCaseKey]);
  const align = () => {
    if (!current()) return;
    // A participant can scroll between a render and its layout callbacks.
    if (Math.abs(interviewScrollArea.scrollTop - expectedTop) > 1) {
      cancelInterviewScrollAlignment();
      return;
    }
    setInterviewScrollTop(followBottom ? interviewScrollArea.scrollHeight : top);
    expectedTop = interviewScrollArea.scrollTop;
  };
  align();
  if (typeof window.requestAnimationFrame === 'function') {
    interviewScrollAlignmentFrame = window.requestAnimationFrame(() => {
      interviewScrollAlignmentFrame = null;
      align();
    });
  }
  interviewScrollAlignmentTimers = [window.setTimeout(align, 80), window.setTimeout(align, 220)];
};

const scheduleInterviewBottomAlignment = () => scheduleInterviewScrollAlignment({ followBottom: true });

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
  const target = compact && !isCycleAssessment() ? interviewTitleRow : interviewCaseHeading;
  const timer = interviewTimerBadge.closest?.('.interview-timer') || interviewTimerBadge;
  if (timer.parentElement !== target) {
    target.appendChild(timer);
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
  const cycle = isCycleAssessment();
  const total = state.assessmentTotalCases;
  const position = state.assessmentCaseNumber;
  const knownTotal = Number.isInteger(total) && total > 0;
  const knownPosition = Number.isInteger(position) && position > 0 && (!knownTotal || position <= total);
  const workspace = interviewPanel.classList.contains('product-answer-screen');
  const assessmentHeader = workspace || interviewPanel.classList.contains('return-required');
  const target = interviewPanel.querySelector?.(assessmentHeader ? '.interview-title-row' : '.interview-case-heading');
  if (target && interviewCaseBadge.parentElement !== target) {
    if (assessmentHeader) target.append(interviewCaseBadge);
    else target.prepend(interviewCaseBadge);
  }
  const format = interviewPanel.querySelector?.('.interview-response-format');
  if (format && !workspace) format.hidden = true;
  const caption = interviewPanel.querySelector?.('.interview-timer-caption');
  if (caption && !workspace) caption.textContent = 'Осталось на ответы';
  interviewCaseBadge.textContent = cycle
    ? knownPosition && knownTotal ? `Ситуация ${position} из ${total}`
      : knownTotal ? `Всего ситуаций: ${total}` : 'Прогресс уточняется'
    : 'Ситуация ' + position + ' из ' + total;
  interviewCaseTitle.textContent = state.assessmentCaseTitle || 'Оценочная ситуация';
  interviewCaseStatus.textContent = '';

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
  if (isCycleAssessment()) {
    const seconds = serverRemainingSeconds(state.assessmentRemainingSeconds);
    return seconds === null ? null : seconds * 1000;
  }
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
  const prefix = interviewTimerBadge.classList.contains('is-paused')
    && !['between-situations', 'return-required'].some((name) => interviewPanel.classList.contains(name)) ? 'Пауза · ' : '';
  if (remainingMs === null) {
    interviewTimerBadge.textContent = isCycleAssessment() ? 'Время недоступно' : 'Остаток времени выполнения уточняется';
    interviewTimerBadge.title = 'Не удалось получить актуальный остаток времени.';
    interviewTimerBadge.classList.remove('is-low-time');
    return false;
  }

  interviewTimerBadge.title = '';
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
      void submitAssessmentMessage('__auto_finish_case__').catch(showInterviewRuntimeError);
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
        void submitAssessmentMessage('__timeout__').catch(showInterviewRuntimeError);
      }
    }, 1000);
  } else if (!state.assessmentTimeoutInFlight) {
    state.assessmentTimeoutInFlight = true;
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    void submitAssessmentMessage('__timeout__').catch(showInterviewRuntimeError);
  }
};

const submitAssessmentMessage = async (text, requestIdentity = null) => {
  if (isCycleAssessment()) {
    if (text === '__timeout__') {
      await loadProductRuntime();
      return;
    }
    const operation = requestIdentity?.cycleId ? requestIdentity
      : prepareProductInterviewAnswer(text, interviewTextarea.value);
    const runtimeUrl = '/users/assessment/cycles/' + encodeURIComponent(operation.cycleId) + '/runtime';
    let outcome = null;
    if (operation.status !== 'prepared') {
      outcome = await readProductInterviewAnswerStatus(operation);
      if (!isProductInterviewAnswerCurrent(operation)) return { stale: true };
      if (productInterviewAnswerResolved(operation, outcome, confirmedProductInterviewSnapshot)) {
        applyProductInterviewAnswerStatus(operation, outcome, confirmedProductInterviewSnapshot);
        operation.accepted = true;
        operation.status = 'accepted';
        // Receipt readback remains conclusive when a later runtime/return GET
        // is unavailable. It does not grant permission to write in that state.
        await loadProductRuntime();
        return { accepted: true, verified: true };
      }
    }
    // Readback always precedes a retry. A failed GET never means the Turn is absent.
    const runtimeResponse = await fetchWithDeadline(runtimeUrl, { credentials: 'same-origin' });
    const snapshot = await readApiResponse(runtimeResponse, 'Не удалось восстановить состояние оценки.');
    if (!isProductInterviewPresentationCurrent(operation)) return { stale: true, accepted: operation.accepted };
    if (!productInterviewSnapshotMatches(snapshot, operation)) {
      throw new Error('Ситуация изменилась. Ответ остаётся связан с исходной ситуацией.');
    }
    if (outcome) {
      applyProductInterviewAnswerStatus(operation, outcome, snapshot);
      if (productInterviewAnswerResolved(operation, outcome, snapshot)) {
        renderProductRuntime(snapshot);
        return { accepted: true, verified: true };
      }
      if (!readProductInterviewAnswer(operation)) { renderProductRuntime(snapshot); return { blocked: true }; }
    }
    renderProductRuntime(snapshot);
    const saved = (snapshot.trace?.turns || []).some((turn) => turn.turn_id === operation.turnId
      && turn.speaker_type === 'assessee' && turn.content_text === operation.text);
    if (saved && (operation.accepted || operation.clarificationId
        || operation.sourcePhase !== productInterviewSourcePhase(snapshot))) {
      return { accepted: true, verified: true };
    }
    if (operation.accepted) return { accepted: true, pending: !saved };
    if (!confirmedProductInterviewCanSend || operation.sourcePhase !== productInterviewSourcePhase(snapshot)) {
      if (operation.status === 'prepared') productAnswerStorage().removeItem(productInterviewAnswerKey(operation));
      return { accepted: saved, pending: operation.status !== 'prepared', blocked: true };
    }
    const expectedEndpoint = operation.clarificationId
      ? '/users/assessment/m7/clarifications/' + encodeURIComponent(operation.clarificationId) + '/answers'
      : '/users/assessment/m5/situations/' + encodeURIComponent(operation.situationId) + '/turns';
    if (operation.endpoint !== expectedEndpoint || text !== operation.text) throw new Error('Операция отправки изменилась.');
    const body = {
      request_id: operation.requestId, turn_id: operation.turnId, content: operation.text,
    };
    operation.lastPostFresh = operation.status === 'prepared' && Number(operation.attemptCount || 0) === 0;
    operation.attemptCount = Number(operation.attemptCount || 0) + 1;
    operation.status = 'unknown';
    operation.absenceChecked = false;
    saveProductInterviewAnswer(operation);
    const response = await fetchWithDeadline(operation.endpoint, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    let receipt;
    try { receipt = await readApiResponse(response, 'Не удалось сохранить ответ.'); }
    catch (error) {
      if ([403, 409].includes(Number(error?.status))) error.productTurnPostRejected = true;
      throw error;
    }
    operation.accepted = productInterviewReceiptAccepted(receipt, operation);
    operation.status = operation.accepted ? 'accepted' : 'unknown';
    saveProductInterviewAnswer(operation);
    if (operation.accepted) {
      rememberProductInterviewReceipt(operation);
      clearInterviewDraft(operation);
      if (isProductInterviewPresentationCurrent(operation)) {
        renderProductRuntime(confirmedProductInterviewSnapshot, { fresh: false });
      }
    }
    if (!isProductInterviewPresentationCurrent(operation)) return { accepted: operation.accepted, stale: true };
    const readbackResponse = await fetchWithDeadline(runtimeUrl, { credentials: 'same-origin' });
    const readback = await readApiResponse(readbackResponse, 'Ответ принят, но историю пока не удалось обновить.');
    if (!isProductInterviewPresentationCurrent(operation)) return { accepted: operation.accepted, stale: true };
    if (!productInterviewSnapshotMatches(readback, operation)) return { accepted: operation.accepted, pending: true };
    renderProductRuntime(readback);
    const verified = (readback.trace?.turns || []).some((turn) => turn.turn_id === operation.turnId
      && turn.speaker_type === 'assessee' && turn.content_text === operation.text);
    return { accepted: operation.accepted || verified, verified, pending: !operation.accepted || !verified };
  }
  const ownerId = state.pendingUser?.id, epoch = state.identityEpoch;
  const screen = state.currentScreen, sessionCode = state.assessmentSessionCode;
  const cycleId = state.productCycleId, situationId = state.productAssessmentSituationId;
  const viewGeneration = getAssessmentViewGeneration();
  const current = () => state.pendingUser?.id === ownerId && state.identityEpoch === epoch
    && state.currentScreen === screen && state.assessmentSessionCode === sessionCode
    && state.productCycleId === cycleId && state.productAssessmentSituationId === situationId
    && viewGeneration === getAssessmentViewGeneration();
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
    if (!current()) return { stale: true };
    handleAssessmentResponse(data);
    stopAssessmentTransitionLoader();
  } catch (error) {
    if (!current()) return { stale: true };
    stopAssessmentTransitionLoader();
    throw error;
  }
};

export const resumeProductRuntimePolling = () => {
  clearInterviewTimer();
  state.assessmentTimerId = window.setInterval(() => {
    if (interviewMessages.querySelector('.interview-return-card[data-return-pending]')) return;
    if (!document.hidden && !interviewPanel.classList.contains('hidden') && productRuntimePollAllowed()) {
      void loadProductRuntime({ generation: productRuntimePollGeneration }).catch(showInterviewRuntimeError);
    } else if (!document.hidden && !interviewPanel.classList.contains('hidden')
        && productProcessingPending(confirmedProductInterviewSnapshot)
        && !productProcessingFailed(confirmedProductInterviewSnapshot)
        && Date.now() >= productProcessingBudget(confirmedProductInterviewSnapshot)) {
      // The existing deadline stops network polling. Refresh its copy once;
      // it does not start another request or imply a failed/stuck operation.
      const deadline = String(productProcessingBudget(confirmedProductInterviewSnapshot));
      if (interviewError.dataset.waitDeadline !== deadline) {
        renderProductInterviewNotice(confirmedProductInterviewSnapshot);
        interviewError.dataset.waitDeadline = deadline;
      }
    }
  }, PRODUCT_RUNTIME_POLL_MS);
};

export const openInterview = () => {
  advanceAssessmentViewGeneration();
  state.newUserSequenceStep = 'interview';
  setCurrentScreen('interview');
  persistAssessmentContext();
  syncUrlState('interview');
  hideAllPanels();
  interviewPanel.classList.remove('completed', 'between-situations', 'return-required');
  interviewMessages.querySelector('.interview-return-card[data-return-key]')?.remove();
  interviewCompleteActions.classList.add('hidden');
  interviewPanel.classList.remove('hidden');
  if (isCycleAssessment()) {
    state.assessmentCaseNumber = null;
    state.assessmentTotalCases = null;
    state.assessmentCompletedCases = null;
    renderInterviewMeta();
    renderCaseProgress(false);
    clearUnconfirmedProductTime();
    // The visible entry screen has no confirmed actionability until runtime is presented.
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    resumeProductRuntimePolling();
    void loadProductRuntime().catch(showInterviewRuntimeError);
  }
};

const startAssessmentInterview = async ({ preparedCycleId = null } = {}) => {
  if (!state.pendingUser || !state.pendingUser.id) {
    showError(prechatError, 'Не удалось определить пользователя для старта ассессмента.');
    return;
  }
  const ownerId = state.pendingUser.id, epoch = state.identityEpoch, screen = state.currentScreen;
  const generation = ++assessmentStartGeneration;
  const viewGeneration = getAssessmentViewGeneration();
  let cycleId = state.productCycleId;
  const current = () => state.pendingUser?.id === ownerId && state.identityEpoch === epoch
    && state.currentScreen === screen && state.productCycleId === cycleId && generation === assessmentStartGeneration
    && viewGeneration === getAssessmentViewGeneration();

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
    state.productCycleId = preparedCycleId;
    cycleId = state.productCycleId;
    if (!state.productCycleId) {
      const prepared = await prepareProductCycle({
        personalized_profile_id: state.dashboard?.personalized_profile_id || null,
        idempotency_key: createOperationId(), selected_skills: ['K1', 'K2', 'K3', 'K4'],
      });
      if (!current()) return;
      state.productCycleId = prepared.plan.cycle_id;
      cycleId = state.productCycleId;
    }
    state.assessmentRuntimeKind = 'cycle';
    persistAssessmentContext();
    const started = await startPreparedProductCycle(state.productCycleId);
    if (!current()) return;
    state.assessmentRuntimeKind = 'cycle';
    state.productCycleId = started.plan.cycle_id;
    state.assessmentSessionCode = null;
    state.assessmentSessionId = null;
    state.preparedAssessmentStartResponse = null;
    if (['collection_closed', 'calculation_pending'].includes(started.runtime?.status?.collection_status)) {
      openProcessing({ confirmedCollection: started.runtime.status });
      return;
    }
    openInterview();
    renderProductRuntime(started.runtime);
  } catch (error) {
    if (!current()) return;
    if (preparedCycleId) throw error; // The acquaintance screen owns retry; never open legacy profile/library.
    if (shouldRecoverProfileOnAssessmentError(error.message)) {
      await recoverProfileCompletionForAssessment();
      return;
    }
    state.assessmentPreparationStatus = 'failed';
    state.assessmentPreparationProgressPercent = 0;
    state.assessmentPreparationTitle = 'Не удалось подготовить кейсы';
    state.assessmentPreparationMessage = assessmentRuntimeErrorMessage(error);
    renderAssessmentPreparationState();
    showError(prechatError, assessmentRuntimeErrorMessage(error));
  }
};

let assessmentEntryPending = null;
export const handleAssessmentEntryClick = async () => {
  if (assessmentEntryPending || !state.pendingUser?.id) return;
  const owner = state.pendingUser.id, epoch = state.identityEpoch;
  const current = () => state.pendingUser?.id === owner && state.identityEpoch === epoch;
  const buttons = ['assessment-action-button', 'start-first-assessment', 'library-start-button']
    .map((id) => document.getElementById(id)).filter(Boolean);
  const disabled = buttons.map((button) => button.disabled);
  const operation = { buttons, disabled };
  assessmentEntryPending = operation;
  buttons.forEach((button) => { button.disabled = true; });
  document.getElementById('assessment-entry-error')?.remove();
  try {
    const { loadUserJourneyState } = await import('../session.js');
    if (!current()) return;
    const journey = await loadUserJourneyState({ allowAdmin: true });
    if (!current()) return;
    if (!journey?.next_action) throw new Error('Не удалось определить текущий этап оценки. Повторите действие.');
    applyJourneyAssessmentContext(journey);
    if (journey.next_action === 'show_onboarding') {
      const { openOnboardingScreen } = await import('../screen-loaders.js');
      if (current()) await openOnboardingScreen({ currentStep: Number(journey.onboarding?.current_step || 0) });
    } else if (journey.next_action === 'wait_for_acquaintance_data') {
      openAcquaintanceWaiting(journey.acquaintance?.readiness);
    } else if (journey.next_action === 'complete_profile') {
      await recoverProfileCompletionForAssessment({ resumeAssessment: false });
    } else if (journey.next_action === 'resume_assessment' && state.productCycleId) {
      openInterview();
    } else if (['show_processing', 'show_assessment_error'].includes(journey.next_action)) {
      openProcessing();
    } else if (['show_dashboard', 'resume_assessment'].includes(journey.next_action)) {
      openPrechat(); // Only a server-authorized historical route, not a failed lookup fallback.
    } else throw new Error('Текущий этап недоступен. Обновите страницу и повторите действие.');
  } catch (error) {
    if (!current()) return;
    const anchor = buttons.find((button) => button.getClientRects().length);
    if (anchor) {
      const message = document.createElement('p'); message.id = 'assessment-entry-error';
      message.className = 'error'; message.setAttribute('role', 'alert');
      message.textContent = assessmentRuntimeErrorMessage(error);
      anchor.insertAdjacentElement('afterend', message);
    }
  } finally {
    if (assessmentEntryPending === operation) assessmentEntryPending = null;
    if (current()) buttons.forEach((button, index) => { button.disabled = disabled[index]; });
  }
};

export const initInterview = () => {
  window.addEventListener('agent4k:assessment-context-cleared', () => {
    cancelInterviewScrollAlignment();
    const pending = assessmentEntryPending;
    assessmentEntryPending = null;
    pending?.buttons.forEach((button, index) => { button.disabled = pending.disabled[index]; });
    document.getElementById('assessment-entry-error')?.remove();
  });
  const draftStatus = document.getElementById?.('interview-draft-status');
  const draftActions = document.getElementById?.('interview-draft-actions');
  if (draftStatus && draftActions) {
    durableDraft = createAnswerDrafts({ input: interviewTextarea, status: draftStatus, actions: draftActions,
      onConflictChange: (blocked) => {
        interviewSubmitButton.disabled = blocked || interviewTextarea.disabled || !confirmedProductInterviewCanSend
          || Boolean(readProductInterviewAnswer());
        const prompt = interviewPanel.querySelector('.interview-your-turn');
        if (prompt) prompt.hidden = interviewSubmitButton.disabled;
      },
      storage: { getItem: (key) => window.localStorage.getItem(key), setItem: (key, value) => window.localStorage.setItem(key, value),
        removeItem: (key) => window.localStorage.removeItem(key), keys: () => Object.keys(window.localStorage) },
      current: (scope) => isProductInterviewAnswerCurrent({ ...scope, viewGeneration: getAssessmentViewGeneration() }),
      request: async (scope, draftWriteData) => {
        const response = await fetchWithDeadline('/users/assessment/m5/situations/' + encodeURIComponent(scope.situationId) + (draftWriteData?.accepted ? '/draft/accepted' : '/draft'), {
          method: draftWriteData?.accepted ? 'POST' : draftWriteData ? 'PUT' : 'GET', credentials: 'same-origin', cache: 'no-store',
          ...(draftWriteData ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draftWriteData) } : {}),
        });
        return readApiResponse(response, 'Не удалось сохранить черновик.');
      }, newRevision: createOperationId });
    window.addEventListener('online', () => durableDraft.retry());
    window.addEventListener('focus', () => durableDraft.retry());
    window.addEventListener('agent4k:before-logout', (event) => {
      if (event.detail.ownerId === String(state.pendingUser?.id || '')) event.detail.unsynced = durableDraft.unsynced();
    });
    window.addEventListener('storage', (event) => durableDraft.storageChanged(event));
    window.addEventListener('agent4k:assessment-context-cleared', () => durableDraft.stop());
    window.addEventListener('pagehide', () => { void durableDraft.flush(); });
  }
  disableTextareaAssistFeatures(interviewTextarea);
  interviewTextarea.addEventListener('input', () => {
    if (durableDraft) { durableDraft.edit(); return; }
    const key = interviewDraftKey();
    if (!key) return;
    activeInterviewDraftKey = interviewDraftSignature();
    // A revision is confirmed only after both the value and its scoped context
    // were written. A quota/privacy failure must not promise a saved draft.
    interviewTextarea.dataset.draftRevision = '';
    try {
      if (interviewTextarea.value) {
        const revision = createOperationId();
        window.sessionStorage.setItem(key, interviewTextarea.value);
        window.sessionStorage.setItem(key + ':context', JSON.stringify({
          ownerId: String(state.pendingUser?.id || ''), clarificationId: interviewDraftScope().clarificationId, revision,
        }));
        interviewTextarea.dataset.draftRevision = revision;
      } else {
        window.sessionStorage.removeItem(key);
        window.sessionStorage.removeItem(key + ':context');
      }
    } catch (_error) {
      showInterviewRuntimeError(new Error('Не удалось сохранить текущий текст в браузере. Оставьте страницу открытой и проверьте соединение перед отправкой.'));
    }
  });
  const viewport = window.visualViewport;
  if (viewport) {
    const fitViewport = () => {
      const shell = interviewPanel.closest('.shell');
      if (viewport.scale === 1 && Math.abs(viewport.height - window.innerHeight) > 1) {
        shell?.style.setProperty('--interview-viewport-height', viewport.height + 'px');
      } else shell?.style.removeProperty('--interview-viewport-height');
    };
    viewport.addEventListener('resize', fitViewport);
    fitViewport();
  }
  placeInterviewTimerBadge();
  interviewCompactQuery?.addEventListener('change', placeInterviewTimerBadge);

  if (interviewMessagesScroll && interviewScrollArea) {
    interviewMessagesScroll.addEventListener('click', () => {
      cancelInterviewScrollAlignment();
      interviewScrollArea.scrollTo({ top: interviewScrollArea.scrollHeight, behavior: 'smooth' });
    });
  }

  if (interviewScrollArea) {
    ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach((eventName) => {
      interviewScrollArea.addEventListener(eventName, cancelInterviewScrollAlignment, { passive: true });
    });
    interviewTextarea.addEventListener('focus', cancelInterviewScrollAlignment);
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
      void loadProductRuntime().catch(showInterviewRuntimeError);
    }
  });

  registerLeaveInterviewCleanup(() => {
    interviewPanel.classList.remove('product-answer-screen');
    interviewTextarea.readOnly = false;
    advanceAssessmentViewGeneration();
    cancelInterviewScrollAlignment();
    clearInterviewTimer();
    stopProductPresence();
    void pauseAssessmentTimerIfNeeded();
  });
};

export { startAssessmentInterview, submitAssessmentMessage, updateInterviewTimer };
