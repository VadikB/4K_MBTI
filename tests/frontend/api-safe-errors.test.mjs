import assert from 'node:assert/strict';
import test from 'node:test';

import { ApiResponseError, readApiResponse } from '../../web/js/api.js';

test('known domain codes provide actionable messages', async () => {
  await assert.rejects(
    readApiResponse(new Response(JSON.stringify({ detail: 'PROGRAM_ROLE_SELECTION_REQUIRED' }), {
      status: 409, headers: { 'content-type': 'application/json' },
    }), 'Не удалось назначить оценку.'),
    (error) => error instanceof ApiResponseError && error.code === 'PROGRAM_ROLE_SELECTION_REQUIRED' &&
      error.message.includes('Выберите одну из разрешённых ролей') && !error.message.includes('подключите программу'),
  );
});
test('membership conflict preserves the already scope-filtered server action', async () => {
  await assert.rejects(
    readApiResponse(new Response(JSON.stringify({
      detail: 'ORGANIZATION_MEMBERSHIP_CONFLICT: Пользователь связан с организацией «Организация А». Откройте организацию или перенесите пользователя.',
    }), { status: 409, headers: { 'content-type': 'application/json' } }), 'Не удалось добавить.'),
    (error) => error.code === 'ORGANIZATION_MEMBERSHIP_CONFLICT' &&
      error.message.includes('Организация А') && error.message.includes('перенесите пользователя'),
  );
});
for (const [name, body, contentType] of [
  ['json detail', JSON.stringify({ detail: 'SQLSTATE 23503 stack traceback' }), 'application/json'],
  ['plain text', 'Internal Server Error SQL SELECT secret', 'text/plain'],
  ['html', '<html><body>traceback secret</body></html>', 'text/html'],
  ['invalid json', '{"detail":', 'application/json'],
]) {
  test(`unknown 500 ${name} is sanitized`, async () => {
    await assert.rejects(
      readApiResponse(new Response(body, { status: 500, headers: {
        'content-type': contentType, 'x-request-id': 'safe-ref-42',
      } }), 'Fallback'),
      (error) => error instanceof ApiResponseError && error.outcomeUnknown === true &&
        error.message.includes('safe-ref-42') && !/SQL|traceback|secret|Internal Server Error/i.test(error.message),
    );
  });
}

test('stale purge preview tells the operator to refresh without claiming deletion', async () => {
  await assert.rejects(
    readApiResponse(new Response(JSON.stringify({ detail: 'PURGE_PREVIEW_STALE' }), {
      status: 409, headers: { 'content-type': 'application/json' },
    }), 'Не удалось удалить.'),
    (error) => error.code === 'PURGE_PREVIEW_STALE' && error.message.includes('Обновите предварительный просмотр') &&
      error.message.includes('удаление не выполнено'),
  );
});
