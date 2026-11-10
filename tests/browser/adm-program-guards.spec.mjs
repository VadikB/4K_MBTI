// P4K-ADM-PROGRAM-UI-FIX-01. Synthetic HTTP against the actual built UI.
// No source-module replacement, working DB, email, provider, or published TEST.
import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const root = process.cwd();
const base = 'http://127.0.0.1:18779';
let server;
const held = new Set();
const gate = () => {
  let release;
  const promise = new Promise((resolve) => { release = resolve; });
  held.add(release);
  return { promise, release };
};
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
  await new Promise((resolve) => server.listen(18779, '127.0.0.1', resolve));
});
test.afterEach(() => { held.forEach((release) => release()); held.clear(); });
test.afterAll(async () => { if (server) await new Promise((resolve) => server.close(resolve)); });

const json = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
const card = (page) => page.locator('[data-organization-id="3"]');
const manual = (page) => card(page).locator('form[data-action="preview-early-data"]');
const csv = (page) => card(page).locator('form[data-action="preview-questionnaire"]');
const connectForm = (page) => card(page).locator('form[data-action="connect-assessment-program"]');
const connection = (id) => id ? ({ organization_id: 3, program_definition_id: id,
  program_name: `Синтетическая программа ${id}`, program_version: `synthetic-${id}`,
  assignment_ref: `pilot-${id}`, roles: [{ version_id: 92, code: 'synthetic', name: 'Синтетическая роль' }],
  role_capabilities: [{ version_id: 92, code: 'synthetic', name: 'Синтетическая роль', is_available: true }] }) : null;
const revision = (ref, id = 201, status = 'confirmed', channel = 'product_form') => ({
  id, assignment_ref: ref, status, channel, source_author: 'Синтетический автор сервера',
  answers_json: { C01: { name: 'Синтетическая организация сервера' } },
  participant_preview: { organization_name: 'Синтетическая организация сервера', result_recipients: 'Участник' },
  validation_json: { errors: [], missing: [] }, recipient_mapping: ['participant'], recipient_user_ids: [],
  readiness: { status: 'ready', company: { status: 'ready' }, assessment: { status: 'ready' } },
});
const file = (label) => ({ name: `synthetic-${label}.csv`, mimeType: 'text/csv',
  buffer: Buffer.from('question_id,field,value\nC01,name,Синтетическая организация\n') });
const scopedPosts = (state) => state.requests.filter((request) => request.method === 'POST' &&
  (/\/questionnaire\/preview$/.test(request.path) || /\/questionnaire\/\d+\/confirm$/.test(request.path) ||
   /\/assessment-assignments$/.test(request.path)));
