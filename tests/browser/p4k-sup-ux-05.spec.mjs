import { readFile } from 'node:fs/promises';
import { test, expect } from '@playwright/test';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const reference = 'P4K-AB0123456789CD0123456789';
const endpoint = '/users/admin/support/preparation';
const release = (await readFile(new URL('../../web/js/config.js', import.meta.url), 'utf8'))
  .match(/APP_RELEASE = "([^"]+)";/)?.[1];
if (!release) throw new Error('web/js/config.js must define APP_RELEASE');
const failure = {
  reference, organization_id: 3, assignment_id: 41, previous_position: 1, state: 'admission_denied', operation_status: 'failed',
  source: 'product_cycle_preparation_operations', stage_source: 'preparation_observations', stage: 'checking',
  stage_label: 'Проверяем материалы ситуации', started_at: '2026-11-21T07:14:00+00:00',
  stage_at: '2026-11-21T07:15:00+00:00', last_confirmed_at: '2026-11-21T07:21:00+00:00',
  read_at: '2026-11-21T07:22:00+00:00', failure_class: 'ASSESSMENT_AS_NOT_ADMITTED', result_confirmed_at: null,
};

let preview;
test.beforeAll(async () => {
  preview = await startAdminProgramPreview({ port: 18978 });
});
test.afterAll(async () => { await preview?.close(); });

