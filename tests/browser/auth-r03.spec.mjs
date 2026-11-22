import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { registerAuthF01Tests } from './helpers/auth-f01.mjs';
import { registerAuthV01Tests } from './helpers/auth-v01.mjs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { capturePathViewports, viewportGeometry, assertViewportGeometry } from './fixtures/path-viewports.mjs';
import { waitForPasswordCreationForm } from './fixtures/auth-password-form.mjs';
import { captureFailurePage } from './fixtures/failure-page.mjs';

const root = process.cwd();
const port = 18764;
const publishedOrigin = process.env.AC18_FIX02_PUBLISHED_ORIGIN || '';
if (publishedOrigin && publishedOrigin !== 'https://test.4k-assistant.ru') {
  throw new Error('AC18_FIX02_PUBLISHED_ORIGIN must be the approved test origin');
}
const base = publishedOrigin || `http://127.0.0.1:${port}`;
const appRelease = (await fs.readFile(path.join(root, 'web/js/config.js'), 'utf8'))
  .match(/APP_RELEASE = "([^"]+)";/)?.[1];
if (!appRelease) throw new Error('web/js/config.js must define APP_RELEASE');
let server;

test.beforeAll(async () => {
  if (publishedOrigin) return;
  server = http.createServer(async (request, response) => {
    try {
      const pathname = new URL(request.url, base).pathname;
      const filename = path.join(root, pathname === '/' ? 'web/index.html' : pathname);
      const body = await fs.readFile(filename);
      const contentType = {
        '.css': 'text/css', '.html': 'text/html', '.js': 'application/javascript',
        '.svg': 'image/svg+xml', '.woff': 'font/woff',
      }[path.extname(filename)] || 'application/octet-stream';
      response.setHeader('Content-Type', contentType);
      response.end(body);
    } catch {
      response.statusCode = 404;
      response.end('missing');
    }
  });
  await new Promise((resolve) => server.listen(port, '127.0.0.1', resolve));
  if (process.env.W02_RESOURCE_LOG) await fs.appendFile(process.env.W02_RESOURCE_LOG, JSON.stringify({ event: 'start', pid: process.pid, port, owner: 'P4K-W02-FIX-01', db: null }) + '\n');
});

test.afterAll(async () => {
  if (!server) return;
  await new Promise((resolve) => server.close(resolve));
  if (process.env.W02_RESOURCE_LOG) await fs.appendFile(process.env.W02_RESOURCE_LOG, JSON.stringify({ event: 'stop', pid: process.pid, port, listening: server.listening }) + '\n');
});

async function blockUnmockedWrites(context) {
  if (!publishedOrigin) return;
  await context.route('**/*', (route) => route.request().method() === 'GET'
    ? route.continue() : route.abort('blockedbyclient'));
}

test.beforeEach(async ({ context }) => blockUnmockedWrites(context));

const fulfillJson = (route, body, status = 200) => route.fulfill({
  status,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

async function baseRoutes(page, restore = { authenticated: false }) {
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, restore);
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    test.info().annotations.push({ type: 'unmocked-api', description: `${route.request().method()} ${pathname}` });
    return fulfillJson(route, {}, 404);
  });
}

registerAuthF01Tests({ test, expect, baseRoutes, base, fulfillJson });
registerAuthV01Tests({ test, expect, baseRoutes, base, fulfillJson, appRelease });

const adminUser = { id: 18, email: 'admin@example.test', full_name: 'Admin' };

for (const [action, endpoint] of [
  ['email_verification', '/users/auth/email/confirm'],
  ['password_reset', '/users/auth/password/reset/validate'],
]) {
  test(`AC18 auth readiness: ${action} cannot submit before validation, then reaches step2`, async ({ page }, testInfo) => {
    await baseRoutes(page);
    let release;
    let requested = false;
    const pending = new Promise((resolve) => { release = resolve; });
    const unexpected = [];
    await page.route('**/users/auth/**', async (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === endpoint) {
        requested = true;
        await pending;
        return fulfillJson(route, { email: 'ready@example.test', auth_mode: 'password_registration' });
      }
      unexpected.push(pathname);
      return fulfillJson(route, { detail: 'Unexpected synthetic auth request' }, 400);
    });
    await page.goto(`${base}/?auth_action=${action}&token=synthetic-readiness`);
    await expect.poll(() => requested).toBe(true);
    await expect(page.locator('#auth-token-form')).toBeHidden({ timeout: 1000 });
    await expect(page.locator('#magic-token-input')).toBeDisabled();
    await expect(page.locator('#verify-magic-link-button')).toBeDisabled();
    await page.screenshot({ path: testInfo.outputPath(`${action}-pending.png`), fullPage: true });
    await page.evaluate(() => document.querySelector('#auth-token-form')
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(unexpected).toEqual([]);
    release();
    await waitForPasswordCreationForm(page, 'ready@example.test');
    await page.locator('#magic-token-input').fill('Readiness-Aa1!');
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 2 из 2');
    expect(unexpected).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`${action}-step2-1440.png`), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator('#verify-magic-link-button')).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await page.screenshot({ path: testInfo.outputPath(`${action}-step2-390.png`), fullPage: true });
  });

  test(`AC18 auth readiness: ${action} validation refusal stays fail-closed`, async ({ page }) => {
    await baseRoutes(page);
    await page.route('**' + endpoint, (route) => fulfillJson(route, { detail: 'Срок ссылки истёк.' }, 400));
    await page.goto(`${base}/?auth_action=${action}&token=synthetic-expired`);
    await expect(page.locator('#auth-email-sent')).toBeVisible();
    await expect(page.locator('#auth-token-form')).toBeHidden();
    await expect(page.locator('#auth-email-sent h2')).toContainText(
      action === 'password_reset' ? 'Срок ссылки истёк' : 'Не удалось проверить ссылку');
  });
}

test('AC18 failure capture uses supplied admin page and never exports credential values', async ({ page }, testInfo) => {
  await baseRoutes(page);
  await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, { auth_mode: 'password' }));
  await page.goto(`${base}/?diagnostic=synthetic`);
  await page.locator('#email-input').fill('admin@example.test');
  await page.locator('#request-magic-link-button').click();
  await expect(page.locator('#magic-token-input')).toBeVisible();
  await page.locator('#magic-token-input').fill('NeverExport-Aa1!');
  await page.evaluate(() => window.history.replaceState({}, '', '/?diagnostic=synthetic&token=MustNotExport'));
  const directory = testInfo.outputPath('safe-failure');
  await fs.mkdir(directory, { recursive: true });
  const context = await captureFailurePage(page, directory, { step: 'admin_login', actor: 'administrator' });
  expect(context.actor).toBe('administrator');
  expect(context.pathname).toBe('/');
  expect(context.query_keys).toEqual(['diagnostic', 'token']);
  expect(context.title).toBe('С возвращением');
  expect(context.credential_values_exported).toBe(false);
  expect(context.credential_input).not.toHaveProperty('value');
  expect(context.credential_input.has_value).toBe(true);
  expect(JSON.stringify(context)).not.toContain('NeverExport-Aa1!');
  expect(JSON.stringify(context)).not.toContain('MustNotExport');
  expect(JSON.parse(await fs.readFile(path.join(directory, 'failure-context.json'), 'utf8'))).toEqual(context);
  expect((await fs.stat(path.join(directory, 'failure.png'))).size).toBeGreaterThan(1000);
});

test('AC18 auth readiness: network validation failure can retry before password entry', async ({ page }) => {
  await baseRoutes(page);
  let calls = 0;
  await page.route('**/users/auth/email/confirm', (route) => {
    calls += 1;
    return calls === 1 ? route.abort('failed') : fulfillJson(route, {
      email: 'retry@example.test', auth_mode: 'password_registration',
    });
  });
  await page.goto(`${base}/?auth_action=email_verification&token=synthetic-retry`);
  await expect(page.locator('#auth-email-sent h2')).toHaveText('Нет связи с сервером');
  await expect(page.locator('#auth-token-form')).toBeHidden();
  await page.locator('#auth-change-email-button').click();
  await waitForPasswordCreationForm(page, 'retry@example.test');
  await page.locator('#magic-token-input').fill('RetryReady-Aa1!');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 2 из 2');
  expect(calls).toBe(2);
});

for (const caseId of ['CASE.SPEC.01', 'CASE.SPEC.02']) {
  test(`AS projection ${caseId}: concrete public materials, no author passport, four widths`, async ({ page }) => {
    test.info().annotations.push({ type: 'synthetic_component', description:
      'Exact author AS/public material fixture through real materializer and UI; NOT real-provider PATH, DB persistence or pilot admission' });
    const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
    const fixture = JSON.parse(execFileSync(python, ['-m', 'tests.m5_participant_projection_inputs', caseId], {
      cwd: root, encoding: 'utf8', timeout: 30000,
    }));
    expect(fixture.scope).toBe('SYNTHETIC_COMPONENT_PRESENTATION_NOT_PILOT_ADMISSION');
    const payload = fixture.participant_payload;
    const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
    const writes = [];
    let reads = 0;
    let remainingSeconds = 7200;
    let extraTurns = [];
    await page.route('**/users/**', (route) => {
      if (route.request().method() !== 'GET') writes.push(route.request().method() + ' ' + new URL(route.request().url()).pathname);
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/users/version') return fulfillJson(route, { version: appRelease });
      if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
      if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
      if (pathname === '/users/8/journey-state') return fulfillJson(route, {
        next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
        assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'projection-cycle',
          cycle_session_id: 'projection-session', assessment_situation_id: 'projection-as' },
      });
      if (pathname === '/users/assessment/m7/cycles/projection-cycle/return-state') {
        return fulfillJson(route, { detail: 'M7_RETURN_POLICY_NOT_SNAPSHOTTED' }, 409);
      }
      if (pathname === '/users/assessment/cycles/projection-cycle/runtime') { reads += 1; return fulfillJson(route, {
        cycle_id: 'projection-cycle', status: { collection_status: 'active', remaining_seconds: remainingSeconds },
        return_policy_enabled: false,
        route: { positions: [{ position_no: 1, state: 'in_progress', current_assessment_situation_id: 'projection-as' }], progress: { total_positions: 8 } },
        current_situation: { assessment_situation_id: 'projection-as', status: 'active', participant_payload: payload,
          response_format: fixture.response_format },
        trace: { turns: extraTurns, events: [] },
      }); }
      return fulfillJson(route, {}, 404);
    });
    await page.goto(`${base}/?screen=interview`);
    const situation = page.locator('.interview-message--situation');
    await expect(situation).toHaveCount(1);
    await expect(page.locator('.interview-response-format')).toHaveText(
      caseId === 'CASE.SPEC.02' ? 'Письменное задание' : 'Диалог');
    await expect(situation).toContainText(payload.introduction);
    for (const item of payload.initial_materials) await expect(situation).toContainText(item.text);
    await expect(situation).not.toContainText('определяются в AS');
    await expect(situation).not.toContainText("[{'Функция'");
    // renderProductRuntime schedules bottom alignment at RAF + 80/220ms.
    // Let those existing initial effects finish before trial scroll measurement;
    // do not alter CSS, clipping assertions, enabled state or scroll behavior.
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    // Keep polling real UI code: an unchanged AS must retain its DOM and user
    // scroll, while timer updates still apply. Do not pause/intercept poll timers.
    const originalNode = await situation.elementHandle();
    const beforeReads = reads;
    await expect(page.locator('#interview-finish-button')).toBeHidden();
    await expect(page.locator('#interview-pause-button')).toBeHidden();
    await page.locator('#interview-submit-button').click({ trial: true });
    const beforeY = await page.evaluate(() => scrollY);
    remainingSeconds = 7100;
    await expect.poll(() => reads).toBeGreaterThanOrEqual(beforeReads + 2);
    expect(await originalNode.evaluate((node) => node.isConnected)).toBe(true);
    expect(await page.evaluate(() => scrollY)).toBeCloseTo(beforeY, 0);
    await expect(page.locator('#interview-timer-badge')).toContainText('118:20');
    const dir = path.join(process.env.AS_PRESENTATION_EVIDENCE_DIRECTORY || path.join(root, '.test-stand/as-presentation'), caseId);
    await fs.mkdir(dir, { recursive: true });
    await capturePathViewports(page, dir, 'first-as', [
      { name: 'home', locator: page.locator('#interview-profile-button') },
      { name: 'answer-input', locator: page.locator('#interview-textarea') },
      { name: 'answer-submit', locator: page.locator('#interview-submit-button') },
    ]);
    // Follow the participant path into the disclosure and keep the material
    // reachable while the runtime polls.
    const materials = situation.locator('details');
    await materials.getByText('Доступные сведения', { exact: true }).click();
    await expect(materials).toHaveJSProperty('open', true);
    const lastMaterial = materials.locator('li').last();
    await lastMaterial.scrollIntoViewIfNeeded();
    await expect.poll(async () => (await viewportGeometry(lastMaterial)).visible_ratio).toBeGreaterThan(0);
    const beforeMaterialReads = reads;
    await expect.poll(() => reads).toBeGreaterThanOrEqual(beforeMaterialReads + 2);
    await expect(materials).toHaveJSProperty('open', true);
    const lastMaterialGeometry = await viewportGeometry(lastMaterial);
    assertViewportGeometry(lastMaterialGeometry, 'last-material-after-poll');
    // fullPage capture resizes the layout viewport and can reset a dvh-sized
    // inner scroller. This evidence must show the actual reading viewport.
    await page.screenshot({ path: path.join(dir, 'last-material.png'), fullPage: false });
    const afterCapture = await viewportGeometry(lastMaterial);
    assertViewportGeometry(afterCapture, 'last-material-after-viewport-capture');
    await fs.writeFile(path.join(dir, 'last-material-geometry.json'), JSON.stringify({
      ...afterCapture, screenshot_mode: 'viewport', material_text: await lastMaterial.innerText(),
    }, null, 2) + '\n');
    await page.reload();
    await expect(situation).toHaveCount(1);
    await expect(situation).toContainText(payload.introduction);
    await expect(page.locator('#interview-textarea')).toHaveValue('');
    // A genuinely changed trace still renders; caching must not hide updates.
    extraTurns = [{ sequence_no: 1, turn_id: 'synthetic-public-update', speaker_type: 'character',
      speaker_name: 'Контролируемый персонаж', content_text: 'Новый публичный материал из synthetic fixture' }];
    await expect(situation.locator('h3')).toHaveText(payload.title);
    await expect(page.locator('[data-speaker-label="Контролируемый персонаж"]')).toContainText('Новый публичный материал');
    expect(writes).toEqual([]);
    await fs.writeFile(path.join(dir, 'readback.json'), JSON.stringify({ scope: fixture.scope,
      case_id: caseId, participant_payload: payload, reload_same_payload: true,
      mutation_requests: writes, assessment_answers: 0 }, null, 2) + '\n');
  });
}

async function adm28Preview(page) {
  const organization = { ...withConnectedAssessment('ADM28 synthetic'),
    admins: [{ user_id: 18, email: adminUser.email, full_name: 'Admin' }] };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  const form = card.locator('form[data-action="preview-early-data"]');
  const proposedName = 'Обновлённое название R03';
  let revisionId = 201;
  await page.route('**/users/admin/organizations/3/questionnaire/preview', (route) => {
    const payload = route.request().postDataJSON();
    return fulfillJson(route, { id: revisionId++, assignment_ref: payload.assignment_ref,
      status: 'ready_for_confirmation', channel: 'product_form', answers_json: payload.answers,
      validation_json: {}, participant_preview: { purpose: payload.answers.C02a.participant_text },
      recipient_options: ['participant', 'organization_admin'] });
  });
  await expect(form.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(form.locator('[name="assignment_ref"]')).toHaveValue('ADM28 synthetic');
  await expect(form.locator('[name="source_author"]')).toHaveCount(0);
  await form.locator('[name="organization_name"]').fill(proposedName);
  await form.locator('[name="purpose"]').fill('Synthetic purpose');
  await form.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(card.locator('.admin-questionnaire-preview')).toBeVisible();
  return { card, form, organization, preview: card.locator('.admin-questionnaire-preview'),
    saved: { id: 201, assignment_ref: 'ADM28 synthetic', status: 'confirmed', channel: 'product_form',
      effective_confirmed: { id: 201, assignment_ref: 'ADM28 synthetic', confirmed_at: null },
      organization_name_current: proposedName,
      answers_json: { C01: { name: proposedName }, C02a: { participant_text: 'Synthetic purpose' } },
      recipient_mapping: ['participant'], recipient_user_ids: [] } };
}

test('ADM28 confirmation finishes before supplementary GET and offers a retry on GET failure', async ({ page }) => {
  const { card, preview, saved } = await adm28Preview(page);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire', async (route) => {
    await delayed;
    return fulfillJson(route, { detail: 'synthetic unavailable' }, 503);
  });
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', (route) => fulfillJson(route, saved));
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(preview).toHaveCount(0);
  await expect(card.locator('[data-organization-confirmed]')).toBeVisible();
  await expect(card).not.toContainText('Подтверждаем…');
  release();
  await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Не удалось обновить готовность');
  await expect(card.getByRole('button', { name: 'Проверить результат' })).toBeVisible();
});

test('ADM28 lost POST response checks exact revision and recipients without republishing', async ({ page }) => {
  const { card, preview, saved } = await adm28Preview(page);
  let posts = 0;
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', (route) => {
    posts += 1;
    return route.abort('connectionreset');
  });
  await page.route('**/users/admin/organizations/3/questionnaire/201', (route) => fulfillJson(route, saved));
  await page.route('**/users/admin/organizations/3/questionnaire', (route) => fulfillJson(route, {
    items: [{ ...saved, readiness: { status: 'incomplete', early: { status: 'ready' } } }],
  }));
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Итог подтверждения неизвестен');
  await expect(preview.locator('[data-action="confirm-questionnaire"]')).toBeHidden();
  await card.getByRole('button', { name: 'Проверить результат' }).click();
  await expect(preview).toHaveCount(0);
  await expect(card.locator('[data-organization-confirmed]')).toBeVisible();
  expect(posts).toBe(1);
});

test('REMAIN-02 removes recipient controls and keeps confirmation available after navigation', async ({ page }) => {
  const { card, form, preview } = await adm28Preview(page);
  await expect(preview.locator('[name="questionnaire_recipient_user"]')).toHaveCount(0);
  await expect(preview.locator('[name="questionnaire_recipient"]')).toHaveCount(0);
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).hover();
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeEnabled();
  await card.getByRole('button', { name: 'Участники оценки', exact: true }).click();
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeEnabled();
  let confirmationPosts = 0, revisionReads = 0;
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', (route) => {
    confirmationPosts += 1;
    return fulfillJson(route, { detail: 'QUESTIONNAIRE_REVISION_CONFLICT' }, 409);
  });
  await page.route('**/users/admin/organizations/3/questionnaire/201', (route) => {
    revisionReads += 1;
    return fulfillJson(route, { id: 201, assignment_ref: 'ADM28 synthetic', status: 'ready_for_confirmation' });
  });
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  const recovery = card.locator('.admin-data-confirmation-recovery');
  await expect(recovery).toBeVisible();
  await expect(recovery).toContainText('уже подтверждена более новая');
  await expect(form.getByRole('button', { name: 'Подтвердить сведения', exact: true })).toHaveCount(0);
  let listRequested, releaseList;
  const listStarted = new Promise((resolve) => { listRequested = resolve; });
  const listResponse = new Promise((resolve) => { releaseList = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire', async (route) => {
    listRequested();
    await listResponse;
    return fulfillJson(route, { items: [] });
  });
  try {
    await recovery.getByRole('button', { name: 'Проверить результат' }).click();
    await listStarted;
    await form.locator('[name="purpose"]').fill('Цель во время сверки');
    await form.locator('[name="results_usage"]').fill('Использование во время сверки');
  } finally {
    releaseList();
  }
  await expect(form.locator('[data-operation-status]')).toContainText('Редакция не сохранена');
  await expect(form.getByRole('button', { name: 'Подтвердить сведения', exact: true })).toBeEnabled();
  await expect(form.locator('[name="purpose"]')).toHaveValue('Цель во время сверки');
  await expect(form.locator('[name="results_usage"]')).toHaveValue('Использование во время сверки');
  await expect(card.locator('[data-preview-value="purpose"]')).toHaveText('Цель во время сверки');
  await expect(card.locator('[data-preview-value="results_usage"]')).toHaveText('Использование во время сверки');
  expect(revisionReads).toBe(1);
  expect(confirmationPosts).toBe(1);
});

test('ADM28 keeps newer input while confirmation is in flight', async ({ page }) => {
  const { card, preview, form, saved } = await adm28Preview(page);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', async (route) => {
    await delayed;
    return fulfillJson(route, saved);
  });
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await form.locator('[name="purpose"]').fill('New synthetic purpose');
  await expect(form.locator('[data-early-data-submit]')).toBeDisabled();
  release();
  await expect(preview).toHaveCount(0);
  await expect(form.locator('[name="purpose"]')).toHaveValue('New synthetic purpose');
  await expect(card.locator('[data-preview-value="purpose"]')).toHaveText('New synthetic purpose');
  await expect(form.locator('[data-early-data-submit]')).toBeEnabled();
});

test('ADMIN-02 name conflict retains the organization draft', async ({ page }) => {
  const { card, preview, form } = await adm28Preview(page);
  const enteredName = await form.locator('[name="organization_name"]').inputValue();
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', (route) =>
    fulfillJson(route, { detail: 'QUESTIONNAIRE_ORGANIZATION_NAME_CONFLICT' }, 409));
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(card.locator('.admin-data-confirmation-recovery')).toContainText('Название организации изменилось');
  await expect(form.locator('[name="organization_name"]')).toHaveValue(enteredName);
});

test('ADM28 late confirmation cannot replace another selected assessment', async ({ page }) => {
  const { card, preview, form, saved, organization } = await adm28Preview(page);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', async (route) => {
    await delayed; return fulfillJson(route, saved);
  });
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  organization.assessment_program = syntheticAdminProgram('Another assessment', 8);
  await reopenAdminOrganizations(page);
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  await form.locator('[name="purpose"]').fill('Another purpose');
  release();
  await expect(form.locator('[name="assignment_ref"]')).toHaveValue('Another assessment');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Another purpose');
  await expect(card.locator('[data-organization-confirmed]')).toBeHidden();
});

test('ADM28 late confirmation after account change cannot populate the new account', async ({ page }) => {
  const { preview, saved } = await adm28Preview(page);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', async (route) => {
    await delayed; return fulfillJson(route, saved);
  });
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await page.locator('#admin-organizations-account-name').click();
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  const nextUser = { ...adminUser, id: 28, email: 'next@example.test', full_name: 'Account B' };
  await page.route('**/users/admin/organizations', (route) => fulfillJson(route, {
    is_superadmin: false, items: [adminOrganization],
  }));
  await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, { email: nextUser.email, auth_mode: 'password' }));
  await page.route('**/users/auth/email/password-login', (route) => fulfillJson(route, {
    exists: true, user: nextUser, is_admin: true, admin_dashboard: { is_superadmin: false },
  }));
  await page.locator('#email-input').fill(nextUser.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('synthetic-existing-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#admin-organizations-account-name')).toHaveText('Account B');
  await expect(page.locator('#admin-organizations-logout-button')).toBeEnabled();
  await expect(page.locator('#admin-organizations-logout-button')).toHaveText('Выйти');
  release();
  await page.locator('[data-organization-id="3"]').getByRole('button', { name: 'Данные организации', exact: true }).click();
  await expect(page.locator('.admin-questionnaire-preview')).toHaveCount(0);
  await expect(page.locator('[data-action="preview-early-data"] [name="assignment_ref"]')).not.toHaveValue('ADM28 synthetic');
  await expect(page.locator('[data-action="preview-early-data"] [name="assignment_ref"]')).toHaveValue('competencies_4k');
});

test('ADM28 session restoration hides credentials and loads each admin resource once', async ({ page }) => {
  let release;
  let organizations = 0;
  let questionnaires = 0;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') {
      await delayed;
      return fulfillJson(route, { authenticated: true, user: adminUser, is_admin: true, admin_dashboard: { is_superadmin: false } });
    }
    if (pathname === '/users/admin/organizations') { organizations += 1; return fulfillJson(route, { items: [adminOrganization] }); }
    if (pathname === '/users/admin/organizations/3/questionnaire') { questionnaires += 1; return fulfillJson(route, { items: [] }); }
    return fulfillJson(route, {});
  });
  await page.goto(base);
  await expect(page.locator('#session-restore-panel')).toBeVisible();
  await expect(page.locator('#email-input')).toBeHidden();
  release();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  await expect(page.locator('.admin-organization-member')).toHaveCount(1);
  expect(organizations).toBe(1);
  await expect.poll(() => questionnaires).toBe(1);
});

test('ADM28 temporary restore failure offers retry and does not show login credentials', async ({ page }) => {
  await page.route('**/users/session/restore', (route) => fulfillJson(route, { detail: 'unavailable' }, 503));
  await page.route('**/users/version', (route) => fulfillJson(route, {}, 503));
  await page.goto(base);
  await expect(page.locator('#session-restore-title')).toHaveText('Не удалось восстановить сессию');
  await expect(page.locator('#session-restore-retry')).toBeVisible();
  await expect(page.locator('#email-input')).toBeHidden();
  await expect(page.locator('.auth-release-badge')).toHaveText(`Релиз ${appRelease}`);
  await expect(page.locator('.app-footer-release')).toBeHidden();
});

test('ADM28 initial HTML has a complete frontend version before JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  try {
    const page = await context.newPage();
    await page.goto(base);
    await expect(page.locator('#session-restore-panel')).toBeVisible();
    await expect(page.locator('.auth-release-badge')).toHaveText(`Релиз ${appRelease}`);
    await expect(page.locator('.app-footer-release')).toBeHidden();
    await expect(page.locator('#email-input')).toBeHidden();
  } finally { await context.close(); }
});

test('ADM-UI-02 retries a lost preview with the same idempotency key', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  const form = card.locator('form[data-action="preview-early-data"]');
  await form.locator('[name="purpose"]').fill('Цель для проверки повтора');
  const requests = [];
  await page.route('**/users/admin/organizations/3/questionnaire/preview', (route) => {
    const payload = route.request().postDataJSON();
    requests.push(payload);
    if (requests.length === 1) return route.abort('connectionreset');
    return fulfillJson(route, {
      id: 322, assignment_ref: payload.assignment_ref, channel: payload.channel, status: 'invalid',
      answers_json: payload.answers, validation_json: { missing: ['C01'] },
    });
  });
  const confirm = form.getByRole('button', { name: 'Подтвердить сведения', exact: true });
  await confirm.click();
  await expect(form.locator('.admin-questionnaire-confirmation [data-operation-status]')).toContainText('Не удалось получить ответ');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Цель для проверки повтора');
  await confirm.click();
  await expect(form.locator('.admin-questionnaire-preview')).toContainText('Проверьте: сведения об организации');
  expect(requests).toHaveLength(2);
  expect(requests[0].idempotency_key).toBeTruthy();
  expect(requests[1]).toEqual(requests[0]);
});

test('ADM-UI-02 asks before replacing a name changed on the server', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), adminOrganization, { body: { items: [] } });
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  const form = card.locator('form[data-action="preview-early-data"]');
  await form.locator('[name="purpose"]').fill('Новая цель');
  await page.route('**/users/admin/organizations/3/questionnaire/preview', (route) => {
    const payload = route.request().postDataJSON();
    return fulfillJson(route, {
      id: 323, assignment_ref: payload.assignment_ref, channel: payload.channel, status: 'ready_for_confirmation',
      answers_json: payload.answers, expected_organization_name: 'Имя изменено другим администратором',
    });
  });
  const writes = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/confirm')) writes.push(request.url());
  });
  await form.locator('[data-early-data-submit]').press('Enter');
  await expect(form.locator('[data-organization-rename]')).toBeVisible();
  await expect(form.locator('[data-organization-rename]')).toContainText('Имя изменено другим администратором');
  await expect(form.locator('[data-action="confirm-questionnaire"]')).toBeFocused();
  await expect(form.locator('[data-early-data-submit]')).toBeHidden();
  expect(writes).toEqual([]);
});

