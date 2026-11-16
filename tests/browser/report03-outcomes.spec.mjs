import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18963 }); });
test.afterAll(async () => { await preview?.close(); });

const base = {
  id: 'r1', cycle_id: 'c1', owner_user_id: 18, revision_no: 1,
  created_at: '2026-11-15T12:00:00Z', program_name: 'Короткая программа',
  c67: {
    skills: [{ skill_id: 'S1', skill_name: 'Взаимодействие', competency_id: 'K1',
      competency_name: 'Коммуникация', outcome: 'full_score',
      score: { value: 0, numerator: 0, denominator: 1 },
      presentation: { label: 'Полный показатель по навыку', reasons: [
        { code: 'plan_scope', message: 'Программа охватывала только часть состава этого навыка.' }] } }],
    competencies: [{ competency_id: 'K1', competency_name: 'Коммуникация', skill_ids: ['S1'] }],
    coverage: {}, reliability: { status: 'not_verified' }, limitations: [],
    descriptive: { status: 'historical', summary: [], claims: [] },
    partial_result: { plan_completed: true, is_incomplete: false, progress: { completed: 3, planned: 3 },
      messages: { title: 'Оценка завершена' }, limitation_reasons: [
        { code: 'plan_scope', message: 'Принятый план покрывал часть целевой области.' }] },
  },
};

test('REPORT-03 completed short program shows scope and numeric zero without machine codes', async ({ page }) => {
  await page.route('**/users/assessment/m8/reports/r1', (route) => route.fulfill({ json: base }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    openReport({ m8CycleId: 'c1', m8ReportId: 'r1' });
  });
  await expect(page.locator('#m8-report-partial')).toContainText('Оценка завершена');
  await expect(page.locator('#m8-report-partial')).toHaveClass(/is-complete-scope/);
  await expect(page.locator('#m8-report-partial')).not.toContainText('не полностью');
  await expect(page.locator('#m8-report-skills')).toContainText('Программа охватывала только часть состава этого навыка.');
  await expect(page.locator('#m8-report-skills')).toContainText('0');
  await expect(page.locator('#m8-report-shell')).not.toContainText('plan_scope');
  const evidence = path.resolve('docs/evc/tasks/p4k-report-03/evidence');
  fs.mkdirSync(evidence, { recursive: true });
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(width + 1);
    if (width !== 320) await page.screenshot({ path: path.join(evidence, `report-scope-${width}.png`), fullPage: true });
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await expect(page.locator('#m8-report-partial')).toContainText('Оценка завершена');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
});

test('REPORT-03 incomplete plan preserves scored and unscored skill outcomes', async ({ page }) => {
  const report = structuredClone(base);
  report.id = 'r2';
  report.c67.partial_result = { plan_completed: false, is_incomplete: true,
    progress: { completed: 2, planned: 3 }, messages: { title: 'Оценка завершена не полностью' },
    limitation_reasons: [{ code: 'collection_incomplete', message: 'Не все ситуации плана были завершены.' }] };
  report.c67.skills = [
    { ...report.c67.skills[0], skill_id: 'S1', outcome: 'full_score', score: { value: 2, numerator: 2, denominator: 1 },
      presentation: { label: 'Полный показатель по навыку', reasons: [] } },
    { ...report.c67.skills[0], skill_id: 'S2', skill_name: 'Решения', outcome: 'partial_score',
      score: { value: 1.5, numerator: 3, denominator: 2 },
      presentation: { label: 'Показатель по части состава навыка', reasons: [
        { code: 'partial_composition', message: 'Показатель рассчитан по доступной части состава навыка.' }] } },
    { ...report.c67.skills[0], skill_id: 'S3', skill_name: 'Диалог', outcome: 'result_without_score', score: null,
      presentation: { label: 'Есть наблюдения без общего показателя', reasons: [
        { code: 'numeric_not_admissible', message: 'Действия удалось наблюдать, но общего числа нет.' }] } },
    { ...report.c67.skills[0], skill_id: 'S4', skill_name: 'Планирование', outcome: 'no_result', score: null,
      presentation: { label: 'По навыку пока нет обоснованного результата', reasons: [
        { code: 'technical_failure', message: 'Часть данных не обработана из-за технической ошибки.' }] } },
  ];
  report.c67.competencies[0].skill_ids = report.c67.skills.map((skill) => skill.skill_id);
  await page.route('**/users/assessment/m8/reports/r2', (route) => route.fulfill({ json: report }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    openReport({ m8CycleId: 'c1', m8ReportId: 'r2' });
  });
  await expect(page.locator('#m8-report-partial')).toContainText('Оценка завершена не полностью');
  await expect(page.locator('#m8-report-skills')).toContainText('Полный показатель по навыку');
  await expect(page.locator('#m8-report-skills')).toContainText('1.5');
  await expect(page.locator('#m8-report-skills')).toContainText('Есть наблюдения без общего показателя');
  await expect(page.locator('#m8-report-skills')).toContainText('Часть данных не обработана из-за технической ошибки.');
  await expect(page.locator('#m8-report-shell')).not.toContainText('technical_failure');
  await expect(page.locator('#m8-report-shell')).not.toContainText('numeric_not_admissible');
});
