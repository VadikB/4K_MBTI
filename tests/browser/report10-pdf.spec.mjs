import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18970 }); });
test.afterAll(async () => { await preview?.close(); });

const saved = {
  id: 'report-pdf', cycle_id: 'cycle-pdf', owner_user_id: 18, status: 'ready',
  program_name: 'Программа взаимодействия', collection_closed_at: '2026-11-17T10:00:00Z',
  participant_name: 'Участник',
  c67: { skills: [], competencies: [], coverage: {}, limitations: [],
    reliability: { status: 'not_verified' },
    descriptive: { status: 'ready', summary: ['Подтверждённое резюме.'], claims: [] } },
};
const bytes = fs.readFileSync(path.resolve('docs/evc/tasks/p4k-report-10/evidence/normal.pdf'));
const pdf = (route) => route.fulfill({ status: 200, body: bytes,
  contentType: 'application/pdf', headers: { 'Content-Disposition': 'attachment; filename="4k-report-report-pdf.pdf"' } });

test('REPORT-10 participant and customer download the selected PDF and retry a render error', async ({ page }) => {
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [] } }));
  await page.route('**/users/assessment/m8/reports/report-pdf', (route) => route.fulfill({ json: saved }));
  await page.route('**/users/admin/m8-access/reports/report-pdf', (route) => route.fulfill({ json: saved }));
  let ownerCalls = 0;
  await page.route('**/users/assessment/m8/reports/report-pdf/pdf', (route) => {
    ownerCalls += 1;
    return ownerCalls === 1
      ? route.fulfill({ status: 503, json: { detail: 'PDF временно недоступен. Повторите скачивание.' } })
      : pdf(route);
  });
  await page.route('**/users/admin/m8-access/reports/report-pdf/pdf', pdf);
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    window.__report10Open = openReport;
  });
  await page.evaluate(() => window.__report10Open({ m8CycleId: 'cycle-pdf', m8ReportId: 'report-pdf' }));
  await expect(page.locator('#report-download-button')).toHaveAttribute('data-m8-report-id', 'report-pdf');
  await page.locator('#report-download-button').click();
  await expect(page.locator('#report-download-status')).toContainText('Попробуйте ещё раз');
  const ownerDownload = page.waitForEvent('download');
  await page.locator('#report-download-button').click();
  expect((await ownerDownload).suggestedFilename()).toBe('4k-report-report-pdf.pdf');
  await page.evaluate(() => window.__report10Open({ m8CycleId: 'cycle-pdf', m8ReportId: 'report-pdf', customerAccess: true }));
  await expect(page.locator('#report-download-button')).toHaveAttribute('data-m8-report-access', 'customer');
  const customerDownload = page.waitForEvent('download');
  await page.locator('#report-download-button').click();
  expect((await customerDownload).suggestedFilename()).toBe('4k-report-report-pdf.pdf');
  expect(ownerCalls).toBe(2);
});


const fixEvidence = path.resolve('docs/evc/tasks/p4k-report-fix-01/evidence');
const fixReport = { ...saved, c67: { ...saved.c67, template_version: 'm8-basic-report/1.5.0',
  skills: [{ skill_id: 'PDF-A', skill_name: 'Контрольный навык PDF', competency_id: 'K1',
    competency_name: 'Коммуникация', outcome: 'full_score', score: { value: 0 } }],
  limitations: ['Skill Level is not derived from numeric Score'] } };
const pair = { mode: 'comparable', current: { report_id: 'report-pdf', program_name: saved.program_name, closed_at: '2026-11-17' },
  previous: { report_id: 'previous', program_name: 'Предыдущая контрольная программа', closed_at: '2026-10-01' },
  skills: [{ skill_id: 'PDF-A', skill_name: 'Контрольный навык PDF', previous: 1, current: 0, difference: -1,
    comparability: { status: 'allowed' } }] };
let selectedBytes, comparisonBytes, projectedReport;
test.beforeAll(() => {
  const render = (input, module, fn) => execFileSync(process.env.BROWSER_PYTHON || '.venv/bin/python', ['-c',
    `import json,sys; from Api.${module} import ${fn}; sys.stdout.buffer.write(${fn}(json.load(sys.stdin)))`],
  { input: JSON.stringify(input), env: { ...process.env, PYTHON_DOTENV_DISABLED: '1', DB_POOL_MIN_SIZE: '0' } });
  projectedReport = JSON.parse(execFileSync(process.env.BROWSER_PYTHON || '.venv/bin/python', ['-c',
    'import json,sys; from Api.m8_report_access import public_projection; print(json.dumps(public_projection(json.load(sys.stdin))))'],
  { input: JSON.stringify(fixReport), env: { ...process.env, PYTHON_DOTENV_DISABLED: '1', DB_POOL_MIN_SIZE: '0' } }));
  selectedBytes = render(fixReport, 'm8_results', 'render_pdf');
  comparisonBytes = render(pair, 'm8_report_comparison', 'render_comparison_pdf');
  fs.mkdirSync(fixEvidence, { recursive: true });
  fs.writeFileSync(path.join(fixEvidence, 'selected-report.pdf'), selectedBytes);
  fs.writeFileSync(path.join(fixEvidence, 'selected-comparison.pdf'), comparisonBytes);
});

