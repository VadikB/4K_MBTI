import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { startReportsPreview } from '../../scripts/reports-ui-preview.mjs';
test.setTimeout(30000);

let preview;
const evidence = path.resolve('docs/evc/tasks/p4k-report-fix-02/evidence');
test.beforeAll(async () => { preview = await startReportsPreview({ port: 18973 }); await fs.mkdir(evidence, { recursive: true }); });
test.afterAll(async () => { await preview?.close(); });
async function openExample(page, key, standalone = false) {
  await page.goto(`${preview.base}/__reports/${key}`);
  let frame = page.frame({ name: 'report-product' });
  await expect(frame.locator('#m8-report-state')).toHaveText('Результат готов');
  if (standalone) { await page.goto(frame.url()); frame = page.mainFrame(); }
  return frame;
}
const assertFits = async (frame, width) => expect(await frame.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);

test('FIX-02 P01/P02: menu, saved scores, gaps, modes and keyboard detail on actual product build', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(preview.base + '/__reports/');
  await expect(page.getByRole('heading', { name: 'Локальный просмотр · вымышленные результаты' })).toBeVisible();
  await expect(page.locator('li a')).toHaveCount(6);
  let frame = await openExample(page, 'P01', true);
  await expect(frame.locator('#report-panel [data-app-header]')).toContainText('4К Ассистент');
  await expect(frame.locator('#report-panel')).not.toContainText('Результат оценки');
  await expect(frame.locator('.m8-radar-point')).toHaveCount(preview.payload.fixture.skills.length);
  await frame.locator('[data-chart-mode="outline"]').click();
  await expect(frame.locator('.m8-radar-fill')).toHaveCount(0);
  await frame.locator('[data-chart-mode="bars"]').click();
  await expect(frame.locator('.m8-score-bar')).toHaveCount(preview.payload.fixture.skills.length);
  await frame.locator('.m8-score-bar [data-m8-skill-id="K1.2"]').focus();
  await page.keyboard.press('Enter');
  await expect(frame.locator('#m8-skill-detail')).toBeFocused();
  await expect(frame.locator('#m8-skill-detail')).toContainText('2.25');
  await frame.locator('#m8-skill-detail summary').filter({ hasText: 'Почему сделан такой вывод' }).click();
  await expect(frame.locator('#m8-skill-detail blockquote')).toContainText('Синтетический пример текущей оценки');
  await frame.locator('[data-chart-mode="fill"]').click();
  await frame.locator('#m8-report-chart').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(evidence, 'single-1440.png') });
  frame = await openExample(page, 'P02', true);
  await expect(frame.locator('.m8-radar-point.is-partial')).toHaveCount(1);
  await expect(frame.locator('#m8-report-skills')).toContainText('Есть наблюдения без общего балла');
  await expect(frame.locator('#m8-report-skills')).toContainText('Недостаточно оснований');
  await expect(frame.locator('#m8-report-chart polygon.m8-radar-line')).toHaveCount(0);
  await expect(frame.locator('#m8-report-chart polyline.m8-radar-line')).toHaveCount(2);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(frame.locator('.m8-score-bar')).toHaveCount(preview.payload.fixture.skills.length);
  await frame.locator('#m8-report-tab-select').selectOption('K1');
  await expect(frame.locator('.m8-radar-key li')).toHaveCount(4);
  await expect(frame.locator('.m8-radar-line,.m8-radar-fill')).toHaveCount(0); // two numeric axes
  await assertFits(frame, 390);
  await page.setViewportSize({ width: 320, height: 844 });
  await frame.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await assertFits(frame, 320);
  await expect(frame.locator('#m8-report-tab-select')).toBeVisible();
});

