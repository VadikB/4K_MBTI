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
const fields = (label) => ({ organization_name: `Синтетическая ИТ-компания ${label}`,
  organization_type: `ИТ-разработка ${label}` });
async function fill(page, values, id = 3) {
  for (const [name, value] of Object.entries(values)) await form(page, id).locator(`[name="${name}"]`).fill(value);
}
async function assertValues(page, values, id = 3) {
  for (const [name, value] of Object.entries(values)) {
    const expected = values === empty && name === 'organization_name' ? `Synthetic organization ${id}` : value;
    await expect(form(page, id).locator(`[name="${name}"]`)).toHaveValue(expected);
  }
}
const empty = Object.fromEntries(Object.keys(fields('')).map((name) => [name, '']));
const confirmed = { id: 201, status: 'confirmed', channel: 'product_form', assignment_ref: 'pilot-11',
  source_author: 'Исторический автор',
  answers_json: {
    C01: { name: 'Synthetic organization 3', organization_type: fields('сервер').organization_type },
    C02a: { participant_text: 'Сохранённая цель' }, C03: { participant_text: 'Сохранённое использование' },
    C17: { case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено' },
    C21: { organizer: fields('сервер').organizer },
  } };

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
    if (pathname === `/users/${state.userId}/session-bootstrap` && state.authenticated) return json(route, auth());
    if (pathname === '/users/session/logout') { state.authenticated = false; return json(route, { ok: true }); }
    if (pathname === '/users/auth/email/request-link') {
      return json(route, { email: `admin-${state.loginId}@example.test`, auth_mode: 'password' });
    }
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
  await assertValues(page, { ...fields('сервер'), organization_name: 'Synthetic organization 3' });
  await expect(form(page).locator('[name="case_reality_level"]')).toHaveValue('Реальные');
  await expect(form(page).locator('[name="organization_name_usage_rules"]')).toHaveValue('Разрешено');
  const preview = card(page).locator('[data-organization-participant-preview]');
  await expect(preview).toContainText('Сохранённая цель');
  await expect(preview).toContainText('Сохранённое использование');
  await expect(form(page).locator('[data-organization-confirmed]')).toBeVisible();
  await expect(form(page).locator('[data-early-data-submit]')).toBeHidden();
  await card(page).getByRole('button', { name: 'Участники оценки', exact: true }).click();
  await card(page).getByRole('button', { name: 'Данные организации', exact: true }).click();
  await assertValues(page, { ...fields('сервер'), organization_name: 'Synthetic organization 3' });
  expect(f.state.mutations).toEqual([]);
});

test('ADMIN-02 offers approved context choices to a new organization draft', async ({ page }) => {
  const f = await fixture(page);
  await finishRead(page, f);
  const reality = form(page).locator('select[name="case_reality_level"]');
  const nameUsage = form(page).locator('select[name="organization_name_usage_rules"]');
  await expect(reality.locator('option')).toHaveText([
    'Выберите вариант', 'Обобщённые рабочие ситуации', 'Близко к реальной работе',
  ]);
  await expect(nameUsage.locator('option')).toHaveText([
    'Выберите вариант', 'Использовать условное название', 'Можно использовать настоящее название',
  ]);
  await reality.selectOption('Близко к реальной работе');
  await nameUsage.selectOption('Использовать условное название');
  await expect(reality).toHaveValue('Близко к реальной работе');
  await expect(nameUsage).toHaveValue('Использовать условное название');
});

