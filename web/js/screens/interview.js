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
import { createOperationId, readApiResponse } from '../api.js';
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
  const pending = readProductInterviewAnswer()
    || productInterviewRequests.get(productInterviewRequestKey(productInterviewAnswerScope()));
  if (pending && pending.status !== 'saved') {
    interviewSubmitButton.disabled = true;
    interviewFinishButton.disabled = true;
    showError(interviewError, pending.accepted
      ? 'Ответ принят. Не удалось обновить историю; проверьте её кнопкой в сообщении.'
      : 'Пока не удалось подтвердить исход отправки. Проверьте сохранение кнопкой в сообщении.');
    return;
  }
  showError(interviewError, assessmentRuntimeErrorMessage(error, { draftSaved: isCurrentInterviewDraftSaved() }));
};

export const restoreInterviewActionControls = () => {
  if (confirmedProductInterviewSnapshot?.cycle_id === state.productCycleId
      && confirmedProductInterviewSnapshot?.current_situation?.assessment_situation_id === state.productAssessmentSituationId) {
    renderProductRuntime(confirmedProductInterviewSnapshot);
  }
};

const restoreInterviewDraft = () => {
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
    const raw = window.sessionStorage.getItem(productInterviewAnswerKey(scope));
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
        || !['prepared', 'unknown', 'accepted', 'saved'].includes(value.status)
        || typeof value.accepted !== 'boolean'
        || (value.clarificationId !== null && (typeof value.clarificationId !== 'string' || !uuid.test(value.clarificationId)))
        || value.endpoint !== expectedEndpoint || typeof value.sourcePhase !== 'string') return null;
    const phase = JSON.parse(value.sourcePhase);
    if (!Array.isArray(phase) || phase.length !== 5 || phase.some((part) => part !== null && typeof part !== 'string')) return null;
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
  window.sessionStorage.setItem(productInterviewAnswerKey(operation), JSON.stringify(saved));
  productInterviewPendingAnswers.set(productInterviewRequestKey(operation), { ...operation });
};

