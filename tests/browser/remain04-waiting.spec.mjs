import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';

const port = 18784, base = `http://127.0.0.1:${port}`;
let server;
test.beforeAll(async () => {
  server = http.createServer(async (req, res) => {
    try {
      const pathname = new URL(req.url, base).pathname;
      const filename = path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      const body = await fs.readFile(filename);
      res.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' }[path.extname(filename)] || 'application/octet-stream');
      res.end(body);
    } catch { res.statusCode = 404; res.end('missing'); }
  });
  await new Promise((resolve) => server.listen(port, '127.0.0.1', resolve));
});
test.afterAll(async () => { if (server) await new Promise((resolve) => server.close(resolve)); });
const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
const user = { id: 8, email: 'synthetic@example.test', full_name: 'Иван Синтетический' };
const waiting = { next_action: 'wait_for_acquaintance_data', profile: { status: 'incomplete' },
  assessment: { status: 'not_started' }, onboarding: { status: 'not_started' },
  acquaintance: { readiness: { status: 'waiting_for_assignment', message: 'Оценка пока не назначена. Обратитесь к уполномоченному назначающему.' } } };
const auth = { exists: true, user, is_admin: false, dashboard: {}, agent: { session_id: 'synthetic', completed: false } };

async function fixture(page, { login = false } = {}) {
  const writes = [], unexpected = [];
  let authenticated = !login, journey = waiting, refused = false, hold = null;
  const model = { readiness: { status: 'ready', organization_id: 10, assignment_ref: 'A', questionnaire_revision_id: 41,
    organization_name: 'Org A', organization_kind: 'organization', briefing: {
      purpose: 'Purpose 41', organizer: 'Organizer 41', results_usage: 'Usage 41',
      result_recipients: 'Свой готовый отчёт видит участник. Готовые отчёты организации видят её действующие администраторы.',
      provided_participant_fields: [ { label: 'ФИО', value: user.full_name }, { label: 'Должность', value: null } ],
      consent_version: 1, consent_text: 'Synthetic consent', questions: ['Рабочие ситуации?', 'Принятие решений?', 'Ограничения?'],
    } }, state: { status: 'not_started', answers_json: {} }, mandatory_complete: false,
    late_readiness: { status: 'waiting_for_assessment_data' }, onboarding: { status: 'in_progress' } };
  await page.route('**/users/**', async (route) => {
    const url = new URL(route.request().url()), method = route.request().method();
    if (method !== 'GET') writes.push(`${method} ${url.pathname}`);
    if (url.pathname === '/users/version') return json(route, { version: 'synthetic' });
    if (url.pathname === '/users/session/restore') return json(route, { authenticated, ...auth });
    if (url.pathname === '/users/auth/email/request-link') return json(route, { email: user.email, auth_mode: 'password' });
    if (url.pathname === '/users/auth/email/password-login') { authenticated = true; return json(route, auth); }
    if (url.pathname === '/users/auth/logout' || url.pathname === '/users/logout') { authenticated = false; return json(route, {}); }
    if (url.pathname === '/users/8/session-bootstrap') return json(route, auth);
    if (url.pathname === '/users/8/journey-state') {
      if (hold) { const pending = hold; hold = null; await pending; }
      return json(route, refused ? { detail: 'controlled refusal' } : journey, refused ? 503 : 200);
    }
    if (url.pathname === '/users/8/acquaintance') return json(route, model);
    if (url.pathname === '/users/8/onboarding') return json(route, route.request().postDataJSON());
    if (url.pathname === '/users/8/acquaintance/consent') { model.state.consent_accepted_at = 'synthetic'; model.state.consent_version = 1; return json(route, model.state); }
    if (url.pathname === '/users/8/acquaintance/answers') {
      const body = route.request().postDataJSON();
      Object.assign(model.state.answers_json, body.answers);
      if (body.confirm) { model.mandatory_complete = true; model.state.answers_confirmed_at = 'synthetic'; }
      return json(route, model.state);
    }
    // STOP boundary: actual profile persistence is independently proven by SQL/HTTP.
    if (url.pathname === '/users/8/acquaintance/resolve-profile') return json(route, model);
    unexpected.push(`${method} ${url.pathname}`);
    return json(route, {}, 404);
  });
  return { writes, unexpected, model,
    assign: () => { journey = { ...waiting, next_action: 'show_onboarding', acquaintance: model }; },
    refuse: (value) => { refused = value; },
    hold: () => { let release; hold = new Promise((resolve) => { release = resolve; }); return release; } };
}

