import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18964 }); });
test.afterAll(async () => { await preview?.close(); });

const report = {
  id: 'r1', cycle_id: 'c1', owner_user_id: 18, status: 'ready',
  program_name: 'Программа во время прохождения', collection_closed_at: '2026-10-17T12:00:00Z',
  c67: {
    skills: [
      { skill_id: 'S1', skill_name: 'Взаимодействие', skill_description: 'Учитывать позицию собеседника.',
        competency_id: 'K1', competency_name: 'Коммуникация', outcome: 'full_score',
        score: { value: 0, numerator: 0, denominator: 1 },
        presentation: { label: 'Полный показатель по навыку', reasons: [] } },
      { skill_id: 'S2', skill_name: 'Решения', competency_id: 'K1', competency_name: 'Коммуникация',
        outcome: 'partial_score', score: { value: 1.5, numerator: 3, denominator: 2 },
        presentation: { label: 'Показатель по части состава навыка', reasons: [
          { message: 'Показатель рассчитан по доступной части состава навыка.' }] } },
      { skill_id: 'S3', skill_name: 'Диалог', competency_id: 'K1', competency_name: 'Коммуникация',
        outcome: 'result_without_score', score: null,
        presentation: { label: 'Есть наблюдения без общего показателя', reasons: [] } },
      { skill_id: 'S4', skill_name: 'Планирование', competency_id: 'K1', competency_name: 'Коммуникация',
        outcome: 'no_result', score: null,
        presentation: { label: 'По навыку пока нет обоснованного результата', reasons: [
          { message: 'Для этого навыка не получено достаточно подтверждённых оснований.' }] } },
    ],
    competencies: [{ competency_id: 'K1', competency_name: 'Коммуникация', skill_ids: ['S1', 'S2', 'S3', 'S4'] }],
    collection: { closed_at: '2026-10-17T12:00:00Z' }, coverage: {}, reliability: { status: 'not_verified' },
    limitations: ['Оценка относится к указанным ситуациям.'],
    descriptive: { status: 'ready', summary: ['Участник уточнил условие перед решением.'], claims: [
      { kind: 'observation', skill_ids: ['S1'], text: 'Участник уточнил условие перед решением.', limitations: [] },
      { kind: 'explanation', skill_ids: ['S1'], text: 'Вывод основан на сохранённом ответе.', limitations: [] },
      { kind: 'context', skill_ids: ['S1'], text: 'В известной работе есть обсуждение условий.', limitations: [] },
      { kind: 'quote', skill_ids: ['S1'], text: 'Я уточню условие.', limitations: [] },
      { kind: 'limitation', skill_ids: ['S1'], text: 'Наблюдение относится к одной ситуации.', limitations: [] },
    ] },
    partial_result: { plan_completed: true, is_incomplete: false, progress: { completed: 3, planned: 3 },
      messages: { title: 'Оценка завершена' }, limitation_reasons: [] },
  },
};

async function open(page, id, cycleId = 'c1') {
  await page.evaluate(({ id, cycleId }) => {
    window.__report04Open({ m8CycleId: cycleId, m8ReportId: id });
  }, { id, cycleId });
}

test('REPORT-04 saved report shows historical header and one selected skill panel', async ({ page }) => {
  await page.route('**/users/assessment/m8/reports/r1', (route) => route.fulfill({ json: report }));
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [] } }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    window.__report04Open = openReport;
  });
  await open(page, 'r1');
  await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
  await expect(page.locator('#m8-report-metadata')).toContainText('Программа во время прохождения');
  await expect(page.locator('#m8-report-metadata')).toContainText('17 октября 2026');
  await expect(page.locator('#m8-report-shell')).not.toContainText('Версия отчёта');
  await expect(page.locator('#m8-skill-detail')).toContainText('Участник уточнил условие');
  await page.locator('#m8-skill-detail summary').filter({ hasText: 'Почему сделан такой вывод' }).click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Я уточню условие.');
  await expect(page.locator('#m8-skill-detail')).toContainText('Наблюдение относится к одной ситуации.');
  const evidence = path.resolve('docs/evc/tasks/p4k-report-04/evidence');
  fs.mkdirSync(evidence, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: path.join(evidence, 'report04-evidence-1440.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.screenshot({ path: path.join(evidence, 'report04-evidence-390.png'), fullPage: true });
  await page.locator('#m8-skill-S2').click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Показатель по части состава навыка');
  await page.locator('#m8-skill-S3').click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Есть наблюдения без общего показателя');
  await page.locator('#m8-skill-S4').click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Числовой показатель не сформирован');
  await expect(page.locator('#m8-skill-detail')).not.toContainText('Я уточню условие.');
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    if (width !== 320) await page.screenshot({ path: path.join(evidence, `report04-${width}.png`), fullPage: true });
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await expect(page.locator('#m8-skill-S4')).toBeVisible();
});

test('REPORT-04 ignores a late response and late history for the old report', async ({ page }) => {
  let releaseOld;
  const newer = structuredClone(report);
  newer.id = 'r2'; newer.cycle_id = 'c2'; newer.program_name = 'Новая программа';
  await page.route('**/users/assessment/m8/reports/r1', async (route) => {
    await new Promise((resolve) => { releaseOld = resolve; });
    await route.fulfill({ json: report });
  });
  await page.route('**/users/assessment/m8/reports/r2', (route) => route.fulfill({ json: newer }));
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [] } }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    window.__report04Open = openReport;
  });
  await open(page, 'r1');
  await expect.poll(() => Boolean(releaseOld)).toBe(true);
  await open(page, 'r2', 'c2');
  await expect(page.locator('#m8-report-metadata')).toContainText('Новая программа');
  releaseOld();
  await expect(page.locator('#m8-report-metadata')).not.toContainText('Программа во время прохождения');
  await expect(page.locator('#report-download-button')).toHaveAttribute('data-m8-report-id', 'r2');
});

test('REPORT-04 missing historical title and failed explanation keep the saved facts', async ({ page }) => {
  const limited = structuredClone(report);
  limited.id = 'r3'; limited.program_name = null;
  limited.c67.descriptive = { status: 'failed', summary: [], claims: [] };
  limited.c67.skills = [limited.c67.skills[3]];
  const requests = [];
  page.on('request', (request) => requests.push(`${request.method()} ${request.url()}`));
  await page.route('**/users/assessment/m8/reports/r3', (route) => route.fulfill({ json: limited }));
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [] } }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    window.__report04Open = openReport;
  });
  await open(page, 'r3');
  await expect(page.locator('#m8-report-metadata')).toContainText('Программа оценки не указана');
  await expect(page.locator('#m8-report-summary')).toContainText('Пояснение временно недоступно');
  await expect(page.locator('#m8-skill-detail')).toContainText('По навыку пока нет обоснованного результата');
  await open(page, 'r3');
  await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
  expect(requests.filter((value) => /\bPOST\b.*(m6|llm|generate)/i.test(value))).toEqual([]);
});
