import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const evidence = path.resolve('docs/evc/tasks/p4k-report-11/evidence');
const saved = JSON.parse(fs.readFileSync(path.join(evidence, 'report11-selected.json'), 'utf8'));
const pdfBytes = fs.readFileSync(path.join(evidence, 'report11-bridge.pdf'));
let preview;

test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18971 }); });
test.afterAll(async () => { await preview?.close(); });

test('REPORT-11 saved HTTP response renders the exact report and downloads its PDF', async ({ page }) => {
  await page.route(`**/users/assessment/m8/reports/${saved.id}`, (route) => route.fulfill({ json: saved }));
  await page.route(`**/users/assessment/m8/reports/${saved.id}/pdf`, (route) => route.fulfill({
    status: 200, body: pdfBytes, contentType: 'application/pdf',
    headers: { 'Content-Disposition': `attachment; filename="4k-report-${saved.id}.pdf"` },
  }));
  await page.goto(`${preview.base}/demo/admin/confirmed/`);
  await page.evaluate(async (report) => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: report.owner_user_id };
    openReport({ m8CycleId: report.cycle_id, m8ReportId: report.id });
  }, saved);

  await expect(page.locator('#report-download-button')).toHaveAttribute('data-m8-report-id', saved.id);
  await expect(page.locator('#m8-report-shell')).toContainText(saved.program_name);
  await expect(page.locator('#m8-report-skills')).toContainText('Ориентация и проектирование коммуникации');
  await expect(page.locator('#m8-report-skills')).toContainText('По навыку пока нет обоснованного результата');
  await expect(page.locator('#m8-report-skills')).toContainText('0');
  await expect(page.locator('#m8-report-shell')).not.toContainText(saved.id);
  await expect(page.locator('#m8-report-shell')).not.toContainText(saved.cycle_id);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    if (width !== 320) await page.screenshot({ path: path.join(evidence, `saved-bridge-${width}.png`), fullPage: true });
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  const download = page.waitForEvent('download');
  await page.locator('#report-download-button').click();
  const artifact = await download;
  expect(artifact.suggestedFilename()).toBe(`4k-report-${saved.id}.pdf`);
  expect(fs.readFileSync(await artifact.path()).equals(pdfBytes)).toBe(true);
});
