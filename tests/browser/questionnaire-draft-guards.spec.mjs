// Synthetic HTTP lifecycle guards through real entry/dist. No DOM/product-method
// replacement. These tests do not claim real DB, admission or real-provider PATH.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const root = process.cwd(), base = 'http://127.0.0.1:18768';
let server;
const releases = new Set();
function gate() {
  let release;
  const promise = new Promise((resolve) => { release = resolve; });
  releases.add(release); return { promise, release };
}
test.beforeAll(async () => {
  server = http.createServer(async (request, response) => {
    try {
      const pathname = new URL(request.url, base).pathname;
      const file = path.join(root, pathname === '/' ? 'web/index.html' : pathname);
      response.setHeader('Content-Type', { '.html': 'text/html', '.js': 'application/javascript',
        '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      response.end(await fs.readFile(file));
    } catch { response.statusCode = 404; response.end('missing'); }
  });
  await new Promise((resolve) => server.listen(18768, '127.0.0.1', resolve));
});
test.afterEach(() => { releases.forEach((release) => release()); releases.clear(); });
test.afterAll(async () => new Promise((resolve) => server.close(resolve)));
const json = (route, value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) });
const card = (page, id = 3) => page.locator(`[data-organization-id="${id}"]`);
const form = (page, id = 3) => card(page, id).locator('[data-action="preview-early-data"]');
const fields = (label) => ({ source_author: `Синтетический автор ${label}`,
  organization_name: `Синтетическая ИТ-компания ${label}`, organization_type: `ИТ-разработка ${label}` });
async function fill(page, values, id = 3) {
  for (const [name, value] of Object.entries(values)) await form(page, id).locator(`[name="${name}"]`).fill(value);
}
async function assertValues(page, values, id = 3) {
  for (const [name, value] of Object.entries(values)) await expect(form(page, id).locator(`[name="${name}"]`)).toHaveValue(value);
}
const empty = Object.fromEntries(Object.keys(fields('')).map((name) => [name, '']));
const confirmed = { id: 201, status: 'confirmed', channel: 'product_form', assignment_ref: 'pilot-11',
  source_author: fields('сервер').source_author,
  answers_json: { C01: { name: fields('сервер').organization_name, organization_type: fields('сервер').organization_type } } };

async function fixture(page, { status = 200, items = [] } = {}) {
  test.info().annotations.push({ type: 'synthetic_http', description: 'Q-DRAFT identity/org/assessment/denial lifecycle only; no DB/provider/PATH admission' });
  const initial = gate(); let initialDone;
  const done = new Promise((resolve) => { initialDone = resolve; });
  const state = { authenticated: true, userId: 18, loginId: 28, status, items, reads: 0, initialHeld: false,
    programs: { 3: 11, 4: 11 }, nextRead: null, mutations: [] };
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const user = () => ({ id: state.userId, email: `admin-${state.userId}@example.test`, full_name: `Synthetic admin ${state.userId}` });
  const auth = () => ({ authenticated: true, exists: true, user: user(), is_admin: true, admin_dashboard: dashboard });
  const connection = (id) => ({ organization_id: id, program_definition_id: state.programs[id],
    program_name: `Synthetic pilot ${state.programs[id]}`, program_version: 'synthetic-1',
    assignment_ref: `pilot-${state.programs[id]}`, roles: [], role_capabilities: [] });
  await page.route('**/users/**', async (route) => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    if (request.method() !== 'GET') state.mutations.push({ method: request.method(), path: pathname });
    if (pathname === '/users/version') return json(route, { version: 'synthetic-questionnaire-guards' });
    if (pathname === '/users/session/restore') return json(route, state.authenticated ? auth() : { authenticated: false });
    if (pathname === '/users/session/logout') { state.authenticated = false; return json(route, { ok: true }); }
    if (pathname === '/users/auth/email/request-link') return json(route, { email: 'admin-28@example.test', auth_mode: 'password' });
    if (pathname === '/users/auth/email/password-login') {
      state.userId = state.loginId; state.authenticated = true; return json(route, auth());
    }
    if (pathname === '/users/admin/dashboard') return json(route, dashboard);
    if (pathname === '/users/admin/organizations') return json(route, { is_superadmin: true,
      assessment_programs: [11, 12].map((id) => ({ id, name: `Synthetic pilot ${id}`, version: 'synthetic-1' })),
      items: [3, 4].map((id) => ({ id, code: `synthetic-${id}`, name: `Synthetic organization ${id}`,
        is_active: true, domains: [], admins: [], members: [], members_count: 0, reports_count: 0,
        assessment_program: connection(id) })) });
    const questionnaire = pathname.match(/^\/users\/admin\/organizations\/(3|4)\/questionnaire$/);
    if (questionnaire) {
      state.reads += 1;
      const isInitial = questionnaire[1] === '3' && !state.initialHeld;
      if (isInitial) { state.initialHeld = true; await initial.promise; }
      else await state.nextRead;
      await json(route, state.status === 200 ? { items: state.items } : { detail: 'Synthetic questionnaire read denied/unavailable' }, state.status);
      if (isInitial) initialDone();
      return;
    }
    const program = pathname.match(/^\/users\/admin\/organizations\/(3|4)\/assessment-program$/);
    if (program) {
      const id = Number(program[1]);
      if (request.method() === 'PUT') state.programs[id] = request.postDataJSON().program_definition_id;
      return json(route, { connection: connection(id) });
    }
    return json(route, {}, 404);
  });
  await page.goto(base);
  await expect(page.locator('#admin-open-organizations-button')).toBeVisible();
  await page.locator('#admin-open-organizations-button').click();
  await expect(card(page)).toBeVisible();
  await expect.poll(() => state.initialHeld).toBe(true);
  await card(page).getByRole('button', { name: 'Данные организации', exact: true }).click();
  return { state, release: initial.release, done };
}
async function finishRead(page, f) {
  f.release(); await f.done;
  await page.evaluate(() => new Promise(requestAnimationFrame));
}

