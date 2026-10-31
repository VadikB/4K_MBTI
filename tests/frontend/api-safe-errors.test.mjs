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

for (const [code, expected, forbidden] of [
  ['ASSIGNMENT_QUESTIONNAIRE_NOT_CONFIRMED', 'Подтвердите сведения', 'подключите программу'],
  ['PROGRAM_ASSIGNMENT_REF_MISMATCH', 'не соответствует подключённой программе', 'Сначала подключите'],
  ['PROGRAM_NOT_AVAILABLE_FOR_NEW_ASSIGNMENTS', 'больше не принимает новые назначения', 'Подтвердите сведения'],
  ['PROGRAM_CONFIGURATION_NOT_AVAILABLE', 'Настройка программы не завершена', 'пустая организация'],
  ['PROGRAM_CATALOG_SCOPE_MISMATCH', 'недоступен этой организации', 'Подтвердите сведения'],
  ['PROGRAM_SOURCE_SELECTION_STALE', 'Обновите карточку', 'подключите программу'],
]) {
  test(`assignment blocker ${code} keeps its exact next action`, async () => {
    await assert.rejects(
      readApiResponse(new Response(JSON.stringify({ detail: code }), {
        status: 409, headers: { 'content-type': 'application/json' },
      }), 'Не удалось назначить оценку.'),
      (error) => error instanceof ApiResponseError && error.code === code &&
        error.message.includes(expected) && !error.message.includes(forbidden),
    );
  });
}
test('known invitation provider configuration error remains actionable', async () => {
  await assert.rejects(
    readApiResponse(new Response(JSON.stringify({ detail: 'EMAIL_PROVIDER_NOT_CONFIGURED' }), {
      status: 503, headers: { 'content-type': 'application/json' },
    }), 'Не удалось отправить приглашение.'),
    (error) => error instanceof ApiResponseError && error.code === 'EMAIL_PROVIDER_NOT_CONFIGURED' &&
      error.message.includes('Сервис приглашений не настроен') && error.outcomeUnknown === false,
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
