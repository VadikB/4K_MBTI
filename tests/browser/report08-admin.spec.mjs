import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18968 }); });
test.afterAll(async () => { await preview?.close(); });

const rows = Array.from({ length: 14 }, (_, index) => ({
  cycle_id: `cycle-${index}`, report_id: index === 0 || index > 2 ? `report-${index}` : null,
  full_name: index === 0 ? 'Иван Иванов' : `Участник ${index}`,
  program_name: index < 3 ? 'Пилот' : 'Другая программа',
  collection_closed_at: new Date(Date.UTC(2026, 10, 16 - index)).toISOString(),
  status: index === 1 ? 'preparing' : index === 2 ? 'failed' : 'ready',
}));
const report = {
  id: 'report-0', cycle_id: 'cycle-0', owner_user_id: 18, participant_name: 'Иван Иванов',
  program_name: 'Пилот', collection_closed_at: rows[0].collection_closed_at,
  c67: { skills: [], competencies: [], coverage: {}, limitations: [], reliability: { status: 'not_verified' },
    descriptive: { status: 'ready', summary: [], claims: [] } },
};

test('REPORT-08 filters, server pages, exact report, return and organization switch', async ({ page }) => {
  await page.route('**/web/dist/main.js*', (route) => route.fulfill({ body: '', contentType: 'application/javascript' }));
  const seen = [];
  await page.route('**/users/admin/m8-access/reports?*', async (route) => {
    const params = new URL(route.request().url()).searchParams;
    seen.push(Object.fromEntries(params));
    const organization = params.get('organization_id') || '1';
    if (organization === '1' && params.get('query') === 'Участник') {
      await new Promise((resolve) => setTimeout(resolve, 700));
    }
    let items = organization === '2' ? [{ ...rows[0], cycle_id: 'org-2', report_id: 'report-org-2', full_name: 'Другой участник' }] : rows;
    if (params.get('query')) items = items.filter((item) => item.full_name.toLowerCase().includes(params.get('query').toLowerCase()));
    if (params.get('program')) items = items.filter((item) => item.program_name === params.get('program'));
    if (params.get('status')) items = items.filter((item) => item.status === params.get('status'));
    const pageNumber = Number(params.get('page'));
    const pageSize = Number(params.get('page_size'));
    return route.fulfill({ json: { items: items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize),
      total: items.length, page: pageNumber, page_size: pageSize, organization_id: Number(organization),
      organizations: [{ id: 1, name: 'Организация A' }, { id: 2, name: 'Организация B' }],
      programs: ['Пилот', 'Другая программа'] } });
  });
  await page.route('**/users/admin/m8-access/reports/report-0', (route) => route.fulfill({ json: report }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async () => {
    const [{ state }, { openAdminReports, changeAdminReportsPage }, { handleReportBack }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/admin/reports.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18, full_name: 'Администратор' };
    state.isAdmin = true;
    state.identityEpoch = 1;
    window.__report08Open = openAdminReports;
    document.getElementById('report-back-button').addEventListener('click', handleReportBack);
    document.getElementById('admin-reports-next-button').addEventListener('click', () => changeAdminReportsPage(1));
    document.getElementById('admin-reports-prev-button').addEventListener('click', () => changeAdminReportsPage(-1));
    await openAdminReports();
  });
  await expect(page.locator('.admin-report-row')).toHaveCount(12);
  await expect(page.locator('#admin-reports-found')).toHaveText('Найдено: 14');
  await expect(page.locator('.admin-report-row').nth(1)).toContainText('Готовится');
  await expect(page.locator('.admin-report-row').nth(1).getByRole('button')).toHaveCount(0);
  await expect(page.locator('.admin-report-row').nth(2)).toContainText('Не удалось подготовить');
  const evidence = path.resolve('docs/evc/tasks/p4k-report-08/evidence');
  await fs.mkdir(evidence, { recursive: true });
  await page.screenshot({ path: path.join(evidence, 'list-1440.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.screenshot({ path: path.join(evidence, 'list-390.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('#admin-reports-next-button').click();
  await expect(page.locator('.admin-report-row')).toHaveCount(2);
  await page.locator('#admin-reports-search').fill('Иван');
  await expect(page.locator('#admin-reports-found')).toHaveText('Найдено: 1');
  expect(seen.at(-1).page).toBe('1');
  await page.locator('#admin-reports-program').selectOption('Пилот');
  await page.locator('#admin-reports-status').selectOption('ready');
  await expect(page.locator('.admin-report-row')).toHaveCount(1);
  await page.locator('.admin-report-row').getByRole('button', { name: 'Открыть' }).click();
  await expect(page.locator('#m8-report-metadata')).toContainText('Пилот');
  await page.locator('#report-back-button').click();
  await expect(page.locator('#admin-reports-search')).toHaveValue('Иван');
  await expect(page.locator('#admin-reports-program')).toHaveValue('Пилот');
  await page.locator('#admin-reports-clear').click();
  await expect(page.locator('#admin-reports-found')).toHaveText('Найдено: 14');
  await page.locator('#admin-reports-organization').selectOption('2');
  await expect(page.locator('#admin-reports-found')).toHaveText('Найдено: 1');
  await expect(page.locator('.admin-report-row')).toContainText('Другой участник');
  await page.locator('#admin-reports-organization').selectOption('1');
  await expect(page.locator('#admin-reports-found')).toHaveText('Найдено: 14');
  await page.locator('#admin-reports-search').fill('Участник');
  await expect.poll(() => seen.some((request) => request.organization_id === '1' && request.query === 'Участник')).toBe(true);
  await page.locator('#admin-reports-organization').selectOption('2');
  await expect(page.locator('.admin-report-row')).toContainText('Другой участник');
  await page.waitForTimeout(800);
  await expect(page.locator('.admin-report-row')).toContainText('Другой участник');
});