test('REMAIN04 waiting login/direct/reload/check, viewports/text200/focus, then exact briefing and own answers', async ({ page }, info) => {
  test.setTimeout(90000);
  const run = await fixture(page, { login: true });
  await page.goto(base);
  await page.locator('#email-input').fill(user.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('Synthetic-password');
  await page.locator('#verify-magic-link-button').click();
  const check = page.getByRole('button', { name: 'Проверить готовность', exact: true });
  await expect(check).toBeVisible();
  const permittedAuth = [...run.writes];
  await page.goto(base + '/?screen=chat');
  await expect(check).toBeVisible();
  await page.reload();
  await expect(check).toBeVisible();
  await check.click();
  await expect(check).toBeEnabled();
  await expect(page.locator('#chat-panel')).toBeHidden();
  await expect(page.locator('#auth-complete-title')).toBeFocused();
  for (const width of [1440,1366,768,390,320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(check).toBeInViewport();
    await page.locator('#auth-complete-logout-button').scrollIntoViewIfNeeded();
    await expect(page.locator('#auth-complete-logout-button')).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.screenshot({ path: info.outputPath(`waiting-${width}.png`), fullPage: true });
  }
  await page.locator('#auth-complete-description').evaluate((node) => { node.textContent = 'Организация готовит сведения для назначения оценки. '.repeat(8); });
  await page.addStyleTag({ content: '#auth-complete-panel { font-size: 200%; } #auth-complete-panel * { font-size: inherit; overflow-wrap: anywhere; }' });
  await check.scrollIntoViewIfNeeded();
  await check.focus();
  await expect(check).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#auth-complete-logout-button')).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await page.screenshot({ path: info.outputPath('waiting-text200.png'), fullPage: true });
  expect(run.writes).toEqual(permittedAuth);
  run.refuse(true);
  await check.click();
  await expect(page.locator('#auth-complete-title')).toHaveText('Не удалось проверить готовность');
  run.refuse(false); run.assign();
  await check.click();
  await expect(page.locator('#onboarding-title')).toContainText('Organizer 41');
  await expect(page.locator('#onboarding-panel')).toContainText('Purpose 41');
  await expect(page.locator('#onboarding-panel')).not.toContainText('historical');
  expect(await page.locator('#onboarding-panel input').count()).toBe(0);
  await page.locator('#onboarding-next').click();
  await expect(page.locator('#onboarding-panel')).toContainText('Не указано');
  await expect(page.locator('#onboarding-panel summary', { hasText: 'Сообщить о неточности' })).toBeVisible();
  await page.locator('#onboarding-next').click();
  for (const answer of ['Synthetic 1','Synthetic 2','Synthetic 3']) {
    await page.locator('#onboarding-panel textarea').fill(answer);
    await page.locator('#onboarding-next').click();
  }
  await page.locator('[data-edit-answer="0"]').click();
  await page.locator('#onboarding-panel textarea').fill('Synthetic edited');
  await page.locator('#onboarding-next').click();
  await expect(page.locator('#onboarding-panel')).toContainText('Synthetic edited');
  await page.locator('#onboarding-next').click();
  await expect(page.locator('#onboarding-title')).toHaveText('Что показывает оценка 4К');
  expect(run.model.mandatory_complete).toBe(true);
  expect(run.unexpected).toEqual([]);
  expect(run.writes.filter((value) => /assign|prepare|start/.test(value))).toEqual([]);
  await page.screenshot({ path: info.outputPath('profile-confirmed.png'), fullPage: true });
});

test('REMAIN04 late waiting response after logout cannot restore participant', async ({ page }) => {
  test.setTimeout(90000);
  const run = await fixture(page);
  await page.goto(base);
  const check = page.getByRole('button', { name: 'Проверить готовность', exact: true });
  await expect(check).toBeVisible();
  const release = run.hold();
  const request = page.waitForRequest('**/users/8/journey-state');
  await check.click();
  await request;
  await page.locator('#auth-complete-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  release();
  await expect(page.locator('#auth-complete-panel')).toBeHidden();
  await expect(page.locator('#chat-panel')).toBeHidden();
});
