// Synthetic HTTP only; real entry/dist, no replacement DOM/product methods.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
const root = process.cwd();
const base = 'http://127.0.0.1:18767';
let server;
const releases = new Set();
const gate = () => {
  let release;
  const promise = new Promise((resolve) => { release = resolve; });
  releases.add(release);
  return { promise, release };
};
test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const file = path.join(root, new URL(request.url, base).pathname === '/' ? 'web/index.html' : new URL(request.url, base).pathname);
      response.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
        '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      response.end(await fs.readFile(file));
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise((resolve) => server.listen(18767, '127.0.0.1', resolve));
});
test.afterEach(() => { releases.forEach((release) => release()); releases.clear(); });
test.afterAll(async () => new Promise((resolve) => server.close(resolve)));
const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
const success = 'Опубликованная версия программы подключена';
const recovery = 'Подключение подтверждено повторным чтением';
const form = (page) => page.locator('[data-organization-id="3"] [data-action="connect-assessment-program"]');
const status = (page) => form(page).locator('[data-operation-status]');
const connection = (org, program) => ({ organization_id: org, program_definition_id: program,
  program_name: `Synthetic pilot ${program}`, program_version: 'synthetic-1', assignment_ref: `pilot-${program}`, roles: [], role_capabilities: [] });