test('FIX-02 P03/P04: two series, exact deltas, pair reload/back, partial basis and real PDF', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let frame = await openExample(page, 'P03', true);
  await expect(frame.locator('#m8-comparison-content')).toContainText('+0,50');
  await expect(frame.locator('.m8-series-previous.m8-radar-point')).toHaveCount(preview.payload.fixture.skills.length);
  await expect(frame.locator('.m8-series-previous.m8-radar-line')).toHaveCount(1);
  const rows = frame.locator('.m8-comparison-table tbody tr');
  await expect(rows.nth(0)).toContainText('1,75'); await expect(rows.nth(0)).toContainText('2,25');
  await expect(rows.nth(1)).toContainText('0,00'); await expect(rows.nth(2)).toContainText('-0,25');
  await frame.locator('[data-comparison-mode="outline"]').click();
  await expect(frame.locator('#m8-comparison-content .m8-radar-fill')).toHaveCount(0);
  await frame.locator('[data-comparison-mode="bars"]').click();
  await expect(frame.locator('.m8-comparison-scale')).toHaveCount(preview.payload.fixture.skills.length);
  await frame.locator('[data-comparison-mode="fill"]').click();
  await frame.locator('[data-compare-skill="K1.2"]').first().focus(); await page.keyboard.press('Enter');
  await expect(frame.locator('#m8-comparison-detail')).toBeFocused();
  const previousId = preview.payload.reports['normal-previous'].id;
  await page.reload();
  await expect(page.locator('#m8-comparison-detail')).toContainText('Передача смысла');
  expect(new URL(page.url()).searchParams.get('previous_report_id')).toBe(previousId);
  await page.locator('[data-compare-back]').click();
  await expect(page.locator('#m8-report-title')).toBeVisible();
  await expect(page.locator('#m8-comparison-select')).toHaveValue(previousId);
  await page.locator('#m8-comparison-open').click();
  await expect(page.locator('.m8-comparison-table')).toBeVisible();
  await page.locator('.m8-comparison-chart').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(evidence, 'comparison-1440.png') });
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Скачать сравнение PDF' }).click();
  expect((await fs.readFile(await (await download).path())).subarray(0, 5).toString()).toBe('%PDF-');
  await page.setViewportSize({ width: 390, height: 844 });
  frame = await openExample(page, 'P04', true);
  await expect(frame.locator('.m8-comparison-scale')).toHaveCount(preview.payload.fixture.skills.length);
  await expect(frame.locator('#m8-comparison-detail')).toContainText('+0,25');
  for (const side of ['previous', 'current']) {
    await expect(frame.locator(`[data-result-side="${side}"]`)).toContainText('Результат по части навыка');
    await expect(frame.locator(`[data-result-side="${side}"]`)).toContainText('Оценена часть обязательных проявлений');
    await frame.locator(`[data-result-side="${side}"] summary`).click();
    await expect(frame.locator(`[data-result-side="${side}"] blockquote`)).toContainText(side === 'previous' ? 'предыдущей' : 'текущей');
  }
  await frame.locator('select[aria-label="Направление сравнения"]').selectOption('K1');
  await expect(frame.locator('.m8-series-previous.is-partial')).toHaveCount(1);
  await assertFits(frame, 390);
  await frame.locator('.m8-comparison-chart').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(evidence, 'partial-390.png') });
  await page.setViewportSize({ width: 320, height: 844 });
  await frame.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await assertFits(frame, 320);
});

