// Controlled HTTP projections exercise the production frontend. Real SQL/HTTP is separate.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { w02Layout } from './fixtures/w02-layout.mjs';
let server, base;
const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
const resource = async (event, port) => {
  if (process.env.W02_RESOURCE_LOG) await fs.appendFile(process.env.W02_RESOURCE_LOG, JSON.stringify({ event, port, pid: process.pid, owner: 'P4K-W02-02', db: null }) + '\n');
};
test.beforeAll(async () => {
  server = http.createServer(async (req, res) => {
    try {
      const file = path.join(process.cwd(), new URL(req.url, 'http://localhost').pathname === '/' ? 'web/index.html' : new URL(req.url, 'http://localhost').pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.statusCode = 404; res.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  await resource('start', server.address().port);
});
test.afterAll(async () => {
  if (!server?.listening) return;
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve)); await resource('stop', port);
});
const plan = () => ({ cycle_id: 'w02-cycle', revision_id: 'w02-plan', revision_no: 1,
  start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'w02-cycle', plan_revision_id: 'w02-plan', can_start: true, reasons: [] },
  plan: { route: Array.from({ length: 5 }, () => ({ case_id: 'synthetic-case' })), time_budget_seconds: 4500, calendar_window_seconds: 172800,
    return_policy_snapshot: { resume_mode: 'replace_assessment_situation' } } });
const model = () => ({ assessment_name: 'Назначенная оценка — синтетический профиль', assignment_id: 91,
  readiness: { status: 'ready', organization_id: 10, assignment_ref: 'w02-assignment', questionnaire_revision_id: 41,
    briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1, consent_text: 'Synthetic consent' } },
  state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' }, consent_accepted_at: 'synthetic', consent_version: 1 },
  mandatory_complete: true, onboarding: { status: 'completed', current_step: 8 }, late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 }, prepared_plan: plan() });
const runtime = (active = true) => ({ runtime_kind: 'cycle', cycle_id: 'w02-cycle', cycle_session_id: 'w02-session', between_situations: false,
  return_policy_enabled: false, status: { collection_status: active ? 'active' : 'prepared', remaining_seconds: 4500 },
  route: { positions: [{ position_no: 1, state: active ? 'in_progress' : 'prepared', current_assessment_situation_id: 'w02-first-as' }], progress: { total_positions: 5 } },
  situations: [{ assessment_situation_id: 'w02-first-as', status: active ? 'active' : 'admitted' }],
  current_situation: { assessment_situation_id: 'w02-first-as', status: active ? 'active' : 'admitted', participant_payload: {
    title: 'Та же первая ситуация W02', situation: 'Синтетическое условие', assessee_task: 'Опишите решение.' } },
  trace: { turns: [], events: [] }, clarification: null, continuation: null, pipeline: null });
