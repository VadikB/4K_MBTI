import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import vm from 'node:vm';

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
for (const [code, expected] of [
  ['INVITATION_ALREADY_USED', 'уже использовано'],
  ['INVITATION_NOT_FOUND', 'больше не найдено'],
  ['INVITATION_STATE_CHANGED', 'Состояние участника изменилось'],
]) {
  test(`invitation conflict ${code} remains safe and actionable`, async () => {
    await assert.rejects(
      readApiResponse(new Response(JSON.stringify({ detail: code }), {
        status: code === 'INVITATION_NOT_FOUND' ? 404 : 409,
        headers: { 'content-type': 'application/json' },
      }), 'Не удалось отозвать приглашение.'),
      (error) => error instanceof ApiResponseError && error.code === code &&
        error.message.includes(expected) && !/SQL|traceback|token_hash/i.test(error.message),
    );
  });
}
test('membership conflict preserves scoped reason and removes unavailable legacy action', async () => {
  await assert.rejects(
    readApiResponse(new Response(JSON.stringify({
      detail: 'ORGANIZATION_MEMBERSHIP_CONFLICT: Пользователь связан с организацией «Организация А». Откройте организацию или перенесите пользователя.',
    }), { status: 409, headers: { 'content-type': 'application/json' } }), 'Не удалось добавить.'),
    (error) => error.code === 'ORGANIZATION_MEMBERSHIP_CONFLICT' &&
      error.message.includes('Организация А') && !/перенос|перенес/i.test(error.message),
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

for (const detail of [
  'ORGANIZATION_MEMBERSHIP_CONFLICT',
  { code: 'ORGANIZATION_MEMBERSHIP_CONFLICT', message: 'Пользователь связан с другой организацией. Обратитесь к суперадминистратору.' },
]) {
  test('membership conflict string/object code never proposes disabled transfer', async () => {
    await assert.rejects(readApiResponse(new Response(JSON.stringify({ detail }), { status: 409 }), 'Ошибка'),
      (error) => error.code === 'ORGANIZATION_MEMBERSHIP_CONFLICT' && !/перенос|перенес/i.test(error.message));
  });
}

test('scoped organization name containing transfer word remains an exact reason', async () => {
  await assert.rejects(readApiResponse(new Response(JSON.stringify({ detail:
    'ORGANIZATION_MEMBERSHIP_CONFLICT: Пользователь связан с организацией «Перенос технологий». Управляйте его участием в текущей организации.' }), { status: 409 }), 'Ошибка'),
    (error) => error.message.includes('«Перенос технологий»') && error.message.includes('Управляйте его участием'));
});

test('actual add-member handler displays the scoped API reason through production membership formatter', async () => {
  const source = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
  const formatter = source.slice(source.indexOf('const membershipErrorMessage ='), source.indexOf('const invitationRevokeErrorMessage ='));
  const handler = source.slice(source.indexOf('export const addAdminOrganizationMember ='),
    source.indexOf('export const deleteAdminOrganizationMember =')).replace('export const ', 'const ');
  const messages = [];
  const context = vm.createContext({
    setStatus: (message, tone) => messages.push({ message, tone }),
    requestOrganizations: async () => readApiResponse(new Response(JSON.stringify({ detail:
      'ORGANIZATION_MEMBERSHIP_CONFLICT: Пользователь связан с организацией «Синтетический заказчик». Управляйте его участием в текущей организации.' }), { status: 409 }), 'Ошибка'),
  });
  vm.runInContext(formatter + handler + '\nthis.addMember = addAdminOrganizationMember;', context);
  assert.equal(await context.addMember(5, { email: 'member@example.test', full_name: 'Synthetic', role_description: 'Synthetic role' }), false);
  assert.equal(messages[0].tone, 'error');
  assert.match(messages[0].message, /«Синтетический заказчик»/);
  assert.match(messages[0].message, /Управляйте его участием/);
  assert.doesNotMatch(messages[0].message, /перенос|перенес|ORGANIZATION_MEMBERSHIP_CONFLICT/);
});