test('FIX-02 P05/P06: mixed and roles, stale response, read failure, four PDF entrypoints and retry', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let frame = await openExample(page, 'P05');
  await expect(frame.locator('.m8-comparison-table tbody tr').nth(0)).toContainText('+0,50');
  await expect(frame.locator('.m8-comparison-table tbody tr').nth(1)).toContainText('состав показателя изменился');
  await expect(frame.locator('.m8-comparison-table tbody tr').nth(2)).toContainText('Полный и частичный');
  await frame.locator('select[aria-label="Направление сравнения"]').selectOption('K1');
  await expect(frame.locator('#m8-comparison-content .m8-radar-line,#m8-comparison-content .m8-radar-fill')).toHaveCount(0); // only one comparable axis
  await frame.locator('.m8-comparison-chart').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(evidence, 'mixed-390.png') });
  await frame.locator('#m8-comparison-select').selectOption(preview.payload.reports['role-previous'].id);
  await expect(frame.locator('#m8-comparison-content')).toContainText('Числовое сравнение недоступно');
  await expect(frame.locator('#m8-comparison-content')).toContainText('Роли в оценках различаются');
  await expect(frame.locator('#m8-comparison-content .m8-radar-line,#m8-comparison-content .m8-radar-fill')).toHaveCount(0);
  await frame.locator('#m8-comparison-select').selectOption(preview.payload.reports['mixed-previous'].id);
  await expect(frame.locator('#m8-comparison-content')).toContainText('+0,50');
  // Hold the first pair response, select a new pair and then release the old one.
  let release, staleDone = false;
  await page.route('**/comparison?*', async (route) => {
    if (new URL(route.request().url()).searchParams.get('previous_report_id') === preview.payload.reports['role-previous'].id) {
      const result = await route.fetch(); await new Promise((resolve) => { release = resolve; }); await route.fulfill({ response: result }); staleDone = true;
    } else await route.continue();
  });
  await frame.locator('#m8-comparison-select').selectOption(preview.payload.reports['role-previous'].id);
  await expect.poll(() => Boolean(release)).toBe(true);
  await frame.locator('#m8-comparison-select').selectOption(preview.payload.reports['mixed-previous'].id);
  await expect(frame.locator('#m8-comparison-content')).toContainText('+0,50');
  release(); await expect.poll(() => staleDone).toBe(true); await page.unroute('**/comparison?*');
  await expect(frame.locator('#m8-comparison-content')).not.toContainText('Роли в оценках различаются');
  frame = await openExample(page, 'P06');
  await expect(frame.locator('#m8-skill-detail')).toContainText('Пример A: уточнил срок');
  await page.getByRole('link', { name: 'История оценок', exact: true }).click();
  await frame.locator(`[data-cycle-id="${preview.payload.reports['error-b'].cycle_id}"] .cycle-report-open`).click();
  await expect(frame.locator('#m8-report-state')).toContainText('Не удалось открыть результат');
  await expect(frame.locator('#m8-report-shell')).not.toContainText('Пример A: уточнил срок');
  await expect(frame.locator('#m8-report-detail')).toBeEmpty();
  await Promise.all([page.waitForResponse('**/__reports/control'), page.getByRole('button', { name: 'Успешный повтор' }).click()]);
  await expect(page.locator('#control-status')).toContainText('Режим обновлён');
  await frame.getByRole('button', { name: 'Повторить', exact: true }).click();
  await expect(frame.locator('#m8-skill-detail')).toContainText('Пример B: согласовал условие');
  for (const place of ['report', 'history', 'admin', 'comparison']) {
    await Promise.all([page.waitForResponse('**/__reports/control'), page.locator('#pdf-failure').check()]);
    await expect(page.locator('#control-status')).toContainText('Режим обновлён');
    if (place === 'history') await page.getByRole('link', { name: 'История оценок', exact: true }).click();
    if (place === 'admin') await page.getByRole('link', { name: 'Список администратора' }).click();
    if (place === 'comparison') {
      await page.getByRole('link', { name: 'Открыть отчёт B' }).click();
      await expect(frame.locator('#m8-comparison-open')).toBeEnabled();
      await frame.locator('#m8-comparison-open').click();
      await expect(frame.locator('.m8-comparison-table')).toBeVisible();
    }
    const button = place === 'report' ? frame.locator('#report-download-button')
      : place === 'history' ? frame.locator('.cycle-report-pdf').first()
        : place === 'admin' ? frame.locator('.admin-report-download-action').getByRole('button', { name: 'PDF', exact: true }).first()
          : frame.getByRole('button', { name: 'Скачать сравнение PDF' });
    await button.click();
    await expect(frame.locator('.report-pdf-status').filter({ hasText: 'Попробуйте ещё раз' }).first()).toBeVisible();
    await Promise.all([page.waitForResponse('**/__reports/control'), page.getByRole('button', { name: 'Успешный повтор' }).click()]);
    await expect(page.locator('#control-status')).toContainText('Режим обновлён');
    const download = page.waitForEvent('download');
    await button.focus(); await page.keyboard.press('Enter');
    expect((await fs.readFile(await (await download).path())).subarray(0, 5).toString()).toBe('%PDF-');
  }
});
