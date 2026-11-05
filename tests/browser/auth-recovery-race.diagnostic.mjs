// Opt-in negative diagnosis, NOT part of the standard *.spec.mjs acceptance suite.
// Real HTML/entry/dist; synthetic HTTP only, no DOM/fetch/timer replacement.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const root = process.cwd();
const base = 'http://127.0.0.1:18765';
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
  await new Promise((resolve) => server.listen(18765, '127.0.0.1', resolve));
});
test.afterAll(async () => new Promise((resolve) => server.close(resolve)));

test('AUTH-DIAG-01: unauthorized cleanup must retain the missing-session error', async ({ page }, testInfo) => {
  testInfo.annotations.push({ type: 'synthetic_http', description: 'Explicitly delayed chat asset; no real auth/provider/DB; not evidence of historical timing.' });
  let releaseChat;
  const gate = new Promise((resolve) => { releaseChat = resolve; });
  let heldChatRequests = 0;
  let journey401 = 0;
  await page.route('**/web/dist/chat-*.js', async (route) => {
    heldChatRequests += 1;
    await gate;
    await route.continue();
  });
  const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return json(route, { version: '2.0.68' });
    if (pathname === '/users/session/restore') return json(route, { authenticated: false });
    if (pathname === '/users/auth/email/request-link') return json(route, { email: 'person@example.test', auth_mode: 'password', message: 'Введите пароль.' });
    if (pathname === '/users/auth/email/password-login') return json(route, {
      exists: true, user: { id: 8, email: 'person@example.test', full_name: 'Person' }, is_admin: false,
      agent: { session_id: 'profile-session', message: '', stage: 'profile', completed: false }, dashboard: {},
    });
    if (pathname === '/users/8/journey-state') {
      journey401 += 1;
      return json(route, { detail: 'Session not found' }, 401);
    }
    return json(route, {}, 404);
  });
  try {
    await page.goto(base);
    await page.locator('#email-input').fill('person@example.test');
    await page.locator('#request-magic-link-button').click();
    await expect(page.locator('#magic-token-input')).toBeVisible();
    await page.locator('#magic-token-input').fill('synthetic-password');
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#auth-error')).toContainText('Сессия входа не сохранилась');
    expect(journey401).toBe(1);
    expect(heldChatRequests).toBeGreaterThan(0);
    const before = await page.locator('#auth-error').textContent();
    await page.screenshot({ path: testInfo.outputPath('before-delayed-cleanup.png') });
    releaseChat();
    await expect.poll(async () => (await page.locator('#auth-error').textContent()) === '', { timeout: 5000 }).toBe(true);
    const after = await page.locator('#auth-error').textContent();
    await testInfo.attach('diagnostic-observation', { body: JSON.stringify({
      scope: 'deterministic_synthetic_transport_reproduction', before, after, journey401, heldChatRequests,
      expected: 'Missing-session error remains after lazy unauthorized cleanup',
      actual: 'Error was cleared by the delayed real chat module cleanup',
      historical_causality: 'NOT_ESTABLISHED', product_changed: false,
    }, null, 2), contentType: 'application/json' });
    // The final assertion intentionally exposes the current product defect.
    await expect(page.locator('#auth-error')).toContainText('Сессия входа не сохранилась');
  } finally { releaseChat(); }
});
