import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { test, expect } from '@playwright/test';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const evidence = process.env.P4K_UX04_SCREENSHOTS;
const reference = process.env.P4K_UX04_REFERENCE_URL;
let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18964 }); });
test.afterAll(async () => { await preview?.close(); });

const createOrganization = (id, code, name, active, reports) => ({
  id, code, name, is_active: active, admins: [], members: [], domains: [],
  members_count: 0, reports_count: reports, assessment_program: null,
});
const historyLink = (page) => page.getByRole('link', { name: 'Журнал и операции' });
const badge = (page) => page.locator('[data-platform-org-state]');
const showPurge = async (page) => {
  await page.getByRole('button', { name: 'Посмотреть состав удаления' }).click();
  await expect(page.getByRole('heading', { name: 'Состав полного удаления' })).toBeVisible();
};

async function fixture(page, { superadmin = true } = {}) {
  const vector = createOrganization(3, 'vector', 'ООО «Вектор»', true, 8);
  const liniya = createOrganization(5, 'liniya', 'АНО «Линия»', false, 3);
  vector.admins = [
    { user_id: 31, email: 'i.sokolov@example.test', full_name: 'Илья Соколов' },
    { user_id: 32, email: 'a.belova@example.test', full_name: 'Анна Белова' },
  ];
  liniya.admins = [{ user_id: 51, email: 'n.fomina@example.test', full_name: 'Нина Фомина' }];
  const state = { items: [vector, liniya], requests: [], posts: [], receipt: null, execution: false,
    blocked: false, stale: false, dropWrite: false, receiptMode: 'exact' };
  const dashboard = { is_superadmin: superadmin, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const listing = () => ({ is_superadmin: superadmin, purge_preview_available: true,
    physical_purge_available: state.execution, items: superadmin ? state.items : [vector], assessment_programs: [] });
  await page.route('**/users/**', async (route) => {
    const request = route.request();
    const { pathname, searchParams } = new URL(request.url());
    const method = request.method();
    state.requests.push({ method, pathname });
    const json = (data, status = 200) => route.fulfill({ json: data, status });
    if (['/users/session/restore', '/users/18/session-bootstrap'].includes(pathname)) return json({
      authenticated: true, user: { id: 18, email: 'synthetic@example.test', full_name: 'Синтетический оператор' },
      is_admin: true, admin_dashboard: dashboard,
    });
    if (pathname === '/users/version') return json({ version: '2.1.65' });
    if (pathname === '/users/admin/dashboard') return json(dashboard);
    if (pathname === '/users/admin/organizations') return json(listing());
    if (pathname === '/users/admin/support/preparation') return json({ items: [], next_before: null });
    if (pathname.endsWith('/questionnaire')) return json({ items: [] });
    const target = pathname.match(/^\/users\/admin\/organizations\/(\d+)(.*)$/);
    if (!target || !superadmin) return json({}, 403);
    const id = Number(target[1]);
    const item = state.items.find((org) => org.id === id);
    const operation = target[2].match(/^\/purge\/operations\/(.+)$/);
    if (operation && method === 'GET') {
      if (state.receiptMode === 'down') return json({}, 503);
      if (!state.receipt || state.receipt.operation_id !== operation[1] ||
          state.receipt.preview_fingerprint !== searchParams.get('preview_fingerprint')) {
        return json({ detail: 'DELETION_RECEIPT_NOT_FOUND' }, 404);
      }
      return json({ ok: true, organization_id: id, operation_id: state.receiptMode === 'wrong' ? 'different' : operation[1] });
    }
    if (!item) return json({}, 404);
    if (target[2] === '/history') {
      return json({ organization_id: id, is_active: item.is_active, events: [
        ...(id === 3 ? [
          { kind: 'administrator_added', occurred_at: '2026-11-20T10:30:00', subject: 'Анна Белова', actor: 'Синтетический оператор' },
          { kind: 'program_connected', occurred_at: '2026-11-18T14:12:00', subject: 'Пилот 4К · 1.2', actor: null },
        ] : []),
        { kind: 'created', occurred_at: '2026-11-17T10:30:00', actor: null },
      ] });
    }
    if ((method === 'DELETE' && !target[2]) || (method === 'POST' && target[2] === '/restore')) {
      item.is_active = method === 'POST';
      return route.abort('connectionreset');
    }
    if (target[2] === '/purge-preview') return json({
      target_id: id, target_type: 'organization', fingerprint: (state.stale ? 'a' : 'b').repeat(64),
      execution_available: state.execution,
      tables: { 'public.organizations': 1, 'public.assessment_reports': item.reports_count },
      total_rows: 1 + item.reports_count,
      accounts: [
        { email: 'shared@example.test', will_delete_account: false },
        ...(state.blocked ? [{ email: 'protected@example.test', preserved_reason: 'configured_account', will_delete_account: false }] : []),
      ],
      execution_blockers: state.blocked ? [{ reason: 'configured_account', email: 'protected@example.test' }] : [],
    });
    if (target[2] === '/purge' && method === 'POST') {
      const command = request.postDataJSON();
      state.posts.push(command);
      if (state.stale) {
        state.stale = false;
        return json({ detail: 'PURGE_PREVIEW_STALE' }, 409);
      }
      if (state.dropWrite) {
        state.dropWrite = false;
        return route.abort('connectionreset');
      }
      state.receipt = command;
      state.items = state.items.filter((org) => org !== item);
      return route.abort('connectionreset');
    }
    return json({}, 404);
  });
  await page.goto(preview.base + '/demo/' + (superadmin ? 'superadmin' : 'admin') + '/confirmed/');
  if (superadmin) await page.locator('#admin-open-organizations-button').click();
  return state;
}

async function openHistory(page, name) {
  await page.getByRole('link', { name, exact: true }).click();
  await historyLink(page).click();
  await expect(page.getByRole('heading', { name: 'Журнал организации' })).toBeVisible();
  await expect(page.getByText('Создана организация', { exact: true })).toBeVisible();
}

test('lifecycle confirms by ID once after a lost response and restores keyboard focus', async ({ page }) => {
  const state = await fixture(page);
  await openHistory(page, 'ООО «Вектор»');
  await expect(page).toHaveURL(/org=3&view=history/);
  await expect(page.getByText('Автор · Синтетический оператор')).toBeVisible();
  await expect(page.locator('time').first()).toHaveAttribute('datetime', '2026-11-20T10:30:00');
  const deactivate = page.getByRole('button', { name: 'Деактивировать организацию' });
  await deactivate.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('button', { name: 'Отмена' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(deactivate).toBeFocused();
  const before = state.requests.length;
  await deactivate.click();
  await dialog.getByRole('button', { name: 'Деактивировать' }).click();
  await expect(badge(page)).toHaveText('Неактивна');
  await expect(page.getByText('Организация деактивирована.', { exact: true })).toBeVisible();
  expect(state.requests.slice(before).filter(({ pathname }) => pathname.includes('/organizations/3'))).toEqual([
    { method: 'DELETE', pathname: '/users/admin/organizations/3' },
    { method: 'GET', pathname: '/users/admin/organizations/3/history' },
  ]);
  await expect(page.locator('.org-history-timeline li')).toHaveCount(3);
  await page.reload();
  await expect(badge(page)).toHaveText('Неактивна');
  await page.getByRole('button', { name: 'Восстановить организацию' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Восстановить' }).click();
  await expect(badge(page)).toHaveText('Активна');
  await page.getByRole('link', { name: 'Обзор' }).click();
  await expect(page.getByText('Готовые отчёты:')).toContainText('8');
});

test('preview enforces safeguards and reload recovers the original purge receipt by GET', async ({ page }) => {
  const state = await fixture(page);
  await page.getByRole('link', { name: 'ООО «Вектор»', exact: true }).click();
  const openPurge = page.getByRole('link', { name: 'Удалить организацию', exact: true });
  await openPurge.focus();
  await page.keyboard.press('Enter');
  const heading = page.getByRole('heading', { name: 'Полное удаление организации' });
  await expect(heading).toBeFocused();
  await expect(page).toHaveURL(/org=3&view=history.*#org-purge-heading$/u);
  await expect(page.getByRole('link', { name: 'Журнал и операции' })).toHaveAttribute('aria-current', 'page');
  await page.reload();
  await expect(heading).toBeFocused();
  expect(state.requests.filter(({ method }) => method !== 'GET')).toEqual([]);
  await showPurge(page);
  await expect(page.getByText('Команда полного удаления недоступна в этом контуре.').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Удалить полностью' })).toHaveCount(0);
  const close = () => page.getByRole('button', { name: 'Закрыть просмотр' }).click();
  const reopen = () => page.getByRole('button', { name: 'Посмотреть состав удаления' }).click();
  state.blocked = state.execution = true;
  await close();
  await expect(page.getByRole('button', { name: 'Посмотреть состав удаления' })).toBeFocused();
  await reopen();
  await expect(page.getByText('Аккаунт защищён настройками доступа')).toBeVisible();
  await expect(page.getByText(/Удаление пока заблокировано/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Удалить полностью' })).toHaveCount(0);
  state.blocked = false;
  state.stale = true;
  await close();
  await reopen();
  const code = page.getByRole('textbox', { name: 'Код организации' });
  const ack = page.getByRole('checkbox', { name: /Подтверждаю полное удаление/ });
  const send = page.getByRole('button', { name: 'Удалить полностью' });
  await code.fill('vector ');
  await ack.check();
  await send.click();
  await expect(page.getByText(/Введите точный код/)).toBeVisible();
  expect(state.posts).toHaveLength(0);
  await code.fill('vector');
  await send.click();
  await expect(page.getByText(/Состав удаления изменился/)).toBeVisible();
  await page.getByRole('button', { name: 'Обновить состав удаления' }).click();
  await expect(code).toHaveValue('');
  await expect(ack).not.toBeChecked();
  state.receiptMode = 'down';
  await code.fill('vector');
  await ack.check();
  await send.click();
  await expect(page.getByRole('button', { name: 'Проверить результат удаления' })).toBeVisible();
  const original = state.posts.at(-1);
  expect(original).toEqual({ confirmation_code: 'vector', preview_fingerprint: 'b'.repeat(64),
    operation_id: expect.any(String), acknowledge_irreversible: true });
  expect(original.operation_id).not.toBe(state.posts[0].operation_id);
  await page.reload();
  const check = page.getByRole('button', { name: 'Проверить результат удаления' });
  await expect(check).toBeVisible();
  state.receiptMode = 'wrong';
  await check.click();
  await expect(page.getByText(/Исход удаления пока неизвестен/)).toBeVisible();
  state.receiptMode = 'exact';
  await check.click();
  await expect(page.getByText(/подтверждено квитанцией/)).toBeVisible();
  expect(state.posts).toHaveLength(2);
  expect(state.requests.filter(({ method, pathname }) => method === 'GET' &&
    pathname.endsWith('/purge/operations/' + original.operation_id))).toHaveLength(3);
  await expect(page.getByRole('link', { name: 'АНО «Линия»', exact: true })).toBeVisible();
});

test('organization administrators cannot open the platform history view', async ({ page }) => {
  const state = await fixture(page, { superadmin: false });
  await page.goto(preview.base + '/?screen=admin-organizations&org=3&view=history');
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  await expect(historyLink(page)).toHaveCount(0);
  expect(state.requests.some(({ pathname }) => pathname.endsWith('/history'))).toBe(false);
});

test('an absent receipt permits an explicit retry of the same confirmed command', async ({ page }) => {
  const state = await fixture(page);
  state.execution = state.dropWrite = true;
  await openHistory(page, 'ООО «Вектор»');
  await showPurge(page);
  await page.getByRole('textbox', { name: 'Код организации' }).fill('vector');
  await page.getByRole('checkbox', { name: /Подтверждаю полное удаление/ }).check();
  await page.getByRole('button', { name: 'Удалить полностью' }).click();
  await expect(page.getByText(/Квитанция пока отсутствует/)).toBeVisible();
  expect(state.posts).toHaveLength(1);
  const check = page.getByRole('button', { name: 'Проверить результат удаления' });
  state.execution = false;
  await page.reload();
  await check.click();
  await expect(page.getByText(/Повтор команды недоступен/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Повторить ту же команду' })).toBeHidden();
  expect(state.posts).toHaveLength(1);
  state.execution = true;
  await page.reload();
  await check.click();
  await page.getByRole('button', { name: 'Повторить ту же команду' }).click();
  await expect(page.getByText(/подтверждено квитанцией/)).toBeVisible();
  expect(state.posts).toEqual([state.posts[0], state.posts[0]]);
});

test('product and v1.6 comparison at 1440, 390 and 320 px', async ({ page, browser }) => {
  test.skip(!reference || !evidence, 'Visual comparison requires local reference and an evidence directory.');
  await mkdir(evidence, { recursive: true });
  const metrics = [];
  const measure = (target, selector) => target.locator(selector).evaluate((element) => ({
    viewport: innerWidth, document: document.documentElement.scrollWidth,
    headingWidth: element.getBoundingClientRect().width, color: getComputedStyle(element).color,
    font: getComputedStyle(element).fontFamily, fontSize: getComputedStyle(element).fontSize,
  }));
  const state = await fixture(page);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    const demo = await browser.newPage({ viewport: { width, height: 1000 }, locale: 'ru-RU' });
    for (const [key, id, label] of [['vector', 3, 'Активна'], ['liniya', 5, 'Неактивна']]) {
      await page.goto(preview.base + '/?screen=admin-organizations&org=' + id + '&view=history');
      await expect(page.getByText('Создана организация', { exact: true })).toBeVisible();
      await expect(badge(page)).toHaveText(label);
      await demo.goto(reference + '/v1.6/?screen=organization-history&org=' + key + '&view=screen');
      const title = demo.getByRole('heading', { name: 'Журнал организации' });
      await expect(title).toBeVisible();
      const product = await measure(page, '#org-history-heading');
      const prototype = await measure(demo, 'h2:has-text("Журнал организации")');
      expect(product.document).toBe(width);
      expect(product.font).toContain('Onest');
      metrics.push({ key, width, product, reference: prototype });
      await page.screenshot({ path: path.join(evidence, width + '-' + key + '-01-product.png'), fullPage: true });
      await demo.screenshot({ path: path.join(evidence, width + '-' + key + '-01-reference.png'), fullPage: true });
      const operation = page.getByRole('button', { name: id === 3 ? 'Деактивировать организацию' : 'Восстановить организацию' });
      await operation.focus();
      await page.keyboard.press('Enter');
      await expect(page.getByRole('dialog').getByRole('button', { name: 'Отмена' })).toBeFocused();
      await page.keyboard.press('Tab');
      const confirm = page.getByRole('dialog').getByRole('button', { name: id === 3 ? 'Деактивировать' : 'Восстановить' });
      await expect(confirm).toBeFocused();
      expect(await confirm.evaluate((el) => getComputedStyle(el).outlineStyle)).toBe('solid');
      await demo.locator('[data-act="org-lifecycle-open"]').click();
      await page.screenshot({ path: path.join(evidence, width + '-' + key + '-02-product.png'), fullPage: true });
      await demo.screenshot({ path: path.join(evidence, width + '-' + key + '-02-reference.png'), fullPage: true });
      await page.keyboard.press('Escape');
      await expect(operation).toBeFocused();
      await showPurge(page);
      await expect(page.getByRole('heading', { name: 'Состав полного удаления' })).toBeFocused();
      expect((await measure(page, '[data-purge-preview-title]')).document).toBe(width);
      await demo.getByText('Полное удаление организации', { exact: true }).click();
      await demo.getByRole('button', { name: 'Посмотреть состав удаления' }).click();
      await page.screenshot({ path: path.join(evidence, width + '-' + key + '-03-product.png'), fullPage: true });
      await demo.screenshot({ path: path.join(evidence, width + '-' + key + '-03-reference.png'), fullPage: true });
      if (id === 3) {
        state.execution = state.blocked = true;
        const close = page.getByRole('button', { name: 'Закрыть просмотр' });
        const open = page.getByRole('button', { name: 'Посмотреть состав удаления' });
        await close.click();
        await open.click();
        await expect(page.getByText('Аккаунт защищён настройками доступа')).toBeVisible();
        expect((await measure(page, '[data-purge-preview-title]')).document).toBe(width);
        await page.screenshot({ path: path.join(evidence, width + '-' + key + '-04-product-blocked.png'), fullPage: true });
        state.blocked = false;
        await close.click();
        await open.click();
        await expect(page.getByRole('button', { name: 'Удалить полностью' })).toBeVisible();
        expect((await measure(page, '[data-purge-preview-title]')).document).toBe(width);
        await page.screenshot({ path: path.join(evidence, width + '-' + key + '-05-product-enabled.png'), fullPage: true });
        state.execution = false;
      }
    }
    await demo.close();
  }
  await writeFile(path.join(evidence, 'measurements.json'), JSON.stringify(metrics, null, 2) + '\n');
});
