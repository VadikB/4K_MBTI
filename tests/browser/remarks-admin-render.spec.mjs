// Actual product renderer/CSS with explicit synthetic HTTP projections.
// Database, native browser zoom and physical devices are verified separately.
import { test, expect } from '@playwright/test';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18952 }); });
test.afterAll(async () => { await preview?.close(); });

test('FIX02 AC05/06: account rows, tags, program groups and revision attribution', async ({ page }, info) => {
  test.setTimeout(180000);
  let longTags = false;
  let revisionId = 71;
  let uploader = 'Синтетический администратор А';
  await page.route('**/users/admin/organizations', async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.detached_accounts = [{ user_id: 33, email: 'detached.' + 'verylong'.repeat(12) + '@example.test' }];
    data.excluded_accounts = [{ user_id: 34, email: 'excluded.' + 'verylong'.repeat(12) + '@example.test',
      full_name: 'Синтетический исключённый', organization_id: 3, organization_name: 'Синтетическая организация' }];
    data.items[0].domains = longTags ? ['long'.repeat(32) + '.example.test'] : [];
    data.items[0].admins = longTags ? [{ user_id: 18, email: 'administrator.' + 'long'.repeat(32) + '@example.test' }] : [];
    await route.fulfill({ response, json: data });
  });
  await page.route('**/users/admin/organizations/3/questionnaire', (route) => route.fulfill({ json: { items: [{
    id: revisionId, assignment_ref: 'synthetic-pilot-11', channel: 'csv', status: 'confirmed',
    answers_json: {}, uploaded_by_user_id: revisionId === 71 ? 40 : 41,
    uploaded_by_name: uploader, uploaded_by_email: 'uploader@example.test', recipient_user_ids: [],
  }] } }));
  const metrics = [];
  for (const width of [1440, 390, 320]) for (const textScale of [1, 2]) for (const populated of [false, true]) {
    longTags = populated;
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(`${preview.base}/demo/superadmin/confirmed/`);
    await expect.poll(async () => await page.locator('#admin-open-organizations-button').isVisible() ||
      await page.locator('#admin-organizations-panel').isVisible()).toBe(true);
    if (await page.locator('#admin-open-organizations-button').isVisible()) await page.locator('#admin-open-organizations-button').click();
    const card = page.locator('[data-organization-id="3"]');
    await expect(card).toBeVisible();
    await expect(card.locator('.admin-questionnaire-load-state').filter({ hasText: 'Загружаем' })).toHaveCount(0);
    await card.locator('[data-action="show-admin-view"][data-view="organization-data"]').click();
    await expect(card.locator('.admin-questionnaire-confirmation .admin-questionnaire-uploader')).toHaveText('Внёс данные: ' + uploader);
    for (const action of ['add-domain', 'add-admin']) {
      await page.locator('[data-action="' + action + '"]').evaluate((form, kind) => {
        const message = document.createElement('p');
        message.className = 'admin-organizations-status';
        message.dataset.operationStatus = '';
        message.dataset.tone = kind;
        message.textContent = 'Синтетический результат операции с доменами и администраторами';
        form.append(message);
      }, (action === 'add-domain') === populated ? 'success' : 'error');
    }
    if (textScale === 2) await page.evaluate(() => {
      const styles = [...document.querySelectorAll('#admin-organizations-panel, #admin-organizations-panel *')].map((node) =>
        ({ node, font: parseFloat(getComputedStyle(node).fontSize), line: parseFloat(getComputedStyle(node).lineHeight) }));
      for (const { node, font, line } of styles) {
        if (Number.isFinite(font)) node.style.fontSize = `${font * 2}px`;
        if (Number.isFinite(line)) node.style.lineHeight = `${line * 2}px`;
      }
    });
    const row = page.locator('.admin-detached-accounts .admin-account-row');
    expect((await row.evaluate((node) => getComputedStyle(node).gridTemplateColumns)).split(' ')[0]).not.toBe('44px');
    const remove = row.getByRole('button', { name: 'Удалить полностью' });
    await remove.focus();
    await expect(remove).toBeFocused();
    await remove.scrollIntoViewIfNeeded();
    const layout = await page.evaluate(() => {
      const form = document.querySelector('[data-action="preview-early-data"]');
      const identity = form.querySelector('.admin-assessment-identity').getBoundingClientRect();
      const groups = [...form.querySelectorAll('.admin-questionnaire-field-group')].map((node) => node.getBoundingClientRect().toJSON());
      const selector = '.admin-account-row, .admin-organization-columns, .admin-organization-program-form, [data-action="preview-early-data"]';
      const outliers = [...document.querySelectorAll(selector)].flatMap((node) => [node, ...node.querySelectorAll('*')])
        .filter((node) => { const r = node.getBoundingClientRect(); return r.width && (r.left < -1 || r.right > innerWidth + 1); })
        .map((node) => ({ tag: node.tagName, class: node.className, text: node.textContent.slice(0, 70) }));
      const tags = [...document.querySelectorAll('.admin-organizations-tag')].map((node) => ({
        height: node.getBoundingClientRect().height,
        contentHeight: Math.max(...[...node.children].map((child) => child.getBoundingClientRect().height)),
      }));
      const statuses = [...document.querySelectorAll('.admin-organization-columns [data-operation-status]')].map((node) => ({
        width: node.getBoundingClientRect().width, formWidth: node.parentElement.getBoundingClientRect().width,
        radius: parseFloat(getComputedStyle(node).borderTopLeftRadius),
      }));
      return { document: document.documentElement.scrollWidth, viewport: innerWidth,
        identity: identity.toJSON(), groups, outliers, tags, statuses };
    });
    metrics.push({ width, textScale, longTags, ...layout });
    expect(layout.document).toBeLessThanOrEqual(width + 1);
    expect(layout.outliers).toEqual([]);
    expect(layout.groups).toHaveLength(2);
    for (const tag of layout.tags) expect(tag.height).toBeLessThanOrEqual(tag.contentHeight + 18);
    for (const status of layout.statuses) {
      expect(status.width).toBeGreaterThanOrEqual(status.formWidth - 2);
      expect(status.radius).toBeLessThanOrEqual(20);
    }
    expect(layout.identity.bottom).toBeLessThanOrEqual(layout.groups[0].top);
    await page.screenshot({ path: info.outputPath(`admin-${width}-text${textScale * 100}-${populated ? 'long' : 'empty'}.png`), fullPage: true });
    if (populated) await card.locator('.admin-organization-columns').screenshot({ path: info.outputPath(`tags-${width}-text${textScale * 100}.png`) });
  }
  // The selected revision changes on server readback, independent of current actor.
  revisionId = 72; uploader = 'Синтетический администратор Б';
  await page.reload();
  const card = page.locator('[data-organization-id="3"]');
  await card.locator('[data-action="show-admin-view"][data-view="questionnaire"]').click();
  await expect(card.locator('.admin-questionnaire-uploader')).toHaveText('Внёс данные: ' + uploader);
  await expect(card.locator('.admin-questionnaire-uploader')).toHaveAttribute('data-questionnaire-revision-id', '72');
  const restore = page.locator('[data-action="restore-excluded-account"]');
  await restore.click();
  const memberForm = card.locator('[data-action="add-member"]');
  await expect(memberForm.locator('[name="email"]')).toHaveValue('excluded.' + 'verylong'.repeat(12) + '@example.test');
  await expect(memberForm.locator('[name="full_name"]')).toHaveValue('Синтетический исключённый');
  await expect(memberForm.locator('[name="role_description"]')).toBeFocused();
  await expect(card.locator('.admin-organization-member-select input')).toHaveCount(1);
  await info.attach('layout-evidence', { body: JSON.stringify({ scope: 'actual_renderer_synthetic_http',
    physical_devices: 'NOT_RUN', native_zoom: 'NOT_RUN', text_zoom: '200%', metrics }, null, 2), contentType: 'application/json' });
});
