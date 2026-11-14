import { createOperationId, readApiResponse, fetchWithDeadline } from './api.js';

const transportFailure = (error) => error instanceof TypeError ||
  /failed to fetch|networkerror|load failed/i.test(String(error?.message || ''));
const uncertainPost = (error) => transportFailure(error) || Number(error?.status) >= 500 ||
  ['AbortError', 'RequestDeadlineError', 'StartReceiptInvalid'].includes(error?.name);

const committedRuntime = (runtime, cycleId) => runtime?.cycle_id === cycleId &&
  runtime?.current_situation?.status === 'active' &&
  runtime.current_situation.participant_payload !== null &&
  typeof runtime.current_situation.participant_payload === 'object' &&
  !Array.isArray(runtime.current_situation.participant_payload) &&
  Object.keys(runtime.current_situation.participant_payload).length > 0;

const pendingKey = (cycleId) => `assessment-start-pending:${cycleId}`;
const pendingStorage = () => {
  try { return window.sessionStorage; } catch { return null; }
};
const readPendingOperation = (cycleId) => {
  try { return pendingStorage()?.getItem(pendingKey(cycleId)); } catch { return null; }
};
const writePendingOperation = (cycleId, operationId) => {
  try { pendingStorage()?.setItem(pendingKey(cycleId), operationId); } catch { /* Readback still runs. */ }
};
const clearPendingOperation = (cycleId) => {
  try { pendingStorage()?.removeItem(pendingKey(cycleId)); } catch { /* Server remains authoritative. */ }
};
export const hasPendingPreparedStart = (cycleId) => Boolean(readPendingOperation(cycleId));
const unknownStart = (operationId, cause) => Object.assign(new Error(
  'Состояние не подтверждено. Результат команды старта пока неизвестен. Проверьте состояние ещё раз перед повтором старта.',
), { name: 'AssessmentStartUnknown', operationId, cause });

const readStartedRuntime = async (cycleId, fetchImpl) => {
  const response = await fetchImpl('/users/assessment/cycles/' + encodeURIComponent(cycleId) + '/runtime', {
    credentials: 'same-origin',
  });
  const runtime = await readApiResponse(response, 'Не удалось проверить состояние старта.');
  if (runtime?.cycle_id !== cycleId) throw new Error('Состояние другого Cycle не подтверждает старт.');
  return runtime;
};

export const readPendingPreparedStart = async (cycleId, {
  fetchImpl = fetchWithDeadline,
} = {}) => {
  const operationId = readPendingOperation(cycleId);
  if (!operationId) return null;
  try {
    const runtime = await readStartedRuntime(cycleId, fetchImpl);
    if (!committedRuntime(runtime, cycleId) && runtime?.current_situation?.status !== 'admitted') {
      throw unknownStart(operationId);
    }
    return { started: committedRuntime(runtime, cycleId), operationId };
  } catch (error) { throw unknownStart(operationId, error); }
};

export const startPreparedProductCycle = async (cycleId, {
  fetchImpl = fetchWithDeadline, operationId = createOperationId(),
} = {}) => {
  const pendingOperationId = readPendingOperation(cycleId);
  if (pendingOperationId) {
    let runtime;
    try { runtime = await readStartedRuntime(cycleId, fetchImpl); }
    catch (error) { throw unknownStart(pendingOperationId, error); }
    if (committedRuntime(runtime, cycleId)) {
      clearPendingOperation(cycleId);
      return { plan: { cycle_id: cycleId }, runtime, recovered_after_transport_failure: true };
    }
    if (runtime?.current_situation?.status !== 'admitted') {
      throw unknownStart(pendingOperationId);
    }
  }
  const startOperationId = pendingOperationId || operationId;
  // Keep the command identity even if the page reloads while POST is in flight.
  writePendingOperation(cycleId, startOperationId);
  try {
    const response = await fetchImpl('/users/assessment/cycles/start', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: cycleId, idempotency_key: startOperationId }),
    });
    let started;
    try {
      started = await readApiResponse(response, 'Не удалось подтвердить ответ на команду старта.');
    } catch (error) {
      if (!response.ok) throw error;
      throw Object.assign(new Error('Неполный ответ на команду старта.'), { name: 'StartReceiptInvalid', cause: error });
    }
    if (started?.plan?.cycle_id !== cycleId || !committedRuntime(started?.runtime, cycleId)) {
      throw Object.assign(new Error('Неполный ответ на команду старта.'), { name: 'StartReceiptInvalid' });
    }
    clearPendingOperation(cycleId);
    return started;
  } catch (error) {
    if (!uncertainPost(error)) {
      clearPendingOperation(cycleId);
      throw error;
    }
    writePendingOperation(cycleId, startOperationId);
    let readbackFailure;
    try {
      const runtime = await readStartedRuntime(cycleId, fetchImpl);
      if (committedRuntime(runtime, cycleId)) {
        clearPendingOperation(cycleId);
        return { plan: { cycle_id: cycleId }, runtime, recovered_after_transport_failure: true };
      }
    } catch (readbackError) {
      // A refusal cannot confirm the POST outcome, but its safe reason matters.
      readbackFailure = readbackError;
    }
    throw unknownStart(startOperationId, readbackFailure || error);
  }
};