const productInterviewSourcePhase = (snapshot) => JSON.stringify([
  snapshot.current_situation?.status, snapshot.clarification?.id || null,
  snapshot.clarification?.status || null, snapshot.clarification?.response_outcome || null,
  snapshot.clarification?.question_turn_id || null,
]);

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
  const response = await fetch('/users/assessment/m5/situations/' + encodeURIComponent(operation.situationId)
    + '/answer-status?' + params, { credentials: 'same-origin', cache: 'no-store' });
  const value = await readApiResponse(response, 'Исход отправки пока не подтверждён.');
  if (value.cycle_id !== operation.cycleId || value.assessment_situation_id !== operation.situationId
      || value.request_id !== operation.requestId || value.turn_id !== operation.turnId
      || value.clarification_id !== operation.clarificationId || !['absent', 'accepted'].includes(value.status)) {
    throw new Error('Сервер не подтвердил идентичность исходной отправки.');
  }
  if (value.status === 'accepted' && (value.turn?.turn_id !== operation.turnId
      || value.turn.request_id !== operation.requestId || value.turn.content_text !== operation.text
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
    clearInterviewDraft(operation);
    const completed = productInterviewAnswerResolved(operation, value, snapshot);
    if (completed) {
      window.sessionStorage.removeItem(productInterviewAnswerKey(operation));
      return true;
    }
    const changed = pending.status !== 'saved';
    saveProductInterviewAnswer({ ...pending, status: 'saved' });
    return changed;
  }
  // An absent receipt is not a rejected write. Only a changed source phase can
  // retire its active slot; the original identity/endpoint remains in session.
  if (!pending.accepted && operation.sourcePhase !== productInterviewSourcePhase(snapshot)) {
    window.sessionStorage.setItem(productInterviewAnswerKey(operation) + ':resolved:' + operation.requestId,
      JSON.stringify({ ...pending, status: 'superseded', resolution: 'absent_in_previous_phase' }));
    window.sessionStorage.removeItem(productInterviewAnswerKey(operation));
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
  void reading.then((value) => {
    if (!isProductInterviewPresentationCurrent(operation)) return;
    const changed = applyProductInterviewAnswerStatus(operation, value, snapshot);
    if (changed && value.status === 'accepted') showError(interviewError, '');
    if (changed && productInterviewSnapshotMatches(confirmedProductInterviewSnapshot, operation)) {
      renderProductRuntime(confirmedProductInterviewSnapshot);
    }
  }).catch(() => { /* A failed readback keeps the original unknown operation. */ })
    .finally(() => { if (productInterviewReadbacks.get(key) === reading) productInterviewReadbacks.delete(key); });
};

const recoverPreviousProductInterviewAnswers = (snapshot, { completedOnly = false } = {}) => {
  const ownerId = String(state.pendingUser?.id || '');
  const prefix = `agent4k.assessmentPending:${snapshot.cycle_id}:`;
  Object.keys(window.sessionStorage).filter((key) => key.startsWith(prefix) && key.endsWith(':' + ownerId))
    .forEach((key) => {
      let saved;
      try { saved = JSON.parse(window.sessionStorage.getItem(key)); } catch (_error) { return; }
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
  if (operation.status === 'prepared' && !productInterviewRequests.has(productInterviewRequestKey(operation))) {
    window.sessionStorage.removeItem(productInterviewAnswerKey(operation));
    return null;
  }
  const saved = (snapshot.trace?.turns || []).some((turn) => turn.turn_id === operation.turnId
    && turn.speaker_type === 'assessee' && turn.content_text === operation.text);
  if (!saved) return operation;
  clearInterviewDraft(operation);
  // M5 commits the participant Turn before provider processing. Keep a lost
  // receipt recoverable with the same identity while its source phase remains.
  if (operation.accepted) {
    window.sessionStorage.removeItem(productInterviewAnswerKey(operation));
    return null;
  }
  operation.status = 'saved';
  saveProductInterviewAnswer(operation);
  return operation;
};

const renderProductInterviewAnswerDelivery = (snapshot, canSend) => {
  const operation = reconcileProductInterviewAnswer(snapshot);
  const localRows = [...interviewMessages.children].filter((row) => row.dataset.pendingTurnId);
  localRows.filter((row) => row.dataset.pendingTurnId !== operation?.turnId).forEach((row) => row.remove());
  [...interviewMessages.children].filter((row) => row.dataset.deliveryRequestId
    && row.dataset.deliveryRequestId !== operation?.requestId).forEach((row) => {
    setInterviewMessageDeliveryState(row, 'sent');
    delete row.dataset.deliveryRequestId;
  });
  if (!operation) return;
  const busy = productInterviewRequests.has(productInterviewRequestKey(operation));
  if (!busy) recoverProductInterviewAnswer(operation, snapshot);
  const savedRow = [...interviewMessages.children].find((row) => row.dataset.turnId === operation.turnId
    && !row.dataset.pendingTurnId);
  let row = savedRow || localRows.find((item) => item.dataset.pendingTurnId === operation.turnId);
  if (!row) {
    row = addInterviewMessage('user', operation.text, null, { scroll: false });
    row.dataset.pendingTurnId = operation.turnId;
  }
  if (savedRow) localRows.forEach((item) => item.remove());
  row.dataset.deliveryRequestId = operation.requestId;
  const retry = canSend && !busy ? () => {
    const pending = readProductInterviewAnswer(operation);
    if (isProductInterviewPresentationCurrent(operation) && pending?.requestId === operation.requestId
        && pending.turnId === operation.turnId) {
      void sendProductInterviewAnswer(operation.text, { scope: operation, draftValue: operation.draftValue });
    }
  } : null;
  const delivery = operation.status === 'saved' ? 'saved'
    : operation.accepted ? 'accepted' : busy ? 'pending' : 'unknown';
  setInterviewMessageDeliveryState(row, delivery, retry);
  if (busy) interviewTextarea.disabled = true;
  interviewSubmitButton.disabled = true;
  // A confirmed saved Turn may use the already permitted separate finish action.
  if (operation.status !== 'saved') interviewFinishButton.disabled = true;
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
  let existing = readProductInterviewAnswer(scope);
  if (existing?.status === 'prepared' && existing.text !== text) {
    window.sessionStorage.removeItem(productInterviewAnswerKey(existing));
    existing = null;
  }
  if (existing) {
    if (existing.text !== text) throw new Error('Сначала проверьте сохранение предыдущего ответа кнопкой в сообщении.');
    return existing;
  }
  if (window.sessionStorage.getItem(productInterviewAnswerKey(scope))) {
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
    draftRevision, requestId: createOperationId(), turnId: createProductInterviewTurnId(),
    clarificationId: isClarification ? clarification.id : null,
    sourcePhase: productInterviewSourcePhase(snapshot), status: 'prepared', accepted: false,
    endpoint: isClarification
      ? '/users/assessment/m7/clarifications/' + encodeURIComponent(clarification.id) + '/answers'
      : '/users/assessment/m5/situations/' + encodeURIComponent(scope.situationId) + '/turns' };
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
  productInterviewRequests.set(key, operation);
  if (isProductInterviewPresentationCurrent(operation)) {
    showError(interviewError, '');
    renderProductRuntime(confirmedProductInterviewSnapshot);
  }
  try {
    return await submitAssessmentMessage(text, operation);
  } catch (error) {
    if (isProductInterviewPresentationCurrent(operation)) {
      showError(interviewError, operation.status === 'prepared'
        ? assessmentRuntimeErrorMessage(error, { draftSaved: isCurrentInterviewDraftSaved() }) : operation.accepted
        ? 'Ответ принят. Не удалось обновить историю; проверьте её кнопкой в сообщении.'
        : 'Пока не удалось подтвердить исход отправки. Проверьте сохранение кнопкой в сообщении.');
    }
    return { accepted: operation.accepted, pending: operation.status !== 'prepared', error };
  } finally {
    if (productInterviewRequests.get(key) === operation) productInterviewRequests.delete(key);
    if (operation.status === 'prepared') {
      const pending = readProductInterviewAnswer(operation);
      if (pending?.requestId === operation.requestId) window.sessionStorage.removeItem(productInterviewAnswerKey(operation));
    }
    if (isProductInterviewPresentationCurrent(operation)) {
      // Existing runtime projection restores phase-owned controls, then the
      // delivery hook applies only its own unresolved-operation UI lock.
      if (productInterviewSnapshotMatches(confirmedProductInterviewSnapshot, operation)) {
        renderProductRuntime(confirmedProductInterviewSnapshot);
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

const returnContinueIdentity = (value) => [
  state.pendingUser?.id, value.cycle_id, value.position_no,
  value.current_assessment_situation_id, value.current_assessment_situation_status,
];

const pendingReturnContinue = (value) => {
  let saved = null;
  try { saved = JSON.parse(window.sessionStorage.getItem(RETURN_CONTINUE_PENDING_KEY) || 'null'); } catch { /* stale storage */ }
  const identity = returnContinueIdentity(value);
  if (saved?.identity && JSON.stringify(saved.identity) === JSON.stringify(identity) && saved.key) return saved;
  saved = { identity, key: createOperationId(), generationKey: createOperationId(), generationOperationId: null };
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

const renderProductRuntime = (snapshot) => {
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
  const completedPositions = routePositions.filter((position) => position.state === 'completed').length;
  state.assessmentRuntimeKind = 'cycle';
  state.productCycleId = snapshot.cycle_id;
  state.productAssessmentSituationId = current?.assessment_situation_id || null;
  state.productClarificationDecisionId = snapshot.clarification?.id || null;
  state.productCycleStatus = snapshot.status?.collection_status || null;
  state.assessmentRemainingSeconds = serverRemainingSeconds(snapshot.status?.remaining_seconds);
  state.assessmentCaseNumber = Math.max(1, Number(currentPosition?.position_no || completedPositions + 1));
  state.assessmentTotalCases = Math.max(state.assessmentCaseNumber,
    Number(snapshot.route?.progress?.total_positions || routePositions.length || 1));
  state.assessmentCaseTitle = current?.participant_payload?.title || current?.participant_payload?.case_title || 'Оценочная ситуация';
  state.activeInterviewCaseKey = current?.assessment_situation_id || null;
  persistAssessmentContext();
  confirmedProductInterviewSnapshot = snapshot;
  restoreInterviewDraft();
  recoverPreviousProductInterviewAnswers(snapshot);

  const initialMaterials = current?.participant_payload?.initial_materials;
  const initialMaterialTextById = new Map((Array.isArray(initialMaterials) ? initialMaterials : [])
    .map((material) => [material?.material_id, payloadItems({ materials: [material] }, ['materials'])[0]])
    .filter(([id, text]) => id && text));
  const dialogue = [
    ...(snapshot.trace?.turns || []).map((item) => ({...item, text:item.content_text,
      role:item.speaker_type === 'assessee' ? 'user' : 'assistant'})),
    ...(snapshot.trace?.events || []).map((event) => ({...event, text:productEventText(event), role:'assistant'}))
      // The start message already contains initial materials. Preserve later
      // content changes and mandatory updates, even when they reuse an ID.
      .filter((event) => event.event_type !== 'material_disclosed'
        || event.text !== initialMaterialTextById.get(event.material_id)),
  ].sort((a, b) => a.sequence_no - b.sequence_no);
  const clarification = snapshot.clarification;
  // Polling the same saved AS must not collapse/recreate its long DOM and move
  // the document back to the message while the participant reads or uses controls.
  // Include only rendered content; status, time and actionability still refresh.
  const messageKey = JSON.stringify([snapshot.cycle_id, current?.assessment_situation_id,
    current?.participant_payload, dialogue, clarification]);
  const messagesChanged = renderedProductMessages?.key !== messageKey
    || renderedProductMessages?.node !== interviewMessages.firstChild;
  if (messagesChanged) {
    cancelInterviewScrollAlignment();
    interviewMessages.innerHTML = '';
    if (current) addProductSituationMessage(current.participant_payload);
    for (const item of dialogue) {
      if (item.text) {
        const label = item.speaker_type === 'character' ? item.speaker_name || 'Персонаж'
          : item.speaker_type === 'assessment' ? 'Уточнение к вашему ответу' : 'Материал ситуации';
        const row = addInterviewMessage(item.role, item.text, label, { scroll: false });
        if (item.turn_id) row.dataset.turnId = item.turn_id;
      }
    }
    if (clarification?.status === 'ASK' && !clarification.response_outcome && clarification.question?.text &&
        !(snapshot.trace?.turns || []).some((turn) => turn.turn_id === clarification.question_turn_id)) {
      addInterviewMessage('assistant', clarification.question.text, 'Уточнение к вашему ответу', { scroll: false });
    }
    renderedProductMessages = { key: messageKey, node: interviewMessages.firstChild,
      cycleId: snapshot.cycle_id, situationId: current?.assessment_situation_id };
  }
  if (interviewScrollArea && messagesChanged) {
    const targetTop = current && previousCaseKey !== current.assessment_situation_id ? 0 : previousScrollTop;
    scheduleInterviewScrollAlignment({
      top: sameSituation ? targetTop : 0,
      followBottom: sameSituation && wasNearBottom,
    });
  }
  renderInterviewMeta();
  renderCaseProgress(false);
  interviewPanel.classList.remove('single-turn-mode', 'completed');
  interviewCompleteActions.classList.add('hidden');
  interviewTimerBadge.classList.remove('is-paused');

  if (snapshot.between_situations) {
    stopProductPresence();
    interviewTimerBadge.classList.add('is-paused');
    interviewMessages.innerHTML = '';
    const card = document.createElement('section'); card.className = 'interview-return-card';
    const title = document.createElement('h3'); title.textContent = `Ситуация ${state.assessmentCaseNumber} завершена`;
    const copy = document.createElement('p');
    copy.textContent = 'Ответы сохранены. Сейчас пауза: время на выполнение не расходуется, но общий срок завершения оценки продолжает идти.';
    const button = document.createElement('button'); button.type = 'button'; button.className = 'primary-button';
    button.textContent = 'Приступить к следующей ситуации';
    const status = document.createElement('p'); status.setAttribute('role', 'status');
    const preparation = snapshot.preparation_operation;
    if (preparation?.status === 'failed') {
      status.textContent = preparation.error?.message || 'Не удалось подготовить следующую ситуацию.';
      button.disabled = preparation.retry_allowed !== true;
      if (!button.disabled) button.textContent = 'Повторить подготовку';
    } else if (['queued', 'running'].includes(preparation?.status)) {
      status.textContent = 'Подготавливаем следующую ситуацию…';
      button.disabled = true;
    }
    button.addEventListener('click', async () => {
      const scope = productInterviewAnswerScope();
      const current = () => isProductInterviewAnswerCurrent(scope) && card.isConnected;
      button.disabled = true; status.textContent = 'Проверяем готовность следующей ситуации…';
      try {
        const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/next', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ idempotency_key: createOperationId() }),
        });
        const accepted = await readApiResponse(response, 'Не удалось перейти к следующей ситуации.');
        if (!current()) return;
        const next = accepted.operation_id ? await waitForProductCyclePreparation(accepted) : accepted;
        if (!current()) return;
        if (next.decision?.status === 'SELECTED') { await loadProductRuntime(); return; }
        if (next.decision?.status === 'WAITING_CURRENT_AS') {
          status.textContent = 'Текущая ситуация ещё не завершена. Возвращаем сохранённое состояние…';
          await loadProductRuntime(); return;
        }
        if (['NO_ADMISSIBLE_CASE', 'OUT_OF_TIME'].includes(next.decision?.status)) {
          await completeProductCycle(); return;
        }
        if (next.decision?.status === 'COLLECTION_CLOSED') {
          status.textContent = 'Сбор ответов завершён. Загружаем состояние обработки…';
          await loadProductRuntime(); return;
        }
        status.textContent = 'Следующая ситуация ещё не готова. Попробуйте ещё раз.';
        button.disabled = false;
      } catch (error) {
        if (!current()) return;
        status.textContent = assessmentRuntimeErrorMessage(error, { draftSaved: isCurrentInterviewDraftSaved() });
        button.disabled = error.name === 'PreparationFailed' && !error.retryAllowed;
        if (error.name === 'PreparationFailed' && error.retryAllowed) button.textContent = 'Повторить подготовку';
      }
    });
    card.append(title, copy, button, status); interviewMessages.appendChild(card);
    interviewTextarea.disabled = true; interviewSubmitButton.disabled = true; interviewFinishButton.disabled = true;
    interviewPauseButton?.classList.add('hidden'); interviewAdditionalButton?.classList.add('hidden');
    interviewCaseStatus.textContent = 'Пауза. Следующая ситуация откроется только после вашего действия.';
    confirmedProductInterviewCanSend = false;
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
  interviewFinishButton.disabled = closed || suspended || !current || waitingQuestion
    || (current.status === 'scenario_ended' && snapshot.finish_availability?.allowed !== true);
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
        ? snapshot.finish_availability?.allowed === true
          ? 'Уточнение завершено. Можно завершить ситуацию.'
          : snapshot.pipeline?.status === 'failed' || ['WAIT_TECHNICAL', 'ANALYSIS_FAILED'].includes(snapshot.finish_availability?.reason)
            ? 'Не удалось завершить анализ. Ответы сохранены; ожидаем восстановления обработки.'
            : 'Анализируем последний ответ. Завершение ситуации пока недоступно.'
        : 'Ответы сохраняются в текущей Assessment Situation.';
  confirmedProductInterviewCanSend = !interviewSubmitButton.disabled && productInterviewSourceReady(snapshot);
  if (!confirmedProductInterviewCanSend) {
    interviewTextarea.disabled = true;
    interviewSubmitButton.disabled = true;
  }
  renderProductInterviewAnswerDelivery(snapshot, confirmedProductInterviewCanSend);
  updateInterviewTimer();
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
  const progress = value.progress || {};
  const completedPositions = Number.isInteger(Number(progress.completed_positions))
    ? Math.max(0, Number(progress.completed_positions)) : 0;
  const totalPositions = Number.isInteger(Number(progress.total_positions))
    ? Math.max(0, Number(progress.total_positions)) : 0;
  state.assessmentRuntimeKind = 'cycle';
  state.productCycleId = value.cycle_id;
  state.productAssessmentSituationId = value.current_assessment_situation_id;
  state.productCycleStatus = value.collection_status;
  state.assessmentCaseNumber = Number.isInteger(Number(value.position_no))
    ? Math.max(1, Number(value.position_no)) : completedPositions + 1;
  state.assessmentTotalCases = totalPositions;
  state.assessmentCaseTitle = 'Продолжение оценки';
  renderInterviewMeta();
  renderCaseProgress(false);
  const confirmedPause = ['paused', 'interrupted'].includes(value.collection_status)
    || ['continue_current', 'replace_current'].includes(value.allowed_action);
  interviewTimerBadge.classList.toggle('is-paused', confirmedPause);
  state.assessmentRemainingSeconds = serverRemainingSeconds(value.remaining_seconds);
  updateInterviewTimer();
  interviewMessages.innerHTML = '';
  const card = document.createElement('section'); card.className = 'interview-return-card';
  const title = document.createElement('h3'); title.textContent = 'Продолжение оценки';
  const copy = document.createElement('p');
  const remainingSeconds = serverRemainingSeconds(value.remaining_seconds);
  const remainingCopy = remainingSeconds === null
    ? 'Остаток времени выполнения уточняется.'
    : `Остаток времени выполнения: ${Math.ceil(remainingSeconds / 60)} мин.`;
  copy.textContent = `Завершено ${completedPositions} из ${totalPositions}. ${remainingCopy}`;
  const reason = document.createElement('p');
  reason.textContent = value.allowed_action === 'replace_current'
    ? 'После продолжения текущая незавершённая ситуация будет обновлена. Частичный диалог не переносится, завершённые ситуации сохраняются.'
    : 'После продолжения откроется та же незавершённая ситуация и сохранённый диалог.';
  const button = document.createElement('button'); button.type = 'button'; button.className = 'primary-button'; button.textContent = 'Продолжить';
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
    button.disabled = true; status.textContent = value.allowed_action === 'replace_current' ? 'Готовим допустимое обновление ситуации…' : 'Восстанавливаем ситуацию…';
    try {
      const pending = pendingReturnContinue(value);
      if (value.allowed_action === 'replace_current' && !pending.generationOperationId) {
        if (!value.provider_config_ref) throw new Error('Для этого Cycle ещё не подключён допущенный provider обновления.');
        const generatedResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(cycleId)
          + '/positions/' + encodeURIComponent(value.position_no) + '/equivalent-candidate', {
          method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ expected_assessment_situation_id: value.current_assessment_situation_id,
            idempotency_key: pending.generationKey, provider_config_ref: value.provider_config_ref }),
        });
        const generated = await readApiResponse(generatedResponse, 'Не удалось подготовить допустимое обновление ситуации.');
        if (!current()) return;
        pending.generationOperationId = generated.operation_id;
        window.sessionStorage.setItem(RETURN_CONTINUE_PENDING_KEY, JSON.stringify(pending));
      }
      if (!current()) return;
      const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(cycleId) + '/return-continue', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_no: value.position_no,
          expected_assessment_situation_id: value.current_assessment_situation_id,
          expected_state: value.current_assessment_situation_status,
          idempotency_key: pending.key, generation_operation_id: pending.generationOperationId }),
      });
      const continued = await readApiResponse(response, 'Не удалось продолжить оценку.');
      if (!current()) return;
      clearPendingReturnContinue(value);
      if (continued.status === 'collection_closed') { openProcessing(); return; }
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
        // The newly rendered card reuses the pending key after server readback.
      } catch (_readbackError) {
        if (!current()) return;
        status.textContent = `${assessmentRuntimeErrorMessage(error, { draftSaved: isCurrentInterviewDraftSaved() })} Результат пока неизвестен. Обновите состояние перед повтором.`;
        return;
      }
    }
  });
  card.append(title, copy, reason, button, status); interviewMessages.appendChild(card);
  interviewTextarea.disabled = true; interviewSubmitButton.disabled = true; interviewFinishButton.disabled = true;
  interviewCaseStatus.textContent = 'Пауза. Оценка продолжится только после вашего действия.';
  scheduleInterviewBottomAlignment();
};

