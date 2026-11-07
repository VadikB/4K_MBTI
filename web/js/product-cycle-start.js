import { createOperationId, readApiResponse } from './api.js';

const transportFailure = (error) => error instanceof TypeError ||
  /failed to fetch|networkerror|load failed/i.test(String(error?.message || ''));

const committedRuntime = (runtime, cycleId) => runtime?.cycle_id === cycleId &&
  runtime?.current_situation?.status !== 'admitted' &&
  Boolean(runtime?.current_situation?.participant_payload);

export const startPreparedProductCycle = async (cycleId, {
  fetchImpl = window.fetch.bind(window), operationId = createOperationId(),
} = {}) => {
  try {
    const response = await fetchImpl('/users/assessment/cycles/start', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_id: cycleId, idempotency_key: operationId }),
    });
    return await readApiResponse(response, 'Не удалось запустить Cycle runtime.');
  } catch (error) {
    if (!transportFailure(error)) throw error;
    try {
      const response = await fetchImpl('/users/assessment/cycles/' + encodeURIComponent(cycleId) + '/runtime', {
        credentials: 'same-origin',
      });
      const runtime = await readApiResponse(response, 'Не удалось проверить состояние старта.');
      if (committedRuntime(runtime, cycleId)) {
        return { plan: { cycle_id: cycleId }, runtime, recovered_after_transport_failure: true };
      }
    } catch (readbackError) {
      if (!transportFailure(readbackError)) throw readbackError;
    }
    throw Object.assign(new Error(
      'Ответ на команду старта не получен. Состояние не подтверждено; данные сохранены. Проверьте состояние ещё раз.',
    ), { name: 'AssessmentStartUnknown', operationId, cause: error });
  }
};
