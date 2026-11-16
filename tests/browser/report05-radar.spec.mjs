import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18965 }); });
test.afterAll(async () => { await preview?.close(); });

const skills = [
  ['S9', 'Понимание интересов собеседника в сложном разговоре', 'K1', 'Коммуникация', 0, 'full_score'],
  ['S2', 'Точное выражение мысли', 'K1', 'Коммуникация', 1.75, 'partial_score'],
  ['S7', 'Слушать и уточнять', 'K1', 'Коммуникация', null, 'result_without_score'],
  ['S4', 'Работа с аргументами', 'K2', 'Критическое мышление', 2.25, 'full_score'],
  ['S1', 'Проверка предположений', 'K2', 'Критическое мышление', null, 'no_result'],
  ['S8', 'Поиск новых подходов', 'K3', 'Креативность', null, 'no_result'],
  ['S3', 'Варианты решений', 'K3', 'Креативность', 3, 'full_score'],
  ['S6', 'Совместное решение', 'K4', 'Кооперация', 2, 'full_score'],
].map(([skill_id, skill_name, competency_id, competency_name, value, outcome]) => ({
  skill_id, skill_name, competency_id, competency_name, outcome,
  score: value == null ? null : { value },
  presentation: { label: outcome === 'partial_score' ? 'Показатель по части состава навыка' :
    value == null ? 'Нет общего показателя' : 'Полный показатель',
    reasons: outcome === 'partial_score' ? [{ message: 'Оценена часть обязательного состава.' }] : [] },
}));

const report = {
  id: 'r05', cycle_id: 'c05', owner_user_id: 18, status: 'ready',
  program_name: 'Сохранённая программа', collection_closed_at: '2026-11-15T12:00:00Z',
  c67: {
    skills,
    competencies: ['K1', 'K2', 'K3', 'K4'].map((id) => ({
      competency_id: id, competency_name: skills.find((skill) => skill.competency_id === id).competency_name,
      skill_ids: skills.filter((skill) => skill.competency_id === id).map((skill) => skill.skill_id),
    })),
    collection: { closed_at: '2026-11-15T12:00:00Z' }, coverage: {},
    reliability: { status: 'not_verified' }, limitations: [],
    descriptive: { status: 'ready', summary: ['Сохранённый результат.'], claims: [
      { kind: 'observation', skill_ids: ['S2'], text: 'Уточнил смысл запроса.', limitations: [] },
      { kind: 'quote', skill_ids: ['S2'], text: 'Я уточню задачу.', limitations: [] },
    ] },
    partial_result: { plan_completed: true, is_incomplete: false, progress: { completed: 3, planned: 3 },
      messages: { title: 'Оценка завершена' }, limitation_reasons: [] },
  },
};

async function openReport(page, payload = report) {
  await page.route(`**/users/assessment/m8/reports/${payload.id}`, (route) => route.fulfill({ json: payload }));
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [] } }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport: open }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    window.__report05Open = open;
  });
  await page.evaluate(({ id, cycleId }) => window.__report05Open({ m8CycleId: cycleId, m8ReportId: id }),
    { id: payload.id, cycleId: payload.cycle_id });
  await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
}