test('ADM28 invalid JSON leaves a finite unknown outcome and restores confirm controls', async ({ page }) => {
  const { card, preview } = await adm28Preview(page);
  await page.route('**/users/admin/organizations/3/questionnaire/201/confirm', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{broken' }));
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(card).toContainText('Итог подтверждения неизвестен');
  await expect(preview).not.toContainText('Подтверждаем…');
  await expect(card.getByRole('button', { name: 'Проверить результат' })).toBeEnabled();
});

test('P4K-SUP-UX-01 superadmin restores the platform organizations cabinet', async ({ page }, info) => {
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const journeyRequests = [];
  page.on('request', (request) => { if (request.url().includes('/journey-state')) journeyRequests.push(request.url()); });
  await page.route('**/users/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (path === '/users/18/session-bootstrap') return fulfillJson(route, {
      user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (path === '/users/admin/dashboard') return fulfillJson(route, dashboard);
    if (path === '/users/admin/support/preparation') return fulfillJson(route, { items: [], next_before: null });
    if (path === '/users/admin/organizations') return fulfillJson(route, { is_superadmin: true, items: [], assessment_programs: [] });
    return fulfillJson(route, {});
  });
  await page.goto(base);
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  await expect(page.locator('#admin-panel')).toBeHidden();
  await expect(page.locator('.platform-navigation [aria-current="page"]')).toHaveText('Организации');
  await expect(page.locator('#admin-start-assessment-button')).toHaveCount(0);
  const reference = await page.context().newPage();
  const referencePath = path.join(root, '.test-stand/reference/reference/v1.6/index.html');
  const hasReference = await fs.access(referencePath).then(() => true, () => false);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => document.activeElement?.blur());
    await page.screenshot({ path: info.outputPath(`product-${width}.png`), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    if (hasReference) {
      await reference.setViewportSize({ width, height: 900 });
      await reference.goto('file://' + referencePath + '?screen=organizations&view=screen');
      await expect(reference.locator('#content')).toContainText('Организации');
      await reference.screenshot({ path: info.outputPath(`reference-${width}.png`), fullPage: true });
      expect(await reference.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    }
    await page.locator('[data-platform-section="problems"]').focus();
    await expect(page.locator('[data-platform-section="problems"]')).toBeFocused();
  }
  if (hasReference) {
    await reference.setViewportSize({ width: 390, height: 900 });
    await reference.goto('file://' + referencePath + '?screen=organizations&view=screen');
    await reference.locator('#account-toggle').click();
    await reference.locator('[data-act="logout"]').click();
    await reference.screenshot({ path: info.outputPath('reference-signed-out-390.png'), fullPage: true });
  }
  await reference.close();
  await page.reload();
  await expect(page.locator('.platform-navigation [aria-current="page"]')).toHaveText('Организации');
  await page.goto(base + '/?screen=admin');
  await expect(page.locator('.platform-navigation [aria-current="page"]')).toHaveText('Организации');
  await expect(page).toHaveURL(/screen=admin-organizations/);
  await page.goto(base + '/?screen=dashboard');
  await expect(page.locator('.platform-navigation [aria-current="page"]')).toHaveText('Организации');
  await expect(page).toHaveURL(/screen=admin-organizations/);
  expect(journeyRequests).toHaveLength(0);
  await page.getByRole('link', { name: 'Проблемы' }).click();
  await expect(page.locator('#platform-problems-title')).toHaveText('Проблемы');
  await expect(page.locator('#platform-problems')).toContainText('Неразрешённых сбоев');
  await page.goBack();
  await expect(page.locator('.platform-navigation [aria-current="page"]')).toHaveText('Организации');
  await page.locator('#admin-organizations-account-name').click();
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  await expect(page.locator('.platform-navigation')).toBeHidden();
  await page.setViewportSize({ width: 390, height: 900 });
  await page.screenshot({ path: info.outputPath('product-signed-out-390.png'), fullPage: true });
});

async function reloadSuperadminOrganizations(page) {
  await page.reload();
  await expect(page.locator('#admin-panel:not(.hidden), #admin-organizations-panel:not(.hidden)')).toHaveCount(1);
  if (await page.locator('#admin-open-organizations-button').isVisible()) {
    await page.locator('#admin-open-organizations-button').click();
  }
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
}

for (const firstReply of ['confirmed', 'lost', 'service-error']) {
  test(`PATH-START AC02 repeats organization creation after ${firstReply} response without a duplicate`, async ({ page }, testInfo) => {
    testInfo.annotations.push({ type: 'synthetic_http', description: 'Stateful HTTP fixture; real entry/dist; no DB/provider.' });
    const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
    const items = [];
    const posts = [];
    let releaseCreate;
    const pendingCreate = new Promise((resolve) => { releaseCreate = resolve; });
    const listing = () => ({ is_superadmin: true, items, assessment_programs: [] });
    await page.route('**/users/**', async (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (['/users/session/restore', '/users/18/session-bootstrap'].includes(pathname)) return fulfillJson(route, {
        authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
      });
      if (pathname === '/users/version') return fulfillJson(route, { version: 'ac02-test' });
      if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
      if (pathname === '/users/admin/organizations') {
        if (route.request().method() === 'GET') return fulfillJson(route, listing());
        const payload = route.request().postDataJSON();
        posts.push(payload);
        if (posts.length === 1) {
          await pendingCreate;
          if (firstReply === 'service-error') return fulfillJson(route, { detail: 'Synthetic create unavailable' }, 503);
        }
        if (items.some((item) => item.code === payload.code)) {
          return fulfillJson(route, { detail: 'Organization with this code already exists' }, 409);
        }
        items.push({ ...payload, id: 3, is_active: true, domains: [], admins: [],
          members_count: 0, reports_count: 0, members: [], assessment_program: null });
        if (posts.length === 1 && firstReply === 'lost') return route.abort('connectionreset');
        return fulfillJson(route, listing());
      }
      if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
      return fulfillJson(route, {}, 404);
    });
    await page.goto(base);
    await page.locator('#admin-open-organizations-button').click();
    const name = page.locator('#admin-organization-name-input');
    const code = page.locator('#admin-organization-code-input');
    const button = page.locator('#admin-organization-create-button');
    const status = page.locator('#admin-organizations-status');
    await name.fill('Owned synthetic AC02');
    await code.fill('owned-ac02');
    await button.click();
    try {
      await expect.poll(() => posts.length).toBe(1);
      await expect(button).toBeDisabled();
      // A real keyboard repeat while the command is pending must not issue another POST.
      await name.press('Enter');
      expect(posts).toHaveLength(1);
    } finally { releaseCreate(); }
    await expect(status).toHaveAttribute('data-tone', firstReply === 'confirmed' ? 'success' : 'error');
    await expect(button).toBeEnabled();
    await reloadSuperadminOrganizations(page);
    await expect(page.locator('[data-organization-id="3"]')).toHaveCount(firstReply === 'service-error' ? 0 : 1);
    await name.fill('Owned synthetic AC02');
    await code.fill('owned-ac02');
    await button.click();
    await expect.poll(() => posts.length).toBe(2);
    await expect(status).toHaveAttribute('data-tone', firstReply === 'service-error' ? 'success' : 'error');
    if (firstReply !== 'service-error') await expect(status).toContainText('Organization with this code already exists');
    expect(items).toHaveLength(1);
    expect(posts[1]).toEqual(posts[0]);
    await expect(button).toBeEnabled();
    await reloadSuperadminOrganizations(page);
    await expect(page.locator('[data-organization-id="3"]')).toHaveCount(1);
    await expect(page.locator('[data-organization-id="3"]')).toContainText('Owned synthetic AC02');
    await page.screenshot({ path: testInfo.outputPath('ac02-result.png') });
  });
}

for (const lostCommandResponse of [false, true]) {
  for (const readbackFailure of ['deadline', 'http503', 'network', 'invalid-json', 'null', 'foreign-program']) {
    test(`PATH-START AC05 ${readbackFailure} GET after ${lostCommandResponse ? 'lost' : 'confirmed'} PUT is finite, unknown and safely repeatable`, async ({ page }, testInfo) => {
      testInfo.annotations.push({ type: 'synthetic_http', description: 'Real entry/dist and unmodified 15s deadline; HTTP faults only, no DB/provider.' });
      const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
      const connection = { organization_id: 3, program_definition_id: 11,
        program_name: 'Owned AC05 pilot', program_version: 'synthetic-v1', assignment_ref: 'ac05',
        roles: [], role_capabilities: [] };
      const organization = { id: 3, code: 'owned-ac05', name: 'Owned AC05 organization',
        is_active: true, domains: [], admins: [], members_count: 0, reports_count: 0,
        members: [], assessment_program: null };
      const operationIds = [];
      let getCount = 0;
      let releaseReadback;
      const stalledReadback = new Promise((resolve) => { releaseReadback = resolve; });
      await page.route('**/users/**', async (route) => {
        const pathname = new URL(route.request().url()).pathname;
        if (['/users/session/restore', '/users/18/session-bootstrap'].includes(pathname)) return fulfillJson(route, {
          authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
        });
        if (pathname === '/users/version') return fulfillJson(route, { version: 'ac05-test' });
        if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
        if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') {
          return fulfillJson(route, { is_superadmin: true, items: [organization],
            assessment_programs: [{ id: 11, name: connection.program_name, version: connection.program_version }] });
        }
        if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
        if (pathname === '/users/admin/organizations/3/assessment-program') {
          if (route.request().method() === 'PUT') {
            operationIds.push(route.request().postDataJSON().operation_id);
            organization.assessment_program = connection; // Fixture models a committed command, even if its response is lost.
            return lostCommandResponse ? route.abort('connectionreset') : fulfillJson(route, { connection });
          }
          getCount += 1;
          if (getCount > 1) return fulfillJson(route, { connection });
          if (readbackFailure === 'deadline') { await stalledReadback; return fulfillJson(route, { connection }); }
          if (readbackFailure === 'http503') return fulfillJson(route, { detail: 'Synthetic readback unavailable' }, 503);
          if (readbackFailure === 'network') return route.abort('connectionreset');
          if (readbackFailure === 'invalid-json') return route.fulfill({ status: 200, contentType: 'application/json', body: '{' });
          if (readbackFailure === 'null') return fulfillJson(route, { connection: null });
          return fulfillJson(route, { connection: { ...connection, program_definition_id: 999, program_name: 'Foreign program' } });
        }
        return fulfillJson(route, {}, 404);
      });
      await page.goto(base);
      await page.locator('#admin-open-organizations-button').click();
      const form = page.locator('[data-action="connect-assessment-program"]');
      const button = form.getByRole('button', { name: 'Подключить', exact: true });
      await form.locator('[name="program_definition_id"]').selectOption('11');
      await button.click();
      const status = form.locator('[data-operation-status]');
      try {
        await expect(status).toHaveAttribute('data-tone', 'error', { timeout: 22000 });
        await expect(status).not.toContainText('Выполняем действие');
        await expect(status).toContainText('Результат подключения не подтверждён');
        await expect(button).toBeEnabled();
        await expect(page.locator('[data-organization-id="3"]')).not.toContainText(/не подключена/i);
        await expect(form.locator('[data-program-connection-state]')).toContainText('пока не подтверждён');
        await expect(form).not.toContainText('Foreign program');
        await page.screenshot({ path: testInfo.outputPath('ac05-unknown.png') });
      } finally { releaseReadback(); }
      if (readbackFailure === 'http503' && !lostCommandResponse) {
        await page.locator('#admin-open-organizations-button').click();
        await expect(form.locator('[data-program-connection-state]')).toContainText('пока не подтверждён');
        for (const width of [1440, 320, 390, 768]) {
          await page.setViewportSize({ width, height: 1000 });
          await button.scrollIntoViewIfNeeded();
          await expect(button).toBeVisible();
          const box = await form.boundingBox();
          expect(box.x).toBeGreaterThanOrEqual(0);
          expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
          await page.screenshot({ path: testInfo.outputPath(`ac05-unknown-${width}.png`) });
        }
      }
      await button.click();
      await expect(form.locator('[data-operation-status]')).toHaveAttribute('data-tone', 'success');
      await expect(form).toContainText('Подключено: Owned AC05 pilot · synthetic-v1');
      expect(operationIds).toHaveLength(2);
      expect(operationIds[1]).toBe(operationIds[0]);
      expect(new Set(operationIds).size).toBe(1);
      expect(getCount).toBe(2);
      await reloadSuperadminOrganizations(page);
      await expect(form).toContainText('Подключено: Owned AC05 pilot · synthetic-v1');
    });
  }
}

test('PROGRAM01 R10 finishes exact program connection while questionnaire refresh is pending', async ({ page }) => {
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const connection = {
    organization_id: 3, program_definition_id: 11, program_name: 'Пилот 4К · 9 кейсов',
    program_version: '1.1', assignment_ref: 'pilot-4k-9', roles: [], role_capabilities: [],
  };
  const organization = {
    id: 3, code: 'r10', name: 'R10 Organization', is_active: true, domains: [], admins: [],
    members_count: 0, reports_count: 0, members: [], assessment_program: null,
  };
  let releaseQuestionnaire;
  const questionnairePending = new Promise((resolve) => { releaseQuestionnaire = resolve; });
  let questionnaireRequests = 0;
  await page.route('**/users/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r10-test' });
    if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
    if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') {
      return fulfillJson(route, {
        is_superadmin: true, items: [organization],
        assessment_programs: [{ id: 11, name: connection.program_name, version: connection.program_version }],
      });
    }
    if (pathname === '/users/admin/organizations/3/questionnaire') {
      questionnaireRequests += 1;
      await questionnairePending;
      return fulfillJson(route, { detail: 'synthetic questionnaire unavailable' }, 503);
    }
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'PUT') {
      return fulfillJson(route, { connection });
    }
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'GET') {
      return fulfillJson(route, { connection });
    }
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#admin-open-organizations-button').click();
  const form = page.locator('[data-action="connect-assessment-program"]');
  await form.locator('[name="program_definition_id"]').selectOption('11');
  await form.getByRole('button', { name: 'Подключить' }).click();
  await expect(form).toContainText('Подключено: Пилот 4К · 9 кейсов · 1.1');
  await expect(form.locator('[data-operation-status]')).toContainText('Опубликованная версия программы подключена');
  expect(questionnaireRequests).toBeGreaterThanOrEqual(1);
  releaseQuestionnaire();
  await expect(form.locator('[data-operation-status]')).toContainText('Опубликованная версия программы подключена');
});

test('PROGRAM01 R10 shows a terminal error when exact readback is null', async ({ page }) => {
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const organization = {
    id: 3, code: 'r10-null', name: 'R10 Null Organization', is_active: true, domains: [], admins: [],
    members_count: 0, reports_count: 0, members: [], assessment_program: null,
  };
  const operationIds = [];
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r10-test' });
    if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
    if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') return fulfillJson(route, {
      is_superadmin: true, items: [organization],
      assessment_programs: [{ id: 11, name: 'Пилот 4К · 9 кейсов', version: '1.1' }],
    });
    if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'PUT') {
      operationIds.push(route.request().postDataJSON().operation_id);
      return fulfillJson(route, { connection: { organization_id: 3, program_definition_id: 11 } });
    }
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'GET') {
      return fulfillJson(route, { connection: null });
    }
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#admin-open-organizations-button').click();
  const form = page.locator('[data-action="connect-assessment-program"]');
  await form.locator('[name="program_definition_id"]').selectOption('11');
  await form.getByRole('button', { name: 'Подключить' }).click();
  await expect(form.locator('[data-operation-status]')).toContainText(
    'Сервер не подтвердил точную версию подключённой программы',
  );
  await expect(form.locator('[data-operation-status]')).not.toContainText('Выполняем действие');
  await expect(form.getByRole('button', { name: 'Подключить' })).toBeEnabled();
  await form.getByRole('button', { name: 'Подключить' }).click();
  await expect.poll(() => operationIds.length).toBe(2);
  expect(operationIds[1]).toBe(operationIds[0]);
});

for (const lostCommandResponse of [false, true]) {
  test(`PATH-START AC05 rejects a foreign organization readback after ${lostCommandResponse ? 'lost' : 'confirmed'} command`, async ({ page }) => {
    const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
    const organization = { id: 3, code: 'ac05-foreign', name: 'Owned synthetic organization',
      is_active: true, domains: [], admins: [], members_count: 0, reports_count: 0,
      members: [], assessment_program: null };
    const connection = { organization_id: 3, program_definition_id: 11,
      program_name: 'Owned pilot', program_version: '1.1', assignment_ref: 'pilot-4k-9',
      roles: [], role_capabilities: [] };
    const operationIds = [];
    await page.route('**/users/**', (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/users/session/restore') return fulfillJson(route, {
        authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
      });
      if (pathname === '/users/version') return fulfillJson(route, { version: 'ac05-test' });
      if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
      if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') {
        return fulfillJson(route, { is_superadmin: true, items: [organization],
          assessment_programs: [{ id: 11, name: connection.program_name, version: connection.program_version }] });
      }
      if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
      if (pathname === '/users/admin/organizations/3/assessment-program') {
        if (route.request().method() === 'PUT') {
          operationIds.push(route.request().postDataJSON().operation_id);
          return lostCommandResponse ? route.abort('connectionreset') : fulfillJson(route, { connection });
        }
        return fulfillJson(route, { connection: { ...connection, organization_id: 999,
          program_name: 'Foreign organization pilot' } });
      }
      return fulfillJson(route, {}, 404);
    });
    await page.goto(base);
    await page.locator('#admin-open-organizations-button').click();
    const form = page.locator('[data-action="connect-assessment-program"]');
    await form.locator('[name="program_definition_id"]').selectOption('11');
    await form.getByRole('button', { name: 'Подключить' }).click();
    const status = form.locator('[data-operation-status]');
    await expect(status).toHaveAttribute('data-tone', 'error');
    await expect(form).not.toContainText('Foreign organization pilot');
    await expect(form.getByRole('button', { name: 'Подключить' })).toBeEnabled();
    await form.getByRole('button', { name: 'Подключить' }).click();
    await expect.poll(() => operationIds.length).toBe(2);
    expect(operationIds[1]).toBe(operationIds[0]);
    await expect(status).toHaveAttribute('data-tone', 'error');
  });
}

test('PROGRAM01 R10 confirms a committed connection after the PUT response is lost', async ({ page }) => {
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const connection = {
    organization_id: 3, program_definition_id: 11, program_name: 'Пилот 4К · 9 кейсов',
    program_version: '1.1', assignment_ref: 'pilot-4k-9', roles: [], role_capabilities: [],
  };
  const operationIds = [];
  let serverConnected = false;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r10-test' });
    if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
    if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') return fulfillJson(route, {
      is_superadmin: true,
      items: [{ id: 3, code: 'r10-lost', name: 'R10 Lost Response', is_active: true,
        domains: [], admins: [], members_count: 0, reports_count: 0, members: [],
        assessment_program: serverConnected ? connection : null }],
      assessment_programs: [{ id: 11, name: connection.program_name, version: connection.program_version }],
    });
    if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'PUT') {
      operationIds.push(route.request().postDataJSON().operation_id);
      serverConnected = true;
      return route.abort('connectionreset');
    }
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'GET') {
      return fulfillJson(route, { connection });
    }
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#admin-open-organizations-button').click();
  const form = page.locator('[data-action="connect-assessment-program"]');
  await form.locator('[name="program_definition_id"]').selectOption('11');
  await form.getByRole('button', { name: 'Подключить' }).click();
  await expect(form.locator('[data-operation-status]')).toContainText('подтверждено повторным чтением');
  await expect(form).toContainText('Подключено: Пилот 4К · 9 кейсов · 1.1');
  expect(operationIds).toHaveLength(1);
});

test('PROGRAM01 R10 restores the exact connected program after reopening the card', async ({ page }) => {
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const connection = {
    organization_id: 3, program_definition_id: 11, program_name: 'Пилот 4К · 9 кейсов',
    program_version: '1.1', assignment_ref: 'pilot-4k-9', roles: [], role_capabilities: [],
  };
  let serverConnected = false;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r10-test' });
    if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
    if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') return fulfillJson(route, {
      is_superadmin: true,
      items: [{ id: 3, code: 'r10-reload', name: 'R10 Reload', is_active: true,
        domains: [], admins: [], members_count: 0, reports_count: 0, members: [],
        assessment_program: serverConnected ? connection : null }],
      assessment_programs: [{ id: 11, name: connection.program_name, version: connection.program_version }],
    });
    if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'PUT') {
      serverConnected = true;
      return fulfillJson(route, { connection });
    }
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'GET') {
      return fulfillJson(route, { connection: serverConnected ? connection : null });
    }
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#admin-open-organizations-button').click();
  const form = page.locator('[data-action="connect-assessment-program"]');
  await form.locator('[name="program_definition_id"]').selectOption('11');
  await form.getByRole('button', { name: 'Подключить' }).click();
  await expect(form).toContainText('Подключено: Пилот 4К · 9 кейсов · 1.1');
  await page.locator('#admin-open-organizations-button').click();
  await expect(page.locator('[data-action="connect-assessment-program"]'))
    .toContainText('Подключено: Пилот 4К · 9 кейсов · 1.1');
});

test('PROGRAM01 R10 does not render the old connection result after logout', async ({ page }) => {
  const dashboard = { is_superadmin: true, metrics: [], insights: [], activity_series: [], competency_average: [] };
  const connection = {
    organization_id: 3, program_definition_id: 11, program_name: 'Пилот 4К · 9 кейсов',
    program_version: '1.1', assignment_ref: 'pilot-4k-9', roles: [], role_capabilities: [],
  };
  let releaseReadback;
  const delayedReadback = new Promise((resolve) => { releaseReadback = resolve; });
  await page.route('**/users/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user: adminUser, is_admin: true, admin_dashboard: dashboard,
    });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r10-test' });
    if (pathname === '/users/admin/dashboard') return fulfillJson(route, dashboard);
    if (pathname === '/users/session/logout') return fulfillJson(route, { ok: true });
    if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') return fulfillJson(route, {
      is_superadmin: true,
      items: [{ id: 3, code: 'r10-context', name: 'R10 Context', is_active: true,
        domains: [], admins: [], members_count: 0, reports_count: 0, members: [], assessment_program: null }],
      assessment_programs: [{ id: 11, name: connection.program_name, version: connection.program_version }],
    });
    if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'PUT') {
      return fulfillJson(route, { connection });
    }
    if (pathname === '/users/admin/organizations/3/assessment-program' && route.request().method() === 'GET') {
      await delayedReadback;
      return fulfillJson(route, { connection });
    }
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#admin-open-organizations-button').click();
  const form = page.locator('[data-action="connect-assessment-program"]');
  await form.locator('[name="program_definition_id"]').selectOption('11');
  await form.getByRole('button', { name: 'Подключить' }).click();
  await page.locator('#admin-organizations-account-name').click();
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  releaseReadback();
  await expect(page.locator('#auth-panel')).toBeVisible();
  await expect(page.locator('#admin-organizations-panel')).toBeHidden();
});
const syntheticAdminProgram = (assignmentRef, id = 7) => ({
  organization_id: 3, program_definition_id: id, program_name: `Синтетическая программа ${id}`,
  program_version: 'synthetic-1', assignment_ref: assignmentRef,
  roles: [{ version_id: 92, code: 'synthetic', name: 'Синтетическая роль' }],
  role_capabilities: [{ version_id: 92, code: 'synthetic', name: 'Синтетическая роль', is_available: true }],
});
const adminOrganization = {
  assessment_program: syntheticAdminProgram('competencies_4k'),
  id: 3, code: 'r03', name: 'R03 Organization', is_active: true, domains: [], admins: [],
  members_count: 1, reports_count: 0,
  members: [{ user_id: 8, email: 'person@example.test', full_name: 'Person', has_password: false,
    registration_status: 'pending', invitation_id: 1, invitation_status: 'queued',
    invitation_assignment_ref: 'competencies_4k', invitation_delivery_status: 'queued', invitation_link_status: 'active' }],
};

const withConnectedAssessment = (assessmentRef, id = 7) => ({
  ...adminOrganization, assessment_program: syntheticAdminProgram(assessmentRef, id),
});

async function fillEarlyField(form, name, value) {
  const field = form.locator(`[name="${name}"]`);
  if (['case_reality_level', 'organization_name_usage_rules'].includes(name)) await field.selectOption(value);
  else await field.fill(value);
}

async function reopenAdminOrganizations(page) {
  await page.locator('#admin-organizations-panel').getByRole('button', { name: 'Отчёты организации', exact: true }).click();
  await page.locator('#admin-reports-panel').getByRole('button', { name: 'К управлению', exact: true }).click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
}

async function openAdminOrganizations(page, invitationHandler, organization = adminOrganization, questionnaireResponse = null, isSuperadmin = false) {
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    if (pathname === '/users/auth/email/request-link') return fulfillJson(route, { email: adminUser.email, auth_mode: 'password' });
    if (pathname === '/users/auth/email/password-login') return fulfillJson(route, {
      exists: true, user: adminUser, is_admin: true,
      agent: { session_id: 'admin', message: '', stage: 'admin', completed: true },
      admin_dashboard: { metrics: [], insights: [], activity_series: [], competency_average: [] },
    });
    if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') {
      return fulfillJson(route, { is_superadmin: isSuperadmin, purge_preview_available: true, items: [organization] });
    }
    if (pathname === '/users/admin/organizations/3' && route.request().method() === 'PATCH') {
      return fulfillJson(route, { is_superadmin: isSuperadmin, purge_preview_available: true, items: [organization] });
    }
    if (pathname === '/users/admin/organizations/3/questionnaire') {
      const fallback = { items: [{ id: 11, assignment_ref: 'competencies_4k',
        status: 'confirmed', channel: 'product_form', validation_json: {}, briefing: {},
        readiness: {
          status: 'incomplete',
          early: { status: 'ready', message: 'Ранний минимум подтверждён. Участников можно приглашать.' },
          context: { status: 'ready', message: 'Контекст выбранной оценки подтверждён и закреплён сервером.' },
          roles: { status: 'incomplete', message: 'Нужно проверить связку профиля и роли: 1.',
            ready: 0, total: 1, action_view: 'people' },
          preparation: { status: 'idle', message: 'Активной подготовки сейчас нет.' },
        } }] };
      return fulfillJson(route, questionnaireResponse?.body || fallback, questionnaireResponse?.status || 200);
    }
    if (pathname.startsWith('/users/admin/organizations/3/personal-invitations')) return invitationHandler(route);
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#email-input').fill(adminUser.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  if (organization.members.length) {
    await page.locator('input[name="invitation_email"]').first().waitFor();
  } else {
    await page.locator('.admin-organizations-empty').waitFor();
  }
}

test('QA19-03 keeps the participant section available with no members', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), {
    ...adminOrganization, members_count: 0, members: [],
  });
  await expect(page.locator('.admin-organization-member')).toHaveCount(0);
  await expect(page.locator('.admin-organization-members-section').first()).toBeVisible();
});

for (const action of ['card', 'cancel-dialog']) {
  test(`PATH-START ST-R1 ${action}: local view or refusal is not a pending mutation`, async ({ page }, testInfo) => {
    const organization = { ...adminOrganization,
      assessment_program: { program_definition_id: 7, program_name: 'Synthetic PATH program',
        program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
      members: [{ ...adminOrganization.members[0], assessment_assignments: ['competencies_4k'],
        assessment_stages: { competencies_4k: { code: 'assigned', assignment_id: 41 } } }] };
    await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
    let mutations = 0;
    page.on('request', (request) => {
      if (request.url().includes('/users/admin/organizations/') && request.method() !== 'GET') mutations += 1;
    });
    if (action === 'card') {
      await page.locator('[data-action="open-member-card"]').click();
      await page.locator('.admin-member-card-dialog').getByRole('button', { name: 'Закрыть', exact: true }).click();
    } else {
      await page.locator('.admin-organization-member-menu summary').click();
      await page.getByRole('menuitem', { name: 'Отменить назначение оценки' }).click();
      await page.getByRole('dialog', { name: 'Отменить назначение?' })
        .getByRole('button', { name: 'Оставить назначение', exact: true }).click();
    }
    const statuses = await page.locator('[data-operation-status]:visible').allTextContents();
    await testInfo.attach('local-action-result', { body: JSON.stringify({ action, mutations, statuses }),
      contentType: 'application/json' });
    expect(mutations).toBe(0);
    expect(statuses.join(' ')).not.toContain('Выполняем действие…');
    await expect(page.locator('#admin-organizations-status')).not.toContainText('Выполняем действие…');
  });
}

test('PATH-START ST-R1: confirmed cancellation has local loading and a terminal error', async ({ page }) => {
  const organization = { ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Synthetic PATH program',
      program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
    members: [{ ...adminOrganization.members[0], assessment_assignments: ['competencies_4k'],
      assessment_stages: { competencies_4k: { code: 'assigned', assignment_id: 41 } } }] };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  let release;
  let posts = 0;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/assessment-assignments/41/cancel', async (route) => {
    posts += 1;
    await delayed;
    return fulfillJson(route, { detail: 'synthetic service failure' }, 500);
  });
  await page.locator('.admin-organization-member-menu summary').click();
  await page.getByRole('menuitem', { name: 'Отменить назначение оценки' }).click();
  await expect(page.locator('#admin-organizations-status')).not.toContainText('Выполняем действие…');
  expect(posts).toBe(0);
  try {
    await page.getByRole('dialog', { name: 'Отменить назначение?' })
      .getByRole('button', { name: 'Отменить назначение', exact: true }).click();
    await expect(page.locator('[data-operation-status]')).toContainText('Выполняем действие…');
    expect(posts).toBe(1);
  } finally {
    release();
  }
  await expect(page.locator('[data-operation-status]')).toBeVisible();
  await expect(page.locator('[data-operation-status]')).not.toContainText('Выполняем действие…');
  await page.locator('.admin-organization-member-menu summary').click();
  await expect(page.getByRole('menuitem', { name: 'Отменить назначение оценки' })).toBeEnabled();
  expect(posts).toBe(1);
});

test('PATH-START ST-R4: authorized read-only preparation action survives renderer', async ({ page }) => {
  const organization = { ...adminOrganization,
    members: [{ ...adminOrganization.members[0], assessment_assignments: ['competencies_4k'],
      assessment_stages: { competencies_4k: { code: 'preparing', label: 'Идёт подготовка оценки',
        action: 'check_preparation', assignment_id: 41, operation_id: 'synthetic-current-operation' } } }] };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  await expect(page.locator('[data-action="check-member-preparation"]')).toBeVisible();
  let mutations = 0;
  page.on('request', (request) => {
    if (request.url().includes('/users/admin/organizations/') && request.method() !== 'GET') mutations += 1;
  });
  await page.locator('[data-action="check-member-preparation"]').click();
  await expect(page.locator('#admin-organizations-status')).toContainText('обновлено');
  expect(mutations).toBe(0);
});

