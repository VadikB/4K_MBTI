// Actual product renderer/CSS with explicit synthetic HTTP projections.
// Database, native browser zoom and physical devices are verified separately.
import { test, expect } from '@playwright/test';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const memberEmail = 'current.' + 'verylong'.repeat(12) + '@example.test';
const adminEmail = 'administrator.' + 'long'.repeat(32) + '@example.test';
const card = (page) => page.locator('[data-organization-id="3"]');

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18952 }); });
test.afterAll(async () => { await preview?.close(); });

async function checkLayout(page, section, width, textScale) {
  if (textScale === 2) await page.evaluate(() => {
    const nodes = [...document.querySelectorAll('#admin-organizations-panel, #admin-organizations-panel *')];
    for (const node of nodes) { node.style.fontSize = ''; node.style.lineHeight = ''; }
    const styles = nodes.map((node) => ({ node, font: parseFloat(getComputedStyle(node).fontSize),
      line: parseFloat(getComputedStyle(node).lineHeight) }));
    for (const { node, font, line } of styles) {
      if (Number.isFinite(font)) node.style.fontSize = font * 2 + 'px';
      if (Number.isFinite(line)) node.style.lineHeight = line * 2 + 'px';
    }
  });
  const layout = await section.evaluate((node) => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
    outliers: [node, ...node.querySelectorAll('*')].filter((element) => {
      const rect = element.getBoundingClientRect();
      return rect.width && (rect.left < -1 || rect.right > innerWidth + 1);
    }).map((element) => ({ tag: element.tagName, class: element.className, text: element.textContent.slice(0, 70) })),
  }));
  expect(layout.document).toBeLessThanOrEqual(width + 1);
  expect(layout.outliers).toEqual([]);
  return layout;
}

test('F02 and FIX02 AC05: selected organization program, administrators and exact account lookup fit the viewport', async ({ page }, info) => {
  let populated = false;
  await page.route('**/users/admin/organizations', async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.purge_preview_available = true;
    data.items[0].members[0] = { ...data.items[0].members[0], user_id: 34,
      email: memberEmail, full_name: 'Синтетический текущий участник' };
    data.items[0].admins = populated
      ? [{ user_id: 19, email: adminEmail, is_participant: false }]
      : [];
    await route.fulfill({ response, json: data });
  });
  await page.route('**/users/admin/organizations/3/history', (route) =>
    route.fulfill({ json: { organization_id: 3, is_active: true, events: [] } }));
  const metrics = [];
  for (const width of [1440, 390, 320]) for (const textScale of [1, 2]) for (const hasAdmin of [false, true]) {
    populated = hasAdmin;
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(preview.base + '/demo/superadmin/confirmed/');
    await page.locator('#platform-org-rows [data-org-id="3"][data-platform-org-view="card"]').click();
    const organization = card(page);
    const program = organization.locator('form[data-action="connect-assessment-program"]');
    await expect(program.locator('[data-program-connection-state]')).toContainText('synthetic-1.11');
    const overview = await checkLayout(page, organization, width, textScale);

    await organization.getByRole('link', { name: 'Журнал и операции', exact: true }).click();
    const account = organization.locator('[data-org-account-actions="purge"]');
    await account.locator('summary').click();
    const email = account.getByLabel('Рабочая почта');
    for (const [address, user] of hasAdmin ? [[memberEmail, '34'], [adminEmail, '19']] : [[memberEmail, '34']]) {
      await email.fill(address);
      const remove = account.getByRole('button', { name: 'Удалить человека' });
      await expect(remove).toHaveAttribute('data-user-id', user);
      await expect(remove).toHaveAttribute('data-email', address);
      await remove.focus();
      await expect(remove).toBeFocused();
    }
    const history = await checkLayout(page, organization, width, textScale);

    await organization.getByRole('link', { name: 'Администраторы', exact: true }).click();
    const access = organization.locator('[data-organization-admins]');
    if (hasAdmin) {
      await expect(access.locator('.admin-access-name')).toHaveText(adminEmail);
      await access.locator('.admin-organization-member-menu summary').click();
      await expect(access.getByRole('menuitem', { name: 'Снять права' })).toBeVisible();
    } else await expect(access).toContainText('Администраторов пока нет.');
    const administrators = await checkLayout(page, organization, width, textScale);
    await expect(organization.locator('[data-action="preview-early-data"], [data-action="add-domain"]')).toHaveCount(0);
    await page.screenshot({ path: info.outputPath('admin-access-' + width + '-text' + textScale * 100 + '-' + (hasAdmin ? 'long' : 'empty') + '.png'), fullPage: true });
    metrics.push({ width, textScale, hasAdmin, overview, history, administrators });
  }
  await info.attach('layout-evidence', { body: JSON.stringify({ scope: 'actual_renderer_synthetic_http',
    physical_devices: 'NOT_RUN', native_zoom: 'NOT_RUN', text_zoom: '200%', metrics }, null, 2), contentType: 'application/json' });
});

test('FIX02 AC06 organization administrator sees the uploader of the current questionnaire revision', async ({ page }) => {
  let revisionId = 71;
  let uploader = 'Синтетический администратор А';
  await page.route('**/users/admin/organizations/3/questionnaire', (route) => route.fulfill({ json: { items: [{
    id: revisionId, assignment_ref: 'synthetic-pilot-11', channel: 'csv', status: 'confirmed',
    effective_confirmed: { id: revisionId, assignment_ref: 'synthetic-pilot-11', confirmed_at: null },
    answers_json: {}, uploaded_by_user_id: revisionId === 71 ? 40 : 41,
    uploaded_by_name: uploader, uploaded_by_email: 'uploader@example.test', recipient_user_ids: [],
  }] } }));
  await page.goto(preview.base + '/demo/admin/confirmed/');
  const organization = card(page);
  await organization.locator('[data-action="show-admin-view"][data-view="organization-data"]').click();
  const attribution = organization.locator('.admin-data-readiness .admin-questionnaire-uploader');
  await expect(attribution).toHaveText('Внёс данные: ' + uploader);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    const readiness = organization.locator('.admin-data-readiness');
    if (await readiness.getAttribute('open') === null) await readiness.locator('summary').click();
    await checkLayout(page, readiness, width, 2);
  }
  revisionId = 72;
  uploader = 'Синтетический администратор Б';
  await page.reload();
  await organization.locator('[data-action="show-admin-view"][data-view="organization-data"]').click();
  await expect(attribution).toHaveText('Внёс данные: ' + uploader);
  await expect(attribution).toHaveAttribute('data-questionnaire-revision-id', '72');
  await organization.locator('.admin-organization-step[data-view="people"]').click();
  const member = organization.locator('[data-action="add-member"]');
  await expect(member.locator('[name="email"]')).toHaveValue('');
  await expect(member.locator('[name="full_name"]')).toHaveValue('');
  await expect(organization.locator('.admin-organization-member-select input')).toHaveCount(1);
});
