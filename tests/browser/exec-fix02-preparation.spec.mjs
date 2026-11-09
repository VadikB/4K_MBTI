/** EXEC-FIX-02 component browser regressions. APIs are explicit synthetic
 * participant-safe projections; real owned PostgreSQL/HTTP tests are separate.
 */
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const root = process.cwd();
let server;
let base;
const user = { id: 8, email: 'synthetic@example.test', full_name: 'Synthetic participant' };
const technical = { code: 'ASSESSMENT_CYCLE_PREPARATION_TECHNICAL_FAILURE',
  message: 'Подготовка завершилась технической ошибкой. Ваши ответы сохранены; можно запустить её повторно.' };
const admission = { code: 'ASSESSMENT_AS_NOT_ADMITTED',
  message: 'Ситуация не прошла обязательную проверку. Ваши ответы сохранены; обратитесь к ответственному за оценку.' };
const json = (route, body, status = 200) => route.fulfill({ status,
  contentType: 'application/json', body: JSON.stringify(body) });

test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
      const filename = path.join(root, pathname === '/' ? 'web/index.html' : pathname);
      const body = await fs.readFile(filename);
      response.setHeader('Content-Type', ({ '.css': 'text/css', '.html': 'text/html',
        '.js': 'application/javascript', '.svg': 'image/svg+xml', '.woff': 'font/woff' })[path.extname(filename)] || 'application/octet-stream');
      response.end(body);
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => { if (server) await new Promise((resolve) => server.close(resolve)); });

for (const retryAllowed of [true, false]) {
  test(`EXEC-FIX-02 first preparation safe failure/reload explicit retry=${retryAllowed}`, async ({ page }, testInfo) => {
    let posts = 0;
    let completed = false;
    let operation = { operation_id: 'first-failed', status: 'failed', retry_allowed: retryAllowed,
      error: retryAllowed ? technical : admission };
    const plan = { cycle_id: 'cycle-first', revision_id: 'revision-first', revision_no: 1,
      start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-first', plan_revision_id: 'revision-first',
        can_start: true, reasons: [] }, plan: { status: 'READY', route: [{ case_id: 'CASE.SPEC.02' }],
        time_budget_seconds: 7200, calendar_window_seconds: 259200 } };
    const acquaintance = () => ({ readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic',
      questionnaire_revision_id: 1, briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } },
      state: { answers_json: { answer_1: 'Saved A', answer_2: 'Saved B', answer_3: 'Saved C' },
        consent_accepted_at: 'synthetic', consent_version: 1, answers_confirmed_at: 'synthetic' },
      mandatory_complete: true, onboarding: { status: 'completed', current_step: 8 },
      late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
      preparation_operation: operation, prepared_plan: completed ? plan : null });
    await page.route('**/users/**', (route) => {
      const request = route.request(); const pathname = new URL(request.url()).pathname;
      if (pathname === '/users/session/restore') return json(route, { authenticated: true, user, is_admin: false, dashboard: {} });
      if (pathname === '/users/8/session-bootstrap') return json(route, { user, is_admin: false, dashboard: {} });
      if (pathname === '/users/8/journey-state') return json(route, { next_action: 'show_onboarding', acquaintance: acquaintance(),
        profile: { status: 'complete' }, onboarding: { status: 'completed', current_step: 8 }, assessment: { status: 'not_started' } });
      if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) return json(route, acquaintance());
      if (pathname === '/users/8/onboarding') return json(route, { status: 'completed', current_step: 8 });
      if (pathname === '/users/assessment/cycles/prepare' && request.method() === 'POST') {
        posts += 1; expect(retryAllowed).toBe(true);
        operation = { operation_id: request.postDataJSON().idempotency_key, status: 'completed', result: { plan } };
        completed = true;
        return json(route, operation, 202);
      }
      if (pathname.startsWith('/users/assessment/cycles/preparation/')) return json(route, operation);
      if (pathname === '/users/version') return json(route, { version: 'exec-fix02-component' });
      return json(route, {}, 404);
    });
    await page.goto(base);
    await expect(page.locator('#onboarding-title')).toHaveText('Не удалось подготовить оценку');
    await expect(page.locator('#onboarding-panel')).toContainText((retryAllowed ? technical : admission).message);
    await expect(page.locator('.onboarding-spinner')).toHaveCount(0);
    await page.reload();
    await expect(page.locator('#onboarding-title')).toHaveText('Не удалось подготовить оценку');
    expect(posts).toBe(0);
    await page.screenshot({ path: testInfo.outputPath('first-failure.png'), fullPage: true });
    if (!retryAllowed) {
      await expect(page.getByRole('button', { name: 'Повторить подготовку', exact: true })).toHaveCount(0);
      await page.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
      expect(posts).toBe(0);
      return;
    }
    const retry = page.getByRole('button', { name: 'Повторить подготовку', exact: true });
    await expect(retry).toBeEnabled();
    await retry.focus(); await expect(retry).toBeFocused();
    await page.setViewportSize({ width: 390, height: 844 });
    await retry.scrollIntoViewIfNeeded(); await expect(retry).toBeInViewport();
    await retry.click();
    await expect(page.locator('#onboarding-title')).toHaveText('Можно приступать к оценке');
    expect(posts).toBe(1);
    await page.reload();
    await expect(page.locator('#onboarding-title')).toHaveText('Можно приступать к оценке');
    expect(posts).toBe(1);
  });
}