test('ADM-UI-02 keeps the participant preview visible for first and partial input', async ({ page }) => {
  const f = await fixture(page, { items: [{
    ...confirmed, status: 'invalid',
    answers_json: { C01: { name: 'Synthetic organization 3', organization_type: 'Компания',
      industry: 'ИТ', activity_description: 'Разрабатывает рабочие инструменты.' } },
  }] });
  const currentForm = form(page);
  const preview = card(page).locator('[data-organization-participant-preview]');
  await expect(currentForm.locator('[name="organization_name"]')).toHaveValue('Synthetic organization 3');
  await expect(preview.locator('[data-preview-value="purpose"]')).toHaveText('Цель пока не указана.');
  await finishRead(page, f);
  await expect(currentForm.locator('[name="organization_type"]')).toHaveValue('Компания');
  await expect(currentForm.locator('[name="industry"]')).toHaveValue('ИТ');
  await expect(currentForm.locator('[name="activity_description"]')).toHaveValue('Разрабатывает рабочие инструменты.');
  await expect(currentForm.locator('[name="case_reality_level"]')).toHaveValue('');
  await fill(page, { purpose: 'Цель для участника', results_usage: 'Для развития' });
  await expect(preview.locator('[data-preview-value="purpose"]')).toHaveText('Цель для участника');
  await expect(preview.locator('[data-preview-value="results_usage"]')).toHaveText('Для развития');
  await expect(preview).toContainText('Вы и действующие администраторы вашей организации.');
  await expect(currentForm.locator('fieldset legend')).toHaveText([
    'Об организации', 'Сведения для знакомства', 'Настройки контекста для ситуаций',
  ]);

  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => window.scrollTo(0, 0));
    const box = await currentForm.boundingBox();
    const panel = await preview.boundingBox();
    const action = await currentForm.locator('[data-early-data-submit]').boundingBox();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect(action.x + action.width).toBeLessThanOrEqual(width);
    if (width === 1440) {
      expect(panel.width).toBeGreaterThanOrEqual(230);
      expect(panel.width).toBeLessThanOrEqual(300);
      expect(panel.x).toBeGreaterThan(box.x + box.width);
      expect(panel.y).toBeCloseTo(box.y, 0);
    } else {
      expect(panel.y).toBeGreaterThan(box.y + box.height);
    }
  }
  expect(f.state.mutations).toEqual([]);
});

test('ADM-FIX-04 explains unsupported saved C17 choice and retains the draft', async ({ page }) => {
  const draft = { ...confirmed, id: 202, status: 'invalid',
    effective_confirmed: { id: 201, assignment_ref: 'pilot-11', confirmed_at: '2026-11-19T10:00:00Z' },
    answers_json: { ...confirmed.answers_json,
      C17: { ...confirmed.answers_json.C17, organization_name_usage_rules: 'Неизвестный вариант' } },
    validation_json: { errors: [{ code: 'CONTEXT_CHOICE_UNSUPPORTED', question_id: 'C17',
      field: 'organization_name_usage_rules', line: 12 }], missing: [] } };
  const f = await fixture(page, { items: [draft] });
  await finishRead(page, f);
  await expect(card(page).locator('[data-context-choice-warning]')).toContainText(
    'неподдерживаемое значение: использование названия организации');
  await expect(form(page).locator('[name="organization_name_usage_rules"]')).toHaveValue('Неизвестный вариант');
  await expect(card(page).locator('[data-action="confirm-questionnaire"]')).toHaveCount(0);
});

