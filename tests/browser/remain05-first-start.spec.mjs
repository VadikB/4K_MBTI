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
const cycleId = 'cycle-unknown-start';
const situationId = 'as-unknown-start';
const situationTitle = 'Сохранённая первая ситуация';
const onboardingPath = '/users/8/onboarding';
const startPath = '/users/assessment/cycles/start';
const runtimePath = '/users/assessment/cycles/' + cycleId + '/runtime';
const completedProgress = { status: 'completed', current_step: 8 };
const saveError = 'Не удалось получить подтверждение сервера';
const progressPut = { method: 'PUT', path: onboardingPath, body: completedProgress };
const startPost = { method: 'POST', path: startPath,
  body: { cycle_id: cycleId, idempotency_key: expect.stringMatching(/\S/) } };

async function mockPreparedStart(page, {
  questions = ['Q1', 'Q2', 'Q3'], onboarding = completedProgress, abortOnboardingPut = false, loseStartReceipt = false,
} = {}) {
  const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
  const plan = { cycle_id: cycleId, revision_id: 'revision-unknown-start', revision_no: 1,
    start_readiness: { contract: 'm7_start_readiness/1', cycle_id: cycleId,
      plan_revision_id: 'revision-unknown-start', can_start: true, reasons: [] },
    plan: { status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], time_budget_seconds: 7200,
      calendar_window_seconds: 259200 } };
  const acquaintance = {
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions, consent_version: 1, consent_text: 'Синтетическое согласие' } },
    state: { answers_json: Object.fromEntries(questions.map((_, index) => ['answer_' + (index + 1), 'Synthetic answer'])),
      consent_accepted_at: 'synthetic', consent_version: 1, answers_confirmed_at: 'synthetic' },
    mandatory_complete: true, onboarding, late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    prepared_plan: plan,
  };
  const runtime = { runtime_kind: 'cycle', cycle_id: cycleId, between_situations: false,
    return_policy_enabled: false, status: { collection_status: 'active', remaining_seconds: 7200 },
    route: { positions: [{ position_no: 1, state: 'in_progress',
      current_assessment_situation_id: situationId }], progress: { total_positions: 1 } },
    situations: [{ assessment_situation_id: situationId, status: 'active' }],
    current_situation: { assessment_situation_id: situationId, status: 'active', participant_payload: {
      title: situationTitle, situation: 'Проверьте состояние после reload.', assessee_task: 'Опишите решение.',
    } }, trace: { turns: [], events: [] }, clarification: null, continuation: null, pipeline: null };
  const traffic = { commands: [], runtimeReads: [], abortOnboardingPut };
  let startAccepted = false;

  await page.route('**/users/**', (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const method = request.method();
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') {
      // Keep the original pending-on-reload scenario until the runtime read succeeds.
      const canResume = startAccepted && (!loseStartReceipt || traffic.runtimeReads.some(({ status }) => status === 200));
      return fulfillJson(route, { next_action: canResume ? 'resume_assessment' : 'show_onboarding', acquaintance,
        profile: { status: 'complete' }, onboarding: acquaintance.onboarding, assessment: canResume
          ? { status: 'in_progress', runtime_kind: 'cycle', cycle_id: cycleId, cycle_session_id: 'session-first' }
          : { status: 'not_started' } });
    }
    if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) return fulfillJson(route, acquaintance);
    if (method !== 'GET') traffic.commands.push({ method, path: pathname, body: request.postDataJSON() });
    if (pathname === onboardingPath && method === 'PUT') {
      if (traffic.abortOnboardingPut) return route.abort('failed');
      acquaintance.onboarding = request.postDataJSON();
      return fulfillJson(route, acquaintance.onboarding);
    }
    if (pathname === startPath && method === 'POST') {
      startAccepted = true;
      return loseStartReceipt ? route.fulfill({ status: 201, contentType: 'application/json', body: '{' })
        : fulfillJson(route, { plan, runtime }, 201);
    }
    if (pathname === '/users/assessment/m7/cycles/' + cycleId + '/return-state') {
      return fulfillJson(route, { detail: 'M7_RETURN_CURRENT_POSITION_NOT_FOUND' }, 409);
    }
    if (pathname === runtimePath) {
      if (!startAccepted) return fulfillJson(route, { detail: 'not started' }, 404);
      const status = loseStartReceipt && traffic.runtimeReads.length === 0 ? 503 : 200;
      traffic.runtimeReads.push({ path: pathname, status, ...(status === 200 ? { cycleId, situationId } : {}) });
      return status === 503 ? fulfillJson(route, { detail: 'temporarily unavailable' }, status) : fulfillJson(route, runtime);
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: 'remain05-controlled' });
    expect(pathname).not.toMatch(/report/i);
    return fulfillJson(route, {}, 404);
  });
  return traffic;
}

const startButton = (page) => page.getByRole('button', { name: 'Приступить к оценке', exact: true });
const firstSituation = (page) => page.getByRole('region', { name: 'История диалога и материалы ситуации' })
  .getByRole('heading', { name: situationTitle, exact: true });
const onboardingError = (page) => page.locator('#onboarding-error');