for (const width of [1440, 320, 390, 768]) {
  test(`PATH-START viewport ${width}: long facts, unknown questionnaire, read-only action`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const organization = { ...adminOrganization,
      name: 'Синтетическая организация с очень длинным названием для проверки переноса важных сведений',
      assessment_program: { program_definition_id: 7, program_name: 'Пилот 4К · 9 кейсов',
        program_version: '1.1', assignment_ref: 'specialist-pilot',
        roles: [{ version_id: 2, code: 'specialist_expert', name: 'Специалист / эксперт' }] },
      members: [{ ...adminOrganization.members[0],
        full_name: 'Синтетический участник с очень длинным именем для проверки переноса строк',
        job_description: 'Специалист по согласованию сложных неоднозначных задач нескольких подразделений',
        assessment_assignments: ['specialist-pilot'], assessment_stages: { 'specialist-pilot': {
          code: 'preparing', label: 'Идёт подготовка оценки', action: 'check_preparation', assignment_id: 41,
          description: 'Подготовка выполняется автоматически. Проверка только обновляет состояние; время оценки не началось.',
        } } }] };
    await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization,
      { body: { detail: 'Synthetic read unavailable' }, status: 503 });
    const card = page.locator('[data-organization-id="3"]');
    await expect(card.locator('.admin-assignment-readiness')).toContainText('Не удалось проверить сохранённую анкету');
    const explanation = await card.locator('.admin-assignment-readiness .form-status li').boundingBox();
    expect(explanation.width).toBeGreaterThan(150);
    const action = card.locator('[data-action="check-member-preparation"]');
    await expect(action).toBeVisible();
    await expect(page.locator('body')).toHaveJSProperty('scrollWidth', width);
    const box = await action.boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(width);
    expect(box.height).toBeGreaterThan(20);
    await fs.mkdir(path.join(root, '.test-stand/path-start-viewports'), { recursive: true });
    await page.screenshot({ path: path.join(root, `.test-stand/path-start-viewports/admin-${width}.png`), fullPage: true });
    await card.locator('[data-action="open-member-card"]').click();
    const dialog = page.locator('.admin-member-card-dialog');
    await expect(dialog).toContainText('Синтетический участник');
    await expect(dialog).toContainText('Подготовка выполняется автоматически');
    await dialog.getByRole('button', { name: 'Закрыть', exact: true }).click();
    expect((await page.locator('[data-operation-status]:visible').allTextContents()).join(' '))
      .not.toContain('Выполняем действие…');
  });
}

test('PATH-START PG-R1: participant sees the exact missing-position reason and can recheck', async ({ page }) => {
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Synthetic participant' };
  let checks = 0;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user, is_admin: false, dashboard: {},
    });
    if (pathname === '/users/8/journey-state') {
      checks += 1;
      return fulfillJson(route, { next_action: 'wait_for_acquaintance_data', profile: { status: 'incomplete' },
        onboarding: { status: 'not_started' }, assessment: { status: 'not_started' },
        acquaintance: { readiness: { status: 'waiting_for_organization', reason: 'participant_fields:position',
          title: 'Нужно уточнить сведения участника',
          message: 'В карточке участника не заполнена должность. Обратитесь к администратору организации. Ваши ответы сохраняются.',
        } } });
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: appRelease });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await expect(page.locator('#auth-complete-title')).toHaveText('Нужно уточнить сведения участника');
  await expect(page.locator('#auth-complete-description')).toContainText('должность');
  await expect(page.locator('#auth-complete-description')).not.toContainText(/Обратитесь|администратору/);
  await expect(page.locator('#auth-complete-description')).not.toContainText('ещё готовит данные');
  const before = checks;
  await page.getByRole('button', { name: 'Проверить готовность', exact: true }).click();
  await expect.poll(() => checks).toBeGreaterThan(before);
});

test('ADM-STATUS-01 shows the current participant stage and opens known facts in the participant card', async ({ page }) => {
  const baseMember = { ...adminOrganization.members[0], assessment_assignments: ['competencies_4k'] };
  const organization = {
    ...adminOrganization,
    members_count: 8,
    members: [
      { ...baseMember, user_id: 8, email: 'not-sent@example.test', invitation_delivery_status: 'not_sent' },
      { ...baseMember, user_id: 9, email: 'started@example.test', assessment_stages: {
        competencies_4k: { code: 'acquaintance', label: 'Проходит знакомство' },
      } },
      { ...baseMember, user_id: 10, email: 'preparing@example.test', assessment_stages: {
        competencies_4k: { code: 'preparing', label: 'Идёт подготовка оценки', operation_id: 'prep-current' },
        'other-assessment': { code: 'preparation_failed', label: 'Подготовка завершилась с ошибкой', operation_id: 'prep-other' },
      } },
      { ...baseMember, user_id: 11, email: 'failed@example.test', assessment_stages: {
        competencies_4k: { code: 'preparation_failed', label: 'Подготовка завершилась с ошибкой' },
      } },
      { ...baseMember, user_id: 12, email: 'active@example.test', assessment_stages: {
        competencies_4k: { code: 'active', label: 'Оценка выполняется', description: 'Прогресс: 1 из 3 AS плана.' },
      } },
      { ...baseMember, user_id: 13, email: 'paused@example.test', assessment_stages: {
        competencies_4k: { code: 'paused', label: 'Оценка приостановлена', description: 'Ответственный: Участник.' },
      } },
      { ...baseMember, user_id: 14, email: 'interrupted@example.test', assessment_stages: {
        competencies_4k: { code: 'interrupted', label: 'Оценка прервана', description: 'Для продолжения требуется восстановить сессию.' },
      } },
      { ...baseMember, user_id: 15, email: 'blocked@example.test', assessment_stages: {
        competencies_4k: { code: 'start_blocked', label: 'Старт оценки заблокирован', description: 'Для Cycle не найден допустимый маршрут. Ответственный: Организатор оценки.' },
      } },
    ],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  const rows = page.locator('.admin-organization-member');
  await expect(rows.nth(0).locator('.admin-organization-current-stage')).toHaveText('Оценка назначена');
  await expect(rows.nth(1).locator('.admin-organization-current-stage')).toHaveText('Проходит знакомство');
  await expect(rows.nth(2).locator('.admin-organization-current-stage')).toHaveText('Идёт подготовка оценки');
  await expect(rows.nth(3).locator('.admin-organization-current-stage')).toHaveText('Подготовка завершилась с ошибкой');
  await expect(rows.nth(3).locator('.admin-organization-current-stage')).toHaveClass(/is-critical/);
  await expect(rows.nth(4).locator('.admin-organization-current-stage')).toHaveText('Оценка выполняется');
  await expect(rows.nth(5).locator('.admin-organization-current-stage')).toHaveText('Оценка приостановлена');
  await expect(rows.nth(6).locator('.admin-organization-current-stage')).toHaveText('Оценка прервана');
  await expect(rows.nth(7).locator('.admin-organization-current-stage')).toHaveText('Старт оценки заблокирован');
  await rows.nth(7).locator('[data-action="open-member-card"]').click();
  await expect(page.locator('.admin-member-card-dialog')).toContainText('Организатор оценки');
  await page.locator('.admin-member-card-dialog').getByRole('button', { name: 'Закрыть', exact: true }).click();
  await rows.nth(1).locator('[data-action="open-member-card"]').click();
  const dialog = page.locator('.admin-member-card-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Проходит знакомство');
  await dialog.getByRole('button', { name: 'Закрыть', exact: true }).click();
  await expect(rows.nth(1).locator('[data-action="open-member-card"]')).toBeFocused();
  await fs.mkdir(path.join(root, 'docs/evc/evidence/adm-status-01'), { recursive: true });
  await page.locator('[data-organization-id="3"] [data-admin-view="people"]').screenshot({
    path: path.join(root, 'docs/evc/evidence/adm-status-01/desktop-status-list.png'),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('body')).toHaveJSProperty('scrollWidth', 390);
  await page.locator('[data-organization-id="3"] [data-admin-view="people"]').screenshot({
    path: path.join(root, 'docs/evc/evidence/adm-status-01/mobile-status-list.png'),
  });
});

test('ADM-STATUS-01 keeps one bulk panel and separates invitation revoke from assignment cancellation', async ({ page }) => {
  const organization = {
    ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Специалист 4К', program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
    members: [{ ...adminOrganization.members[0], full_name: 'Иван Иванов', raw_position: 'Руководитель',
      assessment_assignments: ['competencies_4k'], assessment_stages: {
        competencies_4k: { code: 'assigned', label: 'Оценка назначена', assignment_id: 41 },
      } }],
  };
  let cancelled = false;
  let revoked = false;
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  await page.route('**/users/admin/organizations/3/personal-invitations/1', (route) => {
    revoked = true;
    return fulfillJson(route, { ok: true });
  });
  await page.route('**/users/admin/organizations/3/assessment-assignments/41/cancel', (route) => {
    cancelled = true;
    return fulfillJson(route, { assignment_id: 41, status: 'cancelled' });
  });
  await expect(page.locator('.admin-organization-head')).toContainText('Программа «Специалист 4К» · версия 1.0');
  await expect(page.locator('[data-bulk-actions]')).toBeHidden();
  await page.locator('input[name="invitation_email"]').check();
  await expect(page.locator('[data-bulk-actions]')).toBeVisible();
  await expect(page.locator('[data-selected-count]')).toHaveText('1');
  const menu = page.locator('.admin-organization-member-menu');
  await menu.locator('summary').click();
  const revokeTrigger = menu.getByRole('menuitem', { name: 'Отозвать приглашение' });
  await revokeTrigger.click();
  let dialog = page.getByRole('dialog', { name: 'Отозвать приглашение?' });
  await expect(dialog).toContainText('Иван Иванов · person@example.test');
  await expect(dialog).toContainText('Персональная ссылка перестанет действовать');
  await expect(dialog).toContainText('Назначение оценки, участие в организации, аккаунт и обычный вход сохранятся');
  await expect(dialog.getByRole('button', { name: 'Оставить приглашение' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(menu.locator('summary')).toBeFocused();
  expect(revoked).toBe(false);
  await menu.locator('summary').click();
  await menu.getByRole('menuitem', { name: 'Отозвать приглашение' }).click();
  dialog = page.getByRole('dialog', { name: 'Отозвать приглашение?' });
  await dialog.getByRole('button', { name: 'Отозвать приглашение', exact: true }).click();
  await expect.poll(() => revoked).toBe(true);
  await page.locator('input[name="invitation_email"]').check();
  await menu.locator('summary').click();
  const cancelTrigger = menu.getByRole('menuitem', { name: 'Отменить назначение оценки' });
  await cancelTrigger.click();
  dialog = page.getByRole('dialog', { name: 'Отменить назначение?' });
  await expect(dialog).toContainText('Иван Иванов · «Специалист 4К · не выбрана»');
  await expect(dialog).not.toContainText('competencies_4k');
  await expect(dialog).toContainText('Для нового прохождения потребуется новое назначение');
  await expect(dialog).toContainText('Аккаунт, участие в организации и история сохранятся');
  await dialog.getByRole('button', { name: 'Отменить назначение', exact: true }).click();
  await expect.poll(() => cancelled).toBe(true);
  await expect(page.locator('input[name="invitation_email"]')).toBeVisible();
});

test('PROGRAM01 R08 refreshes actions and explains a revoke conflict after acquaintance starts', async ({ page }) => {
  const organization = structuredClone(adminOrganization);
  organization.members[0].full_name = 'Иван Иванов';
  organization.members[0].invitation_assignment_ref = null;
  await openAdminOrganizations(page, (route) => {
    return fulfillJson(route, { items: [] });
  }, organization);
  await page.route('**/users/admin/organizations/3/personal-invitations/1', (route) => {
    organization.members[0].invitation_status = 'used';
    organization.members[0].invitation_link_status = 'used';
    return fulfillJson(route, { detail: 'INVITATION_STATE_CHANGED' }, 409);
  });

  const menu = page.locator('.admin-organization-member-menu');
  const revoke = page.locator('[data-action="revoke-member-invitation"]');
  await revoke.click();
  await page.getByRole('dialog', { name: 'Отозвать приглашение?' })
    .getByRole('button', { name: 'Отозвать приглашение', exact: true }).click();

  await expect(page.locator('#admin-organizations-status'))
    .toContainText('приглашение нельзя отозвать после начала знакомства');
  await expect(menu).toHaveCount(0);
  await expect(page.locator('[data-action="revoke-member-invitation"]')).toHaveCount(0);
  await expect(page.locator('.admin-organization-member-invitation').filter({ hasText: 'Ссылка использована' }))
    .toContainText('Регистрация: завершена');
});

test('PROGRAM01 R06 marks a confirmed cancellation stale when readback fails and restores the action', async ({ page }) => {
  const organization = {
    ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Специалист 4К', program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
    members: [{ ...adminOrganization.members[0], full_name: 'Иван Иванов',
      assessment_assignments: ['competencies_4k'], assessment_stages: {
        competencies_4k: { code: 'assigned', label: 'Оценка назначена', assignment_id: 41 },
      } }],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  let posts = 0;
  await page.route('**/users/admin/organizations/3/assessment-assignments/41/cancel', (route) => {
    posts += 1;
    return fulfillJson(route, { assignment_id: 41, status: 'cancelled' });
  });
  await page.route('**/users/admin/organizations', (route) => route.abort('connectionreset'));
  const cancel = page.getByRole('menuitem', { name: 'Отменить назначение оценки' });
  await page.locator('.admin-organization-member-menu summary').click();
  await cancel.click();
  await page.getByRole('dialog', { name: 'Отменить назначение?' })
    .getByRole('button', { name: 'Отменить назначение', exact: true }).click();
  await expect(page.locator('[data-organizations-stale]')).toContainText('последнее подтверждённое состояние');
  await expect(page.getByRole('button', { name: 'Обновить безопасно' })).toBeVisible();
  await page.locator('.admin-organization-member-menu summary').click();
  await expect(page.getByRole('menuitem', { name: 'Отменить назначение оценки' })).toBeEnabled();
  expect(posts).toBe(1);
});

test('PROGRAM01 R06 refreshes an exact assignment after 409 and removes an invalid cancellation', async ({ page }) => {
  const member = { ...adminOrganization.members[0], full_name: 'Иван Иванов',
    assessment_assignments: ['competencies_4k'], assessment_stages: {
      competencies_4k: { code: 'assigned', label: 'Оценка назначена', assignment_id: 41 },
    } };
  const organization = {
    ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Специалист 4К', program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
    members: [member],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  await page.route('**/users/admin/organizations/3/assessment-assignments/41/cancel', (route) => {
    member.assessment_stages.competencies_4k = {
      code: 'active', label: 'Оценка выполняется', assignment_id: 41,
    };
    return fulfillJson(route, { detail: 'ASSESSMENT_ALREADY_STARTED' }, 409);
  });
  await page.locator('.admin-organization-member-menu summary').click();
  await page.getByRole('menuitem', { name: 'Отменить назначение оценки' }).click();
  await page.getByRole('dialog', { name: 'Отменить назначение?' })
    .getByRole('button', { name: 'Отменить назначение', exact: true }).click();
  await expect(page.locator('[data-operation-status]')).toContainText('больше не может быть отменено');
  await expect(page.locator('[data-action="cancel-member-assignment"]')).toHaveCount(0);
  await expect(page.locator('.admin-organization-member').first()).toContainText('Оценка выполняется');
});

test('PROGRAM01 R06 resolves a lost cancellation response by exact readback without a new intent', async ({ page }) => {
  const member = { ...adminOrganization.members[0], full_name: 'Иван Иванов',
    assessment_assignments: ['competencies_4k'], assessment_stages: {
      competencies_4k: { code: 'assigned', label: 'Оценка назначена', assignment_id: 41 },
    } };
  const organization = {
    ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Специалист 4К', program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
    members: [member],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  let posts = 0;
  let operationId = '';
  await page.route('**/users/admin/organizations/3/assessment-assignments/41/cancel', (route) => {
    posts += 1;
    operationId = route.request().postDataJSON().operation_id;
    member.assessment_stages.competencies_4k = {
      code: 'cancelled', label: 'Назначение отменено', assignment_id: 41,
    };
    return route.abort('connectionreset');
  });
  await page.locator('.admin-organization-member-menu summary').click();
  await page.getByRole('menuitem', { name: 'Отменить назначение оценки' }).click();
  await page.getByRole('dialog', { name: 'Отменить назначение?' })
    .getByRole('button', { name: 'Отменить назначение', exact: true }).click();
  await expect(page.locator('[data-operation-status]')).toContainText('после потери ответа команды');
  expect(posts).toBe(1);
  expect(operationId).toMatch(/^[0-9a-f-]{16,}$/i);
});

test('PROGRAM01 R06 does not render an old cancellation result after identity changes', async ({ page }) => {
  const organization = {
    ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Специалист 4К', program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
    members: [{ ...adminOrganization.members[0], full_name: 'Иван Иванов',
      assessment_assignments: ['competencies_4k'], assessment_stages: {
        competencies_4k: { code: 'assigned', label: 'Оценка назначена', assignment_id: 41 },
      } }],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  let release;
  const delayed = new Promise((resolve) => { release = resolve; });
  await page.route('**/users/admin/organizations/3/assessment-assignments/41/cancel', async (route) => {
    await delayed;
    return fulfillJson(route, { assignment_id: 41, status: 'cancelled' });
  });
  await page.locator('.admin-organization-member-menu summary').click();
  await page.getByRole('menuitem', { name: 'Отменить назначение оценки' }).click();
  await page.getByRole('dialog', { name: 'Отменить назначение?' })
    .getByRole('button', { name: 'Отменить назначение', exact: true }).click();
  await page.locator('#admin-organizations-account-name').click();
  await page.locator('#admin-organizations-logout-button').click();
  await expect(page.locator('#auth-panel')).toBeVisible();
  release();
  await expect(page.locator('#admin-organizations-panel')).toBeHidden();
  await expect(page.locator('#admin-organizations-status')).not.toContainText('Назначение оценки отменено');
});

for (const [status, detail] of [[403, 'Недостаточно прав.'], [500, 'synthetic service failure']]) {
  test(`PROGRAM01 R06 restores cancellation after ${status}`, async ({ page }) => {
    const organization = {
      ...adminOrganization,
      assessment_program: { program_definition_id: 7, program_name: 'Специалист 4К', program_version: '1.0', assignment_ref: 'competencies_4k', roles: [] },
      members: [{ ...adminOrganization.members[0], full_name: 'Иван Иванов',
        assessment_assignments: ['competencies_4k'], assessment_stages: {
          competencies_4k: { code: 'assigned', label: 'Оценка назначена', assignment_id: 41 },
        } }],
    };
    await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
    let posts = 0;
    await page.route('**/users/admin/organizations/3/assessment-assignments/41/cancel', (route) => {
      posts += 1;
      return fulfillJson(route, { detail }, status);
    });
    await page.locator('.admin-organization-member-menu summary').click();
    await page.getByRole('menuitem', { name: 'Отменить назначение оценки' }).click();
    await page.getByRole('dialog', { name: 'Отменить назначение?' })
      .getByRole('button', { name: 'Отменить назначение', exact: true }).click();
    await expect(page.locator('[data-operation-status]')).toBeVisible();
    await page.locator('.admin-organization-member-menu summary').click();
    await expect(page.getByRole('menuitem', { name: 'Отменить назначение оценки' })).toBeEnabled();
    expect(posts).toBe(1);
  });
}

test('PROGRAM01 R05 keeps privileged password reset in the card and exposes only an authorized exact report', async ({ page }) => {
  const reportId = '11111111-1111-4111-8111-111111111111';
  const organization = {
    ...adminOrganization,
    members: [{ ...adminOrganization.members[0], has_password: true,
      invitation_created_at: '2026-11-01T10:00:00Z', invitation_expires_at: '2026-11-04T10:00:00Z',
      assessment_assignments: ['competencies_4k'], assessment_stages: {
        competencies_4k: { code: 'report_ready', label: 'Отчёт готов', action: 'open_report',
          assignment_id: 41, cycle_id: '22222222-2222-4222-8222-222222222222',
          report_id: reportId, report_access: 'customer' },
      } }],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization, null, true);
  const row = page.locator('.admin-organization-member').first();
  await expect(row.getByRole('button', { name: 'Открыть отчёт' })).toHaveAttribute('data-report-id', reportId);
  await row.locator('.admin-organization-member-menu summary').click();
  await expect(row.getByRole('menuitem', { name: 'Сбросить пароль' })).toHaveCount(0);
  await row.locator('[data-action="open-member-card"]').click();
  const card = page.locator('.admin-member-card-dialog');
  await expect(card).not.toContainText('История приглашения');
  await expect(row.locator('.admin-organization-member-invitation')).toContainText('Ссылка');
  await expect(card.getByRole('button', { name: 'Сбросить пароль' })).toHaveCount(1);
});

test('ADM-UI-01 keeps the sent menu to two items and moves deletion and incident facts to the card', async ({ page }) => {
  const reportId = '11111111-1111-4111-8111-111111111111';
  const organization = { ...adminOrganization, members: [
    { ...adminOrganization.members[0], user_id: 8, email: 'new@example.test', invitation_id: null,
      invitation_status: 'not_sent', invitation_delivery_status: 'not_sent', invitation_link_status: 'not_created' },
    { ...adminOrganization.members[0], user_id: 9, email: 'sent@example.test', invitation_status: 'accepted',
      invitation_delivery_status: 'accepted' },
    { ...adminOrganization.members[0], user_id: 10, email: 'result@example.test', invitation_status: 'used',
      invitation_delivery_status: 'accepted', invitation_link_status: 'used', assessment_assignments: ['competencies_4k'],
      assessment_stages: { competencies_4k: { code: 'report_ready', action: 'open_report',
        cycle_id: '22222222-2222-4222-8222-222222222222', report_id: reportId, report_access: 'customer',
        result_summary: { kind: 'insufficient' } } } },
    { ...adminOrganization.members[0], user_id: 11, email: 'failed@example.test', invitation_status: 'used',
      invitation_delivery_status: 'accepted', assessment_assignments: ['competencies_4k'],
      assessment_stages: { competencies_4k: { code: 'preparation_failed', action: 'retry_preparation',
        operation_id: 'prep-known-11', description: 'Последний подтверждённый этап: подготовка кейсов.' } } },
  ] };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  const account = page.locator('.org-admin-account-menu');
  await expect(account.locator('#admin-organizations-account-name')).toHaveText('Admin');
  await account.locator('summary').click();
  await expect(account.locator('#admin-organizations-menu-name')).toHaveText('Admin');
  await expect(account.locator('#admin-organizations-menu-role')).toHaveText('Администратор R03 Organization');
  await expect(account.getByRole('button', { name: 'К сводке', exact: true })).toHaveCount(0);
  await expect(account.getByRole('button', { name: 'Выйти' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(account).not.toHaveAttribute('open');
  const rows = page.locator('.admin-organization-member');
  await expect(rows.nth(0).getByRole('button', { name: 'Пригласить' })).toBeVisible();
  await expect(rows.nth(0).locator('.admin-organization-member-menu')).toHaveCount(0);
  await expect(rows.nth(1).locator('.admin-organization-member-menu')).toHaveCount(1);
  await rows.nth(1).locator('.admin-organization-member-menu summary').click();
  const sentActions = rows.nth(1).getByRole('menuitem');
  await expect(sentActions).toHaveText(['Отправить письмо повторно', 'Отозвать приглашение']);
  await expect(sentActions.first()).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(sentActions.last()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(rows.nth(1).locator('.admin-organization-member-menu')).not.toHaveAttribute('open');
  await expect(rows.nth(1).locator('.admin-organization-member-menu summary')).toBeFocused();
  await expect(rows.nth(2).getByRole('button', { name: 'Открыть пояснение' })).toHaveAttribute('data-report-id', reportId);
  await expect(rows.nth(2).locator('.admin-organization-member-menu')).toHaveCount(0);
  await expect(rows.locator('[data-action="purge-account"]')).toHaveCount(0);
  await expect(rows.nth(3)).toContainText('Последний подтверждённый этап: подготовка кейсов.');
  await rows.nth(3).locator('[data-action="open-member-card"]').click();
  const incidentCard = page.locator('.org-admin-member-card');
  await expect(incidentCard).toContainText('Подготовка заблокирована');
  await expect(incidentCard.getByRole('button', { name: 'Проверить состояние' })).toBeVisible();
  await expect(incidentCard.getByRole('button', { name: 'Скопировать номер' })).toBeHidden();
  await page.keyboard.press('Escape');
  const reads = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/users/admin/organizations') reads.push(request.method());
  });
  await rows.nth(3).getByRole('button', { name: 'Проверить состояние' }).click();
  await expect.poll(() => reads.length).toBeGreaterThan(0);
  expect(reads).toEqual(['GET']);
  await rows.nth(1).locator('[data-action="open-member-card"]').click();
  await expect(page.locator('.admin-member-card-dialog')).not.toContainText('Регистрация');
  await expect(page.locator('.admin-member-card-dialog')).not.toContainText('Письмо и ссылка');
  await expect(page.locator('[data-card-delete]').getByRole('button', { name: 'Удалить человека' })).toBeVisible();
  await expect(rows.nth(1).locator('.admin-organization-member-invitation')).toContainText('Регистрация');
  await page.locator('.admin-member-card-dialog').getByRole('button', { name: 'Закрыть', exact: true }).click();
  const reportReads = [];
  page.on('request', (request) => {
    if (request.method() === 'GET' && new URL(request.url()).pathname.includes('/admin/m8-access/reports/')) {
      reportReads.push(new URL(request.url()).pathname);
    }
  });
  await rows.nth(2).getByRole('button', { name: 'Открыть пояснение' }).click();
  await expect.poll(() => reportReads).toContain('/users/admin/m8-access/reports/' + reportId);
});

test('ARCH30 offers an explicit one-way legacy profile copy into an empty C01 draft', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), {
    ...adminOrganization,
    profile: 'Старое описание деятельности',
  });
  await page.getByRole('button', { name: 'Данные организации' }).click();
  const legacy = page.locator('.admin-organization-legacy-profile');
  await expect(legacy).toContainText('Старое описание деятельности');
  const target = page.locator('textarea[name="activity_description"]');
  await expect(target).toHaveValue('');
  await legacy.getByRole('button', { name: 'Перенести в описание деятельности' }).click();
  await expect(target).toHaveValue('Старое описание деятельности');
  await expect(legacy.getByRole('button')).toHaveText('Перенесено в черновик');
});

test('QA19-03 keeps long participant rows readable and actions associated after view changes', async ({ page }) => {
  const longEmail = 'very.long.participant.name.for.layout.regression@example.invalid';
  const organization = {
    ...adminOrganization,
    members_count: 2,
    members: [
      { ...adminOrganization.members[0], full_name: 'Очень длинное имя участника для проверки переноса строки без сжатия',
        email: longEmail, raw_position: 'Руководитель направления поддержки и развития клиентских сервисов',
        invitation_delivery_status: 'accepted' },
      { ...adminOrganization.members[0], user_id: 9, email: 'second@example.invalid', full_name: 'Другой участник',
        registration_status: 'registered', invitation_status: 'used', invitation_delivery_status: 'accepted',
        invitation_link_status: 'used', invitation_id: 2 },
    ],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  const rows = page.locator('.admin-organization-member');
  await expect(rows).toHaveCount(2);
  await expect(rows.first().locator('.admin-organization-invitation-state')).toHaveCount(0);
  await rows.nth(1).locator('[data-action="open-member-card"]').click();
  await expect(page.locator('.admin-member-card-dialog')).not.toContainText('Регистрация');
  await expect(rows.nth(1).locator('.admin-organization-member-invitation')).toContainText('Регистрация: завершена');
  await page.locator('.admin-member-card-dialog').getByRole('button', { name: 'Закрыть', exact: true }).click();
  await expect(rows.nth(1).locator('[data-action="send-member-invitation"]')).toHaveCount(0);

  // 683 CSS px approximates the available width at 200% browser zoom on a 1366 px display.
  for (const width of [320, 375, 390, 683, 768, 1024, 1366, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const layout = await rows.first().evaluate((row) => {
      const main = row.querySelector('.admin-organization-member-main').getBoundingClientRect();
      const name = row.querySelector('.admin-organization-member-name').getBoundingClientRect();
      const statuses = row.querySelector('.admin-organization-member-stage').getBoundingClientRect();
      const actions = row.querySelector('.admin-organization-member-menu').getBoundingClientRect();
      const select = row.querySelector('.admin-organization-member-select').getBoundingClientRect();
      const buttons = [...row.querySelectorAll('button, summary')]
        .filter((button) => button.getClientRects().length).map((button) => button.getBoundingClientRect());
      return { documentWidth: document.documentElement.scrollWidth, viewportWidth: document.documentElement.clientWidth,
        mainWidth: main.width, nameWidth: name.width, statusesX: statuses.x, statusesY: statuses.y,
        mainRight: main.right, mainBottom: main.bottom, actionsX: actions.x, actionsY: actions.y,
        selectWidth: select.width, selectHeight: select.height,
        buttons: buttons.map((rect) => ({ width: rect.width, height: rect.height })) };
    });
    expect(layout.documentWidth, JSON.stringify(layout)).toBeLessThanOrEqual(layout.viewportWidth + 1);
    expect(layout.nameWidth).toBeGreaterThan(100);
    expect(layout.selectWidth).toBeGreaterThanOrEqual(44);
    expect(layout.selectHeight).toBeGreaterThanOrEqual(44);
    expect(layout.buttons.every((button) => button.width >= 44 && button.height >= 44)).toBe(true);
    if (layout.statusesY < layout.mainBottom - 1) {
      expect(layout.mainRight).toBeLessThanOrEqual(layout.statusesX);
    } else {
      expect(layout.statusesY).toBeGreaterThanOrEqual(layout.mainBottom);
    }
    expect(layout.actionsX >= layout.mainRight - 1 || layout.actionsY >= layout.mainBottom).toBe(true);
  }

  const checkbox = rows.first().getByRole('checkbox', { name: 'Выбрать ' + longEmail });
  await checkbox.focus();
  await page.keyboard.press('Space');
  await expect(checkbox).toBeChecked();
  await rows.first().locator('.admin-organization-member-select').click();
  await expect(checkbox).not.toBeChecked();
  await page.getByRole('button', { name: 'Данные организации' }).click();
  await page.getByRole('button', { name: 'Участники оценки' }).click();
  await expect(rows.first().locator('[data-action="send-member-invitation"]')).toHaveAttribute('data-value', longEmail);
  await rows.first().locator('[data-action="open-member-card"]').click();
  let purgePosts = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/users\/admin\/users\/8\/purge$/.test(request.url())) purgePosts += 1;
  });
  await page.route('**/users/admin/users/8/purge-preview', (route) => fulfillJson(route, {
    fingerprint: 'synthetic-current-person-delete', tables: { users: 1 },
  }));
  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain(longEmail);
    await dialog.dismiss();
  });
  const deletePerson = page.locator('dialog [data-action="purge-account"]');
  await deletePerson.click();
  await expect(deletePerson).toBeEnabled();
  expect(purgePosts).toBe(0);
  await expect(rows).toHaveCount(2);
  await expect(page.locator('.admin-purge-recovery')).toHaveCount(0);
});

test('ADM-STATUS-01 keeps superadmin participant cards readable on narrow viewports', async ({ page }) => {
  const longEmail = 'very.long.participant.name.for.superadmin.layout@example.invalid';
  const organization = {
    ...adminOrganization,
    members: [{ ...adminOrganization.members[0], email: longEmail,
      full_name: 'Очень длинное имя участника для мобильной карточки суперадмина',
      raw_position: 'Руководитель направления корпоративных внедрений',
      invitation_delivery_status: 'accepted' }],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization, null, true);
  const row = page.locator('.admin-organization-member').first();

  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const layout = await row.evaluate((member) => {
      const main = member.querySelector('.admin-organization-member-main').getBoundingClientRect();
      const name = member.querySelector('.admin-organization-member-name').getBoundingClientRect();
      const stage = member.querySelector('.admin-organization-member-stage').getBoundingClientRect();
      const menu = member.querySelector('.admin-organization-member-menu').getBoundingClientRect();
      return {
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
        rowWidth: member.getBoundingClientRect().width,
        mainWidth: main.width,
        nameWidth: name.width,
        mainRight: main.right,
        mainBottom: main.bottom,
        stageX: stage.x,
        stageY: stage.y,
        menuWidth: menu.width,
        menuHeight: menu.height,
      };
    });
    expect(layout.documentWidth, JSON.stringify(layout)).toBeLessThanOrEqual(layout.viewportWidth + 1);
    expect(layout.rowWidth, JSON.stringify(layout)).toBeGreaterThanOrEqual(width <= 390 ? 190 : 400);
    expect(layout.mainWidth, JSON.stringify(layout)).toBeGreaterThanOrEqual(width <= 390 ? 150 : 180);
    expect(layout.nameWidth, JSON.stringify(layout)).toBeGreaterThanOrEqual(width <= 390 ? 150 : 180);
    if (layout.stageY < layout.mainBottom - 1) {
      expect(layout.mainRight, JSON.stringify(layout)).toBeLessThanOrEqual(layout.stageX + 1);
    } else {
      expect(layout.stageY, JSON.stringify(layout)).toBeGreaterThanOrEqual(layout.mainBottom - 1);
    }
    expect(layout.menuWidth).toBeGreaterThanOrEqual(44);
    expect(layout.menuHeight).toBeGreaterThanOrEqual(44);
  }
});

test('ADM19-01 exposes three keyboard-operable management blocks without horizontal overflow', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));

  const card = page.locator('[data-organization-id="3"]');
  const people = card.locator('[data-admin-view="people"]');
  const organizationData = card.locator('[data-admin-view="organization-data"]');
  const questionnaire = card.locator('[data-admin-view="questionnaire"]');
  const peopleButton = card.getByRole('button', { name: 'Участники оценки' });
  const organizationDataButton = card.getByRole('button', { name: 'Данные организации' });
  const questionnaireButton = card.getByRole('button', { name: 'Анкета', exact: true });

  await expect(people).toBeVisible();
  await expect(organizationData).toBeHidden();
  await expect(questionnaire).toBeHidden();
  await expect(peopleButton).toHaveAttribute('aria-pressed', 'true');

  await organizationDataButton.focus();
  await page.keyboard.press('Enter');
  await expect(people).toBeHidden();
  await expect(organizationData).toBeVisible();
  await expect(organizationDataButton).toHaveAttribute('aria-pressed', 'true');
  await expect(card).toHaveAttribute('data-organization-id', '3');

  await questionnaireButton.click();
  await expect(questionnaire).toBeVisible();
  await expect(questionnaireButton).toHaveAttribute('aria-pressed', 'true');

  await peopleButton.click();
  await expect(people).toBeVisible();
  await expect(organizationData).toBeHidden();
  await expect(peopleButton).toHaveAttribute('aria-pressed', 'true');

  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1280, 1366, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const layout = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      overflow: [...document.querySelectorAll('*')]
        .filter((node) => node.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
        .slice(0, 8)
        .map((node) => ({ tag: node.tagName, className: node.className, right: node.getBoundingClientRect().right })),
    }));
    expect(layout.scrollWidth, JSON.stringify(layout.overflow)).toBe(layout.clientWidth);
  }
});