async function fixture(page, scene = 'ready') {
  const m = model(), calls = [], startKeys = [];
  let active = false, startAttempts = 0, readError = false, held = null;
  const localErrors = { network: 'network', service: 503, access: 403, conflict: 409 };
  if (scene === 'organization') { m.prepared_plan = null; m.late_readiness.status = 'waiting_for_assessment_data'; }
  if (['preparing', 'failed', 'failed-locked', 'missing', 'network', 'service', 'access', 'conflict'].includes(scene)) m.prepared_plan = null;
  if (['failed', 'failed-locked'].includes(scene)) m.preparation_operation = { operation_id: 'w02-op', status: 'failed', retry_allowed: scene === 'failed', error: { message: 'Unsafe: обратитесь к организатору.', code: 'INTERNAL' } };
  if (scene === 'preparing') m.preparation_operation = { operation_id: 'w02-op', status: 'queued' };
  if (scene === 'missing') m.preparation_operation = { operation_id: 'w02-op', status: 'completed' };
  if (scene === 'blocked') m.prepared_plan.start_readiness.can_start = false;
  if (scene === 'incomplete') { m.preparation_operation = { operation_id: 'w02-op', status: 'running' }; }
  if (scene === 'unassigned') m.readiness.status = 'waiting_for_assignment';
  if (scene === 'expired') m.readiness.status = 'expired';
  if (scene.startsWith('start-')) await page.addInitScript(() => sessionStorage.setItem('assessment-start-pending:w02-cycle', 'same-operation-key'));
  await page.route('**/users/**', async (route) => {
    const req = route.request(), pathname = new URL(req.url()).pathname;
    calls.push({ path: pathname, method: req.method(), body: req.postData() });
    const user = { id: 8, email: 'synthetic@example.test', full_name: 'Synthetic' };
    if (pathname === '/users/session/restore') return json(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return json(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return json(route, { next_action: ['unassigned', 'expired'].includes(scene) ? 'wait_for_acquaintance_data' : 'show_onboarding',
      acquaintance: m, profile: { status: 'complete' }, onboarding: m.onboarding, assessment: { status: 'not_started' } });
    if (pathname === '/users/8/acquaintance') {
      if (held) await held;
      if (readError || scene === 'load-error') return route.abort('failed');
      return json(route, m);
    }
    if (pathname === '/users/8/acquaintance/resolve-profile') return json(route, m);
    if (pathname === '/users/8/onboarding') { m.onboarding = req.postDataJSON(); return json(route, m.onboarding); }
    if (pathname === '/users/assessment/cycles/prepare') {
      if (scene in localErrors) return localErrors[scene] === 'network' ? route.abort('failed') : json(route, { detail: 'controlled refusal' }, localErrors[scene]);
      expect(m.preparation_operation?.retry_allowed).toBe(true);
      m.prepared_plan = plan(); m.preparation_operation = { operation_id: req.postDataJSON().idempotency_key, status: 'completed', result: { plan: m.prepared_plan } };
      return json(route, m.preparation_operation, 202);
    }
    if (pathname.startsWith('/users/assessment/cycles/preparation/')) return json(route, m.preparation_operation);
    if (pathname === '/users/assessment/cycles/start') {
      startKeys.push(req.postDataJSON()); startAttempts++;
      if (scene === 'denied') { m.readiness.status = 'waiting_for_assignment'; return json(route, { detail: 'ASSIGNMENT_CANCELLED' }, 409); }
      if (scene === 'lost-before' && startAttempts === 1) return route.abort('failed');
      active = true; return json(route, { plan: m.prepared_plan, runtime: runtime() }, 201);
    }
    if (pathname === '/users/assessment/cycles/w02-cycle/runtime') {
      if (scene === 'start-access') { m.readiness.status = 'waiting_for_assignment'; return json(route, { detail: 'ASSIGNMENT_CANCELLED' }, 403); }
      return scene === 'start-unknown' ? json(route, {}, 503) : json(route, runtime(active));
    }
    if (pathname.includes('/return-state')) return json(route, { detail: 'M7_RETURN_CURRENT_POSITION_NOT_FOUND' }, 409);
    if (pathname === '/users/auth/logout' || pathname === '/users/logout') return json(route, {});
    if (pathname === '/users/version') return json(route, { version: 'w02-controlled' });
    throw new Error(`Unexpected frontend request: ${req.method()} ${pathname}`);
  });
  return { m, calls, startKeys, failRead: () => { readError = true; }, hold: () => { let release; held = new Promise((r) => { release = r; }); return () => { held = null; release(); }; } };
}
const forbiddenCommands = (calls) => calls.filter((c) => /\/(prepare|start)$/.test(c.path) && c.method === 'POST');
const titles = { ready: 'Можно приступать к оценке', preparing: 'Готовим вашу оценку', organization: 'Нужны сведения организации',
  unassigned: 'Оценка пока не назначена', expired: 'Срок доступа к оценке закончился', 'load-error': 'Не удалось загрузить знакомство',
  network: 'Не удалось проверить готовность', service: 'Подготовка временно недоступна', failed: 'Не удалось подготовить оценку',
  'failed-locked': 'Не удалось подготовить оценку', access: 'Доступ к оценке изменился', conflict: 'Состояние оценки изменилось',
  blocked: 'Старт оценки пока недоступен', missing: 'Подготовленный план пока недоступен', 'start-unknown': 'Проверяем начало оценки',
  'start-retry': 'Проверяем начало оценки' };
for (const [scene, title] of Object.entries(titles)) {
  test(`W02-02 state ${scene}: server actions and no contact`, async ({ page }) => {
    const run = await fixture(page, scene);
    await page.goto(base);
    const panel = ['unassigned', 'expired'].includes(scene) ? page.locator('#auth-complete-panel') : page.locator('#onboarding-panel');
    await expect(panel.getByRole('heading', { name: title, exact: true })).toBeVisible();
    await expect(panel).not.toContainText(/Обратитесь|ответственному|организатору|управление/i);
    if (!['unassigned', 'expired'].includes(scene)) {
      await expect(panel.locator('#onboarding-status-icon')).toBeVisible();
      await expect(panel.locator('.onboarding-section-label')).toHaveText('Оценка');
      if (scene === 'preparing') {
        await expect(panel.locator('.onboarding-live')).toHaveText('Подготовка выполняется');
        expect(run.m.preparation_operation.status).toBe('queued');
        run.m.preparation_operation.status = 'running';
        await page.reload();
        await expect(panel.locator('.onboarding-live')).toHaveText('Подготовка выполняется');
      }
      if (scene !== 'load-error') await expect(panel.locator('#onboarding-status-tail #onboarding-view-history')).toBeVisible();
      else await expect(panel.locator('#onboarding-view-history')).toHaveCount(0);
      await expect(panel.locator('#onboarding-logout')).toHaveCount(scene === 'access' ? 1 : 0);
      if (['preparing', 'organization', 'failed-locked'].includes(scene)) {
        expect(await panel.locator('#onboarding-next').evaluate((n) => getComputedStyle(n).backgroundColor)).toBe('rgb(255, 255, 255)');
      }
    }
    if (scene !== 'ready') await expect(panel.getByRole('button', { name: 'Приступить к оценке', exact: true })).toHaveCount(0);
    if (scene === 'failed') {
      await expect(panel.getByRole('button', { name: 'Повторить подготовку', exact: true })).toBeVisible();
      await panel.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
      expect(forbiddenCommands(run.calls)).toHaveLength(0);
      await panel.getByRole('button', { name: 'Повторить подготовку', exact: true }).click();
      await expect(page.locator('#onboarding-title')).toHaveText(titles.ready);
      expect(forbiddenCommands(run.calls)).toHaveLength(1);
    } else if (scene === 'failed-locked') await expect(panel.getByRole('button', { name: 'Повторить подготовку' })).toHaveCount(0);
    else if (scene === 'start-retry') {
      await panel.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
      await expect(page.locator('#onboarding-title')).toHaveText('Начало оценки ещё не подтверждено');
      await expect(panel.getByRole('button', { name: 'Повторить старт', exact: true })).toBeVisible();
      expect(forbiddenCommands(run.calls)).toHaveLength(0);
    } else if (!['network', 'service', 'access', 'conflict'].includes(scene)) expect(forbiddenCommands(run.calls)).toHaveLength(0);
    if (scene === 'blocked') {
      await page.locator('#onboarding-next').click(); expect(run.startKeys).toHaveLength(0);
    }
  });
}
test('W02-02 loading shows only factual loading until GET resolves', async ({ page }) => {
  const run = await fixture(page); const release = run.hold();
  await page.goto(base); await expect(page.locator('#onboarding-title')).toHaveText('Загружаем знакомство');
  await expect(page.locator('#onboarding-next')).toBeDisabled(); await expect(page.locator('.onboarding-metrics')).toHaveCount(0);
  release(); await expect(page.locator('#onboarding-title')).toHaveText(titles.ready); expect(forbiddenCommands(run.calls)).toHaveLength(0);
});
for (const width of [1440, 390, 320]) {
  test(`W02-02 ready/organization/unknown and footer at ${width}px`, async ({ browser }, info) => {
    for (const scene of ['ready', 'organization', 'start-unknown']) {
      const context = await browser.newContext({ viewport: { width, height: width === 1440 ? 1024 : 844 } });
      try {
        const page = await context.newPage(); const run = await fixture(page, scene); await page.goto(base);
        await expect(page.locator('#onboarding-title')).toHaveText(titles[scene]);
        if (scene === 'ready') {
          await expect(page.locator('#onboarding-description')).toContainText('Назначенная оценка');
          await expect(page.locator('.onboarding-metrics')).toContainText('5ситуаций в плане75 мин');
          await expect(page.locator('#feature-list')).toContainText('48 ч.');
          await expect(page.locator('#feature-list')).toContainText('будет заменена');
          expect(await page.locator('#onboarding-next').evaluate((n) => getComputedStyle(n).backgroundColor)).toBe('rgb(24, 184, 198)');
        }
        if (width === 320) await page.locator('#onboarding-description').evaluate((n) => { n.textContent += ' Длинное сообщение '.repeat(25); });
        await page.locator('#onboarding-next').scrollIntoViewIfNeeded();
        await page.locator('#onboarding-next').focus(); await expect(page.locator('#onboarding-next')).toBeFocused();
        await page.locator('.app-footer').scrollIntoViewIfNeeded(); await expect(page.locator('.app-footer')).toBeInViewport();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
        expect(run.startKeys).toHaveLength(0);
        if (width !== 320) {
          const screenshot = `${scene}-${width}.png`;
          const target = process.env.W02_EVIDENCE_DIR ? path.join(process.env.W02_EVIDENCE_DIR, screenshot) : info.outputPath(screenshot);
          await page.screenshot({ path: target, fullPage: true });
        }
      } finally { await context.close(); }
    }
  });
}
test('W02-02 history returns to readiness without preparation and explicit start presents same AS with zero answers', async ({ page }) => {
  const run = await fixture(page); await page.goto(base);
  await page.getByRole('button', { name: 'Посмотреть знакомство', exact: true }).click();
  await expect(page.locator('#onboarding-title')).toHaveText('Знакомство завершено');
  await expect(page.locator('#onboarding-messages')).toContainText('A');
  await expect(page.locator('.onboarding-answer')).toBeDisabled();
  await page.getByRole('button', { name: 'Вернуться к готовности оценки' }).click();
  await expect(page.locator('#onboarding-title')).toHaveText(titles.ready);
  expect(forbiddenCommands(run.calls)).toHaveLength(0);
  await page.getByRole('button', { name: 'Приступить к оценке', exact: true }).click({ clickCount: 2 });
  await expect(page.locator('#interview-case-title')).toHaveText('Та же первая ситуация W02');
  expect(run.startKeys).toHaveLength(1); expect(run.startKeys[0].cycle_id).toBe('w02-cycle');
  expect(run.calls.filter((c) => /answer|turns|next$/.test(c.path) && c.method !== 'GET')).toHaveLength(0);
});
test('W02-02 lost uncommitted start reload/readback/retry keeps original operation and first AS', async ({ page }) => {
  const run = await fixture(page, 'lost-before'); await page.goto(base);
  await page.getByRole('button', { name: 'Приступить к оценке', exact: true }).click();
  await expect(page.locator('#onboarding-title')).toHaveText('Проверяем начало оценки');
  await page.reload(); await expect(page.locator('#onboarding-title')).toHaveText('Проверяем начало оценки');
  await page.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
  await expect(page.locator('#onboarding-title')).toHaveText('Начало оценки ещё не подтверждено');
  expect(run.startKeys).toHaveLength(1);
  await page.getByRole('button', { name: 'Повторить старт', exact: true }).click();
  await expect(page.locator('#interview-case-title')).toHaveText('Та же первая ситуация W02');
  expect(run.startKeys).toHaveLength(2); expect(run.startKeys[0]).toEqual(run.startKeys[1]);
});
test('W02-02 checking failed network reads the same operation after reload and never prepares again', async ({ page }) => {
  const run = await fixture(page, 'failed-locked'); await page.goto(base);
  await expect(page.locator('#onboarding-title')).toHaveText('Не удалось подготовить оценку');
  run.failRead(); await page.locator('#onboarding-next').click();
  await expect(page.locator('#onboarding-title')).toHaveText('Не удалось проверить готовность');
  expect(forbiddenCommands(run.calls)).toHaveLength(0);
});

for (const scene of ['denied', 'start-access']) {
  test(`W02-02 ${scene} rereads own assignment and never bypasses refusal`, async ({ page }) => {
    const run = await fixture(page, scene); await page.goto(base);
    await expect(page.locator('#onboarding-title')).toHaveText(scene === 'denied' ? titles.ready : titles['start-unknown']);
    await page.locator('#onboarding-next').click();
    await expect(page.locator('#auth-complete-title')).toHaveText('Оценка пока не назначена');
    await expect(page.locator('#interview-panel')).toBeHidden();
    expect(run.calls.filter((c) => c.path === '/users/8/acquaintance' && c.method === 'GET').length).toBeGreaterThanOrEqual(2);
    expect(run.startKeys).toHaveLength(scene === 'denied' ? 1 : 0);
    expect(run.calls.filter((c) => c.path.endsWith('/prepare') && c.method === 'POST')).toHaveLength(0);
  });
}

test('W02-02 an incomplete preparation keeps explicit start closed', async ({ page }) => {
  const run = await fixture(page, 'incomplete'); await page.goto(base);
  await expect(page.locator('#onboarding-title')).toHaveText('Готовим вашу оценку');
  await expect(page.getByRole('button', { name: 'Приступить к оценке', exact: true })).toHaveCount(0);
  await page.locator('#onboarding-next').click();
  expect(forbiddenCommands(run.calls)).toHaveLength(0);
  await expect.poll(() => run.calls.filter((c) => c.path.includes('/preparation/')).length).toBeGreaterThanOrEqual(1);
  await expect(page.locator('#onboarding-next')).toBeEnabled();
  expect(forbiddenCommands(run.calls)).toHaveLength(0);
});

if (process.env.W02_ADD01_EVIDENCE) for (const width of [1440, 390]) for (const scene of ['preparing', 'failed-locked', 'ready']) {
  test(`W02 ADD01 product ${scene} ${width}`, async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width, height: width === 1440 ? 1024 : 844 }, deviceScaleFactor: 1 });
    try {
      const page = await context.newPage(), run = await fixture(page, scene);
      await page.goto(base);
      await expect(page.locator('#onboarding-title')).toHaveText(titles[scene]);
      await page.evaluate(() => document.fonts.ready);
      await expect(page.locator('.onboarding-section-label')).toHaveText('Оценка');
      if (scene === 'preparing') {
        await expect(page.locator('.onboarding-live')).toHaveText('Подготовка выполняется');
        await expect(page.locator('#onboarding-panel')).not.toContainText('Операция в очереди');
        expect(run.m.preparation_operation.status).toBe('queued');
      }
      if (scene === 'failed-locked') {
        await expect(page.locator('.onboarding-diagnostics')).not.toHaveAttribute('open', '');
        await expect(page.getByText('Код операции: w02-op')).toBeHidden();
      }
      await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.evaluate(() => window.scrollTo(0, 0));
      const layout = await w02Layout(page);
      expect(layout.viewport.scrollWidth).toBeLessThanOrEqual(width);
      expect(layout.main.bottom).toBeLessThanOrEqual(layout.footer.y + 1);
      // Center the entire card + history group in the space left by the real footer.
      if (layout.group.height + 2 * (width === 1440 ? 32 : 24) < layout.main.height) {
        expect(Math.abs((layout.group.y + layout.group.height / 2) - (layout.main.y + layout.main.height / 2))).toBeLessThan(1);
      }
      const target = path.join(process.env.W02_EVIDENCE_DIR, `${scene}-${width}.png`);
      await page.screenshot({ path: target, fullPage: false });
      await fs.writeFile(target.replace('.png', '.json'), JSON.stringify({ layout: await w02Layout(page), server_operation: run.m.preparation_operation, commands: forbiddenCommands(run.calls) }, null, 2));
      const refresh = page.getByRole('button', { name: scene === 'preparing' ? 'Проверить готовность' : 'Проверить состояние', exact: true });
      if (scene !== 'ready') await refresh.click();
      expect(forbiddenCommands(run.calls)).toHaveLength(0);
    } finally { await context.close(); }
  });
}