for (const width of [1440, 390, 320]) {
  test('UX-05 case queue, stale read and handoff at ' + width + 'px', async ({ page, context }, info) => {
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const packet = [
      'Подготовка следующей ситуации',
      'Контур: local · ' + preview.base,
      'Версия продукта при чтении: ' + release,
      'Организация: #3 · ' + preview.base + '/?screen=admin-organizations&org=3',
      'Поколение назначения: #41',
      'Номер подготовки: ' + reference,
      'Последний этап: Проверяем материалы ситуации',
      'Время подтверждённого факта: 2026-11-21T07:21:00+00:00',
      'Класс отказа: ASSESSMENT_AS_NOT_ADMITTED',
    ].join('\n');
    const reads = [], errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let outcome = 'failure';
    await page.route('**' + endpoint + '**', route => {
      const request = route.request();
      const url = new URL(request.url());
      reads.push({ method: request.method(), pathname: url.pathname, organization: url.searchParams.get('organization_id') });
      if (url.pathname === endpoint) return route.fulfill({ json: { items: [failure], next_before: null } });
      expect(url.pathname).toBe(endpoint + '/' + reference);
      if (outcome === 'lost') return route.abort('failed');
      const detail = outcome === 'confirmed' ? { ...failure, state: 'result_confirmed',
        result_confirmed_at: '2026-11-21T07:26:00+00:00', last_confirmed_at: '2026-11-21T07:26:00+00:00',
        result_source: 'm7_route_assignments' } : failure;
      return route.fulfill({ json: { ...detail, handoff_text: packet } });
    });
    const root = page.locator('#platform-problems');
    const screenshot = async (name) => {
      await page.evaluate(() => document.fonts.ready);
      const geometry = await root.evaluate(node => ({
        width: document.documentElement.scrollWidth,
        headingFont: getComputedStyle(node.querySelector('h1')).fontFamily,
        headingColor: getComputedStyle(node.querySelector('h1')).color,
      }));
      expect(geometry.width).toBeLessThanOrEqual(width);
      expect(geometry.headingFont).toContain('Onest');
      expect(geometry.headingColor).toBe('rgb(34, 44, 48)');
      await page.screenshot({ path: info.outputPath('product-' + name + '-' + width + '.png'), fullPage: true, scale: 'css' });
    };
    await page.goto(preview.base + '/demo/superadmin/confirmed/');
    await page.getByRole('link', { name: 'Проблемы', exact: true }).click();
    const row = root.getByRole('link', { name: 'Следующая ситуация не допущена' });
    await expect(row).toBeVisible();
    await expect(page.locator('.platform-navigation [aria-current="page"]')).toHaveText('Проблемы');
    await screenshot('problems');
    await row.focus();
    await page.keyboard.press('Enter');
    await expect(root.getByRole('heading', { name: 'Следующая ситуация не допущена' })).toBeVisible();
    await expect(root.locator('.support-grid h2')).toHaveText([
      'Наблюдаемое поведение', 'Сведения для поиска', 'Что видят в продукте', 'Ход операции',
    ]);
    await expect(root).toContainText(reference);
    await expect(root).toContainText('#41');
    await screenshot('problem');
    const check = root.getByRole('button', { name: 'Проверить состояние' });
    outcome = 'lost';
    await check.focus();
    await page.keyboard.press('Enter');
    await expect(root.getByRole('status')).toContainText('Показан последний подтверждённый факт');
    await expect(root).toContainText('Исход не подтверждён');
    await expect(root).toContainText('10:21');
    await expect(check).toBeFocused();
    await expect(check).toBeEnabled();
    await screenshot('unknown');
    outcome = 'failure';
    await check.click();
    await expect(root.getByRole('status')).toHaveText('Состояние исходной операции обновлено.');
    await root.getByRole('link', { name: 'Подготовить передачу' }).click();
    await expect(root.getByRole('heading', { name: 'Передача разработчику' })).toBeFocused();
    const copy = root.getByRole('button', { name: 'Скопировать сведения' });
    await copy.focus();
    await page.keyboard.press('Enter');
    await expect(root.getByRole('status').filter({ hasText: 'Сведения скопированы.' })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(packet);
    await expect(root.getByRole('button', { name: 'Отметить передачу' })).toHaveCount(0);
    await screenshot('handoff');
    await root.getByRole('link', { name: 'К карточке проблемы' }).click();
    outcome = 'confirmed';
    await check.click();
    await expect(root.getByRole('heading', { name: 'Следующая ситуация допущена' })).toBeVisible();
    await expect(root).toContainText('#41');
    await expect(root.locator('.support-grid section').first()).toContainText('10:26');
    await screenshot('confirmed');
    await root.getByRole('link', { name: 'К организации' }).click();
    await expect(page).toHaveURL(/org=3/);
    const organization = page.locator('[data-organization-id="3"]');
    await expect(organization.getByRole('link', { name: 'Обзор', exact: true })).toHaveAttribute('aria-current', 'page');
    await expect(organization.getByRole('heading', { name: 'Проблемы организации' })).toBeVisible();
    await expect(page.locator('#admin-organizations-subtitle')).toHaveText('Код организации · synthetic-adm-program');
    await page.goto(preview.base + '/?screen=admin-platform-problems');
    await expect(root.getByRole('heading', { name: 'Проблемы' })).toBeVisible();
    await root.getByLabel('Организация').fill('3');
    await root.getByRole('button', { name: 'Найти' }).click();
    await expect.poll(() => reads.at(-1)?.organization).toBe('3');
    await root.getByRole('searchbox').fill(reference.toLowerCase());
    await root.getByRole('button', { name: 'Найти' }).click();
    await expect(root.getByRole('heading', { name: 'Следующая ситуация допущена' })).toBeVisible();
    expect(reads.map(item => item.method)).toEqual(reads.map(() => 'GET'));
    expect(errors).toEqual([]);
  });
}

test('UX-05 organization administrator sees the same case number but cannot open the platform queue', async ({ page }, info) => {
  let called = false;
  await page.route('**' + endpoint + '**', route => { called = true; return route.abort('blockedbyclient'); });
  await page.route('**/users/admin/organizations', async route => {
    const response = await route.fetch();
    const body = await response.json();
    Object.assign(body.items[0].members[0], {
      has_password: true, assessment_assignments: ['synthetic-pilot-11'],
      assessment_stages: { 'synthetic-pilot-11': { assignment_id: 41, code: 'paused',
        preparation: { ...failure, kind: 'next', status: 'failed', freshness: 'confirmed' } } },
    });
    await route.fulfill({ response, json: body });
  });
  await page.goto(preview.base + '/demo/admin/confirmed/');
  const organization = page.locator('[data-organization-id="3"]');
  await organization.locator('.admin-organization-step[data-view="people"]').click();
  await organization.locator('[data-action="open-member-card"]').click();
  const dialog = page.locator('.org-admin-member-card');
  await expect(dialog.getByRole('button', { name: 'Проверить состояние', exact: true })).toBeVisible();
  await expect(dialog.locator('[data-card-case]')).toContainText(reference);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.screenshot({ path: info.outputPath('product-administrator-' + width + '.png'), fullPage: true, scale: 'css' });
  }
  await page.goto(preview.base + '/?screen=admin-platform-problems&issue=' + reference);
  await expect(page.locator('#platform-problems')).toBeHidden();
  await expect(page.getByRole('link', { name: 'Проблемы', exact: true })).toBeHidden();
  expect(called).toBe(false);
});