const loadReturnState = async ({ generation = productRuntimePollGeneration } = {}) => {
  const requestGeneration = generation ?? productRuntimePollGeneration;
  const viewGeneration = getAssessmentViewGeneration();
  const cycleId = state.productCycleId;
  const situationId = state.productAssessmentSituationId;
  const ownerId = state.pendingUser?.id;
  const identityEpoch = state.identityEpoch;
  const screen = state.currentScreen;
  const current = () => state.productCycleId === cycleId && state.pendingUser?.id === ownerId
    && state.productAssessmentSituationId === situationId && state.identityEpoch === identityEpoch
    && state.currentScreen === screen
    && requestGeneration === productRuntimePollGeneration && viewGeneration === getAssessmentViewGeneration();
  try {
    const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(cycleId) + '/return-state', { credentials: 'same-origin' });
    if (!current()) return false;
    if (response.status === 409) {
      const blocked = await response.json().catch(() => ({}));
      if (!current()) return false;
      if (['M7_RETURN_CURRENT_POSITION_NOT_FOUND', 'M7_RETURN_POLICY_NOT_SNAPSHOTTED'].includes(blocked.detail)) return false;
      throw new Error(blocked.detail || 'Не удалось проверить состояние возврата.');
    }
    const value = await readApiResponse(response, 'Не удалось проверить состояние возврата.');
    if (!current() || value.cycle_id !== cycleId) return false;
    if (['continue_current', 'replace_current'].includes(value.allowed_action)) { renderReturnCard(value); return true; }
    return false;
  } catch (error) {
    if (!current()) return false;
    throw error;
  }
};

