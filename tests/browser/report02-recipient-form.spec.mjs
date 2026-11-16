import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18952 }); });
test.afterAll(async () => { await preview?.close(); });

test('REPORT-02 organization form has no report recipient selection', async ({ page }) => {
  const evidence = path.resolve('docs/evc/tasks/p4k-report-02/evidence');
  fs.mkdirSync(evidence, { recursive: true });
  await page.route('**/users/admin/organizations/3/questionnaire', (route) => route.fulfill({ json: { items: [{
    id: 71, assignment_ref: 'synthetic-pilot-11', status: 'confirmed', channel: 'product_form',
    confirmed_at: '2026-11-15T12:00:00Z', answers_json: {},
    participant_preview: { result_recipients: 'LEGACY RECIPIENT SECTION MUST NOT RENDER' },
  }] } }));
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${preview.base}/demo/admin/confirmed/`);
    const card = page.locator('[data-organization-id="3"]');
    await expect(card).toBeVisible();
    await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Загружаем' })).toHaveCount(0);
    await card.locator('.admin-organization-step[data-view="questionnaire"]').click();
    await expect(card.locator('form[data-action="preview-questionnaire"]')).toBeVisible();
    await expect(card.getByText('Доступ к готовым отчётам')).toHaveCount(0);
    await expect(card.getByText('Получатели отчёта')).toHaveCount(0);
    await expect(card.getByText('LEGACY RECIPIENT SECTION MUST NOT RENDER')).toHaveCount(0);
    await expect(card.locator('[name="result_recipients"], [name="recipient_user_ids"], [name="recipients"]')).toHaveCount(0);
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(width + 1);
    if (width !== 320) await page.screenshot({ path: path.join(evidence, `organization-questionnaire-${width}.png`), fullPage: true });
  }
});
