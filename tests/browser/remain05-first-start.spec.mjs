import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
let server, base;
test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
      const filename = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      response.setHeader('Content-Type', ({ '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' })[path.extname(filename)] || 'application/octet-stream');
      response.end(await fs.readFile(filename));
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => { await new Promise((resolve) => server.close(resolve)); });
const fulfillJson = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
test('REMAIN05 invalid201 reload resolves same first AS without another POST', async ({ page }, testInfo) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
  const plan = { cycle_id: 'cycle-unknown-start', revision_id: 'revision-unknown-start', revision_no: 1,
    start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-unknown-start',
      plan_revision_id: 'revision-unknown-start', can_start: true, reasons: [] },
    plan: { status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], time_budget_seconds: 7200,
      calendar_window_seconds: 259200 } };
  const acquaintance = {
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1, consent_text: 'Синтетическое согласие' } },
    state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' }, consent_accepted_at: 'synthetic',
      consent_version: 1, answers_confirmed_at: 'synthetic' }, mandatory_complete: true,
    onboarding: { status: 'completed', current_step: 8 }, late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    prepared_plan: plan,
  };
  const runtime = { runtime_kind: 'cycle', cycle_id: 'cycle-unknown-start', between_situations: false,
    return_policy_enabled: false, status: { collection_status: 'active', remaining_seconds: 7200 },
    route: { positions: [{ position_no: 1, state: 'in_progress',
      current_assessment_situation_id: 'as-unknown-start' }], progress: { total_positions: 1 } },
    situations: [{ assessment_situation_id: 'as-unknown-start', status: 'active' }],
    current_situation: { assessment_situation_id: 'as-unknown-start', status: 'active', participant_payload: {
      title: 'Сохранённая первая ситуация', situation: 'Проверьте состояние после reload.',
      assessee_task: 'Опишите решение.',
    } }, trace: { turns: [], events: [] }, clarification: null, continuation: null, pipeline: null };
  let startPosts = 0;
  let runtimeReads = 0;
  await page.route('**/users/**', (route) => {
    const request = route.request(); const pathname = new URL(request.url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_onboarding', acquaintance,
      profile: { status: 'complete' }, onboarding: acquaintance.onboarding, assessment: { status: 'not_started' } });
    if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) return fulfillJson(route, acquaintance);
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'completed', current_step: 8 });
    if (pathname === '/users/assessment/cycles/start' && request.method() === 'POST') {
      startPosts += 1; return route.fulfill({ status: 201, contentType: 'application/json', body: '{' });
    }
    if (pathname === '/users/assessment/m7/cycles/cycle-unknown-start/return-state') {
      return fulfillJson(route, { detail: 'M7_RETURN_CURRENT_POSITION_NOT_FOUND' }, 409);
    }
    if (pathname === '/users/assessment/cycles/cycle-unknown-start/runtime') {
      runtimeReads += 1;
      return runtimeReads === 1 ? fulfillJson(route, { detail: 'temporarily unavailable' }, 503) : fulfillJson(route, runtime);
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: 'ac18-fix02-test' });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=onboarding`);
  await expect(page.locator('#onboarding-title')).toHaveText('Можно приступать к оценке');
  await page.getByRole('button', { name: 'Приступить к оценке' }).click();
  await expect(page.locator('#onboarding-panel')).toContainText('Состояние не подтверждено');
  await expect(page.locator('#onboarding-title')).toHaveText('Проверяем первый старт');
  expect(startPosts).toBe(1);
  await page.reload();
  await expect(page.locator('#onboarding-title')).toHaveText('Проверяем первый старт');
  await page.getByRole('button', { name: 'Проверить состояние' }).click();
  await expect(page.locator('#interview-case-title')).toHaveText('Сохранённая первая ситуация');
  expect(startPosts).toBe(1);
  expect(runtimeReads).toBeGreaterThanOrEqual(2);
  expect(runtimeReads).toBeLessThanOrEqual(12);
  await page.screenshot({ path: testInfo.outputPath('same-first-as.png'), fullPage: true }); // Interview also refreshes its own runtime.
});


test('REMAIN05 GET and PUT errors keep the current answer and safe explanation', async ({ page }, testInfo) => {
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Synthetic participant' };
  let getReads = 0;
  const acquaintance = {
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic', result_recipients: 'Synthetic',
        questions: ['Q1', 'Q2', 'Q3'], consent_version: 1, consent_text: 'Синтетическое согласие' } },
    state: { answers_json: {}, consent_accepted_at: null }, mandatory_complete: false,
    onboarding: { status: 'not_started', current_step: 0 }, late_readiness: { status: 'not_ready' },
  };
  await page.route('**/users/**', (route) => {
    const req = route.request(), pathname = new URL(req.url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_onboarding', acquaintance,
      profile: { status: 'complete' }, onboarding: acquaintance.onboarding, assessment: { status: 'not_started' } });
    if (pathname === '/users/8/acquaintance') {
      getReads++;
      return getReads === 1 ? route.abort('failed') : fulfillJson(route, acquaintance);
    }
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'in_progress', current_step: req.postDataJSON().current_step });
    if (pathname === '/users/8/acquaintance/consent') return fulfillJson(route, { ...acquaintance.state, consent_accepted_at: 'synthetic', consent_version: 1 });
    if (pathname === '/users/8/acquaintance/answers') return route.abort('failed');
    if (pathname === '/users/version') return fulfillJson(route, { version: 'remain05-controlled' });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=onboarding`);
  await expect(page.locator('#onboarding-error')).toContainText('Не удалось получить подтверждение сервера');
  await expect(page.locator('#onboarding-error')).not.toContainText('Failed to fetch');
  await page.locator('#onboarding-next').click();
  await page.getByRole('button', { name: 'Начать знакомство', exact: true }).click();
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
  const answer = page.locator('.onboarding-answer');
  await answer.fill('Синтетический несохранённый ответ');
  await page.getByRole('button', { name: 'Отправить', exact: true }).click();
  await expect(page.locator('#onboarding-error')).toContainText('Не удалось получить подтверждение сервера');
  await expect(answer).toHaveValue('Синтетический несохранённый ответ');
  await expect(page.locator('#onboarding-title')).toHaveText('Q1');
  await expect(page.locator('#onboarding-error')).not.toContainText('Failed to fetch');
  await page.screenshot({ path: testInfo.outputPath('safe-error-answer.png'), fullPage: true });
});