export const loadProductRuntime = async ({ generation = productRuntimePollGeneration } = {}) => {
  if (!state.productCycleId) throw new Error('Cycle runtime не инициализирован.');
  const requestGeneration = generation ?? productRuntimePollGeneration;
  const viewGeneration = getAssessmentViewGeneration();
  const cycleId = state.productCycleId;
  let situationId = state.productAssessmentSituationId;
  const ownerId = state.pendingUser?.id;
  const identityEpoch = state.identityEpoch;
  const screen = state.currentScreen;
  const current = () => state.productCycleId === cycleId && state.pendingUser?.id === ownerId
    && state.productAssessmentSituationId === situationId && state.identityEpoch === identityEpoch
    && state.currentScreen === screen
    && requestGeneration === productRuntimePollGeneration && viewGeneration === getAssessmentViewGeneration();
  try {
    // Check the server-owned pause before fetching any AS content. Reload/login/GET
    // never resumes a recognized absence; only the explicit command above does.
    if (await loadReturnState({ generation })) return null;
    if (!current()) return null;
    const response = await fetch('/users/assessment/cycles/' + encodeURIComponent(cycleId) + '/runtime', {
      credentials: 'same-origin',
    });
    const saved = await readApiResponse(response, 'Не удалось восстановить состояние оценки.');
    if (!current() || saved.cycle_id !== cycleId) return null;
    clearConfirmedReturnContinue(saved);
    state.productAssessmentSituationId = saved.current_situation?.assessment_situation_id || null;
    situationId = state.productAssessmentSituationId;
    const terminal = ['collection_closed', 'calculation_pending', 'calculated', 'failed']
      .includes(saved.status?.collection_status);
    const snapshot = renderProductRuntime(saved);
    if (!terminal && saved.return_policy_enabled && saved.current_situation && returnPresenceCycleId !== saved.cycle_id) {
      try {
        const presenceContract = await heartbeatProductPresence();
        if (!current()) return null;
        if (presenceContract) {
          returnPresenceCycleId = saved.cycle_id;
          startProductPresence(presenceContract);
        } else {
          await loadReturnState({ generation });
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
    if (['collection_closed', 'calculation_pending', 'calculated'].includes(snapshot.status?.collection_status) &&
        !interviewPanel.classList.contains('hidden')) {
      openProcessing();
    }
    return snapshot;
  } catch (error) {
    if (!current()) return null;
    throw error;
  }
};

const waitForProductClarification = async (previousDecisionId = null) => {
  const scope = productInterviewAnswerScope();
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (!isProductInterviewAnswerCurrent(scope)) return null;
    const snapshot = await loadProductRuntime();
    if (!snapshot) return null;
    const decision = snapshot.clarification;
    if (snapshot.pipeline?.status === 'failed') throw new Error(snapshot.pipeline.error_code || 'Ошибка анализа.');
    if ((decision?.status === 'ASK' && !decision.response_outcome && decision.id !== previousDecisionId)
        || snapshot.finish_availability?.allowed === true) return snapshot;
    if (snapshot.finish_availability?.reason === 'WAIT_TECHNICAL') {
      throw new Error('Уточнение ожидает восстановления обработки. Ответы сохранены.');
    }
    await new Promise((resolve) => window.setTimeout(resolve, PRODUCT_RUNTIME_POLL_MS));
  }
  throw new Error('Анализ уточнения ещё не завершён. Состояние можно восстановить после обновления страницы.');
};

const completeProductCycle = async () => {
  const scope = productInterviewAnswerScope();
  stopProductPresence();
  const response = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/completion', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'complete', reason: 'user_completed_scenario', idempotency_key: createOperationId() }),
  });
  await readApiResponse(response, 'Не удалось завершить сбор оценки.');
  if (!isProductInterviewAnswerCurrent(scope)) return;
  safeStorage.setItem(STORAGE_KEYS.completionPending, '1');
  openProcessing();
};

