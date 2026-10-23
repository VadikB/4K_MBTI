import { readApiResponse } from './api.js';

const POLL_INTERVAL_MS = 1500;

export const waitForProductCyclePreparation = async (accepted) => {
  if (accepted.status === 'completed' && accepted.result) return accepted.result;
  const operationId = accepted.operation_id;
  if (!operationId) throw new Error('Сервер не вернул идентификатор подготовки плана оценки.');
  while (true) {
    await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
    const statusResponse = await fetch(
      '/users/assessment/cycles/preparation/' + encodeURIComponent(operationId),
      { credentials: 'same-origin' },
    );
    const operation = await readApiResponse(statusResponse, 'Не удалось получить статус подготовки плана оценки.');
    if (operation.status === 'completed') {
      if (!operation.result) throw new Error('Подготовка завершена без готового плана оценки.');
      return operation.result;
    }
    if (operation.status === 'failed') {
      throw new Error(operation.error?.message || 'Не удалось подготовить план оценки.');
    }
  }
};

export const prepareProductCycle = async (payload) => {
  const response = await fetch('/users/assessment/cycles/prepare', {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const accepted = await readApiResponse(response, 'Не удалось поставить подготовку плана оценки в очередь.');
  return waitForProductCyclePreparation(accepted);
};
