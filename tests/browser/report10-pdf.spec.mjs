import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
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