for (const retryAllowed of [true, false]) {
  test(`EXEC-FIX-02 next preparation respects server retry=${retryAllowed} across reload`, async ({ page }, testInfo) => {
    let posts = 0;
    let nextPrepared = false;
    let operation = null;
    const runtime = () => ({ cycle_id: 'cycle-next', runtime_kind: 'cycle', return_policy_enabled: false,
      between_situations: !nextPrepared, status: { collection_status: 'active', remaining_seconds: 2700 },
      route: { positions: [{ position_no: 1, state: 'completed', current_assessment_situation_id: 'as-closed' },
        { position_no: 2, state: nextPrepared ? 'in_progress' : 'planned', current_assessment_situation_id: nextPrepared ? 'as-next' : null }],
        progress: { total_positions: 3 } },
      current_situation: nextPrepared ? { assessment_situation_id: 'as-next', status: 'active',
        participant_payload: { title: 'Подготовлена следующая ситуация', situation: 'Synthetic next AS', assessee_task: 'Synthetic task' } } : null,
      preparation_operation: operation,
      trace: { turns: [], events: [] }, clarification: null, continuation: null, pipeline: null });
    await page.route('**/users/**', (route) => {
      const request = route.request(); const pathname = new URL(request.url()).pathname;
      if (pathname === '/users/session/restore') return json(route, { authenticated: true, user, is_admin: false, dashboard: {} });
      if (pathname === '/users/8/session-bootstrap') return json(route, { user, is_admin: false, dashboard: {} });
      if (pathname === '/users/8/journey-state') return json(route, { next_action: 'resume_assessment', profile: { status: 'complete' },
        onboarding: { status: 'completed' }, assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-next',
          cycle_session_id: 'session-next' } });
      if (pathname === '/users/assessment/m7/cycles/cycle-next/return-state') return json(route, { detail: 'M7_RETURN_POLICY_NOT_SNAPSHOTTED' }, 409);
      if (pathname === '/users/assessment/cycles/cycle-next/runtime') return json(route, runtime());
      if (pathname === '/users/assessment/m7/cycles/cycle-next/next' && request.method() === 'POST') {
        posts += 1;
        if (posts === 1) {
          operation = { operation_id: request.postDataJSON().idempotency_key, status: 'failed',
            retry_allowed: retryAllowed, error: retryAllowed ? technical : admission };
          return json(route, operation, 201);
        }
        expect(retryAllowed).toBe(true);
        nextPrepared = true;
        operation = { operation_id: request.postDataJSON().idempotency_key, status: 'completed',
          result: { plan: { cycle_id: 'cycle-next' }, decision: { status: 'SELECTED', assessment_situation_id: 'as-next' } } };
        return json(route, operation, 201);
      }
      if (pathname.startsWith('/users/assessment/cycles/preparation/')) return json(route, operation);
      if (pathname === '/users/version') return json(route, { version: 'exec-fix02-component' });
      return json(route, {}, 404);
    });
    await page.goto(`${base}/?screen=interview`);
    await page.getByRole('button', { name: 'Приступить к следующей ситуации', exact: true }).click();
    await expect(page.locator('#interview-panel')).toContainText((retryAllowed ? technical : admission).message);
    expect(posts).toBe(1);
    await page.reload();
    await expect(page.locator('#interview-panel')).toContainText((retryAllowed ? technical : admission).message);
    expect(posts).toBe(1);
    await page.screenshot({ path: testInfo.outputPath('next-failure.png'), fullPage: true });
    if (!retryAllowed) {
      const next = page.getByRole('button', { name: /Приступить к следующей ситуации|Повторить подготовку/ });
      if (await next.count()) await expect(next).toBeDisabled();
      return;
    }
    const retry = page.getByRole('button', { name: /Повторить подготовку|Приступить к следующей ситуации/ });
    await expect(retry).toBeEnabled();
    await page.setViewportSize({ width: 390, height: 844 });
    await retry.scrollIntoViewIfNeeded(); await expect(retry).toBeInViewport();
    await retry.click();
    await expect(page.locator('#interview-panel')).toContainText('Подготовлена следующая ситуация');
    expect(posts).toBe(2);
  });
}