async function fixtureApp(page, place) {
  await page.route('**/web/dist/main.js*', (route) => route.fulfill({ body: '', contentType: 'application/javascript' }));
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: [
    { report_id: 'report-pdf', cycle_id: 'cycle-pdf', status: 'report_ready', program_name: saved.program_name, collection_closed_at: saved.collection_closed_at },
    { report_id: 'previous', cycle_id: 'previous-cycle', status: 'report_ready', program_name: pair.previous.program_name, collection_closed_at: '2026-10-01' },
    { report_id: 'older', cycle_id: 'older-cycle', status: 'report_ready', program_name: 'Ещё одна программа', collection_closed_at: '2026-09-01' },
  ] } }));
  await page.route('**/users/assessment/m8/reports/report-pdf', (route) => route.fulfill({ json: projectedReport }));
  await page.route('**/users/admin/m8-access/reports?*', (route) => route.fulfill({ json: {
    items: [{ report_id: 'report-pdf', cycle_id: 'cycle-pdf', status: 'ready', full_name: 'Синтетический участник',
      program_name: saved.program_name, collection_closed_at: saved.collection_closed_at }],
    organizations: [{ id: 1, name: 'Контрольная организация' }], programs: [saved.program_name], organization_id: 1, total: 13, page: 2,
  } }));
  await page.route('**/users/assessment/m8/reports/report-pdf/comparison?*', (route) => route.fulfill({ json: pair }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async (place) => {
    const [{ state }, reportModule, history, admin] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'), import('/web/js/screens/reports.js'),
      import('/web/js/screens/admin/reports.js'),
    ]);
    state.pendingUser = { id: 18 }; state.isAdmin = place === 'admin';
    state.adminReportsPage = 2; state.adminReportsSearch = 'Синтетический'; state.adminReportsProgram = 'Программа взаимодействия';
    window.__fixOpen = reportModule.openReport;
    document.getElementById('report-download-button').addEventListener('click', reportModule.downloadSelectedReportPdf);
    document.getElementById('report-back-button').addEventListener('click', reportModule.handleReportBack);
    if (place === 'history') await history.openReports();
    else if (place === 'admin') await admin.openAdminReports();
    else reportModule.openReport({ m8CycleId: 'cycle-pdf', m8ReportId: 'report-pdf' });
  }, place);
  if (place === 'comparison') {
    await expect(page.locator('#m8-comparison-select')).toBeEnabled();
    await page.locator('#m8-comparison-select').selectOption('previous');
    await page.locator('#m8-comparison-open').click();
    await expect(page.locator('#m8-comparison-content')).toContainText(pair.previous.program_name);
  }
}