async function fixture(page, { questionnaireStatus = 503, lostPut = false } = {}) {
  const questionnaire = gate();
  const state = { linked: 0, puts: 0, reads: 0, questionnaires: 0, failNextPut: false, commandGate: null };
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const user = (id = 18) => ({ id, email: `admin-${id}@example.test`, full_name: `Synthetic admin ${id}` });
  const auth = (id = 18) => ({ authenticated: true, exists: true, user: user(id), is_admin: true, admin_dashboard: dashboard });
  const organization = (id) => ({ id, code: `synthetic-${id}`, name: `Synthetic organization ${id}`, is_active: true,
    domains: [], admins: [], members: [], members_count: 0, reports_count: 0,
    assessment_program: id === 4 ? connection(4, 11) : state.linked ? connection(3, state.linked) : null });
  let initialQuestionnaire = true;
  await page.route('**/users/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return json(route, { version: 'synthetic-r10-feedback' });
    if (pathname === '/users/session/restore') return json(route, auth());
    if (pathname === '/users/session/logout') return json(route, { ok: true });
    if (pathname === '/users/auth/email/request-link') return json(route, { email: user(28).email, auth_mode: 'password' });
    if (pathname === '/users/auth/email/password-login') return json(route, auth(28));
    if (pathname === '/users/admin/dashboard') return json(route, dashboard);
    if (pathname === '/users/admin/organizations') return json(route, { is_superadmin: true,
      items: [organization(3), organization(4)], assessment_programs: [11, 12].map((id) => ({ id, name: `Synthetic pilot ${id}`, version: 'synthetic-1' })) });
    if (pathname.endsWith('/questionnaire')) {
      state.questionnaires += 1;
      if (pathname.includes('/3/') && initialQuestionnaire) { initialQuestionnaire = false; await questionnaire.promise; }
      return questionnaireStatus === 200 ? json(route, { items: [] }) : json(route, { detail: 'Synthetic questionnaire unavailable' }, questionnaireStatus);
    }
    if (pathname === '/users/admin/organizations/3/assessment-program') {
      if (route.request().method() === 'PUT') {
        state.puts += 1;
        await state.commandGate;
        if (state.failNextPut) return json(route, { detail: 'Synthetic rejected command' }, 503);
        state.linked = route.request().postDataJSON().program_definition_id;
        return lostPut ? route.abort('connectionreset') : json(route, { connection: connection(3, state.linked) });
      }
      state.reads += 1;
      return json(route, { connection: state.linked ? connection(3, state.linked) : null });
    }
    return json(route, {}, 404);
  });
  await page.goto(base);
  await expect(page.locator('#admin-open-organizations-button')).toBeVisible();
  await page.locator('#admin-open-organizations-button').click();
  await expect(form(page)).toBeVisible();
  return { state, releaseQuestionnaire: questionnaire.release, message: lostPut ? recovery : success };
}
async function connect(page, f) {
  await form(page).locator('[name="program_definition_id"]').selectOption('11');
  await form(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(status(page)).toContainText(f.message);
}
async function rerender(page) {
  // Non-mutating real UI action triggers the same card renderer. This is also a
  // deterministic barrier: assertions cannot pass just before a delayed render.
  await page.locator('[data-organization-id="3"]').getByRole('button', { name: 'Данные организации', exact: true }).click();
}
for (const questionnaireStatus of [200, 503]) for (const lostPut of [false, true]) {
  test(`R10-STATUS ${questionnaireStatus} ${lostPut ? 'lost' : 'confirmed'} survives completion and re-render`, async ({ page }, info) => {
    info.annotations.push({ type: 'synthetic_http', description: 'Real UI and render; no DB/provider or real program admission.' });
    const f = await fixture(page, { questionnaireStatus, lostPut });
    await connect(page, f);
    expect(f.state.questionnaires).toBeGreaterThanOrEqual(2);
    f.releaseQuestionnaire();
    await rerender(page);
    await expect(status(page)).toContainText(f.message);
    await expect(status(page)).toHaveAttribute('data-tone', 'success');
    await expect(form(page)).toContainText('Подключено: Synthetic pilot 11');
    expect(f.state.puts).toBe(1); expect(f.state.reads).toBe(1);
    await page.screenshot({ path: info.outputPath('persistent-outcome.png') });
  });
}
test('R10-STATUS changing program clears the prior outcome without resurrection', async ({ page }) => {
  const f = await fixture(page); await connect(page, f); f.releaseQuestionnaire();
  await form(page).locator('[name="program_definition_id"]').selectOption('12');
  await expect(status(page)).toHaveCount(0);
  await rerender(page); await expect(status(page)).toHaveCount(0);
  await form(page).locator('[name="program_definition_id"]').selectOption('11');
  await rerender(page); await expect(status(page)).toHaveCount(0);
  expect(f.state.puts).toBe(1);
});
test('R10-STATUS a new failed intent cannot revive success and its error survives render', async ({ page }) => {
  const f = await fixture(page); await connect(page, f); f.releaseQuestionnaire();
  f.state.failNextPut = true;
  await form(page).locator('[name="program_definition_id"]').selectOption('12');
  await form(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(status(page)).toContainText('Результат подключения не подтверждён');
  await rerender(page);
  await expect(status(page)).toHaveAttribute('data-tone', 'error');
  await expect(status(page)).not.toContainText(success);
  expect(f.state.puts).toBe(2);
});
test('R10-STATUS same program in another organization never receives the old outcome', async ({ page }) => {
  const f = await fixture(page); await connect(page, f); f.releaseQuestionnaire();
  await page.locator('#admin-organization-select').selectOption('4');
  await expect(page.locator('[data-organization-id="4"]')).toContainText('Подключено: Synthetic pilot 11');
  await expect(page.locator('[data-organization-id="4"] [data-operation-status]')).toHaveCount(0);
  await page.locator('#admin-organization-select').selectOption('3');
  await expect(status(page)).toHaveCount(0);
});
test('R10-STATUS logout and another account cannot restore the previous outcome', async ({ page }) => {
  const f = await fixture(page); await connect(page, f); f.releaseQuestionnaire();
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  await page.locator('#email-input').fill('admin-28@example.test');
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('synthetic-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#admin-panel')).toBeVisible();
  await page.locator('#admin-open-organizations-button').click();
  await expect(page.locator('#admin-organizations-account-name')).toHaveText('Synthetic admin 28');
  await expect(form(page)).toContainText('Подключено: Synthetic pilot 11');
  await expect(status(page)).toHaveCount(0);
});
test('R10-STATUS a late command cannot restore feedback after program selection changes', async ({ page }) => {
  const f = await fixture(page); f.releaseQuestionnaire();
  const held = gate(); f.state.commandGate = held.promise;
  await form(page).locator('[name="program_definition_id"]').selectOption('11');
  await form(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect.poll(() => f.state.puts).toBe(1);
  await form(page).locator('[name="program_definition_id"]').selectOption('12');
  held.release();
  await expect(form(page)).toContainText('Подключено: Synthetic pilot 11');
  await rerender(page); await expect(status(page)).toHaveCount(0);
  await form(page).locator('[name="program_definition_id"]').selectOption('11');
  await rerender(page); await expect(status(page)).toHaveCount(0);
});
test('R10-STATUS changed server program invalidates the saved outcome even with an old draft', async ({ page }) => {
  const f = await fixture(page); await connect(page, f); f.releaseQuestionnaire();
  f.state.linked = 12;
  await page.locator('#admin-organizations-back-button').click();
  await expect(page.locator('#admin-panel')).toBeVisible();
  await page.locator('#admin-open-organizations-button').click();
  await expect(form(page)).toContainText('Подключено: Synthetic pilot 12');
  await expect(status(page)).toHaveCount(0);
});
