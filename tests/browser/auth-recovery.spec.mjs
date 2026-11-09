// Real entry/dist and real recovery. Only HTTP fixtures/asset delivery are synthetic.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const root = process.cwd();
const base = 'http://127.0.0.1:18766';
const chatFile = [];
for (const name of await fs.readdir(path.join(root, 'web/dist'))) {
  if (!/^chat-.*\.js$/.test(name)) continue;
  const source = await fs.readFile(path.join(root, 'web/dist', name), 'utf8');
  // Both screens/chat and entries/chat may be split entries; select the loader's
  // four-export entry, not the larger screen module with buildProcessingAgentsState.
  if (source.includes('resetChat') && !source.includes('buildProcessingAgentsState')) chatFile.push(name);
}
if (chatFile.length !== 1) throw new Error('Exactly one current built chat entry required');
const chatUrl = `${base}/web/dist/${chatFile[0]}`;
let server;
test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const pathname = new URL(request.url, base).pathname;
      const filename = path.join(root, pathname === '/' ? 'web/index.html' : pathname);
      response.setHeader('Content-Type', path.extname(filename) === '.js' ? 'application/javascript'
        : path.extname(filename) === '.html' ? 'text/html' : 'text/css');
      response.end(await fs.readFile(filename));
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise((resolve) => server.listen(18766, '127.0.0.1', resolve));
});
test.afterAll(async () => new Promise((resolve) => server.close(resolve)));

const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
const missingSession = 'Сессия входа не сохранилась';
const resumeEmail = 'p4k-auth-resume@example.invalid';
const resumePassword = 'P4k!9xQ2mZ';
const waitingJourney = {
  next_action: 'wait_for_acquaintance_data', acquaintance: { readiness: { status: 'waiting_for_assignment' } },
};

async function routes(page) {
  const counts = { journey401: 0, logout: 0 };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return json(route, { version: 'synthetic-auth-regression' });
    if (pathname === '/users/session/restore') return json(route, { authenticated: false });
    if (pathname === '/users/auth/email/request-link') return json(route, {
      email: route.request().postDataJSON().email, auth_mode: 'password', message: 'Введите пароль.',
    });
    if (pathname === '/users/auth/email/password-login') {
      const { email, password } = route.request().postDataJSON();
      expect(password).toBe(resumePassword);
      const id = email.startsWith('newer-') ? 10 : email.startsWith('new-') ? 9 : 8;
      return json(route, { exists: true, user: { id, email, full_name: 'Synthetic' },
        is_admin: false, dashboard: {}, agent: { session_id: 'synthetic-profile', stage: 'profile' } });
    }
    if (pathname === '/users/8/journey-state') {
      counts.journey401 += 1;
      return json(route, { detail: 'Session not found' }, 401);
    }
    if (['/users/9/journey-state', '/users/10/journey-state'].includes(pathname)) return json(route, waitingJourney);
    if (pathname === '/users/session/logout') { counts.logout += 1; return json(route, {}); }
    return json(route, {}, 404);
  });
  return counts;
}

async function login(page, email = resumeEmail) {
  await page.locator('#email-input').fill(email);
  await page.locator('#request-magic-link-button').click();
  await expect(page.locator('#magic-token-input')).toBeVisible();
  await page.locator('#magic-token-input').fill(resumePassword);
  await page.locator('#verify-magic-link-button').click();
}

async function holdChat(page) {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let requests = 0;
  await page.route('**/web/dist/chat-*.js', async (route) => {
    requests += 1;
    await gate;
    await route.continue();
  });
  return { release, requests: () => requests };
}

async function finishChat(page) {
  // Await the SAME real module, then the next rendering turn: all import/recovery
  // microtasks have completed. No sleep, DOM mutation or replacement product hook.
  await page.evaluate(async (url) => {
    await import(url);
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }, chatUrl);
}

async function assertClosed(page, { sharedStorage = false } = {}) {
  await expect(page.locator('#auth-panel')).toBeVisible();
  for (const id of ['dashboard-panel', 'interview-panel', 'admin-panel', 'profile-panel']) {
    await expect(page.locator(`#${id}`)).toBeHidden();
  }
  if (!sharedStorage) expect(await page.evaluate(() => localStorage.getItem('agent4k.pendingUser'))).toBeNull();
}

async function assertRetryAvailable(page) {
  await expect(page.locator('#auth-email-form')).toBeVisible();
  await expect(page.locator('#auth-token-form')).toBeHidden();
  await expect(page.locator('#auth-panel')).not.toHaveAttribute('aria-busy');
  for (const id of ['email-input', 'request-magic-link-button', 'magic-token-input', 'verify-magic-link-button',
    'auth-password-toggle-button', 'auth-change-credential-email-button', 'forgot-password-credential-button']) {
    const control = page.locator(`#${id}`);
    await expect(control).toBeEnabled();
    await expect(control).not.toHaveAttribute('aria-busy');
  }
  await expect(page.locator('#request-magic-link-button')).toHaveText('Продолжить');
}