for (const place of ['history', 'admin', 'comparison']) {
  for (const failure of ['503', 'network', 'json200', 'badSignature', 'timeout']) {
    test(`FIX-01 PDF ${place}: ${failure} stays in place and keyboard retry saves exact bytes`, async ({ page }) => {
      let calls = 0;
      const seen = [];
      const routePath = place === 'admin' ? '**/users/admin/m8-access/reports/report-pdf/pdf'
        : place === 'comparison' ? '**/users/assessment/m8/reports/report-pdf/comparison.pdf?*'
          : '**/users/assessment/m8/reports/report-pdf/pdf';
      const expectedBytes = place === 'comparison' ? comparisonBytes : selectedBytes;
      const downloads = [];
      page.on('download', (download) => downloads.push(download));
      await page.route(routePath, (route) => {
        seen.push(new URL(route.request().url())); calls += 1;
        if (calls === 1) {
          if (failure === 'network') return route.abort('internetdisconnected');
          if (failure === 'timeout') return;
          if (failure === 'badSignature') return route.fulfill({ body: '{"detail":"not a PDF"}', contentType: 'application/pdf' });
          return route.fulfill({ status: failure === '503' ? 503 : 200, json: { detail: 'Synthetic PDF failure' } });
        }
        return route.fulfill({ body: expectedBytes, contentType: 'application/pdf' });
      });
      await fixtureApp(page, place);
      const button = place === 'history' ? page.locator('[data-cycle-id="cycle-pdf"] .cycle-report-pdf')
        : place === 'admin' ? page.locator('.admin-report-download-action').getByRole('button', { name: 'PDF', exact: true })
          : page.getByRole('button', { name: 'Скачать сравнение PDF' });
      const status = place === 'history' ? page.locator('[data-cycle-id="cycle-pdf"] [role="status"]')
        : place === 'admin' ? page.locator('.admin-report-download-action [role="status"]')
          : page.locator('.report-pdf-action [role="status"]');
      const address = page.url();
      if (failure === 'timeout') await page.evaluate(() => {
        const original = window.setTimeout;
        window.setTimeout = (fn, delay, ...args) => original(fn, delay === 30000 ? 30 : delay, ...args);
      });
      await button.click();
      await expect(status).toHaveText('Не удалось скачать PDF. Попробуйте ещё раз.');
      expect(page.url()).toBe(address);
      expect(downloads).toHaveLength(0);
      if (place === 'admin') {
        await expect(page.locator('#admin-reports-search')).toHaveValue('Синтетический');
        await expect(page.locator('#admin-reports-page-indicator')).toHaveText('2 / 2');
      }
      if (place === 'comparison') await expect(page.locator('#m8-comparison-select')).toHaveValue('previous');
      if (failure === '503') {
        for (const width of [1440, 390]) {
          await page.setViewportSize({ width, height: 900 });
          await expect(status).toBeVisible();
          expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
        }
        if (place !== 'comparison') await page.screenshot({ path: path.join(fixEvidence, `pdf-error-${place}-390.png`), fullPage: true });
      }
      const downloaded = page.waitForEvent('download');
      await button.focus(); await page.keyboard.press('Enter');
      const download = await downloaded;
      expect(download.suggestedFilename()).toBe(place === 'comparison' ? '4k-report-comparison-report-pdf.pdf' : '4k-report-report-pdf.pdf');
      expect(fs.readFileSync(await download.path())).toEqual(expectedBytes);
      expect(calls).toBe(2);
      if (place === 'comparison') expect(seen.every((url) => url.searchParams.get('previous_report_id') === 'previous')).toBe(true);
    });
  }
}

test('FIX-01 stale PDF is suppressed after report switch and pair switch; duplicate click is ignored', async ({ page }) => {
  let held, calls = 0;
  const downloads = [];
  page.on('download', (download) => downloads.push(download));
  await page.route('**/users/assessment/m8/reports/report-pdf/pdf', (route) => { held = route; calls += 1; });
  await fixtureApp(page, 'report');
  await expect(page.locator('#report-download-button')).toBeEnabled();
  await expect(page.locator('#m8-report-limitations')).toContainText('Числовой показатель не определяет общий уровень владения навыком');
  await expect(page.locator('#m8-report-shell')).not.toContainText('Skill Level');
  await page.locator('#report-download-button').click();
  await expect.poll(() => Boolean(held)).toBe(true);
  await page.locator('#report-download-button').dispatchEvent('click');
  expect(calls).toBe(1);
  await page.evaluate(() => window.__fixOpen({ m8CycleId: 'other', m8ReportId: 'other' }));
  await held.fulfill({ body: selectedBytes, contentType: 'application/pdf' }).catch(() => {});
  await expect(page.locator('#report-download-button')).toBeDisabled();
  await expect(page.locator('#report-download-status')).toBeEmpty();
  expect(downloads).toHaveLength(0);

  await page.evaluate(() => window.__fixOpen({ m8CycleId: 'cycle-pdf', m8ReportId: 'report-pdf' }));
  await expect(page.locator('#m8-comparison-select')).toBeEnabled();
  await page.locator('#m8-comparison-select').selectOption('previous');
  await page.locator('#m8-comparison-open').click();
  let pairHeld;
  await page.route('**/users/assessment/m8/reports/report-pdf/comparison.pdf?*', (route) => { pairHeld = route; });
  await page.getByRole('button', { name: 'Скачать сравнение PDF' }).click();
  await expect.poll(() => Boolean(pairHeld)).toBe(true);
  await page.locator('#m8-comparison-select').selectOption('older');
  const response = page.waitForResponse((r) => r.url().includes('comparison.pdf'));
  await pairHeld.fulfill({ body: comparisonBytes, contentType: 'application/pdf' });
  await response;
  await expect(page.locator('#m8-comparison-content')).not.toContainText('PDF скачан');
  await page.waitForTimeout(100);
  expect(downloads).toHaveLength(0);
});
