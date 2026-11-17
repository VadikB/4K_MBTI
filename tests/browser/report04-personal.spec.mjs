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
  await expect(page.locator('#m8-report-shell')).not.toContainText(/Skill Level|Score|Results|Report|Cycle|full_score|partial_score|Полнота отдельно не указана/);
});

test('REPORT-04 ignores a late response and late history for the old report', async ({ page }) => {
  let releaseOld;
  const newer = secondReport();
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
  await expect(page.locator('#m8-report-metadata')).toContainText('Контрольная программа Б');
  const late = page.waitForResponse('**/users/assessment/m8/reports/r1');
  releaseOld();
  await late;
  await page.setViewportSize({ width: 390, height: 900 });
  await expect(page.locator('#m8-report-detail')).toContainText('Уникальный навык Б');
  await expect(page.locator('#report-panel')).not.toContainText('Взаимодействие');
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

const fixEvidence = path.resolve('docs/evc/tasks/p4k-report-fix-01/evidence');
const secondReport = () => {
  const newer = structuredClone(report);
  newer.id = 'r2'; newer.cycle_id = 'c2'; newer.program_name = 'Контрольная программа Б';
  newer.c67.skills = [{ skill_id: 'B1', skill_name: 'Уникальный навык Б', competency_id: 'K1',
    competency_name: 'Группа Б', outcome: 'full_score', completeness: 'full',
    score: { value: 2.25, numerator: 9, denominator: 4 },
    presentation: { label: 'Полный показатель по навыку', reasons: [] } }];
  newer.c67.descriptive = { status: 'ready', summary: ['Контрольное резюме Б'], claims: [] };
  return newer;
};
const noOldResult = async (page) => {
  const panel = page.locator('#report-panel');
  for (const value of ['Взаимодействие', 'Учитывать позицию', 'Я уточню условие.',
    'Участник уточнил условие', 'Точное значение: 0', 'Программа во время прохождения']) {
    await expect(panel).not.toContainText(value);
  }
  for (const id of ['m8-report-detail', 'm8-report-chart', 'm8-report-skills', 'm8-report-summary',
    'm8-report-partial', 'm8-report-correction', 'm8-report-update', 'report-download-status']) {
    await expect(page.locator(`#${id}`)).toBeEmpty();
  }
  await expect(page.locator('#report-download-button')).toBeDisabled();
};

async function sourceReportApp(page) {
  await page.route('**/web/dist/main.js*', (route) => route.fulfill({ body: '', contentType: 'application/javascript' }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, reportModule, history] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'), import('/web/js/screens/reports.js'),
    ]);
    state.pendingUser = { id: 18 }; state.isAdmin = false;
    window.__report04Open = reportModule.openReport;
    window.__fixHistory = history.openReports;
    document.getElementById('report-back-button').addEventListener('click', reportModule.handleReportBack);
  });
}

test('FIX-01 AC01 A to history to B503 clears all dependent content and retries B', async ({ page }) => {
  const original = JSON.stringify(report);
  const newer = secondReport();
  let failure = true;
  const seen = [];
  page.on('request', (r) => { if (r.url().includes('/users/')) seen.push(r.method()); });
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [report, newer].map((r) => ({
    report_id: r.id, cycle_id: r.cycle_id, status: 'report_ready', program_name: r.program_name,
    collection_closed_at: r.collection_closed_at,
  })) } }));
  await page.route('**/users/assessment/m8/reports/r1', (route) => route.fulfill({ json: report }));
  await page.route('**/users/assessment/m8/reports/r2', (route) => failure
    ? route.fulfill({ status: 503, json: { detail: 'Synthetic render unavailable' } }) : route.fulfill({ json: newer }));
  await sourceReportApp(page);
  await page.evaluate(() => window.__fixHistory());
  await page.locator('[data-cycle-id="c1"] .cycle-report-open').click();
  await expect(page.locator('#m8-skill-detail')).toContainText('Взаимодействие');
  await page.locator('#report-back-button').click();
  await page.locator('[data-cycle-id="c2"] .cycle-report-open').click();
  await expect(page.locator('#m8-report-state')).toContainText('Не удалось открыть');
  expect(new URL(page.url()).searchParams.get('report_id')).toBe('r2');
  fs.mkdirSync(fixEvidence, { recursive: true });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await noOldResult(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
  }
  await page.screenshot({ path: path.join(fixEvidence, 'open-error-390.png'), fullPage: true });
  failure = false;
  await page.getByRole('button', { name: 'Повторить', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#m8-skill-detail')).toContainText('Уникальный навык Б');
  await expect(page.locator('#m8-skill-detail')).not.toContainText('full');
  await expect(page.locator('#m8-skill-detail')).not.toContainText('Полнота отдельно');
  await expect(page.locator('#m8-skill-detail')).toContainText('2.25');
  await expect(page.locator('#report-panel')).not.toContainText('Взаимодействие');
  expect(seen.every((method) => method === 'GET')).toBe(true);
  expect(JSON.stringify(report)).toBe(original);
});

for (const failure of [403, 404, 'network', 'timeout', 'admin503']) {
  test(`FIX-01 AC02 clean selection on ${failure}`, async ({ page }) => {
    let held;
    await page.route('**/users/assessment/m8/reports/r1', (route) => route.fulfill({ json: report }));
    const customer = failure === 'admin503';
    await page.route(`**/users/${customer ? 'admin/m8-access' : 'assessment/m8'}/reports/r2`, (route) => {
      if (failure === 'network') return route.abort('internetdisconnected');
      if (failure === 'timeout') { held = route; return; }
      return route.fulfill({ status: customer ? 503 : failure, json: { detail: 'Synthetic failure' } });
    });
    await sourceReportApp(page);
    await open(page, 'r1');
    await expect(page.locator('#m8-skill-detail')).toContainText('Взаимодействие');
    if (failure === 'timeout') await page.evaluate(() => {
      const original = window.setTimeout;
      window.setTimeout = (fn, delay, ...args) => original(fn, delay === 30000 ? 30 : delay, ...args);
    });
    await page.evaluate((customerAccess) => window.__report04Open({ m8ReportId: 'r2', m8CycleId: 'c2', customerAccess }), customer);
    await expect(page.locator('#m8-report-state')).toContainText('Не удалось открыть');
    await page.setViewportSize({ width: 390, height: 900 });
    await noOldResult(page);
    if (held) await held.fulfill({ json: secondReport() }).catch(() => {});
  });
}

test('FIX-01 preparing and failed states use public copy', async ({ page }) => {
  let results_status = 'ready', report_status = 'pending';
  await page.route('**/users/assessment/m8/cycles/c1/status', (route) => route.fulfill({ json: { results_status, report_status } }));
  await sourceReportApp(page);
  await page.evaluate(() => window.__report04Open({ m8CycleId: 'c1' }));
  await expect(page.locator('#m8-report-state')).toHaveText('Оценка завершена. Готовим ваш отчёт');
  report_status = 'failed';
  await page.evaluate(() => window.__report04Open({ m8CycleId: 'c1' }));
  await expect(page.locator('#m8-report-state')).toContainText('Ответы сохранены');
  results_status = 'failed';
  await page.evaluate(() => window.__report04Open({ m8CycleId: 'c1' }));
  await expect(page.locator('#m8-report-state')).toContainText('Ответы сохранены');
});