test('UX-FIX20-04 shows server readiness and routes to missing roles without blocking member add', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  const panel = card.locator('[data-admin-view="questionnaire"] .admin-readiness-panel');
  await expect(panel).toContainText('Ранние сведения: Готово');
  await expect(panel).toContainText('Контекст: Готово');
  await expect(panel).toContainText('Участники: Требуется заполнение');
  await panel.getByRole('button', { name: 'Перейти' }).nth(2).click();
  await expect(card.locator('[data-admin-view="people"]')).toBeVisible();
  await expect(card.locator('[data-action="add-member"]')).toBeVisible();
});

test('F22-07 explains participant acquaintance wait without a false roles action', async ({ page }) => {
  const body = { items: [{
    id: 11, assignment_ref: 'competencies_4k', status: 'confirmed', channel: 'product_form',
    validation_json: {}, briefing: {}, readiness: {
      status: 'incomplete',
      early: { status: 'ready', message: 'Ранний минимум подтверждён.' },
      context: { status: 'ready', message: 'Контекст подтверждён.' },
      roles: {
        status: 'incomplete', ready: 0, total: 1, action_view: null,
        reasons: { acquaintance_wait: 1 },
        message: 'К началу готовы 0 из 1. ожидается завершение знакомства: 1.',
      },
      preparation: { status: 'idle', message: 'Активной подготовки сейчас нет.' },
    },
  }] };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), adminOrganization, { body });
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  const participantRow = card.locator('[data-admin-view="questionnaire"] .admin-readiness-panel li').filter({ hasText: 'Участники:' });
  await expect(participantRow).toContainText('ожидается завершение знакомства: 1');
  await expect(participantRow.getByRole('button', { name: 'Перейти' })).toHaveCount(0);
});

test('ADMIN-02 org-admin edits one organization name and never sees free tenant creation', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  await expect(page.locator('#admin-organization-create-form')).toBeHidden();
  const card = page.locator('[data-organization-id="3"]');
  await card.locator('.admin-organization-step[data-view="organization-data"]').click();
  const profile = card.locator('[data-action="update-profile"]');
  await expect(profile).toHaveCount(0);
  const form = card.locator('[data-action="preview-early-data"]');
  await expect(form.locator('[name="organization_name"]')).toHaveValue(adminOrganization.name);
  await expect(form.locator('[name="organization_name"]')).toHaveCount(1);
  await expect(form.locator('[name="code"]')).toHaveCount(0);
  await expect(card).toHaveCSS('border-radius', '8px');
  await expect(form).toBeVisible();
  await expect(card.locator('.admin-people-list')).toHaveCSS('border-radius', '8px');
  await form.locator('[name="organization_name"]').fill('Закреплённая организация');
  await expect(form.locator('[name="organization_name"]')).toHaveValue('Закреплённая организация');
});

test('UX-FIX20-04 keeps readiness separated when org-admin switches assessment', async ({ page }) => {
  const readiness = (status, message) => ({
    status: 'incomplete',
    early: { status, message },
    context: { status, message },
    roles: { status: 'not_started', message: 'Участники ещё не добавлены.', ready: 0, total: 0 },
    preparation: { status: 'idle', message: 'Активной подготовки сейчас нет.' },
  });
  const organization = withConnectedAssessment('assessment-a');
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization, {
    body: { items: [
      { id: 21, assignment_ref: 'assessment-a', status: 'confirmed', channel: 'product_form',
        validation_json: {}, answers_json: {}, readiness: readiness('ready', 'Контекст A подтверждён.') },
      { id: 22, assignment_ref: 'assessment-b', status: 'ready_for_confirmation', channel: 'product_form',
        validation_json: {}, answers_json: {}, readiness: readiness('draft_unconfirmed', 'Черновик B не подтверждён.') },
    ] },
  });
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  const assignment = card.locator('[data-admin-view="questionnaire"] [name="assignment_ref"]');
  const panel = card.locator('[data-admin-view="questionnaire"] .admin-readiness-panel');
  await expect(panel).toContainText('Контекст A подтверждён.');
  await expect(assignment).toHaveAttribute('type', 'hidden');
  organization.assessment_program = syntheticAdminProgram('assessment-b', 8);
  await reopenAdminOrganizations(page);
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  await expect(assignment).toHaveValue('assessment-b');
  await expect(panel).toContainText('Черновик B не подтверждён.');
  await expect(panel).not.toContainText('Контекст A подтверждён.');
});

test('UX-ADM28-02 reports questionnaire load failure separately and offers retry', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), adminOrganization, {
    body: { detail: 'temporary failure' }, status: 503,
  });
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  const error = card.locator('[data-admin-view="questionnaire"] .admin-questionnaire-load-state.error');
  await expect(error).toContainText('Сервис не смог выполнить операцию');
  await expect(error).not.toContainText('temporary failure');
  await expect(error.getByRole('button', { name: 'Повторить' })).toBeVisible();
  await expect(card.locator('[data-admin-view="questionnaire"] .admin-readiness-panel'))
    .toContainText('Готовность выбранной оценки ещё не рассчитана');
  await expect(card.locator('[data-action="preview-questionnaire"] [name="assignment_ref"]'))
    .toHaveValue('competencies_4k');
});

test('AC18-ADM-1A accepted composition stays usable across target widths and keyboard', async ({ page }, testInfo) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), adminOrganization, { body: { items: [] } });
  const card = page.locator('[data-organization-id="3"]');
  const people = card.getByRole('button', { name: 'Участники оценки', exact: true });
  const data = card.getByRole('button', { name: 'Данные организации', exact: true });
  const questionnaire = card.getByRole('button', { name: 'Анкета', exact: true });
  await expect(people).toBeVisible();
  await data.focus();
  await data.press('Enter');
  await expect(card.locator('[data-admin-view="organization-data"]')).toBeVisible();
  await expect(card.getByRole('group', { name: 'Об организации' })).toBeVisible();
  await expect(card.getByRole('group', { name: 'Настройки контекста для ситуаций' })).toBeVisible();
  await expect(card.getByRole('button', { name: 'Подтвердить сведения' })).toBeVisible();
  for (const width of [1440, 1280, 768, 390, 320]) {
    await page.setViewportSize({ width, height: width <= 390 ? 844 : 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await expect(card.getByRole('group', { name: 'Об организации' })).toBeVisible();
    await expect(card.getByRole('group', { name: 'Настройки контекста для ситуаций' })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`adm-1a-data-${width}.png`), fullPage: true });
  }
  await questionnaire.focus();
  await questionnaire.press('Enter');
  await expect(card.locator('[data-admin-view="questionnaire"]')).toBeVisible();
});

test('F22-06 restores confirmed fields when the selected assessment has no local draft', async ({ page }) => {
  const revision = (id, assignmentRef, purpose) => ({
    id, assignment_ref: assignmentRef, status: 'confirmed', channel: 'product_form',
    source_author: `Автор ${assignmentRef}`,
    validation_json: {}, answers_json: {
      C01: { name: `Организация ${assignmentRef}`, organization_type: 'Компания', industry: 'ИТ',
        activity_description: `Описание ${assignmentRef}` },
      C02a: { participant_text: purpose }, C03: { participant_text: `Использование ${assignmentRef}` },
      C04: { answer: 'Участник' }, C17: { case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено' },
      C21: { organizer: 'HR', responsible_contact: `${assignmentRef}@example.test` },
    },
    readiness: { status: 'ready', early: { status: 'ready', message: 'Готово' },
      context: { status: 'ready', message: 'Готово' }, roles: { status: 'ready', message: 'Готово' },
      preparation: { status: 'idle', message: 'Нет подготовки' } },
  });
  const organization = withConnectedAssessment('A');
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization, {
    body: { items: [revision(31, 'A', 'Published A'), revision(32, 'B', 'Published B')] },
  });

  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации' }).click();
  const form = card.locator('[data-action="preview-early-data"]');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Published A');
  await expect(form.locator('[name="source_author"]')).toHaveCount(0);
  const assignment = form.locator('[name="assignment_ref"]');
  await expect(assignment).toHaveAttribute('type', 'hidden');
  organization.assessment_program = syntheticAdminProgram('B', 8);
  await reopenAdminOrganizations(page);
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
  await expect(assignment).toHaveValue('B');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Published B');
  await expect(form.locator('[name="organization_name"]')).toHaveValue(organization.name);
  await expect(form.locator('[name="source_author"]')).toHaveCount(0);

  await form.locator('[name="purpose"]').fill('Draft B');
  await card.getByRole('button', { name: 'Участники' }).click();
  await card.getByRole('button', { name: 'Данные организации' }).click();
  await expect(form.locator('[name="purpose"]')).toHaveValue('Draft B');
});

test('UX-FIX20-02 preserves named drafts across all management views', async ({ page }) => {
  const organization = withConnectedAssessment('Поток A');
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  const card = page.locator('[data-organization-id="3"]');
  const memberForm = card.locator('[data-action="add-member"]');
  await memberForm.locator('[name="email"]').fill('draft.member@example.test');
  await memberForm.locator('[name="full_name"]').fill('Черновик участника');
  await memberForm.locator('[name="role_description"]').fill('Черновик должности');
  await card.locator('input[name="invitation_email"]').check();

  await card.getByRole('button', { name: 'Данные организации' }).click();
  const earlyData = card.locator('[data-action="preview-early-data"]');
  await expect(earlyData.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(earlyData.locator('[name="assignment_ref"]')).toHaveValue('Поток A');
  await earlyData.locator('[name="purpose"]').fill('Несохранённая цель A');

  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  const questionnaire = card.locator('[data-action="preview-questionnaire"]');
  await expect(questionnaire.locator('[name="assignment_ref"]')).toHaveValue('Поток A');
  await expect(questionnaire.locator('[name="source_author"]')).toHaveCount(0);

  await card.getByRole('button', { name: 'Участники оценки' }).click();
  await expect(memberForm.locator('[name="email"]')).toHaveValue('draft.member@example.test');
  await expect(memberForm.locator('[name="full_name"]')).toHaveValue('Черновик участника');
  await expect(memberForm.locator('[name="role_description"]')).toHaveValue('Черновик должности');
  await expect(card.locator('input[name="invitation_email"]')).toBeChecked();

  await card.getByRole('button', { name: 'Данные организации' }).click();
  await expect(earlyData.locator('[name="assignment_ref"]')).toHaveValue('Поток A');
  await expect(earlyData.locator('[name="purpose"]')).toHaveValue('Несохранённая цель A');
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  await expect(questionnaire.locator('[name="source_author"]')).toHaveCount(0);

  const assignment = questionnaire.locator('[name="assignment_ref"]');
  await expect(assignment).toHaveAttribute('type', 'hidden');
  await expect(assignment).toHaveValue('Поток A');
  await card.getByRole('button', { name: 'Участники оценки' }).click();
  await card.getByRole('button', { name: 'Анкета', exact: true }).click();
  await expect(questionnaire.locator('[name="source_author"]')).toHaveCount(0);
  await expect(earlyData.locator('[name="purpose"]')).toHaveValue('Несохранённая цель A');
});

test('UX-FIX20-02 clears account A drafts and ignores its late preview after account B login', async ({ page }) => {
  let releasePreview;
  const previewReleased = new Promise((resolve) => { releasePreview = resolve; });
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }),
    withConnectedAssessment('Поток A'));
  await page.route('**/users/admin/organizations/3/questionnaire/preview', async (route) => {
    await previewReleased;
    return fulfillJson(route, {
      id: 91, assignment_ref: 'Поток A', status: 'ready_for_confirmation',
      channel: 'product_form', answers_json: { C02a: { participant_text: 'Секрет A' } },
      validation_json: { errors: [], missing: [] }, briefing: {},
    });
  });

  const cardA = page.locator('[data-organization-id="3"]');
  await cardA.getByRole('button', { name: 'Данные организации' }).click();
  const formA = cardA.locator('[data-action="preview-early-data"]');
  const valuesA = {
    assignment_ref: 'Поток A', source_author: 'Автор A', organization_name: 'Организация A',
    organization_type: 'Компания', industry: 'ИТ', activity_description: 'Описание A', purpose: 'Секрет A',
    results_usage: 'Развитие',
    case_reality_level: 'Близко к реальной работе', organization_name_usage_rules: 'Можно использовать настоящее название',
  };
  for (const [name, value] of Object.entries(valuesA).filter(([name]) => !['assignment_ref', 'source_author'].includes(name))) {
    await fillEarlyField(formA, name, value);
  }
  await formA.getByRole('button', { name: 'Подтвердить сведения' }).click();

  await page.evaluate(() => document.getElementById('admin-logout-button').click());
  await expect(page.locator('#auth-panel')).toBeVisible();
  await page.unroute('**/users/**');
  const userB = { id: 29, email: 'admin-b@example.test', full_name: 'Admin B' };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    if (pathname === '/users/auth/email/request-link') return fulfillJson(route, { email: userB.email, auth_mode: 'password' });
    if (pathname === '/users/auth/email/password-login') return fulfillJson(route, {
      exists: true, user: userB, is_admin: true,
      agent: { session_id: 'admin-b', message: '', stage: 'admin', completed: true },
      admin_dashboard: { metrics: [], insights: [], activity_series: [], competency_average: [] },
    });
    if (pathname === '/users/admin/organizations' && route.request().method() === 'GET') {
      return fulfillJson(route, { is_superadmin: false, items: [{ ...adminOrganization, name: 'Organization B' }] });
    }
    if (pathname === '/users/admin/organizations/3/questionnaire') return fulfillJson(route, { items: [] });
    if (pathname === '/users/session/logout') return fulfillJson(route, {});
    return fulfillJson(route, {}, 404);
  });
  await page.locator('#email-input').fill(userB.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  const cardB = page.locator('[data-organization-id="3"]');
  await cardB.getByRole('button', { name: 'Данные организации' }).click();
  const formB = cardB.locator('[data-action="preview-early-data"]');
  await expect(formB.locator('[name="purpose"]')).toHaveValue('');
  await expect(formB.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(formB.locator('[name="assignment_ref"]')).toHaveValue('competencies_4k');

  releasePreview();
  await page.waitForTimeout(100);
  await expect(formB.locator('[name="purpose"]')).toHaveValue('');
  await expect(cardB.locator('.admin-questionnaire-preview')).toHaveCount(0);
});

test('UX-FIX20-02 keeps newer input when an older preview response arrives', async ({ page }) => {
  let releasePreview;
  const previewReleased = new Promise((resolve) => { releasePreview = resolve; });
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }),
    withConnectedAssessment('Поток late'));
  await page.route('**/users/admin/organizations/3/questionnaire/preview', async (route) => {
    const submitted = route.request().postDataJSON();
    await previewReleased;
    return fulfillJson(route, {
      id: 92, assignment_ref: submitted.assignment_ref, status: 'ready_for_confirmation',
      channel: 'product_form', answers_json: submitted.answers,
      validation_json: { errors: [], missing: [] }, briefing: {},
    });
  });
  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации' }).click();
  const form = card.locator('[data-action="preview-early-data"]');
  const values = {
    assignment_ref: 'Поток late', source_author: 'Автор', organization_name: 'Организация',
    organization_type: 'Компания', industry: 'ИТ', activity_description: 'Описание', purpose: 'Старая цель',
    results_usage: 'Развитие',
    case_reality_level: 'Близко к реальной работе', organization_name_usage_rules: 'Можно использовать настоящее название',
  };
  await expect(form.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(form.locator('[name="assignment_ref"]')).toHaveValue(values.assignment_ref);
  for (const [name, value] of Object.entries(values).filter(([name]) => !['assignment_ref', 'source_author'].includes(name))) {
    await fillEarlyField(form, name, value);
  }
  await form.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await form.locator('[name="purpose"]').fill('Новая цель после отправки');
  releasePreview();
  const stalePreview = card.locator('.admin-questionnaire-preview');
  await expect(stalePreview).toBeVisible();
  await expect(form.locator('[name="purpose"]')).toHaveValue('Новая цель после отправки');
  await expect(stalePreview).toContainText('Форма изменилась после проверки');
  await expect(stalePreview.locator('[data-action="confirm-questionnaire"]')).toBeHidden();
});

test('ADM19-02 routes org-admin own assessment by server journey and preserves management capability', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  let profileReopens = 0;
  await page.route('**/users/18/session-bootstrap', (route) => fulfillJson(route, {
    user: adminUser, is_admin: true,
    dashboard: { current_assessments: [], completed_assessments: [] },
    admin_dashboard: { metrics: [], insights: [], activity_series: [], competency_average: [] },
  }));
  await page.route('**/users/18/journey-state', (route) => fulfillJson(route, {
    next_action: 'wait_for_acquaintance_data', profile: { status: 'incomplete' },
    onboarding: { status: 'not_started' }, assessment: { status: 'not_started' },
    acquaintance: { readiness: { status: 'waiting_for_assignment', message: 'Оценка пока не назначена. Обратитесь к уполномоченному назначающему.' } },
  }));
  await page.route('**/users/session/reopen-profile', (route) => { profileReopens += 1; return fulfillJson(route, {}, 500); });

  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации' }).click();
  await card.locator('[data-action="preview-early-data"] [name="purpose"]').fill('Черновик цели оценки');
  await page.getByRole('button', { name: 'Моя оценка' }).click();
  await expect(page.getByRole('heading', { name: 'Оценка пока не назначена' })).toBeVisible();
  await expect(page.locator('#admin-assessment-empty-panel')).toBeVisible();
  await expect(page.locator('#participant-area-navigation')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Моя оценка', exact: true }).filter({ visible: true })).toHaveCount(1);
  await expect(page.locator('#admin-assessment-empty-description')).toContainText('Вы можете назначить себе оценку');
  await expect(page.locator('#auth-complete-panel')).toBeHidden();
  await expect(page.getByRole('button', { name: 'Перейти к участникам и назначению' })).toBeVisible();
  expect(profileReopens).toBe(0);
  expect(await page.evaluate(() => localStorage.getItem('agent4k.canAdmin'))).toBe('1');

  await page.getByRole('button', { name: 'Перейти к участникам и назначению' }).click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  await expect(card.locator('[data-admin-view="people"]')).toBeVisible();
  await card.getByRole('button', { name: 'Данные организации' }).click();
  await expect(card.locator('[data-action="preview-early-data"] [name="purpose"]')).toHaveValue('Черновик цели оценки');
  await page.getByRole('button', { name: 'Моя оценка' }).click();
  await expect(page.getByRole('heading', { name: 'Оценка пока не назначена' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('heading', { name: 'Оценка пока не назначена' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Перейти к участникам и назначению' })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('agent4k.activeArea'))).toBe('assessment');

  await page.getByRole('button', { name: 'Перейти к участникам и назначению' }).click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('agent4k.activeArea'))).toBe('management');
  expect(await page.evaluate(() => localStorage.getItem('agent4k.isAdmin'))).toBe('1');

  await page.reload();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
  await page.goto(base + '/?screen=dashboard');
  await expect(page.getByRole('heading', { name: 'Оценка пока не назначена' })).toBeVisible();
});

test('ADM19-02 opens the own saved M8 report and returns to management', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  const ownDashboard = {
    greeting_name: 'Admin', current_assessments: [],
    completed_assessments: [{ cycle_id: 'cycle-own', report_id: 'report-own', title: 'Моя оценка 4К',
      organization_name: 'R03 Organization', status: 'report_ready', status_label: 'Результат готов',
      description: 'Результат доступен.', action: 'open_report', button_label: 'Посмотреть результат' }],
  };
  await page.route('**/users/18/session-bootstrap', (route) => fulfillJson(route, {
    user: adminUser, is_admin: true, dashboard: ownDashboard,
    admin_dashboard: { metrics: [], insights: [], activity_series: [], competency_average: [], is_superadmin: false },
  }));
  await page.route('**/users/18/journey-state', (route) => fulfillJson(route, {
    next_action: 'show_dashboard', profile: { status: 'complete' },
    onboarding: { status: 'completed' }, assessment: { status: 'report_ready' },
  }));
  await page.route('**/users/assessment/m8/reports/report-own', (route) => fulfillJson(route, {
    id: 'report-own', owner_user_id: 18, cycle_id: 'cycle-own', revision_no: 1,
    created_at: '2026-10-19T12:00:00Z', c67: {
      skills: [{ skill_id: 'K1.1', competency_id: 'K1', competency_name: 'Коммуникация',
        skill_name: 'Понимание собеседника', outcome: 'full_score',
        score: { value: 2, numerator: 2, denominator: 1 }, completeness: 'Полный состав' }],
      competencies: [{ competency_id: 'K1', competency_name: 'Коммуникация', skill_ids: ['K1.1'], score: null }],
      descriptive: { status: 'ready', summary: ['Сохранённый результат.'], claims: [] },
      coverage: {}, limitations: [], reliability: { status: 'not_verified' }, sessions: [], collection: {},
    },
  }));
  await page.route('**/users/assessment/m8/history', (route) => fulfillJson(route, { cycles: [] }));
  await page.route('**/users/assessment/m8/reports/report-own/comparison', (route) => fulfillJson(route, { mode: 'none', skills: [] }));

  await page.getByRole('button', { name: 'Моя оценка' }).click();
  await expect(page.getByRole('heading', { name: 'Мои оценки' })).toBeVisible();
  await page.locator('#completed-assessments').getByRole('button', { name: 'Открыть отчёт', exact: true }).click();
  await expect(page.locator('#m8-report-chart svg')).toBeVisible();
  await page.locator('#participant-return-management-button').click();
  await expect(page.locator('#admin-organizations-panel')).toBeVisible();
});

test('ADM19-01 saves early organization data through the versioned product form contract', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }),
    withConnectedAssessment('Поток октябрь 2026'));
  let submittedPayload;
  await page.route('**/users/admin/organizations/3/questionnaire/preview', async (route) => {
    submittedPayload = route.request().postDataJSON();
    return fulfillJson(route, {
      id: 12, assignment_ref: submittedPayload.assignment_ref, status: 'ready_for_confirmation',
      channel: 'product_form', answers_json: submittedPayload.answers,
      validation_json: { errors: [], missing: [] }, briefing: {},
    });
  });

  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации' }).click();
  const form = card.locator('[data-action="preview-early-data"]');
  const values = {
    assignment_ref: 'Поток октябрь 2026', source_author: 'Анна Петрова',
    organization_name: 'R03 Organization', organization_type: 'Компания', industry: 'ИТ',
    activity_description: 'Разрабатывает корпоративные продукты', purpose: 'Оценить управленческие навыки',
    results_usage: 'Для индивидуального развития',
    case_reality_level: 'Близко к реальной работе', organization_name_usage_rules: 'Можно использовать настоящее название',
  };
  await expect(form.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(form.locator('[name="assignment_ref"]')).toHaveValue(values.assignment_ref);
  for (const [name, value] of Object.entries(values).filter(([name]) => !['assignment_ref', 'source_author'].includes(name))) await fillEarlyField(form, name, value);
  await form.getByRole('button', { name: 'Подтвердить сведения' }).click();

  await expect.poll(() => submittedPayload?.assignment_ref).toBe(values.assignment_ref);
  expect(submittedPayload.channel).toBe('product_form');
  expect(submittedPayload.csv_text).toBeNull();
  expect(submittedPayload.answers.C01).toEqual({
    name: values.organization_name, organization_type: values.organization_type,
    industry: values.industry, activity_description: values.activity_description,
  });
  expect(submittedPayload.answers.C21).toBeUndefined();
  expect(submittedPayload.answers.C04).toBeUndefined();
  expect(submittedPayload.idempotency_key).toBeTruthy();
});