test('REPORT-05 modes and selection use one saved skill and adjacent detail', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const writes = [];
  page.on('request', (request) => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url()); });
  await openReport(page);
  await expect(page.locator('.m8-radar-point')).toHaveCount(5);
  await expect(page.locator('.m8-radar-fill')).toHaveCount(1);
  await page.locator('[data-chart-mode="outline"]').click();
  await expect(page.locator('.m8-radar-fill')).toHaveCount(0);
  await page.locator('[data-chart-mode="bars"]').click();
  await expect(page.locator('.m8-score-bar')).toHaveCount(skills.length);
  await expect(page.locator('.m8-score-bars')).toContainText('1.75');
  await page.locator('.m8-score-bar button[data-m8-skill-id="S2"]').click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Точное выражение мысли');
  await expect(page.locator('#m8-report-detail')).toContainText('общий уровень навыка не присваивается');
  await expect(page.locator('#m8-skill-detail')).toContainText('Оценена часть обязательного состава.');
  await expect(page.locator('#m8-skill-detail')).toBeFocused();
  const chart = await page.locator('#m8-report-chart').boundingBox();
  const detail = await page.locator('#m8-skill-detail').boundingBox();
  expect(detail.x).toBeGreaterThan(chart.x + chart.width - 4);
  await page.locator('#m8-skill-detail summary').filter({ hasText: 'Почему сделан такой вывод' }).click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Я уточню задачу.');
  await page.locator('.m8-skill-back').click();
  await expect(page.locator('#m8-skill-S2')).toBeFocused();
  const evidence = path.resolve('docs/evc/tasks/p4k-report-05/evidence');
  fs.mkdirSync(evidence, { recursive: true });
  await page.locator('[data-chart-mode="fill"]').click();
  await page.locator('a[data-m8-skill-id="S4"] .m8-radar-label').click({ timeout: 5000 });
  await expect(page.locator('#m8-skill-detail')).toContainText('Работа с аргументами');
  await page.locator('.m8-radar-point.is-partial').click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Точное выражение мысли');
  await expect(page.locator('.m8-radar-selection')).toHaveCount(1);
  expect(writes).toEqual([]);
  await page.screenshot({ path: path.join(evidence, 'radar-1440.png'), fullPage: true });
});

test('REPORT-05 mobile overview, directions, resize and keyboard keep every skill', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openReport(page);
  await expect(page.locator('.m8-score-bar')).toHaveCount(skills.length);
  await expect(page.locator('[data-chart-mode="bars"]')).toHaveAttribute('aria-pressed', 'true');
  await page.locator('#m8-report-tab-select').selectOption('K1');
  await expect(page.locator('.m8-radar-key li')).toHaveCount(3);
  await page.locator('.m8-radar-key a[data-m8-skill-id="S2"]').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#m8-skill-detail')).toContainText('Точное выражение мысли');
  await expect(page.locator('#m8-skill-detail')).toBeFocused();
  const chart = await page.locator('#m8-report-chart').boundingBox();
  const detail = await page.locator('#m8-skill-detail').boundingBox();
  expect(detail.y).toBeGreaterThan(chart.y + chart.height - 4);
  const evidence = path.resolve('docs/evc/tasks/p4k-report-05/evidence');
  fs.mkdirSync(evidence, { recursive: true });
  await page.screenshot({ path: path.join(evidence, 'radar-390.png'), fullPage: true });
  await page.locator('#m8-report-tab-select').selectOption('all');
  await page.setViewportSize({ width: 320, height: 720 });
  await expect(page.locator('.m8-score-bar')).toHaveCount(skills.length);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(321);
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(321);
  await expect(page.locator('#m8-report-tab-select')).toBeVisible();
  await expect(page.locator('.m8-skill-back')).toBeVisible();
});

test('REPORT-05 all missing and one score retain explanations without synthetic geometry', async ({ page }) => {
  const absent = structuredClone(report);
  absent.id = 'r05-empty';
  absent.c67.skills.forEach((skill) => { skill.score = null; });
  await openReport(page, absent);
  await expect(page.locator('.m8-radar-fill, .m8-radar-line')).toHaveCount(0);
  await expect(page.locator('#m8-report-chart')).toContainText('Числовых показателей нет');
  await expect(page.locator('.m8-skill-row')).toHaveCount(skills.length);
  const single = structuredClone(report);
  single.id = 'r05-single';
  single.c67.skills.forEach((skill) => { skill.score = skill.skill_id === 'S9' ? { value: 0 } : null; });
  await openReport(page, single);
  await expect(page.locator('.m8-radar-line, .m8-radar-fill')).toHaveCount(0);
  await expect(page.locator('.m8-radar-point')).toHaveCount(1);
  await expect(page.locator('.m8-skill-row')).toHaveCount(skills.length);
});