test('ADM-FIX-04 explains unavailable policy on a saved draft', async ({ page }) => {
  const draft = { ...confirmed, id: 203, status: 'invalid',
    validation_json: { errors: [{ code: 'ADMIN_CONTEXT_CHOICES_UNAVAILABLE' }], missing: [] } };
  const f = await fixture(page, { items: [draft] });
  await finishRead(page, f);
  await expect(card(page).locator('[data-context-choice-warning]')).toContainText(
    'не удалось проверить утверждённые варианты');
  await expect(card(page).locator('[data-action="confirm-questionnaire"]')).toHaveCount(0);
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
test('ADM-UI-02 restores pending confirmation only for its account, organization and assessment', async ({ page }) => {
  const f = await fixture(page);
  await finishRead(page, f);
  const originalRef = 'pilot-11';
  const proposedName = 'Новое имя из исходного запроса';
  const stored = { id: 301, assignment_ref: originalRef, status: 'ready_for_confirmation', channel: 'product_form' };
  await page.route('**/users/admin/organizations/3/questionnaire/preview', (route) => {
    stored.answers_json = route.request().postDataJSON().answers;
    return json(route, stored, 201);
  });
  let confirmPosts = 0;
  await page.route('**/users/admin/organizations/3/questionnaire/301/confirm', async (route) => {
    confirmPosts += 1;
    await route.abort('connectionreset');
  });
  const exactReads = [];
  await page.route('**/users/admin/organizations/*/questionnaire/301', (route) => {
    const organizationId = Number(new URL(route.request().url()).pathname.split('/')[4]);
    exactReads.push({ account: f.state.userId, organizationId, program: f.state.programs[organizationId] });
    return json(route, stored);
  });

  await fill(page, { organization_name: proposedName, purpose: 'Исходная цель' });
  await form(page).locator('[data-early-data-submit]').click();
  await form(page).locator('[data-action="confirm-questionnaire"]').click();
  await expect(form(page).locator('.admin-data-confirmation-recovery')).toBeVisible();

  const openData = async (org, assessmentRef) => {
    const landing = page.locator('#admin-open-organizations-button');
    const management = page.locator('#admin-organizations-panel');
    await expect.poll(async () => await landing.isVisible() || await management.isVisible()).toBe(true);
    if (await landing.isVisible()) await landing.click();
    await page.locator('#admin-organization-select').selectOption(String(org));
    await card(page, org).getByRole('button', { name: 'Данные организации', exact: true }).click();
    await expect(form(page, org).locator('[name="assignment_ref"]')).toHaveValue(assessmentRef);
  };
  const signInAs = async (id) => {
    f.state.loginId = id;
    await page.locator('#admin-organizations-account-name').click();
    await page.locator('#admin-organizations-logout-button').click();
    await expect(page.locator('#auth-panel')).toBeVisible();
    await page.locator('#email-input').fill(`admin-${id}@example.test`);
    await page.locator('#request-magic-link-button').click();
    await page.locator('#magic-token-input').fill('synthetic-password');
    await page.locator('#verify-magic-link-button').click();
    await expect.poll(() => f.state.userId).toBe(id);
  };

  f.state.programs[3] = 12;
  await page.reload();
  await openData(3, 'pilot-12');
  await expect(form(page).locator('[data-early-data-submit]')).toBeEnabled();
  expect(exactReads).toEqual([]);

  await openData(4, originalRef);
  await expect(form(page, 4).locator('[data-early-data-submit]')).toBeEnabled();
  expect(exactReads).toEqual([]);

  f.state.programs[3] = 11;
  await signInAs(28);
  await openData(3, originalRef);
  await expect(form(page).locator('[data-early-data-submit]')).toBeEnabled();
  expect(exactReads).toEqual([]);

  await signInAs(18);
  await openData(3, originalRef);
  const retry = form(page).locator('[data-action="confirm-questionnaire"]');
  await expect(retry).toBeEnabled();
  await expect(retry).toHaveAttribute('data-value', '301');
  await expect(form(page).locator('[name="purpose"]')).toHaveValue('Исходная цель');
  expect(exactReads).toEqual([{ account: 18, organizationId: 3, program: 11 }]);
  expect(confirmPosts).toBe(1);
});

test('Q-DRAFT old account read cannot erase or restore drafts after re-login', async ({ page }) => {
  const f = await fixture(page); await fill(page, fields('A'));
  await page.locator('#admin-organizations-account-name').click();
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  await page.locator('#email-input').fill('admin-28@example.test');
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('synthetic-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#admin-organizations-account-name')).toHaveText('Synthetic admin 28');
  await card(page).getByRole('button', { name: 'Данные организации', exact: true }).click();
  await expect(card(page).locator('[data-admin-view="organization-data"] .admin-questionnaire-load-state')).toHaveCount(0);
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
  await card(page).getByRole('button', { name: 'Участники оценки', exact: true }).click();
  await card(page).getByRole('button', { name: 'Данные организации', exact: true }).click();
  await assertValues(page, status === 403 ? empty : changed);
  expect(f.state.mutations).toEqual([]);
});