test('REMAIN-02 confirms content preview without recipient controls', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [{ status: 'queued' }] }), {
    ...withConnectedAssessment('Поток B'),
    admins: [{ user_id: 18, email: 'admin@example.test', full_name: 'Admin' }],
  });
  let revisionId = 100;
  await page.route('**/users/admin/organizations/3/questionnaire/preview', async (route) => {
    const payload = route.request().postDataJSON();
    revisionId += 1;
    return fulfillJson(route, {
      id: revisionId, assignment_ref: payload.assignment_ref, status: 'ready_for_confirmation',
      channel: payload.channel, answers_json: payload.answers, validation_json: { errors: [], missing: [] },
      participant_preview: {
        organization_name: payload.answers.C01.name,
        purpose: payload.answers.C02a.participant_text,
        results_usage: payload.answers.C03.participant_text,
        organizer: payload.answers.C21?.organizer || '',
      },
      changes: [{ field: 'purpose', before: 'Старая цель', after: payload.answers.C02a.participant_text }],
      is_first_publication: false,
    });
  });
  await page.route('**/users/admin/organizations/3/questionnaire/*/confirm', async (route) => {
    const card = page.locator('[data-organization-id="3"]');
    const purpose = await card.locator('[data-action="preview-early-data"] [name="purpose"]').inputValue();
    return fulfillJson(route, {
      id: revisionId, assignment_ref: 'Поток B', status: 'confirmed', channel: 'product_form',
      validation_json: { errors: [], missing: [] }, confirmed_at: '2026-10-21T10:00:00Z',
      answers_json: { C02a: { participant_text: purpose } }, participant_preview: { purpose }, changes: [],
    });
  });

  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации' }).click();
  const form = card.locator('[data-action="preview-early-data"]');
  const values = {
    assignment_ref: 'Поток B', source_author: 'Заказчик', organization_name: 'Организация B',
    organization_type: 'Компания', industry: 'ИТ', activity_description: 'Описание', purpose: 'Новая цель участника',
    results_usage: 'Для развития',
    case_reality_level: 'Близко к реальной работе', organization_name_usage_rules: 'Можно использовать настоящее название',
  };
  await expect(form.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(form.locator('[name="assignment_ref"]')).toHaveValue(values.assignment_ref);
  for (const [name, value] of Object.entries(values).filter(([name]) => !['assignment_ref', 'source_author'].includes(name))) await fillEarlyField(form, name, value);
  await form.getByRole('button', { name: 'Подтвердить сведения' }).click();
  const preview = card.locator('[data-admin-view="organization-data"] .admin-questionnaire-preview');
  const participantPreview = card.locator('[data-organization-participant-preview]');
  await expect(participantPreview).toContainText('Как увидит участник');
  await expect(participantPreview).toContainText('Новая цель участника');
  await expect(participantPreview).toContainText('Для развития');
  await expect(preview).toContainText('Подтвердите переименование организации');
  await expect(preview).not.toContainText('Получатели результатов');
  await expect(preview.locator('[name="questionnaire_recipient"]')).toHaveCount(0);
  await expect(preview.locator('[data-preview-stale]')).toBeHidden();
  await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeEnabled();
  await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await expect(preview).toHaveCount(0);
  await expect(card.locator('[data-admin-view="organization-data"] .admin-readiness-panel'))
    .toContainText('Готовность оценки · ещё не рассчитана');
  await expect(card.locator('[data-admin-view="organization-data"] .admin-readiness-panel')).not.toContainText('Поток B');
  await expect(form.locator('[name="purpose"]')).toHaveValue('Новая цель участника');

});

test('F22-04 keeps a newer confirmed revision and input entered after confirm started', async ({ page }) => {
  let releaseConfirm;
  const confirmReleased = new Promise((resolve) => { releaseConfirm = resolve; });
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }),
    withConnectedAssessment('Поток order'));
  await page.route('**/users/admin/organizations/3/questionnaire/preview', (route) => {
    const payload = route.request().postDataJSON();
    return fulfillJson(route, {
      id: 12, assignment_ref: payload.assignment_ref, status: 'ready_for_confirmation',
      channel: 'product_form', answers_json: payload.answers,
      validation_json: { errors: [], missing: [] }, participant_preview: { purpose: 'Older confirmed 12' },
      changes: [], recipient_options: ['participant'],
    });
  });
  await page.route('**/users/admin/organizations/3/questionnaire/*/confirm', async (route) => {
    await confirmReleased;
    return fulfillJson(route, {
      id: 12, assignment_ref: 'Поток order', status: 'confirmed', channel: 'product_form',
      confirmed_at: '2026-10-21T10:00:00Z', validation_json: { errors: [], missing: [] },
      answers_json: { C02a: { participant_text: 'Older confirmed 12' } },
    });
  });
  await page.route('**/users/admin/organizations/3/questionnaire', (route) => fulfillJson(route, {
    items: [{
      id: 13, assignment_ref: 'Поток order', status: 'confirmed', channel: 'product_form',
      effective_confirmed: { id: 13, assignment_ref: 'Поток order' },
      confirmed_at: '2026-10-21T10:01:00Z', validation_json: { errors: [], missing: [] },
      answers_json: { C02a: { participant_text: 'Newer confirmed 13' } },
      readiness: { early: { status: 'ready' }, context: { status: 'ready' }, roles: { status: 'incomplete' } },
    }],
  }));

  const card = page.locator('[data-organization-id="3"]');
  await card.getByRole('button', { name: 'Данные организации' }).click();
  const form = card.locator('[data-action="preview-early-data"]');
  const values = {
    assignment_ref: 'Поток order', source_author: 'Заказчик', organization_name: 'Организация',
    organization_type: 'Компания', industry: 'ИТ', activity_description: 'Описание', purpose: 'Older confirmed 12',
    results_usage: 'Развитие',
    case_reality_level: 'Близко к реальной работе', organization_name_usage_rules: 'Можно использовать настоящее название',
  };
  await expect(form.locator('[name="assignment_ref"]')).toHaveAttribute('type', 'hidden');
  await expect(form.locator('[name="assignment_ref"]')).toHaveValue(values.assignment_ref);
  for (const [name, value] of Object.entries(values).filter(([name]) => !['assignment_ref', 'source_author'].includes(name))) await fillEarlyField(form, name, value);
  await form.getByRole('button', { name: 'Подтвердить сведения' }).click();
  await card.locator('.admin-questionnaire-preview').getByRole('button', { name: 'Подтвердить сведения' }).click();
  await form.locator('[name="purpose"]').fill('Draft after confirm');
  await card.getByRole('button', { name: 'Участники' }).click();
  await card.getByRole('button', { name: 'Данные организации' }).click();
  releaseConfirm();

  await expect(form.locator('[name="purpose"]')).toHaveValue('Draft after confirm');
  await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('более новая серверная редакция');
});

test('ADM19-01 adds a participant with only email, name and role', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  let submittedPayload;
  await page.route('**/users/admin/organizations/3/members', async (route) => {
    submittedPayload = route.request().postDataJSON();
    return fulfillJson(route, { item: { email: submittedPayload.email } });
  });

  const form = page.locator('[data-organization-id="3"] [data-action="add-member"]');
  await form.locator('[name="email"]').fill('new.person@example.test');
  await form.locator('[name="full_name"]').fill('Новый Участник');
  await form.locator('[name="role_description"]').fill('Руководитель направления');
  await form.getByRole('button', { name: 'Добавить', exact: true }).click();

  await expect(page.locator('#admin-organizations-status')).toContainText('Участник привязан');
  expect(submittedPayload).toEqual({
    email: 'new.person@example.test', full_name: 'Новый Участник',
    role_description: 'Руководитель направления', job_instructions: null,
  });
});

test('UX-ADM27 org-admin assigns the selected assessment to self and a colleague', async ({ page }) => {
  const rolePackage = JSON.parse(await fs.readFile(path.join(root,
    'assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json'), 'utf8'));
  const organization = {
    ...adminOrganization,
    assessment_program: {
      program_definition_id: 7, program_name: 'Специалист 4К', program_version: '1.0',
      assignment_ref: 'competencies_4k', roles: [{ version_id: 92, code: 'specialist', name: 'Специалист' }],
      role_capabilities: rolePackage.base_roles.map((role) => ({
        version_id: role.code === 'specialist_expert' ? 92 : null,
        code: role.code, name: role.description.name, is_available: role.code === 'specialist_expert',
        unavailable_reason: role.code === 'specialist_expert' ? null : 'Недоступно в пилоте',
      })),
    },
    members_count: 2,
    members: [
      { ...adminOrganization.members[0], user_id: 18, email: adminUser.email, full_name: 'Admin',
        registration_status: 'registered', assessment_assignments: [] },
      { ...adminOrganization.members[0], user_id: 19, email: 'colleague@example.test', full_name: 'Colleague',
        assessment_assignments: [] },
    ],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization, {
    body: { items: [
      { id: 90, assignment_ref: 'same-visible-name-wrong-key', status: 'confirmed', channel: 'product_form',
        source_author: 'Чужой черновик', answers_json: { C02a: { participant_text: 'Не использовать' } } },
      { id: 91, assignment_ref: 'competencies_4k', status: 'confirmed', channel: 'product_form',
        effective_confirmed: { id: 91, assignment_ref: 'competencies_4k', confirmed_at: null },
        source_author: 'Точный автор', answers_json: { C02a: { participant_text: 'Точная цель' } } },
    ] },
  });
  let assignmentPayload;
  await page.route('**/users/admin/organizations/3/assessment-source-options', (route) =>
    fulfillJson(route, { configurations: [], roles: [] }));
  await page.route('**/users/admin/organizations/3/assessment-assignments', (route) => {
    assignmentPayload = route.request().postDataJSON();
    return fulfillJson(route, { items: assignmentPayload.user_ids.map((userId) => ({
      user_id: userId, status: 'assigned', assignment_id: userId + 100,
    })) });
  });
  await page.locator('input[name="invitation_email"]').nth(0).check();
  await page.locator('input[name="invitation_email"]').nth(1).check();
  const roleOptions = page.locator('[name="role_profile_version_id"] option');
  await expect(roleOptions).toHaveCount(7);
  expect(organization.assessment_program.role_capabilities.map((role) => role.code))
    .toEqual(rolePackage.base_roles.map((role) => role.code));
  for (const role of rolePackage.base_roles) {
    const option = roleOptions.filter({ hasText: role.description.name });
    await expect(option).toHaveCount(1);
    if (role.code === 'specialist_expert') {
      await expect(option).toBeEnabled();
      await expect(option).toHaveAttribute('value', '92');
    } else {
      await expect(option).toHaveAttribute('disabled', '');
      await expect(option).toHaveAttribute('value', '');
      await expect(option).toContainText('Недоступно в пилоте');
    }
  }
  await expect(page.locator('[name="role_profile_version_id"]')).toHaveValue('92');
  await page.getByRole('button', { name: 'Данные организации', exact: true }).click();
  await page.locator('.admin-data-readiness summary').press('Enter');
  const assessmentIdentity = page.locator('.admin-data-readiness .admin-assessment-identity');
  await expect(assessmentIdentity).toContainText('Специалист 4К');
  await expect(assessmentIdentity).toContainText('Версия программы');
  await expect(assessmentIdentity).toContainText('1.0');
  await expect(assessmentIdentity).not.toContainText('Ключ оценки');
  await expect(assessmentIdentity).not.toContainText('competencies_4k');
  const boundAssignment = page.locator('[data-action="preview-early-data"] [name="assignment_ref"]');
  await expect(boundAssignment).toHaveAttribute('type', 'hidden');
  await expect(boundAssignment).toHaveValue('competencies_4k');
  await expect(page.locator('[data-action="preview-early-data"] [name="source_author"]')).toHaveCount(0);
  await expect(page.locator('[data-action="preview-early-data"] [name="purpose"]')).toHaveValue('Точная цель');
  await page.getByRole('button', { name: 'Участники оценки', exact: true }).click();
  await page.locator('form[data-action="assign-member-assessment"] button[type="submit"]').click();
  await expect.poll(() => assignmentPayload).toBeTruthy();
  await expect(page.locator('#admin-organizations-status')).toContainText('Admin: оценка назначена');
  await expect(page.locator('#admin-organizations-status')).toContainText('Colleague: оценка назначена');
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.admin-organization-head')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  expect(assignmentPayload.assignment_ref).toBe('competencies_4k');
  expect(assignmentPayload.role_profile_version_id).toBe(92);
  expect(assignmentPayload.user_ids.sort()).toEqual([18, 19]);
});

test('PILOT31-03 explains every visible readiness blocker before assignment', async ({ page }) => {
  await openAdminOrganizations(
    page,
    (route) => fulfillJson(route, { items: [] }),
    { ...adminOrganization, assessment_program: null },
    { body: { items: [{ id: 12, assignment_ref: 'other-assessment', status: 'draft' }] } },
  );

  const readiness = page.locator('.admin-assignment-readiness');
  await expect(readiness).toBeVisible();
  await expect(readiness).toContainText('Программа оценки не подключена');
  await expect(readiness).toContainText('Обратитесь к суперадминистратору');
  await expect(readiness).not.toContainText('Анкета для выбранной оценки не подтверждена');
  await expect(readiness).not.toContainText('Оценка не выбрана');
  await expect(readiness.locator('dt:text-is("Роль в оценке") + dd')).toHaveText('ещё не проверена для программы');
  await expect(readiness.locator('dt:text-is("Анкета") + dd')).toHaveText('ещё не проверена для программы');
  await expect(page.locator('[data-bulk-actions]')).toBeHidden();
  await page.locator('input[name="invitation_email"]').check();
  await expect(page.locator('[data-bulk-actions]')).toBeVisible();
  await expect(page.locator('form[data-action="assign-member-assessment"] button[type="submit"]')).toBeDisabled();
});

test('AC18-ADM-1B rejects an incomplete invitation batch instead of reporting zero success', async ({ page }) => {
  const organization = {
    ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Пилот 4К · 9 кейсов',
      program_version: '1.2', assignment_ref: 'specialist-pilot',
      roles: [{ version_id: 92, code: 'specialist_expert', name: 'Специалист' }] },
    members_count: 2,
    members: [
      { ...adminOrganization.members[0], user_id: 8, email: 'first@example.test', full_name: 'Первый участник' },
      { ...adminOrganization.members[0], user_id: 9, email: 'second@example.test', full_name: 'Второй участник' },
    ],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, {
    items: [{ email: 'first@example.test', status: 'accepted' }],
  }), organization, { body: { items: [{ id: 11, assignment_ref: 'specialist-pilot',
    status: 'confirmed', channel: 'product_form', validation_json: {},
    effective_confirmed: { id: 11, assignment_ref: 'specialist-pilot', confirmed_at: null } }] } });
  await page.locator('input[name="invitation_email"]').nth(0).check();
  await page.locator('input[name="invitation_email"]').nth(1).check();
  await page.getByRole('button', { name: 'Отправить приглашения' }).click();
  await expect(page.locator('#admin-organizations-status')).toContainText('Приняты сервисом: 1. Не отправлены: 0. Исход уточняется: 1');
  await expect(page.locator('[data-action="recover-member-invitation"]').first()).toBeVisible();
  await expect(page.locator('#admin-organizations-status')).not.toContainText('принял приглашения: 0');
});

test('R03 reports an unconfigured invitation provider as a known failure', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, { detail: 'EMAIL_PROVIDER_NOT_CONFIGURED' }, 503));
  await page.locator('input[name="invitation_email"]').check();
  await page.getByRole('button', { name: 'Отправить приглашения' }).click();
  await expect(page.locator('.admin-invitation-common')).toContainText('сервис отправки не настроен');
  await expect(page.locator('#admin-organizations-status')).toContainText('Не отправлены: 1');
  await expect(page.locator('.admin-invitation-recovery')).toHaveCount(0);
});

test('AC18-ADM-1C confirms a lost assignment response only by exact operation receipt', async ({ page }) => {
  const member = { ...adminOrganization.members[0], user_id: 8, email: 'person@example.test',
    full_name: 'Участник чтения', assessment_assignments: [] };
  const organization = {
    ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Пилот 4К · 9 кейсов',
      program_version: '1.2', assignment_ref: 'specialist-pilot',
      roles: [{ version_id: 92, code: 'specialist_expert', name: 'Специалист' }],
      role_capabilities: [{ version_id: 92, code: 'specialist_expert', name: 'Специалист', is_available: true }] },
    members: [member],
  };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization,
    { body: { items: [{ id: 11, assignment_ref: 'specialist-pilot', status: 'confirmed',
      channel: 'product_form', validation_json: {},
      effective_confirmed: { id: 11, assignment_ref: 'specialist-pilot', confirmed_at: null } }] } });
  await page.route('**/users/admin/organizations/3/assessment-assignments', (route) => route.abort('failed'));
  await page.route('**/users/admin/organizations/3/assessment-assignments/operations/**', (route) =>
    fulfillJson(route, { items: [{ user_id: 8, status: 'already_assigned', assignment_id: 41 }] }));
  await page.locator('input[name="invitation_email"]').check();
  await page.locator('form[data-action="assign-member-assessment"] button[type="submit"]').click();
  await expect(page.locator('#admin-organizations-status')).toContainText('назначение подтверждено точным чтением операции');
});

test('AC18-ADM-1C does not accept stale assignment state when exact receipt is absent', async ({ page }) => {
  const organization = { ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Пилот 4К · 9 кейсов',
      program_version: '1.2', assignment_ref: 'specialist-pilot',
      roles: [{ version_id: 92, code: 'specialist_expert', name: 'Специалист' }],
      role_capabilities: [{ version_id: 92, code: 'specialist_expert', name: 'Специалист', is_available: true }] },
    members: [{ ...adminOrganization.members[0], user_id: 8, assessment_assignments: ['specialist-pilot'] }] };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization,
    { body: { items: [{ id: 11, assignment_ref: 'specialist-pilot', status: 'confirmed',
      channel: 'product_form', validation_json: {},
      effective_confirmed: { id: 11, assignment_ref: 'specialist-pilot', confirmed_at: null } }] } });
  await page.route('**/users/admin/organizations/3/assessment-assignments', (route) => route.abort('failed'));
  await page.route('**/users/admin/organizations/3/assessment-assignments/operations/**', (route) =>
    fulfillJson(route, { detail: 'ASSIGNMENT_OPERATION_NOT_FOUND' }, 404));
  await page.locator('input[name="invitation_email"]').check();
  await page.locator('form[data-action="assign-member-assessment"] button[type="submit"]').click();
  await expect(page.locator('#admin-organizations-status')).toContainText('Итог назначения пока неизвестен');
  await expect(page.locator('#admin-organizations-status')).not.toContainText('подтверждено');
  await expect(page.locator('#admin-organizations-status')).not.toContainText('operation_id');
});

test('AC18-ADM-1C keeps a confirmed assignment when the following refresh fails', async ({ page }) => {
  let organizationReads = 0;
  const organization = { ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Пилот 4К · 9 кейсов',
      program_version: '1.2', assignment_ref: 'specialist-pilot',
      roles: [{ version_id: 92, code: 'specialist_expert', name: 'Специалист' }],
      role_capabilities: [{ version_id: 92, code: 'specialist_expert', name: 'Специалист', is_available: true }] } };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization,
    { body: { items: [{ id: 11, assignment_ref: 'specialist-pilot', status: 'confirmed',
      channel: 'product_form', validation_json: {},
      effective_confirmed: { id: 11, assignment_ref: 'specialist-pilot', confirmed_at: null } }] } });
  await page.route('**/users/admin/organizations', (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    organizationReads += 1;
    return fulfillJson(route, { detail: 'Synthetic refresh failure' }, 503);
  });
  await page.route('**/users/admin/organizations/3/assessment-assignments', (route) =>
    fulfillJson(route, { items: [{ user_id: 8, status: 'assigned', assignment_id: 42 }] }));
  await page.locator('input[name="invitation_email"]').check();
  await page.locator('form[data-action="assign-member-assessment"] button[type="submit"]').click();
  await expect(page.locator('#admin-organizations-status')).toContainText('оценка назначена');
  await expect(page.locator('#admin-organizations-status')).toContainText('данные могут быть устаревшими');
  expect(organizationReads).toBeGreaterThan(0);
});

test('AC18-ADM-1C shows queued invitation outcome per person without provider counters', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, {
    items: [{ email: 'person@example.test', status: 'queued', invitation_id: 1 }],
  }));
  await page.locator('input[name="invitation_email"]').check();
  await page.getByRole('button', { name: 'Отправить приглашения' }).click();
  await expect(page.locator('.admin-organization-member-invitation')).toContainText('Приглашение подготовлено. Отправка ещё не подтверждена');
  await expect(page.locator('#admin-organizations-status')).toContainText('Приняты сервисом: 0. Не отправлены: 0. Исход уточняется: 1');
  await expect(page.locator('#admin-organizations-status')).not.toContainText('Принято провайдером');
});

test('AC18-ADM-1C reads back an unknown invitation and hides the operation key', async ({ page }) => {
  await openAdminOrganizations(page, (route) => {
    if (route.request().method() === 'POST') return route.abort('failed');
    return fulfillJson(route, { items: [{ email: 'person@example.test', status: 'queued', invitation_id: 1 }] });
  });
  await page.locator('input[name="invitation_email"]').check();
  await page.getByRole('button', { name: 'Отправить приглашения' }).click();
  await expect(page.locator('.admin-organization-member-invitation')).toContainText('Приглашение подготовлено. Отправка ещё не подтверждена');
  await expect(page.locator('#admin-organizations-status')).toContainText('Приняты сервисом: 0. Не отправлены: 0. Исход уточняется: 1');
  await expect(page.locator('#admin-organizations-status')).not.toContainText('operation_id');
});

test('AC18-ADM-1C shows factual invitation lifetime and read-only processing details', async ({ page }) => {
  const organization = { ...adminOrganization,
    assessment_program: { program_definition_id: 7, program_name: 'Пилот 4К · 9 кейсов',
      program_version: '1.2', assignment_ref: 'specialist-pilot', roles: [] },
    members: [{ ...adminOrganization.members[0], invitation_created_at: '2026-11-08T09:00:00Z',
      invitation_expires_at: '2026-11-10T12:30:00Z', invitation_used_at: '2026-11-09T10:15:00Z',
      invitation_link_status: 'used', invitation_status: 'used', assessment_assignments: ['specialist-pilot'],
      assessment_history: [
        { assignment_id: 42, assignment_ref: 'specialist-pilot', assignment_status: 'active',
          assignment_created_at: '2026-11-09T11:00:00Z', cycle_id: 'cycle-current', cycle_status: 'calculation_pending' },
        { assignment_id: 41, assignment_ref: 'specialist-pilot', assignment_status: 'revoked',
          assignment_created_at: '2026-11-08T08:00:00Z', assignment_revoked_at: '2026-11-08T12:00:00Z' },
      ],
      assessment_stages: { 'specialist-pilot': { code: 'processing', action: 'open_processing',
        description: 'Прохождение завершено; формируется отчёт.' } } }] };
  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }), organization);
  await expect(page.locator('.admin-organization-member')).not.toContainText('72 часа');
  await page.getByRole('button', { name: 'Person' }).click();
  await expect(page.locator('.admin-member-card-dialog [data-card-invitation-history]')).toHaveCount(0);
  await expect(page.locator('[data-card-assignment-history]')).toBeHidden();
  await page.locator('.admin-member-history > summary').click();
  await expect(page.locator('[data-card-assignment-history]')).toBeVisible();
  await expect(page.locator('[data-card-assignment-history]')).toContainText('Назначение #42: назначено');
  await expect(page.locator('[data-card-assignment-history]')).toContainText('Cycle cycle-current');
  await expect(page.locator('[data-card-assignment-history]')).toContainText('Назначение #41: отменено');
  await page.locator('.admin-member-card-dialog').getByRole('button', { name: 'Закрыть', exact: true }).click();
  await page.getByRole('button', { name: 'Подробнее об обработке' }).click();
  await expect(page.getByRole('heading', { name: 'Обработка результата' })).toBeVisible();
  await expect(page.locator('.admin-member-card-dialog')).toContainText('Отчёт можно открыть только после готовности');
});

test('QA19-02 resolves palette tokens in visible auth and admin states', async ({ page }) => {
  await baseRoutes(page);
  await page.goto(base);

  const palette = await page.evaluate(() => {
    const styles = getComputedStyle(document.documentElement);
    return {
      cyan: styles.getPropertyValue('--palette-cyan-500').trim(),
      coral: styles.getPropertyValue('--palette-coral-500').trim(),
      graphiteBorder: styles.getPropertyValue('--palette-graphite-200').trim(),
      retiredCyan: styles.getPropertyValue('--palette-cyan-600').trim(),
      retiredCoral: styles.getPropertyValue('--palette-coral-600').trim(),
      retiredGraphite: styles.getPropertyValue('--palette-graphite-100').trim(),
    };
  });
  expect(palette).toEqual({
    cyan: '#18b8c6', coral: '#ff563d', graphiteBorder: '#d6e2e5',
    retiredCyan: '', retiredCoral: '', retiredGraphite: '',
  });

  await page.locator('#email-input').focus();
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Tab');
  await expect(page.locator('#email-input')).toBeFocused();
  await expect(page.locator('#email-input')).toHaveCSS('border-color', 'rgb(34, 44, 48)');
  await expect(page.locator('#email-input')).not.toHaveCSS('box-shadow', 'none');
  await page.keyboard.press('Tab');
  await expect(page.locator('#request-magic-link-button')).toBeFocused();
  await expect(page.locator('#request-magic-link-button')).not.toHaveCSS('outline-style', 'none');
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1366, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    const focusBounds = await page.locator('#request-magic-link-button').boundingBox();
    expect(focusBounds.x).toBeGreaterThanOrEqual(3);
    expect(focusBounds.x + focusBounds.width).toBeLessThanOrEqual(width - 3);
    const layout = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(layout.scrollWidth).toBe(layout.clientWidth);
  }

  await openAdminOrganizations(page, (route) => fulfillJson(route, { items: [] }));
  const card = page.locator('[data-organization-id="3"]');
  await expect(card.locator('.primary-button').first()).toHaveCSS('background-color', 'rgb(34, 44, 48)');
  await expect(card.locator('.admin-organization-head')).toHaveCSS('border-color', 'rgb(214, 226, 229)');
});

test('R03 personal invitation has priority and exposes an explicit account choice', async ({ page }) => {
  await baseRoutes(page, {
    authenticated: true,
    user: { id: 9, email: 'other@example.test', full_name: 'Other' },
  });
  await page.route('**/users/organization-invitations/personal-r03', (route) => fulfillJson(route, {
    organization_id: 3,
    organization_name: 'Organization A',
    recipient_email: 'person@example.test',
    personal: true,
    auth_mode: 'password_registration',
  }));

  await page.goto(`${base}/?invite=personal-r03`);

  await expect(page.locator('#auth-panel')).toBeVisible();
  await expect(page.locator('#auth-token-form')).toBeVisible();
  await expect(page.locator('#auth-email-form')).toBeHidden();
  await expect(page.locator('#organization-invitation-account-conflict')).toContainText('other@example.test');
  await expect(page.locator('#organization-invitation-account-conflict')).toContainText('person@example.test');
});

test('R03 verification pending renders one mail-check heading without password copy', async ({ page }) => {
  await baseRoutes(page);
  await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, {
    email: 'person@example.test', auth_mode: 'verification_pending', message: 'Проверьте почту.',
    retry_after_seconds: 7,
  }));
  await page.goto(base);
  await page.locator('#email-input').fill('person@example.test');
  await page.locator('#request-magic-link-button').click();
  await expect(page.locator('#auth-title')).toBeHidden();
  await expect(page.locator('#auth-subtitle')).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Проверьте почту' })).toBeVisible();
  await expect(page.getByText('С возвращением', { exact: true })).toBeHidden();
  await expect(page.getByText(/Введите пароль для/)).toBeHidden();
  await expect(page.locator('#auth-resend-email-button')).toHaveText('Отправить повторно');
  await expect(page.locator('#auth-resend-countdown')).toContainText('доступна через');
  await expect(page.locator('#auth-resend-email-button')).toBeDisabled();
  const mailHeading = await page.getByRole('heading', { name: 'Проверьте почту' }).evaluate((node) => {
    const style = getComputedStyle(node);
    return { fontSize: style.fontSize, fontWeight: style.fontWeight, lineHeight: style.lineHeight };
  });
  expect(mailHeading).toEqual({ fontSize: '24px', fontWeight: '700', lineHeight: '32px' });
  await expect(page.locator('.auth-email-sent-icon')).toHaveCSS('background-image', /auth-email-outline\.svg/);
  await expect(page.locator('#auth-change-email-button')).toHaveCSS('border-top-width', '0px');
  const changeEmail = await page.locator('#auth-change-email-button').boundingBox();
  const resend = await page.locator('#auth-resend-email-button').boundingBox();
  expect(changeEmail.width).toBeLessThan(resend.width);
  await page.locator('#auth-change-email-button').click();
  await expect(page.locator('#auth-title')).toBeVisible();
  await expect(page.locator('#auth-title')).toHaveText('Добро пожаловать');
});

