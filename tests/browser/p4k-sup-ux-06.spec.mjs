import { test, expect } from '@playwright/test';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const endpoint = '/users/admin/support/invitations';
const reference = 'INV-41';
const trace = 'dc28a075-320d-405b-957a-a912ef30ec62';
const saved = {
  kind: 'invitation', reference, organization_id: 3, assignment_ref: 'competencies_4k',
  outcome: 'unknown', reason_code: 'delivery_unknown', link_status: 'active',
  started_at: '2026-11-21T06:08:00Z', sent_at: null, expires_at: '2026-11-24T06:08:00Z',
  used_at: null, last_confirmed_at: '2026-11-21T06:09:00Z', read_at: '2026-11-21T06:10:00Z',
  source: 'organization_invitations',
};

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18979 }); });
test.afterAll(async () => { await preview?.close(); });

for (const width of [1440, 390, 320]) {
  test('UX-06 checks and copies the same invitation at ' + width + ' px', async ({ page, context }, info) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    const requests = [], errors = [];
    const packet = 'Организация: #3\nНазначение: competencies_4k\nНомер приглашения: INV-41\nИсход отправки: unknown';
    let read = 'unknown';
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**' + endpoint + '**', route => {
      const request = route.request();
      const url = new URL(request.url());
      requests.push([request.method(), url.pathname]);
      if (url.pathname === endpoint) return route.fulfill({ json: { items: [saved], next_before: null } });
      expect(url.pathname).toBe(endpoint + '/' + reference);
      if (read === '503') return route.fulfill({ status: 503, headers: { 'x-request-id': trace }, json: {} });
      const detail = read === 'unknown' ? saved : {
        ...saved, outcome: 'accepted', reason_code: 'accepted', link_status: read,
        sent_at: '2026-11-21T06:12:00Z', last_confirmed_at: '2026-11-21T06:12:00Z',
        read_at: '2026-11-21T06:13:00Z', used_at: read === 'used' ? '2026-11-21T06:13:00Z' : null,
      };
      return route.fulfill({ json: { ...detail, handoff_text: packet } });
    });
    const root = page.locator('#platform-problems');
    const screenshot = async (name) => {
      await page.evaluate(() => document.fonts.ready);
      const metrics = await root.evaluate(node => ({
        width: document.documentElement.scrollWidth,
        headingFont: getComputedStyle(node.querySelector('h1')).fontFamily,
        headingColor: getComputedStyle(node.querySelector('h1')).color,
        gridColumns: getComputedStyle(node.querySelector('.support-grid')).gridTemplateColumns.split(' ').length,
      }));
      expect(metrics).toEqual({ width, headingFont: expect.stringContaining('Onest'),
        headingColor: 'rgb(34, 44, 48)', gridColumns: width === 1440 ? 2 : 1 });
      await page.screenshot({ path: info.outputPath(name + '-' + width + '.png'), fullPage: true, scale: 'css' });
    };
    await page.goto(preview.base + '/demo/superadmin/confirmed/');
    await page.getByRole('link', { name: 'Проблемы', exact: true }).click();
    await root.getByRole('link', { name: 'Приглашения', exact: true }).click();
    const row = root.getByRole('link', { name: 'Исход приглашения неизвестен' });
    await row.focus();
    await page.keyboard.press('Enter');
    await expect(root.getByRole('heading', { name: 'Исход приглашения неизвестен' })).toBeVisible();
    const check = root.getByRole('button', { name: 'Проверить отправку', exact: true });
    read = '503';
    await check.focus();
    await page.keyboard.press('Enter');
    await expect(root.getByRole('status')).toContainText('последний подтверждённый факт');
    await expect(root).toContainText('HTTP 503');
    await expect(root).toContainText(trace);
    await expect(root).toContainText(reference);
    await expect(check).toBeFocused();
    await screenshot('product-unknown');

    await root.getByRole('link', { name: 'Подготовить передачу' }).click();
    const copy = root.getByRole('button', { name: 'Скопировать сведения' });
    await copy.focus();
    await page.keyboard.press('Enter');
    await expect(root.getByRole('status').filter({ hasText: 'Сведения скопированы.' })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(packet + '\nКод обращения (запрос чтения): ' + trace);
    await screenshot('product-handoff');

    await root.getByRole('link', { name: 'К карточке проблемы' }).click();
    read = 'active';
    await check.click();
    await expect(root.getByRole('heading', { name: 'Отправка приглашения подтверждена' })).toBeVisible();
    await expect(root).toContainText(reference);
    await expect(root).toContainText('Ссылка действует до');
    await expect(root.getByRole('button', { name: /Повторно|Отправить/ })).toHaveCount(0);
    await screenshot('product-confirmed');
    read = 'expired';
    await check.click();
    await expect(root.getByText('Срок ссылки истёк', { exact: true }).first()).toBeVisible();
    read = 'used';
    await check.click();
    await expect(root.getByText('Ссылка использована', { exact: true }).first()).toBeVisible();
    expect(requests.filter(([method]) => method !== 'GET')).toEqual([]);
    expect(requests.filter(([, path]) => path === endpoint + '/' + reference)).toHaveLength(5);
    expect(errors).toEqual([]);
  });
}