export const finishProductAssessment = async () => {
  const scope = productInterviewAnswerScope();
  let snapshot = await loadProductRuntime();
  if (!snapshot || !isProductInterviewAnswerCurrent(scope)) return;
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
    if (!isProductInterviewAnswerCurrent(scope)) return;
    interviewCaseStatus.textContent = 'Анализируем, требуется ли уточнение…';
    snapshot = await waitForProductClarification(snapshot.clarification?.id || null);
    if (!snapshot) return;
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
  const finishedResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/finish-situation', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: createOperationId() }),
  });
  await readApiResponse(finishedResponse, 'Не удалось завершить текущую ситуацию.');
  if (!isProductInterviewAnswerCurrent(scope)) return;
  await loadProductRuntime();
};

export const toggleProductPause = async () => {
  const scope = productInterviewAnswerScope();
  const action = state.productCycleStatus === 'paused' ? 'resume' : 'pause';
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
  let snapshot = await loadProductRuntime();
  if (!snapshot || !isProductInterviewAnswerCurrent(scope)) return;
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
    if (!isProductInterviewAnswerCurrent(scope)) return;
    await loadProductRuntime();
    return;
  }
  if (snapshot.continuation?.status === 'pending') {
    const sessionResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/additional-sessions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent_id: snapshot.continuation.intent_id, idempotency_key: createOperationId() }),
    });
    await readApiResponse(sessionResponse, 'Не удалось создать Additional Session.');
    if (!isProductInterviewAnswerCurrent(scope)) return;
  }
  const nextResponse = await fetch('/users/assessment/m7/cycles/' + encodeURIComponent(state.productCycleId) + '/next', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: createOperationId() }),
  });
  const accepted = await readApiResponse(nextResponse, 'Не удалось выбрать следующую Assessment Situation.');
  if (!isProductInterviewAnswerCurrent(scope)) return;
  if (accepted.operation_id) await waitForProductCyclePreparation(accepted);
  if (!isProductInterviewAnswerCurrent(scope)) return;
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