test('R03 reset returns to AUTH 03 with known email and no autologin', async ({ page }) => {
  await baseRoutes(page);
  await page.route('**/users/auth/password/reset/validate', (route) => fulfillJson(route, {
    email: 'person@example.test', auth_mode: 'password_reset', message: 'Задайте новый пароль.',
  }));
  let loginRequests = 0;
  await page.route('**/users/auth/password/reset', (route) => fulfillJson(route, {
    email: 'person@example.test', message: 'Пароль изменён',
  }));
  await page.route('**/users/auth/email/password-login', (route) => {
    loginRequests += 1;
    return fulfillJson(route, {}, 500);
  });

  await page.goto(`${base}/?auth_action=password_reset&token=reset-r03`);
  await page.locator('#magic-token-input').fill('ValidPass1!');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#auth-title')).toHaveText('Подтвердите новый пароль');
  await page.locator('#magic-token-input').fill('ValidPass1!');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.getByText('Пароль изменён', { exact: true })).toBeVisible();
  await page.locator('#auth-change-email-button').click();

  await expect(page.locator('#auth-title')).toHaveText('С возвращением');
  await expect(page.locator('#auth-token-form')).toBeVisible();
  await expect(page.locator('#auth-credential-email-input')).toHaveValue('person@example.test');
  expect(loginRequests).toBe(0);
});

test('R03 mutating auth locks the complete step', async ({ page }) => {
  await baseRoutes(page);
  await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, {
    email: 'person@example.test', auth_mode: 'password', message: 'Введите пароль.',
  }));
  let finishLogin;
  await page.route('**/users/auth/email/password-login', (route) => {
    finishLogin = () => fulfillJson(route, {
      exists: true,
      user: { id: 3, email: 'person@example.test', full_name: 'Person' },
      is_admin: false,
      agent: { session_id: 'session', message: '', stage: 'profile', completed: false },
      dashboard: {},
    });
  });

  await page.goto(base);
  await page.locator('#email-input').fill('person@example.test');
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();

  await expect(page.locator('#magic-token-input')).toBeDisabled();
  await expect(page.locator('#auth-password-toggle-button')).toBeDisabled();
  await expect(page.locator('#auth-change-credential-email-button')).toBeDisabled();
  finishLogin();
});

test('R03 tooltip toggles on tap and stays inside a low viewport', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 320, height: 480 }, hasTouch: true });
  const page = await context.newPage();
  await baseRoutes(page);
  await page.route('**/users/auth/email/confirm', (route) => fulfillJson(route, {
    email: 'person@example.test', auth_mode: 'password_registration', message: 'Создайте пароль.',
  }));
  await page.goto(`${base}/?auth_action=email_verification&token=verify-r03`);
  const trigger = page.locator('#auth-password-requirements-trigger');
  const popover = page.locator('#auth-password-requirements-popover');

  await trigger.tap();
  await expect(popover).toBeVisible();
  const box = await popover.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(320);
  expect(box.y + box.height).toBeLessThanOrEqual(480);
  await trigger.tap();
  await expect(popover).toBeHidden();
  await context.close();
});

test('R03 AUTH 01 and password creation keep canonical R01 metrics', async ({ page }) => {
  await baseRoutes(page);
  await page.goto(base);
  const emailCard = await page.locator('#auth-panel').boundingBox();
  expect(Math.round(emailCard.width)).toBe(474);
  const accessibleEmailLabel = page.locator('#auth-email-form .field > span');
  await expect(accessibleEmailLabel).toHaveClass(/sr-only/);
  const labelBox = await accessibleEmailLabel.boundingBox();
  expect(labelBox.width).toBeLessThanOrEqual(1);
  expect(labelBox.height).toBeLessThanOrEqual(1);
  await expect(page.locator('#forgot-password-button')).toBeHidden();

  await page.route('**/users/auth/email/confirm', (route) => fulfillJson(route, {
    email: 'person@example.test', auth_mode: 'password_registration', message: 'Создайте пароль.',
  }));
  await page.goto(`${base}/?auth_action=email_verification&token=verify-r03`);
  const createCard = await page.locator('#auth-panel').boundingBox();
  const createTitle = await page.locator('#auth-title').boundingBox();
  const passwordField = await page.locator('#magic-token-input').boundingBox();
  expect(Math.round(createCard.width)).toBe(502);
  expect(Math.round(createCard.height)).toBe(547);
  expect(Math.round(passwordField.height)).toBe(49);
  expect(Math.round(createTitle.y - createCard.y)).toBe(78);
  expect(Math.round(passwordField.y - createCard.y)).toBe(190);
  await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 1 из 2');
  await expect(page.locator('#auth-password-generate-button')).toHaveCSS('font-weight', '400');
  const eyeImage = await page.locator('#auth-password-toggle-button').evaluate(
    (button) => getComputedStyle(button, '::after').backgroundImage,
  );
  expect(eyeImage).toMatch(/auth-eye\.svg/);
});

test('R04 shared footer stays in document flow and stacks on mobile', async ({ page }) => {
  await baseRoutes(page);
  await page.goto(base);
  const footer = page.locator('.app-footer');
  await expect(footer).toBeVisible();
  await expect(footer.getByText('Политика конфиденциальности')).toBeVisible();
  await expect(footer.getByText('Согласие на обработку персональных данных')).toBeVisible();
  await expect(footer.getByText('© 2026 LIDUM')).toBeVisible();
  await expect(footer.locator('a')).toHaveCount(0);
  await expect(footer).toHaveCSS('position', 'static');
  await page.setViewportSize({ width: 360, height: 760 });
  await expect(page.locator('#email-input')).toHaveCSS('font-size', '16px');
  await expect(page.locator('.app-footer-documents')).toHaveCSS('flex-direction', 'column');
  const layout = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(layout.scrollWidth).toBe(layout.clientWidth);
});

test('REL-VERSION-01 shows one build number on auth and common areas, with a safe fallback', async ({ page }) => {
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/version') return fulfillJson(route, { version: '2.0.7' });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await expect(page.locator('.auth-header-brand')).toHaveText('4К Ассистент');
  await expect(page.locator('.auth-header-brand')).toBeVisible();
  await expect(page.locator('.auth-release-badge')).toHaveText(`Релиз ${appRelease}`);
  await expect(page.locator('.app-footer-release')).toBeHidden();
  await page.setViewportSize({ width: 360, height: 760 });
  await expect(page.locator('.auth-release-badge')).toBeInViewport();
  await page.locator('#auth-panel').evaluate((panel) => panel.classList.add('hidden'));
  await page.locator('#auth-complete-panel').evaluate((panel) => panel.classList.remove('hidden'));
  await expect(page.locator('.app-footer-release')).toHaveText(`Версия ${appRelease}`);
  await expect(page.locator('.app-footer-release')).toBeVisible();
  await page.locator('#auth-complete-panel').evaluate((panel) => panel.classList.add('hidden'));
  await page.locator('#chat-panel').evaluate((panel) => panel.classList.remove('hidden'));
  await expect(page.locator('.app-footer')).toBeHidden();
});

test('R03 refresh obeys server journey and fails closed on journey outage', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  const auth = {
    exists: true, user, is_admin: false,
    agent: { session_id: 'profile-session', message: 'Продолжим', stage: 'profile', completed: false },
    dashboard: {
      active_assessment: { code: 'competencies_4k', title: 'Компетенции 4К', description: 'Тест', completed_cases: 0, progress_percent: 0, status_label: 'Не начато', button_label: 'Начать' },
      available_assessments: [], reports: [],
    },
  };
  let journey = { next_action: 'show_dashboard', profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'report_ready' } };
  let journeyStatus = 200;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, ...auth });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, auth);
    if (pathname === '/users/8/journey-state') return fulfillJson(route, journeyStatus === 200 ? journey : { detail: 'controlled outage' }, journeyStatus);
    if (pathname === '/users/session/reopen-profile') return fulfillJson(route, auth);
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await expect(page.locator('#dashboard-panel')).toBeVisible();

  journeyStatus = 503;
  await page.reload();
  await expect(page.locator('#chat-panel')).toBeHidden();
  await expect(page.locator('#auth-error')).toContainText('Не удалось определить актуальный этап');
});

test('R03 successful password response reports a missing browser session as auth failure', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/auth/email/request-link') return fulfillJson(route, {
      email: user.email, auth_mode: 'password', message: 'Введите пароль.',
    });
    if (pathname === '/users/auth/email/password-login') return fulfillJson(route, {
      exists: true, user, is_admin: false,
      agent: { session_id: 'profile-session', message: '', stage: 'profile', completed: false },
      dashboard: {},
    });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { detail: 'Session not found' }, 401);
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#email-input').fill(user.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#auth-error')).toContainText('Сессия входа не сохранилась');
  await expect(page.locator('#auth-error')).not.toContainText('актуальный этап');
});

test('LK01 renders selected Cycle cards without catalogue or horizontal overflow', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person', job_description: 'Product Lead' };
  const dashboard = {
    greeting_name: 'Person', profile_readiness: 'ready', personalized_profile_id: 11,
    active_assessment: { code: 'competencies_4k', title: 'Legacy', description: '', completed_cases: 0,
      total_cases: 0, progress_percent: 0, status_label: '', button_label: '' },
    available_assessments: [], reports: [], reports_total: 1,
    current_assessments: [{ cycle_id: 'cycle-current', title: 'Оценка руководителей',
      organization_name: 'Организация с очень длинным названием для проверки переноса строки',
      status: 'active', status_label: 'Оценка начата', description: 'Продолжите с того же места.',
      action: 'continue', button_label: 'Продолжить', completed_cases: 0, completed_positions: 0, total_cases: 4, planned_total: 4, current_position_no: 1,
      calendar_deadline: '2026-10-19T15:30:00Z' }],
    completed_assessments: [{ cycle_id: 'cycle-ready', report_id: 'report-ready', title: 'Оценка 4К',
      organization_name: 'Организация', status: 'report_ready', status_label: 'Результат готов',
      closed_at: '2026-10-17T12:00:00Z',
      description: 'Результат оценки доступен для просмотра.', action: 'open_report',
      button_label: 'Посмотреть результат', completed_cases: 4, total_cases: 4 }],
  };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'lk01-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'show_dashboard', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-current' },
    });
    return fulfillJson(route, {}, 404);
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(base);
  await expect(page.getByRole('heading', { name: 'Мои оценки' })).toBeVisible();
  await expect(page.getByText('1 ситуация из 4')).toBeVisible();
  await expect(page.locator('#current-assessments dl')).toContainText('Текущая ситуация');
  await expect(page.locator('#current-assessments')).toContainText('19 октября 2026, 18:30 МСК');
  await expect(page.locator('#current-assessments').getByRole('progressbar')).toHaveJSProperty('value', 0);
  await expect(page.locator('#completed-assessments')).toContainText('17 октября 2026');
  await expect(page.getByRole('button', { name: 'Продолжить' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Открыть отчёт' })).toBeVisible();
  await expect(page.getByText('Скоро')).toHaveCount(0);
  const desktopCard = await page.locator('.participant-assessment-card').first().boundingBox();
  const desktopButton = await page.getByRole('button', { name: 'Продолжить' }).boundingBox();
  expect(Math.abs(desktopCard.y - desktopButton.y)).toBeLessThan(desktopCard.height);
  await page.setViewportSize({ width: 360, height: 760 });
  const mobileCard = await page.locator('.participant-assessment-card').first().boundingBox();
  const mobileButton = await page.getByRole('button', { name: 'Продолжить' }).boundingBox();
  expect(mobileCard.width - mobileButton.width).toBeLessThanOrEqual(36);
  const layout = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(layout.scrollWidth).toBe(layout.clientWidth);
});

test('RAD01 renders saved scores, gaps and mobile competency view', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person', job_description: 'Product Lead' };
  const dashboard = {
    greeting_name: 'Person', profile_readiness: 'ready', personalized_profile_id: 11,
    active_assessment: null, available_assessments: [], reports: [], reports_total: 1,
    current_assessments: [],
    completed_assessments: [{ cycle_id: 'cycle-rad01', report_id: 'report-rad01', title: 'Оценка 4К',
      organization_name: 'Организация', status: 'report_ready', status_label: 'Результат готов',
      description: 'Результат доступен.', action: 'open_report', button_label: 'Посмотреть результат' }],
  };
  const skills = [
    { skill_id: 'K1.1', competency_id: 'K1', competency_name: 'Коммуникация', skill_name: 'Понимание собеседника', outcome: 'full_score', score: { value: 0, numerator: 0, denominator: 1 }, completeness: 'Полный состав' },
    { skill_id: 'K1.2', competency_id: 'K1', competency_name: 'Коммуникация', skill_name: 'Ясность сообщения', outcome: 'partial_score', score: { value: 2.25, numerator: 9, denominator: 4 }, completeness: 'Часть состава' },
    { skill_id: 'K1.3', competency_id: 'K1', competency_name: 'Коммуникация', skill_name: 'Обратная связь', outcome: 'no_result', completeness: 'Недостаточно оснований' },
    { skill_id: 'K2.1', competency_id: 'K2', competency_name: 'Командная работа', skill_name: 'Сотрудничество', outcome: 'result_without_score', completeness: 'Наблюдения сохранены' },
  ];
  const report = { id: 'report-rad01', owner_user_id: 8, cycle_id: 'cycle-rad01', revision_no: 1, created_at: '2026-10-17T12:00:00Z', c67: {
    skills, competencies: [
      { competency_id: 'K1', competency_name: 'Коммуникация', skill_ids: ['K1.1', 'K1.2', 'K1.3'], score: null },
      { competency_id: 'K2', competency_name: 'Командная работа', skill_ids: ['K2.1'], score: null },
    ], descriptive: { status: 'ready', summary: ['Сохранённый результат.'], claims: [] },
    coverage: {}, limitations: [], reliability: { status: 'not_verified' }, sessions: [], collection: {},
  } };
  const comparison = {
    mode: 'mixed',
    current: { cycle_id: 'cycle-rad01', report_id: 'report-rad01', report_revision_no: 1, results_revision_id: 'rr2', program_name: 'Программа сейчас', created_at: '2026-10-17T12:00:00Z', closed_at: '2026-10-17T11:00:00Z', role_ref: { name: 'Product Lead' } },
    previous: { cycle_id: 'cycle-previous', report_id: 'report-previous', report_revision_no: 1, results_revision_id: 'rr1', program_name: 'Программа ранее', created_at: '2026-09-17T12:00:00Z', closed_at: '2026-09-17T11:00:00Z', role_ref: { name: 'Product Lead' } },
    skills: [
      { skill_id: 'K1.1', skill_name: 'Понимание собеседника', previous: 1.75, current: 2.25, difference: 0.5, comparability: { status: 'allowed', reason: null } },
      { skill_id: 'K1.2', skill_name: 'Ясность сообщения', previous: null, current: 2.25, difference: null, comparability: { status: 'not_allowed', reason: 'full_score_required' } },
    ],
  };
  await page.route('**/users/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'rad01-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_dashboard', profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'report_ready' } });
    if (pathname === '/users/assessment/m8/reports/report-rad01') return fulfillJson(route, report);
    if (pathname === '/users/assessment/m8/history') return fulfillJson(route, { cycles: [
      { cycle_id: 'cycle-rad01', report_id: 'report-rad01', program_name: 'Программа сейчас', collection_closed_at: '2026-10-17T11:00:00Z' },
      { cycle_id: 'cycle-previous', report_id: 'report-previous', program_name: 'Программа ранее', collection_closed_at: '2026-09-17T11:00:00Z' },
      { cycle_id: 'cycle-other', report_id: 'report-other', program_name: 'Другая программа', collection_closed_at: '2026-08-17T11:00:00Z' },
    ] });
    if (pathname === '/users/assessment/m8/reports/report-rad01/comparison') {
      if (new URL(route.request().url()).searchParams.get('previous_report_id') === 'report-other') {
        await new Promise((resolve) => setTimeout(resolve, 250));
        return fulfillJson(route, { ...comparison, previous: { ...comparison.previous, report_id: 'report-other', program_name: 'Другая программа' } });
      }
      return fulfillJson(route, comparison);
    }
    return fulfillJson(route, {}, 404);
  });
  const assertComparisonPdfPair = async () => {
    const request = page.waitForRequest((item) => new URL(item.url()).pathname.endsWith('/comparison.pdf'));
    await page.getByRole('button', { name: 'Скачать сравнение PDF' }).click();
    const url = new URL((await request).url());
    expect(url.pathname).toBe('/users/assessment/m8/reports/report-rad01/comparison.pdf');
    expect(url.searchParams.get('previous_report_id')).toBe('report-previous');
    await expect(page.locator('.report-pdf-action [role="status"]')).toContainText('Не удалось скачать PDF');
  };
  await page.goto(base);
  await page.locator('#completed-assessments').getByRole('button', { name: 'Открыть отчёт', exact: true }).click();
  await expect(page.locator('#m8-report-chart svg')).toBeVisible();
  const waitColors = await page.evaluate(() => {
    const styles = getComputedStyle(document.documentElement);
    return {
      background: styles.getPropertyValue('--status-wait-bg').trim(),
      text: styles.getPropertyValue('--status-wait-text').trim(),
    };
  });
  expect(waitColors).toEqual({ background: '#ffe5e0', text: '#ff563d' });
  await expect(page.locator('.m8-radar-label').filter({ hasText: 'Понимание' })).toContainText('собеседника');
  await expect(page.locator('.m8-radar-point')).toHaveCount(2);
  await expect(page.locator('.m8-radar-point.is-partial')).toHaveCount(1);
  await expect(page.locator('#m8-report-skills .m8-skill-row')).toHaveCount(skills.length);
  await expect(page.locator('#m8-report-skills')).toContainText('Результат по части навыка');
  await expect(page.locator('#m8-report-chart-note')).toContainText('Пропуски оставлены открытыми');
  await page.getByRole('button', { name: 'Сравнить оценки' }).click();
  await expect(page.locator('.m8-comparison-table')).toContainText('+0,50');
  await expect(page.locator('.m8-comparison-periods')).toContainText('Программа ранее');
  await expect(page.locator('.m8-comparison-periods')).toContainText('Программа сейчас');
  await page.getByRole('group', { name: 'Вид сравнения' }).getByRole('button', { name: 'Шкалы' }).click();
  await expect(page.locator('.m8-comparison-scales .m8-comparison-scale')).toHaveCount(2);
  await expect(page.locator('.m8-comparison-table')).toContainText('нет полного результата');
  await assertComparisonPdfPair();
  await page.locator('#m8-comparison-select').selectOption('report-other');
  await expect(page.locator('#m8-comparison-content')).toContainText('Загружаем выбранную пару');
  await page.locator('#m8-comparison-select').selectOption('report-previous');
  await page.waitForTimeout(300);
  await expect(page.locator('.m8-comparison-periods')).toContainText('Программа ранее');
  await expect(page.locator('.m8-comparison-periods')).not.toContainText('Другая программа');
  expect(new URL(page.url()).searchParams.get('previous_report_id')).toBe('report-previous');
  await assertComparisonPdfPair();
  const comparisonEvidence = path.join(root, 'docs/evc/tasks/p4k-report-07/evidence');
  await fs.mkdir(comparisonEvidence, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('.m8-comparison').screenshot({ path: path.join(comparisonEvidence, 'comparison-1440.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.m8-comparison').screenshot({ path: path.join(comparisonEvidence, 'comparison-390.png') });
  await page.setViewportSize({ width: 320, height: 700 });
  const comparisonGeometry = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: document.documentElement.clientWidth }));
  expect(comparisonGeometry.scroll).toBe(comparisonGeometry.viewport);
  // 683 CSS px is the available layout width at 200% zoom on a 1366 px display.
  await page.setViewportSize({ width: 683, height: 900 });
  await expect(page.locator('.m8-comparison-table')).toContainText('+0,50');
  const zoomGeometry = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
    contentRight: document.querySelector('#m8-comparison-content').getBoundingClientRect().right,
  }));
  expect(zoomGeometry.scroll).toBe(zoomGeometry.viewport);
  expect(zoomGeometry.contentRight).toBeLessThanOrEqual(zoomGeometry.viewport);
  await page.locator('.m8-comparison').screenshot({ path: path.join(comparisonEvidence, 'comparison-200pct-equivalent.png') });
  let comparisonVariant = { ...comparison, skills: [comparison.skills[0]] };
  await page.route('**/users/assessment/m8/reports/report-rad01/comparison*', (route) => fulfillJson(route, comparisonVariant));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('[data-compare-back]').click();
  await page.getByRole('button', { name: 'Сравнить оценки' }).click();
  await expect(page.locator('.m8-comparison-table')).toContainText('+0,50');
  await page.locator('.m8-comparison').screenshot({ path: path.join(comparisonEvidence, 'comparison-numeric-1440.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.m8-comparison').screenshot({ path: path.join(comparisonEvidence, 'comparison-numeric-390.png') });
  comparisonVariant = { ...comparison,
    previous: { ...comparison.previous, role_ref: { name: 'Другая роль' } },
    skills: comparison.skills.map((item) => ({ ...item, difference: null,
      comparability: { status: 'not_allowed', reason: 'different_role' } })) };
  await page.locator('[data-compare-back]').click();
  await page.getByRole('button', { name: 'Сравнить оценки' }).click();
  await expect(page.locator('.m8-comparison-table')).toContainText('Роли в оценках различаются');
  await expect(page.locator('.m8-comparison-table')).not.toContainText('+0,50');
  await expect(page.locator('.m8-comparison-chart .m8-radar-line,.m8-comparison-chart .m8-radar-fill')).toHaveCount(0);
  await page.locator('.m8-comparison').screenshot({ path: path.join(comparisonEvidence, 'comparison-role-390.png') });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('.m8-comparison').screenshot({ path: path.join(comparisonEvidence, 'comparison-role-1440.png') });
  await page.locator('[data-compare-back]').click();
  await page.getByRole('button', { name: 'Шкалы' }).click();
  await expect(page.locator('.m8-score-bars')).toBeVisible();
  await page.setViewportSize({ width: 360, height: 760 });
  await expect(page.getByRole('button', { name: 'Заливка' })).toBeDisabled();
  await expect(page.locator('.m8-score-bar')).toHaveCount(skills.length);
  await page.locator('#m8-report-tab-select').selectOption('K1');
  await page.getByRole('button', { name: 'Заливка' }).click();
  await expect(page.locator('#m8-report-chart svg')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 900 });
  await expect(page.locator('.m8-radar-key li')).toHaveCount(3);
  await expect(page.locator('.m8-radar-key')).toContainText('Понимание собеседника');
  await expect(page.locator('.m8-radar-key')).toContainText('Нет числового показателя');
  await expect.poll(() => page.locator('#m8-report-chart').evaluate((chart) => {
    const svg = chart.querySelector('svg');
    const label = svg?.querySelector('.m8-radar-marker');
    if (!label || !svg.viewBox.baseVal.width) return 0;
    return parseFloat(getComputedStyle(label).fontSize) * svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
  }), { message: 'mobile radar marker should not shrink below 12 CSS px' }).toBeGreaterThanOrEqual(12);
  for (const width of [320, 360, 430, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const bounds = await page.locator('#m8-report-chart').evaluate((chart) => {
      const svg = chart.querySelector('svg');
      const svgBox = svg.getBoundingClientRect();
      const inset = 19 * svgBox.width / svg.viewBox.baseVal.width;
      return [...svg.querySelectorAll('.m8-radar-label, .m8-radar-marker-bg')].map((label) => {
        const box = label.getBoundingClientRect();
        return {
          left: box.left,
          top: box.top,
          right: box.right,
          bottom: box.bottom,
          minX: svgBox.left + inset,
          minY: svgBox.top + inset,
          maxX: svgBox.right - inset,
          maxY: svgBox.bottom - inset,
        };
      });
    });
    for (const box of bounds) {
      expect(box.left).toBeGreaterThanOrEqual(box.minX);
      expect(box.top).toBeGreaterThanOrEqual(box.minY);
      expect(box.right).toBeLessThanOrEqual(box.maxX);
      expect(box.bottom).toBeLessThanOrEqual(box.maxY);
    }
  }
  const layout = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
  expect(layout.scrollWidth).toBe(layout.clientWidth);
});

test('UI02 full overview keeps every radar label separate', async ({ page }) => {
  const names = [
    'Ориентация и проектирование коммуникации',
    'Передача смысла',
    'Слушание, реконструкция и верификация смысла другого',
    'Согласование смыслов и позиций',
    'Организация совместной работы',
    'Координация совместных действий',
    'Поддержание продуктивного командного взаимодействия',
    'Исследование пространства возможностей',
    'Создание новых идей и решений',
    'Развитие и доведение нового решения',
    'Анализ и оценка информации',
    'Постановка и анализ проблемы',
    'Рассуждение, аргументация и проверка выводов',
    'Принятие решений',
    'Понимание собеседника',
  ];
  const skills = names.map((skill_name, index) => ({
    skill_id: `S${index + 1}`, competency_id: 'K1', competency_name: 'Коммуникация',
    skill_name, outcome: 'full_score', score: { value: 1, numerator: 1, denominator: 1 },
  }));
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Synthetic' };
  const dashboard = {
    greeting_name: 'Synthetic', profile_readiness: 'ready', personalized_profile_id: 11,
    active_assessment: null, available_assessments: [], reports: [], reports_total: 1,
    current_assessments: [], completed_assessments: [{
      cycle_id: 'cycle-radar', report_id: 'report-radar', title: 'Оценка 4К',
      status: 'report_ready', status_label: 'Результат готов', action: 'open_report',
      button_label: 'Посмотреть результат',
    }],
  };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'radar-layout-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_dashboard', profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'report_ready' } });
    if (pathname === '/users/assessment/m8/reports/report-radar') return fulfillJson(route, {
      id: 'report-radar', owner_user_id: 8, cycle_id: 'cycle-radar', revision_no: 1,
      created_at: '2026-10-19T12:00:00Z', c67: {
        skills, competencies: [{ competency_id: 'K1', competency_name: 'Коммуникация', skill_ids: skills.map((skill) => skill.skill_id) }],
        descriptive: { status: 'ready', summary: [], claims: [] },
        coverage: {}, limitations: [], reliability: { status: 'not_verified' }, sessions: [], collection: {},
      },
    });
    if (pathname === '/users/assessment/m8/history') return fulfillJson(route, { cycles: [] });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#completed-assessments').getByRole('button', { name: 'Открыть отчёт', exact: true }).click();
  await expect(page.locator('.m8-radar-label')).toHaveCount(names.length);
  for (const width of [768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const boxes = await page.locator('#m8-report-chart svg').evaluate((svg) => {
      const bounds = svg.getBoundingClientRect();
      const inset = 19 * bounds.width / svg.viewBox.baseVal.width;
      return [...svg.querySelectorAll('.m8-radar-label')].map((label) => {
        const box = label.getBoundingClientRect();
        return { left: box.left, top: box.top, right: box.right, bottom: box.bottom,
          minX: bounds.left + inset, minY: bounds.top + inset,
          maxX: bounds.right - inset, maxY: bounds.bottom - inset };
      });
    });
    for (const [index, box] of boxes.entries()) {
      expect(box.left).toBeGreaterThanOrEqual(box.minX);
      expect(box.top).toBeGreaterThanOrEqual(box.minY);
      expect(box.right).toBeLessThanOrEqual(box.maxX);
      expect(box.bottom).toBeLessThanOrEqual(box.maxY);
      for (const other of boxes.slice(index + 1)) {
        const overlaps = box.left < other.right + 2 && box.right + 2 > other.left &&
          box.top < other.bottom + 2 && box.bottom + 2 > other.top;
        expect(overlaps, `labels ${index} and ${boxes.indexOf(other)} overlap at ${width}px`).toBe(false);
      }
    }
    const pageWidth = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
    expect(pageWidth.scroll).toBe(pageWidth.client);
  }
  await test.info().attach('radar-overview', {
    body: await page.locator('#m8-report-chart').screenshot(), contentType: 'image/png',
  });
  await page.locator('#m8-report-chart a').first().focus();
  await expect(page.locator('#m8-report-chart a').first()).toBeFocused();
});