async function view(page, name) {
  await card(page).getByRole('button', { name, exact: true }).click();
}
async function forcedSubmit(form) {
  // Exercise the registered submit handler, bypassing only the disabled UI and
  // native constraint validation. The actual product function must reject scope.
  await form.evaluate((node) => node.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
}
async function settled(page) {
  // Dynamic screen imports and File.text() finish before network assertions.
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await expect.poll(() => page.evaluate(() => document.readyState)).toBe('complete');
}
async function forceAssignment(page) {
  await view(page, 'Участники оценки');
  await card(page).locator('input[name="invitation_email"]').check();
  await forcedSubmit(card(page).locator('form[data-action="assign-member-assessment"]'));
  await settled(page);
}
async function evidence(page, state, info, label) {
  await info.attach(`${label}-requests`, { body: JSON.stringify({ scope: 'local_synthetic_http_real_built_ui',
    requests: state.requests }, null, 2), contentType: 'application/json' });
  await page.screenshot({ path: info.outputPath(`${label}.png`), fullPage: true });
}

async function fixture(page, { superadmin = true, program = 11, saved = [], unknown = false,
  rolesMode = 'available', questionnaireStatus = 200 } = {}) {
  test.info().annotations.push({ type: 'synthetic_http',
    description: 'Actual built UI, scoped-command safety and draft lifecycle; no real DB/provider/PATH/TEST claim.' });
  const state = { program, requests: [], saved, nextRevision: 301, reads: 0, puts: 0,
    losePut: false, failRead: false, putGate: null,
    collectionReads: 0, collectionStatus: 200, collectionGate: null, importGate: null,
    programReadGate: null, unknown, rolesMode, questionnaireStatus };
  const fixtureConnection = () => {
    const current = connection(state.program);
    if (!current) return current;
    if (state.rolesMode === 'none') { current.roles = []; current.role_capabilities = []; }
    if (state.rolesMode === 'unavailable') current.role_capabilities = current.role_capabilities.map((role) => ({
      ...role, is_available: false, unavailable_reason: 'Опубликованная версия роли недоступна',
    }));
    if (state.rolesMode === 'unknown') { delete current.roles; delete current.role_capabilities; }
    return current;
  };
  const user = { id: 18, email: 'synthetic-admin@example.test', full_name: 'Синтетический администратор' };
  const dashboard = { is_superadmin: superadmin, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const listing = () => ({ is_superadmin: superadmin,
    assessment_programs: [11, 12].map((id) => ({ id, name: `Синтетическая программа ${id}`, version: `synthetic-${id}` })),
    items: [{ id: 3, code: 'synthetic-owned', name: 'Синтетическая организация', is_active: true,
      domains: [], admins: [{ user_id: 18, email: user.email, full_name: user.full_name }],
      members: [{ user_id: 28, email: 'synthetic-member@example.test', full_name: 'Синтетический участник',
        role_description: 'Синтетическая должность', role: 'member', assessment_assignments: [] }],
      members_count: 1, reports_count: 0, ...(state.unknown ? {} : { assessment_program: fixtureConnection() }) }] });
  await page.route('**/users/**', async (route) => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    let body;
    try { body = request.postDataJSON(); } catch { body = null; }
    state.requests.push({ method: request.method(), path: pathname, body });
    if (pathname === '/users/version') return json(route, { version: 'synthetic-adm-program-guards' });
    if (pathname === '/users/session/restore') return json(route, { authenticated: true, exists: true,
      user, is_admin: true, admin_dashboard: dashboard });
    if (pathname === '/users/admin/dashboard') return json(route, dashboard);
    if (pathname === '/users/admin/organizations') {
      state.collectionReads += 1;
      const responseListing = listing(), responseStatus = state.collectionStatus;
      await state.collectionGate;
      return responseStatus === 200 ? json(route, responseListing)
        : json(route, { detail: 'Синтетический сбой коллекции организаций' }, responseStatus);
    }
    if (pathname === '/users/admin/organizations/3/members/import') {
      const responseListing = listing();
      await state.importGate;
      return json(route, { organizations: responseListing, imported_count: 1, skipped_count: 0 });
    }
    if (pathname === '/users/admin/organizations/3' && request.method() === 'PATCH') return json(route, listing());
    if (pathname === '/users/admin/organizations/3/questionnaire') return state.questionnaireStatus === 200
      ? json(route, { items: state.saved }) : json(route, { detail: 'Synthetic questionnaire unavailable' }, state.questionnaireStatus);
    if (pathname === '/users/admin/organizations/3/assessment-program') {
      if (request.method() === 'PUT') {
        state.puts += 1;
        await state.putGate;
        state.program = body.program_definition_id;
        return state.losePut ? route.abort('connectionreset') : json(route, { connection: fixtureConnection() });
      }
      state.reads += 1;
      const responseConnection = fixtureConnection();
      await state.programReadGate;
      return state.failRead ? json(route, { detail: 'Синтетический сбой readback' }, 503)
        : json(route, { connection: responseConnection });
    }
    if (pathname === '/users/admin/organizations/3/questionnaire/preview') {
      return json(route, { ...revision(body.assignment_ref, state.nextRevision++, 'ready_for_confirmation', body.channel),
        source_author: body.source_author, answers_json: body.answers, is_first_publication: state.saved.length === 0 });
    }
    if (/\/questionnaire\/\d+\/confirm$/.test(pathname)) {
      const id = Number(pathname.match(/questionnaire\/(\d+)/)[1]);
      const savedRevision = revision(`pilot-${state.program}`, id);
      state.saved = [savedRevision]; return json(route, savedRevision);
    }
    if (/\/assessment-assignments$/.test(pathname) && request.method() === 'POST') return json(route, {
      items: [{ user_id: 28, status: 'assigned' }] });
    return json(route, { detail: `Unexpected synthetic endpoint ${pathname}` }, 404);
  });
  await page.goto(base);
  if (superadmin) {
    await expect(page.locator('#admin-open-organizations-button')).toBeVisible();
    await page.locator('#admin-open-organizations-button').click();
  }
  await expect(card(page)).toBeVisible();
  await expect.poll(() => state.requests.some((r) => r.path === '/users/admin/organizations/3/questionnaire')).toBe(true);
  await expect(card(page).locator('.admin-questionnaire-load-state').filter({ hasText: 'Загружаем' })).toHaveCount(0);
  return state;
}

for (const superadmin of [false, true]) {
  test(`ADM-PROGRAM AC01 absent ${superadmin ? 'superadmin' : 'admin'}: both real forms and commands`, async ({ page }, info) => {
    const state = await fixture(page, { superadmin, program: null, saved: [revision('pilot-11')] });
    const message = superadmin
      ? 'Программа оценки не подключена. Подключите опубликованную программу.'
      : 'Программа оценки не подключена. Обратитесь к суперадминистратору.';
    const readiness = card(page).locator('.admin-assignment-readiness');
    await expect(readiness.locator('.form-status li')).toHaveText([message]);
    await expect(readiness.locator('[data-program-next-step]')).toContainText(superadmin
      ? 'подключите опубликованную программу' : 'попросите суперадминистратора подключить опубликованную программу');
    await expect(readiness.locator('dd').nth(1)).toHaveText('ещё не проверена для программы');
    await expect(readiness.locator('dd').nth(2)).toHaveText('ещё не проверена для программы');
    await expect(readiness).not.toContainText('Оценка не выбрана');
    await view(page, 'Данные организации');
    await expect(manual(page).locator('[name="assignment_ref"]')).toHaveCount(0);
    await expect(manual(page)).toContainText(message);
    await expect(manual(page)).not.toContainText('исторический ключ');
    await manual(page).locator('[name="responsible_contact"]').fill('contact-absent@example.test');
    await forcedSubmit(manual(page));
    await settled(page);
    await view(page, 'Анкета');
    await expect(csv(page).locator('[name="assignment_ref"]')).toHaveCount(0);
    await expect(csv(page)).toContainText(message);
    await expect(csv(page)).not.toContainText('исторический ключ');
    await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
    await csv(page).locator('input[type="file"]').setInputFiles(file('absent'));
    await forcedSubmit(csv(page));
    await settled(page);
    await forceAssignment(page);
    expect(scopedPosts(state)).toEqual([]);
    if (superadmin) await expect(connectForm(page)).toBeVisible();
    else {
      await expect(connectForm(page)).toHaveCount(0);
      await view(page, 'Данные организации');
      const profile = card(page).locator('form[data-action="update-profile"]');
      await expect(profile.getByRole('button', { name: 'Сохранить карточку', exact: true })).toBeEnabled();
      await profile.locator('[name="name"]').fill('Синтетическая независимая карточка');
      await profile.getByRole('button', { name: 'Сохранить карточку', exact: true }).click();
      await expect.poll(() => state.requests.some((r) => r.path === '/users/admin/organizations/3' && r.method === 'PATCH')).toBe(true);
    }
    await evidence(page, state, info, `absent-${superadmin ? 'superadmin' : 'admin'}`);
  });
}

for (const superadmin of [false, true]) test(`ADM-PROGRAM AC02 unknown ${superadmin ? 'superadmin' : 'admin'}: no invented scope`, async ({ page }, info) => {
  const state = await fixture(page, { superadmin, unknown: true });
  const readiness = card(page).locator('.admin-assignment-readiness');
  await expect(readiness.locator('.form-status li')).toHaveCount(1);
  await expect(readiness).toContainText('Подключение программы пока не подтверждено');
  await expect(readiness.locator('dd').nth(1)).toHaveText('ещё не проверена для программы');
  await expect(readiness.locator('dd').nth(2)).toHaveText('ещё не проверена для программы');
  await expect(readiness).not.toContainText('Оценка не выбрана');
  for (const [label, form] of [['Данные организации', manual(page)], ['Анкета', csv(page)]]) {
    await view(page, label);
    await expect(form).toContainText('Подключение программы пока не подтверждено');
    await expect(form.locator('[name="assignment_ref"]')).toHaveCount(0);
    if (label === 'Данные организации') {
      await form.locator('[name="responsible_contact"]').fill('contact-unknown@example.test');
    } else {
      await form.locator('input[type="file"]').setInputFiles(file('unknown-initial'));
    }
    await forcedSubmit(form);
  }
  await forceAssignment(page);
  expect(scopedPosts(state)).toEqual([]);
  await evidence(page, state, info, 'unknown-initial');
});

test('ADM-PROGRAM AC04 absent to first connection preserves both unscoped drafts', async ({ page }, info) => {
  const state = await fixture(page, { program: null });
  await view(page, 'Данные организации');
  await manual(page).locator('[name="responsible_contact"]').fill('contact-manual@example.test');
  await manual(page).locator('[name="organization_name"]').fill('Синтетические первые сведения');
  await view(page, 'Анкета');
  await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
  await csv(page).locator('input[type="file"]').setInputFiles(file('first'));
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('11');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(csv(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-11');
  await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
  await expect(csv(page).locator('[data-csv-reselect]')).toBeVisible();
  await view(page, 'Данные организации');
  await expect(manual(page).locator('[name="responsible_contact"]')).toHaveValue('contact-manual@example.test');
  await expect(manual(page).locator('[name="organization_name"]')).toHaveValue('Синтетические первые сведения');
  expect(scopedPosts(state)).toEqual([]);
  await evidence(page, state, info, 'first-connection-drafts');
});

test('ADM-PROGRAM AC02 unknown keeps old A inert; GET-only recovery uses exact B', async ({ page }, info) => {
  const state = await fixture(page, { saved: [revision('pilot-11')] });
  await view(page, 'Данные организации');
  await manual(page).locator('[name="responsible_contact"]').fill('contact-a@example.test');
  await manual(page).getByRole('button', { name: 'Сохранить черновик и предпросмотр', exact: true }).click();
  await expect(card(page).locator('.admin-questionnaire-preview')).toBeVisible();
  const before = scopedPosts(state).length;
  state.losePut = true; state.failRead = true;
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('12');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(connectForm(page)).toContainText('Результат подключения не подтверждён');
  await expect(manual(page)).toContainText('Подключение программы пока не подтверждено. Проверьте состояние подключения.');
  const readiness = card(page).locator('.admin-assignment-readiness');
  await expect(readiness.locator('.form-status li')).toHaveCount(1);
  await expect(readiness.locator('dd').nth(1)).toHaveText('ещё не проверена для программы');
  await expect(readiness.locator('dd').nth(2)).toHaveText('ещё не проверена для программы');
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveCount(0);
  await forcedSubmit(manual(page));
  const staleConfirm = card(page).locator('[data-action="confirm-questionnaire"]');
  await expect(staleConfirm).toBeDisabled();
  // Force a stale DOM click into the real module, beyond the disabled affordance.
  await staleConfirm.evaluate((button) => { button.disabled = false; button.click(); });
  await view(page, 'Анкета');
  await expect(csv(page).locator('[name="assignment_ref"]')).toHaveCount(0);
  await csv(page).locator('input[type="file"]').setInputFiles(file('unknown'));
  await forcedSubmit(csv(page));
  await settled(page);
  await forceAssignment(page);
  expect(scopedPosts(state)).toHaveLength(before);
  const puts = state.puts, reads = state.reads;
  state.failRead = false;
  await view(page, 'Данные организации');
  await manual(page).getByRole('button', { name: 'Проверить состояние подключения', exact: true }).click();
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(manual(page)).toContainText('Синтетическая программа 12');
  await expect(manual(page)).toContainText('synthetic-12');
  await expect(manual(page)).toContainText('Синтетическая роль');
  await expect(csv(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  await expect(card(page).locator('.admin-questionnaire-preview')).toHaveCount(0);
  expect(state.puts).toBe(puts); expect(state.reads).toBe(reads + 1);
  await view(page, 'Участники оценки');
  await expect(card(page).locator('form[data-action="assign-member-assessment"] button')).toBeDisabled();
  await expect(readiness.locator('dd').nth(2)).toHaveText('не подтверждена');
  await expect(readiness.locator('.form-status li')).toHaveCount(1);
  await expect(readiness).toContainText('Анкета для выбранной оценки не подтверждена');
  await evidence(page, state, info, 'unknown-to-exact-B');
});

test('ADM-PROGRAM AC04 manual and CSV authors remain scoped across A to B to A; file reselect is explicit', async ({ page }, info) => {
  const state = await fixture(page);
  await view(page, 'Данные организации');
  await manual(page).locator('[name="responsible_contact"]').fill('contact-a@example.test');
  await manual(page).locator('[name="organization_name"]').fill('Синтетическая организация A');
  await view(page, 'Анкета');
  await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
  await csv(page).locator('input[type="file"]').setInputFiles(file('A'));
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('12');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(csv(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
  await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
  await csv(page).locator('input[type="file"]').setInputFiles(file('B'));
  await view(page, 'Данные организации');
  await expect(manual(page).locator('[name="responsible_contact"]')).toHaveValue('');
  await expect(manual(page).locator('[name="organization_name"]')).toHaveValue('');
  await manual(page).locator('[name="responsible_contact"]').fill('contact-b@example.test');
  await manual(page).locator('[name="organization_name"]').fill('Синтетическая организация B');
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('11');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-11');
  await expect(manual(page).locator('[name="responsible_contact"]')).toHaveValue('contact-a@example.test');
  await expect(manual(page).locator('[name="organization_name"]')).toHaveValue('Синтетическая организация A');
  await view(page, 'Анкета');
  await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
  await expect(csv(page).locator('[data-csv-reselect]')).toContainText('Выберите CSV-файл повторно');
  await expect(csv(page).locator('[data-csv-reselect]')).toHaveAttribute('data-csv-reselect', 'synthetic-A.csv');
  expect(await csv(page).locator('input[type="file"]').evaluate((input) => input.files.length)).toBe(0);
  expect(scopedPosts(state)).toEqual([]);
  await evidence(page, state, info, 'A-B-A-drafts');
});

for (const channel of ['manual', 'csv']) {
  test(`ADM-PROGRAM AC02 confirmed ${channel}: tampered hidden ref cannot preview`, async ({ page }, info) => {
    const state = await fixture(page);
    await view(page, channel === 'manual' ? 'Данные организации' : 'Анкета');
    const form = channel === 'manual' ? manual(page) : csv(page);
    await expect(form.locator('[name="source_author"]')).toHaveCount(0);
    if (channel === 'csv') await form.locator('input[type="file"]').setInputFiles(file('tamper'));
    await form.locator('[name="assignment_ref"]').evaluate((input) => { input.value = 'invented-or-stale-ref'; });
    await forcedSubmit(form);
    await settled(page);
    expect(scopedPosts(state)).toEqual([]);
    await expect(card(page).locator('[data-operation-status]').last()).toContainText('Подключённая программа изменилась');
    await evidence(page, state, info, `tampered-${channel}`);
  });
}

test('ADM-PROGRAM AC02 delayed CSV File.text is rechecked after scope becomes unknown', async ({ page }, info) => {
  const state = await fixture(page);
  await view(page, 'Анкета');
  await expect(csv(page).locator('[name="source_author"]')).toHaveCount(0);
  await csv(page).locator('input[type="file"]').setInputFiles(file('delayed-A'));
  // Delay this selected native File's read only; product handlers remain intact.
  await csv(page).locator('input[type="file"]').evaluate((input) => {
    const selected = input.files[0], originalText = selected.text.bind(selected);
    selected.text = () => new Promise((resolve, reject) => {
      window.__releaseSyntheticCsv = () => originalText().then(resolve, reject);
    });
  });
  await forcedSubmit(csv(page));
  state.losePut = true; state.failRead = true;
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('12');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(csv(page)).toContainText('Подключение программы пока не подтверждено');
  await page.evaluate(() => window.__releaseSyntheticCsv());
  await settled(page);
  expect(scopedPosts(state)).toEqual([]);
  await evidence(page, state, info, 'delayed-CSV-scope');
});

async function seedStaleCollectionThroughAssignment(page, state) {
  await view(page, 'Участники оценки');
  await card(page).locator('input[name="invitation_email"]').check();
  state.collectionStatus = 503;
  const reads = state.collectionReads;
  await card(page).locator('form[data-action="assign-member-assessment"]')
    .getByRole('button', { name: 'Назначить оценку', exact: true }).click();
  await expect.poll(() => state.collectionReads).toBe(reads + 1);
  await expect(page.locator('[data-organizations-stale]')).toBeVisible();
}

for (const channel of ['manual', 'csv']) test(
  `ADM-PROGRAM AC04 failed refresh retains latest ${channel} edits`,
  async ({ page }, info) => {
    const state = await fixture(page, { saved: [revision('pilot-11')] });
    const reads = state.collectionReads;
    const pending = gate();
    state.collectionGate = pending.promise;
    state.collectionStatus = 503;
    await view(page, 'Участники оценки');
    await card(page).locator('input[name="invitation_email"]').check();
    await card(page).locator('form[data-action="assign-member-assessment"]')
      .getByRole('button', { name: 'Назначить оценку', exact: true }).click();
    await expect.poll(() => state.collectionReads).toBe(reads + 1);
    await view(page, channel === 'manual' ? 'Данные организации' : 'Анкета');
    const form = channel === 'manual' ? manual(page) : csv(page);
    if (channel === 'manual') {
      await form.locator('[name="responsible_contact"]').fill('live-contact@example.test');
      await form.locator('[name="organization_name"]').fill('Синтетические live сведения после начала GET');
    } else {
      await form.locator('input[type="file"]').setInputFiles(file('live-after-GET'));
    }
    pending.release();
    await expect(page.locator('[data-organizations-stale]')).toBeVisible();
    await expect(form).toContainText('Подключение программы пока не подтверждено');
    if (channel === 'manual') {
      await expect(form.locator('[name="responsible_contact"]')).toHaveValue('live-contact@example.test');
      await expect(form.locator('[name="organization_name"]')).toHaveValue('Синтетические live сведения после начала GET');
    } else {
      await expect(form.locator('[data-csv-reselect]')).toHaveAttribute('data-csv-reselect', 'synthetic-live-after-GET.csv');
    }
    // Now use the actual safe-refresh affordance; modify the same form again
    // while its GET is pending. This distinguishes latest input from snapshot.
    const nextPending = gate(), nextReads = state.collectionReads;
    state.collectionGate = nextPending.promise;
    await page.getByRole('button', { name: 'Обновить безопасно', exact: true }).click();
    await expect.poll(() => state.collectionReads).toBe(nextReads + 1);
    await expect(page.getByRole('button', { name: 'Обновить безопасно', exact: true })).toBeDisabled();
    if (channel === 'manual') {
      await form.locator('[name="responsible_contact"]').fill('newest-contact@example.test');
    }
    nextPending.release();
    await expect(page.getByRole('button', { name: 'Обновить безопасно', exact: true })).toBeEnabled();
    if (channel === 'manual') {
      await expect(form.locator('[name="responsible_contact"]')).toHaveValue('newest-contact@example.test');
    }
    await expect(form).toContainText('Подключение программы пока не подтверждено');
    expect(scopedPosts(state).filter((request) => !request.path.endsWith('/assessment-assignments'))).toEqual([]);
    await evidence(page, state, info, `failed-refresh-latest-${channel}`);
  },
);

test('ADM-PROGRAM AC04 older collection GET cannot invalidate exact B readback', async ({ page }, info) => {
  const state = await fixture(page, { saved: [revision('pilot-11')] });
  await seedStaleCollectionThroughAssignment(page, state);
  const pending = gate(), reads = state.collectionReads;
  state.collectionStatus = 200;
  state.collectionGate = pending.promise;
  await page.getByRole('button', { name: 'Обновить безопасно', exact: true }).click();
  await expect.poll(() => state.collectionReads).toBe(reads + 1);
  // The independent allowed profile PATCH returns a newer successful collection
  // while the old safe GET remains held; this clears stale through real UI.
  await card(page).locator('form[data-action="update-profile"]')
    .getByRole('button', { name: 'Сохранить карточку', exact: true }).click();
  await expect(page.locator('[data-organizations-stale]')).toHaveCount(0);
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('12');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(connectForm(page)).toContainText('Опубликованная версия программы подключена');
  const oldResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname === '/users/admin/organizations' && response.request().method() === 'GET');
  pending.release();
  await oldResponse;
  await settled(page);
  await view(page, 'Данные организации');
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  await expect(manual(page)).toContainText('Синтетическая программа 12');
  await expect(page.locator('[data-organizations-stale]')).toHaveCount(0);
  await evidence(page, state, info, 'older-collection-after-B-readback');
});

test('ADM-PROGRAM AC02 older import collection cannot authorize stale program A', async ({ page }, info) => {
  const state = await fixture(page);
  const pending = gate(); state.importGate = pending.promise;
  const form = card(page).locator('form[data-action="import-members"]');
  await form.locator('input[type="file"]').setInputFiles(file('members'));
  await form.getByRole('button', { name: 'Импорт', exact: true }).click();
  await expect.poll(() => state.requests.some((r) => r.path.endsWith('/members/import'))).toBe(true);
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('12');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(connectForm(page)).toContainText('Опубликованная версия программы подключена');
  const importResponse = page.waitForResponse((r) => new URL(r.url()).pathname.endsWith('/members/import'));
  pending.release(); await importResponse; await settled(page);
  await view(page, 'Данные организации');
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  await manual(page).locator('[name="responsible_contact"]').fill('contact-b@example.test');
  await manual(page).getByRole('button', { name: 'Сохранить черновик и предпросмотр', exact: true }).click();
  await expect(card(page).locator('.admin-questionnaire-preview')).toBeVisible();
  expect(scopedPosts(state).map((r) => r.body.assignment_ref)).toEqual(['pilot-12']);
  await evidence(page, state, info, 'import-before-B-readback');
});

test('ADM-PROGRAM AC04 older failed load cannot invalidate exact B readback', async ({ page }, info) => {
  const state = await fixture(page, { saved: [revision('pilot-11')] });
  const pending = gate(), reads = state.collectionReads;
  state.collectionGate = pending.promise; state.collectionStatus = 503;
  await card(page).locator('input[name="invitation_email"]').check();
  await card(page).locator('form[data-action="assign-member-assessment"]')
    .getByRole('button', { name: 'Назначить оценку', exact: true }).click();
  await expect.poll(() => state.collectionReads).toBe(reads + 1);
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('12');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await expect(connectForm(page)).toContainText('Опубликованная версия программы подключена');
  const oldResponse = page.waitForResponse((r) => new URL(r.url()).pathname === '/users/admin/organizations');
  pending.release(); await oldResponse; await settled(page);
  await view(page, 'Данные организации');
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  await expect(page.locator('[data-organizations-stale]')).toHaveCount(0);
  await evidence(page, state, info, 'older-failed-load-after-B');
});

test('ADM-PROGRAM AC02 old program GET cannot confirm A over a newer collection B', async ({ page }, info) => {
  const state = await fixture(page, { unknown: true });
  const pending = gate(); state.programReadGate = pending.promise;
  await view(page, 'Данные организации');
  await manual(page).getByRole('button', { name: 'Проверить состояние подключения', exact: true }).click();
  await expect.poll(() => state.reads).toBe(1);
  state.unknown = false; state.program = 12;
  const profile = card(page).locator('form[data-action="update-profile"]');
  await profile.getByRole('button', { name: 'Сохранить карточку', exact: true }).click();
  await expect(profile.locator('[data-operation-status]')).toContainText('Карточка организации сохранена');
  const readback = page.waitForResponse((r) => new URL(r.url()).pathname.endsWith('/assessment-program'));
  pending.release(); await readback; await settled(page);
  await expect(manual(page)).toContainText('Подключение программы пока не подтверждено');
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveCount(0);
  await forcedSubmit(manual(page));
  await forceAssignment(page);
  expect(scopedPosts(state)).toEqual([]);
  state.programReadGate = null;
  await view(page, 'Данные организации');
  await manual(page).getByRole('button', { name: 'Проверить состояние подключения', exact: true }).click();
  await expect(manual(page).locator('[name="assignment_ref"]')).toHaveValue('pilot-12');
  expect(state.puts).toBe(0); expect(state.reads).toBe(2);
  await evidence(page, state, info, 'old-program-GET-newer-B-collection');
});

for (const scenario of [
  { name: 'role unknown, questionnaire confirmed', rolesMode: 'unknown', confirmed: true, label: 'актуальность не проверена', reason: 'Не удалось проверить доступные роли', blockers: 1 },
  { name: 'no allowed roles, questionnaire confirmed', rolesMode: 'none', confirmed: true, label: 'недоступна', reason: 'нет доступной роли', blockers: 1 },
  { name: 'unavailable role and unconfirmed questionnaire', rolesMode: 'unavailable', confirmed: false, label: 'Синтетическая роль · недоступна', reason: 'Опубликованная версия роли недоступна', blockers: 2 },
  { name: 'available role, unconfirmed exact questionnaire', rolesMode: 'available', confirmed: false, label: 'Синтетическая роль', reason: 'Анкета для выбранной оценки не подтверждена', blockers: 1 },
  { name: 'available role and confirmed exact questionnaire', rolesMode: 'available', confirmed: true, label: 'Синтетическая роль', blockers: 0 },
]) test(`ADM-PROGRAM readiness confirmed: ${scenario.name}`, async ({ page }, info) => {
  const state = await fixture(page, { superadmin: false, rolesMode: scenario.rolesMode,
    saved: [revision(scenario.confirmed ? 'pilot-11' : 'old-program')] });
  const readiness = card(page).locator('.admin-assignment-readiness');
  await expect(readiness.locator('dd').nth(1)).toHaveText(scenario.label);
  await expect(readiness.locator('dd').nth(2)).toHaveText(scenario.confirmed ? 'подтверждена' : 'не подтверждена');
  await expect(readiness.locator('.form-status li')).toHaveCount(scenario.blockers);
  if (scenario.reason) await expect(readiness).toContainText(scenario.reason);
  await expect(readiness).not.toContainText('Оценка не выбрана');
  await card(page).locator('input[name="invitation_email"]').check();
  const button = card(page).locator('form[data-action="assign-member-assessment"] button');
  if (scenario.blockers) {
    await expect(button).toBeDisabled();
    expect(scopedPosts(state)).toEqual([]);
  } else {
    await expect(button).toBeEnabled(); await button.click();
    await expect.poll(() => scopedPosts(state).length).toBe(1);
    expect(scopedPosts(state)[0].body.assignment_ref).toBe('pilot-11');
    expect(scopedPosts(state)[0].body.role_profile_version_id).toBe(92);
  }
  await view(page, 'Данные организации');
  await expect(card(page).locator('form[data-action="update-profile"] button')).toBeEnabled();
  await evidence(page, state, info, 'confirmed-readiness-' + scenario.rolesMode);
});

test('ADM-PROGRAM readiness cached confirmation plus failed read stays unknown', async ({ page }, info) => {
  const state = await fixture(page, { saved: [revision('pilot-11')] });
  state.questionnaireStatus = 503;
  await connectForm(page).locator('[name="program_definition_id"]').selectOption('11');
  await connectForm(page).getByRole('button', { name: 'Подключить', exact: true }).click();
  await view(page, 'Данные организации');
  await expect(card(page).locator('.admin-questionnaire-load-state.error').first()).toBeVisible();
  await view(page, 'Участники оценки');
  const readiness = card(page).locator('.admin-assignment-readiness');
  await expect(readiness.locator('dd').nth(2)).toHaveText('подтверждена по сохранённой редакции; актуальность не проверена');
  await expect(readiness).toContainText('Не удалось проверить сохранённую анкету');
  await expect(readiness).not.toContainText('Анкета для выбранной оценки не подтверждена');
  await card(page).locator('input[name="invitation_email"]').check();
  await expect(card(page).locator('form[data-action="assign-member-assessment"] button')).toBeDisabled();
  expect(scopedPosts(state)).toEqual([]);
  await evidence(page, state, info, 'cached-confirmation-read-unknown');
});