for (const timing of ['delayed', 'eager']) {
  test(`AUTH-DIAG-01 ${timing} cleanup retains error and fails closed`, async ({ page }, testInfo) => {
    testInfo.annotations.push({ type: 'synthetic_http', description: 'No real auth/DB/provider; real built UI and cleanup.' });
    const counts = await routes(page);
    const held = timing === 'delayed' ? await holdChat(page) : null;
    try {
      await page.goto(base);
      if (!held) await finishChat(page);
      await login(page);
      await expect(page.locator('#auth-error')).toContainText(missingSession);
      await assertClosed(page);
      if (held) {
        expect(held.requests()).toBe(1);
        held.release();
      }
      await finishChat(page);
      await expect(page.locator('#auth-error')).toContainText(missingSession);
      await expect(page.locator('#auth-error')).toBeVisible();
      await expect(page.locator('#auth-status')).toBeHidden();
      await assertClosed(page);
      await assertRetryAvailable(page);
      expect(counts).toEqual({ journey401: 1, logout: 0 });
      await page.screenshot({ path: testInfo.outputPath('after-cleanup.png') });
      await testInfo.attach('recovery-observation', { body: JSON.stringify({ case_id: 'S-01', timing, ...counts,
        error: await page.locator('#auth-error').textContent(), cleanup_module_settled: true,
        scope: 'synthetic_http_real_built_ui', historical_causality: 'NOT_ESTABLISHED' }), contentType: 'application/json' });
      // A real second attempt proves that neither in-flight guard remains stuck.
      await login(page);
      await finishChat(page);
      await expect(page.locator('#auth-error')).toContainText(missingSession);
      await assertClosed(page);
      await assertRetryAvailable(page);
      expect(counts).toEqual({ journey401: 2, logout: 0 });
    } finally { held?.release(); }
  });
}

test('AUTH-RESUME S-02 valid journey opens the participant path without a missing-session error', async ({ page }) => {
  const counts = await routes(page);
  await page.goto(base);
  await login(page, 'new-person@example.test');
  await expect(page.locator('#auth-complete-panel')).toBeVisible();
  await expect(page.locator('#auth-complete-title')).toHaveText('Оценка пока не назначена');
  await expect(page.locator('#auth-panel')).toBeHidden();
  await expect(page.locator('#auth-error')).toBeHidden();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('agent4k.pendingUser')).id)).toBe(9);
  expect(counts).toEqual({ journey401: 0, logout: 0 });
});

test('AUTH-RESUME S-03 an old journey 401 after a new login cannot revoke the newer session', async ({ page }) => {
  const counts = await routes(page);
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let journeys = 0;
  await page.route('**/users/9/journey-state', async (route) => {
    journeys += 1;
    if (journeys === 1) return json(route, {
      next_action: 'wait_for_acquaintance_data', acquaintance: { readiness: { status: 'waiting_for_data' } },
    });
    await gate;
    return json(route, { detail: 'Old synthetic session not found' }, 401);
  });
  try {
    await page.goto(base);
    await login(page, 'new-person@example.test');
    await expect(page.locator('#auth-complete-panel')).toBeVisible();
    await page.locator('#auth-complete-continue-button').click();
    await expect.poll(() => journeys).toBe(2);
    await expect(page.locator('#auth-complete-continue-button')).toBeDisabled();

    // The readiness request belongs to the account that is explicitly logged out.
    await page.locator('#auth-complete-logout-button').click();
    await expect(page.locator('#auth-email-form')).toBeVisible();
    await login(page, 'newer-person@example.test');
    await expect(page.locator('#auth-complete-panel')).toBeVisible();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('agent4k.pendingUser')).id)).toBe(10);
    const lateResponse = page.waitForResponse((response) => new URL(response.url()).pathname === '/users/9/journey-state');
    release();
    await (await lateResponse).finished();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(resolve)));

    await expect(page.locator('#auth-complete-panel')).toBeVisible();
    await expect(page.locator('#auth-panel')).toBeHidden();
    await expect(page.locator('#auth-error')).toBeHidden();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('agent4k.pendingUser')).id)).toBe(10);
    expect(counts).toEqual({ journey401: 0, logout: 1 });
  } finally { release(); }
});

test('AUTH-DIAG-01 late cleanup cannot erase a newer account in the same tab', async ({ page }) => {
  const counts = await routes(page);
  const held = await holdChat(page);
  try {
    await page.goto(base);
    await login(page);
    await expect(page.locator('#auth-error')).toContainText(missingSession);
    expect(held.requests()).toBe(1);
    await login(page, 'new-person@example.test');
    await expect(page.locator('#auth-complete-panel')).toBeVisible();
    held.release();
    await finishChat(page);
    await expect(page.locator('#auth-complete-panel')).toBeVisible();
    await expect(page.locator('#auth-panel')).toBeHidden();
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('agent4k.pendingUser')).id)).toBe(9);
    expect(counts.logout).toBe(0);
  } finally { held.release(); }
});

test('AUTH-DIAG-01 another tab changes generation while cleanup is pending', async ({ page, context }) => {
  const counts = await routes(page);
  const held = await holdChat(page);
  const other = await context.newPage();
  const otherCounts = await routes(other);
  try {
    await page.goto(base);
    await login(page);
    await expect(page.locator('#auth-error')).toContainText(missingSession);
    expect(held.requests()).toBe(1);
    await other.goto(base);
    await login(other, 'new-person@example.test');
    await expect(other.locator('#auth-complete-panel')).toBeVisible();
    // BroadcastChannel invokes real resetStaleUserState in the original tab.
    await expect(page.locator('#auth-error')).toBeHidden();
    held.release();
    await finishChat(page);
    await assertClosed(page, { sharedStorage: true });
    await expect(page.locator('#auth-error')).toBeHidden();
    await expect(other.locator('#auth-complete-panel')).toBeVisible();
    expect(counts.logout + otherCounts.logout).toBe(0);
  } finally { held.release(); await other.close(); }
});
