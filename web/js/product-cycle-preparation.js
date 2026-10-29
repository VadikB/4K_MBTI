import { readApiResponse, fetchWithDeadline, getSessionGeneration } from './api.js';

const POLL_INTERVAL_MS = 1500;

const stopped = () => Object.assign(new Error('Локальное ожидание завершено; серверная подготовка продолжается.'), {
  name: 'PreparationWaitStopped',
});

export const waitForProductCyclePreparation = async (accepted, {
  onStatus = () => {}, isCurrent = () => true, signal,
} = {}) => {
  const generation = getSessionGeneration();
  const current = () => generation === getSessionGeneration() && isCurrent() && !signal?.aborted;
  let operation = accepted;
  const operationId = accepted.operation_id;
  if (!operationId) throw new Error('Сервер не вернул идентификатор подготовки плана оценки.');
  let delay = POLL_INTERVAL_MS;
  while (current()) {
    onStatus(operation);
    if (operation.status === 'completed' && operation.result) return operation.result;
    if (operation.status === 'failed') {
      throw Object.assign(new Error(operation.error?.message || 'Не удалось подготовить план оценки.'), {
        name: 'PreparationFailed', operationId: operation.operation_id, operationError: operation.error,
      });
    }
    await new Promise((resolve) => window.setTimeout(resolve, delay));
    if (!current()) throw stopped();
    const statusResponse = await fetchWithDeadline(
      '/users/assessment/cycles/preparation/' + encodeURIComponent(operationId),
      { credentials: 'same-origin', signal },
    );
    operation = await readApiResponse(statusResponse, 'Не удалось получить статус подготовки плана оценки.');
    if (!current()) throw stopped();
    if (operation.status === 'completed' && !operation.result) {
      throw new Error('Подготовка завершена без готового плана оценки.');
    }
    delay = Math.min(5000, Math.round(delay * 1.25));
  }
  throw stopped();
};

export const prepareProductCycle = async (payload, options = {}) => {
  // Store transport identity before POST: its response can be lost after commit.
  options.onRequested?.({ operation_id: payload.idempotency_key, status: 'unknown' });
  const response = await fetchWithDeadline('/users/assessment/cycles/prepare', {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal: options.signal,
  });
  const accepted = await readApiResponse(response, 'Не удалось поставить подготовку плана оценки в очередь.');
  options.onAccepted?.(accepted);
  return waitForProductCyclePreparation(accepted, options);
};