test('QA19-04 keeps four M8 competency radars readable across mobile and desktop widths', async ({ page }) => {
  const groups = [
    ['Коммуникация', ['Ориентация и проектирование коммуникации', 'Передача смысла',
      'Слушание, реконструкция и верификация смысла другого', 'Согласование смыслов и позиций']],
    ['Командная работа', ['Организация совместной работы', 'Координация совместных действий',
      'Поддержание продуктивного командного взаимодействия']],
    ['Креативность', ['Исследование пространства возможностей', 'Создание новых идей и решений',
      'Развитие и доведение нового решения']],
    ['Критическое мышление', ['Анализ и оценка информации', 'Постановка и анализ проблемы',
      'Рассуждение, аргументация и проверка выводов', 'Принятие решений']],
  ];
  const skills = groups.flatMap(([competency_name, names], groupIndex) => names.map((skill_name, index) => {
    const value = groupIndex === 0 ? [0, 3, 1.5, 2][index]
      : groupIndex === 1 ? [2, null, 1][index]
        : groupIndex === 2 ? 2 : null;
    return { skill_id: `S${groupIndex + 1}-${index + 1}`, competency_id: `K${groupIndex + 1}`,
      competency_name, skill_name, outcome: value == null ? 'no_result'
        : groupIndex === 1 && index === 0 ? 'partial_score' : 'full_score',
      ...(value == null ? {} : { score: { value, numerator: value, denominator: 1 } }) };
  }));
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Synthetic' };
  const dashboard = {
    greeting_name: 'Synthetic', profile_readiness: 'ready', personalized_profile_id: 11,
    active_assessment: null, available_assessments: [], reports: [], reports_total: 1,
    current_assessments: [], completed_assessments: [{ cycle_id: 'cycle-qa04', report_id: 'report-qa04',
      title: 'Оценка 4К', status: 'report_ready', status_label: 'Результат готов',
      action: 'open_report', button_label: 'Посмотреть результат' }],
  };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'qa19-04-fixture' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_dashboard',
      profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'report_ready' } });
    if (pathname === '/users/assessment/m8/reports/report-qa04') return fulfillJson(route, {
      id: 'report-qa04', owner_user_id: 8, cycle_id: 'cycle-qa04', revision_no: 1,
      created_at: '2026-10-19T12:00:00Z', c67: {
        skills, competencies: groups.map(([competency_name], index) => ({
          competency_id: `K${index + 1}`, competency_name,
          skill_ids: skills.filter((skill) => skill.competency_id === `K${index + 1}`).map((skill) => skill.skill_id),
        })),
        descriptive: { status: 'ready', summary: [], claims: [] }, coverage: {}, limitations: [],
        reliability: { status: 'not_verified' }, sessions: [], collection: {},
      },
    });
    if (pathname === '/users/assessment/m8/history') return fulfillJson(route, { cycles: [
      { cycle_id: 'cycle-qa04', report_id: 'report-qa04', collection_closed_at: '2026-10-19T11:00:00Z' },
      { cycle_id: 'cycle-qa04-previous', report_id: 'report-qa04-previous', collection_closed_at: '2026-09-19T11:00:00Z' },
    ] });
    if (pathname === '/users/assessment/m8/reports/report-qa04/comparison') return fulfillJson(route, {
      mode: 'mixed',
      current: { cycle_id: 'cycle-qa04', report_id: 'report-qa04', created_at: '2026-10-19T12:00:00Z' },
      previous: { cycle_id: 'cycle-qa04-previous', report_id: 'report-qa04-previous', created_at: '2026-09-19T12:00:00Z' },
      skills: [
        { skill_id: 'S1-1', skill_name: groups[0][1][0], previous: 1, current: 0, difference: -1,
          comparability: { status: 'allowed', reason: null } },
        { skill_id: 'S2-2', skill_name: groups[1][1][1], previous: null, current: null, difference: null,
          comparability: { status: 'not_allowed', reason: 'full_score_required' } },
      ],
    });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#completed-assessments').getByRole('button', { name: 'Открыть отчёт', exact: true }).click();
  await page.evaluate(async () => { await document.fonts.ready; });

  // 683 CSS px approximates a 1366 px display at 200% browser zoom.
  for (const width of [320, 360, 375, 390, 430, 683]) {
    await page.setViewportSize({ width, height: 900 });
    for (let groupIndex = 0; groupIndex < groups.length; groupIndex += 1) {
      await page.locator('#m8-report-tab-select').selectOption(`K${groupIndex + 1}`);
      if (groupIndex === 3) {
        await expect(page.locator('.m8-chart-empty')).toBeVisible();
        await expect(page.locator('#m8-report-skills .m8-skill-row')).toHaveCount(groups[groupIndex][1].length);
        continue;
      }
      await expect(page.locator('.m8-radar-key li')).toHaveCount(groups[groupIndex][1].length);
      const geometry = await page.locator('#m8-report-chart').evaluate((node) => {
        const svg = node.querySelector('svg');
        const chart = svg.getBoundingClientRect();
        const scale = chart.width / svg.viewBox.baseVal.width;
        const markers = [...svg.querySelectorAll('.m8-radar-marker-bg')].map((item) => item.getBoundingClientRect());
        const keyNames = [...node.querySelectorAll('.m8-radar-key-name')];
        return {
          markerFont: parseFloat(getComputedStyle(svg.querySelector('.m8-radar-marker')).fontSize) * scale,
          tickFont: parseFloat(getComputedStyle(svg.querySelector('.m8-radar-scale')).fontSize) * scale,
          nameFonts: keyNames.map((item) => parseFloat(getComputedStyle(item).fontSize)),
          names: keyNames.map((item) => item.textContent),
          markers: markers.map((box) => ({ left: box.left, top: box.top, right: box.right, bottom: box.bottom })),
          chart: { left: chart.left, top: chart.top, right: chart.right, bottom: chart.bottom },
          overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        };
      });
      expect(geometry.names).toEqual(groups[groupIndex][1]);
      expect(geometry.markerFont).toBeGreaterThanOrEqual(12);
      expect(geometry.tickFont).toBeGreaterThanOrEqual(12);
      expect(geometry.nameFonts.every((size) => size >= 14)).toBe(true);
      expect(geometry.overflow).toBe(false);
      for (const [index, marker] of geometry.markers.entries()) {
        expect(marker.left).toBeGreaterThanOrEqual(geometry.chart.left);
        expect(marker.right).toBeLessThanOrEqual(geometry.chart.right);
        expect(marker.top).toBeGreaterThanOrEqual(geometry.chart.top);
        expect(marker.bottom).toBeLessThanOrEqual(geometry.chart.bottom);
        for (const other of geometry.markers.slice(index + 1)) {
          expect(marker.left < other.right && marker.right > other.left &&
            marker.top < other.bottom && marker.bottom > other.top).toBe(false);
        }
      }
    }
  }
  await page.locator('#m8-report-tab-select').selectOption('K1');
  await expect(page.locator('.m8-radar-key')).toContainText('0 из 3');
  await expect(page.locator('.m8-radar-key')).toContainText('3 из 3');
  await page.locator('.m8-radar-key a').first().focus();
  await expect(page.locator('.m8-radar-key a').first()).toBeFocused();
  await page.locator('.m8-radar-key a').first().click();
  await expect(page.locator('#m8-skill-detail')).toBeFocused();

  for (const width of [768, 1024, 1366, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    // The detail column can narrow the chart as the viewport grows. Wait for
    // the resize handler to rebuild the SVG before measuring its rendered text.
    await expect.poll(() => page.locator('#m8-report-chart svg').evaluate((svg) =>
      Math.abs(svg.getBoundingClientRect().width - svg.viewBox.baseVal.width),
    ), { message: `Radar resize at ${width}px` }).toBeLessThanOrEqual(1);
    if (width <= 960) {
      await expect(page.locator('.m8-radar-key li')).toHaveCount(groups[0][1].length);
      await expect(page.locator('.m8-radar-label')).toHaveCount(0);
    } else {
      // The FIX-02 detail panel also takes space on desktop. Both supported
      // layouts must show every name once, at the readable sizes below.
      const [labels, keyItems] = await page.locator('#m8-report-chart').evaluate((node) => [
        node.querySelectorAll('.m8-radar-label').length, node.querySelectorAll('.m8-radar-key li').length,
      ]);
      expect(labels + keyItems).toBe(groups[0][1].length);
      expect(labels === 0 || keyItems === 0).toBe(true);
    }
    const geometry = await page.locator('#m8-report-chart').evaluate((node) => {
      const svg = node.querySelector('svg');
      const chart = svg.getBoundingClientRect();
      const scale = chart.width / svg.viewBox.baseVal.width;
      return {
        labelFonts: [...svg.querySelectorAll('.m8-radar-label')]
          .map((item) => parseFloat(getComputedStyle(item).fontSize) * scale),
        markerFonts: [...svg.querySelectorAll('.m8-radar-marker')]
          .map((item) => parseFloat(getComputedStyle(item).fontSize) * scale),
        keyFonts: [...node.querySelectorAll('.m8-radar-key-name')]
          .map((item) => parseFloat(getComputedStyle(item).fontSize)),
        tickFonts: [...svg.querySelectorAll('.m8-radar-scale')]
          .map((item) => parseFloat(getComputedStyle(item).fontSize) * scale),
        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      };
    });
    const readableNames = geometry.labelFonts.length ? geometry.labelFonts : geometry.keyFonts;
    expect(readableNames.every((size) => size >= 14), JSON.stringify(geometry)).toBe(true);
    expect(geometry.markerFonts.every((size) => size >= 12), JSON.stringify(geometry)).toBe(true);
    expect(geometry.tickFonts.every((size) => size >= 12), JSON.stringify(geometry)).toBe(true);
    expect(geometry.overflow).toBe(false);
    if (width === 768 || width === 1024) {
      await test.info().attach(`qa19-04-radar-${width}`, {
        body: await page.locator('#m8-report-chart').screenshot(), contentType: 'image/png',
      });
    }
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await expect(page.locator('.m8-radar-key li')).toHaveCount(groups[0][1].length);
  await page.getByRole('button', { name: 'Сравнить оценки' }).click();
  await expect(page.locator('.m8-comparison-table')).toContainText('-1');
  await expect(page.locator('.m8-comparison-table')).toContainText('нет полного результата');
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
  await test.info().attach('qa19-04-mobile-radar', {
    body: await page.locator('.m8-comparison-chart').screenshot(), contentType: 'image/png',
  });
});

test('R03 late login cannot replace a password-reset step', async ({ page }) => {
  await baseRoutes(page);
  await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, {
    email: 'person@example.test', auth_mode: 'password', message: 'Введите пароль.',
  }));
  let finishLogin;
  await page.route('**/users/auth/email/password-login', (route) => { finishLogin = () => fulfillJson(route, {
    exists: true, user: { id: 3, email: 'person@example.test', full_name: 'Person' }, is_admin: false,
    agent: { session_id: 'session', message: '', stage: 'profile', completed: false }, dashboard: {},
  }); });
  await page.goto(base);
  await page.locator('#email-input').fill('person@example.test');
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#forgot-password-credential-button')).toBeDisabled();
  finishLogin();
});

test('R03 first mouse click keeps tooltip open and second closes it', async ({ page }) => {
  await baseRoutes(page);
  await page.route('**/users/auth/email/confirm', (route) => fulfillJson(route, {
    email: 'person@example.test', auth_mode: 'password_registration', message: 'Создайте пароль.',
  }));
  await page.goto(`${base}/?auth_action=email_verification&token=verify-r03`);
  const trigger = page.locator('#auth-password-requirements-trigger');
  const popover = page.locator('#auth-password-requirements-popover');
  await trigger.hover();
  await trigger.click();
  await expect(popover).toBeVisible();
  await trigger.click();
  await expect(popover).toBeHidden();
});

test('R03 expired reset opens explicit recovery email entry', async ({ page }) => {
  await baseRoutes(page);
  await page.route('**/users/auth/password/reset/validate', (route) => fulfillJson(route, { detail: 'Срок действия ссылки истёк.' }, 400));
  let forgotRequests = 0;
  await page.route('**/users/auth/password/forgot', (route) => {
    forgotRequests += 1;
    return fulfillJson(route, { message: 'Письмо отправлено' });
  });
  await page.goto(`${base}/?auth_action=password_reset&token=expired-r03`);
  await page.locator('#auth-change-email-button').click();
  await expect(page.locator('#auth-title')).toHaveText('Восстановление пароля');
  await expect(page.locator('#email-input')).toBeVisible();
  await page.locator('#email-input').fill('person@example.test');
  await page.locator('#request-magic-link-button').click();
  await expect(page.locator('#auth-email-sent')).toBeVisible();
  expect(forgotRequests).toBe(1);
});

test('R03 queued batch is not reported as provider accepted', async ({ page }) => {
  await openAdminOrganizations(page, (route) => fulfillJson(route, {
    items: [{ email: 'person@example.test', status: 'queued', invitation_id: 1 }],
  }));
  await page.locator('input[name="invitation_email"]').check();
  await page.locator('[data-action="send-member-invitations"] button').click();
  await expect(page.locator('#admin-organizations-status')).toContainText('Приняты сервисом: 0. Не отправлены: 0. Исход уточняется: 1');
  await expect(page.locator('#admin-organizations-status')).not.toContainText('Почтовый сервис принял');
});

test('R03 network retry reuses invitation operation id', async ({ page }) => {
  const keys = [];
  await openAdminOrganizations(page, (route) => {
    if (route.request().method() === 'POST') keys.push(route.request().headers()['idempotency-key']);
    return route.request().method() === 'POST' ? route.abort('failed') : fulfillJson(route, {}, 404);
  }, { ...adminOrganization, members: [{ ...adminOrganization.members[0], invitation_status: 'not_sent', invitation_delivery_status: 'not_sent' }] });
  const row = page.locator('.admin-organization-member').first();
  const button = row.locator('[data-action="send-member-invitation"]');
  await button.click();
  await expect(page.locator('#admin-organizations-status')).toContainText('Исход отправки пока неизвестен');
  await page.locator('[data-action="recover-member-invitation"]').first().click();
  await expect.poll(() => keys.length).toBe(2);
  expect(keys[0]).toBe(keys[1]);
});

test('R03 processing deep link obeys server journey before local state', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  await page.addInitScript(({ user }) => {
    localStorage.setItem('agent4k.pendingUser', JSON.stringify(user));
    localStorage.setItem('agent4k.assessmentSessionId', '99');
    localStorage.setItem('agent4k.currentScreen', 'processing');
  }, { user });
  let journeyRead = false;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, {
      user, is_admin: false,
      dashboard: { active_assessment: { code: 'competencies_4k', title: 'Компетенции 4К', description: 'Тест', completed_cases: 0, progress_percent: 0, status_label: 'Не начато', button_label: 'Начать' }, available_assessments: [], reports: [] },
    });
    if (pathname === '/users/8/journey-state') {
      journeyRead = true;
      return fulfillJson(route, { next_action: 'show_dashboard', profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'report_ready' } });
    }
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=processing`);
  await expect(page.locator('#dashboard-panel')).toBeVisible();
  expect(journeyRead).toBe(true);
  await expect(page.locator('#processing-panel')).toBeHidden();
});

test('R03 direct interview URL uses journey and keeps Cycle failure visible', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  await page.addInitScript(({ user }) => localStorage.setItem('agent4k.pendingUser', JSON.stringify(user)), { user });
  let journeyRead = false;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') {
      journeyRead = true;
      return fulfillJson(route, {
        next_action: 'show_assessment_error', profile: { status: 'complete' }, onboarding: { status: 'completed' },
        assessment: { status: 'failed', runtime_kind: 'cycle', cycle_id: 'current-cycle', cycle_session_id: 'session-1', assessment_situation_id: 'as-1' },
      });
    }
    if (pathname === '/users/assessment/m8/cycles/current-cycle/status') return fulfillJson(route, {
      results_status: 'failed', report_status: 'limited', processing_error: 'CONTROLLED_CODE', pipeline_stage: 'failed',
    });
    return fulfillJson(route, {}, 404);
  });

  await page.goto(`${base}/?screen=interview&cycle_id=stale-cycle`);
  await expect(page.locator('#processing-panel')).toBeVisible();
  await expect(page.locator('#processing-outcome-title')).toContainText('Не удалось подготовить результат');
  await expect(page.locator('#processing-panel').getByRole('button', { name: 'Проверить ещё раз', exact: true })).toBeVisible();
  expect(journeyRead).toBe(true);
  expect(await page.evaluate(() => localStorage.getItem('agent4k.productCycleId'))).toBe('current-cycle');
});

test('E02 shows ready Cycle without automatic navigation and keeps mobile actions usable', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  await page.setViewportSize({ width: 375, height: 667 });
  await page.addInitScript(({ user }) => localStorage.setItem('agent4k.pendingUser', JSON.stringify(user)), { user });
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'e02-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'show_processing', report_status: 'ready', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'report_ready', runtime_kind: 'cycle', cycle_id: 'ready-cycle' },
    });
    if (pathname === '/users/assessment/m8/cycles/ready-cycle/status') return fulfillJson(route, {
      results_status: 'ready', report_status: 'ready', report_id: 'report-1', close_reason: 'complete',
      route_progress: { completed: 3, total: 3 }, partial_result: null,
    });
    return fulfillJson(route, {}, 404);
  });

  await page.goto(`${base}/?screen=processing`);
  await expect(page.locator('#processing-outcome-title')).toHaveText('Ваш результат готов');
  await expect(page.locator('#report-panel')).toBeHidden();
  const action = page.getByRole('button', { name: 'Посмотреть результат' });
  await expect(action).toBeVisible();
  expect(await action.evaluate((node) => Math.round(node.getBoundingClientRect().height))).toBeGreaterThanOrEqual(48);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('E02 never promotes a stalled Cycle status to journey readiness', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  let journeyReads = 0;
  await page.addInitScript(({ user }) => localStorage.setItem('agent4k.pendingUser', JSON.stringify(user)), { user });
  await page.route('**/users/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'e02-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') {
      journeyReads += 1;
      return fulfillJson(route, {
        next_action: 'show_processing', report_status: 'ready',
        profile: { status: 'complete' }, onboarding: { status: 'completed' },
        assessment: { status: 'report_ready', runtime_kind: 'cycle', cycle_id: 'slow-cycle' },
      });
    }
    if (pathname === '/users/assessment/m8/cycles/slow-cycle/status') {
      await new Promise((resolve) => setTimeout(resolve, 6000));
      return fulfillJson(route, { results_status: 'processing', report_status: 'not_created' });
    }
    return fulfillJson(route, {}, 404);
  });

  await page.goto(`${base}/?screen=processing`);
  await expect(page.locator('#processing-outcome-title')).toHaveText('Завершение не подтверждено', { timeout: 10000 });
  await expect(page.getByRole('button', { name: 'Посмотреть результат', exact: true })).toBeHidden();
  expect(journeyReads).toBe(1);
});

test('R03 fresh login persists journey assessment identifiers', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/auth/email/request-link') return fulfillJson(route, { email: user.email, auth_mode: 'password' });
    if (pathname === '/users/auth/email/password-login') return fulfillJson(route, { exists: true, user, is_admin: false, agent: { session_id: 'profile', message: '', stage: 'profile', completed: false }, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' }, assessment: { status: 'in_progress', session_id: 99, session_code: 'session-99' } });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.locator('#email-input').fill(user.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('#prechat-panel')).toBeVisible();
  const saved = await page.evaluate(() => ({ id: localStorage.getItem('agent4k.assessmentSessionId'), code: localStorage.getItem('agent4k.assessmentSessionCode') }));
  expect(saved).toEqual({ id: '99', code: 'session-99' });
});

test('P03 return card hides stopped AS and keeps explicit continue in the same chat', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  let runtimeReads = 0;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'p03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-p03', cycle_session_id: 'session-p03', assessment_situation_id: 'as-old' },
    });
    if (pathname === '/users/assessment/cycles/cycle-p03/runtime') {
      runtimeReads += 1;
      return fulfillJson(route, { detail: 'M7_RETURN_EXPLICIT_CONTINUE_REQUIRED' }, 409);
    }
    if (pathname === '/users/assessment/m7/cycles/cycle-p03/presence') return fulfillJson(route, {
      cycle_id: 'cycle-p03', assessment_situation_id: 'as-old',
      heartbeat_interval_seconds: 30, presence_lease_seconds: 60,
    });
    if (pathname === '/users/assessment/m7/cycles/cycle-p03/return-state') return fulfillJson(route, {
      cycle_id: 'cycle-p03', position_no: 1, current_assessment_situation_id: 'as-old', current_assessment_situation_status: 'active',
      allowed_action: 'replace_current', recognized_absence_seconds: 180, remaining_seconds: 1200,
      calendar_deadline: '2026-10-18T12:00:00Z', progress: { completed_positions: 2, total_positions: 4 },
      generation_operation_id: 'admitted-equivalent-operation',
    });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=interview`);
  await expect(page.locator('.interview-return-card')).toBeVisible();
  await expect(page.locator('.interview-return-card')).not.toContainText('Завершено 2 из 4');
  await expect(page.locator('#interview-case-badge')).toHaveText('Ситуация 1 из 4');
  await expect(page.getByText('Нельзя показывать до Continue')).toBeHidden();
  await expect(page.getByText('Календарный срок:', { exact: false })).toBeHidden();
  await expect(page.locator('.interview-timer-saved')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продолжить', exact: true })).toBeVisible();
  await expect(page.locator('#interview-textarea')).toBeDisabled();
  expect(runtimeReads).toBe(0);
});

test('P03 fresh login opens explicit return card without reading blocked runtime', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  let runtimeReads = 0;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'p03-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: false });
    if (pathname === '/users/auth/email/request-link') return fulfillJson(route, { email: user.email, auth_mode: 'password' });
    if (pathname === '/users/auth/email/password-login') return fulfillJson(route, { exists: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-p03', cycle_session_id: 'session-p03', assessment_situation_id: 'as-old' },
    });
    if (pathname === '/users/assessment/cycles/cycle-p03/runtime') {
      runtimeReads += 1;
      return fulfillJson(route, { detail: 'M7_RETURN_EXPLICIT_CONTINUE_REQUIRED' }, 409);
    }
    if (pathname === '/users/assessment/m7/cycles/cycle-p03/return-state') return fulfillJson(route, {
      cycle_id: 'cycle-p03', position_no: 1, current_assessment_situation_id: 'as-old', current_assessment_situation_status: 'active',
      allowed_action: 'continue_current', recognized_absence_seconds: 180, remaining_seconds: 1200,
      progress: { completed_positions: 2, total_positions: 4 }, provider_config_ref: null,
    });
    return fulfillJson(route, {}, 404);
  });

  await page.goto(base);
  await page.locator('#email-input').fill(user.email);
  await page.locator('#request-magic-link-button').click();
  await page.locator('#magic-token-input').fill('legacy-password');
  await page.locator('#verify-magic-link-button').click();
  await expect(page.locator('.interview-return-card')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Продолжить', exact: true })).toBeVisible();
  await expect(page.locator('#auth-error')).toBeHidden();
  expect(runtimeReads).toBe(0);
});

test('P3-B return card keeps unknown time distinct from known zero', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  let remainingSeconds = null;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'p3b-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-p3b', cycle_session_id: 'session-p3b', assessment_situation_id: 'as-p3b' },
    });
    if (pathname === '/users/assessment/m7/cycles/cycle-p3b/return-state') return fulfillJson(route, {
      cycle_id: 'cycle-p3b', collection_status: 'paused', position_no: 1,
      current_assessment_situation_id: 'as-p3b', current_assessment_situation_status: 'active',
      allowed_action: 'continue_current', remaining_seconds: remainingSeconds,
      progress: { completed_positions: 0, total_positions: 8 },
    });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=interview`);
  await expect(page.getByRole('heading', { name: 'Продолжим оценку?' })).toBeVisible();
  await expect(page.locator('#interview-timer-badge')).toHaveText('Время недоступно');
  await expect(page.getByText('0 мин.', { exact: false })).toBeHidden();
  await expect(page.getByText('Без лимита', { exact: false })).toBeHidden();
  remainingSeconds = 0;
  await page.reload();
  await expect(page.locator('#interview-timer-badge')).toHaveText('00:00');
});

test('P3-B reads server state after a lost Continue response without a second command', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  let continued = false;
  let continueCommands = 0;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/version') return fulfillJson(route, { version: 'p3b-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-lost', cycle_session_id: 'session-lost', assessment_situation_id: 'as-lost' },
    });
    if (pathname === '/users/assessment/m7/cycles/cycle-lost/return-continue') {
      continueCommands += 1;
      continued = true;
      return route.abort('failed');
    }
    if (pathname === '/users/assessment/m7/cycles/cycle-lost/return-state') {
      if (continued) return fulfillJson(route, { detail: 'M7_RETURN_CURRENT_POSITION_NOT_FOUND' }, 409);
      return fulfillJson(route, { cycle_id: 'cycle-lost', collection_status: 'paused', position_no: 1,
        current_assessment_situation_id: 'as-lost', current_assessment_situation_status: 'active',
        allowed_action: 'continue_current', remaining_seconds: 600,
        progress: { completed_positions: 0, total_positions: 8 } });
    }
    if (pathname === '/users/assessment/cycles/cycle-lost/runtime') return fulfillJson(route, {
      cycle_id: 'cycle-lost', status: { collection_status: 'active', remaining_seconds: 600 },
      return_policy_enabled: true,
      route: { positions: [{ position_no: 1, state: 'in_progress', current_assessment_situation_id: 'as-lost' }], progress: { total_positions: 8, completed_positions: 0 } },
      current_situation: { assessment_situation_id: 'as-lost', status: 'active', participant_payload: { title: 'Восстановленная ситуация', assessee_task: 'Продолжите диалог' } },
      trace: { turns: [], events: [] },
    });
    if (pathname === '/users/assessment/m7/cycles/cycle-lost/presence') return fulfillJson(route, {
      cycle_id: 'cycle-lost', assessment_situation_id: 'as-lost', heartbeat_interval_seconds: 30, presence_lease_seconds: 120,
    });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=interview`);
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await expect(page.locator('#interview-messages').getByRole('heading', { name: 'Восстановленная ситуация' })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('agent4k.returnContinuePending'))).toBeNull();
  await page.reload();
  await expect(page.locator('#interview-messages').getByRole('heading', { name: 'Восстановленная ситуация' })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('agent4k.returnContinuePending'))).toBeNull();
  expect(continueCommands).toBe(1);
});

test('E01 renders accepted active assessment copy, colors and AS-scoped draft', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  const deadline = new Date(Date.now()+86400000).toISOString();
  const draft = {version:0,revision:'',text:''};
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/assessment/m5/situations/as-e01/draft') {
      const request=route.request();
      if(request.method()==='PUT') {
        const data=request.postDataJSON();
        expect(data.expected_version).toBe(draft.version);
        Object.assign(draft,{version:draft.version+1,revision:data.revision,text:data.text});
      } else expect(request.method()).toBe('GET');
      return fulfillJson(route,{...draft,owner_id:'8',cycle_id:'cycle-e01',assessment_situation_id:'as-e01',
        slot_id:'dialogue:turn-person',expires_at:deadline});
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: 'e01-test' });
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
      assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: 'cycle-e01', cycle_session_id: 'session-e01', assessment_situation_id: 'as-e01' },
    });
    if (pathname === '/users/assessment/m7/cycles/cycle-e01/return-state') {
      return fulfillJson(route, { detail: 'M7_RETURN_POLICY_NOT_SNAPSHOTTED' }, 409);
    }
    if (pathname === '/users/assessment/cycles/cycle-e01/runtime') return fulfillJson(route, {
      cycle_id: 'cycle-e01', status: { collection_status: 'active', remaining_seconds: 2700, deadline },
      return_policy_enabled: false,
      route: { positions: [{ position_no: 1, state: 'in_progress', current_assessment_situation_id: 'as-e01' }],
        progress: { total_positions: 3, completed_positions: 0 } },
      current_situation: { assessment_situation_id: 'as-e01', status: 'active', participant_payload: {
        title: 'Разговор с коллегой', introduction: 'Вводная Sales AS',
        initial_situation: 'Исходная ситуация', trigger: 'Новое событие',
        assessee_position: 'Ваша роль в разговоре', participants_and_positions: 'Анна — позиция клиента',
        assessee_task: 'Обсудите изменение сроков', conditions_and_constraints: 'Не обещать сроки без проверки',
        initial_materials: [{ material_id: 'M01', title: 'Письмо клиента', text: 'Содержание письма' }],
      } },
      trace: { turns: [{ sequence_no: 1, turn_id: 'turn-person', speaker_type: 'character', speaker_name: 'Анна', content_text: 'Какие варианты вы предлагаете?' }], events: [] },
    });
    return fulfillJson(route, {}, 404);
  });

  await page.goto(`${base}/?screen=interview`);
  await expect(page.locator('#interview-case-badge')).toHaveText('Ситуация 1 из 3');
  await expect(page.locator('#interview-section-title')).toHaveText('4К Ассистент');
  await expect(page.locator('.case-sidebar')).toHaveCount(0);
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  await expect(page.locator('.interview-message--situation')).toContainText('Разговор с коллегой');
  await expect(page.locator('.interview-message--situation')).toContainText('Вводная Sales AS');
  await expect(page.locator('.interview-message--situation')).toContainText('Исходная ситуация');
  await expect(page.locator('.interview-message--situation')).toContainText('Новое событие');
  await expect(page.locator('.interview-message--situation')).toContainText('Ваша роль в разговоре');
  await expect(page.locator('.interview-message--situation')).toContainText('Анна — позиция клиента');
  await expect(page.locator('.interview-message--situation')).toContainText('Обсудите изменение сроков');
  await expect(page.locator('.interview-message--situation')).toContainText('Не обещать сроки без проверки');
  await expect(page.locator('.interview-message--situation')).toContainText('Письмо клиента: Содержание письма');
  await expect(page.getByRole('button', { name: 'Завершить ситуацию' })).toBeHidden();
  await expect(page.locator('.interview-your-turn')).toBeVisible();
  await expect(page.locator('[data-speaker-label="Анна"]')).toBeVisible();
  await expect(page.locator('.interview-bubble.bot').first()).toHaveCSS('background-color', 'rgb(255, 255, 255)');

  await page.locator('#interview-textarea').fill('Мой незавершённый ответ');
  await page.reload();
  await expect(page.locator('.interview-message--situation')).toHaveCount(1);
  await expect(page.locator('#interview-textarea')).toHaveValue('Мой незавершённый ответ');
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.locator('.interview-message--situation')).toContainText('Новое событие');
  await expect(page.locator('#interview-submit-button')).toHaveCSS('height', '48px');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('R03 null journey removes stale legacy and Cycle identifiers', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  await page.addInitScript(() => {
    for (const [key, value] of Object.entries({
      'agent4k.assessmentSessionId': '99',
      'agent4k.assessmentSessionCode': 'stale-code',
      'agent4k.assessmentRuntimeKind': 'cycle',
      'agent4k.productCycleId': 'stale-cycle',
      'agent4k.productAssessmentSituationId': 'stale-as',
    })) localStorage.setItem(key, value);
  });
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user, is_admin: false, dashboard: {},
    });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'show_dashboard', profile: { status: 'complete' },
      onboarding: { status: 'completed' }, assessment: { status: 'not_started' },
    });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r03-test' });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await expect.poll(() => page.evaluate(() => [
      'agent4k.assessmentSessionId', 'agent4k.assessmentSessionCode',
      'agent4k.assessmentRuntimeKind', 'agent4k.productCycleId',
      'agent4k.productAssessmentSituationId',
    ].map((key) => localStorage.getItem(key))))
    .toEqual([null, null, null, null, null]);
});

