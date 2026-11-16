// Synthetic HTTP only; dedicated follow-up, no real user/storage/provider.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
const evidence = process.env.POSTW02_EVIDENCE;
const reference = process.env.POSTW02_REFERENCE;
test.skip(!evidence || !reference, 'Explicit bounded owner follow-up with local exact reference required');
let server, base;
const progress = async (key) => fs.writeFile(process.env.POSTW02_PROGRESS, JSON.stringify({ progress_key: key }));
test.beforeAll(async () => {
  await fs.mkdir(evidence, { recursive: true });
  server = http.createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      const file = pathname.startsWith('/reference/') ? path.join(reference, 'dist', pathname.slice(11))
        : path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.mjs': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.statusCode = 404; res.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  await fs.writeFile(path.join(evidence, 'server.json'), JSON.stringify({ pid: process.pid, port: server.address().port, db: null, llm: 0, mail: 0 }));
  await progress('server-start');
});
test.afterAll(async () => {
  if (!server?.listening) return;
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  await fs.writeFile(path.join(evidence, 'cleanup.json'), JSON.stringify({ port, listening: server.listening }));
});
const card = {
  cycle_id: 'synthetic-header-cycle', title: 'Совместная работа: тестовое назначение', organization_name: 'Синтетический центр «Вектор»',
  status: 'active', journey_state: 'active', status_label: 'Оценка идёт', description: 'Продолжите прохождение с текущей ситуации.',
  action: 'continue', button_label: 'Продолжить оценку →', planned_total: 5, current_position_no: 2, completed_cases: null,
  total_cases: 1, plan_revision_id: 'saved-header-plan', calendar_deadline: '2030-03-05T12:00:00Z',
};
const previous = { ...card, cycle_id: 'synthetic-header-previous', title: 'Тестовая программа команды',
  status: 'report_ready', journey_state: 'report_ready', status_label: 'Результат готов', report_id: 'header-report',
  action: 'open_report', button_label: 'Посмотреть результаты →', closed_at: '2030-02-13T12:00:00Z', current_position_no: null,
};
async function fixture(page, fullName) {
  const user = { id: 8, email: 'header@example.test', full_name: fullName };
  const dashboard = { greeting_name: 'коллега', current_assessments: [{ ...card }], completed_assessments: [{ ...previous }] };
  const calls = [], unexpected = [];
  await page.route('**/users/**', (route) => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    calls.push({ method: request.method(), pathname });
    const send = (body) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (pathname === '/users/version') return send({ version: '2.1.11' });
    if (pathname === '/users/session/restore') return send({ authenticated: true, user, dashboard });
    if (pathname === '/users/8/session-bootstrap') return send({ user, dashboard });
    if (pathname === '/users/8/journey-state') return send({ next_action: 'show_dashboard', can_open_dashboard: true,
      profile: { status: 'complete' }, onboarding: { status: 'completed', current_step: 8 },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: card.cycle_id } });
    unexpected.push(`${request.method()} ${pathname}`);
    return route.fulfill({ status: 500, body: 'unexpected' });
  });
  return { user, dashboard, calls, unexpected };
}
async function styles(page, selectors) {
  return page.evaluate((selectors) => Object.fromEntries(Object.entries(selectors).map(([name, selector]) => {
    const el = document.querySelector(selector), css = getComputedStyle(el), box = el.getBoundingClientRect();
    return [name, { x: box.x, y: box.y, width: box.width, height: box.height, background: css.backgroundColor,
      color: css.color, radius: css.borderRadius, display: css.display, columns: css.gridTemplateColumns, gap: css.gap,
      maxWidth: css.maxWidth, font: css.font, text: el.textContent }];
  })), selectors);
}
for (const width of [1440, 390]) {
  for (const fullName of ['Марина Тестова', null]) {
    test(`header ${fullName ? 'known' : 'fallback'} ${width}`, async ({ page, context }) => {
      test.setTimeout(60000);
      const key = `${fullName ? 'known' : 'fallback'}-${width}`;
      await progress(key);
      await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
      const run = await fixture(page, fullName), errors = [];
      page.on('pageerror', (e) => errors.push(e.message));
      await page.goto(base); await expect(page.locator('#dashboard-panel')).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      await expect(page.locator('#dashboard-user-name')).toHaveText(fullName || 'Участник');
      await expect(page.locator('#dashboard-avatar')).toHaveText(fullName ? 'МТ' : 'У');
      await expect(page.locator('[data-header-user-menu]')).toHaveAttribute('aria-label', `Меню пользователя: ${fullName || 'Участник'}`);
      if (width === 1440) await expect(page.locator('#dashboard-user-name')).toBeVisible();
      await expect(page.locator('#current-assessments h2')).toHaveText(card.title);
      await expect(page.locator('#current-assessments dl')).toContainText('2 ситуация из 5');
      await expect(page.locator('#current-assessments dl')).toContainText(card.organization_name);
      await expect(page.locator('#completed-assessments')).toContainText('13 февраля 2030');
      await expect(page.locator('#completed-assessments')).toContainText(previous.title);
      await expect(page.locator('#dashboard-panel')).not.toContainText('ООО «Север»');
      await expect(page.locator('#dashboard-panel')).not.toContainText('3 ситуация из 8');
      const actual = await styles(page, { header: '[data-app-header]', avatar: '#dashboard-avatar', status: '#current-assessments .participant-assessment-status',
        footer: '.app-footer', grid: '.dashboard-cabinet-grid', aside: '.dashboard-information', title: '#current-assessments h2' });
      expect(actual.avatar.width).toBe(32); expect(actual.avatar.height).toBe(32);
      expect(actual.avatar.radius).toBe('50%'); expect(actual.avatar.background).toBe('rgb(240, 240, 240)');
      expect(actual.avatar.color).toBe('rgb(34, 44, 48)'); expect(actual.status.background).toBe('rgb(250, 250, 250)');
      expect(actual.footer.color).toBe('rgba(100, 116, 139, 0.6)'); expect(actual.footer.background).toBe('rgb(247, 247, 247)');
      expect(actual.header.height).toBe(width === 1440 ? 72 : 64);
      expect(actual.grid.x).toBe(width === 1440 ? 160 : 16); expect(actual.grid.y).toBe(width === 1440 ? 208 : 200);
      expect(actual.grid.gap).toBe(width === 1440 ? '24px' : '16px'); expect(actual.aside.gap).toBe('16px');
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      await page.screenshot({ path: path.join(evidence, `${key}.png`), fullPage: true });
      if (fullName) {
        const refPage = await context.newPage(); await refPage.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
        await refPage.goto(`${base}/reference/report.html?scene=report-history-active`);
        await expect(refPage.locator('.personal-cabinet')).toBeVisible(); await refPage.evaluate(() => document.fonts.ready);
        const ref = await styles(refPage, { avatar: '.avatar', status: '.cabinet-status', footer: '.product-footer' });
        for (const prop of ['width', 'height', 'background', 'color', 'radius']) expect(actual.avatar[prop]).toBe(ref.avatar[prop]);
        expect(actual.status.background).toBe(ref.status.background); expect(actual.footer.color).toBe(ref.footer.color);
        await fs.writeFile(path.join(evidence, `exact-reference-${width}.json`), JSON.stringify({ actual, reference: ref }, null, 2));
        await refPage.close();
      }
      // Existing home actions re-render the saved dashboard; they do not start/prepare.
      await page.locator('#dashboard-cabinet-button').click();
      await expect(page.locator('#current-assessments dl')).toContainText('2 ситуация из 5');
      await page.locator('[data-header-home]').first().click();
      if (width === 1440) {
        const a = await page.locator('#dashboard-avatar').boundingBox(), exit = await page.locator('#dashboard-mobile-exit-button').boundingBox();
        const name = await page.locator('#dashboard-user-name').boundingBox();
        expect(name.x - (a.x + a.width)).toBe(10);
        expect(exit.x).toBeGreaterThan(a.x + a.width);
        expect(exit.x).toBeGreaterThan(name.x + name.width);
      } else {
        await page.locator('[data-header-user-menu]').focus();
        await expect(page.locator('.app-header-mobile-name')).toHaveText(fullName || 'Участник');
        await expect(page.locator('#dashboard-restart-button')).toBeVisible();
        await page.locator('#dashboard-cabinet-button').click();
        await page.setViewportSize({ width: 320, height: 844 });
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
      }
      if (fullName && width === 1440) {
        // Computed-style isolation only, not a new runtime path through another section.
        await page.evaluate(() => {
          document.getElementById('dashboard-panel').classList.add('hidden');
          document.getElementById('admin-panel').classList.remove('hidden');
        });
        await expect(page.locator('.app-footer')).not.toHaveClass(/app-footer--participant/);
        const legacy = await styles(page, { avatar: '#admin-avatar', footer: '.app-footer' });
        expect(legacy.avatar.width).toBe(36); expect(legacy.avatar.background).toBe('rgb(34, 44, 48)');
        expect(legacy.footer.color).toBe('rgb(104, 119, 124)');
      }
      expect(run.calls.every((call) => call.method === 'GET')).toBe(true); expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
      await fs.writeFile(path.join(evidence, `${key}.json`), JSON.stringify({ user: run.user, dashboard: run.dashboard, actual, calls: run.calls }, null, 2));
      await progress(`done-${key}`);
    });
  }
}
