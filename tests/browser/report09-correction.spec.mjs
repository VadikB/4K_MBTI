import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18969 }); });
test.afterAll(async () => { await preview?.close(); });

const base = {
  id: 'r-old', cycle_id: 'c9', owner_user_id: 18, status: 'ready',
  program_name: 'Синтетическая программа', collection_closed_at: '2026-11-15T12:00:00Z',
  c67: {
    skills: [{ skill_id: 'S1', skill_name: 'Взаимодействие', competency_id: 'K1',
      competency_name: 'Коммуникация', outcome: 'full_score',
      score: { value: 1, numerator: 1, denominator: 1 },
      presentation: { label: 'Полный показатель', reasons: [] } }],
    competencies: [{ competency_id: 'K1', competency_name: 'Коммуникация', skill_ids: ['S1'] }],
    collection: { closed_at: '2026-11-15T12:00:00Z' }, coverage: {},
    reliability: { status: 'not_verified' }, limitations: [],
    descriptive: { status: 'ready', summary: ['Сохранённый вывод.'], claims: [
      { kind: 'observation', skill_ids: ['S1'], text: 'Сохранённое наблюдение.', limitations: [] },
    ] },
    partial_result: { plan_completed: true, is_incomplete: false, progress: { completed: 1, planned: 1 },
      messages: { title: 'Оценка завершена' }, limitation_reasons: [] },
  },
};

const corrected = structuredClone(base);
corrected.id = 'r-new';
corrected.c67.skills[0].score = { value: 2, numerator: 2, denominator: 1 };
corrected.c67.descriptive.summary = ['Уточнённый вывод.'];
corrected.c67.descriptive.claims[0].text = 'Уточнённое наблюдение.';
corrected.correction = { created_at: '2026-11-17T10:00:00Z', reason: 'Исправлено основание расчёта.', changes: [
  { skill_id: 'S1', skill_name: 'Взаимодействие', field: 'score',
    before: { value: 1, numerator: 1, denominator: 1 }, after: { value: 2, numerator: 2, denominator: 1 } },
  { skill_id: null, skill_name: null, field: 'summary',
    before: ['Сохранённый вывод.'], after: ['Уточнённый вывод.'] },
  { skill_id: 'S1', skill_name: 'Взаимодействие', field: 'explanation',
    before: [{ text: 'Сохранённое наблюдение.' }], after: [{ text: 'Уточнённое наблюдение.' }] },
] };

test('REPORT-09 keeps old view stable, offers current and shows changed places at 1440/390', async ({ page }) => {
  let current = 'r-old';
  await page.route('**/users/assessment/m8/reports/r-old', (route) => route.fulfill({ json: base }));
  await page.route('**/users/assessment/m8/reports/r-new', (route) => route.fulfill({ json: corrected }));
  await page.route('**/users/assessment/m8/cycles/c9/reports/latest', (route) => route.fulfill({ json: { id: current } }));
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [] } }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    window.__report09Open = openReport;
  });
  await page.evaluate(() => window.__report09Open({ m8CycleId: 'c9', m8ReportId: 'r-old' }));
  await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
  await expect(page.locator('#m8-report-summary')).toContainText('Сохранённый вывод.');
  current = 'r-new';
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.locator('#m8-report-update')).toContainText('Открыть актуальный отчёт');
  await expect(page.locator('#m8-report-summary')).toContainText('Сохранённый вывод.');
  await page.locator('#m8-report-update button').click();
  await expect(page.locator('#m8-report-summary')).toContainText('Уточнённый вывод.');
  await expect(page.locator('#m8-report-correction')).toContainText('Исправлено основание расчёта.');
  await page.locator('#m8-report-correction summary').click();
  await expect(page.locator('#m8-report-correction')).toContainText('Сохранённое наблюдение.');
  await expect(page.locator('#m8-report-correction')).toContainText('Уточнённое наблюдение.');
  await expect(page.locator('#m8-report-correction')).not.toContainText('r-old');
  const evidence = path.resolve('docs/evc/tasks/p4k-report-09/evidence');
  fs.mkdirSync(evidence, { recursive: true });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    const pair = page.locator('.m8-correction-pair').first();
    const columns = await pair.evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(' ').length);
    expect(columns).toBe(width === 390 ? 1 : 2);
    await page.screenshot({ path: path.join(evidence, `correction-${width}.png`), fullPage: true });
  }
});
