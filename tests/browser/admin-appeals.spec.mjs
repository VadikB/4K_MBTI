import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

let server, base;
test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    if (request.url === '/') {
      response.setHeader('Content-Type', 'text/html');
      response.end('<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/web/styles/tokens.css"><link rel="stylesheet" href="/web/styles/base.css"><link rel="stylesheet" href="/web/styles/components.css"><link rel="stylesheet" href="/web/styles/screens/admin-organizations.css"><dialog class="admin-member-card-dialog"><form method="dialog"><h3>Участник</h3><div data-card-actions></div><button>Закрыть</button></form></dialog>');
      return;
    }
    try {
      const file = path.join(process.cwd(), new URL(request.url, 'http://127.0.0.1').pathname);
      response.setHeader('Content-Type', file.endsWith('.css') ? 'text/css' : 'application/javascript');
      response.end(await fs.readFile(file));
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => { if (server?.listening) await new Promise(resolve => server.close(resolve)); });

test('Admin 03 claim, uncertain reply and readback preserve the response', async ({ page }) => {
  const issue = { id: 41, user_id: 1, organization_id: 10, message: 'Поле: Роль\nНужно уточнить',
    status: 'open', assignment_ref: 'assessment-a', assignment_id: 9, questionnaire_revision_id: 3,
    claimed_by_user_id: null, claimed_by_active_admin: false, reply_message: null };
  await page.route('**/users/admin/organizations/10/members/1/issues**', async route => {
    const url = new URL(route.request().url());
    if (route.request().method() === 'GET') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [issue] }) });
    if (url.pathname.endsWith('/claim')) {
      issue.status = 'in_progress'; issue.claimed_by_user_id = 2; issue.claimed_by_active_admin = true;
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ id: 41, status: issue.status }) });
    }
    if (url.pathname.endsWith('/reply')) {
      issue.status = 'answered'; issue.reply_message = route.request().postDataJSON().message;
      // Simulate a lost response after the server committed the reply.
      return route.abort('failed');
    }
  });
  await page.goto(base);
  await page.evaluate(async () => {
    const { state } = await import('/web/js/state.js');
    state.pendingUser = { id: 2 }; state.identityEpoch = 1;
    const dialog = document.querySelector('dialog'); dialog.showModal();
    const { mountMemberAppeals } = await import('/web/js/screens/admin/appeals.js');
    mountMemberAppeals(dialog, 10, 1);
  });
  await expect(page.getByText('Связь с назначением неизвестна')).toHaveCount(0);
  await expect(page.getByText('Поле: Роль')).toBeVisible();
  await page.getByRole('button', { name: 'Взять в работу' }).click();
  const answer = page.getByPlaceholder('Ответ участнику');
  await expect(answer).toBeVisible();
  await answer.fill('Проверили и исправили');
  if (process.env.ADMIN03_EVIDENCE_DIR) {
    await fs.mkdir(process.env.ADMIN03_EVIDENCE_DIR, { recursive: true });
    await page.screenshot({ path: path.join(process.env.ADMIN03_EVIDENCE_DIR, 'admin-appeal.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(process.env.ADMIN03_EVIDENCE_DIR, 'admin-appeal-mobile.png') });
  }
  await page.getByRole('button', { name: 'Отправить ответ' }).click();
  await expect(page.getByText('Ответ: Проверили и исправили')).toBeVisible();
  expect(issue.reply_message).toBe('Проверили и исправили');
});

test('Admin 03 failed save keeps the typed answer', async ({ page }) => {
  const issue = { id: 42, user_id: 1, organization_id: 10, message: 'Неточная должность',
    status: 'in_progress', assignment_ref: null, assignment_id: null, questionnaire_revision_id: null,
    claimed_by_user_id: 2, claimed_by_active_admin: true, reply_message: null };
  await page.route('**/users/admin/organizations/10/members/1/issues**', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ items: [issue] }) });
    return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Сохранение временно недоступно' }) });
  });
  await page.goto(base);
  await page.evaluate(async () => {
    const { state } = await import('/web/js/state.js');
    state.pendingUser = { id: 2 }; state.identityEpoch = 1;
    const dialog = document.querySelector('dialog'); dialog.showModal();
    const { mountMemberAppeals } = await import('/web/js/screens/admin/appeals.js');
    mountMemberAppeals(dialog, 10, 1);
  });
  await expect(page.getByText('Связь с назначением неизвестна')).toBeVisible();
  const answer = page.getByPlaceholder('Ответ участнику');
  await answer.fill('Проверим данные');
  await page.getByRole('button', { name: 'Отправить ответ' }).click();
  await expect(answer).toHaveValue('Проверим данные');
  await expect(page.getByText('Текст ответа сохранён в форме.', { exact: false })).toBeVisible();
});