export const setInterviewMessageDeliveryState = (row, deliveryState, onRetry = null) => {
  if (!(row instanceof HTMLElement)) return;
  const delivery = row.querySelector('.interview-message-delivery');
  const status = row.querySelector('.interview-message-delivery-status');
  const retryButton = row.querySelector('.interview-message-retry');
  if (!delivery || !status || !retryButton) return;
  const followBottom = row.isConnected && isInterviewNearBottom();

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
    retryButton.textContent = 'Повторить';
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
    interviewTimerBadge.textContent = prefix + 'Время уточняется';
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
    const runtimeResponse = await fetch(runtimeUrl, { credentials: 'same-origin' });
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
      if (operation.status === 'prepared') window.sessionStorage.removeItem(productInterviewAnswerKey(operation));
      return { accepted: saved, pending: operation.status !== 'prepared', blocked: true };
    }
    const expectedEndpoint = operation.clarificationId
      ? '/users/assessment/m7/clarifications/' + encodeURIComponent(operation.clarificationId) + '/answers'
      : '/users/assessment/m5/situations/' + encodeURIComponent(operation.situationId) + '/turns';
    if (operation.endpoint !== expectedEndpoint || text !== operation.text) throw new Error('Операция отправки изменилась.');
    const body = {
      request_id: operation.requestId, turn_id: operation.turnId, content: operation.text,
    };
    operation.status = 'unknown';
    saveProductInterviewAnswer(operation);
    const response = await fetch(operation.endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const receipt = await readApiResponse(response, 'Не удалось сохранить ответ в Cycle runtime.');
    operation.accepted = productInterviewReceiptAccepted(receipt, operation);
    operation.status = operation.accepted ? 'accepted' : 'unknown';
    saveProductInterviewAnswer(operation);
    if (operation.accepted) clearInterviewDraft(operation);
    if (!isProductInterviewPresentationCurrent(operation)) return { accepted: operation.accepted, stale: true };
    if (operation.clarificationId && operation.accepted) {
      interviewCaseStatus.textContent = 'Повторно анализируем ответ на уточнение…';
    }
    const readbackResponse = await fetch(runtimeUrl, { credentials: 'same-origin' });
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
    if (!document.hidden && !interviewPanel.classList.contains('hidden')) {
      void loadProductRuntime({ generation: productRuntimePollGeneration }).catch(showInterviewRuntimeError);
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
  interviewPanel.classList.remove('completed');
  interviewCompleteActions.classList.add('hidden');
  interviewPanel.classList.remove('hidden');
  if (isCycleAssessment()) {
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
      persistAssessmentContext();
      openProcessing();
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
      openProcessing({ initialCycleSnapshot: state.productCycleId ? {
        results_status: journey.assessment?.status === 'failed' ? 'failed' : 'processing',
        report_status: journey.report_status || 'not_ready',
      } : null });
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
  disableTextareaAssistFeatures(interviewTextarea);
  interviewTextarea.addEventListener('input', () => {
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
    advanceAssessmentViewGeneration();
    cancelInterviewScrollAlignment();
    clearInterviewTimer();
    stopProductPresence();
    void pauseAssessmentTimerIfNeeded();
  });
};

export { startAssessmentInterview, submitAssessmentMessage, updateInterviewTimer };
