import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18966 }); });
test.afterAll(async () => { await preview?.close(); });

const history = Array.from({ length: 12 }, (_, index) => ({
  cycle_id: `cycle-${index}`, report_id: `report-${index}`,
  program_name: `Программа ${index}`,
  collection_closed_at: new Date(Date.UTC(2026, 10, 15 - index, 12)).toISOString(),
  status: 'report_ready', versions: [{ report_id: `report-${index}` }, { report_id: `old-${index}` }],
}));

const savedReport = (index) => ({
  id: `report-${index}`, cycle_id: `cycle-${index}`, owner_user_id: 18,
  program_name: `Программа ${index}`, collection_closed_at: history[index].collection_closed_at,
  c67: { skills: [], competencies: [], coverage: {}, limitations: [], reliability: { status: 'not_verified' },
    descriptive: { status: 'ready', summary: [], claims: [] } },
});

test('REPORT-06 one card per Cycle, pages, exact report and return context', async ({ page }) => {
  test.setTimeout(30000);
  await page.route('**/web/dist/main.js*', (route) => route.fulfill({ body: '', contentType: 'application/javascript' }));
  let rows = [...history, { cycle_id: 'active', status: 'collecting', report_id: null }];
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill({ json: { cycles: rows } }));
  await page.route('**/users/assessment/m8/reports/*', (route) => {
    const index = Number(new URL(route.request().url()).pathname.split('/').at(-1).split('-').at(-1));
    return route.fulfill({ json: savedReport(index) });
  });
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReports }, { handleReportBack }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/reports.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    state.isAdmin = false;
    window.__report06OpenHistory = openReports;
    document.getElementById('report-back-button').addEventListener('click', handleReportBack);
    await openReports();
  });
  await expect(page.locator('.cycle-report')).toHaveCount(10);
  await expect(page.locator('#reports-panel')).not.toContainText('Сохранённая версия');
  await expect(page.locator('#reports-panel')).not.toContainText('Архив прежних оценок');
  const evidence = path.resolve('docs/evc/tasks/p4k-report-06/evidence');
  await fs.mkdir(evidence, { recursive: true });
  await page.screenshot({ path: path.join(evidence, 'history-list-1440.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.screenshot({ path: path.join(evidence, 'history-list-390.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('navigation', { name: 'Страницы истории оценок' }).getByText('Вперёд').click();
  await expect(page.locator('.cycle-report')).toHaveCount(2);
  await page.locator('[data-cycle-id="cycle-11"] .cycle-report-open').click();
  await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
  await expect(page.locator('#m8-report-metadata')).toContainText('Программа 11');
  expect(new URL(page.url()).searchParams.get('report_id')).toBe('report-11');
  expect(new URL(page.url()).searchParams.get('cycle_id')).toBe('cycle-11');
  await page.locator('#report-back-button').click();
  await expect(page.locator('.cycle-report')).toHaveCount(2);
  await expect(page.locator('.profile-history-page-indicator')).toHaveText('2 из 2');

  rows = [{ ...history[0], report_id: null, status: 'processing' }];
  await page.evaluate(() => window.__report06OpenHistory());
  await expect(page.locator('.cycle-report')).toHaveCount(1);
  await expect(page.locator('.cycle-report')).toContainText('Отчёт готовится');
  rows = [{ ...history[0], report_id: null, status: 'failed' }];
  await page.locator('.cycle-report button').click();
  await expect(page.locator('.cycle-report')).toHaveCount(1);
  await expect(page.locator('.cycle-report')).toContainText('Не удалось подготовить отчёт');
  rows = [{ ...history[0], status: 'report_ready' }];
  await page.locator('.cycle-report button').click();
  await expect(page.locator('.cycle-report')).toHaveCount(1);
  await expect(page.locator('.cycle-report-open')).toBeVisible();

  for (const width of [1440, 720, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    if (width !== 320) await page.screenshot({ path: path.join(evidence, `history-${width}.png`), fullPage: true });
  }
});

test('REPORT-06 history read error is not an empty result', async ({ page }) => {
  test.setTimeout(30000);
  await page.route('**/web/dist/main.js*', (route) => route.fulfill({ body: '', contentType: 'application/javascript' }));
  let response = { status: 503, json: { detail: 'Временно недоступно' } };
  await page.route('**/users/assessment/m8/history', (route) => route.fulfill(response));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openReports }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/reports.js'),
    ]);
    state.pendingUser = { id: 18 };
    state.isAdmin = false;
    await openReports();
  });
  await expect(page.locator('#profile-history-list [role="alert"]')).toBeVisible();
  await expect(page.locator('#profile-history-list')).not.toContainText('Предыдущих завершённых оценок пока нет');
  await expect(page.getByRole('button', { name: 'Повторить загрузку' })).toBeVisible();
  response = { json: { cycles: [] } };
  await page.getByRole('button', { name: 'Повторить загрузку' }).click();
  await expect(page.locator('#profile-history-list')).toContainText('Предыдущих завершённых оценок пока нет');
});

test('REPORT-06 direct link and reload keep the selected Cycle after membership removal', async ({ page }) => {
  test.setTimeout(30000);
  const inactiveMain = (route) => route.fulfill({ body: '', contentType: 'application/javascript' });
  await page.route('**/web/dist/main.js*', inactiveMain);
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.unroute('**/web/dist/main.js*', inactiveMain);
  const seen = [];
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    seen.push(pathname);
    if (pathname === '/users/version') return route.fulfill({ json: { version: '2.1.18' } });
    if (pathname === '/users/session/restore' || pathname === '/users/18/session-bootstrap') {
      return route.fulfill({ json: { authenticated: true, user: { id: 18, full_name: 'Участник' }, dashboard: {} } });
    }
    if (pathname === '/users/assessment/m8/reports/report-11') return route.fulfill({ json: savedReport(11) });
    if (pathname === '/users/assessment/m8/history') return route.fulfill({ json: { cycles: [history[11]] } });
    return route.fulfill({ status: 403, json: { detail: 'Нет действующего членства' } });
  });
  const direct = `${preview.base}/?screen=report&cycle_id=cycle-11&report_id=report-11`;
  await page.goto(direct);
  await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
  await expect(page.locator('#m8-report-metadata')).toContainText('Программа 11');
  await page.reload();
  await expect(page.locator('#m8-report-metadata')).toContainText('Программа 11');
  expect(seen).not.toContain('/users/18/journey-state');
  await page.goto(`${preview.base}/?screen=report&session_id=987`);
  await expect(page.locator('#reports-panel')).toContainText('Старая ссылка не указывает на прохождение');
  await expect(page.locator('#reports-panel')).toContainText('Программа 11');
});
