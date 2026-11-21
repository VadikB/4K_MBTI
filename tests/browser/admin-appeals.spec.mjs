import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

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
      issue.reply_author_user_id = 2; issue.reply_author_display_name = 'Автор ответа';
      issue.replied_at = '2026-11-20T09:34:00Z';
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
  const answer = page.getByLabel('Ответ участнику');
  await expect(answer).toBeVisible();
  await expect(answer).toBeFocused();
  await answer.fill('Проверили и исправили');
  if (process.env.ADMIN03_EVIDENCE_DIR) {
    await fs.mkdir(process.env.ADMIN03_EVIDENCE_DIR, { recursive: true });
    await page.screenshot({ path: path.join(process.env.ADMIN03_EVIDENCE_DIR, 'admin-appeal.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(process.env.ADMIN03_EVIDENCE_DIR, 'admin-appeal-mobile.png') });
  }
  await page.getByRole('button', { name: 'Отправить ответ' }).click();
  await expect(page.getByText('Проверили и исправили', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Ответ отправлен' })).toBeFocused();
  await expect(page.locator('.appeal-reply-attribution')).toHaveText('Автор ответа · 20.11.2026, 12:34 МСК');
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
  const answer = page.getByLabel('Ответ участнику');
  await answer.fill('Проверим данные');
  await page.getByRole('button', { name: 'Отправить ответ' }).click();
  await expect(answer).toHaveValue('Проверим данные');
  await expect(page.getByText('Текст ответа сохранён в форме.', { exact: false })).toBeVisible();
  await expect(answer).toBeEditable();
});

test('ADM-UI-03 organization roster opens the appeals section or the top of the member card', async ({ page }) => {
  const preview = await startAdminProgramPreview({ port: 0 });
  const demo = 'http://127.0.0.1:' + preview.server.address().port + '/demo/admin/confirmed/';
  const longMessage = 'Исходное сообщение\n' + 'ДлинноеОбращение'.repeat(70);
  const longReply = 'Сохранённый ответ\n' + 'ДлинныйОтвет'.repeat(70);
  await page.route('**/users/admin/organizations', async route => {
    const response = await route.fetch();
    const data = await response.json();
    const org = data.items[0];
    const [member] = org.members;
    org.members = [
      { ...member, issue_count: 2 },
      { ...member, user_id: 29, full_name: 'Второй участник', email: 'second@example.test', issue_count: 1 },
      { ...member, user_id: 30, full_name: 'Участник без обращений', email: 'third@example.test', issue_count: 0 },
    ];
    data.items.push({ ...org, id: 4, name: 'Другая синтетическая организация', assessment_program: null, members: [org.members[2]] });
    await route.fulfill({ response, json: data });
  });
  await page.route('**/users/admin/organizations/3/members/28/issues', route => route.fulfill({ json: { items: [
    { id: 43, status: 'in_progress', message: longMessage, assignment_id: 9, assignment_ref: 'technical-ref',
      questionnaire_revision_id: 3, claimed_by_user_id: 19, claimed_by_active_admin: true },
    { id: 44, status: 'answered', message: 'Историческое обращение', reply_message: longReply,
      reply_author_display_name: null, replied_at: '2026-11-20T09:34:00Z' },
  ] } }));
  await page.route('**/users/admin/organizations/4/questionnaire', route => route.fulfill({ json: { items: [] } }));
  try {
    await page.goto(demo);
    const panel = page.locator('#admin-organizations-panel');
    const org = panel.locator('[data-organization-id="3"]');
    const orgSelect = panel.locator('#admin-organization-select');
    const filter = org.getByRole('button', { name: 'С обращениями' });
    const name = org.getByRole('button', { name: 'Синтетический участник', exact: true });
    const issues = org.getByRole('button', { name: 'Обращения · 2', exact: true });
    const noIssues = org.getByRole('button', { name: 'Участник без обращений' });
    const dialog = page.getByRole('dialog', { name: 'Синтетический участник' });
    const heading = dialog.getByRole('heading', { name: 'Обращения участника' });
    const close = dialog.getByRole('button', { name: 'Закрыть карточку' });
    await expect(org.getByRole('button', { name: 'Есть обращение' })).toBeVisible();
    await expect(noIssues).toBeVisible();
    await expect(org.locator('.admin-questionnaire-load-state[role="status"]')).toHaveCount(0);
    await filter.focus();
    await page.keyboard.press('Space');
    await expect(filter).toHaveAttribute('aria-pressed', 'true');
    await expect(filter).toBeFocused();
    await expect(org.getByRole('heading', { name: 'Участники с обращениями' })).toBeVisible();
    await expect(noIssues).toHaveCount(0);

    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 840 });
      await name.focus();
      await page.keyboard.press('Enter');
      await expect(close).toBeFocused();
      await expect(dialog.locator('[data-card-email]')).toHaveText('member@example.test');
      await page.keyboard.press('Escape');
      await expect(name).toBeFocused();

      await issues.focus();
      await page.keyboard.press('Enter');
      await expect(heading).toBeFocused();
      await expect(heading).toBeInViewport();
      await expect(dialog.locator('.admin-member-appeal')).toHaveCount(2);
      await expect(dialog.getByText('В работе у другого администратора')).toBeVisible();
      await expect(dialog.getByText('Связь с назначением неизвестна')).toBeVisible();
      await expect(dialog.getByRole('button', { name: 'Взять в работу' })).toHaveCount(0);
      await expect(dialog.getByLabel('Ответ участнику')).toHaveCount(0);
      await expect(dialog.getByText('Назначение № 9')).toBeHidden();
      await page.keyboard.press('Tab');
      await expect(dialog.getByText('Сведения о назначении', { exact: true })).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(dialog.getByText('Назначение № 9')).toBeVisible();
      await expect(dialog.getByText('Редакция анкеты № 3')).toBeVisible();
      await expect(dialog.locator('blockquote').first()).toHaveText(longMessage);
      await expect(dialog.locator('.admin-member-appeal-reply')).toHaveText(longReply);
      await expect(dialog.locator('.appeal-reply-attribution')).toHaveText('Администратор · 20.11.2026, 12:34 МСК');
      const overflow = await dialog.evaluate(node =>
        [node, ...node.querySelectorAll('.admin-member-appeal, blockquote, .admin-member-appeal-reply')]
          .some(element => element.scrollWidth > element.clientWidth + 1));
      expect(overflow).toBe(false);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      if (process.env.ADMIN03_EVIDENCE_DIR) {
        await dialog.screenshot({ path: path.join(process.env.ADMIN03_EVIDENCE_DIR, 'member-card-' + width + '.png') });
      }
      await page.keyboard.press('Escape');
      await expect(issues).toBeFocused();
    }

    await orgSelect.selectOption('4');
    const otherOrg = panel.locator('[data-organization-id="4"]');
    const emptyFilter = otherOrg.getByRole('button', { name: 'С обращениями' });
    await expect(emptyFilter).toHaveAttribute('aria-pressed', 'false');
    await emptyFilter.click();
    await expect(otherOrg.getByText('Участников с обращениями нет.')).toBeVisible();
    await emptyFilter.click();
    await expect(otherOrg.getByRole('button', { name: 'Участник без обращений' })).toBeVisible();
    await orgSelect.selectOption('3');
    await expect(filter).toHaveAttribute('aria-pressed', 'true');
    await filter.click();
    await expect(filter).toHaveAttribute('aria-pressed', 'false');
    await expect(noIssues).toBeVisible();
  } finally {
    await preview.close();
  }
});