test('REMAIN05 explicit normal start and reload preserve first AS and zero answers', async ({ page }, testInfo) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
  const plan = { cycle_id: 'cycle-unknown-start', revision_id: 'revision-unknown-start', revision_no: 1,
    start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-unknown-start',
      plan_revision_id: 'revision-unknown-start', can_start: true, reasons: [] },
    plan: { status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], time_budget_seconds: 7200,
      calendar_window_seconds: 259200 } };
  const acquaintance = {
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1, consent_text: 'Синтетическое согласие' } },
    state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' }, consent_accepted_at: 'synthetic',
      consent_version: 1, answers_confirmed_at: 'synthetic' }, mandatory_complete: true,
    onboarding: { status: 'completed', current_step: 8 }, late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    prepared_plan: plan,
  };
  const runtime = { runtime_kind: 'cycle', cycle_id: 'cycle-unknown-start', between_situations: false,
    return_policy_enabled: false, status: { collection_status: 'active', remaining_seconds: 7200 },
    route: { positions: [{ position_no: 1, state: 'in_progress',
      current_assessment_situation_id: 'as-unknown-start' }], progress: { total_positions: 1 } },
    situations: [{ assessment_situation_id: 'as-unknown-start', status: 'active' }],
    current_situation: { assessment_situation_id: 'as-unknown-start', status: 'active', participant_payload: {
      title: 'Сохранённая первая ситуация', situation: 'Проверьте состояние после reload.',
      assessee_task: 'Опишите решение.',
    } }, trace: { turns: [], events: [] }, clarification: null, continuation: null, pipeline: null };
  let startPosts = 0;
  let runtimeReads = 0;
  await page.route('**/users/**', (route) => {
    const request = route.request(); const pathname = new URL(request.url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: startPosts ? 'resume_assessment' : 'show_onboarding', acquaintance,
      profile: { status: 'complete' }, onboarding: acquaintance.onboarding, assessment: startPosts ? { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-unknown-start', cycle_session_id: 'session-first' } : { status: 'not_started' } });
    if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) return fulfillJson(route, acquaintance);
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'completed', current_step: 8 });
    if (pathname === '/users/assessment/cycles/start' && request.method() === 'POST') {
      startPosts += 1; return fulfillJson(route, { plan, runtime }, 201);
    }
    if (pathname === '/users/assessment/m7/cycles/cycle-unknown-start/return-state') {
      return fulfillJson(route, { detail: 'M7_RETURN_CURRENT_POSITION_NOT_FOUND' }, 409);
    }
    if (pathname === '/users/assessment/cycles/cycle-unknown-start/runtime') {
      runtimeReads += 1;
      return fulfillJson(route, runtime);
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: 'ac18-fix02-test' });
    expect(request.method()).toBe('GET');
    expect(pathname).not.toMatch(/report/i);
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=onboarding`);
  await expect(page.locator('#onboarding-title')).toHaveText('Можно приступать к оценке');
  await page.getByRole('button', { name: 'Приступить к оценке' }).click();
  await expect(page.locator('#interview-case-title')).toHaveText('Сохранённая первая ситуация');
  expect(startPosts).toBe(1);
  await page.reload();
  await expect(page.locator('#interview-case-title')).toHaveText('Сохранённая первая ситуация');
  expect(startPosts).toBe(1);
  expect(runtimeReads).toBeGreaterThanOrEqual(1);
  expect(runtimeReads).toBeLessThanOrEqual(12);
  await page.screenshot({ path: testInfo.outputPath('same-first-as.png'), fullPage: true }); // Interview also refreshes its own runtime.
});