async function openReadiness(page) {
  await page.goto(base + '/?screen=onboarding');
  await expect(page.locator('#onboarding-title')).toHaveText('Ваши кейсы подготовлены');
}

async function attachStartTraffic(testInfo, name, page, { commands, runtimeReads }) {
  await testInfo.attach(name, { contentType: 'application/json', body: JSON.stringify({
    commands, runtimeReads, onboardingError: await onboardingError(page).textContent(),
    firstSituationTitle: await firstSituation(page).isVisible() ? await firstSituation(page).textContent() : null,
  }, null, 2) });
}

test('REMAIN05 AC-1 confirmed onboarding starts despite a blocked progress PUT', async ({ page }, testInfo) => {
  const traffic = await mockPreparedStart(page, {
    questions: ['Q1', 'Q2'], onboarding: { status: 'completed', current_step: 7 }, abortOnboardingPut: true,
  });
  await openReadiness(page);
  expect(traffic.commands).toEqual([]);
  await startButton(page).click();
  await expect(firstSituation(page).or(onboardingError(page).filter({ hasText: saveError }))).toBeVisible();
  await attachStartTraffic(testInfo, 'first-click', page, traffic);
  expect(traffic.commands).toEqual([startPost]);
  await expect(firstSituation(page)).toBeVisible();
  await page.reload();
  await expect(firstSituation(page)).toBeVisible();
  expect(traffic.commands).toEqual([startPost]);
  expect(traffic.runtimeReads).toContainEqual({ path: runtimePath, status: 200, cycleId, situationId });
  await attachStartTraffic(testInfo, 'after-reload', page, traffic);
  await page.screenshot({ path: testInfo.outputPath('same-first-as.png'), fullPage: true });
});

for (const [label, onboarding] of [
  ['in-progress status', { status: 'in_progress', current_step: 8 }],
  ['different saved step', { status: 'completed', current_step: 7 }],
]) {
  test('REMAIN05 AC-2 saves final progress before start with ' + label, async ({ page }, testInfo) => {
    const traffic = await mockPreparedStart(page, { onboarding });
    await openReadiness(page);
    expect(traffic.commands).toEqual([]);
    await startButton(page).click();
    await expect(firstSituation(page)).toBeVisible();
    expect(traffic.commands).toEqual([progressPut, startPost]);
    await attachStartTraffic(testInfo, 'first-click', page, traffic);
  });
}

test('REMAIN05 AC-2 blocks start after a failed required PUT and allows recovery', async ({ page }, testInfo) => {
  const traffic = await mockPreparedStart(page, {
    onboarding: { status: 'in_progress', current_step: 8 }, abortOnboardingPut: true,
  });
  await openReadiness(page);
  expect(traffic.commands).toEqual([]);
  await startButton(page).click();
  await expect(onboardingError(page)).toContainText(saveError);
  expect(traffic.commands).toEqual([progressPut]);
  await attachStartTraffic(testInfo, 'failed-save', page, traffic);

  traffic.abortOnboardingPut = false;
  await page.getByRole('button', { name: 'Повторить проверку', exact: true }).click();
  await expect(startButton(page)).toBeEnabled();
  expect(traffic.commands).toEqual([progressPut]);
  await startButton(page).click();
  await expect(firstSituation(page)).toBeVisible();
  expect(traffic.commands).toEqual([progressPut, progressPut, startPost]);
  await attachStartTraffic(testInfo, 'after-recovery', page, traffic);
});

test('REMAIN05 AC-3 lost start receipt reads and reloads the same first AS without another POST', async ({ page }, testInfo) => {
  const traffic = await mockPreparedStart(page, { loseStartReceipt: true });
  await openReadiness(page);
  expect(traffic.commands).toEqual([]);
  await startButton(page).click();
  await expect(page.locator('#onboarding-panel')).toContainText('Состояние не подтверждено');
  await expect(page.locator('#onboarding-title')).toHaveText('Проверяем начало оценки');
  expect(traffic.commands).toEqual([startPost]);
  expect(traffic.runtimeReads).toEqual([{ path: runtimePath, status: 503 }]);
  await attachStartTraffic(testInfo, 'unknown-start', page, traffic);

  await page.reload();
  await expect(page.locator('#onboarding-title')).toHaveText('Проверяем начало оценки');
  await page.getByRole('button', { name: 'Проверить состояние', exact: true }).click();
  await expect(firstSituation(page)).toBeVisible();
  expect(traffic.commands).toEqual([startPost]);
  expect(traffic.runtimeReads).toContainEqual({ path: runtimePath, status: 200, cycleId, situationId });
  const readsBeforeReload = traffic.runtimeReads.length;
  await page.reload();
  await expect(firstSituation(page)).toBeVisible();
  expect(traffic.runtimeReads.slice(readsBeforeReload)).toContainEqual({ path: runtimePath, status: 200, cycleId, situationId });
  expect(traffic.commands).toEqual([startPost]);
  await attachStartTraffic(testInfo, 'after-reload', page, traffic);
  await page.screenshot({ path: testInfo.outputPath('same-first-as.png'), fullPage: true });
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