test('W02 blocks direct entry on missing participant briefing and supports readiness retry on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 720 });
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  let checks = 0;
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user, is_admin: false, dashboard: {},
    });
    if (pathname === '/users/8/journey-state') {
      checks += 1;
      return fulfillJson(route, {
        next_action: 'wait_for_acquaintance_data', profile: { status: 'incomplete' },
        onboarding: { status: 'not_started' }, assessment: { status: 'not_started' },
        acquaintance: { readiness: {
          status: 'waiting_for_organization',
          message: 'Организация ещё готовит данные для вашей оценки. Когда подготовка будет завершена, здесь можно будет начать знакомство',
        } },
      });
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: 'w02-test' });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=onboarding`);
  await expect(page.getByRole('heading', { name: 'Нужны сведения организации' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Проверить готовность' })).toBeVisible();
  await expect(page.locator('#onboarding-panel')).toBeHidden();
  await page.getByRole('button', { name: 'Проверить готовность' }).click();
  await expect.poll(() => checks).toBeGreaterThan(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('PARTICIPANT-LAYOUT-01 keeps early W02 waiting text and actions readable', async ({ page }, testInfo) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  let checks = 0, authenticated = false;
  const readiness = { status: 'waiting_for_organization', reason: 'assignment_sources' };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated, ...(authenticated ? { user, is_admin: false, dashboard: {} } : {}) });
    if (pathname === '/users/organization-invitations/w02-fix-owned') return fulfillJson(route, { organization_id: 10, organization_name: 'Synthetic', recipient_email: user.email, personal: true, auth_mode: 'password_registration' });
    if (pathname === '/users/auth/email/password-register') { authenticated = true; return fulfillJson(route, { user, is_admin: false, dashboard: {} }); }
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') {
      checks++;
      return fulfillJson(route, {
        next_action: 'wait_for_acquaintance_data', profile: { status: 'incomplete' },
        onboarding: { status: 'not_started' }, assessment: { status: 'not_started' },
        acquaintance: { readiness },
      });
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: 'controlled' });
    return fulfillJson(route, {}, 404);
  });
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1024 : 844 });
    if (width === 1440) {
      await page.goto(`${base}/?invite=w02-fix-owned`);
      await waitForPasswordCreationForm(page, user.email);
      await page.locator('#magic-token-input').fill('Synthetic-safe-27!');
      await page.locator('#verify-magic-link-button').click();
      await page.locator('#magic-token-input').fill('Synthetic-safe-27!');
      await page.locator('#verify-magic-link-button').click();
    } else await page.goto(`${base}/?screen=onboarding`);
    const panel = page.locator('#auth-complete-panel');
    await expect(page.locator('#auth-complete-title')).toHaveText('Нужны сведения организации');
    await expect(page.locator('#auth-complete-description')).toHaveText('Организация ещё завершает настройку вашей оценки. Когда сведения будут готовы, здесь появится следующий шаг.');
    await expect(panel.locator('.auth-waiting-note')).toHaveText('Время выполнения ещё не идёт.');
    await expect(panel).not.toContainText(/assignment_sources|Причина ожидания|источники назначения/);
    await expect(panel).toHaveAttribute('data-readiness-reason', 'assignment_sources');
    await expect(panel).not.toContainText('ответы сохранены');
    await expect(panel.getByRole('button', { name: 'Посмотреть знакомство' })).toHaveCount(0);
    const geometry = await panel.evaluate((node) => {
      const copy = node.querySelector('.auth-complete-copy'), description = node.querySelector('#auth-complete-description');
      const card = node.querySelector('.auth-complete-card'), actions = node.querySelector('.auth-complete-actions');
      const rect = (n) => { const r = n.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, bottom: r.bottom }; };
      return { card: rect(card), main: rect(node), header: rect(document.querySelector('.auth-header')), footer: rect(document.querySelector('.app-footer')),
        copyWidth: copy.getBoundingClientRect().width, textWidth: description.getBoundingClientRect().width,
        cardWidth: card.getBoundingClientRect().width, scrollWidth: document.documentElement.scrollWidth,
        buttons: [...actions.querySelectorAll('button')].map((b) => ({ height: b.getBoundingClientRect().height, width: b.getBoundingClientRect().width })),
        direction: getComputedStyle(actions).flexDirection };
    });
    expect(geometry.scrollWidth).toBeLessThanOrEqual(width);
    expect(geometry.textWidth).toBeGreaterThan(width === 1440 ? 600 : 250);
    await expect(page.locator('.auth-header')).toBeVisible();
    expect(geometry.copyWidth).toBe(geometry.textWidth);
    expect(geometry.cardWidth).toBe(width === 1440 ? 760 : 358);
    for (const button of geometry.buttons) expect(button.height).toBe(48);
    expect(geometry.direction).toBe(width === 390 ? 'column' : 'row');
    if (width === 1440) expect(geometry.buttons[0].width).toBeLessThan(300);
    const target = process.env.W02_EVIDENCE_DIR ? path.join(process.env.W02_EVIDENCE_DIR, `early-waiting-${width}.png`) : testInfo.outputPath(`early-waiting-${width}.png`);
    await page.evaluate(() => document.fonts.ready);
    if (!process.env.W02_ADD02_EVIDENCE) await page.screenshot({ path: target, fullPage: false });
    await fs.writeFile(target.replace('.png', '.json'), JSON.stringify(geometry, null, 2));
    const before = checks; await panel.getByRole('button', { name: 'Проверить готовность' }).click();
    await expect.poll(() => checks).toBeGreaterThan(before);
    await expect(panel.getByRole('button', { name: 'Выйти' })).toBeVisible();
    await page.locator('#auth-complete-description').evaluate((node) => { node.textContent = 'ОченьДлинноеСообщение'.repeat(40); });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
});

test('W02 does not present plan cards before the prepared plan exists', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window.crypto, 'randomUUID', {
      configurable: true,
      value: undefined,
    });
  });
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  const acquaintance = {
    readiness: { status: 'ready', organization_name: 'Организация А', briefing: {
      organizer: 'Организация А', purpose: 'Развитие компетенций',
      results_usage: 'Для плана развития', result_recipients: 'Участник',
      provided_participant_fields: [{ label: 'Подразделение', value: 'Продукт' }],
      questions: ['Роль?', 'Задачи?', 'Взаимодействие?'], consent_version: 1,
    } },
    state: { answers_json: {} },
    late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    assigned_timing: { status: 'resolved', time_budget_seconds: 4200, calendar_window_seconds: 172800 },
    prepared_plan: null,
  };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'show_onboarding', profile: { status: 'complete' },
      onboarding: { status: 'not_started', current_step: 0 }, assessment: { status: 'not_started' },
      acquaintance,
    });
    if (pathname === '/users/8/acquaintance') return fulfillJson(route, acquaintance);
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'in_progress', current_step: 0 });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'w02-add01-test' });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await expect(page.getByText('Назначенный общий бюджет')).toBeHidden();
  await expect(page.getByText('Календарное окно после старта')).toBeHidden();
  await expect(page.getByText('Время на выполнение')).toBeHidden();
  await expect(page.getByText('Ориентировочная общая длительность')).toBeHidden();
});

test('UX-AUD29-03 grows the answer and submits desktop Enter only once', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  const acquaintance = {
    readiness: { status: 'ready', organization_name: 'Организация А', briefing: {
      organizer: 'Организация А', purpose: 'Пилот', results_usage: 'Для развития',
      result_recipients: 'Участник', provided_participant_fields: [], questions: ['Опишите задачи', 'Q2', 'Q3'],
      consent_version: 1, consent_text: 'Подтверждаю сведения',
    } },
    state: { answers_json: {} }, mandatory_complete: false,
    onboarding: { status: 'not_started', current_step: 0 },
    late_readiness: { status: 'waiting_for_answers' }, prepared_plan: null,
  };
  let answerRequests = 0;
  await page.route('**/users/**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_onboarding', profile: { status: 'incomplete' },
      onboarding: acquaintance.onboarding, assessment: { status: 'not_started' }, acquaintance });
    if (pathname === '/users/8/acquaintance' && request.method() === 'GET') return fulfillJson(route, acquaintance);
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'in_progress', current_step: 0 });
    if (pathname.endsWith('/acquaintance/consent')) {
      acquaintance.state.consent_accepted_at = 'synthetic'; return fulfillJson(route, acquaintance.state);
    }
    if (pathname.endsWith('/acquaintance/answers')) {
      answerRequests += 1;
      const payload = request.postDataJSON();
      acquaintance.state.answers_json = { ...acquaintance.state.answers_json, ...payload.answers };
      return fulfillJson(route, acquaintance.state);
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: appRelease });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await page.getByRole('button', { name: 'Начать знакомство' }).click();
  await page.getByRole('button', { name: 'Подтвердить' }).click();
  const input = page.locator('.onboarding-answer');
  await input.fill('Строка 1\nСтрока 2\nСтрока 3\nСтрока 4\nСтрока 5\nСтрока 6');
  expect(await input.evaluate((node) => parseFloat(getComputedStyle(node).height))).toBeLessThanOrEqual(120);
  await input.press('Shift+Enter');
  expect(answerRequests).toBe(0);
  await input.press('Enter');
  await expect.poll(() => answerRequests).toBe(1);
  await page.waitForTimeout(100);
  expect(answerRequests).toBe(1);
});

test('R08 shows the frozen program budget instead of the planned duration sum', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Person' };
  const acquaintance = {
    readiness: { status: 'ready', organization_name: 'Организация А', briefing: {
      organizer: 'Организация А', purpose: 'Пилот', results_usage: 'Для развития',
      result_recipients: 'Участник', provided_participant_fields: [], questions: ['Q1', 'Q2', 'Q3'], consent_version: 1,
    } },
    state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' },
      consent_accepted_at: 'synthetic', consent_version: 1, answers_confirmed_at: 'synthetic' },
    mandatory_complete: true, onboarding: { status: 'completed', current_step: 8 },
    late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    assigned_timing: { status: 'resolved', time_budget_seconds: 7200, calendar_window_seconds: 259200 },
    prepared_plan: { cycle_id: 'cycle-r08', revision_id: 'revision-r08', revision_no: 1,
      start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-r08',
        plan_revision_id: 'revision-r08', can_start: true, reasons: [] }, plan: {
      status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], planned_max_seconds: 11340,
      time_budget_seconds: 7200, calendar_window_seconds: 259200,
    } },
  };
  await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'show_onboarding', profile: { status: 'complete' },
      onboarding: { status: 'in_progress', current_step: 5 }, assessment: { status: 'not_started' }, acquaintance,
    });
    if (pathname === '/users/8/acquaintance') return fulfillJson(route, acquaintance);
    if (pathname === '/users/8/acquaintance/resolve-profile') return fulfillJson(route, acquaintance);
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'in_progress', current_step: 5 });
    if (pathname === '/users/version') return fulfillJson(route, { version: 'r08-test' });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(base);
  await expect(page.locator('.onboarding-metrics')).toContainText('на ответы');
  await expect(page.getByText('120 мин', { exact: true })).toBeVisible();
  await expect(page.getByText('189 мин', { exact: true })).toBeHidden();
});

test('AC18-FIX-02 published frontend matches the merged release and asset', async ({ page }) => {
  test.skip(!publishedOrigin, 'Runs only for the explicitly selected published test origin');
  const response = await page.goto(base);
  expect(response?.status()).toBe(200);
  const assetPath = await page.locator('script[type="module"][src^="/web/dist/main.js"]').getAttribute('src');
  expect(assetPath).toContain(`v=${appRelease}`);
  const assetResponse = await page.request.get(new URL(assetPath, base).href);
  expect(assetResponse.status()).toBe(200);
  const deployedHash = createHash('sha256').update(await assetResponse.body()).digest('hex');
  const localHash = createHash('sha256').update(await fs.readFile(path.join(root, 'web/dist/main.js'))).digest('hex');
  expect(deployedHash).toBe(localHash);
  const versionResponse = await page.request.get(`${base}/users/version`);
  expect(versionResponse.status()).toBe(200);
  expect((await versionResponse.json()).version).toBe(appRelease);
});

test('AC18-FIX-02 reconciles a committed first start after the POST response is lost', async ({ page }, testInfo) => {
  const evidenceDirectory = process.env.AC18_FIX02_VISUAL_EVIDENCE;
  if (evidenceDirectory) await fs.mkdir(evidenceDirectory, { recursive: true });
  const capture = async (name) => {
    const body = await page.screenshot({
      fullPage: true, ...(evidenceDirectory ? { path: path.join(evidenceDirectory, `${name}.png`) } : {}),
    });
    await testInfo.attach(name, { body, contentType: 'image/png' });
  };
  const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
  const plan = { cycle_id: 'cycle-lost-start', revision_id: 'revision-lost-start', revision_no: 1,
    start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-lost-start',
      plan_revision_id: 'revision-lost-start', can_start: true, reasons: [] }, plan: {
      status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], time_budget_seconds: 7200,
      calendar_window_seconds: 259200,
    } };
  const acquaintance = {
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } },
    state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' }, consent_accepted_at: 'synthetic',
      consent_version: 1, answers_confirmed_at: 'synthetic' }, mandatory_complete: true,
    onboarding: { status: 'completed', current_step: 8 }, late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    prepared_plan: plan,
  };
  const runtime = { runtime_kind: 'cycle', cycle_id: 'cycle-lost-start', between_situations: false,
    return_policy_enabled: false, status: { collection_status: 'active', remaining_seconds: 7200 },
    route: { positions: [{ position_no: 1, state: 'in_progress',
      current_assessment_situation_id: 'as-lost-start' }], progress: { total_positions: 1 } },
    situations: [{ assessment_situation_id: 'as-lost-start', status: 'active' }],
    current_situation: { assessment_situation_id: 'as-lost-start', status: 'active', participant_payload: {
      title: 'Синтетическая первая ситуация', situation: 'Проверьте сохранённое состояние после потери ответа.',
      assessee_task: 'Опишите решение.',
    } }, trace: { turns: [], events: [] }, clarification: null, continuation: null, pipeline: null };
  let startPosts = 0;
  await page.route('**/users/**', (route) => {
    const request = route.request(); const pathname = new URL(request.url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_onboarding', acquaintance,
      profile: { status: 'complete' }, onboarding: acquaintance.onboarding, assessment: { status: 'not_started' } });
    if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) return fulfillJson(route, acquaintance);
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'completed', current_step: 8 });
    if (pathname === '/users/assessment/cycles/start' && request.method() === 'POST') {
      startPosts += 1; return route.abort('failed');
    }
    if (pathname === '/users/assessment/m7/cycles/cycle-lost-start/return-state') {
      return fulfillJson(route, { detail: 'M7_RETURN_CURRENT_POSITION_NOT_FOUND' }, 409);
    }
    if (pathname === '/users/assessment/cycles/cycle-lost-start/runtime') return fulfillJson(route, runtime);
    if (pathname === '/users/version') return fulfillJson(route, { version: 'ac18-fix02-test' });
    return fulfillJson(route, {}, 404);
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base);
  await expect(page.locator('#onboarding-title')).toHaveText('Ваши кейсы подготовлены');
  await page.getByRole('button', { name: 'Приступить к оценке' }).click();
  await expect(page.locator('#interview-panel')).toBeVisible();
  await expect(page.locator('#interview-case-title')).toHaveText('Синтетическая первая ситуация');
  expect(startPosts).toBe(1);
  await capture('ac18-fix02-lost-start-1440');
  for (const width of [768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator('#interview-case-title')).toHaveText('Синтетическая первая ситуация');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await capture(`ac18-fix02-lost-start-${width}`);
  }
});

test('AC18-FIX-02 reload resolves unknown first start by owned GET without another POST', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
  const plan = { cycle_id: 'cycle-unknown-start', revision_id: 'revision-unknown-start', revision_no: 1,
    start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-unknown-start',
      plan_revision_id: 'revision-unknown-start', can_start: true, reasons: [] },
    plan: { status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], time_budget_seconds: 7200,
      calendar_window_seconds: 259200 } };
  const acquaintance = {
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } },
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
      startPosts += 1; return route.abort('failed');
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
  await expect(page.locator('#onboarding-title')).toHaveText('Ваши кейсы подготовлены');
  await page.getByRole('button', { name: 'Приступить к оценке' }).click();
  await expect(page.locator('#onboarding-panel')).toContainText('Состояние не подтверждено');
  await expect(page.locator('#onboarding-title')).toHaveText('Проверяем начало оценки');
  expect(startPosts).toBe(1);
  await page.reload();
  await expect(page.locator('#onboarding-title')).toHaveText('Проверяем начало оценки');
  await page.getByRole('button', { name: 'Проверить состояние' }).click();
  await expect(page.locator('#interview-case-title')).toHaveText('Сохранённая первая ситуация');
  expect(startPosts).toBe(1);
  expect(runtimeReads).toBeGreaterThanOrEqual(2); // Interview also refreshes its own runtime.
});

test('AC18-FIX-02 reload reads a preparation with lost POST response before any new command', async ({ page }) => {
  const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
  const plan = { cycle_id: 'cycle-preparation-readback', revision_id: 'revision-preparation-readback',
    start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-preparation-readback',
      plan_revision_id: 'revision-preparation-readback', can_start: true, reasons: [] },
    plan: { status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], time_budget_seconds: 7200,
      calendar_window_seconds: 259200 } };
  let committed = false;
  let completed = false;
  let preparePosts = 0;
  let statusReads = 0;
  let operationId;
  const acquaintance = () => ({
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } },
    state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' }, consent_accepted_at: 'synthetic',
      consent_version: 1, answers_confirmed_at: 'synthetic' }, mandatory_complete: true,
    onboarding: { status: 'completed', current_step: 8 },
    late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    preparation_operation: completed ? { operation_id: operationId, status: 'completed' } : null,
    prepared_plan: completed ? plan : null,
  });
  await page.route('**/users/**', (route) => {
    const request = route.request(); const pathname = new URL(request.url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_onboarding',
      acquaintance: acquaintance(), profile: { status: 'complete' },
      onboarding: { status: 'completed', current_step: 8 }, assessment: { status: 'not_started' } });
    if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) {
      return fulfillJson(route, acquaintance());
    }
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'completed', current_step: 8 });
    if (pathname === '/users/assessment/cycles/prepare' && request.method() === 'POST') {
      preparePosts += 1;
      operationId = request.postDataJSON().idempotency_key;
      committed = true; // The server accepted the command; only its HTTP response is lost.
      return route.abort('connectionreset');
    }
    if (pathname === `/users/assessment/cycles/preparation/${operationId}`) {
      statusReads += 1;
      expect(committed).toBe(true);
      if (statusReads === 1) return fulfillJson(route, { detail: 'Synthetic readback unavailable' }, 503);
      completed = true;
      return fulfillJson(route, { operation_id: operationId, status: 'completed', result: { plan } });
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: appRelease });
    return fulfillJson(route, {}, 404);
  });
  await page.goto(`${base}/?screen=onboarding`);
  await expect(page.locator('#onboarding-title')).toHaveText('Не удалось проверить готовность');
  expect(preparePosts).toBe(1);
  await page.reload();
  await expect.poll(() => preparePosts + statusReads).toBeGreaterThan(1);
  expect(preparePosts).toBe(1);
  await expect(page.locator('#onboarding-title')).toHaveText('Подготовка временно недоступна');
  await page.getByRole('button', { name: 'Проверить состояние' }).click();
  await expect(page.locator('#onboarding-title')).toHaveText('Ваши кейсы подготовлены');
  expect(statusReads).toBe(2);
  expect(preparePosts).toBe(1);
});

test('AC18-FIX-02 visual readiness states survive reload without another preparation', async ({ browser }, testInfo) => {
  const evidenceDirectory = process.env.AC18_FIX02_VISUAL_EVIDENCE;
  if (evidenceDirectory) await fs.mkdir(evidenceDirectory, { recursive: true });
  const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic participant' };
  const plan = { cycle_id: 'cycle-visual', revision_id: 'revision-visual', revision_no: 1,
    start_readiness: { contract: 'm7_start_readiness/1', cycle_id: 'cycle-visual',
      plan_revision_id: 'revision-visual', can_start: true, reasons: [] }, plan: {
      status: 'READY', route: [{ case_id: 'CASE.SPEC.01' }], time_budget_seconds: 7200,
      calendar_window_seconds: 259200,
    } };
  let phase = 'waiting';
  let preparePosts = 0;
  let operationReads = 0;
  const acquaintance = () => ({
    readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
      briefing: { organizer: 'Synthetic', purpose: 'Synthetic', results_usage: 'Synthetic',
        result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } },
    state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' }, consent_accepted_at: 'synthetic',
      consent_version: 1, answers_confirmed_at: 'synthetic' }, mandatory_complete: true,
    onboarding: { status: 'completed', current_step: 8 },
    late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    preparation_operation: { operation_id: 'operation-visual', status: ['failed', 'technical_failed'].includes(phase) ? 'failed'
      : phase === 'ready' ? 'completed' : 'running',
      ...(phase === 'failed' ? { retry_allowed: false, error: { code: 'ASSESSMENT_AS_NOT_ADMITTED',
        message: 'Ситуация не прошла обязательную проверку. Обратитесь к ответственному.' } } : {}),
      ...(phase === 'technical_failed' ? { retry_allowed: true, error: {
        code: 'ASSESSMENT_CYCLE_PREPARATION_TECHNICAL_FAILURE',
        message: 'Подготовка завершилась технической ошибкой. Можно повторить её.' } } : {}) },
    prepared_plan: phase === 'ready' ? plan : null,
  });
  const states = [
    ['waiting', 'Готовим вашу оценку', 'Проверить состояние'],
    ['failed', 'Подготовка оценки', 'Проверить состояние'],
    ['technical_failed', 'Подготовка оценки', 'Повторить подготовку'],
    ['unknown', 'Не удалось проверить готовность', 'Повторить проверку'],
    ['ready', 'Ваши кейсы подготовлены', 'Приступить к оценке'],
  ];
  for (const [stateName, title, action] of states) {
    phase = stateName;
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    await blockUnmockedWrites(context);
    const page = await context.newPage();
    await page.route('**/users/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/users/session/restore') return fulfillJson(route, {
      authenticated: true, user, is_admin: false, dashboard: {},
    });
    if (pathname === '/users/8/session-bootstrap') return fulfillJson(route, { user, is_admin: false, dashboard: {} });
    if (pathname === '/users/8/journey-state') return fulfillJson(route, {
      next_action: 'show_onboarding', acquaintance: acquaintance(), profile: { status: 'complete' },
      onboarding: { status: 'completed', current_step: 8 }, assessment: { status: 'not_started' },
    });
    if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) {
      return fulfillJson(route, acquaintance());
    }
    if (pathname === '/users/8/onboarding') return fulfillJson(route, { status: 'completed', current_step: 8 });
    if (pathname === '/users/assessment/cycles/preparation/operation-visual') {
      operationReads += 1;
      if (phase === 'unknown') return route.abort('failed');
      return fulfillJson(route, { operation_id: 'operation-visual', status: 'running' });
    }
    if (pathname === '/users/assessment/cycles/prepare') {
      preparePosts += 1;
      return fulfillJson(route, {}, 500);
    }
    if (pathname === '/users/version') return fulfillJson(route, { version: appRelease });
    return fulfillJson(route, {}, 404);
    });
    await page.goto(`${base}/?screen=onboarding`);
    await expect(page.locator('#onboarding-title')).toHaveText(title);
    const actionButton = page.getByRole('button', { name: action, exact: true });
    await expect(actionButton).toBeVisible();
    await expect(actionButton).toBeEnabled();
    if (['failed', 'technical_failed', 'unknown'].includes(stateName)) {
      await expect(page.locator('.onboarding-spinner')).toHaveCount(0);
      await expect(page.locator('#onboarding-panel')).not.toContainText('M5_FUNCTIONAL_AS_NOT_ADMITTED');
    }
    await page.reload();
    await expect(page.locator('#onboarding-title')).toHaveText(title);
    await actionButton.focus();
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Tab');
    await expect(actionButton).toBeFocused();
    for (const width of [1440, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(page.locator('#onboarding-title')).toHaveText(title);
      await expect(actionButton).toBeVisible();
      await actionButton.scrollIntoViewIfNeeded();
      await expect(actionButton).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      const name = `ac18-fix02-${stateName}-${width}`;
      const body = await page.screenshot({ fullPage: true,
        ...(evidenceDirectory ? { path: path.join(evidenceDirectory, `${name}.png`) } : {}) });
      await testInfo.attach(name, { body, contentType: 'image/png' });
    }
    if (stateName === 'failed') {
      await actionButton.click();
      expect(preparePosts).toBe(0);
      await expect(page.getByRole('button', { name: 'Повторить подготовку' })).toHaveCount(0);
    }
    if (stateName === 'technical_failed') {
      await actionButton.click();
      await expect.poll(() => preparePosts).toBe(1);
    }
    await context.close();
  }
  expect(operationReads).toBeGreaterThan(0);
  expect(preparePosts).toBe(1); // Only the explicit server-permitted technical retry writes.
});

test('R03 reset request locks every visible credential action', async ({ page }) => {
  await baseRoutes(page);
  await page.route('**/users/auth/email/request-link', (route) => fulfillJson(route, { email: 'person@example.test', auth_mode: 'password' }));
  let finishReset;
  await page.route('**/users/auth/password/forgot', (route) => { finishReset = () => fulfillJson(route, { message: 'sent' }); });
  await page.goto(base);
  await page.locator('#email-input').fill('person@example.test');
  await page.locator('#request-magic-link-button').click();
  await page.locator('#forgot-password-credential-button').click();
  for (const selector of ['#magic-token-input', '#verify-magic-link-button', '#auth-change-credential-email-button', '#forgot-password-credential-button']) {
    await expect(page.locator(selector)).toBeDisabled();
  }
  finishReset();
});

for (const [failure, expected] of [
  [403, 'Доступ к оценке изменился'], [409, 'Состояние оценки изменилось'],
  [503, 'Подготовка временно недоступна'], ['network', 'Не удалось проверить готовность'],
  ['failed', 'Подготовка оценки'], ['organization', 'Нужны сведения организации'],
]) {
  test(`PATH29 readiness distinguishes ${failure} without a fake ready plan`, async ({ page }) => {
    const user = { id: 8, email: 'person@example.test', full_name: 'Synthetic' };
    const acquaintance = {
      readiness: { status: 'ready', organization_id: 10, assignment_ref: 'synthetic', questionnaire_revision_id: 1,
        briefing: { organizer: 'Synthetic', purpose: 'Synthetic',
          results_usage: 'Synthetic', result_recipients: 'Synthetic', questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } },
      state: { answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' },
        consent_accepted_at: 'synthetic', consent_version: 1, answers_confirmed_at: 'synthetic' },
      mandatory_complete: true, onboarding: { status: 'completed', current_step: 8 },
      late_readiness: { status: failure === 'organization' ? 'waiting_for_assessment_data' : 'ready_to_prepare', personalized_profile_id: 4 },
      prepared_plan: null,
    };
    let prepares = 0;
    await page.route('**/users/**', (route) => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/users/session/restore') return fulfillJson(route, { authenticated: true, user, is_admin: false, dashboard: {} });
      if (pathname === '/users/8/journey-state') return fulfillJson(route, { next_action: 'show_onboarding', acquaintance,
        profile: { status: 'complete' }, onboarding: acquaintance.onboarding, assessment: { status: 'not_started' } });
      if (['/users/8/acquaintance', '/users/8/acquaintance/resolve-profile'].includes(pathname)) return fulfillJson(route, acquaintance);
      if (pathname === '/users/assessment/cycles/prepare') {
        prepares += 1;
        if (failure === 'network') return route.abort('failed');
        if (typeof failure === 'number') return fulfillJson(route, { detail: 'Synthetic controlled refusal' }, failure);
        return fulfillJson(route, { operation_id: 'synthetic-failed-operation', status: 'failed',
          error: { code: 'ASSESSMENT_CYCLE_PREPARATION_FAILED', message: 'Synthetic controlled job failure' } }, 202);
      }
      if (pathname === '/users/version') return fulfillJson(route, { version: 'path29-test' });
      return fulfillJson(route, {}, 404);
    });
    await page.goto(base);
    await expect(page.locator('#onboarding-title')).toHaveText(expected);
    await expect(page.locator('.onboarding-metrics')).toHaveCount(0);
    await expect(page.locator('.onboarding-spinner')).toHaveCount(0);
    await expect(page.locator('#onboarding-next')).toBeEnabled();
    expect(prepares).toBe(failure === 'organization' ? 0 : 1);
    if (failure === 'organization') await expect(page.locator('#feature-list')).toContainText('Когда сведения будут готовы, здесь появится следующий шаг.');
    if (failure === 'failed') await expect(page.locator('#onboarding-panel')).not.toContainText('synthetic-failed-operation');
  });
}
