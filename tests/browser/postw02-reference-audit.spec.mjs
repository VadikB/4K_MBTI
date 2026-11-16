// Audit only: exact v10 served unchanged, product e1b07b3, synthetic owner HTTP.
// A passing runner means evidence was collected, not that visual equivalence passed.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
let server, base;
const reference = process.env.POSTW02_REFERENCE;
const evidence = process.env.POSTW02_EVIDENCE;
// This read-only audit requires an explicitly supplied immutable reference checkout.
// Generic repository CI must not fetch Sites or depend on an owner's local path.
test.skip(!reference || !evidence, 'Manual exact-reference audit; explicit POSTW02_REFERENCE and POSTW02_EVIDENCE required');
const scenes = ['active', 'preparing', 'ready', 'return', 'result'];
const program = 'Универсальные навыки в работе';
const organization = 'ООО «Север»';
const longTitle = 'Оценка универсальных компетенций специалистов по сопровождению сложных межфункциональных проектов и работе с клиентами';
const copy = {
  active: ['active', 'active', 'Оценка начата', 'Продолжите с того же места.', 'continue', 'Продолжить'],
  preparing: ['preparing', 'preparing', 'Оценка готовится', 'Подготавливаем ситуации по вашему плану. Время выполнения ещё не идёт.', 'open_readiness', 'Посмотреть готовность'],
  ready: ['prepared', 'ready', 'Готова к началу', 'Ваша оценка подготовлена. Время выполнения ещё не идёт.', 'open_readiness', 'Приступить к оценке'],
  return: ['active', 'return_required', 'Возвращение к оценке', 'Откройте оценку и подтвердите продолжение на экране возврата.', 'continue', 'Продолжить'],
  result: ['report_ready', 'report_ready', 'Результат готов', 'Результат оценки доступен для просмотра.', 'open_report', 'Посмотреть результат'],
};
const progress = async (key) => fs.writeFile(process.env.POSTW02_PROGRESS, JSON.stringify({ progress_key: key }));
test.beforeAll(async () => {
  if (!reference || !evidence) throw new Error('Explicit reference/evidence paths required');
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
  await fs.writeFile(path.join(evidence, 'server.json'), JSON.stringify({ pid: process.pid, port: server.address().port, reference, db: null, llm: 0, mail: 0 }));
  await progress('server-start');
});
test.afterAll(async () => {
  if (!server?.listening) return;
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  await fs.writeFile(path.join(evidence, 'cleanup.json'), JSON.stringify({ port, listening: server.listening }));
});
async function fixture(page, scene, title) {
  const [status, journey_state, status_label, description, action, button_label] = copy[scene];
  const card = { cycle_id: 'synthetic-current', title, organization_name: organization, status, journey_state, status_label, description, action, button_label,
    planned_total: scene === 'preparing' ? null : 8, total_cases: scene === 'preparing' ? null : 8, current_position_no: ['active', 'return'].includes(scene) ? 3 : null,
    completed_cases: null, plan_revision_id: scene === 'preparing' ? null : 'synthetic-plan', calendar_deadline: ['active', 'return'].includes(scene) ? '2026-11-19T12:00:00Z' : null,
    closed_at: scene === 'result' ? '2026-10-17T12:00:00Z' : null, report_id: scene === 'result' ? 'synthetic-result' : null };
  const history = [
    { ...card, cycle_id: 'synthetic-previous-1', title: program, status: 'report_ready', journey_state: 'report_ready', status_label: 'Результат готов', description: 'Результат оценки доступен для просмотра.', action: 'open_report', button_label: 'Посмотреть результат', planned_total: 8, total_cases: 8, current_position_no: null, calendar_deadline: null, closed_at: '2026-08-15T12:00:00Z', report_id: 'synthetic-report-1' },
    { ...card, cycle_id: 'synthetic-previous-2', title: 'Работа руководителя', status: 'report_ready', journey_state: 'report_ready', status_label: 'Результат готов', description: 'Результат оценки доступен для просмотра.', action: 'open_report', button_label: 'Посмотреть результат', planned_total: 8, total_cases: 8, current_position_no: null, calendar_deadline: null, closed_at: '2026-05-18T12:00:00Z', report_id: 'synthetic-report-2' },
  ];
  const dashboard = { current_assessments: scene === 'result' ? [] : [card], completed_assessments: scene === 'result' ? [card, ...history] : history };
  const calls = [], unexpected = [];
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  await page.route('**/users/**', (route) => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    calls.push({ method: request.method(), pathname });
    const respond = (body) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (pathname === '/users/version') return respond({ version: '2.1.11' });
    if (pathname === '/users/session/restore') return respond({ authenticated: true, user, dashboard });
    if (pathname === '/users/8/session-bootstrap') return respond({ user, dashboard });
    if (pathname === '/users/8/journey-state') return respond({ next_action: 'show_dashboard', can_open_dashboard: true, profile: { status: 'complete' }, onboarding: { status: 'completed', current_step: 8 }, assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: card.cycle_id } });
    unexpected.push(`${request.method()} ${pathname}`);
    return route.fulfill({ status: 500, body: 'Unexpected fixture request' });
  });
  return { calls, unexpected, card };
}
const selectors = {
  reference: { header: '.product-header', heading: '.personal-cabinet h1', subtitle: '.heading-row .meta', grid: '.cabinet-grid', current: '.cabinet-current', top: '.cabinet-card-top', org: '.cabinet-organization', status: '.cabinet-status', title: '.cabinet-current h2', description: '.cabinet-description', metadata: '.cabinet-meta', term: '.cabinet-meta dt', detail: '.cabinet-meta dd', action: '.cabinet-current .primary, .cabinet-current .secondary', aside: '.cabinet-aside', info: '.cabinet-aside .card', infoTitle: '.cabinet-aside h3', infoText: '.cabinet-aside p', history: '.cabinet-history', historyTitle: '.cabinet-history h2', historyList: '.history-list', row: '.history-item', rowTitle: '.history-item h3', rowText: '.history-item p', rowAction: '.history-item .secondary', footer: '.product-footer' },
  product: { header: '#dashboard-panel .dashboard-topbar', heading: '#dashboard-greeting', subtitle: '#dashboard-panel .dashboard-subtitle', grid: '.dashboard-cabinet-grid', current: '#current-assessments .participant-assessment-card', top: '#current-assessments .participant-assessment-top', org: '#current-assessments .participant-assessment-organization', status: '#current-assessments .participant-assessment-status', title: '#current-assessments h4', description: '#current-assessments .participant-assessment-description', metadata: '#current-assessments .participant-assessment-metadata', term: '#current-assessments dt', detail: '#current-assessments dd', action: '#assessment-action-button', aside: '.dashboard-information', info: '.dashboard-info-card', infoTitle: '.dashboard-info-card h3', infoText: '.dashboard-info-card p', history: '.dashboard-history', historyTitle: '.dashboard-history > .dashboard-section-title', historyList: '#completed-assessments', row: '#completed-assessments article', rowTitle: '#completed-assessments h4', rowText: '#completed-assessments .participant-assessment-description', rowAction: '#completed-assessments .participant-assessment-action', footer: '.app-footer' },
};
async function measure(page, kind) {
  return page.evaluate((mapping) => {
    const props = ['display', 'fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'color', 'backgroundColor', 'borderTopWidth', 'borderTopColor', 'borderRadius', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'marginTop', 'marginBottom', 'gap', 'gridTemplateColumns', 'minHeight', 'boxShadow', 'alignItems', 'flexWrap'];
    const nodes = {};
    for (const [key, selector] of Object.entries(mapping)) {
      nodes[key] = [...document.querySelectorAll(selector)].map((el) => {
        const rect = el.getBoundingClientRect(), css = getComputedStyle(el);
        return { text: el.innerText, tag: el.tagName, x: rect.x, y: rect.y, width: rect.width, height: rect.height,
          css: Object.fromEntries(props.map((prop) => [prop, css[prop]])) };
      });
    }
    return { nodes, viewport: { width: innerWidth, height: innerHeight }, scrollWidth: document.documentElement.scrollWidth, pageHeight: document.documentElement.scrollHeight, fontsLoaded: document.fonts.check('16px Onest') };
  }, selectors[kind]);
}
for (const width of [1440, 390]) {
  for (const scene of scenes) {
    test(`exact v10 / product ${scene} ${width}`, async ({ page, context }) => {
      test.setTimeout(60000);
      await progress(`${scene}-${width}`);
      await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
      const errors = []; page.on('pageerror', (e) => errors.push(e.message));
      await page.goto(`${base}/reference/report.html?scene=report-history${scene === 'result' ? '' : `-${scene}`}`);
      await expect(page.locator('.personal-cabinet')).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      const ref = await measure(page, 'reference');
      await page.screenshot({ path: path.join(evidence, `${scene}-${width}-reference.png`), fullPage: true });
      const productPage = await context.newPage();
      await productPage.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
      productPage.on('pageerror', (e) => errors.push(e.message));
      const run = await fixture(productPage, scene, program);
      await productPage.goto(base);
      await expect(productPage.locator('#dashboard-panel')).toBeVisible();
      await productPage.evaluate(() => document.fonts.ready);
      const product = await measure(productPage, 'product');
      await productPage.screenshot({ path: path.join(evidence, `${scene}-${width}-product.png`), fullPage: true });
      expect(ref.fontsLoaded).toBe(true); expect(product.fontsLoaded).toBe(true);
      expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
      expect(run.calls.every((call) => call.method === 'GET')).toBe(true);
      await fs.writeFile(path.join(evidence, `${scene}-${width}.json`), JSON.stringify({ reference: ref, product, requests: run.calls }, null, 2));
      if (scene === 'active') {
        // Only dynamic title changes in reference DOM; all CSS/source stays exact v10.
        await page.locator('.cabinet-current h2').evaluate((node, title) => { node.textContent = title; }, longTitle);
        await page.screenshot({ path: path.join(evidence, `long-${width}-reference.png`), fullPage: true });
        const stressPage = await context.newPage();
        await stressPage.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
        const stress = await fixture(stressPage, scene, longTitle);
        await stressPage.goto(base); await expect(stressPage.locator('#dashboard-panel')).toBeVisible();
        await stressPage.evaluate(() => document.fonts.ready);
        await stressPage.screenshot({ path: path.join(evidence, `long-${width}-product.png`), fullPage: true });
        await fs.writeFile(path.join(evidence, `long-${width}.json`), JSON.stringify({ reference: await measure(page, 'reference'), product: await measure(stressPage, 'product'), reference_dom_change: 'current title text only', requests: stress.calls }, null, 2));
        await stressPage.close();
      }
      await productPage.close();
      await progress(`done-${scene}-${width}`);
    });
  }
}
test('320 overflow only', async ({ page }) => {
  test.setTimeout(60000);
  await progress('overflow-320');
  await page.setViewportSize({ width: 320, height: 844 });
  const result = {};
  for (const scene of scenes) {
    await page.goto(`${base}/reference/report.html?scene=report-history${scene === 'result' ? '' : `-${scene}`}`);
    await expect(page.locator('.personal-cabinet')).toBeVisible();
    const referenceWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    await page.unroute('**/users/**'); await fixture(page, scene, longTitle);
    await page.goto(base); await expect(page.locator('#dashboard-panel')).toBeVisible();
    const productWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    result[scene] = { referenceWidth, productWidth, viewportWidth: 320 };
    expect(referenceWidth).toBe(320); expect(productWidth).toBe(320);
  }
  await fs.writeFile(path.join(evidence, 'overflow-320.json'), JSON.stringify(result, null, 2));
  await progress('done-overflow-320');
});

test('breakpoint and interactive style probes', async ({ page, context }) => {
  test.setTimeout(60000);
  const productPage = await context.newPage();
  await fixture(productPage, 'active', program);
  const results = {};
  for (const width of [1440, 1050, 801, 800, 680, 560, 390]) {
    await progress(`probe-${width}`);
    await page.setViewportSize({ width, height: 1000 });
    await productPage.setViewportSize({ width, height: 1000 });
    await page.goto(`${base}/reference/report.html?scene=report-history-active`);
    await productPage.goto(base);
    await expect(page.locator('.personal-cabinet')).toBeVisible();
    await expect(productPage.locator('#dashboard-panel')).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await productPage.evaluate(() => document.fonts.ready);
    results[width] = { reference: await measure(page, 'reference'), product: await measure(productPage, 'product') };
    if (width === 1440) {
      for (const [kind, target, selector] of [['reference', page, '.cabinet-current .primary'], ['product', productPage, '#assessment-action-button']]) {
        const button = target.locator(selector);
        await button.hover();
        // Both implementations have optional transitions; wait for the finished paint.
        await target.waitForTimeout(250);
        const hovered = await button.evaluate((el) => getComputedStyle(el).backgroundColor);
        await target.mouse.move(0, 0);
        await target.keyboard.press('Tab');
        await button.focus();
        const focused = await button.evaluate((el) => { const css = getComputedStyle(el); return { outlineWidth: css.outlineWidth, outlineColor: css.outlineColor, outlineOffset: css.outlineOffset }; });
        results[width][kind].interactive = { hovered, focused };
      }
      for (const [kind, target, selectors] of [
        ['reference', page, ['.product-footer div span', '.product-footer p']],
        ['product', productPage, ['.app-footer-documents a', '.app-footer-copyright']],
      ]) {
        results[width][kind].footerContent = await target.evaluate((selectors) => selectors.map((selector) => [...document.querySelectorAll(selector)].map((el) => { const css = getComputedStyle(el); return { text: el.textContent, font: css.font, color: css.color, letterSpacing: css.letterSpacing }; })), selectors);
      }
    }
  }
  await fs.writeFile(path.join(evidence, 'probes.json'), JSON.stringify(results, null, 2));
  await productPage.close();
  await progress('done-probes');
});

test('local comparison report renders and switches pairs', async ({ page }) => {
  test.setTimeout(60000);
  await progress('report-preview');
  const errors = []; page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${base}/docs/evc/tasks/p4k-postw02-01/REFERENCE_COMPARISON.html`);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('не соответствует');
  await expect(page.locator('#findings details')).toHaveCount(18);
  await expect(page.locator('#metrics')).toContainText('254');
  await page.locator('#scene').selectOption('preparing');
  await expect(page.locator('#copy')).toContainText('Отсутствует');
  await page.locator('#width').selectOption('390');
  await expect(page.locator('#ref')).toHaveAttribute('src', /preparing-390-reference/);
  await page.locator('#mode').selectOption('overlay');
  await expect(page.locator('#overlay')).toBeVisible();
  await expect(page.locator('#pair')).toBeHidden();
  await expect.poll(() => page.locator('#overlay').evaluate((el) => el.getBoundingClientRect().height)).toBeGreaterThan(1000);
  for (const mode of ['pair', 'overlay']) {
    await page.locator('#mode').selectOption(mode);
    await page.locator('#scene').selectOption('active');
    await page.screenshot({ path: path.join(evidence, `report-${mode}.png`), fullPage: false });
  }
  expect(errors).toEqual([]);
  await progress('done-report-preview');
});