test('Q-DRAFT pristine initial form does not mask a confirmed server revision', async ({ page }) => {
  const f = await fixture(page, { items: [confirmed] });
  await finishRead(page, f);
  await assertValues(page, fields('сервер'));
  await card(page).getByRole('button', { name: 'Организация и участники', exact: true }).click();
  await card(page).getByRole('button', { name: 'Данные организации', exact: true }).click();
  await assertValues(page, fields('сервер'));
  expect(f.state.mutations).toEqual([]);
});
test('Q-DRAFT live input wins over a delayed confirmed revision in the same scope', async ({ page }) => {
  const f = await fixture(page, { items: [confirmed] });
  await fill(page, fields('черновик')); await finishRead(page, f);
  await assertValues(page, fields('черновик'));
  expect(f.state.mutations).toEqual([]);
});
test('Q-DRAFT pending read of organization A cannot overwrite organization B draft', async ({ page }) => {
  const f = await fixture(page); await fill(page, fields('A'));
  await page.locator('#admin-organization-select').selectOption('4');
  await card(page, 4).getByRole('button', { name: 'Данные организации', exact: true }).click();
  await assertValues(page, empty, 4); await fill(page, fields('B'), 4);
  await finishRead(page, f); await assertValues(page, fields('B'), 4);
  await page.locator('#admin-organization-select').selectOption('3');
  await assertValues(page, fields('A'));
});
test('Q-DRAFT pending read cannot clone a draft into a different connected assessment', async ({ page }) => {
  const f = await fixture(page); await fill(page, fields('A'));
  const connect = card(page).locator('[data-action="connect-assessment-program"]');
  await connect.locator('[name="program_definition_id"]').selectOption('12');
  await connect.getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(connect).toContainText('Подключено: Synthetic pilot 12');
  await expect(form(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  await assertValues(page, empty); await fill(page, fields('B'));
  await finishRead(page, f); await assertValues(page, fields('B'));
  await connect.locator('[name="program_definition_id"]').selectOption('11');
  await connect.getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(connect).toContainText('Подключено: Synthetic pilot 11');
  await assertValues(page, fields('A'));
});
test('Q-DRAFT old account read cannot erase or restore drafts after re-login', async ({ page }) => {
  const f = await fixture(page); await fill(page, fields('A'));
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  await page.locator('#email-input').fill('admin-28@example.test');
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('synthetic-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#admin-panel')).toBeVisible();
  await page.locator('#admin-open-organizations-button').click();
  await expect(page.locator('#admin-organizations-account-name')).toHaveText('Synthetic admin 28');
  await card(page).getByRole('button', { name: 'Данные организации', exact: true }).click();
  await expect(card(page).locator('.admin-questionnaire-load-state').filter({ hasText: 'ещё нет сохранённых анкет' }).first()).toBeVisible();
  await assertValues(page, empty); await fill(page, fields('B'));
  await finishRead(page, f); await assertValues(page, fields('B'));
});
for (const status of [503, 403]) test(`Q-DRAFT retry ${status} ${status === 403 ? 'clears denied scope' : 'retains live edits'}`, async ({ page }) => {
  const f = await fixture(page, { status: 503 }); await finishRead(page, f);
  await fill(page, fields('A'));
  const held = gate(); f.state.nextRead = held.promise; f.state.status = status;
  await card(page).locator('.admin-questionnaire-load-state.error').first().getByRole('button', { name: 'Повторить', exact: true }).click();
  await assertValues(page, fields('A'));
  const changed = { ...fields('A'), organization_type: 'ИТ-аналитика после начала retry' };
  await fill(page, changed); held.release();
  await expect(card(page).locator('.admin-questionnaire-load-state.error').first()).toBeVisible();
  await assertValues(page, status === 403 ? empty : changed);
  await card(page).getByRole('button', { name: 'Организация и участники', exact: true }).click();
  await card(page).getByRole('button', { name: 'Данные организации', exact: true }).click();
  await assertValues(page, status === 403 ? empty : changed);
  expect(f.state.mutations).toEqual([]);
});
